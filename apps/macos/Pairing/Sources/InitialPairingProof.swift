import CryptoKit
import Foundation

public enum InitialPairingProofError: Error, Equatable, LocalizedError, Sendable {
    case invalidField(String)
    case invalidPublicKey(String)
    case invalidFingerprint(String)
    case invalidSignature
    case rejectedResultCannotBeSigned

    public var errorDescription: String? {
        switch self {
        case .invalidField(let field):
            return "The initial pairing proof field \(field) is invalid."
        case .invalidPublicKey(let field):
            return "The initial pairing proof public key \(field) is invalid."
        case .invalidFingerprint(let field):
            return "The initial pairing proof fingerprint \(field) is invalid."
        case .invalidSignature:
            return "The initial pairing proof signature is invalid."
        case .rejectedResultCannotBeSigned:
            return "Only accepted initial pairing results may be signed."
        }
    }
}

public protocol InitialPairingRuntimeResultSigning: Sendable {
    func signInitialPairingResult(
        _ result: InitialPairingRuntimeResult
    ) throws -> InitialPairingRuntimeResultProof
}

public enum InitialPairingProof {
    public static let scheme = "p256-sha256-der-v1"
    public static let protocolVersion = 1
    public static let clientContext = "AetherLink initial pairing client proof v1"
    public static let runtimeResultContext = "AetherLink initial pairing runtime result proof v1"

    public static func isCanonicalTransportBinding(_ value: String) -> Bool {
        value == "none" || isLowercaseHex(value, count: 64)
    }

    public static func isCanonicalDigest(_ value: String) -> Bool {
        isLowercaseHex(value, count: 64)
    }

    static func messageData(context: String, fields: [(String, String)]) -> Data {
        let components = [context] + fields.flatMap { name, value in
            [name, String(value.utf8.count), value]
        }
        return Data(components.joined(separator: "\n").utf8)
    }

    static func digestHex(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    static func validatedPublicKey(
        base64: String,
        fingerprint: String,
        keyField: String,
        fingerprintField: String
    ) throws -> P256.Signing.PublicKey {
        guard let data = canonicalBase64Data(base64),
              let key = try? P256.Signing.PublicKey(derRepresentation: data),
              key.derRepresentation == data else {
            throw InitialPairingProofError.invalidPublicKey(keyField)
        }
        guard isCanonicalDigest(fingerprint), digestHex(data) == fingerprint else {
            throw InitialPairingProofError.invalidFingerprint(fingerprintField)
        }
        return key
    }

    static func validatedSignature(_ base64: String) throws -> P256.Signing.ECDSASignature {
        guard let data = canonicalBase64Data(base64),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: data),
              signature.derRepresentation == data else {
            throw InitialPairingProofError.invalidSignature
        }
        return signature
    }

    private static func canonicalBase64Data(_ value: String) -> Data? {
        guard let data = Data(base64Encoded: value), data.base64EncodedString() == value else {
            return nil
        }
        return data
    }

    private static func isLowercaseHex(_ value: String, count: Int) -> Bool {
        value.utf8.count == count && value.utf8.allSatisfy {
            (UInt8(ascii: "0")...UInt8(ascii: "9")).contains($0) ||
                (UInt8(ascii: "a")...UInt8(ascii: "f")).contains($0)
        }
    }
}

public struct InitialPairingClientProof: Equatable, Sendable {
    public var scheme: String
    public var protocolVersion: Int
    public var requestID: String
    public var pairingNonce: String
    public var pairingCode: String
    public var runtimeDeviceID: String
    public var runtimePublicKey: String
    public var runtimeKeyFingerprint: String
    public var clientDeviceID: String
    public var clientDeviceName: String
    public var clientPublicKey: String
    public var clientKeyFingerprint: String
    public var transportBinding: String
    public var signatureBase64: String

    public init(
        scheme: String = InitialPairingProof.scheme,
        protocolVersion: Int = InitialPairingProof.protocolVersion,
        requestID: String,
        pairingNonce: String,
        pairingCode: String,
        runtimeDeviceID: String,
        runtimePublicKey: String,
        runtimeKeyFingerprint: String,
        clientDeviceID: String,
        clientDeviceName: String,
        clientPublicKey: String,
        clientKeyFingerprint: String,
        transportBinding: String,
        signatureBase64: String
    ) throws {
        self.scheme = scheme
        self.protocolVersion = protocolVersion
        self.requestID = requestID
        self.pairingNonce = pairingNonce
        self.pairingCode = pairingCode
        self.runtimeDeviceID = runtimeDeviceID
        self.runtimePublicKey = runtimePublicKey
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.clientDeviceID = clientDeviceID
        self.clientDeviceName = clientDeviceName
        self.clientPublicKey = clientPublicKey
        self.clientKeyFingerprint = clientKeyFingerprint
        self.transportBinding = transportBinding
        self.signatureBase64 = signatureBase64
        try validateShape()
    }

