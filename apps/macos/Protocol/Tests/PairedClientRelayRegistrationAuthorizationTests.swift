import CryptoKit
import Foundation
import XCTest
@testable import BridgeProtocol

final class PairedClientRelayRegistrationAuthorizationTests: XCTestCase {
    func testFixedSharedTranscriptAndDigestVector() throws {
        let challenge = try fixedChallenge()
        let transcript = String(decoding: challenge.transcriptData(), as: UTF8.self)

        XCTAssertEqual(challenge.transcriptDigest(), Self.digest)
        XCTAssertFalse(transcript.hasSuffix("\n"))
        XCTAssertTrue(transcript.contains("scheme\n21\npaired-client-p256-v1"))
        XCTAssertTrue(transcript.contains("ephemeral_key\n130\n\(Self.ephemeralKey)"))
        XCTAssertEqual(
            try PairedClientRelayRegistrationAuthorization.clientKeyFingerprint(
                publicKeyBase64: Self.clientPublicKey
            ),
            Self.clientFingerprint
        )
    }

    func testSignsTypedProofAndRejectsMutationAndWrongKey() throws {
        let challenge = try fixedChallenge()
        let proof = try PairedClientRelayRegistrationProof.sign(
            challenge: challenge,
            using: scalarPrivateKey(2)
        )

        XCTAssertEqual(proof.clientPublicKeyBase64, Self.clientPublicKey)
        XCTAssertTrue(proof.verify(challenge: challenge))
        XCTAssertFalse(proof.verify(challenge: try fixedChallenge(challenge: String(repeating: "f", count: 64))))

        XCTAssertThrowsError(try PairedClientRelayRegistrationProof.sign(
            challenge: challenge,
            using: scalarPrivateKey(1)
        )) {
            XCTAssertEqual(
                $0 as? PairedClientRelayRegistrationAuthorizationError,
                .clientKeyFingerprintMismatch
            )
        }

        let wrongKeyProof = try PairedClientRelayRegistrationProof(
            clientPublicKeyBase64: Self.runtimePublicKey,
            clientSignatureBase64: proof.clientSignatureBase64
        )
        XCTAssertFalse(wrongKeyProof.verify(challenge: challenge))
    }

    func testEveryFieldMutationInvalidatesProof() throws {
        let challenge = try fixedChallenge()
        let proof = try PairedClientRelayRegistrationProof.sign(
            challenge: challenge,
            using: scalarPrivateKey(2)
        )
        let mutations: [(String, [String: Any])] = [
            ("relay_id", ["relay_id": "rt2-\(String(repeating: "a", count: 64))"]),
            ("relay_expires_at", ["relay_expires_at": 1_780_003_600_001]),
            ("relay_nonce", ["relay_nonce": "relay-nonce-fixed-9"]),
            ("runtime_key_fingerprint", ["runtime_key_fingerprint": String(repeating: "a", count: 64)]),
            ("client_key_fingerprint", ["client_key_fingerprint": String(repeating: "b", count: 64)]),
            ("ticket_generation", ["ticket_generation": 9]),
            ("session_nonce", ["session_nonce": "ffeeddccbbaa99887766554433221100"]),
            ("ephemeral_key", ["ephemeral_key": Self.runtimeEphemeralKey]),
            ("challenge", ["challenge": String(repeating: "c", count: 64)]),
            ("challenge_expires_at", ["challenge_expires_at": 1_780_000_000_124]),
        ]

        for (field, mutation) in mutations {
            XCTAssertFalse(
                proof.verify(challenge: try decodedChallenge(challenge, replacing: mutation)),
                field
            )
        }
    }

    func testRejectsRoleSchemeAndVersionDowngrades() throws {
        XCTAssertThrowsError(try fixedChallenge(scheme: "paired-client-p256-v0"))
        XCTAssertThrowsError(try fixedChallenge(protocolVersion: 0))
        XCTAssertThrowsError(try decodedChallenge(
            fixedChallenge(),
            replacing: ["role": "runtime"]
        ))
        XCTAssertThrowsError(try decodedChallenge(
            fixedChallenge(),
            replacing: ["scheme": "runtime-p256-v1"]
        ))
    }

