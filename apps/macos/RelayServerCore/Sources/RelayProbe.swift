import Foundation

public struct RelayProbeRequest: Equatable, Sendable {
    public static let action = "probe"

    public let relayID: String

    public init(relayID: String) throws {
        guard isCanonicalRelayControlLineID(relayID) else {
            throw RelayProbeError.invalidRelayID
        }
        self.relayID = relayID
    }

    public static func parse(_ line: String) throws -> RelayProbeRequest {
        let parts = line.trimmingCharacters(in: .whitespacesAndNewlines).split(
            whereSeparator: { $0.isWhitespace }
        )
        guard parts.count == 3,
              parts[0] == Substring(RelayHandshake.prefix),
              parts[1] == Substring(action)
        else {
            throw RelayProbeError.invalidFormat
        }
        return try RelayProbeRequest(relayID: String(parts[2]))
    }

    public static func isProbeLine(_ line: String) -> Bool {
        let parts = line.trimmingCharacters(in: .whitespacesAndNewlines).split(
            whereSeparator: { $0.isWhitespace }
        )
        return parts.count >= 2 &&
            parts[0] == Substring(RelayHandshake.prefix) &&
            parts[1] == Substring(action)
    }
}

public struct RelayProbeResponse: Equatable, Sendable {
    public let known: Bool
    public let runtimeWaiting: Bool

    public init(known: Bool, runtimeWaiting: Bool) {
        self.known = known
        self.runtimeWaiting = runtimeWaiting
    }

    public func responseLine() -> Data {
        Data(
            "\(RelayHandshake.prefix) probe known=\(known.flagValue) runtime_waiting=\(runtimeWaiting.flagValue)\n".utf8
        )
    }
}

public enum RelayProbeError: Error, Equatable, Sendable {
    case invalidFormat
    case invalidRelayID
}

private extension Bool {
    var flagValue: String {
        self ? "1" : "0"
    }
}
