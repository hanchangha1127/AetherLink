import Foundation

public struct RuntimeMemoryEntry: Equatable, Sendable {
    public var id: String
    public var content: String
    public var enabled: Bool
    public var createdAt: Date
    public var updatedAt: Date
    public var source: RuntimeMemoryEntrySource?

    public init(
        id: String,
        content: String,
        enabled: Bool = true,
        createdAt: Date,
        updatedAt: Date,
        source: RuntimeMemoryEntrySource? = nil
    ) {
        self.id = id
        self.content = content
        self.enabled = enabled
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.source = source
    }
}

public struct RuntimeMemoryEntrySource: Codable, Equatable, Sendable {
    public var kind: String
    public var draftID: String
    public var summaryMethod: String
    public var session: RuntimeMemoryEntrySourceSession
    public var sourceMessageCount: Int
    public var sourceRange: String
    public var sourcePointers: [RuntimeMemoryEntrySourcePointer]

    public init(
        kind: String,
        draftID: String,
        summaryMethod: String,
        session: RuntimeMemoryEntrySourceSession,
        sourceMessageCount: Int,
        sourceRange: String,
        sourcePointers: [RuntimeMemoryEntrySourcePointer]
    ) {
        self.kind = kind
        self.draftID = draftID
        self.summaryMethod = summaryMethod
        self.session = session
        self.sourceMessageCount = sourceMessageCount
        self.sourceRange = sourceRange
        self.sourcePointers = sourcePointers
    }

    enum CodingKeys: String, CodingKey {
        case kind
        case draftID = "draft_id"
        case summaryMethod = "summary_method"
        case session
        case sourceMessageCount = "source_message_count"
        case sourceRange = "source_range"
        case sourcePointers = "source_pointers"
    }
}

public struct RuntimeMemoryEntrySourceSession: Codable, Equatable, Sendable {
    public var sessionID: String
    public var title: String
    public var model: String
    public var lastActivityAt: Date
    public var messageCount: Int
    public var inactiveSeconds: Int

    public init(
        sessionID: String,
        title: String,
        model: String,
        lastActivityAt: Date,
        messageCount: Int,
        inactiveSeconds: Int
    ) {
        self.sessionID = sessionID
        self.title = title
        self.model = model
        self.lastActivityAt = lastActivityAt
        self.messageCount = messageCount
        self.inactiveSeconds = inactiveSeconds
    }

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case title
        case model
        case lastActivityAt = "last_activity_at"
        case messageCount = "message_count"
        case inactiveSeconds = "inactive_seconds"
    }
}

public struct RuntimeMemoryEntrySourcePointer: Codable, Equatable, Sendable {
    public var sessionID: String
    public var messageIndex: Int
    public var role: String
    public var createdAt: Date?
    public var excerpt: String

    public init(
        sessionID: String,
        messageIndex: Int,
        role: String,
        createdAt: Date?,
        excerpt: String
    ) {
        self.sessionID = sessionID
        self.messageIndex = messageIndex
        self.role = role
        self.createdAt = createdAt
        self.excerpt = excerpt
    }

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case messageIndex = "message_index"
        case role
        case createdAt = "created_at"
        case excerpt
    }
}

public struct RuntimeMemoryDeleteResult: Equatable, Sendable {
    public var id: String
    public var deletedAt: Date

    public init(id: String, deletedAt: Date) {
        self.id = id
        self.deletedAt = deletedAt
    }
}

public struct RuntimeMemorySummaryDraftDismissResult: Equatable, Sendable {
    public var draftID: String
    public var dismissedAt: Date

    public init(draftID: String, dismissedAt: Date) {
        self.draftID = draftID
        self.dismissedAt = dismissedAt
    }
}

public enum RuntimeMemoryStoreError: Error, LocalizedError, Equatable {
    case emptyContent
    case missingID
    case corruptEventLog(line: Int, reason: String)

    public var errorDescription: String? {
        switch self {
        case .emptyContent:
            return "Memory content must not be empty."
        case .missingID:
            return "Memory id must not be empty."
        case .corruptEventLog(let line, let reason):
            return "Runtime memory event log is corrupt at line \(line): \(reason)"
        }
    }
}

