import Foundation
import XCTest
@testable import P2PNATContracts

final class P2PNATSessionCryptoVectorTests: XCTestCase {
    func testSharedSessionCryptoVectorsMatchOnDirectAndRelayTranscripts() throws {
        let fixture = try loadFixture()
        let clientKey = try P2PNATSessionEphemeralKey(
            testPrivateScalar: Data(hex: fixture.keyAgreement.clientPrivateScalarHex)
        )
        let runtimeKey = try P2PNATSessionEphemeralKey(
            testPrivateScalar: Data(hex: fixture.keyAgreement.runtimePrivateScalarHex)
        )

        XCTAssertEqual(clientKey.publicKeyX963, try Data(hex: fixture.keyAgreement.clientPublicKeyX963Hex))
        XCTAssertEqual(runtimeKey.publicKeyX963, try Data(hex: fixture.keyAgreement.runtimePublicKeyX963Hex))

        for vector in fixture.cases {
            let transcript = try makeTranscript(vector.transcriptInput)
            XCTAssertEqual(transcript.canonicalBytes(), try Data(hex: vector.expectedCanonicalHex), vector.id)
            let caseClientKey = try P2PNATSessionEphemeralKey(
                testPrivateScalar: Data(hex: fixture.keyAgreement.clientPrivateScalarHex)
            )
            let caseRuntimeKey = try P2PNATSessionEphemeralKey(
                testPrivateScalar: Data(hex: fixture.keyAgreement.runtimePrivateScalarHex)
            )
            let materialClientKey = try P2PNATSessionEphemeralKey(
                testPrivateScalar: Data(hex: fixture.keyAgreement.clientPrivateScalarHex)
            )

            let clientKeys = try P2PNATSessionCrypto.deriveKeys(
                localRole: .client,
                localEphemeralKey: caseClientKey,
                transcript: transcript
            )
            let runtimeKeys = try P2PNATSessionCrypto.deriveKeys(
                localRole: .runtime,
                localEphemeralKey: caseRuntimeKey,
                transcript: transcript
            )
            let material = try P2PNATSessionCrypto.vectorMaterial(
                localRole: .client,
                localEphemeralKey: materialClientKey,
                transcript: transcript
            )

            XCTAssertEqual(material.sharedSecret, try Data(hex: fixture.keyAgreement.expectedSharedSecretHex), vector.id)
            XCTAssertEqual(material.salt, try Data(hex: vector.expectedHkdfSaltHex), vector.id)
            XCTAssertEqual(material.info, try Data(hex: vector.expectedHkdfInfoHex), vector.id)
            XCTAssertEqual(material.prk, try Data(hex: vector.expectedHkdfPrkHex), vector.id)
            XCTAssertEqual(material.okm, try Data(hex: vector.expectedHkdfOkmHex), vector.id)
            XCTAssertEqual(clientKeys.transcriptDigest, try Data(hex: vector.expectedTranscriptSha256Hex), vector.id)
            XCTAssertEqual(clientKeys.clientTrafficKeyBytes, try Data(hex: vector.expectedKeys.clientTrafficKeyHex), vector.id)
            XCTAssertEqual(clientKeys.runtimeTrafficKeyBytes, try Data(hex: vector.expectedKeys.runtimeTrafficKeyHex), vector.id)
            XCTAssertEqual(clientKeys.confirmationKeyBytes, try Data(hex: vector.expectedKeys.confirmationKeyHex), vector.id)
            XCTAssertEqual(runtimeKeys.clientTrafficKeyBytes, clientKeys.clientTrafficKeyBytes, vector.id)
            XCTAssertEqual(runtimeKeys.runtimeTrafficKeyBytes, clientKeys.runtimeTrafficKeyBytes, vector.id)
            XCTAssertEqual(runtimeKeys.confirmationKeyBytes, clientKeys.confirmationKeyBytes, vector.id)
            XCTAssertEqual(try clientKeys.confirmation(for: .client), try Data(hex: vector.expectedConfirmations.client), vector.id)
            XCTAssertEqual(try clientKeys.confirmation(for: .runtime), try Data(hex: vector.expectedConfirmations.runtime), vector.id)

            let clientHandshake = P2PNATSessionHandshake(localRole: .client, keys: clientKeys)
            let runtimeHandshake = P2PNATSessionHandshake(localRole: .runtime, keys: runtimeKeys)
            XCTAssertThrowsError(try clientHandshake.makeCipher()) {
                XCTAssertEqual($0 as? P2PNATSessionCryptoError, .confirmationIncomplete)
            }
            let clientProof = try clientHandshake.localConfirmation()
            let runtimeProof = try runtimeHandshake.localConfirmation()
            try clientHandshake.acceptPeerConfirmation(runtimeProof)
            try runtimeHandshake.acceptPeerConfirmation(clientProof)
            let clientCipher = try clientHandshake.makeCipher()
            let runtimeCipher = try runtimeHandshake.makeCipher()
            XCTAssertThrowsError(try clientHandshake.makeCipher()) {
                XCTAssertEqual($0 as? P2PNATSessionCryptoError, .cipherAlreadyCreated)
            }

            let expectedClient = vector.traffic.client
            let clientPlaintext = try Data(hex: expectedClient.plaintextHex)
            let clientPayload = try clientCipher.seal(clientPlaintext)
            XCTAssertEqual(try P2PNATSessionCipher.nonce(role: .client, sequence: 0), try Data(hex: expectedClient.nonceHex), vector.id)
            XCTAssertEqual(P2PNATSessionCipher.aad(transcript: transcript, senderRole: .client, sequence: 0), try Data(hex: expectedClient.aadHex), vector.id)
            XCTAssertEqual(clientPayload.ciphertext, try Data(hex: expectedClient.ciphertextHex), vector.id)
            XCTAssertEqual(clientPayload.tag, try Data(hex: expectedClient.tagHex), vector.id)
            XCTAssertEqual(try runtimeCipher.open(clientPayload), clientPlaintext, vector.id)

            let expectedRuntime = vector.traffic.runtime
            let runtimePlaintext = try Data(hex: expectedRuntime.plaintextHex)
            let runtimePayload = try runtimeCipher.seal(runtimePlaintext)
            XCTAssertEqual(try P2PNATSessionCipher.nonce(role: .runtime, sequence: 0), try Data(hex: expectedRuntime.nonceHex), vector.id)
            XCTAssertEqual(P2PNATSessionCipher.aad(transcript: transcript, senderRole: .runtime, sequence: 0), try Data(hex: expectedRuntime.aadHex), vector.id)
            XCTAssertEqual(runtimePayload.ciphertext, try Data(hex: expectedRuntime.ciphertextHex), vector.id)
            XCTAssertEqual(runtimePayload.tag, try Data(hex: expectedRuntime.tagHex), vector.id)
            XCTAssertEqual(try clientCipher.open(runtimePayload), runtimePlaintext, vector.id)
        }
    }

