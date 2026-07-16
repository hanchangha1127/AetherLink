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

        XCTAssertEqual(try store.generatedMemorySummaryDrafts(ownerDeviceID: "device-a"), [replacement])
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDraft(ownerDeviceID: "device-a", draftID: replacement.draftID),
            replacement
        )
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
}
