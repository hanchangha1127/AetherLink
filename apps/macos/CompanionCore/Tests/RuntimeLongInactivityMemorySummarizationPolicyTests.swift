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

        XCTAssertTrue(draft.id.hasPrefix("long-inactivity:v2:"))
        XCTAssertEqual(draft.id.count, "long-inactivity:v2:".count + 64)
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

    func testDraftIDBindsSessionMetadataAndVisibleSourceButNotAdvancingInactivity() throws {
        let lastActivityAt = Date(timeIntervalSince1970: 2_408_000)
        let messages = [
            RuntimeChatStoredMessage(
                role: "user",
                content: "Remember the exact source identity.",
                createdAt: Date(timeIntervalSince1970: 2_407_900)
            ),
            RuntimeChatStoredMessage(
                role: "assistant",
                content: "The source identity remains review-bound.",
                createdAt: Date(timeIntervalSince1970: 2_407_901)
            ),
        ]
        let policy = RuntimeLongInactivityMemorySummarizationPolicy(
            minimumInactiveInterval: 0,
            minimumMessageCount: 1,
            maxSourceMessageCount: 2
        )
        let candidate = RuntimeLongInactivityMemorySummarizationCandidate(
            sessionID: "source-bound-session",
            title: "Original title",
            model: "ollama:llama3.1:8b",
            lastActivityAt: lastActivityAt,
            messageCount: 2,
            inactiveInterval: 10
        )
        func makeCandidate(
            sessionID: String = "source-bound-session",
            title: String = "Original title",
            model: String = "ollama:llama3.1:8b",
            lastActivityAt: Date = lastActivityAt,
            messageCount: Int = 2,
            inactiveInterval: TimeInterval = 10
        ) -> RuntimeLongInactivityMemorySummarizationCandidate {
            RuntimeLongInactivityMemorySummarizationCandidate(
                sessionID: sessionID,
                title: title,
                model: model,
                lastActivityAt: lastActivityAt,
                messageCount: messageCount,
                inactiveInterval: inactiveInterval
            )
        }
        let baseline = try XCTUnwrap(policy.draft(for: candidate, messages: messages))
        let laterInactivity = try XCTUnwrap(policy.draft(
            for: makeCandidate(inactiveInterval: 20),
            messages: messages
        ))
        let renamed = try XCTUnwrap(policy.draft(
            for: makeCandidate(title: "Renamed title"),
            messages: messages
        ))
        let changedModel = try XCTUnwrap(policy.draft(
            for: makeCandidate(model: "lm_studio:llama3.1:8b"),
            messages: messages
        ))
        var changedMessages = messages
        changedMessages[1] = RuntimeChatStoredMessage(
            role: "assistant",
            content: "The changed source must receive another identity.",
            createdAt: messages[1].createdAt
        )
        let changedSource = try XCTUnwrap(policy.draft(for: candidate, messages: changedMessages))

        XCTAssertEqual(baseline.id, laterInactivity.id)
        XCTAssertNotEqual(baseline.id, renamed.id)
        XCTAssertNotEqual(baseline.id, changedModel.id)
        XCTAssertNotEqual(baseline.id, changedSource.id)
        for changedCandidate in [
            makeCandidate(sessionID: "another-source-bound-session"),
            makeCandidate(lastActivityAt: lastActivityAt.addingTimeInterval(0.001)),
            makeCandidate(messageCount: 3),
        ] {
            let changedDraft = try XCTUnwrap(policy.draft(
                for: changedCandidate,
                messages: messages
            ))
            XCTAssertNotEqual(baseline.id, changedDraft.id)
        }

        var timestampChangedMessages = messages
        timestampChangedMessages[1] = RuntimeChatStoredMessage(
            role: messages[1].role,
            content: messages[1].content,
            createdAt: messages[1].createdAt?.addingTimeInterval(0.001)
        )
        var nilTimestampMessages = messages
        nilTimestampMessages[1] = RuntimeChatStoredMessage(
            role: messages[1].role,
            content: messages[1].content,
            createdAt: nil
        )
        var roleChangedMessages = messages
        roleChangedMessages[0] = RuntimeChatStoredMessage(
            role: "assistant",
            content: messages[0].content,
            createdAt: messages[0].createdAt
        )
        let leadingSourceMessages = [
            RuntimeChatStoredMessage(
                role: "user",
                content: "An older source shifts the selected pointer range.",
                createdAt: Date(timeIntervalSince1970: 2_407_899)
            ),
        ] + messages
        let sourceVariants = [
            timestampChangedMessages,
            nilTimestampMessages,
            roleChangedMessages,
            Array(messages.reversed()),
            leadingSourceMessages,
        ]
        for sourceVariant in sourceVariants {
            let changedDraft = try XCTUnwrap(policy.draft(
                for: candidate,
                messages: sourceVariant
            ))
            XCTAssertNotEqual(baseline.id, changedDraft.id)
        }
        let onePointerDraft = try XCTUnwrap(
            RuntimeLongInactivityMemorySummarizationPolicy(
                minimumInactiveInterval: 0,
                minimumMessageCount: 1,
                maxSourceMessageCount: 1
            ).draft(for: candidate, messages: messages)
        )
        XCTAssertNotEqual(baseline.id, onePointerDraft.id)

        let sharedExcerptPrefix = String(repeating: "x", count: 180)
        let previewOnlyMessagesA = [RuntimeChatStoredMessage(
            role: "user",
            content: sharedExcerptPrefix + "A",
            createdAt: Date(timeIntervalSince1970: 2_407_902)
        )]
        let previewOnlyMessagesB = [RuntimeChatStoredMessage(
            role: "user",
            content: sharedExcerptPrefix + "B",
            createdAt: Date(timeIntervalSince1970: 2_407_902)
        )]
        let previewOnlyCandidate = makeCandidate(messageCount: 1)
        let previewOnlyDraftA = try XCTUnwrap(policy.draft(
            for: previewOnlyCandidate,
            messages: previewOnlyMessagesA
        ))
        let previewOnlyDraftB = try XCTUnwrap(policy.draft(
            for: previewOnlyCandidate,
            messages: previewOnlyMessagesB
        ))
        XCTAssertEqual(previewOnlyDraftA.sourcePointers, previewOnlyDraftB.sourcePointers)
        XCTAssertNotEqual(previewOnlyDraftA.summaryPreview, previewOnlyDraftB.summaryPreview)
        XCTAssertNotEqual(previewOnlyDraftA.id, previewOnlyDraftB.id)
        XCTAssertEqual(
            baseline.id,
            "long-inactivity:v2:8b7948073088d0a11a411caee1677acca19aa20443f79462eb1663d5a095abc1"
        )
    }

    func testGeneratedOverlayPreservesCandidateAndSourceMetadata() throws {
        let generatedAt = Date(timeIntervalSince1970: 5_100_000)
        let candidate = RuntimeLongInactivityMemorySummarizationCandidate(
            sessionID: "generated-session",
            title: "Generated session",
            model: "ollama:llama3.1:8b",
            lastActivityAt: Date(timeIntervalSince1970: 4_000_000),
            messageCount: 8,
            inactiveInterval: 1_100_000
        )
        let pointers = [RuntimeLongInactivityMemorySummarizationSourcePointer(
            sessionID: candidate.sessionID,
            messageIndex: 7,
            role: "assistant",
            createdAt: Date(timeIntervalSince1970: 4_000_100),
            excerpt: "Original source excerpt"
        )]
        let draft = RuntimeLongInactivityMemorySummarizationDraft(
            candidate: candidate,
            id: "generated-draft",
            sourceMessageCount: 1,
            sourceRangeDescription: "visible message 7 of 7",
            sourcePointers: pointers,
            summaryPreview: "Assistant: Deterministic preview"
        )
        let generated = RuntimeGeneratedMemorySummaryDraft(
            draftID: draft.id,
            sessionID: candidate.sessionID,
            sourceMessageCount: draft.sourceMessageCount,
            content: "Generated summary content",
            modelID: "GPT-5.6 Sol",
            promptSkillBinding: RuntimePromptSkillRegistry.memorySummaryDraftBinding,
            generatedAt: generatedAt
        )

        let composed = draft.applyingGeneratedResult(generated)

        XCTAssertEqual(composed.candidate, candidate)
        XCTAssertEqual(composed.id, draft.id)
        XCTAssertEqual(composed.sourceMessageCount, draft.sourceMessageCount)
        XCTAssertEqual(composed.sourceRangeDescription, draft.sourceRangeDescription)
        XCTAssertEqual(composed.sourcePointers, pointers)
        XCTAssertEqual(composed.summaryPreview, "Generated summary content")
        XCTAssertEqual(composed.summaryMethod, "llm_summary_v1")
        XCTAssertEqual(composed.generatedAt, generatedAt)
        XCTAssertEqual(composed.generatedModelID, "GPT-5.6 Sol")
    }

    func testGeneratedOverlayIgnoresStaleSourceIdentity() {
        let candidate = RuntimeLongInactivityMemorySummarizationCandidate(
            sessionID: "current-session",
            title: "Current session",
            model: "ollama:llama3.1:8b",
            lastActivityAt: Date(timeIntervalSince1970: 4_000_000),
            messageCount: 8,
            inactiveInterval: 1_100_000
        )
        let draft = RuntimeLongInactivityMemorySummarizationDraft(
            candidate: candidate,
            id: "current-draft",
            sourceMessageCount: 2,
            sourceRangeDescription: "visible messages 7-8 of 8",
            sourcePointers: [],
            summaryPreview: "Deterministic preview"
        )
        let staleGenerated = RuntimeGeneratedMemorySummaryDraft(
            draftID: draft.id,
            sessionID: candidate.sessionID,
            sourceMessageCount: 1,
            content: "Stale generated content",
            modelID: "GPT-5.6 Sol",
            promptSkillBinding: RuntimePromptSkillRegistry.memorySummaryDraftBinding,
            generatedAt: Date(timeIntervalSince1970: 5_100_000)
        )

        XCTAssertEqual(draft.applyingGeneratedResult(staleGenerated), draft)
    }

    func testSQLiteStoreListsLongInactivityDraftsWithoutCrossOwnerOrArchivedSources() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
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
        let reopenedDrafts = try SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
            .listLongInactivityMemorySummarizationDrafts(
                ownerDeviceID: "device-a",
                now: now,
                policy: policy
            )

        XCTAssertEqual(drafts.map(\.candidate.sessionID), ["device-a-old-active-draft"])
        XCTAssertEqual(repeatedDrafts.map(\.id), drafts.map(\.id))
        XCTAssertEqual(reopenedDrafts.map(\.id), drafts.map(\.id))
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
