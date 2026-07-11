import DocumentIngestion
import Foundation
import SQLite3
import XCTest
@testable import CompanionCore

final class RuntimeDocumentSourceGovernanceTests: XCTestCase {
    func testInMemoryApprovalRevisionAuditAndRevocationStayContentFree() throws {
        let store = RuntimeDocumentIndexStore()
        let privateCanary = "PRIVATE_APPROVAL_BODY_MUST_NOT_ENTER_AUDIT"
        let first = try governedDocument(text: "Approved runtime guide. \(privateCanary)")
        let document = store.replaceDocument(result: first, documentID: "shared-guide")
        let firstApproval = try XCTUnwrap(store.sourceApproval(documentID: document.id))

        XCTAssertEqual(firstApproval.scope, .runtimeShared)
        XCTAssertEqual(firstApproval.approvedBy, "runtime_host")
        XCTAssertEqual(firstApproval.sourceRevision.count, 64)
        XCTAssertEqual(store.documents(limit: 10).map(\.id), ["shared-guide"])

        store.recordSourceAudit(
            action: .queried,
            actorDeviceID: " device-a ",
            documentID: nil,
            sourceAnchorID: nil,
            resultCount: 1
        )
        let encodedAudit = try JSONEncoder().encode(store.sourceAuditEvents(limit: 10))
        let auditText = String(decoding: encodedAudit, as: UTF8.self)
        XCTAssertFalse(auditText.contains(privateCanary))
        XCTAssertFalse(auditText.contains("Approved runtime guide"))
        XCTAssertEqual(store.sourceAuditEvents(limit: 10).first?.actorDeviceID, "device-a")

        let replacement = try governedDocument(text: "Reindexed runtime guide with a new revision.")
        _ = store.replaceDocument(result: replacement, documentID: "shared-guide")
        let secondApproval = try XCTUnwrap(store.sourceApproval(documentID: "shared-guide"))
        XCTAssertNotEqual(secondApproval.sourceRevision, firstApproval.sourceRevision)
        XCTAssertEqual(store.sourceAuditEvents(limit: 10).first?.action, .reindexed)

        let anchor = try XCTUnwrap(store.query("reindexed runtime", limit: 1, maxSnippetCharacters: 80).first?.sourceAnchorID)
        store.deleteDocument(id: "shared-guide")

        XCTAssertNil(store.sourceApproval(documentID: "shared-guide"))
        XCTAssertTrue(store.documents(limit: 10).isEmpty)
        XCTAssertTrue(store.query("runtime", limit: 10, maxSnippetCharacters: 80).isEmpty)
        XCTAssertNil(store.sourceAnchor(id: anchor))
        XCTAssertEqual(store.sourceAuditEvents(limit: 2).map(\.action), [.deleted, .revoked])
    }

    func testSQLiteLegacyRowsRemainUnapprovedUntilExplicitHostReplacement() throws {
        let databaseURL = temporaryDatabaseURL()
        try seedLegacyUnapprovedDocument(databaseURL: databaseURL)

        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertNil(try store.document(id: "legacy-doc"))
        XCTAssertTrue(try store.documents(limit: 10).isEmpty)
        XCTAssertTrue(try store.chunks(for: "legacy-doc", limit: 10).isEmpty)
        XCTAssertTrue(try store.query("legacy private", limit: 10, maxSnippetCharacters: 80).isEmpty)
        XCTAssertNil(try store.sourceApproval(documentID: "legacy-doc"))

        let approved = try governedDocument(text: "Explicitly approved replacement content.")
        try store.replaceDocument(result: approved, documentID: "legacy-doc")
        let approval = try XCTUnwrap(store.sourceApproval(documentID: "legacy-doc"))
        XCTAssertEqual(approval.scope, .runtimeShared)
        XCTAssertEqual(try store.documents(limit: 10).map(\.id), ["legacy-doc"])

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.sourceApproval(documentID: "legacy-doc"), approval)
        XCTAssertEqual(try reopened.sourceAuditEvents(limit: 10).map(\.action), [.indexed, .approved])

