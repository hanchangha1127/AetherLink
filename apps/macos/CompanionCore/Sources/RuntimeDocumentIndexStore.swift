import DocumentIngestion
import Foundation

public struct RuntimeDocumentIndexDocument: Equatable, Sendable {
    public var id: String
    public var displayName: String
    public var mimeType: String
    public var contentFingerprint: String
    public var extractedCharacterCount: Int
    public var chunkCount: Int
    public var quality: DocumentIngestionQuality
}

public struct RuntimeDocumentIndexChunk: Equatable, Sendable {
    public var id: String
    public var documentID: String
    public var documentDisplayName: String
    public var documentMimeType: String
    public var chunkIndex: Int
    public var startCharacterOffset: Int
    public var endCharacterOffset: Int
    public var text: String
}

public struct RuntimeDocumentIndexChunkSummary: Equatable, Sendable {
    public var documentID: String
    public var documentDisplayName: String
    public var documentMimeType: String
    public var chunkIndex: Int
    public var startCharacterOffset: Int
    public var endCharacterOffset: Int
    public var characterCount: Int
}

public struct RuntimeDocumentSourceAnchor: Equatable, Sendable {
    public var sourceAnchorID: String
    public var document: RuntimeDocumentIndexDocument
    public var chunkSummary: RuntimeDocumentIndexChunkSummary
}

public enum RuntimeDocumentSearchMatchKind: String, Codable, Equatable, Sendable {
    case lexical
    case semantic
}

public struct RuntimeDocumentSearchResult: Equatable, Sendable {
    public var document: RuntimeDocumentIndexDocument
    public var chunk: RuntimeDocumentIndexChunk
    public var sourceAnchorID: String
    public var rank: Int
    public var matchedTerms: [String]
    public var snippet: String
    public var matchKind: RuntimeDocumentSearchMatchKind? = nil
}

public struct RuntimeDocumentIndexSummary: Equatable, Sendable {
    public var documentCount: Int
    public var chunkCount: Int
    public var extractedCharacterCount: Int
    public var qualityCounts: [DocumentIngestionQuality: Int]
}

public protocol RuntimeDocumentIndexCatalogReading {
    func documents(limit: Int) throws -> [RuntimeDocumentIndexDocument]
    func summary() throws -> RuntimeDocumentIndexSummary
}

public protocol RuntimeDocumentIndexSearchReading {
    func query(
        _ query: String,
        limit: Int,
        maxSnippetCharacters: Int
    ) throws -> [RuntimeDocumentSearchResult]
}

public protocol RuntimeDocumentSourceAnchorReading {
    func sourceAnchor(id sourceAnchorID: String) throws -> RuntimeDocumentSourceAnchor?
}

public protocol RuntimeDocumentIndexReading: RuntimeDocumentIndexCatalogReading, RuntimeDocumentIndexSearchReading, RuntimeDocumentSourceAnchorReading {}

struct RuntimeDocumentIndexChunkEnvelope: Equatable, Sendable {
    var chunkIndex: Int
    var startCharacterOffset: Int
    var endCharacterOffset: Int
}

let runtimeDocumentIndexCatalogLimitCeiling = 100
let runtimeDocumentIndexChunkReadLimitCeiling = 200
let runtimeDocumentIndexChunkSummaryLimitCeiling = 100
let runtimeDocumentIndexQueryLimitCeiling = 100
let runtimeDocumentIndexSnippetCharacterLimitCeiling = 500
let runtimeDocumentIndexDocumentIDCharacterLimitCeiling = 128
let runtimeDocumentIndexContentFingerprintCharacterCount = 16
let runtimeDocumentIndexMimeTypeCharacterLimitCeiling = 128
let runtimeDocumentIndexUnknownMimeType = "application/octet-stream"
let runtimeDocumentIndexDisplayNameCharacterLimitCeiling = 256
let runtimeDocumentIndexUnknownDisplayName = "untitled-document"
let runtimeDocumentIndexQueryTextCharacterLimitCeiling = 1_024
let runtimeDocumentIndexQueryTermLimitCeiling = 16
let runtimeDocumentIndexQueryTermCharacterLimitCeiling = 64
let runtimeDocumentSourceAnchorPrefix = "source_anchor_"

public final class RuntimeDocumentIndexStore {
    private var documentsByID: [String: RuntimeDocumentIndexDocument] = [:]
    private var chunksByDocumentID: [String: [RuntimeDocumentIndexChunk]] = [:]
    private var approvalsByDocumentID: [String: RuntimeDocumentSourceApproval] = [:]
    private var sourceAuditLog: [RuntimeDocumentSourceAuditEvent] = []
    private var citationsByID: [String: RuntimeStoredDocumentCitation] = [:]
    private var trustedSourceReviewsByID: [String: RuntimeStoredTrustedSourceReview] = [:]
    private var trustedSourceGrantsByID: [String: RuntimeStoredTrustedSourceGrant] = [:]
    private let sourceAuditEventLimit: Int
    private let lock = NSLock()

    public init(sourceAuditEventLimit: Int = 100_000) {
        self.sourceAuditEventLimit = max(1, min(sourceAuditEventLimit, runtimeDocumentSourceAuditEventLimitCeiling))
    }

    public static func stableDocumentID(for result: DocumentIngestionResult) -> String {
        let digest = stableHexDigest([
            runtimeDocumentIndexEffectiveDisplayName(for: result),
            runtimeDocumentIndexEffectiveMimeType(result.summary.documentMimeType),
            result.document.text
        ])
        return "doc_\(digest)"
    }

