import CryptoKit
import Foundation

public enum ProductionSecureSessionContract {
    public static let magic = Data("ALS1".utf8)
    public static let version: UInt8 = 1
    public static let maxRouteBytes = 512
    public static let maxTranscriptBytes = 1_024
    public static let suite = "aetherlink-secure-session-v1"
    public static let profile = "p256_hkdf_sha256_aes256gcm_v1"
}

public enum ProductionSecureSessionLimits {
    public static let routeAuthorizationBytes = ProductionSecureSessionContract.maxRouteBytes
    public static let transcriptBytes = ProductionSecureSessionContract.maxTranscriptBytes
    public static let maxRouteBytes = routeAuthorizationBytes
    public static let maxTranscriptBytes = transcriptBytes
}

public enum ProductionRouteAuthorizationKind: UInt8, CaseIterable, Sendable {
    case localDirect = 1
    case p2pPublish = 2
    case p2pFetch = 3
    case p2pDirect = 4
    case turnRelay = 5
    case sealedRelay = 6

    public var wireName: String {
        switch self {
        case .localDirect: "local_direct"
        case .p2pPublish: "p2p_publish"
        case .p2pFetch: "p2p_fetch"
        case .p2pDirect: "p2p_direct"
        case .turnRelay: "turn_relay"
        case .sealedRelay: "sealed_relay"
        }
    }

    public init?(wireName: String) {
        guard let value = Self.allCases.first(where: { $0.wireName == wireName }) else {
            return nil
        }
        self = value
    }
}

public enum ProductionRouteAuthorization: Equatable, Sendable {
    public static let suite = ProductionSecureSessionContract.suite

    case localDirect(
        pairBindingDigest: String,
        pairEpoch: UInt64,
        nominatedPathReceiptDigest: String
    )
    case p2pPublish(
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        candidateBatchDigest: String,
        publishCapabilityDigest: String
    )
    case p2pFetch(
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        candidateBatchDigest: String,
        fetchCapabilityDigest: String
    )
    case p2pDirect(
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        candidatePairDigest: String,
        pathValidationReceiptDigest: String,
        publishCapabilityDigest: String,
        fetchCapabilityDigest: String
    )
    case turnRelay(
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        leaseDigest: String,
        allocationDigest: String,
        pathValidationReceiptDigest: String
    )
    case sealedRelay(
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        leaseDigest: String,
        allocationDigest: String,
        pathValidationReceiptDigest: String
    )

    public var kind: ProductionRouteAuthorizationKind {
        switch self {
        case .localDirect: .localDirect
        case .p2pPublish: .p2pPublish
        case .p2pFetch: .p2pFetch
        case .p2pDirect: .p2pDirect
        case .turnRelay: .turnRelay
        case .sealedRelay: .sealedRelay
        }
    }

    public var pairBindingDigest: String {
        switch self {
        case let .localDirect(value, _, _),
             let .p2pPublish(value, _, _, _, _),
             let .p2pFetch(value, _, _, _, _),
             let .p2pDirect(value, _, _, _, _, _, _),
             let .turnRelay(value, _, _, _, _, _),
             let .sealedRelay(value, _, _, _, _, _):
            value
        }
    }

    public var pairEpoch: UInt64 {
        switch self {
        case let .localDirect(_, value, _),
             let .p2pPublish(_, value, _, _, _),
             let .p2pFetch(_, value, _, _, _),
             let .p2pDirect(_, value, _, _, _, _, _),
             let .turnRelay(_, value, _, _, _, _),
             let .sealedRelay(_, value, _, _, _, _):
            value
        }
    }

    public var generation: UInt64? {
        switch self {
        case .localDirect:
            nil
        case let .p2pPublish(_, _, value, _, _),
             let .p2pFetch(_, _, value, _, _),
             let .p2pDirect(_, _, value, _, _, _, _),
             let .turnRelay(_, _, value, _, _, _),
             let .sealedRelay(_, _, value, _, _, _):
            value
        }
    }

