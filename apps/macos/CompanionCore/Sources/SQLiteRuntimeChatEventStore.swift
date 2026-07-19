import Foundation
import OllamaBackend
import SQLite3

public struct RuntimeChatDeletedSessionPruneResult: Equatable, Sendable {
    public var prunedSessionIDs: [String]
    public var prunedEventCount: Int

    public var prunedSessionCount: Int {
        prunedSessionIDs.count
    }

    public init(prunedSessionIDs: [String], prunedEventCount: Int) {
        self.prunedSessionIDs = prunedSessionIDs
        self.prunedEventCount = prunedEventCount
    }
}

struct SQLiteRuntimeChatEventStoreAppendInstrumentation: Sendable {
    var didDecodeStoredEvent: @Sendable () -> Void
    var didRunFullHistoryRepair: @Sendable () -> Void
    var didInsertSearchDocument: @Sendable () -> Void

    init(
        didDecodeStoredEvent: @escaping @Sendable () -> Void = {},
        didRunFullHistoryRepair: @escaping @Sendable () -> Void = {},
        didInsertSearchDocument: @escaping @Sendable () -> Void = {}
    ) {
        self.didDecodeStoredEvent = didDecodeStoredEvent
        self.didRunFullHistoryRepair = didRunFullHistoryRepair
        self.didInsertSearchDocument = didInsertSearchDocument
    }
}

public final class SQLiteRuntimeChatEventStore: RuntimeChatEventStore, @unchecked Sendable {
    private let databaseURL: URL
    private let legacyJSONLFileURL: URL?
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder
    private let semanticEmbeddingRowLimitPerOwnerModel: Int
    private let legacyJSONLCompactionWillReplace: (() -> Void)?
    private let calibrationReportStoreLimits: RuntimeChatCompactionCalibrationStoreLimits
    private let appendInstrumentation: SQLiteRuntimeChatEventStoreAppendInstrumentation?
    private let lock = NSLock()

    public convenience init(
        databaseURL: URL = SQLiteRuntimeChatEventStore.defaultDatabaseURL(),
        legacyJSONLFileURL: URL? = nil,
        semanticEmbeddingRowLimitPerOwnerModel: Int = 10_000
    ) {
        self.init(
            databaseURL: databaseURL,
            legacyJSONLFileURL: legacyJSONLFileURL,
            semanticEmbeddingRowLimitPerOwnerModel: semanticEmbeddingRowLimitPerOwnerModel,
            legacyJSONLCompactionWillReplace: nil,
            appendInstrumentation: nil
        )
    }

    convenience init(
        databaseURL: URL,
        legacyJSONLFileURL: URL,
        legacyJSONLCompactionWillReplace: @escaping () -> Void
    ) {
        self.init(
            databaseURL: databaseURL,
            legacyJSONLFileURL: legacyJSONLFileURL,
            semanticEmbeddingRowLimitPerOwnerModel: 10_000,
            legacyJSONLCompactionWillReplace: legacyJSONLCompactionWillReplace,
            appendInstrumentation: nil
        )
    }

    convenience init(
        databaseURL: URL,
        calibrationReportStoreLimits: RuntimeChatCompactionCalibrationStoreLimits
    ) {
        self.init(
            databaseURL: databaseURL,
            legacyJSONLFileURL: nil,
            semanticEmbeddingRowLimitPerOwnerModel: 10_000,
            legacyJSONLCompactionWillReplace: nil,
            calibrationReportStoreLimits: calibrationReportStoreLimits,
            appendInstrumentation: nil
        )
    }

    convenience init(
        databaseURL: URL,
        appendInstrumentation: SQLiteRuntimeChatEventStoreAppendInstrumentation
    ) {
        self.init(
            databaseURL: databaseURL,
            legacyJSONLFileURL: nil,
            semanticEmbeddingRowLimitPerOwnerModel: 10_000,
            legacyJSONLCompactionWillReplace: nil,
            appendInstrumentation: appendInstrumentation
        )
    }

    private init(
        databaseURL: URL,
        legacyJSONLFileURL: URL?,
        semanticEmbeddingRowLimitPerOwnerModel: Int,
        legacyJSONLCompactionWillReplace: (() -> Void)?,
        calibrationReportStoreLimits: RuntimeChatCompactionCalibrationStoreLimits = .production,
        appendInstrumentation: SQLiteRuntimeChatEventStoreAppendInstrumentation?
    ) {
        self.databaseURL = databaseURL
        self.legacyJSONLFileURL = legacyJSONLFileURL
        self.semanticEmbeddingRowLimitPerOwnerModel = max(1, semanticEmbeddingRowLimitPerOwnerModel)
        self.legacyJSONLCompactionWillReplace = legacyJSONLCompactionWillReplace
        self.calibrationReportStoreLimits = calibrationReportStoreLimits
        self.appendInstrumentation = appendInstrumentation
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
        self.encoder.outputFormatting = [.sortedKeys]
        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601
    }

    public func append(_ event: RuntimeChatStoredEvent) throws {
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    try appendUnlocked(event, database: database)
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func chatCompactionCalibrationReport() throws -> RuntimeChatCompactionCalibrationReport {
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN")
                do {
                    let report = RuntimeChatCompactionCalibrationReport.build(
                        from: try calibrationReportEventsUnlocked(database)
                    )
                    try Self.execute(database, "COMMIT")
                    return report
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func listSessions(
        ownerDeviceID: String?,
        limit: Int = 100,
        includeArchived: Bool = false
    ) throws -> [RuntimeChatStoredSession] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try JSONLRuntimeChatEventStore.sessions(
                    from: readEventsUnlocked(database, matchingOwnerDeviceID: ownerDeviceID.sqliteNormalizedOwnerDeviceID),
                    limit: limit,
                    includeArchived: includeArchived
                )
            }
        }
    }

