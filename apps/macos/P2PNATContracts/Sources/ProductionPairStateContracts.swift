import CryptoKit
import Foundation

public enum ProductionPairStateContract {
    public static let authorityObjectType: UInt8 = 8
    public static let snapshotObjectType: UInt8 = 9
    public static let maxAuthorityBytes = 1_024
    public static let maxSnapshotBytes = 8_192
    public static let maxConsumedEntries = 64
    public static let maxTransitionHistoryEntries = 20
}

public enum ProductionPairStateError: Error, Equatable, Sendable {
    case invalidValue
    case malformedCanonical
    case limitExceeded
    case missingPreviousState
    case unexpectedPreviousState
    case previousStateMismatch
    case transitionConflict
    case transitionHistoryCapacityExhausted
    case nonAdvancingTransition
    case counterRollback
    case invalidEpochTransition
    case identityChangedWithinEpoch
    case revokedStateReactivation
    case invalidRevocationTransition
    case stateMismatch
    case revoked
    case protocolDowngrade
    case routeMismatch
    case replay
    case replayCapacityExceeded
}

public enum ProductionPairAuthorityStatus: String, Codable, Sendable {
    case active
    case revoked
}

public struct ProductionPairAuthorityState: Equatable, Sendable, Codable {
    public static let profile = ProductionSecureSessionContract.profile

    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let clientIdentityFingerprint: String
    public let runtimeIdentityFingerprint: String
    public let generation: UInt64
    public let serviceConfigVersion: UInt64
    public let keysetVersion: UInt64
    public let revocationCounter: UInt64
    public let protocolFloor: UInt32
    public let status: ProductionPairAuthorityStatus
    public let transitionId: String
    public let transitionRequestDigest: String
    public let acceptedReceiptDigest: String
    public let authorityRevision: UInt64

    public init(
        pairBindingDigest: String,
        pairEpoch: UInt64,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        generation: UInt64,
        serviceConfigVersion: UInt64,
        keysetVersion: UInt64,
        revocationCounter: UInt64,
        protocolFloor: UInt32,
        status: ProductionPairAuthorityStatus,
        transitionId: String,
        transitionRequestDigest: String,
        acceptedReceiptDigest: String,
        authorityRevision: UInt64
    ) throws {
        for digest in [
            pairBindingDigest,
            clientIdentityFingerprint,
            runtimeIdentityFingerprint,
            transitionId,
            transitionRequestDigest,
            acceptedReceiptDigest,
        ] {
            try pairValidateLowerHex(digest, byteCount: 32)
        }
        guard pairEpoch > 0,
              generation > 0,
              serviceConfigVersion > 0,
              keysetVersion > 0,
              protocolFloor > 0,
              authorityRevision > 0,
              clientIdentityFingerprint != runtimeIdentityFingerprint else {
            throw ProductionPairStateError.invalidValue
        }
        self.pairBindingDigest = pairBindingDigest
        self.pairEpoch = pairEpoch
        self.clientIdentityFingerprint = clientIdentityFingerprint
        self.runtimeIdentityFingerprint = runtimeIdentityFingerprint
        self.generation = generation
        self.serviceConfigVersion = serviceConfigVersion
        self.keysetVersion = keysetVersion
        self.revocationCounter = revocationCounter
        self.protocolFloor = protocolFloor
        self.status = status
        self.transitionId = transitionId
        self.transitionRequestDigest = transitionRequestDigest
        self.acceptedReceiptDigest = acceptedReceiptDigest
        self.authorityRevision = authorityRevision
        guard try canonicalBytes().count <= ProductionPairStateContract.maxAuthorityBytes else {
            throw ProductionPairStateError.limitExceeded
        }
    }

