import CryptoKit
import Foundation

public enum ProductionC1CandidateCapabilityContract {
    public static let publishObjectType: UInt8 = 23
    public static let fetchObjectType: UInt8 = 24
    public static let grantEvidenceObjectType: UInt8 = 25
    public static let grantAuthorizationObjectType: UInt8 = 26
    public static let endpointOperationProofObjectType: UInt8 = 27
    public static let revision: UInt64 = 1
    public static let maximumCapabilityBytes = 4_096
    public static let maximumGrantEvidenceBytes = 8_192
    public static let maximumGrantAuthorizationBytes = 2_048
    public static let maximumEndpointOperationProofBytes = 2_048
    public static let maximumLifetimeMs = ProductionC1Contract.maximumRouteLifetimeMs
}

public enum ProductionC1CandidateCapabilityError: Error, Equatable, Sendable {
    case malformedCanonical
    case invalidValue
    case roleMismatch
    case authorityMismatch
    case batchMismatch
    case routeMismatch
    case requestConflict
    case replay
    case quotaExceeded
    case revisionMismatch
    case retentionExhausted
    case persistenceUnavailable
}

public enum ProductionC1CandidateOperation: String, Sendable {
    case publish = "candidate_publish"
    case fetch = "candidate_fetch"

    fileprivate var objectType: UInt8 {
        switch self {
        case .publish: ProductionC1CandidateCapabilityContract.publishObjectType
        case .fetch: ProductionC1CandidateCapabilityContract.fetchObjectType
        }
    }

    fileprivate var keyPurpose: ProductionC1DelegatedKeyPurpose {
        switch self {
        case .publish: .candidatePublish
        case .fetch: .candidateFetch
        }
    }

    fileprivate var signingDomain: String {
        "AetherLink G1a-C \(rawValue.replacingOccurrences(of: "_", with: "-")) capability service signature v1"
    }
}

public struct ProductionC1EndpointOperationProof: Equatable, Sendable {
    public let requesterRole: P2PNATRole
    public let requesterIdentityFingerprint: String
    public let requesterPublicKeyX963: Data
    public let operation: ProductionC1CandidateOperation
    public let candidateOwnerRole: P2PNATRole
    public let candidateOwnerIdentityFingerprint: String
    public let sessionId: String
    public let attemptId: String
    public let capabilityId: String
    public let candidateBatchDigest: String
    public let candidateBatchSequence: UInt64
    public let singleUseNonce: String
    public let securityContextDigest: String
    public let issuedAtMs: UInt64
    public let notBeforeMs: UInt64
    public let expiresAtMs: UInt64
    public let proofId: String
    public let pairAuthorityDigest: String
    public let serviceAudienceId: String
    public let initiatorRole: P2PNATRole
    public let endpointSignature: Data

    private init(
        requesterRole: P2PNATRole,
        requesterIdentityFingerprint: String,
        requesterPublicKeyX963: Data,
        operation: ProductionC1CandidateOperation,
        candidateOwnerRole: P2PNATRole,
        candidateOwnerIdentityFingerprint: String,
        sessionId: String,
        attemptId: String,
        capabilityId: String,
        candidateBatchDigest: String,
        candidateBatchSequence: UInt64,
        singleUseNonce: String,
        securityContextDigest: String,
        issuedAtMs: UInt64,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        proofId: String,
        pairAuthorityDigest: String,
        serviceAudienceId: String,
        initiatorRole: P2PNATRole,
        endpointSignature: Data,
        validateSignature: Bool
    ) throws {
        for digest in [
            requesterIdentityFingerprint, candidateOwnerIdentityFingerprint,
            capabilityId, candidateBatchDigest, singleUseNonce, securityContextDigest,
            proofId, pairAuthorityDigest, serviceAudienceId,
        ] { try ProductionC1InternalBridge.validateDigest(digest) }
        guard let requesterPublicKey = try? P256.Signing.PublicKey(
            x963Representation: requesterPublicKeyX963
        ), ProductionC1InternalBridge.keyId(requesterPublicKey)
            == requesterIdentityFingerprint else {
            throw ProductionC1CandidateCapabilityError.roleMismatch
        }
        guard sessionId.utf8.count == 32, candidateIsLowerHex(sessionId),
              attemptId.utf8.count == 64, candidateIsLowerHex(attemptId),
              candidateBatchSequence > 0,
              initiatorRole == .client,
              issuedAtMs <= notBeforeMs, notBeforeMs < expiresAtMs else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        switch operation {
        case .publish where requesterRole != candidateOwnerRole,
             .fetch where requesterRole == candidateOwnerRole:
            throw ProductionC1CandidateCapabilityError.roleMismatch
        default: break
        }
        if validateSignature {
            try ProductionC1InternalBridge.validateSignature(endpointSignature)
        }
        self.requesterRole = requesterRole
        self.requesterIdentityFingerprint = requesterIdentityFingerprint
        self.requesterPublicKeyX963 = requesterPublicKeyX963
        self.operation = operation
        self.candidateOwnerRole = candidateOwnerRole
        self.candidateOwnerIdentityFingerprint = candidateOwnerIdentityFingerprint
        self.sessionId = sessionId
        self.attemptId = attemptId
        self.capabilityId = capabilityId
        self.candidateBatchDigest = candidateBatchDigest
        self.candidateBatchSequence = candidateBatchSequence
        self.singleUseNonce = singleUseNonce
        self.securityContextDigest = securityContextDigest
        self.issuedAtMs = issuedAtMs
        self.notBeforeMs = notBeforeMs
        self.expiresAtMs = expiresAtMs
        self.proofId = proofId
        self.pairAuthorityDigest = pairAuthorityDigest
        self.serviceAudienceId = serviceAudienceId
        self.initiatorRole = initiatorRole
        self.endpointSignature = endpointSignature
        guard try canonicalBytes().count
                <= ProductionC1CandidateCapabilityContract.maximumEndpointOperationProofBytes else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
    }

    public static func signed(
        requesterRole: P2PNATRole,
        operation: ProductionC1CandidateOperation,
        candidateOwnerRole: P2PNATRole,
        proofId: String,
        attemptId: String,
        capabilityId: String,
        candidateBatch: CandidateBatch,
        singleUseNonce: String,
        securityContext: ProductionC1PreauthorizationSessionContext,
        serviceAudienceId: String,
        initiatorRole: P2PNATRole = .client,
        authority: ProductionPairAuthorityState,
        issuedAtMs: UInt64,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        using requesterIdentityKey: P256.Signing.PrivateKey
    ) throws -> Self {
        guard securityContext.sessionId == candidateBatch.sessionId,
              securityContext.generation == candidateBatch.generation,
              securityContext.pairBindingDigest == authority.pairBindingDigest else {
            throw ProductionC1CandidateCapabilityError.roleMismatch
        }
        let requesterIdentity = requesterRole == .client
            ? authority.clientIdentityFingerprint : authority.runtimeIdentityFingerprint
        let ownerIdentity = candidateOwnerRole == .client
            ? authority.clientIdentityFingerprint : authority.runtimeIdentityFingerprint
        let unsigned = try Self(
            requesterRole: requesterRole,
            requesterIdentityFingerprint: requesterIdentity,
            requesterPublicKeyX963: requesterIdentityKey.publicKey.x963Representation,
            operation: operation,
            candidateOwnerRole: candidateOwnerRole,
            candidateOwnerIdentityFingerprint: ownerIdentity,
            sessionId: candidateBatch.sessionId,
            attemptId: attemptId,
            capabilityId: capabilityId,
            candidateBatchDigest: ProductionC1InternalBridge.digestHex(
                candidateBatch.canonicalBytes()
            ),
            candidateBatchSequence: candidateBatch.sequence,
            singleUseNonce: singleUseNonce,
            securityContextDigest: securityContext.digestHex(),
            issuedAtMs: issuedAtMs,
            notBeforeMs: notBeforeMs,
            expiresAtMs: expiresAtMs,
            proofId: proofId,
            pairAuthorityDigest: authority.digestHex(),
            serviceAudienceId: serviceAudienceId,
            initiatorRole: initiatorRole,
            endpointSignature: Data(),
            validateSignature: false
        )
        return try Self(
            requesterRole: unsigned.requesterRole,
            requesterIdentityFingerprint: unsigned.requesterIdentityFingerprint,
            requesterPublicKeyX963: unsigned.requesterPublicKeyX963,
            operation: unsigned.operation,
            candidateOwnerRole: unsigned.candidateOwnerRole,
            candidateOwnerIdentityFingerprint: unsigned.candidateOwnerIdentityFingerprint,
            sessionId: unsigned.sessionId,
            attemptId: unsigned.attemptId,
            capabilityId: unsigned.capabilityId,
            candidateBatchDigest: unsigned.candidateBatchDigest,
            candidateBatchSequence: unsigned.candidateBatchSequence,
            singleUseNonce: unsigned.singleUseNonce,
            securityContextDigest: unsigned.securityContextDigest,
            issuedAtMs: unsigned.issuedAtMs,
            notBeforeMs: unsigned.notBeforeMs,
            expiresAtMs: unsigned.expiresAtMs,
            proofId: unsigned.proofId,
            pairAuthorityDigest: unsigned.pairAuthorityDigest,
            serviceAudienceId: unsigned.serviceAudienceId,
            initiatorRole: unsigned.initiatorRole,
            endpointSignature: ProductionC1InternalBridge.sign(
                unsigned.signingTranscript,
                using: requesterIdentityKey
            ),
            validateSignature: true
        )
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try ProductionC1InternalBridge.decode(
            data,
            objectType: ProductionC1CandidateCapabilityContract.endpointOperationProofObjectType,
            fieldCount: 24,
            maximumBytes:
                ProductionC1CandidateCapabilityContract.maximumEndpointOperationProofBytes
        )
        guard try ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.suite,
              try ProductionC1InternalBridge.uint64(fields[1])
                == ProductionC1CandidateCapabilityContract.revision,
              let requester = P2PNATRole(
                rawValue: try ProductionC1InternalBridge.text(fields[2])
              ),
              let operation = ProductionC1CandidateOperation(
                rawValue: try ProductionC1InternalBridge.text(fields[5])
              ),
              let owner = P2PNATRole(
                rawValue: try ProductionC1InternalBridge.text(fields[6])
              ),
              let initiator = P2PNATRole(
                rawValue: try ProductionC1InternalBridge.text(fields[21])
              ),
              try ProductionC1InternalBridge.text(fields[22])
                == ProductionC1Contract.signatureAlgorithm else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        try self.init(
            requesterRole: requester,
            requesterIdentityFingerprint: ProductionC1InternalBridge.text(fields[3]),
            requesterPublicKeyX963: fields[4],
            operation: operation,
            candidateOwnerRole: owner,
            candidateOwnerIdentityFingerprint: ProductionC1InternalBridge.text(fields[7]),
            sessionId: ProductionC1InternalBridge.text(fields[8]),
            attemptId: ProductionC1InternalBridge.text(fields[9]),
            capabilityId: ProductionC1InternalBridge.text(fields[10]),
            candidateBatchDigest: ProductionC1InternalBridge.text(fields[11]),
            candidateBatchSequence: ProductionC1InternalBridge.uint64(fields[12]),
            singleUseNonce: ProductionC1InternalBridge.text(fields[13]),
            securityContextDigest: ProductionC1InternalBridge.text(fields[14]),
            issuedAtMs: ProductionC1InternalBridge.uint64(fields[15]),
            notBeforeMs: ProductionC1InternalBridge.uint64(fields[16]),
            expiresAtMs: ProductionC1InternalBridge.uint64(fields[17]),
            proofId: ProductionC1InternalBridge.text(fields[18]),
            pairAuthorityDigest: ProductionC1InternalBridge.text(fields[19]),
            serviceAudienceId: ProductionC1InternalBridge.text(fields[20]),
            initiatorRole: initiator,
            endpointSignature: fields[23],
            validateSignature: true
        )
        guard try canonicalBytes() == data else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
    }

    public func canonicalBytes() throws -> Data {
        ProductionC1InternalBridge.encode(
            objectType: ProductionC1CandidateCapabilityContract.endpointOperationProofObjectType,
            fields: claimsFields + [endpointSignature]
        )
    }

    public func digestHex() throws -> String {
        ProductionC1InternalBridge.digestHex(try canonicalBytes())
    }

    fileprivate var signingTranscript: Data {
        ProductionC1InternalBridge.transcript(
            domain: "AetherLink G1a-C endpoint-authenticated candidate operation v1",
            claims: ProductionC1InternalBridge.encode(
                objectType:
                    ProductionC1CandidateCapabilityContract.endpointOperationProofObjectType,
                fields: claimsFields
            )
        )
    }

    private var claimsFields: [Data] {
        [
            ProductionC1InternalBridge.ascii(ProductionC1Contract.suite),
            ProductionC1InternalBridge.be(ProductionC1CandidateCapabilityContract.revision),
            ProductionC1InternalBridge.ascii(requesterRole.rawValue),
            ProductionC1InternalBridge.ascii(requesterIdentityFingerprint),
            requesterPublicKeyX963,
            ProductionC1InternalBridge.ascii(operation.rawValue),
            ProductionC1InternalBridge.ascii(candidateOwnerRole.rawValue),
            ProductionC1InternalBridge.ascii(candidateOwnerIdentityFingerprint),
            ProductionC1InternalBridge.ascii(sessionId),
            ProductionC1InternalBridge.ascii(attemptId),
            ProductionC1InternalBridge.ascii(capabilityId),
            ProductionC1InternalBridge.ascii(candidateBatchDigest),
            ProductionC1InternalBridge.be(candidateBatchSequence),
            ProductionC1InternalBridge.ascii(singleUseNonce),
            ProductionC1InternalBridge.ascii(securityContextDigest),
            ProductionC1InternalBridge.be(issuedAtMs),
            ProductionC1InternalBridge.be(notBeforeMs),
            ProductionC1InternalBridge.be(expiresAtMs),
            ProductionC1InternalBridge.ascii(proofId),
            ProductionC1InternalBridge.ascii(pairAuthorityDigest),
            ProductionC1InternalBridge.ascii(serviceAudienceId),
            ProductionC1InternalBridge.ascii(initiatorRole.rawValue),
            ProductionC1InternalBridge.ascii(ProductionC1Contract.signatureAlgorithm),
        ]
    }
}

public struct ProductionC1CandidateCapability: Equatable, Sendable {
    public let operation: ProductionC1CandidateOperation
    public let serviceIdDigest: String
    public let keysetVersion: UInt64
    public let signingKeyId: String
    public let capabilityId: String
    public let pairAuthorityDigest: String
    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let generation: UInt64
    public let serviceConfigVersion: UInt64
    public let revocationCounter: UInt64
    public let protocolFloor: UInt32
    public let clientIdentityFingerprint: String
    public let runtimeIdentityFingerprint: String
    public let sessionId: String
    public let attemptId: String
    public let requesterRole: P2PNATRole
    public let requesterIdentityFingerprint: String
    public let candidateOwnerRole: P2PNATRole
    public let candidateOwnerIdentityFingerprint: String
    public let candidateBatchDigest: String
    public let candidateBatchByteCount: UInt32
    public let candidateBatchSequence: UInt64
    public let candidateBatchExpiresAtMs: UInt64
    public let maximumCandidateBytes: UInt64
    public let maxOperations: UInt32
    public let singleUseNonce: String
    public let issuedAtMs: UInt64
    public let notBeforeMs: UInt64
    public let expiresAtMs: UInt64
    public let endpointOperationProofDigest: String
    public let serviceSignature: Data

    private init(
        operation: ProductionC1CandidateOperation,
        serviceIdDigest: String,
        keysetVersion: UInt64,
        signingKeyId: String,
        capabilityId: String,
        pairAuthorityDigest: String,
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        serviceConfigVersion: UInt64,
        revocationCounter: UInt64,
        protocolFloor: UInt32,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        sessionId: String,
        attemptId: String,
        requesterRole: P2PNATRole,
        requesterIdentityFingerprint: String,
        candidateOwnerRole: P2PNATRole,
        candidateOwnerIdentityFingerprint: String,
        candidateBatchDigest: String,
        candidateBatchByteCount: UInt32,
        candidateBatchSequence: UInt64,
        candidateBatchExpiresAtMs: UInt64,
        maximumCandidateBytes: UInt64,
        maxOperations: UInt32,
        singleUseNonce: String,
        issuedAtMs: UInt64,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        endpointOperationProofDigest: String,
        serviceSignature: Data,
        validateSignature: Bool
    ) throws {
        for digest in [
            serviceIdDigest, signingKeyId, capabilityId, pairAuthorityDigest,
            pairBindingDigest, clientIdentityFingerprint, runtimeIdentityFingerprint,
            requesterIdentityFingerprint, candidateOwnerIdentityFingerprint,
            candidateBatchDigest, singleUseNonce, endpointOperationProofDigest,
        ] { try ProductionC1InternalBridge.validateDigest(digest) }
        guard sessionId.utf8.count == 32, candidateIsLowerHex(sessionId),
              attemptId.utf8.count == 64, candidateIsLowerHex(attemptId),
              keysetVersion > 0, pairEpoch > 0, generation > 0,
              serviceConfigVersion > 0, protocolFloor > 0,
              clientIdentityFingerprint != runtimeIdentityFingerprint,
              candidateBatchByteCount > 0,
              UInt64(candidateBatchByteCount) <= maximumCandidateBytes,
              maximumCandidateBytes <= UInt64(P2PNATLimits.candidateBatchBytes),
              maxOperations == 1,
              issuedAtMs <= notBeforeMs, notBeforeMs < expiresAtMs,
              expiresAtMs <= candidateBatchExpiresAtMs else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        let requesterExpected = requesterRole == .client
            ? clientIdentityFingerprint : runtimeIdentityFingerprint
        let ownerExpected = candidateOwnerRole == .client
            ? clientIdentityFingerprint : runtimeIdentityFingerprint
        guard requesterIdentityFingerprint == requesterExpected,
              candidateOwnerIdentityFingerprint == ownerExpected else {
            throw ProductionC1CandidateCapabilityError.roleMismatch
        }
        switch operation {
        case .publish:
            guard requesterRole == candidateOwnerRole else {
                throw ProductionC1CandidateCapabilityError.roleMismatch
            }
        case .fetch:
            guard requesterRole != candidateOwnerRole else {
                throw ProductionC1CandidateCapabilityError.roleMismatch
            }
        }
        if validateSignature {
            try ProductionC1InternalBridge.validateSignature(serviceSignature)
        }
        self.operation = operation
        self.serviceIdDigest = serviceIdDigest
        self.keysetVersion = keysetVersion
        self.signingKeyId = signingKeyId
        self.capabilityId = capabilityId
        self.pairAuthorityDigest = pairAuthorityDigest
        self.pairBindingDigest = pairBindingDigest
        self.pairEpoch = pairEpoch
        self.generation = generation
        self.serviceConfigVersion = serviceConfigVersion
        self.revocationCounter = revocationCounter
        self.protocolFloor = protocolFloor
        self.clientIdentityFingerprint = clientIdentityFingerprint
        self.runtimeIdentityFingerprint = runtimeIdentityFingerprint
        self.sessionId = sessionId
        self.attemptId = attemptId
        self.requesterRole = requesterRole
        self.requesterIdentityFingerprint = requesterIdentityFingerprint
        self.candidateOwnerRole = candidateOwnerRole
        self.candidateOwnerIdentityFingerprint = candidateOwnerIdentityFingerprint
        self.candidateBatchDigest = candidateBatchDigest
        self.candidateBatchByteCount = candidateBatchByteCount
        self.candidateBatchSequence = candidateBatchSequence
        self.candidateBatchExpiresAtMs = candidateBatchExpiresAtMs
        self.maximumCandidateBytes = maximumCandidateBytes
        self.maxOperations = maxOperations
        self.singleUseNonce = singleUseNonce
        self.issuedAtMs = issuedAtMs
        self.notBeforeMs = notBeforeMs
        self.expiresAtMs = expiresAtMs
        self.endpointOperationProofDigest = endpointOperationProofDigest
        self.serviceSignature = serviceSignature
        guard try canonicalBytes().count <= ProductionC1CandidateCapabilityContract.maximumCapabilityBytes else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
    }

