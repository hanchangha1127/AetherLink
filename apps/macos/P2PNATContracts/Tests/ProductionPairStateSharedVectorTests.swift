import Foundation
import XCTest
@testable import P2PNATContracts

final class ProductionPairStateSharedVectorTests: XCTestCase {
    func testAuthorityAndEmptySnapshotMatchSharedCanonicalVectors() throws {
        let fixture = try loadFixture()
        XCTAssertEqual(fixture.schema, "aetherlink-production-pair-state-admission-v1-vectors")
        XCTAssertEqual(fixture.version, 1)
        XCTAssertEqual(fixture.magic, "ALS1")
        XCTAssertEqual(fixture.suite, ProductionSecureSessionContract.suite)
        XCTAssertEqual(fixture.profile, ProductionPairAuthorityState.profile)

        let authority = try makeAuthority(fixture.authority.input)
        let authorityBytes = try authority.canonicalBytes()
        XCTAssertEqual(authorityBytes.count, fixture.authority.expectedCanonicalByteCount)
        XCTAssertEqual(authorityBytes.hex, fixture.authority.expectedCanonicalHex)
        XCTAssertEqual(try authority.digestHex(), fixture.authority.expectedSha256Hex)
        XCTAssertEqual(try ProductionPairAuthorityState(canonicalBytes: authorityBytes), authority)

        let snapshot = try makeEmptySnapshot(fixture, authority: authority)
        let snapshotBytes = try snapshot.canonicalBytes()
        XCTAssertEqual(snapshotBytes.count, fixture.emptySnapshot.expectedCanonicalByteCount)
        XCTAssertEqual(snapshotBytes.hex, fixture.emptySnapshot.expectedCanonicalHex)
        XCTAssertEqual(try snapshot.digestHex(), fixture.emptySnapshot.expectedSha256Hex)
        XCTAssertEqual(try ProductionPairStateSnapshot(canonicalBytes: snapshotBytes), snapshot)

        let encoded = try JSONEncoder().encode(snapshot)
        XCTAssertEqual(try JSONDecoder().decode(ProductionPairStateSnapshot.self, from: encoded), snapshot)
    }

    func testLocalDirectAdmissionMatchesSharedSnapshotAndPermit() throws {
        let fixture = try loadFixture()
        let authority = try makeAuthority(fixture.authority.input)
        let snapshot = try makeEmptySnapshot(fixture, authority: authority)
        let route = try makeRoute(fixture.localDirectAdmission.routeInput)
        let transcript = try makeTranscript(fixture.localDirectAdmission.transcriptInput)
        let result = try ProductionPairStateAdmission.prepare(
            transcript: transcript,
            routeAuthorization: route,
            to: snapshot
        )
        let expected = fixture.localDirectAdmission

        XCTAssertEqual(try result.snapshot.canonicalBytes().count, expected.expectedSnapshotByteCount)
        XCTAssertEqual(try result.snapshot.canonicalBytes().hex, expected.expectedSnapshotCanonicalHex)
        XCTAssertEqual(try result.snapshot.digestHex(), expected.expectedSnapshotSha256Hex)
        XCTAssertEqual(result.bindingDigest, expected.expectedPermitBindingDigest)
        XCTAssertEqual(result.pairAuthorityDigest, try authority.digestHex())
        XCTAssertEqual(result.sessionId, transcript.sessionId)
        XCTAssertEqual(result.transcriptDigest, transcript.digestHex)
        XCTAssertEqual(result.routeAuthorizationDigest, try route.digestHex())
        XCTAssertEqual(result.previousPairSnapshotDigest, try snapshot.digestHex())
        XCTAssertEqual(result.pairSnapshotDigest, try result.snapshot.digestHex())
        XCTAssertEqual(result.snapshot.localRevision, 2)
        XCTAssertEqual(result.snapshot.consumedEntries.count, 1)
        XCTAssertEqual(
            try ProductionPairStateSnapshot(
                canonicalBytes: Data(strictHex: expected.expectedSnapshotCanonicalHex)
            ),
            result.snapshot
        )
    }

