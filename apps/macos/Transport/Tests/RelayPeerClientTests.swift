import Darwin
import BridgeProtocol
import CryptoKit
import Foundation
import Network
import XCTest
@testable import Transport

final class RelayPeerClientTests: XCTestCase {
    func testRelayPeerConnectionCompletionReportsSuccessfulEncryptedContentProcessing() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let relayID = "relay-peer-callback-success"
        let relaySecret = "relay-peer-callback-secret"
        let relayNonce = "relay-peer-callback-route-nonce"
        let (connection, stateRecorder) = Self.startLoopbackConnection(port: server.port)
        defer { connection.cancel() }
        XCTAssertTrue(stateRecorder.waitUntilReady())

        let codec = ProtocolCodec()
        let peer = RelayPeerConnection(
            connection: connection,
            codec: codec,
            relaySecret: relaySecret,
            relayNonce: relayNonce
        )
        peer.sendRelayHandshake(relayID: relayID, runtimeIdentity: nil)
        let runtime = try parseStrictRuntimeHandshake(
            try XCTUnwrap(server.waitForHandshake()),
            relayID: relayID
        )
        let clientSessionNonce = "00112233445566778899aabbccddeeff"
        let clientEphemeralKey = RelaySessionEphemeralKey()
        let runtimeSessionKeys = try peer.prepareRelaySession(
            relayID: relayID,
            clientSessionNonce: clientSessionNonce,
            clientEphemeralKey: clientEphemeralKey.publicKeyHex
        )
        let clientSessionKeys = try RelaySessionCrypto.deriveKeys(
            localRole: .client,
            localEphemeralKey: clientEphemeralKey,
            relayID: relayID,
            routeNonce: relayNonce,
            relaySecret: relaySecret,
            clientSessionNonce: clientSessionNonce,
            runtimeSessionNonce: runtime.sessionNonce,
            clientEphemeralKey: clientEphemeralKey.publicKeyHex,
            runtimeEphemeralKey: runtime.ephemeralKey
        )
        XCTAssertEqual(runtimeSessionKeys.bindingID, clientSessionKeys.bindingID)
        try peer.activateFrameCipher(sessionKeys: runtimeSessionKeys)

