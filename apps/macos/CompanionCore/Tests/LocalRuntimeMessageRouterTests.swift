import enum BridgeProtocol.JSONValue
import enum BridgeProtocol.MessageType
import struct BridgeProtocol.ProtocolEnvelope
@testable import CompanionCore
import CryptoKit
import OllamaBackend
import Pairing
import Transport
import TrustedDevices
import XCTest

final class LocalRuntimeMessageRouterTests: XCTestCase {
    func testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets() {
        let log = sanitizedCompanionLogMessage(
            "Model list failed: http://192.168.1.23:11434/api/tags model-provider.example.test:1234/v1/models route_token=route-secret relay_secret=relay-secret rs=compact-secret Remote route ready: relay.example.test:43171"
        )

        XCTAssertFalse(log.contains("192.168.1.23"))
        XCTAssertFalse(log.contains("11434"))
        XCTAssertFalse(log.contains("model-provider.example.test"))
        XCTAssertFalse(log.contains("1234"))
        XCTAssertFalse(log.contains("/api/tags"))
        XCTAssertFalse(log.contains("/v1/models"))
        XCTAssertFalse(log.contains("route-secret"))
        XCTAssertFalse(log.contains("relay-secret"))
        XCTAssertFalse(log.contains("compact-secret"))
        XCTAssertTrue(log.contains("relay.example.test:43171"))
        XCTAssertTrue(log.contains("[redacted]"))
    }

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
            message: "Ollama is not reachable through AetherLink Runtime.",
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
                message: "LM Studio is not reachable through AetherLink Runtime.",
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
        XCTAssertEqual(model["model_kind"], .string("chat"))
        XCTAssertEqual(model["capabilities"], .array([.string("chat")]))
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
        XCTAssertNil(cloudModel["remote_host"])
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

    @MainActor
    func testRouteRefreshReturnsFreshRelayMaterialFromRuntimeProvider() async throws {
        let sink = RecordingSink()
        let routeRefresher = FakeRuntimeRouteRefresher(result: RuntimeRouteRefreshResult(
            runtimeDeviceID: "runtime-1",
            runtimeKeyFingerprint: "runtime-fingerprint",
            relayHost: "relay.example.test",
            relayPort: 43171,
            relayID: "relay-id-1",
            relaySecret: "relay-secret-1",
            relayExpiresAtEpochMillis: 1_782_205_505_000,
            relayNonce: "relay-nonce-1",
            relayScope: "remote"
        ))
        let router = makeRouter(
            backend: MockBackend(),
            routeRefresher: routeRefresher
        )

        router.handle(ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-1"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.routeRefresh)
        XCTAssertEqual(message?.requestID, "route-refresh-1")
        XCTAssertEqual(message?.payload["runtime_device_id"], .string("runtime-1"))
        XCTAssertEqual(message?.payload["runtime_key_fingerprint"], .string("runtime-fingerprint"))
        XCTAssertEqual(message?.payload["relay_host"], .string("relay.example.test"))
        XCTAssertEqual(message?.payload["relay_port"], .number(43171))
        XCTAssertEqual(message?.payload["relay_id"], .string("relay-id-1"))
        XCTAssertEqual(message?.payload["relay_secret"], .string("relay-secret-1"))
        XCTAssertEqual(message?.payload["relay_expires_at"], .number(1_782_205_505_000))
        XCTAssertEqual(message?.payload["relay_nonce"], .string("relay-nonce-1"))
        XCTAssertEqual(message?.payload["relay_scope"], .string("remote"))
        XCTAssertEqual(routeRefresher.refreshCount, 1)
    }

    @MainActor
    func testRouteRefreshReturnsRetryableErrorWhenRuntimeHasNoRefreshableRoute() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend())

        router.handle(ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-missing"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "route-refresh-missing")
        XCTAssertEqual(message?.payload["code"], .string("route_refresh_unavailable"))
        XCTAssertEqual(message?.payload["retryable"], .bool(true))
    }

    @MainActor
    func testRouteRefreshFailureRedactsRelaySecretsAndProviderEndpoints() async throws {
        let sink = RecordingSink()
        let routeRefresher = FakeRuntimeRouteRefresher(error: RuntimeRouteRefreshTestError(
            message: "route.refresh failed relay_secret=relay-secret-1 route_token=route-token-1 https://provider.example.test:1234/v1/models http://127.0.0.1:11434/api/tags backend=192.168.1.23:11434"
        ))
        let router = makeRouter(
            backend: MockBackend(),
            routeRefresher: routeRefresher
        )

        router.handle(ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-redacted"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "route-refresh-redacted")
        XCTAssertEqual(message?.payload["code"], .string("route_refresh_unavailable"))
        XCTAssertEqual(message?.payload["message"], .string("AetherLink Runtime could not refresh remote route material."))
        XCTAssertEqual(message?.payload["retryable"], .bool(true))
        let payloadDescription = String(describing: message?.payload)
        XCTAssertFalse(payloadDescription.contains("relay-secret-1"))
        XCTAssertFalse(payloadDescription.contains("route-token-1"))
        XCTAssertFalse(payloadDescription.contains("provider.example.test"))
        XCTAssertFalse(payloadDescription.contains("127.0.0.1"))
        XCTAssertFalse(payloadDescription.contains("192.168.1.23"))
        XCTAssertFalse(payloadDescription.contains("11434"))
        XCTAssertFalse(payloadDescription.contains("1234"))
        XCTAssertEqual(routeRefresher.refreshCount, 1)
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

    func testChatSendStoresRuntimeSideProcessingEvents() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEvents: [
                    .reasoningDelta("thinking"),
                    .delta("hello"),
                    .done(inputTokens: 1, outputTokens: 2)
                ]
            ),
            chatEventStore: store
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-store-1",
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

        let messages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(messages.map(\.type), [MessageType.chatDelta, MessageType.chatDelta, MessageType.chatDone])
        let storedEvents = store.events
        XCTAssertEqual(storedEvents.map(\.kind), [.request, .reasoningDelta, .assistantDelta, .done])
        XCTAssertEqual(storedEvents.map(\.requestID), Array(repeating: "chat-store-1", count: 4))
        XCTAssertEqual(storedEvents.map(\.sessionID), Array(repeating: "session-1", count: 4))
        XCTAssertEqual(storedEvents.first?.messages?.last?.content, "hi")
        XCTAssertEqual(storedEvents[1].reasoningDelta, "thinking")
        XCTAssertEqual(storedEvents[2].delta, "hello")
        XCTAssertEqual(storedEvents[3].usage, RuntimeChatStoredUsage(inputTokens: 1, outputTokens: 2))
    }

