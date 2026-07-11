import CryptoKit
import Foundation

public enum PairedClientRelayRegistrationAuthorizationError: Error, Equatable, Sendable {
    case invalidField(String)
    case invalidPublicKey
    case invalidSignature
    case clientKeyFingerprintMismatch
}

public enum PairedClientRelayRegistrationRole: String, Codable, Sendable {
    case client
}

public enum PairedClientRelayRegistrationAuthorization {
    public static let scheme = "paired-client-p256-v1"
    public static let protocolVersion = 1
    public static let context = "AetherLink relay client registration authorization v1"
    public static let maximumRelayNonceUTF8Length = 512

    public static func clientKeyFingerprint(publicKeyBase64: String) throws -> String {
        let publicKey = try canonicalPublicKey(base64: publicKeyBase64)
        return SHA256.hash(data: publicKey.derRepresentation)
            .map { String(format: "%02x", $0) }
            .joined()
    }

    fileprivate static func canonicalPublicKey(
        base64: String
    ) throws -> P256.Signing.PublicKey {
        guard let data = canonicalBase64Data(base64),
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: data),
              publicKey.derRepresentation == data else {
            throw PairedClientRelayRegistrationAuthorizationError.invalidPublicKey
        }
        return publicKey
    }

    fileprivate static func canonicalSignature(
        base64: String
    ) throws -> P256.Signing.ECDSASignature {
        guard let data = canonicalBase64Data(base64),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: data),
              signature.derRepresentation == data else {
            throw PairedClientRelayRegistrationAuthorizationError.invalidSignature
        }
        return signature
    }

    fileprivate static func digestHex(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    private static func canonicalBase64Data(_ value: String) -> Data? {
        guard let data = Data(base64Encoded: value),
              data.base64EncodedString() == value else {
            return nil
        }
        return data
    }
}

public struct PairedClientRelayRegistrationChallenge: Codable, Equatable, Sendable {
    public let scheme: String
    public let protocolVersion: Int
    public let role: PairedClientRelayRegistrationRole
    public let relayID: String
    public let relayExpiresAtEpochMillis: Int64
    public let relayNonce: String
    public let runtimeKeyFingerprint: String
    public let clientKeyFingerprint: String
    public let ticketGeneration: Int64
    public let sessionNonce: String
    public let ephemeralKey: String
    public let challenge: String
    public let challengeExpiresAtEpochMillis: Int64

    public init(
        scheme: String = PairedClientRelayRegistrationAuthorization.scheme,
        protocolVersion: Int = PairedClientRelayRegistrationAuthorization.protocolVersion,
        role: PairedClientRelayRegistrationRole = .client,
        relayID: String,
        relayExpiresAtEpochMillis: Int64,
        relayNonce: String,
        runtimeKeyFingerprint: String,
        clientKeyFingerprint: String,
        ticketGeneration: Int64,
        sessionNonce: String,
        ephemeralKey: String,
        challenge: String,
        challengeExpiresAtEpochMillis: Int64
    ) throws {
        self.scheme = scheme
        self.protocolVersion = protocolVersion
        self.role = role
        self.relayID = relayID
        self.relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
        self.relayNonce = relayNonce
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.clientKeyFingerprint = clientKeyFingerprint
        self.ticketGeneration = ticketGeneration
        self.sessionNonce = sessionNonce
        self.ephemeralKey = ephemeralKey
        self.challenge = challenge
        self.challengeExpiresAtEpochMillis = challengeExpiresAtEpochMillis
        try validateShape()
    }

