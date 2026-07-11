import Foundation
@testable import CompanionCore
import XCTest

final class PairScopedRelayRouteStoreTests: XCTestCase {
    private static let fingerprintA = String(repeating: "a", count: 64)
    private static let fingerprintB = String(repeating: "b", count: 64)
    private static let relayIDA = "rt2-\(String(repeating: "c", count: 64))"
    private static let relayIDB = "rt2-\(String(repeating: "d", count: 64))"

    func testRoundTripSurvivesStoreRestart() throws {
        let defaults = try isolatedDefaults()
        let secrets = InMemoryPairScopedRelaySecretStore()
        let route = try makeRoute()
        let firstStore = PairScopedRelayRouteStore(
            userDefaults: defaults,
            relaySecretStore: secrets
        )

        let saved = try firstStore.upsert(route, relaySecret: "relay-secret-a")
        XCTAssertEqual(saved, ResolvedPairScopedRelayRoute(
            route: route,
            relaySecret: "relay-secret-a"
        ))

        let restartedStore = PairScopedRelayRouteStore(
            userDefaults: defaults,
            relaySecretStore: secrets
        )
        XCTAssertEqual(restartedStore.loadAll(), [saved])
    }

    func testSecretIsAbsentFromClosedDefaultsEnvelope() throws {
        let defaults = try isolatedDefaults()
        let secrets = InMemoryPairScopedRelaySecretStore()
        let store = PairScopedRelayRouteStore(
            userDefaults: defaults,
            relaySecretStore: secrets
        )
        try store.upsert(try makeRoute(), relaySecret: "sensitive-relay-secret")

        let data = try XCTUnwrap(defaults.data(forKey: PairScopedRelayRouteStore.userDefaultsKey))
        let json = try XCTUnwrap(String(data: data, encoding: .utf8))
        XCTAssertFalse(json.contains("sensitive-relay-secret"))

        let envelope = try XCTUnwrap(
            JSONSerialization.jsonObject(with: data) as? [String: Any]
        )
        XCTAssertEqual(Set(envelope.keys), ["schema_version", "routes"])
        XCTAssertEqual(envelope["schema_version"] as? Int, 1)
        let routes = try XCTUnwrap(envelope["routes"] as? [[String: Any]])
        let persistedRoute = try XCTUnwrap(routes.first)
        XCTAssertEqual(Set(persistedRoute.keys), [
            "client_key_fingerprint",
            "host",
            "port",
            "relay_expires_at_epoch_millis",
            "relay_id",
            "relay_nonce",
            "route_token",
            "ticket_generation"
        ])
        XCTAssertNil(persistedRoute["relay_secret"])
        XCTAssertNil(persistedRoute["backend"])
        XCTAssertNil(persistedRoute["provider"])
    }

    func testUpsertUpdatesSameClientAndReplacesItsSecret() throws {
        let defaults = try isolatedDefaults()
        let secrets = InMemoryPairScopedRelaySecretStore()
        let store = PairScopedRelayRouteStore(
            userDefaults: defaults,
            relaySecretStore: secrets
        )
        try store.upsert(try makeRoute(), relaySecret: "old-secret")
        let updated = try makeRoute(
            relayID: Self.relayIDB,
            expiry: 4_102_444_900_000,
            nonce: "nonce-generation-2",
            generation: 2
        )

        try store.upsert(updated, relaySecret: "new-secret")

        XCTAssertEqual(store.loadAll(), [ResolvedPairScopedRelayRoute(
            route: updated,
            relaySecret: "new-secret"
        )])
        XCTAssertEqual(secrets.secrets.count, 1)
    }

