import CryptoKit
import Foundation

public enum RelaySessionCryptoError: Error, Equatable {
    case invalidSessionNonce
    case invalidEphemeralKey
    case invalidPrivateKey
    case localEphemeralKeyMismatch
    case emptyRelaySecret
}

public enum RelaySessionNonce {
    public static let characterCount = 32

    public static func generate() -> String {
        var generator = SystemRandomNumberGenerator()
        return (0..<16).map { _ in
            String(format: "%02x", UInt8.random(in: .min ... .max, using: &generator))
        }.joined()
    }

    public static func isCanonical(_ value: String) -> Bool {
        RelayCryptoHex.decodeCanonical(value, byteCount: 16) != nil
    }
}

public struct TransportSecurityContext: Equatable, Hashable, Sendable {
    public let bindingID: String

    public init(bindingID: String) {
        precondition(
            RelayKeyConfirmation.isCanonicalDigest(bindingID),
            "Transport binding id must be 64 lowercase hex characters"
        )
        self.bindingID = bindingID
    }
}

public enum RelayKeyConfirmationRole: String, Sendable {
    case client
    case runtime
}

public struct RelaySessionEphemeralKey: @unchecked Sendable {
    private let privateKey: P256.KeyAgreement.PrivateKey

    public var publicKeyHex: String {
        RelayCryptoHex.lowercase(privateKey.publicKey.x963Representation)
    }

    public init() {
        privateKey = P256.KeyAgreement.PrivateKey()
    }

    public init(privateKeyRawRepresentation: Data) throws {
        guard privateKeyRawRepresentation.count == 32 else {
            throw RelaySessionCryptoError.invalidPrivateKey
        }
        do {
            privateKey = try P256.KeyAgreement.PrivateKey(rawRepresentation: privateKeyRawRepresentation)
        } catch {
            throw RelaySessionCryptoError.invalidPrivateKey
        }
    }

    fileprivate func sharedSecret(peerPublicKeyHex: String) throws -> Data {
        let peerPublicKey = try RelaySessionCrypto.publicKey(from: peerPublicKeyHex)
        do {
            let secret = try privateKey.sharedSecretFromKeyAgreement(with: peerPublicKey)
            return secret.withUnsafeBytes { Data($0) }
        } catch {
            throw RelaySessionCryptoError.invalidEphemeralKey
        }
    }
}

public struct RelaySessionKeys: Sendable {
    public let bindingID: String
    let bindingDigest: Data
    let confirmationKey: Data
    let clientTrafficSecret: Data
    let runtimeTrafficSecret: Data
}

public enum RelaySessionCrypto {
    private static let bindingPrefix = "AetherLink relay session binding v2\n" +
        "crypto_version\n2\nrelay_id\n"
    private static let confirmationLabel = Data("AetherLink relay confirmation v2".utf8)
    private static let clientTrafficLabel = Data("AetherLink relay client traffic v2".utf8)
    private static let runtimeTrafficLabel = Data("AetherLink relay runtime traffic v2".utf8)

    public static func isCanonicalEphemeralKey(_ value: String) -> Bool {
        (try? publicKey(from: value)) != nil
    }

    public static func bindingID(
        relayID: String,
        routeNonce: String?,
        clientSessionNonce: String,
        runtimeSessionNonce: String,
        clientEphemeralKey: String,
        runtimeEphemeralKey: String
    ) throws -> String {
        try validateSessionInputs(
            clientSessionNonce: clientSessionNonce,
            runtimeSessionNonce: runtimeSessionNonce,
            clientEphemeralKey: clientEphemeralKey,
            runtimeEphemeralKey: runtimeEphemeralKey
        )
        let transcript = bindingPrefix + relayID +
            "\nroute_nonce\n" + (routeNonce ?? "") +
            "\nclient_session_nonce\n" + clientSessionNonce +
            "\nruntime_session_nonce\n" + runtimeSessionNonce +
            "\nclient_ephemeral_key\n" + clientEphemeralKey +
            "\nruntime_ephemeral_key\n" + runtimeEphemeralKey
        return RelayCryptoHex.lowercase(Data(SHA256.hash(data: Data(transcript.utf8))))
    }

