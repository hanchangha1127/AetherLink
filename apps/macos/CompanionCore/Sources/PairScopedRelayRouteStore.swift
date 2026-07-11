import enum BridgeProtocol.PairedRelayAllocationAuthorization
import Foundation

public enum PairScopedRelayRouteStoreError: Error, Equatable, LocalizedError, Sendable {
    case invalidField(String)
    case duplicateRelayID(String)
    case corruptPersistence
    case secretPersistenceFailed
    case defaultsPersistenceFailed

    public var errorDescription: String? {
        switch self {
        case .invalidField(let field):
            return "The pair-scoped relay route field \(field) is invalid."
        case .duplicateRelayID(let relayID):
            return "The pair-scoped relay ID \(relayID) is already assigned to another client."
        case .corruptPersistence:
            return "The persisted pair-scoped relay route envelope is corrupt."
        case .secretPersistenceFailed:
            return "The pair-scoped relay secret could not be persisted."
        case .defaultsPersistenceFailed:
            return "The pair-scoped relay route envelope could not be persisted."
        }
    }
}

public struct PairScopedRelayRoute: Equatable, Sendable {
    public let clientKeyFingerprint: String
    public let routeToken: String
    public let host: String
    public let port: UInt16
    public let relayID: String
    public let relayExpiresAtEpochMillis: Int64
    public let relayNonce: String
    public let ticketGeneration: Int64

