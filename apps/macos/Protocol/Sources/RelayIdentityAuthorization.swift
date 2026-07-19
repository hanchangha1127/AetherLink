import CryptoKit
import Foundation

public let relayIdentityAuthorizationScheme = "runtime-p256-v1"
public let relayIdentityAuthorizationCryptoVersion = 2

public struct RelayRuntimeIdentity: Codable, Equatable, Sendable {
    public let publicKeyBase64: String
    public let fingerprint: String

    public init(publicKeyBase64: String, fingerprint: String) throws {
        guard Self.isValid(publicKeyBase64: publicKeyBase64, fingerprint: fingerprint) else {
            throw RelayIdentityAuthorizationError.invalidRuntimeIdentity
        }
        self.publicKeyBase64 = publicKeyBase64
        self.fingerprint = fingerprint
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            publicKeyBase64: container.decode(String.self, forKey: .publicKeyBase64),
            fingerprint: container.decode(String.self, forKey: .fingerprint)
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(publicKeyBase64, forKey: .publicKeyBase64)
        try container.encode(fingerprint, forKey: .fingerprint)
    }

    public static func isValid(publicKeyBase64: String, fingerprint: String) -> Bool {
        guard isCanonicalFingerprint(fingerprint),
              let publicKeyData = Data(base64Encoded: publicKeyBase64),
              publicKeyData.base64EncodedString() == publicKeyBase64,
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: publicKeyData),
              publicKey.derRepresentation == publicKeyData
        else {
            return false
        }
        return fingerprint == SHA256.hash(data: publicKeyData)
            .map { String(format: "%02x", $0) }
            .joined()
    }

    public static func isCanonicalFingerprint(_ value: String) -> Bool {
        isLowercaseHex(value, count: 64)
    }

    private enum CodingKeys: String, CodingKey {
        case publicKeyBase64
        case fingerprint
    }
}

public struct RelayIdentityAuthorizationProof: Equatable, Sendable {
    public let runtimeIdentity: RelayRuntimeIdentity
    public let signatureBase64: String

    public init(runtimeIdentity: RelayRuntimeIdentity, signatureBase64: String) throws {
        guard let signatureData = Data(base64Encoded: signatureBase64),
              signatureData.base64EncodedString() == signatureBase64,
              let signature = try? P256.Signing.ECDSASignature(
                  derRepresentation: signatureData
              ),
              signature.derRepresentation == signatureData
        else {
            throw RelayIdentityAuthorizationError.invalidSignature
        }
        self.runtimeIdentity = runtimeIdentity
        self.signatureBase64 = signatureBase64
    }
}

