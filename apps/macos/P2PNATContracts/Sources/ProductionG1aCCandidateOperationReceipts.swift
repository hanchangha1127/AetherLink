import CryptoKit
import Foundation

public enum ProductionC1CandidateOperationReceiptContract {
    public static let objectType: UInt8 = 28
    public static let revision: UInt64 = 1
    public static let maximumBytes = 4_096
    public static let maximumLifetimeMs = ProductionC1Contract.maximumRouteLifetimeMs
}

public enum ProductionC1CandidateOperationReceiptStatus: String, Sendable {
    case committed
}

/// A service-signed assertion about an already committed candidate operation.
///
/// This value authenticates commit-core claims; it does not itself prove store I/O, fsync,
/// or a full compound readback. `commitRecordDigest` must identify a pre-existing store record
/// that excludes object-28 canonical bytes, its signature, and its digest.
public struct ProductionC1CandidateOperationReceipt: Equatable, Sendable {
    public let status: ProductionC1CandidateOperationReceiptStatus
    public let serviceIdDigest: String
    public let keysetVersion: UInt64
    public let signingKeyId: String
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
    public let ledgerId: String
    public let initiatorRole: P2PNATRole
    public let operation: ProductionC1CandidateOperation
    public let requesterRole: P2PNATRole
    public let candidateOwnerRole: P2PNATRole
    public let capabilityId: String
    public let capabilityDigest: String
    public let endpointOperationProofDigest: String
    public let proofId: String
    public let operationAuthorizationKind: ProductionRouteAuthorizationKind
    public let operationAuthorizationDigest: String
    public let requestDigest: String
    public let singleUseNonce: String
    public let candidateBatchDigest: String
    public let candidateBatchByteCount: UInt32
    public let candidateBatchSequence: UInt64
    public let candidateBatchExpiresAtMs: UInt64
    public let consumedOperations: UInt32
    public let consumedBytes: UInt64
    public let resultDigest: String
    public let previousLedgerRevision: UInt64
    public let committedLedgerRevision: UInt64
    public let previousLedgerStateCoreDigest: String
    public let committedLedgerStateCoreDigest: String
    public let commitRecordDigest: String
    public let committedAtMs: UInt64
    public let issuedAtMs: UInt64
    public let notBeforeMs: UInt64
    public let expiresAtMs: UInt64
    public let serviceSignature: Data