    func testEcdhNormalizesLeadingZeroAndRejectsInvalidScalars() throws {
        let vector = try loadFixture().keyAgreement.leadingZeroNormalizationCase
        let client = try P2PNATSessionEphemeralKey(testPrivateScalar: Data(hex: vector.clientPrivateScalarHex))
        let runtime = try P2PNATSessionEphemeralKey(testPrivateScalar: Data(hex: vector.runtimePrivateScalarHex))
        let transcript = try makeTranscript(
            try loadFixture().cases[0].transcriptInput,
            clientKey: client.publicKeyX963,
            runtimeKey: runtime.publicKeyX963
        )
        let material = try P2PNATSessionCrypto.vectorMaterial(
            localRole: .client,
            localEphemeralKey: client,
            transcript: transcript
        )

        XCTAssertEqual(client.publicKeyX963, try Data(hex: vector.clientPublicKeyX963Hex))
        XCTAssertEqual(runtime.publicKeyX963, try Data(hex: vector.runtimePublicKeyX963Hex))
        XCTAssertEqual(material.sharedSecret, try Data(hex: vector.expectedSharedSecretHex))
        XCTAssertEqual(material.sharedSecret.first, 0)
        XCTAssertThrowsError(try P2PNATSessionEphemeralKey(testPrivateScalar: Data(repeating: 0, count: 32)))
        XCTAssertThrowsError(
            try P2PNATSessionEphemeralKey(
                testPrivateScalar: Data(hex: "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551")
            )
        )
    }