    public func replaceDocument(
        result: DocumentIngestionResult,
        documentID requestedDocumentID: String? = nil
    ) -> RuntimeDocumentIndexDocument {
        let documentID = runtimeDocumentIndexEffectiveDocumentID(
            requestedDocumentID,
            fallback: Self.stableDocumentID(for: result)
        )
        let document = runtimeDocumentIndexDocument(for: result, documentID: documentID)
        let chunks = runtimeDocumentIndexChunks(for: result, documentID: documentID)
        let timestamp = Date()
        let approval = runtimeDocumentHostApproval(
            document: document,
            chunks: chunks,
            timestamp: timestamp
        )

        lock.withLock {
            let wasApproved = approvalsByDocumentID[documentID] != nil
            if let currentApproval = approvalsByDocumentID[documentID],
               currentApproval.sourceRevision != approval.sourceRevision {
                invalidateCitationStateUnlocked(documentID: documentID, timestamp: timestamp)
            }
            documentsByID[documentID] = document
            chunksByDocumentID[documentID] = chunks
            approvalsByDocumentID[documentID] = approval
            if wasApproved {
                appendSourceAuditUnlocked(.reindexed, approval: approval, timestamp: timestamp)
            } else {
                appendSourceAuditUnlocked(.approved, approval: approval, timestamp: timestamp)
                appendSourceAuditUnlocked(.indexed, approval: approval, timestamp: timestamp)
            }
        }
        return document
    }