    public init(canonicalBytes data: Data) throws {
        guard data.count <= ProductionPairStateContract.maxAuthorityBytes else {
            throw ProductionPairStateError.limitExceeded
        }
        let fields = try PairTLV.decode(
            data,
            objectType: ProductionPairStateContract.authorityObjectType,
            fieldCount: 16
        )
        guard try pairText(fields[0]) == ProductionSecureSessionContract.suite,
              try pairText(fields[10]) == Self.profile,
              let status = ProductionPairAuthorityStatus(rawValue: try pairText(fields[11])) else {
            throw ProductionPairStateError.invalidValue
        }
        try self.init(
            pairBindingDigest: pairText(fields[1]),
            pairEpoch: pairUInt(fields[2]),
            clientIdentityFingerprint: pairText(fields[3]),
            runtimeIdentityFingerprint: pairText(fields[4]),
            generation: pairUInt(fields[5]),
            serviceConfigVersion: pairUInt(fields[6]),
            keysetVersion: pairUInt(fields[7]),
            revocationCounter: pairUInt(fields[8]),
            protocolFloor: pairUInt(fields[9]),
            status: status,
            transitionId: pairText(fields[12]),
            transitionRequestDigest: pairText(fields[13]),
            acceptedReceiptDigest: pairText(fields[14]),
            authorityRevision: pairUInt(fields[15])
        )
        guard try canonicalBytes() == data else {
            throw ProductionPairStateError.malformedCanonical
        }
    }

    public func canonicalBytes() throws -> Data {
        let data = PairTLV.encode(
            objectType: ProductionPairStateContract.authorityObjectType,
            fields: [
                pairASCII(ProductionSecureSessionContract.suite),
                pairASCII(pairBindingDigest),
                pairBE(pairEpoch),
                pairASCII(clientIdentityFingerprint),
                pairASCII(runtimeIdentityFingerprint),
                pairBE(generation),
                pairBE(serviceConfigVersion),
                pairBE(keysetVersion),
                pairBE(revocationCounter),
                pairBE(protocolFloor),
                pairASCII(Self.profile),
                pairASCII(status.rawValue),
                pairASCII(transitionId),
                pairASCII(transitionRequestDigest),
                pairASCII(acceptedReceiptDigest),
                pairBE(authorityRevision),
            ]
        )
        guard data.count <= ProductionPairStateContract.maxAuthorityBytes else {
            throw ProductionPairStateError.limitExceeded
        }
        return data
    }

    public func digest() throws -> Data { pairSHA256(try canonicalBytes()) }
    public func digestHex() throws -> String { pairLowerHex(try digest()) }

    public init(from decoder: Decoder) throws {
        let data = try decoder.singleValueContainer().decode(Data.self)
        try self.init(canonicalBytes: data)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(try canonicalBytes())
    }
}

public struct ProductionPairConsumedSession: Equatable, Sendable {
    public let sessionId: String
    public let transcriptDigest: String

    public init(sessionId: String, transcriptDigest: String) throws {
        try pairValidateLowerHex(sessionId, byteCount: 16)
        try pairValidateLowerHex(transcriptDigest, byteCount: 32)
        self.sessionId = sessionId
        self.transcriptDigest = transcriptDigest
    }
}

public struct ProductionPairTransitionHistoryEntry: Equatable, Sendable {
    public let transitionId: String
    public let transitionRequestDigest: String

    public init(transitionId: String, transitionRequestDigest: String) throws {
        try pairValidateLowerHex(transitionId, byteCount: 32)
        try pairValidateLowerHex(transitionRequestDigest, byteCount: 32)
        self.transitionId = transitionId
        self.transitionRequestDigest = transitionRequestDigest
    }
}

public struct ProductionPairStateSnapshot: Equatable, Sendable, Codable {
    public let authority: ProductionPairAuthorityState
    public let localRevision: UInt64
    public let consumedEntries: [ProductionPairConsumedSession]
    public let transitionHistory: [ProductionPairTransitionHistoryEntry]

