import XCTest
@testable import RelayServerCore

final class RelayHandshakeTests: XCTestCase {
    func testParsesRuntimeHandshake() throws {
        let handshake = try RelayHandshake.parse("AETHERLINK_RELAY runtime relay-123\n")

        XCTAssertEqual(handshake.role, .runtime)
        XCTAssertEqual(handshake.relayID, "relay-123")
    }

    func testParsesClientHandshake() throws {
        let handshake = try RelayHandshake.parse("AETHERLINK_RELAY client relay-123")

        XCTAssertEqual(handshake.role, .client)
        XCTAssertEqual(handshake.relayID, "relay-123")
    }

    func testRejectsMalformedHandshake() {
        XCTAssertThrowsError(try RelayHandshake.parse("HELLO runtime relay-123\n"))
        XCTAssertThrowsError(try RelayHandshake.parse("AETHERLINK_RELAY runtime relay-123 extra\n"))
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
