import CryptoKit
import Foundation
import XCTest
@testable import BridgeProtocol

final class RelayIdentityAuthorizationTests: XCTestCase {
    private static let publicKeyBase64 =
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEaxfR8uEsQkf4vOblY6RA8ncDfYEt6zOg9KE5RdiYwpZP40Li/hp/m47n60p8D54WK84zV2sxXs7LtkBoN79R9Q=="
    private static let fingerprint =
        "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3"
    private static let routeTokenHash =
        "6f25c222656b6eeaab74186839fb01912c7aa552274a4384de4bb77cff87025c"
    private static let allocationSignatureBase64 =
        "MEUCIQCjcn0Eo0ZsENubyI+aWVkO70fSxXTFdYeIrd9nTJ3jzAIgQmo07DSRsJnv2MHmh3BsJGixkG+6zVmndvAM6jEwX6o="

    func testRuntimeIdentityMatchesCanonicalDERAndFingerprintVector() throws {
        let identity = try RelayRuntimeIdentity(
            publicKeyBase64: Self.publicKeyBase64,
            fingerprint: Self.fingerprint
        )
        let publicKeyData = try XCTUnwrap(Data(base64Encoded: identity.publicKeyBase64))
        let publicKey = try P256.Signing.PublicKey(derRepresentation: publicKeyData)

        XCTAssertEqual(publicKey.derRepresentation, publicKeyData)
        XCTAssertEqual(
            publicKeyData.map { String(format: "%02x", $0) }.joined(),
            "3059301306072a8648ce3d020106082a8648ce3d030107034200046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c2964fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
        )
        XCTAssertEqual(
            SHA256.hash(data: publicKeyData).map { String(format: "%02x", $0) }.joined(),
            identity.fingerprint
        )
        XCTAssertThrowsError(try RelayRuntimeIdentity(
            publicKeyBase64: Self.publicKeyBase64,
            fingerprint: String(repeating: "0", count: 64)
        ))
        XCTAssertThrowsError(try RelayRuntimeIdentity(
            publicKeyBase64: Self.publicKeyBase64 + "=",
            fingerprint: Self.fingerprint
        ))
    }

    func testAllocationChallengeMatchesExactTranscriptAndDerivationVectors() throws {
        let challenge = try allocationChallenge()

        XCTAssertEqual(
            String(decoding: challenge.signedMessageData(), as: UTF8.self),
            """
            AetherLink relay allocation authorization v1
            operation
            create
            crypto_version
            2
            allocation_auth
            runtime-p256-v1
            relay_id
            rt2-vector
            route_token_hash
            6f25c222656b6eeaab74186839fb01912c7aa552274a4384de4bb77cff87025c
            runtime_key_fingerprint
            5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3
            ticket_generation
            7
            challenge
            2222222222222222222222222222222222222222222222222222222222222222
            challenge_expires_at
            1780000000123
            """
        )
        XCTAssertEqual(
            RelayAllocationIdentityChallenge.routeTokenHash("route-token-vector"),
            Self.routeTokenHash
        )
        XCTAssertEqual(
            RelayAllocationIdentityChallenge.relayID(
                routeToken: "route-token-vector",
                runtimeKeyFingerprint: Self.fingerprint
            ),
            "rt2-bab80c6a36ca54015900f1b37def33f2c15892836cb6b2907faacc3522a78361"
        )
    }

    func testPairScopedRelayIDBindsRouteRuntimeAndClient() {
        let runtimeFingerprint = String(repeating: "a", count: 64)
        let clientFingerprint = String(repeating: "b", count: 64)

        XCTAssertEqual(
            RelayAllocationIdentityChallenge.pairedRelayID(
                routeToken: "route-token",
                runtimeKeyFingerprint: runtimeFingerprint,
                clientKeyFingerprint: clientFingerprint
            ),
            "rt2-31b91c84adca190fc27f6a63fb470a1bf0f1bfea1825cbc7897cc975396cd6bc"
        )
        XCTAssertNotEqual(
            RelayAllocationIdentityChallenge.pairedRelayID(
                routeToken: "route-token-2",
                runtimeKeyFingerprint: runtimeFingerprint,
                clientKeyFingerprint: clientFingerprint
            ),
            RelayAllocationIdentityChallenge.pairedRelayID(
                routeToken: "route-token",
                runtimeKeyFingerprint: runtimeFingerprint,
                clientKeyFingerprint: clientFingerprint
            )
        )
    }