    public func deleteDocument(id documentID: String) {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return }
        lock.withLock {
            revokeAndDeleteDocumentUnlocked(documentID, timestamp: Date())
        }
    }

    public func deleteAllDocuments() {
        lock.withLock {
            let timestamp = Date()
            for documentID in documentsByID.keys.sorted() {
                revokeAndDeleteDocumentUnlocked(documentID, timestamp: timestamp)
            }
        }
    }

    public func deleteDocuments(matchingQuality quality: DocumentIngestionQuality) {
        lock.withLock {
            let documentIDs = documentsByID
                .values
                .filter { $0.quality == quality }
                .map(\.id)
            let timestamp = Date()
            for documentID in documentIDs {
                revokeAndDeleteDocumentUnlocked(documentID, timestamp: timestamp)
            }
        }
    }

    public func deleteDocuments(matchingContentFingerprint contentFingerprint: String) {
        guard let contentFingerprint = runtimeDocumentIndexCanonicalContentFingerprint(contentFingerprint) else { return }
        lock.withLock {
            let documentIDs = documentsByID
                .values
                .filter { $0.contentFingerprint == contentFingerprint }
                .map(\.id)
            let timestamp = Date()
            for documentID in documentIDs {
                revokeAndDeleteDocumentUnlocked(documentID, timestamp: timestamp)
            }
        }
    }

    public func deleteDocuments(matchingDisplayName displayName: String) {
        guard let displayName = runtimeDocumentIndexCanonicalDisplayName(displayName) else { return }
        lock.withLock {
            let documentIDs = documentsByID
                .values
                .filter { $0.displayName == displayName }
                .map(\.id)
            let timestamp = Date()
            for documentID in documentIDs {
                revokeAndDeleteDocumentUnlocked(documentID, timestamp: timestamp)
            }
        }
    }

    public func deleteDocuments(matchingMimeType mimeType: String) {
        guard let mimeType = runtimeDocumentIndexCanonicalMimeType(mimeType) else { return }
        lock.withLock {
            let documentIDs = documentsByID
                .values
                .filter { $0.mimeType == mimeType }
                .map(\.id)
            let timestamp = Date()
            for documentID in documentIDs {
                revokeAndDeleteDocumentUnlocked(documentID, timestamp: timestamp)
            }
        }
    }

    public func document(id documentID: String) -> RuntimeDocumentIndexDocument? {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return nil }
        return lock.withLock {
            guard approvalsByDocumentID[documentID] != nil else { return nil }
            return documentsByID[documentID]
        }
    }

    public func chunks(
        for documentID: String,
        limit: Int = 200
    ) -> [RuntimeDocumentIndexChunk] {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexChunkReadLimitCeiling
              ) else { return [] }
        let chunks: [RuntimeDocumentIndexChunk] = lock.withLock {
            guard approvalsByDocumentID[documentID] != nil else { return [] }
            return chunksByDocumentID[documentID] ?? []
        }
        return runtimeDocumentIndexChunksForRead(chunks, limit: effectiveLimit)
    }

    public func chunkSummaries(
        for documentID: String,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexChunkSummary] {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexChunkSummaryLimitCeiling
              ) else { return [] }
        let chunks: [RuntimeDocumentIndexChunk] = lock.withLock {
            guard approvalsByDocumentID[documentID] != nil else { return [] }
            return chunksByDocumentID[documentID] ?? []
        }
        return runtimeDocumentIndexChunkSummaries(chunks, limit: effectiveLimit)
    }

    public func sourceAnchor(id sourceAnchorID: String) -> RuntimeDocumentSourceAnchor? {
        guard let sourceAnchorID = runtimeDocumentIndexCanonicalSourceAnchorID(sourceAnchorID) else { return nil }
        let snapshot = lock.withLock {
            chunksByDocumentID
                .values
                .flatMap { $0 }
                .compactMap { chunk -> (RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunkSummary)? in
                    guard approvalsByDocumentID[chunk.documentID] != nil else { return nil }
                    guard let document = documentsByID[chunk.documentID] else { return nil }
                    return (document, runtimeDocumentIndexChunkSummary(chunk))
                }
        }
        return runtimeDocumentSourceAnchor(sourceAnchorID: sourceAnchorID, from: snapshot)
    }

    public func documents(limit: Int = 100) -> [RuntimeDocumentIndexDocument] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter { approvalsByDocumentID[$0.id] != nil }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
    }

    public func documents(
        matchingDisplayName displayName: String,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard let displayName = runtimeDocumentIndexCanonicalDisplayName(displayName),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter {
                approvalsByDocumentID[$0.id] != nil && $0.displayName == displayName
            }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
    }

    public func documents(
        matchingContentFingerprint contentFingerprint: String,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard let contentFingerprint = runtimeDocumentIndexCanonicalContentFingerprint(contentFingerprint),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter {
                approvalsByDocumentID[$0.id] != nil && $0.contentFingerprint == contentFingerprint
            }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
    }

    public func documents(
        matchingMimeType mimeType: String,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard let mimeType = runtimeDocumentIndexCanonicalMimeType(mimeType),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter {
                approvalsByDocumentID[$0.id] != nil && $0.mimeType == mimeType
            }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
    }

    public func documents(
        matchingQuality quality: DocumentIngestionQuality,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter {
                approvalsByDocumentID[$0.id] != nil && $0.quality == quality
            }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
    }

    public func summary() -> RuntimeDocumentIndexSummary {
        let documents = lock.withLock {
            documentsByID.values.filter { approvalsByDocumentID[$0.id] != nil }
        }
        return runtimeDocumentIndexSummary(documents)
    }

    public func query(
        _ query: String,
        limit: Int = 10,
        maxSnippetCharacters: Int = 160
    ) -> [RuntimeDocumentSearchResult] {
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

        let snapshot = lock.withLock {
            chunksByDocumentID
                .values
                .flatMap { $0 }
                .compactMap { chunk -> (RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)? in
                    guard approvalsByDocumentID[chunk.documentID] != nil else { return nil }
                    guard let document = documentsByID[chunk.documentID] else { return nil }
                    return (document, chunk)
                }
        }

        return runtimeDocumentSearchResults(
            from: snapshot,
            terms: terms,
            limit: effectiveLimit,
            maxSnippetCharacters: effectiveSnippetLimit
        )
    }

    public func readApprovedCatalog(
        limit: Int,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) -> RuntimeDocumentApprovedCatalog {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else {
            return RuntimeDocumentApprovedCatalog(
                documents: [],
                summary: runtimeDocumentIndexSummary([])
            )
        }
        return lock.withLock {
            let approvedDocuments = documentsByID.values.filter {
                approvalsByDocumentID[$0.id] != nil
            }
            let documents = runtimeDocumentIndexCatalogDocuments(
                approvedDocuments,
                limit: effectiveLimit
            )
            appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                action: .catalogListed,
                actorDeviceID: actorDeviceID,
                resultCount: documents.count,
                timestamp: timestamp
            ))
            return RuntimeDocumentApprovedCatalog(
                documents: documents,
                summary: runtimeDocumentIndexSummary(approvedDocuments)
            )
        }
    }

    public func queryApprovedDocuments(
        _ query: String,
        limit: Int,
        maxSnippetCharacters: Int,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) -> [RuntimeDocumentSearchResult] {
        let terms = runtimeDocumentSearchTerms(query)
        let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexQueryLimitCeiling
        )
        let effectiveSnippetLimit = runtimeDocumentIndexEffectiveLimit(
            maxSnippetCharacters,
            ceiling: runtimeDocumentIndexSnippetCharacterLimitCeiling
        )
        return lock.withLock {
            let results: [RuntimeDocumentSearchResult]
            if !terms.isEmpty,
               let effectiveLimit,
               let effectiveSnippetLimit {
                let snapshot = chunksByDocumentID
                    .values
                    .flatMap { $0 }
                    .compactMap { chunk -> (RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)? in
                        guard approvalsByDocumentID[chunk.documentID] != nil,
                              let document = documentsByID[chunk.documentID] else { return nil }
                        return (document, chunk)
                    }
                results = runtimeDocumentSearchResults(
                    from: snapshot,
                    terms: terms,
                    limit: effectiveLimit,
                    maxSnippetCharacters: effectiveSnippetLimit
                )
            } else {
                results = []
            }
            appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                action: .queried,
                actorDeviceID: actorDeviceID,
                resultCount: results.count,
                timestamp: timestamp
            ))
            return results
        }
    }

    public func resolveApprovedSourceAnchor(
        id sourceAnchorID: String,
        actorDeviceID: String?,
        timestamp: Date = Date()
    ) -> RuntimeDocumentSourceAnchor? {
        guard let sourceAnchorID = runtimeDocumentIndexCanonicalSourceAnchorID(sourceAnchorID) else { return nil }
        return lock.withLock {
            guard let anchor = approvedSourceAnchorUnlocked(sourceAnchorID: sourceAnchorID) else { return nil }
            appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                action: .anchorResolved,
                approval: approvalsByDocumentID[anchor.document.id],
                actorDeviceID: actorDeviceID,
                sourceAnchorID: sourceAnchorID,
                resultCount: 1,
                timestamp: timestamp
            ))
            return anchor
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
            guard let anchor = approvedSourceAnchorUnlocked(sourceAnchorID: sourceAnchorID),
                  let approval = approvalsByDocumentID[anchor.document.id] else {
                throw RuntimeTrustedSourceGovernanceError.citationNotFound
            }
            let citation = runtimeDocumentCitation(anchor: anchor, approval: approval)
            citationsByID[citation.citationID] = RuntimeStoredDocumentCitation(
                citation: citation,
                documentID: anchor.document.id,
                sourceRevision: approval.sourceRevision,
                issuedAt: timestamp,
                staleAt: nil
            )
            trustedSourceReviewsByID = trustedSourceReviewsByID.filter {
                $0.value.actorDeviceID != actorDeviceID
            }
            let review = runtimeTrustedSourceReview(
                citationID: citation.citationID,
                actorDeviceID: actorDeviceID,
                timestamp: timestamp
            )
            trustedSourceReviewsByID[review.reviewID] = RuntimeStoredTrustedSourceReview(
                review: review,
                citationID: citation.citationID,
                actorDeviceID: actorDeviceID
            )
            for action in [
                RuntimeDocumentSourceAuditAction.citationResolved,
                .trustedSourceReviewPrepared
            ] {
                appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                    action: action,
                    approval: approval,
                    actorDeviceID: actorDeviceID,
                    sourceAnchorID: sourceAnchorID,
                    resultCount: 1,
                    timestamp: timestamp
                ))
            }
            let existingGrant = (trustedSourceGrantsByID.values
                .first {
                    $0.actorDeviceID == actorDeviceID
                        && $0.documentID == approval.documentID
                        && $0.sourceRevision == approval.sourceRevision
                        && $0.revokedAt == nil
                })?.grant
            return RuntimeTrustedSourceReviewEnvelope(
                citation: citation,
                review: review,
                trustedSource: existingGrant
            )
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
            guard let storedReview = trustedSourceReviewsByID[reviewID],
                  storedReview.actorDeviceID == actorDeviceID,
                  storedReview.review.confirmationToken == confirmationToken else {
                throw RuntimeTrustedSourceGovernanceError.reviewNotFound
            }
            guard timestamp <= storedReview.review.expiresAt else {
                trustedSourceReviewsByID.removeValue(forKey: reviewID)
                throw RuntimeTrustedSourceGovernanceError.reviewExpired
            }
            guard let storedCitation = citationsByID[storedReview.citationID],
                  storedCitation.staleAt == nil,
                  let approval = approvalsByDocumentID[storedCitation.documentID],
                  approval.sourceRevision == storedCitation.sourceRevision,
                  approvedSourceAnchorUnlocked(
                      sourceAnchorID: storedCitation.citation.sourceAnchorID
                  ) != nil else {
                trustedSourceReviewsByID.removeValue(forKey: reviewID)
                throw RuntimeTrustedSourceGovernanceError.reviewStale
            }
            let grant = runtimeTrustedSourceGrant(
                citation: storedCitation.citation,
                approval: approval,
                actorDeviceID: actorDeviceID,
                timestamp: timestamp
            )
            trustedSourceGrantsByID[grant.grantID] = RuntimeStoredTrustedSourceGrant(
                grant: grant,
                documentID: approval.documentID,
                sourceRevision: approval.sourceRevision,
                actorDeviceID: actorDeviceID,
                revokedAt: nil
            )
            trustedSourceReviewsByID.removeValue(forKey: reviewID)
            appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                action: .trustedSourceApproved,
                approval: approval,
                actorDeviceID: actorDeviceID,
                sourceAnchorID: storedCitation.citation.sourceAnchorID,
                resultCount: 1,
                timestamp: timestamp
            ))
            return grant
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
            guard let review = trustedSourceReviewsByID[reviewID],
                  review.actorDeviceID == actorDeviceID else {
                throw RuntimeTrustedSourceGovernanceError.reviewNotFound
            }
            trustedSourceReviewsByID.removeValue(forKey: reviewID)
            let citation = citationsByID[review.citationID]
            appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                action: .trustedSourceReviewDismissed,
                approval: citation.flatMap { approvalsByDocumentID[$0.documentID] },
                actorDeviceID: actorDeviceID,
                sourceAnchorID: citation?.citation.sourceAnchorID,
                resultCount: 0,
                timestamp: timestamp
            ))
        }
    }

    public func trustedSources(
        actorDeviceID: String?,
        limit: Int,
        timestamp: Date = Date()
    ) throws -> [RuntimeTrustedSourceGrant] {
        guard let actorDeviceID = runtimeDocumentCanonicalAuditActor(actorDeviceID) else { return [] }
        let effectiveLimit = min(max(0, limit), runtimeTrustedSourceListLimitCeiling)
        return lock.withLock {
            let grants = trustedSourceGrantsByID.values
                .filter { stored in
                    guard stored.actorDeviceID == actorDeviceID,
                          stored.revokedAt == nil,
                          let approval = approvalsByDocumentID[stored.documentID] else {
                        return false
                    }
                    return approval.sourceRevision == stored.sourceRevision
                }
                .map(\.grant)
                .sorted {
                    if $0.approvedAt != $1.approvedAt { return $0.approvedAt > $1.approvedAt }
                    return $0.grantID < $1.grantID
                }
            let result = Array(grants.prefix(effectiveLimit))
            appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                action: .trustedSourcesListed,
                actorDeviceID: actorDeviceID,
                resultCount: result.count,
                timestamp: timestamp
            ))
            return result
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
            guard var stored = trustedSourceGrantsByID[grantID],
                  stored.actorDeviceID == actorDeviceID,
                  stored.revokedAt == nil else {
                throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
            }
            stored.revokedAt = timestamp
            trustedSourceGrantsByID[grantID] = stored
            appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                action: .trustedSourceRevoked,
                approval: approvalsByDocumentID[stored.documentID],
                actorDeviceID: actorDeviceID,
                sourceAnchorID: stored.grant.sourceAnchorID,
                resultCount: 0,
                timestamp: timestamp
            ))
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
            let contexts = try grantIDs.map { grantID -> RuntimeTrustedSourceChatContext in
                guard let storedGrant = trustedSourceGrantsByID[grantID],
                      storedGrant.actorDeviceID == actorDeviceID,
                      storedGrant.revokedAt == nil,
                      storedGrant.grant.usageScope == .chatContext,
                      let storedCitation = citationsByID[storedGrant.grant.citationID],
                      storedCitation.staleAt == nil,
                      storedCitation.documentID == storedGrant.documentID,
                      storedCitation.sourceRevision == storedGrant.sourceRevision,
                      storedCitation.citation.sourceAnchorID == storedGrant.grant.sourceAnchorID,
                      let approval = approvalsByDocumentID[storedGrant.documentID],
                      approval.scope == .runtimeShared,
                      approval.sourceRevision == storedGrant.sourceRevision,
                      let document = documentsByID[storedGrant.documentID],
                      document == storedCitation.citation.document,
                      let chunk = chunksByDocumentID[storedGrant.documentID]?.first(where: {
                          let summary = runtimeDocumentIndexChunkSummary($0)
                          return summary == storedCitation.citation.chunkSummary
                              && runtimeDocumentSourceAnchorID(
                                  document: document,
                                  chunkSummary: summary
                              ) == storedGrant.grant.sourceAnchorID
                      }),
                      let text = runtimeTrustedSourceChatContextText(chunk.text) else {
                    throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
                }
                let anchor = RuntimeDocumentSourceAnchor(
                    sourceAnchorID: storedGrant.grant.sourceAnchorID,
                    document: document,
                    chunkSummary: runtimeDocumentIndexChunkSummary(chunk)
                )
                guard runtimeDocumentCitation(anchor: anchor, approval: approval).citationID
                        == storedGrant.grant.citationID else {
                    throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
                }
                return RuntimeTrustedSourceChatContext(
                    grantID: grantID,
                    citationID: storedGrant.grant.citationID,
                    sourceAnchorID: storedGrant.grant.sourceAnchorID,
                    document: document,
                    chunkSummary: anchor.chunkSummary,
                    text: text
                )
            }
            for context in contexts {
                appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                    action: .trustedSourceContextConsumed,
                    approval: approvalsByDocumentID[context.document.id],
                    actorDeviceID: actorDeviceID,
                    sourceAnchorID: context.sourceAnchorID,
                    resultCount: 1,
                    timestamp: timestamp
                ))
            }
            return contexts
        }
    }

    public func sourceApproval(documentID: String) -> RuntimeDocumentSourceApproval? {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return nil }
        return lock.withLock { approvalsByDocumentID[documentID] }
    }

    public func recordSourceAudit(
        action: RuntimeDocumentSourceAuditAction,
        actorDeviceID: String?,
        documentID: String?,
        sourceAnchorID: String?,
        resultCount: Int?,
        timestamp: Date = Date()
    ) {
        lock.withLock {
            appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
                action: action,
                approval: documentID.flatMap { approvalsByDocumentID[$0] },
                actorDeviceID: actorDeviceID,
                documentID: documentID,
                sourceAnchorID: sourceAnchorID,
                resultCount: resultCount,
                timestamp: timestamp
            ))
        }
    }

    public func sourceAuditEvents(limit: Int = 100) -> [RuntimeDocumentSourceAuditEvent] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentSourceAuditLimitCeiling
        ) else { return [] }
        return lock.withLock {
            Array(sourceAuditLog.suffix(effectiveLimit).reversed())
        }
    }

    private func appendSourceAuditEventUnlocked(_ event: RuntimeDocumentSourceAuditEvent) {
        sourceAuditLog.append(event)
        let overflow = sourceAuditLog.count - sourceAuditEventLimit
        if overflow > 0 {
            sourceAuditLog.removeFirst(overflow)
        }
    }

    private func appendSourceAuditUnlocked(
        _ action: RuntimeDocumentSourceAuditAction,
        approval: RuntimeDocumentSourceApproval,
        timestamp: Date
    ) {
        appendSourceAuditEventUnlocked(runtimeDocumentAuditEvent(
            action: action,
            approval: approval,
            actorDeviceID: approval.approvedBy,
            timestamp: timestamp
        ))
    }

    private func revokeAndDeleteDocumentUnlocked(_ documentID: String, timestamp: Date) {
        guard documentsByID[documentID] != nil else { return }
        invalidateCitationStateUnlocked(documentID: documentID, timestamp: timestamp)
        if let approval = approvalsByDocumentID[documentID] {
            appendSourceAuditUnlocked(.revoked, approval: approval, timestamp: timestamp)
            appendSourceAuditUnlocked(.deleted, approval: approval, timestamp: timestamp)
        }
        approvalsByDocumentID.removeValue(forKey: documentID)
        documentsByID.removeValue(forKey: documentID)
        chunksByDocumentID.removeValue(forKey: documentID)
    }

    private func approvedSourceAnchorUnlocked(sourceAnchorID: String) -> RuntimeDocumentSourceAnchor? {
        let snapshot = chunksByDocumentID
            .values
            .flatMap { $0 }
            .compactMap { chunk -> (RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunkSummary)? in
                guard approvalsByDocumentID[chunk.documentID] != nil,
                      let document = documentsByID[chunk.documentID] else { return nil }
                return (document, runtimeDocumentIndexChunkSummary(chunk))
            }
        return runtimeDocumentSourceAnchor(sourceAnchorID: sourceAnchorID, from: snapshot)
    }

    private func invalidateCitationStateUnlocked(documentID: String, timestamp: Date) {
        for citationID in Array(citationsByID.keys) {
            guard var citation = citationsByID[citationID],
                  citation.documentID == documentID,
                  citation.staleAt == nil else { continue }
            citation.staleAt = timestamp
            citationsByID[citationID] = citation
        }
        for grantID in Array(trustedSourceGrantsByID.keys) {
            guard var grant = trustedSourceGrantsByID[grantID],
                  grant.documentID == documentID,
                  grant.revokedAt == nil else { continue }
            grant.revokedAt = timestamp
            trustedSourceGrantsByID[grantID] = grant
        }
    }

    static func stableContentFingerprint(for result: DocumentIngestionResult) -> String {
        stableHexDigest([
            runtimeDocumentIndexEffectiveMimeType(result.summary.documentMimeType),
            result.document.text,
            String(runtimeDocumentIndexEffectiveExtractedCharacterCount(for: result)),
            String(runtimeDocumentIndexEffectiveChunkCount(for: result))
        ])
    }

    static func stableChunkID(
        documentID: String,
        chunkIndex: Int,
        startCharacterOffset: Int,
        endCharacterOffset: Int,
        text: String
    ) -> String {
        let digest = stableHexDigest([
            documentID,
            String(chunkIndex),
            String(startCharacterOffset),
            String(endCharacterOffset),
            text
        ])
        return "chunk_\(digest)"
    }
}

