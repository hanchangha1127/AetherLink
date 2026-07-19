import BridgeProtocol
import CryptoKit
import Darwin
import Foundation

public struct RelayAllocationRequest: Equatable, Sendable {
    public static let action = "allocate"

    public let routeToken: String
    public let requestedRelaySecret: String?
    public let cryptoVersion: Int?
    public let allocationToken: String?
    public let isPreflight: Bool
    public let runtimeIdentity: RelayRuntimeIdentity?
    public var usesEndpointOwnedSecret: Bool { cryptoVersion == RelayAllocationV2.cryptoVersion }
    public var shouldPersistAllocation: Bool { !isPreflight }

    public init(
        routeToken: String,
        requestedRelaySecret: String? = nil,
        cryptoVersion: Int? = nil,
        allocationToken: String? = nil,
        isPreflight: Bool = false,
        runtimeIdentity: RelayRuntimeIdentity? = nil
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
        if let cryptoVersion {
            guard cryptoVersion == RelayAllocationV2.cryptoVersion else {
                throw RelayAllocationError.unsupportedCryptoVersion
            }
            guard requestedRelaySecret == nil else {
                throw RelayAllocationError.relaySecretNotAllowedForCryptoV2
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
        self.cryptoVersion = cryptoVersion
        self.allocationToken = allocationToken
        self.isPreflight = isPreflight
        self.runtimeIdentity = runtimeIdentity
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
        var cryptoVersion: Int?
        var allocationToken: String?
        var isPreflight = false
        for value in parts.dropFirst(3).map(String.init) {
            if value.hasPrefix("crypto=") {
                guard cryptoVersion == nil else {
                    throw RelayAllocationError.invalidFormat
                }
                guard value == "crypto=2" else {
                    throw RelayAllocationError.unsupportedCryptoVersion
                }
                cryptoVersion = RelayAllocationV2.cryptoVersion
            } else if let parsedToken = parseAllocationToken(value) {
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
            cryptoVersion: cryptoVersion,
            allocationToken: allocationToken,
            isPreflight: isPreflight
        )
    }

    public static func parseStrictCryptoV2(_ line: String) throws -> RelayAllocationRequest {
        let parts = try exactControlLineParts(line)
        guard (5...8).contains(parts.count),
              parts[0] == Substring(RelayHandshake.prefix),
              parts[1] == Substring(action),
              parts[3] == "crypto=2"
        else {
            throw RelayAllocationError.invalidFormat
        }

        if parts.count >= 7,
           parts[4] == "allocation_auth=\(relayIdentityAuthorizationScheme)",
           let fingerprint = exactFieldValue(parts[5], name: "runtime_key_fingerprint"),
           let publicKey = exactFieldValue(parts[6], name: "runtime_public_key") {
            var nextOptionIndex = 7
            var allocationToken: String?
            if nextOptionIndex < parts.count,
               parts[nextOptionIndex].hasPrefix("allocation_token=") {
                allocationToken = String(
                    parts[nextOptionIndex].dropFirst("allocation_token=".count)
                )
                nextOptionIndex += 1
            }
            guard nextOptionIndex == parts.count else {
                throw RelayAllocationError.invalidFormat
            }
            return try RelayAllocationRequest(
                routeToken: String(parts[2]),
                cryptoVersion: RelayAllocationV2.cryptoVersion,
                allocationToken: allocationToken,
                runtimeIdentity: {
                    let identity = try RelayRuntimeIdentity(
                        publicKeyBase64: publicKey,
                        fingerprint: fingerprint
                    )
                    guard let keyData = Data(base64Encoded: publicKey),
                          keyData.base64EncodedString() == publicKey,
                          let parsedKey = try? P256.Signing.PublicKey(derRepresentation: keyData),
                          parsedKey.derRepresentation == keyData
                    else {
                        throw RelayAllocationError.invalidRuntimeIdentity
                    }
                    return identity
                }()
            )
        }

        var nextOptionIndex = 4
        var allocationToken: String?
        if nextOptionIndex < parts.count,
           parts[nextOptionIndex].hasPrefix("allocation_token=") {
            allocationToken = String(
                parts[nextOptionIndex].dropFirst("allocation_token=".count)
            )
            nextOptionIndex += 1
        }

        if nextOptionIndex < parts.count, parts[nextOptionIndex] == "preflight=1" {
            nextOptionIndex += 1
        } else {
            throw RelayAllocationError.invalidFormat
        }

        guard nextOptionIndex == parts.count else {
            throw RelayAllocationError.invalidFormat
        }
        return try RelayAllocationRequest(
            routeToken: String(parts[2]),
            cryptoVersion: RelayAllocationV2.cryptoVersion,
            allocationToken: allocationToken,
            isPreflight: true
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

    private static func exactControlLineParts(_ line: String) throws -> [Substring] {
        guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else {
            throw RelayAllocationError.invalidFormat
        }
        let body = line.dropLast()
        guard !body.contains("\n"), !body.contains("\r") else {
            throw RelayAllocationError.invalidFormat
        }
        let parts = body.split(separator: " ", omittingEmptySubsequences: false)
        guard parts.allSatisfy({ !$0.isEmpty }) else {
            throw RelayAllocationError.invalidFormat
        }
        return parts
    }

    private static func exactFieldValue(_ field: Substring, name: String) -> String? {
        let prefix = "\(name)="
        guard field.hasPrefix(prefix) else { return nil }
        let value = String(field.dropFirst(prefix.count))
        return value.isEmpty ? nil : value
    }
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
            relayExpiresAtEpochMillis: try relayAllocationExpirationEpochMillis(
                now: now,
                validFor: seconds
            ),
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
            try StrictJSONDocumentValidator.validate(data)
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

public struct RelayAllocationV2: Codable, Equatable, Sendable {
    public static let cryptoVersion = 2
    public static let responsePrefix = RelayAllocation.responsePrefix

    public let relayID: String
    public let relayExpiresAtEpochMillis: Int64
    public let relayNonce: String
    public let runtimeKeyFingerprint: String
    public let ticketGeneration: Int64

    public init(
        relayID: String,
        relayExpiresAtEpochMillis: Int64,
        relayNonce: String,
        runtimeKeyFingerprint: String,
        ticketGeneration: Int64
    ) throws {
        guard isCanonicalRuntimeKeyBoundRelayID(relayID) else {
            throw RelayAllocationError.invalidRelayID
        }
        guard relayExpiresAtEpochMillis > 0 else {
            throw RelayAllocationError.invalidExpiration
        }
        guard !relayNonce.isEmpty,
              relayNonce.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
        else {
            throw RelayAllocationError.invalidNonce
        }
        guard RelayRuntimeIdentity.isCanonicalFingerprint(runtimeKeyFingerprint) else {
            throw RelayAllocationError.invalidRuntimeIdentity
        }
        guard ticketGeneration > 0 else {
            throw RelayAllocationError.invalidTicketGeneration
        }
        self.relayID = relayID
        self.relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
        self.relayNonce = relayNonce
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.ticketGeneration = ticketGeneration
    }

    public static func make(
        routeToken: String,
        runtimeIdentity: RelayRuntimeIdentity,
        ticketGeneration: Int64,
        now: Date = Date(),
        validFor seconds: TimeInterval = 15 * 60
    ) throws -> RelayAllocationV2 {
        try RelayAllocationV2(
            relayID: RelayAllocationIdentityChallenge.relayID(
                routeToken: routeToken,
                runtimeKeyFingerprint: runtimeIdentity.fingerprint
            ),
            relayExpiresAtEpochMillis: try relayAllocationExpirationEpochMillis(
                now: now,
                validFor: seconds
            ),
            relayNonce: "nonce-\(UUID().uuidString)",
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            ticketGeneration: ticketGeneration
        )
    }

    public func responseLine() throws -> Data {
        let data = try JSONEncoder().encode(self)
        let body = String(decoding: data, as: UTF8.self)
        return Data("\(Self.responsePrefix)\(body)\n".utf8)
    }

    public static func parseResponseLine(_ line: String) throws -> RelayAllocationV2 {
        guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else {
            throw RelayAllocationError.invalidResponseFormat
        }
        let body = String(line.dropLast())
        guard body.hasPrefix(responsePrefix), !body.dropFirst(responsePrefix.count).contains("\n") else {
            throw RelayAllocationError.invalidResponseFormat
        }
        let json = String(body.dropFirst(responsePrefix.count))
        guard let data = json.data(using: .utf8) else {
            throw RelayAllocationError.invalidResponseFormat
        }
        let object: Any
        do {
            try StrictJSONDocumentValidator.validate(data)
            object = try JSONSerialization.jsonObject(with: data)
        } catch {
            throw RelayAllocationError.invalidResponseFormat
        }
        guard let payload = object as? [String: Any] else {
            throw RelayAllocationError.invalidResponseFormat
        }
        guard Set(payload.keys) == responseFieldNames else {
            throw RelayAllocationError.unexpectedResponseMetadata
        }
        do {
            return try JSONDecoder().decode(RelayAllocationV2.self, from: data)
        } catch let error as RelayAllocationError {
            throw error
        } catch {
            throw RelayAllocationError.invalidResponseFormat
        }
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        guard try container.decode(Int.self, forKey: .cryptoVersion) == Self.cryptoVersion else {
            throw RelayAllocationError.unsupportedCryptoVersion
        }
        try self.init(
            relayID: container.decode(String.self, forKey: .relayID),
            relayExpiresAtEpochMillis: container.decode(Int64.self, forKey: .relayExpiresAtEpochMillis),
            relayNonce: container.decode(String.self, forKey: .relayNonce),
            runtimeKeyFingerprint: container.decode(String.self, forKey: .runtimeKeyFingerprint),
            ticketGeneration: container.decode(Int64.self, forKey: .ticketGeneration)
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(relayID, forKey: .relayID)
        try container.encode(relayExpiresAtEpochMillis, forKey: .relayExpiresAtEpochMillis)
        try container.encode(relayNonce, forKey: .relayNonce)
        try container.encode(runtimeKeyFingerprint, forKey: .runtimeKeyFingerprint)
        try container.encode(ticketGeneration, forKey: .ticketGeneration)
        try container.encode(Self.cryptoVersion, forKey: .cryptoVersion)
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case relayID = "relay_id"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case ticketGeneration = "ticket_generation"
        case cryptoVersion = "crypto_version"
    }

    private static let responseFieldNames = Set(CodingKeys.allCases.map(\.stringValue))
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
    case unsupportedCryptoVersion
    case relaySecretNotAllowedForCryptoV2
    case invalidRuntimeIdentity
    case invalidTicketGeneration
    case persistenceFailed
    case allocationConflict
    case allocationNotFound
    case authorizationDowngrade
}

public enum RelayAllocationAuthorizationMode: String, Codable, Equatable, Sendable {
    case bootstrapRuntimeOnly = "bootstrap_runtime_only"
    case pairedDeviceP256V1 = "paired_device_p256_v1"
}

public struct RelayAllocationBinding: Codable, Equatable, Sendable {
    public let relayID: String
    public let relayExpiresAtEpochMillis: Int64
    public let relayNonce: String
    public let runtimeKeyFingerprint: String
    public let runtimePublicKey: String
    public let ticketGeneration: Int64
    public let authorizationMode: RelayAllocationAuthorizationMode
    public let pairedClientKeyFingerprint: String?

    public init(
        relayID: String,
        relayExpiresAtEpochMillis: Int64,
        relayNonce: String,
        runtimeIdentity: RelayRuntimeIdentity,
        ticketGeneration: Int64,
        authorizationMode: RelayAllocationAuthorizationMode = .bootstrapRuntimeOnly,
        pairedClientKeyFingerprint: String? = nil
    ) throws {
        guard isCanonicalRuntimeKeyBoundRelayID(relayID) else {
            throw RelayAllocationError.invalidRelayID
        }
        guard relayExpiresAtEpochMillis > 0 else {
            throw RelayAllocationError.invalidExpiration
        }
        guard !relayNonce.isEmpty,
              relayNonce.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
        else {
            throw RelayAllocationError.invalidNonce
        }
        guard ticketGeneration > 0 else {
            throw RelayAllocationError.invalidTicketGeneration
        }
        guard let publicKeyData = Data(base64Encoded: runtimeIdentity.publicKeyBase64),
              publicKeyData.base64EncodedString() == runtimeIdentity.publicKeyBase64,
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: publicKeyData),
              publicKey.derRepresentation == publicKeyData
        else {
            throw RelayAllocationError.invalidRuntimeIdentity
        }
        switch authorizationMode {
        case .bootstrapRuntimeOnly:
            guard pairedClientKeyFingerprint == nil else {
                throw RelayAllocationError.invalidRuntimeIdentity
            }
        case .pairedDeviceP256V1:
            guard let pairedClientKeyFingerprint,
                  PairedRelayAllocationAuthorization.isCanonicalDigest(
                    pairedClientKeyFingerprint
                  ),
                  pairedClientKeyFingerprint != runtimeIdentity.fingerprint
            else {
                throw RelayAllocationError.invalidRuntimeIdentity
            }
        }
        self.relayID = relayID
        self.relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
        self.relayNonce = relayNonce
        self.runtimeKeyFingerprint = runtimeIdentity.fingerprint
        self.runtimePublicKey = runtimeIdentity.publicKeyBase64
        self.ticketGeneration = ticketGeneration
        self.authorizationMode = authorizationMode
        self.pairedClientKeyFingerprint = pairedClientKeyFingerprint
    }

    public var runtimeIdentity: RelayRuntimeIdentity {
        get throws {
            try RelayRuntimeIdentity(
                publicKeyBase64: runtimePublicKey,
                fingerprint: runtimeKeyFingerprint
            )
        }
    }

    public func isActive(now: Date = Date()) -> Bool {
        relayExpiresAtEpochMillis > epochMillis(now)
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case relayID = "relay_id"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case runtimePublicKey = "runtime_public_key"
        case ticketGeneration = "ticket_generation"
        case authorizationMode = "authorization_mode"
        case pairedClientKeyFingerprint = "paired_client_key_fingerprint"
    }

    public init(from decoder: Decoder) throws {
        let metadata = try decoder.container(keyedBy: AllocationAnyCodingKey.self)
        guard Set(metadata.allKeys.map(\.stringValue)) == Set(CodingKeys.allCases.map(\.stringValue)) else {
            throw RelayAllocationError.persistenceFailed
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let identity = try RelayRuntimeIdentity(
            publicKeyBase64: container.decode(String.self, forKey: .runtimePublicKey),
            fingerprint: container.decode(String.self, forKey: .runtimeKeyFingerprint)
        )
        try self.init(
            relayID: container.decode(String.self, forKey: .relayID),
            relayExpiresAtEpochMillis: container.decode(Int64.self, forKey: .relayExpiresAtEpochMillis),
            relayNonce: container.decode(String.self, forKey: .relayNonce),
            runtimeIdentity: identity,
            ticketGeneration: container.decode(Int64.self, forKey: .ticketGeneration),
            authorizationMode: container.decode(
                RelayAllocationAuthorizationMode.self,
                forKey: .authorizationMode
            ),
            pairedClientKeyFingerprint: container.decodeIfPresent(
                String.self,
                forKey: .pairedClientKeyFingerprint
            )
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(relayID, forKey: .relayID)
        try container.encode(relayExpiresAtEpochMillis, forKey: .relayExpiresAtEpochMillis)
        try container.encode(relayNonce, forKey: .relayNonce)
        try container.encode(runtimeKeyFingerprint, forKey: .runtimeKeyFingerprint)
        try container.encode(runtimePublicKey, forKey: .runtimePublicKey)
        try container.encode(ticketGeneration, forKey: .ticketGeneration)
        try container.encode(authorizationMode, forKey: .authorizationMode)
        if let pairedClientKeyFingerprint {
            try container.encode(
                pairedClientKeyFingerprint,
                forKey: .pairedClientKeyFingerprint
            )
        } else {
            try container.encodeNil(forKey: .pairedClientKeyFingerprint)
        }
    }
}

public struct RelayPairedAllocationProposal: Equatable, Sendable {
    public let operation: PairedRelayAllocationOperation
    public let currentBinding: RelayAllocationBinding
    public let nextRelayID: String

    public init(
        operation: PairedRelayAllocationOperation,
        currentBinding: RelayAllocationBinding,
        nextRelayID: String
    ) {
        self.operation = operation
        self.currentBinding = currentBinding
        self.nextRelayID = nextRelayID
    }
}

public struct RelayBootstrapConsumptionTombstone: Codable, Equatable, Sendable {
    public let relayID: String
    public let runtimeKeyFingerprint: String
    public let runtimePublicKey: String
    public let pairedRelayID: String
    public let pairedClientKeyFingerprint: String
    public let consumedTicketGeneration: Int64

    public init(
        relayID: String,
        runtimeIdentity: RelayRuntimeIdentity,
        pairedRelayID: String,
        pairedClientKeyFingerprint: String,
        consumedTicketGeneration: Int64
    ) throws {
        guard isCanonicalRuntimeKeyBoundRelayID(relayID),
              isCanonicalRuntimeKeyBoundRelayID(pairedRelayID),
              relayID != pairedRelayID,
              PairedRelayAllocationAuthorization.isCanonicalDigest(
                pairedClientKeyFingerprint
              ),
              pairedClientKeyFingerprint != runtimeIdentity.fingerprint,
              consumedTicketGeneration > 0,
              let publicKeyData = Data(base64Encoded: runtimeIdentity.publicKeyBase64),
              publicKeyData.base64EncodedString() == runtimeIdentity.publicKeyBase64,
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: publicKeyData),
              publicKey.derRepresentation == publicKeyData
        else {
            throw RelayAllocationError.persistenceFailed
        }
        self.relayID = relayID
        self.runtimeKeyFingerprint = runtimeIdentity.fingerprint
        self.runtimePublicKey = runtimeIdentity.publicKeyBase64
        self.pairedRelayID = pairedRelayID
        self.pairedClientKeyFingerprint = pairedClientKeyFingerprint
        self.consumedTicketGeneration = consumedTicketGeneration
    }

    public var runtimeIdentity: RelayRuntimeIdentity {
        get throws {
            try RelayRuntimeIdentity(
                publicKeyBase64: runtimePublicKey,
                fingerprint: runtimeKeyFingerprint
            )
        }
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case relayID = "relay_id"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case runtimePublicKey = "runtime_public_key"
        case pairedRelayID = "paired_relay_id"
        case pairedClientKeyFingerprint = "paired_client_key_fingerprint"
        case consumedTicketGeneration = "consumed_ticket_generation"
    }

    public init(from decoder: Decoder) throws {
        let metadata = try decoder.container(keyedBy: AllocationAnyCodingKey.self)
        guard Set(metadata.allKeys.map(\.stringValue)) == Set(CodingKeys.allCases.map(\.stringValue)) else {
            throw RelayAllocationError.persistenceFailed
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            relayID: container.decode(String.self, forKey: .relayID),
            runtimeIdentity: RelayRuntimeIdentity(
                publicKeyBase64: container.decode(String.self, forKey: .runtimePublicKey),
                fingerprint: container.decode(String.self, forKey: .runtimeKeyFingerprint)
            ),
            pairedRelayID: container.decode(String.self, forKey: .pairedRelayID),
            pairedClientKeyFingerprint: container.decode(
                String.self,
                forKey: .pairedClientKeyFingerprint
            ),
            consumedTicketGeneration: container.decode(
                Int64.self,
                forKey: .consumedTicketGeneration
            )
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(relayID, forKey: .relayID)
        try container.encode(runtimeKeyFingerprint, forKey: .runtimeKeyFingerprint)
        try container.encode(runtimePublicKey, forKey: .runtimePublicKey)
        try container.encode(pairedRelayID, forKey: .pairedRelayID)
        try container.encode(pairedClientKeyFingerprint, forKey: .pairedClientKeyFingerprint)
        try container.encode(consumedTicketGeneration, forKey: .consumedTicketGeneration)
    }
}

public final class RelayAllocationRegistry: @unchecked Sendable {
    public static let schemaVersion = 4

    private let lock = NSLock()
    private let persistenceURL: URL?
    private let transactionLock: RelayAllocationStoreTransactionLock?
    private let coordinationToken: String?
    private let wallClockNow: @Sendable () -> Date
    private var persistenceStateIsValid: Bool
    private var allocations: [String: RelayAllocationBinding]
    private var consumedBootstrapAllocations: [String: RelayBootstrapConsumptionTombstone]

    public convenience init(persistenceURL: URL? = nil) {
        self.init(persistenceURL: persistenceURL, wallClockNow: { Date() })
    }

    init(
        persistenceURL: URL?,
        wallClockNow: @escaping @Sendable () -> Date
    ) {
        self.wallClockNow = wallClockNow
        if let requestedPersistenceURL = persistenceURL {
            do {
                let transactionLock = try RelayAllocationStoreTransactionLock(
                    storeURL: requestedPersistenceURL
                )
                var coordinationToken: String?
                let loaded = try transactionLock.withExclusiveLock { marker in
                    coordinationToken = marker.token
                    let storeState = try RelayAllocationStoreCoordination.entryState(
                        at: transactionLock.storeURL
                    )
                    switch marker.state {
                    case .uninitialized:
                        switch storeState {
                        case .absent:
                            try Self.persist(
                                [:],
                                consumedBootstrapAllocations: [:],
                                coordinationToken: marker.token,
                                to: transactionLock.storeURL
                            )
                        case .regular:
                            let initialized = Self.loadAllocations(
                                from: transactionLock.storeURL,
                                expectedCoordinationToken: marker.token,
                                allowLegacyWithoutCoordinationToken: false
                            )
                            guard initialized.isValid, !initialized.requiresRewrite else {
                                throw RelayAllocationError.persistenceFailed
                            }
                        case .invalid:
                            throw RelayAllocationError.persistenceFailed
                        }
                        try transactionLock.markEstablished(expectedToken: marker.token)
                    case .adoptingExistingStore:
                        guard storeState == .regular else {
                            throw RelayAllocationError.persistenceFailed
                        }
                        let adopted = Self.loadAllocations(
                            from: transactionLock.storeURL,
                            expectedCoordinationToken: marker.token,
                            allowLegacyWithoutCoordinationToken: true
                        )
                        guard adopted.isValid else {
                            throw RelayAllocationError.persistenceFailed
                        }
                        if adopted.requiresRewrite {
                            try Self.persist(
                                adopted.allocations,
                                consumedBootstrapAllocations: adopted.consumedBootstrapAllocations,
                                coordinationToken: marker.token,
                                to: transactionLock.storeURL
                            )
                        }
                        try transactionLock.markEstablished(expectedToken: marker.token)
                    case .established:
                        guard storeState == .regular else {
                            throw RelayAllocationError.persistenceFailed
                        }
                    }
                    let result = Self.loadAllocations(
                        from: transactionLock.storeURL,
                        expectedCoordinationToken: marker.token,
                        allowLegacyWithoutCoordinationToken: false
                    )
                    guard result.isValid, !result.requiresRewrite else {
                        throw RelayAllocationError.persistenceFailed
                    }
                    return result
                }
                self.persistenceURL = transactionLock.storeURL
                self.transactionLock = transactionLock
                self.coordinationToken = coordinationToken
                self.allocations = loaded.allocations
                self.consumedBootstrapAllocations = loaded.consumedBootstrapAllocations
                self.persistenceStateIsValid = loaded.isValid
            } catch {
                self.persistenceURL = requestedPersistenceURL
                self.transactionLock = nil
                self.coordinationToken = nil
                self.allocations = [:]
                self.consumedBootstrapAllocations = [:]
                self.persistenceStateIsValid = false
            }
        } else {
            let loaded = Self.loadAllocations(from: nil)
            self.persistenceURL = nil
            self.transactionLock = nil
            self.coordinationToken = nil
            self.allocations = loaded.allocations
            self.consumedBootstrapAllocations = loaded.consumedBootstrapAllocations
            self.persistenceStateIsValid = loaded.isValid
        }
    }

    public var isPersistenceReady: Bool {
        lock.withLock { persistenceStateIsValid }
    }

    public func proposedGeneration(
        relayID: String,
        runtimeIdentity: RelayRuntimeIdentity
    ) throws -> (operation: RelayAllocationIdentityOperation, generation: Int64) {
        try withCoordinatedState {
            guard persistenceStateIsValid else { throw RelayAllocationError.persistenceFailed }
            guard consumedBootstrapAllocations[relayID] == nil else {
                throw RelayAllocationError.authorizationDowngrade
            }
            guard let current = allocations[relayID] else {
                return (.create, 1)
            }
            guard current.runtimeKeyFingerprint == runtimeIdentity.fingerprint,
                  current.runtimePublicKey == runtimeIdentity.publicKeyBase64
            else {
                throw RelayAllocationError.invalidRuntimeIdentity
            }
            guard current.authorizationMode == .bootstrapRuntimeOnly else {
                throw RelayAllocationError.authorizationDowngrade
            }
            guard current.ticketGeneration < Int64.max else {
                throw RelayAllocationError.invalidTicketGeneration
            }
            return (.renew, current.ticketGeneration + 1)
        }
    }

    public func pairedRenewalProposal(
        bootstrapRelayID: String,
        pairedRelayID: String,
        runtimeIdentity: RelayRuntimeIdentity,
        clientKeyFingerprint: String
    ) throws -> RelayPairedAllocationProposal {
        try withCoordinatedState {
            guard persistenceStateIsValid else { throw RelayAllocationError.persistenceFailed }
            guard bootstrapRelayID != pairedRelayID,
                  isCanonicalRuntimeKeyBoundRelayID(bootstrapRelayID),
                  isCanonicalRuntimeKeyBoundRelayID(pairedRelayID)
            else {
                throw RelayAllocationError.invalidRelayID
            }
            if let paired = allocations[pairedRelayID] {
                guard allocations[bootstrapRelayID] == nil,
                      paired.runtimeKeyFingerprint == runtimeIdentity.fingerprint,
                      paired.runtimePublicKey == runtimeIdentity.publicKeyBase64,
                      paired.authorizationMode == .pairedDeviceP256V1,
                      paired.pairedClientKeyFingerprint == clientKeyFingerprint,
                      paired.ticketGeneration < Int64.max
                else {
                    throw RelayAllocationError.unauthorizedAllocation
                }
                return RelayPairedAllocationProposal(
                    operation: .renew,
                    currentBinding: paired,
                    nextRelayID: pairedRelayID
                )
            }
            guard let current = allocations[bootstrapRelayID] else {
                if let consumed = consumedBootstrapAllocations[bootstrapRelayID],
                   consumed.runtimeKeyFingerprint == runtimeIdentity.fingerprint,
                   consumed.runtimePublicKey == runtimeIdentity.publicKeyBase64,
                   consumed.pairedClientKeyFingerprint == clientKeyFingerprint,
                   consumed.pairedRelayID == pairedRelayID {
                    throw RelayAllocationError.allocationConflict
                }
                throw RelayAllocationError.allocationNotFound
            }
            guard current.runtimeKeyFingerprint == runtimeIdentity.fingerprint,
                  current.runtimePublicKey == runtimeIdentity.publicKeyBase64
            else {
                throw RelayAllocationError.invalidRuntimeIdentity
            }
            guard current.ticketGeneration < Int64.max else {
                throw RelayAllocationError.invalidTicketGeneration
            }
            switch current.authorizationMode {
            case .bootstrapRuntimeOnly:
                guard current.pairedClientKeyFingerprint == nil else {
                    throw RelayAllocationError.persistenceFailed
                }
                return RelayPairedAllocationProposal(
                    operation: .claim,
                    currentBinding: current,
                    nextRelayID: pairedRelayID
                )
            case .pairedDeviceP256V1:
                guard current.pairedClientKeyFingerprint == clientKeyFingerprint else {
                    throw RelayAllocationError.unauthorizedAllocation
                }
                return RelayPairedAllocationProposal(
                    operation: .renew,
                    currentBinding: current,
                    nextRelayID: pairedRelayID
                )
            }
        }
    }

    public func commit(
        _ binding: RelayAllocationBinding,
        replacingGeneration: Int64?
    ) throws {
        try withCoordinatedState {
            guard persistenceStateIsValid else { throw RelayAllocationError.persistenceFailed }
            guard consumedBootstrapAllocations[binding.relayID] == nil else {
                throw RelayAllocationError.authorizationDowngrade
            }
            let current = allocations[binding.relayID]
            guard current?.ticketGeneration == replacingGeneration else {
                throw RelayAllocationError.allocationConflict
            }
            if let current {
                guard binding.ticketGeneration == current.ticketGeneration + 1,
                      binding.runtimeKeyFingerprint == current.runtimeKeyFingerprint,
                      binding.runtimePublicKey == current.runtimePublicKey,
                      current.authorizationMode == .bootstrapRuntimeOnly,
                      current.pairedClientKeyFingerprint == nil,
                      binding.authorizationMode == .bootstrapRuntimeOnly,
                      binding.pairedClientKeyFingerprint == nil
                else {
                    throw RelayAllocationError.allocationConflict
                }
            } else {
                guard binding.ticketGeneration == 1,
                      binding.authorizationMode == .bootstrapRuntimeOnly,
                      binding.pairedClientKeyFingerprint == nil
                else {
                    throw RelayAllocationError.allocationConflict
                }
            }
            var replacement = allocations
            replacement[binding.relayID] = binding
            try persistLocked(
                replacement,
                consumedBootstrapAllocations: consumedBootstrapAllocations
            )
            allocations = replacement
        }
    }

    public func commitPairedRenewal(
        _ binding: RelayAllocationBinding,
        replacing expected: RelayAllocationBinding,
        operation: PairedRelayAllocationOperation
    ) throws {
        try withCoordinatedState {
            guard persistenceStateIsValid else { throw RelayAllocationError.persistenceFailed }
            guard allocations[expected.relayID] == expected,
                  expected.ticketGeneration < Int64.max,
                  binding.ticketGeneration == expected.ticketGeneration + 1,
                  binding.relayExpiresAtEpochMillis > expected.relayExpiresAtEpochMillis,
                  binding.relayNonce != expected.relayNonce,
                  binding.runtimeKeyFingerprint == expected.runtimeKeyFingerprint,
                  binding.runtimePublicKey == expected.runtimePublicKey,
                  binding.authorizationMode == .pairedDeviceP256V1,
                  let pairedClientKeyFingerprint = binding.pairedClientKeyFingerprint
            else {
                throw RelayAllocationError.allocationConflict
            }
            switch operation {
            case .claim:
                guard expected.authorizationMode == .bootstrapRuntimeOnly,
                      expected.pairedClientKeyFingerprint == nil,
                      binding.relayID != expected.relayID
                else {
                    throw RelayAllocationError.allocationConflict
                }
            case .renew:
                guard expected.authorizationMode == .pairedDeviceP256V1,
                      expected.pairedClientKeyFingerprint == pairedClientKeyFingerprint
                else {
                    throw RelayAllocationError.allocationConflict
                }
            }
            var replacement = allocations
            var replacementTombstones = consumedBootstrapAllocations
            if binding.relayID != expected.relayID {
                guard replacement[binding.relayID] == nil else {
                    throw RelayAllocationError.allocationConflict
                }
                replacement.removeValue(forKey: expected.relayID)
                let tombstone = try RelayBootstrapConsumptionTombstone(
                    relayID: expected.relayID,
                    runtimeIdentity: expected.runtimeIdentity,
                    pairedRelayID: binding.relayID,
                    pairedClientKeyFingerprint: pairedClientKeyFingerprint,
                    consumedTicketGeneration: expected.ticketGeneration
                )
                guard replacementTombstones[expected.relayID].map({ $0 == tombstone }) ?? true else {
                    throw RelayAllocationError.allocationConflict
                }
                replacementTombstones[expected.relayID] = tombstone
            }
            replacement[binding.relayID] = binding
            try persistLocked(
                replacement,
                consumedBootstrapAllocations: replacementTombstones
            )
            allocations = replacement
            consumedBootstrapAllocations = replacementTombstones
        }
    }

    public func binding(relayID: String) -> RelayAllocationBinding? {
        binding(relayID: relayID, validationDate: nil)
    }

    public func binding(relayID: String, now: Date) -> RelayAllocationBinding? {
        binding(relayID: relayID, validationDate: now)
    }

    private func binding(
        relayID: String,
        validationDate explicitValidationDate: Date?
    ) -> RelayAllocationBinding? {
        try? withCoordinatedState {
            guard persistenceStateIsValid else { return nil }
            let validationDate = explicitValidationDate ?? wallClockNow()
            guard let binding = allocations[relayID], binding.isActive(now: validationDate) else {
                return nil
            }
            return binding
        }
    }

    public func tombstone(relayID: String) -> RelayAllocationBinding? {
        try? withCoordinatedState { persistenceStateIsValid ? allocations[relayID] : nil }
    }

    public func consumedBootstrapTombstone(
        relayID: String
    ) -> RelayBootstrapConsumptionTombstone? {
        try? withCoordinatedState {
            persistenceStateIsValid ? consumedBootstrapAllocations[relayID] : nil
        }
    }

    public func isValid(relayID: String) -> Bool {
        binding(relayID: relayID) != nil
    }

    public func isValid(relayID: String, now: Date) -> Bool {
        binding(relayID: relayID, now: now) != nil
    }

    public func count() -> Int {
        count(validationDate: nil)
    }

    public func count(now: Date) -> Int {
        count(validationDate: now)
    }

    private func count(validationDate explicitValidationDate: Date?) -> Int {
        (try? withCoordinatedState {
            let validationDate = explicitValidationDate ?? wallClockNow()
            return allocations.values.filter { $0.isActive(now: validationDate) }.count
        }) ?? 0
    }

    public func withRevalidatedBinding<T>(
        _ expected: RelayAllocationBinding,
        _ body: () throws -> T
    ) throws -> T {
        try withFreshlyRevalidatedBinding(expected, validationDate: nil) { _ in
            try body()
        }
    }

    public func withRevalidatedBinding<T>(
        _ expected: RelayAllocationBinding,
        now: Date,
        _ body: () throws -> T
    ) throws -> T {
        try withFreshlyRevalidatedBinding(expected, validationDate: now) { _ in
            try body()
        }
    }

    func withFreshlyRevalidatedBinding<T>(
        _ expected: RelayAllocationBinding,
        _ body: (Date) throws -> T
    ) throws -> T {
        try withFreshlyRevalidatedBinding(expected, validationDate: nil, body)
    }

    private func withFreshlyRevalidatedBinding<T>(
        _ expected: RelayAllocationBinding,
        validationDate explicitValidationDate: Date?,
        _ body: (Date) throws -> T
    ) throws -> T {
        try withCoordinatedState {
            guard persistenceStateIsValid else { throw RelayAllocationError.persistenceFailed }
            let validationDate = explicitValidationDate ?? wallClockNow()
            guard allocations[expected.relayID] == expected,
                  expected.isActive(now: validationDate)
            else {
                throw RelayAllocationError.allocationConflict
            }
            return try body(validationDate)
        }
    }

    private func withCoordinatedState<T>(_ body: () throws -> T) throws -> T {
        try lock.withLock {
            guard persistenceStateIsValid else {
                throw RelayAllocationError.persistenceFailed
            }
            guard let transactionLock else {
                return try body()
            }
            do {
                return try transactionLock.withExclusiveLock { marker in
                    guard marker.state == .established,
                          marker.token == coordinationToken
                    else {
                        throw RelayAllocationError.persistenceFailed
                    }
                    try reloadLocked()
                    return try body()
                }
            } catch is RelayAllocationStoreCoordinationError {
                persistenceStateIsValid = false
                allocations = [:]
                consumedBootstrapAllocations = [:]
                throw RelayAllocationError.persistenceFailed
            } catch RelayAllocationError.persistenceFailed {
                persistenceStateIsValid = false
                allocations = [:]
                consumedBootstrapAllocations = [:]
                throw RelayAllocationError.persistenceFailed
            }
        }
    }

    private func reloadLocked() throws {
        guard let persistenceURL, let coordinationToken else { return }
        let loaded = Self.loadAllocations(
            from: persistenceURL,
            expectedCoordinationToken: coordinationToken,
            allowLegacyWithoutCoordinationToken: false
        )
        guard loaded.isValid, !loaded.requiresRewrite else {
            persistenceStateIsValid = false
            allocations = [:]
            consumedBootstrapAllocations = [:]
            throw RelayAllocationError.persistenceFailed
        }
        allocations = loaded.allocations
        consumedBootstrapAllocations = loaded.consumedBootstrapAllocations
    }

    private func persistLocked(
        _ replacement: [String: RelayAllocationBinding],
        consumedBootstrapAllocations: [String: RelayBootstrapConsumptionTombstone]
    ) throws {
        guard let persistenceURL else { return }
        guard let coordinationToken else {
            persistenceStateIsValid = false
            throw RelayAllocationError.persistenceFailed
        }
        do {
            try Self.persist(
                replacement,
                consumedBootstrapAllocations: consumedBootstrapAllocations,
                coordinationToken: coordinationToken,
                to: persistenceURL
            )
        } catch {
            persistenceStateIsValid = false
            allocations = [:]
            self.consumedBootstrapAllocations = [:]
            throw error
        }
    }

    private static func loadAllocations(
        from persistenceURL: URL?,
        expectedCoordinationToken: String? = nil,
        allowLegacyWithoutCoordinationToken: Bool = true
    ) -> (
        allocations: [String: RelayAllocationBinding],
        consumedBootstrapAllocations: [String: RelayBootstrapConsumptionTombstone],
        isValid: Bool,
        requiresRewrite: Bool
    ) {
        guard let persistenceURL else {
            return ([:], [:], true, false)
        }
        do {
            let data = try RelayAllocationStoreCoordination.readSecureFile(at: persistenceURL)
            try StrictJSONDocumentValidator.validate(data)
            guard let version = try? JSONDecoder().decode(
                RelayAllocationStoreVersionProbe.self,
                from: data
            ).schemaVersion else {
                guard allowLegacyWithoutCoordinationToken else {
                    return ([:], [:], false, false)
                }
                _ = try JSONDecoder().decode(
                    [RelayAllocationStoreEnvelopeV1Ticket].self,
                    from: data
                )
                return ([:], [:], true, true)
            }
            switch version {
            case schemaVersion:
                let envelope: RelayAllocationStoreEnvelope
                if let current = try? JSONDecoder().decode(
                    RelayAllocationStoreEnvelope.self,
                    from: data
                ) {
                    guard expectedCoordinationToken == nil
                            || current.coordinationToken == expectedCoordinationToken
                    else {
                        return ([:], [:], false, false)
                    }
                    envelope = current
                } else {
                    guard allowLegacyWithoutCoordinationToken else {
                        return ([:], [:], false, false)
                    }
                    let legacy = try JSONDecoder().decode(
                        RelayAllocationStoreEnvelopeV4WithoutCoordinationToken.self,
                        from: data
                    )
                    let allocations = try validatedAllocations(legacy.allocations)
                    let tombstones = try validatedTombstones(
                        legacy.consumedBootstrapAllocations,
                        allocations: allocations
                    )
                    return (allocations, tombstones, true, true)
                }
                let allocations = try validatedAllocations(envelope.allocations)
                let tombstones = try validatedTombstones(
                    envelope.consumedBootstrapAllocations,
                    allocations: allocations
                )
                return (allocations, tombstones, true, false)
            case 3:
                guard allowLegacyWithoutCoordinationToken else {
                    return ([:], [:], false, false)
                }
                let legacyEnvelope = try JSONDecoder().decode(
                    RelayAllocationStoreEnvelopeV3.self,
                    from: data
                )
                let migrated = try validatedAllocations(legacyEnvelope.allocations)
                return (migrated, [:], true, true)
            case 2:
                guard allowLegacyWithoutCoordinationToken else {
                    return ([:], [:], false, false)
                }
                let legacyEnvelope = try JSONDecoder().decode(
                    RelayAllocationStoreEnvelopeV2.self,
                    from: data
                )
                let migratedBindings = try legacyEnvelope.allocations.map { try $0.migrated() }
                let migrated = try validatedAllocations(migratedBindings)
                return (migrated, [:], true, true)
            default:
                return ([:], [:], false, false)
            }
        } catch {
            return ([:], [:], false, false)
        }
    }

    private static func validatedAllocations(
        _ bindings: [RelayAllocationBinding]
    ) throws -> [String: RelayAllocationBinding] {
        var loaded: [String: RelayAllocationBinding] = [:]
        for binding in bindings {
            guard loaded.updateValue(binding, forKey: binding.relayID) == nil else {
                throw RelayAllocationError.persistenceFailed
            }
        }
        return loaded
    }

    private static func validatedTombstones(
        _ tombstones: [RelayBootstrapConsumptionTombstone],
        allocations: [String: RelayAllocationBinding]
    ) throws -> [String: RelayBootstrapConsumptionTombstone] {
        var loaded: [String: RelayBootstrapConsumptionTombstone] = [:]
        var pairedRelayIDs = Set<String>()
        for tombstone in tombstones {
            guard allocations[tombstone.relayID] == nil,
                  pairedRelayIDs.insert(tombstone.pairedRelayID).inserted,
                  loaded.updateValue(tombstone, forKey: tombstone.relayID) == nil,
                  let paired = allocations[tombstone.pairedRelayID],
                  paired.authorizationMode == .pairedDeviceP256V1,
                  paired.runtimeKeyFingerprint == tombstone.runtimeKeyFingerprint,
                  paired.runtimePublicKey == tombstone.runtimePublicKey,
                  paired.pairedClientKeyFingerprint == tombstone.pairedClientKeyFingerprint,
                  paired.ticketGeneration > tombstone.consumedTicketGeneration
            else {
                throw RelayAllocationError.persistenceFailed
            }
        }
        return loaded
    }

    private static func persist(
        _ replacement: [String: RelayAllocationBinding],
        consumedBootstrapAllocations: [String: RelayBootstrapConsumptionTombstone],
        coordinationToken: String,
        to persistenceURL: URL
    ) throws {
        do {
            let envelope = RelayAllocationStoreEnvelope(
                schemaVersion: schemaVersion,
                coordinationToken: coordinationToken,
                allocations: replacement.values.sorted { $0.relayID < $1.relayID },
                consumedBootstrapAllocations: consumedBootstrapAllocations.values.sorted {
                    $0.relayID < $1.relayID
                }
            )
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.sortedKeys]
            let data = try encoder.encode(envelope)
            do {
                try RelayAllocationStoreCoordination.writeAtomically(data, to: persistenceURL)
            } catch RelayAllocationStoreCoordinationError.durabilityUncertainAfterRename {
                guard try RelayAllocationStoreCoordination.readSecureFile(at: persistenceURL) == data else {
                    throw RelayAllocationError.persistenceFailed
                }
                try RelayAllocationStoreCoordination.syncParentDirectory(of: persistenceURL)
            }
        } catch {
            throw RelayAllocationError.persistenceFailed
        }
    }
}

private struct RelayAllocationStoreEnvelope: Codable {
    let schemaVersion: Int
    let coordinationToken: String
    let allocations: [RelayAllocationBinding]
    let consumedBootstrapAllocations: [RelayBootstrapConsumptionTombstone]

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case schemaVersion = "schema_version"
        case coordinationToken = "coordination_token"
        case allocations
        case consumedBootstrapAllocations = "consumed_bootstrap_allocations"
    }

    init(
        schemaVersion: Int,
        coordinationToken: String,
        allocations: [RelayAllocationBinding],
        consumedBootstrapAllocations: [RelayBootstrapConsumptionTombstone]
    ) {
        self.schemaVersion = schemaVersion
        self.coordinationToken = coordinationToken
        self.allocations = allocations
        self.consumedBootstrapAllocations = consumedBootstrapAllocations
    }

    init(from decoder: Decoder) throws {
        let metadata = try decoder.container(keyedBy: AllocationAnyCodingKey.self)
        guard Set(metadata.allKeys.map(\.stringValue)) == Set(CodingKeys.allCases.map(\.stringValue)) else {
            throw RelayAllocationError.persistenceFailed
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(Int.self, forKey: .schemaVersion)
        guard schemaVersion == RelayAllocationRegistry.schemaVersion else {
            throw RelayAllocationError.persistenceFailed
        }
        coordinationToken = try container.decode(String.self, forKey: .coordinationToken)
        guard coordinationToken.count == 64,
              coordinationToken.allSatisfy({
                  ("0"..."9").contains($0) || ("a"..."f").contains($0)
              })
        else {
            throw RelayAllocationError.persistenceFailed
        }
        allocations = try container.decode([RelayAllocationBinding].self, forKey: .allocations)
        consumedBootstrapAllocations = try container.decode(
            [RelayBootstrapConsumptionTombstone].self,
            forKey: .consumedBootstrapAllocations
        )
    }
}

private struct RelayAllocationStoreEnvelopeV4WithoutCoordinationToken: Decodable {
    let schemaVersion: Int
    let allocations: [RelayAllocationBinding]
    let consumedBootstrapAllocations: [RelayBootstrapConsumptionTombstone]

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case schemaVersion = "schema_version"
        case allocations
        case consumedBootstrapAllocations = "consumed_bootstrap_allocations"
    }

    init(from decoder: Decoder) throws {
        let metadata = try decoder.container(keyedBy: AllocationAnyCodingKey.self)
        guard Set(metadata.allKeys.map(\.stringValue)) == Set(CodingKeys.allCases.map(\.stringValue)) else {
            throw RelayAllocationError.persistenceFailed
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(Int.self, forKey: .schemaVersion)
        guard schemaVersion == RelayAllocationRegistry.schemaVersion else {
            throw RelayAllocationError.persistenceFailed
        }
        allocations = try container.decode([RelayAllocationBinding].self, forKey: .allocations)
        consumedBootstrapAllocations = try container.decode(
            [RelayBootstrapConsumptionTombstone].self,
            forKey: .consumedBootstrapAllocations
        )
    }
}

private struct RelayAllocationStoreEnvelopeV3: Decodable {
    let schemaVersion: Int
    let allocations: [RelayAllocationBinding]

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case schemaVersion = "schema_version"
        case allocations
    }

    init(from decoder: Decoder) throws {
        let metadata = try decoder.container(keyedBy: AllocationAnyCodingKey.self)
        guard Set(metadata.allKeys.map(\.stringValue)) == Set(CodingKeys.allCases.map(\.stringValue)) else {
            throw RelayAllocationError.persistenceFailed
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(Int.self, forKey: .schemaVersion)
        guard schemaVersion == 3 else { throw RelayAllocationError.persistenceFailed }
        allocations = try container.decode([RelayAllocationBinding].self, forKey: .allocations)
    }
}

private struct RelayAllocationStoreVersionProbe: Decodable {
    let schemaVersion: Int

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case schemaVersion = "schema_version"
        case coordinationToken = "coordination_token"
        case allocations
        case consumedBootstrapAllocations = "consumed_bootstrap_allocations"
    }

    init(from decoder: Decoder) throws {
        let metadata = try decoder.container(keyedBy: AllocationAnyCodingKey.self)
        let fields = Set(metadata.allKeys.map(\.stringValue))
        let legacyFields: Set<String> = [
            CodingKeys.schemaVersion.rawValue,
            CodingKeys.allocations.rawValue,
        ]
        let legacyV4Fields = legacyFields.union([
            CodingKeys.consumedBootstrapAllocations.rawValue
        ])
        let currentFields = Set(CodingKeys.allCases.map(\.stringValue))
        guard fields == legacyFields || fields == legacyV4Fields || fields == currentFields else {
            throw RelayAllocationError.persistenceFailed
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(Int.self, forKey: .schemaVersion)
        guard container.contains(.allocations) else {
            throw RelayAllocationError.persistenceFailed
        }
    }
}

private struct RelayAllocationStoreEnvelopeV2: Decodable {
    let schemaVersion: Int
    let allocations: [RelayAllocationBindingV2]

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case schemaVersion = "schema_version"
        case allocations
    }

    init(from decoder: Decoder) throws {
        let metadata = try decoder.container(keyedBy: AllocationAnyCodingKey.self)
        guard Set(metadata.allKeys.map(\.stringValue)) == Set(CodingKeys.allCases.map(\.stringValue)) else {
            throw RelayAllocationError.persistenceFailed
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(Int.self, forKey: .schemaVersion)
        guard schemaVersion == 2 else { throw RelayAllocationError.persistenceFailed }
        allocations = try container.decode([RelayAllocationBindingV2].self, forKey: .allocations)
    }
}

private struct RelayAllocationStoreEnvelopeV1Ticket: Decodable {
    let relayID: String
    let relayExpiresAtEpochMillis: Int64
    let relayNonce: String

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case relayID = "relay_id"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
    }

    init(from decoder: Decoder) throws {
        let metadata = try decoder.container(keyedBy: AllocationAnyCodingKey.self)
        guard Set(metadata.allKeys.map(\.stringValue)) == Set(CodingKeys.allCases.map(\.stringValue)) else {
            throw RelayAllocationError.persistenceFailed
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        relayID = try container.decode(String.self, forKey: .relayID)
        relayExpiresAtEpochMillis = try container.decode(
            Int64.self,
            forKey: .relayExpiresAtEpochMillis
        )
        relayNonce = try container.decode(String.self, forKey: .relayNonce)
        guard isCanonicalRelayControlLineID(relayID),
              relayExpiresAtEpochMillis > 0,
              !relayNonce.isEmpty,
              relayNonce.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
        else {
            throw RelayAllocationError.persistenceFailed
        }
    }
}

private struct RelayAllocationBindingV2: Decodable {
    let relayID: String
    let relayExpiresAtEpochMillis: Int64
    let relayNonce: String
    let runtimeKeyFingerprint: String
    let runtimePublicKey: String
    let ticketGeneration: Int64

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case relayID = "relay_id"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case runtimePublicKey = "runtime_public_key"
        case ticketGeneration = "ticket_generation"
    }

    init(from decoder: Decoder) throws {
        let metadata = try decoder.container(keyedBy: AllocationAnyCodingKey.self)
        guard Set(metadata.allKeys.map(\.stringValue)) == Set(CodingKeys.allCases.map(\.stringValue)) else {
            throw RelayAllocationError.persistenceFailed
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        relayID = try container.decode(String.self, forKey: .relayID)
        relayExpiresAtEpochMillis = try container.decode(
            Int64.self,
            forKey: .relayExpiresAtEpochMillis
        )
        relayNonce = try container.decode(String.self, forKey: .relayNonce)
        runtimeKeyFingerprint = try container.decode(String.self, forKey: .runtimeKeyFingerprint)
        runtimePublicKey = try container.decode(String.self, forKey: .runtimePublicKey)
        ticketGeneration = try container.decode(Int64.self, forKey: .ticketGeneration)
    }

    func migrated() throws -> RelayAllocationBinding {
        try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: relayExpiresAtEpochMillis,
            relayNonce: relayNonce,
            runtimeIdentity: RelayRuntimeIdentity(
                publicKeyBase64: runtimePublicKey,
                fingerprint: runtimeKeyFingerprint
            ),
            ticketGeneration: ticketGeneration,
            authorizationMode: .bootstrapRuntimeOnly,
            pairedClientKeyFingerprint: nil
        )
    }
}

private struct AllocationAnyCodingKey: CodingKey {
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

func relayAllocationExpirationEpochMillis(
    now: Date,
    validFor seconds: TimeInterval
) throws -> Int64 {
    guard RelayServerConfiguration.isValidAllocationTTL(seconds),
          now.timeIntervalSince1970.isFinite
    else {
        throw RelayAllocationError.invalidExpiration
    }
    let milliseconds = ((now.timeIntervalSince1970 + seconds) * 1_000).rounded()
    guard milliseconds.isFinite,
          milliseconds > 0,
          milliseconds < Double(Int64.max)
    else {
        throw RelayAllocationError.invalidExpiration
    }
    return Int64(milliseconds)
}

private func epochMillis(_ date: Date) -> Int64 {
    Int64((date.timeIntervalSince1970 * 1000).rounded())
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
