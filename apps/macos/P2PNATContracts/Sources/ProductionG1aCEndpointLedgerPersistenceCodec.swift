import Foundation

public enum ProductionC1EndpointLedgerPersistenceContract {
    public static let version: UInt32 = 2
    public static let maximumEntries = ProductionPairStateContract.maxConsumedEntries
    public static let maximumBytes = 32 * 1024
}

public extension ProductionC1EndpointGrantLedgerState {
    func persistenceCanonicalBytes() throws -> Data {
        guard entries.count <= ProductionC1EndpointLedgerPersistenceContract.maximumEntries,
              retentionLimit <= UInt32(ProductionC1EndpointLedgerPersistenceContract.maximumEntries),
              remainingGrants <= UInt64(retentionLimit),
              UInt64(entries.count) + remainingGrants <= UInt64(retentionLimit)
        else {
            throw ProductionC1CandidateCapabilityError.retentionExhausted
        }
        // The magic identifies the cross-platform ledger family. Schema changes
        // are carried by the explicit version field so Swift and Kotlin retain
        // byte-for-byte persistence parity.
        var data = Data("ALC1EGL1".utf8)
        data.append(endpointLedgerBE(ProductionC1EndpointLedgerPersistenceContract.version))
        data.append(endpointLedgerBE(revision))
        data.append(try endpointLedgerDigestBytes(pairAuthorityDigest))
        data.append(endpointLedgerBE(pairLocalRevision))
        data.append(endpointLedgerBE(remainingGrants))
        data.append(endpointLedgerBE(retentionLimit))
        data.append(endpointLedgerBE(UInt32(entries.count)))
        for entry in entries {
            for digest in [
                entry.admissionId, entry.bindingDigest, entry.routeGrantDigest,
                entry.transcriptDigest, entry.routeAuthorizationDigest,
                entry.grantAuthorizationDigest,
                entry.connectorInputCommitmentDigest, entry.pairSnapshotDigest,
            ] {
                data.append(try endpointLedgerDigestBytes(digest))
            }
            guard entry.sessionId.utf8.count == 32 else {
                throw ProductionC1CandidateCapabilityError.invalidValue
            }
            data.append(Data(entry.sessionId.utf8))
            data.append(endpointLedgerBE(entry.committedRevision))
        }
        guard data.count <= ProductionC1EndpointLedgerPersistenceContract.maximumBytes else {
            throw ProductionC1CandidateCapabilityError.retentionExhausted
        }
        return data
    }

    init(persistenceCanonicalBytes data: Data) throws {
        guard data.count <= ProductionC1EndpointLedgerPersistenceContract.maximumBytes else {
            throw ProductionC1CandidateCapabilityError.retentionExhausted
        }
        var reader = EndpointLedgerPersistenceReader(data)
        guard try reader.read(8) == Data("ALC1EGL1".utf8),
              try reader.uint32() == ProductionC1EndpointLedgerPersistenceContract.version else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        let revision = try reader.uint64()
        let pairAuthorityDigest = try reader.digestHex()
        let pairLocalRevision = try reader.uint64()
        let remainingGrants = try reader.uint64()
        let retentionLimit = try reader.uint32()
        let entryCount = try reader.uint32()
        guard retentionLimit <= UInt32(ProductionC1EndpointLedgerPersistenceContract.maximumEntries),
              entryCount <= retentionLimit,
              entryCount <= UInt32(ProductionC1EndpointLedgerPersistenceContract.maximumEntries),
              remainingGrants <= UInt64(retentionLimit),
              UInt64(entryCount) + remainingGrants <= UInt64(retentionLimit)
        else {
            throw ProductionC1CandidateCapabilityError.retentionExhausted
        }
        var entries: [ProductionC1EndpointGrantEntry] = []
        entries.reserveCapacity(Int(entryCount))
        for _ in 0..<entryCount {
            let admissionId = try reader.digestHex()
            let bindingDigest = try reader.digestHex()
            let routeGrantDigest = try reader.digestHex()
            let transcriptDigest = try reader.digestHex()
            let routeAuthorizationDigest = try reader.digestHex()
            let grantAuthorizationDigest = try reader.digestHex()
            let connectorInputCommitmentDigest = try reader.digestHex()
            let pairSnapshotDigest = try reader.digestHex()
            let sessionId = try reader.lowerHexText(byteCount: 32)
            let committedRevision = try reader.uint64()
            let entry = ProductionC1EndpointGrantEntry(
                admissionId: admissionId,
                bindingDigest: bindingDigest,
                routeGrantDigest: routeGrantDigest,
                sessionId: sessionId,
                transcriptDigest: transcriptDigest,
                routeAuthorizationDigest: routeAuthorizationDigest,
                grantAuthorizationDigest: grantAuthorizationDigest,
                connectorInputCommitmentDigest: connectorInputCommitmentDigest,
                pairSnapshotDigest: pairSnapshotDigest,
                committedRevision: committedRevision
            )
            entries.append(entry)
        }
        guard reader.isAtEnd else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        try self.init(
            revision: revision,
            pairAuthorityDigest: pairAuthorityDigest,
            pairLocalRevision: pairLocalRevision,
            remainingGrants: remainingGrants,
            retentionLimit: retentionLimit,
            entries: entries
        )
        guard try persistenceCanonicalBytes() == data else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
    }
}

