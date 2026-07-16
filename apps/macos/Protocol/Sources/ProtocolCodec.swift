import Foundation
import CryptoKit

public enum ProtocolCodecError: Error, Equatable {
    case invalidFrameLength(Int)
    case truncatedFrame
    case invalidJSON
    case duplicateJSONObjectKey(String)
}

public enum RelayFrameCipherError: Error, Equatable {
    case invalidCiphertextLength(Int)
    case counterExhausted
}

public enum StrictJSONDocumentValidator {
    public static func validate(_ data: Data) throws {
        try JSONDuplicateKeyValidator.validate(data)
    }
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
        try StrictJSONDocumentValidator.validate(data)
        var envelope = try decoder.decode(ProtocolEnvelope.self, from: data)
        if [
            MessageType.memorySemanticDuplicateSuggestionsList,
            MessageType.memorySemanticDuplicateClustersList,
        ].contains(envelope.type),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let payload = object["payload"] as? [String: Any],
           let number = payload["minimum_similarity_basis_points"] as? NSNumber,
           CFGetTypeID(number) != CFBooleanGetTypeID(),
           !["d", "f"].contains(String(cString: number.objCType)),
           let integer = Int64(number.stringValue) {
            envelope.payload["minimum_similarity_basis_points"] = .integer(integer)
        }
        return envelope
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

private struct JSONDuplicateKeyValidator {
    private static let maximumNestingDepth = 512

    private let bytes: [UInt8]
    private var index = 0

    static func validate(_ data: Data) throws {
        var parser = JSONDuplicateKeyValidator(bytes: Array(data))
        try parser.parseDocument()
    }

    private mutating func parseDocument() throws {
        skipWhitespace()
        try parseValue(depth: 0)
        skipWhitespace()
        guard index == bytes.count else { throw ProtocolCodecError.invalidJSON }
    }

    private mutating func parseValue(depth: Int) throws {
        guard depth <= Self.maximumNestingDepth, index < bytes.count else {
            throw ProtocolCodecError.invalidJSON
        }
        switch bytes[index] {
        case UInt8(ascii: "{"):
            try parseObject(depth: depth)
        case UInt8(ascii: "["):
            try parseArray(depth: depth)
        case UInt8(ascii: "\""):
            _ = try parseString()
        case UInt8(ascii: "t"):
            try consumeLiteral("true")
        case UInt8(ascii: "f"):
            try consumeLiteral("false")
        case UInt8(ascii: "n"):
            try consumeLiteral("null")
        case UInt8(ascii: "-"), UInt8(ascii: "0")...UInt8(ascii: "9"):
            try parseNumber()
        default:
            throw ProtocolCodecError.invalidJSON
        }
    }

    private mutating func parseObject(depth: Int) throws {
        index += 1
        skipWhitespace()
        if consume(UInt8(ascii: "}")) { return }

        var keys = Set<String>()
        while true {
            guard index < bytes.count, bytes[index] == UInt8(ascii: "\"") else {
                throw ProtocolCodecError.invalidJSON
            }
            let key = try parseString()
            guard keys.insert(key).inserted else {
                throw ProtocolCodecError.duplicateJSONObjectKey(key)
            }
            skipWhitespace()
            guard consume(UInt8(ascii: ":")) else { throw ProtocolCodecError.invalidJSON }
            skipWhitespace()
            try parseValue(depth: depth + 1)
            skipWhitespace()
            if consume(UInt8(ascii: "}")) { return }
            guard consume(UInt8(ascii: ",")) else { throw ProtocolCodecError.invalidJSON }
            skipWhitespace()
        }
    }

    private mutating func parseArray(depth: Int) throws {
        index += 1
        skipWhitespace()
        if consume(UInt8(ascii: "]")) { return }

        while true {
            try parseValue(depth: depth + 1)
            skipWhitespace()
            if consume(UInt8(ascii: "]")) { return }
            guard consume(UInt8(ascii: ",")) else { throw ProtocolCodecError.invalidJSON }
            skipWhitespace()
        }
    }

