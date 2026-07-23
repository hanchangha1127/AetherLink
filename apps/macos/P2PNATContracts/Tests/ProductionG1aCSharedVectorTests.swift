import CryptoKit
import Foundation
import XCTest
@testable import P2PNATContracts

final class ProductionG1aCSharedVectorTests: XCTestCase {
    func testSchemaConstantsCanonicalObjectsAndFixedKeysetSignature() throws {
        let fixture = try SharedG1aCFixture.load()

        XCTAssertEqual(try fixture.string("schema"), "aetherlink-production-g1a-c-v1-vectors")
        XCTAssertEqual(try fixture.uint64("version"), 1)
        XCTAssertEqual(try fixture.string("magic"), "ALS1")
        XCTAssertEqual(try fixture.string("suite"), ProductionC1Contract.suite)
        XCTAssertEqual(try fixture.string("signatureAlgorithm"), ProductionC1Contract.signatureAlgorithm)
        XCTAssertEqual(try fixture.constant("maximumClockSkewMs"), ProductionC1Contract.maximumClockSkewMs)
        XCTAssertEqual(try fixture.constant("maximumKeysetLifetimeMs"), ProductionC1Contract.maximumKeysetLifetimeMs)
        XCTAssertEqual(try fixture.constant("maximumStatusLifetimeMs"), ProductionC1Contract.maximumStatusLifetimeMs)
        XCTAssertEqual(try fixture.constant("maximumFreshPairLifetimeMs"), ProductionC1Contract.maximumFreshPairLifetimeMs)
        XCTAssertEqual(try fixture.constant("maximumRouteLifetimeMs"), ProductionC1Contract.maximumRouteLifetimeMs)
        XCTAssertEqual(try fixture.uint64Array("reservedObjectTypes"), [19])
        XCTAssertEqual(fixture.objectNames.count, 18)
        XCTAssertEqual(fixture.objectNames.filter { fixture.coverage($0) == "semantic" }.count, 14)
        XCTAssertEqual(fixture.objectNames.filter { fixture.coverage($0) == "codec_only" }.count, 4)

        let expectedTypes: [String: UInt8] = [
            "previousAuthority": 8,
            "previousSnapshot": 9,
            "serviceKeyset": 10,
            "freshPairProof": 12,
            "nextAuthority": 8,
            "pairStatus": 11,
            "nextSnapshot": 9,
            "preauthorizationSessionContext": 18,
            "turnConnector": 16,
            "routePlan": 14,
            "routeCapability": 13,
            "turnRouteAuthorization": 21,
            "secureSessionTranscript": 7,
            "admittedSnapshot": 9,
            "p2pConnector": 15,
            "sealedRelayConnector": 17,
            "p2pRouteAuthorization": 20,
            "sealedRelayRouteAuthorization": 22,
        ]
        XCTAssertEqual(Set(fixture.objectNames), Set(expectedTypes.keys))
        for name in expectedTypes.keys.sorted() {
            let canonical = try fixture.canonical(name)
            XCTAssertEqual(canonical[canonical.startIndex + 4], expectedTypes[name], name)
            XCTAssertEqual(canonical.count, try fixture.canonicalByteCount(name), name)
            XCTAssertEqual(sha256Hex(canonical), try fixture.canonicalDigest(name), name)
            XCTAssertEqual(try roundTrip(name: name, canonical: canonical), canonical, name)
        }

        for name in fixture.keyNames {
            let publicKey = try fixture.publicKey(name)
            XCTAssertEqual(publicKey.x963Representation, try fixture.keyData(name, "publicKeyX963Hex"), name)
            XCTAssertEqual(publicKey.derRepresentation, try fixture.keyData(name, "publicKeySPKIDERHex"), name)
            XCTAssertEqual(sha256Hex(publicKey.derRepresentation), try fixture.keyString(name, "keyId"), name)
        }

        let keyset = try ProductionC1ServiceKeyset(canonicalBytes: fixture.canonical("serviceKeyset"))
        let verified = try ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            expectedServiceIdDigest: keyset.serviceIdDigest,
            pinnedRootPublicKey: fixture.publicKey("root"),
            minimumAcceptedKeysetVersion: try fixture.constant("minimumAcceptedKeysetVersion"),
            nowMs: try fixture.constant("nowMs")
        )
        XCTAssertEqual(verified.keyset, keyset)

