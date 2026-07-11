import CryptoKit
import Foundation

private struct PairedRelayAllocationDynamicCodingKey: CodingKey {
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

private func rejectUnknownPairedRelayAllocationFields<Key: CodingKey>(
    _ decoder: Decoder,
    allowedKeys: [Key]
) throws {
    let container = try decoder.container(
        keyedBy: PairedRelayAllocationDynamicCodingKey.self
    )
    let allowedFields = Set(allowedKeys.map(\.stringValue))
    if let unknownField = container.allKeys.first(where: {
        !allowedFields.contains($0.stringValue)
    }) {
        throw DecodingError.dataCorruptedError(
            forKey: unknownField,
            in: container,
            debugDescription: "Unknown paired relay allocation field \(unknownField.stringValue)."
        )
    }
}

public enum PairedRelayAllocationAuthorizationError: Error, Equatable, LocalizedError, Sendable {
    case invalidField(String)
    case invalidPublicKey(String)
    case invalidFingerprint(String)
    case invalidSignature(String)

    public var errorDescription: String? {
        switch self {
        case .invalidField(let field):
            return "The paired relay allocation authorization field \(field) is invalid."
        case .invalidPublicKey(let field):
            return "The paired relay allocation authorization public key \(field) is invalid."
        case .invalidFingerprint(let field):
            return "The paired relay allocation authorization fingerprint \(field) is invalid."
        case .invalidSignature(let field):
            return "The paired relay allocation authorization signature \(field) is invalid."
        }
    }
}

public enum PairedRelayAllocationOperation: String, Codable, CaseIterable, Sendable {
    case claim
    case renew
}

public protocol PairedRelayAllocationRuntimeSigning: Sendable {
    func signPairedRelayAllocationAuthorization(
        _ challenge: PairedRelayAllocationAuthorizationChallenge
    ) throws -> PairedRelayAllocationRuntimeProof
}

public enum PairedRelayAllocationAuthorization {
    public static let scheme = "runtime-client-p256-v2"
    public static let protocolVersion = 2
    public static let runtimeContext =
        "AetherLink paired relay allocation runtime authorization v2"
    public static let clientContext =
        "AetherLink paired relay allocation client authorization v2"
    public static let maximumOpaqueIdentifierUTF8Length = 512
    public static let maximumNonceUTF8Length = 512

    public static func isCanonicalRelayID(_ value: String) -> Bool {
        value.hasPrefix("rt2-") &&
            value.utf8.count == 68 &&
            isLowercaseHex(String(value.dropFirst(4)), count: 64)
    }

    public static func isCanonicalDigest(_ value: String) -> Bool {
        isLowercaseHex(value, count: 64)
    }

    public static func isCanonicalOpaqueIdentifier(_ value: String) -> Bool {
        isCanonicalOpaqueValue(value, maximumUTF8Length: maximumOpaqueIdentifierUTF8Length)
    }

    public static func isCanonicalNonce(_ value: String) -> Bool {
        isCanonicalOpaqueValue(value, maximumUTF8Length: maximumNonceUTF8Length)
    }

    public static func routeTokenHash(_ routeToken: String) -> String {
        digestHex(Data(routeToken.utf8))
    }

    public static func publicKeyFingerprint(publicKeyBase64: String) throws -> String {
        let publicKey = try canonicalPublicKey(
            base64: publicKeyBase64,
            field: "public_key"
        )
        return digestHex(publicKey.derRepresentation)
    }

    public static func validatedRuntimePublicKey(
        base64: String,
        fingerprint: String
    ) throws -> P256.Signing.PublicKey {
        try validatedPublicKey(
            base64: base64,
            fingerprint: fingerprint,
            keyField: "runtime_public_key",
            fingerprintField: "runtime_key_fingerprint"
        )
    }

    public static func validatedClientPublicKey(
        base64: String,
        fingerprint: String
    ) throws -> P256.Signing.PublicKey {
        try validatedPublicKey(
            base64: base64,
            fingerprint: fingerprint,
            keyField: "client_public_key",
            fingerprintField: "client_key_fingerprint"
        )
    }

