import CryptoKit
import Foundation
import XCTest
@testable import BridgeProtocol

final class PairedRelayAllocationAuthorizationTests: XCTestCase {
    private static let runtimePublicKey =
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEaxfR8uEsQkf4vOblY6RA8ncDfYEt6zOg9KE5RdiYwpZP40Li/hp/m47n60p8D54WK84zV2sxXs7LtkBoN79R9Q=="
    private static let runtimeFingerprint =
        "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3"
    private static let clientPublicKey =
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfPJ7GI0DT36KUjgDBLUaw8CJaeJ38hs1pgtI/EdmmXgHd1UQ247QQCk9msafdDDbun2t5jzpgimeBLedInhz0Q=="
    private static let clientFingerprint =
        "dc0ce633dbcc913dafafa4b89ac44d8ce683fdfc3f60c8bdf21213b9f2b534ba"
    private static let routeTokenHash =
        "6f25c222656b6eeaab74186839fb01912c7aa552274a4384de4bb77cff87025c"
    private static let currentRelayID =
        "rt2-bab80c6a36ca54015900f1b37def33f2c15892836cb6b2907faacc3522a78361"
    private static let nextRelayID =
        "rt2-aab80c6a36ca54015900f1b37def33f2c15892836cb6b2907faacc3522a78362"
    private static let challengeHex = String(repeating: "2", count: 64)
    private static let binding = String(repeating: "3", count: 64)

    func testFixedRuntimeAndClientTranscriptDigestsAndFraming() throws {
        let challenge = try fixedChallenge()
        let runtimeData = challenge.runtimeSignedMessageData()
        let clientData = challenge.clientSignedMessageData()

        XCTAssertEqual(
            String(decoding: runtimeData, as: UTF8.self),
            expectedTranscript(context: PairedRelayAllocationAuthorization.runtimeContext)
        )
        XCTAssertEqual(
            String(decoding: clientData, as: UTF8.self),
            expectedTranscript(context: PairedRelayAllocationAuthorization.clientContext)
        )
        XCTAssertFalse(runtimeData.last == UInt8(ascii: "\n"))
        XCTAssertFalse(clientData.last == UInt8(ascii: "\n"))
        XCTAssertEqual(
            challenge.runtimeTranscriptDigest(),
            "e452c682d979b2423284220693984e27639e8153ad60cb4a772f26702527b294"
        )
        XCTAssertEqual(
            challenge.clientTranscriptDigest(),
            "c5cf9abceebf9664030cbfc6dec86fc0bb24fb1dd9c43022234cb785565f2f17"
        )
        XCTAssertEqual(
            PairedRelayAllocationAuthorization.routeTokenHash("route-token-vector"),
            Self.routeTokenHash
        )
        XCTAssertEqual(
            try PairedRelayAllocationAuthorization.publicKeyFingerprint(
                publicKeyBase64: Self.runtimePublicKey
            ),
            Self.runtimeFingerprint
        )
        XCTAssertFalse(String(decoding: runtimeData, as: UTF8.self).contains(Self.runtimePublicKey))
        XCTAssertFalse(String(decoding: clientData, as: UTF8.self).contains(Self.clientPublicKey))
    }

    func testAndroidSharedFixedTranscriptDigests() throws {
        let challenge = try PairedRelayAllocationAuthorizationChallenge(
            operation: .claim,
            requestID: "request-fixed-1",
            authorizationID: "authorization-fixed-1",
            currentRelayID: "rt2-\(String(repeating: "01", count: 32))",
            nextRelayID: "rt2-\(String(repeating: "02", count: 32))",
            routeTokenHash: String(repeating: "12", count: 32),
            runtimeKeyFingerprint: Self.runtimeFingerprint,
            clientKeyFingerprint: Self.clientFingerprint,
            currentTicketGeneration: 7,
            nextTicketGeneration: 8,
            currentRelayExpiresAtEpochMillis: 1_780_000_000_123,
            currentRelayNonce: String(repeating: "34", count: 32),
            nextRelayExpiresAtEpochMillis: 1_780_003_600_123,
            nextRelayNonce: String(repeating: "56", count: 32),
            challenge: String(repeating: "78", count: 32),
            challengeExpiresAtEpochMillis: 1_779_999_999_123,
            transportBinding: String(repeating: "9a", count: 32)
        )

        XCTAssertEqual(
            challenge.runtimeTranscriptDigest(),
            "445ee1adc3d521b2ba9d09e39d1ab23e913a262e5a5619f813ab162abc6ec37a"
        )
        XCTAssertEqual(
            challenge.clientTranscriptDigest(),
            "fa37320c45fef6dfdea036fd0315262d9f067f51b0ce335f7a31890419d822fa"
        )
    }