    func testExplicitEphemeralKeyCloseDropsPrivateKeyAndRejectsReplay() throws {
        let fixture = try loadFixture()
        let key = try P2PNATSessionEphemeralKey(
            testPrivateScalar: Data(hex: fixture.keyAgreement.clientPrivateScalarHex)
        )
        let transcript = try makeTranscript(fixture.cases[0].transcriptInput)
        XCTAssertTrue(key.testOnlyRetainsPrivateKey)

        key.close()
        key.close()

        XCTAssertFalse(key.testOnlyRetainsPrivateKey)
        XCTAssertTrue(key.testOnlyIsClosed)
        XCTAssertThrowsError(
            try P2PNATSessionCrypto.deriveKeys(
                localRole: .client,
                localEphemeralKey: key,
                transcript: transcript
            )
        ) {
            XCTAssertEqual(
                $0 as? P2PNATSessionCryptoError,
                .ephemeralKeyClosed
            )
        }
    }

    func testConcurrentCloseAndDeriveHaveOneLinearizedTerminalState() throws {
        let fixture = try loadFixture()
        let transcript = try makeTranscript(fixture.cases[0].transcriptInput)

        for _ in 0..<64 {
            let key = try P2PNATSessionEphemeralKey(
                testPrivateScalar: Data(
                    hex: fixture.keyAgreement.clientPrivateScalarHex
                )
            )
            let resultLock = NSLock()
            var derivationSuccesses = 0
            var derivationErrors: [Error] = []

            DispatchQueue.concurrentPerform(iterations: 2) { index in
                if index == 0 {
                    key.close()
                    return
                }
                do {
                    _ = try P2PNATSessionCrypto.deriveKeys(
                        localRole: .client,
                        localEphemeralKey: key,
                        transcript: transcript
                    )
                    resultLock.withLock { derivationSuccesses += 1 }
                } catch {
                    resultLock.withLock { derivationErrors.append(error) }
                }
            }

            XCTAssertFalse(key.testOnlyRetainsPrivateKey)
            if derivationSuccesses == 1 {
                XCTAssertTrue(derivationErrors.isEmpty)
                XCTAssertTrue(key.testOnlyIsConsumed)
                XCTAssertFalse(key.testOnlyIsClosed)
            } else {
                XCTAssertEqual(derivationSuccesses, 0)
                XCTAssertEqual(derivationErrors.count, 1)
                XCTAssertEqual(
                    derivationErrors.first as? P2PNATSessionCryptoError,
                    .ephemeralKeyClosed
                )
                XCTAssertTrue(key.testOnlyIsClosed)
                XCTAssertFalse(key.testOnlyIsConsumed)
            }
        }
    }