    private init(
        status: ProductionC1CandidateOperationReceiptStatus,
        serviceIdDigest: String,
        keysetVersion: UInt64,
        signingKeyId: String,
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
        ledgerId: String,
        initiatorRole: P2PNATRole,
        operation: ProductionC1CandidateOperation,
        requesterRole: P2PNATRole,
        candidateOwnerRole: P2PNATRole,
        capabilityId: String,
        capabilityDigest: String,
        endpointOperationProofDigest: String,
        proofId: String,
        operationAuthorizationKind: ProductionRouteAuthorizationKind,
        operationAuthorizationDigest: String,
        requestDigest: String,
        singleUseNonce: String,
        candidateBatchDigest: String,
        candidateBatchByteCount: UInt32,
        candidateBatchSequence: UInt64,
        candidateBatchExpiresAtMs: UInt64,
        consumedOperations: UInt32,
        consumedBytes: UInt64,
        resultDigest: String,
        previousLedgerRevision: UInt64,
        committedLedgerRevision: UInt64,
        previousLedgerStateCoreDigest: String,
        committedLedgerStateCoreDigest: String,
        commitRecordDigest: String,
        committedAtMs: UInt64,
        issuedAtMs: UInt64,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        serviceSignature: Data,
        validateSignature: Bool
    ) throws {
        for digest in [
            serviceIdDigest, signingKeyId, pairAuthorityDigest, pairBindingDigest,
            clientIdentityFingerprint, runtimeIdentityFingerprint, ledgerId,
            capabilityId, capabilityDigest, endpointOperationProofDigest, proofId,
            operationAuthorizationDigest, requestDigest, singleUseNonce,
            candidateBatchDigest, resultDigest, previousLedgerStateCoreDigest,
            committedLedgerStateCoreDigest, commitRecordDigest,
        ] {
            try ProductionC1InternalBridge.validateDigest(digest)
        }
        guard keysetVersion > 0, pairEpoch > 0, generation > 0,
              serviceConfigVersion > 0, protocolFloor > 0,
              clientIdentityFingerprint != runtimeIdentityFingerprint,
              sessionId.utf8.count == 32, receiptIsLowerHex(sessionId),
              attemptId.utf8.count == 64, receiptIsLowerHex(attemptId),
              initiatorRole == .client,
              candidateBatchByteCount > 0, candidateBatchSequence > 0,
              consumedOperations == 1,
              consumedBytes == UInt64(candidateBatchByteCount),
              previousLedgerRevision > 0,
              previousLedgerRevision < UInt64.max,
              committedLedgerRevision == previousLedgerRevision + 1,
              committedAtMs <= issuedAtMs,
              issuedAtMs <= notBeforeMs, notBeforeMs < expiresAtMs,
              expiresAtMs - issuedAtMs
                <= ProductionC1CandidateOperationReceiptContract.maximumLifetimeMs else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        switch (operation, requesterRole, candidateOwnerRole, operationAuthorizationKind) {
        case (.publish, let requester, let owner, .p2pPublish) where requester == owner:
            break
        case (.fetch, let requester, let owner, .p2pFetch) where requester != owner:
            break
        default:
            throw ProductionC1CandidateCapabilityError.roleMismatch
        }
        let expectedRequest = try ProductionC1CandidateUsageLedger.requestDigest(
            requestId: proofId,
            capabilityDigest: capabilityDigest,
            authorizationDigest: operationAuthorizationDigest
        )
        let expectedResult = try Self.commitResultDigest(
            proofId: proofId,
            requestDigest: requestDigest,
            capabilityDigest: capabilityDigest,
            operationAuthorizationDigest: operationAuthorizationDigest,
            singleUseNonce: singleUseNonce,
            consumedBytes: consumedBytes,
            previousLedgerRevision: previousLedgerRevision,
            committedLedgerRevision: committedLedgerRevision
        )
        guard requestDigest == expectedRequest, resultDigest == expectedResult else {
            throw ProductionC1CandidateCapabilityError.requestConflict
        }
        if validateSignature {
            try ProductionC1InternalBridge.validateSignature(serviceSignature)
        }
        self.status = status
        self.serviceIdDigest = serviceIdDigest
        self.keysetVersion = keysetVersion
        self.signingKeyId = signingKeyId
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
        self.ledgerId = ledgerId
        self.initiatorRole = initiatorRole
        self.operation = operation
        self.requesterRole = requesterRole
        self.candidateOwnerRole = candidateOwnerRole
        self.capabilityId = capabilityId
        self.capabilityDigest = capabilityDigest
        self.endpointOperationProofDigest = endpointOperationProofDigest
        self.proofId = proofId
        self.operationAuthorizationKind = operationAuthorizationKind
        self.operationAuthorizationDigest = operationAuthorizationDigest
        self.requestDigest = requestDigest
        self.singleUseNonce = singleUseNonce
        self.candidateBatchDigest = candidateBatchDigest
        self.candidateBatchByteCount = candidateBatchByteCount
        self.candidateBatchSequence = candidateBatchSequence
        self.candidateBatchExpiresAtMs = candidateBatchExpiresAtMs
        self.consumedOperations = consumedOperations
        self.consumedBytes = consumedBytes
        self.resultDigest = resultDigest
        self.previousLedgerRevision = previousLedgerRevision
        self.committedLedgerRevision = committedLedgerRevision
        self.previousLedgerStateCoreDigest = previousLedgerStateCoreDigest
        self.committedLedgerStateCoreDigest = committedLedgerStateCoreDigest
        self.commitRecordDigest = commitRecordDigest
        self.committedAtMs = committedAtMs
        self.issuedAtMs = issuedAtMs
        self.notBeforeMs = notBeforeMs
        self.expiresAtMs = expiresAtMs
        self.serviceSignature = serviceSignature
        guard try canonicalBytes().count
                <= ProductionC1CandidateOperationReceiptContract.maximumBytes else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
    }

