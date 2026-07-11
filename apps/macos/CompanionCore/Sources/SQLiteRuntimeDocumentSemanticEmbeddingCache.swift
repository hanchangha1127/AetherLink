import CryptoKit
import DocumentIngestion
import Foundation
import OllamaBackend
import SQLite3

private final class SQLiteRuntimeDocumentProgressCancellation: @unchecked Sendable {
    let shouldContinue: @Sendable () -> Bool
    let onProgress: (@Sendable () -> Void)?

    init(
        _ shouldContinue: @escaping @Sendable () -> Bool,
        onProgress: (@Sendable () -> Void)?
    ) {
        self.shouldContinue = shouldContinue
        self.onProgress = onProgress
    }
}

private let runtimeDocumentProgressCancellationHandler:
    @convention(c) (UnsafeMutableRawPointer?) -> Int32 = { context in
        guard let context else { return 0 }
        let cancellation = Unmanaged<SQLiteRuntimeDocumentProgressCancellation>
            .fromOpaque(context)
            .takeUnretainedValue()
        cancellation.onProgress?()
        return cancellation.shouldContinue() ? 0 : 1
    }

struct RuntimeDocumentSemanticCandidate: Equatable, Sendable {
    var document: RuntimeDocumentIndexDocument
    var chunk: RuntimeDocumentIndexChunk
    var sourceRevision: String
    var semanticDocument: String
    var documentByteLimit: Int
    var documentFingerprint: String

    var identity: RuntimeDocumentSemanticCandidateIdentity {
        RuntimeDocumentSemanticCandidateIdentity(
            documentID: document.id,
            chunkID: chunk.id,
            sourceRevision: sourceRevision,
            documentByteLimit: documentByteLimit,
            documentFingerprint: documentFingerprint
        )
    }
}

struct RuntimeDocumentSemanticCandidateIdentity: Equatable, Hashable, Sendable {
    var documentID: String
    var chunkID: String
    var sourceRevision: String
    var documentByteLimit: Int
    var documentFingerprint: String
}

struct RuntimeDocumentSemanticEmbeddingKey: Equatable, Hashable, Sendable {
    var documentID: String
    var chunkID: String
    var sourceRevision: String
    var canonicalQualifiedEmbeddingModelID: String
    var modelFingerprint: String
    var documentEncodingVersion: String
    var documentByteLimit: Int
    var documentFingerprint: String
}

struct RuntimeDocumentSemanticEmbeddingRecord: Equatable, Sendable {
    var key: RuntimeDocumentSemanticEmbeddingKey
    var embedding: [Double]
}

