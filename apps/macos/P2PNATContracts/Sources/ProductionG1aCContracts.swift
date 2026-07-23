import CryptoKit
import Foundation

// G1a-C extends the ALS1 namespace without changing the historical object 1...9 codecs.
public enum ProductionC1Contract {
    public static let serviceKeysetObjectType: UInt8 = 10
    public static let pairStatusObjectType: UInt8 = 11
    public static let freshPairProofObjectType: UInt8 = 12
    public static let routeCapabilityObjectType: UInt8 = 13
    public static let routePlanObjectType: UInt8 = 14
    public static let p2pConnectorObjectType: UInt8 = 15
    public static let turnConnectorObjectType: UInt8 = 16
    public static let sealedRelayConnectorObjectType: UInt8 = 17
    public static let preauthorizationSessionContextObjectType: UInt8 = 18
    public static let p2pRouteAuthorizationObjectType: UInt8 = 20
    public static let turnRouteAuthorizationObjectType: UInt8 = 21
    public static let sealedRelayRouteAuthorizationObjectType: UInt8 = 22

    public static let suite = "aetherlink-production-authority-route-v1"
    public static let signatureAlgorithm = "p256_ecdsa_sha256_der_low_s_v1"
    public static let maximumKeysetBytes = 4_096
    public static let maximumPairStatusBytes = 4_096
    public static let maximumFreshPairProofBytes = 4_096
    public static let maximumRouteCapabilityBytes = 2_048
    public static let maximumRoutePlanBytes = 2_048
    public static let maximumConnectorBytes = 1_024
    public static let maximumRouteAuthorizationBytes = 1_024
    public static let maximumPreauthorizationSessionContextBytes = 2_048
    public static let maximumDelegatedKeys = 8
    public static let maximumTransitionHistoryEntries = 20
    public static let maximumClockSkewMs: UInt64 = 30_000
    public static let maximumKeysetLifetimeMs: UInt64 = 31 * 24 * 60 * 60 * 1_000
    public static let maximumStatusLifetimeMs: UInt64 = 5 * 60 * 1_000
    public static let maximumFreshPairLifetimeMs: UInt64 = 5 * 60 * 1_000
    public static let maximumRouteLifetimeMs: UInt64 = 10 * 60 * 1_000
}

public enum ProductionC1Error: Error, Equatable, Sendable {
    case malformedCanonical
    case invalidValue
    case limitExceeded
    case invalidPublicKey
    case invalidSignature
    case nonCanonicalSignature
    case highS
    case untrustedRoot
    case serviceMismatch
    case keysetRollback
    case keysetGap
    case previousKeysetMismatch
    case keyUnavailable
    case keyPurposeMismatch
    case keyRevoked
    case issuedInFuture
    case notYetValid
    case expired
    case stateMismatch
    case historyMismatch
    case evidenceMismatch
    case invalidFreshPair
    case routeMismatch
}

public struct ProductionC1DelegatedKeyPurpose: OptionSet, Equatable, Sendable {
    public let rawValue: UInt32

    public init(rawValue: UInt32) { self.rawValue = rawValue }

    public static let pairStatus = Self(rawValue: 1 << 0)
    public static let routeCapability = Self(rawValue: 1 << 1)
    public static let candidatePublish = Self(rawValue: 1 << 2)
    public static let candidateFetch = Self(rawValue: 1 << 3)
    public static let candidatePublishReceipt = Self(rawValue: 1 << 4)
    public static let candidateFetchReceipt = Self(rawValue: 1 << 5)
    public static let allowed: Self = [
        .pairStatus, .routeCapability, .candidatePublish, .candidateFetch,
        .candidatePublishReceipt, .candidateFetchReceipt,
    ]
}

public struct ProductionC1DelegatedKey: Equatable, Sendable {
    public let keysetVersion: UInt64
    public let keyId: String
    public let purposes: ProductionC1DelegatedKeyPurpose
    public let notBeforeMs: UInt64
    public let expiresAtMs: UInt64
    public let revokedAtMs: UInt64?
    public let publicKeyX963: Data

    public init(
        keysetVersion: UInt64,
        keyId: String,
        purposes: ProductionC1DelegatedKeyPurpose,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        revokedAtMs: UInt64? = nil,
        publicKeyX963: Data
    ) throws {
        try c1ValidateDigest(keyId)
        guard keysetVersion > 0,
              !purposes.isEmpty,
              purposes.subtracting(.allowed).isEmpty,
              notBeforeMs < expiresAtMs,
              revokedAtMs.map({ notBeforeMs <= $0 && $0 <= expiresAtMs }) ?? true else {
            throw ProductionC1Error.invalidValue
        }
        _ = try c1PublicKey(x963: publicKeyX963)
        guard keyId == c1KeyId(try c1PublicKey(x963: publicKeyX963)) else {
            throw ProductionC1Error.invalidValue
        }
        self.keysetVersion = keysetVersion
        self.keyId = keyId
        self.purposes = purposes
        self.notBeforeMs = notBeforeMs
        self.expiresAtMs = expiresAtMs
        self.revokedAtMs = revokedAtMs
        self.publicKeyX963 = publicKeyX963
    }
}

public struct ProductionC1ServiceKeyset: Equatable, Sendable {
    public let serviceIdDigest: String
    public let keysetVersion: UInt64
    public let previousKeysetDigest: String?
    public let issuedAtMs: UInt64
    public let expiresAtMs: UInt64
    public let rootKeyId: String
    public let delegatedKeys: [ProductionC1DelegatedKey]
    public let rootSignature: Data

    private init(
        serviceIdDigest: String,
        keysetVersion: UInt64,
        previousKeysetDigest: String?,
        issuedAtMs: UInt64,
        expiresAtMs: UInt64,
        rootKeyId: String,
        delegatedKeys: [ProductionC1DelegatedKey],
        rootSignature: Data,
        validateSignatureEncoding: Bool
    ) throws {
        try c1ValidateDigest(serviceIdDigest)
        if let previousKeysetDigest { try c1ValidateDigest(previousKeysetDigest) }
        try c1ValidateDigest(rootKeyId)
        guard keysetVersion > 0,
              issuedAtMs < expiresAtMs,
              delegatedKeys.count > 0,
              delegatedKeys.count <= ProductionC1Contract.maximumDelegatedKeys,
              Set(delegatedKeys.map(\.keyId)).count == delegatedKeys.count,
              delegatedKeys.contains(where: { $0.keysetVersion == keysetVersion }),
              delegatedKeys.allSatisfy({
                  $0.keysetVersion == keysetVersion ||
                      (keysetVersion > 1 && $0.keysetVersion == keysetVersion - 1)
              }),
              delegatedKeys.allSatisfy({
                  $0.notBeforeMs >= issuedAtMs && $0.expiresAtMs <= expiresAtMs
              }),
              delegatedKeys.map(\.keyId) == delegatedKeys.map(\.keyId).sorted() else {
            throw ProductionC1Error.invalidValue
        }
        if validateSignatureEncoding { try c1ValidateCanonicalLowS(rootSignature) }
        self.serviceIdDigest = serviceIdDigest
        self.keysetVersion = keysetVersion
        self.previousKeysetDigest = previousKeysetDigest
        self.issuedAtMs = issuedAtMs
        self.expiresAtMs = expiresAtMs
        self.rootKeyId = rootKeyId
        self.delegatedKeys = delegatedKeys
        self.rootSignature = rootSignature
        guard try canonicalBytes().count <= ProductionC1Contract.maximumKeysetBytes else {
            throw ProductionC1Error.limitExceeded
        }
    }

    public static func signed(
        serviceIdDigest: String,
        keysetVersion: UInt64,
        previousKeysetDigest: String?,
        issuedAtMs: UInt64,
        expiresAtMs: UInt64,
        delegatedKeys: [ProductionC1DelegatedKey],
        using rootPrivateKey: P256.Signing.PrivateKey
    ) throws -> Self {
        let rootKeyId = c1KeyId(rootPrivateKey.publicKey)
        let unsigned = try Self(
            serviceIdDigest: serviceIdDigest,
            keysetVersion: keysetVersion,
            previousKeysetDigest: previousKeysetDigest,
            issuedAtMs: issuedAtMs,
            expiresAtMs: expiresAtMs,
            rootKeyId: rootKeyId,
            delegatedKeys: delegatedKeys,
            rootSignature: Data(),
            validateSignatureEncoding: false
        )
        return try Self(
            serviceIdDigest: serviceIdDigest,
            keysetVersion: keysetVersion,
            previousKeysetDigest: previousKeysetDigest,
            issuedAtMs: issuedAtMs,
            expiresAtMs: expiresAtMs,
            rootKeyId: rootKeyId,
            delegatedKeys: delegatedKeys,
            rootSignature: c1Sign(
                unsigned.signingTranscript,
                using: rootPrivateKey
            ),
            validateSignatureEncoding: true
        )
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try C1TLV.decode(
            data,
            objectType: ProductionC1Contract.serviceKeysetObjectType,
            fieldCount: 11,
            maximumBytes: ProductionC1Contract.maximumKeysetBytes
        )
        guard try c1Text(fields[0]) == ProductionC1Contract.suite,
              try c1Text(fields[9]) == ProductionC1Contract.signatureAlgorithm else {
            throw ProductionC1Error.invalidValue
        }
        let version = try c1UInt64(fields[2])
        let count = try c1UInt32(fields[7])
        guard count > 0, count <= ProductionC1Contract.maximumDelegatedKeys else {
            throw ProductionC1Error.limitExceeded
        }
        let entries = try Self.decodeEntries(fields[8], count: Int(count))
        try self.init(
            serviceIdDigest: c1Text(fields[1]),
            keysetVersion: version,
            previousKeysetDigest: c1OptionalDigest(fields[3]),
            issuedAtMs: c1UInt64(fields[4]),
            expiresAtMs: c1UInt64(fields[5]),
            rootKeyId: c1Text(fields[6]),
            delegatedKeys: entries,
            rootSignature: fields[10],
            validateSignatureEncoding: true
        )
        guard try canonicalBytes() == data else { throw ProductionC1Error.malformedCanonical }
    }

    public func canonicalBytes() throws -> Data {
        C1TLV.encode(
            objectType: ProductionC1Contract.serviceKeysetObjectType,
            fields: claimsFields + [rootSignature]
        )
    }

    public func digestHex() throws -> String { c1DigestHex(try canonicalBytes()) }

    fileprivate var signingTranscript: Data {
        c1SignatureTranscript(
            domain: "AetherLink G1a-C service-keyset root signature v1",
            claims: C1TLV.encode(
                objectType: ProductionC1Contract.serviceKeysetObjectType,
                fields: claimsFields
            )
        )
    }

    private var claimsFields: [Data] {
        [
            c1ASCII(ProductionC1Contract.suite),
            c1ASCII(serviceIdDigest),
            c1BE(keysetVersion),
            c1OptionalDigestBytes(previousKeysetDigest),
            c1BE(issuedAtMs),
            c1BE(expiresAtMs),
            c1ASCII(rootKeyId),
            c1BE(UInt32(delegatedKeys.count)),
            Self.encodeEntries(delegatedKeys),
            c1ASCII(ProductionC1Contract.signatureAlgorithm),
        ]
    }

    private static func encodeEntries(_ values: [ProductionC1DelegatedKey]) -> Data {
        values.reduce(into: Data()) { output, value in
            output.append(c1BE(value.keysetVersion))
            output.append(c1ForceDecodeDigest(value.keyId))
            output.append(c1BE(value.purposes.rawValue))
            output.append(c1BE(value.notBeforeMs))
            output.append(c1BE(value.expiresAtMs))
            output.append(c1BE(value.revokedAtMs ?? 0))
            output.append(value.publicKeyX963)
        }
    }

    private static func decodeEntries(_ data: Data, count: Int) throws -> [ProductionC1DelegatedKey] {
        let size = 8 + 32 + 4 + 8 + 8 + 8 + 65
        guard data.count == count * size else { throw ProductionC1Error.malformedCanonical }
        var result: [ProductionC1DelegatedKey] = []
        for index in 0..<count {
            let base = index * size
            let version = try c1UInt64(data.subdata(in: base..<(base + 8)))
            let keyId = c1LowerHex(data.subdata(in: (base + 8)..<(base + 40)))
            let purpose = try c1UInt32(data.subdata(in: (base + 40)..<(base + 44)))
            let notBefore = try c1UInt64(data.subdata(in: (base + 44)..<(base + 52)))
            let expires = try c1UInt64(data.subdata(in: (base + 52)..<(base + 60)))
            let revoked = try c1UInt64(data.subdata(in: (base + 60)..<(base + 68)))
            result.append(try ProductionC1DelegatedKey(
                keysetVersion: version,
                keyId: keyId,
                purposes: ProductionC1DelegatedKeyPurpose(rawValue: purpose),
                notBeforeMs: notBefore,
                expiresAtMs: expires,
                revokedAtMs: revoked == 0 ? nil : revoked,
                publicKeyX963: data.subdata(in: (base + 68)..<(base + size))
            ))
        }
        return result
    }
}

public struct VerifiedProductionC1ServiceKeyset: Equatable, Sendable {
    public let keyset: ProductionC1ServiceKeyset

    fileprivate init(_ keyset: ProductionC1ServiceKeyset) { self.keyset = keyset }
}

public enum ProductionC1RequesterRole: String, Sendable {
    case client
    case runtime
}

public enum ProductionC1TransitionKind: String, Sendable {
    case genesis
    case sameEpoch = "same_epoch"
    case revoke
    case freshPair = "fresh_pair"
}

public enum ProductionC1AuthorizationEvidenceKind: String, Sendable {
    case initialPairing = "initial_pairing"
    case sameEpochTransition = "same_epoch_transition"
    case denyOnlyRevocation = "deny_only_revocation"
    case dualSignedFreshPair = "dual_signed_fresh_pair"
}

public struct ProductionC1PairStatus: Equatable, Sendable {
    public let serviceIdDigest: String
    public let keysetVersion: UInt64
    public let signingKeyId: String
    public let issuedAtMs: UInt64
    public let expiresAtMs: UInt64
    public let requesterRole: ProductionC1RequesterRole
    public let requestNonce: String
    public let transitionKind: ProductionC1TransitionKind
    public let previousAuthorityDigest: String?
    public let evidenceKind: ProductionC1AuthorizationEvidenceKind
    public let authorizationEvidenceDigest: String
    public let authority: ProductionPairAuthorityState
    public let transitionHistory: [ProductionPairTransitionHistoryEntry]
    public let serviceSignature: Data

    private init(
        serviceIdDigest: String,
        keysetVersion: UInt64,
        signingKeyId: String,
        issuedAtMs: UInt64,
        expiresAtMs: UInt64,
        requesterRole: ProductionC1RequesterRole,
        requestNonce: String,
        transitionKind: ProductionC1TransitionKind,
        previousAuthorityDigest: String?,
        evidenceKind: ProductionC1AuthorizationEvidenceKind,
        authorizationEvidenceDigest: String,
        authority: ProductionPairAuthorityState,
        transitionHistory: [ProductionPairTransitionHistoryEntry],
        serviceSignature: Data,
        validateSignatureEncoding: Bool
    ) throws {
        for digest in [serviceIdDigest, signingKeyId, requestNonce, authorizationEvidenceDigest] {
            try c1ValidateDigest(digest)
        }
        if let previousAuthorityDigest { try c1ValidateDigest(previousAuthorityDigest) }
        guard keysetVersion > 0,
              issuedAtMs < expiresAtMs,
              transitionHistory.count <= ProductionC1Contract.maximumTransitionHistoryEntries,
              Set(transitionHistory.map(\.transitionId)).count == transitionHistory.count,
              !transitionHistory.contains(where: { $0.transitionId == authority.transitionId }) else {
            throw ProductionC1Error.invalidValue
        }
        if validateSignatureEncoding { try c1ValidateCanonicalLowS(serviceSignature) }
        self.serviceIdDigest = serviceIdDigest
        self.keysetVersion = keysetVersion
        self.signingKeyId = signingKeyId
        self.issuedAtMs = issuedAtMs
        self.expiresAtMs = expiresAtMs
        self.requesterRole = requesterRole
        self.requestNonce = requestNonce
        self.transitionKind = transitionKind
        self.previousAuthorityDigest = previousAuthorityDigest
        self.evidenceKind = evidenceKind
        self.authorizationEvidenceDigest = authorizationEvidenceDigest
        self.authority = authority
        self.transitionHistory = transitionHistory
        self.serviceSignature = serviceSignature
        guard try canonicalBytes().count <= ProductionC1Contract.maximumPairStatusBytes else {
            throw ProductionC1Error.limitExceeded
        }
    }