    public func encode() throws -> Data {
        let fields: [ProductionTLVField]
        switch self {
        case let .localDirect(pairDigest, epoch, pathDigest):
            try validateCommon(pairDigest: pairDigest, pairEpoch: epoch)
            try productionValidateLowerHex(pathDigest, byteCount: 32)
            fields = commonFields(pairDigest: pairDigest, pairEpoch: epoch) + [
                .init(tag: 4, value: productionASCII(pathDigest)),
            ]
        case let .p2pPublish(pairDigest, epoch, generation, batchDigest, capabilityDigest):
            try validateCommon(pairDigest: pairDigest, pairEpoch: epoch)
            try productionValidatePositive(generation)
            try productionValidateLowerHex(batchDigest, byteCount: 32)
            try productionValidateLowerHex(capabilityDigest, byteCount: 32)
            fields = commonFields(pairDigest: pairDigest, pairEpoch: epoch) + [
                .init(tag: 4, value: productionBE(generation)),
                .init(tag: 5, value: productionASCII(batchDigest)),
                .init(tag: 6, value: productionASCII(capabilityDigest)),
            ]
        case let .p2pFetch(pairDigest, epoch, generation, batchDigest, capabilityDigest):
            try validateCommon(pairDigest: pairDigest, pairEpoch: epoch)
            try productionValidatePositive(generation)
            try productionValidateLowerHex(batchDigest, byteCount: 32)
            try productionValidateLowerHex(capabilityDigest, byteCount: 32)
            fields = commonFields(pairDigest: pairDigest, pairEpoch: epoch) + [
                .init(tag: 4, value: productionBE(generation)),
                .init(tag: 5, value: productionASCII(batchDigest)),
                .init(tag: 6, value: productionASCII(capabilityDigest)),
            ]
        case let .p2pDirect(
            pairDigest,
            epoch,
            generation,
            candidatePairDigest,
            pathDigest,
            publishDigest,
            fetchDigest
        ):
            try validateCommon(pairDigest: pairDigest, pairEpoch: epoch)
            try productionValidatePositive(generation)
            for digest in [candidatePairDigest, pathDigest, publishDigest, fetchDigest] {
                try productionValidateLowerHex(digest, byteCount: 32)
            }
            fields = commonFields(pairDigest: pairDigest, pairEpoch: epoch) + [
                .init(tag: 4, value: productionBE(generation)),
                .init(tag: 5, value: productionASCII(candidatePairDigest)),
                .init(tag: 6, value: productionASCII(pathDigest)),
                .init(tag: 7, value: productionASCII(publishDigest)),
                .init(tag: 8, value: productionASCII(fetchDigest)),
            ]
        case let .turnRelay(pairDigest, epoch, generation, leaseDigest, allocationDigest, pathDigest),
             let .sealedRelay(pairDigest, epoch, generation, leaseDigest, allocationDigest, pathDigest):
            try validateCommon(pairDigest: pairDigest, pairEpoch: epoch)
            try productionValidatePositive(generation)
            for digest in [leaseDigest, allocationDigest, pathDigest] {
                try productionValidateLowerHex(digest, byteCount: 32)
            }
            fields = commonFields(pairDigest: pairDigest, pairEpoch: epoch) + [
                .init(tag: 4, value: productionBE(generation)),
                .init(tag: 5, value: productionASCII(leaseDigest)),
                .init(tag: 6, value: productionASCII(allocationDigest)),
                .init(tag: 7, value: productionASCII(pathDigest)),
            ]
        }

        let encoded = ProductionTLVEncoder(objectType: kind.rawValue).encode(fields)
        guard encoded.count <= ProductionSecureSessionLimits.routeAuthorizationBytes else {
            throw P2PNATContractError.limitExceeded
        }
        return encoded
    }

    public func canonicalBytes() throws -> Data {
        try encode()
    }

    public func digest() throws -> Data {
        Data(SHA256.hash(data: try encode()))
    }

    public func digestHex() throws -> String {
        productionLowerHex(try digest())
    }

    public static func decode(_ data: Data) throws -> Self {
        try Self(canonicalBytes: data)
    }

