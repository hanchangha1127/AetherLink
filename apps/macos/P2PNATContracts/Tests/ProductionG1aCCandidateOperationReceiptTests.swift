import CryptoKit
import Foundation
import XCTest
@testable import P2PNATContracts

final class ProductionG1aCCandidateOperationReceiptTests: XCTestCase {
    private let now: UInt64 = 1_000_000
    private let serviceId = String(repeating: "a", count: 64)

    func testObject28RoundTripsAndUsesOperationSpecificSigningDomains() throws {
        let publish = try makeFixture(operation: .publish)
        let fetch = try makeFixture(operation: .fetch)
        for fixture in [publish, fetch] {
            let bytes = try fixture.receipt.canonicalBytes()
            XCTAssertEqual(bytes[bytes.startIndex + 4], 28)
            XCTAssertLessThanOrEqual(
                bytes.count,
                ProductionC1CandidateOperationReceiptContract.maximumBytes
            )
            XCTAssertEqual(
                try ProductionC1CandidateOperationReceipt(canonicalBytes: bytes),
                fixture.receipt
            )
            XCTAssertEqual(fixture.receipt.status, .committed)
            XCTAssertEqual(fixture.receipt.consumedOperations, 1)
            _ = try ProductionC1CandidateOperationReceiptVerifier.verify(
                fixture.receipt,
                verifiedCapability: fixture.verifiedCapability,
                authorization: fixture.authorization,
                authority: fixture.authority,
                verifiedKeyset: fixture.verifiedKeyset,
                nowMs: now
            )
        }
        XCTAssertNotEqual(publish.receipt.serviceSignature, fetch.receipt.serviceSignature)
        XCTAssertNotEqual(try publish.receipt.digestHex(), try fetch.receipt.digestHex())
    }

    func testObject28RejectsBoundFieldSignatureOrderAndSizeMutations() throws {
        let fixture = try makeFixture(operation: .publish)
        let canonical = try fixture.receipt.canonicalBytes()
        let mutations: [(UInt8, Data)] = [
            (3, Data("pending".utf8)),
            (24, Data(String(repeating: "0", count: 64).utf8)),
            (25, Data(String(repeating: "0", count: 64).utf8)),
            (26, Data(String(repeating: "0", count: 64).utf8)),
            (28, Data(String(repeating: "0", count: 64).utf8)),
            (29, Data(String(repeating: "0", count: 64).utf8)),
            (30, Data(String(repeating: "0", count: 64).utf8)),
            (33, uint64Bytes(fixture.receipt.candidateBatchSequence + 1)),
            (37, Data(String(repeating: "0", count: 64).utf8)),
            (38, uint64Bytes(fixture.receipt.previousLedgerRevision + 1)),
            (40, Data(String(repeating: "0", count: 64).utf8)),
            (41, Data(String(repeating: "0", count: 64).utf8)),
            (42, Data(String(repeating: "0", count: 64).utf8)),
            (46, uint64Bytes(fixture.receipt.notBeforeMs)),
        ]
        for (tag, value) in mutations {
            assertReceiptRejected(
                try replacingTLVField(in: canonical, tag: tag, with: value),
                fixture: fixture,
                id: "tag-\(tag)"
            )
        }

        var signature = fixture.receipt.serviceSignature
        signature[signature.index(before: signature.endIndex)] ^= 0x01
        assertReceiptRejected(
            try replacingTLVField(in: canonical, tag: 48, with: signature),
            fixture: fixture,
            id: "signature"
        )
        XCTAssertThrowsError(try ProductionC1CandidateOperationReceipt(
            canonicalBytes: try swappingTLVFields(in: canonical, firstTag: 23, secondTag: 24)
        ))
        var oversized = canonical
        oversized.append(Data(
            repeating: 0,
            count: ProductionC1CandidateOperationReceiptContract.maximumBytes
        ))
        XCTAssertThrowsError(try ProductionC1CandidateOperationReceipt(
            canonicalBytes: oversized
        ))
    }

