import BridgeProtocol
import CryptoKit
import Foundation

public struct RelayAllocationPreflightResponse: Codable, Equatable, Sendable {
    public static let responsePrefix = "\(RelayHandshake.prefix) preflight "

    public let preflight: Bool
    public let cryptoVersion: Int
    public let allocationAuth: String

    public init() {
        preflight = true
        cryptoVersion = relayIdentityAuthorizationCryptoVersion
        allocationAuth = relayIdentityAuthorizationScheme
    }

    public func responseLine() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return Data(
            "\(Self.responsePrefix)\(String(decoding: try encoder.encode(self), as: UTF8.self))\n".utf8
        )
    }

    public static func parseResponseLine(_ line: String) throws -> Self {
        let data = try exactJSONBody(line, prefix: responsePrefix, fields: fieldNames)
        let response = try JSONDecoder().decode(Self.self, from: data)
        guard response == Self() else { throw RelayAllocationError.invalidResponseFormat }
        return response
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case preflight
        case cryptoVersion = "crypto_version"
        case allocationAuth = "allocation_auth"
    }

    private static let fieldNames = Set(CodingKeys.allCases.map(\.stringValue))
}

public struct RelayAllocationChallengeResponse: Equatable, Sendable {
    public let challenge: RelayAllocationIdentityChallenge

    public init(challenge: RelayAllocationIdentityChallenge) {
        self.challenge = challenge
    }

    public func responseLine() throws -> Data {
        try identityChallengeLine(
            prefix: RelayAllocationIdentityChallenge.responsePrefix,
            challenge: challenge
        )
    }

    public static func parseResponseLine(_ line: String) throws -> Self {
        let decoded = try parseIdentityChallengeLine(
            line,
            prefix: RelayAllocationIdentityChallenge.responsePrefix,
            fields: [
                "operation", "relay_id", "route_token_hash", "runtime_key_fingerprint",
                "ticket_generation", "challenge", "challenge_expires_at", "crypto_version",
                "allocation_auth"
            ],
            as: RelayAllocationIdentityChallenge.self
        )
        return try Self(challenge: RelayAllocationIdentityChallenge(
            operation: decoded.operation,
            relayID: decoded.relayID,
            routeTokenHash: decoded.routeTokenHash,
            runtimeKeyFingerprint: decoded.runtimeKeyFingerprint,
            ticketGeneration: decoded.ticketGeneration,
            challenge: decoded.challenge,
            challengeExpiresAtEpochMillis: decoded.challengeExpiresAtEpochMillis,
            cryptoVersion: decoded.cryptoVersion,
            allocationAuth: decoded.allocationAuth
        ))
    }
}

public struct RelayRuntimeRegistrationChallengeResponse: Equatable, Sendable {
    public let challenge: RelayRuntimeRegistrationIdentityChallenge

    public init(challenge: RelayRuntimeRegistrationIdentityChallenge) {
        self.challenge = challenge
    }

    public func responseLine() throws -> Data {
        try identityChallengeLine(
            prefix: RelayRuntimeRegistrationIdentityChallenge.responsePrefix,
            challenge: challenge
        )
    }

    public static func parseResponseLine(_ line: String) throws -> Self {
        let decoded = try parseIdentityChallengeLine(
            line,
            prefix: RelayRuntimeRegistrationIdentityChallenge.responsePrefix,
            fields: [
                "relay_id", "relay_expires_at", "relay_nonce", "runtime_key_fingerprint",
                "ticket_generation", "session_nonce", "ephemeral_key", "challenge",
                "challenge_expires_at", "crypto_version", "allocation_auth"
            ],
            as: RelayRuntimeRegistrationIdentityChallenge.self
        )
        return try Self(challenge: RelayRuntimeRegistrationIdentityChallenge(
            relayID: decoded.relayID,
            relayExpiresAtEpochMillis: decoded.relayExpiresAtEpochMillis,
            relayNonce: decoded.relayNonce,
            runtimeKeyFingerprint: decoded.runtimeKeyFingerprint,
            ticketGeneration: decoded.ticketGeneration,
            sessionNonce: decoded.sessionNonce,
            ephemeralKey: decoded.ephemeralKey,
            challenge: decoded.challenge,
            challengeExpiresAtEpochMillis: decoded.challengeExpiresAtEpochMillis,
            cryptoVersion: decoded.cryptoVersion,
            allocationAuth: decoded.allocationAuth
        ))
    }
}

public struct RelayAllocationProofRequest: Equatable, Sendable {
    public static let prefix = "\(RelayHandshake.prefix) allocation_proof"

    public let challenge: String
    public let signatureBase64: String

    public init(
        challenge: String,
        signatureBase64: String,
        runtimeIdentity: RelayRuntimeIdentity
    ) throws {
        try validateProofChallenge(challenge)
        _ = try RelayIdentityAuthorizationProof(
            runtimeIdentity: runtimeIdentity,
            signatureBase64: signatureBase64
        )
        try validateCanonicalSignature(signatureBase64)
        self.challenge = challenge
        self.signatureBase64 = signatureBase64
    }