    func testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        let capturedRequests = LockedBox<[ChatRequest]>([])
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEventBatches: [
                    [
                        .delta("The runtime mediates model access after QR pairing."),
                        .done(inputTokens: 2, outputTokens: 3),
                    ],
                    [
                        .delta(#"{"title":"Runtime Pairing Summary"}"#),
                        .done(inputTokens: 4, outputTokens: 5),
                    ],
                ],
                onChatRequest: { request in
                    capturedRequests.value = capturedRequests.value + [request]
                }
            ),
            chatEventStore: store
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-title-auto",
            payload: [
                "session_id": .string("session-title-auto"),
                "model": .string("llama3.1:8b"),
                "locale": .string("fr"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain QR pairing.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let messages = try await sink.waitForMessages(count: 2)
        XCTAssertEqual(messages.map(\.type), [MessageType.chatDelta, MessageType.chatDone])
        let title = try await waitForSessionTitle(
            in: store,
            sessionID: "session-title-auto",
            expectedTitle: "Runtime Pairing Summary"
        )
        XCTAssertEqual(title, "Runtime Pairing Summary")
        let storedMessages = try store.listMessages(sessionID: "session-title-auto", limit: 10)
        XCTAssertEqual(storedMessages.map(\.role), ["user", "assistant"])
        let backendRequests = capturedRequests.value
        XCTAssertEqual(backendRequests.count, 2)
        XCTAssertEqual(backendRequests.first?.generationID, "chat-title-auto")
        XCTAssertTrue(
            backendRequests.last?.messages.first?.content.contains(
                "Use this BCP-47 locale when writing the title unless the conversation clearly uses another language: fr."
            ) == true
        )
    }

    func testChatSendGeneratedRuntimeTitleStripsInlineThinking() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEventBatches: [
                    [
                        .delta("The runtime keeps model access behind pairing."),
                        .done(inputTokens: 2, outputTokens: 3),
                    ],
                    [
                        .delta("<think>Draft a concise title first.</think>"),
                        .delta(#"{"title":"Trusted Runtime Pairing"}"#),
                        .done(inputTokens: 4, outputTokens: 5),
                    ],
                ]
            ),
            chatEventStore: store
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-title-think-auto",
            payload: [
                "session_id": .string("session-title-think-auto"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain trusted runtime pairing.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let messages = try await sink.waitForMessages(count: 2)
        XCTAssertEqual(messages.map(\.type), [MessageType.chatDelta, MessageType.chatDone])
        let title = try await waitForSessionTitle(
            in: store,
            sessionID: "session-title-think-auto",
            expectedTitle: "Trusted Runtime Pairing"
        )
        XCTAssertEqual(title, "Trusted Runtime Pairing")
        let titleEvents = try store
            .listSessions(limit: 20, includeArchived: true)
            .filter { $0.sessionID == "session-title-think-auto" }
        XCTAssertEqual(titleEvents.first?.title, "Trusted Runtime Pairing")
    }

    func testChatSendTitleGenerationUsesDeterministicFallbackWhenBackendTitleIsInvalid() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEventBatches: [
                    [
                        .delta("Use QR pairing to trust the runtime before model commands."),
                        .done(inputTokens: 2, outputTokens: 3),
                    ],
                    [
                        .delta(#"{"name":"Wrong key"}"#),
                        .done(inputTokens: 4, outputTokens: 5),
                    ],
                ]
            ),
            chatEventStore: store
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-title-fallback",
            payload: [
                "session_id": .string("session-title-fallback"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("How should pairing work?")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        _ = try await sink.waitForMessages(count: 2)
        let title = try await waitForSessionTitle(
            in: store,
            sessionID: "session-title-fallback",
            expectedTitle: "Use QR pairing to trust the"
        )
        XCTAssertEqual(title, "Use QR pairing to trust the")
    }

    func testRuntimeChatStoreListsSessionsAndMessages() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        let requestDate = Date(timeIntervalSince1970: 100)
        let deltaDate = Date(timeIntervalSince1970: 101)
        let doneDate = Date(timeIntervalSince1970: 102)
        try store.append(RuntimeChatStoredEvent(
            timestamp: requestDate,
            kind: .request,
            requestID: "chat-store-read",
            sessionID: "session-read",
            model: "llama3.1:8b",
            messages: [
                ChatMessage(role: "system", content: "AetherLink currently provides runtime-mediated local model chat and does not provide live web search."),
                ChatMessage(role: "system", content: "Runtime user memory:\n- Prefers concise answers."),
                ChatMessage(
                    role: "user",
                    content: "Explain QR pairing.",
                    attachments: [
                        ChatAttachment(
                            type: "image",
                            mimeType: "image/png",
                            name: "pairing.png",
                            dataBase64: "iVBORw0KGgo="
                        ),
                        ChatAttachment(
                            type: "document",
                            mimeType: "text/plain",
                            name: "notes.txt",
                            text: "QR route notes"
                        )
                    ]
                ),
            ]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: deltaDate,
            kind: .reasoningDelta,
            requestID: "chat-store-read",
            sessionID: "session-read",
            model: "llama3.1:8b",
            reasoningDelta: "Checking route material."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: deltaDate,
            kind: .assistantDelta,
            requestID: "chat-store-read",
            sessionID: "session-read",
            model: "llama3.1:8b",
            delta: "Scan the runtime QR."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: doneDate,
            kind: .done,
            requestID: "chat-store-read",
            sessionID: "session-read",
            model: "llama3.1:8b",
            finishReason: "stop",
            usage: RuntimeChatStoredUsage(inputTokens: 3, outputTokens: 4)
        ))

        let sessions = try store.listSessions(limit: 10)
        let messages = try store.listMessages(sessionID: "session-read", limit: 10)

        XCTAssertEqual(sessions.count, 1)
        XCTAssertEqual(sessions.first?.sessionID, "session-read")
        XCTAssertEqual(sessions.first?.title, "New chat")
        XCTAssertEqual(sessions.first?.messageCount, 2)
        XCTAssertEqual(sessions.first?.lastActivityAt, doneDate)
        XCTAssertEqual(sessions.first?.lastEvent, "done")
        XCTAssertEqual(sessions.first?.lastFinishReason, "stop")
        XCTAssertNil(sessions.first?.lastErrorCode)
        XCTAssertEqual(messages.map(\.role), ["user", "assistant"])
        XCTAssertEqual(messages.first?.content, "Explain QR pairing.")
        XCTAssertEqual(messages.first?.attachments.count, 2)
        XCTAssertEqual(messages.first?.attachments.first?.name, "pairing.png")
        XCTAssertEqual(messages.first?.attachments.first?.dataBase64, nil)
        XCTAssertEqual(messages.first?.attachments.last?.name, "notes.txt")
        XCTAssertEqual(messages.first?.attachments.last?.text, "QR route notes")
        XCTAssertEqual(messages.last?.content, "Scan the runtime QR.")
        XCTAssertEqual(messages.last?.reasoning, "Checking route material.")
    }

    func testRuntimeChatStoreReconstructsMultipleTurnsAndUsesStoredTitle() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        let firstRequestDate = Date(timeIntervalSince1970: 200)
        let firstDoneDate = Date(timeIntervalSince1970: 202)
        let secondRequestDate = Date(timeIntervalSince1970: 203)
        let secondDoneDate = Date(timeIntervalSince1970: 205)
        let titleDate = Date(timeIntervalSince1970: 206)

        try store.append(RuntimeChatStoredEvent(
            timestamp: firstRequestDate,
            kind: .request,
            requestID: "turn-1",
            sessionID: "session-multi",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "How does pairing work?")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 201),
            kind: .assistantDelta,
            requestID: "turn-1",
            sessionID: "session-multi",
            model: "llama3.1:8b",
            delta: "Scan a trusted runtime QR."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: firstDoneDate,
            kind: .done,
            requestID: "turn-1",
            sessionID: "session-multi",
            model: "llama3.1:8b"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: secondRequestDate,
            kind: .request,
            requestID: "turn-2",
            sessionID: "session-multi",
            model: "llama3.1:8b",
            messages: [
                ChatMessage(role: "user", content: "How does pairing work?"),
                ChatMessage(role: "assistant", content: "Scan a trusted runtime QR."),
                ChatMessage(role: "user", content: "What happens next?")
            ]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 204),
            kind: .assistantDelta,
            requestID: "turn-2",
            sessionID: "session-multi",
            model: "llama3.1:8b",
            delta: "The trusted device authenticates before model commands."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: secondDoneDate,
            kind: .done,
            requestID: "turn-2",
            sessionID: "session-multi",
            model: "llama3.1:8b"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: titleDate,
            kind: .title,
            requestID: "title-1",
            sessionID: "session-multi",
            model: "llama3.1:8b",
            title: "QR Pairing Flow"
        ))

        let sessions = try store.listSessions(limit: 10)
        let messages = try store.listMessages(sessionID: "session-multi", limit: 10)

        XCTAssertEqual(sessions.first?.title, "QR Pairing Flow")
        XCTAssertEqual(sessions.first?.lastActivityAt, secondDoneDate)
        XCTAssertEqual(sessions.first?.messageCount, 4)
        XCTAssertEqual(messages.map(\.role), ["user", "assistant", "user", "assistant"])
        XCTAssertEqual(messages.map(\.content), [
            "How does pairing work?",
            "Scan a trusted runtime QR.",
            "What happens next?",
            "The trusted device authenticates before model commands."
        ])
    }

    func testRuntimeChatStoreSessionSummaryExposesCancelledAndErrorProcessingState() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 210),
            kind: .request,
            requestID: "cancel-turn",
            sessionID: "session-cancel",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Stop this.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 211),
            kind: .cancelled,
            requestID: "cancel-turn",
            sessionID: "session-cancel",
            model: "llama3.1:8b",
            finishReason: "cancelled"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 220),
            kind: .request,
            requestID: "error-turn",
            sessionID: "session-error",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Use a missing model.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 221),
            kind: .error,
            requestID: "error-turn",
            sessionID: "session-error",
            model: "llama3.1:8b",
            error: RuntimeChatStoredError(code: "model_not_installed", message: "Model is not installed.")
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 230),
            kind: .request,
            requestID: "in-progress-1",
            sessionID: "session-in-progress",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "First turn.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 231),
            kind: .done,
            requestID: "in-progress-1",
            sessionID: "session-in-progress",
            model: "llama3.1:8b",
            finishReason: "stop"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 232),
            kind: .request,
            requestID: "in-progress-2",
            sessionID: "session-in-progress",
            model: "llama3.1:8b",
            messages: [
                ChatMessage(role: "user", content: "First turn."),
                ChatMessage(role: "assistant", content: "First answer."),
                ChatMessage(role: "user", content: "Second turn.")
            ]
        ))

        let sessions = try store.listSessions(limit: 10)
        let cancelled = try XCTUnwrap(sessions.first { $0.sessionID == "session-cancel" })
        let failed = try XCTUnwrap(sessions.first { $0.sessionID == "session-error" })
        let inProgress = try XCTUnwrap(sessions.first { $0.sessionID == "session-in-progress" })

        XCTAssertEqual(cancelled.lastEvent, "cancelled")
        XCTAssertEqual(cancelled.lastFinishReason, "cancelled")
        XCTAssertNil(cancelled.lastErrorCode)
        XCTAssertEqual(failed.lastEvent, "error")
        XCTAssertNil(failed.lastFinishReason)
        XCTAssertEqual(failed.lastErrorCode, "model_not_installed")
        XCTAssertEqual(inProgress.lastEvent, "request")
        XCTAssertNil(inProgress.lastFinishReason)
        XCTAssertNil(inProgress.lastErrorCode)
    }

    func testRuntimeChatStoreAppliesArchiveRestoreAndDeleteLifecycle() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 300),
            kind: .request,
            requestID: "turn-1",
            sessionID: "session-lifecycle",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Keep this runtime-owned chat.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 301),
            kind: .assistantDelta,
            requestID: "turn-1",
            sessionID: "session-lifecycle",
            model: "llama3.1:8b",
            delta: "Stored on the runtime."
        ))

        XCTAssertEqual(try store.listSessions(limit: 10).map(\.sessionID), ["session-lifecycle"])

        let archived = try store.mutateSession(
            sessionID: "session-lifecycle",
            requestID: "archive-1",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 302)
        )
        XCTAssertEqual(archived.mutation, .archive)
        XCTAssertTrue(try store.listSessions(limit: 10).isEmpty)
        let archivedSessions = try store.listSessions(limit: 10, includeArchived: true)
        XCTAssertEqual(archivedSessions.map(\.sessionID), ["session-lifecycle"])
        XCTAssertEqual(archivedSessions.first?.status, "archived")
        XCTAssertEqual(archivedSessions.first?.archivedAt, Date(timeIntervalSince1970: 302))
        XCTAssertEqual(archivedSessions.first?.lastActivityAt, Date(timeIntervalSince1970: 301))
        XCTAssertEqual(try store.listMessages(sessionID: "session-lifecycle", limit: 10).count, 2)

        let restored = try store.mutateSession(
            sessionID: "session-lifecycle",
            requestID: "restore-1",
            mutation: .restore,
            timestamp: Date(timeIntervalSince1970: 303)
        )
        XCTAssertEqual(restored.mutation, .restore)
        XCTAssertEqual(try store.listSessions(limit: 10).map(\.sessionID), ["session-lifecycle"])
        XCTAssertThrowsError(try store.mutateSession(
            sessionID: "session-lifecycle",
            requestID: "delete-active",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 304)
        )) { error in
            XCTAssertEqual(
                error as? RuntimeChatEventStoreError,
                RuntimeChatEventStoreError.sessionMustBeArchivedBeforeDelete("session-lifecycle")
            )
        }

        let archivedAgain = try store.mutateSession(
            sessionID: "session-lifecycle",
            requestID: "archive-2",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 305)
        )
        XCTAssertEqual(archivedAgain.mutation, .archive)

        let deleted = try store.mutateSession(
            sessionID: "session-lifecycle",
            requestID: "delete-1",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 306)
        )
        XCTAssertEqual(deleted.mutation, .delete)
        XCTAssertTrue(try store.listSessions(limit: 10).isEmpty)
        XCTAssertTrue(try store.listSessions(limit: 10, includeArchived: true).isEmpty)
        XCTAssertTrue(try store.listMessages(sessionID: "session-lifecycle", limit: 10).isEmpty)
        XCTAssertThrowsError(try store.mutateSession(
            sessionID: "session-lifecycle",
            requestID: "restore-deleted",
            mutation: .restore,
            timestamp: Date(timeIntervalSince1970: 307)
        ))
    }

    func testRuntimeChatStoreReportsCorruptJSONLLineInsteadOfDroppingIt() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 320),
            kind: .request,
            requestID: "turn-corrupt",
            sessionID: "session-corrupt",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "This valid turn must not be silently hidden.")]
        ))
        try appendRawChatEventLogLine(
            #"{"secret_prompt":"should-not-leak","broken":}"#,
            to: fileURL
        )

        XCTAssertThrowsError(try store.listSessions(limit: 10, includeArchived: true)) { error in
            guard case RuntimeChatEventStoreError.corruptEventLog(let line, let reason) = error else {
                XCTFail("Expected corrupt event log error, got \(error)")
                return
            }
            XCTAssertEqual(line, 2)
            XCTAssertFalse(reason.isEmpty)
            XCTAssertFalse(error.localizedDescription.contains("should-not-leak"))
        }
    }

    func testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore(
            sessions: [
                RuntimeChatStoredSession(
                    sessionID: "session-1",
                    title: "Runtime history",
                    model: "llama3.1:8b",
                    lastActivityAt: Date(timeIntervalSince1970: 100),
                    messageCount: 2,
                    lastEvent: "done",
                    lastFinishReason: "stop",
                    lastErrorCode: nil
                )
            ],
            messages: [
                "session-1": [
                    RuntimeChatStoredMessage(
                        role: "user",
                        content: "Hi",
                        attachments: [
                            ChatAttachment(
                                type: "document",
                                mimeType: "text/plain",
                                name: "context.txt",
                                text: "Saved context"
                            )
                        ],
                        createdAt: Date(timeIntervalSince1970: 100)
                    ),
                    RuntimeChatStoredMessage(
                        role: "assistant",
                        content: "Hello",
                        reasoning: "Short thought",
                        createdAt: Date(timeIntervalSince1970: 101)
                    )
                ]
            ]
        )
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-1",
            payload: ["limit": .number(20)]
        ), sink: sink)
        router.handle(ProtocolEnvelope(
            type: MessageType.chatMessagesList,
            requestID: "messages-1",
            payload: [
                "session_id": .string("session-1"),
                "limit": .number(20)
            ]
        ), sink: sink)

        let responses = try await sink.waitForMessages(count: 2)
        let sessionsResponse = responses.first { $0.requestID == "sessions-1" }
        let messagesResponse = responses.first { $0.requestID == "messages-1" }
        XCTAssertEqual(sessionsResponse?.type, MessageType.chatSessionsList)
        guard case .array(let sessions)? = sessionsResponse?.payload["sessions"],
              case .object(let session)? = sessions.first else {
            XCTFail("Expected sessions response")
            return
        }
        XCTAssertEqual(session["session_id"], .string("session-1"))
        XCTAssertEqual(session["title"], .string("Runtime history"))
        XCTAssertEqual(session["message_count"], .number(2))
        XCTAssertEqual(session["last_event"], .string("done"))
        XCTAssertEqual(session["last_finish_reason"], .string("stop"))
        XCTAssertNil(session["last_error_code"])

        XCTAssertEqual(messagesResponse?.type, MessageType.chatMessagesList)
        XCTAssertEqual(messagesResponse?.payload["session_id"], .string("session-1"))
        guard case .array(let messages)? = messagesResponse?.payload["messages"],
              messages.count == 2,
              case .object(let user)? = messages.first,
              case .object(let assistant)? = messages.last else {
            XCTFail("Expected messages response")
            return
        }
        XCTAssertEqual(user["role"], .string("user"))
        guard case .array(let attachments)? = user["attachments"],
              case .object(let attachment)? = attachments.first else {
            XCTFail("Expected stored attachment response")
            return
        }
        XCTAssertEqual(attachment["type"], .string("document"))
        XCTAssertEqual(attachment["mime_type"], .string("text/plain"))
        XCTAssertEqual(attachment["name"], .string("context.txt"))
        XCTAssertEqual(attachment["text"], .string("Saved context"))
        XCTAssertNil(attachment["data_base64"])
        XCTAssertEqual(assistant["role"], .string("assistant"))
        XCTAssertEqual(assistant["content"], .string("Hello"))
        XCTAssertEqual(assistant["reasoning"], .string("Short thought"))
    }

    func testRuntimeChatHistoryCorruptStoreReturnsStructuredError() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 330),
            kind: .request,
            requestID: "turn-corrupt-route",
            sessionID: "session-corrupt-route",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Keep runtime history reliable.")]
        ))
        try appendRawChatEventLogLine(
            #"{"secret_prompt":"should-not-leak","broken":}"#,
            to: fileURL
        )
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-corrupt",
            payload: ["limit": .number(20)]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "sessions-corrupt")
        XCTAssertEqual(response?.payload["code"], .string("chat_store_unavailable"))
        if case .string(let message)? = response?.payload["message"] {
            XCTAssertTrue(message.contains("corrupt at line 2"))
            XCTAssertFalse(message.contains("should-not-leak"))
        } else {
            XCTFail("Expected structured chat-store error message")
        }
    }

    func testRuntimeChatSessionLifecycleMessagesMutateRuntimeStore() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 400),
            kind: .request,
            requestID: "turn-1",
            sessionID: "session-route",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Archive this chat.")]
        ))
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionArchive,
            requestID: "archive-route",
            payload: ["session_id": .string("session-route")]
        ), sink: sink)
        let archiveResponse = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(archiveResponse?.type, MessageType.chatSessionArchive)
        XCTAssertEqual(archiveResponse?.payload["session_id"], .string("session-route"))
        XCTAssertEqual(archiveResponse?.payload["status"], .string("archived"))
        XCTAssertNotNil(archiveResponse?.payload["archived_at"])
        XCTAssertTrue(try store.listSessions(limit: 10).isEmpty)

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-archived",
            payload: [
                "limit": .number(10),
                "include_archived": .bool(true)
            ]
        ), sink: sink)
        let archivedListResponse = try await sink.waitForMessages(count: 2).last
        XCTAssertEqual(archivedListResponse?.type, MessageType.chatSessionsList)
        guard case .array(let archivedSessions)? = archivedListResponse?.payload["sessions"],
              case .object(let archivedSession)? = archivedSessions.first else {
            XCTFail("Expected archived sessions response")
            return
        }
        XCTAssertEqual(archivedSession["session_id"], .string("session-route"))
        XCTAssertEqual(archivedSession["status"], .string("archived"))
        XCTAssertNotNil(archivedSession["archived_at"])

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionRestore,
            requestID: "restore-route",
            payload: ["session_id": .string("session-route")]
        ), sink: sink)
        let restoreResponse = try await sink.waitForMessages(count: 3).last
        XCTAssertEqual(restoreResponse?.type, MessageType.chatSessionRestore)
        XCTAssertEqual(restoreResponse?.payload["status"], .string("restored"))
        XCTAssertEqual(try store.listSessions(limit: 10).map(\.sessionID), ["session-route"])

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionDelete,
            requestID: "delete-active-route",
            payload: ["session_id": .string("session-route")]
        ), sink: sink)
        let deleteResponse = try await sink.waitForMessages(count: 4).last
        XCTAssertEqual(deleteResponse?.type, MessageType.error)
        XCTAssertEqual(deleteResponse?.requestID, "delete-active-route")
        XCTAssertEqual(deleteResponse?.payload["code"], .string("chat_session_must_be_archived_before_delete"))
        XCTAssertEqual(try store.listSessions(limit: 10).map(\.sessionID), ["session-route"])

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionArchive,
            requestID: "archive-before-delete-route",
            payload: ["session_id": .string("session-route")]
        ), sink: sink)
        let secondArchiveResponse = try await sink.waitForMessages(count: 5).last
        XCTAssertEqual(secondArchiveResponse?.type, MessageType.chatSessionArchive)
        XCTAssertEqual(secondArchiveResponse?.payload["status"], .string("archived"))

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionDelete,
            requestID: "delete-route",
            payload: ["session_id": .string("session-route")]
        ), sink: sink)
        let deleteResponseAfterArchive = try await sink.waitForMessages(count: 6).last
        XCTAssertEqual(deleteResponseAfterArchive?.type, MessageType.chatSessionDelete)
        XCTAssertEqual(deleteResponseAfterArchive?.requestID, "delete-route")
        XCTAssertEqual(deleteResponseAfterArchive?.payload["status"], .string("deleted"))
        XCTAssertTrue(try store.listSessions(limit: 10).isEmpty)
    }

    func testRuntimeChatSessionRenameStoresRuntimeTitle() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 430),
            kind: .request,
            requestID: "turn-rename",
            sessionID: "session-rename",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Rename this chat.")]
        ))
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionRename,
            requestID: "rename-route",
            payload: [
                "session_id": .string("session-rename"),
                "title": .string("  Runtime route notes  ")
            ]
        ), sink: sink)
        let renameResponse = try await sink.waitForMessages(count: 1).first

        XCTAssertEqual(renameResponse?.type, MessageType.chatSessionRename)
        XCTAssertEqual(renameResponse?.payload["session_id"], .string("session-rename"))
        XCTAssertEqual(renameResponse?.payload["title"], .string("Runtime route notes"))
        XCTAssertNotNil(renameResponse?.payload["renamed_at"])
        XCTAssertEqual(try store.listSessions(limit: 10).first?.title, "Runtime route notes")
    }

    func testRuntimeMemoryMessagesMutateRuntimeStore() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let router = makeRouter(
            backend: MockBackend(),
            memoryStore: memoryStore
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryUpsert,
            requestID: "memory-upsert-1",
            payload: [
                "id": .string("memory-1"),
                "content": .string(" Prefers concise Korean answers. "),
                "enabled": .bool(true)
            ]
        ), sink: sink)
        let upsertResponse = try await sink.waitForMessages(count: 1).last
        XCTAssertEqual(upsertResponse?.type, MessageType.memoryUpsert)
        guard case .object(let upsertedEntry)? = upsertResponse?.payload["entry"] else {
            XCTFail("Expected memory entry")
            return
        }
        XCTAssertEqual(upsertedEntry["id"], .string("memory-1"))
        XCTAssertEqual(upsertedEntry["content"], .string("Prefers concise Korean answers."))
        XCTAssertEqual(upsertedEntry["enabled"], .bool(true))

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryList,
            requestID: "memory-list-1"
        ), sink: sink)
        let listResponse = try await sink.waitForMessages(count: 2).last
        XCTAssertEqual(listResponse?.type, MessageType.memoryList)
        guard case .array(let entries)? = listResponse?.payload["entries"],
              case .object(let listedEntry)? = entries.first else {
            XCTFail("Expected memory list")
            return
        }
        XCTAssertEqual(listedEntry["id"], .string("memory-1"))

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryUpsert,
            requestID: "memory-upsert-2",
            payload: [
                "id": .string("memory-1"),
                "content": .string("Prefers short Korean answers."),
                "enabled": .bool(false)
            ]
        ), sink: sink)
        let updateResponse = try await sink.waitForMessages(count: 3).last
        guard case .object(let updatedEntry)? = updateResponse?.payload["entry"] else {
            XCTFail("Expected updated memory entry")
            return
        }
        XCTAssertEqual(updatedEntry["content"], .string("Prefers short Korean answers."))
        XCTAssertEqual(updatedEntry["enabled"], .bool(false))

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryDelete,
            requestID: "memory-delete-1",
            payload: ["id": .string("memory-1")]
        ), sink: sink)
        let deleteResponse = try await sink.waitForMessages(count: 4).last
        XCTAssertEqual(deleteResponse?.type, MessageType.memoryDelete)
        XCTAssertEqual(deleteResponse?.payload["id"], .string("memory-1"))
        XCTAssertNotNil(deleteResponse?.payload["deleted_at"])

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryList,
            requestID: "memory-list-2"
        ), sink: sink)
        let emptyListResponse = try await sink.waitForMessages(count: 5).last
        guard case .array(let emptyEntries)? = emptyListResponse?.payload["entries"] else {
            XCTFail("Expected empty memory list")
            return
        }
        XCTAssertTrue(emptyEntries.isEmpty)
    }

    func testChatSendPrependsRuntimeCapabilityGuard() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-capability-guard",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Can you search the web?")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        let request = try XCTUnwrap(capturedRequest.value)
        XCTAssertEqual(request.messages.first?.role, "system")
        XCTAssertTrue(request.messages.first?.content.contains("does not provide live web search") == true)
        XCTAssertTrue(request.messages.first?.content.contains("Do not claim that you can search the web") == true)
        XCTAssertEqual(request.messages.dropFirst().first?.role, "user")
        XCTAssertEqual(request.messages.dropFirst().first?.content, "Can you search the web?")
    }

    func testChatSendDoesNotDuplicateClientCapabilityGuard() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let clientGuard = """
        AetherLink currently provides runtime-mediated local model chat, model listing, file/image attachment handling when supported, chat titles, and suggested next questions.
        The current build does not provide live web search, browsing, MCP tools, skills, scheduled automations, Python execution, or other external tools unless explicit tool output is included in this conversation.
        Do not claim that you can search the web, browse, run tools, access files, or use unavailable integrations.
        """
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-capability-guard-existing",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("system"),
                        "content": .string(clientGuard)
                    ]),
                    .object([
                        "role": .string("user"),
                        "content": .string("Can you browse?")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        let request = try XCTUnwrap(capturedRequest.value)
        let guardMessages = request.messages.filter { message in
            message.role == "system" &&
                message.content.lowercased().contains("does not provide live web search")
        }
        XCTAssertEqual(guardMessages.count, 1)
        XCTAssertEqual(request.messages.count, 2)
        XCTAssertEqual(request.messages.first?.content, clientGuard)
    }

    func testChatSendInjectsEnabledRuntimeMemoryFromRuntimeStore() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let now = Date()
        _ = try memoryStore.upsert(
            id: "memory-1",
            content: " Prefers concise Korean answers. ",
            enabled: true,
            timestamp: now
        )
        _ = try memoryStore.upsert(
            id: "memory-2",
            content: "Ignore disabled entries.",
            enabled: false,
            timestamp: now.addingTimeInterval(1)
        )
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
                onChatRequest: { request in
                    capturedRequest.value = request
                }
            ),
            memoryStore: memoryStore
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-runtime-memory",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Remember my preferences?")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        let request = try XCTUnwrap(capturedRequest.value)
        XCTAssertEqual(request.messages.first?.role, "system")
        XCTAssertTrue(request.messages.first?.content.contains("does not provide live web search") == true)
        XCTAssertEqual(request.messages.dropFirst().first?.role, "system")
        XCTAssertTrue(request.messages.dropFirst().first?.content.hasPrefix("Runtime user memory:") == true)
        XCTAssertTrue(request.messages.dropFirst().first?.content.contains("Prefers concise Korean answers.") == true)
        XCTAssertFalse(request.messages.dropFirst().first?.content.contains("Ignore disabled entries.") == true)
        XCTAssertEqual(request.messages.dropFirst(2).first?.role, "user")
    }

    func testChatSendRuntimeMemoryOverridesClientSuppliedMemory() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        _ = try memoryStore.upsert(
            id: "memory-1",
            content: "Runtime canonical memory.",
            enabled: true,
            timestamp: Date()
        )
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
                onChatRequest: { request in
                    capturedRequest.value = request
                }
            ),
            memoryStore: memoryStore
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-runtime-memory-override",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("system"),
                        "content": .string("Runtime user memory:\n- stale client memory")
                    ]),
                    .object([
                        "role": .string("user"),
                        "content": .string("Use current memory.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        let request = try XCTUnwrap(capturedRequest.value)
        let memoryMessages = request.messages.filter { message in
            message.role == "system" &&
                message.content.trimmingCharacters(in: .whitespacesAndNewlines).hasPrefix("Runtime user memory:")
        }
        XCTAssertEqual(memoryMessages.count, 1)
        XCTAssertTrue(memoryMessages.first?.content.contains("Runtime canonical memory.") == true)
        XCTAssertFalse(memoryMessages.first?.content.contains("stale client memory") == true)
    }

    func testChatSendStoresOnlyClientVisibleMessagesWhileBackendReceivesRuntimeContext() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let chatEventStore = RecordingRuntimeChatEventStore()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        _ = try memoryStore.upsert(
            id: "memory-1",
            content: "Runtime canonical memory.",
            enabled: true,
            timestamp: Date()
        )
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
                onChatRequest: { request in
                    capturedRequest.value = request
                }
            ),
            chatEventStore: chatEventStore,
            memoryStore: memoryStore
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-runtime-memory-storage",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("system"),
                        "content": .string("Runtime user memory:\n- stale client memory")
                    ]),
                    .object([
                        "role": .string("user"),
                        "content": .string("Use current memory.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        let backendRequest = try XCTUnwrap(capturedRequest.value)
        XCTAssertTrue(backendRequest.messages.contains { message in
            message.role == "system" &&
                message.content.lowercased().contains("does not provide live web search")
        })
        XCTAssertTrue(backendRequest.messages.contains { message in
            message.role == "system" &&
                message.content.contains("Runtime canonical memory.")
        })
        let requestEvent = try XCTUnwrap(chatEventStore.events.first { $0.kind == .request })
        XCTAssertEqual(requestEvent.messages?.map(\.role), ["user"])
        XCTAssertEqual(requestEvent.messages?.first?.content, "Use current memory.")
        XCTAssertFalse(requestEvent.messages?.contains { message in
            message.content.lowercased().contains("does not provide live web search") ||
                message.content.trimmingCharacters(in: .whitespacesAndNewlines).hasPrefix("Runtime user memory:")
        } == true)
    }

    func testChatSendDoesNotCompactShortConversation() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-no-compaction",
            payload: [
                "session_id": .string("session-compact"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Summarize the pairing flow.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("Pair with a QR code, then keep the runtime trusted.")
                    ]),
                    .object([
                        "role": .string("user"),
                        "content": .string("Keep it brief.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        let request = try XCTUnwrap(capturedRequest.value)
        XCTAssertFalse(request.messages.contains { $0.content.hasPrefix("Runtime conversation summary:") })
        XCTAssertEqual(request.messages.filter(\.isConversationTurnForTests).map(\.content), [
            "Summarize the pairing flow.",
            "Pair with a QR code, then keep the runtime trusted.",
            "Keep it brief."
        ])
    }

    func testChatSendCompactsOlderTurnsBeforeBackendRequestWhenContextIsLarge() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let chatEventStore = RecordingRuntimeChatEventStore()
        let olderUserContent = "old user turn 0 " + String(repeating: "A", count: 2_000)
        let olderAssistantContent = "old assistant turn 0 " + String(repeating: "B", count: 2_000)
        let recentUserContent = "recent user turn 8 must remain verbatim"
        let recentAssistantContent = "recent assistant turn 8 must remain verbatim"
        var messagePayloads: [JSONValue] = [
            .object([
                "role": .string("user"),
                "content": .string(olderUserContent)
            ]),
            .object([
                "role": .string("assistant"),
                "content": .string(olderAssistantContent)
            ])
        ]
        for index in 1...7 {
            messagePayloads.append(.object([
                "role": .string("user"),
                "content": .string("old user turn \(index) " + String(repeating: "U", count: 2_000))
            ]))
            messagePayloads.append(.object([
                "role": .string("assistant"),
                "content": .string("old assistant turn \(index) " + String(repeating: "A", count: 2_000))
            ]))
        }
        messagePayloads.append(.object([
            "role": .string("user"),
            "content": .string(recentUserContent)
        ]))
        messagePayloads.append(.object([
            "role": .string("assistant"),
            "content": .string(recentAssistantContent)
        ]))
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
                onChatRequest: { request in
                    capturedRequest.value = request
                }
            ),
            chatEventStore: chatEventStore
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-compaction-large",
            payload: [
                "session_id": .string("session-compact"),
                "model": .string("llama3.1:8b"),
                "messages": .array(messagePayloads)
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        let request = try XCTUnwrap(capturedRequest.value)
        let summaryMessage = try XCTUnwrap(request.messages.first { $0.content.hasPrefix("Runtime conversation summary:") })
        XCTAssertEqual(summaryMessage.role, "system")
        XCTAssertTrue(summaryMessage.content.contains("Backend-only summary of older turns"))
        XCTAssertTrue(summaryMessage.content.contains("old user turn 0"))
        XCTAssertFalse(request.messages.contains { $0.content == olderUserContent })
        XCTAssertFalse(request.messages.contains { $0.content == olderAssistantContent })
        XCTAssertTrue(request.messages.contains { $0.content == recentUserContent })
        XCTAssertTrue(request.messages.contains { $0.content == recentAssistantContent })
        XCTAssertEqual(request.messages.filter(\.isConversationTurnForTests).count, 12)

        let requestEvent = try XCTUnwrap(chatEventStore.events.first { $0.kind == .request })
        XCTAssertEqual(requestEvent.messages?.count, messagePayloads.count)
        XCTAssertTrue(requestEvent.messages?.contains { $0.content == olderUserContent } == true)
        XCTAssertFalse(requestEvent.messages?.contains { $0.content.hasPrefix("Runtime conversation summary:") } == true)
    }

    func testChatSendCompactionKeepsRuntimeMemoryAndCapabilityGuardSeparate() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        _ = try memoryStore.upsert(
            id: "memory-1",
            content: "Always answer with concise bilingual summaries.",
            enabled: true,
            timestamp: Date()
        )
        var messagePayloads: [JSONValue] = []
        for index in 0..<18 {
            messagePayloads.append(.object([
                "role": .string(index.isMultiple(of: 2) ? "user" : "assistant"),
                "content": .string("memory separation turn \(index) " + String(repeating: "M", count: 1_600))
            ]))
        }
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
                onChatRequest: { request in
                    capturedRequest.value = request
                }
            ),
            memoryStore: memoryStore
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-compaction-memory",
            payload: [
                "session_id": .string("session-compact"),
                "model": .string("llama3.1:8b"),
                "messages": .array(messagePayloads)
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        let request = try XCTUnwrap(capturedRequest.value)
        XCTAssertTrue(request.messages.first?.content.contains("does not provide live web search") == true)
        XCTAssertTrue(request.messages.dropFirst().first?.content.hasPrefix("Runtime user memory:") == true)
        XCTAssertTrue(request.messages.dropFirst(2).first?.content.hasPrefix("Runtime conversation summary:") == true)
        XCTAssertEqual(request.messages.filter { $0.content.hasPrefix("Runtime user memory:") }.count, 1)
        XCTAssertEqual(request.messages.filter { $0.content.hasPrefix("Runtime conversation summary:") }.count, 1)
    }

    func testChatSendReturnsStructuredErrorWhenRuntimeMemoryCannotLoad() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
                onChatRequest: { request in
                    capturedRequest.value = request
                }
            ),
            memoryStore: FailingRuntimeMemoryStore()
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-runtime-memory-error",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Hello")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.payload["code"], .string("memory_store_unavailable"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertNil(capturedRequest.value)
    }

    func testChatSendAppendsDocumentAttachmentTextAndPreservesImageAttachment() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            models: [
                ModelInfo(
                    id: "llama3.2-vision",
                    name: "llama3.2-vision",
                    capabilities: ["chat", "vision"],
                    installed: true
                )
            ],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
        let documentText = "Roadmap item: add offline document summaries."
        let imageDataBase64 = "iVBORw0KGgo="
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-attachments",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.2-vision"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Summarize this."),
                        "attachments": .array([
                            .object([
                                "type": .string("document"),
                                "mime_type": .string("text/markdown"),
                                "name": .string("roadmap.md"),
                                "data_base64": .string(Data(documentText.utf8).base64EncodedString())
                            ]),
                            .object([
                                "type": .string("image"),
                                "mime_type": .string("image/png"),
                                "name": .string("diagram.png"),
                                "data_base64": .string(imageDataBase64)
                            ])
                        ])
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)

        let request = try XCTUnwrap(capturedRequest.value)
        let forwardedMessage = try XCTUnwrap(request.messages.first(where: { $0.role == "user" }))
        XCTAssertTrue(forwardedMessage.content.contains("Summarize this."))
        XCTAssertTrue(forwardedMessage.content.contains("[Attached document: roadmap.md (text/plain)]"))
        XCTAssertTrue(forwardedMessage.content.contains(documentText))
        XCTAssertEqual(forwardedMessage.attachments, [
            ChatAttachment(
                type: "document",
                mimeType: "text/plain",
                name: "roadmap.md",
                text: documentText
            ),
            ChatAttachment(
                type: "image",
                mimeType: "image/png",
                name: "diagram.png",
                dataBase64: imageDataBase64
            )
        ])
    }

    func testChatSendExtractsMimeOnlyStructuredTextDocumentAttachment() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
        let documentText = #"title = "Hello TOML""#
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-mime-only-document",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Read this config."),
                        "attachments": .array([
                            .object([
                                "type": .string("document"),
                                "mime_type": .string("application/toml"),
                                "name": .string("config"),
                                "data_base64": .string(Data(documentText.utf8).base64EncodedString())
                            ])
                        ])
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)

        let request = try XCTUnwrap(capturedRequest.value)
        let forwardedMessage = try XCTUnwrap(request.messages.first(where: { $0.role == "user" }))
        XCTAssertTrue(forwardedMessage.content.contains("Read this config."))
        XCTAssertTrue(forwardedMessage.content.contains("[Attached document: config (text/plain)]"))
        XCTAssertTrue(forwardedMessage.content.contains(documentText))
        XCTAssertEqual(forwardedMessage.attachments, [
            ChatAttachment(
                type: "document",
                mimeType: "text/plain",
                name: "config",
                text: documentText
            )
        ])
    }

    func testChatSendImageAttachmentRequiresVisionCapableModel() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-image-non-vision",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Describe this image."),
                        "attachments": .array([
                            .object([
                                "type": .string("image"),
                                "mime_type": .string("image/png"),
                                "name": .string("photo.png"),
                                "data_base64": .string("iVBORw0KGgo=")
                            ])
                        ])
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "chat-image-non-vision")
        XCTAssertEqual(message?.payload["code"], .string("unsupported_attachment"))
        XCTAssertNil(capturedRequest.value)
    }

    func testChatSendAllowsLMStudioImageAttachmentsForVisionCapableModel() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            provider: .lmStudio,
            models: [
                ModelInfo(
                    id: "local-vision",
                    name: "Local Vision",
                    provider: .lmStudio,
                    capabilities: ["chat", "vision"],
                    installed: true
                )
            ],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-lmstudio-image",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("lm_studio:local-vision"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Describe this image."),
                        "attachments": .array([
                            .object([
                                "type": .string("image"),
                                "mime_type": .string("image/png"),
                                "name": .string("photo.png"),
                                "data_base64": .string("iVBORw0KGgo=")
                            ])
                        ])
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        XCTAssertEqual(message?.requestID, "chat-lmstudio-image")
        let forwardedRequest = try XCTUnwrap(capturedRequest.value)
        let forwardedMessage = try XCTUnwrap(forwardedRequest.messages.first(where: { $0.role == "user" }))
        XCTAssertEqual(forwardedMessage.attachments.first?.dataBase64, "iVBORw0KGgo=")
    }

    func testChatSendUnsupportedDocumentAttachmentReturnsStructuredError() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-unsupported-attachment",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Read this."),
                        "attachments": .array([
                            .object([
                                "type": .string("document"),
                                "mime_type": .string("application/x-custom"),
                                "name": .string("archive.custom"),
                                "data_base64": .string(Data("not supported".utf8).base64EncodedString())
                            ])
                        ])
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "chat-unsupported-attachment")
        XCTAssertEqual(message?.payload["code"], .string("unsupported_attachment"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertNil(capturedRequest.value)
    }

    func testChatSendStreamsReasoningDeltaSeparatelyFromAnswerDelta() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "qwen3:8b", name: "qwen3:8b", installed: true)],
            chatEvents: [
                .reasoningDelta("thinking"),
                .delta("answer"),
                .done(inputTokens: 3, outputTokens: 4)
            ]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-reasoning",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("qwen3:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("hi")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let messages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(messages.map(\.type), [MessageType.chatDelta, MessageType.chatDelta, MessageType.chatDone])
        XCTAssertEqual(messages[0].requestID, "chat-reasoning")
        XCTAssertEqual(messages[0].payload["reasoning_delta"], .string("thinking"))
        XCTAssertNil(messages[0].payload["delta"])
        XCTAssertEqual(messages[1].payload["delta"], .string("answer"))
        XCTAssertNil(messages[1].payload["reasoning_delta"])
    }

    func testChatSendSplitsInlineThinkTagsBeforeStreamingAnswer() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "qwen3:8b", name: "qwen3:8b", installed: true)],
                chatEvents: [
                    .delta("<thi"),
                    .delta("nk>Plan first."),
                    .delta("</think>Answer"),
                    .done(inputTokens: 3, outputTokens: 4)
                ]
            ),
            chatEventStore: store
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-inline-think",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("qwen3:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("hi")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let messages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(messages.map(\.type), [MessageType.chatDelta, MessageType.chatDelta, MessageType.chatDone])
        XCTAssertEqual(messages[0].payload["reasoning_delta"], .string("Plan first."))
        XCTAssertNil(messages[0].payload["delta"])
        XCTAssertEqual(messages[1].payload["delta"], .string("Answer"))
        XCTAssertNil(messages[1].payload["reasoning_delta"])

        let storedEvents = store.events
        XCTAssertEqual(storedEvents.map(\.kind), [.request, .reasoningDelta, .assistantDelta, .done])
        XCTAssertEqual(storedEvents[1].reasoningDelta, "Plan first.")
        XCTAssertEqual(storedEvents[2].delta, "Answer")
    }

    func testChatSendSplitsInlineThinkingAliasBeforeStreamingAnswer() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "qwen3:8b", name: "qwen3:8b", installed: true)],
            chatEvents: [
                .delta("<thinking>Check.</thinking>Visible"),
                .done(inputTokens: 3, outputTokens: 4)
            ]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-inline-thinking",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("qwen3:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("hi")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let messages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(messages.map(\.type), [MessageType.chatDelta, MessageType.chatDelta, MessageType.chatDone])
        XCTAssertEqual(messages[0].payload["reasoning_delta"], .string("Check."))
        XCTAssertEqual(messages[1].payload["delta"], .string("Visible"))
    }

    func testChatSendInstalledCloudModelReturnsModelNotInstalled() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore()
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
        ), chatEventStore: store)
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
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "chat-cloud")
        XCTAssertEqual(message?.payload["code"], .string("model_not_installed"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertEqual(store.events.map(\.kind), [.request, .error])
        XCTAssertEqual(store.events.last?.error?.code, "model_not_installed")
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

    func testChatSuggestionsRequestReturnsStructuredSuggestions() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"suggestions":["1. What should we verify next?","what should we verify next?","- Can you compare the tradeoffs?","\"• What happens when the route expires?\""]}"#),
                .done(inputTokens: 4, outputTokens: 12)
            ],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSuggestionsRequest,
            requestID: "suggestions-1",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "max_suggestions": .number(3),
                "locale": .string("en"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates all backend access.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatSuggestionsResult)
        XCTAssertEqual(message?.requestID, "suggestions-1")
        XCTAssertEqual(message?.payload["suggestions"], .array([
            .string("What should we verify next?"),
            .string("Can you compare the tradeoffs?"),
            .string("What happens when the route expires?")
        ]))
        let request = try XCTUnwrap(capturedRequest.value)
        XCTAssertEqual(request.generationID, "suggestions-1")
        XCTAssertEqual(request.model, "llama3.1:8b")
        XCTAssertTrue(request.messages.first?.content.contains("strict JSON") == true)
    }

    func testChatSuggestionsRequestNormalizesBlankDuplicateAndExcessSuggestions() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"suggestions":["  1. What   should\nwe verify next?  ","what should we verify next?","   ","Résumé details?","Resume details?","How do archived chats affect memory?","How is relay lease renewed?","Should not appear?"]}"#),
                .done(inputTokens: 4, outputTokens: 12)
            ]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSuggestionsRequest,
            requestID: "suggestions-normalized",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "max_suggestions": .number(5),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates all backend access.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatSuggestionsResult)
        XCTAssertEqual(message?.requestID, "suggestions-normalized")
        XCTAssertEqual(message?.payload["suggestions"], .array([
            .string("What should we verify next?"),
            .string("Résumé details?"),
            .string("How do archived chats affect memory?"),
            .string("How is relay lease renewed?")
        ]))
    }

    func testChatSuggestionsRequestAcceptsFencedStructuredSuggestions() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta("""
                ```json
                {"suggestions":["How should pairing be verified?","What happens when the route expires?"]}
                ```
                """),
                .done(inputTokens: 4, outputTokens: 12)
            ]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSuggestionsRequest,
            requestID: "suggestions-fenced-json",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "max_suggestions": .number(3),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates all backend access.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatSuggestionsResult)
        XCTAssertEqual(message?.requestID, "suggestions-fenced-json")
        XCTAssertEqual(message?.payload["suggestions"], .array([
            .string("How should pairing be verified?"),
            .string("What happens when the route expires?")
        ]))
    }

    func testChatSuggestionsRequestReturnsEmptySuggestionsForInvalidJSON() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta("Ask about follow-up work\nCompare alternatives"),
                .done(inputTokens: 4, outputTokens: 12)
            ]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSuggestionsRequest,
            requestID: "suggestions-invalid-json",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates all backend access.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatSuggestionsResult)
        XCTAssertEqual(message?.requestID, "suggestions-invalid-json")
        XCTAssertEqual(message?.payload["suggestions"], .array([]))
    }

    func testChatSuggestionsRequestFallsBackToNumberedLocalizedList() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta("""
                1. 다음에는 어떤 경로를 확인할까요?
                2. どの設定を見直しますか？
                3. Quels journaux faut-il vérifier ?
                4. Should not be returned?
                """),
                .done(inputTokens: 4, outputTokens: 12)
            ]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSuggestionsRequest,
            requestID: "suggestions-numbered-localized",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "max_suggestions": .number(3),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates all backend access.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatSuggestionsResult)
        XCTAssertEqual(message?.requestID, "suggestions-numbered-localized")
        XCTAssertEqual(message?.payload["suggestions"], .array([
            .string("다음에는 어떤 경로를 확인할까요?"),
            .string("どの設定を見直しますか？"),
            .string("Quels journaux faut-il vérifier ?")
        ]))
    }

    func testChatTitleRequestReturnsStructuredTitle() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"title":"Runtime-Mediated Model Access"}"#),
                .done(inputTokens: 4, outputTokens: 8)
            ],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ), chatEventStore: store)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-1",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "locale": .string("en"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates all backend access.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatTitleResult)
        XCTAssertEqual(message?.requestID, "title-1")
        XCTAssertEqual(message?.payload["title"], .string("Runtime-Mediated Model Access"))
        let request = try XCTUnwrap(capturedRequest.value)
        XCTAssertEqual(request.generationID, "title-1")
        XCTAssertEqual(request.model, "llama3.1:8b")
        XCTAssertTrue(request.messages.first?.content.contains("strict JSON") == true)
        XCTAssertTrue(request.messages.first?.content.contains("en") == true)
        XCTAssertEqual(store.events.map(\.kind), [.title])
        XCTAssertEqual(store.events.first?.sessionID, "session-1")
        XCTAssertEqual(store.events.first?.requestID, "title-1")
        XCTAssertEqual(store.events.first?.title, "Runtime-Mediated Model Access")
    }

    func testChatTitleRequestAcceptsFencedStructuredTitle() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta("""
                ```json
                {"title":"Runtime Route Refresh"}
                ```
                """),
                .done(inputTokens: 4, outputTokens: 8)
            ]
        ), chatEventStore: store)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-fenced-json",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain route refresh.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("Scan the latest QR to refresh route material.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatTitleResult)
        XCTAssertEqual(message?.requestID, "title-fenced-json")
        XCTAssertEqual(message?.payload["title"], .string("Runtime Route Refresh"))
        XCTAssertEqual(store.events.map(\.kind), [.title])
        XCTAssertEqual(store.events.first?.title, "Runtime Route Refresh")
    }

    func testChatTitleRequestFallsBackToPlainTitle() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta("Title: Runtime pairing and model routing"),
                .done(inputTokens: 4, outputTokens: 8)
            ]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-plain",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("How should pairing work?")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("Use QR pairing and keep model routing on the runtime.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatTitleResult)
        XCTAssertEqual(message?.requestID, "title-plain")
        XCTAssertEqual(message?.payload["title"], .string("Runtime pairing and model routing"))
    }

    func testChatTitleRequestReturnsEmptyTitleForInvalidJSONOrEmptyOutput() async throws {
        let invalidJSONSink = RecordingSink()
        let invalidJSONRouter = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"name":"Wrong key"}"#),
                .done(inputTokens: 4, outputTokens: 8)
            ]
        ))
        let invalidJSONEnvelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-invalid-json",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates backend access.")
                    ])
                ])
            ]
        )

        invalidJSONRouter.handle(invalidJSONEnvelope, sink: invalidJSONSink)

        let invalidJSONMessage = try await invalidJSONSink.waitForMessages(count: 1).first
        XCTAssertEqual(invalidJSONMessage?.type, MessageType.chatTitleResult)
        XCTAssertEqual(invalidJSONMessage?.requestID, "title-invalid-json")
        XCTAssertEqual(invalidJSONMessage?.payload["title"], .string(""))

        let emptySink = RecordingSink()
        let emptyRouter = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta("   \n"),
                .done(inputTokens: 4, outputTokens: 0)
            ]
        ))
        let emptyEnvelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-empty",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates backend access.")
                    ])
                ])
            ]
        )

        emptyRouter.handle(emptyEnvelope, sink: emptySink)

        let emptyMessage = try await emptySink.waitForMessages(count: 1).first
        XCTAssertEqual(emptyMessage?.type, MessageType.chatTitleResult)
        XCTAssertEqual(emptyMessage?.requestID, "title-empty")
        XCTAssertEqual(emptyMessage?.payload["title"], .string(""))

        let invalidFencedSink = RecordingSink()
        let invalidFencedRouter = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta("""
                ```json
                {"name":"Wrong key"}
                ```
                """),
                .done(inputTokens: 4, outputTokens: 8)
            ]
        ))
        let invalidFencedEnvelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-invalid-fenced-json",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ]),
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates backend access.")
                    ])
                ])
            ]
        )

        invalidFencedRouter.handle(invalidFencedEnvelope, sink: invalidFencedSink)

        let invalidFencedMessage = try await invalidFencedSink.waitForMessages(count: 1).first
        XCTAssertEqual(invalidFencedMessage?.type, MessageType.chatTitleResult)
        XCTAssertEqual(invalidFencedMessage?.requestID, "title-invalid-fenced-json")
        XCTAssertEqual(invalidFencedMessage?.payload["title"], .string(""))
    }

    func testChatTitleRequestWithoutUserMessageReturnsInvalidPayload() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-invalid",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("assistant"),
                        "content": .string("The runtime mediates all backend access.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "title-invalid")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testChatTitleRequestWithoutAssistantMessageReturnsInvalidPayload() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)]
        ))
        let envelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-no-assistant",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Explain the transport.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "title-no-assistant")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testChatSendNonInstalledModelReturnsModelNotInstalled() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "example-uninstalled", name: "example-uninstalled", installed: false, source: .local)]
        ), chatEventStore: store)
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
        XCTAssertEqual(store.events.map(\.kind), [.request, .error])
        XCTAssertEqual(store.events.first?.requestID, "chat-missing-model")
        XCTAssertEqual(store.events.first?.sessionID, "session-1")
        XCTAssertEqual(store.events.first?.messages?.first(where: { $0.role == "user" })?.content, "hi")
        XCTAssertEqual(store.events.last?.error?.code, "model_not_installed")
    }

    func testChatSendInstalledEmbeddingModelReturnsModelNotInstalled() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(backend: MockBackend(
            models: [
                ModelInfo(
                    id: "nomic-embed-text",
                    name: "nomic-embed-text",
                    kind: .embedding,
                    installed: true,
                    source: .local
                )
            ],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)]
        ), chatEventStore: store)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-embedding-model",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("nomic-embed-text"),
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
        XCTAssertEqual(message?.requestID, "chat-embedding-model")
        XCTAssertEqual(message?.payload["code"], .string("model_not_installed"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertEqual(store.events.map(\.kind), [.request, .error])
        XCTAssertEqual(store.events.last?.error?.code, "model_not_installed")
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
        XCTAssertEqual(
            message?.payload["message"],
            .string("Unsupported AetherLink Runtime message type: memory.search")
        )
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testPairingQRCodePayloadCanOmitEndpointHints() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "mac-1",
            macName: "AetherLink Runtime",
            fingerprint: "fp-1",
            runtimePublicKeyBase64: "runtime+public/key=",
            routeToken: "route-1"
        )

        let components = try XCTUnwrap(URLComponents(string: session.qrPayload))
        let queryItems = try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }

        XCTAssertEqual(components.scheme, "aetherlink")
        XCTAssertEqual(components.host, "pair")
        XCTAssertEqual(queryItems["version"], "1")
        XCTAssertEqual(queryItems["pairing_nonce"], session.nonce)
        XCTAssertEqual(queryItems["pairing_code"], session.code)
        XCTAssertEqual(queryItems["runtime_device_id"], "mac-1")
        XCTAssertEqual(queryItems["runtime_name"], "AetherLink Runtime")
        XCTAssertEqual(queryItems["runtime_public_key"], "runtime+public/key=")
        XCTAssertEqual(queryItems["runtime_key_fingerprint"], "fp-1")
        XCTAssertEqual(queryItems["route_token"], "route-1")
        XCTAssertNil(queryItems["mac_device_id"])
        XCTAssertNil(queryItems["mac_name"])
        XCTAssertNil(queryItems["fingerprint"])
        XCTAssertNil(queryItems["service_type"])
        XCTAssertNil(queryItems["host"])
        XCTAssertNil(queryItems["port"])
        XCTAssertTrue(session.qrPayload.contains("runtime_public_key=runtime%2Bpublic/key%3D"))
    }

    func testPairingQRCodePayloadIncludesRelaySecretWhenPresent() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "mac-1",
            macName: "AetherLink Runtime",
            fingerprint: "fp-1",
            routeToken: "route-1",
            relayHost: "relay.example.test",
            relayPort: 43171,
            relayID: "relay-id-1",
            relaySecret: "secret with symbols + / =",
            relayExpiresAtEpochMillis: 1_780_000_000_000,
            relayNonce: "relay-nonce-1",
            relayScope: "usb_reverse"
        )

        let components = try XCTUnwrap(URLComponents(string: session.qrPayload))
        let queryItems = try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }

        XCTAssertEqual(queryItems["relay_host"], "relay.example.test")
        XCTAssertEqual(queryItems["relay_port"], "43171")
        XCTAssertEqual(queryItems["relay_id"], "relay-id-1")
        XCTAssertEqual(queryItems["relay_secret"], "secret with symbols + / =")
        XCTAssertEqual(queryItems["relay_expires_at"], "1780000000000")
        XCTAssertEqual(queryItems["relay_nonce"], "relay-nonce-1")
        XCTAssertEqual(queryItems["relay_scope"], "usb_reverse")
        XCTAssertTrue(session.qrPayload.contains("relay_secret=secret%20with%20symbols%20%2B%20/%20%3D"))
    }

    func testCompactPairingQRCodePayloadUsesShortAliasesForCameraScanning() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "mac-1",
            macName: "AetherLink Runtime",
            fingerprint: "fp-1",
            runtimePublicKeyBase64: "runtime+public/key=",
            routeToken: "route-1",
            relayHost: "relay.example.test",
            relayPort: 43171,
            relayID: "relay-id-1",
            relaySecret: "secret-1",
            relayExpiresAtEpochMillis: 1_780_000_000_000,
            relayNonce: "relay-nonce-1"
        )

        let components = try XCTUnwrap(URLComponents(string: session.compactQRCodePayload))
        let queryItems = try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }

        XCTAssertEqual(components.scheme, "aetherlink")
        XCTAssertEqual(components.host, "pair")
        XCTAssertLessThan(session.compactQRCodePayload.count, session.qrPayload.count)
        XCTAssertEqual(queryItems["v"], "1")
        XCTAssertEqual(queryItems["n"], session.nonce)
        XCTAssertEqual(queryItems["c"], session.code)
        XCTAssertEqual(queryItems["rid"], "mac-1")
        XCTAssertEqual(queryItems["rn"], "AetherLink Runtime")
        XCTAssertEqual(queryItems["rk"], "runtime+public/key=")
        XCTAssertEqual(queryItems["rf"], "fp-1")
        XCTAssertEqual(queryItems["rt"], "route-1")
        XCTAssertEqual(queryItems["rh"], "relay.example.test")
        XCTAssertEqual(queryItems["rp"], "43171")
        XCTAssertEqual(queryItems["ri"], "relay-id-1")
        XCTAssertEqual(queryItems["rs"], "secret-1")
        XCTAssertEqual(queryItems["rx"], "1780000000000")
        XCTAssertEqual(queryItems["rrn"], "relay-nonce-1")
        XCTAssertNil(queryItems["runtime_device_id"])
        XCTAssertNil(queryItems["runtime_key_fingerprint"])
        XCTAssertNil(queryItems["relay_secret"])
    }

    func testCompactPairingQRCodePayloadMatchesSharedRelayFixture() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            runtimePublicKeyBase64: "runtime+public/key=",
            routeToken: "route-token-1",
            relayHost: "relay.example.test",
            relayPort: 43171,
            relayID: "relay-bootstrap-1",
            relaySecret: "secret-bootstrap-1",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "allocated-nonce-1",
            relayScope: "remote"
        )

        let normalizedPayload = try compactPairingPayload(
            session.compactQRCodePayload,
            overriding: [
                "n": "nonce-1",
                "c": "123456"
            ]
        )

        XCTAssertEqual(normalizedPayload, try sharedProtocolFixture("macos-compact-relay-pairing-uri.txt"))
    }

    func testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            runtimePublicKeyBase64: "runtime+public/key=",
            routeToken: "route-token-1",
            relayHost: "100.64.1.10",
            relayPort: 43171,
            relayID: "relay-private-overlay-1",
            relaySecret: "secret-private-overlay-1",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "private-overlay-nonce-1",
            relayScope: "private_overlay"
        )

        let normalizedPayload = try compactPairingPayload(
            session.compactQRCodePayload,
            overriding: [
                "n": "nonce-private-1",
                "c": "654321"
            ]
        )

        XCTAssertEqual(
            normalizedPayload,
            try sharedProtocolFixture("macos-compact-private-overlay-pairing-uri.txt")
        )
    }

    func testPairingRequestStoresTrustedDeviceAndReturnsAccepted() async throws {
        let sink = RecordingSink()
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "mac-1",
            fingerprint: "fp-1",
            runtimePublicKeyBase64: "runtime-public-key",
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
        XCTAssertEqual(message?.payload["runtime_device_id"], .string("mac-1"))
        XCTAssertEqual(message?.payload["runtime_public_key"], .string("runtime-public-key"))
        XCTAssertEqual(message?.payload["runtime_key_fingerprint"], .string("fp-1"))
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
        XCTAssertEqual(
            lockout?.payload["message"],
            .string("Too many invalid pairing attempts. Start pairing again in AetherLink Runtime.")
        )
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
        XCTAssertEqual(
            expired?.payload["message"],
            .string("Pairing session expired. Start pairing again in AetherLink Runtime.")
        )
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

    @MainActor
    func testRouteRefreshRequiresAuthenticatedConnectionByDefault() async throws {
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            routeRefresher: FakeRuntimeRouteRefresher(result: RuntimeRouteRefreshResult(
                runtimeDeviceID: "runtime-1",
                runtimeKeyFingerprint: "runtime-fingerprint",
                relayHost: "relay.example.test",
                relayPort: 43171,
                relayID: "relay-id-1",
                relaySecret: "relay-secret-1",
                relayExpiresAtEpochMillis: 1_782_205_505_000,
                relayNonce: "relay-nonce-1"
            ))
        )

        router.handle(ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-unauthenticated"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "route-refresh-unauthenticated")
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
        XCTAssertNil(challenge?.payload["runtime_key_fingerprint"])
        XCTAssertNil(challenge?.payload["runtime_signature"])
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

    func testTrustedHelloIncludesVerifiableRuntimeProofWhenSignerIsAvailable() async throws {
        let clientKey = P256.Signing.PrivateKey()
        let runtimeKey = P256.Signing.PrivateKey()
        let runtimeIdentity = RuntimeIdentityKeyStore.identityKey(from: runtimeKey)
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await store.trust(TrustedDevice(
            id: "android-runtime-proof",
            name: "Runtime Proof Android",
            publicKeyBase64: clientKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: store,
            runtimeChallengeSigner: TestRuntimeChallengeSigner(privateKey: runtimeKey)
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-runtime-proof",
            payload: ["device_id": .string("android-runtime-proof")]
        ), sink: sink)

        let challenge = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(challenge?.type, MessageType.authChallenge)
        XCTAssertEqual(challenge?.payload["device_id"], .string("android-runtime-proof"))
        XCTAssertEqual(challenge?.payload["runtime_key_fingerprint"], .string(runtimeIdentity.fingerprint))
        guard case .string(let nonce)? = challenge?.payload["nonce"],
              case .string(let signature)? = challenge?.payload["runtime_signature"] else {
            XCTFail("Expected nonce and runtime signature in auth challenge")
            return
        }

        XCTAssertTrue(RuntimeIdentityKeyStore.verifyAuthChallengeSignature(
            publicKeyBase64: runtimeIdentity.publicKeyBase64,
            deviceID: "android-runtime-proof",
            nonce: nonce,
            signatureBase64: signature
        ))
        XCTAssertFalse(RuntimeIdentityKeyStore.verifyAuthChallengeSignature(
            publicKeyBase64: runtimeIdentity.publicKeyBase64,
            deviceID: "android-runtime-proof",
            nonce: "different-nonce",
            signatureBase64: signature
        ))
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
    func testCompanionAppModelGeneratesDirectRoutePairingQRCode() throws {
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing(routePolicy: .allowLocalDiagnostic)

        let session = try XCTUnwrap(model.pairingSession)
        let components = try XCTUnwrap(URLComponents(string: session.qrPayload))
        let queryItems = try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }

        XCTAssertEqual(components.scheme, "aetherlink")
        XCTAssertEqual(components.host, "pair")
        XCTAssertEqual(queryItems["pairing_nonce"], session.nonce)
        XCTAssertEqual(queryItems["pairing_code"], session.code)
        XCTAssertFalse(queryItems["runtime_device_id"]?.isEmpty ?? true)
        XCTAssertFalse(queryItems["runtime_key_fingerprint"]?.isEmpty ?? true)
        XCTAssertFalse(queryItems["route_token"]?.isEmpty ?? true)
        XCTAssertNil(queryItems["mac_device_id"])
        XCTAssertNil(queryItems["fingerprint"])
        XCTAssertEqual(queryItems["host"], "192.168.1.44")
        XCTAssertEqual(queryItems["port"], "43170")
    }

    @MainActor
    func testCompanionAppModelDefaultPairingRequiresRemoteQRCodeRoute() throws {
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(model.logs.first, "Remote pairing QR not generated: configure a reachable remote route first")
    }

    @MainActor
    func testCompanionAppModelPublishesRemoteRoutePreparationIssueWhenBootstrapAllocationThrows() throws {
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: nil,
            canAllocateRemoteRelayRoute: true,
            error: NSError(
                domain: "AetherLinkTests",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: "Route allocator offline"]
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            remoteRelayRouteAllocator: allocator,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.kind, .automaticPreparationFailed)
        XCTAssertNil(model.remoteRoutePreparationIssue?.endpoint)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.message, "Route allocator offline")
        XCTAssertEqual(model.logs.first, "Remote pairing QR not generated: configure a reachable remote route first")
        XCTAssertTrue(model.logs.contains("Remote route bootstrap failed: Route allocator offline"))
    }

    @MainActor
    func testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator() async throws {
        let defaults = try isolatedDefaults()
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.bootstrap.test",
                    port: 43171,
                    relayID: "relay-bootstrap-1",
                    relaySecret: "secret-bootstrap-1"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "allocated-nonce-1"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(model.developmentRelayEndpoint, "relay.bootstrap.test:43171")
        XCTAssertTrue(model.isDevelopmentRelayRouteEligibleForQRCode)
        XCTAssertTrue(model.isDevelopmentRelayRoutePreparedForQRCode)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)
        XCTAssertEqual(model.developmentRelayConnectionStatus.status, .stopped)
        XCTAssertEqual(relayClient.startedConfiguration?.host, "relay.bootstrap.test")
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "allocated-nonce-1")
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.host"), "relay.bootstrap.test")
        assertStoredRelaySecret("secret-bootstrap-1", defaults: defaults, store: relaySecretStore)

        relayClient.emit(.waitingForPeer)
        await Task.yield()

        let session = try XCTUnwrap(model.pairingSession)
        let qrItems = try queryItems(from: session.qrPayload)
        let compactQRItems = try queryItems(from: session.compactQRCodePayload)
        XCTAssertEqual(qrItems["relay_host"], "relay.bootstrap.test")
        XCTAssertEqual(qrItems["relay_port"], "43171")
        XCTAssertEqual(qrItems["relay_id"], "relay-bootstrap-1")
        XCTAssertEqual(qrItems["relay_secret"], "secret-bootstrap-1")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "allocated-nonce-1")
        XCTAssertEqual(qrItems["relay_scope"], "remote")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
        XCTAssertLessThan(session.compactQRCodePayload.count, session.qrPayload.count)
        XCTAssertEqual(compactQRItems["rt"], qrItems["route_token"])
        XCTAssertEqual(compactQRItems["rh"], "relay.bootstrap.test")
        XCTAssertEqual(compactQRItems["rp"], "43171")
        XCTAssertEqual(compactQRItems["ri"], "relay-bootstrap-1")
        XCTAssertEqual(compactQRItems["rs"], "secret-bootstrap-1")
        XCTAssertEqual(compactQRItems["rx"], "4102444800000")
        XCTAssertEqual(compactQRItems["rrn"], "allocated-nonce-1")
        XCTAssertEqual(compactQRItems["rsc"], "remote")
        XCTAssertNil(compactQRItems["h"])
        XCTAssertNil(compactQRItems["p"])
        XCTAssertNil(compactQRItems["relay_host"])
        XCTAssertNil(compactQRItems["relay_secret"])
    }

    @MainActor
    func testCompanionAppModelDefaultPairingFallsBackAcrossBootstrapRelayEndpointsBeforeQRCode() async throws {
        let defaults = try isolatedDefaults()
        let relayClient = FakeRelayPeerClient()
        let environment = [
            "AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS": "relay-dead.test:8443,relay-good.test:443"
        ]
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocations: [
                nil,
                CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: "relay-good.test",
                        port: 443,
                        relayID: "relay-good-id",
                        relaySecret: "relay-good-secret"
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: 4_102_444_800_000,
                        nonce: "relay-good-nonce"
                    )
                )
            ]
        )
        let allocator = EnvironmentRemoteRelayRouteAllocator(
            environment: environment,
            relayServiceAllocator: serviceAllocator
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            environment: environment,
            userDefaults: defaults,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(serviceAllocator.calls, [
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-dead.test",
                port: 8443,
                routeToken: try XCTUnwrap(defaults.string(forKey: "aetherlink.discovery_route_token")),
                relaySecret: nil,
                allocationToken: nil
            ),
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-good.test",
                port: 443,
                routeToken: try XCTUnwrap(defaults.string(forKey: "aetherlink.discovery_route_token")),
                relaySecret: nil,
                allocationToken: nil
            )
        ])
        XCTAssertEqual(relayClient.startedConfiguration?.host, "relay-good.test")
        XCTAssertEqual(relayClient.startedConfiguration?.port, 443)
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-good-id")
        XCTAssertEqual(relayClient.startedConfiguration?.relaySecret, "relay-good-secret")
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "relay-good-nonce")
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.host"), "relay-good.test")
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.port"), 443)

        relayClient.emit(.waitingForPeer)
        await Task.yield()

        let session = try XCTUnwrap(model.pairingSession)
        let qrItems = try queryItems(from: session.qrPayload)
        XCTAssertEqual(qrItems["relay_host"], "relay-good.test")
        XCTAssertEqual(qrItems["relay_port"], "443")
        XCTAssertEqual(qrItems["relay_id"], "relay-good-id")
        XCTAssertEqual(qrItems["relay_secret"], "relay-good-secret")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "relay-good-nonce")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
    }

    @MainActor
    func testCompanionAppModelDefaultPairingUsesSavedBootstrapRelayEndpointBeforeQRCode() async throws {
        let defaults = try isolatedDefaults()
        defaults.set("relay-saved-dead.test:8443, relay-saved-good.test:443", forKey: "aetherlink.bootstrap_relay.endpoints")
        defaults.set("stored-allocation-token", forKey: "aetherlink.bootstrap_relay.allocation_token")
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let relayClient = FakeRelayPeerClient()
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocations: [
                nil,
                CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: "relay-saved-good.test",
                        port: 443,
                        relayID: "relay-saved-id",
                        relaySecret: "relay-saved-secret"
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: 4_102_444_800_000,
                        nonce: "relay-saved-nonce"
                    )
                )
            ]
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            relayServiceRouteAllocator: serviceAllocator,
            environment: [:],
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        XCTAssertTrue(model.bootstrapRelaySettings.isEnabled)
        XCTAssertTrue(model.canPrepareRemoteRelayRouteAutomatically)
        assertStoredBootstrapAllocationToken("stored-allocation-token", defaults: defaults, store: relaySecretStore)

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(serviceAllocator.calls, [
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-saved-dead.test",
                port: 8443,
                routeToken: try XCTUnwrap(defaults.string(forKey: "aetherlink.discovery_route_token")),
                relaySecret: nil,
                allocationToken: "stored-allocation-token"
            ),
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-saved-good.test",
                port: 443,
                routeToken: try XCTUnwrap(defaults.string(forKey: "aetherlink.discovery_route_token")),
                relaySecret: nil,
                allocationToken: "stored-allocation-token"
            )
        ])
        XCTAssertEqual(relayClient.startedConfiguration?.host, "relay-saved-good.test")
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-saved-id")
        XCTAssertEqual(relayClient.startedConfiguration?.relaySecret, "relay-saved-secret")
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "relay-saved-nonce")

        relayClient.emit(.waitingForPeer)
        await Task.yield()

        let session = try XCTUnwrap(model.pairingSession)
        let qrItems = try queryItems(from: session.qrPayload)
        XCTAssertEqual(qrItems["relay_host"], "relay-saved-good.test")
        XCTAssertEqual(qrItems["relay_port"], "443")
        XCTAssertEqual(qrItems["relay_id"], "relay-saved-id")
        XCTAssertEqual(qrItems["relay_secret"], "relay-saved-secret")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "relay-saved-nonce")
        XCTAssertEqual(qrItems["relay_scope"], "remote")
        XCTAssertNil(qrItems["allocation_token"])
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
    }

    @MainActor
    func testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode() async throws {
        let defaults = try isolatedDefaults()
        let relayClient = FakeRelayPeerClient()
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.bootstrap.test",
                    port: 43171,
                    relayID: "relay-bootstrap-fresh",
                    relaySecret: "secret-bootstrap-fresh"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "allocated-nonce-fresh"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: defaults,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.configureDevelopmentRelay(
            host: "relay.bootstrap.test",
            port: 43171,
            relaySecret: "stale-secret"
        )
        model.start()
        relayClient.emit(.waitingForPeer)
        await Task.yield()
        let staleRelayID = try XCTUnwrap(relayClient.startedConfiguration?.relayID)
        XCTAssertNotEqual(staleRelayID, "relay-bootstrap-fresh")
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(serviceAllocator.calls.count, 1)
        XCTAssertEqual(serviceAllocator.calls.first?.host, "relay.bootstrap.test")
        XCTAssertEqual(serviceAllocator.calls.first?.relaySecret, "stale-secret")
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-bootstrap-fresh")
        XCTAssertEqual(relayClient.startedConfiguration?.relaySecret, "secret-bootstrap-fresh")
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "allocated-nonce-fresh")
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        relayClient.emit(.waitingForPeer)
        await Task.yield()

        let session = try XCTUnwrap(model.pairingSession)
        let qrItems = try queryItems(from: session.qrPayload)
        XCTAssertEqual(qrItems["relay_host"], "relay.bootstrap.test")
        XCTAssertEqual(qrItems["relay_id"], "relay-bootstrap-fresh")
        XCTAssertEqual(qrItems["relay_secret"], "secret-bootstrap-fresh")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "allocated-nonce-fresh")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
    }

    @MainActor
    func testCompanionAppModelRejectsUnreachableRemoteRouteAllocation() throws {
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "127.0.0.1",
                    port: 43171,
                    relayID: "relay-loopback",
                    relaySecret: "secret-loopback"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertNil(relayClient.startedConfiguration)
        XCTAssertTrue(model.logs.contains("Remote route bootstrap rejected unreachable connection address 127.0.0.1"))
    }

    @MainActor
    func testCompanionAppModelStartRenewsSavedBootstrapRelayRouteBeforeRelayStart() throws {
        let defaults = try isolatedDefaults()
        defaults.set("relay.stale.test", forKey: "aetherlink.relay.host")
        defaults.set(43171, forKey: "aetherlink.relay.port")
        defaults.set("relay-stale", forKey: "aetherlink.relay.id")
        defaults.set("saved-secret", forKey: "aetherlink.relay.secret")
        let relaySecretStore = FakeCompanionRelaySecretStore()
        var events: [String] = []
        let relayClient = FakeRelayPeerClient {
            events.append("relay-start")
        }
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.bootstrap.test",
                    port: 443,
                    relayID: "relay-renewed",
                    relaySecret: "saved-secret"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "renewed-nonce"
                )
            ),
            onAllocate: {
                events.append("allocate")
            }
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS": "relay.bootstrap.test:443"
            ],
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.start(port: 43210)

        XCTAssertEqual(events, ["allocate", "relay-start"])
        XCTAssertEqual(allocator.calls.map(\.preferredRelaySecret), ["saved-secret"])
        XCTAssertEqual(relayClient.startedConfiguration?.host, "relay.bootstrap.test")
        XCTAssertEqual(relayClient.startedConfiguration?.port, 443)
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-renewed")
        XCTAssertEqual(relayClient.startedConfiguration?.relaySecret, "saved-secret")
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "renewed-nonce")
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.host"), "relay.bootstrap.test")
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.port"), 443)
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.id"), "relay-renewed")
        assertStoredRelaySecret("saved-secret", defaults: defaults, store: relaySecretStore)
        XCTAssertNil(model.pairingSession)
        XCTAssertFalse(model.logs.contains("Pairing code generated"))
    }

    @MainActor
    func testCompanionAppModelStartDoesNotAllocateSavedRelayWithoutBootstrapEnvironment() throws {
        let defaults = try isolatedDefaults()
        defaults.set("relay.saved.test", forKey: "aetherlink.relay.host")
        defaults.set(43171, forKey: "aetherlink.relay.port")
        defaults.set("relay-saved", forKey: "aetherlink.relay.id")
        defaults.set("saved-secret", forKey: "aetherlink.relay.secret")
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.bootstrap.test",
                    port: 443,
                    relayID: "relay-renewed",
                    relaySecret: "saved-secret"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            environment: [:],
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.start(port: 43210)

        XCTAssertTrue(allocator.calls.isEmpty)
        XCTAssertEqual(relayClient.startedConfiguration?.host, "relay.saved.test")
        XCTAssertEqual(relayClient.startedConfiguration?.port, 43171)
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-saved")
        XCTAssertEqual(relayClient.startedConfiguration?.relaySecret, "saved-secret")
        assertStoredRelaySecret("saved-secret", defaults: defaults, store: relaySecretStore)
        XCTAssertNil(model.pairingSession)
        XCTAssertFalse(model.logs.contains("Pairing code generated"))
    }

    @MainActor
    func testCompanionAppModelRenewsBootstrapRelayRouteAfterRelayFailure() async throws {
        let defaults = try isolatedDefaults()
        defaults.set("relay.stale.test", forKey: "aetherlink.relay.host")
        defaults.set(43171, forKey: "aetherlink.relay.port")
        defaults.set("relay-stale", forKey: "aetherlink.relay.id")
        defaults.set("saved-secret", forKey: "aetherlink.relay.secret")
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.bootstrap.test",
                    port: 443,
                    relayID: "relay-renewed",
                    relaySecret: "saved-secret"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS": "relay.bootstrap.test:443,relay.after-failure.test:443"
            ],
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.start(port: 43210)
        XCTAssertEqual(allocator.calls.map(\.preferredRelaySecret), ["saved-secret"])
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-renewed")

        allocator.allocation = CompanionRemoteRelayRouteAllocation(
            configuration: RelayPeerConfiguration(
                host: "relay.after-failure.test",
                port: 443,
                relayID: "relay-after-failure",
                relaySecret: "saved-secret"
            )
        )
        relayClient.emit(.failed("Relay did not return ready after registration."))
        await Task.yield()

        XCTAssertEqual(allocator.calls.map(\.preferredRelaySecret), ["saved-secret", "saved-secret"])
        XCTAssertEqual(relayClient.startedConfiguration?.host, "relay.after-failure.test")
        XCTAssertEqual(relayClient.startedConfiguration?.port, 443)
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-after-failure")
        XCTAssertEqual(relayClient.startedConfiguration?.relaySecret, "saved-secret")
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.host"), "relay.after-failure.test")
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.id"), "relay-after-failure")
        assertStoredRelaySecret("saved-secret", defaults: defaults, store: relaySecretStore)
        XCTAssertNil(model.pairingSession)
    }

    @MainActor
    func testCompanionAppModelRelayFailureDoesNotAllocateWithoutBootstrapEnvironment() async throws {
        let defaults = try isolatedDefaults()
        defaults.set("relay.saved.test", forKey: "aetherlink.relay.host")
        defaults.set(43171, forKey: "aetherlink.relay.port")
        defaults.set("relay-saved", forKey: "aetherlink.relay.id")
        defaults.set("saved-secret", forKey: "aetherlink.relay.secret")
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.bootstrap.test",
                    port: 443,
                    relayID: "relay-renewed",
                    relaySecret: "saved-secret"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            environment: [:],
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.start(port: 43210)
        relayClient.emit(.failed("Relay did not return ready after registration."))
        await Task.yield()

        XCTAssertTrue(allocator.calls.isEmpty)
        XCTAssertEqual(relayClient.startedConfiguration?.host, "relay.saved.test")
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-saved")
        assertStoredRelaySecret("saved-secret", defaults: defaults, store: relaySecretStore)
        XCTAssertNil(model.pairingSession)
    }

    func testEnvironmentRemoteRelayRouteAllocatorRequestsBootstrapServiceAllocation() throws {
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.bootstrap.test",
                    port: 443,
                    relayID: "allocated-relay",
                    relaySecret: "allocated-secret"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "allocated-nonce"
                )
            )
        )
        let allocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_HOST": "relay.bootstrap.test",
                "AETHERLINK_BOOTSTRAP_RELAY_PORT": "443"
            ],
            relayServiceAllocator: serviceAllocator
        )

        let allocation = try allocator.allocateRemoteRelayRoute(
            runtimeDeviceID: "runtime-1",
            routeToken: "route-token-1",
            preferredRelaySecret: "preferred-secret-1"
        )

        XCTAssertEqual(allocation?.configuration.host, "relay.bootstrap.test")
        XCTAssertEqual(allocation?.configuration.port, 443)
        XCTAssertEqual(allocation?.configuration.relayID, "allocated-relay")
        XCTAssertEqual(allocation?.configuration.relaySecret, "allocated-secret")
        XCTAssertEqual(allocation?.lease?.nonce, "allocated-nonce")
        XCTAssertEqual(serviceAllocator.calls, [
            FakeRelayServiceRouteAllocator.Call(
                host: "relay.bootstrap.test",
                port: 443,
                routeToken: "route-token-1",
                relaySecret: "preferred-secret-1",
                allocationToken: nil
            )
        ])
    }

    func testEnvironmentRemoteRelayRouteAllocatorPassesBootstrapAllocationToken() throws {
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.bootstrap.test",
                    port: 443,
                    relayID: "allocated-relay",
                    relaySecret: "allocated-secret"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "allocated-nonce"
                )
            )
        )
        let allocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_HOST": "relay.bootstrap.test",
                "AETHERLINK_BOOTSTRAP_RELAY_PORT": "443",
                "AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN": "allocation-token-1"
            ],
            relayServiceAllocator: serviceAllocator
        )

        _ = try allocator.allocateRemoteRelayRoute(
            runtimeDeviceID: "runtime-1",
            routeToken: "route-token-1",
            preferredRelaySecret: "preferred-secret-1"
        )

        XCTAssertEqual(serviceAllocator.calls.first?.allocationToken, "allocation-token-1")
    }

    func testEnvironmentRemoteRelayRouteAllocatorUsesStoredBootstrapSettingsWhenEnvironmentIsEmpty() throws {
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocations: [
                nil,
                CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: "relay-saved-good.test",
                        port: 443,
                        relayID: "allocated-relay",
                        relaySecret: "allocated-secret"
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: 4_102_444_800_000,
                        nonce: "allocated-nonce"
                    )
                )
            ]
        )
        let allocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [:],
            storedBootstrapRelaySettings: CompanionBootstrapRelaySettings(
                isEnabled: true,
                endpoints: "relay-saved-dead.test:8443, relay-saved-good.test:443",
                allocationToken: "stored-allocation-token"
            ),
            relayServiceAllocator: serviceAllocator
        )

        XCTAssertTrue(allocator.canAllocateRemoteRelayRoute)
        let allocation = try allocator.allocateRemoteRelayRoute(
            runtimeDeviceID: "runtime-1",
            routeToken: "route-token-1",
            preferredRelaySecret: "preferred-secret-1"
        )

        XCTAssertEqual(allocation?.configuration.host, "relay-saved-good.test")
        XCTAssertEqual(allocation?.configuration.port, 443)
        XCTAssertEqual(allocation?.lease?.nonce, "allocated-nonce")
        XCTAssertEqual(serviceAllocator.calls, [
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-saved-dead.test",
                port: 8443,
                routeToken: "route-token-1",
                relaySecret: "preferred-secret-1",
                allocationToken: "stored-allocation-token"
            ),
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-saved-good.test",
                port: 443,
                routeToken: "route-token-1",
                relaySecret: "preferred-secret-1",
                allocationToken: "stored-allocation-token"
            )
        ])
    }

    func testEnvironmentRemoteRelayRouteAllocatorReportsAutomaticAvailabilityFromBootstrapEnvironment() throws {
        let noBootstrapAllocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [:],
            relayServiceAllocator: FakeRelayServiceRouteAllocator(allocation: nil)
        )
        let dynamicBootstrapAllocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_HOST": "relay.example.test",
                "AETHERLINK_BOOTSTRAP_RELAY_PORT": "443"
            ],
            relayServiceAllocator: FakeRelayServiceRouteAllocator(allocation: nil)
        )
        let completeStaticBootstrapAllocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_HOST": "relay.example.test",
                "AETHERLINK_BOOTSTRAP_RELAY_ID": "relay-id",
                "AETHERLINK_BOOTSTRAP_RELAY_SECRET": "relay-secret"
            ],
            relayServiceAllocator: FakeRelayServiceRouteAllocator(allocation: nil)
        )
        let incompleteStaticBootstrapAllocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_HOST": "relay.example.test",
                "AETHERLINK_BOOTSTRAP_RELAY_ID": "relay-id"
            ],
            relayServiceAllocator: FakeRelayServiceRouteAllocator(allocation: nil)
        )

        XCTAssertFalse(noBootstrapAllocator.canAllocateRemoteRelayRoute)
        XCTAssertTrue(dynamicBootstrapAllocator.canAllocateRemoteRelayRoute)
        XCTAssertTrue(completeStaticBootstrapAllocator.canAllocateRemoteRelayRoute)
        XCTAssertFalse(incompleteStaticBootstrapAllocator.canAllocateRemoteRelayRoute)
    }

    func testEnvironmentRemoteRelayRouteAllocatorParsesEndpointListInOrder() throws {
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocations: [
                nil,
                nil,
                CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: "2001:db8::42",
                        port: 8443,
                        relayID: "allocated-relay",
                        relaySecret: "allocated-secret"
                    )
                )
            ]
        )
        let allocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS": " relay-one.test, relay-two.test:443, [2001:db8::42]:8443 ",
                "AETHERLINK_BOOTSTRAP_RELAY_PORT": "9443"
            ],
            relayServiceAllocator: serviceAllocator
        )

        let allocation = try allocator.allocateRemoteRelayRoute(
            runtimeDeviceID: "runtime-1",
            routeToken: "route-token-1",
            preferredRelaySecret: nil
        )

        XCTAssertEqual(allocation?.configuration.host, "2001:db8::42")
        XCTAssertEqual(allocation?.configuration.port, 8443)
        XCTAssertEqual(serviceAllocator.calls, [
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-one.test",
                port: 9443,
                routeToken: "route-token-1",
                relaySecret: nil,
                allocationToken: nil
            ),
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-two.test",
                port: 443,
                routeToken: "route-token-1",
                relaySecret: nil,
                allocationToken: nil
            ),
            FakeRelayServiceRouteAllocator.Call(
                host: "2001:db8::42",
                port: 8443,
                routeToken: "route-token-1",
                relaySecret: nil,
                allocationToken: nil
            )
        ])
    }

    func testEnvironmentRemoteRelayRouteAllocatorFallsBackAcrossEndpointList() throws {
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocations: [
                nil,
                CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: "relay-good.test",
                        port: 443,
                        relayID: "allocated-relay",
                        relaySecret: "allocated-secret"
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: 4_102_444_800_000,
                        nonce: "allocated-nonce"
                    )
                )
            ]
        )
        let allocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS": "relay-bad.test:8443,relay-good.test:443",
                "AETHERLINK_BOOTSTRAP_RELAY_HOST": "legacy-relay.test",
                "AETHERLINK_BOOTSTRAP_RELAY_PORT": "9443"
            ],
            relayServiceAllocator: serviceAllocator
        )

        let allocation = try allocator.allocateRemoteRelayRoute(
            runtimeDeviceID: "runtime-1",
            routeToken: "route-token-1",
            preferredRelaySecret: "preferred-secret-1"
        )

        XCTAssertEqual(allocation?.configuration.host, "relay-good.test")
        XCTAssertEqual(allocation?.lease?.nonce, "allocated-nonce")
        XCTAssertEqual(serviceAllocator.calls, [
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-bad.test",
                port: 8443,
                routeToken: "route-token-1",
                relaySecret: "preferred-secret-1",
                allocationToken: nil
            ),
            FakeRelayServiceRouteAllocator.Call(
                host: "relay-good.test",
                port: 443,
                routeToken: "route-token-1",
                relaySecret: "preferred-secret-1",
                allocationToken: nil
            )
        ])
    }

    func testEnvironmentRemoteRelayRouteAllocatorUsesFirstEndpointForStaticBootstrapOverride() throws {
        let serviceAllocator = FakeRelayServiceRouteAllocator(allocation: nil)
        let allocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS": "relay-static-one.test:443,relay-static-two.test:8443",
                "AETHERLINK_BOOTSTRAP_RELAY_ID": "relay-static",
                "AETHERLINK_BOOTSTRAP_RELAY_SECRET": "relay-static-secret"
            ],
            relayServiceAllocator: serviceAllocator
        )

        let allocation = try allocator.allocateRemoteRelayRoute(
            runtimeDeviceID: "runtime-1",
            routeToken: "route-token-1",
            preferredRelaySecret: nil
        )

        XCTAssertEqual(allocation?.configuration.host, "relay-static-one.test")
        XCTAssertEqual(allocation?.configuration.port, 443)
        XCTAssertEqual(allocation?.configuration.relayID, "relay-static")
        XCTAssertEqual(allocation?.configuration.relaySecret, "relay-static-secret")
        XCTAssertTrue(serviceAllocator.calls.isEmpty)
    }

    func testEnvironmentRemoteRelayRouteAllocatorRejectsIncompleteStaticBootstrapOverride() throws {
        let allocator = EnvironmentRemoteRelayRouteAllocator(
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS": "relay.bootstrap.test:443",
                "AETHERLINK_BOOTSTRAP_RELAY_ID": "relay-static"
            ],
            relayServiceAllocator: FakeRelayServiceRouteAllocator(allocation: nil)
        )

        XCTAssertThrowsError(try allocator.allocateRemoteRelayRoute(
            runtimeDeviceID: "runtime-1",
            routeToken: "route-token-1",
            preferredRelaySecret: nil
        )) { error in
            XCTAssertEqual(
                error as? RelayServiceRouteAllocationError,
                .incompleteStaticBootstrapRoute
            )
        }
    }

    @MainActor
    func testCompanionAppModelPersistsRelaySettingsAndIncludesRelayInQRCodeAfterRelayReady() async throws {
        let defaults = try isolatedDefaults()
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let transport = FakeRuntimeTransport()
        let relayClient = FakeRelayPeerClient()
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.example.test",
                    port: 43171,
                    relayID: "allocated-relay",
                    relaySecret: "allocated-secret"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "allocated-nonce"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: transport,
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.configureDevelopmentRelay(
            host: " relay.example.test ",
            port: 43171,
            relaySecret: "secret-1",
            attemptAllocation: true
        )

        model.beginPairing()
        XCTAssertTrue(model.hasDevelopmentRelayRoute)
        XCTAssertTrue(model.isDevelopmentRelayRouteEligibleForQRCode)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)
        XCTAssertFalse(model.shouldIncludeDevelopmentRelayInPairingQRCode)
        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(
            model.logs.first,
            "Remote pairing QR not generated: remote route relay.example.test:43171 is not ready"
        )

        relayClient.emit(.waitingForPeer)
        await Task.yield()

        XCTAssertTrue(model.hasDevelopmentRelayRoute)
        XCTAssertEqual(model.developmentRelayEndpoint, "relay.example.test:43171")
        XCTAssertTrue(model.relayFrameEncryptionEnabled)
        XCTAssertEqual(model.developmentRelaySettings.host, "relay.example.test")
        XCTAssertEqual(model.developmentRelaySettings.port, 43171)
        XCTAssertEqual(model.developmentRelaySettings.relayID, "allocated-relay")
        XCTAssertEqual(model.developmentRelaySettings.relaySecret, "allocated-secret")
        XCTAssertFalse(model.developmentRelaySettings.isEnvironmentOverride)
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.host"), "relay.example.test")
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.port"), 43171)
        assertStoredRelaySecret("allocated-secret", defaults: defaults, store: relaySecretStore)

        let session = try XCTUnwrap(model.pairingSession)
        let qrItems = try queryItems(from: session.qrPayload)
        XCTAssertTrue(model.isDevelopmentRelayQRCodeReady)
        XCTAssertTrue(model.shouldIncludeDevelopmentRelayInPairingQRCode)
        XCTAssertEqual(qrItems["relay_host"], "relay.example.test")
        XCTAssertEqual(qrItems["relay_port"], "43171")
        XCTAssertEqual(qrItems["relay_secret"], "allocated-secret")
        XCTAssertEqual(qrItems["relay_id"], "allocated-relay")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "allocated-nonce")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])

        let restoredRelayClient = FakeRelayPeerClient()
        let restoredModel = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: restoredRelayClient,
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )
        XCTAssertTrue(restoredModel.hasDevelopmentRelayRoute)
        XCTAssertEqual(restoredModel.developmentRelayEndpoint, "relay.example.test:43171")
        XCTAssertEqual(restoredModel.developmentRelaySettings.relaySecret, "allocated-secret")
        XCTAssertFalse(restoredModel.developmentRelaySettings.isEnvironmentOverride)

        restoredModel.regenerateDevelopmentRelaySecret()
        let regeneratedSecret = try XCTUnwrap(restoredModel.developmentRelaySettings.relaySecret)
        XCTAssertNotEqual(regeneratedSecret, "allocated-secret")
        assertStoredRelaySecret(regeneratedSecret, defaults: defaults, store: relaySecretStore)
        restoredModel.start(port: 43211)
        restoredRelayClient.emit(.waitingForPeer)
        await Task.yield()
        restoredModel.beginPairing()
        XCTAssertNil(restoredModel.pairingSession)
        XCTAssertFalse(restoredModel.isDevelopmentRelayQRCodeReady)

        restoredModel.clearDevelopmentRelay()
        restoredModel.beginPairing()
        XCTAssertNil(restoredModel.pairingSession)
        restoredModel.beginPairing(routePolicy: .allowLocalDiagnostic)

        XCTAssertFalse(restoredModel.hasDevelopmentRelayRoute)
        XCTAssertNil(restoredModel.developmentRelayEndpoint)
        XCTAssertFalse(restoredModel.relayFrameEncryptionEnabled)
        XCTAssertNil(defaults.string(forKey: "aetherlink.relay.host"))
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.port"), 0)
        assertNoStoredRelaySecret(defaults: defaults, store: relaySecretStore)
        let clearedQueryItems = try queryItems(from: try XCTUnwrap(restoredModel.pairingSession).qrPayload)
        XCTAssertNil(clearedQueryItems["relay_host"])
        XCTAssertNil(clearedQueryItems["relay_port"])
        XCTAssertNil(clearedQueryItems["relay_id"])
        XCTAssertNil(clearedQueryItems["relay_secret"])
        XCTAssertNil(clearedQueryItems["relay_expires_at"])
        XCTAssertNil(clearedQueryItems["relay_nonce"])
        XCTAssertEqual(clearedQueryItems["host"], "192.168.1.44")
        XCTAssertEqual(clearedQueryItems["port"], "43211")
    }

    @MainActor
    func testCompanionAppModelGeneratesRelaySecretWhenSavingBlankSecret() throws {
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            userDefaults: try isolatedDefaults()
        )

        model.configureDevelopmentRelay(host: "relay.example.test", port: 43171, relaySecret: "")

        XCTAssertTrue(model.relayFrameEncryptionEnabled)
        XCTAssertFalse(model.developmentRelaySettings.relaySecret?.isEmpty ?? true)
    }

    @MainActor
    func testCompanionAppModelAllocatesRelayWhenSavingRelayWithAllocationAttempt() throws {
        let defaults = try isolatedDefaults()
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let lease = CompanionRemoteRouteLease(
            expiresAtEpochMillis: 4_102_444_800_000,
            nonce: "allocated-nonce"
        )
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.example.test",
                    port: 443,
                    relayID: "allocated-relay",
                    relaySecret: "allocated-secret"
                ),
                lease: lease
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: defaults,
            relaySecretStore: relaySecretStore
        )

        let result = model.configureDevelopmentRelay(
            host: " relay.example.test ",
            port: 443,
            relaySecret: "preferred-secret",
            attemptAllocation: true
        )

        XCTAssertEqual(result, .allocated(endpoint: "relay.example.test:443"))
        XCTAssertEqual(serviceAllocator.calls.count, 1)
        XCTAssertEqual(serviceAllocator.calls.first?.host, "relay.example.test")
        XCTAssertEqual(serviceAllocator.calls.first?.port, 443)
        XCTAssertEqual(serviceAllocator.calls.first?.relaySecret, "preferred-secret")
        XCTAssertFalse(serviceAllocator.calls.first?.routeToken.isEmpty ?? true)
        XCTAssertEqual(model.developmentRelaySettings.host, "relay.example.test")
        XCTAssertEqual(model.developmentRelaySettings.port, 443)
        XCTAssertEqual(model.developmentRelaySettings.relayID, "allocated-relay")
        XCTAssertEqual(model.developmentRelaySettings.relaySecret, "allocated-secret")
        XCTAssertEqual(model.developmentRelayEndpoint, "relay.example.test:443")
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.id"), "allocated-relay")
        assertStoredRelaySecret("allocated-secret", defaults: defaults, store: relaySecretStore)
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.lease_expires_at"), Int(lease.expiresAtEpochMillis))
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.lease_nonce"), "allocated-nonce")
    }

    @MainActor
    func testCompanionAppModelSavesBootstrapRelaySettingsAndAllocatesRoute() throws {
        let defaults = try isolatedDefaults()
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay-bootstrap-saved.test",
                    port: 443,
                    relayID: "saved-bootstrap-relay",
                    relaySecret: "saved-bootstrap-secret"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "saved-bootstrap-nonce"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayServiceRouteAllocator: serviceAllocator,
            environment: [:],
            userDefaults: defaults,
            relaySecretStore: relaySecretStore
        )

        let result = model.configureBootstrapRelay(
            endpoints: " relay-bootstrap-saved.test:443 ",
            allocationToken: " stored-bootstrap-token ",
            allowsPrivateOverlay: true
        )

        XCTAssertEqual(result, .allocated(endpoint: "relay-bootstrap-saved.test:443"))
        XCTAssertTrue(model.bootstrapRelaySettings.isEnabled)
        XCTAssertEqual(model.bootstrapRelaySettings.endpoints, "relay-bootstrap-saved.test:443")
        XCTAssertEqual(model.bootstrapRelaySettings.allocationToken, "stored-bootstrap-token")
        XCTAssertTrue(model.bootstrapRelaySettings.allowsPrivateOverlay)
        XCTAssertEqual(defaults.string(forKey: "aetherlink.bootstrap_relay.endpoints"), "relay-bootstrap-saved.test:443")
        assertStoredBootstrapAllocationToken("stored-bootstrap-token", defaults: defaults, store: relaySecretStore)
        XCTAssertTrue(defaults.bool(forKey: "aetherlink.bootstrap_relay.allows_private_overlay"))
        XCTAssertEqual(serviceAllocator.calls.first?.host, "relay-bootstrap-saved.test")
        XCTAssertEqual(serviceAllocator.calls.first?.port, 443)
        XCTAssertEqual(serviceAllocator.calls.first?.allocationToken, "stored-bootstrap-token")
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.id"), "saved-bootstrap-relay")
        assertStoredRelaySecret("saved-bootstrap-secret", defaults: defaults, store: relaySecretStore)
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.lease_expires_at"), 4_102_444_800_000)
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.lease_nonce"), "saved-bootstrap-nonce")
    }

    @MainActor
    func testCompanionAppModelKeepsSavedRelayWhenAllocationAttemptFails() throws {
        let defaults = try isolatedDefaults()
        let serviceAllocator = FakeRelayServiceRouteAllocator(allocation: nil)
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: defaults
        )

        let result = model.configureDevelopmentRelay(
            host: "relay.example.test",
            port: 43171,
            relaySecret: "preferred-secret",
            attemptAllocation: true
        )

        if case .allocationFailed(let endpoint, let message) = result {
            XCTAssertEqual(endpoint, "relay.example.test:43171")
            XCTAssertFalse(message.isEmpty)
        } else {
            XCTFail("Expected allocation failure, got \(result)")
        }
        XCTAssertEqual(serviceAllocator.calls.count, 1)
        XCTAssertEqual(model.developmentRelaySettings.host, "relay.example.test")
        XCTAssertEqual(model.developmentRelaySettings.relaySecret, "preferred-secret")
        XCTAssertEqual(model.developmentRelaySettings.relayID, defaults.string(forKey: "aetherlink.discovery_route_token"))
        XCTAssertNil(defaults.string(forKey: "aetherlink.relay.lease_nonce"))
    }

    @MainActor
    func testCompanionAppModelRetriesGUIRelayAllocationWhenGeneratingQRCodeWithoutLease() async throws {
        let defaults = try isolatedDefaults()
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocations: [
                nil,
                CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: "relay.example.test",
                        port: 43171,
                        relayID: "allocated-relay-retry",
                        relaySecret: "allocated-secret-retry"
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: 4_102_444_800_000,
                        nonce: "allocated-nonce-retry"
                    )
                )
            ]
        )
        let relayClient = FakeRelayPeerClient()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: defaults,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        let result = model.configureDevelopmentRelay(
            host: "relay.example.test",
            port: 43171,
            relaySecret: "preferred-secret",
            attemptAllocation: true
        )
        XCTAssertTrue({
            if case .allocationFailed = result { return true }
            return false
        }())
        XCTAssertFalse(model.isDevelopmentRelayRoutePreparedForQRCode)

        model.beginPairing()
        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(serviceAllocator.calls.count, 2)
        XCTAssertEqual(serviceAllocator.calls.last?.host, "relay.example.test")
        XCTAssertEqual(serviceAllocator.calls.last?.relaySecret, "preferred-secret")
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "allocated-relay-retry")
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "allocated-nonce-retry")

        relayClient.emit(.waitingForPeer)
        await Task.yield()

        let qrItems = try queryItems(from: try XCTUnwrap(model.pairingSession).qrPayload)
        XCTAssertEqual(qrItems["relay_host"], "relay.example.test")
        XCTAssertEqual(qrItems["relay_port"], "43171")
        XCTAssertEqual(qrItems["relay_id"], "allocated-relay-retry")
        XCTAssertEqual(qrItems["relay_secret"], "allocated-secret-retry")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "allocated-nonce-retry")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
    }

    func testDevelopmentRelaySettingsClassifiesHostsThatCannotCrossNetworks() {
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "https://relay.example.test"),
            .invalidFormat
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "relay.example.test:43171"),
            .invalidFormat
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "user@relay.example.test"),
            .invalidFormat
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "127.0.0.1"),
            .loopback
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "localhost"),
            .loopback
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "192.168.1.10"),
            .privateNetwork
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "10.0.0.20"),
            .privateNetwork
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "100.64.1.10"),
            .privateNetwork
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "169.254.10.20"),
            .privateNetwork
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "172.20.1.10"),
            .privateNetwork
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "[fe80::1]"),
            .privateNetwork
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "[fd00::1]"),
            .privateNetwork
        )
        XCTAssertEqual(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "runtime.local"),
            .localName
        )
        XCTAssertNil(
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: "relay.example.test")
        )
    }

    @MainActor
    func testCompanionAppModelBlocksInvalidRelayHostFormatForRemoteQRCode() async throws {
        let relayClient = FakeRelayPeerClient()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        let result = model.configureDevelopmentRelay(
            host: "relay.example.test:43171",
            port: 43171,
            relaySecret: "secret-1"
        )
        model.start(port: 43210)
        relayClient.emit(.waitingForPeer)
        await Task.yield()

        if case .allocationFailed(let endpoint, let message) = result {
            XCTAssertEqual(endpoint, "relay.example.test:43171")
            XCTAssertTrue(message.contains("Connection address must not include"))
        } else {
            XCTFail("Expected invalid connection address rejection, got \(result)")
        }
        XCTAssertFalse(model.developmentRelaySettings.isEnabled)
        XCTAssertNil(relayClient.startedConfiguration)
        XCTAssertFalse(model.isDevelopmentRelayRouteEligibleForQRCode)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertTrue(model.logs.contains(
            "Remote route configuration rejected: Connection address must not include a scheme, path, user info, query, fragment, or port."
        ))
    }

    @MainActor
    func testCompanionAppModelWaitsForLeaseBeforeUsingCGNATPrivateOverlayRelayQRCode() async throws {
        let relayClient = FakeRelayPeerClient()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.configureDevelopmentRelay(
            host: "100.64.1.10",
            port: 43171,
            relaySecret: "secret-1",
            allowsPrivateOverlay: true
        )
        model.start(port: 43210)
        relayClient.emit(.waitingForPeer)
        await Task.yield()

        XCTAssertEqual(model.developmentRelaySettings.hostReachabilityWarning, .privateNetwork)
        XCTAssertTrue(model.developmentRelaySettings.allowsPrivateOverlay)
        XCTAssertTrue(model.isDevelopmentRelayRouteEligibleForQRCode)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertTrue(model.logs.contains(
            "Remote pairing QR not generated: remote route 100.64.1.10:43171 is not ready"
        ))
    }

    @MainActor
    func testCompanionAppModelPublishesRelayConnectionStatus() async throws {
        let relayClient = FakeRelayPeerClient()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            userDefaults: try isolatedDefaults()
        )

        model.configureDevelopmentRelay(host: "relay.example.test", port: 43171, relaySecret: "secret-1")
        model.start(port: 43210)

        XCTAssertEqual(relayClient.startedConfiguration?.host, "relay.example.test")
        XCTAssertEqual(relayClient.startedConfiguration?.port, 43171)
        XCTAssertEqual(model.developmentRelayConnectionStatus.status, .stopped)
        XCTAssertEqual(model.developmentRelayConnectionStatus.endpoint, "relay.example.test:43171")
        XCTAssertTrue(model.transportStatus.contains("relay configured relay.example.test:43171"))
        XCTAssertTrue(model.isDevelopmentRelayRouteEligibleForQRCode)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        relayClient.emit(.connecting)
        await Task.yield()
        XCTAssertEqual(model.developmentRelayConnectionStatus.status, .connecting)
        XCTAssertEqual(model.developmentRelayConnectionStatus.endpoint, "relay.example.test:43171")
        XCTAssertTrue(model.transportStatus.contains("relay connecting relay.example.test:43171"))
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        relayClient.emit(.waitingForPeer)
        await Task.yield()
        XCTAssertEqual(model.developmentRelayConnectionStatus.status, .waitingForPeer)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        relayClient.emit(.ready)
        await Task.yield()
        XCTAssertEqual(model.developmentRelayConnectionStatus.status, .ready)
        XCTAssertTrue(model.transportStatus.contains("relay ready relay.example.test:43171"))
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        relayClient.emit(.failed("Connection refused"))
        await Task.yield()
        XCTAssertEqual(model.developmentRelayConnectionStatus.status, .failed("Connection refused"))
        XCTAssertTrue(model.transportStatus.contains("relay failed relay.example.test:43171: Connection refused"))
        XCTAssertEqual(model.remoteRoutePreparationIssue?.kind, .relayConnectionFailed)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.endpoint, "relay.example.test:43171")
        XCTAssertEqual(model.remoteRoutePreparationIssue?.message, "Connection refused")
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)
    }

    @MainActor
    func testCompanionAppModelKeepsLeasePreparationIssueWhenRelayIsReadyWithoutLease() async throws {
        let relayClient = FakeRelayPeerClient()
        let serviceAllocator = FakeRelayServiceRouteAllocator(allocation: nil)
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: try isolatedDefaults()
        )

        model.configureDevelopmentRelay(host: "relay.example.test", port: 43171, relaySecret: "secret-1")
        model.start(port: 43210)
        relayClient.emit(.waitingForPeer)
        await Task.yield()

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(serviceAllocator.calls.count, 1)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.kind, .routeLeaseRefreshFailed)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.endpoint, "relay.example.test:43171")
        XCTAssertEqual(model.remoteRoutePreparationIssue?.message, "Remote route allocation response was invalid.")
        XCTAssertFalse(model.isDevelopmentRelayRoutePreparedForQRCode)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)
        XCTAssertTrue(model.logs.contains(
            "Remote pairing QR not generated: Remote route allocation response was invalid."
        ))

        relayClient.emit(.ready)
        await Task.yield()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.kind, .routeLeaseRefreshFailed)
        XCTAssertTrue(model.logs.contains("Remote route ready: relay.example.test:43171"))
    }

    @MainActor
    func testCompanionAppModelRequiresRemoteQRCodeForLoopbackSavedRelayHost() async throws {
        let relayClient = FakeRelayPeerClient()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.configureDevelopmentRelay(host: "127.0.0.1", port: 43171, relaySecret: "secret-1")
        model.start(port: 43210)
        relayClient.emit(.waitingForPeer)
        await Task.yield()

        XCTAssertEqual(model.developmentRelaySettings.hostReachabilityWarning, .loopback)
        XCTAssertFalse(model.developmentRelaySettings.isEnvironmentOverride)
        XCTAssertEqual(model.developmentRelayConnectionStatus.status, .waitingForPeer)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)
        XCTAssertFalse(model.shouldIncludeDevelopmentRelayInPairingQRCode)

        model.beginPairing()
        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(
            model.logs.first,
            "Remote pairing QR not generated: remote route 127.0.0.1:43171 cannot be included in QR"
        )

        model.beginPairing(routePolicy: .allowLocalDiagnostic)
        let queryItems = try queryItems(from: try XCTUnwrap(model.pairingSession).qrPayload)
        XCTAssertNil(queryItems["relay_host"])
        XCTAssertNil(queryItems["relay_port"])
        XCTAssertNil(queryItems["relay_id"])
        XCTAssertNil(queryItems["relay_secret"])
        XCTAssertEqual(queryItems["host"], "192.168.1.44")
        XCTAssertEqual(queryItems["port"], "43210")
    }

    @MainActor
    func testCompanionAppModelBlocksPrivateRelayHostWithoutExplicitOverlayOptIn() async throws {
        let relayClient = FakeRelayPeerClient()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.configureDevelopmentRelay(host: "192.168.50.10", port: 43171, relaySecret: "secret-1")
        model.start(port: 43210)

        XCTAssertEqual(model.developmentRelaySettings.hostReachabilityWarning, .privateNetwork)
        XCTAssertFalse(model.developmentRelaySettings.allowsPrivateOverlay)
        XCTAssertEqual(model.developmentRelayConnectionStatus.status, .stopped)
        XCTAssertFalse(model.isDevelopmentRelayRouteEligibleForQRCode)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)
        XCTAssertFalse(model.shouldIncludeDevelopmentRelayInPairingQRCode)

        model.beginPairing()
        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(
            model.logs.first,
            "Remote pairing QR not generated: remote route 192.168.50.10:43171 cannot be included in QR"
        )

        relayClient.emit(.waitingForPeer)
        await Task.yield()

        XCTAssertNil(model.pairingSession)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        model.beginPairing(routePolicy: .allowLocalDiagnostic)
        let queryItems = try queryItems(from: try XCTUnwrap(model.pairingSession).qrPayload)
        XCTAssertNil(queryItems["relay_host"])
        XCTAssertNil(queryItems["relay_port"])
        XCTAssertNil(queryItems["relay_secret"])
        XCTAssertNil(queryItems["relay_id"])
        XCTAssertEqual(queryItems["host"], "192.168.1.44")
        XCTAssertEqual(queryItems["port"], "43210")
    }

    @MainActor
    func testCompanionAppModelRejectsPrivateOverlayRemoteRouteAllocationWithoutExplicitOptIn() async throws {
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "192.168.50.10",
                    port: 43171,
                    relayID: "relay-private",
                    relaySecret: "secret-private"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "allocated-private-nonce"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertNil(relayClient.startedConfiguration)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.kind, .automaticPreparationRejected)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.endpoint, "192.168.50.10:43171")

        relayClient.emit(.waitingForPeer)
        await Task.yield()

        XCTAssertNil(model.pairingSession)
    }

    @MainActor
    func testCompanionAppModelAllowsPrivateOverlayRemoteRouteAllocationWithExplicitEnvironmentOptIn() async throws {
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "192.168.50.10",
                    port: 43171,
                    relayID: "relay-private",
                    relaySecret: "secret-private"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "allocated-private-nonce"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_ALLOW_PRIVATE_OVERLAY": "1"
            ],
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(relayClient.startedConfiguration?.host, "192.168.50.10")
        XCTAssertNil(model.remoteRoutePreparationIssue)

        relayClient.emit(.waitingForPeer)
        await Task.yield()

        let queryItems = try queryItems(from: try XCTUnwrap(model.pairingSession).qrPayload)
        XCTAssertEqual(queryItems["relay_host"], "192.168.50.10")
        XCTAssertEqual(queryItems["relay_port"], "43171")
        XCTAssertEqual(queryItems["relay_id"], "relay-private")
        XCTAssertEqual(queryItems["relay_secret"], "secret-private")
        XCTAssertEqual(queryItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(queryItems["relay_nonce"], "allocated-private-nonce")
        XCTAssertEqual(queryItems["relay_scope"], "private_overlay")
        XCTAssertNil(queryItems["host"])
        XCTAssertNil(queryItems["port"])
    }

    @MainActor
    func testCompanionAppModelAllowsEnvironmentPrivateOverlayRelayButWaitsForLease() async throws {
        let relayClient = FakeRelayPeerClient()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            environment: [
                "AETHERLINK_RELAY_HOST": "192.168.50.10",
                "AETHERLINK_RELAY_PORT": "43171",
                "AETHERLINK_RELAY_ID": "relay-private",
                "AETHERLINK_RELAY_SECRET": "secret-private",
                "AETHERLINK_RELAY_ALLOW_PRIVATE_OVERLAY": "1"
            ],
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        XCTAssertTrue(model.developmentRelaySettings.isEnvironmentOverride)
        XCTAssertEqual(model.developmentRelaySettings.hostReachabilityWarning, .privateNetwork)
        XCTAssertTrue(model.developmentRelaySettings.allowsPrivateOverlay)
        XCTAssertTrue(model.isDevelopmentRelayRouteEligibleForQRCode)

        model.start(port: 43210)
        relayClient.emit(.waitingForPeer)
        await Task.yield()

        XCTAssertEqual(relayClient.startedConfiguration?.host, "192.168.50.10")
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)
        XCTAssertFalse(model.shouldIncludeDevelopmentRelayInPairingQRCode)

        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertTrue(model.logs.contains(
            "Remote pairing QR not generated: remote route 192.168.50.10:43171 is not ready"
        ))
    }

    @MainActor
    func testCompanionAppModelPersistsBootstrapAllocationLeaseForRestoredQRCode() async throws {
        let defaults = try isolatedDefaults()
        defaults.set("route-token-bootstrap", forKey: "aetherlink.discovery_route_token")
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let allocation = CompanionRemoteRelayRouteAllocation(
            configuration: RelayPeerConfiguration(
                host: "relay.example.test",
                port: 443,
                relayID: "route-token-bootstrap",
                relaySecret: "allocated-secret-1"
            ),
            lease: CompanionRemoteRouteLease(
                expiresAtEpochMillis: 4_102_444_800_000,
                nonce: "allocated-nonce-1"
            )
        )
        let allocator = FakeRemoteRelayRouteAllocator(allocation: allocation)
        let relayClient = FakeRelayPeerClient()
        let environment = [
            "AETHERLINK_BOOTSTRAP_RELAY_HOST": "relay.example.test",
            "AETHERLINK_BOOTSTRAP_RELAY_PORT": "443"
        ]
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            environment: environment,
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing()
        relayClient.emit(.waitingForPeer)
        await Task.yield()

        let qrItems = try queryItems(from: try XCTUnwrap(model.pairingSession).qrPayload)
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "allocated-nonce-1")
        XCTAssertEqual(qrItems["relay_host"], "relay.example.test")
        XCTAssertEqual(qrItems["relay_port"], "443")
        XCTAssertEqual(qrItems["relay_id"], qrItems["route_token"])
        XCTAssertEqual(qrItems["relay_secret"], "allocated-secret-1")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "allocated-nonce-1")
        XCTAssertEqual(qrItems["relay_scope"], "remote")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
        assertStoredRelaySecret("allocated-secret-1", defaults: defaults, store: relaySecretStore)
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.lease_expires_at"), 4_102_444_800_000)
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.lease_nonce"), "allocated-nonce-1")

        let restoredRelayClient = FakeRelayPeerClient()
        let restoredModel = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: restoredRelayClient,
            remoteRelayRouteAllocator: FakeRemoteRelayRouteAllocator(allocation: nil),
            environment: environment,
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        restoredModel.beginPairing()
        restoredRelayClient.emit(.waitingForPeer)
        await Task.yield()

        let restoredQRItems = try queryItems(from: try XCTUnwrap(restoredModel.pairingSession).qrPayload)
        XCTAssertEqual(restoredRelayClient.startedConfiguration?.relayNonce, "allocated-nonce-1")
        XCTAssertEqual(restoredQRItems["relay_host"], "relay.example.test")
        XCTAssertEqual(restoredQRItems["relay_secret"], "allocated-secret-1")
        XCTAssertEqual(restoredQRItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(restoredQRItems["relay_nonce"], "allocated-nonce-1")
        XCTAssertNil(restoredQRItems["host"])
        XCTAssertNil(restoredQRItems["port"])
    }

    @MainActor
    func testCompanionAppModelRegeneratesBootstrapQRCodeWithExpiredSavedLease() async throws {
        let defaults = try isolatedDefaults()
        defaults.set("route-token-bootstrap", forKey: "aetherlink.discovery_route_token")
        defaults.set("allocated-secret-1", forKey: "aetherlink.relay.secret")
        defaults.set(1_000, forKey: "aetherlink.relay.lease_expires_at")
        defaults.set("expired-nonce-1", forKey: "aetherlink.relay.lease_nonce")
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.example.test",
                    port: 443,
                    relayID: "route-token-bootstrap",
                    relaySecret: "allocated-secret-2"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "allocated-nonce-2"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            remoteRelayRouteAllocator: allocator,
            environment: [
                "AETHERLINK_BOOTSTRAP_RELAY_HOST": "relay.example.test",
                "AETHERLINK_BOOTSTRAP_RELAY_PORT": "443"
            ],
            userDefaults: defaults,
            relaySecretStore: relaySecretStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.beginPairing()
        relayClient.emit(.waitingForPeer)
        await Task.yield()

        let qrItems = try queryItems(from: try XCTUnwrap(model.pairingSession).qrPayload)
        XCTAssertEqual(qrItems["relay_host"], "relay.example.test")
        XCTAssertEqual(qrItems["relay_port"], "443")
        XCTAssertEqual(qrItems["relay_id"], "route-token-bootstrap")
        XCTAssertEqual(qrItems["relay_secret"], "allocated-secret-2")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "allocated-nonce-2")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
        XCTAssertEqual(allocator.calls.count, 2)
        XCTAssertEqual(allocator.calls.first?.preferredRelaySecret, "allocated-secret-1")
        XCTAssertEqual(allocator.calls.last?.preferredRelaySecret, "allocated-secret-2")
        assertStoredRelaySecret("allocated-secret-2", defaults: defaults, store: relaySecretStore)
    }

    @MainActor
    func testCompanionAppModelRegeneratesGUIAllocatedQRCodeWithExpiredLease() async throws {
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocations: [
                CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: "relay.example.test",
                        port: 443,
                        relayID: "allocated-relay-expired",
                        relaySecret: "allocated-secret"
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: 1_000,
                        nonce: "expired-nonce"
                    )
                ),
                CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: "relay.example.test",
                        port: 443,
                        relayID: "allocated-relay-fresh",
                        relaySecret: "allocated-secret-fresh"
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: 4_102_444_800_000,
                        nonce: "fresh-nonce"
                    )
                )
            ]
        )
        let relayClient = FakeRelayPeerClient()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        let result = model.configureDevelopmentRelay(
            host: "relay.example.test",
            port: 443,
            relaySecret: "preferred-secret",
            attemptAllocation: true
        )
        XCTAssertEqual(result, .allocated(endpoint: "relay.example.test:443"))
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)

        model.beginPairing()
        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "allocated-relay-fresh")
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "fresh-nonce")
        relayClient.emit(.waitingForPeer)
        await Task.yield()

        let qrItems = try queryItems(from: try XCTUnwrap(model.pairingSession).qrPayload)
        XCTAssertEqual(qrItems["relay_host"], "relay.example.test")
        XCTAssertEqual(qrItems["relay_port"], "443")
        XCTAssertEqual(qrItems["relay_id"], "allocated-relay-fresh")
        XCTAssertEqual(qrItems["relay_secret"], "allocated-secret-fresh")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "fresh-nonce")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
        XCTAssertEqual(serviceAllocator.calls.count, 2)
    }

    @MainActor
    func testCompanionAppModelRefreshRuntimeRouteReturnsNilWithoutFreshRelayLease() async throws {
        let serviceAllocator = FakeRelayServiceRouteAllocator(allocation: nil)
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        let result = model.configureDevelopmentRelay(
            host: "relay.example.test",
            port: 443,
            relaySecret: "preferred-secret"
        )
        XCTAssertEqual(result, .savedStatic(endpoint: "relay.example.test:443"))

        let refresh = try await model.refreshRuntimeRoute()

        XCTAssertNil(refresh)
        XCTAssertEqual(serviceAllocator.calls.count, 1)
        XCTAssertEqual(serviceAllocator.calls.first?.host, "relay.example.test")
        XCTAssertEqual(serviceAllocator.calls.first?.port, 443)
        XCTAssertEqual(serviceAllocator.calls.first?.relaySecret, "preferred-secret")
        XCTAssertEqual(model.remoteRoutePreparationIssue?.kind, .routeLeaseRefreshFailed)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.endpoint, "relay.example.test:443")
    }

    @MainActor
    func testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial() async throws {
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.example.test",
                    port: 443,
                    relayID: "allocated-refresh-relay",
                    relaySecret: "allocated-refresh-secret"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "allocated-refresh-nonce"
                )
            )
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: try isolatedDefaults(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        let result = model.configureDevelopmentRelay(
            host: "relay.example.test",
            port: 443,
            relaySecret: "preferred-secret"
        )
        XCTAssertEqual(result, .savedStatic(endpoint: "relay.example.test:443"))

        let refreshResult = try await model.refreshRuntimeRoute()
        let refresh = try XCTUnwrap(refreshResult)

        XCTAssertEqual(serviceAllocator.calls.count, 1)
        XCTAssertEqual(serviceAllocator.calls.first?.host, "relay.example.test")
        XCTAssertEqual(serviceAllocator.calls.first?.port, 443)
        XCTAssertEqual(serviceAllocator.calls.first?.relaySecret, "preferred-secret")
        XCTAssertEqual(refresh.relayHost, "relay.example.test")
        XCTAssertEqual(refresh.relayPort, 443)
        XCTAssertEqual(refresh.relayID, "allocated-refresh-relay")
        XCTAssertEqual(refresh.relaySecret, "allocated-refresh-secret")
        XCTAssertEqual(refresh.relayExpiresAtEpochMillis, 4_102_444_800_000)
        XCTAssertEqual(refresh.relayNonce, "allocated-refresh-nonce")
        XCTAssertEqual(refresh.relayScope, "remote")
        XCTAssertTrue(model.isDevelopmentRelayRoutePreparedForQRCode)
    }

    @MainActor
    func testCompanionAppModelStopsRelayClientWhenRelayIsCleared() async throws {
        let relayClient = FakeRelayPeerClient()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            userDefaults: try isolatedDefaults()
        )

        model.configureDevelopmentRelay(host: "relay.example.test", port: 43171, relaySecret: "secret-1")
        model.start(port: 43210)
        relayClient.emit(.ready)
        await Task.yield()

        model.clearDevelopmentRelay()
        await Task.yield()

        XCTAssertTrue(relayClient.didStop)
        XCTAssertEqual(model.developmentRelayConnectionStatus.status, .stopped)
        XCTAssertNil(model.developmentRelayConnectionStatus.endpoint)
        XCTAssertFalse(model.hasDevelopmentRelayRoute)
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
        XCTAssertEqual(advertiser.startedMetadata?.version, "1")
        XCTAssertEqual(advertiser.startedMetadata?.app, "AetherLink")
        XCTAssertFalse(advertiser.startedMetadata?.routeToken?.isEmpty ?? true)
        XCTAssertFalse(advertiser.startedMetadata?.deviceID?.isEmpty ?? true)
        XCTAssertFalse(advertiser.startedMetadata?.fingerprint?.isEmpty ?? true)
        XCTAssertEqual(model.transportState.state, .advertising)
        XCTAssertEqual(model.transportState.serviceName, "_aetherlink._tcp.local.")
        XCTAssertEqual(model.transportState.port, 43210)
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
        XCTAssertEqual(model.transportState, .stopped)
        XCTAssertEqual(model.transportStatus, "Stopped")
    }

    @MainActor
    func testCompanionAppModelReportsFailedTransportWithoutAdvertising() async throws {
        let transport = FakeRuntimeTransport(statusAfterStart: .failed("Port is already in use."))
        let advertiser = FakeRuntimeAdvertiser()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: transport,
            advertiser: advertiser
        )

        model.start(port: 43210)

        XCTAssertEqual(transport.startedPort, 43210)
        XCTAssertNil(advertiser.startedPort)
        XCTAssertTrue(advertiser.didStop)
        XCTAssertEqual(model.transportState.state, .failed)
        XCTAssertEqual(model.transportState.failureMessage, "Port is already in use.")
        XCTAssertTrue(model.transportStatus.contains("Port is already in use."))
    }

    @MainActor
    func testCompanionAppModelPublishesStructuredBackendProviderStatuses() async throws {
        let backend = AggregatingLlmBackend([
            MockBackend(provider: .ollama, status: .available),
            MockBackend(provider: .lmStudio, status: .unavailable(BackendError(
                provider: .lmStudio,
                code: "backend_unavailable",
                message: "LM Studio is not reachable through AetherLink Runtime.",
                retryable: true
            )))
        ])
        let model = CompanionAppModel(
            backend: backend,
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser()
        )

        await model.refreshBackendStatus()

        let statusesByProvider = Dictionary(uniqueKeysWithValues: model.providerStatuses.map { ($0.provider, $0) })
        XCTAssertEqual(statusesByProvider[.ollama]?.availability, .available)
        XCTAssertEqual(statusesByProvider[.lmStudio]?.availability, .unavailable)
        XCTAssertEqual(statusesByProvider[.lmStudio]?.code, "backend_unavailable")
        XCTAssertEqual(statusesByProvider[.lmStudio]?.retryable, true)
        XCTAssertTrue(model.backendStatus.contains("Ollama available"))
        XCTAssertTrue(model.backendStatus.contains("LM Studio unavailable"))
    }
}