    public static func signed(
        operation: ProductionC1CandidateOperation,
        serviceIdDigest: String,
        keysetVersion: UInt64,
        capabilityId: String,
        attemptId: String,
        requesterRole: P2PNATRole,
        candidateOwnerRole: P2PNATRole,
        maximumCandidateBytes: UInt64,
        singleUseNonce: String,
        issuedAtMs: UInt64,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        authority: ProductionPairAuthorityState,
        candidateBatch: CandidateBatch,
        endpointOperationProof: ProductionC1EndpointOperationProof,
        using signingKey: P256.Signing.PrivateKey
    ) throws -> Self {
        let batchBytes = candidateBatch.canonicalBytes()
        guard batchBytes.count <= Int(UInt32.max) else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        let requesterIdentity = requesterRole == .client
            ? authority.clientIdentityFingerprint : authority.runtimeIdentityFingerprint
        let ownerIdentity = candidateOwnerRole == .client
            ? authority.clientIdentityFingerprint : authority.runtimeIdentityFingerprint
        guard endpointOperationProof.operation == operation,
              endpointOperationProof.requesterRole == requesterRole,
              endpointOperationProof.requesterIdentityFingerprint == requesterIdentity,
              endpointOperationProof.candidateOwnerRole == candidateOwnerRole,
              endpointOperationProof.candidateOwnerIdentityFingerprint == ownerIdentity,
              endpointOperationProof.capabilityId == capabilityId,
              endpointOperationProof.attemptId == attemptId,
              endpointOperationProof.singleUseNonce == singleUseNonce,
              endpointOperationProof.sessionId == candidateBatch.sessionId,
              endpointOperationProof.candidateBatchDigest
                == ProductionC1InternalBridge.digestHex(batchBytes),
              endpointOperationProof.candidateBatchSequence == candidateBatch.sequence,
              endpointOperationProof.notBeforeMs <= notBeforeMs,
              endpointOperationProof.expiresAtMs >= expiresAtMs else {
            throw ProductionC1CandidateCapabilityError.roleMismatch
        }
        let unsigned = try Self(
            operation: operation,
            serviceIdDigest: serviceIdDigest,
            keysetVersion: keysetVersion,
            signingKeyId: ProductionC1InternalBridge.keyId(signingKey.publicKey),
            capabilityId: capabilityId,
            pairAuthorityDigest: authority.digestHex(),
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            revocationCounter: authority.revocationCounter,
            protocolFloor: authority.protocolFloor,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            sessionId: candidateBatch.sessionId,
            attemptId: attemptId,
            requesterRole: requesterRole,
            requesterIdentityFingerprint: requesterIdentity,
            candidateOwnerRole: candidateOwnerRole,
            candidateOwnerIdentityFingerprint: ownerIdentity,
            candidateBatchDigest: ProductionC1InternalBridge.digestHex(batchBytes),
            candidateBatchByteCount: UInt32(batchBytes.count),
            candidateBatchSequence: candidateBatch.sequence,
            candidateBatchExpiresAtMs: candidateBatch.expires,
            maximumCandidateBytes: maximumCandidateBytes,
            maxOperations: 1,
            singleUseNonce: singleUseNonce,
            issuedAtMs: issuedAtMs,
            notBeforeMs: notBeforeMs,
            expiresAtMs: expiresAtMs,
            endpointOperationProofDigest: endpointOperationProof.digestHex(),
            serviceSignature: Data(),
            validateSignature: false
        )
        return try Self(
            operation: operation,
            serviceIdDigest: unsigned.serviceIdDigest,
            keysetVersion: unsigned.keysetVersion,
            signingKeyId: unsigned.signingKeyId,
            capabilityId: unsigned.capabilityId,
            pairAuthorityDigest: unsigned.pairAuthorityDigest,
            pairBindingDigest: unsigned.pairBindingDigest,
            pairEpoch: unsigned.pairEpoch,
            generation: unsigned.generation,
            serviceConfigVersion: unsigned.serviceConfigVersion,
            revocationCounter: unsigned.revocationCounter,
            protocolFloor: unsigned.protocolFloor,
            clientIdentityFingerprint: unsigned.clientIdentityFingerprint,
            runtimeIdentityFingerprint: unsigned.runtimeIdentityFingerprint,
            sessionId: unsigned.sessionId,
            attemptId: unsigned.attemptId,
            requesterRole: unsigned.requesterRole,
            requesterIdentityFingerprint: unsigned.requesterIdentityFingerprint,
            candidateOwnerRole: unsigned.candidateOwnerRole,
            candidateOwnerIdentityFingerprint: unsigned.candidateOwnerIdentityFingerprint,
            candidateBatchDigest: unsigned.candidateBatchDigest,
            candidateBatchByteCount: unsigned.candidateBatchByteCount,
            candidateBatchSequence: unsigned.candidateBatchSequence,
            candidateBatchExpiresAtMs: unsigned.candidateBatchExpiresAtMs,
            maximumCandidateBytes: unsigned.maximumCandidateBytes,
            maxOperations: unsigned.maxOperations,
            singleUseNonce: unsigned.singleUseNonce,
            issuedAtMs: unsigned.issuedAtMs,
            notBeforeMs: unsigned.notBeforeMs,
            expiresAtMs: unsigned.expiresAtMs,
            endpointOperationProofDigest: unsigned.endpointOperationProofDigest,
            serviceSignature: ProductionC1InternalBridge.sign(
                unsigned.signingTranscript,
                using: signingKey
            ),
            validateSignature: true
        )
    }

    public init(canonicalBytes data: Data) throws {
        guard data.count >= 6 else { throw ProductionC1CandidateCapabilityError.malformedCanonical }
        let operation: ProductionC1CandidateOperation
        switch data[data.startIndex + 4] {
        case ProductionC1CandidateCapabilityContract.publishObjectType: operation = .publish
        case ProductionC1CandidateCapabilityContract.fetchObjectType: operation = .fetch
        default: throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        let fields = try ProductionC1InternalBridge.decode(
            data,
            objectType: operation.objectType,
            fieldCount: 34,
            maximumBytes: ProductionC1CandidateCapabilityContract.maximumCapabilityBytes
        )
        guard try ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.suite,
              try ProductionC1InternalBridge.text(fields[1]) == operation.rawValue,
              let requester = P2PNATRole(rawValue: try ProductionC1InternalBridge.text(fields[17])),
              let owner = P2PNATRole(rawValue: try ProductionC1InternalBridge.text(fields[19])),
              try ProductionC1InternalBridge.text(fields[32]) == ProductionC1Contract.signatureAlgorithm else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        try self.init(
            operation: operation,
            serviceIdDigest: ProductionC1InternalBridge.text(fields[2]),
            keysetVersion: ProductionC1InternalBridge.uint64(fields[3]),
            signingKeyId: ProductionC1InternalBridge.text(fields[4]),
            capabilityId: ProductionC1InternalBridge.text(fields[5]),
            pairAuthorityDigest: ProductionC1InternalBridge.text(fields[6]),
            pairBindingDigest: ProductionC1InternalBridge.text(fields[7]),
            pairEpoch: ProductionC1InternalBridge.uint64(fields[8]),
            generation: ProductionC1InternalBridge.uint64(fields[9]),
            serviceConfigVersion: ProductionC1InternalBridge.uint64(fields[10]),
            revocationCounter: ProductionC1InternalBridge.uint64(fields[11]),
            protocolFloor: ProductionC1InternalBridge.uint32(fields[12]),
            clientIdentityFingerprint: ProductionC1InternalBridge.text(fields[13]),
            runtimeIdentityFingerprint: ProductionC1InternalBridge.text(fields[14]),
            sessionId: ProductionC1InternalBridge.text(fields[15]),
            attemptId: ProductionC1InternalBridge.text(fields[16]),
            requesterRole: requester,
            requesterIdentityFingerprint: ProductionC1InternalBridge.text(fields[18]),
            candidateOwnerRole: owner,
            candidateOwnerIdentityFingerprint: ProductionC1InternalBridge.text(fields[20]),
            candidateBatchDigest: ProductionC1InternalBridge.text(fields[21]),
            candidateBatchByteCount: ProductionC1InternalBridge.uint32(fields[22]),
            candidateBatchSequence: ProductionC1InternalBridge.uint64(fields[23]),
            candidateBatchExpiresAtMs: ProductionC1InternalBridge.uint64(fields[24]),
            maximumCandidateBytes: ProductionC1InternalBridge.uint64(fields[25]),
            maxOperations: ProductionC1InternalBridge.uint32(fields[26]),
            singleUseNonce: ProductionC1InternalBridge.text(fields[27]),
            issuedAtMs: ProductionC1InternalBridge.uint64(fields[28]),
            notBeforeMs: ProductionC1InternalBridge.uint64(fields[29]),
            expiresAtMs: ProductionC1InternalBridge.uint64(fields[30]),
            endpointOperationProofDigest: ProductionC1InternalBridge.text(fields[31]),
            serviceSignature: fields[33],
            validateSignature: true
        )
        guard try canonicalBytes() == data else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
    }

    public func canonicalBytes() throws -> Data {
        ProductionC1InternalBridge.encode(
            objectType: operation.objectType,
            fields: claimsFields + [serviceSignature]
        )
    }

    public func digestHex() throws -> String {
        ProductionC1InternalBridge.digestHex(try canonicalBytes())
    }

    fileprivate var signingTranscript: Data {
        ProductionC1InternalBridge.transcript(
            domain: operation.signingDomain,
            claims: ProductionC1InternalBridge.encode(
                objectType: operation.objectType,
                fields: claimsFields
            )
        )
    }

    private var claimsFields: [Data] {
        [
            ProductionC1InternalBridge.ascii(ProductionC1Contract.suite),
            ProductionC1InternalBridge.ascii(operation.rawValue),
            ProductionC1InternalBridge.ascii(serviceIdDigest),
            ProductionC1InternalBridge.be(keysetVersion),
            ProductionC1InternalBridge.ascii(signingKeyId),
            ProductionC1InternalBridge.ascii(capabilityId),
            ProductionC1InternalBridge.ascii(pairAuthorityDigest),
            ProductionC1InternalBridge.ascii(pairBindingDigest),
            ProductionC1InternalBridge.be(pairEpoch),
            ProductionC1InternalBridge.be(generation),
            ProductionC1InternalBridge.be(serviceConfigVersion),
            ProductionC1InternalBridge.be(revocationCounter),
            ProductionC1InternalBridge.be(protocolFloor),
            ProductionC1InternalBridge.ascii(clientIdentityFingerprint),
            ProductionC1InternalBridge.ascii(runtimeIdentityFingerprint),
            ProductionC1InternalBridge.ascii(sessionId),
            ProductionC1InternalBridge.ascii(attemptId),
            ProductionC1InternalBridge.ascii(requesterRole.rawValue),
            ProductionC1InternalBridge.ascii(requesterIdentityFingerprint),
            ProductionC1InternalBridge.ascii(candidateOwnerRole.rawValue),
            ProductionC1InternalBridge.ascii(candidateOwnerIdentityFingerprint),
            ProductionC1InternalBridge.ascii(candidateBatchDigest),
            ProductionC1InternalBridge.be(candidateBatchByteCount),
            ProductionC1InternalBridge.be(candidateBatchSequence),
            ProductionC1InternalBridge.be(candidateBatchExpiresAtMs),
            ProductionC1InternalBridge.be(maximumCandidateBytes),
            ProductionC1InternalBridge.be(maxOperations),
            ProductionC1InternalBridge.ascii(singleUseNonce),
            ProductionC1InternalBridge.be(issuedAtMs),
            ProductionC1InternalBridge.be(notBeforeMs),
            ProductionC1InternalBridge.be(expiresAtMs),
            ProductionC1InternalBridge.ascii(endpointOperationProofDigest),
            ProductionC1InternalBridge.ascii(ProductionC1Contract.signatureAlgorithm),
        ]
    }
}

public struct VerifiedProductionC1CandidateCapability: Equatable, Sendable {
    public let capability: ProductionC1CandidateCapability
    public let canonicalCandidateBatch: Data
    public let candidateBatch: CandidateBatch
    public let capabilityDigest: String
    public let endpointOperationProof: ProductionC1EndpointOperationProof
    public let securityContext: ProductionC1PreauthorizationSessionContext
    fileprivate let verifiedKeyset: VerifiedProductionC1ServiceKeyset

    fileprivate init(
        capability: ProductionC1CandidateCapability,
        canonicalCandidateBatch: Data,
        candidateBatch: CandidateBatch,
        capabilityDigest: String,
        endpointOperationProof: ProductionC1EndpointOperationProof,
        securityContext: ProductionC1PreauthorizationSessionContext,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset
    ) {
        self.capability = capability
        self.canonicalCandidateBatch = canonicalCandidateBatch
        self.candidateBatch = candidateBatch
        self.capabilityDigest = capabilityDigest
        self.endpointOperationProof = endpointOperationProof
        self.securityContext = securityContext
        self.verifiedKeyset = verifiedKeyset
    }
}

public struct VerifiedProductionC1BilateralCandidateCapabilities: Equatable, Sendable {
    public let clientPublish: VerifiedProductionC1CandidateCapability
    public let runtimeFetchClient: VerifiedProductionC1CandidateCapability
    public let runtimePublish: VerifiedProductionC1CandidateCapability
    public let clientFetchRuntime: VerifiedProductionC1CandidateCapability
    public let bilateralPublishDigest: String
    public let bilateralFetchDigest: String

    fileprivate var all: [VerifiedProductionC1CandidateCapability] {
        [clientPublish, runtimeFetchClient, runtimePublish, clientFetchRuntime]
    }
}

public struct VerifiedProductionC1CandidateP2PPlan: Equatable, Sendable {
    public let bilateral: VerifiedProductionC1BilateralCandidateCapabilities
    public let pathValidationReceipt: PathValidationReceipt
    public let pathValidationReceiptDigest: String
    public let selectedClientCandidate: P2PNATCandidate
    public let selectedRuntimeCandidate: P2PNATCandidate
    public let effectiveNotBeforeMs: UInt64
    public let expiresAtMs: UInt64
    fileprivate let basePlan: VerifiedProductionC1RoutePlan

    public var claims: ProductionC1RoutePlanClaims { basePlan.claims }
    public var capability: ProductionC1RouteCapability { basePlan.capability }
    public var securityContext: ProductionC1PreauthorizationSessionContext { basePlan.securityContext }
}

public struct ProductionC1BilateralRouteAuthorizations: Equatable, Sendable {
    public let clientPublish: ProductionRouteAuthorization
    public let runtimeFetchClient: ProductionRouteAuthorization
    public let runtimePublish: ProductionRouteAuthorization
    public let clientFetchRuntime: ProductionRouteAuthorization
    public let finalP2PDirect: ProductionRouteAuthorization
}

public struct VerifiedProductionC1CandidateP2PConnectorInput: Equatable, @unchecked Sendable {
    public let connector: ProductionC1RouteConnectorMaterial
    public let commitmentDigest: String
    fileprivate let routeHandle: String
    fileprivate let nonce: String
    fileprivate let secret: Data

    fileprivate init(
        connector: ProductionC1RouteConnectorMaterial,
        commitmentDigest: String,
        routeHandle: String,
        nonce: String,
        secret: Data
    ) {
        self.connector = connector
        self.commitmentDigest = commitmentDigest
        self.routeHandle = routeHandle
        self.nonce = nonce
        self.secret = secret
    }
}

/// Verifier-minted, secret-free input to the production P2P key schedule.
///
/// This binding proves that the exact object-7 transcript is authorized by the
/// currently valid object-26 grant before ECDH derivation or key confirmation begins.
public struct VerifiedProductionC1CandidateP2PKeyScheduleBinding: Equatable, Sendable {
    public let transcript: ProductionSecureSessionTranscript
    public let grantAuthorization: VerifiedProductionC1P2PGrantAuthorization
    public let securityContext: ProductionC1PreauthorizationSessionContext
    public let localRole: P2PNATRole