    func testGenericAdmissionRejectsAllP2PAuthorizationKindsUntilObject28() throws {
        let fixture = try loadFixture()
        let authority = try makeAuthority(fixture.authority.input)
        let snapshot = try makeEmptySnapshot(fixture, authority: authority)
        let baseTranscript = try makeTranscript(fixture.localDirectAdmission.transcriptInput)
        let routes: [ProductionRouteAuthorization] = [
            .p2pPublish(
                pairBindingDigest: authority.pairBindingDigest,
                pairEpoch: authority.pairEpoch,
                generation: authority.generation,
                candidateBatchDigest: String(repeating: "1", count: 64),
                publishCapabilityDigest: String(repeating: "2", count: 64)
            ),
            .p2pFetch(
                pairBindingDigest: authority.pairBindingDigest,
                pairEpoch: authority.pairEpoch,
                generation: authority.generation,
                candidateBatchDigest: String(repeating: "3", count: 64),
                fetchCapabilityDigest: String(repeating: "4", count: 64)
            ),
            .p2pDirect(
                pairBindingDigest: authority.pairBindingDigest,
                pairEpoch: authority.pairEpoch,
                generation: authority.generation,
                candidatePairDigest: String(repeating: "5", count: 64),
                pathValidationReceiptDigest: String(repeating: "6", count: 64),
                publishCapabilityDigest: String(repeating: "7", count: 64),
                fetchCapabilityDigest: String(repeating: "8", count: 64)
            ),
        ]
        for route in routes {
            let transcript = try ProductionSecureSessionTranscript(
                sessionId: baseTranscript.sessionId,
                pairBindingDigest: baseTranscript.pairBindingDigest,
                pairEpoch: baseTranscript.pairEpoch,
                clientIdentityFingerprint: baseTranscript.clientIdentityFingerprint,
                runtimeIdentityFingerprint: baseTranscript.runtimeIdentityFingerprint,
                clientEphemeralPublicKey: baseTranscript.clientEphemeralPublicKey,
                runtimeEphemeralPublicKey: baseTranscript.runtimeEphemeralPublicKey,
                clientNonce: baseTranscript.clientNonce,
                runtimeNonce: baseTranscript.runtimeNonce,
                generation: baseTranscript.generation,
                serviceConfigVersion: baseTranscript.serviceConfigVersion,
                keysetVersion: baseTranscript.keysetVersion,
                revocationCounter: baseTranscript.revocationCounter,
                routeKind: route.kind,
                routeAuthDigest: try route.digest().hex
            )
            assertPairError(.routeMismatch, route.kind.wireName) {
                _ = try ProductionPairStateAdmission.prepare(
                    transcript: transcript,
                    routeAuthorization: route,
                    to: snapshot
                )
            }
        }
    }

