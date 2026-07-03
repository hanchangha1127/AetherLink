import XCTest
@testable import Pairing

final class PairingCoordinatorTests: XCTestCase {
    func testPairingQRCodeRejectsInvalidRelayScopeBeforeEmission() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            routeToken: "route-token-1",
            relayHost: "relay.example.test",
            relayPort: 43171,
            relayID: "relay-id-1",
            relaySecret: "relay-secret-1",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "relay-nonce-1",
            relayScope: "REMOTE"
        )

        XCTAssertNil(session.relayScope)
        let queryItems = try parseQueryItems(from: session.qrPayload)
        let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)
        XCTAssertEqual(queryItems["relay_host"], "relay.example.test")
        XCTAssertEqual(queryItems["relay_port"], "43171")
        XCTAssertNil(queryItems["relay_scope"])
        XCTAssertNil(queryItems["route_scope"])
        XCTAssertNil(compactQueryItems["rsc"])
        XCTAssertFalse(session.qrPayload.contains("REMOTE"))
        XCTAssertFalse(session.compactQRCodePayload.contains("REMOTE"))
    }

    func testPairingQRCodeEmitsOnlyAllowedRelayScopes() throws {
        for relayScope in ["remote", "private_overlay", "usb_reverse"] {
            let coordinator = PairingCoordinator()
            let session = coordinator.beginPairing(
                macDeviceID: "runtime-1",
                macName: "AetherLink Runtime",
                fingerprint: "runtime-fingerprint",
                routeToken: "route-token-1",
                relayHost: "relay.example.test",
                relayPort: 43171,
                relayID: "relay-id-1",
                relaySecret: "relay-secret-1",
                relayExpiresAtEpochMillis: 4_102_444_800_000,
                relayNonce: "relay-nonce-1",
                relayScope: relayScope
            )

            XCTAssertEqual(session.relayScope, relayScope)
            let queryItems = try parseQueryItems(from: session.qrPayload)
            let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)
            XCTAssertEqual(queryItems["relay_scope"], relayScope)
            XCTAssertEqual(compactQueryItems["rsc"], relayScope)
        }
    }

    func testPairingQRCodeDirectEndpointScopeDefaultsToLocalDiagnosticOnly() throws {
        let coordinator = PairingCoordinator()
        let defaultSession = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            routeToken: "route-token-1",
            host: "192.168.1.10",
            port: 43170
        )
        XCTAssertEqual(defaultSession.relayScope, "local_diagnostic")
        XCTAssertEqual(try parseQueryItems(from: defaultSession.qrPayload)["route_scope"], "local_diagnostic")
        XCTAssertEqual(try parseQueryItems(from: defaultSession.compactQRCodePayload)["rsc"], "local_diagnostic")

        let invalidScopeSession = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            routeToken: "route-token-1",
            host: "192.168.1.10",
            port: 43170,
            relayScope: "remote"
        )
        XCTAssertNil(invalidScopeSession.relayScope)
        XCTAssertNil(try parseQueryItems(from: invalidScopeSession.qrPayload)["route_scope"])
        XCTAssertNil(try parseQueryItems(from: invalidScopeSession.compactQRCodePayload)["rsc"])
    }

    private func parseQueryItems(from payload: String) throws -> [String: String] {
        let components = try XCTUnwrap(URLComponents(string: payload))
        return try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }
    }
}
