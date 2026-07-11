import DocumentIngestion
import Foundation
import OllamaBackend
import SQLite3
import XCTest
@testable import CompanionCore

final class SQLiteRuntimeDocumentSemanticEmbeddingCacheTests: XCTestCase {
    func testPersistentModelFingerprintReusesStrongLocalEmbeddingPolicy() throws {
        let ollama = ModelInfo(
            id: "nomic-embed-text:latest",
            name: "Nomic Embed",
            provider: .ollama,
            kind: .embedding,
            capabilities: ["embedding", "local"],
            providerModelID: "nomic-embed-text:latest",
            sizeBytes: 123,
            modifiedAt: Date(timeIntervalSince1970: 100),
            contextWindowTokens: 2_048,
            persistentEmbeddingRevision: "ollama-sha256:" + String(repeating: "a", count: 64)
        )
        var lmStudio = ollama
        lmStudio.provider = .lmStudio
        lmStudio.persistentEmbeddingRevision = nil

        XCTAssertEqual(
            RuntimeSemanticDocumentSearch.persistentModelFingerprint(
                model: ollama,
                requestedQualifiedModelID: "ollama:nomic-embed-text"
            ),
            RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
                model: ollama,
                requestedQualifiedModelID: "ollama:nomic-embed-text"
            )
        )
        XCTAssertNil(RuntimeSemanticDocumentSearch.persistentModelFingerprint(
            model: lmStudio,
            requestedQualifiedModelID: "lm_studio:nomic-embed-text"
        ))
    }

    func testApprovedCandidatesAreBoundedAndUnapprovedRowsStayHidden() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: String(repeating: "approved semantic text ", count: 400)),
            documentID: "approved-doc"
        )
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)

        let candidates = try cache.approvedCandidates(limit: 500)
        XCTAssertFalse(candidates.isEmpty)
        XCTAssertLessThanOrEqual(candidates.count, RuntimeSemanticDocumentSearch.maximumCandidateCount)
        XCTAssertTrue(candidates.allSatisfy { $0.semanticDocument.utf8.count <= 4_096 })
        XCTAssertTrue(candidates.allSatisfy { $0.sourceRevision.count == 64 })
        XCTAssertTrue(candidates.allSatisfy { $0.documentFingerprint.count == 64 })

        try executeRaw(databaseURL, "DELETE FROM runtime_document_source_approvals")
        XCTAssertTrue(try cache.approvedCandidates().isEmpty)
    }

    func testCandidateLimitCountsUsableRowsInsteadOfLeadingBlankChunks() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "usable semantic candidate after blank rows"),
            documentID: "zzzz-usable"
        )
        try seedLeadingBlankApprovedChunks(databaseURL: databaseURL, count: 205)

        let candidates = try SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
            .approvedCandidates(limit: 1)

        XCTAssertEqual(candidates.map(\.document.id), ["zzzz-usable"])
    }

    func testApprovedSourceCeilingBlocksNewApprovalsAndOversizedLegacyCorpus() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        _ = try store.documents()
        try seedLeadingBlankApprovedChunks(
            databaseURL: databaseURL,
            count: runtimeDocumentApprovedSourceLimitCeiling
        )

        XCTAssertThrowsError(try store.replaceDocument(
            result: ingestedDocument(text: "source above approved semantic ceiling"),
            documentID: "over-approved-limit"
        ))

        try executeRaw(
            databaseURL,
            """
            INSERT INTO runtime_document_index_documents(
                document_id, display_name, mime_type, content_fingerprint,
                extracted_character_count, chunk_count, quality
            ) VALUES ('legacy-over-limit', 'legacy-over-limit.md', 'text/markdown',
                      '0123456789abcdef', 0, 0, 'no_usable_text');
            INSERT INTO runtime_document_source_approvals(
                document_id, approval_id, source_revision, approval_scope, approved_by, approved_at
            ) VALUES ('legacy-over-limit', 'legacy-over-limit-approval',
                      '(String(repeating: "d", count: 64))', 'runtime_shared', 'runtime_host', 0);
            """
        )
        XCTAssertThrowsError(
            try SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
                .approvedCandidates()
        )
    }

    func testCandidateDiscoveryReadsAtMostFourTimesTheFinalCandidateLimit() throws {
        let databaseURL = temporaryDatabaseURL()
        _ = try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).documents()
        try seedApprovedCandidateCorpus(
            databaseURL: databaseURL,
            documentCount: RuntimeSemanticDocumentSearch.maximumCandidateCount,
            chunksPerDocument: RuntimeSemanticDocumentSearch.maximumCandidateRowScanMultiplier + 1
        )
        let counter = SemanticCandidateRowCounter()
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        cache.onCandidateRowRead = { counter.increment() }

        let candidates = try cache.approvedCandidates(
            limit: RuntimeSemanticDocumentSearch.maximumCandidateCount
        )

        XCTAssertEqual(candidates.count, RuntimeSemanticDocumentSearch.maximumCandidateCount)
        XCTAssertLessThanOrEqual(
            counter.value,
            RuntimeSemanticDocumentSearch.maximumCandidateCount
                * RuntimeSemanticDocumentSearch.maximumCandidateRowScanMultiplier
        )
    }

    func testCandidateDiscoveryStopsWhenCancellationIsObserved() throws {
        let databaseURL = temporaryDatabaseURL()
        _ = try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).documents()
        try seedApprovedCandidateCorpus(databaseURL: databaseURL, documentCount: 40, chunksPerDocument: 20)
        let gate = SemanticCandidateCancellationGate(cancelAfterRows: 10)
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        cache.onCandidateRowRead = { gate.didReadRow() }

        XCTAssertThrowsError(
            try cache.approvedCandidates(limit: 40, if: { gate.shouldContinue })
        ) { error in
            XCTAssertTrue(error is CancellationError)
        }
        XCTAssertEqual(gate.rowCount, 10)
    }

    func testSQLiteProgressHandlerInterruptsInsideCandidateStatement() throws {
        let databaseURL = temporaryDatabaseURL()
        _ = try SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL).documents()
        try seedApprovedCandidateCorpus(databaseURL: databaseURL, documentCount: 200, chunksPerDocument: 5)
        let gate = SemanticCandidateProgressCancellationGate()
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        cache.onCandidateSQLWillExecute = { gate.enterCandidatePhase() }
        cache.onCandidateSQLProgress = { gate.cancelFromProgressHandler() }

        XCTAssertThrowsError(
            try cache.approvedCandidates(limit: 200, if: { gate.shouldContinue })
        ) { error in
            XCTAssertTrue(error is CancellationError)
        }
        XCTAssertTrue(gate.candidatePhaseEntered)
        XCTAssertGreaterThan(gate.progressCount, 0)
    }

    func testApprovedCandidatesAreSelectedFairlyAcrossDocuments() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let largeDocument = try ingestedDocument(
            text: String(repeating: "large approved document ", count: 2_000)
        )
        XCTAssertGreaterThanOrEqual(largeDocument.chunks.count, 200)
        try store.replaceDocument(
            result: largeDocument,
            documentID: "aaa-large"
        )
        try store.replaceDocument(
            result: ingestedDocument(text: "small approved document beta"),
            documentID: "bbb-small"
        )
        try store.replaceDocument(
            result: ingestedDocument(text: "small approved document zeta"),
            documentID: "zzz-small"
        )

        let candidates = try SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
            .approvedCandidates(limit: 4)

        XCTAssertEqual(
            candidates.map(\.document.id),
            ["aaa-large", "bbb-small", "zzz-small", "aaa-large"]
        )
        XCTAssertEqual(candidates.map(\.chunk.chunkIndex), [0, 0, 0, 1])
    }

    func testRankedResultsRemainOrderedForHugeFiniteVectors() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "orthogonal semantic candidate"),
            documentID: "aaa-orthogonal"
        )
        try store.replaceDocument(
            result: ingestedDocument(text: "aligned semantic candidate"),
            documentID: "zzz-aligned"
        )
        let candidates = try SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
            .approvedCandidates(limit: 2)
        let huge = Double.greatestFiniteMagnitude

        let results = try RuntimeSemanticDocumentSearch.rankedResults(
            candidates: candidates,
            query: "semantic",
            queryEmbedding: [huge, huge],
            candidateEmbeddings: [[huge, -huge], [huge, huge]],
            limit: 2,
            maxSnippetCharacters: 120
        )

        XCTAssertEqual(results.map(\.document.id), ["zzz-aligned", "aaa-orthogonal"])
        XCTAssertEqual(results.map(\.rank), [1, 2])
    }

    func testCandidateEmbeddingPersistsAcrossReopenAndSeparatesModelIdentity() throws {
        let databaseURL = temporaryDatabaseURL()
        let key = try approvedKey(databaseURL: databaseURL, documentID: "shared-doc")
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        let record = RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: [0.25, 0.5, 0.75])

        try cache.upsertEmbeddings([record], if: { true })
        let reopened = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.cachedEmbeddings(for: [key]), [record])

        var differentModel = key
        differentModel.canonicalQualifiedEmbeddingModelID = "ollama:other-embed"
        XCTAssertTrue(try reopened.cachedEmbeddings(for: [differentModel]).isEmpty)

        var differentFingerprint = key
        differentFingerprint.modelFingerprint = String(repeating: "b", count: 64)
        XCTAssertTrue(try reopened.cachedEmbeddings(for: [differentFingerprint]).isEmpty)
    }

    func testCandidateEmbeddingSeparatesModelInputByteLimits() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: String(repeating: "bounded semantic source ", count: 220)),
            documentID: "byte-limit-doc"
        )
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        let shortCandidate = try XCTUnwrap(
            cache.approvedCandidates(limit: 1, maximumDocumentUTF8Bytes: 1_024).first
        )
        let longCandidate = try XCTUnwrap(
            cache.approvedCandidates(limit: 1, maximumDocumentUTF8Bytes: 4_096).first
        )
        let modelFingerprint = String(repeating: "a", count: 64)
        let shortKey = RuntimeSemanticDocumentSearch.cacheKey(
            candidate: shortCandidate,
            canonicalQualifiedEmbeddingModelID: "ollama:embed",
            modelFingerprint: modelFingerprint
        )
        let longKey = RuntimeSemanticDocumentSearch.cacheKey(
            candidate: longCandidate,
            canonicalQualifiedEmbeddingModelID: "ollama:embed",
            modelFingerprint: modelFingerprint
        )

        XCTAssertEqual(shortKey.documentByteLimit, 1_024)
        XCTAssertEqual(longKey.documentByteLimit, 4_096)
        XCTAssertNotEqual(shortKey.documentFingerprint, longKey.documentFingerprint)
        try cache.upsertEmbeddings([
            RuntimeDocumentSemanticEmbeddingRecord(key: shortKey, embedding: [1, 0]),
            RuntimeDocumentSemanticEmbeddingRecord(key: longKey, embedding: [0, 1])
        ], if: { true })

        let records = try SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
            .cachedEmbeddings(for: [shortKey, longKey])
        XCTAssertEqual(Set(records.map(\.key)), Set([shortKey, longKey]))
        XCTAssertEqual(try cache.storedRowCount(), 2)
    }

    func testReplacementAndDeletionAtomicallyInvalidateDerivedRows() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "first approved semantic revision"),
            documentID: "rotating-doc"
        )
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        var candidate = try XCTUnwrap(cache.approvedCandidates().first)
        var key = RuntimeSemanticDocumentSearch.cacheKey(
            candidate: candidate,
            canonicalQualifiedEmbeddingModelID: "ollama:embed",
            modelFingerprint: String(repeating: "a", count: 64)
        )
        try cache.upsertEmbeddings([
            RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: [1, 2, 3])
        ], if: { true })
        XCTAssertEqual(try cache.storedRowCount(), 1)

        try store.replaceDocument(
            result: ingestedDocument(text: "second approved semantic revision"),
            documentID: "rotating-doc"
        )
        XCTAssertEqual(try cache.storedRowCount(), 0)

        candidate = try XCTUnwrap(cache.approvedCandidates().first)
        key = RuntimeSemanticDocumentSearch.cacheKey(
            candidate: candidate,
            canonicalQualifiedEmbeddingModelID: "ollama:embed",
            modelFingerprint: String(repeating: "a", count: 64)
        )
        try cache.upsertEmbeddings([
            RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: [1, 2, 3])
        ], if: { true })
        try store.deleteDocument(id: "rotating-doc")
        XCTAssertEqual(try cache.storedRowCount(), 0)
    }

    func testStaleRevisionCannotRepopulateAfterReplacement() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "semantic source before inference"),
            documentID: "stale-doc"
        )
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        let staleCandidate = try XCTUnwrap(cache.approvedCandidates().first)
        let staleKey = RuntimeSemanticDocumentSearch.cacheKey(
            candidate: staleCandidate,
            canonicalQualifiedEmbeddingModelID: "ollama:embed",
            modelFingerprint: String(repeating: "a", count: 64)
        )

        try store.replaceDocument(
            result: ingestedDocument(text: "semantic source after inference"),
            documentID: "stale-doc"
        )

        XCTAssertThrowsError(
            try cache.upsertEmbeddings([
                RuntimeDocumentSemanticEmbeddingRecord(key: staleKey, embedding: [1, 2, 3])
            ], if: { true })
        ) { error in
            XCTAssertEqual(error as? RuntimeDocumentSemanticEmbeddingCacheError, .staleSource)
        }
        XCTAssertEqual(try cache.storedRowCount(), 0)
    }

    func testStaleRecordRollsBackEarlierValidRecordInSameBatch() throws {
        let databaseURL = temporaryDatabaseURL()
        let firstKey = try approvedKey(databaseURL: databaseURL, documentID: "batch-valid")
        let staleKey = try approvedKey(databaseURL: databaseURL, documentID: "batch-stale")
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "replacement invalidates the second batch record"),
            documentID: "batch-stale"
        )
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)

        XCTAssertThrowsError(
            try cache.upsertEmbeddings([
                RuntimeDocumentSemanticEmbeddingRecord(key: firstKey, embedding: [1, 2, 3]),
                RuntimeDocumentSemanticEmbeddingRecord(key: staleKey, embedding: [4, 5, 6])
            ], if: { true })
        ) { error in
            XCTAssertEqual(error as? RuntimeDocumentSemanticEmbeddingCacheError, .staleSource)
        }
        XCTAssertEqual(try cache.storedRowCount(), 0)
    }

    func testCancelledConditionalWriteDoesNotCommit() throws {
        let databaseURL = temporaryDatabaseURL()
        let key = try approvedKey(databaseURL: databaseURL, documentID: "cancelled-doc")
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        let gate = SemanticCacheCommitGate(successfulChecks: 2)

        try cache.upsertEmbeddings([
            RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: [1, 2, 3])
        ], if: { gate.shouldCommit() })

        XCTAssertEqual(try cache.storedRowCount(), 0)
        XCTAssertLessThanOrEqual(gate.currentCheckCount, 3)
    }

    func testConcurrentCacheCommitAndDocumentReplacementWaitInsteadOfReturningBusy() async throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "concurrent cache writer source"),
            documentID: "concurrent-doc"
        )
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        let candidate = try XCTUnwrap(cache.approvedCandidates().first)
        let key = RuntimeSemanticDocumentSearch.cacheKey(
            candidate: candidate,
            canonicalQualifiedEmbeddingModelID: "ollama:embed",
            modelFingerprint: String(repeating: "a", count: 64)
        )
        let reachedCommit = DispatchSemaphore(value: 0)
        let allowCommit = DispatchSemaphore(value: 0)
        let replacementStarted = DispatchSemaphore(value: 0)
        let replacementFinished = DispatchSemaphore(value: 0)
        cache.onBeforeCommit = {
            reachedCommit.signal()
            _ = allowCommit.wait(timeout: .now() + 2)
        }

        let cacheTask = Task.detached {
            try cache.upsertEmbeddings([
                RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: [1, 2, 3])
            ], if: { true })
        }
        XCTAssertEqual(reachedCommit.wait(timeout: .now() + 2), .success)
        let replacement = try ingestedDocument(text: "replacement waits for cache commit")
        let replacementTask = Task.detached {
            replacementStarted.signal()
            try store.replaceDocument(
                result: replacement,
                documentID: "concurrent-doc"
            )
            replacementFinished.signal()
        }
        XCTAssertEqual(replacementStarted.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(replacementFinished.wait(timeout: .now() + 0.05), .timedOut)

        allowCommit.signal()
        try await cacheTask.value
        try await replacementTask.value
        cache.onBeforeCommit = nil

        XCTAssertEqual(try cache.storedRowCount(), 0)
        XCTAssertEqual(try store.document(id: "concurrent-doc")?.displayName, "semantic-source.md")
    }

    func testFilteredAndDeleteAllMaintenanceInvalidateSemanticRows() throws {
        let databaseURL = temporaryDatabaseURL()
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        for index in 0..<3 {
            let key = try approvedKey(databaseURL: databaseURL, documentID: "maintenance-\(index)")
            try cache.upsertEmbeddings([
                RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: [1, 2, 3])
            ], if: { true })
        }
        XCTAssertEqual(try cache.storedRowCount(), 3)

        try store.deleteDocuments(matchingDisplayName: "semantic-source.md")
        XCTAssertEqual(try cache.storedRowCount(), 0)

        for index in 0..<2 {
            let key = try approvedKey(databaseURL: databaseURL, documentID: "clear-all-\(index)")
            try cache.upsertEmbeddings([
                RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: [1, 2, 3])
            ], if: { true })
        }
        XCTAssertEqual(try cache.storedRowCount(), 2)
        try store.deleteAllDocuments()
        XCTAssertEqual(try cache.storedRowCount(), 0)
    }

    func testRowAndVectorByteLimitsEvictOldestCandidates() throws {
        let databaseURL = temporaryDatabaseURL()
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(
            databaseURL: databaseURL,
            rowLimitPerModel: 2,
            byteLimitPerModel: 40,
            totalByteLimit: 64
        )
        for index in 0..<3 {
            let key = try approvedKey(databaseURL: databaseURL, documentID: "bounded-\(index)")
            try cache.upsertEmbeddings([
                RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: [1, 2, 3])
            ], if: { true })
        }

        XCTAssertLessThanOrEqual(try cache.storedRowCount(), 2)
        XCTAssertLessThanOrEqual(
            try cache.storedVectorByteCount(modelID: "ollama:embed"),
            40
        )
        XCTAssertLessThanOrEqual(try cache.storedVectorByteCount(), 64)
    }

    func testInvalidKeysVectorsAndOversizedBatchesFailBeforeWriting() throws {
        let databaseURL = temporaryDatabaseURL()
        let key = try approvedKey(databaseURL: databaseURL, documentID: "invalid-doc")
        let cache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)

        var invalidRevision = key
        invalidRevision.sourceRevision = "weak"
        XCTAssertThrowsError(try cache.cachedEmbeddings(for: [invalidRevision]))
        XCTAssertThrowsError(
            try cache.cachedEmbeddings(
                for: Array(
                    repeating: key,
                    count: RuntimeSemanticDocumentSearch.maximumEmbeddingBatchCount + 1
                )
            )
        )
        XCTAssertThrowsError(
            try cache.upsertEmbeddings([
                RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: [0, 0, 0])
            ], if: { true })
        )
        XCTAssertThrowsError(
            try cache.upsertEmbeddings(
                Array(
                    repeating: RuntimeDocumentSemanticEmbeddingRecord(
                        key: key,
                        embedding: [1, 2, 3]
                    ),
                    count: RuntimeSemanticDocumentSearch.maximumEmbeddingBatchCount + 1
                ),
                if: { true }
            )
        )
        XCTAssertEqual(try cache.storedRowCount(), 0)
    }

    private func approvedKey(
        databaseURL: URL,
        documentID: String
    ) throws -> RuntimeDocumentSemanticEmbeddingKey {
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "approved semantic candidate for \(documentID)"),
            documentID: documentID
        )
        let candidate = try XCTUnwrap(
            SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
                .approvedCandidates()
                .first(where: { $0.document.id == documentID })
        )
        return RuntimeSemanticDocumentSearch.cacheKey(
            candidate: candidate,
            canonicalQualifiedEmbeddingModelID: "ollama:embed",
            modelFingerprint: String(repeating: "a", count: 64)
        )
    }

    private func ingestedDocument(text: String) throws -> DocumentIngestionResult {
        try DocumentIngestor(chunker: DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 120,
            overlapCharacters: 8,
            minChunkCharacters: 24
        ))).ingest(extractedDocument: ExtractedDocument(
            fileName: "semantic-source.md",
            mimeType: "text/markdown",
            text: text
        ))
    }

    private func temporaryDatabaseURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("runtime-document-index.sqlite")
    }

    private func executeRaw(_ databaseURL: URL, _ sql: String) throws {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READWRITE, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeDocumentSemanticEmbeddingCacheTests", code: 1)
        }
        defer { sqlite3_close(database) }
        var message: UnsafeMutablePointer<CChar>?
        let result = sqlite3_exec(database, sql, nil, nil, &message)
        let detail = message.map { String(cString: $0) }
        sqlite3_free(message)
        guard result == SQLITE_OK else {
            throw NSError(
                domain: detail ?? "SQLiteRuntimeDocumentSemanticEmbeddingCacheTests",
                code: 2
            )
        }
    }

    private func seedLeadingBlankApprovedChunks(databaseURL: URL, count: Int) throws {
        let revision = String(repeating: "c", count: 64)
        try executeRaw(
            databaseURL,
            """
            WITH RECURSIVE seq(value) AS (
                SELECT 0 UNION ALL SELECT value + 1 FROM seq WHERE value + 1 < \(count)
            )
            INSERT INTO runtime_document_index_documents(
                document_id, display_name, mime_type, content_fingerprint,
                extracted_character_count, chunk_count, quality
            )
            SELECT printf('blank-%03d', value), printf('000-blank-%03d.md', value),
                   'text/markdown', '0123456789abcdef', 1, 1, 'single_chunk'
            FROM seq
            """
        )
        try executeRaw(
            databaseURL,
            """
            WITH RECURSIVE seq(value) AS (
                SELECT 0 UNION ALL SELECT value + 1 FROM seq WHERE value + 1 < \(count)
            )
            INSERT INTO runtime_document_index_chunks(
                chunk_id, document_id, document_display_name, document_mime_type,
                chunk_index, start_character_offset, end_character_offset, text
            )
            SELECT printf('blank-chunk-%03d', value), printf('blank-%03d', value),
                   printf('000-blank-%03d.md', value), 'text/markdown', 0, 0, 1, '   \n  '
            FROM seq
            """
        )
        try executeRaw(
            databaseURL,
            """
            WITH RECURSIVE seq(value) AS (
                SELECT 0 UNION ALL SELECT value + 1 FROM seq WHERE value + 1 < \(count)
            )
            INSERT INTO runtime_document_source_approvals(
                document_id, approval_id, source_revision, approval_scope, approved_by, approved_at
            )
            SELECT printf('blank-%03d', value), printf('blank-approval-%03d', value),
                   '\(revision)', 'runtime_shared', 'runtime_host', 0
            FROM seq
            """
        )
    }

    private func seedApprovedCandidateCorpus(
        databaseURL: URL,
        documentCount: Int,
        chunksPerDocument: Int
    ) throws {
        let revision = String(repeating: "e", count: 64)
        try executeRaw(
            databaseURL,
            """
            WITH RECURSIVE documents(value) AS (
                SELECT 0 UNION ALL SELECT value + 1 FROM documents WHERE value + 1 < \(documentCount)
            )
            INSERT INTO runtime_document_index_documents(
                document_id, display_name, mime_type, content_fingerprint,
                extracted_character_count, chunk_count, quality
            )
            SELECT printf('candidate-%03d', value), printf('candidate-%03d.md', value),
                   'text/markdown', '0123456789abcdef', \(chunksPerDocument * 16),
                   \(chunksPerDocument), 'chunked'
            FROM documents;

            WITH RECURSIVE documents(value) AS (
                SELECT 0 UNION ALL SELECT value + 1 FROM documents WHERE value + 1 < \(documentCount)
            ), chunks(value) AS (
                SELECT 0 UNION ALL SELECT value + 1 FROM chunks WHERE value + 1 < \(chunksPerDocument)
            )
            INSERT INTO runtime_document_index_chunks(
                chunk_id, document_id, document_display_name, document_mime_type,
                chunk_index, start_character_offset, end_character_offset, text
            )
            SELECT printf('candidate-%03d-chunk-%03d', documents.value, chunks.value),
                   printf('candidate-%03d', documents.value),
                   printf('candidate-%03d.md', documents.value), 'text/markdown', chunks.value,
                   chunks.value * 16, (chunks.value + 1) * 16,
                   printf('semantic row %03d %03d', documents.value, chunks.value)
            FROM documents CROSS JOIN chunks;

            WITH RECURSIVE documents(value) AS (
                SELECT 0 UNION ALL SELECT value + 1 FROM documents WHERE value + 1 < \(documentCount)
            )
            INSERT INTO runtime_document_source_approvals(
                document_id, approval_id, source_revision, approval_scope, approved_by, approved_at
            )
            SELECT printf('candidate-%03d', value), printf('candidate-approval-%03d', value),
                   '\(revision)', 'runtime_shared', 'runtime_host', 0
            FROM documents;
            """
        )
    }
}

