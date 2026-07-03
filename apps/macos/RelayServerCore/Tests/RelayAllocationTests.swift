import XCTest
@testable import RelayServerCore

final class RelayAllocationTests: XCTestCase {
    func testRelayServerConfigurationUsesShortDefaultAllocationTTL() {
        let configuration = RelayServerConfiguration()

        XCTAssertEqual(configuration.allocationTTLSeconds, 15 * 60)
        XCTAssertTrue(configuration.requiresAllocation)
    }

    func testRelayServerConfigurationCanExplicitlyAllowLegacyUnallocatedRelays() {
        let configuration = RelayServerConfiguration(requiresAllocation: false)

        XCTAssertFalse(configuration.requiresAllocation)
    }

    func testRelayBindExposureAllowsOnlyLoopbackWithoutAllocationToken() throws {
        let hosts = ["127.0.0.1", "127.0.0.2", "::1", "[::1]", "localhost", "LOCALHOST"]

        for host in hosts {
            XCTAssertFalse(RelayBindExposure.requiresAllocationToken(host: host), host)
            XCTAssertNoThrow(try RelayServerConfiguration(host: host).validate(), host)
        }
    }

    func testRelayBindExposureRequiresTokenForWildcardAndNonLoopbackBinds() {
        let hosts = [
            "",
            "0.0.0.0",
            "::",
            "192.168.1.10",
            "100.64.1.10",
            "8.8.8.8",
            "relay.example.test"
        ]

        for host in hosts {
            XCTAssertTrue(RelayBindExposure.requiresAllocationToken(host: host), host)
            XCTAssertThrowsError(try RelayServerConfiguration(host: host).validate(), host) { error in
                XCTAssertEqual(
                    error as? RelayServerError,
                    .allocationTokenRequiredForExposedBind(RelayBindExposure.normalizedHost(host))
                )
            }
        }
    }

    func testRelayBindExposureAllowsWildcardAndNonLoopbackBindsWithAllocationToken() {
        let hosts = ["0.0.0.0", "::", "192.168.1.10", "relay.example.test"]

        for host in hosts {
            XCTAssertNoThrow(
                try RelayServerConfiguration(host: host, allocationToken: "allocation-token-1").validate(),
                host
            )
        }
    }

    func testRelayConfigurationRejectsInvalidAllocationTokens() {
        for token in ["", " ", "token value", "token\nvalue"] {
            XCTAssertThrowsError(
                try RelayServerConfiguration(host: "127.0.0.1", allocationToken: token).validate(),
                token
            ) { error in
                XCTAssertEqual(error as? RelayServerError, .invalidAllocationToken)
            }
        }
    }

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

    func testParsesAllocationRequestWithBase64RequestedRelaySecret() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 secret+with/symbols= allocation_token=allocation-token-1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertEqual(request.requestedRelaySecret, "secret+with/symbols=")
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
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

    func testParsesAllocationRequestWithAuthAlias() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 auth=allocation-token-1 preflight=1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertNil(request.requestedRelaySecret)
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
        XCTAssertTrue(request.isPreflight)
        XCTAssertFalse(request.shouldPersistAllocation)
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