    public init(
        authority: ProductionPairAuthorityState,
        localRevision: UInt64,
        consumedEntries: [ProductionPairConsumedSession] = [],
        transitionHistory: [ProductionPairTransitionHistoryEntry] = []
    ) throws {
        guard localRevision > 0,
              consumedEntries.count <= ProductionPairStateContract.maxConsumedEntries,
              Set(consumedEntries.map(\.sessionId)).count == consumedEntries.count,
              Set(consumedEntries.map(\.transcriptDigest)).count == consumedEntries.count,
              transitionHistory.count <= ProductionPairStateContract.maxTransitionHistoryEntries,
              Set(transitionHistory.map(\.transitionId)).count == transitionHistory.count,
              !transitionHistory.contains(where: { $0.transitionId == authority.transitionId }) else {
            throw ProductionPairStateError.invalidValue
        }
        self.authority = authority
        self.localRevision = localRevision
        self.consumedEntries = consumedEntries
        self.transitionHistory = transitionHistory
        guard try canonicalBytes().count <= ProductionPairStateContract.maxSnapshotBytes else {
            throw ProductionPairStateError.limitExceeded
        }
    }

    public init(canonicalBytes data: Data) throws {
        guard data.count <= ProductionPairStateContract.maxSnapshotBytes else {
            throw ProductionPairStateError.limitExceeded
        }
        let fields = try PairTLV.decode(
            data,
            objectType: ProductionPairStateContract.snapshotObjectType,
            allowedFieldCounts: [5, 7]
        )
        guard try pairText(fields[0]) == ProductionSecureSessionContract.suite else {
            throw ProductionPairStateError.invalidValue
        }
        let count: UInt32 = try pairUInt(fields[3])
        guard count <= UInt32(ProductionPairStateContract.maxConsumedEntries),
              fields[4].count == Int(count) * 96 else {
            throw ProductionPairStateError.malformedCanonical
        }
        var entries: [ProductionPairConsumedSession] = []
        for offset in stride(from: 0, to: fields[4].count, by: 96) {
            entries.append(try ProductionPairConsumedSession(
                sessionId: pairText(fields[4].subdata(in: offset..<(offset + 32))),
                transcriptDigest: pairText(fields[4].subdata(in: (offset + 32)..<(offset + 96)))
            ))
        }
        var transitionHistory: [ProductionPairTransitionHistoryEntry] = []
        if fields.count == 7 {
            let historyCount: UInt32 = try pairUInt(fields[5])
            guard historyCount > 0,
                  historyCount <= UInt32(ProductionPairStateContract.maxTransitionHistoryEntries),
                  fields[6].count == Int(historyCount) * 64 else {
                throw ProductionPairStateError.malformedCanonical
            }
            for offset in stride(from: 0, to: fields[6].count, by: 64) {
                transitionHistory.append(try ProductionPairTransitionHistoryEntry(
                    transitionId: pairLowerHex(
                        fields[6].subdata(in: offset..<(offset + 32))
                    ),
                    transitionRequestDigest: pairLowerHex(
                        fields[6].subdata(in: (offset + 32)..<(offset + 64))
                    )
                ))
            }
        }
        try self.init(
            authority: ProductionPairAuthorityState(canonicalBytes: fields[1]),
            localRevision: pairUInt(fields[2]),
            consumedEntries: entries,
            transitionHistory: transitionHistory
        )
        guard try canonicalBytes() == data else {
            throw ProductionPairStateError.malformedCanonical
        }
    }

    public func canonicalBytes() throws -> Data {
        let consumedBytes = consumedEntries.reduce(into: Data()) { result, entry in
            result.append(pairASCII(entry.sessionId))
            result.append(pairASCII(entry.transcriptDigest))
        }
        var fields = [
            pairASCII(ProductionSecureSessionContract.suite),
            try authority.canonicalBytes(),
            pairBE(localRevision),
            pairBE(UInt32(consumedEntries.count)),
            consumedBytes,
        ]
        if !transitionHistory.isEmpty {
            var historyBytes = Data()
            historyBytes.reserveCapacity(transitionHistory.count * 64)
            for entry in transitionHistory {
                historyBytes.append(try pairDecodeLowerHex(entry.transitionId))
                historyBytes.append(try pairDecodeLowerHex(entry.transitionRequestDigest))
            }
            fields.append(pairBE(UInt32(transitionHistory.count)))
            fields.append(historyBytes)
        }
        let data = PairTLV.encode(
            objectType: ProductionPairStateContract.snapshotObjectType,
            fields: fields
        )
        guard data.count <= ProductionPairStateContract.maxSnapshotBytes else {
            throw ProductionPairStateError.limitExceeded
        }
        return data
    }