    func testVerifierRejectsCapabilityProofAndAuthorizationSubstitution() throws {
        let publish = try makeFixture(operation: .publish)
        let fetch = try makeFixture(operation: .fetch)
        XCTAssertThrowsError(try ProductionC1CandidateOperationReceiptVerifier.verify(
            publish.receipt,
            verifiedCapability: fetch.verifiedCapability,
            authorization: fetch.authorization,
            authority: fetch.authority,
            verifiedKeyset: fetch.verifiedKeyset,
            nowMs: now
        ))
        XCTAssertThrowsError(try ProductionC1CandidateOperationReceiptVerifier.verify(
            publish.receipt,
            verifiedCapability: publish.verifiedCapability,
            authorization: fetch.authorization,
            authority: publish.authority,
            verifiedKeyset: publish.verifiedKeyset,
            nowMs: now
        ))
    }

    func testReceiptPurposeRotationRevocationAndExpiryAreCheckedAtUse() throws {
        XCTAssertThrowsError(try makeFixture(
            operation: .publish,
            receiptPurposes: [.candidateFetchReceipt]
        )) {
            XCTAssertEqual($0 as? ProductionC1Error, .keyPurposeMismatch)
        }
        let fixture = try makeFixture(operation: .publish)
        let rotated = try alternateKeyset(
            fixture,
            version: 2,
            delegatedVersion: 1,
            purposes: [.candidatePublishReceipt],
            notBeforeMs: now - 1_000,
            expiresAtMs: now + 100_000
        )
        _ = try ProductionC1CandidateOperationReceiptVerifier.verify(
            fixture.receipt,
            verifiedCapability: fixture.verifiedCapability,
            authorization: fixture.authorization,
            authority: fixture.authority,
            verifiedKeyset: rotated,
            nowMs: now
        )

        let wrongPurpose = try alternateKeyset(
            fixture,
            purposes: [.candidateFetchReceipt],
            notBeforeMs: now - 1_000,
            expiresAtMs: now + 100_000
        )
        XCTAssertThrowsError(try ProductionC1CandidateOperationReceiptVerifier.verify(
            fixture.receipt,
            verifiedCapability: fixture.verifiedCapability,
            authorization: fixture.authorization,
            authority: fixture.authority,
            verifiedKeyset: wrongPurpose,
            nowMs: now
        )) {
            XCTAssertEqual($0 as? ProductionC1Error, .keyPurposeMismatch)
        }
        let revoked = try alternateKeyset(
            fixture,
            purposes: [.candidatePublishReceipt],
            notBeforeMs: now - 1_000,
            expiresAtMs: now + 100_000,
            revokedAtMs: now
        )
        XCTAssertThrowsError(try ProductionC1CandidateOperationReceiptVerifier.verify(
            fixture.receipt,
            verifiedCapability: fixture.verifiedCapability,
            authorization: fixture.authorization,
            authority: fixture.authority,
            verifiedKeyset: revoked,
            nowMs: now
        )) {
            XCTAssertEqual($0 as? ProductionC1Error, .keyRevoked)
        }
        let expired = try alternateKeyset(
            fixture,
            purposes: [.candidatePublishReceipt],
            notBeforeMs: now - 1_000,
            expiresAtMs: now
        )
        XCTAssertThrowsError(try ProductionC1CandidateOperationReceiptVerifier.verify(
            fixture.receipt,
            verifiedCapability: fixture.verifiedCapability,
            authorization: fixture.authorization,
            authority: fixture.authority,
            verifiedKeyset: expired,
            nowMs: now
        )) {
            XCTAssertEqual($0 as? ProductionC1Error, .expired)
        }
        XCTAssertThrowsError(try ProductionC1CandidateOperationReceiptVerifier.verify(
            fixture.receipt,
            verifiedCapability: fixture.verifiedCapability,
            authorization: fixture.authorization,
            authority: fixture.authority,
            verifiedKeyset: fixture.verifiedKeyset,
            nowMs: fixture.receipt.expiresAtMs
        )) {
            XCTAssertEqual($0 as? ProductionC1Error, .expired)
        }
    }