    public static func signed(
        serviceIdDigest: String,
        keysetVersion: UInt64,
        issuedAtMs: UInt64,
        expiresAtMs: UInt64,
        requesterRole: ProductionC1RequesterRole,
        requestNonce: String,
        transitionKind: ProductionC1TransitionKind,
        previousAuthorityDigest: String?,
        evidenceKind: ProductionC1AuthorizationEvidenceKind,
        authorizationEvidenceDigest: String,
        authority: ProductionPairAuthorityState,
        transitionHistory: [ProductionPairTransitionHistoryEntry],
        using signingKey: P256.Signing.PrivateKey
    ) throws -> Self {
        let keyId = c1KeyId(signingKey.publicKey)
        let unsigned = try Self(
            serviceIdDigest: serviceIdDigest,
            keysetVersion: keysetVersion,
            signingKeyId: keyId,
            issuedAtMs: issuedAtMs,
            expiresAtMs: expiresAtMs,
            requesterRole: requesterRole,
            requestNonce: requestNonce,
            transitionKind: transitionKind,
            previousAuthorityDigest: previousAuthorityDigest,
            evidenceKind: evidenceKind,
            authorizationEvidenceDigest: authorizationEvidenceDigest,
            authority: authority,
            transitionHistory: transitionHistory,
            serviceSignature: Data(),
            validateSignatureEncoding: false
        )
        return try Self(
            serviceIdDigest: serviceIdDigest,
            keysetVersion: keysetVersion,
            signingKeyId: keyId,
            issuedAtMs: issuedAtMs,
            expiresAtMs: expiresAtMs,
            requesterRole: requesterRole,
            requestNonce: requestNonce,
            transitionKind: transitionKind,
            previousAuthorityDigest: previousAuthorityDigest,
            evidenceKind: evidenceKind,
            authorizationEvidenceDigest: authorizationEvidenceDigest,
            authority: authority,
            transitionHistory: transitionHistory,
            serviceSignature: c1Sign(unsigned.signingTranscript, using: signingKey),
            validateSignatureEncoding: true
        )
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try C1TLV.decode(
            data,
            objectType: ProductionC1Contract.pairStatusObjectType,
            fieldCount: 17,
            maximumBytes: ProductionC1Contract.maximumPairStatusBytes
        )
        guard try c1Text(fields[0]) == ProductionC1Contract.suite,
              let requester = ProductionC1RequesterRole(rawValue: try c1Text(fields[6])),
              let transition = ProductionC1TransitionKind(rawValue: try c1Text(fields[8])),
              let evidence = ProductionC1AuthorizationEvidenceKind(rawValue: try c1Text(fields[10])),
              try c1Text(fields[15]) == ProductionC1Contract.signatureAlgorithm else {
            throw ProductionC1Error.invalidValue
        }
        let count = try c1UInt32(fields[13])
        guard count <= ProductionC1Contract.maximumTransitionHistoryEntries,
              fields[14].count == Int(count) * 64 else {
            throw ProductionC1Error.malformedCanonical
        }
        var history: [ProductionPairTransitionHistoryEntry] = []
        for index in 0..<Int(count) {
            let base = index * 64
            history.append(try ProductionPairTransitionHistoryEntry(
                transitionId: c1LowerHex(fields[14].subdata(in: base..<(base + 32))),
                transitionRequestDigest: c1LowerHex(fields[14].subdata(in: (base + 32)..<(base + 64)))
            ))
        }
        try self.init(
            serviceIdDigest: c1Text(fields[1]),
            keysetVersion: c1UInt64(fields[2]),
            signingKeyId: c1Text(fields[3]),
            issuedAtMs: c1UInt64(fields[4]),
            expiresAtMs: c1UInt64(fields[5]),
            requesterRole: requester,
            requestNonce: c1Text(fields[7]),
            transitionKind: transition,
            previousAuthorityDigest: c1OptionalDigest(fields[9]),
            evidenceKind: evidence,
            authorizationEvidenceDigest: c1Text(fields[11]),
            authority: ProductionPairAuthorityState(canonicalBytes: fields[12]),
            transitionHistory: history,
            serviceSignature: fields[16],
            validateSignatureEncoding: true
        )
        guard try canonicalBytes() == data else { throw ProductionC1Error.malformedCanonical }
    }

    public func canonicalBytes() throws -> Data {
        C1TLV.encode(
            objectType: ProductionC1Contract.pairStatusObjectType,
            fields: claimsFields + [serviceSignature]
        )
    }

    public func digestHex() throws -> String { c1DigestHex(try canonicalBytes()) }

    fileprivate var signingTranscript: Data {
        c1SignatureTranscript(
            domain: "AetherLink G1a-C pair-status service signature v1",
            claims: C1TLV.encode(
                objectType: ProductionC1Contract.pairStatusObjectType,
                fields: claimsFields
            )
        )
    }

    private var claimsFields: [Data] {
        var history = Data()
        for entry in transitionHistory {
            history.append(c1ForceDecodeDigest(entry.transitionId))
            history.append(c1ForceDecodeDigest(entry.transitionRequestDigest))
        }
        return [
            c1ASCII(ProductionC1Contract.suite),
            c1ASCII(serviceIdDigest),
            c1BE(keysetVersion),
            c1ASCII(signingKeyId),
            c1BE(issuedAtMs),
            c1BE(expiresAtMs),
            c1ASCII(requesterRole.rawValue),
            c1ASCII(requestNonce),
            c1ASCII(transitionKind.rawValue),
            c1OptionalDigestBytes(previousAuthorityDigest),
            c1ASCII(evidenceKind.rawValue),
            c1ASCII(authorizationEvidenceDigest),
            (try? authority.canonicalBytes()) ?? Data(),
            c1BE(UInt32(transitionHistory.count)),
            history,
            c1ASCII(ProductionC1Contract.signatureAlgorithm),
        ]
    }
}

public struct VerifiedProductionC1PairStatus: Equatable, Sendable {
    public let status: ProductionC1PairStatus
    fileprivate let verifiedKeyset: VerifiedProductionC1ServiceKeyset

    fileprivate init(
        _ status: ProductionC1PairStatus,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset
    ) {
        self.status = status
        self.verifiedKeyset = verifiedKeyset
    }
}

public enum ProductionC1ReplacementRole: String, Sendable {
    case client
    case runtime

    fileprivate var survivorRole: ProductionC1RequesterRole {
        switch self {
        case .client: .runtime
        case .runtime: .client
        }
    }

    fileprivate var signerRole: ProductionC1RequesterRole {
        switch self {
        case .client: .client
        case .runtime: .runtime
        }
    }
}

public struct ProductionC1CurrentRecoveryCommitments: Equatable, Sendable {
    public let pairBindingDigest: String
    public let endpointTrafficSecretCommitment: String
    public let routeTokenSeedCommitment: String
    public let endpointTrafficSecretReuseDigest: String
    public let routeTokenSeedReuseDigest: String

    fileprivate init(
        pairBindingDigest: String,
        endpointTrafficSecretCommitment: String,
        routeTokenSeedCommitment: String,
        endpointTrafficSecretReuseDigest: String,
        routeTokenSeedReuseDigest: String
    ) {
        self.pairBindingDigest = pairBindingDigest
        self.endpointTrafficSecretCommitment = endpointTrafficSecretCommitment
        self.routeTokenSeedCommitment = routeTokenSeedCommitment
        self.endpointTrafficSecretReuseDigest = endpointTrafficSecretReuseDigest
        self.routeTokenSeedReuseDigest = routeTokenSeedReuseDigest
    }
}

public enum ProductionC1RecoveryCommitments {
    public static let minimumSecretBytes = 32
    public static let maximumSecretBytes = 512

    public static func endpointTrafficSecret(
        pairBindingDigest: String,
        rawSecret: Data
    ) throws -> String {
        let reuseDigest = try materialReuseDigest(
            pairBindingDigest: pairBindingDigest,
            rawSecret: rawSecret
        )
        return try purposeCommitment(
            domain: "AetherLink G1a-C endpoint-traffic-secret commitment v1",
            pairBindingDigest: pairBindingDigest,
            materialReuseDigest: reuseDigest
        )
    }

    public static func routeTokenSeed(
        pairBindingDigest: String,
        rawSecret: Data
    ) throws -> String {
        let reuseDigest = try materialReuseDigest(
            pairBindingDigest: pairBindingDigest,
            rawSecret: rawSecret
        )
        return try purposeCommitment(
            domain: "AetherLink G1a-C route-" + "token-seed commitment v1",
            pairBindingDigest: pairBindingDigest,
            materialReuseDigest: reuseDigest
        )
    }

    public static func currentToken(
        pairBindingDigest: String,
        endpointTrafficSecret: Data,
        routeTokenSeed: Data
    ) throws -> ProductionC1CurrentRecoveryCommitments {
        let endpoint = try self.endpointTrafficSecret(
            pairBindingDigest: pairBindingDigest,
            rawSecret: endpointTrafficSecret
        )
        let route = try self.routeTokenSeed(
            pairBindingDigest: pairBindingDigest,
            rawSecret: routeTokenSeed
        )
        let endpointReuse = try materialReuseDigest(
            pairBindingDigest: pairBindingDigest,
            rawSecret: endpointTrafficSecret
        )
        let routeReuse = try materialReuseDigest(
            pairBindingDigest: pairBindingDigest,
            rawSecret: routeTokenSeed
        )
        guard endpoint != route, endpointReuse != routeReuse else {
            throw ProductionC1Error.invalidFreshPair
        }
        return ProductionC1CurrentRecoveryCommitments(
            pairBindingDigest: pairBindingDigest,
            endpointTrafficSecretCommitment: endpoint,
            routeTokenSeedCommitment: route,
            endpointTrafficSecretReuseDigest: endpointReuse,
            routeTokenSeedReuseDigest: routeReuse
        )
    }

    public static func materialReuseDigest(
        pairBindingDigest: String,
        rawSecret: Data
    ) throws -> String {
        try rawSecretCommitment(
            domain: "AetherLink G1a-C secret-material reuse commitment v1",
            pairBindingDigest: pairBindingDigest,
            rawSecret: rawSecret
        )
    }

    fileprivate static func endpointTrafficSecret(
        pairBindingDigest: String,
        materialReuseDigest: String
    ) throws -> String {
        try purposeCommitment(
            domain: "AetherLink G1a-C endpoint-traffic-secret commitment v1",
            pairBindingDigest: pairBindingDigest,
            materialReuseDigest: materialReuseDigest
        )
    }

    fileprivate static func routeTokenSeed(
        pairBindingDigest: String,
        materialReuseDigest: String
    ) throws -> String {
        try purposeCommitment(
            domain: "AetherLink G1a-C route-" + "token-seed commitment v1",
            pairBindingDigest: pairBindingDigest,
            materialReuseDigest: materialReuseDigest
        )
    }

    private static func rawSecretCommitment(
        domain: String,
        pairBindingDigest: String,
        rawSecret: Data
    ) throws -> String {
        try c1ValidateDigest(pairBindingDigest)
        guard rawSecret.count >= minimumSecretBytes,
              rawSecret.count <= maximumSecretBytes else {
            throw ProductionC1Error.limitExceeded
        }
        var claims = c1ForceDecodeDigest(pairBindingDigest)
        claims.append(c1BE(UInt32(rawSecret.count)))
        claims.append(rawSecret)
        return c1DigestHex(c1SignatureTranscript(domain: domain, claims: claims))
    }

    private static func purposeCommitment(
        domain: String,
        pairBindingDigest: String,
        materialReuseDigest: String
    ) throws -> String {
        try c1ValidateDigest(pairBindingDigest)
        try c1ValidateDigest(materialReuseDigest)
        var claims = c1ForceDecodeDigest(pairBindingDigest)
        claims.append(c1ForceDecodeDigest(materialReuseDigest))
        return c1DigestHex(c1SignatureTranscript(domain: domain, claims: claims))
    }
}

public struct ProductionC1FreshPairProof: Equatable, Sendable {
    public let transitionId: String
    public let replacementRole: ProductionC1ReplacementRole
    public let previousAuthorityDigest: String
    public let previousPairBindingDigest: String
    public let nextPairBindingDigest: String
    public let previousPairEpoch: UInt64
    public let nextPairEpoch: UInt64
    public let previousClientIdentityFingerprint: String
    public let nextClientIdentityFingerprint: String
    public let previousRuntimeIdentityFingerprint: String
    public let nextRuntimeIdentityFingerprint: String
    public let nextGeneration: UInt64
    public let nextServiceConfigVersion: UInt64
    public let nextKeysetVersion: UInt64
    public let nextRevocationCounter: UInt64
    public let nextProtocolFloor: UInt32
    public let nextAuthorityRevision: UInt64
    public let issuedAtMs: UInt64
    public let expiresAtMs: UInt64
    public let freshPairingRequestDigest: String
    public let freshPairingResultDigest: String
    public let freshTransportBindingDigest: String
    public let previousEndpointTrafficSecretCommitment: String
    public let nextEndpointTrafficSecretCommitment: String
    public let previousRouteTokenSeedCommitment: String
    public let nextRouteTokenSeedCommitment: String
    public let previousEndpointTrafficSecretReuseDigest: String
    public let nextEndpointTrafficSecretReuseDigest: String
    public let previousRouteTokenSeedReuseDigest: String
    public let nextRouteTokenSeedReuseDigest: String
    public let survivorSignature: Data
    public let replacementSignature: Data

    public var transitionRequestDigest: String {
        c1DigestHex(C1TLV.encode(
            objectType: ProductionC1Contract.freshPairProofObjectType,
            fields: claimsFields
        ))
    }

    private init(
        transitionId: String,
        replacementRole: ProductionC1ReplacementRole,
        previousAuthorityDigest: String,
        previousPairBindingDigest: String,
        nextPairBindingDigest: String,
        previousPairEpoch: UInt64,
        nextPairEpoch: UInt64,
        previousClientIdentityFingerprint: String,
        nextClientIdentityFingerprint: String,
        previousRuntimeIdentityFingerprint: String,
        nextRuntimeIdentityFingerprint: String,
        nextGeneration: UInt64,
        nextServiceConfigVersion: UInt64,
        nextKeysetVersion: UInt64,
        nextRevocationCounter: UInt64,
        nextProtocolFloor: UInt32,
        nextAuthorityRevision: UInt64,
        issuedAtMs: UInt64,
        expiresAtMs: UInt64,
        freshPairingRequestDigest: String,
        freshPairingResultDigest: String,
        freshTransportBindingDigest: String,
        previousEndpointTrafficSecretCommitment: String,
        nextEndpointTrafficSecretCommitment: String,
        previousRouteTokenSeedCommitment: String,
        nextRouteTokenSeedCommitment: String,
        previousEndpointTrafficSecretReuseDigest: String,
        nextEndpointTrafficSecretReuseDigest: String,
        previousRouteTokenSeedReuseDigest: String,
        nextRouteTokenSeedReuseDigest: String,
        survivorSignature: Data,
        replacementSignature: Data,
        validateSignatureEncoding: Bool
    ) throws {
        for digest in [
            transitionId, previousAuthorityDigest, previousPairBindingDigest,
            nextPairBindingDigest, previousClientIdentityFingerprint,
            nextClientIdentityFingerprint, previousRuntimeIdentityFingerprint,
            nextRuntimeIdentityFingerprint, freshPairingRequestDigest,
            freshPairingResultDigest, freshTransportBindingDigest,
            previousEndpointTrafficSecretCommitment, nextEndpointTrafficSecretCommitment,
            previousRouteTokenSeedCommitment, nextRouteTokenSeedCommitment,
            previousEndpointTrafficSecretReuseDigest, nextEndpointTrafficSecretReuseDigest,
            previousRouteTokenSeedReuseDigest, nextRouteTokenSeedReuseDigest,
        ] { try c1ValidateDigest(digest) }
        let expectedPreviousEndpoint = try ProductionC1RecoveryCommitments.endpointTrafficSecret(
            pairBindingDigest: previousPairBindingDigest,
            materialReuseDigest: previousEndpointTrafficSecretReuseDigest
        )
        let expectedNextEndpoint = try ProductionC1RecoveryCommitments.endpointTrafficSecret(
            pairBindingDigest: nextPairBindingDigest,
            materialReuseDigest: nextEndpointTrafficSecretReuseDigest
        )
        let expectedPreviousRoute = try ProductionC1RecoveryCommitments.routeTokenSeed(
            pairBindingDigest: previousPairBindingDigest,
            materialReuseDigest: previousRouteTokenSeedReuseDigest
        )
        let expectedNextRoute = try ProductionC1RecoveryCommitments.routeTokenSeed(
            pairBindingDigest: nextPairBindingDigest,
            materialReuseDigest: nextRouteTokenSeedReuseDigest
        )
        guard previousPairEpoch > 0,
              previousPairEpoch < UInt64.max,
              nextPairEpoch == previousPairEpoch + 1,
              previousPairBindingDigest == nextPairBindingDigest,
              nextGeneration > 0,
              nextServiceConfigVersion > 0,
              nextKeysetVersion > 0,
              nextProtocolFloor > 0,
              nextAuthorityRevision > 1,
              issuedAtMs < expiresAtMs,
              freshPairingRequestDigest != freshPairingResultDigest,
              previousEndpointTrafficSecretCommitment == expectedPreviousEndpoint,
              nextEndpointTrafficSecretCommitment == expectedNextEndpoint,
              previousRouteTokenSeedCommitment == expectedPreviousRoute,
              nextRouteTokenSeedCommitment == expectedNextRoute,
              previousEndpointTrafficSecretCommitment != nextEndpointTrafficSecretCommitment,
              previousRouteTokenSeedCommitment != nextRouteTokenSeedCommitment,
              previousEndpointTrafficSecretCommitment != previousRouteTokenSeedCommitment,
              nextEndpointTrafficSecretCommitment != nextRouteTokenSeedCommitment,
              Set([
                  previousEndpointTrafficSecretReuseDigest,
                  nextEndpointTrafficSecretReuseDigest,
                  previousRouteTokenSeedReuseDigest,
                  nextRouteTokenSeedReuseDigest,
              ]).count == 4 else {
            throw ProductionC1Error.invalidFreshPair
        }
        let clientChanged = previousClientIdentityFingerprint != nextClientIdentityFingerprint
        let runtimeChanged = previousRuntimeIdentityFingerprint != nextRuntimeIdentityFingerprint
        guard clientChanged != runtimeChanged,
              (replacementRole == .client) == clientChanged,
              previousClientIdentityFingerprint != previousRuntimeIdentityFingerprint,
              nextClientIdentityFingerprint != nextRuntimeIdentityFingerprint else {
            throw ProductionC1Error.invalidFreshPair
        }
        if validateSignatureEncoding {
            try c1ValidateCanonicalLowS(survivorSignature)
            try c1ValidateCanonicalLowS(replacementSignature)
        }
        self.transitionId = transitionId
        self.replacementRole = replacementRole
        self.previousAuthorityDigest = previousAuthorityDigest
        self.previousPairBindingDigest = previousPairBindingDigest
        self.nextPairBindingDigest = nextPairBindingDigest
        self.previousPairEpoch = previousPairEpoch
        self.nextPairEpoch = nextPairEpoch
        self.previousClientIdentityFingerprint = previousClientIdentityFingerprint
        self.nextClientIdentityFingerprint = nextClientIdentityFingerprint
        self.previousRuntimeIdentityFingerprint = previousRuntimeIdentityFingerprint
        self.nextRuntimeIdentityFingerprint = nextRuntimeIdentityFingerprint
        self.nextGeneration = nextGeneration
        self.nextServiceConfigVersion = nextServiceConfigVersion
        self.nextKeysetVersion = nextKeysetVersion
        self.nextRevocationCounter = nextRevocationCounter
        self.nextProtocolFloor = nextProtocolFloor
        self.nextAuthorityRevision = nextAuthorityRevision
        self.issuedAtMs = issuedAtMs
        self.expiresAtMs = expiresAtMs
        self.freshPairingRequestDigest = freshPairingRequestDigest
        self.freshPairingResultDigest = freshPairingResultDigest
        self.freshTransportBindingDigest = freshTransportBindingDigest
        self.previousEndpointTrafficSecretCommitment = previousEndpointTrafficSecretCommitment
        self.nextEndpointTrafficSecretCommitment = nextEndpointTrafficSecretCommitment
        self.previousRouteTokenSeedCommitment = previousRouteTokenSeedCommitment
        self.nextRouteTokenSeedCommitment = nextRouteTokenSeedCommitment
        self.previousEndpointTrafficSecretReuseDigest = previousEndpointTrafficSecretReuseDigest
        self.nextEndpointTrafficSecretReuseDigest = nextEndpointTrafficSecretReuseDigest
        self.previousRouteTokenSeedReuseDigest = previousRouteTokenSeedReuseDigest
        self.nextRouteTokenSeedReuseDigest = nextRouteTokenSeedReuseDigest
        self.survivorSignature = survivorSignature
        self.replacementSignature = replacementSignature
        guard try canonicalBytes().count <= ProductionC1Contract.maximumFreshPairProofBytes else {
            throw ProductionC1Error.limitExceeded
        }
    }