    public func digest() throws -> Data { pairSHA256(try canonicalBytes()) }
    public func digestHex() throws -> String { pairLowerHex(try digest()) }

    public init(from decoder: Decoder) throws {
        let data = try decoder.singleValueContainer().decode(Data.self)
        try self.init(canonicalBytes: data)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(try canonicalBytes())
    }
}

public struct ProductionPairStateTransition: Equatable, Sendable {
    public let expectedPreviousAuthorityDigest: String?
    public let nextAuthority: ProductionPairAuthorityState

    public init(
        expectedPreviousAuthorityDigest: String?,
        nextAuthority: ProductionPairAuthorityState
    ) throws {
        if let expectedPreviousAuthorityDigest {
            try pairValidateLowerHex(expectedPreviousAuthorityDigest, byteCount: 32)
        }
        self.expectedPreviousAuthorityDigest = expectedPreviousAuthorityDigest
        self.nextAuthority = nextAuthority
    }
}

public enum ProductionPairStateTransitionDisposition: Equatable, Sendable {
    case applied
    case idempotent
}

public struct ProductionPairStateTransitionResult: Equatable, Sendable {
    public let disposition: ProductionPairStateTransitionDisposition
    public let snapshot: ProductionPairStateSnapshot
}

public enum ProductionPairStateMachine {
    public static func apply(
        _ transition: ProductionPairStateTransition,
        to current: ProductionPairStateSnapshot?
    ) throws -> ProductionPairStateTransitionResult {
        guard let current else {
            guard transition.expectedPreviousAuthorityDigest == nil else {
                throw ProductionPairStateError.unexpectedPreviousState
            }
            guard transition.nextAuthority.authorityRevision == 1,
                  transition.nextAuthority.status == .active else {
                throw ProductionPairStateError.invalidValue
            }
            return ProductionPairStateTransitionResult(
                disposition: .applied,
                snapshot: try ProductionPairStateSnapshot(
                    authority: transition.nextAuthority,
                    localRevision: 1
                )
            )
        }

        let previous = current.authority
        let next = transition.nextAuthority
        if next.transitionId == previous.transitionId {
            guard next.transitionRequestDigest == previous.transitionRequestDigest,
                  next == previous else {
                throw ProductionPairStateError.transitionConflict
            }
            return ProductionPairStateTransitionResult(disposition: .idempotent, snapshot: current)
        }
        guard !current.transitionHistory.contains(where: {
            $0.transitionId == next.transitionId
        }) else {
            throw ProductionPairStateError.transitionConflict
        }
        guard next != previous else {
            throw ProductionPairStateError.nonAdvancingTransition
        }
        guard let expected = transition.expectedPreviousAuthorityDigest else {
            throw ProductionPairStateError.missingPreviousState
        }
        guard expected == (try previous.digestHex()) else {
            throw ProductionPairStateError.previousStateMismatch
        }
        guard previous.authorityRevision < UInt64.max,
              next.authorityRevision == previous.authorityRevision + 1 else {
            throw ProductionPairStateError.counterRollback
        }
        guard next.pairEpoch >= previous.pairEpoch,
              next.generation >= previous.generation,
              next.serviceConfigVersion >= previous.serviceConfigVersion,
              next.keysetVersion >= previous.keysetVersion,
              next.revocationCounter >= previous.revocationCounter,
              next.protocolFloor >= previous.protocolFloor else {
            throw ProductionPairStateError.counterRollback
        }
        guard next.pairEpoch == previous.pairEpoch else {
            throw ProductionPairStateError.invalidEpochTransition
        }
        guard next.pairBindingDigest == previous.pairBindingDigest,
              next.clientIdentityFingerprint == previous.clientIdentityFingerprint,
              next.runtimeIdentityFingerprint == previous.runtimeIdentityFingerprint else {
            throw ProductionPairStateError.identityChangedWithinEpoch
        }
        if previous.status == .revoked, next.status == .active {
            throw ProductionPairStateError.revokedStateReactivation
        }
        if previous.status == .active, next.status == .revoked {
            guard previous.revocationCounter < UInt64.max,
                  next.revocationCounter == previous.revocationCounter + 1 else {
                throw ProductionPairStateError.invalidRevocationTransition
            }
        }
        guard pairHasAuthoritativeAdvance(from: previous, to: next) else {
            throw ProductionPairStateError.nonAdvancingTransition
        }
        guard current.localRevision < UInt64.max else {
            throw ProductionPairStateError.limitExceeded
        }
        guard current.transitionHistory.count
            < ProductionPairStateContract.maxTransitionHistoryEntries else {
            throw ProductionPairStateError.transitionHistoryCapacityExhausted
        }
        let preserveConsumed = next.pairEpoch == previous.pairEpoch
            && next.generation == previous.generation
        let previousTransition = try ProductionPairTransitionHistoryEntry(
            transitionId: previous.transitionId,
            transitionRequestDigest: previous.transitionRequestDigest
        )
        return ProductionPairStateTransitionResult(
            disposition: .applied,
            snapshot: try ProductionPairStateSnapshot(
                authority: next,
                localRevision: current.localRevision + 1,
                consumedEntries: preserveConsumed ? current.consumedEntries : [],
                transitionHistory: current.transitionHistory + [previousTransition]
            )
        )
    }
}

