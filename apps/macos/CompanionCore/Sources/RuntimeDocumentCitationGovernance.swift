import CryptoKit
import Foundation
import Security

public enum RuntimeTrustedSourceUsageScope: String, Codable, Sendable {
    case chatContext = "chat_context"
}

public struct RuntimeDocumentCitation: Equatable, Sendable {
    public var schemaVersion: Int
    public var citationID: String
    public var sourceAnchorID: String
    public var document: RuntimeDocumentIndexDocument
    public var chunkSummary: RuntimeDocumentIndexChunkSummary
}

public struct RuntimeTrustedSourceReview: Equatable, Sendable {
    public var reviewID: String
    public var confirmationToken: String
    public var disclosureVersion: String
    public var usageScope: RuntimeTrustedSourceUsageScope
    public var expiresAt: Date
}

public struct RuntimeTrustedSourceGrant: Equatable, Sendable {
    public var grantID: String
    public var citationID: String
    public var sourceAnchorID: String
    public var document: RuntimeDocumentIndexDocument
    public var usageScope: RuntimeTrustedSourceUsageScope
    public var approvedAt: Date
}

public struct RuntimeTrustedSourceChatContext: Equatable, Sendable {
    public var grantID: String
    public var citationID: String
    public var sourceAnchorID: String
    public var sourceRevision: String
    public var document: RuntimeDocumentIndexDocument
    public var chunkSummary: RuntimeDocumentIndexChunkSummary
    public var text: String
}

public struct RuntimeTrustedSourceReviewEnvelope: Equatable, Sendable {
    public var citation: RuntimeDocumentCitation
    public var review: RuntimeTrustedSourceReview
    public var trustedSource: RuntimeTrustedSourceGrant?
}

public enum RuntimeTrustedSourceGovernanceError: Error, Equatable, Sendable {
    case citationNotFound
    case reviewNotFound
    case reviewExpired
    case reviewStale
    case trustedSourceNotFound
}

struct RuntimeStoredDocumentCitation: Equatable, Sendable {
    var citation: RuntimeDocumentCitation
    var documentID: String
    var sourceRevision: String
    var issuedAt: Date
    var staleAt: Date?
}

struct RuntimeStoredTrustedSourceReview: Equatable, Sendable {
    var review: RuntimeTrustedSourceReview
    var citationID: String
    var actorDeviceID: String
}

struct RuntimeStoredTrustedSourceGrant: Equatable, Sendable {
    var grant: RuntimeTrustedSourceGrant
    var documentID: String
    var sourceRevision: String
    var actorDeviceID: String
    var revokedAt: Date?
}

let runtimeDocumentCitationSchemaVersion = 1
let runtimeDocumentCitationPrefix = "citation_"
let runtimeDocumentCitationDigestCharacterCount = 32
let runtimeTrustedSourceReviewPrefix = "source_review_"
let runtimeTrustedSourceReviewDigestCharacterCount = 32
let runtimeTrustedSourceConfirmationPrefix = "source_confirmation_"
let runtimeTrustedSourceConfirmationDigestCharacterCount = 64
let runtimeTrustedSourceGrantPrefix = "trusted_source_"
let runtimeTrustedSourceGrantDigestCharacterCount = 32
let runtimeTrustedSourceDisclosureVersion = "runtime-trusted-source-v1"
let runtimeTrustedSourceReviewLifetime: TimeInterval = 10 * 60
let runtimeTrustedSourceListLimitCeiling = 100
let runtimeTrustedSourceChatContextGrantLimitCeiling = 8
let runtimeTrustedSourceChatContextTextUTF8ByteLimit = 4_096

func runtimeDocumentCitation(
    anchor: RuntimeDocumentSourceAnchor,
    approval: RuntimeDocumentSourceApproval
) -> RuntimeDocumentCitation {
    let digest = runtimeDocumentCitationDigest([
        "runtime-document-citation-v1",
        approval.sourceRevision,
        anchor.sourceAnchorID
    ])
    return RuntimeDocumentCitation(
        schemaVersion: runtimeDocumentCitationSchemaVersion,
        citationID: runtimeDocumentCitationPrefix + String(digest.prefix(runtimeDocumentCitationDigestCharacterCount)),
        sourceAnchorID: anchor.sourceAnchorID,
        document: anchor.document,
        chunkSummary: anchor.chunkSummary
    )
}

