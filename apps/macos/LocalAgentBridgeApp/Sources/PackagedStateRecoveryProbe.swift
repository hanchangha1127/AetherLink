import CompanionCore
import Foundation

/// A closed, environment-gated QA observation used only by the packaged-state
/// recovery runner. The canary is supplied outside the app; this helper only
/// records what `CompanionAppModel` projected during normal initialization.
final class PackagedStateRecoveryProbe {
    enum Mode: String {
        case migrationRead = "migration-read-v1"
        case sqliteReadback = "sqlite-readback-v1"
    }

    struct Canary: Codable, Equatable {
        let eventID: String
        let model: String
        let requestID: String
        let sessionID: String
        let timestampEpochMilliseconds: Int
    }

    struct Observation: Codable, Equatable {
        let lastActivityEpochMilliseconds: Int?
        let lastEvent: String?
        let matchingSessionCount: Int
        let messageCount: Int?
        let model: String?
        let status: String?
    }

    struct Marker: Codable, Equatable {
        let canary: Canary
        let failureCode: String?
        let mode: String
        let observation: Observation
        let schemaVersion: Int
        let status: String
    }

    static let environmentKey = "AETHERLINK_QA_PACKAGED_STATE_RECOVERY_MODE"
    static let markerDirectoryName = "qa-packaged-state-recovery-v1"
    static let canary = Canary(
        eventID: "packaged-state-recovery-canary-event-v1",
        model: "qa:packaged-state-recovery-canary-v1",
        requestID: "packaged-state-recovery-canary-request-v1",
        sessionID: "packaged-state-recovery-canary-session-v1",
        timestampEpochMilliseconds: 1_000
    )

    let mode: Mode
    let markerURL: URL

    private let fileManager: FileManager

    private init(
        mode: Mode,
        markerURL: URL,
        fileManager: FileManager
    ) {
        self.mode = mode
        self.markerURL = markerURL
        self.fileManager = fileManager
    }

    static func prepareIfRequested(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        databaseURL: URL = SQLiteRuntimeChatEventStore.defaultDatabaseURL(),
        fileManager: FileManager = .default
    ) -> PackagedStateRecoveryProbe? {
        guard let rawMode = environment[environmentKey],
              let mode = Mode(rawValue: rawMode) else {
            return nil
        }
        let markerURL = databaseURL
            .deletingLastPathComponent()
            .appendingPathComponent(markerDirectoryName, isDirectory: true)
            .appendingPathComponent("\(mode.rawValue).json", isDirectory: false)
        return PackagedStateRecoveryProbe(
            mode: mode,
            markerURL: markerURL,
            fileManager: fileManager
        )
    }

    @discardableResult
    func recordObservation(
        sessions: [RuntimeChatStoredSession],
        storeError: String?
    ) -> Bool {
        let matches = sessions.filter { $0.sessionID == Self.canary.sessionID }
        let observed = matches.count == 1 ? matches[0] : nil
        let observation = Observation(
            lastActivityEpochMilliseconds: observed.map {
                Self.epochMilliseconds($0.lastActivityAt)
            },
            lastEvent: observed?.lastEvent,
            matchingSessionCount: matches.count,
            messageCount: observed?.messageCount,
            model: observed?.model,
            status: observed?.status
        )
        let failureCode = Self.observationFailureCode(
            observation,
            storeError: storeError
        )
        let marker = Marker(
            canary: Self.canary,
            failureCode: failureCode,
            mode: mode.rawValue,
            observation: observation,
            schemaVersion: 1,
            status: failureCode == nil ? "passed" : "failed"
        )

        do {
            try fileManager.createDirectory(
                at: markerURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.sortedKeys]
            var payload = try encoder.encode(marker)
            payload.append(0x0A)
            try payload.write(to: markerURL, options: .atomic)
            return true
        } catch {
            return false
        }
    }

    private static func observationFailureCode(
        _ observation: Observation,
        storeError: String?
    ) -> String? {
        if storeError != nil {
            return "runtime-chat-read-failed"
        }
        guard observation.matchingSessionCount > 0 else {
            return "canary-session-not-recovered"
        }
        guard observation.matchingSessionCount == 1 else {
            return "canary-session-ambiguous"
        }
        guard
            observation.lastActivityEpochMilliseconds
                == canary.timestampEpochMilliseconds,
            observation.lastEvent
                == RuntimeChatStoredEventKind.request.rawValue,
            observation.messageCount == 1,
            observation.model == canary.model,
            observation.status == "active"
        else {
            return "canary-projection-mismatch"
        }
        return nil
    }

    private static func epochMilliseconds(_ date: Date) -> Int {
        Int((date.timeIntervalSince1970 * 1_000).rounded())
    }
}
