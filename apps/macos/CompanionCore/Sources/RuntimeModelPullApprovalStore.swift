import Foundation
import SQLite3

public enum RuntimeModelPullApprovalProvider: String, CaseIterable, Sendable {
    case ollama
}

public enum RuntimeModelPullApprovalEvent: String, CaseIterable, Sendable {
    case requested
    case dispatchReserved = "dispatch_reserved"
    case success
    case failure
    case resultSuppressed = "result_suppressed"
    case dismissal
    case expiry
    case connectionClosed = "connection_closed"
    case authenticationChanged = "authentication_changed"
    case permissionChanged = "permission_changed"
    case hostRestarted = "host_restarted"

    fileprivate var outcome: RuntimeModelPullApprovalOutcome {
        switch self {
        case .requested, .dispatchReserved:
            return .none
        case .success:
            return .success
        case .failure:
            return .failure
        case .resultSuppressed:
            return .resultSuppressed
        case .dismissal:
            return .dismissal
        case .expiry:
            return .expiry
        case .connectionClosed:
            return .connectionClosed
        case .authenticationChanged:
            return .authenticationChanged
        case .permissionChanged:
            return .permissionChanged
        case .hostRestarted:
            return .hostRestarted
        }
    }
}

public enum RuntimeModelPullApprovalOutcome: String, CaseIterable, Sendable {
    case none
    case success
    case failure
    case resultSuppressed = "result_suppressed"
    case dismissal
    case expiry
    case connectionClosed = "connection_closed"
    case authenticationChanged = "authentication_changed"
    case permissionChanged = "permission_changed"
    case hostRestarted = "host_restarted"
}

public struct RuntimeModelPullApprovalRecord: Equatable, Sendable {
    public let operationID: String
    public let requestBindingDigest: String
    public let provider: RuntimeModelPullApprovalProvider
    public let actionID: String
    public let policyRevision: String
    public let currentEvent: RuntimeModelPullApprovalEvent
    public let outcome: RuntimeModelPullApprovalOutcome
    public let requestedAt: Date
    public let updatedAt: Date
    public let expiresAt: Date
    public let schemaVersion: Int
}

public struct RuntimeModelPullApprovalEventRecord: Equatable, Sendable {
    public let operationID: String
    public let order: Int
    public let event: RuntimeModelPullApprovalEvent
    public let outcome: RuntimeModelPullApprovalOutcome
    public let actionID: String
    public let policyRevision: String
    public let occurredAt: Date
    public let schemaVersion: Int
}

public struct RuntimeModelPullApprovalRecoveryResult: Equatable, Sendable {
    public let pendingTerminalized: Int
    public let reservedTerminalized: Int

    public var totalTerminalized: Int {
        pendingTerminalized + reservedTerminalized
    }
}

public enum RuntimeModelPullApprovalStoreError: Error, Equatable, Sendable {
    case invalidOperationID
    case invalidRequestBindingDigest
    case invalidProvider
    case invalidActionID
    case invalidPolicyRevision
    case invalidEvent
    case invalidTimestamp
    case invalidLimit
    case duplicateOperationID
    case duplicateRequestBinding
    case operationNotFound
    case requestBindingMismatch
    case illegalTransition
    case expiredReservation
    case corruptPersistence
    case storageFailure(String)
}

public protocol RuntimeModelPullApprovalStoring: AnyObject, Sendable {
    @discardableResult
    func createRequest(
        operationID: String,
        requestBindingDigest: String,
        provider: RuntimeModelPullApprovalProvider,
        actionID: String,
        policyRevision: String,
        requestedAt: Date,
        expiresAt: Date
    ) throws -> RuntimeModelPullApprovalRecord

    @discardableResult
    func reserveDispatch(
        operationID: String,
        requestBindingDigest: String,
        at: Date
    ) throws -> RuntimeModelPullApprovalRecord

    @discardableResult
    func recordTerminal(
        operationID: String,
        event: RuntimeModelPullApprovalEvent,
        at: Date
    ) throws -> RuntimeModelPullApprovalRecord

    func recoverUnfinished(at: Date) throws -> RuntimeModelPullApprovalRecoveryResult
    func recentEvents(limit: Int) throws -> [RuntimeModelPullApprovalEventRecord]
    func record(operationID: String) throws -> RuntimeModelPullApprovalRecord?
}

