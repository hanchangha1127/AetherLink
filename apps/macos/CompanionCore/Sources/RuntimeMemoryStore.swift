import Foundation

public struct RuntimeMemoryEntry: Equatable, Sendable {
    public var id: String
    public var content: String
    public var enabled: Bool
    public var createdAt: Date
    public var updatedAt: Date

    public init(
        id: String,
        content: String,
        enabled: Bool = true,
        createdAt: Date,
        updatedAt: Date
    ) {
        self.id = id
        self.content = content
        self.enabled = enabled
        self.createdAt = createdAt
        self.updatedAt = updatedAt
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

public enum RuntimeMemoryStoreError: Error, LocalizedError, Equatable {
    case emptyContent
    case missingID

    public var errorDescription: String? {
        switch self {
        case .emptyContent:
            return "Memory content must not be empty."
        case .missingID:
            return "Memory id must not be empty."
        }
    }
}

public protocol RuntimeMemoryStore: Sendable {
    func list() throws -> [RuntimeMemoryEntry]
    func upsert(id: String?, content: String, enabled: Bool?, timestamp: Date) throws -> RuntimeMemoryEntry
    func delete(id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult
}

public struct NullRuntimeMemoryStore: RuntimeMemoryStore {
    public init() {}

    public func list() throws -> [RuntimeMemoryEntry] {
        []
    }

    public func upsert(id: String?, content: String, enabled: Bool?, timestamp: Date) throws -> RuntimeMemoryEntry {
        let cleanID = id
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .flatMap { $0.takeIfNotEmpty() } ?? UUID().uuidString
        return RuntimeMemoryEntry(
            id: cleanID,
            content: content.trimmingCharacters(in: .whitespacesAndNewlines),
            enabled: enabled ?? true,
            createdAt: timestamp,
            updatedAt: timestamp
        )
    }

    public func delete(id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult {
        RuntimeMemoryDeleteResult(id: id, deletedAt: timestamp)
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

    public func list() throws -> [RuntimeMemoryEntry] {
        try lock.withLock {
            Self.entries(from: try readEvents())
        }
    }

    public func upsert(
        id: String?,
        content: String,
        enabled: Bool?,
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
            let existing = Self.entries(from: try readEvents()).first { $0.id == cleanID }
            let entry = RuntimeMemoryEntry(
                id: cleanID,
                content: cleanContent,
                enabled: enabled ?? existing?.enabled ?? true,
                createdAt: existing?.createdAt ?? timestamp,
                updatedAt: timestamp
            )
            try appendUnlocked(RuntimeMemoryStoredEvent(
                kind: .upsert,
                id: entry.id,
                timestamp: timestamp,
                content: entry.content,
                enabled: entry.enabled,
                createdAt: entry.createdAt
            ))
            return entry
        }
    }

    public func delete(id: String, timestamp: Date = Date()) throws -> RuntimeMemoryDeleteResult {
        try lock.withLock {
            let cleanID = id.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !cleanID.isEmpty else {
                throw RuntimeMemoryStoreError.missingID
            }
            try appendUnlocked(RuntimeMemoryStoredEvent(
                kind: .delete,
                id: cleanID,
                timestamp: timestamp
            ))
            return RuntimeMemoryDeleteResult(id: cleanID, deletedAt: timestamp)
        }
    }

    public static func defaultFileURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-memory-events.jsonl", isDirectory: false)
    }

    private func readEvents() throws -> [RuntimeMemoryStoredEvent] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let data = try Data(contentsOf: fileURL)
        guard !data.isEmpty else { return [] }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return String(decoding: data, as: UTF8.self)
            .split(separator: "\n")
            .compactMap { line in
                guard let lineData = line.data(using: .utf8) else { return nil }
                return try? decoder.decode(RuntimeMemoryStoredEvent.self, from: lineData)
            }
            .sorted { $0.timestamp < $1.timestamp }
    }

    private func appendUnlocked(_ event: RuntimeMemoryStoredEvent) throws {
        let directory = fileURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let data = try encoder.encode(event)
        let line = data + Data([0x0A])
        if FileManager.default.fileExists(atPath: fileURL.path) {
            let handle = try FileHandle(forWritingTo: fileURL)
            defer { try? handle.close() }
            try handle.seekToEnd()
            try handle.write(contentsOf: line)
        } else {
            try line.write(to: fileURL, options: .atomic)
        }
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
                    updatedAt: event.timestamp
                )
            case .delete:
                entriesByID.removeValue(forKey: event.id)
            }
        }
        return entriesByID.values.sorted {
            if $0.updatedAt == $1.updatedAt {
                return $0.id < $1.id
            }
            return $0.updatedAt > $1.updatedAt
        }
    }
}

private enum RuntimeMemoryStoredEventKind: String, Codable {
    case upsert
    case delete
}

private struct RuntimeMemoryStoredEvent: Codable {
    var kind: RuntimeMemoryStoredEventKind
    var id: String
    var timestamp: Date
    var content: String?
    var enabled: Bool?
    var createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case kind
        case id
        case timestamp
        case content
        case enabled
        case createdAt = "created_at"
    }
}

private extension String {
    func takeIfNotEmpty() -> String? {
        isEmpty ? nil : self
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