private func makeRouter(
    backend: any LlmBackend,
    requiresAuthentication: Bool = false,
    trustedDeviceStore: TrustedDeviceStore = TrustedDeviceStore(
        fileURL: FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("trusted-devices.json")
    ),
    chatEventStore: any RuntimeChatEventStore = NullRuntimeChatEventStore(),
    memoryStore: any RuntimeMemoryStore = NullRuntimeMemoryStore(),
    routeRefresher: (any RuntimeRouteRefreshing)? = nil,
    runtimeChallengeSigner: (any RuntimeChallengeSigning)? = nil
) -> LocalRuntimeMessageRouter {
    LocalRuntimeMessageRouter(
        backend: backend,
        requiresAuthentication: requiresAuthentication,
        trustedDeviceStore: trustedDeviceStore,
        chatEventStore: chatEventStore,
        memoryStore: memoryStore,
        routeRefresher: routeRefresher,
        runtimeChallengeSigner: runtimeChallengeSigner
    )
}

private func appendRawChatEventLogLine(_ line: String, to fileURL: URL) throws {
    let handle = try FileHandle(forWritingTo: fileURL)
    defer { try? handle.close() }
    try handle.seekToEnd()
    try handle.write(contentsOf: Data((line + "\n").utf8))
}

@MainActor
private final class FakeRuntimeRouteRefresher: RuntimeRouteRefreshing {
    private let result: RuntimeRouteRefreshResult?
    private let error: (any Error)?
    private(set) var refreshCount = 0