    public static func digestHex(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    fileprivate static func messageData(
        context: String,
        fields: [(String, String)]
    ) -> Data {
        let components = [context] + fields.flatMap { name, value in
            [name, String(value.utf8.count), value]
        }
        return Data(components.joined(separator: "\n").utf8)
    }

    fileprivate static func canonicalPublicKey(
        base64: String,
        field: String
    ) throws -> P256.Signing.PublicKey {
        guard let data = canonicalBase64Data(base64),
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: data),
              publicKey.derRepresentation == data else {
            throw PairedRelayAllocationAuthorizationError.invalidPublicKey(field)
        }
        return publicKey
    }

    fileprivate static func validatedSignature(
        base64: String,
        field: String
    ) throws -> P256.Signing.ECDSASignature {
        guard let data = canonicalBase64Data(base64),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: data),
              signature.derRepresentation == data else {
            throw PairedRelayAllocationAuthorizationError.invalidSignature(field)
        }
        return signature
    }

    fileprivate static func signatureBase64(
        messageData: Data,
        privateKey: P256.Signing.PrivateKey,
        expectedFingerprint: String,
        keyField: String,
        fingerprintField: String
    ) throws -> (publicKeyBase64: String, signatureBase64: String) {
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        _ = try validatedPublicKey(
            base64: publicKeyBase64,
            fingerprint: expectedFingerprint,
            keyField: keyField,
            fingerprintField: fingerprintField
        )
        let signature = try privateKey.signature(for: SHA256.hash(data: messageData))
        return (
            publicKeyBase64,
            signature.derRepresentation.base64EncodedString()
        )
    }

    fileprivate static func verify(
        signatureBase64: String,
        publicKeyBase64: String,
        expectedFingerprint: String,
        messageData: Data,
        keyField: String,
        fingerprintField: String,
        signatureField: String
    ) -> Bool {
        do {
            let publicKey = try validatedPublicKey(
                base64: publicKeyBase64,
                fingerprint: expectedFingerprint,
                keyField: keyField,
                fingerprintField: fingerprintField
            )
            let signature = try validatedSignature(
                base64: signatureBase64,
                field: signatureField
            )
            return publicKey.isValidSignature(
                signature,
                for: SHA256.hash(data: messageData)
            )
        } catch {
            return false
        }
    }

    private static func validatedPublicKey(
        base64: String,
        fingerprint: String,
        keyField: String,
        fingerprintField: String
    ) throws -> P256.Signing.PublicKey {
        let publicKey = try canonicalPublicKey(base64: base64, field: keyField)
        guard isCanonicalDigest(fingerprint),
              digestHex(publicKey.derRepresentation) == fingerprint else {
            throw PairedRelayAllocationAuthorizationError.invalidFingerprint(
                fingerprintField
            )
        }
        return publicKey
    }

    private static func canonicalBase64Data(_ value: String) -> Data? {
        guard let data = Data(base64Encoded: value),
              data.base64EncodedString() == value else {
            return nil
        }
        return data
    }

    private static func isCanonicalOpaqueValue(
        _ value: String,
        maximumUTF8Length: Int
    ) -> Bool {
        guard !value.isEmpty,
              value.utf8.count <= maximumUTF8Length else {
            return false
        }
        return value.unicodeScalars.allSatisfy { scalar in
            !CharacterSet.whitespacesAndNewlines.contains(scalar) &&
                !CharacterSet.controlCharacters.contains(scalar)
        }
    }

    private static func isLowercaseHex(_ value: String, count: Int) -> Bool {
        value.utf8.count == count && value.utf8.allSatisfy { byte in
            (UInt8(ascii: "0")...UInt8(ascii: "9")).contains(byte) ||
                (UInt8(ascii: "a")...UInt8(ascii: "f")).contains(byte)
        }
    }
}