    func testDeterministicKeysProduceValidRoleSpecificProofsAndCodableValues() throws {
        let challenge = try fixedChallenge()
        let runtimeProof = try PairedRelayAllocationRuntimeProof.sign(
            challenge: challenge,
            using: scalarPrivateKey(1)
        )
        let clientProof = try PairedRelayAllocationClientProof.sign(
            challenge: challenge,
            using: scalarPrivateKey(2)
        )

        XCTAssertEqual(runtimeProof.publicKeyBase64, Self.runtimePublicKey)
        XCTAssertEqual(clientProof.publicKeyBase64, Self.clientPublicKey)
        XCTAssertTrue(runtimeProof.verify(challenge: challenge))
        XCTAssertTrue(clientProof.verify(challenge: challenge))
        XCTAssertNoThrow(try PairedRelayAllocationAuthorization.validatedRuntimePublicKey(
            base64: runtimeProof.publicKeyBase64,
            fingerprint: challenge.runtimeKeyFingerprint
        ))
        XCTAssertNoThrow(try PairedRelayAllocationAuthorization.validatedClientPublicKey(
            base64: clientProof.publicKeyBase64,
            fingerprint: challenge.clientKeyFingerprint
        ))

        let decoder = JSONDecoder()
        XCTAssertEqual(
            try decoder.decode(
                PairedRelayAllocationAuthorizationChallenge.self,
                from: JSONEncoder().encode(challenge)
            ),
            challenge
        )
        XCTAssertEqual(
            try decoder.decode(
                PairedRelayAllocationRuntimeProof.self,
                from: JSONEncoder().encode(runtimeProof)
            ),
            runtimeProof
        )
        XCTAssertEqual(
            try decoder.decode(
                PairedRelayAllocationClientProof.self,
                from: JSONEncoder().encode(clientProof)
            ),
            clientProof
        )
        XCTAssertThrowsError(try decodedChallenge(
            challenge,
            replacing: ["unknown": "metadata"]
        ))
        XCTAssertThrowsError(try decodedChallenge(
            challenge,
            replacing: ["relay_id": Self.currentRelayID]
        ))
        XCTAssertThrowsError(try decodedProof(
            runtimeProof,
            as: PairedRelayAllocationRuntimeProof.self,
            adding: ["unknown": "metadata"]
        ))
        XCTAssertThrowsError(try decodedProof(
            clientProof,
            as: PairedRelayAllocationClientProof.self,
            adding: ["unknown": "metadata"]
        ))
    }

    func testWrongKeysCannotSignOrVerify() throws {
        let challenge = try fixedChallenge()
        let wrongKey = try scalarPrivateKey(3)

        XCTAssertThrowsError(try PairedRelayAllocationRuntimeProof.sign(
            challenge: challenge,
            using: wrongKey
        )) {
            XCTAssertEqual(
                $0 as? PairedRelayAllocationAuthorizationError,
                .invalidFingerprint("runtime_key_fingerprint")
            )
        }
        XCTAssertThrowsError(try PairedRelayAllocationClientProof.sign(
            challenge: challenge,
            using: wrongKey
        )) {
            XCTAssertEqual(
                $0 as? PairedRelayAllocationAuthorizationError,
                .invalidFingerprint("client_key_fingerprint")
            )
        }

        let wrongSignature = try wrongKey.signature(
            for: SHA256.hash(data: challenge.runtimeSignedMessageData())
        )
        let wrongKeyProof = try PairedRelayAllocationRuntimeProof(
            publicKeyBase64: wrongKey.publicKey.derRepresentation.base64EncodedString(),
            signatureBase64: wrongSignature.derRepresentation.base64EncodedString()
        )
        let wrongSignatureProof = try PairedRelayAllocationRuntimeProof(
            publicKeyBase64: Self.runtimePublicKey,
            signatureBase64: wrongSignature.derRepresentation.base64EncodedString()
        )

        XCTAssertFalse(wrongKeyProof.verify(challenge: challenge))
        XCTAssertFalse(wrongSignatureProof.verify(challenge: challenge))
    }