    func testSharedTransitionCaseExpectations() throws {
        let fixture = try loadFixture()
        let baseline = try makeAuthority(fixture.authority.input)
        let snapshot = try makeEmptySnapshot(fixture, authority: baseline)

        for vector in fixture.transitionCases {
            switch vector.mutation {
            case "genesis":
                let result = try ProductionPairStateMachine.apply(
                    try ProductionPairStateTransition(
                        expectedPreviousAuthorityDigest: nil,
                        nextAuthority: baseline
                    ),
                    to: nil
                )
                XCTAssertEqual(vector.expected, "applied", vector.id)
                XCTAssertEqual(result.disposition, .applied, vector.id)
                XCTAssertEqual(result.snapshot, snapshot, vector.id)
            case "idempotent":
                let result = try ProductionPairStateMachine.apply(
                    try ProductionPairStateTransition(
                        expectedPreviousAuthorityDigest: baseline.digestHex(),
                        nextAuthority: baseline
                    ),
                    to: snapshot
                )
                XCTAssertEqual(vector.expected, "idempotent", vector.id)
                XCTAssertEqual(result.disposition, .idempotent, vector.id)
                XCTAssertEqual(result.snapshot, snapshot, vector.id)
            case "generation_advance":
                let next = try replacing(
                    baseline,
                    generation: 8,
                    transitionId: String(repeating: "f", count: 64),
                    transitionRequestDigest: String(repeating: "1", count: 64),
                    acceptedReceiptDigest: String(repeating: "2", count: 64),
                    authorityRevision: 2
                )
                let result = try ProductionPairStateMachine.apply(
                    try ProductionPairStateTransition(
                        expectedPreviousAuthorityDigest: baseline.digestHex(),
                        nextAuthority: next
                    ),
                    to: snapshot
                )
                XCTAssertEqual(vector.expected, "applied", vector.id)
                XCTAssertEqual(result.disposition, .applied, vector.id)
                XCTAssertEqual(result.snapshot.authority.generation, 8, vector.id)
                XCTAssertEqual(result.snapshot.localRevision, 2, vector.id)
            case "generation_rollback":
                let next = try replacing(
                    baseline,
                    generation: 6,
                    transitionId: String(repeating: "f", count: 64),
                    transitionRequestDigest: String(repeating: "1", count: 64),
                    acceptedReceiptDigest: String(repeating: "2", count: 64),
                    authorityRevision: 2
                )
                XCTAssertEqual(vector.expected, "rejected", vector.id)
                assertPairError(.counterRollback, vector.id) {
                    _ = try ProductionPairStateMachine.apply(
                        ProductionPairStateTransition(
                            expectedPreviousAuthorityDigest: baseline.digestHex(),
                            nextAuthority: next
                        ),
                        to: snapshot
                    )
                }
            case "revoke":
                let next = try replacing(
                    baseline,
                    revocationCounter: 3,
                    status: .revoked,
                    transitionId: String(repeating: "f", count: 64),
                    transitionRequestDigest: String(repeating: "1", count: 64),
                    acceptedReceiptDigest: String(repeating: "2", count: 64),
                    authorityRevision: 2
                )
                let result = try ProductionPairStateMachine.apply(
                    try ProductionPairStateTransition(
                        expectedPreviousAuthorityDigest: baseline.digestHex(),
                        nextAuthority: next
                    ),
                    to: snapshot
                )
                XCTAssertEqual(vector.expected, "applied", vector.id)
                XCTAssertEqual(result.snapshot.authority.status, .revoked, vector.id)
            default:
                XCTFail("unknown transition mutation \(vector.mutation)")
            }
        }
    }

    func testTransitionHistoryUsesCanonicalSevenFieldEncodingAndRejectsLifetimeReuse() throws {
        let fixture = try loadFixture()
        let baseline = try makeAuthority(fixture.authority.input)
        let initial = try makeEmptySnapshot(fixture, authority: baseline)
        let second = try replacing(
            baseline,
            generation: baseline.generation + 1,
            transitionId: String(repeating: "f", count: 64),
            transitionRequestDigest: String(repeating: "1", count: 64),
            acceptedReceiptDigest: String(repeating: "2", count: 64),
            authorityRevision: baseline.authorityRevision + 1
        )
        let advanced = try ProductionPairStateMachine.apply(
            ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: baseline.digestHex(),
                nextAuthority: second
            ),
            to: initial
        ).snapshot

        let expectedHistory = [
            try ProductionPairTransitionHistoryEntry(
                transitionId: baseline.transitionId,
                transitionRequestDigest: baseline.transitionRequestDigest
            ),
        ]
        XCTAssertEqual(advanced.transitionHistory, expectedHistory)

        let canonical = try advanced.canonicalBytes()
        XCTAssertEqual(canonical.count, 734)
        XCTAssertEqual(
            try advanced.digestHex(),
            "bf32cef0254efcc882a4fc370192bd339ea7076833c1514a0e6958ebfa5d6b96"
        )
        var expectedTail = Data([6, 0, 0, 0, 4, 0, 0, 0, 1, 7, 0, 0, 0, 64])
        expectedTail.append(try Data(strictHex: baseline.transitionId))
        expectedTail.append(try Data(strictHex: baseline.transitionRequestDigest))
        XCTAssertEqual(Data(canonical.suffix(expectedTail.count)), expectedTail)
        XCTAssertEqual(try ProductionPairStateSnapshot(canonicalBytes: canonical), advanced)
        XCTAssertEqual(
            try JSONDecoder().decode(
                ProductionPairStateSnapshot.self,
                from: JSONEncoder().encode(advanced)
            ),
            advanced
        )

        let missingHistoryBody = Data(canonical.dropLast(69))
        assertPairError(.malformedCanonical, "six-field history") {
            _ = try ProductionPairStateSnapshot(canonicalBytes: missingHistoryBody)
        }