    public static func signed(
        transitionId: String,
        replacementRole: ProductionC1ReplacementRole,
        previousAuthority: ProductionPairAuthorityState,
        nextClientIdentityFingerprint: String,
        nextRuntimeIdentityFingerprint: String,
        nextGeneration: UInt64,
        nextServiceConfigVersion: UInt64,
        nextKeysetVersion: UInt64,
        nextRevocationCounter: UInt64,
        nextProtocolFloor: UInt32,
        issuedAtMs: UInt64,
        expiresAtMs: UInt64,
        freshPairingRequestDigest: String,
        freshPairingResultDigest: String,
        freshTransportBindingDigest: String,
        currentCommitments: ProductionC1CurrentRecoveryCommitments,
        nextEndpointTrafficSecret: Data,
        nextRouteTokenSeed: Data,
        survivorKey: P256.Signing.PrivateKey,
        replacementKey: P256.Signing.PrivateKey
    ) throws -> Self {
        guard previousAuthority.pairEpoch < UInt64.max,
              previousAuthority.authorityRevision < UInt64.max else {
            throw ProductionC1Error.invalidFreshPair
        }
        guard currentCommitments.pairBindingDigest == previousAuthority.pairBindingDigest else {
            throw ProductionC1Error.invalidFreshPair
        }
        let nextEndpointCommitment = try ProductionC1RecoveryCommitments.endpointTrafficSecret(
            pairBindingDigest: previousAuthority.pairBindingDigest,
            rawSecret: nextEndpointTrafficSecret
        )
        let nextRouteCommitment = try ProductionC1RecoveryCommitments.routeTokenSeed(
            pairBindingDigest: previousAuthority.pairBindingDigest,
            rawSecret: nextRouteTokenSeed
        )
        let nextEndpointReuse = try ProductionC1RecoveryCommitments.materialReuseDigest(
            pairBindingDigest: previousAuthority.pairBindingDigest,
            rawSecret: nextEndpointTrafficSecret
        )
        let nextRouteReuse = try ProductionC1RecoveryCommitments.materialReuseDigest(
            pairBindingDigest: previousAuthority.pairBindingDigest,
            rawSecret: nextRouteTokenSeed
        )
        let unsigned = try Self(
            transitionId: transitionId,
            replacementRole: replacementRole,
            previousAuthorityDigest: previousAuthority.digestHex(),
            previousPairBindingDigest: previousAuthority.pairBindingDigest,
            nextPairBindingDigest: previousAuthority.pairBindingDigest,
            previousPairEpoch: previousAuthority.pairEpoch,
            nextPairEpoch: previousAuthority.pairEpoch + 1,
            previousClientIdentityFingerprint: previousAuthority.clientIdentityFingerprint,
            nextClientIdentityFingerprint: nextClientIdentityFingerprint,
            previousRuntimeIdentityFingerprint: previousAuthority.runtimeIdentityFingerprint,
            nextRuntimeIdentityFingerprint: nextRuntimeIdentityFingerprint,
            nextGeneration: nextGeneration,
            nextServiceConfigVersion: nextServiceConfigVersion,
            nextKeysetVersion: nextKeysetVersion,
            nextRevocationCounter: nextRevocationCounter,
            nextProtocolFloor: nextProtocolFloor,
            nextAuthorityRevision: previousAuthority.authorityRevision + 1,
            issuedAtMs: issuedAtMs,
            expiresAtMs: expiresAtMs,
            freshPairingRequestDigest: freshPairingRequestDigest,
            freshPairingResultDigest: freshPairingResultDigest,
            freshTransportBindingDigest: freshTransportBindingDigest,
            previousEndpointTrafficSecretCommitment:
                currentCommitments.endpointTrafficSecretCommitment,
            nextEndpointTrafficSecretCommitment: nextEndpointCommitment,
            previousRouteTokenSeedCommitment: currentCommitments.routeTokenSeedCommitment,
            nextRouteTokenSeedCommitment: nextRouteCommitment,
            previousEndpointTrafficSecretReuseDigest:
                currentCommitments.endpointTrafficSecretReuseDigest,
            nextEndpointTrafficSecretReuseDigest: nextEndpointReuse,
            previousRouteTokenSeedReuseDigest: currentCommitments.routeTokenSeedReuseDigest,
            nextRouteTokenSeedReuseDigest: nextRouteReuse,
            survivorSignature: Data(),
            replacementSignature: Data(),
            validateSignatureEncoding: false
        )
        return try Self(
            transitionId: transitionId,
            replacementRole: replacementRole,
            previousAuthorityDigest: unsigned.previousAuthorityDigest,
            previousPairBindingDigest: unsigned.previousPairBindingDigest,
            nextPairBindingDigest: unsigned.nextPairBindingDigest,
            previousPairEpoch: unsigned.previousPairEpoch,
            nextPairEpoch: unsigned.nextPairEpoch,
            previousClientIdentityFingerprint: unsigned.previousClientIdentityFingerprint,
            nextClientIdentityFingerprint: nextClientIdentityFingerprint,
            previousRuntimeIdentityFingerprint: unsigned.previousRuntimeIdentityFingerprint,
            nextRuntimeIdentityFingerprint: nextRuntimeIdentityFingerprint,
            nextGeneration: nextGeneration,
            nextServiceConfigVersion: nextServiceConfigVersion,
            nextKeysetVersion: nextKeysetVersion,
            nextRevocationCounter: nextRevocationCounter,
            nextProtocolFloor: nextProtocolFloor,
            nextAuthorityRevision: unsigned.nextAuthorityRevision,
            issuedAtMs: issuedAtMs,
            expiresAtMs: expiresAtMs,
            freshPairingRequestDigest: unsigned.freshPairingRequestDigest,
            freshPairingResultDigest: unsigned.freshPairingResultDigest,
            freshTransportBindingDigest: unsigned.freshTransportBindingDigest,
            previousEndpointTrafficSecretCommitment:
                unsigned.previousEndpointTrafficSecretCommitment,
            nextEndpointTrafficSecretCommitment: unsigned.nextEndpointTrafficSecretCommitment,
            previousRouteTokenSeedCommitment: unsigned.previousRouteTokenSeedCommitment,
            nextRouteTokenSeedCommitment: unsigned.nextRouteTokenSeedCommitment,
            previousEndpointTrafficSecretReuseDigest:
                unsigned.previousEndpointTrafficSecretReuseDigest,
            nextEndpointTrafficSecretReuseDigest: unsigned.nextEndpointTrafficSecretReuseDigest,
            previousRouteTokenSeedReuseDigest: unsigned.previousRouteTokenSeedReuseDigest,
            nextRouteTokenSeedReuseDigest: unsigned.nextRouteTokenSeedReuseDigest,
            survivorSignature: c1Sign(
                unsigned.survivorSigningTranscript,
                using: survivorKey
            ),
            replacementSignature: c1Sign(
                unsigned.replacementSigningTranscript,
                using: replacementKey
            ),
            validateSignatureEncoding: true
        )
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try C1TLV.decode(
            data,
            objectType: ProductionC1Contract.freshPairProofObjectType,
            fieldCount: 36,
            maximumBytes: ProductionC1Contract.maximumFreshPairProofBytes
        )
        guard try c1Text(fields[0]) == ProductionC1Contract.suite,
              let replacement = ProductionC1ReplacementRole(rawValue: try c1Text(fields[2])),
              try c1Text(fields[31]) == ProductionC1Contract.signatureAlgorithm,
              try c1Text(fields[32]) == replacement.survivorRole.rawValue,
              try c1Text(fields[33]) == replacement.signerRole.rawValue else {
            throw ProductionC1Error.invalidFreshPair
        }
        try self.init(
            transitionId: c1Text(fields[1]),
            replacementRole: replacement,
            previousAuthorityDigest: c1Text(fields[3]),
            previousPairBindingDigest: c1Text(fields[4]),
            nextPairBindingDigest: c1Text(fields[5]),
            previousPairEpoch: c1UInt64(fields[6]),
            nextPairEpoch: c1UInt64(fields[7]),
            previousClientIdentityFingerprint: c1Text(fields[8]),
            nextClientIdentityFingerprint: c1Text(fields[9]),
            previousRuntimeIdentityFingerprint: c1Text(fields[10]),
            nextRuntimeIdentityFingerprint: c1Text(fields[11]),
            nextGeneration: c1UInt64(fields[12]),
            nextServiceConfigVersion: c1UInt64(fields[13]),
            nextKeysetVersion: c1UInt64(fields[14]),
            nextRevocationCounter: c1UInt64(fields[15]),
            nextProtocolFloor: c1UInt32(fields[16]),
            nextAuthorityRevision: c1UInt64(fields[17]),
            issuedAtMs: c1UInt64(fields[18]),
            expiresAtMs: c1UInt64(fields[19]),
            freshPairingRequestDigest: c1Text(fields[20]),
            freshPairingResultDigest: c1Text(fields[21]),
            freshTransportBindingDigest: c1Text(fields[22]),
            previousEndpointTrafficSecretCommitment: c1Text(fields[23]),
            nextEndpointTrafficSecretCommitment: c1Text(fields[24]),
            previousRouteTokenSeedCommitment: c1Text(fields[25]),
            nextRouteTokenSeedCommitment: c1Text(fields[26]),
            previousEndpointTrafficSecretReuseDigest: c1Text(fields[27]),
            nextEndpointTrafficSecretReuseDigest: c1Text(fields[28]),
            previousRouteTokenSeedReuseDigest: c1Text(fields[29]),
            nextRouteTokenSeedReuseDigest: c1Text(fields[30]),
            survivorSignature: fields[34],
            replacementSignature: fields[35],
            validateSignatureEncoding: true
        )
        guard try canonicalBytes() == data else { throw ProductionC1Error.malformedCanonical }
    }

    public func canonicalBytes() throws -> Data {
        C1TLV.encode(
            objectType: ProductionC1Contract.freshPairProofObjectType,
            fields: claimsFields + [survivorSignature, replacementSignature]
        )
    }

    public func digestHex() throws -> String { c1DigestHex(try canonicalBytes()) }

    fileprivate var survivorSigningTranscript: Data {
        c1SignatureTranscript(
            domain: "AetherLink G1a-C fresh-pair survivor \(replacementRole.survivorRole.rawValue) signature v1",
            claims: C1TLV.encode(
                objectType: ProductionC1Contract.freshPairProofObjectType,
                fields: claimsFields
            )
        )
    }

    fileprivate var replacementSigningTranscript: Data {
        c1SignatureTranscript(
            domain: "AetherLink G1a-C fresh-pair replacement \(replacementRole.signerRole.rawValue) signature v1",
            claims: C1TLV.encode(
                objectType: ProductionC1Contract.freshPairProofObjectType,
                fields: claimsFields
            )
        )
    }

    private var claimsFields: [Data] {
        [
            c1ASCII(ProductionC1Contract.suite), c1ASCII(transitionId),
            c1ASCII(replacementRole.rawValue), c1ASCII(previousAuthorityDigest),
            c1ASCII(previousPairBindingDigest), c1ASCII(nextPairBindingDigest),
            c1BE(previousPairEpoch), c1BE(nextPairEpoch),
            c1ASCII(previousClientIdentityFingerprint), c1ASCII(nextClientIdentityFingerprint),
            c1ASCII(previousRuntimeIdentityFingerprint), c1ASCII(nextRuntimeIdentityFingerprint),
            c1BE(nextGeneration), c1BE(nextServiceConfigVersion), c1BE(nextKeysetVersion),
            c1BE(nextRevocationCounter), c1BE(nextProtocolFloor), c1BE(nextAuthorityRevision),
            c1BE(issuedAtMs), c1BE(expiresAtMs), c1ASCII(freshPairingRequestDigest),
            c1ASCII(freshPairingResultDigest), c1ASCII(freshTransportBindingDigest),
            c1ASCII(previousEndpointTrafficSecretCommitment),
            c1ASCII(nextEndpointTrafficSecretCommitment),
            c1ASCII(previousRouteTokenSeedCommitment), c1ASCII(nextRouteTokenSeedCommitment),
            c1ASCII(previousEndpointTrafficSecretReuseDigest),
            c1ASCII(nextEndpointTrafficSecretReuseDigest),
            c1ASCII(previousRouteTokenSeedReuseDigest), c1ASCII(nextRouteTokenSeedReuseDigest),
            c1ASCII(ProductionC1Contract.signatureAlgorithm),
            c1ASCII(replacementRole.survivorRole.rawValue),
            c1ASCII(replacementRole.signerRole.rawValue),
        ]
    }
}

public struct ProductionC1FreshPairApplyPreparation: Equatable, Sendable {
    public let expectedPreviousAuthorityDigest: String
    public let expectedPreviousSnapshotDigest: String
    public let nextAuthority: ProductionPairAuthorityState
    public let nextTransitionHistory: [ProductionPairTransitionHistoryEntry]
    public let nextSnapshot: ProductionPairStateSnapshot

    fileprivate init(
        expectedPreviousAuthorityDigest: String,
        expectedPreviousSnapshotDigest: String,
        nextAuthority: ProductionPairAuthorityState,
        nextTransitionHistory: [ProductionPairTransitionHistoryEntry],
        nextSnapshot: ProductionPairStateSnapshot
    ) {
        self.expectedPreviousAuthorityDigest = expectedPreviousAuthorityDigest
        self.expectedPreviousSnapshotDigest = expectedPreviousSnapshotDigest
        self.nextAuthority = nextAuthority
        self.nextTransitionHistory = nextTransitionHistory
        self.nextSnapshot = nextSnapshot
    }
}