package struct ProductionPairAdmissionPreparation: Equatable, Sendable {
    package let snapshot: ProductionPairStateSnapshot
    package let bindingDigest: String
    package let pairAuthorityDigest: String
    package let sessionId: String
    package let transcriptDigest: String
    package let routeAuthorizationDigest: String
    package let previousPairSnapshotDigest: String
    package let pairSnapshotDigest: String

    fileprivate init(
        snapshot: ProductionPairStateSnapshot,
        bindingDigest: String,
        pairAuthorityDigest: String,
        sessionId: String,
        transcriptDigest: String,
        routeAuthorizationDigest: String,
        previousPairSnapshotDigest: String,
        pairSnapshotDigest: String
    ) {
        self.snapshot = snapshot
        self.bindingDigest = bindingDigest
        self.pairAuthorityDigest = pairAuthorityDigest
        self.sessionId = sessionId
        self.transcriptDigest = transcriptDigest
        self.routeAuthorizationDigest = routeAuthorizationDigest
        self.previousPairSnapshotDigest = previousPairSnapshotDigest
        self.pairSnapshotDigest = pairSnapshotDigest
    }
}

package enum ProductionPairStateAdmission {
    package static func prepare(
        transcript: ProductionSecureSessionTranscript,
        routeAuthorization: ProductionRouteAuthorization,
        to snapshot: ProductionPairStateSnapshot
    ) throws -> ProductionPairAdmissionPreparation {
        switch routeAuthorization.kind {
        case .p2pPublish, .p2pFetch, .p2pDirect:
            // P2P activation requires the dedicated durable object-28 path.
            throw ProductionPairStateError.routeMismatch
        case .localDirect, .turnRelay, .sealedRelay:
            break
        }
        let authority = snapshot.authority
        guard authority.status == .active else {
            throw ProductionPairStateError.revoked
        }
        guard transcript.pairBindingDigest == authority.pairBindingDigest,
              transcript.pairEpoch == authority.pairEpoch,
              transcript.clientIdentityFingerprint == authority.clientIdentityFingerprint,
              transcript.runtimeIdentityFingerprint == authority.runtimeIdentityFingerprint,
              transcript.generation == authority.generation,
              transcript.serviceConfigVersion == authority.serviceConfigVersion,
              transcript.keysetVersion == authority.keysetVersion,
              transcript.revocationCounter == authority.revocationCounter else {
            throw ProductionPairStateError.stateMismatch
        }
        guard ProductionSecureSessionTranscript.protocolVersion >= authority.protocolFloor,
              ProductionSecureSessionTranscript.minimumProtocolVersion >= authority.protocolFloor,
              ProductionSecureSessionTranscript.profile == ProductionPairAuthorityState.profile else {
            throw ProductionPairStateError.protocolDowngrade
        }
        guard transcript.matches(routeAuthorization) else {
            throw ProductionPairStateError.routeMismatch
        }
        let transcriptDigest = transcript.digestHex
        guard !snapshot.consumedEntries.contains(where: {
            $0.sessionId == transcript.sessionId || $0.transcriptDigest == transcriptDigest
        }) else {
            throw ProductionPairStateError.replay
        }
        guard snapshot.consumedEntries.count < ProductionPairStateContract.maxConsumedEntries else {
            throw ProductionPairStateError.replayCapacityExceeded
        }
        guard snapshot.localRevision < UInt64.max else {
            throw ProductionPairStateError.limitExceeded
        }
        let updated = try ProductionPairStateSnapshot(
            authority: authority,
            localRevision: snapshot.localRevision + 1,
            consumedEntries: snapshot.consumedEntries + [
                try ProductionPairConsumedSession(
                    sessionId: transcript.sessionId,
                    transcriptDigest: transcriptDigest
                ),
            ],
            transitionHistory: snapshot.transitionHistory
        )
        let routeAuthorizationDigest = try routeAuthorization.digestHex()
        let previousPairSnapshotDigest = try snapshot.digestHex()
        let pairSnapshotDigest = try updated.digestHex()
        let bindingBytes = transcript.digest
            + (try routeAuthorization.digest())
            + (try updated.digest())
        return ProductionPairAdmissionPreparation(
            snapshot: updated,
            bindingDigest: pairLowerHex(pairSHA256(bindingBytes)),
            pairAuthorityDigest: try authority.digestHex(),
            sessionId: transcript.sessionId,
            transcriptDigest: transcriptDigest,
            routeAuthorizationDigest: routeAuthorizationDigest,
            previousPairSnapshotDigest: previousPairSnapshotDigest,
            pairSnapshotDigest: pairSnapshotDigest
        )
    }
}

