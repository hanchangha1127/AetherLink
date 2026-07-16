import CryptoKit
import Foundation
import OllamaBackend
import SQLite3

public struct RuntimeChatCompactionSummarySourceFingerprint: Equatable, Sendable {
    public var algorithm: String
    public var digest: String
    public var sourceUTF8ByteCount: Int
}

public enum RuntimeChatCompactionSummarySourceFingerprinter {
    public static let algorithm = "sha256-length-framed-chat-compaction-summary-source-v1"

    public static func fingerprint(source: String) -> RuntimeChatCompactionSummarySourceFingerprint {
        var hasher = SHA256()

        func appendLengthFramed(_ data: Data) {
            var byteCount = UInt64(data.count).bigEndian
            hasher.update(data: withUnsafeBytes(of: &byteCount) { Data($0) })
            hasher.update(data: data)
        }

        let sourceData = Data(source.utf8)
        appendLengthFramed(Data("AetherLink runtime chat compaction summary source v1".utf8))
        appendLengthFramed(sourceData)
        return RuntimeChatCompactionSummarySourceFingerprint(
            algorithm: algorithm,
            digest: Self.digest(hasher.finalize()),
            sourceUTF8ByteCount: sourceData.count
        )
    }

    private static func digest(_ value: SHA256.Digest) -> String {
        value.map { String(format: "%02x", $0) }.joined()
    }
}

public struct RuntimeChatCompactionSummaryLineageFingerprint: Equatable, Hashable, Sendable {
    public var algorithm: String
    public var digest: String
    public var canonicalByteCount: Int
    public var compactedTurnCount: Int

    public init(
        algorithm: String,
        digest: String,
        canonicalByteCount: Int,
        compactedTurnCount: Int
    ) {
        self.algorithm = algorithm
        self.digest = digest
        self.canonicalByteCount = canonicalByteCount
        self.compactedTurnCount = compactedTurnCount
    }
}

public enum RuntimeChatCompactionSummaryLineageFingerprinter {
    public static let algorithm = "sha256-length-framed-chat-compaction-summary-lineage-v1"

    public static func prefixFingerprints(
        for messages: [ChatMessage]
    ) -> [RuntimeChatCompactionSummaryLineageFingerprint] {
        var accumulator = Accumulator()
        var fingerprints: [RuntimeChatCompactionSummaryLineageFingerprint] = []
        fingerprints.reserveCapacity(messages.count)
        for (index, message) in messages.enumerated() {
            accumulator.append(message)
            fingerprints.append(accumulator.fingerprint(compactedTurnCount: index + 1))
        }
        return fingerprints
    }

    public static func fingerprint(
        for messages: [ChatMessage]
    ) -> RuntimeChatCompactionSummaryLineageFingerprint {
        var accumulator = Accumulator()
        for message in messages {
            accumulator.append(message)
        }
        return accumulator.fingerprint(compactedTurnCount: messages.count)
    }

    private struct Accumulator {
        private var hasher = SHA256()
        private var canonicalByteCount = 0

        init() {
            append(Data("AetherLink runtime chat compaction summary lineage v1\0".utf8))
        }

        mutating func append(_ message: ChatMessage) {
            appendString(message.role)
            appendString(message.content)
            appendCount(message.attachments.count)
            for attachment in message.attachments {
                appendString(attachment.type)
                appendString(attachment.mimeType)
                appendOptionalString(attachment.name)
                appendOptionalString(attachment.dataBase64)
                appendOptionalString(attachment.text)
            }
        }

        func fingerprint(compactedTurnCount: Int) -> RuntimeChatCompactionSummaryLineageFingerprint {
            let snapshot = hasher
            return RuntimeChatCompactionSummaryLineageFingerprint(
                algorithm: RuntimeChatCompactionSummaryLineageFingerprinter.algorithm,
                digest: snapshot.finalize().map { String(format: "%02x", $0) }.joined(),
                canonicalByteCount: canonicalByteCount,
                compactedTurnCount: compactedTurnCount
            )
        }

        private mutating func append(_ data: Data) {
            hasher.update(data: data)
            canonicalByteCount += data.count
        }

        private mutating func appendByte(_ value: UInt8) {
            append(Data([value]))
        }