        let mutationIds = Set(try fixture.mutationIds())
        XCTAssertEqual(mutationIds.count, 16)
        XCTAssertTrue([
            "reordered_tag", "trailing_byte", "high_s", "rollback_floor",
            "swapped_fresh_signatures", "wrong_security_context", "wrong_connector_secret",
            "expired_plan_reuse", "admission_replay",
        ].allSatisfy(mutationIds.contains))
    }

    func testFixedFreshPairSignaturesApplyAndIdempotency() throws {
        let fixture = try SharedG1aCFixture.load()
        let chain = try verifiedFreshChain(fixture)
        let now = try fixture.constant("nowMs")

        let previousCommitments = try fixture.dictionary("derived", "previousRecoveryCommitments")
        XCTAssertEqual(
            chain.commitments.endpointTrafficSecretCommitment,
            try fixture.string(in: previousCommitments, "endpointTrafficSecretCommitment")
        )
        XCTAssertEqual(
            chain.commitments.routeTokenSeedCommitment,
            try fixture.string(in: previousCommitments, "routeTokenSeedCommitment")
        )
        XCTAssertEqual(
            chain.commitments.endpointTrafficSecretReuseDigest,
            try fixture.string(in: previousCommitments, "endpointTrafficSecretReuseDigest")
        )
        XCTAssertEqual(
            chain.commitments.routeTokenSeedReuseDigest,
            try fixture.string(in: previousCommitments, "routeTokenSeedReuseDigest")
        )
        XCTAssertEqual(chain.proof.transitionRequestDigest, try fixture.derived("freshPairTransitionRequestDigest"))
        XCTAssertEqual(try chain.proof.digestHex(), try fixture.derived("freshPairProofDigest"))

        let applied = try ProductionC1FreshPairStateMachine.apply(
            chain.transition,
            to: chain.current,
            nowMs: now
        )
        XCTAssertEqual(applied.disposition, .applied)
        XCTAssertEqual(try applied.snapshot.canonicalBytes(), try fixture.canonical("nextSnapshot"))
        XCTAssertEqual(try applied.snapshot.digestHex(), try fixture.derived("nextSnapshotDigest"))
        XCTAssertEqual(applied.snapshot, chain.transition.applyPreparation.nextSnapshot)

        let idempotent = try ProductionC1FreshPairStateMachine.apply(
            chain.transition,
            to: applied.snapshot,
            nowMs: now
        )
        XCTAssertEqual(idempotent.disposition, .idempotent)
        XCTAssertEqual(idempotent.snapshot, applied.snapshot)

        assertC1Error(.keysetRollback) {
            _ = try ProductionC1Verifier.verifyServiceKeyset(
                chain.verifiedKeyset.keyset,
                expectedServiceIdDigest: chain.verifiedKeyset.keyset.serviceIdDigest,
                pinnedRootPublicKey: try fixture.publicKey("root"),
                minimumAcceptedKeysetVersion: chain.verifiedKeyset.keyset.keysetVersion + 1,
                nowMs: now
            )
        }

        var reordered = try fixture.canonical("serviceKeyset")
        reordered[reordered.startIndex + 6] = 2
        assertC1Error(.malformedCanonical) {
            _ = try ProductionC1ServiceKeyset(canonicalBytes: reordered)
        }

        var trailing = try fixture.canonical("turnConnector")
        trailing.append(0)
        assertC1Error(.malformedCanonical) {
            _ = try ProductionC1RouteConnectorMaterial(canonicalBytes: trailing)
        }

        let highS = try makeHighS(chain.verifiedKeyset.keyset.rootSignature)
        let highSKeyset = try replacingTLVField(
            in: fixture.canonical("serviceKeyset"),
            tag: 11,
            with: highS
        )
        assertC1Error(.highS) {
            _ = try ProductionC1ServiceKeyset(canonicalBytes: highSKeyset)
        }

        let qrMutation = try replacingTLVField(
            in: fixture.canonical("freshPairProof"),
            tag: 21,
            with: Data(String(repeating: "a", count: 64).utf8)
        )
        let qrMutatedProof = try ProductionC1FreshPairProof(canonicalBytes: qrMutation)
        assertC1Error(.invalidSignature) {
            _ = try ProductionC1Verifier.verifyFreshPairProof(
                qrMutatedProof,
                acceptedBy: chain.verifiedStatus,
                current: chain.current,
                currentCommitments: chain.commitments,
                survivorPublicKey: try fixture.publicKey("survivorRuntimeIdentity"),
                replacementPublicKey: try fixture.publicKey("replacementClientIdentity"),
                nowMs: now
            )
        }

        let swappedBytes = try replacingTLVFields(
            in: fixture.canonical("freshPairProof"),
            replacements: [35: chain.proof.replacementSignature, 36: chain.proof.survivorSignature]
        )
        let swapped = try ProductionC1FreshPairProof(canonicalBytes: swappedBytes)
        assertC1Error(.invalidSignature) {
            _ = try ProductionC1Verifier.verifyFreshPairProof(
                swapped,
                acceptedBy: chain.verifiedStatus,
                current: chain.current,
                currentCommitments: chain.commitments,
                survivorPublicKey: try fixture.publicKey("survivorRuntimeIdentity"),
                replacementPublicKey: try fixture.publicKey("replacementClientIdentity"),
                nowMs: now
            )
        }

        let wrongCommitments = try ProductionC1RecoveryCommitments.currentToken(
            pairBindingDigest: chain.current.authority.pairBindingDigest,
            endpointTrafficSecret: Data(repeating: 0x21, count: 32),
            routeTokenSeed: Data(repeating: 0x22, count: 32)
        )
        assertC1Error(.invalidFreshPair) {
            _ = try ProductionC1Verifier.verifyFreshPairProof(
                chain.proof,
                acceptedBy: chain.verifiedStatus,
                current: chain.current,
                currentCommitments: wrongCommitments,
                survivorPublicKey: try fixture.publicKey("survivorRuntimeIdentity"),
                replacementPublicKey: try fixture.publicKey("replacementClientIdentity"),
                nowMs: now
            )
        }

        assertC1Error(.expired) {
            _ = try ProductionC1FreshPairStateMachine.apply(
                chain.transition,
                to: chain.current,
                nowMs: chain.proof.expiresAtMs
            )
        }
    }

    func testFixedTurnRouteChainConnectorBindingAndDurableAdmission() throws {
        let fixture = try SharedG1aCFixture.load()
        let fresh = try verifiedFreshChain(fixture)
        let now = try fixture.constant("nowMs")
        let nextSnapshot = try ProductionC1FreshPairStateMachine.apply(
            fresh.transition,
            to: fresh.current,
            nowMs: now
        ).snapshot
        let authority = nextSnapshot.authority

        let context = try ProductionC1PreauthorizationSessionContext(
            canonicalBytes: fixture.canonical("preauthorizationSessionContext")
        )
        let connector = try ProductionC1RouteConnectorMaterial(
            canonicalBytes: fixture.canonical("turnConnector")
        )
        let plan = try ProductionC1RoutePlanClaims(canonicalBytes: fixture.canonical("routePlan"))
        let capability = try ProductionC1RouteCapability(
            canonicalBytes: fixture.canonical("routeCapability")
        )
        XCTAssertEqual(plan.connector, connector)
        XCTAssertEqual(context.digestHex(), try fixture.derived("preauthorizationSessionContextDigest"))
        XCTAssertEqual(try plan.digestHex(), try fixture.derived("routePlanClaimsDigest"))
        XCTAssertEqual(try capability.digestHex(), try fixture.derived("routeCapabilityDigest"))

        let verifiedPlan = try ProductionC1Verifier.verifyRoutePlan(
            claims: plan,
            capability: capability,
            securityContext: context,
            authority: authority,
            verifiedKeyset: fresh.verifiedKeyset,
            nowMs: now
        )
        let routeHandle = try fixture.syntheticString("routeHandle")
        let nonce = try fixture.syntheticString("connectorNonce")
        let secret = try fixture.syntheticData("connectorSecretHex")
        let connectorInput = try ProductionC1Verifier.verifyConnectorInput(
            for: verifiedPlan,
            routeHandle: routeHandle,
            nonce: nonce,
            secret: secret,
            nowMs: now
        )
        XCTAssertEqual(
            connectorInput.commitmentDigest,
            try fixture.derived("connectorInputCommitmentDigest")
        )

        let authorization = try ProductionC1Verifier.makeRouteAuthorization(
            for: verifiedPlan,
            nowMs: now
        )
        XCTAssertEqual(authorization.canonicalBytes, try fixture.canonical("turnRouteAuthorization"))
        XCTAssertEqual(authorization.digestHex, try fixture.derived("turnRouteAuthorizationDigest"))

        let transcript = try ProductionSecureSessionTranscript(
            canonicalBytes: fixture.canonical("secureSessionTranscript")
        )
        XCTAssertEqual(try ProductionC1PreauthorizationSessionContext(transcript: transcript), context)
        XCTAssertEqual(transcript.routeAuthDigest, authorization.digestHex)
        let binding = try ProductionC1Verifier.verifyTranscriptBinding(
            transcript: transcript,
            authorization: authorization,
            verifiedPlan: verifiedPlan,
            connectorInput: connectorInput,
            authority: authority,
            nowMs: now
        )
        let admitted = try ProductionC1PairStateAdmission.prepare(
            binding: binding,
            to: nextSnapshot,
            nowMs: now
        )
        XCTAssertEqual(try admitted.snapshot.canonicalBytes(), try fixture.canonical("admittedSnapshot"))
        XCTAssertEqual(try admitted.snapshot.digestHex(), try fixture.derived("admittedSnapshotDigest"))
        XCTAssertEqual(admitted.bindingDigest, try fixture.derived("durableAdmissionPermitDigest"))
        XCTAssertEqual(admitted.pairAuthorityDigest, try authority.digestHex())
        XCTAssertEqual(admitted.sessionId, transcript.sessionId)
        XCTAssertEqual(admitted.transcriptDigest, transcript.digestHex)
        XCTAssertEqual(admitted.routeAuthorizationDigest, authorization.digestHex)
        XCTAssertEqual(admitted.routeCapabilityDigest, verifiedPlan.capabilityDigest)
        XCTAssertEqual(admitted.routePlanClaimsDigest, verifiedPlan.claimsDigest)
        XCTAssertEqual(admitted.connectorInputCommitmentDigest, connectorInput.commitmentDigest)
        XCTAssertEqual(admitted.previousPairSnapshotDigest, try nextSnapshot.digestHex())
        XCTAssertEqual(admitted.pairSnapshotDigest, try admitted.snapshot.digestHex())
        XCTAssertEqual(admitted.effectiveNotBeforeMs, plan.notBeforeMs)
        XCTAssertEqual(admitted.expiresAtMs, plan.expiresAtMs)

        let alteredContext = try ProductionC1PreauthorizationSessionContext(
            sessionId: String(repeating: "d", count: 32),
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
            routeKind: context.routeKind
        )
        assertC1Error(.routeMismatch) {
            _ = try ProductionC1Verifier.verifyRoutePlan(
                claims: plan,
                capability: capability,
                securityContext: alteredContext,
                authority: authority,
                verifiedKeyset: fresh.verifiedKeyset,
                nowMs: now
            )
        }

        assertC1Error(.routeMismatch) {
            _ = try ProductionC1Verifier.verifyConnectorInput(
                for: verifiedPlan,
                routeHandle: routeHandle,
                nonce: nonce,
                secret: Data(repeating: 0x5b, count: 32),
                nowMs: now
            )
        }

        let wrongRouteDigestTranscript = try ProductionSecureSessionTranscript(
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
            routeKind: transcript.routeKind,
            routeAuthDigest: context.digestHex()
        )
        assertC1Error(.routeMismatch) {
            _ = try ProductionC1Verifier.verifyTranscriptBinding(
                transcript: wrongRouteDigestTranscript,
                authorization: authorization,
                verifiedPlan: verifiedPlan,
                connectorInput: connectorInput,
                authority: authority,
                nowMs: now
            )
        }

        assertC1Error(.expired) {
            _ = try ProductionC1Verifier.makeRouteAuthorization(
                for: verifiedPlan,
                nowMs: plan.expiresAtMs
            )
        }
        assertPairStateError(.replay) {
            _ = try ProductionC1PairStateAdmission.prepare(
                binding: binding,
                to: admitted.snapshot,
                nowMs: now
            )
        }
    }

    private struct FreshChain {
        let verifiedKeyset: VerifiedProductionC1ServiceKeyset
        let current: ProductionPairStateSnapshot
        let proof: ProductionC1FreshPairProof
        let verifiedStatus: VerifiedProductionC1PairStatus
        let commitments: ProductionC1CurrentRecoveryCommitments
        let transition: VerifiedProductionC1FreshPairTransition
    }

    private func verifiedFreshChain(_ fixture: SharedG1aCFixture) throws -> FreshChain {
        let now = try fixture.constant("nowMs")
        let keyset = try ProductionC1ServiceKeyset(canonicalBytes: fixture.canonical("serviceKeyset"))
        let verifiedKeyset = try ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            expectedServiceIdDigest: keyset.serviceIdDigest,
            pinnedRootPublicKey: fixture.publicKey("root"),
            minimumAcceptedKeysetVersion: try fixture.constant("minimumAcceptedKeysetVersion"),
            nowMs: now
        )
        let current = try ProductionPairStateSnapshot(canonicalBytes: fixture.canonical("previousSnapshot"))
        let proof = try ProductionC1FreshPairProof(canonicalBytes: fixture.canonical("freshPairProof"))
        let status = try ProductionC1PairStatus(canonicalBytes: fixture.canonical("pairStatus"))
        let verifiedStatus = try ProductionC1Verifier.verifyPairStatus(
            status,
            expectedServiceIdDigest: keyset.serviceIdDigest,
            expectedRequesterRole: .runtime,
            expectedRequestNonce: status.requestNonce,
            current: current,
            verifiedKeyset: verifiedKeyset,
            nowMs: now
        )
        let commitments = try ProductionC1RecoveryCommitments.currentToken(
            pairBindingDigest: current.authority.pairBindingDigest,
            endpointTrafficSecret: fixture.syntheticData("previousEndpointTrafficSecretHex"),
            routeTokenSeed: fixture.syntheticData("previousRouteTokenSeedHex")
        )
        let transition = try ProductionC1Verifier.verifyFreshPairProof(
            proof,
            acceptedBy: verifiedStatus,
            current: current,
            currentCommitments: commitments,
            survivorPublicKey: fixture.publicKey("survivorRuntimeIdentity"),
            replacementPublicKey: fixture.publicKey("replacementClientIdentity"),
            nowMs: now
        )
        return FreshChain(
            verifiedKeyset: verifiedKeyset,
            current: current,
            proof: proof,
            verifiedStatus: verifiedStatus,
            commitments: commitments,
            transition: transition
        )
    }

    private func roundTrip(name: String, canonical: Data) throws -> Data {
        switch name {
        case "secureSessionTranscript":
            return try ProductionSecureSessionTranscript(canonicalBytes: canonical).canonicalBytes()
        case "previousAuthority", "nextAuthority":
            return try ProductionPairAuthorityState(canonicalBytes: canonical).canonicalBytes()
        case "previousSnapshot", "nextSnapshot", "admittedSnapshot":
            return try ProductionPairStateSnapshot(canonicalBytes: canonical).canonicalBytes()
        case "serviceKeyset":
            return try ProductionC1ServiceKeyset(canonicalBytes: canonical).canonicalBytes()
        case "pairStatus":
            return try ProductionC1PairStatus(canonicalBytes: canonical).canonicalBytes()
        case "freshPairProof":
            return try ProductionC1FreshPairProof(canonicalBytes: canonical).canonicalBytes()
        case "routeCapability":
            return try ProductionC1RouteCapability(canonicalBytes: canonical).canonicalBytes()
        case "routePlan":
            return try ProductionC1RoutePlanClaims(canonicalBytes: canonical).canonicalBytes()
        case "p2pConnector", "turnConnector", "sealedRelayConnector":
            return try ProductionC1RouteConnectorMaterial(canonicalBytes: canonical).canonicalBytes()
        case "preauthorizationSessionContext":
            return try ProductionC1PreauthorizationSessionContext(canonicalBytes: canonical).canonicalBytes()
        case "p2pRouteAuthorization", "turnRouteAuthorization", "sealedRelayRouteAuthorization":
            return try ProductionC1RouteAuthorization(canonicalBytes: canonical).canonicalBytes()
        default:
            throw SharedG1aCFixtureError.invalidValue("unknown object \(name)")
        }
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

    private func replacingTLVField(in data: Data, tag: UInt8, with replacement: Data) throws -> Data {
        try replacingTLVFields(in: data, replacements: [tag: replacement])
    }

    private func replacingTLVFields(
        in data: Data,
        replacements: [UInt8: Data]
    ) throws -> Data {
        guard data.count >= 6 else { throw SharedG1aCFixtureError.invalidValue("short TLV") }
        var output = Data(data.prefix(6))
        var cursor = 6
        while cursor < data.count {
            guard cursor + 5 <= data.count else {
                throw SharedG1aCFixtureError.invalidValue("short TLV header")
            }
            let tag = data[cursor]
            let length = data[(cursor + 1)..<(cursor + 5)].reduce(UInt32(0)) {
                ($0 << 8) | UInt32($1)
            }
            let valueStart = cursor + 5
            let valueEnd = valueStart + Int(length)
            guard valueEnd <= data.count else {
                throw SharedG1aCFixtureError.invalidValue("short TLV value")
            }
            let value = replacements[tag] ?? Data(data[valueStart..<valueEnd])
            output.append(tag)
            var size = UInt32(value.count).bigEndian
            withUnsafeBytes(of: &size) { output.append(contentsOf: $0) }
            output.append(value)
            cursor = valueEnd
        }
        return output
    }

    private func sha256Hex(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }
}