public struct VerifiedProductionC1FreshPairTransition: Equatable, Sendable {
    public let proof: ProductionC1FreshPairProof
    public let status: ProductionC1PairStatus
    public let applyPreparation: ProductionC1FreshPairApplyPreparation
    fileprivate let verifiedStatus: VerifiedProductionC1PairStatus

    fileprivate init(
        proof: ProductionC1FreshPairProof,
        verifiedStatus: VerifiedProductionC1PairStatus,
        applyPreparation: ProductionC1FreshPairApplyPreparation
    ) {
        self.proof = proof
        self.status = verifiedStatus.status
        self.verifiedStatus = verifiedStatus
        self.applyPreparation = applyPreparation
    }
}

public enum ProductionC1FreshPairStateMachine {
    public static func apply(
        _ verified: VerifiedProductionC1FreshPairTransition,
        to current: ProductionPairStateSnapshot,
        nowMs: UInt64
    ) throws -> ProductionPairStateTransitionResult {
        try c1ValidateFreshPairTransitionUse(verified, nowMs: nowMs)
        let preparation = verified.applyPreparation
        if try current.digestHex() == preparation.nextSnapshot.digestHex() {
            return ProductionPairStateTransitionResult(
                disposition: .idempotent,
                snapshot: current
            )
        }
        guard try current.authority.digestHex() == preparation.expectedPreviousAuthorityDigest,
              try current.digestHex() == preparation.expectedPreviousSnapshotDigest else {
            throw ProductionC1Error.stateMismatch
        }
        return ProductionPairStateTransitionResult(
            disposition: .applied,
            snapshot: preparation.nextSnapshot
        )
    }
}

public enum ProductionC1RouteKind: String, CaseIterable, Sendable {
    case p2pDirect = "verified_p2p_direct_v1"
    case turnRelay = "verified_turn_relay_v1"
    case sealedRelay = "verified_sealed_relay_v1"

    fileprivate var connectorObjectType: UInt8 {
        switch self {
        case .p2pDirect: ProductionC1Contract.p2pConnectorObjectType
        case .turnRelay: ProductionC1Contract.turnConnectorObjectType
        case .sealedRelay: ProductionC1Contract.sealedRelayConnectorObjectType
        }
    }

    fileprivate var authorizationObjectType: UInt8 {
        switch self {
        case .p2pDirect: ProductionC1Contract.p2pRouteAuthorizationObjectType
        case .turnRelay: ProductionC1Contract.turnRouteAuthorizationObjectType
        case .sealedRelay: ProductionC1Contract.sealedRelayRouteAuthorizationObjectType
        }
    }

    fileprivate var transcriptKind: ProductionRouteAuthorizationKind {
        switch self {
        case .p2pDirect: .p2pDirect
        case .turnRelay: .turnRelay
        case .sealedRelay: .sealedRelay
        }
    }

    fileprivate init?(transcriptKind: ProductionRouteAuthorizationKind) {
        switch transcriptKind {
        case .p2pDirect: self = .p2pDirect
        case .turnRelay: self = .turnRelay
        case .sealedRelay: self = .sealedRelay
        case .localDirect, .p2pPublish, .p2pFetch: return nil
        }
    }
}

public struct ProductionC1PreauthorizationSessionContext: Equatable, Sendable {
    public static let revision: UInt64 = 1

    public let sessionId: String
    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let clientIdentityFingerprint: String
    public let runtimeIdentityFingerprint: String
    public let clientEphemeralPublicKey: Data
    public let runtimeEphemeralPublicKey: Data
    public let clientNonce: String
    public let runtimeNonce: String
    public let generation: UInt64
    public let serviceConfigVersion: UInt64
    public let keysetVersion: UInt64
    public let revocationCounter: UInt64
    public let routeKind: ProductionC1RouteKind

    public init(
        sessionId: String,
        pairBindingDigest: String,
        pairEpoch: UInt64,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        clientEphemeralPublicKey: Data,
        runtimeEphemeralPublicKey: Data,
        clientNonce: String,
        runtimeNonce: String,
        generation: UInt64,
        serviceConfigVersion: UInt64,
        keysetVersion: UInt64,
        revocationCounter: UInt64,
        routeKind: ProductionC1RouteKind
    ) throws {
        guard let sessionBytes = c1DecodeLowerHex(sessionId), sessionBytes.count == 16,
              let clientNonceBytes = c1DecodeLowerHex(clientNonce), clientNonceBytes.count == 16,
              let runtimeNonceBytes = c1DecodeLowerHex(runtimeNonce), runtimeNonceBytes.count == 16 else {
            throw ProductionC1Error.invalidValue
        }
        for digest in [
            pairBindingDigest, clientIdentityFingerprint, runtimeIdentityFingerprint,
        ] { try c1ValidateDigest(digest) }
        _ = try c1PublicKey(x963: clientEphemeralPublicKey)
        _ = try c1PublicKey(x963: runtimeEphemeralPublicKey)
        guard pairEpoch > 0,
              generation > 0,
              serviceConfigVersion > 0,
              keysetVersion > 0,
              clientIdentityFingerprint != runtimeIdentityFingerprint,
              clientEphemeralPublicKey != runtimeEphemeralPublicKey,
              clientNonce != runtimeNonce else {
            throw ProductionC1Error.invalidValue
        }
        self.sessionId = sessionId
        self.pairBindingDigest = pairBindingDigest
        self.pairEpoch = pairEpoch
        self.clientIdentityFingerprint = clientIdentityFingerprint
        self.runtimeIdentityFingerprint = runtimeIdentityFingerprint
        self.clientEphemeralPublicKey = clientEphemeralPublicKey
        self.runtimeEphemeralPublicKey = runtimeEphemeralPublicKey
        self.clientNonce = clientNonce
        self.runtimeNonce = runtimeNonce
        self.generation = generation
        self.serviceConfigVersion = serviceConfigVersion
        self.keysetVersion = keysetVersion
        self.revocationCounter = revocationCounter
        self.routeKind = routeKind
        guard canonicalBytes().count <=
                ProductionC1Contract.maximumPreauthorizationSessionContextBytes else {
            throw ProductionC1Error.limitExceeded
        }
    }

    public init(transcript: ProductionSecureSessionTranscript) throws {
        guard let kind = ProductionC1RouteKind(transcriptKind: transcript.routeKind) else {
            throw ProductionC1Error.routeMismatch
        }
        try self.init(
            sessionId: transcript.sessionId,
            pairBindingDigest: transcript.pairBindingDigest,
            pairEpoch: transcript.pairEpoch,
            clientIdentityFingerprint: transcript.clientIdentityFingerprint,
            runtimeIdentityFingerprint: transcript.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: transcript.clientEphemeralPublicKey,
            runtimeEphemeralPublicKey: transcript.runtimeEphemeralPublicKey,
            clientNonce: transcript.clientNonce,
            runtimeNonce: transcript.runtimeNonce,
            generation: transcript.generation,
            serviceConfigVersion: transcript.serviceConfigVersion,
            keysetVersion: transcript.keysetVersion,
            revocationCounter: transcript.revocationCounter,
            routeKind: kind
        )
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try C1TLV.decode(
            data,
            objectType: ProductionC1Contract.preauthorizationSessionContextObjectType,
            fieldCount: 21,
            maximumBytes: ProductionC1Contract.maximumPreauthorizationSessionContextBytes
        )
        guard try c1Text(fields[0]) == ProductionC1Contract.suite,
              try c1UInt64(fields[1]) == Self.revision,
              try c1Text(fields[7]) == "client",
              try c1Text(fields[8]) == "runtime",
              try c1UInt32(fields[17]) == ProductionSecureSessionTranscript.protocolVersion,
              try c1UInt32(fields[18]) == ProductionSecureSessionTranscript.minimumProtocolVersion,
              try c1Text(fields[19]) == ProductionSecureSessionTranscript.profile,
              let kind = ProductionC1RouteKind(rawValue: try c1Text(fields[20])) else {
            throw ProductionC1Error.invalidValue
        }
        try self.init(
            sessionId: c1Text(fields[2]),
            pairBindingDigest: c1Text(fields[3]),
            pairEpoch: c1UInt64(fields[4]),
            clientIdentityFingerprint: c1Text(fields[5]),
            runtimeIdentityFingerprint: c1Text(fields[6]),
            clientEphemeralPublicKey: fields[9],
            runtimeEphemeralPublicKey: fields[10],
            clientNonce: c1Text(fields[11]),
            runtimeNonce: c1Text(fields[12]),
            generation: c1UInt64(fields[13]),
            serviceConfigVersion: c1UInt64(fields[14]),
            keysetVersion: c1UInt64(fields[15]),
            revocationCounter: c1UInt64(fields[16]),
            routeKind: kind
        )
        guard canonicalBytes() == data else { throw ProductionC1Error.malformedCanonical }
    }

    public func canonicalBytes() -> Data {
        C1TLV.encode(
            objectType: ProductionC1Contract.preauthorizationSessionContextObjectType,
            fields: [
                c1ASCII(ProductionC1Contract.suite), c1BE(Self.revision), c1ASCII(sessionId),
                c1ASCII(pairBindingDigest), c1BE(pairEpoch),
                c1ASCII(clientIdentityFingerprint), c1ASCII(runtimeIdentityFingerprint),
                c1ASCII("client"), c1ASCII("runtime"), clientEphemeralPublicKey,
                runtimeEphemeralPublicKey, c1ASCII(clientNonce), c1ASCII(runtimeNonce),
                c1BE(generation), c1BE(serviceConfigVersion), c1BE(keysetVersion),
                c1BE(revocationCounter), c1BE(ProductionSecureSessionTranscript.protocolVersion),
                c1BE(ProductionSecureSessionTranscript.minimumProtocolVersion),
                c1ASCII(ProductionSecureSessionTranscript.profile), c1ASCII(routeKind.rawValue),
            ]
        )
    }

    public func digestHex() -> String { c1DigestHex(canonicalBytes()) }
}

public enum ProductionC1RouteTransport: String, Sendable {
    case udp
    case tlsTcp = "tls_tcp"
}

public struct ProductionC1RouteConnectorMaterial: Equatable, Sendable {
    public let kind: ProductionC1RouteKind
    public let addressBytes: Data
    public let port: UInt16
    public let serverName: String?
    public let transport: ProductionC1RouteTransport
    public let routeHandleDigest: String
    public let credentialCommitmentDigest: String
    public let pathReceiptDigest: String
    public let leaseDigest: String?
    public let allocationDigest: String?

    public init(
        kind: ProductionC1RouteKind,
        addressBytes: Data,
        port: UInt16,
        serverName: String?,
        transport: ProductionC1RouteTransport,
        routeHandleDigest: String,
        credentialCommitmentDigest: String,
        pathReceiptDigest: String,
        leaseDigest: String? = nil,
        allocationDigest: String? = nil
    ) throws {
        for digest in [routeHandleDigest, credentialCommitmentDigest, pathReceiptDigest] {
            try c1ValidateDigest(digest)
        }
        if let leaseDigest { try c1ValidateDigest(leaseDigest) }
        if let allocationDigest { try c1ValidateDigest(allocationDigest) }
        guard addressBytes.count == 4 || addressBytes.count == 16,
              port > 0,
              serverName.map(c1IsCanonicalServerName) ?? true else {
            throw ProductionC1Error.invalidValue
        }
        switch kind {
        case .p2pDirect:
            guard serverName == nil,
                  transport == .udp,
                  leaseDigest == nil,
                  allocationDigest == nil else {
                throw ProductionC1Error.invalidValue
            }
        case .turnRelay, .sealedRelay:
            guard serverName != nil,
                  transport == .tlsTcp,
                  leaseDigest != nil,
                  allocationDigest != nil else {
                throw ProductionC1Error.invalidValue
            }
        }
        self.kind = kind
        self.addressBytes = addressBytes
        self.port = port
        self.serverName = serverName
        self.transport = transport
        self.routeHandleDigest = routeHandleDigest
        self.credentialCommitmentDigest = credentialCommitmentDigest
        self.pathReceiptDigest = pathReceiptDigest
        self.leaseDigest = leaseDigest
        self.allocationDigest = allocationDigest
        guard try canonicalBytes().count <= ProductionC1Contract.maximumConnectorBytes else {
            throw ProductionC1Error.limitExceeded
        }
    }

    public init(canonicalBytes data: Data) throws {
        guard let kind = ProductionC1RouteKind.allCases.first(where: {
            $0.connectorObjectType == data.dropFirst(4).first
        }) else {
            throw ProductionC1Error.malformedCanonical
        }
        let fields = try C1TLV.decode(
            data,
            objectType: kind.connectorObjectType,
            fieldCount: 11,
            maximumBytes: ProductionC1Contract.maximumConnectorBytes
        )
        guard try c1Text(fields[0]) == ProductionC1Contract.suite,
              try c1Text(fields[1]) == kind.rawValue,
              let transport = ProductionC1RouteTransport(rawValue: try c1Text(fields[5])) else {
            throw ProductionC1Error.invalidValue
        }
        let serverText = try c1Text(fields[4])
        try self.init(
            kind: kind,
            addressBytes: fields[2],
            port: c1UInt16(fields[3]),
            serverName: serverText == "none" ? nil : serverText,
            transport: transport,
            routeHandleDigest: c1Text(fields[6]),
            credentialCommitmentDigest: c1Text(fields[7]),
            pathReceiptDigest: c1Text(fields[8]),
            leaseDigest: c1OptionalDigest(fields[9]),
            allocationDigest: c1OptionalDigest(fields[10])
        )
        guard try canonicalBytes() == data else { throw ProductionC1Error.malformedCanonical }
    }

    public func canonicalBytes() throws -> Data {
        C1TLV.encode(
            objectType: kind.connectorObjectType,
            fields: [
                c1ASCII(ProductionC1Contract.suite),
                c1ASCII(kind.rawValue),
                addressBytes,
                c1BE(port),
                c1ASCII(serverName ?? "none"),
                c1ASCII(transport.rawValue),
                c1ASCII(routeHandleDigest),
                c1ASCII(credentialCommitmentDigest),
                c1ASCII(pathReceiptDigest),
                c1OptionalDigestBytes(leaseDigest),
                c1OptionalDigestBytes(allocationDigest),
            ]
        )
    }
}

public struct ProductionC1RoutePlanClaims: Equatable, Sendable {
    public static let revision: UInt64 = 1

    public let planId: String
    public let kind: ProductionC1RouteKind
    public let pairAuthorityDigest: String
    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let generation: UInt64
    public let clientIdentityFingerprint: String
    public let runtimeIdentityFingerprint: String
    public let connector: ProductionC1RouteConnectorMaterial
    public let securityContextDigest: String
    public let selectedPathReceiptDigest: String
    public let notBeforeMs: UInt64
    public let expiresAtMs: UInt64

    public init(
        planId: String,
        kind: ProductionC1RouteKind,
        pairAuthorityDigest: String,
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        connector: ProductionC1RouteConnectorMaterial,
        securityContextDigest: String,
        selectedPathReceiptDigest: String,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64
    ) throws {
        for digest in [
            planId, pairAuthorityDigest, pairBindingDigest, clientIdentityFingerprint,
            runtimeIdentityFingerprint, securityContextDigest, selectedPathReceiptDigest,
        ] { try c1ValidateDigest(digest) }
        guard pairEpoch > 0,
              generation > 0,
              clientIdentityFingerprint != runtimeIdentityFingerprint,
              connector.kind == kind,
              connector.pathReceiptDigest == selectedPathReceiptDigest,
              notBeforeMs < expiresAtMs else {
            throw ProductionC1Error.invalidValue
        }
        self.planId = planId
        self.kind = kind
        self.pairAuthorityDigest = pairAuthorityDigest
        self.pairBindingDigest = pairBindingDigest
        self.pairEpoch = pairEpoch
        self.generation = generation
        self.clientIdentityFingerprint = clientIdentityFingerprint
        self.runtimeIdentityFingerprint = runtimeIdentityFingerprint
        self.connector = connector
        self.securityContextDigest = securityContextDigest
        self.selectedPathReceiptDigest = selectedPathReceiptDigest
        self.notBeforeMs = notBeforeMs
        self.expiresAtMs = expiresAtMs
        guard try canonicalBytes().count <= ProductionC1Contract.maximumRoutePlanBytes else {
            throw ProductionC1Error.limitExceeded
        }
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try C1TLV.decode(
            data,
            objectType: ProductionC1Contract.routePlanObjectType,
            fieldCount: 15,
            maximumBytes: ProductionC1Contract.maximumRoutePlanBytes
        )
        guard try c1Text(fields[0]) == ProductionC1Contract.suite,
              try c1UInt64(fields[2]) == Self.revision,
              let kind = ProductionC1RouteKind(rawValue: try c1Text(fields[3])) else {
            throw ProductionC1Error.invalidValue
        }
        try self.init(
            planId: c1Text(fields[1]),
            kind: kind,
            pairAuthorityDigest: c1Text(fields[4]),
            pairBindingDigest: c1Text(fields[5]),
            pairEpoch: c1UInt64(fields[6]),
            generation: c1UInt64(fields[7]),
            clientIdentityFingerprint: c1Text(fields[8]),
            runtimeIdentityFingerprint: c1Text(fields[9]),
            connector: ProductionC1RouteConnectorMaterial(canonicalBytes: fields[10]),
            securityContextDigest: c1Text(fields[11]),
            selectedPathReceiptDigest: c1Text(fields[12]),
            notBeforeMs: c1UInt64(fields[13]),
            expiresAtMs: c1UInt64(fields[14])
        )
        guard try canonicalBytes() == data else { throw ProductionC1Error.malformedCanonical }
    }

