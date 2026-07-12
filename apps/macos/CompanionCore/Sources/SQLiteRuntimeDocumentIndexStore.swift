import DocumentIngestion
import Foundation
import SQLite3

public struct RuntimeDocumentSourceRevisionConflictError: Error, Equatable, Sendable {}

public final class SQLiteRuntimeDocumentIndexStore: RuntimeDocumentSemanticSearchStoring, @unchecked Sendable {
    private let databaseURL: URL
    private let semanticEmbeddingCache: SQLiteRuntimeDocumentSemanticEmbeddingCache
    private let sourceAuditEventLimit: Int
    private let lock = NSLock()
    var onBeforeApprovedReadAuditCommit: (@Sendable () -> Void)?
    var onBeforeApprovedSemanticQueryAuditCommit: (@Sendable () -> Void)?
    var onBeforeTrustedSourceApprovalCommit: (@Sendable () -> Void)?
    var onBeforeTrustedSourceContextAuditCommit: (@Sendable () -> Void)?

    public init(
        databaseURL: URL = SQLiteRuntimeDocumentIndexStore.defaultDatabaseURL(),
        sourceAuditEventLimit: Int = 100_000
    ) {
        self.databaseURL = databaseURL
        self.semanticEmbeddingCache = SQLiteRuntimeDocumentSemanticEmbeddingCache(databaseURL: databaseURL)
        self.sourceAuditEventLimit = max(
            1,
            min(sourceAuditEventLimit, runtimeDocumentSourceAuditEventLimitCeiling)
        )
    }

