import Foundation
@testable import CompanionCore
import SQLite3
import XCTest

final class RuntimeModelPullApprovalStoreTests: XCTestCase {
    func testDurableBytesAndSchemaContainOnlyRedactedApprovalMetadata() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        let operationID = operationID(1)
        let digest = requestBindingDigest("a")

        _ = try store.createRequest(
            operationID: operationID,
            requestBindingDigest: digest,
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(300)
        )
        _ = try store.reserveDispatch(
            operationID: operationID,
            requestBindingDigest: digest,
            at: date(200)
        )
        _ = try store.recordTerminal(operationID: operationID, event: .success, at: date(250))

        XCTAssertEqual(
            try tableColumns(databaseURL, table: "runtime_model_pull_approval_operations"),
            [
                "operation_id", "request_binding_digest", "provider_code",
                "action_id", "policy_revision", "current_event_code", "outcome_code",
                "created_at_ms", "updated_at_ms", "expires_at_ms", "schema_version",
            ]
        )
        XCTAssertEqual(
            try tableColumns(databaseURL, table: "runtime_model_pull_approval_events"),
            [
                "operation_id", "event_order", "event_code", "outcome_code",
                "occurred_at_ms", "schema_version",
            ]
        )
        let record = try XCTUnwrap(store.record(operationID: operationID))
        XCTAssertEqual(record.actionID, RuntimePermissionPolicyRegistry.modelPullActionID)
        XCTAssertEqual(record.policyRevision, RuntimePermissionPolicyRegistry.modelPullRevision)
        XCTAssertTrue(
            try store.recentEvents(limit: 10).allSatisfy {
                $0.actionID == RuntimePermissionPolicyRegistry.modelPullActionID &&
                    $0.policyRevision == RuntimePermissionPolicyRegistry.modelPullRevision
            }
        )