    public func listSessionSummaries(
        ownerDeviceID: String?,
        sessionIDs: [String],
        includeArchived: Bool
    ) throws -> [RuntimeChatStoredSession] {
        let validatedSessionIDs = try validatedTargetedSessionSummaryIDs(sessionIDs)
        guard !validatedSessionIDs.isEmpty else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try JSONLRuntimeChatEventStore.sessions(
                    from: readEventsUnlocked(
                        database,
                        matchingOwnerDeviceID: ownerDeviceID.sqliteNormalizedOwnerDeviceID,
                        sessionIDs: validatedSessionIDs
                    ),
                    limit: validatedSessionIDs.count,
                    includeArchived: includeArchived
                )
            }
        }
    }

    public func listSessions(
        ownerDeviceID: String?,
        limit: Int,
        includeArchived: Bool,
        query: String?,
        embeddingModelID: String?
    ) throws -> [RuntimeChatStoredSession] {
        guard let searchQuery = RuntimeChatSessionSearchQuery(query) else {
            return try listSessions(ownerDeviceID: ownerDeviceID, limit: limit, includeArchived: includeArchived)
        }
        guard limit > 0 else { return [] }

        return try lock.withLock {
            try withDatabase { database in
                try ensureIncrementalAppendStateUnlocked(database)
                let scopedOwnerDeviceID = ownerDeviceID.sqliteNormalizedOwnerDeviceID
                let candidateIDs = try searchCandidateSessionIDsUnlocked(
                    database,
                    ownerDeviceID: scopedOwnerDeviceID,
                    query: searchQuery
                )
                guard !candidateIDs.isEmpty else { return [] }

                let candidateEvents = try readEventsUnlocked(
                    database,
                    matchingOwnerDeviceID: scopedOwnerDeviceID,
                    sessionIDs: candidateIDs
                )
                let eventsBySessionID = Dictionary(grouping: candidateEvents, by: \RuntimeChatStoredEvent.sessionID)
                let candidates = try JSONLRuntimeChatEventStore.sessions(
                    from: candidateEvents,
                    limit: Int.max,
                    includeArchived: includeArchived
                )
                var matches: [(session: RuntimeChatStoredSession, match: RuntimeChatSessionSearchMatch)] = []
                for session in candidates {
                    let sessionEvents = eventsBySessionID[session.sessionID] ?? []
                    let messages = JSONLRuntimeChatEventStore.messages(
                        from: sessionEvents,
                        sessionID: session.sessionID,
                        limit: Int.max
                    )
                    if let match = session.runtimeSearchMatch(searchQuery, messages: messages) {
                        matches.append((session, match))
                    }
                }
                return matches
                    .sorted { lhs, rhs in
                        if lhs.match.score != rhs.match.score {
                            return lhs.match.score > rhs.match.score
                        }
                        if lhs.session.lastActivityAt != rhs.session.lastActivityAt {
                            return lhs.session.lastActivityAt > rhs.session.lastActivityAt
                        }
                        return lhs.session.sessionID < rhs.session.sessionID
                    }
                    .limited(to: limit)
                    .enumerated()
                    .map { offset, result in
                        var session = result.session
                        session.search = RuntimeChatStoredSessionSearch(
                            rank: offset + 1,
                            snippet: result.match.snippet,
                            matchedFields: result.match.matchedFields
                        )
                        return session
                    }
            }
        }
    }

    public func pruneDeletedSessions(
        ownerDeviceID: String?,
        deletedBefore cutoff: Date,
        limit: Int = Int.max
    ) throws -> RuntimeChatDeletedSessionPruneResult {
        try pruneDeletedSessions(
            scope: .owner(ownerDeviceID.sqliteNormalizedOwnerDeviceID),
            deletedBefore: cutoff,
            limit: limit,
            legacyCompactionTiming: .immediate
        )
    }

    public func pruneDeletedSessions(
        deletedBefore cutoff: Date,
        limit: Int = Int.max
    ) throws -> RuntimeChatDeletedSessionPruneResult {
        try pruneDeletedSessions(
            scope: .allOwners,
            deletedBefore: cutoff,
            limit: limit,
            legacyCompactionTiming: .immediate
        )
    }

    func pruneDeletedSessionsBatch(
        ownerDeviceID: String?,
        deletedBefore cutoff: Date,
        limit: Int
    ) throws -> RuntimeChatDeletedSessionPruneResult {
        try pruneDeletedSessions(
            scope: .owner(ownerDeviceID.sqliteNormalizedOwnerDeviceID),
            deletedBefore: cutoff,
            limit: limit,
            legacyCompactionTiming: .whenBatchDrained
        )
    }

    func pruneDeletedSessionsBatch(
        deletedBefore cutoff: Date,
        limit: Int
    ) throws -> RuntimeChatDeletedSessionPruneResult {
        try pruneDeletedSessions(
            scope: .allOwners,
            deletedBefore: cutoff,
            limit: limit,
            legacyCompactionTiming: .whenBatchDrained
        )
    }

    private func pruneDeletedSessions(
        scope: RuntimeChatRetentionScope,
        deletedBefore cutoff: Date,
        limit: Int,
        legacyCompactionTiming: RuntimeChatLegacyCompactionTiming
    ) throws -> RuntimeChatDeletedSessionPruneResult {
        guard limit > 0 else {
            return RuntimeChatDeletedSessionPruneResult(prunedSessionIDs: [], prunedEventCount: 0)
        }
        return try lock.withLock {
            try withDatabase(
                deferLegacyJSONLCompaction: legacyCompactionTiming == .whenBatchDrained
            ) { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                let result: RuntimeChatDeletedSessionPruneResult
                do {
                    result = try pruneDeletedSessionsUnlocked(
                        database,
                        scope: scope,
                        deletedBefore: cutoff,
                        limit: limit
                    )
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
                if legacyCompactionTiming == .immediate || result.prunedSessionCount < limit {
                    try compactLegacyJSONLIfNeeded(database)
                }
                return result
            }
        }
    }

    public func listAllSessions(
        limit: Int = 100,
        includeArchived: Bool = false
    ) throws -> [RuntimeChatStoredSession] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try JSONLRuntimeChatEventStore.sessions(
                    from: readEventsUnlocked(database),
                    limit: limit,
                    includeArchived: includeArchived
                )
            }
        }
    }

    public func listMessages(
        ownerDeviceID: String?,
        sessionID: String,
        limit: Int = 200
    ) throws -> [RuntimeChatStoredMessage] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                JSONLRuntimeChatEventStore.messages(
                    from: try readEventsUnlocked(database, matchingOwnerDeviceID: ownerDeviceID.sqliteNormalizedOwnerDeviceID),
                    sessionID: sessionID,
                    limit: limit
                )
            }
        }
    }

    public func performIfLongInactivityMemorySummarySourceCurrent(
        ownerDeviceID: String?,
        expectedDraft: RuntimeLongInactivityMemorySummarizationDraft,
        policy: RuntimeLongInactivityMemorySummarizationPolicy,
        operation: @Sendable () throws -> Void
    ) throws -> Bool {
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let events = try readEventsUnlocked(
                        database,
                        matchingOwnerDeviceID: ownerDeviceID.sqliteNormalizedOwnerDeviceID
                    )
                    let sessions = try JSONLRuntimeChatEventStore.sessions(
                        from: events,
                        limit: Int.max,
                        includeArchived: false
                    )
                    guard let candidate = policy.candidates(from: sessions, now: Date())
                            .first(where: {
                                $0.sessionID == expectedDraft.candidate.sessionID
                            }),
                          let currentDraft = policy.draft(
                            for: candidate,
                            messages: JSONLRuntimeChatEventStore.messages(
                                from: events,
                                sessionID: candidate.sessionID,
                                limit: Int.max
                            )
                          ),
                          currentDraft.hasSameMemorySummarySource(as: expectedDraft) else {
                        try Self.execute(database, "ROLLBACK")
                        return false
                    }
                    try operation()
                    try Self.execute(database, "COMMIT")
                    return true
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func listSemanticSearchSources(
        ownerDeviceID: String?,
        sessionLimit: Int,
        messageLimit: Int,
        includeArchived: Bool
    ) throws -> [RuntimeChatSemanticSearchSource] {
        guard sessionLimit > 0, messageLimit > 0 else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN DEFERRED")
                do {
                    let scopedOwnerDeviceID = ownerDeviceID.sqliteNormalizedOwnerDeviceID
                    let events = try readEventsUnlocked(
                        database,
                        matchingOwnerDeviceID: scopedOwnerDeviceID
                    )
                    let sources = try JSONLRuntimeChatEventStore.sessions(
                        from: events,
                        limit: sessionLimit,
                        includeArchived: includeArchived
                    ).map { session in
                        RuntimeChatSemanticSearchSource(
                            session: session,
                            messages: JSONLRuntimeChatEventStore.messages(
                                from: events,
                                sessionID: session.sessionID,
                                limit: messageLimit
                            ),
                            sourceRevision: try sessionRevisionUnlocked(
                                database,
                                ownerDeviceID: scopedOwnerDeviceID,
                                sessionID: session.sessionID
                            )
                        )
                    }
                    try Self.execute(database, "COMMIT")
                    return sources
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func cachedSemanticEmbeddings(
        for keys: [RuntimeChatSemanticEmbeddingKey]
    ) throws -> [RuntimeChatSemanticEmbeddingRecord] {
        guard !keys.isEmpty else { return [] }
        let uniqueKeys = keys.reduce(into: [RuntimeChatSemanticEmbeddingKey]()) { result, key in
            if !result.contains(key) { result.append(key) }
        }
        try uniqueKeys.forEach(Self.validateSemanticEmbeddingKey)
        return try lock.withLock {
            try withDatabase { database in
                var records: [RuntimeChatSemanticEmbeddingRecord] = []
                for key in uniqueKeys {
                    if let record = try semanticEmbeddingUnlocked(for: key, database: database) {
                        records.append(record)
                    }
                }
                return records
            }
        }
    }

    public func upsertSemanticEmbeddings(
        _ records: [RuntimeChatSemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws {
        guard !records.isEmpty else { return }
        try records.forEach(Self.validateSemanticEmbeddingRecord)
        try lock.withLock {
            guard shouldCommit() else { return }
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    var scopes = Set<RuntimeChatSemanticEmbeddingScope>()
                    for record in records {
                        if let sourceRevision = record.sourceRevision {
                            let currentRevision = try sessionRevisionUnlocked(
                                database,
                                ownerDeviceID: record.key.ownerDeviceID.sqliteNormalizedOwnerDeviceID,
                                sessionID: record.key.sessionID
                            )
                            guard currentRevision == sourceRevision else { continue }
                        }
                        try upsertSemanticEmbeddingUnlocked(record, database: database)
                        scopes.insert(RuntimeChatSemanticEmbeddingScope(key: record.key))
                    }
                    for scope in scopes {
                        try enforceSemanticEmbeddingRowLimitUnlocked(scope, database: database)
                    }
                    guard shouldCommit() else {
                        try Self.execute(database, "ROLLBACK")
                        return
                    }
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func listAllMessages(
        sessionID: String,
        limit: Int = 200
    ) throws -> [RuntimeChatStoredMessage] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                let events = try readEventsUnlocked(database)
                let keys = JSONLRuntimeChatEventStore.sessionProjectionKeys(
                    from: events,
                    sessionID: sessionID
                )
                guard keys.count <= 1 else {
                    throw RuntimeChatHostWideProjectionError.ambiguousSessionID(sessionID)
                }
                guard let key = keys.first else { return [] }
                return JSONLRuntimeChatEventStore.messages(
                    from: events,
                    key: key,
                    limit: limit
                )
            }
        }
    }

    public func resolveSourceAttribution(
        ownerDeviceID: String?,
        sessionID: String,
        assistantMessageID: String,
        sourceIndex: Int
    ) throws -> RuntimeChatResolvedSourceAttribution? {
        try lock.withLock {
            try withDatabase { database in
                JSONLRuntimeChatEventStore.resolvedSourceAttribution(
                    from: try readEventsUnlocked(
                        database,
                        matchingOwnerDeviceID: ownerDeviceID.sqliteNormalizedOwnerDeviceID
                    ),
                    sessionID: sessionID,
                    assistantMessageID: assistantMessageID,
                    sourceIndex: sourceIndex
                )
            }
        }
    }

    public func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date = Date()
    ) throws -> RuntimeChatSessionMutationResult {
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let cleanSessionID = sessionID.trimmingCharacters(in: .whitespacesAndNewlines)
                    let scopedOwnerDeviceID = ownerDeviceID.sqliteNormalizedOwnerDeviceID
                    let events = try readEventsUnlocked(database, matchingOwnerDeviceID: scopedOwnerDeviceID)
                    let sessionEvents = events.filter { $0.sessionID == cleanSessionID }
                    let visibleSession = try JSONLRuntimeChatEventStore.sessions(
                        from: sessionEvents,
                        limit: 1,
                        includeArchived: true
                    ).first
                    guard !cleanSessionID.isEmpty,
                          !sessionEvents.isEmpty,
                          let visibleSession else {
                        throw RuntimeChatEventStoreError.sessionNotFound(sessionID)
                    }
                    if mutation == .delete, visibleSession.status != "archived" {
                        throw RuntimeChatEventStoreError.sessionMustBeArchivedBeforeDelete(cleanSessionID)
                    }

                    try appendUnlocked(RuntimeChatStoredEvent(
                        timestamp: timestamp,
                        kind: mutation.eventKind,
                        requestID: requestID,
                        sessionID: cleanSessionID,
                        model: JSONLRuntimeChatEventStore.latestModel(from: sessionEvents),
                        ownerDeviceID: scopedOwnerDeviceID
                    ), database: database)
                    let result = RuntimeChatSessionMutationResult(
                        sessionID: cleanSessionID,
                        mutation: mutation,
                        timestamp: timestamp
                    )
                    try Self.execute(database, "COMMIT")
                    return result
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func mutateSessions(
        ownerDeviceID: String?,
        scope: RuntimeChatSessionBulkScope,
        limit: Int,
        requestID: String,
        timestamp: Date = Date(),
        beforeCommit: @Sendable ([String]) throws -> Void = { _ in }
    ) throws -> RuntimeChatSessionBulkMutationResult {
        let boundedLimit = max(1, min(limit, 200))
        return try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let scopedOwnerDeviceID = ownerDeviceID.sqliteNormalizedOwnerDeviceID
                    let ownerEvents = try readEventsUnlocked(
                        database,
                        matchingOwnerDeviceID: scopedOwnerDeviceID
                    )
                    let targets = try JSONLRuntimeChatEventStore.sessions(
                        from: ownerEvents,
                        limit: Int.max,
                        includeArchived: true
                    ).filter { session in
                        switch scope {
                        case .allActive: session.status == "active"
                        case .allArchived: session.status == "archived"
                        }
                    }
                    let selected = Array(targets.prefix(boundedLimit))
                    let selectedIDs = selected.map(\.sessionID)
                    try beforeCommit(selectedIDs)
                    let eventsBySessionID = Dictionary(grouping: ownerEvents, by: \.sessionID)
                    let mutationEvents = selected.map { session in
                        RuntimeChatStoredEvent(
                            timestamp: timestamp,
                            kind: scope.mutation.eventKind,
                            requestID: requestID,
                            sessionID: session.sessionID,
                            model: JSONLRuntimeChatEventStore.latestModel(
                                from: eventsBySessionID[session.sessionID] ?? []
                            ),
                            ownerDeviceID: scopedOwnerDeviceID
                        )
                    }
                    try appendBatchUnlocked(mutationEvents, database: database)
                    let result = RuntimeChatSessionBulkMutationResult(
                        scope: scope,
                        affectedSessionIDs: selectedIDs,
                        remainingCount: targets.count - selected.count,
                        timestamp: timestamp
                    )
                    try Self.execute(database, "COMMIT")
                    return result
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public static func defaultDatabaseURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-chat-events.sqlite", isDirectory: false)
    }

    private func appendUnlocked(_ event: RuntimeChatStoredEvent, database: OpaquePointer) throws {
        let sanitized = event.sanitizedForStorage()
        try JSONLRuntimeChatEventStore.validateStoredEvent(sanitized, line: 0)
        try repairIncrementalAppendStateIfNeededUnlocked(database)
        try validateCompactionResolutionAppendUnlocked(sanitized, database: database)
        if try eventExistsUnlocked(database, eventID: sanitized.id) {
            throw SQLiteRuntimeChatEventStoreError("Runtime chat SQLite event already exists: \(sanitized.id)")
        }
        guard let sequence = try insertEventUnlocked(
            sanitized,
            database: database,
            skipExisting: false
        ) else {
            throw SQLiteRuntimeChatEventStoreError("Runtime chat SQLite event was not inserted: \(sanitized.id)")
        }
        try insertIncrementalSearchDocumentUnlocked(
            database,
            sequence: sequence,
            event: sanitized
        )
        try deleteSemanticEmbeddingsUnlocked(
            database,
            ownerDeviceID: sanitized.ownerDeviceID.sqliteNormalizedOwnerDeviceID,
            sessionID: sanitized.sessionID
        )
        try markIncrementalAppendStateValidatedUnlocked(database)
    }

    private func appendBatchUnlocked(
        _ events: [RuntimeChatStoredEvent],
        database: OpaquePointer
    ) throws {
        guard !events.isEmpty else { return }
        let sanitizedEvents = events.map { $0.sanitizedForStorage() }
        for event in sanitizedEvents {
            try JSONLRuntimeChatEventStore.validateStoredEvent(event, line: 0)
        }
        try repairIncrementalAppendStateIfNeededUnlocked(database)
        for event in sanitizedEvents {
            try validateCompactionResolutionAppendUnlocked(event, database: database)
            if try eventExistsUnlocked(database, eventID: event.id) {
                throw SQLiteRuntimeChatEventStoreError(
                    "Runtime chat SQLite event already exists: \(event.id)"
                )
            }
            guard let sequence = try insertEventUnlocked(
                event,
                database: database,
                skipExisting: false
            ) else {
                throw SQLiteRuntimeChatEventStoreError(
                    "Runtime chat SQLite event was not inserted: \(event.id)"
                )
            }
            try insertIncrementalSearchDocumentUnlocked(
                database,
                sequence: sequence,
                event: event
            )
            try deleteSemanticEmbeddingsUnlocked(
                database,
                ownerDeviceID: event.ownerDeviceID.sqliteNormalizedOwnerDeviceID,
                sessionID: event.sessionID
            )
        }
        try markIncrementalAppendStateValidatedUnlocked(database)
    }

    private func validateCompactionResolutionAppendUnlocked(
        _ event: RuntimeChatStoredEvent,
        database: OpaquePointer
    ) throws {
        guard event.compactionResolution != nil else { return }
        let key = RuntimeChatCompactionResolutionBindingKey(event: event)
        guard try !compactionTerminalBindingExistsUnlocked(database, key: key) else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: 0,
                reason: "chat compaction binding has duplicate terminal resolution"
            )
        }

        var validationEvents: [(line: Int, event: RuntimeChatStoredEvent)] = []
        if let request = try latestRequestBindingUnlocked(
            database,
            key: key,
            beforeSequence: Int64.max
        ) {
            validationEvents.append((line: Int(request.sequence), event: request.event))
        }
        validationEvents.append((line: 0, event: event))
        try JSONLRuntimeChatEventStore.validateCompactionResolutionBindings(validationEvents)
    }

    private func compactionTerminalBindingExistsUnlocked(
        _ database: OpaquePointer,
        key: RuntimeChatCompactionResolutionBindingKey
    ) throws -> Bool {
        let statement = try Self.prepare(
            database,
            """
            SELECT 1
            FROM runtime_chat_events
            WHERE kind IN ('done', 'cancelled', 'error')
              AND COALESCE(NULLIF(TRIM(owner_device_id), ''), '') = ?
              AND session_id = ?
              AND request_id = ?
              AND json_type(event_json, '$.compaction_resolution') IS NOT NULL
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(key.ownerDeviceID ?? "", to: statement, at: 1)
        try Self.bindText(key.sessionID, to: statement, at: 2)
        try Self.bindText(key.requestID, to: statement, at: 3)
        let result = sqlite3_step(statement)
        if result == SQLITE_ROW { return true }
        if result == SQLITE_DONE { return false }
        throw Self.failure(database, "Could not check runtime chat compaction terminal binding.")
    }

    @discardableResult
    private func insertEventUnlocked(
        _ event: RuntimeChatStoredEvent,
        database: OpaquePointer,
        skipExisting: Bool
    ) throws -> Int64? {
        let ownerDeviceID = event.ownerDeviceID.sqliteNormalizedOwnerDeviceID
        if try retentionTombstoneExistsUnlocked(
            database,
            ownerDeviceID: ownerDeviceID,
            sessionID: event.sessionID
        ) {
            if skipExisting { return nil }
            throw SQLiteRuntimeChatEventStoreError(
                "Runtime chat SQLite session was pruned by retention: \(event.sessionID)"
            )
        }
        if skipExisting, try eventExistsUnlocked(database, eventID: event.id) {
            return nil
        }
        let data = try encoder.encode(event)
        guard let eventJSON = String(data: data, encoding: .utf8) else {
            throw SQLiteRuntimeChatEventStoreError("Could not encode runtime chat event JSON.")
        }

        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_chat_events(
                event_id,
                timestamp,
                kind,
                request_id,
                session_id,
                owner_device_id,
                model,
                event_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(event.id, to: statement, at: 1)
        try Self.bindText(Self.timestampString(from: event.timestamp), to: statement, at: 2)
        try Self.bindText(event.kind.rawValue, to: statement, at: 3)
        try Self.bindText(event.requestID, to: statement, at: 4)
        try Self.bindText(event.sessionID, to: statement, at: 5)
        try Self.bindOptionalText(ownerDeviceID, to: statement, at: 6)
        try Self.bindText(event.model, to: statement, at: 7)
        try Self.bindText(eventJSON, to: statement, at: 8)
        try Self.stepDone(statement, database: database)
        return sqlite3_last_insert_rowid(database)
    }

    private func readEventsUnlocked(_ database: OpaquePointer) throws -> [RuntimeChatStoredEvent] {
        try readEventsUnlocked(database, sql: "SELECT event_json FROM runtime_chat_events ORDER BY sequence ASC", bind: { _ in })
    }

    private func readEventsUnlocked(
        _ database: OpaquePointer,
        matchingOwnerDeviceID ownerDeviceID: String?
    ) throws -> [RuntimeChatStoredEvent] {
        if let ownerDeviceID {
            return try readEventsUnlocked(
                database,
                sql: "SELECT event_json FROM runtime_chat_events WHERE owner_device_id = ? ORDER BY sequence ASC",
                bind: { statement in try Self.bindText(ownerDeviceID, to: statement, at: 1) }
            )
        }
        return try readEventsUnlocked(
            database,
            sql: "SELECT event_json FROM runtime_chat_events WHERE owner_device_id IS NULL ORDER BY sequence ASC",
            bind: { _ in }
        )
    }

    private func readEventsUnlocked(
        _ database: OpaquePointer,
        matchingOwnerDeviceID ownerDeviceID: String?,
        sessionIDs: [String]
    ) throws -> [RuntimeChatStoredEvent] {
        let ownerParameterCount = ownerDeviceID == nil ? 0 : 1
        let variableLimit = Int(sqlite3_limit(database, SQLITE_LIMIT_VARIABLE_NUMBER, -1))
        let availableSessionIDParameters = variableLimit - ownerParameterCount
        guard availableSessionIDParameters > 0 else {
            throw SQLiteRuntimeChatEventStoreError(
                "Runtime chat SQLite variable limit cannot support targeted session summary lookup."
            )
        }
        let batchSize = min(500, availableSessionIDParameters)
        let ownerPredicate = ownerDeviceID == nil ? "owner_device_id IS NULL" : "owner_device_id = ?"
        var events: [RuntimeChatStoredEvent] = []
        for batchStart in stride(from: 0, to: sessionIDs.count, by: batchSize) {
            let batchEnd = min(batchStart + batchSize, sessionIDs.count)
            let batch = sessionIDs[batchStart..<batchEnd]
            let placeholders = Array(repeating: "?", count: batch.count).joined(separator: ", ")
            let batchEvents = try readEventsUnlocked(
                database,
                sql: """
                SELECT event_json
                FROM runtime_chat_events
                WHERE \(ownerPredicate)
                  AND session_id IN (\(placeholders))
                ORDER BY sequence ASC
                """,
                bind: { statement in
                    var bindIndex: Int32 = 1
                    if let ownerDeviceID {
                        try Self.bindText(ownerDeviceID, to: statement, at: bindIndex)
                        bindIndex += 1
                    }
                    for sessionID in batch {
                        try Self.bindText(sessionID, to: statement, at: bindIndex)
                        bindIndex += 1
                    }
                }
            )
            events.append(contentsOf: batchEvents)
        }
        return events
    }

    private func readEventsUnlocked(
        _ database: OpaquePointer,
        sql: String,
        bind: (OpaquePointer) throws -> Void
    ) throws -> [RuntimeChatStoredEvent] {
        let statement = try Self.prepare(database, sql)
        defer { sqlite3_finalize(statement) }
        try bind(statement)

        var events: [RuntimeChatStoredEvent] = []
        var line = 0
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime chat events.")
            }
            line += 1
            guard let text = sqlite3_column_text(statement, 0) else {
                throw RuntimeChatEventStoreError.corruptEventLog(line: line, reason: "stored event JSON is empty")
            }
            let data = Data(String(cString: text).utf8)
            do {
                appendInstrumentation?.didDecodeStoredEvent()
                let decoded = try decoder.decode(RuntimeChatStoredEvent.self, from: data)
                let event = JSONLRuntimeChatEventStore.projectingLegacyTitleForReplay(decoded)
                try JSONLRuntimeChatEventStore.validateStoredEvent(event, line: line)
                events.append(event)
            } catch {
                if let storeError = error as? RuntimeChatEventStoreError {
                    throw storeError
                }
                throw RuntimeChatEventStoreError.corruptEventLog(line: line, reason: "decode failed")
            }
        }
        try JSONLRuntimeChatEventStore.validateCompactionResolutionBindings(
            events.enumerated().map { (line: $0.offset + 1, event: $0.element) }
        )
        return events
    }

    private func calibrationReportEventsUnlocked(
        _ database: OpaquePointer
    ) throws -> [RuntimeChatStoredEvent] {
        let lowerBound = try calibrationReportDoneSequenceLowerBoundUnlocked(database)
        let candidateSQL: String
        // SQL bounds calibration-shaped candidates; the shared report predicate below applies
        // the sample cap only after full report eligibility is established.
        if lowerBound == nil {
            candidateSQL = """
                SELECT sequence,
                       event_json,
                       json_type(
                         event_json,
                         '$.compaction_resolution.provider_usage_calibration'
                       )
                FROM runtime_chat_events
                WHERE kind = 'done'
                  AND json_type(
                    event_json,
                    '$.compaction_resolution.provider_usage_calibration'
                  ) IS NOT NULL
                ORDER BY sequence DESC
                LIMIT ?
                """
        } else {
            candidateSQL = """
                SELECT sequence,
                       event_json,
                       json_type(
                         event_json,
                         '$.compaction_resolution.provider_usage_calibration'
                       )
                FROM runtime_chat_events
                WHERE kind = 'done'
                  AND sequence >= ?
                  AND json_type(
                    event_json,
                    '$.compaction_resolution.provider_usage_calibration'
                  ) IS NOT NULL
                ORDER BY sequence DESC
                LIMIT ?
                """
        }

        let statement = try Self.prepare(database, candidateSQL)
        defer { sqlite3_finalize(statement) }
        var bindIndex: Int32 = 1
        if let lowerBound {
            guard sqlite3_bind_int64(statement, bindIndex, lowerBound) == SQLITE_OK else {
                throw Self.failure(database, "Could not bind runtime chat calibration lower bound.")
            }
            bindIndex += 1
        }
        guard sqlite3_bind_int64(
            statement,
            bindIndex,
            Int64(calibrationReportStoreLimits.sqliteTerminalScanCeiling)
        ) == SQLITE_OK else {
            throw Self.failure(database, "Could not bind runtime chat calibration sample limit.")
        }

        var selected: [(sequence: Int64, event: RuntimeChatStoredEvent)] = []
        var selectedKeys: Set<RuntimeChatCompactionResolutionBindingKey> = []
        while true {
            if selected.count == RuntimeChatCompactionCalibrationReport.recentEligibleSampleCap {
                break
            }
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read bounded runtime chat calibration events.")
            }
            let sequence = sqlite3_column_int64(statement, 0)
            guard let calibrationType = sqlite3_column_text(statement, 2),
                  String(cString: calibrationType) == "object" else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: Int(sequence),
                    reason: "chat provider usage calibration payload is not an object"
                )
            }
            let event = try decodeStoredEvent(
                from: statement,
                column: 1,
                line: Int(sequence),
                validating: false
            )
            guard isFullyEligibleRuntimeChatCompactionCalibrationEvent(event) else {
                continue
            }
            try JSONLRuntimeChatEventStore.validateStoredEvent(event, line: Int(sequence))
            let key = RuntimeChatCompactionResolutionBindingKey(event: event)
            guard selectedKeys.insert(key).inserted else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: Int(sequence),
                    reason: "chat compaction binding has duplicate terminal resolution"
                )
            }
            selected.append((sequence, event))
        }

        if selected.count < RuntimeChatCompactionCalibrationReport.recentEligibleSampleCap,
           let lowerBound,
           try hasDoneEventBeforeUnlocked(database, sequence: lowerBound) {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: 0,
                reason: "chat compaction calibration SQLite scan exceeds the terminal ceiling"
            )
        }

        var validationEvents: [(sequence: Int64, event: RuntimeChatStoredEvent)] = selected
        for terminal in selected {
            let key = RuntimeChatCompactionResolutionBindingKey(event: terminal.event)
            try requireUniqueCompactionTerminalBindingUnlocked(database, key: key)
            if let request = try latestRequestBindingUnlocked(
                database,
                key: key,
                beforeSequence: terminal.sequence
            ) {
                validationEvents.append(request)
            }
        }
        validationEvents.sort { $0.sequence < $1.sequence }
        try JSONLRuntimeChatEventStore.validateCompactionResolutionBindings(
            validationEvents.map { (line: Int($0.sequence), event: $0.event) }
        )
        return selected
            .sorted { $0.sequence < $1.sequence }
            .map(\.event)
    }

    private func calibrationReportDoneSequenceLowerBoundUnlocked(
        _ database: OpaquePointer
    ) throws -> Int64? {
        let statement = try Self.prepare(
            database,
            """
            SELECT sequence
            FROM runtime_chat_events
            WHERE kind = 'done'
            ORDER BY sequence DESC
            LIMIT 1 OFFSET ?
            """
        )
        defer { sqlite3_finalize(statement) }
        guard sqlite3_bind_int64(
            statement,
            1,
            Int64(calibrationReportStoreLimits.sqliteTerminalScanCeiling - 1)
        ) == SQLITE_OK else {
            throw Self.failure(database, "Could not bind runtime chat calibration scan ceiling.")
        }
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW else {
            throw Self.failure(database, "Could not determine runtime chat calibration scan window.")
        }
        return sqlite3_column_int64(statement, 0)
    }

    private func hasDoneEventBeforeUnlocked(
        _ database: OpaquePointer,
        sequence: Int64
    ) throws -> Bool {
        let statement = try Self.prepare(
            database,
            "SELECT 1 FROM runtime_chat_events WHERE kind = 'done' AND sequence < ? LIMIT 1"
        )
        defer { sqlite3_finalize(statement) }
        guard sqlite3_bind_int64(statement, 1, sequence) == SQLITE_OK else {
            throw Self.failure(database, "Could not bind runtime chat calibration boundary.")
        }
        let result = sqlite3_step(statement)
        if result == SQLITE_ROW { return true }
        guard result == SQLITE_DONE else {
            throw Self.failure(database, "Could not verify runtime chat calibration scan completeness.")
        }
        return false
    }

    private func requireUniqueCompactionTerminalBindingUnlocked(
        _ database: OpaquePointer,
        key: RuntimeChatCompactionResolutionBindingKey
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            SELECT COUNT(*)
            FROM (
                SELECT 1
                FROM runtime_chat_events
                WHERE kind IN ('done', 'cancelled', 'error')
                  AND COALESCE(NULLIF(TRIM(owner_device_id), ''), '') = ?
                  AND session_id = ?
                  AND request_id = ?
                  AND json_type(event_json, '$.compaction_resolution') IS NOT NULL
                LIMIT 2
            )
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(key.ownerDeviceID ?? "", to: statement, at: 1)
        try Self.bindText(key.sessionID, to: statement, at: 2)
        try Self.bindText(key.requestID, to: statement, at: 3)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw Self.failure(database, "Could not verify runtime chat compaction terminal uniqueness.")
        }
        guard sqlite3_column_int64(statement, 0) == 1 else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: 0,
                reason: "chat compaction binding has duplicate terminal resolution"
            )
        }
    }

    private func latestRequestBindingUnlocked(
        _ database: OpaquePointer,
        key: RuntimeChatCompactionResolutionBindingKey,
        beforeSequence: Int64
    ) throws -> (sequence: Int64, event: RuntimeChatStoredEvent)? {
        let statement = try Self.prepare(
            database,
            """
            SELECT sequence, event_json
            FROM runtime_chat_events
            WHERE kind = 'request'
              AND COALESCE(NULLIF(TRIM(owner_device_id), ''), '') = ?
              AND session_id = ?
              AND request_id = ?
              AND sequence < ?
            ORDER BY sequence DESC
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(key.ownerDeviceID ?? "", to: statement, at: 1)
        try Self.bindText(key.sessionID, to: statement, at: 2)
        try Self.bindText(key.requestID, to: statement, at: 3)
        guard sqlite3_bind_int64(statement, 4, beforeSequence) == SQLITE_OK else {
            throw Self.failure(database, "Could not bind runtime chat calibration terminal sequence.")
        }
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW else {
            throw Self.failure(database, "Could not read runtime chat calibration request binding.")
        }
        let sequence = sqlite3_column_int64(statement, 0)
        return (
            sequence,
            try decodeStoredEvent(from: statement, column: 1, line: Int(sequence))
        )
    }

    private func decodeStoredEvent(
        from statement: OpaquePointer,
        column: Int32,
        line: Int,
        validating: Bool = true
    ) throws -> RuntimeChatStoredEvent {
        guard let text = sqlite3_column_text(statement, column) else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "stored event JSON is empty"
            )
        }
        do {
            appendInstrumentation?.didDecodeStoredEvent()
            let decoded = try decoder.decode(
                RuntimeChatStoredEvent.self,
                from: Data(String(cString: text).utf8)
            )
            let event = JSONLRuntimeChatEventStore.projectingLegacyTitleForReplay(decoded)
            if validating {
                try JSONLRuntimeChatEventStore.validateStoredEvent(event, line: line)
            }
            return event
        } catch {
            if let storeError = error as? RuntimeChatEventStoreError {
                throw storeError
            }
            throw RuntimeChatEventStoreError.corruptEventLog(line: line, reason: "decode failed")
        }
    }

    private func ensureIncrementalAppendStateUnlocked(_ database: OpaquePointer) throws {
        let state = try incrementalAppendStateUnlocked(database)
        guard !state.isCurrent(searchProjectionVersion: Self.incrementalSearchProjectionVersion) else { return }

        try Self.execute(database, "BEGIN IMMEDIATE")
        do {
            try repairIncrementalAppendStateIfNeededUnlocked(database)
            try Self.execute(database, "COMMIT")
        } catch {
            try? Self.execute(database, "ROLLBACK")
            throw error
        }
    }

    private func repairIncrementalAppendStateIfNeededUnlocked(_ database: OpaquePointer) throws {
        let state = try incrementalAppendStateUnlocked(database)
        guard !state.isCurrent(searchProjectionVersion: Self.incrementalSearchProjectionVersion) else { return }

        appendInstrumentation?.didRunFullHistoryRepair()
        let indexedEvents = try readIndexedEventsForIncrementalRepairUnlocked(database)
        try Self.execute(database, "DELETE FROM runtime_chat_session_fts")
        try Self.execute(database, "DELETE FROM runtime_chat_event_fts_v2")
        for indexedEvent in indexedEvents {
            try insertIncrementalSearchDocumentUnlocked(
                database,
                sequence: indexedEvent.sequence,
                event: indexedEvent.event
            )
        }
        try markIncrementalAppendStateValidatedUnlocked(database)
    }

    private func incrementalAppendStateUnlocked(
        _ database: OpaquePointer
    ) throws -> RuntimeChatIncrementalAppendState {
        let statement = try Self.prepare(
            database,
            """
            SELECT mutation_revision, validated_revision, search_projection_version
            FROM runtime_chat_append_state
            WHERE singleton = 1
            """
        )
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw SQLiteRuntimeChatEventStoreError("Runtime chat incremental append state is missing.")
        }
        return RuntimeChatIncrementalAppendState(
            mutationRevision: sqlite3_column_int64(statement, 0),
            validatedRevision: sqlite3_column_int64(statement, 1),
            searchProjectionVersion: Int(sqlite3_column_int64(statement, 2))
        )
    }

    private func markIncrementalAppendStateValidatedUnlocked(_ database: OpaquePointer) throws {
        let statement = try Self.prepare(
            database,
            """
            UPDATE runtime_chat_append_state
            SET validated_revision = mutation_revision,
                search_projection_version = ?
            WHERE singleton = 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindInt(Self.incrementalSearchProjectionVersion, to: statement, at: 1)
        try Self.stepDone(statement, database: database)
        guard sqlite3_changes(database) == 1 else {
            throw SQLiteRuntimeChatEventStoreError("Could not validate runtime chat incremental append state.")
        }
    }

    private func readIndexedEventsForIncrementalRepairUnlocked(
        _ database: OpaquePointer
    ) throws -> [(sequence: Int64, event: RuntimeChatStoredEvent)] {
        let statement = try Self.prepare(
            database,
            "SELECT sequence, event_json FROM runtime_chat_events ORDER BY sequence ASC"
        )
        defer { sqlite3_finalize(statement) }
        var events: [(sequence: Int64, event: RuntimeChatStoredEvent)] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not repair runtime chat append state.")
            }
            let sequence = sqlite3_column_int64(statement, 0)
            events.append((
                sequence: sequence,
                event: try decodeStoredEvent(
                    from: statement,
                    column: 1,
                    line: Int(sequence)
                )
            ))
        }
        try JSONLRuntimeChatEventStore.validateCompactionResolutionBindings(
            events.map { (line: Int($0.sequence), event: $0.event) }
        )
        return events
    }

    private func insertIncrementalSearchDocumentUnlocked(
        _ database: OpaquePointer,
        sequence: Int64,
        event: RuntimeChatStoredEvent
    ) throws {
        let requestMessages: [RuntimeChatStoredMessage]
        if event.kind == .request {
            requestMessages = JSONLRuntimeChatEventStore.messages(
                from: [event],
                key: RuntimeChatSessionProjectionKey(event: event),
                limit: Int.max
            )
        } else {
            requestMessages = []
        }
        let title = [event.title, "New chat"]
            .compactMap { $0?.runtimeSearchSnippetText }
            .filter { !$0.isEmpty }
            .joined(separator: " ")
        let status: String
        switch event.kind {
        case .archived:
            status = "archived"
        case .deleted:
            status = "deleted"
        default:
            status = "active"
        }
        let metadata = [
            event.kind.rawValue,
            event.finishReason,
            event.error?.code,
        ]
        .compactMap { $0?.runtimeSearchSnippetText }
        .filter { !$0.isEmpty }
        .joined(separator: " ")
        let transcript = (
            requestMessages.map(\.content)
                + [event.delta].compactMap { $0 }
        )
        .map(\.runtimeSearchSnippetText)
        .filter { !$0.isEmpty }
        .joined(separator: " ")
        let reasoning = event.reasoningDelta?.runtimeSearchSnippetText ?? ""
        let attachment = requestMessages
            .flatMap(\.attachments)
            .flatMap { attachment in
                [attachment.name, attachment.mimeType, attachment.text]
            }
            .compactMap { $0?.runtimeSearchSnippetText }
            .filter { !$0.isEmpty }
            .joined(separator: " ")

        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_chat_event_fts_v2(
                rowid,
                event_id,
                owner_key,
                session_id,
                title,
                indexed_session_id,
                model,
                status,
                metadata,
                transcript,
                reasoning,
                attachment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        guard sqlite3_bind_int64(statement, 1, sequence) == SQLITE_OK else {
            throw Self.failure(database, "Could not bind runtime chat search sequence.")
        }
        try Self.bindText(event.id, to: statement, at: 2)
        try Self.bindText(Self.ownerKey(event.ownerDeviceID.sqliteNormalizedOwnerDeviceID), to: statement, at: 3)
        try Self.bindText(event.sessionID, to: statement, at: 4)
        try Self.bindText(title.normalizedRuntimeSearchText, to: statement, at: 5)
        try Self.bindText(
            event.sessionID.runtimeSearchSnippetText.normalizedRuntimeSearchText,
            to: statement,
            at: 6
        )
        try Self.bindText(
            event.model.runtimeSearchSnippetText.normalizedRuntimeSearchText,
            to: statement,
            at: 7
        )
        try Self.bindText(status.normalizedRuntimeSearchText, to: statement, at: 8)
        try Self.bindText(metadata.normalizedRuntimeSearchText, to: statement, at: 9)
        try Self.bindText(transcript.normalizedRuntimeSearchText, to: statement, at: 10)
        try Self.bindText(reasoning.normalizedRuntimeSearchText, to: statement, at: 11)
        try Self.bindText(attachment.normalizedRuntimeSearchText, to: statement, at: 12)
        try Self.stepDone(statement, database: database)
        appendInstrumentation?.didInsertSearchDocument()
    }

    private func searchCandidateSessionIDsUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        query: RuntimeChatSessionSearchQuery
    ) throws -> [String] {
        // A streamed answer can contain a match that crosses event boundaries. Those
        // sessions are conservative candidates; the exact in-memory projection below
        // removes stale or unrelated matches.
        let streamBoundarySessionIDs = try streamBoundarySessionIDsUnlocked(
            database,
            ownerDeviceID: ownerDeviceID
        )
        var matchingSessionIDs: Set<String>?
        for term in query.terms {
            var termSessionIDs = try substringSessionIDsUnlocked(
                database,
                ownerDeviceID: ownerDeviceID,
                term: term
            )
            termSessionIDs.formUnion(streamBoundarySessionIDs)
            if let existing = matchingSessionIDs {
                matchingSessionIDs = existing.intersection(termSessionIDs)
            } else {
                matchingSessionIDs = termSessionIDs
            }
            if matchingSessionIDs?.isEmpty == true { return [] }
        }
        return (matchingSessionIDs ?? []).sorted()
    }

    private func substringSessionIDsUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        term: String
    ) throws -> Set<String> {
        let statement = try Self.prepare(
            database,
            """
            SELECT DISTINCT session_id
            FROM runtime_chat_event_fts_v2
            WHERE owner_key = ?
              AND (
                    instr(title, ?) > 0
                 OR instr(indexed_session_id, ?) > 0
                 OR instr(model, ?) > 0
                 OR instr(status, ?) > 0
                 OR instr(metadata, ?) > 0
                 OR instr(transcript, ?) > 0
                 OR instr(reasoning, ?) > 0
                 OR instr(attachment, ?) > 0
              )
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(ownerDeviceID), to: statement, at: 1)
        for bindIndex in 2...9 {
            try Self.bindText(term, to: statement, at: Int32(bindIndex))
        }

        var sessionIDs = Set<String>()
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime chat substring candidates.")
            }
            if let text = sqlite3_column_text(statement, 0) {
                sessionIDs.insert(String(cString: text))
            }
        }
        return sessionIDs
    }

    private func streamBoundarySessionIDsUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?
    ) throws -> Set<String> {
        let statement = try Self.prepare(
            database,
            """
            SELECT session_id
            FROM runtime_chat_events
            WHERE COALESCE(NULLIF(TRIM(owner_device_id), ''), '') = ?
              AND (
                    json_type(event_json, '$.delta') = 'text'
                 OR json_type(event_json, '$.reasoning_delta') = 'text'
              )
            GROUP BY session_id, request_id
            HAVING COUNT(*) > 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(ownerDeviceID), to: statement, at: 1)

        var sessionIDs = Set<String>()
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime chat stream-boundary candidates.")
            }
            if let text = sqlite3_column_text(statement, 0) {
                sessionIDs.insert(String(cString: text))
            }
        }
        return sessionIDs
    }

    private func semanticEmbeddingUnlocked(
        for key: RuntimeChatSemanticEmbeddingKey,
        database: OpaquePointer
    ) throws -> RuntimeChatSemanticEmbeddingRecord? {
        let statement = try Self.prepare(
            database,
            """
            SELECT dimension, vector_blob
            FROM runtime_chat_semantic_embeddings
            WHERE owner_key = ?
              AND session_id = ?
              AND embedding_model_id = ?
              AND model_fingerprint = ?
              AND document_fingerprint = ?
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(key.ownerDeviceID.sqliteNormalizedOwnerDeviceID), to: statement, at: 1)
        try Self.bindText(key.sessionID, to: statement, at: 2)
        try Self.bindText(key.canonicalQualifiedEmbeddingModelID, to: statement, at: 3)
        try Self.bindText(key.modelFingerprint, to: statement, at: 4)
        try Self.bindText(key.documentFingerprint, to: statement, at: 5)

        let result = sqlite3_step(statement)
        guard result == SQLITE_ROW else {
            if result == SQLITE_DONE { return nil }
            throw Self.failure(database, "Could not read runtime chat semantic embedding.")
        }
        let dimension = Int(sqlite3_column_int64(statement, 0))
        let blobSize = Int(sqlite3_column_bytes(statement, 1))
        let blob = sqlite3_column_blob(statement, 1).map { Data(bytes: $0, count: blobSize) }
        guard sqlite3_column_type(statement, 0) == SQLITE_INTEGER,
              sqlite3_column_type(statement, 1) == SQLITE_BLOB,
              let blob,
              let embedding = Self.decodeSemanticEmbedding(blob, dimension: dimension) else {
            return nil
        }
        return RuntimeChatSemanticEmbeddingRecord(key: key, embedding: embedding)
    }

    private func sessionRevisionUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        sessionID: String
    ) throws -> Int64? {
        let ownerPredicate = ownerDeviceID == nil ? "owner_device_id IS NULL" : "owner_device_id = ?"
        let statement = try Self.prepare(
            database,
            "SELECT MAX(sequence) FROM runtime_chat_events WHERE \(ownerPredicate) AND session_id = ?"
        )
        defer { sqlite3_finalize(statement) }
        var bindIndex: Int32 = 1
        if let ownerDeviceID {
            try Self.bindText(ownerDeviceID, to: statement, at: bindIndex)
            bindIndex += 1
        }
        try Self.bindText(sessionID, to: statement, at: bindIndex)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw Self.failure(database, "Could not read runtime chat session revision.")
        }
        guard sqlite3_column_type(statement, 0) == SQLITE_INTEGER else { return nil }
        return sqlite3_column_int64(statement, 0)
    }

    private func upsertSemanticEmbeddingUnlocked(
        _ record: RuntimeChatSemanticEmbeddingRecord,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_chat_semantic_embeddings(
                owner_key,
                session_id,
                embedding_model_id,
                model_fingerprint,
                document_fingerprint,
                dimension,
                vector_blob,
                last_accessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                owner_key,
                session_id,
                embedding_model_id,
                model_fingerprint,
                document_fingerprint
            ) DO UPDATE SET
                dimension = excluded.dimension,
                vector_blob = excluded.vector_blob,
                last_accessed_at = excluded.last_accessed_at
            """
        )
        defer { sqlite3_finalize(statement) }
        let key = record.key
        try Self.bindText(Self.ownerKey(key.ownerDeviceID.sqliteNormalizedOwnerDeviceID), to: statement, at: 1)
        try Self.bindText(key.sessionID, to: statement, at: 2)
        try Self.bindText(key.canonicalQualifiedEmbeddingModelID, to: statement, at: 3)
        try Self.bindText(key.modelFingerprint, to: statement, at: 4)
        try Self.bindText(key.documentFingerprint, to: statement, at: 5)
        try Self.bindInt(record.embedding.count, to: statement, at: 6)
        try Self.bindBlob(Self.encodeSemanticEmbedding(record.embedding), to: statement, at: 7)
        try Self.bindDouble(Date().timeIntervalSince1970, to: statement, at: 8)
        try Self.stepDone(statement, database: database)
    }

    private func deleteSemanticEmbeddingUnlocked(
        _ key: RuntimeChatSemanticEmbeddingKey,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            DELETE FROM runtime_chat_semantic_embeddings
            WHERE owner_key = ?
              AND session_id = ?
              AND embedding_model_id = ?
              AND model_fingerprint = ?
              AND document_fingerprint = ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(key.ownerDeviceID.sqliteNormalizedOwnerDeviceID), to: statement, at: 1)
        try Self.bindText(key.sessionID, to: statement, at: 2)
        try Self.bindText(key.canonicalQualifiedEmbeddingModelID, to: statement, at: 3)
        try Self.bindText(key.modelFingerprint, to: statement, at: 4)
        try Self.bindText(key.documentFingerprint, to: statement, at: 5)
        try Self.stepDone(statement, database: database)
    }

    private func deleteSemanticEmbeddingsUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        sessionID: String
    ) throws {
        let statement = try Self.prepare(
            database,
            "DELETE FROM runtime_chat_semantic_embeddings WHERE owner_key = ? AND session_id = ?"
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(ownerDeviceID), to: statement, at: 1)
        try Self.bindText(sessionID, to: statement, at: 2)
        try Self.stepDone(statement, database: database)
    }

    private func deleteSearchRowUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        sessionID: String
    ) throws {
        let statement = try Self.prepare(
            database,
            "DELETE FROM runtime_chat_session_fts WHERE owner_key = ? AND session_id = ?"
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(ownerDeviceID), to: statement, at: 1)
        try Self.bindText(sessionID, to: statement, at: 2)
        try Self.stepDone(statement, database: database)
    }

    private func deleteIncrementalSearchDocumentsUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        sessionID: String
    ) throws {
        let ownerPredicate = ownerDeviceID == nil ? "owner_device_id IS NULL" : "owner_device_id = ?"
        let statement = try Self.prepare(
            database,
            """
            DELETE FROM runtime_chat_event_fts_v2
            WHERE rowid IN (
                SELECT sequence
                FROM runtime_chat_events
                WHERE \(ownerPredicate) AND session_id = ?
            )
            """
        )
        defer { sqlite3_finalize(statement) }
        var bindIndex: Int32 = 1
        if let ownerDeviceID {
            try Self.bindText(ownerDeviceID, to: statement, at: bindIndex)
            bindIndex += 1
        }
        try Self.bindText(sessionID, to: statement, at: bindIndex)
        try Self.stepDone(statement, database: database)
    }

    private func enforceSemanticEmbeddingRowLimitUnlocked(
        _ scope: RuntimeChatSemanticEmbeddingScope,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            DELETE FROM runtime_chat_semantic_embeddings
            WHERE rowid IN (
                SELECT rowid
                FROM runtime_chat_semantic_embeddings
                WHERE owner_key = ?
                  AND embedding_model_id = ?
                ORDER BY last_accessed_at DESC, rowid DESC
                LIMIT -1 OFFSET ?
            )
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(scope.ownerKey, to: statement, at: 1)
        try Self.bindText(scope.embeddingModelID, to: statement, at: 2)
        try Self.bindInt(semanticEmbeddingRowLimitPerOwnerModel, to: statement, at: 3)
        try Self.stepDone(statement, database: database)
    }

    private func pruneDeletedSessionsUnlocked(
        _ database: OpaquePointer,
        scope: RuntimeChatRetentionScope,
        deletedBefore cutoff: Date,
        limit: Int
    ) throws -> RuntimeChatDeletedSessionPruneResult {
        let appendStateWasCurrent = try incrementalAppendStateUnlocked(database)
            .isCurrent(searchProjectionVersion: Self.incrementalSearchProjectionVersion)
        let candidates = try retentionCandidatesUnlocked(
            database,
            scope: scope,
            deletedBefore: cutoff,
            limit: limit
        )

        var prunedSessionIDs: [String] = []
        var prunedEventCount = 0
        for candidate in candidates {
            try recordRetentionTombstoneUnlocked(
                database,
                ownerDeviceID: candidate.key.ownerDeviceID,
                sessionID: candidate.key.sessionID,
                deletedAt: candidate.deletedAt
            )
            try deleteIncrementalSearchDocumentsUnlocked(
                database,
                ownerDeviceID: candidate.key.ownerDeviceID,
                sessionID: candidate.key.sessionID
            )
            prunedEventCount += try deleteEventsUnlocked(
                database,
                ownerDeviceID: candidate.key.ownerDeviceID,
                sessionID: candidate.key.sessionID
            )
            try deleteSemanticEmbeddingsUnlocked(
                database,
                ownerDeviceID: candidate.key.ownerDeviceID,
                sessionID: candidate.key.sessionID
            )
            try deleteSearchRowUnlocked(
                database,
                ownerDeviceID: candidate.key.ownerDeviceID,
                sessionID: candidate.key.sessionID
            )
            prunedSessionIDs.append(candidate.key.sessionID)
        }
        if appendStateWasCurrent, !candidates.isEmpty {
            try markIncrementalAppendStateValidatedUnlocked(database)
        }
        return RuntimeChatDeletedSessionPruneResult(
            prunedSessionIDs: prunedSessionIDs,
            prunedEventCount: prunedEventCount
        )
    }

    private func retentionCandidatesUnlocked(
        _ database: OpaquePointer,
        scope: RuntimeChatRetentionScope,
        deletedBefore cutoff: Date,
        limit: Int
    ) throws -> [RuntimeChatRetentionCandidate] {
        let ownerPredicate: String
        switch scope {
        case .owner(nil):
            ownerPredicate = "AND owner_device_id IS NULL"
        case .owner:
            ownerPredicate = "AND owner_device_id = ?"
        case .allOwners:
            ownerPredicate = ""
        }
        let statement = try Self.prepare(
            database,
            """
            WITH ranked_lifecycle AS (
                SELECT
                    owner_device_id,
                    session_id,
                    kind,
                    timestamp,
                    ROW_NUMBER() OVER (
                        PARTITION BY COALESCE(NULLIF(TRIM(owner_device_id), ''), ''), session_id
                        ORDER BY sequence DESC
                    ) AS lifecycle_rank
                FROM runtime_chat_events
                WHERE kind IN (?, ?, ?)
                \(ownerPredicate)
            )
            SELECT owner_device_id, session_id, timestamp
            FROM ranked_lifecycle
            WHERE lifecycle_rank = 1
              AND kind = ?
              AND timestamp < ?
            ORDER BY timestamp ASC, COALESCE(owner_device_id, '') ASC, session_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }

        var bindIndex: Int32 = 1
        for kind in [
            RuntimeChatStoredEventKind.archived,
            RuntimeChatStoredEventKind.restored,
            RuntimeChatStoredEventKind.deleted,
        ] {
            try Self.bindText(kind.rawValue, to: statement, at: bindIndex)
            bindIndex += 1
        }
        if case .owner(let ownerDeviceID?) = scope {
            try Self.bindText(ownerDeviceID, to: statement, at: bindIndex)
            bindIndex += 1
        }
        try Self.bindText(RuntimeChatStoredEventKind.deleted.rawValue, to: statement, at: bindIndex)
        bindIndex += 1
        try Self.bindText(Self.timestampString(from: cutoff), to: statement, at: bindIndex)
        bindIndex += 1
        try Self.bindInt(limit, to: statement, at: bindIndex)

        var candidates: [RuntimeChatRetentionCandidate] = []
        candidates.reserveCapacity(min(limit, 100))
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW,
                  let sessionIDText = sqlite3_column_text(statement, 1),
                  let deletedAtText = sqlite3_column_text(statement, 2) else {
                throw Self.failure(database, "Could not read runtime chat retention candidates.")
            }
            let ownerDeviceID = sqlite3_column_type(statement, 0) == SQLITE_NULL
                ? nil
                : sqlite3_column_text(statement, 0).map { String(cString: $0) }
            candidates.append(RuntimeChatRetentionCandidate(
                key: RuntimeChatRetentionSessionKey(
                    ownerDeviceID: ownerDeviceID,
                    sessionID: String(cString: sessionIDText)
                ),
                deletedAt: String(cString: deletedAtText)
            ))
        }
        return candidates
    }

    private func recordRetentionTombstoneUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        sessionID: String,
        deletedAt: String
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_chat_retention_tombstones(owner_key, session_id, deleted_at)
            VALUES (?, ?, ?)
            ON CONFLICT(owner_key, session_id) DO UPDATE SET deleted_at = excluded.deleted_at
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(ownerDeviceID), to: statement, at: 1)
        try Self.bindText(sessionID, to: statement, at: 2)
        try Self.bindText(deletedAt, to: statement, at: 3)
        try Self.stepDone(statement, database: database)
    }

    private func deleteEventsUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        sessionID: String
    ) throws -> Int {
        let statement: OpaquePointer
        if let ownerDeviceID {
            statement = try Self.prepare(
                database,
                "DELETE FROM runtime_chat_events WHERE owner_device_id = ? AND session_id = ?"
            )
            try Self.bindText(ownerDeviceID, to: statement, at: 1)
            try Self.bindText(sessionID, to: statement, at: 2)
        } else {
            statement = try Self.prepare(
                database,
                "DELETE FROM runtime_chat_events WHERE owner_device_id IS NULL AND session_id = ?"
            )
            try Self.bindText(sessionID, to: statement, at: 1)
        }
        defer { sqlite3_finalize(statement) }
        try Self.stepDone(statement, database: database)
        return Int(sqlite3_changes(database))
    }

    private func retentionTombstoneExistsUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        sessionID: String
    ) throws -> Bool {
        let statement = try Self.prepare(
            database,
            """
            SELECT 1
            FROM runtime_chat_retention_tombstones
            WHERE owner_key = ? AND session_id = ?
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(ownerDeviceID), to: statement, at: 1)
        try Self.bindText(sessionID, to: statement, at: 2)
        let result = sqlite3_step(statement)
        if result == SQLITE_ROW { return true }
        if result == SQLITE_DONE { return false }
        throw Self.failure(database, "Could not check runtime chat retention tombstone.")
    }

    private func withDatabase<T>(
        deferLegacyJSONLCompaction: Bool = false,
        _ body: (OpaquePointer) throws -> T
    ) throws -> T {
        try RuntimeEventLogFileProtection.prepareDirectory(for: databaseURL)
        if FileManager.default.fileExists(atPath: databaseURL.path) {
            try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        var database: OpaquePointer?
        let flags = SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX
        guard sqlite3_open_v2(databaseURL.path, &database, flags, nil) == SQLITE_OK,
              let openedDatabase = database else {
            defer {
                if let database {
                    sqlite3_close(database)
                }
            }
            throw SQLiteRuntimeChatEventStoreError("Could not open runtime chat SQLite store.")
        }
        defer {
            sqlite3_close(openedDatabase)
            try? RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        try Self.ensureSchema(openedDatabase)
        try importLegacyJSONLIfNeeded(
            openedDatabase,
            compactRetentionTombstones: !deferLegacyJSONLCompaction
        )
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        return try body(openedDatabase)
    }

    private static func ensureSchema(_ database: OpaquePointer) throws {
        try execute(database, "PRAGMA foreign_keys = ON")
        let incrementalSearchTableExisted = try schemaObjectExists(
            database,
            type: "table",
            name: incrementalSearchTableName
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_chat_events(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                kind TEXT NOT NULL,
                request_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                owner_device_id TEXT,
                model TEXT NOT NULL,
                event_json TEXT NOT NULL
            )
            """
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_chat_append_state(
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                mutation_revision INTEGER NOT NULL,
                validated_revision INTEGER NOT NULL,
                search_projection_version INTEGER NOT NULL
            )
            """
        )
        try execute(
            database,
            """
            INSERT OR IGNORE INTO runtime_chat_append_state(
                singleton,
                mutation_revision,
                validated_revision,
                search_projection_version
            ) VALUES (1, 0, -1, 0)
            """
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_chat_store_metadata(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_chat_retention_tombstones(
                owner_key TEXT NOT NULL,
                session_id TEXT NOT NULL,
                deleted_at TEXT NOT NULL,
                PRIMARY KEY(owner_key, session_id)
            )
            """
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_chat_semantic_embeddings(
                owner_key TEXT NOT NULL,
                session_id TEXT NOT NULL,
                embedding_model_id TEXT NOT NULL,
                model_fingerprint TEXT NOT NULL,
                document_fingerprint TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                vector_blob BLOB NOT NULL,
                last_accessed_at REAL NOT NULL,
                PRIMARY KEY(
                    owner_key,
                    session_id,
                    embedding_model_id,
                    model_fingerprint,
                    document_fingerprint
                )
            )
            """
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_chat_events_owner_session ON runtime_chat_events(owner_device_id, session_id, sequence)"
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_chat_events_event_id ON runtime_chat_events(event_id)"
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_chat_events_timestamp ON runtime_chat_events(timestamp)"
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_chat_events_kind_sequence ON runtime_chat_events(kind, sequence DESC)"
        )
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_chat_events_compaction_binding
            ON runtime_chat_events(
                kind,
                COALESCE(NULLIF(TRIM(owner_device_id), ''), ''),
                session_id,
                request_id,
                sequence DESC
            )
            """
        )
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_chat_events_retention_lifecycle
            ON runtime_chat_events(owner_device_id, session_id, timestamp DESC, sequence DESC)
            WHERE kind IN ('archived', 'restored', 'deleted')
            """
        )
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_chat_events_retention_lifecycle_sequence_v2
            ON runtime_chat_events(
                COALESCE(NULLIF(TRIM(owner_device_id), ''), ''),
                session_id,
                sequence DESC
            )
            WHERE kind IN ('archived', 'restored', 'deleted')
            """
        )
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_chat_semantic_embeddings_owner_model_lru
            ON runtime_chat_semantic_embeddings(
                owner_key,
                embedding_model_id,
                last_accessed_at DESC
            )
            """
        )
        try execute(
            database,
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS runtime_chat_session_fts USING fts5(
                owner_key UNINDEXED,
                session_id UNINDEXED,
                title,
                indexed_session_id,
                model,
                status,
                metadata,
                transcript,
                reasoning,
                attachment,
                tokenize = 'unicode61 remove_diacritics 2'
            )
            """
        )
        try execute(
            database,
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS runtime_chat_event_fts_v2 USING fts5(
                event_id UNINDEXED,
                owner_key UNINDEXED,
                session_id UNINDEXED,
                title,
                indexed_session_id,
                model,
                status,
                metadata,
                transcript,
                reasoning,
                attachment,
                tokenize = 'unicode61 remove_diacritics 2'
            )
            """
        )
        if !incrementalSearchTableExisted {
            try execute(
                database,
                "UPDATE runtime_chat_append_state SET search_projection_version = 0 WHERE singleton = 1"
            )
        }
        try execute(
            database,
            """
            CREATE TRIGGER IF NOT EXISTS runtime_chat_events_append_state_insert_v2
            AFTER INSERT ON runtime_chat_events
            BEGIN
                UPDATE runtime_chat_append_state
                SET mutation_revision = mutation_revision + 1
                WHERE singleton = 1;
            END
            """
        )
        try execute(
            database,
            """
            CREATE TRIGGER IF NOT EXISTS runtime_chat_events_append_state_update_v2
            AFTER UPDATE ON runtime_chat_events
            BEGIN
                UPDATE runtime_chat_append_state
                SET mutation_revision = mutation_revision + 1
                WHERE singleton = 1;
            END
            """
        )
        try execute(
            database,
            """
            CREATE TRIGGER IF NOT EXISTS runtime_chat_events_append_state_delete_v2
            AFTER DELETE ON runtime_chat_events
            BEGIN
                UPDATE runtime_chat_append_state
                SET mutation_revision = mutation_revision + 1
                WHERE singleton = 1;
            END
            """
        )
    }

    private func importLegacyJSONLIfNeeded(
        _ database: OpaquePointer,
        compactRetentionTombstones: Bool
    ) throws {
        guard let legacyJSONLFileURL else { return }
        try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: legacyJSONLFileURL) {
            try importLegacyJSONLIfNeededCoordinated(
                database,
                legacyJSONLFileURL: legacyJSONLFileURL,
                compactRetentionTombstones: compactRetentionTombstones
            )
        }
    }

    private func importLegacyJSONLIfNeededCoordinated(
        _ database: OpaquePointer,
        legacyJSONLFileURL: URL,
        compactRetentionTombstones: Bool
    ) throws {
        let legacyPath = legacyJSONLFileURL.standardizedFileURL.path
        guard FileManager.default.fileExists(atPath: legacyPath) else { return }
        let legacySignature = try Self.legacyImportSignature(for: legacyJSONLFileURL)
        let tombstoneCount = try retentionTombstoneCountUnlocked(database)
        let compactionMarker = Self.legacyCompactionMarker(
            legacySignature: legacySignature,
            tombstoneCount: tombstoneCount
        )
        let importedSignature = try Self.metadataValue(database, key: Self.legacyImportMetadataKey)
        let compactedMarker = try Self.metadataValue(database, key: Self.legacyCompactionMetadataKey)
        if importedSignature == legacySignature,
           !compactRetentionTombstones || compactedMarker == compactionMarker {
            return
        }

        let snapshot = try legacyJSONLSnapshot(from: legacyJSONLFileURL)
        if importedSignature != snapshot.signature {
            for record in snapshot.records {
                let sanitized = record.event.sanitizedForStorage()
                try JSONLRuntimeChatEventStore.validateStoredEvent(sanitized, line: record.line)
                _ = try insertEventUnlocked(
                    sanitized,
                    database: database,
                    skipExisting: true
                )
            }
            try Self.setMetadataValue(database, key: Self.legacyImportMetadataKey, value: snapshot.signature)
        }

        if compactRetentionTombstones {
            try compactLegacyJSONLIfNeeded(
                database,
                snapshot: snapshot,
                tombstoneCount: tombstoneCount
            )
        }
    }

    private func compactLegacyJSONLIfNeeded(
        _ database: OpaquePointer,
        snapshot providedSnapshot: RuntimeChatLegacyJSONLSnapshot? = nil,
        tombstoneCount providedTombstoneCount: Int? = nil
    ) throws {
        guard let legacyJSONLFileURL else { return }
        try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: legacyJSONLFileURL) {
            try compactLegacyJSONLIfNeededCoordinated(
                database,
                legacyJSONLFileURL: legacyJSONLFileURL,
                snapshot: providedSnapshot,
                tombstoneCount: providedTombstoneCount
            )
        }
    }

    private func compactLegacyJSONLIfNeededCoordinated(
        _ database: OpaquePointer,
        legacyJSONLFileURL: URL,
        snapshot providedSnapshot: RuntimeChatLegacyJSONLSnapshot?,
        tombstoneCount providedTombstoneCount: Int?
    ) throws {
        let legacyPath = legacyJSONLFileURL.standardizedFileURL.path
        guard FileManager.default.fileExists(atPath: legacyPath) else { return }

        let tombstoneCount = try providedTombstoneCount ?? retentionTombstoneCountUnlocked(database)
        let currentSignature = try Self.legacyImportSignature(for: legacyJSONLFileURL)
        let currentMarker = Self.legacyCompactionMarker(
            legacySignature: currentSignature,
            tombstoneCount: tombstoneCount
        )
        if providedSnapshot == nil,
           try Self.metadataValue(database, key: Self.legacyCompactionMetadataKey) == currentMarker {
            return
        }

        let snapshot: RuntimeChatLegacyJSONLSnapshot
        if let providedSnapshot, providedSnapshot.signature == currentSignature {
            snapshot = providedSnapshot
        } else {
            snapshot = try legacyJSONLSnapshot(from: legacyJSONLFileURL)
        }
        guard try Self.metadataValue(database, key: Self.legacyImportMetadataKey) == snapshot.signature else {
            return
        }

        var tombstoneCache: [RuntimeChatRetentionSessionKey: Bool] = [:]
        var compactedData = Data()
        compactedData.reserveCapacity(snapshot.data.count)
        var removedEvent = false
        for record in snapshot.records {
            let key = RuntimeChatRetentionSessionKey(
                ownerDeviceID: record.event.ownerDeviceID.sqliteNormalizedOwnerDeviceID,
                sessionID: record.event.sessionID
            )
            let isTombstoned: Bool
            if let cached = tombstoneCache[key] {
                isTombstoned = cached
            } else {
                isTombstoned = try retentionTombstoneExistsUnlocked(
                    database,
                    ownerDeviceID: key.ownerDeviceID,
                    sessionID: key.sessionID
                )
                tombstoneCache[key] = isTombstoned
            }
            if isTombstoned {
                removedEvent = true
            } else {
                compactedData.append(record.rawLine)
                compactedData.append(0x0A)
            }
        }

        if removedEvent {
            // Current writers hold the same sidecar lock through validation and append, so this
            // check and replace are one coordinated critical section. Pre-protocol writers do
            // not honor that lock; a change visible before replacement fails closed and retries,
            // but bytes written only to an already-replaced inode are outside this protocol.
            guard try Self.legacyImportSignature(for: legacyJSONLFileURL) == snapshot.signature else {
                return
            }
            legacyJSONLCompactionWillReplace?()
            try compactedData.write(to: legacyJSONLFileURL, options: .atomic)
            try RuntimeEventLogFileProtection.secureFile(at: legacyJSONLFileURL)
            let compactedSignature = try Self.legacyImportSignature(for: legacyJSONLFileURL)
            let writtenData = try Data(contentsOf: legacyJSONLFileURL)
            guard writtenData == compactedData,
                  try Self.legacyImportSignature(for: legacyJSONLFileURL) == compactedSignature else {
                return
            }
            try Self.setMetadataValue(
                database,
                key: Self.legacyImportMetadataKey,
                value: compactedSignature
            )
            try Self.setMetadataValue(
                database,
                key: Self.legacyCompactionMetadataKey,
                value: Self.legacyCompactionMarker(
                    legacySignature: compactedSignature,
                    tombstoneCount: tombstoneCount
                )
            )
            return
        }

        try Self.setMetadataValue(
            database,
            key: Self.legacyCompactionMetadataKey,
            value: Self.legacyCompactionMarker(
                legacySignature: snapshot.signature,
                tombstoneCount: tombstoneCount
            )
        )
    }

    private func legacyJSONLSnapshot(from fileURL: URL) throws -> RuntimeChatLegacyJSONLSnapshot {
        for _ in 0..<3 {
            let signatureBeforeRead = try Self.legacyImportSignature(for: fileURL)
            let data = try Data(contentsOf: fileURL)
            let signatureAfterRead = try Self.legacyImportSignature(for: fileURL)
            guard signatureBeforeRead == signatureAfterRead else { continue }

            var records: [RuntimeChatLegacyJSONLRecord] = []
            let rawLines = data.split(separator: 0x0A, omittingEmptySubsequences: false)
            for (index, rawLine) in rawLines.enumerated() {
                let line = String(decoding: rawLine, as: UTF8.self)
                guard !line.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                    continue
                }
                let event: RuntimeChatStoredEvent
                do {
                    let decoded = try decoder.decode(RuntimeChatStoredEvent.self, from: Data(rawLine))
                    event = JSONLRuntimeChatEventStore.projectingLegacyTitleForReplay(decoded)
                    try JSONLRuntimeChatEventStore.validateStoredEvent(event, line: index + 1)
                } catch {
                    if let storeError = error as? RuntimeChatEventStoreError {
                        throw storeError
                    }
                    throw RuntimeChatEventStoreError.corruptEventLog(
                        line: index + 1,
                        reason: "decode failed"
                    )
                }
                records.append(RuntimeChatLegacyJSONLRecord(
                    line: index + 1,
                    event: event,
                    rawLine: Data(rawLine)
                ))
            }
            try JSONLRuntimeChatEventStore.validateCompactionResolutionBindings(
                records.map { (line: $0.line, event: $0.event) }
            )
            return RuntimeChatLegacyJSONLSnapshot(
                signature: signatureAfterRead,
                data: data,
                records: records
            )
        }
        throw SQLiteRuntimeChatEventStoreError(
            "Runtime chat legacy JSONL changed while it was being migrated."
        )
    }

    private func retentionTombstoneCountUnlocked(_ database: OpaquePointer) throws -> Int {
        let statement = try Self.prepare(database, "SELECT COUNT(*) FROM runtime_chat_retention_tombstones")
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw Self.failure(database, "Could not count runtime chat retention tombstones.")
        }
        return Int(sqlite3_column_int64(statement, 0))
    }

    private static func legacyCompactionMarker(
        legacySignature: String,
        tombstoneCount: Int
    ) -> String {
        "\(legacySignature)|tombstones=\(tombstoneCount)"
    }

    private static func legacyImportSignature(for fileURL: URL) throws -> String {
        let standardizedURL = fileURL.standardizedFileURL
        let attributes = try FileManager.default.attributesOfItem(atPath: standardizedURL.path)
        let fileSize = (attributes[.size] as? NSNumber)?.int64Value ?? 0
        let modifiedAt = (attributes[.modificationDate] as? Date)?.timeIntervalSince1970 ?? 0
        return "\(standardizedURL.path)|size=\(fileSize)|mtime=\(String(format: "%.6f", modifiedAt))"
    }

    private func eventExistsUnlocked(_ database: OpaquePointer, eventID: String) throws -> Bool {
        let statement = try Self.prepare(database, "SELECT 1 FROM runtime_chat_events WHERE event_id = ? LIMIT 1")
        defer { sqlite3_finalize(statement) }
        try Self.bindText(eventID, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_ROW { return true }
        if result == SQLITE_DONE { return false }
        throw Self.failure(database, "Could not check runtime chat SQLite event id.")
    }

    private static func metadataValue(_ database: OpaquePointer, key: String) throws -> String? {
        let statement = try prepare(database, "SELECT value FROM runtime_chat_store_metadata WHERE key = ? LIMIT 1")
        defer { sqlite3_finalize(statement) }
        try bindText(key, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW else {
            throw failure(database, "Could not read runtime chat SQLite metadata.")
        }
        guard let text = sqlite3_column_text(statement, 0) else { return nil }
        return String(cString: text)
    }

    private static func setMetadataValue(_ database: OpaquePointer, key: String, value: String) throws {
        let statement = try prepare(
            database,
            """
            INSERT INTO runtime_chat_store_metadata(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        )
        defer { sqlite3_finalize(statement) }
        try bindText(key, to: statement, at: 1)
        try bindText(value, to: statement, at: 2)
        try stepDone(statement, database: database)
    }

    private static func schemaObjectExists(
        _ database: OpaquePointer,
        type: String,
        name: String
    ) throws -> Bool {
        let statement = try prepare(
            database,
            "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ? LIMIT 1"
        )
        defer { sqlite3_finalize(statement) }
        try bindText(type, to: statement, at: 1)
        try bindText(name, to: statement, at: 2)
        let result = sqlite3_step(statement)
        if result == SQLITE_ROW { return true }
        if result == SQLITE_DONE { return false }
        throw failure(database, "Could not inspect runtime chat SQLite schema.")
    }

    private static func execute(_ database: OpaquePointer, _ sql: String) throws {
        var error: UnsafeMutablePointer<CChar>?
        if sqlite3_exec(database, sql, nil, nil, &error) != SQLITE_OK {
            let message = error.map { String(cString: $0) } ?? "unknown SQLite error"
            sqlite3_free(error)
            throw SQLiteRuntimeChatEventStoreError(message)
        }
    }

    private static func prepare(_ database: OpaquePointer, _ sql: String) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw failure(database, "Could not prepare runtime chat SQLite statement.")
        }
        return statement
    }

    private static func bindText(_ value: String, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_text(statement, index, value, -1, sqliteTransient) == SQLITE_OK else {
            throw SQLiteRuntimeChatEventStoreError("Could not bind runtime chat SQLite text.")
        }
    }

    private static func bindOptionalText(_ value: String?, to statement: OpaquePointer, at index: Int32) throws {
        guard let value else {
            guard sqlite3_bind_null(statement, index) == SQLITE_OK else {
                throw SQLiteRuntimeChatEventStoreError("Could not bind runtime chat SQLite null.")
            }
            return
        }
        try bindText(value, to: statement, at: index)
    }

    private static func bindInt(_ value: Int, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_int64(statement, index, sqlite3_int64(value)) == SQLITE_OK else {
            throw SQLiteRuntimeChatEventStoreError("Could not bind runtime chat SQLite integer.")
        }
    }

    private static func bindDouble(_ value: Double, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_double(statement, index, value) == SQLITE_OK else {
            throw SQLiteRuntimeChatEventStoreError("Could not bind runtime chat SQLite double.")
        }
    }

    private static func bindBlob(_ value: Data, to statement: OpaquePointer, at index: Int32) throws {
        let result = value.withUnsafeBytes { bytes in
            sqlite3_bind_blob(statement, index, bytes.baseAddress, Int32(bytes.count), sqliteTransient)
        }
        guard result == SQLITE_OK else {
            throw SQLiteRuntimeChatEventStoreError("Could not bind runtime chat SQLite blob.")
        }
    }

    private static func stepDone(_ statement: OpaquePointer, database: OpaquePointer) throws {
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw failure(database, "Could not write runtime chat SQLite row.")
        }
    }

    private static func failure(_ database: OpaquePointer, _ fallback: String) -> SQLiteRuntimeChatEventStoreError {
        let message = sqlite3_errmsg(database).map { String(cString: $0) } ?? fallback
        return SQLiteRuntimeChatEventStoreError(message.isEmpty ? fallback : message)
    }

    private static func timestampString(from date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
    }

    private static func ownerKey(_ ownerDeviceID: String?) -> String {
        ownerDeviceID ?? ""
    }

    private static func validateSemanticEmbeddingKey(_ key: RuntimeChatSemanticEmbeddingKey) throws {
        guard key.ownerDeviceID == key.ownerDeviceID.sqliteNormalizedOwnerDeviceID else {
            throw SQLiteRuntimeChatEventStoreError("Runtime chat semantic embedding owner is not canonical.")
        }
        for (value, label) in [
            (key.sessionID, "session id"),
            (key.canonicalQualifiedEmbeddingModelID, "embedding model id"),
            (key.modelFingerprint, "model fingerprint"),
            (key.documentFingerprint, "document fingerprint"),
        ] {
            guard !value.isEmpty,
                  value == value.trimmingCharacters(in: .whitespacesAndNewlines),
                  !value.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else {
                throw SQLiteRuntimeChatEventStoreError(
                    "Runtime chat semantic embedding \(label) is not canonical."
                )
            }
        }
        guard let qualifiedModel = ModelProvider.splitQualifiedModelID(
            key.canonicalQualifiedEmbeddingModelID
        ),
              !qualifiedModel.modelID.isEmpty,
              qualifiedModel.provider.qualifiedModelID(qualifiedModel.modelID)
                == key.canonicalQualifiedEmbeddingModelID else {
            throw SQLiteRuntimeChatEventStoreError(
                "Runtime chat semantic embedding model id is not canonical and qualified."
            )
        }
    }

    private static func validateSemanticEmbeddingRecord(
        _ record: RuntimeChatSemanticEmbeddingRecord
    ) throws {
        try validateSemanticEmbeddingKey(record.key)
        guard !record.embedding.isEmpty,
              record.embedding.count <= semanticEmbeddingDimensionLimit,
              record.embedding.allSatisfy(\.isFinite),
              record.embedding.contains(where: { $0 != 0 }) else {
            throw SQLiteRuntimeChatEventStoreError(
                "Runtime chat semantic embedding vector must be finite, nonempty, and nonzero."
            )
        }
    }

    private static func encodeSemanticEmbedding(_ embedding: [Double]) -> Data {
        var data = Data(capacity: embedding.count * MemoryLayout<UInt64>.size)
        for value in embedding {
            var bits = value.bitPattern.littleEndian
            withUnsafeBytes(of: &bits) { data.append(contentsOf: $0) }
        }
        return data
    }

    private static func decodeSemanticEmbedding(_ data: Data, dimension: Int) -> [Double]? {
        guard dimension > 0,
              dimension <= semanticEmbeddingDimensionLimit,
              data.count == dimension * MemoryLayout<UInt64>.size else {
            return nil
        }
        var embedding: [Double] = []
        embedding.reserveCapacity(dimension)
        for offset in stride(from: 0, to: data.count, by: MemoryLayout<UInt64>.size) {
            var bits: UInt64 = 0
            _ = withUnsafeMutableBytes(of: &bits) { destination in
                data.copyBytes(to: destination, from: offset..<(offset + MemoryLayout<UInt64>.size))
            }
            embedding.append(Double(bitPattern: UInt64(littleEndian: bits)))
        }
        guard embedding.allSatisfy(\.isFinite),
              embedding.contains(where: { $0 != 0 }) else {
            return nil
        }
        return embedding
    }

    private static let legacyImportMetadataKey = "legacy_jsonl_imported"
    private static let legacyCompactionMetadataKey = "legacy_jsonl_retention_compacted"
    private static let incrementalSearchTableName = "runtime_chat_event_fts_v2"
    private static let incrementalSearchProjectionVersion = 2
    private static let semanticEmbeddingDimensionLimit = 65_536
}

