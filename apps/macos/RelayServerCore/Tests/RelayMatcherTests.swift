import XCTest
@testable import RelayServerCore

final class RelayMatcherTests: XCTestCase {
    func testWaitsUntilOppositeRoleWithSameRelayIDArrives() {
        let matcher = RelayMatcher()
        let runtime = RelayPeerRegistration(role: .runtime, relayID: "shared")
        let client = RelayPeerRegistration(role: .client, relayID: "shared")

        XCTAssertEqual(matcher.register(runtime), .waiting(replaced: nil))
        XCTAssertEqual(matcher.register(client), .matched(runtime: runtime, client: client))
        XCTAssertEqual(matcher.pendingCount(), 0)
    }

    func testDoesNotMatchDifferentRelayIDs() {
        let matcher = RelayMatcher()
        let runtime = RelayPeerRegistration(role: .runtime, relayID: "one")
        let client = RelayPeerRegistration(role: .client, relayID: "two")

        XCTAssertEqual(matcher.register(runtime), .waiting(replaced: nil))
        XCTAssertEqual(matcher.register(client), .waiting(replaced: nil))
        XCTAssertEqual(matcher.pendingCount(), 2)
    }

    func testReplacesEarlierPeerWithSameRoleAndRelayID() {
        let matcher = RelayMatcher()
        let firstRuntime = RelayPeerRegistration(role: .runtime, relayID: "shared")
        let secondRuntime = RelayPeerRegistration(role: .runtime, relayID: "shared")
        let client = RelayPeerRegistration(role: .client, relayID: "shared")

        XCTAssertEqual(matcher.register(firstRuntime), .waiting(replaced: nil))
        XCTAssertEqual(matcher.register(secondRuntime), .waiting(replaced: firstRuntime))
        XCTAssertEqual(matcher.register(client), .matched(runtime: secondRuntime, client: client))
    }

    func testRuntimeWaitingProbeDoesNotConsumePendingRuntime() {
        let matcher = RelayMatcher()
        let runtime = RelayPeerRegistration(role: .runtime, relayID: "shared")
        let client = RelayPeerRegistration(role: .client, relayID: "shared")

        XCTAssertEqual(matcher.register(runtime), .waiting(replaced: nil))
        XCTAssertTrue(matcher.hasWaitingRuntime(relayID: "shared"))
        XCTAssertEqual(matcher.pendingCount(relayID: "shared"), 1)

        XCTAssertTrue(matcher.hasWaitingRuntime(relayID: "shared"))
        XCTAssertEqual(matcher.register(client), .matched(runtime: runtime, client: client))
        XCTAssertFalse(matcher.hasWaitingRuntime(relayID: "shared"))
        XCTAssertEqual(matcher.pendingCount(relayID: "shared"), 0)
    }

    func testRuntimeWaitingProbeIgnoresWaitingClient() {
        let matcher = RelayMatcher()
        let client = RelayPeerRegistration(role: .client, relayID: "shared")

        XCTAssertEqual(matcher.register(client), .waiting(replaced: nil))
        XCTAssertFalse(matcher.hasWaitingRuntime(relayID: "shared"))
        XCTAssertEqual(matcher.pendingCount(relayID: "shared"), 1)
    }
}