    public func signedMessageData() -> Data {
        InitialPairingProof.messageData(context: InitialPairingProof.clientContext, fields: fields)
    }

    public static func signingMessageData(
        scheme: String = InitialPairingProof.scheme,
        protocolVersion: Int = InitialPairingProof.protocolVersion,
        requestID: String,
        pairingNonce: String,
        pairingCode: String,
        runtimeDeviceID: String,
        runtimePublicKey: String,
        runtimeKeyFingerprint: String,
        clientDeviceID: String,
        clientDeviceName: String,
        clientPublicKey: String,
        clientKeyFingerprint: String,
        transportBinding: String
    ) throws -> Data {
        guard scheme == InitialPairingProof.scheme else {
            throw InitialPairingProofError.invalidField("scheme")
        }
        guard protocolVersion == InitialPairingProof.protocolVersion else {
            throw InitialPairingProofError.invalidField("protocol_version")
        }
        guard InitialPairingProof.isCanonicalTransportBinding(transportBinding) else {
            throw InitialPairingProofError.invalidField("transport_binding")
        }
        _ = try InitialPairingProof.validatedPublicKey(
            base64: runtimePublicKey,
            fingerprint: runtimeKeyFingerprint,
            keyField: "runtime_public_key",
            fingerprintField: "runtime_key_fingerprint"
        )
        _ = try InitialPairingProof.validatedPublicKey(
            base64: clientPublicKey,
            fingerprint: clientKeyFingerprint,
            keyField: "client_public_key",
            fingerprintField: "client_key_fingerprint"
        )
        return InitialPairingProof.messageData(
            context: InitialPairingProof.clientContext,
            fields: [
                ("scheme", scheme), ("protocol_version", String(protocolVersion)),
                ("request_id", requestID), ("pairing_nonce", pairingNonce),
                ("pairing_code", pairingCode), ("runtime_device_id", runtimeDeviceID),
                ("runtime_public_key", runtimePublicKey),
                ("runtime_key_fingerprint", runtimeKeyFingerprint),
                ("client_device_id", clientDeviceID), ("client_device_name", clientDeviceName),
                ("client_public_key", clientPublicKey),
                ("client_key_fingerprint", clientKeyFingerprint),
                ("transport_binding", transportBinding),
            ]
        )
    }

    public func requestDigest() -> String {
        InitialPairingProof.digestHex(signedMessageData())
    }

    public func verify() -> Bool {
        do {
            try validateShape()
            let key = try InitialPairingProof.validatedPublicKey(
                base64: clientPublicKey,
                fingerprint: clientKeyFingerprint,
                keyField: "client_public_key",
                fingerprintField: "client_key_fingerprint"
            )
            let signature = try InitialPairingProof.validatedSignature(signatureBase64)
            return key.isValidSignature(signature, for: SHA256.hash(data: signedMessageData()))
        } catch {
            return false
        }
    }

    private var fields: [(String, String)] {
        [
            ("scheme", scheme), ("protocol_version", String(protocolVersion)),
            ("request_id", requestID), ("pairing_nonce", pairingNonce),
            ("pairing_code", pairingCode), ("runtime_device_id", runtimeDeviceID),
            ("runtime_public_key", runtimePublicKey), ("runtime_key_fingerprint", runtimeKeyFingerprint),
            ("client_device_id", clientDeviceID), ("client_device_name", clientDeviceName),
            ("client_public_key", clientPublicKey), ("client_key_fingerprint", clientKeyFingerprint),
            ("transport_binding", transportBinding),
        ]
    }

    private func validateShape() throws {
        guard scheme == InitialPairingProof.scheme else { throw InitialPairingProofError.invalidField("scheme") }
        guard protocolVersion == InitialPairingProof.protocolVersion else { throw InitialPairingProofError.invalidField("protocol_version") }
        guard InitialPairingProof.isCanonicalTransportBinding(transportBinding) else { throw InitialPairingProofError.invalidField("transport_binding") }
        _ = try InitialPairingProof.validatedPublicKey(base64: runtimePublicKey, fingerprint: runtimeKeyFingerprint, keyField: "runtime_public_key", fingerprintField: "runtime_key_fingerprint")
        _ = try InitialPairingProof.validatedPublicKey(base64: clientPublicKey, fingerprint: clientKeyFingerprint, keyField: "client_public_key", fingerprintField: "client_key_fingerprint")
        _ = try InitialPairingProof.validatedSignature(signatureBase64)
    }
}