func runtimeTrustedSourceReview(
    citationID: String,
    actorDeviceID: String,
    timestamp: Date
) -> RuntimeTrustedSourceReview {
    RuntimeTrustedSourceReview(
        reviewID: runtimeTrustedSourceReviewPrefix + String(
            runtimeDocumentCitationDigest([
                "runtime-trusted-source-review-v1",
                citationID,
                actorDeviceID,
                UUID().uuidString
            ]).prefix(runtimeTrustedSourceReviewDigestCharacterCount)
        ),
        confirmationToken: runtimeTrustedSourceConfirmationPrefix
            + runtimeDocumentRandomHex(characterCount: runtimeTrustedSourceConfirmationDigestCharacterCount),
        disclosureVersion: runtimeTrustedSourceDisclosureVersion,
        usageScope: .chatContext,
        expiresAt: timestamp.addingTimeInterval(runtimeTrustedSourceReviewLifetime)
    )
}

func runtimeTrustedSourceGrant(
    citation: RuntimeDocumentCitation,
    approval: RuntimeDocumentSourceApproval,
    actorDeviceID: String,
    timestamp: Date
) -> RuntimeTrustedSourceGrant {
    let digest = runtimeDocumentCitationDigest([
        "runtime-trusted-source-grant-v1",
        actorDeviceID,
        approval.documentID,
        approval.sourceRevision,
        RuntimeTrustedSourceUsageScope.chatContext.rawValue
    ])
    return RuntimeTrustedSourceGrant(
        grantID: runtimeTrustedSourceGrantPrefix + String(digest.prefix(runtimeTrustedSourceGrantDigestCharacterCount)),
        citationID: citation.citationID,
        sourceAnchorID: citation.sourceAnchorID,
        document: citation.document,
        usageScope: .chatContext,
        approvedAt: timestamp
    )
}

func runtimeDocumentCanonicalCitationID(_ value: String?) -> String? {
    runtimeDocumentCanonicalOpaqueID(
        value,
        prefix: runtimeDocumentCitationPrefix,
        digestCharacterCount: runtimeDocumentCitationDigestCharacterCount
    )
}

func runtimeDocumentCanonicalTrustedSourceReviewID(_ value: String?) -> String? {
    runtimeDocumentCanonicalOpaqueID(
        value,
        prefix: runtimeTrustedSourceReviewPrefix,
        digestCharacterCount: runtimeTrustedSourceReviewDigestCharacterCount
    )
}

func runtimeDocumentCanonicalTrustedSourceConfirmationToken(_ value: String?) -> String? {
    runtimeDocumentCanonicalOpaqueID(
        value,
        prefix: runtimeTrustedSourceConfirmationPrefix,
        digestCharacterCount: runtimeTrustedSourceConfirmationDigestCharacterCount
    )
}

func runtimeDocumentCanonicalTrustedSourceGrantID(_ value: String?) -> String? {
    runtimeDocumentCanonicalOpaqueID(
        value,
        prefix: runtimeTrustedSourceGrantPrefix,
        digestCharacterCount: runtimeTrustedSourceGrantDigestCharacterCount
    )
}

private func runtimeDocumentCanonicalOpaqueID(
    _ value: String?,
    prefix: String,
    digestCharacterCount: Int
) -> String? {
    guard let value, value.hasPrefix(prefix) else { return nil }
    let digest = value.dropFirst(prefix.count)
    guard digest.count == digestCharacterCount,
          digest.utf8.allSatisfy({ byte in
              (byte >= 48 && byte <= 57) || (byte >= 97 && byte <= 102)
          }) else { return nil }
    return value
}

private func runtimeDocumentCitationDigest(_ fields: [String]) -> String {
    var hasher = SHA256()
    for field in fields {
        let data = Data(field.utf8)
        var length = UInt64(data.count).bigEndian
        withUnsafeBytes(of: &length) { hasher.update(data: Data($0)) }
        hasher.update(data: data)
    }
    return hasher.finalize().map { String(format: "%02x", $0) }.joined()
}

private func runtimeDocumentRandomHex(characterCount: Int) -> String {
    precondition(characterCount > 0, "Random hex output must be non-empty")
    var bytes = [UInt8](repeating: 0, count: (characterCount + 1) / 2)
    let status = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
    precondition(status == errSecSuccess, "Unable to generate trusted-source confirmation material")
    return String(bytes.map { String(format: "%02x", $0) }.joined().prefix(characterCount))
}

func runtimeTrustedSourceChatContextText(_ text: String) -> String? {
    let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !normalized.isEmpty else { return nil }
    var result = ""
    var byteCount = 0
    for character in normalized {
        let fragment = String(character)
        let fragmentByteCount = fragment.utf8.count
        guard byteCount + fragmentByteCount <= runtimeTrustedSourceChatContextTextUTF8ByteLimit else {
            break
        }
        result += fragment
        byteCount += fragmentByteCount
    }
    return result.isEmpty ? nil : result
}