protocol RuntimeDocumentSemanticSearchStoring: AnyObject {
    func approvedSemanticSearchCandidates(
        limit: Int,
        maximumDocumentUTF8Bytes: Int
    ) throws -> [RuntimeDocumentSemanticCandidate]
    func approvedSemanticSearchCandidates(
        limit: Int,
        maximumDocumentUTF8Bytes: Int,
        if shouldContinue: @escaping @Sendable () -> Bool
    ) throws -> [RuntimeDocumentSemanticCandidate]
    func cachedDocumentSemanticEmbeddings(
        for keys: [RuntimeDocumentSemanticEmbeddingKey]
    ) throws -> [RuntimeDocumentSemanticEmbeddingRecord]
    func upsertDocumentSemanticEmbeddings(
        _ records: [RuntimeDocumentSemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws
    func beginApprovedSemanticAccess(
        candidateIdentities: [RuntimeDocumentSemanticCandidateIdentity],
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> Set<RuntimeDocumentSemanticCandidateIdentity>
    func commitApprovedSemanticQuery(
        candidateIdentities: [RuntimeDocumentSemanticCandidateIdentity],
        maximumResultCount: Int,
        actorDeviceID: String?,
        timestamp: Date,
        if shouldCommit: @Sendable () -> Bool
    ) throws -> Set<RuntimeDocumentSemanticCandidateIdentity>
}

extension RuntimeDocumentSemanticSearchStoring {
    func approvedSemanticSearchCandidates(
        limit: Int,
        maximumDocumentUTF8Bytes: Int,
        if shouldContinue: @escaping @Sendable () -> Bool
    ) throws -> [RuntimeDocumentSemanticCandidate] {
        guard shouldContinue() else { throw CancellationError() }
        let candidates = try approvedSemanticSearchCandidates(
            limit: limit,
            maximumDocumentUTF8Bytes: maximumDocumentUTF8Bytes
        )
        guard shouldContinue() else { throw CancellationError() }
        return candidates
    }
}

enum RuntimeDocumentSemanticEmbeddingCacheError: Error, Equatable, LocalizedError {
    case failure(String)
    case staleSource

    var errorDescription: String? {
        switch self {
        case .failure(let message): message
        case .staleSource: "The approved document source changed before its semantic cache was committed."
        }
    }
}

enum RuntimeSemanticDocumentSearch {
    static let maximumCandidateCount = 200
    static let maximumDocumentUTF8Bytes = 4_096
    static let maximumEmbeddingBatchCount = 64
    static let maximumEmbeddingBatchUTF8Bytes = 262_144
    static let maximumCandidateRowScanMultiplier = 4
    static let documentEncodingVersion = "runtime-document-semantic-chunk-v1"

    static func persistentModelFingerprint(
        model: ModelInfo,
        requestedQualifiedModelID: String
    ) -> String? {
        RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: model,
            requestedQualifiedModelID: requestedQualifiedModelID
        )
    }

    static func candidate(
        document: RuntimeDocumentIndexDocument,
        chunk: RuntimeDocumentIndexChunk,
        sourceRevision: String,
        maximumDocumentUTF8Bytes: Int = maximumDocumentUTF8Bytes
    ) -> RuntimeDocumentSemanticCandidate? {
        let documentByteLimit = max(1, min(maximumDocumentUTF8Bytes, Self.maximumDocumentUTF8Bytes))
        let semanticDocument = utf8Prefix(chunk.text, maximumBytes: documentByteLimit)
        guard !semanticDocument.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return nil
        }
        return RuntimeDocumentSemanticCandidate(
            document: document,
            chunk: chunk,
            sourceRevision: sourceRevision,
            semanticDocument: semanticDocument,
            documentByteLimit: documentByteLimit,
            documentFingerprint: fingerprint(fields: [
                documentEncodingVersion,
                String(documentByteLimit),
                semanticDocument
            ])
        )
    }

    static func cacheKey(
        candidate: RuntimeDocumentSemanticCandidate,
        canonicalQualifiedEmbeddingModelID: String,
        modelFingerprint: String
    ) -> RuntimeDocumentSemanticEmbeddingKey {
        RuntimeDocumentSemanticEmbeddingKey(
            documentID: candidate.document.id,
            chunkID: candidate.chunk.id,
            sourceRevision: candidate.sourceRevision,
            canonicalQualifiedEmbeddingModelID: canonicalQualifiedEmbeddingModelID,
            modelFingerprint: modelFingerprint,
            documentEncodingVersion: documentEncodingVersion,
            documentByteLimit: candidate.documentByteLimit,
            documentFingerprint: candidate.documentFingerprint
        )
    }

    static func rankedResults(
        candidates: [RuntimeDocumentSemanticCandidate],
        query: String,
        queryEmbedding: [Double],
        candidateEmbeddings: [[Double]],
        limit: Int,
        maxSnippetCharacters: Int
    ) throws -> [RuntimeDocumentSearchResult] {
        guard queryEmbedding.isValidSemanticEmbedding else {
            throw RuntimeSemanticDocumentSearchError.invalidQueryEmbedding
        }
        guard candidateEmbeddings.count == candidates.count else {
            throw RuntimeSemanticDocumentSearchError.embeddingCountMismatch
        }
        let terms = runtimeDocumentSearchTerms(query)
        let snippetLimit = max(1, min(
            maxSnippetCharacters,
            runtimeDocumentIndexSnippetCharacterLimitCeiling
        ))
        let resultLimit = max(0, min(limit, runtimeDocumentIndexQueryLimitCeiling))
        let scored = try zip(candidates, candidateEmbeddings).map { candidate, embedding in
            guard embedding.count == queryEmbedding.count,
                  embedding.isValidSemanticEmbedding else {
                throw RuntimeSemanticDocumentSearchError.invalidCandidateEmbedding
            }
            return (candidate: candidate, score: cosineSimilarity(queryEmbedding, embedding))
        }
        return scored
            .sorted { lhs, rhs in
                if lhs.score != rhs.score { return lhs.score > rhs.score }
                if lhs.candidate.document.displayName != rhs.candidate.document.displayName {
                    return lhs.candidate.document.displayName < rhs.candidate.document.displayName
                }
                if lhs.candidate.document.id != rhs.candidate.document.id {
                    return lhs.candidate.document.id < rhs.candidate.document.id
                }
                return lhs.candidate.chunk.chunkIndex < rhs.candidate.chunk.chunkIndex
            }
            .prefix(resultLimit)
            .enumerated()
            .map { offset, scoredCandidate in
                let candidate = scoredCandidate.candidate
                let searchableText = candidate.chunk.text.lowercased()
                let matchedTerms = terms.filter { searchableText.contains($0) }
                return RuntimeDocumentSearchResult(
                    document: candidate.document,
                    chunk: candidate.chunk,
                    sourceAnchorID: runtimeDocumentSourceAnchorID(
                        document: candidate.document,
                        chunk: candidate.chunk
                    ),
                    rank: offset + 1,
                    matchedTerms: matchedTerms,
                    snippet: String(candidate.chunk.text.prefix(snippetLimit)),
                    matchKind: .semantic
                )
            }
    }

    private static func utf8Prefix(_ text: String, maximumBytes: Int) -> String {
        guard text.utf8.count > maximumBytes else { return text }
        var byteCount = 0
        var end = text.startIndex
        while end < text.endIndex {
            let next = text.index(after: end)
            let characterBytes = text[end..<next].utf8.count
            guard byteCount + characterBytes <= maximumBytes else { break }
            byteCount += characterBytes
            end = next
        }
        return String(text[..<end])
    }

    private static func fingerprint(fields: [String]) -> String {
        var hasher = SHA256()
        for field in fields {
            let data = Data(field.utf8)
            var length = UInt64(data.count).bigEndian
            withUnsafeBytes(of: &length) { hasher.update(data: Data($0)) }
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    private static func cosineSimilarity(_ lhs: [Double], _ rhs: [Double]) -> Double {
        let lhsScale = lhs.reduce(0.0) { max($0, abs($1)) }
        let rhsScale = rhs.reduce(0.0) { max($0, abs($1)) }
        guard lhsScale > 0, rhsScale > 0 else { return -1 }

        var dotProduct = 0.0
        var lhsMagnitudeSquared = 0.0
        var rhsMagnitudeSquared = 0.0
        for index in lhs.indices {
            let scaledLHS = lhs[index] / lhsScale
            let scaledRHS = rhs[index] / rhsScale
            dotProduct += scaledLHS * scaledRHS
            lhsMagnitudeSquared += scaledLHS * scaledLHS
            rhsMagnitudeSquared += scaledRHS * scaledRHS
        }
        let denominator = sqrt(lhsMagnitudeSquared) * sqrt(rhsMagnitudeSquared)
        guard denominator.isFinite, denominator > 0 else { return -1 }
        return max(-1, min(1, dotProduct / denominator))
    }
}

enum RuntimeSemanticDocumentSearchError: Error, Equatable {
    case invalidQueryEmbedding
    case embeddingCountMismatch
    case invalidCandidateEmbedding
}

final class SQLiteRuntimeDocumentSemanticEmbeddingCache: @unchecked Sendable {
    private let databaseURL: URL
    private let rowLimitPerModel: Int
    private let byteLimitPerModel: Int
    private let totalByteLimit: Int
    private let lock = NSLock()
    var onBeforeCommit: (@Sendable () -> Void)?
    var onCandidateRowRead: (@Sendable () -> Void)?
    var onCandidateSQLWillExecute: (@Sendable () -> Void)?
    var onCandidateSQLProgress: (@Sendable () -> Void)?

    init(
        databaseURL: URL = SQLiteRuntimeDocumentIndexStore.defaultDatabaseURL(),
        rowLimitPerModel: Int = 2_000,
        byteLimitPerModel: Int = 32 * 1_024 * 1_024,
        totalByteLimit: Int = 64 * 1_024 * 1_024
    ) {
        self.databaseURL = databaseURL
        self.rowLimitPerModel = max(1, rowLimitPerModel)
        self.byteLimitPerModel = max(MemoryLayout<Double>.size, byteLimitPerModel)
        self.totalByteLimit = max(self.byteLimitPerModel, totalByteLimit)
    }

    func approvedCandidates(
        limit: Int = RuntimeSemanticDocumentSearch.maximumCandidateCount,
        maximumDocumentUTF8Bytes: Int = RuntimeSemanticDocumentSearch.maximumDocumentUTF8Bytes,
        if shouldContinue: @escaping @Sendable () -> Bool = { true }
    ) throws -> [RuntimeDocumentSemanticCandidate] {
        let effectiveLimit = max(0, min(limit, RuntimeSemanticDocumentSearch.maximumCandidateCount))
        guard effectiveLimit > 0, FileManager.default.fileExists(atPath: databaseURL.path) else {
            return []
        }
        return try lock.withLock {
            try withDatabase { database in
                let progressCancellation = SQLiteRuntimeDocumentProgressCancellation(
                    shouldContinue,
                    onProgress: onCandidateSQLProgress
                )
                let progressContext = Unmanaged.passRetained(progressCancellation).toOpaque()
                sqlite3_progress_handler(
                    database,
                    1_000,
                    runtimeDocumentProgressCancellationHandler,
                    progressContext
                )
                defer {
                    sqlite3_progress_handler(database, 0, nil, nil)
                    Unmanaged<SQLiteRuntimeDocumentProgressCancellation>
                        .fromOpaque(progressContext)
                        .release()
                }
                try Self.checkCancellation(shouldContinue)
                try enforceApprovedSourceLimit(database, shouldContinue: shouldContinue)
                onCandidateSQLWillExecute?()
                let approvedDocumentStatement = try Self.prepare(
                    database,
                    """
                    SELECT d.document_id, d.display_name, d.mime_type,
                           d.content_fingerprint, d.extracted_character_count,
                           d.chunk_count, d.quality, a.source_revision
                    FROM runtime_document_index_documents d
                    JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
                    WHERE a.approval_scope = 'runtime_shared'
                      AND EXISTS (
                          SELECT 1
                          FROM runtime_document_index_chunks usable
                          WHERE usable.document_id = d.document_id
                            AND length(trim(usable.text, ' ' || char(9) || char(10) || char(13))) > 0
                      )
                    ORDER BY d.document_id ASC
                    LIMIT ?
                    """
                )
                defer { sqlite3_finalize(approvedDocumentStatement) }
                try Self.bindInt(effectiveLimit, to: approvedDocumentStatement, at: 1)

                var approvedDocuments: [(RuntimeDocumentIndexDocument, String)] = []
                while true {
                    try Self.checkCancellation(shouldContinue)
                    let result = sqlite3_step(approvedDocumentStatement)
                    if result == SQLITE_DONE { break }
                    if result == SQLITE_INTERRUPT, !shouldContinue() { throw CancellationError() }
                    guard result == SQLITE_ROW else {
                        throw Self.failure(database, "Could not read approved semantic document sources.")
                    }
                    let document = RuntimeDocumentIndexDocument(
                        id: try Self.columnText(approvedDocumentStatement, 0),
                        displayName: try Self.columnText(approvedDocumentStatement, 1),
                        mimeType: try Self.columnText(approvedDocumentStatement, 2),
                        contentFingerprint: try Self.columnText(approvedDocumentStatement, 3),
                        extractedCharacterCount: Int(sqlite3_column_int64(approvedDocumentStatement, 4)),
                        chunkCount: Int(sqlite3_column_int64(approvedDocumentStatement, 5)),
                        quality: try Self.documentQuality(Self.columnText(approvedDocumentStatement, 6))
                    )
                    approvedDocuments.append((
                        document,
                        try Self.columnText(approvedDocumentStatement, 7)
                    ))
                }
                approvedDocuments.sort {
                    if $0.0.displayName != $1.0.displayName {
                        return $0.0.displayName < $1.0.displayName
                    }
                    return $0.0.id < $1.0.id
                }
                return try approvedCandidates(
                    for: approvedDocuments,
                    effectiveLimit: effectiveLimit,
                    maximumDocumentUTF8Bytes: maximumDocumentUTF8Bytes,
                    database: database,
                    shouldContinue: shouldContinue
                )
            }
        }
    }

    private func approvedCandidates(
        for approvedDocuments: [(RuntimeDocumentIndexDocument, String)],
        effectiveLimit: Int,
        maximumDocumentUTF8Bytes: Int,
        database: OpaquePointer,
        shouldContinue: @escaping @Sendable () -> Bool
    ) throws -> [RuntimeDocumentSemanticCandidate] {
        guard !approvedDocuments.isEmpty else { return [] }
        let totalRowBudget = effectiveLimit * RuntimeSemanticDocumentSearch.maximumCandidateRowScanMultiplier
        let baseBudget = totalRowBudget / approvedDocuments.count
        let remainder = totalRowBudget % approvedDocuments.count
        var rowsByDocument: [[RuntimeDocumentSemanticCandidate]] = []
        rowsByDocument.reserveCapacity(approvedDocuments.count)

        for (index, approvedDocument) in approvedDocuments.enumerated() {
            try Self.checkCancellation(shouldContinue)
            let rowBudget = min(effectiveLimit, baseBudget + (index < remainder ? 1 : 0))
            guard rowBudget > 0 else {
                rowsByDocument.append([])
                continue
            }
            let statement = try Self.prepare(
                database,
                """
                SELECT chunk_id, document_id, document_display_name, document_mime_type,
                       chunk_index, start_character_offset, end_character_offset, text
                FROM runtime_document_index_chunks
                WHERE document_id = ?
                  AND length(trim(text, ' ' || char(9) || char(10) || char(13))) > 0
                ORDER BY chunk_index ASC, chunk_id ASC
                LIMIT ?
                """
            )
            defer { sqlite3_finalize(statement) }
            try Self.bindText(approvedDocument.0.id, to: statement, at: 1)
            try Self.bindInt(rowBudget, to: statement, at: 2)
            var documentRows: [RuntimeDocumentSemanticCandidate] = []
            while true {
                try Self.checkCancellation(shouldContinue)
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }
                if result == SQLITE_INTERRUPT, !shouldContinue() { throw CancellationError() }
                guard result == SQLITE_ROW else {
                    throw Self.failure(database, "Could not read approved semantic document candidates.")
                }
                onCandidateRowRead?()
                let chunk = RuntimeDocumentIndexChunk(
                    id: try Self.columnText(statement, 0),
                    documentID: try Self.columnText(statement, 1),
                    documentDisplayName: try Self.columnText(statement, 2),
                    documentMimeType: try Self.columnText(statement, 3),
                    chunkIndex: Int(sqlite3_column_int64(statement, 4)),
                    startCharacterOffset: Int(sqlite3_column_int64(statement, 5)),
                    endCharacterOffset: Int(sqlite3_column_int64(statement, 6)),
                    text: try Self.columnText(statement, 7)
                )
                if let candidate = RuntimeSemanticDocumentSearch.candidate(
                    document: approvedDocument.0,
                    chunk: chunk,
                    sourceRevision: approvedDocument.1,
                    maximumDocumentUTF8Bytes: maximumDocumentUTF8Bytes
                ) {
                    documentRows.append(candidate)
                }
            }
            rowsByDocument.append(documentRows)
        }

        var candidates: [RuntimeDocumentSemanticCandidate] = []
        for round in 0..<effectiveLimit {
            for documentRows in rowsByDocument where round < documentRows.count {
                candidates.append(documentRows[round])
                if candidates.count == effectiveLimit { return candidates }
            }
        }
        return candidates
    }

    private static func checkCancellation(
        _ shouldContinue: @escaping @Sendable () -> Bool
    ) throws {
        guard shouldContinue() else { throw CancellationError() }
    }

    private func enforceApprovedSourceLimit(
        _ database: OpaquePointer,
        shouldContinue: @escaping @Sendable () -> Bool
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id
            FROM runtime_document_source_approvals
            WHERE approval_scope = 'runtime_shared'
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindInt(runtimeDocumentApprovedSourceLimitCeiling + 1, to: statement, at: 1)
        var count = 0
        while true {
            try Self.checkCancellation(shouldContinue)
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            if result == SQLITE_INTERRUPT, !shouldContinue() { throw CancellationError() }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not enforce the approved document source limit.")
            }
            count += 1
        }
        guard count <= runtimeDocumentApprovedSourceLimitCeiling else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "The approved runtime document source limit was exceeded."
            )
        }
    }

    func cachedEmbeddings(
        for keys: [RuntimeDocumentSemanticEmbeddingKey]
    ) throws -> [RuntimeDocumentSemanticEmbeddingRecord] {
        guard !keys.isEmpty, FileManager.default.fileExists(atPath: databaseURL.path) else { return [] }
        guard keys.count <= RuntimeSemanticDocumentSearch.maximumEmbeddingBatchCount else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "A semantic document cache read may contain at most 64 keys."
            )
        }
        let uniqueKeys = Array(Set(keys))
        try uniqueKeys.forEach(Self.validate)
        return try lock.withLock {
            try withDatabase { database in
                try uniqueKeys.compactMap { try cachedEmbedding(for: $0, database: database) }
            }
        }
    }

    func upsertEmbeddings(
        _ records: [RuntimeDocumentSemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws {
        guard !records.isEmpty else { return }
        guard records.count <= RuntimeSemanticDocumentSearch.maximumEmbeddingBatchCount else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "A semantic document embedding batch may contain at most 64 records."
            )
        }
        try records.forEach(Self.validate)
        try lock.withLock {
            guard shouldCommit() else { return }
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    guard shouldCommit() else {
                        try Self.execute(database, "ROLLBACK")
                        return
                    }
                    for record in records {
                        try Self.requireCommit(shouldCommit)
                        guard try currentSourceMatches(record.key, database: database) else {
                            throw RuntimeDocumentSemanticEmbeddingCacheError.staleSource
                        }
                        try upsert(record, database: database)
                    }
                    for modelID in Set(records.map(\.key.canonicalQualifiedEmbeddingModelID)) {
                        try Self.requireCommit(shouldCommit)
                        try enforceRowLimit(
                            modelID: modelID,
                            database: database,
                            shouldCommit: shouldCommit
                        )
                        try enforceByteLimit(
                            byteLimitPerModel,
                            modelID: modelID,
                            database: database,
                            shouldCommit: shouldCommit
                        )
                    }
                    try enforceByteLimit(
                        totalByteLimit,
                        modelID: nil,
                        database: database,
                        shouldCommit: shouldCommit
                    )
                    onBeforeCommit?()
                    try Self.requireCommit(shouldCommit)
                    try Self.execute(database, "COMMIT")
                } catch is RuntimeDocumentSemanticEmbeddingCacheWriteCancelled {
                    try? Self.execute(database, "ROLLBACK")
                    return
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    func storedRowCount() throws -> Int {
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return 0 }
        return try lock.withLock {
            try withDatabase { database in
                try Self.scalarInt(
                    database,
                    sql: "SELECT COUNT(*) FROM runtime_document_semantic_embeddings"
                )
            }
        }
    }

    func storedVectorByteCount(modelID: String? = nil) throws -> Int {
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return 0 }
        return try lock.withLock {
            try withDatabase { database in
                if let modelID {
                    return try Self.scalarInt(
                        database,
                        sql: "SELECT COALESCE(SUM(length(vector_blob)), 0) FROM runtime_document_semantic_embeddings WHERE embedding_model_id = ?",
                        bind: { try Self.bindText(modelID, to: $0, at: 1) }
                    )
                }
                return try Self.scalarInt(
                    database,
                    sql: "SELECT COALESCE(SUM(length(vector_blob)), 0) FROM runtime_document_semantic_embeddings"
                )
            }
        }
    }

    private func currentSourceMatches(
        _ key: RuntimeDocumentSemanticEmbeddingKey,
        database: OpaquePointer
    ) throws -> Bool {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality,
                   c.chunk_id, c.document_id, c.document_display_name, c.document_mime_type,
                   c.chunk_index, c.start_character_offset, c.end_character_offset, c.text,
                   a.source_revision
            FROM runtime_document_index_chunks c
            JOIN runtime_document_index_documents d ON d.document_id = c.document_id
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE d.document_id = ? AND c.chunk_id = ?
              AND a.approval_scope = 'runtime_shared' AND a.source_revision = ?
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(key.documentID, to: statement, at: 1)
        try Self.bindText(key.chunkID, to: statement, at: 2)
        try Self.bindText(key.sourceRevision, to: statement, at: 3)
        guard sqlite3_step(statement) == SQLITE_ROW else { return false }
        let document = RuntimeDocumentIndexDocument(
            id: try Self.columnText(statement, 0),
            displayName: try Self.columnText(statement, 1),
            mimeType: try Self.columnText(statement, 2),
            contentFingerprint: try Self.columnText(statement, 3),
            extractedCharacterCount: Int(sqlite3_column_int64(statement, 4)),
            chunkCount: Int(sqlite3_column_int64(statement, 5)),
            quality: try Self.documentQuality(Self.columnText(statement, 6))
        )
        let chunk = RuntimeDocumentIndexChunk(
            id: try Self.columnText(statement, 7),
            documentID: try Self.columnText(statement, 8),
            documentDisplayName: try Self.columnText(statement, 9),
            documentMimeType: try Self.columnText(statement, 10),
            chunkIndex: Int(sqlite3_column_int64(statement, 11)),
            startCharacterOffset: Int(sqlite3_column_int64(statement, 12)),
            endCharacterOffset: Int(sqlite3_column_int64(statement, 13)),
            text: try Self.columnText(statement, 14)
        )
        guard key.documentEncodingVersion == RuntimeSemanticDocumentSearch.documentEncodingVersion,
              let candidate = RuntimeSemanticDocumentSearch.candidate(
                document: document,
                chunk: chunk,
                sourceRevision: try Self.columnText(statement, 15),
                maximumDocumentUTF8Bytes: key.documentByteLimit
              ) else { return false }
        return candidate.documentFingerprint == key.documentFingerprint
    }

    private func cachedEmbedding(
        for key: RuntimeDocumentSemanticEmbeddingKey,
        database: OpaquePointer
    ) throws -> RuntimeDocumentSemanticEmbeddingRecord? {
        let statement = try Self.prepare(
            database,
            """
            SELECT dimension, vector_blob
            FROM runtime_document_semantic_embeddings
            WHERE document_id = ? AND chunk_id = ? AND source_revision = ?
              AND embedding_model_id = ? AND model_fingerprint = ?
              AND document_encoding_version = ? AND document_byte_limit = ?
              AND document_fingerprint = ?
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        for (index, value) in [
            key.documentID,
            key.chunkID,
            key.sourceRevision,
            key.canonicalQualifiedEmbeddingModelID,
            key.modelFingerprint,
            key.documentEncodingVersion
        ].enumerated() {
            try Self.bindText(value, to: statement, at: Int32(index + 1))
        }
        try Self.bindInt(key.documentByteLimit, to: statement, at: 7)
        try Self.bindText(key.documentFingerprint, to: statement, at: 8)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW else {
            throw Self.failure(database, "Could not read a semantic document embedding.")
        }
        let dimension = Int(sqlite3_column_int64(statement, 0))
        let blobSize = Int(sqlite3_column_bytes(statement, 1))
        let blob = sqlite3_column_blob(statement, 1).map { Data(bytes: $0, count: blobSize) }
        guard sqlite3_column_type(statement, 0) == SQLITE_INTEGER,
              sqlite3_column_type(statement, 1) == SQLITE_BLOB,
              let blob,
              let embedding = Self.decode(blob, dimension: dimension) else {
            return nil
        }
        return RuntimeDocumentSemanticEmbeddingRecord(key: key, embedding: embedding)
    }

    private func upsert(
        _ record: RuntimeDocumentSemanticEmbeddingRecord,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_semantic_embeddings(
                document_id, chunk_id, source_revision, embedding_model_id,
                model_fingerprint, document_encoding_version, document_byte_limit,
                document_fingerprint, dimension, vector_blob, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                document_id, chunk_id, source_revision, embedding_model_id,
                model_fingerprint, document_encoding_version, document_fingerprint
            ) DO UPDATE SET
                dimension = excluded.dimension,
                vector_blob = excluded.vector_blob,
                created_at = excluded.created_at
            """
        )
        defer { sqlite3_finalize(statement) }
        let key = record.key
        for (index, value) in [
            key.documentID,
            key.chunkID,
            key.sourceRevision,
            key.canonicalQualifiedEmbeddingModelID,
            key.modelFingerprint,
            key.documentEncodingVersion
        ].enumerated() {
            try Self.bindText(value, to: statement, at: Int32(index + 1))
        }
        try Self.bindInt(key.documentByteLimit, to: statement, at: 7)
        try Self.bindText(key.documentFingerprint, to: statement, at: 8)
        try Self.bindInt(record.embedding.count, to: statement, at: 9)
        try Self.bindBlob(Self.encode(record.embedding), to: statement, at: 10)
        try Self.bindDouble(Date().timeIntervalSince1970, to: statement, at: 11)
        try Self.stepDone(statement, database: database)
    }

    private func enforceRowLimit(
        modelID: String,
        database: OpaquePointer,
        shouldCommit: @Sendable () -> Bool
    ) throws {
        try Self.requireCommit(shouldCommit)
        let statement = try Self.prepare(
            database,
            """
            DELETE FROM runtime_document_semantic_embeddings
            WHERE rowid IN (
                SELECT rowid FROM runtime_document_semantic_embeddings
                WHERE embedding_model_id = ?
                ORDER BY created_at DESC, document_id ASC, chunk_id ASC
                LIMIT -1 OFFSET ?
            )
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(modelID, to: statement, at: 1)
        try Self.bindInt(rowLimitPerModel, to: statement, at: 2)
        try Self.stepDone(statement, database: database)
    }

    private func enforceByteLimit(
        _ limit: Int,
        modelID: String?,
        database: OpaquePointer,
        shouldCommit: @Sendable () -> Bool
    ) throws {
        while try vectorByteCount(modelID: modelID, database: database) > limit {
            try Self.requireCommit(shouldCommit)
            try deleteOldestEmbedding(modelID: modelID, database: database)
        }
    }

    private func deleteOldestEmbedding(modelID: String?, database: OpaquePointer) throws {
        let statement = try Self.prepare(
            database,
            """
            DELETE FROM runtime_document_semantic_embeddings
            WHERE rowid = (
                SELECT rowid FROM runtime_document_semantic_embeddings
                \(modelID == nil ? "" : "WHERE embedding_model_id = ?")
                ORDER BY created_at ASC, document_id ASC, chunk_id ASC
                LIMIT 1
            )
            """
        )
        defer { sqlite3_finalize(statement) }
        if let modelID {
            try Self.bindText(modelID, to: statement, at: 1)
        }
        try Self.stepDone(statement, database: database)
    }

    private func vectorByteCount(modelID: String?, database: OpaquePointer) throws -> Int {
        if let modelID {
            return try Self.scalarInt(
                database,
                sql: "SELECT COALESCE(SUM(length(vector_blob)), 0) FROM runtime_document_semantic_embeddings WHERE embedding_model_id = ?",
                bind: { try Self.bindText(modelID, to: $0, at: 1) }
            )
        }
        return try Self.scalarInt(
            database,
            sql: "SELECT COALESCE(SUM(length(vector_blob)), 0) FROM runtime_document_semantic_embeddings"
        )
    }

    private func withDatabase<T>(_ body: (OpaquePointer) throws -> T) throws -> T {
        try RuntimeEventLogFileProtection.prepareDirectory(for: databaseURL)
        if FileManager.default.fileExists(atPath: databaseURL.path) {
            try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        var database: OpaquePointer?
        let flags = SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX
        guard sqlite3_open_v2(databaseURL.path, &database, flags, nil) == SQLITE_OK,
              let openedDatabase = database else {
            if let database { sqlite3_close(database) }
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "Could not open the semantic document cache."
            )
        }
        defer {
            sqlite3_close(openedDatabase)
            try? RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        guard sqlite3_busy_timeout(openedDatabase, 5_000) == SQLITE_OK else {
            throw Self.failure(openedDatabase, "Could not configure semantic document cache concurrency.")
        }
        try Self.execute(openedDatabase, "PRAGMA foreign_keys = ON")
        try Self.ensureSchema(openedDatabase)
        return try body(openedDatabase)
    }

    private static func ensureSchema(_ database: OpaquePointer) throws {
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_semantic_embeddings(
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                source_revision TEXT NOT NULL,
                embedding_model_id TEXT NOT NULL,
                model_fingerprint TEXT NOT NULL,
                document_encoding_version TEXT NOT NULL,
                document_byte_limit INTEGER NOT NULL DEFAULT 4096,
                document_fingerprint TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                vector_blob BLOB NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY(
                    document_id, chunk_id, source_revision, embedding_model_id,
                    model_fingerprint, document_encoding_version, document_fingerprint
                ),
                FOREIGN KEY(document_id) REFERENCES runtime_document_index_documents(document_id) ON DELETE CASCADE,
                FOREIGN KEY(chunk_id) REFERENCES runtime_document_index_chunks(chunk_id) ON DELETE CASCADE
            )
            """
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_document_semantic_model_created ON runtime_document_semantic_embeddings(embedding_model_id, created_at ASC)"
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_document_semantic_created ON runtime_document_semantic_embeddings(created_at ASC)"
        )
        if try !tableHasColumn(
            database,
            table: "runtime_document_semantic_embeddings",
            column: "document_byte_limit"
        ) {
            try execute(
                database,
                "ALTER TABLE runtime_document_semantic_embeddings ADD COLUMN document_byte_limit INTEGER NOT NULL DEFAULT 4096"
            )
        }
    }

    private static func validate(_ key: RuntimeDocumentSemanticEmbeddingKey) throws {
        let nonblank = [
            key.documentID,
            key.chunkID,
            key.canonicalQualifiedEmbeddingModelID,
            key.documentEncodingVersion
        ].allSatisfy { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        guard nonblank,
              key.documentEncodingVersion == RuntimeSemanticDocumentSearch.documentEncodingVersion,
              key.documentByteLimit > 0,
              key.documentByteLimit <= RuntimeSemanticDocumentSearch.maximumDocumentUTF8Bytes,
              isLowercaseHexDigest(key.sourceRevision),
              isLowercaseHexDigest(key.modelFingerprint),
              isLowercaseHexDigest(key.documentFingerprint) else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "A semantic document embedding key is invalid."
            )
        }
    }

    private static func requireCommit(_ shouldCommit: @Sendable () -> Bool) throws {
        guard shouldCommit() else {
            throw RuntimeDocumentSemanticEmbeddingCacheWriteCancelled()
        }
    }

    private static func validate(_ record: RuntimeDocumentSemanticEmbeddingRecord) throws {
        try validate(record.key)
        guard !record.embedding.isEmpty,
              record.embedding.count <= 65_536,
              record.embedding.allSatisfy(\.isFinite),
              record.embedding.contains(where: { $0 != 0 }) else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "A semantic document embedding vector is invalid."
            )
        }
    }

    private static func isLowercaseHexDigest(_ value: String) -> Bool {
        value.count == 64 && value.unicodeScalars.allSatisfy {
            CharacterSet(charactersIn: "0123456789abcdef").contains($0)
        }
    }

    private static func documentQuality(_ rawValue: String) throws -> DocumentIngestionQuality {
        guard let quality = DocumentIngestionQuality(rawValue: rawValue) else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "The semantic document candidate quality is invalid."
            )
        }
        return quality
    }

    private static func encode(_ embedding: [Double]) -> Data {
        var data = Data(capacity: embedding.count * MemoryLayout<UInt64>.size)
        for value in embedding {
            var bits = value.bitPattern.littleEndian
            withUnsafeBytes(of: &bits) { data.append(contentsOf: $0) }
        }
        return data
    }

    private static func decode(_ data: Data, dimension: Int) -> [Double]? {
        guard dimension > 0,
              dimension <= 65_536,
              data.count == dimension * MemoryLayout<Double>.size else { return nil }
        var embedding: [Double] = []
        embedding.reserveCapacity(dimension)
        for offset in stride(from: 0, to: data.count, by: MemoryLayout<UInt64>.size) {
            var bits: UInt64 = 0
            _ = withUnsafeMutableBytes(of: &bits) { destination in
                data.copyBytes(to: destination, from: offset..<(offset + MemoryLayout<UInt64>.size))
            }
            embedding.append(Double(bitPattern: UInt64(littleEndian: bits)))
        }
        guard embedding.allSatisfy(\.isFinite), embedding.contains(where: { $0 != 0 }) else {
            return nil
        }
        return embedding
    }

    private static func scalarInt(
        _ database: OpaquePointer,
        sql: String,
        bind: ((OpaquePointer) throws -> Void)? = nil
    ) throws -> Int {
        let statement = try prepare(database, sql)
        defer { sqlite3_finalize(statement) }
        try bind?(statement)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw failure(database, "Could not read a semantic document cache count.")
        }
        return Int(sqlite3_column_int64(statement, 0))
    }

    private static func tableHasColumn(
        _ database: OpaquePointer,
        table: String,
        column: String
    ) throws -> Bool {
        let statement = try prepare(database, "PRAGMA table_info(\(table))")
        defer { sqlite3_finalize(statement) }
        while sqlite3_step(statement) == SQLITE_ROW {
            if try columnText(statement, 1) == column { return true }
        }
        return false
    }

    private static func execute(_ database: OpaquePointer, _ sql: String) throws {
        var message: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(database, sql, nil, nil, &message) == SQLITE_OK else {
            defer { sqlite3_free(message) }
            let detail = message.map { String(cString: $0) } ?? "unknown SQLite failure"
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(detail)
        }
    }

    private static func prepare(_ database: OpaquePointer, _ sql: String) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw failure(database, "Could not prepare a semantic document cache statement.")
        }
        return statement
    }

    private static func bindText(_ value: String, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_text(statement, index, value, -1, SQLITE_TRANSIENT_DOCUMENT) == SQLITE_OK else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "Could not bind semantic document cache text."
            )
        }
    }

    private static func bindInt(_ value: Int, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_int64(statement, index, sqlite3_int64(value)) == SQLITE_OK else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "Could not bind a semantic document cache integer."
            )
        }
    }

    private static func bindDouble(_ value: Double, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_double(statement, index, value) == SQLITE_OK else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "Could not bind a semantic document cache number."
            )
        }
    }

    private static func bindBlob(_ value: Data, to statement: OpaquePointer, at index: Int32) throws {
        let result = value.withUnsafeBytes { bytes in
            sqlite3_bind_blob(
                statement,
                index,
                bytes.baseAddress,
                Int32(value.count),
                SQLITE_TRANSIENT_DOCUMENT
            )
        }
        guard result == SQLITE_OK else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "Could not bind a semantic document cache vector."
            )
        }
    }

    private static func columnText(_ statement: OpaquePointer, _ index: Int32) throws -> String {
        guard sqlite3_column_type(statement, index) == SQLITE_TEXT,
              let value = sqlite3_column_text(statement, index) else {
            throw RuntimeDocumentSemanticEmbeddingCacheError.failure(
                "The semantic document cache row contains invalid text."
            )
        }
        return String(cString: value)
    }

    private static func stepDone(_ statement: OpaquePointer, database: OpaquePointer) throws {
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw failure(database, "Could not write the semantic document cache.")
        }
    }

    private static func failure(_ database: OpaquePointer, _ prefix: String) -> Error {
        let detail = sqlite3_errmsg(database).map { String(cString: $0) } ?? "unknown SQLite failure"
        return RuntimeDocumentSemanticEmbeddingCacheError.failure("\(prefix) \(detail)")
    }
}

private let SQLITE_TRANSIENT_DOCUMENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

private struct RuntimeDocumentSemanticEmbeddingCacheWriteCancelled: Error {}
