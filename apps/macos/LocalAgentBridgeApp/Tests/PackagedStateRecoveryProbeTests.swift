import CompanionCore
import Foundation
import XCTest
@testable import LocalAgentBridge

final class PackagedStateRecoveryProbeTests: XCTestCase {
    func testMissingOrUnknownModeLeavesProbeDisabled() {
        XCTAssertNil(
            PackagedStateRecoveryProbe.prepareIfRequested(environment: [:])
        )
        XCTAssertNil(
            PackagedStateRecoveryProbe.prepareIfRequested(
                environment: [
                    PackagedStateRecoveryProbe.environmentKey: "unknown"
                ]
            )
        )
    }

    func testMigrationModePublishesExactPassedObservationLine() throws {
        let probe = try XCTUnwrap(
            PackagedStateRecoveryProbe.prepareIfRequested(
                environment: modeEnvironment(.migrationRead)
            )
        )

        XCTAssertEqual(probe.mode, .migrationRead)
        XCTAssertEqual(
            probe.observationResultLine(
                sessions: [matchingSession()],
                storeError: nil
            ),
            Data(
                "AETHERLINK_QA_PACKAGED_STATE_RECOVERY_RESULT=migration-read-v1:passed\n"
                    .utf8
            )
        )
    }

    func testSQLiteReadbackModePublishesExactPassedObservationLine() throws {
        let probe = try XCTUnwrap(
            PackagedStateRecoveryProbe.prepareIfRequested(
                environment: modeEnvironment(.sqliteReadback)
            )
        )

        XCTAssertEqual(
            probe.observationResultLine(
                sessions: [matchingSession()],
                storeError: nil
            ),
            Data(
                "AETHERLINK_QA_PACKAGED_STATE_RECOVERY_RESULT=sqlite-readback-v1:passed\n"
                    .utf8
            )
        )
    }

    func testReadFailureOutputIsContentFreeAndTakesPrecedence() throws {
        let probe = try XCTUnwrap(
            PackagedStateRecoveryProbe.prepareIfRequested(
                environment: modeEnvironment(.sqliteReadback)
            )
        )
        let output = probe.observationResultLine(
            sessions: [matchingSession()],
            storeError: "sensitive fixture detail"
        )

        XCTAssertEqual(
            output,
            Data(
                (
                    "AETHERLINK_QA_PACKAGED_STATE_RECOVERY_RESULT="
                    + "sqlite-readback-v1:failed:"
                    + "runtime-chat-read-failed\n"
                ).utf8
            )
        )
        XCTAssertFalse(
            String(decoding: output, as: UTF8.self)
                .contains("sensitive fixture detail")
        )
    }

    func testProjectionFailuresUseClosedContentFreeCodes() throws {
        let probe = try XCTUnwrap(
            PackagedStateRecoveryProbe.prepareIfRequested(
                environment: modeEnvironment(.sqliteReadback)
            )
        )

        XCTAssertEqual(
            probe.observationResultLine(sessions: [], storeError: nil),
            resultLine("canary-session-not-recovered")
        )
        XCTAssertEqual(
            probe.observationResultLine(
                sessions: [matchingSession(), matchingSession()],
                storeError: nil
            ),
            resultLine("canary-session-ambiguous")
        )
        var mismatch = matchingSession()
        mismatch.messageCount = 0
        XCTAssertEqual(
            probe.observationResultLine(
                sessions: [mismatch],
                storeError: nil
            ),
            resultLine("canary-projection-mismatch")
        )
    }

    func testLegacyFixtureMigratesThenReopensFromSQLiteOnly() throws {
        try withTemporaryRoot { root in
            let databaseURL = databaseURL(under: root)
            let legacyURL = databaseURL
                .deletingLastPathComponent()
                .appendingPathComponent("runtime-chat-events.jsonl")
            try FileManager.default.createDirectory(
                at: legacyURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try Self.legacyFixture.write(to: legacyURL)

            let migrationStore = RuntimeChatEventStoreDefaults.productionStore(
                sqliteDatabaseURL: databaseURL,
                legacyJSONLFileURL: legacyURL
            )
            let migratedSessions = try migrationStore.listAllSessions(
                limit: Int.max,
                includeArchived: true
            )
            XCTAssertEqual(migratedSessions, [matchingSession()])

            try FileManager.default.removeItem(at: legacyURL)
            let sqliteOnlyStore = RuntimeChatEventStoreDefaults.productionStore(
                sqliteDatabaseURL: databaseURL,
                legacyJSONLFileURL: legacyURL
            )
            let reopenedSessions = try sqliteOnlyStore.listAllSessions(
                limit: Int.max,
                includeArchived: true
            )
            XCTAssertEqual(reopenedSessions, migratedSessions)
        }
    }

    func testLegacyFixtureBytesStayExact() {
        XCTAssertEqual(Self.legacyFixture.count, 345)
        XCTAssertEqual(
            Self.legacyFixture,
            Data(
                """
                {"id":"packaged-state-recovery-canary-event-v1","kind":"request","messages":[{"content":"Benign packaged state recovery canary v1.","role":"user"}],"model":"qa:packaged-state-recovery-canary-v1","request_id":"packaged-state-recovery-canary-request-v1","session_id":"packaged-state-recovery-canary-session-v1","timestamp":"1970-01-01T00:00:01Z"}

                """.utf8
            )
        )
    }

    private static let legacyFixture = Data(
        """
        {"id":"packaged-state-recovery-canary-event-v1","kind":"request","messages":[{"content":"Benign packaged state recovery canary v1.","role":"user"}],"model":"qa:packaged-state-recovery-canary-v1","request_id":"packaged-state-recovery-canary-request-v1","session_id":"packaged-state-recovery-canary-session-v1","timestamp":"1970-01-01T00:00:01Z"}

        """.utf8
    )

    private func resultLine(_ failureCode: String) -> Data {
        Data(
            (
                "AETHERLINK_QA_PACKAGED_STATE_RECOVERY_RESULT="
                + "sqlite-readback-v1:failed:"
                + failureCode
                + "\n"
            ).utf8
        )
    }

    private func modeEnvironment(
        _ mode: PackagedStateRecoveryProbe.Mode
    ) -> [String: String] {
        [PackagedStateRecoveryProbe.environmentKey: mode.rawValue]
    }

    private func databaseURL(under root: URL) -> URL {
        root
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-chat-events.sqlite")
    }

    private func matchingSession() -> RuntimeChatStoredSession {
        RuntimeChatStoredSession(
            sessionID: PackagedStateRecoveryProbe.canarySessionID,
            title: "New chat",
            model: PackagedStateRecoveryProbe.canaryModel,
            lastActivityAt: Date(
                timeIntervalSince1970: TimeInterval(
                    PackagedStateRecoveryProbe
                        .canaryTimestampEpochMilliseconds
                ) / 1_000
            ),
            messageCount: 1,
            status: "active",
            lastEvent: RuntimeChatStoredEventKind.request.rawValue
        )
    }

    private func withTemporaryRoot(
        _ body: (URL) throws -> Void
    ) throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(
                "aetherlink-state-recovery-\(UUID().uuidString)",
                isDirectory: true
            )
        try FileManager.default.createDirectory(
            at: root,
            withIntermediateDirectories: false
        )
        defer { try? FileManager.default.removeItem(at: root) }
        try body(root)
    }
}