    public static func deriveKeys(
        localRole: RelayKeyConfirmationRole,
        localEphemeralKey: RelaySessionEphemeralKey,
        relayID: String,
        routeNonce: String?,
        relaySecret: String,
        clientSessionNonce: String,
        runtimeSessionNonce: String,
        clientEphemeralKey: String,
        runtimeEphemeralKey: String
    ) throws -> RelaySessionKeys {
        guard !relaySecret.isEmpty else { throw RelaySessionCryptoError.emptyRelaySecret }
        let bindingID = try bindingID(
            relayID: relayID,
            routeNonce: routeNonce,
            clientSessionNonce: clientSessionNonce,
            runtimeSessionNonce: runtimeSessionNonce,
            clientEphemeralKey: clientEphemeralKey,
            runtimeEphemeralKey: runtimeEphemeralKey
        )
        let expectedLocalKey = localRole == .client ? clientEphemeralKey : runtimeEphemeralKey
        guard localEphemeralKey.publicKeyHex == expectedLocalKey else {
            throw RelaySessionCryptoError.localEphemeralKeyMismatch
        }
        let peerKey = localRole == .client ? runtimeEphemeralKey : clientEphemeralKey
        let sharedSecret = try localEphemeralKey.sharedSecret(peerPublicKeyHex: peerKey)
        guard sharedSecret.count == 32,
              let bindingDigest = RelayCryptoHex.decodeCanonical(bindingID, byteCount: 32)
        else {
            throw RelaySessionCryptoError.invalidEphemeralKey
        }

        var inputKeyMaterial = sharedSecret
        inputKeyMaterial.append(Data(relaySecret.utf8))
        let inputKey = SymmetricKey(data: inputKeyMaterial)
        return RelaySessionKeys(
            bindingID: bindingID,
            bindingDigest: bindingDigest,
            confirmationKey: deriveKey(inputKey: inputKey, salt: bindingDigest, label: confirmationLabel),
            clientTrafficSecret: deriveKey(inputKey: inputKey, salt: bindingDigest, label: clientTrafficLabel),
            runtimeTrafficSecret: deriveKey(inputKey: inputKey, salt: bindingDigest, label: runtimeTrafficLabel)
        )
    }

    fileprivate static func publicKey(from canonicalHex: String) throws -> P256.KeyAgreement.PublicKey {
        guard let representation = RelayCryptoHex.decodeCanonical(canonicalHex, byteCount: 65),
              representation.first == 0x04
        else {
            throw RelaySessionCryptoError.invalidEphemeralKey
        }
        do {
            return try P256.KeyAgreement.PublicKey(x963Representation: representation)
        } catch {
            throw RelaySessionCryptoError.invalidEphemeralKey
        }
    }

    private static func validateSessionInputs(
        clientSessionNonce: String,
        runtimeSessionNonce: String,
        clientEphemeralKey: String,
        runtimeEphemeralKey: String
    ) throws {
        guard RelaySessionNonce.isCanonical(clientSessionNonce),
              RelaySessionNonce.isCanonical(runtimeSessionNonce)
        else {
            throw RelaySessionCryptoError.invalidSessionNonce
        }
        _ = try publicKey(from: clientEphemeralKey)
        _ = try publicKey(from: runtimeEphemeralKey)
    }

    private static func deriveKey(
        inputKey: SymmetricKey,
        salt: Data,
        label: Data
    ) -> Data {
        let key = HKDF<SHA256>.deriveKey(
            inputKeyMaterial: inputKey,
            salt: salt,
            info: label,
            outputByteCount: 32
        )
        return key.withUnsafeBytes { Data($0) }
    }
}

public enum RelayKeyConfirmation {
    private static let proofPrefix = "AetherLink relay key confirmation v2\nrole\n"

