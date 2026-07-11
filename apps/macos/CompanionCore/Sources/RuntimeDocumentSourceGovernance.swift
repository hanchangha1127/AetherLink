import CryptoKit
import Foundation

let runtimeDocumentSourceAuditEventLimitCeiling = 100_000

public enum RuntimeDocumentSourceApprovalScope: String, Codable, Sendable {
    case runtimeShared = "runtime_shared"
}

public struct RuntimeDocumentSourceApproval: Equatable, Codable, Sendable {
    public var approvalID: String
    public var documentID: String
    public var sourceRevision: String
    public var scope: RuntimeDocumentSourceApprovalScope
    public var approvedBy: String
    public var approvedAt: Date
}

public enum RuntimeDocumentSourceAuditAction: String, Codable, Sendable {
    case approved
    case indexed
    case reindexed
    case catalogListed = "catalog_listed"
    case semanticAccessed = "semantic_accessed"
    case queried
    case anchorResolved = "anchor_resolved"
    case citationResolved = "citation_resolved"
    case trustedSourceReviewPrepared = "trusted_source_review_prepared"
    case trustedSourceReviewDismissed = "trusted_source_review_dismissed"
    case trustedSourceApproved = "trusted_source_approved"
    case trustedSourcesListed = "trusted_sources_listed"
    case trustedSourceRevoked = "trusted_source_revoked"
    case trustedSourceContextConsumed = "trusted_source_context_consumed"
    case revoked
    case deleted
}

public struct RuntimeDocumentSourceAuditEvent: Equatable, Codable, Sendable {
    public var eventID: String
    public var action: RuntimeDocumentSourceAuditAction
    public var documentID: String?
    public var sourceRevision: String?
    public var actorDeviceID: String?
    public var sourceAnchorID: String?
    public var resultCount: Int?
    public var occurredAt: Date
}

public struct RuntimeDocumentApprovedCatalog: Equatable, Sendable {
    public var documents: [RuntimeDocumentIndexDocument]
    public var summary: RuntimeDocumentIndexSummary
}