    public static func parse(_ line: String, runtimeIdentity: RelayRuntimeIdentity) throws -> Self {
        let fields = try exactIdentityProofFields(line, action: "allocation_proof")
        return try Self(
            challenge: fields.challenge,
            signatureBase64: fields.signature,
            runtimeIdentity: runtimeIdentity
        )
    }

    public func requestLine() -> Data {
        Data(
            "\(Self.prefix) crypto=2 challenge=\(challenge) signature=\(signatureBase64)\n".utf8
        )
    }
}

public struct RelayRuntimeRegistrationProofRequest: Equatable, Sendable {
    public static let prefix = "\(RelayHandshake.prefix) registration_proof"

    public let challenge: String
    public let signatureBase64: String

    public init(
        challenge: String,
        signatureBase64: String,
        runtimeIdentity: RelayRuntimeIdentity
    ) throws {
        try validateProofChallenge(challenge)
        _ = try RelayIdentityAuthorizationProof(
            runtimeIdentity: runtimeIdentity,
            signatureBase64: signatureBase64
        )
        try validateCanonicalSignature(signatureBase64)
        self.challenge = challenge
        self.signatureBase64 = signatureBase64
    }

    public static func parse(_ line: String, runtimeIdentity: RelayRuntimeIdentity) throws -> Self {
        let fields = try exactIdentityProofFields(line, action: "registration_proof")
        return try Self(
            challenge: fields.challenge,
            signatureBase64: fields.signature,
            runtimeIdentity: runtimeIdentity
        )
    }

    public func requestLine() -> Data {
        Data(
            "\(Self.prefix) crypto=2 challenge=\(challenge) signature=\(signatureBase64)\n".utf8
        )
    }
}

private func identityChallengeLine<T: Encodable>(prefix: String, challenge: T) throws -> Data {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    return Data("\(prefix)\(String(decoding: try encoder.encode(challenge), as: UTF8.self))\n".utf8)
}

private func parseIdentityChallengeLine<T: Decodable>(
    _ line: String,
    prefix: String,
    fields: Set<String>,
    as type: T.Type
) throws -> T {
    guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else {
        throw RelayAllocationError.invalidResponseFormat
    }
    let body = String(line.dropLast())
    guard body.hasPrefix(prefix), !body.dropFirst(prefix.count).contains("\n") else {
        throw RelayAllocationError.invalidResponseFormat
    }
    do {
        let data = Data(body.dropFirst(prefix.count).utf8)
        try StrictJSONDocumentValidator.validate(data)
        guard let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              Set(payload.keys) == fields
        else {
            throw RelayAllocationError.unexpectedResponseMetadata
        }
        return try JSONDecoder().decode(T.self, from: data)
    } catch {
        throw RelayAllocationError.invalidResponseFormat
    }
}

private func exactJSONBody(
    _ line: String,
    prefix: String,
    fields: Set<String>
) throws -> Data {
    guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else {
        throw RelayAllocationError.invalidResponseFormat
    }
    let body = String(line.dropLast())
    guard body.hasPrefix(prefix) else { throw RelayAllocationError.invalidResponseFormat }
    let data = Data(body.dropFirst(prefix.count).utf8)
    do {
        try StrictJSONDocumentValidator.validate(data)
        guard let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              Set(payload.keys) == fields
        else {
            throw RelayAllocationError.unexpectedResponseMetadata
        }
        return data
    } catch let error as RelayAllocationError {
        throw error
    } catch {
        throw RelayAllocationError.invalidResponseFormat
    }
}

private func exactIdentityProofFields(
    _ line: String,
    action: String
) throws -> (challenge: String, signature: String) {
    guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else {
        throw RelayAllocationError.invalidFormat
    }
    let parts = line.dropLast().split(separator: " ", omittingEmptySubsequences: false)
    guard parts.count == 5,
          parts[0] == Substring(RelayHandshake.prefix),
          parts[1] == Substring(action),
          parts[2] == "crypto=2",
          let challenge = fieldValue(parts[3], name: "challenge"),
          let signature = fieldValue(parts[4], name: "signature")
    else {
        throw RelayAllocationError.invalidFormat
    }
    return (challenge, signature)
}

private func fieldValue(_ field: Substring, name: String) -> String? {
    let prefix = "\(name)="
    guard field.hasPrefix(prefix) else { return nil }
    let value = String(field.dropFirst(prefix.count))
    return value.isEmpty ? nil : value
}

private func validateProofChallenge(_ challenge: String) throws {
    guard challenge.utf8.count == 64,
          challenge.utf8.allSatisfy({
            (UInt8(ascii: "0")...UInt8(ascii: "9")).contains($0) ||
                (UInt8(ascii: "a")...UInt8(ascii: "f")).contains($0)
          })
    else {
        throw RelayAllocationError.invalidFormat
    }
}

private func validateCanonicalSignature(_ signatureBase64: String) throws {
    guard let data = Data(base64Encoded: signatureBase64),
          data.base64EncodedString() == signatureBase64,
          let signature = try? P256.Signing.ECDSASignature(derRepresentation: data),
          signature.derRepresentation == data
    else {
        throw RelayAllocationError.invalidFormat
    }
}