    init(result: RuntimeRouteRefreshResult?) {
        self.result = result
        self.error = nil
    }

    init(error: any Error) {
        self.result = nil
        self.error = error
    }

    func refreshRuntimeRoute() async throws -> RuntimeRouteRefreshResult? {
        refreshCount += 1
        if let error {
            throw error
        }
        return result
    }
}

private struct RuntimeRouteRefreshTestError: Error, LocalizedError {
    var message: String

    var errorDescription: String? {
        message
    }
}

private struct TestRuntimeChallengeSigner: RuntimeChallengeSigning {
    var privateKey: P256.Signing.PrivateKey

    func signAuthChallenge(deviceID: String, nonce: String) throws -> RuntimeChallengeSignature {
        let identity = RuntimeIdentityKeyStore.identityKey(from: privateKey)
        let messageData = RuntimeIdentityKeyStore.authChallengeMessageData(
            deviceID: deviceID,
            nonce: nonce
        )
        let signature = try privateKey.signature(for: SHA256.hash(data: messageData))
        return RuntimeChallengeSignature(
            runtimeKeyFingerprint: identity.fingerprint,
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
    }
}

private struct FailingRuntimeMemoryStore: RuntimeMemoryStore {
    func list() throws -> [RuntimeMemoryEntry] {
        throw NSError(
            domain: "AetherLinkTests",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "memory store read failed"]
        )
    }