        private mutating func appendCount(_ value: Int) {
            var encoded = UInt64(value).bigEndian
            append(withUnsafeBytes(of: &encoded) { Data($0) })
        }

        private mutating func appendString(_ value: String) {
            let data = Data(value.utf8)
            appendCount(data.count)
            append(data)
        }

        private mutating func appendOptionalString(_ value: String?) {
            guard let value else {
                appendByte(0)
                return
            }
            appendByte(1)
            appendString(value)
        }
    }
}

public struct RuntimeChatCompactionSummaryCacheKey: Equatable, Hashable, Sendable {
    public var ownerDeviceID: String?
    public var sessionID: String
    public var sourceFingerprintAlgorithm: String
    public var sourceFingerprintDigest: String
    public var sourceUTF8ByteCount: Int
    public var lineageFingerprintAlgorithm: String
    public var lineageFingerprintDigest: String
    public var lineageCanonicalByteCount: Int
    public var compactedTurnCount: Int
    public var providerQualifiedModelID: String
    public var summaryPolicy: String
    public var promptSkillBinding: RuntimePromptSkillBinding

    public init(
        ownerDeviceID: String?,
        sessionID: String,
        sourceFingerprintAlgorithm: String,
        sourceFingerprintDigest: String,
        sourceUTF8ByteCount: Int,
        lineageFingerprintAlgorithm: String,
        lineageFingerprintDigest: String,
        lineageCanonicalByteCount: Int,
        compactedTurnCount: Int,
        providerQualifiedModelID: String,
        summaryPolicy: String,
        promptSkillBinding: RuntimePromptSkillBinding
    ) {
        self.ownerDeviceID = Self.normalizedOwnerDeviceID(ownerDeviceID)
        self.sessionID = sessionID
        self.sourceFingerprintAlgorithm = sourceFingerprintAlgorithm
        self.sourceFingerprintDigest = sourceFingerprintDigest
        self.sourceUTF8ByteCount = sourceUTF8ByteCount
        self.lineageFingerprintAlgorithm = lineageFingerprintAlgorithm
        self.lineageFingerprintDigest = lineageFingerprintDigest
        self.lineageCanonicalByteCount = lineageCanonicalByteCount
        self.compactedTurnCount = compactedTurnCount
        self.providerQualifiedModelID = providerQualifiedModelID
        self.summaryPolicy = summaryPolicy
        self.promptSkillBinding = promptSkillBinding
    }

    public init(
        ownerDeviceID: String?,
        sessionID: String,
        sourceFingerprint: RuntimeChatCompactionSummarySourceFingerprint,
        lineageFingerprint: RuntimeChatCompactionSummaryLineageFingerprint,
        providerQualifiedModelID: String,
        summaryPolicy: String,
        promptSkillBinding: RuntimePromptSkillBinding
    ) {
        self.init(
            ownerDeviceID: ownerDeviceID,
            sessionID: sessionID,
            sourceFingerprintAlgorithm: sourceFingerprint.algorithm,
            sourceFingerprintDigest: sourceFingerprint.digest,
            sourceUTF8ByteCount: sourceFingerprint.sourceUTF8ByteCount,
            lineageFingerprintAlgorithm: lineageFingerprint.algorithm,
            lineageFingerprintDigest: lineageFingerprint.digest,
            lineageCanonicalByteCount: lineageFingerprint.canonicalByteCount,
            compactedTurnCount: lineageFingerprint.compactedTurnCount,
            providerQualifiedModelID: providerQualifiedModelID,
            summaryPolicy: summaryPolicy,
            promptSkillBinding: promptSkillBinding
        )
    }

    public var lineageFingerprint: RuntimeChatCompactionSummaryLineageFingerprint {
        RuntimeChatCompactionSummaryLineageFingerprint(
            algorithm: lineageFingerprintAlgorithm,
            digest: lineageFingerprintDigest,
            canonicalByteCount: lineageCanonicalByteCount,
            compactedTurnCount: compactedTurnCount
        )
    }

    private static func normalizedOwnerDeviceID(_ ownerDeviceID: String?) -> String? {
        guard let value = ownerDeviceID?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else {
            return nil
        }
        return value
    }
}

