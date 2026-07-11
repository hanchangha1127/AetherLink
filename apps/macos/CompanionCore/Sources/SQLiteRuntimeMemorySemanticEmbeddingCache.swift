import Foundation
import SQLite3

enum SQLiteRuntimeMemorySemanticEmbeddingCacheError: Error, LocalizedError {
    case failure(String)

    var errorDescription: String? {
        switch self {
        case .failure(let message): message
        }
    }
}

final class SQLiteRuntimeMemorySemanticEmbeddingCache: @unchecked Sendable {
    private let databaseURL: URL
    private let rowLimitPerOwnerModel: Int
    private let lock = NSLock()

    init(databaseURL: URL, rowLimitPerOwnerModel: Int = 2_000) {
        self.databaseURL = databaseURL
        self.rowLimitPerOwnerModel = max(1, rowLimitPerOwnerModel)
    }

    func cachedEmbeddings(
        for keys: [RuntimeMemorySemanticEmbeddingKey]
    ) throws -> [RuntimeMemorySemanticEmbeddingRecord] {
        guard !keys.isEmpty else { return [] }
        let uniqueKeys = keys.reduce(into: [RuntimeMemorySemanticEmbeddingKey]()) { result, key in
            if !result.contains(key) { result.append(key) }
        }
        try uniqueKeys.forEach(Self.validate)
        return try lock.withLock {
            try withDatabase { database in
                try uniqueKeys.compactMap { key in
                    try cachedEmbedding(for: key, database: database)
                }
            }
        }
    }