    func testConfirmationReflectionTamperingReplayAndTranscriptSubstitutionFailClosed() throws {
        let fixture = try loadFixture()
        XCTAssertEqual(Set(fixture.negativeVectors.map(\.id)), Set([
            "off_curve_public_key", "truncated_public_key", "zero_private_scalar",
            "out_of_range_private_scalar", "transcript_substitution", "role_reflection",
            "generation_replay", "nonce_reuse", "modified_gcm_tag", "provider_failure",
        ]))
        XCTAssertEqual(
            Set(fixture.negativeVectors.filter { $0.platforms.contains("swift") }.map(\.id)),
            Set(fixture.negativeVectors.map(\.id)).subtracting(["provider_failure"])
        )
        XCTAssertEqual(
            fixture.negativeVectors.first { $0.id == "provider_failure" }?.platforms,
            ["android"]
        )
        let vector = fixture.cases[0]
        let transcript = try makeTranscript(vector.transcriptInput)
        let clientKey = try P2PNATSessionEphemeralKey(testPrivateScalar: Data(hex: fixture.keyAgreement.clientPrivateScalarHex))
        let runtimeKey = try P2PNATSessionEphemeralKey(testPrivateScalar: Data(hex: fixture.keyAgreement.runtimePrivateScalarHex))
        let clientKeys = try P2PNATSessionCrypto.deriveKeys(localRole: .client, localEphemeralKey: clientKey, transcript: transcript)
        let runtimeKeys = try P2PNATSessionCrypto.deriveKeys(localRole: .runtime, localEphemeralKey: runtimeKey, transcript: transcript)

        let reflected = P2PNATSessionHandshake(localRole: .client, keys: clientKeys)
        XCTAssertThrowsError(try reflected.acceptPeerConfirmation(clientKeys.confirmation(for: .client))) {
            XCTAssertEqual($0 as? P2PNATSessionCryptoError, .invalidConfirmation)
        }

        let sender = P2PNATSessionCipher(localRole: .client, keys: clientKeys)
        let receiver = P2PNATSessionCipher(localRole: .runtime, keys: runtimeKeys)
        let payload = try sender.seal(Data("authenticated".utf8))
        var tamperedTag = payload.tag
        tamperedTag[tamperedTag.startIndex] ^= 0x01
        XCTAssertThrowsError(try receiver.open(P2PNATSealedPayload(ciphertext: payload.ciphertext, tag: tamperedTag))) {
            XCTAssertEqual($0 as? P2PNATSessionCryptoError, .authenticationFailed)
        }
        XCTAssertEqual(try receiver.open(payload), Data("authenticated".utf8))
        XCTAssertThrowsError(try receiver.open(payload))

        let substituted = try makeTranscript(
            vector.transcriptInput,
            pairDigest: String(repeating: "1", count: 64)
        )
        let substitutedRuntimeKey = try P2PNATSessionEphemeralKey(
            testPrivateScalar: Data(hex: fixture.keyAgreement.runtimePrivateScalarHex)
        )
        let substitutedRuntimeKeys = try P2PNATSessionCrypto.deriveKeys(
            localRole: .runtime,
            localEphemeralKey: substitutedRuntimeKey,
            transcript: substituted
        )
        let wrongTranscriptReceiver = P2PNATSessionCipher(localRole: .runtime, keys: substitutedRuntimeKeys)
        let freshSender = P2PNATSessionCipher(localRole: .client, keys: clientKeys)
        XCTAssertThrowsError(try wrongTranscriptReceiver.open(freshSender.seal(Data("bound".utf8))))

        let replayedGeneration = try makeTranscript(vector.transcriptInput, generation: vector.transcriptInput.generation + 1)
        let replayRuntimeKey = try P2PNATSessionEphemeralKey(
            testPrivateScalar: Data(hex: fixture.keyAgreement.runtimePrivateScalarHex)
        )
        let replayRuntimeKeys = try P2PNATSessionCrypto.deriveKeys(
            localRole: .runtime,
            localEphemeralKey: replayRuntimeKey,
            transcript: replayedGeneration
        )
        let replayReceiver = P2PNATSessionCipher(localRole: .runtime, keys: replayRuntimeKeys)
        let generationSender = P2PNATSessionCipher(localRole: .client, keys: clientKeys)
        XCTAssertThrowsError(try replayReceiver.open(generationSender.seal(Data("generation-bound".utf8))))
    }

    func testFixtureScopedInvalidPublicKeysExecuteOnSwift() throws {
        let fixture = try loadFixture()
        let input = fixture.cases[0].transcriptInput
        let mutations = Dictionary(uniqueKeysWithValues: fixture.negativeVectors.map { ($0.id, $0) })
        let offCurve = Data([0x04]) + Data(repeating: 0, count: 64)
        let truncated = try Data(hex: input.runtimeEphemeralKeyHex).dropLast()

        XCTAssertEqual(mutations["off_curve_public_key"]?.operation, "derive_keys")
        XCTAssertEqual(mutations["off_curve_public_key"]?.mutation, "runtime_public_key_all_zero_coordinates")
        XCTAssertEqual(mutations["off_curve_public_key"]?.expectedResult, "reject_before_key_agreement")
        XCTAssertTrue(mutations["off_curve_public_key"]?.platforms.contains("swift") == true)
        XCTAssertThrowsError(try makeTranscript(input, runtimeKey: offCurve))

        XCTAssertEqual(mutations["truncated_public_key"]?.operation, "derive_keys")
        XCTAssertEqual(mutations["truncated_public_key"]?.mutation, "runtime_public_key_remove_last_byte")
        XCTAssertEqual(mutations["truncated_public_key"]?.expectedResult, "reject_before_key_agreement")
        XCTAssertTrue(mutations["truncated_public_key"]?.platforms.contains("swift") == true)
        XCTAssertThrowsError(try makeTranscript(input, runtimeKey: Data(truncated)))
    }