public struct PairedRelayAllocationAuthorizationChallenge: Codable, Equatable, Sendable {
    public let scheme: String
    public let protocolVersion: Int
    public let operation: PairedRelayAllocationOperation
    public let requestID: String
    public let authorizationID: String
    public let currentRelayID: String
    public let nextRelayID: String
    public let routeTokenHash: String
    public let runtimeKeyFingerprint: String
    public let clientKeyFingerprint: String
    public let currentTicketGeneration: Int64
    public let nextTicketGeneration: Int64
    public let currentRelayExpiresAtEpochMillis: Int64
    public let currentRelayNonce: String
    public let nextRelayExpiresAtEpochMillis: Int64
    public let nextRelayNonce: String
    public let challenge: String
    public let challengeExpiresAtEpochMillis: Int64
    public let transportBinding: String

    public init(
        scheme: String = PairedRelayAllocationAuthorization.scheme,
        protocolVersion: Int = PairedRelayAllocationAuthorization.protocolVersion,
        operation: PairedRelayAllocationOperation,
        requestID: String,
        authorizationID: String,
        currentRelayID: String,
        nextRelayID: String,
        routeTokenHash: String,
        runtimeKeyFingerprint: String,
        clientKeyFingerprint: String,
        currentTicketGeneration: Int64,
        nextTicketGeneration: Int64,
        currentRelayExpiresAtEpochMillis: Int64,
        currentRelayNonce: String,
        nextRelayExpiresAtEpochMillis: Int64,
        nextRelayNonce: String,
        challenge: String,
        challengeExpiresAtEpochMillis: Int64,
        transportBinding: String
    ) throws {
        self.scheme = scheme
        self.protocolVersion = protocolVersion
        self.operation = operation
        self.requestID = requestID
        self.authorizationID = authorizationID
        self.currentRelayID = currentRelayID
        self.nextRelayID = nextRelayID
        self.routeTokenHash = routeTokenHash
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.clientKeyFingerprint = clientKeyFingerprint
        self.currentTicketGeneration = currentTicketGeneration
        self.nextTicketGeneration = nextTicketGeneration
        self.currentRelayExpiresAtEpochMillis = currentRelayExpiresAtEpochMillis
        self.currentRelayNonce = currentRelayNonce
        self.nextRelayExpiresAtEpochMillis = nextRelayExpiresAtEpochMillis
        self.nextRelayNonce = nextRelayNonce
        self.challenge = challenge
        self.challengeExpiresAtEpochMillis = challengeExpiresAtEpochMillis
        self.transportBinding = transportBinding
        try validateShape()
    }