    /// Readiness-only signer for module tests. Production code must obtain object 28 from a
    /// stateful service coordinator that persists and replays one canonical receipt per commit.
    /// This pure helper is deliberately not exported because it cannot enforce that durability.
    static func signedAfterAppliedCommit(
        verifiedCapability: VerifiedProductionC1CandidateCapability,
        authorization: ProductionRouteAuthorization,
        confirmedUsageReceipt: ReadbackConfirmedProductionC1CandidateUsageReceipt,
        previousLedgerState: ProductionC1CandidateUsageLedgerState,
        committedLedgerState: ProductionC1CandidateUsageLedgerState,
        committedAtMs: UInt64,
        issuedAtMs: UInt64,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        using signingKey: P256.Signing.PrivateKey
    ) throws -> Self {
        guard confirmedUsageReceipt.disposition == .applied else {
            throw ProductionC1CandidateCapabilityError.replay
        }
        try ProductionC1CandidateVerifier.validateUse(
            verifiedCapability,
            authority: authority,
            nowMs: committedAtMs
        )
        try ProductionC1CandidateUsageLedger.requireExactAuthorization(
            authorization,
            verifiedCapability: verifiedCapability
        )
        let capability = verifiedCapability.capability
        let proof = verifiedCapability.endpointOperationProof
        let usage = confirmedUsageReceipt.receipt
        let entry = usage.entry
        let authorizationDigest = ProductionC1InternalBridge.digestHex(
            try authorization.canonicalBytes()
        )
        let expectedRequestDigest = try ProductionC1CandidateUsageLedger.requestDigest(
            requestId: proof.proofId,
            capabilityDigest: verifiedCapability.capabilityDigest,
            authorizationDigest: authorizationDigest
        )
        guard entry.requestId == proof.proofId,
              entry.requestDigest == expectedRequestDigest,
              entry.capabilityDigest == verifiedCapability.capabilityDigest,
              entry.authorizationDigest == authorizationDigest,
              entry.singleUseNonce == capability.singleUseNonce,
              entry.consumedBytes == UInt64(capability.candidateBatchByteCount),
              usage.previousRevision == previousLedgerState.revision,
              usage.committedRevision == committedLedgerState.revision,
              entry.committedRevision == committedLedgerState.revision,
              previousLedgerState.revision < UInt64.max,
              committedLedgerState.revision == previousLedgerState.revision + 1,
              previousLedgerState.remainingOperations >= 1,
              previousLedgerState.remainingOperations - 1
                == committedLedgerState.remainingOperations,
              previousLedgerState.remainingBytes >= entry.consumedBytes,
              previousLedgerState.remainingBytes - entry.consumedBytes
                == committedLedgerState.remainingBytes,
              previousLedgerState.retentionLimit == committedLedgerState.retentionLimit,
              committedLedgerState.entries == previousLedgerState.entries + [entry],
              try previousLedgerState.snapshotDigestHex()
                == confirmedUsageReceipt.previousStateCoreDigest,
              try committedLedgerState.snapshotDigestHex()
                == confirmedUsageReceipt.committedStateCoreDigest,
              committedAtMs >= capability.notBeforeMs,
              committedAtMs >= proof.notBeforeMs,
              issuedAtMs >= capability.issuedAtMs,
              notBeforeMs >= capability.notBeforeMs,
              notBeforeMs >= proof.notBeforeMs,
              expiresAtMs <= capability.expiresAtMs,
              expiresAtMs <= proof.expiresAtMs,
              authority.status == .active,
              capability.pairAuthorityDigest == (try authority.digestHex()),
              capability.serviceIdDigest == verifiedKeyset.keyset.serviceIdDigest,
              capability.keysetVersion == verifiedKeyset.keyset.keysetVersion,
              capability.keysetVersion == authority.keysetVersion else {
            throw ProductionC1CandidateCapabilityError.revisionMismatch
        }
        let purpose = receiptPurpose(for: capability.operation)
        let signingKeyId = ProductionC1InternalBridge.keyId(signingKey.publicKey)
        let delegatedAtIssue = try ProductionC1InternalBridge.delegatedSigningKey(
            id: signingKeyId,
            purpose: purpose,
            in: verifiedKeyset,
            nowMs: issuedAtMs
        )
        guard expiresAtMs > 0 else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        let delegatedAtExpiry = try ProductionC1InternalBridge.delegatedSigningKey(
            id: signingKeyId,
            purpose: purpose,
            in: verifiedKeyset,
            nowMs: expiresAtMs - 1
        )
        guard delegatedAtIssue.x963Representation == signingKey.publicKey.x963Representation,
              delegatedAtExpiry.x963Representation == signingKey.publicKey.x963Representation else {
            throw ProductionC1CandidateCapabilityError.authorityMismatch
        }
        let resultDigest = try commitResultDigest(
            proofId: proof.proofId,
            requestDigest: entry.requestDigest,
            capabilityDigest: verifiedCapability.capabilityDigest,
            operationAuthorizationDigest: authorizationDigest,
            singleUseNonce: capability.singleUseNonce,
            consumedBytes: entry.consumedBytes,
            previousLedgerRevision: usage.previousRevision,
            committedLedgerRevision: usage.committedRevision
        )
        guard resultDigest == entry.receiptDigest else {
            throw ProductionC1CandidateCapabilityError.requestConflict
        }
        let unsigned = try Self(
            status: .committed,
            serviceIdDigest: capability.serviceIdDigest,
            keysetVersion: capability.keysetVersion,
            signingKeyId: signingKeyId,
            pairAuthorityDigest: capability.pairAuthorityDigest,
            pairBindingDigest: capability.pairBindingDigest,
            pairEpoch: capability.pairEpoch,
            generation: capability.generation,
            serviceConfigVersion: capability.serviceConfigVersion,
            revocationCounter: capability.revocationCounter,
            protocolFloor: capability.protocolFloor,
            clientIdentityFingerprint: capability.clientIdentityFingerprint,
            runtimeIdentityFingerprint: capability.runtimeIdentityFingerprint,
            sessionId: capability.sessionId,
            attemptId: capability.attemptId,
            ledgerId: confirmedUsageReceipt.ledgerId,
            initiatorRole: proof.initiatorRole,
            operation: capability.operation,
            requesterRole: capability.requesterRole,
            candidateOwnerRole: capability.candidateOwnerRole,
            capabilityId: capability.capabilityId,
            capabilityDigest: verifiedCapability.capabilityDigest,
            endpointOperationProofDigest: capability.endpointOperationProofDigest,
            proofId: proof.proofId,
            operationAuthorizationKind: authorization.kind,
            operationAuthorizationDigest: authorizationDigest,
            requestDigest: entry.requestDigest,
            singleUseNonce: capability.singleUseNonce,
            candidateBatchDigest: capability.candidateBatchDigest,
            candidateBatchByteCount: capability.candidateBatchByteCount,
            candidateBatchSequence: capability.candidateBatchSequence,
            candidateBatchExpiresAtMs: capability.candidateBatchExpiresAtMs,
            consumedOperations: capability.maxOperations,
            consumedBytes: entry.consumedBytes,
            resultDigest: resultDigest,
            previousLedgerRevision: usage.previousRevision,
            committedLedgerRevision: usage.committedRevision,
            previousLedgerStateCoreDigest: previousLedgerState.snapshotDigestHex(),
            committedLedgerStateCoreDigest: committedLedgerState.snapshotDigestHex(),
            commitRecordDigest: confirmedUsageReceipt.commitRecordDigest,
            committedAtMs: committedAtMs,
            issuedAtMs: issuedAtMs,
            notBeforeMs: notBeforeMs,
            expiresAtMs: expiresAtMs,
            serviceSignature: Data(),
            validateSignature: false
        )
        return try unsigned.replacingSignature(
            ProductionC1InternalBridge.sign(unsigned.signingTranscript, using: signingKey)
        )
    }