    func upsert(id: String?, content: String, enabled: Bool?, timestamp: Date) throws -> RuntimeMemoryEntry {
        throw NSError(
            domain: "AetherLinkTests",
            code: 2,
            userInfo: [NSLocalizedDescriptionKey: "memory store write failed"]
        )
    }

    func delete(id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult {
        throw NSError(
            domain: "AetherLinkTests",
            code: 3,
            userInfo: [NSLocalizedDescriptionKey: "memory store delete failed"]
        )
    }
}

private final class FakeRemoteRelayRouteAllocator: CompanionRemoteRelayRouteAllocating, @unchecked Sendable {
    struct Call: Equatable {
        var runtimeDeviceID: String
        var routeToken: String
        var preferredRelaySecret: String?
    }

    var allocation: CompanionRemoteRelayRouteAllocation?
    var canAllocateRemoteRelayRoute: Bool
    var error: Error?
    private let onAllocate: (() -> Void)?
    private(set) var calls: [Call] = []

    init(
        allocation: CompanionRemoteRelayRouteAllocation?,
        canAllocateRemoteRelayRoute: Bool = false,
        error: Error? = nil,
        onAllocate: (() -> Void)? = nil
    ) {
        self.allocation = allocation
        self.canAllocateRemoteRelayRoute = canAllocateRemoteRelayRoute
        self.error = error
        self.onAllocate = onAllocate
    }

