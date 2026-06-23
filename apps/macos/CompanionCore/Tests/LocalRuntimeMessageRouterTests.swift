import enum BridgeProtocol.JSONValue
import enum BridgeProtocol.MessageType
import struct BridgeProtocol.ProtocolEnvelope
import CompanionCore
import CryptoKit
import OllamaBackend
import Pairing
import Transport
import TrustedDevices
import XCTest

final class LocalRuntimeMessageRouterTests: XCTestCase {
    func testRuntimeHealthResponseUsesRuntimeHealthType() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(status: BackendStatus.available))

        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-1"), sink: sink)

        let messages = try await sink.waitForMessages(count: 1)
        XCTAssertEqual(messages.first?.type, MessageType.runtimeHealth)
        XCTAssertEqual(messages.first?.requestID, "health-1")
        XCTAssertEqual(messages.first?.payload["status"], .string("ok"))
        guard case .object(let ollama)? = messages.first?.payload["ollama"] else {
            XCTFail("Expected ollama object")
            return
        }
        XCTAssertFalse(String(describing: ollama).contains("11434"))
        XCTAssertFalse(String(describing: ollama).contains("127.0.0.1"))
        XCTAssertFalse(String(describing: ollama).contains("localhost"))
    }

    func testRuntimeHealthUnavailableReturnsProtocolErrorWithoutBackendURL() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(status: .unavailable(BackendError(
            provider: .ollama,
            code: "backend_unavailable",
            message: "Ollama is not reachable from the Mac runtime.",
            retryable: true
        ))))

        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-2"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        guard case .object(let ollama)? = message?.payload["ollama"] else {
            XCTFail("Expected ollama object")
            return
        }
        XCTAssertEqual(ollama["available"], .bool(false))
        XCTAssertEqual(ollama["code"], .string("backend_unavailable"))
        XCTAssertEqual(ollama["retryable"], .bool(true))
        XCTAssertFalse(String(describing: ollama).contains("11434"))
        XCTAssertFalse(String(describing: ollama).contains("127.0.0.1"))
    }

    func testRuntimeHealthIncludesAggregateProviderStatuses() async throws {
        let sink = RecordingSink()
        let backend = AggregatingLlmBackend([
            MockBackend(provider: .ollama, status: .available),
            MockBackend(provider: .lmStudio, status: .unavailable(BackendError(
                provider: .lmStudio,
                code: "backend_unavailable",
                message: "LM Studio is not reachable from the Mac runtime.",
                retryable: true
            )))
        ])
        let router = makeRouter(backend: backend)

        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-aggregate"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.payload["status"], .string("ok"))
        guard case .object(let ollama)? = message?.payload["ollama"],
              case .object(let lmStudio)? = message?.payload["lm_studio"] else {
            XCTFail("Expected provider health objects")
            return
        }
        XCTAssertEqual(ollama["available"], .bool(true))
        XCTAssertEqual(lmStudio["available"], .bool(false))
        XCTAssertEqual(lmStudio["code"], .string("backend_unavailable"))
        XCTAssertFalse(String(describing: message?.payload).contains("1234"))
    }

    func testModelsListReturnsModelsWithoutExposingOllamaURL() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [
                ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", sizeBytes: 4),
                ModelInfo(
                    id: "deepseek-v4-pro:cloud",
                    name: "deepseek-v4-pro:cloud",
                    sizeBytes: 344,
                    installed: true,
                    source: .cloud,
                    remoteModel: "deepseek-v4-pro",
                    remoteHost: "https://ollama.com:443"
                )
            ]
        ))

        router.handle(ProtocolEnvelope(type: MessageType.modelsList, requestID: "models-1"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.modelsList)
        guard case .array(let models)? = message?.payload["models"] else {
            XCTFail("Expected models array")
            return
        }
        XCTAssertEqual(models.count, 2)
        guard case .object(let model)? = models.first else {
            XCTFail("Expected model object")
            return
        }
        XCTAssertEqual(model["installed"], .bool(true))
        XCTAssertEqual(model["running"], .bool(false))
        XCTAssertEqual(model["source"], .string("local"))
        XCTAssertEqual(model["backend"], .string("ollama"))
        XCTAssertEqual(model["provider"], .string("ollama"))
        XCTAssertEqual(model["provider_model_id"], .string("llama3.1:8b"))
        XCTAssertEqual(model["qualified_id"], .string("ollama:llama3.1:8b"))
        XCTAssertFalse(String(describing: message?.payload).contains("11434"))

        guard case .object(let cloudModel)? = models.last else {
            XCTFail("Expected cloud model object")
            return
        }
        XCTAssertEqual(cloudModel["id"], .string("deepseek-v4-pro:cloud"))
        XCTAssertEqual(cloudModel["qualified_id"], .string("ollama:deepseek-v4-pro:cloud"))
        XCTAssertEqual(cloudModel["installed"], .bool(true))
        XCTAssertEqual(cloudModel["source"], .string("cloud"))
        XCTAssertEqual(cloudModel["remote_model"], .string("deepseek-v4-pro"))
        XCTAssertEqual(cloudModel["remote_host"], .string("https://ollama.com:443"))
    }

    func testModelsListBackendErrorUsesProtocolErrorCodeWithoutBackendURL() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(modelListError: OllamaBackendError.unreachable(
            endpoint: "GET /api/tags",
            baseURL: "http://127.0.0.1:11434",
            reason: "Connection refused"
        )))

        router.handle(ProtocolEnvelope(type: MessageType.modelsList, requestID: "models-error"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "models-error")
        XCTAssertEqual(message?.payload["code"], .string("backend_unavailable"))
        XCTAssertEqual(message?.payload["retryable"], .bool(true))
        XCTAssertFalse(String(describing: message?.payload).contains("11434"))
        XCTAssertFalse(String(describing: message?.payload).contains("127.0.0.1"))
    }

    func testModelsPullReturnsSuccessWithoutExposingOllamaURL() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            pullResult: ModelPullResult(model: "deepseek-v4-pro:cloud", status: "success", installed: true)
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.modelsPull,
            requestID: "pull-1",
            payload: ["model": .string("deepseek-v4-pro:cloud")]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.modelsPull)
        XCTAssertEqual(message?.requestID, "pull-1")
        XCTAssertEqual(message?.payload["model"], .string("deepseek-v4-pro:cloud"))
        XCTAssertEqual(message?.payload["status"], .string("success"))
        XCTAssertEqual(message?.payload["installed"], .bool(true))
        XCTAssertFalse(String(describing: message?.payload).contains("11434"))
        XCTAssertFalse(String(describing: message?.payload).contains("127.0.0.1"))
    }

    func testModelsPullBackendErrorUsesProtocolErrorCodeWithoutBackendURL() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(pullError: OllamaBackendError.unreachable(
            endpoint: "POST /api/pull",
            baseURL: "http://127.0.0.1:11434",
            reason: "Connection refused"
        )))
        let envelope = ProtocolEnvelope(
            type: MessageType.modelsPull,
            requestID: "pull-error",
            payload: ["model": .string("gemma3")]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "pull-error")
        XCTAssertEqual(message?.payload["code"], .string("backend_unavailable"))
        XCTAssertEqual(message?.payload["retryable"], .bool(true))
        XCTAssertFalse(String(describing: message?.payload).contains("11434"))
        XCTAssertFalse(String(describing: message?.payload).contains("127.0.0.1"))
    }

    func testChatSendStreamsDeltaAndDone() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                ChatStreamEvent.delta("hello"),
                ChatStreamEvent.done(inputTokens: 1, outputTokens: 2)
            ]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-1",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("hi")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let messages = try await sink.waitForMessages(count: 2)
        XCTAssertEqual(messages.map(\.type), [MessageType.chatDelta, MessageType.chatDone])
        XCTAssertEqual(messages.first?.payload["delta"], .string("hello"))
    }

    func testChatSendInstalledCloudModelIsSelectable() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [
                ModelInfo(
                    id: "deepseek-v4-pro:cloud",
                    name: "deepseek-v4-pro:cloud",
                    installed: true,
                    source: .cloud,
                    remoteModel: "deepseek-v4-pro",
                    remoteHost: "https://ollama.com:443"
                )
            ],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-cloud",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("deepseek-v4-pro:cloud"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("hi")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        XCTAssertEqual(message?.requestID, "chat-cloud")
        XCTAssertEqual(message?.payload["finish_reason"], .string("stop"))
    }

    func testChatSendRoutesQualifiedLMStudioModelThroughAggregateBackend() async throws {
        let sink = RecordingSink()
        let routedModel = LockedBox<String?>(nil)
        let backend = AggregatingLlmBackend([
            MockBackend(
                provider: .ollama,
                models: [ModelInfo(id: "qwen-local", name: "Ollama Qwen", provider: .ollama, installed: true)]
            ),
            MockBackend(
                provider: .lmStudio,
                models: [ModelInfo(id: "qwen-local", name: "LM Studio Qwen", provider: .lmStudio, installed: true)],
                chatEvents: [.done(inputTokens: 2, outputTokens: 3)],
                onChatRequest: { request in
                    routedModel.value = request.model
                }
            )
        ])
        let router = makeRouter(backend: backend)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-lm-studio",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("lm_studio:qwen-local"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("hi")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        XCTAssertEqual(message?.payload["finish_reason"], .string("stop"))
        XCTAssertEqual(routedModel.value, "qwen-local")
    }

    func testChatSendNonInstalledModelReturnsModelNotInstalled() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "example-uninstalled", name: "example-uninstalled", installed: false, source: .local)]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-missing-model",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("example-uninstalled"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("hi")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "chat-missing-model")
        XCTAssertEqual(message?.payload["code"], .string("model_not_installed"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertFalse(String(describing: message?.payload).contains("11434"))
    }

    func testChatSendInvalidPayloadReturnsInvalidPayloadError() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend())
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-invalid",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b")
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "chat-invalid")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testChatCancelReturnsCancelAcknowledgement() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(cancelResult: GenerationCancellationResult.cancelled(generationID: "chat-1")))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatCancel,
            requestID: "cancel-1",
            payload: ["target_request_id": .string("chat-1")]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatCancel)
        XCTAssertEqual(message?.payload["cancelled"], .bool(true))
    }

    func testChatCancelUnknownGenerationReturnsProtocolError() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(cancelResult: GenerationCancellationResult.notFound(generationID: "chat-1")))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatCancel,
            requestID: "cancel-missing",
            payload: ["target_request_id": .string("chat-1")]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "cancel-missing")
        XCTAssertEqual(message?.payload["code"], .string("generation_not_found"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testUnknownMessageTypeReturnsProtocolError() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend())

        router.handle(ProtocolEnvelope(type: "memory.search", requestID: "future-1"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "future-1")
        XCTAssertEqual(message?.payload["code"], .string("unknown_message_type"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testPairingRequestStoresTrustedDeviceAndReturnsAccepted() async throws {
        let sink = RecordingSink()
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "mac-1",
            fingerprint: "fp-1",
            host: "192.168.1.10",
            port: 43170
        )
        let storeURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("trusted-devices.json")
        let store = TrustedDeviceStore(fileURL: storeURL)
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(),
            pairingCoordinator: coordinator,
            trustedDeviceStore: store
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.pairingRequest,
            requestID: "pair-1",
            payload: [
                "pairing_nonce": .string(session.nonce),
                "pairing_code": .string(session.code),
                "device_id": .string("android-1"),
                "device_name": .string("Android Phone"),
                "public_key": .string("public-key")
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.pairingResult)
        XCTAssertEqual(message?.requestID, "pair-1")
        XCTAssertEqual(message?.payload["accepted"], .bool(true))
        XCTAssertEqual(message?.payload["mac_device_id"], .string("mac-1"))
        XCTAssertEqual(message?.payload["trusted_device_id"], .string("android-1"))

        let devices = try await store.load()
        XCTAssertEqual(devices.map(\.id), ["android-1"])
        XCTAssertEqual(devices.first?.name, "Android Phone")

        router.handle(pairingEnvelope(
            requestID: "pair-reuse",
            session: session,
            deviceID: "android-2",
            deviceName: "Second Android"
        ), sink: sink)

        let reuseMessage = try await sink.waitForMessages(count: 2).last
        XCTAssertEqual(reuseMessage?.type, MessageType.pairingResult)
        XCTAssertEqual(reuseMessage?.requestID, "pair-reuse")
        XCTAssertEqual(reuseMessage?.payload["accepted"], .bool(false))
        XCTAssertEqual(reuseMessage?.payload["code"], .string(PairingRejectionReason.noActiveSession.rawValue))

        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-after-pairing"), sink: sink)

        let authenticatedMessages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(authenticatedMessages.last?.type, MessageType.runtimeHealth)
        XCTAssertEqual(authenticatedMessages.last?.payload["status"], .string("ok"))
    }

    func testRepeatedInvalidPairingAttemptsInvalidateActiveSession() async throws {
        let sink = RecordingSink()
        let coordinator = PairingCoordinator(maxFailedAttempts: 2)
        let session = coordinator.beginPairing(
            macDeviceID: "mac-1",
            fingerprint: "fp-1",
            host: "192.168.1.10",
            port: 43170
        )
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(),
            pairingCoordinator: coordinator,
            trustedDeviceStore: store
        )

        router.handle(pairingEnvelope(
            requestID: "pair-bad-1",
            session: session,
            pairingCode: "000000"
        ), sink: sink)

        let firstRejection = try await sink.waitForMessages(count: 1).last
        XCTAssertEqual(firstRejection?.type, MessageType.pairingResult)
        XCTAssertEqual(firstRejection?.payload["accepted"], .bool(false))
        XCTAssertEqual(firstRejection?.payload["code"], .string(PairingRejectionReason.invalidCredentials.rawValue))
        XCTAssertEqual(firstRejection?.payload["retryable"], .bool(true))
        XCTAssertEqual(firstRejection?.payload["failed_attempts"], .number(1))
        XCTAssertEqual(firstRejection?.payload["remaining_attempts"], .number(1))

        router.handle(pairingEnvelope(
            requestID: "pair-bad-2",
            session: session,
            pairingNonce: "wrong-nonce"
        ), sink: sink)

        let lockout = try await sink.waitForMessages(count: 2).last
        XCTAssertEqual(lockout?.type, MessageType.pairingResult)
        XCTAssertEqual(lockout?.payload["accepted"], .bool(false))
        XCTAssertEqual(lockout?.payload["code"], .string(PairingRejectionReason.attemptsExceeded.rawValue))
        XCTAssertEqual(lockout?.payload["retryable"], .bool(false))
        XCTAssertEqual(lockout?.payload["failed_attempts"], .number(2))
        XCTAssertEqual(lockout?.payload["remaining_attempts"], .number(0))

        router.handle(pairingEnvelope(
            requestID: "pair-after-lockout",
            session: session
        ), sink: sink)

        let validAfterLockout = try await sink.waitForMessages(count: 3).last
        XCTAssertEqual(validAfterLockout?.type, MessageType.pairingResult)
        XCTAssertEqual(validAfterLockout?.payload["accepted"], .bool(false))
        XCTAssertEqual(validAfterLockout?.payload["code"], .string(PairingRejectionReason.noActiveSession.rawValue))
        let trustedDevices = try await store.load()
        XCTAssertEqual(trustedDevices, [])
    }

    func testExpiredAndNoActivePairingRequestsReturnStructuredRejections() async throws {
        let sink = RecordingSink()
        let coordinator = PairingCoordinator()
        let expiredSession = coordinator.beginPairing(
            validFor: -1,
            macDeviceID: "mac-1",
            fingerprint: "fp-1",
            host: "192.168.1.10",
            port: 43170
        )
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(),
            pairingCoordinator: coordinator,
            trustedDeviceStore: TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        )

        router.handle(pairingEnvelope(
            requestID: "pair-expired",
            session: expiredSession
        ), sink: sink)

        let expired = try await sink.waitForMessages(count: 1).last
        XCTAssertEqual(expired?.type, MessageType.pairingResult)
        XCTAssertEqual(expired?.payload["accepted"], .bool(false))
        XCTAssertEqual(expired?.payload["code"], .string(PairingRejectionReason.expired.rawValue))
        XCTAssertEqual(expired?.payload["retryable"], .bool(false))

        router.handle(pairingEnvelope(
            requestID: "pair-no-active",
            session: expiredSession
        ), sink: sink)

        let noActive = try await sink.waitForMessages(count: 2).last
        XCTAssertEqual(noActive?.type, MessageType.pairingResult)
        XCTAssertEqual(noActive?.payload["accepted"], .bool(false))
        XCTAssertEqual(noActive?.payload["code"], .string(PairingRejectionReason.noActiveSession.rawValue))
        XCTAssertEqual(noActive?.payload["retryable"], .bool(false))
    }

    func testRuntimeCommandRequiresAuthenticatedConnectionByDefault() async throws {
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(backend: MockBackend(status: .available))

        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-unauthenticated"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "health-unauthenticated")
        XCTAssertEqual(message?.payload["code"], .string("authentication_required"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testModelsPullRequiresAuthenticatedConnectionByDefault() async throws {
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(backend: MockBackend(status: .available))
        let envelope = ProtocolEnvelope(
            type: MessageType.modelsPull,
            requestID: "pull-unauthenticated",
            payload: ["model": .string("gemma3")]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "pull-unauthenticated")
        XCTAssertEqual(message?.payload["code"], .string("authentication_required"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }


    func testTrustedHelloAndAuthResponseAuthenticatesConnection() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        let storeURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("trusted-devices.json")
        let store = TrustedDeviceStore(fileURL: storeURL)
        try await store.trust(TrustedDevice(
            id: "android-trusted",
            name: "Trusted Android",
            publicKeyBase64: publicKeyBase64
        ))
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-1",
            payload: ["device_id": .string("android-trusted")]
        ), sink: sink)

        let challenge = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(challenge?.type, MessageType.authChallenge)
        XCTAssertEqual(challenge?.requestID, "hello-1")
        XCTAssertEqual(challenge?.payload["device_id"], .string("android-trusted"))
        guard case .string(let nonce)? = challenge?.payload["nonce"] else {
            XCTFail("Expected nonce in auth challenge")
            return
        }

        let nonceData = try XCTUnwrap(nonce.data(using: .utf8))
        let digest = SHA256.hash(data: nonceData)
        let signature = try privateKey.signature(for: digest).derRepresentation.base64EncodedString()
        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-1",
            payload: [
                "device_id": .string("android-trusted"),
                "nonce": .string(nonce),
                "signature": .string(signature)
            ]
        ), sink: sink)

        let authMessages = try await sink.waitForMessages(count: 2)
        XCTAssertEqual(authMessages.last?.type, MessageType.authResponse)
        XCTAssertEqual(authMessages.last?.payload["accepted"], .bool(true))

        router.handle(ProtocolEnvelope(type: MessageType.modelsList, requestID: "models-after-auth"), sink: sink)

        let runtimeMessages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(runtimeMessages.last?.type, MessageType.modelsList)
    }

    func testUntrustedHelloReturnsPairingRequired() async throws {
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(backend: MockBackend())

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-untrusted",
            payload: ["device_id": .string("unknown-device")]
        ), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "hello-untrusted")
        XCTAssertEqual(message?.payload["code"], .string("pairing_required"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    @MainActor
    func testCompanionAppModelStartsReplaceableTransportAndStopsIt() async throws {
        let transport = FakeRuntimeTransport()
        let advertiser = FakeRuntimeAdvertiser()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: transport,
            advertiser: advertiser
        )

        model.start(port: 43210)

        XCTAssertEqual(transport.startedPort, 43210)
        XCTAssertEqual(advertiser.startedPort, 43210)
        XCTAssertTrue(model.transportStatus.contains("43210"))

        let sink = RecordingSink()
        let handler = try XCTUnwrap(transport.onMessage)
        handler(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "app-health"), sink)

        let messages = try await sink.waitForMessages(count: 1)
        XCTAssertEqual(messages.first?.type, MessageType.error)
        XCTAssertEqual(messages.first?.requestID, "app-health")
        XCTAssertEqual(messages.first?.payload["code"], .string("authentication_required"))

        model.stop()

        XCTAssertTrue(transport.didStop)
        XCTAssertTrue(advertiser.didStop)
        XCTAssertEqual(model.transportStatus, "Stopped")
    }
}