    public init(canonicalBytes data: Data) throws {
        let fields = try ProductionC1InternalBridge.decode(
            data,
            objectType: ProductionC1CandidateOperationReceiptContract.objectType,
            fieldCount: 48,
            maximumBytes: ProductionC1CandidateOperationReceiptContract.maximumBytes
        )
        guard try ProductionC1InternalBridge.text(fields[0]) == ProductionC1Contract.suite,
              try ProductionC1InternalBridge.uint64(fields[1])
                == ProductionC1CandidateOperationReceiptContract.revision,
              let status = ProductionC1CandidateOperationReceiptStatus(
                rawValue: try ProductionC1InternalBridge.text(fields[2])
              ),
              let initiator = P2PNATRole(
                rawValue: try ProductionC1InternalBridge.text(fields[18])
              ),
              let operation = ProductionC1CandidateOperation(
                rawValue: try ProductionC1InternalBridge.text(fields[19])
              ),
              let requester = P2PNATRole(
                rawValue: try ProductionC1InternalBridge.text(fields[20])
              ),
              let owner = P2PNATRole(
                rawValue: try ProductionC1InternalBridge.text(fields[21])
              ),
              let authKind = ProductionRouteAuthorizationKind(
                wireName: try ProductionC1InternalBridge.text(fields[26])
              ),
              try ProductionC1InternalBridge.text(fields[46])
                == ProductionC1Contract.signatureAlgorithm else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        try self.init(
            status: status,
            serviceIdDigest: ProductionC1InternalBridge.text(fields[3]),
            keysetVersion: ProductionC1InternalBridge.uint64(fields[4]),
            signingKeyId: ProductionC1InternalBridge.text(fields[5]),
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
            ledgerId: ProductionC1InternalBridge.text(fields[17]),
            initiatorRole: initiator,
            operation: operation,
            requesterRole: requester,
            candidateOwnerRole: owner,
            capabilityId: ProductionC1InternalBridge.text(fields[22]),
            capabilityDigest: ProductionC1InternalBridge.text(fields[23]),
            endpointOperationProofDigest: ProductionC1InternalBridge.text(fields[24]),
            proofId: ProductionC1InternalBridge.text(fields[25]),
            operationAuthorizationKind: authKind,
            operationAuthorizationDigest: ProductionC1InternalBridge.text(fields[27]),
            requestDigest: ProductionC1InternalBridge.text(fields[28]),
            singleUseNonce: ProductionC1InternalBridge.text(fields[29]),
            candidateBatchDigest: ProductionC1InternalBridge.text(fields[30]),
            candidateBatchByteCount: ProductionC1InternalBridge.uint32(fields[31]),
            candidateBatchSequence: ProductionC1InternalBridge.uint64(fields[32]),
            candidateBatchExpiresAtMs: ProductionC1InternalBridge.uint64(fields[33]),
            consumedOperations: ProductionC1InternalBridge.uint32(fields[34]),
            consumedBytes: ProductionC1InternalBridge.uint64(fields[35]),
            resultDigest: ProductionC1InternalBridge.text(fields[36]),
            previousLedgerRevision: ProductionC1InternalBridge.uint64(fields[37]),
            committedLedgerRevision: ProductionC1InternalBridge.uint64(fields[38]),
            previousLedgerStateCoreDigest: ProductionC1InternalBridge.text(fields[39]),
            committedLedgerStateCoreDigest: ProductionC1InternalBridge.text(fields[40]),
            commitRecordDigest: ProductionC1InternalBridge.text(fields[41]),
            committedAtMs: ProductionC1InternalBridge.uint64(fields[42]),
            issuedAtMs: ProductionC1InternalBridge.uint64(fields[43]),
            notBeforeMs: ProductionC1InternalBridge.uint64(fields[44]),
            expiresAtMs: ProductionC1InternalBridge.uint64(fields[45]),
            serviceSignature: fields[47],
            validateSignature: true
        )
        guard try canonicalBytes() == data else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
    }