    func testCipherAliasesAndConcurrentOperationsDoNotReuseSequences() throws {
        let fixture = try loadFixture()
        let transcript = try makeTranscript(fixture.cases[0].transcriptInput)
        let client = try P2PNATSessionEphemeralKey(
            testPrivateScalar: Data(hex: fixture.keyAgreement.clientPrivateScalarHex)
        )
        let runtime = try P2PNATSessionEphemeralKey(
            testPrivateScalar: Data(hex: fixture.keyAgreement.runtimePrivateScalarHex)
        )
        let clientKeys = try P2PNATSessionCrypto.deriveKeys(
            localRole: .client,
            localEphemeralKey: client,
            transcript: transcript
        )
        let runtimeKeys = try P2PNATSessionCrypto.deriveKeys(
            localRole: .runtime,
            localEphemeralKey: runtime,
            transcript: transcript
        )

        let firstHandshake = P2PNATSessionHandshake(localRole: .client, keys: clientKeys)
        let duplicateHandshake = P2PNATSessionHandshake(localRole: .client, keys: clientKeys)
        _ = try firstHandshake.localConfirmation()
        _ = try duplicateHandshake.localConfirmation()
        let runtimeProof = try runtimeKeys.confirmation(for: .runtime)
        try firstHandshake.acceptPeerConfirmation(runtimeProof)
        try duplicateHandshake.acceptPeerConfirmation(runtimeProof)
        let issuanceLock = NSLock()
        var issuanceSuccesses = 0
        var issuanceErrors: [Error] = []
        let handshakes = [firstHandshake, duplicateHandshake]
        DispatchQueue.concurrentPerform(iterations: handshakes.count) { index in
            do {
                _ = try handshakes[index].makeCipher()
                issuanceLock.withLock { issuanceSuccesses += 1 }
            } catch {
                issuanceLock.withLock { issuanceErrors.append(error) }
            }
        }
        XCTAssertEqual(issuanceSuccesses, 1)
        XCTAssertEqual(issuanceErrors.count, 1)
        XCTAssertEqual(issuanceErrors.first as? P2PNATSessionCryptoError, .cipherAlreadyCreated)

        let consumedEphemeral = try P2PNATSessionEphemeralKey(
            testPrivateScalar: Data(hex: fixture.keyAgreement.clientPrivateScalarHex)
        )
        _ = try P2PNATSessionCrypto.deriveKeys(
            localRole: .client,
            localEphemeralKey: consumedEphemeral,
            transcript: transcript
        )
        XCTAssertThrowsError(
            try P2PNATSessionCrypto.deriveKeys(
                localRole: .client,
                localEphemeralKey: consumedEphemeral,
                transcript: transcript
            )
        ) {
            XCTAssertEqual($0 as? P2PNATSessionCryptoError, .ephemeralKeyAlreadyUsed)
        }

        let aliasedCipher = P2PNATSessionCipher(localRole: .client, keys: clientKeys)
        let alias = aliasedCipher
        let first = try aliasedCipher.seal(Data("same".utf8))
        let second = try alias.seal(Data("same".utf8))
        XCTAssertNotEqual(first.ciphertext + first.tag, second.ciphertext + second.tag)

        let concurrentCipher = P2PNATSessionCipher(localRole: .client, keys: clientKeys)
        let resultLock = NSLock()
        var payloads: [P2PNATSealedPayload] = []
        var sealErrors: [Error] = []
        DispatchQueue.concurrentPerform(iterations: 2) { _ in
            do {
                let payload = try concurrentCipher.seal(Data("concurrent".utf8))
                resultLock.withLock { payloads.append(payload) }
            } catch {
                resultLock.withLock { sealErrors.append(error) }
            }
        }
        XCTAssertTrue(sealErrors.isEmpty)
        XCTAssertEqual(payloads.count, 2)
        XCTAssertEqual(Set(payloads.map { $0.ciphertext + $0.tag }).count, 2)

        let sender = P2PNATSessionCipher(localRole: .client, keys: clientKeys)
        let receiver = P2PNATSessionCipher(localRole: .runtime, keys: runtimeKeys)
        let sequenceZero = try sender.seal(Data("zero".utf8))
        var openSuccesses = 0
        var openFailures = 0
        DispatchQueue.concurrentPerform(iterations: 2) { _ in
            do {
                _ = try receiver.open(sequenceZero)
                resultLock.withLock { openSuccesses += 1 }
            } catch {
                resultLock.withLock { openFailures += 1 }
            }
        }
        XCTAssertEqual(openSuccesses, 1)
        XCTAssertEqual(openFailures, 1)
        XCTAssertEqual(try receiver.open(sender.seal(Data("one".utf8))), Data("one".utf8))
    }