extension RuntimeDocumentIndexStore: RuntimeDocumentIndexReading {}
extension RuntimeDocumentIndexStore: RuntimeDocumentSourceGovernance {}

func runtimeDocumentIndexDocument(
    for result: DocumentIngestionResult,
    documentID: String
) -> RuntimeDocumentIndexDocument {
    RuntimeDocumentIndexDocument(
        id: documentID,
        displayName: runtimeDocumentIndexEffectiveDisplayName(for: result),
        mimeType: runtimeDocumentIndexEffectiveMimeType(result.summary.documentMimeType),
        contentFingerprint: RuntimeDocumentIndexStore.stableContentFingerprint(for: result),
        extractedCharacterCount: runtimeDocumentIndexEffectiveExtractedCharacterCount(for: result),
        chunkCount: runtimeDocumentIndexEffectiveChunkCount(for: result),
        quality: runtimeDocumentIndexEffectiveQuality(for: result)
    )
}

func runtimeDocumentIndexEffectiveExtractedCharacterCount(for result: DocumentIngestionResult) -> Int {
    result.document.text.trimmingCharacters(in: .whitespacesAndNewlines).count
}

func runtimeDocumentIndexEffectiveChunkCount(for result: DocumentIngestionResult) -> Int {
    result.chunks.count
}