public struct InitialPairingRuntimeResult: Equatable, Sendable {
    public var scheme: String
    public var protocolVersion: Int
    public var requestID: String
    public var pairingRequestDigest: String
    public var accepted: Bool
    public var runtimeDeviceID: String
    public var runtimePublicKey: String
    public var runtimeKeyFingerprint: String
    public var trustedDeviceID: String
    public var message: String
    public var transportBinding: String

    public init(
        scheme: String = InitialPairingProof.scheme,
        protocolVersion: Int = InitialPairingProof.protocolVersion,
        requestID: String,
        pairingRequestDigest: String,
        accepted: Bool,
        runtimeDeviceID: String,
        runtimePublicKey: String,
        runtimeKeyFingerprint: String,
        trustedDeviceID: String,
        message: String,
        transportBinding: String
    ) throws {
        guard accepted else { throw InitialPairingProofError.rejectedResultCannotBeSigned }
        guard scheme == InitialPairingProof.scheme else { throw InitialPairingProofError.invalidField("scheme") }
        guard protocolVersion == InitialPairingProof.protocolVersion else { throw InitialPairingProofError.invalidField("protocol_version") }
        guard InitialPairingProof.isCanonicalDigest(pairingRequestDigest) else { throw InitialPairingProofError.invalidField("pairing_request_digest") }
        guard InitialPairingProof.isCanonicalTransportBinding(transportBinding) else { throw InitialPairingProofError.invalidField("transport_binding") }
        _ = try InitialPairingProof.validatedPublicKey(base64: runtimePublicKey, fingerprint: runtimeKeyFingerprint, keyField: "runtime_public_key", fingerprintField: "runtime_key_fingerprint")
        self.scheme = scheme
        self.protocolVersion = protocolVersion
        self.requestID = requestID
        self.pairingRequestDigest = pairingRequestDigest
        self.accepted = accepted
        self.runtimeDeviceID = runtimeDeviceID
        self.runtimePublicKey = runtimePublicKey
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.trustedDeviceID = trustedDeviceID
        self.message = message
        self.transportBinding = transportBinding
    }

    public func signedMessageData() -> Data {
        InitialPairingProof.messageData(context: InitialPairingProof.runtimeResultContext, fields: [
            ("scheme", scheme), ("protocol_version", String(protocolVersion)),
            ("request_id", requestID), ("pairing_request_digest", pairingRequestDigest),
            ("accepted", accepted ? "true" : "false"), ("runtime_device_id", runtimeDeviceID),
            ("runtime_public_key", runtimePublicKey), ("runtime_key_fingerprint", runtimeKeyFingerprint),
            ("trusted_device_id", trustedDeviceID), ("message", message),
            ("transport_binding", transportBinding),
        ])
    }

    public func resultDigest() -> String {
        InitialPairingProof.digestHex(signedMessageData())
    }

    func validate() throws {
        guard accepted else { throw InitialPairingProofError.rejectedResultCannotBeSigned }
        guard scheme == InitialPairingProof.scheme else { throw InitialPairingProofError.invalidField("scheme") }
        guard protocolVersion == InitialPairingProof.protocolVersion else { throw InitialPairingProofError.invalidField("protocol_version") }
        guard InitialPairingProof.isCanonicalDigest(pairingRequestDigest) else { throw InitialPairingProofError.invalidField("pairing_request_digest") }
        guard InitialPairingProof.isCanonicalTransportBinding(transportBinding) else { throw InitialPairingProofError.invalidField("transport_binding") }
        _ = try InitialPairingProof.validatedPublicKey(base64: runtimePublicKey, fingerprint: runtimeKeyFingerprint, keyField: "runtime_public_key", fingerprintField: "runtime_key_fingerprint")
    }
}

public struct InitialPairingRuntimeResultProof: Equatable, Sendable {
    public var result: InitialPairingRuntimeResult
    public var signatureBase64: String

    public init(result: InitialPairingRuntimeResult, signatureBase64: String) throws {
        _ = try InitialPairingProof.validatedSignature(signatureBase64)
        self.result = result
        self.signatureBase64 = signatureBase64
    }

    public func verify() -> Bool {
        do {
            try result.validate()
            let key = try InitialPairingProof.validatedPublicKey(
                base64: result.runtimePublicKey,
                fingerprint: result.runtimeKeyFingerprint,
                keyField: "runtime_public_key",
                fingerprintField: "runtime_key_fingerprint"
            )
            let signature = try InitialPairingProof.validatedSignature(signatureBase64)
            return key.isValidSignature(signature, for: SHA256.hash(data: result.signedMessageData()))
        } catch {
            return false
        }
    }
}
