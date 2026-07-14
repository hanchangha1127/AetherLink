@testable import CompanionCore
import Foundation
import XCTest

final class RuntimeMemoryExactDuplicateSuggestionsTests: XCTestCase {
    func testZeroAndOneEntryProduceNoGroups() throws {
        XCTAssertEqual(
            try RuntimeMemoryExactDuplicateSuggester.suggestions(from: []),
            RuntimeMemoryDuplicateSuggestions(groups: [], scannedCount: 0, truncated: false)
        )

        let result = try RuntimeMemoryExactDuplicateSuggester.suggestions(from: [
            entry(id: "only", content: "stored content", updatedAt: 1)
        ])

        XCTAssertEqual(result.groups, [])
        XCTAssertEqual(result.scannedCount, 1)
        XCTAssertFalse(result.truncated)
    }

    func testGroupsOnlyByteExactContentWithDeterministicUniqueIDs() throws {
        let source = RuntimeMemoryEntrySource(
            kind: "test-source",
            draftID: "draft-1",
            summaryMethod: "test",
            session: RuntimeMemoryEntrySourceSession(
                sessionID: "session-1",
                title: "Title",
                model: "model-1",
                lastActivityAt: Date(timeIntervalSince1970: 1),
                messageCount: 1,
                inactiveSeconds: 1
            ),
            sourceMessageCount: 1,
            sourceRange: "1",
            sourcePointers: [RuntimeMemoryEntrySourcePointer(
                sessionID: "session-1",
                messageIndex: 0,
                role: "user",
                createdAt: nil,
                excerpt: "source excerpt"
            )]
        )
        let entries = [
            entry(id: "z2", content: "Beta", enabled: false, updatedAt: 2),
            entry(id: "a2", content: "Alpha", updatedAt: 4),
            entry(id: "case", content: "alpha", updatedAt: 8),
            entry(id: "inner-space", content: "Al pha", updatedAt: 7),
            entry(id: "composed", content: "Caf\u{00E9}", updatedAt: 6),
            entry(id: "decomposed", content: "Cafe\u{0301}", updatedAt: 5),
            entry(id: "z1", content: "Beta", source: source, updatedAt: 3),
            entry(id: "a1", content: "Alpha", enabled: false, source: source, updatedAt: 1),
            entry(id: "a2", content: "different stale duplicate id", updatedAt: 0)
        ]

        let result = try RuntimeMemoryExactDuplicateSuggester.suggestions(from: entries)

        XCTAssertEqual(result.groups, [
            RuntimeMemoryDuplicateSuggestionGroup(entryIDs: ["a1", "a2"]),
            RuntimeMemoryDuplicateSuggestionGroup(entryIDs: ["z1", "z2"])
        ])
        XCTAssertEqual(result.scannedCount, 8)
        XCTAssertFalse(result.truncated)
        XCTAssertEqual(Set(result.groups.flatMap(\.entryIDs)).count, 4)
    }

    func testLatestTwoHundredBoundarySetsTruncatedAndExcludesOlderEntry() throws {
        var entries = (0...200).map { index in
            entry(
                id: String(format: "entry-%03d", index),
                content: "unique-\(index)",
                updatedAt: TimeInterval(index)
            )
        }
        entries[0].content = "boundary-duplicate"
        entries[1].content = "boundary-duplicate"
        entries[199].content = "included-duplicate"
        entries[200].content = "included-duplicate"

        let result = try RuntimeMemoryExactDuplicateSuggester.suggestions(from: entries.shuffled())

        XCTAssertEqual(result.scannedCount, 200)
        XCTAssertTrue(result.truncated)
        XCTAssertEqual(result.groups, [
            RuntimeMemoryDuplicateSuggestionGroup(entryIDs: ["entry-199", "entry-200"])
        ])
        XCTAssertFalse(result.groups.flatMap(\.entryIDs).contains("entry-000"))
    }

    func testCanonicalOrderingUsesUnsignedUTF8BytesAcrossUnicodePlanes() throws {
        let privateUseID = "entry-\u{E000}"
        let astralID = "entry-\u{1F600}"
        let result = try RuntimeMemoryExactDuplicateSuggester.suggestions(from: [
            entry(id: astralID, content: "same", updatedAt: 1),
            entry(id: privateUseID, content: "same", updatedAt: 1)
        ])

        XCTAssertEqual(result.groups, [
            RuntimeMemoryDuplicateSuggestionGroup(entryIDs: [privateUseID, astralID])
        ])
    }

    func testCandidateContentAndResponseIDByteCapsFailClosed() {
        let oversizedContent = String(
            repeating: "x",
            count: RuntimeMemoryExactDuplicateSuggester.maximumCandidateContentUTF8ByteCount / 2 + 1
        )
        XCTAssertThrowsError(try RuntimeMemoryExactDuplicateSuggester.suggestions(from: [
            entry(id: "content-a", content: oversizedContent, updatedAt: 2),
            entry(id: "content-b", content: oversizedContent, updatedAt: 1)
        ])) { error in
            XCTAssertEqual(
                error as? RuntimeMemoryStoreError,
                .duplicateSuggestionResourceLimitExceeded
            )
        }

        let oversizedIDPart = String(
            repeating: "i",
            count: RuntimeMemoryExactDuplicateSuggester.maximumResponseEntryIDUTF8ByteCount / 2 + 1
        )
        XCTAssertThrowsError(try RuntimeMemoryExactDuplicateSuggester.suggestions(from: [
            entry(id: "a-\(oversizedIDPart)", content: "same", updatedAt: 2),
            entry(id: "b-\(oversizedIDPart)", content: "same", updatedAt: 1)
        ])) { error in
            XCTAssertEqual(
                error as? RuntimeMemoryStoreError,
                .duplicateSuggestionResourceLimitExceeded
            )
        }
    }

    func testJSONLProductionScanRejectsOversizedSourceBeforeDecode() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let fileURL = directory.appendingPathComponent("memory.jsonl")
        try Data(
            repeating: 0x20,
            count: RuntimeMemoryExactDuplicateSuggester.maximumSourceEventLogByteCount + 1
        ).write(to: fileURL)
        let store = JSONLRuntimeMemoryStore(fileURL: fileURL)

        XCTAssertThrowsError(try store.exactDuplicateSuggestions(ownerDeviceID: "owner")) { error in
            XCTAssertEqual(
                error as? RuntimeMemoryStoreError,
                .duplicateSuggestionResourceLimitExceeded
            )
        }
    }

    private func entry(
        id: String,
        content: String,
        enabled: Bool = true,
        source: RuntimeMemoryEntrySource? = nil,
        updatedAt: TimeInterval
    ) -> RuntimeMemoryEntry {
        RuntimeMemoryEntry(
            id: id,
            content: content,
            enabled: enabled,
            createdAt: Date(timeIntervalSince1970: 0),
            updatedAt: Date(timeIntervalSince1970: updatedAt),
            source: source
        )
    }
}
