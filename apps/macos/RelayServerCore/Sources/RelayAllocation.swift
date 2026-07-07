import CryptoKit
import Foundation

public struct RelayAllocationRequest: Equatable, Sendable {
    public static let action = "allocate"

    public let routeToken: String
    public let requestedRelaySecret: String?
    public let allocationToken: String?
    public let isPreflight: Bool
    public var shouldPersistAllocation: Bool { !isPreflight }

    public init(
        routeToken: String,
        requestedRelaySecret: String? = nil,
        allocationToken: String? = nil,
        isPreflight: Bool = false
    ) throws {
        guard !routeToken.isEmpty,
              routeToken.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
        else {
            throw RelayAllocationError.invalidRouteToken
        }
        if let requestedRelaySecret {
            guard !requestedRelaySecret.isEmpty,
                  requestedRelaySecret.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
            else {
                throw RelayAllocationError.invalidRelaySecret
            }
        }
        if let allocationToken {
            guard !allocationToken.isEmpty,
                  allocationToken.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
            else {
                throw RelayAllocationError.invalidAllocationToken
            }
        }
        self.routeToken = routeToken
        self.requestedRelaySecret = requestedRelaySecret
        self.allocationToken = allocationToken
        self.isPreflight = isPreflight
    }

    public static func parse(_ line: String) throws -> RelayAllocationRequest {
        let parts = line.trimmingCharacters(in: .whitespacesAndNewlines).split(
            whereSeparator: { $0.isWhitespace }
        )
        guard (3...6).contains(parts.count),
              parts[0] == Substring(RelayHandshake.prefix),
              parts[1] == Substring(action)
        else {
            throw RelayAllocationError.invalidFormat
        }
        var requestedRelaySecret: String?
        var allocationToken: String?
        var isPreflight = false
        for value in parts.dropFirst(3).map(String.init) {
            if let parsedToken = parseAllocationToken(value) {
                guard allocationToken == nil else {
                    throw RelayAllocationError.invalidFormat
                }
                allocationToken = parsedToken
            } else if isPreflightOption(value) {
                guard !isPreflight else {
                    throw RelayAllocationError.invalidFormat
                }
                isPreflight = true
            } else {
                guard !looksLikeUnknownOption(value) else {
                    throw RelayAllocationError.invalidFormat
                }
                guard requestedRelaySecret == nil else {
                    throw RelayAllocationError.invalidFormat
                }
                requestedRelaySecret = value
            }
        }
        return try RelayAllocationRequest(
            routeToken: String(parts[2]),
            requestedRelaySecret: requestedRelaySecret,
            allocationToken: allocationToken,
            isPreflight: isPreflight
        )
    }

    public static func isAllocationLine(_ line: String) -> Bool {
        let parts = line.trimmingCharacters(in: .whitespacesAndNewlines).split(
            whereSeparator: { $0.isWhitespace }
        )
        return parts.count >= 2 &&
            parts[0] == Substring(RelayHandshake.prefix) &&
            parts[1] == Substring(action)
    }

    private static func parseAllocationToken(_ value: String) -> String? {
        if value.hasPrefix("allocation_token=") {
            return String(value.dropFirst("allocation_token=".count))
        }
        if value.hasPrefix("auth=") {
            return String(value.dropFirst("auth=".count))
        }
        return nil
    }

    private static func isPreflightOption(_ value: String) -> Bool {
        value == "preflight=1" || value == "preflight=true"
    }

    private static func looksLikeUnknownOption(_ value: String) -> Bool {
        guard let separator = value.firstIndex(of: "=") else {
            return false
        }
        let key = String(value[..<separator])
        if rejectedRequestMetadataKeys.contains(key) {
            return true
        }
        guard isRecognizedOptionName(key) else {
            return false
        }
        let suffix = value[value.index(after: separator)...]
        return !suffix.allSatisfy { $0 == "=" }
    }

    private static func isRecognizedOptionName(_ value: String) -> Bool {
        guard let first = value.first, first.isLetter || first == "_" else {
            return false
        }
        return value.allSatisfy { character in
            character.isLetter || character.isNumber || character == "_" || character == "-"
        }
    }

    private static let rejectedRequestMetadataKeys: Set<String> = [
        "backend_url",
        "provider_url",
        "requested_route_token",
        "relay_secret_debug",
        "route_token",
        "relay_id",
        "relay_secret",
        "relay_expires_at",
        "relay_nonce",
    ]
}

public struct RelayAllocation: Codable, Equatable, Sendable {
    public static let responsePrefix = "\(RelayHandshake.prefix) allocation "