func runtimeDocumentIndexEffectiveQuality(for result: DocumentIngestionResult) -> DocumentIngestionQuality {
    switch runtimeDocumentIndexEffectiveChunkCount(for: result) {
    case 0:
        return .noUsableText
    case 1:
        return .singleChunk
    default:
        return .chunked
    }
}

func runtimeDocumentIndexEffectiveDisplayName(for result: DocumentIngestionResult) -> String {
    runtimeDocumentIndexCanonicalDisplayName(result.document.fileName)
        ?? runtimeDocumentIndexCanonicalDisplayName(result.summary.documentFileName)
        ?? runtimeDocumentIndexUnknownDisplayName
}

func runtimeDocumentIndexChunks(
    for result: DocumentIngestionResult,
    documentID: String
) -> [RuntimeDocumentIndexChunk] {
    let documentDisplayName = runtimeDocumentIndexEffectiveDisplayName(for: result)
    let documentCharacters = Array(result.document.text.trimmingCharacters(in: .whitespacesAndNewlines))
    var fallbackStartOffset = 0
    var minimumSearchStartOffset = 0

    return result.chunks.enumerated().map { canonicalIndex, chunk in
        let envelope = runtimeDocumentIndexEffectiveChunkEnvelope(
            for: chunk,
            canonicalIndex: canonicalIndex,
            documentCharacters: documentCharacters,
            minimumSearchStartOffset: minimumSearchStartOffset,
            fallbackStartOffset: fallbackStartOffset
        )
        fallbackStartOffset = max(fallbackStartOffset, envelope.endCharacterOffset)
        minimumSearchStartOffset = min(envelope.startCharacterOffset + 1, documentCharacters.count)

        return RuntimeDocumentIndexChunk(
            id: RuntimeDocumentIndexStore.stableChunkID(
                documentID: documentID,
                chunkIndex: envelope.chunkIndex,
                startCharacterOffset: envelope.startCharacterOffset,
                endCharacterOffset: envelope.endCharacterOffset,
                text: chunk.text
            ),
            documentID: documentID,
            documentDisplayName: documentDisplayName,
            documentMimeType: runtimeDocumentIndexEffectiveMimeType(chunk.documentMimeType),
            chunkIndex: envelope.chunkIndex,
            startCharacterOffset: envelope.startCharacterOffset,
            endCharacterOffset: envelope.endCharacterOffset,
            text: chunk.text
        )
    }
}