        let reused = try replacing(
            second,
            generation: second.generation + 1,
            transitionId: baseline.transitionId,
            transitionRequestDigest: String(repeating: "3", count: 64),
            acceptedReceiptDigest: String(repeating: "4", count: 64),
            authorityRevision: second.authorityRevision + 1
        )
        assertPairError(.transitionConflict, "historical transition id reuse") {
            _ = try ProductionPairStateMachine.apply(
                ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest: second.digestHex(),
                    nextAuthority: reused
                ),
                to: advanced
            )
        }
    }

    func testTransitionHistoryCapacityCoexistsWithReplayCapacityAndFailsClosed() throws {
        let fixture = try loadFixture()
        let baseline = try makeAuthority(fixture.authority.input)
        let sessions = try (1...ProductionPairStateContract.maxConsumedEntries).map { index in
            try ProductionPairConsumedSession(
                sessionId: String(format: "%032x", index),
                transcriptDigest: String(format: "%064x", index + 1_000)
            )
        }
        let history = try (1...ProductionPairStateContract.maxTransitionHistoryEntries).map { index in
            try ProductionPairTransitionHistoryEntry(
                transitionId: String(format: "%064x", index),
                transitionRequestDigest: String(format: "%064x", index + 10_000)
            )
        }
        let full = try ProductionPairStateSnapshot(
            authority: baseline,
            localRevision: 1,
            consumedEntries: sessions,
            transitionHistory: history
        )
        let fullBytes = try full.canonicalBytes()
        XCTAssertLessThanOrEqual(fullBytes.count, ProductionPairStateContract.maxSnapshotBytes)
        XCTAssertEqual(try ProductionPairStateSnapshot(canonicalBytes: fullBytes), full)

        let next = try replacing(
            baseline,
            generation: baseline.generation + 1,
            transitionId: String(repeating: "f", count: 64),
            transitionRequestDigest: String(repeating: "a", count: 64),
            acceptedReceiptDigest: String(repeating: "b", count: 64),
            authorityRevision: baseline.authorityRevision + 1
        )
        assertPairError(.transitionHistoryCapacityExhausted, "transition history capacity") {
            _ = try ProductionPairStateMachine.apply(
                ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest: baseline.digestHex(),
                    nextAuthority: next
                ),
                to: full
            )
        }
    }

    func testAdmissionPreservesTransitionHistory() throws {
        let fixture = try loadFixture()
        let baseline = try makeAuthority(fixture.authority.input)
        let history = [
            try ProductionPairTransitionHistoryEntry(
                transitionId: String(repeating: "f", count: 64),
                transitionRequestDigest: String(repeating: "1", count: 64)
            ),
        ]
        let snapshot = try ProductionPairStateSnapshot(
            authority: baseline,
            localRevision: 1,
            transitionHistory: history
        )
        let admitted = try ProductionPairStateAdmission.prepare(
            transcript: makeTranscript(fixture.localDirectAdmission.transcriptInput),
            routeAuthorization: makeRoute(fixture.localDirectAdmission.routeInput),
            to: snapshot
        ).snapshot

        XCTAssertEqual(admitted.transitionHistory, history)
        XCTAssertEqual(
            try ProductionPairStateSnapshot(canonicalBytes: admitted.canonicalBytes()),
            admitted
        )
    }

    func testEpochAdvanceFailsClosedUntilFreshPairProofContractExists() throws {
        let fixture = try loadFixture()
        let baseline = try makeAuthority(fixture.authority.input)
        let snapshot = try makeEmptySnapshot(fixture, authority: baseline)
        let nextEpoch = try replacing(
            baseline,
            pairEpoch: baseline.pairEpoch + 1,
            generation: baseline.generation + 1,
            transitionId: String(repeating: "f", count: 64),
            transitionRequestDigest: String(repeating: "1", count: 64),
            acceptedReceiptDigest: String(repeating: "2", count: 64),
            authorityRevision: baseline.authorityRevision + 1
        )

        assertPairError(.invalidEpochTransition, "epoch advance without fresh-pair proof") {
            _ = try ProductionPairStateMachine.apply(
                ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest: baseline.digestHex(),
                    nextAuthority: nextEpoch
                ),
                to: snapshot
            )
        }
    }

    func testSharedAdmissionAndMalformedCaseExpectations() throws {
        let fixture = try loadFixture()
        let baseline = try makeAuthority(fixture.authority.input)
        let empty = try makeEmptySnapshot(fixture, authority: baseline)
        let route = try makeRoute(fixture.localDirectAdmission.routeInput)
        let transcript = try makeTranscript(fixture.localDirectAdmission.transcriptInput)
        let admitted = try ProductionPairStateAdmission.prepare(
            transcript: transcript,
            routeAuthorization: route,
            to: empty
        ).snapshot

        for vector in fixture.admissionCases {
            switch vector.mutation {
            case "none":
                XCTAssertEqual(vector.expected, "accepted", vector.id)
                _ = try ProductionPairStateAdmission.prepare(
                    transcript: transcript,
                    routeAuthorization: route,
                    to: empty
                )
            case "replay":
                XCTAssertEqual(vector.expected, "rejected", vector.id)
                assertPairError(.replay, vector.id) {
                    _ = try ProductionPairStateAdmission.prepare(
                        transcript: transcript,
                        routeAuthorization: route,
                        to: admitted
                    )
                }
            case "revoked":
                let revoked = try ProductionPairStateSnapshot(
                    authority: replacing(baseline, status: .revoked),
                    localRevision: 1
                )
                XCTAssertEqual(vector.expected, "rejected", vector.id)
                assertPairError(.revoked, vector.id) {
                    _ = try ProductionPairStateAdmission.prepare(
                        transcript: transcript,
                        routeAuthorization: route,
                        to: revoked
                    )
                }
            case "persisted_epoch_mismatch":
                let future = try ProductionPairStateSnapshot(
                    authority: replacing(baseline, pairEpoch: 10),
                    localRevision: 1
                )
                XCTAssertEqual(vector.expected, "rejected", vector.id)
                assertPairError(.stateMismatch, vector.id) {
                    _ = try ProductionPairStateAdmission.prepare(
                        transcript: transcript,
                        routeAuthorization: route,
                        to: future
                    )
                }
            case "route_digest_mismatch":
                let wrongRoute = ProductionRouteAuthorization.localDirect(
                    pairBindingDigest: route.pairBindingDigest,
                    pairEpoch: route.pairEpoch,
                    nominatedPathReceiptDigest: String(repeating: "2", count: 64)
                )
                XCTAssertEqual(vector.expected, "rejected", vector.id)
                assertPairError(.routeMismatch, vector.id) {
                    _ = try ProductionPairStateAdmission.prepare(
                        transcript: transcript,
                        routeAuthorization: wrongRoute,
                        to: empty
                    )
                }
            case "capacity":
                let entries = try (1...ProductionPairStateContract.maxConsumedEntries).map { index in
                    try ProductionPairConsumedSession(
                        sessionId: String(format: "%032x", index),
                        transcriptDigest: String(format: "%064x", index + 1_000)
                    )
                }
                let full = try ProductionPairStateSnapshot(
                    authority: baseline,
                    localRevision: 1,
                    consumedEntries: entries
                )
                XCTAssertEqual(vector.expected, "rejected", vector.id)
                assertPairError(.replayCapacityExceeded, vector.id) {
                    _ = try ProductionPairStateAdmission.prepare(
                        transcript: transcript,
                        routeAuthorization: route,
                        to: full
                    )
                }
            case "malformed_authority":
                var malformed = try baseline.canonicalBytes()
                malformed.append(0)
                XCTAssertEqual(vector.expected, "rejected", vector.id)
                XCTAssertThrowsError(try ProductionPairAuthorityState(canonicalBytes: malformed))
            default:
                XCTFail("unknown admission mutation \(vector.mutation)")
            }
        }
    }

    private func makeAuthority(_ input: AuthorityInput) throws -> ProductionPairAuthorityState {
        guard let status = ProductionPairAuthorityStatus(rawValue: input.status) else {
            throw FixtureError.invalidFixture
        }
        return try ProductionPairAuthorityState(
            pairBindingDigest: input.pairBindingDigest,
            pairEpoch: input.pairEpoch,
            clientIdentityFingerprint: input.clientIdentityFingerprint,
            runtimeIdentityFingerprint: input.runtimeIdentityFingerprint,
            generation: input.generation,
            serviceConfigVersion: input.serviceConfigVersion,
            keysetVersion: input.keysetVersion,
            revocationCounter: input.revocationCounter,
            protocolFloor: input.protocolFloor,
            status: status,
            transitionId: input.transitionId,
            transitionRequestDigest: input.transitionRequestDigest,
            acceptedReceiptDigest: input.acceptedReceiptDigest,
            authorityRevision: input.authorityRevision
        )
    }

    private func makeEmptySnapshot(
        _ fixture: Fixture,
        authority: ProductionPairAuthorityState
    ) throws -> ProductionPairStateSnapshot {
        try ProductionPairStateSnapshot(
            authority: authority,
            localRevision: fixture.emptySnapshot.localRevision
        )
    }

    private func makeRoute(_ input: RouteInput) throws -> ProductionRouteAuthorization {
        guard input.suite == ProductionSecureSessionContract.suite else {
            throw FixtureError.invalidFixture
        }
        return .localDirect(
            pairBindingDigest: input.pairBindingDigest,
            pairEpoch: input.pairEpoch,
            nominatedPathReceiptDigest: input.nominatedPathReceiptDigest
        )
    }

    private func makeTranscript(_ input: TranscriptInput) throws -> ProductionSecureSessionTranscript {
        guard input.suite == ProductionSecureSessionContract.suite,
              input.clientRole == "client",
              input.runtimeRole == "runtime",
              input.protocolVersion == ProductionSecureSessionTranscript.protocolVersion,
              input.minimumProtocolVersion == ProductionSecureSessionTranscript.minimumProtocolVersion,
              input.cryptographicProfile == ProductionSecureSessionTranscript.profile,
              let kind = ProductionRouteAuthorizationKind(wireName: input.routeKind) else {
            throw FixtureError.invalidFixture
        }
        return try ProductionSecureSessionTranscript(
            sessionId: input.sessionId,
            pairBindingDigest: input.pairBindingDigest,
            pairEpoch: input.pairEpoch,
            clientIdentityFingerprint: input.clientIdentityFingerprint,
            runtimeIdentityFingerprint: input.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: Data(strictHex: input.clientEphemeralPublicKeyHex),
            runtimeEphemeralPublicKey: Data(strictHex: input.runtimeEphemeralPublicKeyHex),
            clientNonce: input.clientNonce,
            runtimeNonce: input.runtimeNonce,
            generation: input.generation,
            serviceConfigVersion: input.serviceConfigVersion,
            keysetVersion: input.keysetVersion,
            revocationCounter: input.revocationCounter,
            routeKind: kind,
            routeAuthDigest: input.routeAuthorizationDigest
        )
    }

    private func replacing(
        _ value: ProductionPairAuthorityState,
        pairEpoch: UInt64? = nil,
        generation: UInt64? = nil,
        revocationCounter: UInt64? = nil,
        status: ProductionPairAuthorityStatus? = nil,
        transitionId: String? = nil,
        transitionRequestDigest: String? = nil,
        acceptedReceiptDigest: String? = nil,
        authorityRevision: UInt64? = nil
    ) throws -> ProductionPairAuthorityState {
        try ProductionPairAuthorityState(
            pairBindingDigest: value.pairBindingDigest,
            pairEpoch: pairEpoch ?? value.pairEpoch,
            clientIdentityFingerprint: value.clientIdentityFingerprint,
            runtimeIdentityFingerprint: value.runtimeIdentityFingerprint,
            generation: generation ?? value.generation,
            serviceConfigVersion: value.serviceConfigVersion,
            keysetVersion: value.keysetVersion,
            revocationCounter: revocationCounter ?? value.revocationCounter,
            protocolFloor: value.protocolFloor,
            status: status ?? value.status,
            transitionId: transitionId ?? value.transitionId,
            transitionRequestDigest: transitionRequestDigest ?? value.transitionRequestDigest,
            acceptedReceiptDigest: acceptedReceiptDigest ?? value.acceptedReceiptDigest,
            authorityRevision: authorityRevision ?? value.authorityRevision
        )
    }

    private func assertPairError(
        _ expected: ProductionPairStateError,
        _ id: String,
        _ body: () throws -> Void
    ) {
        XCTAssertThrowsError(try body(), id) { error in
            XCTAssertEqual(error as? ProductionPairStateError, expected, id)
        }
    }

    private func loadFixture() throws -> Fixture {
        let relative = "shared/protocol/fixtures/production-pair-state-admission-v1-vectors.json"
        let starts = [
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true),
            URL(fileURLWithPath: #filePath).deletingLastPathComponent(),
        ]
        for start in starts {
            var directory = start.standardizedFileURL
            while true {
                let candidate = directory.appendingPathComponent(relative)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    return try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: candidate))
                }
                let parent = directory.deletingLastPathComponent()
                if parent.path == directory.path { break }
                directory = parent
            }
        }
        throw FixtureError.notFound
    }
}