    func testRuntimeAndClientProofsCannotBeRoleSwapped() throws {
        let sharedKeyChallenge = try fixedChallenge(
            clientKeyFingerprint: Self.runtimeFingerprint
        )
        let key = try scalarPrivateKey(1)
        let runtimeProof = try PairedRelayAllocationRuntimeProof.sign(
            challenge: sharedKeyChallenge,
            using: key
        )
        let clientProof = try PairedRelayAllocationClientProof.sign(
            challenge: sharedKeyChallenge,
            using: key
        )

        let runtimeAsClient = try PairedRelayAllocationClientProof(
            publicKeyBase64: runtimeProof.publicKeyBase64,
            signatureBase64: runtimeProof.signatureBase64
        )
        let clientAsRuntime = try PairedRelayAllocationRuntimeProof(
            publicKeyBase64: clientProof.publicKeyBase64,
            signatureBase64: clientProof.signatureBase64
        )

        XCTAssertFalse(runtimeAsClient.verify(challenge: sharedKeyChallenge))
        XCTAssertFalse(clientAsRuntime.verify(challenge: sharedKeyChallenge))
    }

    func testEveryMutableTranscriptClaimIsSignatureBound() throws {
        let challenge = try fixedChallenge()
        let runtimeProof = try PairedRelayAllocationRuntimeProof.sign(
            challenge: challenge,
            using: scalarPrivateKey(1)
        )
        let clientProof = try PairedRelayAllocationClientProof.sign(
            challenge: challenge,
            using: scalarPrivateKey(2)
        )
        let mutations: [(String, [String: Any])] = [
            ("operation", ["operation": "renew"]),
            ("request_id", ["request_id": "request-fixed-2"]),
            ("authorization_id", ["authorization_id": "authorization-fixed-2"]),
            ("current_relay_id", ["current_relay_id": "rt2-\(String(repeating: "a", count: 64))"]),
            ("next_relay_id", ["next_relay_id": "rt2-\(String(repeating: "b", count: 64))"]),
            ("route_token_hash", ["route_token_hash": String(repeating: "a", count: 64)]),
            ("runtime_key_fingerprint", ["runtime_key_fingerprint": String(repeating: "b", count: 64)]),
            ("client_key_fingerprint", ["client_key_fingerprint": String(repeating: "c", count: 64)]),
            ("ticket_generations", ["current_ticket_generation": 9, "next_ticket_generation": 10]),
            ("current_relay_expires_at", ["current_relay_expires_at": 1_780_000_200_000]),
            ("current_relay_nonce", ["current_relay_nonce": "nonce-current-9"]),
            ("next_relay_expires_at", ["next_relay_expires_at": 1_780_003_700_000]),
            ("next_relay_nonce", ["next_relay_nonce": "nonce-next-9"]),
            ("challenge", ["challenge": String(repeating: "d", count: 64)]),
            ("challenge_expires_at", ["challenge_expires_at": 1_780_000_000_124]),
            ("transport_binding", ["transport_binding": String(repeating: "e", count: 64)]),
        ]

        for (name, changes) in mutations {
            let mutated = try decodedChallenge(challenge, replacing: changes)
            XCTAssertFalse(runtimeProof.verify(challenge: mutated), name)
            XCTAssertFalse(clientProof.verify(challenge: mutated), name)
        }
    }

    func testRejectsSchemeVersionAndOperationDowngrades() throws {
        XCTAssertEqual(PairedRelayAllocationOperation.allCases, [.claim, .renew])
        XCTAssertThrowsError(try fixedChallenge(scheme: "runtime-client-p256-v0")) {
            XCTAssertEqual(
                $0 as? PairedRelayAllocationAuthorizationError,
                .invalidField("scheme")
            )
        }
        XCTAssertThrowsError(try fixedChallenge(protocolVersion: 0)) {
            XCTAssertEqual(
                $0 as? PairedRelayAllocationAuthorizationError,
                .invalidField("protocol_version")
            )
        }
        XCTAssertThrowsError(try decodedChallenge(
            fixedChallenge(),
            replacing: ["operation": "create"]
        ))
    }