package typealias ProductionPairStateAdmissionPreparation = ProductionPairAdmissionPreparation

private func pairHasAuthoritativeAdvance(
    from previous: ProductionPairAuthorityState,
    to next: ProductionPairAuthorityState
) -> Bool {
    previous.pairBindingDigest != next.pairBindingDigest
        || previous.pairEpoch != next.pairEpoch
        || previous.clientIdentityFingerprint != next.clientIdentityFingerprint
        || previous.runtimeIdentityFingerprint != next.runtimeIdentityFingerprint
        || previous.generation != next.generation
        || previous.serviceConfigVersion != next.serviceConfigVersion
        || previous.keysetVersion != next.keysetVersion
        || previous.revocationCounter != next.revocationCounter
        || previous.protocolFloor != next.protocolFloor
        || previous.status != next.status
}

private enum PairTLV {
    static func encode(objectType: UInt8, fields: [Data]) -> Data {
        var result = ProductionSecureSessionContract.magic
        result.append(objectType)
        result.append(ProductionSecureSessionContract.version)
        for (index, field) in fields.enumerated() {
            result.append(UInt8(index + 1))
            result.append(pairBE(UInt32(field.count)))
            result.append(field)
        }
        return result
    }

    static func decode(_ data: Data, objectType: UInt8, fieldCount: Int) throws -> [Data] {
        try decode(data, objectType: objectType, allowedFieldCounts: [fieldCount])
    }