    public func canonicalBytes() throws -> Data {
        ProductionC1InternalBridge.encode(
            objectType: ProductionC1CandidateOperationReceiptContract.objectType,
            fields: claimsFields + [serviceSignature]
        )
    }

    public func digestHex() throws -> String {
        ProductionC1InternalBridge.digestHex(try canonicalBytes())
    }

    fileprivate var signingTranscript: Data {
        ProductionC1InternalBridge.transcript(
            domain: operation == .publish
                ? "AetherLink G1a-C candidate-publish operation receipt service signature v1"
                : "AetherLink G1a-C candidate-fetch operation receipt service signature v1",
            claims: ProductionC1InternalBridge.encode(
                objectType: ProductionC1CandidateOperationReceiptContract.objectType,
                fields: claimsFields
            )
        )
    }

    fileprivate var requiredPurpose: ProductionC1DelegatedKeyPurpose {
        Self.receiptPurpose(for: operation)
    }

    private var claimsFields: [Data] {
        [
            ProductionC1InternalBridge.ascii(ProductionC1Contract.suite),
            ProductionC1InternalBridge.be(ProductionC1CandidateOperationReceiptContract.revision),
            ProductionC1InternalBridge.ascii(status.rawValue),
            ProductionC1InternalBridge.ascii(serviceIdDigest),
            ProductionC1InternalBridge.be(keysetVersion),
            ProductionC1InternalBridge.ascii(signingKeyId),
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
            ProductionC1InternalBridge.ascii(ledgerId),
            ProductionC1InternalBridge.ascii(initiatorRole.rawValue),
            ProductionC1InternalBridge.ascii(operation.rawValue),
            ProductionC1InternalBridge.ascii(requesterRole.rawValue),
            ProductionC1InternalBridge.ascii(candidateOwnerRole.rawValue),
            ProductionC1InternalBridge.ascii(capabilityId),
            ProductionC1InternalBridge.ascii(capabilityDigest),
            ProductionC1InternalBridge.ascii(endpointOperationProofDigest),
            ProductionC1InternalBridge.ascii(proofId),
            ProductionC1InternalBridge.ascii(operationAuthorizationKind.wireName),
            ProductionC1InternalBridge.ascii(operationAuthorizationDigest),
            ProductionC1InternalBridge.ascii(requestDigest),
            ProductionC1InternalBridge.ascii(singleUseNonce),
            ProductionC1InternalBridge.ascii(candidateBatchDigest),
            ProductionC1InternalBridge.be(candidateBatchByteCount),
            ProductionC1InternalBridge.be(candidateBatchSequence),
            ProductionC1InternalBridge.be(candidateBatchExpiresAtMs),
            ProductionC1InternalBridge.be(consumedOperations),
            ProductionC1InternalBridge.be(consumedBytes),
            ProductionC1InternalBridge.ascii(resultDigest),
            ProductionC1InternalBridge.be(previousLedgerRevision),
            ProductionC1InternalBridge.be(committedLedgerRevision),
            ProductionC1InternalBridge.ascii(previousLedgerStateCoreDigest),
            ProductionC1InternalBridge.ascii(committedLedgerStateCoreDigest),
            ProductionC1InternalBridge.ascii(commitRecordDigest),
            ProductionC1InternalBridge.be(committedAtMs),
            ProductionC1InternalBridge.be(issuedAtMs),
            ProductionC1InternalBridge.be(notBeforeMs),
            ProductionC1InternalBridge.be(expiresAtMs),
            ProductionC1InternalBridge.ascii(ProductionC1Contract.signatureAlgorithm),
        ]
    }

