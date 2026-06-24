import CryptoKit
import Foundation
import Pairing
import XCTest

final class RuntimeIdentityKeyStoreTests: XCTestCase {
    func testLoadOrCreatePersistsRuntimeIdentityForSameKeychainSlot() throws {
        let service = "dev.aetherlink.tests.runtime-identity.\(UUID().uuidString)"
        let account = "runtime-signing-key"
        let store = RuntimeIdentityKeyStore(service: service, account: account)
        defer { try? store.delete() }

        let first = try loadOrSkip(store)
        let second = try loadOrSkip(RuntimeIdentityKeyStore(service: service, account: account))

        XCTAssertEqual(first, second)
        XCTAssertFalse(first.publicKeyBase64.isEmpty)
        XCTAssertEqual(first.fingerprint, try fingerprint(forPublicKeyBase64: first.publicKeyBase64))
    }

    func testDeleteRotatesRuntimeIdentityKey() throws {
        let service = "dev.aetherlink.tests.runtime-identity.\(UUID().uuidString)"
        let account = "runtime-signing-key"
        let store = RuntimeIdentityKeyStore(service: service, account: account)
        defer { try? store.delete() }

        let first = try loadOrSkip(store)
        try store.delete()
        let second = try loadOrSkip(store)

        XCTAssertNotEqual(first.publicKeyBase64, second.publicKeyBase64)
        XCTAssertNotEqual(first.fingerprint, second.fingerprint)
    }

    private func loadOrSkip(_ store: RuntimeIdentityKeyStore) throws -> RuntimeIdentityKey {
        do {
            return try store.loadOrCreate()
        } catch let error as RuntimeIdentityKeyStoreError {
            throw XCTSkip("Keychain is unavailable for this test run: \(error.localizedDescription)")
        }
    }

    private func fingerprint(forPublicKeyBase64 publicKeyBase64: String) throws -> String {
        let publicKeyData = try XCTUnwrap(Data(base64Encoded: publicKeyBase64))
        return SHA256.hash(data: publicKeyData)
            .map { String(format: "%02x", $0) }
            .joined()
    }
}