    static func decode(
        _ data: Data,
        objectType: UInt8,
        allowedFieldCounts: Set<Int>
    ) throws -> [Data] {
        guard let maximumFieldCount = allowedFieldCounts.max(),
              allowedFieldCounts.allSatisfy({ $0 > 0 }) else {
            throw ProductionPairStateError.malformedCanonical
        }
        var cursor = PairByteCursor(data)
        guard try cursor.read(ProductionSecureSessionContract.magic.count)
                == ProductionSecureSessionContract.magic,
              try cursor.byte() == objectType,
              try cursor.byte() == ProductionSecureSessionContract.version else {
            throw ProductionPairStateError.malformedCanonical
        }
        var fields: [Data] = []
        for expectedTag in 1...maximumFieldCount {
            if cursor.remaining == 0 { break }
            guard try cursor.byte() == UInt8(expectedTag) else {
                throw ProductionPairStateError.malformedCanonical
            }
            let length: UInt32 = try cursor.readBE()
            guard UInt64(length) <= UInt64(cursor.remaining) else {
                throw ProductionPairStateError.malformedCanonical
            }
            fields.append(try cursor.read(Int(length)))
        }
        guard cursor.remaining == 0, allowedFieldCounts.contains(fields.count) else {
            throw ProductionPairStateError.malformedCanonical
        }
        return fields
    }
}

private struct PairByteCursor {
    let data: Data
    var offset = 0

    init(_ data: Data) { self.data = data }

    var remaining: Int { data.count - offset }

    mutating func byte() throws -> UInt8 {
        guard remaining >= 1 else { throw ProductionPairStateError.malformedCanonical }
        defer { offset += 1 }
        return data[offset]
    }

    mutating func read(_ count: Int) throws -> Data {
        guard count >= 0, count <= remaining else {
            throw ProductionPairStateError.malformedCanonical
        }
        defer { offset += count }
        return data.subdata(in: offset..<(offset + count))
    }

    mutating func readBE<T: FixedWidthInteger>() throws -> T {
        let bytes = try read(MemoryLayout<T>.size)
        return bytes.reduce(T.zero) { ($0 << 8) | T($1) }
    }
}

private func pairASCII(_ value: String) -> Data { Data(value.utf8) }

private func pairText(_ data: Data) throws -> String {
    guard data.allSatisfy({ (0x20...0x7e).contains($0) }),
          let value = String(data: data, encoding: .utf8),
          Data(value.utf8) == data else {
        throw ProductionPairStateError.malformedCanonical
    }
    return value
}

private func pairValidateLowerHex(_ value: String, byteCount: Int) throws {
    guard value.utf8.count == byteCount * 2,
          value.utf8.allSatisfy({ byte in
              (UInt8(ascii: "0")...UInt8(ascii: "9")).contains(byte)
                  || (UInt8(ascii: "a")...UInt8(ascii: "f")).contains(byte)
          }) else {
        throw ProductionPairStateError.invalidValue
    }
}

private func pairDecodeLowerHex(_ value: String) throws -> Data {
    guard value.utf8.count.isMultiple(of: 2) else {
        throw ProductionPairStateError.invalidValue
    }
    var result = Data()
    result.reserveCapacity(value.utf8.count / 2)
    var index = value.startIndex
    while index < value.endIndex {
        let next = value.index(index, offsetBy: 2)
        guard let byte = UInt8(value[index..<next], radix: 16) else {
            throw ProductionPairStateError.invalidValue
        }
        result.append(byte)
        index = next
    }
    return result
}

private func pairBE<T: FixedWidthInteger>(_ value: T) -> Data {
    var result = Data()
    for shift in stride(from: (MemoryLayout<T>.size - 1) * 8, through: 0, by: -8) {
        result.append(UInt8(truncatingIfNeeded: value >> T(shift)))
    }
    return result
}

private func pairUInt<T: FixedWidthInteger>(_ data: Data, as: T.Type = T.self) throws -> T {
    guard data.count == MemoryLayout<T>.size else {
        throw ProductionPairStateError.malformedCanonical
    }
    return data.reduce(T.zero) { ($0 << 8) | T($1) }
}

private func pairSHA256(_ data: Data) -> Data { Data(SHA256.hash(data: data)) }

private func pairLowerHex(_ data: Data) -> String {
    data.map { String(format: "%02x", $0) }.joined()
}
