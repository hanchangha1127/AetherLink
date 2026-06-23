import Foundation

public enum ProtocolCodecError: Error, Equatable {
    case invalidFrameLength(Int)
    case truncatedFrame
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
        let body = try encoder.encode(envelope)
        var length = UInt32(body.count).bigEndian
        var frame = Data(bytes: &length, count: MemoryLayout<UInt32>.size)
        frame.append(body)
        return frame
    }

    public func decodeEnvelope(_ data: Data) throws -> ProtocolEnvelope {
        try decoder.decode(ProtocolEnvelope.self, from: data)
    }

    public func decodeFrame(_ frame: Data) throws -> ProtocolEnvelope {
        guard frame.count >= 4 else { throw ProtocolCodecError.truncatedFrame }
        let length = frame.prefix(4).withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
        let bodyLength = Int(length)
        guard bodyLength > 0 && bodyLength <= Self.maxFrameBytes else {
            throw ProtocolCodecError.invalidFrameLength(bodyLength)
        }
        guard frame.count >= 4 + bodyLength else { throw ProtocolCodecError.truncatedFrame }
        return try decodeEnvelope(frame.dropFirst(4).prefix(bodyLength))
    }
}

