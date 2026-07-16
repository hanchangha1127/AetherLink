import Foundation
import BridgeProtocol
import OllamaBackend

public struct RuntimeMemoryEntry: Equatable, Sendable {
    public var id: String
    public var content: String
    public var enabled: Bool
    public var createdAt: Date
    public var updatedAt: Date
    public var source: RuntimeMemoryEntrySource?
    public var search: RuntimeMemoryEntrySearch?

    public init(
        id: String,
        content: String,
        enabled: Bool = true,
        createdAt: Date,
        updatedAt: Date,
        source: RuntimeMemoryEntrySource? = nil,
        search: RuntimeMemoryEntrySearch? = nil
    ) {
        self.id = id
        self.content = content
        self.enabled = enabled
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.source = source
        self.search = search
    }
}

public struct RuntimeMemoryEntrySearch: Equatable, Sendable {
    public var rank: Int
    public var snippet: String
    public var matchedFields: [String]

    public init(rank: Int, snippet: String, matchedFields: [String]) {
        self.rank = rank
        self.snippet = snippet
        self.matchedFields = matchedFields
    }
}

public struct RuntimeMemorySemanticSearchSource: Equatable, Sendable {
    public var entry: RuntimeMemoryEntry
    public var sourceRevision: String

    public init(entry: RuntimeMemoryEntry, sourceRevision: String) {
        self.entry = entry
        self.sourceRevision = sourceRevision
    }
}

public struct RuntimeMemorySemanticEmbeddingKey: Equatable, Hashable, Sendable {
    public var ownerDeviceID: String?
    public var entryID: String
    public var canonicalQualifiedEmbeddingModelID: String
    public var modelFingerprint: String
    public var documentFingerprint: String
    public var sourceRevision: String

    public init(
        ownerDeviceID: String?,
        entryID: String,
        canonicalQualifiedEmbeddingModelID: String,
        modelFingerprint: String,
        documentFingerprint: String,
        sourceRevision: String
    ) {
        self.ownerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        self.entryID = entryID
        self.canonicalQualifiedEmbeddingModelID = canonicalQualifiedEmbeddingModelID
        self.modelFingerprint = modelFingerprint
        self.documentFingerprint = documentFingerprint
        self.sourceRevision = sourceRevision
    }
}

public struct RuntimeMemorySemanticEmbeddingRecord: Equatable, Sendable {
    public var key: RuntimeMemorySemanticEmbeddingKey
    public var embedding: [Double]

