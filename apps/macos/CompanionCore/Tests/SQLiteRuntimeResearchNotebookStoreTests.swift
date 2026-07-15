import Foundation
@testable import CompanionCore
import SQLite3
import XCTest

final class SQLiteRuntimeResearchNotebookStoreTests: XCTestCase {
    func testReopenParitySchemaPrivacyGrantOrderAndOwnerOnlyPermissions() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeResearchNotebookStore(
            databaseURL: databaseURL,
            now: { Date(timeIntervalSince1970: 123) }
        )
        let grants = [grantID("3"), grantID("1"), grantID("2")]
        let created = try store.create(
            ownerDeviceID: "owner-a",
            notebookID: notebookID("1"),
            backingSessionID: "runtime-session-a",
            title: "Research title",
            model: "ollama:model-a",
            trustedSourceGrantIDs: grants
        )

        let reopened = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.get(ownerDeviceID: "owner-a", notebookID: created.notebookID), created)
        XCTAssertEqual(
            try reopened.getByBackingSessionID(ownerDeviceID: "owner-a", backingSessionID: "runtime-session-a"),
            created
        )
        XCTAssertEqual(try rawGrantIDs(databaseURL), grants)
        XCTAssertEqual(try queryInt(databaseURL, "PRAGMA user_version"), 3)
        XCTAssertEqual(
            try tableColumns(databaseURL, table: "runtime_research_notebooks"),
            ["notebook_id", "owner_device_id", "backing_session_id", "title", "model", "lifecycle", "created_at", "updated_at"]
        )
        XCTAssertEqual(
            try tableColumns(databaseURL, table: "runtime_research_notebook_grants"),
            ["notebook_id", "position", "grant_id"]
        )
        XCTAssertEqual(
            try tableColumns(databaseURL, table: "runtime_research_notebook_lifecycle_intents"),
            [
                "notebook_id", "owner_device_id", "backing_session_id", "mutation",
                "coordinator_id", "operation_id", "lease_expires_at",
            ]
        )
        let attributes = try FileManager.default.attributesOfItem(atPath: databaseURL.path)
        XCTAssertEqual((attributes[.posixPermissions] as? NSNumber)?.intValue, 0o600)

        let schema = try queryStrings(
            databaseURL,
            "SELECT sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).joined(separator: " ").lowercased()
        for forbidden in ["prompt", "brief", "result_body", "snippet", "path", "url", "endpoint", "token", "source_text"] {
            XCTAssertFalse(schema.contains(forbidden), "Unexpected persisted field: \(forbidden)")
        }
    }

    func testOwnerIsolationStrictCollisionsLifecycleDeleteAndReopen() throws {
        let clock = SQLiteNotebookClock([100, 200, 300])
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL, now: { clock.now() })
        let first = try create(store, owner: "owner-a", notebook: "1", session: "session-a")

        XCTAssertThrowsError(try create(store, owner: "owner-b", notebook: "1", session: "session-b")) {
            XCTAssertEqual($0 as? RuntimeResearchNotebookStoreError, .notebookIDCollision)
        }
        XCTAssertThrowsError(try create(store, owner: "owner-a", notebook: "2", session: "session-a")) {
            XCTAssertEqual($0 as? RuntimeResearchNotebookStoreError, .backingSessionIDCollision)
        }
        XCTAssertNil(try store.get(ownerDeviceID: "owner-b", notebookID: first.notebookID))
        XCTAssertNil(try store.archive(ownerDeviceID: "owner-b", notebookID: first.notebookID))
        XCTAssertFalse(try store.delete(ownerDeviceID: "owner-b", notebookID: first.notebookID))

        let archived = try XCTUnwrap(try store.archive(ownerDeviceID: "owner-a", notebookID: first.notebookID))
        XCTAssertEqual(archived.lifecycle, .archived)
        XCTAssertEqual(archived.updatedAt, Date(timeIntervalSince1970: 200))
        XCTAssertEqual(try store.archive(ownerDeviceID: "owner-a", notebookID: first.notebookID), archived)
        let restored = try XCTUnwrap(try store.restore(ownerDeviceID: "owner-a", notebookID: first.notebookID))
        XCTAssertEqual(restored.lifecycle, .active)
        XCTAssertEqual(restored.updatedAt, Date(timeIntervalSince1970: 300))
        XCTAssertEqual(try store.restore(ownerDeviceID: "owner-a", notebookID: first.notebookID), restored)

        let reopened = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.get(ownerDeviceID: "owner-a", notebookID: first.notebookID), restored)
        XCTAssertTrue(try reopened.delete(ownerDeviceID: "owner-a", notebookID: first.notebookID))
        XCTAssertFalse(try reopened.delete(ownerDeviceID: "owner-a", notebookID: first.notebookID))
        XCTAssertNil(try SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
            .getByBackingSessionID(ownerDeviceID: "owner-a", backingSessionID: "session-a"))
    }

    func testOrderingFiltersLimitsBoundsAndValidationMatchMemoryStore() throws {
        let clock = SQLiteNotebookClock([100, 200, 200, 300])
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeResearchNotebookStore(
            databaseURL: databaseURL,
            rowLimitPerOwner: 3,
            now: { clock.now() }
        )
        let first = try create(store, owner: "owner", notebook: "3", session: "session-3")
        let second = try create(store, owner: "owner", notebook: "2", session: "session-2")
        let third = try create(store, owner: "owner", notebook: "1", session: "session-1")

        XCTAssertEqual(
            try store.list(ownerDeviceID: "owner", limit: 2).map(\.notebookID),
            [third.notebookID, second.notebookID]
        )
        let archived = try XCTUnwrap(try store.archive(ownerDeviceID: "owner", notebookID: first.notebookID))
        XCTAssertEqual(try store.list(ownerDeviceID: "owner", lifecycle: .archived).map(\.notebookID), [archived.notebookID])
        XCTAssertEqual(try store.list(ownerDeviceID: "owner", lifecycle: .active).map(\.notebookID), [third.notebookID, second.notebookID])
        XCTAssertThrowsError(try store.list(ownerDeviceID: "owner", limit: 0))
        XCTAssertEqual(try store.list(ownerDeviceID: "owner", limit: 101).count, 3)
        XCTAssertThrowsError(
            try store.list(
                ownerDeviceID: "owner",
                limit: RuntimeResearchNotebook.maximumStoreListLimit + 1
            )
        )
        XCTAssertThrowsError(try create(store, owner: "owner", notebook: "4", session: "session-4")) {
            XCTAssertEqual($0 as? RuntimeResearchNotebookStoreError, .rowLimitReached)
        }

        XCTAssertTrue(try store.delete(ownerDeviceID: "owner", notebookID: second.notebookID))
        let reused = try create(store, owner: "owner", notebook: "4", session: "session-2")
        XCTAssertEqual(
            try SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
                .getByBackingSessionID(ownerDeviceID: "owner", backingSessionID: "session-2"),
            reused
        )
    }

    func testLifecycleIntentsPersistAcrossReopenAndCompleteOrCancelAtomically() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        let createIntent = try store.createPendingChatPersistence(
            ownerDeviceID: "owner",
            notebookID: notebookID("a"),
            backingSessionID: "session-a",
            title: "Pending create",
            model: "ollama:model",
            trustedSourceGrantIDs: [grantID("a")],
            coordinatorID: String(repeating: "1", count: 32),
            operationID: String(repeating: "2", count: 32),
            leaseExpiresAt: Date(timeIntervalSince1970: 1_000)
        )
        XCTAssertEqual(createIntent.mutation, .create)

        let reopened = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        XCTAssertEqual(try reopened.pendingLifecycleMutations(ownerDeviceID: "owner"), [createIntent])
        try reopened.completeLifecycleMutation(createIntent)
        XCTAssertNotNil(try reopened.get(ownerDeviceID: "owner", notebookID: notebookID("a")))
        XCTAssertTrue(try reopened.pendingLifecycleMutations(ownerDeviceID: "owner").isEmpty)

        let deleteIntent = try XCTUnwrap(try reopened.prepareLifecycleMutation(
            ownerDeviceID: "owner",
            backingSessionID: "session-a",
            mutation: .delete,
            coordinatorID: String(repeating: "1", count: 32),
            operationID: String(repeating: "3", count: 32),
            leaseExpiresAt: Date(timeIntervalSince1970: 2_000)
        ))
        XCTAssertEqual(
            try SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
                .pendingLifecycleMutations(ownerDeviceID: "owner"),
            [deleteIntent]
        )
        try reopened.completeLifecycleMutation(deleteIntent)
        XCTAssertNil(try reopened.get(ownerDeviceID: "owner", notebookID: notebookID("a")))

        let cancelledCreate = try reopened.createPendingChatPersistence(
            ownerDeviceID: "owner",
            notebookID: notebookID("b"),
            backingSessionID: "session-b",
            title: "Cancelled create",
            model: "ollama:model",
            trustedSourceGrantIDs: [grantID("b")],
            coordinatorID: String(repeating: "1", count: 32),
            operationID: String(repeating: "4", count: 32),
            leaseExpiresAt: Date(timeIntervalSince1970: 3_000)
        )
        try reopened.cancelLifecycleMutation(cancelledCreate)
        XCTAssertNil(try reopened.get(ownerDeviceID: "owner", notebookID: notebookID("b")))
        XCTAssertTrue(try reopened.pendingLifecycleMutations(ownerDeviceID: "owner").isEmpty)
    }

    func testLifecycleIntentRenewalPersistsAndFencesStaleLease() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        _ = try create(store, owner: "owner", notebook: "1", session: "session")
        let original = try XCTUnwrap(try store.prepareLifecycleMutation(
            ownerDeviceID: "owner",
            backingSessionID: "session",
            mutation: .archive,
            coordinatorID: String(repeating: "a", count: 32),
            operationID: String(repeating: "b", count: 32),
            leaseExpiresAt: Date(timeIntervalSince1970: 100)
        ))
        let renewed = try store.renewLifecycleMutation(
            original,
            leaseExpiresAt: Date(timeIntervalSince1970: 200)
        )
        XCTAssertEqual(
            try SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
                .pendingLifecycleMutations(ownerDeviceID: "owner"),
            [renewed]
        )
        XCTAssertThrowsError(try store.renewLifecycleMutation(
            original,
            leaseExpiresAt: Date(timeIntervalSince1970: 300)
        )) { error in
            guard case RuntimeResearchNotebookStoreError.storageFailure = error else {
                return XCTFail("Expected stale-lease fencing, got \(error)")
            }
        }
        try store.completeLifecycleMutation(renewed)
        XCTAssertEqual(
            try store.get(ownerDeviceID: "owner", notebookID: notebookID("1"))?.lifecycle,
            .archived
        )
    }

    func testPendingCreateCanRenewLeaseBeforeCompletion() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        let pending: RuntimeResearchNotebookLifecycleIntent
        do {
            pending = try store.createPendingChatPersistence(
                ownerDeviceID: "aetherlink-auth-smoke-device",
                notebookID: notebookID("c"),
                backingSessionID: "smoke-session-research-\(UUID().uuidString.lowercased())",
                title: "Build a brief from the approved seeded runtime source.",
                model: "dev-mock",
                trustedSourceGrantIDs: [grantID("c")],
                coordinatorID: UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased(),
                operationID: UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased(),
                leaseExpiresAt: Date(timeIntervalSince1970: 100)
            )
        } catch {
            return XCTFail("Pending create failed: \(error)")
        }
        let renewed: RuntimeResearchNotebookLifecycleIntent
        do {
            renewed = try store.renewLifecycleMutation(
                pending,
                leaseExpiresAt: try nonSQLiteCanonicalDate()
            )
        } catch {
            return XCTFail("Lease renewal failed: \(error)")
        }
        let persisted = try XCTUnwrap(
            store.pendingLifecycleMutations(ownerDeviceID: renewed.ownerDeviceID).first
        )
        XCTAssertEqual(
            persisted,
            renewed,
            "persisted=\(persisted.leaseExpiresAt.timeIntervalSince1970.bitPattern) "
                + "renewed=\(renewed.leaseExpiresAt.timeIntervalSince1970.bitPattern)"
        )
        do {
            try store.completeLifecycleMutation(renewed)
        } catch {
            return XCTFail("Completion failed: \(error)")
        }

        XCTAssertEqual(
            try store.get(ownerDeviceID: renewed.ownerDeviceID, notebookID: renewed.notebookID)?
                .backingSessionID,
            renewed.backingSessionID
        )
        XCTAssertTrue(
            try store.pendingLifecycleMutations(ownerDeviceID: renewed.ownerDeviceID).isEmpty
        )
    }

    func testPendingCreateDateRoundTripsBeforeDirectCompletion() throws {
        let store = SQLiteRuntimeResearchNotebookStore(databaseURL: temporaryDatabaseURL())
        let leaseExpiresAt = try nonSQLiteCanonicalDate()
        let pending = try store.createPendingChatPersistence(
            ownerDeviceID: "owner",
            notebookID: notebookID("e"),
            backingSessionID: "session-e",
            title: "Direct pending create",
            model: "dev-mock",
            trustedSourceGrantIDs: [grantID("e")],
            coordinatorID: String(repeating: "a", count: 32),
            operationID: String(repeating: "b", count: 32),
            leaseExpiresAt: leaseExpiresAt
        )

        XCTAssertNotEqual(leaseExpiresAt, sqliteCanonicalDate(leaseExpiresAt))
        XCTAssertEqual(pending.leaseExpiresAt, sqliteCanonicalDate(leaseExpiresAt))
        XCTAssertEqual(try store.pendingLifecycleMutations(ownerDeviceID: "owner"), [pending])
        try store.completeLifecycleMutation(pending)

        XCTAssertNotNil(try store.get(ownerDeviceID: "owner", notebookID: notebookID("e")))
        XCTAssertTrue(try store.pendingLifecycleMutations(ownerDeviceID: "owner").isEmpty)
    }

    func testPreparedLifecycleMutationDateRoundTripsBeforeCompletion() throws {
        let store = SQLiteRuntimeResearchNotebookStore(databaseURL: temporaryDatabaseURL())
        _ = try create(store, owner: "owner", notebook: "d", session: "session-d")
        let leaseExpiresAt = try nonSQLiteCanonicalDate()
        let intent = try XCTUnwrap(try store.prepareLifecycleMutation(
            ownerDeviceID: "owner",
            backingSessionID: "session-d",
            mutation: .archive,
            coordinatorID: String(repeating: "a", count: 32),
            operationID: String(repeating: "b", count: 32),
            leaseExpiresAt: leaseExpiresAt
        ))

        XCTAssertNotEqual(leaseExpiresAt, sqliteCanonicalDate(leaseExpiresAt))
        XCTAssertEqual(intent.leaseExpiresAt, sqliteCanonicalDate(leaseExpiresAt))
        XCTAssertEqual(try store.pendingLifecycleMutations(ownerDeviceID: "owner"), [intent])
        try store.completeLifecycleMutation(intent)

        XCTAssertEqual(
            try store.get(ownerDeviceID: "owner", notebookID: notebookID("d"))?.lifecycle,
            .archived
        )
    }

    func testLifecycleCoordinationIsSharedAcrossStoreInstances() {
        let databaseURL = temporaryDatabaseURL()
        let first = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        let second = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        let firstEntered = DispatchSemaphore(value: 0)
        let releaseFirst = DispatchSemaphore(value: 0)
        let secondEntered = DispatchSemaphore(value: 0)
        let group = DispatchGroup()

        group.enter()
        DispatchQueue.global().async {
            first.withLifecycleCoordination {
                _ = firstEntered.signal()
                releaseFirst.wait()
            }
            group.leave()
        }
        XCTAssertEqual(firstEntered.wait(timeout: .now() + 10), .success)

        group.enter()
        DispatchQueue.global().async {
            second.withLifecycleCoordination {
                _ = secondEntered.signal()
            }
            group.leave()
        }
        XCTAssertEqual(secondEntered.wait(timeout: .now() + 0.1), .timedOut)

        releaseFirst.signal()
        XCTAssertEqual(secondEntered.wait(timeout: .now() + 10), .success)
        XCTAssertEqual(group.wait(timeout: .now() + 10), .success)
    }

    func testTrueV2PendingIntentMigratesToExpiredCanonicalV3Intent() throws {
        let databaseURL = temporaryDatabaseURL()
        let notebookID = notebookID("2")
        let grantID = grantID("2")
        try seedLegacyPendingIntentFixture(
            databaseURL,
            version: 2,
            notebookID: notebookID,
            grantID: grantID
        )

        let store = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        let pending = try store.pendingLifecycleMutations(ownerDeviceID: "owner-v2")
        let intent = try XCTUnwrap(pending.first)
        XCTAssertEqual(pending.count, 1)
        XCTAssertEqual(intent.notebookID, notebookID)
        XCTAssertEqual(intent.backingSessionID, "session-v2")
        XCTAssertEqual(intent.mutation, .archive)
        XCTAssertTrue(isCanonicalLifecycleID(intent.coordinatorID))
        XCTAssertTrue(isCanonicalLifecycleID(intent.operationID))
        XCTAssertEqual(intent.operationID, String(notebookID.suffix(32)))
        XCTAssertEqual(intent.leaseExpiresAt, Date(timeIntervalSince1970: 0))
        XCTAssertEqual(try queryInt(databaseURL, "PRAGMA user_version"), 3)
        XCTAssertEqual(
            try store.get(ownerDeviceID: "owner-v2", notebookID: notebookID)?.trustedSourceGrantIDs,
            [grantID]
        )
    }

    func testV1MigrationDoesNotTrustAmbiguousPendingIntentRows() throws {
        let databaseURL = temporaryDatabaseURL()
        let notebookID = notebookID("1")
        try seedLegacyPendingIntentFixture(
            databaseURL,
            version: 1,
            notebookID: notebookID,
            grantID: grantID("1")
        )

        let store = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        XCTAssertTrue(try store.pendingLifecycleMutations(ownerDeviceID: "owner-v1").isEmpty)
        XCTAssertNotNil(try store.get(ownerDeviceID: "owner-v1", notebookID: notebookID))
        XCTAssertEqual(try queryInt(databaseURL, "PRAGMA user_version"), 3)
    }

    func testMalformedNotebookAndGrantRowsFailClosed() throws {
        let malformedNotebookURL = temporaryDatabaseURL()
        let first = SQLiteRuntimeResearchNotebookStore(databaseURL: malformedNotebookURL)
        let notebook = try create(first, owner: "owner", notebook: "1", session: "session")
        try executeRaw(
            malformedNotebookURL,
            "UPDATE runtime_research_notebooks SET title = CAST(X'01' AS BLOB)"
        )
        XCTAssertThrowsError(try SQLiteRuntimeResearchNotebookStore(databaseURL: malformedNotebookURL)
            .get(ownerDeviceID: "owner", notebookID: notebook.notebookID)) {
            XCTAssertEqual($0 as? RuntimeResearchNotebookStoreError, .corruptPersistence)
        }

        let malformedGrantURL = temporaryDatabaseURL()
        let second = SQLiteRuntimeResearchNotebookStore(databaseURL: malformedGrantURL)
        _ = try create(second, owner: "owner", notebook: "2", session: "session")
        try executeRaw(
            malformedGrantURL,
            "UPDATE runtime_research_notebook_grants SET grant_id = CAST(X'01' AS BLOB)"
        )
        XCTAssertThrowsError(try SQLiteRuntimeResearchNotebookStore(databaseURL: malformedGrantURL)
            .list(ownerDeviceID: "owner")) {
            XCTAssertEqual($0 as? RuntimeResearchNotebookStoreError, .corruptPersistence)
        }
    }

    func testConcurrentCreateCollisionAcrossStoreInstancesCommitsExactlyOneRow() throws {
        let databaseURL = temporaryDatabaseURL()
        let first = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        let second = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
        let results = SQLiteNotebookConcurrentResults()
        let group = DispatchGroup()
        let start = DispatchSemaphore(value: 0)

        for (offset, store) in [first, second].enumerated() {
            group.enter()
            DispatchQueue.global().async {
                start.wait()
                do {
                    let notebook = try store.create(
                        ownerDeviceID: "owner",
                        notebookID: self.notebookID("f"),
                        backingSessionID: "session-\(offset)",
                        title: "Concurrent title",
                        model: "ollama:model",
                        trustedSourceGrantIDs: [self.grantID("f")]
                    )
                    results.append(.success(notebook))
                } catch {
                    results.append(.failure(error))
                }
                group.leave()
            }
        }
        start.signal()
        start.signal()
        XCTAssertEqual(group.wait(timeout: .now() + 10), .success)

        let snapshot = results.snapshot
        XCTAssertEqual(snapshot.compactMap { try? $0.get() }.count, 1)
        XCTAssertEqual(
            snapshot.compactMap { result -> RuntimeResearchNotebookStoreError? in
                guard case .failure(let error) = result else { return nil }
                return error as? RuntimeResearchNotebookStoreError
            },
            [.notebookIDCollision]
        )
        XCTAssertEqual(
            try SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
                .list(ownerDeviceID: "owner").count,
            1
        )
    }

    func testConcurrentLegacyMigrationRechecksLockedVersionBeforePreservingV3Intent() throws {
        for legacyVersion in [1, 2] {
            let databaseURL = temporaryDatabaseURL()
            let seedStore = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
            _ = try create(
                seedStore,
                owner: "owner-v\(legacyVersion)",
                notebook: "\(legacyVersion)",
                session: "session-v\(legacyVersion)"
            )
            XCTAssertTrue(
                try seedStore.pendingLifecycleMutations(ownerDeviceID: "owner-v\(legacyVersion)").isEmpty
            )
            try executeRaw(databaseURL, "PRAGMA user_version = \(legacyVersion)")

            let writer = SQLiteRuntimeResearchNotebookStore(databaseURL: databaseURL)
            let coordinatorID = String(repeating: "a", count: 32)
            let operationID = String(repeating: "b", count: 31) + "\(legacyVersion)"
            let migrator = SQLiteRuntimeResearchNotebookStore(
                databaseURL: databaseURL,
                beforeSchemaMigrationLock: { observedVersion in
                    XCTAssertEqual(observedVersion, legacyVersion)
                    _ = try writer.prepareLifecycleMutation(
                        ownerDeviceID: "owner-v\(legacyVersion)",
                        backingSessionID: "session-v\(legacyVersion)",
                        mutation: .archive,
                        coordinatorID: coordinatorID,
                        operationID: operationID,
                        leaseExpiresAt: Date(timeIntervalSince1970: 10_000 + Double(legacyVersion))
                    )
                }
            )

            let pending = try migrator.pendingLifecycleMutations(
                ownerDeviceID: "owner-v\(legacyVersion)"
            )
            XCTAssertEqual(pending.count, 1)
            XCTAssertEqual(pending.first?.mutation, .archive)
            XCTAssertEqual(pending.first?.coordinatorID, coordinatorID)
            XCTAssertEqual(pending.first?.operationID, operationID)
            XCTAssertEqual(try queryInt(databaseURL, "PRAGMA user_version"), 3)
        }
    }

    private func create(
        _ store: SQLiteRuntimeResearchNotebookStore,
        owner: String,
        notebook: String,
        session: String
    ) throws -> RuntimeResearchNotebook {
        try store.create(
            ownerDeviceID: owner,
            notebookID: notebookID(notebook),
            backingSessionID: session,
            title: "Research title \(notebook)",
            model: "ollama:model-\(notebook)",
            trustedSourceGrantIDs: [grantID(notebook)]
        )
    }

    private func notebookID(_ digit: String) -> String {
        "research_notebook_" + String(repeating: "0", count: 32 - digit.count) + digit
    }

    private func grantID(_ digit: String) -> String {
        "trusted_source_" + String(repeating: "0", count: 32 - digit.count) + digit
    }

    private func temporaryDatabaseURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent("runtime-research-notebook-\(UUID().uuidString)", isDirectory: true)
            .appendingPathComponent("notebooks.sqlite", isDirectory: false)
    }

    private func nonSQLiteCanonicalDate(
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws -> Date {
        let candidate = (0..<4_096)
            .lazy
            .map { offset in
                Date().addingTimeInterval(Double(offset) / 1_000_000_000)
            }
            .first { value in
                value != sqliteCanonicalDate(value)
            }
        return try XCTUnwrap(
            candidate,
            "Could not produce a Date with precision beyond SQLite Double storage.",
            file: file,
            line: line
        )
    }

    private func sqliteCanonicalDate(_ value: Date) -> Date {
        Date(timeIntervalSince1970: value.timeIntervalSince1970)
    }

    private func rawGrantIDs(_ databaseURL: URL) throws -> [String] {
        try queryStrings(
            databaseURL,
            "SELECT grant_id FROM runtime_research_notebook_grants ORDER BY position ASC"
        )
    }

    private func tableColumns(_ databaseURL: URL, table: String) throws -> Set<String> {
        Set(try queryStrings(databaseURL, "PRAGMA table_info(\(table))", column: 1))
    }

    private func queryInt(_ databaseURL: URL, _ sql: String) throws -> Int {
        var database: OpaquePointer?
        XCTAssertEqual(sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY, nil), SQLITE_OK)
        let opened = try XCTUnwrap(database)
        defer { sqlite3_close(opened) }
        var statement: OpaquePointer?
        XCTAssertEqual(sqlite3_prepare_v2(opened, sql, -1, &statement, nil), SQLITE_OK)
        let prepared = try XCTUnwrap(statement)
        defer { sqlite3_finalize(prepared) }
        XCTAssertEqual(sqlite3_step(prepared), SQLITE_ROW)
        return Int(sqlite3_column_int64(prepared, 0))
    }

    private func queryStrings(
        _ databaseURL: URL,
        _ sql: String,
        column: Int32 = 0
    ) throws -> [String] {
        var database: OpaquePointer?
        XCTAssertEqual(sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY, nil), SQLITE_OK)
        let opened = try XCTUnwrap(database)
        defer { sqlite3_close(opened) }
        var statement: OpaquePointer?
        XCTAssertEqual(sqlite3_prepare_v2(opened, sql, -1, &statement, nil), SQLITE_OK)
        let prepared = try XCTUnwrap(statement)
        defer { sqlite3_finalize(prepared) }
        var values: [String] = []
        while sqlite3_step(prepared) == SQLITE_ROW {
            values.append(String(cString: sqlite3_column_text(prepared, column)))
        }
        return values
    }

    private func executeRaw(_ databaseURL: URL, _ sql: String) throws {
        var database: OpaquePointer?
        XCTAssertEqual(
            sqlite3_open_v2(
                databaseURL.path,
                &database,
                SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE,
                nil
            ),
            SQLITE_OK
        )
        let opened = try XCTUnwrap(database)
        defer { sqlite3_close(opened) }
        XCTAssertEqual(sqlite3_exec(opened, sql, nil, nil, nil), SQLITE_OK)
    }

    private func seedLegacyPendingIntentFixture(
        _ databaseURL: URL,
        version: Int,
        notebookID: String,
        grantID: String
    ) throws {
        try FileManager.default.createDirectory(
            at: databaseURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try executeRaw(
            databaseURL,
            """
            CREATE TABLE runtime_research_notebooks(
                notebook_id TEXT PRIMARY KEY NOT NULL,
                owner_device_id TEXT NOT NULL,
                backing_session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                model TEXT NOT NULL,
                lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active', 'archived')),
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL CHECK(updated_at >= created_at),
                UNIQUE(owner_device_id, backing_session_id)
            );
            CREATE TABLE runtime_research_notebook_grants(
                notebook_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                grant_id TEXT NOT NULL,
                PRIMARY KEY(notebook_id, position),
                FOREIGN KEY(notebook_id) REFERENCES runtime_research_notebooks(notebook_id)
                    ON DELETE CASCADE
            );
            CREATE TABLE runtime_research_notebook_lifecycle_intents(
                notebook_id TEXT PRIMARY KEY NOT NULL,
                owner_device_id TEXT NOT NULL,
                backing_session_id TEXT NOT NULL,
                mutation TEXT NOT NULL
            );
            CREATE TABLE runtime_research_notebook_store_metadata(
                singleton INTEGER PRIMARY KEY NOT NULL,
                schema_version INTEGER NOT NULL
            );
            INSERT INTO runtime_research_notebooks VALUES(
                '\(notebookID)', 'owner-v\(version)', 'session-v\(version)',
                'Legacy notebook', 'ollama:model', 'active', 10, 10
            );
            INSERT INTO runtime_research_notebook_grants VALUES(
                '\(notebookID)', 0, '\(grantID)'
            );
            INSERT INTO runtime_research_notebook_lifecycle_intents VALUES(
                '\(notebookID)', 'owner-v\(version)', 'session-v\(version)', 'archive'
            );
            INSERT INTO runtime_research_notebook_store_metadata VALUES(1, \(version));
            PRAGMA user_version = \(version);
            """
        )
    }

    private func isCanonicalLifecycleID(_ value: String) -> Bool {
        value.utf8.count == 32 && value.utf8.allSatisfy { byte in
            (48...57).contains(byte) || (97...102).contains(byte)
        }
    }
}

private final class SQLiteNotebookClock: @unchecked Sendable {
    private let lock = NSLock()
    private let timestamps: [TimeInterval]
    private var index = 0

    init(_ timestamps: [TimeInterval]) {
        self.timestamps = timestamps
    }

    func now() -> Date {
        lock.lock()
        defer { lock.unlock() }
        let timestamp = timestamps[min(index, timestamps.count - 1)]
        index += 1
        return Date(timeIntervalSince1970: timestamp)
    }
}

private final class SQLiteNotebookConcurrentResults: @unchecked Sendable {
    private let lock = NSLock()
    private var values: [Result<RuntimeResearchNotebook, Error>] = []

    func append(_ value: Result<RuntimeResearchNotebook, Error>) {
        lock.lock()
        defer { lock.unlock() }
        values.append(value)
    }

    var snapshot: [Result<RuntimeResearchNotebook, Error>] {
        lock.lock()
        defer { lock.unlock() }
        return values
    }
}
