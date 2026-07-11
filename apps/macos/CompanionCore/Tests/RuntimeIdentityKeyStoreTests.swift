import CryptoKit
import BridgeProtocol
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

    func testAuthChallengeMessageDataPreservesV1AndBuildsBoundV2Bytes() {
        let binding = String(repeating: "a", count: 64)

        XCTAssertEqual(
            String(decoding: RuntimeIdentityKeyStore.authChallengeMessageData(
                deviceID: "android-device-1",
                nonce: "nonce-1"
            ), as: UTF8.self),
            "AetherLink runtime auth challenge v1\nandroid-device-1\nnonce-1"
        )
        XCTAssertEqual(
            String(decoding: RuntimeIdentityKeyStore.authChallengeMessageData(
                deviceID: "android-device-1",
                nonce: "nonce-1",
                transportBinding: binding
            ), as: UTF8.self),
            "AetherLink runtime auth challenge v2\nandroid-device-1\nnonce-1\n\(binding)"
        )
    }

    func testFileStoreSignsTransportBoundV2AuthChallengeWithoutV1Downgrade() throws {
        let fileURL = temporaryIdentityFileURL()
        let store = FileRuntimeIdentityKeyStore(fileURL: fileURL)
        let identity = try store.loadOrCreate()
        let binding = String(repeating: "b", count: 64)

        let signature = try store.signAuthChallenge(
            deviceID: "android-device-1",
            nonce: "nonce-1",
            transportBinding: binding
        )

        XCTAssertTrue(RuntimeIdentityKeyStore.verifyAuthChallengeSignature(
            publicKeyBase64: identity.publicKeyBase64,
            deviceID: "android-device-1",
            nonce: "nonce-1",
            signatureBase64: signature.signatureBase64,
            transportBinding: binding
        ))
        XCTAssertFalse(RuntimeIdentityKeyStore.verifyAuthChallengeSignature(
            publicKeyBase64: identity.publicKeyBase64,
            deviceID: "android-device-1",
            nonce: "nonce-1",
            signatureBase64: signature.signatureBase64
        ))
        XCTAssertFalse(RuntimeIdentityKeyStore.verifyAuthChallengeSignature(
            publicKeyBase64: identity.publicKeyBase64,
            deviceID: "android-device-1",
            nonce: "nonce-1",
            signatureBase64: signature.signatureBase64,
            transportBinding: String(repeating: "c", count: 64)
        ))
    }

    func testKeychainStoreSignsTransportBoundV2AuthChallenge() throws {
        let service = "dev.aetherlink.tests.runtime-identity.\(UUID().uuidString)"
        let account = "runtime-signing-key"
        let store = RuntimeIdentityKeyStore(service: service, account: account)
        defer { try? store.delete() }
        let identity = try loadOrSkip(store)
        let binding = String(repeating: "d", count: 64)

        let signature = try store.signAuthChallenge(
            deviceID: "android-device-1",
            nonce: "nonce-1",
            transportBinding: binding
        )

        XCTAssertTrue(RuntimeIdentityKeyStore.verifyAuthChallengeSignature(
            publicKeyBase64: identity.publicKeyBase64,
            deviceID: "android-device-1",
            nonce: "nonce-1",
            signatureBase64: signature.signatureBase64,
            transportBinding: binding
        ))
    }

    func testRuntimeIdentitySignersRejectNoncanonicalTransportBindings() throws {
        let fileStore = FileRuntimeIdentityKeyStore(fileURL: temporaryIdentityFileURL())
        let invalidBindings = [
            String(repeating: "A", count: 64),
            String(repeating: "a", count: 63),
            String(repeating: "١", count: 64),
        ]

        for binding in invalidBindings {
            XCTAssertThrowsError(try fileStore.signAuthChallenge(
                deviceID: "android-device-1",
                nonce: "nonce-1",
                transportBinding: binding
            )) { error in
                guard case RuntimeIdentityKeyStoreError.invalidTransportBinding = error else {
                    XCTFail("Expected invalidTransportBinding, got \(error)")
                    return
                }
            }
            XCTAssertFalse(RuntimeIdentityKeyStore.verifyAuthChallengeSignature(
                publicKeyBase64: "invalid",
                deviceID: "android-device-1",
                nonce: "nonce-1",
                signatureBase64: "invalid",
                transportBinding: binding
            ))
        }
    }

    func testFileStoreSignsRelayAuthorizationWithPersistedKeyAndRejectsSubstitution() throws {
        let store = FileRuntimeIdentityKeyStore(fileURL: temporaryIdentityFileURL())
        let persistedIdentity = try store.loadOrCreate()
        let relayIdentity = try store.relayRuntimeIdentity()
        let allocation = try allocationChallenge(fingerprint: relayIdentity.fingerprint)
        let registration = try registrationChallenge(fingerprint: relayIdentity.fingerprint)

        XCTAssertEqual(relayIdentity.publicKeyBase64, persistedIdentity.publicKeyBase64)
        XCTAssertEqual(relayIdentity.fingerprint, persistedIdentity.fingerprint)
        try assertCanonicalSignerIdentity(relayIdentity)

        let allocationProof = try store.signRelayAllocationChallenge(allocation)
        let registrationProof = try store.signRelayRuntimeRegistrationChallenge(registration)

        try assertProof(
            allocationProof,
            verifies: allocation.signedMessageData(),
            expectedIdentity: relayIdentity
        )
        try assertProof(
            registrationProof,
            verifies: registration.signedMessageData(),
            expectedIdentity: relayIdentity
        )

        let mutatedAllocation = try RelayAllocationIdentityChallenge(
            operation: allocation.operation,
            relayID: allocation.relayID,
            routeTokenHash: allocation.routeTokenHash,
            runtimeKeyFingerprint: allocation.runtimeKeyFingerprint,
            ticketGeneration: allocation.ticketGeneration + 1,
            challenge: allocation.challenge,
            challengeExpiresAtEpochMillis: allocation.challengeExpiresAtEpochMillis
        )
        let mutatedRegistration = try RelayRuntimeRegistrationIdentityChallenge(
            relayID: registration.relayID,
            relayExpiresAtEpochMillis: registration.relayExpiresAtEpochMillis,
            relayNonce: "mutated-relay-nonce",
            runtimeKeyFingerprint: registration.runtimeKeyFingerprint,
            ticketGeneration: registration.ticketGeneration,
            sessionNonce: registration.sessionNonce,
            ephemeralKey: registration.ephemeralKey,
            challenge: registration.challenge,
            challengeExpiresAtEpochMillis: registration.challengeExpiresAtEpochMillis
        )
        let wrongIdentity = try makeRelayIdentity(for: P256.Signing.PrivateKey())

        XCTAssertFalse(RelayIdentityAuthorization.verify(
            signatureBase64: allocationProof.signatureBase64,
            messageData: mutatedAllocation.signedMessageData(),
            runtimeIdentity: relayIdentity
        ))
        XCTAssertFalse(RelayIdentityAuthorization.verify(
            signatureBase64: registrationProof.signatureBase64,
            messageData: mutatedRegistration.signedMessageData(),
            runtimeIdentity: relayIdentity
        ))
        XCTAssertFalse(RelayIdentityAuthorization.verify(
            signatureBase64: allocationProof.signatureBase64,
            messageData: allocation.signedMessageData(),
            runtimeIdentity: wrongIdentity
        ))
        XCTAssertFalse(RelayIdentityAuthorization.verify(
            signatureBase64: registrationProof.signatureBase64,
            messageData: registration.signedMessageData(),
            runtimeIdentity: wrongIdentity
        ))
    }

    func testKeychainStoreSignsBothRelayAuthorizationChallengesWithActualSignerIdentity() throws {
        let service = "dev.aetherlink.tests.relay-identity.\(UUID().uuidString)"
        let account = "runtime-signing-key"
        let store = RuntimeIdentityKeyStore(service: service, account: account)
        defer { try? store.delete() }
        let persistedIdentity = try loadOrSkip(store)
        let relayIdentity = try store.relayRuntimeIdentity()
        let allocation = try allocationChallenge(fingerprint: relayIdentity.fingerprint)
        let registration = try registrationChallenge(fingerprint: relayIdentity.fingerprint)

        XCTAssertEqual(relayIdentity.publicKeyBase64, persistedIdentity.publicKeyBase64)
        XCTAssertEqual(relayIdentity.fingerprint, persistedIdentity.fingerprint)
        try assertCanonicalSignerIdentity(relayIdentity)

        try assertProof(
            store.signRelayAllocationChallenge(allocation),
            verifies: allocation.signedMessageData(),
            expectedIdentity: relayIdentity
        )
        try assertProof(
            store.signRelayRuntimeRegistrationChallenge(registration),
            verifies: registration.signedMessageData(),
            expectedIdentity: relayIdentity
        )
    }

    func testRelayAuthorizationSignersRejectPresentationFingerprintOverrides() throws {
        let fileStore = FileRuntimeIdentityKeyStore(fileURL: temporaryIdentityFileURL())
        let forgedFingerprint = String(repeating: "0", count: 64)
        let forgedAllocation = try allocationChallenge(fingerprint: forgedFingerprint)
        let forgedRegistration = try registrationChallenge(fingerprint: forgedFingerprint)

        XCTAssertThrowsError(try fileStore.signRelayAllocationChallenge(forgedAllocation)) { error in
            XCTAssertEqual(error as? RelayIdentityAuthorizationError, .invalidChallenge)
        }
        XCTAssertThrowsError(try fileStore.signRelayRuntimeRegistrationChallenge(forgedRegistration)) { error in
            XCTAssertEqual(error as? RelayIdentityAuthorizationError, .invalidChallenge)
        }

        let service = "dev.aetherlink.tests.relay-identity.\(UUID().uuidString)"
        let keychainStore = RuntimeIdentityKeyStore(service: service, account: "runtime-signing-key")
        defer { try? keychainStore.delete() }
        _ = try loadOrSkip(keychainStore)

        XCTAssertThrowsError(try keychainStore.signRelayAllocationChallenge(forgedAllocation)) { error in
            XCTAssertEqual(error as? RelayIdentityAuthorizationError, .invalidChallenge)
        }
        XCTAssertThrowsError(try keychainStore.signRelayRuntimeRegistrationChallenge(forgedRegistration)) { error in
            XCTAssertEqual(error as? RelayIdentityAuthorizationError, .invalidChallenge)
        }
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

    private func allocationChallenge(
        fingerprint: String
    ) throws -> RelayAllocationIdentityChallenge {
        try RelayAllocationIdentityChallenge(
            operation: .create,
            relayID: "rt2-store-test",
            routeTokenHash: String(repeating: "a", count: 64),
            runtimeKeyFingerprint: fingerprint,
            ticketGeneration: 7,
            challenge: String(repeating: "b", count: 64),
            challengeExpiresAtEpochMillis: 1_780_000_000_123
        )
    }

    private func registrationChallenge(
        fingerprint: String
    ) throws -> RelayRuntimeRegistrationIdentityChallenge {
        try RelayRuntimeRegistrationIdentityChallenge(
            relayID: "rt2-store-test",
            relayExpiresAtEpochMillis: 1_780_000_000_000,
            relayNonce: "relay-nonce-store-test",
            runtimeKeyFingerprint: fingerprint,
            ticketGeneration: 7,
            sessionNonce: String(repeating: "c", count: 32),
            ephemeralKey: "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1",
            challenge: String(repeating: "d", count: 64),
            challengeExpiresAtEpochMillis: 1_780_000_000_999
        )
    }

    private func assertCanonicalSignerIdentity(
        _ identity: RelayRuntimeIdentity,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws {
        let publicKeyData = try XCTUnwrap(
            Data(base64Encoded: identity.publicKeyBase64),
            file: file,
            line: line
        )
        let publicKey = try P256.Signing.PublicKey(derRepresentation: publicKeyData)
        XCTAssertEqual(publicKey.derRepresentation, publicKeyData, file: file, line: line)
        XCTAssertEqual(
            SHA256.hash(data: publicKeyData).map { String(format: "%02x", $0) }.joined(),
            identity.fingerprint,
            file: file,
            line: line
        )
    }

    private func assertProof(
        _ proof: RelayIdentityAuthorizationProof,
        verifies messageData: Data,
        expectedIdentity: RelayRuntimeIdentity,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws {
        XCTAssertEqual(proof.runtimeIdentity, expectedIdentity, file: file, line: line)
        let signatureData = try XCTUnwrap(
            Data(base64Encoded: proof.signatureBase64),
            file: file,
            line: line
        )
        XCTAssertNoThrow(
            try P256.Signing.ECDSASignature(derRepresentation: signatureData),
            file: file,
            line: line
        )
        XCTAssertTrue(
            RelayIdentityAuthorization.verify(
                signatureBase64: proof.signatureBase64,
                messageData: messageData,
                runtimeIdentity: proof.runtimeIdentity
            ),
            file: file,
            line: line
        )
    }

    private func makeRelayIdentity(
        for privateKey: P256.Signing.PrivateKey
    ) throws -> RelayRuntimeIdentity {
        let publicKeyData = privateKey.publicKey.derRepresentation
        return try RelayRuntimeIdentity(
            publicKeyBase64: publicKeyData.base64EncodedString(),
            fingerprint: SHA256.hash(data: publicKeyData)
                .map { String(format: "%02x", $0) }
                .joined()
        )
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
