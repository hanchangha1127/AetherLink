import CryptoKit
import Foundation

public enum RuntimePermissionEffect: String, CaseIterable, Sendable {
    case providerArtifactInstall = "provider_artifact_install"
}

public enum RuntimePermissionDecision: String, CaseIterable, Sendable {
    case hostExplicitApproval = "host_explicit_approval"
}

public enum RuntimePermissionAuditRequirement: String, CaseIterable, Sendable {
    case durableRedactedRequired = "durable_redacted_required"
}

public struct RuntimePermissionPolicyManifest: Equatable, Sendable {
    public let actionID: String
    public let revision: String
    public let effect: String
    public let decision: String
    public let audit: String

    public init(
        actionID: String,
        revision: String,
        effect: String,
        decision: String,
        audit: String
    ) {
        self.actionID = actionID
        self.revision = revision
        self.effect = effect
        self.decision = decision
        self.audit = audit
    }
}

public struct RuntimePermissionPolicyDefinition: Equatable, Sendable {
    public let actionID: String
    public let revision: String
    public let effect: RuntimePermissionEffect
    public let decision: RuntimePermissionDecision
    public let audit: RuntimePermissionAuditRequirement
}

public struct RuntimePermissionAuthorityBinding: Equatable, Sendable {
    public let connectionID: UUID
    public let requestID: String
    public let authenticationGeneration: UInt64
    public let deviceID: String
    public let publicKeyBase64: String
    public let transportBinding: String?

    public init(
        connectionID: UUID,
        requestID: String,
        authenticationGeneration: UInt64,
        deviceID: String,
        publicKeyBase64: String,
        transportBinding: String?
    ) {
        self.connectionID = connectionID
        self.requestID = requestID
        self.authenticationGeneration = authenticationGeneration
        self.deviceID = deviceID
        self.publicKeyBase64 = publicKeyBase64
        self.transportBinding = transportBinding
    }
}

public struct RuntimePermissionPolicyClaim: Equatable, Sendable {
    public let definition: RuntimePermissionPolicyDefinition
    public let requestBindingDigest: String
    public let authorityKeyFingerprint: String
    fileprivate let authority: RuntimePermissionAuthorityBinding
    fileprivate let resourceKind: String
    fileprivate let resourceValue: String

    fileprivate init(
        definition: RuntimePermissionPolicyDefinition,
        requestBindingDigest: String,
        authorityKeyFingerprint: String,
        authority: RuntimePermissionAuthorityBinding,
        resourceKind: String,
        resourceValue: String
    ) {
        self.definition = definition
        self.requestBindingDigest = requestBindingDigest
        self.authorityKeyFingerprint = authorityKeyFingerprint
        self.authority = authority
        self.resourceKind = resourceKind
        self.resourceValue = resourceValue
    }
}

public enum RuntimePermissionPolicyRegistryError: Error, Equatable, Sendable {
    case emptyRegistry
    case tooManyDefinitions
    case invalidActionID
    case invalidRevision
    case unsupportedEffect
    case unsupportedDecision
    case unsupportedAuditRequirement
    case revisionMismatch
    case duplicateActionID
    case duplicateRevision
    case unknownAction
    case unexpectedRevision
    case invalidAuthorityBinding
    case invalidResource
}

public struct RuntimePermissionPolicyRegistry: Sendable {
    public static let maximumDefinitionCount = 32
    public static let maximumActionIDUTF8Bytes = 64
    public static let maximumRequestIDUTF8Bytes = 256
    public static let maximumDeviceIDUTF8Bytes = 256
    public static let maximumPublicKeyUTF8Bytes = 1_024
    public static let maximumTransportBindingUTF8Bytes = 256
    public static let maximumResourceUTF8Bytes = 256
    public static let modelPullActionID = "models_pull_ollama_v1"
    public static let modelPullResourceKind = "ollama_model"
    public static let modelPullRevision =
        "5969f34082e579a4e393bded6ce62706382e7376258b364c3afed0dbbcb163d3"