    public init(from decoder: Decoder) throws {
        let dynamic = try decoder.container(
            keyedBy: PairedClientRelayRegistrationDynamicCodingKey.self
        )
        let allowed = Set(CodingKeys.allCases.map(\.stringValue))
        if let unknown = dynamic.allKeys.first(where: { !allowed.contains($0.stringValue) }) {
            throw DecodingError.dataCorruptedError(
                forKey: unknown,
                in: dynamic,
                debugDescription: "Unknown paired client registration field \(unknown.stringValue)."
            )
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            scheme: container.decode(String.self, forKey: .scheme),
            protocolVersion: container.decode(Int.self, forKey: .protocolVersion),
            role: container.decode(PairedClientRelayRegistrationRole.self, forKey: .role),
            relayID: container.decode(String.self, forKey: .relayID),
            relayExpiresAtEpochMillis: container.decode(Int64.self, forKey: .relayExpiresAtEpochMillis),
            relayNonce: container.decode(String.self, forKey: .relayNonce),
            runtimeKeyFingerprint: container.decode(String.self, forKey: .runtimeKeyFingerprint),
            clientKeyFingerprint: container.decode(String.self, forKey: .clientKeyFingerprint),
            ticketGeneration: container.decode(Int64.self, forKey: .ticketGeneration),
            sessionNonce: container.decode(String.self, forKey: .sessionNonce),
            ephemeralKey: container.decode(String.self, forKey: .ephemeralKey),
            challenge: container.decode(String.self, forKey: .challenge),
            challengeExpiresAtEpochMillis: container.decode(Int64.self, forKey: .challengeExpiresAtEpochMillis)
        )
    }

    public func transcriptData() -> Data {
        let fields = [
            ("scheme", scheme),
            ("protocol_version", String(protocolVersion)),
            ("role", role.rawValue),
            ("relay_id", relayID),
            ("relay_expires_at", String(relayExpiresAtEpochMillis)),
            ("relay_nonce", relayNonce),
            ("runtime_key_fingerprint", runtimeKeyFingerprint),
            ("client_key_fingerprint", clientKeyFingerprint),
            ("ticket_generation", String(ticketGeneration)),
            ("session_nonce", sessionNonce),
            ("ephemeral_key", ephemeralKey),
            ("challenge", challenge),
            ("challenge_expires_at", String(challengeExpiresAtEpochMillis)),
        ]
        let components = [PairedClientRelayRegistrationAuthorization.context] +
            fields.flatMap { name, value in [name, String(value.utf8.count), value] }
        return Data(components.joined(separator: "\n").utf8)
    }

    public func transcriptDigest() -> String {
        PairedClientRelayRegistrationAuthorization.digestHex(transcriptData())
    }

    public func isRelayFresh(atEpochMillis nowEpochMillis: Int64) -> Bool {
        nowEpochMillis >= 0 && relayExpiresAtEpochMillis > nowEpochMillis
    }

    public func isChallengeFresh(atEpochMillis nowEpochMillis: Int64) -> Bool {
        nowEpochMillis >= 0 && challengeExpiresAtEpochMillis > nowEpochMillis
    }

    public func isFresh(atEpochMillis nowEpochMillis: Int64) -> Bool {
        isRelayFresh(atEpochMillis: nowEpochMillis) &&
            isChallengeFresh(atEpochMillis: nowEpochMillis)
    }

    public func validateShape() throws {
        guard scheme == PairedClientRelayRegistrationAuthorization.scheme else {
            throw invalid("scheme")
        }
        guard protocolVersion == PairedClientRelayRegistrationAuthorization.protocolVersion else {
            throw invalid("protocol_version")
        }
        guard role == .client else { throw invalid("role") }
        guard PairedRelayAllocationAuthorization.isCanonicalRelayID(relayID) else {
            throw invalid("relay_id")
        }
        guard relayExpiresAtEpochMillis > 0 else { throw invalid("relay_expires_at") }
        guard Self.isCanonicalRelayNonce(relayNonce) else { throw invalid("relay_nonce") }
        guard Self.isCanonicalDigest(runtimeKeyFingerprint) else {
            throw invalid("runtime_key_fingerprint")
        }
        guard Self.isCanonicalDigest(clientKeyFingerprint),
              clientKeyFingerprint != runtimeKeyFingerprint else {
            throw invalid("client_key_fingerprint")
        }
        guard ticketGeneration > 0 else { throw invalid("ticket_generation") }
        guard RelaySessionNonce.isCanonical(sessionNonce) else { throw invalid("session_nonce") }
        guard RelaySessionCrypto.isCanonicalEphemeralKey(ephemeralKey) else {
            throw invalid("ephemeral_key")
        }
        guard Self.isCanonicalDigest(challenge) else { throw invalid("challenge") }
        guard challengeExpiresAtEpochMillis > 0 else { throw invalid("challenge_expires_at") }
    }