    public static func defaultDatabaseURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-document-index.sqlite", isDirectory: false)
    }

    @discardableResult
    public func replaceDocument(
        result: DocumentIngestionResult,
        documentID requestedDocumentID: String? = nil
    ) throws -> RuntimeDocumentIndexDocument {
        try replaceDocument(
            result: result,
            documentID: requestedDocumentID,
            expectedSourceRevision: nil,
            requiresRevisionMatch: false
        )
    }

    @discardableResult
    public func replaceDocument(
        result: DocumentIngestionResult,
        documentID requestedDocumentID: String,
        ifCurrentSourceRevisionEquals expectedSourceRevision: String?
    ) throws -> RuntimeDocumentIndexDocument {
        try replaceDocument(
            result: result,
            documentID: requestedDocumentID,
            expectedSourceRevision: expectedSourceRevision,
            requiresRevisionMatch: true
        )
    }

    private func replaceDocument(
        result: DocumentIngestionResult,
        documentID requestedDocumentID: String?,
        expectedSourceRevision: String?,
        requiresRevisionMatch: Bool
    ) throws -> RuntimeDocumentIndexDocument {
        let documentID = runtimeDocumentIndexEffectiveDocumentID(
            requestedDocumentID,
            fallback: RuntimeDocumentIndexStore.stableDocumentID(for: result)
        )
        let document = runtimeDocumentIndexDocument(for: result, documentID: documentID)
        let chunks = runtimeDocumentIndexChunks(for: result, documentID: documentID)
        let timestamp = Date()
        let approval = runtimeDocumentHostApproval(
            document: document,
            chunks: chunks,
            timestamp: timestamp
        )

        return try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let currentApproval = try sourceApprovalUnlocked(documentID: documentID, database: database)
                    if requiresRevisionMatch,
                       currentApproval?.sourceRevision != expectedSourceRevision {
                        throw RuntimeDocumentSourceRevisionConflictError()
                    }
                    let wasApproved = currentApproval != nil
                    if !wasApproved,
                       try approvedSourceCountUnlocked(database) >= runtimeDocumentApprovedSourceLimitCeiling {
                        throw SQLiteRuntimeDocumentIndexStoreError(
                            "The approved runtime document source limit has been reached."
                        )
                    }
                    try deleteDocumentUnlocked(
                        id: documentID,
                        invalidateCitationState: currentApproval?.sourceRevision
                            != approval.sourceRevision,
                        database: database
                    )
                    try insertDocumentUnlocked(document, database: database)
                    for chunk in chunks {
                        try insertChunkUnlocked(chunk, database: database)
                    }
                    try insertSourceApprovalUnlocked(approval, database: database)
                    if wasApproved {
                        try insertSourceAuditUnlocked(
                            runtimeDocumentAuditEvent(
                                action: .reindexed,
                                approval: approval,
                                actorDeviceID: approval.approvedBy,
                                timestamp: timestamp
                            ),
                            database: database
                        )
                    } else {
                        for action in [RuntimeDocumentSourceAuditAction.approved, .indexed] {
                            try insertSourceAuditUnlocked(
                                runtimeDocumentAuditEvent(
                                    action: action,
                                    approval: approval,
                                    actorDeviceID: approval.approvedBy,
                                    timestamp: timestamp
                                ),
                                database: database
                            )
                        }
                    }
                    try Self.execute(database, "COMMIT")
                    return document
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocument(id documentID: String) throws {
        try deleteDocument(
            id: documentID,
            expectedSourceRevision: nil,
            requiresRevisionMatch: false
        )
    }

    public func deleteDocument(
        id documentID: String,
        ifCurrentSourceRevisionEquals expectedSourceRevision: String
    ) throws {
        try deleteDocument(
            id: documentID,
            expectedSourceRevision: expectedSourceRevision,
            requiresRevisionMatch: true
        )
    }

    private func deleteDocument(
        id documentID: String,
        expectedSourceRevision: String?,
        requiresRevisionMatch: Bool
    ) throws {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return }
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    if requiresRevisionMatch {
                        let currentApproval = try sourceApprovalUnlocked(
                            documentID: documentID,
                            database: database
                        )
                        guard currentApproval?.sourceRevision == expectedSourceRevision else {
                            throw RuntimeDocumentSourceRevisionConflictError()
                        }
                    }
                    try revokeAndDeleteDocumentUnlocked(
                        id: documentID,
                        timestamp: Date(),
                        database: database
                    )
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteAllDocuments() throws {
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let approvals = try sourceApprovalsUnlocked(database: database)
                    let timestamp = Date()
                    for approval in approvals {
                        try insertRevocationAuditUnlocked(
                            approval: approval,
                            timestamp: timestamp,
                            database: database
                        )
                    }
                    try deleteAllDocumentsUnlocked(database: database)
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocuments(matchingQuality quality: DocumentIngestionQuality) throws {
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let documentIDs = try documentIDsUnlocked(matchingQuality: quality, database: database)
                    let timestamp = Date()
                    for documentID in documentIDs {
                        try revokeAndDeleteDocumentUnlocked(id: documentID, timestamp: timestamp, database: database)
                    }
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocuments(matchingContentFingerprint contentFingerprint: String) throws {
        guard let contentFingerprint = runtimeDocumentIndexCanonicalContentFingerprint(contentFingerprint) else { return }
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let documentIDs = try documentIDsUnlocked(
                        matchingContentFingerprint: contentFingerprint,
                        database: database
                    )
                    let timestamp = Date()
                    for documentID in documentIDs {
                        try revokeAndDeleteDocumentUnlocked(id: documentID, timestamp: timestamp, database: database)
                    }
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocuments(matchingDisplayName displayName: String) throws {
        guard let displayName = runtimeDocumentIndexCanonicalDisplayName(displayName) else { return }
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let documentIDs = try documentIDsUnlocked(matchingDisplayName: displayName, database: database)
                    let timestamp = Date()
                    for documentID in documentIDs {
                        try revokeAndDeleteDocumentUnlocked(id: documentID, timestamp: timestamp, database: database)
                    }
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocuments(matchingMimeType mimeType: String) throws {
        guard let mimeType = runtimeDocumentIndexCanonicalMimeType(mimeType) else { return }
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let documentIDs = try documentIDsUnlocked(matchingMimeType: mimeType, database: database)
                    let timestamp = Date()
                    for documentID in documentIDs {
                        try revokeAndDeleteDocumentUnlocked(id: documentID, timestamp: timestamp, database: database)
                    }
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func document(id documentID: String) throws -> RuntimeDocumentIndexDocument? {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                try documentUnlocked(id: documentID, database: database)
            }
        }
    }

    public func chunks(
        for documentID: String,
        limit: Int = 200
    ) throws -> [RuntimeDocumentIndexChunk] {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexChunkReadLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try chunksUnlocked(for: documentID, limit: effectiveLimit, database: database)
            }
        }
    }

    public func chunkSummaries(
        for documentID: String,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexChunkSummary] {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexChunkSummaryLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try chunkSummariesUnlocked(for: documentID, limit: effectiveLimit, database: database)
            }
        }
    }

    public func sourceAnchor(id sourceAnchorID: String) throws -> RuntimeDocumentSourceAnchor? {
        guard let sourceAnchorID = runtimeDocumentIndexCanonicalSourceAnchorID(sourceAnchorID) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                try sourceAnchorUnlocked(id: sourceAnchorID, database: database)
            }
        }
    }

    public func documents(limit: Int = 100) throws -> [RuntimeDocumentIndexDocument] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(limit: effectiveLimit, database: database)
            }
        }
    }

    func hostManagedApprovedDocuments(
        limit: Int = runtimeDocumentApprovedSourceLimitCeiling
    ) throws -> [RuntimeDocumentIndexDocument] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentApprovedSourceLimitCeiling
        ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(limit: effectiveLimit, database: database)
            }
        }
    }

    public func documents(
        matchingDisplayName displayName: String,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexDocument] {
        guard let displayName = runtimeDocumentIndexCanonicalDisplayName(displayName),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(matchingDisplayName: displayName, limit: effectiveLimit, database: database)
            }
        }
    }

    public func documents(
        matchingContentFingerprint contentFingerprint: String,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexDocument] {
        guard let contentFingerprint = runtimeDocumentIndexCanonicalContentFingerprint(contentFingerprint),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(
                    matchingContentFingerprint: contentFingerprint,
                    limit: effectiveLimit,
                    database: database
                )
            }
        }
    }

    public func documents(
        matchingMimeType mimeType: String,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexDocument] {
        guard let mimeType = runtimeDocumentIndexCanonicalMimeType(mimeType),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(matchingMimeType: mimeType, limit: effectiveLimit, database: database)
            }
        }
    }

    public func documents(
        matchingQuality quality: DocumentIngestionQuality,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexDocument] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(matchingQuality: quality, limit: effectiveLimit, database: database)
            }
        }
    }

    public func summary() throws -> RuntimeDocumentIndexSummary {
        try lock.withLock {
            try withDatabase { database in
                try summaryUnlocked(database: database)
            }
        }
    }

    public func query(
        _ query: String,
        limit: Int = 10,
        maxSnippetCharacters: Int = 160
    ) throws -> [RuntimeDocumentSearchResult] {
        let terms = runtimeDocumentSearchTerms(query)
        guard !terms.isEmpty,
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexQueryLimitCeiling
              ),
              let effectiveSnippetLimit = runtimeDocumentIndexEffectiveLimit(
                maxSnippetCharacters,
                ceiling: runtimeDocumentIndexSnippetCharacterLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                return try runtimeDocumentSearchResults(
                    from: searchSnapshotUnlocked(database),
                    query: query,
                    limit: effectiveLimit,
                    maxSnippetCharacters: effectiveSnippetLimit
                )
            }
        }
    }

    public func readApprovedCatalog(
        limit: Int,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) throws -> RuntimeDocumentApprovedCatalog {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else {
            return RuntimeDocumentApprovedCatalog(
                documents: [],
                summary: runtimeDocumentIndexSummary([])
            )
        }
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    let documents = try documentsUnlocked(limit: effectiveLimit, database: database)
                    let summary = try summaryUnlocked(database: database)
                    onBeforeApprovedReadAuditCommit?()
                    try insertSourceAuditUnlocked(
                        runtimeDocumentAuditEvent(
                            action: .catalogListed,
                            actorDeviceID: actorDeviceID,
                            resultCount: documents.count,
                            timestamp: timestamp
                        ),
                        database: database
                    )
                    return RuntimeDocumentApprovedCatalog(documents: documents, summary: summary)
                }
            }
        }
    }

    public func queryApprovedDocuments(
        _ query: String,
        limit: Int,
        maxSnippetCharacters: Int,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) throws -> [RuntimeDocumentSearchResult] {
        let terms = runtimeDocumentSearchTerms(query)
        let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexQueryLimitCeiling
        )
        let effectiveSnippetLimit = runtimeDocumentIndexEffectiveLimit(
            maxSnippetCharacters,
            ceiling: runtimeDocumentIndexSnippetCharacterLimitCeiling
        )
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    let results: [RuntimeDocumentSearchResult]
                    if !terms.isEmpty,
                       let effectiveLimit,
                       let effectiveSnippetLimit {
                        results = runtimeDocumentSearchResults(
                            from: try searchSnapshotUnlocked(database),
                            query: query,
                            limit: effectiveLimit,
                            maxSnippetCharacters: effectiveSnippetLimit
                        )
                    } else {
                        results = []
                    }
                    onBeforeApprovedReadAuditCommit?()
                    try insertSourceAuditUnlocked(
                        runtimeDocumentAuditEvent(
                            action: .queried,
                            actorDeviceID: actorDeviceID,
                            resultCount: results.count,
                            timestamp: timestamp
                        ),
                        database: database
                    )
                    return results
                }
            }
        }
    }

    func approvedSemanticSearchCandidates(
        limit: Int,
        maximumDocumentUTF8Bytes: Int
    ) throws -> [RuntimeDocumentSemanticCandidate] {
        try semanticEmbeddingCache.approvedCandidates(
            limit: limit,
            maximumDocumentUTF8Bytes: maximumDocumentUTF8Bytes
        )
    }

    func approvedSemanticSearchCandidates(
        limit: Int,
        maximumDocumentUTF8Bytes: Int,
        if shouldContinue: @escaping @Sendable () -> Bool
    ) throws -> [RuntimeDocumentSemanticCandidate] {
        try semanticEmbeddingCache.approvedCandidates(
            limit: limit,
            maximumDocumentUTF8Bytes: maximumDocumentUTF8Bytes,
            if: shouldContinue
        )
    }

    func cachedDocumentSemanticEmbeddings(
        for keys: [RuntimeDocumentSemanticEmbeddingKey]
    ) throws -> [RuntimeDocumentSemanticEmbeddingRecord] {
        try semanticEmbeddingCache.cachedEmbeddings(for: keys)
    }

    func upsertDocumentSemanticEmbeddings(
        _ records: [RuntimeDocumentSemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws {
        try semanticEmbeddingCache.upsertEmbeddings(records, if: shouldCommit)
    }

    func beginApprovedSemanticAccess(
        candidateIdentities: [RuntimeDocumentSemanticCandidateIdentity],
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> Set<RuntimeDocumentSemanticCandidateIdentity> {
        try revalidateSemanticCandidatesAndAudit(
            candidateIdentities: candidateIdentities,
            action: .semanticAccessed,
            resultCount: nil,
            actorDeviceID: actorDeviceID,
            timestamp: timestamp
        )
    }

    func commitApprovedSemanticQuery(
        candidateIdentities: [RuntimeDocumentSemanticCandidateIdentity],
        maximumResultCount: Int,
        actorDeviceID: String?,
        timestamp: Date,
        if shouldCommit: @Sendable () -> Bool
    ) throws -> Set<RuntimeDocumentSemanticCandidateIdentity> {
        try revalidateSemanticCandidatesAndAudit(
            candidateIdentities: candidateIdentities,
            action: .queried,
            resultCount: maximumResultCount,
            actorDeviceID: actorDeviceID,
            timestamp: timestamp,
            shouldCommit: shouldCommit
        )
    }

    private func revalidateSemanticCandidatesAndAudit(
        candidateIdentities: [RuntimeDocumentSemanticCandidateIdentity],
        action: RuntimeDocumentSourceAuditAction,
        resultCount: Int?,
        actorDeviceID: String?,
        timestamp: Date,
        shouldCommit: @Sendable () -> Bool = { true }
    ) throws -> Set<RuntimeDocumentSemanticCandidateIdentity> {
        guard shouldCommit() else { throw CancellationError() }
        let uniqueIdentities = Array(Set(candidateIdentities))
            .prefix(RuntimeSemanticDocumentSearch.maximumCandidateCount)
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard shouldCommit() else { throw CancellationError() }
                    var currentIdentities = Set<RuntimeDocumentSemanticCandidateIdentity>()
                    for identity in uniqueIdentities {
                        if try semanticCandidateIdentityIsCurrentUnlocked(identity, database: database) {
                            currentIdentities.insert(identity)
                        }
                    }
                    if action == .queried {
                        onBeforeApprovedSemanticQueryAuditCommit?()
                    }
                    onBeforeApprovedReadAuditCommit?()
                    guard shouldCommit() else { throw CancellationError() }
                    try insertSourceAuditUnlocked(
                        runtimeDocumentAuditEvent(
                            action: action,
                            actorDeviceID: actorDeviceID,
                            resultCount: resultCount.map {
                                min(max(0, $0), currentIdentities.count)
                            } ?? currentIdentities.count,
                            timestamp: timestamp
                        ),
                        database: database
                    )
                    guard shouldCommit() else { throw CancellationError() }
                    return currentIdentities
                }
            }
        }
    }

    public func resolveApprovedSourceAnchor(
        id sourceAnchorID: String,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) throws -> RuntimeDocumentSourceAnchor? {
        guard let sourceAnchorID = runtimeDocumentIndexCanonicalSourceAnchorID(sourceAnchorID) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard let anchor = try sourceAnchorUnlocked(id: sourceAnchorID, database: database) else {
                        return nil
                    }
                    guard let approval = try sourceApprovalUnlocked(
                        documentID: anchor.document.id,
                        database: database
                    ) else {
                        throw SQLiteRuntimeDocumentIndexStoreError(
                            "Runtime document source approval changed during anchor resolution."
                        )
                    }
                    onBeforeApprovedReadAuditCommit?()
                    try insertSourceAuditUnlocked(
                        runtimeDocumentAuditEvent(
                            action: .anchorResolved,
                            approval: approval,
                            actorDeviceID: actorDeviceID,
                            sourceAnchorID: sourceAnchorID,
                            resultCount: 1,
                            timestamp: timestamp
                        ),
                        database: database
                    )
                    return anchor
                }
            }
        }
    }

    public func prepareTrustedSourceReview(
        sourceAnchorID: String,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) throws -> RuntimeTrustedSourceReviewEnvelope {
        guard let sourceAnchorID = runtimeDocumentIndexCanonicalSourceAnchorID(sourceAnchorID),
              let actorDeviceID = runtimeDocumentCanonicalAuditActor(actorDeviceID) else {
            throw RuntimeTrustedSourceGovernanceError.citationNotFound
        }
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard let anchor = try sourceAnchorUnlocked(
                        id: sourceAnchorID,
                        database: database
                    ), let approval = try sourceApprovalUnlocked(
                        documentID: anchor.document.id,
                        database: database
                    ) else {
                        throw RuntimeTrustedSourceGovernanceError.citationNotFound
                    }
                    let citation = runtimeDocumentCitation(anchor: anchor, approval: approval)
                    try upsertCitationUnlocked(
                        citation,
                        sourceRevision: approval.sourceRevision,
                        timestamp: timestamp,
                        database: database
                    )
                    try deleteTrustedSourceReviewsUnlocked(
                        actorDeviceID: actorDeviceID,
                        database: database
                    )
                    let review = runtimeTrustedSourceReview(
                        citationID: citation.citationID,
                        actorDeviceID: actorDeviceID,
                        timestamp: timestamp
                    )
                    try insertTrustedSourceReviewUnlocked(
                        review,
                        citationID: citation.citationID,
                        actorDeviceID: actorDeviceID,
                        database: database
                    )
                    for action in [
                        RuntimeDocumentSourceAuditAction.citationResolved,
                        .trustedSourceReviewPrepared
                    ] {
                        try insertSourceAuditUnlocked(
                            runtimeDocumentAuditEvent(
                                action: action,
                                approval: approval,
                                actorDeviceID: actorDeviceID,
                                sourceAnchorID: sourceAnchorID,
                                resultCount: 1,
                                timestamp: timestamp
                            ),
                            database: database
                        )
                    }
                    return RuntimeTrustedSourceReviewEnvelope(
                        citation: citation,
                        review: review,
                        trustedSource: try trustedSourceGrantUnlocked(
                            actorDeviceID: actorDeviceID,
                            documentID: approval.documentID,
                            sourceRevision: approval.sourceRevision,
                            database: database
                        )
                    )
                }
            }
        }
    }

    public func prepareTrustedSourceReview(
        sourceAnchorID: String,
        documentID: String,
        sourceRevision: String,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) throws -> RuntimeTrustedSourceReviewEnvelope {
        guard runtimeDocumentIndexCanonicalSourceAnchorID(sourceAnchorID) == sourceAnchorID,
              runtimeDocumentIndexCanonicalDocumentID(documentID) == documentID,
              runtimeDocumentCanonicalSourceRevision(sourceRevision) == sourceRevision,
              let actorDeviceID = runtimeDocumentCanonicalAuditActor(actorDeviceID) else {
            throw RuntimeTrustedSourceGovernanceError.citationNotFound
        }
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard let approval = try sourceApprovalUnlocked(documentID: documentID, database: database),
                          approval.scope == .runtimeShared,
                          approval.sourceRevision == sourceRevision,
                          let anchor = try sourceAnchorUnlocked(id: sourceAnchorID, database: database),
                          anchor.document.id == documentID else {
                        throw RuntimeTrustedSourceGovernanceError.citationNotFound
                    }
                    let citation = runtimeDocumentCitation(anchor: anchor, approval: approval)
                    try upsertCitationUnlocked(
                        citation,
                        sourceRevision: sourceRevision,
                        timestamp: timestamp,
                        database: database
                    )
                    try deleteTrustedSourceReviewsUnlocked(actorDeviceID: actorDeviceID, database: database)
                    let review = runtimeTrustedSourceReview(
                        citationID: citation.citationID,
                        actorDeviceID: actorDeviceID,
                        timestamp: timestamp
                    )
                    try insertTrustedSourceReviewUnlocked(
                        review,
                        citationID: citation.citationID,
                        actorDeviceID: actorDeviceID,
                        database: database
                    )
                    for action in [RuntimeDocumentSourceAuditAction.citationResolved, .trustedSourceReviewPrepared] {
                        try insertSourceAuditUnlocked(
                            runtimeDocumentAuditEvent(
                                action: action,
                                approval: approval,
                                actorDeviceID: actorDeviceID,
                                sourceAnchorID: sourceAnchorID,
                                resultCount: 1,
                                timestamp: timestamp
                            ),
                            database: database
                        )
                    }
                    return RuntimeTrustedSourceReviewEnvelope(
                        citation: citation,
                        review: review,
                        trustedSource: try trustedSourceGrantUnlocked(
                            actorDeviceID: actorDeviceID,
                            documentID: documentID,
                            sourceRevision: sourceRevision,
                            database: database
                        )
                    )
                }
            }
        }
    }

    public func approveTrustedSourceReview(
        reviewID: String,
        confirmationToken: String,
        disclosureVersion: String,
        usageScope: RuntimeTrustedSourceUsageScope,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) throws -> RuntimeTrustedSourceGrant {
        guard let reviewID = runtimeDocumentCanonicalTrustedSourceReviewID(reviewID),
              let confirmationToken = runtimeDocumentCanonicalTrustedSourceConfirmationToken(confirmationToken),
              disclosureVersion == runtimeTrustedSourceDisclosureVersion,
              usageScope == .chatContext,
              let actorDeviceID = runtimeDocumentCanonicalAuditActor(actorDeviceID) else {
            throw RuntimeTrustedSourceGovernanceError.reviewNotFound
        }
        return try lock.withLock {
            try withDatabase { database in
                let outcome: Result<RuntimeTrustedSourceGrant, RuntimeTrustedSourceGovernanceError> =
                    try withImmediateTransaction(database) {
                    guard let storedReview = try trustedSourceReviewUnlocked(
                        reviewID: reviewID,
                        database: database
                    ), storedReview.actorDeviceID == actorDeviceID,
                       storedReview.review.confirmationToken == confirmationToken else {
                        throw RuntimeTrustedSourceGovernanceError.reviewNotFound
                    }
                    guard timestamp <= storedReview.review.expiresAt else {
                        try deleteTrustedSourceReviewUnlocked(
                            reviewID: reviewID,
                            database: database
                        )
                        return .failure(.reviewExpired)
                    }
                    guard let storedCitation = try storedCitationUnlocked(
                        citationID: storedReview.citationID,
                        database: database
                    ), storedCitation.staleAt == nil,
                       let approval = try sourceApprovalUnlocked(
                           documentID: storedCitation.documentID,
                           database: database
                       ), approval.sourceRevision == storedCitation.sourceRevision,
                       let anchor = try sourceAnchorUnlocked(
                           id: storedCitation.citation.sourceAnchorID,
                           database: database
                       ) else {
                        try deleteTrustedSourceReviewUnlocked(
                            reviewID: reviewID,
                            database: database
                        )
                        return .failure(.reviewStale)
                    }
                    let currentCitation = runtimeDocumentCitation(anchor: anchor, approval: approval)
                    guard currentCitation.citationID == storedCitation.citation.citationID else {
                        try deleteTrustedSourceReviewUnlocked(
                            reviewID: reviewID,
                            database: database
                        )
                        return .failure(.reviewStale)
                    }
                    let grant = runtimeTrustedSourceGrant(
                        citation: currentCitation,
                        approval: approval,
                        actorDeviceID: actorDeviceID,
                        timestamp: timestamp
                    )
                    onBeforeTrustedSourceApprovalCommit?()
                    try upsertTrustedSourceGrantUnlocked(
                        grant,
                        sourceRevision: approval.sourceRevision,
                        actorDeviceID: actorDeviceID,
                        database: database
                    )
                    try deleteTrustedSourceReviewUnlocked(
                        reviewID: reviewID,
                        database: database
                    )
                    try insertSourceAuditUnlocked(
                        runtimeDocumentAuditEvent(
                            action: .trustedSourceApproved,
                            approval: approval,
                            actorDeviceID: actorDeviceID,
                            sourceAnchorID: currentCitation.sourceAnchorID,
                            resultCount: 1,
                            timestamp: timestamp
                        ),
                        database: database
                    )
                    return .success(grant)
                }
                return try outcome.get()
            }
        }
    }

    public func dismissTrustedSourceReview(
        reviewID: String,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) throws {
        guard let reviewID = runtimeDocumentCanonicalTrustedSourceReviewID(reviewID),
              let actorDeviceID = runtimeDocumentCanonicalAuditActor(actorDeviceID) else {
            throw RuntimeTrustedSourceGovernanceError.reviewNotFound
        }
        try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard let storedReview = try trustedSourceReviewUnlocked(
                        reviewID: reviewID,
                        database: database
                    ), storedReview.actorDeviceID == actorDeviceID else {
                        throw RuntimeTrustedSourceGovernanceError.reviewNotFound
                    }
                    let citation = try storedCitationUnlocked(
                        citationID: storedReview.citationID,
                        database: database
                    )
                    try deleteTrustedSourceReviewUnlocked(reviewID: reviewID, database: database)
                    try insertSourceAuditUnlocked(
                        runtimeDocumentAuditEvent(
                            action: .trustedSourceReviewDismissed,
                            approval: try citation.flatMap {
                                try sourceApprovalUnlocked(documentID: $0.documentID, database: database)
                            },
                            actorDeviceID: actorDeviceID,
                            sourceAnchorID: citation?.citation.sourceAnchorID,
                            resultCount: 0,
                            timestamp: timestamp
                        ),
                        database: database
                    )
                }
            }
        }
    }

    public func trustedSources(
        actorDeviceID: String?,
        limit: Int,
        timestamp: Date = Date()
    ) throws -> [RuntimeTrustedSourceGrant] {
        guard let actorDeviceID = runtimeDocumentCanonicalAuditActor(actorDeviceID) else { return [] }
        let effectiveLimit = min(max(0, limit), runtimeTrustedSourceListLimitCeiling)
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    let grants = try trustedSourceGrantsUnlocked(
                        actorDeviceID: actorDeviceID,
                        limit: effectiveLimit,
                        database: database
                    )
                    try insertSourceAuditUnlocked(
                        runtimeDocumentAuditEvent(
                            action: .trustedSourcesListed,
                            actorDeviceID: actorDeviceID,
                            resultCount: grants.count,
                            timestamp: timestamp
                        ),
                        database: database
                    )
                    return grants
                }
            }
        }
    }

    public func revokeTrustedSource(
        grantID: String,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) throws {
        guard let grantID = runtimeDocumentCanonicalTrustedSourceGrantID(grantID),
              let actorDeviceID = runtimeDocumentCanonicalAuditActor(actorDeviceID) else {
            throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
        }
        try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard let storedGrant = try storedTrustedSourceGrantUnlocked(
                        grantID: grantID,
                        database: database
                    ), storedGrant.actorDeviceID == actorDeviceID,
                       storedGrant.revokedAt == nil else {
                        throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
                    }
                    try revokeTrustedSourceGrantUnlocked(
                        grantID: grantID,
                        timestamp: timestamp,
                        database: database
                    )
                    try insertSourceAuditUnlocked(
                        runtimeDocumentAuditEvent(
                            action: .trustedSourceRevoked,
                            approval: try sourceApprovalUnlocked(
                                documentID: storedGrant.documentID,
                                database: database
                            ),
                            actorDeviceID: actorDeviceID,
                            sourceAnchorID: storedGrant.grant.sourceAnchorID,
                            resultCount: 0,
                            timestamp: timestamp
                        ),
                        database: database
                    )
                }
            }
        }
    }

    public func consumeTrustedSourceChatContexts(
        grantIDs: [String],
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) throws -> [RuntimeTrustedSourceChatContext] {
        guard !grantIDs.isEmpty,
              grantIDs.count <= runtimeTrustedSourceChatContextGrantLimitCeiling,
              Set(grantIDs).count == grantIDs.count,
              grantIDs.allSatisfy({ runtimeDocumentCanonicalTrustedSourceGrantID($0) == $0 }),
              let actorDeviceID = runtimeDocumentCanonicalAuditActor(actorDeviceID) else {
            throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
        }
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    let contexts = try grantIDs.map {
                        try trustedSourceChatContextUnlocked(
                            grantID: $0,
                            actorDeviceID: actorDeviceID,
                            database: database
                        )
                    }
                    onBeforeTrustedSourceContextAuditCommit?()
                    for context in contexts {
                        try insertSourceAuditUnlocked(
                            runtimeDocumentAuditEvent(
                                action: .trustedSourceContextConsumed,
                                approval: try sourceApprovalUnlocked(
                                    documentID: context.document.id,
                                    database: database
                                ),
                                actorDeviceID: actorDeviceID,
                                sourceAnchorID: context.sourceAnchorID,
                                resultCount: 1,
                                timestamp: timestamp
                            ),
                            database: database
                        )
                    }
                    return contexts
                }
            }
        }
    }

    public func sourceApproval(documentID: String) throws -> RuntimeDocumentSourceApproval? {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                try sourceApprovalUnlocked(documentID: documentID, database: database)
            }
        }
    }

    public func recordSourceAudit(
        action: RuntimeDocumentSourceAuditAction,
        actorDeviceID: String?,
        documentID: String?,
        sourceAnchorID: String?,
        resultCount: Int?,
        timestamp: Date = Date()
    ) throws {
        try lock.withLock {
            try withDatabase { database in
                let approval: RuntimeDocumentSourceApproval?
                if let documentID,
                   let canonicalID = runtimeDocumentIndexCanonicalDocumentID(documentID) {
                    approval = try sourceApprovalUnlocked(documentID: canonicalID, database: database)
                } else {
                    approval = nil
                }
                try insertSourceAuditUnlocked(
                    runtimeDocumentAuditEvent(
                        action: action,
                        approval: approval,
                        actorDeviceID: actorDeviceID,
                        documentID: documentID,
                        sourceAnchorID: sourceAnchorID,
                        resultCount: resultCount,
                        timestamp: timestamp
                    ),
                    database: database
                )
            }
        }
    }

    public func sourceAuditEvents(limit: Int = 100) throws -> [RuntimeDocumentSourceAuditEvent] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentSourceAuditLimitCeiling
        ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try sourceAuditEventsUnlocked(limit: effectiveLimit, database: database)
            }
        }
    }

    private func insertDocumentUnlocked(
        _ document: RuntimeDocumentIndexDocument,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(document.id, to: statement, at: 1)
        try Self.bindText(document.displayName, to: statement, at: 2)
        try Self.bindText(document.mimeType, to: statement, at: 3)
        try Self.bindText(document.contentFingerprint, to: statement, at: 4)
        try Self.bindInt(document.extractedCharacterCount, to: statement, at: 5)
        try Self.bindInt(document.chunkCount, to: statement, at: 6)
        try Self.bindText(document.quality.rawValue, to: statement, at: 7)
        try Self.stepDone(statement, database: database)
    }

    private func insertChunkUnlocked(
        _ chunk: RuntimeDocumentIndexChunk,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_index_chunks(
                chunk_id,
                document_id,
                document_display_name,
                document_mime_type,
                chunk_index,
                start_character_offset,
                end_character_offset,
                text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(chunk.id, to: statement, at: 1)
        try Self.bindText(chunk.documentID, to: statement, at: 2)
        try Self.bindText(chunk.documentDisplayName, to: statement, at: 3)
        try Self.bindText(chunk.documentMimeType, to: statement, at: 4)
        try Self.bindInt(chunk.chunkIndex, to: statement, at: 5)
        try Self.bindInt(chunk.startCharacterOffset, to: statement, at: 6)
        try Self.bindInt(chunk.endCharacterOffset, to: statement, at: 7)
        try Self.bindText(chunk.text, to: statement, at: 8)
        try Self.stepDone(statement, database: database)
        try insertChunkSearchRowUnlocked(chunk, database: database)
    }

    private func insertChunkSearchRowUnlocked(
        _ chunk: RuntimeDocumentIndexChunk,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_index_chunk_fts(
                chunk_id,
                document_id,
                text
            ) VALUES (?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(chunk.id, to: statement, at: 1)
        try Self.bindText(chunk.documentID, to: statement, at: 2)
        try Self.bindText(chunk.text, to: statement, at: 3)
        try Self.stepDone(statement, database: database)
    }

    private func insertSourceApprovalUnlocked(
        _ approval: RuntimeDocumentSourceApproval,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_source_approvals(
                document_id, approval_id, source_revision, approval_scope, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(approval.documentID, to: statement, at: 1)
        try Self.bindText(approval.approvalID, to: statement, at: 2)
        try Self.bindText(approval.sourceRevision, to: statement, at: 3)
        try Self.bindText(approval.scope.rawValue, to: statement, at: 4)
        try Self.bindText(approval.approvedBy, to: statement, at: 5)
        try Self.bindDouble(approval.approvedAt.timeIntervalSince1970, to: statement, at: 6)
        try Self.stepDone(statement, database: database)
    }

    private func insertSourceAuditUnlocked(
        _ event: RuntimeDocumentSourceAuditEvent,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_source_audit_events(
                event_id, action, document_id, source_revision, actor_device_id,
                source_anchor_id, result_count, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(event.eventID, to: statement, at: 1)
        try Self.bindText(event.action.rawValue, to: statement, at: 2)
        try Self.bindOptionalText(event.documentID, to: statement, at: 3)
        try Self.bindOptionalText(event.sourceRevision, to: statement, at: 4)
        try Self.bindOptionalText(event.actorDeviceID, to: statement, at: 5)
        try Self.bindOptionalText(event.sourceAnchorID, to: statement, at: 6)
        try Self.bindOptionalInt(event.resultCount, to: statement, at: 7)
        try Self.bindDouble(event.occurredAt.timeIntervalSince1970, to: statement, at: 8)
        try Self.stepDone(statement, database: database)
        try trimSourceAuditUnlocked(database: database)
    }

    private func trimSourceAuditUnlocked(database: OpaquePointer) throws {
        let statement = try Self.prepare(
            database,
            """
            DELETE FROM runtime_document_source_audit_events
            WHERE rowid IN (
                SELECT rowid
                FROM runtime_document_source_audit_events
                ORDER BY rowid ASC
                LIMIT MAX(
                    (SELECT COUNT(*) FROM runtime_document_source_audit_events) - ?,
                    0
                )
            )
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindInt(sourceAuditEventLimit, to: statement, at: 1)
        try Self.stepDone(statement, database: database)
    }

    private func upsertCitationUnlocked(
        _ citation: RuntimeDocumentCitation,
        sourceRevision: String,
        timestamp: Date,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_citations(
                citation_id, source_anchor_id, document_id, document_display_name,
                document_mime_type, document_content_fingerprint,
                document_extracted_character_count, document_chunk_count, document_quality,
                source_revision, chunk_index, start_character_offset, end_character_offset,
                character_count, issued_at, stale_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(citation_id) DO UPDATE SET
                issued_at = excluded.issued_at,
                stale_at = NULL
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(citation.citationID, to: statement, at: 1)
        try Self.bindText(citation.sourceAnchorID, to: statement, at: 2)
        try Self.bindText(citation.document.id, to: statement, at: 3)
        try Self.bindText(citation.document.displayName, to: statement, at: 4)
        try Self.bindText(citation.document.mimeType, to: statement, at: 5)
        try Self.bindText(citation.document.contentFingerprint, to: statement, at: 6)
        try Self.bindInt(citation.document.extractedCharacterCount, to: statement, at: 7)
        try Self.bindInt(citation.document.chunkCount, to: statement, at: 8)
        try Self.bindText(citation.document.quality.rawValue, to: statement, at: 9)
        try Self.bindText(sourceRevision, to: statement, at: 10)
        try Self.bindInt(citation.chunkSummary.chunkIndex, to: statement, at: 11)
        try Self.bindInt(citation.chunkSummary.startCharacterOffset, to: statement, at: 12)
        try Self.bindInt(citation.chunkSummary.endCharacterOffset, to: statement, at: 13)
        try Self.bindInt(citation.chunkSummary.characterCount, to: statement, at: 14)
        try Self.bindDouble(timestamp.timeIntervalSince1970, to: statement, at: 15)
        try Self.stepDone(statement, database: database)
    }

    private func storedCitationUnlocked(
        citationID: String,
        database: OpaquePointer
    ) throws -> RuntimeStoredDocumentCitation? {
        let statement = try Self.prepare(
            database,
            """
            SELECT citation_id, source_anchor_id, document_id, document_display_name,
                   document_mime_type, document_content_fingerprint,
                   document_extracted_character_count, document_chunk_count, document_quality,
                   source_revision, chunk_index, start_character_offset, end_character_offset,
                   character_count, issued_at, stale_at
            FROM runtime_document_citations
            WHERE citation_id = ?
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(citationID, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW,
              let quality = DocumentIngestionQuality(rawValue: try Self.columnText(statement, 8)) else {
            throw Self.failure(database, "Could not read runtime document citation.")
        }
        let document = RuntimeDocumentIndexDocument(
            id: try Self.columnText(statement, 2),
            displayName: try Self.columnText(statement, 3),
            mimeType: try Self.columnText(statement, 4),
            contentFingerprint: try Self.columnText(statement, 5),
            extractedCharacterCount: Self.columnInt(statement, 6),
            chunkCount: Self.columnInt(statement, 7),
            quality: quality
        )
        let chunkSummary = RuntimeDocumentIndexChunkSummary(
            documentID: document.id,
            documentDisplayName: document.displayName,
            documentMimeType: document.mimeType,
            chunkIndex: Self.columnInt(statement, 10),
            startCharacterOffset: Self.columnInt(statement, 11),
            endCharacterOffset: Self.columnInt(statement, 12),
            characterCount: Self.columnInt(statement, 13)
        )
        return RuntimeStoredDocumentCitation(
            citation: RuntimeDocumentCitation(
                schemaVersion: runtimeDocumentCitationSchemaVersion,
                citationID: try Self.columnText(statement, 0),
                sourceAnchorID: try Self.columnText(statement, 1),
                document: document,
                chunkSummary: chunkSummary
            ),
            documentID: document.id,
            sourceRevision: try Self.columnText(statement, 9),
            issuedAt: Date(timeIntervalSince1970: Self.columnDouble(statement, 14)),
            staleAt: Self.columnOptionalDouble(statement, 15).map(Date.init(timeIntervalSince1970:))
        )
    }

    private func insertTrustedSourceReviewUnlocked(
        _ review: RuntimeTrustedSourceReview,
        citationID: String,
        actorDeviceID: String,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_trusted_source_reviews(
                review_id, confirmation_token, citation_id, actor_device_id,
                disclosure_version, usage_scope, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(review.reviewID, to: statement, at: 1)
        try Self.bindText(review.confirmationToken, to: statement, at: 2)
        try Self.bindText(citationID, to: statement, at: 3)
        try Self.bindText(actorDeviceID, to: statement, at: 4)
        try Self.bindText(review.disclosureVersion, to: statement, at: 5)
        try Self.bindText(review.usageScope.rawValue, to: statement, at: 6)
        try Self.bindDouble(review.expiresAt.timeIntervalSince1970, to: statement, at: 7)
        try Self.stepDone(statement, database: database)
    }

    private func trustedSourceReviewUnlocked(
        reviewID: String,
        database: OpaquePointer
    ) throws -> RuntimeStoredTrustedSourceReview? {
        let statement = try Self.prepare(
            database,
            """
            SELECT review_id, confirmation_token, citation_id, actor_device_id,
                   disclosure_version, usage_scope, expires_at
            FROM runtime_document_trusted_source_reviews
            WHERE review_id = ?
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(reviewID, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW,
              let usageScope = RuntimeTrustedSourceUsageScope(
                  rawValue: try Self.columnText(statement, 5)
              ) else {
            throw Self.failure(database, "Could not read runtime trusted-source review.")
        }
        return RuntimeStoredTrustedSourceReview(
            review: RuntimeTrustedSourceReview(
                reviewID: try Self.columnText(statement, 0),
                confirmationToken: try Self.columnText(statement, 1),
                disclosureVersion: try Self.columnText(statement, 4),
                usageScope: usageScope,
                expiresAt: Date(timeIntervalSince1970: Self.columnDouble(statement, 6))
            ),
            citationID: try Self.columnText(statement, 2),
            actorDeviceID: try Self.columnText(statement, 3)
        )
    }

    private func deleteTrustedSourceReviewsUnlocked(
        actorDeviceID: String,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            "DELETE FROM runtime_document_trusted_source_reviews WHERE actor_device_id = ?"
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(actorDeviceID, to: statement, at: 1)
        try Self.stepDone(statement, database: database)
    }

    private func deleteTrustedSourceReviewUnlocked(
        reviewID: String,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            "DELETE FROM runtime_document_trusted_source_reviews WHERE review_id = ?"
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(reviewID, to: statement, at: 1)
        try Self.stepDone(statement, database: database)
    }

    private func upsertTrustedSourceGrantUnlocked(
        _ grant: RuntimeTrustedSourceGrant,
        sourceRevision: String,
        actorDeviceID: String,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_trusted_source_grants(
                grant_id, citation_id, source_anchor_id, document_id, source_revision,
                actor_device_id, usage_scope, approved_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(grant_id) DO UPDATE SET
                citation_id = excluded.citation_id,
                source_anchor_id = excluded.source_anchor_id,
                approved_at = excluded.approved_at,
                revoked_at = NULL
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(grant.grantID, to: statement, at: 1)
        try Self.bindText(grant.citationID, to: statement, at: 2)
        try Self.bindText(grant.sourceAnchorID, to: statement, at: 3)
        try Self.bindText(grant.document.id, to: statement, at: 4)
        try Self.bindText(sourceRevision, to: statement, at: 5)
        try Self.bindText(actorDeviceID, to: statement, at: 6)
        try Self.bindText(grant.usageScope.rawValue, to: statement, at: 7)
        try Self.bindDouble(grant.approvedAt.timeIntervalSince1970, to: statement, at: 8)
        try Self.stepDone(statement, database: database)
    }

    private func storedTrustedSourceGrantUnlocked(
        grantID: String,
        database: OpaquePointer
    ) throws -> RuntimeStoredTrustedSourceGrant? {
        let statement = try Self.prepare(
            database,
            """
            SELECT grant_id, citation_id, source_anchor_id, document_id, source_revision,
                   actor_device_id, usage_scope, approved_at, revoked_at
            FROM runtime_document_trusted_source_grants
            WHERE grant_id = ?
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(grantID, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW,
              let usageScope = RuntimeTrustedSourceUsageScope(
                  rawValue: try Self.columnText(statement, 6)
              ), let citation = try storedCitationUnlocked(
                  citationID: try Self.columnText(statement, 1),
                  database: database
              ) else {
            throw Self.failure(database, "Could not read runtime trusted-source grant.")
        }
        let approvedAt = Date(timeIntervalSince1970: Self.columnDouble(statement, 7))
        return RuntimeStoredTrustedSourceGrant(
            grant: RuntimeTrustedSourceGrant(
                grantID: try Self.columnText(statement, 0),
                citationID: citation.citation.citationID,
                sourceAnchorID: try Self.columnText(statement, 2),
                document: citation.citation.document,
                usageScope: usageScope,
                approvedAt: approvedAt
            ),
            documentID: try Self.columnText(statement, 3),
            sourceRevision: try Self.columnText(statement, 4),
            actorDeviceID: try Self.columnText(statement, 5),
            revokedAt: Self.columnOptionalDouble(statement, 8).map(Date.init(timeIntervalSince1970:))
        )
    }

    private func trustedSourceGrantUnlocked(
        actorDeviceID: String,
        documentID: String,
        sourceRevision: String,
        database: OpaquePointer
    ) throws -> RuntimeTrustedSourceGrant? {
        let statement = try Self.prepare(
            database,
            """
            SELECT grant_id
            FROM runtime_document_trusted_source_grants
            WHERE actor_device_id = ? AND document_id = ? AND source_revision = ?
              AND usage_scope = 'chat_context' AND revoked_at IS NULL
            ORDER BY approved_at DESC, grant_id ASC
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(actorDeviceID, to: statement, at: 1)
        try Self.bindText(documentID, to: statement, at: 2)
        try Self.bindText(sourceRevision, to: statement, at: 3)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW else {
            throw Self.failure(database, "Could not read runtime trusted-source grant.")
        }
        return try storedTrustedSourceGrantUnlocked(
            grantID: Self.columnText(statement, 0),
            database: database
        )?.grant
    }

    private func trustedSourceChatContextUnlocked(
        grantID: String,
        actorDeviceID: String,
        database: OpaquePointer
    ) throws -> RuntimeTrustedSourceChatContext {
        guard let storedGrant = try storedTrustedSourceGrantUnlocked(
            grantID: grantID,
            database: database
        ), storedGrant.actorDeviceID == actorDeviceID,
           storedGrant.revokedAt == nil,
           storedGrant.grant.usageScope == .chatContext,
           let storedCitation = try storedCitationUnlocked(
               citationID: storedGrant.grant.citationID,
               database: database
           ), storedCitation.staleAt == nil,
           storedCitation.documentID == storedGrant.documentID,
           storedCitation.sourceRevision == storedGrant.sourceRevision,
           storedCitation.citation.sourceAnchorID == storedGrant.grant.sourceAnchorID,
           let approval = try sourceApprovalUnlocked(
               documentID: storedGrant.documentID,
               database: database
           ), approval.scope == .runtimeShared,
           approval.sourceRevision == storedGrant.sourceRevision,
           let document = try documentUnlocked(id: storedGrant.documentID, database: database),
           document == storedCitation.citation.document,
           let chunk = try trustedSourceChunkUnlocked(
               citation: storedCitation.citation,
               database: database
           ), RuntimeDocumentIndexStore.stableChunkID(
               documentID: chunk.documentID,
               chunkIndex: chunk.chunkIndex,
               startCharacterOffset: chunk.startCharacterOffset,
               endCharacterOffset: chunk.endCharacterOffset,
               text: chunk.text
           ) == chunk.id,
           let text = runtimeTrustedSourceChatContextText(chunk.text) else {
            throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
        }
        let summary = runtimeDocumentIndexChunkSummary(chunk)
        let anchor = RuntimeDocumentSourceAnchor(
            sourceAnchorID: runtimeDocumentSourceAnchorID(
                document: document,
                chunkSummary: summary
            ),
            document: document,
            chunkSummary: summary
        )
        guard anchor.sourceAnchorID == storedGrant.grant.sourceAnchorID,
              summary == storedCitation.citation.chunkSummary,
              runtimeDocumentCitation(anchor: anchor, approval: approval).citationID
                == storedGrant.grant.citationID else {
            throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
        }
        return RuntimeTrustedSourceChatContext(
            grantID: grantID,
            citationID: storedGrant.grant.citationID,
            sourceAnchorID: storedGrant.grant.sourceAnchorID,
            sourceRevision: approval.sourceRevision,
            document: document,
            chunkSummary: summary,
            text: text
        )
    }

    private func trustedSourceChunkUnlocked(
        citation: RuntimeDocumentCitation,
        database: OpaquePointer
    ) throws -> RuntimeDocumentIndexChunk? {
        let statement = try Self.prepare(
            database,
            """
            SELECT chunk_id, document_id, document_display_name, document_mime_type,
                   chunk_index, start_character_offset, end_character_offset, text
            FROM runtime_document_index_chunks
            WHERE document_id = ? AND chunk_index = ?
              AND start_character_offset = ? AND end_character_offset = ?
            LIMIT 2
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(citation.document.id, to: statement, at: 1)
        try Self.bindInt(citation.chunkSummary.chunkIndex, to: statement, at: 2)
        try Self.bindInt(citation.chunkSummary.startCharacterOffset, to: statement, at: 3)
        try Self.bindInt(citation.chunkSummary.endCharacterOffset, to: statement, at: 4)
        guard sqlite3_step(statement) == SQLITE_ROW else { return nil }
        let chunk = try Self.chunk(from: statement)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw Self.failure(database, "Runtime trusted-source citation matched duplicate chunks.")
        }
        return chunk
    }

    private func trustedSourceGrantsUnlocked(
        actorDeviceID: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeTrustedSourceGrant] {
        guard limit > 0 else { return [] }
        let statement = try Self.prepare(
            database,
            """
            SELECT g.grant_id
            FROM runtime_document_trusted_source_grants g
            JOIN runtime_document_source_approvals a
              ON a.document_id = g.document_id AND a.source_revision = g.source_revision
            JOIN runtime_document_citations c
              ON c.citation_id = g.citation_id AND c.stale_at IS NULL
            WHERE g.actor_device_id = ? AND g.usage_scope = 'chat_context'
              AND g.revoked_at IS NULL AND a.approval_scope = 'runtime_shared'
            ORDER BY g.approved_at DESC, g.grant_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(actorDeviceID, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)
        var grants: [RuntimeTrustedSourceGrant] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return grants }
            guard result == SQLITE_ROW,
                  let grant = try storedTrustedSourceGrantUnlocked(
                      grantID: Self.columnText(statement, 0),
                      database: database
                  )?.grant else {
                throw Self.failure(database, "Could not list runtime trusted-source grants.")
            }
            grants.append(grant)
        }
    }

    private func revokeTrustedSourceGrantUnlocked(
        grantID: String,
        timestamp: Date,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            UPDATE runtime_document_trusted_source_grants
            SET revoked_at = ?
            WHERE grant_id = ? AND revoked_at IS NULL
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindDouble(timestamp.timeIntervalSince1970, to: statement, at: 1)
        try Self.bindText(grantID, to: statement, at: 2)
        try Self.stepDone(statement, database: database)
    }

    private func semanticCandidateIdentityIsCurrentUnlocked(
        _ identity: RuntimeDocumentSemanticCandidateIdentity,
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
        try Self.bindText(identity.documentID, to: statement, at: 1)
        try Self.bindText(identity.chunkID, to: statement, at: 2)
        try Self.bindText(identity.sourceRevision, to: statement, at: 3)
        guard sqlite3_step(statement) == SQLITE_ROW else { return false }
        let document = try Self.document(from: statement)
        let chunk = try Self.chunk(from: statement, offset: 7)
        guard let candidate = RuntimeSemanticDocumentSearch.candidate(
            document: document,
            chunk: chunk,
            sourceRevision: try Self.columnText(statement, 15),
            maximumDocumentUTF8Bytes: identity.documentByteLimit
        ) else { return false }
        return candidate.identity == identity
    }

    private func sourceApprovalUnlocked(
        documentID: String,
        database: OpaquePointer
    ) throws -> RuntimeDocumentSourceApproval? {
        let statement = try Self.prepare(
            database,
            """
            SELECT approval_id, document_id, source_revision, approval_scope, approved_by, approved_at
            FROM runtime_document_source_approvals
            WHERE document_id = ? AND approval_scope = 'runtime_shared'
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(documentID, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW,
              let scope = RuntimeDocumentSourceApprovalScope(rawValue: try Self.columnText(statement, 3)) else {
            throw Self.failure(database, "Could not read runtime document source approval.")
        }
        return RuntimeDocumentSourceApproval(
            approvalID: try Self.columnText(statement, 0),
            documentID: try Self.columnText(statement, 1),
            sourceRevision: try Self.columnText(statement, 2),
            scope: scope,
            approvedBy: try Self.columnText(statement, 4),
            approvedAt: Date(timeIntervalSince1970: Self.columnDouble(statement, 5))
        )
    }

    private func approvedSourceCountUnlocked(_ database: OpaquePointer) throws -> Int {
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
        try Self.bindInt(runtimeDocumentApprovedSourceLimitCeiling, to: statement, at: 1)
        var count = 0
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not enforce the approved document source limit.")
            }
            count += 1
        }
        return count
    }

    private func sourceApprovalsUnlocked(
        database: OpaquePointer
    ) throws -> [RuntimeDocumentSourceApproval] {
        let statement = try Self.prepare(
            database,
            """
            SELECT approval_id, document_id, source_revision, approval_scope, approved_by, approved_at
            FROM runtime_document_source_approvals
            WHERE approval_scope = 'runtime_shared'
            ORDER BY document_id ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        var approvals: [RuntimeDocumentSourceApproval] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return approvals }
            guard result == SQLITE_ROW,
                  let scope = RuntimeDocumentSourceApprovalScope(rawValue: try Self.columnText(statement, 3)) else {
                throw Self.failure(database, "Could not read runtime document source approvals.")
            }
            approvals.append(RuntimeDocumentSourceApproval(
                approvalID: try Self.columnText(statement, 0),
                documentID: try Self.columnText(statement, 1),
                sourceRevision: try Self.columnText(statement, 2),
                scope: scope,
                approvedBy: try Self.columnText(statement, 4),
                approvedAt: Date(timeIntervalSince1970: Self.columnDouble(statement, 5))
            ))
        }
    }

    private func sourceAuditEventsUnlocked(
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentSourceAuditEvent] {
        let statement = try Self.prepare(
            database,
            """
            SELECT event_id, action, document_id, source_revision, actor_device_id,
                   source_anchor_id, result_count, occurred_at
            FROM runtime_document_source_audit_events
            ORDER BY rowid DESC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindInt(limit, to: statement, at: 1)
        var events: [RuntimeDocumentSourceAuditEvent] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return events }
            guard result == SQLITE_ROW,
                  let action = RuntimeDocumentSourceAuditAction(rawValue: try Self.columnText(statement, 1)) else {
                throw Self.failure(database, "Could not read runtime document source audit events.")
            }
            events.append(RuntimeDocumentSourceAuditEvent(
                eventID: try Self.columnText(statement, 0),
                action: action,
                documentID: Self.columnOptionalText(statement, 2),
                sourceRevision: Self.columnOptionalText(statement, 3),
                actorDeviceID: Self.columnOptionalText(statement, 4),
                sourceAnchorID: Self.columnOptionalText(statement, 5),
                resultCount: Self.columnOptionalInt(statement, 6),
                occurredAt: Date(timeIntervalSince1970: Self.columnDouble(statement, 7))
            ))
        }
    }

    private func insertRevocationAuditUnlocked(
        approval: RuntimeDocumentSourceApproval,
        timestamp: Date,
        database: OpaquePointer
    ) throws {
        for action in [RuntimeDocumentSourceAuditAction.revoked, .deleted] {
            try insertSourceAuditUnlocked(
                runtimeDocumentAuditEvent(
                    action: action,
                    approval: approval,
                    actorDeviceID: approval.approvedBy,
                    timestamp: timestamp
                ),
                database: database
            )
        }
    }

    private func revokeAndDeleteDocumentUnlocked(
        id documentID: String,
        timestamp: Date,
        database: OpaquePointer
    ) throws {
        if let approval = try sourceApprovalUnlocked(documentID: documentID, database: database) {
            try insertRevocationAuditUnlocked(
                approval: approval,
                timestamp: timestamp,
                database: database
            )
        }
        try deleteDocumentUnlocked(id: documentID, database: database)
    }

    private func deleteDocumentUnlocked(
        id documentID: String,
        invalidateCitationState: Bool = true,
        database: OpaquePointer
    ) throws {
        if invalidateCitationState {
            try markCitationStateStaleUnlocked(
                documentID: documentID,
                timestamp: Date(),
                database: database
            )
        }
        let deleteSemanticEmbeddings = try Self.prepare(
            database,
            "DELETE FROM runtime_document_semantic_embeddings WHERE document_id = ?"
        )
        defer { sqlite3_finalize(deleteSemanticEmbeddings) }
        try Self.bindText(documentID, to: deleteSemanticEmbeddings, at: 1)
        try Self.stepDone(deleteSemanticEmbeddings, database: database)

        let deleteSearchRows = try Self.prepare(
            database,
            "DELETE FROM runtime_document_index_chunk_fts WHERE document_id = ?"
        )
        defer { sqlite3_finalize(deleteSearchRows) }
        try Self.bindText(documentID, to: deleteSearchRows, at: 1)
        try Self.stepDone(deleteSearchRows, database: database)

        let deleteChunks = try Self.prepare(
            database,
            "DELETE FROM runtime_document_index_chunks WHERE document_id = ?"
        )
        defer { sqlite3_finalize(deleteChunks) }
        try Self.bindText(documentID, to: deleteChunks, at: 1)
        try Self.stepDone(deleteChunks, database: database)

        let deleteDocument = try Self.prepare(
            database,
            "DELETE FROM runtime_document_index_documents WHERE document_id = ?"
        )
        defer { sqlite3_finalize(deleteDocument) }
        try Self.bindText(documentID, to: deleteDocument, at: 1)
        try Self.stepDone(deleteDocument, database: database)
    }

    private func deleteAllDocumentsUnlocked(database: OpaquePointer) throws {
        try markAllCitationStateStaleUnlocked(timestamp: Date(), database: database)
        try Self.execute(database, "DELETE FROM runtime_document_semantic_embeddings")
        try Self.execute(database, "DELETE FROM runtime_document_index_chunk_fts")
        try Self.execute(database, "DELETE FROM runtime_document_index_chunks")
        try Self.execute(database, "DELETE FROM runtime_document_index_documents")
    }

    private func markCitationStateStaleUnlocked(
        documentID: String,
        timestamp: Date,
        database: OpaquePointer
    ) throws {
        let staleCitations = try Self.prepare(
            database,
            "UPDATE runtime_document_citations SET stale_at = COALESCE(stale_at, ?) WHERE document_id = ?"
        )
        defer { sqlite3_finalize(staleCitations) }
        try Self.bindDouble(timestamp.timeIntervalSince1970, to: staleCitations, at: 1)
        try Self.bindText(documentID, to: staleCitations, at: 2)
        try Self.stepDone(staleCitations, database: database)

        let revokeGrants = try Self.prepare(
            database,
            """
            UPDATE runtime_document_trusted_source_grants
            SET revoked_at = COALESCE(revoked_at, ?)
            WHERE document_id = ?
            """
        )
        defer { sqlite3_finalize(revokeGrants) }
        try Self.bindDouble(timestamp.timeIntervalSince1970, to: revokeGrants, at: 1)
        try Self.bindText(documentID, to: revokeGrants, at: 2)
        try Self.stepDone(revokeGrants, database: database)
    }

    private func markAllCitationStateStaleUnlocked(
        timestamp: Date,
        database: OpaquePointer
    ) throws {
        let staleCitations = try Self.prepare(
            database,
            "UPDATE runtime_document_citations SET stale_at = COALESCE(stale_at, ?)"
        )
        defer { sqlite3_finalize(staleCitations) }
        try Self.bindDouble(timestamp.timeIntervalSince1970, to: staleCitations, at: 1)
        try Self.stepDone(staleCitations, database: database)
        let revokeGrants = try Self.prepare(
            database,
            "UPDATE runtime_document_trusted_source_grants SET revoked_at = COALESCE(revoked_at, ?)"
        )
        defer { sqlite3_finalize(revokeGrants) }
        try Self.bindDouble(timestamp.timeIntervalSince1970, to: revokeGrants, at: 1)
        try Self.stepDone(revokeGrants, database: database)
    }

    private func documentIDsUnlocked(
        matchingQuality quality: DocumentIngestionQuality,
        database: OpaquePointer
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id
            FROM runtime_document_index_documents
            WHERE quality = ?
            ORDER BY document_id ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(quality.rawValue, to: statement, at: 1)

        var documentIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index quality deletion rows.")
            }
            documentIDs.append(try Self.columnText(statement, 0))
        }
        return documentIDs
    }

    private func documentIDsUnlocked(
        matchingContentFingerprint contentFingerprint: String,
        database: OpaquePointer
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id
            FROM runtime_document_index_documents
            WHERE content_fingerprint = ?
            ORDER BY document_id ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(contentFingerprint, to: statement, at: 1)

        var documentIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index fingerprint deletion rows.")
            }
            documentIDs.append(try Self.columnText(statement, 0))
        }
        return documentIDs
    }

    private func documentIDsUnlocked(
        matchingDisplayName displayName: String,
        database: OpaquePointer
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id
            FROM runtime_document_index_documents
            WHERE display_name = ?
            ORDER BY document_id ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(displayName, to: statement, at: 1)

        var documentIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index display-name deletion rows.")
            }
            documentIDs.append(try Self.columnText(statement, 0))
        }
        return documentIDs
    }

    private func documentIDsUnlocked(
        matchingMimeType mimeType: String,
        database: OpaquePointer
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id
            FROM runtime_document_index_documents
            WHERE mime_type = ?
            ORDER BY document_id ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(mimeType, to: statement, at: 1)

        var documentIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index MIME-type deletion rows.")
            }
            documentIDs.append(try Self.columnText(statement, 0))
        }
        return documentIDs
    }

    private func documentUnlocked(
        id documentID: String,
        database: OpaquePointer
    ) throws -> RuntimeDocumentIndexDocument? {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality
            FROM runtime_document_index_documents d
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE d.document_id = ? AND a.approval_scope = 'runtime_shared'
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(documentID, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW else {
            throw Self.failure(database, "Could not read runtime document index document.")
        }
        return try Self.document(from: statement)
    }

    private func chunksUnlocked(
        for documentID: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexChunk] {
        try readChunksUnlocked(
            database,
            sql: """
            SELECT c.chunk_id, c.document_id, c.document_display_name, c.document_mime_type,
                   c.chunk_index, c.start_character_offset, c.end_character_offset, c.text
            FROM runtime_document_index_chunks c
            JOIN runtime_document_source_approvals a ON a.document_id = c.document_id
            WHERE c.document_id = ? AND a.approval_scope = 'runtime_shared'
            ORDER BY c.chunk_index ASC
            LIMIT ?
            """,
            bind: { statement in
                try Self.bindText(documentID, to: statement, at: 1)
                try Self.bindInt(limit, to: statement, at: 2)
            }
        )
    }

    private func chunkSummariesUnlocked(
        for documentID: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexChunkSummary] {
        let statement = try Self.prepare(
            database,
            """
            SELECT c.document_id, c.document_display_name, c.document_mime_type,
                   c.chunk_index, c.start_character_offset, c.end_character_offset, length(c.text)
            FROM runtime_document_index_chunks c
            JOIN runtime_document_source_approvals a ON a.document_id = c.document_id
            WHERE c.document_id = ? AND a.approval_scope = 'runtime_shared'
            ORDER BY c.chunk_index ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(documentID, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var chunks: [RuntimeDocumentIndexChunkSummary] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index chunk summaries.")
            }
            chunks.append(try Self.chunkSummary(from: statement))
        }
        return chunks
    }

    private func sourceAnchorUnlocked(
        id sourceAnchorID: String,
        database: OpaquePointer
    ) throws -> RuntimeDocumentSourceAnchor? {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality,
                   c.document_id, c.document_display_name, c.document_mime_type,
                   c.chunk_index, c.start_character_offset, c.end_character_offset, length(c.text)
            FROM runtime_document_index_chunks c
            JOIN runtime_document_index_documents d ON d.document_id = c.document_id
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE a.approval_scope = 'runtime_shared'
            ORDER BY d.display_name ASC, c.chunk_index ASC
            """
        )
        defer { sqlite3_finalize(statement) }

        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return nil }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not resolve runtime document source anchor.")
            }
            let document = try Self.document(from: statement, offset: 0)
            let chunkSummary = try Self.chunkSummary(from: statement, offset: 7)
            let anchor = RuntimeDocumentSourceAnchor(
                sourceAnchorID: runtimeDocumentSourceAnchorID(document: document, chunkSummary: chunkSummary),
                document: document,
                chunkSummary: chunkSummary
            )
            if anchor.sourceAnchorID == sourceAnchorID {
                return anchor
            }
        }
    }

    private func documentsUnlocked(
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality
            FROM runtime_document_index_documents d
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE a.approval_scope = 'runtime_shared'
            ORDER BY d.display_name ASC, d.document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindInt(limit, to: statement, at: 1)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index catalog rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func documentsUnlocked(
        matchingMimeType mimeType: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality
            FROM runtime_document_index_documents d
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE d.mime_type = ? AND a.approval_scope = 'runtime_shared'
            ORDER BY d.display_name ASC, d.document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(mimeType, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index MIME-type rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func documentsUnlocked(
        matchingDisplayName displayName: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality
            FROM runtime_document_index_documents d
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE d.display_name = ? AND a.approval_scope = 'runtime_shared'
            ORDER BY d.display_name ASC, d.document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(displayName, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index display-name rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func documentsUnlocked(
        matchingQuality quality: DocumentIngestionQuality,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality
            FROM runtime_document_index_documents d
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE d.quality = ? AND a.approval_scope = 'runtime_shared'
            ORDER BY d.display_name ASC, d.document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(quality.rawValue, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index quality-filtered rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func documentsUnlocked(
        matchingContentFingerprint contentFingerprint: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality
            FROM runtime_document_index_documents d
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE d.content_fingerprint = ? AND a.approval_scope = 'runtime_shared'
            ORDER BY d.display_name ASC, d.document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(contentFingerprint, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index fingerprint rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func summaryUnlocked(
        database: OpaquePointer
    ) throws -> RuntimeDocumentIndexSummary {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality
            FROM runtime_document_index_documents d
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE a.approval_scope = 'runtime_shared'
            """
        )
        defer { sqlite3_finalize(statement) }

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not summarize runtime document index rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return runtimeDocumentIndexSummary(documents)
    }

    private func searchSnapshotUnlocked(
        _ database: OpaquePointer,
        candidateChunkIDs: [String]? = nil
    ) throws -> [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)] {
        let chunkFilter: String
        if let candidateChunkIDs {
            chunkFilter = "AND c.chunk_id IN (\(Array(repeating: "?", count: candidateChunkIDs.count).joined(separator: ", ")))"
        } else {
            chunkFilter = ""
        }
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality,
                   c.chunk_id, c.document_id, c.document_display_name, c.document_mime_type,
                   c.chunk_index, c.start_character_offset, c.end_character_offset, c.text
            FROM runtime_document_index_chunks c
            JOIN runtime_document_index_documents d ON d.document_id = c.document_id
            JOIN runtime_document_source_approvals a ON a.document_id = d.document_id
            WHERE a.approval_scope = 'runtime_shared'
            \(chunkFilter)
            ORDER BY d.display_name ASC, c.chunk_index ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        if let candidateChunkIDs {
            for (index, chunkID) in candidateChunkIDs.enumerated() {
                try Self.bindText(chunkID, to: statement, at: Int32(index + 1))
            }
        }

        var snapshot: [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index search rows.")
            }
            snapshot.append((
                try Self.document(from: statement, offset: 0),
                try Self.chunk(from: statement, offset: 7)
            ))
        }
        return snapshot
    }

    private func ftsCandidateChunkIDsUnlocked(
        _ database: OpaquePointer,
        terms: [String]
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT chunk_id
            FROM runtime_document_index_chunk_fts
            WHERE runtime_document_index_chunk_fts MATCH ?
            ORDER BY rowid ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ftsMatchQuery(for: terms), to: statement, at: 1)

        var chunkIDs: [String] = []
        var seen = Set<String>()
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index FTS candidates.")
            }
            let chunkID = try Self.columnText(statement, 0)
            if seen.insert(chunkID).inserted {
                chunkIDs.append(chunkID)
            }
        }
        return chunkIDs
    }

    private func readChunksUnlocked(
        _ database: OpaquePointer,
        sql: String,
        bind: (OpaquePointer) throws -> Void
    ) throws -> [RuntimeDocumentIndexChunk] {
        let statement = try Self.prepare(database, sql)
        defer { sqlite3_finalize(statement) }
        try bind(statement)

        var chunks: [RuntimeDocumentIndexChunk] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index chunks.")
            }
            chunks.append(try Self.chunk(from: statement))
        }
        return chunks
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
            defer {
                if let database {
                    sqlite3_close(database)
                }
            }
            throw SQLiteRuntimeDocumentIndexStoreError("Could not open runtime document index SQLite store.")
        }
        defer {
            sqlite3_close(openedDatabase)
            try? RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        guard sqlite3_busy_timeout(openedDatabase, 5_000) == SQLITE_OK else {
            throw Self.failure(openedDatabase, "Could not configure runtime document index concurrency.")
        }
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        try Self.ensureSchema(openedDatabase)
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        return try body(openedDatabase)
    }

    private func withImmediateTransaction<T>(
        _ database: OpaquePointer,
        body: () throws -> T
    ) throws -> T {
        try Self.execute(database, "BEGIN IMMEDIATE")
        do {
            let result = try body()
            try Self.execute(database, "COMMIT")
            return result
        } catch {
            try? Self.execute(database, "ROLLBACK")
            throw error
        }
    }

    private static func ensureSchema(_ database: OpaquePointer) throws {
        try execute(database, "PRAGMA foreign_keys = ON")
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_index_documents(
                document_id TEXT PRIMARY KEY NOT NULL,
                display_name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                content_fingerprint TEXT NOT NULL,
                extracted_character_count INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL,
                quality TEXT NOT NULL
            )
            """
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_source_approvals(
                document_id TEXT PRIMARY KEY NOT NULL,
                approval_id TEXT NOT NULL,
                source_revision TEXT NOT NULL,
                approval_scope TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                approved_at REAL NOT NULL,
                FOREIGN KEY(document_id) REFERENCES runtime_document_index_documents(document_id) ON DELETE CASCADE
            )
            """
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_source_audit_events(
                event_id TEXT PRIMARY KEY NOT NULL,
                action TEXT NOT NULL,
                document_id TEXT,
                source_revision TEXT,
                actor_device_id TEXT,
                source_anchor_id TEXT,
                result_count INTEGER,
                occurred_at REAL NOT NULL
            )
            """
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_document_source_audit_time ON runtime_document_source_audit_events(occurred_at DESC)"
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_citations(
                citation_id TEXT PRIMARY KEY NOT NULL,
                source_anchor_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                document_display_name TEXT NOT NULL,
                document_mime_type TEXT NOT NULL,
                document_content_fingerprint TEXT NOT NULL,
                document_extracted_character_count INTEGER NOT NULL,
                document_chunk_count INTEGER NOT NULL,
                document_quality TEXT NOT NULL,
                source_revision TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_character_offset INTEGER NOT NULL,
                end_character_offset INTEGER NOT NULL,
                character_count INTEGER NOT NULL,
                issued_at REAL NOT NULL,
                stale_at REAL
            )
            """
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_document_citations_document ON runtime_document_citations(document_id, source_revision)"
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_trusted_source_reviews(
                review_id TEXT PRIMARY KEY NOT NULL,
                confirmation_token TEXT NOT NULL,
                citation_id TEXT NOT NULL,
                actor_device_id TEXT NOT NULL,
                disclosure_version TEXT NOT NULL,
                usage_scope TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_document_trusted_source_reviews_actor ON runtime_document_trusted_source_reviews(actor_device_id)"
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_trusted_source_grants(
                grant_id TEXT PRIMARY KEY NOT NULL,
                citation_id TEXT NOT NULL,
                source_anchor_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                source_revision TEXT NOT NULL,
                actor_device_id TEXT NOT NULL,
                usage_scope TEXT NOT NULL,
                approved_at REAL NOT NULL,
                revoked_at REAL
            )
            """
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_document_trusted_source_grants_actor ON runtime_document_trusted_source_grants(actor_device_id, approved_at DESC)"
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_index_chunks(
                chunk_id TEXT PRIMARY KEY NOT NULL,
                document_id TEXT NOT NULL,
                document_display_name TEXT NOT NULL,
                document_mime_type TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_character_offset INTEGER NOT NULL,
                end_character_offset INTEGER NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES runtime_document_index_documents(document_id) ON DELETE CASCADE
            )
            """
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_document_index_chunks_document ON runtime_document_index_chunks(document_id, chunk_index)"
        )
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
                    document_id,
                    chunk_id,
                    source_revision,
                    embedding_model_id,
                    model_fingerprint,
                    document_encoding_version,
                    document_fingerprint
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
        try execute(
            database,
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS runtime_document_index_chunk_fts USING fts5(
                chunk_id UNINDEXED,
                document_id UNINDEXED,
                text,
                tokenize = 'unicode61 remove_diacritics 2'
            )
            """
        )
    }

    private static func document(
        from statement: OpaquePointer,
        offset: Int32 = 0
    ) throws -> RuntimeDocumentIndexDocument {
        let qualityRawValue = try columnText(statement, offset + 6)
        guard let quality = DocumentIngestionQuality(rawValue: qualityRawValue) else {
            throw SQLiteRuntimeDocumentIndexStoreError("Runtime document index SQLite quality is invalid.")
        }
        return RuntimeDocumentIndexDocument(
            id: try columnText(statement, offset),
            displayName: try columnText(statement, offset + 1),
            mimeType: try columnText(statement, offset + 2),
            contentFingerprint: try columnText(statement, offset + 3),
            extractedCharacterCount: columnInt(statement, offset + 4),
            chunkCount: columnInt(statement, offset + 5),
            quality: quality
        )
    }

    private static func chunk(
        from statement: OpaquePointer,
        offset: Int32 = 0
    ) throws -> RuntimeDocumentIndexChunk {
        RuntimeDocumentIndexChunk(
            id: try columnText(statement, offset),
            documentID: try columnText(statement, offset + 1),
            documentDisplayName: try columnText(statement, offset + 2),
            documentMimeType: try columnText(statement, offset + 3),
            chunkIndex: columnInt(statement, offset + 4),
            startCharacterOffset: columnInt(statement, offset + 5),
            endCharacterOffset: columnInt(statement, offset + 6),
            text: try columnText(statement, offset + 7)
        )
    }

    private static func chunkSummary(
        from statement: OpaquePointer,
        offset: Int32 = 0
    ) throws -> RuntimeDocumentIndexChunkSummary {
        RuntimeDocumentIndexChunkSummary(
            documentID: try columnText(statement, offset),
            documentDisplayName: try columnText(statement, offset + 1),
            documentMimeType: try columnText(statement, offset + 2),
            chunkIndex: columnInt(statement, offset + 3),
            startCharacterOffset: columnInt(statement, offset + 4),
            endCharacterOffset: columnInt(statement, offset + 5),
            characterCount: columnInt(statement, offset + 6)
        )
    }

    private static func execute(_ database: OpaquePointer, _ sql: String) throws {
        var error: UnsafeMutablePointer<CChar>?
        if sqlite3_exec(database, sql, nil, nil, &error) != SQLITE_OK {
            let message = error.map { String(cString: $0) } ?? "unknown SQLite error"
            sqlite3_free(error)
            throw SQLiteRuntimeDocumentIndexStoreError(message)
        }
    }

    private static func prepare(_ database: OpaquePointer, _ sql: String) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw failure(database, "Could not prepare runtime document index SQLite statement.")
        }
        return statement
    }

    private static func bindText(_ value: String, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_text(statement, index, value, -1, sqliteDocumentIndexTransient) == SQLITE_OK else {
            throw SQLiteRuntimeDocumentIndexStoreError("Could not bind runtime document index SQLite text.")
        }
    }

    private static func bindInt(_ value: Int, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_int64(statement, index, sqlite3_int64(value)) == SQLITE_OK else {
            throw SQLiteRuntimeDocumentIndexStoreError("Could not bind runtime document index SQLite integer.")
        }
    }

    private static func bindOptionalInt(_ value: Int?, to statement: OpaquePointer, at index: Int32) throws {
        guard let value else {
            guard sqlite3_bind_null(statement, index) == SQLITE_OK else {
                throw SQLiteRuntimeDocumentIndexStoreError("Could not bind runtime document index SQLite null integer.")
            }
            return
        }
        try bindInt(value, to: statement, at: index)
    }

    private static func bindDouble(_ value: Double, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_double(statement, index, value) == SQLITE_OK else {
            throw SQLiteRuntimeDocumentIndexStoreError("Could not bind runtime document index SQLite double.")
        }
    }

    private static func bindOptionalText(_ value: String?, to statement: OpaquePointer, at index: Int32) throws {
        guard let value else {
            guard sqlite3_bind_null(statement, index) == SQLITE_OK else {
                throw SQLiteRuntimeDocumentIndexStoreError("Could not bind runtime document index SQLite null text.")
            }
            return
        }
        try bindText(value, to: statement, at: index)
    }

    private static func columnText(_ statement: OpaquePointer, _ index: Int32) throws -> String {
        guard let text = sqlite3_column_text(statement, index) else {
            throw SQLiteRuntimeDocumentIndexStoreError("Runtime document index SQLite text column is empty.")
        }
        return String(cString: text)
    }

    private static func columnInt(_ statement: OpaquePointer, _ index: Int32) -> Int {
        Int(sqlite3_column_int64(statement, index))
    }

    private static func columnOptionalInt(_ statement: OpaquePointer, _ index: Int32) -> Int? {
        sqlite3_column_type(statement, index) == SQLITE_NULL ? nil : columnInt(statement, index)
    }

    private static func columnDouble(_ statement: OpaquePointer, _ index: Int32) -> Double {
        sqlite3_column_double(statement, index)
    }

    private static func columnOptionalDouble(_ statement: OpaquePointer, _ index: Int32) -> Double? {
        sqlite3_column_type(statement, index) == SQLITE_NULL ? nil : columnDouble(statement, index)
    }

    private static func columnOptionalText(_ statement: OpaquePointer, _ index: Int32) -> String? {
        guard sqlite3_column_type(statement, index) != SQLITE_NULL,
              let text = sqlite3_column_text(statement, index) else { return nil }
        return String(cString: text)
    }

    private static func stepDone(_ statement: OpaquePointer, database: OpaquePointer) throws {
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw failure(database, "Could not write runtime document index SQLite row.")
        }
    }

    private static func ftsMatchQuery(for terms: [String]) -> String {
        terms
            .map { term in
                "\"\(term.replacingOccurrences(of: "\"", with: "\"\""))\""
            }
            .joined(separator: " OR ")
    }

    private static func failure(_ database: OpaquePointer, _ fallback: String) -> SQLiteRuntimeDocumentIndexStoreError {
        let message = sqlite3_errmsg(database).map { String(cString: $0) } ?? fallback
        return SQLiteRuntimeDocumentIndexStoreError(message.isEmpty ? fallback : message)
    }
}

extension SQLiteRuntimeDocumentIndexStore: RuntimeDocumentIndexReading {}
extension SQLiteRuntimeDocumentIndexStore: RuntimeDocumentSourceGovernance {}

private let sqliteDocumentIndexTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

private struct SQLiteRuntimeDocumentIndexStoreError: LocalizedError {
    var message: String

    init(_ message: String) {
        self.message = message
    }

    var errorDescription: String? {
        message
    }
}