    public init(from decoder: Decoder) throws {
        try rejectUnknownPairedRelayAllocationFields(
            decoder,
            allowedKeys: CodingKeys.allCases
        )
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            scheme: container.decode(String.self, forKey: .scheme),
            protocolVersion: container.decode(Int.self, forKey: .protocolVersion),
            operation: container.decode(PairedRelayAllocationOperation.self, forKey: .operation),
            requestID: container.decode(String.self, forKey: .requestID),
            authorizationID: container.decode(String.self, forKey: .authorizationID),
            currentRelayID: container.decode(String.self, forKey: .currentRelayID),
            nextRelayID: container.decode(String.self, forKey: .nextRelayID),
            routeTokenHash: container.decode(String.self, forKey: .routeTokenHash),
            runtimeKeyFingerprint: container.decode(String.self, forKey: .runtimeKeyFingerprint),
            clientKeyFingerprint: container.decode(String.self, forKey: .clientKeyFingerprint),
            currentTicketGeneration: container.decode(Int64.self, forKey: .currentTicketGeneration),
            nextTicketGeneration: container.decode(Int64.self, forKey: .nextTicketGeneration),
            currentRelayExpiresAtEpochMillis: container.decode(Int64.self, forKey: .currentRelayExpiresAtEpochMillis),
            currentRelayNonce: container.decode(String.self, forKey: .currentRelayNonce),
            nextRelayExpiresAtEpochMillis: container.decode(Int64.self, forKey: .nextRelayExpiresAtEpochMillis),
            nextRelayNonce: container.decode(String.self, forKey: .nextRelayNonce),
            challenge: container.decode(String.self, forKey: .challenge),
            challengeExpiresAtEpochMillis: container.decode(Int64.self, forKey: .challengeExpiresAtEpochMillis),
            transportBinding: container.decode(String.self, forKey: .transportBinding)
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(scheme, forKey: .scheme)
        try container.encode(protocolVersion, forKey: .protocolVersion)
        try container.encode(operation, forKey: .operation)
        try container.encode(requestID, forKey: .requestID)
        try container.encode(authorizationID, forKey: .authorizationID)
        try container.encode(currentRelayID, forKey: .currentRelayID)
        try container.encode(nextRelayID, forKey: .nextRelayID)
        try container.encode(routeTokenHash, forKey: .routeTokenHash)
        try container.encode(runtimeKeyFingerprint, forKey: .runtimeKeyFingerprint)
        try container.encode(clientKeyFingerprint, forKey: .clientKeyFingerprint)
        try container.encode(currentTicketGeneration, forKey: .currentTicketGeneration)
        try container.encode(nextTicketGeneration, forKey: .nextTicketGeneration)
        try container.encode(currentRelayExpiresAtEpochMillis, forKey: .currentRelayExpiresAtEpochMillis)
        try container.encode(currentRelayNonce, forKey: .currentRelayNonce)
        try container.encode(nextRelayExpiresAtEpochMillis, forKey: .nextRelayExpiresAtEpochMillis)
        try container.encode(nextRelayNonce, forKey: .nextRelayNonce)
        try container.encode(challenge, forKey: .challenge)
        try container.encode(challengeExpiresAtEpochMillis, forKey: .challengeExpiresAtEpochMillis)
        try container.encode(transportBinding, forKey: .transportBinding)
    }

    public func runtimeSignedMessageData() -> Data {
        PairedRelayAllocationAuthorization.messageData(
            context: PairedRelayAllocationAuthorization.runtimeContext,
            fields: fields
        )
    }

    public func clientSignedMessageData() -> Data {
        PairedRelayAllocationAuthorization.messageData(
            context: PairedRelayAllocationAuthorization.clientContext,
            fields: fields
        )
    }

    public func runtimeTranscriptDigest() -> String {
        PairedRelayAllocationAuthorization.digestHex(runtimeSignedMessageData())
    }

    public func clientTranscriptDigest() -> String {
        PairedRelayAllocationAuthorization.digestHex(clientSignedMessageData())
    }

    public func isFresh(atEpochMillis nowEpochMillis: Int64) -> Bool {
        nowEpochMillis >= 0 &&
            currentRelayExpiresAtEpochMillis > nowEpochMillis &&
            nextRelayExpiresAtEpochMillis > nowEpochMillis &&
            challengeExpiresAtEpochMillis > nowEpochMillis
    }