    private static func isCanonicalDigest(_ value: String) -> Bool {
        value.utf8.count == 64 && value.utf8.allSatisfy { byte in
            (UInt8(ascii: "0")...UInt8(ascii: "9")).contains(byte) ||
                (UInt8(ascii: "a")...UInt8(ascii: "f")).contains(byte)
        }
    }

    private static func isCanonicalRelayNonce(_ value: String) -> Bool {
        !value.isEmpty &&
            value.utf8.count <= PairedClientRelayRegistrationAuthorization.maximumRelayNonceUTF8Length &&
            value.unicodeScalars.allSatisfy { scalar in
                !CharacterSet.whitespacesAndNewlines.contains(scalar) &&
                    !CharacterSet.controlCharacters.contains(scalar)
            }
    }

    private func invalid(
        _ field: String
    ) -> PairedClientRelayRegistrationAuthorizationError {
        .invalidField(field)
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case scheme
        case protocolVersion = "protocol_version"
        case role
        case relayID = "relay_id"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case clientKeyFingerprint = "client_key_fingerprint"
        case ticketGeneration = "ticket_generation"
        case sessionNonce = "session_nonce"
        case ephemeralKey = "ephemeral_key"
        case challenge
        case challengeExpiresAtEpochMillis = "challenge_expires_at"
    }
}

public struct PairedClientRelayRegistrationProof: Codable, Equatable, Sendable {
    public let clientPublicKeyBase64: String
    public let clientSignatureBase64: String

    public init(clientPublicKeyBase64: String, clientSignatureBase64: String) throws {
        _ = try PairedClientRelayRegistrationAuthorization.canonicalPublicKey(
            base64: clientPublicKeyBase64
        )
        _ = try PairedClientRelayRegistrationAuthorization.canonicalSignature(
            base64: clientSignatureBase64
        )
        self.clientPublicKeyBase64 = clientPublicKeyBase64
        self.clientSignatureBase64 = clientSignatureBase64
    }

    public static func sign(
        challenge: PairedClientRelayRegistrationChallenge,
        using privateKey: P256.Signing.PrivateKey
    ) throws -> Self {
        try challenge.validateShape()
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        guard try PairedClientRelayRegistrationAuthorization.clientKeyFingerprint(
            publicKeyBase64: publicKeyBase64
        ) == challenge.clientKeyFingerprint else {
            throw PairedClientRelayRegistrationAuthorizationError.clientKeyFingerprintMismatch
        }
        let signature = try privateKey.signature(
            for: SHA256.hash(data: challenge.transcriptData())
        )
        return try Self(
            clientPublicKeyBase64: publicKeyBase64,
            clientSignatureBase64: signature.derRepresentation.base64EncodedString()
        )
    }

    public func verify(challenge: PairedClientRelayRegistrationChallenge) -> Bool {
        do {
            try challenge.validateShape()
            guard try PairedClientRelayRegistrationAuthorization.clientKeyFingerprint(
                publicKeyBase64: clientPublicKeyBase64
            ) == challenge.clientKeyFingerprint else {
                return false
            }
            let publicKey = try PairedClientRelayRegistrationAuthorization.canonicalPublicKey(
                base64: clientPublicKeyBase64
            )
            let signature = try PairedClientRelayRegistrationAuthorization.canonicalSignature(
                base64: clientSignatureBase64
            )
            return publicKey.isValidSignature(
                signature,
                for: SHA256.hash(data: challenge.transcriptData())
            )
        } catch {
            return false
        }
    }

    private enum CodingKeys: String, CodingKey {
        case clientPublicKeyBase64 = "client_public_key"
        case clientSignatureBase64 = "client_signature"
    }
}

private struct PairedClientRelayRegistrationDynamicCodingKey: CodingKey {
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
