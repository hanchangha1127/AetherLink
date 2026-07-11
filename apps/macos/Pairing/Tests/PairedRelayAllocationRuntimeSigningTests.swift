import BridgeProtocol
import CryptoKit
import Foundation
import XCTest
@testable import Pairing

final class PairedRelayAllocationRuntimeSigningTests: XCTestCase {
    func testFileStoreUsesPersistentRuntimeIdentityAndRuntimeRoleTranscript() throws {
        let fileURL = temporaryIdentityFileURL()
        let firstStore = FileRuntimeIdentityKeyStore(fileURL: fileURL)
        let identity = try firstStore.loadOrCreate()
        let challenge = try makeChallenge(runtimeFingerprint: identity.fingerprint)

        let firstProof = try sign(challenge, using: firstStore)
        let secondProof = try sign(
            challenge,
            using: FileRuntimeIdentityKeyStore(fileURL: fileURL)
        )

        XCTAssertEqual(firstProof.publicKeyBase64, identity.publicKeyBase64)
        XCTAssertEqual(secondProof.publicKeyBase64, identity.publicKeyBase64)
        XCTAssertTrue(firstProof.verify(challenge: challenge))
        XCTAssertTrue(secondProof.verify(challenge: challenge))
        try assertRuntimeProofCannotBePresentedAsClientProof(
            firstProof,
            challenge: challenge
        )
    }

    func testKeychainStoreUsesPersistentRuntimeIdentityAndRuntimeRoleTranscript() throws {
        let service = "dev.aetherlink.tests.paired-allocation.\(UUID().uuidString)"
        let account = "runtime-signing-key"
        let firstStore = RuntimeIdentityKeyStore(service: service, account: account)
        defer { try? firstStore.delete() }
        let identity = try loadOrSkip(firstStore)
        let challenge = try makeChallenge(runtimeFingerprint: identity.fingerprint)

        let firstProof = try sign(challenge, using: firstStore)
        let secondProof = try sign(
            challenge,
            using: RuntimeIdentityKeyStore(service: service, account: account)
        )

        XCTAssertEqual(firstProof.publicKeyBase64, identity.publicKeyBase64)
        XCTAssertEqual(secondProof.publicKeyBase64, identity.publicKeyBase64)
        XCTAssertTrue(firstProof.verify(challenge: challenge))
        XCTAssertTrue(secondProof.verify(challenge: challenge))
        try assertRuntimeProofCannotBePresentedAsClientProof(
            firstProof,
            challenge: challenge
        )
    }

    func testStoresRejectRuntimeFingerprintPresentationOverride() throws {
        let fileStore = FileRuntimeIdentityKeyStore(fileURL: temporaryIdentityFileURL())
        let fileIdentity = try fileStore.loadOrCreate()
        let wrongFileChallenge = try makeChallenge(
            runtimeFingerprint: differentFingerprint(from: fileIdentity.fingerprint)
        )
        assertFingerprintMismatch(wrongFileChallenge, signer: fileStore)

        let keychainStore = RuntimeIdentityKeyStore(
            service: "dev.aetherlink.tests.paired-allocation.\(UUID().uuidString)",
            account: "runtime-signing-key"
        )
        defer { try? keychainStore.delete() }
        let keychainIdentity = try loadOrSkip(keychainStore)
        let wrongKeychainChallenge = try makeChallenge(
            runtimeFingerprint: differentFingerprint(from: keychainIdentity.fingerprint)
        )
        assertFingerprintMismatch(wrongKeychainChallenge, signer: keychainStore)
    }

    func testRuntimeProofRejectsTranscriptMutation() throws {
        let store = FileRuntimeIdentityKeyStore(fileURL: temporaryIdentityFileURL())
        let identity = try store.loadOrCreate()
        let challenge = try makeChallenge(runtimeFingerprint: identity.fingerprint)
        let proof = try sign(challenge, using: store)
        let mutatedChallenge = try makeChallenge(
            runtimeFingerprint: identity.fingerprint,
            requestID: "request-mutated"
        )

        XCTAssertTrue(proof.verify(challenge: challenge))
        XCTAssertFalse(proof.verify(challenge: mutatedChallenge))
    }

    func testDeletingFileRotatesSignerAndInvalidatesOldFingerprint() throws {
        let fileURL = temporaryIdentityFileURL()
        let store = FileRuntimeIdentityKeyStore(fileURL: fileURL)
        let firstIdentity = try store.loadOrCreate()
        let firstChallenge = try makeChallenge(
            runtimeFingerprint: firstIdentity.fingerprint
        )
        let firstProof = try sign(firstChallenge, using: store)

        try FileManager.default.removeItem(at: fileURL)

        let rotatedStore = FileRuntimeIdentityKeyStore(fileURL: fileURL)
        let secondIdentity = try rotatedStore.loadOrCreate()
        XCTAssertNotEqual(secondIdentity, firstIdentity)
        XCTAssertTrue(firstProof.verify(challenge: firstChallenge))
        assertFingerprintMismatch(firstChallenge, signer: rotatedStore)

        let secondChallenge = try makeChallenge(
            runtimeFingerprint: secondIdentity.fingerprint
        )
        let secondProof = try sign(secondChallenge, using: rotatedStore)
        XCTAssertEqual(secondProof.publicKeyBase64, secondIdentity.publicKeyBase64)
        XCTAssertTrue(secondProof.verify(challenge: secondChallenge))
    }

