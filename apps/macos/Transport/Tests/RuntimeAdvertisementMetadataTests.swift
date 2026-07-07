import Foundation
import XCTest
@testable import Transport

final class RuntimeAdvertisementMetadataTests: XCTestCase {
    func testRuntimeAdvertisementMetadataPublishesOnlyRouteTokenIdentityHint() {
        let metadata = RuntimeAdvertisementMetadata(
            version: " 1 ",
            routeToken: "route-token-1",
            deviceID: " runtime-device-1 ",
            fingerprint: " fingerprint-1 ",
            app: " AetherLink "
        )

        XCTAssertEqual(
            metadata.txtRecord,
            [
                "version": "1",
                "app": "AetherLink",
                "route_token": "route-token-1",
            ]
        )
        XCTAssertEqual(metadata.txtRecordData["route_token"], Data("route-token-1".utf8))
        XCTAssertNil(metadata.txtRecord["device_id"])
        XCTAssertNil(metadata.txtRecord["fingerprint"])
    }

    func testRejectsWhitespaceMutatedRouteTokenInsteadOfNormalizing() {
        let leadingWhitespace = RuntimeAdvertisementMetadata(routeToken: " route-token-1")
        let trailingWhitespace = RuntimeAdvertisementMetadata(routeToken: "route-token-1 ")
        let embeddedWhitespace = RuntimeAdvertisementMetadata(routeToken: "route token 1")
        let controlWhitespace = RuntimeAdvertisementMetadata(routeToken: "route-token-1\n")

        XCTAssertNil(leadingWhitespace.txtRecord["route_token"])
        XCTAssertNil(trailingWhitespace.txtRecord["route_token"])
        XCTAssertNil(embeddedWhitespace.txtRecord["route_token"])
        XCTAssertNil(controlWhitespace.txtRecord["route_token"])
    }

    func testRejectsUnsafeDiscoveryTxtMetadata() {
        let oversizedToken = String(repeating: "r", count: 161)
        let metadata = RuntimeAdvertisementMetadata(
            version: "1\n2",
            routeToken: oversizedToken,
            deviceID: "https://runtime.example.test:43170",
            fingerprint: "relay_secret=secret-1",
            app: "backend_url=http://127.0.0.1:11434"
        )

        XCTAssertEqual(metadata.txtRecord, [:])
        XCTAssertEqual(metadata.txtRecordData, [:])
    }

    func testRejectsRuntimeCommandAndBackendHintsFromDiscoveryTxtMetadata() {
        let metadata = RuntimeAdvertisementMetadata(
            version: "1",
            routeToken: "chat.send",
            deviceID: "runtime.local:1234",
            fingerprint: "memory.list",
            app: "AetherLink"
        )

        XCTAssertEqual(metadata.txtRecord["version"], "1")
        XCTAssertEqual(metadata.txtRecord["app"], "AetherLink")
        XCTAssertNil(metadata.txtRecord["route_token"])
        XCTAssertNil(metadata.txtRecord["device_id"])
        XCTAssertNil(metadata.txtRecord["fingerprint"])
    }

    func testRejectsRequestedRouteTokenHintsFromDiscoveryTxtMetadata() {
        let metadata = RuntimeAdvertisementMetadata(
            version: "requested-route-token=debug-token",
            routeToken: "requested_route_token=debug-token",
            app: "AetherLink requested_route_token"
        )

        XCTAssertEqual(metadata.txtRecord, [:])
        XCTAssertEqual(metadata.txtRecordData, [:])
    }
}
