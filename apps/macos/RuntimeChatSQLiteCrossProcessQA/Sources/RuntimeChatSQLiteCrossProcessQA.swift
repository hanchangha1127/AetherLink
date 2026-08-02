@testable import CompanionCore
import Darwin
import Foundation
import OllamaBackend
import SQLite3

private let databaseFilename = "runtime-chat-events.sqlite"
private let gateFilename = "start-gate"
private let abruptCheckpointFilename = "abrupt-checkpoint-v1.json"
private let productionAppendCheckpointFilename =
    "production-append-checkpoint-v1.json"
private let sharedSessionID = "qa-shared-session"
private let modelID = "ollama:llama3.1:8b"
private let eventCountPerWriter = 48
private let abruptCommittedPrefixCount = 24
private let abruptInFlightEventID = "qa-writer-a-inflight-uncommitted-v1"
private let abruptInFlightRequestID = "qa-writer-a-inflight-request-v1"
private let abruptInFlightContent = "writer-a-inflight-uncommitted-v1"
private let gateTimeoutNanoseconds: UInt64 = 10_000_000_000
private let sqliteTransientQA = unsafeBitCast(
    -1,
    to: sqlite3_destructor_type.self
)

private enum HelperError: Error, LocalizedError {
    case invalidArguments
    case invalidDatabaseRoot
    case unsupportedWriter
    case gateTimeout
    case sqliteFailure
    case checkpointFailure
    case outputFailure

    var errorDescription: String? {
        switch self {
        case .invalidArguments:
            return "arguments are invalid"
        case .invalidDatabaseRoot:
            return "database root is invalid"
        case .unsupportedWriter:
            return "writer is unsupported"
        case .gateTimeout:
            return "start gate timed out"
        case .sqliteFailure:
            return "SQLite readback failed"
        case .checkpointFailure:
            return "abrupt-termination checkpoint failed"
        case .outputFailure:
            return "result encoding failed"
        }
    }
}

private enum Writer: String, CaseIterable {
    case writerA = "writer-a"
    case writerB = "writer-b"

    var ownerDeviceID: String {
        switch self {
        case .writerA: "qa-owner-a"
        case .writerB: "qa-owner-b"
        }
    }

    var eventPrefix: String {
        switch self {
        case .writerA: "qa-writer-a-event"
        case .writerB: "qa-writer-b-event"
        }
    }

    var requestPrefix: String {
        switch self {
        case .writerA: "qa-writer-a-request"
        case .writerB: "qa-writer-b-request"
        }
    }

    var contentPrefix: String {
        switch self {
        case .writerA: "writer-a-message"
        case .writerB: "writer-b-message"
        }
    }

    var timestampOffset: TimeInterval {
        switch self {
        case .writerA: 0
        case .writerB: 1_000
        }
    }
}

private struct WriteResult: Encodable {
    var eventCount: Int
    var status: String
    var writer: String
}

private struct ResumeWriteResult: Encodable {
    var endExclusive: Int
    var eventCount: Int
    var startOrdinal: Int
    var status: String
    var writer: String
}

private struct AbruptCheckpoint: Encodable {
    var committedPrefixCount: Int
    var databaseCacheFlushed: Bool
    var inFlightEventID: String
    var insideTransactionEventCount: Int
    var insideTransactionFTSEventCount: Int
    var insideTransactionMutationRevision: Int
    var insideTransactionValidatedRevision: Int
    var journalMode: String
    var schemaVersion: Int
    var status: String
    var transactionOpen: Bool
    var writer: String
}

private struct ProductionAppendCheckpoint: Encodable {
    var databaseCacheFlushed: Bool
    var eventID: String
    var ownerDeviceID: String
    var phase: String
    var requestID: String
    var schemaVersion: Int
    var status: String
    var transactionOpen: Bool
    var writePath: String
    var writer: String
}

private struct ReadbackRow: Encodable {
    var sequence: Int64
    var eventID: String
    var kind: String
    var requestID: String
    var sessionID: String
    var ownerDeviceID: String?
}