    func testRejectsBlankAllocationTokenAndRelaySecret() {
        XCTAssertThrowsError(
            try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token-1 allocation_token=\n")
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidAllocationToken)
        }
        XCTAssertThrowsError(
            try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token-1 auth=\n")
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidAllocationToken)
        }
        XCTAssertThrowsError(
            try RelayAllocationRequest(routeToken: "route-token-1", requestedRelaySecret: "")
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidRelaySecret)
        }
        XCTAssertThrowsError(
            try RelayAllocationRequest(routeToken: "route-token-1", requestedRelaySecret: "secret value")
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidRelaySecret)
        }
    }

    func testRejectsUnexpectedAllocationRequestMetadata() {
        for line in [
            "AETHERLINK_RELAY allocate route-token-1 backend_url=http://127.0.0.1:11434/api/tags allocation_token=allocation-token-1\n",
            "AETHERLINK_RELAY allocate route-token-1 provider_url=https://provider.example.test/v1/models allocation_token=allocation-token-1\n",
            "AETHERLINK_RELAY allocate route-token-1 requested_route_token=leaked-route-token allocation_token=allocation-token-1\n",
            "AETHERLINK_RELAY allocate route-token-1 relay_secret_debug=leaked-relay-secret allocation_token=allocation-token-1\n"
        ] {
            XCTAssertThrowsError(
                try RelayAllocationRequest.parse(line)
            ) { error in
                XCTAssertEqual(error as? RelayAllocationError, .invalidFormat)
            }
        }
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

    func testRejectsInvalidAllocationResponseLineFields() {
        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(allocationResponseLine(relayID: "relay 1"))
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidRelayID)
        }
        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(allocationResponseLine(relaySecret: "secret value"))
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidRelaySecret)
        }
        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(allocationResponseLine(relayExpiresAtEpochMillis: 0))
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidExpiration)
        }
        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(allocationResponseLine(relayNonce: "nonce value"))
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidNonce)
        }
    }

    func testRejectsUnexpectedAllocationResponseLineMetadata() {
        let line = """
        \(RelayAllocation.responsePrefix){"relay_id":"rt1-response","relay_secret":"secret-1","relay_expires_at":4102444800000,"relay_nonce":"nonce-1","requested_route_token":"leaked-route-token","backend_url":"http://127.0.0.1:11434/api/tags","provider_url":"https://provider.example.test/v1/models","allocation_token":"leaked-allocation-token","relay_secret_debug":"leaked-relay-secret"}
        """

        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(line)
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .unexpectedResponseMetadata)
        }
    }

    func testAllocationDerivesOpaqueStableRelayIDFromRouteTokenAndRequestedSecret() throws {
        let allocation = try RelayAllocation.make(
            routeToken: "route-token-1",
            requestedRelaySecret: "secret-1",
            now: Date(timeIntervalSince1970: 1),
            validFor: 60
        )
        let second = try RelayAllocation.make(
            routeToken: "route-token-1",
            requestedRelaySecret: "secret-2",
            now: Date(timeIntervalSince1970: 2),
            validFor: 60
        )
        let differentRoute = try RelayAllocation.make(
            routeToken: "route-token-2",
            requestedRelaySecret: "secret-1",
            now: Date(timeIntervalSince1970: 1),
            validFor: 60
        )

        XCTAssertEqual(allocation.relayID, try RelayAllocation.relayID(forRouteToken: "route-token-1"))
        XCTAssertEqual(second.relayID, allocation.relayID)
        XCTAssertNotEqual(differentRoute.relayID, allocation.relayID)
        XCTAssertTrue(allocation.relayID.hasPrefix("rt1-"))
        XCTAssertFalse(allocation.relayID.contains("route-token-1"))
        XCTAssertEqual(allocation.relaySecret, "secret-1")
        XCTAssertEqual(allocation.relayExpiresAtEpochMillis, 61_000)
        XCTAssertFalse(allocation.relayNonce.isEmpty)
    }

    func testAllocationRegistryPersistsOpaqueRelayIDWithoutRawRouteToken() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let allocation = try RelayAllocation.make(
            routeToken: "route-token-that-must-not-persist",
            requestedRelaySecret: "secret-that-must-not-persist",
            now: Date(timeIntervalSince1970: 1_700_000_000),
            validFor: 60
        )

        RelayAllocationRegistry(persistenceURL: storeURL).store(allocation)
        let persisted = try String(contentsOf: storeURL, encoding: .utf8)

        XCTAssertTrue(persisted.contains(allocation.relayID))
        XCTAssertFalse(persisted.contains("route-token-that-must-not-persist"))
        XCTAssertFalse(persisted.contains("secret-that-must-not-persist"))
        XCTAssertTrue(RelayAllocationRegistry(persistenceURL: storeURL).isValid(
            relayID: allocation.relayID,
            now: Date(timeIntervalSince1970: 1_700_000_001)
        ))
    }

    func testAllocationRegistryIgnoresNonAdvancingRenewalForStableRelayID() throws {
        let registry = RelayAllocationRegistry()
        let relayID = try RelayAllocation.relayID(forRouteToken: "route-token-renewal")
        let current = try RelayAllocation(
            relayID: relayID,
            relaySecret: "secret-1",
            relayExpiresAtEpochMillis: 10_000,
            relayNonce: "nonce-current"
        )
        let older = try RelayAllocation(
            relayID: relayID,
            relaySecret: "secret-2",
            relayExpiresAtEpochMillis: 9_000,
            relayNonce: "nonce-older"
        )
        let sameExpiry = try RelayAllocation(
            relayID: relayID,
            relaySecret: "secret-3",
            relayExpiresAtEpochMillis: 10_000,
            relayNonce: "nonce-same-expiry"
        )
        let reusedNonce = try RelayAllocation(
            relayID: relayID,
            relaySecret: "secret-4",
            relayExpiresAtEpochMillis: 12_000,
            relayNonce: "nonce-current"
        )

        XCTAssertTrue(registry.store(current))
        XCTAssertFalse(registry.store(older))
        XCTAssertFalse(registry.store(sameExpiry))
        XCTAssertFalse(registry.store(reusedNonce))

        XCTAssertTrue(registry.isValid(relayID: relayID, now: Date(timeIntervalSince1970: 9)))
        XCTAssertFalse(registry.isValid(relayID: relayID, now: Date(timeIntervalSince1970: 11)))
    }

    func testAllocationRegistryAcceptsAdvancingRenewalWithFreshNonce() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let relayID = try RelayAllocation.relayID(forRouteToken: "route-token-renewal")
        let current = try RelayAllocation(
            relayID: relayID,
            relaySecret: "secret-1",
            relayExpiresAtEpochMillis: 10_000,
            relayNonce: "nonce-current"
        )
        let renewed = try RelayAllocation(
            relayID: relayID,
            relaySecret: "secret-2",
            relayExpiresAtEpochMillis: 12_000,
            relayNonce: "nonce-renewed"
        )

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertTrue(registry.store(current))
        XCTAssertTrue(registry.store(renewed))
        XCTAssertTrue(registry.isValid(relayID: relayID, now: Date(timeIntervalSince1970: 11)))
        let persisted = try String(contentsOf: storeURL, encoding: .utf8)
        XCTAssertTrue(persisted.contains("nonce-renewed"))
        XCTAssertFalse(persisted.contains("nonce-current"))
    }

    func testAllocationRegistryLoadsDuplicatePersistedRelayIDsWithAdvancingTicket() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let relayID = try RelayAllocation.relayID(forRouteToken: "route-token-reload")
        try writeAllocationTicketsJSON(
            [
                [
                    "relay_id": relayID,
                    "relay_expires_at": 10_000,
                    "relay_nonce": "nonce-current"
                ],
                [
                    "relay_id": relayID,
                    "relay_expires_at": 12_000,
                    "relay_nonce": "nonce-renewed"
                ],
                [
                    "relay_id": relayID,
                    "relay_expires_at": 13_000,
                    "relay_nonce": "nonce-renewed"
                ]
            ],
            to: storeURL
        )

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertEqual(registry.count(now: Date(timeIntervalSince1970: 11)), 1)
        XCTAssertTrue(registry.isValid(relayID: relayID, now: Date(timeIntervalSince1970: 11)))
        XCTAssertFalse(registry.isValid(relayID: relayID, now: Date(timeIntervalSince1970: 13)))
    }

    func testAllocationRegistrySkipsMalformedPersistedTicketsOnLoad() throws {
        let storeURL = try temporaryAllocationStoreURL()
        try writeAllocationTicketsJSON(
            [
                [
                    "relay_id": "",
                    "relay_expires_at": 20_000,
                    "relay_nonce": "nonce-blank-relay"
                ],
                [
                    "relay_id": "relay whitespace",
                    "relay_expires_at": 20_000,
                    "relay_nonce": "nonce-whitespace-relay"
                ],
                [
                    "relay_id": "relay-bad-expiration",
                    "relay_expires_at": 0,
                    "relay_nonce": "nonce-bad-expiration"
                ],
                [
                    "relay_id": "relay-bad-nonce",
                    "relay_expires_at": 20_000,
                    "relay_nonce": "nonce bad"
                ],
                [
                    "relay_id": "relay-loadable",
                    "relay_expires_at": 20_000,
                    "relay_nonce": "nonce-loadable"
                ]
            ],
            to: storeURL
        )

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertEqual(registry.count(now: Date(timeIntervalSince1970: 10)), 1)
        XCTAssertTrue(registry.isValid(relayID: "relay-loadable", now: Date(timeIntervalSince1970: 10)))
        XCTAssertFalse(registry.isValid(relayID: "relay-bad-expiration", now: Date(timeIntervalSince1970: 10)))
        XCTAssertFalse(registry.isValid(relayID: "relay-bad-nonce", now: Date(timeIntervalSince1970: 10)))
    }

    func testAllocationRegistrySkipsPersistedTicketsWithUnexpectedMetadata() throws {
        let storeURL = try temporaryAllocationStoreURL()
        try writeAllocationTicketsJSON(
            [
                [
                    "relay_id": "relay-with-metadata",
                    "relay_expires_at": 20_000,
                    "relay_nonce": "nonce-with-metadata",
                    "relay_secret": "leaked-relay-secret",
                    "requested_route_token": "leaked-route-token",
                    "backend_url": "http://127.0.0.1:11434/api/tags",
                    "provider_url": "https://provider.example.test/v1/models",
                    "allocation_token": "leaked-allocation-token"
                ],
                [
                    "relay_id": "relay-loadable",
                    "relay_expires_at": 20_000,
                    "relay_nonce": "nonce-loadable"
                ]
            ],
            to: storeURL
        )

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertEqual(registry.count(now: Date(timeIntervalSince1970: 10)), 1)
        XCTAssertFalse(registry.isValid(relayID: "relay-with-metadata", now: Date(timeIntervalSince1970: 10)))
        XCTAssertTrue(registry.isValid(relayID: "relay-loadable", now: Date(timeIntervalSince1970: 10)))
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

    private func allocationResponseLine(
        relayID: String = "relay-1",
        relaySecret: String = "secret-1",
        relayExpiresAtEpochMillis: Int64 = 4_102_444_800_000,
        relayNonce: String = "nonce-1"
    ) -> String {
        """
        \(RelayAllocation.responsePrefix){"relay_id":"\(relayID)","relay_secret":"\(relaySecret)","relay_expires_at":\(relayExpiresAtEpochMillis),"relay_nonce":"\(relayNonce)"}
        """
    }

    private func writeAllocationTicketsJSON(_ tickets: [[String: Any]], to url: URL) throws {
        let data = try JSONSerialization.data(withJSONObject: tickets, options: [.prettyPrinted, .sortedKeys])
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try data.write(to: url)
    }
}
