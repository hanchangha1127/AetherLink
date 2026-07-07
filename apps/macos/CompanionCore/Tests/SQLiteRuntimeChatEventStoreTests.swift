@testable import CompanionCore
import OllamaBackend
import XCTest

final class SQLiteRuntimeChatEventStoreTests: XCTestCase {
    func testSQLiteStoreListsMessagesAndStripsInlineAttachmentData() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let requestDate = Date(timeIntervalSince1970: 100)
        let deltaDate = Date(timeIntervalSince1970: 101)
        let doneDate = Date(timeIntervalSince1970: 102)

        try store.append(RuntimeChatStoredEvent(
            timestamp: requestDate,
            kind: .request,
            requestID: "sqlite-read",
            sessionID: "sqlite-session",
            model: "ollama:llama3.1:8b",
            messages: [
                ChatMessage(
                    role: "user",
                    content: "Explain QR pairing.",
                    attachments: [
                        ChatAttachment(
                            type: "image",
                            mimeType: "image/png",
                            name: "pairing.png",
                            dataBase64: "sensitive-inline-bytes"
                        ),
                        ChatAttachment(
                            type: "text",
                            mimeType: "text/plain",
                            name: "notes.txt",
                            text: "QR route notes"
                        )
                    ]
                )
            ]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: deltaDate,
            kind: .reasoningDelta,
            requestID: "sqlite-read",
            sessionID: "sqlite-session",
            model: "ollama:llama3.1:8b",
            reasoningDelta: "Checking route material."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: deltaDate,
            kind: .assistantDelta,
            requestID: "sqlite-read",
            sessionID: "sqlite-session",
            model: "ollama:llama3.1:8b",
            delta: "Scan the runtime QR."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: doneDate,
            kind: .done,
            requestID: "sqlite-read",
            sessionID: "sqlite-session",
            model: "ollama:llama3.1:8b",
            finishReason: "stop",
            usage: RuntimeChatStoredUsage(inputTokens: 3, outputTokens: 4)
        ))

        let reopenedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let sessions = try reopenedStore.listSessions(limit: 10)
        let messages = try reopenedStore.listMessages(sessionID: "sqlite-session", limit: 10)
        let reasoningSearchResults = try reopenedStore.listSessions(
            ownerDeviceID: nil,
            limit: 10,
            includeArchived: false,
            query: "Checking material"
        )