    func allocateRemoteRelayRoute(
        runtimeDeviceID: String,
        routeToken: String,
        preferredRelaySecret: String?
    ) throws -> CompanionRemoteRelayRouteAllocation? {
        calls.append(Call(
            runtimeDeviceID: runtimeDeviceID,
            routeToken: routeToken,
            preferredRelaySecret: preferredRelaySecret
        ))
        onAllocate?()
        if let error {
            throw error
        }
        return allocation
    }
}

private final class FakeRelayServiceRouteAllocator: RelayServiceRouteAllocating, @unchecked Sendable {
    struct Call: Equatable {
        var host: String
        var port: UInt16
        var routeToken: String
        var relaySecret: String?
        var allocationToken: String?
    }

    private var allocations: [CompanionRemoteRelayRouteAllocation?]
    private(set) var calls: [Call] = []

    init(allocation: CompanionRemoteRelayRouteAllocation?) {
        self.allocations = [allocation]
    }

    init(allocations: [CompanionRemoteRelayRouteAllocation?]) {
        self.allocations = allocations
    }

    func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        relaySecret: String?,
        allocationToken: String?,
        timeout: TimeInterval
    ) throws -> CompanionRemoteRelayRouteAllocation {
        calls.append(Call(
            host: host,
            port: port,
            routeToken: routeToken,
            relaySecret: relaySecret,
            allocationToken: allocationToken
        ))
        let allocation = allocations.isEmpty ? nil : allocations.removeFirst()
        guard let allocation else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }
        return allocation
    }
}