        let forbiddenValues = [
            "private-model-name", "request-id-secret", "device-id-secret",
            "device-name-secret", "transport-binding-secret", "https://secret.invalid",
            "credential-secret", "backend-error-secret",
        ]
        let durableFiles = try FileManager.default.contentsOfDirectory(
            at: databaseURL.deletingLastPathComponent(),
            includingPropertiesForKeys: nil
        ).filter { $0.lastPathComponent.contains(databaseURL.lastPathComponent) }
        for fileURL in durableFiles {
            let bytes = try Data(contentsOf: fileURL)
            for forbiddenValue in forbiddenValues {
                XCTAssertNil(bytes.range(of: Data(forbiddenValue.utf8)), "Found \(forbiddenValue)")
            }
        }
    }

    func testReopenPreservesRecordAndAppendOnlyEvents() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        let operationID = operationID(2)
        let digest = requestBindingDigest("b")
        let created = try store.createRequest(
            operationID: operationID,
            requestBindingDigest: digest,
            provider: .ollama,
            requestedAt: date(100.1239),
            expiresAt: date(400)
        )
        XCTAssertEqual(created.requestedAt, date(100.123))
        _ = try store.reserveDispatch(
            operationID: operationID,
            requestBindingDigest: digest,
            at: date(200)
        )

        let reopened = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        let terminal = try reopened.recordTerminal(
            operationID: operationID,
            event: .failure,
            at: date(300)
        )
        XCTAssertEqual(try reopened.record(operationID: operationID), terminal)
        XCTAssertEqual(
            try reopened.recentEvents(limit: 10).map(\.event),
            [.failure, .dispatchReserved, .requested]
        )
    }

    func testConcurrentReservationAcrossTwoInstancesSucceedsExactlyOnce() throws {
        let databaseURL = temporaryDatabaseURL()
        let first = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        let second = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        let operationID = operationID(3)
        let digest = requestBindingDigest("c")
        _ = try first.createRequest(
            operationID: operationID,
            requestBindingDigest: digest,
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(500)
        )

        let results = ConcurrentReservationResults()
        let group = DispatchGroup()
        for store in [first, second] {
            group.enter()
            DispatchQueue.global().async {
                defer { group.leave() }
                do {
                    _ = try store.reserveDispatch(
                        operationID: operationID,
                        requestBindingDigest: digest,
                        at: self.date(200)
                    )
                    results.append(nil)
                } catch {
                    results.append(error as? RuntimeModelPullApprovalStoreError)
                }
            }
        }
        group.wait()

        XCTAssertEqual(results.values.filter { $0 == nil }.count, 1)
        XCTAssertEqual(results.values.compactMap { $0 }, [.illegalTransition])
        XCTAssertEqual(try first.recentEvents(limit: 10).map(\.event), [.dispatchReserved, .requested])
    }

    func testExpiryFailsClosedBeforeDispatchAndAfterReservation() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        let pendingID = operationID(4)
        let pendingDigest = requestBindingDigest("d")
        _ = try store.createRequest(
            operationID: pendingID,
            requestBindingDigest: pendingDigest,
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(200)
        )
        XCTAssertThrowsError(try store.reserveDispatch(
            operationID: pendingID,
            requestBindingDigest: pendingDigest,
            at: date(200)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .expiredReservation)
        }
        XCTAssertEqual(try store.record(operationID: pendingID)?.currentEvent, .expiry)

        let reservedID = operationID(5)
        let reservedDigest = requestBindingDigest("e")
        _ = try store.createRequest(
            operationID: reservedID,
            requestBindingDigest: reservedDigest,
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(300)
        )
        _ = try store.reserveDispatch(
            operationID: reservedID,
            requestBindingDigest: reservedDigest,
            at: date(200)
        )
        XCTAssertThrowsError(try store.recordTerminal(
            operationID: reservedID,
            event: .success,
            at: date(300)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .expiredReservation)
        }
        XCTAssertEqual(try store.record(operationID: reservedID)?.currentEvent, .resultSuppressed)
    }

    func testRejectsIllegalTransitionsDuplicateBindingAndBindingMismatch() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        let operationID = operationID(6)
        let digest = requestBindingDigest("f")
        _ = try store.createRequest(
            operationID: operationID,
            requestBindingDigest: digest,
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(500)
        )
        XCTAssertThrowsError(try store.recordTerminal(
            operationID: operationID,
            event: .success,
            at: date(200)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .illegalTransition)
        }
        XCTAssertThrowsError(try store.reserveDispatch(
            operationID: operationID,
            requestBindingDigest: requestBindingDigest("0"),
            at: date(200)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .requestBindingMismatch)
        }
        XCTAssertThrowsError(try store.createRequest(
            operationID: self.operationID(7),
            requestBindingDigest: digest,
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(500)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .duplicateRequestBinding)
        }
        _ = try store.reserveDispatch(
            operationID: operationID,
            requestBindingDigest: digest,
            at: date(200)
        )
        XCTAssertThrowsError(try store.reserveDispatch(
            operationID: operationID,
            requestBindingDigest: digest,
            at: date(201)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .illegalTransition)
        }
        XCTAssertThrowsError(try store.recordTerminal(
            operationID: operationID,
            event: .dismissal,
            at: date(250)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .illegalTransition)
        }
    }

    func testRejectsMalformedInputsAndPersistedEventCorruption() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        XCTAssertThrowsError(try store.createRequest(
            operationID: "not-a-canonical-uuid",
            requestBindingDigest: requestBindingDigest("a"),
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(200)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .invalidOperationID)
        }
        XCTAssertThrowsError(try store.createRequest(
            operationID: operationID(8),
            requestBindingDigest: "a" + String(repeating: "0", count: 64),
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(200)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .invalidRequestBindingDigest)
        }
        XCTAssertThrowsError(try store.createRequest(
            operationID: operationID(8),
            requestBindingDigest: requestBindingDigest("8"),
            providerCode: "lmstudio",
            requestedAt: date(100),
            expiresAt: date(200)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .invalidProvider)
        }
        XCTAssertThrowsError(try store.recordTerminal(
            operationID: operationID(8),
            eventCode: "provider_error_text",
            at: date(200)
        )) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .invalidEvent)
        }
        XCTAssertThrowsError(try store.recentEvents(limit: 0)) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .invalidLimit)
        }

        let operationID = operationID(9)
        _ = try store.createRequest(
            operationID: operationID,
            requestBindingDigest: requestBindingDigest("9"),
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(300)
        )
        try executeRaw(
            databaseURL,
            "UPDATE runtime_model_pull_approval_events SET event_code = 'dispatch_reserved' " +
                "WHERE operation_id = '\(operationID)'"
        )
        XCTAssertThrowsError(try store.record(operationID: operationID)) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .corruptPersistence)
        }
        XCTAssertThrowsError(try store.recentEvents(limit: 10)) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .corruptPersistence)
        }
    }

    func testRecoveryTerminalizesWithoutReturningRetryableWork() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        let pendingID = operationID(10)
        let reservedID = operationID(11)
        let completedID = operationID(12)
        for (identifier, marker) in [(pendingID, "a"), (reservedID, "b"), (completedID, "c")] {
            _ = try store.createRequest(
                operationID: identifier,
                requestBindingDigest: requestBindingDigest(marker),
                provider: .ollama,
                requestedAt: date(100),
                expiresAt: date(500)
            )
        }
        _ = try store.reserveDispatch(
            operationID: reservedID,
            requestBindingDigest: requestBindingDigest("b"),
            at: date(150)
        )
        _ = try store.recordTerminal(operationID: completedID, event: .dismissal, at: date(150))

        let reopened = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try reopened.recoverUnfinished(at: date(200)),
            RuntimeModelPullApprovalRecoveryResult(pendingTerminalized: 1, reservedTerminalized: 1)
        )
        XCTAssertEqual(try reopened.record(operationID: pendingID)?.currentEvent, .hostRestarted)
        XCTAssertEqual(try reopened.record(operationID: reservedID)?.currentEvent, .resultSuppressed)
        XCTAssertEqual(try reopened.record(operationID: completedID)?.currentEvent, .dismissal)
        XCTAssertEqual(
            try reopened.recoverUnfinished(at: date(300)),
            RuntimeModelPullApprovalRecoveryResult(pendingTerminalized: 0, reservedTerminalized: 0)
        )
    }

    func testDatabaseAndDirectoryUseOwnerOnlyPermissions() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        _ = try store.createRequest(
            operationID: operationID(13),
            requestBindingDigest: requestBindingDigest("d"),
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(200)
        )
        let fileAttributes = try FileManager.default.attributesOfItem(atPath: databaseURL.path)
        let directoryAttributes = try FileManager.default.attributesOfItem(
            atPath: databaseURL.deletingLastPathComponent().path
        )
        XCTAssertEqual((fileAttributes[.posixPermissions] as? NSNumber)?.intValue, 0o600)
        XCTAssertEqual((directoryAttributes[.posixPermissions] as? NSNumber)?.intValue, 0o700)
    }

    func testSchemaV1MigrationPinsPolicyAndNeverRestoresPendingExecution() throws {
        let databaseURL = temporaryDatabaseURL()
        try FileManager.default.createDirectory(
            at: databaseURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let pendingOperationID = operationID(14)
        let digest = requestBindingDigest("e")
        let reservedOperationID = operationID(15)
        let reservedDigest = requestBindingDigest("f")
        try executeRaw(
            databaseURL,
            """
            PRAGMA application_id = 1095585857;
            PRAGMA user_version = 1;
            CREATE TABLE runtime_model_pull_approval_operations(
                operation_id TEXT PRIMARY KEY NOT NULL,
                request_binding_digest TEXT UNIQUE NOT NULL,
                provider_code TEXT NOT NULL,
                current_event_code TEXT NOT NULL,
                outcome_code TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL
            );
            CREATE TABLE runtime_model_pull_approval_events(
                operation_id TEXT NOT NULL,
                event_order INTEGER NOT NULL,
                event_code TEXT NOT NULL,
                outcome_code TEXT NOT NULL,
                occurred_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL,
                PRIMARY KEY(operation_id, event_order)
            );
            CREATE TABLE runtime_model_pull_approval_metadata(
                singleton INTEGER PRIMARY KEY NOT NULL,
                schema_version INTEGER NOT NULL
            );
            INSERT INTO runtime_model_pull_approval_metadata VALUES(1, 1);
            INSERT INTO runtime_model_pull_approval_operations VALUES(
                '\(pendingOperationID)', '\(digest)', 'ollama', 'requested', 'none',
                100000, 100000, 300000, 1
            );
            INSERT INTO runtime_model_pull_approval_events VALUES(
                '\(pendingOperationID)', 0, 'requested', 'none', 100000, 1
            );
            INSERT INTO runtime_model_pull_approval_operations VALUES(
                '\(reservedOperationID)', '\(reservedDigest)', 'ollama',
                'dispatch_reserved', 'none', 100000, 150000, 300000, 1
            );
            INSERT INTO runtime_model_pull_approval_events VALUES(
                '\(reservedOperationID)', 0, 'requested', 'none', 100000, 1
            );
            INSERT INTO runtime_model_pull_approval_events VALUES(
                '\(reservedOperationID)', 1, 'dispatch_reserved', 'none', 150000, 1
            );
            """
        )

        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try store.recoverUnfinished(at: date(200)),
            RuntimeModelPullApprovalRecoveryResult(
                pendingTerminalized: 1,
                reservedTerminalized: 1
            )
        )
        let migrated = try XCTUnwrap(store.record(operationID: pendingOperationID))
        XCTAssertEqual(migrated.schemaVersion, 2)
        XCTAssertEqual(migrated.actionID, RuntimePermissionPolicyRegistry.modelPullActionID)
        XCTAssertEqual(
            migrated.policyRevision,
            RuntimePermissionPolicyRegistry.modelPullRevision
        )
        XCTAssertEqual(migrated.currentEvent, .hostRestarted)
        let migratedReserved = try XCTUnwrap(store.record(operationID: reservedOperationID))
        XCTAssertEqual(migratedReserved.schemaVersion, 2)
        XCTAssertEqual(migratedReserved.actionID, RuntimePermissionPolicyRegistry.modelPullActionID)
        XCTAssertEqual(
            migratedReserved.policyRevision,
            RuntimePermissionPolicyRegistry.modelPullRevision
        )
        XCTAssertEqual(migratedReserved.currentEvent, .resultSuppressed)
        XCTAssertEqual(
            try store.recentEvents(limit: 10).filter {
                $0.operationID == pendingOperationID
            }.map(\.event),
            [.hostRestarted, .requested]
        )
        XCTAssertEqual(
            try store.recentEvents(limit: 10).filter {
                $0.operationID == reservedOperationID
            }.map(\.event),
            [.resultSuppressed, .dispatchReserved, .requested]
        )
        XCTAssertEqual(
            try tableColumns(
                databaseURL,
                table: "runtime_model_pull_approval_operations"
            ),
            [
                "operation_id", "request_binding_digest", "provider_code",
                "action_id", "policy_revision", "current_event_code", "outcome_code",
                "created_at_ms", "updated_at_ms", "expires_at_ms", "schema_version",
            ]
        )
    }

    func testSchemaV1MigrationRejectsMalformedHistoryAndRollsBackPolicyStamping() throws {
        let databaseURL = temporaryDatabaseURL()
        try FileManager.default.createDirectory(
            at: databaseURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let operationID = operationID(16)
        let digest = requestBindingDigest("a")
        try executeRaw(
            databaseURL,
            """
            PRAGMA application_id = 1095585857;
            PRAGMA user_version = 1;
            CREATE TABLE runtime_model_pull_approval_operations(
                operation_id TEXT PRIMARY KEY NOT NULL,
                request_binding_digest TEXT UNIQUE NOT NULL,
                provider_code TEXT NOT NULL,
                current_event_code TEXT NOT NULL,
                outcome_code TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL
            );
            CREATE TABLE runtime_model_pull_approval_events(
                operation_id TEXT NOT NULL,
                event_order INTEGER NOT NULL,
                event_code TEXT NOT NULL,
                outcome_code TEXT NOT NULL,
                occurred_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL,
                PRIMARY KEY(operation_id, event_order)
            );
            CREATE TABLE runtime_model_pull_approval_metadata(
                singleton INTEGER PRIMARY KEY NOT NULL,
                schema_version INTEGER NOT NULL
            );
            INSERT INTO runtime_model_pull_approval_metadata VALUES(1, 1);
            INSERT INTO runtime_model_pull_approval_operations VALUES(
                '\(operationID)', '\(digest)', 'ollama', 'requested', 'none',
                100000, 100000, 300000, 1
            );
            INSERT INTO runtime_model_pull_approval_events VALUES(
                '\(operationID)', 0, 'requested', 'none', 100000, 1
            );
            INSERT INTO runtime_model_pull_approval_events VALUES(
                '\(operationID)', 1, 'dispatch_reserved', 'none', 150000, 1
            );
            """
        )

        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        XCTAssertThrowsError(try store.record(operationID: operationID)) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .corruptPersistence)
        }
        XCTAssertEqual(try userVersion(databaseURL), 1)
        XCTAssertEqual(
            try tableColumns(
                databaseURL,
                table: "runtime_model_pull_approval_operations"
            ),
            [
                "operation_id", "request_binding_digest", "provider_code",
                "current_event_code", "outcome_code", "created_at_ms",
                "updated_at_ms", "expires_at_ms", "schema_version",
            ]
        )
    }

    func testSchemaV1MigrationRejectsExpiredReservationAndRollsBackPolicyStamping() throws {
        let databaseURL = temporaryDatabaseURL()
        try FileManager.default.createDirectory(
            at: databaseURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let operationID = operationID(18)
        let digest = requestBindingDigest("c")
        try executeRaw(
            databaseURL,
            """
            PRAGMA application_id = 1095585857;
            PRAGMA user_version = 1;
            CREATE TABLE runtime_model_pull_approval_operations(
                operation_id TEXT PRIMARY KEY NOT NULL,
                request_binding_digest TEXT UNIQUE NOT NULL,
                provider_code TEXT NOT NULL,
                current_event_code TEXT NOT NULL,
                outcome_code TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL
            );
            CREATE TABLE runtime_model_pull_approval_events(
                operation_id TEXT NOT NULL,
                event_order INTEGER NOT NULL,
                event_code TEXT NOT NULL,
                outcome_code TEXT NOT NULL,
                occurred_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL,
                PRIMARY KEY(operation_id, event_order)
            );
            CREATE TABLE runtime_model_pull_approval_metadata(
                singleton INTEGER PRIMARY KEY NOT NULL,
                schema_version INTEGER NOT NULL
            );
            INSERT INTO runtime_model_pull_approval_metadata VALUES(1, 1);
            INSERT INTO runtime_model_pull_approval_operations VALUES(
                '\(operationID)', '\(digest)', 'ollama', 'dispatch_reserved', 'none',
                100000, 300000, 300000, 1
            );
            INSERT INTO runtime_model_pull_approval_events VALUES(
                '\(operationID)', 0, 'requested', 'none', 100000, 1
            );
            INSERT INTO runtime_model_pull_approval_events VALUES(
                '\(operationID)', 1, 'dispatch_reserved', 'none', 300000, 1
            );
            """
        )

        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        XCTAssertThrowsError(try store.record(operationID: operationID)) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .corruptPersistence)
        }
        XCTAssertEqual(try userVersion(databaseURL), 1)
        XCTAssertFalse(
            try tableColumns(
                databaseURL,
                table: "runtime_model_pull_approval_operations"
            ).contains("policy_revision")
        )
    }

    func testSchemaV1MigrationRejectsInvalidRowVersionsAndRollsBackPolicyStamping() throws {
        let databaseURL = temporaryDatabaseURL()
        try FileManager.default.createDirectory(
            at: databaseURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let operationID = operationID(17)
        let digest = requestBindingDigest("b")
        try executeRaw(
            databaseURL,
            """
            PRAGMA application_id = 1095585857;
            PRAGMA user_version = 1;
            CREATE TABLE runtime_model_pull_approval_operations(
                operation_id TEXT PRIMARY KEY NOT NULL,
                request_binding_digest TEXT UNIQUE NOT NULL,
                provider_code TEXT NOT NULL,
                current_event_code TEXT NOT NULL,
                outcome_code TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL
            );
            CREATE TABLE runtime_model_pull_approval_events(
                operation_id TEXT NOT NULL,
                event_order INTEGER NOT NULL,
                event_code TEXT NOT NULL,
                outcome_code TEXT NOT NULL,
                occurred_at_ms INTEGER NOT NULL,
                schema_version INTEGER NOT NULL,
                PRIMARY KEY(operation_id, event_order)
            );
            CREATE TABLE runtime_model_pull_approval_metadata(
                singleton INTEGER PRIMARY KEY NOT NULL,
                schema_version INTEGER NOT NULL
            );
            INSERT INTO runtime_model_pull_approval_metadata VALUES(1, 1);
            INSERT INTO runtime_model_pull_approval_operations VALUES(
                '\(operationID)', '\(digest)', 'ollama', 'requested', 'none',
                100000, 100000, 300000, 2
            );
            INSERT INTO runtime_model_pull_approval_events VALUES(
                '\(operationID)', 0, 'requested', 'none', 100000, 1
            );
            """
        )

        let store = SQLiteRuntimeModelPullApprovalStore(databaseURL: databaseURL)
        XCTAssertThrowsError(try store.record(operationID: operationID)) {
            XCTAssertEqual($0 as? RuntimeModelPullApprovalStoreError, .corruptPersistence)
        }
        XCTAssertEqual(try userVersion(databaseURL), 1)
        XCTAssertFalse(
            try tableColumns(
                databaseURL,
                table: "runtime_model_pull_approval_operations"
            ).contains("policy_revision")
        )
    }

    private func temporaryDatabaseURL() -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        return directory.appendingPathComponent("approvals.sqlite", isDirectory: false)
    }

    private func operationID(_ value: Int) -> String {
        String(format: "00000000-0000-4000-8000-%012d", value)
    }

    private func requestBindingDigest(_ marker: String) -> String {
        SQLiteRuntimeModelPullApprovalStore.requestBindingDigestPrefix
            + String(repeating: marker, count: 64)
    }

    private func date(_ seconds: TimeInterval) -> Date {
        Date(timeIntervalSince1970: seconds)
    }

    private func tableColumns(_ databaseURL: URL, table: String) throws -> Set<String> {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "RuntimeModelPullApprovalStoreTests", code: 1)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, "PRAGMA table_info(\(table))", -1, &statement, nil)
                == SQLITE_OK,
              let statement else {
            throw NSError(domain: "RuntimeModelPullApprovalStoreTests", code: 2)
        }
        defer { sqlite3_finalize(statement) }
        var columns = Set<String>()
        while sqlite3_step(statement) == SQLITE_ROW {
            guard let bytes = sqlite3_column_text(statement, 1) else { continue }
            columns.insert(String(cString: bytes))
        }
        return columns
    }

    private func userVersion(_ databaseURL: URL) throws -> Int {
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY, nil) == SQLITE_OK,
              let database else {
            throw NSError(domain: "RuntimeModelPullApprovalStoreTests", code: 5)
        }
        defer { sqlite3_close(database) }
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, "PRAGMA user_version", -1, &statement, nil)
                == SQLITE_OK,
              let statement else {
            throw NSError(domain: "RuntimeModelPullApprovalStoreTests", code: 6)
        }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_step(statement) == SQLITE_ROW else {
            throw NSError(domain: "RuntimeModelPullApprovalStoreTests", code: 7)
        }
        return Int(sqlite3_column_int(statement, 0))
    }

    private func executeRaw(_ databaseURL: URL, _ sql: String) throws {
        var database: OpaquePointer?
        guard sqlite3_open_v2(
            databaseURL.path,
            &database,
            SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE,
            nil
        ) == SQLITE_OK,
              let database else {
            throw NSError(domain: "RuntimeModelPullApprovalStoreTests", code: 3)
        }
        defer { sqlite3_close(database) }
        guard sqlite3_exec(database, sql, nil, nil, nil) == SQLITE_OK else {
            throw NSError(domain: "RuntimeModelPullApprovalStoreTests", code: 4)
        }
    }
}

private final class ConcurrentReservationResults: @unchecked Sendable {
    private let lock = NSLock()
    private var storage: [RuntimeModelPullApprovalStoreError?] = []

    var values: [RuntimeModelPullApprovalStoreError?] {
        lock.withLock { storage }
    }

    func append(_ value: RuntimeModelPullApprovalStoreError?) {
        lock.withLock { storage.append(value) }
    }
}
