import XCTest
@testable import RelayServerCore

final class RelayProbeTests: XCTestCase {
    func testParsesProbeRequest() throws {
        let request = try RelayProbeRequest.parse("AETHERLINK_RELAY probe relay-123\n")

        XCTAssertEqual(request.relayID, "relay-123")
        XCTAssertTrue(RelayProbeRequest.isProbeLine("AETHERLINK_RELAY probe relay-123\n"))
    }

    func testRejectsMalformedProbeRequest() {
        XCTAssertThrowsError(try RelayProbeRequest.parse("AETHERLINK_RELAY probe\n"))
        XCTAssertThrowsError(try RelayProbeRequest.parse("AETHERLINK_RELAY probe relay-123 extra\n"))
        XCTAssertThrowsError(try RelayProbeRequest.parse("AETHERLINK_RELAY runtime relay-123\n"))
        XCTAssertFalse(RelayProbeRequest.isProbeLine("AETHERLINK_RELAY runtime relay-123\n"))
    }

    func testFormatsProbeResponseLine() {
        let waiting = String(
            decoding: RelayProbeResponse(known: true, runtimeWaiting: true).responseLine(),
            as: UTF8.self
        )
        let missing = String(
            decoding: RelayProbeResponse(known: false, runtimeWaiting: false).responseLine(),
            as: UTF8.self
        )

        XCTAssertEqual(waiting, "AETHERLINK_RELAY probe known=1 runtime_waiting=1\n")
        XCTAssertEqual(missing, "AETHERLINK_RELAY probe known=0 runtime_waiting=0\n")
    }

    func testServerLineFramingRequiresNewlineForProbeRequest() throws {
        XCTAssertThrowsError(
            try RelayServerLineFraming.decode(Data("AETHERLINK_RELAY probe relay-1".utf8))
        ) { error in
            XCTAssertEqual(error as? RelayServerError, .handshakeReadFailed)
        }
        XCTAssertNoThrow(
            try RelayServerLineFraming.decode(Data("AETHERLINK_RELAY probe relay-1\n".utf8))
        )
    }
}