        try reopened.deleteDocument(id: "legacy-doc")
        XCTAssertTrue(try reopened.documents(limit: 10).isEmpty)
        XCTAssertNil(try reopened.sourceApproval(documentID: "legacy-doc"))
        XCTAssertEqual(try reopened.sourceAuditEvents(limit: 2).map(\.action), [.deleted, .revoked])
    }

    func testSQLiteApprovedQueryAndAuditLinearizeBeforeConcurrentRevocation() async throws {
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: temporaryDatabaseURL())
        try store.replaceDocument(
            result: governedDocument(text: "Atomic approved retrieval must commit its audit before revocation."),
            documentID: "atomic-shared"
        )

        let readReachedAuditBoundary = DispatchSemaphore(value: 0)
        let allowReadAuditCommit = DispatchSemaphore(value: 0)
        let revokeStarted = DispatchSemaphore(value: 0)
        let revokeFinished = DispatchSemaphore(value: 0)
        store.onBeforeApprovedReadAuditCommit = {
            readReachedAuditBoundary.signal()
            _ = allowReadAuditCommit.wait(timeout: .now() + 2)
        }

        let readTask = Task.detached {
            try store.queryApprovedDocuments(
                "atomic approved retrieval",
                limit: 1,
                maxSnippetCharacters: 80,
                actorDeviceID: "reader-device",
                timestamp: Date()
            )
        }
        XCTAssertEqual(readReachedAuditBoundary.wait(timeout: .now() + 2), .success)

        let revokeTask = Task.detached {
            revokeStarted.signal()
            try store.deleteDocument(id: "atomic-shared")
            revokeFinished.signal()
        }
        XCTAssertEqual(revokeStarted.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(revokeFinished.wait(timeout: .now() + 0.05), .timedOut)

        allowReadAuditCommit.signal()
        let results = try await readTask.value
        try await revokeTask.value
        store.onBeforeApprovedReadAuditCommit = nil

        XCTAssertEqual(results.map(\.document.id), ["atomic-shared"])
        XCTAssertEqual(
            try store.sourceAuditEvents(limit: 3).map(\.action),
            [.deleted, .revoked, .queried]
        )
        XCTAssertTrue(
            try store.queryApprovedDocuments(
                "atomic approved retrieval",
                limit: 1,
                maxSnippetCharacters: 80,
                actorDeviceID: "reader-device",
                timestamp: Date()
            ).isEmpty
        )
    }

    func testAcceptedZeroResultApprovedQueriesStillWriteAudit() throws {
        let memoryStore = RuntimeDocumentIndexStore()
        XCTAssertTrue(
            memoryStore.queryApprovedDocuments(
                "!!!",
                limit: 0,
                maxSnippetCharacters: 80,
                actorDeviceID: "memory-reader",
                timestamp: Date()
            ).isEmpty
        )
        XCTAssertEqual(memoryStore.sourceAuditEvents(limit: 1).first?.action, .queried)
        XCTAssertEqual(memoryStore.sourceAuditEvents(limit: 1).first?.resultCount, 0)
        XCTAssertEqual(memoryStore.sourceAuditEvents(limit: 1).first?.actorDeviceID, "memory-reader")

        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: temporaryDatabaseURL())
        XCTAssertTrue(
            try sqliteStore.queryApprovedDocuments(
                "!!!",
                limit: 0,
                maxSnippetCharacters: 80,
                actorDeviceID: "sqlite-reader",
                timestamp: Date()
            ).isEmpty
        )
        let sqliteAudit = try XCTUnwrap(sqliteStore.sourceAuditEvents(limit: 1).first)
        XCTAssertEqual(sqliteAudit.action, .queried)
        XCTAssertEqual(sqliteAudit.resultCount, 0)
        XCTAssertEqual(sqliteAudit.actorDeviceID, "sqlite-reader")
    }

    func testSourceAuditRetentionKeepsOnlyNewestConfiguredEventsAcrossSQLiteReopen() throws {
        let memoryStore = RuntimeDocumentIndexStore(sourceAuditEventLimit: 3)
        for resultCount in 0..<5 {
            memoryStore.recordSourceAudit(
                action: .queried,
                actorDeviceID: "memory-reader",
                documentID: nil,
                sourceAnchorID: nil,
                resultCount: resultCount
            )
        }
        XCTAssertEqual(memoryStore.sourceAuditEvents(limit: 10).map(\.resultCount), [4, 3, 2])

        let databaseURL = temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(
            databaseURL: databaseURL,
            sourceAuditEventLimit: 3
        )
        let timestamps: [TimeInterval] = [10, 10, 1, 20, 0]
        for resultCount in 0..<5 {
            try sqliteStore.recordSourceAudit(
                action: .queried,
                actorDeviceID: "sqlite-reader",
                documentID: nil,
                sourceAnchorID: nil,
                resultCount: resultCount,
                timestamp: Date(timeIntervalSince1970: timestamps[resultCount])
            )
        }
        XCTAssertEqual(try sqliteStore.sourceAuditEvents(limit: 10).map(\.resultCount), [4, 3, 2])

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.sourceAuditEvents(limit: 10).map(\.resultCount), [4, 3, 2])
    }

    private func governedDocument(text: String) throws -> DocumentIngestionResult {
        try DocumentIngestor(chunker: DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 120,
            overlapCharacters: 8,
            minChunkCharacters: 24
        ))).ingest(extractedDocument: ExtractedDocument(
            fileName: "shared-guide.md",
            mimeType: "text/markdown",
            text: text
        ))
    }

    private func temporaryDatabaseURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("runtime-document-index.sqlite")
    }

    private func seedLegacyUnapprovedDocument(databaseURL: URL) throws {
        try FileManager.default.createDirectory(
            at: databaseURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        var database: OpaquePointer?
        XCTAssertEqual(sqlite3_open(databaseURL.path, &database), SQLITE_OK)
        let opened = try XCTUnwrap(database)
        defer { sqlite3_close(opened) }
        let statements = [
            """
            CREATE TABLE runtime_document_index_documents(
                document_id TEXT PRIMARY KEY NOT NULL,
                display_name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                content_fingerprint TEXT NOT NULL,
                extracted_character_count INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL,
                quality TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE runtime_document_index_chunks(
                chunk_id TEXT PRIMARY KEY NOT NULL,
                document_id TEXT NOT NULL,
                document_display_name TEXT NOT NULL,
                document_mime_type TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_character_offset INTEGER NOT NULL,
                end_character_offset INTEGER NOT NULL,
                text TEXT NOT NULL
            )
            """,
            """
            CREATE VIRTUAL TABLE runtime_document_index_chunk_fts USING fts5(
                chunk_id UNINDEXED, document_id UNINDEXED, text
            )
            """,
            "INSERT INTO runtime_document_index_documents VALUES('legacy-doc','legacy.md','text/markdown','0123456789abcdef',26,1,'single_chunk')",
            "INSERT INTO runtime_document_index_chunks VALUES('legacy-chunk','legacy-doc','legacy.md','text/markdown',0,0,26,'legacy private document')",
            "INSERT INTO runtime_document_index_chunk_fts VALUES('legacy-chunk','legacy-doc','legacy private document')"
        ]
        for statement in statements {
            var error: UnsafeMutablePointer<CChar>?
            let result = sqlite3_exec(opened, statement, nil, nil, &error)
            let message = error.map { String(cString: $0) }
            sqlite3_free(error)
            XCTAssertEqual(result, SQLITE_OK, message ?? statement)
        }
    }
}
