import Foundation

public enum RelayRole: String, Sendable {
    case runtime
    case client
}

public struct RelayHandshake: Equatable, Sendable {
    public static let prefix = "AETHERLINK_RELAY"
    public static let registeredLine = Data("AETHERLINK_RELAY registered\n".utf8)
    public static let readyLine = Data("AETHERLINK_RELAY ready\n".utf8)

    public let role: RelayRole
    public let relayID: String

    public init(role: RelayRole, relayID: String) throws {
        guard !relayID.isEmpty, relayID.rangeOfCharacter(from: .whitespacesAndNewlines) == nil else {
            throw RelayHandshakeError.invalidRelayID
        }
        self.role = role
        self.relayID = relayID
    }

    public static func parse(_ line: String) throws -> RelayHandshake {
        let parts = line.trimmingCharacters(in: .whitespacesAndNewlines).split(
            whereSeparator: { $0.isWhitespace }
        )
        guard parts.count == 3, parts[0] == Substring(prefix) else {
            throw RelayHandshakeError.invalidFormat
        }
        guard let role = RelayRole(rawValue: String(parts[1])) else {
            throw RelayHandshakeError.invalidRole
        }
        return try RelayHandshake(role: role, relayID: String(parts[2]))
    }
}

public enum RelayHandshakeError: Error, Equatable, Sendable {
    case invalidFormat
    case invalidRole
    case invalidRelayID
}