    public func validateShape() throws {
        guard scheme == PairedRelayAllocationAuthorization.scheme else {
            throw PairedRelayAllocationAuthorizationError.invalidField("scheme")
        }
        guard protocolVersion == PairedRelayAllocationAuthorization.protocolVersion else {
            throw PairedRelayAllocationAuthorizationError.invalidField("protocol_version")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(requestID) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("request_id")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(authorizationID) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("authorization_id")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalRelayID(currentRelayID) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("current_relay_id")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalRelayID(nextRelayID) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("next_relay_id")
        }
        guard operation != .claim || currentRelayID != nextRelayID else {
            throw PairedRelayAllocationAuthorizationError.invalidField("next_relay_id")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalDigest(routeTokenHash) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("route_token_hash")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalDigest(runtimeKeyFingerprint) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("runtime_key_fingerprint")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalDigest(clientKeyFingerprint) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("client_key_fingerprint")
        }
        guard currentTicketGeneration > 0 else {
            throw PairedRelayAllocationAuthorizationError.invalidField("current_ticket_generation")
        }
        guard currentTicketGeneration < Int64.max,
              nextTicketGeneration == currentTicketGeneration + 1 else {
            throw PairedRelayAllocationAuthorizationError.invalidField("next_ticket_generation")
        }
        guard currentRelayExpiresAtEpochMillis > 0 else {
            throw PairedRelayAllocationAuthorizationError.invalidField("current_relay_expires_at")
        }
        guard nextRelayExpiresAtEpochMillis > currentRelayExpiresAtEpochMillis else {
            throw PairedRelayAllocationAuthorizationError.invalidField("next_relay_expires_at")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalNonce(currentRelayNonce) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("current_relay_nonce")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalNonce(nextRelayNonce),
              nextRelayNonce != currentRelayNonce else {
            throw PairedRelayAllocationAuthorizationError.invalidField("next_relay_nonce")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalDigest(challenge) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("challenge")
        }
        guard challengeExpiresAtEpochMillis > 0 else {
            throw PairedRelayAllocationAuthorizationError.invalidField("challenge_expires_at")
        }
        guard PairedRelayAllocationAuthorization.isCanonicalDigest(transportBinding) else {
            throw PairedRelayAllocationAuthorizationError.invalidField("transport_binding")
        }
    }

    private var fields: [(String, String)] {
        [
            ("scheme", scheme),
            ("protocol_version", String(protocolVersion)),
            ("operation", operation.rawValue),
            ("request_id", requestID),
            ("authorization_id", authorizationID),
            ("current_relay_id", currentRelayID),
            ("next_relay_id", nextRelayID),
            ("route_token_hash", routeTokenHash),
            ("runtime_key_fingerprint", runtimeKeyFingerprint),
            ("client_key_fingerprint", clientKeyFingerprint),
            ("current_ticket_generation", String(currentTicketGeneration)),
            ("next_ticket_generation", String(nextTicketGeneration)),
            ("current_relay_expires_at", String(currentRelayExpiresAtEpochMillis)),
            ("current_relay_nonce", currentRelayNonce),
            ("next_relay_expires_at", String(nextRelayExpiresAtEpochMillis)),
            ("next_relay_nonce", nextRelayNonce),
            ("challenge", challenge),
            ("challenge_expires_at", String(challengeExpiresAtEpochMillis)),
            ("transport_binding", transportBinding),
        ]
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case scheme
        case protocolVersion = "protocol_version"
        case operation
        case requestID = "request_id"
        case authorizationID = "authorization_id"
        case currentRelayID = "current_relay_id"
        case nextRelayID = "next_relay_id"
        case routeTokenHash = "route_token_hash"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case clientKeyFingerprint = "client_key_fingerprint"
        case currentTicketGeneration = "current_ticket_generation"
        case nextTicketGeneration = "next_ticket_generation"
        case currentRelayExpiresAtEpochMillis = "current_relay_expires_at"
        case currentRelayNonce = "current_relay_nonce"
        case nextRelayExpiresAtEpochMillis = "next_relay_expires_at"
        case nextRelayNonce = "next_relay_nonce"
        case challenge
        case challengeExpiresAtEpochMillis = "challenge_expires_at"
        case transportBinding = "transport_binding"
    }
}

public typealias PairedRelayAllocationAuthorizationTranscript =
    PairedRelayAllocationAuthorizationChallenge

public struct PairedRelayAllocationRuntimeProof: Codable, Equatable, Sendable {
    public let publicKeyBase64: String
    public let signatureBase64: String

    public init(publicKeyBase64: String, signatureBase64: String) throws {
        _ = try PairedRelayAllocationAuthorization.canonicalPublicKey(
            base64: publicKeyBase64,
            field: "runtime_public_key"
        )
        _ = try PairedRelayAllocationAuthorization.validatedSignature(
            base64: signatureBase64,
            field: "runtime_signature"
        )
        self.publicKeyBase64 = publicKeyBase64
        self.signatureBase64 = signatureBase64
    }

