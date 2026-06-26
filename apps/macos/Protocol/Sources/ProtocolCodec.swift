import Foundation
import CryptoKit

public enum ProtocolCodecError: Error, Equatable {
    case invalidFrameLength(Int)
    case truncatedFrame
}

public enum RelayFrameCipherError: Error, Equatable {
    case invalidCiphertextLength(Int)
}

public struct ProtocolCodec: Sendable {
    public static let maxFrameBytes = 1024 * 1024

    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    public init() {
        encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
    }

    public func encodeFrame(_ envelope: ProtocolEnvelope) throws -> Data {
        try encodeLengthPrefixedBody(encodeEnvelopeBody(envelope))
    }

    public func encodeEnvelopeBody(_ envelope: ProtocolEnvelope) throws -> Data {
        try encoder.encode(envelope)
    }

    public func encodeLengthPrefixedBody(_ body: Data) throws -> Data {
        try validateFrameBodyLength(body.count)
        var length = UInt32(body.count).bigEndian
        var frame = Data(bytes: &length, count: MemoryLayout<UInt32>.size)
        frame.append(body)
        return frame
    }

    public func decodeEnvelope(_ data: Data) throws -> ProtocolEnvelope {
        try decoder.decode(ProtocolEnvelope.self, from: data)
    }

    public func decodeFrame(_ frame: Data) throws -> ProtocolEnvelope {
        try decodeEnvelope(decodeLengthPrefixedBody(frame))
    }

    public func decodeLengthPrefixedBody(_ frame: Data) throws -> Data {
        guard frame.count >= 4 else { throw ProtocolCodecError.truncatedFrame }
        let length = frame.prefix(4).withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
        let bodyLength = Int(length)
        try validateFrameBodyLength(bodyLength)
        guard frame.count >= 4 + bodyLength else { throw ProtocolCodecError.truncatedFrame }
        return Data(frame.dropFirst(4).prefix(bodyLength))
    }

    public func validateFrameBodyLength(_ bodyLength: Int) throws {
        guard bodyLength > 0 && bodyLength <= Self.maxFrameBytes else {
            throw ProtocolCodecError.invalidFrameLength(bodyLength)
        }
    }
}

public struct RelayFrameCipher: Sendable {
    public static let aad = Data("AETHERLINK_RELAY_FRAME_V1".utf8)
    private static let keyPrefix = Data("AetherLink relay frame v1\n".utf8)
    private static let routeNonceContext = Data("\nroute_nonce\n".utf8)
    private static let authenticationTagBytes = 16

    private let key: SymmetricKey
    private var runtimeSendCounter: UInt64 = 0
    private var clientSendCounter: UInt64 = 0
    private var runtimeReceiveCounter: UInt64 = 0
    private var clientReceiveCounter: UInt64 = 0

    public init(relaySecret: String, routeNonce: String? = nil) {
        var material = Self.keyPrefix
        material.append(Data(relaySecret.utf8))
        if let routeNonce, !routeNonce.isEmpty {
            material.append(Self.routeNonceContext)
            material.append(Data(routeNonce.utf8))
        }
        self.key = SymmetricKey(data: Data(SHA256.hash(data: material)))
    }

    public mutating func encryptRuntimeBody(_ body: Data) throws -> Data {
        let encrypted = try encrypt(body, direction: "RUNT", counter: runtimeSendCounter)
        runtimeSendCounter += 1
        return encrypted
    }

    public mutating func decryptClientBody(_ body: Data) throws -> Data {
        defer { clientReceiveCounter += 1 }
        return try decrypt(body, direction: "CLNT", counter: clientReceiveCounter)
    }

    public mutating func encryptClientBody(_ body: Data) throws -> Data {
        let encrypted = try encrypt(body, direction: "CLNT", counter: clientSendCounter)
        clientSendCounter += 1
        return encrypted
    }

    public mutating func decryptRuntimeBody(_ body: Data) throws -> Data {
        defer { runtimeReceiveCounter += 1 }
        return try decrypt(body, direction: "RUNT", counter: runtimeReceiveCounter)
    }

    private func encrypt(_ body: Data, direction: String, counter: UInt64) throws -> Data {
        let sealed = try AES.GCM.seal(
            body,
            using: key,
            nonce: nonce(direction: direction, counter: counter),
            authenticating: Self.aad
        )
        var framedBody = sealed.ciphertext
        framedBody.append(sealed.tag)
        return framedBody
    }

    private func decrypt(_ body: Data, direction: String, counter: UInt64) throws -> Data {
        guard body.count >= Self.authenticationTagBytes else {
            throw RelayFrameCipherError.invalidCiphertextLength(body.count)
        }
        let ciphertext = body.prefix(body.count - Self.authenticationTagBytes)
        let tag = body.suffix(Self.authenticationTagBytes)
        let sealed = try AES.GCM.SealedBox(
            nonce: nonce(direction: direction, counter: counter),
            ciphertext: ciphertext,
            tag: tag
        )
        return try AES.GCM.open(sealed, using: key, authenticating: Self.aad)
    }

    private func nonce(direction: String, counter: UInt64) throws -> AES.GCM.Nonce {
        var nonce = Data(direction.utf8)
        var bigEndianCounter = counter.bigEndian
        nonce.append(Data(bytes: &bigEndianCounter, count: MemoryLayout<UInt64>.size))
        return try AES.GCM.Nonce(data: nonce)
    }
}