    func testRejectsNoncanonicalBase64DERAndFingerprintBindings() throws {
        let challenge = try fixedChallenge()
        let runtimeProof = try PairedRelayAllocationRuntimeProof.sign(
            challenge: challenge,
            using: scalarPrivateKey(1)
        )
        let runtimeKey = try scalarPrivateKey(1)
        let publicKeyDER = try XCTUnwrap(Data(base64Encoded: Self.runtimePublicKey))
        var noncanonicalPublicKeyDER = Data([publicKeyDER[0], 0x81, publicKeyDER[1]])
        noncanonicalPublicKeyDER.append(publicKeyDER.dropFirst(2))
        let signatureDER = try XCTUnwrap(Data(base64Encoded: runtimeProof.signatureBase64))
        var noncanonicalSignatureDER = Data([signatureDER[0], 0x81, signatureDER[1]])
        noncanonicalSignatureDER.append(signatureDER.dropFirst(2))

        for publicKey in [
            Self.runtimePublicKey + "\n",
            noncanonicalPublicKeyDER.base64EncodedString(),
            runtimeKey.publicKey.rawRepresentation.base64EncodedString(),
        ] {
            XCTAssertThrowsError(try PairedRelayAllocationRuntimeProof(
                publicKeyBase64: publicKey,
                signatureBase64: runtimeProof.signatureBase64
            )) {
                XCTAssertEqual(
                    $0 as? PairedRelayAllocationAuthorizationError,
                    .invalidPublicKey("runtime_public_key")
                )
            }
        }

        for signature in [
            runtimeProof.signatureBase64 + "\n",
            noncanonicalSignatureDER.base64EncodedString(),
            Data(repeating: 1, count: 64).base64EncodedString(),
        ] {
            XCTAssertThrowsError(try PairedRelayAllocationRuntimeProof(
                publicKeyBase64: Self.runtimePublicKey,
                signatureBase64: signature
            )) {
                XCTAssertEqual(
                    $0 as? PairedRelayAllocationAuthorizationError,
                    .invalidSignature("runtime_signature")
                )
            }
        }

        XCTAssertThrowsError(try PairedRelayAllocationAuthorization.validatedRuntimePublicKey(
            base64: Self.runtimePublicKey,
            fingerprint: Self.clientFingerprint
        )) {
            XCTAssertEqual(
                $0 as? PairedRelayAllocationAuthorizationError,
                .invalidFingerprint("runtime_key_fingerprint")
            )
        }
        XCTAssertThrowsError(try PairedRelayAllocationAuthorization.validatedClientPublicKey(
            base64: Self.clientPublicKey + "=",
            fingerprint: Self.clientFingerprint
        ))
    }

    func testRejectsNoncanonicalHexAndRelayIDValues() throws {
        let invalidCases: [(String, () throws -> Void)] = [
            ("current relay prefix", { _ = try self.fixedChallenge(currentRelayID: "rt1-\(String(repeating: "a", count: 64))") }),
            ("current relay short", { _ = try self.fixedChallenge(currentRelayID: "rt2-short") }),
            ("next relay uppercase", { _ = try self.fixedChallenge(nextRelayID: "rt2-\(String(repeating: "A", count: 64))") }),
            ("route hash", { _ = try self.fixedChallenge(routeTokenHash: Self.routeTokenHash.uppercased()) }),
            ("runtime fingerprint", { _ = try self.fixedChallenge(runtimeKeyFingerprint: Self.runtimeFingerprint.uppercased()) }),
            ("client fingerprint", { _ = try self.fixedChallenge(clientKeyFingerprint: Self.clientFingerprint.uppercased()) }),
            ("challenge", { _ = try self.fixedChallenge(challengeHex: String(repeating: "A", count: 64)) }),
            ("binding", { _ = try self.fixedChallenge(transportBinding: String(repeating: "B", count: 64)) }),
        ]

        for (name, operation) in invalidCases {
            XCTAssertThrowsError(try operation(), name)
        }
    }