public protocol RuntimeMemoryStore: Sendable {
    func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry]
    func listAll() throws -> [RuntimeMemoryEntry]
    func upsert(
        ownerDeviceID: String?,
        id: String?,
        content: String,
        enabled: Bool?,
        source: RuntimeMemoryEntrySource?,
        timestamp: Date
    ) throws -> RuntimeMemoryEntry
    func delete(ownerDeviceID: String?, id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult
    func dismissedMemorySummaryDraftIDs(ownerDeviceID: String?) throws -> Set<String>
    func dismissMemorySummaryDraft(
        ownerDeviceID: String?,
        draftID: String,
        timestamp: Date
    ) throws -> RuntimeMemorySummaryDraftDismissResult
}

public extension RuntimeMemoryStore {
    func list() throws -> [RuntimeMemoryEntry] {
        try list(ownerDeviceID: nil)
    }

    func upsert(id: String?, content: String, enabled: Bool?, timestamp: Date) throws -> RuntimeMemoryEntry {
        try upsert(ownerDeviceID: nil, id: id, content: content, enabled: enabled, source: nil, timestamp: timestamp)
    }

    func upsert(
        ownerDeviceID: String?,
        id: String?,
        content: String,
        enabled: Bool?,
        timestamp: Date
    ) throws -> RuntimeMemoryEntry {
        try upsert(
            ownerDeviceID: ownerDeviceID,
            id: id,
            content: content,
            enabled: enabled,
            source: nil,
            timestamp: timestamp
        )
    }

    func delete(id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult {
        try delete(ownerDeviceID: nil, id: id, timestamp: timestamp)
    }
}

public struct NullRuntimeMemoryStore: RuntimeMemoryStore {
    public init() {}

    public func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry] {
        []
    }

    public func listAll() throws -> [RuntimeMemoryEntry] {
        []
    }

    public func upsert(
        ownerDeviceID: String?,
        id: String?,
        content: String,
        enabled: Bool?,
        source: RuntimeMemoryEntrySource?,
        timestamp: Date
    ) throws -> RuntimeMemoryEntry {
        let cleanID = id
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .flatMap { $0.takeIfNotEmpty() } ?? UUID().uuidString
        return RuntimeMemoryEntry(
            id: cleanID,
            content: content.trimmingCharacters(in: .whitespacesAndNewlines),
            enabled: enabled ?? true,
            createdAt: timestamp,
            updatedAt: timestamp,
            source: source
        )
    }

    public func delete(ownerDeviceID: String?, id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult {
        RuntimeMemoryDeleteResult(id: id, deletedAt: timestamp)
    }

    public func dismissedMemorySummaryDraftIDs(ownerDeviceID: String?) throws -> Set<String> {
        []
    }

    public func dismissMemorySummaryDraft(
        ownerDeviceID: String?,
        draftID: String,
        timestamp: Date
    ) throws -> RuntimeMemorySummaryDraftDismissResult {
        RuntimeMemorySummaryDraftDismissResult(draftID: draftID, dismissedAt: timestamp)
    }
}

public final class JSONLRuntimeMemoryStore: RuntimeMemoryStore, @unchecked Sendable {
    private let fileURL: URL
    private let encoder: JSONEncoder
    private let lock = NSLock()

    public init(fileURL: URL = JSONLRuntimeMemoryStore.defaultFileURL()) {
        self.fileURL = fileURL
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
        self.encoder.outputFormatting = [.sortedKeys]
    }

    public func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry] {
        try lock.withLock {
            Self.entries(from: try readEvents(ownerDeviceID: ownerDeviceID))
        }
    }

    public func listAll() throws -> [RuntimeMemoryEntry] {
        try lock.withLock {
            Self.entries(from: try readEvents())
        }
    }

