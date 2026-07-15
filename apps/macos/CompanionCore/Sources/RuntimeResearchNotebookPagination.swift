import CryptoKit
import Foundation

enum RuntimeResearchNotebookPaginationError: Error {
    case invalidCursor
    case snapshotLimitExceeded
}

struct RuntimeResearchNotebookSnapshotContext: Equatable, Sendable {
    var includeArchived: Bool
}

struct RuntimeResearchNotebookSnapshotItem: Equatable, Sendable {
    var notebook: RuntimeResearchNotebook
    var archivedAt: Date?
    var updatedAt: Date

    static func precedes(
        _ lhs: RuntimeResearchNotebookSnapshotItem,
        _ rhs: RuntimeResearchNotebookSnapshotItem
    ) -> Bool {
        if lhs.updatedAt != rhs.updatedAt {
            return lhs.updatedAt > rhs.updatedAt
        }
        return lhs.notebook.notebookID.utf8.lexicographicallyPrecedes(
            rhs.notebook.notebookID.utf8
        )
    }
}

struct RuntimeResearchNotebookSnapshotPage: Sendable {
    var notebooks: [RuntimeResearchNotebookSnapshotItem]
    var snapshotCount: Int
    var nextCursor: String?
}

final class RuntimeResearchNotebookPagination: @unchecked Sendable {
    static let maximumSnapshotCount = 10_000
    static let maximumCursorUTF8Bytes = 512
    static let snapshotTTL: TimeInterval = 120
    static let maximumGlobalSnapshots = 8

    private struct Snapshot {
        var id: String
        var connectionID: UUID
        var ownerDeviceID: String
        var context: RuntimeResearchNotebookSnapshotContext
        var notebooks: [RuntimeResearchNotebookSnapshotItem]
        var pageLimit: Int
        var expiresAtUnixSeconds: Int64
        var expiresAtMonotonicSeconds: TimeInterval
        var sequence: UInt64
    }

    private struct ParsedCursor {
        var snapshotID: String
        var includeArchived: Bool
        var pageLimit: Int
        var snapshotCount: Int
        var offset: Int
        var expiresAtUnixSeconds: Int64
        var authenticationCode: Data
    }

    private let authenticationKey: SymmetricKey
    private let monotonicNow: @Sendable () -> TimeInterval
    private let lock = NSLock()
    private var snapshotsByID: [String: Snapshot] = [:]
    private var snapshotIDByConnection: [UUID: String] = [:]
    private var nextSequence: UInt64 = 0

    init(
        authenticationKey: SymmetricKey = SymmetricKey(size: .bits256),
        monotonicNow: @escaping @Sendable () -> TimeInterval = {
            ProcessInfo.processInfo.systemUptime
        }
    ) {
        self.authenticationKey = authenticationKey
        self.monotonicNow = monotonicNow
    }

    func createSnapshot(
        connectionID: UUID,
        ownerDeviceID: String,
        context: RuntimeResearchNotebookSnapshotContext,
        notebooks: [RuntimeResearchNotebookSnapshotItem],
        pageLimit: Int,
        now: Date = Date()
    ) throws -> RuntimeResearchNotebookSnapshotPage {
        guard notebooks.count <= Self.maximumSnapshotCount else {
            throw RuntimeResearchNotebookPaginationError.snapshotLimitExceeded
        }
        guard let ownerDeviceID = Self.normalizedOwnerDeviceID(ownerDeviceID),
              (1...200).contains(pageLimit) else {
            throw RuntimeResearchNotebookPaginationError.invalidCursor
        }
        return lock.withLock {
            let nowSeconds = Int64(now.timeIntervalSince1970)
            let monotonicNowSeconds = monotonicNow()
            removeExpiredSnapshots(
                nowSeconds: nowSeconds,
                monotonicNowSeconds: monotonicNowSeconds
            )
            removeSnapshot(for: connectionID)
            while snapshotsByID.count >= Self.maximumGlobalSnapshots {
                guard let oldest = snapshotsByID.values.min(by: { $0.sequence < $1.sequence }) else {
                    break
                }
                removeSnapshot(id: oldest.id)
            }

            let snapshotID = uniqueSnapshotID()
            let snapshot = Snapshot(
                id: snapshotID,
                connectionID: connectionID,
                ownerDeviceID: ownerDeviceID,
                context: context,
                notebooks: notebooks,
                pageLimit: pageLimit,
                expiresAtUnixSeconds: nowSeconds + Int64(Self.snapshotTTL),
                expiresAtMonotonicSeconds: monotonicNowSeconds + Self.snapshotTTL,
                sequence: nextSequence
            )
            nextSequence &+= 1
            snapshotsByID[snapshotID] = snapshot
            snapshotIDByConnection[connectionID] = snapshotID
            let result = page(from: snapshot, offset: 0)
            if result.nextCursor == nil {
                removeSnapshot(id: snapshotID)
            }
            return result
        }
    }

