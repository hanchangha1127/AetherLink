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

public final class RuntimeIdentityKeyStore: @unchecked Sendable {
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
}