    private func replacingSignature(_ signature: Data) throws -> Self {
        try Self(
            status: status,
            serviceIdDigest: serviceIdDigest,
            keysetVersion: keysetVersion,
            signingKeyId: signingKeyId,
            pairAuthorityDigest: pairAuthorityDigest,
            pairBindingDigest: pairBindingDigest,
            pairEpoch: pairEpoch,
            generation: generation,
            serviceConfigVersion: serviceConfigVersion,
            revocationCounter: revocationCounter,
            protocolFloor: protocolFloor,
            clientIdentityFingerprint: clientIdentityFingerprint,
            runtimeIdentityFingerprint: runtimeIdentityFingerprint,
            sessionId: sessionId,
            attemptId: attemptId,
            ledgerId: ledgerId,
            initiatorRole: initiatorRole,
            operation: operation,
            requesterRole: requesterRole,
            candidateOwnerRole: candidateOwnerRole,
            capabilityId: capabilityId,
            capabilityDigest: capabilityDigest,
            endpointOperationProofDigest: endpointOperationProofDigest,
            proofId: proofId,
            operationAuthorizationKind: operationAuthorizationKind,
            operationAuthorizationDigest: operationAuthorizationDigest,
            requestDigest: requestDigest,
            singleUseNonce: singleUseNonce,
            candidateBatchDigest: candidateBatchDigest,
            candidateBatchByteCount: candidateBatchByteCount,
            candidateBatchSequence: candidateBatchSequence,
            candidateBatchExpiresAtMs: candidateBatchExpiresAtMs,
            consumedOperations: consumedOperations,
            consumedBytes: consumedBytes,
            resultDigest: resultDigest,
            previousLedgerRevision: previousLedgerRevision,
            committedLedgerRevision: committedLedgerRevision,
            previousLedgerStateCoreDigest: previousLedgerStateCoreDigest,
            committedLedgerStateCoreDigest: committedLedgerStateCoreDigest,
            commitRecordDigest: commitRecordDigest,
            committedAtMs: committedAtMs,
            issuedAtMs: issuedAtMs,
            notBeforeMs: notBeforeMs,
            expiresAtMs: expiresAtMs,
            serviceSignature: signature,
            validateSignature: true
        )
    }