    func testRejectsNoncanonicalRelayCryptoAndIdentityFields() throws {
        let invalid: [(String, () throws -> Void)] = [
            ("rt3 relay", { _ = try self.fixedChallenge(relayID: "rt3-\(String(repeating: "a", count: 64))") }),
            ("uppercase relay", { _ = try self.fixedChallenge(relayID: Self.relayID.uppercased()) }),
            ("zero relay expiration", { _ = try self.fixedChallenge(relayExpiresAt: 0) }),
            ("blank relay nonce", { _ = try self.fixedChallenge(relayNonce: "") }),
            ("spaced relay nonce", { _ = try self.fixedChallenge(relayNonce: "relay nonce") }),
            ("oversized relay nonce", { _ = try self.fixedChallenge(relayNonce: String(repeating: "n", count: 513)) }),
            ("uppercase runtime fingerprint", { _ = try self.fixedChallenge(runtimeFingerprint: Self.runtimeFingerprint.uppercased()) }),
            ("same fingerprints", { _ = try self.fixedChallenge(clientFingerprint: Self.runtimeFingerprint) }),
            ("zero generation", { _ = try self.fixedChallenge(ticketGeneration: 0) }),
            ("uppercase session nonce", { _ = try self.fixedChallenge(sessionNonce: Self.sessionNonce.uppercased()) }),
            ("uppercase ephemeral key", { _ = try self.fixedChallenge(ephemeralKey: Self.ephemeralKey.uppercased()) }),
            ("off-curve ephemeral key", { _ = try self.fixedChallenge(ephemeralKey: "04" + String(repeating: "0", count: 128)) }),
            ("uppercase challenge", { _ = try self.fixedChallenge(challenge: Self.challenge.uppercased()) }),
            ("zero challenge expiration", { _ = try self.fixedChallenge(challengeExpiresAt: 0) }),
        ]

        for (name, operation) in invalid {
            XCTAssertThrowsError(try operation(), name)
        }
    }

    func testFreshnessHelpersUseStrictExpirationBoundaries() throws {
        let challenge = try fixedChallenge()

        XCTAssertTrue(challenge.isFresh(atEpochMillis: 1_780_000_000_000))
        XCTAssertTrue(challenge.isRelayFresh(atEpochMillis: 1_780_000_000_123))
        XCTAssertFalse(challenge.isChallengeFresh(atEpochMillis: 1_780_000_000_123))
        XCTAssertFalse(challenge.isFresh(atEpochMillis: 1_780_000_000_123))
        XCTAssertFalse(challenge.isRelayFresh(atEpochMillis: 1_780_003_600_000))
        XCTAssertFalse(challenge.isFresh(atEpochMillis: -1))
    }

    func testUTF8LengthsAndCanonicalDERBase64AreEnforced() throws {
        let unicodeNonce = try fixedChallenge(relayNonce: "é")
        XCTAssertTrue(
            String(decoding: unicodeNonce.transcriptData(), as: UTF8.self)
                .contains("relay_nonce\n2\né")
        )

        let proof = try PairedClientRelayRegistrationProof.sign(
            challenge: fixedChallenge(),
            using: scalarPrivateKey(2)
        )
        XCTAssertThrowsError(try PairedClientRelayRegistrationProof(
            clientPublicKeyBase64: proof.clientPublicKeyBase64 + "\n",
            clientSignatureBase64: proof.clientSignatureBase64
        ))
        XCTAssertThrowsError(try PairedClientRelayRegistrationProof(
            clientPublicKeyBase64: proof.clientPublicKeyBase64,
            clientSignatureBase64: proof.clientSignatureBase64 + "\n"
        ))

        let signatureDER = try XCTUnwrap(Data(base64Encoded: proof.clientSignatureBase64))
        var noncanonicalDER = Data([signatureDER[0], 0x81, signatureDER[1]])
        noncanonicalDER.append(signatureDER.dropFirst(2))
        XCTAssertThrowsError(try PairedClientRelayRegistrationProof(
            clientPublicKeyBase64: proof.clientPublicKeyBase64,
            clientSignatureBase64: noncanonicalDER.base64EncodedString()
        ))
    }

