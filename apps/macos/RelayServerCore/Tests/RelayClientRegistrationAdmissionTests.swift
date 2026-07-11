import BridgeProtocol
import CryptoKit
import Foundation
import XCTest
@testable import RelayServerCore

final class RelayClientRegistrationAdmissionTests: XCTestCase {
    func testChallengeResponseUsesExactCanonicalLineAndRoundTrips() throws {
        let challenge = try fixedChallenge()
        let response = RelayPairedClientRegistrationChallengeResponse(challenge: challenge)
        let line = String(decoding: try response.responseLine(), as: UTF8.self)

        XCTAssertEqual(
            line,
            "AETHERLINK_RELAY client_registration_challenge " +
                "{\"challenge\":\"\(Self.challengeHex)\"," +
                "\"challenge_expires_at\":1780000000123," +
                "\"client_key_fingerprint\":\"\(Self.clientFingerprint)\"," +
                "\"ephemeral_key\":\"\(Self.clientEphemeralKey)\"," +
                "\"protocol_version\":1," +
                "\"relay_expires_at\":1780003600000," +
                "\"relay_id\":\"\(Self.relayID)\"," +
                "\"relay_nonce\":\"relay-nonce-fixed-8\"," +
                "\"role\":\"client\"," +
                "\"runtime_key_fingerprint\":\"\(Self.runtimeFingerprint)\"," +
                "\"scheme\":\"paired-client-p256-v1\"," +
                "\"session_nonce\":\"\(Self.sessionNonce)\"," +
                "\"ticket_generation\":8}\n"
        )
        XCTAssertEqual(
            try RelayPairedClientRegistrationChallengeResponse.parseResponseLine(line),
            response
        )
    }

    func testChallengeResponseRejectsMalformedExtraCRLFAndNoncanonicalBodies() throws {
        let valid = String(
            decoding: try RelayPairedClientRegistrationChallengeResponse(
                challenge: fixedChallenge()
            ).responseLine(),
            as: UTF8.self
        )
        let malformed = [
            String(valid.dropLast()),
            valid.replacingOccurrences(of: "\n", with: "\r\n"),
            valid.replacingOccurrences(of: "\"ticket_generation\":8", with: "\"ticket_generation\":8,\"extra\":true"),
            valid.replacingOccurrences(of: Self.challengeHex, with: Self.challengeHex.uppercased()),
            valid + "trailing\n",
            "AETHERLINK_RELAY client_registration_challenge {}\n",
        ]

        for line in malformed {
            XCTAssertThrowsError(
                try RelayPairedClientRegistrationChallengeResponse.parseResponseLine(line),
                line
            )
        }
    }

    func testProofRequestUsesExactFieldOrderAndRoundTrips() throws {
        let proof = try PairedClientRelayRegistrationProof.sign(
            challenge: fixedChallenge(),
            using: scalarPrivateKey(2)
        )
        let request = try RelayPairedClientRegistrationProofRequest(
            challenge: Self.challengeHex,
            clientPublicKeyBase64: proof.clientPublicKeyBase64,
            clientSignatureBase64: proof.clientSignatureBase64
        )
        let line = String(decoding: request.requestLine(), as: UTF8.self)

        XCTAssertEqual(
            line,
            "AETHERLINK_RELAY client_registration_proof crypto=2 " +
                "challenge=\(Self.challengeHex) " +
                "client_public_key=\(proof.clientPublicKeyBase64) " +
                "client_signature=\(proof.clientSignatureBase64)\n"
        )
        XCTAssertEqual(try RelayPairedClientRegistrationProofRequest.parse(line), request)
    }

    func testProofParserRejectsMalformedExtraReorderedCRLFAndNoncanonicalFields() throws {
        let proof = try PairedClientRelayRegistrationProof.sign(
            challenge: fixedChallenge(),
            using: scalarPrivateKey(2)
        )
        let publicKey = proof.clientPublicKeyBase64
        let signature = proof.clientSignatureBase64
        let valid =
            "AETHERLINK_RELAY client_registration_proof crypto=2 " +
            "challenge=\(Self.challengeHex) client_public_key=\(publicKey) " +
            "client_signature=\(signature)\n"
        let malformed = [
            String(valid.dropLast()),
            valid.replacingOccurrences(of: "\n", with: "\r\n"),
            valid.replacingOccurrences(of: " client_public_key", with: "  client_public_key"),
            valid.replacingOccurrences(of: "client_registration_proof ", with: "client_registration_proof\t"),
            valid.replacingOccurrences(of: "crypto=2", with: "crypto=1"),
            valid.replacingOccurrences(
                of: "challenge=\(Self.challengeHex) client_public_key=\(publicKey)",
                with: "client_public_key=\(publicKey) challenge=\(Self.challengeHex)"
            ),
            String(valid.dropLast()) + " extra=1\n",
            valid.replacingOccurrences(of: Self.challengeHex, with: Self.challengeHex.uppercased()),
            valid.replacingOccurrences(of: publicKey, with: String(publicKey.dropLast())),
            valid.replacingOccurrences(of: signature, with: signature + "="),
            valid + "extra\n",
        ]

        for line in malformed {
            XCTAssertThrowsError(try RelayPairedClientRegistrationProofRequest.parse(line), line)
        }
    }

    private func fixedChallenge() throws -> PairedClientRelayRegistrationChallenge {
        try PairedClientRelayRegistrationChallenge(
            relayID: Self.relayID,
            relayExpiresAtEpochMillis: 1_780_003_600_000,
            relayNonce: "relay-nonce-fixed-8",
            runtimeKeyFingerprint: Self.runtimeFingerprint,
            clientKeyFingerprint: Self.clientFingerprint,
            ticketGeneration: 8,
            sessionNonce: Self.sessionNonce,
            ephemeralKey: Self.clientEphemeralKey,
            challenge: Self.challengeHex,
            challengeExpiresAtEpochMillis: 1_780_000_000_123
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
    private static let clientEphemeralKey =
        "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc47669978" +
        "07775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1"
    private static let challengeHex =
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
