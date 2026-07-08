import XCTest
@testable import CompanionCore
@testable import DocumentIngestion

final class RuntimeDocumentIndexStoreTests: XCTestCase {
    func testIndexesChunksWithStableIDsAndSourceLabels() throws {
        let result = try ingestedDocument(
            fileName: "runtime-guide.md",
            text: [
                "Runtime document indexing keeps user-approved file text on the host.",
                "Stable chunk identifiers prepare later retrieval without protocol exposure."
            ].joined(separator: " ")
        )
        let store = RuntimeDocumentIndexStore()

        let firstRecord = store.replaceDocument(result: result)
        let firstChunks = store.chunks(for: firstRecord.id)
        let secondRecord = store.replaceDocument(result: result)
        let secondChunks = store.chunks(for: secondRecord.id)

        XCTAssertEqual(firstRecord.id, secondRecord.id)
        XCTAssertEqual(firstRecord.contentFingerprint, secondRecord.contentFingerprint)
        XCTAssertEqual(firstChunks.map(\.id), secondChunks.map(\.id))
        XCTAssertEqual(firstChunks.map(\.documentDisplayName), Array(repeating: "runtime-guide.md", count: firstChunks.count))
        XCTAssertEqual(firstChunks.map(\.documentMimeType), Array(repeating: "text/markdown", count: firstChunks.count))
        XCTAssertEqual(firstRecord.chunkCount, result.chunks.count)
        XCTAssertEqual(firstRecord.quality, .chunked)
    }

    func testLexicalQueryRanksAndReturnsBoundedSnippets() throws {
        let store = RuntimeDocumentIndexStore()
        let primary = try ingestedDocument(
            fileName: "retrieval.md",
            text: [
                "Runtime retrieval planning starts with lexical retrieval over approved chunks.",
                "Retrieval snippets stay bounded before embeddings are introduced."
            ].joined(separator: " ")
        )
        let secondary = try ingestedDocument(
            fileName: "memory.md",
            text: "Runtime memory search is related but has fewer retrieval matches."
        )

        _ = store.replaceDocument(result: secondary, documentID: "memory")
        _ = store.replaceDocument(result: primary, documentID: "retrieval")
        let results = store.query("retrieval runtime", limit: 3, maxSnippetCharacters: 64)

        XCTAssertGreaterThanOrEqual(results.count, 2)
        XCTAssertEqual(results.first?.document.id, "retrieval")
        XCTAssertGreaterThan(results[0].rank, results[1].rank)
        XCTAssertTrue(results.allSatisfy { !$0.snippet.isEmpty })
        XCTAssertTrue(results.allSatisfy { $0.snippet.count <= 64 })
        XCTAssertTrue(results.first?.matchedTerms.contains("retrieval") == true)
        XCTAssertTrue(results.first?.matchedTerms.contains("runtime") == true)
    }

    func testListsDocumentsAsBoundedCatalog() throws {
        let store = RuntimeDocumentIndexStore()
        let alpha = try ingestedDocument(fileName: "alpha.md", text: "Alpha catalog content should stay out of document listings.")
        let gamma = try ingestedDocument(fileName: "gamma.md", text: "Gamma catalog content should stay out of document listings.")
        let zeta = try ingestedDocument(fileName: "zeta.md", text: "Zeta catalog content will be replaced.")
        let beta = try ingestedDocument(fileName: "beta.md", text: "Beta catalog replacement content stays host-local.")

        _ = store.replaceDocument(result: gamma, documentID: "gamma")
        _ = store.replaceDocument(result: alpha, documentID: "alpha")
        _ = store.replaceDocument(result: zeta, documentID: "beta")

        XCTAssertEqual(store.documents().map(\.id), ["alpha", "gamma", "beta"])
        XCTAssertEqual(store.documents(limit: 2).map(\.id), ["alpha", "gamma"])
        XCTAssertEqual(store.documents(limit: 0), [])

        _ = store.replaceDocument(result: beta, documentID: "beta")
        store.deleteDocument(id: "alpha")

        let catalog = store.documents()
        XCTAssertEqual(catalog.map(\.id), ["beta", "gamma"])
        XCTAssertEqual(catalog.first?.displayName, "beta.md")
        XCTAssertFalse(String(describing: catalog).contains("Beta catalog replacement content"))
        XCTAssertFalse(String(describing: catalog).contains("Gamma catalog content"))
    }

    func testSummarizesDocumentIndexWithoutContentOrFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
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

        _ = store.replaceDocument(result: chunked, documentID: "chunked")
        _ = store.replaceDocument(result: single, documentID: "single")
        _ = store.replaceDocument(result: empty, documentID: "empty")