    private func fixedChallenge(
        scheme: String = PairedClientRelayRegistrationAuthorization.scheme,
        protocolVersion: Int = PairedClientRelayRegistrationAuthorization.protocolVersion,
        relayID: String = PairedClientRelayRegistrationAuthorizationTests.relayID,
        relayExpiresAt: Int64 = 1_780_003_600_000,
        relayNonce: String = "relay-nonce-fixed-8",
        runtimeFingerprint: String = PairedClientRelayRegistrationAuthorizationTests.runtimeFingerprint,
        clientFingerprint: String = PairedClientRelayRegistrationAuthorizationTests.clientFingerprint,
        ticketGeneration: Int64 = 8,
        sessionNonce: String = PairedClientRelayRegistrationAuthorizationTests.sessionNonce,
        ephemeralKey: String = PairedClientRelayRegistrationAuthorizationTests.ephemeralKey,
        challenge: String = PairedClientRelayRegistrationAuthorizationTests.challenge,
        challengeExpiresAt: Int64 = 1_780_000_000_123
    ) throws -> PairedClientRelayRegistrationChallenge {
        try PairedClientRelayRegistrationChallenge(
            scheme: scheme,
            protocolVersion: protocolVersion,
            relayID: relayID,
            relayExpiresAtEpochMillis: relayExpiresAt,
            relayNonce: relayNonce,
            runtimeKeyFingerprint: runtimeFingerprint,
            clientKeyFingerprint: clientFingerprint,
            ticketGeneration: ticketGeneration,
            sessionNonce: sessionNonce,
            ephemeralKey: ephemeralKey,
            challenge: challenge,
            challengeExpiresAtEpochMillis: challengeExpiresAt
        )
    }

    private func decodedChallenge(
        _ challenge: PairedClientRelayRegistrationChallenge,
        replacing fields: [String: Any]
    ) throws -> PairedClientRelayRegistrationChallenge {
        var object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: JSONEncoder().encode(challenge)) as? [String: Any]
        )
        fields.forEach { object[$0.key] = $0.value }
        return try JSONDecoder().decode(
            PairedClientRelayRegistrationChallenge.self,
            from: JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        )
    }

    private func scalarPrivateKey(_ scalar: UInt8) throws -> P256.Signing.PrivateKey {
        var raw = Data(repeating: 0, count: 32)
        raw[31] = scalar
        return try P256.Signing.PrivateKey(rawRepresentation: raw)
    }

    private static let relayID =
        "rt2-bab80c6a36ca54015900f1b37def33f2c15892836cb6b2907faacc3522a78361"
    private static let runtimeFingerprint =
        "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3"
    private static let clientFingerprint =
        "dc0ce633dbcc913dafafa4b89ac44d8ce683fdfc3f60c8bdf21213b9f2b534ba"
    private static let sessionNonce = "00112233445566778899aabbccddeeff"
    private static let ephemeralKey =
        "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1"
    private static let runtimeEphemeralKey =
        "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c2964fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
    private static let challenge =
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    private static let digest =
        "84181665e9bb332c46838e3e473ff6a98f2deb0eb74ccb1f5773b8f8d149412f"
    private static let runtimePublicKey =
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEaxfR8uEsQkf4vOblY6RA8ncDfYEt6zOg9KE5RdiYwpZP40Li/hp/m47n60p8D54WK84zV2sxXs7LtkBoN79R9Q=="
    private static let clientPublicKey =
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfPJ7GI0DT36KUjgDBLUaw8CJaeJ38hs1pgtI/EdmmXgHd1UQ247QQCk9msafdDDbun2t5jzpgimeBLedInhz0Q=="
}