    public init(key: RuntimeMemorySemanticEmbeddingKey, embedding: [Double]) {
        self.key = key
        self.embedding = embedding
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

public struct RuntimeGeneratedMemorySummaryDraft: Equatable, Sendable {
    public static let summaryMethod = "llm_summary_v1"
    public static let maxContentCharacters = 600

    public var draftID: String
    public var sessionID: String
    public var sourceMessageCount: Int
    public var content: String
    public var modelID: String
    public var providerQualifiedModelID: String?
    public var promptSkillBinding: RuntimePromptSkillBinding
    public var generatedAt: Date

    public init(
        draftID: String,
        sessionID: String,
        sourceMessageCount: Int,
        content: String,
        modelID: String,
        providerQualifiedModelID: String? = nil,
        promptSkillBinding: RuntimePromptSkillBinding,
        generatedAt: Date
    ) {
        self.draftID = draftID.trimmingCharacters(in: .whitespacesAndNewlines)
        self.sessionID = sessionID.trimmingCharacters(in: .whitespacesAndNewlines)
        self.sourceMessageCount = sourceMessageCount
        self.content = String(
            content.trimmingCharacters(in: .whitespacesAndNewlines)
                .prefix(Self.maxContentCharacters)
        )
        self.modelID = modelID.trimmingCharacters(in: .whitespacesAndNewlines)
        self.providerQualifiedModelID = providerQualifiedModelID
        self.promptSkillBinding = promptSkillBinding
        self.generatedAt = generatedAt
    }

    public var summaryMethod: String {
        Self.summaryMethod
    }
}

public enum RuntimeMemoryStoreError: Error, LocalizedError, Equatable {
    case emptyContent
    case missingID
    case corruptEventLog(line: Int, reason: String)
    case duplicateSuggestionResourceLimitExceeded

    public var errorDescription: String? {
        switch self {
        case .emptyContent:
            return "Memory content must not be empty."
        case .missingID:
            return "Memory id must not be empty."
        case .corruptEventLog(let line, let reason):
            return "Runtime memory event log is corrupt at line \(line): \(reason)"
        case .duplicateSuggestionResourceLimitExceeded:
            return "Runtime memory duplicate suggestion scan exceeded its resource limit."
        }
    }
}

public protocol RuntimeMemoryStore: Sendable {
    func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry]
    func exactDuplicateSuggestions(ownerDeviceID: String?) throws -> RuntimeMemoryDuplicateSuggestions
    func semanticDuplicateSuggestionSources(
        ownerDeviceID: String?,
        limit: Int
    ) throws -> [RuntimeMemorySemanticSearchSource]
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
    func generatedMemorySummaryDrafts(ownerDeviceID: String?) throws -> [RuntimeGeneratedMemorySummaryDraft]
    func listSemanticSearchSources(
        ownerDeviceID: String?,
        limit: Int
    ) throws -> [RuntimeMemorySemanticSearchSource]
    func cachedMemorySemanticEmbeddings(
        for keys: [RuntimeMemorySemanticEmbeddingKey]
    ) throws -> [RuntimeMemorySemanticEmbeddingRecord]
    func upsertMemorySemanticEmbeddings(
        _ records: [RuntimeMemorySemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws
    @discardableResult
    func cacheGeneratedMemorySummaryDraft(
        ownerDeviceID: String?,
        draft: RuntimeGeneratedMemorySummaryDraft
    ) throws -> RuntimeGeneratedMemorySummaryDraft
    @discardableResult
    func cacheGeneratedMemorySummaryDraft(
        ownerDeviceID: String?,
        draft: RuntimeGeneratedMemorySummaryDraft,
        if shouldCommit: @Sendable () -> Bool
    ) throws -> RuntimeGeneratedMemorySummaryDraft?
}

public extension RuntimeMemoryStore {
    func list() throws -> [RuntimeMemoryEntry] {
        try list(ownerDeviceID: nil)
    }

    func list(ownerDeviceID: String?, query: String?) throws -> [RuntimeMemoryEntry] {
        let entries = try list(ownerDeviceID: ownerDeviceID)
        guard let searchQuery = RuntimeMemorySearchQuery(query) else {
            return entries
        }
        let matches = entries.compactMap { entry -> (entry: RuntimeMemoryEntry, match: RuntimeMemorySearchMatch)? in
            guard let match = entry.runtimeMemorySearchMatch(searchQuery) else { return nil }
            return (entry, match)
        }
        let rankedMatches = matches.sorted { lhs, rhs in
            if lhs.match.score != rhs.match.score {
                return lhs.match.score > rhs.match.score
            }
            if lhs.entry.updatedAt != rhs.entry.updatedAt {
                return lhs.entry.updatedAt > rhs.entry.updatedAt
            }
            return lhs.entry.id < rhs.entry.id
        }
        return rankedMatches.enumerated().map { offset, result in
            var entry = result.entry
            entry.search = RuntimeMemoryEntrySearch(
                rank: offset + 1,
                snippet: result.match.snippet,
                matchedFields: result.match.matchedFields
            )
            return entry
        }
    }

    func exactDuplicateSuggestions(ownerDeviceID: String?) throws -> RuntimeMemoryDuplicateSuggestions {
        try RuntimeMemoryExactDuplicateSuggester.suggestions(
            from: list(ownerDeviceID: ownerDeviceID)
        )
    }

    func semanticDuplicateSuggestionSources(
        ownerDeviceID: String?,
        limit: Int
    ) throws -> [RuntimeMemorySemanticSearchSource] {
        try listSemanticSearchSources(ownerDeviceID: ownerDeviceID, limit: limit)
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

    func generatedMemorySummaryDrafts(ownerDeviceID: String?) throws -> [RuntimeGeneratedMemorySummaryDraft] {
        []
    }

    func listSemanticSearchSources(
        ownerDeviceID: String?,
        limit: Int
    ) throws -> [RuntimeMemorySemanticSearchSource] {
        guard limit > 0 else { return [] }
        return try list(ownerDeviceID: ownerDeviceID)
            .prefix(limit)
            .map { entry in
                RuntimeMemorySemanticSearchSource(
                    entry: entry,
                    sourceRevision: RuntimeSemanticMemorySearch.sourceRevision(for: entry)
                )
            }
    }

    func cachedMemorySemanticEmbeddings(
        for keys: [RuntimeMemorySemanticEmbeddingKey]
    ) throws -> [RuntimeMemorySemanticEmbeddingRecord] {
        []
    }

    func upsertMemorySemanticEmbeddings(
        _ records: [RuntimeMemorySemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws {}

    func generatedMemorySummaryDraft(
        ownerDeviceID: String?,
        draftID: String
    ) throws -> RuntimeGeneratedMemorySummaryDraft? {
        let cleanDraftID = draftID.trimmingCharacters(in: .whitespacesAndNewlines)
        return try generatedMemorySummaryDrafts(ownerDeviceID: ownerDeviceID)
            .first { $0.draftID == cleanDraftID }
    }

    @discardableResult
    func cacheGeneratedMemorySummaryDraft(
        ownerDeviceID: String?,
        draft: RuntimeGeneratedMemorySummaryDraft
    ) throws -> RuntimeGeneratedMemorySummaryDraft {
        draft
    }

    @discardableResult
    func cacheGeneratedMemorySummaryDraft(
        ownerDeviceID: String?,
        draft: RuntimeGeneratedMemorySummaryDraft,
        if shouldCommit: @Sendable () -> Bool
    ) throws -> RuntimeGeneratedMemorySummaryDraft? {
        guard shouldCommit() else { return nil }
        let cachedDraft = try cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: ownerDeviceID,
            draft: draft
        )
        return shouldCommit() ? cachedDraft : nil
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
    private let semanticEmbeddingCache: SQLiteRuntimeMemorySemanticEmbeddingCache
    private let lock = NSLock()

    public init(
        fileURL: URL = JSONLRuntimeMemoryStore.defaultFileURL(),
        semanticCacheDatabaseURL: URL? = nil,
        semanticEmbeddingRowLimitPerOwnerModel: Int = 2_000
    ) {
        self.fileURL = fileURL
        self.semanticEmbeddingCache = SQLiteRuntimeMemorySemanticEmbeddingCache(
            databaseURL: semanticCacheDatabaseURL ?? Self.defaultSemanticCacheDatabaseURL(for: fileURL),
            rowLimitPerOwnerModel: semanticEmbeddingRowLimitPerOwnerModel
        )
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
        self.encoder.outputFormatting = [.sortedKeys]
    }

    public func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry] {
        try lock.withLock {
            Self.entries(from: try readEvents(ownerDeviceID: ownerDeviceID))
        }
    }

    public func exactDuplicateSuggestions(ownerDeviceID: String?) throws -> RuntimeMemoryDuplicateSuggestions {
        try lock.withLock {
            try RuntimeMemoryExactDuplicateSuggester.suggestions(
                from: Self.entries(
                    from: try readEvents(
                        ownerDeviceID: ownerDeviceID,
                        maximumByteCount: RuntimeMemoryExactDuplicateSuggester.maximumSourceEventLogByteCount
                    )
                )
            )
        }
    }

    public func semanticDuplicateSuggestionSources(
        ownerDeviceID: String?,
        limit: Int
    ) throws -> [RuntimeMemorySemanticSearchSource] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            Self.entries(
                from: try readEvents(
                    ownerDeviceID: ownerDeviceID,
                    maximumByteCount: RuntimeMemorySemanticDuplicateSuggester.maximumSourceEventLogByteCount
                )
            )
            .prefix(limit)
            .map { entry in
                RuntimeMemorySemanticSearchSource(
                    entry: entry,
                    sourceRevision: RuntimeSemanticMemorySearch.sourceRevision(for: entry)
                )
            }
        }
    }

    public func listAll() throws -> [RuntimeMemoryEntry] {
        try lock.withLock {
            Self.entries(from: try readEvents())
        }
    }

    public func listSemanticSearchSources(
        ownerDeviceID: String?,
        limit: Int
    ) throws -> [RuntimeMemorySemanticSearchSource] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            Self.entries(from: try readEvents(ownerDeviceID: ownerDeviceID))
                .prefix(limit)
                .map { entry in
                    RuntimeMemorySemanticSearchSource(
                        entry: entry,
                        sourceRevision: RuntimeSemanticMemorySearch.sourceRevision(for: entry)
                    )
                }
        }
    }

    public func cachedMemorySemanticEmbeddings(
        for keys: [RuntimeMemorySemanticEmbeddingKey]
    ) throws -> [RuntimeMemorySemanticEmbeddingRecord] {
        try semanticEmbeddingCache.cachedEmbeddings(for: keys)
    }

    public func upsertMemorySemanticEmbeddings(
        _ records: [RuntimeMemorySemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws {
        guard !records.isEmpty else { return }
        try lock.withLock {
            guard shouldCommit() else { return }
            let recordsByOwner = Dictionary(grouping: records, by: { $0.key.ownerDeviceID })
            var currentRecords: [RuntimeMemorySemanticEmbeddingRecord] = []
            for (ownerDeviceID, ownerRecords) in recordsByOwner {
                let currentRevisions = Dictionary(uniqueKeysWithValues:
                    Self.entries(from: try readEvents(ownerDeviceID: ownerDeviceID)).map { entry in
                        (entry.id, RuntimeSemanticMemorySearch.sourceRevision(for: entry))
                    }
                )
                currentRecords.append(contentsOf: ownerRecords.filter { record in
                    currentRevisions[record.key.entryID] == record.key.sourceRevision
                })
            }
            guard !currentRecords.isEmpty, shouldCommit() else { return }
            try semanticEmbeddingCache.upsertEmbeddings(currentRecords, if: shouldCommit)
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
            try semanticEmbeddingCache.deleteEmbeddings(
                ownerDeviceID: scopedOwnerDeviceID,
                entryID: entry.id
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
            try semanticEmbeddingCache.deleteEmbeddings(
                ownerDeviceID: scopedOwnerDeviceID,
                entryID: cleanID
            )
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

    public func generatedMemorySummaryDrafts(
        ownerDeviceID: String?
    ) throws -> [RuntimeGeneratedMemorySummaryDraft] {
        try lock.withLock {
            Self.generatedMemorySummaryDrafts(from: try readEvents(ownerDeviceID: ownerDeviceID))
        }
    }

    @discardableResult
    public func cacheGeneratedMemorySummaryDraft(
        ownerDeviceID: String?,
        draft: RuntimeGeneratedMemorySummaryDraft
    ) throws -> RuntimeGeneratedMemorySummaryDraft {
        try cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: ownerDeviceID,
            draft: draft,
            if: { true }
        ) ?? draft
    }

    @discardableResult
    public func cacheGeneratedMemorySummaryDraft(
        ownerDeviceID: String?,
        draft: RuntimeGeneratedMemorySummaryDraft,
        if shouldCommit: @Sendable () -> Bool
    ) throws -> RuntimeGeneratedMemorySummaryDraft? {
        try lock.withLock {
            try Self.validateGeneratedMemorySummaryDraft(draft)
            guard shouldCommit() else { return nil }
            try appendUnlocked(RuntimeMemoryStoredEvent(
                kind: .generatedMemorySummaryDraft,
                id: draft.draftID,
                timestamp: draft.generatedAt,
                content: draft.content,
                ownerDeviceID: ownerDeviceID.normalizedOwnerDeviceID,
                sessionID: draft.sessionID,
                sourceMessageCount: draft.sourceMessageCount,
                summaryMethod: draft.summaryMethod,
                modelID: draft.modelID,
                providerQualifiedModelID: draft.providerQualifiedModelID,
                promptSkillID: draft.promptSkillBinding.identifier,
                promptSkillRevision: draft.promptSkillBinding.revision,
                generatedAt: draft.generatedAt
            ))
            return draft
        }
    }

    public static func defaultFileURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-memory-events.jsonl", isDirectory: false)
    }

    public static func defaultSemanticCacheDatabaseURL(for fileURL: URL = defaultFileURL()) -> URL {
        fileURL.deletingPathExtension().appendingPathExtension("semantic-cache.sqlite")
    }

    private func readEvents(ownerDeviceID: String?) throws -> [RuntimeMemoryStoredEvent] {
        let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        return try readEvents().filter { $0.ownerDeviceID == scopedOwnerDeviceID }
    }

    private func readEvents(
        ownerDeviceID: String?,
        maximumByteCount: Int
    ) throws -> [RuntimeMemoryStoredEvent] {
        let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        return try readEvents(maximumByteCount: maximumByteCount)
            .filter { $0.ownerDeviceID == scopedOwnerDeviceID }
    }

    private func readEvents() throws -> [RuntimeMemoryStoredEvent] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let data = try Data(contentsOf: fileURL)
        return try Self.decodeEvents(data)
    }

    private func readEvents(maximumByteCount: Int) throws -> [RuntimeMemoryStoredEvent] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let handle = try FileHandle(forReadingFrom: fileURL)
        defer { try? handle.close() }
        let data = try handle.read(upToCount: maximumByteCount + 1) ?? Data()
        guard data.count <= maximumByteCount else {
            throw RuntimeMemoryStoreError.duplicateSuggestionResourceLimitExceeded
        }
        return try Self.decodeEvents(data)
    }

    private static func decodeEvents(_ data: Data) throws -> [RuntimeMemoryStoredEvent] {
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
                let lineData = Data(line.utf8)
                try StrictJSONDocumentValidator.validate(lineData)
                let event = try decoder.decode(RuntimeMemoryStoredEvent.self, from: lineData)
                if event.kind == .generatedMemorySummaryDraft {
                    let promptBindingFields = try decoder.decode(
                        RuntimeMemoryPromptSkillBindingFieldPresence.self,
                        from: lineData
                    )
                    guard promptBindingFields.hasPromptSkillID
                            == promptBindingFields.hasPromptSkillRevision else {
                        throw RuntimeMemoryStoreError.corruptEventLog(
                            line: index + 1,
                            reason: "generated memory summary draft is invalid"
                        )
                    }
                }
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
        case .generatedMemorySummaryDraft:
            guard let content = event.content?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !content.isEmpty,
                  content.count <= RuntimeGeneratedMemorySummaryDraft.maxContentCharacters,
                  event.summaryMethod == RuntimeGeneratedMemorySummaryDraft.summaryMethod else {
                throw RuntimeMemoryStoreError.corruptEventLog(
                    line: line,
                    reason: "generated memory summary draft is invalid"
                )
            }
            guard let generatedDraft = event.generatedMemorySummaryDraft else {
                throw RuntimeMemoryStoreError.corruptEventLog(
                    line: line,
                    reason: "generated memory summary draft is invalid"
                )
            }
            do {
                try validateGeneratedMemorySummaryDraft(generatedDraft)
            } catch {
                throw RuntimeMemoryStoreError.corruptEventLog(
                    line: line,
                    reason: "generated memory summary draft is invalid"
                )
            }
        }
    }

    private static func validateGeneratedMemorySummaryDraft(
        _ draft: RuntimeGeneratedMemorySummaryDraft
    ) throws {
        guard !draft.draftID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw RuntimeMemoryStoreError.missingID
        }
        guard !draft.sessionID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              draft.sourceMessageCount > 0,
              !draft.modelID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              draft.promptSkillBinding.identifier
                == RuntimePromptSkillRegistry.memorySummaryDraftSkillID else {
            throw RuntimeMemoryStoreError.missingID
        }
        if let providerQualifiedModelID = draft.providerQualifiedModelID {
            guard let resolved = ModelProvider.splitQualifiedModelID(providerQualifiedModelID),
                  !resolved.modelID.isEmpty,
                  ModelProvider.splitQualifiedModelID(resolved.modelID) == nil,
                  resolved.provider.qualifiedModelID(resolved.modelID)
                    == providerQualifiedModelID else {
                throw RuntimeMemoryStoreError.missingID
            }
        }
        let cleanContent = draft.content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanContent.isEmpty else {
            throw RuntimeMemoryStoreError.emptyContent
        }
        guard cleanContent.count <= RuntimeGeneratedMemorySummaryDraft.maxContentCharacters else {
            throw RuntimeMemoryStoreError.emptyContent
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
            case .generatedMemorySummaryDraft:
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

    private static func generatedMemorySummaryDrafts(
        from events: [RuntimeMemoryStoredEvent]
    ) -> [RuntimeGeneratedMemorySummaryDraft] {
        var draftsByID: [String: RuntimeGeneratedMemorySummaryDraft] = [:]
        for event in events where event.kind == .generatedMemorySummaryDraft {
            guard let draft = event.generatedMemorySummaryDraft else { continue }
            draftsByID[draft.draftID] = draft
        }
        return draftsByID.values.sorted {
            if $0.generatedAt == $1.generatedAt {
                return $0.draftID < $1.draftID
            }
            return $0.generatedAt > $1.generatedAt
        }
    }
}

private enum RuntimeMemoryStoredEventKind: String, Codable {
    case upsert
    case delete
    case dismissMemorySummaryDraft = "dismiss_memory_summary_draft"
    case generatedMemorySummaryDraft = "generated_memory_summary_draft"
}

private struct RuntimeMemoryPromptSkillBindingFieldPresence: Decodable {
    let hasPromptSkillID: Bool
    let hasPromptSkillRevision: Bool

    private enum CodingKeys: String, CodingKey {
        case promptSkillID = "prompt_skill_id"
        case promptSkillRevision = "prompt_skill_revision"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        hasPromptSkillID = container.contains(.promptSkillID)
        hasPromptSkillRevision = container.contains(.promptSkillRevision)
        if hasPromptSkillID {
            _ = try container.decode(String.self, forKey: .promptSkillID)
        }
        if hasPromptSkillRevision {
            _ = try container.decode(String.self, forKey: .promptSkillRevision)
        }
    }
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
    var sessionID: String?
    var sourceMessageCount: Int?
    var summaryMethod: String?
    var modelID: String?
    var providerQualifiedModelID: String?
    var promptSkillID: String?
    var promptSkillRevision: String?
    var generatedAt: Date?

    var generatedMemorySummaryDraft: RuntimeGeneratedMemorySummaryDraft? {
        guard kind == .generatedMemorySummaryDraft,
              let content,
              let sessionID,
              let sourceMessageCount,
              summaryMethod == RuntimeGeneratedMemorySummaryDraft.summaryMethod,
              let modelID,
              let generatedAt else {
            return nil
        }
        let promptSkillBinding: RuntimePromptSkillBinding
        switch (promptSkillID, promptSkillRevision) {
        case (nil, nil):
            promptSkillBinding = RuntimePromptSkillRegistry.originalMemorySummaryDraftBinding
        case (.some(let identifier), .some(let revision)):
            guard identifier == RuntimePromptSkillRegistry.memorySummaryDraftSkillID,
                  let binding = try? RuntimePromptSkillBinding(
                    identifier: identifier,
                    revision: revision
                  ) else {
                return nil
            }
            promptSkillBinding = binding
        case (.some, nil), (nil, .some):
            return nil
        }
        return RuntimeGeneratedMemorySummaryDraft(
            draftID: id,
            sessionID: sessionID,
            sourceMessageCount: sourceMessageCount,
            content: content,
            modelID: modelID,
            providerQualifiedModelID: providerQualifiedModelID,
            promptSkillBinding: promptSkillBinding,
            generatedAt: generatedAt
        )
    }

    enum CodingKeys: String, CodingKey {
        case kind
        case id
        case timestamp
        case content
        case enabled
        case createdAt = "created_at"
        case ownerDeviceID = "owner_device_id"
        case source
        case sessionID = "session_id"
        case sourceMessageCount = "source_message_count"
        case summaryMethod = "summary_method"
        case modelID = "model_id"
        case providerQualifiedModelID = "provider_qualified_model_id"
        case promptSkillID = "prompt_skill_id"
        case promptSkillRevision = "prompt_skill_revision"
        case generatedAt = "generated_at"
    }
}

private struct RuntimeMemorySearchQuery {
    let terms: [String]

    init?(_ rawQuery: String?) {
        let normalizedTerms = rawQuery?
            .normalizedRuntimeSearchText
            .split(whereSeparator: { $0.isWhitespace })
            .map(String.init)
            ?? []
        var terms: [String] = []
        for term in normalizedTerms where !terms.contains(term) {
            terms.append(term)
        }
        guard !terms.isEmpty else { return nil }
        self.terms = terms
    }
}

private struct RuntimeMemorySearchField {
    var name: String
    var text: String
    var weight: Int
    var order: Int
}

private struct RuntimeMemorySearchMatch {
    var score: Int
    var snippet: String
    var matchedFields: [String]
}

private extension RuntimeMemoryEntry {
    func runtimeMemorySearchMatch(_ query: RuntimeMemorySearchQuery) -> RuntimeMemorySearchMatch? {
        let fields = runtimeMemorySearchFields()
        var matchedTerms = Set<String>()
        var matchedFields: [String] = []
        var termScores: [String: Int] = [:]
        var snippetCandidates: [(field: RuntimeMemorySearchField, termCount: Int)] = []

        for field in fields {
            let normalizedText = field.text.normalizedRuntimeSearchText
            guard !normalizedText.isEmpty else { continue }
            let fieldTerms = query.terms.filter { normalizedText.contains($0) }
            guard !fieldTerms.isEmpty else { continue }

            matchedTerms.formUnion(fieldTerms)
            if !matchedFields.contains(field.name) {
                matchedFields.append(field.name)
            }
            for term in fieldTerms {
                termScores[term] = max(termScores[term] ?? 0, field.weight)
            }
            snippetCandidates.append((field, fieldTerms.count))
        }

        guard query.terms.allSatisfy({ matchedTerms.contains($0) }) else { return nil }
        let score = termScores.values.reduce(0, +)
            + (snippetCandidates.contains { $0.termCount == query.terms.count } ? 25 : 0)
            + matchedFields.count

        let bestSnippetField = snippetCandidates
            .sorted { lhs, rhs in
                if lhs.termCount != rhs.termCount {
                    return lhs.termCount > rhs.termCount
                }
                if lhs.field.weight != rhs.field.weight {
                    return lhs.field.weight > rhs.field.weight
                }
                return lhs.field.order < rhs.field.order
            }
            .first?
            .field
        let snippet = bestSnippetField
            .map { Self.searchSnippet(from: $0.text, terms: query.terms) }
            ?? content

        return RuntimeMemorySearchMatch(
            score: score,
            snippet: snippet,
            matchedFields: matchedFields
        )
    }

    private func runtimeMemorySearchFields() -> [RuntimeMemorySearchField] {
        var fields: [RuntimeMemorySearchField] = []
        func append(_ name: String, _ text: String?, weight: Int) {
            guard let text = text?.runtimeSearchSnippetText, !text.isEmpty else { return }
            fields.append(RuntimeMemorySearchField(name: name, text: text, weight: weight, order: fields.count))
        }
        append("content", content, weight: 100)
        if let source {
            append("source_title", source.session.title, weight: 60)
            append("source_range", source.sourceRange, weight: 20)
            for pointer in source.sourcePointers {
                append("source_excerpt", pointer.excerpt, weight: 40)
            }
        }
        return fields
    }

    private static func searchSnippet(from text: String, terms: [String], maxLength: Int = 160) -> String {
        let cleanText = text.runtimeSearchSnippetText
        guard cleanText.count > maxLength else { return cleanText }
        let normalized = cleanText.normalizedRuntimeSearchText
        let firstMatch = terms
            .compactMap { normalized.range(of: $0)?.lowerBound }
            .map { normalized.distance(from: normalized.startIndex, to: $0) }
            .min() ?? 0
        let halfWindow = maxLength / 2
        let startOffset = max(0, firstMatch - halfWindow)
        let endOffset = min(cleanText.count, startOffset + maxLength)
        let start = cleanText.index(cleanText.startIndex, offsetBy: startOffset)
        let end = cleanText.index(cleanText.startIndex, offsetBy: endOffset)
        let snippet = cleanText[start..<end].trimmingCharacters(in: .whitespacesAndNewlines)
        let leading = startOffset > 0 ? "..." : ""
        let trailing = endOffset < cleanText.count ? "..." : ""
        return leading + snippet + trailing
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