    private mutating func parseString() throws -> String {
        let start = index
        index += 1
        while index < bytes.count {
            let byte = bytes[index]
            if byte == UInt8(ascii: "\"") {
                index += 1
                let encoded = Data(bytes[start..<index])
                guard let value = try? JSONDecoder().decode(String.self, from: encoded) else {
                    throw ProtocolCodecError.invalidJSON
                }
                return value
            }
            if byte < 0x20 { throw ProtocolCodecError.invalidJSON }
            if byte == UInt8(ascii: "\\") {
                index += 1
                guard index < bytes.count else { throw ProtocolCodecError.invalidJSON }
                if bytes[index] == UInt8(ascii: "u") {
                    guard index + 4 < bytes.count else { throw ProtocolCodecError.invalidJSON }
                    index += 4
                }
            }
            index += 1
        }
        throw ProtocolCodecError.invalidJSON
    }

    private mutating func parseNumber() throws {
        _ = consume(UInt8(ascii: "-"))
        guard index < bytes.count else { throw ProtocolCodecError.invalidJSON }

        if consume(UInt8(ascii: "0")) {
            guard index == bytes.count || !isDigit(bytes[index]) else {
                throw ProtocolCodecError.invalidJSON
            }
        } else {
            guard consumeDigit(in: UInt8(ascii: "1")...UInt8(ascii: "9")) else {
                throw ProtocolCodecError.invalidJSON
            }
            while index < bytes.count, isDigit(bytes[index]) { index += 1 }
        }

        if consume(UInt8(ascii: ".")) {
            guard consumeDigit(in: UInt8(ascii: "0")...UInt8(ascii: "9")) else {
                throw ProtocolCodecError.invalidJSON
            }
            while index < bytes.count, isDigit(bytes[index]) { index += 1 }
        }

        if index < bytes.count, bytes[index] == UInt8(ascii: "e") || bytes[index] == UInt8(ascii: "E") {
            index += 1
            if index < bytes.count, bytes[index] == UInt8(ascii: "+") || bytes[index] == UInt8(ascii: "-") {
                index += 1
            }
            guard consumeDigit(in: UInt8(ascii: "0")...UInt8(ascii: "9")) else {
                throw ProtocolCodecError.invalidJSON
            }
            while index < bytes.count, isDigit(bytes[index]) { index += 1 }
        }
    }

    private mutating func consumeLiteral(_ literal: StaticString) throws {
        let literalBytes = Array(String(describing: literal).utf8)
        guard index + literalBytes.count <= bytes.count,
              bytes[index..<(index + literalBytes.count)].elementsEqual(literalBytes) else {
            throw ProtocolCodecError.invalidJSON
        }
        index += literalBytes.count
    }

    private mutating func consume(_ byte: UInt8) -> Bool {
        guard index < bytes.count, bytes[index] == byte else { return false }
        index += 1
        return true
    }

    private mutating func consumeDigit(in range: ClosedRange<UInt8>) -> Bool {
        guard index < bytes.count, range.contains(bytes[index]) else { return false }
        index += 1
        return true
    }

    private func isDigit(_ byte: UInt8) -> Bool {
        (UInt8(ascii: "0")...UInt8(ascii: "9")).contains(byte)
    }

    private mutating func skipWhitespace() {
        while index < bytes.count, [0x20, 0x09, 0x0a, 0x0d].contains(bytes[index]) {
            index += 1
        }
    }
}

public struct RelayFrameCipher: Sendable {
    private static let framesPerEpoch: Int64 = 65_536
    private static let aadPrefix = Data("AETHERLINK_RELAY_FRAME_V2".utf8)
    private static let epochPrefix = Data("AetherLink relay frame epoch v2\n".utf8)
    private static let authenticationTagBytes = 16

    private let bindingDigest: Data
    private let clientTrafficSecret: Data
    private let runtimeTrafficSecret: Data
    private var runtimeSendFrameIndex: Int64
    private var clientSendFrameIndex: Int64
    private var runtimeReceiveFrameIndex: Int64
    private var clientReceiveFrameIndex: Int64

    public init(sessionKeys: RelaySessionKeys) {
        self.init(sessionKeys: sessionKeys, frameIndex: 0)
    }

    init(sessionKeys: RelaySessionKeys, frameIndex: Int64) {
        precondition(frameIndex >= 0, "Relay frame index must not be negative")
        bindingDigest = sessionKeys.bindingDigest
        clientTrafficSecret = sessionKeys.clientTrafficSecret
        runtimeTrafficSecret = sessionKeys.runtimeTrafficSecret
        runtimeSendFrameIndex = frameIndex
        clientSendFrameIndex = frameIndex
        runtimeReceiveFrameIndex = frameIndex
        clientReceiveFrameIndex = frameIndex
    }