    public init(canonicalBytes data: Data) throws {
        guard data.count <= ProductionSecureSessionLimits.routeAuthorizationBytes else {
            throw P2PNATContractError.limitExceeded
        }
        let objectType = try productionObjectType(data)
        guard let kind = ProductionRouteAuthorizationKind(rawValue: objectType) else {
            throw P2PNATContractError.invalidObjectType
        }
        let tagCount: UInt8
        switch kind {
        case .localDirect: tagCount = 4
        case .p2pPublish, .p2pFetch: tagCount = 6
        case .p2pDirect: tagCount = 8
        case .turnRelay, .sealedRelay: tagCount = 7
        }
        let fields = try ProductionTLVDecoder(
            data,
            objectType: objectType,
            expectedTags: Array(1...tagCount)
        ).fields
        guard try productionText(fields[0]) == Self.suite else {
            throw P2PNATContractError.invalidValue
        }
        let pairDigest = try productionText(fields[1])
        let pairEpoch: UInt64 = try productionUInt(fields[2])

        switch kind {
        case .localDirect:
            self = .localDirect(
                pairBindingDigest: pairDigest,
                pairEpoch: pairEpoch,
                nominatedPathReceiptDigest: try productionText(fields[3])
            )
        case .p2pPublish:
            self = .p2pPublish(
                pairBindingDigest: pairDigest,
                pairEpoch: pairEpoch,
                generation: try productionUInt(fields[3]),
                candidateBatchDigest: try productionText(fields[4]),
                publishCapabilityDigest: try productionText(fields[5])
            )
        case .p2pFetch:
            self = .p2pFetch(
                pairBindingDigest: pairDigest,
                pairEpoch: pairEpoch,
                generation: try productionUInt(fields[3]),
                candidateBatchDigest: try productionText(fields[4]),
                fetchCapabilityDigest: try productionText(fields[5])
            )
        case .p2pDirect:
            self = .p2pDirect(
                pairBindingDigest: pairDigest,
                pairEpoch: pairEpoch,
                generation: try productionUInt(fields[3]),
                candidatePairDigest: try productionText(fields[4]),
                pathValidationReceiptDigest: try productionText(fields[5]),
                publishCapabilityDigest: try productionText(fields[6]),
                fetchCapabilityDigest: try productionText(fields[7])
            )
        case .turnRelay:
            self = .turnRelay(
                pairBindingDigest: pairDigest,
                pairEpoch: pairEpoch,
                generation: try productionUInt(fields[3]),
                leaseDigest: try productionText(fields[4]),
                allocationDigest: try productionText(fields[5]),
                pathValidationReceiptDigest: try productionText(fields[6])
            )
        case .sealedRelay:
            self = .sealedRelay(
                pairBindingDigest: pairDigest,
                pairEpoch: pairEpoch,
                generation: try productionUInt(fields[3]),
                leaseDigest: try productionText(fields[4]),
                allocationDigest: try productionText(fields[5]),
                pathValidationReceiptDigest: try productionText(fields[6])
            )
        }
        _ = try encode()
    }

    public func matches(
        kind expectedKind: ProductionRouteAuthorizationKind,
        digest expectedDigest: String,
        pairBindingDigest expectedPairBindingDigest: String,
        pairEpoch expectedPairEpoch: UInt64,
        generation expectedGeneration: UInt64?
    ) -> Bool {
        guard kind == expectedKind,
              pairBindingDigest == expectedPairBindingDigest,
              pairEpoch == expectedPairEpoch,
              let expectedDigestBytes = productionDecodeLowerHex(expectedDigest),
              let actualDigest = try? digest(),
              productionConstantTimeEqual(actualDigest, expectedDigestBytes) else {
            return false
        }
        guard let generation else { return true }
        return expectedGeneration == generation
    }

    public func matches(_ transcript: ProductionSecureSessionTranscript) -> Bool {
        transcript.matches(self)
    }