private enum RuntimeChatRetentionScope {
    case owner(String?)
    case allOwners
}

private struct RuntimeChatIncrementalAppendState {
    var mutationRevision: Int64
    var validatedRevision: Int64
    var searchProjectionVersion: Int

    func isCurrent(searchProjectionVersion currentVersion: Int) -> Bool {
        mutationRevision == validatedRevision
            && searchProjectionVersion == currentVersion
    }
}

private enum RuntimeChatLegacyCompactionTiming: Equatable {
    case immediate
    case whenBatchDrained
}

private struct RuntimeChatRetentionSessionKey: Hashable {
    var ownerDeviceID: String?
    var sessionID: String

    init(ownerDeviceID: String?, sessionID: String) {
        self.ownerDeviceID = ownerDeviceID.sqliteNormalizedOwnerDeviceID
        self.sessionID = sessionID
    }
}

private struct RuntimeChatRetentionCandidate {
    var key: RuntimeChatRetentionSessionKey
    var deletedAt: String
}

private struct RuntimeChatLegacyJSONLRecord {
    var line: Int
    var event: RuntimeChatStoredEvent
    var rawLine: Data
}

private struct RuntimeChatLegacyJSONLSnapshot {
    var signature: String
    var data: Data
    var records: [RuntimeChatLegacyJSONLRecord]
}

private struct RuntimeChatSemanticEmbeddingScope: Hashable {
    var ownerKey: String
    var embeddingModelID: String

    init(key: RuntimeChatSemanticEmbeddingKey) {
        self.ownerKey = key.ownerDeviceID ?? ""
        self.embeddingModelID = key.canonicalQualifiedEmbeddingModelID
    }
}

private let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

private struct SQLiteRuntimeChatEventStoreError: LocalizedError {
    var message: String

    init(_ message: String) {
        self.message = message
    }

    var errorDescription: String? {
        message
    }
}

private extension Optional where Wrapped == String {
    var sqliteNormalizedOwnerDeviceID: String? {
        guard let value = self?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else {
            return nil
        }
        return value
    }
}