    func testTwoClientsRemainIsolatedAndPersistInFingerprintOrder() throws {
        let defaults = try isolatedDefaults()
        let secrets = InMemoryPairScopedRelaySecretStore()
        let store = PairScopedRelayRouteStore(
            userDefaults: defaults,
            relaySecretStore: secrets
        )
        let routeB = try makeRoute(
            fingerprint: Self.fingerprintB,
            routeToken: "route-token-b",
            relayID: Self.relayIDB,
            nonce: "nonce-b"
        )
        let routeA = try makeRoute()

        try store.upsert(routeB, relaySecret: "secret-b")
        try store.upsert(routeA, relaySecret: "secret-a")

        XCTAssertEqual(store.loadAll(), [
            ResolvedPairScopedRelayRoute(route: routeA, relaySecret: "secret-a"),
            ResolvedPairScopedRelayRoute(route: routeB, relaySecret: "secret-b")
        ])
        XCTAssertEqual(secrets.secrets.count, 2)
        XCTAssertEqual(
            secrets.secrets[PairScopedRelayRouteStore.secretHandle(
                forClientKeyFingerprint: Self.fingerprintA
            )],
            "secret-a"
        )
        XCTAssertEqual(
            secrets.secrets[PairScopedRelayRouteStore.secretHandle(
                forClientKeyFingerprint: Self.fingerprintB
            )],
            "secret-b"
        )
    }

    func testDuplicateCorruptUnknownAndMalformedPersistenceFailsClosedWithoutSecretReads() throws {
        let defaults = try isolatedDefaults()
        let secrets = InMemoryPairScopedRelaySecretStore()
        secrets.saveSecret(
            "secret-a",
            for: PairScopedRelayRouteStore.secretHandle(
                forClientKeyFingerprint: Self.fingerprintA
            )
        )

        let routeA = persistedRouteJSON()
        let routeB = persistedRouteJSON(
            fingerprint: Self.fingerprintB,
            relayID: Self.relayIDB,
            routeToken: "route-token-b",
            nonce: "nonce-b"
        )
        let cases = [
            "{\"schema_version\":1,\"routes\":[",
            "{\"schema_version\":2,\"routes\":[]}",
            "{\"schema_version\":1,\"routes\":[],\"provider\":\"ollama\"}",
            envelopeJSON(routes: [routeA.dropLast() + ",\"backend\":\"lmstudio\"}"]),
            envelopeJSON(routes: [routeA, routeA]),
            envelopeJSON(routes: [
                routeA,
                persistedRouteJSON(fingerprint: Self.fingerprintB, relayID: Self.relayIDA)
            ]),
            envelopeJSON(routes: [routeB, routeA]),
            envelopeJSON(routes: [persistedRouteJSON(fingerprint: "not-a-fingerprint")]),
            envelopeJSON(routes: [persistedRouteJSON(relayID: "rt2-not-canonical")]),
            envelopeJSON(routes: [persistedRouteJSON(expiry: 0)]),
            envelopeJSON(routes: [persistedRouteJSON(generation: 0)])
        ]

        for json in cases {
            defaults.set(Data(json.utf8), forKey: PairScopedRelayRouteStore.userDefaultsKey)
            secrets.resetReadHandles()
            let store = PairScopedRelayRouteStore(
                userDefaults: defaults,
                relaySecretStore: secrets
            )

            XCTAssertTrue(store.loadAll().isEmpty, "Expected fail-closed JSON: \(json)")
            XCTAssertTrue(secrets.readHandles.isEmpty, "Secrets were read for corrupt JSON: \(json)")
        }
    }

    func testRemoveAndRemoveAllCleanSecretsWithoutCrossClientDeletion() throws {
        let defaults = try isolatedDefaults()
        let secrets = InMemoryPairScopedRelaySecretStore()
        let store = PairScopedRelayRouteStore(
            userDefaults: defaults,
            relaySecretStore: secrets
        )
        let routeA = try makeRoute()
        let routeB = try makeRoute(
            fingerprint: Self.fingerprintB,
            routeToken: "route-token-b",
            relayID: Self.relayIDB,
            nonce: "nonce-b"
        )
        try store.upsert(routeA, relaySecret: "secret-a")
        try store.upsert(routeB, relaySecret: "secret-b")

        XCTAssertTrue(try store.remove(clientKeyFingerprint: Self.fingerprintA))
        XCTAssertNil(secrets.secrets[PairScopedRelayRouteStore.secretHandle(
            forClientKeyFingerprint: Self.fingerprintA
        )])
        XCTAssertEqual(store.loadAll(), [ResolvedPairScopedRelayRoute(
            route: routeB,
            relaySecret: "secret-b"
        )])

        try store.removeAll()
        XCTAssertTrue(secrets.secrets.isEmpty)
        XCTAssertNil(defaults.object(forKey: PairScopedRelayRouteStore.userDefaultsKey))
        XCTAssertTrue(store.loadAll().isEmpty)
    }