        XCTAssertEqual(sessions.count, 1)
        XCTAssertEqual(sessions.first?.sessionID, "sqlite-session")
        XCTAssertEqual(sessions.first?.title, "New chat")
        XCTAssertEqual(sessions.first?.messageCount, 2)
        XCTAssertEqual(sessions.first?.lastActivityAt, doneDate)
        XCTAssertEqual(sessions.first?.lastEvent, "done")
        XCTAssertEqual(sessions.first?.lastFinishReason, "stop")
        XCTAssertNil(sessions.first?.lastErrorCode)
        XCTAssertEqual(messages.map(\.role), ["user", "assistant"])
        XCTAssertEqual(messages.first?.attachments.first?.dataBase64, nil)
        XCTAssertEqual(messages.first?.attachments.last?.text, "QR route notes")
        XCTAssertEqual(messages.last?.content, "Scan the runtime QR.")
        XCTAssertEqual(messages.last?.reasoning, "Checking route material.")
        XCTAssertEqual(reasoningSearchResults.map(\.sessionID), ["sqlite-session"])
        XCTAssertEqual(reasoningSearchResults.first?.search?.matchedFields, ["reasoning"])
        XCTAssertEqual(reasoningSearchResults.first?.search?.snippet, "Checking route material.")
        XCTAssertTrue(try reopenedStore.listSessions(limit: 0).isEmpty)
        XCTAssertTrue(try reopenedStore.listMessages(sessionID: "sqlite-session", limit: 0).isEmpty)
    }

    func testSQLiteStoreScopesLifecycleAndMutationsByOwnerDevice() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 200),
            kind: .request,
            requestID: "legacy-turn",
            sessionID: "legacy-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Legacy unscoped chat.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 201),
            kind: .request,
            requestID: "device-a-turn",
            sessionID: "device-a-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Device A chat.")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 202),
            kind: .assistantDelta,
            requestID: "device-a-turn",
            sessionID: "device-a-session",
            model: "ollama:llama3.1:8b",
            delta: "Device A answer.",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 203),
            kind: .request,
            requestID: "device-b-turn",
            sessionID: "device-b-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Device B chat.")],
            ownerDeviceID: "device-b"
        ))

        XCTAssertEqual(try store.listSessions(limit: 10).map(\.sessionID), ["legacy-session"])
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).map(\.sessionID),
            ["device-a-session"]
        )
        XCTAssertTrue(
            try store.listMessages(ownerDeviceID: "device-b", sessionID: "device-a-session", limit: 10).isEmpty
        )
        XCTAssertThrowsError(try store.mutateSession(
            ownerDeviceID: "device-b",
            sessionID: "device-a-session",
            requestID: "device-b-archive-a",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 204)
        )) { error in
            XCTAssertEqual(error as? RuntimeChatEventStoreError, .sessionNotFound("device-a-session"))
        }
        XCTAssertThrowsError(try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-session",
            requestID: "delete-active-a",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 205)
        )) { error in
            XCTAssertEqual(error as? RuntimeChatEventStoreError, .sessionMustBeArchivedBeforeDelete("device-a-session"))
        }

        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-session",
            requestID: "archive-a",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 206)
        )
        XCTAssertTrue(try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false).isEmpty)
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).map(\.status),
            ["archived"]
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-session",
            requestID: "delete-a",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 207)
        )
        XCTAssertTrue(try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).isEmpty)
        XCTAssertTrue(try store.listMessages(ownerDeviceID: "device-a", sessionID: "device-a-session", limit: 10).isEmpty)
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-b", limit: 10, includeArchived: true).map(\.sessionID),
            ["device-b-session"]
        )
    }

    func testSQLiteStorePreservesAppendOrderForSameTimestampTitles() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let timestamp = Date(timeIntervalSince1970: 250)

        try store.append(RuntimeChatStoredEvent(
            id: "same-second-request",
            timestamp: timestamp,
            kind: .request,
            requestID: "same-second-turn",
            sessionID: "same-second-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Name this chat.")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "same-second-generated-title",
            timestamp: timestamp,
            kind: .title,
            requestID: "same-second-generated-title",
            sessionID: "same-second-session",
            model: "ollama:llama3.1:8b",
            title: "Generated title",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "same-second-manual-title",
            timestamp: timestamp,
            kind: .title,
            requestID: "same-second-manual-title",
            sessionID: "same-second-session",
            model: "ollama:llama3.1:8b",
            title: "Manual title",
            ownerDeviceID: "device-a"
        ))

        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).first?.title,
            "Manual title"
        )
    }

    func testSQLiteStoreUsesFTSSearchWithRankSnippetsAndRuntimeContextExclusion() throws {
        let concreteStore = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let store: any RuntimeChatEventStore = concreteStore

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 300),
            kind: .request,
            requestID: "device-a-relay-turn",
            sessionID: "device-a-relay",
            model: "ollama:llama3.1:8b",
            messages: [
                ChatMessage(
                    role: "system",
                    content: "Runtime user memory:\nHidden latest QR route system context."
                ),
                ChatMessage(
                    role: "user",
                    content: "How can I repair pairing?",
                    attachments: [ChatAttachment(type: "text", mimeType: "text/plain", name: "lease.txt", text: "Lease renewal checklist")]
                )
            ],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 301),
            kind: .assistantDelta,
            requestID: "device-a-relay-turn",
            sessionID: "device-a-relay",
            model: "ollama:llama3.1:8b",
            delta: "Scan the latest QR route before retrying relay.",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 302),
            kind: .done,
            requestID: "device-a-relay-turn",
            sessionID: "device-a-relay",
            model: "ollama:llama3.1:8b",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 303),
            kind: .title,
            requestID: "device-a-relay-title",
            sessionID: "device-a-relay",
            model: "ollama:llama3.1:8b",
            title: "Relay Repair Notes",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 304),
            kind: .request,
            requestID: "device-a-model-turn",
            sessionID: "device-a-model",
            model: "lmstudio:qwen3:8b",
            messages: [ChatMessage(role: "user", content: "Compare local model choices.")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 305),
            kind: .done,
            requestID: "device-a-model-turn",
            sessionID: "device-a-model",
            model: "lmstudio:qwen3:8b",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 306),
            kind: .request,
            requestID: "device-a-archived-turn",
            sessionID: "device-a-archived",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Archived overlay diagnostics.")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 307),
            kind: .assistantDelta,
            requestID: "device-a-archived-turn",
            sessionID: "device-a-archived",
            model: "ollama:llama3.1:8b",
            delta: "Archived relay route note.",
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-archived",
            requestID: "device-a-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 308)
        )
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 309),
            kind: .request,
            requestID: "device-a-deleted-turn",
            sessionID: "device-a-deleted",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Deleted secret route.")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-deleted",
            requestID: "device-a-deleted-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 310)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-deleted",
            requestID: "device-a-delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 311)
        )
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 312),
            kind: .request,
            requestID: "device-b-relay-turn",
            sessionID: "device-b-relay",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Relay private text.")],
            ownerDeviceID: "device-b"
        ))

        let latestQRResults = try store.listSessions(
            ownerDeviceID: "device-a",
            limit: 10,
            includeArchived: false,
            query: "latest QR"
        )
        XCTAssertEqual(latestQRResults.map(\.sessionID), ["device-a-relay"])
        XCTAssertEqual(latestQRResults.first?.search?.rank, 1)
        XCTAssertEqual(latestQRResults.first?.search?.matchedFields, ["transcript"])
        XCTAssertTrue(latestQRResults.first?.search?.snippet.contains("latest QR route") ?? false)
        XCTAssertFalse(latestQRResults.first?.search?.snippet.contains("Runtime user memory") ?? true)
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false, query: "hidden latest").isEmpty
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false, query: "qwen3").map(\.sessionID),
            ["device-a-model"]
        )
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false, query: "archived relay").isEmpty
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true, query: "archived relay").map(\.sessionID),
            ["device-a-archived"]
        )
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true, query: "deleted secret").isEmpty
        )
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true, query: "private text").isEmpty
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-b", limit: 10, includeArchived: true, query: "private text").map(\.sessionID),
            ["device-b-relay"]
        )
        let rankedRelayResults = try store.listSessions(
            ownerDeviceID: "device-a",
            limit: 10,
            includeArchived: true,
            query: "relay"
        )
        XCTAssertEqual(rankedRelayResults.map(\.sessionID), ["device-a-relay", "device-a-archived"])
        XCTAssertEqual(rankedRelayResults.compactMap { $0.search?.rank }, [1, 2])
    }

    func testSQLiteStoreCreatesDatabaseWithOwnerOnlyPermissions() throws {
        let databaseURL = try temporaryDatabaseURL()
        let directoryURL = databaseURL.deletingLastPathComponent()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 370),
            kind: .request,
            requestID: "sqlite-permissions",
            sessionID: "sqlite-permissions-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Create protected SQLite history.")]
        ))

        XCTAssertEqual(try posixPermissions(at: databaseURL), 0o600)
        XCTAssertEqual(try posixPermissions(at: directoryURL), 0o700)
    }

    func testSQLiteStoreCorrectsBroadDatabasePermissionsOnOpen() throws {
        let databaseURL = try temporaryDatabaseURL()
        let directoryURL = databaseURL.deletingLastPathComponent()
        try FileManager.default.setAttributes([.posixPermissions: 0o777], ofItemAtPath: directoryURL.path)
        _ = FileManager.default.createFile(
            atPath: databaseURL.path,
            contents: Data(),
            attributes: [.posixPermissions: 0o666]
        )

        XCTAssertEqual(try posixPermissions(at: databaseURL), 0o666)
        XCTAssertEqual(try posixPermissions(at: directoryURL), 0o777)

        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)

        XCTAssertTrue(try store.listSessions(limit: 10).isEmpty)
        XCTAssertEqual(try posixPermissions(at: databaseURL), 0o600)
        XCTAssertEqual(try posixPermissions(at: directoryURL), 0o700)
    }

    func testSQLiteRetentionPrunesDeletedSessionsByOwnerScopeAndCutoff() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let cutoff = Date(timeIntervalSince1970: 1_000)

        try store.append(RuntimeChatStoredEvent(
            id: "retention-active-request",
            timestamp: Date(timeIntervalSince1970: 700),
            kind: .request,
            requestID: "retention-active-turn",
            sessionID: "retention-active",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "active keeper transcript")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "retention-archived-request",
            timestamp: Date(timeIntervalSince1970: 710),
            kind: .request,
            requestID: "retention-archived-turn",
            sessionID: "retention-archived",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "archived keeper transcript")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "retention-archived",
            requestID: "retention-archived-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 720)
        )
        try store.append(RuntimeChatStoredEvent(
            id: "retention-device-a-shared-request",
            timestamp: Date(timeIntervalSince1970: 730),
            kind: .request,
            requestID: "retention-device-a-shared-turn",
            sessionID: "retention-shared",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "device a old deleted transcript")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "retention-shared",
            requestID: "retention-device-a-shared-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 740)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "retention-shared",
            requestID: "retention-device-a-shared-delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 750)
        )
        try store.append(RuntimeChatStoredEvent(
            id: "retention-device-b-shared-request",
            timestamp: Date(timeIntervalSince1970: 760),
            kind: .request,
            requestID: "retention-device-b-shared-turn",
            sessionID: "retention-shared",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "device b shared keeper")],
            ownerDeviceID: "device-b"
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "retention-recent-request",
            timestamp: Date(timeIntervalSince1970: 1_100),
            kind: .request,
            requestID: "retention-recent-turn",
            sessionID: "retention-recent-deleted",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "recent deleted transcript")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "retention-recent-deleted",
            requestID: "retention-recent-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 1_110)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "retention-recent-deleted",
            requestID: "retention-recent-delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 1_120)
        )

        let result = try store.pruneDeletedSessions(
            ownerDeviceID: "device-a",
            deletedBefore: cutoff
        )

        XCTAssertEqual(result.prunedSessionIDs, ["retention-shared"])
        XCTAssertEqual(result.prunedSessionCount, 1)
        XCTAssertEqual(result.prunedEventCount, 3)
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).map(\.sessionID),
            ["retention-archived", "retention-active"]
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-b", limit: 10, includeArchived: true).map(\.sessionID),
            ["retention-shared"]
        )
        try store.append(RuntimeChatStoredEvent(
            id: "retention-device-b-shared-delta",
            timestamp: Date(timeIntervalSince1970: 1_130),
            kind: .assistantDelta,
            requestID: "retention-device-b-shared-turn",
            sessionID: "retention-shared",
            model: "ollama:llama3.1:8b",
            delta: "device b answer after device a prune",
            ownerDeviceID: "device-b"
        ))
        XCTAssertEqual(
            try store.listMessages(ownerDeviceID: "device-b", sessionID: "retention-shared", limit: 10).map(\.content),
            ["device b shared keeper", "device b answer after device a prune"]
        )
        XCTAssertEqual(
            try store.listSessions(
                ownerDeviceID: "device-a",
                limit: 10,
                includeArchived: true,
                query: "archived keeper"
            ).map(\.sessionID),
            ["retention-archived"]
        )
        XCTAssertThrowsError(try store.append(RuntimeChatStoredEvent(
            id: "retention-device-a-shared-after-prune",
            timestamp: Date(timeIntervalSince1970: 1_140),
            kind: .request,
            requestID: "retention-device-a-shared-after-prune",
            sessionID: "retention-shared",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "should not resurrect")],
            ownerDeviceID: "device-a"
        ))) { error in
            XCTAssertTrue(error.localizedDescription.contains("pruned by retention"))
        }
        let idempotentResult = try store.pruneDeletedSessions(ownerDeviceID: "device-a", deletedBefore: cutoff)
        XCTAssertEqual(idempotentResult.prunedSessionIDs, [])
        XCTAssertEqual(idempotentResult.prunedEventCount, 0)

        let laterResult = try store.pruneDeletedSessions(
            ownerDeviceID: "device-a",
            deletedBefore: Date(timeIntervalSince1970: 1_200)
        )
        XCTAssertEqual(laterResult.prunedSessionIDs, ["retention-recent-deleted"])
        XCTAssertEqual(laterResult.prunedEventCount, 3)
    }

    func testSQLiteRetentionTombstonePreventsLegacyBackfillResurrection() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        let legacyStore = JSONLRuntimeChatEventStore(fileURL: legacyURL)

        try legacyStore.append(RuntimeChatStoredEvent(
            id: "legacy-retention-request",
            timestamp: Date(timeIntervalSince1970: 800),
            kind: .request,
            requestID: "legacy-retention-turn",
            sessionID: "legacy-retention-deleted",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "legacy deleted transcript")],
            ownerDeviceID: "device-a"
        ))
        _ = try legacyStore.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "legacy-retention-deleted",
            requestID: "legacy-retention-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 810)
        )
        _ = try legacyStore.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "legacy-retention-deleted",
            requestID: "legacy-retention-delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 820)
        )
        try legacyStore.append(RuntimeChatStoredEvent(
            id: "legacy-retention-kept-request",
            timestamp: Date(timeIntervalSince1970: 830),
            kind: .request,
            requestID: "legacy-retention-kept-turn",
            sessionID: "legacy-retention-kept",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "legacy kept transcript")],
            ownerDeviceID: "device-a"
        ))

        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).map(\.sessionID),
            ["legacy-retention-kept"]
        )
        let pruneResult = try store.pruneDeletedSessions(
            ownerDeviceID: "device-a",
            deletedBefore: Date(timeIntervalSince1970: 900)
        )
        XCTAssertEqual(pruneResult.prunedSessionIDs, ["legacy-retention-deleted"])
        XCTAssertEqual(pruneResult.prunedEventCount, 3)

        try legacyStore.append(RuntimeChatStoredEvent(
            id: "legacy-retention-kept-delta",
            timestamp: Date(timeIntervalSince1970: 840),
            kind: .assistantDelta,
            requestID: "legacy-retention-kept-turn",
            sessionID: "legacy-retention-kept",
            model: "ollama:llama3.1:8b",
            delta: "legacy kept follow-up",
            ownerDeviceID: "device-a"
        ))

        let reopenedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)
        XCTAssertTrue(
            try reopenedStore.listMessages(ownerDeviceID: "device-a", sessionID: "legacy-retention-deleted", limit: 10).isEmpty
        )
        XCTAssertEqual(
            try reopenedStore.listMessages(ownerDeviceID: "device-a", sessionID: "legacy-retention-kept", limit: 10).map(\.content),
            ["legacy kept transcript", "legacy kept follow-up"]
        )
        let secondPruneResult = try reopenedStore.pruneDeletedSessions(
            ownerDeviceID: "device-a",
            deletedBefore: Date(timeIntervalSince1970: 900)
        )
        XCTAssertEqual(secondPruneResult.prunedSessionIDs, [])
        XCTAssertEqual(secondPruneResult.prunedEventCount, 0)
    }

    func testProductionRuntimeChatEventStoreDefaultUsesSQLiteWithLegacyBackfill() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        try JSONLRuntimeChatEventStore(fileURL: legacyURL).append(RuntimeChatStoredEvent(
            id: "production-default-legacy-request",
            timestamp: Date(timeIntervalSince1970: 390),
            kind: .request,
            requestID: "production-default-turn",
            sessionID: "production-default-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Production default should import this.")],
            ownerDeviceID: "device-a"
        ))

        let store = RuntimeChatEventStoreDefaults.productionStore(
            sqliteDatabaseURL: databaseURL,
            legacyJSONLFileURL: legacyURL
        )

        XCTAssertTrue(store is SQLiteRuntimeChatEventStore)
        XCTAssertEqual(
            try store.listMessages(ownerDeviceID: "device-a", sessionID: "production-default-session", limit: 10).map(\.content),
            ["Production default should import this."]
        )
    }

    func testProductionRuntimeChatRetentionPolicyPrunesOnlyExpiredDeletedSessions() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = RuntimeChatEventStoreDefaults.productionStore(
            sqliteDatabaseURL: databaseURL,
            legacyJSONLFileURL: nil
        )
        let policy = RuntimeChatRetentionPolicy(
            deletedSessionRetentionInterval: 1_000,
            deletedSessionPruneLimit: 1
        )

        try store.append(RuntimeChatStoredEvent(
            id: "policy-active-request",
            timestamp: Date(timeIntervalSince1970: 200),
            kind: .request,
            requestID: "policy-active-turn",
            sessionID: "policy-active",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "active production keeper")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "policy-archived-request",
            timestamp: Date(timeIntervalSince1970: 210),
            kind: .request,
            requestID: "policy-archived-turn",
            sessionID: "policy-archived",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "archived production keeper")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "policy-archived",
            requestID: "policy-archived-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 220)
        )
        try store.append(RuntimeChatStoredEvent(
            id: "policy-old-deleted-1-request",
            timestamp: Date(timeIntervalSince1970: 300),
            kind: .request,
            requestID: "policy-old-deleted-1-turn",
            sessionID: "policy-old-deleted-1",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "old deleted one")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "policy-old-deleted-1",
            requestID: "policy-old-deleted-1-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 310)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "policy-old-deleted-1",
            requestID: "policy-old-deleted-1-delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 320)
        )
        try store.append(RuntimeChatStoredEvent(
            id: "policy-old-deleted-2-request",
            timestamp: Date(timeIntervalSince1970: 330),
            kind: .request,
            requestID: "policy-old-deleted-2-turn",
            sessionID: "policy-old-deleted-2",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "old deleted two")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "policy-old-deleted-2",
            requestID: "policy-old-deleted-2-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 340)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "policy-old-deleted-2",
            requestID: "policy-old-deleted-2-delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 350)
        )
        try store.append(RuntimeChatStoredEvent(
            id: "policy-recent-deleted-request",
            timestamp: Date(timeIntervalSince1970: 1_200),
            kind: .request,
            requestID: "policy-recent-deleted-turn",
            sessionID: "policy-recent-deleted",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "recent deleted stays until cutoff")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "policy-recent-deleted",
            requestID: "policy-recent-deleted-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 1_210)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "policy-recent-deleted",
            requestID: "policy-recent-deleted-delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 1_220)
        )
        try store.append(RuntimeChatStoredEvent(
            id: "policy-device-b-same-id-request",
            timestamp: Date(timeIntervalSince1970: 360),
            kind: .request,
            requestID: "policy-device-b-same-id-turn",
            sessionID: "policy-old-deleted-1",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "device b same session id keeper")],
            ownerDeviceID: "device-b"
        ))

        let firstResult = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            ownerDeviceID: "device-a",
            now: Date(timeIntervalSince1970: 1_500),
            policy: policy
        )

        XCTAssertEqual(firstResult.deletedSessionPruneResult.prunedSessionIDs, ["policy-old-deleted-1"])
        XCTAssertEqual(firstResult.prunedDeletedSessionCount, 1)
        XCTAssertEqual(firstResult.deletedSessionPruneResult.prunedEventCount, 3)
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).map(\.sessionID),
            ["policy-archived", "policy-active"]
        )
        XCTAssertEqual(
            try store.listMessages(ownerDeviceID: "device-a", sessionID: "policy-old-deleted-1", limit: 10).map(\.content),
            []
        )
        XCTAssertEqual(
            try store.listMessages(ownerDeviceID: "device-b", sessionID: "policy-old-deleted-1", limit: 10).map(\.content),
            ["device b same session id keeper"]
        )

        let secondResult = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            ownerDeviceID: "device-a",
            now: Date(timeIntervalSince1970: 1_500),
            policy: RuntimeChatRetentionPolicy(
                deletedSessionRetentionInterval: 1_000,
                deletedSessionPruneLimit: 10
            )
        )
        XCTAssertEqual(secondResult.deletedSessionPruneResult.prunedSessionIDs, ["policy-old-deleted-2"])
        let thirdResult = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            ownerDeviceID: "device-a",
            now: Date(timeIntervalSince1970: 3_000),
            policy: RuntimeChatRetentionPolicy(
                deletedSessionRetentionInterval: 1_000,
                deletedSessionPruneLimit: 10
            )
        )
        XCTAssertEqual(thirdResult.deletedSessionPruneResult.prunedSessionIDs, ["policy-recent-deleted"])
        XCTAssertThrowsError(try store.append(RuntimeChatStoredEvent(
            id: "policy-old-deleted-1-after-prune",
            timestamp: Date(timeIntervalSince1970: 1_600),
            kind: .request,
            requestID: "policy-old-deleted-1-after-prune",
            sessionID: "policy-old-deleted-1",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "should not resurrect")],
            ownerDeviceID: "device-a"
        ))) { error in
            XCTAssertTrue(error.localizedDescription.contains("pruned by retention"))
        }
    }

    func testSQLiteStoreBackfillsExistingJSONLIdempotently() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        let importedRequest = RuntimeChatStoredEvent(
            id: "legacy-request-event",
            timestamp: Date(timeIntervalSince1970: 400),
            kind: .request,
            requestID: "legacy-turn",
            sessionID: "legacy-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Backfill QR route.")],
            ownerDeviceID: "device-a"
        )
        try JSONLRuntimeChatEventStore(fileURL: legacyURL).append(importedRequest)
        try JSONLRuntimeChatEventStore(fileURL: legacyURL).append(RuntimeChatStoredEvent(
            id: "legacy-delta-event",
            timestamp: Date(timeIntervalSince1970: 401),
            kind: .assistantDelta,
            requestID: "legacy-turn",
            sessionID: "legacy-session",
            model: "ollama:llama3.1:8b",
            delta: "Imported answer.",
            ownerDeviceID: "device-a"
        ))

        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)
        XCTAssertEqual(
            try store.listMessages(ownerDeviceID: "device-a", sessionID: "legacy-session", limit: 10).map(\.content),
            ["Backfill QR route.", "Imported answer."]
        )

        let reopenedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)
        XCTAssertEqual(
            try reopenedStore.listMessages(ownerDeviceID: "device-a", sessionID: "legacy-session", limit: 10).map(\.content),
            ["Backfill QR route.", "Imported answer."]
        )
        try JSONLRuntimeChatEventStore(fileURL: legacyURL).append(RuntimeChatStoredEvent(
            id: "legacy-followup-event",
            timestamp: Date(timeIntervalSince1970: 402),
            kind: .assistantDelta,
            requestID: "legacy-turn",
            sessionID: "legacy-session",
            model: "ollama:llama3.1:8b",
            delta: "Imported follow-up after marker refresh.",
            ownerDeviceID: "device-a"
        ))
        let refreshedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)
        XCTAssertEqual(
            try refreshedStore.listMessages(ownerDeviceID: "device-a", sessionID: "legacy-session", limit: 10).map(\.content),
            ["Backfill QR route.", "Imported answer.Imported follow-up after marker refresh."]
        )
        XCTAssertThrowsError(try reopenedStore.append(importedRequest)) { error in
            XCTAssertTrue(error.localizedDescription.contains("Runtime chat SQLite event already exists"))
        }
    }

    func testSQLiteBackfillPreservesOwnerScopesAndLegacyNilOwner() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        let legacyStore = JSONLRuntimeChatEventStore(fileURL: legacyURL)
        try legacyStore.append(RuntimeChatStoredEvent(
            id: "legacy-nil-owner",
            timestamp: Date(timeIntervalSince1970: 410),
            kind: .request,
            requestID: "legacy-nil-turn",
            sessionID: "legacy-nil-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Unscoped legacy session.")]
        ))
        try legacyStore.append(RuntimeChatStoredEvent(
            id: "legacy-device-a",
            timestamp: Date(timeIntervalSince1970: 411),
            kind: .request,
            requestID: "legacy-device-a-turn",
            sessionID: "legacy-device-a-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Device A legacy session.")],
            ownerDeviceID: "device-a"
        ))

        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)

        XCTAssertEqual(try store.listSessions(limit: 10).map(\.sessionID), ["legacy-nil-session"])
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).map(\.sessionID),
            ["legacy-device-a-session"]
        )
        XCTAssertTrue(try store.listSessions(ownerDeviceID: "device-b", limit: 10, includeArchived: true).isEmpty)
        XCTAssertTrue(try store.listMessages(ownerDeviceID: "device-a", sessionID: "legacy-nil-session", limit: 10).isEmpty)
    }

    func testSQLiteBackfillStripsInlineAttachmentBytesBeforeStorageAndFTS() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        try writeRawLegacyEvents([
            RuntimeChatStoredEvent(
                id: "legacy-attachment-request",
                timestamp: Date(timeIntervalSince1970: 420),
                kind: .request,
                requestID: "legacy-attachment-turn",
                sessionID: "legacy-attachment-session",
                model: "ollama:llama3.1:8b",
                messages: [
                    ChatMessage(
                        role: "user",
                        content: "Import the attachment notes.",
                        attachments: [
                            ChatAttachment(
                                type: "text",
                                mimeType: "text/plain",
                                name: "legacy-attachment.txt",
                                dataBase64: "do-not-store",
                                text: "legacy attachment searchable text"
                            )
                        ]
                    )
                ],
                ownerDeviceID: "device-a"
            )
        ], to: legacyURL)

        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)
        let messages = try store.listMessages(ownerDeviceID: "device-a", sessionID: "legacy-attachment-session", limit: 10)
        let attachmentResults = try store.listSessions(
            ownerDeviceID: "device-a",
            limit: 10,
            includeArchived: true,
            query: "searchable"
        )

        XCTAssertEqual(messages.first?.attachments.first?.dataBase64, nil)
        XCTAssertEqual(messages.first?.attachments.first?.text, "legacy attachment searchable text")
        XCTAssertEqual(attachmentResults.map(\.sessionID), ["legacy-attachment-session"])
        XCTAssertEqual(attachmentResults.first?.search?.matchedFields, ["attachment"])
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true, query: "do-not-store").isEmpty
        )
    }

    func testSQLiteBackfillRejectsCorruptJSONLWithoutPartialSilentMigration() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        let validEvent = RuntimeChatStoredEvent(
            id: "legacy-valid-before-corrupt",
            timestamp: Date(timeIntervalSince1970: 430),
            kind: .request,
            requestID: "legacy-valid-turn",
            sessionID: "legacy-valid-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "This should not partially import.")]
        )
        try writeRawLegacyEvents([validEvent], to: legacyURL)
        try appendRawLine("{\"id\":", to: legacyURL)

        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)
        XCTAssertThrowsError(try store.listSessions(limit: 10)) { error in
            guard case RuntimeChatEventStoreError.corruptEventLog(let line, _) = error else {
                return XCTFail("Expected corrupt legacy JSONL error, got \(error).")
            }
            XCTAssertEqual(line, 2)
        }

        let emptySQLiteStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        XCTAssertTrue(try emptySQLiteStore.listSessions(limit: 10).isEmpty)
    }

    private func temporaryDatabaseURL() throws -> URL {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        return directoryURL.appendingPathComponent("runtime-chat-events.sqlite")
    }

    private func temporaryJSONLURL() throws -> URL {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        return directoryURL.appendingPathComponent("runtime-chat-events.jsonl")
    }

    private func writeRawLegacyEvents(_ events: [RuntimeChatStoredEvent], to fileURL: URL) throws {
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let lines = try events.map { event in
            String(data: try legacyJSONLEncoder.encode(event), encoding: .utf8)!
        }
        .joined(separator: "\n")
        try (lines + "\n").write(to: fileURL, atomically: true, encoding: .utf8)
    }

    private func appendRawLine(_ line: String, to fileURL: URL) throws {
        let handle = try FileHandle(forWritingTo: fileURL)
        defer { try? handle.close() }
        try handle.seekToEnd()
        try handle.write(contentsOf: Data((line + "\n").utf8))
    }

    private func posixPermissions(at url: URL) throws -> Int {
        let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
        let permissions = try XCTUnwrap(attributes[.posixPermissions] as? NSNumber)
        return permissions.intValue & 0o777
    }

    private var legacyJSONLEncoder: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }
}
