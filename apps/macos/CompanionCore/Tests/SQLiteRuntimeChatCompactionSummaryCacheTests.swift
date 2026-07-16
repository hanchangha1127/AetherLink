import Foundation
import OllamaBackend
import SQLite3
import XCTest
@testable import CompanionCore

final class SQLiteRuntimeChatCompactionSummaryCacheTests: XCTestCase {
    func testLineageFingerprintGoldenAndCanonicalDistinctions() {
        let messages = goldenMessages()
        let prefixes = RuntimeChatCompactionSummaryLineageFingerprinter.prefixFingerprints(for: messages)
        let full = RuntimeChatCompactionSummaryLineageFingerprinter.fingerprint(for: messages)

        XCTAssertEqual(prefixes.count, 2)
        XCTAssertEqual(prefixes.last, full)
        XCTAssertEqual(full.algorithm, "sha256-length-framed-chat-compaction-summary-lineage-v1")
        XCTAssertEqual(full.compactedTurnCount, 2)
        XCTAssertEqual(full.canonicalByteCount, 242)
        XCTAssertEqual(full.digest, "a7ee716d92c0e67e3094785a950a88f04984aa6304ad0b776341279f74261473")
        XCTAssertEqual(
            prefixes,
            RuntimeChatCompactionSummaryLineageFingerprinter.prefixFingerprints(for: messages)
        )
        XCTAssertNotEqual(full.algorithm, RuntimeChatCompactionSourceFingerprinter.algorithm)
        XCTAssertNotEqual(full.algorithm, RuntimeChatCompactionSummarySourceFingerprinter.algorithm)

        var nilVersusEmpty = messages
        nilVersusEmpty[0].attachments[0].name = ""
        var attachmentOrder = messages
        attachmentOrder[0].attachments.swapAt(0, 1)
        var roleChanged = messages
        roleChanged[0].role = "assistant"
        var contentChanged = messages
        contentChanged[0].content += "!"
        let messageOrder = [messages[1], messages[0]]
        for variant in [nilVersusEmpty, attachmentOrder, roleChanged, contentChanged, messageOrder] {
            XCTAssertNotEqual(
                RuntimeChatCompactionSummaryLineageFingerprinter.fingerprint(for: variant).digest,
                full.digest
            )
        }
    }

    func testExactKeyRequiresFullLineageEvenWhenBoundedSourceMatches() throws {
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: temporaryDatabaseURL())
        let source = "same bounded summary source"
        let firstMessages = messages("one", "two")
        let baseline = key(source: source, messages: firstMessages)
        try cache.upsert(.init(key: baseline, summary: "first lineage"), if: { true })