    func testClaimRotatesRelayIDAndRenewAllowsEqualOrDifferentIDs() throws {
        XCTAssertThrowsError(try fixedChallenge(nextRelayID: Self.currentRelayID)) {
            XCTAssertEqual(
                $0 as? PairedRelayAllocationAuthorizationError,
                .invalidField("next_relay_id")
            )
        }
        XCTAssertNoThrow(try fixedChallenge(operation: .renew))
        XCTAssertNoThrow(try fixedChallenge(
            operation: .renew,
            nextRelayID: Self.currentRelayID
        ))
    }

    func testGenerationExpirationAndFreshnessInvariants() throws {
        XCTAssertThrowsError(try fixedChallenge(currentTicketGeneration: 0))
        XCTAssertThrowsError(try fixedChallenge(
            currentTicketGeneration: Int64.max,
            nextTicketGeneration: Int64.max
        ))
        XCTAssertThrowsError(try fixedChallenge(nextTicketGeneration: 7))
        XCTAssertThrowsError(try fixedChallenge(currentRelayExpiresAtEpochMillis: 0))
        XCTAssertThrowsError(try fixedChallenge(nextRelayExpiresAtEpochMillis: 1_780_000_100_000))
        XCTAssertThrowsError(try fixedChallenge(challengeExpiresAtEpochMillis: 0))

        let challenge = try fixedChallenge()
        XCTAssertTrue(challenge.isFresh(atEpochMillis: 1_780_000_000_000))
        XCTAssertFalse(challenge.isFresh(atEpochMillis: 1_780_000_000_123))
        XCTAssertFalse(challenge.isFresh(atEpochMillis: 1_780_000_100_000))
        XCTAssertFalse(challenge.isFresh(atEpochMillis: -1))
    }

    func testOpaqueIDsAndDistinctCanonicalNoncesAreRequired() throws {
        XCTAssertNoThrow(try fixedChallenge(
            requestID: "request+opaque/1=",
            authorizationID: String(repeating: "a", count: 512),
            currentRelayNonce: "nonce+opaque/1=",
            nextRelayNonce: "nonce+opaque/2="
        ))

        for requestID in ["", " ", "request\nid", String(repeating: "r", count: 513)] {
            XCTAssertThrowsError(try fixedChallenge(requestID: requestID))
        }
        for authorizationID in ["", "\t", "authorization id", String(repeating: "a", count: 513)] {
            XCTAssertThrowsError(try fixedChallenge(authorizationID: authorizationID))
        }
        for currentNonce in ["", "nonce value", "nonce\nvalue", String(repeating: "n", count: 513)] {
            XCTAssertThrowsError(try fixedChallenge(currentRelayNonce: currentNonce))
        }
        for nextNonce in ["", "nonce value", "nonce\tvalue", String(repeating: "n", count: 513)] {
            XCTAssertThrowsError(try fixedChallenge(nextRelayNonce: nextNonce))
        }
        XCTAssertThrowsError(try fixedChallenge(
            currentRelayNonce: "same-nonce",
            nextRelayNonce: "same-nonce"
        )) {
            XCTAssertEqual(
                $0 as? PairedRelayAllocationAuthorizationError,
                .invalidField("next_relay_nonce")
            )
        }
    }