    func testDeletingKeychainItemRotatesSignerAndInvalidatesOldFingerprint() throws {
        let store = RuntimeIdentityKeyStore(
            service: "dev.aetherlink.tests.paired-allocation.\(UUID().uuidString)",
            account: "runtime-signing-key"
        )
        defer { try? store.delete() }
        let firstIdentity = try loadOrSkip(store)
        let firstChallenge = try makeChallenge(
            runtimeFingerprint: firstIdentity.fingerprint
        )
        let firstProof = try sign(firstChallenge, using: store)

        try store.delete()

        let secondIdentity = try loadOrSkip(store)
        XCTAssertNotEqual(secondIdentity, firstIdentity)
        XCTAssertTrue(firstProof.verify(challenge: firstChallenge))
        assertFingerprintMismatch(firstChallenge, signer: store)

        let secondChallenge = try makeChallenge(
            runtimeFingerprint: secondIdentity.fingerprint
        )
        let secondProof = try sign(secondChallenge, using: store)
        XCTAssertEqual(secondProof.publicKeyBase64, secondIdentity.publicKeyBase64)
        XCTAssertTrue(secondProof.verify(challenge: secondChallenge))
    }

    private func sign(
        _ challenge: PairedRelayAllocationAuthorizationChallenge,
        using signer: any PairedRelayAllocationRuntimeSigning
    ) throws -> PairedRelayAllocationRuntimeProof {
        try signer.signPairedRelayAllocationAuthorization(challenge)
    }

    private func assertFingerprintMismatch(
        _ challenge: PairedRelayAllocationAuthorizationChallenge,
        signer: any PairedRelayAllocationRuntimeSigning,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertThrowsError(
            try signer.signPairedRelayAllocationAuthorization(challenge),
            file: file,
            line: line
        ) { error in
            XCTAssertEqual(
                error as? PairedRelayAllocationAuthorizationError,
                .invalidFingerprint("runtime_key_fingerprint"),
                file: file,
                line: line
            )
        }
    }

    private func assertRuntimeProofCannotBePresentedAsClientProof(
        _ runtimeProof: PairedRelayAllocationRuntimeProof,
        challenge: PairedRelayAllocationAuthorizationChallenge,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws {
        let clientProof = try PairedRelayAllocationClientProof(
            publicKeyBase64: runtimeProof.publicKeyBase64,
            signatureBase64: runtimeProof.signatureBase64
        )
        XCTAssertFalse(
            clientProof.verify(challenge: challenge),
            file: file,
            line: line
        )
    }

    private func loadOrSkip(
        _ store: RuntimeIdentityKeyStore
    ) throws -> RuntimeIdentityKey {
        do {
            return try store.loadOrCreate()
        } catch let error as RuntimeIdentityKeyStoreError {
            throw XCTSkip(
                "Keychain is unavailable for this test run: \(error.localizedDescription)"
            )
        }
    }

    private func makeChallenge(
        runtimeFingerprint: String,
        requestID: String = "request-runtime-store"
    ) throws -> PairedRelayAllocationAuthorizationChallenge {
        try PairedRelayAllocationAuthorizationChallenge(
            operation: .claim,
            requestID: requestID,
            authorizationID: "authorization-runtime-store",
            currentRelayID: "rt2-\(String(repeating: "1", count: 64))",
            nextRelayID: "rt2-\(String(repeating: "5", count: 64))",
            routeTokenHash: String(repeating: "2", count: 64),
            runtimeKeyFingerprint: runtimeFingerprint,
            clientKeyFingerprint: runtimeFingerprint,
            currentTicketGeneration: 7,
            nextTicketGeneration: 8,
            currentRelayExpiresAtEpochMillis: 1_780_000_100_000,
            currentRelayNonce: "current-runtime-store",
            nextRelayExpiresAtEpochMillis: 1_780_003_600_000,
            nextRelayNonce: "next-runtime-store",
            challenge: String(repeating: "3", count: 64),
            challengeExpiresAtEpochMillis: 1_780_000_000_123,
            transportBinding: String(repeating: "4", count: 64)
        )
    }

    private func differentFingerprint(from fingerprint: String) -> String {
        fingerprint == String(repeating: "0", count: 64)
            ? String(repeating: "1", count: 64)
            : String(repeating: "0", count: 64)
    }

    private func temporaryIdentityFileURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent(
                "aetherlink-paired-allocation-signing-tests",
                isDirectory: true
            )
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("runtime-identity.json")
    }
}
