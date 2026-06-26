import CryptoKit
import Foundation
import Security

public struct RuntimeIdentityKey: Equatable, Sendable {
    public var publicKeyBase64: String
    public var fingerprint: String

    public init(publicKeyBase64: String, fingerprint: String) {
        self.publicKeyBase64 = publicKeyBase64
        self.fingerprint = fingerprint
    }
}

public struct RuntimeChallengeSignature: Equatable, Sendable {
    public var runtimeKeyFingerprint: String
    public var signatureBase64: String

    public init(runtimeKeyFingerprint: String, signatureBase64: String) {
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.signatureBase64 = signatureBase64
    }
}

public protocol RuntimeChallengeSigning: Sendable {
    func signAuthChallenge(deviceID: String, nonce: String) throws -> RuntimeChallengeSignature
}

public enum RuntimeIdentityKeyStoreError: Error, LocalizedError, Sendable {
    case keychainReadFailed(OSStatus)
    case keychainWriteFailed(OSStatus)
    case keychainDeleteFailed(OSStatus)
    case invalidStoredKey

    public var errorDescription: String? {
        switch self {
        case .keychainReadFailed(let status):
            return "Could not read the runtime identity key from Keychain: \(status)"
        case .keychainWriteFailed(let status):
            return "Could not write the runtime identity key to Keychain: \(status)"
        case .keychainDeleteFailed(let status):
            return "Could not delete the runtime identity key from Keychain: \(status)"
        case .invalidStoredKey:
            return "The stored runtime identity key is invalid."
        }
    }
}

public final class RuntimeIdentityKeyStore: RuntimeChallengeSigning, @unchecked Sendable {
    private static let authChallengeContext = "AetherLink runtime auth challenge v1"

    private let service: String
    private let account: String

    public init(
        service: String = "dev.aetherlink.runtime-identity",
        account: String = "runtime-signing-private-key"
    ) {
        self.service = service
        self.account = account
    }

    public func loadOrCreate() throws -> RuntimeIdentityKey {
        let privateKey = try loadPrivateKey() ?? createAndStorePrivateKey()
        return Self.identityKey(from: privateKey)
    }

    public func signAuthChallenge(deviceID: String, nonce: String) throws -> RuntimeChallengeSignature {
        let privateKey = try loadPrivateKey() ?? createAndStorePrivateKey()
        let digest = Self.authChallengeDigest(deviceID: deviceID, nonce: nonce)
        let signature = try privateKey.signature(for: digest)
        return RuntimeChallengeSignature(
            runtimeKeyFingerprint: Self.identityKey(from: privateKey).fingerprint,
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
    }

    public func delete() throws {
        let status = SecItemDelete(keychainQuery() as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw RuntimeIdentityKeyStoreError.keychainDeleteFailed(status)
        }
    }

    private func loadPrivateKey() throws -> P256.Signing.PrivateKey? {
        var query = keychainQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        switch status {
        case errSecSuccess:
            guard let data = item as? Data,
                  let privateKey = try? P256.Signing.PrivateKey(rawRepresentation: data)
            else {
                throw RuntimeIdentityKeyStoreError.invalidStoredKey
            }
            return privateKey
        case errSecItemNotFound:
            return nil
        default:
            throw RuntimeIdentityKeyStoreError.keychainReadFailed(status)
        }
    }

    private func createAndStorePrivateKey() throws -> P256.Signing.PrivateKey {
        let privateKey = P256.Signing.PrivateKey()
        var item = keychainQuery()
        item[kSecValueData as String] = privateKey.rawRepresentation
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly

        let status = SecItemAdd(item as CFDictionary, nil)
        guard status == errSecSuccess || status == errSecDuplicateItem else {
            throw RuntimeIdentityKeyStoreError.keychainWriteFailed(status)
        }
        if status == errSecDuplicateItem, let loaded = try loadPrivateKey() {
            return loaded
        }
        return privateKey
    }

    private func keychainQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
    }

    public static func identityKey(from privateKey: P256.Signing.PrivateKey) -> RuntimeIdentityKey {
        let publicKeyData = privateKey.publicKey.derRepresentation
        let fingerprint = SHA256.hash(data: publicKeyData)
            .map { String(format: "%02x", $0) }
            .joined()
        return RuntimeIdentityKey(
            publicKeyBase64: publicKeyData.base64EncodedString(),
            fingerprint: fingerprint
        )
    }

    public static func authChallengeMessageData(deviceID: String, nonce: String) -> Data {
        Data("\(authChallengeContext)\n\(deviceID)\n\(nonce)".utf8)
    }

    public static func verifyAuthChallengeSignature(
        publicKeyBase64: String,
        deviceID: String,
        nonce: String,
        signatureBase64: String
    ) -> Bool {
        guard let publicKeyData = Data(base64Encoded: publicKeyBase64),
              let signatureData = Data(base64Encoded: signatureBase64),
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: publicKeyData),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: signatureData)
        else {
            return false
        }
        return publicKey.isValidSignature(
            signature,
            for: authChallengeDigest(deviceID: deviceID, nonce: nonce)
        )
    }

    private static func authChallengeDigest(deviceID: String, nonce: String) -> SHA256.Digest {
        SHA256.hash(data: authChallengeMessageData(deviceID: deviceID, nonce: nonce))
    }

}
