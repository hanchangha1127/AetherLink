import CryptoKit
import Foundation
import XCTest
@testable import P2PNATContracts
@_spi(TrustedDeviceTesting) @testable import TrustedDevices

final class ProductionG1aCContractTests: XCTestCase {
    private let now: UInt64 = 1_000_000
    private let serviceId = String(repeating: "a", count: 64)

    func testServiceKeysetVerifiesCanonicalRoundTripAndNMinusOneRotation() throws {
        let root = try privateKey(1)
        let statusKey = try privateKey(2)
        let routeKey = try privateKey(3)
        let first = try makeKeyset(
            root: root,
            version: 1,
            previousDigest: nil,
            keys: [try delegated(statusKey, version: 1, purposes: [.pairStatus, .routeCapability])]
        )
        let verifiedFirst = try ProductionC1Verifier.verifyServiceKeyset(
            first,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: root.publicKey,
            minimumAcceptedKeysetVersion: 1,
            nowMs: now
        )
        XCTAssertEqual(
            try ProductionC1ServiceKeyset(canonicalBytes: first.canonicalBytes()),
            first
        )

        let second = try makeKeyset(
            root: root,
            version: 2,
            previousDigest: first.digestHex(),
            keys: [
                try delegated(statusKey, version: 1, purposes: [.pairStatus]),
                try delegated(routeKey, version: 2, purposes: [.routeCapability]),
            ].sorted { $0.keyId < $1.keyId }
        )
        let verifiedSecond = try ProductionC1Verifier.verifyServiceKeyset(
            second,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: root.publicKey,
            minimumAcceptedKeysetVersion: 1,
            previous: verifiedFirst,
            nowMs: now
        )
        XCTAssertEqual(verifiedSecond.keyset.keysetVersion, 2)

        let gap = try makeKeyset(
            root: root,
            version: 3,
            previousDigest: first.digestHex(),
            keys: [try delegated(routeKey, version: 3, purposes: [.routeCapability])]
        )
        assertC1Error(.keysetGap) {
            _ = try ProductionC1Verifier.verifyServiceKeyset(
                gap,
                expectedServiceIdDigest: serviceId,
                pinnedRootPublicKey: root.publicKey,
                minimumAcceptedKeysetVersion: 1,
                previous: verifiedFirst,
                nowMs: now
            )
        }
    }

    func testStrictCanonicalDERRejectsHighSAndTrailingMutation() throws {
        let root = try privateKey(4)
        let delegatedKey = try privateKey(5)
        let keyset = try makeKeyset(
            root: root,
            version: 1,
            previousDigest: nil,
            keys: [try delegated(delegatedKey, version: 1, purposes: [.pairStatus])]
        )
        let highS = try makeHighS(keyset.rootSignature)
        let highSBytes = try replacingLastTLVField(in: keyset.canonicalBytes(), with: highS)
        assertC1Error(.highS) {
            _ = try ProductionC1ServiceKeyset(canonicalBytes: highSBytes)
        }

        var trailing = try keyset.canonicalBytes()
        trailing.append(0)
        assertC1Error(.malformedCanonical) {
            _ = try ProductionC1ServiceKeyset(canonicalBytes: trailing)
        }
    }

    func testSignedPairStatusBindsNonceEvidenceHistoryAndFreshness() throws {
        let fixture = try makeFixture()
        let evidence = String(repeating: "e", count: 64)
        let authority = try makeAuthority(
            acceptedReceiptDigest: evidence,
            clientFingerprint: fixture.clientFingerprint,
            runtimeFingerprint: fixture.runtimeFingerprint
        )
        let status = try ProductionC1PairStatus.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            issuedAtMs: now - 100,
            expiresAtMs: now + 10_000,
            requesterRole: .client,
            requestNonce: String(repeating: "9", count: 64),
            transitionKind: .genesis,
            previousAuthorityDigest: nil,
            evidenceKind: .initialPairing,
            authorizationEvidenceDigest: evidence,
            authority: authority,
            transitionHistory: [],
            using: fixture.statusKey
        )
        let verified = try ProductionC1Verifier.verifyPairStatus(
            status,
            expectedServiceIdDigest: serviceId,
            expectedRequesterRole: .client,
            expectedRequestNonce: String(repeating: "9", count: 64),
            current: nil,
            verifiedKeyset: fixture.verifiedKeyset,
            nowMs: now
        )
        XCTAssertEqual(verified.status.authority, authority)
        let currentGenesis = try ProductionPairStateSnapshot(authority: authority, localRevision: 1)
        XCTAssertEqual(
            try ProductionC1Verifier.verifyPairStatus(
                status,
                expectedServiceIdDigest: serviceId,
                expectedRequesterRole: .client,
                expectedRequestNonce: String(repeating: "9", count: 64),
                current: currentGenesis,
                verifiedKeyset: fixture.verifiedKeyset,
                nowMs: now
            ).status.authority,
            authority
        )
        XCTAssertEqual(
            try ProductionC1PairStatus(canonicalBytes: status.canonicalBytes()),
            status
        )

        assertC1Error(.stateMismatch) {
            _ = try ProductionC1Verifier.verifyPairStatus(
                status,
                expectedServiceIdDigest: serviceId,
                expectedRequesterRole: .runtime,
                expectedRequestNonce: String(repeating: "9", count: 64),
                current: nil,
                verifiedKeyset: fixture.verifiedKeyset,
                nowMs: now
            )
        }