    func testCounterExhaustionFailsBeforeCryptography() throws {
        let fixture = try loadFixture()
        let transcript = try makeTranscript(fixture.cases[0].transcriptInput)
        let client = try P2PNATSessionEphemeralKey(testPrivateScalar: Data(hex: fixture.keyAgreement.clientPrivateScalarHex))
        let runtime = try P2PNATSessionEphemeralKey(testPrivateScalar: Data(hex: fixture.keyAgreement.runtimePrivateScalarHex))
        let keys = try P2PNATSessionCrypto.deriveKeys(localRole: .client, localEphemeralKey: client, transcript: transcript)
        let runtimeKeys = try P2PNATSessionCrypto.deriveKeys(localRole: .runtime, localEphemeralKey: runtime, transcript: transcript)
        XCTAssertEqual(
            try P2PNATSessionCipher.nonce(role: .client, sequence: UInt64.max - 1),
            Data("CLNT".utf8) + Data(repeating: 0xff, count: 7) + Data([0xfe])
        )
        XCTAssertThrowsError(try P2PNATSessionCipher.nonce(role: .client, sequence: UInt64.max)) {
            XCTAssertEqual($0 as? P2PNATSessionCryptoError, .counterExhausted)
        }

        let nearLimitClient = P2PNATSessionCipher(
            localRole: .client,
            keys: keys,
            sendSequence: UInt64.max - 2,
            receiveSequence: UInt64.max - 2
        )
        let nearLimitRuntime = P2PNATSessionCipher(
            localRole: .runtime,
            keys: runtimeKeys,
            sendSequence: UInt64.max - 2,
            receiveSequence: UInt64.max - 2
        )
        XCTAssertEqual(try nearLimitRuntime.open(nearLimitClient.seal(Data("client".utf8))), Data("client".utf8))
        XCTAssertEqual(try nearLimitClient.open(nearLimitRuntime.seal(Data("runtime".utf8))), Data("runtime".utf8))
        XCTAssertThrowsError(try nearLimitClient.seal(Data("x".utf8))) {
            XCTAssertEqual($0 as? P2PNATSessionCryptoError, .counterExhausted)
        }
        XCTAssertThrowsError(try nearLimitClient.open(P2PNATSealedPayload(ciphertext: Data(), tag: Data(repeating: 0, count: 16)))) {
            XCTAssertEqual($0 as? P2PNATSessionCryptoError, .counterExhausted)
        }

        let exhausted = P2PNATSessionCipher(
            localRole: .client,
            keys: keys,
            sendSequence: UInt64.max - 1,
            receiveSequence: UInt64.max - 1
        )

        XCTAssertThrowsError(try exhausted.seal(Data("x".utf8))) {
            XCTAssertEqual($0 as? P2PNATSessionCryptoError, .counterExhausted)
        }
        XCTAssertThrowsError(try exhausted.open(P2PNATSealedPayload(ciphertext: Data(), tag: Data(repeating: 0, count: 16)))) {
            XCTAssertEqual($0 as? P2PNATSessionCryptoError, .counterExhausted)
        }
    }