    public static func proof(
        role: RelayKeyConfirmationRole,
        sessionKeys: RelaySessionKeys
    ) -> String {
        let message = proofPrefix + role.rawValue +
            "\ntransport_binding\n" + sessionKeys.bindingID
        let authenticationCode = HMAC<SHA256>.authenticationCode(
            for: Data(message.utf8),
            using: SymmetricKey(data: sessionKeys.confirmationKey)
        )
        return RelayCryptoHex.lowercase(Data(authenticationCode))
    }

    public static func controlLine(
        role: RelayKeyConfirmationRole,
        sessionKeys: RelaySessionKeys
    ) -> String {
        "AETHERLINK_RELAY confirm \(role.rawValue) binding=\(sessionKeys.bindingID) " +
            "proof=\(proof(role: role, sessionKeys: sessionKeys))\n"
    }

    public static func validateControlLine(
        _ line: String,
        expectedRole: RelayKeyConfirmationRole,
        sessionKeys: RelaySessionKeys
    ) -> Bool {
        guard let parsed = parseControlLine(line) else { return false }
        let expectedProof = proof(role: expectedRole, sessionKeys: sessionKeys)
        return parsed.role == expectedRole.rawValue &&
            constantTimeEqual(parsed.bindingID, sessionKeys.bindingID) &&
            constantTimeEqual(parsed.proof, expectedProof)
    }

    public static func isCanonicalDigest(_ value: String) -> Bool {
        RelayCryptoHex.decodeCanonical(value, byteCount: 32) != nil
    }

    private static func parseControlLine(_ line: String) -> (role: String, bindingID: String, proof: String)? {
        guard line.hasSuffix("\n"),
              !line.dropLast().contains("\n"),
              !line.contains("\r")
        else { return nil }
        let parts = line.dropLast().split(separator: " ", omittingEmptySubsequences: false)
        guard parts.count == 5,
              parts[0] == "AETHERLINK_RELAY",
              parts[1] == "confirm",
              parts[3].hasPrefix("binding="),
              parts[4].hasPrefix("proof=")
        else { return nil }
        let bindingID = String(parts[3].dropFirst("binding=".count))
        let proof = String(parts[4].dropFirst("proof=".count))
        guard isCanonicalDigest(bindingID), isCanonicalDigest(proof) else { return nil }
        return (String(parts[2]), bindingID, proof)
    }

    private static func constantTimeEqual(_ lhs: String, _ rhs: String) -> Bool {
        let lhsBytes = Array(lhs.utf8)
        let rhsBytes = Array(rhs.utf8)
        var difference = lhsBytes.count ^ rhsBytes.count
        for index in 0..<max(lhsBytes.count, rhsBytes.count) {
            let lhsByte = index < lhsBytes.count ? lhsBytes[index] : 0
            let rhsByte = index < rhsBytes.count ? rhsBytes[index] : 0
            difference |= Int(lhsByte ^ rhsByte)
        }
        return difference == 0
    }
}

enum RelayCryptoHex {
    static func lowercase(_ data: Data) -> String {
        data.map { String(format: "%02x", $0) }.joined()
    }

    static func decodeCanonical(_ value: String, byteCount: Int) -> Data? {
        guard value.utf8.count == byteCount * 2 else { return nil }
        var bytes = [UInt8]()
        bytes.reserveCapacity(byteCount)
        var highNibble: UInt8?
        for byte in value.utf8 {
            let nibble: UInt8
            switch byte {
            case UInt8(ascii: "0")...UInt8(ascii: "9"):
                nibble = byte - UInt8(ascii: "0")
            case UInt8(ascii: "a")...UInt8(ascii: "f"):
                nibble = byte - UInt8(ascii: "a") + 10
            default:
                return nil
            }
            if let high = highNibble {
                bytes.append((high << 4) | nibble)
                highNibble = nil
            } else {
                highNibble = nibble
            }
        }
        return Data(bytes)
    }
}
