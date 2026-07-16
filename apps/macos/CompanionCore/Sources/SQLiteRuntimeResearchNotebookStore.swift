import Foundation
import SQLite3

private final class SQLiteResearchNotebookWeakLock: @unchecked Sendable {
    weak var lock: NSRecursiveLock?

    init(_ lock: NSRecursiveLock) {
        self.lock = lock
    }
}

private enum SQLiteResearchNotebookLockRegistry {
    private static let registryLock = NSLock()
    nonisolated(unsafe) private static var locksByPath: [String: SQLiteResearchNotebookWeakLock] = [:]

    static func lock(for databaseURL: URL) -> NSRecursiveLock {
        let path = databaseURL.standardizedFileURL.path
        return registryLock.withLock {
            locksByPath = locksByPath.filter { $0.value.lock != nil }
            if let existing = locksByPath[path]?.lock {
                return existing
            }
            let lock = NSRecursiveLock()
            locksByPath[path] = SQLiteResearchNotebookWeakLock(lock)
            return lock
        }
    }
}

public final class SQLiteRuntimeResearchNotebookStore: RuntimeResearchNotebookStoring, @unchecked Sendable {
    private static let schemaVersion = 4
    private static let migratedV2CoordinatorID = "00000000000000000000000000000002"
    private static let notebooksTable = "runtime_research_notebooks"
    private static let grantsTable = "runtime_research_notebook_grants"
    private static let lifecycleIntentsTable = "runtime_research_notebook_lifecycle_intents"
    private static let metadataTable = "runtime_research_notebook_store_metadata"

    private let databaseURL: URL
    private let rowLimitPerOwner: Int
    private let now: @Sendable () -> Date
    private let beforeSchemaMigrationLock: (@Sendable (Int) throws -> Void)?
    private let lock: NSRecursiveLock

    public convenience init(
        databaseURL: URL = SQLiteRuntimeResearchNotebookStore.defaultDatabaseURL(),
        rowLimitPerOwner: Int = RuntimeResearchNotebook.maximumRowsPerOwner,
        now: @escaping @Sendable () -> Date = { Date() }
    ) {
        self.init(
            databaseURL: databaseURL,
            rowLimitPerOwner: rowLimitPerOwner,
            now: now,
            beforeSchemaMigrationLock: nil
        )
    }

    init(
        databaseURL: URL,
        rowLimitPerOwner: Int = RuntimeResearchNotebook.maximumRowsPerOwner,
        now: @escaping @Sendable () -> Date = { Date() },
        beforeSchemaMigrationLock: (@Sendable (Int) throws -> Void)?
    ) {
        self.databaseURL = databaseURL
        self.rowLimitPerOwner = max(
            1,
            min(rowLimitPerOwner, RuntimeResearchNotebook.maximumRowsPerOwner)
        )
        self.now = now
        self.beforeSchemaMigrationLock = beforeSchemaMigrationLock
        self.lock = SQLiteResearchNotebookLockRegistry.lock(for: databaseURL)
    }

    public func withLifecycleCoordination<Result>(
        _ body: () throws -> Result
    ) rethrows -> Result {
        try lock.withLock(body)
    }

    public static func defaultDatabaseURL() -> URL {
        let baseDirectory = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-research-notebooks.sqlite", isDirectory: false)
    }

