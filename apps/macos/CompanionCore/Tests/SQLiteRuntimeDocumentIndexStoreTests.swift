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

    func testSQLiteRequestedDocumentIDsUseStoreOwnedCanonicalityGuardsAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let blankResult = try ingestedDocument(
            fileName: "blank-id.md",
            text: "Blank requested SQLite document ids must not become runtime index rows."
        )
        let customResult = try ingestedDocument(
            fileName: "custom-id.md",
            text: "Whitespace-mutated SQLite document ids are normalized before storage."
        )
        let oversizedResult = try ingestedDocument(
            fileName: "oversized-id.md",
            text: "Oversized requested SQLite document ids must fall back to deterministic stable ids."
        )

        let blankMemory = memoryStore.replaceDocument(result: blankResult, documentID: " \n\t ")
        let customMemory = memoryStore.replaceDocument(result: customResult, documentID: "  custom-doc  \n")
        let oversizedRequestedID = String(repeating: "x", count: runtimeDocumentIndexDocumentIDCharacterLimitCeiling + 1)
        let oversizedMemory = memoryStore.replaceDocument(result: oversizedResult, documentID: oversizedRequestedID)
        let blankSQLite = try sqliteStore.replaceDocument(result: blankResult, documentID: " \n\t ")
        let customSQLite = try sqliteStore.replaceDocument(result: customResult, documentID: "  custom-doc  \n")
        let oversizedSQLite = try sqliteStore.replaceDocument(result: oversizedResult, documentID: oversizedRequestedID)

        XCTAssertEqual(blankSQLite, blankMemory)
        XCTAssertEqual(customSQLite, customMemory)
        XCTAssertEqual(oversizedSQLite, oversizedMemory)
        XCTAssertEqual(blankSQLite.id, RuntimeDocumentIndexStore.stableDocumentID(for: blankResult))
        XCTAssertEqual(customSQLite.id, "custom-doc")
        XCTAssertEqual(oversizedSQLite.id, RuntimeDocumentIndexStore.stableDocumentID(for: oversizedResult))

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.document(id: " custom-doc "), customMemory)
        XCTAssertEqual(Set(try reopened.chunks(for: " custom-doc ").map(\.documentID)), Set(["custom-doc"]))
        XCTAssertEqual(Set(try reopened.chunkSummaries(for: " custom-doc ").map(\.documentID)), Set(["custom-doc"]))
        XCTAssertNil(try reopened.document(id: ""))
        XCTAssertNil(try reopened.document(id: " \n\t "))
        XCTAssertNil(try reopened.document(id: oversizedRequestedID))
        XCTAssertEqual(try reopened.chunks(for: ""), [])
        XCTAssertEqual(try reopened.chunkSummaries(for: " \n\t "), [])

        let storedDocumentIDs = try rawDocumentIDs(in: databaseURL, table: "runtime_document_index_documents")
        let storedChunkDocumentIDs = try rawDocumentIDs(in: databaseURL, table: "runtime_document_index_chunks")
        let storedFtsDocumentIDs = try rawDocumentIDs(in: databaseURL, table: "runtime_document_index_chunk_fts")
        XCTAssertEqual(Set(storedDocumentIDs), Set(memoryStore.documents().map(\.id)))
        XCTAssertFalse(storedDocumentIDs.contains(""))
        XCTAssertFalse(storedDocumentIDs.contains("  custom-doc  \n"))
        XCTAssertFalse(storedDocumentIDs.contains(oversizedRequestedID))
        XCTAssertFalse(storedChunkDocumentIDs.contains(""))
        XCTAssertFalse(storedChunkDocumentIDs.contains("  custom-doc  \n"))
        XCTAssertFalse(storedChunkDocumentIDs.contains(oversizedRequestedID))
        XCTAssertFalse(storedFtsDocumentIDs.contains(""))
        XCTAssertFalse(storedFtsDocumentIDs.contains("  custom-doc  \n"))
        XCTAssertFalse(storedFtsDocumentIDs.contains(oversizedRequestedID))

        try reopened.deleteDocument(id: " custom-doc ")
        memoryStore.deleteDocument(id: " custom-doc ")

        let afterDelete = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try afterDelete.documents(), memoryStore.documents())
        XCTAssertNil(try afterDelete.document(id: "custom-doc"))
        XCTAssertEqual(try afterDelete.chunks(for: "custom-doc"), [])
        XCTAssertEqual(try afterDelete.query("Whitespace-mutated"), [])
        XCTAssertEqual(try afterDelete.query("Blank requested"), memoryStore.query("Blank requested"))
        XCTAssertEqual(try afterDelete.query("Oversized requested"), memoryStore.query("Oversized requested"))
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "custom-doc"), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: blankSQLite.id), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: oversizedSQLite.id), 0)
    }

    func testSQLiteRejectsControlCharacterRequestedDocumentIDsAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let controlRequestedID = "control\u{0000}doc"
        let controlResult = try ingestedDocument(
            fileName: "control-id.md",
            text: "SQLite control-character requested document ids must not persist in document, chunk, or FTS rows."
        )

        let memoryRecord = memoryStore.replaceDocument(result: controlResult, documentID: controlRequestedID)
        let sqliteRecord = try sqliteStore.replaceDocument(result: controlResult, documentID: controlRequestedID)
        XCTAssertEqual(sqliteRecord, memoryRecord)
        XCTAssertEqual(sqliteRecord.id, RuntimeDocumentIndexStore.stableDocumentID(for: controlResult))

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.document(id: sqliteRecord.id), memoryRecord)
        XCTAssertNil(try reopened.document(id: controlRequestedID))
        XCTAssertEqual(try reopened.chunks(for: controlRequestedID), [])
        XCTAssertEqual(try reopened.chunkSummaries(for: controlRequestedID), [])
        XCTAssertEqual(Set(try reopened.chunks(for: sqliteRecord.id).map(\.documentID)), [sqliteRecord.id])
        XCTAssertEqual(Set(try reopened.chunkSummaries(for: sqliteRecord.id).map(\.documentID)), [sqliteRecord.id])
        XCTAssertEqual(try reopened.query("Control-character"), memoryStore.query("Control-character"))

        let storedDocumentIDs = try rawDocumentIDs(in: databaseURL, table: "runtime_document_index_documents")
        let storedChunkDocumentIDs = try rawDocumentIDs(in: databaseURL, table: "runtime_document_index_chunks")
        let storedFtsDocumentIDs = try rawDocumentIDs(in: databaseURL, table: "runtime_document_index_chunk_fts")
        XCTAssertEqual(storedDocumentIDs, [sqliteRecord.id])
        XCTAssertEqual(Set(storedChunkDocumentIDs), [sqliteRecord.id])
        XCTAssertEqual(Set(storedFtsDocumentIDs), [sqliteRecord.id])
        XCTAssertFalse(storedDocumentIDs.contains(controlRequestedID))
        XCTAssertFalse(storedChunkDocumentIDs.contains(controlRequestedID))
        XCTAssertFalse(storedFtsDocumentIDs.contains(controlRequestedID))
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: sqliteRecord.id), 0)
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: controlRequestedID), 0)

        try reopened.deleteDocument(id: controlRequestedID)
        XCTAssertEqual(try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).document(id: sqliteRecord.id), memoryRecord)
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

    func testSQLiteStoreMaintainsFtsCandidateRowsWithoutChangingQueryResults() throws {
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

    func testSQLiteQueryPreservesSubstringParityWhenFtsMissesSubstringCandidate() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let pairing = try ingestedDocument(
            fileName: "pairing.md",
            text: "Pairing token candidate appears without the substring-only clock term."
        )
        let runtime = try ingestedDocument(
            fileName: "runtime.md",
            text: "Runtime substring matching remains part of the lexical document index contract."
        )

        _ = memoryStore.replaceDocument(result: pairing, documentID: "pairing")
        _ = memoryStore.replaceDocument(result: runtime, documentID: "runtime")
        try sqliteStore.replaceDocument(result: pairing, documentID: "pairing")
        try sqliteStore.replaceDocument(result: runtime, documentID: "runtime")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let pairingChunkID = try XCTUnwrap(memoryStore.chunks(for: "pairing").single?.id)
        XCTAssertEqual(try ftsChunkIDs(in: databaseURL, matching: "\"time\""), [])
        XCTAssertEqual(try ftsChunkIDs(in: databaseURL, matching: "\"pairing\" OR \"time\""), [pairingChunkID])

        let substringOnlyResults = memoryStore.query("time", limit: 5, maxSnippetCharacters: 80)
        XCTAssertEqual(substringOnlyResults.single?.document.id, "runtime")
        XCTAssertEqual(try reopened.query("time", limit: 5, maxSnippetCharacters: 80), substringOnlyResults)

        let mixedResults = memoryStore.query("pairing time", limit: 5, maxSnippetCharacters: 80)
        XCTAssertEqual(try reopened.query("pairing time", limit: 5, maxSnippetCharacters: 80), mixedResults)
        XCTAssertEqual(Set(mixedResults.map(\.document.id)), Set(["pairing", "runtime"]))
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

    func testSQLiteStoreListsDocumentsByDisplayNameAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let bodySentinel = "PRIVATE_SQLITE_DISPLAY_NAME_BODY_SHOULD_NOT_APPEAR"
        let duplicateB = try ingestedDocument(fileName: "shared-name.md", text: "\(bodySentinel) duplicate body remains private.")
        let duplicateA = try ingestedDocument(fileName: "shared-name.md", text: "Second SQLite duplicate body remains private.")
        let unrelated = try ingestedDocument(fileName: "other-name.md", text: "SQLite unrelated body remains private.")
        let replacement = try ingestedDocument(fileName: "renamed.md", text: "SQLite replacement body remains private.")

        _ = memoryStore.replaceDocument(result: duplicateB, documentID: "duplicate-b")
        _ = memoryStore.replaceDocument(result: unrelated, documentID: "unrelated")
        _ = memoryStore.replaceDocument(result: duplicateA, documentID: "duplicate-a")
        try sqliteStore.replaceDocument(result: duplicateB, documentID: "duplicate-b")
        try sqliteStore.replaceDocument(result: unrelated, documentID: "unrelated")
        try sqliteStore.replaceDocument(result: duplicateA, documentID: "duplicate-a")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let matches = try reopened.documents(matchingDisplayName: "shared-name.md")
        XCTAssertEqual(matches, memoryStore.documents(matchingDisplayName: "shared-name.md"))
        XCTAssertEqual(matches.map(\.id), ["duplicate-a", "duplicate-b"])
        XCTAssertEqual(
            try reopened.documents(matchingDisplayName: "shared-name.md", limit: 1).map(\.id),
            ["duplicate-a"]
        )
        XCTAssertEqual(try reopened.documents(matchingDisplayName: "other-name.md"), memoryStore.documents(matchingDisplayName: "other-name.md"))
        XCTAssertEqual(try reopened.documents(matchingDisplayName: "missing.md"), [])
        XCTAssertEqual(try reopened.documents(matchingDisplayName: ""), [])
        XCTAssertEqual(try reopened.documents(matchingDisplayName: "shared-name.md", limit: 0), [])
        XCTAssertFalse(String(describing: matches).contains(bodySentinel))
        XCTAssertFalse(String(describing: matches).contains("source_path"))
        XCTAssertFalse(String(describing: matches).contains("workspace_id"))
        XCTAssertFalse(String(describing: matches).contains("retrieval_context"))
        XCTAssertFalse(String(describing: matches).contains("embedding"))
        XCTAssertFalse(String(describing: matches).contains("citation"))

        _ = memoryStore.replaceDocument(result: replacement, documentID: "duplicate-b")
        memoryStore.deleteDocument(id: "duplicate-a")
        try reopened.replaceDocument(result: replacement, documentID: "duplicate-b")
        try reopened.deleteDocument(id: "duplicate-a")

        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try rereopened.documents(matchingDisplayName: "shared-name.md"), [])
        XCTAssertEqual(try rereopened.documents(matchingDisplayName: "renamed.md"), memoryStore.documents(matchingDisplayName: "renamed.md"))
    }

    func testSQLiteStoreDeleteDocumentsByDisplayNameClearsMatchingRowsAndFtsAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let sharedSentinel = "SQLiteSharedDisplayNameDeleteSentinel"
        let unrelatedSentinel = "SQLiteUnrelatedDisplayNameDeleteSentinel"
        let pdfSentinel = "SQLitePdfDisplayNameDeleteSentinel"
        let duplicateB = try ingestedDocument(
            fileName: "shared-name.md",
            text: "\(sharedSentinel) cleanup duplicate display-name row should be removed."
        )
        let duplicateA = try ingestedDocument(
            fileName: "shared-name.md",
            text: "\(sharedSentinel) cleanup second display-name row should be removed."
        )
        let unrelated = try ingestedDocument(
            fileName: "other-name.md",
            text: "\(unrelatedSentinel) cleanup text remains searchable."
        )
        let pdf = try ingestedDocument(
            fileName: "brief.pdf",
            mimeType: "application/pdf",
            text: "\(pdfSentinel) cleanup text remains indexed."
        )
        let overlongDisplayName = String(repeating: "a", count: runtimeDocumentIndexDisplayNameCharacterLimitCeiling + 1)

        _ = memoryStore.replaceDocument(result: duplicateB, documentID: "duplicate-b")
        _ = memoryStore.replaceDocument(result: unrelated, documentID: "unrelated")
        _ = memoryStore.replaceDocument(result: pdf, documentID: "pdf")
        _ = memoryStore.replaceDocument(result: duplicateA, documentID: "duplicate-a")
        try sqliteStore.replaceDocument(result: duplicateB, documentID: "duplicate-b")
        try sqliteStore.replaceDocument(result: unrelated, documentID: "unrelated")
        try sqliteStore.replaceDocument(result: pdf, documentID: "pdf")
        try sqliteStore.replaceDocument(result: duplicateA, documentID: "duplicate-a")
        XCTAssertGreaterThan(try ftsTotalRowCount(in: databaseURL), 0)

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try reopened.documents(matchingDisplayName: "shared-name.md"),
            memoryStore.documents(matchingDisplayName: "shared-name.md")
        )
        try reopened.deleteDocuments(matchingDisplayName: "")
        try reopened.deleteDocuments(matchingDisplayName: overlongDisplayName)
        try reopened.deleteDocuments(matchingDisplayName: "Shared-name.md")
        XCTAssertEqual(try reopened.documents(), memoryStore.documents())

        memoryStore.deleteDocuments(matchingDisplayName: " /Users/private/shared-name.md\n")
        try reopened.deleteDocuments(matchingDisplayName: " /Users/private/shared-name.md\n")

        let afterDelete = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertNil(try afterDelete.document(id: "duplicate-a"))
        XCTAssertNil(try afterDelete.document(id: "duplicate-b"))
        XCTAssertNotNil(try afterDelete.document(id: "unrelated"))
        XCTAssertNotNil(try afterDelete.document(id: "pdf"))
        XCTAssertEqual(try afterDelete.chunks(for: "duplicate-a"), [])
        XCTAssertEqual(try afterDelete.chunks(for: "duplicate-b"), [])
        XCTAssertFalse(try afterDelete.chunks(for: "unrelated").isEmpty)
        XCTAssertFalse(try afterDelete.chunks(for: "pdf").isEmpty)
        XCTAssertEqual(try afterDelete.chunkSummaries(for: "duplicate-a"), [])
        XCTAssertEqual(try afterDelete.chunkSummaries(for: "duplicate-b"), [])
        XCTAssertFalse(try afterDelete.chunkSummaries(for: "unrelated").isEmpty)
        XCTAssertEqual(try afterDelete.documents(matchingDisplayName: "shared-name.md"), [])
        XCTAssertEqual(try afterDelete.documents(), memoryStore.documents())
        XCTAssertEqual(try afterDelete.documents().map(\.id), ["pdf", "unrelated"])
        XCTAssertEqual(try afterDelete.query(sharedSentinel), [])
        XCTAssertEqual(try afterDelete.query(unrelatedSentinel).single?.document.id, "unrelated")
        XCTAssertEqual(try afterDelete.query(pdfSentinel).single?.document.id, "pdf")
        XCTAssertEqual(try afterDelete.summary(), memoryStore.summary())
        XCTAssertEqual(try afterDelete.summary().documentCount, 2)
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "duplicate-a"), 0)
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "duplicate-b"), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: "unrelated"), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: "pdf"), 0)
        XCTAssertFalse(String(describing: try afterDelete.documents()).contains(sharedSentinel))
        XCTAssertFalse(String(describing: try afterDelete.documents()).contains("source_path"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("project_id"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("workspace_id"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("citation"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("trusted_source"))

        try afterDelete.deleteDocuments(matchingDisplayName: "shared-name.md")
        XCTAssertEqual(try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).documents(), memoryStore.documents())
    }

    func testSQLiteStoreNormalizesDisplayNamesAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        var pathResult = try ingestedDocument(
            fileName: "report.md",
            text: chunkCeilingText(minimumChunks: 2)
        )
        var basenameResult = pathResult
        pathResult.document.fileName = "/Users/private/Documents/report.md"
        pathResult.summary.documentFileName = "/Users/private/Documents/summary-secret.md"
        pathResult.chunks = pathResult.chunks.map { chunk in
            var chunk = chunk
            chunk.documentFileName = "/Users/private/Documents/chunk-secret.md"
            return chunk
        }
        basenameResult.document.fileName = "report.md"
        basenameResult.summary.documentFileName = "report.md"

        XCTAssertEqual(
            RuntimeDocumentIndexStore.stableDocumentID(for: pathResult),
            RuntimeDocumentIndexStore.stableDocumentID(for: basenameResult)
        )

        var fallbackResult = try ingestedDocument(
            fileName: "fallback.md",
            text: "SQLite fallback display names must not preserve blank or oversized source labels."
        )
        fallbackResult.document.fileName = " \n\t "
        fallbackResult.summary.documentFileName = String(
            repeating: "x",
            count: runtimeDocumentIndexDisplayNameCharacterLimitCeiling + 1
        )
        fallbackResult.chunks = fallbackResult.chunks.map { chunk in
            var chunk = chunk
            chunk.documentFileName = "/Users/private/Documents/fallback-chunk.md"
            return chunk
        }

        try sqliteStore.replaceDocument(result: pathResult, documentID: "path-report")
        try sqliteStore.replaceDocument(result: fallbackResult, documentID: "fallback")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let storedPath = try XCTUnwrap(reopened.document(id: "path-report"))
        let storedFallback = try XCTUnwrap(reopened.document(id: "fallback"))

        XCTAssertEqual(storedPath.displayName, "report.md")
        XCTAssertEqual(storedFallback.displayName, runtimeDocumentIndexUnknownDisplayName)
        XCTAssertEqual(
            try reopened.documents(matchingDisplayName: " /Users/private/Documents/report.md\n").map(\.id),
            ["path-report"]
        )
        XCTAssertEqual(try reopened.documents(matchingDisplayName: "C:\\Users\\private\\report.md").map(\.id), ["path-report"])
        XCTAssertEqual(try reopened.documents(matchingDisplayName: "/Users/private/Documents/summary-secret.md"), [])
        XCTAssertEqual(try reopened.documents(matchingDisplayName: "/Users/private/Documents/chunk-secret.md"), [])
        XCTAssertEqual(try reopened.documents(matchingDisplayName: runtimeDocumentIndexUnknownDisplayName).map(\.id), ["fallback"])
        XCTAssertEqual(Set(try reopened.chunks(for: "path-report").map(\.documentDisplayName)), ["report.md"])
        XCTAssertEqual(
            Set(try reopened.chunkSummaries(for: "fallback").map(\.documentDisplayName)),
            [runtimeDocumentIndexUnknownDisplayName]
        )

        let rawDocumentDisplayNames = try rawStringValues(
            in: databaseURL,
            table: "runtime_document_index_documents",
            column: "display_name"
        )
        let rawChunkDisplayNames = try rawStringValues(
            in: databaseURL,
            table: "runtime_document_index_chunks",
            column: "document_display_name"
        )
        XCTAssertEqual(rawDocumentDisplayNames, ["report.md", runtimeDocumentIndexUnknownDisplayName])
        XCTAssertEqual(Set(rawChunkDisplayNames), ["report.md", runtimeDocumentIndexUnknownDisplayName])
        XCTAssertFalse(rawDocumentDisplayNames.joined(separator: " ").contains("/Users/private"))
        XCTAssertFalse(rawChunkDisplayNames.joined(separator: " ").contains("/Users/private"))
        XCTAssertFalse(rawDocumentDisplayNames.joined(separator: " ").contains("summary-secret"))
        XCTAssertFalse(rawChunkDisplayNames.joined(separator: " ").contains("chunk-secret"))
    }

    func testSQLiteStoreRejectsControlCharacterDisplayNamesAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let forgedDisplayName = "runtime\u{0000}secret.md"
        var controlResult = try ingestedDocument(
            fileName: "control.md",
            text: "SQLite control-character display names must not survive durable document index storage."
        )
        controlResult.document.fileName = forgedDisplayName
        controlResult.summary.documentFileName = "summary\u{0000}secret.md"
        controlResult.chunks = controlResult.chunks.map { chunk in
            var chunk = chunk
            chunk.documentFileName = "chunk\u{0000}secret.md"
            return chunk
        }

        try sqliteStore.replaceDocument(result: controlResult, documentID: "control")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let storedControl = try XCTUnwrap(reopened.document(id: "control"))
        XCTAssertEqual(storedControl.displayName, runtimeDocumentIndexUnknownDisplayName)
        XCTAssertEqual(try reopened.documents(matchingDisplayName: forgedDisplayName), [])
        XCTAssertEqual(try reopened.documents(matchingDisplayName: runtimeDocumentIndexUnknownDisplayName).map(\.id), ["control"])
        XCTAssertEqual(Set(try reopened.chunks(for: "control").map(\.documentDisplayName)), [runtimeDocumentIndexUnknownDisplayName])
        XCTAssertEqual(
            Set(try reopened.chunkSummaries(for: "control").map(\.documentDisplayName)),
            [runtimeDocumentIndexUnknownDisplayName]
        )

        let rawDocumentDisplayNames = try rawStringValues(
            in: databaseURL,
            table: "runtime_document_index_documents",
            column: "display_name"
        )
        let rawChunkDisplayNames = try rawStringValues(
            in: databaseURL,
            table: "runtime_document_index_chunks",
            column: "document_display_name"
        )
        XCTAssertEqual(rawDocumentDisplayNames, [runtimeDocumentIndexUnknownDisplayName])
        XCTAssertEqual(Set(rawChunkDisplayNames), [runtimeDocumentIndexUnknownDisplayName])
        XCTAssertFalse(rawDocumentDisplayNames.joined(separator: " ").contains("runtime"))
        XCTAssertFalse(rawChunkDisplayNames.joined(separator: " ").contains("secret"))
    }

    func testSQLiteStoreNormalizesChunkEnvelopeAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let canonical = try ingestedDocument(
            fileName: "chunk-envelope.md",
            text: chunkCeilingText(minimumChunks: 3)
        )
        XCTAssertGreaterThan(canonical.chunks.count, 1)

        var forged = canonical
        forged.chunks = canonical.chunks.enumerated().map { offset, chunk in
            var chunk = chunk
            chunk.index = offset.isMultiple(of: 2) ? 999 : -7
            chunk.startCharacterOffset = offset == 0 ? -50 : chunk.endCharacterOffset + 1_000
            chunk.endCharacterOffset = offset == 0 ? -1 : chunk.startCharacterOffset - 12
            return chunk
        }

        _ = memoryStore.replaceDocument(result: forged, documentID: "chunk-envelope")
        try sqliteStore.replaceDocument(result: forged, documentID: "chunk-envelope")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let chunks = try reopened.chunks(for: "chunk-envelope")
        let summaries = try reopened.chunkSummaries(for: "chunk-envelope")
        let expectedChunks = runtimeDocumentIndexChunks(for: canonical, documentID: "chunk-envelope")

        XCTAssertEqual(chunks, memoryStore.chunks(for: "chunk-envelope"))
        XCTAssertEqual(chunks, expectedChunks)
        XCTAssertEqual(chunks.map(\.chunkIndex), Array(0..<canonical.chunks.count))
        XCTAssertEqual(chunks.map(\.id), expectedChunks.map(\.id))
        XCTAssertEqual(summaries.map(\.chunkIndex), chunks.map(\.chunkIndex))
        XCTAssertEqual(summaries.map(\.startCharacterOffset), chunks.map(\.startCharacterOffset))
        XCTAssertEqual(summaries.map(\.endCharacterOffset), chunks.map(\.endCharacterOffset))

        let rawChunkIndexes = try rawIntValues(
            in: databaseURL,
            table: "runtime_document_index_chunks",
            column: "chunk_index"
        )
        let rawStartOffsets = try rawIntValues(
            in: databaseURL,
            table: "runtime_document_index_chunks",
            column: "start_character_offset"
        )
        let rawEndOffsets = try rawIntValues(
            in: databaseURL,
            table: "runtime_document_index_chunks",
            column: "end_character_offset"
        )
        XCTAssertEqual(rawChunkIndexes, Array(0..<canonical.chunks.count))
        XCTAssertEqual(rawStartOffsets, expectedChunks.map(\.startCharacterOffset).sorted())
        XCTAssertEqual(rawEndOffsets, expectedChunks.map(\.endCharacterOffset).sorted())
        XCTAssertFalse(rawChunkIndexes.contains(999))
        XCTAssertFalse(rawChunkIndexes.contains(-7))
        XCTAssertFalse(rawStartOffsets.contains(-50))
        XCTAssertFalse(rawEndOffsets.contains(-1))

        var fallback = try ingestedDocument(
            fileName: "fallback-envelope.md",
            text: "SQLite fallback chunk envelope offsets stay bounded even for forged direct-ingestion chunks."
        )
        let fallbackText = "SQLITE_FORGED_CHUNK_TEXT_NOT_IN_DOCUMENT"
        let fallbackDocumentCharacterCount = fallback.document.text.trimmingCharacters(in: .whitespacesAndNewlines).count
        fallback.chunks = [
            DocumentChunk(
                documentFileName: fallback.document.fileName,
                documentMimeType: fallback.document.mimeType,
                index: -99,
                startCharacterOffset: -5_000,
                endCharacterOffset: 9_999,
                text: fallbackText
            )
        ]

        try reopened.replaceDocument(result: fallback, documentID: "fallback-envelope")
        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let fallbackChunk = try XCTUnwrap(rereopened.chunks(for: "fallback-envelope").single)
        XCTAssertEqual(fallbackChunk.chunkIndex, 0)
        XCTAssertEqual(fallbackChunk.startCharacterOffset, 0)
        XCTAssertEqual(fallbackChunk.endCharacterOffset, min(fallbackText.count, fallbackDocumentCharacterCount))
        XCTAssertFalse(fallbackChunk.startCharacterOffset < 0)
        XCTAssertLessThanOrEqual(fallbackChunk.endCharacterOffset, fallbackDocumentCharacterCount)
    }

    func testSQLiteStoreSummarizesChunksForDocumentAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let bodySentinel = "PRIVATE_SQLITE_CHUNK_SUMMARY_BODY_SHOULD_NOT_APPEAR"
        let chunked = try ingestedDocument(
            fileName: "chunk-review.md",
            text: [
                "\(bodySentinel) starts the first indexed SQLite chunk for maintenance.",
                "The second sentence forces multiple chunks for bounded summary review.",
                "The third sentence keeps chunk offsets and lengths useful."
            ].joined(separator: " ")
        )
        let replacement = try ingestedDocument(
            fileName: "chunk-review.md",
            text: "SQLite replacement chunk summary body remains private."
        )

        _ = memoryStore.replaceDocument(result: chunked, documentID: "chunk-review")
        try sqliteStore.replaceDocument(result: chunked, documentID: "chunk-review")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let chunks = memoryStore.chunks(for: "chunk-review")
        let summaries = try reopened.chunkSummaries(for: "chunk-review")
        XCTAssertGreaterThan(chunks.count, 1)
        XCTAssertEqual(summaries, memoryStore.chunkSummaries(for: "chunk-review"))
        XCTAssertEqual(summaries.map(\.chunkIndex), chunks.map(\.chunkIndex))
        XCTAssertEqual(summaries.map(\.characterCount), chunks.map { $0.text.count })
        XCTAssertEqual(
            try reopened.chunkSummaries(for: "chunk-review", limit: 1),
            Array(memoryStore.chunkSummaries(for: "chunk-review").prefix(1))
        )
        XCTAssertEqual(try reopened.chunkSummaries(for: "missing"), [])
        XCTAssertEqual(try reopened.chunkSummaries(for: ""), [])
        XCTAssertEqual(try reopened.chunkSummaries(for: "chunk-review", limit: 0), [])
        XCTAssertFalse(String(describing: summaries).contains(bodySentinel))
        XCTAssertFalse(String(describing: summaries).contains("source_path"))
        XCTAssertFalse(String(describing: summaries).contains("project_id"))
        XCTAssertFalse(String(describing: summaries).contains("workspace_id"))
        XCTAssertFalse(String(describing: summaries).contains("retrieval_context"))
        XCTAssertFalse(String(describing: summaries).contains("embedding"))
        XCTAssertFalse(String(describing: summaries).contains("citation"))
        XCTAssertFalse(String(describing: summaries).contains("trusted_source"))

        _ = memoryStore.replaceDocument(result: replacement, documentID: "chunk-review")
        try reopened.replaceDocument(result: replacement, documentID: "chunk-review")

        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try rereopened.chunkSummaries(for: "chunk-review"), memoryStore.chunkSummaries(for: "chunk-review"))
        XCTAssertEqual(try rereopened.chunkSummaries(for: "chunk-review").single?.characterCount, replacement.chunks.single?.text.count)

        memoryStore.deleteDocument(id: "chunk-review")
        try rereopened.deleteDocument(id: "chunk-review")
        XCTAssertEqual(try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).chunkSummaries(for: "chunk-review"), [])
    }

    func testSQLiteChunkReadsApplyStoreOwnedLimitCeilingAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let manyChunks = try ingestedDocument(
            fileName: "chunk-read.md",
            text: chunkCeilingText(minimumChunks: runtimeDocumentIndexChunkReadLimitCeiling + 5)
        )
        let replacement = try ingestedDocument(
            fileName: "chunk-read.md",
            text: "SQLite replacement chunk read content stays bounded."
        )

        _ = memoryStore.replaceDocument(result: manyChunks, documentID: "chunk-read")
        try sqliteStore.replaceDocument(result: manyChunks, documentID: "chunk-read")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let limitedChunks = try reopened.chunks(
            for: "chunk-read",
            limit: runtimeDocumentIndexChunkReadLimitCeiling + 50
        )
        XCTAssertEqual(
            limitedChunks,
            memoryStore.chunks(
                for: "chunk-read",
                limit: runtimeDocumentIndexChunkReadLimitCeiling + 50
            )
        )
        XCTAssertEqual(limitedChunks.count, runtimeDocumentIndexChunkReadLimitCeiling)
        XCTAssertEqual(limitedChunks.map(\.chunkIndex), Array(0..<runtimeDocumentIndexChunkReadLimitCeiling))
        XCTAssertEqual(try reopened.chunks(for: "chunk-read", limit: 1), memoryStore.chunks(for: "chunk-read", limit: 1))
        XCTAssertEqual(try reopened.chunks(for: "chunk-read", limit: 0), [])
        XCTAssertEqual(try reopened.chunks(for: ""), [])
        XCTAssertFalse(String(describing: limitedChunks).contains("source_path"))
        XCTAssertFalse(String(describing: limitedChunks).contains("project_id"))
        XCTAssertFalse(String(describing: limitedChunks).contains("workspace_id"))
        XCTAssertFalse(String(describing: limitedChunks).contains("retrieval_context"))
        XCTAssertFalse(String(describing: limitedChunks).contains("embedding"))
        XCTAssertFalse(String(describing: limitedChunks).contains("citation"))
        XCTAssertFalse(String(describing: limitedChunks).contains("trusted_source"))

        _ = memoryStore.replaceDocument(result: replacement, documentID: "chunk-read")
        try reopened.replaceDocument(result: replacement, documentID: "chunk-read")

        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try rereopened.chunks(
                for: "chunk-read",
                limit: runtimeDocumentIndexChunkReadLimitCeiling + 50
            ),
            memoryStore.chunks(
                for: "chunk-read",
                limit: runtimeDocumentIndexChunkReadLimitCeiling + 50
            )
        )

        memoryStore.deleteDocument(id: "chunk-read")
        try rereopened.deleteDocument(id: "chunk-read")
        XCTAssertEqual(
            try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).chunks(
                for: "chunk-read",
                limit: runtimeDocumentIndexChunkReadLimitCeiling + 50
            ),
            []
        )
    }

    func testSQLiteStoreCatalogChunkSummariesAndQueryApplyStoreOwnedLimitCeilingsAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let totalDocuments = max(runtimeDocumentIndexCatalogLimitCeiling, runtimeDocumentIndexQueryLimitCeiling) + 5

        for index in 0..<totalDocuments {
            let id = String(format: "ceiling-%03d", index)
            let result = try ingestedDocument(
                fileName: "\(id).md",
                text: "SQLite ceiling query term \(index) remains private while metadata limits are enforced."
            )
            _ = memoryStore.replaceDocument(result: result, documentID: id)
            try sqliteStore.replaceDocument(result: result, documentID: id)
        }

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.documents(limit: totalDocuments), memoryStore.documents(limit: totalDocuments))
        XCTAssertEqual(try reopened.documents(limit: totalDocuments).count, runtimeDocumentIndexCatalogLimitCeiling)
        XCTAssertEqual(
            try reopened.documents(matchingMimeType: "text/markdown", limit: totalDocuments),
            memoryStore.documents(matchingMimeType: "text/markdown", limit: totalDocuments)
        )
        XCTAssertEqual(
            try reopened.documents(matchingQuality: .singleChunk, limit: totalDocuments),
            memoryStore.documents(matchingQuality: .singleChunk, limit: totalDocuments)
        )
        XCTAssertEqual(try reopened.query("ceiling", limit: totalDocuments), memoryStore.query("ceiling", limit: totalDocuments))
        XCTAssertEqual(try reopened.query("ceiling", limit: totalDocuments).count, runtimeDocumentIndexQueryLimitCeiling)

        let manyChunks = try ingestedDocument(
            fileName: "many-chunks.md",
            text: chunkCeilingText(minimumChunks: runtimeDocumentIndexChunkSummaryLimitCeiling + 5)
        )
        _ = memoryStore.replaceDocument(result: manyChunks, documentID: "many-chunks")
        try reopened.replaceDocument(result: manyChunks, documentID: "many-chunks")

        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertGreaterThan(memoryStore.chunks(for: "many-chunks").count, runtimeDocumentIndexChunkSummaryLimitCeiling)
        XCTAssertEqual(
            try rereopened.chunkSummaries(
                for: "many-chunks",
                limit: runtimeDocumentIndexChunkSummaryLimitCeiling + 50
            ),
            memoryStore.chunkSummaries(
                for: "many-chunks",
                limit: runtimeDocumentIndexChunkSummaryLimitCeiling + 50
            )
        )
        XCTAssertEqual(
            try rereopened.chunkSummaries(
                for: "many-chunks",
                limit: runtimeDocumentIndexChunkSummaryLimitCeiling + 50
            ).count,
            runtimeDocumentIndexChunkSummaryLimitCeiling
        )
    }

    func testSQLiteQueryTermsApplyStoreOwnedResourceGuardsWithoutFtsSyntaxErrors() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let result = try ingestedDocument(
            fileName: "query-guard.md",
            text: "Alpha or beta gamma delta guarded term appears in SQLite runtime document search."
        )
        _ = memoryStore.replaceDocument(result: result, documentID: "query-guard")
        try sqliteStore.replaceDocument(result: result, documentID: "query-guard")
        XCTAssertGreaterThan(try ftsTotalRowCount(in: databaseURL), 0)

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let overlongQuery = String(repeating: "a", count: runtimeDocumentIndexQueryTextCharacterLimitCeiling + 1)
        let overlongTerm = String(repeating: "x", count: runtimeDocumentIndexQueryTermCharacterLimitCeiling + 1)
        let excessiveTerms = (0...runtimeDocumentIndexQueryTermLimitCeiling)
            .map { "term\($0)" }
            .joined(separator: " ")
        let duplicateTerms = String(repeating: "guarded ", count: runtimeDocumentIndexQueryTermLimitCeiling + 3)
        let operatorHeavyQuery = "alpha OR beta - gamma \"delta\"*"

        XCTAssertEqual(try reopened.query("guarded term"), memoryStore.query("guarded term"))
        XCTAssertEqual(try reopened.query("---- !!!"), [])
        XCTAssertEqual(memoryStore.query("---- !!!"), [])
        XCTAssertEqual(try reopened.query(overlongQuery), [])
        XCTAssertEqual(memoryStore.query(overlongQuery), [])
        XCTAssertEqual(try reopened.query(overlongTerm), [])
        XCTAssertEqual(memoryStore.query(overlongTerm), [])
        XCTAssertEqual(try reopened.query(excessiveTerms), [])
        XCTAssertEqual(memoryStore.query(excessiveTerms), [])
        XCTAssertEqual(try reopened.query(duplicateTerms), memoryStore.query(duplicateTerms))
        XCTAssertEqual(try reopened.query(duplicateTerms).single?.document.id, "query-guard")
        XCTAssertEqual(try reopened.query(operatorHeavyQuery), memoryStore.query(operatorHeavyQuery))
        XCTAssertEqual(runtimeDocumentIndexEffectiveSearchTerms(operatorHeavyQuery), ["alpha", "or", "beta", "gamma", "delta"])
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

    func testSQLiteStoreNormalizesMalformedIngestionSummaryAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let chunked = try ingestedDocument(
            fileName: "summary.md",
            text: chunkCeilingText(minimumChunks: 2)
        )
        XCTAssertGreaterThan(chunked.chunks.count, 1)

        let malformedChunked = DocumentIngestionResult(
            document: chunked.document,
            chunks: chunked.chunks,
            summary: DocumentIngestionSummary(
                documentFileName: chunked.summary.documentFileName,
                documentMimeType: chunked.summary.documentMimeType,
                extractedCharacterCount: -900,
                chunkCount: 999,
                minChunkCharacters: 0,
                maxChunkCharacters: 0,
                quality: .noUsableText
            )
        )
        let empty = try ingestedDocument(fileName: "empty.md", text: "   ")
        let malformedEmpty = DocumentIngestionResult(
            document: empty.document,
            chunks: empty.chunks,
            summary: DocumentIngestionSummary(
                documentFileName: empty.summary.documentFileName,
                documentMimeType: empty.summary.documentMimeType,
                extractedCharacterCount: 777,
                chunkCount: 8,
                minChunkCharacters: 8,
                maxChunkCharacters: 128,
                quality: .chunked
            )
        )

        XCTAssertEqual(
            RuntimeDocumentIndexStore.stableContentFingerprint(for: malformedChunked),
            RuntimeDocumentIndexStore.stableContentFingerprint(for: chunked)
        )

        try sqliteStore.replaceDocument(result: malformedChunked, documentID: "summary")
        try sqliteStore.replaceDocument(result: malformedEmpty, documentID: "empty")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let storedChunked = try XCTUnwrap(reopened.document(id: "summary"))
        let storedEmpty = try XCTUnwrap(reopened.document(id: "empty"))
        let expectedCharacterCount = chunked.document.text.trimmingCharacters(in: .whitespacesAndNewlines).count

        XCTAssertEqual(storedChunked.extractedCharacterCount, expectedCharacterCount)
        XCTAssertEqual(storedChunked.chunkCount, chunked.chunks.count)
        XCTAssertEqual(storedChunked.quality, .chunked)
        XCTAssertEqual(storedEmpty.extractedCharacterCount, 0)
        XCTAssertEqual(storedEmpty.chunkCount, 0)
        XCTAssertEqual(storedEmpty.quality, .noUsableText)
        XCTAssertEqual(try reopened.summary().extractedCharacterCount, expectedCharacterCount)
        XCTAssertEqual(try reopened.summary().chunkCount, chunked.chunks.count)
        XCTAssertEqual(try reopened.summary().qualityCounts[.chunked], 1)
        XCTAssertEqual(try reopened.summary().qualityCounts[.noUsableText], 1)
        XCTAssertEqual(
            try rawIntValues(
                in: databaseURL,
                table: "runtime_document_index_documents",
                column: "extracted_character_count"
            ),
            [0, expectedCharacterCount]
        )
        XCTAssertEqual(
            try rawIntValues(in: databaseURL, table: "runtime_document_index_documents", column: "chunk_count"),
            [0, chunked.chunks.count]
        )
        XCTAssertEqual(
            try rawStringValues(in: databaseURL, table: "runtime_document_index_documents", column: "quality"),
            ["chunked", "no_usable_text"]
        )
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
        let uppercaseFingerprint = "ABCDEFABCDEFABCD"
        let caseMutatedFingerprint = "A" + String(duplicateFingerprint.dropFirst())
        let underLengthFingerprint = String(repeating: "a", count: runtimeDocumentIndexContentFingerprintCharacterCount - 1)
        let overLengthFingerprint = String(repeating: "a", count: runtimeDocumentIndexContentFingerprintCharacterCount + 1)
        let nonHexFingerprint = String(repeating: "g", count: runtimeDocumentIndexContentFingerprintCharacterCount)

        XCTAssertEqual(duplicateFingerprint, RuntimeDocumentIndexStore.stableContentFingerprint(for: copyA))
        XCTAssertNotEqual(duplicateFingerprint, RuntimeDocumentIndexStore.stableContentFingerprint(for: unrelated))
        XCTAssertEqual(runtimeDocumentIndexCanonicalContentFingerprint(" \(duplicateFingerprint)\n"), duplicateFingerprint)
        XCTAssertNil(runtimeDocumentIndexCanonicalContentFingerprint(""))
        XCTAssertNil(runtimeDocumentIndexCanonicalContentFingerprint(" \n\t "))
        XCTAssertNil(runtimeDocumentIndexCanonicalContentFingerprint(uppercaseFingerprint))
        XCTAssertNil(runtimeDocumentIndexCanonicalContentFingerprint(caseMutatedFingerprint))
        XCTAssertNil(runtimeDocumentIndexCanonicalContentFingerprint(underLengthFingerprint))
        XCTAssertNil(runtimeDocumentIndexCanonicalContentFingerprint(overLengthFingerprint))
        XCTAssertNil(runtimeDocumentIndexCanonicalContentFingerprint(nonHexFingerprint))

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
            try reopened.documents(matchingContentFingerprint: " \(duplicateFingerprint)\n"),
            memoryStore.documents(matchingContentFingerprint: " \(duplicateFingerprint)\n")
        )
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: " \(duplicateFingerprint)\n").map(\.id), ["copy-a", "copy-b"])
        XCTAssertEqual(
            try reopened.documents(matchingContentFingerprint: duplicateFingerprint, limit: 1).map(\.id),
            ["copy-a"]
        )
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: "missing"), [])
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: ""), [])
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: " \n\t "), [])
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: uppercaseFingerprint), [])
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: caseMutatedFingerprint), [])
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: underLengthFingerprint), [])
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: overLengthFingerprint), [])
        XCTAssertEqual(try reopened.documents(matchingContentFingerprint: nonHexFingerprint), [])
        XCTAssertFalse(String(describing: matches).contains(duplicateText))
        XCTAssertFalse(String(describing: matches).contains("source_path"))
        XCTAssertFalse(String(describing: matches).contains("workspace_id"))
        XCTAssertFalse(String(describing: matches).contains("retrieval_context"))
        XCTAssertFalse(String(describing: matches).contains("embedding"))
        XCTAssertFalse(String(describing: matches).contains("citation"))
        XCTAssertFalse(String(describing: matches).contains("trusted_source"))

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

    func testSQLiteStoreDeleteDocumentsByContentFingerprintClearsMatchingRowsAndFtsAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let duplicateText = "SQLite fingerprint delete duplicate text should be removed from runtime document search."
        let copyB = try ingestedDocument(fileName: "copy-b.md", text: duplicateText)
        let copyA = try ingestedDocument(fileName: "copy-a.md", text: duplicateText)
        let unrelated = try ingestedDocument(
            fileName: "unrelated.md",
            text: "SQLite unrelated fingerprint delete text should remain searchable after cleanup."
        )
        let duplicateFingerprint = RuntimeDocumentIndexStore.stableContentFingerprint(for: copyB)
        let uppercaseFingerprint = "A" + String(duplicateFingerprint.dropFirst())
        let overLengthFingerprint = String(repeating: "a", count: runtimeDocumentIndexContentFingerprintCharacterCount + 1)

        _ = memoryStore.replaceDocument(result: copyB, documentID: "copy-b")
        _ = memoryStore.replaceDocument(result: unrelated, documentID: "unrelated")
        _ = memoryStore.replaceDocument(result: copyA, documentID: "copy-a")
        try sqliteStore.replaceDocument(result: copyB, documentID: "copy-b")
        try sqliteStore.replaceDocument(result: unrelated, documentID: "unrelated")
        try sqliteStore.replaceDocument(result: copyA, documentID: "copy-a")
        XCTAssertGreaterThan(try ftsTotalRowCount(in: databaseURL), 0)

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try reopened.documents(matchingContentFingerprint: duplicateFingerprint),
            memoryStore.documents(matchingContentFingerprint: duplicateFingerprint)
        )
        try reopened.deleteDocuments(matchingContentFingerprint: uppercaseFingerprint)
        try reopened.deleteDocuments(matchingContentFingerprint: overLengthFingerprint)
        XCTAssertEqual(try reopened.documents(), memoryStore.documents())

        memoryStore.deleteDocuments(matchingContentFingerprint: " \(duplicateFingerprint)\n")
        try reopened.deleteDocuments(matchingContentFingerprint: " \(duplicateFingerprint)\n")

        let afterDelete = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertNil(try afterDelete.document(id: "copy-a"))
        XCTAssertNil(try afterDelete.document(id: "copy-b"))
        XCTAssertNotNil(try afterDelete.document(id: "unrelated"))
        XCTAssertEqual(try afterDelete.chunks(for: "copy-a"), [])
        XCTAssertEqual(try afterDelete.chunks(for: "copy-b"), [])
        XCTAssertFalse(try afterDelete.chunks(for: "unrelated").isEmpty)
        XCTAssertEqual(try afterDelete.chunkSummaries(for: "copy-a"), [])
        XCTAssertEqual(try afterDelete.chunkSummaries(for: "copy-b"), [])
        XCTAssertFalse(try afterDelete.chunkSummaries(for: "unrelated").isEmpty)
        XCTAssertEqual(try afterDelete.documents(matchingContentFingerprint: duplicateFingerprint), [])
        XCTAssertEqual(try afterDelete.documents(), memoryStore.documents())
        XCTAssertEqual(try afterDelete.documents().map(\.id), ["unrelated"])
        XCTAssertEqual(try afterDelete.query("duplicate"), [])
        XCTAssertEqual(try afterDelete.query("unrelated").single?.document.id, "unrelated")
        XCTAssertEqual(try afterDelete.summary(), memoryStore.summary())
        XCTAssertEqual(try afterDelete.summary().documentCount, 1)
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "copy-a"), 0)
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "copy-b"), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: "unrelated"), 0)
        XCTAssertFalse(String(describing: try afterDelete.documents()).contains(duplicateText))
        XCTAssertFalse(String(describing: try afterDelete.documents()).contains("source_path"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("project_id"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("workspace_id"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("citation"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("trusted_source"))

        try afterDelete.deleteDocuments(matchingContentFingerprint: duplicateFingerprint)
        XCTAssertEqual(try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).documents(), memoryStore.documents())
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

    func testSQLiteStoreListsDocumentsByMimeTypeAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let bodySentinel = "PRIVATE_SQLITE_MIME_BODY_SHOULD_NOT_APPEAR"
        let markdownB = try ingestedDocument(fileName: "markdown-b.md", text: "\(bodySentinel) markdown body remains private.")
        let markdownA = try ingestedDocument(fileName: "markdown-a.md", text: "Second SQLite markdown body remains private.")
        let plain = try ingestedDocument(
            fileName: "notes.txt",
            mimeType: "text/plain",
            text: "SQLite plain text body remains private."
        )
        let spacedPlain = try ingestedDocument(
            fileName: "aaa-spaced.txt",
            mimeType: " text/plain\n",
            text: "SQLite spaced MIME text should store as canonical plain text."
        )
        let pdf = try ingestedDocument(
            fileName: "brief.pdf",
            mimeType: "application/pdf",
            text: "SQLite PDF extracted body remains private."
        )
        let malformedMime = try ingestedDocument(
            fileName: "zzz-unknown.bin",
            mimeType: "text/plain; charset=utf-8",
            text: "SQLite malformed MIME text should store under the safe unknown type."
        )
        let replacement = try ingestedDocument(
            fileName: "markdown-b.txt",
            mimeType: "text/plain",
            text: "SQLite replacement text body remains private."
        )
        let caseMutatedMimeType = "Text/markdown"
        let missingSlashMimeType = "textplain"
        let urlShapedMimeType = "https://example.invalid/text/plain"
        let overlongMimeType = String(repeating: "a", count: runtimeDocumentIndexMimeTypeCharacterLimitCeiling + 1)

        XCTAssertEqual(runtimeDocumentIndexCanonicalMimeType(" text/markdown\n"), "text/markdown")
        XCTAssertNil(runtimeDocumentIndexCanonicalMimeType(""))
        XCTAssertNil(runtimeDocumentIndexCanonicalMimeType(" \n\t "))
        XCTAssertNil(runtimeDocumentIndexCanonicalMimeType(caseMutatedMimeType))
        XCTAssertNil(runtimeDocumentIndexCanonicalMimeType(missingSlashMimeType))
        XCTAssertNil(runtimeDocumentIndexCanonicalMimeType(urlShapedMimeType))
        XCTAssertNil(runtimeDocumentIndexCanonicalMimeType(overlongMimeType))
        XCTAssertEqual(runtimeDocumentIndexEffectiveMimeType("text/plain; charset=utf-8"), runtimeDocumentIndexUnknownMimeType)

        _ = memoryStore.replaceDocument(result: markdownB, documentID: "markdown-b")
        _ = memoryStore.replaceDocument(result: spacedPlain, documentID: "spaced-plain")
        _ = memoryStore.replaceDocument(result: plain, documentID: "plain")
        _ = memoryStore.replaceDocument(result: pdf, documentID: "pdf")
        _ = memoryStore.replaceDocument(result: malformedMime, documentID: "unknown")
        _ = memoryStore.replaceDocument(result: markdownA, documentID: "markdown-a")
        try sqliteStore.replaceDocument(result: markdownB, documentID: "markdown-b")
        try sqliteStore.replaceDocument(result: spacedPlain, documentID: "spaced-plain")
        try sqliteStore.replaceDocument(result: plain, documentID: "plain")
        try sqliteStore.replaceDocument(result: pdf, documentID: "pdf")
        try sqliteStore.replaceDocument(result: malformedMime, documentID: "unknown")
        try sqliteStore.replaceDocument(result: markdownA, documentID: "markdown-a")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let markdownCatalog = try reopened.documents(matchingMimeType: "text/markdown")
        XCTAssertEqual(markdownCatalog, memoryStore.documents(matchingMimeType: "text/markdown"))
        XCTAssertEqual(markdownCatalog.map(\.id), ["markdown-a", "markdown-b"])
        XCTAssertEqual(
            try reopened.documents(matchingMimeType: " text/markdown\n"),
            memoryStore.documents(matchingMimeType: " text/markdown\n")
        )
        XCTAssertEqual(
            try reopened.documents(matchingMimeType: "text/markdown", limit: 1).map(\.id),
            ["markdown-a"]
        )
        XCTAssertEqual(try reopened.documents(matchingMimeType: "text/plain"), memoryStore.documents(matchingMimeType: "text/plain"))
        XCTAssertEqual(
            try reopened.documents(matchingMimeType: " text/plain\n"),
            memoryStore.documents(matchingMimeType: " text/plain\n")
        )
        XCTAssertEqual(try reopened.documents(matchingMimeType: "application/pdf"), memoryStore.documents(matchingMimeType: "application/pdf"))
        XCTAssertEqual(
            try reopened.documents(matchingMimeType: runtimeDocumentIndexUnknownMimeType),
            memoryStore.documents(matchingMimeType: runtimeDocumentIndexUnknownMimeType)
        )
        XCTAssertEqual(try reopened.documents(matchingMimeType: "application/json"), [])
        XCTAssertEqual(try reopened.documents(matchingMimeType: ""), [])
        XCTAssertEqual(try reopened.documents(matchingMimeType: " \n\t "), [])
        XCTAssertEqual(try reopened.documents(matchingMimeType: caseMutatedMimeType), [])
        XCTAssertEqual(try reopened.documents(matchingMimeType: missingSlashMimeType), [])
        XCTAssertEqual(try reopened.documents(matchingMimeType: urlShapedMimeType), [])
        XCTAssertEqual(try reopened.documents(matchingMimeType: overlongMimeType), [])
        XCTAssertEqual(try reopened.documents(matchingMimeType: "text/plain; charset=utf-8"), [])
        XCTAssertEqual(try reopened.documents(matchingMimeType: "text/markdown", limit: 0), [])
        XCTAssertEqual(try reopened.document(id: "spaced-plain")?.mimeType, "text/plain")
        XCTAssertEqual(try reopened.document(id: "unknown")?.mimeType, runtimeDocumentIndexUnknownMimeType)
        XCTAssertEqual(Set(try reopened.chunks(for: "spaced-plain").map(\.documentMimeType)), ["text/plain"])
        XCTAssertEqual(Set(try reopened.chunks(for: "unknown").map(\.documentMimeType)), [runtimeDocumentIndexUnknownMimeType])
        let storedDocumentMimeTypes = try rawStringValues(
            in: databaseURL,
            table: "runtime_document_index_documents",
            column: "mime_type"
        )
        let storedChunkMimeTypes = try rawStringValues(
            in: databaseURL,
            table: "runtime_document_index_chunks",
            column: "document_mime_type"
        )
        XCTAssertFalse(storedDocumentMimeTypes.contains(" text/plain\n"))
        XCTAssertFalse(storedDocumentMimeTypes.contains("text/plain; charset=utf-8"))
        XCTAssertFalse(storedChunkMimeTypes.contains(" text/plain\n"))
        XCTAssertFalse(storedChunkMimeTypes.contains("text/plain; charset=utf-8"))
        XCTAssertFalse(String(describing: markdownCatalog).contains(bodySentinel))
        XCTAssertFalse(String(describing: markdownCatalog).contains("source_path"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("workspace_id"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("retrieval_context"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("embedding"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("citation"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("trusted_source"))

        _ = memoryStore.replaceDocument(result: replacement, documentID: "markdown-b")
        memoryStore.deleteDocument(id: "markdown-a")
        try reopened.replaceDocument(result: replacement, documentID: "markdown-b")
        try reopened.deleteDocument(id: "markdown-a")

        let rereopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try rereopened.documents(matchingMimeType: "text/markdown"), [])
        XCTAssertEqual(try rereopened.documents(matchingMimeType: "text/plain"), memoryStore.documents(matchingMimeType: "text/plain"))
    }

    func testSQLiteStoreDeleteDocumentsByMimeTypeClearsMatchingRowsAndFtsAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let markdownSentinel = "SQLiteMarkdownMimeDeleteSentinel"
        let plainSentinel = "SQLitePlainMimeDeleteSentinel"
        let pdfSentinel = "SQLitePdfMimeDeleteSentinel"
        let markdownB = try ingestedDocument(
            fileName: "markdown-b.md",
            text: "\(markdownSentinel) cleanup duplicate markdown rows should be removed together."
        )
        let markdownA = try ingestedDocument(
            fileName: "markdown-a.md",
            text: "\(markdownSentinel) cleanup second markdown row should be removed together."
        )
        let plain = try ingestedDocument(
            fileName: "notes.txt",
            mimeType: "text/plain",
            text: "\(plainSentinel) cleanup text remains searchable."
        )
        let pdf = try ingestedDocument(
            fileName: "brief.pdf",
            mimeType: "application/pdf",
            text: "\(pdfSentinel) cleanup text remains indexed."
        )
        let caseMutatedMimeType = "Text/markdown"
        let overlongMimeType = String(repeating: "a", count: runtimeDocumentIndexMimeTypeCharacterLimitCeiling + 1)

        _ = memoryStore.replaceDocument(result: markdownB, documentID: "markdown-b")
        _ = memoryStore.replaceDocument(result: plain, documentID: "plain")
        _ = memoryStore.replaceDocument(result: pdf, documentID: "pdf")
        _ = memoryStore.replaceDocument(result: markdownA, documentID: "markdown-a")
        try sqliteStore.replaceDocument(result: markdownB, documentID: "markdown-b")
        try sqliteStore.replaceDocument(result: plain, documentID: "plain")
        try sqliteStore.replaceDocument(result: pdf, documentID: "pdf")
        try sqliteStore.replaceDocument(result: markdownA, documentID: "markdown-a")
        XCTAssertGreaterThan(try ftsTotalRowCount(in: databaseURL), 0)

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try reopened.documents(matchingMimeType: "text/markdown"),
            memoryStore.documents(matchingMimeType: "text/markdown")
        )
        try reopened.deleteDocuments(matchingMimeType: caseMutatedMimeType)
        try reopened.deleteDocuments(matchingMimeType: overlongMimeType)
        XCTAssertEqual(try reopened.documents(), memoryStore.documents())

        memoryStore.deleteDocuments(matchingMimeType: " text/markdown\n")
        try reopened.deleteDocuments(matchingMimeType: " text/markdown\n")

        let afterDelete = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertNil(try afterDelete.document(id: "markdown-a"))
        XCTAssertNil(try afterDelete.document(id: "markdown-b"))
        XCTAssertNotNil(try afterDelete.document(id: "plain"))
        XCTAssertNotNil(try afterDelete.document(id: "pdf"))
        XCTAssertEqual(try afterDelete.chunks(for: "markdown-a"), [])
        XCTAssertEqual(try afterDelete.chunks(for: "markdown-b"), [])
        XCTAssertFalse(try afterDelete.chunks(for: "plain").isEmpty)
        XCTAssertFalse(try afterDelete.chunks(for: "pdf").isEmpty)
        XCTAssertEqual(try afterDelete.chunkSummaries(for: "markdown-a"), [])
        XCTAssertEqual(try afterDelete.chunkSummaries(for: "markdown-b"), [])
        XCTAssertFalse(try afterDelete.chunkSummaries(for: "plain").isEmpty)
        XCTAssertEqual(try afterDelete.documents(matchingMimeType: "text/markdown"), [])
        XCTAssertEqual(try afterDelete.documents(), memoryStore.documents())
        XCTAssertEqual(try afterDelete.documents().map(\.id), ["pdf", "plain"])
        XCTAssertEqual(try afterDelete.query(markdownSentinel), [])
        XCTAssertEqual(try afterDelete.query(plainSentinel).single?.document.id, "plain")
        XCTAssertEqual(try afterDelete.query(pdfSentinel).single?.document.id, "pdf")
        XCTAssertEqual(try afterDelete.summary(), memoryStore.summary())
        XCTAssertEqual(try afterDelete.summary().documentCount, 2)
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "markdown-a"), 0)
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "markdown-b"), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: "plain"), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: "pdf"), 0)
        XCTAssertFalse(String(describing: try afterDelete.documents()).contains(markdownSentinel))
        XCTAssertFalse(String(describing: try afterDelete.documents()).contains("source_path"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("project_id"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("workspace_id"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("citation"))
        XCTAssertFalse(String(describing: try afterDelete.summary()).contains("trusted_source"))

        try afterDelete.deleteDocuments(matchingMimeType: "text/markdown")
        XCTAssertEqual(try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).documents(), memoryStore.documents())
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

    func testSQLiteStoreDeleteAllDocumentsClearsCatalogChunksSummaryQueryAndFtsAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let alpha = try ingestedDocument(
            fileName: "alpha.md",
            text: "SQLite alpha clear-all query text should disappear from runtime document search."
        )
        let beta = try ingestedDocument(
            fileName: "beta.md",
            text: "SQLite beta clear-all maintenance content should leave no chunk summaries behind."
        )

        _ = memoryStore.replaceDocument(result: alpha, documentID: "alpha")
        _ = memoryStore.replaceDocument(result: beta, documentID: "beta")
        try sqliteStore.replaceDocument(result: alpha, documentID: "alpha")
        try sqliteStore.replaceDocument(result: beta, documentID: "beta")

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.documents(), memoryStore.documents())
        XCTAssertFalse(try reopened.chunkSummaries(for: "alpha").isEmpty)
        XCTAssertFalse(try reopened.query("clear-all").isEmpty)
        XCTAssertGreaterThan(try ftsTotalRowCount(in: databaseURL), 0)

        memoryStore.deleteAllDocuments()
        try reopened.deleteAllDocuments()

        let cleared = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try cleared.documents(), memoryStore.documents())
        XCTAssertEqual(try cleared.documents(matchingDisplayName: "alpha.md"), [])
        XCTAssertEqual(try cleared.documents(matchingMimeType: "text/markdown"), [])
        XCTAssertEqual(try cleared.documents(matchingQuality: .singleChunk), [])
        XCTAssertNil(try cleared.document(id: "alpha"))
        XCTAssertNil(try cleared.document(id: "beta"))
        XCTAssertEqual(try cleared.chunks(for: "alpha"), [])
        XCTAssertEqual(try cleared.chunks(for: "beta"), [])
        XCTAssertEqual(try cleared.chunkSummaries(for: "alpha"), [])
        XCTAssertEqual(try cleared.query("clear-all"), [])
        XCTAssertEqual(try cleared.summary(), memoryStore.summary())
        XCTAssertEqual(try cleared.summary().documentCount, 0)
        XCTAssertEqual(try ftsTotalRowCount(in: databaseURL), 0)
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "alpha"), 0)
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "beta"), 0)
        XCTAssertFalse(String(describing: try cleared.summary()).contains("source_path"))
        XCTAssertFalse(String(describing: try cleared.summary()).contains("project_id"))
        XCTAssertFalse(String(describing: try cleared.summary()).contains("workspace_id"))
        XCTAssertFalse(String(describing: try cleared.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: try cleared.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: try cleared.summary()).contains("citation"))
        XCTAssertFalse(String(describing: try cleared.summary()).contains("trusted_source"))

        try cleared.deleteAllDocuments()
        XCTAssertEqual(try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).documents(), [])
        XCTAssertEqual(try ftsTotalRowCount(in: databaseURL), 0)
    }

    func testSQLiteStoreDeleteDocumentsByQualityClearsMatchingRowsAndFtsAfterReopen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let memoryStore = RuntimeDocumentIndexStore()
        let empty = try ingestedDocument(fileName: "empty.md", text: "   ")
        let chunked = try ingestedDocument(
            fileName: "chunked.md",
            text: [
                "SQLite chunked quality deletion text should remain searchable after empty rows are removed.",
                "Additional text forces chunk planning and keeps metadata maintenance useful.",
                "The runtime index must not expose source paths while deleting by quality."
            ].joined(separator: " ")
        )
        let single = try ingestedDocument(
            fileName: "single.md",
            text: "SQLite single quality deletion text should remain in the runtime index."
        )

        _ = memoryStore.replaceDocument(result: empty, documentID: "empty")
        _ = memoryStore.replaceDocument(result: chunked, documentID: "chunked")
        _ = memoryStore.replaceDocument(result: single, documentID: "single")
        try sqliteStore.replaceDocument(result: empty, documentID: "empty")
        try sqliteStore.replaceDocument(result: chunked, documentID: "chunked")
        try sqliteStore.replaceDocument(result: single, documentID: "single")
        XCTAssertGreaterThan(try ftsTotalRowCount(in: databaseURL), 0)

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.documents(), memoryStore.documents())
        memoryStore.deleteDocuments(matchingQuality: .noUsableText)
        try reopened.deleteDocuments(matchingQuality: .noUsableText)

        let afterEmptyDelete = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertNil(try afterEmptyDelete.document(id: "empty"))
        XCTAssertEqual(try afterEmptyDelete.chunks(for: "empty"), [])
        XCTAssertEqual(try afterEmptyDelete.chunkSummaries(for: "empty"), [])
        XCTAssertEqual(try afterEmptyDelete.documents(matchingQuality: .noUsableText), [])
        XCTAssertEqual(try afterEmptyDelete.documents(), memoryStore.documents())
        XCTAssertEqual(try afterEmptyDelete.documents().map(\.id), ["chunked", "single"])
        XCTAssertEqual(try afterEmptyDelete.documents(matchingQuality: .chunked).map(\.id), ["chunked"])
        XCTAssertEqual(try afterEmptyDelete.documents(matchingQuality: .singleChunk).map(\.id), ["single"])
        XCTAssertEqual(try afterEmptyDelete.query("quality deletion"), memoryStore.query("quality deletion"))
        XCTAssertEqual(Set(try afterEmptyDelete.query("quality deletion").map(\.document.id)), Set(["chunked", "single"]))
        XCTAssertFalse(try afterEmptyDelete.query("quality deletion").contains { $0.document.id == "empty" })
        XCTAssertEqual(try afterEmptyDelete.summary(), memoryStore.summary())
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "empty"), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: "chunked"), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: "single"), 0)
        XCTAssertFalse(String(describing: try afterEmptyDelete.summary()).contains("source_path"))
        XCTAssertFalse(String(describing: try afterEmptyDelete.summary()).contains("project_id"))
        XCTAssertFalse(String(describing: try afterEmptyDelete.summary()).contains("workspace_id"))
        XCTAssertFalse(String(describing: try afterEmptyDelete.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: try afterEmptyDelete.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: try afterEmptyDelete.summary()).contains("citation"))
        XCTAssertFalse(String(describing: try afterEmptyDelete.summary()).contains("trusted_source"))

        try afterEmptyDelete.deleteDocuments(matchingQuality: .noUsableText)
        XCTAssertEqual(try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).documents(), memoryStore.documents())

        memoryStore.deleteDocuments(matchingQuality: .chunked)
        try afterEmptyDelete.deleteDocuments(matchingQuality: .chunked)

        let final = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(try final.documents(), memoryStore.documents())
        XCTAssertEqual(try final.documents().map(\.id), ["single"])
        XCTAssertEqual(try final.query("chunked"), [])
        XCTAssertEqual(try final.query("single").single?.document.id, "single")
        XCTAssertEqual(try ftsRowCount(in: databaseURL, documentID: "chunked"), 0)
        XCTAssertGreaterThan(try ftsRowCount(in: databaseURL, documentID: "single"), 0)
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

    private func chunkCeilingText(minimumChunks: Int) -> String {
        (0..<minimumChunks)
            .map { index in
                "SQLite ceiling chunk \(index) keeps metadata review bounded with repeated runtime-local content for splitting."
            }
            .joined(separator: " ")
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

    private func rawDocumentIDs(in databaseURL: URL, table: String) throws -> [String] {
        let database = try openRawDatabase(databaseURL)
        defer { sqlite3_close(database) }
        let statement = try prepareRaw(
            database,
            "SELECT document_id FROM \(table) ORDER BY document_id ASC"
        )
        defer { sqlite3_finalize(statement) }

        var documentIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 4)
            }
            let rawDocumentID = try XCTUnwrap(sqlite3_column_text(statement, 0))
            documentIDs.append(String(cString: rawDocumentID))
        }
        return documentIDs
    }

    private func rawStringValues(in databaseURL: URL, table: String, column: String) throws -> [String] {
        let database = try openRawDatabase(databaseURL)
        defer { sqlite3_close(database) }
        let statement = try prepareRaw(
            database,
            "SELECT \(column) FROM \(table) ORDER BY \(column) ASC"
        )
        defer { sqlite3_finalize(statement) }

        var values: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 5)
            }
            let rawValue = try XCTUnwrap(sqlite3_column_text(statement, 0))
            values.append(String(cString: rawValue))
        }
        return values
    }

    private func rawIntValues(in databaseURL: URL, table: String, column: String) throws -> [Int] {
        let database = try openRawDatabase(databaseURL)
        defer { sqlite3_close(database) }
        let statement = try prepareRaw(
            database,
            "SELECT \(column) FROM \(table) ORDER BY \(column) ASC"
        )
        defer { sqlite3_finalize(statement) }

        var values: [Int] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 6)
            }
            values.append(Int(sqlite3_column_int64(statement, 0)))
        }
        return values
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
                throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 6)
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

    private func ftsTotalRowCount(in databaseURL: URL) throws -> Int {
        let database = try openRawDatabase(databaseURL)
        defer { sqlite3_close(database) }
        let statement = try prepareRaw(
            database,
            "SELECT COUNT(*) FROM runtime_document_index_chunk_fts"
        )
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw NSError(domain: "SQLiteRuntimeDocumentIndexStoreTests", code: 7)
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