    // The legacy prefix stays stable so existing model-pull audit rows remain readable.
    public static let requestBindingDigestPrefix =
        "aetherlink.model-pull.request-binding.v1:"

    public static let bundled: RuntimePermissionPolicyRegistry = {
        do {
            return try RuntimePermissionPolicyRegistry(manifests: [
                RuntimePermissionPolicyManifest(
                    actionID: modelPullActionID,
                    revision: modelPullRevision,
                    effect: RuntimePermissionEffect.providerArtifactInstall.rawValue,
                    decision: RuntimePermissionDecision.hostExplicitApproval.rawValue,
                    audit: RuntimePermissionAuditRequirement.durableRedactedRequired.rawValue
                )
            ])
        } catch {
            preconditionFailure("Bundled runtime permission policy registry is invalid.")
        }
    }()

    public let definitions: [RuntimePermissionPolicyDefinition]
    private let definitionsByActionID: [String: RuntimePermissionPolicyDefinition]

    public init(manifests: [RuntimePermissionPolicyManifest]) throws {
        guard !manifests.isEmpty else {
            throw RuntimePermissionPolicyRegistryError.emptyRegistry
        }
        guard manifests.count <= Self.maximumDefinitionCount else {
            throw RuntimePermissionPolicyRegistryError.tooManyDefinitions
        }

        var actionIDs = Set<String>()
        var revisions = Set<String>()
        var validatedDefinitions: [RuntimePermissionPolicyDefinition] = []
        validatedDefinitions.reserveCapacity(manifests.count)

        for manifest in manifests {
            guard Self.isCanonicalActionID(manifest.actionID) else {
                throw RuntimePermissionPolicyRegistryError.invalidActionID
            }
            guard Self.isCanonicalRevision(manifest.revision) else {
                throw RuntimePermissionPolicyRegistryError.invalidRevision
            }
            guard let effect = RuntimePermissionEffect(rawValue: manifest.effect) else {
                throw RuntimePermissionPolicyRegistryError.unsupportedEffect
            }
            guard let decision = RuntimePermissionDecision(rawValue: manifest.decision) else {
                throw RuntimePermissionPolicyRegistryError.unsupportedDecision
            }
            guard let audit = RuntimePermissionAuditRequirement(rawValue: manifest.audit) else {
                throw RuntimePermissionPolicyRegistryError.unsupportedAuditRequirement
            }
            guard actionIDs.insert(manifest.actionID).inserted else {
                throw RuntimePermissionPolicyRegistryError.duplicateActionID
            }
            guard revisions.insert(manifest.revision).inserted else {
                throw RuntimePermissionPolicyRegistryError.duplicateRevision
            }
            guard Self.computedRevision(
                actionID: manifest.actionID,
                effect: effect,
                decision: decision,
                audit: audit
            ) == manifest.revision else {
                throw RuntimePermissionPolicyRegistryError.revisionMismatch
            }
            validatedDefinitions.append(RuntimePermissionPolicyDefinition(
                actionID: manifest.actionID,
                revision: manifest.revision,
                effect: effect,
                decision: decision,
                audit: audit
            ))
        }

        definitions = validatedDefinitions.sorted { $0.actionID < $1.actionID }
        definitionsByActionID = Dictionary(
            uniqueKeysWithValues: definitions.map { ($0.actionID, $0) }
        )
    }

    public func definition(
        actionID: String,
        expectedRevision: String
    ) throws -> RuntimePermissionPolicyDefinition {
        guard let definition = definitionsByActionID[actionID] else {
            throw RuntimePermissionPolicyRegistryError.unknownAction
        }
        guard definition.revision == expectedRevision else {
            throw RuntimePermissionPolicyRegistryError.unexpectedRevision
        }
        return definition
    }