    private func makeTranscript(
        _ input: TranscriptInput,
        pairDigest: String? = nil,
        generation: UInt64? = nil,
        clientKey: Data? = nil,
        runtimeKey: Data? = nil
    ) throws -> IdentitySessionTranscript {
        try IdentitySessionTranscript(
            sessionId: input.sessionId,
            pairDigest: pairDigest ?? input.pairBindingDigest,
            clientFingerprint: input.clientFingerprint,
            runtimeFingerprint: input.runtimeFingerprint,
            clientKey: clientKey ?? Data(hex: input.clientEphemeralKeyHex),
            runtimeKey: runtimeKey ?? Data(hex: input.runtimeEphemeralKeyHex),
            generation: generation ?? input.generation,
            pathReceiptDigest: input.pathReceiptDigest,
            transport: P2PNATTransport(rawValue: input.transportContext)!,
            fallback: P2PNATFallback(rawValue: input.fallbackReason)!,
            protocolFloor: input.protocolFloor
        )
    }

    private func loadFixture() throws -> Fixture {
        let relative = "shared/protocol/fixtures/production-p2p-nat-v1-session-crypto-vectors.json"
        let starts = [
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true),
            URL(fileURLWithPath: #filePath).deletingLastPathComponent(),
        ]
        for start in starts {
            var directory = start.standardizedFileURL
            while true {
                let candidate = directory.appendingPathComponent(relative)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    return try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: candidate))
                }
                let parent = directory.deletingLastPathComponent()
                if parent.path == directory.path { break }
                directory = parent
            }
        }
        throw FixtureError.notFound
    }
}

private enum FixtureError: Error { case notFound, invalidHex }

private struct Fixture: Decodable {
    let keyAgreement: KeyAgreementVector
    let cases: [SessionCase]
    let negativeVectors: [NegativeVector]
}

private struct KeyAgreementVector: Decodable {
    let clientPrivateScalarHex: String
    let runtimePrivateScalarHex: String
    let clientPublicKeyX963Hex: String
    let runtimePublicKeyX963Hex: String
    let expectedSharedSecretHex: String
    let leadingZeroNormalizationCase: LeadingZeroVector
}

private struct LeadingZeroVector: Decodable {
    let clientPrivateScalarHex: String
    let runtimePrivateScalarHex: String
    let clientPublicKeyX963Hex: String
    let runtimePublicKeyX963Hex: String
    let expectedSharedSecretHex: String
}

private struct SessionCase: Decodable {
    let id: String
    let transcriptInput: TranscriptInput
    let expectedCanonicalHex: String
    let expectedTranscriptSha256Hex: String
    let expectedHkdfSaltHex: String
    let expectedHkdfInfoHex: String
    let expectedHkdfPrkHex: String
    let expectedHkdfOkmHex: String
    let expectedKeys: ExpectedKeys
    let expectedConfirmations: RoleStrings
    let traffic: TrafficVectors
}

private struct TranscriptInput: Decodable {
    let sessionId: String
    let pairBindingDigest: String
    let clientFingerprint: String
    let runtimeFingerprint: String
    let clientEphemeralKeyHex: String
    let runtimeEphemeralKeyHex: String
    let generation: UInt64
    let pathReceiptDigest: String
    let transportContext: String
    let fallbackReason: String
    let protocolFloor: UInt32
}

private struct ExpectedKeys: Decodable {
    let clientTrafficKeyHex: String
    let runtimeTrafficKeyHex: String
    let confirmationKeyHex: String
}

private struct RoleStrings: Decodable { let client: String; let runtime: String }
private struct TrafficVectors: Decodable { let client: TrafficVector; let runtime: TrafficVector }
private struct TrafficVector: Decodable {
    let sequence: UInt64
    let nonceHex: String
    let aadHex: String
    let plaintextHex: String
    let ciphertextHex: String
    let tagHex: String
}
private struct NegativeVector: Decodable {
    let id: String
    let operation: String
    let mutation: String
    let expectedResult: String
    let platforms: [String]
}

private extension NSLock {
    func withLock<T>(_ operation: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try operation()
    }
}

private extension Data {
    init(hex: String) throws {
        guard hex.count.isMultiple(of: 2), hex.allSatisfy({ $0.isNumber || ("a"..."f").contains(String($0)) }) else {
            throw FixtureError.invalidHex
        }
        self = Data(stride(from: 0, to: hex.count, by: 2).map { index in
            UInt8(hex.dropFirst(index).prefix(2), radix: 16)!
        })
    }
}
