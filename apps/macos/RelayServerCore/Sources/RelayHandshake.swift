import BridgeProtocol
import Foundation

let relayControlLineRelayIDMaxCharacters = 512
let relaySessionNonceCharacterCount = 32
let relayEphemeralKeyCharacterCount = 130

private let relayControlLineRelayIDForbiddenCharacters = CharacterSet(charactersIn: "/\\?#@:")

func isCanonicalRelayControlLineID(_ relayID: String) -> Bool {
    !relayID.isEmpty &&
        relayID.count <= relayControlLineRelayIDMaxCharacters &&
        relayID.rangeOfCharacter(from: .whitespacesAndNewlines) == nil &&
        relayID.rangeOfCharacter(from: relayControlLineRelayIDForbiddenCharacters) == nil
}

func isCanonicalRuntimeKeyBoundRelayID(_ relayID: String) -> Bool {
    guard relayID.hasPrefix("rt2-") else { return false }
    return isLowercaseHex(
        String(relayID.dropFirst("rt2-".count)),
        characterCount: 64
    )
}

func isCanonicalRelaySessionNonce(_ nonce: String) -> Bool {
    isLowercaseHex(nonce, characterCount: relaySessionNonceCharacterCount)
}

func isCanonicalRelayEphemeralKey(_ key: String) -> Bool {
    key.hasPrefix("04") && isLowercaseHex(key, characterCount: relayEphemeralKeyCharacterCount)
}

private func isLowercaseHex(_ value: String, characterCount: Int) -> Bool {
    value.utf8.count == characterCount && value.utf8.allSatisfy { byte in
        (UInt8(ascii: "0")...UInt8(ascii: "9")).contains(byte) ||
            (UInt8(ascii: "a")...UInt8(ascii: "f")).contains(byte)
    }
}

public enum RelayRole: String, Sendable {
    case runtime
    case client
}

public struct RelayHandshake: Equatable, Sendable {
    public static let prefix = "AETHERLINK_RELAY"
    public static let registeredLine = Data("AETHERLINK_RELAY registered\n".utf8)
    public static let readyLine = Data("AETHERLINK_RELAY ready\n".utf8)
    public static let cryptoV2RegisteredLine = Data("AETHERLINK_RELAY registered crypto=2\n".utf8)

    public let role: RelayRole
    public let relayID: String
    public let sessionNonce: String?
    public let ephemeralKey: String?
    public let runtimeKeyFingerprint: String?
    public var usesCryptoV2: Bool { sessionNonce != nil && ephemeralKey != nil }

    public init(role: RelayRole, relayID: String) throws {
        guard isCanonicalRelayControlLineID(relayID) else {
            throw RelayHandshakeError.invalidRelayID
        }
        self.role = role
        self.relayID = relayID
        self.sessionNonce = nil
        self.ephemeralKey = nil
        self.runtimeKeyFingerprint = nil
    }

    public init(
        role: RelayRole,
        relayID: String,
        sessionNonce: String,
        ephemeralKey: String,
        runtimeKeyFingerprint: String? = nil
    ) throws {
        guard isCanonicalRelayControlLineID(relayID) else {
            throw RelayHandshakeError.invalidRelayID
        }
        guard isCanonicalRelaySessionNonce(sessionNonce) else {
            throw RelayHandshakeError.invalidSessionNonce
        }
        guard isCanonicalRelayEphemeralKey(ephemeralKey) else {
            throw RelayHandshakeError.invalidEphemeralKey
        }
        if role == .runtime {
            guard let runtimeKeyFingerprint,
                  RelayRuntimeIdentity.isCanonicalFingerprint(runtimeKeyFingerprint)
            else {
                throw RelayHandshakeError.invalidRuntimeKeyFingerprint
            }
        } else if runtimeKeyFingerprint != nil {
            throw RelayHandshakeError.invalidFormat
        }
        self.role = role
        self.relayID = relayID
        self.sessionNonce = sessionNonce
        self.ephemeralKey = ephemeralKey
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
    }

    public static func parse(_ line: String) throws -> RelayHandshake {
        let body = line.hasSuffix("\n") ? line.dropLast() : Substring(line)
        guard !body.contains("\n"), !body.contains("\r") else {
            throw RelayHandshakeError.invalidFormat
        }
        let parts = body.split(separator: " ", omittingEmptySubsequences: false)
        guard (parts.count == 3 || parts.count == 6 || parts.count == 7),
              parts[0] == Substring(prefix)
        else {
            throw RelayHandshakeError.invalidFormat
        }
        guard let role = RelayRole(rawValue: String(parts[1])) else {
            throw RelayHandshakeError.invalidRole
        }
        guard parts.count != 3 else {
            return try RelayHandshake(role: role, relayID: String(parts[2]))
        }

        guard parts[3] == "crypto=2" else {
            throw RelayHandshakeError.invalidCryptoVersion
        }
        let fingerprint: String?
        let sessionNonce: String
        let ephemeralKey: String
        switch role {
        case .runtime:
            guard parts.count == 7,
                  let parsedNonce = fieldValue(parts[4], name: "session_nonce"),
                  let parsedKey = fieldValue(parts[5], name: "ephemeral_key"),
                  let parsedFingerprint = fieldValue(parts[6], name: "runtime_key_fingerprint")
            else {
                throw RelayHandshakeError.invalidFormat
            }
            fingerprint = parsedFingerprint
            sessionNonce = parsedNonce
            ephemeralKey = parsedKey
        case .client:
            guard parts.count == 6,
                  let parsedNonce = fieldValue(parts[4], name: "session_nonce"),
                  let parsedKey = fieldValue(parts[5], name: "ephemeral_key")
            else {
                throw RelayHandshakeError.invalidFormat
            }
            fingerprint = nil
            sessionNonce = parsedNonce
            ephemeralKey = parsedKey
        }
        return try RelayHandshake(
            role: role,
            relayID: String(parts[2]),
            sessionNonce: sessionNonce,
            ephemeralKey: ephemeralKey,
            runtimeKeyFingerprint: fingerprint
        )
    }

    public static func cryptoV2ReadyLine(peerSessionNonce: String, peerEphemeralKey: String) -> Data {
        Data(
            ("AETHERLINK_RELAY ready crypto=2 peer_session_nonce=\(peerSessionNonce) " +
                "peer_ephemeral_key=\(peerEphemeralKey)\n").utf8
        )
    }

    private static func fieldValue(_ field: Substring, name: String) -> String? {
        let prefix = "\(name)="
        guard field.hasPrefix(prefix) else { return nil }
        return String(field.dropFirst(prefix.count))
    }
}

public enum RelayHandshakeError: Error, Equatable, Sendable {
    case invalidFormat
    case invalidRole
    case invalidRelayID
    case invalidCryptoVersion
    case invalidSessionNonce
    case invalidEphemeralKey
    case invalidRuntimeKeyFingerprint
}