private func makeRouter(
    backend: any LlmBackend,
    requiresAuthentication: Bool = false,
    trustedDeviceStore: TrustedDeviceStore = TrustedDeviceStore(
        fileURL: FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("trusted-devices.json")
    )
) -> LocalRuntimeMessageRouter {
    LocalRuntimeMessageRouter(
        backend: backend,
        requiresAuthentication: requiresAuthentication,
        trustedDeviceStore: trustedDeviceStore
    )
}

private func trustedDeviceStoreURL() -> URL {
    FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString)
        .appendingPathComponent("trusted-devices.json")
}

private func pairingEnvelope(
    requestID: String,
    session: PairingSession,
    pairingNonce: String? = nil,
    pairingCode: String? = nil,
    deviceID: String = "android-1",
    deviceName: String = "Android Phone",
    publicKey: String = "public-key"
) -> ProtocolEnvelope {
    ProtocolEnvelope(
        type: MessageType.pairingRequest,
        requestID: requestID,
        payload: [
            "pairing_nonce": .string(pairingNonce ?? session.nonce),
            "pairing_code": .string(pairingCode ?? session.code),
            "device_id": .string(deviceID),
            "device_name": .string(deviceName),
            "public_key": .string(publicKey)
        ]
    )
}

private final class MockBackend: LlmBackend, @unchecked Sendable {
    let provider: ModelProvider
    private let status: BackendStatus
    private let models: [ModelInfo]
    private let modelListError: Error?
    private let pullResult: ModelPullResult
    private let pullError: Error?
    private let chatEvents: [ChatStreamEvent]
    private let cancelResult: GenerationCancellationResult
    private let onChatRequest: ((ChatRequest) -> Void)?