private final class FakeCompanionRelaySecretStore: CompanionRelaySecretStoring, @unchecked Sendable {
    private(set) var secrets: [String: String] = [:]

    func saveSecret(_ secret: String, for handle: String) {
        secrets[handle] = secret
    }

    func readSecret(for handle: String) -> String? {
        secrets[handle]
    }

    func removeSecret(for handle: String) {
        secrets.removeValue(forKey: handle)
    }
}

private func assertStoredRelaySecret(
    _ expected: String,
    defaults: UserDefaults,
    store: FakeCompanionRelaySecretStore? = nil,
    file: StaticString = #filePath,
    line: UInt = #line
) {
    XCTAssertNil(defaults.string(forKey: "aetherlink.relay.secret"), file: file, line: line)
    let secretRef = defaults.string(forKey: "aetherlink.relay.secret_ref")
    XCTAssertFalse(secretRef?.isEmpty ?? true, file: file, line: line)
    if let secretRef, let store {
        XCTAssertEqual(store.secrets[secretRef], expected, file: file, line: line)
    }
}

private func assertNoStoredRelaySecret(
    defaults: UserDefaults,
    store: FakeCompanionRelaySecretStore? = nil,
    file: StaticString = #filePath,
    line: UInt = #line
) {
    let secretRef = defaults.string(forKey: "aetherlink.relay.secret_ref")
    XCTAssertNil(defaults.string(forKey: "aetherlink.relay.secret"), file: file, line: line)
    XCTAssertNil(secretRef, file: file, line: line)
    if let secretRef, let store {
        XCTAssertNil(store.secrets[secretRef], file: file, line: line)
    }
}