public protocol RuntimeDocumentSourceGovernance {
    func readApprovedCatalog(
        limit: Int,
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> RuntimeDocumentApprovedCatalog
    func queryApprovedDocuments(
        _ query: String,
        limit: Int,
        maxSnippetCharacters: Int,
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> [RuntimeDocumentSearchResult]
    func resolveApprovedSourceAnchor(
        id sourceAnchorID: String,
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> RuntimeDocumentSourceAnchor?
    func prepareTrustedSourceReview(
        sourceAnchorID: String,
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> RuntimeTrustedSourceReviewEnvelope
    func approveTrustedSourceReview(
        reviewID: String,
        confirmationToken: String,
        disclosureVersion: String,
        usageScope: RuntimeTrustedSourceUsageScope,
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> RuntimeTrustedSourceGrant
    func dismissTrustedSourceReview(
        reviewID: String,
        actorDeviceID: String?,
        timestamp: Date
    ) throws
    func trustedSources(
        actorDeviceID: String?,
        limit: Int,
        timestamp: Date
    ) throws -> [RuntimeTrustedSourceGrant]
    func revokeTrustedSource(
        grantID: String,
        actorDeviceID: String?,
        timestamp: Date
    ) throws
    func consumeTrustedSourceChatContexts(
        grantIDs: [String],
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> [RuntimeTrustedSourceChatContext]
    func sourceApproval(documentID: String) throws -> RuntimeDocumentSourceApproval?
    func recordSourceAudit(
        action: RuntimeDocumentSourceAuditAction,
        actorDeviceID: String?,
        documentID: String?,
        sourceAnchorID: String?,
        resultCount: Int?,
        timestamp: Date
    ) throws
    func sourceAuditEvents(limit: Int) throws -> [RuntimeDocumentSourceAuditEvent]
}

public extension RuntimeDocumentSourceGovernance {
    func prepareTrustedSourceReview(
        sourceAnchorID: String,
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> RuntimeTrustedSourceReviewEnvelope {
        throw RuntimeTrustedSourceGovernanceError.citationNotFound
    }

    func approveTrustedSourceReview(
        reviewID: String,
        confirmationToken: String,
        disclosureVersion: String,
        usageScope: RuntimeTrustedSourceUsageScope,
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> RuntimeTrustedSourceGrant {
        throw RuntimeTrustedSourceGovernanceError.reviewNotFound
    }

    func consumeTrustedSourceChatContexts(
        grantIDs: [String],
        actorDeviceID: String?,
        timestamp: Date
    ) throws -> [RuntimeTrustedSourceChatContext] {
        throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
    }

    func dismissTrustedSourceReview(
        reviewID: String,
        actorDeviceID: String?,
        timestamp: Date
    ) throws {
        throw RuntimeTrustedSourceGovernanceError.reviewNotFound
    }

    func trustedSources(
        actorDeviceID: String?,
        limit: Int,
        timestamp: Date
    ) throws -> [RuntimeTrustedSourceGrant] {
        []
    }

    func revokeTrustedSource(
        grantID: String,
        actorDeviceID: String?,
        timestamp: Date
    ) throws {
        throw RuntimeTrustedSourceGovernanceError.trustedSourceNotFound
    }
}

let runtimeDocumentSourceAuditLimitCeiling = 1_000
let runtimeDocumentSourceActorCharacterLimit = 256
let runtimeDocumentApprovedSourceLimitCeiling = 800

func runtimeDocumentHostApproval(
    document: RuntimeDocumentIndexDocument,
    chunks: [RuntimeDocumentIndexChunk],
    timestamp: Date
) -> RuntimeDocumentSourceApproval {
    let revision = runtimeDocumentSourceRevision(document: document, chunks: chunks)
    return RuntimeDocumentSourceApproval(
        approvalID: "approval_\(runtimeDocumentStrongDigest([document.id, revision]).prefix(24))",
        documentID: document.id,
        sourceRevision: revision,
        scope: .runtimeShared,
        approvedBy: "runtime_host",
        approvedAt: timestamp
    )
}

func runtimeDocumentSourceRevision(
    document: RuntimeDocumentIndexDocument,
    chunks: [RuntimeDocumentIndexChunk]
) -> String {
    runtimeDocumentStrongDigest(
        [
            "runtime-document-source-revision-v1",
            document.id,
            document.contentFingerprint,
            document.displayName,
            document.mimeType,
            String(document.extractedCharacterCount),
            String(document.chunkCount),
            document.quality.rawValue
        ] + chunks.sorted(by: { $0.chunkIndex < $1.chunkIndex }).flatMap { chunk in
            [
                chunk.id,
                String(chunk.chunkIndex),
                String(chunk.startCharacterOffset),
                String(chunk.endCharacterOffset),
                chunk.text
            ]
        }
    )
}

func runtimeDocumentAuditEvent(
    action: RuntimeDocumentSourceAuditAction,
    approval: RuntimeDocumentSourceApproval? = nil,
    actorDeviceID: String?,
    documentID: String? = nil,
    sourceAnchorID: String? = nil,
    resultCount: Int? = nil,
    timestamp: Date
) -> RuntimeDocumentSourceAuditEvent {
    let actor = runtimeDocumentCanonicalAuditActor(actorDeviceID)
    let canonicalDocumentID = documentID.flatMap(runtimeDocumentIndexCanonicalDocumentID)
    let canonicalAnchorID = sourceAnchorID.flatMap(runtimeDocumentIndexCanonicalSourceAnchorID)
    let count = resultCount.map { max(0, $0) }
    return RuntimeDocumentSourceAuditEvent(
        eventID: UUID().uuidString.lowercased(),
        action: action,
        documentID: approval?.documentID ?? canonicalDocumentID,
        sourceRevision: approval?.sourceRevision,
        actorDeviceID: actor,
        sourceAnchorID: canonicalAnchorID,
        resultCount: count,
        occurredAt: timestamp
    )
}

func runtimeDocumentCanonicalAuditActor(_ actorDeviceID: String?) -> String? {
    guard let value = actorDeviceID?.trimmingCharacters(in: .whitespacesAndNewlines),
          !value.isEmpty,
          value.count <= runtimeDocumentSourceActorCharacterLimit,
          !value.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else {
        return nil
    }
    return value
}

private func runtimeDocumentStrongDigest(_ fields: [String]) -> String {
    var hasher = SHA256()
    for field in fields {
        let data = Data(field.utf8)
        var length = UInt64(data.count).bigEndian
        withUnsafeBytes(of: &length) { hasher.update(data: Data($0)) }
        hasher.update(data: data)
    }
    return hasher.finalize().map { String(format: "%02x", $0) }.joined()
}