func runtimeDocumentIndexEffectiveChunkEnvelope(
    for chunk: DocumentChunk,
    canonicalIndex: Int,
    documentCharacters: [Character],
    minimumSearchStartOffset: Int,
    fallbackStartOffset: Int
) -> RuntimeDocumentIndexChunkEnvelope {
    let offsets = runtimeDocumentIndexValidatedChunkOffsets(
        for: chunk,
        documentCharacters: documentCharacters,
        minimumSearchStartOffset: minimumSearchStartOffset
    )
        ?? runtimeDocumentIndexLocatedChunkOffsets(
            for: chunk.text,
            documentCharacters: documentCharacters,
            minimumSearchStartOffset: minimumSearchStartOffset
        )
        ?? runtimeDocumentIndexFallbackChunkOffsets(
            for: chunk.text,
            documentCharacterCount: documentCharacters.count,
            fallbackStartOffset: fallbackStartOffset
        )
    return RuntimeDocumentIndexChunkEnvelope(
        chunkIndex: canonicalIndex,
        startCharacterOffset: offsets.start,
        endCharacterOffset: offsets.end
    )
}

func runtimeDocumentIndexValidatedChunkOffsets(
    for chunk: DocumentChunk,
    documentCharacters: [Character],
    minimumSearchStartOffset: Int
) -> (start: Int, end: Int)? {
    guard chunk.startCharacterOffset >= 0,
          chunk.startCharacterOffset >= minimumSearchStartOffset,
          chunk.endCharacterOffset >= chunk.startCharacterOffset,
          chunk.endCharacterOffset <= documentCharacters.count else { return nil }
    let text = String(documentCharacters[chunk.startCharacterOffset..<chunk.endCharacterOffset])
    guard text == chunk.text else { return nil }
    return (chunk.startCharacterOffset, chunk.endCharacterOffset)
}

func runtimeDocumentIndexLocatedChunkOffsets(
    for text: String,
    documentCharacters: [Character],
    minimumSearchStartOffset: Int
) -> (start: Int, end: Int)? {
    let chunkCharacters = Array(text)
    guard !chunkCharacters.isEmpty,
          chunkCharacters.count <= documentCharacters.count else { return nil }
    let lastStart = documentCharacters.count - chunkCharacters.count
    let firstStart = min(max(minimumSearchStartOffset, 0), documentCharacters.count)
    guard firstStart <= lastStart else { return nil }
    for start in firstStart...lastStart {
        let end = start + chunkCharacters.count
        if Array(documentCharacters[start..<end]) == chunkCharacters {
            return (start, end)
        }
    }
    return nil
}

func runtimeDocumentIndexFallbackChunkOffsets(
    for text: String,
    documentCharacterCount: Int,
    fallbackStartOffset: Int
) -> (start: Int, end: Int) {
    let start = min(max(fallbackStartOffset, 0), documentCharacterCount)
    let end = min(start + text.count, documentCharacterCount)
    return (start, end)
}

func runtimeDocumentIndexEffectiveDocumentID(_ requestedDocumentID: String?, fallback: String) -> String {
    runtimeDocumentIndexCanonicalDocumentID(requestedDocumentID) ?? fallback
}

func runtimeDocumentIndexCanonicalDocumentID(_ documentID: String?) -> String? {
    guard let documentID else { return nil }
    let trimmed = documentID.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty,
          !trimmed.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }),
          trimmed.count <= runtimeDocumentIndexDocumentIDCharacterLimitCeiling else { return nil }
    return trimmed
}

func runtimeDocumentIndexCanonicalDisplayName(_ displayName: String?) -> String? {
    guard let displayName else { return nil }
    let trimmed = displayName.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { return nil }

    let normalizedSeparators = trimmed.replacingOccurrences(of: "\\", with: "/")
    guard let lastComponent = normalizedSeparators
        .split(separator: "/", omittingEmptySubsequences: true)
        .last
        .map(String.init)?
        .trimmingCharacters(in: .whitespacesAndNewlines),
        !lastComponent.isEmpty,
        lastComponent != ".",
        lastComponent != "..",
        !lastComponent.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }),
        lastComponent.count <= runtimeDocumentIndexDisplayNameCharacterLimitCeiling
    else { return nil }

    return lastComponent
}