    public func canonicalBytes() throws -> Data {
        C1TLV.encode(
            objectType: ProductionC1Contract.routePlanObjectType,
            fields: [
                c1ASCII(ProductionC1Contract.suite),
                c1ASCII(planId),
                c1BE(Self.revision),
                c1ASCII(kind.rawValue),
                c1ASCII(pairAuthorityDigest),
                c1ASCII(pairBindingDigest),
                c1BE(pairEpoch),
                c1BE(generation),
                c1ASCII(clientIdentityFingerprint),
                c1ASCII(runtimeIdentityFingerprint),
                try connector.canonicalBytes(),
                c1ASCII(securityContextDigest),
                c1ASCII(selectedPathReceiptDigest),
                c1BE(notBeforeMs),
                c1BE(expiresAtMs),
            ]
        )
    }

    public func digestHex() throws -> String { c1DigestHex(try canonicalBytes()) }
}

public struct ProductionC1RouteCapability: Equatable, Sendable {
    public let serviceIdDigest: String
    public let keysetVersion: UInt64
    public let signingKeyId: String
    public let capabilityId: String
    public let issuedAtMs: UInt64
    public let notBeforeMs: UInt64
    public let expiresAtMs: UInt64
    public let pairAuthorityDigest: String
    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let clientIdentityFingerprint: String
    public let runtimeIdentityFingerprint: String
    public let generation: UInt64
    public let serviceConfigVersion: UInt64
    public let revocationCounter: UInt64
    public let protocolFloor: UInt32
    public let kind: ProductionC1RouteKind
    public let routePlanClaimsDigest: String
    public let maxUses: UInt32
    public let serviceSignature: Data

    private init(
        serviceIdDigest: String,
        keysetVersion: UInt64,
        signingKeyId: String,
        capabilityId: String,
        issuedAtMs: UInt64,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        pairAuthorityDigest: String,
        pairBindingDigest: String,
        pairEpoch: UInt64,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        generation: UInt64,
        serviceConfigVersion: UInt64,
        revocationCounter: UInt64,
        protocolFloor: UInt32,
        kind: ProductionC1RouteKind,
        routePlanClaimsDigest: String,
        maxUses: UInt32,
        serviceSignature: Data,
        validateSignatureEncoding: Bool
    ) throws {
        for digest in [
            serviceIdDigest, signingKeyId, capabilityId, pairAuthorityDigest,
            pairBindingDigest, clientIdentityFingerprint, runtimeIdentityFingerprint,
            routePlanClaimsDigest,
        ] { try c1ValidateDigest(digest) }
        guard keysetVersion > 0,
              issuedAtMs <= notBeforeMs,
              notBeforeMs < expiresAtMs,
              pairEpoch > 0,
              generation > 0,
              serviceConfigVersion > 0,
              protocolFloor > 0,
              maxUses == 1,
              clientIdentityFingerprint != runtimeIdentityFingerprint else {
            throw ProductionC1Error.invalidValue
        }
        if validateSignatureEncoding { try c1ValidateCanonicalLowS(serviceSignature) }
        self.serviceIdDigest = serviceIdDigest
        self.keysetVersion = keysetVersion
        self.signingKeyId = signingKeyId
        self.capabilityId = capabilityId
        self.issuedAtMs = issuedAtMs
        self.notBeforeMs = notBeforeMs
        self.expiresAtMs = expiresAtMs
        self.pairAuthorityDigest = pairAuthorityDigest
        self.pairBindingDigest = pairBindingDigest
        self.pairEpoch = pairEpoch
        self.clientIdentityFingerprint = clientIdentityFingerprint
        self.runtimeIdentityFingerprint = runtimeIdentityFingerprint
        self.generation = generation
        self.serviceConfigVersion = serviceConfigVersion
        self.revocationCounter = revocationCounter
        self.protocolFloor = protocolFloor
        self.kind = kind
        self.routePlanClaimsDigest = routePlanClaimsDigest
        self.maxUses = maxUses
        self.serviceSignature = serviceSignature
        guard try canonicalBytes().count <= ProductionC1Contract.maximumRouteCapabilityBytes else {
            throw ProductionC1Error.limitExceeded
        }
    }

    public static func signed(
        serviceIdDigest: String,
        keysetVersion: UInt64,
        capabilityId: String,
        issuedAtMs: UInt64,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        authority: ProductionPairAuthorityState,
        kind: ProductionC1RouteKind,
        routePlanClaimsDigest: String,
        using signingKey: P256.Signing.PrivateKey
    ) throws -> Self {
        let signingKeyId = c1KeyId(signingKey.publicKey)
        let authorityDigest = try authority.digestHex()
        let unsigned = try Self(
            serviceIdDigest: serviceIdDigest,
            keysetVersion: keysetVersion,
            signingKeyId: signingKeyId,
            capabilityId: capabilityId,
            issuedAtMs: issuedAtMs,
            notBeforeMs: notBeforeMs,
            expiresAtMs: expiresAtMs,
            pairAuthorityDigest: authorityDigest,
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            revocationCounter: authority.revocationCounter,
            protocolFloor: authority.protocolFloor,
            kind: kind,
            routePlanClaimsDigest: routePlanClaimsDigest,
            maxUses: 1,
            serviceSignature: Data(),
            validateSignatureEncoding: false
        )
        return try Self(
            serviceIdDigest: serviceIdDigest,
            keysetVersion: keysetVersion,
            signingKeyId: signingKeyId,
            capabilityId: capabilityId,
            issuedAtMs: issuedAtMs,
            notBeforeMs: notBeforeMs,
            expiresAtMs: expiresAtMs,
            pairAuthorityDigest: authorityDigest,
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            revocationCounter: authority.revocationCounter,
            protocolFloor: authority.protocolFloor,
            kind: kind,
            routePlanClaimsDigest: routePlanClaimsDigest,
            maxUses: 1,
            serviceSignature: c1Sign(unsigned.signingTranscript, using: signingKey),
            validateSignatureEncoding: true
        )
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try C1TLV.decode(
            data,
            objectType: ProductionC1Contract.routeCapabilityObjectType,
            fieldCount: 22,
            maximumBytes: ProductionC1Contract.maximumRouteCapabilityBytes
        )
        guard try c1Text(fields[0]) == ProductionC1Contract.suite,
              let kind = ProductionC1RouteKind(rawValue: try c1Text(fields[17])),
              try c1Text(fields[20]) == ProductionC1Contract.signatureAlgorithm else {
            throw ProductionC1Error.invalidValue
        }
        try self.init(
            serviceIdDigest: c1Text(fields[1]),
            keysetVersion: c1UInt64(fields[2]),
            signingKeyId: c1Text(fields[3]),
            capabilityId: c1Text(fields[4]),
            issuedAtMs: c1UInt64(fields[5]),
            notBeforeMs: c1UInt64(fields[6]),
            expiresAtMs: c1UInt64(fields[7]),
            pairAuthorityDigest: c1Text(fields[8]),
            pairBindingDigest: c1Text(fields[9]),
            pairEpoch: c1UInt64(fields[10]),
            clientIdentityFingerprint: c1Text(fields[11]),
            runtimeIdentityFingerprint: c1Text(fields[12]),
            generation: c1UInt64(fields[13]),
            serviceConfigVersion: c1UInt64(fields[14]),
            revocationCounter: c1UInt64(fields[15]),
            protocolFloor: c1UInt32(fields[16]),
            kind: kind,
            routePlanClaimsDigest: c1Text(fields[18]),
            maxUses: c1UInt32(fields[19]),
            serviceSignature: fields[21],
            validateSignatureEncoding: true
        )
        guard try canonicalBytes() == data else { throw ProductionC1Error.malformedCanonical }
    }

    public func canonicalBytes() throws -> Data {
        C1TLV.encode(
            objectType: ProductionC1Contract.routeCapabilityObjectType,
            fields: claimsFields + [serviceSignature]
        )
    }

    public func digestHex() throws -> String { c1DigestHex(try canonicalBytes()) }

    fileprivate var signingTranscript: Data {
        c1SignatureTranscript(
            domain: "AetherLink G1a-C route-capability service signature v1",
            claims: C1TLV.encode(
                objectType: ProductionC1Contract.routeCapabilityObjectType,
                fields: claimsFields
            )
        )
    }

    private var claimsFields: [Data] {
        [
            c1ASCII(ProductionC1Contract.suite), c1ASCII(serviceIdDigest),
            c1BE(keysetVersion), c1ASCII(signingKeyId), c1ASCII(capabilityId),
            c1BE(issuedAtMs), c1BE(notBeforeMs), c1BE(expiresAtMs),
            c1ASCII(pairAuthorityDigest), c1ASCII(pairBindingDigest), c1BE(pairEpoch),
            c1ASCII(clientIdentityFingerprint), c1ASCII(runtimeIdentityFingerprint),
            c1BE(generation), c1BE(serviceConfigVersion), c1BE(revocationCounter),
            c1BE(protocolFloor), c1ASCII(kind.rawValue), c1ASCII(routePlanClaimsDigest),
            c1BE(maxUses), c1ASCII(ProductionC1Contract.signatureAlgorithm),
        ]
    }
}

public struct VerifiedProductionC1RouteCapability: Equatable, Sendable {
    public let capability: ProductionC1RouteCapability

    fileprivate init(_ capability: ProductionC1RouteCapability) { self.capability = capability }
}

public struct VerifiedProductionC1RoutePlan: Equatable, Sendable {
    public let claims: ProductionC1RoutePlanClaims
    public let capability: ProductionC1RouteCapability
    public let securityContext: ProductionC1PreauthorizationSessionContext
    public let authorityDigest: String
    public let capabilityDigest: String
    public let claimsDigest: String
    fileprivate let verifiedKeyset: VerifiedProductionC1ServiceKeyset

    public var kind: ProductionC1RouteKind { claims.kind }
    public var pairBindingDigest: String { claims.pairBindingDigest }
    public var pairEpoch: UInt64 { claims.pairEpoch }
    public var clientIdentityFingerprint: String { claims.clientIdentityFingerprint }
    public var runtimeIdentityFingerprint: String { claims.runtimeIdentityFingerprint }
    public var generation: UInt64 { claims.generation }
    public var connectorMaterial: ProductionC1RouteConnectorMaterial { claims.connector }

    fileprivate init(
        claims: ProductionC1RoutePlanClaims,
        capability: ProductionC1RouteCapability,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authorityDigest: String,
        capabilityDigest: String,
        claimsDigest: String,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset
    ) {
        self.claims = claims
        self.capability = capability
        self.securityContext = securityContext
        self.authorityDigest = authorityDigest
        self.capabilityDigest = capabilityDigest
        self.claimsDigest = claimsDigest
        self.verifiedKeyset = verifiedKeyset
    }
}

public struct ProductionC1RouteAuthorization: Equatable, Sendable {
    public let kind: ProductionC1RouteKind
    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let generation: UInt64
    public let pairAuthorityDigest: String
    public let routeCapabilityDigest: String
    public let routePlanClaimsDigest: String
    public let selectedPathReceiptDigest: String
    public let serviceIdDigest: String
    public let keysetVersion: UInt64

    fileprivate init(verifiedPlan: VerifiedProductionC1RoutePlan) {
        kind = verifiedPlan.kind
        pairBindingDigest = verifiedPlan.pairBindingDigest
        pairEpoch = verifiedPlan.pairEpoch
        generation = verifiedPlan.generation
        pairAuthorityDigest = verifiedPlan.authorityDigest
        routeCapabilityDigest = verifiedPlan.capabilityDigest
        routePlanClaimsDigest = verifiedPlan.claimsDigest
        selectedPathReceiptDigest = verifiedPlan.claims.selectedPathReceiptDigest
        serviceIdDigest = verifiedPlan.capability.serviceIdDigest
        keysetVersion = verifiedPlan.capability.keysetVersion
    }

    public init(canonicalBytes data: Data) throws {
        guard let kind = ProductionC1RouteKind.allCases.first(where: {
            $0.authorizationObjectType == data.dropFirst(4).first
        }) else { throw ProductionC1Error.malformedCanonical }
        let fields = try C1TLV.decode(
            data,
            objectType: kind.authorizationObjectType,
            fieldCount: 10,
            maximumBytes: ProductionC1Contract.maximumRouteAuthorizationBytes
        )
        guard try c1Text(fields[0]) == ProductionC1Contract.suite else {
            throw ProductionC1Error.invalidValue
        }
        self.kind = kind
        pairBindingDigest = try c1Text(fields[1])
        pairEpoch = try c1UInt64(fields[2])
        generation = try c1UInt64(fields[3])
        pairAuthorityDigest = try c1Text(fields[4])
        routeCapabilityDigest = try c1Text(fields[5])
        routePlanClaimsDigest = try c1Text(fields[6])
        selectedPathReceiptDigest = try c1Text(fields[7])
        serviceIdDigest = try c1Text(fields[8])
        keysetVersion = try c1UInt64(fields[9])
        for digest in [pairBindingDigest, pairAuthorityDigest, routeCapabilityDigest,
                       routePlanClaimsDigest, selectedPathReceiptDigest, serviceIdDigest] {
            try c1ValidateDigest(digest)
        }
        guard pairEpoch > 0, generation > 0, keysetVersion > 0,
              try canonicalBytes() == data else {
            throw ProductionC1Error.malformedCanonical
        }
    }

    public func canonicalBytes() throws -> Data {
        C1TLV.encode(
            objectType: kind.authorizationObjectType,
            fields: [
                c1ASCII(ProductionC1Contract.suite), c1ASCII(pairBindingDigest),
                c1BE(pairEpoch), c1BE(generation), c1ASCII(pairAuthorityDigest),
                c1ASCII(routeCapabilityDigest), c1ASCII(routePlanClaimsDigest),
                c1ASCII(selectedPathReceiptDigest), c1ASCII(serviceIdDigest),
                c1BE(keysetVersion),
            ]
        )
    }

    public func digestHex() throws -> String { c1DigestHex(try canonicalBytes()) }
}

public struct VerifiedProductionC1RouteAuthorization: Equatable, Sendable {
    public let authorization: ProductionC1RouteAuthorization
    public let canonicalBytes: Data
    public let digestHex: String

    public var kind: ProductionC1RouteKind { authorization.kind }
    public var pairBindingDigest: String { authorization.pairBindingDigest }
    public var pairEpoch: UInt64 { authorization.pairEpoch }
    public var generation: UInt64 { authorization.generation }

    fileprivate init(_ authorization: ProductionC1RouteAuthorization) throws {
        self.authorization = authorization
        canonicalBytes = try authorization.canonicalBytes()
        digestHex = try authorization.digestHex()
    }
}

public enum ProductionC1RouteCommitments {
    public static let maximumRouteHandleBytes = 512
    public static let maximumNonceBytes = 512
    public static let minimumSecretBytes = 32
    public static let maximumSecretBytes = 512

    public static func routeHandleDigest(
        kind: ProductionC1RouteKind,
        routeHandle: String
    ) throws -> String {
        let bytes = try c1BoundedUTF8(
            routeHandle,
            maximum: maximumRouteHandleBytes
        )
        var claims = c1BE(UInt32(bytes.count))
        claims.append(bytes)
        return c1DigestHex(c1SignatureTranscript(
            domain: "AetherLink G1a-C route-handle commitment \(kind.rawValue) v1",
            claims: claims
        ))
    }

    public static func credentialCommitmentDigest(
        kind: ProductionC1RouteKind,
        routeHandle: String,
        nonce: String,
        secret: Data
    ) throws -> String {
        let handleBytes = try c1BoundedUTF8(
            routeHandle,
            maximum: maximumRouteHandleBytes
        )
        let nonceBytes = try c1BoundedUTF8(nonce, maximum: maximumNonceBytes)
        guard secret.count >= minimumSecretBytes, secret.count <= maximumSecretBytes else {
            throw ProductionC1Error.limitExceeded
        }
        var claims = c1BE(UInt32(handleBytes.count))
        claims.append(handleBytes)
        claims.append(c1BE(UInt32(nonceBytes.count)))
        claims.append(nonceBytes)
        claims.append(c1BE(UInt32(secret.count)))
        claims.append(secret)
        return c1DigestHex(c1SignatureTranscript(
            domain: "AetherLink G1a-C credential commitment \(kind.rawValue) v1",
            claims: claims
        ))
    }
}

public struct VerifiedProductionC1ConnectorInput: Equatable, @unchecked Sendable {
    public let routeHandle: String
    public let nonce: String
    public let secret: Data
    public let connector: ProductionC1RouteConnectorMaterial
    public let commitmentDigest: String

    fileprivate init(
        routeHandle: String,
        nonce: String,
        secret: Data,
        connector: ProductionC1RouteConnectorMaterial,
        commitmentDigest: String
    ) {
        self.routeHandle = routeHandle
        self.nonce = nonce
        self.secret = secret
        self.connector = connector
        self.commitmentDigest = commitmentDigest
    }
}