        let expired = try ProductionC1PairStatus.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            issuedAtMs: now - 1_000,
            expiresAtMs: now - 1,
            requesterRole: .client,
            requestNonce: String(repeating: "9", count: 64),
            transitionKind: .genesis,
            previousAuthorityDigest: nil,
            evidenceKind: .initialPairing,
            authorizationEvidenceDigest: evidence,
            authority: authority,
            transitionHistory: [],
            using: fixture.statusKey
        )
        assertC1Error(.expired) {
            _ = try ProductionC1Verifier.verifyPairStatus(
                expired,
                expectedServiceIdDigest: serviceId,
                expectedRequesterRole: .client,
                expectedRequestNonce: String(repeating: "9", count: 64),
                current: nil,
                verifiedKeyset: fixture.verifiedKeyset,
                nowMs: now
            )
        }
    }

    func testSignedRevocationStatusAllowsExactAlreadyCurrentReconciliation() throws {
        let fixture = try makeFixture()
        let previous = try makeAuthority(
            acceptedReceiptDigest: String(repeating: "e", count: 64),
            clientFingerprint: fixture.clientFingerprint,
            runtimeFingerprint: fixture.runtimeFingerprint
        )
        let evidence = String(repeating: "f", count: 64)
        let revoked = try ProductionPairAuthorityState(
            pairBindingDigest: previous.pairBindingDigest,
            pairEpoch: previous.pairEpoch,
            clientIdentityFingerprint: previous.clientIdentityFingerprint,
            runtimeIdentityFingerprint: previous.runtimeIdentityFingerprint,
            generation: previous.generation,
            serviceConfigVersion: previous.serviceConfigVersion,
            keysetVersion: previous.keysetVersion,
            revocationCounter: previous.revocationCounter + 1,
            protocolFloor: previous.protocolFloor,
            status: .revoked,
            transitionId: String(repeating: "3", count: 64),
            transitionRequestDigest: String(repeating: "4", count: 64),
            acceptedReceiptDigest: evidence,
            authorityRevision: previous.authorityRevision + 1
        )
        let history = [try ProductionPairTransitionHistoryEntry(
            transitionId: previous.transitionId,
            transitionRequestDigest: previous.transitionRequestDigest
        )]
        let status = try ProductionC1PairStatus.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            issuedAtMs: now - 100,
            expiresAtMs: now + 10_000,
            requesterRole: .client,
            requestNonce: String(repeating: "9", count: 64),
            transitionKind: .revoke,
            previousAuthorityDigest: previous.digestHex(),
            evidenceKind: .denyOnlyRevocation,
            authorizationEvidenceDigest: evidence,
            authority: revoked,
            transitionHistory: history,
            using: fixture.statusKey
        )
        let previousSnapshot = try ProductionPairStateSnapshot(
            authority: previous,
            localRevision: 1
        )
        _ = try ProductionC1Verifier.verifyPairStatus(
            status,
            expectedServiceIdDigest: serviceId,
            expectedRequesterRole: .client,
            expectedRequestNonce: String(repeating: "9", count: 64),
            current: previousSnapshot,
            verifiedKeyset: fixture.verifiedKeyset,
            nowMs: now
        )
        let currentRevoked = try ProductionPairStateSnapshot(
            authority: revoked,
            localRevision: 2,
            transitionHistory: history
        )
        let reconciled = try ProductionC1Verifier.verifyPairStatus(
            status,
            expectedServiceIdDigest: serviceId,
            expectedRequesterRole: .client,
            expectedRequestNonce: String(repeating: "9", count: 64),
            current: currentRevoked,
            verifiedKeyset: fixture.verifiedKeyset,
            nowMs: now
        )
        XCTAssertEqual(reconciled.status.authority, revoked)
    }

    func testVerifiedRoutePlanUsesOneWayDigestDAGAndExactConnectorMaterial() throws {
        let fixture = try makeFixture()
        let evidence = String(repeating: "e", count: 64)
        let authority = try makeAuthority(
            acceptedReceiptDigest: evidence,
            clientFingerprint: fixture.clientFingerprint,
            runtimeFingerprint: fixture.runtimeFingerprint
        )
        let pathDigest = String(repeating: "7", count: 64)
        let routeHandle = "relay-01"
        let nonce = "nonce-01"
        let secret = Data(repeating: 0x5a, count: 32)
        let sessionId = String(repeating: "a", count: 32)
        let clientEphemeral = try privateKey(30).publicKey.x963Representation
        let runtimeEphemeral = try privateKey(31).publicKey.x963Representation
        let clientNonce = String(repeating: "b", count: 32)
        let runtimeNonce = String(repeating: "c", count: 32)
        let securityContext = try ProductionC1PreauthorizationSessionContext(
            sessionId: sessionId,
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: clientEphemeral,
            runtimeEphemeralPublicKey: runtimeEphemeral,
            clientNonce: clientNonce,
            runtimeNonce: runtimeNonce,
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            keysetVersion: authority.keysetVersion,
            revocationCounter: authority.revocationCounter,
            routeKind: .turnRelay
        )
        XCTAssertEqual(
            try ProductionC1PreauthorizationSessionContext(
                canonicalBytes: securityContext.canonicalBytes()
            ),
            securityContext
        )
        let handleDigest = try ProductionC1RouteCommitments.routeHandleDigest(
            kind: .turnRelay,
            routeHandle: routeHandle
        )
        let credentialDigest = try ProductionC1RouteCommitments.credentialCommitmentDigest(
            kind: .turnRelay,
            routeHandle: routeHandle,
            nonce: nonce,
            secret: secret
        )
        let connector = try ProductionC1RouteConnectorMaterial(
            kind: .turnRelay,
            addressBytes: Data([127, 0, 0, 1]),
            port: 443,
            serverName: "relay.example",
            transport: .tlsTcp,
            routeHandleDigest: handleDigest,
            credentialCommitmentDigest: credentialDigest,
            pathReceiptDigest: pathDigest,
            leaseDigest: String(repeating: "6", count: 64),
            allocationDigest: String(repeating: "8", count: 64)
        )
        let claims = try ProductionC1RoutePlanClaims(
            planId: String(repeating: "1", count: 64),
            kind: .turnRelay,
            pairAuthorityDigest: authority.digestHex(),
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            generation: authority.generation,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            connector: connector,
            securityContextDigest: securityContext.digestHex(),
            selectedPathReceiptDigest: pathDigest,
            notBeforeMs: now - 10,
            expiresAtMs: now + 20_000
        )
        let capability = try ProductionC1RouteCapability.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            capabilityId: String(repeating: "3", count: 64),
            issuedAtMs: now - 100,
            notBeforeMs: now - 10,
            expiresAtMs: now + 30_000,
            authority: authority,
            kind: .turnRelay,
            routePlanClaimsDigest: claims.digestHex(),
            using: fixture.routeKey
        )
        let verifiedPlan = try ProductionC1Verifier.verifyRoutePlan(
            claims: claims,
            capability: capability,
            securityContext: securityContext,
            authority: authority,
            verifiedKeyset: fixture.verifiedKeyset,
            nowMs: now
        )
        XCTAssertEqual(verifiedPlan.connectorMaterial, connector)
        XCTAssertEqual(verifiedPlan.claimsDigest, try claims.digestHex())
        XCTAssertEqual(verifiedPlan.capabilityDigest, try capability.digestHex())
        let alteredEphemeralContext = try ProductionC1PreauthorizationSessionContext(
            sessionId: sessionId,
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: try privateKey(32).publicKey.x963Representation,
            runtimeEphemeralPublicKey: runtimeEphemeral,
            clientNonce: clientNonce,
            runtimeNonce: runtimeNonce,
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            keysetVersion: authority.keysetVersion,
            revocationCounter: authority.revocationCounter,
            routeKind: .turnRelay
        )
        assertC1Error(.routeMismatch) {
            _ = try ProductionC1Verifier.verifyRoutePlan(
                claims: claims,
                capability: capability,
                securityContext: alteredEphemeralContext,
                authority: authority,
                verifiedKeyset: fixture.verifiedKeyset,
                nowMs: now
            )
        }

        let verifiedInput = try ProductionC1Verifier.verifyConnectorInput(
            for: verifiedPlan,
            routeHandle: routeHandle,
            nonce: nonce,
            secret: secret,
            nowMs: now
        )
        XCTAssertEqual(verifiedInput.routeHandle, routeHandle)
        assertC1Error(.routeMismatch) {
            _ = try ProductionC1Verifier.verifyConnectorInput(
                for: verifiedPlan,
                routeHandle: routeHandle,
                nonce: nonce,
                secret: Data(repeating: 0x5b, count: 32),
                nowMs: now
            )
        }

        let verifiedAuthorization = try ProductionC1Verifier.makeRouteAuthorization(
            for: verifiedPlan,
            nowMs: now
        )
        XCTAssertEqual(verifiedAuthorization.kind, .turnRelay)
        XCTAssertEqual(verifiedAuthorization.authorization.routePlanClaimsDigest, try claims.digestHex())
        XCTAssertEqual(verifiedAuthorization.authorization.routeCapabilityDigest, try capability.digestHex())
        XCTAssertEqual(
            try ProductionC1RouteAuthorization(canonicalBytes: verifiedAuthorization.canonicalBytes),
            verifiedAuthorization.authorization
        )

        let transcript = try ProductionSecureSessionTranscript(
            sessionId: sessionId,
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: clientEphemeral,
            runtimeEphemeralPublicKey: runtimeEphemeral,
            clientNonce: clientNonce,
            runtimeNonce: runtimeNonce,
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            keysetVersion: authority.keysetVersion,
            revocationCounter: authority.revocationCounter,
            routeKind: .turnRelay,
            routeAuthDigest: verifiedAuthorization.digestHex
        )
        let binding = try ProductionC1Verifier.verifyTranscriptBinding(
            transcript: transcript,
            authorization: verifiedAuthorization,
            verifiedPlan: verifiedPlan,
            connectorInput: verifiedInput,
            authority: authority,
            nowMs: now
        )
        XCTAssertEqual(binding.authorization, verifiedAuthorization)
        XCTAssertEqual(binding.plan, verifiedPlan)
        XCTAssertEqual(binding.connectorInput.commitmentDigest, verifiedInput.commitmentDigest)
        let capabilityReuseTranscript = try ProductionSecureSessionTranscript(
            sessionId: String(repeating: "d", count: 32),
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: clientEphemeral,
            runtimeEphemeralPublicKey: runtimeEphemeral,
            clientNonce: clientNonce,
            runtimeNonce: runtimeNonce,
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            keysetVersion: authority.keysetVersion,
            revocationCounter: authority.revocationCounter,
            routeKind: .turnRelay,
            routeAuthDigest: verifiedAuthorization.digestHex
        )
        assertC1Error(.routeMismatch) {
            _ = try ProductionC1Verifier.verifyTranscriptBinding(
                transcript: capabilityReuseTranscript,
                authorization: verifiedAuthorization,
                verifiedPlan: verifiedPlan,
                connectorInput: verifiedInput,
                authority: authority,
                nowMs: now
            )
        }
        let initialSnapshot = try ProductionPairStateSnapshot(
            authority: authority,
            localRevision: 1
        )
        let admitted = try ProductionC1PairStateAdmission.prepare(
            binding: binding,
            to: initialSnapshot,
            nowMs: now
        )
        XCTAssertEqual(admitted.snapshot.localRevision, 2)
        XCTAssertEqual(admitted.snapshot.consumedEntries.count, 1)
        XCTAssertEqual(admitted.bindingDigest.count, 64)
        XCTAssertEqual(admitted.pairAuthorityDigest, try authority.digestHex())
        XCTAssertEqual(admitted.sessionId, transcript.sessionId)
        XCTAssertEqual(admitted.transcriptDigest, transcript.digestHex)
        XCTAssertEqual(admitted.routeAuthorizationDigest, verifiedAuthorization.digestHex)
        XCTAssertEqual(admitted.routeCapabilityDigest, verifiedPlan.capabilityDigest)
        XCTAssertEqual(admitted.routePlanClaimsDigest, verifiedPlan.claimsDigest)
        XCTAssertEqual(
            admitted.connectorInputCommitmentDigest,
            verifiedInput.commitmentDigest
        )
        XCTAssertEqual(admitted.previousPairSnapshotDigest, try initialSnapshot.digestHex())
        XCTAssertEqual(admitted.pairSnapshotDigest, try admitted.snapshot.digestHex())
        XCTAssertEqual(admitted.effectiveNotBeforeMs, claims.notBeforeMs)
        XCTAssertEqual(admitted.expiresAtMs, claims.expiresAtMs)
        XCTAssertThrowsError(try ProductionC1PairStateAdmission.prepare(
            binding: binding,
            to: admitted.snapshot,
            nowMs: now
        )) { error in
            XCTAssertEqual(error as? ProductionPairStateError, .replay)
        }
        assertC1Error(.expired) {
            _ = try ProductionC1Verifier.makeRouteAuthorization(
                for: verifiedPlan,
                nowMs: claims.expiresAtMs
            )
        }
        assertC1Error(.expired) {
            _ = try ProductionC1Verifier.verifyConnectorInput(
                for: verifiedPlan,
                routeHandle: routeHandle,
                nonce: nonce,
                secret: secret,
                nowMs: claims.expiresAtMs
            )
        }
        assertC1Error(.expired) {
            _ = try ProductionC1Verifier.verifyTranscriptBinding(
                transcript: transcript,
                authorization: verifiedAuthorization,
                verifiedPlan: verifiedPlan,
                connectorInput: verifiedInput,
                authority: authority,
                nowMs: claims.expiresAtMs
            )
        }
        assertC1Error(.expired) {
            _ = try ProductionC1PairStateAdmission.prepare(
                binding: binding,
                to: initialSnapshot,
                nowMs: claims.expiresAtMs
            )
        }

        let otherConnector = try ProductionC1RouteConnectorMaterial(
            kind: .turnRelay,
            addressBytes: Data([127, 0, 0, 2]),
            port: 443,
            serverName: "relay.example",
            transport: .tlsTcp,
            routeHandleDigest: connector.routeHandleDigest,
            credentialCommitmentDigest: connector.credentialCommitmentDigest,
            pathReceiptDigest: connector.pathReceiptDigest,
            leaseDigest: connector.leaseDigest,
            allocationDigest: connector.allocationDigest
        )
        let substitutedClaims = try ProductionC1RoutePlanClaims(
            planId: claims.planId,
            kind: claims.kind,
            pairAuthorityDigest: claims.pairAuthorityDigest,
            pairBindingDigest: claims.pairBindingDigest,
            pairEpoch: claims.pairEpoch,
            generation: claims.generation,
            clientIdentityFingerprint: claims.clientIdentityFingerprint,
            runtimeIdentityFingerprint: claims.runtimeIdentityFingerprint,
            connector: otherConnector,
            securityContextDigest: claims.securityContextDigest,
            selectedPathReceiptDigest: claims.selectedPathReceiptDigest,
            notBeforeMs: claims.notBeforeMs,
            expiresAtMs: claims.expiresAtMs
        )
        assertC1Error(.routeMismatch) {
            _ = try ProductionC1Verifier.verifyRoutePlan(
                claims: substitutedClaims,
                capability: capability,
                securityContext: securityContext,
                authority: authority,
                verifiedKeyset: fixture.verifiedKeyset,
                nowMs: now
            )
        }
    }

    func testRouteCapabilityRejectsWrongPurposeRevokedUnknownAndFutureKeys() throws {
        let root = try privateKey(20)
        let statusOnly = try privateKey(21)
        let authority = try makeAuthority(
            acceptedReceiptDigest: String(repeating: "e", count: 64),
            clientFingerprint: String(repeating: "b", count: 64),
            runtimeFingerprint: String(repeating: "c", count: 64)
        )
        let keyset = try makeKeyset(
            root: root,
            version: 1,
            previousDigest: nil,
            keys: [try delegated(statusOnly, version: 1, purposes: [.pairStatus])]
        )
        let verified = try ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: root.publicKey,
            minimumAcceptedKeysetVersion: 1,
            nowMs: now
        )
        let capability = try ProductionC1RouteCapability.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            capabilityId: String(repeating: "3", count: 64),
            issuedAtMs: now - 100,
            notBeforeMs: now - 10,
            expiresAtMs: now + 100,
            authority: authority,
            kind: .p2pDirect,
            routePlanClaimsDigest: String(repeating: "4", count: 64),
            using: statusOnly
        )
        assertC1Error(.keyPurposeMismatch) {
            _ = try ProductionC1Verifier.verifyRouteCapability(
                capability,
                authority: authority,
                verifiedKeyset: verified,
                nowMs: now
            )
        }


        let unknown = try privateKey(22)
        let unknownCapability = try ProductionC1RouteCapability.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            capabilityId: String(repeating: "5", count: 64),
            issuedAtMs: now - 100,
            notBeforeMs: now - 10,
            expiresAtMs: now + 100,
            authority: authority,
            kind: .p2pDirect,
            routePlanClaimsDigest: String(repeating: "6", count: 64),
            using: unknown
        )
        assertC1Error(.keyUnavailable) {
            _ = try ProductionC1Verifier.verifyRouteCapability(
                unknownCapability,
                authority: authority,
                verifiedKeyset: verified,
                nowMs: now
            )
        }

        let revokedRoute = try privateKey(23)
        let revokedKeyset = try makeKeyset(
            root: root,
            version: 1,
            previousDigest: nil,
            keys: [try delegated(
                revokedRoute,
                version: 1,
                purposes: [.routeCapability],
                revokedAtMs: now - 1
            )]
        )
        let verifiedRevokedKeyset = try ProductionC1Verifier.verifyServiceKeyset(
            revokedKeyset,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: root.publicKey,
            minimumAcceptedKeysetVersion: 1,
            nowMs: now
        )
        let revokedCapability = try ProductionC1RouteCapability.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            capabilityId: String(repeating: "7", count: 64),
            issuedAtMs: now - 100,
            notBeforeMs: now - 10,
            expiresAtMs: now + 100,
            authority: authority,
            kind: .p2pDirect,
            routePlanClaimsDigest: String(repeating: "8", count: 64),
            using: revokedRoute
        )
        assertC1Error(.keyRevoked) {
            _ = try ProductionC1Verifier.verifyRouteCapability(
                revokedCapability,
                authority: authority,
                verifiedKeyset: verifiedRevokedKeyset,
                nowMs: now
            )
        }

        let futureCapability = try ProductionC1RouteCapability.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            capabilityId: String(repeating: "9", count: 64),
            issuedAtMs: now + ProductionC1Contract.maximumClockSkewMs + 1,
            notBeforeMs: now + ProductionC1Contract.maximumClockSkewMs + 1,
            expiresAtMs: now + ProductionC1Contract.maximumClockSkewMs + 1_000,
            authority: authority,
            kind: .p2pDirect,
            routePlanClaimsDigest: String(repeating: "a", count: 64),
            using: statusOnly
        )
        assertC1Error(.issuedInFuture) {
            _ = try ProductionC1Verifier.verifyRouteCapability(
                futureCapability,
                authority: authority,
                verifiedKeyset: verified,
                nowMs: now
            )
        }
    }

    func testDualSignedFreshPairIsTheOnlyEpochApplyPreparationPath() async throws {
        let fixture = try makeFixture()
        let oldClient = try privateKey(50)
        let survivorRuntime = try privateKey(51)
        let replacementClient = try privateKey(52)
        let previous = try makeAuthority(
            acceptedReceiptDigest: String(repeating: "e", count: 64),
            clientFingerprint: keyId(oldClient.publicKey),
            runtimeFingerprint: keyId(survivorRuntime.publicKey)
        )
        let current = try ProductionPairStateSnapshot(authority: previous, localRevision: 1)
        let previousEndpointSecret = Data(repeating: 0x11, count: 32)
        let previousRouteSeed = Data(repeating: 0x12, count: 32)
        let nextEndpointSecret = Data(repeating: 0x13, count: 32)
        let nextRouteSeed = Data(repeating: 0x14, count: 32)
        let currentCommitments = try ProductionC1RecoveryCommitments.currentToken(
            pairBindingDigest: previous.pairBindingDigest,
            endpointTrafficSecret: previousEndpointSecret,
            routeTokenSeed: previousRouteSeed
        )
        let proof = try ProductionC1FreshPairProof.signed(
            transitionId: String(repeating: "f", count: 64),
            replacementRole: .client,
            previousAuthority: previous,
            nextClientIdentityFingerprint: keyId(replacementClient.publicKey),
            nextRuntimeIdentityFingerprint: keyId(survivorRuntime.publicKey),
            nextGeneration: previous.generation + 1,
            nextServiceConfigVersion: previous.serviceConfigVersion,
            nextKeysetVersion: previous.keysetVersion,
            nextRevocationCounter: previous.revocationCounter,
            nextProtocolFloor: previous.protocolFloor,
            issuedAtMs: now - 100,
            expiresAtMs: now + 10_000,
            freshPairingRequestDigest: String(repeating: "3", count: 64),
            freshPairingResultDigest: String(repeating: "4", count: 64),
            freshTransportBindingDigest: String(repeating: "5", count: 64),
            currentCommitments: currentCommitments,
            nextEndpointTrafficSecret: nextEndpointSecret,
            nextRouteTokenSeed: nextRouteSeed,
            survivorKey: survivorRuntime,
            replacementKey: replacementClient
        )
        assertC1Error(.invalidFreshPair) {
            _ = try ProductionC1FreshPairProof.signed(
                transitionId: String(repeating: "6", count: 64),
                replacementRole: .client,
                previousAuthority: previous,
                nextClientIdentityFingerprint: keyId(replacementClient.publicKey),
                nextRuntimeIdentityFingerprint: keyId(survivorRuntime.publicKey),
                nextGeneration: previous.generation + 1,
                nextServiceConfigVersion: previous.serviceConfigVersion,
                nextKeysetVersion: previous.keysetVersion,
                nextRevocationCounter: previous.revocationCounter,
                nextProtocolFloor: previous.protocolFloor,
                issuedAtMs: now - 100,
                expiresAtMs: now + 10_000,
                freshPairingRequestDigest: String(repeating: "3", count: 64),
                freshPairingResultDigest: String(repeating: "4", count: 64),
                freshTransportBindingDigest: String(repeating: "5", count: 64),
                currentCommitments: currentCommitments,
                nextEndpointTrafficSecret: previousEndpointSecret,
                nextRouteTokenSeed: nextRouteSeed,
                survivorKey: survivorRuntime,
                replacementKey: replacementClient
            )
        }
        assertC1Error(.invalidFreshPair) {
            _ = try ProductionC1FreshPairProof.signed(
                transitionId: String(repeating: "7", count: 64),
                replacementRole: .client,
                previousAuthority: previous,
                nextClientIdentityFingerprint: keyId(replacementClient.publicKey),
                nextRuntimeIdentityFingerprint: keyId(survivorRuntime.publicKey),
                nextGeneration: previous.generation + 1,
                nextServiceConfigVersion: previous.serviceConfigVersion,
                nextKeysetVersion: previous.keysetVersion,
                nextRevocationCounter: previous.revocationCounter,
                nextProtocolFloor: previous.protocolFloor,
                issuedAtMs: now - 100,
                expiresAtMs: now + 10_000,
                freshPairingRequestDigest: String(repeating: "3", count: 64),
                freshPairingResultDigest: String(repeating: "4", count: 64),
                freshTransportBindingDigest: String(repeating: "5", count: 64),
                currentCommitments: currentCommitments,
                nextEndpointTrafficSecret: nextEndpointSecret,
                nextRouteTokenSeed: nextEndpointSecret,
                survivorKey: survivorRuntime,
                replacementKey: replacementClient
            )
        }
        let next = try ProductionPairAuthorityState(
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
            acceptedReceiptDigest: proof.digestHex(),
            authorityRevision: proof.nextAuthorityRevision
        )
        let history = [try ProductionPairTransitionHistoryEntry(
            transitionId: previous.transitionId,
            transitionRequestDigest: previous.transitionRequestDigest
        )]
        let status = try ProductionC1PairStatus.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            issuedAtMs: now - 50,
            expiresAtMs: now + 10_000,
            requesterRole: .runtime,
            requestNonce: String(repeating: "9", count: 64),
            transitionKind: .freshPair,
            previousAuthorityDigest: previous.digestHex(),
            evidenceKind: .dualSignedFreshPair,
            authorizationEvidenceDigest: proof.digestHex(),
            authority: next,
            transitionHistory: history,
            using: fixture.statusKey
        )
        let verifiedStatus = try ProductionC1Verifier.verifyPairStatus(
            status,
            expectedServiceIdDigest: serviceId,
            expectedRequesterRole: .runtime,
            expectedRequestNonce: String(repeating: "9", count: 64),
            current: current,
            verifiedKeyset: fixture.verifiedKeyset,
            nowMs: now
        )
        let wrongCurrentCommitments = try ProductionC1RecoveryCommitments.currentToken(
            pairBindingDigest: previous.pairBindingDigest,
            endpointTrafficSecret: Data(repeating: 0x21, count: 32),
            routeTokenSeed: Data(repeating: 0x22, count: 32)
        )
        assertC1Error(.invalidFreshPair) {
            _ = try ProductionC1Verifier.verifyFreshPairProof(
                proof,
                acceptedBy: verifiedStatus,
                current: current,
                currentCommitments: wrongCurrentCommitments,
                survivorPublicKey: survivorRuntime.publicKey,
                replacementPublicKey: replacementClient.publicKey,
                nowMs: now
            )
        }
        let verified = try ProductionC1Verifier.verifyFreshPairProof(
            proof,
            acceptedBy: verifiedStatus,
            current: current,
            currentCommitments: currentCommitments,
            survivorPublicKey: survivorRuntime.publicKey,
            replacementPublicKey: replacementClient.publicKey,
            nowMs: now
        )
        XCTAssertEqual(verified.applyPreparation.nextAuthority, next)
        XCTAssertEqual(proof.previousPairBindingDigest, proof.nextPairBindingDigest)
        XCTAssertNotEqual(
            proof.previousEndpointTrafficSecretReuseDigest,
            proof.nextEndpointTrafficSecretReuseDigest
        )
        XCTAssertEqual(
            try ProductionC1FreshPairProof(canonicalBytes: proof.canonicalBytes()),
            proof
        )
        let qrMutated = try replacingTLVField(
            in: proof.canonicalBytes(),
            tag: 21,
            with: Data(String(repeating: "a", count: 64).utf8)
        )
        let qrMutatedProof = try ProductionC1FreshPairProof(canonicalBytes: qrMutated)
        assertC1Error(.invalidSignature) {
            _ = try ProductionC1Verifier.verifyFreshPairProof(
                qrMutatedProof,
                acceptedBy: verifiedStatus,
                current: current,
                currentCommitments: currentCommitments,
                survivorPublicKey: survivorRuntime.publicKey,
                replacementPublicKey: replacementClient.publicKey,
                nowMs: now
            )
        }

        assertPairStateError(.invalidEpochTransition) {
            _ = try ProductionPairStateMachine.apply(
                ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest: try previous.digestHex(),
                    nextAuthority: next
                ),
                to: current
            )
        }
        let applied = try ProductionC1FreshPairStateMachine.apply(
            verified,
            to: current,
            nowMs: now
        )
        XCTAssertEqual(applied.snapshot.authority, next)
        XCTAssertEqual(applied.snapshot.transitionHistory, history)
        XCTAssertTrue(applied.snapshot.consumedEntries.isEmpty)
        let reconciledCurrentStatus = try ProductionC1Verifier.verifyPairStatus(
            status,
            expectedServiceIdDigest: serviceId,
            expectedRequesterRole: .runtime,
            expectedRequestNonce: String(repeating: "9", count: 64),
            current: applied.snapshot,
            verifiedKeyset: fixture.verifiedKeyset,
            nowMs: now
        )
        XCTAssertEqual(reconciledCurrentStatus.status.authority, applied.snapshot.authority)
        let idempotent = try ProductionC1FreshPairStateMachine.apply(
            verified,
            to: applied.snapshot,
            nowMs: now
        )
        XCTAssertEqual(idempotent.disposition, .idempotent)
        XCTAssertEqual(idempotent.snapshot, applied.snapshot)
        assertC1Error(.expired) {
            _ = try ProductionC1FreshPairStateMachine.apply(
                verified,
                to: current,
                nowMs: proof.expiresAtMs
            )
        }

        assertC1Error(.invalidFreshPair) {
            _ = try ProductionC1FreshPairProof.signed(
                transitionId: String(repeating: "6", count: 64),
                replacementRole: .client,
                previousAuthority: previous,
                nextClientIdentityFingerprint: keyId(replacementClient.publicKey),
                nextRuntimeIdentityFingerprint: keyId(try privateKey(53).publicKey),
                nextGeneration: 2,
                nextServiceConfigVersion: 1,
                nextKeysetVersion: 1,
                nextRevocationCounter: 0,
                nextProtocolFloor: 1,
                issuedAtMs: now,
                expiresAtMs: now + 10_000,
                freshPairingRequestDigest: String(repeating: "7", count: 64),
                freshPairingResultDigest: String(repeating: "8", count: 64),
                freshTransportBindingDigest: String(repeating: "9", count: 64),
                currentCommitments: currentCommitments,
                nextEndpointTrafficSecret: nextEndpointSecret,
                nextRouteTokenSeed: nextRouteSeed,
                survivorKey: survivorRuntime,
                replacementKey: replacementClient
            )
        }

        let wrongSignerProof = try ProductionC1FreshPairProof.signed(
            transitionId: proof.transitionId,
            replacementRole: .client,
            previousAuthority: previous,
            nextClientIdentityFingerprint: proof.nextClientIdentityFingerprint,
            nextRuntimeIdentityFingerprint: proof.nextRuntimeIdentityFingerprint,
            nextGeneration: proof.nextGeneration,
            nextServiceConfigVersion: proof.nextServiceConfigVersion,
            nextKeysetVersion: proof.nextKeysetVersion,
            nextRevocationCounter: proof.nextRevocationCounter,
            nextProtocolFloor: proof.nextProtocolFloor,
            issuedAtMs: proof.issuedAtMs,
            expiresAtMs: proof.expiresAtMs,
            freshPairingRequestDigest: proof.freshPairingRequestDigest,
            freshPairingResultDigest: proof.freshPairingResultDigest,
            freshTransportBindingDigest: proof.freshTransportBindingDigest,
            currentCommitments: currentCommitments,
            nextEndpointTrafficSecret: nextEndpointSecret,
            nextRouteTokenSeed: nextRouteSeed,
            survivorKey: oldClient,
            replacementKey: replacementClient
        )
        assertC1Error(.invalidSignature) {
            _ = try ProductionC1Verifier.verifyFreshPairProof(
                wrongSignerProof,
                acceptedBy: verifiedStatus,
                current: current,
                currentCommitments: currentCommitments,
                survivorPublicKey: survivorRuntime.publicKey,
                replacementPublicKey: replacementClient.publicKey,
                nowMs: now
            )
        }


        let epochPlusTwo = try replacingTLVField(
            in: proof.canonicalBytes(),
            tag: 8,
            with: be(proof.previousPairEpoch + 2)
        )
        assertC1Error(.invalidFreshPair) {
            _ = try ProductionC1FreshPairProof(canonicalBytes: epochPlusTwo)
        }

        let swappedSignatures = try replacingTLVFields(
            in: proof.canonicalBytes(),
            replacements: [35: proof.replacementSignature, 36: proof.survivorSignature]
        )
        let swappedProof = try ProductionC1FreshPairProof(canonicalBytes: swappedSignatures)
        assertC1Error(.invalidSignature) {
            _ = try ProductionC1Verifier.verifyFreshPairProof(
                swappedProof,
                acceptedBy: verifiedStatus,
                current: current,
                currentCommitments: currentCommitments,
                survivorPublicKey: survivorRuntime.publicKey,
                replacementPublicKey: replacementClient.publicKey,
                nowMs: now
            )
        }

        let durabilityFailure = FreshPairDurabilityFailureSwitch()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("trusted-devices.json")
        let trustedNow = now
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                shouldFailDirectorySyncAfterRename: {
                    durabilityFailure.isEnabled()
                }
            ),
            trustedNowEpochMillis: { trustedNow }
        )
        let device = TrustedDevice(
            id: "fresh-pair-uncertain",
            name: "Fresh pair uncertainty",
            publicKeyBase64: "fresh-pair-key"
        )
        try await store.trust(device)
        let installed = try await store.installProductionPairStateForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            authority: previous
        )
        XCTAssertEqual(installed, current)
        let coordinator = await store.productionC1ExactBoundStartCoordinator()
        let validation = ProductionC1ExactBoundStartValidation(
            deviceID: device.id,
            pairAuthorityDigest: try previous.digestHex(),
            markerDigest: String(repeating: "a", count: 64),
            admissionID: String(repeating: "b", count: 64),
            bindingDigest: String(repeating: "c", count: 64),
            sessionID: String(repeating: "d", count: 32),
            effectiveNotBeforeMs: 0,
            expiresAtMs: UInt64.max,
            pairLocalRevision: 1,
            ledgerRevision: 1
        )
        let handle = try await coordinator.admitForTesting(validation) { $0 }
        let abortRecorder = FreshPairDurabilityAbortRecorder()
        _ = try await coordinator.beginForTesting(
            handle,
            claimed: validation,
            validator: { $0 },
            abort: { _ in await abortRecorder.record() }
        )
        durabilityFailure.enable()
        do {
            _ = try await store.applyVerifiedProductionC1FreshPairTransition(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                transition: verified
            )
            XCTFail("Expected fresh-pair post-rename durability uncertainty")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .durabilityUncertainAfterRename
            )
        }
        let abortCount = await abortRecorder.value()
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(abortCount, 1)
        XCTAssertEqual(reasons, [.authorityAdvanced])
    }

    func testHistoricalObjectNamespaceRemainsDisjoint() {
        XCTAssertEqual(ProductionC1Contract.serviceKeysetObjectType, 10)
        XCTAssertEqual(ProductionC1Contract.routePlanObjectType, 14)
        XCTAssertEqual(ProductionC1Contract.preauthorizationSessionContextObjectType, 18)
        XCTAssertEqual(ProductionC1Contract.maximumClockSkewMs, 30_000)
        XCTAssertEqual(ProductionC1Contract.maximumRouteLifetimeMs, 600_000)
        XCTAssertTrue((1...9).allSatisfy { UInt8($0) != ProductionC1Contract.serviceKeysetObjectType })
        XCTAssertEqual(ProductionSecureSessionTranscript.objectType, 7)
        XCTAssertEqual(ProductionPairStateContract.authorityObjectType, 8)
        XCTAssertEqual(ProductionPairStateContract.snapshotObjectType, 9)
    }

    func testFirstTrustRequiresRollbackFloorAndExpiryBoundaryIsExclusive() throws {
        let root = try privateKey(40)
        let delegatedKey = try privateKey(41)
        let versionTwo = try makeKeyset(
            root: root,
            version: 2,
            previousDigest: String(repeating: "1", count: 64),
            keys: [try delegated(delegatedKey, version: 2, purposes: [.pairStatus])]
        )
        let bootstrappedCurrent = try ProductionC1Verifier.verifyServiceKeyset(
            versionTwo,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: root.publicKey,
            minimumAcceptedKeysetVersion: 2,
            nowMs: now
        )
        XCTAssertEqual(bootstrappedCurrent.keyset.keysetVersion, 2)
        assertC1Error(.keysetRollback) {
            _ = try ProductionC1Verifier.verifyServiceKeyset(
                versionTwo,
                expectedServiceIdDigest: serviceId,
                pinnedRootPublicKey: root.publicKey,
                minimumAcceptedKeysetVersion: 3,
                nowMs: now
            )
        }

        let expiringDelegated = try ProductionC1DelegatedKey(
            keysetVersion: 1,
            keyId: keyId(delegatedKey.publicKey),
            purposes: [.pairStatus],
            notBeforeMs: now - 1_000,
            expiresAtMs: now,
            publicKeyX963: delegatedKey.publicKey.x963Representation
        )
        let expiring = try ProductionC1ServiceKeyset.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            previousKeysetDigest: nil,
            issuedAtMs: now - 1_000,
            expiresAtMs: now,
            delegatedKeys: [expiringDelegated],
            using: root
        )
        assertC1Error(.expired) {
            _ = try ProductionC1Verifier.verifyServiceKeyset(
                expiring,
                expectedServiceIdDigest: serviceId,
                pinnedRootPublicKey: root.publicKey,
                minimumAcceptedKeysetVersion: 1,
                nowMs: now
            )
        }


        let first = try makeKeyset(
            root: root,
            version: 1,
            previousDigest: nil,
            keys: [try delegated(delegatedKey, version: 1, purposes: [.pairStatus])]
        )
        let verifiedFirst = try ProductionC1Verifier.verifyServiceKeyset(
            first,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: root.publicKey,
            minimumAcceptedKeysetVersion: 1,
            nowMs: now
        )
        assertC1Error(.keysetRollback) {
            _ = try ProductionC1Verifier.verifyServiceKeyset(
                first,
                expectedServiceIdDigest: serviceId,
                pinnedRootPublicKey: root.publicKey,
                minimumAcceptedKeysetVersion: 1,
                previous: verifiedFirst,
                nowMs: now
            )
        }

        var reordered = try first.canonicalBytes()
        reordered[6] = 2
        assertC1Error(.malformedCanonical) {
            _ = try ProductionC1ServiceKeyset(canonicalBytes: reordered)
        }
    }

    func testCachedKeysetExpiryAndDelegatedValidityAreRecheckedAtUse() throws {
        let root = try privateKey(60)
        let online = try privateKey(61)
        let delegatedKey = try ProductionC1DelegatedKey(
            keysetVersion: 1,
            keyId: keyId(online.publicKey),
            purposes: [.pairStatus, .routeCapability],
            notBeforeMs: now - 1_000,
            expiresAtMs: now + 100,
            publicKeyX963: online.publicKey.x963Representation
        )
        let keyset = try ProductionC1ServiceKeyset.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            previousKeysetDigest: nil,
            issuedAtMs: now - 1_000,
            expiresAtMs: now + 100,
            delegatedKeys: [delegatedKey],
            using: root
        )
        let verifiedKeyset = try ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            expectedServiceIdDigest: serviceId,
            pinnedRootPublicKey: root.publicKey,
            minimumAcceptedKeysetVersion: 1,
            nowMs: now
        )
        let evidence = String(repeating: "e", count: 64)
        let authority = try makeAuthority(
            acceptedReceiptDigest: evidence,
            clientFingerprint: String(repeating: "b", count: 64),
            runtimeFingerprint: String(repeating: "c", count: 64)
        )
        let status = try ProductionC1PairStatus.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            issuedAtMs: now,
            expiresAtMs: now + 1_000,
            requesterRole: .client,
            requestNonce: String(repeating: "9", count: 64),
            transitionKind: .genesis,
            previousAuthorityDigest: nil,
            evidenceKind: .initialPairing,
            authorizationEvidenceDigest: evidence,
            authority: authority,
            transitionHistory: [],
            using: online
        )
        _ = try ProductionC1Verifier.verifyPairStatus(
            status,
            expectedServiceIdDigest: serviceId,
            expectedRequesterRole: .client,
            expectedRequestNonce: String(repeating: "9", count: 64),
            current: nil,
            verifiedKeyset: verifiedKeyset,
            nowMs: now
        )
        assertC1Error(.expired) {
            _ = try ProductionC1Verifier.verifyPairStatus(
                status,
                expectedServiceIdDigest: serviceId,
                expectedRequesterRole: .client,
                expectedRequestNonce: String(repeating: "9", count: 64),
                current: nil,
                verifiedKeyset: verifiedKeyset,
                nowMs: keyset.expiresAtMs
            )
        }
        let capability = try ProductionC1RouteCapability.signed(
            serviceIdDigest: serviceId,
            keysetVersion: 1,
            capabilityId: String(repeating: "3", count: 64),
            issuedAtMs: now,
            notBeforeMs: now,
            expiresAtMs: now + 1_000,
            authority: authority,
            kind: .p2pDirect,
            routePlanClaimsDigest: String(repeating: "4", count: 64),
            using: online
        )
        _ = try ProductionC1Verifier.verifyRouteCapability(
            capability,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            nowMs: now
        )
        assertC1Error(.expired) {
            _ = try ProductionC1Verifier.verifyRouteCapability(
                capability,
                authority: authority,
                verifiedKeyset: verifiedKeyset,
                nowMs: keyset.expiresAtMs
            )
        }

        let overlongDelegated = try ProductionC1DelegatedKey(
            keysetVersion: 1,
            keyId: keyId(online.publicKey),
            purposes: [.pairStatus],
            notBeforeMs: now - 1_000,
            expiresAtMs: now + 101,
            publicKeyX963: online.publicKey.x963Representation
        )
        assertC1Error(.invalidValue) {
            _ = try ProductionC1ServiceKeyset.signed(
                serviceIdDigest: serviceId,
                keysetVersion: 1,
                previousKeysetDigest: nil,
                issuedAtMs: now - 1_000,
                expiresAtMs: now + 100,
                delegatedKeys: [overlongDelegated],
                using: root
            )
        }
    }

    private struct Fixture {
        let statusKey: P256.Signing.PrivateKey
        let routeKey: P256.Signing.PrivateKey
        let verifiedKeyset: VerifiedProductionC1ServiceKeyset
        let clientFingerprint: String
        let runtimeFingerprint: String
    }

    private func makeFixture() throws -> Fixture {
        let root = try privateKey(10)
        let status = try privateKey(11)
        let route = try privateKey(12)
        let keys = [
            try delegated(status, version: 1, purposes: [.pairStatus]),
            try delegated(route, version: 1, purposes: [.routeCapability]),
        ].sorted { $0.keyId < $1.keyId }
        let keyset = try makeKeyset(
            root: root,
            version: 1,
            previousDigest: nil,
            keys: keys
        )
        return Fixture(
            statusKey: status,
            routeKey: route,
            verifiedKeyset: try ProductionC1Verifier.verifyServiceKeyset(
                keyset,
                expectedServiceIdDigest: serviceId,
                pinnedRootPublicKey: root.publicKey,
                minimumAcceptedKeysetVersion: 1,
                nowMs: now
            ),
            clientFingerprint: keyId(try privateKey(13).publicKey),
            runtimeFingerprint: keyId(try privateKey(14).publicKey)
        )
    }

    private func makeKeyset(
        root: P256.Signing.PrivateKey,
        version: UInt64,
        previousDigest: String?,
        keys: [ProductionC1DelegatedKey]
    ) throws -> ProductionC1ServiceKeyset {
        try ProductionC1ServiceKeyset.signed(
            serviceIdDigest: serviceId,
            keysetVersion: version,
            previousKeysetDigest: previousDigest,
            issuedAtMs: now - 1_000,
            expiresAtMs: now + 100_000,
            delegatedKeys: keys,
            using: root
        )
    }

    private func delegated(
        _ key: P256.Signing.PrivateKey,
        version: UInt64,
        purposes: ProductionC1DelegatedKeyPurpose,
        revokedAtMs: UInt64? = nil
    ) throws -> ProductionC1DelegatedKey {
        try ProductionC1DelegatedKey(
            keysetVersion: version,
            keyId: keyId(key.publicKey),
            purposes: purposes,
            notBeforeMs: now - 1_000,
            expiresAtMs: now + 100_000,
            revokedAtMs: revokedAtMs,
            publicKeyX963: key.publicKey.x963Representation
        )
    }

    private func makeAuthority(
        acceptedReceiptDigest: String,
        clientFingerprint: String,
        runtimeFingerprint: String
    ) throws -> ProductionPairAuthorityState {
        try ProductionPairAuthorityState(
            pairBindingDigest: String(repeating: "d", count: 64),
            pairEpoch: 1,
            clientIdentityFingerprint: clientFingerprint,
            runtimeIdentityFingerprint: runtimeFingerprint,
            generation: 1,
            serviceConfigVersion: 1,
            keysetVersion: 1,
            revocationCounter: 0,
            protocolFloor: 1,
            status: .active,
            transitionId: String(repeating: "1", count: 64),
            transitionRequestDigest: String(repeating: "2", count: 64),
            acceptedReceiptDigest: acceptedReceiptDigest,
            authorityRevision: 1
        )
    }

    private func privateKey(_ scalar: UInt8) throws -> P256.Signing.PrivateKey {
        var raw = Data(repeating: 0, count: 32)
        raw[31] = scalar
        return try P256.Signing.PrivateKey(rawRepresentation: raw)
    }

    private func keyId(_ key: P256.Signing.PublicKey) -> String {
        SHA256.hash(data: key.derRepresentation).map { String(format: "%02x", $0) }.joined()
    }

    private func assertC1Error(
        _ expected: ProductionC1Error,
        file: StaticString = #filePath,
        line: UInt = #line,
        _ body: () throws -> Void
    ) {
        XCTAssertThrowsError(try body(), file: file, line: line) { error in
            XCTAssertEqual(error as? ProductionC1Error, expected, file: file, line: line)
        }
    }

    private func assertPairStateError(
        _ expected: ProductionPairStateError,
        file: StaticString = #filePath,
        line: UInt = #line,
        _ body: () throws -> Void
    ) {
        XCTAssertThrowsError(try body(), file: file, line: line) { error in
            XCTAssertEqual(error as? ProductionPairStateError, expected, file: file, line: line)
        }
    }

    private func makeHighS(_ der: Data) throws -> Data {
        let signature = try P256.Signing.ECDSASignature(derRepresentation: der)
        let raw = [UInt8](signature.rawRepresentation)
        let order: [UInt8] = [
            0xff, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0x00,
            0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
            0xbc, 0xe6, 0xfa, 0xad, 0xa7, 0x17, 0x9e, 0x84,
            0xf3, 0xb9, 0xca, 0xc2, 0xfc, 0x63, 0x25, 0x51,
        ]
        let lowS = Array(raw[32..<64])
        var highS = Array(repeating: UInt8(0), count: 32)
        var borrow = 0
        for index in stride(from: 31, through: 0, by: -1) {
            var value = Int(order[index]) - Int(lowS[index]) - borrow
            if value < 0 { value += 256; borrow = 1 } else { borrow = 0 }
            highS[index] = UInt8(value)
        }
        return try P256.Signing.ECDSASignature(
            rawRepresentation: Data(Array(raw[0..<32]) + highS)
        ).derRepresentation
    }

    private func replacingLastTLVField(in data: Data, with replacement: Data) throws -> Data {
        var cursor = 6
        var lastStart = 0
        while cursor < data.count {
            lastStart = cursor
            guard cursor + 5 <= data.count else { throw ProductionC1Error.malformedCanonical }
            let length = data[(cursor + 1)..<(cursor + 5)].reduce(UInt32(0)) {
                ($0 << 8) | UInt32($1)
            }
            cursor += 5 + Int(length)
        }
        guard cursor == data.count else { throw ProductionC1Error.malformedCanonical }
        var output = Data(data[..<lastStart])
        output.append(data[lastStart])
        var length = UInt32(replacement.count).bigEndian
        withUnsafeBytes(of: &length) { output.append(contentsOf: $0) }
        output.append(replacement)
        return output
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
        guard data.count >= 6 else { throw ProductionC1Error.malformedCanonical }
        var output = Data(data.prefix(6))
        var cursor = 6
        while cursor < data.count {
            guard cursor + 5 <= data.count else { throw ProductionC1Error.malformedCanonical }
            let tag = data[cursor]
            let length = data[(cursor + 1)..<(cursor + 5)].reduce(UInt32(0)) {
                ($0 << 8) | UInt32($1)
            }
            let valueStart = cursor + 5
            let valueEnd = valueStart + Int(length)
            guard valueEnd <= data.count else { throw ProductionC1Error.malformedCanonical }
            let value = replacements[tag] ?? Data(data[valueStart..<valueEnd])
            output.append(tag)
            output.append(be(UInt32(value.count)))
            output.append(value)
            cursor = valueEnd
        }
        guard cursor == data.count else { throw ProductionC1Error.malformedCanonical }
        return output
    }

    private func be<T: FixedWidthInteger>(_ value: T) -> Data {
        var big = value.bigEndian
        return withUnsafeBytes(of: &big) { Data($0) }
    }
}

private final class FreshPairDurabilityFailureSwitch: @unchecked Sendable {
    private let lock = NSLock()
    private var enabled = false

    func enable() {
        lock.lock()
        enabled = true
        lock.unlock()
    }

    func isEnabled() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return enabled
    }
}

private actor FreshPairDurabilityAbortRecorder {
    private var count = 0

    func record() { count += 1 }
    func value() -> Int { count }
}
