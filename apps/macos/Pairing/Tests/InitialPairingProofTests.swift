import CryptoKit
import XCTest
@testable import Pairing

final class InitialPairingProofTests: XCTestCase {
    private let binding = String(repeating: "0123456789abcdef", count: 4)
    private let runtimePublicKey = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEaxfR8uEsQkf4vOblY6RA8ncDfYEt6zOg9KE5RdiYwpZP40Li/hp/m47n60p8D54WK84zV2sxXs7LtkBoN79R9Q=="
    private let runtimeFingerprint = "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3"
    private let clientPublicKey = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfPJ7GI0DT36KUjgDBLUaw8CJaeJ38hs1pgtI/EdmmXgHd1UQ247QQCk9msafdDDbun2t5jzpgimeBLedInhz0Q=="
    private let clientFingerprint = "dc0ce633dbcc913dafafa4b89ac44d8ce683fdfc3f60c8bdf21213b9f2b534ba"

    func testFixedClientAndRuntimeResultDigests() throws {
        let client = try fixedClientProof(transportBinding: binding)
        XCTAssertEqual(client.requestDigest(), "7ecceffa7e90feeaebdac054b6be386307bc26db9914a9b0d5660f9c671f0965")
        XCTAssertFalse(client.signedMessageData().last == UInt8(ascii: "\n"))

        let result = try fixedResult(transportBinding: binding)
        XCTAssertEqual(result.resultDigest(), "9bf74c2179506f02c8b071f507465e29ec35530608bcdf72f325f23dd419f84f")
        XCTAssertFalse(result.signedMessageData().last == UInt8(ascii: "\n"))
    }

    func testClientProofVerifiesAndRejectsWrongKeyAndTampering() throws {
        var proof = try fixedClientProof(transportBinding: binding)
        XCTAssertTrue(proof.verify())

        proof.pairingCode = "654321"
        XCTAssertFalse(proof.verify())
        proof = try fixedClientProof(transportBinding: binding)
        proof.clientPublicKey = runtimePublicKey
        proof.clientKeyFingerprint = runtimeFingerprint
        XCTAssertFalse(proof.verify())
        proof = try fixedClientProof(transportBinding: binding)
        proof.transportBinding = "none"
        XCTAssertFalse(proof.verify())
    }