    init(
        provider: ModelProvider = .ollama,
        status: BackendStatus = .available,
        models: [ModelInfo] = [],
        modelListError: Error? = nil,
        pullResult: ModelPullResult = ModelPullResult(model: "mock", status: "success", installed: true),
        pullError: Error? = nil,
        chatEvents: [ChatStreamEvent] = [],
        cancelResult: GenerationCancellationResult = .notFound(generationID: "missing"),
        onChatRequest: ((ChatRequest) -> Void)? = nil
    ) {
        self.provider = provider
        self.status = status
        self.models = models
        self.modelListError = modelListError
        self.pullResult = pullResult
        self.pullError = pullError
        self.chatEvents = chatEvents
        self.cancelResult = cancelResult
        self.onChatRequest = onChatRequest
    }

    func healthCheck() async -> BackendStatus {
        status
    }

    func listModels() async throws -> [ModelInfo] {
        if let modelListError {
            throw modelListError
        }
        return models
    }

    func pullModel(name: String) async throws -> ModelPullResult {
        if let pullError {
            throw pullError
        }
        return ModelPullResult(model: name, status: pullResult.status, installed: pullResult.installed)
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            onChatRequest?(request)
            chatEvents.forEach { continuation.yield($0) }
            continuation.finish()
        }
    }

    func cancel(generationID: String) -> GenerationCancellationResult {
        cancelResult
    }
}