private struct ReadbackSession: Encodable {
    var sessionID: String
    var messageCount: Int
}

private struct OwnerProjection: Encodable {
    var ownerDeviceID: String
    var sessions: [ReadbackSession]
    var messageContents: [String]
}

private struct ReadbackResult: Encodable {
    var hostWideSessionCount: Int
    var missingOwnerSessionCount: Int
    var ownerProjections: [OwnerProjection]
    var rows: [ReadbackRow]
    var status: String
    var unownedSessionCount: Int
}

@main
private struct RuntimeChatSQLiteCrossProcessQA {
    static func main() {
        do {
            try run()
        } catch {
            let message = "Runtime-chat SQLite cross-process QA helper failed: "
                + ((error as? LocalizedError)?.errorDescription ?? "unknown failure")
                + "\n"
            FileHandle.standardError.write(Data(message.utf8))
            Darwin.exit(1)
        }
    }

    private static func run() throws {
        let arguments = Array(CommandLine.arguments.dropFirst())
        guard arguments.count >= 3,
              arguments[1] == "--database-root" else {
            throw HelperError.invalidArguments
        }
        let databaseRoot = try validatedDatabaseRoot(arguments[2])
        let databaseURL = databaseRoot.appendingPathComponent(databaseFilename, isDirectory: false)

        switch arguments[0] {
        case "write":
            guard arguments.count == 5,
                  arguments[3] == "--writer",
                  let writer = Writer(rawValue: arguments[4]) else {
                throw arguments.count == 5 ? HelperError.unsupportedWriter : HelperError.invalidArguments
            }
            try awaitStartGate(in: databaseRoot)
            try write(
                writer: writer,
                ordinals: 0..<eventCountPerWriter,
                databaseURL: databaseURL
            )
            try writeJSON(WriteResult(
                eventCount: eventCountPerWriter,
                status: "passed",
                writer: writer.rawValue
            ))
        case "production-append":
            guard arguments.count == 5,
                  arguments[3] == "--writer",
                  let writer = Writer(rawValue: arguments[4]),
                  writer == .writerA else {
                throw arguments.count == 5 ? HelperError.unsupportedWriter : HelperError.invalidArguments
            }
            let appendEvent = event(writer: writer, ordinal: 0)
            let instrumentation = SQLiteRuntimeChatEventStoreAppendInstrumentation(
                didFlushDatabaseCacheBeforeCommit: {
                    try writeCheckpoint(
                        ProductionAppendCheckpoint(
                            databaseCacheFlushed: true,
                            eventID: appendEvent.id,
                            ownerDeviceID: writer.ownerDeviceID,
                            phase: "after-validated-state-and-cache-flush-before-commit",
                            requestID: appendEvent.requestID,
                            schemaVersion: 1,
                            status: "ready-for-abrupt-termination",
                            transactionOpen: true,
                            writePath: "SQLiteRuntimeChatEventStore.append",
                            writer: writer.rawValue
                        ),
                        to: databaseRoot.appendingPathComponent(
                            productionAppendCheckpointFilename,
                            isDirectory: false
                        )
                    )
                    try awaitStartGate(in: databaseRoot)
                }
            )
            let store = SQLiteRuntimeChatEventStore(
                databaseURL: databaseURL,
                appendInstrumentation: instrumentation
            )
            try store.append(appendEvent)
            try writeJSON(WriteResult(
                eventCount: 1,
                status: "unexpectedly-committed",
                writer: writer.rawValue
            ))
        case "abrupt-prefix":
            guard arguments.count == 5,
                  arguments[3] == "--writer",
                  let writer = Writer(rawValue: arguments[4]),
                  writer == .writerA else {
                throw arguments.count == 5 ? HelperError.unsupportedWriter : HelperError.invalidArguments
            }
            try prepareAbruptTermination(
                writer: writer,
                databaseRoot: databaseRoot,
                databaseURL: databaseURL
            )
        case "resume":
            guard arguments.count == 5,
                  arguments[3] == "--writer",
                  let writer = Writer(rawValue: arguments[4]),
                  writer == .writerA else {
                throw arguments.count == 5 ? HelperError.unsupportedWriter : HelperError.invalidArguments
            }
            try write(
                writer: writer,
                ordinals: abruptCommittedPrefixCount..<eventCountPerWriter,
                databaseURL: databaseURL
            )
            try writeJSON(ResumeWriteResult(
                endExclusive: eventCountPerWriter,
                eventCount: eventCountPerWriter - abruptCommittedPrefixCount,
                startOrdinal: abruptCommittedPrefixCount,
                status: "passed",
                writer: writer.rawValue
            ))
        case "read":
            guard arguments.count == 3 else {
                throw HelperError.invalidArguments
            }
            try read(databaseURL: databaseURL)
        default:
            throw HelperError.invalidArguments
        }
    }