    public func claim(
        actionID: String,
        expectedRevision: String,
        authority: RuntimePermissionAuthorityBinding,
        resourceKind: String,
        resourceValue: String
    ) throws -> RuntimePermissionPolicyClaim {
        let definition = try definition(
            actionID: actionID,
            expectedRevision: expectedRevision
        )
        guard Self.isCanonicalAuthority(authority) else {
            throw RuntimePermissionPolicyRegistryError.invalidAuthorityBinding
        }
        guard Self.isCanonicalActionID(resourceKind),
              Self.isCanonicalBoundedString(
                resourceValue,
                maximumUTF8Bytes: Self.maximumResourceUTF8Bytes
              ) else {
            throw RuntimePermissionPolicyRegistryError.invalidResource
        }

        return RuntimePermissionPolicyClaim(
            definition: definition,
            requestBindingDigest: Self.requestBindingDigest(
                definition: definition,
                authority: authority,
                resourceKind: resourceKind,
                resourceValue: resourceValue
            ),
            authorityKeyFingerprint: Self.keyFingerprint(authority.publicKeyBase64),
            authority: authority,
            resourceKind: resourceKind,
            resourceValue: resourceValue
        )
    }

    private static func requestBindingDigest(
        definition: RuntimePermissionPolicyDefinition,
        authority: RuntimePermissionAuthorityBinding,
        resourceKind: String,
        resourceValue: String
    ) -> String {
        let fields = [
            "runtime-permission-request-binding-v1",
            definition.actionID,
            definition.revision,
            definition.effect.rawValue,
            definition.decision.rawValue,
            definition.audit.rawValue,
            authority.connectionID.uuidString.lowercased(),
            authority.requestID,
            String(authority.authenticationGeneration),
            authority.deviceID,
            authority.publicKeyBase64,
            authority.transportBinding == nil ? "transport_absent" : "transport_present",
            authority.transportBinding ?? "",
            resourceKind,
            resourceValue,
        ]
        var material = Data()
        for field in fields {
            var length = UInt64(field.utf8.count).bigEndian
            withUnsafeBytes(of: &length) { material.append(contentsOf: $0) }
            material.append(contentsOf: field.utf8)
        }
        let digest = SHA256.hash(data: material)
            .map { String(format: "%02x", $0) }
            .joined()
        return Self.requestBindingDigestPrefix + digest
    }

    public func validates(_ claim: RuntimePermissionPolicyClaim) -> Bool {
        guard (try? definition(
            actionID: claim.definition.actionID,
            expectedRevision: claim.definition.revision
        )) == claim.definition else {
            return false
        }
        guard Self.isCanonicalAuthority(claim.authority),
              Self.isCanonicalActionID(claim.resourceKind),
              Self.isCanonicalBoundedString(
                claim.resourceValue,
                maximumUTF8Bytes: Self.maximumResourceUTF8Bytes
              ) else {
            return false
        }
        return claim.requestBindingDigest == Self.requestBindingDigest(
            definition: claim.definition,
            authority: claim.authority,
            resourceKind: claim.resourceKind,
            resourceValue: claim.resourceValue
        ) && claim.authorityKeyFingerprint == Self.keyFingerprint(
            claim.authority.publicKeyBase64
        )
    }

    public func validates(
        _ claim: RuntimePermissionPolicyClaim,
        authority: RuntimePermissionAuthorityBinding,
        resourceKind: String,
        resourceValue: String
    ) -> Bool {
        validates(claim) &&
            claim.authority == authority &&
            claim.resourceKind == resourceKind &&
            claim.resourceValue == resourceValue
    }

    public func validatesModelPullClaim(_ claim: RuntimePermissionPolicyClaim) -> Bool {
        guard validates(claim),
              claim.definition.actionID == Self.modelPullActionID,
              claim.definition.revision == Self.modelPullRevision,
              claim.definition.effect == .providerArtifactInstall,
              claim.definition.decision == .hostExplicitApproval,
              claim.definition.audit == .durableRedactedRequired,
              claim.resourceKind == Self.modelPullResourceKind else {
            return false
        }
        return true
    }

