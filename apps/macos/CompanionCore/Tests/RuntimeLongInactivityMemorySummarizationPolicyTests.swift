@testable import CompanionCore
import OllamaBackend
import XCTest

final class RuntimeLongInactivityMemorySummarizationPolicyTests: XCTestCase {
    func testPolicySelectsOnlyLongInactiveActiveSessionsAndOrdersOldestFirst() {
        let now = Date(timeIntervalSince1970: 2_000_000)
        let day: TimeInterval = 24 * 60 * 60
        let policy = RuntimeLongInactivityMemorySummarizationPolicy(
            minimumInactiveInterval: 14 * day,
            minimumMessageCount: 6,
            maxCandidateCount: 2
        )

        let candidates = policy.candidates(from: [
            storedSession(
                id: "recent",
                lastActivityAt: now.addingTimeInterval(-13 * day),
                messageCount: 20
            ),
            storedSession(
                id: "old-short",
                lastActivityAt: now.addingTimeInterval(-30 * day),
                messageCount: 5
            ),
            storedSession(
                id: "old-archived",
                lastActivityAt: now.addingTimeInterval(-40 * day),
                messageCount: 8,
                status: "archived"
            ),
            storedSession(
                id: "old-active-newer",
                lastActivityAt: now.addingTimeInterval(-15 * day),
                messageCount: 6
            ),
            storedSession(
                id: "old-active-older",
                lastActivityAt: now.addingTimeInterval(-31 * day),
                messageCount: 10
            ),
            storedSession(
                id: "old-active-extra",
                lastActivityAt: now.addingTimeInterval(-20 * day),
                messageCount: 7
            )
        ], now: now)

        XCTAssertEqual(candidates.map(\.sessionID), ["old-active-older", "old-active-extra"])
        XCTAssertEqual(candidates.first?.messageCount, 10)
        XCTAssertEqual(candidates.first?.inactiveInterval, 31 * day)
    }

    func testSQLiteStoreListsLongInactivityCandidatesWithinOwnerAndLifecycleBoundaries() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let now = Date(timeIntervalSince1970: 4_000_000)
        let day: TimeInterval = 24 * 60 * 60
        let policy = RuntimeLongInactivityMemorySummarizationPolicy(
            minimumInactiveInterval: 14 * day,
            minimumMessageCount: 6,
            maxCandidateCount: 10
        )