        let summary = store.summary()
        XCTAssertEqual(summary.documentCount, 3)
        XCTAssertEqual(summary.chunkCount, chunked.chunks.count + single.chunks.count + empty.chunks.count)
        XCTAssertEqual(summary.extractedCharacterCount, chunked.summary.extractedCharacterCount + single.summary.extractedCharacterCount + empty.summary.extractedCharacterCount)
        XCTAssertEqual(summary.qualityCounts[.chunked], 1)
        XCTAssertEqual(summary.qualityCounts[.singleChunk], 1)
        XCTAssertEqual(summary.qualityCounts[.noUsableText], 1)
        XCTAssertFalse(String(describing: summary).contains("summary content"))
        XCTAssertFalse(String(describing: summary).contains("sourcePath"))
        XCTAssertFalse(String(describing: summary).contains("workspaceID"))
        XCTAssertFalse(String(describing: summary).contains("retrieval_context"))
        XCTAssertFalse(String(describing: summary).contains("embedding"))

        _ = store.replaceDocument(result: single, documentID: "chunked")
        store.deleteDocument(id: "empty")

        let updated = store.summary()
        XCTAssertEqual(updated.documentCount, 2)
        XCTAssertEqual(updated.qualityCounts[.chunked], nil)
        XCTAssertEqual(updated.qualityCounts[.singleChunk], 2)
        XCTAssertEqual(updated.qualityCounts[.noUsableText], nil)
    }

    func testFindsDocumentsByContentFingerprintWithoutContentOrFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let duplicateText = "Duplicate approved document text should stay out of fingerprint lookup rows."
        let copyB = try ingestedDocument(fileName: "copy-b.md", text: duplicateText)
        let copyA = try ingestedDocument(fileName: "copy-a.md", text: duplicateText)
        let unrelated = try ingestedDocument(
            fileName: "unrelated.md",
            text: "Unrelated document text must not share the same content fingerprint."
        )
        let replacement = try ingestedDocument(
            fileName: "copy-a.md",
            text: "Replacement text should move copy-a to a new content fingerprint."
        )
        let duplicateFingerprint = RuntimeDocumentIndexStore.stableContentFingerprint(for: copyB)
        let replacementFingerprint = RuntimeDocumentIndexStore.stableContentFingerprint(for: replacement)

        XCTAssertEqual(duplicateFingerprint, RuntimeDocumentIndexStore.stableContentFingerprint(for: copyA))
        XCTAssertNotEqual(duplicateFingerprint, RuntimeDocumentIndexStore.stableContentFingerprint(for: unrelated))

        _ = store.replaceDocument(result: copyB, documentID: "copy-b")
        _ = store.replaceDocument(result: unrelated, documentID: "unrelated")
        _ = store.replaceDocument(result: copyA, documentID: "copy-a")

        let matches = store.documents(matchingContentFingerprint: duplicateFingerprint)
        XCTAssertEqual(matches.map(\.id), ["copy-a", "copy-b"])
        XCTAssertEqual(store.documents(matchingContentFingerprint: duplicateFingerprint, limit: 1).map(\.id), ["copy-a"])
        XCTAssertEqual(store.documents(matchingContentFingerprint: "missing"), [])
        XCTAssertEqual(store.documents(matchingContentFingerprint: ""), [])
        XCTAssertFalse(String(describing: matches).contains(duplicateText))
        XCTAssertFalse(String(describing: matches).contains("sourcePath"))
        XCTAssertFalse(String(describing: matches).contains("workspaceID"))
        XCTAssertFalse(String(describing: matches).contains("retrieval_context"))
        XCTAssertFalse(String(describing: matches).contains("embedding"))

        _ = store.replaceDocument(result: replacement, documentID: "copy-a")
        XCTAssertEqual(store.documents(matchingContentFingerprint: duplicateFingerprint).map(\.id), ["copy-b"])
        XCTAssertEqual(store.documents(matchingContentFingerprint: replacementFingerprint).map(\.id), ["copy-a"])

        store.deleteDocument(id: "copy-b")
        XCTAssertEqual(store.documents(matchingContentFingerprint: duplicateFingerprint), [])
    }

    func testListsDocumentsByQualityWithoutContentOrFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let bodySentinel = "PRIVATE_QUALITY_BODY_SHOULD_NOT_APPEAR"
        let chunked = try ingestedDocument(
            fileName: "chunked.md",
            text: [
                "\(bodySentinel) starts a quality-filtered catalog review.",
                "Additional sentence text forces the chunking policy to split safely.",
                "The quality catalog should identify rows without exposing body text."
            ].joined(separator: " ")
        )
        let single = try ingestedDocument(fileName: "single.md", text: "Single chunk quality content remains private.")
        let empty = try ingestedDocument(fileName: "empty.md", text: "   ")

        _ = store.replaceDocument(result: single, documentID: "single")
        _ = store.replaceDocument(result: chunked, documentID: "chunked")
        _ = store.replaceDocument(result: empty, documentID: "empty")

        let chunkedCatalog = store.documents(matchingQuality: .chunked)
        let singleCatalog = store.documents(matchingQuality: .singleChunk)
        XCTAssertEqual(chunkedCatalog.map(\.id), ["chunked"])
        XCTAssertEqual(singleCatalog.map(\.id), ["single"])
        XCTAssertEqual(store.documents(matchingQuality: .noUsableText).map(\.id), ["empty"])
        XCTAssertEqual(store.documents(matchingQuality: .singleChunk, limit: 0), [])
        XCTAssertFalse(String(describing: chunkedCatalog + singleCatalog).contains(bodySentinel))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("sourcePath"))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("workspaceID"))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("retrieval_context"))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("embedding"))
        XCTAssertFalse(String(describing: chunkedCatalog).contains("citation"))

        _ = store.replaceDocument(result: single, documentID: "chunked")
        store.deleteDocument(id: "empty")

        XCTAssertEqual(store.documents(matchingQuality: .chunked), [])
        XCTAssertEqual(store.documents(matchingQuality: .singleChunk).map(\.id), ["chunked", "single"])
        XCTAssertEqual(store.documents(matchingQuality: .noUsableText), [])
    }

    func testReplacingDocumentRemovesOldChunks() throws {
        let store = RuntimeDocumentIndexStore()
        let first = try ingestedDocument(fileName: "notes.txt", mimeType: "text/plain", text: "obsolete alpha content")
        let replacement = try ingestedDocument(fileName: "notes.txt", mimeType: "text/plain", text: "fresh beta content")

        _ = store.replaceDocument(result: first, documentID: "notes")
        XCTAssertEqual(store.query("obsolete").count, 1)

        let record = store.replaceDocument(result: replacement, documentID: "notes")

        XCTAssertEqual(record.id, "notes")
        XCTAssertEqual(store.query("obsolete"), [])
        XCTAssertEqual(store.query("fresh").single?.document.id, "notes")
        XCTAssertEqual(store.chunks(for: "notes").map(\.text).joined(separator: " "), "fresh beta content")
    }

    func testIndexRecordsDoNotCarryWorkspaceSourcePathOrRetrievalMetadata() throws {
        let result = try ingestedDocument(
            fileName: "safe-summary.txt",
            mimeType: "text/plain",
            text: "Index records keep display names and structural chunk offsets only."
        )
        let store = RuntimeDocumentIndexStore()

        let record = store.replaceDocument(result: result, documentID: "safe")
        let chunk = try XCTUnwrap(store.chunks(for: "safe").single)
        let forbiddenLabels = Set([
            "sourcePath",
            "projectID",
            "projectId",
            "workspaceID",
            "workspaceId",
            "retrievalContext",
            "embedding",
            "embeddingModelID",
            "embeddingModelId"
        ])

        XCTAssertTrue(Set(Mirror(reflecting: record).children.compactMap(\.label)).isDisjoint(with: forbiddenLabels))
        XCTAssertTrue(Set(Mirror(reflecting: chunk).children.compactMap(\.label)).isDisjoint(with: forbiddenLabels))
        XCTAssertFalse(String(describing: record).contains("/tmp/"))
        XCTAssertFalse(String(describing: chunk).contains("/tmp/"))
        XCTAssertFalse(String(describing: record).contains("retrieval_context"))
        XCTAssertFalse(String(describing: chunk).contains("project_id"))
    }

    func testDeletedDocumentsAreNotReturned() throws {
        let store = RuntimeDocumentIndexStore()
        let result = try ingestedDocument(fileName: "delete-me.txt", mimeType: "text/plain", text: "temporary indexed content")
        _ = store.replaceDocument(result: result, documentID: "temporary")

        XCTAssertEqual(store.query("temporary").count, 1)

        store.deleteDocument(id: "temporary")

        XCTAssertNil(store.document(id: "temporary"))
        XCTAssertEqual(store.chunks(for: "temporary"), [])
        XCTAssertEqual(store.query("temporary"), [])
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
}

private extension Array {
    var single: Element? {
        count == 1 ? self[0] : nil
    }
}
