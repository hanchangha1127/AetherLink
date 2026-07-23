import CryptoKit
import Foundation
import XCTest
@_spi(AuthorityLifecycle) @testable import P2PNATContracts
@_spi(ProductionTransport) @_spi(TrustedDeviceTesting) @testable import TrustedDevices

final class ProductionG1aCCandidateCapabilityTests: XCTestCase {
    func testEndpointLedgerPersistenceMatchesAndroidObject4Object26Bytes() throws {
        let entry = ProductionC1EndpointGrantEntry(
            admissionId: String(repeating: "1", count: 64),
            bindingDigest: String(repeating: "2", count: 64),
            routeGrantDigest: String(repeating: "3", count: 64),
            sessionId: String(repeating: "4", count: 32),
            transcriptDigest: String(repeating: "5", count: 64),
            routeAuthorizationDigest: String(repeating: "6", count: 64),
            grantAuthorizationDigest: String(repeating: "9", count: 64),
            connectorInputCommitmentDigest: String(repeating: "7", count: 64),
            pairSnapshotDigest: String(repeating: "8", count: 64),
            committedRevision: 2
        )
        let state = try ProductionC1EndpointGrantLedgerState(
            revision: 2,
            pairAuthorityDigest: String(repeating: "a", count: 64),
            pairLocalRevision: 2,
            remainingGrants: 1,
            retentionLimit: 8,
            entries: [entry]
        )
        let expectedHex =
            "414c433145474c31000000020000000000000002" +
            String(repeating: "a", count: 64) +
            "000000000000000200000000000000010000000800000001" +
            String(repeating: "1", count: 64) +
            String(repeating: "2", count: 64) +
            String(repeating: "3", count: 64) +
            String(repeating: "5", count: 64) +
            String(repeating: "6", count: 64) +
            String(repeating: "9", count: 64) +
            String(repeating: "7", count: 64) +
            String(repeating: "8", count: 64) +
            String(repeating: "34", count: 32) +
            "0000000000000002"
        let encoded = try state.persistenceCanonicalBytes()
        XCTAssertEqual(
            encoded.map { String(format: "%02x", $0) }.joined(),
            expectedHex
        )
        XCTAssertEqual(
            try ProductionC1EndpointGrantLedgerState(persistenceCanonicalBytes: encoded),
            state
        )
    }

    func testEndpointAdmissionBindingMatchesObject4Object26CrossPlatformVector() throws {
        XCTAssertEqual(
            try ProductionC1EndpointGrantAdmission.bindingDigest(
                admissionId: String(repeating: "00", count: 32),
                routeGrantDigest: String(repeating: "11", count: 32),
                transcriptDigest: String(repeating: "22", count: 32),
                routeAuthorizationDigest: String(repeating: "33", count: 32),
                grantAuthorizationDigest: String(repeating: "44", count: 32),
                connectorInputCommitmentDigest: String(repeating: "55", count: 32)
            ),
            "6e405627c9f8c876db1755f1fae47185bcb4b00384e5850665bff4aa78f0b784"
        )
    }

    func testKeyScheduleBindingAcceptsBothRolesAndRejectsStaleAuthorization() throws {
        let fixture = try makeFixture()
        let committed = try commitAllOperations(fixture)
        let grant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: committed.operationReceipts,
            initiatorRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        let transcript = try makeTranscript(
            fixture,
            routeAuthorizationDigest: grant.grantAuthorization.digestHex
        )

        let client = try ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
            transcript: transcript,
            verifiedGrant: grant,
            localRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        let runtime = try ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
            transcript: transcript,
            verifiedGrant: grant,
            localRole: .runtime,
            authority: fixture.authority,
            nowMs: now
        )
        XCTAssertEqual(client.transcript, transcript)
        XCTAssertEqual(client.grantAuthorization, grant.grantAuthorization)
        XCTAssertEqual(client.securityContext, fixture.securityContext)
        XCTAssertEqual(client.localRole, .client)
        XCTAssertEqual(runtime.localRole, .runtime)