    fileprivate init(
        transcript: ProductionSecureSessionTranscript,
        grantAuthorization: VerifiedProductionC1P2PGrantAuthorization,
        securityContext: ProductionC1PreauthorizationSessionContext,
        localRole: P2PNATRole
    ) {
        self.transcript = transcript
        self.grantAuthorization = grantAuthorization
        self.securityContext = securityContext
        self.localRole = localRole
    }
}

public struct VerifiedProductionC1CandidateP2PTranscriptBinding: Equatable, Sendable {
    public let transcript: ProductionSecureSessionTranscript
    public let grant: VerifiedProductionC1P2PGrantEvidence
    public let connectorInput: VerifiedProductionC1CandidateP2PConnectorInput
    public let securityContext: ProductionC1PreauthorizationSessionContext
    /// Secret-free runtime view minted alongside the client endpoint binding.
    /// Production callers cannot manufacture or substitute this value.
    public let runtimeKeyScheduleBinding:
        VerifiedProductionC1CandidateP2PKeyScheduleBinding
    fileprivate let keyConfirmationKey: Data
    fileprivate let presentedPeerKeyConfirmation: Data

    fileprivate init(
        transcript: ProductionSecureSessionTranscript,
        grant: VerifiedProductionC1P2PGrantEvidence,
        connectorInput: VerifiedProductionC1CandidateP2PConnectorInput,
        securityContext: ProductionC1PreauthorizationSessionContext,
        runtimeKeyScheduleBinding:
            VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        keyConfirmationKey: Data,
        presentedPeerKeyConfirmation: Data
    ) {
        self.transcript = transcript
        self.grant = grant
        self.connectorInput = connectorInput
        self.securityContext = securityContext
        self.runtimeKeyScheduleBinding = runtimeKeyScheduleBinding
        self.keyConfirmationKey = keyConfirmationKey
        self.presentedPeerKeyConfirmation = presentedPeerKeyConfirmation
    }
}

public struct VerifiedProductionC1CandidateP2PInboundMaterial: Equatable, Sendable {
    public let observedPeerCandidate: P2PNATCandidate
    public let peerKeyConfirmationDigest: String
    public let transcriptDigest: String
    public let routeGrantDigest: String
    public let grantAuthorizationDigest: String
    public let sessionId: String

    fileprivate init(
        observedPeerCandidate: P2PNATCandidate,
        peerKeyConfirmationDigest: String,
        transcriptDigest: String,
        routeGrantDigest: String,
        grantAuthorizationDigest: String,
        sessionId: String
    ) {
        self.observedPeerCandidate = observedPeerCandidate
        self.peerKeyConfirmationDigest = peerKeyConfirmationDigest
        self.transcriptDigest = transcriptDigest
        self.routeGrantDigest = routeGrantDigest
        self.grantAuthorizationDigest = grantAuthorizationDigest
        self.sessionId = sessionId
    }
}

public struct VerifiedProductionC1CandidateP2PInboundTranscriptBinding: Equatable, Sendable {
    public let transcript: ProductionSecureSessionTranscript
    public let grant: VerifiedProductionC1P2PGrantEvidence
    public let inboundMaterial: VerifiedProductionC1CandidateP2PInboundMaterial
    public let securityContext: ProductionC1PreauthorizationSessionContext

    fileprivate init(
        transcript: ProductionSecureSessionTranscript,
        grant: VerifiedProductionC1P2PGrantEvidence,
        inboundMaterial: VerifiedProductionC1CandidateP2PInboundMaterial,
        securityContext: ProductionC1PreauthorizationSessionContext
    ) {
        self.transcript = transcript
        self.grant = grant
        self.inboundMaterial = inboundMaterial
        self.securityContext = securityContext
    }
}

public enum ProductionC1P2PDestinationPolicy: Equatable, Sendable {
    case publicOnly

    public static let policyId = "public_only_special_use_deny_iana_2025_10_09_v1"
    public static let policyVersion: UInt64 = 1
    public static let initiatorRole: P2PNATRole = .client
    public static let connectorTargetRole: P2PNATRole = .runtime
}

public enum ProductionC1PublicOnlyV1Policy {
    public static let id = ProductionC1P2PDestinationPolicy.policyId
    public static let version = ProductionC1P2PDestinationPolicy.policyVersion

    public static func allows(address: Data, port: UInt16) -> Bool {
        guard port >= 1_024 else { return false }
        let bytes = [UInt8](address)
        if bytes.count == 4 {
            return !ipv4SpecialUse.contains { prefixMatches(bytes, $0.0, $0.1) }
        }
        guard bytes.count == 16, (bytes[0] & 0xe0) == 0x20 else { return false }
        return !ipv6SpecialUse.contains { prefixMatches(bytes, $0.0, $0.1) }
    }

    // IANA special-purpose registries snapshot: 2025-10-09. This policy
    // intentionally denies globally-reachable exceptions as well.
    private static let ipv4SpecialUse: [([UInt8], Int)] = [
        ([0, 0, 0, 0], 8), ([10, 0, 0, 0], 8), ([100, 64, 0, 0], 10),
        ([127, 0, 0, 0], 8), ([169, 254, 0, 0], 16), ([172, 16, 0, 0], 12),
        ([192, 0, 0, 0], 24), ([192, 0, 2, 0], 24), ([192, 31, 196, 0], 24),
        ([192, 52, 193, 0], 24), ([192, 88, 99, 0], 24), ([192, 168, 0, 0], 16),
        ([192, 175, 48, 0], 24), ([198, 18, 0, 0], 15),
        ([198, 51, 100, 0], 24), ([203, 0, 113, 0], 24),
        ([224, 0, 0, 0], 4), ([240, 0, 0, 0], 4),
    ]

    private static let ipv6SpecialUse: [([UInt8], Int)] = [
        ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 128),
        ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1], 128),
        ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff, 0, 0, 0, 0], 96),
        ([0x00, 0x64, 0xff, 0x9b] + Array(repeating: 0, count: 12), 96),
        ([0x00, 0x64, 0xff, 0x9b, 0x00, 0x01] + Array(repeating: 0, count: 10), 48),
        ([0x01, 0x00] + Array(repeating: 0, count: 14), 64),
        ([0x20, 0x01] + Array(repeating: 0, count: 14), 23),
        ([0x20, 0x01, 0x00, 0x00] + Array(repeating: 0, count: 12), 32),
        ([0x20, 0x01, 0x00, 0x01] + Array(repeating: 0, count: 10) + [0, 1], 128),
        ([0x20, 0x01, 0x00, 0x01] + Array(repeating: 0, count: 10) + [0, 2], 128),
        ([0x20, 0x01, 0x00, 0x02] + Array(repeating: 0, count: 12), 48),
        ([0x20, 0x01, 0x00, 0x03] + Array(repeating: 0, count: 12), 32),
        ([0x20, 0x01, 0x00, 0x04, 0x01, 0x12] + Array(repeating: 0, count: 10), 48),
        ([0x20, 0x01, 0x00, 0x10] + Array(repeating: 0, count: 12), 28),
        ([0x20, 0x01, 0x00, 0x20] + Array(repeating: 0, count: 12), 28),
        ([0x20, 0x01, 0x00, 0x30] + Array(repeating: 0, count: 12), 28),
        ([0x20, 0x01, 0x0d, 0xb8] + Array(repeating: 0, count: 12), 32),
        ([0x20, 0x02] + Array(repeating: 0, count: 14), 16),
        ([0x26, 0x20, 0x00, 0x4f, 0x80, 0x00] + Array(repeating: 0, count: 10), 48),
        ([0x3f, 0xff] + Array(repeating: 0, count: 14), 20),
        ([0x5f, 0x00] + Array(repeating: 0, count: 14), 16),
        ([0xfc, 0x00] + Array(repeating: 0, count: 14), 7),
        ([0xfe, 0x80] + Array(repeating: 0, count: 14), 10),
        ([0xff, 0x00] + Array(repeating: 0, count: 14), 8),
    ]

    private static func prefixMatches(
        _ address: [UInt8],
        _ prefix: [UInt8],
        _ bitCount: Int
    ) -> Bool {
        guard address.count == prefix.count else { return false }
        let wholeBytes = bitCount / 8
        let remainingBits = bitCount % 8
        guard address.prefix(wholeBytes).elementsEqual(prefix.prefix(wholeBytes)) else {
            return false
        }
        guard remainingBits > 0 else { return true }
        let mask = UInt8.max << (8 - remainingBits)
        return (address[wholeBytes] & mask) == (prefix[wholeBytes] & mask)
    }
}

public enum ProductionC1CandidateVerifier {
    public static func requireProductionP2PActivationPersistence() throws {
        throw ProductionC1CandidateCapabilityError.persistenceUnavailable
    }