    private func commonFields(pairDigest: String, pairEpoch: UInt64) -> [ProductionTLVField] {
        [
            .init(tag: 1, value: productionASCII(Self.suite)),
            .init(tag: 2, value: productionASCII(pairDigest)),
            .init(tag: 3, value: productionBE(pairEpoch)),
        ]
    }

    private func validateCommon(pairDigest: String, pairEpoch: UInt64) throws {
        try productionValidateLowerHex(pairDigest, byteCount: 32)
        try productionValidatePositive(pairEpoch)
    }
}

public struct ProductionSecureSessionTranscript: Equatable, Sendable {
    public static let objectType: UInt8 = 7
    public static let suite = ProductionRouteAuthorization.suite
    public static let profile = ProductionSecureSessionContract.profile
    public static let protocolVersion: UInt32 = 1
    public static let minimumProtocolVersion: UInt32 = 1

    public let sessionId: String
    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let clientIdentityFingerprint: String
    public let runtimeIdentityFingerprint: String
    public let clientEphemeralPublicKey: Data
    public let runtimeEphemeralPublicKey: Data
    public let clientNonce: String
    public let runtimeNonce: String
    public let generation: UInt64
    public let serviceConfigVersion: UInt64
    public let keysetVersion: UInt64
    public let revocationCounter: UInt64
    public let routeKind: ProductionRouteAuthorizationKind
    public let routeAuthDigest: String

    public var clientRole: String { "client" }
    public var runtimeRole: String { "runtime" }
    public var clientPublicKeyX963: Data { clientEphemeralPublicKey }
    public var runtimePublicKeyX963: Data { runtimeEphemeralPublicKey }
    public var routeAuthorizationKind: ProductionRouteAuthorizationKind { routeKind }
    public var routeAuthorizationDigest: String { routeAuthDigest }

    public init(
        sessionId: String,
        pairBindingDigest: String,
        pairEpoch: UInt64,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        clientEphemeralPublicKey: Data,
        runtimeEphemeralPublicKey: Data,
        clientNonce: String,
        runtimeNonce: String,
        generation: UInt64,
        serviceConfigVersion: UInt64,
        keysetVersion: UInt64,
        revocationCounter: UInt64,
        routeKind: ProductionRouteAuthorizationKind,
        routeAuthDigest: String
    ) throws {
        try productionValidateLowerHex(sessionId, byteCount: 16)
        for digest in [
            pairBindingDigest,
            clientIdentityFingerprint,
            runtimeIdentityFingerprint,
            routeAuthDigest,
        ] {
            try productionValidateLowerHex(digest, byteCount: 32)
        }
        try productionValidateLowerHex(clientNonce, byteCount: 16)
        try productionValidateLowerHex(runtimeNonce, byteCount: 16)
        for value in [pairEpoch, generation, serviceConfigVersion, keysetVersion] {
            try productionValidatePositive(value)
        }
        guard productionIsValidP256Key(clientEphemeralPublicKey),
              productionIsValidP256Key(runtimeEphemeralPublicKey),
              clientIdentityFingerprint != runtimeIdentityFingerprint,
              clientEphemeralPublicKey != runtimeEphemeralPublicKey,
              clientNonce != runtimeNonce else {
            throw P2PNATContractError.invalidValue
        }

        self.sessionId = sessionId
        self.pairBindingDigest = pairBindingDigest
        self.pairEpoch = pairEpoch
        self.clientIdentityFingerprint = clientIdentityFingerprint
        self.runtimeIdentityFingerprint = runtimeIdentityFingerprint
        self.clientEphemeralPublicKey = clientEphemeralPublicKey
        self.runtimeEphemeralPublicKey = runtimeEphemeralPublicKey
        self.clientNonce = clientNonce
        self.runtimeNonce = runtimeNonce
        self.generation = generation
        self.serviceConfigVersion = serviceConfigVersion
        self.keysetVersion = keysetVersion
        self.revocationCounter = revocationCounter
        self.routeKind = routeKind
        self.routeAuthDigest = routeAuthDigest

        guard encode().count <= ProductionSecureSessionLimits.transcriptBytes else {
            throw P2PNATContractError.limitExceeded
        }
    }