public final class SQLiteRuntimeModelPullApprovalStore:
    RuntimeModelPullApprovalStoring,
    @unchecked Sendable
{
    public static let requestBindingDigestPrefix =
        RuntimePermissionPolicyRegistry.requestBindingDigestPrefix
    public static let maximumRecentEventLimit = 500

    private static let schemaVersion = 2
    private static let legacySchemaVersion = 1
    private static let applicationID = 0x414D5041
    private static let operationsTable = "runtime_model_pull_approval_operations"
    private static let eventsTable = "runtime_model_pull_approval_events"
    private static let metadataTable = "runtime_model_pull_approval_metadata"
    private static let maximumEpochMilliseconds: Int64 = 253_402_300_799_999

    private let databaseURL: URL

    public init(databaseURL: URL = SQLiteRuntimeModelPullApprovalStore.defaultDatabaseURL()) {
        self.databaseURL = databaseURL
    }

    public static func defaultDatabaseURL() -> URL {
        let baseDirectory = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent(
                "runtime-model-pull-approvals.sqlite",
                isDirectory: false
            )
    }

    public static func makeRandomOperationID() -> String {
        UUID().uuidString.lowercased()
    }

    @discardableResult
    public func createRequest(
        operationID: String,
        requestBindingDigest: String,
        provider: RuntimeModelPullApprovalProvider,
        actionID: String = RuntimePermissionPolicyRegistry.modelPullActionID,
        policyRevision: String = RuntimePermissionPolicyRegistry.modelPullRevision,
        requestedAt: Date,
        expiresAt: Date
    ) throws -> RuntimeModelPullApprovalRecord {
        try Self.validateOperationID(operationID)
        try Self.validateRequestBindingDigest(requestBindingDigest)
        try Self.validatePolicy(actionID: actionID, policyRevision: policyRevision)
        let requestedAtMS = try Self.canonicalMilliseconds(requestedAt)
        let expiresAtMS = try Self.canonicalMilliseconds(expiresAt)
        guard expiresAtMS > requestedAtMS else {
            throw RuntimeModelPullApprovalStoreError.invalidTimestamp
        }

        return try withDatabase { database in
            try withImmediateTransaction(database) {
                if try Self.valueExists(
                    operationID,
                    column: "operation_id",
                    database: database
                ) {
                    throw RuntimeModelPullApprovalStoreError.duplicateOperationID
                }
                if try Self.valueExists(
                    requestBindingDigest,
                    column: "request_binding_digest",
                    database: database
                ) {
                    throw RuntimeModelPullApprovalStoreError.duplicateRequestBinding
                }

                let record = RuntimeModelPullApprovalRecord(
                    operationID: operationID,
                    requestBindingDigest: requestBindingDigest,
                    provider: provider,
                    actionID: actionID,
                    policyRevision: policyRevision,
                    currentEvent: .requested,
                    outcome: .none,
                    requestedAt: Self.date(fromCanonicalMilliseconds: requestedAtMS),
                    updatedAt: Self.date(fromCanonicalMilliseconds: requestedAtMS),
                    expiresAt: Self.date(fromCanonicalMilliseconds: expiresAtMS),
                    schemaVersion: Self.schemaVersion
                )
                try Self.insertOperation(record, database: database)
                try Self.insertEvent(
                    operationID: operationID,
                    order: 0,
                    event: .requested,
                    occurredAtMS: requestedAtMS,
                    database: database
                )
                return record
            }
        }
    }

    @discardableResult
    public func createRequest(
        operationID: String,
        requestBindingDigest: String,
        providerCode: String,
        actionID: String = RuntimePermissionPolicyRegistry.modelPullActionID,
        policyRevision: String = RuntimePermissionPolicyRegistry.modelPullRevision,
        requestedAt: Date,
        expiresAt: Date
    ) throws -> RuntimeModelPullApprovalRecord {
        guard let provider = RuntimeModelPullApprovalProvider(rawValue: providerCode) else {
            throw RuntimeModelPullApprovalStoreError.invalidProvider
        }
        return try createRequest(
            operationID: operationID,
            requestBindingDigest: requestBindingDigest,
            provider: provider,
            actionID: actionID,
            policyRevision: policyRevision,
            requestedAt: requestedAt,
            expiresAt: expiresAt
        )
    }

    @discardableResult
    public func reserveDispatch(
        operationID: String,
        requestBindingDigest: String,
        at: Date
    ) throws -> RuntimeModelPullApprovalRecord {
        try Self.validateOperationID(operationID)
        try Self.validateRequestBindingDigest(requestBindingDigest)
        let atMS = try Self.canonicalMilliseconds(at)

        let result: ReservationResult = try withDatabase { database in
            try withImmediateTransaction(database) {
                guard let record = try Self.readRecord(
                    operationID: operationID,
                    validateHistory: true,
                    database: database
                ) else {
                    throw RuntimeModelPullApprovalStoreError.operationNotFound
                }
                guard record.requestBindingDigest == requestBindingDigest else {
                    throw RuntimeModelPullApprovalStoreError.requestBindingMismatch
                }
                guard record.currentEvent == .requested else {
                    throw RuntimeModelPullApprovalStoreError.illegalTransition
                }
                let updatedAtMS = try Self.canonicalMilliseconds(record.updatedAt)
                let expiresAtMS = try Self.canonicalMilliseconds(record.expiresAt)
                guard atMS >= updatedAtMS else {
                    throw RuntimeModelPullApprovalStoreError.invalidTimestamp
                }
                if atMS >= expiresAtMS {
                    _ = try Self.appendTransition(
                        record: record,
                        event: .expiry,
                        occurredAtMS: atMS,
                        database: database
                    )
                    return .expired
                }
                return .reserved(try Self.appendTransition(
                    record: record,
                    event: .dispatchReserved,
                    occurredAtMS: atMS,
                    database: database
                ))
            }
        }
        switch result {
        case .reserved(let record):
            return record
        case .expired:
            throw RuntimeModelPullApprovalStoreError.expiredReservation
        }
    }

    @discardableResult
    public func recordTerminal(
        operationID: String,
        event: RuntimeModelPullApprovalEvent,
        at: Date
    ) throws -> RuntimeModelPullApprovalRecord {
        try Self.validateOperationID(operationID)
        guard Self.terminalEvents.contains(event) else {
            throw RuntimeModelPullApprovalStoreError.invalidEvent
        }
        let atMS = try Self.canonicalMilliseconds(at)

        let result: TerminalResult = try withDatabase { database in
            try withImmediateTransaction(database) {
                guard let record = try Self.readRecord(
                    operationID: operationID,
                    validateHistory: true,
                    database: database
                ) else {
                    throw RuntimeModelPullApprovalStoreError.operationNotFound
                }
                let updatedAtMS = try Self.canonicalMilliseconds(record.updatedAt)
                let expiresAtMS = try Self.canonicalMilliseconds(record.expiresAt)
                guard atMS >= updatedAtMS else {
                    throw RuntimeModelPullApprovalStoreError.invalidTimestamp
                }

                switch record.currentEvent {
                case .requested:
                    guard Self.pendingTerminalEvents.contains(event) else {
                        throw RuntimeModelPullApprovalStoreError.illegalTransition
                    }
                    if event == .expiry {
                        guard atMS >= expiresAtMS else {
                            throw RuntimeModelPullApprovalStoreError.illegalTransition
                        }
                    } else if atMS >= expiresAtMS {
                        _ = try Self.appendTransition(
                            record: record,
                            event: .expiry,
                            occurredAtMS: atMS,
                            database: database
                        )
                        return .expired
                    }
                case .dispatchReserved:
                    guard Self.reservedTerminalEvents.contains(event) else {
                        throw RuntimeModelPullApprovalStoreError.illegalTransition
                    }
                    if atMS >= expiresAtMS, event != .resultSuppressed {
                        _ = try Self.appendTransition(
                            record: record,
                            event: .resultSuppressed,
                            occurredAtMS: atMS,
                            database: database
                        )
                        return .expired
                    }
                default:
                    throw RuntimeModelPullApprovalStoreError.illegalTransition
                }

                return .recorded(try Self.appendTransition(
                    record: record,
                    event: event,
                    occurredAtMS: atMS,
                    database: database
                ))
            }
        }
        switch result {
        case .recorded(let record):
            return record
        case .expired:
            throw RuntimeModelPullApprovalStoreError.expiredReservation
        }
    }

    @discardableResult
    public func recordTerminal(
        operationID: String,
        eventCode: String,
        at: Date
    ) throws -> RuntimeModelPullApprovalRecord {
        guard let event = RuntimeModelPullApprovalEvent(rawValue: eventCode) else {
            throw RuntimeModelPullApprovalStoreError.invalidEvent
        }
        return try recordTerminal(operationID: operationID, event: event, at: at)
    }

    public func recoverUnfinished(
        at: Date
    ) throws -> RuntimeModelPullApprovalRecoveryResult {
        let atMS = try Self.canonicalMilliseconds(at)
        return try withDatabase { database in
            try withImmediateTransaction(database) {
                let records = try Self.readUnfinishedRecords(database: database)
                for record in records {
                    let updatedAtMS = try Self.canonicalMilliseconds(record.updatedAt)
                    guard atMS >= updatedAtMS else {
                        throw RuntimeModelPullApprovalStoreError.invalidTimestamp
                    }
                }

                var pendingCount = 0
                var reservedCount = 0
                for record in records {
                    switch record.currentEvent {
                    case .requested:
                        _ = try Self.appendTransition(
                            record: record,
                            event: .hostRestarted,
                            occurredAtMS: atMS,
                            database: database
                        )
                        pendingCount += 1
                    case .dispatchReserved:
                        _ = try Self.appendTransition(
                            record: record,
                            event: .resultSuppressed,
                            occurredAtMS: atMS,
                            database: database
                        )
                        reservedCount += 1
                    default:
                        throw RuntimeModelPullApprovalStoreError.corruptPersistence
                    }
                }
                return RuntimeModelPullApprovalRecoveryResult(
                    pendingTerminalized: pendingCount,
                    reservedTerminalized: reservedCount
                )
            }
        }
    }

    public func recentEvents(
        limit: Int
    ) throws -> [RuntimeModelPullApprovalEventRecord] {
        guard (1...Self.maximumRecentEventLimit).contains(limit) else {
            throw RuntimeModelPullApprovalStoreError.invalidLimit
        }
        return try withDatabase { database in
            let statement = try Self.prepare(
                database,
                """
                SELECT events.operation_id, events.event_order, events.event_code,
                       events.outcome_code, events.occurred_at_ms, events.schema_version,
                       operations.action_id, operations.policy_revision
                FROM \(Self.eventsTable) AS events
                JOIN \(Self.operationsTable) AS operations
                  ON operations.operation_id = events.operation_id
                ORDER BY events.occurred_at_ms DESC, events.operation_id DESC,
                         events.event_order DESC
                LIMIT ?
                """
            )
            defer { sqlite3_finalize(statement) }
            try Self.bindInt(limit, to: statement, at: 1)
            var events: [RuntimeModelPullApprovalEventRecord] = []
            while true {
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { break }
                guard result == SQLITE_ROW else {
                    throw Self.failure(database, "Could not read model-pull approval events.")
                }
                events.append(try Self.eventRecord(from: statement))
            }
            for operationID in Set(events.map(\.operationID)) {
                guard try Self.readRecord(
                    operationID: operationID,
                    validateHistory: true,
                    database: database
                ) != nil else {
                    throw RuntimeModelPullApprovalStoreError.corruptPersistence
                }
            }
            return events
        }
    }

    public func record(
        operationID: String
    ) throws -> RuntimeModelPullApprovalRecord? {
        try Self.validateOperationID(operationID)
        return try withDatabase { database in
            try Self.readRecord(
                operationID: operationID,
                validateHistory: true,
                database: database
            )
        }
    }

    private enum ReservationResult {
        case reserved(RuntimeModelPullApprovalRecord)
        case expired
    }

    private enum TerminalResult {
        case recorded(RuntimeModelPullApprovalRecord)
        case expired
    }

    private static let terminalEvents = Set(RuntimeModelPullApprovalEvent.allCases.filter {
        $0 != .requested && $0 != .dispatchReserved
    })
    private static let pendingTerminalEvents: Set<RuntimeModelPullApprovalEvent> = [
        .dismissal,
        .expiry,
        .connectionClosed,
        .authenticationChanged,
        .permissionChanged,
        .hostRestarted,
    ]
    private static let reservedTerminalEvents: Set<RuntimeModelPullApprovalEvent> = [
        .success,
        .failure,
        .resultSuppressed,
    ]

    private func withDatabase<Result>(
        _ body: (OpaquePointer) throws -> Result
    ) throws -> Result {
        try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: databaseURL) {
            try RuntimeEventLogFileProtection.prepareDirectory(for: databaseURL)
            if FileManager.default.fileExists(atPath: databaseURL.path) {
                try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
            }

            var database: OpaquePointer?
            let flags = SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX
            guard sqlite3_open_v2(databaseURL.path, &database, flags, nil) == SQLITE_OK,
                  let openedDatabase = database else {
                if let database { sqlite3_close(database) }
                throw RuntimeModelPullApprovalStoreError.storageFailure(
                    "Could not open the model-pull approval SQLite store."
                )
            }
            defer {
                sqlite3_close(openedDatabase)
                try? RuntimeEventLogFileProtection.secureFile(at: databaseURL)
            }

            guard sqlite3_busy_timeout(openedDatabase, 5_000) == SQLITE_OK else {
                throw Self.failure(
                    openedDatabase,
                    "Could not configure model-pull approval concurrency."
                )
            }
            Self.applySQLiteLimits(openedDatabase)
            try Self.configure(openedDatabase)
            try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
            try Self.ensureSchema(openedDatabase)
            try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
            return try body(openedDatabase)
        }
    }

    private func withImmediateTransaction<Result>(
        _ database: OpaquePointer,
        _ body: () throws -> Result
    ) throws -> Result {
        try Self.execute(database, "BEGIN IMMEDIATE")
        do {
            let result = try body()
            try Self.execute(database, "COMMIT")
            return result
        } catch {
            try? Self.execute(database, "ROLLBACK")
            throw error
        }
    }

    private static func configure(_ database: OpaquePointer) throws {
        try execute(database, "PRAGMA foreign_keys = ON")
        try execute(database, "PRAGMA trusted_schema = OFF")
        try execute(database, "PRAGMA recursive_triggers = OFF")
        try execute(database, "PRAGMA temp_store = MEMORY")
        try execute(database, "PRAGMA secure_delete = ON")
        try execute(database, "PRAGMA journal_mode = DELETE")
        try execute(database, "PRAGMA synchronous = FULL")
        try execute(database, "PRAGMA journal_size_limit = 0")
        try execute(database, "PRAGMA max_page_count = 16384")
        try execute(database, "PRAGMA cell_size_check = ON")
    }

    private static func applySQLiteLimits(_ database: OpaquePointer) {
        _ = sqlite3_limit(database, SQLITE_LIMIT_LENGTH, 4_096)
        _ = sqlite3_limit(database, SQLITE_LIMIT_SQL_LENGTH, 32_768)
        _ = sqlite3_limit(database, SQLITE_LIMIT_COLUMN, 32)
        _ = sqlite3_limit(database, SQLITE_LIMIT_EXPR_DEPTH, 32)
        _ = sqlite3_limit(database, SQLITE_LIMIT_COMPOUND_SELECT, 4)
        _ = sqlite3_limit(database, SQLITE_LIMIT_VARIABLE_NUMBER, 16)
        _ = sqlite3_limit(database, SQLITE_LIMIT_ATTACHED, 0)
    }

    private static func ensureSchema(_ database: OpaquePointer) throws {
        let version = try schemaUserVersion(database)
        guard version == 0 || version == legacySchemaVersion || version == schemaVersion else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
        if version == 0 {
            try execute(database, "BEGIN IMMEDIATE")
            do {
                try createSchema(database)
                try execute(database, "PRAGMA application_id = \(applicationID)")
                try execute(database, "PRAGMA user_version = \(schemaVersion)")
                try execute(database, "COMMIT")
            } catch {
                try? execute(database, "ROLLBACK")
                throw error
            }
        } else if version == legacySchemaVersion {
            guard try pragmaInteger(database, name: "application_id") == applicationID else {
                throw RuntimeModelPullApprovalStoreError.corruptPersistence
            }
            try verifyLegacySchema(database)
            try verifyIntegrity(database)
            try migrateLegacySchema(database)
        }
        guard try pragmaInteger(database, name: "application_id") == applicationID else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
        try verifySchema(database)
        try verifyIntegrity(database)
    }

    private static func createSchema(_ database: OpaquePointer) throws {
        let eventCodes = sqlAllowlist(RuntimeModelPullApprovalEvent.allCases.map(\.rawValue))
        let outcomeCodes = sqlAllowlist(RuntimeModelPullApprovalOutcome.allCases.map(\.rawValue))
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS \(operationsTable)(
                operation_id TEXT PRIMARY KEY NOT NULL,
                request_binding_digest TEXT UNIQUE NOT NULL,
                provider_code TEXT NOT NULL CHECK(provider_code = 'ollama'),
                action_id TEXT NOT NULL CHECK(action_id = 'models_pull_ollama_v1'),
                policy_revision TEXT NOT NULL CHECK(
                    policy_revision = '5969f34082e579a4e393bded6ce62706382e7376258b364c3afed0dbbcb163d3'
                ),
                current_event_code TEXT NOT NULL CHECK(current_event_code IN (\(eventCodes))),
                outcome_code TEXT NOT NULL CHECK(outcome_code IN (\(outcomeCodes))),
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL CHECK(schema_version = 2),
                CHECK(length(operation_id) = 36),
                CHECK(length(request_binding_digest) = 105),
                CHECK(length(action_id) = 21),
                CHECK(length(policy_revision) = 64),
                CHECK(updated_at_ms >= created_at_ms),
                CHECK(expires_at_ms > created_at_ms)
            )
            """
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS \(eventsTable)(
                operation_id TEXT NOT NULL REFERENCES \(operationsTable)(operation_id)
                    ON DELETE RESTRICT,
                event_order INTEGER NOT NULL CHECK(event_order BETWEEN 0 AND 2),
                event_code TEXT NOT NULL CHECK(event_code IN (\(eventCodes))),
                outcome_code TEXT NOT NULL CHECK(outcome_code IN (\(outcomeCodes))),
                occurred_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL CHECK(schema_version = 2),
                PRIMARY KEY(operation_id, event_order),
                UNIQUE(operation_id, event_code)
            )
            """
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS \(metadataTable)(
                singleton INTEGER PRIMARY KEY NOT NULL CHECK(singleton = 1),
                schema_version INTEGER NOT NULL CHECK(schema_version = 2)
            )
            """
        )
        try execute(
            database,
            "INSERT OR IGNORE INTO \(metadataTable)(singleton, schema_version) VALUES (1, 2)"
        )
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS runtime_model_pull_approval_events_recent
            ON \(eventsTable)(occurred_at_ms DESC, operation_id DESC, event_order DESC)
            """
        )
    }

    private static func verifyLegacySchema(_ database: OpaquePointer) throws {
        let operationColumns: Set<String> = [
            "operation_id", "request_binding_digest", "provider_code",
            "current_event_code", "outcome_code", "created_at_ms", "updated_at_ms",
            "expires_at_ms", "schema_version",
        ]
        let eventColumns: Set<String> = [
            "operation_id", "event_order", "event_code", "outcome_code",
            "occurred_at_ms", "schema_version",
        ]
        let metadataColumns: Set<String> = ["singleton", "schema_version"]
        guard try tableColumns(operationsTable, database: database) == operationColumns,
              try tableColumns(eventsTable, database: database) == eventColumns,
              try tableColumns(metadataTable, database: database) == metadataColumns else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }

        let statement = try prepare(
            database,
            "SELECT singleton, schema_version FROM \(metadataTable)"
        )
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW,
              validInt(statement, at: 0) == 1,
              validInt(statement, at: 1) == legacySchemaVersion,
              sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }

        let rowVersionStatement = try prepare(
            database,
            """
            SELECT
                EXISTS(
                    SELECT 1 FROM \(operationsTable)
                    WHERE typeof(schema_version) != 'integer'
                       OR schema_version != \(legacySchemaVersion)
                ),
                EXISTS(
                    SELECT 1 FROM \(eventsTable)
                    WHERE typeof(schema_version) != 'integer'
                       OR schema_version != \(legacySchemaVersion)
                )
            """
        )
        defer { sqlite3_finalize(rowVersionStatement) }
        guard sqlite3_step(rowVersionStatement) == SQLITE_ROW,
              validInt(rowVersionStatement, at: 0) == 0,
              validInt(rowVersionStatement, at: 1) == 0,
              sqlite3_step(rowVersionStatement) == SQLITE_DONE else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
    }

    private static func migrateLegacySchema(_ database: OpaquePointer) throws {
        let legacyOperations = "\(operationsTable)_v1"
        let legacyEvents = "\(eventsTable)_v1"
        let legacyMetadata = "\(metadataTable)_v1"
        try execute(database, "BEGIN IMMEDIATE")
        do {
            try execute(
                database,
                "DROP INDEX IF EXISTS runtime_model_pull_approval_events_recent"
            )
            try execute(database, "ALTER TABLE \(eventsTable) RENAME TO \(legacyEvents)")
            try execute(database, "ALTER TABLE \(operationsTable) RENAME TO \(legacyOperations)")
            try execute(database, "ALTER TABLE \(metadataTable) RENAME TO \(legacyMetadata)")
            try createSchema(database)
            try execute(
                database,
                """
                INSERT INTO \(operationsTable)(
                    operation_id, request_binding_digest, provider_code, action_id,
                    policy_revision, current_event_code, outcome_code, created_at_ms,
                    updated_at_ms, expires_at_ms, schema_version
                )
                SELECT operation_id, request_binding_digest, provider_code,
                       'models_pull_ollama_v1',
                       '5969f34082e579a4e393bded6ce62706382e7376258b364c3afed0dbbcb163d3',
                       current_event_code, outcome_code, created_at_ms, updated_at_ms,
                       expires_at_ms, 2
                FROM \(legacyOperations)
                """
            )
            try execute(
                database,
                """
                INSERT INTO \(eventsTable)(
                    operation_id, event_order, event_code, outcome_code,
                    occurred_at_ms, schema_version
                )
                SELECT operation_id, event_order, event_code, outcome_code,
                       occurred_at_ms, 2
                FROM \(legacyEvents)
                """
            )
            try validateAllRecordHistories(database: database)
            try execute(database, "DROP TABLE \(legacyEvents)")
            try execute(database, "DROP TABLE \(legacyOperations)")
            try execute(database, "DROP TABLE \(legacyMetadata)")
            try execute(database, "PRAGMA user_version = \(schemaVersion)")
            try execute(database, "COMMIT")
        } catch {
            try? execute(database, "ROLLBACK")
            throw error
        }
    }

    private static func verifySchema(_ database: OpaquePointer) throws {
        let operationColumns: Set<String> = [
            "operation_id", "request_binding_digest", "provider_code",
            "action_id", "policy_revision", "current_event_code", "outcome_code",
            "created_at_ms", "updated_at_ms", "expires_at_ms", "schema_version",
        ]
        let eventColumns: Set<String> = [
            "operation_id", "event_order", "event_code", "outcome_code",
            "occurred_at_ms", "schema_version",
        ]
        let metadataColumns: Set<String> = ["singleton", "schema_version"]
        guard try tableColumns(operationsTable, database: database) == operationColumns,
              try tableColumns(eventsTable, database: database) == eventColumns,
              try tableColumns(metadataTable, database: database) == metadataColumns else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }

        let statement = try prepare(
            database,
            "SELECT singleton, schema_version FROM \(metadataTable)"
        )
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW,
              validInt(statement, at: 0) == 1,
              validInt(statement, at: 1) == schemaVersion,
              sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
    }

    private static func verifyIntegrity(_ database: OpaquePointer) throws {
        let statement = try prepare(database, "PRAGMA quick_check(1)")
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW,
              validText(statement, at: 0) == "ok",
              sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
    }

    private static func insertOperation(
        _ record: RuntimeModelPullApprovalRecord,
        database: OpaquePointer
    ) throws {
        let statement = try prepare(
            database,
            """
            INSERT INTO \(operationsTable)(
                operation_id, request_binding_digest, provider_code, action_id,
                policy_revision, current_event_code, outcome_code, created_at_ms,
                updated_at_ms, expires_at_ms, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try bindText(record.operationID, to: statement, at: 1)
        try bindText(record.requestBindingDigest, to: statement, at: 2)
        try bindText(record.provider.rawValue, to: statement, at: 3)
        try bindText(record.actionID, to: statement, at: 4)
        try bindText(record.policyRevision, to: statement, at: 5)
        try bindText(record.currentEvent.rawValue, to: statement, at: 6)
        try bindText(record.outcome.rawValue, to: statement, at: 7)
        try bindInt64(canonicalMilliseconds(record.requestedAt), to: statement, at: 8)
        try bindInt64(canonicalMilliseconds(record.updatedAt), to: statement, at: 9)
        try bindInt64(canonicalMilliseconds(record.expiresAt), to: statement, at: 10)
        try bindInt(schemaVersion, to: statement, at: 11)
        try stepDone(statement, database: database)
    }

    private static func insertEvent(
        operationID: String,
        order: Int,
        event: RuntimeModelPullApprovalEvent,
        occurredAtMS: Int64,
        database: OpaquePointer
    ) throws {
        let statement = try prepare(
            database,
            """
            INSERT INTO \(eventsTable)(
                operation_id, event_order, event_code, outcome_code,
                occurred_at_ms, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try bindText(operationID, to: statement, at: 1)
        try bindInt(order, to: statement, at: 2)
        try bindText(event.rawValue, to: statement, at: 3)
        try bindText(event.outcome.rawValue, to: statement, at: 4)
        try bindInt64(occurredAtMS, to: statement, at: 5)
        try bindInt(schemaVersion, to: statement, at: 6)
        try stepDone(statement, database: database)
    }

    private static func appendTransition(
        record: RuntimeModelPullApprovalRecord,
        event: RuntimeModelPullApprovalEvent,
        occurredAtMS: Int64,
        database: OpaquePointer
    ) throws -> RuntimeModelPullApprovalRecord {
        let order = record.currentEvent == .requested ? 1 : 2
        let statement = try prepare(
            database,
            """
            UPDATE \(operationsTable)
            SET current_event_code = ?, outcome_code = ?, updated_at_ms = ?
            WHERE operation_id = ? AND current_event_code = ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try bindText(event.rawValue, to: statement, at: 1)
        try bindText(event.outcome.rawValue, to: statement, at: 2)
        try bindInt64(occurredAtMS, to: statement, at: 3)
        try bindText(record.operationID, to: statement, at: 4)
        try bindText(record.currentEvent.rawValue, to: statement, at: 5)
        try stepDone(statement, database: database)
        guard sqlite3_changes(database) == 1 else {
            throw RuntimeModelPullApprovalStoreError.illegalTransition
        }
        try insertEvent(
            operationID: record.operationID,
            order: order,
            event: event,
            occurredAtMS: occurredAtMS,
            database: database
        )
        return RuntimeModelPullApprovalRecord(
            operationID: record.operationID,
            requestBindingDigest: record.requestBindingDigest,
            provider: record.provider,
            actionID: record.actionID,
            policyRevision: record.policyRevision,
            currentEvent: event,
            outcome: event.outcome,
            requestedAt: record.requestedAt,
            updatedAt: date(fromCanonicalMilliseconds: occurredAtMS),
            expiresAt: record.expiresAt,
            schemaVersion: schemaVersion
        )
    }

    private static func readRecord(
        operationID: String,
        validateHistory: Bool,
        database: OpaquePointer
    ) throws -> RuntimeModelPullApprovalRecord? {
        let statement = try prepare(
            database,
            """
            SELECT operation_id, request_binding_digest, provider_code, action_id,
                   policy_revision, current_event_code, outcome_code, created_at_ms,
                   updated_at_ms, expires_at_ms, schema_version
            FROM \(operationsTable)
            WHERE operation_id = ?
            LIMIT 2
            """
        )
        defer { sqlite3_finalize(statement) }
        try bindText(operationID, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW else {
            throw failure(database, "Could not read model-pull approval state.")
        }
        let record = try approvalRecord(from: statement)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
        if validateHistory {
            try validateEventHistory(for: record, database: database)
        }
        return record
    }

    private static func readUnfinishedRecords(
        database: OpaquePointer
    ) throws -> [RuntimeModelPullApprovalRecord] {
        let statement = try prepare(
            database,
            """
            SELECT operation_id
            FROM \(operationsTable)
            WHERE current_event_code IN ('requested', 'dispatch_reserved')
            ORDER BY operation_id
            LIMIT 501
            """
        )
        defer { sqlite3_finalize(statement) }
        var operationIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW,
                  let operationID = validText(statement, at: 0) else {
                throw RuntimeModelPullApprovalStoreError.corruptPersistence
            }
            operationIDs.append(operationID)
        }
        guard operationIDs.count <= 500 else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
        return try operationIDs.map { operationID in
            guard let record = try readRecord(
                operationID: operationID,
                validateHistory: true,
                database: database
            ) else {
                throw RuntimeModelPullApprovalStoreError.corruptPersistence
            }
            return record
        }
    }

    private static func approvalRecord(
        from statement: OpaquePointer
    ) throws -> RuntimeModelPullApprovalRecord {
        guard let operationID = validText(statement, at: 0),
              let requestBindingDigest = validText(statement, at: 1),
              let providerCode = validText(statement, at: 2),
              let provider = RuntimeModelPullApprovalProvider(rawValue: providerCode),
              let actionID = validText(statement, at: 3),
              let policyRevision = validText(statement, at: 4),
              let eventCode = validText(statement, at: 5),
              let event = RuntimeModelPullApprovalEvent(rawValue: eventCode),
              let outcomeCode = validText(statement, at: 6),
              let outcome = RuntimeModelPullApprovalOutcome(rawValue: outcomeCode),
              let createdAtMS = validInt64(statement, at: 7),
              let updatedAtMS = validInt64(statement, at: 8),
              let expiresAtMS = validInt64(statement, at: 9),
              let version = validInt(statement, at: 10),
              version == schemaVersion,
              updatedAtMS >= createdAtMS,
              expiresAtMS > createdAtMS,
              (0...maximumEpochMilliseconds).contains(createdAtMS),
              (0...maximumEpochMilliseconds).contains(updatedAtMS),
              (0...maximumEpochMilliseconds).contains(expiresAtMS),
              event.outcome == outcome else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
        do {
            try validateOperationID(operationID)
            try validateRequestBindingDigest(requestBindingDigest)
            try validatePolicy(actionID: actionID, policyRevision: policyRevision)
        } catch {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
        return RuntimeModelPullApprovalRecord(
            operationID: operationID,
            requestBindingDigest: requestBindingDigest,
            provider: provider,
            actionID: actionID,
            policyRevision: policyRevision,
            currentEvent: event,
            outcome: outcome,
            requestedAt: date(fromCanonicalMilliseconds: createdAtMS),
            updatedAt: date(fromCanonicalMilliseconds: updatedAtMS),
            expiresAt: date(fromCanonicalMilliseconds: expiresAtMS),
            schemaVersion: version
        )
    }

    private static func eventRecord(
        from statement: OpaquePointer
    ) throws -> RuntimeModelPullApprovalEventRecord {
        guard let operationID = validText(statement, at: 0),
              let order = validInt(statement, at: 1),
              (0...2).contains(order),
              let eventCode = validText(statement, at: 2),
              let event = RuntimeModelPullApprovalEvent(rawValue: eventCode),
              let outcomeCode = validText(statement, at: 3),
              let outcome = RuntimeModelPullApprovalOutcome(rawValue: outcomeCode),
              event.outcome == outcome,
              let occurredAtMS = validInt64(statement, at: 4),
              (0...maximumEpochMilliseconds).contains(occurredAtMS),
              let version = validInt(statement, at: 5),
              version == schemaVersion,
              let actionID = validText(statement, at: 6),
              let policyRevision = validText(statement, at: 7) else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
        do {
            try validateOperationID(operationID)
            try validatePolicy(actionID: actionID, policyRevision: policyRevision)
        } catch {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
        return RuntimeModelPullApprovalEventRecord(
            operationID: operationID,
            order: order,
            event: event,
            outcome: outcome,
            actionID: actionID,
            policyRevision: policyRevision,
            occurredAt: date(fromCanonicalMilliseconds: occurredAtMS),
            schemaVersion: version
        )
    }

    private static func validateEventHistory(
        for record: RuntimeModelPullApprovalRecord,
        database: OpaquePointer
    ) throws {
        let statement = try prepare(
            database,
            """
            SELECT events.operation_id, events.event_order, events.event_code,
                   events.outcome_code, events.occurred_at_ms, events.schema_version,
                   operations.action_id, operations.policy_revision
            FROM \(eventsTable) AS events
            JOIN \(operationsTable) AS operations
              ON operations.operation_id = events.operation_id
            WHERE events.operation_id = ?
            ORDER BY events.event_order
            LIMIT 4
            """
        )
        defer { sqlite3_finalize(statement) }
        try bindText(record.operationID, to: statement, at: 1)
        var events: [RuntimeModelPullApprovalEventRecord] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw failure(database, "Could not validate model-pull approval history.")
            }
            events.append(try eventRecord(from: statement))
        }

        let expectedEvents: [RuntimeModelPullApprovalEvent]
        switch record.currentEvent {
        case .requested:
            expectedEvents = [.requested]
        case .dispatchReserved:
            expectedEvents = [.requested, .dispatchReserved]
        case .success, .failure, .resultSuppressed:
            expectedEvents = [.requested, .dispatchReserved, record.currentEvent]
        case .dismissal, .expiry, .connectionClosed, .authenticationChanged,
             .permissionChanged, .hostRestarted:
            expectedEvents = [.requested, record.currentEvent]
        }
        let eventTimes = try events.map { try canonicalMilliseconds($0.occurredAt) }
        let requestedAtMS = try canonicalMilliseconds(record.requestedAt)
        let updatedAtMS = try canonicalMilliseconds(record.updatedAt)
        let expiresAtMS = try canonicalMilliseconds(record.expiresAt)
        let reservationTimes = zip(events, eventTimes).compactMap { event, occurredAtMS in
            event.event == .dispatchReserved ? occurredAtMS : nil
        }
        let terminalTimeIsValid: Bool
        switch record.currentEvent {
        case .success, .failure:
            terminalTimeIsValid = eventTimes.last.map { $0 < expiresAtMS } ?? false
        case .expiry:
            terminalTimeIsValid = eventTimes.last.map { $0 >= expiresAtMS } ?? false
        case .dismissal, .connectionClosed, .authenticationChanged, .permissionChanged:
            terminalTimeIsValid = eventTimes.last.map { $0 < expiresAtMS } ?? false
        case .requested, .dispatchReserved, .resultSuppressed, .hostRestarted:
            terminalTimeIsValid = true
        }
        guard events.map(\.event) == expectedEvents,
              events.map(\.order) == Array(0..<events.count),
              events.allSatisfy({ $0.operationID == record.operationID }),
              events.allSatisfy({
                $0.actionID == record.actionID &&
                    $0.policyRevision == record.policyRevision
              }),
              eventTimes == eventTimes.sorted(),
              eventTimes.first == requestedAtMS,
              eventTimes.last == updatedAtMS,
              reservationTimes.allSatisfy({ $0 < expiresAtMS }),
              terminalTimeIsValid else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
    }

    private static func validateAllRecordHistories(database: OpaquePointer) throws {
        let statement = try prepare(
            database,
            "SELECT operation_id FROM \(operationsTable) ORDER BY operation_id"
        )
        var operationIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW,
                  let operationID = validText(statement, at: 0) else {
                sqlite3_finalize(statement)
                throw RuntimeModelPullApprovalStoreError.corruptPersistence
            }
            operationIDs.append(operationID)
        }
        sqlite3_finalize(statement)

        for operationID in operationIDs {
            guard try readRecord(
                operationID: operationID,
                validateHistory: true,
                database: database
            ) != nil else {
                throw RuntimeModelPullApprovalStoreError.corruptPersistence
            }
        }
    }

    private static func valueExists(
        _ value: String,
        column: String,
        database: OpaquePointer
    ) throws -> Bool {
        guard column == "operation_id" || column == "request_binding_digest" else {
            throw RuntimeModelPullApprovalStoreError.storageFailure(
                "Invalid model-pull approval lookup column."
            )
        }
        let statement = try prepare(
            database,
            "SELECT 1 FROM \(operationsTable) WHERE \(column) = ? LIMIT 1"
        )
        defer { sqlite3_finalize(statement) }
        try bindText(value, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_ROW { return true }
        if result == SQLITE_DONE { return false }
        throw failure(database, "Could not check model-pull approval uniqueness.")
    }

    private static func validateOperationID(_ operationID: String) throws {
        guard let parsed = UUID(uuidString: operationID),
              parsed.uuidString.lowercased() == operationID else {
            throw RuntimeModelPullApprovalStoreError.invalidOperationID
        }
    }

    private static func validateRequestBindingDigest(_ digest: String) throws {
        guard RuntimePermissionPolicyRegistry.isCanonicalRequestBindingDigest(digest) else {
            throw RuntimeModelPullApprovalStoreError.invalidRequestBindingDigest
        }
    }

    private static func validatePolicy(
        actionID: String,
        policyRevision: String
    ) throws {
        guard actionID == RuntimePermissionPolicyRegistry.modelPullActionID else {
            throw RuntimeModelPullApprovalStoreError.invalidActionID
        }
        guard policyRevision == RuntimePermissionPolicyRegistry.modelPullRevision else {
            throw RuntimeModelPullApprovalStoreError.invalidPolicyRevision
        }
    }

    private static func canonicalMilliseconds(_ date: Date) throws -> Int64 {
        let milliseconds = date.timeIntervalSince1970 * 1_000
        guard milliseconds.isFinite,
              milliseconds >= 0,
              milliseconds <= Double(maximumEpochMilliseconds) else {
            throw RuntimeModelPullApprovalStoreError.invalidTimestamp
        }
        return Int64(milliseconds.rounded(.towardZero))
    }

    private static func date(fromCanonicalMilliseconds milliseconds: Int64) -> Date {
        Date(timeIntervalSince1970: Double(milliseconds) / 1_000)
    }

    private static func sqlAllowlist(_ values: [String]) -> String {
        values.map { "'\($0)'" }.joined(separator: ", ")
    }

    private static func schemaUserVersion(_ database: OpaquePointer) throws -> Int {
        try pragmaInteger(database, name: "user_version")
    }

    private static func pragmaInteger(
        _ database: OpaquePointer,
        name: String
    ) throws -> Int {
        guard name == "user_version" || name == "application_id" else {
            throw RuntimeModelPullApprovalStoreError.storageFailure("Invalid SQLite pragma.")
        }
        let statement = try prepare(database, "PRAGMA \(name)")
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW,
              let value = validInt(statement, at: 0),
              sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeModelPullApprovalStoreError.corruptPersistence
        }
        return value
    }

    private static func tableColumns(
        _ table: String,
        database: OpaquePointer
    ) throws -> Set<String> {
        guard [operationsTable, eventsTable, metadataTable].contains(table) else {
            throw RuntimeModelPullApprovalStoreError.storageFailure("Invalid SQLite table.")
        }
        let statement = try prepare(database, "PRAGMA table_info(\(table))")
        defer { sqlite3_finalize(statement) }
        var columns = Set<String>()
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return columns }
            guard result == SQLITE_ROW,
                  let name = validText(statement, at: 1) else {
                throw RuntimeModelPullApprovalStoreError.corruptPersistence
            }
            columns.insert(name)
        }
    }

    private static func execute(_ database: OpaquePointer, _ sql: String) throws {
        var message: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(database, sql, nil, nil, &message) == SQLITE_OK else {
            defer { sqlite3_free(message) }
            let detail = message.map { String(cString: $0) } ?? "unknown SQLite failure"
            throw RuntimeModelPullApprovalStoreError.storageFailure(detail)
        }
    }

    private static func prepare(
        _ database: OpaquePointer,
        _ sql: String
    ) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw failure(database, "Could not prepare a model-pull approval statement.")
        }
        return statement
    }

    private static func bindText(
        _ value: String,
        to statement: OpaquePointer,
        at index: Int32
    ) throws {
        guard sqlite3_bind_text(
            statement,
            index,
            value,
            -1,
            SQLITE_TRANSIENT_MODEL_PULL_APPROVAL
        ) == SQLITE_OK else {
            throw RuntimeModelPullApprovalStoreError.storageFailure(
                "Could not bind model-pull approval text."
            )
        }
    }

    private static func bindInt(
        _ value: Int,
        to statement: OpaquePointer,
        at index: Int32
    ) throws {
        guard sqlite3_bind_int64(statement, index, sqlite3_int64(value)) == SQLITE_OK else {
            throw RuntimeModelPullApprovalStoreError.storageFailure(
                "Could not bind model-pull approval metadata."
            )
        }
    }

    private static func bindInt64(
        _ value: Int64,
        to statement: OpaquePointer,
        at index: Int32
    ) throws {
        guard sqlite3_bind_int64(statement, index, sqlite3_int64(value)) == SQLITE_OK else {
            throw RuntimeModelPullApprovalStoreError.storageFailure(
                "Could not bind model-pull approval timestamp."
            )
        }
    }

    private static func stepDone(
        _ statement: OpaquePointer,
        database: OpaquePointer
    ) throws {
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw failure(database, "Could not write model-pull approval state.")
        }
    }

    private static func validText(_ statement: OpaquePointer, at index: Int32) -> String? {
        guard sqlite3_column_type(statement, index) == SQLITE_TEXT,
              let bytes = sqlite3_column_text(statement, index) else {
            return nil
        }
        return String(
            data: Data(bytes: bytes, count: Int(sqlite3_column_bytes(statement, index))),
            encoding: .utf8
        )
    }

    private static func validInt(_ statement: OpaquePointer, at index: Int32) -> Int? {
        guard sqlite3_column_type(statement, index) == SQLITE_INTEGER else { return nil }
        return Int(exactly: sqlite3_column_int64(statement, index))
    }

    private static func validInt64(_ statement: OpaquePointer, at index: Int32) -> Int64? {
        guard sqlite3_column_type(statement, index) == SQLITE_INTEGER else { return nil }
        return sqlite3_column_int64(statement, index)
    }

    private static func failure(_ database: OpaquePointer, _ prefix: String) -> Error {
        let detail = sqlite3_errmsg(database).map { String(cString: $0) }
            ?? "unknown SQLite failure"
        return RuntimeModelPullApprovalStoreError.storageFailure("\(prefix) \(detail)")
    }
}

private let SQLITE_TRANSIENT_MODEL_PULL_APPROVAL = unsafeBitCast(
    -1,
    to: sqlite3_destructor_type.self
)