    public init(
        clientKeyFingerprint: String,
        routeToken: String,
        host: String,
        port: UInt16,
        relayID: String,
        relayExpiresAtEpochMillis: Int64,
        relayNonce: String,
        ticketGeneration: Int64
    ) throws {
        guard PairedRelayAllocationAuthorization.isCanonicalDigest(clientKeyFingerprint) else {
            throw PairScopedRelayRouteStoreError.invalidField("client_key_fingerprint")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(routeToken) else {
            throw PairScopedRelayRouteStoreError.invalidField("route_token")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(host) else {
            throw PairScopedRelayRouteStoreError.invalidField("host")
        }
        guard port > 0 else {
            throw PairScopedRelayRouteStoreError.invalidField("port")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalRelayID(relayID) else {
            throw PairScopedRelayRouteStoreError.invalidField("relay_id")
        }
        guard relayExpiresAtEpochMillis > 0 else {
            throw PairScopedRelayRouteStoreError.invalidField("relay_expires_at_epoch_millis")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalNonce(relayNonce) else {
            throw PairScopedRelayRouteStoreError.invalidField("relay_nonce")
        }
        guard ticketGeneration > 0 else {
            throw PairScopedRelayRouteStoreError.invalidField("ticket_generation")
        }

        self.clientKeyFingerprint = clientKeyFingerprint
        self.routeToken = routeToken
        self.host = host
        self.port = port
        self.relayID = relayID
        self.relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
        self.relayNonce = relayNonce
        self.ticketGeneration = ticketGeneration
    }
}

public struct ResolvedPairScopedRelayRoute: Equatable, Sendable {
    public let route: PairScopedRelayRoute
    public let relaySecret: String

    public init(route: PairScopedRelayRoute, relaySecret: String) {
        self.route = route
        self.relaySecret = relaySecret
    }

    public var clientKeyFingerprint: String { route.clientKeyFingerprint }
    public var routeToken: String { route.routeToken }
    public var host: String { route.host }
    public var port: UInt16 { route.port }
    public var relayID: String { route.relayID }
    public var relayExpiresAtEpochMillis: Int64 { route.relayExpiresAtEpochMillis }
    public var relayNonce: String { route.relayNonce }
    public var ticketGeneration: Int64 { route.ticketGeneration }
}

public final class PairScopedRelayRouteStore: @unchecked Sendable {
    public static let userDefaultsKey = "aetherlink.pair_scoped_relay_routes.v1"

    private static let schemaVersion = 1
    private static let secretHandlePrefix = "aetherlink.pair-scoped-relay-route.v1."

    private let userDefaults: UserDefaults
    private let relaySecretStore: any CompanionRelaySecretStoring
    private let lock = NSLock()

    public init(
        userDefaults: UserDefaults = .standard,
        relaySecretStore: any CompanionRelaySecretStoring = KeychainCompanionRelaySecretStore()
    ) {
        self.userDefaults = userDefaults
        self.relaySecretStore = relaySecretStore
    }

    public func loadAll() -> [ResolvedPairScopedRelayRoute] {
        withLock {
            guard case .valid(let envelope, _) = persistedState() else {
                return []
            }

            return envelope.routes.compactMap { persistedRoute in
                let handle = Self.secretHandle(
                    forClientKeyFingerprint: persistedRoute.route.clientKeyFingerprint
                )
                guard let secret = relaySecretStore.readSecret(for: handle),
                      Self.isValidSecret(secret) else {
                    return nil
                }
                return ResolvedPairScopedRelayRoute(
                    route: persistedRoute.route,
                    relaySecret: secret
                )
            }
        }
    }

    @discardableResult
    public func upsert(
        _ route: PairScopedRelayRoute,
        relaySecret: String
    ) throws -> ResolvedPairScopedRelayRoute {
        try withLock {
            guard Self.isValidSecret(relaySecret) else {
                throw PairScopedRelayRouteStoreError.invalidField("relay_secret")
            }

            let existingEnvelope: PersistedEnvelope
            let previousData: Data?
            switch persistedState() {
            case .missing:
                existingEnvelope = PersistedEnvelope(routes: [])
                previousData = nil
            case .valid(let envelope, let data):
                existingEnvelope = envelope
                previousData = data
            case .corrupt:
                throw PairScopedRelayRouteStoreError.corruptPersistence
            }

            if existingEnvelope.routes.contains(where: {
                $0.route.relayID == route.relayID &&
                    $0.route.clientKeyFingerprint != route.clientKeyFingerprint
            }) {
                throw PairScopedRelayRouteStoreError.duplicateRelayID(route.relayID)
            }

            var routes = existingEnvelope.routes.filter {
                $0.route.clientKeyFingerprint != route.clientKeyFingerprint
            }
            routes.append(PersistedRoute(route: route))
            routes.sort { $0.route.clientKeyFingerprint < $1.route.clientKeyFingerprint }
            let encoded = try encode(PersistedEnvelope(routes: routes))

            let handle = Self.secretHandle(forClientKeyFingerprint: route.clientKeyFingerprint)
            let previousSecret = relaySecretStore.readSecret(for: handle)
            relaySecretStore.saveSecret(relaySecret, for: handle)
            guard relaySecretStore.readSecret(for: handle) == relaySecret else {
                restoreSecret(previousSecret, for: handle)
                throw PairScopedRelayRouteStoreError.secretPersistenceFailed
            }

            userDefaults.set(encoded, forKey: Self.userDefaultsKey)
            guard userDefaults.data(forKey: Self.userDefaultsKey) == encoded else {
                restoreDefaults(previousData)
                restoreSecret(previousSecret, for: handle)
                throw PairScopedRelayRouteStoreError.defaultsPersistenceFailed
            }

            return ResolvedPairScopedRelayRoute(route: route, relaySecret: relaySecret)
        }
    }

    @discardableResult
    public func remove(clientKeyFingerprint: String) throws -> Bool {
        try withLock {
            guard PairedRelayAllocationAuthorization.isCanonicalDigest(clientKeyFingerprint) else {
                throw PairScopedRelayRouteStoreError.invalidField("client_key_fingerprint")
            }

            let envelope: PersistedEnvelope
            let previousData: Data?
            switch persistedState() {
            case .missing:
                relaySecretStore.removeSecret(
                    for: Self.secretHandle(forClientKeyFingerprint: clientKeyFingerprint)
                )
                return false
            case .valid(let loaded, let data):
                envelope = loaded
                previousData = data
            case .corrupt:
                throw PairScopedRelayRouteStoreError.corruptPersistence
            }

            let remainingRoutes = envelope.routes.filter {
                $0.route.clientKeyFingerprint != clientKeyFingerprint
            }
            guard remainingRoutes.count != envelope.routes.count else {
                relaySecretStore.removeSecret(
                    for: Self.secretHandle(forClientKeyFingerprint: clientKeyFingerprint)
                )
                return false
            }

            if remainingRoutes.isEmpty {
                userDefaults.removeObject(forKey: Self.userDefaultsKey)
                guard userDefaults.object(forKey: Self.userDefaultsKey) == nil else {
                    throw PairScopedRelayRouteStoreError.defaultsPersistenceFailed
                }
            } else {
                let encoded = try encode(PersistedEnvelope(routes: remainingRoutes))
                userDefaults.set(encoded, forKey: Self.userDefaultsKey)
                guard userDefaults.data(forKey: Self.userDefaultsKey) == encoded else {
                    restoreDefaults(previousData)
                    throw PairScopedRelayRouteStoreError.defaultsPersistenceFailed
                }
            }

            let handle = Self.secretHandle(forClientKeyFingerprint: clientKeyFingerprint)
            relaySecretStore.removeSecret(for: handle)
            guard relaySecretStore.readSecret(for: handle) == nil else {
                throw PairScopedRelayRouteStoreError.secretPersistenceFailed
            }
            return true
        }
    }

    public func removeAll() throws {
        try withLock {
            let fingerprints: Set<String>
            switch persistedState() {
            case .missing:
                fingerprints = []
            case .valid(let envelope, _):
                fingerprints = Set(envelope.routes.map(\.route.clientKeyFingerprint))
            case .corrupt(let data):
                fingerprints = data.map(Self.recoverCanonicalFingerprints(from:)) ?? []
            }

            userDefaults.removeObject(forKey: Self.userDefaultsKey)
            guard userDefaults.object(forKey: Self.userDefaultsKey) == nil else {
                throw PairScopedRelayRouteStoreError.defaultsPersistenceFailed
            }

            var failedToRemoveSecret = false
            for fingerprint in fingerprints {
                let handle = Self.secretHandle(forClientKeyFingerprint: fingerprint)
                relaySecretStore.removeSecret(for: handle)
                failedToRemoveSecret = relaySecretStore.readSecret(for: handle) != nil ||
                    failedToRemoveSecret
            }
            if failedToRemoveSecret {
                throw PairScopedRelayRouteStoreError.secretPersistenceFailed
            }
        }
    }

    static func secretHandle(forClientKeyFingerprint fingerprint: String) -> String {
        secretHandlePrefix + fingerprint
    }

    private func persistedState() -> PersistedState {
        guard let object = userDefaults.object(forKey: Self.userDefaultsKey) else {
            return .missing
        }
        guard let data = object as? Data else {
            return .corrupt(data: nil)
        }

        do {
            let envelope = try JSONDecoder().decode(PersistedEnvelope.self, from: data)
            return .valid(envelope: envelope, data: data)
        } catch {
            return .corrupt(data: data)
        }
    }

    private func encode(_ envelope: PersistedEnvelope) throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        do {
            return try encoder.encode(envelope)
        } catch {
            throw PairScopedRelayRouteStoreError.defaultsPersistenceFailed
        }
    }

    private func restoreSecret(_ secret: String?, for handle: String) {
        if let secret {
            relaySecretStore.saveSecret(secret, for: handle)
        } else {
            relaySecretStore.removeSecret(for: handle)
        }
    }

    private func restoreDefaults(_ data: Data?) {
        if let data {
            userDefaults.set(data, forKey: Self.userDefaultsKey)
        } else {
            userDefaults.removeObject(forKey: Self.userDefaultsKey)
        }
    }

    private func withLock<T>(_ operation: () throws -> T) rethrows -> T {
        lock.lock()
        defer { lock.unlock() }
        return try operation()
    }

    private static func isValidSecret(_ secret: String) -> Bool {
        PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(secret)
    }

    private static func recoverCanonicalFingerprints(from data: Data) -> Set<String> {
        guard let object = try? JSONSerialization.jsonObject(with: data),
              let envelope = object as? [String: Any],
              let routes = envelope["routes"] as? [[String: Any]] else {
            return []
        }
        return Set(routes.compactMap { route in
            guard let fingerprint = route["client_key_fingerprint"] as? String,
                  PairedRelayAllocationAuthorization.isCanonicalDigest(fingerprint) else {
                return nil
            }
            return fingerprint
        })
    }
}

private enum PersistedState {
    case missing
    case valid(envelope: PersistedEnvelope, data: Data)
    case corrupt(data: Data?)
}

private struct PersistedEnvelope: Codable {
    let schemaVersion: Int
    let routes: [PersistedRoute]

    init(routes: [PersistedRoute]) {
        schemaVersion = 1
        self.routes = routes
    }

    init(from decoder: Decoder) throws {
        try rejectUnknownFields(decoder, allowedKeys: CodingKeys.allCases)
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let schemaVersion = try container.decode(Int.self, forKey: .schemaVersion)
        guard schemaVersion == 1 else {
            throw PairScopedRelayRouteStoreError.corruptPersistence
        }

        let routes = try container.decode([PersistedRoute].self, forKey: .routes)
        let fingerprints = routes.map(\.route.clientKeyFingerprint)
        guard fingerprints == fingerprints.sorted(),
              Set(fingerprints).count == fingerprints.count else {
            throw PairScopedRelayRouteStoreError.corruptPersistence
        }
        let relayIDs = routes.map(\.route.relayID)
        guard Set(relayIDs).count == relayIDs.count else {
            throw PairScopedRelayRouteStoreError.corruptPersistence
        }

        self.schemaVersion = schemaVersion
        self.routes = routes
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case schemaVersion = "schema_version"
        case routes
    }
}

private struct PersistedRoute: Codable {
    let route: PairScopedRelayRoute

    init(route: PairScopedRelayRoute) {
        self.route = route
    }

    init(from decoder: Decoder) throws {
        try rejectUnknownFields(decoder, allowedKeys: CodingKeys.allCases)
        let container = try decoder.container(keyedBy: CodingKeys.self)
        route = try PairScopedRelayRoute(
            clientKeyFingerprint: container.decode(String.self, forKey: .clientKeyFingerprint),
            routeToken: container.decode(String.self, forKey: .routeToken),
            host: container.decode(String.self, forKey: .host),
            port: container.decode(UInt16.self, forKey: .port),
            relayID: container.decode(String.self, forKey: .relayID),
            relayExpiresAtEpochMillis: container.decode(
                Int64.self,
                forKey: .relayExpiresAtEpochMillis
            ),
            relayNonce: container.decode(String.self, forKey: .relayNonce),
            ticketGeneration: container.decode(Int64.self, forKey: .ticketGeneration)
        )
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(route.clientKeyFingerprint, forKey: .clientKeyFingerprint)
        try container.encode(route.routeToken, forKey: .routeToken)
        try container.encode(route.host, forKey: .host)
        try container.encode(route.port, forKey: .port)
        try container.encode(route.relayID, forKey: .relayID)
        try container.encode(
            route.relayExpiresAtEpochMillis,
            forKey: .relayExpiresAtEpochMillis
        )
        try container.encode(route.relayNonce, forKey: .relayNonce)
        try container.encode(route.ticketGeneration, forKey: .ticketGeneration)
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case clientKeyFingerprint = "client_key_fingerprint"
        case routeToken = "route_token"
        case host
        case port
        case relayID = "relay_id"
        case relayExpiresAtEpochMillis = "relay_expires_at_epoch_millis"
        case relayNonce = "relay_nonce"
        case ticketGeneration = "ticket_generation"
    }
}

private struct PairScopedRelayRouteDynamicCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int?

    init?(stringValue: String) {
        self.stringValue = stringValue
        intValue = nil
    }

    init?(intValue: Int) {
        stringValue = String(intValue)
        self.intValue = intValue
    }
}

private func rejectUnknownFields<Key: CodingKey>(
    _ decoder: Decoder,
    allowedKeys: [Key]
) throws {
    let container = try decoder.container(keyedBy: PairScopedRelayRouteDynamicCodingKey.self)
    let allowedFields = Set(allowedKeys.map(\.stringValue))
    if let unknownKey = container.allKeys.first(where: {
        !allowedFields.contains($0.stringValue)
    }) {
        throw DecodingError.dataCorruptedError(
            forKey: unknownKey,
            in: container,
            debugDescription: "Unknown pair-scoped relay route field \(unknownKey.stringValue)."
        )
    }
}