    func testRegistrationChallengeMatchesExactTranscript() throws {
        let challenge = try registrationChallenge()

        XCTAssertEqual(
            String(decoding: challenge.signedMessageData(), as: UTF8.self),
            """
            AetherLink relay runtime registration authorization v1
            crypto_version
            2
            allocation_auth
            runtime-p256-v1
            relay_id
            rt2-vector
            relay_expires_at
            1780000000000
            relay_nonce
            relay-nonce-vector
            runtime_key_fingerprint
            5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3
            ticket_generation
            7
            session_nonce
            00112233445566778899aabbccddeeff
            ephemeral_key
            047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1
            challenge
            3333333333333333333333333333333333333333333333333333333333333333
            challenge_expires_at
            1780000000999
            """
        )
    }

    func testFixedAllocationSignatureRejectsTranscriptMutationAndWrongKey() throws {
        let identity = try RelayRuntimeIdentity(
            publicKeyBase64: Self.publicKeyBase64,
            fingerprint: Self.fingerprint
        )
        let challenge = try allocationChallenge()
        let mutatedChallenge = try RelayAllocationIdentityChallenge(
            operation: .create,
            relayID: "rt2-vector",
            routeTokenHash: Self.routeTokenHash,
            runtimeKeyFingerprint: Self.fingerprint,
            ticketGeneration: 7,
            challenge: String(repeating: "3", count: 64),
            challengeExpiresAtEpochMillis: 1_780_000_000_123
        )
        let wrongKey = P256.Signing.PrivateKey()
        let wrongKeyData = wrongKey.publicKey.derRepresentation
        let wrongIdentity = try RelayRuntimeIdentity(
            publicKeyBase64: wrongKeyData.base64EncodedString(),
            fingerprint: SHA256.hash(data: wrongKeyData)
                .map { String(format: "%02x", $0) }
                .joined()
        )

        XCTAssertThrowsError(try RelayIdentityAuthorizationProof(
            runtimeIdentity: identity,
            signatureBase64: Self.allocationSignatureBase64 + "="
        ))

        XCTAssertTrue(RelayIdentityAuthorization.verify(
            signatureBase64: Self.allocationSignatureBase64,
            messageData: challenge.signedMessageData(),
            runtimeIdentity: identity
        ))
        XCTAssertFalse(RelayIdentityAuthorization.verify(
            signatureBase64: Self.allocationSignatureBase64,
            messageData: mutatedChallenge.signedMessageData(),
            runtimeIdentity: identity
        ))
        XCTAssertFalse(RelayIdentityAuthorization.verify(
            signatureBase64: Self.allocationSignatureBase64,
            messageData: challenge.signedMessageData(),
            runtimeIdentity: wrongIdentity
        ))
    }

    private func allocationChallenge() throws -> RelayAllocationIdentityChallenge {
        try RelayAllocationIdentityChallenge(
            operation: .create,
            relayID: "rt2-vector",
            routeTokenHash: Self.routeTokenHash,
            runtimeKeyFingerprint: Self.fingerprint,
            ticketGeneration: 7,
            challenge: String(repeating: "2", count: 64),
            challengeExpiresAtEpochMillis: 1_780_000_000_123
        )
    }

    private func registrationChallenge() throws -> RelayRuntimeRegistrationIdentityChallenge {
        try RelayRuntimeRegistrationIdentityChallenge(
            relayID: "rt2-vector",
            relayExpiresAtEpochMillis: 1_780_000_000_000,
            relayNonce: "relay-nonce-vector",
            runtimeKeyFingerprint: Self.fingerprint,
            ticketGeneration: 7,
            sessionNonce: "00112233445566778899aabbccddeeff",
            ephemeralKey: "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1",
            challenge: String(repeating: "3", count: 64),
            challengeExpiresAtEpochMillis: 1_780_000_000_999
        )
    }
}