func runtimeDocumentIndexCanonicalContentFingerprint(_ contentFingerprint: String?) -> String? {
    guard let contentFingerprint else { return nil }
    let trimmed = contentFingerprint.trimmingCharacters(in: .whitespacesAndNewlines)
    guard trimmed.count == runtimeDocumentIndexContentFingerprintCharacterCount,
          trimmed.utf8.allSatisfy({ byte in
            (byte >= 48 && byte <= 57) || (byte >= 97 && byte <= 102)
          }) else { return nil }
    return trimmed
}

func runtimeDocumentIndexCanonicalSourceAnchorID(_ sourceAnchorID: String?) -> String? {
    guard let sourceAnchorID else { return nil }
    let trimmed = sourceAnchorID.trimmingCharacters(in: .whitespacesAndNewlines)
    guard trimmed == sourceAnchorID,
          sourceAnchorID.hasPrefix(runtimeDocumentSourceAnchorPrefix) else { return nil }
    let digest = String(sourceAnchorID.dropFirst(runtimeDocumentSourceAnchorPrefix.count))
    guard digest.count == runtimeDocumentIndexContentFingerprintCharacterCount,
          digest.utf8.allSatisfy({ byte in
            (byte >= 48 && byte <= 57) || (byte >= 97 && byte <= 102)
          }) else { return nil }
    return sourceAnchorID
}

func runtimeDocumentIndexEffectiveMimeType(_ mimeType: String?) -> String {
    runtimeDocumentIndexCanonicalMimeType(mimeType) ?? runtimeDocumentIndexUnknownMimeType
}

func runtimeDocumentIndexCanonicalMimeType(_ mimeType: String?) -> String? {
    guard let mimeType else { return nil }
    let trimmed = mimeType.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty,
          trimmed.count <= runtimeDocumentIndexMimeTypeCharacterLimitCeiling else { return nil }
    let parts = trimmed.split(separator: "/", omittingEmptySubsequences: false)
    guard parts.count == 2,
          parts.allSatisfy({ !$0.isEmpty }),
          parts.allSatisfy({ component in
            component.utf8.allSatisfy(runtimeDocumentIndexMimeTypeTokenByteIsAllowed)
          }) else { return nil }
    return trimmed
}

private func runtimeDocumentIndexMimeTypeTokenByteIsAllowed(_ byte: UInt8) -> Bool {
    (byte >= 48 && byte <= 57)
        || (byte >= 97 && byte <= 122)
        || byte == 33
        || byte == 35
        || byte == 36
        || byte == 37
        || byte == 38
        || byte == 39
        || byte == 42
        || byte == 43
        || byte == 45
        || byte == 46
        || byte == 94
        || byte == 95
        || byte == 96
        || byte == 124
        || byte == 126
}

func runtimeDocumentIndexChunkSummaries(
    _ chunks: [RuntimeDocumentIndexChunk],
    limit: Int
) -> [RuntimeDocumentIndexChunkSummary] {
    guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
        limit,
        ceiling: runtimeDocumentIndexChunkSummaryLimitCeiling
    ) else { return [] }
    return chunks
        .sorted { lhs, rhs in lhs.chunkIndex < rhs.chunkIndex }
        .prefix(effectiveLimit)
        .map(runtimeDocumentIndexChunkSummary)
}

func runtimeDocumentIndexChunkSummary(_ chunk: RuntimeDocumentIndexChunk) -> RuntimeDocumentIndexChunkSummary {
    RuntimeDocumentIndexChunkSummary(
        documentID: chunk.documentID,
        documentDisplayName: chunk.documentDisplayName,
        documentMimeType: chunk.documentMimeType,
        chunkIndex: chunk.chunkIndex,
        startCharacterOffset: chunk.startCharacterOffset,
        endCharacterOffset: chunk.endCharacterOffset,
        characterCount: chunk.text.count
    )
}

func runtimeDocumentSourceAnchor(
    sourceAnchorID: String,
    from snapshot: [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunkSummary)]
) -> RuntimeDocumentSourceAnchor? {
    snapshot
        .map { document, chunkSummary in
            RuntimeDocumentSourceAnchor(
                sourceAnchorID: runtimeDocumentSourceAnchorID(document: document, chunkSummary: chunkSummary),
                document: document,
                chunkSummary: chunkSummary
            )
        }
        .first { $0.sourceAnchorID == sourceAnchorID }
}

func runtimeDocumentIndexChunksForRead(
    _ chunks: [RuntimeDocumentIndexChunk],
    limit: Int
) -> [RuntimeDocumentIndexChunk] {
    guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
        limit,
        ceiling: runtimeDocumentIndexChunkReadLimitCeiling
    ) else { return [] }
    return chunks
        .sorted { lhs, rhs in lhs.chunkIndex < rhs.chunkIndex }
        .prefix(effectiveLimit)
        .map { $0 }
}

func runtimeDocumentIndexCatalogDocuments(
    _ documents: [RuntimeDocumentIndexDocument],
    limit: Int
) -> [RuntimeDocumentIndexDocument] {
    guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
        limit,
        ceiling: runtimeDocumentIndexCatalogLimitCeiling
    ) else { return [] }
    return documents
        .sorted { lhs, rhs in
            if lhs.displayName != rhs.displayName {
                return lhs.displayName < rhs.displayName
            }
            return lhs.id < rhs.id
        }
        .prefix(effectiveLimit)
        .map { $0 }
}

func runtimeDocumentIndexSummary(
    _ documents: [RuntimeDocumentIndexDocument]
) -> RuntimeDocumentIndexSummary {
    documents.reduce(into: RuntimeDocumentIndexSummary(
        documentCount: 0,
        chunkCount: 0,
        extractedCharacterCount: 0,
        qualityCounts: [:]
    )) { summary, document in
        summary.documentCount += 1
        summary.chunkCount += document.chunkCount
        summary.extractedCharacterCount += document.extractedCharacterCount
        summary.qualityCounts[document.quality, default: 0] += 1
    }
}

func runtimeDocumentSearchTerms(_ query: String) -> [String] {
    runtimeDocumentIndexEffectiveSearchTerms(query)
}