    func testInvalidInputAndCrossClientRelayIDReuseAreRejected() throws {
        let invalidRoutes: [() throws -> Void] = [
            { _ = try self.makeRoute(fingerprint: String(repeating: "A", count: 64)) },
            { _ = try self.makeRoute(routeToken: "   ") },
            { _ = try self.makeRoute(host: "relay host") },
            { _ = try self.makeRoute(port: 0) },
            { _ = try self.makeRoute(relayID: "rt2-short") },
            { _ = try self.makeRoute(expiry: 0) },
            { _ = try self.makeRoute(nonce: "nonce with whitespace") },
            { _ = try self.makeRoute(generation: 0) }
        ]
        for makeInvalidRoute in invalidRoutes {
            XCTAssertThrowsError(try makeInvalidRoute())
        }

        let defaults = try isolatedDefaults()
        let secrets = InMemoryPairScopedRelaySecretStore()
        let store = PairScopedRelayRouteStore(
            userDefaults: defaults,
            relaySecretStore: secrets
        )
        try store.upsert(try makeRoute(), relaySecret: "secret-a")
        XCTAssertThrowsError(try store.upsert(try makeRoute(
            fingerprint: Self.fingerprintB,
            routeToken: "route-token-b",
            relayID: Self.relayIDA,
            nonce: "nonce-b"
        ), relaySecret: "secret-b")) { error in
            XCTAssertEqual(
                error as? PairScopedRelayRouteStoreError,
                .duplicateRelayID(Self.relayIDA)
            )
        }
        XCTAssertThrowsError(try store.upsert(try makeRoute(), relaySecret: "   "))
        XCTAssertEqual(store.loadAll().map(\.clientKeyFingerprint), [Self.fingerprintA])
    }

    private func makeRoute(
        fingerprint: String = PairScopedRelayRouteStoreTests.fingerprintA,
        routeToken: String = "route-token-a",
        host: String = "relay.example.test",
        port: UInt16 = 8443,
        relayID: String = PairScopedRelayRouteStoreTests.relayIDA,
        expiry: Int64 = 4_102_444_800_000,
        nonce: String = "nonce-a",
        generation: Int64 = 1
    ) throws -> PairScopedRelayRoute {
        try PairScopedRelayRoute(
            clientKeyFingerprint: fingerprint,
            routeToken: routeToken,
            host: host,
            port: port,
            relayID: relayID,
            relayExpiresAtEpochMillis: expiry,
            relayNonce: nonce,
            ticketGeneration: generation
        )
    }

    private func persistedRouteJSON(
        fingerprint: String = PairScopedRelayRouteStoreTests.fingerprintA,
        relayID: String = PairScopedRelayRouteStoreTests.relayIDA,
        routeToken: String = "route-token-a",
        host: String = "relay.example.test",
        port: UInt16 = 8443,
        expiry: Int64 = 4_102_444_800_000,
        nonce: String = "nonce-a",
        generation: Int64 = 1
    ) -> String {
        """
        {"client_key_fingerprint":"\(fingerprint)","host":"\(host)","port":\(port),"relay_expires_at_epoch_millis":\(expiry),"relay_id":"\(relayID)","relay_nonce":"\(nonce)","route_token":"\(routeToken)","ticket_generation":\(generation)}
        """
    }

    private func envelopeJSON(routes: [String]) -> String {
        "{\"schema_version\":1,\"routes\":[\(routes.joined(separator: ","))]}"
    }

    private func isolatedDefaults() throws -> UserDefaults {
        let suiteName = "PairScopedRelayRouteStoreTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defaults.removePersistentDomain(forName: suiteName)
        return defaults
    }
}

private final class InMemoryPairScopedRelaySecretStore: CompanionRelaySecretStoring, @unchecked Sendable {
    private(set) var secrets: [String: String] = [:]
    private(set) var readHandles: [String] = []

    func saveSecret(_ secret: String, for handle: String) {
        secrets[handle] = secret
    }

    func readSecret(for handle: String) -> String? {
        readHandles.append(handle)
        return secrets[handle]
    }

    func removeSecret(for handle: String) {
        secrets.removeValue(forKey: handle)
    }

    func resetReadHandles() {
        readHandles.removeAll()
    }
}