    public static func verifyCapability(
        _ capability: ProductionC1CandidateCapability,
        candidateBatchCanonicalBytes: Data,
        endpointOperationProof: ProductionC1EndpointOperationProof,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1CandidateCapability {
        let batch = try CandidateBatch(canonicalBytes: candidateBatchCanonicalBytes)
        guard batch.canonicalBytes() == candidateBatchCanonicalBytes else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        let verified = VerifiedProductionC1CandidateCapability(
            capability: capability,
            canonicalCandidateBatch: candidateBatchCanonicalBytes,
            candidateBatch: batch,
            capabilityDigest: try capability.digestHex(),
            endpointOperationProof: endpointOperationProof,
            securityContext: securityContext,
            verifiedKeyset: verifiedKeyset
        )
        try validateUse(verified, authority: authority, nowMs: nowMs)
        return verified
    }

    public static func verifyBilateral(
        clientPublish: VerifiedProductionC1CandidateCapability,
        runtimeFetchClient: VerifiedProductionC1CandidateCapability,
        runtimePublish: VerifiedProductionC1CandidateCapability,
        clientFetchRuntime: VerifiedProductionC1CandidateCapability,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1BilateralCandidateCapabilities {
        let values = [clientPublish, runtimeFetchClient, runtimePublish, clientFetchRuntime]
        for value in values { try validateUse(value, authority: authority, nowMs: nowMs) }
        try requireShape(clientPublish, operation: .publish, requester: .client, owner: .client)
        try requireShape(runtimeFetchClient, operation: .fetch, requester: .runtime, owner: .client)
        try requireShape(runtimePublish, operation: .publish, requester: .runtime, owner: .runtime)
        try requireShape(clientFetchRuntime, operation: .fetch, requester: .client, owner: .runtime)
        let expectedKeysetBytes = try clientPublish.verifiedKeyset.keyset.canonicalBytes()
        guard try values.allSatisfy({ value in
            try value.verifiedKeyset.keyset.canonicalBytes() == expectedKeysetBytes
        }) else {
            throw ProductionC1CandidateCapabilityError.authorityMismatch
        }
        let first = clientPublish.capability
        guard values.allSatisfy({ value in
            let candidate = value.capability
            return candidate.serviceIdDigest == first.serviceIdDigest
                && candidate.keysetVersion == first.keysetVersion
                && candidate.pairAuthorityDigest == first.pairAuthorityDigest
                && candidate.pairBindingDigest == first.pairBindingDigest
                && candidate.pairEpoch == first.pairEpoch
                && candidate.generation == first.generation
                && candidate.serviceConfigVersion == first.serviceConfigVersion
                && candidate.revocationCounter == first.revocationCounter
                && candidate.protocolFloor == first.protocolFloor
                && candidate.clientIdentityFingerprint == first.clientIdentityFingerprint
                && candidate.runtimeIdentityFingerprint == first.runtimeIdentityFingerprint
                && candidate.sessionId == first.sessionId
                && candidate.attemptId == first.attemptId
                && value.endpointOperationProof.securityContextDigest
                    == clientPublish.endpointOperationProof.securityContextDigest
                && value.securityContext == clientPublish.securityContext
                && value.endpointOperationProof.serviceAudienceId
                    == clientPublish.endpointOperationProof.serviceAudienceId
                && value.endpointOperationProof.initiatorRole
                    == clientPublish.endpointOperationProof.initiatorRole
        }), Set(values.map(\.capability.capabilityId)).count == 4,
            Set(values.map(\.endpointOperationProof.proofId)).count == 4,
            Set(values.map(\.capability.singleUseNonce)).count == 4 else {
            throw ProductionC1CandidateCapabilityError.authorityMismatch
        }
        guard clientPublish.canonicalCandidateBatch == runtimeFetchClient.canonicalCandidateBatch,
              runtimePublish.canonicalCandidateBatch == clientFetchRuntime.canonicalCandidateBatch,
              clientPublish.capability.candidateBatchDigest
                == runtimeFetchClient.capability.candidateBatchDigest,
              runtimePublish.capability.candidateBatchDigest
                == clientFetchRuntime.capability.candidateBatchDigest,
              clientPublish.capability.candidateBatchDigest
                != runtimePublish.capability.candidateBatchDigest else {
            throw ProductionC1CandidateCapabilityError.batchMismatch
        }
        return VerifiedProductionC1BilateralCandidateCapabilities(
            clientPublish: clientPublish,
            runtimeFetchClient: runtimeFetchClient,
            runtimePublish: runtimePublish,
            clientFetchRuntime: clientFetchRuntime,
            bilateralPublishDigest: try aggregateDigest(
                domain: "AetherLink G1a-C bilateral candidate-publish set v1",
                clientDigest: clientPublish.capabilityDigest,
                runtimeDigest: runtimePublish.capabilityDigest
            ),
            bilateralFetchDigest: try aggregateDigest(
                domain: "AetherLink G1a-C bilateral candidate-fetch set v1",
                clientDigest: clientFetchRuntime.capabilityDigest,
                runtimeDigest: runtimeFetchClient.capabilityDigest
            )
        )
    }

    public static func selectedCandidatePairDigest(
        clientCandidate: P2PNATCandidate,
        runtimeCandidate: P2PNATCandidate
    ) -> String {
        var claims = Data()
        for (role, candidate) in [
            ("client", clientCandidate), ("runtime", runtimeCandidate),
        ] {
            let roleBytes = ProductionC1InternalBridge.ascii(role)
            let candidateBytes = candidate.encodedBytes
            claims.append(ProductionC1InternalBridge.be(UInt32(roleBytes.count)))
            claims.append(roleBytes)
            claims.append(ProductionC1InternalBridge.be(UInt32(candidateBytes.count)))
            claims.append(candidateBytes)
        }
        return candidateDomainDigest(
            "AetherLink G1a-C selected direct candidate-pair v1",
            claims: claims
        )
    }

    public static func verifyP2PDirectPlan(
        claims: ProductionC1RoutePlanClaims,
        capability: ProductionC1RouteCapability,
        securityContext: ProductionC1PreauthorizationSessionContext,
        bilateral: VerifiedProductionC1BilateralCandidateCapabilities,
        selectedClientCandidate: P2PNATCandidate,
        selectedRuntimeCandidate: P2PNATCandidate,
        pathValidationReceiptCanonicalBytes: Data,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        destinationPolicy: ProductionC1P2PDestinationPolicy = .publicOnly,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1CandidateP2PPlan {
        try validateBilateralUse(bilateral, authority: authority, nowMs: nowMs)
        guard try verifiedKeyset.keyset.canonicalBytes()
                == bilateral.clientPublish.verifiedKeyset.keyset.canonicalBytes() else {
            throw ProductionC1CandidateCapabilityError.authorityMismatch
        }
        guard claims.kind == .p2pDirect, securityContext.routeKind == .p2pDirect,
              securityContext.sessionId == bilateral.clientPublish.capability.sessionId,
              bilateral.all.allSatisfy({ $0.securityContext == securityContext }) else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        try validateDestination(
            claims.connector.addressBytes,
            port: claims.connector.port,
            policy: destinationPolicy
        )
        let selectedPairDigest = try validateSelectedCandidates(
            bilateral: bilateral,
            client: selectedClientCandidate,
            runtime: selectedRuntimeCandidate,
            connector: claims.connector
        )
        let receipt = try PathValidationReceipt(
            freshCanonicalBytes: pathValidationReceiptCanonicalBytes,
            now: nowMs
        )
        guard receipt.canonicalBytes() == pathValidationReceiptCanonicalBytes,
              receipt.transport == .direct,
              receipt.sessionId == securityContext.sessionId,
              receipt.generation == authority.generation,
              receipt.candidatePairDigest == selectedPairDigest,
              nowMs < receipt.expires else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        let receiptDigest = ProductionC1InternalBridge.digestHex(pathValidationReceiptCanonicalBytes)
        let base = try ProductionC1Verifier.verifyCandidateP2PRoutePlanBase(
            claims: claims,
            capability: capability,
            securityContext: securityContext,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            nowMs: nowMs
        )
        let keyset = bilateral.clientPublish.verifiedKeyset.keyset
        let delegatedExpiries = try bilateral.all.map { value -> UInt64 in
            guard let delegated = keyset.delegatedKeys.first(where: {
                $0.keyId == value.capability.signingKeyId
                    && $0.purposes.contains(value.capability.operation.keyPurpose)
            }) else { throw ProductionC1CandidateCapabilityError.authorityMismatch }
            return delegated.expiresAtMs
        }
        guard let routeDelegated = keyset.delegatedKeys.first(where: {
            $0.keyId == capability.signingKeyId
                && $0.purposes.contains(.routeCapability)
        }) else { throw ProductionC1CandidateCapabilityError.authorityMismatch }
        let notBefore = ([
            claims.notBeforeMs, capability.notBeforeMs, receipt.validatedAt,
        ] + bilateral.all.flatMap {
            [$0.capability.notBeforeMs, $0.endpointOperationProof.notBeforeMs]
        }).max() ?? 0
        let expires = ([
            receipt.expires, claims.expiresAtMs, capability.expiresAtMs,
            keyset.expiresAtMs, routeDelegated.expiresAtMs,
        ] + delegatedExpiries + bilateral.all.flatMap {
            [
                $0.capability.expiresAtMs, $0.endpointOperationProof.expiresAtMs,
                $0.candidateBatch.expires,
            ]
        }).min() ?? 0
        guard claims.selectedPathReceiptDigest == receiptDigest,
              nowMs >= notBefore, nowMs < expires else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        return VerifiedProductionC1CandidateP2PPlan(
            bilateral: bilateral,
            pathValidationReceipt: receipt,
            pathValidationReceiptDigest: receiptDigest,
            selectedClientCandidate: selectedClientCandidate,
            selectedRuntimeCandidate: selectedRuntimeCandidate,
            effectiveNotBeforeMs: notBefore,
            expiresAtMs: expires,
            basePlan: base
        )
    }

    public static func makeBilateralRouteAuthorizations(
        for plan: VerifiedProductionC1CandidateP2PPlan,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> ProductionC1BilateralRouteAuthorizations {
        try validatePlanUse(plan, authority: authority, nowMs: nowMs)
        let bilateral = plan.bilateral
        let clientPublish = publishAuthorization(bilateral.clientPublish)
        let runtimeFetchClient = fetchAuthorization(bilateral.runtimeFetchClient)
        let runtimePublish = publishAuthorization(bilateral.runtimePublish)
        let clientFetchRuntime = fetchAuthorization(bilateral.clientFetchRuntime)
        let final = ProductionRouteAuthorization.p2pDirect(
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            generation: authority.generation,
            candidatePairDigest: plan.pathValidationReceipt.candidatePairDigest,
            pathValidationReceiptDigest: plan.pathValidationReceiptDigest,
            publishCapabilityDigest: bilateral.bilateralPublishDigest,
            fetchCapabilityDigest: bilateral.bilateralFetchDigest
        )
        _ = try final.canonicalBytes()
        return ProductionC1BilateralRouteAuthorizations(
            clientPublish: clientPublish,
            runtimeFetchClient: runtimeFetchClient,
            runtimePublish: runtimePublish,
            clientFetchRuntime: clientFetchRuntime,
            finalP2PDirect: final
        )
    }

    static func validateUse(
        _ verified: VerifiedProductionC1CandidateCapability,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws {
        let capability = verified.capability
        let batch = verified.candidateBatch
        let proof = verified.endpointOperationProof
        let context = verified.securityContext
        guard authority.status == .active,
              capability.pairAuthorityDigest == (try authority.digestHex()),
              capability.pairBindingDigest == authority.pairBindingDigest,
              capability.pairEpoch == authority.pairEpoch,
              capability.generation == authority.generation,
              capability.serviceConfigVersion == authority.serviceConfigVersion,
              capability.revocationCounter == authority.revocationCounter,
              capability.protocolFloor == authority.protocolFloor,
              capability.clientIdentityFingerprint == authority.clientIdentityFingerprint,
              capability.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint,
              capability.serviceIdDigest == verified.verifiedKeyset.keyset.serviceIdDigest,
              capability.keysetVersion == verified.verifiedKeyset.keyset.keysetVersion,
              capability.keysetVersion == authority.keysetVersion else {
            throw ProductionC1CandidateCapabilityError.authorityMismatch
        }
        let requesterIdentity = capability.requesterRole == .client
            ? authority.clientIdentityFingerprint : authority.runtimeIdentityFingerprint
        guard try proof.digestHex() == capability.endpointOperationProofDigest,
              proof.operation == capability.operation,
              proof.requesterRole == capability.requesterRole,
              proof.requesterIdentityFingerprint == requesterIdentity,
              proof.candidateOwnerRole == capability.candidateOwnerRole,
              proof.candidateOwnerIdentityFingerprint
                == capability.candidateOwnerIdentityFingerprint,
              proof.sessionId == capability.sessionId,
              proof.attemptId == capability.attemptId,
              proof.capabilityId == capability.capabilityId,
              proof.candidateBatchDigest == capability.candidateBatchDigest,
              proof.candidateBatchSequence == capability.candidateBatchSequence,
              proof.singleUseNonce == capability.singleUseNonce,
              proof.securityContextDigest == context.digestHex(),
              proof.pairAuthorityDigest == capability.pairAuthorityDigest,
              proof.serviceAudienceId == capability.serviceIdDigest,
              proof.initiatorRole == .client,
              capability.issuedAtMs >= proof.issuedAtMs,
              proof.notBeforeMs <= capability.notBeforeMs,
              proof.expiresAtMs >= capability.expiresAtMs,
              context.sessionId == capability.sessionId,
              context.pairBindingDigest == capability.pairBindingDigest,
              context.pairEpoch == capability.pairEpoch,
              context.generation == capability.generation,
              context.serviceConfigVersion == capability.serviceConfigVersion,
              context.keysetVersion == capability.keysetVersion,
              context.revocationCounter == capability.revocationCounter,
              context.clientIdentityFingerprint == authority.clientIdentityFingerprint,
              context.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint else {
            throw ProductionC1CandidateCapabilityError.roleMismatch
        }
        try ProductionC1InternalBridge.validateWindow(
            issuedAtMs: proof.issuedAtMs,
            notBeforeMs: proof.notBeforeMs,
            expiresAtMs: proof.expiresAtMs,
            maximumLifetimeMs: ProductionC1CandidateCapabilityContract.maximumLifetimeMs,
            nowMs: nowMs
        )
        let endpointPublicKey = try P256.Signing.PublicKey(
            x963Representation: proof.requesterPublicKeyX963
        )
        try ProductionC1InternalBridge.verify(
            signature: proof.endpointSignature,
            transcript: proof.signingTranscript,
            publicKey: endpointPublicKey
        )
        let batchBytes = verified.canonicalCandidateBatch
        guard batch.canonicalBytes() == batchBytes,
              ProductionC1InternalBridge.digestHex(batchBytes) == capability.candidateBatchDigest,
              batchBytes.count == Int(capability.candidateBatchByteCount),
              batch.sessionId == capability.sessionId,
              batch.generation == capability.generation,
              batch.sequence == capability.candidateBatchSequence,
              batch.expires == capability.candidateBatchExpiresAtMs,
              batch.role == capability.candidateOwnerRole,
              nowMs < batch.expires,
              P2PNATFreshness.isFresh(expires: batch.expires, now: nowMs) else {
            throw ProductionC1CandidateCapabilityError.batchMismatch
        }
        try ProductionC1InternalBridge.validateWindow(
            issuedAtMs: capability.issuedAtMs,
            notBeforeMs: capability.notBeforeMs,
            expiresAtMs: capability.expiresAtMs,
            maximumLifetimeMs: ProductionC1CandidateCapabilityContract.maximumLifetimeMs,
            nowMs: nowMs
        )
        let signingKey = try ProductionC1InternalBridge.delegatedSigningKey(
            id: capability.signingKeyId,
            purpose: capability.operation.keyPurpose,
            in: verified.verifiedKeyset,
            nowMs: nowMs
        )
        try ProductionC1InternalBridge.verify(
            signature: capability.serviceSignature,
            transcript: capability.signingTranscript,
            publicKey: signingKey
        )
    }

    static func validatePlanUse(
        _ plan: VerifiedProductionC1CandidateP2PPlan,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws {
        try validateBilateralUse(plan.bilateral, authority: authority, nowMs: nowMs)
        try validateDestination(
            plan.claims.connector.addressBytes,
            port: plan.claims.connector.port,
            policy: .publicOnly
        )
        let selectedPairDigest = try validateSelectedCandidates(
            bilateral: plan.bilateral,
            client: plan.selectedClientCandidate,
            runtime: plan.selectedRuntimeCandidate,
            connector: plan.claims.connector
        )
        guard nowMs >= plan.effectiveNotBeforeMs, nowMs < plan.expiresAtMs,
              plan.pathValidationReceipt.transport == .direct,
              plan.pathValidationReceipt.sessionId == plan.securityContext.sessionId,
              plan.pathValidationReceipt.generation == authority.generation,
              plan.pathValidationReceipt.candidatePairDigest == selectedPairDigest,
              plan.pathValidationReceiptDigest == plan.claims.selectedPathReceiptDigest,
              P2PNATFreshness.isPathValidationFresh(
                validatedAt: plan.pathValidationReceipt.validatedAt,
                expires: plan.pathValidationReceipt.expires,
                now: nowMs
              ) else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        _ = try ProductionC1Verifier.makeCandidateP2PRouteAuthorizationBase(
            for: plan.basePlan,
            nowMs: nowMs
        )
    }

    private static func validateBilateralUse(
        _ bilateral: VerifiedProductionC1BilateralCandidateCapabilities,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws {
        let refreshed = try verifyBilateral(
            clientPublish: bilateral.clientPublish,
            runtimeFetchClient: bilateral.runtimeFetchClient,
            runtimePublish: bilateral.runtimePublish,
            clientFetchRuntime: bilateral.clientFetchRuntime,
            authority: authority,
            nowMs: nowMs
        )
        guard refreshed == bilateral else {
            throw ProductionC1CandidateCapabilityError.authorityMismatch
        }
    }

    private static func requireShape(
        _ value: VerifiedProductionC1CandidateCapability,
        operation: ProductionC1CandidateOperation,
        requester: P2PNATRole,
        owner: P2PNATRole
    ) throws {
        guard value.capability.operation == operation,
              value.capability.requesterRole == requester,
              value.capability.candidateOwnerRole == owner else {
            throw ProductionC1CandidateCapabilityError.roleMismatch
        }
    }

    private static func aggregateDigest(
        domain: String,
        clientDigest: String,
        runtimeDigest: String
    ) throws -> String {
        var claims = Data()
        for (role, digest) in [("client", clientDigest), ("runtime", runtimeDigest)] {
            let roleBytes = ProductionC1InternalBridge.ascii(role)
            let digestBytes = try ProductionC1InternalBridge.rawDigest(digest)
            claims.append(ProductionC1InternalBridge.be(UInt32(roleBytes.count)))
            claims.append(roleBytes)
            claims.append(ProductionC1InternalBridge.be(UInt32(digestBytes.count)))
            claims.append(digestBytes)
        }
        return ProductionC1InternalBridge.digestHex(
            ProductionC1InternalBridge.transcript(domain: domain, claims: claims)
        )
    }

    private static func validateSelectedCandidates(
        bilateral: VerifiedProductionC1BilateralCandidateCapabilities,
        client: P2PNATCandidate,
        runtime: P2PNATCandidate,
        connector: ProductionC1RouteConnectorMaterial
    ) throws -> String {
        let directKinds: Set<CandidateKind> = [.host, .srflx, .prflx]
        guard directKinds.contains(client.kind), directKinds.contains(runtime.kind),
              client.transport == .udp, runtime.transport == .udp,
              client.family == runtime.family,
              client.address.count == runtime.address.count,
              bilateral.clientPublish.candidateBatch.candidates.contains(client),
              bilateral.runtimePublish.candidateBatch.candidates.contains(runtime),
              connector.addressBytes == runtime.address,
              connector.port == runtime.port else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        try validateDestination(client.address, port: client.port, policy: .publicOnly)
        try validateDestination(runtime.address, port: runtime.port, policy: .publicOnly)
        return selectedCandidatePairDigest(
            clientCandidate: client,
            runtimeCandidate: runtime
        )
    }

    private static func publishAuthorization(
        _ verified: VerifiedProductionC1CandidateCapability
    ) -> ProductionRouteAuthorization {
        let value = verified.capability
        return .p2pPublish(
            pairBindingDigest: value.pairBindingDigest,
            pairEpoch: value.pairEpoch,
            generation: value.generation,
            candidateBatchDigest: value.candidateBatchDigest,
            publishCapabilityDigest: verified.capabilityDigest
        )
    }

    private static func fetchAuthorization(
        _ verified: VerifiedProductionC1CandidateCapability
    ) -> ProductionRouteAuthorization {
        let value = verified.capability
        return .p2pFetch(
            pairBindingDigest: value.pairBindingDigest,
            pairEpoch: value.pairEpoch,
            generation: value.generation,
            candidateBatchDigest: value.candidateBatchDigest,
            fetchCapabilityDigest: verified.capabilityDigest
        )
    }

    private static func validateDestination(
        _ address: Data,
        port: UInt16,
        policy: ProductionC1P2PDestinationPolicy
    ) throws {
        guard policy == .publicOnly,
              ProductionC1PublicOnlyV1Policy.allows(address: address, port: port) else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
    }
}

public enum ProductionC1CandidateCASDisposition: String, Sendable {
    case applied
    case idempotent
}

public struct ProductionC1CandidateUsageEntry: Equatable, Sendable {
    public let requestId: String
    public let requestDigest: String
    public let capabilityDigest: String
    public let authorizationDigest: String
    public let singleUseNonce: String
    public let consumedBytes: UInt64
    public let receiptDigest: String
    public let committedRevision: UInt64
}

public struct ProductionC1CandidateUsageLedgerState: Equatable, Sendable {
    public let revision: UInt64
    public let remainingOperations: UInt64
    public let remainingBytes: UInt64
    public let retentionLimit: UInt32
    public let entries: [ProductionC1CandidateUsageEntry]

    public init(
        revision: UInt64 = 1,
        remainingOperations: UInt64,
        remainingBytes: UInt64,
        retentionLimit: UInt32,
        entries: [ProductionC1CandidateUsageEntry] = []
    ) throws {
        guard revision > 0,
              retentionLimit > 0, entries.count <= Int(retentionLimit),
              Set(entries.map(\.requestId)).count == entries.count,
              Set(entries.map(\.singleUseNonce)).count == entries.count,
              Set(entries.map(\.capabilityDigest)).count == entries.count,
              Set(entries.map(\.receiptDigest)).count == entries.count else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        var previousCommittedRevision: UInt64 = 0
        for entry in entries {
            for digest in [
                entry.requestId, entry.requestDigest, entry.capabilityDigest,
                entry.authorizationDigest, entry.singleUseNonce, entry.receiptDigest,
            ] { try ProductionC1InternalBridge.validateDigest(digest) }
            guard entry.consumedBytes > 0,
                  entry.committedRevision > previousCommittedRevision,
                  entry.committedRevision <= revision else {
                throw ProductionC1CandidateCapabilityError.invalidValue
            }
            previousCommittedRevision = entry.committedRevision
        }
        self.revision = revision
        self.remainingOperations = remainingOperations
        self.remainingBytes = remainingBytes
        self.retentionLimit = retentionLimit
        self.entries = entries
    }

    public func snapshotDigestHex() throws -> String {
        var claims = ProductionC1InternalBridge.be(revision)
        claims.append(ProductionC1InternalBridge.be(remainingOperations))
        claims.append(ProductionC1InternalBridge.be(remainingBytes))
        claims.append(ProductionC1InternalBridge.be(retentionLimit))
        claims.append(ProductionC1InternalBridge.be(UInt32(entries.count)))
        for entry in entries {
            for digest in [
                entry.requestId, entry.requestDigest, entry.capabilityDigest,
                entry.authorizationDigest, entry.singleUseNonce, entry.receiptDigest,
            ] { claims.append(try ProductionC1InternalBridge.rawDigest(digest)) }
            claims.append(ProductionC1InternalBridge.be(entry.consumedBytes))
            claims.append(ProductionC1InternalBridge.be(entry.committedRevision))
        }
        return candidateDomainDigest(
            "AetherLink G1a-C candidate usage ledger snapshot v1",
            claims: claims
        )
    }
}

public struct ProductionC1CandidateUsageReceipt: Equatable, Sendable {
    public let entry: ProductionC1CandidateUsageEntry
    public let previousRevision: UInt64
    public let committedRevision: UInt64
}

struct ReadbackConfirmedProductionC1CandidateUsageReceipt: Equatable, Sendable {
    let receipt: ProductionC1CandidateUsageReceipt
    let disposition: ProductionC1CandidateCASDisposition
    let previousStateCoreDigest: String
    let committedStateCoreDigest: String
    let ledgerId: String
    let commitRecordDigest: String

    private init(
        _ receipt: ProductionC1CandidateUsageReceipt,
        disposition: ProductionC1CandidateCASDisposition,
        previousStateCoreDigest: String,
        committedStateCoreDigest: String,
        ledgerId: String,
        commitRecordDigest: String
    ) {
        self.receipt = receipt
        self.disposition = disposition
        self.previousStateCoreDigest = previousStateCoreDigest
        self.committedStateCoreDigest = committedStateCoreDigest
        self.ledgerId = ledgerId
        self.commitRecordDigest = commitRecordDigest
    }

    static func confirm(
        _ preparation: ProductionC1CandidateUsagePreparation,
        committedReadback: ProductionC1CandidateUsageLedgerState,
        ledgerId: String,
        commitRecordDigest: String
    ) throws -> Self {
        try ProductionC1InternalBridge.validateDigest(ledgerId)
        try ProductionC1InternalBridge.validateDigest(commitRecordDigest)
        guard committedReadback == preparation.nextState,
              committedReadback.entries.contains(preparation.receipt.entry) else {
            throw ProductionC1CandidateCapabilityError.revisionMismatch
        }
        if preparation.disposition == .applied {
            guard committedReadback.revision == preparation.receipt.committedRevision else {
                throw ProductionC1CandidateCapabilityError.revisionMismatch
            }
        }
        return Self(
            preparation.receipt,
            disposition: preparation.disposition,
            previousStateCoreDigest: preparation.expectedSnapshotDigest,
            committedStateCoreDigest: try committedReadback.snapshotDigestHex(),
            ledgerId: ledgerId,
            commitRecordDigest: commitRecordDigest
        )
    }
}

public struct ProductionC1CandidateUsagePreparation: Equatable, Sendable {
    public let disposition: ProductionC1CandidateCASDisposition
    public let expectedRevision: UInt64
    public let expectedSnapshotDigest: String
    public let nextState: ProductionC1CandidateUsageLedgerState
    public let receipt: ProductionC1CandidateUsageReceipt
}

public enum ProductionC1CandidateUsageLedger {
    public static func requestDigest(
        requestId: String,
        capabilityDigest: String,
        authorizationDigest: String
    ) throws -> String {
        var claims = try ProductionC1InternalBridge.rawDigest(requestId)
        claims.append(try ProductionC1InternalBridge.rawDigest(capabilityDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(authorizationDigest))
        return candidateDomainDigest(
            "AetherLink G1a-C candidate usage request v1",
            claims: claims
        )
    }

    /// Restores only a previously committed idempotent result after process reload.
    /// It deliberately performs no current-time/keyset validation and cannot create a new effect.
    public static func prepareCommittedRetry(
        state: ProductionC1CandidateUsageLedgerState,
        requestId: String,
        requestDigest: String,
        capabilityCanonicalBytes: Data,
        authorization: ProductionRouteAuthorization
    ) throws -> ProductionC1CandidateUsagePreparation {
        let capability = try ProductionC1CandidateCapability(
            canonicalBytes: capabilityCanonicalBytes
        )
        guard try capability.canonicalBytes() == capabilityCanonicalBytes else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        let capabilityDigest = ProductionC1InternalBridge.digestHex(capabilityCanonicalBytes)
        let authorizationDigest = ProductionC1InternalBridge.digestHex(
            try authorization.canonicalBytes()
        )
        try requireExactAuthorization(
            authorization,
            capability: capability,
            capabilityDigest: capabilityDigest
        )
        let exactRequestDigest = try Self.requestDigest(
            requestId: requestId,
            capabilityDigest: capabilityDigest,
            authorizationDigest: authorizationDigest
        )
        guard requestDigest == exactRequestDigest,
              let existing = state.entries.first(where: { $0.requestId == requestId }),
              existing.requestDigest == requestDigest,
              existing.capabilityDigest == capabilityDigest,
              existing.authorizationDigest == authorizationDigest else {
            throw ProductionC1CandidateCapabilityError.requestConflict
        }
        let receipt = ProductionC1CandidateUsageReceipt(
            entry: existing,
            previousRevision: existing.committedRevision - 1,
            committedRevision: existing.committedRevision
        )
        return ProductionC1CandidateUsagePreparation(
            disposition: .idempotent,
            expectedRevision: state.revision,
            expectedSnapshotDigest: try state.snapshotDigestHex(),
            nextState: state,
            receipt: receipt
        )
    }

    static func prepareConsume(
        state: ProductionC1CandidateUsageLedgerState,
        expectedRevision: UInt64,
        expectedSnapshotDigest: String,
        requestId: String,
        requestDigest: String,
        verifiedCapability: VerifiedProductionC1CandidateCapability,
        authorization: ProductionRouteAuthorization,
        authenticatedLocalRole: P2PNATRole,
        authenticatedLocalIdentityFingerprint: String,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> ProductionC1CandidateUsagePreparation {
        let capability = verifiedCapability.capability
        let proof = verifiedCapability.endpointOperationProof
        guard requestId == proof.proofId,
              authenticatedLocalRole == proof.requesterRole,
              authenticatedLocalIdentityFingerprint
                == proof.requesterIdentityFingerprint else {
            throw ProductionC1CandidateCapabilityError.roleMismatch
        }
        let authorizationBytes = try authorization.canonicalBytes()
        let authorizationDigest = ProductionC1InternalBridge.digestHex(authorizationBytes)
        try requireExactAuthorization(
            authorization,
            verifiedCapability: verifiedCapability
        )
        let expectedRequestDigest = try Self.requestDigest(
            requestId: requestId,
            capabilityDigest: verifiedCapability.capabilityDigest,
            authorizationDigest: authorizationDigest
        )
        guard requestDigest == expectedRequestDigest else {
            throw ProductionC1CandidateCapabilityError.requestConflict
        }
        if let existing = state.entries.first(where: { $0.requestId == requestId }) {
            guard existing.requestDigest == requestDigest,
                  existing.capabilityDigest == verifiedCapability.capabilityDigest,
                  existing.authorizationDigest == authorizationDigest else {
                throw ProductionC1CandidateCapabilityError.requestConflict
            }
            let receipt = ProductionC1CandidateUsageReceipt(
                entry: existing,
                previousRevision: existing.committedRevision - 1,
                committedRevision: existing.committedRevision
            )
            return ProductionC1CandidateUsagePreparation(
                disposition: .idempotent,
                expectedRevision: state.revision,
                expectedSnapshotDigest: try state.snapshotDigestHex(),
                nextState: state,
                receipt: receipt
            )
        }
        try ProductionC1CandidateVerifier.validateUse(
            verifiedCapability,
            authority: authority,
            nowMs: nowMs
        )
        guard state.revision == expectedRevision,
              try state.snapshotDigestHex() == expectedSnapshotDigest else {
            throw ProductionC1CandidateCapabilityError.revisionMismatch
        }
        guard state.entries.count < Int(state.retentionLimit) else {
            throw ProductionC1CandidateCapabilityError.retentionExhausted
        }
        guard !state.entries.contains(where: {
            $0.singleUseNonce == capability.singleUseNonce
                || $0.capabilityDigest == verifiedCapability.capabilityDigest
        }) else {
            throw ProductionC1CandidateCapabilityError.replay
        }
        let bytes = UInt64(capability.candidateBatchByteCount)
        guard state.remainingOperations >= UInt64(capability.maxOperations),
              state.remainingBytes >= bytes,
              state.revision < UInt64.max else {
            throw ProductionC1CandidateCapabilityError.quotaExceeded
        }
        let committedRevision = state.revision + 1
        var receiptClaims = try ProductionC1InternalBridge.rawDigest(requestId)
        receiptClaims.append(try ProductionC1InternalBridge.rawDigest(requestDigest))
        receiptClaims.append(try ProductionC1InternalBridge.rawDigest(verifiedCapability.capabilityDigest))
        receiptClaims.append(try ProductionC1InternalBridge.rawDigest(authorizationDigest))
        receiptClaims.append(try ProductionC1InternalBridge.rawDigest(capability.singleUseNonce))
        receiptClaims.append(ProductionC1InternalBridge.be(bytes))
        receiptClaims.append(ProductionC1InternalBridge.be(state.revision))
        receiptClaims.append(ProductionC1InternalBridge.be(committedRevision))
        let entry = ProductionC1CandidateUsageEntry(
            requestId: requestId,
            requestDigest: requestDigest,
            capabilityDigest: verifiedCapability.capabilityDigest,
            authorizationDigest: authorizationDigest,
            singleUseNonce: capability.singleUseNonce,
            consumedBytes: bytes,
            receiptDigest: candidateDomainDigest(
                "AetherLink G1a-C readback-confirmed candidate usage receipt v1",
                claims: receiptClaims
            ),
            committedRevision: committedRevision
        )
        let next = try ProductionC1CandidateUsageLedgerState(
            revision: committedRevision,
            remainingOperations: state.remainingOperations - UInt64(capability.maxOperations),
            remainingBytes: state.remainingBytes - bytes,
            retentionLimit: state.retentionLimit,
            entries: state.entries + [entry]
        )
        return ProductionC1CandidateUsagePreparation(
            disposition: .applied,
            expectedRevision: state.revision,
            expectedSnapshotDigest: expectedSnapshotDigest,
            nextState: next,
            receipt: ProductionC1CandidateUsageReceipt(
                entry: entry,
                previousRevision: state.revision,
                committedRevision: committedRevision
            )
        )
    }

    static func requireExactAuthorization(
        _ authorization: ProductionRouteAuthorization,
        verifiedCapability: VerifiedProductionC1CandidateCapability
    ) throws {
        let capability = verifiedCapability.capability
        try requireExactAuthorization(
            authorization,
            capability: capability,
            capabilityDigest: verifiedCapability.capabilityDigest
        )
    }

    static func requireExactAuthorization(
        _ authorization: ProductionRouteAuthorization,
        capability: ProductionC1CandidateCapability,
        capabilityDigest: String
    ) throws {
        switch (capability.operation, authorization) {
        case let (.publish, .p2pPublish(pair, epoch, generation, batch, digest)):
            guard pair == capability.pairBindingDigest, epoch == capability.pairEpoch,
                  generation == capability.generation, batch == capability.candidateBatchDigest,
                  digest == capabilityDigest else {
                throw ProductionC1CandidateCapabilityError.routeMismatch
            }
        case let (.fetch, .p2pFetch(pair, epoch, generation, batch, digest)):
            guard pair == capability.pairBindingDigest, epoch == capability.pairEpoch,
                  generation == capability.generation, batch == capability.candidateBatchDigest,
                  digest == capabilityDigest else {
                throw ProductionC1CandidateCapabilityError.routeMismatch
            }
        default:
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
    }
}

public struct ProductionC1P2PGrantEvidence: Equatable, Sendable {
    public static let operationOrder =
        "client_publish,runtime_fetch_client,runtime_publish,client_fetch_runtime"

    public let serviceIdDigest: String
    public let keysetVersion: UInt64
    public let pairAuthorityDigest: String
    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let generation: UInt64
    public let sessionId: String
    public let attemptId: String
    public let clientIdentityFingerprint: String
    public let runtimeIdentityFingerprint: String
    public let clientCandidateBatchDigest: String
    public let clientCandidateBatchByteCount: UInt32
    public let runtimeCandidateBatchDigest: String
    public let runtimeCandidateBatchByteCount: UInt32
    public let operationCapabilityDigests: [String]
    public let operationAuthorizationDigests: [String]
    public let bilateralPublishDigest: String
    public let bilateralFetchDigest: String
    public let candidatePairDigest: String
    public let pathValidationReceiptDigest: String
    public let finalRouteAuthorizationDigest: String
    public let c1RoutePlanClaimsDigest: String
    public let c1RouteCapabilityDigest: String
    public let operationReceiptDigests: [String]
    public let initiatorRole: P2PNATRole
    public let connectorTargetRole: P2PNATRole
    public let destinationPolicyId: String
    public let destinationPolicyVersion: UInt64
    public let securityContextDigest: String
    public let effectiveNotBeforeMs: UInt64
    public let expiresAtMs: UInt64

    fileprivate init(
        serviceIdDigest: String,
        keysetVersion: UInt64,
        pairAuthorityDigest: String,
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        sessionId: String,
        attemptId: String,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        clientCandidateBatchDigest: String,
        clientCandidateBatchByteCount: UInt32,
        runtimeCandidateBatchDigest: String,
        runtimeCandidateBatchByteCount: UInt32,
        operationCapabilityDigests: [String],
        operationAuthorizationDigests: [String],
        bilateralPublishDigest: String,
        bilateralFetchDigest: String,
        candidatePairDigest: String,
        pathValidationReceiptDigest: String,
        finalRouteAuthorizationDigest: String,
        c1RoutePlanClaimsDigest: String,
        c1RouteCapabilityDigest: String,
        operationReceiptDigests: [String],
        initiatorRole: P2PNATRole,
        connectorTargetRole: P2PNATRole,
        destinationPolicyId: String,
        destinationPolicyVersion: UInt64,
        securityContextDigest: String,
        effectiveNotBeforeMs: UInt64,
        expiresAtMs: UInt64
    ) throws {
        let scalarDigests = [
            serviceIdDigest, pairAuthorityDigest, pairBindingDigest,
            clientIdentityFingerprint, runtimeIdentityFingerprint,
            clientCandidateBatchDigest, runtimeCandidateBatchDigest,
            bilateralPublishDigest, bilateralFetchDigest, candidatePairDigest,
            pathValidationReceiptDigest, finalRouteAuthorizationDigest,
            c1RoutePlanClaimsDigest, c1RouteCapabilityDigest, securityContextDigest,
        ]
        for digest in scalarDigests + operationCapabilityDigests
            + operationAuthorizationDigests + operationReceiptDigests {
            try ProductionC1InternalBridge.validateDigest(digest)
        }
        guard keysetVersion > 0, pairEpoch > 0, generation > 0,
              sessionId.utf8.count == 32, candidateIsLowerHex(sessionId),
              attemptId.utf8.count == 64, candidateIsLowerHex(attemptId),
              clientIdentityFingerprint != runtimeIdentityFingerprint,
              clientCandidateBatchByteCount > 0, runtimeCandidateBatchByteCount > 0,
              operationCapabilityDigests.count == 4,
              operationAuthorizationDigests.count == 4,
              operationReceiptDigests.count == 4,
              Set(operationCapabilityDigests).count == 4,
              Set(operationAuthorizationDigests).count == 4,
              Set(operationReceiptDigests).count == 4,
              initiatorRole == ProductionC1P2PDestinationPolicy.initiatorRole,
              connectorTargetRole == ProductionC1P2PDestinationPolicy.connectorTargetRole,
              destinationPolicyId == ProductionC1P2PDestinationPolicy.policyId,
              destinationPolicyVersion == ProductionC1P2PDestinationPolicy.policyVersion,
              effectiveNotBeforeMs < expiresAtMs else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        self.serviceIdDigest = serviceIdDigest
        self.keysetVersion = keysetVersion
        self.pairAuthorityDigest = pairAuthorityDigest
        self.pairBindingDigest = pairBindingDigest
        self.pairEpoch = pairEpoch
        self.generation = generation
        self.sessionId = sessionId
        self.attemptId = attemptId
        self.clientIdentityFingerprint = clientIdentityFingerprint
        self.runtimeIdentityFingerprint = runtimeIdentityFingerprint
        self.clientCandidateBatchDigest = clientCandidateBatchDigest
        self.clientCandidateBatchByteCount = clientCandidateBatchByteCount
        self.runtimeCandidateBatchDigest = runtimeCandidateBatchDigest
        self.runtimeCandidateBatchByteCount = runtimeCandidateBatchByteCount
        self.operationCapabilityDigests = operationCapabilityDigests
        self.operationAuthorizationDigests = operationAuthorizationDigests
        self.bilateralPublishDigest = bilateralPublishDigest
        self.bilateralFetchDigest = bilateralFetchDigest
        self.candidatePairDigest = candidatePairDigest
        self.pathValidationReceiptDigest = pathValidationReceiptDigest
        self.finalRouteAuthorizationDigest = finalRouteAuthorizationDigest
        self.c1RoutePlanClaimsDigest = c1RoutePlanClaimsDigest
        self.c1RouteCapabilityDigest = c1RouteCapabilityDigest
        self.operationReceiptDigests = operationReceiptDigests
        self.initiatorRole = initiatorRole
        self.connectorTargetRole = connectorTargetRole
        self.destinationPolicyId = destinationPolicyId
        self.destinationPolicyVersion = destinationPolicyVersion
        self.securityContextDigest = securityContextDigest
        self.effectiveNotBeforeMs = effectiveNotBeforeMs
        self.expiresAtMs = expiresAtMs
        guard try canonicalBytes().count <= ProductionC1CandidateCapabilityContract.maximumGrantEvidenceBytes else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try ProductionC1InternalBridge.decode(
            data,
            objectType: ProductionC1CandidateCapabilityContract.grantEvidenceObjectType,
            fieldCount: 34,
            maximumBytes: ProductionC1CandidateCapabilityContract.maximumGrantEvidenceBytes
        )
        guard try ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.suite,
              try ProductionC1InternalBridge.uint64(fields[1])
                == ProductionC1CandidateCapabilityContract.revision,
              try ProductionC1InternalBridge.text(fields[16]) == Self.operationOrder else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        try self.init(
            serviceIdDigest: ProductionC1InternalBridge.text(fields[2]),
            keysetVersion: ProductionC1InternalBridge.uint64(fields[3]),
            pairAuthorityDigest: ProductionC1InternalBridge.text(fields[4]),
            pairBindingDigest: ProductionC1InternalBridge.text(fields[5]),
            pairEpoch: ProductionC1InternalBridge.uint64(fields[6]),
            generation: ProductionC1InternalBridge.uint64(fields[7]),
            sessionId: ProductionC1InternalBridge.text(fields[8]),
            attemptId: ProductionC1InternalBridge.text(fields[9]),
            clientIdentityFingerprint: ProductionC1InternalBridge.text(fields[10]),
            runtimeIdentityFingerprint: ProductionC1InternalBridge.text(fields[11]),
            clientCandidateBatchDigest: ProductionC1InternalBridge.text(fields[12]),
            clientCandidateBatchByteCount: ProductionC1InternalBridge.uint32(fields[13]),
            runtimeCandidateBatchDigest: ProductionC1InternalBridge.text(fields[14]),
            runtimeCandidateBatchByteCount: ProductionC1InternalBridge.uint32(fields[15]),
            operationCapabilityDigests: try Self.unpackDigests(fields[17]),
            operationAuthorizationDigests: try Self.unpackDigests(fields[18]),
            bilateralPublishDigest: ProductionC1InternalBridge.text(fields[19]),
            bilateralFetchDigest: ProductionC1InternalBridge.text(fields[20]),
            candidatePairDigest: ProductionC1InternalBridge.text(fields[21]),
            pathValidationReceiptDigest: ProductionC1InternalBridge.text(fields[22]),
            finalRouteAuthorizationDigest: ProductionC1InternalBridge.text(fields[23]),
            c1RoutePlanClaimsDigest: ProductionC1InternalBridge.text(fields[24]),
            c1RouteCapabilityDigest: ProductionC1InternalBridge.text(fields[25]),
            operationReceiptDigests: try Self.unpackDigests(fields[26]),
            initiatorRole: try Self.role(fields[27]),
            connectorTargetRole: try Self.role(fields[28]),
            destinationPolicyId: ProductionC1InternalBridge.text(fields[29]),
            destinationPolicyVersion: ProductionC1InternalBridge.uint64(fields[30]),
            securityContextDigest: ProductionC1InternalBridge.text(fields[31]),
            effectiveNotBeforeMs: ProductionC1InternalBridge.uint64(fields[32]),
            expiresAtMs: ProductionC1InternalBridge.uint64(fields[33])
        )
        guard try canonicalBytes() == data else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
    }

    public func canonicalBytes() throws -> Data {
        ProductionC1InternalBridge.encode(
            objectType: ProductionC1CandidateCapabilityContract.grantEvidenceObjectType,
            fields: [
                ProductionC1InternalBridge.ascii(ProductionC1Contract.suite),
                ProductionC1InternalBridge.be(ProductionC1CandidateCapabilityContract.revision),
                ProductionC1InternalBridge.ascii(serviceIdDigest),
                ProductionC1InternalBridge.be(keysetVersion),
                ProductionC1InternalBridge.ascii(pairAuthorityDigest),
                ProductionC1InternalBridge.ascii(pairBindingDigest),
                ProductionC1InternalBridge.be(pairEpoch),
                ProductionC1InternalBridge.be(generation),
                ProductionC1InternalBridge.ascii(sessionId),
                ProductionC1InternalBridge.ascii(attemptId),
                ProductionC1InternalBridge.ascii(clientIdentityFingerprint),
                ProductionC1InternalBridge.ascii(runtimeIdentityFingerprint),
                ProductionC1InternalBridge.ascii(clientCandidateBatchDigest),
                ProductionC1InternalBridge.be(clientCandidateBatchByteCount),
                ProductionC1InternalBridge.ascii(runtimeCandidateBatchDigest),
                ProductionC1InternalBridge.be(runtimeCandidateBatchByteCount),
                ProductionC1InternalBridge.ascii(Self.operationOrder),
                try Self.packDigests(operationCapabilityDigests),
                try Self.packDigests(operationAuthorizationDigests),
                ProductionC1InternalBridge.ascii(bilateralPublishDigest),
                ProductionC1InternalBridge.ascii(bilateralFetchDigest),
                ProductionC1InternalBridge.ascii(candidatePairDigest),
                ProductionC1InternalBridge.ascii(pathValidationReceiptDigest),
                ProductionC1InternalBridge.ascii(finalRouteAuthorizationDigest),
                ProductionC1InternalBridge.ascii(c1RoutePlanClaimsDigest),
                ProductionC1InternalBridge.ascii(c1RouteCapabilityDigest),
                try Self.packDigests(operationReceiptDigests),
                ProductionC1InternalBridge.ascii(initiatorRole.rawValue),
                ProductionC1InternalBridge.ascii(connectorTargetRole.rawValue),
                ProductionC1InternalBridge.ascii(destinationPolicyId),
                ProductionC1InternalBridge.be(destinationPolicyVersion),
                ProductionC1InternalBridge.ascii(securityContextDigest),
                ProductionC1InternalBridge.be(effectiveNotBeforeMs),
                ProductionC1InternalBridge.be(expiresAtMs),
            ]
        )
    }

    public func digestHex() throws -> String {
        ProductionC1InternalBridge.digestHex(try canonicalBytes())
    }

    private static func packDigests(_ values: [String]) throws -> Data {
        guard values.count == 4 else { throw ProductionC1CandidateCapabilityError.invalidValue }
        return try values.reduce(into: Data()) {
            $0.append(try ProductionC1InternalBridge.rawDigest($1))
        }
    }

    private static func unpackDigests(_ data: Data) throws -> [String] {
        guard data.count == 128 else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        return stride(from: 0, to: data.count, by: 32).map {
            data.subdata(in: $0..<($0 + 32)).map { String(format: "%02x", $0) }.joined()
        }
    }

    private static func role(_ data: Data) throws -> P2PNATRole {
        guard let role = P2PNATRole(rawValue: try ProductionC1InternalBridge.text(data)) else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        return role
    }
}

public struct ProductionC1P2PGrantAuthorization: Equatable, Sendable {
    public let grantEvidenceDigest: String
    public let pairAuthorityDigest: String
    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let generation: UInt64
    public let clientIdentityFingerprint: String
    public let runtimeIdentityFingerprint: String
    public let sessionId: String
    public let attemptId: String
    public let initiatorRole: P2PNATRole
    public let connectorTargetRole: P2PNATRole
    public let destinationPolicyId: String
    public let destinationPolicyVersion: UInt64
    public let securityContextDigest: String
    public let effectiveNotBeforeMs: UInt64
    public let expiresAtMs: UInt64

    fileprivate init(
        grantEvidenceDigest: String,
        pairAuthorityDigest: String,
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        sessionId: String,
        attemptId: String,
        initiatorRole: P2PNATRole,
        connectorTargetRole: P2PNATRole,
        destinationPolicyId: String,
        destinationPolicyVersion: UInt64,
        securityContextDigest: String,
        effectiveNotBeforeMs: UInt64,
        expiresAtMs: UInt64
    ) throws {
        for digest in [
            grantEvidenceDigest, pairAuthorityDigest, pairBindingDigest,
            clientIdentityFingerprint, runtimeIdentityFingerprint, securityContextDigest,
        ] { try ProductionC1InternalBridge.validateDigest(digest) }
        guard pairEpoch > 0, generation > 0,
              clientIdentityFingerprint != runtimeIdentityFingerprint,
              sessionId.utf8.count == 32, candidateIsLowerHex(sessionId),
              attemptId.utf8.count == 64, candidateIsLowerHex(attemptId),
              initiatorRole != connectorTargetRole,
              !destinationPolicyId.isEmpty,
              destinationPolicyVersion > 0,
              effectiveNotBeforeMs < expiresAtMs else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        self.grantEvidenceDigest = grantEvidenceDigest
        self.pairAuthorityDigest = pairAuthorityDigest
        self.pairBindingDigest = pairBindingDigest
        self.pairEpoch = pairEpoch
        self.generation = generation
        self.clientIdentityFingerprint = clientIdentityFingerprint
        self.runtimeIdentityFingerprint = runtimeIdentityFingerprint
        self.sessionId = sessionId
        self.attemptId = attemptId
        self.initiatorRole = initiatorRole
        self.connectorTargetRole = connectorTargetRole
        self.destinationPolicyId = destinationPolicyId
        self.destinationPolicyVersion = destinationPolicyVersion
        self.securityContextDigest = securityContextDigest
        self.effectiveNotBeforeMs = effectiveNotBeforeMs
        self.expiresAtMs = expiresAtMs
        guard try canonicalBytes().count
                <= ProductionC1CandidateCapabilityContract.maximumGrantAuthorizationBytes else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try ProductionC1InternalBridge.decode(
            data,
            objectType: ProductionC1CandidateCapabilityContract.grantAuthorizationObjectType,
            fieldCount: 18,
            maximumBytes:
                ProductionC1CandidateCapabilityContract.maximumGrantAuthorizationBytes
        )
        guard try ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.suite,
              try ProductionC1InternalBridge.uint64(fields[1])
                == ProductionC1CandidateCapabilityContract.revision,
              let initiator = P2PNATRole(
                rawValue: try ProductionC1InternalBridge.text(fields[11])
              ),
              let target = P2PNATRole(
                rawValue: try ProductionC1InternalBridge.text(fields[12])
              ) else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        try self.init(
            grantEvidenceDigest: ProductionC1InternalBridge.text(fields[2]),
            pairAuthorityDigest: ProductionC1InternalBridge.text(fields[3]),
            pairBindingDigest: ProductionC1InternalBridge.text(fields[4]),
            pairEpoch: ProductionC1InternalBridge.uint64(fields[5]),
            generation: ProductionC1InternalBridge.uint64(fields[6]),
            clientIdentityFingerprint: ProductionC1InternalBridge.text(fields[7]),
            runtimeIdentityFingerprint: ProductionC1InternalBridge.text(fields[8]),
            sessionId: ProductionC1InternalBridge.text(fields[9]),
            attemptId: ProductionC1InternalBridge.text(fields[10]),
            initiatorRole: initiator,
            connectorTargetRole: target,
            destinationPolicyId: ProductionC1InternalBridge.text(fields[13]),
            destinationPolicyVersion: ProductionC1InternalBridge.uint64(fields[14]),
            securityContextDigest: ProductionC1InternalBridge.text(fields[15]),
            effectiveNotBeforeMs: ProductionC1InternalBridge.uint64(fields[16]),
            expiresAtMs: ProductionC1InternalBridge.uint64(fields[17])
        )
        guard try canonicalBytes() == data else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
    }

    public func canonicalBytes() throws -> Data {
        ProductionC1InternalBridge.encode(
            objectType: ProductionC1CandidateCapabilityContract.grantAuthorizationObjectType,
            fields: [
                ProductionC1InternalBridge.ascii(ProductionC1Contract.suite),
                ProductionC1InternalBridge.be(ProductionC1CandidateCapabilityContract.revision),
                ProductionC1InternalBridge.ascii(grantEvidenceDigest),
                ProductionC1InternalBridge.ascii(pairAuthorityDigest),
                ProductionC1InternalBridge.ascii(pairBindingDigest),
                ProductionC1InternalBridge.be(pairEpoch),
                ProductionC1InternalBridge.be(generation),
                ProductionC1InternalBridge.ascii(clientIdentityFingerprint),
                ProductionC1InternalBridge.ascii(runtimeIdentityFingerprint),
                ProductionC1InternalBridge.ascii(sessionId),
                ProductionC1InternalBridge.ascii(attemptId),
                ProductionC1InternalBridge.ascii(initiatorRole.rawValue),
                ProductionC1InternalBridge.ascii(connectorTargetRole.rawValue),
                ProductionC1InternalBridge.ascii(destinationPolicyId),
                ProductionC1InternalBridge.be(destinationPolicyVersion),
                ProductionC1InternalBridge.ascii(securityContextDigest),
                ProductionC1InternalBridge.be(effectiveNotBeforeMs),
                ProductionC1InternalBridge.be(expiresAtMs),
            ]
        )
    }

    public func digestHex() throws -> String {
        ProductionC1InternalBridge.digestHex(try canonicalBytes())
    }
}

public struct VerifiedProductionC1P2PGrantAuthorization: Equatable, Sendable {
    public let authorization: ProductionC1P2PGrantAuthorization
    public let digestHex: String

    fileprivate init(_ authorization: ProductionC1P2PGrantAuthorization) throws {
        self.authorization = authorization
        digestHex = try authorization.digestHex()
    }
}

public struct VerifiedProductionC1P2PGrantEvidence: Equatable, Sendable {
    public let evidence: ProductionC1P2PGrantEvidence
    public let routeAuthorizations: ProductionC1BilateralRouteAuthorizations
    public let operationReceipts: [VerifiedProductionC1CandidateOperationReceipt]
    public let grantAuthorization: VerifiedProductionC1P2PGrantAuthorization
    fileprivate let plan: VerifiedProductionC1CandidateP2PPlan
}

extension ProductionC1CandidateVerifier {
    static func deriveGrantEvidence(
        plan: VerifiedProductionC1CandidateP2PPlan,
        routeAuthorizations: ProductionC1BilateralRouteAuthorizations,
        operationReceipts: [VerifiedProductionC1CandidateOperationReceipt],
        initiatorRole: P2PNATRole,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1P2PGrantEvidence {
        try validatePlanUse(plan, authority: authority, nowMs: nowMs)
        guard operationReceipts.count == 4,
              initiatorRole == ProductionC1P2PDestinationPolicy.initiatorRole else {
            throw ProductionC1CandidateCapabilityError.quotaExceeded
        }
        let bilateral = plan.bilateral
        let capabilities = bilateral.all
        let authorizations = [
            routeAuthorizations.clientPublish,
            routeAuthorizations.runtimeFetchClient,
            routeAuthorizations.runtimePublish,
            routeAuthorizations.clientFetchRuntime,
        ]
        let capabilityDigests = capabilities.map(\.capabilityDigest)
        let authorizationDigests = try authorizations.map {
            ProductionC1InternalBridge.digestHex(try $0.canonicalBytes())
        }
        let receipts = operationReceipts.map(\.receipt)
        let receiptDigests = try receipts.map { try $0.digestHex() }
        guard Set(receiptDigests).count == 4,
              Set(receipts.map(\.proofId)).count == 4,
              Set(receipts.map(\.capabilityDigest)).count == 4,
              Set(receipts.map(\.operationAuthorizationDigest)).count == 4,
              Set(receipts.map(\.singleUseNonce)).count == 4,
              let firstReceipt = receipts.first,
              receipts.allSatisfy({ $0.ledgerId == firstReceipt.ledgerId }) else {
            throw ProductionC1CandidateCapabilityError.requestConflict
        }
        for index in receipts.indices {
            let receipt = receipts[index]
            let refreshed = try ProductionC1CandidateOperationReceiptVerifier.verify(
                receipt,
                verifiedCapability: capabilities[index],
                authorization: authorizations[index],
                authority: authority,
                verifiedKeyset: capabilities[index].verifiedKeyset,
                nowMs: nowMs
            )
            guard refreshed == operationReceipts[index],
                  receipt.capabilityDigest == capabilityDigests[index],
                  receipt.operationAuthorizationDigest == authorizationDigests[index] else {
                throw ProductionC1CandidateCapabilityError.requestConflict
            }
            if index > 0 {
                let previous = receipts[index - 1]
                guard receipt.previousLedgerRevision == previous.committedLedgerRevision,
                      receipt.previousLedgerStateCoreDigest
                        == previous.committedLedgerStateCoreDigest,
                      receipt.committedAtMs >= previous.committedAtMs else {
                    throw ProductionC1CandidateCapabilityError.revisionMismatch
                }
            }
        }
        let effectiveNotBefore = max(
            plan.effectiveNotBeforeMs,
            receipts.map(\.notBeforeMs).max() ?? 0
        )
        let expiresAt = min(
            plan.expiresAtMs,
            receipts.map(\.expiresAtMs).min() ?? 0
        )
        guard nowMs >= effectiveNotBefore, nowMs < expiresAt else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        let finalDigest = ProductionC1InternalBridge.digestHex(
            try routeAuthorizations.finalP2PDirect.canonicalBytes()
        )
        try requireFinalRoute(
            routeAuthorizations.finalP2PDirect,
            plan: plan,
            authority: authority
        )
        let first = bilateral.clientPublish.capability
        let evidence = try ProductionC1P2PGrantEvidence(
            serviceIdDigest: first.serviceIdDigest,
            keysetVersion: first.keysetVersion,
            pairAuthorityDigest: first.pairAuthorityDigest,
            pairBindingDigest: first.pairBindingDigest,
            pairEpoch: first.pairEpoch,
            generation: first.generation,
            sessionId: first.sessionId,
            attemptId: first.attemptId,
            clientIdentityFingerprint: first.clientIdentityFingerprint,
            runtimeIdentityFingerprint: first.runtimeIdentityFingerprint,
            clientCandidateBatchDigest: bilateral.clientPublish.capability.candidateBatchDigest,
            clientCandidateBatchByteCount: bilateral.clientPublish.capability.candidateBatchByteCount,
            runtimeCandidateBatchDigest: bilateral.runtimePublish.capability.candidateBatchDigest,
            runtimeCandidateBatchByteCount: bilateral.runtimePublish.capability.candidateBatchByteCount,
            operationCapabilityDigests: capabilityDigests,
            operationAuthorizationDigests: authorizationDigests,
            bilateralPublishDigest: bilateral.bilateralPublishDigest,
            bilateralFetchDigest: bilateral.bilateralFetchDigest,
            candidatePairDigest: plan.pathValidationReceipt.candidatePairDigest,
            pathValidationReceiptDigest: plan.pathValidationReceiptDigest,
            finalRouteAuthorizationDigest: finalDigest,
            c1RoutePlanClaimsDigest: try plan.claims.digestHex(),
            c1RouteCapabilityDigest: try plan.capability.digestHex(),
            operationReceiptDigests: receiptDigests,
            initiatorRole: initiatorRole,
            connectorTargetRole: ProductionC1P2PDestinationPolicy.connectorTargetRole,
            destinationPolicyId: ProductionC1P2PDestinationPolicy.policyId,
            destinationPolicyVersion: ProductionC1P2PDestinationPolicy.policyVersion,
            securityContextDigest: plan.securityContext.digestHex(),
            effectiveNotBeforeMs: effectiveNotBefore,
            expiresAtMs: expiresAt
        )
        let grantAuthorization = try verifyGrantAuthorization(
            try makeGrantAuthorization(evidence),
            evidence: evidence,
            plan: plan,
            localRole: initiatorRole
        )
        return VerifiedProductionC1P2PGrantEvidence(
            evidence: evidence,
            routeAuthorizations: routeAuthorizations,
            operationReceipts: operationReceipts,
            grantAuthorization: grantAuthorization,
            plan: plan
        )
    }

    static func verifyGrantEvidence(
        _ evidence: ProductionC1P2PGrantEvidence,
        plan: VerifiedProductionC1CandidateP2PPlan,
        routeAuthorizations: ProductionC1BilateralRouteAuthorizations,
        operationReceipts: [VerifiedProductionC1CandidateOperationReceipt],
        localRole: P2PNATRole,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1P2PGrantEvidence {
        let derived = try deriveGrantEvidence(
            plan: plan,
            routeAuthorizations: routeAuthorizations,
            operationReceipts: operationReceipts,
            initiatorRole: evidence.initiatorRole,
            authority: authority,
            nowMs: nowMs
        )
        guard derived.evidence == evidence,
              localRole == evidence.initiatorRole
                || localRole == evidence.connectorTargetRole else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        return derived
    }

    static func makeGrantAuthorization(
        _ evidence: ProductionC1P2PGrantEvidence
    ) throws -> ProductionC1P2PGrantAuthorization {
        try ProductionC1P2PGrantAuthorization(
            grantEvidenceDigest: evidence.digestHex(),
            pairAuthorityDigest: evidence.pairAuthorityDigest,
            pairBindingDigest: evidence.pairBindingDigest,
            pairEpoch: evidence.pairEpoch,
            generation: evidence.generation,
            clientIdentityFingerprint: evidence.clientIdentityFingerprint,
            runtimeIdentityFingerprint: evidence.runtimeIdentityFingerprint,
            sessionId: evidence.sessionId,
            attemptId: evidence.attemptId,
            initiatorRole: evidence.initiatorRole,
            connectorTargetRole: evidence.connectorTargetRole,
            destinationPolicyId: evidence.destinationPolicyId,
            destinationPolicyVersion: evidence.destinationPolicyVersion,
            securityContextDigest: evidence.securityContextDigest,
            effectiveNotBeforeMs: evidence.effectiveNotBeforeMs,
            expiresAtMs: evidence.expiresAtMs
        )
    }

    static func verifyGrantAuthorization(
        _ authorization: ProductionC1P2PGrantAuthorization,
        evidence: ProductionC1P2PGrantEvidence,
        plan: VerifiedProductionC1CandidateP2PPlan,
        localRole: P2PNATRole
    ) throws -> VerifiedProductionC1P2PGrantAuthorization {
        let expected = try makeGrantAuthorization(evidence)
        guard authorization == expected,
              localRole == authorization.initiatorRole
                || localRole == authorization.connectorTargetRole,
              authorization.connectorTargetRole == .runtime,
              authorization.destinationPolicyId
                == ProductionC1P2PDestinationPolicy.policyId,
              authorization.destinationPolicyVersion
                == ProductionC1P2PDestinationPolicy.policyVersion,
              authorization.securityContextDigest == plan.securityContext.digestHex(),
              authorization.effectiveNotBeforeMs == evidence.effectiveNotBeforeMs,
              authorization.expiresAtMs == evidence.expiresAtMs,
              authorization.effectiveNotBeforeMs >= plan.effectiveNotBeforeMs,
              authorization.expiresAtMs <= plan.expiresAtMs else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        return try VerifiedProductionC1P2PGrantAuthorization(authorization)
    }

    static func verifyP2PConnectorInput(
        for verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
        localRole: P2PNATRole,
        routeHandle: String,
        nonce: String,
        secret: Data,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1CandidateP2PConnectorInput {
        let refreshed = try verifyGrantEvidence(
            verifiedGrant.evidence,
            plan: verifiedGrant.plan,
            routeAuthorizations: verifiedGrant.routeAuthorizations,
            operationReceipts: verifiedGrant.operationReceipts,
            localRole: localRole,
            authority: authority,
            nowMs: nowMs
        )
        let connector = verifiedGrant.plan.claims.connector
        guard refreshed == verifiedGrant,
              localRole == verifiedGrant.evidence.initiatorRole,
              verifiedGrant.evidence.connectorTargetRole == .runtime,
              verifiedGrant.plan.selectedRuntimeCandidate.address == connector.addressBytes,
              verifiedGrant.plan.selectedRuntimeCandidate.port == connector.port else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        let expectedHandle = try ProductionC1RouteCommitments.routeHandleDigest(
            kind: .p2pDirect,
            routeHandle: routeHandle
        )
        let expectedCredential = try ProductionC1RouteCommitments.credentialCommitmentDigest(
            kind: .p2pDirect,
            routeHandle: routeHandle,
            nonce: nonce,
            secret: secret
        )
        guard expectedHandle == connector.routeHandleDigest,
              expectedCredential == connector.credentialCommitmentDigest else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        let handleBytes = ProductionC1InternalBridge.ascii(routeHandle)
        let nonceBytes = ProductionC1InternalBridge.ascii(nonce)
        guard handleBytes.count <= ProductionC1RouteCommitments.maximumRouteHandleBytes,
              nonceBytes.count <= ProductionC1RouteCommitments.maximumNonceBytes else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        var claims = try connector.canonicalBytes()
        claims.append(ProductionC1InternalBridge.be(UInt32(handleBytes.count)))
        claims.append(handleBytes)
        claims.append(ProductionC1InternalBridge.be(UInt32(nonceBytes.count)))
        claims.append(nonceBytes)
        claims.append(try ProductionC1InternalBridge.rawDigest(expectedCredential))
        return VerifiedProductionC1CandidateP2PConnectorInput(
            connector: connector,
            commitmentDigest: candidateDomainDigest(
                "AetherLink G1a-C verified P2P connector-input commitment v1",
                claims: claims
            ),
            routeHandle: routeHandle,
            nonce: nonce,
            secret: secret
        )
    }

    static func verifyP2PTranscriptBinding(
        transcript: ProductionSecureSessionTranscript,
        verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
        connectorInput: VerifiedProductionC1CandidateP2PConnectorInput,
        localRole: P2PNATRole,
        keyConfirmationKey: Data,
        presentedPeerKeyConfirmation: Data,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1CandidateP2PTranscriptBinding {
        let keyScheduleBinding = try verifyP2PKeyScheduleBinding(
            transcript: transcript,
            verifiedGrant: verifiedGrant,
            localRole: localRole,
            authority: authority,
            nowMs: nowMs
        )
        let runtimeKeyScheduleBinding = try verifyP2PKeyScheduleBinding(
            transcript: transcript,
            verifiedGrant: verifiedGrant,
            localRole: .runtime,
            authority: authority,
            nowMs: nowMs
        )
        let expectedInput = try verifyP2PConnectorInput(
            for: verifiedGrant,
            localRole: localRole,
            routeHandle: connectorInput.routeHandle,
            nonce: connectorInput.nonce,
            secret: connectorInput.secret,
            authority: authority,
            nowMs: nowMs
        )
        let expectedPeerConfirmation = try p2PKeyConfirmation(
            transcript: transcript,
            grantAuthorization: keyScheduleBinding.grantAuthorization,
            confirmingRole: verifiedGrant.evidence.connectorTargetRole,
            key: keyConfirmationKey
        )
        guard expectedInput == connectorInput,
              localRole == .client,
              presentedPeerKeyConfirmation == expectedPeerConfirmation else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        return VerifiedProductionC1CandidateP2PTranscriptBinding(
            transcript: transcript,
            grant: verifiedGrant,
            connectorInput: connectorInput,
            securityContext: keyScheduleBinding.securityContext,
            runtimeKeyScheduleBinding: runtimeKeyScheduleBinding,
            keyConfirmationKey: keyConfirmationKey,
            presentedPeerKeyConfirmation: presentedPeerKeyConfirmation
        )
    }

    static func verifyP2PKeyScheduleBinding(
        transcript: ProductionSecureSessionTranscript,
        verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
        localRole: P2PNATRole,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1CandidateP2PKeyScheduleBinding {
        let refreshed = try verifyGrantEvidence(
            verifiedGrant.evidence,
            plan: verifiedGrant.plan,
            routeAuthorizations: verifiedGrant.routeAuthorizations,
            operationReceipts: verifiedGrant.operationReceipts,
            localRole: localRole,
            authority: authority,
            nowMs: nowMs
        )
        let expectedContext = try ProductionC1PreauthorizationSessionContext(
            transcript: transcript
        )
        let evidence = verifiedGrant.evidence
        let grantAuthorization = try verifyGrantAuthorization(
            verifiedGrant.grantAuthorization.authorization,
            evidence: evidence,
            plan: verifiedGrant.plan,
            localRole: localRole
        )
        guard refreshed == verifiedGrant,
              grantAuthorization == verifiedGrant.grantAuthorization,
              expectedContext == verifiedGrant.plan.securityContext,
              expectedContext.digestHex() == verifiedGrant.plan.claims.securityContextDigest,
              authority.status == .active,
              try authority.digestHex() == evidence.pairAuthorityDigest,
              nowMs >= evidence.effectiveNotBeforeMs,
              nowMs < evidence.expiresAtMs,
              transcript.routeKind == .p2pDirect,
              transcript.routeAuthDigest == grantAuthorization.digestHex,
              transcript.sessionId == evidence.sessionId,
              transcript.pairBindingDigest == evidence.pairBindingDigest,
              transcript.pairEpoch == evidence.pairEpoch,
              transcript.generation == evidence.generation,
              transcript.clientIdentityFingerprint == evidence.clientIdentityFingerprint,
              transcript.runtimeIdentityFingerprint == evidence.runtimeIdentityFingerprint,
              transcript.serviceConfigVersion == authority.serviceConfigVersion,
              transcript.keysetVersion == authority.keysetVersion,
              transcript.revocationCounter == authority.revocationCounter,
              ProductionSecureSessionTranscript.protocolVersion >= authority.protocolFloor,
              ProductionSecureSessionTranscript.minimumProtocolVersion
                >= authority.protocolFloor else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        return VerifiedProductionC1CandidateP2PKeyScheduleBinding(
            transcript: transcript,
            grantAuthorization: grantAuthorization,
            securityContext: expectedContext,
            localRole: localRole
        )
    }

    static func makeP2PKeyConfirmation(
        transcript: ProductionSecureSessionTranscript,
        grantAuthorization: VerifiedProductionC1P2PGrantAuthorization,
        confirmingRole: P2PNATRole,
        key: Data
    ) throws -> Data {
        try p2PKeyConfirmation(
            transcript: transcript,
            grantAuthorization: grantAuthorization,
            confirmingRole: confirmingRole,
            key: key
        )
    }

    static func verifyP2PInboundMaterial(
        transcript: ProductionSecureSessionTranscript,
        verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
        localRole: P2PNATRole,
        observedPeerCandidate: P2PNATCandidate,
        keyConfirmationKey: Data,
        presentedPeerKeyConfirmation: Data,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1CandidateP2PInboundMaterial {
        let refreshed = try verifyGrantEvidence(
            verifiedGrant.evidence,
            plan: verifiedGrant.plan,
            routeAuthorizations: verifiedGrant.routeAuthorizations,
            operationReceipts: verifiedGrant.operationReceipts,
            localRole: localRole,
            authority: authority,
            nowMs: nowMs
        )
        let grantAuthorization = try verifyGrantAuthorization(
            verifiedGrant.grantAuthorization.authorization,
            evidence: verifiedGrant.evidence,
            plan: verifiedGrant.plan,
            localRole: localRole
        )
        let expectedPeerConfirmation = try p2PKeyConfirmation(
            transcript: transcript,
            grantAuthorization: grantAuthorization,
            confirmingRole: verifiedGrant.evidence.initiatorRole,
            key: keyConfirmationKey
        )
        guard refreshed == verifiedGrant,
              localRole == verifiedGrant.evidence.connectorTargetRole,
              observedPeerCandidate == verifiedGrant.plan.selectedClientCandidate,
              presentedPeerKeyConfirmation == expectedPeerConfirmation else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        return VerifiedProductionC1CandidateP2PInboundMaterial(
            observedPeerCandidate: observedPeerCandidate,
            peerKeyConfirmationDigest: ProductionC1InternalBridge.digestHex(
                presentedPeerKeyConfirmation
            ),
            transcriptDigest: ProductionC1InternalBridge.digestHex(
                transcript.canonicalBytes()
            ),
            routeGrantDigest: try verifiedGrant.evidence.digestHex(),
            grantAuthorizationDigest: grantAuthorization.digestHex,
            sessionId: verifiedGrant.evidence.sessionId
        )
    }

    static func verifyP2PInboundTranscriptBinding(
        transcript: ProductionSecureSessionTranscript,
        verifiedGrant: VerifiedProductionC1P2PGrantEvidence,
        inboundMaterial: VerifiedProductionC1CandidateP2PInboundMaterial,
        localRole: P2PNATRole,
        authority: ProductionPairAuthorityState,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1CandidateP2PInboundTranscriptBinding {
        let expectedContext = try ProductionC1PreauthorizationSessionContext(
            transcript: transcript
        )
        let grantAuthorization = try verifyGrantAuthorization(
            verifiedGrant.grantAuthorization.authorization,
            evidence: verifiedGrant.evidence,
            plan: verifiedGrant.plan,
            localRole: localRole
        )
        let evidence = verifiedGrant.evidence
        let transcriptDigest = ProductionC1InternalBridge.digestHex(
            transcript.canonicalBytes()
        )
        guard localRole == evidence.connectorTargetRole,
              inboundMaterial.observedPeerCandidate
                == verifiedGrant.plan.selectedClientCandidate,
              inboundMaterial.transcriptDigest == transcriptDigest,
              inboundMaterial.routeGrantDigest == (try evidence.digestHex()),
              inboundMaterial.grantAuthorizationDigest == grantAuthorization.digestHex,
              inboundMaterial.sessionId == evidence.sessionId,
              expectedContext == verifiedGrant.plan.securityContext,
              transcript.routeKind == .p2pDirect,
              transcript.routeAuthDigest == grantAuthorization.digestHex,
              transcript.sessionId == evidence.sessionId,
              transcript.pairBindingDigest == evidence.pairBindingDigest,
              transcript.pairEpoch == evidence.pairEpoch,
              transcript.generation == evidence.generation,
              try authority.digestHex() == evidence.pairAuthorityDigest,
              nowMs >= evidence.effectiveNotBeforeMs,
              nowMs < evidence.expiresAtMs else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        return VerifiedProductionC1CandidateP2PInboundTranscriptBinding(
            transcript: transcript,
            grant: verifiedGrant,
            inboundMaterial: inboundMaterial,
            securityContext: expectedContext
        )
    }

    private static func p2PKeyConfirmation(
        transcript: ProductionSecureSessionTranscript,
        grantAuthorization: VerifiedProductionC1P2PGrantAuthorization,
        confirmingRole: P2PNATRole,
        key: Data
    ) throws -> Data {
        // Readiness-only seam: raw Data is not production KDF provenance. Activation remains
        // fail-closed until an authenticated ECDH KDF and accepted-peer adapter supply this key.
        guard key.count == 32 else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        var claims = transcript.canonicalBytes()
        claims.append(try grantAuthorization.authorization.canonicalBytes())
        claims.append(ProductionC1InternalBridge.ascii(confirmingRole.rawValue))
        let message = ProductionC1InternalBridge.transcript(
            domain: "AetherLink G1a-C role-labeled P2P key confirmation v1",
            claims: claims
        )
        return Data(HMAC<SHA256>.authenticationCode(
            for: message,
            using: SymmetricKey(data: key)
        ))
    }

    private static func requireFinalRoute(
        _ route: ProductionRouteAuthorization,
        plan: VerifiedProductionC1CandidateP2PPlan,
        authority: ProductionPairAuthorityState
    ) throws {
        guard case let .p2pDirect(
            pair, epoch, generation, candidatePair, receipt, publish, fetch
        ) = route,
            pair == authority.pairBindingDigest,
            epoch == authority.pairEpoch,
            generation == authority.generation,
            candidatePair == plan.pathValidationReceipt.candidatePairDigest,
            receipt == plan.pathValidationReceiptDigest,
            publish == plan.bilateral.bilateralPublishDigest,
            fetch == plan.bilateral.bilateralFetchDigest else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
    }
}

public struct ProductionC1EndpointGrantEntry: Equatable, Sendable {
    public let admissionId: String
    public let bindingDigest: String
    public let routeGrantDigest: String
    public let sessionId: String
    public let transcriptDigest: String
    /// Digest of the generic object-4 route authorization selected for the endpoint.
    public let routeAuthorizationDigest: String
    /// Digest of the exact object-26 grant authorization bound by the transcript.
    public let grantAuthorizationDigest: String
    public let connectorInputCommitmentDigest: String
    public let pairSnapshotDigest: String
    public let committedRevision: UInt64
}

public struct ProductionC1EndpointGrantLedgerState: Equatable, Sendable {
    public let revision: UInt64
    public let pairAuthorityDigest: String
    public let pairLocalRevision: UInt64
    public let remainingGrants: UInt64
    public let retentionLimit: UInt32
    public let entries: [ProductionC1EndpointGrantEntry]

    public init(
        revision: UInt64 = 1,
        pairAuthorityDigest: String,
        pairLocalRevision: UInt64,
        remainingGrants: UInt64,
        retentionLimit: UInt32,
        entries: [ProductionC1EndpointGrantEntry] = []
    ) throws {
        try ProductionC1InternalBridge.validateDigest(pairAuthorityDigest)
        guard revision > 0, pairLocalRevision > 0,
              retentionLimit > 0, entries.count <= Int(retentionLimit),
              revision == UInt64(entries.count) + 1,
              Set(entries.map(\.admissionId)).count == entries.count,
              Set(entries.map(\.sessionId)).count == entries.count,
              Set(entries.map(\.routeGrantDigest)).count == entries.count,
              Set(entries.map(\.transcriptDigest)).count == entries.count else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        for (index, entry) in entries.enumerated() {
            for digest in [
                entry.admissionId, entry.bindingDigest, entry.routeGrantDigest,
                entry.transcriptDigest, entry.routeAuthorizationDigest,
                entry.grantAuthorizationDigest,
                entry.connectorInputCommitmentDigest, entry.pairSnapshotDigest,
            ] { try ProductionC1InternalBridge.validateDigest(digest) }
            guard candidateIsLowerHex(entry.sessionId), entry.sessionId.utf8.count == 32,
                  entry.committedRevision == UInt64(index) + 2 else {
                throw ProductionC1CandidateCapabilityError.invalidValue
            }
        }
        self.revision = revision
        self.pairAuthorityDigest = pairAuthorityDigest
        self.pairLocalRevision = pairLocalRevision
        self.remainingGrants = remainingGrants
        self.retentionLimit = retentionLimit
        self.entries = entries
    }

    public func snapshotDigestHex() throws -> String {
        var claims = ProductionC1InternalBridge.be(revision)
        claims.append(try ProductionC1InternalBridge.rawDigest(pairAuthorityDigest))
        claims.append(ProductionC1InternalBridge.be(pairLocalRevision))
        claims.append(ProductionC1InternalBridge.be(remainingGrants))
        claims.append(ProductionC1InternalBridge.be(retentionLimit))
        for entry in entries {
            for digest in [
                entry.admissionId, entry.bindingDigest, entry.routeGrantDigest,
                entry.transcriptDigest, entry.routeAuthorizationDigest,
                entry.grantAuthorizationDigest,
                entry.connectorInputCommitmentDigest, entry.pairSnapshotDigest,
            ] { claims.append(try ProductionC1InternalBridge.rawDigest(digest)) }
            claims.append(ProductionC1InternalBridge.ascii(entry.sessionId))
            claims.append(ProductionC1InternalBridge.be(entry.committedRevision))
        }
        return candidateDomainDigest(
            "AetherLink G1a-C endpoint grant ledger snapshot v2 object4+object26",
            claims: claims
        )
    }
}

public struct ProductionC1EndpointCompoundRecord: Equatable, Sendable {
    public let grantLedger: ProductionC1EndpointGrantLedgerState
    public let pairSnapshot: ProductionPairStateSnapshot

    public init(
        grantLedger: ProductionC1EndpointGrantLedgerState,
        pairSnapshot: ProductionPairStateSnapshot
    ) throws {
        guard try pairSnapshot.authority.digestHex() == grantLedger.pairAuthorityDigest,
              pairSnapshot.localRevision == grantLedger.pairLocalRevision else {
            throw ProductionC1CandidateCapabilityError.authorityMismatch
        }
        self.grantLedger = grantLedger
        self.pairSnapshot = pairSnapshot
    }

    public func digestHex() throws -> String {
        var claims = try ProductionC1InternalBridge.rawDigest(
            grantLedger.snapshotDigestHex()
        )
        claims.append(try ProductionC1InternalBridge.rawDigest(pairSnapshot.digestHex()))
        return candidateDomainDigest(
            "AetherLink G1a-C endpoint pair-and-grant compound record v1",
            claims: claims
        )
    }
}

public struct ProductionC1EndpointGrantAdmissionPreparation: Equatable, Sendable {
    public let disposition: ProductionC1CandidateCASDisposition
    public let sessionID: String
    public let routeAuthorizationDigest: String
    public let grantAuthorizationDigest: String
    public let pairAuthorityDigest: String
    public let effectiveNotBeforeMs: UInt64
    public let expiresAtMs: UInt64
    public let expectedRevision: UInt64
    public let expectedSnapshotDigest: String
    public let expectedPairSnapshotDigest: String
    public let nextState: ProductionC1EndpointGrantLedgerState
    public let nextPairSnapshot: ProductionPairStateSnapshot
    public let expectedCompoundDigest: String
    public let nextCompoundRecord: ProductionC1EndpointCompoundRecord
    public let entry: ProductionC1EndpointGrantEntry

    init(
        disposition: ProductionC1CandidateCASDisposition,
        sessionID: String,
        routeAuthorizationDigest: String,
        grantAuthorizationDigest: String,
        pairAuthorityDigest: String,
        effectiveNotBeforeMs: UInt64,
        expiresAtMs: UInt64,
        expectedRevision: UInt64,
        expectedSnapshotDigest: String,
        expectedPairSnapshotDigest: String,
        nextState: ProductionC1EndpointGrantLedgerState,
        nextPairSnapshot: ProductionPairStateSnapshot,
        expectedCompoundDigest: String,
        nextCompoundRecord: ProductionC1EndpointCompoundRecord,
        entry: ProductionC1EndpointGrantEntry
    ) throws {
        guard effectiveNotBeforeMs < expiresAtMs,
              entry.sessionId == sessionID,
              entry.routeAuthorizationDigest == routeAuthorizationDigest,
              entry.grantAuthorizationDigest == grantAuthorizationDigest,
              nextState.pairAuthorityDigest == pairAuthorityDigest,
              try nextPairSnapshot.authority.digestHex() == pairAuthorityDigest else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        self.disposition = disposition
        self.sessionID = sessionID
        self.routeAuthorizationDigest = routeAuthorizationDigest
        self.grantAuthorizationDigest = grantAuthorizationDigest
        self.pairAuthorityDigest = pairAuthorityDigest
        self.effectiveNotBeforeMs = effectiveNotBeforeMs
        self.expiresAtMs = expiresAtMs
        self.expectedRevision = expectedRevision
        self.expectedSnapshotDigest = expectedSnapshotDigest
        self.expectedPairSnapshotDigest = expectedPairSnapshotDigest
        self.nextState = nextState
        self.nextPairSnapshot = nextPairSnapshot
        self.expectedCompoundDigest = expectedCompoundDigest
        self.nextCompoundRecord = nextCompoundRecord
        self.entry = entry
    }
}

public struct ReadbackConfirmedProductionC1EndpointGrantAdmission: Equatable, Sendable {
    public let entry: ProductionC1EndpointGrantEntry

    private init(entry: ProductionC1EndpointGrantEntry) {
        self.entry = entry
    }

    static func confirm(
        _ preparation: ProductionC1EndpointGrantAdmissionPreparation,
        committedCompoundReadback: ProductionC1EndpointCompoundRecord
    ) throws -> Self {
        let committedLedgerReadback = committedCompoundReadback.grantLedger
        let committedPairSnapshotReadback = committedCompoundReadback.pairSnapshot
        guard committedLedgerReadback == preparation.nextState,
              committedPairSnapshotReadback == preparation.nextPairSnapshot,
              committedCompoundReadback == preparation.nextCompoundRecord,
              committedLedgerReadback.entries.contains(preparation.entry),
              try committedPairSnapshotReadback.digestHex()
                == preparation.entry.pairSnapshotDigest else {
            throw ProductionC1CandidateCapabilityError.revisionMismatch
        }
        if preparation.disposition == .applied {
            guard committedLedgerReadback.revision == preparation.entry.committedRevision,
                  committedPairSnapshotReadback.localRevision
                    == committedLedgerReadback.pairLocalRevision else {
                throw ProductionC1CandidateCapabilityError.revisionMismatch
            }
        }
        return Self(entry: preparation.entry)
    }
}

public enum ProductionC1EndpointGrantAdmission {
    public static func bindingDigest(
        admissionId: String,
        routeGrantDigest: String,
        transcriptDigest: String,
        routeAuthorizationDigest: String,
        grantAuthorizationDigest: String,
        connectorInputCommitmentDigest: String
    ) throws -> String {
        var claims = try ProductionC1InternalBridge.rawDigest(admissionId)
        claims.append(try ProductionC1InternalBridge.rawDigest(routeGrantDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(transcriptDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(routeAuthorizationDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(grantAuthorizationDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(connectorInputCommitmentDigest))
        return candidateDomainDigest(
            "AetherLink G1a-C endpoint grant admission binding v2 object4+object26",
            claims: claims
        )
    }

    /// Restores only an already committed admission after process reload.
    /// No connector secret, verified wrapper, or new grant effect is produced.
    static func prepareCommittedRetry(
        state: ProductionC1EndpointGrantLedgerState,
        admissionId: String,
        bindingDigest: String,
        grantEvidenceCanonicalBytes: Data,
        routeAuthorization: ProductionRouteAuthorization,
        transcriptCanonicalBytes: Data,
        connectorInputCommitmentDigest: String,
        currentPairSnapshot: ProductionPairStateSnapshot
    ) throws -> ProductionC1EndpointGrantAdmissionPreparation {
        let evidence = try ProductionC1P2PGrantEvidence(
            canonicalBytes: grantEvidenceCanonicalBytes
        )
        let transcript = try ProductionSecureSessionTranscript(
            canonicalBytes: transcriptCanonicalBytes
        )
        let grantDigest = ProductionC1InternalBridge.digestHex(grantEvidenceCanonicalBytes)
        let grantAuthorization = try ProductionC1CandidateVerifier.makeGrantAuthorization(evidence)
        let grantAuthorizationDigest = try grantAuthorization.digestHex()
        let routeDigest = ProductionC1InternalBridge.digestHex(
            try routeAuthorization.canonicalBytes()
        )
        let transcriptDigest = ProductionC1InternalBridge.digestHex(transcriptCanonicalBytes)
        let exactBinding = try self.bindingDigest(
            admissionId: admissionId,
            routeGrantDigest: grantDigest,
            transcriptDigest: transcriptDigest,
            routeAuthorizationDigest: routeDigest,
            grantAuthorizationDigest: grantAuthorizationDigest,
            connectorInputCommitmentDigest: connectorInputCommitmentDigest
        )
        let pairSnapshotDigest = try currentPairSnapshot.digestHex()
        guard bindingDigest == exactBinding,
              routeDigest == evidence.finalRouteAuthorizationDigest,
              transcript.routeAuthDigest == grantAuthorizationDigest,
              transcript.sessionId == evidence.sessionId,
              let existing = state.entries.first(where: { $0.admissionId == admissionId }),
              existing.bindingDigest == bindingDigest,
              existing.routeGrantDigest == grantDigest,
              existing.sessionId == transcript.sessionId,
              existing.transcriptDigest == transcriptDigest,
              existing.routeAuthorizationDigest == routeDigest,
              existing.grantAuthorizationDigest == grantAuthorizationDigest,
              existing.connectorInputCommitmentDigest == connectorInputCommitmentDigest,
              existing.pairSnapshotDigest == pairSnapshotDigest,
              currentPairSnapshot.localRevision == state.pairLocalRevision,
              try currentPairSnapshot.authority.digestHex() == state.pairAuthorityDigest else {
            throw ProductionC1CandidateCapabilityError.requestConflict
        }
        return try ProductionC1EndpointGrantAdmissionPreparation(
            disposition: .idempotent,
            sessionID: transcript.sessionId,
            routeAuthorizationDigest: routeDigest,
            grantAuthorizationDigest: grantAuthorizationDigest,
            pairAuthorityDigest: state.pairAuthorityDigest,
            effectiveNotBeforeMs: evidence.effectiveNotBeforeMs,
            expiresAtMs: evidence.expiresAtMs,
            expectedRevision: state.revision,
            expectedSnapshotDigest: try state.snapshotDigestHex(),
            expectedPairSnapshotDigest: pairSnapshotDigest,
            nextState: state,
            nextPairSnapshot: currentPairSnapshot,
            expectedCompoundDigest: try ProductionC1EndpointCompoundRecord(
                grantLedger: state,
                pairSnapshot: currentPairSnapshot
            ).digestHex(),
            nextCompoundRecord: try ProductionC1EndpointCompoundRecord(
                grantLedger: state,
                pairSnapshot: currentPairSnapshot
            ),
            entry: existing
        )
    }

    static func prepare(
        state: ProductionC1EndpointGrantLedgerState,
        expectedRevision: UInt64,
        expectedSnapshotDigest: String,
        admissionId: String,
        bindingDigest: String,
        verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        currentPairSnapshot: ProductionPairStateSnapshot,
        nowMs: UInt64
    ) throws -> ProductionC1EndpointGrantAdmissionPreparation {
        let verifiedGrant = verifiedBinding.grant
        let transcript = verifiedBinding.transcript
        let evidence = verifiedGrant.evidence
        let routeAuthorization = verifiedGrant.routeAuthorizations.finalP2PDirect
        let routeBytes = try routeAuthorization.canonicalBytes()
        let routeDigest = ProductionC1InternalBridge.digestHex(routeBytes)
        let transcriptBytes = transcript.canonicalBytes()
        let transcriptDigest = ProductionC1InternalBridge.digestHex(transcriptBytes)
        let grantDigest = try evidence.digestHex()
        let grantAuthorizationDigest = verifiedGrant.grantAuthorization.digestHex
        let expectedBinding = try self.bindingDigest(
            admissionId: admissionId,
            routeGrantDigest: grantDigest,
            transcriptDigest: transcriptDigest,
            routeAuthorizationDigest: routeDigest,
            grantAuthorizationDigest: grantAuthorizationDigest,
            connectorInputCommitmentDigest: verifiedBinding.connectorInput.commitmentDigest
        )
        guard bindingDigest == expectedBinding,
              routeAuthorization == verifiedGrant.routeAuthorizations.finalP2PDirect,
              routeDigest == evidence.finalRouteAuthorizationDigest,
              transcript.routeKind == .p2pDirect,
              transcript.routeAuthDigest == grantAuthorizationDigest,
              transcript.sessionId == evidence.sessionId,
              transcript.pairBindingDigest == evidence.pairBindingDigest,
              transcript.pairEpoch == evidence.pairEpoch,
              transcript.generation == evidence.generation,
              transcript.clientIdentityFingerprint == evidence.clientIdentityFingerprint,
              transcript.runtimeIdentityFingerprint == evidence.runtimeIdentityFingerprint,
              try ProductionC1PreauthorizationSessionContext(transcript: transcript)
                == verifiedGrant.plan.securityContext else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        let currentPairDigest = try currentPairSnapshot.digestHex()
        if let existing = state.entries.first(where: { $0.admissionId == admissionId }) {
            guard existing.bindingDigest == bindingDigest,
                  existing.routeGrantDigest == grantDigest,
                  existing.sessionId == transcript.sessionId,
                  existing.transcriptDigest == transcriptDigest,
                  existing.routeAuthorizationDigest == routeDigest,
                  existing.grantAuthorizationDigest == grantAuthorizationDigest,
                  existing.connectorInputCommitmentDigest
                    == verifiedBinding.connectorInput.commitmentDigest,
                  existing.pairSnapshotDigest == currentPairDigest,
                  currentPairSnapshot.localRevision == state.pairLocalRevision,
                  try currentPairSnapshot.authority.digestHex() == state.pairAuthorityDigest else {
                throw ProductionC1CandidateCapabilityError.requestConflict
            }
            return try ProductionC1EndpointGrantAdmissionPreparation(
                disposition: .idempotent,
                sessionID: transcript.sessionId,
                routeAuthorizationDigest: routeDigest,
                grantAuthorizationDigest: grantAuthorizationDigest,
                pairAuthorityDigest: state.pairAuthorityDigest,
                effectiveNotBeforeMs: evidence.effectiveNotBeforeMs,
                expiresAtMs: evidence.expiresAtMs,
                expectedRevision: state.revision,
                expectedSnapshotDigest: try state.snapshotDigestHex(),
                expectedPairSnapshotDigest: currentPairDigest,
                nextState: state,
                nextPairSnapshot: currentPairSnapshot,
                expectedCompoundDigest: try ProductionC1EndpointCompoundRecord(
                    grantLedger: state,
                    pairSnapshot: currentPairSnapshot
                ).digestHex(),
                nextCompoundRecord: try ProductionC1EndpointCompoundRecord(
                    grantLedger: state,
                    pairSnapshot: currentPairSnapshot
                ),
                entry: existing
            )
        }
        let refreshedBinding = try ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
            transcript: transcript,
            verifiedGrant: verifiedGrant,
            connectorInput: verifiedBinding.connectorInput,
            localRole: .client,
            keyConfirmationKey: verifiedBinding.keyConfirmationKey,
            presentedPeerKeyConfirmation: verifiedBinding.presentedPeerKeyConfirmation,
            authority: currentPairSnapshot.authority,
            nowMs: nowMs
        )
        guard refreshedBinding == verifiedBinding else {
            throw ProductionC1CandidateCapabilityError.routeMismatch
        }
        guard nowMs >= evidence.effectiveNotBeforeMs, nowMs < evidence.expiresAtMs,
              try currentPairSnapshot.authority.digestHex() == state.pairAuthorityDigest,
              currentPairSnapshot.localRevision == state.pairLocalRevision,
              try currentPairSnapshot.authority.digestHex() == evidence.pairAuthorityDigest else {
            throw ProductionC1CandidateCapabilityError.authorityMismatch
        }
        guard state.revision == expectedRevision,
              try state.snapshotDigestHex() == expectedSnapshotDigest else {
            throw ProductionC1CandidateCapabilityError.revisionMismatch
        }
        guard state.entries.count < Int(state.retentionLimit) else {
            throw ProductionC1CandidateCapabilityError.retentionExhausted
        }
        guard !state.entries.contains(where: {
            $0.routeGrantDigest == grantDigest || $0.sessionId == transcript.sessionId
                || $0.transcriptDigest == transcriptDigest
        }) else {
            throw ProductionC1CandidateCapabilityError.replay
        }
        guard !currentPairSnapshot.consumedEntries.contains(where: {
            $0.sessionId == transcript.sessionId || $0.transcriptDigest == transcriptDigest
        }) else {
            throw ProductionC1CandidateCapabilityError.replay
        }
        guard state.remainingGrants > 0, state.revision < UInt64.max,
              currentPairSnapshot.localRevision < UInt64.max else {
            throw ProductionC1CandidateCapabilityError.quotaExceeded
        }
        let nextPairSnapshot = try ProductionPairStateSnapshot(
            authority: currentPairSnapshot.authority,
            localRevision: currentPairSnapshot.localRevision + 1,
            consumedEntries: currentPairSnapshot.consumedEntries + [
                try ProductionPairConsumedSession(
                    sessionId: transcript.sessionId,
                    transcriptDigest: transcriptDigest
                ),
            ],
            transitionHistory: currentPairSnapshot.transitionHistory
        )
        let nextPairDigest = try nextPairSnapshot.digestHex()
        let entry = ProductionC1EndpointGrantEntry(
            admissionId: admissionId,
            bindingDigest: bindingDigest,
            routeGrantDigest: grantDigest,
            sessionId: transcript.sessionId,
            transcriptDigest: transcriptDigest,
            routeAuthorizationDigest: routeDigest,
            grantAuthorizationDigest: grantAuthorizationDigest,
            connectorInputCommitmentDigest: verifiedBinding.connectorInput.commitmentDigest,
            pairSnapshotDigest: nextPairDigest,
            committedRevision: state.revision + 1
        )
        let next = try ProductionC1EndpointGrantLedgerState(
            revision: state.revision + 1,
            pairAuthorityDigest: state.pairAuthorityDigest,
            pairLocalRevision: nextPairSnapshot.localRevision,
            remainingGrants: state.remainingGrants - 1,
            retentionLimit: state.retentionLimit,
            entries: state.entries + [entry]
        )
        let currentCompound = try ProductionC1EndpointCompoundRecord(
            grantLedger: state,
            pairSnapshot: currentPairSnapshot
        )
        let nextCompound = try ProductionC1EndpointCompoundRecord(
            grantLedger: next,
            pairSnapshot: nextPairSnapshot
        )
        return try ProductionC1EndpointGrantAdmissionPreparation(
            disposition: .applied,
            sessionID: transcript.sessionId,
            routeAuthorizationDigest: routeDigest,
            grantAuthorizationDigest: grantAuthorizationDigest,
            pairAuthorityDigest: state.pairAuthorityDigest,
            effectiveNotBeforeMs: evidence.effectiveNotBeforeMs,
            expiresAtMs: evidence.expiresAtMs,
            expectedRevision: state.revision,
            expectedSnapshotDigest: expectedSnapshotDigest,
            expectedPairSnapshotDigest: currentPairDigest,
            nextState: next,
            nextPairSnapshot: nextPairSnapshot,
            expectedCompoundDigest: try currentCompound.digestHex(),
            nextCompoundRecord: nextCompound,
            entry: entry
        )
    }
}

private func candidateDomainDigest(_ domain: String, claims: Data) -> String {
    ProductionC1InternalBridge.digestHex(
        ProductionC1InternalBridge.transcript(domain: domain, claims: claims)
    )
}

private func candidateIsLowerHex(_ value: String) -> Bool {
    value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
}