    public init(from decoder: Decoder) throws {
        try rejectUnknownPairedRelayAllocationFields(
            decoder,
            allowedKeys: CodingKeys.allCases
        )
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            publicKeyBase64: container.decode(String.self, forKey: .publicKeyBase64),
            signatureBase64: container.decode(String.self, forKey: .signatureBase64)
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(publicKeyBase64, forKey: .publicKeyBase64)
        try container.encode(signatureBase64, forKey: .signatureBase64)
    }

    public static func sign(
        challenge: PairedRelayAllocationAuthorizationChallenge,
        using privateKey: P256.Signing.PrivateKey
    ) throws -> Self {
        try challenge.validateShape()
        let proof = try PairedRelayAllocationAuthorization.signatureBase64(
            messageData: challenge.runtimeSignedMessageData(),
            privateKey: privateKey,
            expectedFingerprint: challenge.runtimeKeyFingerprint,
            keyField: "runtime_public_key",
            fingerprintField: "runtime_key_fingerprint"
        )
        return try Self(
            publicKeyBase64: proof.publicKeyBase64,
            signatureBase64: proof.signatureBase64
        )
    }

    public func verify(
        challenge: PairedRelayAllocationAuthorizationChallenge
    ) -> Bool {
        guard (try? challenge.validateShape()) != nil else { return false }
        return PairedRelayAllocationAuthorization.verify(
            signatureBase64: signatureBase64,
            publicKeyBase64: publicKeyBase64,
            expectedFingerprint: challenge.runtimeKeyFingerprint,
            messageData: challenge.runtimeSignedMessageData(),
            keyField: "runtime_public_key",
            fingerprintField: "runtime_key_fingerprint",
            signatureField: "runtime_signature"
        )
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case publicKeyBase64 = "runtime_public_key"
        case signatureBase64 = "runtime_signature"
    }
}

public struct PairedRelayAllocationClientProof: Codable, Equatable, Sendable {
    public let publicKeyBase64: String
    public let signatureBase64: String

    public init(publicKeyBase64: String, signatureBase64: String) throws {
        _ = try PairedRelayAllocationAuthorization.canonicalPublicKey(
            base64: publicKeyBase64,
            field: "client_public_key"
        )
        _ = try PairedRelayAllocationAuthorization.validatedSignature(
            base64: signatureBase64,
            field: "client_signature"
        )
        self.publicKeyBase64 = publicKeyBase64
        self.signatureBase64 = signatureBase64
    }

    public init(from decoder: Decoder) throws {
        try rejectUnknownPairedRelayAllocationFields(
            decoder,
            allowedKeys: CodingKeys.allCases
        )
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            publicKeyBase64: container.decode(String.self, forKey: .publicKeyBase64),
            signatureBase64: container.decode(String.self, forKey: .signatureBase64)
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(publicKeyBase64, forKey: .publicKeyBase64)
        try container.encode(signatureBase64, forKey: .signatureBase64)
    }

    public static func sign(
        challenge: PairedRelayAllocationAuthorizationChallenge,
        using privateKey: P256.Signing.PrivateKey
    ) throws -> Self {
        try challenge.validateShape()
        let proof = try PairedRelayAllocationAuthorization.signatureBase64(
            messageData: challenge.clientSignedMessageData(),
            privateKey: privateKey,
            expectedFingerprint: challenge.clientKeyFingerprint,
            keyField: "client_public_key",
            fingerprintField: "client_key_fingerprint"
        )
        return try Self(
            publicKeyBase64: proof.publicKeyBase64,
            signatureBase64: proof.signatureBase64
        )
    }

    public func verify(
        challenge: PairedRelayAllocationAuthorizationChallenge
    ) -> Bool {
        guard (try? challenge.validateShape()) != nil else { return false }
        return PairedRelayAllocationAuthorization.verify(
            signatureBase64: signatureBase64,
            publicKeyBase64: publicKeyBase64,
            expectedFingerprint: challenge.clientKeyFingerprint,
            messageData: challenge.clientSignedMessageData(),
            keyField: "client_public_key",
            fingerprintField: "client_key_fingerprint",
            signatureField: "client_signature"
        )
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case publicKeyBase64 = "client_public_key"
        case signatureBase64 = "client_signature"
    }
}
