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

    func testMigrationModePublishesExactPassedObservation() throws {
        try withTemporaryRoot { root in
            let databaseURL = databaseURL(under: root)
            let probe = try XCTUnwrap(
                PackagedStateRecoveryProbe.prepareIfRequested(
                    environment: modeEnvironment(.migrationRead),
                    databaseURL: databaseURL
                )
            )

            XCTAssertEqual(probe.mode, .migrationRead)
            XCTAssertEqual(
                probe.markerURL,
                databaseURL
                    .deletingLastPathComponent()
                    .appendingPathComponent(
                        PackagedStateRecoveryProbe.markerDirectoryName,
                        isDirectory: true
                    )
                    .appendingPathComponent("migration-read-v1.json")
            )
            XCTAssertTrue(
                probe.recordObservation(
                    sessions: [matchingSession()],
                    storeError: nil
                )
            )
            XCTAssertEqual(
                try decodedMarker(at: probe.markerURL),
                PackagedStateRecoveryProbe.Marker(
                    canary: PackagedStateRecoveryProbe.canary,
                    failureCode: nil,
                    mode: "migration-read-v1",
                    observation: matchingObservation(),
                    schemaVersion: 1,
                    status: "passed"
                )
            )
            XCTAssertEqual(try probe.markerURL.readBytes().last, 0x0A)
        }
    }

    func testSQLiteReadbackModePublishesExactPassedObservation() throws {
        try withTemporaryRoot { root in
            let probe = try XCTUnwrap(
                PackagedStateRecoveryProbe.prepareIfRequested(
                    environment: modeEnvironment(.sqliteReadback),
                    databaseURL: databaseURL(under: root)
                )
            )

            XCTAssertTrue(
                probe.recordObservation(
                    sessions: [matchingSession()],
                    storeError: nil
                )
            )
            let marker = try decodedMarker(at: probe.markerURL)
            XCTAssertEqual(marker.mode, "sqlite-readback-v1")
            XCTAssertEqual(marker.status, "passed")
            XCTAssertNil(marker.failureCode)
            XCTAssertEqual(marker.observation, matchingObservation())
        }
    }

    func testReadFailureIsContentFreeAndTakesPrecedence() throws {
        try withTemporaryRoot { root in
            let probe = try XCTUnwrap(
                PackagedStateRecoveryProbe.prepareIfRequested(
                    environment: modeEnvironment(.sqliteReadback),
                    databaseURL: databaseURL(under: root)
                )
            )

            XCTAssertTrue(
                probe.recordObservation(
                    sessions: [matchingSession()],
                    storeError: "sensitive fixture detail"
                )
            )
            let markerBytes = try probe.markerURL.readBytes()
            let marker = try decodedMarker(at: probe.markerURL)
            XCTAssertEqual(marker.status, "failed")
            XCTAssertEqual(marker.failureCode, "runtime-chat-read-failed")
            XCTAssertFalse(
                String(decoding: markerBytes, as: UTF8.self)
                    .contains("sensitive fixture detail")
            )
        }
    }

    func testProjectionFailuresUseClosedCodes() throws {
        try withTemporaryRoot { root in
            let databaseURL = databaseURL(under: root)
            let missingProbe = try XCTUnwrap(
                PackagedStateRecoveryProbe.prepareIfRequested(
                    environment: modeEnvironment(.sqliteReadback),
                    databaseURL: databaseURL
                )
            )
            XCTAssertTrue(
                missingProbe.recordObservation(sessions: [], storeError: nil)
            )
            XCTAssertEqual(
                try decodedMarker(at: missingProbe.markerURL).failureCode,
                "canary-session-not-recovered"
            )

            let ambiguousProbe = try XCTUnwrap(
                PackagedStateRecoveryProbe.prepareIfRequested(
                    environment: modeEnvironment(.sqliteReadback),
                    databaseURL: databaseURL
                )
            )
            XCTAssertTrue(
                ambiguousProbe.recordObservation(
                    sessions: [matchingSession(), matchingSession()],
                    storeError: nil
                )
            )
            XCTAssertEqual(
                try decodedMarker(at: ambiguousProbe.markerURL).failureCode,
                "canary-session-ambiguous"
            )

            let mismatchedProbe = try XCTUnwrap(
                PackagedStateRecoveryProbe.prepareIfRequested(
                    environment: modeEnvironment(.sqliteReadback),
                    databaseURL: databaseURL
                )
            )
            var mismatch = matchingSession()
            mismatch.messageCount = 0
            XCTAssertTrue(
                mismatchedProbe.recordObservation(
                    sessions: [mismatch],
                    storeError: nil
                )
            )
            XCTAssertEqual(
                try decodedMarker(at: mismatchedProbe.markerURL).failureCode,
                "canary-projection-mismatch"
            )
        }
    }

    func testMarkerWriteFailureReturnsFalse() throws {
        try withTemporaryRoot { root in
            let applicationSupport = root / "AetherLink"
            try Data("not-a-directory".utf8).write(to: applicationSupport)
            let probe = try XCTUnwrap(
                PackagedStateRecoveryProbe.prepareIfRequested(
                    environment: modeEnvironment(.sqliteReadback),
                    databaseURL: applicationSupport
                        .appendingPathComponent("runtime-chat-events.sqlite")
                )
            )

            XCTAssertFalse(
                probe.recordObservation(
                    sessions: [matchingSession()],
                    storeError: nil
                )
            )
        }
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

    func testLegacyFixtureBytesAndIdentityStayExact() {
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
        let canary = PackagedStateRecoveryProbe.canary
        return RuntimeChatStoredSession(
            sessionID: canary.sessionID,
            title: "New chat",
            model: canary.model,
            lastActivityAt: Date(
                timeIntervalSince1970: TimeInterval(
                    canary.timestampEpochMilliseconds
                ) / 1_000
            ),
            messageCount: 1,
            status: "active",
            lastEvent: RuntimeChatStoredEventKind.request.rawValue
        )
    }

    private func matchingObservation() -> PackagedStateRecoveryProbe.Observation {
        let canary = PackagedStateRecoveryProbe.canary
        return PackagedStateRecoveryProbe.Observation(
            lastActivityEpochMilliseconds: canary.timestampEpochMilliseconds,
            lastEvent: RuntimeChatStoredEventKind.request.rawValue,
            matchingSessionCount: 1,
            messageCount: 1,
            model: canary.model,
            status: "active"
        )
    }

    private func decodedMarker(
        at path: URL
    ) throws -> PackagedStateRecoveryProbe.Marker {
        try JSONDecoder().decode(
            PackagedStateRecoveryProbe.Marker.self,
            from: path.readBytes()
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

private extension URL {
    static func / (lhs: URL, rhs: String) -> URL {
        lhs.appendingPathComponent(rhs)
    }

    func readBytes() throws -> Data {
        try Data(contentsOf: self)
    }
}
