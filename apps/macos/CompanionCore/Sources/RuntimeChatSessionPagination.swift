import CryptoKit
import Foundation

enum RuntimeChatSessionPaginationError: Error {
    case invalidCursor
    case snapshotLimitExceeded
}

struct RuntimeChatSessionSnapshotContext: Equatable, Sendable {
    var mode: String
    var includeArchived: Bool
    var query: String?
    var embeddingModelID: String?
}

struct RuntimeChatSessionSnapshotPage: Sendable {
    var sessions: [RuntimeChatStoredSession]
    var snapshotCount: Int
    var nextCursor: String?
}

final class RuntimeChatSessionPagination: @unchecked Sendable {
    static let maximumSnapshotCount = 10_000
    static let maximumCursorUTF8Bytes = 512
    static let snapshotTTL: TimeInterval = 120
    static let maximumGlobalSnapshots = 8

    private struct Snapshot {
        var id: String
        var connectionID: UUID
        var ownerDeviceID: String?
        var context: RuntimeChatSessionSnapshotContext
        var sessions: [RuntimeChatStoredSession]
        var pageLimit: Int
        var expiresAtUnixSeconds: Int64
        var expiresAtMonotonicSeconds: TimeInterval
        var sequence: UInt64
    }

    private struct ParsedCursor {
        var snapshotID: String
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
        ownerDeviceID: String?,
        context: RuntimeChatSessionSnapshotContext,
        sessions: [RuntimeChatStoredSession],
        pageLimit: Int,
        now: Date = Date()
    ) throws -> RuntimeChatSessionSnapshotPage {
        guard sessions.count <= Self.maximumSnapshotCount else {
            throw RuntimeChatSessionPaginationError.snapshotLimitExceeded
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
                ownerDeviceID: Self.normalizedOwnerDeviceID(ownerDeviceID),
                context: context,
                sessions: sessions,
                pageLimit: max(0, min(pageLimit, 200)),
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
        ownerDeviceID: String?,
        now: Date = Date()
    ) throws -> RuntimeChatSessionSnapshotPage {
        let parsed = try parse(cursor)
        return try lock.withLock {
            let nowSeconds = Int64(now.timeIntervalSince1970)
            let monotonicNowSeconds = monotonicNow()
            removeExpiredSnapshots(
                nowSeconds: nowSeconds,
                monotonicNowSeconds: monotonicNowSeconds
            )
            guard let snapshot = snapshotsByID[parsed.snapshotID],
                  snapshot.connectionID == connectionID,
                  snapshot.ownerDeviceID == Self.normalizedOwnerDeviceID(ownerDeviceID),
                  snapshot.expiresAtUnixSeconds == parsed.expiresAtUnixSeconds,
                  parsed.expiresAtUnixSeconds > nowSeconds,
                  snapshot.expiresAtMonotonicSeconds > monotonicNowSeconds,
                  parsed.offset > 0,
                  parsed.offset < snapshot.sessions.count,
                  HMAC<SHA256>.isValidAuthenticationCode(
                    parsed.authenticationCode,
                    authenticating: canonicalAuthenticationData(
                        snapshot: snapshot,
                        offset: parsed.offset
                    ),
                    using: authenticationKey
                  ) else {
                throw RuntimeChatSessionPaginationError.invalidCursor
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

    func invalidateOwner(_ ownerDeviceID: String?) {
        let normalizedOwner = Self.normalizedOwnerDeviceID(ownerDeviceID)
        lock.withLock {
            let matchingIDs = snapshotsByID.values
                .filter { $0.ownerDeviceID == normalizedOwner }
                .map(\.id)
            matchingIDs.forEach(removeSnapshot(id:))
        }
    }

    private func page(from snapshot: Snapshot, offset: Int) -> RuntimeChatSessionSnapshotPage {
        guard snapshot.pageLimit > 0 else {
            return RuntimeChatSessionSnapshotPage(
                sessions: [],
                snapshotCount: snapshot.sessions.count,
                nextCursor: nil
            )
        }
        let end = min(snapshot.sessions.count, offset + snapshot.pageLimit)
        let sessions = offset < end ? Array(snapshot.sessions[offset..<end]) : []
        let nextCursor = end < snapshot.sessions.count ? cursor(snapshot: snapshot, offset: end) : nil
        return RuntimeChatSessionSnapshotPage(
            sessions: sessions,
            snapshotCount: snapshot.sessions.count,
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
            String(offset),
            String(snapshot.expiresAtUnixSeconds),
            Data(code).lowercaseHex
        ].joined(separator: ".")
    }

    private func parse(_ cursor: String) throws -> ParsedCursor {
        guard cursor.utf8.count <= Self.maximumCursorUTF8Bytes else {
            throw RuntimeChatSessionPaginationError.invalidCursor
        }
        let fields = cursor.split(separator: ".", omittingEmptySubsequences: false).map(String.init)
        guard fields.count == 5,
              fields[0] == "v1",
              let uuid = UUID(uuidString: fields[1]),
              uuid.uuidString.lowercased() == fields[1],
              let offset = Int(fields[2]),
              offset > 0,
              String(offset) == fields[2],
              let expiry = Int64(fields[3]),
              expiry > 0,
              String(expiry) == fields[3],
              let authenticationCode = Data(canonicalLowercaseHex: fields[4]),
              authenticationCode.count == SHA256.byteCount else {
            throw RuntimeChatSessionPaginationError.invalidCursor
        }
        return ParsedCursor(
            snapshotID: fields[1],
            offset: offset,
            expiresAtUnixSeconds: expiry,
            authenticationCode: authenticationCode
        )
    }

    private func canonicalAuthenticationData(snapshot: Snapshot, offset: Int) -> Data {
        let fields = [
            "AetherLink chat session pagination cursor v1",
            snapshot.id,
            snapshot.connectionID.uuidString.lowercased(),
            Self.base64URL(snapshot.ownerDeviceID ?? ""),
            Self.base64URL(snapshot.context.mode),
            snapshot.context.includeArchived ? "1" : "0",
            Self.base64URL(snapshot.context.query ?? ""),
            Self.base64URL(snapshot.context.embeddingModelID ?? ""),
            String(snapshot.pageLimit),
            String(snapshot.sessions.count),
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

    private static func normalizedOwnerDeviceID(_ ownerDeviceID: String?) -> String? {
        guard let value = ownerDeviceID?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else {
            return nil
        }
        return value
    }

    private static func base64URL(_ value: String) -> String {
        Data(value.utf8).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}

private extension Data {
    init?(canonicalLowercaseHex value: String) {
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

    var lowercaseHex: String {
        map { String(format: "%02x", $0) }.joined()
    }
}