    private static func validatedDatabaseRoot(_ value: String) throws -> URL {
        guard value.hasPrefix("/"),
              !value.contains("\0") else {
            throw HelperError.invalidDatabaseRoot
        }
        let root = URL(fileURLWithPath: value, isDirectory: true)
        guard root.standardizedFileURL.path == root.path else {
            throw HelperError.invalidDatabaseRoot
        }
        var status = stat()
        guard lstat(root.path, &status) == 0,
              (status.st_mode & S_IFMT) == S_IFDIR,
              (status.st_mode & mode_t(0o077)) == 0 else {
            throw HelperError.invalidDatabaseRoot
        }
        return root
    }

    private static func awaitStartGate(in databaseRoot: URL) throws {
        let gateURL = databaseRoot.appendingPathComponent(gateFilename, isDirectory: false)
        let deadline = DispatchTime.now().uptimeNanoseconds + gateTimeoutNanoseconds
        while DispatchTime.now().uptimeNanoseconds < deadline {
            var status = stat()
            if lstat(gateURL.path, &status) == 0 {
                guard (status.st_mode & S_IFMT) == S_IFREG,
                      (status.st_mode & mode_t(0o077)) == 0 else {
                    throw HelperError.invalidDatabaseRoot
                }
                return
            }
            usleep(10_000)
        }
        throw HelperError.gateTimeout
    }

    private static func event(
        writer: Writer,
        ordinal: Int
    ) -> RuntimeChatStoredEvent {
        let suffix = String(format: "%04d", ordinal)
        return RuntimeChatStoredEvent(
            id: "\(writer.eventPrefix)-\(suffix)",
            timestamp: Date(
                timeIntervalSince1970: 1_700_000_000
                    + writer.timestampOffset
                    + TimeInterval(ordinal)
            ),
            kind: .request,
            requestID: "\(writer.requestPrefix)-\(suffix)",
            sessionID: sharedSessionID,
            model: modelID,
            messages: [
                ChatMessage(
                    role: "user",
                    content: "\(writer.contentPrefix)-\(suffix)"
                )
            ],
            ownerDeviceID: writer.ownerDeviceID
        )
    }