    func continueSnapshot(
        cursor: String,
        connectionID: UUID,
        ownerDeviceID: String,
        now: Date = Date()
    ) throws -> RuntimeResearchNotebookSnapshotPage {
        let parsed = try parse(cursor)
        guard let ownerDeviceID = Self.normalizedOwnerDeviceID(ownerDeviceID) else {
            throw RuntimeResearchNotebookPaginationError.invalidCursor
        }
        return try lock.withLock {
            let nowSeconds = Int64(now.timeIntervalSince1970)
            let monotonicNowSeconds = monotonicNow()
            removeExpiredSnapshots(
                nowSeconds: nowSeconds,
                monotonicNowSeconds: monotonicNowSeconds
            )
            guard let snapshot = snapshotsByID[parsed.snapshotID],
                  snapshot.connectionID == connectionID,
                  snapshot.ownerDeviceID == ownerDeviceID,
                  snapshot.context.includeArchived == parsed.includeArchived,
                  snapshot.pageLimit == parsed.pageLimit,
                  snapshot.notebooks.count == parsed.snapshotCount,
                  snapshot.expiresAtUnixSeconds == parsed.expiresAtUnixSeconds,
                  parsed.expiresAtUnixSeconds > nowSeconds,
                  snapshot.expiresAtMonotonicSeconds > monotonicNowSeconds,
                  parsed.offset > 0,
                  parsed.offset < snapshot.notebooks.count,
                  parsed.offset.isMultiple(of: snapshot.pageLimit),
                  HMAC<SHA256>.isValidAuthenticationCode(
                    parsed.authenticationCode,
                    authenticating: canonicalAuthenticationData(
                        snapshot: snapshot,
                        offset: parsed.offset
                    ),
                    using: authenticationKey
                  ) else {
                throw RuntimeResearchNotebookPaginationError.invalidCursor
            }
            let result = page(from: snapshot, offset: parsed.offset)
            if result.nextCursor == nil {
                removeSnapshot(id: snapshot.id)
            }
            return result
        }
    }

    func clearConnection(_ connectionID: UUID) {
        lock.withLock {
            removeSnapshot(for: connectionID)
        }
    }

    func invalidateOwner(_ ownerDeviceID: String) {
        guard let normalizedOwner = Self.normalizedOwnerDeviceID(ownerDeviceID) else { return }
        lock.withLock {
            let matchingIDs = snapshotsByID.values
                .filter { $0.ownerDeviceID == normalizedOwner }
                .map(\.id)
            matchingIDs.forEach(removeSnapshot(id:))
        }
    }

    private func page(from snapshot: Snapshot, offset: Int) -> RuntimeResearchNotebookSnapshotPage {
        let end = min(snapshot.notebooks.count, offset + snapshot.pageLimit)
        let notebooks = offset < end ? Array(snapshot.notebooks[offset..<end]) : []
        let nextCursor = end < snapshot.notebooks.count ? cursor(snapshot: snapshot, offset: end) : nil
        return RuntimeResearchNotebookSnapshotPage(
            notebooks: notebooks,
            snapshotCount: snapshot.notebooks.count,
            nextCursor: nextCursor
        )
    }

    private func cursor(snapshot: Snapshot, offset: Int) -> String {
        let code = HMAC<SHA256>.authenticationCode(
            for: canonicalAuthenticationData(snapshot: snapshot, offset: offset),
            using: authenticationKey
        )
        return [
            "v1",
            snapshot.id,
            snapshot.context.includeArchived ? "1" : "0",
            String(snapshot.pageLimit),
            String(snapshot.notebooks.count),
            String(offset),
            String(snapshot.expiresAtUnixSeconds),
            Data(code).runtimeResearchNotebookLowercaseHex
        ].joined(separator: ".")
    }