        let completion = RelayPeerSendCompletionRecorder()
        let envelope = ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "relay-peer-callback-success",
            timestamp: Date(timeIntervalSince1970: 1_700_000_000),
            payload: ["status": .string("encrypted-ready")]
        )
        let plaintextBody = try codec.encodeEnvelopeBody(envelope)

        peer.send(envelope) { succeeded in
            completion.append(succeeded)
        }

        XCTAssertEqual(completion.waitForValue(), true)
        let encryptedBody = try XCTUnwrap(server.waitForFrameBody())
        XCTAssertNotEqual(encryptedBody, plaintextBody)
        var clientCipher = RelayFrameCipher(sessionKeys: clientSessionKeys)
        let decodedBody = try clientCipher.decryptRuntimeBody(encryptedBody)
        XCTAssertEqual(try codec.decodeEnvelope(decodedBody), envelope)
        XCTAssertFalse(completion.waitForAdditionalValue())
    }

    func testRelayPeerConnectionCompletionReportsEncodingFailure() {
        let connection = NWConnection(host: "127.0.0.1", port: 1, using: .tcp)
        let peer = RelayPeerConnection(
            connection: connection,
            codec: ProtocolCodec(),
            relaySecret: nil,
            relayNonce: nil
        )
        let completion = RelayPeerSendCompletionRecorder()
        let unencodableEnvelope = ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "relay-peer-callback-encoding-failure",
            payload: ["invalid_number": .number(.nan)]
        )

        peer.send(unencodableEnvelope) { succeeded in
            completion.append(succeeded)
        }

        XCTAssertEqual(completion.waitForValue(), false)
        XCTAssertFalse(completion.waitForAdditionalValue())
    }

    func testRelayPeerConnectionCompletionReportsEncryptionFailure() throws {
        let relayID = "relay-peer-callback-encryption-failure"
        let relaySecret = "relay-peer-callback-encryption-secret"
        let relayNonce = "relay-peer-callback-encryption-nonce"
        let runtimeSessionNonce = "ffeeddccbbaa99887766554433221100"
        let clientSessionNonce = "00112233445566778899aabbccddeeff"
        let runtimeEphemeralKey = RelaySessionEphemeralKey()
        let clientEphemeralKey = RelaySessionEphemeralKey()
        let sessionKeys = try RelaySessionCrypto.deriveKeys(
            localRole: .runtime,
            localEphemeralKey: runtimeEphemeralKey,
            relayID: relayID,
            routeNonce: relayNonce,
            relaySecret: relaySecret,
            clientSessionNonce: clientSessionNonce,
            runtimeSessionNonce: runtimeSessionNonce,
            clientEphemeralKey: clientEphemeralKey.publicKeyHex,
            runtimeEphemeralKey: runtimeEphemeralKey.publicKeyHex
        )
        let connection = NWConnection(host: "127.0.0.1", port: 1, using: .tcp)
        let peer = RelayPeerConnection(
            connection: connection,
            codec: ProtocolCodec(),
            relaySecret: relaySecret,
            relayNonce: relayNonce
        )
        try peer.activateFrameCipher(
            sessionKeys: sessionKeys,
            initialFrameIndex: Int64.max
        )
        let completion = RelayPeerSendCompletionRecorder()

        peer.send(ProtocolEnvelope(type: MessageType.runtimeHealth)) { succeeded in
            completion.append(succeeded)
        }

        XCTAssertEqual(completion.waitForValue(), false)
        XCTAssertFalse(completion.waitForAdditionalValue())
    }

    func testRelayPeerConnectionCompletionReportsContentProcessedErrorAfterCancellation() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let (connection, stateRecorder) = Self.startLoopbackConnection(port: server.port)
        XCTAssertTrue(stateRecorder.waitUntilReady())
        let peer = RelayPeerConnection(
            connection: connection,
            codec: ProtocolCodec(),
            relaySecret: nil,
            relayNonce: nil
        )

        connection.cancel()
        XCTAssertTrue(stateRecorder.waitUntilCancelled())

        let completion = RelayPeerSendCompletionRecorder()
        peer.send(ProtocolEnvelope(type: MessageType.runtimeHealth)) { succeeded in
            completion.append(succeeded)
        }

        XCTAssertEqual(completion.waitForValue(), false)
        XCTAssertFalse(completion.waitForAdditionalValue())
    }

    func testRelayPeerConfigurationDefaultControlLineTimeoutAllowsPhysicalQrStartup() {
        let configuration = RelayPeerConfiguration(
            host: "127.0.0.1",
            port: 43171,
            relayID: "relay-default-timeout"
        )

        XCTAssertEqual(configuration.controlLineTimeout, 45)
    }

    func testRelayPeerConfigurationPreservesRuntimeIdentityAuthorizationAcrossNonceRefresh() throws {
        let signer = try TestRelayIdentityAuthorizationSigner()
        let configuration = RelayPeerConfiguration(
            host: "127.0.0.1",
            port: 43171,
            relayID: "relay-identity-configuration",
            relaySecret: "relay-secret",
            relayNonce: "relay-nonce-1",
            runtimeIdentity: signer.identity,
            identityAuthorizationSigner: signer
        )

        let refreshed = configuration.withRelayNonce("relay-nonce-2")

        XCTAssertEqual(refreshed.runtimeIdentity, signer.identity)
        XCTAssertNotNil(refreshed.identityAuthorizationSigner)
        XCTAssertEqual(refreshed.relayNonce, "relay-nonce-2")
        XCTAssertEqual(refreshed, configuration.withRelayNonce("relay-nonce-2"))
        XCTAssertNotEqual(refreshed, configuration)
    }

    func testRelayPeerClientWaitsForAcceptedRuntimeRegistrationBeforeWaitingForPeer() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let statusRecorder = RelayStatusRecorder()
        let registeredStatus = DispatchSemaphore(value: 0)
        let readyStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-test",
                reconnectDelay: 60
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .waitingForPeer {
                    registeredStatus.signal()
                }
                if status == .ready {
                    readyStatus.signal()
                }
            },
            onMessage: { _, _ in }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-test\n")
        XCTAssertFalse(statusRecorder.contains(.waitingForPeer))

        server.write("AETHERLINK_RELAY registered\n")
        XCTAssertEqual(registeredStatus.wait(timeout: .now() + 2), .success)
        XCTAssertTrue(statusRecorder.contains(.waitingForPeer))
        XCTAssertFalse(statusRecorder.contains(.ready))

        server.write("AETHERLINK_RELAY ready\n")
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 2), .success)
        XCTAssertTrue(statusRecorder.contains(.ready))
    }

    func testRelayPeerClientTimesOutWhenRegistrationLineNeverArrives() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let statusRecorder = RelayStatusRecorder()
        let failedStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-registration-timeout",
                reconnectDelay: 60,
                controlLineTimeout: 0.1
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .failed("Relay registration timed out before ready.") {
                    failedStatus.signal()
                }
            },
            onMessage: { _, _ in }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-registration-timeout\n")
        XCTAssertEqual(failedStatus.wait(timeout: .now() + 2), .success)
        XCTAssertFalse(statusRecorder.contains(.waitingForPeer))
        XCTAssertFalse(statusRecorder.contains(.ready))
    }

    func testRelayPeerClientTimesOutWhenReadyLineNeverArrivesAfterRegistration() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let statusRecorder = RelayStatusRecorder()
        let registeredStatus = DispatchSemaphore(value: 0)
        let failedStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-ready-timeout",
                reconnectDelay: 60,
                controlLineTimeout: 0.1
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .waitingForPeer {
                    registeredStatus.signal()
                }
                if status == .failed("Relay ready line timed out after registration.") {
                    failedStatus.signal()
                }
            },
            onMessage: { _, _ in }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-ready-timeout\n")
        server.write("AETHERLINK_RELAY registered\n")
        XCTAssertEqual(registeredStatus.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(failedStatus.wait(timeout: .now() + 2), .success)
        XCTAssertFalse(statusRecorder.contains(.ready))
    }

    func testRelayPeerClientReportsDisconnectOnceWhenStoppedConnectionCancels() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let disconnectRecorder = RelayDisconnectRecorder()
        let client = RelayPeerClient()
        defer { client.stop() }
        client.onDisconnect = { id in
            disconnectRecorder.append(id)
        }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-disconnect-test",
                reconnectDelay: 60
            ),
            onMessage: { _, _ in }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-disconnect-test\n")

        client.stop()
        XCTAssertEqual(disconnectRecorder.waitForCount(1), 1)
        Thread.sleep(forTimeInterval: 0.2)
        XCTAssertEqual(disconnectRecorder.count, 1)
    }

    func testRelayPeerClientRetireKeepsCurrentConnectionAndSuppressesReconnect() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let codec = ProtocolCodec()
        let statusRecorder = RelayStatusRecorder()
        let readyStatus = DispatchSemaphore(value: 0)
        let requestHandled = DispatchSemaphore(value: 0)
        let disconnectRecorder = RelayDisconnectRecorder()
        let client = RelayPeerClient()
        defer { client.stop() }
        client.onDisconnect = { id in
            disconnectRecorder.append(id)
        }

        let responseEnvelope = ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "retired-response",
            payload: ["status": .string("retired-current-connection")]
        )
        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-retire-test",
                reconnectDelay: 0.1
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .ready {
                    readyStatus.signal()
                }
            },
            onMessage: { envelope, sink in
                XCTAssertEqual(envelope.type, MessageType.modelsList)
                XCTAssertEqual(envelope.requestID, "retired-current-request")
                XCTAssertNil(sink.transportSecurityContext)
                sink.send(responseEnvelope)
                requestHandled.signal()
            }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-retire-test\n")
        server.write("AETHERLINK_RELAY ready\n")
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 2), .success)

        client.retireAfterCurrentConnection()
        XCTAssertFalse(statusRecorder.contains(.stopped))

        let requestEnvelope = ProtocolEnvelope(
            type: MessageType.modelsList,
            requestID: "retired-current-request"
        )
        server.writeFrameBody(try codec.encodeEnvelopeBody(requestEnvelope))
        XCTAssertEqual(requestHandled.wait(timeout: .now() + 2), .success)

        let responseBody = try XCTUnwrap(server.waitForFrameBody())
        let decodedResponse = try codec.decodeEnvelope(responseBody)
        XCTAssertEqual(decodedResponse.type, responseEnvelope.type)
        XCTAssertEqual(decodedResponse.requestID, responseEnvelope.requestID)
        XCTAssertEqual(decodedResponse.payload, responseEnvelope.payload)

        server.closeAcceptedSocket()
        XCTAssertEqual(disconnectRecorder.waitForCount(1), 1)
        XCTAssertNil(server.waitForHandshake(index: 1, timeout: .now() + 0.5))
        XCTAssertFalse(statusRecorder.contains { status in
            if case .reconnecting = status {
                return true
            }
            return false
        })
    }

    func testStrictRelayPeerClientCompletesCrypto2HandshakeAndEncryptsFrames() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let codec = ProtocolCodec()
        let relayID = "relay-strict-v2"
        let relaySecret = "strict-relay-secret"
        let relayNonce = "strict-route-nonce"
        let requestHandled = DispatchSemaphore(value: 0)
        let readyStatus = DispatchSemaphore(value: 0)
        let securityContextRecorder = TransportSecurityContextRecorder()
        let client = RelayPeerClient()
        defer { client.stop() }

        let responseEnvelope = ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "strict-response",
            payload: ["status": .string("runtime-ciphertext")]
        )
        let plaintextResponseBody = try codec.encodeEnvelopeBody(responseEnvelope)

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: relayID,
                relaySecret: relaySecret,
                relayNonce: relayNonce,
                reconnectDelay: 60
            ),
            onStatusChange: { status in
                if status == .ready {
                    readyStatus.signal()
                }
            },
            onMessage: { envelope, sink in
                XCTAssertEqual(envelope.type, MessageType.modelsList)
                XCTAssertEqual(envelope.requestID, "strict-request")
                securityContextRecorder.append(sink.transportSecurityContext)
                sink.send(responseEnvelope)
                requestHandled.signal()
            }
        )

        let sessionKeys = try completeStrictHandshake(
            server: server,
            relayID: relayID,
            relaySecret: relaySecret,
            relayNonce: relayNonce,
            readyStatus: readyStatus
        )
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 2), .success)

        let requestEnvelope = ProtocolEnvelope(
            type: MessageType.modelsList,
            requestID: "strict-request",
            payload: ["probe": .string("client-ciphertext")]
        )
        var clientCipher = RelayFrameCipher(sessionKeys: sessionKeys)
        let encryptedRequestBody = try clientCipher.encryptClientBody(try codec.encodeEnvelopeBody(requestEnvelope))
        server.writeFrameBody(encryptedRequestBody)

        XCTAssertEqual(requestHandled.wait(timeout: .now() + 2), .success)
        let encryptedResponseBody = try XCTUnwrap(server.waitForFrameBody())

        XCTAssertNotEqual(encryptedResponseBody, plaintextResponseBody)
        XCTAssertNil(encryptedResponseBody.range(of: Data(MessageType.runtimeHealth.utf8)))
        XCTAssertNil(encryptedResponseBody.range(of: Data("runtime-ciphertext".utf8)))

        XCTAssertEqual(
            securityContextRecorder.value,
            TransportSecurityContext(bindingID: sessionKeys.bindingID)
        )

        var runtimeCipher = RelayFrameCipher(sessionKeys: sessionKeys)
        let decryptedResponseBody = try runtimeCipher.decryptRuntimeBody(encryptedResponseBody)
        let decodedResponse = try codec.decodeEnvelope(decryptedResponseBody)
        XCTAssertEqual(decodedResponse.version, responseEnvelope.version)
        XCTAssertEqual(decodedResponse.type, responseEnvelope.type)
        XCTAssertEqual(decodedResponse.requestID, responseEnvelope.requestID)
        XCTAssertEqual(decodedResponse.payload, responseEnvelope.payload)
    }

    func testIdentityBoundStrictRelayAuthorizesBeforeRegistrationAndReady() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let signer = try TestRelayIdentityAuthorizationSigner()
        let relayID = "relay-identity-success"
        let relaySecret = "identity-success-secret"
        let relayNonce = "identity-success-nonce"
        let waitingStatus = DispatchSemaphore(value: 0)
        let readyStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: relayID,
                relaySecret: relaySecret,
                relayNonce: relayNonce,
                reconnectDelay: 60,
                runtimeIdentity: signer.identity,
                identityAuthorizationSigner: signer
            ),
            onStatusChange: { status in
                if status == .waitingForPeer { waitingStatus.signal() }
                if status == .ready { readyStatus.signal() }
            },
            onMessage: { _, _ in }
        )

        let runtime = try parseIdentityBoundStrictRuntimeHandshake(
            try XCTUnwrap(server.waitForHandshake()),
            relayID: relayID,
            runtimeIdentity: signer.identity
        )
        let challenge = try makeRegistrationChallenge(
            relayID: relayID,
            relayNonce: relayNonce,
            runtimeIdentity: signer.identity,
            runtime: runtime
        )
        server.write(try registrationChallengeLine(challenge))

        let proof = try parseRegistrationProof(try XCTUnwrap(server.waitForControlLine()))
        XCTAssertEqual(proof.challenge, challenge.challenge)
        XCTAssertTrue(RelayIdentityAuthorization.verify(
            signatureBase64: proof.signatureBase64,
            messageData: challenge.signedMessageData(),
            runtimeIdentity: signer.identity
        ))
        XCTAssertEqual(signer.registrationSignatureCount, 1)

        let clientSessionNonce = "00112233445566778899aabbccddeeff"
        let clientEphemeralKey = RelaySessionEphemeralKey()
        let keys = try RelaySessionCrypto.deriveKeys(
            localRole: .client,
            localEphemeralKey: clientEphemeralKey,
            relayID: relayID,
            routeNonce: relayNonce,
            relaySecret: relaySecret,
            clientSessionNonce: clientSessionNonce,
            runtimeSessionNonce: runtime.sessionNonce,
            clientEphemeralKey: clientEphemeralKey.publicKeyHex,
            runtimeEphemeralKey: runtime.ephemeralKey
        )
        server.write("AETHERLINK_RELAY registered crypto=2\n")
        XCTAssertEqual(waitingStatus.wait(timeout: .now() + 2), .success)
        server.write(
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=\(clientSessionNonce) " +
                "peer_ephemeral_key=\(clientEphemeralKey.publicKeyHex)\n"
        )
        server.write(RelayKeyConfirmation.controlLine(role: .client, sessionKeys: keys))

        XCTAssertEqual(
            server.waitForControlLine(),
            RelayKeyConfirmation.controlLine(role: .runtime, sessionKeys: keys)
        )
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 2), .success)
    }

    func testIdentityBoundStrictRelayRejectsMissingAndNonExactChallengesBeforeMatcher() throws {
        let responses: [(String, (RelayRuntimeRegistrationIdentityChallenge) throws -> String)] = [
            ("missing challenge", { _ in "AETHERLINK_RELAY registered crypto=2\n" }),
            ("missing JSON fields", { _ in
                RelayRuntimeRegistrationIdentityChallenge.responsePrefix + "{}\n"
            }),
            ("unknown JSON field", { challenge in
                let encoded = try JSONEncoder().encode(challenge)
                var object = try XCTUnwrap(
                    JSONSerialization.jsonObject(with: encoded) as? [String: Any]
                )
                object["unexpected"] = true
                let data = try JSONSerialization.data(withJSONObject: object)
                return RelayRuntimeRegistrationIdentityChallenge.responsePrefix +
                    String(decoding: data, as: UTF8.self) + "\n"
            })
        ]

        for (label, response) in responses {
            try assertIdentityAuthorizationRejected(label: label) { challenge in
                try response(challenge)
            }
        }
    }

    func testIdentityBoundStrictRelayRejectsChallengeBindingMutationsBeforeSigning() throws {
        let mutations: [(String, RegistrationChallengeMutation)] = [
            ("relay id", .relayID),
            ("relay nonce", .relayNonce),
            ("runtime fingerprint", .runtimeFingerprint),
            ("session nonce", .sessionNonce),
            ("ephemeral key", .ephemeralKey)
        ]

        for (label, mutation) in mutations {
            try assertIdentityAuthorizationRejected(label: label) { challenge in
                try self.registrationChallengeLine(
                    self.mutatingRegistrationChallenge(challenge, mutation: mutation)
                )
            }
        }
    }

    func testIdentityBoundStrictRelayRejectsExpiredChallengeOrRelayLeaseBeforeSigning() throws {
        for expiresRelay in [false, true] {
            try assertIdentityAuthorizationRejected(
                label: expiresRelay ? "expired relay lease" : "expired challenge"
            ) { challenge in
                let now = Int64(Date().timeIntervalSince1970 * 1_000)
                let expired = try RelayRuntimeRegistrationIdentityChallenge(
                    relayID: challenge.relayID,
                    relayExpiresAtEpochMillis: expiresRelay ? now - 1 : challenge.relayExpiresAtEpochMillis,
                    relayNonce: challenge.relayNonce,
                    runtimeKeyFingerprint: challenge.runtimeKeyFingerprint,
                    ticketGeneration: challenge.ticketGeneration,
                    sessionNonce: challenge.sessionNonce,
                    ephemeralKey: challenge.ephemeralKey,
                    challenge: challenge.challenge,
                    challengeExpiresAtEpochMillis: expiresRelay ? challenge.challengeExpiresAtEpochMillis : now - 1
                )
                return try self.registrationChallengeLine(expired)
            }
        }
    }

    func testIdentityBoundStrictRelayClosesWhenRestrictedSignerFails() throws {
        let signer = try TestRelayIdentityAuthorizationSigner(failsRegistrationSigning: true)
        try assertIdentityAuthorizationRejected(label: "signer failure", signer: signer) { challenge in
            try self.registrationChallengeLine(challenge)
        }
        XCTAssertEqual(signer.registrationSignatureCount, 1)
    }

    func testStrictRelayPeerClientRejectsPlainRegisteredWithoutV1Fallback() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let failedStatus = DispatchSemaphore(value: 0)
        let statusRecorder = RelayStatusRecorder()
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-no-v1-fallback",
                relaySecret: "strict-secret",
                reconnectDelay: 60
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if case .failed = status {
                    failedStatus.signal()
                }
            },
            onMessage: { _, _ in
                XCTFail("Encrypted relay without peer session nonce must not receive frames")
            }
        )

        _ = try parseStrictRuntimeHandshake(try XCTUnwrap(server.waitForHandshake()), relayID: "relay-no-v1-fallback")
        server.write("AETHERLINK_RELAY registered\n")

        XCTAssertEqual(failedStatus.wait(timeout: .now() + 2), .success)
        XCTAssertTrue(statusRecorder.contains(.failed("Relay key confirmation failed.")))
        XCTAssertFalse(statusRecorder.contains(.ready))
        XCTAssertTrue(server.waitForPeerClose())
    }

    func testStrictRelayPeerClientRejectsOffCurvePeerKey() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let failedStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }
        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-off-curve",
                relaySecret: "strict-secret",
                reconnectDelay: 60
            ),
            onStatusChange: { status in
                if case .failed = status { failedStatus.signal() }
            },
            onMessage: { _, _ in XCTFail("Invalid strict peer key must close before frames") }
        )

        _ = try parseStrictRuntimeHandshake(try XCTUnwrap(server.waitForHandshake()), relayID: "relay-off-curve")
        server.write("AETHERLINK_RELAY registered crypto=2\n")
        server.write(
            "AETHERLINK_RELAY ready crypto=2 " +
                "peer_session_nonce=00112233445566778899aabbccddeeff " +
                "peer_ephemeral_key=04\(String(repeating: "0", count: 128))\n"
        )

        XCTAssertEqual(failedStatus.wait(timeout: .now() + 2), .success)
        XCTAssertTrue(server.waitForPeerClose())
    }

    func testStrictRelayPeerClientFailsClosedOnWrongClientConfirmation() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let relaySecret = "confirmation-required-secret"
        let relayNonce = "confirmation-required-route"
        let clientSessionNonce = "00112233445566778899aabbccddeeff"
        let clientEphemeralKey = RelaySessionEphemeralKey()
        let failedStatus = DispatchSemaphore(value: 0)
        let readyStatus = DispatchSemaphore(value: 0)
        let statusRecorder = RelayStatusRecorder()
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-confirmation-required",
                relaySecret: relaySecret,
                relayNonce: relayNonce,
                reconnectDelay: 60
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .ready {
                    readyStatus.signal()
                }
                if status == .failed("Relay key confirmation failed.") {
                    failedStatus.signal()
                }
            },
            onMessage: { _, _ in
                XCTFail("Encrypted relay must not process frames before key confirmation")
            }
        )

        let runtime = try parseStrictRuntimeHandshake(
            try XCTUnwrap(server.waitForHandshake()),
            relayID: "relay-confirmation-required"
        )
        let sessionKeys = try RelaySessionCrypto.deriveKeys(
            localRole: .client,
            localEphemeralKey: clientEphemeralKey,
            relayID: "relay-confirmation-required",
            routeNonce: relayNonce,
            relaySecret: relaySecret,
            clientSessionNonce: clientSessionNonce,
            runtimeSessionNonce: runtime.sessionNonce,
            clientEphemeralKey: clientEphemeralKey.publicKeyHex,
            runtimeEphemeralKey: runtime.ephemeralKey
        )

        server.write("AETHERLINK_RELAY registered crypto=2\n")
        server.write(
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=\(clientSessionNonce) " +
                "peer_ephemeral_key=\(clientEphemeralKey.publicKeyHex)\n"
        )
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 0.2), .timedOut)
        server.write(
            "AETHERLINK_RELAY confirm client binding=\(sessionKeys.bindingID) " +
                "proof=\(String(repeating: "0", count: 64))\n"
        )

        XCTAssertEqual(failedStatus.wait(timeout: .now() + 2), .success)
        XCTAssertFalse(statusRecorder.contains(.ready))
        XCTAssertTrue(server.waitForPeerClose())
    }

    func testStrictRelayPeerClientClosesImmediatelyOnFrameAuthenticationFailure() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let readyStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }
        let relayID = "relay-frame-auth-failure"
        let relaySecret = "frame-auth-secret"
        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: relayID,
                relaySecret: relaySecret,
                reconnectDelay: 60
            ),
            onStatusChange: { status in
                if status == .ready { readyStatus.signal() }
            },
            onMessage: { _, _ in XCTFail("Tampered frame must not reach the router") }
        )

        let keys = try completeStrictHandshake(
            server: server,
            relayID: relayID,
            relaySecret: relaySecret,
            relayNonce: nil,
            readyStatus: readyStatus
        )
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 2), .success)
        var cipher = RelayFrameCipher(sessionKeys: keys)
        var tampered = try cipher.encryptClientBody(Data("authenticated-frame".utf8))
        tampered[tampered.startIndex] ^= 0x01
        server.writeFrameBody(tampered)

        XCTAssertTrue(server.waitForPeerClose())
    }

    private func completeStrictHandshake(
        server: ControlledRelayServer,
        relayID: String,
        relaySecret: String,
        relayNonce: String?,
        readyStatus: DispatchSemaphore
    ) throws -> RelaySessionKeys {
        let runtime = try parseStrictRuntimeHandshake(
            try XCTUnwrap(server.waitForHandshake()),
            relayID: relayID
        )
        let clientSessionNonce = "00112233445566778899aabbccddeeff"
        let clientEphemeralKey = RelaySessionEphemeralKey()
        let keys = try RelaySessionCrypto.deriveKeys(
            localRole: .client,
            localEphemeralKey: clientEphemeralKey,
            relayID: relayID,
            routeNonce: relayNonce,
            relaySecret: relaySecret,
            clientSessionNonce: clientSessionNonce,
            runtimeSessionNonce: runtime.sessionNonce,
            clientEphemeralKey: clientEphemeralKey.publicKeyHex,
            runtimeEphemeralKey: runtime.ephemeralKey
        )
        server.write("AETHERLINK_RELAY registered crypto=2\n")
        server.write(
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=\(clientSessionNonce) " +
                "peer_ephemeral_key=\(clientEphemeralKey.publicKeyHex)\n"
        )
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 0.2), .timedOut)
        server.write(RelayKeyConfirmation.controlLine(role: .client, sessionKeys: keys))
        XCTAssertEqual(
            server.waitForControlLine(),
            RelayKeyConfirmation.controlLine(role: .runtime, sessionKeys: keys)
        )
        return keys
    }

    private func assertIdentityAuthorizationRejected(
        label: String,
        signer: TestRelayIdentityAuthorizationSigner? = nil,
        response: (RelayRuntimeRegistrationIdentityChallenge) throws -> String
    ) throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }
        let signer = try signer ?? TestRelayIdentityAuthorizationSigner()
        let relayID = "relay-rejected-\(UUID().uuidString)"
        let relayNonce = "rejected-nonce"
        let failedStatus = DispatchSemaphore(value: 0)
        let statusRecorder = RelayStatusRecorder()
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: relayID,
                relaySecret: "rejected-secret",
                relayNonce: relayNonce,
                reconnectDelay: 60,
                runtimeIdentity: signer.identity,
                identityAuthorizationSigner: signer
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .failed("Relay runtime registration authorization failed.") {
                    failedStatus.signal()
                }
            },
            onMessage: { _, _ in XCTFail("\(label) must close before matcher frames") }
        )

        let runtime = try parseIdentityBoundStrictRuntimeHandshake(
            try XCTUnwrap(server.waitForHandshake(), label),
            relayID: relayID,
            runtimeIdentity: signer.identity
        )
        let challenge = try makeRegistrationChallenge(
            relayID: relayID,
            relayNonce: relayNonce,
            runtimeIdentity: signer.identity,
            runtime: runtime
        )
        server.write(try response(challenge))

        XCTAssertEqual(failedStatus.wait(timeout: .now() + 2), .success, label)
        XCTAssertFalse(statusRecorder.contains(.waitingForPeer), label)
        XCTAssertFalse(statusRecorder.contains(.ready), label)
        XCTAssertTrue(server.waitForPeerClose(), label)
        if !signer.failsRegistrationSigning {
            XCTAssertEqual(signer.registrationSignatureCount, 0, label)
        }
    }

    private func makeRegistrationChallenge(
        relayID: String,
        relayNonce: String,
        runtimeIdentity: RelayRuntimeIdentity,
        runtime: (sessionNonce: String, ephemeralKey: String)
    ) throws -> RelayRuntimeRegistrationIdentityChallenge {
        let now = Int64(Date().timeIntervalSince1970 * 1_000)
        return try RelayRuntimeRegistrationIdentityChallenge(
            relayID: relayID,
            relayExpiresAtEpochMillis: now + 60_000,
            relayNonce: relayNonce,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            ticketGeneration: 1,
            sessionNonce: runtime.sessionNonce,
            ephemeralKey: runtime.ephemeralKey,
            challenge: String(repeating: "a", count: 64),
            challengeExpiresAtEpochMillis: now + 30_000
        )
    }

    private func registrationChallengeLine(
        _ challenge: RelayRuntimeRegistrationIdentityChallenge
    ) throws -> String {
        let data = try JSONEncoder().encode(challenge)
        return RelayRuntimeRegistrationIdentityChallenge.responsePrefix +
            String(decoding: data, as: UTF8.self) + "\n"
    }

    private func mutatingRegistrationChallenge(
        _ challenge: RelayRuntimeRegistrationIdentityChallenge,
        mutation: RegistrationChallengeMutation
    ) throws -> RelayRuntimeRegistrationIdentityChallenge {
        let alternateIdentity = try TestRelayIdentityAuthorizationSigner().identity
        let alternateEphemeralKey = RelaySessionEphemeralKey().publicKeyHex
        return try RelayRuntimeRegistrationIdentityChallenge(
            relayID: mutation == .relayID ? "wrong-relay-id" : challenge.relayID,
            relayExpiresAtEpochMillis: challenge.relayExpiresAtEpochMillis,
            relayNonce: mutation == .relayNonce ? "wrong-relay-nonce" : challenge.relayNonce,
            runtimeKeyFingerprint: mutation == .runtimeFingerprint
                ? alternateIdentity.fingerprint
                : challenge.runtimeKeyFingerprint,
            ticketGeneration: challenge.ticketGeneration,
            sessionNonce: mutation == .sessionNonce
                ? String(repeating: "f", count: 32)
                : challenge.sessionNonce,
            ephemeralKey: mutation == .ephemeralKey ? alternateEphemeralKey : challenge.ephemeralKey,
            challenge: challenge.challenge,
            challengeExpiresAtEpochMillis: challenge.challengeExpiresAtEpochMillis
        )
    }

    private func parseRegistrationProof(_ line: String) throws -> (challenge: String, signatureBase64: String) {
        XCTAssertTrue(line.hasSuffix("\n"))
        let parts = line.dropLast().split(separator: " ", omittingEmptySubsequences: false)
        XCTAssertEqual(parts.count, 5)
        guard parts.count == 5,
              parts[0] == "AETHERLINK_RELAY",
              parts[1] == "registration_proof",
              parts[2] == "crypto=2",
              parts[3].hasPrefix("challenge="),
              parts[4].hasPrefix("signature=")
        else { throw TestRelayServerError.invalidHandshake }
        let challenge = String(parts[3].dropFirst("challenge=".count))
        let signature = String(parts[4].dropFirst("signature=".count))
        XCTAssertEqual(challenge.count, 64)
        XCTAssertNotNil(Data(base64Encoded: signature))
        return (challenge, signature)
    }

    private static func startLoopbackConnection(
        port: UInt16
    ) -> (connection: NWConnection, stateRecorder: RelayPeerNWConnectionStateRecorder) {
        let connection = NWConnection(
            host: "127.0.0.1",
            port: NWEndpoint.Port(rawValue: port)!,
            using: .tcp
        )
        let stateRecorder = RelayPeerNWConnectionStateRecorder()
        connection.stateUpdateHandler = { state in
            stateRecorder.append(state)
        }
        connection.start(queue: DispatchQueue(label: "relay-peer-connection-test"))
        return (connection, stateRecorder)
    }

    private func parseIdentityBoundStrictRuntimeHandshake(
        _ line: String,
        relayID: String,
        runtimeIdentity: RelayRuntimeIdentity
    ) throws -> (sessionNonce: String, ephemeralKey: String) {
        XCTAssertTrue(line.hasSuffix("\n"))
        let parts = line.dropLast().split(separator: " ", omittingEmptySubsequences: false)
        XCTAssertEqual(parts.count, 7)
        guard parts.count == 7,
              parts[0] == "AETHERLINK_RELAY",
              parts[1] == "runtime",
              parts[2] == Substring(relayID),
              parts[3] == "crypto=2",
              parts[4].hasPrefix("session_nonce="),
              parts[5].hasPrefix("ephemeral_key="),
              parts[6] == "runtime_key_fingerprint=\(runtimeIdentity.fingerprint)"
        else { throw TestRelayServerError.invalidHandshake }
        let sessionNonce = String(parts[4].dropFirst("session_nonce=".count))
        let ephemeralKey = String(parts[5].dropFirst("ephemeral_key=".count))
        XCTAssertTrue(RelaySessionNonce.isCanonical(sessionNonce))
        XCTAssertTrue(RelaySessionCrypto.isCanonicalEphemeralKey(ephemeralKey))
        return (sessionNonce, ephemeralKey)
    }

    private func parseStrictRuntimeHandshake(
        _ line: String,
        relayID: String
    ) throws -> (sessionNonce: String, ephemeralKey: String) {
        XCTAssertTrue(line.hasSuffix("\n"))
        let parts = line.dropLast().split(separator: " ", omittingEmptySubsequences: false)
        XCTAssertEqual(parts.count, 6)
        guard parts.count == 6 else { throw TestRelayServerError.invalidHandshake }
        XCTAssertEqual(parts[0], "AETHERLINK_RELAY")
        XCTAssertEqual(parts[1], "runtime")
        XCTAssertEqual(parts[2], Substring(relayID))
        XCTAssertEqual(parts[3], "crypto=2")
        let noncePrefix = "session_nonce="
        let keyPrefix = "ephemeral_key="
        guard parts[4].hasPrefix(noncePrefix), parts[5].hasPrefix(keyPrefix) else {
            throw TestRelayServerError.invalidHandshake
        }
        let sessionNonce = String(parts[4].dropFirst(noncePrefix.count))
        let ephemeralKey = String(parts[5].dropFirst(keyPrefix.count))
        XCTAssertTrue(RelaySessionNonce.isCanonical(sessionNonce))
        XCTAssertTrue(RelaySessionCrypto.isCanonicalEphemeralKey(ephemeralKey))
        return (sessionNonce, ephemeralKey)
    }
}