    public func encode() -> Data {
        ProductionTLVEncoder(objectType: Self.objectType).encode([
            .init(tag: 1, value: productionASCII(Self.suite)),
            .init(tag: 2, value: productionASCII(sessionId)),
            .init(tag: 3, value: productionASCII(pairBindingDigest)),
            .init(tag: 4, value: productionBE(pairEpoch)),
            .init(tag: 5, value: productionASCII(clientIdentityFingerprint)),
            .init(tag: 6, value: productionASCII(runtimeIdentityFingerprint)),
            .init(tag: 7, value: productionASCII(clientRole)),
            .init(tag: 8, value: productionASCII(runtimeRole)),
            .init(tag: 9, value: clientEphemeralPublicKey),
            .init(tag: 10, value: runtimeEphemeralPublicKey),
            .init(tag: 11, value: productionASCII(clientNonce)),
            .init(tag: 12, value: productionASCII(runtimeNonce)),
            .init(tag: 13, value: productionBE(generation)),
            .init(tag: 14, value: productionBE(serviceConfigVersion)),
            .init(tag: 15, value: productionBE(keysetVersion)),
            .init(tag: 16, value: productionBE(revocationCounter)),
            .init(tag: 17, value: productionBE(Self.protocolVersion)),
            .init(tag: 18, value: productionBE(Self.minimumProtocolVersion)),
            .init(tag: 19, value: productionASCII(Self.profile)),
            .init(tag: 20, value: productionASCII(routeKind.wireName)),
            .init(tag: 21, value: productionASCII(routeAuthDigest)),
        ])
    }

    public func canonicalBytes() -> Data {
        encode()
    }

    public var digest: Data {
        Data(SHA256.hash(data: encode()))
    }

    public var digestHex: String {
        productionLowerHex(digest)
    }

    public static func decode(_ data: Data) throws -> Self {
        try Self(canonicalBytes: data)
    }

    public init(canonicalBytes data: Data) throws {
        guard data.count <= ProductionSecureSessionLimits.transcriptBytes else {
            throw P2PNATContractError.limitExceeded
        }
        let fields = try ProductionTLVDecoder(
            data,
            objectType: Self.objectType,
            expectedTags: Array(1...21)
        ).fields
        guard try productionText(fields[0]) == Self.suite,
              try productionText(fields[6]) == "client",
              try productionText(fields[7]) == "runtime",
              try productionUInt(fields[16], as: UInt32.self) == Self.protocolVersion,
              try productionUInt(fields[17], as: UInt32.self) == Self.minimumProtocolVersion,
              try productionText(fields[18]) == Self.profile,
              let routeKind = ProductionRouteAuthorizationKind(
                  wireName: try productionText(fields[19])
              ) else {
            throw P2PNATContractError.invalidValue
        }
        try self.init(
            sessionId: productionText(fields[1]),
            pairBindingDigest: productionText(fields[2]),
            pairEpoch: productionUInt(fields[3]),
            clientIdentityFingerprint: productionText(fields[4]),
            runtimeIdentityFingerprint: productionText(fields[5]),
            clientEphemeralPublicKey: fields[8],
            runtimeEphemeralPublicKey: fields[9],
            clientNonce: productionText(fields[10]),
            runtimeNonce: productionText(fields[11]),
            generation: productionUInt(fields[12]),
            serviceConfigVersion: productionUInt(fields[13]),
            keysetVersion: productionUInt(fields[14]),
            revocationCounter: productionUInt(fields[15]),
            routeKind: routeKind,
            routeAuthDigest: productionText(fields[20])
        )
    }

    public func matches(_ authorization: ProductionRouteAuthorization) -> Bool {
        authorization.matches(
            kind: routeKind,
            digest: routeAuthDigest,
            pairBindingDigest: pairBindingDigest,
            pairEpoch: pairEpoch,
            generation: generation
        )
    }