        try appendAnsweredTurns(
            to: store,
            sessionID: "device-a-old-active",
            ownerDeviceID: "device-a",
            firstTurnAt: now.addingTimeInterval(-30 * day),
            turnCount: 3
        )
        try appendAnsweredTurns(
            to: store,
            sessionID: "device-a-recent-active",
            ownerDeviceID: "device-a",
            firstTurnAt: now.addingTimeInterval(-2 * day),
            turnCount: 3
        )
        try appendAnsweredTurns(
            to: store,
            sessionID: "device-a-old-short",
            ownerDeviceID: "device-a",
            firstTurnAt: now.addingTimeInterval(-30 * day),
            turnCount: 2
        )
        try appendAnsweredTurns(
            to: store,
            sessionID: "device-a-old-archived",
            ownerDeviceID: "device-a",
            firstTurnAt: now.addingTimeInterval(-30 * day),
            turnCount: 3
        )
        try appendAnsweredTurns(
            to: store,
            sessionID: "device-a-old-deleted",
            ownerDeviceID: "device-a",
            firstTurnAt: now.addingTimeInterval(-30 * day),
            turnCount: 3
        )
        try appendAnsweredTurns(
            to: store,
            sessionID: "device-b-old-active",
            ownerDeviceID: "device-b",
            firstTurnAt: now.addingTimeInterval(-30 * day),
            turnCount: 3
        )

        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-old-archived",
            requestID: "archive-device-a-old-archived",
            mutation: .archive,
            timestamp: now.addingTimeInterval(-20 * day)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-old-deleted",
            requestID: "archive-device-a-old-deleted",
            mutation: .archive,
            timestamp: now.addingTimeInterval(-20 * day)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-old-deleted",
            requestID: "delete-device-a-old-deleted",
            mutation: .delete,
            timestamp: now.addingTimeInterval(-19 * day)
        )

        let deviceACandidates = try store.listLongInactivityMemorySummarizationCandidates(
            ownerDeviceID: "device-a",
            now: now,
            policy: policy
        )
        let deviceBCandidates = try store.listLongInactivityMemorySummarizationCandidates(
            ownerDeviceID: "device-b",
            now: now,
            policy: policy
        )

        XCTAssertEqual(deviceACandidates.map(\.sessionID), ["device-a-old-active"])
        XCTAssertEqual(deviceACandidates.first?.messageCount, 6)
        XCTAssertEqual(deviceACandidates.first?.title, "New chat")
        XCTAssertEqual(deviceBCandidates.map(\.sessionID), ["device-b-old-active"])
    }

    func testDraftUsesVisibleTranscriptContentOnlyWithSourcePointer() throws {
        let now = Date(timeIntervalSince1970: 5_000_000)
        let policy = RuntimeLongInactivityMemorySummarizationPolicy(
            minimumInactiveInterval: 14 * 24 * 60 * 60,
            minimumMessageCount: 1,
            maxCandidateCount: 10,
            maxSourceMessageCount: 2,
            maxDraftPreviewCharacters: 160
        )
        let candidate = try XCTUnwrap(policy.candidate(
            for: storedSession(
                id: "draft-session",
                lastActivityAt: now.addingTimeInterval(-30 * 24 * 60 * 60),
                messageCount: 3
            ),
            now: now
        ))

        let draft = try XCTUnwrap(policy.draft(
            for: candidate,
            messages: [
                RuntimeChatStoredMessage(
                    role: "system",
                    content: "Runtime user memory:\nDo not leak this runtime context.",
                    createdAt: Date(timeIntervalSince1970: 10)
                ),
                RuntimeChatStoredMessage(
                    role: "user",
                    content: "  First visible question.  ",
                    createdAt: Date(timeIntervalSince1970: 11)
                ),
                RuntimeChatStoredMessage(
                    role: "assistant",
                    content: "Visible answer.",
                    reasoning: "private reasoning only",
                    createdAt: Date(timeIntervalSince1970: 12)
                ),
                RuntimeChatStoredMessage(
                    role: "assistant",
                    content: "",
                    reasoning: "reasoning without visible answer",
                    createdAt: Date(timeIntervalSince1970: 13)
                ),
                RuntimeChatStoredMessage(
                    role: "system",
                    content: "Runtime conversation summary:\nOlder backend-only compaction context.",
                    createdAt: Date(timeIntervalSince1970: 14)
                ),
                RuntimeChatStoredMessage(
                    role: "user",
                    content: "Follow up with whitespace\n\nnormalized.",
                    createdAt: Date(timeIntervalSince1970: 15)
                )
            ]
        ))

        XCTAssertEqual(draft.id, "long-inactivity:draft-session:2408000000:3")
        XCTAssertEqual(draft.candidate.sessionID, "draft-session")
        XCTAssertEqual(draft.sourceMessageCount, 2)
        XCTAssertEqual(draft.sourceRangeDescription, "visible messages 2-3 of 3")
        XCTAssertEqual(draft.sourcePointers.map(\.messageIndex), [2, 3])
        XCTAssertEqual(draft.sourcePointers.map(\.role), ["assistant", "user"])
        XCTAssertEqual(draft.sourcePointers.map(\.createdAt), [
            Date(timeIntervalSince1970: 12),
            Date(timeIntervalSince1970: 15)
        ])
        XCTAssertEqual(draft.sourcePointers.first?.excerpt, "Visible answer.")
        XCTAssertTrue(draft.summaryPreview.contains("Assistant: Visible answer."))
        XCTAssertTrue(draft.summaryPreview.contains("User: Follow up with whitespace normalized."))
        XCTAssertFalse(draft.summaryPreview.contains("Runtime user memory"))
        XCTAssertFalse(draft.summaryPreview.contains("Runtime conversation summary"))
        XCTAssertFalse(draft.summaryPreview.contains("private reasoning only"))
        XCTAssertFalse(draft.summaryPreview.contains("reasoning without visible answer"))
    }

    func testSQLiteStoreListsLongInactivityDraftsWithoutCrossOwnerOrArchivedSources() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let now = Date(timeIntervalSince1970: 6_000_000)
        let day: TimeInterval = 24 * 60 * 60
        let policy = RuntimeLongInactivityMemorySummarizationPolicy(
            minimumInactiveInterval: 14 * day,
            minimumMessageCount: 2,
            maxCandidateCount: 10,
            maxSourceMessageCount: 3,
            maxDraftPreviewCharacters: 180
        )

        try appendAnsweredTurns(
            to: store,
            sessionID: "device-a-old-active-draft",
            ownerDeviceID: "device-a",
            firstTurnAt: now.addingTimeInterval(-30 * day),
            turnCount: 2
        )
        try appendAnsweredTurns(
            to: store,
            sessionID: "device-a-old-archived-draft",
            ownerDeviceID: "device-a",
            firstTurnAt: now.addingTimeInterval(-30 * day),
            turnCount: 2
        )
        try appendAnsweredTurns(
            to: store,
            sessionID: "device-b-old-active-draft",
            ownerDeviceID: "device-b",
            firstTurnAt: now.addingTimeInterval(-30 * day),
            turnCount: 2
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-old-archived-draft",
            requestID: "archive-device-a-old-archived-draft",
            mutation: .archive,
            timestamp: now.addingTimeInterval(-20 * day)
        )

        let drafts = try store.listLongInactivityMemorySummarizationDrafts(
            ownerDeviceID: "device-a",
            now: now,
            policy: policy
        )
        let repeatedDrafts = try store.listLongInactivityMemorySummarizationDrafts(
            ownerDeviceID: "device-a",
            now: now,
            policy: policy
        )

        XCTAssertEqual(drafts.map(\.candidate.sessionID), ["device-a-old-active-draft"])
        XCTAssertEqual(repeatedDrafts.map(\.id), drafts.map(\.id))
        XCTAssertEqual(drafts.first?.sourceMessageCount, 3)
        XCTAssertEqual(drafts.first?.sourceRangeDescription, "visible messages 2-4 of 4")
        XCTAssertEqual(drafts.first?.sourcePointers.map(\.messageIndex), [2, 3, 4])
        XCTAssertEqual(drafts.first?.sourcePointers.map(\.role), ["assistant", "user", "assistant"])
        XCTAssertEqual(drafts.first?.sourcePointers.first?.sessionID, "device-a-old-active-draft")
        XCTAssertEqual(drafts.first?.sourcePointers.first?.excerpt, "Answer 0")
        XCTAssertTrue(drafts.first?.summaryPreview.contains("Answer 0") == true)
        XCTAssertTrue(drafts.first?.summaryPreview.contains("Question 1") == true)
        XCTAssertTrue(drafts.first?.summaryPreview.contains("Answer 1") == true)
        XCTAssertFalse(drafts.first?.summaryPreview.contains("device-b") == true)
        XCTAssertFalse(drafts.first?.summaryPreview.contains("archived") == true)
    }

    private func storedSession(
        id: String,
        lastActivityAt: Date,
        messageCount: Int,
        status: String = "active"
    ) -> RuntimeChatStoredSession {
        RuntimeChatStoredSession(
            sessionID: id,
            title: id,
            model: "ollama:llama3.1:8b",
            lastActivityAt: lastActivityAt,
            messageCount: messageCount,
            status: status,
            archivedAt: status == "archived" ? lastActivityAt : nil
        )
    }

    private func appendAnsweredTurns(
        to store: SQLiteRuntimeChatEventStore,
        sessionID: String,
        ownerDeviceID: String,
        firstTurnAt: Date,
        turnCount: Int
    ) throws {
        for index in 0..<turnCount {
            let timestamp = firstTurnAt.addingTimeInterval(TimeInterval(index * 60))
            let requestID = "\(sessionID)-turn-\(index)"
            try store.append(RuntimeChatStoredEvent(
                id: "\(requestID)-request",
                timestamp: timestamp,
                kind: .request,
                requestID: requestID,
                sessionID: sessionID,
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Question \(index)")],
                ownerDeviceID: ownerDeviceID
            ))
            try store.append(RuntimeChatStoredEvent(
                id: "\(requestID)-assistant",
                timestamp: timestamp.addingTimeInterval(1),
                kind: .assistantDelta,
                requestID: requestID,
                sessionID: sessionID,
                model: "ollama:llama3.1:8b",
                delta: "Answer \(index)",
                ownerDeviceID: ownerDeviceID
            ))
            try store.append(RuntimeChatStoredEvent(
                id: "\(requestID)-done",
                timestamp: timestamp.addingTimeInterval(2),
                kind: .done,
                requestID: requestID,
                sessionID: sessionID,
                model: "ollama:llama3.1:8b",
                finishReason: "stop",
                ownerDeviceID: ownerDeviceID
            ))
        }
    }

    private func temporaryDatabaseURL() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock {
            try? FileManager.default.removeItem(at: directory)
        }
        return directory.appendingPathComponent("runtime-chat-events.sqlite")
    }
}