public extension ProductionC1EndpointGrantAdmission {
    /// Produces non-authorizing state-transition data for the trusted persistence boundary.
    /// Only the persistence owner may convert this preparation into a connector-start token.
    static func prepareForTrustedPersistence(
        state: ProductionC1EndpointGrantLedgerState,
        expectedRevision: UInt64,
        expectedSnapshotDigest: String,
        admissionId: String,
        bindingDigest: String,
        verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        currentPairSnapshot: ProductionPairStateSnapshot,
        nowMs: UInt64
    ) throws -> ProductionC1EndpointGrantAdmissionPreparation {
        try prepare(
            state: state,
            expectedRevision: expectedRevision,
            expectedSnapshotDigest: expectedSnapshotDigest,
            admissionId: admissionId,
            bindingDigest: bindingDigest,
            verifiedBinding: verifiedBinding,
            currentPairSnapshot: currentPairSnapshot,
            nowMs: nowMs
        )
    }
}

private struct EndpointLedgerPersistenceReader {
    private let data: Data
    private var offset: Data.Index

    init(_ data: Data) {
        self.data = data
        offset = data.startIndex
    }

    var isAtEnd: Bool { offset == data.endIndex }

    mutating func read(_ count: Int) throws -> Data {
        guard count >= 0,
              offset <= data.endIndex,
              count <= data.distance(from: offset, to: data.endIndex) else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        let end = data.index(offset, offsetBy: count)
        defer { offset = end }
        return data.subdata(in: offset..<end)
    }

    mutating func uint32() throws -> UInt32 {
        let bytes = [UInt8](try read(4))
        return bytes.reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
    }

    mutating func uint64() throws -> UInt64 {
        let bytes = [UInt8](try read(8))
        return bytes.reduce(UInt64(0)) { ($0 << 8) | UInt64($1) }
    }

    mutating func digestHex() throws -> String {
        try read(32).map { String(format: "%02x", $0) }.joined()
    }

    mutating func lowerHexText(byteCount: Int) throws -> String {
        let bytes = try read(byteCount)
        guard let value = String(data: bytes, encoding: .utf8),
              value.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
            throw ProductionC1CandidateCapabilityError.malformedCanonical
        }
        return value
    }
}

private func endpointLedgerDigestBytes(_ value: String) throws -> Data {
    guard value.utf8.count == 64 else {
        throw ProductionC1CandidateCapabilityError.invalidValue
    }
    var result = Data(capacity: 32)
    var index = value.startIndex
    for _ in 0..<32 {
        let next = value.index(index, offsetBy: 2)
        guard let byte = UInt8(value[index..<next], radix: 16) else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        result.append(byte)
        index = next
    }
    return result
}

private func endpointLedgerBE<T: FixedWidthInteger>(_ value: T) -> Data {
    var bigEndian = value.bigEndian
    return withUnsafeBytes(of: &bigEndian) { Data($0) }
}