    public func validatesModelPullClaim(
        _ claim: RuntimePermissionPolicyClaim,
        connectionID: UUID,
        model: String
    ) -> Bool {
        validatesModelPullClaim(claim) &&
            claim.authority.connectionID == connectionID &&
            claim.resourceValue == model
    }

    public func validatesModelPullClaim(
        _ claim: RuntimePermissionPolicyClaim,
        authority: RuntimePermissionAuthorityBinding,
        model: String
    ) -> Bool {
        validatesModelPullClaim(claim) && validates(
            claim,
            authority: authority,
            resourceKind: Self.modelPullResourceKind,
            resourceValue: model
        )
    }

    public static func computedRevision(
        actionID: String,
        effect: RuntimePermissionEffect,
        decision: RuntimePermissionDecision,
        audit: RuntimePermissionAuditRequirement
    ) -> String {
        let canonical = [
            "runtime-permission-policy-v1",
            actionID,
            effect.rawValue,
            decision.rawValue,
            audit.rawValue,
        ].joined(separator: "\0")
        return SHA256.hash(data: Data(canonical.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
    }

    public static func isCanonicalRequestBindingDigest(_ digest: String) -> Bool {
        guard digest.utf8.count == requestBindingDigestPrefix.utf8.count + 64,
              digest.hasPrefix(requestBindingDigestPrefix) else {
            return false
        }
        return digest.dropFirst(requestBindingDigestPrefix.count).unicodeScalars.allSatisfy {
            (48...57).contains($0.value) || (97...102).contains($0.value)
        }
    }

    private static func isCanonicalAuthority(
        _ authority: RuntimePermissionAuthorityBinding
    ) -> Bool {
        authority.authenticationGeneration <= UInt64(Int64.max) &&
            isCanonicalBoundedString(
                authority.requestID,
                maximumUTF8Bytes: maximumRequestIDUTF8Bytes
            ) &&
            isCanonicalBoundedString(
                authority.deviceID,
                maximumUTF8Bytes: maximumDeviceIDUTF8Bytes
            ) &&
            isCanonicalBoundedString(
                authority.publicKeyBase64,
                maximumUTF8Bytes: maximumPublicKeyUTF8Bytes
            ) &&
            (authority.transportBinding == nil || isCanonicalBoundedString(
                authority.transportBinding ?? "",
                maximumUTF8Bytes: maximumTransportBindingUTF8Bytes
            ))
    }

    private static func keyFingerprint(_ publicKeyBase64: String) -> String {
        let keyData = Data(base64Encoded: publicKeyBase64) ?? Data(publicKeyBase64.utf8)
        return SHA256.hash(data: keyData).prefix(6)
            .map { String(format: "%02X", $0) }
            .joined(separator: ":")
    }

    private static func isCanonicalActionID(_ value: String) -> Bool {
        guard value.utf8.elementsEqual(value.precomposedStringWithCanonicalMapping.utf8),
              value.utf8.count <= maximumActionIDUTF8Bytes,
              let first = value.unicodeScalars.first,
              (97...122).contains(first.value) else {
            return false
        }
        return value.unicodeScalars.allSatisfy { scalar in
            switch scalar.value {
            case 48...57, 97...122, 95:
                return true
            default:
                return false
            }
        }
    }

    private static func isCanonicalRevision(_ value: String) -> Bool {
        value.utf8.count == 64 && value.unicodeScalars.allSatisfy { scalar in
            (48...57).contains(scalar.value) || (97...102).contains(scalar.value)
        }
    }

    private static func isCanonicalBoundedString(
        _ value: String,
        maximumUTF8Bytes: Int
    ) -> Bool {
        guard !value.isEmpty,
              value.utf8.count <= maximumUTF8Bytes,
              value.utf8.elementsEqual(value.precomposedStringWithCanonicalMapping.utf8),
              value == value.trimmingCharacters(in: .whitespacesAndNewlines) else {
            return false
        }
        return value.unicodeScalars.allSatisfy {
            !CharacterSet.controlCharacters.contains($0)
        }
    }
}
