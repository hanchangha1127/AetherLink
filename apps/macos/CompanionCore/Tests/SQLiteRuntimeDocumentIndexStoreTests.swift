@testable import CompanionCore
@testable import DocumentIngestion
import SQLite3
import XCTest

final class SQLiteRuntimeDocumentIndexStoreTests: XCTestCase {
    func testSQLiteStorePersistsDocumentAndChunksAcrossReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let result = try ingestedDocument(
            fileName: "runtime-guide.md",
            text: [
                "Runtime indexing should survive process restarts.",
                "Chunk records keep offsets and display labels."
            ].joined(separator: " ")
        )

        let inserted = try store.replaceDocument(result: result, documentID: "runtime-guide")
        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let document = try XCTUnwrap(reopened.document(id: "runtime-guide"))
        let chunks = try reopened.chunks(for: "runtime-guide")

        XCTAssertEqual(document, inserted)
        XCTAssertEqual(chunks.count, result.chunks.count)
        XCTAssertEqual(chunks.map(\.documentID), Array(repeating: "runtime-guide", count: chunks.count))
        XCTAssertEqual(chunks.map(\.documentDisplayName), Array(repeating: "runtime-guide.md", count: chunks.count))
        XCTAssertEqual(chunks.map(\.documentMimeType), Array(repeating: "text/markdown", count: chunks.count))
        XCTAssertTrue(try posixPermissions(at: databaseURL) == 0o600)
    }

    func testSQLiteStoreQueryMatchesRuntimeIndexStoreAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let primary = try ingestedDocument(
            fileName: "retrieval.md",
            text: [
                "Runtime retrieval planning starts with lexical retrieval over approved chunks.",
                "Retrieval snippets stay bounded before semantic indexes are introduced."
            ].joined(separator: " ")
        )
        let secondary = try ingestedDocument(
            fileName: "memory.md",
            text: "Runtime memory search is adjacent but has fewer retrieval matches."
        )

        _ = memoryStore.replaceDocument(result: secondary, documentID: "memory")
        _ = memoryStore.replaceDocument(result: primary, documentID: "retrieval")
        try sqliteStore.replaceDocument(result: secondary, documentID: "memory")
        try sqliteStore.replaceDocument(result: primary, documentID: "retrieval")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let sqliteResults = try reopened.query("retrieval runtime", limit: 3, maxSnippetCharacters: 64)
        let memoryResults = memoryStore.query("retrieval runtime", limit: 3, maxSnippetCharacters: 64)

        XCTAssertEqual(sqliteResults, memoryResults)
        XCTAssertEqual(sqliteResults.first?.document.id, "retrieval")
        XCTAssertTrue(sqliteResults.allSatisfy { !$0.snippet.isEmpty })
        XCTAssertTrue(sqliteResults.allSatisfy { $0.snippet.count <= 64 })
        XCTAssertTrue(sqliteResults.first?.matchedTerms.contains("retrieval") == true)
        XCTAssertTrue(sqliteResults.first?.matchedTerms.contains("runtime") == true)
    }

    func testSQLiteStoreUsesFtsCandidateIndexWithoutChangingQueryResults() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let pairing = try ingestedDocument(
            fileName: "pairing-guide.md",
            text: [
                "Runtime pairing relay repair starts with fresh route material.",
                "Pairing diagnostics should keep stale relay rows out of search."
            ].joined(separator: " ")
        )
        let model = try ingestedDocument(
            fileName: "model-guide.md",
            text: "Runtime model residency notes are useful but do not mention QR repair."
        )

        _ = memoryStore.replaceDocument(result: pairing, documentID: "pairing")
        _ = memoryStore.replaceDocument(result: model, documentID: "model")
        try sqliteStore.replaceDocument(result: pairing, documentID: "pairing")
        try sqliteStore.replaceDocument(result: model, documentID: "model")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let sqliteResults = try reopened.query("runtime pairing", limit: 10, maxSnippetCharacters: 72)
        let memoryResults = memoryStore.query("runtime pairing", limit: 10, maxSnippetCharacters: 72)
        let ftsCandidateIDs = try ftsChunkIDs(in: databaseURL, matching: "\"runtime\" OR \"pairing\"")

        XCTAssertEqual(sqliteResults, memoryResults)
        XCTAssertFalse(ftsCandidateIDs.isEmpty)
        XCTAssertEqual(Set(ftsCandidateIDs), Set(sqliteResults.map(\.chunk.id)))
        XCTAssertEqual(sqliteResults.first?.document.id, "pairing")
    }

    func testSQLiteStoreListsDocumentsAsBoundedCatalogAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let alpha = try ingestedDocument(fileName: "alpha.md", text: "Alpha catalog content should stay out of document listings.")
        let gamma = try ingestedDocument(fileName: "gamma.md", text: "Gamma catalog content should stay out of document listings.")
        let zeta = try ingestedDocument(fileName: "zeta.md", text: "Zeta catalog content will be replaced.")
        let beta = try ingestedDocument(fileName: "beta.md", text: "Beta catalog replacement content stays host-local.")

        _ = memoryStore.replaceDocument(result: gamma, documentID: "gamma")
        _ = memoryStore.replaceDocument(result: alpha, documentID: "alpha")
        _ = memoryStore.replaceDocument(result: zeta, documentID: "beta")
        try sqliteStore.replaceDocument(result: gamma, documentID: "gamma")
        try sqliteStore.replaceDocument(result: alpha, documentID: "alpha")
        try sqliteStore.replaceDocument(result: zeta, documentID: "beta")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.documents(), memoryStore.documents())
        XCTAssertEqual(try reopened.documents(limit: 2), memoryStore.documents(limit: 2))
        XCTAssertEqual(try reopened.documents(limit: 0), [])

        _ = memoryStore.replaceDocument(result: beta, documentID: "beta")
        memoryStore.deleteDocument(id: "alpha")
        try reopened.replaceDocument(result: beta, documentID: "beta")
        try reopened.deleteDocument(id: "alpha")

        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let catalog = try rereopened.documents()
        XCTAssertEqual(catalog, memoryStore.documents())
        XCTAssertEqual(catalog.map(\.id), ["beta", "gamma"])
        XCTAssertEqual(catalog.first?.displayName, "beta.md")
        XCTAssertFalse(String(describing: catalog).contains("Beta catalog replacement content"))
        XCTAssertFalse(String(describing: catalog).contains("Gamma catalog content"))
    }

    func testSQLiteStoreSummarizesDocumentIndexAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let chunked = try ingestedDocument(
            fileName: "chunked.md",
            text: [
                "Chunked index content should contribute only counts.",
                "Additional sentence text forces the chunking policy to split safely.",
                "The summary must never expose document body text."
            ].joined(separator: " ")
        )
        let single = try ingestedDocument(fileName: "single.md", text: "Single chunk summary content stays private.")
        let empty = try ingestedDocument(fileName: "empty.md", text: "   ")

        _ = memoryStore.replaceDocument(result: chunked, documentID: "chunked")
        _ = memoryStore.replaceDocument(result: single, documentID: "single")
        _ = memoryStore.replaceDocument(result: empty, documentID: "empty")
        try sqliteStore.replaceDocument(result: chunked, documentID: "chunked")
        try sqliteStore.replaceDocument(result: single, documentID: "single")
        try sqliteStore.replaceDocument(result: empty, documentID: "empty")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let summary = try reopened.summary()
        XCTAssertEqual(summary, memoryStore.summary())
        XCTAssertEqual(summary.documentCount, 3)
        XCTAssertEqual(summary.qualityCounts[.chunked], 1)
        XCTAssertEqual(summary.qualityCounts[.singleChunk], 1)
        XCTAssertEqual(summary.qualityCounts[.noUsableText], 1)
        XCTAssertFalse(String(describing: summary).contains("summary content"))
        XCTAssertFalse(String(describing: summary).contains("source_path"))
        XCTAssertFalse(String(describing: summary).contains("workspace_id"))
        XCTAssertFalse(String(describing: summary).contains("retrieval_context"))
        XCTAssertFalse(String(describing: summary).contains("embedding"))

        _ = memoryStore.replaceDocument(result: single, documentID: "chunked")
        memoryStore.deleteDocument(id: "empty")
        try reopened.replaceDocument(result: single, documentID: "chunked")
        try reopened.deleteDocument(id: "empty")

        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try rereopened.summary(), memoryStore.summary())
        XCTAssertEqual(try rereopened.summary().documentCount, 2)
        XCTAssertEqual(try rereopened.summary().qualityCounts[.singleChunk], 2)
    }

    func testSQLiteStoreFindsDocumentsByContentFingerprintAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let duplicateText = "Duplicate approved document text should stay out of SQLite fingerprint lookup rows."
        let copyB = try ingestedDocument(fileName: "copy-b.md", text: duplicateText)
        let copyA = try ingestedDocument(fileName: "copy-a.md", text: duplicateText)
        let unrelated = try ingestedDocument(
            fileName: "unrelated.md",
            text: "Unrelated SQLite document text must not share the same content fingerprint."
        )
        let replacement = try ingestedDocument(
            fileName: "copy-a.md",
            text: "Replacement SQLite text should move copy-a to a new content fingerprint."
        )
        let duplicateFingerprint = RuntimeDocumentIndexStore.stableContentFingerprint(for: copyB)
        let replacementFingerprint = RuntimeDocumentIndexStore.stableContentFingerprint(for: replacement)

        XCTAssertEqual(duplicateFingerprint, RuntimeDocumentIndexStore.stableContentFingerprint(for: copyA))
        XCTAssertNotEqual(duplicateFingerprint, RuntimeDocumentIndexStore.stableContentFingerprint(for: unrelated))

        _ = memoryStore.replaceDocument(result: copyB, documentID: "copy-b")
        _ = memoryStore.replaceDocument(result: unrelated, documentID: "unrelated")
        _ = memoryStore.replaceDocument(result: copyA, documentID: "copy-a")
        try sqliteStore.replaceDocument(result: copyB, documentID: "copy-b")
        try sqliteStore.replaceDocument(result: unrelated, documentID: "unrelated")
        try sqliteStore.replaceDocument(result: copyA, documentID: "copy-a")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let matches = try reopened.documents(matchingContentFingerprint: duplicateFingerprint)
        XCTAssertEqual(matches, memoryStore.documents(matchingContentFingerprint: duplicateFingerprint))
        XCTAssertEqual(matches.map(\.id), ["copy-a", "copy-b"])
        XCTAssertEqual(
            try reopened.documents(matchingContentFingerprint: duplicateFingerprint, limit: 1).map(\.id),
            ["copy-a"]
        )
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: "missing"), [])
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: ""), [])
        XCTAssertFalse(String(describing: matches).contains(duplicateText))
        XCTAssertFalse(String(describing: matches).contains("source_path"))
        XCTAssertFalse(String(describing: matches).contains("workspace_id"))
        XCTAssertFalse(String(describing: matches).contains("retrieval_context"))
        XCTAssertFalse(String(describing: matches).contains("embedding"))

        _ = memoryStore.replaceDocument(result: replacement, documentID: "copy-a")
        memoryStore.deleteDocument(id: "copy-b")
        try reopened.replaceDocument(result: replacement, documentID: "copy-a")
        try reopened.deleteDocument(id: "copy-b")

        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try rereopened.documents(matchingContentFingerprint: duplicateFingerprint),
            memoryStore.documents(matchingContentFingerprint: duplicateFingerprint)
        )
        XCTAssertEqual(try rereopened.documents(matchingContentFingerprint: duplicateFingerprint), [])
        XCTAssertEqual(
            try rereopened.documents(matchingContentFingerprint: replacementFingerprint),
            memoryStore.documents(matchingContentFingerprint: replacementFingerprint)
        )
        XCTAssertEqual(try rereopened.documents(matchingContentFingerprint: replacementFingerprint).map(\.id), ["copy-a"])
    }

    func testSQLiteStoreListsDocumentsByQualityAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let bodySentinel = "PRIVATE_SQLITE_QUALITY_BODY_SHOULD_NOT_APPEAR"
        let chunked = try ingestedDocument(
            fileName: "chunked.md",
            text: [
                "\(bodySentinel) starts a quality-filtered SQLite catalog review.",
                "Additional sentence text forces the chunking policy to split safely.",
                "The quality catalog should identify rows without exposing body text."
            ].joined(separator: " ")
        )
        let single = try ingestedDocument(fileName: "single.md", text: "Single chunk SQLite quality content remains private.")
        let empty = try ingestedDocument(fileName: "empty.md", text: "   ")

        _ = memoryStore.replaceDocument(result: single, documentID: "single")
        _ = memoryStore.replaceDocument(result: chunked, documentID: "chunked")
        _ = memoryStore.replaceDocument(result: empty, documentID: "empty")
        try sqliteStore.replaceDocument(result: single, documentID: "single")
        try sqliteStore.replaceDocument(result: chunked, documentID: "chunked")
        try sqliteStore.replaceDocument(result: empty, documentID: "empty")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let chunkedCatalog = try reopened.documents(matchingQuality: .chunked)
        XCTAssertEqual(chunkedCatalog, memoryStore.documents(matchingQuality: .chunked))
        XCTAssertEqual(chunkedCatalog.map(\.id), ["chunked"])
        XCTAssertEqual(try reopened.documents(matchingQuality: .singleChunk), memoryStore.documents(matchingQuality: .singleChunk))
        XCTAssertEqual(try reopened.documents(matchingQuality: .noUsableText), memoryStore.documents(matchingQuality: .noUsableText))
        XCTAssertEqual(try reopened.documents(matchingQuality: .singleChunk, limit: 0), [])
        XCTAssertFalse(String(describing: chunkedCatalog).contains(bodySentinel))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("source_path"))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("workspace_id"))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("retrieval_context"))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("embedding"))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("citation"))

        _ = memoryStore.replaceDocument(result: single, documentID: "chunked")
        memoryStore.deleteDocument(id: "empty")
        try reopened.replaceDocument(result: single, documentID: "chunked")
        try reopened.deleteDocument(id: "empty")

        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try rereopened.documents(matchingQuality: .chunked), [])
        XCTAssertEqual(try rereopened.documents(matchingQuality: .singleChunk), memoryStore.documents(matchingQuality: .singleChunk))
        XCTAssertEqual(try rereopened.documents(matchingQuality: .noUsableText), [])
    }

    func testSQLiteStoreReplacingDocumentRemovesOldChunksAndQueryRows() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let first = try ingestedDocument(fileName: "notes.txt", mimeType: "text/plain", text: "obsolete alpha content")
        let replacement = try ingestedDocument(fileName: "notes.txt", mimeType: "text/plain", text: "fresh beta content")

        try store.replaceDocument(result: first, documentID: "notes")
        XCTAssertEqual(try store.query("obsolete").count, 1)

        let record = try store.replaceDocument(result: replacement, documentID: "notes")

        XCTAssertEqual(record.id, "notes")
        XCTAssertEqual(try store.query("obsolete"), [])
        XCTAssertEqual(try store.query("fresh").single?.document.id, "notes")
        XCTAssertEqual(try ftsChunkIDs(in: databaseURL, matching: "\"obsolete\""), [])
        XCTAssertEqual(try ftsChunkIDs(in: databaseURL, matching: "\"fresh\"").count, 1)
        XCTAssertEqual(try store.chunks(for: "notes").map(\.text).joined(separator: " "), "fresh beta content")
    }

    func testSQLiteStoreDeleteRemovesDocumentChunksAndQueryRows() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let result = try ingestedDocument(fileName: "delete-me.txt", mimeType: "text/plain", text: "temporary indexed content")
        try store.replaceDocument(result: result, documentID: "temporary")

        XCTAssertEqual(try store.query("temporary").count, 1)

        try store.deleteDocument(id: "temporary")

        XCTAssertNil(try store.document(id: "temporary"))
        XCTAssertEqual(try store.chunks(for: "temporary"), [])
        XCTAssertEqual(try store.query("temporary"), [])
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "temporary"), 0)
    }

    func testSQLiteStoreSchemaDoesNotPersistPathProjectRetrievalEmbeddingOrCitationColumns() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: try ingestedDocument(fileName: "safe.txt", mimeType: "text/plain", text: "safe structural index row"),
            documentID: "safe"
        )

        let columns = try tableColumns(
            in: databaseURL,
            tables: [
                "runtime_document_index_documents",
                "runtime_document_index_chunks",
                "runtime_document_index_chunk_fts"
            ]
        )
        let forbidden = Set([
            "source_path",
            "workspace_id",
            "project_id",
            "retrieval_context",
            "embedding",
            "embedding_model_id",
            "citation",
            "backend_url"
        ])

        XCTAssertTrue(columns.isDisjoint(with: forbidden), "\(columns.sorted())")
        XCTAssertTrue(columns.isSuperset(of: ["chunk_id", "document_id", "text"]))
    }

    func testSQLiteStoreRejectsCorruptQualityValues() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try store.query("bootstrap"), [])
        try insertRawDocument(databaseURL: databaseURL, quality: "unexpected_quality")

        XCTAssertThrowsError(try store.document(id: "corrupt")) { error in
            XCTAssertTrue(String(describing: error).contains("quality"))
        }
    }

    private func ingestedDocument(
        fileName: String,
        mimeType: String = "text/markdown",
        text: String
    ) throws -> DocumentIngestionResult {
        try DocumentIngestor(chunker: DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 82,
            overlapCharacters: 8,
            minChunkCharacters: 28
        ))).ingest(extractedDocument: ExtractedDocument(fileName: fileName, mimeType: mimeType, text: text))
    }

    private func temporaryDatabaseURL() throws -> URL {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        return directoryURL.appendingPathComponent("runtime-document-index.sqlite")
    }

    private func tableColumns(in databaseURL: URL, tables: [String]) throws -> Set<String> {
        let database = try openRawDatabase(databaseURL)
        defer { sqlite3_close(database) }

        var columns = Set<String>()
        for table in tables {
            let statement = try prepareRaw(database, "PRAGMA table_info(\(table))")
            defer { sqlite3_finalize(statement) }
            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }
                guard result == SQLITE_ROW else {
                    throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 3)
                }
                let name = try XCTUnwrap(sqlite3_column_text(statement, 1))
                columns.insert(String(cString: name))
            }
        }
        return columns
    }

    private func ftsChunkIDs(in databaseURL: URL, matching matchQuery: String) throws -> [String] {
        let database = try openRawDatabase(databaseURL)
        defer { sqlite3_close(database) }
        let statement = try prepareRaw(
            database,
            """
            SELECT chunk_id
            FROM runtime_document_index_chunk_fts
            WHERE runtime_document_index_chunk_fts MATCH ?
            ORDER BY rowid ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        sqlite3_bind_text(statement, 1, matchQuery, -1, sqliteDocumentIndexTestTransient)

        var chunkIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 5)
            }
            let rawChunkID = try XCTUnwrap(sqlite3_column_text(statement, 0))
            chunkIDs.append(String(cString: rawChunkID))
        }
        return chunkIDs
    }

    private func ftsRowCount(in databaseURL: URL, documentID: String) throws -> Int {
        let database = try openRawDatabase(databaseURL)
        defer { sqlite3_close(database) }
        let statement = try prepareRaw(
            database,
            "SELECT COUNT(*) FROM runtime_document_index_chunk_fts WHERE document_id = ?"
        )
        defer { sqlite3_finalize(statement) }
        sqlite3_bind_text(statement, 1, documentID, -1, sqliteDocumentIndexTestTransient)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 6)
        }
        return Int(sqlite3_column_int64(statement, 0))
    }

    private func insertRawDocument(databaseURL: URL, quality: String) throws {
        let database = try openRawDatabase(databaseURL)
        defer { sqlite3_close(database) }
        let statement = try prepareRaw(
            database,
            """
            INSERT INTO runtime_document_index_documents(
                document_id,
                display_name,
                mime_type,
                content_fingerprint,
                extracted_character_count,
                chunk_count,
                quality
            ) VALUES ('corrupt', 'corrupt.txt', 'text/plain', 'fingerprint', 1, 0, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        sqlite3_bind_text(statement, 1, quality, -1, sqliteDocumentIndexTestTransient)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 4)
        }
    }

    private func openRawDatabase(_ databaseURL: URL) throws -> OpaquePointer {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READWRITE, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 1)
        }
        return database
    }

    private func prepareRaw(_ database: OpaquePointer, _ sql: String) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 2)
        }
        return statement
    }

    private func posixPermissions(at url: URL) throws -> Int {
        let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
        let permissions = try XCTUnwrap(attributes[.posixPermissions] as? NSNumber)
        return permissions.intValue & 0o777
    }
}

private extension Array {
    var single: Element? {
        count == 1 ? self[0] : nil
    }
}

private let sqliteDocumentIndexTestTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