    public func matches(routeAuthorization authorization: ProductionRouteAuthorization) -> Bool {
        matches(authorization)
    }
}

public enum ProductionSecureSessionCodec {
    public static func encode(_ value: ProductionRouteAuthorization) throws -> Data {
        try value.encode()
    }

    public static func decodeRouteAuthorization(_ data: Data) throws -> ProductionRouteAuthorization {
        try ProductionRouteAuthorization.decode(data)
    }

    public static func encode(_ value: ProductionSecureSessionTranscript) -> Data {
        value.encode()
    }

    public static func decodeTranscript(_ data: Data) throws -> ProductionSecureSessionTranscript {
        try ProductionSecureSessionTranscript.decode(data)
    }

    public static func digest(_ value: ProductionRouteAuthorization) throws -> Data {
        try value.digest()
    }

    public static func digest(_ value: ProductionSecureSessionTranscript) -> Data {
        value.digest
    }

    public static func matches(
        transcript: ProductionSecureSessionTranscript,
        routeAuthorization: ProductionRouteAuthorization
    ) -> Bool {
        transcript.matches(routeAuthorization)
    }
}

private let productionSecureSessionMagic = ProductionSecureSessionContract.magic
private let productionSecureSessionVersion = ProductionSecureSessionContract.version

private struct ProductionTLVField {
    let tag: UInt8
    let value: Data
}

private struct ProductionTLVEncoder {
    let objectType: UInt8

    func encode(_ fields: [ProductionTLVField]) -> Data {
        var data = productionSecureSessionMagic
        data.append(objectType)
        data.append(productionSecureSessionVersion)
        for field in fields {
            data.append(field.tag)
            data.productionAppendBE(UInt32(field.value.count))
            data.append(field.value)
        }
        return data
    }
}

private struct ProductionTLVDecoder {
    let fields: [Data]

    init(_ data: Data, objectType: UInt8, expectedTags: [UInt8]) throws {
        var cursor = ProductionByteCursor(data)
        guard try cursor.read(productionSecureSessionMagic.count) == productionSecureSessionMagic else {
            throw P2PNATContractError.invalidHeader
        }
        guard try cursor.byte() == objectType else {
            throw P2PNATContractError.invalidObjectType
        }
        guard try cursor.byte() == productionSecureSessionVersion else {
            throw P2PNATContractError.invalidVersion
        }

        var values: [Data] = []
        var seen = Set<UInt8>()
        for expectedTag in expectedTags {
            guard !cursor.isAtEnd else { throw P2PNATContractError.invalidField }
            let actualTag = try cursor.byte()
            if seen.contains(actualTag) {
                throw P2PNATContractError.duplicateField
            }
            guard expectedTags.contains(actualTag) else {
                throw P2PNATContractError.unknownField
            }
            guard actualTag == expectedTag else {
                throw P2PNATContractError.invalidFieldOrder
            }
            seen.insert(actualTag)
            let length: UInt32 = try cursor.readBE()
            values.append(try cursor.read(Int(length)))
        }

        guard cursor.isAtEnd else {
            if cursor.remaining >= 1 {
                let extraTag = try cursor.peekByte()
                if seen.contains(extraTag) {
                    throw P2PNATContractError.duplicateField
                }
                if !expectedTags.contains(extraTag), cursor.remaining >= 5 {
                    throw P2PNATContractError.unknownField
                }
            }
            throw P2PNATContractError.trailingBytes
        }
        fields = values
    }
}

private struct ProductionByteCursor {
    let data: Data
    var offset = 0

    init(_ data: Data) {
        self.data = data
    }

    var isAtEnd: Bool { offset == data.count }
    var remaining: Int { data.count - offset }

    mutating func byte() throws -> UInt8 {
        guard offset < data.count else { throw P2PNATContractError.invalidLength }
        defer { offset += 1 }
        return data[offset]
    }

    func peekByte() throws -> UInt8 {
        guard offset < data.count else { throw P2PNATContractError.invalidLength }
        return data[offset]
    }