    public func upsert(
        ownerDeviceID: String?,
        id: String?,
        content: String,
        enabled: Bool?,
        source: RuntimeMemoryEntrySource?,
        timestamp: Date = Date()
    ) throws -> RuntimeMemoryEntry {
        try lock.withLock {
            let cleanContent = content.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !cleanContent.isEmpty else {
                throw RuntimeMemoryStoreError.emptyContent
            }
            let cleanID = id
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .flatMap { $0.takeIfNotEmpty() } ?? UUID().uuidString
            let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
            let existing = Self.entries(from: try readEvents(ownerDeviceID: scopedOwnerDeviceID))
                .first { $0.id == cleanID }
            let entry = RuntimeMemoryEntry(
                id: cleanID,
                content: cleanContent,
                enabled: enabled ?? existing?.enabled ?? true,
                createdAt: existing?.createdAt ?? timestamp,
                updatedAt: timestamp,
                source: source ?? existing?.source
            )
            try appendUnlocked(RuntimeMemoryStoredEvent(
                kind: .upsert,
                id: entry.id,
                timestamp: timestamp,
                content: entry.content,
                enabled: entry.enabled,
                createdAt: entry.createdAt,
                ownerDeviceID: scopedOwnerDeviceID,
                source: entry.source
            ))
            return entry
        }
    }

    public func delete(ownerDeviceID: String?, id: String, timestamp: Date = Date()) throws -> RuntimeMemoryDeleteResult {
        try lock.withLock {
            let cleanID = id.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !cleanID.isEmpty else {
                throw RuntimeMemoryStoreError.missingID
            }
            let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
            try appendUnlocked(RuntimeMemoryStoredEvent(
                kind: .delete,
                id: cleanID,
                timestamp: timestamp,
                ownerDeviceID: scopedOwnerDeviceID
            ))
            return RuntimeMemoryDeleteResult(id: cleanID, deletedAt: timestamp)
        }
    }

    public func dismissedMemorySummaryDraftIDs(ownerDeviceID: String?) throws -> Set<String> {
        try lock.withLock {
            Self.dismissedMemorySummaryDraftIDs(from: try readEvents(ownerDeviceID: ownerDeviceID))
        }
    }

    public func dismissMemorySummaryDraft(
        ownerDeviceID: String?,
        draftID: String,
        timestamp: Date = Date()
    ) throws -> RuntimeMemorySummaryDraftDismissResult {
        try lock.withLock {
            let cleanDraftID = draftID.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !cleanDraftID.isEmpty else {
                throw RuntimeMemoryStoreError.missingID
            }
            let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
            try appendUnlocked(RuntimeMemoryStoredEvent(
                kind: .dismissMemorySummaryDraft,
                id: cleanDraftID,
                timestamp: timestamp,
                ownerDeviceID: scopedOwnerDeviceID
            ))
            return RuntimeMemorySummaryDraftDismissResult(draftID: cleanDraftID, dismissedAt: timestamp)
        }
    }