    @discardableResult
    public func create(
        ownerDeviceID: String,
        notebookID: String,
        backingSessionID: String,
        title: String,
        model: String,
        promptSkillBinding: RuntimePromptSkillBinding,
        trustedSourceGrantIDs: [String]
    ) throws -> RuntimeResearchNotebook {
        try runtimeResearchNotebookValidateCreateFields(
            ownerDeviceID: ownerDeviceID,
            notebookID: notebookID,
            backingSessionID: backingSessionID,
            title: title,
            model: model,
            promptSkillBinding: promptSkillBinding,
            trustedSourceGrantIDs: trustedSourceGrantIDs
        )

        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    if try Self.notebookIDExists(notebookID, database: database) {
                        throw RuntimeResearchNotebookStoreError.notebookIDCollision
                    }
                    if try Self.backingSessionExists(
                        ownerDeviceID: ownerDeviceID,
                        backingSessionID: backingSessionID,
                        database: database
                    ) {
                        throw RuntimeResearchNotebookStoreError.backingSessionIDCollision
                    }
                    guard try Self.rowCount(ownerDeviceID: ownerDeviceID, database: database)
                            < rowLimitPerOwner else {
                        throw RuntimeResearchNotebookStoreError.rowLimitReached
                    }
                    let timestamp = now()
                    let notebook = RuntimeResearchNotebook(
                        notebookID: notebookID,
                        ownerDeviceID: ownerDeviceID,
                        backingSessionID: backingSessionID,
                        title: title,
                        model: model,
                        promptSkillBinding: promptSkillBinding,
                        trustedSourceGrantIDs: trustedSourceGrantIDs,
                        lifecycle: .active,
                        createdAt: timestamp,
                        updatedAt: timestamp
                    )
                    try runtimeResearchNotebookValidate(notebook)
                    try Self.insert(notebook, database: database)
                    return notebook
                }
            }
        }
    }

    public func createPendingChatPersistence(
        ownerDeviceID: String,
        notebookID: String,
        backingSessionID: String,
        title: String,
        model: String,
        promptSkillBinding: RuntimePromptSkillBinding,
        trustedSourceGrantIDs: [String],
        coordinatorID: String,
        operationID: String,
        leaseExpiresAt: Date
    ) throws -> RuntimeResearchNotebookLifecycleIntent {
        try runtimeResearchNotebookValidateCreateFields(
            ownerDeviceID: ownerDeviceID,
            notebookID: notebookID,
            backingSessionID: backingSessionID,
            title: title,
            model: model,
            promptSkillBinding: promptSkillBinding,
            trustedSourceGrantIDs: trustedSourceGrantIDs
        )
        try runtimeResearchNotebookValidateLifecycleIdentity(
            coordinatorID: coordinatorID,
            operationID: operationID,
            leaseExpiresAt: leaseExpiresAt
        )
        let canonicalLeaseExpiresAt = Self.sqliteCanonicalDate(leaseExpiresAt)
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    if try Self.notebookIDExists(notebookID, database: database) {
                        throw RuntimeResearchNotebookStoreError.notebookIDCollision
                    }
                    if try Self.backingSessionExists(
                        ownerDeviceID: ownerDeviceID,
                        backingSessionID: backingSessionID,
                        database: database
                    ) {
                        throw RuntimeResearchNotebookStoreError.backingSessionIDCollision
                    }
                    guard try Self.rowCount(ownerDeviceID: ownerDeviceID, database: database)
                            < rowLimitPerOwner else {
                        throw RuntimeResearchNotebookStoreError.rowLimitReached
                    }
                    let timestamp = now()
                    let notebook = RuntimeResearchNotebook(
                        notebookID: notebookID,
                        ownerDeviceID: ownerDeviceID,
                        backingSessionID: backingSessionID,
                        title: title,
                        model: model,
                        promptSkillBinding: promptSkillBinding,
                        trustedSourceGrantIDs: trustedSourceGrantIDs,
                        lifecycle: .active,
                        createdAt: timestamp,
                        updatedAt: timestamp
                    )
                    try runtimeResearchNotebookValidate(notebook)
                    try Self.insert(notebook, database: database)
                    let intent = RuntimeResearchNotebookLifecycleIntent(
                        ownerDeviceID: ownerDeviceID,
                        notebookID: notebookID,
                        backingSessionID: backingSessionID,
                        mutation: .create,
                        coordinatorID: coordinatorID,
                        operationID: operationID,
                        leaseExpiresAt: canonicalLeaseExpiresAt
                    )
                    let statement = try Self.prepare(
                        database,
                        """
                        INSERT INTO \(Self.lifecycleIntentsTable)(
                            notebook_id, owner_device_id, backing_session_id, mutation,
                            coordinator_id, operation_id, lease_expires_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """
                    )
                    defer { sqlite3_finalize(statement) }
                    try Self.bindText(notebookID, to: statement, at: 1)
                    try Self.bindText(ownerDeviceID, to: statement, at: 2)
                    try Self.bindText(backingSessionID, to: statement, at: 3)
                    try Self.bindText(intent.mutation.rawValue, to: statement, at: 4)
                    try Self.bindText(intent.coordinatorID, to: statement, at: 5)
                    try Self.bindText(intent.operationID, to: statement, at: 6)
                    try Self.bindDouble(intent.leaseExpiresAt.timeIntervalSince1970, to: statement, at: 7)
                    try Self.stepDone(statement, database: database)
                    return intent
                }
            }
        }
    }

    public func get(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> RuntimeResearchNotebook? {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateID(notebookID)
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                try Self.readOne(
                    whereClause: "owner_device_id = ? AND notebook_id = ?",
                    bindings: [ownerDeviceID, notebookID],
                    database: database
                )
            }
        }
    }

    public func getByBackingSessionID(
        ownerDeviceID: String,
        backingSessionID: String
    ) throws -> RuntimeResearchNotebook? {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateBackingSessionID(backingSessionID)
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                try Self.readOne(
                    whereClause: "owner_device_id = ? AND backing_session_id = ?",
                    bindings: [ownerDeviceID, backingSessionID],
                    database: database
                )
            }
        }
    }

    public func list(
        ownerDeviceID: String,
        lifecycle: RuntimeResearchNotebookLifecycle? = nil,
        limit: Int = RuntimeResearchNotebook.maximumListLimit
    ) throws -> [RuntimeResearchNotebook] {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateListLimit(limit)
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                let statement: OpaquePointer
                if let lifecycle {
                    statement = try Self.prepare(
                        database,
                        Self.selectColumns + " WHERE owner_device_id = ? AND lifecycle = ?"
                    )
                    try Self.bindText(ownerDeviceID, to: statement, at: 1)
                    try Self.bindText(lifecycle.rawValue, to: statement, at: 2)
                } else {
                    statement = try Self.prepare(
                        database,
                        Self.selectColumns + " WHERE owner_device_id = ?"
                    )
                    try Self.bindText(ownerDeviceID, to: statement, at: 1)
                }
                defer { sqlite3_finalize(statement) }

                var notebooks: [RuntimeResearchNotebook] = []
                while true {
                    let result = sqlite3_step(statement)
                    if result == SQLITE_DONE { break }
                    guard result == SQLITE_ROW else {
                        throw Self.failure(database, "Could not list research notebooks.")
                    }
                    notebooks.append(try Self.notebook(from: statement, database: database))
                    guard notebooks.count <= rowLimitPerOwner else {
                        throw RuntimeResearchNotebookStoreError.corruptPersistence
                    }
                }
                return notebooks
                    .sorted(by: runtimeResearchNotebookPrecedes)
                    .prefix(limit)
                    .map { $0 }
            }
        }
    }

    @discardableResult
    public func archive(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> RuntimeResearchNotebook? {
        try mutateLifecycle(
            ownerDeviceID: ownerDeviceID,
            notebookID: notebookID,
            lifecycle: .archived
        )
    }

    @discardableResult
    public func restore(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> RuntimeResearchNotebook? {
        try mutateLifecycle(
            ownerDeviceID: ownerDeviceID,
            notebookID: notebookID,
            lifecycle: .active
        )
    }

    @discardableResult
    public func delete(
        ownerDeviceID: String,
        notebookID: String
    ) throws -> Bool {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateID(notebookID)
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return false }
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    let statement = try Self.prepare(
                        database,
                        "DELETE FROM \(Self.notebooksTable) WHERE owner_device_id = ? AND notebook_id = ?"
                    )
                    defer { sqlite3_finalize(statement) }
                    try Self.bindText(ownerDeviceID, to: statement, at: 1)
                    try Self.bindText(notebookID, to: statement, at: 2)
                    try Self.stepDone(statement, database: database)
                    return sqlite3_changes(database) == 1
                }
            }
        }
    }

    public func prepareLifecycleMutation(
        ownerDeviceID: String,
        backingSessionID: String,
        mutation: RuntimeResearchNotebookLifecycleMutation,
        coordinatorID: String,
        operationID: String,
        leaseExpiresAt: Date
    ) throws -> RuntimeResearchNotebookLifecycleIntent? {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateBackingSessionID(backingSessionID)
        try runtimeResearchNotebookValidateLifecycleIdentity(
            coordinatorID: coordinatorID,
            operationID: operationID,
            leaseExpiresAt: leaseExpiresAt
        )
        let canonicalLeaseExpiresAt = Self.sqliteCanonicalDate(leaseExpiresAt)
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard let notebook = try Self.readOne(
                        whereClause: "owner_device_id = ? AND backing_session_id = ?",
                        bindings: [ownerDeviceID, backingSessionID],
                        database: database
                    ) else {
                        return nil
                    }
                    let intent = RuntimeResearchNotebookLifecycleIntent(
                        ownerDeviceID: ownerDeviceID,
                        notebookID: notebook.notebookID,
                        backingSessionID: backingSessionID,
                        mutation: mutation,
                        coordinatorID: coordinatorID,
                        operationID: operationID,
                        leaseExpiresAt: canonicalLeaseExpiresAt
                    )
                    if let current = try Self.readLifecycleIntent(
                        notebookID: notebook.notebookID,
                        database: database
                    ) {
                        guard current == intent else {
                            throw RuntimeResearchNotebookStoreError.storageFailure(
                                "A different research notebook lifecycle mutation is already pending."
                            )
                        }
                        return current
                    }
                    let statement = try Self.prepare(
                        database,
                        """
                        INSERT INTO \(Self.lifecycleIntentsTable)(
                            notebook_id, owner_device_id, backing_session_id, mutation,
                            coordinator_id, operation_id, lease_expires_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """
                    )
                    defer { sqlite3_finalize(statement) }
                    try Self.bindText(intent.notebookID, to: statement, at: 1)
                    try Self.bindText(intent.ownerDeviceID, to: statement, at: 2)
                    try Self.bindText(intent.backingSessionID, to: statement, at: 3)
                    try Self.bindText(intent.mutation.rawValue, to: statement, at: 4)
                    try Self.bindText(intent.coordinatorID, to: statement, at: 5)
                    try Self.bindText(intent.operationID, to: statement, at: 6)
                    try Self.bindDouble(intent.leaseExpiresAt.timeIntervalSince1970, to: statement, at: 7)
                    try Self.stepDone(statement, database: database)
                    return intent
                }
            }
        }
    }

    public func completeLifecycleMutation(
        _ intent: RuntimeResearchNotebookLifecycleIntent
    ) throws {
        try runtimeResearchNotebookValidateLifecycleIntent(intent)
        try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard let pending = try Self.readLifecycleIntent(
                        notebookID: intent.notebookID,
                        database: database
                    ) else {
                        try Self.validateCompletedLifecycleIntent(intent, database: database)
                        return
                    }
                    guard pending == intent else {
                        throw RuntimeResearchNotebookStoreError.corruptPersistence
                    }
                    switch intent.mutation {
                    case .create:
                        guard let notebook = try Self.readOne(
                            whereClause: "owner_device_id = ? AND notebook_id = ?",
                            bindings: [intent.ownerDeviceID, intent.notebookID],
                            database: database
                        ), notebook.backingSessionID == intent.backingSessionID,
                           notebook.lifecycle == .active else {
                            throw RuntimeResearchNotebookStoreError.corruptPersistence
                        }
                        try Self.deleteLifecycleIntent(intent, database: database)
                    case .archive, .restore:
                        guard let current = try Self.readOne(
                            whereClause: "owner_device_id = ? AND notebook_id = ?",
                            bindings: [intent.ownerDeviceID, intent.notebookID],
                            database: database
                        ), current.backingSessionID == intent.backingSessionID else {
                            throw RuntimeResearchNotebookStoreError.corruptPersistence
                        }
                        let lifecycle: RuntimeResearchNotebookLifecycle =
                            intent.mutation == .archive ? .archived : .active
                        if current.lifecycle != lifecycle {
                            let timestamp = now()
                            guard timestamp.timeIntervalSince1970.isFinite,
                                  timestamp >= current.updatedAt else {
                                throw RuntimeResearchNotebookStoreError.invalidField("updated_at")
                            }
                            let statement = try Self.prepare(
                                database,
                                """
                                UPDATE \(Self.notebooksTable)
                                SET lifecycle = ?, updated_at = ?
                                WHERE owner_device_id = ? AND notebook_id = ?
                                """
                            )
                            defer { sqlite3_finalize(statement) }
                            try Self.bindText(lifecycle.rawValue, to: statement, at: 1)
                            try Self.bindDouble(timestamp.timeIntervalSince1970, to: statement, at: 2)
                            try Self.bindText(intent.ownerDeviceID, to: statement, at: 3)
                            try Self.bindText(intent.notebookID, to: statement, at: 4)
                            try Self.stepDone(statement, database: database)
                            guard sqlite3_changes(database) == 1 else {
                                throw RuntimeResearchNotebookStoreError.corruptPersistence
                            }
                        }
                        try Self.deleteLifecycleIntent(intent, database: database)
                    case .delete:
                        let statement = try Self.prepare(
                            database,
                            """
                            DELETE FROM \(Self.notebooksTable)
                            WHERE owner_device_id = ? AND notebook_id = ? AND backing_session_id = ?
                            """
                        )
                        defer { sqlite3_finalize(statement) }
                        try Self.bindText(intent.ownerDeviceID, to: statement, at: 1)
                        try Self.bindText(intent.notebookID, to: statement, at: 2)
                        try Self.bindText(intent.backingSessionID, to: statement, at: 3)
                        try Self.stepDone(statement, database: database)
                        guard sqlite3_changes(database) == 1 else {
                            throw RuntimeResearchNotebookStoreError.corruptPersistence
                        }
                    }
                }
            }
        }
    }

    public func renewLifecycleMutation(
        _ intent: RuntimeResearchNotebookLifecycleIntent,
        leaseExpiresAt: Date
    ) throws -> RuntimeResearchNotebookLifecycleIntent {
        try runtimeResearchNotebookValidateLifecycleIntent(intent)
        try runtimeResearchNotebookValidateLifecycleIdentity(
            coordinatorID: intent.coordinatorID,
            operationID: intent.operationID,
            leaseExpiresAt: leaseExpiresAt
        )
        let canonicalLeaseExpiresAt = Self.sqliteCanonicalDate(leaseExpiresAt)
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    let statement = try Self.prepare(
                        database,
                        """
                        UPDATE \(Self.lifecycleIntentsTable)
                        SET lease_expires_at = ?
                        WHERE notebook_id = ? AND owner_device_id = ?
                          AND backing_session_id = ? AND mutation = ?
                          AND coordinator_id = ? AND operation_id = ? AND lease_expires_at = ?
                        """
                    )
                    defer { sqlite3_finalize(statement) }
                    try Self.bindDouble(
                        canonicalLeaseExpiresAt.timeIntervalSince1970,
                        to: statement,
                        at: 1
                    )
                    try Self.bindText(intent.notebookID, to: statement, at: 2)
                    try Self.bindText(intent.ownerDeviceID, to: statement, at: 3)
                    try Self.bindText(intent.backingSessionID, to: statement, at: 4)
                    try Self.bindText(intent.mutation.rawValue, to: statement, at: 5)
                    try Self.bindText(intent.coordinatorID, to: statement, at: 6)
                    try Self.bindText(intent.operationID, to: statement, at: 7)
                    try Self.bindDouble(intent.leaseExpiresAt.timeIntervalSince1970, to: statement, at: 8)
                    try Self.stepDone(statement, database: database)
                    guard sqlite3_changes(database) == 1 else {
                        throw RuntimeResearchNotebookStoreError.storageFailure(
                            "The research notebook lifecycle intent is no longer owned by this operation."
                        )
                    }
                    return RuntimeResearchNotebookLifecycleIntent(
                        ownerDeviceID: intent.ownerDeviceID,
                        notebookID: intent.notebookID,
                        backingSessionID: intent.backingSessionID,
                        mutation: intent.mutation,
                        coordinatorID: intent.coordinatorID,
                        operationID: intent.operationID,
                        leaseExpiresAt: canonicalLeaseExpiresAt
                    )
                }
            }
        }
    }

    public func cancelLifecycleMutation(
        _ intent: RuntimeResearchNotebookLifecycleIntent
    ) throws {
        try runtimeResearchNotebookValidateLifecycleIntent(intent)
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return }
        try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard let pending = try Self.readLifecycleIntent(
                        notebookID: intent.notebookID,
                        database: database
                    ) else { return }
                    guard pending == intent else {
                        throw RuntimeResearchNotebookStoreError.corruptPersistence
                    }
                    if intent.mutation == .create {
                        let statement = try Self.prepare(
                            database,
                            """
                            DELETE FROM \(Self.notebooksTable)
                            WHERE owner_device_id = ? AND notebook_id = ? AND backing_session_id = ?
                            """
                        )
                        defer { sqlite3_finalize(statement) }
                        try Self.bindText(intent.ownerDeviceID, to: statement, at: 1)
                        try Self.bindText(intent.notebookID, to: statement, at: 2)
                        try Self.bindText(intent.backingSessionID, to: statement, at: 3)
                        try Self.stepDone(statement, database: database)
                        guard sqlite3_changes(database) == 1 else {
                            throw RuntimeResearchNotebookStoreError.corruptPersistence
                        }
                    } else {
                        try Self.deleteLifecycleIntent(intent, database: database)
                    }
                }
            }
        }
    }

    public func pendingLifecycleMutations(
        ownerDeviceID: String
    ) throws -> [RuntimeResearchNotebookLifecycleIntent] {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                let statement = try Self.prepare(
                    database,
                    """
                    SELECT notebook_id, owner_device_id, backing_session_id, mutation,
                           coordinator_id, operation_id, lease_expires_at
                    FROM \(Self.lifecycleIntentsTable)
                    WHERE owner_device_id = ?
                    ORDER BY backing_session_id ASC, notebook_id ASC
                    """
                )
                defer { sqlite3_finalize(statement) }
                try Self.bindText(ownerDeviceID, to: statement, at: 1)
                var intents: [RuntimeResearchNotebookLifecycleIntent] = []
                while true {
                    let result = sqlite3_step(statement)
                    if result == SQLITE_DONE { return intents }
                    guard result == SQLITE_ROW else {
                        throw Self.failure(database, "Could not list research notebook lifecycle intents.")
                    }
                    intents.append(try Self.lifecycleIntent(from: statement))
                }
            }
        }
    }

    private func mutateLifecycle(
        ownerDeviceID: String,
        notebookID: String,
        lifecycle: RuntimeResearchNotebookLifecycle
    ) throws -> RuntimeResearchNotebook? {
        try runtimeResearchNotebookValidateOwner(ownerDeviceID)
        try runtimeResearchNotebookValidateID(notebookID)
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                try withImmediateTransaction(database) {
                    guard let current = try Self.readOne(
                        whereClause: "owner_device_id = ? AND notebook_id = ?",
                        bindings: [ownerDeviceID, notebookID],
                        database: database
                    ) else {
                        return nil
                    }
                    guard current.lifecycle != lifecycle else { return current }
                    let timestamp = now()
                    guard timestamp.timeIntervalSince1970.isFinite,
                          timestamp >= current.updatedAt else {
                        throw RuntimeResearchNotebookStoreError.invalidField("updated_at")
                    }
                    let statement = try Self.prepare(
                        database,
                        """
                        UPDATE \(Self.notebooksTable)
                        SET lifecycle = ?, updated_at = ?
                        WHERE owner_device_id = ? AND notebook_id = ?
                        """
                    )
                    defer { sqlite3_finalize(statement) }
                    try Self.bindText(lifecycle.rawValue, to: statement, at: 1)
                    try Self.bindDouble(timestamp.timeIntervalSince1970, to: statement, at: 2)
                    try Self.bindText(ownerDeviceID, to: statement, at: 3)
                    try Self.bindText(notebookID, to: statement, at: 4)
                    try Self.stepDone(statement, database: database)
                    guard sqlite3_changes(database) == 1 else {
                        throw RuntimeResearchNotebookStoreError.corruptPersistence
                    }
                    return RuntimeResearchNotebook(
                        notebookID: current.notebookID,
                        ownerDeviceID: current.ownerDeviceID,
                        backingSessionID: current.backingSessionID,
                        title: current.title,
                        model: current.model,
                        promptSkillBinding: current.promptSkillBinding,
                        trustedSourceGrantIDs: current.trustedSourceGrantIDs,
                        lifecycle: lifecycle,
                        createdAt: current.createdAt,
                        updatedAt: timestamp
                    )
                }
            }
        }
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
            if let database { sqlite3_close(database) }
            throw RuntimeResearchNotebookStoreError.storageFailure(
                "Could not open the research notebook SQLite store."
            )
        }
        defer {
            sqlite3_close(openedDatabase)
            try? RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        guard sqlite3_busy_timeout(openedDatabase, 5_000) == SQLITE_OK else {
            throw Self.failure(openedDatabase, "Could not configure research notebook concurrency.")
        }
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        try Self.ensureSchema(
            openedDatabase,
            beforeSchemaMigrationLock: beforeSchemaMigrationLock
        )
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        return try body(openedDatabase)
    }

    private func withImmediateTransaction<T>(
        _ database: OpaquePointer,
        _ body: () throws -> T
    ) throws -> T {
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

    private static let selectColumns = """
        SELECT notebook_id, owner_device_id, backing_session_id, title, model,
               prompt_skill_id, prompt_skill_revision, lifecycle, created_at, updated_at
        FROM runtime_research_notebooks
        """

    private static func readOne(
        whereClause: String,
        bindings: [String],
        database: OpaquePointer
    ) throws -> RuntimeResearchNotebook? {
        let statement = try prepare(
            database,
            selectColumns + " WHERE " + whereClause + " LIMIT 2"
        )
        defer { sqlite3_finalize(statement) }
        for (offset, value) in bindings.enumerated() {
            try bindText(value, to: statement, at: Int32(offset + 1))
        }
        let firstResult = sqlite3_step(statement)
        if firstResult == SQLITE_DONE { return nil }
        guard firstResult == SQLITE_ROW else {
            throw failure(database, "Could not read research notebook metadata.")
        }
        let notebook = try self.notebook(from: statement, database: database)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        return notebook
    }

    private static func notebook(
        from statement: OpaquePointer,
        database: OpaquePointer
    ) throws -> RuntimeResearchNotebook {
        guard let notebookID = validText(statement, at: 0),
              let ownerDeviceID = validText(statement, at: 1),
              let backingSessionID = validText(statement, at: 2),
              let title = validText(statement, at: 3),
              let model = validText(statement, at: 4),
              let promptSkillID = validText(statement, at: 5),
              let promptSkillRevision = validText(statement, at: 6),
              let promptSkillBinding = try? RuntimePromptSkillBinding(
                identifier: promptSkillID,
                revision: promptSkillRevision
              ),
              let lifecycleValue = validText(statement, at: 7),
              let lifecycle = RuntimeResearchNotebookLifecycle(rawValue: lifecycleValue),
              let createdAtValue = validDouble(statement, at: 8),
              let updatedAtValue = validDouble(statement, at: 9) else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        let grants = try trustedSourceGrantIDs(notebookID: notebookID, database: database)
        let notebook = RuntimeResearchNotebook(
            notebookID: notebookID,
            ownerDeviceID: ownerDeviceID,
            backingSessionID: backingSessionID,
            title: title,
            model: model,
            promptSkillBinding: promptSkillBinding,
            trustedSourceGrantIDs: grants,
            lifecycle: lifecycle,
            createdAt: Date(timeIntervalSince1970: createdAtValue),
            updatedAt: Date(timeIntervalSince1970: updatedAtValue)
        )
        do {
            try runtimeResearchNotebookValidate(notebook)
        } catch {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        return notebook
    }

    private static func trustedSourceGrantIDs(
        notebookID: String,
        database: OpaquePointer
    ) throws -> [String] {
        let statement = try prepare(
            database,
            """
            SELECT position, grant_id
            FROM \(grantsTable)
            WHERE notebook_id = ?
            ORDER BY position ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try bindText(notebookID, to: statement, at: 1)
        var grants: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW,
                  let position = validInt(statement, at: 0),
                  let grantID = validText(statement, at: 1),
                  position == grants.count else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
            grants.append(grantID)
            guard grants.count <= RuntimeResearchNotebook.maximumTrustedSourceGrantCount else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
        }
        return grants
    }

    private static func insert(
        _ notebook: RuntimeResearchNotebook,
        database: OpaquePointer
    ) throws {
        let notebookStatement = try prepare(
            database,
            """
            INSERT INTO \(notebooksTable)(
                notebook_id, owner_device_id, backing_session_id, title, model,
                prompt_skill_id, prompt_skill_revision, lifecycle, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(notebookStatement) }
        try bindText(notebook.notebookID, to: notebookStatement, at: 1)
        try bindText(notebook.ownerDeviceID, to: notebookStatement, at: 2)
        try bindText(notebook.backingSessionID, to: notebookStatement, at: 3)
        try bindText(notebook.title, to: notebookStatement, at: 4)
        try bindText(notebook.model, to: notebookStatement, at: 5)
        try bindText(notebook.promptSkillBinding.identifier, to: notebookStatement, at: 6)
        try bindText(notebook.promptSkillBinding.revision, to: notebookStatement, at: 7)
        try bindText(notebook.lifecycle.rawValue, to: notebookStatement, at: 8)
        try bindDouble(notebook.createdAt.timeIntervalSince1970, to: notebookStatement, at: 9)
        try bindDouble(notebook.updatedAt.timeIntervalSince1970, to: notebookStatement, at: 10)
        try stepDone(notebookStatement, database: database)

        let grantStatement = try prepare(
            database,
            "INSERT INTO \(grantsTable)(notebook_id, position, grant_id) VALUES (?, ?, ?)"
        )
        defer { sqlite3_finalize(grantStatement) }
        for (position, grantID) in notebook.trustedSourceGrantIDs.enumerated() {
            sqlite3_reset(grantStatement)
            sqlite3_clear_bindings(grantStatement)
            try bindText(notebook.notebookID, to: grantStatement, at: 1)
            try bindInt(position, to: grantStatement, at: 2)
            try bindText(grantID, to: grantStatement, at: 3)
            try stepDone(grantStatement, database: database)
        }
    }

    private static func notebookIDExists(
        _ notebookID: String,
        database: OpaquePointer
    ) throws -> Bool {
        try exists(
            sql: "SELECT 1 FROM \(notebooksTable) WHERE notebook_id = ? LIMIT 1",
            bindings: [notebookID],
            database: database
        )
    }

    private static func backingSessionExists(
        ownerDeviceID: String,
        backingSessionID: String,
        database: OpaquePointer
    ) throws -> Bool {
        try exists(
            sql: "SELECT 1 FROM \(notebooksTable) WHERE owner_device_id = ? AND backing_session_id = ? LIMIT 1",
            bindings: [ownerDeviceID, backingSessionID],
            database: database
        )
    }

    private static func exists(
        sql: String,
        bindings: [String],
        database: OpaquePointer
    ) throws -> Bool {
        let statement = try prepare(database, sql)
        defer { sqlite3_finalize(statement) }
        for (offset, value) in bindings.enumerated() {
            try bindText(value, to: statement, at: Int32(offset + 1))
        }
        let result = sqlite3_step(statement)
        if result == SQLITE_ROW { return true }
        if result == SQLITE_DONE { return false }
        throw failure(database, "Could not inspect research notebook uniqueness.")
    }

    private static func rowCount(
        ownerDeviceID: String,
        database: OpaquePointer
    ) throws -> Int {
        let statement = try prepare(
            database,
            "SELECT COUNT(*) FROM \(notebooksTable) WHERE owner_device_id = ?"
        )
        defer { sqlite3_finalize(statement) }
        try bindText(ownerDeviceID, to: statement, at: 1)
        guard sqlite3_step(statement) == SQLITE_ROW,
              let count = validInt(statement, at: 0),
              count >= 0,
              sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        return count
    }

    private static func readLifecycleIntent(
        notebookID: String,
        database: OpaquePointer
    ) throws -> RuntimeResearchNotebookLifecycleIntent? {
        let statement = try prepare(
            database,
            """
            SELECT notebook_id, owner_device_id, backing_session_id, mutation,
                   coordinator_id, operation_id, lease_expires_at
            FROM \(lifecycleIntentsTable)
            WHERE notebook_id = ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try bindText(notebookID, to: statement, at: 1)
        let first = sqlite3_step(statement)
        if first == SQLITE_DONE { return nil }
        guard first == SQLITE_ROW else {
            throw failure(database, "Could not read a research notebook lifecycle intent.")
        }
        let intent = try lifecycleIntent(from: statement)
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        return intent
    }

    private static func lifecycleIntent(
        from statement: OpaquePointer
    ) throws -> RuntimeResearchNotebookLifecycleIntent {
        guard let notebookID = validText(statement, at: 0),
              let ownerDeviceID = validText(statement, at: 1),
              let backingSessionID = validText(statement, at: 2),
              let rawMutation = validText(statement, at: 3),
              let mutation = RuntimeResearchNotebookLifecycleMutation(rawValue: rawMutation),
              let coordinatorID = validText(statement, at: 4),
              let operationID = validText(statement, at: 5),
              let leaseExpiresAt = validDouble(statement, at: 6) else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        let intent = RuntimeResearchNotebookLifecycleIntent(
            ownerDeviceID: ownerDeviceID,
            notebookID: notebookID,
            backingSessionID: backingSessionID,
            mutation: mutation,
            coordinatorID: coordinatorID,
            operationID: operationID,
            leaseExpiresAt: Date(timeIntervalSince1970: leaseExpiresAt)
        )
        try runtimeResearchNotebookValidateLifecycleIntent(intent)
        return intent
    }

    private static func deleteLifecycleIntent(
        _ intent: RuntimeResearchNotebookLifecycleIntent,
        database: OpaquePointer
    ) throws {
        let statement = try prepare(
            database,
            """
            DELETE FROM \(lifecycleIntentsTable)
            WHERE notebook_id = ? AND owner_device_id = ?
              AND backing_session_id = ? AND mutation = ?
              AND coordinator_id = ? AND operation_id = ? AND lease_expires_at = ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try bindText(intent.notebookID, to: statement, at: 1)
        try bindText(intent.ownerDeviceID, to: statement, at: 2)
        try bindText(intent.backingSessionID, to: statement, at: 3)
        try bindText(intent.mutation.rawValue, to: statement, at: 4)
        try bindText(intent.coordinatorID, to: statement, at: 5)
        try bindText(intent.operationID, to: statement, at: 6)
        try bindDouble(intent.leaseExpiresAt.timeIntervalSince1970, to: statement, at: 7)
        try stepDone(statement, database: database)
        guard sqlite3_changes(database) == 1 else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
    }

    private static func validateCompletedLifecycleIntent(
        _ intent: RuntimeResearchNotebookLifecycleIntent,
        database: OpaquePointer
    ) throws {
        guard let notebook = try readOne(
            whereClause: "owner_device_id = ? AND notebook_id = ?",
            bindings: [intent.ownerDeviceID, intent.notebookID],
            database: database
        ) else {
            guard intent.mutation == .delete else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
            return
        }
        guard notebook.backingSessionID == intent.backingSessionID else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        switch intent.mutation {
        case .create:
            guard notebook.lifecycle == .active else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
        case .archive:
            guard notebook.lifecycle == .archived else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
        case .restore:
            guard notebook.lifecycle == .active else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
        case .delete:
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
    }

    private static func ensureSchema(
        _ database: OpaquePointer,
        beforeSchemaMigrationLock: (@Sendable (Int) throws -> Void)?
    ) throws {
        try execute(database, "PRAGMA foreign_keys = ON")
        let version = try schemaUserVersion(database)
        guard (0...schemaVersion).contains(version) else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        if version != schemaVersion {
            try beforeSchemaMigrationLock?(version)
            try execute(database, "BEGIN IMMEDIATE")
            do {
                let lockedVersion = try schemaUserVersion(database)
                switch lockedVersion {
                case 0:
                    try createSchema(database)
                    try execute(database, "PRAGMA user_version = \(schemaVersion)")
                case 1:
                    try execute(database, "DROP TABLE IF EXISTS \(lifecycleIntentsTable)")
                    try execute(database, "DROP TABLE IF EXISTS \(metadataTable)")
                    try createLifecycleIntentsSchema(database)
                    try migrateV3NotebookSchema(database)
                    try resetMetadataSchema(database)
                    try execute(database, "PRAGMA user_version = \(schemaVersion)")
                case 2:
                    try migrateV2Schema(database)
                    try migrateV3NotebookSchema(database)
                    try resetMetadataSchema(database)
                    try execute(database, "PRAGMA user_version = \(schemaVersion)")
                case 3:
                    try migrateV3NotebookSchema(database)
                    try resetMetadataSchema(database)
                    try execute(database, "PRAGMA user_version = \(schemaVersion)")
                case schemaVersion:
                    break
                default:
                    throw RuntimeResearchNotebookStoreError.corruptPersistence
                }
                try execute(database, "COMMIT")
            } catch {
                try? execute(database, "ROLLBACK")
                throw error
            }
        }
        try verifySchema(database)
    }

    private static func createSchema(_ database: OpaquePointer) throws {
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS \(notebooksTable)(
                notebook_id TEXT PRIMARY KEY NOT NULL,
                owner_device_id TEXT NOT NULL,
                backing_session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_skill_id TEXT NOT NULL CHECK(
                    length(prompt_skill_id) BETWEEN 1 AND 64
                ),
                prompt_skill_revision TEXT NOT NULL CHECK(
                    length(prompt_skill_revision) = 64
                ),
                lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active', 'archived')),
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL CHECK(updated_at >= created_at),
                UNIQUE(owner_device_id, backing_session_id)
            )
            """
        )
        try createLifecycleIntentsSchema(database)
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS \(grantsTable)(
                notebook_id TEXT NOT NULL,
                position INTEGER NOT NULL CHECK(position >= 0 AND position < 8),
                grant_id TEXT NOT NULL,
                PRIMARY KEY(notebook_id, position),
                UNIQUE(notebook_id, grant_id),
                FOREIGN KEY(notebook_id) REFERENCES \(notebooksTable)(notebook_id) ON DELETE CASCADE
            )
            """
        )
        try createMetadataSchema(database)
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_research_notebooks_owner_order
            ON \(notebooksTable)(owner_device_id, lifecycle, updated_at DESC, notebook_id ASC)
            """
        )
    }

    private static func createLifecycleIntentsSchema(_ database: OpaquePointer) throws {
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS \(lifecycleIntentsTable)(
                notebook_id TEXT PRIMARY KEY NOT NULL,
                owner_device_id TEXT NOT NULL,
                backing_session_id TEXT NOT NULL,
                mutation TEXT NOT NULL CHECK(mutation IN ('create', 'archive', 'restore', 'delete')),
                coordinator_id TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                lease_expires_at REAL NOT NULL,
                FOREIGN KEY(notebook_id) REFERENCES \(notebooksTable)(notebook_id) ON DELETE CASCADE,
                FOREIGN KEY(owner_device_id, backing_session_id)
                    REFERENCES \(notebooksTable)(owner_device_id, backing_session_id)
                    ON DELETE CASCADE
            )
            """
        )
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_research_notebook_lifecycle_intents_owner
            ON \(lifecycleIntentsTable)(owner_device_id, lease_expires_at, backing_session_id, notebook_id)
            """
        )
    }

    private static func migrateV2Schema(_ database: OpaquePointer) throws {
        let v2Columns: Set<String> = [
            "notebook_id", "owner_device_id", "backing_session_id", "mutation"
        ]
        let v3Columns: Set<String> = [
            "notebook_id", "owner_device_id", "backing_session_id", "mutation",
            "coordinator_id", "operation_id", "lease_expires_at"
        ]
        let existingColumns = try tableColumns(lifecycleIntentsTable, database: database)
        if existingColumns == v3Columns {
            return
        }
        guard existingColumns == v2Columns else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        let migratedTable = lifecycleIntentsTable + "_v3_migration"
        try execute(database, "DROP TABLE IF EXISTS \(migratedTable)")
        try execute(
            database,
            """
            CREATE TABLE \(migratedTable)(
                notebook_id TEXT PRIMARY KEY NOT NULL,
                owner_device_id TEXT NOT NULL,
                backing_session_id TEXT NOT NULL,
                mutation TEXT NOT NULL CHECK(mutation IN ('create', 'archive', 'restore', 'delete')),
                coordinator_id TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                lease_expires_at REAL NOT NULL,
                FOREIGN KEY(notebook_id) REFERENCES \(notebooksTable)(notebook_id) ON DELETE CASCADE,
                FOREIGN KEY(owner_device_id, backing_session_id)
                    REFERENCES \(notebooksTable)(owner_device_id, backing_session_id)
                    ON DELETE CASCADE
            )
            """
        )
        try execute(
            database,
            """
            INSERT INTO \(migratedTable)(
                notebook_id, owner_device_id, backing_session_id, mutation,
                coordinator_id, operation_id, lease_expires_at
            )
            SELECT notebook_id, owner_device_id, backing_session_id, mutation,
                   '\(migratedV2CoordinatorID)',
                   substr(notebook_id, length('\(RuntimeResearchNotebook.notebookIDPrefix)') + 1),
                   0
            FROM \(lifecycleIntentsTable)
            """
        )
        try execute(database, "DROP TABLE IF EXISTS \(metadataTable)")
        try execute(database, "DROP TABLE \(lifecycleIntentsTable)")
        try execute(database, "ALTER TABLE \(migratedTable) RENAME TO \(lifecycleIntentsTable)")
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_research_notebook_lifecycle_intents_owner
            ON \(lifecycleIntentsTable)(owner_device_id, lease_expires_at, backing_session_id, notebook_id)
            """
        )
    }

    private static func migrateV3NotebookSchema(_ database: OpaquePointer) throws {
        let v3NotebookColumns: Set<String> = [
            "notebook_id", "owner_device_id", "backing_session_id", "title", "model",
            "lifecycle", "created_at", "updated_at"
        ]
        let v4NotebookColumns = v3NotebookColumns.union([
            "prompt_skill_id", "prompt_skill_revision"
        ])
        let existingNotebookColumns = try tableColumns(notebooksTable, database: database)
        if existingNotebookColumns == v4NotebookColumns {
            try validateMigratedRows(database)
            return
        }
        guard existingNotebookColumns == v3NotebookColumns,
              try tableColumns(grantsTable, database: database) == [
                "notebook_id", "position", "grant_id"
              ],
              try tableColumns(lifecycleIntentsTable, database: database) == [
                "notebook_id", "owner_device_id", "backing_session_id", "mutation",
                "coordinator_id", "operation_id", "lease_expires_at"
              ] else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }

        let notebookMigration = "runtime_research_notebooks_v4_migration"
        let grantMigration = "runtime_research_notebook_grants_v4_migration"
        let intentMigration = "runtime_research_notebook_intents_v4_migration"
        try execute(database, "DROP TABLE IF EXISTS temp.\(notebookMigration)")
        try execute(database, "DROP TABLE IF EXISTS temp.\(grantMigration)")
        try execute(database, "DROP TABLE IF EXISTS temp.\(intentMigration)")
        try execute(
            database,
            """
            CREATE TEMP TABLE \(notebookMigration) AS
            SELECT notebook_id, owner_device_id, backing_session_id, title, model,
                   lifecycle, created_at, updated_at
            FROM \(notebooksTable)
            """
        )
        try execute(
            database,
            """
            CREATE TEMP TABLE \(grantMigration) AS
            SELECT notebook_id, position, grant_id FROM \(grantsTable)
            """
        )
        try execute(
            database,
            """
            CREATE TEMP TABLE \(intentMigration) AS
            SELECT notebook_id, owner_device_id, backing_session_id, mutation,
                   coordinator_id, operation_id, lease_expires_at
            FROM \(lifecycleIntentsTable)
            """
        )

        try execute(database, "DROP TABLE \(grantsTable)")
        try execute(database, "DROP TABLE \(lifecycleIntentsTable)")
        try execute(database, "DROP TABLE \(notebooksTable)")
        try execute(database, "DROP TABLE IF EXISTS \(metadataTable)")
        try createSchema(database)
        try execute(
            database,
            """
            INSERT INTO \(notebooksTable)(
                notebook_id, owner_device_id, backing_session_id, title, model,
                prompt_skill_id, prompt_skill_revision, lifecycle, created_at, updated_at
            )
            SELECT notebook_id, owner_device_id, backing_session_id, title, model,
                   '\(RuntimePromptSkillRegistry.researchBriefSkillID)',
                   '\(RuntimePromptSkillRegistry.researchBriefRevision)',
                   lifecycle, created_at, updated_at
            FROM temp.\(notebookMigration)
            """
        )
        try execute(
            database,
            """
            INSERT INTO \(grantsTable)(notebook_id, position, grant_id)
            SELECT notebook_id, position, grant_id FROM temp.\(grantMigration)
            """
        )
        try execute(
            database,
            """
            INSERT INTO \(lifecycleIntentsTable)(
                notebook_id, owner_device_id, backing_session_id, mutation,
                coordinator_id, operation_id, lease_expires_at
            )
            SELECT notebook_id, owner_device_id, backing_session_id, mutation,
                   coordinator_id, operation_id, lease_expires_at
            FROM temp.\(intentMigration)
            """
        )
        try execute(database, "DROP TABLE temp.\(intentMigration)")
        try execute(database, "DROP TABLE temp.\(grantMigration)")
        try execute(database, "DROP TABLE temp.\(notebookMigration)")
        try validateMigratedRows(database)
    }

    private static func validateMigratedRows(_ database: OpaquePointer) throws {
        let notebookStatement = try prepare(
            database,
            "SELECT notebook_id FROM \(notebooksTable) ORDER BY notebook_id"
        )
        defer { sqlite3_finalize(notebookStatement) }
        while true {
            let result = sqlite3_step(notebookStatement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW,
                  let notebookID = validText(notebookStatement, at: 0),
                  try readOne(
                    whereClause: "notebook_id = ?",
                    bindings: [notebookID],
                    database: database
                  ) != nil else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
        }

        let intentStatement = try prepare(
            database,
            """
            SELECT notebook_id, owner_device_id, backing_session_id, mutation,
                   coordinator_id, operation_id, lease_expires_at
            FROM \(lifecycleIntentsTable)
            ORDER BY notebook_id
            """
        )
        defer { sqlite3_finalize(intentStatement) }
        while true {
            let result = sqlite3_step(intentStatement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
            _ = try lifecycleIntent(from: intentStatement)
        }

        let foreignKeyStatement = try prepare(database, "PRAGMA foreign_key_check")
        defer { sqlite3_finalize(foreignKeyStatement) }
        guard sqlite3_step(foreignKeyStatement) == SQLITE_DONE else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
    }

    private static func resetMetadataSchema(_ database: OpaquePointer) throws {
        try execute(database, "DROP TABLE IF EXISTS \(metadataTable)")
        try createMetadataSchema(database)
    }

    private static func createMetadataSchema(_ database: OpaquePointer) throws {
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS \(metadataTable)(
                singleton INTEGER PRIMARY KEY NOT NULL CHECK(singleton = 1),
                schema_version INTEGER NOT NULL CHECK(schema_version = 4)
            )
            """
        )
        try execute(
            database,
            "INSERT OR IGNORE INTO \(metadataTable)(singleton, schema_version) VALUES (1, 4)"
        )
    }

    private static func verifySchema(_ database: OpaquePointer) throws {
        let requiredNotebookColumns: Set<String> = [
            "notebook_id", "owner_device_id", "backing_session_id", "title", "model",
            "prompt_skill_id", "prompt_skill_revision", "lifecycle", "created_at", "updated_at"
        ]
        let requiredGrantColumns: Set<String> = ["notebook_id", "position", "grant_id"]
        let requiredLifecycleIntentColumns: Set<String> = [
            "notebook_id", "owner_device_id", "backing_session_id", "mutation",
            "coordinator_id", "operation_id", "lease_expires_at"
        ]
        let requiredMetadataColumns: Set<String> = ["singleton", "schema_version"]
        guard try tableColumns(notebooksTable, database: database) == requiredNotebookColumns,
              try tableColumns(grantsTable, database: database) == requiredGrantColumns,
              try tableColumns(lifecycleIntentsTable, database: database)
                == requiredLifecycleIntentColumns,
              try tableColumns(metadataTable, database: database) == requiredMetadataColumns else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        let statement = try prepare(
            database,
            "SELECT singleton, schema_version FROM \(metadataTable)"
        )
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW,
              validInt(statement, at: 0) == 1,
              validInt(statement, at: 1) == 4,
              sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
    }

    private static func schemaUserVersion(_ database: OpaquePointer) throws -> Int {
        let statement = try prepare(database, "PRAGMA user_version")
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW,
              let version = validInt(statement, at: 0),
              sqlite3_step(statement) == SQLITE_DONE else {
            throw RuntimeResearchNotebookStoreError.corruptPersistence
        }
        return version
    }

    private static func tableColumns(
        _ table: String,
        database: OpaquePointer
    ) throws -> Set<String> {
        let statement = try prepare(database, "PRAGMA table_info(\(table))")
        defer { sqlite3_finalize(statement) }
        var columns = Set<String>()
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return columns }
            guard result == SQLITE_ROW,
                  let name = validText(statement, at: 1) else {
                throw RuntimeResearchNotebookStoreError.corruptPersistence
            }
            columns.insert(name)
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

    private static func validDouble(_ statement: OpaquePointer, at index: Int32) -> Double? {
        guard sqlite3_column_type(statement, index) == SQLITE_FLOAT else { return nil }
        let value = sqlite3_column_double(statement, index)
        return value.isFinite ? value : nil
    }

    private static func sqliteCanonicalDate(_ value: Date) -> Date {
        Date(timeIntervalSince1970: value.timeIntervalSince1970)
    }

    private static func execute(_ database: OpaquePointer, _ sql: String) throws {
        var message: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(database, sql, nil, nil, &message) == SQLITE_OK else {
            defer { sqlite3_free(message) }
            let detail = message.map { String(cString: $0) } ?? "unknown SQLite failure"
            throw RuntimeResearchNotebookStoreError.storageFailure(detail)
        }
    }

    private static func prepare(_ database: OpaquePointer, _ sql: String) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw failure(database, "Could not prepare a research notebook statement.")
        }
        return statement
    }

    private static func bindText(
        _ value: String,
        to statement: OpaquePointer,
        at index: Int32
    ) throws {
        guard sqlite3_bind_text(statement, index, value, -1, SQLITE_TRANSIENT) == SQLITE_OK else {
            throw RuntimeResearchNotebookStoreError.storageFailure(
                "Could not bind research notebook text."
            )
        }
    }

    private static func bindInt(
        _ value: Int,
        to statement: OpaquePointer,
        at index: Int32
    ) throws {
        guard sqlite3_bind_int64(statement, index, sqlite3_int64(value)) == SQLITE_OK else {
            throw RuntimeResearchNotebookStoreError.storageFailure(
                "Could not bind a research notebook integer."
            )
        }
    }

    private static func bindDouble(
        _ value: Double,
        to statement: OpaquePointer,
        at index: Int32
    ) throws {
        guard value.isFinite,
              sqlite3_bind_double(statement, index, value) == SQLITE_OK else {
            throw RuntimeResearchNotebookStoreError.storageFailure(
                "Could not bind a research notebook timestamp."
            )
        }
    }

    private static func stepDone(
        _ statement: OpaquePointer,
        database: OpaquePointer
    ) throws {
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw failure(database, "Could not write research notebook metadata.")
        }
    }

    private static func failure(_ database: OpaquePointer, _ prefix: String) -> Error {
        let detail = sqlite3_errmsg(database).map { String(cString: $0) }
            ?? "unknown SQLite failure"
        return RuntimeResearchNotebookStoreError.storageFailure("\(prefix) \(detail)")
    }
}

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