public protocol RelayIdentityAuthorizationSigning: Sendable {
    func relayRuntimeIdentity() throws -> RelayRuntimeIdentity
    func signRelayAllocationChallenge(
        _ challenge: RelayAllocationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof
    func signRelayRuntimeRegistrationChallenge(
        _ challenge: RelayRuntimeRegistrationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof
}

public enum RelayAllocationIdentityOperation: String, Codable, Sendable {
    case create
    case renew
    case preflight
}

public struct RelayAllocationIdentityChallenge: Codable, Equatable, Sendable {
    public static let responsePrefix = "AETHERLINK_RELAY allocation_challenge "

    public let operation: RelayAllocationIdentityOperation
    public let relayID: String
    public let routeTokenHash: String
    public let runtimeKeyFingerprint: String
    public let ticketGeneration: Int64
    public let challenge: String
    public let challengeExpiresAtEpochMillis: Int64
    public let cryptoVersion: Int
    public let allocationAuth: String

    public init(
        operation: RelayAllocationIdentityOperation,
        relayID: String,
        routeTokenHash: String,
        runtimeKeyFingerprint: String,
        ticketGeneration: Int64,
        challenge: String,
        challengeExpiresAtEpochMillis: Int64,
        cryptoVersion: Int = relayIdentityAuthorizationCryptoVersion,
        allocationAuth: String = relayIdentityAuthorizationScheme
    ) throws {
        guard !relayID.isEmpty,
              relayID.rangeOfCharacter(from: .whitespacesAndNewlines) == nil,
              isLowercaseHex(routeTokenHash, count: 64),
              RelayRuntimeIdentity.isCanonicalFingerprint(runtimeKeyFingerprint),
              ticketGeneration > 0,
              isLowercaseHex(challenge, count: 64),
              challengeExpiresAtEpochMillis > 0,
              cryptoVersion == relayIdentityAuthorizationCryptoVersion,
              allocationAuth == relayIdentityAuthorizationScheme
        else {
            throw RelayIdentityAuthorizationError.invalidChallenge
        }
        self.operation = operation
        self.relayID = relayID
        self.routeTokenHash = routeTokenHash
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.ticketGeneration = ticketGeneration
        self.challenge = challenge
        self.challengeExpiresAtEpochMillis = challengeExpiresAtEpochMillis
        self.cryptoVersion = cryptoVersion
        self.allocationAuth = allocationAuth
    }

    public func signedMessageData() -> Data {
        Data(
            """
            AetherLink relay allocation authorization v1
            operation
            \(operation.rawValue)
            crypto_version
            \(cryptoVersion)
            allocation_auth
            \(allocationAuth)
            relay_id
            \(relayID)
            route_token_hash
            \(routeTokenHash)
            runtime_key_fingerprint
            \(runtimeKeyFingerprint)
            ticket_generation
            \(ticketGeneration)
            challenge
            \(challenge)
            challenge_expires_at
            \(challengeExpiresAtEpochMillis)
            """.utf8
        )
    }

    public static func routeTokenHash(_ routeToken: String) -> String {
        SHA256.hash(data: Data(routeToken.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
    }

    public static func relayID(routeToken: String, runtimeKeyFingerprint: String) -> String {
        let material = "AetherLink relay id v2\n\(runtimeKeyFingerprint)\n\(routeToken)"
        let digest = SHA256.hash(data: Data(material.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
        return "rt2-\(digest)"
    }

    public static func pairedRelayID(
        routeToken: String,
        runtimeKeyFingerprint: String,
        clientKeyFingerprint: String
    ) -> String {
        let material = [
            "AetherLink paired relay id v1",
            runtimeKeyFingerprint,
            clientKeyFingerprint,
            routeToken,
        ].joined(separator: "\n")
        let digest = SHA256.hash(data: Data(material.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
        return "rt2-\(digest)"
    }

    private enum CodingKeys: String, CodingKey {
        case operation
        case relayID = "relay_id"
        case routeTokenHash = "route_token_hash"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case ticketGeneration = "ticket_generation"
        case challenge
        case challengeExpiresAtEpochMillis = "challenge_expires_at"
        case cryptoVersion = "crypto_version"
        case allocationAuth = "allocation_auth"
    }
}

public struct RelayRuntimeRegistrationIdentityChallenge: Codable, Equatable, Sendable {
    public static let responsePrefix = "AETHERLINK_RELAY registration_challenge "

    public let relayID: String
    public let relayExpiresAtEpochMillis: Int64
    public let relayNonce: String
    public let runtimeKeyFingerprint: String
    public let ticketGeneration: Int64
    public let sessionNonce: String
    public let ephemeralKey: String
    public let challenge: String
    public let challengeExpiresAtEpochMillis: Int64
    public let cryptoVersion: Int
    public let allocationAuth: String

    public init(
        relayID: String,
        relayExpiresAtEpochMillis: Int64,
        relayNonce: String,
        runtimeKeyFingerprint: String,
        ticketGeneration: Int64,
        sessionNonce: String,
        ephemeralKey: String,
        challenge: String,
        challengeExpiresAtEpochMillis: Int64,
        cryptoVersion: Int = relayIdentityAuthorizationCryptoVersion,
        allocationAuth: String = relayIdentityAuthorizationScheme
    ) throws {
        guard !relayID.isEmpty,
              relayID.rangeOfCharacter(from: .whitespacesAndNewlines) == nil,
              relayExpiresAtEpochMillis > 0,
              !relayNonce.isEmpty,
              relayNonce.rangeOfCharacter(from: .whitespacesAndNewlines) == nil,
              RelayRuntimeIdentity.isCanonicalFingerprint(runtimeKeyFingerprint),
              ticketGeneration > 0,
              isLowercaseHex(sessionNonce, count: 32),
              ephemeralKey.hasPrefix("04"),
              isLowercaseHex(ephemeralKey, count: 130),
              isLowercaseHex(challenge, count: 64),
              challengeExpiresAtEpochMillis > 0,
              cryptoVersion == relayIdentityAuthorizationCryptoVersion,
              allocationAuth == relayIdentityAuthorizationScheme
        else {
            throw RelayIdentityAuthorizationError.invalidChallenge
        }
        self.relayID = relayID
        self.relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
        self.relayNonce = relayNonce
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.ticketGeneration = ticketGeneration
        self.sessionNonce = sessionNonce
        self.ephemeralKey = ephemeralKey
        self.challenge = challenge
        self.challengeExpiresAtEpochMillis = challengeExpiresAtEpochMillis
        self.cryptoVersion = cryptoVersion
        self.allocationAuth = allocationAuth
    }

    public func signedMessageData() -> Data {
        Data(
            """
            AetherLink relay runtime registration authorization v1
            crypto_version
            \(cryptoVersion)
            allocation_auth
            \(allocationAuth)
            relay_id
            \(relayID)
            relay_expires_at
            \(relayExpiresAtEpochMillis)
            relay_nonce
            \(relayNonce)
            runtime_key_fingerprint
            \(runtimeKeyFingerprint)
            ticket_generation
            \(ticketGeneration)
            session_nonce
            \(sessionNonce)
            ephemeral_key
            \(ephemeralKey)
            challenge
            \(challenge)
            challenge_expires_at
            \(challengeExpiresAtEpochMillis)
            """.utf8
        )
    }

    private enum CodingKeys: String, CodingKey {
        case relayID = "relay_id"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case ticketGeneration = "ticket_generation"
        case sessionNonce = "session_nonce"
        case ephemeralKey = "ephemeral_key"
        case challenge
        case challengeExpiresAtEpochMillis = "challenge_expires_at"
        case cryptoVersion = "crypto_version"
        case allocationAuth = "allocation_auth"
    }
}

public enum RelayIdentityAuthorization {
    public static func verify(
        signatureBase64: String,
        messageData: Data,
        runtimeIdentity: RelayRuntimeIdentity
    ) -> Bool {
        guard let publicKeyData = Data(base64Encoded: runtimeIdentity.publicKeyBase64),
              let signatureData = Data(base64Encoded: signatureBase64),
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: publicKeyData),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: signatureData)
        else {
            return false
        }
        return publicKey.isValidSignature(signature, for: SHA256.hash(data: messageData))
    }
}

public enum RelayIdentityAuthorizationError: Error, Equatable, Sendable {
    case invalidRuntimeIdentity
    case invalidChallenge
    case invalidSignature
}

private func isLowercaseHex(_ value: String, count: Int) -> Bool {
    value.utf8.count == count && value.utf8.allSatisfy { byte in
        (UInt8(ascii: "0")...UInt8(ascii: "9")).contains(byte) ||
            (UInt8(ascii: "a")...UInt8(ascii: "f")).contains(byte)
    }
}
