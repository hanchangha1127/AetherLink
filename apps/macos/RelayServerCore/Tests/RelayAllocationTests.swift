import XCTest
@testable import RelayServerCore

final class RelayAllocationTests: XCTestCase {
    func testParsesAllocationRequest() throws {
        let request = try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token-1\n")

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertNil(request.requestedRelaySecret)
        XCTAssertNil(request.allocationToken)
        XCTAssertTrue(RelayAllocationRequest.isAllocationLine("AETHERLINK_RELAY allocate route-token-1\n"))
    }

    func testParsesAllocationRequestWithRequestedRelaySecret() throws {
        let request = try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token-1 secret-1\n")

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertEqual(request.requestedRelaySecret, "secret-1")
        XCTAssertNil(request.allocationToken)
    }

    func testParsesAllocationRequestWithAllocationToken() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 secret-1 allocation_token=allocation-token-1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertEqual(request.requestedRelaySecret, "secret-1")
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
    }

    func testParsesAllocationRequestWithAllocationTokenOnly() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 allocation_token=allocation-token-1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertNil(request.requestedRelaySecret)
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
        XCTAssertFalse(request.isPreflight)
        XCTAssertTrue(request.shouldPersistAllocation)
    }

    func testParsesPreflightAllocationRequest() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 allocation_token=allocation-token-1 preflight=1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertNil(request.requestedRelaySecret)
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
        XCTAssertTrue(request.isPreflight)
        XCTAssertFalse(request.shouldPersistAllocation)
    }

    func testParsesPreflightAllocationRequestWithRequestedSecret() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 secret-1 preflight=true allocation_token=allocation-token-1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertEqual(request.requestedRelaySecret, "secret-1")
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
        XCTAssertTrue(request.isPreflight)
        XCTAssertFalse(request.shouldPersistAllocation)
    }

    func testRejectsMalformedAllocationRequest() {
        XCTAssertThrowsError(try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate\n"))
        XCTAssertThrowsError(try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route token extra\n"))
        XCTAssertThrowsError(try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token secret-1 allocation_token=one allocation_token=two\n"))
        XCTAssertThrowsError(try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token preflight=1 preflight=true\n"))
        XCTAssertFalse(RelayAllocationRequest.isAllocationLine("AETHERLINK_RELAY runtime relay-1\n"))
    }

    func testAllocationResponseRoundTripsAsLine() throws {
        let allocation = try RelayAllocation(
            relayID: "relay-1",
            relaySecret: "secret-1",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "nonce-1"
        )

        let line = String(decoding: try allocation.responseLine(), as: UTF8.self)
        let parsed = try RelayAllocation.parseResponseLine(line)

        XCTAssertEqual(parsed, allocation)
    }

    func testAllocationCanUseStableRouteTokenAndRequestedSecret() throws {
        let allocation = try RelayAllocation.make(
            routeToken: "route-token-1",
            requestedRelaySecret: "secret-1",
            now: Date(timeIntervalSince1970: 1),
            validFor: 60
        )

        XCTAssertEqual(allocation.relayID, "route-token-1")
        XCTAssertEqual(allocation.relaySecret, "secret-1")
        XCTAssertEqual(allocation.relayExpiresAtEpochMillis, 61_000)
        XCTAssertFalse(allocation.relayNonce.isEmpty)
    }

    func testAllocationRegistryExpiresAndRemovesRelayIDs() throws {
        let registry = RelayAllocationRegistry()
        let allocation = try RelayAllocation(
            relayID: "relay-1",
            relaySecret: "secret-1",
            relayExpiresAtEpochMillis: 2_000,
            relayNonce: "nonce-1"
        )

        registry.store(allocation)

        XCTAssertTrue(registry.isValid(relayID: "relay-1", now: Date(timeIntervalSince1970: 1)))
        XCTAssertFalse(registry.isValid(relayID: "relay-1", now: Date(timeIntervalSince1970: 3)))
        XCTAssertEqual(registry.count(now: Date(timeIntervalSince1970: 3)), 0)
    }

    func testAllocationRegistryPersistsAndReloadsRelayIDs() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let allocation = try RelayAllocation(
            relayID: "relay-persisted",
            relaySecret: "secret-that-must-not-be-persisted",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "nonce-1"
        )

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)
        registry.store(allocation)

        let reloaded = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertTrue(reloaded.isValid(
            relayID: "relay-persisted",
            now: Date(timeIntervalSince1970: 1_700_000_000)
        ))
        XCTAssertEqual(reloaded.count(now: Date(timeIntervalSince1970: 1_700_000_000)), 1)
        let persisted = try String(contentsOf: storeURL, encoding: .utf8)
        XCTAssertTrue(persisted.contains("relay-persisted"))
        XCTAssertFalse(persisted.contains("secret-that-must-not-be-persisted"))
    }

    func testAllocationRegistryPrunesExpiredPersistedRelayIDs() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let allocation = try RelayAllocation(
            relayID: "relay-expired",
            relaySecret: "secret-1",
            relayExpiresAtEpochMillis: 2_000,
            relayNonce: "nonce-1"
        )
        RelayAllocationRegistry(persistenceURL: storeURL).store(allocation)

        let reloaded = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertFalse(reloaded.isValid(relayID: "relay-expired", now: Date(timeIntervalSince1970: 3)))
        XCTAssertEqual(reloaded.count(now: Date(timeIntervalSince1970: 3)), 0)
        XCTAssertEqual(
            RelayAllocationRegistry(persistenceURL: storeURL).count(now: Date(timeIntervalSince1970: 3)),
            0
        )
    }

    private func temporaryAllocationStoreURL() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("AetherLinkRelayTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock {
            try? FileManager.default.removeItem(at: directory)
        }
        return directory.appendingPathComponent("allocations.json")
    }
}