private enum FixtureError: Error { case notFound, invalidFixture, invalidHex }

private struct Fixture: Decodable {
    let schema: String
    let version: Int
    let magic: String
    let suite: String
    let profile: String
    let authority: AuthorityVector
    let emptySnapshot: SnapshotVector
    let localDirectAdmission: AdmissionVector
    let transitionCases: [CaseVector]
    let admissionCases: [CaseVector]
}

private struct AuthorityVector: Decodable {
    let input: AuthorityInput
    let expectedCanonicalByteCount: Int
    let expectedCanonicalHex: String
    let expectedSha256Hex: String
}

private struct AuthorityInput: Decodable {
    let pairBindingDigest: String
    let pairEpoch: UInt64
    let clientIdentityFingerprint: String
    let runtimeIdentityFingerprint: String
    let generation: UInt64
    let serviceConfigVersion: UInt64
    let keysetVersion: UInt64
    let revocationCounter: UInt64
    let protocolFloor: UInt32
    let status: String
    let transitionId: String
    let transitionRequestDigest: String
    let acceptedReceiptDigest: String
    let authorityRevision: UInt64
}

private struct SnapshotVector: Decodable {
    let localRevision: UInt64
    let expectedCanonicalByteCount: Int
    let expectedCanonicalHex: String
    let expectedSha256Hex: String
}