        let object4BoundTranscript = try makeTranscript(
            fixture,
            routeAuthorizationDigest: digest(
                try fixture.authorizations.finalP2PDirect.canonicalBytes()
            )
        )
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
                transcript: object4BoundTranscript,
                verifiedGrant: grant,
                localRole: .client,
                authority: fixture.authority,
                nowMs: now
            )
        }
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
                transcript: transcript,
                verifiedGrant: grant,
                localRole: .client,
                authority: fixture.authority,
                nowMs: grant.evidence.expiresAtMs
            )
        }

        let driftedAuthority = try ProductionPairAuthorityState(
            pairBindingDigest: fixture.authority.pairBindingDigest,
            pairEpoch: fixture.authority.pairEpoch,
            clientIdentityFingerprint: fixture.authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: fixture.authority.runtimeIdentityFingerprint,
            generation: fixture.authority.generation,
            serviceConfigVersion: fixture.authority.serviceConfigVersion,
            keysetVersion: fixture.authority.keysetVersion,
            revocationCounter: fixture.authority.revocationCounter + 1,
            protocolFloor: fixture.authority.protocolFloor,
            status: fixture.authority.status,
            transitionId: fixture.authority.transitionId,
            transitionRequestDigest: fixture.authority.transitionRequestDigest,
            acceptedReceiptDigest: fixture.authority.acceptedReceiptDigest,
            authorityRevision: fixture.authority.authorityRevision + 1
        )
        assertCandidateError(.authorityMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
                transcript: transcript,
                verifiedGrant: grant,
                localRole: .runtime,
                authority: driftedAuthority,
                nowMs: now
            )
        }
    }

    private let now: UInt64 = 1_000_000
    private let serviceId = String(repeating: "a", count: 64)

    func testFourCapabilitiesRoundTripAggregateAndGenericP2PBypassIsClosed() throws {
        let fixture = try makeFixture()
        for value in fixture.bilateralValues {
            XCTAssertEqual(
                try ProductionC1CandidateCapability(canonicalBytes: value.capability.canonicalBytes()),
                value.capability
            )
            XCTAssertEqual(value.capability.maxOperations, 1)
            XCTAssertLessThanOrEqual(
                UInt64(value.capability.candidateBatchByteCount),
                value.capability.maximumCandidateBytes
            )
        }
        XCTAssertEqual(
            fixture.plan.pathValidationReceipt.candidatePairDigest,
            ProductionC1CandidateVerifier.selectedCandidatePairDigest(
                clientCandidate: fixture.plan.selectedClientCandidate,
                runtimeCandidate: fixture.plan.selectedRuntimeCandidate
            )
        )
        XCTAssertNotEqual(
            fixture.bilateral.bilateralPublishDigest,
            fixture.bilateral.bilateralFetchDigest
        )
        XCTAssertThrowsError(try ProductionC1Verifier.verifyRoutePlan(
            claims: fixture.claims,
            capability: fixture.routeCapability,
            securityContext: fixture.securityContext,
            authority: fixture.authority,
            verifiedKeyset: fixture.verifiedKeyset,
            nowMs: now
        )) { XCTAssertEqual($0 as? ProductionC1Error, .routeMismatch) }
        XCTAssertThrowsError(try ProductionC1Verifier.makeRouteAuthorization(
            for: fixture.unwrappedBasePlan,
            nowMs: now
        )) { XCTAssertEqual($0 as? ProductionC1Error, .routeMismatch) }
    }

    func testPublicOnlyDestinationRejectsLoopbackAndLowPort() throws {
        let fixture = try makeFixture()
        let rejected: [(Data, UInt16)] = [
            (Data([127, 0, 0, 1]), 50_000),
            (Data([100, 64, 0, 1]), 50_000),
            (Data([240, 0, 0, 1]), 50_000),
            (Data([8, 8, 4, 4]), 443),
            (Data([9, 9, 9, 9]), 50_000),
            (Data([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff, 127, 0, 0, 1]), 50_000),
            (Data([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff, 10, 0, 0, 1]), 50_000),
        ]
        for (address, port) in rejected {
            let connector = try makeConnector(
                address: address,
                port: port,
                pathDigest: fixture.plan.pathValidationReceiptDigest
            )
            let claims = try makeClaims(
                connector: connector,
                securityContext: fixture.securityContext,
                authority: fixture.authority
            )
            let capability = try routeCapability(
                claims: claims,
                authority: fixture.authority,
                key: fixture.signingKey
            )
            assertCandidateError(.routeMismatch) {
                _ = try ProductionC1CandidateVerifier.verifyP2PDirectPlan(
                    claims: claims,
                    capability: capability,
                    securityContext: fixture.securityContext,
                    bilateral: fixture.bilateral,
                    selectedClientCandidate: fixture.plan.selectedClientCandidate,
                    selectedRuntimeCandidate: fixture.plan.selectedRuntimeCandidate,
                    pathValidationReceiptCanonicalBytes:
                        fixture.plan.pathValidationReceipt.canonicalBytes(),
                    authority: fixture.authority,
                    verifiedKeyset: fixture.verifiedKeyset,
                    nowMs: now
                )
            }
        }
    }

    func testUsageCASIsAtomicReplaySafeAndExactRetrySurvivesExpiry() throws {
        let fixture = try makeFixture()
        var state = try initialUsageState(fixture)
        let first = fixture.bilateralValues[0]
        let firstAuthorization = fixture.operationAuthorizations[0]
        let requestId = String(repeating: "1", count: 64)
        let authorizationDigest = digest(try firstAuthorization.canonicalBytes())
        let requestDigest = try ProductionC1CandidateUsageLedger.requestDigest(
            requestId: requestId,
            capabilityDigest: first.capabilityDigest,
            authorizationDigest: authorizationDigest
        )
        let snapshot = try state.snapshotDigestHex()
        let preparation = try ProductionC1CandidateUsageLedger.prepareConsume(
            state: state,
            expectedRevision: state.revision,
            expectedSnapshotDigest: snapshot,
            requestId: requestId,
            requestDigest: requestDigest,
            verifiedCapability: first,
            authorization: firstAuthorization,
            authenticatedLocalRole: first.capability.requesterRole,
            authenticatedLocalIdentityFingerprint:
                first.capability.requesterIdentityFingerprint,
            authority: fixture.authority,
            nowMs: now
        )
        XCTAssertEqual(preparation.disposition, .applied)
        XCTAssertEqual(state, try initialUsageState(fixture))
        state = preparation.nextState
        _ = try ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
            preparation,
            committedReadback: state,
            ledgerId: String(repeating: "a", count: 64),
            commitRecordDigest: String(repeating: "b", count: 64)
        )

        let retry = try ProductionC1CandidateUsageLedger.prepareConsume(
            state: state,
            expectedRevision: 999,
            expectedSnapshotDigest: String(repeating: "f", count: 64),
            requestId: requestId,
            requestDigest: requestDigest,
            verifiedCapability: first,
            authorization: firstAuthorization,
            authenticatedLocalRole: first.capability.requesterRole,
            authenticatedLocalIdentityFingerprint:
                first.capability.requesterIdentityFingerprint,
            authority: fixture.authority,
            nowMs: first.capability.expiresAtMs
        )
        XCTAssertEqual(retry.disposition, .idempotent)
        XCTAssertEqual(retry.nextState, state)
        _ = try ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
            retry,
            committedReadback: state,
            ledgerId: String(repeating: "a", count: 64),
            commitRecordDigest: String(repeating: "b", count: 64)
        )
        let reloadRetry = try ProductionC1CandidateUsageLedger.prepareCommittedRetry(
            state: state,
            requestId: requestId,
            requestDigest: requestDigest,
            capabilityCanonicalBytes: first.capability.canonicalBytes(),
            authorization: firstAuthorization
        )
        XCTAssertEqual(reloadRetry.disposition, .idempotent)
        _ = try ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
            reloadRetry,
            committedReadback: state,
            ledgerId: String(repeating: "a", count: 64),
            commitRecordDigest: String(repeating: "b", count: 64)
        )

        let replayId = String(repeating: "2", count: 64)
        let replayDigest = try ProductionC1CandidateUsageLedger.requestDigest(
            requestId: replayId,
            capabilityDigest: first.capabilityDigest,
            authorizationDigest: authorizationDigest
        )
        assertCandidateError(.roleMismatch) {
            _ = try ProductionC1CandidateUsageLedger.prepareConsume(
                state: state,
                expectedRevision: state.revision,
                expectedSnapshotDigest: try state.snapshotDigestHex(),
                requestId: replayId,
                requestDigest: replayDigest,
                verifiedCapability: first,
                authorization: firstAuthorization,
                authenticatedLocalRole: first.capability.requesterRole,
                authenticatedLocalIdentityFingerprint:
                    first.capability.requesterIdentityFingerprint,
                authority: fixture.authority,
                nowMs: now
            )
        }

        let second = fixture.bilateralValues[1]
        let secondAuthorization = fixture.operationAuthorizations[1]
        let secondId = second.endpointOperationProof.proofId
        let secondDigest = try ProductionC1CandidateUsageLedger.requestDigest(
            requestId: secondId,
            capabilityDigest: second.capabilityDigest,
            authorizationDigest: digest(try secondAuthorization.canonicalBytes())
        )
        let competing = try ProductionC1CandidateUsageLedger.prepareConsume(
            state: state,
            expectedRevision: state.revision,
            expectedSnapshotDigest: try state.snapshotDigestHex(),
            requestId: secondId,
            requestDigest: secondDigest,
            verifiedCapability: second,
            authorization: secondAuthorization,
            authenticatedLocalRole: second.capability.requesterRole,
            authenticatedLocalIdentityFingerprint:
                second.capability.requesterIdentityFingerprint,
            authority: fixture.authority,
            nowMs: now
        )
        XCTAssertThrowsError(try ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
            competing,
            committedReadback: state,
            ledgerId: String(repeating: "a", count: 64),
            commitRecordDigest: String(repeating: "b", count: 64)
        ))
    }

    func testGrantEvidenceRequiresFourReadbackConfirmedOperationsAndRoundTrips() throws {
        let fixture = try makeFixture()
        let committed = try commitAllOperations(fixture)
        assertCandidateError(.quotaExceeded) {
            _ = try ProductionC1CandidateVerifier.deriveGrantEvidence(
                plan: fixture.plan,
                routeAuthorizations: fixture.authorizations,
                operationReceipts: Array(committed.operationReceipts.prefix(3)),
                initiatorRole: .client,
                authority: fixture.authority,
                nowMs: now
            )
        }
        var outOfOrder = committed.operationReceipts
        outOfOrder.swapAt(0, 1)
        assertCandidateError(.authorityMismatch) {
            _ = try ProductionC1CandidateVerifier.deriveGrantEvidence(
                plan: fixture.plan,
                routeAuthorizations: fixture.authorizations,
                operationReceipts: outOfOrder,
                initiatorRole: .client,
                authority: fixture.authority,
                nowMs: now
            )
        }
        var duplicate = committed.operationReceipts
        duplicate[3] = duplicate[0]
        assertCandidateError(.requestConflict) {
            _ = try ProductionC1CandidateVerifier.deriveGrantEvidence(
                plan: fixture.plan,
                routeAuthorizations: fixture.authorizations,
                operationReceipts: duplicate,
                initiatorRole: .client,
                authority: fixture.authority,
                nowMs: now
            )
        }
        let otherChain = try commitAllOperations(fixture, initialRevision: 10)
        var wrongChain = committed.operationReceipts
        wrongChain[0] = otherChain.operationReceipts[0]
        assertCandidateError(.revisionMismatch) {
            _ = try ProductionC1CandidateVerifier.deriveGrantEvidence(
                plan: fixture.plan,
                routeAuthorizations: fixture.authorizations,
                operationReceipts: wrongChain,
                initiatorRole: .client,
                authority: fixture.authority,
                nowMs: now
            )
        }
        let grant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: committed.operationReceipts,
            initiatorRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        let bytes = try grant.evidence.canonicalBytes()
        let decoded = try ProductionC1P2PGrantEvidence(canonicalBytes: bytes)
        XCTAssertEqual(decoded, grant.evidence)
        XCTAssertEqual(decoded.operationCapabilityDigests.count, 4)
        XCTAssertEqual(decoded.operationReceiptDigests.count, 4)
        XCTAssertEqual(
            decoded.finalRouteAuthorizationDigest,
            digest(try fixture.authorizations.finalP2PDirect.canonicalBytes())
        )
        _ = try ProductionC1CandidateVerifier.verifyGrantEvidence(
            decoded,
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: committed.operationReceipts,
            localRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
    }

    func testP2PConnectorInputRejectsWrongSecret() throws {
        let fixture = try makeFixture()
        let committed = try commitAllOperations(fixture)
        let grant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: committed.operationReceipts,
            initiatorRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PConnectorInput(
                for: grant,
                localRole: .client,
                routeHandle: "direct-01",
                nonce: "nonce-01",
                secret: Data(repeating: 0x5b, count: 32),
                authority: fixture.authority,
                nowMs: now
            )
        }
    }

    func testSelectedCandidatesRequireSameAddressFamily() {
        assertCandidateError(.routeMismatch) {
            _ = try makeFixture(clientAddress: [
                0x26, 0x06, 0x47, 0x00, 0x47, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x11, 0x11,
            ])
        }
    }

    func testTranscriptCommitsExactObject26ForObject25ReadbackReceiptSet() throws {
        let fixture = try makeFixture()
        let firstReadback = try commitAllOperations(fixture)
        let secondReadback = try commitAllOperations(fixture, initialRevision: 10)
        let firstGrant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: firstReadback.operationReceipts,
            initiatorRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        let secondGrant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: secondReadback.operationReceipts,
            initiatorRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        XCTAssertEqual(
            firstGrant.evidence.finalRouteAuthorizationDigest,
            secondGrant.evidence.finalRouteAuthorizationDigest
        )
        XCTAssertNotEqual(
            try firstGrant.evidence.digestHex(),
            try secondGrant.evidence.digestHex()
        )
        XCTAssertNotEqual(
            firstGrant.grantAuthorization.digestHex,
            secondGrant.grantAuthorization.digestHex
        )
        let connectorInput = try ProductionC1CandidateVerifier.verifyP2PConnectorInput(
            for: secondGrant,
            localRole: .client,
            routeHandle: "direct-01",
            nonce: "nonce-01",
            secret: Data(repeating: 0x5a, count: 32),
            authority: fixture.authority,
            nowMs: now
        )
        let transcriptBoundToFirstGrant = try makeTranscript(
            fixture,
            routeAuthorizationDigest: firstGrant.grantAuthorization.digestHex
        )
        let confirmationKey = Data(repeating: 0x77, count: 32)
        let peerConfirmation = try ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            transcript: transcriptBoundToFirstGrant,
            grantAuthorization: secondGrant.grantAuthorization,
            confirmingRole: .runtime,
            key: confirmationKey
        )
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
                transcript: transcriptBoundToFirstGrant,
                verifiedGrant: secondGrant,
                connectorInput: connectorInput,
                localRole: .client,
                keyConfirmationKey: confirmationKey,
                presentedPeerKeyConfirmation: peerConfirmation,
                authority: fixture.authority,
                nowMs: now
            )
        }
    }

    func testEndpointAdmissionAtomicallyBindsObject25AndPairTombstone() throws {
        let fixture = try makeFixture()
        let committed = try commitAllOperations(fixture)
        let grant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: committed.operationReceipts,
            initiatorRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        let transcript = try makeTranscript(
            fixture,
            routeAuthorizationDigest: grant.grantAuthorization.digestHex
        )
        let connectorInput = try ProductionC1CandidateVerifier.verifyP2PConnectorInput(
            for: grant,
            localRole: .client,
            routeHandle: "direct-01",
            nonce: "nonce-01",
            secret: Data(repeating: 0x5a, count: 32),
            authority: fixture.authority,
            nowMs: now
        )
        let confirmationKey = Data(repeating: 0x77, count: 32)
        let runtimeConfirmation = try ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            transcript: transcript,
            grantAuthorization: grant.grantAuthorization,
            confirmingRole: .runtime,
            key: confirmationKey
        )
        let verifiedBinding = try ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
            transcript: transcript,
            verifiedGrant: grant,
            connectorInput: connectorInput,
            localRole: .client,
            keyConfirmationKey: confirmationKey,
            presentedPeerKeyConfirmation: runtimeConfirmation,
            authority: fixture.authority,
            nowMs: now
        )
        let initialPair = try ProductionPairStateSnapshot(
            authority: fixture.authority,
            localRevision: 1
        )
        let ledger = try ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest: fixture.authority.digestHex(),
            pairLocalRevision: initialPair.localRevision,
            remainingGrants: 1,
            retentionLimit: 8
        )
        let admissionId = String(repeating: "9", count: 64)
        let grantDigest = try grant.evidence.digestHex()
        let transcriptDigest = digest(transcript.canonicalBytes())
        let finalDigest = digest(try fixture.authorizations.finalP2PDirect.canonicalBytes())
        let grantAuthorizationDigest = grant.grantAuthorization.digestHex
        XCTAssertNotEqual(finalDigest, grantAuthorizationDigest)
        XCTAssertEqual(transcript.routeAuthDigest, grantAuthorizationDigest)
        let binding = try ProductionC1EndpointGrantAdmission.bindingDigest(
            admissionId: admissionId,
            routeGrantDigest: grantDigest,
            transcriptDigest: transcriptDigest,
            routeAuthorizationDigest: finalDigest,
            grantAuthorizationDigest: grantAuthorizationDigest,
            connectorInputCommitmentDigest: connectorInput.commitmentDigest
        )
        let substitutedRouteAuthorizationDigest = finalDigest
            == String(repeating: "a", count: 64)
            ? String(repeating: "b", count: 64)
            : String(repeating: "a", count: 64)
        let object4OnlySubstitutionBinding = try ProductionC1EndpointGrantAdmission
            .bindingDigest(
                admissionId: admissionId,
                routeGrantDigest: grantDigest,
                transcriptDigest: transcriptDigest,
                routeAuthorizationDigest: substitutedRouteAuthorizationDigest,
                grantAuthorizationDigest: grantAuthorizationDigest,
                connectorInputCommitmentDigest: connectorInput.commitmentDigest
            )
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1EndpointGrantAdmission.prepare(
                state: ledger,
                expectedRevision: ledger.revision,
                expectedSnapshotDigest: try ledger.snapshotDigestHex(),
                admissionId: admissionId,
                bindingDigest: object4OnlySubstitutionBinding,
                verifiedBinding: verifiedBinding,
                currentPairSnapshot: initialPair,
                nowMs: now
            )
        }
        let substitutedGrantAuthorizationDigest = grantAuthorizationDigest
            == String(repeating: "c", count: 64)
            ? String(repeating: "d", count: 64)
            : String(repeating: "c", count: 64)
        let object26OnlySubstitutionBinding = try ProductionC1EndpointGrantAdmission
            .bindingDigest(
                admissionId: admissionId,
                routeGrantDigest: grantDigest,
                transcriptDigest: transcriptDigest,
                routeAuthorizationDigest: finalDigest,
                grantAuthorizationDigest: substitutedGrantAuthorizationDigest,
                connectorInputCommitmentDigest: connectorInput.commitmentDigest
            )
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1EndpointGrantAdmission.prepare(
                state: ledger,
                expectedRevision: ledger.revision,
                expectedSnapshotDigest: try ledger.snapshotDigestHex(),
                admissionId: admissionId,
                bindingDigest: object26OnlySubstitutionBinding,
                verifiedBinding: verifiedBinding,
                currentPairSnapshot: initialPair,
                nowMs: now
            )
        }
        let preparation = try ProductionC1EndpointGrantAdmission.prepare(
            state: ledger,
            expectedRevision: ledger.revision,
            expectedSnapshotDigest: try ledger.snapshotDigestHex(),
            admissionId: admissionId,
            bindingDigest: binding,
            verifiedBinding: verifiedBinding,
            currentPairSnapshot: initialPair,
            nowMs: now
        )
        XCTAssertEqual(preparation.disposition, .applied)
        XCTAssertEqual(preparation.sessionID, transcript.sessionId)
        XCTAssertEqual(preparation.routeAuthorizationDigest, finalDigest)
        XCTAssertEqual(preparation.grantAuthorizationDigest, grantAuthorizationDigest)
        XCTAssertEqual(preparation.entry.routeAuthorizationDigest, finalDigest)
        XCTAssertEqual(
            preparation.entry.grantAuthorizationDigest,
            grantAuthorizationDigest
        )
        XCTAssertEqual(preparation.pairAuthorityDigest, try fixture.authority.digestHex())
        XCTAssertEqual(preparation.effectiveNotBeforeMs, grant.evidence.effectiveNotBeforeMs)
        XCTAssertEqual(preparation.expiresAtMs, grant.evidence.expiresAtMs)
        XCTAssertEqual(preparation.nextState.remainingGrants, 0)
        XCTAssertEqual(preparation.nextPairSnapshot.localRevision, 2)
        XCTAssertEqual(preparation.nextPairSnapshot.consumedEntries.count, 1)
        XCTAssertEqual(
            preparation.entry.pairSnapshotDigest,
            try preparation.nextPairSnapshot.digestHex()
        )
        _ = try ReadbackConfirmedProductionC1EndpointGrantAdmission.confirm(
            preparation,
            committedCompoundReadback: preparation.nextCompoundRecord
        )

        let retry = try ProductionC1EndpointGrantAdmission.prepare(
            state: preparation.nextState,
            expectedRevision: 999,
            expectedSnapshotDigest: String(repeating: "f", count: 64),
            admissionId: admissionId,
            bindingDigest: binding,
            verifiedBinding: verifiedBinding,
            currentPairSnapshot: preparation.nextPairSnapshot,
            nowMs: fixture.plan.expiresAtMs
        )
        XCTAssertEqual(retry.disposition, .idempotent)
        XCTAssertEqual(retry.sessionID, preparation.sessionID)
        XCTAssertEqual(retry.routeAuthorizationDigest, preparation.routeAuthorizationDigest)
        XCTAssertEqual(
            retry.grantAuthorizationDigest,
            preparation.grantAuthorizationDigest
        )
        XCTAssertEqual(retry.pairAuthorityDigest, preparation.pairAuthorityDigest)
        XCTAssertEqual(retry.effectiveNotBeforeMs, grant.evidence.effectiveNotBeforeMs)
        XCTAssertEqual(retry.expiresAtMs, grant.evidence.expiresAtMs)
        _ = try ReadbackConfirmedProductionC1EndpointGrantAdmission.confirm(
            retry,
            committedCompoundReadback: retry.nextCompoundRecord
        )
        let reloadRetry = try ProductionC1EndpointGrantAdmission.prepareCommittedRetry(
            state: preparation.nextState,
            admissionId: admissionId,
            bindingDigest: binding,
            grantEvidenceCanonicalBytes: grant.evidence.canonicalBytes(),
            routeAuthorization: fixture.authorizations.finalP2PDirect,
            transcriptCanonicalBytes: transcript.canonicalBytes(),
            connectorInputCommitmentDigest: connectorInput.commitmentDigest,
            currentPairSnapshot: preparation.nextPairSnapshot
        )
        XCTAssertEqual(reloadRetry.disposition, .idempotent)
        XCTAssertEqual(reloadRetry.sessionID, preparation.sessionID)
        XCTAssertEqual(
            reloadRetry.routeAuthorizationDigest,
            preparation.routeAuthorizationDigest
        )
        XCTAssertEqual(
            reloadRetry.grantAuthorizationDigest,
            preparation.grantAuthorizationDigest
        )
        XCTAssertEqual(reloadRetry.pairAuthorityDigest, preparation.pairAuthorityDigest)
        XCTAssertEqual(reloadRetry.effectiveNotBeforeMs, grant.evidence.effectiveNotBeforeMs)
        XCTAssertEqual(reloadRetry.expiresAtMs, grant.evidence.expiresAtMs)
        _ = try ReadbackConfirmedProductionC1EndpointGrantAdmission.confirm(
            reloadRetry,
            committedCompoundReadback: reloadRetry.nextCompoundRecord
        )

        let legacyBoundTranscript = try makeTranscript(
            fixture,
            routeAuthorizationDigest: finalDigest
        )
        let legacyConfirmation = try ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            transcript: legacyBoundTranscript,
            grantAuthorization: grant.grantAuthorization,
            confirmingRole: .runtime,
            key: confirmationKey
        )
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
                transcript: legacyBoundTranscript,
                verifiedGrant: grant,
                connectorInput: connectorInput,
                localRole: .client,
                keyConfirmationKey: confirmationKey,
                presentedPeerKeyConfirmation: legacyConfirmation,
                authority: fixture.authority,
                nowMs: now
            )
        }
    }

    func testTrustedDeviceExactBoundDurableValidatorHappyStaleAndExpiry()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let liveClock = ExactBoundDurableClock(now)
        let live = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: liveClock,
            suffix: "live"
        )

        let validated = try await live.store.validateProductionC1ExactBoundStart(
            live.request
        )
        XCTAssertEqual(validated.markerDigest, live.token.markerDigest)
        XCTAssertEqual(validated.ledgerRevision, live.token.ledgerRevision)

        let secondPreparation = try syntheticNextEndpointPreparation(
            currentLedger: live.firstPreparation.nextState,
            currentPair: live.firstPreparation.nextPairSnapshot,
            effectiveNotBeforeMs: live.token.effectiveNotBeforeMs,
            expiresAtMs: live.token.expiresAtMs
        )
        _ = try await live.store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: live.device.id,
            expectedPublicKeyBase64: live.device.publicKeyBase64,
            preparation: secondPreparation
        )
        do {
            _ = try await live.store.validateProductionC1ExactBoundStart(live.request)
            XCTFail("Expected a non-last durable marker to be stale for start")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartValidationError,
                .staleCommit
            )
        }

        let expiryClock = ExactBoundDurableClock(now)
        let expiring = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: expiryClock,
            suffix: "expiry"
        )
        expiryClock.set(expiring.token.expiresAtMs)
        do {
            _ = try await expiring.store.validateProductionC1ExactBoundStart(
                expiring.request
            )
            XCTFail("Expected the exact expiry upper bound to fail closed")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartValidationError,
                .expired
            )
        }
    }

    func testExactBoundSecureSessionExchangesRecordsAndCloseIsIdempotent()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: clock,
            suffix: "crypto-happy"
        )
        let runtimeBinding = try makeKeyScheduleBinding(
            fixture: fixture,
            endpointBinding: binding,
            role: .runtime
        )
        let clientBinding = try makeKeyScheduleBinding(
            fixture: fixture,
            endpointBinding: binding,
            role: .client
        )
        let coordinator = await durable.store.productionC1ExactBoundStartCoordinator()
        let session = try await ProductionC1ExactBoundSecureSession.start(
            coordinator: coordinator,
            request: durable.request,
            localEphemeralKey: try agreementKey(21),
            nowMs: { clock.get() }
        )
        XCTAssertEqual(binding.runtimeKeyScheduleBinding, runtimeBinding)
        XCTAssertEqual(binding.runtimeKeyScheduleBinding.localRole, .runtime)
        let clientHandshake = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: clientBinding,
            localEphemeralKey: try agreementKey(20),
            nowMs: clock.get()
        )

        do {
            _ = try await durable.store.applyVerifiedProductionPairTransition(
                deviceID: durable.device.id,
                expectedPublicKeyBase64: durable.device.publicKeyBase64,
                transition: ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest: String(repeating: "0", count: 64),
                    nextAuthority: try advancedAuthority(from: fixture.authority)
                )
            )
            XCTFail("Expected the stale authority mutation to fail")
        } catch {
            // The write permit must be released so the old authority remains usable.
        }

        let runtimeConfirmation = try await session.localConfirmation()
        let clientConfirmation = try clientHandshake.localConfirmation(nowMs: clock.get())
        try await session.markLocalConfirmationSent(runtimeConfirmation)
        try clientHandshake.markLocalConfirmationSent(
            clientConfirmation,
            nowMs: clock.get()
        )
        try await session.acceptPeerConfirmation(clientConfirmation)
        try clientHandshake.acceptPeerConfirmation(
            runtimeConfirmation,
            nowMs: clock.get()
        )
        try await session.activate()
        let clientCipher = try clientHandshake.makeCipher(nowMs: clock.get())

        let outbound = try await session.sealApplication(Data("runtime".utf8))
        let outboundCopy = outbound
        XCTAssertEqual(outboundCopy, outbound)
        XCTAssertEqual(
            try ProductionSecureSessionEncryptedRecord(
                canonicalBytes: outbound.record.canonicalBytes()
            ),
            outbound.record
        )
        XCTAssertEqual(
            try clientCipher.open(outbound.record, nowMs: clock.get()).plaintext,
            Data("runtime".utf8)
        )
        let inbound = try clientCipher.sealApplication(
            Data("client".utf8),
            nowMs: clock.get()
        )
        let openedInbound = try await session.open(inbound.record)
        let openedInboundCopy = openedInbound
        XCTAssertEqual(openedInboundCopy, openedInbound)
        XCTAssertEqual(openedInbound.plaintext, Data("client".utf8))

        await session.close()
        await session.close()
        do {
            _ = try await session.sealApplication(Data())
            XCTFail("Expected a locally closed lease to reject further results")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .invalidLease
            )
        }
        let closeReasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(closeReasons, [.completed])
    }

    func testTransportFacadeDescriptorAndConfirmationPublicationHoldExactAuthority()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: clock,
            suffix: "transport-confirmation"
        )
        let coordinator = await durable.store.productionC1ExactBoundStartCoordinator()
        let localEphemeralKey = try agreementKey(21)
        let session = try await durable.store.beginProductionC1TransportSecureSession(
            deviceID: durable.device.id,
            expectedPublicKeyBase64: durable.device.publicKeyBase64,
            token: durable.token,
            verifiedBinding: binding,
            localEphemeralKey: localEphemeralKey
        )
        XCTAssertFalse(localEphemeralKey.testOnlyRetainsPrivateKey)
        XCTAssertTrue(localEphemeralKey.testOnlyIsConsumed)
        XCTAssertEqual(session.descriptor.sessionID, durable.token.sessionID)
        XCTAssertEqual(session.descriptor.expiresAtMs, durable.token.expiresAtMs)
        XCTAssertEqual(session.descriptor.bindingDigest.count, 64)
        XCTAssertTrue(session.descriptor.bindingDigest.allSatisfy {
            $0.isNumber || ("a"..."f").contains(String($0))
        })
        XCTAssertEqual(
            session.descriptor.bindingDigest,
            try ProductionSecureSessionCrypto.exactBindingDigestHex(
                binding.runtimeKeyScheduleBinding
            )
        )
        XCTAssertNotEqual(
            session.descriptor.bindingDigest,
            durable.token.bindingDigest
        )

        let attachmentRightCount = await withTaskGroup(of: Bool.self) { group in
            for _ in 0..<32 {
                group.addTask {
                    session.issueTransportAttachmentRight() != nil
                }
            }
            var count = 0
            for await issued in group where issued { count += 1 }
            return count
        }
        XCTAssertEqual(attachmentRightCount, 1)
        XCTAssertNil(session.issueTransportAttachmentRight())

        let sendGate = ExactBoundSecureSessionGate()
        let sentConfirmation = ExactBoundSecureSessionRetainedValue<Data>()
        let terminalCount = ExactBoundSecureSessionCounter()
        XCTAssertTrue(session.installTerminalObserver { terminalCount.increment() })
        XCTAssertFalse(session.installTerminalObserver {})
        let sendTask = Task {
            try await session.sendLocalConfirmation { bytes in
                sentConfirmation.store(bytes)
                await sendGate.suspend()
            }
        }
        await sendGate.waitUntilEntered()
        let transitionTask = Task {
            try await durable.store.applyVerifiedProductionPairTransition(
                deviceID: durable.device.id,
                expectedPublicKeyBase64: durable.device.publicKeyBase64,
                transition: ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest: durable.token.pairAuthorityDigest,
                    nextAuthority: try advancedAuthority(from: fixture.authority)
                )
            )
        }
        while await coordinator.waitingPublicationWriterCountForTesting() == 0 {
            await Task.yield()
        }
        XCTAssertEqual(terminalCount.get(), 0)
        await sendGate.release()
        try await sendTask.value
        _ = try await transitionTask.value
        XCTAssertFalse(sentConfirmation.get()?.isEmpty ?? true)
        XCTAssertEqual(terminalCount.get(), 1)
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.authorityAdvanced])
    }

    func testTransportStoreHandoffClosesEphemeralKeyOnAdmissionFailure()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: clock,
            suffix: "transport-key-handoff-failure"
        )
        let localEphemeralKey = try agreementKey(21)

        do {
            _ = try await durable.store.beginProductionC1TransportSecureSession(
                deviceID: "missing-device",
                expectedPublicKeyBase64: durable.device.publicKeyBase64,
                token: durable.token,
                verifiedBinding: binding,
                localEphemeralKey: localEphemeralKey
            )
            XCTFail("Expected durable admission failure")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .trustedDeviceNotFound
            )
        }

        XCTAssertFalse(localEphemeralKey.testOnlyRetainsPrivateKey)
        XCTAssertTrue(localEphemeralKey.testOnlyIsClosed)
        let runtimeBinding = try makeKeyScheduleBinding(
            fixture: fixture,
            endpointBinding: binding,
            role: .runtime
        )
        XCTAssertThrowsError(
            try ProductionSecureSessionCrypto.deriveHandshake(
                binding: runtimeBinding,
                localEphemeralKey: localEphemeralKey,
                nowMs: clock.get()
            )
        ) {
            XCTAssertEqual(
                $0 as? ProductionSecureSessionCryptoError,
                .ephemeralKeyClosed
            )
        }
    }

    func testTransportFacadeSendFailureIsTerminalAndNotifiesOnce()
        async throws
    {
        let transport = try await makeActiveTransportFixture(
            suffix: "transport-send-failure"
        )
        let terminalCount = ExactBoundSecureSessionCounter()
        XCTAssertTrue(transport.session.installTerminalObserver {
            terminalCount.increment()
        })
        do {
            _ = try await transport.session.sealApplicationAndSend(
                Data("not-delivered".utf8)
            ) { _ in
                throw ExactBoundTransportTestError.publicationFailed
            }
            XCTFail("Expected the transport send failure to terminalize")
        } catch {
            XCTAssertEqual(
                error as? ExactBoundTransportTestError,
                .publicationFailed
            )
        }
        XCTAssertEqual(terminalCount.get(), 1)
        do {
            _ = try await transport.session.sealApplicationAndSend(Data()) { _ in }
            XCTFail("Expected a failed send to reject later records")
        } catch {
            XCTAssertNotNil(error as? ProductionC1ExactBoundSecureSessionError)
        }
        await transport.session.close()
        XCTAssertEqual(terminalCount.get(), 1)
        let reasons = await transport.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.cancelled])
    }

    func testTransportFacadeOpenPublicationFailureIsTerminal()
        async throws
    {
        let transport = try await makeActiveTransportFixture(
            suffix: "transport-open-failure"
        )
        let inbound = try transport.clientCipher.sealApplication(
            Data("not-published".utf8),
            nowMs: transport.clock.get()
        )
        let terminalCount = ExactBoundSecureSessionCounter()
        XCTAssertTrue(transport.session.installTerminalObserver {
            terminalCount.increment()
        })
        do {
            let _: ProductionC1TransportOpenPublication<Int> = try await transport
                .session.openAndPublish(inbound.record.canonicalBytes()) { _ in
                    throw ExactBoundTransportTestError.publicationFailed
                }
            XCTFail("Expected the application publisher failure to terminalize")
        } catch {
            XCTAssertEqual(
                error as? ExactBoundTransportTestError,
                .publicationFailed
            )
        }
        XCTAssertEqual(terminalCount.get(), 1)
        let reasons = await transport.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.cancelled])
    }

    func testTransportFacadeCancellationIsTerminal()
        async throws
    {
        let transport = try await makeActiveTransportFixture(
            suffix: "transport-cancellation"
        )
        let sendGate = ExactBoundSecureSessionGate()
        let terminalCount = ExactBoundSecureSessionCounter()
        XCTAssertTrue(transport.session.installTerminalObserver {
            terminalCount.increment()
        })
        let sendTask = Task {
            try await transport.session.sealApplicationAndSend(
                Data("cancelled-send".utf8)
            ) { _ in
                await sendGate.suspend()
                try Task.checkCancellation()
            }
        }
        await sendGate.waitUntilEntered()
        sendTask.cancel()
        await sendGate.release()
        do {
            _ = try await sendTask.value
            XCTFail("Expected cancellation after sequence consumption")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }
        XCTAssertEqual(terminalCount.get(), 1)
        let reasons = await transport.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.cancelled])
    }

    func testTransportTerminalFailureDoesNotFinishCloseBeforeOtherSendDrains()
        async throws
    {
        let transport = try await makeActiveTransportFixture(
            suffix: "transport-terminal-drain"
        )
        let failingGate = ExactBoundSecureSessionGate()
        let otherGate = ExactBoundSecureSessionGate()
        let closeFinished = ExactBoundSecureSessionSignal()
        let failing = Task {
            try await transport.session.sealApplicationAndSend(
                Data("failing".utf8)
            ) { _ in
                await failingGate.suspend()
                throw ExactBoundTransportTestError.publicationFailed
            }
        }
        await failingGate.waitUntilEntered()
        let other = Task {
            try await transport.session.sealApplicationAndSend(
                Data("other".utf8)
            ) { _ in
                await otherGate.suspend()
            }
        }
        await otherGate.waitUntilEntered()
        let closeTask = Task {
            await transport.session.close()
            await closeFinished.mark()
        }
        await failingGate.release()
        do {
            _ = try await failing.value
            XCTFail("Expected the first publication to fail")
        } catch {
            XCTAssertEqual(
                error as? ExactBoundTransportTestError,
                .publicationFailed
            )
        }
        let didFinishEarly = await closeFinished.isMarked()
        XCTAssertFalse(didFinishEarly)
        await otherGate.release()
        do {
            _ = try await other.value
            XCTFail("Expected the concurrent publication to observe termination")
        } catch {
            XCTAssertTrue(
                error is ProductionC1ExactBoundSecureSessionError
                    || error is ProductionC1ExactBoundStartCoordinatorError
            )
        }
        await closeTask.value
        let didFinish = await closeFinished.isMarked()
        XCTAssertTrue(didFinish)
    }

    func testTransportFacadeOpenPublishesBeforeAuthorityFence()
        async throws
    {
        let transport = try await makeActiveTransportFixture(
            suffix: "transport-open-publication"
        )
        let inbound = try transport.clientCipher.sealApplication(
            Data("publish-before-fence".utf8),
            nowMs: transport.clock.get()
        )
        let publishGate = ExactBoundSecureSessionGate()
        let published = ExactBoundSecureSessionRetainedValue<Data>()
        let openTask = Task {
            try await transport.session.openAndPublish(
                inbound.record.canonicalBytes()
            ) { plaintext in
                published.store(plaintext)
                await publishGate.suspend()
                return plaintext.count
            }
        }
        await publishGate.waitUntilEntered()
        let transitionTask = Task {
            try await transport.store.applyVerifiedProductionPairTransition(
                deviceID: transport.device.id,
                expectedPublicKeyBase64: transport.device.publicKeyBase64,
                transition: ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest: transport.token.pairAuthorityDigest,
                    nextAuthority: transport.nextAuthority
                )
            )
        }
        while await transport.coordinator
            .waitingPublicationWriterCountForTesting() == 0 {
            await Task.yield()
        }
        await publishGate.release()
        let publication = try await openTask.value
        guard case let .application(count, _, _) = publication else {
            return XCTFail("Expected an application publication")
        }
        XCTAssertEqual(count, Data("publish-before-fence".utf8).count)
        XCTAssertEqual(published.get(), Data("publish-before-fence".utf8))
        _ = try await transitionTask.value
        let reasons = await transport.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.authorityAdvanced])
    }

    func testTransportFacadeCloseDrainsAllConcurrentAtomicSends()
        async throws
    {
        let transport = try await makeActiveTransportFixture(
            suffix: "transport-close-drain"
        )
        let firstGate = ExactBoundSecureSessionGate()
        let secondGate = ExactBoundSecureSessionGate()
        let terminalCount = ExactBoundSecureSessionCounter()
        XCTAssertTrue(transport.session.installTerminalObserver {
            terminalCount.increment()
        })
        let first = Task {
            try await transport.session.sealApplicationAndSend(
                Data("first".utf8)
            ) { _ in
                await firstGate.suspend()
            }
        }
        await firstGate.waitUntilEntered()
        let second = Task {
            try await transport.session.sealApplicationAndSend(
                Data("second".utf8)
            ) { _ in
                await secondGate.suspend()
            }
        }
        await secondGate.waitUntilEntered()
        let closeTask = Task { await transport.session.close() }
        await Task.yield()
        XCTAssertEqual(terminalCount.get(), 0)

        await firstGate.release()
        _ = try await first.value
        XCTAssertEqual(terminalCount.get(), 0)
        await secondGate.release()
        _ = try await second.value
        await closeTask.value
        XCTAssertEqual(terminalCount.get(), 1)
        let reasons = await transport.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.completed])
    }

    func testExactBoundSecureSessionRejectsDifferentVerifierBindingBeforeECDH()
        async throws
    {
        let durableFixture = try makeFixture()
        let durableBinding = try makeVerifiedEndpointBinding(durableFixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: durableFixture,
            binding: durableBinding,
            clock: clock,
            suffix: "crypto-mismatch"
        )
        let otherFixture = try makeFixture(clientAddress: [9, 9, 9, 9])
        let otherBinding = try makeVerifiedEndpointBinding(otherFixture)
        let mismatched = try makeKeyScheduleBinding(
            fixture: otherFixture,
            endpointBinding: otherBinding,
            role: .runtime
        )
        let key = try agreementKey(21)
        let coordinator = await durable.store.productionC1ExactBoundStartCoordinator()

        do {
            _ = try await ProductionC1ExactBoundSecureSession.startForTesting(
                coordinator: coordinator,
                request: durable.request,
                localEphemeralKey: key,
                nowMs: { clock.get() },
                keyScheduleBindingOverride: mismatched
            )
            XCTFail("Expected an exact object-7/object-26 mismatch")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundSecureSessionError,
                .exactBindingMismatch
            )
        }
        XCTAssertTrue(key.testOnlyRetainsPrivateKey)
        let liveCount = await coordinator.liveCountForTesting()
        XCTAssertEqual(liveCount, 0)

        let clientOnly = try makeKeyScheduleBinding(
            fixture: durableFixture,
            endpointBinding: durableBinding,
            role: .client
        )
        let clientKey = try agreementKey(20)
        do {
            _ = try await ProductionC1ExactBoundSecureSession.startForTesting(
                coordinator: coordinator,
                request: durable.request,
                localEphemeralKey: clientKey,
                nowMs: { clock.get() },
                keyScheduleBindingOverride: clientOnly
            )
            XCTFail("Expected the macOS runtime wrapper to reject a client role")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundSecureSessionError,
                .exactBindingMismatch
            )
        }
        XCTAssertTrue(clientKey.testOnlyRetainsPrivateKey)
    }

    func testExactBoundSecureSessionRevocationFencesLateHandshakePublication()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: clock,
            suffix: "crypto-late-publish"
        )
        let coordinator = await durable.store.productionC1ExactBoundStartCoordinator()
        let publicationGate = ExactBoundSecureSessionGate()
        let abortSignal = ExactBoundSecureSessionSignal()
        let startTask = Task {
            try await ProductionC1ExactBoundSecureSession.startForTesting(
                coordinator: coordinator,
                request: durable.request,
                localEphemeralKey: try agreementKey(21),
                nowMs: { clock.get() },
                afterDeriveBeforeInstall: { await publicationGate.suspend() },
                afterAbort: { await abortSignal.mark() }
            )
        }
        await publicationGate.waitUntilEntered()
        let revokeTask = Task {
            await coordinator.fenceRevoked(
                pairAuthorityDigest: durable.token.pairAuthorityDigest
            )
        }
        await abortSignal.waitUntilMarked()
        await publicationGate.release()
        await revokeTask.value
        do {
            _ = try await startTask.value
            XCTFail("Expected late handshake publication to stay fenced")
        } catch {
            XCTAssertNotNil(error as? ProductionC1ExactBoundSecureSessionError)
        }
        let revokeReasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(revokeReasons, [.revoked])
    }

    func testExactBoundSecureSessionAuthorityAdvanceExpiryAndPostFenceDiscard()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)

        let raceClock = ExactBoundDurableClock(now)
        let race = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: raceClock,
            suffix: "crypto-post-fence"
        )
        let raceCoordinator = await race.store.productionC1ExactBoundStartCoordinator()
        let resultGate = ExactBoundSecureSessionGate()
        let raceSession = try await ProductionC1ExactBoundSecureSession.startForTesting(
            coordinator: raceCoordinator,
            request: race.request,
            localEphemeralKey: try agreementKey(21),
            nowMs: { raceClock.get() },
            beforePostFence: { await resultGate.suspend() }
        )
        let resultTask = Task { try await raceSession.localConfirmation() }
        await resultGate.waitUntilEntered()
        let advancedAuthority = try advancedAuthority(from: fixture.authority)
        let transitionTask = Task {
            try await race.store.applyVerifiedProductionPairTransition(
                deviceID: race.device.id,
                expectedPublicKeyBase64: race.device.publicKeyBase64,
                transition: ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest: race.token.pairAuthorityDigest,
                    nextAuthority: advancedAuthority
                )
            )
        }
        while await raceCoordinator.waitingPublicationWriterCountForTesting() == 0 {
            await Task.yield()
        }
        await resultGate.release()
        let preCommitResult = try await resultTask.value
        XCTAssertFalse(preCommitResult.isEmpty)
        _ = try await transitionTask.value
        do {
            _ = try await raceSession.localConfirmation()
            XCTFail("Expected the committed authority advance to fence later results")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .invalidLease
            )
        }
        await raceSession.close()
        let advanceReasons = await raceCoordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(advanceReasons, [.authorityAdvanced])

        let expiryClock = ExactBoundDurableClock(now)
        let expiring = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: expiryClock,
            suffix: "crypto-expiry"
        )
        let expiryCoordinator = await expiring.store
            .productionC1ExactBoundStartCoordinator()
        let expirySession = try await ProductionC1ExactBoundSecureSession.start(
            coordinator: expiryCoordinator,
            request: expiring.request,
            localEphemeralKey: try agreementKey(21),
            nowMs: { expiryClock.get() }
        )
        expiryClock.set(expiring.token.expiresAtMs)
        do {
            _ = try await expirySession.localConfirmation()
            XCTFail("Expected exact upper-bound expiry to terminate crypto")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .expired
            )
        }
        do {
            _ = try await expirySession.localConfirmation()
            XCTFail("Expected expiry termination to remain terminal")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .invalidLease
            )
        }
        let expiryReasons = await expiryCoordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(expiryReasons, [.expired])
    }

    func testExactBoundSecureSessionCloseDiscardsConcurrentSealBeforeComplete()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: clock,
            suffix: "crypto-close-race"
        )
        let coordinator = await durable.store.productionC1ExactBoundStartCoordinator()
        let resultGate = ExactBoundSecureSessionArmedGate()
        let closeGate = ExactBoundSecureSessionGate()
        let retainedSeal = ExactBoundSecureSessionRetainedValue<
            ProductionSecureSessionSealResult
        >()
        let session = try await ProductionC1ExactBoundSecureSession.startForTesting(
            coordinator: coordinator,
            request: durable.request,
            localEphemeralKey: try agreementKey(21),
            nowMs: { clock.get() },
            beforePostFence: { await resultGate.suspendIfArmed() },
            afterCloseInvalidateBeforeComplete: { await closeGate.suspend() },
            observeSealResult: { retainedSeal.store($0) }
        )
        let clientBinding = try makeKeyScheduleBinding(
            fixture: fixture,
            endpointBinding: binding,
            role: .client
        )
        let clientHandshake = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: clientBinding,
            localEphemeralKey: try agreementKey(20),
            nowMs: clock.get()
        )
        let runtimeConfirmation = try await session.localConfirmation()
        let clientConfirmation = try clientHandshake.localConfirmation(nowMs: clock.get())
        try await session.markLocalConfirmationSent(runtimeConfirmation)
        try clientHandshake.markLocalConfirmationSent(
            clientConfirmation,
            nowMs: clock.get()
        )
        try await session.acceptPeerConfirmation(clientConfirmation)
        try clientHandshake.acceptPeerConfirmation(
            runtimeConfirmation,
            nowMs: clock.get()
        )
        try await session.activate()

        await resultGate.arm()
        let sealTask = Task {
            try await session.sealApplication(Data("discard-me".utf8))
        }
        await resultGate.waitUntilEntered()
        let producedSeal = try XCTUnwrap(retainedSeal.get())
        XCTAssertTrue(producedSeal.record.ciphertext.contains { $0 != 0 })
        XCTAssertTrue(producedSeal.record.tag.contains { $0 != 0 })
        let closeTask = Task { await session.close() }
        await closeGate.waitUntilEntered()
        await resultGate.release()
        do {
            _ = try await sealTask.value
            XCTFail("Expected close-invalidated seal output to be discarded")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundSecureSessionError,
                .fenced
            )
        }
        // `producedSeal` is a value copy retained before discard. Observing
        // zeros through that copy proves the backing allocation was wiped;
        // resetting a later Data value through COW would leave this nonzero.
        XCTAssertEqual(
            producedSeal.record.ciphertext,
            Data(repeating: 0, count: producedSeal.record.ciphertext.count)
        )
        XCTAssertEqual(
            producedSeal.record.tag,
            Data(repeating: 0, count: producedSeal.record.tag.count)
        )
        await closeGate.release()
        await closeTask.value
        let closeReasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(closeReasons, [.completed])
    }

    func testExactBoundSecureSessionPostFenceWipesRetainedConfirmationStorage()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: clock,
            suffix: "crypto-confirmation-discard"
        )
        let coordinator = await durable.store.productionC1ExactBoundStartCoordinator()
        let resultGate = ExactBoundSecureSessionGate()
        let retainedConfirmation = ExactBoundSecureSessionRetainedValue<
            ProductionC1SensitiveResultTestingProbe
        >()
        let session = try await ProductionC1ExactBoundSecureSession.startForTesting(
            coordinator: coordinator,
            request: durable.request,
            localEphemeralKey: try agreementKey(21),
            nowMs: { clock.get() },
            beforePostFence: { await resultGate.suspend() },
            observeLocalConfirmationResult: { retainedConfirmation.store($0) }
        )

        let confirmationTask = Task { try await session.localConfirmation() }
        await resultGate.waitUntilEntered()
        let producedConfirmation = try XCTUnwrap(retainedConfirmation.get())
        let confirmationBeforeDiscard = producedConfirmation.snapshot()
        XCTAssertFalse(confirmationBeforeDiscard.isEmpty)
        XCTAssertTrue(confirmationBeforeDiscard.contains { $0 != 0 })

        await session.close()
        await resultGate.release()
        do {
            _ = try await confirmationTask.value
            XCTFail("Expected locally closed confirmation output to be suppressed")
        } catch {
            XCTAssertTrue(
                error is ProductionC1ExactBoundStartCoordinatorError
                    || error is ProductionC1ExactBoundSecureSessionError
            )
        }
        XCTAssertEqual(
            producedConfirmation.snapshot(),
            Data(repeating: 0, count: confirmationBeforeDiscard.count)
        )
    }

    func testExactBoundSecureSessionPostFenceWipesRetainedOpenStorage()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: clock,
            suffix: "crypto-open-discard"
        )
        let coordinator = await durable.store.productionC1ExactBoundStartCoordinator()
        let resultGate = ExactBoundSecureSessionArmedGate()
        let retainedOpen = ExactBoundSecureSessionRetainedValue<
            ProductionSecureSessionOpenResult
        >()
        let session = try await ProductionC1ExactBoundSecureSession.startForTesting(
            coordinator: coordinator,
            request: durable.request,
            localEphemeralKey: try agreementKey(21),
            nowMs: { clock.get() },
            beforePostFence: { await resultGate.suspendIfArmed() },
            observeOpenResult: { retainedOpen.store($0) }
        )
        let clientHandshake = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: try makeKeyScheduleBinding(
                fixture: fixture,
                endpointBinding: binding,
                role: .client
            ),
            localEphemeralKey: try agreementKey(20),
            nowMs: clock.get()
        )
        let runtimeConfirmation = try await session.localConfirmation()
        let clientConfirmation = try clientHandshake.localConfirmation(nowMs: clock.get())
        try await session.markLocalConfirmationSent(runtimeConfirmation)
        try clientHandshake.markLocalConfirmationSent(
            clientConfirmation,
            nowMs: clock.get()
        )
        try await session.acceptPeerConfirmation(clientConfirmation)
        try clientHandshake.acceptPeerConfirmation(
            runtimeConfirmation,
            nowMs: clock.get()
        )
        try await session.activate()
        let clientCipher = try clientHandshake.makeCipher(nowMs: clock.get())
        let expectedPlaintext = Data("discard-open-plaintext".utf8)
        let inbound = try clientCipher.sealApplication(
            expectedPlaintext,
            nowMs: clock.get()
        )

        await resultGate.arm()
        let openTask = Task { try await session.open(inbound.record) }
        await resultGate.waitUntilEntered()
        let producedOpen = try XCTUnwrap(retainedOpen.get())
        XCTAssertEqual(producedOpen.plaintext, expectedPlaintext)

        await session.close()
        await resultGate.release()
        do {
            _ = try await openTask.value
            XCTFail("Expected locally closed plaintext output to be suppressed")
        } catch {
            XCTAssertTrue(
                error is ProductionC1ExactBoundStartCoordinatorError
                    || error is ProductionC1ExactBoundSecureSessionError
            )
        }
        XCTAssertEqual(
            producedOpen.plaintext,
            Data(repeating: 0, count: expectedPlaintext.count)
        )
    }

    func testAuthorityCommitWaitsForInFlightSealThenFencesLaterResults()
        async throws
    {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: clock,
            suffix: "crypto-commit-seal"
        )
        let coordinator = await durable.store.productionC1ExactBoundStartCoordinator()
        let sealGate = ExactBoundSecureSessionArmedGate()
        let session = try await ProductionC1ExactBoundSecureSession.startForTesting(
            coordinator: coordinator,
            request: durable.request,
            localEphemeralKey: try agreementKey(21),
            nowMs: { clock.get() },
            beforePostFence: { await sealGate.suspendIfArmed() }
        )
        let clientHandshake = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: try makeKeyScheduleBinding(
                fixture: fixture,
                endpointBinding: binding,
                role: .client
            ),
            localEphemeralKey: try agreementKey(20),
            nowMs: clock.get()
        )
        let runtimeConfirmation = try await session.localConfirmation()
        let clientConfirmation = try clientHandshake.localConfirmation(nowMs: clock.get())
        try await session.markLocalConfirmationSent(runtimeConfirmation)
        try clientHandshake.markLocalConfirmationSent(
            clientConfirmation,
            nowMs: clock.get()
        )
        try await session.acceptPeerConfirmation(clientConfirmation)
        try clientHandshake.acceptPeerConfirmation(
            runtimeConfirmation,
            nowMs: clock.get()
        )
        try await session.activate()

        await sealGate.arm()
        let sealTask = Task {
            try await session.sealApplication(Data("before-commit".utf8))
        }
        await sealGate.waitUntilEntered()
        let advanced = try advancedAuthority(from: fixture.authority)
        let transitionTask = Task {
            try await durable.store.applyVerifiedProductionPairTransition(
                deviceID: durable.device.id,
                expectedPublicKeyBase64: durable.device.publicKeyBase64,
                transition: ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest: durable.token.pairAuthorityDigest,
                    nextAuthority: advanced
                )
            )
        }
        while await coordinator.waitingPublicationWriterCountForTesting() == 0 {
            await Task.yield()
        }
        await sealGate.release()
        let preCommitSeal = try await sealTask.value
        XCTAssertFalse(preCommitSeal.record.ciphertext.isEmpty)
        _ = try await transitionTask.value
        do {
            _ = try await session.sealApplication(Data("after-commit".utf8))
            XCTFail("Expected no old-authority record after durable commit")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .invalidLease
            )
        }
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.authorityAdvanced])
    }

    func testObject27RejectsWrongLongTermKeyRoleContextAndProofIdFrontRun() throws {
        let fixture = try makeFixture()
        let value = fixture.bilateral.clientPublish
        let proof = value.endpointOperationProof
        XCTAssertEqual(
            try ProductionC1EndpointOperationProof(canonicalBytes: proof.canonicalBytes()),
            proof
        )

        assertCandidateError(.roleMismatch) {
            _ = try ProductionC1EndpointOperationProof.signed(
                requesterRole: .client,
                operation: .publish,
                candidateOwnerRole: .client,
                proofId: proof.proofId,
                attemptId: proof.attemptId,
                capabilityId: proof.capabilityId,
                candidateBatch: fixture.clientBatch,
                singleUseNonce: proof.singleUseNonce,
                securityContext: fixture.securityContext,
                serviceAudienceId: serviceId,
                authority: fixture.authority,
                issuedAtMs: proof.issuedAtMs,
                notBeforeMs: proof.notBeforeMs,
                expiresAtMs: proof.expiresAtMs,
                using: fixture.runtimeIdentityKey
            )
        }
        assertCandidateError(.roleMismatch) {
            _ = try ProductionC1EndpointOperationProof.signed(
                requesterRole: .client,
                operation: .fetch,
                candidateOwnerRole: .client,
                proofId: proof.proofId,
                attemptId: proof.attemptId,
                capabilityId: proof.capabilityId,
                candidateBatch: fixture.clientBatch,
                singleUseNonce: proof.singleUseNonce,
                securityContext: fixture.securityContext,
                serviceAudienceId: serviceId,
                authority: fixture.authority,
                issuedAtMs: proof.issuedAtMs,
                notBeforeMs: proof.notBeforeMs,
                expiresAtMs: proof.expiresAtMs,
                using: fixture.clientIdentityKey
            )
        }

        let wrongContextProof = try ProductionC1EndpointOperationProof(
            canonicalBytes: replacingTLVField(
                in: proof.canonicalBytes(),
                tag: 15,
                with: Data(String(repeating: "f", count: 64).utf8)
            )
        )
        assertCandidateError(.roleMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyCapability(
                value.capability,
                candidateBatchCanonicalBytes: fixture.clientBatch.canonicalBytes(),
                endpointOperationProof: wrongContextProof,
                securityContext: fixture.securityContext,
                authority: fixture.authority,
                verifiedKeyset: fixture.verifiedKeyset,
                nowMs: now
            )
        }

        let authorization = fixture.authorizations.clientPublish
        let frontRunId = String(repeating: "0", count: 64)
        let frontRunDigest = try ProductionC1CandidateUsageLedger.requestDigest(
            requestId: frontRunId,
            capabilityDigest: value.capabilityDigest,
            authorizationDigest: digest(try authorization.canonicalBytes())
        )
        let usageState = try initialUsageState(fixture)
        assertCandidateError(.roleMismatch) {
            _ = try ProductionC1CandidateUsageLedger.prepareConsume(
                state: usageState,
                expectedRevision: usageState.revision,
                expectedSnapshotDigest: try usageState.snapshotDigestHex(),
                requestId: frontRunId,
                requestDigest: frontRunDigest,
                verifiedCapability: value,
                authorization: authorization,
                authenticatedLocalRole: .client,
                authenticatedLocalIdentityFingerprint:
                    fixture.authority.clientIdentityFingerprint,
                authority: fixture.authority,
                nowMs: now
            )
        }
    }

    func testObject26RejectsEvidencePolicyAndRoleSubstitution() throws {
        let fixture = try makeFixture()
        let committed = try commitAllOperations(fixture)
        let grant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: committed.operationReceipts,
            initiatorRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        let canonical = try grant.grantAuthorization.authorization.canonicalBytes()
        let substitutions: [Data] = [
            try replacingTLVField(
                in: canonical,
                tag: 3,
                with: Data(String(repeating: "0", count: 64).utf8)
            ),
            try replacingTLVField(in: canonical, tag: 15, with: uint64Bytes(2)),
            try replacingTLVFields(
                in: canonical,
                replacements: [
                    12: Data(P2PNATRole.runtime.rawValue.utf8),
                    13: Data(P2PNATRole.client.rawValue.utf8),
                ]
            ),
        ]
        for bytes in substitutions {
            let substituted = try ProductionC1P2PGrantAuthorization(canonicalBytes: bytes)
            assertCandidateError(.routeMismatch) {
                _ = try ProductionC1CandidateVerifier.verifyGrantAuthorization(
                    substituted,
                    evidence: grant.evidence,
                    plan: fixture.plan,
                    localRole: .client
                )
            }
        }
    }

    func testPublicOnlyPolicyDeniesRegistrySpecialPurposePrefixes() {
        let blocked: [Data] = [
            Data([192, 0, 2, 1]),
            Data([198, 18, 0, 1]),
            Data([100, 64, 0, 1]),
            Data([0x20, 0x01, 0x01, 0x00] + Array(repeating: 0, count: 12)),
            Data([0x20, 0x01, 0x0d, 0xb8] + Array(repeating: 0, count: 12)),
            Data(Array(repeating: 0, count: 10) + [0xff, 0xff, 8, 8, 8, 8]),
            Data([0x20, 0x02] + Array(repeating: 0, count: 14)),
        ]
        for address in blocked {
            XCTAssertFalse(
                ProductionC1PublicOnlyV1Policy.allows(address: address, port: 50_000),
                "unexpectedly allowed \(address as NSData)"
            )
        }
        XCTAssertFalse(ProductionC1PublicOnlyV1Policy.allows(
            address: Data([1, 1, 1, 1]),
            port: 443
        ))
        XCTAssertTrue(ProductionC1PublicOnlyV1Policy.allows(
            address: Data([1, 1, 1, 1]),
            port: 50_000
        ))
        XCTAssertTrue(ProductionC1PublicOnlyV1Policy.allows(
            address: Data([
                0x26, 0x06, 0x47, 0x00, 0x47, 0x00, 0, 0,
                0, 0, 0, 0, 0, 0, 0x11, 0x11,
            ]),
            port: 50_000
        ))
    }

    func testClientOnlyOutboundAndRuntimeOnlyInboundRejectRoleAndPeerSubstitution() throws {
        let fixture = try makeFixture()
        let committed = try commitAllOperations(fixture)
        let grant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: committed.operationReceipts,
            initiatorRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PConnectorInput(
                for: grant,
                localRole: .runtime,
                routeHandle: "direct-01",
                nonce: "nonce-01",
                secret: Data(repeating: 0x5a, count: 32),
                authority: fixture.authority,
                nowMs: now
            )
        }

        let transcript = try makeTranscript(
            fixture,
            routeAuthorizationDigest: grant.grantAuthorization.digestHex
        )
        let confirmationKey = Data(repeating: 0x77, count: 32)
        let clientConfirmation = try ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            transcript: transcript,
            grantAuthorization: grant.grantAuthorization,
            confirmingRole: .client,
            key: confirmationKey
        )
        let inbound = try ProductionC1CandidateVerifier.verifyP2PInboundMaterial(
            transcript: transcript,
            verifiedGrant: grant,
            localRole: .runtime,
            observedPeerCandidate: fixture.plan.selectedClientCandidate,
            keyConfirmationKey: confirmationKey,
            presentedPeerKeyConfirmation: clientConfirmation,
            authority: fixture.authority,
            nowMs: now
        )
        XCTAssertEqual(
            inbound.transcriptDigest,
            ProductionC1InternalBridge.digestHex(transcript.canonicalBytes())
        )
        XCTAssertEqual(inbound.routeGrantDigest, try grant.evidence.digestHex())
        XCTAssertEqual(
            inbound.grantAuthorizationDigest,
            grant.grantAuthorization.digestHex
        )
        XCTAssertEqual(inbound.sessionId, transcript.sessionId)
        _ = try ProductionC1CandidateVerifier.verifyP2PInboundTranscriptBinding(
            transcript: transcript,
            verifiedGrant: grant,
            inboundMaterial: inbound,
            localRole: .runtime,
            authority: fixture.authority,
            nowMs: now
        )
        let anotherSession = try ProductionSecureSessionTranscript(
            sessionId: String(repeating: "d", count: 32),
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
            routeKind: transcript.routeKind,
            routeAuthDigest: transcript.routeAuthDigest
        )
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PInboundTranscriptBinding(
                transcript: anotherSession,
                verifiedGrant: grant,
                inboundMaterial: inbound,
                localRole: .runtime,
                authority: fixture.authority,
                nowMs: now
            )
        }
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PInboundMaterial(
                transcript: transcript,
                verifiedGrant: grant,
                localRole: .client,
                observedPeerCandidate: fixture.plan.selectedClientCandidate,
                keyConfirmationKey: confirmationKey,
                presentedPeerKeyConfirmation: clientConfirmation,
                authority: fixture.authority,
                nowMs: now
            )
        }
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PInboundMaterial(
                transcript: transcript,
                verifiedGrant: grant,
                localRole: .runtime,
                observedPeerCandidate: fixture.plan.selectedRuntimeCandidate,
                keyConfirmationKey: confirmationKey,
                presentedPeerKeyConfirmation: clientConfirmation,
                authority: fixture.authority,
                nowMs: now
            )
        }
    }

    func testProductionActivationPersistenceGateFailsClosed() {
        assertCandidateError(.persistenceUnavailable) {
            try ProductionC1CandidateVerifier.requireProductionP2PActivationPersistence()
        }
    }

    func testBilateralAndPlanRejectSameVersionKeysetForks() throws {
        let fixture = try makeFixture()
        let forkedDelegated = try ProductionC1DelegatedKey(
            keysetVersion: 1,
            keyId: keyId(fixture.signingKey.publicKey),
            purposes: [
                .routeCapability, .candidatePublish, .candidateFetch,
                .candidatePublishReceipt, .candidateFetchReceipt,
            ],
            notBeforeMs: now - 1_000,
            expiresAtMs: now + 90_000,
            publicKeyX963: fixture.signingKey.publicKey.x963Representation
        )
        let forkedKeyset = try ProductionC1ServiceKeyset.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            previousKeysetDigest: nil,
            issuedAtMs: now - 1_000,
            expiresAtMs: now + 90_000,
            delegatedKeys: [forkedDelegated],
            using: fixture.rootKey
        )
        let verifiedFork = try ProductionC1Verifier.verifyServiceKeyset(
            forkedKeyset,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: fixture.rootKey.publicKey,
            minimumAcceptedKeysetVersion: 1,
            nowMs: now
        )
        XCTAssertNotEqual(
            try fixture.verifiedKeyset.keyset.canonicalBytes(),
            try verifiedFork.keyset.canonicalBytes()
        )

        let originalRuntimePublish = fixture.bilateral.runtimePublish
        let forkedRuntimePublish = try ProductionC1CandidateVerifier.verifyCapability(
            originalRuntimePublish.capability,
            candidateBatchCanonicalBytes: originalRuntimePublish.canonicalCandidateBatch,
            endpointOperationProof: originalRuntimePublish.endpointOperationProof,
            securityContext: originalRuntimePublish.securityContext,
            authority: fixture.authority,
            verifiedKeyset: verifiedFork,
            nowMs: now
        )
        assertCandidateError(.authorityMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyBilateral(
                clientPublish: fixture.bilateral.clientPublish,
                runtimeFetchClient: fixture.bilateral.runtimeFetchClient,
                runtimePublish: forkedRuntimePublish,
                clientFetchRuntime: fixture.bilateral.clientFetchRuntime,
                authority: fixture.authority,
                nowMs: now
            )
        }
        let forgedBilateral = VerifiedProductionC1BilateralCandidateCapabilities(
            clientPublish: fixture.bilateral.clientPublish,
            runtimeFetchClient: fixture.bilateral.runtimeFetchClient,
            runtimePublish: fixture.bilateral.runtimePublish,
            clientFetchRuntime: fixture.bilateral.clientFetchRuntime,
            bilateralPublishDigest: String(repeating: "0", count: 64),
            bilateralFetchDigest: fixture.bilateral.bilateralFetchDigest
        )
        assertCandidateError(.authorityMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PDirectPlan(
                claims: fixture.claims,
                capability: fixture.routeCapability,
                securityContext: fixture.securityContext,
                bilateral: forgedBilateral,
                selectedClientCandidate: fixture.plan.selectedClientCandidate,
                selectedRuntimeCandidate: fixture.plan.selectedRuntimeCandidate,
                pathValidationReceiptCanonicalBytes:
                    fixture.plan.pathValidationReceipt.canonicalBytes(),
                authority: fixture.authority,
                verifiedKeyset: fixture.verifiedKeyset,
                nowMs: now
            )
        }
        assertCandidateError(.authorityMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PDirectPlan(
                claims: fixture.claims,
                capability: fixture.routeCapability,
                securityContext: fixture.securityContext,
                bilateral: fixture.bilateral,
                selectedClientCandidate: fixture.plan.selectedClientCandidate,
                selectedRuntimeCandidate: fixture.plan.selectedRuntimeCandidate,
                pathValidationReceiptCanonicalBytes:
                    fixture.plan.pathValidationReceipt.canonicalBytes(),
                authority: fixture.authority,
                verifiedKeyset: verifiedFork,
                nowMs: now
            )
        }
    }

    private func makeVerifiedEndpointBinding(
        _ fixture: Fixture
    ) throws -> VerifiedProductionC1CandidateP2PTranscriptBinding {
        let committed = try commitAllOperations(fixture)
        let grant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: fixture.plan,
            routeAuthorizations: fixture.authorizations,
            operationReceipts: committed.operationReceipts,
            initiatorRole: .client,
            authority: fixture.authority,
            nowMs: now
        )
        let transcript = try makeTranscript(
            fixture,
            routeAuthorizationDigest: grant.grantAuthorization.digestHex
        )
        let connectorInput = try ProductionC1CandidateVerifier.verifyP2PConnectorInput(
            for: grant,
            localRole: .client,
            routeHandle: "direct-01",
            nonce: "nonce-01",
            secret: Data(repeating: 0x5a, count: 32),
            authority: fixture.authority,
            nowMs: now
        )
        let confirmationKey = Data(repeating: 0x77, count: 32)
        let runtimeConfirmation = try ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            transcript: transcript,
            grantAuthorization: grant.grantAuthorization,
            confirmingRole: .runtime,
            key: confirmationKey
        )
        return try ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
            transcript: transcript,
            verifiedGrant: grant,
            connectorInput: connectorInput,
            localRole: .client,
            keyConfirmationKey: confirmationKey,
            presentedPeerKeyConfirmation: runtimeConfirmation,
            authority: fixture.authority,
            nowMs: now
        )
    }

    private func makeKeyScheduleBinding(
        fixture: Fixture,
        endpointBinding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        role: P2PNATRole
    ) throws -> VerifiedProductionC1CandidateP2PKeyScheduleBinding {
        try ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
            transcript: endpointBinding.transcript,
            verifiedGrant: endpointBinding.grant,
            localRole: role,
            authority: fixture.authority,
            nowMs: now
        )
    }

    private func agreementKey(_ scalar: UInt8) throws
        -> P2PNATSessionEphemeralKey
    {
        var raw = Data(repeating: 0, count: 32)
        raw[31] = scalar
        return try P2PNATSessionEphemeralKey(testPrivateScalar: raw)
    }

    private func advancedAuthority(
        from previous: ProductionPairAuthorityState
    ) throws -> ProductionPairAuthorityState {
        try ProductionPairAuthorityState(
            pairBindingDigest: previous.pairBindingDigest,
            pairEpoch: previous.pairEpoch,
            clientIdentityFingerprint: previous.clientIdentityFingerprint,
            runtimeIdentityFingerprint: previous.runtimeIdentityFingerprint,
            generation: previous.generation + 1,
            serviceConfigVersion: previous.serviceConfigVersion,
            keysetVersion: previous.keysetVersion,
            revocationCounter: previous.revocationCounter,
            protocolFloor: previous.protocolFloor,
            status: .active,
            transitionId: String(repeating: "7", count: 64),
            transitionRequestDigest: String(repeating: "8", count: 64),
            acceptedReceiptDigest: previous.acceptedReceiptDigest,
            authorityRevision: previous.authorityRevision + 1
        )
    }

    private func makeActiveTransportFixture(
        suffix: String
    ) async throws -> ActiveTransportFixture {
        let fixture = try makeFixture()
        let binding = try makeVerifiedEndpointBinding(fixture)
        let clock = ExactBoundDurableClock(now)
        let durable = try await makeDurablyCommittedExactBoundFixture(
            fixture: fixture,
            binding: binding,
            clock: clock,
            suffix: suffix
        )
        let coordinator = await durable.store.productionC1ExactBoundStartCoordinator()
        let session = try await durable.store.beginProductionC1TransportSecureSession(
            deviceID: durable.device.id,
            expectedPublicKeyBase64: durable.device.publicKeyBase64,
            token: durable.token,
            verifiedBinding: binding,
            localEphemeralKey: try agreementKey(21)
        )
        let clientHandshake = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: try makeKeyScheduleBinding(
                fixture: fixture,
                endpointBinding: binding,
                role: .client
            ),
            localEphemeralKey: try agreementKey(20),
            nowMs: clock.get()
        )
        let runtimeConfirmation = ExactBoundSecureSessionRetainedValue<Data>()
        try await session.sendLocalConfirmation { bytes in
            runtimeConfirmation.store(bytes)
        }
        guard let runtimeBytes = runtimeConfirmation.get() else {
            throw ExactBoundTransportTestError.missingConfirmation
        }
        let clientConfirmation = try clientHandshake.localConfirmation(
            nowMs: clock.get()
        )
        try clientHandshake.markLocalConfirmationSent(
            clientConfirmation,
            nowMs: clock.get()
        )
        try await session.acceptPeerConfirmation(clientConfirmation)
        try clientHandshake.acceptPeerConfirmation(
            runtimeBytes,
            nowMs: clock.get()
        )
        try await session.activate()
        return ActiveTransportFixture(
            store: durable.store,
            device: durable.device,
            token: durable.token,
            coordinator: coordinator,
            session: session,
            clientCipher: try clientHandshake.makeCipher(nowMs: clock.get()),
            clock: clock,
            nextAuthority: try advancedAuthority(from: fixture.authority)
        )
    }

    private func makeDurablyCommittedExactBoundFixture(
        fixture: Fixture,
        binding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        clock: ExactBoundDurableClock,
        suffix: String
    ) async throws -> (
        store: TrustedDeviceStore,
        device: TrustedDevice,
        token: ProductionC1EndpointGrantCompoundCommitToken,
        request: ProductionC1ExactBoundStartRequest,
        firstPreparation: ProductionC1EndpointGrantAdmissionPreparation
    ) {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("trusted-devices.json")
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            trustedNowEpochMillis: { clock.get() }
        )
        let device = TrustedDevice(
            id: "exact-bound-\(suffix)",
            name: "Exact bound \(suffix)",
            publicKeyBase64: "exact-bound-key-\(suffix)"
        )
        try await store.trust(device)
        let initialPair = try await store.installProductionPairStateForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            authority: fixture.authority
        )
        let initialLedger = try ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest: fixture.authority.digestHex(),
            pairLocalRevision: initialPair.localRevision,
            remainingGrants: UInt64(
                ProductionC1EndpointLedgerPersistenceContract.maximumEntries
            ),
            retentionLimit: UInt32(
                ProductionC1EndpointLedgerPersistenceContract.maximumEntries
            )
        )
        let admissionID = digest(Data("exact-bound-admission-\(suffix)".utf8))
        let routeGrantDigest = try binding.grant.evidence.digestHex()
        let transcriptDigest = digest(binding.transcript.canonicalBytes())
        let routeAuthorizationDigest = digest(
            try binding.grant.routeAuthorizations.finalP2PDirect.canonicalBytes()
        )
        let grantAuthorizationDigest = try binding.grant
            .grantAuthorization.authorization.digestHex()
        let bindingDigest = try ProductionC1EndpointGrantAdmission.bindingDigest(
            admissionId: admissionID,
            routeGrantDigest: routeGrantDigest,
            transcriptDigest: transcriptDigest,
            routeAuthorizationDigest: routeAuthorizationDigest,
            grantAuthorizationDigest: grantAuthorizationDigest,
            connectorInputCommitmentDigest: binding.connectorInput.commitmentDigest
        )
        let firstPreparation = try ProductionC1EndpointGrantAdmission.prepare(
            state: initialLedger,
            expectedRevision: initialLedger.revision,
            expectedSnapshotDigest: initialLedger.snapshotDigestHex(),
            admissionId: admissionID,
            bindingDigest: bindingDigest,
            verifiedBinding: binding,
            currentPairSnapshot: initialPair,
            nowMs: clock.get()
        )
        let outcome = try await store.commitProductionC1EndpointGrant(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            admissionID: admissionID,
            bindingDigest: bindingDigest,
            verifiedBinding: binding
        )
        guard case let .committed(token) = outcome else {
            throw ExactBoundDurableFixtureError.nonAppliedCommit
        }
        let request = ProductionC1ExactBoundStartRequest(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            token: token,
            verifiedBinding: binding
        )
        return (store, device, token, request, firstPreparation)
    }

    private func syntheticNextEndpointPreparation(
        currentLedger: ProductionC1EndpointGrantLedgerState,
        currentPair: ProductionPairStateSnapshot,
        effectiveNotBeforeMs: UInt64,
        expiresAtMs: UInt64
    ) throws -> ProductionC1EndpointGrantAdmissionPreparation {
        let sessionID = String(repeating: "b", count: 32)
        let transcriptDigest = digest(Data("synthetic second transcript".utf8))
        let nextPair = try ProductionPairStateSnapshot(
            authority: currentPair.authority,
            localRevision: currentPair.localRevision + 1,
            consumedEntries: currentPair.consumedEntries + [
                try ProductionPairConsumedSession(
                    sessionId: sessionID,
                    transcriptDigest: transcriptDigest
                ),
            ],
            transitionHistory: currentPair.transitionHistory
        )
        let entry = ProductionC1EndpointGrantEntry(
            admissionId: digest(Data("synthetic second admission".utf8)),
            bindingDigest: digest(Data("synthetic second binding".utf8)),
            routeGrantDigest: digest(Data("synthetic second grant".utf8)),
            sessionId: sessionID,
            transcriptDigest: transcriptDigest,
            routeAuthorizationDigest: digest(Data("synthetic object 4".utf8)),
            grantAuthorizationDigest: digest(Data("synthetic object 26".utf8)),
            connectorInputCommitmentDigest: digest(Data("synthetic connector".utf8)),
            pairSnapshotDigest: try nextPair.digestHex(),
            committedRevision: currentLedger.revision + 1
        )
        let nextLedger = try ProductionC1EndpointGrantLedgerState(
            revision: currentLedger.revision + 1,
            pairAuthorityDigest: currentLedger.pairAuthorityDigest,
            pairLocalRevision: nextPair.localRevision,
            remainingGrants: currentLedger.remainingGrants - 1,
            retentionLimit: currentLedger.retentionLimit,
            entries: currentLedger.entries + [entry]
        )
        let currentCompound = try ProductionC1EndpointCompoundRecord(
            grantLedger: currentLedger,
            pairSnapshot: currentPair
        )
        let nextCompound = try ProductionC1EndpointCompoundRecord(
            grantLedger: nextLedger,
            pairSnapshot: nextPair
        )
        return try ProductionC1EndpointGrantAdmissionPreparation(
            disposition: .applied,
            sessionID: entry.sessionId,
            routeAuthorizationDigest: entry.routeAuthorizationDigest,
            grantAuthorizationDigest: entry.grantAuthorizationDigest,
            pairAuthorityDigest: currentLedger.pairAuthorityDigest,
            effectiveNotBeforeMs: effectiveNotBeforeMs,
            expiresAtMs: expiresAtMs,
            expectedRevision: currentLedger.revision,
            expectedSnapshotDigest: currentLedger.snapshotDigestHex(),
            expectedPairSnapshotDigest: currentPair.digestHex(),
            nextState: nextLedger,
            nextPairSnapshot: nextPair,
            expectedCompoundDigest: currentCompound.digestHex(),
            nextCompoundRecord: nextCompound,
            entry: entry
        )
    }

    private struct Fixture {
        let rootKey: P256.Signing.PrivateKey
        let signingKey: P256.Signing.PrivateKey
        let clientIdentityKey: P256.Signing.PrivateKey
        let runtimeIdentityKey: P256.Signing.PrivateKey
        let authority: ProductionPairAuthorityState
        let verifiedKeyset: VerifiedProductionC1ServiceKeyset
        let clientBatch: CandidateBatch
        let runtimeBatch: CandidateBatch
        let bilateral: VerifiedProductionC1BilateralCandidateCapabilities
        let securityContext: ProductionC1PreauthorizationSessionContext
        let claims: ProductionC1RoutePlanClaims
        let routeCapability: ProductionC1RouteCapability
        let plan: VerifiedProductionC1CandidateP2PPlan
        let authorizations: ProductionC1BilateralRouteAuthorizations

        var bilateralValues: [VerifiedProductionC1CandidateCapability] {
            [bilateral.clientPublish, bilateral.runtimeFetchClient,
             bilateral.runtimePublish, bilateral.clientFetchRuntime]
        }

        var operationAuthorizations: [ProductionRouteAuthorization] {
            [authorizations.clientPublish, authorizations.runtimeFetchClient,
             authorizations.runtimePublish, authorizations.clientFetchRuntime]
        }

        var unwrappedBasePlan: VerifiedProductionC1RoutePlan {
            // A dedicated verifier intentionally keeps this inaccessible; re-verifying through
            // the internal testable base proves the public generic authorization gate rejects it.
            try! ProductionC1Verifier.verifyCandidateP2PRoutePlanBase(
                claims: claims,
                capability: routeCapability,
                securityContext: securityContext,
                authority: authority,
                verifiedKeyset: verifiedKeyset,
                nowMs: 1_000_000
            )
        }
    }

    private struct ActiveTransportFixture {
        let store: TrustedDeviceStore
        let device: TrustedDevice
        let token: ProductionC1EndpointGrantCompoundCommitToken
        let coordinator: ProductionC1ExactBoundStartCoordinator
        let session: ProductionC1TransportSecureSession
        let clientCipher: ProductionSecureSessionCipher
        let clock: ExactBoundDurableClock
        let nextAuthority: ProductionPairAuthorityState
    }

    private func makeFixture(
        clientAddress: [UInt8] = [1, 1, 1, 1]
    ) throws -> Fixture {
        let root = try privateKey(1)
        let signing = try privateKey(2)
        let delegated = try ProductionC1DelegatedKey(
            keysetVersion: 1,
            keyId: keyId(signing.publicKey),
            purposes: [
                .routeCapability, .candidatePublish, .candidateFetch,
                .candidatePublishReceipt, .candidateFetchReceipt,
            ],
            notBeforeMs: now - 1_000,
            expiresAtMs: now + 100_000,
            publicKeyX963: signing.publicKey.x963Representation
        )
        let keyset = try ProductionC1ServiceKeyset.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            previousKeysetDigest: nil,
            issuedAtMs: now - 1_000,
            expiresAtMs: now + 100_000,
            delegatedKeys: [delegated],
            using: root
        )
        let verifiedKeyset = try ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: root.publicKey,
            minimumAcceptedKeysetVersion: 1,
            nowMs: now
        )
        let clientIdentityKey = try privateKey(10)
        let runtimeIdentityKey = try privateKey(11)
        let authority = try ProductionPairAuthorityState(
            pairBindingDigest: String(repeating: "d", count: 64),
            pairEpoch: 1,
            clientIdentityFingerprint: keyId(clientIdentityKey.publicKey),
            runtimeIdentityFingerprint: keyId(runtimeIdentityKey.publicKey),
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
        let sessionId = String(repeating: "a", count: 32)
        let securityContext = try ProductionC1PreauthorizationSessionContext(
            sessionId: sessionId,
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
        let clientBatch = try makeBatch(
            sessionId: sessionId,
            role: .client,
            sequence: 1,
            address: clientAddress
        )
        let runtimeBatch = try makeBatch(
            sessionId: sessionId,
            role: .runtime,
            sequence: 2,
            address: [8, 8, 4, 4]
        )
        func capability(
            _ operation: ProductionC1CandidateOperation,
            requester: P2PNATRole,
            owner: P2PNATRole,
            proof: Character,
            id: Character,
            nonce: Character,
            batch: CandidateBatch
        ) throws -> VerifiedProductionC1CandidateCapability {
            let identityKey = requester == .client ? clientIdentityKey : runtimeIdentityKey
            let endpointProof = try ProductionC1EndpointOperationProof.signed(
                requesterRole: requester,
                operation: operation,
                candidateOwnerRole: owner,
                proofId: String(repeating: String(proof), count: 64),
                attemptId: String(repeating: "b", count: 64),
                capabilityId: String(repeating: String(id), count: 64),
                candidateBatch: batch,
                singleUseNonce: String(repeating: String(nonce), count: 64),
                securityContext: securityContext,
                serviceAudienceId: serviceId,
                authority: authority,
                issuedAtMs: now - 200,
                notBeforeMs: now - 10,
                expiresAtMs: now + 20_000,
                using: identityKey
            )
            let value = try ProductionC1CandidateCapability.signed(
                operation: operation,
                serviceIdDigest: serviceId,
                keysetVersion: 1,
                capabilityId: String(repeating: String(id), count: 64),
                attemptId: String(repeating: "b", count: 64),
                requesterRole: requester,
                candidateOwnerRole: owner,
                maximumCandidateBytes: UInt64(P2PNATLimits.candidateBatchBytes),
                singleUseNonce: String(repeating: String(nonce), count: 64),
                issuedAtMs: now - 100,
                notBeforeMs: now - 10,
                expiresAtMs: now + 20_000,
                authority: authority,
                candidateBatch: batch,
                endpointOperationProof: endpointProof,
                using: signing
            )
            return try ProductionC1CandidateVerifier.verifyCapability(
                value,
                candidateBatchCanonicalBytes: batch.canonicalBytes(),
                endpointOperationProof: endpointProof,
                securityContext: securityContext,
                authority: authority,
                verifiedKeyset: verifiedKeyset,
                nowMs: now
            )
        }
        let clientPublish = try capability(
            .publish, requester: .client, owner: .client,
            proof: "1", id: "3", nonce: "7", batch: clientBatch
        )
        let runtimeFetchClient = try capability(
            .fetch, requester: .runtime, owner: .client,
            proof: "2", id: "4", nonce: "8", batch: clientBatch
        )
        let runtimePublish = try capability(
            .publish, requester: .runtime, owner: .runtime,
            proof: "3", id: "5", nonce: "9", batch: runtimeBatch
        )
        let clientFetchRuntime = try capability(
            .fetch, requester: .client, owner: .runtime,
            proof: "4", id: "6", nonce: "c", batch: runtimeBatch
        )
        let bilateral = try ProductionC1CandidateVerifier.verifyBilateral(
            clientPublish: clientPublish,
            runtimeFetchClient: runtimeFetchClient,
            runtimePublish: runtimePublish,
            clientFetchRuntime: clientFetchRuntime,
            authority: authority,
            nowMs: now
        )
        let receipt = try PathValidationReceipt(
            sessionId: sessionId,
            generation: authority.generation,
            candidatePairDigest: ProductionC1CandidateVerifier.selectedCandidatePairDigest(
                clientCandidate: clientBatch.candidates[0],
                runtimeCandidate: runtimeBatch.candidates[0]
            ),
            transport: .direct,
            clientObserved: String(repeating: "3", count: 64),
            runtimeObserved: String(repeating: "4", count: 64),
            validatedAt: now - 100,
            expires: now + 15_000
        )
        let pathDigest = digest(receipt.canonicalBytes())
        let connector = try makeConnector(
            address: Data([8, 8, 4, 4]),
            port: 50_000,
            pathDigest: pathDigest
        )
        let claims = try makeClaims(
            connector: connector,
            securityContext: securityContext,
            authority: authority
        )
        let routeCapability = try self.routeCapability(
            claims: claims,
            authority: authority,
            key: signing
        )
        let plan = try ProductionC1CandidateVerifier.verifyP2PDirectPlan(
            claims: claims,
            capability: routeCapability,
            securityContext: securityContext,
            bilateral: bilateral,
            selectedClientCandidate: clientBatch.candidates[0],
            selectedRuntimeCandidate: runtimeBatch.candidates[0],
            pathValidationReceiptCanonicalBytes: receipt.canonicalBytes(),
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            nowMs: now
        )
        let authorizations = try ProductionC1CandidateVerifier.makeBilateralRouteAuthorizations(
            for: plan,
            authority: authority,
            nowMs: now
        )
        return Fixture(
            rootKey: root,
            signingKey: signing,
            clientIdentityKey: clientIdentityKey,
            runtimeIdentityKey: runtimeIdentityKey,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            clientBatch: clientBatch,
            runtimeBatch: runtimeBatch,
            bilateral: bilateral,
            securityContext: securityContext,
            claims: claims,
            routeCapability: routeCapability,
            plan: plan,
            authorizations: authorizations
        )
    }

    private func makeBatch(
        sessionId: String,
        role: P2PNATRole,
        sequence: UInt64,
        address: [UInt8]
    ) throws -> CandidateBatch {
        try CandidateBatch(
            sessionId: sessionId,
            generation: 1,
            sequence: sequence,
            expires: now + 30_000,
            role: role,
            candidates: [try P2PNATCandidate(
                kind: .srflx,
                family: address.count == 4 ? .ipv4 : .ipv6,
                port: 50_000,
                priority: 100,
                foundation: Data(repeating: UInt8(sequence), count: 8),
                address: Data(address)
            )]
        )
    }

    private func makeConnector(
        address: Data,
        port: UInt16,
        pathDigest: String
    ) throws -> ProductionC1RouteConnectorMaterial {
        let handle = "direct-01"
        let nonce = "nonce-01"
        return try ProductionC1RouteConnectorMaterial(
            kind: .p2pDirect,
            addressBytes: address,
            port: port,
            serverName: nil,
            transport: .udp,
            routeHandleDigest: ProductionC1RouteCommitments.routeHandleDigest(
                kind: .p2pDirect,
                routeHandle: handle
            ),
            credentialCommitmentDigest:
                ProductionC1RouteCommitments.credentialCommitmentDigest(
                    kind: .p2pDirect,
                    routeHandle: handle,
                    nonce: nonce,
                    secret: Data(repeating: 0x5a, count: 32)
                ),
            pathReceiptDigest: pathDigest
        )
    }

    private func makeClaims(
        connector: ProductionC1RouteConnectorMaterial,
        securityContext: ProductionC1PreauthorizationSessionContext,
        authority: ProductionPairAuthorityState
    ) throws -> ProductionC1RoutePlanClaims {
        try ProductionC1RoutePlanClaims(
            planId: String(repeating: "f", count: 64),
            kind: .p2pDirect,
            pairAuthorityDigest: authority.digestHex(),
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            generation: authority.generation,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            connector: connector,
            securityContextDigest: securityContext.digestHex(),
            selectedPathReceiptDigest: connector.pathReceiptDigest,
            notBeforeMs: now - 10,
            expiresAtMs: now + 10_000
        )
    }

    private func routeCapability(
        claims: ProductionC1RoutePlanClaims,
        authority: ProductionPairAuthorityState,
        key: P256.Signing.PrivateKey
    ) throws -> ProductionC1RouteCapability {
        try ProductionC1RouteCapability.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            capabilityId: String(repeating: "e", count: 64),
            issuedAtMs: now - 100,
            notBeforeMs: now - 10,
            expiresAtMs: now + 12_000,
            authority: authority,
            kind: .p2pDirect,
            routePlanClaimsDigest: claims.digestHex(),
            using: key
        )
    }

    private func initialUsageState(
        _ fixture: Fixture,
        revision: UInt64 = 1
    ) throws
        -> ProductionC1CandidateUsageLedgerState {
        try ProductionC1CandidateUsageLedgerState(
            revision: revision,
            remainingOperations: 4,
            remainingBytes: fixture.bilateralValues.reduce(0) {
                $0 + UInt64($1.capability.candidateBatchByteCount)
            },
            retentionLimit: 8
        )
    }

    private func commitAllOperations(
        _ fixture: Fixture,
        initialRevision: UInt64 = 1
    ) throws -> (
        state: ProductionC1CandidateUsageLedgerState,
        operationReceipts: [VerifiedProductionC1CandidateOperationReceipt]
    ) {
        var state = try initialUsageState(fixture, revision: initialRevision)
        var operationReceipts: [VerifiedProductionC1CandidateOperationReceipt] = []
        let ledgerId = digest(Data("candidate-operation-ledger".utf8))
        for index in fixture.bilateralValues.indices {
            let value = fixture.bilateralValues[index]
            let authorization = fixture.operationAuthorizations[index]
            let requestId = value.endpointOperationProof.proofId
            let authorizationDigest = digest(try authorization.canonicalBytes())
            let requestDigest = try ProductionC1CandidateUsageLedger.requestDigest(
                requestId: requestId,
                capabilityDigest: value.capabilityDigest,
                authorizationDigest: authorizationDigest
            )
            let preparation = try ProductionC1CandidateUsageLedger.prepareConsume(
                state: state,
                expectedRevision: state.revision,
                expectedSnapshotDigest: try state.snapshotDigestHex(),
                requestId: requestId,
                requestDigest: requestDigest,
                verifiedCapability: value,
                authorization: authorization,
                authenticatedLocalRole: value.capability.requesterRole,
                authenticatedLocalIdentityFingerprint:
                    value.capability.requesterIdentityFingerprint,
                authority: fixture.authority,
                nowMs: now
            )
            let previousState = state
            state = preparation.nextState
            let confirmed = try ReadbackConfirmedProductionC1CandidateUsageReceipt.confirm(
                preparation,
                committedReadback: state,
                ledgerId: ledgerId,
                commitRecordDigest: digest(Data("candidate-commit-\(index)".utf8))
            )
            let receipt = try ProductionC1CandidateOperationReceipt.signedAfterAppliedCommit(
                verifiedCapability: value,
                authorization: authorization,
                confirmedUsageReceipt: confirmed,
                previousLedgerState: previousState,
                committedLedgerState: state,
                committedAtMs: now,
                issuedAtMs: now,
                notBeforeMs: now,
                expiresAtMs: now + 10_000,
                authority: fixture.authority,
                verifiedKeyset: fixture.verifiedKeyset,
                using: fixture.signingKey
            )
            operationReceipts.append(
                try ProductionC1CandidateOperationReceiptVerifier.verify(
                    receipt,
                    verifiedCapability: value,
                    authorization: authorization,
                    authority: fixture.authority,
                    verifiedKeyset: fixture.verifiedKeyset,
                    nowMs: now
                )
            )
        }
        return (state, operationReceipts)
    }

    private func makeTranscript(
        _ fixture: Fixture,
        routeAuthorizationDigest: String
    ) throws -> ProductionSecureSessionTranscript {
        let context = fixture.securityContext
        return try ProductionSecureSessionTranscript(
            sessionId: context.sessionId,
            pairBindingDigest: context.pairBindingDigest,
            pairEpoch: context.pairEpoch,
            clientIdentityFingerprint: context.clientIdentityFingerprint,
            runtimeIdentityFingerprint: context.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: context.clientEphemeralPublicKey,
            runtimeEphemeralPublicKey: context.runtimeEphemeralPublicKey,
            clientNonce: context.clientNonce,
            runtimeNonce: context.runtimeNonce,
            generation: context.generation,
            serviceConfigVersion: context.serviceConfigVersion,
            keysetVersion: context.keysetVersion,
            revocationCounter: context.revocationCounter,
            routeKind: .p2pDirect,
            routeAuthDigest: routeAuthorizationDigest
        )
    }

    private func privateKey(_ scalar: UInt8) throws -> P256.Signing.PrivateKey {
        var raw = Data(repeating: 0, count: 32)
        raw[31] = scalar
        return try P256.Signing.PrivateKey(rawRepresentation: raw)
    }

    private func keyId(_ key: P256.Signing.PublicKey) -> String {
        digest(key.derRepresentation)
    }

    private func replacingTLVField(
        in data: Data,
        tag: UInt8,
        with replacement: Data
    ) throws -> Data {
        try replacingTLVFields(in: data, replacements: [tag: replacement])
    }

    private func replacingTLVFields(
        in data: Data,
        replacements: [UInt8: Data]
    ) throws -> Data {
        guard data.count >= 6 else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        var output = Data(data.prefix(6))
        var cursor = 6
        while cursor < data.count {
            guard cursor + 5 <= data.count else {
                throw ProductionC1CandidateCapabilityError.malformedCanonical
            }
            let tag = data[cursor]
            let length = data[(cursor + 1)..<(cursor + 5)].reduce(UInt32(0)) {
                ($0 << 8) | UInt32($1)
            }
            let valueStart = cursor + 5
            let valueEnd = valueStart + Int(length)
            guard valueEnd <= data.count else {
                throw ProductionC1CandidateCapabilityError.malformedCanonical
            }
            let value = replacements[tag] ?? Data(data[valueStart..<valueEnd])
            output.append(tag)
            var encodedLength = UInt32(value.count).bigEndian
            Swift.withUnsafeBytes(of: &encodedLength) {
                output.append(contentsOf: $0)
            }
            output.append(value)
            cursor = valueEnd
        }
        return output
    }

    private func uint64Bytes(_ value: UInt64) -> Data {
        var encoded = value.bigEndian
        return Swift.withUnsafeBytes(of: &encoded) { Data($0) }
    }

    private func digest(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    private func assertCandidateError(
        _ expected: ProductionC1CandidateCapabilityError,
        file: StaticString = #filePath,
        line: UInt = #line,
        _ body: () throws -> Void
    ) {
        XCTAssertThrowsError(try body(), file: file, line: line) {
            XCTAssertEqual(
                $0 as? ProductionC1CandidateCapabilityError,
                expected,
                file: file,
                line: line
            )
        }
    }
}