    func testRuntimeResultProofVerifiesAndRejectsWrongKeyAndTampering() throws {
        let runtimeKey = try scalarPrivateKey(1)
        let result = try fixedResult(transportBinding: binding)
        let signature = try runtimeKey.signature(for: SHA256.hash(data: result.signedMessageData()))
        var proof = try InitialPairingRuntimeResultProof(
            result: result,
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
        XCTAssertTrue(proof.verify())

        proof.result.message += "!"
        XCTAssertFalse(proof.verify())
        proof = try InitialPairingRuntimeResultProof(
            result: result,
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
        proof.result.runtimePublicKey = clientPublicKey
        proof.result.runtimeKeyFingerprint = clientFingerprint
        XCTAssertFalse(proof.verify())
    }

    func testRejectsNoncanonicalBase64DERKeyFingerprintAndRejectedResult() throws {
        let valid = try fixedClientProof(transportBinding: binding)
        XCTAssertThrowsError(try fixedClientProof(
            transportBinding: binding,
            clientPublicKey: clientPublicKey + "\n"
        )) { XCTAssertEqual($0 as? InitialPairingProofError, .invalidPublicKey("client_public_key")) }
        XCTAssertThrowsError(try fixedClientProof(
            transportBinding: binding,
            clientFingerprint: clientFingerprint.uppercased()
        )) { XCTAssertEqual($0 as? InitialPairingProofError, .invalidFingerprint("client_key_fingerprint")) }

        let rawSignature = Data(repeating: 1, count: 64).base64EncodedString()
        XCTAssertThrowsError(try fixedClientProof(
            transportBinding: binding,
            signatureBase64: rawSignature
        )) { XCTAssertEqual($0 as? InitialPairingProofError, .invalidSignature) }
        let canonicalDER = try XCTUnwrap(Data(base64Encoded: valid.signatureBase64))
        var noncanonicalDER = Data([canonicalDER[0], 0x81, canonicalDER[1]])
        noncanonicalDER.append(canonicalDER.dropFirst(2))
        XCTAssertThrowsError(try fixedClientProof(
            transportBinding: binding,
            signatureBase64: noncanonicalDER.base64EncodedString()
        )) { XCTAssertEqual($0 as? InitialPairingProofError, .invalidSignature) }
        XCTAssertThrowsError(try fixedClientProof(
            transportBinding: binding,
            signatureBase64: valid.signatureBase64 + "\n"
        )) { XCTAssertEqual($0 as? InitialPairingProofError, .invalidSignature) }

        XCTAssertThrowsError(try InitialPairingRuntimeResult(
            requestID: "request-fixed-1",
            pairingRequestDigest: valid.requestDigest(),
            accepted: false,
            runtimeDeviceID: "runtime-fixed-1",
            runtimePublicKey: runtimePublicKey,
            runtimeKeyFingerprint: runtimeFingerprint,
            trustedDeviceID: "client-fixed-1",
            message: "rejected",
            transportBinding: binding
        )) { XCTAssertEqual($0 as? InitialPairingProofError, .rejectedResultCannotBeSigned) }
    }

    func testNoneAndCanonicalBindingAreAcceptedAndOtherFormsRejected() throws {
        XCTAssertNoThrow(try fixedClientProof(transportBinding: "none"))
        XCTAssertNoThrow(try fixedResult(transportBinding: "none", requestDigest: String(repeating: "a", count: 64)))
        XCTAssertNoThrow(try fixedClientProof(transportBinding: binding))

        for invalid in ["NONE", "", String(repeating: "A", count: 64), String(repeating: "0", count: 63), String(repeating: "０", count: 64)] {
            XCTAssertThrowsError(try fixedClientProof(transportBinding: invalid)) {
                XCTAssertEqual($0 as? InitialPairingProofError, .invalidField("transport_binding"))
            }
        }
    }

    func testFileStoreSignsTypedRuntimeResultWithPersistedIdentity() throws {
        let store = FileRuntimeIdentityKeyStore(fileURL: temporaryIdentityFileURL())
        let identity = try store.loadOrCreate()
        let signingResult = try result(for: identity, transportBinding: "none")

        let proof = try store.signInitialPairingResult(signingResult)
        XCTAssertTrue(proof.verify())

        let otherIdentity = RuntimeIdentityKeyStore.identityKey(from: P256.Signing.PrivateKey())
        XCTAssertThrowsError(try store.signInitialPairingResult(try result(for: otherIdentity, transportBinding: "none")))
        var rejected = signingResult
        rejected.accepted = false
        XCTAssertThrowsError(try store.signInitialPairingResult(rejected)) {
            XCTAssertEqual($0 as? InitialPairingProofError, .rejectedResultCannotBeSigned)
        }
    }

    func testKeychainStoreSignsTypedRuntimeResultWithPersistedIdentity() throws {
        let store = RuntimeIdentityKeyStore(
            service: "dev.aetherlink.tests.initial-pairing.\(UUID().uuidString)",
            account: "runtime-signing-key"
        )
        defer { try? store.delete() }
        let identity: RuntimeIdentityKey
        do {
            identity = try store.loadOrCreate()
        } catch let error as RuntimeIdentityKeyStoreError {
            throw XCTSkip("Keychain is unavailable for this test run: \(error.localizedDescription)")
        }

        XCTAssertTrue(try store.signInitialPairingResult(result(for: identity, transportBinding: binding)).verify())
    }

    private func fixedClientProof(
        transportBinding: String,
        clientPublicKey: String? = nil,
        clientFingerprint: String? = nil,
        signatureBase64: String? = nil
    ) throws -> InitialPairingClientProof {
        let clientKey = try scalarPrivateKey(2)
        let placeholder = try clientKey.signature(for: SHA256.hash(data: Data("placeholder".utf8)))
        var proof = try InitialPairingClientProof(
            requestID: "request-fixed-1",
            pairingNonce: "nonce-fixed-1",
            pairingCode: "123456",
            runtimeDeviceID: "runtime-fixed-1",
            runtimePublicKey: runtimePublicKey,
            runtimeKeyFingerprint: runtimeFingerprint,
            clientDeviceID: "client-fixed-1",
            clientDeviceName: "Android Device",
            clientPublicKey: clientPublicKey ?? self.clientPublicKey,
            clientKeyFingerprint: clientFingerprint ?? self.clientFingerprint,
            transportBinding: transportBinding,
            signatureBase64: signatureBase64 ?? placeholder.derRepresentation.base64EncodedString()
        )
        if signatureBase64 == nil, clientPublicKey == nil, clientFingerprint == nil {
            proof.signatureBase64 = try clientKey
                .signature(for: SHA256.hash(data: proof.signedMessageData()))
                .derRepresentation.base64EncodedString()
        }
        return proof
    }

    private func fixedResult(
        transportBinding: String,
        requestDigest: String = "7ecceffa7e90feeaebdac054b6be386307bc26db9914a9b0d5660f9c671f0965"
    ) throws -> InitialPairingRuntimeResult {
        try InitialPairingRuntimeResult(
            requestID: "request-fixed-1",
            pairingRequestDigest: requestDigest,
            accepted: true,
            runtimeDeviceID: "runtime-fixed-1",
            runtimePublicKey: runtimePublicKey,
            runtimeKeyFingerprint: runtimeFingerprint,
            trustedDeviceID: "client-fixed-1",
            message: "Android Device is now trusted by AetherLink Runtime.",
            transportBinding: transportBinding
        )
    }

    private func result(
        for identity: RuntimeIdentityKey,
        transportBinding: String
    ) throws -> InitialPairingRuntimeResult {
        try InitialPairingRuntimeResult(
            requestID: "request-store-1",
            pairingRequestDigest: String(repeating: "a", count: 64),
            accepted: true,
            runtimeDeviceID: "runtime-store-1",
            runtimePublicKey: identity.publicKeyBase64,
            runtimeKeyFingerprint: identity.fingerprint,
            trustedDeviceID: "client-store-1",
            message: "Client is now trusted.",
            transportBinding: transportBinding
        )
    }

    private func scalarPrivateKey(_ scalar: UInt8) throws -> P256.Signing.PrivateKey {
        var raw = Data(repeating: 0, count: 32)
        raw[31] = scalar
        return try P256.Signing.PrivateKey(rawRepresentation: raw)
    }

    private func temporaryIdentityFileURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-initial-pairing-tests", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("runtime-identity.json")
    }
}