func runtimeDocumentIndexEffectiveSearchTerms(_ query: String) -> [String] {
    guard query.count <= runtimeDocumentIndexQueryTextCharacterLimitCeiling else { return [] }

    var seen = Set<String>()
    var terms: [String] = []
    for rawTerm in query.lowercased().split(whereSeparator: { character in
        !character.unicodeScalars.allSatisfy { CharacterSet.alphanumerics.contains($0) }
    }) {
        let term = String(rawTerm)
        guard term.count <= runtimeDocumentIndexQueryTermCharacterLimitCeiling else { return [] }
        guard !term.isEmpty, !seen.contains(term) else { continue }
        seen.insert(term)
        terms.append(term)
        guard terms.count <= runtimeDocumentIndexQueryTermLimitCeiling else { return [] }
    }
    return terms
}

func runtimeDocumentSearchResults(
    from snapshot: [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)],
    query: String,
    limit: Int = 10,
    maxSnippetCharacters: Int = 160
) -> [RuntimeDocumentSearchResult] {
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
    return runtimeDocumentSearchResults(
        from: snapshot,
        terms: terms,
        limit: effectiveLimit,
        maxSnippetCharacters: effectiveSnippetLimit
    )
}

private func runtimeDocumentSearchResults(
    from snapshot: [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)],
    terms: [String],
    limit: Int,
    maxSnippetCharacters: Int
) -> [RuntimeDocumentSearchResult] {
    guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
        limit,
        ceiling: runtimeDocumentIndexQueryLimitCeiling
    ),
          let effectiveSnippetLimit = runtimeDocumentIndexEffectiveLimit(
            maxSnippetCharacters,
            ceiling: runtimeDocumentIndexSnippetCharacterLimitCeiling
          ) else { return [] }
    return snapshot.compactMap { document, chunk in
        let counts = matchCounts(in: chunk.text, terms: terms)
        let matchedTerms = terms.filter { (counts[$0] ?? 0) > 0 }
        guard !matchedTerms.isEmpty else { return nil }
        let rank = matchedTerms.count * 100 + counts.values.reduce(0, +)
        return RuntimeDocumentSearchResult(
            document: document,
            chunk: chunk,
            sourceAnchorID: runtimeDocumentSourceAnchorID(document: document, chunk: chunk),
            rank: rank,
            matchedTerms: matchedTerms,
            snippet: boundedSnippet(from: chunk.text, terms: matchedTerms, maxCharacters: effectiveSnippetLimit)
        )
    }
    .sorted { lhs, rhs in
        if lhs.rank != rhs.rank { return lhs.rank > rhs.rank }
        if lhs.document.displayName != rhs.document.displayName {
            return lhs.document.displayName < rhs.document.displayName
        }
        return lhs.chunk.chunkIndex < rhs.chunk.chunkIndex
    }
    .prefix(effectiveLimit)
    .map { $0 }
}

func runtimeDocumentSourceAnchorID(
    document: RuntimeDocumentIndexDocument,
    chunk: RuntimeDocumentIndexChunk
) -> String {
    runtimeDocumentSourceAnchorID(document: document, chunkSummary: runtimeDocumentIndexChunkSummary(chunk))
}

func runtimeDocumentSourceAnchorID(
    document: RuntimeDocumentIndexDocument,
    chunkSummary: RuntimeDocumentIndexChunkSummary
) -> String {
    let digest = stableHexDigest([
        "runtime-document-source-anchor-v1",
        document.id,
        document.contentFingerprint,
        String(chunkSummary.chunkIndex),
        String(chunkSummary.startCharacterOffset),
        String(chunkSummary.endCharacterOffset)
    ])
    return "\(runtimeDocumentSourceAnchorPrefix)\(digest)"
}

func runtimeDocumentIndexEffectiveLimit(_ requestedLimit: Int, ceiling: Int) -> Int? {
    guard requestedLimit > 0, ceiling > 0 else { return nil }
    return min(requestedLimit, ceiling)
}

private func matchCounts(in text: String, terms: [String]) -> [String: Int] {
    let searchableText = text.lowercased()
    return terms.reduce(into: [String: Int]()) { counts, term in
        var searchStart = searchableText.startIndex
        while let range = searchableText.range(of: term, range: searchStart..<searchableText.endIndex) {
            counts[term, default: 0] += 1
            searchStart = range.upperBound
        }
    }
}

private func boundedSnippet(from text: String, terms: [String], maxCharacters: Int) -> String {
    guard maxCharacters > 0 else { return "" }
    guard let firstRange = firstMatchRange(in: text, terms: terms) else {
        return String(text.prefix(maxCharacters))
    }

    let usesPrefix = firstRange.lowerBound > text.startIndex
    let usesSuffix = firstRange.upperBound < text.endIndex
    let prefix = usesPrefix ? "..." : ""
    let suffix = usesSuffix ? "..." : ""
    let contentBudget = max(0, maxCharacters - prefix.count - suffix.count)
    guard contentBudget > 0 else {
        return String((prefix + suffix).prefix(maxCharacters))
    }

    let matchedOffset = text.distance(from: text.startIndex, to: firstRange.lowerBound)
    let halfBudget = max(0, contentBudget / 2)
    let startOffset = max(0, matchedOffset - halfBudget)
    let startIndex = text.index(text.startIndex, offsetBy: startOffset)
    let endIndex = text.index(startIndex, offsetBy: min(contentBudget, text.distance(from: startIndex, to: text.endIndex)))
    return prefix + text[startIndex..<endIndex].trimmingCharacters(in: .whitespacesAndNewlines) + suffix
}

private func firstMatchRange(in text: String, terms: [String]) -> Range<String.Index>? {
    terms
        .compactMap { term in
            text.range(of: term, options: [.caseInsensitive, .diacriticInsensitive])
        }
        .min { lhs, rhs in lhs.lowerBound < rhs.lowerBound }
}

private func stableHexDigest(_ values: [String]) -> String {
    var hash: UInt64 = 0xcbf29ce484222325
    for value in values {
        for byte in value.utf8 {
            hash ^= UInt64(byte)
            hash = hash &* 0x100000001b3
        }
        hash ^= 0xff
        hash = hash &* 0x100000001b3
    }
    let hex = String(hash, radix: 16)
    return String(repeating: "0", count: max(0, 16 - hex.count)) + hex
}

private extension NSLock {
    func withLock<T>(_ operation: () -> T) -> T {
        lock()
        defer { unlock() }
        return operation()
    }
}
