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

    func testRequestedDocumentIDsUseStoreOwnedCanonicalityGuards() throws {
        let store = RuntimeDocumentIndexStore()
        let blankResult = try ingestedDocument(
            fileName: "blank-id.md",
            text: "Blank requested document ids must not become runtime index rows."
        )
        let customResult = try ingestedDocument(
            fileName: "custom-id.md",
            text: "Whitespace-mutated requested document ids are normalized before storage."
        )
        let oversizedResult = try ingestedDocument(
            fileName: "oversized-id.md",
            text: "Oversized requested document ids must fall back to deterministic stable ids."
        )

        let blankFallbackID = RuntimeDocumentIndexStore.stableDocumentID(for: blankResult)
        let blankRecord = store.replaceDocument(result: blankResult, documentID: " \n\t ")

        XCTAssertEqual(blankRecord.id, blankFallbackID)
        XCTAssertEqual(store.document(id: blankFallbackID), blankRecord)
        XCTAssertNil(store.document(id: ""))
        XCTAssertEqual(store.chunks(for: ""), [])
        XCTAssertEqual(store.chunkSummaries(for: " \n\t "), [])
        XCTAssertFalse(store.documents().map(\.id).contains(""))

        let customRecord = store.replaceDocument(result: customResult, documentID: "  custom-doc  \n")
        XCTAssertEqual(customRecord.id, "custom-doc")
        XCTAssertEqual(store.document(id: " custom-doc "), customRecord)
        XCTAssertEqual(Set(store.chunks(for: " custom-doc ").map(\.documentID)), Set(["custom-doc"]))
        XCTAssertEqual(Set(store.chunkSummaries(for: " custom-doc ").map(\.documentID)), Set(["custom-doc"]))
        XCTAssertFalse(store.documents().map(\.id).contains("  custom-doc  \n"))

        let oversizedRequestedID = String(repeating: "x", count: runtimeDocumentIndexDocumentIDCharacterLimitCeiling + 1)
        let oversizedFallbackID = RuntimeDocumentIndexStore.stableDocumentID(for: oversizedResult)
        let oversizedRecord = store.replaceDocument(result: oversizedResult, documentID: oversizedRequestedID)
        XCTAssertEqual(oversizedRecord.id, oversizedFallbackID)
        XCTAssertNil(store.document(id: oversizedRequestedID))
        XCTAssertFalse(store.documents().map(\.id).contains(oversizedRequestedID))

        store.deleteDocument(id: " custom-doc ")
        XCTAssertNil(store.document(id: "custom-doc"))
        XCTAssertEqual(store.chunks(for: "custom-doc"), [])
        XCTAssertEqual(store.query("Whitespace-mutated"), [])
        XCTAssertEqual(store.query("Blank").single?.document.id, blankFallbackID)
        XCTAssertEqual(store.query("Oversized").single?.document.id, oversizedFallbackID)
    }

    func testRejectsControlCharacterRequestedDocumentIDsBeforeStorageAndLookup() throws {
        let store = RuntimeDocumentIndexStore()
        let controlRequestedID = "control\u{0000}doc"
        let controlResult = try ingestedDocument(
            fileName: "control-id.md",
            text: "Control-character requested document ids must not become runtime index rows."
        )
        let fallbackID = RuntimeDocumentIndexStore.stableDocumentID(for: controlResult)

        XCTAssertNil(runtimeDocumentIndexCanonicalDocumentID(controlRequestedID))

        let stored = store.replaceDocument(result: controlResult, documentID: controlRequestedID)
        XCTAssertEqual(stored.id, fallbackID)
        XCTAssertEqual(store.document(id: fallbackID), stored)
        XCTAssertNil(store.document(id: controlRequestedID))
        XCTAssertEqual(store.chunks(for: controlRequestedID), [])
        XCTAssertEqual(store.chunkSummaries(for: controlRequestedID), [])
        XCTAssertFalse(store.documents().map(\.id).contains(controlRequestedID))
        XCTAssertEqual(Set(store.chunks(for: fallbackID).map(\.documentID)), [fallbackID])
        XCTAssertEqual(Set(store.chunkSummaries(for: fallbackID).map(\.documentID)), [fallbackID])
        XCTAssertEqual(store.query("Control-character").single?.document.id, fallbackID)

        store.deleteDocument(id: controlRequestedID)
        XCTAssertEqual(store.document(id: fallbackID), stored)
        XCTAssertEqual(store.query("Control-character").single?.document.id, fallbackID)
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

    func testLexicalQueryMatchesSubstringInsideTokens() throws {
        let store = RuntimeDocumentIndexStore()
        let result = try ingestedDocument(
            fileName: "runtime.md",
            text: "Runtime substring matching remains part of the lexical document index contract."
        )
        _ = store.replaceDocument(result: result, documentID: "runtime")

        let results = store.query("time", limit: 5, maxSnippetCharacters: 80)

        XCTAssertEqual(results.single?.document.id, "runtime")
        XCTAssertEqual(results.single?.matchedTerms, ["time"])
        XCTAssertTrue(results.single?.snippet.lowercased().contains("runtime") == true)
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

    func testListsDocumentsByDisplayNameWithoutContentOrFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let bodySentinel = "PRIVATE_DISPLAY_NAME_BODY_SHOULD_NOT_APPEAR"
        let duplicateB = try ingestedDocument(fileName: "shared-name.md", text: "\(bodySentinel) duplicate body remains private.")
        let duplicateA = try ingestedDocument(fileName: "shared-name.md", text: "Second duplicate body remains private.")
        let unrelated = try ingestedDocument(fileName: "other-name.md", text: "Unrelated body remains private.")
        let replacement = try ingestedDocument(fileName: "renamed.md", text: "Replacement body remains private.")

        _ = store.replaceDocument(result: duplicateB, documentID: "duplicate-b")
        _ = store.replaceDocument(result: unrelated, documentID: "unrelated")
        _ = store.replaceDocument(result: duplicateA, documentID: "duplicate-a")

        let matches = store.documents(matchingDisplayName: "shared-name.md")
        XCTAssertEqual(matches.map(\.id), ["duplicate-a", "duplicate-b"])
        XCTAssertEqual(store.documents(matchingDisplayName: "shared-name.md", limit: 1).map(\.id), ["duplicate-a"])
        XCTAssertEqual(store.documents(matchingDisplayName: "other-name.md").map(\.id), ["unrelated"])
        XCTAssertEqual(store.documents(matchingDisplayName: "missing.md"), [])
        XCTAssertEqual(store.documents(matchingDisplayName: ""), [])
        XCTAssertEqual(store.documents(matchingDisplayName: "shared-name.md", limit: 0), [])
        XCTAssertFalse(String(describing: matches).contains(bodySentinel))
        XCTAssertFalse(String(describing: matches).contains("sourcePath"))
        XCTAssertFalse(String(describing: matches).contains("workspaceID"))
        XCTAssertFalse(String(describing: matches).contains("retrieval_context"))
        XCTAssertFalse(String(describing: matches).contains("embedding"))
        XCTAssertFalse(String(describing: matches).contains("citation"))

        _ = store.replaceDocument(result: replacement, documentID: "duplicate-b")
        store.deleteDocument(id: "duplicate-a")

        XCTAssertEqual(store.documents(matchingDisplayName: "shared-name.md"), [])
        XCTAssertEqual(store.documents(matchingDisplayName: "renamed.md").map(\.id), ["duplicate-b"])
    }

    func testDeleteDocumentsByDisplayNameClearsMatchingRowsWithoutFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let sharedSentinel = "SharedDisplayNameDeleteSentinel"
        let unrelatedSentinel = "UnrelatedDisplayNameDeleteSentinel"
        let pdfSentinel = "PdfDisplayNameDeleteSentinel"
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

        _ = store.replaceDocument(result: duplicateB, documentID: "duplicate-b")
        _ = store.replaceDocument(result: unrelated, documentID: "unrelated")
        _ = store.replaceDocument(result: pdf, documentID: "pdf")
        _ = store.replaceDocument(result: duplicateA, documentID: "duplicate-a")

        XCTAssertEqual(store.documents(matchingDisplayName: "shared-name.md").map(\.id), ["duplicate-a", "duplicate-b"])
        XCTAssertEqual(Set(store.query("cleanup").map(\.document.id)), Set(["duplicate-a", "duplicate-b", "pdf", "unrelated"]))
        XCTAssertEqual(store.summary().documentCount, 4)

        store.deleteDocuments(matchingDisplayName: "")
        store.deleteDocuments(matchingDisplayName: overlongDisplayName)
        store.deleteDocuments(matchingDisplayName: "Shared-name.md")
        XCTAssertEqual(Set(store.documents().map(\.id)), Set(["duplicate-a", "duplicate-b", "pdf", "unrelated"]))

        store.deleteDocuments(matchingDisplayName: " /Users/private/shared-name.md\n")

        XCTAssertNil(store.document(id: "duplicate-a"))
        XCTAssertNil(store.document(id: "duplicate-b"))
        XCTAssertNotNil(store.document(id: "unrelated"))
        XCTAssertNotNil(store.document(id: "pdf"))
        XCTAssertEqual(store.chunks(for: "duplicate-a"), [])
        XCTAssertEqual(store.chunks(for: "duplicate-b"), [])
        XCTAssertFalse(store.chunks(for: "unrelated").isEmpty)
        XCTAssertFalse(store.chunks(for: "pdf").isEmpty)
        XCTAssertEqual(store.chunkSummaries(for: "duplicate-a"), [])
        XCTAssertEqual(store.chunkSummaries(for: "duplicate-b"), [])
        XCTAssertFalse(store.chunkSummaries(for: "unrelated").isEmpty)
        XCTAssertEqual(store.documents(matchingDisplayName: "shared-name.md"), [])
        XCTAssertEqual(store.documents().map(\.id), ["pdf", "unrelated"])
        XCTAssertEqual(store.query(sharedSentinel), [])
        XCTAssertEqual(store.query(unrelatedSentinel).single?.document.id, "unrelated")
        XCTAssertEqual(store.query(pdfSentinel).single?.document.id, "pdf")
        XCTAssertEqual(store.summary().documentCount, 2)
        XCTAssertEqual(store.summary().chunkCount, unrelated.chunks.count + pdf.chunks.count)
        XCTAssertEqual(
            store.summary().qualityCounts,
            Dictionary([unrelated.summary.quality, pdf.summary.quality].map { ($0, 1) }, uniquingKeysWith: +)
        )
        XCTAssertFalse(String(describing: store.documents()).contains(sharedSentinel))
        XCTAssertFalse(String(describing: store.documents()).contains("sourcePath"))
        XCTAssertFalse(String(describing: store.summary()).contains("projectID"))
        XCTAssertFalse(String(describing: store.summary()).contains("workspaceID"))
        XCTAssertFalse(String(describing: store.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: store.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: store.summary()).contains("citation"))
        XCTAssertFalse(String(describing: store.summary()).contains("trustedSource"))

        store.deleteDocuments(matchingDisplayName: "shared-name.md")
        XCTAssertEqual(store.documents().map(\.id), ["pdf", "unrelated"])
    }

    func testNormalizesDisplayNamesBeforeStorageAndLookup() throws {
        let store = RuntimeDocumentIndexStore()
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
        XCTAssertEqual(runtimeDocumentIndexCanonicalDisplayName(" C:\\Users\\private\\report.md\n"), "report.md")

        let storedPath = store.replaceDocument(result: pathResult, documentID: "path-report")
        XCTAssertEqual(storedPath.displayName, "report.md")
        XCTAssertEqual(store.documents(matchingDisplayName: " /Users/private/Documents/report.md\n").map(\.id), ["path-report"])
        XCTAssertEqual(store.documents(matchingDisplayName: "C:\\Users\\private\\report.md").map(\.id), ["path-report"])
        XCTAssertEqual(store.documents(matchingDisplayName: "/Users/private/Documents/summary-secret.md"), [])
        XCTAssertEqual(store.documents(matchingDisplayName: "/Users/private/Documents/chunk-secret.md"), [])
        XCTAssertEqual(Set(store.chunks(for: "path-report").map(\.documentDisplayName)), ["report.md"])
        XCTAssertEqual(Set(store.chunkSummaries(for: "path-report").map(\.documentDisplayName)), ["report.md"])
        XCTAssertFalse(String(describing: store.documents()).contains("/Users/private"))
        XCTAssertFalse(String(describing: store.chunks(for: "path-report")).contains("summary-secret"))
        XCTAssertFalse(String(describing: store.chunks(for: "path-report")).contains("chunk-secret"))

        var fallbackResult = try ingestedDocument(
            fileName: "fallback.md",
            text: "Fallback display names must not preserve blank or oversized source labels."
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

        let storedFallback = store.replaceDocument(result: fallbackResult, documentID: "fallback")
        XCTAssertEqual(storedFallback.displayName, runtimeDocumentIndexUnknownDisplayName)
        XCTAssertEqual(store.documents(matchingDisplayName: runtimeDocumentIndexUnknownDisplayName).map(\.id), ["fallback"])
        XCTAssertEqual(Set(store.chunks(for: "fallback").map(\.documentDisplayName)), [runtimeDocumentIndexUnknownDisplayName])
        XCTAssertEqual(store.documents(matchingDisplayName: String(
            repeating: "x",
            count: runtimeDocumentIndexDisplayNameCharacterLimitCeiling + 1
        )), [])
    }

    func testRejectsControlCharacterDisplayNamesBeforeStorageAndLookup() throws {
        let store = RuntimeDocumentIndexStore()
        let forgedDisplayName = "runtime\u{0000}secret.md"
        var controlResult = try ingestedDocument(
            fileName: "control.md",
            text: "Control-character display names must not persist in runtime document index rows."
        )
        controlResult.document.fileName = forgedDisplayName
        controlResult.summary.documentFileName = "summary\u{0000}secret.md"
        controlResult.chunks = controlResult.chunks.map { chunk in
            var chunk = chunk
            chunk.documentFileName = "chunk\u{0000}secret.md"
            return chunk
        }

        XCTAssertNil(runtimeDocumentIndexCanonicalDisplayName(forgedDisplayName))

        let storedControl = store.replaceDocument(result: controlResult, documentID: "control")
        XCTAssertEqual(storedControl.displayName, runtimeDocumentIndexUnknownDisplayName)
        XCTAssertEqual(store.documents(matchingDisplayName: forgedDisplayName), [])
        XCTAssertEqual(store.documents(matchingDisplayName: runtimeDocumentIndexUnknownDisplayName).map(\.id), ["control"])
        XCTAssertEqual(Set(store.chunks(for: "control").map(\.documentDisplayName)), [runtimeDocumentIndexUnknownDisplayName])
        XCTAssertEqual(
            Set(store.chunkSummaries(for: "control").map(\.documentDisplayName)),
            [runtimeDocumentIndexUnknownDisplayName]
        )
        XCTAssertFalse(String(describing: store.documents()).contains("runtime"))
        XCTAssertFalse(String(describing: store.chunks(for: "control")).contains("secret"))
    }

    func testNormalizesChunkEnvelopeBeforeStorageAndLookup() throws {
        let store = RuntimeDocumentIndexStore()
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

        let expectedChunks = runtimeDocumentIndexChunks(for: canonical, documentID: "chunk-envelope")
        XCTAssertNotEqual(forged.chunks.map(\.index), expectedChunks.map(\.chunkIndex))
        XCTAssertNotEqual(forged.chunks.map(\.startCharacterOffset), expectedChunks.map(\.startCharacterOffset))
        XCTAssertNotEqual(forged.chunks.map(\.endCharacterOffset), expectedChunks.map(\.endCharacterOffset))

        let stored = store.replaceDocument(result: forged, documentID: "chunk-envelope")
        let chunks = store.chunks(for: stored.id)
        let summaries = store.chunkSummaries(for: stored.id)

        XCTAssertEqual(chunks, expectedChunks)
        XCTAssertEqual(chunks.map(\.chunkIndex), Array(0..<canonical.chunks.count))
        XCTAssertEqual(chunks.map(\.id), expectedChunks.map(\.id))
        XCTAssertEqual(summaries.map(\.chunkIndex), chunks.map(\.chunkIndex))
        XCTAssertEqual(summaries.map(\.startCharacterOffset), chunks.map(\.startCharacterOffset))
        XCTAssertEqual(summaries.map(\.endCharacterOffset), chunks.map(\.endCharacterOffset))
        XCTAssertFalse(chunks.map(\.chunkIndex).contains(999))
        XCTAssertFalse(chunks.map(\.chunkIndex).contains(-7))
        XCTAssertFalse(chunks.map(\.startCharacterOffset).contains(-50))
        XCTAssertFalse(chunks.map(\.endCharacterOffset).contains(-1))

        var fallback = try ingestedDocument(
            fileName: "fallback-envelope.md",
            text: "Fallback chunk envelope offsets stay bounded even for forged direct-ingestion chunks."
        )
        let fallbackText = "FORGED_CHUNK_TEXT_NOT_IN_DOCUMENT"
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

        _ = store.replaceDocument(result: fallback, documentID: "fallback-envelope")
        let fallbackChunk = try XCTUnwrap(store.chunks(for: "fallback-envelope").single)
        XCTAssertEqual(fallbackChunk.chunkIndex, 0)
        XCTAssertEqual(fallbackChunk.startCharacterOffset, 0)
        XCTAssertEqual(fallbackChunk.endCharacterOffset, min(fallbackText.count, fallbackDocumentCharacterCount))
        XCTAssertFalse(fallbackChunk.startCharacterOffset < 0)
        XCTAssertLessThanOrEqual(fallbackChunk.endCharacterOffset, fallbackDocumentCharacterCount)
    }

    func testSummarizesChunksForDocumentWithoutTextOrFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let bodySentinel = "PRIVATE_CHUNK_SUMMARY_BODY_SHOULD_NOT_APPEAR"
        let chunked = try ingestedDocument(
            fileName: "chunk-review.md",
            text: [
                "\(bodySentinel) starts the first indexed chunk for maintenance.",
                "The second sentence forces multiple chunks for bounded summary review.",
                "The third sentence keeps chunk offsets and lengths useful."
            ].joined(separator: " ")
        )
        let replacement = try ingestedDocument(
            fileName: "chunk-review.md",
            text: "Replacement chunk summary body remains private."
        )

        _ = store.replaceDocument(result: chunked, documentID: "chunk-review")
        let chunks = store.chunks(for: "chunk-review")
        let summaries = store.chunkSummaries(for: "chunk-review")

        XCTAssertGreaterThan(chunks.count, 1)
        XCTAssertEqual(summaries.count, chunks.count)
        XCTAssertEqual(summaries.map(\.chunkIndex), chunks.map(\.chunkIndex))
        XCTAssertEqual(summaries.map(\.startCharacterOffset), chunks.map(\.startCharacterOffset))
        XCTAssertEqual(summaries.map(\.endCharacterOffset), chunks.map(\.endCharacterOffset))
        XCTAssertEqual(summaries.map(\.characterCount), chunks.map { $0.text.count })
        XCTAssertEqual(summaries.map(\.documentDisplayName), Array(repeating: "chunk-review.md", count: summaries.count))
        XCTAssertEqual(store.chunkSummaries(for: "chunk-review", limit: 1), Array(summaries.prefix(1)))
        XCTAssertEqual(store.chunkSummaries(for: "missing"), [])
        XCTAssertEqual(store.chunkSummaries(for: ""), [])
        XCTAssertEqual(store.chunkSummaries(for: "chunk-review", limit: 0), [])
        XCTAssertFalse(String(describing: summaries).contains(bodySentinel))
        XCTAssertFalse(String(describing: summaries).contains("sourcePath"))
        XCTAssertFalse(String(describing: summaries).contains("projectID"))
        XCTAssertFalse(String(describing: summaries).contains("workspaceID"))
        XCTAssertFalse(String(describing: summaries).contains("retrieval_context"))
        XCTAssertFalse(String(describing: summaries).contains("embedding"))
        XCTAssertFalse(String(describing: summaries).contains("citation"))
        XCTAssertFalse(String(describing: summaries).contains("trustedSource"))

        _ = store.replaceDocument(result: replacement, documentID: "chunk-review")
        let updated = store.chunkSummaries(for: "chunk-review")
        XCTAssertEqual(updated.count, replacement.chunks.count)
        XCTAssertEqual(updated.single?.characterCount, replacement.chunks.single?.text.count)

        store.deleteDocument(id: "chunk-review")
        XCTAssertEqual(store.chunkSummaries(for: "chunk-review"), [])
    }

    func testChunkReadsApplyStoreOwnedLimitCeiling() throws {
        let store = RuntimeDocumentIndexStore()
        let manyChunks = try ingestedDocument(
            fileName: "chunk-read.md",
            text: chunkCeilingText(minimumChunks: runtimeDocumentIndexChunkReadLimitCeiling + 5)
        )
        let replacement = try ingestedDocument(
            fileName: "chunk-read.md",
            text: "Replacement chunk read content stays bounded."
        )

        _ = store.replaceDocument(result: manyChunks, documentID: "chunk-read")
        let limitedChunks = store.chunks(
            for: "chunk-read",
            limit: runtimeDocumentIndexChunkReadLimitCeiling + 50
        )

        XCTAssertEqual(limitedChunks.count, runtimeDocumentIndexChunkReadLimitCeiling)
        XCTAssertEqual(limitedChunks.map(\.chunkIndex), Array(0..<runtimeDocumentIndexChunkReadLimitCeiling))
        XCTAssertEqual(store.chunks(for: "chunk-read", limit: 1).map(\.chunkIndex), [0])
        XCTAssertEqual(store.chunks(for: "chunk-read", limit: 0), [])
        XCTAssertEqual(store.chunks(for: ""), [])
        XCTAssertFalse(String(describing: limitedChunks).contains("sourcePath"))
        XCTAssertFalse(String(describing: limitedChunks).contains("projectID"))
        XCTAssertFalse(String(describing: limitedChunks).contains("workspaceID"))
        XCTAssertFalse(String(describing: limitedChunks).contains("retrieval_context"))
        XCTAssertFalse(String(describing: limitedChunks).contains("embedding"))
        XCTAssertFalse(String(describing: limitedChunks).contains("citation"))
        XCTAssertFalse(String(describing: limitedChunks).contains("trustedSource"))

        _ = store.replaceDocument(result: replacement, documentID: "chunk-read")
        let replacementChunks = store.chunks(
            for: "chunk-read",
            limit: runtimeDocumentIndexChunkReadLimitCeiling + 50
        )
        XCTAssertEqual(replacementChunks.count, replacement.chunks.count)
        XCTAssertEqual(replacementChunks.map(\.text).joined(separator: " "), replacement.chunks.map(\.text).joined(separator: " "))

        store.deleteDocument(id: "chunk-read")
        XCTAssertEqual(store.chunks(for: "chunk-read", limit: runtimeDocumentIndexChunkReadLimitCeiling + 50), [])
    }

    func testCatalogChunkSummariesAndQueryApplyStoreOwnedLimitCeilings() throws {
        let store = RuntimeDocumentIndexStore()
        let totalDocuments = max(runtimeDocumentIndexCatalogLimitCeiling, runtimeDocumentIndexQueryLimitCeiling) + 5

        for index in 0..<totalDocuments {
            let id = String(format: "ceiling-%03d", index)
            let result = try ingestedDocument(
                fileName: "\(id).md",
                text: "Ceiling query term \(index) remains private while metadata limits are enforced."
            )
            _ = store.replaceDocument(result: result, documentID: id)
        }

        XCTAssertEqual(store.documents(limit: totalDocuments).count, runtimeDocumentIndexCatalogLimitCeiling)
        XCTAssertEqual(
            store.documents(matchingMimeType: "text/markdown", limit: totalDocuments).count,
            runtimeDocumentIndexCatalogLimitCeiling
        )
        XCTAssertEqual(
            store.documents(matchingQuality: .singleChunk, limit: totalDocuments).count,
            runtimeDocumentIndexCatalogLimitCeiling
        )
        XCTAssertEqual(store.query("ceiling", limit: totalDocuments).count, runtimeDocumentIndexQueryLimitCeiling)

        let manyChunks = try ingestedDocument(
            fileName: "many-chunks.md",
            text: chunkCeilingText(minimumChunks: runtimeDocumentIndexChunkSummaryLimitCeiling + 5)
        )
        _ = store.replaceDocument(result: manyChunks, documentID: "many-chunks")
        XCTAssertGreaterThan(store.chunks(for: "many-chunks").count, runtimeDocumentIndexChunkSummaryLimitCeiling)
        XCTAssertEqual(
            store.chunkSummaries(
                for: "many-chunks",
                limit: runtimeDocumentIndexChunkSummaryLimitCeiling + 50
            ).count,
            runtimeDocumentIndexChunkSummaryLimitCeiling
        )

        let document = RuntimeDocumentIndexDocument(
            id: "long-snippet",
            displayName: "long-snippet.md",
            mimeType: "text/markdown",
            contentFingerprint: "fingerprint",
            extractedCharacterCount: runtimeDocumentIndexSnippetCharacterLimitCeiling * 10,
            chunkCount: 1,
            quality: .singleChunk
        )
        let chunk = RuntimeDocumentIndexChunk(
            id: "long-snippet-chunk",
            documentID: document.id,
            documentDisplayName: document.displayName,
            documentMimeType: document.mimeType,
            chunkIndex: 0,
            startCharacterOffset: 0,
            endCharacterOffset: runtimeDocumentIndexSnippetCharacterLimitCeiling * 10,
            text: String(repeating: "needle bounded snippet content ", count: runtimeDocumentIndexSnippetCharacterLimitCeiling)
        )
        let results = runtimeDocumentSearchResults(
            from: [(document, chunk)],
            query: "needle",
            limit: runtimeDocumentIndexQueryLimitCeiling + 50,
            maxSnippetCharacters: runtimeDocumentIndexSnippetCharacterLimitCeiling + 1_000
        )
        XCTAssertEqual(results.count, 1)
        XCTAssertLessThanOrEqual(results.single?.snippet.count ?? 0, runtimeDocumentIndexSnippetCharacterLimitCeiling)
    }

    func testQueryTermsApplyStoreOwnedResourceGuards() throws {
        let store = RuntimeDocumentIndexStore()
        let result = try ingestedDocument(
            fileName: "query-guard.md",
            text: "Alpha or beta gamma delta guarded term appears in runtime document search."
        )
        _ = store.replaceDocument(result: result, documentID: "query-guard")

        let overlongQuery = String(repeating: "a", count: runtimeDocumentIndexQueryTextCharacterLimitCeiling + 1)
        let overlongTerm = String(repeating: "x", count: runtimeDocumentIndexQueryTermCharacterLimitCeiling + 1)
        let excessiveTerms = (0...runtimeDocumentIndexQueryTermLimitCeiling)
            .map { "term\($0)" }
            .joined(separator: " ")
        let duplicateTerms = String(repeating: "guarded ", count: runtimeDocumentIndexQueryTermLimitCeiling + 3)
        let operatorHeavyQuery = "alpha OR beta - gamma \"delta\"*"

        XCTAssertEqual(runtimeDocumentIndexEffectiveSearchTerms("Guarded guarded TERM"), ["guarded", "term"])
        XCTAssertEqual(runtimeDocumentIndexEffectiveSearchTerms(operatorHeavyQuery), ["alpha", "or", "beta", "gamma", "delta"])
        XCTAssertEqual(runtimeDocumentIndexEffectiveSearchTerms("---- !!!"), [])
        XCTAssertEqual(runtimeDocumentIndexEffectiveSearchTerms(overlongQuery), [])
        XCTAssertEqual(runtimeDocumentIndexEffectiveSearchTerms(overlongTerm), [])
        XCTAssertEqual(runtimeDocumentIndexEffectiveSearchTerms(excessiveTerms), [])

        XCTAssertEqual(store.query(overlongQuery), [])
        XCTAssertEqual(store.query(overlongTerm), [])
        XCTAssertEqual(store.query(excessiveTerms), [])
        XCTAssertEqual(store.query(duplicateTerms).single?.document.id, "query-guard")
        XCTAssertEqual(store.query(operatorHeavyQuery).single?.matchedTerms, ["alpha", "or", "beta", "gamma", "delta"])
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

    func testNormalizesMalformedIngestionSummaryBeforeStorage() throws {
        let store = RuntimeDocumentIndexStore()
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

        XCTAssertEqual(
            RuntimeDocumentIndexStore.stableContentFingerprint(for: malformedChunked),
            RuntimeDocumentIndexStore.stableContentFingerprint(for: chunked)
        )

        let storedChunked = store.replaceDocument(result: malformedChunked, documentID: "summary")
        let expectedCharacterCount = chunked.document.text.trimmingCharacters(in: .whitespacesAndNewlines).count
        XCTAssertEqual(storedChunked.extractedCharacterCount, expectedCharacterCount)
        XCTAssertEqual(storedChunked.chunkCount, chunked.chunks.count)
        XCTAssertEqual(storedChunked.quality, .chunked)

        let summary = store.summary()
        XCTAssertEqual(summary.extractedCharacterCount, expectedCharacterCount)
        XCTAssertEqual(summary.chunkCount, chunked.chunks.count)
        XCTAssertEqual(summary.qualityCounts[.chunked], 1)
        XCTAssertEqual(summary.qualityCounts[.noUsableText], nil)

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

        let storedEmpty = store.replaceDocument(result: malformedEmpty, documentID: "empty")
        XCTAssertEqual(storedEmpty.extractedCharacterCount, 0)
        XCTAssertEqual(storedEmpty.chunkCount, 0)
        XCTAssertEqual(storedEmpty.quality, .noUsableText)
        XCTAssertEqual(store.documents(matchingQuality: .noUsableText).map(\.id), ["empty"])
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

        _ = store.replaceDocument(result: copyB, documentID: "copy-b")
        _ = store.replaceDocument(result: unrelated, documentID: "unrelated")
        _ = store.replaceDocument(result: copyA, documentID: "copy-a")

        let matches = store.documents(matchingContentFingerprint: duplicateFingerprint)
        XCTAssertEqual(matches.map(\.id), ["copy-a", "copy-b"])
        XCTAssertEqual(store.documents(matchingContentFingerprint: " \(duplicateFingerprint)\n").map(\.id), ["copy-a", "copy-b"])
        XCTAssertEqual(store.documents(matchingContentFingerprint: duplicateFingerprint, limit: 1).map(\.id), ["copy-a"])
        XCTAssertEqual(store.documents(matchingContentFingerprint: "missing"), [])
        XCTAssertEqual(store.documents(matchingContentFingerprint: ""), [])
        XCTAssertEqual(store.documents(matchingContentFingerprint: " \n\t "), [])
        XCTAssertEqual(store.documents(matchingContentFingerprint: uppercaseFingerprint), [])
        XCTAssertEqual(store.documents(matchingContentFingerprint: caseMutatedFingerprint), [])
        XCTAssertEqual(store.documents(matchingContentFingerprint: underLengthFingerprint), [])
        XCTAssertEqual(store.documents(matchingContentFingerprint: overLengthFingerprint), [])
        XCTAssertEqual(store.documents(matchingContentFingerprint: nonHexFingerprint), [])
        XCTAssertFalse(String(describing: matches).contains(duplicateText))
        XCTAssertFalse(String(describing: matches).contains("sourcePath"))
        XCTAssertFalse(String(describing: matches).contains("workspaceID"))
        XCTAssertFalse(String(describing: matches).contains("retrieval_context"))
        XCTAssertFalse(String(describing: matches).contains("embedding"))
        XCTAssertFalse(String(describing: matches).contains("citation"))
        XCTAssertFalse(String(describing: matches).contains("trustedSource"))

        _ = store.replaceDocument(result: replacement, documentID: "copy-a")
        XCTAssertEqual(store.documents(matchingContentFingerprint: duplicateFingerprint).map(\.id), ["copy-b"])
        XCTAssertEqual(store.documents(matchingContentFingerprint: replacementFingerprint).map(\.id), ["copy-a"])

        store.deleteDocument(id: "copy-b")
        XCTAssertEqual(store.documents(matchingContentFingerprint: duplicateFingerprint), [])
    }

    func testDeleteDocumentsByContentFingerprintClearsMatchingRowsWithoutFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let duplicateText = "Fingerprint delete duplicate text should be removed from runtime document search."
        let copyB = try ingestedDocument(fileName: "copy-b.md", text: duplicateText)
        let copyA = try ingestedDocument(fileName: "copy-a.md", text: duplicateText)
        let unrelated = try ingestedDocument(
            fileName: "unrelated.md",
            text: "Unrelated fingerprint delete text should remain searchable after maintenance cleanup."
        )
        let duplicateFingerprint = RuntimeDocumentIndexStore.stableContentFingerprint(for: copyB)
        let uppercaseFingerprint = "A" + String(duplicateFingerprint.dropFirst())
        let overLengthFingerprint = String(repeating: "a", count: runtimeDocumentIndexContentFingerprintCharacterCount + 1)

        _ = store.replaceDocument(result: copyB, documentID: "copy-b")
        _ = store.replaceDocument(result: unrelated, documentID: "unrelated")
        _ = store.replaceDocument(result: copyA, documentID: "copy-a")

        XCTAssertEqual(store.documents(matchingContentFingerprint: duplicateFingerprint).map(\.id), ["copy-a", "copy-b"])
        XCTAssertEqual(Set(store.query("fingerprint delete").map(\.document.id)), Set(["copy-a", "copy-b", "unrelated"]))
        XCTAssertEqual(store.summary().documentCount, 3)

        store.deleteDocuments(matchingContentFingerprint: uppercaseFingerprint)
        store.deleteDocuments(matchingContentFingerprint: overLengthFingerprint)
        XCTAssertEqual(store.documents().map(\.id), ["copy-a", "copy-b", "unrelated"])

        store.deleteDocuments(matchingContentFingerprint: " \(duplicateFingerprint)\n")

        XCTAssertNil(store.document(id: "copy-a"))
        XCTAssertNil(store.document(id: "copy-b"))
        XCTAssertNotNil(store.document(id: "unrelated"))
        XCTAssertEqual(store.chunks(for: "copy-a"), [])
        XCTAssertEqual(store.chunks(for: "copy-b"), [])
        XCTAssertFalse(store.chunks(for: "unrelated").isEmpty)
        XCTAssertEqual(store.chunkSummaries(for: "copy-a"), [])
        XCTAssertEqual(store.chunkSummaries(for: "copy-b"), [])
        XCTAssertFalse(store.chunkSummaries(for: "unrelated").isEmpty)
        XCTAssertEqual(store.documents(matchingContentFingerprint: duplicateFingerprint), [])
        XCTAssertEqual(store.documents().map(\.id), ["unrelated"])
        XCTAssertEqual(store.query("duplicate"), [])
        XCTAssertEqual(store.query("unrelated").single?.document.id, "unrelated")
        XCTAssertEqual(store.summary().documentCount, 1)
        XCTAssertEqual(store.summary().chunkCount, unrelated.chunks.count)
        XCTAssertEqual(store.summary().qualityCounts[unrelated.summary.quality], 1)
        XCTAssertFalse(String(describing: store.documents()).contains(duplicateText))
        XCTAssertFalse(String(describing: store.documents()).contains("sourcePath"))
        XCTAssertFalse(String(describing: store.summary()).contains("projectID"))
        XCTAssertFalse(String(describing: store.summary()).contains("workspaceID"))
        XCTAssertFalse(String(describing: store.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: store.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: store.summary()).contains("citation"))
        XCTAssertFalse(String(describing: store.summary()).contains("trustedSource"))

        store.deleteDocuments(matchingContentFingerprint: duplicateFingerprint)
        XCTAssertEqual(store.documents().map(\.id), ["unrelated"])
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

    func testListsDocumentsByMimeTypeWithoutContentOrFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let bodySentinel = "PRIVATE_MIME_BODY_SHOULD_NOT_APPEAR"
        let markdownB = try ingestedDocument(fileName: "markdown-b.md", text: "\(bodySentinel) markdown body remains private.")
        let markdownA = try ingestedDocument(fileName: "markdown-a.md", text: "Second markdown body remains private.")
        let plain = try ingestedDocument(
            fileName: "notes.txt",
            mimeType: "text/plain",
            text: "Plain text body remains private."
        )
        let spacedPlain = try ingestedDocument(
            fileName: "aaa-spaced.txt",
            mimeType: " text/plain\n",
            text: "Spaced MIME text should store as canonical plain text."
        )
        let pdf = try ingestedDocument(
            fileName: "brief.pdf",
            mimeType: "application/pdf",
            text: "PDF extracted body remains private."
        )
        let malformedMime = try ingestedDocument(
            fileName: "zzz-unknown.bin",
            mimeType: "text/plain; charset=utf-8",
            text: "Malformed MIME text should store under the safe unknown type."
        )
        let replacement = try ingestedDocument(
            fileName: "markdown-b.txt",
            mimeType: "text/plain",
            text: "Replacement text body remains private."
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

        _ = store.replaceDocument(result: markdownB, documentID: "markdown-b")
        _ = store.replaceDocument(result: spacedPlain, documentID: "spaced-plain")
        _ = store.replaceDocument(result: plain, documentID: "plain")
        _ = store.replaceDocument(result: pdf, documentID: "pdf")
        _ = store.replaceDocument(result: malformedMime, documentID: "unknown")
        _ = store.replaceDocument(result: markdownA, documentID: "markdown-a")

        let markdownCatalog = store.documents(matchingMimeType: "text/markdown")
        XCTAssertEqual(markdownCatalog.map(\.id), ["markdown-a", "markdown-b"])
        XCTAssertEqual(store.documents(matchingMimeType: " text/markdown\n").map(\.id), ["markdown-a", "markdown-b"])
        XCTAssertEqual(store.documents(matchingMimeType: "text/markdown", limit: 1).map(\.id), ["markdown-a"])
        XCTAssertEqual(store.documents(matchingMimeType: "text/plain").map(\.id), ["spaced-plain", "plain"])
        XCTAssertEqual(store.documents(matchingMimeType: " text/plain\n").map(\.id), ["spaced-plain", "plain"])
        XCTAssertEqual(store.documents(matchingMimeType: "application/pdf").map(\.id), ["pdf"])
        XCTAssertEqual(store.documents(matchingMimeType: runtimeDocumentIndexUnknownMimeType).map(\.id), ["unknown"])
        XCTAssertEqual(store.documents(matchingMimeType: "application/json"), [])
        XCTAssertEqual(store.documents(matchingMimeType: ""), [])
        XCTAssertEqual(store.documents(matchingMimeType: " \n\t "), [])
        XCTAssertEqual(store.documents(matchingMimeType: caseMutatedMimeType), [])
        XCTAssertEqual(store.documents(matchingMimeType: missingSlashMimeType), [])
        XCTAssertEqual(store.documents(matchingMimeType: urlShapedMimeType), [])
        XCTAssertEqual(store.documents(matchingMimeType: overlongMimeType), [])
        XCTAssertEqual(store.documents(matchingMimeType: "text/plain; charset=utf-8"), [])
        XCTAssertEqual(store.documents(matchingMimeType: "text/markdown", limit: 0), [])
        XCTAssertEqual(store.document(id: "spaced-plain")?.mimeType, "text/plain")
        XCTAssertEqual(store.document(id: "unknown")?.mimeType, runtimeDocumentIndexUnknownMimeType)
        XCTAssertEqual(Set(store.chunks(for: "spaced-plain").map(\.documentMimeType)), ["text/plain"])
        XCTAssertEqual(Set(store.chunks(for: "unknown").map(\.documentMimeType)), [runtimeDocumentIndexUnknownMimeType])
        XCTAssertFalse(String(describing: markdownCatalog).contains(bodySentinel))
        XCTAssertFalse(String(describing: markdownCatalog).contains("sourcePath"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("workspaceID"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("retrieval_context"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("embedding"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("citation"))
        XCTAssertFalse(String(describing: markdownCatalog).contains("trustedSource"))

        _ = store.replaceDocument(result: replacement, documentID: "markdown-b")
        store.deleteDocument(id: "markdown-a")

        XCTAssertEqual(store.documents(matchingMimeType: "text/markdown"), [])
        XCTAssertEqual(store.documents(matchingMimeType: "text/plain").map(\.id), ["spaced-plain", "markdown-b", "plain"])
    }

    func testDeleteDocumentsByMimeTypeClearsMatchingRowsWithoutFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let markdownSentinel = "MarkdownMimeDeleteSentinel"
        let plainSentinel = "PlainMimeDeleteSentinel"
        let pdfSentinel = "PdfMimeDeleteSentinel"
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

        _ = store.replaceDocument(result: markdownB, documentID: "markdown-b")
        _ = store.replaceDocument(result: plain, documentID: "plain")
        _ = store.replaceDocument(result: pdf, documentID: "pdf")
        _ = store.replaceDocument(result: markdownA, documentID: "markdown-a")

        XCTAssertEqual(store.documents(matchingMimeType: "text/markdown").map(\.id), ["markdown-a", "markdown-b"])
        XCTAssertEqual(Set(store.query("cleanup").map(\.document.id)), Set(["markdown-a", "markdown-b", "plain", "pdf"]))
        XCTAssertEqual(store.summary().documentCount, 4)

        store.deleteDocuments(matchingMimeType: caseMutatedMimeType)
        store.deleteDocuments(matchingMimeType: overlongMimeType)
        XCTAssertEqual(Set(store.documents().map(\.id)), Set(["markdown-a", "markdown-b", "pdf", "plain"]))

        store.deleteDocuments(matchingMimeType: " text/markdown\n")

        XCTAssertNil(store.document(id: "markdown-a"))
        XCTAssertNil(store.document(id: "markdown-b"))
        XCTAssertNotNil(store.document(id: "plain"))
        XCTAssertNotNil(store.document(id: "pdf"))
        XCTAssertEqual(store.chunks(for: "markdown-a"), [])
        XCTAssertEqual(store.chunks(for: "markdown-b"), [])
        XCTAssertFalse(store.chunks(for: "plain").isEmpty)
        XCTAssertFalse(store.chunks(for: "pdf").isEmpty)
        XCTAssertEqual(store.chunkSummaries(for: "markdown-a"), [])
        XCTAssertEqual(store.chunkSummaries(for: "markdown-b"), [])
        XCTAssertFalse(store.chunkSummaries(for: "plain").isEmpty)
        XCTAssertEqual(store.documents(matchingMimeType: "text/markdown"), [])
        XCTAssertEqual(store.documents().map(\.id), ["pdf", "plain"])
        XCTAssertEqual(store.query(markdownSentinel), [])
        XCTAssertEqual(store.query(plainSentinel).single?.document.id, "plain")
        XCTAssertEqual(store.query(pdfSentinel).single?.document.id, "pdf")
        XCTAssertEqual(store.summary().documentCount, 2)
        XCTAssertEqual(store.summary().chunkCount, plain.chunks.count + pdf.chunks.count)
        XCTAssertEqual(
            store.summary().qualityCounts,
            Dictionary([plain.summary.quality, pdf.summary.quality].map { ($0, 1) }, uniquingKeysWith: +)
        )
        XCTAssertFalse(String(describing: store.documents()).contains(markdownSentinel))
        XCTAssertFalse(String(describing: store.documents()).contains("sourcePath"))
        XCTAssertFalse(String(describing: store.summary()).contains("projectID"))
        XCTAssertFalse(String(describing: store.summary()).contains("workspaceID"))
        XCTAssertFalse(String(describing: store.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: store.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: store.summary()).contains("citation"))
        XCTAssertFalse(String(describing: store.summary()).contains("trustedSource"))

        store.deleteDocuments(matchingMimeType: "text/markdown")
        XCTAssertEqual(store.documents().map(\.id), ["pdf", "plain"])
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

    func testDeleteAllDocumentsClearsCatalogChunksSummaryAndQueryWithoutFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let alpha = try ingestedDocument(
            fileName: "alpha.md",
            text: "Alpha clear-all query text should disappear from runtime document search."
        )
        let beta = try ingestedDocument(
            fileName: "beta.md",
            text: "Beta clear-all maintenance content should leave no chunk summaries behind."
        )

        _ = store.replaceDocument(result: alpha, documentID: "alpha")
        _ = store.replaceDocument(result: beta, documentID: "beta")

        XCTAssertEqual(store.documents().count, 2)
        XCTAssertFalse(store.chunkSummaries(for: "alpha").isEmpty)
        XCTAssertFalse(store.query("clear-all").isEmpty)
        XCTAssertEqual(store.summary().documentCount, 2)

        store.deleteAllDocuments()

        XCTAssertEqual(store.documents(), [])
        XCTAssertEqual(store.documents(matchingDisplayName: "alpha.md"), [])
        XCTAssertEqual(store.documents(matchingMimeType: "text/markdown"), [])
        XCTAssertEqual(store.documents(matchingQuality: .singleChunk), [])
        XCTAssertNil(store.document(id: "alpha"))
        XCTAssertNil(store.document(id: "beta"))
        XCTAssertEqual(store.chunks(for: "alpha"), [])
        XCTAssertEqual(store.chunks(for: "beta"), [])
        XCTAssertEqual(store.chunkSummaries(for: "alpha"), [])
        XCTAssertEqual(store.query("clear-all"), [])
        XCTAssertEqual(store.summary(), RuntimeDocumentIndexSummary(
            documentCount: 0,
            chunkCount: 0,
            extractedCharacterCount: 0,
            qualityCounts: [:]
        ))
        XCTAssertFalse(String(describing: store.summary()).contains("sourcePath"))
        XCTAssertFalse(String(describing: store.summary()).contains("projectID"))
        XCTAssertFalse(String(describing: store.summary()).contains("workspaceID"))
        XCTAssertFalse(String(describing: store.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: store.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: store.summary()).contains("citation"))
        XCTAssertFalse(String(describing: store.summary()).contains("trustedSource"))

        store.deleteAllDocuments()
        XCTAssertEqual(store.documents(), [])
        XCTAssertEqual(store.query("clear-all"), [])
    }

    func testDeleteDocumentsByQualityClearsOnlyMatchingRowsWithoutFutureMetadata() throws {
        let store = RuntimeDocumentIndexStore()
        let empty = try ingestedDocument(fileName: "empty.md", text: "   ")
        let chunked = try ingestedDocument(
            fileName: "chunked.md",
            text: [
                "Chunked quality deletion text should remain searchable after empty rows are removed.",
                "Additional text forces chunk planning and keeps metadata maintenance useful.",
                "The runtime index must not expose source paths while deleting by quality."
            ].joined(separator: " ")
        )
        let single = try ingestedDocument(
            fileName: "single.md",
            text: "Single quality deletion text should remain in the runtime index."
        )

        _ = store.replaceDocument(result: empty, documentID: "empty")
        _ = store.replaceDocument(result: chunked, documentID: "chunked")
        _ = store.replaceDocument(result: single, documentID: "single")
        XCTAssertEqual(store.documents().count, 3)
        XCTAssertEqual(store.documents(matchingQuality: .noUsableText).map(\.id), ["empty"])

        store.deleteDocuments(matchingQuality: .noUsableText)

        XCTAssertNil(store.document(id: "empty"))
        XCTAssertEqual(store.chunks(for: "empty"), [])
        XCTAssertEqual(store.chunkSummaries(for: "empty"), [])
        XCTAssertEqual(store.documents(matchingQuality: .noUsableText), [])
        XCTAssertEqual(store.documents().map(\.id), ["chunked", "single"])
        XCTAssertEqual(store.documents(matchingQuality: .chunked).map(\.id), ["chunked"])
        XCTAssertEqual(store.documents(matchingQuality: .singleChunk).map(\.id), ["single"])
        XCTAssertEqual(Set(store.query("quality deletion").map(\.document.id)), Set(["chunked", "single"]))
        XCTAssertFalse(store.query("quality deletion").contains { $0.document.id == "empty" })
        XCTAssertEqual(store.summary().documentCount, 2)
        XCTAssertEqual(store.summary().qualityCounts[.noUsableText], nil)
        XCTAssertEqual(store.summary().qualityCounts[.chunked], 1)
        XCTAssertEqual(store.summary().qualityCounts[.singleChunk], 1)
        XCTAssertFalse(String(describing: store.documents()).contains("sourcePath"))
        XCTAssertFalse(String(describing: store.summary()).contains("projectID"))
        XCTAssertFalse(String(describing: store.summary()).contains("workspaceID"))
        XCTAssertFalse(String(describing: store.summary()).contains("retrieval_context"))
        XCTAssertFalse(String(describing: store.summary()).contains("embedding"))
        XCTAssertFalse(String(describing: store.summary()).contains("citation"))
        XCTAssertFalse(String(describing: store.summary()).contains("trustedSource"))

        store.deleteDocuments(matchingQuality: .noUsableText)
        XCTAssertEqual(store.documents().map(\.id), ["chunked", "single"])

        store.deleteDocuments(matchingQuality: .chunked)
        XCTAssertEqual(store.documents().map(\.id), ["single"])
        XCTAssertEqual(store.query("chunked"), [])
        XCTAssertEqual(store.query("single").single?.document.id, "single")
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
                "Ceiling chunk \(index) keeps metadata review bounded with repeated runtime-local content for splitting."
            }
            .joined(separator: " ")
    }
}

private extension Array {
    var single: Element? {
        count == 1 ? self[0] : nil
    }
}
