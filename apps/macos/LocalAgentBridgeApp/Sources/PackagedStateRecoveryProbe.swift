import CompanionCore
import Darwin
import Foundation

/// A closed, environment-gated QA observation used only by the packaged-state
/// recovery runner. The canary is supplied outside the app; this helper only
/// reports whether `CompanionAppModel` projected it during normal startup.
final class PackagedStateRecoveryProbe {
    enum Mode: String {
        case migrationRead = "migration-read-v1"
        case sqliteReadback = "sqlite-readback-v1"
    }

    static let environmentKey = "AETHERLINK_QA_PACKAGED_STATE_RECOVERY_MODE"
    static let resultLinePrefix =
        "AETHERLINK_QA_PACKAGED_STATE_RECOVERY_RESULT="
    static let canaryModel = "qa:packaged-state-recovery-canary-v1"
    static let canarySessionID =
        "packaged-state-recovery-canary-session-v1"
    static let canaryTimestampEpochMilliseconds = 1_000

    let mode: Mode

    private init(mode: Mode) {
        self.mode = mode
    }

    static func prepareIfRequested(
        environment: [String: String]? = nil
    ) -> PackagedStateRecoveryProbe? {
        let rawMode: String?
        if let environment {
            rawMode = environment[environmentKey]
        } else {
            rawMode = environmentKey.withCString { pointer in
                getenv(pointer).flatMap { String(validatingUTF8: $0) }
            }
        }
        guard let rawMode,
              let mode = Mode(rawValue: rawMode) else {
            return nil
        }
        return PackagedStateRecoveryProbe(mode: mode)
    }

    func observationResultLine(
        sessions: [RuntimeChatStoredSession],
        storeError: String?
    ) -> Data {
        let matches = sessions.filter {
            $0.sessionID == Self.canarySessionID
        }
        let observed = matches.count == 1 ? matches[0] : nil
        let failureCode = Self.observationFailureCode(
            matchingSessionCount: matches.count,
            observed: observed,
            storeError: storeError
        )
        let result = failureCode.map { "failed:\($0)" } ?? "passed"
        return Data(
            (
                Self.resultLinePrefix
                + mode.rawValue
                + ":"
                + result
                + "\n"
            ).utf8
        )
    }

    private static func observationFailureCode(
        matchingSessionCount: Int,
        observed: RuntimeChatStoredSession?,
        storeError: String?
    ) -> String? {
        if storeError != nil {
            return "runtime-chat-read-failed"
        }
        guard matchingSessionCount > 0 else {
            return "canary-session-not-recovered"
        }
        guard matchingSessionCount == 1 else {
            return "canary-session-ambiguous"
        }
        guard let observed,
              epochMilliseconds(observed.lastActivityAt)
                == canaryTimestampEpochMilliseconds,
              observed.lastEvent
                == RuntimeChatStoredEventKind.request.rawValue,
              observed.messageCount == 1,
              observed.model == canaryModel,
              observed.status == "active"
        else {
            return "canary-projection-mismatch"
        }
        return nil
    }

    private static func epochMilliseconds(_ date: Date) -> Int {
        Int((date.timeIntervalSince1970 * 1_000).rounded())
    }
}