private final class LockedBox<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var storage: Value

    init(_ value: Value) {
        storage = value
    }

    var value: Value {
        get {
            lock.withLock { storage }
        }
        set {
            lock.withLock { storage = newValue }
        }
    }
}

private final class RecordingSink: RuntimeMessageSink, @unchecked Sendable {
    let connectionID = UUID()
    private let lock = NSLock()
    private var messages: [ProtocolEnvelope] = []

    func send(_ envelope: ProtocolEnvelope) {
        lock.withLock {
            messages.append(envelope)
        }
    }

    func close() {}

    func waitForMessages(count: Int, timeout: TimeInterval = 1.0) async throws -> [ProtocolEnvelope] {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            let snapshot = lock.withLock { messages }
            if snapshot.count >= count {
                return snapshot
            }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        return lock.withLock { messages }
    }
}

private final class FakeRuntimeTransport: RuntimeTransport {
    private(set) var status = PeerServerStatus.stopped
    private(set) var startedPort: UInt16?
    private(set) var didStop = false
    private(set) var onMessage: LocalPeerMessageHandler?

    func start(port: UInt16, onMessage: @escaping LocalPeerMessageHandler) {
        startedPort = port
        self.onMessage = onMessage
        didStop = false
        status = .listening(port: port)
    }

    func stop() {
        didStop = true
        onMessage = nil
        status = .stopped
    }
}

private final class FakeRuntimeAdvertiser: RuntimeAdvertiser {
    private(set) var startedPort: Int32?
    private(set) var didStop = false

    func start(port: Int32) {
        startedPort = port
        didStop = false
    }

    func stop() {
        didStop = true
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