    public static func defaultFileURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-memory-events.jsonl", isDirectory: false)
    }

    private func readEvents(ownerDeviceID: String?) throws -> [RuntimeMemoryStoredEvent] {
        let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        return try readEvents().filter { $0.ownerDeviceID == scopedOwnerDeviceID }
    }

    private func readEvents() throws -> [RuntimeMemoryStoredEvent] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let data = try Data(contentsOf: fileURL)
        guard !data.isEmpty else { return [] }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let lines = String(decoding: data, as: UTF8.self)
            .components(separatedBy: .newlines)
        var events: [RuntimeMemoryStoredEvent] = []
        for (index, line) in lines.enumerated() {
            guard !line.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                continue
            }
            do {
                let event = try decoder.decode(RuntimeMemoryStoredEvent.self, from: Data(line.utf8))
                try Self.validateStoredEvent(event, line: index + 1)
                events.append(event)
            } catch {
                if let storeError = error as? RuntimeMemoryStoreError {
                    throw storeError
                }
                throw RuntimeMemoryStoreError.corruptEventLog(
                    line: index + 1,
                    reason: Self.decodeFailureReason(error)
                )
            }
        }
        return events.sorted { $0.timestamp < $1.timestamp }
    }

    private static func decodeFailureReason(_ error: Error) -> String {
        if let decodingError = error as? DecodingError {
            switch decodingError {
            case .dataCorrupted:
                return "data corrupted"
            case .keyNotFound(let key, _):
                return "missing key '\(key.stringValue)'"
            case .typeMismatch(let type, _):
                return "type mismatch for \(type)"
            case .valueNotFound(let type, _):
                return "missing value for \(type)"
            @unknown default:
                return "decode failed"
            }
        }
        return "decode failed"
    }

    private static func validateStoredEvent(_ event: RuntimeMemoryStoredEvent, line: Int) throws {
        guard !event.id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw RuntimeMemoryStoreError.corruptEventLog(
                line: line,
                reason: "memory event id is empty"
            )
        }
        switch event.kind {
        case .upsert:
            guard let content = event.content?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !content.isEmpty else {
                throw RuntimeMemoryStoreError.corruptEventLog(
                    line: line,
                    reason: "memory upsert content is empty"
                )
            }
            if let source = event.source {
                try validateStoredSource(source, line: line)
            }
        case .delete,
             .dismissMemorySummaryDraft:
            break
        }
    }

    private static func validateStoredSource(_ source: RuntimeMemoryEntrySource, line: Int) throws {
        guard !source.kind.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw RuntimeMemoryStoreError.corruptEventLog(
                line: line,
                reason: "memory source kind is empty"
            )
        }
        guard !source.draftID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw RuntimeMemoryStoreError.corruptEventLog(
                line: line,
                reason: "memory source draft id is empty"
            )
        }
        guard source.sourceMessageCount > 0 else {
            throw RuntimeMemoryStoreError.corruptEventLog(
                line: line,
                reason: "memory source message count is invalid"
            )
        }
        guard !source.sourcePointers.isEmpty else {
            throw RuntimeMemoryStoreError.corruptEventLog(
                line: line,
                reason: "memory source pointers are empty"
            )
        }
        for pointer in source.sourcePointers {
            guard !pointer.sessionID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  !pointer.role.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  !pointer.excerpt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                throw RuntimeMemoryStoreError.corruptEventLog(
                    line: line,
                    reason: "memory source pointer is invalid"
                )
            }
        }
    }

    private func appendUnlocked(_ event: RuntimeMemoryStoredEvent) throws {
        let data = try encoder.encode(event)
        let line = data + Data([0x0A])
        try RuntimeEventLogFileProtection.appendLine(line, to: fileURL)
    }

    private static func entries(from events: [RuntimeMemoryStoredEvent]) -> [RuntimeMemoryEntry] {
        var entriesByID: [String: RuntimeMemoryEntry] = [:]
        for event in events {
            switch event.kind {
            case .upsert:
                guard let content = event.content?.trimmingCharacters(in: .whitespacesAndNewlines),
                      !content.isEmpty else {
                    continue
                }
                let existing = entriesByID[event.id]
                entriesByID[event.id] = RuntimeMemoryEntry(
                    id: event.id,
                    content: content,
                    enabled: event.enabled ?? existing?.enabled ?? true,
                    createdAt: event.createdAt ?? existing?.createdAt ?? event.timestamp,
                    updatedAt: event.timestamp,
                    source: event.source ?? existing?.source
                )
            case .delete:
                entriesByID.removeValue(forKey: event.id)
            case .dismissMemorySummaryDraft:
                break
            }
        }
        return entriesByID.values.sorted {
            if $0.updatedAt == $1.updatedAt {
                return $0.id < $1.id
            }
            return $0.updatedAt > $1.updatedAt
        }
    }

    private static func dismissedMemorySummaryDraftIDs(from events: [RuntimeMemoryStoredEvent]) -> Set<String> {
        Set(events.compactMap { event in
            event.kind == .dismissMemorySummaryDraft ? event.id : nil
        })
    }
}

private enum RuntimeMemoryStoredEventKind: String, Codable {
    case upsert
    case delete
    case dismissMemorySummaryDraft = "dismiss_memory_summary_draft"
}

private struct RuntimeMemoryStoredEvent: Codable {
    var kind: RuntimeMemoryStoredEventKind
    var id: String
    var timestamp: Date
    var content: String?
    var enabled: Bool?
    var createdAt: Date?
    var ownerDeviceID: String?
    var source: RuntimeMemoryEntrySource?

    enum CodingKeys: String, CodingKey {
        case kind
        case id
        case timestamp
        case content
        case enabled
        case createdAt = "created_at"
        case ownerDeviceID = "owner_device_id"
        case source
    }
}

private extension String {
    func takeIfNotEmpty() -> String? {
        isEmpty ? nil : self
    }
}

private extension Optional where Wrapped == String {
    var normalizedOwnerDeviceID: String? {
        guard let value = self?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else {
            return nil
        }
        return value
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