private enum SharedG1aCFixtureError: Error {
    case notFound
    case invalidValue(String)
    case invalidHex(String)
}

private struct SharedG1aCFixture {
    let root: [String: Any]

    static func load() throws -> Self {
        let relative = "shared/protocol/fixtures/production-g1a-c-v1-vectors.json"
        let starts = [
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true),
            URL(fileURLWithPath: #filePath).deletingLastPathComponent(),
        ]
        for start in starts {
            var directory = start.standardizedFileURL
            while true {
                let candidate = directory.appendingPathComponent(relative)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    let value = try JSONSerialization.jsonObject(with: Data(contentsOf: candidate))
                    guard let root = value as? [String: Any] else {
                        throw SharedG1aCFixtureError.invalidValue("root")
                    }
                    return Self(root: root)
                }
                let parent = directory.deletingLastPathComponent()
                if parent.path == directory.path { break }
                directory = parent
            }
        }
        throw SharedG1aCFixtureError.notFound
    }

    var objectNames: [String] {
        ((try? dictionary("objects")) ?? [:]).keys.sorted()
    }

    var keyNames: [String] {
        ((try? dictionary("keys")) ?? [:]).keys.sorted()
    }

    func string(_ key: String) throws -> String {
        try string(in: root, key)
    }

    func uint64(_ key: String) throws -> UInt64 {
        try uint64(in: root, key)
    }

    func uint64Array(_ key: String) throws -> [UInt64] {
        guard let values = root[key] as? [NSNumber] else {
            throw SharedG1aCFixtureError.invalidValue(key)
        }
        return values.map(\.uint64Value)
    }

    func constant(_ key: String) throws -> UInt64 {
        try uint64(in: dictionary("constants"), key)
    }

    func syntheticString(_ key: String) throws -> String {
        try string(in: dictionary("syntheticMaterials"), key)
    }

    func syntheticData(_ key: String) throws -> Data {
        try decodeHex(syntheticString(key))
    }

    func derived(_ key: String) throws -> String {
        try string(in: dictionary("derived"), key)
    }

    func dictionary(_ keys: String...) throws -> [String: Any] {
        var value: Any = root
        for key in keys {
            guard let dictionary = value as? [String: Any], let next = dictionary[key] else {
                throw SharedG1aCFixtureError.invalidValue(keys.joined(separator: "."))
            }
            value = next
        }
        guard let result = value as? [String: Any] else {
            throw SharedG1aCFixtureError.invalidValue(keys.joined(separator: "."))
        }
        return result
    }

    func string(in dictionary: [String: Any], _ key: String) throws -> String {
        guard let value = dictionary[key] as? String else {
            throw SharedG1aCFixtureError.invalidValue(key)
        }
        return value
    }

    func coverage(_ name: String) -> String? {
        guard let record = try? dictionary("objects", name) else { return nil }
        return try? string(in: record, "coverage")
    }

    func canonical(_ name: String) throws -> Data {
        try decodeHex(string(in: dictionary("objects", name), "expectedCanonicalHex"))
    }

    func canonicalByteCount(_ name: String) throws -> Int {
        Int(try uint64(in: dictionary("objects", name), "expectedCanonicalByteCount"))
    }

    func canonicalDigest(_ name: String) throws -> String {
        try string(in: dictionary("objects", name), "expectedSha256Hex")
    }

    func publicKey(_ name: String) throws -> P256.Signing.PublicKey {
        try P256.Signing.PublicKey(x963Representation: keyData(name, "publicKeyX963Hex"))
    }

    func keyData(_ name: String, _ key: String) throws -> Data {
        try decodeHex(keyString(name, key))
    }

    func keyString(_ name: String, _ key: String) throws -> String {
        try string(in: dictionary("keys", name), key)
    }

    func mutationIds() throws -> [String] {
        guard let values = root["mutations"] as? [[String: Any]] else {
            throw SharedG1aCFixtureError.invalidValue("mutations")
        }
        return try values.map { try string(in: $0, "id") }
    }

    private func uint64(in dictionary: [String: Any], _ key: String) throws -> UInt64 {
        guard let value = dictionary[key] as? NSNumber else {
            throw SharedG1aCFixtureError.invalidValue(key)
        }
        return value.uint64Value
    }

    private func decodeHex(_ value: String) throws -> Data {
        guard value.count.isMultiple(of: 2),
              value.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
            throw SharedG1aCFixtureError.invalidHex(value)
        }
        var output = Data()
        output.reserveCapacity(value.count / 2)
        var index = value.startIndex
        while index < value.endIndex {
            let next = value.index(index, offsetBy: 2)
            guard let byte = UInt8(value[index..<next], radix: 16) else {
                throw SharedG1aCFixtureError.invalidHex(value)
            }
            output.append(byte)
            index = next
        }
        return output
    }
}