    private static func write(
        writer: Writer,
        ordinals: Range<Int>,
        databaseURL: URL
    ) throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        for ordinal in ordinals {
            try store.append(event(writer: writer, ordinal: ordinal))
            usleep(1_000)
        }
    }

    private static func prepareAbruptTermination(
        writer: Writer,
        databaseRoot: URL,
        databaseURL: URL
    ) throws {
        try write(
            writer: writer,
            ordinals: 0..<abruptCommittedPrefixCount,
            databaseURL: databaseURL
        )

        var database: OpaquePointer?
        let flags = SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX
        guard sqlite3_open_v2(databaseURL.path, &database, flags, nil) == SQLITE_OK,
              let openedDatabase = database else {
            if let database {
                sqlite3_close(database)
            }
            throw HelperError.sqliteFailure
        }
        defer { sqlite3_close(openedDatabase) }
        guard sqlite3_busy_timeout(openedDatabase, 2_000) == SQLITE_OK,
              sqlite3_exec(
                openedDatabase,
                "PRAGMA foreign_keys = ON",
                nil,
                nil,
                nil
              ) == SQLITE_OK,
              try journalMode(openedDatabase) == "delete",
              sqlite3_exec(
                openedDatabase,
                "BEGIN IMMEDIATE",
                nil,
                nil,
                nil
              ) == SQLITE_OK else {
            throw HelperError.sqliteFailure
        }
        do {
            let inFlight = RuntimeChatStoredEvent(
                id: abruptInFlightEventID,
                timestamp: Date(timeIntervalSince1970: 1_700_100_000),
                kind: .request,
                requestID: abruptInFlightRequestID,
                sessionID: sharedSessionID,
                model: modelID,
                messages: [
                    ChatMessage(
                        role: "user",
                        content: abruptInFlightContent
                    )
                ],
                ownerDeviceID: writer.ownerDeviceID
            )
            try insertRawEvent(inFlight, database: openedDatabase)
            try insertRawFTSEvent(
                inFlight,
                ownerDeviceID: writer.ownerDeviceID,
                database: openedDatabase
            )
            guard sqlite3_db_cacheflush(openedDatabase) == SQLITE_OK else {
                throw HelperError.sqliteFailure
            }
            let eventCount = try scalarInt(
                openedDatabase,
                sql: "SELECT COUNT(*) FROM runtime_chat_events"
            )
            let ftsCount = try scalarInt(
                openedDatabase,
                sql: "SELECT COUNT(*) FROM runtime_chat_event_fts_v2"
            )
            let revisions = try appendStateRevisions(openedDatabase)
            guard sqlite3_get_autocommit(openedDatabase) == 0,
                  eventCount == abruptCommittedPrefixCount + 1,
                  ftsCount == abruptCommittedPrefixCount + 1,
                  revisions.mutation == abruptCommittedPrefixCount + 1,
                  revisions.validated == abruptCommittedPrefixCount else {
                throw HelperError.sqliteFailure
            }
            try writeCheckpoint(
                AbruptCheckpoint(
                    committedPrefixCount: abruptCommittedPrefixCount,
                    databaseCacheFlushed: true,
                    inFlightEventID: abruptInFlightEventID,
                    insideTransactionEventCount: eventCount,
                    insideTransactionFTSEventCount: ftsCount,
                    insideTransactionMutationRevision: revisions.mutation,
                    insideTransactionValidatedRevision: revisions.validated,
                    journalMode: "delete",
                    schemaVersion: 1,
                    status: "ready-for-abrupt-termination",
                    transactionOpen: true,
                    writer: writer.rawValue
                ),
                to: databaseRoot.appendingPathComponent(
                    abruptCheckpointFilename,
                    isDirectory: false
                )
            )
            while true {
                usleep(100_000)
            }
        } catch {
            sqlite3_exec(openedDatabase, "ROLLBACK", nil, nil, nil)
            throw error
        }
    }

    private static func insertRawEvent(
        _ event: RuntimeChatStoredEvent,
        database: OpaquePointer
    ) throws {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        let eventData = try encoder.encode(event)
        guard let eventJSON = String(data: eventData, encoding: .utf8) else {
            throw HelperError.sqliteFailure
        }
        let timestamp = ISO8601DateFormatter().string(from: event.timestamp)
        var statement: OpaquePointer?
        let sql = """
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
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let prepared = statement else {
            throw HelperError.sqliteFailure
        }
        defer { sqlite3_finalize(prepared) }
        let values = [
            event.id,
            timestamp,
            event.kind.rawValue,
            event.requestID,
            event.sessionID,
            event.ownerDeviceID ?? "",
            event.model,
            eventJSON,
        ]
        for (offset, value) in values.enumerated() {
            guard sqlite3_bind_text(
                prepared,
                Int32(offset + 1),
                value,
                -1,
                sqliteTransientQA
            ) == SQLITE_OK else {
                throw HelperError.sqliteFailure
            }
        }
        guard sqlite3_step(prepared) == SQLITE_DONE else {
            throw HelperError.sqliteFailure
        }
    }

    private static func insertRawFTSEvent(
        _ event: RuntimeChatStoredEvent,
        ownerDeviceID: String,
        database: OpaquePointer
    ) throws {
        var statement: OpaquePointer?
        let sql = """
            INSERT INTO runtime_chat_event_fts_v2(
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
            ) VALUES (?, ?, ?, '', ?, ?, '', '', ?, '', '')
            """
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let prepared = statement else {
            throw HelperError.sqliteFailure
        }
        defer { sqlite3_finalize(prepared) }
        let values = [
            event.id,
            ownerDeviceID,
            event.sessionID,
            event.sessionID,
            event.model,
            abruptInFlightContent,
        ]
        for (offset, value) in values.enumerated() {
            guard sqlite3_bind_text(
                prepared,
                Int32(offset + 1),
                value,
                -1,
                sqliteTransientQA
            ) == SQLITE_OK else {
                throw HelperError.sqliteFailure
            }
        }
        guard sqlite3_step(prepared) == SQLITE_DONE else {
            throw HelperError.sqliteFailure
        }
    }

    private static func journalMode(
        _ database: OpaquePointer
    ) throws -> String {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(
            database,
            "PRAGMA journal_mode",
            -1,
            &statement,
            nil
        ) == SQLITE_OK,
        let prepared = statement else {
            throw HelperError.sqliteFailure
        }
        defer { sqlite3_finalize(prepared) }
        guard sqlite3_step(prepared) == SQLITE_ROW else {
            throw HelperError.sqliteFailure
        }
        return try requiredText(prepared, column: 0)
    }

    private static func scalarInt(
        _ database: OpaquePointer,
        sql: String
    ) throws -> Int {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let prepared = statement else {
            throw HelperError.sqliteFailure
        }
        defer { sqlite3_finalize(prepared) }
        guard sqlite3_step(prepared) == SQLITE_ROW,
              sqlite3_column_type(prepared, 0) == SQLITE_INTEGER else {
            throw HelperError.sqliteFailure
        }
        return Int(sqlite3_column_int64(prepared, 0))
    }

    private static func appendStateRevisions(
        _ database: OpaquePointer
    ) throws -> (mutation: Int, validated: Int) {
        var statement: OpaquePointer?
        let sql = """
            SELECT mutation_revision, validated_revision
            FROM runtime_chat_append_state
            WHERE singleton = 1
            """
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let prepared = statement else {
            throw HelperError.sqliteFailure
        }
        defer { sqlite3_finalize(prepared) }
        guard sqlite3_step(prepared) == SQLITE_ROW,
              sqlite3_column_type(prepared, 0) == SQLITE_INTEGER,
              sqlite3_column_type(prepared, 1) == SQLITE_INTEGER else {
            throw HelperError.sqliteFailure
        }
        let result = (
            mutation: Int(sqlite3_column_int64(prepared, 0)),
            validated: Int(sqlite3_column_int64(prepared, 1))
        )
        guard sqlite3_step(prepared) == SQLITE_DONE else {
            throw HelperError.sqliteFailure
        }
        return result
    }

    private static func writeCheckpoint<T: Encodable>(
        _ value: T,
        to url: URL
    ) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        var data = try encoder.encode(value)
        data.append(0x0A)
        guard data.count <= 4_096 else {
            throw HelperError.checkpointFailure
        }
        let flags = O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW
        let descriptor = Darwin.open(url.path, flags, mode_t(0o600))
        guard descriptor >= 0 else {
            throw HelperError.checkpointFailure
        }
        var writeFailed = false
        data.withUnsafeBytes { rawBuffer in
            guard let baseAddress = rawBuffer.baseAddress else {
                writeFailed = true
                return
            }
            var written = 0
            while written < rawBuffer.count {
                let result = Darwin.write(
                    descriptor,
                    baseAddress.advanced(by: written),
                    rawBuffer.count - written
                )
                if result <= 0 {
                    writeFailed = true
                    return
                }
                written += result
            }
        }
        if writeFailed || fsync(descriptor) != 0 {
            _ = close(descriptor)
            throw HelperError.checkpointFailure
        }
        if close(descriptor) != 0 {
            throw HelperError.checkpointFailure
        }
        var status = stat()
        guard lstat(url.path, &status) == 0,
              (status.st_mode & S_IFMT) == S_IFREG,
              (status.st_mode & mode_t(0o077)) == 0,
              status.st_size == data.count else {
            throw HelperError.checkpointFailure
        }
    }

    private static func read(databaseURL: URL) throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let projections = try Writer.allCases.map { writer in
            OwnerProjection(
                ownerDeviceID: writer.ownerDeviceID,
                sessions: try store.listSessions(
                    ownerDeviceID: writer.ownerDeviceID,
                    limit: 10,
                    includeArchived: true
                ).map {
                    ReadbackSession(
                        sessionID: $0.sessionID,
                        messageCount: $0.messageCount
                    )
                },
                messageContents: try store.listMessages(
                    ownerDeviceID: writer.ownerDeviceID,
                    sessionID: sharedSessionID,
                    limit: eventCountPerWriter + 1
                ).map(\.content)
            )
        }
        let result = ReadbackResult(
            hostWideSessionCount: try store.listAllSessions(
                limit: 10,
                includeArchived: true
            ).count,
            missingOwnerSessionCount: try store.listSessions(
                ownerDeviceID: "qa-owner-missing",
                limit: 10,
                includeArchived: true
            ).count,
            ownerProjections: projections,
            rows: try rawRows(databaseURL: databaseURL),
            status: "passed",
            unownedSessionCount: try store.listSessions(
                ownerDeviceID: nil,
                limit: 10,
                includeArchived: true
            ).count
        )
        try writeJSON(result)
    }

    private static func rawRows(databaseURL: URL) throws -> [ReadbackRow] {
        var database: OpaquePointer?
        let flags = SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX
        guard sqlite3_open_v2(databaseURL.path, &database, flags, nil) == SQLITE_OK,
              let openedDatabase = database else {
            if let database {
                sqlite3_close(database)
            }
            throw HelperError.sqliteFailure
        }
        defer { sqlite3_close(openedDatabase) }
        guard sqlite3_busy_timeout(openedDatabase, 2_000) == SQLITE_OK,
              sqlite3_exec(openedDatabase, "PRAGMA query_only = ON", nil, nil, nil) == SQLITE_OK else {
            throw HelperError.sqliteFailure
        }

        var statement: OpaquePointer?
        let sql = """
            SELECT sequence, event_id, kind, request_id, session_id, owner_device_id
            FROM runtime_chat_events
            ORDER BY sequence ASC
            """
        guard sqlite3_prepare_v2(openedDatabase, sql, -1, &statement, nil) == SQLITE_OK,
              let prepared = statement else {
            throw HelperError.sqliteFailure
        }
        defer { sqlite3_finalize(prepared) }

        var rows: [ReadbackRow] = []
        while true {
            switch sqlite3_step(prepared) {
            case SQLITE_ROW:
                rows.append(ReadbackRow(
                    sequence: sqlite3_column_int64(prepared, 0),
                    eventID: try requiredText(prepared, column: 1),
                    kind: try requiredText(prepared, column: 2),
                    requestID: try requiredText(prepared, column: 3),
                    sessionID: try requiredText(prepared, column: 4),
                    ownerDeviceID: optionalText(prepared, column: 5)
                ))
            case SQLITE_DONE:
                return rows
            default:
                throw HelperError.sqliteFailure
            }
        }
    }

    private static func requiredText(
        _ statement: OpaquePointer,
        column: Int32
    ) throws -> String {
        guard let value = sqlite3_column_text(statement, column) else {
            throw HelperError.sqliteFailure
        }
        return String(cString: value)
    }

    private static func optionalText(
        _ statement: OpaquePointer,
        column: Int32
    ) -> String? {
        guard sqlite3_column_type(statement, column) != SQLITE_NULL,
              let value = sqlite3_column_text(statement, column) else {
            return nil
        }
        return String(cString: value)
    }

    private static func writeJSON<T: Encodable>(_ value: T) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let data = try encoder.encode(value)
        guard data.count <= 65_536 else {
            throw HelperError.outputFailure
        }
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([0x0A]))
    }
}