private actor ExactBoundSecureSessionGate {
    private var entered = false
    private var continuation: CheckedContinuation<Void, Never>?

    func suspend() async {
        entered = true
        await withCheckedContinuation { continuation = $0 }
    }

    func waitUntilEntered() async {
        while !entered { await Task.yield() }
    }

    func release() {
        continuation?.resume()
        continuation = nil
    }
}

private actor ExactBoundSecureSessionSignal {
    private var marked = false

    func mark() { marked = true }

    func isMarked() -> Bool { marked }

    func waitUntilMarked() async {
        while !marked { await Task.yield() }
    }
}

private actor ExactBoundSecureSessionArmedGate {
    private var armed = false
    private var entered = false
    private var continuation: CheckedContinuation<Void, Never>?

    func arm() { armed = true }

    func suspendIfArmed() async {
        guard armed else { return }
        armed = false
        entered = true
        await withCheckedContinuation { continuation = $0 }
    }

    func waitUntilEntered() async {
        while !entered { await Task.yield() }
    }

    func release() {
        continuation?.resume()
        continuation = nil
    }
}

private final class ExactBoundSecureSessionRetainedValue<Value: Sendable>:
    @unchecked Sendable
{
    private let lock = NSLock()
    private var value: Value?

    func store(_ value: Value) {
        lock.lock()
        self.value = value
        lock.unlock()
    }

    func get() -> Value? {
        lock.lock()
        defer { lock.unlock() }
        return value
    }
}

private final class ExactBoundSecureSessionCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var value = 0

    func increment() {
        lock.lock()
        value += 1
        lock.unlock()
    }

    func get() -> Int {
        lock.lock()
        defer { lock.unlock() }
        return value
    }
}

private enum ExactBoundTransportTestError: Error, Equatable {
    case missingConfirmation
    case publicationFailed
}

private enum ExactBoundDurableFixtureError: Error {
    case nonAppliedCommit
}

private final class ExactBoundDurableClock: @unchecked Sendable {
    private let lock = NSLock()
    private var instant: UInt64

    init(_ instant: UInt64) { self.instant = instant }

    func get() -> UInt64 {
        lock.lock()
        defer { lock.unlock() }
        return instant
    }

    func set(_ instant: UInt64) {
        lock.lock()
        self.instant = instant
        lock.unlock()
    }
}
