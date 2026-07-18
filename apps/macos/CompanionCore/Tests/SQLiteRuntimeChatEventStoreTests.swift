@testable import CompanionCore
import OllamaBackend
import SQLite3
import XCTest

final class SQLiteRuntimeChatEventStoreTests: XCTestCase {
    func testTargetedSessionSummariesMatchJSONLAndSQLiteAcrossBatchesArchiveAndOwnerScope() throws {
        let jsonlStore = JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL())
        let sqliteStore = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
        let stores: [any RuntimeChatEventStore] = [jsonlStore, sqliteStore]
        let events = [
            RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: 100),
                kind: .request,
                requestID: "target-active-request",
                sessionID: "target-active",
                model: "owner-a-active",
                messages: [ChatMessage(role: "user", content: "active")],
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: 101),
                kind: .done,
                requestID: "target-active-request",
                sessionID: "target-active",
                model: "owner-a-active",
                finishReason: "stop",
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: 200),
                kind: .request,
                requestID: "target-archived-request",
                sessionID: "target-archived",
                model: "owner-a-archived",
                messages: [ChatMessage(role: "user", content: "archived")],
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: 201),
                kind: .done,
                requestID: "target-archived-request",
                sessionID: "target-archived",
                model: "owner-a-archived",
                finishReason: "stop",
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: 202),
                kind: .archived,
                requestID: "target-archived-mutation",
                sessionID: "target-archived",
                model: "owner-a-archived",
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: 10_000),
                kind: .request,
                requestID: "unrelated-request",
                sessionID: "unrelated-newer",
                model: "unrelated",
                messages: [ChatMessage(role: "user", content: "unrelated")],
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: 20_000),
                kind: .request,
                requestID: "other-owner-request",
                sessionID: "target-active",
                model: "owner-b-active",
                messages: [ChatMessage(role: "user", content: "other owner")],
                ownerDeviceID: "device-b"
            ),
        ]
        for store in stores {
            for event in events {
                try store.append(event)
            }
        }

        let requestedIDs = ["target-active", "target-archived"]
            + (0..<999).map { "missing-target-\($0)" }
        let jsonlIncludingArchived = try jsonlStore.listSessionSummaries(
            ownerDeviceID: "device-a",
            sessionIDs: requestedIDs,
            includeArchived: true
        )
        let sqliteIncludingArchived = try sqliteStore.listSessionSummaries(
            ownerDeviceID: "device-a",
            sessionIDs: requestedIDs,
            includeArchived: true
        )
        XCTAssertEqual(sqliteIncludingArchived, jsonlIncludingArchived)
        XCTAssertEqual(jsonlIncludingArchived.map(\.sessionID), ["target-archived", "target-active"])
        XCTAssertFalse(jsonlIncludingArchived.map(\.sessionID).contains("unrelated-newer"))

        for store in stores {
            XCTAssertEqual(
                try store.listSessionSummaries(
                    ownerDeviceID: "device-a",
                    sessionIDs: requestedIDs,
                    includeArchived: false
                ).map(\.sessionID),
                ["target-active"]
            )
            let otherOwner = try store.listSessionSummaries(
                ownerDeviceID: "device-b",
                sessionIDs: ["target-active"],
                includeArchived: true
            )
            XCTAssertEqual(otherOwner.map(\.sessionID), ["target-active"])
            XCTAssertEqual(otherOwner.map(\.model), ["owner-b-active"])
        }
    }

    func testTargetedSessionSummaryInputBoundsFailClosedForJSONLAndSQLite() throws {
        let stores: [any RuntimeChatEventStore] = [
            JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL()),
            SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL()),
        ]
        let maximum = RuntimeChatEventStoreLimits.maximumTargetedSessionSummaryCount
        let maximumIDs = (0..<maximum).map { "bounded-target-\($0)" }
        let overboundIDs = maximumIDs + ["bounded-target-overflow"]
        let maximumBackingSessionIDCharacters = RuntimeResearchNotebook.maximumBackingSessionIDCharacters
        let maximumBackingSessionIDUTF8Bytes = RuntimeResearchNotebook.maximumBackingSessionIDUTF8Bytes
        let maximumWidthScalar = "\u{1F600}"
        let exactUTF8BoundaryID = String(
            repeating: maximumWidthScalar,
            count: maximumBackingSessionIDCharacters
        )
        XCTAssertEqual(exactUTF8BoundaryID.unicodeScalars.count, maximumBackingSessionIDCharacters)
        XCTAssertEqual(exactUTF8BoundaryID.utf8.count, maximumBackingSessionIDUTF8Bytes)
        let invalidSessionIDs: [(label: String, sessionID: String)] = [
            ("blank", " \n\t"),
            ("leading whitespace mutation", " target-session"),
            ("trailing whitespace mutation", "target-session "),
            ("control character", "target\u{0000}session"),
            ("non-NFC", "cafe\u{0301}-session"),
            (
                "character bound",
                String(repeating: "a", count: maximumBackingSessionIDCharacters + 1)
            ),
            (
                "UTF-8 byte bound",
                String(repeating: maximumWidthScalar, count: maximumBackingSessionIDCharacters + 1)
            ),
        ]

        for store in stores {
            XCTAssertTrue(try store.listSessionSummaries(
                ownerDeviceID: "device-a",
                sessionIDs: [],
                includeArchived: true
            ).isEmpty)
            XCTAssertTrue(try store.listSessionSummaries(
                ownerDeviceID: "device-a",
                sessionIDs: maximumIDs,
                includeArchived: true
            ).isEmpty)
            XCTAssertTrue(try store.listSessionSummaries(
                ownerDeviceID: "device-a",
                sessionIDs: ["caf\u{00E9}-session", exactUTF8BoundaryID],
                includeArchived: true
            ).isEmpty)
            XCTAssertThrowsError(try store.listSessionSummaries(
                ownerDeviceID: "device-a",
                sessionIDs: overboundIDs,
                includeArchived: true
            )) { error in
                XCTAssertEqual(
                    error as? RuntimeChatEventStoreError,
                    .targetedSessionSummaryLimitExceeded(maximum: maximum)
                )
            }
            XCTAssertThrowsError(try store.listSessionSummaries(
                ownerDeviceID: "device-a",
                sessionIDs: ["duplicate", "duplicate"],
                includeArchived: true
            )) { error in
                XCTAssertEqual(error as? RuntimeChatEventStoreError, .duplicateTargetedSessionSummarySessionID)
            }
            for invalidSessionID in invalidSessionIDs {
                XCTAssertThrowsError(try store.listSessionSummaries(
                    ownerDeviceID: "device-a",
                    sessionIDs: [invalidSessionID.sessionID],
                    includeArchived: true
                ), invalidSessionID.label) { error in
                    XCTAssertEqual(
                        error as? RuntimeChatEventStoreError,
                        .invalidTargetedSessionSummarySessionID,
                        invalidSessionID.label
                    )
                }
            }
        }
    }

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

    func testSQLiteStorePreservesAndRevalidatesAdaptiveV3SourceFingerprint() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let messages = [
            ChatMessage(role: "user", content: "Bound source question."),
            ChatMessage(
                role: "assistant",
                content: "Bound source answer.",
                attachments: [ChatAttachment(
                    type: "document",
                    mimeType: "text/markdown",
                    name: "source.md",
                    text: "Stored attachment text."
                )]
            ),
            ChatMessage(role: "user", content: "Retained question."),
            ChatMessage(role: "assistant", content: "Retained answer."),
        ]
        var pointer = RuntimeChatCompactionSourcePointer(
            sessionID: "sqlite-v3-compaction-session",
            requestID: "sqlite-v3-compaction-request",
            startTurn: 1,
            endTurn: 2,
            totalTurns: 4,
            compactedTurnCount: 2,
            retainedStartTurn: 3,
            retainedEndTurn: 4,
            retainedTurnCount: 2
        )
        let fingerprint = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: Array(messages.prefix(2))
        )
        pointer.sourceFingerprintAlgorithm = fingerprint.algorithm
        pointer.sourceFingerprint = fingerprint.digest
        pointer.sourceCanonicalByteCount = fingerprint.canonicalByteCount
        let metadata = RuntimeChatCompactionMetadata(
            strategy: "adaptive_backend_only_summary_v3",
            sourcePointers: [pointer],
            estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
            contextWindowTokens: 8_192,
            outputReserveTokens: 1_024,
            inputBudgetTokens: 7_168,
            estimatedInputTokensBefore: 8_500,
            estimatedInputTokensAfter: 6_900,
            estimateKind: "planned_upper_bound",
            summaryPolicy: "llm_prepass_with_deterministic_fallback_v1"
        )

        try store.append(RuntimeChatStoredEvent(
            kind: .request,
            requestID: pointer.requestID,
            sessionID: pointer.sessionID,
            model: "ollama:llama3.1:8b",
            messages: messages,
            compactionMetadata: metadata
        ))
        let resolution = RuntimeChatCompactionResolution(
            primaryDispatched: true,
            summaryMethod: "llm_summary_v1",
            estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
            inputBudgetTokens: 7_168,
            estimatedInputTokensAfter: 6_500
        )
        try store.append(RuntimeChatStoredEvent(
            kind: .done,
            requestID: pointer.requestID,
            sessionID: pointer.sessionID,
            model: "ollama:llama3.1:8b",
            finishReason: "stop",
            compactionResolution: resolution
        ))

        let reopened = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try rawSQLiteEvents(at: databaseURL).first?.compactionMetadata,
            metadata
        )
        XCTAssertEqual(
            try rawSQLiteEvents(at: databaseURL).first { $0.kind == .done }?.compactionResolution,
            resolution
        )
        XCTAssertEqual(
            try reopened.listMessages(sessionID: pointer.sessionID, limit: 10).map(\.content),
            messages.map(\.content)
        )
        XCTAssertTrue(
            try reopened.listSessions(
                ownerDeviceID: nil,
                limit: 10,
                includeArchived: true,
                query: fingerprint.digest
            ).isEmpty
        )
        XCTAssertTrue(
            try reopened.listSessions(
                ownerDeviceID: nil,
                limit: 10,
                includeArchived: true,
                query: "llm_summary_v1"
            ).isEmpty
        )
    }

    func testJSONLStoreRevalidatesAdaptiveV3SourceFingerprintAfterReopen() throws {
        let fileURL = try temporaryJSONLURL()
        let messages = [
            ChatMessage(role: "user", content: "JSONL bound source."),
            ChatMessage(role: "assistant", content: "JSONL bound answer."),
            ChatMessage(role: "user", content: "JSONL retained question."),
        ]
        var pointer = RuntimeChatCompactionSourcePointer(
            sessionID: "jsonl-v3-session",
            requestID: "jsonl-v3-request",
            startTurn: 1,
            endTurn: 2,
            totalTurns: 3,
            compactedTurnCount: 2,
            retainedStartTurn: 3,
            retainedEndTurn: 3,
            retainedTurnCount: 1
        )
        let fingerprint = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: Array(messages.prefix(2))
        )
        pointer.sourceFingerprintAlgorithm = fingerprint.algorithm
        pointer.sourceFingerprint = fingerprint.digest
        pointer.sourceCanonicalByteCount = fingerprint.canonicalByteCount
        let metadata = RuntimeChatCompactionMetadata(
            strategy: "adaptive_backend_only_summary_v3",
            sourcePointers: [pointer],
            estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
            contextWindowTokens: 8_192,
            outputReserveTokens: 1_024,
            inputBudgetTokens: 7_168,
            estimatedInputTokensBefore: 8_500,
            estimatedInputTokensAfter: 6_900,
            estimateKind: "planned_upper_bound",
            summaryPolicy: "llm_prepass_with_deterministic_fallback_v1"
        )
        let event = RuntimeChatStoredEvent(
            kind: .request,
            requestID: pointer.requestID,
            sessionID: pointer.sessionID,
            model: "ollama:llama3.1:8b",
            messages: messages,
            compactionMetadata: metadata
        )
        try JSONLRuntimeChatEventStore(fileURL: fileURL).append(event)
        let resolution = RuntimeChatCompactionResolution(
            primaryDispatched: true,
            summaryMethod: "deterministic_preview_v1",
            estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
            inputBudgetTokens: 7_168,
            estimatedInputTokensAfter: 6_900
        )
        try JSONLRuntimeChatEventStore(fileURL: fileURL).append(RuntimeChatStoredEvent(
            kind: .done,
            requestID: pointer.requestID,
            sessionID: pointer.sessionID,
            model: "ollama:llama3.1:8b",
            finishReason: "stop",
            compactionResolution: resolution
        ))
        XCTAssertEqual(
            try JSONLRuntimeChatEventStore(fileURL: fileURL)
                .listMessages(sessionID: pointer.sessionID, limit: 10)
                .map(\.content),
            messages.map(\.content)
        )
        XCTAssertEqual(
            try JSONLRuntimeChatEventStore.events(from: fileURL)
                .first { $0.kind == .done }?.compactionResolution,
            resolution
        )

        let tamperedURL = try temporaryJSONLURL()
        var tamperedEvent = event
        tamperedEvent.messages?[0].content = "Tampered JSONL source."
        try writeRawLegacyEvents([tamperedEvent], to: tamperedURL)
        XCTAssertThrowsError(
            try JSONLRuntimeChatEventStore(fileURL: tamperedURL)
                .listMessages(sessionID: pointer.sessionID, limit: 10)
        ) { error in
            XCTAssertEqual(
                error as? RuntimeChatEventStoreError,
                .corruptEventLog(
                    line: 1,
                    reason: "chat compaction source fingerprint does not match the request event"
                )
            )
        }
    }

    func testSQLiteStoreRejectsInvalidOrMismatchedAdaptiveV3SourceFingerprint() throws {
        let messages = [
            ChatMessage(role: "user", content: "Original source question."),
            ChatMessage(role: "assistant", content: "Original source answer."),
            ChatMessage(role: "user", content: "Retained question."),
        ]
        func validPointer() -> RuntimeChatCompactionSourcePointer {
            var pointer = RuntimeChatCompactionSourcePointer(
                sessionID: "sqlite-invalid-v3-session",
                requestID: "sqlite-invalid-v3-request",
                startTurn: 1,
                endTurn: 2,
                totalTurns: 3,
                compactedTurnCount: 2,
                retainedStartTurn: 3,
                retainedEndTurn: 3,
                retainedTurnCount: 1
            )
            let fingerprint = RuntimeChatCompactionSourceFingerprinter.fingerprint(
                pointer: pointer,
                messages: Array(messages.prefix(2))
            )
            pointer.sourceFingerprintAlgorithm = fingerprint.algorithm
            pointer.sourceFingerprint = fingerprint.digest
            pointer.sourceCanonicalByteCount = fingerprint.canonicalByteCount
            return pointer
        }
        func event(
            pointer: RuntimeChatCompactionSourcePointer,
            messages eventMessages: [ChatMessage] = messages,
            strategy: String = "adaptive_backend_only_summary_v3",
            summaryPolicy: String? = nil
        ) -> RuntimeChatStoredEvent {
            RuntimeChatStoredEvent(
                kind: .request,
                requestID: "sqlite-invalid-v3-request",
                sessionID: "sqlite-invalid-v3-session",
                model: "ollama:llama3.1:8b",
                messages: eventMessages,
                compactionMetadata: RuntimeChatCompactionMetadata(
                    strategy: strategy,
                    sourcePointers: [pointer],
                    estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
                    contextWindowTokens: 8_192,
                    outputReserveTokens: 1_024,
                    inputBudgetTokens: 7_168,
                    estimatedInputTokensBefore: 8_500,
                    estimatedInputTokensAfter: 6_900,
                    estimateKind: strategy == "adaptive_backend_only_summary_v3"
                        ? "planned_upper_bound"
                        : nil,
                    summaryPolicy: strategy == "adaptive_backend_only_summary_v3"
                        ? (summaryPolicy ?? "llm_prepass_with_deterministic_fallback_v1")
                        : nil
                )
            )
        }

        for policy in [
            "llm_prepass_with_deterministic_fallback_v1",
            "llm_prepass_with_incremental_lineage_v2",
        ] {
            let databaseURL = try temporaryDatabaseURL()
            let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
            let validEvent = event(pointer: validPointer(), summaryPolicy: policy)
            XCTAssertNoThrow(try store.append(validEvent))
            XCTAssertEqual(
                try rawSQLiteEvents(at: databaseURL).first?.compactionMetadata?.summaryPolicy,
                policy
            )
        }

        var partial = validPointer()
        partial.sourceCanonicalByteCount = nil
        var unknownAlgorithm = validPointer()
        unknownAlgorithm.sourceFingerprintAlgorithm = "sha256"
        var uppercaseDigest = validPointer()
        uppercaseDigest.sourceFingerprint = uppercaseDigest.sourceFingerprint?.uppercased()
        var wrongByteCount = validPointer()
        wrongByteCount.sourceCanonicalByteCount = (wrongByteCount.sourceCanonicalByteCount ?? 0) + 1
        var wrongDigest = validPointer()
        wrongDigest.sourceFingerprint = String(repeating: "0", count: 64)
        var wrongTotal = validPointer()
        wrongTotal.totalTurns = 4
        wrongTotal.retainedEndTurn = 4
        wrongTotal.retainedTurnCount = 2
        let extremePointer = RuntimeChatCompactionSourcePointer(
            sessionID: "sqlite-invalid-v3-session",
            requestID: "sqlite-invalid-v3-request",
            startTurn: 1,
            endTurn: Int.max,
            totalTurns: Int.max,
            compactedTurnCount: Int.max,
            retainedTurnCount: 0
        )
        let tamperedMessages = [
            ChatMessage(role: "user", content: "Tampered source question."),
            messages[1],
            messages[2],
        ]

        let invalid: [(RuntimeChatStoredEvent, String)] = [
            (event(pointer: partial), "chat compaction source fingerprint fields must be all present or all absent"),
            (event(pointer: unknownAlgorithm), "chat compaction source fingerprint is invalid"),
            (event(pointer: uppercaseDigest), "chat compaction source fingerprint is invalid"),
            (event(pointer: wrongByteCount), "chat compaction source fingerprint does not match the request event"),
            (event(pointer: wrongDigest), "chat compaction source fingerprint does not match the request event"),
            (event(
                pointer: wrongDigest,
                strategy: "adaptive_backend_only_summary_v2"
            ), "chat compaction source fingerprint does not match the request event"),
            (event(pointer: wrongTotal), "chat compaction source turns do not match the request event"),
            (event(pointer: extremePointer), "adaptive chat compaction source pointer is inconsistent with request event"),
            (event(pointer: validPointer(), messages: tamperedMessages), "chat compaction source fingerprint does not match the request event"),
            (event(
                pointer: validPointer(),
                summaryPolicy: "llm_prepass_with_unregistered_policy_v99"
            ), "adaptive v3 chat compaction estimate policy is invalid"),
        ]
        for (invalidEvent, reason) in invalid {
            let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
            XCTAssertThrowsError(try store.append(invalidEvent), reason) { error in
                XCTAssertEqual(
                    error as? RuntimeChatEventStoreError,
                    .corruptEventLog(line: 0, reason: reason)
                )
            }
        }
    }

    func testStoresRejectInvalidCompactionResolutionShapes() throws {
        func event(
            kind: RuntimeChatStoredEventKind,
            resolution: RuntimeChatCompactionResolution
        ) -> RuntimeChatStoredEvent {
            RuntimeChatStoredEvent(
                kind: kind,
                requestID: "invalid-resolution-request",
                sessionID: "invalid-resolution-session",
                model: "ollama:llama3.1:8b",
                messages: kind == .request
                    ? [ChatMessage(role: "user", content: "Visible request.")]
                    : nil,
                finishReason: kind == .done ? "stop" : (kind == .cancelled ? "cancelled" : nil),
                compactionResolution: resolution
            )
        }
        let validDispatched = RuntimeChatCompactionResolution(
            primaryDispatched: true,
            summaryMethod: "llm_summary_v1",
            estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
            inputBudgetTokens: 7_168,
            estimatedInputTokensAfter: 6_500
        )
        let invalid: [(RuntimeChatStoredEvent, String)] = [
            (
                event(kind: .request, resolution: validDispatched),
                "chat compaction resolution is only valid on terminal events"
            ),
            (
                event(kind: .done, resolution: RuntimeChatCompactionResolution(
                    primaryDispatched: true,
                    estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
                    inputBudgetTokens: 7_168,
                    estimatedInputTokensAfter: 6_500
                )),
                "dispatched chat compaction resolution is invalid"
            ),
            (
                event(kind: .done, resolution: RuntimeChatCompactionResolution(
                    primaryDispatched: true,
                    summaryMethod: "llm_summary_v1",
                    estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
                    inputBudgetTokens: 7_168,
                    estimatedInputTokensAfter: 7_169
                )),
                "dispatched chat compaction resolution is invalid"
            ),
            (
                event(kind: .cancelled, resolution: RuntimeChatCompactionResolution(
                    primaryDispatched: false,
                    summaryMethod: "deterministic_preview_v1",
                    estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
                    inputBudgetTokens: 7_168
                )),
                "undispatched chat compaction resolution is invalid"
            ),
            (
                event(kind: .done, resolution: RuntimeChatCompactionResolution(
                    primaryDispatched: false,
                    estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
                    inputBudgetTokens: 7_168
                )),
                "undispatched chat compaction resolution is invalid"
            ),
            (
                event(kind: .cancelled, resolution: RuntimeChatCompactionResolution(
                    primaryDispatched: false,
                    estimatorIdentifier: "  ",
                    inputBudgetTokens: 7_168
                )),
                "chat compaction resolution estimator identifier is empty"
            ),
            (
                event(kind: .cancelled, resolution: RuntimeChatCompactionResolution(
                    primaryDispatched: false,
                    estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
                    inputBudgetTokens: 0
                )),
                "chat compaction resolution input budget is invalid"
            ),
            (
                event(kind: .done, resolution: RuntimeChatCompactionResolution(
                    primaryDispatched: true,
                    summaryMethod: "llm_summary_v1",
                    estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
                    inputBudgetTokens: 7_168,
                    estimatedInputTokensAfter: 6_500,
                    resolvedProviderQualifiedModelID: "ollama:llama3.1:8b:latest"
                )),
                "chat compaction resolved provider model binding is invalid"
            ),
        ]
        for (invalidEvent, reason) in invalid {
            let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
            XCTAssertThrowsError(try store.append(invalidEvent), reason) { error in
                XCTAssertEqual(
                    error as? RuntimeChatEventStoreError,
                    .corruptEventLog(line: 0, reason: reason)
                )
            }
        }
    }

    func testStoresRoundTripProviderUsageCalibration() throws {
        let fixture = adaptiveV3CompactionFixture()
        var resolution = fixture.resolution
        resolution.resolvedProviderQualifiedModelID = "ollama:llama3.1:8b"
        resolution.providerUsageCalibration = RuntimeChatProviderUsageCalibration(
            provider: "ollama",
            providerModelID: "llama3.1:8b",
            wireMode: "ollama_chat",
            inputTokens: 6_000,
            relation: .withinConservativeEstimate
        )
        let terminal = RuntimeChatStoredEvent(
            kind: .done,
            requestID: fixture.request.requestID,
            sessionID: fixture.request.sessionID,
            model: fixture.request.model,
            finishReason: "stop",
            usage: RuntimeChatStoredUsage(inputTokens: 6_000, outputTokens: 320),
            ownerDeviceID: fixture.request.ownerDeviceID,
            compactionResolution: resolution
        )
        let stores: [any RuntimeChatEventStore] = [
            JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL()),
            SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL()),
        ]

        for store in stores {
            try store.append(fixture.request)
            try store.append(terminal)
        }
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(
            RuntimeChatStoredEvent.self,
            from: encoder.encode(terminal)
        )
        XCTAssertEqual(
            decoded.compactionResolution?.providerUsageCalibration,
            resolution.providerUsageCalibration
        )
    }

    func testStoresExposeAggregateOnlyCompactionCalibrationReportAfterReopen() throws {
        let fixture = adaptiveV3CompactionFixture()
        var resolution = fixture.resolution
        resolution.resolvedProviderQualifiedModelID = "ollama:llama3.1:8b"
        resolution.providerUsageCalibration = RuntimeChatProviderUsageCalibration(
            provider: "ollama",
            providerModelID: "llama3.1:8b",
            wireMode: "ollama_chat",
            inputTokens: 6_600,
            relation: .exceededConservativeEstimateWithinBudget
        )
        let terminal = RuntimeChatStoredEvent(
            kind: .done,
            requestID: fixture.request.requestID,
            sessionID: fixture.request.sessionID,
            model: fixture.request.model,
            finishReason: "stop",
            usage: RuntimeChatStoredUsage(inputTokens: 6_600, outputTokens: 320),
            ownerDeviceID: fixture.request.ownerDeviceID,
            compactionResolution: resolution
        )

        func appendFixture(to store: any RuntimeChatEventStore) throws {
            try store.append(fixture.request)
            try store.append(terminal)
        }
        func assertReport(from store: any RuntimeChatEventStore) throws {
            let report = try store.chatCompactionCalibrationReport()
            XCTAssertEqual(report.sampledEligibleCount, 1)
            XCTAssertEqual(report.reportedSampleCount, 1)
            XCTAssertEqual(report.omittedSampleCount, 0)
            let group = try XCTUnwrap(report.groups.first)
            XCTAssertEqual(group.provider, "ollama")
            XCTAssertEqual(group.providerModelID, "llama3.1:8b")
            XCTAssertEqual(group.wireMode, "ollama_chat")
            XCTAssertEqual(
                group.estimatorIdentifier,
                "conservative_utf8_bytes_vision_framing_v2"
            )
            XCTAssertEqual(group.sampleCount, 1)
            XCTAssertEqual(group.withinConservativeEstimateCount, 0)
            XCTAssertEqual(group.exceededConservativeEstimateWithinBudgetCount, 1)
            XCTAssertEqual(group.exceededInputBudgetCount, 0)
            XCTAssertEqual(group.status, .collecting)
        }

        let jsonlURL = try temporaryJSONLURL()
        try appendFixture(to: JSONLRuntimeChatEventStore(fileURL: jsonlURL))
        try assertReport(from: JSONLRuntimeChatEventStore(fileURL: jsonlURL))

        let sqliteURL = try temporaryDatabaseURL()
        try appendFixture(to: SQLiteRuntimeChatEventStore(databaseURL: sqliteURL))
        try assertReport(from: SQLiteRuntimeChatEventStore(databaseURL: sqliteURL))
    }

    func testStoresRejectInvalidProviderUsageCalibrationShapes() throws {
        func event(
            kind: RuntimeChatStoredEventKind = .done,
            usageInputTokens: Int? = 6_000,
            calibration: RuntimeChatProviderUsageCalibration
        ) -> RuntimeChatStoredEvent {
            RuntimeChatStoredEvent(
                kind: kind,
                requestID: "invalid-calibration-request",
                sessionID: "invalid-calibration-session",
                model: "ollama:llama3.1:8b",
                finishReason: kind == .done ? "stop" : "cancelled",
                usage: RuntimeChatStoredUsage(inputTokens: usageInputTokens, outputTokens: 100),
                compactionResolution: RuntimeChatCompactionResolution(
                    primaryDispatched: true,
                    summaryMethod: "llm_summary_v1",
                    estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
                    inputBudgetTokens: 7_168,
                    estimatedInputTokensAfter: 6_500,
                    resolvedProviderQualifiedModelID: "ollama:llama3.1:8b",
                    providerUsageCalibration: calibration
                )
            )
        }
        let valid = RuntimeChatProviderUsageCalibration(
            provider: "ollama",
            providerModelID: "llama3.1:8b",
            wireMode: "ollama_chat",
            inputTokens: 6_000,
            relation: .withinConservativeEstimate
        )
        let invalid: [(RuntimeChatStoredEvent, String)] = [
            (
                event(kind: .cancelled, calibration: valid),
                "chat provider usage calibration is invalid"
            ),
            (
                event(usageInputTokens: 5_999, calibration: valid),
                "chat provider usage calibration is invalid"
            ),
            (
                event(calibration: RuntimeChatProviderUsageCalibration(
                    provider: "ollama",
                    providerModelID: "llama3.1:8b",
                    wireMode: "lmstudio_native",
                    inputTokens: 6_000,
                    relation: .withinConservativeEstimate
                )),
                "chat provider usage calibration is invalid"
            ),
            (
                event(calibration: RuntimeChatProviderUsageCalibration(
                    provider: "lm_studio",
                    providerModelID: "llama3.1:8b",
                    wireMode: "lmstudio_native",
                    inputTokens: 6_000,
                    relation: .withinConservativeEstimate
                )),
                "chat provider usage calibration is invalid"
            ),
            (
                event(calibration: RuntimeChatProviderUsageCalibration(
                    provider: "ollama",
                    providerModelID: "llama3.1:8b:latest",
                    wireMode: "ollama_chat",
                    inputTokens: 6_000,
                    relation: .withinConservativeEstimate
                )),
                "chat provider usage calibration is invalid"
            ),
            (
                event(calibration: RuntimeChatProviderUsageCalibration(
                    countSource: "provider_usage_calibration_v0",
                    provider: "ollama",
                    providerModelID: "llama3.1:8b",
                    wireMode: "ollama_chat",
                    inputTokens: 6_000,
                    relation: .withinConservativeEstimate
                )),
                "chat provider usage calibration is invalid"
            ),
            (
                event(usageInputTokens: 6_600, calibration: RuntimeChatProviderUsageCalibration(
                    provider: "ollama",
                    providerModelID: "llama3.1:8b",
                    wireMode: "ollama_chat",
                    inputTokens: 6_600,
                    relation: .withinConservativeEstimate
                )),
                "chat provider usage calibration relation does not match request accounting"
            ),
        ]

        for (invalidEvent, reason) in invalid {
            let store = SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
            XCTAssertThrowsError(try store.append(invalidEvent), reason) { error in
                XCTAssertEqual(
                    error as? RuntimeChatEventStoreError,
                    .corruptEventLog(line: 0, reason: reason)
                )
            }
        }
    }

    func testStoresBindCompactionResolutionToAdaptiveV3RequestAccounting() throws {
        let fixture = adaptiveV3CompactionFixture()
        let terminal = RuntimeChatStoredEvent(
            kind: .done,
            requestID: fixture.request.requestID,
            sessionID: fixture.request.sessionID,
            model: fixture.request.model,
            finishReason: "stop",
            ownerDeviceID: fixture.request.ownerDeviceID,
            compactionResolution: fixture.resolution
        )
        func stores() throws -> [any RuntimeChatEventStore] {
            [
                JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL()),
                SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL()),
            ]
        }
        func assertRejected(
            by store: any RuntimeChatEventStore,
            event: RuntimeChatStoredEvent,
            reason: String
        ) {
            XCTAssertThrowsError(try store.append(event), reason) { error in
                XCTAssertEqual(
                    error as? RuntimeChatEventStoreError,
                    .corruptEventLog(line: 0, reason: reason)
                )
            }
        }

        for store in try stores() {
            assertRejected(
                by: store,
                event: terminal,
                reason: "chat compaction resolution is not bound to an adaptive v3 request"
            )
        }

        var nonCompactedRequest = fixture.request
        nonCompactedRequest.compactionMetadata = nil
        for store in try stores() {
            try store.append(nonCompactedRequest)
            assertRejected(
                by: store,
                event: terminal,
                reason: "chat compaction resolution is not bound to an adaptive v3 request"
            )
        }

        var wrongEstimator = terminal
        wrongEstimator.compactionResolution?.estimatorIdentifier = "different-estimator-v1"
        var wrongBudget = terminal
        wrongBudget.compactionResolution?.inputBudgetTokens -= 1
        for mismatchedTerminal in [wrongEstimator, wrongBudget] {
            for store in try stores() {
                try store.append(fixture.request)
                assertRejected(
                    by: store,
                    event: mismatchedTerminal,
                    reason: "chat compaction resolution does not match request accounting"
                )
            }
        }
    }

    func testStoresRequireDeterministicPreviewEstimateToMatchBoundRequest() throws {
        let fixture = adaptiveV3CompactionFixture()
        var mismatchedResolution = fixture.resolution
        mismatchedResolution.summaryMethod = "deterministic_preview_v1"
        mismatchedResolution.estimatedInputTokensAfter = 6_500
        let mismatchedTerminal = calibratedTerminal(
            request: fixture.request,
            resolution: mismatchedResolution,
            id: "deterministic-mismatch-terminal"
        )
        let reason = "deterministic chat compaction resolution does not match request estimate"

        for store in [
            JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL()) as any RuntimeChatEventStore,
            SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL()),
        ] {
            try store.append(fixture.request)
            XCTAssertThrowsError(try store.append(mismatchedTerminal)) { error in
                XCTAssertEqual(
                    error as? RuntimeChatEventStoreError,
                    .corruptEventLog(line: 0, reason: reason)
                )
            }
        }

        let llmTerminal = calibratedTerminal(
            request: fixture.request,
            resolution: fixture.resolution,
            id: "llm-independent-estimate-terminal"
        )
        for store in [
            JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL()) as any RuntimeChatEventStore,
            SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL()),
        ] {
            try store.append(fixture.request)
            XCTAssertNoThrow(try store.append(llmTerminal))
        }
    }

    func testStoresRejectDeterministicPreviewEstimateMismatchAfterReopenAndReport() throws {
        let fixture = adaptiveV3CompactionFixture()
        var validResolution = fixture.resolution
        validResolution.summaryMethod = "deterministic_preview_v1"
        validResolution.estimatedInputTokensAfter = 6_900
        let validTerminal = calibratedTerminal(
            request: fixture.request,
            resolution: validResolution,
            id: "reopen-deterministic-terminal"
        )
        var mismatchedTerminal = validTerminal
        mismatchedTerminal.compactionResolution?.estimatedInputTokensAfter = 6_500
        let reason = "deterministic chat compaction resolution does not match request estimate"

        let jsonlURL = try temporaryJSONLURL()
        try writeRawLegacyEvents([fixture.request, mismatchedTerminal], to: jsonlURL)
        let jsonlStore = JSONLRuntimeChatEventStore(fileURL: jsonlURL)
        for operation in [
            { try JSONLRuntimeChatEventStore.events(from: jsonlURL).count },
            { try jsonlStore.chatCompactionCalibrationReport().sampledEligibleCount },
        ] {
            XCTAssertThrowsError(try operation()) { error in
                guard case RuntimeChatEventStoreError.corruptEventLog(_, let actualReason) = error else {
                    return XCTFail("Expected corrupt event log, got \(error)")
                }
                XCTAssertEqual(actualReason, reason)
            }
        }

        let sqliteURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
        try sqliteStore.append(fixture.request)
        try sqliteStore.append(validTerminal)
        try replaceRawSQLiteEventJSON(mismatchedTerminal, at: sqliteURL)
        let reopenedSQLiteStore = SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
        for operation in [
            {
                try reopenedSQLiteStore.listSessions(
                    ownerDeviceID: "device-a",
                    limit: 10,
                    includeArchived: true
                ).count
            },
            { try reopenedSQLiteStore.chatCompactionCalibrationReport().sampledEligibleCount },
        ] {
            XCTAssertThrowsError(try operation()) { error in
                guard case RuntimeChatEventStoreError.corruptEventLog(_, let actualReason) = error else {
                    return XCTFail("Expected corrupt event log, got \(error)")
                }
                XCTAssertEqual(actualReason, reason)
            }
        }
    }

    func testStoresRejectDuplicateCompactionTerminalBindingOnAppend() throws {
        let fixture = adaptiveV3CompactionFixture()
        let terminal = calibratedTerminal(
            request: fixture.request,
            resolution: fixture.resolution,
            id: "unique-compaction-terminal"
        )
        var duplicate = terminal
        duplicate.id = "duplicate-compaction-terminal"
        duplicate.ownerDeviceID = "  device-a  "
        let reason = "chat compaction binding has duplicate terminal resolution"

        for store in [
            JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL()) as any RuntimeChatEventStore,
            SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL()),
        ] {
            try store.append(fixture.request)
            try store.append(terminal)
            XCTAssertThrowsError(try store.append(duplicate)) { error in
                XCTAssertEqual(
                    error as? RuntimeChatEventStoreError,
                    .corruptEventLog(line: 0, reason: reason)
                )
            }
        }
    }

    func testStoresRejectDuplicateCompactionTerminalBindingAfterReopenAndReport() throws {
        let fixture = adaptiveV3CompactionFixture()
        let terminal = calibratedTerminal(
            request: fixture.request,
            resolution: fixture.resolution,
            id: "reopen-unique-compaction-terminal"
        )
        var duplicate = terminal
        duplicate.id = "reopen-duplicate-compaction-terminal"
        duplicate.ownerDeviceID = " device-a "
        let reason = "chat compaction binding has duplicate terminal resolution"

        let jsonlURL = try temporaryJSONLURL()
        try writeRawLegacyEvents([fixture.request, terminal, duplicate], to: jsonlURL)
        let jsonlStore = JSONLRuntimeChatEventStore(fileURL: jsonlURL)
        for operation in [
            { try JSONLRuntimeChatEventStore.events(from: jsonlURL).count },
            { try jsonlStore.chatCompactionCalibrationReport().sampledEligibleCount },
        ] {
            XCTAssertThrowsError(try operation()) { error in
                guard case RuntimeChatEventStoreError.corruptEventLog(_, let actualReason) = error else {
                    return XCTFail("Expected corrupt event log, got \(error)")
                }
                XCTAssertEqual(actualReason, reason)
            }
        }

        let sqliteURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
        try sqliteStore.append(fixture.request)
        try sqliteStore.append(terminal)
        var placeholder = duplicate
        placeholder.compactionResolution = nil
        placeholder.usage = nil
        try sqliteStore.append(placeholder)
        try replaceRawSQLiteEventJSON(duplicate, at: sqliteURL)
        let reopenedSQLiteStore = SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
        for operation in [
            {
                try reopenedSQLiteStore.listSessions(
                    ownerDeviceID: "device-a",
                    limit: 10,
                    includeArchived: true
                ).count
            },
            { try reopenedSQLiteStore.chatCompactionCalibrationReport().sampledEligibleCount },
        ] {
            XCTAssertThrowsError(try operation()) { error in
                guard case RuntimeChatEventStoreError.corruptEventLog(_, let actualReason) = error else {
                    return XCTFail("Expected corrupt event log, got \(error)")
                }
                XCTAssertEqual(actualReason, reason)
            }
        }
    }

    func testStoresKeepSessionAndRequestCompactionBindingsExact() throws {
        let fixture = adaptiveV3CompactionFixture()
        let terminal = calibratedTerminal(
            request: fixture.request,
            resolution: fixture.resolution,
            id: "exact-compaction-terminal"
        )
        let reason = "chat compaction resolution is not bound to an adaptive v3 request"

        for mutate in [
            { (event: inout RuntimeChatStoredEvent) in
                event.sessionID = " \(event.sessionID) "
            },
            { (event: inout RuntimeChatStoredEvent) in
                event.requestID = " \(event.requestID) "
            },
        ] {
            for store in [
                JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL()) as any RuntimeChatEventStore,
                SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL()),
            ] {
                var mismatched = terminal
                mismatched.id = UUID().uuidString
                mutate(&mismatched)
                try store.append(fixture.request)
                XCTAssertThrowsError(try store.append(mismatched)) { error in
                    XCTAssertEqual(
                        error as? RuntimeChatEventStoreError,
                        .corruptEventLog(line: 0, reason: reason)
                    )
                }
            }
        }
    }

    func testCalibrationReportsRejectDuplicateBindingWithUncalibratedTerminal() throws {
        let fixture = adaptiveV3CompactionFixture()
        let calibrated = calibratedTerminal(
            request: fixture.request,
            resolution: fixture.resolution,
            id: "duplicate-mixed-calibrated-terminal"
        )
        var uncalibrated = calibrated
        uncalibrated.id = "duplicate-mixed-uncalibrated-terminal"
        uncalibrated.compactionResolution?.providerUsageCalibration = nil
        let reason = "chat compaction binding has duplicate terminal resolution"

        for terminals in [
            [calibrated, uncalibrated],
            [uncalibrated, calibrated],
        ] {
            let jsonlURL = try temporaryJSONLURL()
            try writeRawLegacyEvents([fixture.request] + terminals, to: jsonlURL)
            XCTAssertThrowsError(
                try JSONLRuntimeChatEventStore(fileURL: jsonlURL)
                    .chatCompactionCalibrationReport()
            ) { error in
                guard case RuntimeChatEventStoreError.corruptEventLog(_, let actualReason) = error else {
                    return XCTFail("Expected corrupt JSONL event log, got \(error)")
                }
                XCTAssertEqual(actualReason, reason)
            }

            let sqliteURL = try temporaryDatabaseURL()
            let sqliteStore = SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
            try sqliteStore.append(fixture.request)
            for terminal in terminals {
                var placeholder = terminal
                placeholder.compactionResolution = nil
                placeholder.usage = nil
                try sqliteStore.append(placeholder)
            }
            try replaceRawSQLiteEventJSONs(terminals, at: sqliteURL)
            XCTAssertThrowsError(
                try SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
                    .chatCompactionCalibrationReport()
            ) { error in
                guard case RuntimeChatEventStoreError.corruptEventLog(_, let actualReason) = error else {
                    return XCTFail("Expected corrupt SQLite event log, got \(error)")
                }
                XCTAssertEqual(actualReason, reason)
            }
        }
    }

    func testCalibrationReportStoreLimitsFailClosedOnExhaustion() throws {
        let production = RuntimeChatCompactionCalibrationStoreLimits.production
        XCTAssertEqual(production.jsonlByteCeiling, 64 * 1_024 * 1_024)
        XCTAssertEqual(production.jsonlLineCeiling, 50_000)
        XCTAssertEqual(production.jsonlLineByteCeiling, 4 * 1_024 * 1_024)
        XCTAssertEqual(production.sqliteTerminalScanCeiling, 50_000)

        func doneEvent(_ index: Int) -> RuntimeChatStoredEvent {
            RuntimeChatStoredEvent(
                id: "calibration-limit-event-\(index)",
                kind: .done,
                requestID: "calibration-limit-request-\(index)",
                sessionID: "calibration-limit-session-\(index)",
                model: "ollama:llama3.1:8b",
                finishReason: "stop"
            )
        }

        func assertCorruptReason(
            contains expected: String,
            operation: () throws -> Void
        ) {
            XCTAssertThrowsError(try operation()) { error in
                guard case RuntimeChatEventStoreError.corruptEventLog(_, let reason) = error else {
                    return XCTFail("Expected corrupt event log, got \(error)")
                }
                XCTAssertTrue(reason.contains(expected), "Unexpected reason: \(reason)")
            }
        }

        let lineLimits = RuntimeChatCompactionCalibrationStoreLimits(
            jsonlByteCeiling: 1_024 * 1_024,
            jsonlLineCeiling: 3,
            jsonlLineByteCeiling: 4_096,
            sqliteTerminalScanCeiling: 3
        )
        let lineURL = try temporaryJSONLURL()
        let lineStore = JSONLRuntimeChatEventStore(
            fileURL: lineURL,
            calibrationReportStoreLimits: lineLimits
        )
        for index in 0..<4 {
            try lineStore.append(doneEvent(index))
        }
        assertCorruptReason(contains: "line ceiling") {
            _ = try lineStore.chatCompactionCalibrationReport()
        }

        let byteLimits = RuntimeChatCompactionCalibrationStoreLimits(
            jsonlByteCeiling: 64,
            jsonlLineCeiling: 100,
            jsonlLineByteCeiling: 4_096,
            sqliteTerminalScanCeiling: 3
        )
        let byteStore = JSONLRuntimeChatEventStore(
            fileURL: try temporaryJSONLURL(),
            calibrationReportStoreLimits: byteLimits
        )
        try byteStore.append(doneEvent(10))
        assertCorruptReason(contains: "scan ceiling") {
            _ = try byteStore.chatCompactionCalibrationReport()
        }

        let recordLimits = RuntimeChatCompactionCalibrationStoreLimits(
            jsonlByteCeiling: 4_096,
            jsonlLineCeiling: 100,
            jsonlLineByteCeiling: 64,
            sqliteTerminalScanCeiling: 3
        )
        let recordStore = JSONLRuntimeChatEventStore(
            fileURL: try temporaryJSONLURL(),
            calibrationReportStoreLimits: recordLimits
        )
        try recordStore.append(doneEvent(20))
        assertCorruptReason(contains: "record exceeds the byte ceiling") {
            _ = try recordStore.chatCompactionCalibrationReport()
        }

        let sqliteStore = SQLiteRuntimeChatEventStore(
            databaseURL: try temporaryDatabaseURL(),
            calibrationReportStoreLimits: lineLimits
        )
        for index in 0..<4 {
            try sqliteStore.append(doneEvent(30 + index))
        }
        assertCorruptReason(contains: "SQLite scan exceeds the terminal ceiling") {
            _ = try sqliteStore.chatCompactionCalibrationReport()
        }
    }

    func testCalibrationReportCapCountsFullyEligibleSamplesPastNewerCalibrationShapedRows() throws {
        let sampleCap = RuntimeChatCompactionCalibrationReport.recentEligibleSampleCap
        var requests: [RuntimeChatStoredEvent] = []
        var terminals: [RuntimeChatStoredEvent] = []
        for index in 0..<sampleCap {
            let fixture = calibratedCompactionFixture(index: index)
            requests.append(fixture.request)
            terminals.append(fixture.terminal)
        }
        let newerIneligibleCalibration = (0..<1_100).map { index in
            RuntimeChatStoredEvent(
                id: "newer-ineligible-calibration-\(index)",
                kind: .done,
                requestID: "newer-ineligible-request-\(index)",
                sessionID: "newer-ineligible-session-\(index)",
                model: "ollama:llama3.1:8b",
                finishReason: "stop",
                usage: RuntimeChatStoredUsage(inputTokens: 6_000, outputTokens: 100),
                compactionResolution: RuntimeChatCompactionResolution(
                    primaryDispatched: true,
                    summaryMethod: "llm_summary_v1",
                    estimatorIdentifier: "conservative_utf8_bytes_vision_framing_v2",
                    inputBudgetTokens: 7_168,
                    estimatedInputTokensAfter: 6_500,
                    resolvedProviderQualifiedModelID: "ollama:llama3.1:8b",
                    providerUsageCalibration: RuntimeChatProviderUsageCalibration(
                        provider: "ollama",
                        providerModelID: "llama3.1:8b",
                        wireMode: "ollama_chat",
                        inputTokens: 6_000,
                        relation: .exceededInputBudget
                    )
                )
            )
        }
        let sqlitePlaceholders = newerIneligibleCalibration.map { candidate in
            var placeholder = candidate
            placeholder.usage = nil
            placeholder.compactionResolution = nil
            return placeholder
        }
        let validOldUnrelated = RuntimeChatStoredEvent(
            id: "old-unrelated-event",
            kind: .request,
            requestID: "old-unrelated-request",
            sessionID: "old-unrelated-session",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Old unrelated history.")]
        )
        var invalidOldUnrelated = validOldUnrelated
        invalidOldUnrelated.messages = []

        func assertCappedReport(_ report: RuntimeChatCompactionCalibrationReport) throws {
            XCTAssertEqual(report.sampledEligibleCount, sampleCap)
            XCTAssertEqual(report.reportedSampleCount, sampleCap)
            XCTAssertEqual(report.omittedSampleCount, 0)
            XCTAssertEqual(try XCTUnwrap(report.groups.first).sampleCount, sampleCap)
        }

        let jsonlURL = try temporaryJSONLURL()
        try writeRawLegacyEvents(
            [invalidOldUnrelated] + requests + terminals + newerIneligibleCalibration,
            to: jsonlURL
        )
        try assertCappedReport(
            JSONLRuntimeChatEventStore(fileURL: jsonlURL).chatCompactionCalibrationReport()
        )

        let sqliteURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        try writeRawLegacyEvents(
            [validOldUnrelated] + requests + terminals + sqlitePlaceholders,
            to: legacyURL
        )
        _ = try SQLiteRuntimeChatEventStore(
            databaseURL: sqliteURL,
            legacyJSONLFileURL: legacyURL
        ).listSessions(limit: 1)
        try replaceRawSQLiteEventJSONs(
            [invalidOldUnrelated] + newerIneligibleCalibration,
            at: sqliteURL
        )
        try assertCappedReport(
            SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
                .chatCompactionCalibrationReport()
        )
    }

    func testCalibrationReportsRejectMalformedOrWrongTypeCalibrationPayloads() throws {
        let fixture = calibratedCompactionFixture(index: 0)
        let payloads: [(name: String, value: Any)] = [
            ("wrong-type", "tampered-calibration"),
            ("malformed-object", ["provider": "ollama"]),
        ]

        for payload in payloads {
            let tamperedJSON = try rawEventJSON(
                fixture.terminal,
                replacingCalibrationPayloadWith: payload.value
            )

            let jsonlURL = try temporaryJSONLURL()
            try writeRawLegacyEvents([fixture.request], to: jsonlURL)
            try appendRawLine(tamperedJSON, to: jsonlURL)
            XCTAssertThrowsError(
                try JSONLRuntimeChatEventStore(fileURL: jsonlURL)
                    .chatCompactionCalibrationReport(),
                payload.name
            ) { error in
                guard case RuntimeChatEventStoreError.corruptEventLog = error else {
                    return XCTFail("Expected corrupt JSONL event log, got \(error)")
                }
            }

            let sqliteURL = try temporaryDatabaseURL()
            let sqliteStore = SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
            try sqliteStore.append(fixture.request)
            try sqliteStore.append(fixture.terminal)
            try replaceRawSQLiteEventJSONString(
                eventID: fixture.terminal.id,
                eventJSON: tamperedJSON,
                at: sqliteURL
            )
            XCTAssertThrowsError(
                try SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
                    .chatCompactionCalibrationReport(),
                payload.name
            ) { error in
                guard case RuntimeChatEventStoreError.corruptEventLog = error else {
                    return XCTFail("Expected corrupt SQLite event log, got \(error)")
                }
            }
        }
    }

    func testCalibrationReportsRequireSelectedRequestBinding() throws {
        let fixture = calibratedCompactionFixture(index: 0)
        let reason = "chat compaction resolution is not bound to an adaptive v3 request"

        let jsonlURL = try temporaryJSONLURL()
        try writeRawLegacyEvents([fixture.terminal], to: jsonlURL)
        XCTAssertThrowsError(
            try JSONLRuntimeChatEventStore(fileURL: jsonlURL).chatCompactionCalibrationReport()
        ) { error in
            guard case RuntimeChatEventStoreError.corruptEventLog(_, let actualReason) = error else {
                return XCTFail("Expected corrupt event log, got \(error)")
            }
            XCTAssertEqual(
                actualReason,
                "chat compaction calibration request binding is outside the bounded JSONL tail"
            )
        }

        let sqliteURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
        try sqliteStore.append(fixture.request)
        try sqliteStore.append(fixture.terminal)
        try executeRawSQLite(
            "DELETE FROM runtime_chat_events WHERE event_id = '\(fixture.request.id)'",
            at: sqliteURL
        )
        XCTAssertThrowsError(
            try SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
                .chatCompactionCalibrationReport()
        ) { error in
            guard case RuntimeChatEventStoreError.corruptEventLog(_, let actualReason) = error else {
                return XCTFail("Expected corrupt event log, got \(error)")
            }
            XCTAssertEqual(actualReason, reason)
        }
    }

    func testStoresRejectMismatchedCompactionResolutionAfterReopen() throws {
        let fixture = adaptiveV3CompactionFixture()
        var mismatchedTerminal = RuntimeChatStoredEvent(
            kind: .done,
            requestID: fixture.request.requestID,
            sessionID: fixture.request.sessionID,
            model: fixture.request.model,
            finishReason: "stop",
            ownerDeviceID: fixture.request.ownerDeviceID,
            compactionResolution: fixture.resolution
        )
        mismatchedTerminal.compactionResolution?.inputBudgetTokens -= 1
        let reason = "chat compaction resolution does not match request accounting"

        let jsonlURL = try temporaryJSONLURL()
        try writeRawLegacyEvents([fixture.request, mismatchedTerminal], to: jsonlURL)
        XCTAssertThrowsError(try JSONLRuntimeChatEventStore.events(from: jsonlURL)) { error in
            XCTAssertEqual(
                error as? RuntimeChatEventStoreError,
                .corruptEventLog(line: 2, reason: reason)
            )
        }

        let sqliteURL = try temporaryDatabaseURL()
        let sqliteStore = SQLiteRuntimeChatEventStore(databaseURL: sqliteURL)
        try sqliteStore.append(fixture.request)
        var validTerminal = mismatchedTerminal
        validTerminal.compactionResolution = fixture.resolution
        try sqliteStore.append(validTerminal)
        try replaceRawSQLiteEventJSON(mismatchedTerminal, at: sqliteURL)
        XCTAssertThrowsError(
            try SQLiteRuntimeChatEventStore(databaseURL: sqliteURL).listSessions(
                ownerDeviceID: "device-a",
                limit: 10,
                includeArchived: true
            )
        ) { error in
            XCTAssertEqual(
                error as? RuntimeChatEventStoreError,
                .corruptEventLog(line: 2, reason: reason)
            )
        }
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
            estimatedInputTokensAfter: Int? = 6_900,
            estimateKind: String? = nil,
            summaryPolicy: String? = nil
        ) -> RuntimeChatCompactionMetadata {
            RuntimeChatCompactionMetadata(
                strategy: strategy,
                sourcePointers: sourcePointers ?? [validPointer],
                estimatorIdentifier: estimatorIdentifier,
                contextWindowTokens: contextWindowTokens,
                outputReserveTokens: outputReserveTokens,
                inputBudgetTokens: inputBudgetTokens,
                estimatedInputTokensBefore: estimatedInputTokensBefore,
                estimatedInputTokensAfter: estimatedInputTokensAfter,
                estimateKind: estimateKind,
                summaryPolicy: summaryPolicy
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
                    requestID: "sqlite-invalid-compaction-partial-policy",
                    metadata: accountingMetadata(estimateKind: "planned_upper_bound")
                ),
                "chat compaction estimate policy fields must be all present or all absent"
            ),
            (
                invalidCompactionRequest(
                    requestID: "sqlite-invalid-compaction-v3-policy",
                    metadata: accountingMetadata(
                        strategy: "adaptive_backend_only_summary_v3",
                        estimateKind: "exact_effective_estimate",
                        summaryPolicy: "llm_prepass_with_deterministic_fallback_v1"
                    )
                ),
                "adaptive v3 chat compaction estimate policy is invalid"
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

    func testSQLiteBulkLifecycleProcessesDeterministicBoundedBatchesBeyondFirstPage() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        var events: [RuntimeChatStoredEvent] = (0..<205).map { index in
            RuntimeChatStoredEvent(
                id: String(format: "bulk-a-%03d-event", index),
                timestamp: Date(timeIntervalSince1970: TimeInterval(1_000 + index)),
                kind: .request,
                requestID: String(format: "bulk-a-%03d-turn", index),
                sessionID: String(format: "bulk-a-%03d", index),
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Bulk owner A \(index)")],
                ownerDeviceID: "device-a"
            )
        }
        events.append(contentsOf: (0..<3).map { index in
            RuntimeChatStoredEvent(
                id: "bulk-b-\(index)-event",
                timestamp: Date(timeIntervalSince1970: TimeInterval(2_000 + index)),
                kind: .request,
                requestID: "bulk-b-\(index)-turn",
                sessionID: "bulk-b-\(index)",
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Bulk owner B \(index)")],
                ownerDeviceID: "device-b"
            )
        })
        try writeRawLegacyEvents(events, to: legacyURL)
        let store = SQLiteRuntimeChatEventStore(
            databaseURL: databaseURL,
            legacyJSONLFileURL: legacyURL
        )
        XCTAssertEqual(
            try store.listSessions(
                ownerDeviceID: "device-a",
                limit: Int.max,
                includeArchived: true
            ).count,
            205
        )

        let firstArchive = try store.mutateSessions(
            ownerDeviceID: "device-a",
            scope: .allActive,
            limit: 120,
            requestID: "bulk-archive-1",
            timestamp: Date(timeIntervalSince1970: 3_000)
        )
        XCTAssertEqual(firstArchive.affectedCount, 120)
        XCTAssertEqual(firstArchive.remainingCount, 85)
        XCTAssertEqual(
            firstArchive.affectedSessionIDs,
            (85..<205).reversed().map { String(format: "bulk-a-%03d", $0) }
        )

        let secondArchive = try store.mutateSessions(
            ownerDeviceID: "device-a",
            scope: .allActive,
            limit: 200,
            requestID: "bulk-archive-2",
            timestamp: Date(timeIntervalSince1970: 3_001)
        )
        XCTAssertEqual(secondArchive.affectedCount, 85)
        XCTAssertEqual(secondArchive.remainingCount, 0)
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: Int.max, includeArchived: true).count,
            205
        )

        let firstDelete = try store.mutateSessions(
            ownerDeviceID: "device-a",
            scope: .allArchived,
            limit: 200,
            requestID: "bulk-delete-1",
            timestamp: Date(timeIntervalSince1970: 3_002)
        )
        XCTAssertEqual(firstDelete.affectedCount, 200)
        XCTAssertEqual(firstDelete.remainingCount, 5)
        let finalDelete = try store.mutateSessions(
            ownerDeviceID: "device-a",
            scope: .allArchived,
            limit: 200,
            requestID: "bulk-delete-2",
            timestamp: Date(timeIntervalSince1970: 3_003)
        )
        XCTAssertEqual(finalDelete.affectedCount, 5)
        XCTAssertEqual(finalDelete.remainingCount, 0)
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: Int.max, includeArchived: true).isEmpty
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-b", limit: Int.max, includeArchived: true)
                .map(\.sessionID),
            ["bulk-b-2", "bulk-b-1", "bulk-b-0"]
        )
    }

    func testJSONLBulkLifecycleHoldsOwnerScopedDeterministicBatchState() throws {
        let store = JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL())
        for (owner, sessionID, timestamp) in [
            ("device-a", "jsonl-a-old", 10.0),
            ("device-a", "jsonl-a-new", 20.0),
            ("device-a", "jsonl-a-new-tie", 20.0),
            ("device-b", "jsonl-b", 30.0),
        ] {
            try store.append(RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: timestamp),
                kind: .request,
                requestID: "\(sessionID)-turn",
                sessionID: sessionID,
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: sessionID)],
                ownerDeviceID: owner
            ))
        }

        let first = try store.mutateSessions(
            ownerDeviceID: "device-a",
            scope: .allActive,
            limit: 2,
            requestID: "jsonl-bulk-archive-1",
            timestamp: Date(timeIntervalSince1970: 40)
        )
        XCTAssertEqual(first.affectedSessionIDs, ["jsonl-a-new", "jsonl-a-new-tie"])
        XCTAssertEqual(first.remainingCount, 1)
        let second = try store.mutateSessions(
            ownerDeviceID: "device-a",
            scope: .allActive,
            limit: 2,
            requestID: "jsonl-bulk-archive-2",
            timestamp: Date(timeIntervalSince1970: 41)
        )
        XCTAssertEqual(second.affectedSessionIDs, ["jsonl-a-old"])
        XCTAssertEqual(second.remainingCount, 0)
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-b", limit: 10, includeArchived: true)
                .map(\.sessionID),
            ["jsonl-b"]
        )
    }

    func testSQLiteBulkLifecycleRollsBackEntireBatchOnInsertFailure() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        for index in 0..<3 {
            try store.append(RuntimeChatStoredEvent(
                timestamp: Date(timeIntervalSince1970: TimeInterval(100 + index)),
                kind: .request,
                requestID: "rollback-\(index)-turn",
                sessionID: "rollback-\(index)",
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Rollback \(index)")],
                ownerDeviceID: "device-a"
            ))
        }
        try executeRawSQLite(
            """
            CREATE TRIGGER fail_bulk_archive_insert
            BEFORE INSERT ON runtime_chat_events
            WHEN NEW.kind = 'archived' AND NEW.session_id = 'rollback-1'
            BEGIN
                SELECT RAISE(ABORT, 'forced bulk rollback');
            END
            """,
            at: databaseURL
        )

        XCTAssertThrowsError(try store.mutateSessions(
            ownerDeviceID: "device-a",
            scope: .allActive,
            limit: 3,
            requestID: "rollback-bulk",
            timestamp: Date(timeIntervalSince1970: 200)
        ))
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false)
                .map(\.sessionID),
            ["rollback-2", "rollback-1", "rollback-0"]
        )
        XCTAssertEqual(
            try rawSQLiteInt(
                "SELECT COUNT(*) FROM runtime_chat_events WHERE kind = 'archived'",
                at: databaseURL
            ),
            0
        )
    }

    func testBulkLifecyclePreCommitFailureReceivesExactTargetsAndWritesNothing() throws {
        let stores: [any RuntimeChatEventStore] = [
            JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL()),
            SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL()),
        ]
        for store in stores {
            for index in 0..<3 {
                try store.append(RuntimeChatStoredEvent(
                    timestamp: Date(timeIntervalSince1970: TimeInterval(300 + index)),
                    kind: .request,
                    requestID: "precommit-\(index)-turn",
                    sessionID: "precommit-\(index)",
                    model: "ollama:llama3.1:8b",
                    messages: [ChatMessage(role: "user", content: "Precommit \(index)")],
                    ownerDeviceID: "device-a"
                ))
            }
            let receivedTargetIDs = SQLiteRuntimeChatConcurrentResultBox<[String]>()
            XCTAssertThrowsError(try store.mutateSessions(
                ownerDeviceID: "device-a",
                scope: .allActive,
                limit: 2,
                requestID: "precommit-failure",
                timestamp: Date(timeIntervalSince1970: 400),
                beforeCommit: { targetIDs in
                    receivedTargetIDs.store(targetIDs)
                    throw NSError(
                        domain: "SQLiteRuntimeChatEventStoreTests",
                        code: 50,
                        userInfo: [NSLocalizedDescriptionKey: "forced precommit failure"]
                    )
                }
            ))
            XCTAssertEqual(receivedTargetIDs.load(), ["precommit-2", "precommit-1"])
            XCTAssertEqual(
                try store.listSessions(
                    ownerDeviceID: "device-a",
                    limit: 10,
                    includeArchived: false
                ).map(\.sessionID),
                ["precommit-2", "precommit-1", "precommit-0"]
            )
            XCTAssertTrue(
                try store.listSessions(
                    ownerDeviceID: "device-a",
                    limit: 10,
                    includeArchived: true
                ).allSatisfy { $0.status == "active" }
            )
        }
    }

    func testChatEventStoresRejectInvalidTitleEventsAndAcceptCanonicalBoundedTitles() throws {
        let stores: [(name: String, store: any RuntimeChatEventStore)] = [
            (
                "JSONL",
                JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL())
            ),
            (
                "SQLite",
                SQLiteRuntimeChatEventStore(databaseURL: try temporaryDatabaseURL())
            ),
        ]
        let invalidTitles: [(name: String, value: String)] = [
            ("control", "Control\u{0000}Title"),
            ("non-NFC", "Cafe\u{0301}"),
            ("noncanonical whitespace", " Leading whitespace"),
            (
                "oversized",
                String(repeating: "a", count: RuntimeResearchNotebook.maximumTitleCharacters + 1)
            ),
        ]

        for storeFixture in stores {
            for (index, invalidTitle) in invalidTitles.enumerated() {
                XCTAssertThrowsError(try storeFixture.store.append(RuntimeChatStoredEvent(
                    id: "\(storeFixture.name)-invalid-title-\(index)",
                    timestamp: Date(timeIntervalSince1970: TimeInterval(index)),
                    kind: .title,
                    requestID: "invalid-title-\(index)",
                    sessionID: "title-validation-session",
                    model: "ollama:llama3.1:8b",
                    title: invalidTitle.value,
                    ownerDeviceID: "device-a"
                )), "\(storeFixture.name): \(invalidTitle.name)")
            }

            let boundedCanonicalTitle = String(
                repeating: "a",
                count: RuntimeResearchNotebook.maximumTitleCharacters
            )
            try storeFixture.store.append(RuntimeChatStoredEvent(
                id: "\(storeFixture.name)-canonical-bounded-title",
                timestamp: Date(timeIntervalSince1970: 100),
                kind: .title,
                requestID: "canonical-bounded-title",
                sessionID: "title-validation-session",
                model: "ollama:llama3.1:8b",
                title: boundedCanonicalTitle,
                ownerDeviceID: "device-a"
            ))
            XCTAssertEqual(
                try storeFixture.store.listSessions(
                    ownerDeviceID: "device-a",
                    limit: 10,
                    includeArchived: true
                ).first?.title,
                boundedCanonicalTitle,
                storeFixture.name
            )
        }
    }

    func testLegacyInvalidTitlesProjectCanonicallyWithoutBlockingJSONLOrSQLiteReplay() throws {
        let fixtures: [(sessionID: String, invalidTitle: String, expectedTitle: String)] = [
            ("legacy-non-nfc-title", "Cafe\u{0301}", "Caf\u{00E9}"),
            ("legacy-control-title", "Safe\u{0000}\nTitle", "SafeTitle"),
            (
                "legacy-oversized-title",
                String(repeating: "x", count: RuntimeResearchNotebook.maximumTitleCharacters + 17),
                String(repeating: "x", count: RuntimeResearchNotebook.maximumTitleCharacters)
            ),
        ]
        var legacyEvents: [RuntimeChatStoredEvent] = []
        for (index, fixture) in fixtures.enumerated() {
            let timestamp = TimeInterval(100 + index * 10)
            legacyEvents.append(RuntimeChatStoredEvent(
                id: "\(fixture.sessionID)-request-event",
                timestamp: Date(timeIntervalSince1970: timestamp),
                kind: .request,
                requestID: "\(fixture.sessionID)-turn",
                sessionID: fixture.sessionID,
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Replay the full legacy session.")],
                ownerDeviceID: "device-a"
            ))
            legacyEvents.append(RuntimeChatStoredEvent(
                id: "\(fixture.sessionID)-title-event",
                timestamp: Date(timeIntervalSince1970: timestamp + 1),
                kind: .title,
                requestID: "\(fixture.sessionID)-title",
                sessionID: fixture.sessionID,
                model: "ollama:llama3.1:8b",
                title: fixture.invalidTitle,
                ownerDeviceID: "device-a"
            ))
            legacyEvents.append(RuntimeChatStoredEvent(
                id: "\(fixture.sessionID)-done-event",
                timestamp: Date(timeIntervalSince1970: timestamp + 2),
                kind: .done,
                requestID: "\(fixture.sessionID)-turn",
                sessionID: fixture.sessionID,
                model: "ollama:llama3.1:8b",
                finishReason: "stop",
                ownerDeviceID: "device-a"
            ))
        }

        let legacyURL = try temporaryJSONLURL()
        try writeRawLegacyEvents(legacyEvents, to: legacyURL)
        let jsonlSessions = try JSONLRuntimeChatEventStore(fileURL: legacyURL).listSessions(
            ownerDeviceID: "device-a",
            limit: 20,
            includeArchived: true
        )
        let jsonlSessionsByID = Dictionary(uniqueKeysWithValues: jsonlSessions.map { ($0.sessionID, $0) })
        XCTAssertEqual(jsonlSessions.count, fixtures.count)
        for fixture in fixtures {
            XCTAssertEqual(jsonlSessionsByID[fixture.sessionID]?.title, fixture.expectedTitle)
            XCTAssertEqual(jsonlSessionsByID[fixture.sessionID]?.messageCount, 1)
        }

        let importedDatabaseURL = try temporaryDatabaseURL()
        let importedStore = SQLiteRuntimeChatEventStore(
            databaseURL: importedDatabaseURL,
            legacyJSONLFileURL: legacyURL
        )
        let importedSessions = try importedStore.listSessions(
            ownerDeviceID: "device-a",
            limit: 20,
            includeArchived: true
        )
        XCTAssertEqual(importedSessions, jsonlSessions)
        XCTAssertEqual(
            try SQLiteRuntimeChatEventStore(databaseURL: importedDatabaseURL).listSessions(
                ownerDeviceID: "device-a",
                limit: 20,
                includeArchived: true
            ),
            jsonlSessions
        )

        let existingDatabaseURL = try temporaryDatabaseURL()
        let existingStore = SQLiteRuntimeChatEventStore(databaseURL: existingDatabaseURL)
        for (index, fixture) in fixtures.enumerated() {
            let timestamp = TimeInterval(200 + index * 10)
            try existingStore.append(RuntimeChatStoredEvent(
                id: "sqlite-\(fixture.sessionID)-request-event",
                timestamp: Date(timeIntervalSince1970: timestamp),
                kind: .request,
                requestID: "sqlite-\(fixture.sessionID)-turn",
                sessionID: fixture.sessionID,
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Replay existing SQLite state.")],
                ownerDeviceID: "device-a"
            ))
            let titleEvent = RuntimeChatStoredEvent(
                id: "sqlite-\(fixture.sessionID)-title-event",
                timestamp: Date(timeIntervalSince1970: timestamp + 1),
                kind: .title,
                requestID: "sqlite-\(fixture.sessionID)-title",
                sessionID: fixture.sessionID,
                model: "ollama:llama3.1:8b",
                title: "Temporary canonical title",
                ownerDeviceID: "device-a"
            )
            try existingStore.append(titleEvent)
            var invalidStoredTitleEvent = titleEvent
            invalidStoredTitleEvent.title = fixture.invalidTitle
            try replaceRawSQLiteEventJSON(invalidStoredTitleEvent, at: existingDatabaseURL)
            try existingStore.append(RuntimeChatStoredEvent(
                id: "sqlite-\(fixture.sessionID)-done-event",
                timestamp: Date(timeIntervalSince1970: timestamp + 2),
                kind: .done,
                requestID: "sqlite-\(fixture.sessionID)-turn",
                sessionID: fixture.sessionID,
                model: "ollama:llama3.1:8b",
                finishReason: "stop",
                ownerDeviceID: "device-a"
            ))
        }
        let existingSessions = try SQLiteRuntimeChatEventStore(databaseURL: existingDatabaseURL).listSessions(
            ownerDeviceID: "device-a",
            limit: 20,
            includeArchived: true
        )
        let existingSessionsByID = Dictionary(uniqueKeysWithValues: existingSessions.map { ($0.sessionID, $0) })
        XCTAssertEqual(existingSessions.count, fixtures.count)
        for fixture in fixtures {
            XCTAssertEqual(existingSessionsByID[fixture.sessionID]?.title, fixture.expectedTitle)
            XCTAssertEqual(existingSessionsByID[fixture.sessionID]?.messageCount, 1)
        }
    }

    func testJSONLAndSQLitePreserveSameTimestampTitleAppendOrderAfterReopen() throws {
        let jsonlURL = try temporaryJSONLURL()
        let databaseURL = try temporaryDatabaseURL()
        let stores: [any RuntimeChatEventStore] = [
            JSONLRuntimeChatEventStore(fileURL: jsonlURL),
            SQLiteRuntimeChatEventStore(databaseURL: databaseURL),
        ]
        let timestamp = Date(timeIntervalSince1970: 250)
        let events = [
            RuntimeChatStoredEvent(
                id: "same-time-request",
                timestamp: timestamp,
                kind: .request,
                requestID: "same-time-turn",
                sessionID: "same-time-session",
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Name this chat.")],
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                id: "same-time-generated-title",
                timestamp: timestamp,
                kind: .title,
                requestID: "same-time-generated-title",
                sessionID: "same-time-session",
                model: "ollama:llama3.1:8b",
                title: "Generated title",
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                id: "same-time-manual-title",
                timestamp: timestamp,
                kind: .title,
                requestID: "same-time-manual-title",
                sessionID: "same-time-session",
                model: "ollama:llama3.1:8b",
                title: "Manual title",
                ownerDeviceID: "device-a"
            ),
        ]
        for store in stores {
            for event in events { try store.append(event) }
        }

        let reopenedStores: [any RuntimeChatEventStore] = [
            JSONLRuntimeChatEventStore(fileURL: jsonlURL),
            SQLiteRuntimeChatEventStore(databaseURL: databaseURL),
        ]
        let reopenedSessions = try reopenedStores.map { store in
            try XCTUnwrap(store.listSessions(
                ownerDeviceID: "device-a",
                limit: 10,
                includeArchived: true
            ).first)
        }
        XCTAssertEqual(reopenedSessions.map(\.title), ["Manual title", "Manual title"])
        XCTAssertEqual(reopenedSessions.map(\.titleUpdatedAt), [timestamp, timestamp])
        XCTAssertEqual(reopenedSessions.map(\.titleRevision), [2, 2])
        XCTAssertEqual(reopenedSessions[0], reopenedSessions[1])
    }

    func testJSONLAndSQLitePreserveReverseTimestampTitleAppendOrderAfterReopen() throws {
        let jsonlURL = try temporaryJSONLURL()
        let databaseURL = try temporaryDatabaseURL()
        let stores: [any RuntimeChatEventStore] = [
            JSONLRuntimeChatEventStore(fileURL: jsonlURL),
            SQLiteRuntimeChatEventStore(databaseURL: databaseURL),
        ]
        let latestTimestamp = Date(timeIntervalSince1970: 300)
        let reverseTimestamp = Date(timeIntervalSince1970: 200)
        let events = [
            RuntimeChatStoredEvent(
                id: "reverse-time-request",
                timestamp: Date(timeIntervalSince1970: 100),
                kind: .request,
                requestID: "reverse-time-turn",
                sessionID: "reverse-time-session",
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Name this chat.")],
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                id: "reverse-time-first-title",
                timestamp: latestTimestamp,
                kind: .title,
                requestID: "reverse-time-first-title",
                sessionID: "reverse-time-session",
                model: "ollama:llama3.1:8b",
                title: "First appended title",
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                id: "reverse-time-second-title",
                timestamp: reverseTimestamp,
                kind: .title,
                requestID: "reverse-time-second-title",
                sessionID: "reverse-time-session",
                model: "ollama:llama3.1:8b",
                title: "Second appended title",
                ownerDeviceID: "device-a"
            ),
        ]
        for store in stores {
            for event in events { try store.append(event) }
        }

        let reopenedSessions = try [
            JSONLRuntimeChatEventStore(fileURL: jsonlURL) as any RuntimeChatEventStore,
            SQLiteRuntimeChatEventStore(databaseURL: databaseURL) as any RuntimeChatEventStore,
        ].map { store in
            try XCTUnwrap(store.listSessions(
                ownerDeviceID: "device-a",
                limit: 10,
                includeArchived: true
            ).first)
        }
        XCTAssertEqual(reopenedSessions.map(\.title), ["Second appended title", "Second appended title"])
        XCTAssertEqual(reopenedSessions.map(\.titleUpdatedAt), [reverseTimestamp, reverseTimestamp])
        XCTAssertEqual(reopenedSessions.map(\.titleRevision), [2, 2])
        XCTAssertEqual(reopenedSessions[0], reopenedSessions[1])
    }

    func testSQLiteLegacyImportPreservesReverseTimestampTitleAppendOrder() throws {
        let legacyURL = try temporaryJSONLURL()
        let databaseURL = try temporaryDatabaseURL()
        let reverseTimestamp = Date(timeIntervalSince1970: 200)
        try writeRawLegacyEvents([
            RuntimeChatStoredEvent(
                id: "legacy-reverse-request",
                timestamp: Date(timeIntervalSince1970: 100),
                kind: .request,
                requestID: "legacy-reverse-turn",
                sessionID: "legacy-reverse-session",
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Preserve legacy append order.")],
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                id: "legacy-reverse-first-title",
                timestamp: Date(timeIntervalSince1970: 300),
                kind: .title,
                requestID: "legacy-reverse-first-title",
                sessionID: "legacy-reverse-session",
                model: "ollama:llama3.1:8b",
                title: "Legacy first title",
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                id: "legacy-reverse-second-title",
                timestamp: reverseTimestamp,
                kind: .title,
                requestID: "legacy-reverse-second-title",
                sessionID: "legacy-reverse-session",
                model: "ollama:llama3.1:8b",
                title: "Legacy second title",
                ownerDeviceID: "device-a"
            ),
        ], to: legacyURL)

        let jsonlSession = try XCTUnwrap(JSONLRuntimeChatEventStore(fileURL: legacyURL).listSessions(
            ownerDeviceID: "device-a",
            limit: 10,
            includeArchived: true
        ).first)
        let importedStore = SQLiteRuntimeChatEventStore(
            databaseURL: databaseURL,
            legacyJSONLFileURL: legacyURL
        )
        let importedSession = try XCTUnwrap(importedStore.listSessions(
            ownerDeviceID: "device-a",
            limit: 10,
            includeArchived: true
        ).first)
        let reopenedSession = try XCTUnwrap(SQLiteRuntimeChatEventStore(databaseURL: databaseURL).listSessions(
            ownerDeviceID: "device-a",
            limit: 10,
            includeArchived: true
        ).first)

        XCTAssertEqual(jsonlSession.title, "Legacy second title")
        XCTAssertEqual(jsonlSession.titleUpdatedAt, reverseTimestamp)
        XCTAssertEqual(jsonlSession.titleRevision, 2)
        XCTAssertEqual(importedSession, jsonlSession)
        XCTAssertEqual(reopenedSession, jsonlSession)
    }

    func testSQLiteStorePreservesAppendOrderForSameTimestampTitles() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
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

        let session = try XCTUnwrap(
            store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).first
        )
        XCTAssertEqual(session.title, "Manual title")
        XCTAssertEqual(session.titleUpdatedAt, timestamp)

        let reopenedStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let reopenedSession = try XCTUnwrap(
            reopenedStore.listSessions(
                ownerDeviceID: "device-a",
                limit: 10,
                includeArchived: true
            ).first
        )
        XCTAssertEqual(reopenedSession.title, "Manual title")
        XCTAssertEqual(reopenedSession.titleUpdatedAt, timestamp)
        XCTAssertEqual(reopenedSession, session)
    }

    func testJSONLStoreUsesSessionIDTieBreakForEqualActivityAndLexicalScores() throws {
        let store: any RuntimeChatEventStore = JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL())
        try appendEqualRankingSessions(to: store)

        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: nil, limit: 1, includeArchived: false).map(\.sessionID),
            ["session-a"]
        )
        XCTAssertEqual(
            try store.listSessions(
                ownerDeviceID: nil,
                limit: 1,
                includeArchived: false,
                query: "deterministic lexical tie"
            ).map(\.sessionID),
            ["session-a"]
        )
    }

    func testSQLiteStoreUsesSessionIDTieBreakAfterReopenForEqualActivityAndLexicalScores() throws {
        let databaseURL = try temporaryDatabaseURL()
        try appendEqualRankingSessions(to: SQLiteRuntimeChatEventStore(databaseURL: databaseURL))

        let reopenedStore: any RuntimeChatEventStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try reopenedStore.listSessions(ownerDeviceID: nil, limit: 1, includeArchived: false).map(\.sessionID),
            ["session-a"]
        )
        XCTAssertEqual(
            try reopenedStore.listSessions(
                ownerDeviceID: nil,
                limit: 1,
                includeArchived: false,
                query: "deterministic lexical tie"
            ).map(\.sessionID),
            ["session-a"]
        )
    }

    func testSQLiteAppendRewritesOnlyAffectedFTSSessionRow() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        try store.append(RuntimeChatStoredEvent(
            id: "incremental-affected-request",
            timestamp: Date(timeIntervalSince1970: 100),
            kind: .request,
            requestID: "incremental-affected-turn",
            sessionID: "incremental-affected",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Affected searchable content")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "incremental-unaffected-request",
            timestamp: Date(timeIntervalSince1970: 101),
            kind: .request,
            requestID: "incremental-unaffected-turn",
            sessionID: "incremental-unaffected",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Unaffected searchable content")],
            ownerDeviceID: "device-a"
        ))
        let before = try rawFTSSessionRowIDs(at: databaseURL)

        try store.append(RuntimeChatStoredEvent(
            id: "incremental-affected-delta",
            timestamp: Date(timeIntervalSince1970: 102),
            kind: .assistantDelta,
            requestID: "incremental-affected-turn",
            sessionID: "incremental-affected",
            model: "ollama:llama3.1:8b",
            delta: "Affected follow-up",
            ownerDeviceID: "device-a"
        ))

        let after = try rawFTSSessionRowIDs(at: databaseURL)
        XCTAssertEqual(after.count, 2)
        XCTAssertNotEqual(before["device-a|incremental-affected"], after["device-a|incremental-affected"])
        XCTAssertEqual(before["device-a|incremental-unaffected"], after["device-a|incremental-unaffected"])
        XCTAssertEqual(
            try store.listSessions(
                ownerDeviceID: "device-a",
                limit: 10,
                includeArchived: true,
                query: "affected follow-up"
            ).map(\.sessionID),
            ["incremental-affected"]
        )
    }

    func testSQLiteIncrementalFTSMatchesJSONLForSingleAndBatchMultiSessionUpdates() throws {
        let databaseURL = try temporaryDatabaseURL()
        let sqliteStore: any RuntimeChatEventStore = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let jsonlStore: any RuntimeChatEventStore = JSONLRuntimeChatEventStore(fileURL: try temporaryJSONLURL())
        let initialEvents = [
            RuntimeChatStoredEvent(
                id: "incremental-alpha-request",
                timestamp: Date(timeIntervalSince1970: 200),
                kind: .request,
                requestID: "incremental-alpha-turn",
                sessionID: "incremental-alpha",
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(
                    role: "user",
                    content: "Alpha searchable transcript",
                    attachments: [ChatAttachment(
                        type: "text",
                        mimeType: "text/plain",
                        name: "alpha.txt",
                        text: "Alpha searchable attachment"
                    )]
                )],
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                id: "incremental-alpha-reasoning",
                timestamp: Date(timeIntervalSince1970: 201),
                kind: .reasoningDelta,
                requestID: "incremental-alpha-turn",
                sessionID: "incremental-alpha",
                model: "ollama:llama3.1:8b",
                reasoningDelta: "Alpha searchable reasoning",
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                id: "incremental-beta-request",
                timestamp: Date(timeIntervalSince1970: 210),
                kind: .request,
                requestID: "incremental-beta-turn",
                sessionID: "incremental-beta",
                model: "lmstudio:qwen3:8b",
                messages: [ChatMessage(role: "user", content: "Beta searchable transcript")],
                ownerDeviceID: "device-a"
            ),
            RuntimeChatStoredEvent(
                id: "incremental-gamma-request",
                timestamp: Date(timeIntervalSince1970: 220),
                kind: .request,
                requestID: "incremental-gamma-turn",
                sessionID: "incremental-gamma",
                model: "ollama:gemma3:4b",
                messages: [ChatMessage(role: "user", content: "Gamma searchable transcript")],
                ownerDeviceID: "device-a"
            )
        ]
        for event in initialEvents {
            try sqliteStore.append(event)
            try jsonlStore.append(event)
        }
        let singleUpdate = RuntimeChatStoredEvent(
            id: "incremental-alpha-answer",
            timestamp: Date(timeIntervalSince1970: 230),
            kind: .assistantDelta,
            requestID: "incremental-alpha-turn",
            sessionID: "incremental-alpha",
            model: "ollama:llama3.1:8b",
            delta: "Single incremental answer",
            ownerDeviceID: "device-a"
        )
        try sqliteStore.append(singleUpdate)
        try jsonlStore.append(singleUpdate)

        for query in ["single incremental", "searchable attachment", "searchable reasoning", "beta"] {
            XCTAssertEqual(
                try sqliteStore.listSessions(
                    ownerDeviceID: "device-a",
                    limit: 10,
                    includeArchived: true,
                    query: query
                ),
                try jsonlStore.listSessions(
                    ownerDeviceID: "device-a",
                    limit: 10,
                    includeArchived: true,
                    query: query
                )
            )
        }

        let rowIDsBeforeBatch = try rawFTSSessionRowIDs(at: databaseURL)
        let sqliteMutation = try sqliteStore.mutateSessions(
            ownerDeviceID: "device-a",
            scope: .allActive,
            limit: 2,
            requestID: "incremental-batch-archive",
            timestamp: Date(timeIntervalSince1970: 240)
        )
        let jsonlMutation = try jsonlStore.mutateSessions(
            ownerDeviceID: "device-a",
            scope: .allActive,
            limit: 2,
            requestID: "incremental-batch-archive",
            timestamp: Date(timeIntervalSince1970: 240)
        )
        XCTAssertEqual(sqliteMutation, jsonlMutation)

        let rowIDsAfterBatch = try rawFTSSessionRowIDs(at: databaseURL)
        let affectedKeys = Set(sqliteMutation.affectedSessionIDs.map { "device-a|\($0)" })
        for key in rowIDsBeforeBatch.keys where !affectedKeys.contains(key) {
            XCTAssertEqual(rowIDsBeforeBatch[key], rowIDsAfterBatch[key], key)
        }
        XCTAssertEqual(rowIDsAfterBatch.count, rowIDsBeforeBatch.count)
        for query in ["archived", "single incremental", "gamma searchable", "beta searchable"] {
            XCTAssertEqual(
                try sqliteStore.listSessions(
                    ownerDeviceID: "device-a",
                    limit: 10,
                    includeArchived: true,
                    query: query
                ),
                try jsonlStore.listSessions(
                    ownerDeviceID: "device-a",
                    limit: 10,
                    includeArchived: true,
                    query: query
                )
            )
        }
    }

    func testSQLiteIncrementalAppendRejectsUnrelatedCorruptEventAndRollsBack() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        try store.append(RuntimeChatStoredEvent(
            id: "incremental-valid-request",
            timestamp: Date(timeIntervalSince1970: 300),
            kind: .request,
            requestID: "incremental-valid-turn",
            sessionID: "incremental-valid",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Valid session")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "incremental-corrupt-request",
            timestamp: Date(timeIntervalSince1970: 301),
            kind: .request,
            requestID: "incremental-corrupt-turn",
            sessionID: "incremental-corrupt",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Unrelated session")],
            ownerDeviceID: "device-a"
        ))
        let rowIDsBefore = try rawFTSSessionRowIDs(at: databaseURL)
        try executeRawSQLite(
            "UPDATE runtime_chat_events SET event_json = '{not-json' " +
                "WHERE event_id = 'incremental-corrupt-request'",
            at: databaseURL
        )

        XCTAssertThrowsError(try store.append(RuntimeChatStoredEvent(
            id: "incremental-rolled-back-delta",
            timestamp: Date(timeIntervalSince1970: 302),
            kind: .assistantDelta,
            requestID: "incremental-valid-turn",
            sessionID: "incremental-valid",
            model: "ollama:llama3.1:8b",
            delta: "Must roll back",
            ownerDeviceID: "device-a"
        ))) { error in
            guard case RuntimeChatEventStoreError.corruptEventLog = error else {
                return XCTFail("Expected corrupt event log, got \(error).")
            }
        }
        XCTAssertEqual(
            try rawSQLiteInt(
                "SELECT COUNT(*) FROM runtime_chat_events " +
                    "WHERE event_id = 'incremental-rolled-back-delta'",
                at: databaseURL
            ),
            0
        )
        XCTAssertEqual(try rawFTSSessionRowIDs(at: databaseURL), rowIDsBefore)
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

    func testSQLiteAllOwnerRetentionUsesGlobalLimitAndDeterministicOwnerTieBreak() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        let cutoff = Date(timeIntervalSince1970: 1_000)

        try appendDeletedSession(
            to: store,
            ownerDeviceID: "device-b",
            sessionID: "all-owner-oldest",
            requestTimestamp: 100,
            deletedTimestamp: 300
        )
        try appendDeletedSession(
            to: store,
            ownerDeviceID: nil,
            sessionID: "all-owner-legacy",
            requestTimestamp: 110,
            deletedTimestamp: 400
        )
        try appendDeletedSession(
            to: store,
            ownerDeviceID: "device-a",
            sessionID: "all-owner-shared",
            requestTimestamp: 120,
            deletedTimestamp: 400
        )
        try appendDeletedSession(
            to: store,
            ownerDeviceID: "device-b",
            sessionID: "all-owner-shared",
            requestTimestamp: 130,
            deletedTimestamp: 400
        )
        try store.append(RuntimeChatStoredEvent(
            id: "all-owner-active-request",
            timestamp: Date(timeIntervalSince1970: 500),
            kind: .request,
            requestID: "all-owner-active-turn",
            sessionID: "all-owner-active",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "active keeper")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "all-owner-archived-request",
            timestamp: Date(timeIntervalSince1970: 510),
            kind: .request,
            requestID: "all-owner-archived-turn",
            sessionID: "all-owner-archived",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "archived keeper")],
            ownerDeviceID: "device-b"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-b",
            sessionID: "all-owner-archived",
            requestID: "all-owner-archived-mutation",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 520)
        )
        try appendDeletedSession(
            to: store,
            ownerDeviceID: nil,
            sessionID: "all-owner-recent",
            requestTimestamp: 1_100,
            deletedTimestamp: 1_200
        )

        let firstResult = try store.pruneDeletedSessions(deletedBefore: cutoff, limit: 3)

        XCTAssertEqual(
            firstResult.prunedSessionIDs,
            ["all-owner-oldest", "all-owner-legacy", "all-owner-shared"]
        )
        XCTAssertEqual(firstResult.prunedSessionCount, 3)
        XCTAssertEqual(firstResult.prunedEventCount, 9)
        let remainingEvents = try rawSQLiteEvents(at: databaseURL)
        XCTAssertFalse(remainingEvents.contains {
            $0.ownerDeviceID == nil && $0.sessionID == "all-owner-legacy"
        })
        XCTAssertFalse(remainingEvents.contains {
            $0.ownerDeviceID == "device-a" && $0.sessionID == "all-owner-shared"
        })
        XCTAssertEqual(
            remainingEvents.filter {
                $0.ownerDeviceID == "device-b" && $0.sessionID == "all-owner-shared"
            }.count,
            3
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).map(\.sessionID),
            ["all-owner-active"]
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-b", limit: 10, includeArchived: true).map(\.sessionID),
            ["all-owner-archived"]
        )
        XCTAssertEqual(
            remainingEvents.filter {
                $0.ownerDeviceID == nil && $0.sessionID == "all-owner-recent"
            }.count,
            3
        )
        XCTAssertThrowsError(try store.append(RuntimeChatStoredEvent(
            id: "all-owner-device-a-resurrection",
            timestamp: Date(timeIntervalSince1970: 600),
            kind: .request,
            requestID: "all-owner-device-a-resurrection",
            sessionID: "all-owner-shared",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "must stay pruned")],
            ownerDeviceID: "device-a"
        ))) { error in
            XCTAssertTrue(error.localizedDescription.contains("pruned by retention"))
        }
        XCTAssertThrowsError(try store.append(RuntimeChatStoredEvent(
            id: "all-owner-legacy-resurrection",
            timestamp: Date(timeIntervalSince1970: 605),
            kind: .request,
            requestID: "all-owner-legacy-resurrection",
            sessionID: "all-owner-legacy",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "legacy must stay pruned")]
        ))) { error in
            XCTAssertTrue(error.localizedDescription.contains("pruned by retention"))
        }
        try store.append(RuntimeChatStoredEvent(
            id: "all-owner-device-b-after-device-a-prune",
            timestamp: Date(timeIntervalSince1970: 610),
            kind: .assistantDelta,
            requestID: "all-owner-shared-device-b-turn",
            sessionID: "all-owner-shared",
            model: "ollama:llama3.1:8b",
            delta: "owner isolation preserved",
            ownerDeviceID: "device-b"
        ))

        let secondResult = try store.pruneDeletedSessions(deletedBefore: cutoff, limit: 1)
        XCTAssertEqual(secondResult.prunedSessionIDs, ["all-owner-shared"])
        XCTAssertEqual(secondResult.prunedEventCount, 4)
        XCTAssertEqual(
            try rawSQLiteEvents(at: databaseURL).filter {
                $0.ownerDeviceID == nil && $0.sessionID == "all-owner-recent"
            }.count,
            3
        )
    }

    func testSQLiteAllOwnerRetentionUsesBoundedMetadataQueryAndTargetedFTSDeletion() throws {
        let databaseURL = try temporaryDatabaseURL()
        let store = SQLiteRuntimeChatEventStore(databaseURL: databaseURL)
        try appendDeletedSession(
            to: store,
            ownerDeviceID: nil,
            sessionID: "metadata-oldest",
            requestTimestamp: 100,
            deletedTimestamp: 200
        )
        try appendDeletedSession(
            to: store,
            ownerDeviceID: "device-a",
            sessionID: "metadata-later",
            requestTimestamp: 110,
            deletedTimestamp: 300
        )
        try store.append(RuntimeChatStoredEvent(
            id: "metadata-keeper-request",
            timestamp: Date(timeIntervalSince1970: 400),
            kind: .request,
            requestID: "metadata-keeper-turn",
            sessionID: "metadata-keeper",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "metadata keeper searchable")],
            ownerDeviceID: "device-b"
        ))
        try executeRawSQLite(
            "UPDATE runtime_chat_events SET event_json = '{not-json'",
            at: databaseURL
        )
        try insertRawFTSSession(ownerKey: "", sessionID: "metadata-oldest", at: databaseURL)
        try insertRawFTSSession(ownerKey: "device-a", sessionID: "metadata-later", at: databaseURL)

        let result = try store.pruneDeletedSessions(
            deletedBefore: Date(timeIntervalSince1970: 1_000),
            limit: 1
        )

        XCTAssertEqual(result.prunedSessionIDs, ["metadata-oldest"])
        XCTAssertEqual(result.prunedEventCount, 3)
        XCTAssertEqual(
            try rawSQLiteInt(
                "SELECT COUNT(*) FROM runtime_chat_events WHERE session_id = 'metadata-oldest'",
                at: databaseURL
            ),
            0
        )
        XCTAssertEqual(
            try rawSQLiteInt(
                "SELECT COUNT(*) FROM runtime_chat_events WHERE session_id = 'metadata-later'",
                at: databaseURL
            ),
            3
        )
        XCTAssertEqual(
            try rawFTSSessionKeys(at: databaseURL),
            ["device-a|metadata-later", "device-b|metadata-keeper"]
        )
    }

    func testProductionAllOwnerMaintenanceOverloadPrunesAcrossOwnersWithOneLimit() throws {
        let store = RuntimeChatEventStoreDefaults.productionStore(
            sqliteDatabaseURL: try temporaryDatabaseURL(),
            legacyJSONLFileURL: nil
        )
        try appendDeletedSession(
            to: store,
            ownerDeviceID: "device-b",
            sessionID: "production-all-owner-oldest",
            requestTimestamp: 100,
            deletedTimestamp: 200
        )
        try appendDeletedSession(
            to: store,
            ownerDeviceID: nil,
            sessionID: "production-all-owner-legacy",
            requestTimestamp: 110,
            deletedTimestamp: 210
        )
        try appendDeletedSession(
            to: store,
            ownerDeviceID: "device-a",
            sessionID: "production-all-owner-remaining",
            requestTimestamp: 120,
            deletedTimestamp: 220
        )
        let policy = RuntimeChatRetentionPolicy(
            deletedSessionRetentionInterval: 500,
            deletedSessionPruneLimit: 2
        )

        let allOwnerResult = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            now: Date(timeIntervalSince1970: 1_000),
            policy: policy
        )

        XCTAssertEqual(
            allOwnerResult.deletedSessionPruneResult.prunedSessionIDs,
            ["production-all-owner-oldest", "production-all-owner-legacy"]
        )
        XCTAssertEqual(allOwnerResult.prunedDeletedSessionCount, 2)
        let ownerResult = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            ownerDeviceID: "device-a",
            now: Date(timeIntervalSince1970: 1_000),
            policy: policy
        )
        XCTAssertEqual(
            ownerResult.deletedSessionPruneResult.prunedSessionIDs,
            ["production-all-owner-remaining"]
        )
    }

    func testProductionRetentionCompactsLegacyJSONLOnlyAfterCommitAndPreservesAppendBackfill() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        let legacyStore = JSONLRuntimeChatEventStore(fileURL: legacyURL)
        try appendDeletedSession(
            to: legacyStore,
            ownerDeviceID: "device-a",
            sessionID: "legacy-compaction-deleted",
            requestTimestamp: 100,
            deletedTimestamp: 200
        )
        try legacyStore.append(RuntimeChatStoredEvent(
            id: "legacy-compaction-kept-request",
            timestamp: Date(timeIntervalSince1970: 300),
            kind: .request,
            requestID: "legacy-compaction-kept-turn",
            sessionID: "legacy-compaction-kept",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "legacy compaction keeper")],
            ownerDeviceID: "device-b"
        ))
        let store = RuntimeChatEventStoreDefaults.productionStore(
            sqliteDatabaseURL: databaseURL,
            legacyJSONLFileURL: legacyURL
        )
        XCTAssertEqual(
            try store.listMessages(
                ownerDeviceID: "device-b",
                sessionID: "legacy-compaction-kept",
                limit: 10
            ).map(\.content),
            ["legacy compaction keeper"]
        )
        try executeRawSQLite(
            """
            CREATE TRIGGER fail_runtime_chat_retention_tombstone
            BEFORE INSERT ON runtime_chat_retention_tombstones
            BEGIN
                SELECT RAISE(ABORT, 'forced retention rollback');
            END
            """,
            at: databaseURL
        )
        let policy = RuntimeChatRetentionPolicy(
            deletedSessionRetentionInterval: 500,
            deletedSessionPruneLimit: 10
        )

        XCTAssertThrowsError(try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            now: Date(timeIntervalSince1970: 1_000),
            policy: policy
        ))
        XCTAssertEqual(
            try JSONLRuntimeChatEventStore.events(from: legacyURL)
                .filter { $0.sessionID == "legacy-compaction-deleted" }.count,
            3
        )
        XCTAssertEqual(
            try rawSQLiteInt(
                "SELECT COUNT(*) FROM runtime_chat_events WHERE session_id = 'legacy-compaction-deleted'",
                at: databaseURL
            ),
            3
        )

        try executeRawSQLite("DROP TRIGGER fail_runtime_chat_retention_tombstone", at: databaseURL)
        let maintenance = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            now: Date(timeIntervalSince1970: 1_000),
            policy: policy
        )
        XCTAssertEqual(
            maintenance.deletedSessionPruneResult.prunedSessionIDs,
            ["legacy-compaction-deleted"]
        )
        XCTAssertEqual(
            try JSONLRuntimeChatEventStore.events(from: legacyURL).map(\.sessionID),
            ["legacy-compaction-kept"]
        )
        XCTAssertFalse(
            String(decoding: try Data(contentsOf: legacyURL), as: UTF8.self)
                .contains("legacy-compaction-deleted")
        )
        XCTAssertEqual(try posixPermissions(at: legacyURL), 0o600)

        try legacyStore.append(RuntimeChatStoredEvent(
            id: "legacy-compaction-kept-followup",
            timestamp: Date(timeIntervalSince1970: 310),
            kind: .assistantDelta,
            requestID: "legacy-compaction-kept-turn",
            sessionID: "legacy-compaction-kept",
            model: "ollama:llama3.1:8b",
            delta: " after compaction",
            ownerDeviceID: "device-b"
        ))
        try legacyStore.append(RuntimeChatStoredEvent(
            id: "legacy-compaction-deleted-replay",
            timestamp: Date(timeIntervalSince1970: 320),
            kind: .assistantDelta,
            requestID: "legacy-compaction-deleted-turn",
            sessionID: "legacy-compaction-deleted",
            model: "ollama:llama3.1:8b",
            delta: "must be compacted again",
            ownerDeviceID: "device-a"
        ))
        let reopenedStore = RuntimeChatEventStoreDefaults.productionStore(
            sqliteDatabaseURL: databaseURL,
            legacyJSONLFileURL: legacyURL
        )

        XCTAssertEqual(
            try reopenedStore.listMessages(
                ownerDeviceID: "device-b",
                sessionID: "legacy-compaction-kept",
                limit: 10
            ).map(\.content),
            ["legacy compaction keeper", "after compaction"]
        )
        XCTAssertEqual(
            try JSONLRuntimeChatEventStore.events(from: legacyURL).map(\.sessionID),
            ["legacy-compaction-kept", "legacy-compaction-kept"]
        )
    }

    func testLegacyCompactionCoordinatesConcurrentCrossInstanceAppendWithoutDataLoss() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        let legacyStore = JSONLRuntimeChatEventStore(fileURL: legacyURL)
        try appendDeletedSession(
            to: legacyStore,
            ownerDeviceID: "device-a",
            sessionID: "coordination-deleted",
            requestTimestamp: 100,
            deletedTimestamp: 200
        )
        try legacyStore.append(RuntimeChatStoredEvent(
            id: "coordination-kept-request",
            timestamp: Date(timeIntervalSince1970: 300),
            kind: .request,
            requestID: "coordination-kept-turn",
            sessionID: "coordination-kept",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "coordination keeper")],
            ownerDeviceID: "device-b"
        ))
        let compactionReachedReplace = DispatchSemaphore(value: 0)
        let allowCompactionReplace = DispatchSemaphore(value: 0)
        let compactionHookWait = SQLiteRuntimeChatConcurrentResultBox<DispatchTimeoutResult>()
        let sqliteStore = SQLiteRuntimeChatEventStore(
            databaseURL: databaseURL,
            legacyJSONLFileURL: legacyURL,
            legacyJSONLCompactionWillReplace: {
                compactionReachedReplace.signal()
                compactionHookWait.store(
                    allowCompactionReplace.wait(timeout: .now() + .seconds(2))
                )
            }
        )
        XCTAssertEqual(
            try sqliteStore.listMessages(
                ownerDeviceID: "device-b",
                sessionID: "coordination-kept",
                limit: 10
            ).map(\.content),
            ["coordination keeper"]
        )

        let pruneResult = SQLiteRuntimeChatConcurrentResultBox<
            Result<RuntimeChatDeletedSessionPruneResult, Error>
        >()
        let appendResult = SQLiteRuntimeChatConcurrentResultBox<Result<Void, Error>>()
        let pruneFinished = DispatchSemaphore(value: 0)
        let appendFinished = DispatchSemaphore(value: 0)
        DispatchQueue.global(qos: .userInitiated).async {
            pruneResult.store(Result {
                try sqliteStore.pruneDeletedSessions(
                    deletedBefore: Date(timeIntervalSince1970: 1_000),
                    limit: 10
                )
            })
            pruneFinished.signal()
        }

        XCTAssertEqual(
            compactionReachedReplace.wait(timeout: .now() + .seconds(2)),
            .success
        )
        let concurrentStore = JSONLRuntimeChatEventStore(fileURL: legacyURL)
        DispatchQueue.global(qos: .userInitiated).async {
            appendResult.store(Result {
                try concurrentStore.append(RuntimeChatStoredEvent(
                    id: "coordination-concurrent-append",
                    timestamp: Date(timeIntervalSince1970: 310),
                    kind: .assistantDelta,
                    requestID: "coordination-kept-turn",
                    sessionID: "coordination-kept",
                    model: "ollama:llama3.1:8b",
                    delta: "concurrent append",
                    ownerDeviceID: "device-b"
                ))
            })
            appendFinished.signal()
        }
        XCTAssertEqual(pruneFinished.wait(timeout: .now() + .milliseconds(50)), .timedOut)
        XCTAssertEqual(appendFinished.wait(timeout: .now() + .milliseconds(50)), .timedOut)
        allowCompactionReplace.signal()

        XCTAssertEqual(pruneFinished.wait(timeout: .now() + .seconds(2)), .success)
        XCTAssertEqual(appendFinished.wait(timeout: .now() + .seconds(2)), .success)
        XCTAssertEqual(compactionHookWait.load(), .success)
        XCTAssertEqual(try XCTUnwrap(pruneResult.load()).get().prunedSessionIDs, ["coordination-deleted"])
        try XCTUnwrap(appendResult.load()).get()

        let reopenedStore = SQLiteRuntimeChatEventStore(
            databaseURL: databaseURL,
            legacyJSONLFileURL: legacyURL
        )
        XCTAssertEqual(
            try reopenedStore.listMessages(
                ownerDeviceID: "device-b",
                sessionID: "coordination-kept",
                limit: 10
            ).map(\.content),
            ["coordination keeper", "concurrent append"]
        )
        let remainingLegacyEvents = try JSONLRuntimeChatEventStore.events(from: legacyURL)
        XCTAssertTrue(remainingLegacyEvents.contains { $0.id == "coordination-concurrent-append" })
        XCTAssertFalse(remainingLegacyEvents.contains { $0.sessionID == "coordination-deleted" })
    }

    func testProductionRetentionDefersLegacyCompactionUntilFinalBatchDrain() throws {
        let databaseURL = try temporaryDatabaseURL()
        let legacyURL = try temporaryJSONLURL()
        var legacyEvents = [RuntimeChatStoredEvent(
            id: "batch-drain-kept-request",
            timestamp: Date(timeIntervalSince1970: 50),
            kind: .request,
            requestID: "batch-drain-kept-turn",
            sessionID: "batch-drain-kept",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "batch drain keeper")],
            ownerDeviceID: "device-keeper"
        )]
        for index in 0..<205 {
            let ownerDeviceID: String? = switch index % 3 {
            case 0: nil
            case 1: "device-a"
            default: "device-b"
            }
            legacyEvents.append(contentsOf: deletedSessionEvents(
                ownerDeviceID: ownerDeviceID,
                sessionID: String(format: "batch-drain-%03d", index),
                requestTimestamp: TimeInterval(100 + index * 3),
                deletedTimestamp: TimeInterval(102 + index * 3)
            ))
        }
        try writeRawLegacyEvents(legacyEvents, to: legacyURL)
        let store = RuntimeChatEventStoreDefaults.productionStore(
            sqliteDatabaseURL: databaseURL,
            legacyJSONLFileURL: legacyURL
        )
        XCTAssertEqual(
            try store.listMessages(
                ownerDeviceID: "device-keeper",
                sessionID: "batch-drain-kept",
                limit: 10
            ).map(\.content),
            ["batch drain keeper"]
        )
        let policy = RuntimeChatRetentionPolicy(
            deletedSessionRetentionInterval: 100,
            deletedSessionPruneLimit: 100
        )
        let originalLegacyData = try Data(contentsOf: legacyURL)

        let firstBatch = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            now: Date(timeIntervalSince1970: 10_000),
            policy: policy
        )
        XCTAssertEqual(firstBatch.prunedDeletedSessionCount, 100)
        XCTAssertEqual(try Data(contentsOf: legacyURL), originalLegacyData)

        try JSONLRuntimeChatEventStore(fileURL: legacyURL).append(RuntimeChatStoredEvent(
            id: "batch-drain-kept-followup",
            timestamp: Date(timeIntervalSince1970: 800),
            kind: .assistantDelta,
            requestID: "batch-drain-kept-turn",
            sessionID: "batch-drain-kept",
            model: "ollama:llama3.1:8b",
            delta: "batch append backfill",
            ownerDeviceID: "device-keeper"
        ))
        let legacyDataAfterAppend = try Data(contentsOf: legacyURL)
        try executeRawSQLite(
            """
            CREATE TRIGGER fail_deferred_runtime_chat_retention_tombstone
            BEFORE INSERT ON runtime_chat_retention_tombstones
            BEGIN
                SELECT RAISE(ABORT, 'forced deferred retention rollback');
            END
            """,
            at: databaseURL
        )
        XCTAssertThrowsError(try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            now: Date(timeIntervalSince1970: 10_000),
            policy: policy
        ))
        XCTAssertEqual(
            try rawSQLiteInt(
                "SELECT COUNT(*) FROM runtime_chat_retention_tombstones",
                at: databaseURL
            ),
            100
        )
        XCTAssertEqual(try Data(contentsOf: legacyURL), legacyDataAfterAppend)
        try executeRawSQLite(
            "DROP TRIGGER fail_deferred_runtime_chat_retention_tombstone",
            at: databaseURL
        )

        let secondBatch = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            now: Date(timeIntervalSince1970: 10_000),
            policy: policy
        )
        XCTAssertEqual(secondBatch.prunedDeletedSessionCount, 100)
        XCTAssertEqual(try Data(contentsOf: legacyURL), legacyDataAfterAppend)

        let finalBatch = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            now: Date(timeIntervalSince1970: 10_000),
            policy: policy
        )
        XCTAssertEqual(finalBatch.prunedDeletedSessionCount, 5)
        let compactedLegacyData = try Data(contentsOf: legacyURL)
        XCTAssertNotEqual(compactedLegacyData, legacyDataAfterAppend)
        XCTAssertEqual(
            try JSONLRuntimeChatEventStore.events(from: legacyURL).map(\.sessionID),
            ["batch-drain-kept", "batch-drain-kept"]
        )
        XCTAssertEqual(
            try store.listMessages(
                ownerDeviceID: "device-keeper",
                sessionID: "batch-drain-kept",
                limit: 10
            ).map(\.content),
            ["batch drain keeper", "batch append backfill"]
        )

        let drainedBatch = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
            on: store,
            now: Date(timeIntervalSince1970: 10_000),
            policy: policy
        )
        XCTAssertEqual(drainedBatch.prunedDeletedSessionCount, 0)
        XCTAssertEqual(try Data(contentsOf: legacyURL), compactedLegacyData)
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

    private func adaptiveV3CompactionFixture() -> (
        request: RuntimeChatStoredEvent,
        resolution: RuntimeChatCompactionResolution
    ) {
        let requestID = "bound-resolution-request"
        let sessionID = "bound-resolution-session"
        let messages = [
            ChatMessage(role: "user", content: "Original compacted question."),
            ChatMessage(role: "assistant", content: "Original compacted answer."),
            ChatMessage(role: "user", content: "Retained question."),
        ]
        var pointer = RuntimeChatCompactionSourcePointer(
            sessionID: sessionID,
            requestID: requestID,
            startTurn: 1,
            endTurn: 2,
            totalTurns: 3,
            compactedTurnCount: 2,
            retainedStartTurn: 3,
            retainedEndTurn: 3,
            retainedTurnCount: 1
        )
        let fingerprint = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: Array(messages.prefix(2))
        )
        pointer.sourceFingerprintAlgorithm = fingerprint.algorithm
        pointer.sourceFingerprint = fingerprint.digest
        pointer.sourceCanonicalByteCount = fingerprint.canonicalByteCount
        let estimatorIdentifier = "conservative_utf8_bytes_vision_framing_v2"
        let inputBudgetTokens = 7_168
        return (
            request: RuntimeChatStoredEvent(
                kind: .request,
                requestID: requestID,
                sessionID: sessionID,
                model: "ollama:llama3.1:8b",
                messages: messages,
                ownerDeviceID: "device-a",
                compactionMetadata: RuntimeChatCompactionMetadata(
                    strategy: "adaptive_backend_only_summary_v3",
                    sourcePointers: [pointer],
                    estimatorIdentifier: estimatorIdentifier,
                    contextWindowTokens: 8_192,
                    outputReserveTokens: 1_024,
                    inputBudgetTokens: inputBudgetTokens,
                    estimatedInputTokensBefore: 8_500,
                    estimatedInputTokensAfter: 6_900,
                    estimateKind: "planned_upper_bound",
                    summaryPolicy: "llm_prepass_with_deterministic_fallback_v1"
                )
            ),
            resolution: RuntimeChatCompactionResolution(
                primaryDispatched: true,
                summaryMethod: "llm_summary_v1",
                estimatorIdentifier: estimatorIdentifier,
                inputBudgetTokens: inputBudgetTokens,
                estimatedInputTokensAfter: 6_500
            )
        )
    }

    private func calibratedTerminal(
        request: RuntimeChatStoredEvent,
        resolution: RuntimeChatCompactionResolution,
        id: String
    ) -> RuntimeChatStoredEvent {
        var calibratedResolution = resolution
        calibratedResolution.resolvedProviderQualifiedModelID = "ollama:llama3.1:8b"
        let inputTokens = min(6_000, calibratedResolution.estimatedInputTokensAfter ?? 6_000)
        calibratedResolution.providerUsageCalibration = RuntimeChatProviderUsageCalibration(
            provider: "ollama",
            providerModelID: "llama3.1:8b",
            wireMode: "ollama_chat",
            inputTokens: inputTokens,
            relation: .withinConservativeEstimate
        )
        return RuntimeChatStoredEvent(
            id: id,
            kind: .done,
            requestID: request.requestID,
            sessionID: request.sessionID,
            model: request.model,
            finishReason: "stop",
            usage: RuntimeChatStoredUsage(inputTokens: inputTokens, outputTokens: 320),
            ownerDeviceID: request.ownerDeviceID,
            compactionResolution: calibratedResolution
        )
    }

    private func calibratedCompactionFixture(
        index: Int
    ) -> (request: RuntimeChatStoredEvent, terminal: RuntimeChatStoredEvent) {
        let fixture = adaptiveV3CompactionFixture()
        let requestID = "capped-calibration-request-\(index)"
        let sessionID = "capped-calibration-session-\(index)"
        var request = fixture.request
        request.id = "capped-calibration-request-event-\(index)"
        request.requestID = requestID
        request.sessionID = sessionID
        var metadata = request.compactionMetadata!
        var pointer = metadata.sourcePointers[0]
        pointer.requestID = requestID
        pointer.sessionID = sessionID
        let messages = request.messages ?? []
        let fingerprint = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: Array(messages.prefix(pointer.compactedTurnCount))
        )
        pointer.sourceFingerprintAlgorithm = fingerprint.algorithm
        pointer.sourceFingerprint = fingerprint.digest
        pointer.sourceCanonicalByteCount = fingerprint.canonicalByteCount
        metadata.sourcePointers = [pointer]
        request.compactionMetadata = metadata

        var resolution = fixture.resolution
        resolution.summaryMethod = "deterministic_preview_v1"
        resolution.estimatedInputTokensAfter = metadata.estimatedInputTokensAfter
        return (
            request,
            calibratedTerminal(
                request: request,
                resolution: resolution,
                id: "capped-calibration-terminal-\(index)"
            )
        )
    }

    private func appendDeletedSession(
        to store: any RuntimeChatEventStore,
        ownerDeviceID: String?,
        sessionID: String,
        requestTimestamp: TimeInterval,
        deletedTimestamp: TimeInterval
    ) throws {
        let ownerLabel = ownerDeviceID ?? "legacy"
        let requestID = "\(sessionID)-\(ownerLabel)-turn"
        try store.append(RuntimeChatStoredEvent(
            id: "\(requestID)-request",
            timestamp: Date(timeIntervalSince1970: requestTimestamp),
            kind: .request,
            requestID: requestID,
            sessionID: sessionID,
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "\(sessionID) \(ownerLabel)")],
            ownerDeviceID: ownerDeviceID
        ))
        _ = try store.mutateSession(
            ownerDeviceID: ownerDeviceID,
            sessionID: sessionID,
            requestID: "\(requestID)-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: deletedTimestamp - 1)
        )
        _ = try store.mutateSession(
            ownerDeviceID: ownerDeviceID,
            sessionID: sessionID,
            requestID: "\(requestID)-delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: deletedTimestamp)
        )
    }

    private func deletedSessionEvents(
        ownerDeviceID: String?,
        sessionID: String,
        requestTimestamp: TimeInterval,
        deletedTimestamp: TimeInterval
    ) -> [RuntimeChatStoredEvent] {
        let ownerLabel = ownerDeviceID ?? "legacy"
        let requestID = "\(sessionID)-\(ownerLabel)-turn"
        return [
            RuntimeChatStoredEvent(
                id: "\(requestID)-request",
                timestamp: Date(timeIntervalSince1970: requestTimestamp),
                kind: .request,
                requestID: requestID,
                sessionID: sessionID,
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "\(sessionID) \(ownerLabel)")],
                ownerDeviceID: ownerDeviceID
            ),
            RuntimeChatStoredEvent(
                id: "\(requestID)-archive",
                timestamp: Date(timeIntervalSince1970: deletedTimestamp - 1),
                kind: .archived,
                requestID: "\(requestID)-archive",
                sessionID: sessionID,
                model: "ollama:llama3.1:8b",
                ownerDeviceID: ownerDeviceID
            ),
            RuntimeChatStoredEvent(
                id: "\(requestID)-delete",
                timestamp: Date(timeIntervalSince1970: deletedTimestamp),
                kind: .deleted,
                requestID: "\(requestID)-delete",
                sessionID: sessionID,
                model: "ollama:llama3.1:8b",
                ownerDeviceID: ownerDeviceID
            ),
        ]
    }

    private func appendEqualRankingSessions(to store: any RuntimeChatEventStore) throws {
        let timestamp = Date(timeIntervalSince1970: 299)
        for sessionID in ["session-b", "session-a"] {
            try store.append(RuntimeChatStoredEvent(
                timestamp: timestamp,
                kind: .request,
                requestID: "request-\(sessionID)",
                sessionID: sessionID,
                model: "ollama:llama3.1:8b",
                messages: [ChatMessage(role: "user", content: "Deterministic lexical tie.")]
            ))
        }
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

    private func replaceRawSQLiteEventJSON(
        _ event: RuntimeChatStoredEvent,
        at databaseURL: URL
    ) throws {
        try replaceRawSQLiteEventJSONs([event], at: databaseURL)
    }

    private func replaceRawSQLiteEventJSONs(
        _ events: [RuntimeChatStoredEvent],
        at databaseURL: URL
    ) throws {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READWRITE, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 20)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(
            database,
            "UPDATE runtime_chat_events SET event_json = ? WHERE event_id = ?",
            -1,
            &statement,
            nil
        ) == SQLITE_OK,
              let statement else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 21)
        }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_exec(database, "BEGIN", nil, nil, nil) == SQLITE_OK else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 22)
        }
        do {
            for event in events {
                let data = try legacyJSONLEncoder.encode(event)
                let eventJSON = try XCTUnwrap(String(data: data, encoding: .utf8))
                guard sqlite3_reset(statement) == SQLITE_OK,
                      sqlite3_clear_bindings(statement) == SQLITE_OK,
                      sqlite3_bind_text(
                        statement,
                        1,
                        eventJSON,
                        -1,
                        sqliteRuntimeChatTestTransient
                      ) == SQLITE_OK,
                      sqlite3_bind_text(
                        statement,
                        2,
                        event.id,
                        -1,
                        sqliteRuntimeChatTestTransient
                      ) == SQLITE_OK,
                      sqlite3_step(statement) == SQLITE_DONE else {
                    throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 23)
                }
            }
            guard sqlite3_exec(database, "COMMIT", nil, nil, nil) == SQLITE_OK else {
                throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 24)
            }
        } catch {
            _ = sqlite3_exec(database, "ROLLBACK", nil, nil, nil)
            throw error
        }
    }

    private func replaceRawSQLiteEventJSONString(
        eventID: String,
        eventJSON: String,
        at databaseURL: URL
    ) throws {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READWRITE, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 25)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(
            database,
            "UPDATE runtime_chat_events SET event_json = ? WHERE event_id = ?",
            -1,
            &statement,
            nil
        ) == SQLITE_OK,
              let statement else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 26)
        }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_bind_text(
            statement,
            1,
            eventJSON,
            -1,
            sqliteRuntimeChatTestTransient
        ) == SQLITE_OK,
              sqlite3_bind_text(
                statement,
                2,
                eventID,
                -1,
                sqliteRuntimeChatTestTransient
              ) == SQLITE_OK,
              sqlite3_step(statement) == SQLITE_DONE else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 27)
        }
    }

    private func executeRawSQLite(_ sql: String, at databaseURL: URL) throws {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READWRITE, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 30)
        }
        defer { sqlite3_close(database) }
        guard sqlite3_exec(database, sql, nil, nil, nil) == SQLITE_OK else {
            throw NSError(
                domain: "SQLiteRuntimeChatEventStoreTests",
                code: 31,
                userInfo: [
                    NSLocalizedDescriptionKey: sqlite3_errmsg(database).map { String(cString: $0) } ?? "SQLite write failed"
                ]
            )
        }
    }

    private func insertRawFTSSession(
        ownerKey: String,
        sessionID: String,
        at databaseURL: URL
    ) throws {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READWRITE, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 32)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(
            database,
            """
            INSERT INTO runtime_chat_session_fts(
                owner_key, session_id, title, indexed_session_id, model,
                status, metadata, transcript, reasoning, attachment
            ) VALUES (?, ?, '', '', '', '', '', 'stale retention row', '', '')
            """,
            -1,
            &statement,
            nil
        ) == SQLITE_OK,
              let statement else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 33)
        }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_bind_text(statement, 1, ownerKey, -1, sqliteRuntimeChatTestTransient) == SQLITE_OK,
              sqlite3_bind_text(statement, 2, sessionID, -1, sqliteRuntimeChatTestTransient) == SQLITE_OK,
              sqlite3_step(statement) == SQLITE_DONE else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 34)
        }
    }

    private func rawSQLiteInt(_ sql: String, at databaseURL: URL) throws -> Int {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 35)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 36)
        }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 37)
        }
        return Int(sqlite3_column_int64(statement, 0))
    }

    private func rawFTSSessionKeys(at databaseURL: URL) throws -> [String] {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 38)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(
            database,
            "SELECT owner_key, session_id FROM runtime_chat_session_fts ORDER BY owner_key, session_id",
            -1,
            &statement,
            nil
        ) == SQLITE_OK,
              let statement else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 39)
        }
        defer { sqlite3_finalize(statement) }
        var keys: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW,
                  let ownerKey = sqlite3_column_text(statement, 0),
                  let sessionID = sqlite3_column_text(statement, 1) else {
                throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 40)
            }
            keys.append("\(String(cString: ownerKey))|\(String(cString: sessionID))")
        }
        return keys
    }

    private func rawFTSSessionRowIDs(at databaseURL: URL) throws -> [String: Int64] {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 41)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(
            database,
            "SELECT rowid, owner_key, session_id FROM runtime_chat_session_fts",
            -1,
            &statement,
            nil
        ) == SQLITE_OK,
              let statement else {
            throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 42)
        }
        defer { sqlite3_finalize(statement) }
        var rowIDs: [String: Int64] = [:]
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW,
                  let ownerKey = sqlite3_column_text(statement, 1),
                  let sessionID = sqlite3_column_text(statement, 2) else {
                throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 43)
            }
            let key = "\(String(cString: ownerKey))|\(String(cString: sessionID))"
            guard rowIDs.updateValue(sqlite3_column_int64(statement, 0), forKey: key) == nil else {
                throw NSError(domain: "SQLiteRuntimeChatEventStoreTests", code: 44)
            }
        }
        return rowIDs
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

    private func rawEventJSON(
        _ event: RuntimeChatStoredEvent,
        replacingCalibrationPayloadWith payload: Any
    ) throws -> String {
        let data = try legacyJSONLEncoder.encode(event)
        var object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: data) as? [String: Any]
        )
        var resolution = try XCTUnwrap(
            object["compaction_resolution"] as? [String: Any]
        )
        resolution["provider_usage_calibration"] = payload
        object["compaction_resolution"] = resolution
        let tamperedData = try JSONSerialization.data(
            withJSONObject: object,
            options: [.sortedKeys]
        )
        return try XCTUnwrap(String(data: tamperedData, encoding: .utf8))
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

private final class SQLiteRuntimeChatConcurrentResultBox<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var value: Value?

    func store(_ value: Value) {
        lock.lock()
        self.value = value
        lock.unlock()
    }

    func load() -> Value? {
        lock.lock()
        defer { lock.unlock() }
        return value
    }
}

private let sqliteRuntimeChatTestTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
