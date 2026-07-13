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

public final class SQLiteRuntimeChatEventStore: RuntimeChatEventStore, @unchecked Sendable {
    private let databaseURL: URL
    private let legacyJSONLFileURL: URL?
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder
    private let semanticEmbeddingRowLimitPerOwnerModel: Int
    private let lock = NSLock()

    public init(
        databaseURL: URL = SQLiteRuntimeChatEventStore.defaultDatabaseURL(),
        legacyJSONLFileURL: URL? = nil,
        semanticEmbeddingRowLimitPerOwnerModel: Int = 10_000
    ) {
        self.databaseURL = databaseURL
        self.legacyJSONLFileURL = legacyJSONLFileURL
        self.semanticEmbeddingRowLimitPerOwnerModel = max(1, semanticEmbeddingRowLimitPerOwnerModel)
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
                let scopedOwnerDeviceID = ownerDeviceID.sqliteNormalizedOwnerDeviceID
                let candidateIDs = try ftsCandidateSessionIDsUnlocked(
                    database,
                    ownerDeviceID: scopedOwnerDeviceID,
                    query: searchQuery
                )
                guard !candidateIDs.isEmpty else { return [] }

                let ownerEvents = try readEventsUnlocked(database, matchingOwnerDeviceID: scopedOwnerDeviceID)
                let candidateIDSet = Set(candidateIDs)
                let candidates = try JSONLRuntimeChatEventStore.sessions(
                    from: ownerEvents,
                    limit: Int.max,
                    includeArchived: includeArchived
                )
                .filter { candidateIDSet.contains($0.sessionID) }
                var matches: [(session: RuntimeChatStoredSession, match: RuntimeChatSessionSearchMatch)] = []
                for session in candidates {
                    let messages = JSONLRuntimeChatEventStore.messages(
                        from: ownerEvents,
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
                        return lhs.session.lastActivityAt > rhs.session.lastActivityAt
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
        guard limit > 0 else {
            return RuntimeChatDeletedSessionPruneResult(prunedSessionIDs: [], prunedEventCount: 0)
        }
        return try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let result = try pruneDeletedSessionsUnlocked(
                        database,
                        ownerDeviceID: ownerDeviceID.sqliteNormalizedOwnerDeviceID,
                        deletedBefore: cutoff,
                        limit: limit
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
                JSONLRuntimeChatEventStore.messages(
                    from: try readEventsUnlocked(database),
                    sessionID: sessionID,
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
        if sanitized.compactionResolution != nil {
            let existingEvents = try readEventsUnlocked(database)
            try JSONLRuntimeChatEventStore.validateCompactionResolutionBindings(
                existingEvents.enumerated().map { (line: $0.offset + 1, event: $0.element) }
                    + [(line: 0, event: sanitized)]
            )
        }
        if try eventExistsUnlocked(database, eventID: sanitized.id) {
            throw SQLiteRuntimeChatEventStoreError("Runtime chat SQLite event already exists: \(sanitized.id)")
        }
        try insertEventUnlocked(sanitized, database: database, skipExisting: false)
        try rebuildSearchIndexUnlocked(database)
        try deleteSemanticEmbeddingsUnlocked(
            database,
            ownerDeviceID: sanitized.ownerDeviceID.sqliteNormalizedOwnerDeviceID,
            sessionID: sanitized.sessionID
        )
    }

    @discardableResult
    private func insertEventUnlocked(
        _ event: RuntimeChatStoredEvent,
        database: OpaquePointer,
        skipExisting: Bool
    ) throws -> Bool {
        let ownerDeviceID = event.ownerDeviceID.sqliteNormalizedOwnerDeviceID
        if try retentionTombstoneExistsUnlocked(
            database,
            ownerDeviceID: ownerDeviceID,
            sessionID: event.sessionID
        ) {
            if skipExisting { return false }
            throw SQLiteRuntimeChatEventStoreError(
                "Runtime chat SQLite session was pruned by retention: \(event.sessionID)"
            )
        }
        if skipExisting, try eventExistsUnlocked(database, eventID: event.id) {
            return false
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
        return true
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
                let event = try decoder.decode(RuntimeChatStoredEvent.self, from: data)
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

    private func rebuildSearchIndexUnlocked(_ database: OpaquePointer) throws {
        try Self.execute(database, "DELETE FROM runtime_chat_session_fts")
        let events = try readEventsUnlocked(database)
        let ownerDeviceIDs = Array(Set(events.map(\.ownerDeviceID)))
        for ownerDeviceID in ownerDeviceIDs {
            let ownerEvents = events.filter { $0.ownerDeviceID == ownerDeviceID }
            let sessions = try JSONLRuntimeChatEventStore.sessions(
                from: ownerEvents,
                limit: Int.max,
                includeArchived: true
            )
            for session in sessions {
                let messages = JSONLRuntimeChatEventStore.messages(
                    from: ownerEvents,
                    sessionID: session.sessionID,
                    limit: Int.max
                )
                try insertSearchRowUnlocked(
                    database,
                    ownerDeviceID: ownerDeviceID,
                    session: session,
                    messages: messages
                )
            }
        }
    }

    private func insertSearchRowUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        session: RuntimeChatStoredSession,
        messages: [RuntimeChatStoredMessage]
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_chat_session_fts(
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        let metadata = [
            session.lastEvent,
            session.lastFinishReason,
            session.lastErrorCode
        ]
        .compactMap { $0?.runtimeSearchSnippetText }
        .joined(separator: " ")
        let transcript = messages
            .map(\.content.runtimeSearchSnippetText)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
        let reasoning = messages
            .compactMap(\.reasoning?.runtimeSearchSnippetText)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
        let attachment = messages
            .flatMap(\.attachments)
            .flatMap { attachment in
                [
                    attachment.name?.runtimeSearchSnippetText,
                    attachment.mimeType.runtimeSearchSnippetText,
                    attachment.text?.runtimeSearchSnippetText
                ]
            }
            .compactMap { $0 }
            .filter { !$0.isEmpty }
            .joined(separator: " ")

        try Self.bindText(Self.ownerKey(ownerDeviceID), to: statement, at: 1)
        try Self.bindText(session.sessionID, to: statement, at: 2)
        try Self.bindText(session.title.runtimeSearchSnippetText, to: statement, at: 3)
        try Self.bindText(session.sessionID.runtimeSearchSnippetText, to: statement, at: 4)
        try Self.bindText(session.model.runtimeSearchSnippetText, to: statement, at: 5)
        try Self.bindText(session.status.runtimeSearchSnippetText, to: statement, at: 6)
        try Self.bindText(metadata, to: statement, at: 7)
        try Self.bindText(transcript, to: statement, at: 8)
        try Self.bindText(reasoning, to: statement, at: 9)
        try Self.bindText(attachment, to: statement, at: 10)
        try Self.stepDone(statement, database: database)
    }

    private func ftsCandidateSessionIDsUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        query: RuntimeChatSessionSearchQuery
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT session_id
            FROM runtime_chat_session_fts
            WHERE owner_key = ?
              AND runtime_chat_session_fts MATCH ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(ownerDeviceID), to: statement, at: 1)
        try Self.bindText(Self.ftsMatchQuery(for: query), to: statement, at: 2)

        var sessionIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime chat FTS candidates.")
            }
            if let text = sqlite3_column_text(statement, 0) {
                sessionIDs.append(String(cString: text))
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
        ownerDeviceID: String?,
        deletedBefore cutoff: Date,
        limit: Int
    ) throws -> RuntimeChatDeletedSessionPruneResult {
        let events = try readEventsUnlocked(database, matchingOwnerDeviceID: ownerDeviceID)
        let candidates = Dictionary(grouping: events.enumerated(), by: { $0.element.sessionID })
            .compactMap { sessionID, sessionEvents -> RuntimeChatRetentionCandidate? in
                guard let lifecycleEvent = Self.latestLifecycleEvent(from: sessionEvents),
                      lifecycleEvent.event.kind == .deleted,
                      lifecycleEvent.event.timestamp < cutoff else {
                    return nil
                }
                return RuntimeChatRetentionCandidate(
                    sessionID: sessionID,
                    deletedAt: lifecycleEvent.event.timestamp,
                    eventCount: sessionEvents.count
                )
            }
            .sorted { lhs, rhs in
                if lhs.deletedAt == rhs.deletedAt {
                    return lhs.sessionID < rhs.sessionID
                }
                return lhs.deletedAt < rhs.deletedAt
            }
            .prefix(limit)

        var prunedSessionIDs: [String] = []
        var prunedEventCount = 0
        for candidate in candidates {
            try recordRetentionTombstoneUnlocked(
                database,
                ownerDeviceID: ownerDeviceID,
                sessionID: candidate.sessionID,
                deletedAt: candidate.deletedAt
            )
            prunedEventCount += try deleteEventsUnlocked(
                database,
                ownerDeviceID: ownerDeviceID,
                sessionID: candidate.sessionID
            )
            try deleteSemanticEmbeddingsUnlocked(
                database,
                ownerDeviceID: ownerDeviceID,
                sessionID: candidate.sessionID
            )
            prunedSessionIDs.append(candidate.sessionID)
        }
        if prunedEventCount > 0 {
            try rebuildSearchIndexUnlocked(database)
        }
        return RuntimeChatDeletedSessionPruneResult(
            prunedSessionIDs: prunedSessionIDs,
            prunedEventCount: prunedEventCount
        )
    }

    private func recordRetentionTombstoneUnlocked(
        _ database: OpaquePointer,
        ownerDeviceID: String?,
        sessionID: String,
        deletedAt: Date
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
        try Self.bindText(Self.timestampString(from: deletedAt), to: statement, at: 3)
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

    private func withDatabase<T>(_ body: (OpaquePointer) throws -> T) throws -> T {
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
        try importLegacyJSONLIfNeeded(openedDatabase)
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        return try body(openedDatabase)
    }

    private static func ensureSchema(_ database: OpaquePointer) throws {
        try execute(database, "PRAGMA foreign_keys = ON")
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
            "CREATE INDEX IF NOT EXISTS idx_runtime_chat_events_timestamp ON runtime_chat_events(timestamp)"
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
    }

    private func importLegacyJSONLIfNeeded(_ database: OpaquePointer) throws {
        guard let legacyJSONLFileURL else { return }
        let legacyPath = legacyJSONLFileURL.standardizedFileURL.path
        guard FileManager.default.fileExists(atPath: legacyPath) else { return }
        let legacySignature = try Self.legacyImportSignature(for: legacyJSONLFileURL)
        if try Self.metadataValue(database, key: Self.legacyImportMetadataKey) == legacySignature {
            return
        }

        let legacyEvents = try JSONLRuntimeChatEventStore.events(from: legacyJSONLFileURL)
        var importedAnyEvent = false
        for legacyEvent in legacyEvents {
            let sanitized = legacyEvent.sanitizedForStorage()
            try JSONLRuntimeChatEventStore.validateStoredEvent(sanitized, line: 0)
            let inserted = try insertEventUnlocked(sanitized, database: database, skipExisting: true)
            importedAnyEvent = importedAnyEvent || inserted
        }
        if importedAnyEvent {
            try rebuildSearchIndexUnlocked(database)
        }
        try Self.setMetadataValue(database, key: Self.legacyImportMetadataKey, value: legacySignature)
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

    private static func ftsMatchQuery(for query: RuntimeChatSessionSearchQuery) -> String {
        query.terms
            .map { term in
                "\"\(term.replacingOccurrences(of: "\"", with: "\"\""))\""
            }
            .joined(separator: " AND ")
    }

    private static func latestLifecycleEvent(
        from events: [EnumeratedSequence<[RuntimeChatStoredEvent]>.Element]
    ) -> (offset: Int, event: RuntimeChatStoredEvent)? {
        events
            .filter { $0.element.kind.isSQLiteSessionLifecycle }
            .max { lhs, rhs in
                if lhs.element.timestamp == rhs.element.timestamp {
                    return lhs.offset < rhs.offset
                }
                return lhs.element.timestamp < rhs.element.timestamp
            }
            .map { (offset: $0.offset, event: $0.element) }
    }

    private static let legacyImportMetadataKey = "legacy_jsonl_imported"
    private static let semanticEmbeddingDimensionLimit = 65_536
}

private struct RuntimeChatRetentionCandidate {
    var sessionID: String
    var deletedAt: Date
    var eventCount: Int
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

private extension RuntimeChatStoredEventKind {
    var isSQLiteSessionLifecycle: Bool {
        switch self {
        case .archived, .restored, .deleted:
            return true
        default:
            return false
        }
    }
}
