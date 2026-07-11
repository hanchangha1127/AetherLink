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
        let replacement = generatedDraft(content: "Replacement summary", generatedAt: 201)

        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: original)
        try store.cacheGeneratedMemorySummaryDraft(ownerDeviceID: "device-a", draft: replacement)

        XCTAssertEqual(try store.generatedMemorySummaryDrafts(ownerDeviceID: "device-a"), [replacement])
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: fileURL)
                .generatedMemorySummaryDraft(ownerDeviceID: "device-a", draftID: replacement.draftID),
            replacement
        )
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
        generatedAt: TimeInterval
    ) -> RuntimeGeneratedMemorySummaryDraft {
        RuntimeGeneratedMemorySummaryDraft(
            draftID: "generated-draft",
            sessionID: "generated-session",
            sourceMessageCount: 2,
            content: content,
            modelID: "GPT-5.6 Sol",
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