private final class SemanticCandidateRowCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var count = 0

    func increment() {
        lock.withLock { count += 1 }
    }

    var value: Int {
        lock.withLock { count }
    }
}

private final class SemanticCandidateCancellationGate: @unchecked Sendable {
    private let cancelAfterRows: Int
    private let lock = NSLock()
    private var rows = 0

    init(cancelAfterRows: Int) {
        self.cancelAfterRows = cancelAfterRows
    }

    func didReadRow() {
        lock.withLock { rows += 1 }
    }

    var shouldContinue: Bool {
        lock.withLock { rows < cancelAfterRows }
    }

    var rowCount: Int {
        lock.withLock { rows }
    }
}

private final class SemanticCandidateProgressCancellationGate: @unchecked Sendable {
    private let lock = NSLock()
    private var cancelled = false
    private var candidatePhase = false
    private var progressCallbacks = 0

    func enterCandidatePhase() {
        lock.withLock { candidatePhase = true }
    }

    func cancelFromProgressHandler() {
        lock.withLock {
            guard candidatePhase else { return }
            progressCallbacks += 1
            cancelled = true
        }
    }

    var shouldContinue: Bool {
        lock.withLock { !cancelled }
    }

    var progressCount: Int {
        lock.withLock { progressCallbacks }
    }

    var candidatePhaseEntered: Bool {
        lock.withLock { candidatePhase }
    }
}

private final class SemanticCacheCommitGate: @unchecked Sendable {
    private let successfulChecks: Int
    private let lock = NSLock()
    private var checkCount = 0

    init(successfulChecks: Int) {
        self.successfulChecks = successfulChecks
    }

    func shouldCommit() -> Bool {
        lock.withLock {
            checkCount += 1
            return checkCount <= successfulChecks
        }
    }

    var currentCheckCount: Int {
        lock.withLock { checkCount }
    }
}