    private func parse(_ cursor: String) throws -> ParsedCursor {
        guard cursor.utf8.count <= Self.maximumCursorUTF8Bytes else {
            throw RuntimeResearchNotebookPaginationError.invalidCursor
        }
        let fields = cursor.split(separator: ".", omittingEmptySubsequences: false).map(String.init)
        guard fields.count == 8,
              fields[0] == "v1",
              let uuid = UUID(uuidString: fields[1]),
              uuid.uuidString.lowercased() == fields[1],
              fields[2] == "0" || fields[2] == "1",
              let pageLimit = Self.canonicalPositiveInt(fields[3]),
              (1...200).contains(pageLimit),
              let snapshotCount = Self.canonicalNonNegativeInt(fields[4]),
              snapshotCount <= Self.maximumSnapshotCount,
              let offset = Self.canonicalPositiveInt(fields[5]),
              let expiry = Int64(fields[6]),
              expiry > 0,
              String(expiry) == fields[6],
              let authenticationCode = Data(
                runtimeResearchNotebookCanonicalLowercaseHex: fields[7]
              ),
              authenticationCode.count == SHA256.byteCount else {
            throw RuntimeResearchNotebookPaginationError.invalidCursor
        }
        return ParsedCursor(
            snapshotID: fields[1],
            includeArchived: fields[2] == "1",
            pageLimit: pageLimit,
            snapshotCount: snapshotCount,
            offset: offset,
            expiresAtUnixSeconds: expiry,
            authenticationCode: authenticationCode
        )
    }

    private func canonicalAuthenticationData(snapshot: Snapshot, offset: Int) -> Data {
        let fields = [
            "AetherLink research notebook pagination cursor v1",
            snapshot.id,
            snapshot.connectionID.uuidString.lowercased(),
            Self.base64URL(snapshot.ownerDeviceID),
            snapshot.context.includeArchived ? "1" : "0",
            String(snapshot.pageLimit),
            String(snapshot.notebooks.count),
            String(offset),
            String(snapshot.expiresAtUnixSeconds)
        ]
        return Data(fields.joined(separator: "\n").utf8)
    }

    private func uniqueSnapshotID() -> String {
        while true {
            let candidate = UUID().uuidString.lowercased()
            if snapshotsByID[candidate] == nil { return candidate }
        }
    }

    private func removeExpiredSnapshots(
        nowSeconds: Int64,
        monotonicNowSeconds: TimeInterval
    ) {
        let expiredIDs = snapshotsByID.values
            .filter {
                $0.expiresAtUnixSeconds <= nowSeconds
                    || $0.expiresAtMonotonicSeconds <= monotonicNowSeconds
            }
            .map(\.id)
        expiredIDs.forEach(removeSnapshot(id:))
    }

    private func removeSnapshot(for connectionID: UUID) {
        guard let snapshotID = snapshotIDByConnection[connectionID] else { return }
        removeSnapshot(id: snapshotID)
    }

    private func removeSnapshot(id: String) {
        guard let removed = snapshotsByID.removeValue(forKey: id) else { return }
        if snapshotIDByConnection[removed.connectionID] == id {
            snapshotIDByConnection[removed.connectionID] = nil
        }
    }

    private static func normalizedOwnerDeviceID(_ ownerDeviceID: String) -> String? {
        let value = ownerDeviceID.trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }

    private static func canonicalPositiveInt(_ value: String) -> Int? {
        guard let parsed = Int(value), parsed > 0, String(parsed) == value else { return nil }
        return parsed
    }

    private static func canonicalNonNegativeInt(_ value: String) -> Int? {
        guard let parsed = Int(value), parsed >= 0, String(parsed) == value else { return nil }
        return parsed
    }

    private static func base64URL(_ value: String) -> String {
        Data(value.utf8).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}

private extension Data {
    init?(runtimeResearchNotebookCanonicalLowercaseHex value: String) {
        guard value.count % 2 == 0,
              value.utf8.allSatisfy({ byte in
                  (byte >= 48 && byte <= 57) || (byte >= 97 && byte <= 102)
              }) else {
            return nil
        }
        var bytes: [UInt8] = []
        bytes.reserveCapacity(value.count / 2)
        var index = value.startIndex
        while index < value.endIndex {
            let next = value.index(index, offsetBy: 2)
            guard let byte = UInt8(value[index..<next], radix: 16) else { return nil }
            bytes.append(byte)
            index = next
        }
        self = Data(bytes)
    }

    var runtimeResearchNotebookLowercaseHex: String {
        map { String(format: "%02x", $0) }.joined()
    }
}