    public mutating func encryptRuntimeBody(_ body: Data) throws -> Data {
        let encrypted = try encrypt(
            body,
            direction: Data("RUNT".utf8),
            trafficSecret: runtimeTrafficSecret,
            frameIndex: runtimeSendFrameIndex
        )
        runtimeSendFrameIndex += 1
        return encrypted
    }

    public mutating func decryptClientBody(_ body: Data) throws -> Data {
        let decrypted = try decrypt(
            body,
            direction: Data("CLNT".utf8),
            trafficSecret: clientTrafficSecret,
            frameIndex: clientReceiveFrameIndex
        )
        clientReceiveFrameIndex += 1
        return decrypted
    }

    public mutating func encryptClientBody(_ body: Data) throws -> Data {
        let encrypted = try encrypt(
            body,
            direction: Data("CLNT".utf8),
            trafficSecret: clientTrafficSecret,
            frameIndex: clientSendFrameIndex
        )
        clientSendFrameIndex += 1
        return encrypted
    }

    public mutating func decryptRuntimeBody(_ body: Data) throws -> Data {
        let decrypted = try decrypt(
            body,
            direction: Data("RUNT".utf8),
            trafficSecret: runtimeTrafficSecret,
            frameIndex: runtimeReceiveFrameIndex
        )
        runtimeReceiveFrameIndex += 1
        return decrypted
    }

    private func encrypt(
        _ body: Data,
        direction: Data,
        trafficSecret: Data,
        frameIndex: Int64
    ) throws -> Data {
        let parameters = try frameParameters(
            direction: direction,
            trafficSecret: trafficSecret,
            frameIndex: frameIndex
        )
        let sealed = try AES.GCM.seal(
            body,
            using: parameters.key,
            nonce: parameters.nonce,
            authenticating: parameters.aad
        )
        var framedBody = sealed.ciphertext
        framedBody.append(sealed.tag)
        return framedBody
    }

    private func decrypt(
        _ body: Data,
        direction: Data,
        trafficSecret: Data,
        frameIndex: Int64
    ) throws -> Data {
        guard body.count >= Self.authenticationTagBytes else {
            throw RelayFrameCipherError.invalidCiphertextLength(body.count)
        }
        let parameters = try frameParameters(
            direction: direction,
            trafficSecret: trafficSecret,
            frameIndex: frameIndex
        )
        let ciphertext = body.prefix(body.count - Self.authenticationTagBytes)
        let tag = body.suffix(Self.authenticationTagBytes)
        let sealed = try AES.GCM.SealedBox(
            nonce: parameters.nonce,
            ciphertext: ciphertext,
            tag: tag
        )
        return try AES.GCM.open(sealed, using: parameters.key, authenticating: parameters.aad)
    }

    private func frameParameters(
        direction: Data,
        trafficSecret: Data,
        frameIndex: Int64
    ) throws -> (key: SymmetricKey, nonce: AES.GCM.Nonce, aad: Data) {
        guard frameIndex < Int64.max else { throw RelayFrameCipherError.counterExhausted }
        let epoch = UInt64(frameIndex / Self.framesPerEpoch)
        let sequence = UInt64(frameIndex & 0xffff)

        var epochMaterial = Self.epochPrefix
        epochMaterial.append(direction)
        epochMaterial.append(bigEndianData(epoch))
        let epochAuthenticationCode = HMAC<SHA256>.authenticationCode(
            for: epochMaterial,
            using: SymmetricKey(data: trafficSecret)
        )
        let key = SymmetricKey(data: Data(epochAuthenticationCode))

        var nonceData = direction
        nonceData.append(bigEndianData(sequence))

        var aad = Self.aadPrefix
        aad.append(bindingDigest)
        aad.append(direction)
        aad.append(bigEndianData(epoch))
        aad.append(bigEndianData(sequence))
        return (key, try AES.GCM.Nonce(data: nonceData), aad)
    }

    private func bigEndianData(_ value: UInt64) -> Data {
        var bigEndianValue = value.bigEndian
        return Data(bytes: &bigEndianValue, count: MemoryLayout<UInt64>.size)
    }
}