    public let relayID: String
    public let relaySecret: String
    public let relayExpiresAtEpochMillis: Int64
    public let relayNonce: String

    public init(
        relayID: String,
        relaySecret: String,
        relayExpiresAtEpochMillis: Int64,
        relayNonce: String
    ) throws {
        guard isCanonicalRelayControlLineID(relayID) else {
            throw RelayAllocationError.invalidRelayID
        }
        guard !relaySecret.isEmpty,
              relaySecret.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
        else {
            throw RelayAllocationError.invalidRelaySecret
        }
        guard relayExpiresAtEpochMillis > 0 else {
            throw RelayAllocationError.invalidExpiration
        }
        guard !relayNonce.isEmpty,
              relayNonce.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
        else {
            throw RelayAllocationError.invalidNonce
        }
        self.relayID = relayID
        self.relaySecret = relaySecret
        self.relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
        self.relayNonce = relayNonce
    }

    public static func make(
        routeToken: String? = nil,
        requestedRelaySecret: String? = nil,
        now: Date = Date(),
        validFor seconds: TimeInterval = 15 * 60
    ) throws -> RelayAllocation {
        let relayID = try routeToken.map { try Self.relayID(forRouteToken: $0) }
            ?? "relay-\(UUID().uuidString)"
        return try RelayAllocation(
            relayID: relayID,
            relaySecret: requestedRelaySecret ?? "\(UUID().uuidString).\(UUID().uuidString)",
            relayExpiresAtEpochMillis: Int64((now.addingTimeInterval(seconds).timeIntervalSince1970 * 1000).rounded()),
            relayNonce: "nonce-\(UUID().uuidString)"
        )
    }

    public static func relayID(forRouteToken routeToken: String) throws -> String {
        let canonicalRouteToken = try RelayAllocationRequest(routeToken: routeToken).routeToken
        let digestInput = "AetherLink relay allocation id v1\n\(canonicalRouteToken)"
        let digest = SHA256.hash(data: Data(digestInput.utf8))
        let hexDigest = digest.map { String(format: "%02x", $0) }.joined()
        return "rt1-\(hexDigest)"
    }

    public func responseLine() throws -> Data {
        let data = try JSONEncoder().encode(self)
        let body = String(decoding: data, as: UTF8.self)
        return Data("\(Self.responsePrefix)\(body)\n".utf8)
    }

    public static func parseResponseLine(_ line: String) throws -> RelayAllocation {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.hasPrefix(responsePrefix) else {
            throw RelayAllocationError.invalidResponseFormat
        }
        let json = String(trimmed.dropFirst(responsePrefix.count))
        guard let data = json.data(using: .utf8) else {
            throw RelayAllocationError.invalidResponseFormat
        }
        let object: Any
        do {
            object = try JSONSerialization.jsonObject(with: data)
        } catch {
            throw RelayAllocationError.invalidResponseFormat
        }
        guard let payload = object as? [String: Any] else {
            throw RelayAllocationError.invalidResponseFormat
        }
        guard Set(payload.keys).isSubset(of: allowedResponseFieldNames) else {
            throw RelayAllocationError.unexpectedResponseMetadata
        }
        return try JSONDecoder().decode(RelayAllocation.self, from: data)
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            relayID: container.decode(String.self, forKey: .relayID),
            relaySecret: container.decode(String.self, forKey: .relaySecret),
            relayExpiresAtEpochMillis: container.decode(Int64.self, forKey: .relayExpiresAtEpochMillis),
            relayNonce: container.decode(String.self, forKey: .relayNonce)
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(relayID, forKey: .relayID)
        try container.encode(relaySecret, forKey: .relaySecret)
        try container.encode(relayExpiresAtEpochMillis, forKey: .relayExpiresAtEpochMillis)
        try container.encode(relayNonce, forKey: .relayNonce)
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case relayID = "relay_id"
        case relaySecret = "relay_secret"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
    }

    private static let allowedResponseFieldNames = Set(CodingKeys.allCases.map(\.stringValue))
}

public enum RelayAllocationError: Error, Equatable, Sendable {
    case invalidFormat
    case invalidRouteToken
    case invalidRelayID
    case invalidRelaySecret
    case invalidExpiration
    case invalidNonce
    case invalidResponseFormat
    case unexpectedResponseMetadata
    case invalidAllocationToken
    case unauthorizedAllocation
}

public final class RelayAllocationRegistry: @unchecked Sendable {
    private let lock = NSLock()
    private let persistenceURL: URL?
    private var allocations: [String: RelayAllocationTicket]

    public init(persistenceURL: URL? = nil) {
        self.persistenceURL = persistenceURL
        self.allocations = Self.loadAllocations(from: persistenceURL)
    }