private enum RegistrationChallengeMutation {
    case relayID
    case relayNonce
    case runtimeFingerprint
    case sessionNonce
    case ephemeralKey
}

private final class TestRelayIdentityAuthorizationSigner: RelayIdentityAuthorizationSigning, @unchecked Sendable {
    let identity: RelayRuntimeIdentity
    let failsRegistrationSigning: Bool

    private let privateKey: P256.Signing.PrivateKey
    private let lock = NSLock()
    private var signatureCount = 0

    var registrationSignatureCount: Int {
        lock.withLock { signatureCount }
    }

    init(failsRegistrationSigning: Bool = false) throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKeyData = privateKey.publicKey.derRepresentation
        let fingerprint = SHA256.hash(data: publicKeyData)
            .map { String(format: "%02x", $0) }
            .joined()
        self.privateKey = privateKey
        self.identity = try RelayRuntimeIdentity(
            publicKeyBase64: publicKeyData.base64EncodedString(),
            fingerprint: fingerprint
        )
        self.failsRegistrationSigning = failsRegistrationSigning
    }

    func relayRuntimeIdentity() throws -> RelayRuntimeIdentity {
        identity
    }

    func signRelayAllocationChallenge(
        _ challenge: RelayAllocationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof {
        throw TestRelayIdentityAuthorizationSignerError.unsupportedAllocation
    }

    func signRelayRuntimeRegistrationChallenge(
        _ challenge: RelayRuntimeRegistrationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof {
        lock.withLock {
            signatureCount += 1
        }
        if failsRegistrationSigning {
            throw TestRelayIdentityAuthorizationSignerError.registrationFailure
        }
        let signature = try privateKey.signature(for: SHA256.hash(data: challenge.signedMessageData()))
        return try RelayIdentityAuthorizationProof(
            runtimeIdentity: identity,
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
    }
}

private enum TestRelayIdentityAuthorizationSignerError: Error {
    case unsupportedAllocation
    case registrationFailure
}

private final class ControlledRelayServer {
    let port: UInt16

    private let listenSocket: Int32
    private let handshakeSemaphore = DispatchSemaphore(value: 0)
    private let lock = NSLock()
    private var acceptedSocket: Int32 = -1
    private var handshakes = [[UInt8]]()
    private var stopped = false

    init() throws {
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else {
            throw TestRelayServerError.socket(String(cString: strerror(errno)))
        }
        var yes: Int32 = 1
        setsockopt(socket, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = UInt16(0).bigEndian
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let bound = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                Darwin.bind(socket, sockaddrPointer, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard bound == 0 else {
            Darwin.close(socket)
            throw TestRelayServerError.socket(String(cString: strerror(errno)))
        }
        guard Darwin.listen(socket, 1) == 0 else {
            Darwin.close(socket)
            throw TestRelayServerError.socket(String(cString: strerror(errno)))
        }

        var boundAddress = sockaddr_in()
        var boundAddressLength = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &boundAddress) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                Darwin.getsockname(socket, sockaddrPointer, &boundAddressLength)
            }
        }
        guard named == 0 else {
            Darwin.close(socket)
            throw TestRelayServerError.socket(String(cString: strerror(errno)))
        }

        self.listenSocket = socket
        self.port = UInt16(bigEndian: boundAddress.sin_port)

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.acceptConnections(socket: socket)
        }
    }

    func waitForHandshake(index: Int = 0, timeout: DispatchTime = .now() + 2) -> String? {
        while lock.withLock({ handshakes.count <= index }) {
            guard handshakeSemaphore.wait(timeout: timeout) == .success else {
                return nil
            }
        }
        return lock.withLock {
            String(bytes: handshakes[index], encoding: .utf8)
        }
    }

    func waitForFrameBody() -> Data? {
        let fd = lock.withLock { acceptedSocket }
        guard fd >= 0,
              let lengthData = readExactly(byteCount: 4, socket: fd)
        else {
            return nil
        }
        let bodyLength = lengthData.reduce(UInt32(0)) { partial, byte in
            (partial << 8) | UInt32(byte)
        }
        guard bodyLength > 0,
              bodyLength <= UInt32(ProtocolCodec.maxFrameBytes)
        else {
            return nil
        }
        return readExactly(byteCount: Int(bodyLength), socket: fd)
    }

    func waitForControlLine() -> String? {
        let fd = lock.withLock { acceptedSocket }
        guard fd >= 0 else { return nil }
        var bytes = [UInt8]()
        while bytes.count < 256 {
            var byte: UInt8 = 0
            guard Darwin.recv(fd, &byte, 1, 0) == 1 else { return nil }
            bytes.append(byte)
            if byte == UInt8(ascii: "\n") {
                return String(bytes: bytes, encoding: .utf8)
            }
        }
        return nil
    }

    func write(_ line: String) {
        let fd = lock.withLock { acceptedSocket }
        guard fd >= 0 else { return }
        let bytes = Array(line.utf8)
        _ = bytes.withUnsafeBytes { rawBuffer in
            Darwin.send(fd, rawBuffer.baseAddress, rawBuffer.count, 0)
        }
    }

    func writeFrameBody(_ body: Data) {
        let fd = lock.withLock { acceptedSocket }
        guard fd >= 0 else { return }
        var length = UInt32(body.count).bigEndian
        var frame = Data(bytes: &length, count: MemoryLayout<UInt32>.size)
        frame.append(body)
        frame.withUnsafeBytes { rawBuffer in
            _ = Darwin.send(fd, rawBuffer.baseAddress, rawBuffer.count, 0)
        }
    }

    func stop() {
        let sockets = lock.withLock {
            stopped = true
            let accepted = acceptedSocket
            acceptedSocket = -1
            return (listen: listenSocket, accepted: accepted)
        }
        if sockets.accepted >= 0 {
            Darwin.close(sockets.accepted)
        }
        Darwin.close(sockets.listen)
    }

    func closeAcceptedSocket() {
        let accepted = lock.withLock {
            let accepted = acceptedSocket
            acceptedSocket = -1
            return accepted
        }
        if accepted >= 0 {
            Darwin.close(accepted)
        }
    }

    func waitForPeerClose() -> Bool {
        let fd = lock.withLock { acceptedSocket }
        guard fd >= 0 else { return true }
        var byte: UInt8 = 0
        return Darwin.recv(fd, &byte, 1, 0) <= 0
    }

    private func acceptConnections(socket: Int32) {
        while true {
            let fd = Darwin.accept(socket, nil, nil)
            guard fd >= 0 else { return }
            let shouldClose = lock.withLock {
                if stopped {
                    return true
                }
                acceptedSocket = fd
                return false
            }
            if shouldClose {
                Darwin.close(fd)
                return
            }
            var timeout = timeval(tv_sec: 2, tv_usec: 0)
            setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))
            receiveHandshake(socket: fd)
        }
    }

    private func receiveHandshake(socket: Int32) {
        var handshake = [UInt8]()
        while true {
            var byte: UInt8 = 0
            let count = Darwin.recv(socket, &byte, 1, 0)
            guard count == 1 else { return }
            handshake.append(byte)
            if byte == UInt8(ascii: "\n") {
                lock.withLock {
                    handshakes.append(handshake)
                }
                handshakeSemaphore.signal()
                return
            }
        }
    }

    private func readExactly(byteCount: Int, socket: Int32) -> Data? {
        var buffer = [UInt8](repeating: 0, count: byteCount)
        var offset = 0
        while offset < byteCount {
            let received = buffer.withUnsafeMutableBytes { rawBuffer -> Int in
                guard let baseAddress = rawBuffer.baseAddress else { return -1 }
                return Darwin.recv(socket, baseAddress.advanced(by: offset), byteCount - offset, 0)
            }
            guard received > 0 else {
                return nil
            }
            offset += received
        }
        return Data(buffer)
    }
}