        let changed = key(source: source, messages: messages("one edited", "two"))
        let longer = key(source: source, messages: messages("one", "two", "three"))
        XCTAssertEqual(try cache.cachedSummary(for: baseline), "first lineage")
        XCTAssertNil(try cache.cachedSummary(for: changed))
        XCTAssertNil(try cache.cachedSummary(for: longer))
    }

    func testStrictExtensionReturnsNewestMatchingPrefixByCountThenWriteOrder() throws {
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: temporaryDatabaseURL())
        let currentMessages = messages("one", "two", "three", "four")
        let countThreeOld = key(source: "old source", messages: currentMessages, count: 3)
        let countThreeNew = key(source: "new source", messages: currentMessages, count: 3)
        let countTwoNewestWrite = key(source: "latest write", messages: currentMessages, count: 2)
        try cache.upsert(.init(key: countThreeOld, summary: "older same count"), if: { true })
        try cache.upsert(.init(key: countThreeNew, summary: "newest matching count"), if: { true })
        try cache.upsert(.init(key: countTwoNewestWrite, summary: "newer write but shorter"), if: { true })

        let current = key(source: "current bounded source", messages: currentMessages)
        let result = try cache.newestStrictPrefixRecord(
            for: current,
            currentPrefixFingerprints: prefixes(currentMessages)
        )
        XCTAssertEqual(result?.key.compactedTurnCount, 3)
        XCTAssertEqual(result?.key.sourceFingerprintDigest, countThreeNew.sourceFingerprintDigest)
        XCTAssertEqual(result?.summary, "newest matching count")
    }

    func testStrictPrefixRejectsEditedReorderedAndUnrelatedLineages() throws {
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: temporaryDatabaseURL())
        let original = messages("one", "two", "three")
        try cache.upsert(
            .init(key: key(source: "prior", messages: original, count: 2), summary: "prior summary"),
            if: { true }
        )

        for currentMessages in [
            messages("one edited", "two", "three", "four"),
            messages("two", "one", "three", "four"),
            messages("unrelated", "history", "continues"),
        ] {
            XCTAssertNil(try cache.newestStrictPrefixRecord(
                for: key(source: "current", messages: currentMessages),
                currentPrefixFingerprints: prefixes(currentMessages)
            ))
        }
    }

    func testStrictPrefixScopeIsolatesOwnerSessionModelAndPolicy() throws {
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: temporaryDatabaseURL())
        let currentMessages = messages("one", "two", "three")
        let target = key(
            owner: "device-a",
            session: "session-a",
            source: "current",
            messages: currentMessages
        )
        let isolatedKeys = [
            key(owner: "device-b", session: "session-a", source: "owner", messages: currentMessages, count: 2),
            key(owner: "device-a", session: "session-b", source: "session", messages: currentMessages, count: 2),
            key(owner: "device-a", session: "session-a", source: "model", messages: currentMessages, count: 2, model: "lm_studio:model-a"),
            key(owner: "device-a", session: "session-a", source: "policy", messages: currentMessages, count: 2, policy: "policy-v2"),
        ]
        for isolated in isolatedKeys {
            try cache.upsert(.init(key: isolated, summary: isolated.sourceFingerprintDigest), if: { true })
        }
        XCTAssertNil(try cache.newestStrictPrefixRecord(
            for: target,
            currentPrefixFingerprints: prefixes(currentMessages)
        ))

        let matching = key(
            owner: "  device-a  ",
            session: "session-a",
            source: "matching",
            messages: currentMessages,
            count: 2
        )
        try cache.upsert(.init(key: matching, summary: "matching"), if: { true })
        XCTAssertEqual(try cache.newestStrictPrefixRecord(
            for: target,
            currentPrefixFingerprints: prefixes(currentMessages)
        )?.summary, "matching")
    }

    func testExactAndStrictPrefixScopesIsolatePromptSkillRevision() throws {
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: temporaryDatabaseURL())
        let currentMessages = messages("one", "two", "three")
        let historicalPrompt = "Historical chat compaction summary prompt."
        let historicalBinding = try RuntimePromptSkillBinding(
            identifier: RuntimePromptSkillRegistry.chatCompactionSummarySkillID,
            revision: RuntimePromptSkillRegistry.computedRevision(
                identifier: RuntimePromptSkillRegistry.chatCompactionSummarySkillID,
                effect: .promptOnly,
                prompt: historicalPrompt
            )
        )
        let historicalExact = key(
            source: "current",
            messages: currentMessages,
            promptSkillBinding: historicalBinding
        )
        let historicalPrefix = key(
            source: "historical prefix",
            messages: currentMessages,
            count: 2,
            promptSkillBinding: historicalBinding
        )
        try cache.upsert(.init(key: historicalExact, summary: "historical exact"), if: { true })
        try cache.upsert(.init(key: historicalPrefix, summary: "historical prefix"), if: { true })

        let current = key(source: "current", messages: currentMessages)
        XCTAssertNil(try cache.cachedSummary(for: current))
        XCTAssertNil(try cache.newestStrictPrefixRecord(
            for: current,
            currentPrefixFingerprints: prefixes(currentMessages)
        ))

        let currentPrefix = key(source: "current prefix", messages: currentMessages, count: 2)
        try cache.upsert(.init(key: currentPrefix, summary: "current prefix"), if: { true })
        XCTAssertEqual(try cache.newestStrictPrefixRecord(
            for: current,
            currentPrefixFingerprints: prefixes(currentMessages)
        )?.summary, "current prefix")
    }

    func testOldSchemaMigrationDropsRowsAndCreatesLineageColumns() throws {
        let databaseURL = temporaryDatabaseURL()
        try executeRaw(databaseURL, Self.oldSchemaSQL)
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: databaseURL)
        let current = key(source: "legacy source", messages: messages("one"))

        XCTAssertNil(try cache.cachedSummary(for: current))
        XCTAssertEqual(try queryInt(databaseURL, "SELECT COUNT(*) FROM runtime_chat_compaction_summaries"), 0)
        let columns = try queryStrings(databaseURL, "PRAGMA table_info(runtime_chat_compaction_summaries)", column: 1)
        XCTAssertTrue(columns.contains("lineage_fingerprint_digest"))
        XCTAssertTrue(columns.contains("compacted_turn_count"))
    }

    func testPrePromptSchemaMigrationDropsRowsAndCreatesPromptBindingColumns() throws {
        let databaseURL = temporaryDatabaseURL()
        try executeRaw(databaseURL, Self.prePromptSchemaSQL)
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: databaseURL)
        let current = key(source: "legacy source", messages: messages("one"))

        XCTAssertNil(try cache.cachedSummary(for: current))
        XCTAssertEqual(try queryInt(databaseURL, "SELECT COUNT(*) FROM runtime_chat_compaction_summaries"), 0)
        let columns = try queryStrings(databaseURL, "PRAGMA table_info(runtime_chat_compaction_summaries)", column: 1)
        XCTAssertTrue(columns.contains("prompt_skill_id"))
        XCTAssertTrue(columns.contains("prompt_skill_revision"))
    }

    func testSummaryPersistsAcrossReopenWithOwnerOnlyPermissions() throws {
        let databaseURL = temporaryDatabaseURL()
        let record = RuntimeChatCompactionSummaryCacheRecord(
            key: key(source: "durable source", messages: messages("one", "two")),
            summary: "durable summary"
        )
        try SQLiteRuntimeChatCompactionSummaryCache(databaseURL: databaseURL)
            .upsert(record, if: { true })

        let reopened = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.cachedSummary(for: record.key), record.summary)
        let attributes = try FileManager.default.attributesOfItem(atPath: databaseURL.path)
        XCTAssertEqual((attributes[.posixPermissions] as? NSNumber)?.intValue, 0o600)
    }

    func testCommitCancellationRollsBackInsertedSummary() throws {
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: temporaryDatabaseURL())
        let record = RuntimeChatCompactionSummaryCacheRecord(
            key: key(source: "source", messages: messages("one")),
            summary: "must roll back"
        )
        let gate = CommitGate(allowedChecks: 1)
        try cache.upsert(record, if: { gate.shouldCommit() })
        XCTAssertEqual(gate.checkCount, 2)
        XCTAssertNil(try cache.cachedSummary(for: record.key))
    }

    func testCorruptExactAndPrefixRowsAreCacheMisses() throws {
        let databaseURL = temporaryDatabaseURL()
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: databaseURL)
        let currentMessages = messages("one", "two", "three")
        let prior = key(source: "source", messages: currentMessages, count: 2)
        try cache.upsert(.init(key: prior, summary: "valid summary"), if: { true })
        try executeRaw(
            databaseURL,
            "UPDATE runtime_chat_compaction_summaries SET lineage_fingerprint_digest = '\(String(repeating: "A", count: 64))'"
        )

        XCTAssertNil(try cache.cachedSummary(for: prior))
        XCTAssertNil(try cache.newestStrictPrefixRecord(
            for: key(source: "current", messages: currentMessages),
            currentPrefixFingerprints: prefixes(currentMessages)
        ))
    }

    func testRowCapAndScopedDeleteRemainOwnerSessionBounded() throws {
        let cache = SQLiteRuntimeChatCompactionSummaryCache(
            databaseURL: temporaryDatabaseURL(),
            rowLimitPerOwnerSession: 2
        )
        let first = key(owner: "device-a", session: "bounded", source: "one", messages: messages("one"))
        let second = key(owner: "device-a", session: "bounded", source: "two", messages: messages("two"))
        let third = key(owner: "device-a", session: "bounded", source: "three", messages: messages("three"))
        let other = key(owner: "device-b", session: "bounded", source: "other", messages: messages("other"))
        for (key, summary) in [(first, "first"), (second, "second"), (other, "other"), (third, "third")] {
            try cache.upsert(.init(key: key, summary: summary), if: { true })
        }
        XCTAssertNil(try cache.cachedSummary(for: first))
        XCTAssertEqual(try cache.cachedSummary(for: second), "second")
        XCTAssertEqual(try cache.cachedSummary(for: third), "third")
        XCTAssertEqual(try cache.cachedSummary(for: other), "other")

        try cache.deleteSummaries(ownerDeviceID: " device-a ", sessionID: "bounded")
        XCTAssertNil(try cache.cachedSummary(for: second))
        XCTAssertNil(try cache.cachedSummary(for: third))
        XCTAssertEqual(try cache.cachedSummary(for: other), "other")
    }

    func testInvalidDigestsCountsSummariesAndPrefixListsThrow() throws {
        let cache = SQLiteRuntimeChatCompactionSummaryCache(databaseURL: temporaryDatabaseURL())
        let currentMessages = messages("one", "two")
        let valid = key(source: "source", messages: currentMessages)
        var invalidDigest = valid
        invalidDigest.lineageFingerprintDigest = String(repeating: "A", count: 64)
        XCTAssertThrowsError(try cache.cachedSummary(for: invalidDigest))
        var invalidCount = valid
        invalidCount.compactedTurnCount = 0
        XCTAssertThrowsError(try cache.cachedSummary(for: invalidCount))
        var wrongSkill = valid
        wrongSkill.promptSkillBinding = RuntimePromptSkillRegistry.researchBriefBinding
        XCTAssertThrowsError(try cache.cachedSummary(for: wrongSkill))
        XCTAssertThrowsError(try cache.upsert(.init(key: valid, summary: "   "), if: { true }))
        XCTAssertThrowsError(try cache.upsert(
            .init(key: valid, summary: String(repeating: "x", count: 16_385)),
            if: { true }
        ))
        XCTAssertThrowsError(try cache.newestStrictPrefixRecord(
            for: valid,
            currentPrefixFingerprints: Array(prefixes(currentMessages).dropLast())
        ))
    }

    private func goldenMessages() -> [ChatMessage] {
        [
            ChatMessage(
                role: "user",
                content: "Hello\n안녕",
                attachments: [
                    ChatAttachment(type: "text", mimeType: "text/plain", name: nil, dataBase64: "", text: "memo"),
                    ChatAttachment(type: "image", mimeType: "image/png", name: "a.png", dataBase64: "AQ==", text: nil),
                ]
            ),
            ChatMessage(role: "assistant", content: "Done", attachments: []),
        ]
    }

    private func messages(_ contents: String...) -> [ChatMessage] {
        contents.enumerated().map {
            ChatMessage(role: $0.offset.isMultiple(of: 2) ? "user" : "assistant", content: $0.element)
        }
    }

    private func prefixes(_ messages: [ChatMessage]) -> [RuntimeChatCompactionSummaryLineageFingerprint] {
        RuntimeChatCompactionSummaryLineageFingerprinter.prefixFingerprints(for: messages)
    }

    private func key(
        owner: String? = nil,
        session: String = "session-a",
        source: String,
        messages: [ChatMessage],
        count: Int? = nil,
        model: String = "ollama:model-a",
        policy: String = "policy-v1",
        promptSkillBinding: RuntimePromptSkillBinding = RuntimePromptSkillRegistry.chatCompactionSummaryBinding
    ) -> RuntimeChatCompactionSummaryCacheKey {
        let compactedCount = count ?? messages.count
        return RuntimeChatCompactionSummaryCacheKey(
            ownerDeviceID: owner,
            sessionID: session,
            sourceFingerprint: RuntimeChatCompactionSummarySourceFingerprinter.fingerprint(source: source),
            lineageFingerprint: RuntimeChatCompactionSummaryLineageFingerprinter.fingerprint(
                for: Array(messages.prefix(compactedCount))
            ),
            providerQualifiedModelID: model,
            summaryPolicy: policy,
            promptSkillBinding: promptSkillBinding
        )
    }

    private func temporaryDatabaseURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("runtime-chat-compaction-summary-cache.sqlite")
    }

    private func executeRaw(_ databaseURL: URL, _ sql: String) throws {
        try FileManager.default.createDirectory(
            at: databaseURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        var database: OpaquePointer?
        let flags = SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX
        guard sqlite3_open_v2(databaseURL.path, &database, flags, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatCompactionSummaryCacheTests", code: 1)
        }
        defer { sqlite3_close(database) }
        var message: UnsafeMutablePointer<CChar>?
        let result = sqlite3_exec(database, sql, nil, nil, &message)
        let detail = message.map { String(cString: $0) }
        sqlite3_free(message)
        guard result == SQLITE_OK else {
            throw NSError(domain: detail ?? "SQLiteRuntimeChatCompactionSummaryCacheTests", code: 2)
        }
    }

    private func queryInt(_ databaseURL: URL, _ sql: String) throws -> Int {
        let values = try query(databaseURL, sql) { Int(sqlite3_column_int64($0, 0)) }
        return try XCTUnwrap(values.first)
    }

    private func queryStrings(_ databaseURL: URL, _ sql: String, column: Int32) throws -> Set<String> {
        Set(try query(databaseURL, sql) { statement in
            String(cString: sqlite3_column_text(statement, column))
        })
    }

    private func query<T>(_ databaseURL: URL, _ sql: String, row: (OpaquePointer) -> T) throws -> [T] {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatCompactionSummaryCacheTests", code: 3)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw NSError(domain: "SQLiteRuntimeChatCompactionSummaryCacheTests", code: 4)
        }
        defer { sqlite3_finalize(statement) }
        var values: [T] = []
        while sqlite3_step(statement) == SQLITE_ROW { values.append(row(statement)) }
        return values
    }

    private static let oldSchemaSQL = """
    CREATE TABLE runtime_chat_compaction_summaries(
        owner_key TEXT NOT NULL, session_id TEXT NOT NULL,
        source_fingerprint_algorithm TEXT NOT NULL, source_fingerprint_digest TEXT NOT NULL,
        source_utf8_byte_count INTEGER NOT NULL, provider_qualified_model_id TEXT NOT NULL,
        summary_policy TEXT NOT NULL, summary TEXT NOT NULL, write_order INTEGER NOT NULL,
        PRIMARY KEY(owner_key, session_id, source_fingerprint_algorithm, source_fingerprint_digest,
                    source_utf8_byte_count, provider_qualified_model_id, summary_policy)
    );
    INSERT INTO runtime_chat_compaction_summaries VALUES(
        '', 'session-a', 'sha256-length-framed-chat-compaction-summary-source-v1',
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 13,
        'ollama:model-a', 'policy-v1', 'must be dropped', 1
    );
    """

    private static let prePromptSchemaSQL = """
    CREATE TABLE runtime_chat_compaction_summaries(
        owner_key TEXT NOT NULL, session_id TEXT NOT NULL,
        source_fingerprint_algorithm TEXT NOT NULL, source_fingerprint_digest TEXT NOT NULL,
        source_utf8_byte_count INTEGER NOT NULL,
        lineage_fingerprint_algorithm TEXT NOT NULL, lineage_fingerprint_digest TEXT NOT NULL,
        lineage_canonical_byte_count INTEGER NOT NULL, compacted_turn_count INTEGER NOT NULL,
        provider_qualified_model_id TEXT NOT NULL, summary_policy TEXT NOT NULL,
        summary TEXT NOT NULL, write_order INTEGER NOT NULL,
        PRIMARY KEY(owner_key, session_id, source_fingerprint_algorithm, source_fingerprint_digest,
                    source_utf8_byte_count, lineage_fingerprint_algorithm,
                    lineage_fingerprint_digest, lineage_canonical_byte_count, compacted_turn_count,
                    provider_qualified_model_id, summary_policy)
    );
    INSERT INTO runtime_chat_compaction_summaries VALUES(
        '', 'session-a', 'sha256-length-framed-chat-compaction-summary-source-v1',
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 13,
        'sha256-length-framed-chat-compaction-summary-lineage-v1',
        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        128, 1, 'ollama:model-a', 'policy-v1', 'must be dropped', 1
    );
    """
}

private final class CommitGate: @unchecked Sendable {
    private let lock = NSLock()
    private let allowedChecks: Int
    private var checks = 0

    init(allowedChecks: Int) { self.allowedChecks = allowedChecks }

    func shouldCommit() -> Bool {
        lock.withLock {
            checks += 1
            return checks <= allowedChecks
        }
    }

    var checkCount: Int { lock.withLock { checks } }
}