public struct RuntimeChatCompactionSummaryCacheRecord: Equatable, Sendable {
    public var key: RuntimeChatCompactionSummaryCacheKey
    public var summary: String

    public init(key: RuntimeChatCompactionSummaryCacheKey, summary: String) {
        self.key = key
        self.summary = summary
    }
}

public protocol RuntimeChatCompactionSummaryCaching: AnyObject, Sendable {
    func cachedSummary(for key: RuntimeChatCompactionSummaryCacheKey) throws -> String?
    func newestStrictPrefixRecord(
        for key: RuntimeChatCompactionSummaryCacheKey,
        currentPrefixFingerprints: [RuntimeChatCompactionSummaryLineageFingerprint]
    ) throws -> RuntimeChatCompactionSummaryCacheRecord?
    func upsert(
        _ record: RuntimeChatCompactionSummaryCacheRecord,
        if shouldCommit: @Sendable () -> Bool
    ) throws
    func deleteSummaries(ownerDeviceID: String?, sessionID: String) throws
}

public enum SQLiteRuntimeChatCompactionSummaryCacheError: Error, Equatable, LocalizedError {
    case failure(String)

    public var errorDescription: String? {
        switch self {
        case .failure(let message): message
        }
    }
}

public final class SQLiteRuntimeChatCompactionSummaryCache: RuntimeChatCompactionSummaryCaching, @unchecked Sendable {
    public static let defaultRowLimitPerOwnerSession = 32
    public static let maximumSummaryUTF8Bytes = 16_384

    private static let maximumOwnerDeviceIDUTF8Bytes = 512
    private static let maximumSessionIDUTF8Bytes = 512
    private static let maximumFingerprintAlgorithmUTF8Bytes = 128
    private static let maximumModelIDUTF8Bytes = 1_024
    private static let maximumSummaryPolicyUTF8Bytes = 512
    private static let maximumSourceUTF8Bytes = 16 * 1_024 * 1_024
    private static let maximumLineageCanonicalBytes = 64 * 1_024 * 1_024
    private static let tableName = "runtime_chat_compaction_summaries"
    private static let requiredColumns: Set<String> = [
        "owner_key", "session_id", "source_fingerprint_algorithm",
        "source_fingerprint_digest", "source_utf8_byte_count",
        "lineage_fingerprint_algorithm", "lineage_fingerprint_digest",
        "lineage_canonical_byte_count", "compacted_turn_count",
        "provider_qualified_model_id", "summary_policy", "prompt_skill_id",
        "prompt_skill_revision", "summary", "write_order",
    ]

    private let databaseURL: URL
    private let rowLimitPerOwnerSession: Int
    private let lock = NSLock()

    public init(
        databaseURL: URL = SQLiteRuntimeChatCompactionSummaryCache.defaultDatabaseURL(),
        rowLimitPerOwnerSession: Int = defaultRowLimitPerOwnerSession
    ) {
        self.databaseURL = databaseURL
        self.rowLimitPerOwnerSession = max(1, min(rowLimitPerOwnerSession, Self.defaultRowLimitPerOwnerSession))
    }

