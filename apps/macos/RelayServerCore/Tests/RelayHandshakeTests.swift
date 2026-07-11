import XCTest
@testable import RelayServerCore

final class RelayHandshakeTests: XCTestCase {
    private let sessionNonce = "0123456789abcdef0123456789abcdef"
    private let ephemeralKey =
        "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296" +
        "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
    private let runtimeFingerprint = String(repeating: "a", count: 64)

    func testParsesRuntimeHandshake() throws {
        let handshake = try RelayHandshake.parse("AETHERLINK_RELAY runtime relay-123\n")

        XCTAssertEqual(handshake.role, .runtime)
        XCTAssertEqual(handshake.relayID, "relay-123")
        XCTAssertNil(handshake.sessionNonce)
        XCTAssertNil(handshake.ephemeralKey)
        XCTAssertFalse(handshake.usesCryptoV2)
    }

    func testParsesClientHandshake() throws {
        let handshake = try RelayHandshake.parse("AETHERLINK_RELAY client relay-123")

        XCTAssertEqual(handshake.role, .client)
        XCTAssertEqual(handshake.relayID, "relay-123")
        XCTAssertNil(handshake.sessionNonce)
        XCTAssertNil(handshake.ephemeralKey)
        XCTAssertFalse(handshake.usesCryptoV2)
    }

    func testParsesExactCryptoV2Handshake() throws {
        let handshake = try RelayHandshake.parse(
            "AETHERLINK_RELAY runtime relay-123 crypto=2 session_nonce=\(sessionNonce) " +
                "ephemeral_key=\(ephemeralKey) runtime_key_fingerprint=\(runtimeFingerprint)\n"
        )

        XCTAssertEqual(handshake.role, .runtime)
        XCTAssertEqual(handshake.relayID, "relay-123")
        XCTAssertEqual(handshake.sessionNonce, sessionNonce)
        XCTAssertEqual(handshake.ephemeralKey, ephemeralKey)
        XCTAssertEqual(handshake.runtimeKeyFingerprint, runtimeFingerprint)
        XCTAssertTrue(handshake.usesCryptoV2)
    }

    func testRejectsMalformedAndNonExactHandshake() {
        XCTAssertThrowsError(try RelayHandshake.parse("HELLO runtime relay-123\n"))
        XCTAssertThrowsError(try RelayHandshake.parse("AETHERLINK_RELAY runtime relay-123 extra\n"))
        let malformedLines = [
            "AETHERLINK_RELAY  runtime relay-123\n",
            "AETHERLINK_RELAY\truntime relay-123\n",
            "AETHERLINK_RELAY runtime relay-123 \n",
            "AETHERLINK_RELAY runtime relay-123\r\n",
            "AETHERLINK_RELAY runtime relay-123 crypto=2 session_nonce=\(sessionNonce)\n",
            "AETHERLINK_RELAY runtime relay-123 crypto=2 ephemeral_key=\(ephemeralKey) session_nonce=\(sessionNonce)\n",
            "AETHERLINK_RELAY runtime relay-123 crypto=2 nonce=\(sessionNonce) ephemeral_key=\(ephemeralKey)\n",
            "AETHERLINK_RELAY runtime relay-123 crypto=2 session_nonce=\(sessionNonce) key=\(ephemeralKey)\n",
            "AETHERLINK_RELAY runtime relay-123 crypto=2 session_nonce=\(sessionNonce) ephemeral_key=\(ephemeralKey) extra\n",
        ]
        for line in malformedLines {
            XCTAssertThrowsError(try RelayHandshake.parse(line), line)
        }
    }

    func testRejectsAnyCryptoVersionOtherThanTwo() {
        XCTAssertThrowsError(
            try RelayHandshake.parse(
                "AETHERLINK_RELAY client relay-123 crypto=1 session_nonce=\(sessionNonce) " +
                    "ephemeral_key=\(ephemeralKey)\n"
            )
        ) { error in
            XCTAssertEqual(error as? RelayHandshakeError, .invalidCryptoVersion)
        }
    }

    func testRejectsNonCanonicalSessionNonce() {
        let nonces = [
            "",
            "0123456789abcdef0123456789abcde",
            "0123456789abcdef0123456789abcdef0",
            "0123456789ABCDEF0123456789ABCDEF",
            "g123456789abcdef0123456789abcdef",
        ]

        for nonce in nonces {
            XCTAssertThrowsError(
                try RelayHandshake.parse(
                    "AETHERLINK_RELAY runtime relay-123 crypto=2 session_nonce=\(nonce) " +
                        "ephemeral_key=\(ephemeralKey) runtime_key_fingerprint=\(runtimeFingerprint)\n"
                ),
                nonce
            ) { error in
                XCTAssertEqual(error as? RelayHandshakeError, .invalidSessionNonce)
            }
            XCTAssertThrowsError(
                try RelayHandshake(
                    role: .runtime,
                    relayID: "relay-123",
                    sessionNonce: nonce,
                    ephemeralKey: ephemeralKey,
                    runtimeKeyFingerprint: runtimeFingerprint
                ),
                nonce
            ) { error in
                XCTAssertEqual(error as? RelayHandshakeError, .invalidSessionNonce)
            }
        }
    }