    @discardableResult
    public func store(_ allocation: RelayAllocation) -> Bool {
        lock.withLock {
            let ticket = RelayAllocationTicket(allocation)
            if let existing = allocations[allocation.relayID],
               !ticket.isAdvancingReplacement(of: existing) {
                return false
            }
            allocations[allocation.relayID] = ticket
            persistLocked()
            return true
        }
    }

    public func isValid(relayID: String, now: Date = Date()) -> Bool {
        lock.withLock {
            if removeExpiredLocked(now: now) {
                persistLocked()
            }
            return allocations[relayID] != nil
        }
    }

    public func remove(relayID: String) {
        lock.withLock {
            if allocations.removeValue(forKey: relayID) != nil {
                persistLocked()
            }
        }
    }

    public func count(now: Date = Date()) -> Int {
        lock.withLock {
            if removeExpiredLocked(now: now) {
                persistLocked()
            }
            return allocations.count
        }
    }

    private func removeExpiredLocked(now: Date) -> Bool {
        let nowMillis = Int64((now.timeIntervalSince1970 * 1000).rounded())
        let originalCount = allocations.count
        allocations = allocations.filter { _, ticket in
            ticket.relayExpiresAtEpochMillis > nowMillis
        }
        return allocations.count != originalCount
    }

    private func persistLocked() {
        guard let persistenceURL else { return }
        do {
            try FileManager.default.createDirectory(
                at: persistenceURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            let tickets = allocations.values.sorted { $0.relayID < $1.relayID }
            let data = try JSONEncoder().encode(tickets)
            try data.write(to: persistenceURL, options: [.atomic])
        } catch {
            // Allocation persistence is best-effort; live relay state remains authoritative.
        }
    }

    private static func loadAllocations(from persistenceURL: URL?) -> [String: RelayAllocationTicket] {
        guard let persistenceURL else { return [:] }
        do {
            let data = try Data(contentsOf: persistenceURL)
            let tickets = try JSONDecoder().decode([RelayAllocationTicket].self, from: data)
            var loaded: [String: RelayAllocationTicket] = [:]
            for ticket in tickets where ticket.isLoadable {
                if let existing = loaded[ticket.relayID] {
                    if ticket.isAdvancingReplacement(of: existing) {
                        loaded[ticket.relayID] = ticket
                    }
                } else {
                    loaded[ticket.relayID] = ticket
                }
            }
            return loaded
        } catch {
            return [:]
        }
    }
}

private struct RelayAllocationTicket: Codable, Equatable, Sendable {
    let relayID: String
    let relayExpiresAtEpochMillis: Int64
    let relayNonce: String
    private let hasUnexpectedMetadata: Bool

    init(_ allocation: RelayAllocation) {
        self.relayID = allocation.relayID
        self.relayExpiresAtEpochMillis = allocation.relayExpiresAtEpochMillis
        self.relayNonce = allocation.relayNonce
        self.hasUnexpectedMetadata = false
    }

    func isAdvancingReplacement(of existing: RelayAllocationTicket) -> Bool {
        relayExpiresAtEpochMillis > existing.relayExpiresAtEpochMillis &&
            relayNonce != existing.relayNonce
    }

    var isLoadable: Bool {
        !hasUnexpectedMetadata &&
            isCanonicalRelayControlLineID(relayID) &&
            relayExpiresAtEpochMillis > 0 &&
            !relayNonce.isEmpty &&
            relayNonce.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
    }

    init(from decoder: Decoder) throws {
        let metadataContainer = try decoder.container(keyedBy: AnyCodingKey.self)
        let allowedKeys = Set(CodingKeys.allCases.map(\.stringValue))
        hasUnexpectedMetadata = !Set(metadataContainer.allKeys.map(\.stringValue)).isSubset(of: allowedKeys)

        let container = try decoder.container(keyedBy: CodingKeys.self)
        relayID = try container.decode(String.self, forKey: .relayID)
        relayExpiresAtEpochMillis = try container.decode(Int64.self, forKey: .relayExpiresAtEpochMillis)
        relayNonce = try container.decode(String.self, forKey: .relayNonce)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(relayID, forKey: .relayID)
        try container.encode(relayExpiresAtEpochMillis, forKey: .relayExpiresAtEpochMillis)
        try container.encode(relayNonce, forKey: .relayNonce)
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case relayID = "relay_id"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
    }
}

private struct AnyCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int?

    init?(stringValue: String) {
        self.stringValue = stringValue
        self.intValue = nil
    }

    init?(intValue: Int) {
        self.stringValue = "\(intValue)"
        self.intValue = intValue
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