    private func fixedChallenge(
        scheme: String = PairedRelayAllocationAuthorization.scheme,
        protocolVersion: Int = PairedRelayAllocationAuthorization.protocolVersion,
        operation: PairedRelayAllocationOperation = .claim,
        requestID: String = "request-fixed-1",
        authorizationID: String = "authorization-fixed-1",
        currentRelayID: String = PairedRelayAllocationAuthorizationTests.currentRelayID,
        nextRelayID: String = PairedRelayAllocationAuthorizationTests.nextRelayID,
        routeTokenHash: String = PairedRelayAllocationAuthorizationTests.routeTokenHash,
        runtimeKeyFingerprint: String = PairedRelayAllocationAuthorizationTests.runtimeFingerprint,
        clientKeyFingerprint: String = PairedRelayAllocationAuthorizationTests.clientFingerprint,
        currentTicketGeneration: Int64 = 7,
        nextTicketGeneration: Int64 = 8,
        currentRelayExpiresAtEpochMillis: Int64 = 1_780_000_100_000,
        currentRelayNonce: String = "nonce-current-7",
        nextRelayExpiresAtEpochMillis: Int64 = 1_780_003_600_000,
        nextRelayNonce: String = "nonce-next-8",
        challengeHex: String = PairedRelayAllocationAuthorizationTests.challengeHex,
        challengeExpiresAtEpochMillis: Int64 = 1_780_000_000_123,
        transportBinding: String = PairedRelayAllocationAuthorizationTests.binding
    ) throws -> PairedRelayAllocationAuthorizationChallenge {
        try PairedRelayAllocationAuthorizationChallenge(
            scheme: scheme,
            protocolVersion: protocolVersion,
            operation: operation,
            requestID: requestID,
            authorizationID: authorizationID,
            currentRelayID: currentRelayID,
            nextRelayID: nextRelayID,
            routeTokenHash: routeTokenHash,
            runtimeKeyFingerprint: runtimeKeyFingerprint,
            clientKeyFingerprint: clientKeyFingerprint,
            currentTicketGeneration: currentTicketGeneration,
            nextTicketGeneration: nextTicketGeneration,
            currentRelayExpiresAtEpochMillis: currentRelayExpiresAtEpochMillis,
            currentRelayNonce: currentRelayNonce,
            nextRelayExpiresAtEpochMillis: nextRelayExpiresAtEpochMillis,
            nextRelayNonce: nextRelayNonce,
            challenge: challengeHex,
            challengeExpiresAtEpochMillis: challengeExpiresAtEpochMillis,
            transportBinding: transportBinding
        )
    }

    private func expectedTranscript(context: String) -> String {
        let fields = [
            ("scheme", PairedRelayAllocationAuthorization.scheme),
            ("protocol_version", "2"),
            ("operation", "claim"),
            ("request_id", "request-fixed-1"),
            ("authorization_id", "authorization-fixed-1"),
            ("current_relay_id", Self.currentRelayID),
            ("next_relay_id", Self.nextRelayID),
            ("route_token_hash", Self.routeTokenHash),
            ("runtime_key_fingerprint", Self.runtimeFingerprint),
            ("client_key_fingerprint", Self.clientFingerprint),
            ("current_ticket_generation", "7"),
            ("next_ticket_generation", "8"),
            ("current_relay_expires_at", "1780000100000"),
            ("current_relay_nonce", "nonce-current-7"),
            ("next_relay_expires_at", "1780003600000"),
            ("next_relay_nonce", "nonce-next-8"),
            ("challenge", Self.challengeHex),
            ("challenge_expires_at", "1780000000123"),
            ("transport_binding", Self.binding),
        ]
        let components = [context] + fields.flatMap { name, value in
            [name, String(value.utf8.count), value]
        }
        return components.joined(separator: "\n")
    }

    private func decodedChallenge(
        _ challenge: PairedRelayAllocationAuthorizationChallenge,
        replacing changes: [String: Any]
    ) throws -> PairedRelayAllocationAuthorizationChallenge {
        let encoded = try JSONEncoder().encode(challenge)
        var object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: encoded) as? [String: Any]
        )
        for (key, value) in changes {
            object[key] = value
        }
        return try JSONDecoder().decode(
            PairedRelayAllocationAuthorizationChallenge.self,
            from: JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        )
    }

    private func decodedProof<Proof: Codable>(
        _ proof: Proof,
        as type: Proof.Type,
        adding fields: [String: Any]
    ) throws -> Proof {
        let encoded = try JSONEncoder().encode(proof)
        var object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: encoded) as? [String: Any]
        )
        for (key, value) in fields {
            object[key] = value
        }
        return try JSONDecoder().decode(
            type,
            from: JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        )
    }

    private func scalarPrivateKey(_ scalar: UInt8) throws -> P256.Signing.PrivateKey {
        var raw = Data(repeating: 0, count: 32)
        raw[31] = scalar
        return try P256.Signing.PrivateKey(rawRepresentation: raw)
    }
}