public struct VerifiedProductionC1TranscriptBinding: Equatable, Sendable {
    public let transcript: ProductionSecureSessionTranscript
    public let authorization: VerifiedProductionC1RouteAuthorization
    public let plan: VerifiedProductionC1RoutePlan
    public let connectorInput: VerifiedProductionC1ConnectorInput
    public let securityContext: ProductionC1PreauthorizationSessionContext

    fileprivate init(
        transcript: ProductionSecureSessionTranscript,
        authorization: VerifiedProductionC1RouteAuthorization,
        plan: VerifiedProductionC1RoutePlan,
        connectorInput: VerifiedProductionC1ConnectorInput,
        securityContext: ProductionC1PreauthorizationSessionContext
    ) {
        self.transcript = transcript
        self.authorization = authorization
        self.plan = plan
        self.connectorInput = connectorInput
        self.securityContext = securityContext
    }
}

package struct ProductionC1AdmissionPreparation: Equatable, Sendable {
    package let snapshot: ProductionPairStateSnapshot
    package let bindingDigest: String
    package let pairAuthorityDigest: String
    package let sessionId: String
    package let transcriptDigest: String
    package let routeAuthorizationDigest: String
    package let routeCapabilityDigest: String
    package let routePlanClaimsDigest: String
    package let connectorInputCommitmentDigest: String
    package let previousPairSnapshotDigest: String
    package let pairSnapshotDigest: String
    package let effectiveNotBeforeMs: UInt64
    package let expiresAtMs: UInt64
}

package enum ProductionC1PairStateAdmission {
    package static func prepare(
        binding: VerifiedProductionC1TranscriptBinding,
        to snapshot: ProductionPairStateSnapshot,
        nowMs: UInt64
    ) throws -> ProductionC1AdmissionPreparation {
        guard binding.plan.kind != .p2pDirect else {
            throw ProductionC1Error.routeMismatch
        }
        try c1ValidateVerifiedRoutePlanUse(binding.plan, nowMs: nowMs)
        let transcript = binding.transcript
        let authorization = binding.authorization.authorization
        let authority = snapshot.authority
        guard authority.status == .active,
              authorization.pairAuthorityDigest == (try authority.digestHex()),
              transcript.pairBindingDigest == authority.pairBindingDigest,
              transcript.pairEpoch == authority.pairEpoch,
              transcript.clientIdentityFingerprint == authority.clientIdentityFingerprint,
              transcript.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint,
              transcript.generation == authority.generation,
              transcript.serviceConfigVersion == authority.serviceConfigVersion,
              transcript.keysetVersion == authority.keysetVersion,
              transcript.revocationCounter == authority.revocationCounter else {
            throw ProductionC1Error.stateMismatch
        }
        let transcriptDigest = transcript.digestHex
        guard !snapshot.consumedEntries.contains(where: {
            $0.sessionId == transcript.sessionId || $0.transcriptDigest == transcriptDigest
        }) else {
            throw ProductionPairStateError.replay
        }
        guard snapshot.consumedEntries.count < ProductionPairStateContract.maxConsumedEntries else {
            throw ProductionPairStateError.replayCapacityExceeded
        }
        guard snapshot.localRevision < UInt64.max else {
            throw ProductionPairStateError.limitExceeded
        }
        let updated = try ProductionPairStateSnapshot(
            authority: authority,
            localRevision: snapshot.localRevision + 1,
            consumedEntries: snapshot.consumedEntries + [
                try ProductionPairConsumedSession(
                    sessionId: transcript.sessionId,
                    transcriptDigest: transcriptDigest
                ),
            ],
            transitionHistory: snapshot.transitionHistory
        )
        var permitClaims = transcript.digest
        permitClaims.append(binding.authorization.canonicalBytes)
        permitClaims.append(try binding.plan.claims.canonicalBytes())
        permitClaims.append(try binding.plan.connectorMaterial.canonicalBytes())
        permitClaims.append(try binding.plan.capability.canonicalBytes())
        permitClaims.append(binding.securityContext.canonicalBytes())
        permitClaims.append(c1ForceDecodeDigest(binding.connectorInput.commitmentDigest))
        permitClaims.append(try updated.digest())
        let routeKey = try c1DelegatedKey(
            id: binding.plan.capability.signingKeyId,
            purpose: .routeCapability,
            in: binding.plan.verifiedKeyset,
            nowMs: nowMs
        )
        let effectiveNotBeforeMs = max(
            binding.plan.verifiedKeyset.keyset.issuedAtMs,
            max(
                routeKey.notBeforeMs,
                max(binding.plan.capability.notBeforeMs, binding.plan.claims.notBeforeMs)
            )
        )
        let routeKeyExpiresAtMs = min(
            routeKey.expiresAtMs,
            routeKey.revokedAtMs ?? routeKey.expiresAtMs
        )
        let expiresAtMs = min(
            binding.plan.verifiedKeyset.keyset.expiresAtMs,
            min(
                routeKeyExpiresAtMs,
                min(binding.plan.capability.expiresAtMs, binding.plan.claims.expiresAtMs)
            )
        )
        guard effectiveNotBeforeMs < expiresAtMs else {
            throw ProductionC1Error.invalidValue
        }
        return ProductionC1AdmissionPreparation(
            snapshot: updated,
            bindingDigest: c1DigestHex(c1SignatureTranscript(
                domain: "AetherLink G1a-C durable admission permit v1",
                claims: permitClaims
            )),
            pairAuthorityDigest: authorization.pairAuthorityDigest,
            sessionId: transcript.sessionId,
            transcriptDigest: transcriptDigest,
            routeAuthorizationDigest: binding.authorization.digestHex,
            routeCapabilityDigest: binding.plan.capabilityDigest,
            routePlanClaimsDigest: binding.plan.claimsDigest,
            connectorInputCommitmentDigest: binding.connectorInput.commitmentDigest,
            previousPairSnapshotDigest: try snapshot.digestHex(),
            pairSnapshotDigest: try updated.digestHex(),
            effectiveNotBeforeMs: effectiveNotBeforeMs,
            expiresAtMs: expiresAtMs
        )
    }
}

