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

    func testFileStoreLoadOrCreatePersistsRuntimeIdentity() throws {
        let fileURL = temporaryIdentityFileURL()
        let store = FileRuntimeIdentityKeyStore(fileURL: fileURL)

        let first = try store.loadOrCreate()
        let second = try FileRuntimeIdentityKeyStore(fileURL: fileURL).loadOrCreate()

        XCTAssertEqual(first, second)
        XCTAssertFalse(first.publicKeyBase64.isEmpty)
        XCTAssertEqual(first.fingerprint, try fingerprint(forPublicKeyBase64: first.publicKeyBase64))
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
        XCTAssertEqual(try directoryPermissions(at: fileURL.deletingLastPathComponent()), 0o700)
    }

    func testFileStoreCorrectsBroadPermissionsWithoutRotatingIdentity() throws {
        let fileURL = temporaryIdentityFileURL()
        let store = FileRuntimeIdentityKeyStore(fileURL: fileURL)
        let first = try store.loadOrCreate()
        let directoryURL = fileURL.deletingLastPathComponent()

        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: directoryURL.path)
        try FileManager.default.setAttributes([.posixPermissions: 0o644], ofItemAtPath: fileURL.path)

        let second = try FileRuntimeIdentityKeyStore(fileURL: fileURL).loadOrCreate()

        XCTAssertEqual(first, second)
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
        XCTAssertEqual(try directoryPermissions(at: directoryURL), 0o700)
    }

    func testFileStoreSignsVerifiableAuthChallenge() throws {
        let fileURL = temporaryIdentityFileURL()
        let store = FileRuntimeIdentityKeyStore(fileURL: fileURL)
        let identity = try store.loadOrCreate()

        let signature = try store.signAuthChallenge(deviceID: "android-device-1", nonce: "nonce-1")

        XCTAssertEqual(signature.runtimeKeyFingerprint, identity.fingerprint)
        XCTAssertTrue(RuntimeIdentityKeyStore.verifyAuthChallengeSignature(
            publicKeyBase64: identity.publicKeyBase64,
            deviceID: "android-device-1",
            nonce: "nonce-1",
            signatureBase64: signature.signatureBase64
        ))
        XCTAssertFalse(RuntimeIdentityKeyStore.verifyAuthChallengeSignature(
            publicKeyBase64: identity.publicKeyBase64,
            deviceID: "android-device-1",
            nonce: "different-nonce",
            signatureBase64: signature.signatureBase64
        ))
    }

    func testFileStoreThrowsStructuredErrorForInvalidFile() throws {
        let fileURL = temporaryIdentityFileURL()
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try Data("not-json".utf8).write(to: fileURL)

        XCTAssertThrowsError(try FileRuntimeIdentityKeyStore(fileURL: fileURL).loadOrCreate()) { error in
            guard case FileRuntimeIdentityKeyStoreError.invalidData(let path, let reason) = error else {
                XCTFail("Expected invalidData, got \(error)")
                return
            }
            XCTAssertEqual(path, fileURL.standardizedFileURL.path)
            XCTAssertFalse(reason.isEmpty)
        }
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

    private func temporaryIdentityFileURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-file-identity-tests", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("runtime-identity.json")
    }

    private func filePermissions(at fileURL: URL) throws -> Int {
        let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
        return try XCTUnwrap(attributes[.posixPermissions] as? Int) & 0o777
    }

    private func directoryPermissions(at directoryURL: URL) throws -> Int {
        let attributes = try FileManager.default.attributesOfItem(atPath: directoryURL.path)
        return try XCTUnwrap(attributes[.posixPermissions] as? Int) & 0o777
    }
}
