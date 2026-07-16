import Foundation
import XCTest
@testable import CompanionCore

final class RuntimeMemoryStoreGeneratedDraftTests: XCTestCase {
    func testGeneratedDraftCacheIsOwnerScopedAndDoesNotCreateApprovedEntry() throws {
        let store = JSONLRuntimeMemoryStore(fileURL: try temporaryStoreURL())
        let deviceADraft = generatedDraft(content: "Device A summary", generatedAt: 100)
        let deviceBDraft = generatedDraft(content: "Device B summary", generatedAt: 101)

        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: deviceADraft)
        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-b", draft: deviceBDraft)

        XCTAssertEqual(
            try store.generatedMemorySummaryDraft(ownerDeviceID: "device-a", draftID: deviceADraft.draftID),
            deviceADraft
        )
        XCTAssertEqual(
            try store.generatedMemorySummaryDraft(ownerDeviceID: "device-b", draftID: deviceBDraft.draftID),
            deviceBDraft
        )
        XCTAssertTrue(try store.generatedMemorySummaryDrafts(ownerDeviceID: nil).isEmpty)
        XCTAssertTrue(try store.list(ownerDeviceID: "device-a").isEmpty)
        XCTAssertTrue(try store.listAll().isEmpty)
    }

    func testGeneratedDraftCacheKeepsLatestDraftAndReopens() throws {
        let fileURL = try temporaryStoreURL()
        let store = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let original = generatedDraft(content: "Original summary", generatedAt: 200)
        let historicalBinding = try RuntimePromptSkillBinding(
            identifier: RuntimePromptSkillRegistry.memorySummaryDraftSkillID,
            revision: String(repeating: "a", count: 64)
        )
        let replacement = generatedDraft(
            content: "Replacement summary",
            generatedAt: 201,
            modelID: "ollama:replacement",
            promptSkillBinding: historicalBinding
        )

        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: original)
        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: replacement)

        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 2)
        XCTAssertEqual(try store.generatedMemorySummaryDrafts(ownerDeviceID: "device-a"), [replacement])
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDraft(ownerDeviceID: "device-a", draftID: replacement.draftID),
            replacement
        )
    }

    func testGeneratedDraftCacheDoesNotAppendExactDuplicate() throws {
        let fileURL = try temporaryStoreURL()
        let store = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let draft = generatedDraft(content: "Stable summary", generatedAt: 225)

        let first = try store.cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: draft,
            if: { true }
        )
        let second = try store.cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: draft,
            if: { true }
        )

        XCTAssertEqual(first, draft)
        XCTAssertEqual(second, draft)
        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 1)
    }

    func testGeneratedDraftCacheDeduplicatesConcurrentCrossInstanceWrites() async throws {
        let fileURL = try temporaryStoreURL()
        let firstStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let secondStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let draft = generatedDraft(
            content: "Cross-instance stable summary",
            generatedAt: 230,
            persistenceOperationID: "00000000-0000-4000-8000-000000000031"
        )
        let ready = DispatchSemaphore(value: 0)
        let start = DispatchSemaphore(value: 0)

        async let firstResult = Self.cacheGeneratedDraft(
            in: firstStore,
            draft: draft,
            ready: ready,
            start: start
        )
        async let secondResult = Self.cacheGeneratedDraft(
            in: secondStore,
            draft: draft,
            ready: ready,
            start: start
        )
        XCTAssertEqual(ready.wait(timeout: .now() + 1), .success)
        XCTAssertEqual(ready.wait(timeout: .now() + 1), .success)
        start.signal()
        start.signal()

        let first = try await firstResult
        let second = try await secondResult
        XCTAssertEqual(first, draft)
        XCTAssertEqual(second, draft)
        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 1)
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDraft(ownerDeviceID: "device-a", draftID: draft.draftID),
            draft
        )
    }

    func testGeneratedDraftCacheDoesNotReappendHistoricalExactDraftAfterReplacement() throws {
        let fileURL = try temporaryStoreURL()
        let firstStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let secondStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let original = generatedDraft(
            content: "Original retry candidate",
            generatedAt: 232,
            persistenceOperationID: "00000000-0000-4000-8000-000000000001"
        )
        let replacement = generatedDraft(
            content: "Current replacement",
            generatedAt: 233,
            persistenceOperationID: "00000000-0000-4000-8000-000000000002"
        )

        try firstStore.cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: original
        )
        try secondStore.cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: replacement
        )
        let retried = try firstStore.cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: original,
            if: { true }
        )

        XCTAssertEqual(retried, original)
        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 2)
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDraft(ownerDeviceID: "device-a", draftID: original.draftID),
            replacement
        )
    }

    func testGeneratedDraftCacheAppendsNewIdenticalValueWithDistinctOperationID() throws {
        let fileURL = try temporaryStoreURL()
        let store = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let original = generatedDraft(
            content: "Identical generated value",
            generatedAt: 234,
            persistenceOperationID: "00000000-0000-4000-8000-000000000011"
        )
        let replacement = generatedDraft(
            content: "Replacement between identical values",
            generatedAt: 234,
            persistenceOperationID: "00000000-0000-4000-8000-000000000012"
        )
        let regenerated = generatedDraft(
            content: original.content,
            generatedAt: original.generatedAt.timeIntervalSince1970,
            persistenceOperationID: "00000000-0000-4000-8000-000000000013"
        )

        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: original)
        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: replacement)
        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: regenerated)

        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 3)
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDraft(ownerDeviceID: "device-a", draftID: original.draftID),
            regenerated
        )
    }

    func testGeneratedDraftCacheRejectsConflictingValueForSameOperationID() throws {
        let fileURL = try temporaryStoreURL()
        let store = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let operationID = "00000000-0000-4000-8000-000000000021"
        let original = generatedDraft(
            content: "Original operation value",
            generatedAt: 236,
            persistenceOperationID: operationID
        )
        let conflicting = generatedDraft(
            content: "Conflicting operation value",
            generatedAt: 236,
            persistenceOperationID: operationID
        )

        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: original)

        XCTAssertThrowsError(
            try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: conflicting)
        ) { error in
            XCTAssertEqual(
                error as? RuntimeMemoryStoreError,
                .generatedMemorySummaryDraftPersistenceConflict
            )
        }
        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 1)
    }

    func testGeneratedDraftCacheUsesPhysicalAppendOrderWhenClockMovesBackward() throws {
        let fileURL = try temporaryStoreURL()
        let store = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let first = generatedDraft(
            content: "First generated value",
            generatedAt: 300,
            persistenceOperationID: "00000000-0000-4000-8000-000000000041"
        )
        let second = generatedDraft(
            content: "Second generated value",
            generatedAt: 301,
            persistenceOperationID: "00000000-0000-4000-8000-000000000042"
        )
        let appendedAfterClockRollback = generatedDraft(
            content: "Current value after clock rollback",
            generatedAt: 299,
            persistenceOperationID: "00000000-0000-4000-8000-000000000043"
        )

        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: first)
        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: second)
        try store.cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: appendedAfterClockRollback
        )

        XCTAssertEqual(try nonEmptyJSONLLines(at: fileURL).count, 3)
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDraft(
                    ownerDeviceID: "device-a",
                    draftID: appendedAfterClockRollback.draftID
                ),
            appendedAfterClockRollback
        )
    }

    func testGeneratedDraftConditionalCacheRechecksInsideFileLock() throws {
        let fileURL = try temporaryStoreURL()
        let store = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let commitGate = GeneratedDraftCommitGate()

        let result = try store.cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: generatedDraft(content: "Revoked before file commit", generatedAt: 240),
            if: { commitGate.allowNextCheck() }
        )

        XCTAssertNil(result)
        XCTAssertEqual(commitGate.checkCount, 2)
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))
    }

    func testGeneratedDraftCachePersistsBindingWithoutPromptBody() throws {
        let fileURL = try temporaryStoreURL()
        let draft = generatedDraft(content: "Bound summary", generatedAt: 250)

        try JSONLRuntimeMemoryStore(fileURL: fileURL).cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: draft
        )

        let persisted = try String(contentsOf: fileURL, encoding: .utf8)
        XCTAssertTrue(persisted.contains(#""prompt_skill_id":"memory_summary_draft_v1""#))
        XCTAssertTrue(persisted.contains(RuntimePromptSkillRegistry.memorySummaryDraftRevision))
        XCTAssertFalse(persisted.contains(RuntimePromptSkillRegistry.memorySummaryDraftPrompt))
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDraft(ownerDeviceID: "device-a", draftID: draft.draftID),
            draft
        )
    }

    func testGeneratedDraftCachePersistsExactProviderQualifiedModelIdentity() throws {
        let fileURL = try temporaryStoreURL()
        let draft = generatedDraft(
            content: "Provider-bound summary",
            generatedAt: 275,
            providerQualifiedModelID: "ollama:provider-model-exact"
        )

        try JSONLRuntimeMemoryStore(fileURL: fileURL).cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: draft
        )

        let persisted = try String(contentsOf: fileURL, encoding: .utf8)
        XCTAssertTrue(
            persisted.contains(#""provider_qualified_model_id":"ollama:provider-model-exact""#)
        )
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDraft(ownerDeviceID: "device-a", draftID: draft.draftID),
            draft
        )
    }

    func testGeneratedDraftCacheRejectsAmbiguousProviderQualifiedModelIdentity() throws {
        for providerQualifiedModelID in [
            "",
            " ollama:provider-model",
            "ollama:ollama:provider-model",
            "aggregate:provider-model",
        ] {
            let store = JSONLRuntimeMemoryStore(fileURL: try temporaryStoreURL())
            XCTAssertThrowsError(try store.cacheGeneratedMemorySummaryDraft(
                ownerDeviceID: "device-a",
                draft: generatedDraft(
                    content: "Ambiguous provider identity",
                    generatedAt: 280,
                    providerQualifiedModelID: providerQualifiedModelID
                )
            ))
        }
    }

    func testGeneratedDraftCacheMapsCompleteLegacyEventToOriginalPromptBinding() throws {
        let fileURL = try temporaryStoreURL()
        let legacyLine = #"{"content":"Legacy summary","generated_at":"1970-01-01T00:05:00Z","id":"legacy-draft","kind":"generated_memory_summary_draft","model_id":"ollama:legacy","owner_device_id":"device-a","session_id":"legacy-session","source_message_count":2,"summary_method":"llm_summary_v1","timestamp":"1970-01-01T00:05:00Z"}"#
        try Data((legacyLine + "\n").utf8).write(to: fileURL)

        let draft = try XCTUnwrap(
            JSONLRuntimeMemoryStore(fileURL: fileURL).generatedMemorySummaryDraft(
                ownerDeviceID: "device-a",
                draftID: "legacy-draft"
            )
        )
        XCTAssertEqual(
            draft.promptSkillBinding,
            RuntimePromptSkillRegistry.originalMemorySummaryDraftBinding
        )
        XCTAssertEqual(
            draft.promptSkillBinding.revision,
            "34e4783c082748b6d5cd8d31e62a1082479c8f4378caa861da03ae97857064ca"
        )
        XCTAssertEqual(draft.modelID, "ollama:legacy")
        XCTAssertNil(draft.providerQualifiedModelID)
    }

    func testGeneratedDraftCacheRejectsPartialMalformedOrWrongPromptBinding() throws {
        let currentRevision = RuntimePromptSkillRegistry.memorySummaryDraftRevision
        let promptFieldFragments = [
            ",\"prompt_skill_id\":\"memory_summary_draft_v1\"",
            ",\"prompt_skill_revision\":\"\(currentRevision)\"",
            ",\"prompt_skill_id\":\"research_brief_v1\",\"prompt_skill_revision\":\"\(currentRevision)\"",
            ",\"prompt_skill_id\":\"memory_summary_draft_v1\",\"prompt_skill_revision\":\"\(String(repeating: "A", count: 64))\"",
        ]

        for (index, promptFields) in promptFieldFragments.enumerated() {
            let fileURL = try temporaryStoreURL()
            let line = """
                {"content":"Invalid binding","generated_at":"1970-01-01T00:05:00Z","id":"invalid-draft-\(index)","kind":"generated_memory_summary_draft","model_id":"ollama:test","owner_device_id":"device-a","session_id":"invalid-session","source_message_count":2,"summary_method":"llm_summary_v1","timestamp":"1970-01-01T00:05:00Z"\(promptFields)}
                """
            try Data((line + "\n").utf8).write(to: fileURL)

            XCTAssertThrowsError(
                try JSONLRuntimeMemoryStore(fileURL: fileURL)
                    .generatedMemorySummaryDrafts(ownerDeviceID: "device-a")
            ) { error in
                guard case RuntimeMemoryStoreError.corruptEventLog(let line, let reason) = error else {
                    return XCTFail("Expected corrupt event error, got \(error)")
                }
                XCTAssertEqual(line, 1)
                XCTAssertEqual(reason, "generated memory summary draft is invalid")
            }
        }
    }

    func testGeneratedDraftCacheRejectsNullAndDuplicatePromptBindingBeforeLegacyMapping() throws {
        let currentRevision = RuntimePromptSkillRegistry.memorySummaryDraftRevision
        let promptFieldFragments = [
            #","prompt_skill_id":null,"prompt_skill_revision":null"#,
            #","prompt_skill_id":"memory_summary_draft_v1","prompt_skill_revision":"\#(currentRevision)","prompt_skill_id":"research_brief_v1""#,
            #","prompt_skill_id":"memory_summary_draft_v1","prompt_skill_revision":"\#(currentRevision)","\u0070rompt_skill_id":"research_brief_v1""#,
        ]

        for (index, promptFields) in promptFieldFragments.enumerated() {
            let fileURL = try temporaryStoreURL()
            let line = """
                {"content":"Invalid binding","generated_at":"1970-01-01T00:05:00Z","id":"invalid-null-or-duplicate-draft-\(index)","kind":"generated_memory_summary_draft","model_id":"ollama:test","owner_device_id":"device-a","session_id":"invalid-session","source_message_count":2,"summary_method":"llm_summary_v1","timestamp":"1970-01-01T00:05:00Z"\(promptFields)}
                """
            try Data((line + "\n").utf8).write(to: fileURL)

            XCTAssertThrowsError(
                try JSONLRuntimeMemoryStore(fileURL: fileURL)
                    .generatedMemorySummaryDrafts(ownerDeviceID: "device-a")
            ) { error in
                guard case RuntimeMemoryStoreError.corruptEventLog(let line, _) = error else {
                    return XCTFail("Expected corrupt event error, got \(error)")
                }
                XCTAssertEqual(line, 1)
            }
        }
    }

    func testGeneratedDraftCacheRejectsCorruptEventAfterReopen() throws {
        let fileURL = try temporaryStoreURL()
        let store = JSONLRuntimeMemoryStore(fileURL: fileURL)
        try store.cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: generatedDraft(content: "Valid summary", generatedAt: 300)
        )
        let corruptLine = #"{"content":"   ","generated_at":"1970-01-01T00:05:01Z","id":"generated-draft","kind":"generated_memory_summary_draft","model_id":"GPT-5.6 Sol","owner_device_id":"device-a","session_id":"generated-session","source_message_count":2,"summary_method":"llm_summary_v1","timestamp":"1970-01-01T00:05:01Z"}"#
        let handle = try FileHandle(forWritingTo: fileURL)
        try handle.seekToEnd()
        try handle.write(contentsOf: Data((corruptLine + "\n").utf8))
        try handle.close()

        XCTAssertThrowsError(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDrafts(ownerDeviceID: "device-a")
        ) { error in
            guard case RuntimeMemoryStoreError.corruptEventLog(let line, let reason) = error else {
                return XCTFail("Expected corrupt event error, got \(error)")
            }
            XCTAssertEqual(line, 2)
            XCTAssertEqual(reason, "generated memory summary draft is invalid")
        }
    }

    private func generatedDraft(
        content: String,
        generatedAt: TimeInterval,
        modelID: String = "GPT-5.6 Sol",
        providerQualifiedModelID: String? = nil,
        persistenceOperationID: String? = nil,
        promptSkillBinding: RuntimePromptSkillBinding =
            RuntimePromptSkillRegistry.memorySummaryDraftBinding
    ) -> RuntimeGeneratedMemorySummaryDraft {
        RuntimeGeneratedMemorySummaryDraft(
            draftID: "generated-draft",
            sessionID: "generated-session",
            sourceMessageCount: 2,
            content: content,
            modelID: modelID,
            providerQualifiedModelID: providerQualifiedModelID,
            persistenceOperationID: persistenceOperationID,
            promptSkillBinding: promptSkillBinding,
            generatedAt: Date(timeIntervalSince1970: generatedAt)
        )
    }

    private func temporaryStoreURL() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock {
            try? FileManager.default.removeItem(at: directory)
        }
        return directory.appendingPathComponent("runtime-memory-events.jsonl")
    }

    private func nonEmptyJSONLLines(at fileURL: URL) throws -> [Substring] {
        try String(contentsOf: fileURL, encoding: .utf8)
            .split(whereSeparator: { $0.isNewline })
            .filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }

    private static func cacheGeneratedDraft(
        in store: JSONLRuntimeMemoryStore,
        draft: RuntimeGeneratedMemorySummaryDraft,
        ready: DispatchSemaphore,
        start: DispatchSemaphore
    ) async throws -> RuntimeGeneratedMemorySummaryDraft? {
        try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                ready.signal()
                start.wait()
                do {
                    continuation.resume(returning: try store.cacheGeneratedMemorySummaryDraft(
                        ownerDeviceID: "device-a",
                        draft: draft,
                        if: { true }
                    ))
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }
}

private final class GeneratedDraftCommitGate: @unchecked Sendable {
    private let lock = NSLock()
    private var checks = 0

    var checkCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return checks
    }

    func allowNextCheck() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        checks += 1
        return checks == 1
    }
}