public enum ProductionC1Verifier {
    public static func verifyServiceKeyset(
        _ keyset: ProductionC1ServiceKeyset,
        expectedServiceIdDigest: String,
        pinnedRootPublicKey: P256.Signing.PublicKey,
        minimumAcceptedKeysetVersion: UInt64,
        previous: VerifiedProductionC1ServiceKeyset? = nil,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1ServiceKeyset {
        try c1ValidateDigest(expectedServiceIdDigest)
        guard minimumAcceptedKeysetVersion > 0,
              keyset.keysetVersion >= minimumAcceptedKeysetVersion else {
            throw ProductionC1Error.keysetRollback
        }
        guard keyset.serviceIdDigest == expectedServiceIdDigest else {
            throw ProductionC1Error.serviceMismatch
        }
        guard keyset.rootKeyId == c1KeyId(pinnedRootPublicKey) else {
            throw ProductionC1Error.untrustedRoot
        }
        try c1ValidateWindow(
            issuedAtMs: keyset.issuedAtMs,
            notBeforeMs: keyset.issuedAtMs,
            expiresAtMs: keyset.expiresAtMs,
            maximumLifetimeMs: ProductionC1Contract.maximumKeysetLifetimeMs,
            nowMs: nowMs
        )
        if let previous {
            guard previous.keyset.serviceIdDigest == keyset.serviceIdDigest,
                  previous.keyset.rootKeyId == keyset.rootKeyId else {
                throw ProductionC1Error.serviceMismatch
            }
            guard previous.keyset.keysetVersion < UInt64.max,
                  keyset.keysetVersion == previous.keyset.keysetVersion + 1 else {
                throw keyset.keysetVersion <= previous.keyset.keysetVersion
                    ? ProductionC1Error.keysetRollback
                    : ProductionC1Error.keysetGap
            }
            guard keyset.previousKeysetDigest == (try previous.keyset.digestHex()) else {
                throw ProductionC1Error.previousKeysetMismatch
            }
        } else {
            guard (keyset.keysetVersion == 1 && keyset.previousKeysetDigest == nil) ||
                    (keyset.keysetVersion > 1 && keyset.previousKeysetDigest != nil) else {
                throw ProductionC1Error.previousKeysetMismatch
            }
        }
        try c1Verify(
            signature: keyset.rootSignature,
            transcript: keyset.signingTranscript,
            publicKey: pinnedRootPublicKey
        )
        return VerifiedProductionC1ServiceKeyset(keyset)
    }

    public static func verifyPairStatus(
        _ status: ProductionC1PairStatus,
        expectedServiceIdDigest: String,
        expectedRequesterRole: ProductionC1RequesterRole,
        expectedRequestNonce: String,
        current: ProductionPairStateSnapshot?,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1PairStatus {
        try c1ValidateDigest(expectedRequestNonce)
        guard status.serviceIdDigest == expectedServiceIdDigest,
              status.serviceIdDigest == verifiedKeyset.keyset.serviceIdDigest else {
            throw ProductionC1Error.serviceMismatch
        }
        guard status.keysetVersion == verifiedKeyset.keyset.keysetVersion,
              status.authority.keysetVersion == status.keysetVersion else {
            throw ProductionC1Error.keysetRollback
        }
        guard status.requesterRole == expectedRequesterRole,
              status.requestNonce == expectedRequestNonce else {
            throw ProductionC1Error.stateMismatch
        }
        try c1ValidateVerifiedKeysetUse(verifiedKeyset, nowMs: nowMs)
        try c1ValidateWindow(
            issuedAtMs: status.issuedAtMs,
            notBeforeMs: status.issuedAtMs,
            expiresAtMs: status.expiresAtMs,
            maximumLifetimeMs: ProductionC1Contract.maximumStatusLifetimeMs,
            nowMs: nowMs
        )
        let signingKey = try c1DelegatedKey(
            id: status.signingKeyId,
            purpose: .pairStatus,
            in: verifiedKeyset,
            nowMs: nowMs
        )
        try c1Verify(
            signature: status.serviceSignature,
            transcript: status.signingTranscript,
            publicKey: try c1PublicKey(x963: signingKey.publicKeyX963)
        )
        guard status.authority.acceptedReceiptDigest == status.authorizationEvidenceDigest else {
            throw ProductionC1Error.evidenceMismatch
        }
        let remoteSequence = try c1TransitionSequence(
            history: status.transitionHistory,
            authority: status.authority
        )
        guard UInt64(remoteSequence.count) == status.authority.authorityRevision else {
            throw ProductionC1Error.historyMismatch
        }
        guard c1TransitionKindMatchesState(status) else {
            throw ProductionC1Error.stateMismatch
        }
        if let current {
            let localSequence = try c1TransitionSequence(
                history: current.transitionHistory,
                authority: current.authority
            )
            guard localSequence.count <= remoteSequence.count,
                  Array(remoteSequence.prefix(localSequence.count)) == localSequence else {
                throw ProductionC1Error.historyMismatch
            }
            if status.authority.authorityRevision == current.authority.authorityRevision {
                guard status.authority == current.authority,
                      status.transitionHistory == current.transitionHistory else {
                    throw ProductionC1Error.stateMismatch
                }
            } else {
                try c1ValidateAuthorityAdvance(
                    previous: current.authority,
                    next: status.authority,
                    transitionKind: status.transitionKind
                )
                if status.authority.authorityRevision == current.authority.authorityRevision + 1 {
                guard status.previousAuthorityDigest == (try current.authority.digestHex()) else {
                    throw ProductionC1Error.previousKeysetMismatch
                }
                } else {
                    guard status.previousAuthorityDigest != nil else {
                        throw ProductionC1Error.stateMismatch
                    }
                }
            }
        } else {
            guard status.transitionKind == .genesis,
                  status.previousAuthorityDigest == nil,
                  status.authority.authorityRevision == 1,
                  status.authority.status == .active,
                  status.transitionHistory.isEmpty else {
                throw ProductionC1Error.stateMismatch
            }
        }
        return VerifiedProductionC1PairStatus(status, verifiedKeyset: verifiedKeyset)
    }

    public static func verifyFreshPairProof(
        _ proof: ProductionC1FreshPairProof,
        acceptedBy verifiedStatus: VerifiedProductionC1PairStatus,
        current: ProductionPairStateSnapshot,
        currentCommitments: ProductionC1CurrentRecoveryCommitments,
        survivorPublicKey: P256.Signing.PublicKey,
        replacementPublicKey: P256.Signing.PublicKey,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1FreshPairTransition {
        let previous = current.authority
        let status = verifiedStatus.status
        try c1ValidateVerifiedPairStatusUse(verifiedStatus, nowMs: nowMs)
        guard previous.pairEpoch < UInt64.max,
              previous.authorityRevision < UInt64.max else {
            throw ProductionC1Error.invalidFreshPair
        }
        try c1ValidateWindow(
            issuedAtMs: proof.issuedAtMs,
            notBeforeMs: proof.issuedAtMs,
            expiresAtMs: proof.expiresAtMs,
            maximumLifetimeMs: ProductionC1Contract.maximumFreshPairLifetimeMs,
            nowMs: nowMs
        )
        guard status.transitionKind == .freshPair,
              status.evidenceKind == .dualSignedFreshPair,
              status.previousAuthorityDigest == (try previous.digestHex()),
              proof.previousAuthorityDigest == (try previous.digestHex()),
              proof.previousPairBindingDigest == previous.pairBindingDigest,
              proof.nextPairBindingDigest == previous.pairBindingDigest,
              currentCommitments.pairBindingDigest == previous.pairBindingDigest,
              proof.previousEndpointTrafficSecretCommitment ==
                  currentCommitments.endpointTrafficSecretCommitment,
              proof.previousRouteTokenSeedCommitment ==
                  currentCommitments.routeTokenSeedCommitment,
              proof.previousEndpointTrafficSecretReuseDigest ==
                  currentCommitments.endpointTrafficSecretReuseDigest,
              proof.previousRouteTokenSeedReuseDigest ==
                  currentCommitments.routeTokenSeedReuseDigest,
              proof.nextEndpointTrafficSecretCommitment !=
                  currentCommitments.endpointTrafficSecretCommitment,
              proof.nextRouteTokenSeedCommitment != currentCommitments.routeTokenSeedCommitment,
              proof.nextEndpointTrafficSecretReuseDigest !=
                  currentCommitments.endpointTrafficSecretReuseDigest,
              proof.nextRouteTokenSeedReuseDigest != currentCommitments.routeTokenSeedReuseDigest,
              proof.nextEndpointTrafficSecretReuseDigest != proof.nextRouteTokenSeedReuseDigest,
              proof.previousPairEpoch == previous.pairEpoch,
              proof.previousClientIdentityFingerprint == previous.clientIdentityFingerprint,
              proof.previousRuntimeIdentityFingerprint == previous.runtimeIdentityFingerprint,
              proof.nextPairEpoch == previous.pairEpoch + 1,
              proof.nextGeneration > previous.generation,
              proof.nextServiceConfigVersion >= previous.serviceConfigVersion,
              proof.nextKeysetVersion >= previous.keysetVersion,
              proof.nextRevocationCounter >= previous.revocationCounter,
              proof.nextProtocolFloor >= previous.protocolFloor,
              proof.nextAuthorityRevision == previous.authorityRevision + 1,
              !current.transitionHistory.contains(where: { $0.transitionId == proof.transitionId }),
              proof.transitionId != previous.transitionId else {
            throw ProductionC1Error.invalidFreshPair
        }
        let survivorFingerprint = c1KeyId(survivorPublicKey)
        let replacementFingerprint = c1KeyId(replacementPublicKey)
        switch proof.replacementRole {
        case .client:
            guard proof.nextClientIdentityFingerprint == replacementFingerprint,
                  proof.previousClientIdentityFingerprint != replacementFingerprint,
                  proof.previousRuntimeIdentityFingerprint == survivorFingerprint,
                  proof.nextRuntimeIdentityFingerprint == survivorFingerprint else {
                throw ProductionC1Error.invalidFreshPair
            }
        case .runtime:
            guard proof.nextRuntimeIdentityFingerprint == replacementFingerprint,
                  proof.previousRuntimeIdentityFingerprint != replacementFingerprint,
                  proof.previousClientIdentityFingerprint == survivorFingerprint,
                  proof.nextClientIdentityFingerprint == survivorFingerprint else {
                throw ProductionC1Error.invalidFreshPair
            }
        }
        try c1Verify(
            signature: proof.survivorSignature,
            transcript: proof.survivorSigningTranscript,
            publicKey: survivorPublicKey
        )
        try c1Verify(
            signature: proof.replacementSignature,
            transcript: proof.replacementSigningTranscript,
            publicKey: replacementPublicKey
        )
        let proofDigest = try proof.digestHex()
        guard status.authorizationEvidenceDigest == proofDigest,
              status.authority.acceptedReceiptDigest == proofDigest else {
            throw ProductionC1Error.evidenceMismatch
        }
        let expectedNext = try ProductionPairAuthorityState(
            pairBindingDigest: proof.nextPairBindingDigest,
            pairEpoch: proof.nextPairEpoch,
            clientIdentityFingerprint: proof.nextClientIdentityFingerprint,
            runtimeIdentityFingerprint: proof.nextRuntimeIdentityFingerprint,
            generation: proof.nextGeneration,
            serviceConfigVersion: proof.nextServiceConfigVersion,
            keysetVersion: proof.nextKeysetVersion,
            revocationCounter: proof.nextRevocationCounter,
            protocolFloor: proof.nextProtocolFloor,
            status: .active,
            transitionId: proof.transitionId,
            transitionRequestDigest: proof.transitionRequestDigest,
            acceptedReceiptDigest: proofDigest,
            authorityRevision: proof.nextAuthorityRevision
        )
        guard status.authority == expectedNext else { throw ProductionC1Error.stateMismatch }
        guard current.transitionHistory.count < ProductionPairStateContract.maxTransitionHistoryEntries else {
            throw ProductionPairStateError.transitionHistoryCapacityExhausted
        }
        let expectedHistory = current.transitionHistory + [
            try ProductionPairTransitionHistoryEntry(
                transitionId: previous.transitionId,
                transitionRequestDigest: previous.transitionRequestDigest
            ),
        ]
        guard status.transitionHistory == expectedHistory else {
            throw ProductionC1Error.historyMismatch
        }
        guard current.localRevision < UInt64.max else {
            throw ProductionPairStateError.limitExceeded
        }
        let nextSnapshot = try ProductionPairStateSnapshot(
            authority: expectedNext,
            localRevision: current.localRevision + 1,
            consumedEntries: [],
            transitionHistory: expectedHistory
        )
        return VerifiedProductionC1FreshPairTransition(
            proof: proof,
            verifiedStatus: verifiedStatus,
            applyPreparation: ProductionC1FreshPairApplyPreparation(
                expectedPreviousAuthorityDigest: proof.previousAuthorityDigest,
                expectedPreviousSnapshotDigest: try current.digestHex(),
                nextAuthority: expectedNext,
                nextTransitionHistory: expectedHistory,
                nextSnapshot: nextSnapshot
            )
        )
    }

    public static func verifyRouteCapability(
        _ capability: ProductionC1RouteCapability,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1RouteCapability {
        guard authority.status == .active else { throw ProductionC1Error.stateMismatch }
        try c1ValidateVerifiedKeysetUse(verifiedKeyset, nowMs: nowMs)
        guard capability.serviceIdDigest == verifiedKeyset.keyset.serviceIdDigest else {
            throw ProductionC1Error.serviceMismatch
        }
        guard capability.keysetVersion == verifiedKeyset.keyset.keysetVersion,
              capability.keysetVersion == authority.keysetVersion else {
            throw ProductionC1Error.keysetRollback
        }
        try c1ValidateWindow(
            issuedAtMs: capability.issuedAtMs,
            notBeforeMs: capability.notBeforeMs,
            expiresAtMs: capability.expiresAtMs,
            maximumLifetimeMs: ProductionC1Contract.maximumRouteLifetimeMs,
            nowMs: nowMs
        )
        guard capability.pairAuthorityDigest == (try authority.digestHex()),
              capability.pairBindingDigest == authority.pairBindingDigest,
              capability.pairEpoch == authority.pairEpoch,
              capability.clientIdentityFingerprint == authority.clientIdentityFingerprint,
              capability.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint,
              capability.generation == authority.generation,
              capability.serviceConfigVersion == authority.serviceConfigVersion,
              capability.revocationCounter == authority.revocationCounter,
              capability.protocolFloor == authority.protocolFloor,
              capability.maxUses == 1 else {
            throw ProductionC1Error.stateMismatch
        }
        let signingKey = try c1DelegatedKey(
            id: capability.signingKeyId,
            purpose: .routeCapability,
            in: verifiedKeyset,
            nowMs: nowMs
        )
        try c1Verify(
            signature: capability.serviceSignature,
            transcript: capability.signingTranscript,
            publicKey: try c1PublicKey(x963: signingKey.publicKeyX963)
        )
        return VerifiedProductionC1RouteCapability(capability)
    }

    public static func verifyRoutePlan(
        claims: ProductionC1RoutePlanClaims,
        capability: ProductionC1RouteCapability,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1RoutePlan {
        guard claims.kind != .p2pDirect else { throw ProductionC1Error.routeMismatch }
        return try verifyRoutePlanCore(
            claims: claims,
            capability: capability,
            securityContext: securityContext,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            nowMs: nowMs
        )
    }

    // Module-internal provenance gate. Only the object-25 candidate verifier calls this.
    static func verifyCandidateP2PRoutePlanBase(
        claims: ProductionC1RoutePlanClaims,
        capability: ProductionC1RouteCapability,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1RoutePlan {
        guard claims.kind == .p2pDirect else { throw ProductionC1Error.routeMismatch }
        return try verifyRoutePlanCore(
            claims: claims,
            capability: capability,
            securityContext: securityContext,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            nowMs: nowMs
        )
    }

    private static func verifyRoutePlanCore(
        claims: ProductionC1RoutePlanClaims,
        capability: ProductionC1RouteCapability,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1RoutePlan {
        _ = try verifyRouteCapability(
            capability,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            nowMs: nowMs
        )
        try c1ValidateWindow(
            issuedAtMs: capability.issuedAtMs,
            notBeforeMs: claims.notBeforeMs,
            expiresAtMs: claims.expiresAtMs,
            maximumLifetimeMs: ProductionC1Contract.maximumRouteLifetimeMs,
            nowMs: nowMs
        )
        let claimsDigest = try claims.digestHex()
        let authorityDigest = try authority.digestHex()
        guard claimsDigest == capability.routePlanClaimsDigest,
              claims.securityContextDigest == securityContext.digestHex(),
              claims.kind == capability.kind,
              securityContext.routeKind == claims.kind,
              claims.pairAuthorityDigest == authorityDigest,
              claims.pairBindingDigest == authority.pairBindingDigest,
              claims.pairEpoch == authority.pairEpoch,
              claims.generation == authority.generation,
              claims.clientIdentityFingerprint == authority.clientIdentityFingerprint,
              claims.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint,
              securityContext.pairBindingDigest == authority.pairBindingDigest,
              securityContext.pairEpoch == authority.pairEpoch,
              securityContext.clientIdentityFingerprint == authority.clientIdentityFingerprint,
              securityContext.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint,
              securityContext.generation == authority.generation,
              securityContext.serviceConfigVersion == authority.serviceConfigVersion,
              securityContext.keysetVersion == authority.keysetVersion,
              securityContext.revocationCounter == authority.revocationCounter,
              ProductionSecureSessionTranscript.protocolVersion >= authority.protocolFloor,
              ProductionSecureSessionTranscript.minimumProtocolVersion >= authority.protocolFloor,
              claims.notBeforeMs >= capability.notBeforeMs,
              claims.expiresAtMs <= capability.expiresAtMs,
              claims.connector.pathReceiptDigest == claims.selectedPathReceiptDigest else {
            throw ProductionC1Error.routeMismatch
        }
        return try VerifiedProductionC1RoutePlan(
            claims: claims,
            capability: capability,
            securityContext: securityContext,
            authorityDigest: authorityDigest,
            capabilityDigest: capability.digestHex(),
            claimsDigest: claimsDigest,
            verifiedKeyset: verifiedKeyset
        )
    }

    public static func makeRouteAuthorization(
        for verifiedPlan: VerifiedProductionC1RoutePlan,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1RouteAuthorization {
        guard verifiedPlan.kind != .p2pDirect else { throw ProductionC1Error.routeMismatch }
        return try makeRouteAuthorizationCore(for: verifiedPlan, nowMs: nowMs)
    }

    static func makeCandidateP2PRouteAuthorizationBase(
        for verifiedPlan: VerifiedProductionC1RoutePlan,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1RouteAuthorization {
        guard verifiedPlan.kind == .p2pDirect else { throw ProductionC1Error.routeMismatch }
        return try makeRouteAuthorizationCore(for: verifiedPlan, nowMs: nowMs)
    }

    private static func makeRouteAuthorizationCore(
        for verifiedPlan: VerifiedProductionC1RoutePlan,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1RouteAuthorization {
        try c1ValidateVerifiedRoutePlanUse(verifiedPlan, nowMs: nowMs)
        return try VerifiedProductionC1RouteAuthorization(
            ProductionC1RouteAuthorization(verifiedPlan: verifiedPlan)
        )
    }

    public static func verifyConnectorInput(
        for verifiedPlan: VerifiedProductionC1RoutePlan,
        routeHandle: String,
        nonce: String,
        secret: Data,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1ConnectorInput {
        guard verifiedPlan.kind != .p2pDirect else { throw ProductionC1Error.routeMismatch }
        try c1ValidateVerifiedRoutePlanUse(verifiedPlan, nowMs: nowMs)
        let expectedHandle = try ProductionC1RouteCommitments.routeHandleDigest(
            kind: verifiedPlan.kind,
            routeHandle: routeHandle
        )
        let expectedCredential = try ProductionC1RouteCommitments.credentialCommitmentDigest(
            kind: verifiedPlan.kind,
            routeHandle: routeHandle,
            nonce: nonce,
            secret: secret
        )
        guard expectedHandle == verifiedPlan.connectorMaterial.routeHandleDigest,
              expectedCredential == verifiedPlan.connectorMaterial.credentialCommitmentDigest else {
            throw ProductionC1Error.routeMismatch
        }
        var inputClaims = try verifiedPlan.connectorMaterial.canonicalBytes()
        let handleBytes = try c1BoundedUTF8(
            routeHandle,
            maximum: ProductionC1RouteCommitments.maximumRouteHandleBytes
        )
        let nonceBytes = try c1BoundedUTF8(
            nonce,
            maximum: ProductionC1RouteCommitments.maximumNonceBytes
        )
        inputClaims.append(c1BE(UInt32(handleBytes.count)))
        inputClaims.append(handleBytes)
        inputClaims.append(c1BE(UInt32(nonceBytes.count)))
        inputClaims.append(nonceBytes)
        inputClaims.append(c1ForceDecodeDigest(expectedCredential))
        let inputCommitment = c1DigestHex(c1SignatureTranscript(
            domain: "AetherLink G1a-C verified connector-input commitment v1",
            claims: inputClaims
        ))
        return VerifiedProductionC1ConnectorInput(
            routeHandle: routeHandle,
            nonce: nonce,
            secret: secret,
            connector: verifiedPlan.connectorMaterial,
            commitmentDigest: inputCommitment
        )
    }

    public static func verifyTranscriptBinding(
        transcript: ProductionSecureSessionTranscript,
        authorization: VerifiedProductionC1RouteAuthorization,
        verifiedPlan: VerifiedProductionC1RoutePlan,
        connectorInput: VerifiedProductionC1ConnectorInput,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1TranscriptBinding {
        guard verifiedPlan.kind != .p2pDirect else { throw ProductionC1Error.routeMismatch }
        try c1ValidateVerifiedRoutePlanUse(verifiedPlan, nowMs: nowMs)
        let expectedContext = try ProductionC1PreauthorizationSessionContext(
            transcript: transcript
        )
        let expectedConnectorInput = try verifyConnectorInput(
            for: verifiedPlan,
            routeHandle: connectorInput.routeHandle,
            nonce: connectorInput.nonce,
            secret: connectorInput.secret,
            nowMs: nowMs
        )
        guard authority.status == .active,
              authorization.kind == verifiedPlan.kind,
              authorization.authorization.pairAuthorityDigest == verifiedPlan.authorityDigest,
              authorization.authorization.routeCapabilityDigest == verifiedPlan.capabilityDigest,
              authorization.authorization.routePlanClaimsDigest == verifiedPlan.claimsDigest,
              authorization.authorization.selectedPathReceiptDigest ==
                  verifiedPlan.claims.selectedPathReceiptDigest,
              connectorInput == expectedConnectorInput,
              expectedContext == verifiedPlan.securityContext,
              expectedContext.digestHex() == verifiedPlan.claims.securityContextDigest,
              transcript.routeKind == authorization.kind.transcriptKind,
              transcript.routeAuthDigest == authorization.digestHex,
              transcript.pairBindingDigest == authorization.pairBindingDigest,
              transcript.pairEpoch == authorization.pairEpoch,
              transcript.generation == authorization.generation,
              transcript.pairBindingDigest == authority.pairBindingDigest,
              transcript.pairEpoch == authority.pairEpoch,
              transcript.clientIdentityFingerprint == authority.clientIdentityFingerprint,
              transcript.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint,
              transcript.generation == authority.generation,
              transcript.serviceConfigVersion == authority.serviceConfigVersion,
              transcript.keysetVersion == authority.keysetVersion,
              transcript.revocationCounter == authority.revocationCounter,
              ProductionSecureSessionTranscript.protocolVersion >= authority.protocolFloor,
              ProductionSecureSessionTranscript.minimumProtocolVersion >= authority.protocolFloor else {
            throw ProductionC1Error.routeMismatch
        }
        return VerifiedProductionC1TranscriptBinding(
            transcript: transcript,
            authorization: authorization,
            plan: verifiedPlan,
            connectorInput: connectorInput,
            securityContext: expectedContext
        )
    }
}

private struct C1TLV {
    static let magic = Data("ALS1".utf8)
    static let version: UInt8 = 1

    static func encode(objectType: UInt8, fields: [Data]) -> Data {
        var output = magic
        output.append(objectType)
        output.append(version)
        for (index, value) in fields.enumerated() {
            output.append(UInt8(index + 1))
            output.append(c1BE(UInt32(value.count)))
            output.append(value)
        }
        return output
    }

    static func decode(
        _ data: Data,
        objectType: UInt8,
        fieldCount: Int,
        maximumBytes: Int
    ) throws -> [Data] {
        guard data.count <= maximumBytes else { throw ProductionC1Error.limitExceeded }
        guard fieldCount > 0, fieldCount <= Int(UInt8.max), data.count >= 6 else {
            throw ProductionC1Error.malformedCanonical
        }
        var cursor = C1Cursor(data)
        guard try cursor.read(4) == magic,
              try cursor.byte() == objectType,
              try cursor.byte() == version else {
            throw ProductionC1Error.malformedCanonical
        }
        var fields: [Data] = []
        for expected in 1...fieldCount {
            guard try cursor.byte() == UInt8(expected) else {
                throw ProductionC1Error.malformedCanonical
            }
            let length = try cursor.uint32()
            guard length <= UInt32(maximumBytes) else { throw ProductionC1Error.limitExceeded }
            fields.append(try cursor.read(Int(length)))
        }
        guard cursor.isAtEnd else { throw ProductionC1Error.malformedCanonical }
        return fields
    }
}

private struct C1Cursor {
    let data: Data
    var offset = 0

    init(_ data: Data) { self.data = data }
    var isAtEnd: Bool { offset == data.count }

    mutating func read(_ count: Int) throws -> Data {
        guard count >= 0, offset <= data.count, count <= data.count - offset else {
            throw ProductionC1Error.malformedCanonical
        }
        defer { offset += count }
        return data.subdata(in: offset..<(offset + count))
    }

    mutating func byte() throws -> UInt8 {
        guard offset < data.count else { throw ProductionC1Error.malformedCanonical }
        defer { offset += 1 }
        return data[offset]
    }

    mutating func uint32() throws -> UInt32 { try c1UInt32(read(4)) }
}

private func c1ASCII(_ value: String) -> Data { Data(value.utf8) }

private func c1Text(_ data: Data) throws -> String {
    guard data.allSatisfy({ $0 < 0x80 }), let value = String(data: data, encoding: .utf8) else {
        throw ProductionC1Error.malformedCanonical
    }
    return value
}

private func c1BE<T: FixedWidthInteger>(_ value: T) -> Data {
    var big = value.bigEndian
    return withUnsafeBytes(of: &big) { Data($0) }
}

private func c1UInt64(_ data: Data) throws -> UInt64 {
    guard data.count == 8 else { throw ProductionC1Error.malformedCanonical }
    return data.reduce(0) { ($0 << 8) | UInt64($1) }
}

private func c1UInt32(_ data: Data) throws -> UInt32 {
    guard data.count == 4 else { throw ProductionC1Error.malformedCanonical }
    return data.reduce(0) { ($0 << 8) | UInt32($1) }
}

private func c1UInt16(_ data: Data) throws -> UInt16 {
    guard data.count == 2 else { throw ProductionC1Error.malformedCanonical }
    return data.reduce(0) { ($0 << 8) | UInt16($1) }
}

private func c1LowerHex(_ data: Data) -> String {
    data.map { String(format: "%02x", $0) }.joined()
}

private func c1DecodeLowerHex(_ value: String) -> Data? {
    guard value.utf8.count.isMultiple(of: 2),
          value.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
        return nil
    }
    var output = Data()
    output.reserveCapacity(value.utf8.count / 2)
    var index = value.startIndex
    while index < value.endIndex {
        let next = value.index(index, offsetBy: 2)
        guard let byte = UInt8(value[index..<next], radix: 16) else { return nil }
        output.append(byte)
        index = next
    }
    return output
}

private func c1ValidateDigest(_ value: String) throws {
    guard let bytes = c1DecodeLowerHex(value), bytes.count == 32 else {
        throw ProductionC1Error.invalidValue
    }
}

private func c1ForceDecodeDigest(_ value: String) -> Data {
    c1DecodeLowerHex(value) ?? Data()
}

private func c1OptionalDigestBytes(_ value: String?) -> Data {
    c1ASCII(value ?? "none")
}

private func c1OptionalDigest(_ data: Data) throws -> String? {
    let value = try c1Text(data)
    if value == "none" { return nil }
    try c1ValidateDigest(value)
    return value
}

private func c1DigestHex(_ data: Data) -> String {
    c1LowerHex(Data(SHA256.hash(data: data)))
}

private func c1PublicKey(x963: Data) throws -> P256.Signing.PublicKey {
    guard let key = try? P256.Signing.PublicKey(x963Representation: x963),
          key.x963Representation == x963 else {
        throw ProductionC1Error.invalidPublicKey
    }
    return key
}

private func c1KeyId(_ key: P256.Signing.PublicKey) -> String {
    c1DigestHex(key.derRepresentation)
}

private func c1SignatureTranscript(domain: String, claims: Data) -> Data {
    var output = c1ASCII(domain)
    output.append(0)
    output.append(c1BE(UInt32(claims.count)))
    output.append(claims)
    return output
}

private let c1P256Order: [UInt8] = [
    0xff, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0x00,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xbc, 0xe6, 0xfa, 0xad, 0xa7, 0x17, 0x9e, 0x84,
    0xf3, 0xb9, 0xca, 0xc2, 0xfc, 0x63, 0x25, 0x51,
]

private let c1P256HalfOrder: [UInt8] = [
    0x7f, 0xff, 0xff, 0xff, 0x80, 0x00, 0x00, 0x00,
    0x7f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xde, 0x73, 0x7d, 0x56, 0xd3, 0x8b, 0xcf, 0x42,
    0x79, 0xdc, 0xe5, 0x61, 0x7e, 0x31, 0x92, 0xa8,
]

private func c1ValidateCanonicalLowS(_ data: Data) throws {
    let bytes = [UInt8](data)
    guard bytes.count >= 8, bytes.count <= 72,
          bytes[0] == 0x30,
          Int(bytes[1]) == bytes.count - 2 else {
        throw ProductionC1Error.nonCanonicalSignature
    }
    var offset = 2
    let r = try c1DERInteger(bytes, offset: &offset)
    let s = try c1DERInteger(bytes, offset: &offset)
    guard offset == bytes.count,
          c1Compare(r, c1P256Order) < 0,
          c1Compare(s, c1P256Order) < 0 else {
        throw ProductionC1Error.nonCanonicalSignature
    }
    guard c1Compare(s, c1P256HalfOrder) <= 0 else { throw ProductionC1Error.highS }
    guard let parsed = try? P256.Signing.ECDSASignature(derRepresentation: data),
          parsed.derRepresentation == data else {
        throw ProductionC1Error.nonCanonicalSignature
    }
}

private func c1DERInteger(_ bytes: [UInt8], offset: inout Int) throws -> [UInt8] {
    guard offset + 2 <= bytes.count, bytes[offset] == 0x02 else {
        throw ProductionC1Error.nonCanonicalSignature
    }
    let length = Int(bytes[offset + 1])
    offset += 2
    guard length > 0, length <= 33, offset + length <= bytes.count else {
        throw ProductionC1Error.nonCanonicalSignature
    }
    var value = Array(bytes[offset..<(offset + length)])
    offset += length
    if value[0] == 0 {
        guard value.count > 1, value[1] & 0x80 != 0 else {
            throw ProductionC1Error.nonCanonicalSignature
        }
        value.removeFirst()
    } else if value[0] & 0x80 != 0 {
        throw ProductionC1Error.nonCanonicalSignature
    }
    guard value.count <= 32, value.contains(where: { $0 != 0 }) else {
        throw ProductionC1Error.nonCanonicalSignature
    }
    return Array(repeating: 0, count: 32 - value.count) + value
}

private func c1Compare(_ left: [UInt8], _ right: [UInt8]) -> Int {
    for (a, b) in zip(left, right) where a != b { return a < b ? -1 : 1 }
    return 0
}

private func c1Subtract(_ left: [UInt8], _ right: [UInt8]) -> [UInt8] {
    var result = Array(repeating: UInt8(0), count: left.count)
    var borrow = 0
    for index in stride(from: left.count - 1, through: 0, by: -1) {
        var value = Int(left[index]) - Int(right[index]) - borrow
        if value < 0 { value += 256; borrow = 1 } else { borrow = 0 }
        result[index] = UInt8(value)
    }
    return result
}

private func c1Sign(_ data: Data, using key: P256.Signing.PrivateKey) throws -> Data {
    let signature = try key.signature(for: data)
    let raw = [UInt8](signature.rawRepresentation)
    guard raw.count == 64 else { throw ProductionC1Error.invalidSignature }
    let r = Array(raw[0..<32])
    var s = Array(raw[32..<64])
    if c1Compare(s, c1P256HalfOrder) > 0 { s = c1Subtract(c1P256Order, s) }
    let normalized = try P256.Signing.ECDSASignature(rawRepresentation: Data(r + s))
    let der = normalized.derRepresentation
    try c1ValidateCanonicalLowS(der)
    return der
}

private func c1Verify(
    signature data: Data,
    transcript: Data,
    publicKey: P256.Signing.PublicKey
) throws {
    try c1ValidateCanonicalLowS(data)
    guard let signature = try? P256.Signing.ECDSASignature(derRepresentation: data),
          publicKey.isValidSignature(signature, for: transcript) else {
        throw ProductionC1Error.invalidSignature
    }
}

private func c1ValidateWindow(
    issuedAtMs: UInt64,
    notBeforeMs: UInt64,
    expiresAtMs: UInt64,
    maximumLifetimeMs: UInt64,
    nowMs: UInt64
) throws {
    guard issuedAtMs <= notBeforeMs,
          notBeforeMs < expiresAtMs,
          expiresAtMs - issuedAtMs <= maximumLifetimeMs else {
        throw ProductionC1Error.invalidValue
    }
    let futureLimit = nowMs.addingReportingOverflow(ProductionC1Contract.maximumClockSkewMs)
    guard !futureLimit.overflow, issuedAtMs <= futureLimit.partialValue else {
        throw ProductionC1Error.issuedInFuture
    }
    guard !futureLimit.overflow, notBeforeMs <= futureLimit.partialValue else {
        throw ProductionC1Error.notYetValid
    }
    guard nowMs < expiresAtMs else { throw ProductionC1Error.expired }
}

private func c1ValidateVerifiedKeysetUse(
    _ verifiedKeyset: VerifiedProductionC1ServiceKeyset,
    nowMs: UInt64
) throws {
    let keyset = verifiedKeyset.keyset
    try c1ValidateWindow(
        issuedAtMs: keyset.issuedAtMs,
        notBeforeMs: keyset.issuedAtMs,
        expiresAtMs: keyset.expiresAtMs,
        maximumLifetimeMs: ProductionC1Contract.maximumKeysetLifetimeMs,
        nowMs: nowMs
    )
}

// Narrow module-only bridge for extension codecs. It keeps the ALS1, DER,
// signing, key-purpose, and use-time rules single-sourced in this file.
enum ProductionC1InternalBridge {
    static func encode(objectType: UInt8, fields: [Data]) -> Data {
        C1TLV.encode(objectType: objectType, fields: fields)
    }

    static func decode(
        _ data: Data,
        objectType: UInt8,
        fieldCount: Int,
        maximumBytes: Int
    ) throws -> [Data] {
        try C1TLV.decode(
            data,
            objectType: objectType,
            fieldCount: fieldCount,
            maximumBytes: maximumBytes
        )
    }

    static func ascii(_ value: String) -> Data { c1ASCII(value) }
    static func text(_ data: Data) throws -> String { try c1Text(data) }
    static func be<T: FixedWidthInteger>(_ value: T) -> Data { c1BE(value) }
    static func uint64(_ data: Data) throws -> UInt64 { try c1UInt64(data) }
    static func uint32(_ data: Data) throws -> UInt32 { try c1UInt32(data) }
    static func validateDigest(_ value: String) throws { try c1ValidateDigest(value) }
    static func rawDigest(_ value: String) throws -> Data {
        try c1ValidateDigest(value)
        return c1ForceDecodeDigest(value)
    }
    static func digestHex(_ data: Data) -> String { c1DigestHex(data) }
    static func keyId(_ key: P256.Signing.PublicKey) -> String { c1KeyId(key) }
    static func transcript(domain: String, claims: Data) -> Data {
        c1SignatureTranscript(domain: domain, claims: claims)
    }
    static func sign(_ transcript: Data, using key: P256.Signing.PrivateKey) throws -> Data {
        try c1Sign(transcript, using: key)
    }
    static func validateSignature(_ signature: Data) throws {
        try c1ValidateCanonicalLowS(signature)
    }
    static func verify(
        signature: Data,
        transcript: Data,
        publicKey: P256.Signing.PublicKey
    ) throws {
        try c1Verify(signature: signature, transcript: transcript, publicKey: publicKey)
    }
    static func validateWindow(
        issuedAtMs: UInt64,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        maximumLifetimeMs: UInt64,
        nowMs: UInt64
    ) throws {
        try c1ValidateWindow(
            issuedAtMs: issuedAtMs,
            notBeforeMs: notBeforeMs,
            expiresAtMs: expiresAtMs,
            maximumLifetimeMs: maximumLifetimeMs,
            nowMs: nowMs
        )
    }
    static func delegatedSigningKey(
        id: String,
        purpose: ProductionC1DelegatedKeyPurpose,
        in keyset: VerifiedProductionC1ServiceKeyset,
        nowMs: UInt64
    ) throws -> P256.Signing.PublicKey {
        try c1ValidateVerifiedKeysetUse(keyset, nowMs: nowMs)
        let delegated = try c1DelegatedKey(
            id: id,
            purpose: purpose,
            in: keyset,
            nowMs: nowMs
        )
        return try c1PublicKey(x963: delegated.publicKeyX963)
    }
}

private func c1ValidateVerifiedPairStatusUse(
    _ verifiedStatus: VerifiedProductionC1PairStatus,
    nowMs: UInt64
) throws {
    try c1ValidateVerifiedKeysetUse(verifiedStatus.verifiedKeyset, nowMs: nowMs)
    let status = verifiedStatus.status
    try c1ValidateWindow(
        issuedAtMs: status.issuedAtMs,
        notBeforeMs: status.issuedAtMs,
        expiresAtMs: status.expiresAtMs,
        maximumLifetimeMs: ProductionC1Contract.maximumStatusLifetimeMs,
        nowMs: nowMs
    )
    _ = try c1DelegatedKey(
        id: status.signingKeyId,
        purpose: .pairStatus,
        in: verifiedStatus.verifiedKeyset,
        nowMs: nowMs
    )
}

private func c1ValidateFreshPairTransitionUse(
    _ verified: VerifiedProductionC1FreshPairTransition,
    nowMs: UInt64
) throws {
    try c1ValidateVerifiedPairStatusUse(verified.verifiedStatus, nowMs: nowMs)
    try c1ValidateWindow(
        issuedAtMs: verified.proof.issuedAtMs,
        notBeforeMs: verified.proof.issuedAtMs,
        expiresAtMs: verified.proof.expiresAtMs,
        maximumLifetimeMs: ProductionC1Contract.maximumFreshPairLifetimeMs,
        nowMs: nowMs
    )
}

private func c1ValidateVerifiedRoutePlanUse(
    _ verifiedPlan: VerifiedProductionC1RoutePlan,
    nowMs: UInt64
) throws {
    try c1ValidateVerifiedKeysetUse(verifiedPlan.verifiedKeyset, nowMs: nowMs)
    guard verifiedPlan.claims.securityContextDigest == verifiedPlan.securityContext.digestHex(),
          verifiedPlan.claims.kind == verifiedPlan.securityContext.routeKind else {
        throw ProductionC1Error.routeMismatch
    }
    let capability = verifiedPlan.capability
    try c1ValidateWindow(
        issuedAtMs: capability.issuedAtMs,
        notBeforeMs: capability.notBeforeMs,
        expiresAtMs: capability.expiresAtMs,
        maximumLifetimeMs: ProductionC1Contract.maximumRouteLifetimeMs,
        nowMs: nowMs
    )
    try c1ValidateWindow(
        issuedAtMs: capability.issuedAtMs,
        notBeforeMs: verifiedPlan.claims.notBeforeMs,
        expiresAtMs: verifiedPlan.claims.expiresAtMs,
        maximumLifetimeMs: ProductionC1Contract.maximumRouteLifetimeMs,
        nowMs: nowMs
    )
    _ = try c1DelegatedKey(
        id: capability.signingKeyId,
        purpose: .routeCapability,
        in: verifiedPlan.verifiedKeyset,
        nowMs: nowMs
    )
}

private func c1DelegatedKey(
    id: String,
    purpose: ProductionC1DelegatedKeyPurpose,
    in keyset: VerifiedProductionC1ServiceKeyset,
    nowMs: UInt64
) throws -> ProductionC1DelegatedKey {
    guard let key = keyset.keyset.delegatedKeys.first(where: { $0.keyId == id }) else {
        throw ProductionC1Error.keyUnavailable
    }
    guard key.keysetVersion == keyset.keyset.keysetVersion ||
            (keyset.keyset.keysetVersion > 1 &&
             key.keysetVersion == keyset.keyset.keysetVersion - 1) else {
        throw ProductionC1Error.keyUnavailable
    }
    guard key.purposes.contains(purpose) else { throw ProductionC1Error.keyPurposeMismatch }
    if let revoked = key.revokedAtMs, revoked <= nowMs { throw ProductionC1Error.keyRevoked }
    guard key.notBeforeMs <= nowMs else { throw ProductionC1Error.notYetValid }
    guard nowMs < key.expiresAtMs else { throw ProductionC1Error.expired }
    return key
}

private func c1TransitionSequence(
    history: [ProductionPairTransitionHistoryEntry],
    authority: ProductionPairAuthorityState
) throws -> [ProductionPairTransitionHistoryEntry] {
    history + [try ProductionPairTransitionHistoryEntry(
        transitionId: authority.transitionId,
        transitionRequestDigest: authority.transitionRequestDigest
    )]
}

private func c1TransitionKindMatchesState(_ status: ProductionC1PairStatus) -> Bool {
    switch status.transitionKind {
    case .genesis:
        status.evidenceKind == .initialPairing && status.authority.status == .active
    case .sameEpoch:
        status.evidenceKind == .sameEpochTransition && status.authority.status == .active
    case .revoke:
        status.evidenceKind == .denyOnlyRevocation && status.authority.status == .revoked
    case .freshPair:
        status.evidenceKind == .dualSignedFreshPair && status.authority.status == .active
    }
}

private func c1ValidateAuthorityAdvance(
    previous: ProductionPairAuthorityState,
    next: ProductionPairAuthorityState,
    transitionKind: ProductionC1TransitionKind
) throws {
    guard next.authorityRevision >= previous.authorityRevision,
          next.generation >= previous.generation,
          next.serviceConfigVersion >= previous.serviceConfigVersion,
          next.keysetVersion >= previous.keysetVersion,
          next.revocationCounter >= previous.revocationCounter,
          next.protocolFloor >= previous.protocolFloor else {
        throw ProductionC1Error.stateMismatch
    }
    switch transitionKind {
    case .sameEpoch, .revoke:
        guard next.pairEpoch == previous.pairEpoch,
              next.pairBindingDigest == previous.pairBindingDigest,
              next.clientIdentityFingerprint == previous.clientIdentityFingerprint,
              next.runtimeIdentityFingerprint == previous.runtimeIdentityFingerprint,
              !(previous.status == .revoked && next.status == .active) else {
            throw ProductionC1Error.stateMismatch
        }
        if transitionKind == .revoke {
            guard previous.status == .active,
                  previous.revocationCounter < UInt64.max,
                  next.revocationCounter == previous.revocationCounter + 1 else {
                throw ProductionC1Error.stateMismatch
            }
        }
    case .freshPair:
        guard previous.pairEpoch < UInt64.max,
              next.pairEpoch == previous.pairEpoch + 1 else {
            throw ProductionC1Error.invalidFreshPair
        }
    case .genesis:
        throw ProductionC1Error.stateMismatch
    }
}

private func c1IsCanonicalServerName(_ value: String) -> Bool {
    guard !value.isEmpty, value != "none", value.utf8.count <= 253,
          value == value.lowercased(), value.unicodeScalars.allSatisfy({ $0.isASCII }) else {
        return false
    }
    let labels = value.split(separator: ".", omittingEmptySubsequences: false)
    return !labels.isEmpty && labels.allSatisfy { label in
        !label.isEmpty && label.utf8.count <= 63 &&
            label.first != "-" && label.last != "-" &&
            label.utf8.allSatisfy { (48...57).contains($0) || (97...122).contains($0) || $0 == 45 }
    }
}

private func c1BoundedUTF8(_ value: String, maximum: Int) throws -> Data {
    let bytes = Data(value.utf8)
    guard !bytes.isEmpty, bytes.count <= maximum else { throw ProductionC1Error.limitExceeded }
    return bytes
}
