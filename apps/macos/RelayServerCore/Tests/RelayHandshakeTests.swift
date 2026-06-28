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