private struct AdmissionVector: Decodable {
    let routeInput: RouteInput
    let transcriptInput: TranscriptInput
    let expectedSnapshotByteCount: Int
    let expectedSnapshotCanonicalHex: String
    let expectedSnapshotSha256Hex: String
    let expectedPermitBindingDigest: String
}

private struct CaseVector: Decodable { let id: String; let mutation: String; let expected: String }

private struct RouteInput: Decodable {
    let suite: String
    let pairBindingDigest: String
    let pairEpoch: UInt64
    let nominatedPathReceiptDigest: String
}

private struct TranscriptInput: Decodable {
    let suite: String
    let sessionId: String
    let pairBindingDigest: String
    let pairEpoch: UInt64
    let clientIdentityFingerprint: String
    let runtimeIdentityFingerprint: String
    let clientRole: String
    let runtimeRole: String
    let clientEphemeralPublicKeyHex: String
    let runtimeEphemeralPublicKeyHex: String
    let clientNonce: String
    let runtimeNonce: String
    let generation: UInt64
    let serviceConfigVersion: UInt64
    let keysetVersion: UInt64
    let revocationCounter: UInt64
    let protocolVersion: UInt32
    let minimumProtocolVersion: UInt32
    let cryptographicProfile: String
    let routeKind: String
    let routeAuthorizationDigest: String
}

private extension Data {
    init(strictHex: String) throws {
        guard !strictHex.isEmpty, strictHex.count.isMultiple(of: 2),
              strictHex.allSatisfy({ $0.isNumber || ("a"..."f").contains(String($0)) }) else {
            throw FixtureError.invalidHex
        }
        self.init()
        var index = strictHex.startIndex
        while index < strictHex.endIndex {
            let next = strictHex.index(index, offsetBy: 2)
            guard let byte = UInt8(strictHex[index..<next], radix: 16) else {
                throw FixtureError.invalidHex
            }
            append(byte)
            index = next
        }
    }

    var hex: String { map { String(format: "%02x", $0) }.joined() }
}