private final class RelayStatusRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var statuses: [RelayPeerStatus] = []

    func append(_ status: RelayPeerStatus) {
        lock.withLock {
            statuses.append(status)
        }
    }

    func contains(_ status: RelayPeerStatus) -> Bool {
        lock.withLock {
            statuses.contains(status)
        }
    }

    func contains(_ predicate: (RelayPeerStatus) -> Bool) -> Bool {
        lock.withLock {
            statuses.contains(where: predicate)
        }
    }
}

private final class RelayDisconnectRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private let semaphore = DispatchSemaphore(value: 0)
    private var ids: [UUID] = []

    var count: Int {
        lock.withLock { ids.count }
    }

    func append(_ id: UUID) {
        lock.withLock {
            ids.append(id)
        }
        semaphore.signal()
    }

    func waitForCount(_ expectedCount: Int, timeout: DispatchTime = .now() + 2) -> Int {
        while count < expectedCount {
            if semaphore.wait(timeout: timeout) != .success {
                break
            }
        }
        return count
    }
}

private final class TransportSecurityContextRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var context: TransportSecurityContext?

    var value: TransportSecurityContext? {
        lock.withLock { context }
    }

    func append(_ context: TransportSecurityContext?) {
        lock.withLock {
            self.context = context
        }
    }
}

private final class RelayPeerSendCompletionRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private let semaphore = DispatchSemaphore(value: 0)
    private var values = [Bool]()

    func append(_ value: Bool) {
        lock.withLock {
            values.append(value)
        }
        semaphore.signal()
    }

    func waitForValue(timeout: DispatchTime = .now() + 2) -> Bool? {
        guard semaphore.wait(timeout: timeout) == .success else { return nil }
        return lock.withLock { values.first }
    }

    func waitForAdditionalValue(timeout: DispatchTime = .now() + 0.05) -> Bool {
        semaphore.wait(timeout: timeout) == .success
    }
}

private final class RelayPeerNWConnectionStateRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private let readyOrFailed = DispatchSemaphore(value: 0)
    private let cancelled = DispatchSemaphore(value: 0)
    private var becameReady = false

    func append(_ state: NWConnection.State) {
        switch state {
        case .ready:
            lock.withLock {
                becameReady = true
            }
            readyOrFailed.signal()
        case .failed:
            readyOrFailed.signal()
        case .cancelled:
            cancelled.signal()
        default:
            break
        }
    }

    func waitUntilReady(timeout: DispatchTime = .now() + 2) -> Bool {
        guard readyOrFailed.wait(timeout: timeout) == .success else { return false }
        return lock.withLock { becameReady }
    }

    func waitUntilCancelled(timeout: DispatchTime = .now() + 2) -> Bool {
        cancelled.wait(timeout: timeout) == .success
    }
}

private enum TestRelayServerError: Error {
    case socket(String)
    case invalidHandshake
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