    private static func receiptPurpose(
        for operation: ProductionC1CandidateOperation
    ) -> ProductionC1DelegatedKeyPurpose {
        operation == .publish ? .candidatePublishReceipt : .candidateFetchReceipt
    }

    private static func commitResultDigest(
        proofId: String,
        requestDigest: String,
        capabilityDigest: String,
        operationAuthorizationDigest: String,
        singleUseNonce: String,
        consumedBytes: UInt64,
        previousLedgerRevision: UInt64,
        committedLedgerRevision: UInt64
    ) throws -> String {
        var claims = try ProductionC1InternalBridge.rawDigest(proofId)
        claims.append(try ProductionC1InternalBridge.rawDigest(requestDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(capabilityDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(operationAuthorizationDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(singleUseNonce))
        claims.append(ProductionC1InternalBridge.be(consumedBytes))
        claims.append(ProductionC1InternalBridge.be(previousLedgerRevision))
        claims.append(ProductionC1InternalBridge.be(committedLedgerRevision))
        return receiptDomainDigest(
            "AetherLink G1a-C readback-confirmed candidate usage receipt v1",
            claims: claims
        )
    }
}

public struct VerifiedProductionC1CandidateOperationReceipt: Equatable, Sendable {
    public let receipt: ProductionC1CandidateOperationReceipt

    fileprivate init(_ receipt: ProductionC1CandidateOperationReceipt) {
        self.receipt = receipt
    }
}

public enum ProductionC1CandidateOperationReceiptVerifier {
    public static func verify(
        _ receipt: ProductionC1CandidateOperationReceipt,
        verifiedCapability: VerifiedProductionC1CandidateCapability,
        authorization: ProductionRouteAuthorization,
        authority: ProductionPairAuthorityState,
        verifiedKeyset: VerifiedProductionC1ServiceKeyset,
        nowMs: UInt64
    ) throws -> VerifiedProductionC1CandidateOperationReceipt {
        try ProductionC1CandidateVerifier.validateUse(
            verifiedCapability,
            authority: authority,
            nowMs: nowMs
        )
        try ProductionC1CandidateUsageLedger.requireExactAuthorization(
            authorization,
            verifiedCapability: verifiedCapability
        )
        let capability = verifiedCapability.capability
        let proof = verifiedCapability.endpointOperationProof
        let authorizationDigest = ProductionC1InternalBridge.digestHex(
            try authorization.canonicalBytes()
        )
        guard receipt.status == .committed,
              receipt.serviceIdDigest == capability.serviceIdDigest,
              receipt.keysetVersion == capability.keysetVersion,
              receipt.serviceIdDigest == verifiedKeyset.keyset.serviceIdDigest,
              verifiedKeyset.keyset.keysetVersion == receipt.keysetVersion
                || (receipt.keysetVersion < UInt64.max
                    && verifiedKeyset.keyset.keysetVersion == receipt.keysetVersion + 1),
              receipt.pairAuthorityDigest == (try authority.digestHex()),
              receipt.pairBindingDigest == authority.pairBindingDigest,
              receipt.pairEpoch == authority.pairEpoch,
              receipt.generation == authority.generation,
              receipt.serviceConfigVersion == authority.serviceConfigVersion,
              receipt.revocationCounter == authority.revocationCounter,
              receipt.protocolFloor == authority.protocolFloor,
              receipt.clientIdentityFingerprint == authority.clientIdentityFingerprint,
              receipt.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint,
              receipt.sessionId == capability.sessionId,
              receipt.attemptId == capability.attemptId,
              receipt.initiatorRole == proof.initiatorRole,
              receipt.operation == capability.operation,
              receipt.requesterRole == capability.requesterRole,
              receipt.candidateOwnerRole == capability.candidateOwnerRole,
              receipt.capabilityId == capability.capabilityId,
              receipt.capabilityDigest == verifiedCapability.capabilityDigest,
              receipt.endpointOperationProofDigest == capability.endpointOperationProofDigest,
              receipt.endpointOperationProofDigest == (try proof.digestHex()),
              receipt.proofId == proof.proofId,
              receipt.operationAuthorizationKind == authorization.kind,
              receipt.operationAuthorizationDigest == authorizationDigest,
              receipt.singleUseNonce == capability.singleUseNonce,
              receipt.candidateBatchDigest == capability.candidateBatchDigest,
              receipt.candidateBatchByteCount == capability.candidateBatchByteCount,
              receipt.candidateBatchSequence == capability.candidateBatchSequence,
              receipt.candidateBatchExpiresAtMs == capability.candidateBatchExpiresAtMs,
              receipt.consumedOperations == capability.maxOperations,
              receipt.consumedBytes == UInt64(capability.candidateBatchByteCount),
              receipt.committedAtMs >= capability.notBeforeMs,
              receipt.committedAtMs >= proof.notBeforeMs,
              receipt.issuedAtMs >= capability.issuedAtMs,
              receipt.notBeforeMs >= capability.notBeforeMs,
              receipt.notBeforeMs >= proof.notBeforeMs,
              receipt.expiresAtMs <= capability.expiresAtMs,
              receipt.expiresAtMs <= proof.expiresAtMs else {
            throw ProductionC1CandidateCapabilityError.authorityMismatch
        }
        try ProductionC1InternalBridge.validateWindow(
            issuedAtMs: receipt.issuedAtMs,
            notBeforeMs: receipt.notBeforeMs,
            expiresAtMs: receipt.expiresAtMs,
            maximumLifetimeMs: ProductionC1CandidateOperationReceiptContract.maximumLifetimeMs,
            nowMs: nowMs
        )
        guard let delegated = verifiedKeyset.keyset.delegatedKeys.first(where: {
            $0.keyId == receipt.signingKeyId
        }),
            delegated.keysetVersion == receipt.keysetVersion else {
            throw ProductionC1Error.keyUnavailable
        }
        guard delegated.purposes.contains(receipt.requiredPurpose) else {
            throw ProductionC1Error.keyPurposeMismatch
        }
        guard delegated.notBeforeMs <= receipt.issuedAtMs,
              delegated.notBeforeMs <= receipt.notBeforeMs else {
            throw ProductionC1Error.notYetValid
        }
        guard receipt.expiresAtMs <= delegated.expiresAtMs else {
            throw ProductionC1Error.expired
        }
        guard delegated.revokedAtMs.map({ receipt.expiresAtMs <= $0 }) ?? true else {
            throw ProductionC1Error.keyRevoked
        }
        let publicKey = try ProductionC1InternalBridge.delegatedSigningKey(
            id: receipt.signingKeyId,
            purpose: receipt.requiredPurpose,
            in: verifiedKeyset,
            nowMs: nowMs
        )
        try ProductionC1InternalBridge.verify(
            signature: receipt.serviceSignature,
            transcript: receipt.signingTranscript,
            publicKey: publicKey
        )
        return VerifiedProductionC1CandidateOperationReceipt(receipt)
    }
}

private func receiptDomainDigest(_ domain: String, claims: Data) -> String {
    ProductionC1InternalBridge.digestHex(
        ProductionC1InternalBridge.transcript(domain: domain, claims: claims)
    )
}

private func receiptIsLowerHex(_ value: String) -> Bool {
    value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
}