    func testIdempotentRetryCannotCreateAnotherObject28Signature() throws {
        let fixture = try makeFixture(operation: .publish)
        let entry = fixture.confirmedUsageReceipt.receipt.entry
        let retry = try ProductionC1CandidateUsageLedger.prepareConsume(
            state: fixture.committedState,
            expectedRevision: UInt64.max,
            expectedSnapshotDigest: String(repeating: "f", count: 64),
            requestId: entry.requestId,
            requestDigest: entry.requestDigest,
            verifiedCapability: fixture.verifiedCapability,
            authorization: fixture.authorization,
            authenticatedLocalRole: fixture.verifiedCapability.capability.requesterRole,
            authenticatedLocalIdentityFingerprint:
                fixture.verifiedCapability.capability.requesterIdentityFingerprint,
            authority: fixture.authority,
            nowMs: fixture.verifiedCapability.capability.expiresAtMs
        )
        XCTAssertEqual(retry.disposition, .idempotent)
        let confirmedRetry = try ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
            retry,
            committedReadback: fixture.committedState,
            ledgerId: fixture.receipt.ledgerId,
            commitRecordDigest: fixture.receipt.commitRecordDigest
        )
        XCTAssertThrowsError(try ProductionC1CandidateOperationReceipt.signedAfterAppliedCommit(
            verifiedCapability: fixture.verifiedCapability,
            authorization: fixture.authorization,
            confirmedUsageReceipt: confirmedRetry,
            previousLedgerState: fixture.previousState,
            committedLedgerState: fixture.committedState,
            committedAtMs: now,
            issuedAtMs: now,
            notBeforeMs: now,
            expiresAtMs: now + 10_000,
            authority: fixture.authority,
            verifiedKeyset: fixture.verifiedKeyset,
            using: fixture.receiptKey
        )) {
            XCTAssertEqual($0 as? ProductionC1CandidateCapabilityError, .replay)
        }
    }

    func testReadbackTokenRejectsLedgerStateCoreSubstitution() throws {
        let fixture = try makeFixture(operation: .publish)
        let alternatePrevious = try ProductionC1CandidateUsageLedgerState(
            revision: fixture.previousState.revision,
            remainingOperations: fixture.previousState.remainingOperations,
            remainingBytes: fixture.previousState.remainingBytes,
            retentionLimit: fixture.previousState.retentionLimit + 1,
            entries: fixture.previousState.entries
        )
        let alternateCommitted = try ProductionC1CandidateUsageLedgerState(
            revision: fixture.committedState.revision,
            remainingOperations: fixture.committedState.remainingOperations,
            remainingBytes: fixture.committedState.remainingBytes,
            retentionLimit: fixture.committedState.retentionLimit + 1,
            entries: fixture.committedState.entries
        )

        XCTAssertThrowsError(try ProductionC1CandidateOperationReceipt.signedAfterAppliedCommit(
            verifiedCapability: fixture.verifiedCapability,
            authorization: fixture.authorization,
            confirmedUsageReceipt: fixture.confirmedUsageReceipt,
            previousLedgerState: alternatePrevious,
            committedLedgerState: alternateCommitted,
            committedAtMs: now,
            issuedAtMs: now,
            notBeforeMs: now,
            expiresAtMs: now + 10_000,
            authority: fixture.authority,
            verifiedKeyset: fixture.verifiedKeyset,
            using: fixture.receiptKey
        )) {
            XCTAssertEqual($0 as? ProductionC1CandidateCapabilityError, .revisionMismatch)
        }
    }

    private struct Fixture {
        let rootKey: P256.Signing.PrivateKey
        let receiptKey: P256.Signing.PrivateKey
        let authority: ProductionPairAuthorityState
        let verifiedKeyset: VerifiedProductionC1ServiceKeyset
        let verifiedCapability: VerifiedProductionC1CandidateCapability
        let authorization: ProductionRouteAuthorization
        let previousState: ProductionC1CandidateUsageLedgerState
        let committedState: ProductionC1CandidateUsageLedgerState
        let confirmedUsageReceipt: ReadbackConfirmedProductionC1CandidateUsageReceipt
        let receipt: ProductionC1CandidateOperationReceipt
    }

    private func makeFixture(
        operation: ProductionC1CandidateOperation,
        receiptPurposes: ProductionC1DelegatedKeyPurpose? = nil
    ) throws -> Fixture {
        let root = try privateKey(1)
        let capabilityKey = try privateKey(2)
        let receiptKey = try privateKey(3)
        let expectedReceiptPurpose: ProductionC1DelegatedKeyPurpose = operation == .publish
            ? .candidatePublishReceipt : .candidateFetchReceipt
        let capabilityPurpose: ProductionC1DelegatedKeyPurpose = operation == .publish
            ? .candidatePublish : .candidateFetch
        let delegated = [
            try ProductionC1DelegatedKey(
                keysetVersion: 1,
                keyId: keyId(capabilityKey.publicKey),
                purposes: capabilityPurpose,
                notBeforeMs: now - 1_000,
                expiresAtMs: now + 100_000,
                publicKeyX963: capabilityKey.publicKey.x963Representation
            ),
            try ProductionC1DelegatedKey(
                keysetVersion: 1,
                keyId: keyId(receiptKey.publicKey),
                purposes: receiptPurposes ?? expectedReceiptPurpose,
                notBeforeMs: now - 1_000,
                expiresAtMs: now + 100_000,
                publicKeyX963: receiptKey.publicKey.x963Representation
            ),
        ]
        let keyset = try ProductionC1ServiceKeyset.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            previousKeysetDigest: nil,
            issuedAtMs: now - 1_000,
            expiresAtMs: now + 100_000,
            delegatedKeys: delegated.sorted { $0.keyId < $1.keyId },
            using: root
        )
        let verifiedKeyset = try ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: root.publicKey,
            minimumAcceptedKeysetVersion: 1,
            nowMs: now
        )
        let clientIdentity = try privateKey(10)
        let runtimeIdentity = try privateKey(11)
        let authority = try ProductionPairAuthorityState(
            pairBindingDigest: String(repeating: "d", count: 64),
            pairEpoch: 1,
            clientIdentityFingerprint: keyId(clientIdentity.publicKey),
            runtimeIdentityFingerprint: keyId(runtimeIdentity.publicKey),
            generation: 1,
            serviceConfigVersion: 1,
            keysetVersion: 1,
            revocationCounter: 0,
            protocolFloor: 1,
            status: .active,
            transitionId: String(repeating: "1", count: 64),
            transitionRequestDigest: String(repeating: "2", count: 64),
            acceptedReceiptDigest: String(repeating: "e", count: 64),
            authorityRevision: 1
        )
        let context = try ProductionC1PreauthorizationSessionContext(
            sessionId: String(repeating: "a", count: 32),
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: try privateKey(20).publicKey.x963Representation,
            runtimeEphemeralPublicKey: try privateKey(21).publicKey.x963Representation,
            clientNonce: String(repeating: "c", count: 32),
            runtimeNonce: String(repeating: "d", count: 32),
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            keysetVersion: authority.keysetVersion,
            revocationCounter: authority.revocationCounter,
            routeKind: .p2pDirect
        )
        let requester: P2PNATRole = .client
        let owner: P2PNATRole = operation == .publish ? .client : .runtime
        let identityKey = clientIdentity
        let batch = try CandidateBatch(
            sessionId: context.sessionId,
            generation: authority.generation,
            sequence: operation == .publish ? 1 : 2,
            expires: now + 30_000,
            role: owner,
            candidates: [try P2PNATCandidate(
                kind: .srflx,
                family: .ipv4,
                port: 50_000,
                priority: 100,
                foundation: Data(repeating: operation == .publish ? 1 : 2, count: 8),
                address: Data(operation == .publish ? [1, 1, 1, 1] : [8, 8, 4, 4])
            )]
        )
        let proofId = String(repeating: operation == .publish ? "3" : "4", count: 64)
        let capabilityId = String(repeating: operation == .publish ? "5" : "6", count: 64)
        let nonce = String(repeating: operation == .publish ? "7" : "8", count: 64)
        let proof = try ProductionC1EndpointOperationProof.signed(
            requesterRole: requester,
            operation: operation,
            candidateOwnerRole: owner,
            proofId: proofId,
            attemptId: String(repeating: "b", count: 64),
            capabilityId: capabilityId,
            candidateBatch: batch,
            singleUseNonce: nonce,
            securityContext: context,
            serviceAudienceId: serviceId,
            authority: authority,
            issuedAtMs: now - 200,
            notBeforeMs: now - 10,
            expiresAtMs: now + 20_000,
            using: identityKey
        )
        let capability = try ProductionC1CandidateCapability.signed(
            operation: operation,
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            capabilityId: capabilityId,
            attemptId: proof.attemptId,
            requesterRole: requester,
            candidateOwnerRole: owner,
            maximumCandidateBytes: UInt64(P2PNATLimits.candidateBatchBytes),
            singleUseNonce: nonce,
            issuedAtMs: now - 100,
            notBeforeMs: now - 10,
            expiresAtMs: now + 20_000,
            authority: authority,
            candidateBatch: batch,
            endpointOperationProof: proof,
            using: capabilityKey
        )
        let verifiedCapability = try ProductionC1CandidateVerifier.verifyCapability(
            capability,
            candidateBatchCanonicalBytes: batch.canonicalBytes(),
            endpointOperationProof: proof,
            securityContext: context,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            nowMs: now
        )
        let authorization: ProductionRouteAuthorization = operation == .publish
            ? .p2pPublish(
                pairBindingDigest: authority.pairBindingDigest,
                pairEpoch: authority.pairEpoch,
                generation: authority.generation,
                candidateBatchDigest: capability.candidateBatchDigest,
                publishCapabilityDigest: verifiedCapability.capabilityDigest
            )
            : .p2pFetch(
                pairBindingDigest: authority.pairBindingDigest,
                pairEpoch: authority.pairEpoch,
                generation: authority.generation,
                candidateBatchDigest: capability.candidateBatchDigest,
                fetchCapabilityDigest: verifiedCapability.capabilityDigest
            )
        let previous = try ProductionC1CandidateUsageLedgerState(
            remainingOperations: 1,
            remainingBytes: UInt64(capability.candidateBatchByteCount),
            retentionLimit: 4
        )
        let authorizationDigest = digest(try authorization.canonicalBytes())
        let requestDigest = try ProductionC1CandidateUsageLedger.requestDigest(
            requestId: proofId,
            capabilityDigest: verifiedCapability.capabilityDigest,
            authorizationDigest: authorizationDigest
        )
        let preparation = try ProductionC1CandidateUsageLedger.prepareConsume(
            state: previous,
            expectedRevision: previous.revision,
            expectedSnapshotDigest: try previous.snapshotDigestHex(),
            requestId: proofId,
            requestDigest: requestDigest,
            verifiedCapability: verifiedCapability,
            authorization: authorization,
            authenticatedLocalRole: requester,
            authenticatedLocalIdentityFingerprint: authority.clientIdentityFingerprint,
            authority: authority,
            nowMs: now
        )
        let committed = preparation.nextState
        let ledgerId = digest(Data("object28-ledger".utf8))
        let commitRecordDigest = digest(Data("object28-commit-\(operation.rawValue)".utf8))
        let confirmed = try ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
            preparation,
            committedReadback: committed,
            ledgerId: ledgerId,
            commitRecordDigest: commitRecordDigest
        )
        let receipt = try ProductionC1CandidateOperationReceipt.signedAfterAppliedCommit(
            verifiedCapability: verifiedCapability,
            authorization: authorization,
            confirmedUsageReceipt: confirmed,
            previousLedgerState: previous,
            committedLedgerState: committed,
            committedAtMs: now,
            issuedAtMs: now,
            notBeforeMs: now,
            expiresAtMs: now + 10_000,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            using: receiptKey
        )
        return Fixture(
            rootKey: root,
            receiptKey: receiptKey,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            verifiedCapability: verifiedCapability,
            authorization: authorization,
            previousState: previous,
            committedState: committed,
            confirmedUsageReceipt: confirmed,
            receipt: receipt
        )
    }

    private func alternateKeyset(
        _ fixture: Fixture,
        version: UInt64 = 1,
        delegatedVersion: UInt64 = 1,
        purposes: ProductionC1DelegatedKeyPurpose,
        notBeforeMs: UInt64,
        expiresAtMs: UInt64,
        revokedAtMs: UInt64? = nil
    ) throws -> VerifiedProductionC1ServiceKeyset {
        let key = try ProductionC1DelegatedKey(
            keysetVersion: delegatedVersion,
            keyId: keyId(fixture.receiptKey.publicKey),
            purposes: purposes,
            notBeforeMs: notBeforeMs,
            expiresAtMs: expiresAtMs,
            revokedAtMs: revokedAtMs,
            publicKeyX963: fixture.receiptKey.publicKey.x963Representation
        )
        var delegatedKeys = [key]
        if version != delegatedVersion {
            let currentKey = try privateKey(2)
            delegatedKeys.append(try ProductionC1DelegatedKey(
                keysetVersion: version,
                keyId: keyId(currentKey.publicKey),
                purposes: [.routeCapability],
                notBeforeMs: now - 1_000,
                expiresAtMs: now + 100_000,
                publicKeyX963: currentKey.publicKey.x963Representation
            ))
        }
        let keyset = try ProductionC1ServiceKeyset.signed(
            serviceIdDigest: serviceId,
            keysetVersion: version,
            previousKeysetDigest: version == 1
                ? nil : try fixture.verifiedKeyset.keyset.digestHex(),
            issuedAtMs: now - 1_000,
            expiresAtMs: now + 100_000,
            delegatedKeys: delegatedKeys.sorted { $0.keyId < $1.keyId },
            using: fixture.rootKey
        )
        return try ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: fixture.rootKey.publicKey,
            minimumAcceptedKeysetVersion: version,
            nowMs: now - 1
        )
    }

    private func assertReceiptRejected(
        _ bytes: Data,
        fixture: Fixture,
        id: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertThrowsError(try {
            let receipt = try ProductionC1CandidateOperationReceipt(canonicalBytes: bytes)
            _ = try ProductionC1CandidateOperationReceiptVerifier.verify(
                receipt,
                verifiedCapability: fixture.verifiedCapability,
                authorization: fixture.authorization,
                authority: fixture.authority,
                verifiedKeyset: fixture.verifiedKeyset,
                nowMs: now
            )
        }(), id, file: file, line: line)
    }

    private func replacingTLVField(
        in data: Data,
        tag: UInt8,
        with replacement: Data
    ) throws -> Data {
        var fields = try tlvFields(data)
        guard let index = fields.firstIndex(where: { $0.0 == tag }) else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        fields[index].1 = replacement
        return encodeTLVHeader(data, fields: fields)
    }

    private func swappingTLVFields(
        in data: Data,
        firstTag: UInt8,
        secondTag: UInt8
    ) throws -> Data {
        var fields = try tlvFields(data)
        guard let first = fields.firstIndex(where: { $0.0 == firstTag }),
              let second = fields.firstIndex(where: { $0.0 == secondTag }) else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        fields.swapAt(first, second)
        return encodeTLVHeader(data, fields: fields)
    }

    private func tlvFields(_ data: Data) throws -> [(UInt8, Data)] {
        guard data.count >= 6 else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        var fields: [(UInt8, Data)] = []
        var cursor = 6
        while cursor < data.count {
            guard cursor + 5 <= data.count else {
                throw ProductionC1CandidateCapabilityError.malformedCanonical
            }
            let tag = data[cursor]
            let length = data[(cursor + 1)..<(cursor + 5)].reduce(UInt32(0)) {
                ($0 << 8) | UInt32($1)
            }
            let start = cursor + 5
            let end = start + Int(length)
            guard end <= data.count else {
                throw ProductionC1CandidateCapabilityError.malformedCanonical
            }
            fields.append((tag, Data(data[start..<end])))
            cursor = end
        }
        return fields
    }

    private func encodeTLVHeader(
        _ original: Data,
        fields: [(UInt8, Data)]
    ) -> Data {
        var output = Data(original.prefix(6))
        for (tag, value) in fields {
            output.append(tag)
            var length = UInt32(value.count).bigEndian
            Swift.withUnsafeBytes(of: &length) { output.append(contentsOf: $0) }
            output.append(value)
        }
        return output
    }

    private func uint64Bytes(_ value: UInt64) -> Data {
        var encoded = value.bigEndian
        return Swift.withUnsafeBytes(of: &encoded) { Data($0) }
    }

    private func privateKey(_ scalar: UInt8) throws -> P256.Signing.PrivateKey {
        var raw = Data(repeating: 0, count: 32)
        raw[31] = scalar
        return try P256.Signing.PrivateKey(rawRepresentation: raw)
    }

    private func keyId(_ key: P256.Signing.PublicKey) -> String {
        digest(key.derRepresentation)
    }

    private func digest(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }
}