    func testRejectsNonCanonicalEphemeralKeyShapeWithoutCheckingCurve() throws {
        let invalidKeys = [
            "04" + String(repeating: "0", count: 127),
            "04" + String(repeating: "0", count: 129),
            "04" + String(repeating: "A", count: 128),
            "03" + String(repeating: "0", count: 128),
            "04" + String(repeating: "g", count: 128),
        ]

        for key in invalidKeys {
            XCTAssertThrowsError(
                try RelayHandshake(
                    role: .runtime,
                    relayID: "relay-123",
                    sessionNonce: sessionNonce,
                    ephemeralKey: key,
                    runtimeKeyFingerprint: runtimeFingerprint
                ),
                key
            ) { error in
                XCTAssertEqual(error as? RelayHandshakeError, .invalidEphemeralKey)
            }
        }

        let shapeOnlyKey = "04" + String(repeating: "0", count: 128)
        XCTAssertNoThrow(
            try RelayHandshake(
                role: .runtime,
                relayID: "relay-123",
                sessionNonce: sessionNonce,
                ephemeralKey: shapeOnlyKey,
                runtimeKeyFingerprint: runtimeFingerprint
            )
        )
        XCTAssertNoThrow(
            try RelayHandshake.parse(
                "AETHERLINK_RELAY runtime relay-123 crypto=2 session_nonce=\(sessionNonce) " +
                    "ephemeral_key=\(shapeOnlyKey) runtime_key_fingerprint=\(runtimeFingerprint)\n"
            )
        )
    }

    func testBuildsExactCryptoV2ControlLines() {
        let nonce = "fedcba9876543210fedcba9876543210"

        XCTAssertEqual(
            RelayHandshake.cryptoV2RegisteredLine,
            Data("AETHERLINK_RELAY registered crypto=2\n".utf8)
        )
        XCTAssertEqual(
            RelayHandshake.cryptoV2ReadyLine(
                peerSessionNonce: nonce,
                peerEphemeralKey: ephemeralKey
            ),
            Data(
                ("AETHERLINK_RELAY ready crypto=2 peer_session_nonce=\(nonce) " +
                    "peer_ephemeral_key=\(ephemeralKey)\n").utf8
            )
        )
    }

    func testRejectsUnknownRole() {
        XCTAssertThrowsError(try RelayHandshake.parse("AETHERLINK_RELAY observer relay-123\n")) { error in
            XCTAssertEqual(error as? RelayHandshakeError, .invalidRole)
        }
    }

    func testRejectsBlankRelayID() {
        XCTAssertThrowsError(try RelayHandshake.parse("AETHERLINK_RELAY runtime \n"))
        XCTAssertThrowsError(try RelayHandshake(role: .runtime, relayID: ""))
    }

    func testRejectsNonCanonicalRelayID() {
        let relayIDs = [
            "relay 123",
            String(repeating: "r", count: relayControlLineRelayIDMaxCharacters + 1),
            "https://relay.example.test/room?route_token=secret",
            "relay.example.test:443",
            "user@relay-id",
            "relay/id",
            "relay\\id",
            "relay#fragment",
        ]

        for relayID in relayIDs {
            XCTAssertThrowsError(try RelayHandshake(role: .runtime, relayID: relayID), relayID) { error in
                XCTAssertEqual(error as? RelayHandshakeError, .invalidRelayID)
            }
        }
        for relayID in relayIDs where relayID.rangeOfCharacter(from: .whitespacesAndNewlines) == nil {
            XCTAssertThrowsError(try RelayHandshake.parse("AETHERLINK_RELAY runtime \(relayID)\n"), relayID) { error in
                XCTAssertEqual(error as? RelayHandshakeError, .invalidRelayID)
            }
        }
    }

    func testServerLineFramingRequiresNewlineForRelayHandshake() throws {
        XCTAssertThrowsError(
            try RelayServerLineFraming.decode(Data("AETHERLINK_RELAY runtime relay-1".utf8))
        ) { error in
            XCTAssertEqual(error as? RelayServerError, .handshakeReadFailed)
        }
        XCTAssertNoThrow(
            try RelayServerLineFraming.decode(Data("AETHERLINK_RELAY runtime relay-1\n".utf8))
        )
    }

    func testServerLineFramingRequiresNewlineForAllocationRequest() throws {
        XCTAssertThrowsError(
            try RelayServerLineFraming.decode(Data("AETHERLINK_RELAY allocate route-token-1".utf8))
        ) { error in
            XCTAssertEqual(error as? RelayServerError, .handshakeReadFailed)
        }
        XCTAssertNoThrow(
            try RelayServerLineFraming.decode(Data("AETHERLINK_RELAY allocate route-token-1\n".utf8))
        )
    }
}