    public func cachedSummary(for key: RuntimeChatCompactionSummaryCacheKey) throws -> String? {
        try Self.validate(key)
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                let statement = try Self.prepare(
                    database,
                    """
                    SELECT summary
                    FROM runtime_chat_compaction_summaries
                    WHERE owner_key = ?
                      AND session_id = ?
                      AND source_fingerprint_algorithm = ?
                      AND source_fingerprint_digest = ?
                      AND source_utf8_byte_count = ?
                      AND lineage_fingerprint_algorithm = ?
                      AND lineage_fingerprint_digest = ?
                      AND lineage_canonical_byte_count = ?
                      AND compacted_turn_count = ?
                      AND provider_qualified_model_id = ?
                      AND summary_policy = ?
                      AND prompt_skill_id = ?
                      AND prompt_skill_revision = ?
                    LIMIT 1
                    """
                )
                defer { sqlite3_finalize(statement) }
                try Self.bind(key, to: statement)
                let result = sqlite3_step(statement)
                if result == SQLITE_DONE { return nil }
                guard result == SQLITE_ROW else {
                    throw Self.failure(database, "Could not read chat compaction summary cache.")
                }
                return Self.validText(statement, at: 0).flatMap {
                    Self.isValidSummary($0) ? $0 : nil
                }
            }
        }
    }

    public func newestStrictPrefixRecord(
        for key: RuntimeChatCompactionSummaryCacheKey,
        currentPrefixFingerprints: [RuntimeChatCompactionSummaryLineageFingerprint]
    ) throws -> RuntimeChatCompactionSummaryCacheRecord? {
        try Self.validate(key)
        let fingerprintsByCount = try Self.validateCurrentPrefixFingerprints(
            currentPrefixFingerprints,
            for: key
        )
        guard key.compactedTurnCount > 1,
              FileManager.default.fileExists(atPath: databaseURL.path) else {
            return nil
        }
        return try lock.withLock {
            try withDatabase { database in
                let statement = try Self.prepare(
                    database,
                    """
                    SELECT source_fingerprint_algorithm, source_fingerprint_digest,
                           source_utf8_byte_count, lineage_fingerprint_algorithm,
                           lineage_fingerprint_digest, lineage_canonical_byte_count,
                           compacted_turn_count, summary
                    FROM runtime_chat_compaction_summaries
                    WHERE owner_key = ?
                      AND session_id = ?
                      AND provider_qualified_model_id = ?
                      AND summary_policy = ?
                      AND prompt_skill_id = ?
                      AND prompt_skill_revision = ?
                      AND compacted_turn_count < ?
                    ORDER BY compacted_turn_count DESC, write_order DESC
                    LIMIT ?
                    """
                )
                defer { sqlite3_finalize(statement) }
                try Self.bindText(Self.ownerKey(key.ownerDeviceID), to: statement, at: 1)
                try Self.bindText(key.sessionID, to: statement, at: 2)
                try Self.bindText(key.providerQualifiedModelID, to: statement, at: 3)
                try Self.bindText(key.summaryPolicy, to: statement, at: 4)
                try Self.bindText(key.promptSkillBinding.identifier, to: statement, at: 5)
                try Self.bindText(key.promptSkillBinding.revision, to: statement, at: 6)
                try Self.bindInt(key.compactedTurnCount, to: statement, at: 7)
                try Self.bindInt(rowLimitPerOwnerSession, to: statement, at: 8)

                while true {
                    let result = sqlite3_step(statement)
                    if result == SQLITE_DONE { return nil }
                    guard result == SQLITE_ROW else {
                        throw Self.failure(database, "Could not read chat compaction summary prefixes.")
                    }
                    guard let sourceAlgorithm = Self.validText(statement, at: 0),
                          let sourceDigest = Self.validText(statement, at: 1),
                          let sourceByteCount = Self.validInt(statement, at: 2),
                          let lineageAlgorithm = Self.validText(statement, at: 3),
                          let lineageDigest = Self.validText(statement, at: 4),
                          let lineageByteCount = Self.validInt(statement, at: 5),
                          let compactedTurnCount = Self.validInt(statement, at: 6),
                          let summary = Self.validText(statement, at: 7),
                          let expected = fingerprintsByCount[compactedTurnCount],
                          expected.algorithm == lineageAlgorithm,
                          expected.digest == lineageDigest,
                          expected.canonicalByteCount == lineageByteCount else {
                        continue
                    }
                    let candidateKey = RuntimeChatCompactionSummaryCacheKey(
                        ownerDeviceID: key.ownerDeviceID,
                        sessionID: key.sessionID,
                        sourceFingerprintAlgorithm: sourceAlgorithm,
                        sourceFingerprintDigest: sourceDigest,
                        sourceUTF8ByteCount: sourceByteCount,
                        lineageFingerprintAlgorithm: lineageAlgorithm,
                        lineageFingerprintDigest: lineageDigest,
                        lineageCanonicalByteCount: lineageByteCount,
                        compactedTurnCount: compactedTurnCount,
                        providerQualifiedModelID: key.providerQualifiedModelID,
                        summaryPolicy: key.summaryPolicy,
                        promptSkillBinding: key.promptSkillBinding
                    )
                    let candidate = RuntimeChatCompactionSummaryCacheRecord(
                        key: candidateKey,
                        summary: summary
                    )
                    guard (try? Self.validate(candidate)) != nil else { continue }
                    return candidate
                }
            }
        }
    }

    public func upsert(
        _ record: RuntimeChatCompactionSummaryCacheRecord,
        if shouldCommit: @Sendable () -> Bool
    ) throws {
        try Self.validate(record)
        try lock.withLock {
            guard shouldCommit() else { return }
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    try upsert(record, database: database)
                    try enforceRowLimit(for: record.key, database: database)
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

    public func deleteSummaries(ownerDeviceID: String?, sessionID: String) throws {
        let normalizedOwnerDeviceID = Self.normalizedOwnerDeviceID(ownerDeviceID)
        try Self.validateOwnerDeviceID(normalizedOwnerDeviceID)
        try Self.validateBoundedNonblank(
            sessionID,
            maximumUTF8Bytes: Self.maximumSessionIDUTF8Bytes,
            field: "session ID"
        )
        guard FileManager.default.fileExists(atPath: databaseURL.path) else { return }
        try lock.withLock {
            try withDatabase { database in
                let statement = try Self.prepare(
                    database,
                    "DELETE FROM runtime_chat_compaction_summaries WHERE owner_key = ? AND session_id = ?"
                )
                defer { sqlite3_finalize(statement) }
                try Self.bindText(Self.ownerKey(normalizedOwnerDeviceID), to: statement, at: 1)
                try Self.bindText(sessionID, to: statement, at: 2)
                try Self.stepDone(statement, database: database)
            }
        }
    }

    public static func defaultDatabaseURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-chat-compaction-summary-cache.sqlite", isDirectory: false)
    }

    private func upsert(
        _ record: RuntimeChatCompactionSummaryCacheRecord,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_chat_compaction_summaries(
                owner_key, session_id, source_fingerprint_algorithm,
                source_fingerprint_digest, source_utf8_byte_count,
                lineage_fingerprint_algorithm, lineage_fingerprint_digest,
                lineage_canonical_byte_count, compacted_turn_count,
                provider_qualified_model_id, summary_policy, prompt_skill_id,
                prompt_skill_revision, summary, write_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, (
                SELECT COALESCE(MAX(write_order), 0) + 1
                FROM runtime_chat_compaction_summaries
            ))
            ON CONFLICT(
                owner_key, session_id, source_fingerprint_algorithm,
                source_fingerprint_digest, source_utf8_byte_count,
                lineage_fingerprint_algorithm, lineage_fingerprint_digest,
                lineage_canonical_byte_count, compacted_turn_count,
                provider_qualified_model_id, summary_policy, prompt_skill_id,
                prompt_skill_revision
            ) DO UPDATE SET
                summary = excluded.summary,
                write_order = excluded.write_order
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bind(record.key, to: statement)
        try Self.bindText(record.summary, to: statement, at: 14)
        try Self.stepDone(statement, database: database)
    }

    private func enforceRowLimit(
        for key: RuntimeChatCompactionSummaryCacheKey,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            DELETE FROM runtime_chat_compaction_summaries
            WHERE rowid IN (
                SELECT rowid
                FROM runtime_chat_compaction_summaries
                WHERE owner_key = ? AND session_id = ?
                ORDER BY write_order DESC,
                         compacted_turn_count DESC,
                         lineage_fingerprint_digest ASC,
                         source_fingerprint_digest ASC
                LIMIT -1 OFFSET ?
            )
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ownerKey(key.ownerDeviceID), to: statement, at: 1)
        try Self.bindText(key.sessionID, to: statement, at: 2)
        try Self.bindInt(rowLimitPerOwnerSession, to: statement, at: 3)
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
            throw SQLiteRuntimeChatCompactionSummaryCacheError.failure(
                "Could not open chat compaction summary cache."
            )
        }
        defer {
            sqlite3_close(openedDatabase)
            try? RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        try Self.execute(openedDatabase, "PRAGMA temp_store = MEMORY")
        try Self.ensureSchema(openedDatabase)
        return try body(openedDatabase)
    }

    private static func ensureSchema(_ database: OpaquePointer) throws {
        let existingColumns = try tableColumns(database)
        if !existingColumns.isEmpty && !requiredColumns.isSubset(of: existingColumns) {
            try execute(database, "BEGIN IMMEDIATE")
            do {
                try execute(database, "DROP TABLE IF EXISTS runtime_chat_compaction_summaries")
                try createSchema(database)
                try execute(database, "COMMIT")
            } catch {
                try? execute(database, "ROLLBACK")
                throw error
            }
            return
        }
        try createSchema(database)
    }

    private static func createSchema(_ database: OpaquePointer) throws {
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_chat_compaction_summaries(
                owner_key TEXT NOT NULL,
                session_id TEXT NOT NULL,
                source_fingerprint_algorithm TEXT NOT NULL,
                source_fingerprint_digest TEXT NOT NULL,
                source_utf8_byte_count INTEGER NOT NULL,
                lineage_fingerprint_algorithm TEXT NOT NULL,
                lineage_fingerprint_digest TEXT NOT NULL,
                lineage_canonical_byte_count INTEGER NOT NULL,
                compacted_turn_count INTEGER NOT NULL CHECK(compacted_turn_count > 0),
                provider_qualified_model_id TEXT NOT NULL,
                summary_policy TEXT NOT NULL,
                prompt_skill_id TEXT NOT NULL,
                prompt_skill_revision TEXT NOT NULL,
                summary TEXT NOT NULL,
                write_order INTEGER NOT NULL,
                PRIMARY KEY(
                    owner_key, session_id, source_fingerprint_algorithm,
                    source_fingerprint_digest, source_utf8_byte_count,
                    lineage_fingerprint_algorithm, lineage_fingerprint_digest,
                    lineage_canonical_byte_count, compacted_turn_count,
                    provider_qualified_model_id, summary_policy, prompt_skill_id,
                    prompt_skill_revision
                )
            )
            """
        )
        try execute(
            database,
            """
            CREATE INDEX IF NOT EXISTS idx_runtime_chat_compaction_summary_lineage_scope_order
            ON runtime_chat_compaction_summaries(
                owner_key, session_id, provider_qualified_model_id, summary_policy,
                prompt_skill_id, prompt_skill_revision, compacted_turn_count DESC,
                write_order DESC
            )
            """
        )
    }

    private static func tableColumns(_ database: OpaquePointer) throws -> Set<String> {
        let statement = try prepare(database, "PRAGMA table_info(runtime_chat_compaction_summaries)")
        defer { sqlite3_finalize(statement) }
        var columns = Set<String>()
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return columns }
            guard result == SQLITE_ROW else {
                throw failure(database, "Could not inspect chat compaction summary cache schema.")
            }
            if let name = validText(statement, at: 1) {
                columns.insert(name)
            }
        }
    }

    private static func validate(_ key: RuntimeChatCompactionSummaryCacheKey) throws {
        let normalizedOwnerDeviceID = normalizedOwnerDeviceID(key.ownerDeviceID)
        guard normalizedOwnerDeviceID == key.ownerDeviceID else {
            throw invalid("owner device ID")
        }
        try validateOwnerDeviceID(normalizedOwnerDeviceID)
        try validateBoundedNonblank(
            key.sessionID,
            maximumUTF8Bytes: maximumSessionIDUTF8Bytes,
            field: "session ID"
        )
        try validateBoundedNonblank(
            key.sourceFingerprintAlgorithm,
            maximumUTF8Bytes: maximumFingerprintAlgorithmUTF8Bytes,
            field: "source fingerprint algorithm"
        )
        guard isCanonicalSHA256Digest(key.sourceFingerprintDigest),
              (0...maximumSourceUTF8Bytes).contains(key.sourceUTF8ByteCount) else {
            throw invalid("source fingerprint")
        }
        try validateBoundedNonblank(
            key.lineageFingerprintAlgorithm,
            maximumUTF8Bytes: maximumFingerprintAlgorithmUTF8Bytes,
            field: "lineage fingerprint algorithm"
        )
        guard isCanonicalSHA256Digest(key.lineageFingerprintDigest),
              (1...maximumLineageCanonicalBytes).contains(key.lineageCanonicalByteCount),
              key.compactedTurnCount > 0 else {
            throw invalid("lineage fingerprint")
        }
        try validateBoundedNonblank(
            key.providerQualifiedModelID,
            maximumUTF8Bytes: maximumModelIDUTF8Bytes,
            field: "provider-qualified model ID"
        )
        guard isProviderQualifiedModelID(key.providerQualifiedModelID) else {
            throw invalid("provider-qualified model ID")
        }
        try validateBoundedNonblank(
            key.summaryPolicy,
            maximumUTF8Bytes: maximumSummaryPolicyUTF8Bytes,
            field: "summary policy"
        )
        guard key.promptSkillBinding.identifier == RuntimePromptSkillRegistry.chatCompactionSummarySkillID else {
            throw invalid("prompt skill binding")
        }
    }

    private static func validate(
        _ fingerprint: RuntimeChatCompactionSummaryLineageFingerprint
    ) throws {
        try validateBoundedNonblank(
            fingerprint.algorithm,
            maximumUTF8Bytes: maximumFingerprintAlgorithmUTF8Bytes,
            field: "lineage fingerprint algorithm"
        )
        guard isCanonicalSHA256Digest(fingerprint.digest),
              (1...maximumLineageCanonicalBytes).contains(fingerprint.canonicalByteCount),
              fingerprint.compactedTurnCount > 0 else {
            throw invalid("lineage fingerprint")
        }
    }

    private static func validateCurrentPrefixFingerprints(
        _ fingerprints: [RuntimeChatCompactionSummaryLineageFingerprint],
        for key: RuntimeChatCompactionSummaryCacheKey
    ) throws -> [Int: RuntimeChatCompactionSummaryLineageFingerprint] {
        guard fingerprints.count == key.compactedTurnCount else {
            throw invalid("current prefix fingerprints")
        }
        var byCount: [Int: RuntimeChatCompactionSummaryLineageFingerprint] = [:]
        byCount.reserveCapacity(fingerprints.count)
        for (index, fingerprint) in fingerprints.enumerated() {
            try validate(fingerprint)
            guard fingerprint.compactedTurnCount == index + 1,
                  fingerprint.algorithm == key.lineageFingerprintAlgorithm else {
                throw invalid("current prefix fingerprints")
            }
            byCount[fingerprint.compactedTurnCount] = fingerprint
        }
        guard fingerprints.last == key.lineageFingerprint else {
            throw invalid("current prefix fingerprints")
        }
        return byCount
    }

    private static func validate(_ record: RuntimeChatCompactionSummaryCacheRecord) throws {
        try validate(record.key)
        guard isValidSummary(record.summary) else { throw invalid("summary") }
    }

    private static func validateOwnerDeviceID(_ value: String?) throws {
        guard let value else { return }
        try validateBoundedNonblank(
            value,
            maximumUTF8Bytes: maximumOwnerDeviceIDUTF8Bytes,
            field: "owner device ID"
        )
    }

    private static func validateBoundedNonblank(
        _ value: String,
        maximumUTF8Bytes: Int,
        field: String
    ) throws {
        guard value == value.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty,
              value.utf8.count <= maximumUTF8Bytes else {
            throw invalid(field)
        }
    }

    private static func isValidSummary(_ summary: String) -> Bool {
        !summary.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && summary.utf8.count <= maximumSummaryUTF8Bytes
    }

    private static func isCanonicalSHA256Digest(_ value: String) -> Bool {
        value.utf8.count == 64 && value.utf8.allSatisfy {
            ($0 >= 48 && $0 <= 57) || ($0 >= 97 && $0 <= 102)
        }
    }

    private static func isProviderQualifiedModelID(_ value: String) -> Bool {
        guard let separator = value.firstIndex(of: ":"),
              separator != value.startIndex else {
            return false
        }
        return value.index(after: separator) != value.endIndex
    }

    private static func normalizedOwnerDeviceID(_ ownerDeviceID: String?) -> String? {
        guard let value = ownerDeviceID?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else {
            return nil
        }
        return value
    }

    private static func ownerKey(_ ownerDeviceID: String?) -> String {
        normalizedOwnerDeviceID(ownerDeviceID) ?? ""
    }

    private static func bind(
        _ key: RuntimeChatCompactionSummaryCacheKey,
        to statement: OpaquePointer
    ) throws {
        try bindText(ownerKey(key.ownerDeviceID), to: statement, at: 1)
        try bindText(key.sessionID, to: statement, at: 2)
        try bindText(key.sourceFingerprintAlgorithm, to: statement, at: 3)
        try bindText(key.sourceFingerprintDigest, to: statement, at: 4)
        try bindInt(key.sourceUTF8ByteCount, to: statement, at: 5)
        try bindText(key.lineageFingerprintAlgorithm, to: statement, at: 6)
        try bindText(key.lineageFingerprintDigest, to: statement, at: 7)
        try bindInt(key.lineageCanonicalByteCount, to: statement, at: 8)
        try bindInt(key.compactedTurnCount, to: statement, at: 9)
        try bindText(key.providerQualifiedModelID, to: statement, at: 10)
        try bindText(key.summaryPolicy, to: statement, at: 11)
        try bindText(key.promptSkillBinding.identifier, to: statement, at: 12)
        try bindText(key.promptSkillBinding.revision, to: statement, at: 13)
    }

    private static func validText(_ statement: OpaquePointer, at index: Int32) -> String? {
        guard sqlite3_column_type(statement, index) == SQLITE_TEXT,
              let bytes = sqlite3_column_text(statement, index) else {
            return nil
        }
        let byteCount = Int(sqlite3_column_bytes(statement, index))
        return String(data: Data(bytes: bytes, count: byteCount), encoding: .utf8)
    }

    private static func validInt(_ statement: OpaquePointer, at index: Int32) -> Int? {
        guard sqlite3_column_type(statement, index) == SQLITE_INTEGER else { return nil }
        return Int(exactly: sqlite3_column_int64(statement, index))
    }

    private static func execute(_ database: OpaquePointer, _ sql: String) throws {
        var message: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(database, sql, nil, nil, &message) == SQLITE_OK else {
            defer { sqlite3_free(message) }
            let detail = message.map { String(cString: $0) } ?? "unknown SQLite failure"
            throw SQLiteRuntimeChatCompactionSummaryCacheError.failure(detail)
        }
    }

    private static func prepare(_ database: OpaquePointer, _ sql: String) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw failure(database, "Could not prepare chat compaction summary cache statement.")
        }
        return statement
    }

    private static func bindText(_ value: String, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_text(statement, index, value, -1, SQLITE_TRANSIENT) == SQLITE_OK else {
            throw SQLiteRuntimeChatCompactionSummaryCacheError.failure(
                "Could not bind chat compaction summary cache text."
            )
        }
    }

    private static func bindInt(_ value: Int, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_int64(statement, index, sqlite3_int64(value)) == SQLITE_OK else {
            throw SQLiteRuntimeChatCompactionSummaryCacheError.failure(
                "Could not bind chat compaction summary cache integer."
            )
        }
    }

    private static func stepDone(_ statement: OpaquePointer, database: OpaquePointer) throws {
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw failure(database, "Could not write chat compaction summary cache.")
        }
    }

    private static func failure(_ database: OpaquePointer, _ prefix: String) -> Error {
        let detail = sqlite3_errmsg(database).map { String(cString: $0) } ?? "unknown SQLite failure"
        return SQLiteRuntimeChatCompactionSummaryCacheError.failure("\(prefix) \(detail)")
    }

    private static func invalid(_ field: String) -> SQLiteRuntimeChatCompactionSummaryCacheError {
        .failure("Runtime chat compaction summary cache \(field) is invalid.")
    }
}

public final class NullRuntimeChatCompactionSummaryCache: RuntimeChatCompactionSummaryCaching, @unchecked Sendable {
    public init() {}

    public func cachedSummary(for key: RuntimeChatCompactionSummaryCacheKey) throws -> String? {
        nil
    }

    public func newestStrictPrefixRecord(
        for key: RuntimeChatCompactionSummaryCacheKey,
        currentPrefixFingerprints: [RuntimeChatCompactionSummaryLineageFingerprint]
    ) throws -> RuntimeChatCompactionSummaryCacheRecord? {
        nil
    }

    public func upsert(
        _ record: RuntimeChatCompactionSummaryCacheRecord,
        if shouldCommit: @Sendable () -> Bool
    ) throws {}

    public func deleteSummaries(ownerDeviceID: String?, sessionID: String) throws {}
}

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