private func assertStoredBootstrapAllocationToken(
    _ expected: String,
    defaults: UserDefaults,
    store: FakeCompanionRelaySecretStore? = nil,
    file: StaticString = #filePath,
    line: UInt = #line
) {
    XCTAssertNil(defaults.string(forKey: "aetherlink.bootstrap_relay.allocation_token"), file: file, line: line)
    let tokenRef = defaults.string(forKey: "aetherlink.bootstrap_relay.allocation_token_ref")
    XCTAssertFalse(tokenRef?.isEmpty ?? true, file: file, line: line)
    if let tokenRef, let store {
        XCTAssertEqual(store.secrets[tokenRef], expected, file: file, line: line)
    }
}

private func trustedDeviceStoreURL() -> URL {
    FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString)
        .appendingPathComponent("trusted-devices.json")
}

private func isolatedDefaults() throws -> UserDefaults {
    let suiteName = "dev.aetherlink.tests.\(UUID().uuidString)"
    let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
    defaults.removePersistentDomain(forName: suiteName)
    return defaults
}

private func queryItems(from urlString: String) throws -> [String: String] {
    let components = try XCTUnwrap(URLComponents(string: urlString))
    return try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
        result[item.name] = item.value
    }
}

private func compactPairingPayload(
    _ urlString: String,
    overriding overrides: [String: String]
) throws -> String {
    var components = try XCTUnwrap(URLComponents(string: urlString))
    var queryItems = try XCTUnwrap(components.queryItems)
    queryItems = queryItems.map { item in
        URLQueryItem(name: item.name, value: overrides[item.name] ?? item.value)
    }
    components.queryItems = queryItems
    if let percentEncodedQuery = components.percentEncodedQuery {
        components.percentEncodedQuery = percentEncodedQuery.replacingOccurrences(of: "+", with: "%2B")
    }
    return try XCTUnwrap(components.string)
}

private func sharedProtocolFixture(_ name: String, filePath: String = #filePath) throws -> String {
    var current = URL(fileURLWithPath: filePath).deletingLastPathComponent()
    while true {
        let fixture = current
            .appendingPathComponent("shared")
            .appendingPathComponent("protocol")
            .appendingPathComponent("fixtures")
            .appendingPathComponent(name)
        if FileManager.default.fileExists(atPath: fixture.path) {
            return try String(contentsOf: fixture, encoding: .utf8)
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        let parent = current.deletingLastPathComponent()
        if parent.path == current.path {
            throw NSError(
                domain: "AetherLinkTests",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: "Missing shared protocol fixture: \(name)"]
            )
        }
        current = parent
    }
}

private func waitForSessionTitle(
    in store: JSONLRuntimeChatEventStore,
    sessionID: String,
    expectedTitle: String,
    timeout: TimeInterval = 1.0
) async throws -> String? {
    let deadline = Date().addingTimeInterval(timeout)
    var lastTitle: String?
    while Date() < deadline {
        lastTitle = try store
            .listSessions(limit: 20, includeArchived: true)
            .first { $0.sessionID == sessionID }?
            .title
        if lastTitle == expectedTitle {
            return lastTitle
        }
        try await Task.sleep(nanoseconds: 20_000_000)
    }
    return lastTitle
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
    private let chatEventBatchesLock = NSLock()
    private var chatEventBatches: [[ChatStreamEvent]]
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
        chatEventBatches: [[ChatStreamEvent]] = [],
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
        self.chatEventBatches = chatEventBatches
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
            nextChatEvents().forEach { continuation.yield($0) }
            continuation.finish()
        }
    }

    func cancel(generationID: String) -> GenerationCancellationResult {
        cancelResult
    }

    private func nextChatEvents() -> [ChatStreamEvent] {
        chatEventBatchesLock.withLock {
            guard !chatEventBatches.isEmpty else { return chatEvents }
            return chatEventBatches.removeFirst()
        }
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

private final class RecordingRuntimeChatEventStore: RuntimeChatEventStore, @unchecked Sendable {
    private let lock = NSLock()
    private var storedEvents: [RuntimeChatStoredEvent] = []
    private var storedSessions: [RuntimeChatStoredSession]
    private var storedMessages: [String: [RuntimeChatStoredMessage]]

    init(
        sessions: [RuntimeChatStoredSession] = [],
        messages: [String: [RuntimeChatStoredMessage]] = [:]
    ) {
        self.storedSessions = sessions
        self.storedMessages = messages
    }

    var events: [RuntimeChatStoredEvent] {
        lock.withLock { storedEvents }
    }

    func append(_ event: RuntimeChatStoredEvent) throws {
        lock.withLock {
            storedEvents.append(event)
        }
    }

    func mutateSession(
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult {
        lock.withLock {
            storedEvents.append(RuntimeChatStoredEvent(
                timestamp: timestamp,
                kind: mutation.eventKind,
                requestID: requestID,
                sessionID: sessionID,
                model: storedSessions.first { $0.sessionID == sessionID }?.model ?? ""
            ))
        }
        return RuntimeChatSessionMutationResult(sessionID: sessionID, mutation: mutation, timestamp: timestamp)
    }

    func listSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        lock.withLock { Array(storedSessions.prefix(limit)) }
    }

    func listMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        lock.withLock { Array((storedMessages[sessionID] ?? []).suffix(limit)) }
    }
}

private extension RuntimeChatSessionMutation {
    var eventKind: RuntimeChatStoredEventKind {
        switch self {
        case .archive:
            return .archived
        case .restore:
            return .restored
        case .delete:
            return .deleted
        }
    }
}

private extension ChatMessage {
    var isConversationTurnForTests: Bool {
        let normalizedRole = role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return normalizedRole == "user" || normalizedRole == "assistant"
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
    private let statusAfterStart: PeerServerStatus?
    private(set) var status = PeerServerStatus.stopped
    private(set) var startedPort: UInt16?
    private(set) var didStop = false
    private(set) var onMessage: LocalPeerMessageHandler?

    init(statusAfterStart: PeerServerStatus? = nil) {
        self.statusAfterStart = statusAfterStart
    }

    func start(port: UInt16, onMessage: @escaping LocalPeerMessageHandler) {
        startedPort = port
        self.onMessage = onMessage
        didStop = false
        status = statusAfterStart ?? .listening(port: port)
    }

    func stop() {
        didStop = true
        onMessage = nil
        status = .stopped
    }
}

private final class FakeRuntimeAdvertiser: RuntimeAdvertiser {
    private(set) var startedPort: Int32?
    private(set) var startedMetadata: RuntimeAdvertisementMetadata?
    private(set) var didStop = false

    func start(port: Int32, metadata: RuntimeAdvertisementMetadata) {
        startedPort = port
        startedMetadata = metadata
        didStop = false
    }

    func stop() {
        didStop = true
    }
}

private final class FakeRelayPeerClient: RelayPeerTransport, @unchecked Sendable {
    private(set) var startedConfiguration: RelayPeerConfiguration?
    private(set) var didStop = false
    private let onStart: (() -> Void)?
    private var statusHandler: (@Sendable (RelayPeerStatus) -> Void)?

    init(onStart: (() -> Void)? = nil) {
        self.onStart = onStart
    }

    func start(
        configuration: RelayPeerConfiguration,
        onStatusChange: (@Sendable (RelayPeerStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        onStart?()
        startedConfiguration = configuration
        statusHandler = onStatusChange
        didStop = false
    }

    func stop() {
        didStop = true
        statusHandler?(.stopped)
        statusHandler = nil
    }

    func emit(_ status: RelayPeerStatus) {
        statusHandler?(status)
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