    func upsertEmbeddings(
        _ records: [RuntimeMemorySemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws {
        guard !records.isEmpty else { return }
        try records.forEach(Self.validate)
        try lock.withLock {
            guard shouldCommit() else { return }
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    var scopes = Set<Scope>()
                    for record in records {
                        try upsert(record, database: database)
                        scopes.insert(Scope(key: record.key))
                    }
                    for scope in scopes {
                        try enforceRowLimit(scope, database: database)
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

    func deleteEmbeddings(ownerDeviceID: String?, entryID: String) throws {
        let cleanEntryID = entryID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanEntryID.isEmpty,
              FileManager.default.fileExists(atPath: databaseURL.path) else { return }
        try lock.withLock {
            try withDatabase { database in
                let statement = try Self.prepare(
                    database,
                    "DELETE FROM runtime_memory_semantic_embeddings WHERE owner_key = ? AND entry_id = ?"
                )
                defer { sqlite3_finalize(statement) }
                try Self.bindText(Self.ownerKey(ownerDeviceID), to: statement, at: 1)
                try Self.bindText(cleanEntryID, to: statement, at: 2)
                try Self.stepDone(statement, database: database)
            }
        }
    }

    private func cachedEmbedding(
        for key: RuntimeMemorySemanticEmbeddingKey,
        database: OpaquePointer
    ) throws -> RuntimeMemorySemanticEmbeddingRecord? {
        let statement = try Self.prepare(
            database,
            """
            SELECT dimension, vector_blob
            FROM runtime_memory_semantic_embeddings
            WHERE owner_key = ?
              AND entry_id = ?
              AND embedding_model_id = ?
              AND model_fingerprint = ?
              AND document_fingerprint = ?
              AND source_revision = ?
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(key.ownerDeviceID), to: statement, at: 1)
        try Self.bindText(key.entryID, to: statement, at: 2)
        try Self.bindText(key.canonicalQualifiedEmbeddingModelID, to: statement, at: 3)
        try Self.bindText(key.modelFingerprint, to: statement, at: 4)
        try Self.bindText(key.documentFingerprint, to: statement, at: 5)
        try Self.bindText(key.sourceRevision, to: statement, at: 6)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW else {
            throw Self.failure(database, "Could not read runtime memory semantic embedding.")
        }
        let dimension = Int(sqlite3_column_int64(statement, 0))
        let blobSize = Int(sqlite3_column_bytes(statement, 1))
        let blob = sqlite3_column_blob(statement, 1).map { Data(bytes: $0, count: blobSize) }
        guard sqlite3_column_type(statement, 0) == SQLITE_INTEGER,
              sqlite3_column_type(statement, 1) == SQLITE_BLOB,
              let blob,
              let embedding = Self.decode(blob, dimension: dimension) else {
            return nil
        }
        return RuntimeMemorySemanticEmbeddingRecord(key: key, embedding: embedding)
    }

    private func upsert(
        _ record: RuntimeMemorySemanticEmbeddingRecord,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_memory_semantic_embeddings(
                owner_key,
                entry_id,
                embedding_model_id,
                model_fingerprint,
                document_fingerprint,
                source_revision,
                dimension,
                vector_blob,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                owner_key,
                entry_id,
                embedding_model_id,
                model_fingerprint,
                document_fingerprint,
                source_revision
            ) DO UPDATE SET
                dimension = excluded.dimension,
                vector_blob = excluded.vector_blob
            """
        )
        defer { sqlite3_finalize(statement) }
        let key = record.key
        try Self.bindText(Self.ownerKey(key.ownerDeviceID), to: statement, at: 1)
        try Self.bindText(key.entryID, to: statement, at: 2)
        try Self.bindText(key.canonicalQualifiedEmbeddingModelID, to: statement, at: 3)
        try Self.bindText(key.modelFingerprint, to: statement, at: 4)
        try Self.bindText(key.documentFingerprint, to: statement, at: 5)
        try Self.bindText(key.sourceRevision, to: statement, at: 6)
        try Self.bindInt(record.embedding.count, to: statement, at: 7)
        try Self.bindBlob(Self.encode(record.embedding), to: statement, at: 8)
        try Self.bindDouble(Date().timeIntervalSince1970, to: statement, at: 9)
        try Self.stepDone(statement, database: database)
    }

    private func enforceRowLimit(_ scope: Scope, database: OpaquePointer) throws {
        let statement = try Self.prepare(
            database,
            """
            DELETE FROM runtime_memory_semantic_embeddings
            WHERE rowid IN (
                SELECT rowid
                FROM runtime_memory_semantic_embeddings
                WHERE owner_key = ? AND embedding_model_id = ?
                ORDER BY created_at DESC, entry_id ASC, source_revision ASC
                LIMIT -1 OFFSET ?
            )
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(scope.ownerKey, to: statement, at: 1)
        try Self.bindText(scope.embeddingModelID, to: statement, at: 2)
        try Self.bindInt(rowLimitPerOwnerModel, to: statement, at: 3)
        try Self.stepDone(statement, database: database)
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
            throw SQLiteRuntimeMemorySemanticEmbeddingCacheError.failure(
                "Could not open runtime memory semantic cache."
            )
        }
        defer {
            sqlite3_close(openedDatabase)
            try? RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        try Self.ensureSchema(openedDatabase)
        return try body(openedDatabase)
    }

    private static func ensureSchema(_ database: OpaquePointer) throws {
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_memory_semantic_embeddings(
                owner_key TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                embedding_model_id TEXT NOT NULL,
                model_fingerprint TEXT NOT NULL,
                document_fingerprint TEXT NOT NULL,
                source_revision TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                vector_blob BLOB NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY(
                    owner_key,
                    entry_id,
                    embedding_model_id,
                    model_fingerprint,
                    document_fingerprint,
                    source_revision
                )
            )
            """
        )
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_memory_semantic_owner_model_created
            ON runtime_memory_semantic_embeddings(owner_key, embedding_model_id, created_at DESC)
            """
        )
    }

    private static func validate(_ key: RuntimeMemorySemanticEmbeddingKey) throws {
        let values = [
            key.entryID,
            key.canonicalQualifiedEmbeddingModelID,
            key.modelFingerprint,
            key.documentFingerprint,
            key.sourceRevision
        ]
        guard values.allSatisfy({ !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }),
              key.documentFingerprint.count == 64,
              key.sourceRevision.count == 64 else {
            throw SQLiteRuntimeMemorySemanticEmbeddingCacheError.failure(
                "Runtime memory semantic embedding key is invalid."
            )
        }
    }

    private static func validate(_ record: RuntimeMemorySemanticEmbeddingRecord) throws {
        try validate(record.key)
        guard !record.embedding.isEmpty,
              record.embedding.count <= 65_536,
              record.embedding.allSatisfy(\.isFinite),
              record.embedding.contains(where: { $0 != 0 }) else {
            throw SQLiteRuntimeMemorySemanticEmbeddingCacheError.failure(
                "Runtime memory semantic embedding is invalid."
            )
        }
    }

    private static func ownerKey(_ ownerDeviceID: String?) -> String {
        let trimmed = ownerDeviceID?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return trimmed.isEmpty ? "" : trimmed
    }

    private static func encode(_ embedding: [Double]) -> Data {
        var data = Data(capacity: embedding.count * MemoryLayout<UInt64>.size)
        for value in embedding {
            var bits = value.bitPattern.littleEndian
            withUnsafeBytes(of: &bits) { data.append(contentsOf: $0) }
        }
        return data
    }

    private static func decode(_ data: Data, dimension: Int) -> [Double]? {
        guard dimension > 0,
              dimension <= 65_536,
              data.count == dimension * MemoryLayout<Double>.size else {
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
        guard embedding.count == dimension,
              embedding.allSatisfy(\.isFinite),
              embedding.contains(where: { $0 != 0 }) else {
            return nil
        }
        return embedding
    }

    private static func execute(_ database: OpaquePointer, _ sql: String) throws {
        var message: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(database, sql, nil, nil, &message) == SQLITE_OK else {
            defer { sqlite3_free(message) }
            let detail = message.map { String(cString: $0) } ?? "unknown SQLite failure"
            throw SQLiteRuntimeMemorySemanticEmbeddingCacheError.failure(detail)
        }
    }

    private static func prepare(_ database: OpaquePointer, _ sql: String) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw failure(database, "Could not prepare runtime memory semantic cache statement.")
        }
        return statement
    }

    private static func bindText(_ value: String, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_text(statement, index, value, -1, SQLITE_TRANSIENT) == SQLITE_OK else {
            throw SQLiteRuntimeMemorySemanticEmbeddingCacheError.failure("Could not bind semantic cache text.")
        }
    }

    private static func bindInt(_ value: Int, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_int64(statement, index, sqlite3_int64(value)) == SQLITE_OK else {
            throw SQLiteRuntimeMemorySemanticEmbeddingCacheError.failure("Could not bind semantic cache integer.")
        }
    }

    private static func bindDouble(_ value: Double, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_double(statement, index, value) == SQLITE_OK else {
            throw SQLiteRuntimeMemorySemanticEmbeddingCacheError.failure("Could not bind semantic cache number.")
        }
    }

    private static func bindBlob(_ value: Data, to statement: OpaquePointer, at index: Int32) throws {
        let result = value.withUnsafeBytes { bytes in
            sqlite3_bind_blob(statement, index, bytes.baseAddress, Int32(value.count), SQLITE_TRANSIENT)
        }
        guard result == SQLITE_OK else {
            throw SQLiteRuntimeMemorySemanticEmbeddingCacheError.failure("Could not bind semantic cache vector.")
        }
    }

    private static func stepDone(_ statement: OpaquePointer, database: OpaquePointer) throws {
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw failure(database, "Could not write runtime memory semantic cache.")
        }
    }

    private static func failure(_ database: OpaquePointer, _ prefix: String) -> Error {
        let detail = sqlite3_errmsg(database).map { String(cString: $0) } ?? "unknown SQLite failure"
        return SQLiteRuntimeMemorySemanticEmbeddingCacheError.failure("\(prefix) \(detail)")
    }
}

private struct Scope: Hashable {
    var ownerKey: String
    var embeddingModelID: String

    init(key: RuntimeMemorySemanticEmbeddingKey) {
        let trimmed = key.ownerDeviceID?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        ownerKey = trimmed.isEmpty ? "" : trimmed
        embeddingModelID = key.canonicalQualifiedEmbeddingModelID
    }
}

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
