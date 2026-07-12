@testable import CompanionCore
import OllamaBackend
import SQLite3
import XCTest

final class SQLiteRuntimeChatEventStoreTests: XCTestCase {
    func testSQLiteSemanticEmbeddingCachePersistsAcrossReopenAndMatchesFullOwnerScopedKey() throws {
        let databaseURL = try temporaryDatabaseURL()
        let key = semanticEmbeddingKey(owner: "device-a", session: "session-a", document: "document-a")
        let record = RuntimeChatSemanticEmbeddingRecord(key: key, embedding: [0.25, -0.5, 1.75])

        try SQLiteRuntimeChatEventStore(databaseURL: databaseURL).upsertSemanticEmbeddings([record])

        let reopenedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopenedStore.cachedSemanticEmbeddings(for: [key]), [record])
        XCTAssertTrue(try reopenedStore.cachedSemanticEmbeddings(for: [
            semanticEmbeddingKey(owner: "device-b", session: "session-a", document: "document-a"),
            semanticEmbeddingKey(owner: "device-a", session: "session-b", document: "document-a"),
            semanticEmbeddingKey(owner: "device-a", session: "session-a", model: "ollama:nomic-embed-text-v2", document: "document-a"),
            semanticEmbeddingKey(owner: "device-a", session: "session-a", modelFingerprint: "model-v2", document: "document-a"),
            semanticEmbeddingKey(owner: "device-a", session: "session-a", document: "document-b"),
        ]).isEmpty)
    }

    func testSQLiteSemanticEmbeddingBatchRejectsInvalidVectorsWithoutPartialWrite() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let valid = RuntimeChatSemanticEmbeddingRecord(
            key: semanticEmbeddingKey(owner: "device-a", session: "valid", document: "valid"),
            embedding: [1, 2]
        )
        for invalidEmbedding in [[0, 0], [Double.nan, 1], [Double.infinity, 1], []] {
            let invalid = RuntimeChatSemanticEmbeddingRecord(
                key: semanticEmbeddingKey(owner: "device-a", session: "invalid", document: UUID().uuidString),
                embedding: invalidEmbedding
            )
            XCTAssertThrowsError(try store.upsertSemanticEmbeddings([valid, invalid]))
        }

        XCTAssertTrue(try store.cachedSemanticEmbeddings(for: [valid.key]).isEmpty)
    }

    func testSQLiteSemanticEmbeddingCacheInvalidatesOnlyAppendedOwnerSession() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let invalidated = semanticEmbeddingKey(owner: "device-a", session: "shared", document: "a")
        let otherOwner = semanticEmbeddingKey(owner: "device-b", session: "shared", document: "b")
        let otherSession = semanticEmbeddingKey(owner: "device-a", session: "other", document: "c")
        try store.upsertSemanticEmbeddings([
            RuntimeChatSemanticEmbeddingRecord(key: invalidated, embedding: [1]),
            RuntimeChatSemanticEmbeddingRecord(key: otherOwner, embedding: [2]),
            RuntimeChatSemanticEmbeddingRecord(key: otherSession, embedding: [3]),
        ])

        try store.append(RuntimeChatStoredEvent(
            kind: .request,
            requestID: "request",
            sessionID: "shared",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "changed")],
            ownerDeviceID: "device-a"
        ))

        XCTAssertEqual(
            try store.cachedSemanticEmbeddings(for: [invalidated, otherOwner, otherSession]).map(\.key),
            [otherOwner, otherSession]
        )
    }

    func testSQLiteSemanticEmbeddingCacheRejectsStaleSourceRevisionAfterAppend() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        try store.append(RuntimeChatStoredEvent(
            kind: .request,
            requestID: "request-1",
            sessionID: "revision-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "old document")],
            ownerDeviceID: "device-a"
        ))
        let staleRevision = try XCTUnwrap(store.listSemanticSearchSources(
            ownerDeviceID: "device-a",
            sessionLimit: 10,
            messageLimit: 10,
            includeArchived: false
        ).first?.sourceRevision)
        let key = semanticEmbeddingKey(
            owner: "device-a",
            session: "revision-session",
            document: "old-document"
        )

        try store.append(RuntimeChatStoredEvent(
            kind: .assistantDelta,
            requestID: "request-1",
            sessionID: "revision-session",
            model: "ollama:llama3.1:8b",
            delta: "new document",
            ownerDeviceID: "device-a"
        ))
        try store.upsertSemanticEmbeddings([
            RuntimeChatSemanticEmbeddingRecord(
                key: key,
                embedding: [1, 2],
                sourceRevision: staleRevision
            )
        ])

        XCTAssertTrue(try store.cachedSemanticEmbeddings(for: [key]).isEmpty)
    }

    func testSQLiteSemanticEmbeddingCacheRollsBackWhenCommitGuardIsCancelled() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let key = semanticEmbeddingKey(owner: "device-a", session: "cancelled", document: "document")

        try store.upsertSemanticEmbeddings(
            [RuntimeChatSemanticEmbeddingRecord(key: key, embedding: [1, 2])],
            if: { false }
        )

        XCTAssertTrue(try store.cachedSemanticEmbeddings(for: [key]).isEmpty)
    }

    func testSQLiteSemanticEmbeddingRetentionPruneDeletesOwnerScopedRows() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 100),
            kind: .request,
            requestID: "request",
            sessionID: "deleted-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "delete me")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "deleted-session",
            requestID: "archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 110)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "deleted-session",
            requestID: "delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 120)
        )
        let ownerA = semanticEmbeddingKey(owner: "device-a", session: "deleted-session", document: "a")
        let ownerB = semanticEmbeddingKey(owner: "device-b", session: "deleted-session", document: "b")
        try store.upsertSemanticEmbeddings([
            RuntimeChatSemanticEmbeddingRecord(key: ownerA, embedding: [1]),
            RuntimeChatSemanticEmbeddingRecord(key: ownerB, embedding: [2]),
        ])

        _ = try store.pruneDeletedSessions(
            ownerDeviceID: "device-a",
            deletedBefore: Date(timeIntervalSince1970: 200)
        )

        XCTAssertEqual(try store.cachedSemanticEmbeddings(for: [ownerA, ownerB]).map(\.key), [ownerB])
    }

    func testSQLiteSemanticEmbeddingCacheTreatsCorruptRowsAsReadOnlyMisses() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let key = semanticEmbeddingKey(owner: "device-a", session: "corrupt", document: "document")
        try store.upsertSemanticEmbeddings([
            RuntimeChatSemanticEmbeddingRecord(key: key, embedding: [1, 2])
        ])
        try executeRawSQLite(
            at: databaseURL,
            sql: "UPDATE runtime_chat_semantic_embeddings SET dimension = 3 WHERE session_id = 'corrupt'"
        )

        XCTAssertTrue(try store.cachedSemanticEmbeddings(for: [key]).isEmpty)
        XCTAssertEqual(
            try rawSQLiteInteger(at: databaseURL, sql: "SELECT COUNT(*) FROM runtime_chat_semantic_embeddings"),
            1
        )
    }

    func testSQLiteSemanticEmbeddingCacheCapsRowsPerOwnerModelScope() throws {
        let store = SQLiteRuntimeChatEventStore(
            databaseURL: try temporaryDatabaseURL(),
            semanticEmbeddingRowLimitPerOwnerModel: 2
        )
        let keys = (1...3).map {
            semanticEmbeddingKey(owner: "device-a", session: "session-\($0)", document: "document-\($0)")
        }
        try store.upsertSemanticEmbeddings(keys.map {
            RuntimeChatSemanticEmbeddingRecord(key: $0, embedding: [Double($0.sessionID.suffix(1)) ?? 1])
        })
        let otherOwner = semanticEmbeddingKey(owner: "device-b", session: "session-1", document: "document-1")
        let otherModel = semanticEmbeddingKey(
            owner: "device-a",
            session: "session-1",
            modelFingerprint: "model-v2",
            document: "document-1"
        )
        try store.upsertSemanticEmbeddings([
            RuntimeChatSemanticEmbeddingRecord(key: otherOwner, embedding: [4]),
            RuntimeChatSemanticEmbeddingRecord(key: otherModel, embedding: [5]),
        ])

        XCTAssertEqual(try store.cachedSemanticEmbeddings(for: keys).map(\.key), [keys[2]])
        XCTAssertEqual(try store.cachedSemanticEmbeddings(for: [otherOwner, otherModel]).map(\.key), [otherOwner, otherModel])
    }

    func testSQLiteSemanticSearchSourcesReadOwnerScopedSessionsAndMessagesInOneSnapshot() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        for (owner, session, content, timestamp) in [
            ("device-a", "session-a", "Device A private semantic text", 100.0),
            ("device-b", "session-b", "Device B private semantic text", 200.0),
        ] {
            try store.append(RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: timestamp),
                kind: .request,
                requestID: "request-\(session)",
                sessionID: session,
                model: "ollama:llama3.1:8b",
                messages: [
                    ChatMessage(
                        role: "user",
                        content: content,
                        attachments: [
                            ChatAttachment(
                                type: "image",
                                mimeType: "image/png",
                                dataBase64: "inline-byte-canary-\(owner)"
                            )
                        ]
                    )
                ],
                ownerDeviceID: owner
            ))
        }

        let sources = try store.listSemanticSearchSources(
            ownerDeviceID: "device-a",
            sessionLimit: 10,
            messageLimit: 10,
            includeArchived: false
        )

        XCTAssertEqual(sources.map(\.session.sessionID), ["session-a"])
        XCTAssertEqual(sources.first?.messages.map(\.content), ["Device A private semantic text"])
        XCTAssertNil(sources.first?.messages.first?.attachments.first?.dataBase64)
        XCTAssertFalse(String(describing: sources).contains("Device B private semantic text"))
    }

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

    func testSQLiteStorePersistsSourceAttributionsAndRegeneratePrefixRewindsAssistant() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let firstAssistantMessageID = "assistant_message_11111111111111111111111111111111"
        let secondAssistantMessageID = "assistant_message_22222222222222222222222222222222"
        let firstAttribution = RuntimeChatSourceAttribution(
            sourceIndex: 1,
            documentName: "old.md",
            mimeType: "text/markdown",
            chunkIndex: 0
        )
        let secondAttribution = RuntimeChatSourceAttribution(
            sourceIndex: 1,
            documentName: "new.md",
            mimeType: "text/markdown",
            chunkIndex: 3
        )
        let firstBinding = RuntimeChatSourceAttributionBinding(
            sourceIndex: 1,
            sourceAnchorID: "source_anchor_1111111111111111",
            documentID: "doc-old",
            sourceRevision: String(repeating: "1", count: 64)
        )
        let secondBinding = RuntimeChatSourceAttributionBinding(
            sourceIndex: 1,
            sourceAnchorID: "source_anchor_2222222222222222",
            documentID: "doc-new",
            sourceRevision: String(repeating: "2", count: 64)
        )
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 100),
            kind: .request,
            requestID: "turn-1",
            sessionID: "regenerate-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Regenerate this answer.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 101),
            kind: .assistantDelta,
            requestID: "turn-1",
            sessionID: "regenerate-session",
            model: "ollama:llama3.1:8b",
            delta: "Old answer"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 102),
            kind: .done,
            requestID: "turn-1",
            sessionID: "regenerate-session",
            model: "ollama:llama3.1:8b",
            finishReason: "stop",
            sourceAttributions: [firstAttribution],
            assistantMessageID: firstAssistantMessageID,
            sourceAttributionBindings: [firstBinding]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 103),
            kind: .request,
            requestID: "turn-2",
            sessionID: "regenerate-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Regenerate this answer.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 104),
            kind: .assistantDelta,
            requestID: "turn-2",
            sessionID: "regenerate-session",
            model: "ollama:llama3.1:8b",
            delta: "New answer"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 105),
            kind: .done,
            requestID: "turn-2",
            sessionID: "regenerate-session",
            model: "ollama:llama3.1:8b",
            finishReason: "stop",
            sourceAttributions: [secondAttribution],
            assistantMessageID: secondAssistantMessageID,
            sourceAttributionBindings: [secondBinding]
        ))

        let reopenedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let messages = try reopenedStore.listMessages(sessionID: "regenerate-session", limit: 10)
        XCTAssertEqual(messages.map(\.content), ["Regenerate this answer.", "New answer"])
        XCTAssertEqual(messages.last?.sourceAttributions, [secondAttribution])
        XCTAssertEqual(messages.last?.assistantMessageID, secondAssistantMessageID)
        XCTAssertNil(try reopenedStore.resolveSourceAttribution(
            ownerDeviceID: nil,
            sessionID: "regenerate-session",
            assistantMessageID: firstAssistantMessageID,
            sourceIndex: 1
        ))
        XCTAssertEqual(
            try reopenedStore.resolveSourceAttribution(
                ownerDeviceID: nil,
                sessionID: "regenerate-session",
                assistantMessageID: secondAssistantMessageID,
                sourceIndex: 1
            )?.binding,
            secondBinding
        )
    }

    func testSQLiteStoreResolvesOnlyOwnerScopedBoundCanonicalAssistantAttribution() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let assistantMessageID = "assistant_message_0123456789abcdef0123456789abcdef"
        let attribution = RuntimeChatSourceAttribution(
            sourceIndex: 1,
            documentName: "source.md",
            mimeType: "text/markdown",
            chunkIndex: 0
        )
        let binding = RuntimeChatSourceAttributionBinding(
            sourceIndex: 1,
            sourceAnchorID: "source_anchor_0123456789abcdef",
            documentID: "doc-source",
            sourceRevision: String(repeating: "a", count: 64)
        )
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 1),
            kind: .request,
            requestID: "request",
            sessionID: "session",
            model: "model",
            messages: [ChatMessage(role: "user", content: "Question")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 2),
            kind: .assistantDelta,
            requestID: "request",
            sessionID: "session",
            model: "model",
            delta: "Answer",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 3),
            kind: .done,
            requestID: "request",
            sessionID: "session",
            model: "model",
            finishReason: "stop",
            ownerDeviceID: "device-a",
            sourceAttributions: [attribution],
            assistantMessageID: assistantMessageID,
            sourceAttributionBindings: [binding]
        ))

        let reopenedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try reopenedStore.listMessages(
                ownerDeviceID: "device-a",
                sessionID: "session",
                limit: 10
            ).last?.assistantMessageID,
            assistantMessageID
        )
        XCTAssertEqual(
            try reopenedStore.resolveSourceAttribution(
                ownerDeviceID: "device-a",
                sessionID: "session",
                assistantMessageID: assistantMessageID,
                sourceIndex: 1
            )?.binding,
            binding
        )
        XCTAssertNil(try reopenedStore.resolveSourceAttribution(
            ownerDeviceID: "device-b",
            sessionID: "session",
            assistantMessageID: assistantMessageID,
            sourceIndex: 1
        ))
        XCTAssertNil(try reopenedStore.resolveSourceAttribution(
            ownerDeviceID: "device-a",
            sessionID: "wrong-session",
            assistantMessageID: assistantMessageID,
            sourceIndex: 1
        ))
        XCTAssertNil(try reopenedStore.resolveSourceAttribution(
            ownerDeviceID: "device-a",
            sessionID: "session",
            assistantMessageID: assistantMessageID,
            sourceIndex: 2
        ))

        _ = try reopenedStore.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "session",
            requestID: "archive-session",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 4)
        )
        _ = try reopenedStore.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "session",
            requestID: "delete-session",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 5)
        )
        XCTAssertNil(try reopenedStore.resolveSourceAttribution(
            ownerDeviceID: "device-a",
            sessionID: "session",
            assistantMessageID: assistantMessageID,
            sourceIndex: 1
        ))
        let pruneResult = try reopenedStore.pruneDeletedSessions(
            ownerDeviceID: "device-a",
            deletedBefore: Date(timeIntervalSince1970: 6)
        )
        XCTAssertEqual(pruneResult.prunedSessionIDs, ["session"])
        XCTAssertNil(try SQLiteRuntimeChatEventStore(databaseURL: databaseURL).resolveSourceAttribution(
            ownerDeviceID: "device-a",
            sessionID: "session",
            assistantMessageID: assistantMessageID,
            sourceIndex: 1
        ))

        let legacyStore = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        try legacyStore.append(RuntimeChatStoredEvent(
            kind: .done,
            requestID: "legacy",
            sessionID: "legacy",
            model: "model",
            finishReason: "stop",
            sourceAttributions: [attribution]
        ))
        XCTAssertNil(try legacyStore.resolveSourceAttribution(
            ownerDeviceID: nil,
            sessionID: "legacy",
            assistantMessageID: assistantMessageID,
            sourceIndex: 1
        ))
    }

    func testSQLiteStoreRejectsNoncanonicalOrMisplacedSourceAttributions() throws {
        let valid = RuntimeChatSourceAttribution(
            sourceIndex: 1,
            documentName: "source.md",
            mimeType: "text/markdown",
            chunkIndex: 0
        )
        let invalidEvents = [
            RuntimeChatStoredEvent(
                kind: .cancelled,
                requestID: "wrong-kind",
                sessionID: "session",
                model: "model",
                finishReason: "cancelled",
                sourceAttributions: [valid]
            ),
            RuntimeChatStoredEvent(
                kind: .done,
                requestID: "wrong-finish",
                sessionID: "session",
                model: "model",
                finishReason: "length",
                sourceAttributions: [valid]
            ),
            RuntimeChatStoredEvent(
                kind: .done,
                requestID: "noncontiguous",
                sessionID: "session",
                model: "model",
                finishReason: "stop",
                sourceAttributions: [RuntimeChatSourceAttribution(
                    sourceIndex: 2,
                    documentName: "source.md",
                    mimeType: "text/markdown",
                    chunkIndex: 0
                )]
            ),
            RuntimeChatStoredEvent(
                kind: .done,
                requestID: "unsafe-fields",
                sessionID: "session",
                model: "model",
                finishReason: "stop",
                sourceAttributions: [RuntimeChatSourceAttribution(
                    sourceIndex: 1,
                    documentName: "/private/source.md",
                    mimeType: "TEXT/PLAIN",
                    chunkIndex: -1
                )]
            ),
        ]

        for event in invalidEvents {
            let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
            XCTAssertThrowsError(try store.append(event))
        }
    }

    func testJSONLStoreRejectsForbiddenSourceAttributionFieldsAndAcceptsLegacyEvents() throws {
        let fileURL = try temporaryJSONLURL()
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let event = RuntimeChatStoredEvent(
            kind: .done,
            requestID: "forbidden-field",
            sessionID: "session",
            model: "model",
            finishReason: "stop",
            sourceAttributions: [RuntimeChatSourceAttribution(
                sourceIndex: 1,
                documentName: "source.md",
                mimeType: "text/markdown",
                chunkIndex: 0
            )]
        )
        var object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: encoder.encode(event)) as? [String: Any]
        )
        var attributions = try XCTUnwrap(object["source_attributions"] as? [[String: Any]])
        attributions[0]["text"] = "forbidden source text"
        object["source_attributions"] = attributions
        let forbiddenData = try JSONSerialization.data(withJSONObject: object)
        try (forbiddenData + Data([0x0A])).write(to: fileURL)

        XCTAssertThrowsError(
            try JSONLRuntimeChatEventStore(fileURL: fileURL).listMessages(
                sessionID: "session",
                limit: 10
            )
        )

        let legacyURL = try temporaryJSONLURL()
        let legacyEvent = RuntimeChatStoredEvent(
            kind: .done,
            requestID: "legacy",
            sessionID: "legacy-session",
            model: "model",
            finishReason: "stop"
        )
        try (encoder.encode(legacyEvent) + Data([0x0A])).write(to: legacyURL)
        XCTAssertNoThrow(
            try JSONLRuntimeChatEventStore(fileURL: legacyURL).listMessages(
                sessionID: "legacy-session",
                limit: 10
            )
        )
    }

    func testJSONLStoreRejectsUnknownInternalSourceAttributionBindingFields() throws {
        let fileURL = try temporaryJSONLURL()
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let event = RuntimeChatStoredEvent(
            kind: .done,
            requestID: "unknown-binding-field",
            sessionID: "session",
            model: "model",
            finishReason: "stop",
            sourceAttributions: [RuntimeChatSourceAttribution(
                sourceIndex: 1,
                documentName: "source.md",
                mimeType: "text/markdown",
                chunkIndex: 0
            )],
            assistantMessageID: "assistant_message_33333333333333333333333333333333",
            sourceAttributionBindings: [RuntimeChatSourceAttributionBinding(
                sourceIndex: 1,
                sourceAnchorID: "source_anchor_3333333333333333",
                documentID: "doc-source",
                sourceRevision: String(repeating: "3", count: 64)
            )]
        )
        var object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: encoder.encode(event)) as? [String: Any]
        )
        var bindings = try XCTUnwrap(object["source_attribution_bindings"] as? [[String: Any]])
        bindings[0]["future_internal_locator"] = "must fail closed"
        object["source_attribution_bindings"] = bindings
        let data = try JSONSerialization.data(withJSONObject: object)
        try (data + Data([0x0A])).write(to: fileURL)

        XCTAssertThrowsError(
            try JSONLRuntimeChatEventStore(fileURL: fileURL).listMessages(
                sessionID: "session",
                limit: 10
            )
        ) { error in
            guard case RuntimeChatEventStoreError.corruptEventLog(let line, _) = error else {
                return XCTFail("Expected corrupt event log, got \(error)")
            }
            XCTAssertEqual(line, 1)
        }
    }

    func testSourceAttributionResolverRejectsDuplicateRequestBoundaryAfterJSONLAndSQLiteReopen() throws {
        let canonicalAssistantMessageID = "assistant_message_44444444444444444444444444444444"
        let duplicateAssistantMessageID = "assistant_message_55555555555555555555555555555555"
        let attribution = RuntimeChatSourceAttribution(
            sourceIndex: 1,
            documentName: "source.md",
            mimeType: "text/markdown",
            chunkIndex: 0
        )
        let binding = RuntimeChatSourceAttributionBinding(
            sourceIndex: 1,
            sourceAnchorID: "source_anchor_4444444444444444",
            documentID: "doc-source",
            sourceRevision: String(repeating: "4", count: 64)
        )

        func appendFixtures(to store: any RuntimeChatEventStore) throws {
            for event in [
                RuntimeChatStoredEvent(
                    timestamp: Date(timeIntervalSince1970: 1),
                    kind: .request,
                    requestID: "canonical-request",
                    sessionID: "canonical-session",
                    model: "model",
                    messages: [ChatMessage(role: "user", content: "Canonical question")]
                ),
                RuntimeChatStoredEvent(
                    timestamp: Date(timeIntervalSince1970: 2),
                    kind: .assistantDelta,
                    requestID: "canonical-request",
                    sessionID: "canonical-session",
                    model: "model",
                    delta: "Canonical answer"
                ),
                RuntimeChatStoredEvent(
                    timestamp: Date(timeIntervalSince1970: 3),
                    kind: .done,
                    requestID: "canonical-request",
                    sessionID: "canonical-session",
                    model: "model",
                    finishReason: "stop",
                    sourceAttributions: [attribution],
                    assistantMessageID: canonicalAssistantMessageID,
                    sourceAttributionBindings: [binding]
                ),
                RuntimeChatStoredEvent(
                    timestamp: Date(timeIntervalSince1970: 10),
                    kind: .request,
                    requestID: "client-duplicate-request",
                    sessionID: "duplicate-session",
                    model: "model",
                    messages: [ChatMessage(role: "user", content: "First request")]
                ),
                RuntimeChatStoredEvent(
                    timestamp: Date(timeIntervalSince1970: 11),
                    kind: .assistantDelta,
                    requestID: "client-duplicate-request",
                    sessionID: "duplicate-session",
                    model: "model",
                    delta: "Output before duplicate boundary"
                ),
                RuntimeChatStoredEvent(
                    timestamp: Date(timeIntervalSince1970: 12),
                    kind: .request,
                    requestID: "client-duplicate-request",
                    sessionID: "duplicate-session",
                    model: "model",
                    messages: [ChatMessage(role: "user", content: "Second request")]
                ),
                RuntimeChatStoredEvent(
                    timestamp: Date(timeIntervalSince1970: 13),
                    kind: .done,
                    requestID: "client-duplicate-request",
                    sessionID: "duplicate-session",
                    model: "model",
                    finishReason: "stop",
                    sourceAttributions: [attribution],
                    assistantMessageID: duplicateAssistantMessageID,
                    sourceAttributionBindings: [binding]
                ),
            ] {
                try store.append(event)
            }
        }

        func assertResolutionAfterReopen(_ store: any RuntimeChatEventStore) throws {
            XCTAssertEqual(
                try store.resolveSourceAttribution(
                    ownerDeviceID: nil,
                    sessionID: "canonical-session",
                    assistantMessageID: canonicalAssistantMessageID,
                    sourceIndex: 1
                )?.binding,
                binding
            )
            XCTAssertNil(try store.resolveSourceAttribution(
                ownerDeviceID: nil,
                sessionID: "duplicate-session",
                assistantMessageID: duplicateAssistantMessageID,
                sourceIndex: 1
            ))
        }

        let jsonlURL = try temporaryJSONLURL()
        try appendFixtures(to: JSONLRuntimeChatEventStore(fileURL: jsonlURL))
        try assertResolutionAfterReopen(JSONLRuntimeChatEventStore(fileURL: jsonlURL))

        let sqliteURL = try temporaryDatabaseURL()
        try appendFixtures(to: SQLiteRuntimeChatEventStore(databaseURL: sqliteURL))
        try assertResolutionAfterReopen(SQLiteRuntimeChatEventStore(databaseURL: sqliteURL))
    }

    func testJSONLAppendRejectsInvalidAttributionBeforeCreatingEventLog() throws {
        let fileURL = try temporaryJSONLURL()
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        let invalidEvent = RuntimeChatStoredEvent(
            kind: .done,
            requestID: "invalid-attribution-append",
            sessionID: "session",
            model: "model",
            finishReason: "stop",
            sourceAttributions: [RuntimeChatSourceAttribution(
                sourceIndex: 2,
                documentName: "source.md",
                mimeType: "text/markdown",
                chunkIndex: 0
            )]
        )

        XCTAssertThrowsError(try store.append(invalidEvent))
        XCTAssertFalse(FileManager.default.fileExists(atPath: fileURL.path))
    }

    func testSQLiteStorePreservesRuntimeCompactionMetadataWithoutIndexingIt() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let metadataSentinel = "sourcepointerftssentinel9f31"
        let metadata = RuntimeChatCompactionMetadata(
            strategy: "adaptive_backend_only_summary_v2",
            sourcePointers: [
                RuntimeChatCompactionSourcePointer(
                    sessionID: "sqlite-compaction-session",
                    requestID: "sqlite-compaction-visible-request",
                    startTurn: 1,
                    endTurn: 6,
                    totalTurns: 18,
                    compactedTurnCount: 6,
                    retainedStartTurn: 7,
                    retainedEndTurn: 18,
                    retainedTurnCount: 12
                )
            ],
            estimatorIdentifier: metadataSentinel,
            contextWindowTokens: 8_192,
            outputReserveTokens: 1_024,
            inputBudgetTokens: 7_168,
            estimatedInputTokensBefore: 8_500,
            estimatedInputTokensAfter: 6_900
        )

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 180),
            kind: .request,
            requestID: "sqlite-compaction-visible-request",
            sessionID: "sqlite-compaction-session",
            model: "ollama:llama3.1:8b",
            messages: [
                ChatMessage(role: "user", content: "Visible compaction transcript only.")
            ],
            compactionMetadata: metadata
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 181),
            kind: .assistantDelta,
            requestID: "sqlite-compaction-visible-request",
            sessionID: "sqlite-compaction-session",
            model: "ollama:llama3.1:8b",
            delta: "Visible answer only."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 182),
            kind: .done,
            requestID: "sqlite-compaction-visible-request",
            sessionID: "sqlite-compaction-session",
            model: "ollama:llama3.1:8b",
            finishReason: "stop"
        ))

        let reopenedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let visibleMessages = try reopenedStore.listMessages(sessionID: "sqlite-compaction-session", limit: 10)
        XCTAssertEqual(visibleMessages.map(\.content), [
            "Visible compaction transcript only.",
            "Visible answer only."
        ])
        XCTAssertEqual(
            try reopenedStore.listSessions(
                ownerDeviceID: nil,
                limit: 10,
                includeArchived: true,
                query: "Visible transcript"
            ).map(\.sessionID),
            ["sqlite-compaction-session"]
        )
        XCTAssertTrue(
            try reopenedStore.listSessions(
                ownerDeviceID: nil,
                limit: 10,
                includeArchived: true,
                query: metadataSentinel
            ).isEmpty
        )

        let rawEvents = try rawSQLiteEvents(at: databaseURL)
        let storedRequest = try XCTUnwrap(rawEvents.first { $0.kind == .request })
        XCTAssertEqual(storedRequest.compactionMetadata, metadata)
        XCTAssertFalse(storedRequest.messages?.contains { $0.content.contains(metadataSentinel) } == true)
        let storedMetadataJSON = try JSONEncoder().encode(try XCTUnwrap(storedRequest.compactionMetadata))
        let storedMetadataObject = try XCTUnwrap(
            JSONSerialization.jsonObject(with: storedMetadataJSON) as? [String: Any]
        )
        XCTAssertNil(storedMetadataObject["summary"])
        XCTAssertNil(storedMetadataObject["summary_text"])
    }

    func testSQLiteStoreImportsLegacyCompactionMetadataWithoutStructuralAccounting() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        let pointer = RuntimeChatCompactionSourcePointer(
            sessionID: "sqlite-legacy-compaction-session",
            requestID: "sqlite-legacy-compaction-source",
            startTurn: 1,
            endTurn: 2,
            totalTurns: 4,
            compactedTurnCount: 2,
            retainedStartTurn: 3,
            retainedEndTurn: 4,
            retainedTurnCount: 2
        )
        let legacyMetadata = RuntimeChatCompactionMetadata(sourcePointers: [pointer])
        let legacyEvent = RuntimeChatStoredEvent(
            id: "sqlite-legacy-compaction-event",
            timestamp: Date(timeIntervalSince1970: 183),
            kind: .request,
            requestID: "sqlite-legacy-compaction-request",
            sessionID: "sqlite-legacy-compaction-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Visible legacy compaction transcript.")],
            compactionMetadata: legacyMetadata
        )

        let encodedLegacyEvent = try legacyJSONLEncoder.encode(legacyEvent)
        let encodedLegacyObject = try XCTUnwrap(
            JSONSerialization.jsonObject(with: encodedLegacyEvent) as? [String: Any]
        )
        let encodedLegacyMetadata = try XCTUnwrap(
            encodedLegacyObject["compaction_metadata"] as? [String: Any]
        )
        XCTAssertEqual(encodedLegacyMetadata["strategy"] as? String, "backend_only_summary_v1")
        XCTAssertNil(encodedLegacyMetadata["estimator_identifier"])
        XCTAssertNil(encodedLegacyMetadata["context_window_tokens"])
        XCTAssertNil(encodedLegacyMetadata["estimated_input_tokens_before"])

        try writeRawLegacyEvents([legacyEvent], to: legacyURL)
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)
        XCTAssertEqual(
            try store.listMessages(sessionID: "sqlite-legacy-compaction-session", limit: 10).map(\.content),
            ["Visible legacy compaction transcript."]
        )

        let reopenedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL, legacyJSONLFileURL: legacyURL)
        XCTAssertEqual(try reopenedStore.listSessions(limit: 10).map(\.sessionID), ["sqlite-legacy-compaction-session"])
        let storedMetadata = try XCTUnwrap(rawSQLiteEvents(at: databaseURL).first?.compactionMetadata)
        XCTAssertEqual(storedMetadata, legacyMetadata)
        XCTAssertEqual(storedMetadata.strategy, "backend_only_summary_v1")
        XCTAssertNil(storedMetadata.estimatorIdentifier)
        XCTAssertNil(storedMetadata.contextWindowTokens)
        XCTAssertNil(storedMetadata.outputReserveTokens)
        XCTAssertNil(storedMetadata.inputBudgetTokens)
        XCTAssertNil(storedMetadata.estimatedInputTokensBefore)
        XCTAssertNil(storedMetadata.estimatedInputTokensAfter)
    }

    func testSQLiteStorePreservesWhitespaceOnlyStreamingDeltas() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 170),
            kind: .request,
            requestID: "sqlite-whitespace",
            sessionID: "sqlite-whitespace-session",
            model: "ollama:qwen3:8b",
            messages: [ChatMessage(role: "user", content: "Stream whitespace chunks.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 171),
            kind: .reasoningDelta,
            requestID: "sqlite-whitespace",
            sessionID: "sqlite-whitespace-session",
            model: "ollama:qwen3:8b",
            reasoningDelta: "Think"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 172),
            kind: .reasoningDelta,
            requestID: "sqlite-whitespace",
            sessionID: "sqlite-whitespace-session",
            model: "ollama:qwen3:8b",
            reasoningDelta: "\n"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 173),
            kind: .reasoningDelta,
            requestID: "sqlite-whitespace",
            sessionID: "sqlite-whitespace-session",
            model: "ollama:qwen3:8b",
            reasoningDelta: "more"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 174),
            kind: .assistantDelta,
            requestID: "sqlite-whitespace",
            sessionID: "sqlite-whitespace-session",
            model: "ollama:qwen3:8b",
            delta: "Hello"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 175),
            kind: .assistantDelta,
            requestID: "sqlite-whitespace",
            sessionID: "sqlite-whitespace-session",
            model: "ollama:qwen3:8b",
            delta: " "
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 176),
            kind: .assistantDelta,
            requestID: "sqlite-whitespace",
            sessionID: "sqlite-whitespace-session",
            model: "ollama:qwen3:8b",
            delta: "world"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 177),
            kind: .done,
            requestID: "sqlite-whitespace",
            sessionID: "sqlite-whitespace-session",
            model: "ollama:qwen3:8b",
            finishReason: "stop"
        ))

        let messages = try store.listMessages(sessionID: "sqlite-whitespace-session", limit: 10)

        XCTAssertEqual(messages.map(\.role), ["user", "assistant"])
        XCTAssertEqual(messages.last?.content, "Hello world")
        XCTAssertEqual(messages.last?.reasoning, "Think\nmore")
    }

    func testSQLiteStoreRejectsEmptyStreamingDeltas() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())

        XCTAssertThrowsError(try store.append(RuntimeChatStoredEvent(
            kind: .assistantDelta,
            requestID: "sqlite-empty-assistant",
            sessionID: "sqlite-empty-session",
            model: "ollama:qwen3:8b",
            delta: ""
        ))) { error in
            XCTAssertEqual(
                error as? RuntimeChatEventStoreError,
                .corruptEventLog(line: 0, reason: "chat assistant delta is empty")
            )
        }
        XCTAssertThrowsError(try store.append(RuntimeChatStoredEvent(
            kind: .reasoningDelta,
            requestID: "sqlite-empty-reasoning",
            sessionID: "sqlite-empty-session",
            model: "ollama:qwen3:8b",
            reasoningDelta: ""
        ))) { error in
            XCTAssertEqual(
                error as? RuntimeChatEventStoreError,
                .corruptEventLog(line: 0, reason: "chat reasoning delta is empty")
            )
        }
    }

    func testSQLiteStoreRejectsInvalidRuntimeCompactionMetadata() throws {
        let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let validPointer = RuntimeChatCompactionSourcePointer(
            sessionID: "sqlite-invalid-compaction-session",
            requestID: "sqlite-invalid-compaction",
            startTurn: 1,
            endTurn: 2,
            totalTurns: 5,
            compactedTurnCount: 2,
            retainedStartTurn: 3,
            retainedEndTurn: 5,
            retainedTurnCount: 3
        )
        let validMetadata = RuntimeChatCompactionMetadata(sourcePointers: [validPointer])
        func accountingMetadata(
            strategy: String = "adaptive_backend_only_summary_v2",
            sourcePointers: [RuntimeChatCompactionSourcePointer]? = nil,
            estimatorIdentifier: String? = "utf8_bytes_div_4_v1",
            contextWindowTokens: Int? = 8_192,
            outputReserveTokens: Int? = 1_024,
            inputBudgetTokens: Int? = 7_168,
            estimatedInputTokensBefore: Int? = 8_500,
            estimatedInputTokensAfter: Int? = 6_900
        ) -> RuntimeChatCompactionMetadata {
            RuntimeChatCompactionMetadata(
                strategy: strategy,
                sourcePointers: sourcePointers ?? [validPointer],
                estimatorIdentifier: estimatorIdentifier,
                contextWindowTokens: contextWindowTokens,
                outputReserveTokens: outputReserveTokens,
                inputBudgetTokens: inputBudgetTokens,
                estimatedInputTokensBefore: estimatedInputTokensBefore,
                estimatedInputTokensAfter: estimatedInputTokensAfter
            )
        }

        let invalidEvents: [(event: RuntimeChatStoredEvent, reason: String)] = [
            (
                RuntimeChatStoredEvent(
                    kind: .assistantDelta,
                    requestID: "sqlite-invalid-compaction-non-request",
                    sessionID: "sqlite-invalid-compaction-session",
                    model: "ollama:llama3.1:8b",
                    delta: "Visible answer.",
                    compactionMetadata: validMetadata
                ),
                "chat compaction metadata is only valid on request events"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-empty-strategy",
                    metadata: RuntimeChatCompactionMetadata(
                        strategy: "  ",
                        sourcePointers: [validPointer]
                    )
                ),
                "chat compaction strategy is empty"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-empty-pointers",
                    metadata: RuntimeChatCompactionMetadata(sourcePointers: [])
                ),
                "chat compaction source pointers are empty"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-partial-accounting",
                    metadata: accountingMetadata(estimatedInputTokensAfter: nil)
                ),
                "chat compaction accounting fields must be all present or all absent"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-v2-missing-accounting",
                    metadata: RuntimeChatCompactionMetadata(
                        strategy: "adaptive_backend_only_summary_v2",
                        sourcePointers: [validPointer]
                    )
                ),
                "adaptive chat compaction accounting is missing"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-empty-estimator",
                    metadata: accountingMetadata(estimatorIdentifier: "  ")
                ),
                "chat compaction estimator identifier is empty"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-negative-reserve",
                    metadata: accountingMetadata(outputReserveTokens: -1)
                ),
                "chat compaction accounting token counts are invalid"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-zero-context",
                    metadata: accountingMetadata(contextWindowTokens: 0)
                ),
                "chat compaction accounting token counts are invalid"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-zero-budget",
                    metadata: accountingMetadata(inputBudgetTokens: 0)
                ),
                "chat compaction accounting token counts are invalid"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-negative-after",
                    metadata: accountingMetadata(estimatedInputTokensAfter: -1)
                ),
                "chat compaction accounting token counts are invalid"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-context-reserve",
                    metadata: accountingMetadata(
                        contextWindowTokens: 1_024,
                        outputReserveTokens: 1_024,
                        inputBudgetTokens: 1
                    )
                ),
                "chat compaction context window must exceed output reserve"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-budget",
                    metadata: accountingMetadata(inputBudgetTokens: 7_000)
                ),
                "chat compaction input budget is inconsistent"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-before-budget",
                    metadata: accountingMetadata(estimatedInputTokensBefore: 7_168)
                ),
                "chat compaction input estimate did not exceed budget"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-after-budget",
                    metadata: accountingMetadata(estimatedInputTokensAfter: 7_169)
                ),
                "chat compaction output estimate exceeds input budget"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-mismatched-event",
                    metadata: accountingMetadata()
                ),
                "adaptive chat compaction source pointer is inconsistent with request event"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction",
                    metadata: accountingMetadata(sourcePointers: [validPointer, validPointer])
                ),
                "adaptive chat compaction source pointer is inconsistent with request event"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction",
                    metadata: accountingMetadata(sourcePointers: [
                        RuntimeChatCompactionSourcePointer(
                            sessionID: "sqlite-invalid-compaction-session",
                            requestID: "sqlite-invalid-compaction",
                            startTurn: 1,
                            endTurn: 2,
                            totalTurns: 5,
                            compactedTurnCount: 2,
                            retainedStartTurn: 4,
                            retainedEndTurn: 5,
                            retainedTurnCount: 2
                        )
                    ])
                ),
                "adaptive chat compaction source pointer is inconsistent with request event"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-empty-source-kind",
                    metadata: RuntimeChatCompactionMetadata(sourcePointers: [
                        RuntimeChatCompactionSourcePointer(
                            sourceKind: "  ",
                            sessionID: "sqlite-invalid-compaction-session",
                            requestID: "sqlite-invalid-compaction-empty-source-kind",
                            startTurn: 1,
                            endTurn: 2,
                            totalTurns: 5,
                            compactedTurnCount: 2,
                            retainedStartTurn: 3,
                            retainedEndTurn: 5,
                            retainedTurnCount: 3
                        )
                    ])
                ),
                "chat compaction source kind is empty"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-range",
                    metadata: RuntimeChatCompactionMetadata(sourcePointers: [
                        RuntimeChatCompactionSourcePointer(
                            sessionID: "sqlite-invalid-compaction-session",
                            requestID: "sqlite-invalid-compaction-range",
                            startTurn: 2,
                            endTurn: 4,
                            totalTurns: 5,
                            compactedTurnCount: 2,
                            retainedStartTurn: 5,
                            retainedEndTurn: 5,
                            retainedTurnCount: 1
                        )
                    ])
                ),
                "chat compaction source pointer range is invalid"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-retained-start",
                    metadata: RuntimeChatCompactionMetadata(sourcePointers: [
                        RuntimeChatCompactionSourcePointer(
                            sessionID: "sqlite-invalid-compaction-session",
                            requestID: "sqlite-invalid-compaction-retained-start",
                            startTurn: 1,
                            endTurn: 3,
                            totalTurns: 5,
                            compactedTurnCount: 3,
                            retainedStartTurn: 3,
                            retainedEndTurn: 5,
                            retainedTurnCount: 3
                        )
                    ])
                ),
                "chat compaction retained range starts before compacted range"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-retained-end",
                    metadata: RuntimeChatCompactionMetadata(sourcePointers: [
                        RuntimeChatCompactionSourcePointer(
                            sessionID: "sqlite-invalid-compaction-session",
                            requestID: "sqlite-invalid-compaction-retained-end",
                            startTurn: 1,
                            endTurn: 2,
                            totalTurns: 5,
                            compactedTurnCount: 2,
                            retainedStartTurn: 3,
                            retainedEndTurn: 6,
                            retainedTurnCount: 4
                        )
                    ])
                ),
                "chat compaction retained range exceeds total turns"
            ),
        ]

        for (event, reason) in invalidEvents {
            XCTAssertThrowsError(try store.append(event), reason) { error in
                XCTAssertEqual(
                    error as? RuntimeChatEventStoreError,
                    .corruptEventLog(line: 0, reason: reason)
                )
            }
        }
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

    private func semanticEmbeddingKey(
        owner: String?,
        session: String,
        model: String = "ollama:nomic-embed-text",
        modelFingerprint: String = "model-v1",
        document: String
    ) -> RuntimeChatSemanticEmbeddingKey {
        RuntimeChatSemanticEmbeddingKey(
            ownerDeviceID: owner,
            sessionID: session,
            canonicalQualifiedEmbeddingModelID: model,
            modelFingerprint: modelFingerprint,
            documentFingerprint: document
        )
    }

    private func executeRawSQLite(at databaseURL: URL, sql: String) throws {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READWRITE, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 10)
        }
        defer { sqlite3_close(database) }
        guard sqlite3_exec(database, sql, nil, nil, nil) == SQLITE_OK else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 11)
        }
    }

    private func rawSQLiteInteger(at databaseURL: URL, sql: String) throws -> Int {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 12)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 13)
        }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 14)
        }
        return Int(sqlite3_column_int64(statement, 0))
    }

    private func invalidCompactionRequest(
        requestID: String,
        metadata: RuntimeChatCompactionMetadata
    ) -> RuntimeChatStoredEvent {
        RuntimeChatStoredEvent(
            kind: .request,
            requestID: requestID,
            sessionID: "sqlite-invalid-compaction-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Visible prompt.")],
            compactionMetadata: metadata
        )
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

    private func rawSQLiteEvents(at databaseURL: URL) throws -> [RuntimeChatStoredEvent] {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY, nil) == SQLITE_OK,
              let database else {
            throw NSError(
                domain: "SQLiteRuntimeChatEventStoreTests",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: "Could not open SQLite event store."]
            )
        }
        defer { sqlite3_close(database) }

        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(
            database,
            "SELECT event_json FROM runtime_chat_events ORDER BY sequence ASC",
            -1,
            &statement,
            nil
        ) == SQLITE_OK,
              let statement else {
            throw NSError(
                domain: "SQLiteRuntimeChatEventStoreTests",
                code: 2,
                userInfo: [NSLocalizedDescriptionKey: "Could not prepare SQLite event read."]
            )
        }
        defer { sqlite3_finalize(statement) }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        var events: [RuntimeChatStoredEvent] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw NSError(
                    domain: "SQLiteRuntimeChatEventStoreTests",
                    code: 3,
                    userInfo: [NSLocalizedDescriptionKey: "Could not step SQLite event read."]
                )
            }
            let text = try XCTUnwrap(sqlite3_column_text(statement, 0))
            let data = Data(String(cString: text).utf8)
            events.append(try decoder.decode(RuntimeChatStoredEvent.self, from: data))
        }
        return events
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