    mutating func read(_ count: Int) throws -> Data {
        guard count >= 0, count <= remaining else {
            throw P2PNATContractError.invalidLength
        }
        defer { offset += count }
        return data.subdata(in: offset..<(offset + count))
    }

    mutating func readBE<T: FixedWidthInteger>() throws -> T {
        let bytes = try read(MemoryLayout<T>.size)
        return bytes.reduce(T.zero) { ($0 << 8) | T($1) }
    }
}

private func productionObjectType(_ data: Data) throws -> UInt8 {
    var cursor = ProductionByteCursor(data)
    guard try cursor.read(productionSecureSessionMagic.count) == productionSecureSessionMagic else {
        throw P2PNATContractError.invalidHeader
    }
    let objectType = try cursor.byte()
    guard try cursor.byte() == productionSecureSessionVersion else {
        throw P2PNATContractError.invalidVersion
    }
    return objectType
}

private func productionASCII(_ value: String) -> Data {
    Data(value.utf8)
}

private func productionText(_ data: Data) throws -> String {
    guard data.allSatisfy({ (0x20...0x7e).contains($0) }),
          let value = String(data: data, encoding: .utf8),
          Data(value.utf8) == data else {
        throw P2PNATContractError.invalidText
    }
    return value
}

private func productionValidateLowerHex(_ value: String, byteCount: Int) throws {
    guard value.utf8.count == byteCount * 2,
          value.utf8.allSatisfy({ byte in
              (UInt8(ascii: "0")...UInt8(ascii: "9")).contains(byte)
                  || (UInt8(ascii: "a")...UInt8(ascii: "f")).contains(byte)
          }) else {
        throw P2PNATContractError.invalidValue
    }
}

private func productionValidatePositive<T: FixedWidthInteger>(_ value: T) throws {
    guard value > 0 else { throw P2PNATContractError.invalidValue }
}

private func productionIsValidP256Key(_ data: Data) -> Bool {
    data.count == 65 && (try? P256.KeyAgreement.PublicKey(x963Representation: data)) != nil
}

private func productionBE<T: FixedWidthInteger>(_ value: T) -> Data {
    var data = Data()
    data.productionAppendBE(value)
    return data
}

private func productionUInt<T: FixedWidthInteger>(_ data: Data, as type: T.Type = T.self) throws -> T {
    guard data.count == MemoryLayout<T>.size else {
        throw P2PNATContractError.invalidInteger
    }
    var cursor = ProductionByteCursor(data)
    return try cursor.readBE()
}

private func productionLowerHex(_ data: Data) -> String {
    data.map { String(format: "%02x", $0) }.joined()
}

private func productionDecodeLowerHex(_ value: String) -> Data? {
    guard value.utf8.count == 64,
          value.utf8.allSatisfy({ byte in
              (UInt8(ascii: "0")...UInt8(ascii: "9")).contains(byte)
                  || (UInt8(ascii: "a")...UInt8(ascii: "f")).contains(byte)
          }) else {
        return nil
    }
    var bytes = Data(capacity: 32)
    let utf8 = Array(value.utf8)
    for index in stride(from: 0, to: utf8.count, by: 2) {
        func nibble(_ byte: UInt8) -> UInt8 {
            byte <= UInt8(ascii: "9")
                ? byte - UInt8(ascii: "0")
                : byte - UInt8(ascii: "a") + 10
        }
        bytes.append((nibble(utf8[index]) << 4) | nibble(utf8[index + 1]))
    }
    return bytes
}

private func productionConstantTimeEqual(_ lhs: Data, _ rhs: Data) -> Bool {
    guard lhs.count == rhs.count else { return false }
    var difference: UInt8 = 0
    for index in lhs.indices {
        difference |= lhs[index] ^ rhs[index]
    }
    return difference == 0
}

private extension Data {
    mutating func productionAppendBE<T: FixedWidthInteger>(_ value: T) {
        for shift in stride(from: (MemoryLayout<T>.size - 1) * 8, through: 0, by: -8) {
            append(UInt8(truncatingIfNeeded: value >> T(shift)))
        }
    }
}
