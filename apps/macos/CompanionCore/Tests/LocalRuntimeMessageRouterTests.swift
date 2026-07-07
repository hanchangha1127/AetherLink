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
            #"Model list failed: http://192.168.1.23:11434/api/tags model-provider.example.test:1234/v1/models route_token=route-secret relay_secret=relay-secret rs=compact-secret {"relaySecret":"json-secret","relayId":"room","relayNonce":"nonce"} allocationToken: bearer-token rrn=compact-nonce p2p_record_id=p2p-record-secret p2p_encrypted_body=p2p-body-secret p2p_anti_replay_nonce=p2p-nonce-secret pc=p2p_rendezvous prid=compact-p2p-record peb=compact-p2p-body pn=compact-p2p-nonce Remote route ready: relay.example.test:43171"#
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
        XCTAssertFalse(log.contains("json-secret"))
        XCTAssertFalse(log.contains("bearer-token"))
        XCTAssertFalse(log.contains("compact-nonce"))
        XCTAssertFalse(log.contains("p2p-record-secret"))
        XCTAssertFalse(log.contains("p2p-body-secret"))
        XCTAssertFalse(log.contains("p2p-nonce-secret"))
        XCTAssertFalse(log.contains("compact-p2p-record"))
        XCTAssertFalse(log.contains("compact-p2p-body"))
        XCTAssertFalse(log.contains("compact-p2p-nonce"))
        XCTAssertTrue(log.contains("relay.example.test:43171"))
        XCTAssertTrue(log.contains("[redacted]"))
    }

    func testRejectsBlankEnvelopeRequestIDBeforeRuntimeCommandDispatch() async throws {
        let sink = RecordingSink()
        let backend = MockBackend(status: BackendStatus.available)
        let router = makeRouter(
            backend: backend,
            requiresAuthentication: true
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "   \n\t"
        ), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "   \n\t")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: message?.payload).contains("request_id"))
        XCTAssertEqual(backend.healthCheckCallCount, 0)
    }

    func testRejectsUnsupportedEnvelopeVersionBeforeRuntimeCommandDispatch() async throws {
        let sink = RecordingSink()
        let backend = MockBackend(status: BackendStatus.available)
        let router = makeRouter(
            backend: backend,
            requiresAuthentication: true
        )

        router.handle(ProtocolEnvelope(
            version: 2,
            type: MessageType.runtimeHealth,
            requestID: "unsupported-version"
        ), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "unsupported-version")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: message?.payload).contains("version"))
        XCTAssertEqual(backend.healthCheckCallCount, 0)
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

    func testRuntimeHealthRejectsUnknownPayloadMetadataBeforeBackendDispatch() async throws {
        let sink = RecordingSink()
        let backend = MockBackend(status: BackendStatus.available)
        let router = makeRouter(backend: backend)

        router.handle(ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "health-unknown-metadata",
            payload: [
                "status": .string("ok"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "backend_credentials": .string("future-backend-token"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "health-unknown-metadata")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: message?.payload).contains("status"))
        XCTAssertTrue(String(describing: message?.payload).contains("backend_url"))
        XCTAssertEqual(backend.healthCheckCallCount, 0)
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
              case .object(let lmStudio)? = message?.payload["lm_studio"],
              case .object(let modelResidency)? = message?.payload["model_residency"] else {
            XCTFail("Expected provider health and model residency objects")
            return
        }
        XCTAssertEqual(ollama["available"], .bool(true))
        XCTAssertEqual(lmStudio["available"], .bool(false))
        XCTAssertEqual(lmStudio["code"], .string("backend_unavailable"))
        XCTAssertEqual(modelResidency["supported"], .bool(true))
        XCTAssertEqual(modelResidency["in_flight_generations"], .number(0))
        XCTAssertEqual(modelResidency["idle_unload_delay_seconds"], .number(600))
        XCTAssertNil(modelResidency["active_provider"])
        XCTAssertNil(modelResidency["active_model_id"])
        XCTAssertFalse(String(describing: message?.payload).contains("1234"))
    }

    func testRuntimeHealthIncludesModelResidencyLastUnloadFailureWithoutRawErrorMessage() async throws {
        let sink = RecordingSink()
        let backend = AggregatingLlmBackend([
            MockBackend(
                provider: .ollama,
                models: [
                    ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)
                ],
                unloadError: NSError(
                    domain: "AetherLinkResidencyTest",
                    code: 42,
                    userInfo: [
                        NSLocalizedDescriptionKey: "unload denied http://127.0.0.1:11434/api/chat route_token=secret"
                    ]
                )
            ),
            MockBackend(
                provider: .lmStudio,
                models: [
                    ModelInfo(id: "gemma-local", name: "gemma-local", provider: .lmStudio)
                ]
            )
        ])
        try await drain(backend.chat(request: chatRequest(model: "ollama:qwen-local", sessionID: "health-a")))
        try await drain(backend.chat(request: chatRequest(model: "lm_studio:gemma-local", sessionID: "health-b")))
        try await waitForResidencyFailure(on: backend)

        let router = makeRouter(backend: backend)
        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-residency-failure"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        guard case .object(let modelResidency)? = message?.payload["model_residency"],
              case .object(let failure)? = modelResidency["last_unload_failure"] else {
            XCTFail("Expected model residency last_unload_failure object")
            return
        }
        XCTAssertEqual(failure["provider"], .string("ollama"))
        XCTAssertEqual(failure["model_id"], .string("qwen-local"))
        XCTAssertEqual(failure["reason"], .string("model_switch"))
        XCTAssertNil(failure["message"])
        XCTAssertFalse(String(describing: failure).contains("127.0.0.1"))
        XCTAssertFalse(String(describing: failure).contains("route_token"))
        XCTAssertFalse(String(describing: failure).contains("unload denied"))
    }

    private func chatRequest(model: String, sessionID: String) -> ChatRequest {
        ChatRequest(
            sessionID: sessionID,
            model: model,
            messages: [ChatMessage(role: "user", content: "hello")]
        )
    }

    private func drain(_ stream: AsyncThrowingStream<ChatStreamEvent, Error>) async throws {
        for try await _ in stream {}
    }

    private func waitForResidencyFailure(on backend: AggregatingLlmBackend) async throws {
        for _ in 0..<50 {
            if backend.modelResidencySnapshot().lastUnloadFailure != nil {
                return
            }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        XCTFail("Timed out waiting for model residency unload failure")
    }

    func testModelsListReturnsModelsWithoutExposingOllamaURL() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [
                ModelInfo(
                    id: "llama3.1:8b",
                    name: "llama3.1:8b",
                    sizeBytes: 4,
                    contextWindowTokens: 32768
                ),
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
        XCTAssertEqual(model["context_window_tokens"], .number(32768))
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

    func testModelsListRejectsUnknownPayloadMetadataBeforeBackendDispatch() async throws {
        let sink = RecordingSink()
        let backend = MockBackend(modelListError: OllamaBackendError.unreachable(
            endpoint: "GET /api/tags",
            baseURL: "http://127.0.0.1:11434",
            reason: "should not be called"
        ))
        let router = makeRouter(backend: backend)

        router.handle(ProtocolEnvelope(
            type: MessageType.modelsList,
            requestID: "models-unknown-metadata",
            payload: [
                "models": .array([]),
                "backend_url": .string("http://127.0.0.1:11434"),
                "backend_credentials": .string("future-backend-token"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified"),
                "model_command": .string("direct-provider-list")
            ]
        ), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "models-unknown-metadata")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: message?.payload).contains("models"))
        XCTAssertTrue(String(describing: message?.payload).contains("backend_url"))
        XCTAssertEqual(backend.listModelsCallCount, 0)
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

    func testModelsPullRejectsUnknownPayloadMetadataBeforeBackendDispatch() async throws {
        let sink = RecordingSink()
        let backend = MockBackend()
        let router = makeRouter(backend: backend)
        let envelope = ProtocolEnvelope(
            type: MessageType.modelsPull,
            requestID: "pull-metadata",
            payload: [
                "model": .string("llama3.1:8b"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant")
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "pull-metadata")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: message?.payload).contains("backend_url"))
        XCTAssertEqual(backend.pulledModelNames, [])
    }

    func testModelsPullRejectsInvalidAllowedPayloadTypesBeforeBackendDispatch() async throws {
        let cases: [(requestID: String, payload: [String: JSONValue])] = [
            (
                requestID: "pull-invalid-model-type",
                payload: ["model": .number(42)]
            ),
            (
                requestID: "pull-empty-model",
                payload: ["model": .string("")]
            ),
            (
                requestID: "pull-blank-model",
                payload: ["model": .string("   \n\t")]
            ),
            (
                requestID: "pull-invalid-backend-type",
                payload: [
                    "model": .string("llama3.1:8b"),
                    "backend": .number(1)
                ]
            ),
            (
                requestID: "pull-invalid-backend-value",
                payload: [
                    "model": .string("llama3.1:8b"),
                    "backend": .string("lm_studio")
                ]
            )
        ]

        for testCase in cases {
            let sink = RecordingSink()
            let backend = MockBackend()
            let router = makeRouter(backend: backend)

            router.handle(ProtocolEnvelope(
                type: MessageType.modelsPull,
                requestID: testCase.requestID,
                payload: testCase.payload
            ), sink: sink)

            let message = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(message?.type, MessageType.error, testCase.requestID)
            XCTAssertEqual(message?.requestID, testCase.requestID)
            XCTAssertEqual(message?.payload["code"], .string("invalid_payload"), testCase.requestID)
            XCTAssertEqual(message?.payload["retryable"], .bool(false), testCase.requestID)
            XCTAssertEqual(backend.pulledModelNames, [], testCase.requestID)
        }
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
            relayExpiresAtEpochMillis: 4_102_444_800_000,
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
        XCTAssertEqual(message?.payload["relay_expires_at"], .number(4_102_444_800_000))
        XCTAssertEqual(message?.payload["relay_nonce"], .string("relay-nonce-1"))
        XCTAssertEqual(message?.payload["relay_scope"], .string("remote"))
        XCTAssertEqual(routeRefresher.refreshCount, 1)
    }

    @MainActor
    func testRouteRefreshRejectsUnknownPayloadMetadataBeforeRuntimeProviderDispatch() async throws {
        let sink = RecordingSink()
        let routeRefresher = FakeRuntimeRouteRefresher(result: RuntimeRouteRefreshResult(
            runtimeDeviceID: "runtime-1",
            runtimeKeyFingerprint: "runtime-fingerprint",
            relayHost: "relay.example.test",
            relayPort: 43171,
            relayID: "relay-id-1",
            relaySecret: "relay-secret-1",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "relay-nonce-1",
            relayScope: "remote"
        ))
        let router = makeRouter(
            backend: MockBackend(),
            routeRefresher: routeRefresher
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.routeRefresh,
            requestID: "route-refresh-unknown-metadata",
            payload: [
                "relay_secret": .string("future-relay-secret"),
                "relay_nonce": .string("future-relay-nonce"),
                "p2p_record_id": .string("future-p2p-record"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "route-refresh-unknown-metadata")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: message?.payload).contains("relay_secret"))
        XCTAssertTrue(String(describing: message?.payload).contains("backend_url"))
        XCTAssertEqual(routeRefresher.refreshCount, 0)
    }

    @MainActor
    func testRouteRefreshReturnsFreshP2PRendezvousMaterialFromRuntimeProvider() async throws {
        let sink = RecordingSink()
        let routeRefresher = FakeRuntimeRouteRefresher(result: RuntimeRouteRefreshResult(
            runtimeDeviceID: "runtime-1",
            runtimeKeyFingerprint: "runtime-fingerprint",
            p2pRouteClass: "p2p_rendezvous",
            p2pRecordID: "p2p-record-1",
            p2pEncryptedBody: "opaque-candidate-body-1",
            p2pExpiresAtEpochMillis: 4_102_444_800_000,
            p2pAntiReplayNonce: "p2p-nonce-1",
            p2pProtocolVersion: 1
        ))
        let router = makeRouter(
            backend: MockBackend(),
            routeRefresher: routeRefresher
        )

        router.handle(ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-p2p"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.routeRefresh)
        XCTAssertEqual(message?.requestID, "route-refresh-p2p")
        XCTAssertEqual(message?.payload["runtime_device_id"], .string("runtime-1"))
        XCTAssertEqual(message?.payload["runtime_key_fingerprint"], .string("runtime-fingerprint"))
        XCTAssertEqual(message?.payload["p2p_class"], .string("p2p_rendezvous"))
        XCTAssertEqual(message?.payload["p2p_record_id"], .string("p2p-record-1"))
        XCTAssertEqual(message?.payload["p2p_encrypted_body"], .string("opaque-candidate-body-1"))
        XCTAssertEqual(message?.payload["p2p_expires_at"], .number(4_102_444_800_000))
        XCTAssertEqual(message?.payload["p2p_anti_replay_nonce"], .string("p2p-nonce-1"))
        XCTAssertEqual(message?.payload["p2p_protocol_version"], .number(1))
        XCTAssertNil(message?.payload["relay_host"])
        XCTAssertNil(message?.payload["relay_id"])
        XCTAssertEqual(routeRefresher.refreshCount, 1)
    }

    @MainActor
    func testRouteRefreshAllowsBoundedP2PEncryptedBodyLargerThanRouteValues() async throws {
        let encryptedBody = String(repeating: "p", count: 2_048)
        let sink = RecordingSink()
        let routeRefresher = FakeRuntimeRouteRefresher(result: p2pRouteRefreshResult(
            p2pEncryptedBody: encryptedBody
        ))
        let router = makeRouter(
            backend: MockBackend(),
            routeRefresher: routeRefresher
        )

        router.handle(ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-p2p-body-bound"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.routeRefresh)
        XCTAssertEqual(message?.requestID, "route-refresh-p2p-body-bound")
        XCTAssertEqual(message?.payload["p2p_encrypted_body"], .string(encryptedBody))
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
    func testRouteRefreshRejectsUnknownRelayScopeFromRuntimeProvider() async throws {
        let sink = RecordingSink()
        let routeRefresher = FakeRuntimeRouteRefresher(result: RuntimeRouteRefreshResult(
            runtimeDeviceID: "runtime-1",
            runtimeKeyFingerprint: "runtime-fingerprint",
            relayHost: "relay.example.test",
            relayPort: 43171,
            relayID: "relay-id-1",
            relaySecret: "relay-secret-1",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "relay-nonce-1",
            relayScope: "public"
        ))
        let router = makeRouter(
            backend: MockBackend(),
            routeRefresher: routeRefresher
        )

        router.handle(ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-bad-scope"), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "route-refresh-bad-scope")
        XCTAssertEqual(message?.payload["code"], .string("route_refresh_unavailable"))
        XCTAssertEqual(message?.payload["message"], .string("AetherLink Runtime could not refresh remote route material."))
        XCTAssertEqual(message?.payload["retryable"], .bool(true))
        XCTAssertNil(message?.payload["relay_scope"])
        XCTAssertEqual(routeRefresher.refreshCount, 1)
    }

    @MainActor
    func testRouteRefreshRejectsMalformedRelayMaterialFromRuntimeProvider() async throws {
        let invalidRoutes: [RuntimeRouteRefreshResult] = [
            routeRefreshResult(relayHost: "relay.example.test", relayPort: 0),
            routeRefreshResult(relayHost: "relay.example.test", relayID: ""),
            routeRefreshResult(relayHost: "relay.example.test", relayID: String(repeating: "r", count: 513)),
            routeRefreshResult(relayHost: "relay.example.test", relaySecret: ""),
            routeRefreshResult(relayHost: "relay.example.test", relaySecret: String(repeating: "s", count: 513)),
            routeRefreshResult(relayHost: "relay.example.test", relayExpiresAtEpochMillis: 1),
            routeRefreshResult(relayHost: "relay.example.test", relayNonce: ""),
            routeRefreshResult(relayHost: "relay.example.test", relayNonce: String(repeating: "n", count: 513)),
            routeRefreshResult(relayHost: "https://relay.example.test"),
            routeRefreshResult(relayHost: "relay.example.test/path"),
            routeRefreshResult(relayHost: "relay.example.test?token=x"),
            routeRefreshResult(relayHost: "relay.example.test#frag"),
            routeRefreshResult(relayHost: "user@relay.example.test"),
            routeRefreshResult(relayHost: "relay.example.test:43171"),
            routeRefreshResult(relayHost: " relay.example.test"),
            routeRefreshResult(relayHost: "relay.example.test "),
            routeRefreshResult(relayHost: "aetherlink.local"),
            routeRefreshResult(relayHost: "127.0.0.1", relayScope: "remote"),
            routeRefreshResult(relayHost: "100.64.1.10", relayScope: nil),
            routeRefreshResult(relayHost: "100.64.1.10", relayScope: "remote"),
            routeRefreshResult(runtimeDeviceID: "runtime 1", relayHost: "relay.example.test"),
            routeRefreshResult(runtimeDeviceID: String(repeating: "d", count: 513), relayHost: "relay.example.test"),
        ]

        for (index, route) in invalidRoutes.enumerated() {
            let sink = RecordingSink()
            let routeRefresher = FakeRuntimeRouteRefresher(result: route)
            let router = makeRouter(
                backend: MockBackend(),
                routeRefresher: routeRefresher
            )

            router.handle(
                ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-invalid-\(index)"),
                sink: sink
            )

            let message = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(message?.type, MessageType.error)
            XCTAssertEqual(message?.requestID, "route-refresh-invalid-\(index)")
            XCTAssertEqual(message?.payload["code"], .string("route_refresh_unavailable"))
            XCTAssertEqual(message?.payload["message"], .string("AetherLink Runtime could not refresh remote route material."))
            XCTAssertEqual(message?.payload["retryable"], .bool(true))
            XCTAssertNil(message?.payload["relay_secret"])
            XCTAssertEqual(routeRefresher.refreshCount, 1)
        }
    }

    @MainActor
    func testRouteRefreshRejectsMalformedP2PRendezvousMaterialFromRuntimeProvider() async throws {
        let invalidRoutes: [RuntimeRouteRefreshResult] = [
            p2pRouteRefreshResult(p2pRouteClass: "relay_rendezvous"),
            p2pRouteRefreshResult(p2pRecordID: ""),
            p2pRouteRefreshResult(p2pRecordID: "p2p record 1"),
            p2pRouteRefreshResult(p2pRecordID: String(repeating: "r", count: 513)),
            p2pRouteRefreshResult(p2pEncryptedBody: ""),
            p2pRouteRefreshResult(p2pEncryptedBody: "opaque body 1"),
            p2pRouteRefreshResult(p2pEncryptedBody: String(repeating: "p", count: 2_049)),
            p2pRouteRefreshResult(p2pExpiresAtEpochMillis: 1),
            p2pRouteRefreshResult(p2pAntiReplayNonce: ""),
            p2pRouteRefreshResult(p2pAntiReplayNonce: "p2p nonce 1"),
            p2pRouteRefreshResult(p2pAntiReplayNonce: String(repeating: "n", count: 513)),
            p2pRouteRefreshResult(p2pProtocolVersion: 2),
            p2pRouteRefreshResult(runtimeDeviceID: "runtime 1"),
            p2pRouteRefreshResult(runtimeKeyFingerprint: String(repeating: "f", count: 513)),
            RuntimeRouteRefreshResult(
                runtimeDeviceID: "runtime-1",
                runtimeKeyFingerprint: "runtime-fingerprint",
                p2pRouteClass: "p2p_rendezvous",
                p2pRecordID: "p2p-record-1"
            )
        ]

        for (index, route) in invalidRoutes.enumerated() {
            let sink = RecordingSink()
            let routeRefresher = FakeRuntimeRouteRefresher(result: route)
            let router = makeRouter(
                backend: MockBackend(),
                routeRefresher: routeRefresher
            )

            router.handle(
                ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-invalid-p2p-\(index)"),
                sink: sink
            )

            let message = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(message?.type, MessageType.error)
            XCTAssertEqual(message?.requestID, "route-refresh-invalid-p2p-\(index)")
            XCTAssertEqual(message?.payload["code"], .string("route_refresh_unavailable"))
            XCTAssertEqual(message?.payload["message"], .string("AetherLink Runtime could not refresh remote route material."))
            XCTAssertEqual(message?.payload["retryable"], .bool(true))
            XCTAssertNil(message?.payload["p2p_encrypted_body"])
            XCTAssertEqual(routeRefresher.refreshCount, 1)
        }
    }

    @MainActor
    func testRouteRefreshAllowsPrivateOverlayAndUsbReverseScopedRelayMaterial() async throws {
        let validRoutes: [(RuntimeRouteRefreshResult, String)] = [
            (routeRefreshResult(relayHost: "100.64.1.10", relayScope: "private_overlay"), "private_overlay"),
            (routeRefreshResult(relayHost: "127.0.0.1", relayScope: "usb_reverse"), "usb_reverse"),
        ]

        for (index, item) in validRoutes.enumerated() {
            let (route, expectedScope) = item
            let sink = RecordingSink()
            let router = makeRouter(
                backend: MockBackend(),
                routeRefresher: FakeRuntimeRouteRefresher(result: route)
            )

            router.handle(
                ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-scoped-\(index)"),
                sink: sink
            )

            let message = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(message?.type, MessageType.routeRefresh)
            XCTAssertEqual(message?.requestID, "route-refresh-scoped-\(index)")
            XCTAssertEqual(message?.payload["relay_host"], .string(try XCTUnwrap(route.relayHost)))
            XCTAssertEqual(message?.payload["relay_scope"], .string(expectedScope))
            XCTAssertEqual(message?.payload["relay_secret"], .string("relay-secret-1"))
        }
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

    func testChatSendIntoArchivedRuntimeSessionReturnsStructuredErrorWithoutMutatingStore() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let store = RecordingRuntimeChatEventStore(sessions: [
            RuntimeChatStoredSession(
                sessionID: "archived-session",
                title: "Archived route debug",
                model: "llama3.1:8b",
                lastActivityAt: Date(timeIntervalSince1970: 410),
                messageCount: 2,
                status: "archived",
                archivedAt: Date(timeIntervalSince1970: 420)
            )
        ])
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
                onChatRequest: { request in
                    capturedRequest.value = request
                }
            ),
            chatEventStore: store
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-archived-send",
            payload: [
                "session_id": .string("archived-session"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Continue this archived chat.")
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "chat-archived-send")
        XCTAssertEqual(response?.payload["code"], .string("chat_session_must_be_restored_before_send"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        if case .string(let message)? = response?.payload["message"] {
            XCTAssertTrue(message.contains("Restore this archived chat"))
            XCTAssertTrue(message.contains("archived-session"))
        } else {
            XCTFail("Expected archived chat.send error message")
        }
        XCTAssertNil(capturedRequest.value)
        XCTAssertTrue(store.events.isEmpty)
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

    func testRuntimeChatStoreZeroLimitsReturnEmptyWithoutReadingLog() throws {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        let fileURL = directoryURL.appendingPathComponent("runtime-chat-events.jsonl")
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        try Data("not json\n".utf8).write(to: fileURL)
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)

        XCTAssertEqual(try store.listSessions(limit: 0), [])
        XCTAssertEqual(try store.listSessions(limit: -1, includeArchived: true), [])
        XCTAssertEqual(try store.listMessages(sessionID: "session-read", limit: 0), [])
        XCTAssertEqual(try store.listMessages(sessionID: "session-read", limit: -1), [])
        XCTAssertThrowsError(try store.listSessions(limit: 1)) { error in
            guard case RuntimeChatEventStoreError.corruptEventLog(let line, _)? = error as? RuntimeChatEventStoreError else {
                XCTFail("Expected corrupt event log error, got \(error)")
                return
            }
            XCTAssertEqual(line, 1)
        }
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

    func testRuntimeChatStoreTreatsNonPositiveLimitsAsEmptyHistoryWindows() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 208),
            kind: .request,
            requestID: "turn-limited",
            sessionID: "session-limited",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Keep the history window bounded.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 209),
            kind: .assistantDelta,
            requestID: "turn-limited",
            sessionID: "session-limited",
            model: "llama3.1:8b",
            delta: "Only return requested history."
        ))

        XCTAssertEqual(try store.listSessions(limit: 1).map(\.sessionID), ["session-limited"])
        XCTAssertEqual(try store.listMessages(sessionID: "session-limited", limit: 1).map(\.content), ["Only return requested history."])
        XCTAssertTrue(try store.listSessions(limit: 0).isEmpty)
        XCTAssertTrue(try store.listSessions(limit: -1, includeArchived: true).isEmpty)
        XCTAssertTrue(try store.listMessages(sessionID: "session-limited", limit: 0).isEmpty)
        XCTAssertTrue(try store.listMessages(sessionID: "session-limited", limit: -1).isEmpty)
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

    func testRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 320),
            kind: .request,
            requestID: "legacy-turn",
            sessionID: "legacy-session",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Legacy unscoped chat.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 321),
            kind: .request,
            requestID: "device-a-turn",
            sessionID: "device-a-session",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Device A chat.")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 322),
            kind: .assistantDelta,
            requestID: "device-a-turn",
            sessionID: "device-a-session",
            model: "llama3.1:8b",
            delta: "Device A answer.",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 323),
            kind: .request,
            requestID: "device-b-turn",
            sessionID: "device-b-session",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Device B chat.")],
            ownerDeviceID: "device-b"
        ))

        XCTAssertEqual(try store.listSessions(limit: 10).map(\.sessionID), ["legacy-session"])
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).map(\.sessionID),
            ["device-a-session"]
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-b", limit: 10, includeArchived: true).map(\.sessionID),
            ["device-b-session"]
        )
        XCTAssertEqual(
            try store.listMessages(ownerDeviceID: "device-a", sessionID: "device-a-session", limit: 10).map(\.content),
            ["Device A chat.", "Device A answer."]
        )
        XCTAssertTrue(try store.listMessages(ownerDeviceID: "device-b", sessionID: "device-a-session", limit: 10).isEmpty)
        XCTAssertThrowsError(try store.mutateSession(
            ownerDeviceID: "device-b",
            sessionID: "device-a-session",
            requestID: "device-b-archive-a",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 324)
        )) { error in
            XCTAssertEqual(error as? RuntimeChatEventStoreError, .sessionNotFound("device-a-session"))
        }

        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-session",
            requestID: "device-a-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 325)
        )
        XCTAssertTrue(try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false).isEmpty)
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true).map(\.status),
            ["archived"]
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-b", limit: 10, includeArchived: true).map(\.sessionID),
            ["device-b-session"]
        )
    }

    func testRuntimeChatStoreSearchesSessionSummariesAndTranscriptWithinOwnerScope() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 340),
            kind: .request,
            requestID: "device-a-relay-turn",
            sessionID: "device-a-relay",
            model: "ollama:llama3.1:8b",
            messages: [
                ChatMessage(
                    role: "system",
                    content: "Runtime user memory:\nHidden latest QR route system context."
                ),
                ChatMessage(
                    role: "user",
                    content: "How can I repair pairing?",
                    attachments: [ChatAttachment(type: "text", mimeType: "text/plain", name: "lease.txt", text: "Lease renewal checklist")]
                )
            ],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 341),
            kind: .assistantDelta,
            requestID: "device-a-relay-turn",
            sessionID: "device-a-relay",
            model: "ollama:llama3.1:8b",
            delta: "Scan the latest QR route before retrying relay.",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 342),
            kind: .done,
            requestID: "device-a-relay-turn",
            sessionID: "device-a-relay",
            model: "ollama:llama3.1:8b",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 343),
            kind: .title,
            requestID: "device-a-relay-title",
            sessionID: "device-a-relay",
            model: "ollama:llama3.1:8b",
            title: "Relay Repair Notes",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 344),
            kind: .request,
            requestID: "device-a-model-turn",
            sessionID: "device-a-model",
            model: "lmstudio:qwen3:8b",
            messages: [ChatMessage(role: "user", content: "Compare local model choices.")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 345),
            kind: .done,
            requestID: "device-a-model-turn",
            sessionID: "device-a-model",
            model: "lmstudio:qwen3:8b",
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 346),
            kind: .request,
            requestID: "device-a-archived-turn",
            sessionID: "device-a-archived",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Archived overlay diagnostics.")],
            ownerDeviceID: "device-a"
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 347),
            kind: .assistantDelta,
            requestID: "device-a-archived-turn",
            sessionID: "device-a-archived",
            model: "ollama:llama3.1:8b",
            delta: "Archived relay route note.",
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-archived",
            requestID: "device-a-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 348)
        )
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 349),
            kind: .request,
            requestID: "device-a-deleted-turn",
            sessionID: "device-a-deleted",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Deleted secret route.")],
            ownerDeviceID: "device-a"
        ))
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-deleted",
            requestID: "device-a-deleted-archive",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 350)
        )
        _ = try store.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-deleted",
            requestID: "device-a-delete",
            mutation: .delete,
            timestamp: Date(timeIntervalSince1970: 351)
        )
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 352),
            kind: .request,
            requestID: "device-b-relay-turn",
            sessionID: "device-b-relay",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Relay private text.")],
            ownerDeviceID: "device-b"
        ))

        let latestQRResults = try store.listSessions(
            ownerDeviceID: "device-a",
            limit: 10,
            includeArchived: false,
            query: "latest QR"
        )
        XCTAssertEqual(
            latestQRResults.map(\.sessionID),
            ["device-a-relay"]
        )
        XCTAssertEqual(latestQRResults.first?.search?.rank, 1)
        XCTAssertEqual(latestQRResults.first?.search?.matchedFields, ["transcript"])
        XCTAssertTrue(latestQRResults.first?.search?.snippet.contains("latest QR route") ?? false)
        XCTAssertFalse(latestQRResults.first?.search?.snippet.contains("Runtime user memory") ?? true)
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false, query: "hidden latest").isEmpty
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false, query: "qwen3").map(\.sessionID),
            ["device-a-model"]
        )
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false, query: "archived relay").isEmpty
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true, query: "archived relay").map(\.sessionID),
            ["device-a-archived"]
        )
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true, query: "deleted secret").isEmpty
        )
        XCTAssertTrue(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: true, query: "private text").isEmpty
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-b", limit: 10, includeArchived: true, query: "private text").map(\.sessionID),
            ["device-b-relay"]
        )
        let rankedRelayResults = try store.listSessions(
            ownerDeviceID: "device-a",
            limit: 10,
            includeArchived: true,
            query: "relay"
        )
        XCTAssertEqual(rankedRelayResults.map(\.sessionID), ["device-a-relay", "device-a-archived"])
        XCTAssertEqual(rankedRelayResults.compactMap { $0.search?.rank }, [1, 2])
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 1, includeArchived: true, query: "relay").map(\.sessionID),
            ["device-a-relay"]
        )
        XCTAssertEqual(
            try store.listSessions(ownerDeviceID: "device-a", limit: 10, includeArchived: false, query: "   ").map(\.sessionID),
            ["device-a-model", "device-a-relay"]
        )
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

    func testRuntimeChatEventLogIsCreatedWithOwnerOnlyPermissions() throws {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        let fileURL = directoryURL.appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 330),
            kind: .request,
            requestID: "turn-permissions",
            sessionID: "session-permissions",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Persist this securely.")]
        ))

        XCTAssertEqual(try posixPermissions(at: fileURL), 0o600)
        XCTAssertEqual(try posixPermissions(at: directoryURL), 0o700)
    }

    func testRuntimeChatEventLogPermissionsAreCorrectedOnAppend() throws {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        let fileURL = directoryURL.appendingPathComponent("runtime-chat-events.jsonl")
        try createBroadPermissionEventLog(at: fileURL)
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)

        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 331),
            kind: .request,
            requestID: "turn-permissions-corrected",
            sessionID: "session-permissions-corrected",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Correct file permissions.")]
        ))

        XCTAssertEqual(try posixPermissions(at: fileURL), 0o600)
        XCTAssertEqual(try posixPermissions(at: directoryURL), 0o700)
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

    func testRuntimeChatHistorySemanticallyInvalidEventReturnsStructuredError() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 335),
            kind: .request,
            requestID: "turn-semantic-route",
            sessionID: "session-semantic-route",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Valid history must not be partially returned.")]
        ))
        try appendRawChatEventLogLine(
            #"{"id":"event-semantic-invalid","kind":"request","messages":[{"content":"blank role","role":"   "}],"model":"llama3.1:8b","request_id":"turn-semantic-invalid","session_id":"session-semantic-route","timestamp":"1970-01-01T00:05:36Z"}"#,
            to: fileURL
        )
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-semantic-corrupt",
            payload: ["limit": .number(20)]
        ), sink: sink)
        router.handle(ProtocolEnvelope(
            type: MessageType.chatMessagesList,
            requestID: "messages-semantic-corrupt",
            payload: [
                "session_id": .string("session-semantic-route"),
                "limit": .number(20)
            ]
        ), sink: sink)

        let responses = try await sink.waitForMessages(count: 2)
        for requestID in ["sessions-semantic-corrupt", "messages-semantic-corrupt"] {
            let response = responses.first { $0.requestID == requestID }
            XCTAssertEqual(response?.type, MessageType.error)
            XCTAssertEqual(response?.payload["code"], .string("chat_store_unavailable"))
            if case .string(let message)? = response?.payload["message"] {
                XCTAssertTrue(message.contains("corrupt at line 2"))
                XCTAssertTrue(message.contains("chat request message role is empty"))
                XCTAssertFalse(message.contains("Valid history must not be partially returned."))
            } else {
                XCTFail("Expected structured chat-store error message for \(requestID)")
            }
        }
    }

    func testRuntimeChatHistoryHandlersReturnEmptyForNonPositiveLimitsWithoutReadingStore() async throws {
        let sink = RecordingSink()
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        let fileURL = directoryURL.appendingPathComponent("runtime-chat-events.jsonl")
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        try Data("not json\n".utf8).write(to: fileURL)
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-empty-window",
            payload: ["limit": .number(0)]
        ), sink: sink)
        router.handle(ProtocolEnvelope(
            type: MessageType.chatMessagesList,
            requestID: "messages-empty-window",
            payload: [
                "session_id": .string("session-read"),
                "limit": .number(-1)
            ]
        ), sink: sink)

        let responses = try await sink.waitForMessages(count: 2)
        let sessionsResponse = responses.first { $0.requestID == "sessions-empty-window" }
        let messagesResponse = responses.first { $0.requestID == "messages-empty-window" }

        XCTAssertEqual(sessionsResponse?.type, MessageType.chatSessionsList)
        XCTAssertEqual(sessionsResponse?.payload["sessions"], .array([]))
        XCTAssertEqual(messagesResponse?.type, MessageType.chatMessagesList)
        XCTAssertEqual(messagesResponse?.payload["session_id"], .string("session-read"))
        XCTAssertEqual(messagesResponse?.payload["messages"], .array([]))
    }

    func testChatSessionsListQueryFiltersRuntimeOwnedSummaries() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 390),
            kind: .request,
            requestID: "search-route-turn",
            sessionID: "session-search-route",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Repair the remote relay route.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 391),
            kind: .assistantDelta,
            requestID: "search-route-turn",
            sessionID: "session-search-route",
            model: "ollama:llama3.1:8b",
            delta: "Scan a fresh QR before reconnecting."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 392),
            kind: .request,
            requestID: "search-memory-turn",
            sessionID: "session-search-memory",
            model: "ollama:llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Summarize memory notes.")]
        ))
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-search-route",
            payload: [
                "limit": .number(10),
                "query": .string("fresh QR")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.chatSessionsList)
        guard case .array(let sessions)? = response?.payload["sessions"],
              case .object(let session)? = sessions.first else {
            XCTFail("Expected filtered sessions response")
            return
        }
        XCTAssertEqual(sessions.count, 1)
        XCTAssertEqual(session["session_id"], .string("session-search-route"))
        guard case .object(let search)? = session["search"],
              case .array(let matchedFields)? = search["matched_fields"] else {
            XCTFail("Expected query response search metadata")
            return
        }
        XCTAssertEqual(search["rank"], .number(1))
        XCTAssertEqual(search["snippet"], .string("Scan a fresh QR before reconnecting."))
        XCTAssertEqual(matchedFields, [.string("transcript")])

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-unqueried",
            payload: [
                "limit": .number(10)
            ]
        ), sink: sink)

        let responses = try await sink.waitForMessages(count: 2)
        let unqueriedResponse = responses.first { $0.requestID == "sessions-unqueried" }
        guard case .array(let unqueriedSessions)? = unqueriedResponse?.payload["sessions"],
              case .object(let unqueriedSession)? = unqueriedSessions.first else {
            XCTFail("Expected unqueried sessions response")
            return
        }
        XCTAssertNil(unqueriedSession["search"])
    }

    func testChatSessionsListEmbeddingModelHintStaysSearchOnly() async throws {
        let sink = RecordingSink()
        let store = SearchHintRecordingRuntimeChatEventStore(sessions: [
            RuntimeChatStoredSession(
                sessionID: "session-search-route",
                title: "Remote relay route",
                model: "ollama:llama3.1:8b",
                lastActivityAt: Date(timeIntervalSince1970: 400),
                messageCount: 2,
                search: RuntimeChatStoredSessionSearch(
                    rank: 1,
                    snippet: "Scan a fresh QR before reconnecting.",
                    matchedFields: ["transcript"]
                )
            )
        ])
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-search-embedding-hint",
            payload: [
                "limit": .number(10),
                "query": .string("fresh QR"),
                "embedding_model_id": .string("  ollama:nomic-embed-text  ")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.chatSessionsList)
        XCTAssertEqual(store.searchRequests.first?.query, "fresh QR")
        XCTAssertEqual(store.searchRequests.first?.embeddingModelID, "ollama:nomic-embed-text")
        guard case .array(let sessions)? = response?.payload["sessions"],
              case .object(let session)? = sessions.first,
              case .object(let search)? = session["search"],
              case .array(let matchedFields)? = search["matched_fields"] else {
            XCTFail("Expected search response metadata")
            return
        }
        XCTAssertNil(session["embedding_model_id"])
        XCTAssertEqual(search["rank"], .number(1))
        XCTAssertEqual(search["snippet"], .string("Scan a fresh QR before reconnecting."))
        XCTAssertEqual(matchedFields, [.string("transcript")])

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-blank-query-embedding-hint",
            payload: [
                "limit": .number(10),
                "query": .string("   "),
                "embedding_model_id": .string("ollama:nomic-embed-text")
            ]
        ), sink: sink)

        _ = try await sink.waitForMessages(count: 2)
        XCTAssertEqual(store.searchRequests.count, 2)
        XCTAssertEqual(store.searchRequests.last?.query, "   ")
        XCTAssertNil(store.searchRequests.last?.embeddingModelID)
    }

    func testChatSessionsListRejectsUnknownPayloadMetadataBeforeStoreDispatch() async throws {
        let sink = RecordingSink()
        let store = SearchHintRecordingRuntimeChatEventStore(sessions: [])
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-metadata",
            payload: [
                "limit": .number(10),
                "include_archived": .bool(true),
                "query": .string("fresh QR"),
                "embedding_model_id": .string("ollama:nomic-embed-text"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "sessions-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("backend_url"))
        XCTAssertEqual(store.searchRequests, [])
    }

    func testChatSessionsListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch() async throws {
        let invalidPayloads: [(requestID: String, payload: [String: JSONValue], expectedField: String)] = [
            (
                "sessions-invalid-limit-type",
                ["limit": .string("10")],
                "limit"
            ),
            (
                "sessions-invalid-limit-fraction",
                ["limit": .number(1.5)],
                "limit"
            ),
            (
                "sessions-invalid-include-archived-type",
                ["include_archived": .string("true")],
                "include_archived"
            ),
            (
                "sessions-invalid-query-type",
                ["query": .number(42)],
                "query"
            ),
            (
                "sessions-invalid-embedding-type",
                [
                    "query": .string("fresh QR"),
                    "embedding_model_id": .object(["id": .string("ollama:nomic-embed-text")])
                ],
                "embedding_model_id"
            ),
            (
                "sessions-invalid-embedding-without-query-type",
                ["embedding_model_id": .array([.string("ollama:nomic-embed-text")])],
                "embedding_model_id"
            )
        ]

        for invalidPayload in invalidPayloads {
            let sink = RecordingSink()
            let store = SearchHintRecordingRuntimeChatEventStore(sessions: [])
            let router = makeRouter(
                backend: MockBackend(),
                chatEventStore: store
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.chatSessionsList,
                requestID: invalidPayload.requestID,
                payload: invalidPayload.payload
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error)
            XCTAssertEqual(response?.requestID, invalidPayload.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
            XCTAssertEqual(response?.payload["retryable"], .bool(false))
            XCTAssertTrue(String(describing: response?.payload).contains(invalidPayload.expectedField))
            XCTAssertEqual(store.searchRequests, [])
        }
    }

    func testChatMessagesListRejectsUnknownPayloadMetadataBeforeStoreDispatch() async throws {
        let sink = RecordingSink()
        let store = SearchHintRecordingRuntimeChatEventStore(sessions: [])
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatMessagesList,
            requestID: "messages-metadata",
            payload: [
                "session_id": .string("session-1"),
                "limit": .number(10),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "messages-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("backend_url"))
        XCTAssertEqual(store.messageRequests, [])
    }

    func testChatMessagesListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch() async throws {
        let invalidPayloads: [(requestID: String, payload: [String: JSONValue], expectedField: String)] = [
            (
                "messages-invalid-session-id-whitespace",
                [
                    "session_id": .string("   \n\t"),
                    "limit": .number(20)
                ],
                "session_id"
            ),
            (
                "messages-invalid-limit-type",
                [
                    "session_id": .string("session-1"),
                    "limit": .string("20")
                ],
                "limit"
            ),
            (
                "messages-invalid-limit-fraction",
                [
                    "session_id": .string("session-1"),
                    "limit": .number(20.5)
                ],
                "limit"
            )
        ]

        for invalidPayload in invalidPayloads {
            let sink = RecordingSink()
            let store = SearchHintRecordingRuntimeChatEventStore(sessions: [])
            let router = makeRouter(
                backend: MockBackend(),
                chatEventStore: store
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.chatMessagesList,
                requestID: invalidPayload.requestID,
                payload: invalidPayload.payload
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error)
            XCTAssertEqual(response?.requestID, invalidPayload.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
            XCTAssertEqual(response?.payload["retryable"], .bool(false))
            XCTAssertTrue(String(describing: response?.payload).contains(invalidPayload.expectedField))
            XCTAssertEqual(store.messageRequests, [])
        }
    }

    func testChatSessionsListQueryMatchesReasoningWhileMessagesKeepAnswerSeparate() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl")
        let store = JSONLRuntimeChatEventStore(fileURL: fileURL)
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 395),
            kind: .request,
            requestID: "reasoning-search-turn",
            sessionID: "session-reasoning-search",
            model: "qwen3:8b",
            messages: [ChatMessage(role: "user", content: "Keep the visible answer short.")]
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 396),
            kind: .reasoningDelta,
            requestID: "reasoning-search-turn",
            sessionID: "session-reasoning-search",
            model: "qwen3:8b",
            reasoningDelta: "Checking latent calibration before answering."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 397),
            kind: .assistantDelta,
            requestID: "reasoning-search-turn",
            sessionID: "session-reasoning-search",
            model: "qwen3:8b",
            delta: "Visible answer stays separate."
        ))
        try store.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 398),
            kind: .done,
            requestID: "reasoning-search-turn",
            sessionID: "session-reasoning-search",
            model: "qwen3:8b",
            finishReason: "stop"
        ))
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionsList,
            requestID: "sessions-search-reasoning",
            payload: [
                "limit": .number(10),
                "query": .string("latent calibration")
            ]
        ), sink: sink)

        let searchResponse = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(searchResponse?.type, MessageType.chatSessionsList)
        guard case .array(let sessions)? = searchResponse?.payload["sessions"],
              case .object(let session)? = sessions.first,
              case .object(let search)? = session["search"],
              case .array(let matchedFields)? = search["matched_fields"] else {
            XCTFail("Expected reasoning search metadata")
            return
        }
        XCTAssertEqual(sessions.count, 1)
        XCTAssertEqual(session["session_id"], .string("session-reasoning-search"))
        XCTAssertEqual(search["rank"], .number(1))
        XCTAssertEqual(search["snippet"], .string("Checking latent calibration before answering."))
        XCTAssertEqual(matchedFields, [.string("reasoning")])

        router.handle(ProtocolEnvelope(
            type: MessageType.chatMessagesList,
            requestID: "messages-search-reasoning",
            payload: [
                "session_id": .string("session-reasoning-search"),
                "limit": .number(10)
            ]
        ), sink: sink)

        let responses = try await sink.waitForMessages(count: 2)
        let messagesResponse = responses.first { $0.requestID == "messages-search-reasoning" }
        guard case .array(let messages)? = messagesResponse?.payload["messages"],
              case .object(let assistant)? = messages.last else {
            XCTFail("Expected reasoning transcript response")
            return
        }
        XCTAssertEqual(assistant["role"], .string("assistant"))
        XCTAssertEqual(assistant["content"], .string("Visible answer stays separate."))
        XCTAssertEqual(assistant["reasoning"], .string("Checking latent calibration before answering."))
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

    func testChatSessionLifecycleRejectsUnknownPayloadMetadataBeforeStoreMutation() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore(sessions: [
            RuntimeChatStoredSession(
                sessionID: "session-lifecycle-metadata",
                title: "Runtime lifecycle",
                model: "llama3.1:8b",
                lastActivityAt: Date(timeIntervalSince1970: 420),
                messageCount: 1
            )
        ])
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionArchive,
            requestID: "archive-metadata",
            payload: [
                "session_id": .string("session-lifecycle-metadata"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "archive-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("backend_url"))
        XCTAssertEqual(store.mutationRequests, [])
        XCTAssertEqual(store.events, [])
    }

    func testChatSessionLifecycleRejectsInvalidAllowedPayloadTypesBeforeStoreMutation() async throws {
        let testCases: [(type: String, requestID: String, payload: [String: JSONValue])] = [
            (
                MessageType.chatSessionArchive,
                "archive-invalid-session-id-number",
                ["session_id": .number(42)]
            ),
            (
                MessageType.chatSessionRestore,
                "restore-invalid-session-id-bool",
                ["session_id": .bool(true)]
            ),
            (
                MessageType.chatSessionDelete,
                "delete-invalid-session-id-empty",
                ["session_id": .string("")]
            ),
            (
                MessageType.chatSessionArchive,
                "archive-invalid-session-id-whitespace",
                ["session_id": .string("   \n\t")]
            )
        ]

        for testCase in testCases {
            let sink = RecordingSink()
            let store = RecordingRuntimeChatEventStore(sessions: [
                RuntimeChatStoredSession(
                    sessionID: "session-lifecycle-invalid",
                    title: "Runtime lifecycle",
                    model: "llama3.1:8b",
                    lastActivityAt: Date(timeIntervalSince1970: 421),
                    messageCount: 1
                )
            ])
            let router = makeRouter(
                backend: MockBackend(),
                chatEventStore: store
            )

            router.handle(ProtocolEnvelope(
                type: testCase.type,
                requestID: testCase.requestID,
                payload: testCase.payload
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error, testCase.requestID)
            XCTAssertEqual(response?.requestID, testCase.requestID, testCase.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"), testCase.requestID)
            XCTAssertEqual(response?.payload["retryable"], .bool(false), testCase.requestID)
            XCTAssertEqual(store.mutationRequests, [], testCase.requestID)
            XCTAssertEqual(store.events, [], testCase.requestID)
        }
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

    func testChatSessionRenameRejectsUnknownPayloadMetadataBeforeTitleStoreMutation() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore(sessions: [
            RuntimeChatStoredSession(
                sessionID: "session-rename-metadata",
                title: "Runtime rename",
                model: "llama3.1:8b",
                lastActivityAt: Date(timeIntervalSince1970: 440),
                messageCount: 1
            )
        ])
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionRename,
            requestID: "rename-metadata",
            payload: [
                "session_id": .string("session-rename-metadata"),
                "title": .string("Runtime route notes"),
                "renamed_at": .string("2026-06-23T09:02:00Z"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "rename-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("renamed_at"))
        XCTAssertEqual(store.events, [])
    }

    func testChatSessionRenameRejectsInvalidAllowedPayloadTypesBeforeTitleStoreMutation() async throws {
        let testCases: [(requestID: String, payload: [String: JSONValue])] = [
            (
                "rename-invalid-session-id-number",
                [
                    "session_id": .number(42),
                    "title": .string("Runtime route notes")
                ]
            ),
            (
                "rename-invalid-session-id-whitespace",
                [
                    "session_id": .string("   \n\t"),
                    "title": .string("Runtime route notes")
                ]
            ),
            (
                "rename-invalid-title-bool",
                [
                    "session_id": .string("session-rename-invalid"),
                    "title": .bool(true)
                ]
            ),
            (
                "rename-invalid-title-empty-after-trim",
                [
                    "session_id": .string("session-rename-invalid"),
                    "title": .string("   ")
                ]
            )
        ]

        for testCase in testCases {
            let sink = RecordingSink()
            let store = RecordingRuntimeChatEventStore(sessions: [
                RuntimeChatStoredSession(
                    sessionID: "session-rename-invalid",
                    title: "Runtime rename",
                    model: "llama3.1:8b",
                    lastActivityAt: Date(timeIntervalSince1970: 441),
                    messageCount: 1
                )
            ])
            let router = makeRouter(
                backend: MockBackend(),
                chatEventStore: store
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.chatSessionRename,
                requestID: testCase.requestID,
                payload: testCase.payload
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error, testCase.requestID)
            XCTAssertEqual(response?.requestID, testCase.requestID, testCase.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"), testCase.requestID)
            XCTAssertEqual(response?.payload["retryable"], .bool(false), testCase.requestID)
            XCTAssertEqual(store.sessionListRequests, [], testCase.requestID)
            XCTAssertEqual(store.events, [], testCase.requestID)
        }
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

    func testMemoryDeleteRejectsUnknownPayloadMetadataBeforeStoreMutation() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeMemoryStore()
        let router = makeRouter(
            backend: MockBackend(),
            memoryStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryDelete,
            requestID: "memory-delete-metadata",
            payload: [
                "id": .string("memory-metadata"),
                "deleted_at": .string("2026-06-23T09:02:00Z"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "memory-delete-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("backend_url"))
        XCTAssertEqual(store.deleteRequests, [])
    }

    func testMemoryDeleteRejectsInvalidAllowedPayloadTypesBeforeStoreMutation() async throws {
        let testCases: [(requestID: String, payload: [String: JSONValue])] = [
            (
                "memory-delete-invalid-id-number",
                ["id": .number(42)]
            ),
            (
                "memory-delete-invalid-id-empty",
                ["id": .string("")]
            ),
            (
                "memory-delete-invalid-id-whitespace",
                ["id": .string("   \n\t")]
            )
        ]

        for testCase in testCases {
            let sink = RecordingSink()
            let store = RecordingRuntimeMemoryStore()
            let router = makeRouter(
                backend: MockBackend(),
                memoryStore: store
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.memoryDelete,
                requestID: testCase.requestID,
                payload: testCase.payload
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error, testCase.requestID)
            XCTAssertEqual(response?.requestID, testCase.requestID, testCase.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"), testCase.requestID)
            XCTAssertEqual(response?.payload["retryable"], .bool(false), testCase.requestID)
            XCTAssertEqual(store.deleteRequests, [], testCase.requestID)
        }
    }

    func testMemoryListRejectsUnknownPayloadMetadataBeforeStoreDispatch() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeMemoryStore(entries: [
            RuntimeMemoryEntry(
                id: "memory-metadata",
                content: "Use latest QR recovery for relay route failures.",
                createdAt: Date(timeIntervalSince1970: 1_000),
                updatedAt: Date(timeIntervalSince1970: 1_000)
            )
        ])
        let router = makeRouter(
            backend: MockBackend(),
            memoryStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryList,
            requestID: "memory-list-metadata",
            payload: [
                "query": .string("relay recovery"),
                "entries": .array([]),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "memory-list-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("backend_url"))
        XCTAssertEqual(store.listRequests, [])
    }

    func testMemoryListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch() async throws {
        let cases: [(requestID: String, query: JSONValue)] = [
            ("memory-list-invalid-query-number", .number(42)),
            ("memory-list-invalid-query-bool", .bool(true)),
            ("memory-list-invalid-query-object", .object(["term": .string("relay recovery")]))
        ]

        for testCase in cases {
            let sink = RecordingSink()
            let store = RecordingRuntimeMemoryStore(entries: [
                RuntimeMemoryEntry(
                    id: "memory-query-type",
                    content: "Use latest QR recovery for relay route failures.",
                    createdAt: Date(timeIntervalSince1970: 1_000),
                    updatedAt: Date(timeIntervalSince1970: 1_000)
                )
            ])
            let router = makeRouter(
                backend: MockBackend(),
                memoryStore: store
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.memoryList,
                requestID: testCase.requestID,
                payload: ["query": testCase.query]
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error)
            XCTAssertEqual(response?.requestID, testCase.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
            XCTAssertEqual(response?.payload["retryable"], .bool(false))
            XCTAssertTrue(String(describing: response?.payload).contains("query"))
            XCTAssertEqual(store.listRequests, [])
        }
    }

    func testMemoryListRejectsOversizedQueryBeforeStoreDispatch() async throws {
        let overlongQuery = String(repeating: "a", count: 257)
        let excessiveTermQuery = (1...17).map { "term\($0)" }.joined(separator: " ")
        let cases: [(requestID: String, query: String, expectedMessage: String)] = [
            (
                "memory-list-overlong-query",
                overlongQuery,
                "at most 256 characters"
            ),
            (
                "memory-list-excessive-term-query",
                excessiveTermQuery,
                "at most 16 distinct terms"
            )
        ]

        for testCase in cases {
            let sink = RecordingSink()
            let store = RecordingRuntimeMemoryStore(entries: [
                RuntimeMemoryEntry(
                    id: "memory-query-resource-guard",
                    content: "Use latest QR recovery for relay route failures.",
                    createdAt: Date(timeIntervalSince1970: 1_000),
                    updatedAt: Date(timeIntervalSince1970: 1_000)
                )
            ])
            let router = makeRouter(
                backend: MockBackend(),
                memoryStore: store
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.memoryList,
                requestID: testCase.requestID,
                payload: ["query": .string(testCase.query)]
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error, testCase.requestID)
            XCTAssertEqual(response?.requestID, testCase.requestID, testCase.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"), testCase.requestID)
            XCTAssertEqual(response?.payload["retryable"], .bool(false), testCase.requestID)
            XCTAssertTrue(String(describing: response?.payload).contains("query"), testCase.requestID)
            XCTAssertTrue(String(describing: response?.payload).contains(testCase.expectedMessage), testCase.requestID)
            XCTAssertEqual(store.listRequests, [], testCase.requestID)
        }
    }

    func testMemoryListQueryFiltersRuntimeOwnedMemoryWithSearchMetadata() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        _ = try memoryStore.upsert(
            id: "memory-content-match",
            content: "Use latest QR recovery for relay route failures.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 1_000)
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: nil,
            id: "memory-source-match",
            content: "Review older connection notes.",
            enabled: true,
            source: RuntimeMemoryEntrySource(
                kind: "long_inactivity_summary",
                draftID: "long-inactivity:source-match:1000:6",
                summaryMethod: "deterministic_preview",
                session: RuntimeMemoryEntrySourceSession(
                    sessionID: "source-match",
                    title: "Relay recovery source",
                    model: "dev-mock",
                    lastActivityAt: Date(timeIntervalSince1970: 900),
                    messageCount: 7,
                    inactiveSeconds: 86_400
                ),
                sourceMessageCount: 6,
                sourceRange: "visible messages 1-6 of 6",
                sourcePointers: [
                    RuntimeMemoryEntrySourcePointer(
                        sessionID: "source-match",
                        messageIndex: 1,
                        role: "user",
                        createdAt: Date(timeIntervalSince1970: 850),
                        excerpt: "Relay recovery should keep source excerpts bounded."
                    )
                ]
            ),
            timestamp: Date(timeIntervalSince1970: 1_100)
        )
        _ = try memoryStore.upsert(
            id: "memory-unmatched",
            content: "Prefers concise Korean answers.",
            enabled: false,
            timestamp: Date(timeIntervalSince1970: 1_200)
        )
        let router = makeRouter(
            backend: MockBackend(),
            memoryStore: memoryStore
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryList,
            requestID: "memory-list-query",
            payload: ["query": .string("relay recovery")]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).last
        XCTAssertEqual(response?.type, MessageType.memoryList)
        XCTAssertEqual(response?.requestID, "memory-list-query")
        guard case .array(let entries)? = response?.payload["entries"],
              case .object(let firstEntry)? = entries.first,
              case .object(let firstSearch)? = firstEntry["search"],
              case .object(let secondEntry)? = entries.dropFirst().first,
              case .object(let secondSearch)? = secondEntry["search"] else {
            XCTFail("Expected searched memory list entries with search metadata")
            return
        }
        XCTAssertEqual(entries.count, 2)
        XCTAssertEqual(firstEntry["id"], .string("memory-content-match"))
        XCTAssertEqual(firstSearch["rank"], .number(1))
        XCTAssertEqual(firstSearch["matched_fields"], .array([.string("content")]))
        XCTAssertEqual(firstSearch["snippet"], .string("Use latest QR recovery for relay route failures."))
        XCTAssertEqual(secondEntry["id"], .string("memory-source-match"))
        XCTAssertEqual(secondSearch["rank"], .number(2))
        XCTAssertEqual(secondSearch["matched_fields"], .array([.string("source_title"), .string("source_excerpt")]))
        guard case .string(let secondSnippet)? = secondSearch["snippet"] else {
            XCTFail("Expected source search snippet")
            return
        }
        XCTAssertTrue(secondSnippet.contains("Relay recovery"))
        XCTAssertNotEqual(firstEntry["id"], .string("memory-unmatched"))

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryList,
            requestID: "memory-list-blank-query",
            payload: ["query": .string("   ")]
        ), sink: sink)

        let blankResponse = try await sink.waitForMessages(count: 2).last
        guard case .array(let blankEntries)? = blankResponse?.payload["entries"],
              case .object(let blankFirstEntry)? = blankEntries.first else {
            XCTFail("Expected unfiltered memory list for blank query")
            return
        }
        XCTAssertEqual(blankEntries.count, 3)
        XCTAssertNil(blankFirstEntry["search"])
    }

    func testMemoryUpsertRejectsUnknownPayloadMetadataBeforeStoreMutation() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeMemoryStore()
        let router = makeRouter(
            backend: MockBackend(),
            memoryStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryUpsert,
            requestID: "memory-upsert-metadata",
            payload: [
                "id": .string("manual-memory"),
                "content": .string("Client tries to smuggle direct-store metadata."),
                "enabled": .bool(true),
                "entry": .object([
                    "id": .string("response-entry"),
                    "content": .string("response-only memory entry"),
                    "enabled": .bool(true)
                ]),
                "source": .object([
                    "kind": .string("forged"),
                    "draft_id": .string("attacker-draft")
                ]),
                "backend_url": .string("http://127.0.0.1:11434"),
                "backend_credentials": .string("future-backend-token"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "memory-upsert-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("entry"))
        XCTAssertTrue(String(describing: response?.payload).contains("source"))
        XCTAssertTrue(String(describing: response?.payload).contains("backend_url"))
        XCTAssertEqual(store.upsertRequests, [])
    }

    func testMemoryUpsertRejectsInvalidAllowedPayloadTypesBeforeStoreMutation() async throws {
        let cases: [(requestID: String, payload: [String: JSONValue], expectedField: String)] = [
            (
                "memory-upsert-invalid-id-empty",
                [
                    "id": .string(""),
                    "content": .string("Client sends an empty memory id."),
                    "enabled": .bool(true)
                ],
                "id"
            ),
            (
                "memory-upsert-invalid-id-whitespace",
                [
                    "id": .string("   \n\t"),
                    "content": .string("Client sends a blank memory id."),
                    "enabled": .bool(true)
                ],
                "id"
            ),
            (
                "memory-upsert-invalid-id-type",
                [
                    "id": .number(42),
                    "content": .string("Client sends a malformed memory id."),
                    "enabled": .bool(true)
                ],
                "id"
            ),
            (
                "memory-upsert-invalid-content-whitespace",
                [
                    "id": .string("memory-invalid-content-whitespace"),
                    "content": .string("   \n\t"),
                    "enabled": .bool(true)
                ],
                "content"
            ),
            (
                "memory-upsert-invalid-content-type",
                [
                    "id": .string("memory-invalid-content-type"),
                    "content": .number(42),
                    "enabled": .bool(true)
                ],
                "content"
            ),
            (
                "memory-upsert-invalid-enabled-string",
                [
                    "id": .string("memory-invalid-enabled-string"),
                    "content": .string("Client sends a string enabled flag."),
                    "enabled": .string("false")
                ],
                "enabled"
            ),
            (
                "memory-upsert-invalid-enabled-number",
                [
                    "id": .string("memory-invalid-enabled-number"),
                    "content": .string("Client sends a numeric enabled flag."),
                    "enabled": .number(1)
                ],
                "enabled"
            )
        ]

        for testCase in cases {
            let sink = RecordingSink()
            let store = RecordingRuntimeMemoryStore()
            let router = makeRouter(
                backend: MockBackend(),
                memoryStore: store
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.memoryUpsert,
                requestID: testCase.requestID,
                payload: testCase.payload
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error)
            XCTAssertEqual(response?.requestID, testCase.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
            XCTAssertEqual(response?.payload["retryable"], .bool(false))
            XCTAssertTrue(String(describing: response?.payload).contains(testCase.expectedField))
            XCTAssertEqual(store.upsertRequests, [])
        }
    }

    func testMemoryUpsertRejectsClientSuppliedSourceMetadataAndPreservesRuntimeSource() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        let source = RuntimeMemoryEntrySource(
            kind: "long_inactivity_summary",
            draftID: "long-inactivity:source-session:1000:6",
            summaryMethod: "deterministic_preview",
            session: RuntimeMemoryEntrySourceSession(
                sessionID: "source-session",
                title: "Runtime source session",
                model: "dev-mock",
                lastActivityAt: Date(timeIntervalSince1970: 1_000),
                messageCount: 7,
                inactiveSeconds: 86_400
            ),
            sourceMessageCount: 6,
            sourceRange: "visible messages 1-6 of 6",
            sourcePointers: [
                RuntimeMemoryEntrySourcePointer(
                    sessionID: "source-session",
                    messageIndex: 1,
                    role: "user",
                    createdAt: Date(timeIntervalSince1970: 900),
                    excerpt: "User-approved source excerpt."
                )
            ]
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: nil,
            id: "memory-summary:long-inactivity:source-session:1000:6",
            content: "User-approved memory from source.",
            enabled: true,
            source: source,
            timestamp: Date(timeIntervalSince1970: 1_100)
        )
        let router = makeRouter(
            backend: MockBackend(),
            memoryStore: memoryStore
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryUpsert,
            requestID: "memory-source-forgery",
            payload: [
                "id": .string("manual-memory"),
                "content": .string("Client tries to forge source metadata."),
                "enabled": .bool(true),
                "source": .object([
                    "kind": .string("forged"),
                    "draft_id": .string("attacker-draft")
                ])
            ]
        ), sink: sink)

        let rejectedResponse = try await sink.waitForMessages(count: 1).last
        XCTAssertEqual(rejectedResponse?.type, MessageType.error)
        XCTAssertEqual(rejectedResponse?.requestID, "memory-source-forgery")
        XCTAssertEqual(rejectedResponse?.payload["code"], .string("invalid_payload"))
        XCTAssertTrue(
            try memoryStore.list().allSatisfy { $0.id != "manual-memory" },
            "Rejected client-supplied source metadata must not create a memory entry."
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryUpsert,
            requestID: "memory-source-preserving-edit",
            payload: [
                "id": .string("memory-summary:long-inactivity:source-session:1000:6"),
                "content": .string("Edited approved memory keeps audit source."),
                "enabled": .bool(false)
            ]
        ), sink: sink)

        let editResponse = try await sink.waitForMessages(count: 2).last
        XCTAssertEqual(editResponse?.type, MessageType.memoryUpsert)
        guard case .object(let editedEntryPayload)? = editResponse?.payload["entry"],
              case .object(let editedSourcePayload)? = editedEntryPayload["source"],
              case .object(let editedSourceSessionPayload)? = editedSourcePayload["session"],
              case .array(let editedPointersPayload)? = editedSourcePayload["source_pointers"],
              case .object(let editedFirstPointerPayload)? = editedPointersPayload.first else {
            XCTFail("Expected runtime-derived source metadata to survive memory edit")
            return
        }
        XCTAssertEqual(editedEntryPayload["content"], .string("Edited approved memory keeps audit source."))
        XCTAssertEqual(editedEntryPayload["enabled"], .bool(false))
        XCTAssertEqual(editedSourcePayload["draft_id"], .string(source.draftID))
        XCTAssertEqual(editedSourcePayload["source_range"], .string("visible messages 1-6 of 6"))
        XCTAssertEqual(editedSourceSessionPayload["session_id"], .string("source-session"))
        XCTAssertEqual(editedFirstPointerPayload["excerpt"], .string("User-approved source excerpt."))

        let reloadedEntry = try JSONLRuntimeMemoryStore(fileURL: fileURL).list().first
        XCTAssertEqual(reloadedEntry?.source?.draftID, source.draftID)
        XCTAssertEqual(reloadedEntry?.source?.sourcePointers.first?.excerpt, "User-approved source excerpt.")
    }

    func testMemorySummaryDraftsListRequiresAuthentication() async throws {
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(backend: MockBackend(status: .available))

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftsList,
            requestID: "summary-drafts-unauthenticated"
        ), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "summary-drafts-unauthenticated")
        XCTAssertEqual(message?.payload["code"], .string("authentication_required"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testMemorySummaryDraftsListReturnsOwnerScopedActiveVisibleDraftsOnly() async throws {
        let deviceAKey = P256.Signing.PrivateKey()
        let deviceBKey = P256.Signing.PrivateKey()
        let trustedStore = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await trustedStore.trust(TrustedDevice(
            id: "device-a",
            name: "Device A",
            publicKeyBase64: deviceAKey.publicKey.derRepresentation.base64EncodedString()
        ))
        try await trustedStore.trust(TrustedDevice(
            id: "device-b",
            name: "Device B",
            publicKeyBase64: deviceBKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let chatStore = SQLiteRuntimeChatEventStore(databaseURL: temporarySQLiteURL())
        let memoryStoreURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: memoryStoreURL)
        let oldDate = Date(timeIntervalSince1970: 1_000_000)

        try appendMemorySummaryDraftTranscript(
            to: chatStore,
            sessionID: "device-a-visible-draft",
            ownerDeviceID: "device-a",
            firstTurnAt: oldDate,
            visiblePrefix: "Device A"
        )
        try appendMemorySummaryDraftTranscript(
            to: chatStore,
            sessionID: "device-b-hidden-draft",
            ownerDeviceID: "device-b",
            firstTurnAt: oldDate,
            visiblePrefix: "Device B private"
        )
        try appendMemorySummaryDraftTranscript(
            to: chatStore,
            sessionID: "device-a-archived-draft",
            ownerDeviceID: "device-a",
            firstTurnAt: oldDate,
            visiblePrefix: "Archived private"
        )
        _ = try chatStore.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-archived-draft",
            requestID: "archive-device-a-archived-draft",
            mutation: .archive,
            timestamp: oldDate.addingTimeInterval(600)
        )
        try appendMemorySummaryDraftTranscript(
            to: chatStore,
            sessionID: "device-a-deleted-draft",
            ownerDeviceID: "device-a",
            firstTurnAt: oldDate,
            visiblePrefix: "Deleted private"
        )
        _ = try chatStore.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-deleted-draft",
            requestID: "archive-device-a-deleted-draft",
            mutation: .archive,
            timestamp: oldDate.addingTimeInterval(700)
        )
        _ = try chatStore.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "device-a-deleted-draft",
            requestID: "delete-device-a-deleted-draft",
            mutation: .delete,
            timestamp: oldDate.addingTimeInterval(701)
        )

        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: trustedStore,
            chatEventStore: chatStore,
            memoryStore: memoryStore
        )
        let sinkA = RecordingSink()
        try await authenticateTrustedDevice(router: router, sink: sinkA, deviceID: "device-a", privateKey: deviceAKey)

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftsList,
            requestID: "summary-drafts-device-a",
            payload: ["limit": .number(10)]
        ), sink: sinkA)

        let response = try await sinkA.waitForMessages(count: 3).last
        XCTAssertEqual(response?.type, MessageType.memorySummaryDraftsList)
        XCTAssertEqual(response?.requestID, "summary-drafts-device-a")
        guard case .array(let drafts)? = response?.payload["drafts"],
              case .object(let draft)? = drafts.first,
              case .object(let session)? = draft["session"],
              case .array(let pointers)? = draft["source_pointers"],
              case .object(let firstPointer)? = pointers.first,
              case .string(let preview)? = draft["summary_preview"] else {
            XCTFail("Expected memory summary draft payload")
            return
        }

        XCTAssertEqual(drafts.count, 1)
        XCTAssertEqual(session["session_id"], .string("device-a-visible-draft"))
        XCTAssertEqual(session["message_count"], .number(7))
        XCTAssertEqual(draft["source_message_count"], .number(6))
        XCTAssertEqual(draft["source_range"], .string("visible messages 1-6 of 6"))
        XCTAssertEqual(firstPointer["session_id"], .string("device-a-visible-draft"))
        XCTAssertEqual(firstPointer["message_index"], .number(1))
        XCTAssertEqual(firstPointer["role"], .string("user"))
        XCTAssertEqual(firstPointer["excerpt"], .string("Device A question 0"))
        XCTAssertTrue(preview.contains("User: Device A question 0"))
        XCTAssertTrue(preview.contains("Assistant: Device A answer 2"))
        XCTAssertFalse(preview.contains("Runtime user memory"))
        XCTAssertFalse(preview.contains("Runtime conversation summary"))
        XCTAssertFalse(preview.contains("private reasoning"))
        XCTAssertFalse(preview.contains("Device B private"))
        XCTAssertFalse(preview.contains("Archived private"))
        XCTAssertFalse(preview.contains("Deleted private"))
        XCTAssertTrue(try memoryStore.list(ownerDeviceID: "device-a").isEmpty)
    }

    func testMemorySummaryDraftsListRejectsUnknownPayloadMetadataBeforeStoreDispatch() async throws {
        let sink = RecordingSink()
        let chatStore = RecordingRuntimeChatEventStore()
        let memoryStore = RecordingRuntimeMemoryStore()
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: chatStore,
            memoryStore: memoryStore
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftsList,
            requestID: "summary-drafts-metadata",
            payload: [
                "limit": .number(10),
                "drafts": .array([]),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "summary-drafts-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("backend_url"))
        XCTAssertEqual(chatStore.sessionListRequests, [])
        XCTAssertEqual(memoryStore.listRequests, [])
    }

    func testMemorySummaryDraftsListRejectsInvalidAllowedPayloadTypesBeforeStoreDispatch() async throws {
        let invalidPayloads: [(requestID: String, payload: [String: JSONValue], expectedField: String)] = [
            (
                "summary-drafts-invalid-limit-string",
                ["limit": .string("10")],
                "limit"
            ),
            (
                "summary-drafts-invalid-limit-fraction",
                ["limit": .number(10.5)],
                "limit"
            )
        ]

        for invalidPayload in invalidPayloads {
            let sink = RecordingSink()
            let chatStore = RecordingRuntimeChatEventStore()
            let memoryStore = RecordingRuntimeMemoryStore()
            let router = makeRouter(
                backend: MockBackend(),
                chatEventStore: chatStore,
                memoryStore: memoryStore
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.memorySummaryDraftsList,
                requestID: invalidPayload.requestID,
                payload: invalidPayload.payload
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error)
            XCTAssertEqual(response?.requestID, invalidPayload.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
            XCTAssertEqual(response?.payload["retryable"], .bool(false))
            XCTAssertTrue(String(describing: response?.payload).contains(invalidPayload.expectedField))
            XCTAssertEqual(chatStore.sessionListRequests, [])
            XCTAssertEqual(memoryStore.listRequests, [])
        }
    }

    func testMemorySummaryDraftApproveRequiresAuthentication() async throws {
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(backend: MockBackend(status: .available))

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftApprove,
            requestID: "summary-draft-approve-unauthenticated",
            payload: ["draft_id": .string("long-inactivity:session-1:1000:6")]
        ), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "summary-draft-approve-unauthenticated")
        XCTAssertEqual(message?.payload["code"], .string("authentication_required"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testMemorySummaryDraftDismissRequiresAuthentication() async throws {
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(backend: MockBackend(status: .available))

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftDismiss,
            requestID: "summary-draft-dismiss-unauthenticated",
            payload: ["draft_id": .string("long-inactivity:session-1:1000:6")]
        ), sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "summary-draft-dismiss-unauthenticated")
        XCTAssertEqual(message?.payload["code"], .string("authentication_required"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
    }

    func testMemorySummaryDraftApproveWritesIdempotentOwnerScopedMemoryAndHidesApprovedDraft() async throws {
        let deviceAKey = P256.Signing.PrivateKey()
        let deviceBKey = P256.Signing.PrivateKey()
        let trustedStore = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await trustedStore.trust(TrustedDevice(
            id: "device-a",
            name: "Device A",
            publicKeyBase64: deviceAKey.publicKey.derRepresentation.base64EncodedString()
        ))
        try await trustedStore.trust(TrustedDevice(
            id: "device-b",
            name: "Device B",
            publicKeyBase64: deviceBKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let chatStore = SQLiteRuntimeChatEventStore(databaseURL: temporarySQLiteURL())
        let memoryStoreURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: memoryStoreURL)
        let oldDate = Date(timeIntervalSince1970: 1_000_000)

        try appendMemorySummaryDraftTranscript(
            to: chatStore,
            sessionID: "device-a-approval-draft",
            ownerDeviceID: "device-a",
            firstTurnAt: oldDate,
            visiblePrefix: "Approval"
        )
        try appendMemorySummaryDraftTranscript(
            to: chatStore,
            sessionID: "device-b-hidden-approval-draft",
            ownerDeviceID: "device-b",
            firstTurnAt: oldDate,
            visiblePrefix: "Device B hidden"
        )

        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: trustedStore,
            chatEventStore: chatStore,
            memoryStore: memoryStore
        )
        let sinkA = RecordingSink()
        try await authenticateTrustedDevice(router: router, sink: sinkA, deviceID: "device-a", privateKey: deviceAKey)

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftsList,
            requestID: "summary-drafts-before-approval",
            payload: ["limit": .number(10)]
        ), sink: sinkA)

        let listResponse = try await sinkA.waitForMessages(count: 3).last
        guard case .array(let drafts)? = listResponse?.payload["drafts"],
              case .object(let draft)? = drafts.first,
              case .string(let draftID)? = draft["id"],
              case .object(let session)? = draft["session"] else {
            XCTFail("Expected memory summary draft payload before approval")
            return
        }
        XCTAssertEqual(drafts.count, 1)
        XCTAssertEqual(session["session_id"], .string("device-a-approval-draft"))

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftApprove,
            requestID: "summary-draft-approve-stale",
            payload: [
                "draft_id": .string(draftID),
                "expected_session_id": .string("device-a-approval-draft"),
                "expected_source_message_count": .number(99)
            ]
        ), sink: sinkA)

        let staleResponse = try await sinkA.waitForMessages(count: 4).last
        XCTAssertEqual(staleResponse?.type, MessageType.error)
        XCTAssertEqual(staleResponse?.requestID, "summary-draft-approve-stale")
        XCTAssertEqual(staleResponse?.payload["code"], .string("memory_summary_draft_stale"))
        XCTAssertTrue(try memoryStore.list(ownerDeviceID: "device-a").isEmpty)

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftApprove,
            requestID: "summary-draft-approve",
            payload: [
                "draft_id": .string(draftID),
                "expected_session_id": .string("device-a-approval-draft"),
                "expected_source_message_count": .number(6)
            ]
        ), sink: sinkA)

        let approveResponse = try await sinkA.waitForMessages(count: 5).last
        XCTAssertEqual(approveResponse?.type, MessageType.memorySummaryDraftApprove)
        XCTAssertEqual(approveResponse?.requestID, "summary-draft-approve")
        XCTAssertEqual(approveResponse?.payload["draft_id"], .string(draftID))
        XCTAssertEqual(approveResponse?.payload["status"], .string("approved"))
        guard case .object(let entryPayload)? = approveResponse?.payload["entry"],
              case .string(let memoryID)? = entryPayload["id"],
              case .string(let memoryContent)? = entryPayload["content"],
              case .object(let sourcePayload)? = entryPayload["source"],
              case .object(let sourceSessionPayload)? = sourcePayload["session"],
              case .array(let sourcePointersPayload)? = sourcePayload["source_pointers"],
              case .object(let firstSourcePointerPayload)? = sourcePointersPayload.first else {
            XCTFail("Expected approved memory entry payload")
            return
        }
        XCTAssertEqual(memoryID, "memory-summary:\(draftID)")
        XCTAssertTrue(memoryContent.contains("User: Approval question 0"))
        XCTAssertTrue(memoryContent.contains("Assistant: Approval answer 2"))
        XCTAssertFalse(memoryContent.contains("Device B hidden"))
        XCTAssertFalse(memoryContent.contains("private reasoning"))
        XCTAssertEqual(sourcePayload["kind"], .string("long_inactivity_summary_draft"))
        XCTAssertEqual(sourcePayload["draft_id"], .string(draftID))
        XCTAssertEqual(sourcePayload["summary_method"], .string("deterministic_preview"))
        XCTAssertEqual(sourcePayload["source_message_count"], .number(6))
        XCTAssertEqual(sourcePayload["source_range"], .string("visible messages 1-6 of 6"))
        XCTAssertEqual(sourceSessionPayload["session_id"], .string("device-a-approval-draft"))
        XCTAssertEqual(firstSourcePointerPayload["session_id"], .string("device-a-approval-draft"))
        XCTAssertEqual(firstSourcePointerPayload["message_index"], .number(1))
        XCTAssertEqual(firstSourcePointerPayload["role"], .string("user"))
        XCTAssertEqual(firstSourcePointerPayload["excerpt"], .string("Approval question 0"))

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftApprove,
            requestID: "summary-draft-approve-retry",
            payload: ["draft_id": .string(draftID)]
        ), sink: sinkA)

        _ = try await sinkA.waitForMessages(count: 6).last
        let entries = try memoryStore.list(ownerDeviceID: "device-a")
        XCTAssertEqual(entries.map(\.id), ["memory-summary:\(draftID)"])
        XCTAssertEqual(entries.first?.source?.draftID, draftID)
        XCTAssertEqual(entries.first?.source?.sourceRange, "visible messages 1-6 of 6")
        XCTAssertEqual(entries.first?.source?.sourcePointers.first?.excerpt, "Approval question 0")
        let reloadedEntries = try JSONLRuntimeMemoryStore(fileURL: memoryStoreURL)
            .list(ownerDeviceID: "device-a")
        XCTAssertEqual(reloadedEntries.first?.source?.draftID, draftID)
        XCTAssertEqual(reloadedEntries.first?.source?.sourcePointers.map(\.excerpt), [
            "Approval question 0",
            "Approval answer 0",
            "Approval question 1",
            "Approval answer 1",
            "Approval question 2",
            "Approval answer 2"
        ])
        XCTAssertTrue(try memoryStore.list(ownerDeviceID: "device-b").isEmpty)

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryList,
            requestID: "memory-list-after-approval"
        ), sink: sinkA)

        let memoryListResponse = try await sinkA.waitForMessages(count: 7).last
        XCTAssertEqual(memoryListResponse?.type, MessageType.memoryList)
        guard case .array(let memoryListEntries)? = memoryListResponse?.payload["entries"],
              case .object(let listedEntry)? = memoryListEntries.first,
              case .object(let listedSource)? = listedEntry["source"] else {
            XCTFail("Expected memory list source metadata")
            return
        }
        XCTAssertEqual(listedSource["draft_id"], .string(draftID))
        XCTAssertEqual(listedSource["source_range"], .string("visible messages 1-6 of 6"))

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftsList,
            requestID: "summary-drafts-after-approval",
            payload: ["limit": .number(10)]
        ), sink: sinkA)

        let afterListResponse = try await sinkA.waitForMessages(count: 8).last
        XCTAssertEqual(afterListResponse?.type, MessageType.memorySummaryDraftsList)
        XCTAssertEqual(afterListResponse?.payload["drafts"], .array([]))
    }

    func testMemorySummaryDraftApproveRejectsUnknownPayloadMetadataBeforeStoreMutation() async throws {
        let sink = RecordingSink()
        let chatStore = RecordingRuntimeChatEventStore()
        let memoryStore = RecordingRuntimeMemoryStore()
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: chatStore,
            memoryStore: memoryStore
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftApprove,
            requestID: "summary-draft-approve-metadata",
            payload: [
                "draft_id": .string("long-inactivity:session-1:1000:6"),
                "content": .string("Approve this runtime-owned draft."),
                "enabled": .bool(true),
                "expected_session_id": .string("session-1"),
                "expected_source_message_count": .number(6),
                "status": .string("approved"),
                "entry": .object(["id": .string("client-entry")]),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "summary-draft-approve-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("backend_url"))
        XCTAssertEqual(chatStore.sessionListRequests, [])
        XCTAssertEqual(memoryStore.upsertRequests, [])
    }

    func testMemorySummaryDraftApproveRejectsInvalidAllowedPayloadTypesBeforeStoreMutation() async throws {
        let invalidPayloads: [(requestID: String, payload: [String: JSONValue], expectedField: String)] = [
            (
                "summary-draft-approve-invalid-content-type",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "content": .number(42)
                ],
                "content"
            ),
            (
                "summary-draft-approve-blank-content",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "content": .string("   \n\t")
                ],
                "content"
            ),
            (
                "summary-draft-approve-invalid-enabled-type",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "enabled": .string("true")
                ],
                "enabled"
            ),
            (
                "summary-draft-approve-invalid-expected-session-type",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "expected_session_id": .number(1)
                ],
                "expected_session_id"
            ),
            (
                "summary-draft-approve-blank-expected-session",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "expected_session_id": .string("   \n\t")
                ],
                "expected_session_id"
            ),
            (
                "summary-draft-approve-invalid-expected-count-string",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "expected_source_message_count": .string("6")
                ],
                "expected_source_message_count"
            ),
            (
                "summary-draft-approve-invalid-expected-count-fraction",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "expected_source_message_count": .number(6.5)
                ],
                "expected_source_message_count"
            )
        ]

        for invalidPayload in invalidPayloads {
            let sink = RecordingSink()
            let chatStore = RecordingRuntimeChatEventStore()
            let memoryStore = RecordingRuntimeMemoryStore()
            let router = makeRouter(
                backend: MockBackend(),
                chatEventStore: chatStore,
                memoryStore: memoryStore
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.memorySummaryDraftApprove,
                requestID: invalidPayload.requestID,
                payload: invalidPayload.payload
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error)
            XCTAssertEqual(response?.requestID, invalidPayload.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
            XCTAssertEqual(response?.payload["retryable"], .bool(false))
            XCTAssertTrue(String(describing: response?.payload).contains(invalidPayload.expectedField))
            XCTAssertEqual(chatStore.sessionListRequests, [])
            XCTAssertEqual(memoryStore.upsertRequests, [])
        }
    }

    func testMemorySummaryDraftApproveRejectsBlankDraftIDBeforeStoreMutation() async throws {
        let sink = RecordingSink()
        let chatStore = RecordingRuntimeChatEventStore()
        let memoryStore = RecordingRuntimeMemoryStore()
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: chatStore,
            memoryStore: memoryStore
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftApprove,
            requestID: "summary-draft-approve-blank-draft-id",
            payload: [
                "draft_id": .string("   \n\t"),
                "content": .string("Client should not reach memory mutation.")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "summary-draft-approve-blank-draft-id")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("draft_id"))
        XCTAssertEqual(chatStore.sessionListRequests, [])
        XCTAssertEqual(memoryStore.upsertRequests, [])
    }

    func testMemorySummaryDraftDismissHidesOwnerScopedDraftWithoutWritingMemory() async throws {
        let deviceAKey = P256.Signing.PrivateKey()
        let deviceBKey = P256.Signing.PrivateKey()
        let trustedStore = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await trustedStore.trust(TrustedDevice(
            id: "device-a",
            name: "Device A",
            publicKeyBase64: deviceAKey.publicKey.derRepresentation.base64EncodedString()
        ))
        try await trustedStore.trust(TrustedDevice(
            id: "device-b",
            name: "Device B",
            publicKeyBase64: deviceBKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let chatStore = SQLiteRuntimeChatEventStore(databaseURL: temporarySQLiteURL())
        let memoryStoreURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: memoryStoreURL)
        let oldDate = Date(timeIntervalSince1970: 1_000_000)

        try appendMemorySummaryDraftTranscript(
            to: chatStore,
            sessionID: "device-a-dismiss-draft",
            ownerDeviceID: "device-a",
            firstTurnAt: oldDate,
            visiblePrefix: "Dismiss"
        )
        try appendMemorySummaryDraftTranscript(
            to: chatStore,
            sessionID: "device-b-dismiss-draft",
            ownerDeviceID: "device-b",
            firstTurnAt: oldDate,
            visiblePrefix: "Device B dismiss"
        )

        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: trustedStore,
            chatEventStore: chatStore,
            memoryStore: memoryStore
        )
        let sinkA = RecordingSink()
        try await authenticateTrustedDevice(router: router, sink: sinkA, deviceID: "device-a", privateKey: deviceAKey)

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftsList,
            requestID: "summary-drafts-before-dismiss",
            payload: ["limit": .number(10)]
        ), sink: sinkA)

        let listResponse = try await sinkA.waitForMessages(count: 3).last
        guard case .array(let drafts)? = listResponse?.payload["drafts"],
              case .object(let draft)? = drafts.first,
              case .string(let draftID)? = draft["id"],
              case .object(let session)? = draft["session"] else {
            XCTFail("Expected memory summary draft payload before dismiss")
            return
        }
        XCTAssertEqual(drafts.count, 1)
        XCTAssertEqual(session["session_id"], .string("device-a-dismiss-draft"))

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftDismiss,
            requestID: "summary-draft-dismiss-stale",
            payload: [
                "draft_id": .string(draftID),
                "expected_session_id": .string("device-a-dismiss-draft"),
                "expected_source_message_count": .number(99)
            ]
        ), sink: sinkA)

        let staleResponse = try await sinkA.waitForMessages(count: 4).last
        XCTAssertEqual(staleResponse?.type, MessageType.error)
        XCTAssertEqual(staleResponse?.requestID, "summary-draft-dismiss-stale")
        XCTAssertEqual(staleResponse?.payload["code"], .string("memory_summary_draft_stale"))
        XCTAssertTrue(try memoryStore.dismissedMemorySummaryDraftIDs(ownerDeviceID: "device-a").isEmpty)
        XCTAssertTrue(try memoryStore.list(ownerDeviceID: "device-a").isEmpty)

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftDismiss,
            requestID: "summary-draft-dismiss",
            payload: [
                "draft_id": .string(draftID),
                "expected_session_id": .string("device-a-dismiss-draft"),
                "expected_source_message_count": .number(6)
            ]
        ), sink: sinkA)

        let dismissResponse = try await sinkA.waitForMessages(count: 5).last
        XCTAssertEqual(dismissResponse?.type, MessageType.memorySummaryDraftDismiss)
        XCTAssertEqual(dismissResponse?.requestID, "summary-draft-dismiss")
        XCTAssertEqual(dismissResponse?.payload["draft_id"], .string(draftID))
        XCTAssertEqual(dismissResponse?.payload["status"], .string("dismissed"))
        guard case .string(let dismissedAt)? = dismissResponse?.payload["dismissed_at"] else {
            XCTFail("Expected dismissed_at payload")
            return
        }
        XCTAssertFalse(dismissedAt.isEmpty)
        XCTAssertEqual(try memoryStore.dismissedMemorySummaryDraftIDs(ownerDeviceID: "device-a"), Set([draftID]))
        XCTAssertEqual(
            try JSONLRuntimeMemoryStore(fileURL: memoryStoreURL)
                .dismissedMemorySummaryDraftIDs(ownerDeviceID: "device-a"),
            Set([draftID])
        )
        XCTAssertTrue(try memoryStore.list(ownerDeviceID: "device-a").isEmpty)
        XCTAssertTrue(try memoryStore.list(ownerDeviceID: "device-b").isEmpty)

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftsList,
            requestID: "summary-drafts-after-dismiss",
            payload: ["limit": .number(10)]
        ), sink: sinkA)

        let afterListResponse = try await sinkA.waitForMessages(count: 6).last
        XCTAssertEqual(afterListResponse?.type, MessageType.memorySummaryDraftsList)
        XCTAssertEqual(afterListResponse?.payload["drafts"], .array([]))

        let sinkB = RecordingSink()
        try await authenticateTrustedDevice(router: router, sink: sinkB, deviceID: "device-b", privateKey: deviceBKey)
        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftsList,
            requestID: "summary-drafts-device-b-after-device-a-dismiss",
            payload: ["limit": .number(10)]
        ), sink: sinkB)

        let deviceBListResponse = try await sinkB.waitForMessages(count: 3).last
        guard case .array(let deviceBDrafts)? = deviceBListResponse?.payload["drafts"],
              case .object(let deviceBDraft)? = deviceBDrafts.first,
              case .object(let deviceBSession)? = deviceBDraft["session"] else {
            XCTFail("Expected owner-isolated memory summary draft payload")
            return
        }
        XCTAssertEqual(deviceBDrafts.count, 1)
        XCTAssertEqual(deviceBSession["session_id"], .string("device-b-dismiss-draft"))

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftDismiss,
            requestID: "summary-draft-dismiss-retry",
            payload: ["draft_id": .string(draftID)]
        ), sink: sinkA)

        let retryResponse = try await sinkA.waitForMessages(count: 7).last
        XCTAssertEqual(retryResponse?.type, MessageType.memorySummaryDraftDismiss)
        XCTAssertEqual(retryResponse?.payload["draft_id"], .string(draftID))
        XCTAssertEqual(retryResponse?.payload["status"], .string("dismissed"))
        XCTAssertEqual(try memoryStore.dismissedMemorySummaryDraftIDs(ownerDeviceID: "device-a"), Set([draftID]))
        XCTAssertTrue(try memoryStore.list(ownerDeviceID: "device-a").isEmpty)
    }

    func testMemorySummaryDraftDismissRejectsUnknownPayloadMetadataBeforeStoreMutation() async throws {
        let sink = RecordingSink()
        let chatStore = RecordingRuntimeChatEventStore()
        let memoryStore = RecordingRuntimeMemoryStore()
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: chatStore,
            memoryStore: memoryStore
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftDismiss,
            requestID: "summary-draft-dismiss-metadata",
            payload: [
                "draft_id": .string("long-inactivity:session-1:1000:6"),
                "expected_session_id": .string("session-1"),
                "expected_source_message_count": .number(6),
                "status": .string("dismissed"),
                "dismissed_at": .string("2026-06-23T09:02:00Z"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "summary-draft-dismiss-metadata")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("backend_url"))
        XCTAssertEqual(chatStore.sessionListRequests, [])
        XCTAssertEqual(memoryStore.dismissMemorySummaryDraftRequests, [])
    }

    func testMemorySummaryDraftDismissRejectsInvalidAllowedPayloadTypesBeforeStoreMutation() async throws {
        let invalidPayloads: [(requestID: String, payload: [String: JSONValue], expectedField: String)] = [
            (
                "summary-draft-dismiss-invalid-expected-session-type",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "expected_session_id": .number(1)
                ],
                "expected_session_id"
            ),
            (
                "summary-draft-dismiss-blank-expected-session",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "expected_session_id": .string("   \n\t")
                ],
                "expected_session_id"
            ),
            (
                "summary-draft-dismiss-invalid-expected-count-string",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "expected_source_message_count": .string("6")
                ],
                "expected_source_message_count"
            ),
            (
                "summary-draft-dismiss-invalid-expected-count-fraction",
                [
                    "draft_id": .string("long-inactivity:session-1:1000:6"),
                    "expected_source_message_count": .number(6.5)
                ],
                "expected_source_message_count"
            )
        ]

        for invalidPayload in invalidPayloads {
            let sink = RecordingSink()
            let chatStore = RecordingRuntimeChatEventStore()
            let memoryStore = RecordingRuntimeMemoryStore()
            let router = makeRouter(
                backend: MockBackend(),
                chatEventStore: chatStore,
                memoryStore: memoryStore
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.memorySummaryDraftDismiss,
                requestID: invalidPayload.requestID,
                payload: invalidPayload.payload
            ), sink: sink)

            let response = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(response?.type, MessageType.error)
            XCTAssertEqual(response?.requestID, invalidPayload.requestID)
            XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
            XCTAssertEqual(response?.payload["retryable"], .bool(false))
            XCTAssertTrue(String(describing: response?.payload).contains(invalidPayload.expectedField))
            XCTAssertEqual(chatStore.sessionListRequests, [])
            XCTAssertEqual(memoryStore.dismissMemorySummaryDraftRequests, [])
        }
    }

    func testMemorySummaryDraftDismissRejectsBlankDraftIDBeforeStoreMutation() async throws {
        let sink = RecordingSink()
        let chatStore = RecordingRuntimeChatEventStore()
        let memoryStore = RecordingRuntimeMemoryStore()
        let router = makeRouter(
            backend: MockBackend(),
            chatEventStore: chatStore,
            memoryStore: memoryStore
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memorySummaryDraftDismiss,
            requestID: "summary-draft-dismiss-blank-draft-id",
            payload: [
                "draft_id": .string("   \n\t")
            ]
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "summary-draft-dismiss-blank-draft-id")
        XCTAssertEqual(response?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(response?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: response?.payload).contains("draft_id"))
        XCTAssertEqual(chatStore.sessionListRequests, [])
        XCTAssertEqual(memoryStore.dismissMemorySummaryDraftRequests, [])
    }

    func testRuntimeMemoryStoreReportsCorruptJSONLLineInsteadOfDroppingIt() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        _ = try memoryStore.upsert(
            id: "memory-1",
            content: "This runtime memory must not hide a corrupt tail event.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 400)
        )
        try appendRawMemoryEventLogLine(
            #"{"secret_memory":"should-not-leak","broken":}"#,
            to: fileURL
        )

        XCTAssertThrowsError(try memoryStore.list()) { error in
            guard case RuntimeMemoryStoreError.corruptEventLog(let line, let reason) = error else {
                XCTFail("Expected corrupt memory event log error, got \(error)")
                return
            }
            XCTAssertEqual(line, 2)
            XCTAssertFalse(reason.isEmpty)
            XCTAssertFalse(error.localizedDescription.contains("should-not-leak"))
        }
    }

    func testRuntimeMemoryEventLogIsCreatedWithOwnerOnlyPermissions() throws {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        let fileURL = directoryURL.appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)

        _ = try memoryStore.upsert(
            id: "memory-permissions",
            content: "Keep runtime memory private.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 401)
        )

        XCTAssertEqual(try posixPermissions(at: fileURL), 0o600)
        XCTAssertEqual(try posixPermissions(at: directoryURL), 0o700)
    }

    func testRuntimeMemoryEventLogPermissionsAreCorrectedOnAppend() throws {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        let fileURL = directoryURL.appendingPathComponent("runtime-memory-events.jsonl")
        try createBroadPermissionEventLog(at: fileURL)
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)

        _ = try memoryStore.upsert(
            id: "memory-permissions-corrected",
            content: "Correct runtime memory permissions.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 402)
        )

        XCTAssertEqual(try posixPermissions(at: fileURL), 0o600)
        XCTAssertEqual(try posixPermissions(at: directoryURL), 0o700)
    }

    func testRuntimeMemoryStoreReportsSemanticallyInvalidUpsertLine() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        _ = try memoryStore.upsert(
            id: "memory-1",
            content: "Runtime memory should not be silently dropped.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 405)
        )
        try appendRawMemoryEventLogLine(
            #"{"content":"   ","enabled":true,"id":"memory-2","kind":"upsert","timestamp":"1970-01-01T00:06:46Z"}"#,
            to: fileURL
        )

        XCTAssertThrowsError(try memoryStore.list()) { error in
            guard case RuntimeMemoryStoreError.corruptEventLog(let line, let reason) = error else {
                XCTFail("Expected corrupt memory event log error, got \(error)")
                return
            }
            XCTAssertEqual(line, 2)
            XCTAssertEqual(reason, "memory upsert content is empty")
            XCTAssertFalse(error.localizedDescription.contains("Runtime memory should not be silently dropped."))
        }
    }

    func testRuntimeMemoryStoreScopesEntriesByOwnerDevice() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        _ = try memoryStore.upsert(
            id: "shared-memory-id",
            content: "Legacy unscoped memory.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 420)
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: "device-a",
            id: "shared-memory-id",
            content: "Device A scoped memory.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 421)
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: "device-b",
            id: "shared-memory-id",
            content: "Device B scoped memory.",
            enabled: false,
            timestamp: Date(timeIntervalSince1970: 422)
        )

        XCTAssertEqual(try memoryStore.list().map(\.content), ["Legacy unscoped memory."])
        XCTAssertEqual(try memoryStore.list(ownerDeviceID: "device-a").map(\.content), ["Device A scoped memory."])
        XCTAssertEqual(try memoryStore.list(ownerDeviceID: "device-b").map(\.content), ["Device B scoped memory."])
        XCTAssertEqual(try memoryStore.list(ownerDeviceID: "device-b").first?.enabled, false)

        _ = try memoryStore.delete(
            ownerDeviceID: "device-a",
            id: "shared-memory-id",
            timestamp: Date(timeIntervalSince1970: 423)
        )

        XCTAssertTrue(try memoryStore.list(ownerDeviceID: "device-a").isEmpty)
        XCTAssertEqual(try memoryStore.list(ownerDeviceID: "device-b").map(\.content), ["Device B scoped memory."])
        XCTAssertEqual(try memoryStore.list().map(\.content), ["Legacy unscoped memory."])
    }

    func testRuntimeMemoryListCorruptStoreReturnsStructuredError() async throws {
        let sink = RecordingSink()
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl")
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: fileURL)
        _ = try memoryStore.upsert(
            id: "memory-1",
            content: "Runtime memory is persisted on the host.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 410)
        )
        try appendRawMemoryEventLogLine(
            #"{"secret_memory":"should-not-leak","broken":}"#,
            to: fileURL
        )
        let router = makeRouter(
            backend: MockBackend(),
            memoryStore: memoryStore
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryList,
            requestID: "memory-corrupt"
        ), sink: sink)

        let response = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(response?.type, MessageType.error)
        XCTAssertEqual(response?.requestID, "memory-corrupt")
        XCTAssertEqual(response?.payload["code"], .string("memory_store_unavailable"))
        if case .string(let message)? = response?.payload["message"] {
            XCTAssertTrue(message.contains("corrupt at line 2"))
            XCTAssertFalse(message.contains("should-not-leak"))
        } else {
            XCTFail("Expected structured memory-store error message")
        }
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
        AetherLink currently provides runtime-mediated local model chat, model listing, file/image attachment handling when supported, and chat titles.
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

    func testChatSendCompactionAnnotatesBackendOnlySourceSpanWithoutPersisting() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let chatEventStore = RecordingRuntimeChatEventStore()
        var messagePayloads: [JSONValue] = []
        for index in 1...18 {
            messagePayloads.append(.object([
                "role": .string(index.isMultiple(of: 2) ? "assistant" : "user"),
                "content": .string("source span turn \(index) " + String(repeating: "S", count: 1_600))
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
            chatEventStore: chatEventStore
        )
        let envelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-compaction-source-span",
            payload: [
                "session_id": .string("session-source-span"),
                "model": .string("llama3.1:8b"),
                "messages": .array(messagePayloads)
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.chatDone)
        let request = try XCTUnwrap(capturedRequest.value)
        let summaryMessage = try XCTUnwrap(request.messages.first { $0.content.hasPrefix("Runtime conversation summary:") })
        XCTAssertTrue(summaryMessage.content.contains("Source span: client-visible conversation turns 1-6 of 18."))
        let retainedConversationTurns = request.messages.filter(\.isConversationTurnForTests)
        XCTAssertFalse(retainedConversationTurns.contains { $0.content.contains("source span turn 1 ") })
        XCTAssertTrue(retainedConversationTurns.contains { $0.content.contains("source span turn 7 ") })
        XCTAssertEqual(request.messages.filter(\.isConversationTurnForTests).count, 12)

        let requestEvent = try XCTUnwrap(chatEventStore.events.first { $0.kind == .request })
        XCTAssertEqual(requestEvent.messages?.count, messagePayloads.count)
        XCTAssertTrue(requestEvent.messages?.contains { $0.content.contains("source span turn 1 ") } == true)
        XCTAssertFalse(requestEvent.messages?.contains { $0.content.hasPrefix("Runtime conversation summary:") } == true)
        XCTAssertFalse(requestEvent.messages?.contains { $0.content.contains("Source span: client-visible conversation turns") } == true)
    }

    func testChatSendUsesModelContextWindowMetadataForCompactionBudget() async throws {
        var messagePayloads: [JSONValue] = []
        for index in 0..<18 {
            messagePayloads.append(.object([
                "role": .string(index.isMultiple(of: 2) ? "user" : "assistant"),
                "content": .string("context-window turn \(index) " + String(repeating: "C", count: 1_600))
            ]))
        }

        let smallModelSink = RecordingSink()
        let smallModelRequest = LockedBox<ChatRequest?>(nil)
        let smallModelRouter = makeRouter(backend: MockBackend(
            models: [
                ModelInfo(
                    id: "llama3.1:small",
                    name: "llama3.1:small",
                    installed: true,
                    contextWindowTokens: 4_096
                )
            ],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
            onChatRequest: { request in
                smallModelRequest.value = request
            }
        ))
        smallModelRouter.handle(ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-small-context-window",
            payload: [
                "session_id": .string("session-small-context"),
                "model": .string("llama3.1:small"),
                "messages": .array(messagePayloads)
            ]
        ), sink: smallModelSink)

        let smallModelMessage = try await smallModelSink.waitForMessages(count: 1).first
        XCTAssertEqual(smallModelMessage?.type, MessageType.chatDone)
        let compactedRequest = try XCTUnwrap(smallModelRequest.value)
        XCTAssertTrue(compactedRequest.messages.contains { $0.content.hasPrefix("Runtime conversation summary:") })

        let largeModelSink = RecordingSink()
        let largeModelRequest = LockedBox<ChatRequest?>(nil)
        let largeModelRouter = makeRouter(backend: MockBackend(
            models: [
                ModelInfo(
                    id: "llama3.1:large",
                    name: "llama3.1:large",
                    installed: true,
                    contextWindowTokens: 128_000
                )
            ],
            chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
            onChatRequest: { request in
                largeModelRequest.value = request
            }
        ))
        largeModelRouter.handle(ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-large-context-window",
            payload: [
                "session_id": .string("session-large-context"),
                "model": .string("llama3.1:large"),
                "messages": .array(messagePayloads)
            ]
        ), sink: largeModelSink)

        let largeModelMessage = try await largeModelSink.waitForMessages(count: 1).first
        XCTAssertEqual(largeModelMessage?.type, MessageType.chatDone)
        let uncompactRequest = try XCTUnwrap(largeModelRequest.value)
        XCTAssertFalse(uncompactRequest.messages.contains { $0.content.hasPrefix("Runtime conversation summary:") })
        XCTAssertEqual(uncompactRequest.messages.filter(\.isConversationTurnForTests).count, messagePayloads.count)
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
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(
            backend: MockBackend(
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
            ),
            chatEventStore: store
        )
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

        let requestEvent = try XCTUnwrap(store.events.first { $0.kind == .request })
        let storedMessage = try XCTUnwrap(requestEvent.messages?.first(where: { $0.role == "user" }))
        XCTAssertEqual(storedMessage.content, "Summarize this.")
        XCTAssertFalse(storedMessage.content.contains("[Attached document: roadmap.md (text/plain)]"))
        XCTAssertFalse(storedMessage.content.contains(documentText))
        XCTAssertEqual(storedMessage.attachments, [
            ChatAttachment(
                type: "document",
                mimeType: "text/plain",
                name: "roadmap.md",
                text: documentText
            ),
            ChatAttachment(
                type: "image",
                mimeType: "image/png",
                name: "diagram.png"
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

    func testChatSendRejectsTopLevelPayloadMetadataBeforeBackendDispatch() async throws {
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
            requestID: "chat-payload-source-metadata",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "locale": .string("en"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Use this project context.")
                    ])
                ]),
                "project_id": .string("project-1"),
                "workspace_id": .string("workspace-1"),
                "retrieval_context": .string("future retrieval context"),
                "permission_grant": .string("future permission grant"),
                "backend_url": .string("https://provider.example.invalid/v1/chat/completions")
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "chat-payload-source-metadata")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        if case .string(let errorMessage)? = message?.payload["message"] {
            XCTAssertTrue(errorMessage.contains("project_id"))
        } else {
            XCTFail("Expected invalid payload message to mention the unsupported payload field.")
        }
        XCTAssertNil(capturedRequest.value)
    }

    func testChatSendRejectsMessageSourceMetadataBeforeBackendDispatch() async throws {
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
            requestID: "chat-message-source-metadata",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Use this project context."),
                        "source_path": .string("/Users/example/project/notes.txt"),
                        "workspace_id": .string("workspace-1"),
                        "source_control_status": .string("modified"),
                        "backend_url": .string("https://provider.example.invalid/v1/chat/completions"),
                        "trusted_source": .bool(true)
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "chat-message-source-metadata")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        if case .string(let errorMessage)? = message?.payload["message"] {
            XCTAssertTrue(errorMessage.contains("source_path"))
        } else {
            XCTFail("Expected invalid payload message to mention the unsupported message field.")
        }
        XCTAssertNil(capturedRequest.value)
    }

    func testChatSendRejectsAttachmentSourceMetadataBeforeBackendDispatch() async throws {
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
            requestID: "chat-attachment-source-metadata",
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
                                "mime_type": .string("text/plain"),
                                "name": .string("notes.txt"),
                                "text": .string("private note"),
                                "source_path": .string("/Users/example/project/notes.txt"),
                                "workspace_id": .string("workspace-1"),
                                "source_control_status": .string("modified"),
                                "backend_url": .string("https://provider.example.invalid/v1/chat/completions")
                            ])
                        ])
                    ])
                ])
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "chat-attachment-source-metadata")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        if case .string(let errorMessage)? = message?.payload["message"] {
            XCTAssertTrue(errorMessage.contains("source_path"))
        } else {
            XCTFail("Expected invalid payload message to mention the unsupported attachment field.")
        }
        XCTAssertNil(capturedRequest.value)
    }

    func testChatSendRejectsInvalidAllowedPayloadTypesBeforeBackendDispatch() async throws {
        let cases: [(requestID: String, payload: [String: JSONValue], expectedMessageField: String)] = [
            (
                requestID: "chat-invalid-session-id-whitespace",
                payload: [
                    "session_id": .string("   \n\t"),
                    "model": .string("llama3.1:8b"),
                    "messages": .array([
                        .object([
                            "role": .string("user"),
                            "content": .string("Use this project context.")
                        ])
                    ])
                ],
                expectedMessageField: "session_id"
            ),
            (
                requestID: "chat-invalid-model-whitespace",
                payload: [
                    "session_id": .string("session-1"),
                    "model": .string("   \n\t"),
                    "messages": .array([
                        .object([
                            "role": .string("user"),
                            "content": .string("Use this project context.")
                        ])
                    ])
                ],
                expectedMessageField: "model"
            ),
            (
                requestID: "chat-invalid-locale-type",
                payload: [
                    "session_id": .string("session-1"),
                    "model": .string("llama3.1:8b"),
                    "locale": .array([.string("en")]),
                    "messages": .array([
                        .object([
                            "role": .string("user"),
                            "content": .string("Use this project context.")
                        ])
                    ])
                ],
                expectedMessageField: "locale"
            ),
            (
                requestID: "chat-invalid-role-value",
                payload: [
                    "session_id": .string("session-1"),
                    "model": .string("llama3.1:8b"),
                    "messages": .array([
                        .object([
                            "role": .string("tool"),
                            "content": .string("Use this project context.")
                        ])
                    ])
                ],
                expectedMessageField: "role"
            ),
            (
                requestID: "chat-invalid-attachment-type-value",
                payload: [
                    "session_id": .string("session-1"),
                    "model": .string("llama3.1:8b"),
                    "messages": .array([
                        .object([
                            "role": .string("user"),
                            "content": .string("Read this."),
                            "attachments": .array([
                                .object([
                                    "type": .string("tool_result"),
                                    "mime_type": .string("text/plain"),
                                    "text": .string("private note")
                                ])
                            ])
                        ])
                    ])
                ],
                expectedMessageField: "type"
            ),
            (
                requestID: "chat-invalid-attachment-name-type",
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
                                    "mime_type": .string("text/plain"),
                                    "name": .array([.string("notes.txt")]),
                                    "text": .string("private note")
                                ])
                            ])
                        ])
                    ])
                ],
                expectedMessageField: "name"
            ),
            (
                requestID: "chat-invalid-attachment-data-type",
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
                                    "mime_type": .string("text/plain"),
                                    "data_base64": .bool(true)
                                ])
                            ])
                        ])
                    ])
                ],
                expectedMessageField: "data_base64"
            ),
            (
                requestID: "chat-invalid-attachment-text-type",
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
                                    "mime_type": .string("text/plain"),
                                    "text": .number(42)
                                ])
                            ])
                        ])
                    ])
                ],
                expectedMessageField: "text"
            ),
        ]

        for testCase in cases {
            let sink = RecordingSink()
            let capturedRequest = LockedBox<ChatRequest?>(nil)
            let store = RecordingRuntimeChatEventStore()
            let router = makeRouter(
                backend: MockBackend(
                    models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                    onChatRequest: { request in
                        capturedRequest.value = request
                    }
                ),
                chatEventStore: store
            )
            let envelope = ProtocolEnvelope(
                type: MessageType.chatSend,
                requestID: testCase.requestID,
                payload: testCase.payload
            )

            router.handle(envelope, sink: sink)

            let message = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(message?.type, MessageType.error, testCase.requestID)
            XCTAssertEqual(message?.requestID, testCase.requestID)
            XCTAssertEqual(message?.payload["code"], .string("invalid_payload"), testCase.requestID)
            XCTAssertEqual(message?.payload["retryable"], .bool(false), testCase.requestID)
            if case .string(let errorMessage)? = message?.payload["message"] {
                XCTAssertTrue(errorMessage.contains(testCase.expectedMessageField), testCase.requestID)
            } else {
                XCTFail("Expected invalid payload message to mention \(testCase.expectedMessageField).")
            }
            XCTAssertNil(capturedRequest.value, testCase.requestID)
            XCTAssertTrue(store.events.isEmpty, testCase.requestID)
        }
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

    func testChatTitleRequestRejectsUnknownPayloadMetadataBeforeBackendDispatch() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let backend = MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"title":"Forged"}"#),
                .done(inputTokens: 4, outputTokens: 8)
            ],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        )
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(backend: backend, chatEventStore: store)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-unknown-metadata",
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
                ]),
                "title": .string("client-supplied-title"),
                "project_id": .string("project-1"),
                "workspace_id": .string("workspace-1"),
                "retrieval_context": .string("future retrieval context"),
                "permission_grant": .string("future permission grant"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "backend_credentials": .string("secret-token"),
                "provider_url": .string("http://127.0.0.1:1234/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified"),
                "tool_results": .array([]),
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "title-unknown-metadata")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertEqual(backend.listModelsCallCount, 0)
        XCTAssertNil(capturedRequest.value)
        XCTAssertTrue(store.events.isEmpty)
    }

    func testChatTitleRequestRejectsInvalidAllowedLocaleTypeBeforeBackendDispatch() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let backend = MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"title":"Forged"}"#),
                .done(inputTokens: 4, outputTokens: 8)
            ],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        )
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(backend: backend, chatEventStore: store)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-invalid-locale-type",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("llama3.1:8b"),
                "locale": .array([.string("en")]),
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
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "title-invalid-locale-type")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        if case .string(let errorMessage)? = message?.payload["message"] {
            XCTAssertTrue(errorMessage.contains("locale"))
        } else {
            XCTFail("Expected invalid payload message to mention locale.")
        }
        XCTAssertEqual(backend.listModelsCallCount, 0)
        XCTAssertNil(capturedRequest.value)
        XCTAssertTrue(store.events.isEmpty)
    }

    func testChatTitleRequestRejectsBlankSessionIDBeforeBackendDispatch() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let backend = MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"title":"Forged"}"#),
                .done(inputTokens: 4, outputTokens: 8)
            ],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        )
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(backend: backend, chatEventStore: store)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-blank-session-id",
            payload: [
                "session_id": .string("   \n\t"),
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
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "title-blank-session-id")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        if case .string(let errorMessage)? = message?.payload["message"] {
            XCTAssertTrue(errorMessage.contains("session_id"))
        } else {
            XCTFail("Expected invalid payload message to mention session_id.")
        }
        XCTAssertEqual(backend.listModelsCallCount, 0)
        XCTAssertNil(capturedRequest.value)
        XCTAssertTrue(store.events.isEmpty)
    }

    func testChatTitleRequestRejectsBlankModelBeforeBackendDispatch() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let backend = MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"title":"Forged"}"#),
                .done(inputTokens: 4, outputTokens: 8)
            ],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        )
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(backend: backend, chatEventStore: store)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatTitleRequest,
            requestID: "title-blank-model",
            payload: [
                "session_id": .string("session-1"),
                "model": .string("   \n\t"),
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
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "title-blank-model")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        if case .string(let errorMessage)? = message?.payload["message"] {
            XCTAssertTrue(errorMessage.contains("model"))
        } else {
            XCTFail("Expected invalid payload message to mention model.")
        }
        XCTAssertEqual(backend.listModelsCallCount, 0)
        XCTAssertNil(capturedRequest.value)
        XCTAssertTrue(store.events.isEmpty)
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

    func testChatCancelRejectsUnknownPayloadMetadataBeforeBackendDispatch() async throws {
        let sink = RecordingSink()
        let backend = MockBackend(cancelResult: GenerationCancellationResult.cancelled(generationID: "chat-1"))
        let router = makeRouter(backend: backend)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatCancel,
            requestID: "cancel-metadata",
            payload: [
                "target_request_id": .string("chat-1"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_control_status": .string("modified")
            ]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "cancel-metadata")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: message?.payload).contains("backend_url"))
        XCTAssertEqual(backend.cancelledGenerationIDs, [])
    }

    func testChatCancelRejectsBlankTargetRequestIDBeforeBackendDispatch() async throws {
        let sink = RecordingSink()
        let backend = MockBackend(cancelResult: GenerationCancellationResult.cancelled(generationID: "chat-blank"))
        let router = makeRouter(backend: backend)
        let envelope = ProtocolEnvelope(
            type: MessageType.chatCancel,
            requestID: "cancel-blank",
            payload: ["target_request_id": .string("   \n\t")]
        )

        router.handle(envelope, sink: sink)

        let message = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "cancel-blank")
        XCTAssertEqual(message?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(message?.payload["retryable"], .bool(false))
        XCTAssertEqual(backend.cancelledGenerationIDs, [])
    }

    func testChatCancelAcknowledgementPersistsRuntimeOwnedCancelledEvent() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore()
        let router = makeRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                finishChatStream: false,
                cancelFinishesChatStream: true,
                cancelResult: GenerationCancellationResult.cancelled(generationID: "chat-cancel-store")
            ),
            chatEventStore: store
        )
        let chatEnvelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-cancel-store",
            payload: [
                "session_id": .string("session-cancel-store"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Cancel this from the runtime.")
                    ])
                ])
            ]
        )

        router.handle(chatEnvelope, sink: sink)

        let requestEvents = try await waitForRecordedEvents(in: store, count: 1)
        XCTAssertEqual(requestEvents.map(\.kind), [.request])
        XCTAssertEqual(requestEvents.first?.sessionID, "session-cancel-store")

        let cancelEnvelope = ProtocolEnvelope(
            type: MessageType.chatCancel,
            requestID: "cancel-store-1",
            payload: ["target_request_id": .string("chat-cancel-store")]
        )
        router.handle(cancelEnvelope, sink: sink)

        let messages = try await sink.waitForMessages(count: 2)
        XCTAssertTrue(messages.contains { message in
            message.type == MessageType.chatCancel &&
                message.requestID == "cancel-store-1" &&
                message.payload["target_request_id"] == .string("chat-cancel-store") &&
                message.payload["cancelled"] == .bool(true)
        })
        XCTAssertTrue(messages.contains { message in
            message.type == MessageType.chatDone &&
                message.requestID == "chat-cancel-store" &&
                message.payload["finish_reason"] == .string("cancelled")
        })

        let storedEvents = try await waitForRecordedEvents(in: store, count: 2)
        let cancelledEvents = storedEvents.filter { $0.kind == .cancelled }
        XCTAssertEqual(cancelledEvents.count, 1)
        XCTAssertEqual(cancelledEvents.first?.requestID, "chat-cancel-store")
        XCTAssertEqual(cancelledEvents.first?.sessionID, "session-cancel-store")
        XCTAssertEqual(cancelledEvents.first?.model, "llama3.1:8b")
        XCTAssertEqual(cancelledEvents.first?.finishReason, "cancelled")

        try await Task.sleep(nanoseconds: 50_000_000)
        XCTAssertEqual(store.events.filter { $0.kind == .cancelled }.count, 1)
        let finalMessages = try await sink.waitForMessages(count: 3, timeout: 0.1)
        XCTAssertEqual(finalMessages.filter { $0.type == MessageType.chatDone }.count, 1)
    }

    func testConnectionCloseCancelsActiveChatGenerationAndPersistsCancelledEvent() async throws {
        let sink = RecordingSink()
        let store = RecordingRuntimeChatEventStore()
        let backend = MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            finishChatStream: false,
            cancelFinishesChatStream: true,
            cancelResult: GenerationCancellationResult.cancelled(generationID: "chat-disconnect")
        )
        let router = makeRouter(backend: backend, chatEventStore: store)
        let chatEnvelope = ProtocolEnvelope(
            type: MessageType.chatSend,
            requestID: "chat-disconnect",
            payload: [
                "session_id": .string("session-disconnect"),
                "model": .string("llama3.1:8b"),
                "messages": .array([
                    .object([
                        "role": .string("user"),
                        "content": .string("Cancel this when the socket closes.")
                    ])
                ])
            ]
        )

        router.handle(chatEnvelope, sink: sink)

        let requestEvents = try await waitForRecordedEvents(in: store, count: 1)
        XCTAssertEqual(requestEvents.map(\.kind), [.request])

        router.connectionDidClose(sink.connectionID)

        let storedEvents = try await waitForRecordedEvents(in: store, count: 2)
        XCTAssertEqual(backend.cancelledGenerationIDs, ["chat-disconnect"])
        let cancelledEvents = storedEvents.filter { $0.kind == .cancelled }
        XCTAssertEqual(cancelledEvents.count, 1)
        XCTAssertEqual(cancelledEvents.first?.requestID, "chat-disconnect")
        XCTAssertEqual(cancelledEvents.first?.sessionID, "session-disconnect")
        XCTAssertEqual(cancelledEvents.first?.model, "llama3.1:8b")
        XCTAssertEqual(cancelledEvents.first?.finishReason, "cancelled")

        try await Task.sleep(nanoseconds: 50_000_000)
        XCTAssertEqual(store.events.filter { $0.kind == .cancelled }.count, 1)
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

    func testResponseOnlyMessageTypesReturnDirectionProtocolError() async throws {
        let router = makeRouter(backend: MockBackend())
        let responseOnlyTypes = [
            MessageType.authChallenge,
            MessageType.pairingResult,
            MessageType.modelsResult,
            MessageType.chatDelta,
            MessageType.chatDone,
            MessageType.chatTitleResult,
            MessageType.error,
        ]

        for (index, type) in responseOnlyTypes.enumerated() {
            let sink = RecordingSink()
            router.handle(
                ProtocolEnvelope(
                    type: type,
                    requestID: "response-only-\(index)",
                    payload: [
                        "runtime_device_id": .string("forged-runtime"),
                        "backend_url": .string("http://127.0.0.1:11434"),
                    ]
                ),
                sink: sink
            )

            let message = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(message?.type, MessageType.error)
            XCTAssertEqual(message?.requestID, "response-only-\(index)")
            XCTAssertEqual(message?.payload["code"], .string("unexpected_message_direction"))
            XCTAssertEqual(
                message?.payload["message"],
                .string("Runtime-to-client message type cannot be sent to AetherLink Runtime: \(type)")
            )
            XCTAssertEqual(message?.payload["retryable"], .bool(false))
        }
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
            relaySecret: "secret+with/symbols=",
            relayExpiresAtEpochMillis: 1_780_000_000_000,
            relayNonce: "relay-nonce-1",
            relayScope: "remote"
        )

        let components = try XCTUnwrap(URLComponents(string: session.qrPayload))
        let queryItems = try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }

        XCTAssertEqual(queryItems["relay_host"], "relay.example.test")
        XCTAssertEqual(queryItems["relay_port"], "43171")
        XCTAssertEqual(queryItems["relay_id"], "relay-id-1")
        XCTAssertEqual(queryItems["relay_secret"], "secret+with/symbols=")
        XCTAssertEqual(queryItems["relay_expires_at"], "1780000000000")
        XCTAssertEqual(queryItems["relay_nonce"], "relay-nonce-1")
        XCTAssertEqual(queryItems["relay_scope"], "remote")
        XCTAssertTrue(session.qrPayload.contains("relay_secret=secret%2Bwith/symbols%3D"))
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

    func testPairingQRCodePayloadIncludesP2PRendezvousRecordWhenPresent() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "mac-1",
            macName: "AetherLink Runtime",
            fingerprint: "fp-1",
            routeToken: "route-1",
            p2pRouteClass: "p2p_rendezvous",
            p2pRecordID: "p2p-record-1",
            p2pEncryptedBody: "opaque-candidate-1",
            p2pExpiresAtEpochMillis: 1_780_000_000_000,
            p2pAntiReplayNonce: "p2p-nonce-1",
            p2pProtocolVersion: 1
        )

        let queryItems = try queryItems(from: session.qrPayload)

        XCTAssertEqual(queryItems["p2p_class"], "p2p_rendezvous")
        XCTAssertEqual(queryItems["p2p_record_id"], "p2p-record-1")
        XCTAssertEqual(queryItems["p2p_encrypted_body"], "opaque-candidate-1")
        XCTAssertEqual(queryItems["p2p_expires_at"], "1780000000000")
        XCTAssertEqual(queryItems["p2p_anti_replay_nonce"], "p2p-nonce-1")
        XCTAssertEqual(queryItems["p2p_protocol_version"], "1")
        XCTAssertNil(queryItems["rendezvous_id"])
        XCTAssertNil(queryItems["relay_id"])
        XCTAssertNil(queryItems["host"])
        XCTAssertNil(queryItems["port"])
    }

    func testCompactPairingQRCodePayloadMatchesSharedP2PRendezvousFixture() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            runtimePublicKeyBase64: "runtime+public/key=",
            routeToken: "route-token-1",
            p2pRouteClass: "p2p_rendezvous",
            p2pRecordID: "p2p-record-1",
            p2pEncryptedBody: "opaque-candidate-1",
            p2pExpiresAtEpochMillis: 4_102_444_800_000,
            p2pAntiReplayNonce: "nonce-p2p-route-1",
            p2pProtocolVersion: 1
        )

        let normalizedPayload = try compactPairingPayload(
            session.compactQRCodePayload,
            overriding: [
                "n": "nonce-p2p-1",
                "c": "123456"
            ]
        )

        XCTAssertEqual(
            normalizedPayload,
            try sharedProtocolFixture("macos-compact-p2p-rendezvous-pairing-uri.txt")
        )
    }

    func testPairingRequestStoresTrustedDeviceAndReturnsAccepted() async throws {
        let sink = RecordingSink()
        let coordinator = PairingCoordinator()
        let clientPublicKey = testClientPublicKeyBase64()
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
                "public_key": .string(clientPublicKey)
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
        XCTAssertEqual(devices.first?.publicKeyBase64, clientPublicKey)

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

    func testPairingRequestRejectsUnknownPayloadMetadataBeforeTrusting() async throws {
        let sink = RecordingSink()
        let coordinator = PairingCoordinator(maxFailedAttempts: 6)
        let clientPublicKey = testClientPublicKeyBase64()
        let session = coordinator.beginPairing(
            macDeviceID: "mac-1",
            fingerprint: "fp-1",
            runtimePublicKeyBase64: "runtime-public-key",
            host: "192.168.1.10",
            port: 43170
        )
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(),
            pairingCoordinator: coordinator,
            trustedDeviceStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.pairingRequest,
            requestID: "pair-unknown-metadata",
            payload: [
                "pairing_nonce": .string(session.nonce),
                "pairing_code": .string(session.code),
                "device_id": .string("android-unknown-metadata"),
                "device_name": .string("Android Phone"),
                "public_key": .string(clientPublicKey),
                "accepted": .bool(true),
                "mac_device_id": .string("forged-runtime"),
                "runtime_device_id": .string("forged-runtime"),
                "runtime_public_key": .string("forged-runtime-public-key"),
                "runtime_key_fingerprint": .string("forged-runtime-fingerprint"),
                "trusted_device_id": .string("forged-trusted-device"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "backend_credentials": .string("future-backend-token"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "requested_route_token": .string("future-requested-route-token"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant"),
                "source_path": .string("/Users/example/project/notes.md"),
                "source_control_status": .string("modified")
            ]
        ), sink: sink)

        let rejected = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(rejected?.type, MessageType.error)
        XCTAssertEqual(rejected?.requestID, "pair-unknown-metadata")
        XCTAssertEqual(rejected?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(rejected?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: rejected?.payload).contains("accepted"))
        XCTAssertTrue(String(describing: rejected?.payload).contains("backend_url"))
        let devicesAfterRejectedPayload = try await store.load()
        XCTAssertTrue(devicesAfterRejectedPayload.isEmpty)

        router.handle(pairingEnvelope(
            requestID: "pair-valid-after-unknown-metadata",
            session: session,
            deviceID: "android-valid-after-unknown",
            publicKey: clientPublicKey
        ), sink: sink)

        let accepted = try await sink.waitForMessages(count: 2).last
        XCTAssertEqual(accepted?.type, MessageType.pairingResult)
        XCTAssertEqual(accepted?.payload["accepted"], .bool(true))
        let devicesAfterAcceptedPayload = try await store.load()
        XCTAssertEqual(devicesAfterAcceptedPayload.map(\.id), ["android-valid-after-unknown"])
    }

    func testPairingRequestRejectsBlankAllowedFieldsBeforeTrusting() async throws {
        let sink = RecordingSink()
        let coordinator = PairingCoordinator(maxFailedAttempts: 6)
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
        let blankPayloads = [
            pairingEnvelope(requestID: "pair-blank-nonce", session: session, pairingNonce: "   \n\t"),
            pairingEnvelope(requestID: "pair-blank-code", session: session, pairingCode: "   \n\t"),
            pairingEnvelope(requestID: "pair-blank-device-id", session: session, deviceID: "   \n\t"),
            pairingEnvelope(requestID: "pair-blank-device-name", session: session, deviceName: "   \n\t"),
            pairingEnvelope(requestID: "pair-blank-public-key", session: session, publicKey: "   \n\t")
        ]

        for (index, envelope) in blankPayloads.enumerated() {
            router.handle(envelope, sink: sink)
            let rejection = try await sink.waitForMessages(count: index + 1).last
            XCTAssertEqual(rejection?.type, MessageType.error, envelope.requestID)
            XCTAssertEqual(rejection?.requestID, envelope.requestID)
            XCTAssertEqual(rejection?.payload["code"], .string("invalid_payload"), envelope.requestID)
            XCTAssertEqual(rejection?.payload["retryable"], .bool(false), envelope.requestID)
        }
        let devicesAfterBlankPayloads = try await store.load()
        XCTAssertTrue(devicesAfterBlankPayloads.isEmpty)

        let invalidCode = session.code == "000000" ? "999999" : "000000"
        router.handle(pairingEnvelope(
            requestID: "pair-invalid-code-after-blank-fields",
            session: session,
            pairingCode: invalidCode
        ), sink: sink)

        let invalidCodeRejection = try await sink.waitForMessages(count: blankPayloads.count + 1).last
        XCTAssertEqual(invalidCodeRejection?.type, MessageType.pairingResult)
        XCTAssertEqual(invalidCodeRejection?.payload["accepted"], .bool(false))
        XCTAssertEqual(invalidCodeRejection?.payload["code"], .string(PairingRejectionReason.invalidCredentials.rawValue))
        XCTAssertEqual(invalidCodeRejection?.payload["failed_attempts"], .number(1))
        let devicesAfterInvalidCode = try await store.load()
        XCTAssertEqual(devicesAfterInvalidCode, [])

        let validPublicKey = testClientPublicKeyBase64()
        router.handle(pairingEnvelope(
            requestID: "pair-valid-after-blank-fields",
            session: session,
            deviceID: "android-valid-after-blank",
            publicKey: validPublicKey
        ), sink: sink)

        let accepted = try await sink.waitForMessages(count: blankPayloads.count + 2).last
        XCTAssertEqual(accepted?.type, MessageType.pairingResult)
        XCTAssertEqual(accepted?.payload["accepted"], .bool(true))
        XCTAssertEqual(accepted?.payload["trusted_device_id"], .string("android-valid-after-blank"))
        let devicesAfterAcceptedPayload = try await store.load()
        XCTAssertEqual(devicesAfterAcceptedPayload.map(\.id), ["android-valid-after-blank"])
    }

    func testPairingRequestRejectsWhitespaceMutatedDeviceIdentityBeforeTrusting() async throws {
        let sink = RecordingSink()
        let coordinator = PairingCoordinator(maxFailedAttempts: 6)
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
        let invalidRequests = [
            pairingEnvelope(requestID: "pair-invalid-device-id", session: session, deviceID: " android-1"),
            pairingEnvelope(requestID: "pair-whitespace-public-key", session: session, publicKey: " public-key"),
            pairingEnvelope(requestID: "pair-invalid-public-key", session: session, publicKey: "public-key"),
            pairingEnvelope(requestID: "pair-non-p256-public-key", session: session, publicKey: "bm90LWEtUDI1Ni1rZXk=")
        ]

        for (index, envelope) in invalidRequests.enumerated() {
            router.handle(envelope, sink: sink)
            let rejection = try await sink.waitForMessages(count: index + 1).last
            XCTAssertEqual(rejection?.type, MessageType.pairingResult)
            XCTAssertEqual(rejection?.payload["accepted"], .bool(false))
            XCTAssertEqual(rejection?.payload["code"], .string(PairingRejectionReason.invalidDeviceIdentity.rawValue))
            XCTAssertEqual(rejection?.payload["retryable"], .bool(true))
        }
        let devicesAfterRejectedIdentities = try await store.load()
        XCTAssertTrue(devicesAfterRejectedIdentities.isEmpty)
        let validPublicKey = testClientPublicKeyBase64()

        router.handle(pairingEnvelope(
            requestID: "pair-valid-after-invalid-identity",
            session: session,
            deviceID: "android-1",
            deviceName: "  Android   Phone\nBeta  ",
            publicKey: validPublicKey
        ), sink: sink)

        let accepted = try await sink.waitForMessages(count: invalidRequests.count + 1).last
        XCTAssertEqual(accepted?.type, MessageType.pairingResult)
        XCTAssertEqual(accepted?.payload["accepted"], .bool(true))
        XCTAssertEqual(accepted?.payload["trusted_device_id"], .string("android-1"))
        let trustedDevices = try await store.load()
        let trusted = try XCTUnwrap(trustedDevices.first)
        XCTAssertEqual(trusted.id, "android-1")
        XCTAssertEqual(trusted.name, "Android Phone Beta")
        XCTAssertEqual(trusted.publicKeyBase64, validPublicKey)
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

    func testUnauthenticatedRuntimeCommandsRejectBeforeProtocolPayloadHandling() async throws {
        let runtimeCommandTypes = [
            MessageType.modelsList,
            MessageType.modelsPull,
            MessageType.routeRefresh,
            MessageType.chatSend,
            MessageType.chatCancel,
            MessageType.chatSessionsList,
            MessageType.chatMessagesList,
            MessageType.chatTitleRequest,
            MessageType.chatSessionRename,
            MessageType.chatSessionArchive,
            MessageType.chatSessionRestore,
            MessageType.chatSessionDelete,
            MessageType.memoryList,
            MessageType.memoryUpsert,
            MessageType.memoryDelete,
            MessageType.memorySummaryDraftsList,
            MessageType.memorySummaryDraftApprove,
            MessageType.memorySummaryDraftDismiss,
        ]

        for (index, type) in runtimeCommandTypes.enumerated() {
            let sink = RecordingSink()
            let router = LocalRuntimeMessageRouter(backend: MockBackend(status: .available))
            let requestID = "unauthenticated-runtime-command-\(index)"

            router.handle(ProtocolEnvelope(type: type, requestID: requestID), sink: sink)

            let message = try await sink.waitForMessages(count: 1).first
            XCTAssertEqual(message?.type, MessageType.error, "Expected unauthenticated \(type) to be rejected")
            XCTAssertEqual(message?.requestID, requestID)
            XCTAssertEqual(message?.payload["code"], .string("authentication_required"))
            XCTAssertEqual(message?.payload["retryable"], .bool(false))
        }
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

        let authMessage = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
            deviceID: "android-trusted",
            nonce: nonce
        )
        let authMessageData = try XCTUnwrap(authMessage.data(using: .utf8))
        let digest = SHA256.hash(data: authMessageData)
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

    func testHelloRejectsUnknownPayloadMetadataBeforeChallengeCreation() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await store.trust(TrustedDevice(
            id: "android-trusted",
            name: "Trusted Android",
            publicKeyBase64: privateKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-unknown-metadata",
            payload: [
                "device_id": .string("android-trusted"),
                "device_name": .string("Trusted Android"),
                "client_capabilities": .array([.string("chat")]),
                "nonce": .string("client-supplied-nonce"),
                "signature": .string("client-supplied-signature"),
                "runtime_signature": .string("forged-runtime-signature"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant")
            ]
        ), sink: sink)

        let rejected = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(rejected?.type, MessageType.error)
        XCTAssertEqual(rejected?.requestID, "hello-unknown-metadata")
        XCTAssertEqual(rejected?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(rejected?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: rejected?.payload).contains("nonce"))
        XCTAssertTrue(String(describing: rejected?.payload).contains("backend_url"))

        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-after-rejected-hello"), sink: sink)

        let unauthenticated = try await sink.waitForMessages(count: 2).last
        XCTAssertEqual(unauthenticated?.type, MessageType.error)
        XCTAssertEqual(unauthenticated?.payload["code"], .string("authentication_required"))

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-valid-after-unknown-metadata",
            payload: [
                "device_id": .string("android-trusted"),
                "device_name": .string("Trusted Android"),
                "client_capabilities": .array([.string("chat")])
            ]
        ), sink: sink)

        let challenge = try await sink.waitForMessages(count: 3).last
        XCTAssertEqual(challenge?.type, MessageType.authChallenge)
        XCTAssertEqual(challenge?.requestID, "hello-valid-after-unknown-metadata")
    }

    func testHelloRejectsInvalidAllowedPayloadTypesBeforeChallengeCreation() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await store.trust(TrustedDevice(
            id: "android-trusted",
            name: "Trusted Android",
            publicKeyBase64: privateKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: store
        )
        let invalidPayloads: [(requestID: String, payload: [String: JSONValue], marker: String)] = [
            (
                "hello-blank-device-id",
                [
                    "device_id": .string("   \n\t"),
                    "device_name": .string("Trusted Android"),
                    "client_capabilities": .array([.string("chat")])
                ],
                "device_id"
            ),
            (
                "hello-invalid-device-name-type",
                [
                    "device_id": .string("android-trusted"),
                    "device_name": .number(1),
                    "client_capabilities": .array([.string("chat")])
                ],
                "device_name"
            ),
            (
                "hello-blank-device-name",
                [
                    "device_id": .string("android-trusted"),
                    "device_name": .string("  \n\t"),
                    "client_capabilities": .array([.string("chat")])
                ],
                "device_name"
            ),
            (
                "hello-invalid-capabilities-type",
                [
                    "device_id": .string("android-trusted"),
                    "device_name": .string("Trusted Android"),
                    "client_capabilities": .string("chat")
                ],
                "client_capabilities"
            ),
            (
                "hello-invalid-capability-item",
                [
                    "device_id": .string("android-trusted"),
                    "device_name": .string("Trusted Android"),
                    "client_capabilities": .array([.string("chat"), .number(1)])
                ],
                "client_capabilities"
            ),
            (
                "hello-duplicate-capability",
                [
                    "device_id": .string("android-trusted"),
                    "device_name": .string("Trusted Android"),
                    "client_capabilities": .array([.string("chat"), .string("chat")])
                ],
                "client_capabilities"
            )
        ]

        for (index, invalidPayload) in invalidPayloads.enumerated() {
            router.handle(ProtocolEnvelope(
                type: MessageType.hello,
                requestID: invalidPayload.requestID,
                payload: invalidPayload.payload
            ), sink: sink)

            let rejected = try await sink.waitForMessages(count: index + 1).last
            XCTAssertEqual(rejected?.type, MessageType.error)
            XCTAssertEqual(rejected?.requestID, invalidPayload.requestID)
            XCTAssertEqual(rejected?.payload["code"], .string("invalid_payload"))
            XCTAssertEqual(rejected?.payload["retryable"], .bool(false))
            XCTAssertTrue(String(describing: rejected?.payload).contains(invalidPayload.marker))
        }

        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-after-invalid-hello"), sink: sink)

        let unauthenticated = try await sink.waitForMessages(count: invalidPayloads.count + 1).last
        XCTAssertEqual(unauthenticated?.type, MessageType.error)
        XCTAssertEqual(unauthenticated?.payload["code"], .string("authentication_required"))

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-valid-after-invalid-allowed-types",
            payload: ["device_id": .string("android-trusted")]
        ), sink: sink)

        let challenge = try await sink.waitForMessages(count: invalidPayloads.count + 2).last
        XCTAssertEqual(challenge?.type, MessageType.authChallenge)
        XCTAssertEqual(challenge?.requestID, "hello-valid-after-invalid-allowed-types")
    }

    func testAuthResponseRejectsUnknownPayloadMetadataBeforeAuthentication() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
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
            requestID: "hello-before-auth-unknown-metadata",
            payload: ["device_id": .string("android-trusted")]
        ), sink: sink)

        let challenge = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(challenge?.type, MessageType.authChallenge)
        guard case .string(let nonce)? = challenge?.payload["nonce"] else {
            XCTFail("Expected nonce in auth challenge")
            return
        }
        let authMessage = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
            deviceID: "android-trusted",
            nonce: nonce
        )
        let authMessageData = try XCTUnwrap(authMessage.data(using: .utf8))
        let signature = try privateKey
            .signature(for: SHA256.hash(data: authMessageData))
            .derRepresentation
            .base64EncodedString()

        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-unknown-metadata",
            payload: [
                "device_id": .string("android-trusted"),
                "nonce": .string(nonce),
                "signature": .string(signature),
                "accepted": .bool(true),
                "runtime_signature": .string("forged-runtime-signature"),
                "backend_url": .string("http://127.0.0.1:11434"),
                "provider_url": .string("http://provider.example.invalid/v1"),
                "route_token": .string("future-route-token"),
                "relay_secret": .string("future-relay-secret"),
                "workspace_id": .string("workspace-1"),
                "permission_grant": .string("future permission grant")
            ]
        ), sink: sink)

        let rejected = try await sink.waitForMessages(count: 2).last
        XCTAssertEqual(rejected?.type, MessageType.error)
        XCTAssertEqual(rejected?.requestID, "auth-unknown-metadata")
        XCTAssertEqual(rejected?.payload["code"], .string("invalid_payload"))
        XCTAssertEqual(rejected?.payload["retryable"], .bool(false))
        XCTAssertTrue(String(describing: rejected?.payload).contains("accepted"))
        XCTAssertTrue(String(describing: rejected?.payload).contains("backend_url"))

        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-after-rejected-auth"), sink: sink)

        let unauthenticated = try await sink.waitForMessages(count: 3).last
        XCTAssertEqual(unauthenticated?.type, MessageType.error)
        XCTAssertEqual(unauthenticated?.payload["code"], .string("authentication_required"))

        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-valid-after-unknown-metadata",
            payload: [
                "device_id": .string("android-trusted"),
                "nonce": .string(nonce),
                "signature": .string(signature)
            ]
        ), sink: sink)

        let accepted = try await sink.waitForMessages(count: 4).last
        XCTAssertEqual(accepted?.type, MessageType.authResponse)
        XCTAssertEqual(accepted?.payload["accepted"], .bool(true))
    }

    func testAuthResponseRejectsBlankAllowedFieldsBeforeAuthentication() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
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
            requestID: "hello-before-auth-invalid-allowed-types",
            payload: ["device_id": .string("android-trusted")]
        ), sink: sink)

        let challenge = try await sink.waitForMessages(count: 1).first
        XCTAssertEqual(challenge?.type, MessageType.authChallenge)
        guard case .string(let nonce)? = challenge?.payload["nonce"] else {
            XCTFail("Expected nonce in auth challenge")
            return
        }
        let authMessage = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
            deviceID: "android-trusted",
            nonce: nonce
        )
        let authMessageData = try XCTUnwrap(authMessage.data(using: .utf8))
        let signature = try privateKey
            .signature(for: SHA256.hash(data: authMessageData))
            .derRepresentation
            .base64EncodedString()
        let invalidPayloads: [(requestID: String, payload: [String: JSONValue], marker: String)] = [
            (
                "auth-blank-device-id",
                [
                    "device_id": .string("   \n\t"),
                    "nonce": .string(nonce),
                    "signature": .string(signature)
                ],
                "device_id"
            ),
            (
                "auth-blank-nonce",
                [
                    "device_id": .string("android-trusted"),
                    "nonce": .string("  \n\t"),
                    "signature": .string(signature)
                ],
                "nonce"
            ),
            (
                "auth-blank-signature",
                [
                    "device_id": .string("android-trusted"),
                    "nonce": .string(nonce),
                    "signature": .string("  \n\t")
                ],
                "signature"
            ),
            (
                "auth-invalid-signature-type",
                [
                    "device_id": .string("android-trusted"),
                    "nonce": .string(nonce),
                    "signature": .number(1)
                ],
                "signature"
            )
        ]

        for (index, invalidPayload) in invalidPayloads.enumerated() {
            router.handle(ProtocolEnvelope(
                type: MessageType.authResponse,
                requestID: invalidPayload.requestID,
                payload: invalidPayload.payload
            ), sink: sink)

            let rejected = try await sink.waitForMessages(count: index + 2).last
            XCTAssertEqual(rejected?.type, MessageType.error)
            XCTAssertEqual(rejected?.requestID, invalidPayload.requestID)
            XCTAssertEqual(rejected?.payload["code"], .string("invalid_payload"))
            XCTAssertEqual(rejected?.payload["retryable"], .bool(false))
            XCTAssertTrue(String(describing: rejected?.payload).contains(invalidPayload.marker))
        }

        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-after-invalid-auth"), sink: sink)

        let unauthenticated = try await sink.waitForMessages(count: invalidPayloads.count + 2).last
        XCTAssertEqual(unauthenticated?.type, MessageType.error)
        XCTAssertEqual(unauthenticated?.payload["code"], .string("authentication_required"))

        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-valid-after-invalid-allowed-types",
            payload: [
                "device_id": .string("android-trusted"),
                "nonce": .string(nonce),
                "signature": .string(signature)
            ]
        ), sink: sink)

        let accepted = try await sink.waitForMessages(count: invalidPayloads.count + 3).last
        XCTAssertEqual(accepted?.type, MessageType.authResponse)
        XCTAssertEqual(accepted?.requestID, "auth-valid-after-invalid-allowed-types")
        XCTAssertEqual(accepted?.payload["accepted"], .bool(true))
    }

    func testAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory() async throws {
        let deviceAKey = P256.Signing.PrivateKey()
        let deviceBKey = P256.Signing.PrivateKey()
        let trustedStore = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await trustedStore.trust(TrustedDevice(
            id: "device-a",
            name: "Device A",
            publicKeyBase64: deviceAKey.publicKey.derRepresentation.base64EncodedString()
        ))
        try await trustedStore.trust(TrustedDevice(
            id: "device-b",
            name: "Device B",
            publicKeyBase64: deviceBKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let chatStore = JSONLRuntimeChatEventStore(fileURL: FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-chat-events.jsonl"))
        let memoryStore = JSONLRuntimeMemoryStore(fileURL: FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("runtime-memory-events.jsonl"))
        let capturedRequests = LockedBox<[ChatRequest]>([])
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(
                models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
                chatEvents: [.done(inputTokens: 1, outputTokens: 1)],
                onChatRequest: { request in
                    capturedRequests.value = capturedRequests.value + [request]
                }
            ),
            trustedDeviceStore: trustedStore,
            chatEventStore: chatStore,
            memoryStore: memoryStore
        )
        let sinkA = RecordingSink()
        let sinkB = RecordingSink()
        try await authenticateTrustedDevice(router: router, sink: sinkA, deviceID: "device-a", privateKey: deviceAKey)
        try await authenticateTrustedDevice(router: router, sink: sinkB, deviceID: "device-b", privateKey: deviceBKey)

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryUpsert,
            requestID: "memory-a-upsert",
            payload: [
                "id": .string("same-memory-id"),
                "content": .string("Device A private memory."),
                "enabled": .bool(true)
            ]
        ), sink: sinkA)
        let memoryAUpsert = try await sinkA.waitForMessages(count: 3).last
        XCTAssertEqual(memoryAUpsert?.type, MessageType.memoryUpsert)

        router.handle(ProtocolEnvelope(type: MessageType.memoryList, requestID: "memory-b-empty"), sink: sinkB)
        let emptyMemoryB = try await sinkB.waitForMessages(count: 3).last
        guard case .array(let emptyEntries)? = emptyMemoryB?.payload["entries"] else {
            XCTFail("Expected empty memory list")
            return
        }
        XCTAssertTrue(emptyEntries.isEmpty)

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryUpsert,
            requestID: "memory-b-upsert",
            payload: [
                "id": .string("same-memory-id"),
                "content": .string("Device B private memory."),
                "enabled": .bool(true)
            ]
        ), sink: sinkB)
        _ = try await sinkB.waitForMessages(count: 4)

        router.handle(ProtocolEnvelope(type: MessageType.memoryList, requestID: "memory-a-list"), sink: sinkA)
        let memoryAList = try await sinkA.waitForMessages(count: 4).last
        guard case .array(let memoryAEntries)? = memoryAList?.payload["entries"],
              case .object(let memoryAEntry)? = memoryAEntries.first else {
            XCTFail("Expected device A memory entry")
            return
        }
        XCTAssertEqual(memoryAEntries.count, 1)
        XCTAssertEqual(memoryAEntry["id"], .string("same-memory-id"))
        XCTAssertEqual(memoryAEntry["content"], .string("Device A private memory."))

        router.handle(ProtocolEnvelope(type: MessageType.memoryList, requestID: "memory-b-list"), sink: sinkB)
        let memoryBList = try await sinkB.waitForMessages(count: 5).last
        guard case .array(let memoryBEntries)? = memoryBList?.payload["entries"],
              case .object(let memoryBEntry)? = memoryBEntries.first else {
            XCTFail("Expected device B memory entry")
            return
        }
        XCTAssertEqual(memoryBEntries.count, 1)
        XCTAssertEqual(memoryBEntry["id"], .string("same-memory-id"))
        XCTAssertEqual(memoryBEntry["content"], .string("Device B private memory."))

        router.handle(chatSendEnvelope(
            requestID: "chat-device-a",
            sessionID: "session-device-a",
            content: "Use device A memory."
        ), sink: sinkA)
        let chatDeviceAResponse = try await sinkA.waitForMessages(count: 5).last
        XCTAssertEqual(chatDeviceAResponse?.type, MessageType.chatDone)

        router.handle(ProtocolEnvelope(type: MessageType.chatSessionsList, requestID: "sessions-b-empty"), sink: sinkB)
        let sessionsBEmpty = try await sinkB.waitForMessages(count: 6).last
        XCTAssertEqual(sessionsBEmpty?.payload["sessions"], .array([]))

        router.handle(ProtocolEnvelope(
            type: MessageType.chatMessagesList,
            requestID: "messages-b-a",
            payload: ["session_id": .string("session-device-a")]
        ), sink: sinkB)
        let messagesBA = try await sinkB.waitForMessages(count: 7).last
        XCTAssertEqual(messagesBA?.payload["messages"], .array([]))

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionRename,
            requestID: "rename-b-a",
            payload: [
                "session_id": .string("session-device-a"),
                "title": .string("B cannot rename A")
            ]
        ), sink: sinkB)
        let renameBAResponse = try await sinkB.waitForMessages(count: 8).last
        XCTAssertEqual(renameBAResponse?.payload["code"], .string("chat_session_not_found"))

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionArchive,
            requestID: "archive-b-a",
            payload: ["session_id": .string("session-device-a")]
        ), sink: sinkB)
        let archiveBAResponse = try await sinkB.waitForMessages(count: 9).last
        XCTAssertEqual(archiveBAResponse?.payload["code"], .string("chat_session_not_found"))

        router.handle(ProtocolEnvelope(
            type: MessageType.chatSessionDelete,
            requestID: "delete-b-a",
            payload: ["session_id": .string("session-device-a")]
        ), sink: sinkB)
        let deleteBAResponse = try await sinkB.waitForMessages(count: 10).last
        XCTAssertEqual(deleteBAResponse?.payload["code"], .string("chat_session_not_found"))

        router.handle(chatSendEnvelope(
            requestID: "chat-device-b",
            sessionID: "session-device-b",
            content: "Use device B memory."
        ), sink: sinkB)
        let chatDeviceBResponse = try await sinkB.waitForMessages(count: 11).last
        XCTAssertEqual(chatDeviceBResponse?.type, MessageType.chatDone)

        router.handle(ProtocolEnvelope(type: MessageType.chatSessionsList, requestID: "sessions-a"), sink: sinkA)
        let sessionsA = try await sinkA.waitForMessages(count: 6).last
        guard case .array(let sessionsAArray)? = sessionsA?.payload["sessions"],
              case .object(let sessionA)? = sessionsAArray.first else {
            XCTFail("Expected device A session")
            return
        }
        XCTAssertEqual(sessionsAArray.count, 1)
        XCTAssertEqual(sessionA["session_id"], .string("session-device-a"))

        router.handle(ProtocolEnvelope(type: MessageType.chatSessionsList, requestID: "sessions-b"), sink: sinkB)
        let sessionsB = try await sinkB.waitForMessages(count: 12).last
        guard case .array(let sessionsBArray)? = sessionsB?.payload["sessions"],
              case .object(let sessionB)? = sessionsBArray.first else {
            XCTFail("Expected device B session")
            return
        }
        XCTAssertEqual(sessionsBArray.count, 1)
        XCTAssertEqual(sessionB["session_id"], .string("session-device-b"))

        let requestA = try XCTUnwrap(capturedRequests.value.first { $0.generationID == "chat-device-a" })
        let requestB = try XCTUnwrap(capturedRequests.value.first { $0.generationID == "chat-device-b" })
        XCTAssertTrue(requestA.messages.contains { $0.content.contains("Device A private memory.") })
        XCTAssertFalse(requestA.messages.contains { $0.content.contains("Device B private memory.") })
        XCTAssertTrue(requestB.messages.contains { $0.content.contains("Device B private memory.") })
        XCTAssertFalse(requestB.messages.contains { $0.content.contains("Device A private memory.") })
    }

    func testTrustedAuthResponseRejectsRawNonceSignature() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await store.trust(TrustedDevice(
            id: "android-raw-nonce",
            name: "Raw Nonce Client",
            publicKeyBase64: publicKeyBase64
        ))
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-raw-nonce",
            payload: ["device_id": .string("android-raw-nonce")]
        ), sink: sink)

        let challenge = try await sink.waitForMessages(count: 1).first
        guard case .string(let nonce)? = challenge?.payload["nonce"],
              let nonceData = nonce.data(using: .utf8) else {
            XCTFail("Expected nonce in auth challenge")
            return
        }

        let rawNonceSignature = try privateKey
            .signature(for: SHA256.hash(data: nonceData))
            .derRepresentation
            .base64EncodedString()
        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-raw-nonce",
            payload: [
                "device_id": .string("android-raw-nonce"),
                "nonce": .string(nonce),
                "signature": .string(rawNonceSignature)
            ]
        ), sink: sink)

        let authMessages = try await sink.waitForMessages(count: 2)
        XCTAssertEqual(authMessages.last?.type, MessageType.error)
        XCTAssertEqual(authMessages.last?.payload["code"], .string("authentication_failed"))

        router.handle(ProtocolEnvelope(type: MessageType.modelsList, requestID: "models-after-raw-nonce"), sink: sink)

        let runtimeMessages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(runtimeMessages.last?.type, MessageType.error)
        XCTAssertEqual(runtimeMessages.last?.payload["code"], .string("authentication_required"))
    }

    func testTrustedAuthResponseRejectsReplayedNonceAfterAuthentication() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await store.trust(TrustedDevice(
            id: "android-replay",
            name: "Replay Client",
            publicKeyBase64: publicKeyBase64
        ))
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-replay",
            payload: ["device_id": .string("android-replay")]
        ), sink: sink)

        let challenge = try await sink.waitForMessages(count: 1).first
        guard case .string(let nonce)? = challenge?.payload["nonce"] else {
            XCTFail("Expected nonce in auth challenge")
            return
        }
        let authMessage = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
            deviceID: "android-replay",
            nonce: nonce
        )
        let authMessageData = try XCTUnwrap(authMessage.data(using: .utf8))
        let signature = try privateKey
            .signature(for: SHA256.hash(data: authMessageData))
            .derRepresentation
            .base64EncodedString()
        let authPayload: [String: JSONValue] = [
            "device_id": .string("android-replay"),
            "nonce": .string(nonce),
            "signature": .string(signature)
        ]

        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-replay-first",
            payload: authPayload
        ), sink: sink)

        let authMessages = try await sink.waitForMessages(count: 2)
        XCTAssertEqual(authMessages.last?.type, MessageType.authResponse)
        XCTAssertEqual(authMessages.last?.payload["accepted"], .bool(true))

        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-replay-second",
            payload: authPayload
        ), sink: sink)

        let replayMessages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(replayMessages.last?.type, MessageType.error)
        XCTAssertEqual(replayMessages.last?.requestID, "auth-replay-second")
        XCTAssertEqual(replayMessages.last?.payload["code"], .string("authentication_failed"))

        router.handle(ProtocolEnvelope(type: MessageType.modelsList, requestID: "models-after-replay"), sink: sink)

        let runtimeMessages = try await sink.waitForMessages(count: 4)
        XCTAssertEqual(runtimeMessages.last?.type, MessageType.modelsList)
    }

    func testTrustedAuthResponseRejectsSupersededChallengeNonce() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await store.trust(TrustedDevice(
            id: "android-superseded",
            name: "Superseded Nonce Client",
            publicKeyBase64: publicKeyBase64
        ))
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-superseded-1",
            payload: ["device_id": .string("android-superseded")]
        ), sink: sink)
        let firstChallenge = try await sink.waitForMessages(count: 1).first
        guard case .string(let firstNonce)? = firstChallenge?.payload["nonce"] else {
            XCTFail("Expected first nonce in auth challenge")
            return
        }

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-superseded-2",
            payload: ["device_id": .string("android-superseded")]
        ), sink: sink)
        let secondChallenge = try await sink.waitForMessages(count: 2).last
        guard case .string(let secondNonce)? = secondChallenge?.payload["nonce"] else {
            XCTFail("Expected second nonce in auth challenge")
            return
        }
        XCTAssertNotEqual(firstNonce, secondNonce)

        let staleAuthMessage = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
            deviceID: "android-superseded",
            nonce: firstNonce
        )
        let staleAuthMessageData = try XCTUnwrap(staleAuthMessage.data(using: .utf8))
        let staleSignature = try privateKey
            .signature(for: SHA256.hash(data: staleAuthMessageData))
            .derRepresentation
            .base64EncodedString()
        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-superseded-stale",
            payload: [
                "device_id": .string("android-superseded"),
                "nonce": .string(firstNonce),
                "signature": .string(staleSignature)
            ]
        ), sink: sink)

        let staleMessages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(staleMessages.last?.type, MessageType.error)
        XCTAssertEqual(staleMessages.last?.payload["code"], .string("authentication_failed"))

        let freshAuthMessage = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
            deviceID: "android-superseded",
            nonce: secondNonce
        )
        let freshAuthMessageData = try XCTUnwrap(freshAuthMessage.data(using: .utf8))
        let freshSignature = try privateKey
            .signature(for: SHA256.hash(data: freshAuthMessageData))
            .derRepresentation
            .base64EncodedString()
        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-superseded-fresh",
            payload: [
                "device_id": .string("android-superseded"),
                "nonce": .string(secondNonce),
                "signature": .string(freshSignature)
            ]
        ), sink: sink)

        let freshMessages = try await sink.waitForMessages(count: 4)
        XCTAssertEqual(freshMessages.last?.type, MessageType.authResponse)
        XCTAssertEqual(freshMessages.last?.payload["accepted"], .bool(true))
    }

    func testConnectionDidCloseClearsAuthenticatedSession() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await store.trust(TrustedDevice(
            id: "android-disconnect",
            name: "Disconnect Client",
            publicKeyBase64: publicKeyBase64
        ))
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available),
            trustedDeviceStore: store
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-disconnect",
            payload: ["device_id": .string("android-disconnect")]
        ), sink: sink)

        let challenge = try await sink.waitForMessages(count: 1).first
        guard case .string(let nonce)? = challenge?.payload["nonce"] else {
            XCTFail("Expected nonce in auth challenge")
            return
        }
        let authMessage = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
            deviceID: "android-disconnect",
            nonce: nonce
        )
        let authMessageData = try XCTUnwrap(authMessage.data(using: .utf8))
        let signature = try privateKey
            .signature(for: SHA256.hash(data: authMessageData))
            .derRepresentation
            .base64EncodedString()
        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-disconnect",
            payload: [
                "device_id": .string("android-disconnect"),
                "nonce": .string(nonce),
                "signature": .string(signature)
            ]
        ), sink: sink)

        let authMessages = try await sink.waitForMessages(count: 2)
        XCTAssertEqual(authMessages.last?.type, MessageType.authResponse)
        XCTAssertEqual(authMessages.last?.payload["accepted"], .bool(true))

        router.connectionDidClose(sink.connectionID)
        router.handle(ProtocolEnvelope(type: MessageType.modelsList, requestID: "models-after-disconnect"), sink: sink)

        let runtimeMessages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(runtimeMessages.last?.type, MessageType.error)
        XCTAssertEqual(runtimeMessages.last?.requestID, "models-after-disconnect")
        XCTAssertEqual(runtimeMessages.last?.payload["code"], .string("authentication_required"))
    }

    func testRemovedTrustedDeviceCannotContinueUsingAuthenticatedConnection() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
        let store = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await store.trust(TrustedDevice(
            id: "android-revoked",
            name: "Revoked Client",
            publicKeyBase64: publicKeyBase64
        ))
        let sink = RecordingSink()
        let router = LocalRuntimeMessageRouter(
            backend: MockBackend(status: .available, models: [
                ModelInfo(id: "llama3.1:8b", name: "Llama 3.1", sizeBytes: nil, modifiedAt: nil)
            ]),
            trustedDeviceStore: store
        )
        try await authenticateTrustedDevice(
            router: router,
            sink: sink,
            deviceID: "android-revoked",
            privateKey: privateKey
        )

        router.handle(ProtocolEnvelope(type: MessageType.modelsList, requestID: "models-before-revoke"), sink: sink)
        let modelsResponse = try await sink.waitForMessages(count: 3).last
        XCTAssertEqual(modelsResponse?.type, MessageType.modelsList)

        try await store.remove(deviceID: "android-revoked")
        router.handle(ProtocolEnvelope(type: MessageType.runtimeHealth, requestID: "health-after-revoke"), sink: sink)

        let revokedResponse = try await sink.waitForMessages(count: 4).last
        XCTAssertEqual(revokedResponse?.type, MessageType.error)
        XCTAssertEqual(revokedResponse?.requestID, "health-after-revoke")
        XCTAssertEqual(revokedResponse?.payload["code"], .string("pairing_required"))

        router.handle(ProtocolEnvelope(type: MessageType.modelsList, requestID: "models-after-revoke"), sink: sink)

        let clearedSessionResponse = try await sink.waitForMessages(count: 5).last
        XCTAssertEqual(clearedSessionResponse?.type, MessageType.error)
        XCTAssertEqual(clearedSessionResponse?.requestID, "models-after-revoke")
        XCTAssertEqual(clearedSessionResponse?.payload["code"], .string("authentication_required"))
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
        XCTAssertEqual(model.remoteRoutePreparationIssue?.kind, .automaticPreparationUnavailable)
        XCTAssertNil(model.remoteRoutePreparationIssue?.endpoint)
        XCTAssertEqual(
            model.remoteRoutePreparationIssue?.message,
            "Configure a reachable remote route before generating a remote pairing QR."
        )
        XCTAssertEqual(model.logs.first, "Remote pairing QR not generated: configure a reachable remote route first")
    }

    @MainActor
    func testCompanionAppModelPublishesRuntimeDataSummaryFromInjectedStores() throws {
        let chatStore = JSONLRuntimeChatEventStore(
            fileURL: FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathComponent("runtime-chat-events.jsonl")
        )
        try chatStore.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 100),
            kind: .request,
            requestID: "request-active",
            sessionID: "active-1",
            model: "llama",
            messages: [ChatMessage(role: "user", content: "Active device-scoped chat.")],
            ownerDeviceID: "device-a"
        ))
        try chatStore.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 101),
            kind: .request,
            requestID: "request-archived",
            sessionID: "archived-1",
            model: "llama",
            messages: [ChatMessage(role: "user", content: "Archived device-scoped chat.")],
            ownerDeviceID: "device-a"
        ))
        _ = try chatStore.mutateSession(
            ownerDeviceID: "device-a",
            sessionID: "archived-1",
            requestID: "archive-archived",
            mutation: .archive,
            timestamp: Date(timeIntervalSince1970: 102)
        )
        XCTAssertTrue(try chatStore.listSessions(limit: 10, includeArchived: true).isEmpty)
        let memoryStore = JSONLRuntimeMemoryStore(
            fileURL: FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathComponent("runtime-memory-events.jsonl")
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: "device-a",
            id: "memory-enabled",
            content: "Use Korean UI.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 103)
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: "device-a",
            id: "memory-paused",
            content: "Paused detail.",
            enabled: false,
            timestamp: Date(timeIntervalSince1970: 104)
        )
        XCTAssertTrue(try memoryStore.list().isEmpty)

        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeChatEventStore: chatStore,
            runtimeMemoryStore: memoryStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        XCTAssertEqual(model.runtimeDataSummary.activeChatSessionCount, 1)
        XCTAssertEqual(model.runtimeDataSummary.archivedChatSessionCount, 1)
        XCTAssertEqual(model.runtimeChatSessions.map(\.sessionID), ["archived-1", "active-1"])
        XCTAssertEqual(model.runtimeChatSessions.map(\.status), ["archived", "active"])
        XCTAssertEqual(model.runtimeChatSessions.map(\.messageCount), [1, 1])
        XCTAssertNil(model.runtimeChatSessionsError)
        XCTAssertEqual(model.runtimeDataSummary.enabledMemoryCount, 1)
        XCTAssertEqual(model.runtimeDataSummary.pausedMemoryCount, 1)
        XCTAssertEqual(model.runtimeMemoryEntries.map(\.id), ["memory-paused", "memory-enabled"])
        XCTAssertEqual(model.runtimeMemoryEntries.map(\.content), ["Paused detail.", "Use Korean UI."])
        XCTAssertEqual(model.runtimeMemoryEntries.map(\.enabled), [false, true])
        XCTAssertNil(model.runtimeMemoryEntriesError)
        XCTAssertNotNil(model.runtimeDataSummary.lastRefreshedAt)
        XCTAssertNil(model.runtimeDataSummary.errorMessage)
    }

    @MainActor
    func testCompanionAppModelPublishesRuntimeHistoryTranscriptPreviewAcrossOwners() throws {
        let chatStore = JSONLRuntimeChatEventStore(
            fileURL: FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathComponent("runtime-chat-events.jsonl")
        )
        try chatStore.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 100),
            kind: .request,
            requestID: "request-preview",
            sessionID: "session-preview",
            model: "llama",
            messages: [ChatMessage(role: "user", content: "Explain the runtime boundary.")],
            ownerDeviceID: "device-a"
        ))
        try chatStore.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 101),
            kind: .reasoningDelta,
            requestID: "request-preview",
            sessionID: "session-preview",
            model: "llama",
            reasoningDelta: "Think first.",
            ownerDeviceID: "device-a"
        ))
        try chatStore.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 102),
            kind: .assistantDelta,
            requestID: "request-preview",
            sessionID: "session-preview",
            model: "llama",
            delta: "Runtime owns model access.",
            ownerDeviceID: "device-a"
        ))
        try chatStore.append(RuntimeChatStoredEvent(
            timestamp: Date(timeIntervalSince1970: 103),
            kind: .done,
            requestID: "request-preview",
            sessionID: "session-preview",
            model: "llama",
            ownerDeviceID: "device-a"
        ))
        XCTAssertTrue(try chatStore.listMessages(sessionID: "session-preview", limit: 10).isEmpty)

        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeChatEventStore: chatStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.refreshRuntimeChatTranscriptPreview(sessionID: "session-preview", limit: 10)

        let messages = try XCTUnwrap(model.runtimeChatTranscriptMessages["session-preview"])
        XCTAssertEqual(messages.map(\.role), ["user", "assistant"])
        XCTAssertEqual(messages.map(\.content), ["Explain the runtime boundary.", "Runtime owns model access."])
        XCTAssertEqual(messages.last?.reasoning, "Think first.")
        XCTAssertNil(model.runtimeChatTranscriptErrors["session-preview"])
    }

    @MainActor
    func testCompanionAppModelPublishesRuntimeHistoryInspectorError() throws {
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeChatEventStore: FailingRuntimeChatEventStore(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.refreshRuntimeChatSessions()

        XCTAssertTrue(model.runtimeChatSessions.isEmpty)
        XCTAssertEqual(model.runtimeChatSessionsError, "chat store read failed")
        XCTAssertEqual(model.runtimeDataSummary.errorMessage, "chat store read failed")

        model.refreshRuntimeChatTranscriptPreview(sessionID: "broken-session")

        XCTAssertEqual(model.runtimeChatTranscriptMessages["broken-session"], [])
        XCTAssertEqual(model.runtimeChatTranscriptErrors["broken-session"], "chat store messages failed")
    }

    @MainActor
    func testCompanionAppModelPublishesRuntimeMemoryInspectorError() throws {
        let chatStore = JSONLRuntimeChatEventStore(
            fileURL: FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathComponent("runtime-chat-events.jsonl")
        )
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeChatEventStore: chatStore,
            runtimeMemoryStore: FailingRuntimeMemoryStore(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.refreshRuntimeMemoryEntries()

        XCTAssertTrue(model.runtimeMemoryEntries.isEmpty)
        XCTAssertEqual(model.runtimeMemoryEntriesError, "memory store read failed")
        XCTAssertEqual(model.runtimeDataSummary.errorMessage, "memory store read failed")
    }

    @MainActor
    func testCompanionAppModelRefreshRuntimeMemoryEntriesClearsRecoveredSummaryError() throws {
        let memoryStore = SequencedRuntimeMemoryStore(results: [
            .failure(testRuntimeInspectorError("memory store read failed")),
            .success([
                RuntimeMemoryEntry(
                    id: "memory-enabled",
                    content: "Recovered runtime memory.",
                    enabled: true,
                    createdAt: Date(timeIntervalSince1970: 100),
                    updatedAt: Date(timeIntervalSince1970: 100)
                )
            ])
        ])
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeChatEventStore: NullRuntimeChatEventStore(),
            runtimeMemoryStore: memoryStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )
        XCTAssertEqual(model.runtimeDataSummary.errorMessage, "memory store read failed")

        model.refreshRuntimeMemoryEntries()

        XCTAssertNil(model.runtimeMemoryEntriesError)
        XCTAssertNil(model.runtimeDataSummary.errorMessage)
        XCTAssertEqual(model.runtimeDataSummary.enabledMemoryCount, 1)
        XCTAssertEqual(model.runtimeDataSummary.pausedMemoryCount, 0)
    }

    @MainActor
    func testCompanionAppModelRefreshRuntimeChatSessionsClearsRecoveredSummaryError() throws {
        let chatStore = SequencedRuntimeChatEventStore(results: [
            .failure(testRuntimeInspectorError("chat store read failed")),
            .success([
                RuntimeChatStoredSession(
                    sessionID: "session-recovered",
                    title: "Recovered session",
                    model: "llama",
                    lastActivityAt: Date(timeIntervalSince1970: 100),
                    messageCount: 1
                )
            ])
        ])
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeChatEventStore: chatStore,
            runtimeMemoryStore: NullRuntimeMemoryStore(),
            runtimeRouteHostProvider: { "192.168.1.44" }
        )
        XCTAssertEqual(model.runtimeDataSummary.errorMessage, "chat store read failed")

        model.refreshRuntimeChatSessions()

        XCTAssertNil(model.runtimeChatSessionsError)
        XCTAssertNil(model.runtimeDataSummary.errorMessage)
        XCTAssertEqual(model.runtimeDataSummary.activeChatSessionCount, 1)
        XCTAssertEqual(model.runtimeDataSummary.archivedChatSessionCount, 0)
    }

    @MainActor
    func testCompanionAppModelRefreshRuntimeMemoryEntriesPreservesChatSummaryError() throws {
        let chatStore = FailingRuntimeChatEventStore()
        let memoryStore = SequencedRuntimeMemoryStore(results: [
            .failure(testRuntimeInspectorError("memory store read failed")),
            .success([
                RuntimeMemoryEntry(
                    id: "memory-recovered",
                    content: "Recovered while chat history is still unavailable.",
                    enabled: false,
                    createdAt: Date(timeIntervalSince1970: 100),
                    updatedAt: Date(timeIntervalSince1970: 101)
                )
            ])
        ])
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeChatEventStore: chatStore,
            runtimeMemoryStore: memoryStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )
        XCTAssertEqual(model.runtimeDataSummary.errorMessage, "chat store read failed")
        XCTAssertEqual(model.runtimeMemoryEntriesError, "memory store read failed")

        model.refreshRuntimeMemoryEntries()

        XCTAssertNil(model.runtimeMemoryEntriesError)
        XCTAssertEqual(model.runtimeChatSessionsError, "chat store read failed")
        XCTAssertEqual(model.runtimeDataSummary.errorMessage, "chat store read failed")
        XCTAssertEqual(model.runtimeDataSummary.enabledMemoryCount, 0)
        XCTAssertEqual(model.runtimeDataSummary.pausedMemoryCount, 1)
    }

    @MainActor
    func testCompanionAppModelRefreshRuntimeChatSessionsPreservesMemorySummaryError() throws {
        let chatStore = SequencedRuntimeChatEventStore(results: [
            .failure(testRuntimeInspectorError("chat store read failed")),
            .success([
                RuntimeChatStoredSession(
                    sessionID: "session-recovered-with-memory-error",
                    title: "Recovered chat",
                    model: "llama",
                    lastActivityAt: Date(timeIntervalSince1970: 100),
                    messageCount: 1
                )
            ])
        ])
        let memoryStore = FailingRuntimeMemoryStore()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            runtimeChatEventStore: chatStore,
            runtimeMemoryStore: memoryStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )
        XCTAssertEqual(model.runtimeDataSummary.errorMessage, "chat store read failed")
        XCTAssertEqual(model.runtimeMemoryEntriesError, "memory store read failed")

        model.refreshRuntimeChatSessions()

        XCTAssertNil(model.runtimeChatSessionsError)
        XCTAssertEqual(model.runtimeMemoryEntriesError, "memory store read failed")
        XCTAssertEqual(model.runtimeDataSummary.errorMessage, "memory store read failed")
        XCTAssertEqual(model.runtimeDataSummary.activeChatSessionCount, 1)
        XCTAssertEqual(model.runtimeDataSummary.archivedChatSessionCount, 0)
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
        XCTAssertEqual(model.logs.first, "Remote pairing QR not generated: Route allocator offline")
        XCTAssertTrue(model.logs.contains("Remote pairing QR not generated: Route allocator offline"))
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
                relayID: "relay-opaque-bootstrap",
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
        XCTAssertEqual(qrItems["relay_id"], "relay-opaque-bootstrap")
        XCTAssertNotEqual(qrItems["relay_id"], qrItems["route_token"])
        XCTAssertEqual(qrItems["relay_secret"], "allocated-secret-1")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "allocated-nonce-1")
        XCTAssertEqual(qrItems["relay_scope"], "remote")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
        assertStoredRelaySecret("allocated-secret-1", defaults: defaults, store: relaySecretStore)
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.lease_expires_at"), 4_102_444_800_000)
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.lease_nonce"), "allocated-nonce-1")
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.lease_host"), "relay.example.test")
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.lease_port"), 443)
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.lease_id"), "relay-opaque-bootstrap")

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
    func testCompanionAppModelAcceptsAdvancingSavedBootstrapLeaseForStableRelayID() async throws {
        let defaults = try isolatedDefaults()
        let nearExpiryEpochMillis = Int64(
            (Date().addingTimeInterval(60).timeIntervalSince1970 * 1000).rounded()
        )
        defaults.set("saved-secret", forKey: "aetherlink.relay.secret")
        defaults.set(nearExpiryEpochMillis, forKey: "aetherlink.relay.lease_expires_at")
        defaults.set("nonce-current", forKey: "aetherlink.relay.lease_nonce")
        defaults.set("relay.example.test", forKey: "aetherlink.relay.lease_host")
        defaults.set(443, forKey: "aetherlink.relay.lease_port")
        defaults.set("relay-stable", forKey: "aetherlink.relay.lease_id")
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.example.test",
                    port: 443,
                    relayID: "relay-stable",
                    relaySecret: "saved-secret"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "nonce-renewed"
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

        model.start(port: 43210)

        XCTAssertEqual(allocator.calls.count, 1)
        XCTAssertEqual(allocator.calls.first?.preferredRelaySecret, "saved-secret")
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-stable")
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "nonce-renewed")
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.lease_expires_at"), 4_102_444_800_000)
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.lease_nonce"), "nonce-renewed")
        assertStoredRelaySecret("saved-secret", defaults: defaults, store: relaySecretStore)

        relayClient.emit(.waitingForPeer)
        await Task.yield()
        model.beginPairing()

        XCTAssertEqual(allocator.calls.count, 1)
        let qrItems = try queryItems(from: try XCTUnwrap(model.pairingSession).qrPayload)
        XCTAssertEqual(qrItems["relay_host"], "relay.example.test")
        XCTAssertEqual(qrItems["relay_port"], "443")
        XCTAssertEqual(qrItems["relay_id"], "relay-stable")
        XCTAssertEqual(qrItems["relay_secret"], "saved-secret")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "nonce-renewed")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
    }

    @MainActor
    func testCompanionAppModelRejectsNonAdvancingSavedBootstrapLeaseForStableRelayID() async throws {
        let defaults = try isolatedDefaults()
        let nearExpiryEpochMillis = Int64(
            (Date().addingTimeInterval(60).timeIntervalSince1970 * 1000).rounded()
        )
        defaults.set("saved-secret", forKey: "aetherlink.relay.secret")
        defaults.set(nearExpiryEpochMillis, forKey: "aetherlink.relay.lease_expires_at")
        defaults.set("nonce-current", forKey: "aetherlink.relay.lease_nonce")
        defaults.set("relay.example.test", forKey: "aetherlink.relay.lease_host")
        defaults.set(443, forKey: "aetherlink.relay.lease_port")
        defaults.set("relay-stable", forKey: "aetherlink.relay.lease_id")
        let relaySecretStore = FakeCompanionRelaySecretStore()
        let relayClient = FakeRelayPeerClient()
        let allocator = FakeRemoteRelayRouteAllocator(
            allocation: CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: "relay.example.test",
                    port: 443,
                    relayID: "relay-stable",
                    relaySecret: "stale-secret"
                ),
                lease: CompanionRemoteRouteLease(
                    expiresAtEpochMillis: 4_102_444_800_000,
                    nonce: "nonce-current"
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

        model.start(port: 43210)

        XCTAssertEqual(allocator.calls.count, 1)
        XCTAssertEqual(relayClient.startedConfiguration?.relayID, "relay-stable")
        XCTAssertEqual(relayClient.startedConfiguration?.relaySecret, "saved-secret")
        XCTAssertEqual(relayClient.startedConfiguration?.relayNonce, "nonce-current")
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.lease_expires_at"), Int(nearExpiryEpochMillis))
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.lease_nonce"), "nonce-current")
        assertStoredRelaySecret("saved-secret", defaults: defaults, store: relaySecretStore)

        relayClient.emit(.waitingForPeer)
        await Task.yield()
        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertEqual(allocator.calls.count, 2)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.kind, .automaticPreparationRejected)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.endpoint, "relay.example.test:443")
        XCTAssertEqual(model.remoteRoutePreparationIssue?.message, "Remote route lease did not advance.")
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)
        XCTAssertEqual(defaults.integer(forKey: "aetherlink.relay.lease_expires_at"), Int(nearExpiryEpochMillis))
        XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.lease_nonce"), "nonce-current")
        XCTAssertTrue(model.logs.contains("Remote pairing QR not generated: Remote route lease did not advance."))
    }

    @MainActor
    func testCompanionAppModelDoesNotReuseSavedLeaseForDifferentRelayRoute() async throws {
        let defaults = try isolatedDefaults()
        defaults.set("relay-current", forKey: "aetherlink.relay.id")
        defaults.set("secret-current", forKey: "aetherlink.relay.secret")
        defaults.set(4_102_444_800_000, forKey: "aetherlink.relay.lease_expires_at")
        defaults.set("stale-nonce", forKey: "aetherlink.relay.lease_nonce")
        defaults.set("relay.previous.test", forKey: "aetherlink.relay.lease_host")
        defaults.set(443, forKey: "aetherlink.relay.lease_port")
        defaults.set("relay-previous", forKey: "aetherlink.relay.lease_id")
        let relayClient = FakeRelayPeerClient()
        let serviceAllocator = FakeRelayServiceRouteAllocator(allocation: nil)
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser(),
            relayClient: relayClient,
            relayServiceRouteAllocator: serviceAllocator,
            environment: [
                "AETHERLINK_RELAY_HOST": "relay.current.test",
                "AETHERLINK_RELAY_PORT": "443",
                "AETHERLINK_RELAY_ID": "relay-current",
                "AETHERLINK_RELAY_SECRET": "secret-current"
            ],
            userDefaults: defaults,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.start(port: 43210)
        relayClient.emit(.waitingForPeer)
        await Task.yield()
        model.beginPairing()

        XCTAssertNil(model.pairingSession)
        XCTAssertNil(relayClient.startedConfiguration?.relayNonce)
        XCTAssertFalse(model.isDevelopmentRelayRoutePreparedForQRCode)
        XCTAssertFalse(model.isDevelopmentRelayQRCodeReady)
        XCTAssertEqual(serviceAllocator.calls.count, 1)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.kind, .routeLeaseRefreshFailed)
        XCTAssertEqual(model.remoteRoutePreparationIssue?.endpoint, "relay.current.test:443")
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
                    relayID: "relay-opaque-bootstrap-fresh",
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
        XCTAssertEqual(qrItems["relay_id"], "relay-opaque-bootstrap-fresh")
        XCTAssertNotEqual(qrItems["relay_id"], qrItems["route_token"])
        XCTAssertEqual(qrItems["relay_secret"], "allocated-secret-2")
        XCTAssertEqual(qrItems["relay_expires_at"], "4102444800000")
        XCTAssertEqual(qrItems["relay_nonce"], "allocated-nonce-2")
        XCTAssertNil(qrItems["host"])
        XCTAssertNil(qrItems["port"])
        XCTAssertEqual(allocator.calls.count, 1)
        XCTAssertEqual(allocator.calls.first?.preferredRelaySecret, "allocated-secret-1")
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
    func testCompanionAppModelRegeneratesGUIAllocatedQRCodeWithNearExpiredLease() async throws {
        let nearExpiryEpochMillis = Int64(
            (Date().addingTimeInterval(10).timeIntervalSince1970 * 1000).rounded()
        )
        let serviceAllocator = FakeRelayServiceRouteAllocator(
            allocations: [
                CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: "relay.example.test",
                        port: 443,
                        relayID: "allocated-relay-near-expiry",
                        relaySecret: "allocated-secret-near-expiry"
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: nearExpiryEpochMillis,
                        nonce: "near-expiry-nonce"
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
        XCTAssertFalse(model.isDevelopmentRelayRoutePreparedForQRCode)
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
    func testCompanionAppModelDoesNotExposeAuthenticatedRouteRefreshByDefault() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let trustedStore = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await trustedStore.trust(TrustedDevice(
            id: "android-trusted",
            name: "Trusted Android",
            publicKeyBase64: privateKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let transport = FakeRuntimeTransport()
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
            peerServer: transport,
            advertiser: FakeRuntimeAdvertiser(),
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: try isolatedDefaults(),
            trustedDeviceStore: trustedStore,
            runtimeRouteHostProvider: { "192.168.1.44" }
        )

        model.configureDevelopmentRelay(
            host: "relay.example.test",
            port: 443,
            relaySecret: "preferred-secret"
        )
        model.start(port: 43210)
        defer { model.stop() }
        let handler = try XCTUnwrap(transport.onMessage)
        let sink = RecordingSink()
        try await authenticateTrustedDevice(
            handler: handler,
            sink: sink,
            deviceID: "android-trusted",
            privateKey: privateKey
        )

        handler(ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-default-off"), sink)

        let messages = try await sink.waitForMessages(count: 3)
        let message = messages.last
        XCTAssertEqual(message?.type, MessageType.error)
        XCTAssertEqual(message?.requestID, "route-refresh-default-off")
        XCTAssertEqual(message?.payload["code"], .string("route_refresh_unavailable"))
        XCTAssertEqual(message?.payload["retryable"], .bool(true))
        XCTAssertEqual(serviceAllocator.calls.count, 0)
        XCTAssertFalse(model.isDevelopmentRelayRoutePreparedForQRCode)
    }

    @MainActor
    func testCompanionAppModelExposesAuthenticatedRouteRefreshWhenDiagnosticOptInIsEnabled() async throws {
        let privateKey = P256.Signing.PrivateKey()
        let trustedStore = TrustedDeviceStore(fileURL: trustedDeviceStoreURL())
        try await trustedStore.trust(TrustedDevice(
            id: "android-trusted",
            name: "Trusted Android",
            publicKeyBase64: privateKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let transport = FakeRuntimeTransport()
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
            peerServer: transport,
            advertiser: FakeRuntimeAdvertiser(),
            relayServiceRouteAllocator: serviceAllocator,
            userDefaults: try isolatedDefaults(),
            trustedDeviceStore: trustedStore,
            runtimeRouteHostProvider: { "192.168.1.44" },
            allowsAuthenticatedRouteRefresh: true
        )

        model.configureDevelopmentRelay(
            host: "relay.example.test",
            port: 443,
            relaySecret: "preferred-secret"
        )
        model.start(port: 43210)
        defer { model.stop() }
        let handler = try XCTUnwrap(transport.onMessage)
        let sink = RecordingSink()
        try await authenticateTrustedDevice(
            handler: handler,
            sink: sink,
            deviceID: "android-trusted",
            privateKey: privateKey
        )

        handler(ProtocolEnvelope(type: MessageType.routeRefresh, requestID: "route-refresh-opt-in"), sink)

        let messages = try await sink.waitForMessages(count: 3)
        let message = messages.last
        XCTAssertEqual(message?.type, MessageType.routeRefresh)
        XCTAssertEqual(message?.requestID, "route-refresh-opt-in")
        XCTAssertEqual(message?.payload["relay_host"], .string("relay.example.test"))
        XCTAssertEqual(message?.payload["relay_port"], .number(443))
        XCTAssertEqual(message?.payload["relay_id"], .string("allocated-refresh-relay"))
        XCTAssertEqual(message?.payload["relay_secret"], .string("allocated-refresh-secret"))
        XCTAssertEqual(message?.payload["relay_expires_at"], .number(4_102_444_800_000))
        XCTAssertEqual(message?.payload["relay_nonce"], .string("allocated-refresh-nonce"))
        XCTAssertEqual(message?.payload["relay_scope"], .string("remote"))
        XCTAssertEqual(serviceAllocator.calls.count, 1)
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
    func testCompanionAppModelAdvertisesRouteTokenWithoutStableIdentityTXTMetadata() async throws {
        let advertiser = FakeRuntimeAdvertiser()
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: advertiser,
            userDefaults: try isolatedDefaults()
        )

        model.start(port: 43210)
        defer { model.stop() }

        let metadata = try XCTUnwrap(advertiser.startedMetadata)
        XCTAssertEqual(metadata.version, "1")
        XCTAssertEqual(metadata.app, "AetherLink")
        XCTAssertFalse(metadata.routeToken?.isEmpty ?? true)
        XCTAssertNil(metadata.deviceID)
        XCTAssertNil(metadata.fingerprint)
        XCTAssertEqual(metadata.txtRecord["route_token"], metadata.routeToken)
        XCTAssertNil(metadata.txtRecord["device_id"])
        XCTAssertNil(metadata.txtRecord["fingerprint"])
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
        XCTAssertNil(advertiser.startedMetadata?.deviceID)
        XCTAssertNil(advertiser.startedMetadata?.fingerprint)
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

private func authenticateTrustedDevice(
    router: LocalRuntimeMessageRouter,
    sink: RecordingSink,
    deviceID: String,
    privateKey: P256.Signing.PrivateKey
) async throws {
    try await authenticateTrustedDevice(
        send: { envelope, sink in router.handle(envelope, sink: sink) },
        sink: sink,
        deviceID: deviceID,
        privateKey: privateKey
    )
}

private func authenticateTrustedDevice(
    handler: LocalPeerMessageHandler,
    sink: RecordingSink,
    deviceID: String,
    privateKey: P256.Signing.PrivateKey
) async throws {
    try await authenticateTrustedDevice(
        send: handler,
        sink: sink,
        deviceID: deviceID,
        privateKey: privateKey
    )
}

private func authenticateTrustedDevice(
    send: (ProtocolEnvelope, any RuntimeMessageSink) -> Void,
    sink: RecordingSink,
    deviceID: String,
    privateKey: P256.Signing.PrivateKey
) async throws {
    send(ProtocolEnvelope(
        type: MessageType.hello,
        requestID: "hello-\(deviceID)",
        payload: ["device_id": .string(deviceID)]
    ), sink)

    let challenge = try await sink.waitForMessages(count: 1).last
    XCTAssertEqual(challenge?.type, MessageType.authChallenge)
    guard case .string(let nonce)? = challenge?.payload["nonce"] else {
        XCTFail("Expected nonce in auth challenge")
        return
    }
    let authMessage = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
        deviceID: deviceID,
        nonce: nonce
    )
    let authMessageData = try XCTUnwrap(authMessage.data(using: .utf8))
    let signature = try privateKey
        .signature(for: SHA256.hash(data: authMessageData))
        .derRepresentation
        .base64EncodedString()
    send(ProtocolEnvelope(
        type: MessageType.authResponse,
        requestID: "auth-\(deviceID)",
        payload: [
            "device_id": .string(deviceID),
            "nonce": .string(nonce),
            "signature": .string(signature)
        ]
    ), sink)

    let authResponse = try await sink.waitForMessages(count: 2).last
    XCTAssertEqual(authResponse?.type, MessageType.authResponse)
    XCTAssertEqual(authResponse?.payload["accepted"], .bool(true))
}

private func chatSendEnvelope(requestID: String, sessionID: String, content: String) -> ProtocolEnvelope {
    ProtocolEnvelope(
        type: MessageType.chatSend,
        requestID: requestID,
        payload: [
            "session_id": .string(sessionID),
            "model": .string("llama3.1:8b"),
            "messages": .array([
                .object([
                    "role": .string("user"),
                    "content": .string(content)
                ])
            ])
        ]
    )
}

private func appendRawChatEventLogLine(_ line: String, to fileURL: URL) throws {
    let handle = try FileHandle(forWritingTo: fileURL)
    defer { try? handle.close() }
    try handle.seekToEnd()
    try handle.write(contentsOf: Data((line + "\n").utf8))
}

private func appendRawMemoryEventLogLine(_ line: String, to fileURL: URL) throws {
    let handle = try FileHandle(forWritingTo: fileURL)
    defer { try? handle.close() }
    try handle.seekToEnd()
    try handle.write(contentsOf: Data((line + "\n").utf8))
}

private func createBroadPermissionEventLog(at fileURL: URL) throws {
    let directoryURL = fileURL.deletingLastPathComponent()
    try FileManager.default.createDirectory(
        at: directoryURL,
        withIntermediateDirectories: true,
        attributes: [.posixPermissions: 0o777]
    )
    try FileManager.default.setAttributes(
        [.posixPermissions: 0o777],
        ofItemAtPath: directoryURL.path
    )
    FileManager.default.createFile(
        atPath: fileURL.path,
        contents: nil,
        attributes: [.posixPermissions: 0o666]
    )
    try FileManager.default.setAttributes(
        [.posixPermissions: 0o666],
        ofItemAtPath: fileURL.path
    )
    XCTAssertEqual(try posixPermissions(at: fileURL), 0o666)
    XCTAssertEqual(try posixPermissions(at: directoryURL), 0o777)
}

private func posixPermissions(at url: URL) throws -> Int {
    let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
    guard let permissions = attributes[.posixPermissions] as? NSNumber else {
        throw CocoaError(.fileReadUnknown)
    }
    return permissions.intValue & 0o777
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

private func routeRefreshResult(
    runtimeDeviceID: String = "runtime-1",
    runtimeKeyFingerprint: String = "runtime-fingerprint",
    relayHost: String,
    relayPort: Int = 43171,
    relayID: String = "relay-id-1",
    relaySecret: String = "relay-secret-1",
    relayExpiresAtEpochMillis: Int64 = 4_102_444_800_000,
    relayNonce: String = "relay-nonce-1",
    relayScope: String? = "remote"
) -> RuntimeRouteRefreshResult {
    RuntimeRouteRefreshResult(
        runtimeDeviceID: runtimeDeviceID,
        runtimeKeyFingerprint: runtimeKeyFingerprint,
        relayHost: relayHost,
        relayPort: relayPort,
        relayID: relayID,
        relaySecret: relaySecret,
        relayExpiresAtEpochMillis: relayExpiresAtEpochMillis,
        relayNonce: relayNonce,
        relayScope: relayScope
    )
}

private func p2pRouteRefreshResult(
    runtimeDeviceID: String = "runtime-1",
    runtimeKeyFingerprint: String = "runtime-fingerprint",
    p2pRouteClass: String = "p2p_rendezvous",
    p2pRecordID: String = "p2p-record-1",
    p2pEncryptedBody: String = "opaque-candidate-body-1",
    p2pExpiresAtEpochMillis: Int64 = 4_102_444_800_000,
    p2pAntiReplayNonce: String = "p2p-nonce-1",
    p2pProtocolVersion: Int = 1
) -> RuntimeRouteRefreshResult {
    RuntimeRouteRefreshResult(
        runtimeDeviceID: runtimeDeviceID,
        runtimeKeyFingerprint: runtimeKeyFingerprint,
        p2pRouteClass: p2pRouteClass,
        p2pRecordID: p2pRecordID,
        p2pEncryptedBody: p2pEncryptedBody,
        p2pExpiresAtEpochMillis: p2pExpiresAtEpochMillis,
        p2pAntiReplayNonce: p2pAntiReplayNonce,
        p2pProtocolVersion: p2pProtocolVersion
    )
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

private struct RecordingRuntimeMemoryListRequest: Equatable {
    var ownerDeviceID: String?
}

private struct RecordingRuntimeMemoryUpsertRequest: Equatable {
    var ownerDeviceID: String?
    var id: String?
    var content: String
    var enabled: Bool?
}

private struct RecordingRuntimeMemoryDeleteRequest: Equatable {
    var ownerDeviceID: String?
    var id: String
}

private struct RecordingRuntimeMemorySummaryDraftDismissRequest: Equatable {
    var ownerDeviceID: String?
    var draftID: String
}

private final class RecordingRuntimeMemoryStore: RuntimeMemoryStore, @unchecked Sendable {
    private let lock = NSLock()
    private var entries: [RuntimeMemoryEntry]
    private var recordedListRequests: [RecordingRuntimeMemoryListRequest] = []
    private var recordedUpsertRequests: [RecordingRuntimeMemoryUpsertRequest] = []
    private var recordedDeleteRequests: [RecordingRuntimeMemoryDeleteRequest] = []
    private var recordedDismissMemorySummaryDraftRequests: [RecordingRuntimeMemorySummaryDraftDismissRequest] = []

    init(entries: [RuntimeMemoryEntry] = []) {
        self.entries = entries
    }

    var listRequests: [RecordingRuntimeMemoryListRequest] {
        lock.withLock { recordedListRequests }
    }

    var upsertRequests: [RecordingRuntimeMemoryUpsertRequest] {
        lock.withLock { recordedUpsertRequests }
    }

    var deleteRequests: [RecordingRuntimeMemoryDeleteRequest] {
        lock.withLock { recordedDeleteRequests }
    }

    var dismissMemorySummaryDraftRequests: [RecordingRuntimeMemorySummaryDraftDismissRequest] {
        lock.withLock { recordedDismissMemorySummaryDraftRequests }
    }

    func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry] {
        lock.withLock {
            recordedListRequests.append(RecordingRuntimeMemoryListRequest(ownerDeviceID: ownerDeviceID))
            return entries
        }
    }

    func listAll() throws -> [RuntimeMemoryEntry] {
        try list(ownerDeviceID: nil)
    }

    func upsert(
        ownerDeviceID: String?,
        id: String?,
        content: String,
        enabled: Bool?,
        source: RuntimeMemoryEntrySource?,
        timestamp: Date
    ) throws -> RuntimeMemoryEntry {
        let entry = RuntimeMemoryEntry(
            id: id ?? UUID().uuidString,
            content: content.trimmingCharacters(in: .whitespacesAndNewlines),
            enabled: enabled ?? true,
            createdAt: timestamp,
            updatedAt: timestamp,
            source: source
        )
        lock.withLock {
            recordedUpsertRequests.append(RecordingRuntimeMemoryUpsertRequest(
                ownerDeviceID: ownerDeviceID,
                id: id,
                content: content,
                enabled: enabled
            ))
            entries.removeAll { $0.id == entry.id }
            entries.append(entry)
        }
        return entry
    }

    func delete(ownerDeviceID: String?, id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult {
        lock.withLock {
            recordedDeleteRequests.append(RecordingRuntimeMemoryDeleteRequest(
                ownerDeviceID: ownerDeviceID,
                id: id
            ))
            entries.removeAll { $0.id == id }
        }
        return RuntimeMemoryDeleteResult(id: id, deletedAt: timestamp)
    }

    func dismissedMemorySummaryDraftIDs(ownerDeviceID: String?) throws -> Set<String> {
        []
    }

    func dismissMemorySummaryDraft(
        ownerDeviceID: String?,
        draftID: String,
        timestamp: Date
    ) throws -> RuntimeMemorySummaryDraftDismissResult {
        lock.withLock {
            recordedDismissMemorySummaryDraftRequests.append(RecordingRuntimeMemorySummaryDraftDismissRequest(
                ownerDeviceID: ownerDeviceID,
                draftID: draftID
            ))
        }
        return RuntimeMemorySummaryDraftDismissResult(draftID: draftID, dismissedAt: timestamp)
    }
}

private struct FailingRuntimeMemoryStore: RuntimeMemoryStore {
    func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry] {
        throw NSError(
            domain: "AetherLinkTests",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "memory store read failed"]
        )
    }

    func listAll() throws -> [RuntimeMemoryEntry] {
        try list(ownerDeviceID: nil)
    }

    func upsert(
        ownerDeviceID: String?,
        id: String?,
        content: String,
        enabled: Bool?,
        source: RuntimeMemoryEntrySource?,
        timestamp: Date
    ) throws -> RuntimeMemoryEntry {
        throw NSError(
            domain: "AetherLinkTests",
            code: 2,
            userInfo: [NSLocalizedDescriptionKey: "memory store write failed"]
        )
    }

    func delete(ownerDeviceID: String?, id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult {
        throw NSError(
            domain: "AetherLinkTests",
            code: 3,
            userInfo: [NSLocalizedDescriptionKey: "memory store delete failed"]
        )
    }

    func dismissedMemorySummaryDraftIDs(ownerDeviceID: String?) throws -> Set<String> {
        throw NSError(
            domain: "AetherLinkTests",
            code: 4,
            userInfo: [NSLocalizedDescriptionKey: "memory summary draft dismiss read failed"]
        )
    }

    func dismissMemorySummaryDraft(
        ownerDeviceID: String?,
        draftID: String,
        timestamp: Date
    ) throws -> RuntimeMemorySummaryDraftDismissResult {
        throw NSError(
            domain: "AetherLinkTests",
            code: 5,
            userInfo: [NSLocalizedDescriptionKey: "memory summary draft dismiss write failed"]
        )
    }
}

private final class SequencedRuntimeMemoryStore: RuntimeMemoryStore, @unchecked Sendable {
    private let lock = NSLock()
    private var results: [Result<[RuntimeMemoryEntry], Error>]

    init(results: [Result<[RuntimeMemoryEntry], Error>]) {
        self.results = results
    }

    func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry] {
        try listAll()
    }

    func listAll() throws -> [RuntimeMemoryEntry] {
        let result = lock.withLock {
            results.isEmpty ? .success([]) : results.removeFirst()
        }
        return try result.get()
    }

    func upsert(
        ownerDeviceID: String?,
        id: String?,
        content: String,
        enabled: Bool?,
        source: RuntimeMemoryEntrySource?,
        timestamp: Date
    ) throws -> RuntimeMemoryEntry {
        RuntimeMemoryEntry(
            id: id ?? UUID().uuidString,
            content: content,
            enabled: enabled ?? true,
            createdAt: timestamp,
            updatedAt: timestamp,
            source: source
        )
    }

    func delete(ownerDeviceID: String?, id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult {
        RuntimeMemoryDeleteResult(id: id, deletedAt: timestamp)
    }

    func dismissedMemorySummaryDraftIDs(ownerDeviceID: String?) throws -> Set<String> {
        []
    }

    func dismissMemorySummaryDraft(
        ownerDeviceID: String?,
        draftID: String,
        timestamp: Date
    ) throws -> RuntimeMemorySummaryDraftDismissResult {
        RuntimeMemorySummaryDraftDismissResult(draftID: draftID, dismissedAt: timestamp)
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

private func temporarySQLiteURL() -> URL {
    FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString)
        .appendingPathComponent("runtime-chat-events.sqlite")
}

private func appendMemorySummaryDraftTranscript(
    to store: SQLiteRuntimeChatEventStore,
    sessionID: String,
    ownerDeviceID: String,
    firstTurnAt: Date,
    visiblePrefix: String
) throws {
    for index in 0..<3 {
        let timestamp = firstTurnAt.addingTimeInterval(TimeInterval(index * 60))
        let requestID = "\(sessionID)-turn-\(index)"
        var messages: [ChatMessage] = [
            ChatMessage(role: "user", content: "\(visiblePrefix) question \(index)")
        ]
        if index == 0 {
            messages = [
                ChatMessage(
                    role: "system",
                    content: "Runtime user memory:\nSensitive memory context should stay backend-only."
                ),
                ChatMessage(
                    role: "system",
                    content: "Runtime conversation summary:\nOlder compaction context should stay backend-only."
                )
            ] + messages
        }
        try store.append(RuntimeChatStoredEvent(
            id: "\(requestID)-request",
            timestamp: timestamp,
            kind: .request,
            requestID: requestID,
            sessionID: sessionID,
            model: "ollama:llama3.1:8b",
            messages: messages,
            ownerDeviceID: ownerDeviceID
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "\(requestID)-reasoning",
            timestamp: timestamp.addingTimeInterval(1),
            kind: .reasoningDelta,
            requestID: requestID,
            sessionID: sessionID,
            model: "ollama:llama3.1:8b",
            reasoningDelta: "\(visiblePrefix) private reasoning \(index)",
            ownerDeviceID: ownerDeviceID
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "\(requestID)-assistant",
            timestamp: timestamp.addingTimeInterval(2),
            kind: .assistantDelta,
            requestID: requestID,
            sessionID: sessionID,
            model: "ollama:llama3.1:8b",
            delta: "\(visiblePrefix) answer \(index)",
            ownerDeviceID: ownerDeviceID
        ))
        try store.append(RuntimeChatStoredEvent(
            id: "\(requestID)-done",
            timestamp: timestamp.addingTimeInterval(3),
            kind: .done,
            requestID: requestID,
            sessionID: sessionID,
            model: "ollama:llama3.1:8b",
            finishReason: "stop",
            ownerDeviceID: ownerDeviceID
        ))
    }
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

private func waitForRecordedEvents(
    in store: RecordingRuntimeChatEventStore,
    count: Int,
    timeout: TimeInterval = 1.0
) async throws -> [RuntimeChatStoredEvent] {
    let deadline = Date().addingTimeInterval(timeout)
    var lastEvents = store.events
    while Date() < deadline {
        lastEvents = store.events
        if lastEvents.count >= count {
            return lastEvents
        }
        try await Task.sleep(nanoseconds: 20_000_000)
    }
    return lastEvents
}

private func pairingEnvelope(
    requestID: String,
    session: PairingSession,
    pairingNonce: String? = nil,
    pairingCode: String? = nil,
    deviceID: String = "android-1",
    deviceName: String = "Android Phone",
    publicKey: String? = nil
) -> ProtocolEnvelope {
    ProtocolEnvelope(
        type: MessageType.pairingRequest,
        requestID: requestID,
        payload: [
            "pairing_nonce": .string(pairingNonce ?? session.nonce),
            "pairing_code": .string(pairingCode ?? session.code),
            "device_id": .string(deviceID),
            "device_name": .string(deviceName),
            "public_key": .string(publicKey ?? testClientPublicKeyBase64())
        ]
    )
}

private func testClientPublicKeyBase64() -> String {
    P256.Signing.PrivateKey().publicKey.derRepresentation.base64EncodedString()
}

private final class MockBackend: LlmBackend, @unchecked Sendable {
    let provider: ModelProvider
    private let status: BackendStatus
    private let models: [ModelInfo]
    private let modelListError: Error?
    private let pullResult: ModelPullResult
    private let pullError: Error?
    private let unloadError: Error?
    private let healthCheckCallCountLock = NSLock()
    private var healthCheckCalls = 0
    private let listModelsCallCountLock = NSLock()
    private var listModelsCalls = 0
    private let chatEvents: [ChatStreamEvent]
    private let chatEventBatchesLock = NSLock()
    private var chatEventBatches: [[ChatStreamEvent]]
    private let chatContinuationsLock = NSLock()
    private var chatContinuations: [AsyncThrowingStream<ChatStreamEvent, Error>.Continuation] = []
    private let cancelledGenerationIDsLock = NSLock()
    private var cancelledIDs: [String] = []
    private let pulledModelNamesLock = NSLock()
    private var pulledNames: [String] = []
    private let finishChatStream: Bool
    private let cancelFinishesChatStream: Bool
    private let cancelResult: GenerationCancellationResult
    private let onChatRequest: ((ChatRequest) -> Void)?

    init(
        provider: ModelProvider = .ollama,
        status: BackendStatus = .available,
        models: [ModelInfo] = [],
        modelListError: Error? = nil,
        pullResult: ModelPullResult = ModelPullResult(model: "mock", status: "success", installed: true),
        pullError: Error? = nil,
        unloadError: Error? = nil,
        chatEvents: [ChatStreamEvent] = [],
        chatEventBatches: [[ChatStreamEvent]] = [],
        finishChatStream: Bool = true,
        cancelFinishesChatStream: Bool = false,
        cancelResult: GenerationCancellationResult = .notFound(generationID: "missing"),
        onChatRequest: ((ChatRequest) -> Void)? = nil
    ) {
        self.provider = provider
        self.status = status
        self.models = models
        self.modelListError = modelListError
        self.pullResult = pullResult
        self.pullError = pullError
        self.unloadError = unloadError
        self.chatEvents = chatEvents
        self.chatEventBatches = chatEventBatches
        self.finishChatStream = finishChatStream
        self.cancelFinishesChatStream = cancelFinishesChatStream
        self.cancelResult = cancelResult
        self.onChatRequest = onChatRequest
    }

    var cancelledGenerationIDs: [String] {
        cancelledGenerationIDsLock.withLock { cancelledIDs }
    }

    var pulledModelNames: [String] {
        pulledModelNamesLock.withLock { pulledNames }
    }

    var healthCheckCallCount: Int {
        healthCheckCallCountLock.withLock { healthCheckCalls }
    }

    var listModelsCallCount: Int {
        listModelsCallCountLock.withLock { listModelsCalls }
    }

    func healthCheck() async -> BackendStatus {
        healthCheckCallCountLock.withLock {
            healthCheckCalls += 1
        }
        return status
    }

    func listModels() async throws -> [ModelInfo] {
        listModelsCallCountLock.withLock {
            listModelsCalls += 1
        }
        if let modelListError {
            throw modelListError
        }
        return models
    }

    func pullModel(name: String) async throws -> ModelPullResult {
        pulledModelNamesLock.withLock {
            pulledNames.append(name)
        }
        if let pullError {
            throw pullError
        }
        return ModelPullResult(model: name, status: pullResult.status, installed: pullResult.installed)
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            onChatRequest?(request)
            nextChatEvents().forEach { continuation.yield($0) }
            if finishChatStream {
                continuation.finish()
            } else {
                chatContinuationsLock.withLock {
                    chatContinuations.append(continuation)
                }
            }
        }
    }

    func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        if let unloadError {
            throw unloadError
        }
        return .unsupported(provider: provider, modelID: providerModelID)
    }

    func cancel(generationID: String) -> GenerationCancellationResult {
        cancelledGenerationIDsLock.withLock {
            cancelledIDs.append(generationID)
        }
        if cancelFinishesChatStream {
            let continuations = chatContinuationsLock.withLock {
                let continuations = chatContinuations
                chatContinuations.removeAll()
                return continuations
            }
            continuations.forEach { continuation in
                continuation.finish(throwing: OllamaBackendError.generationCancelled(generationID: generationID))
            }
        }
        return cancelResult
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
    private var recordedSessionListRequests: [RuntimeChatSessionListRequest] = []
    private var recordedMutationRequests: [RuntimeChatMutationRequest] = []

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

    var mutationRequests: [RuntimeChatMutationRequest] {
        lock.withLock { recordedMutationRequests }
    }

    var sessionListRequests: [RuntimeChatSessionListRequest] {
        lock.withLock { recordedSessionListRequests }
    }

    func append(_ event: RuntimeChatStoredEvent) throws {
        lock.withLock {
            storedEvents.append(event)
        }
    }

    func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult {
        lock.withLock {
            recordedMutationRequests.append(RuntimeChatMutationRequest(
                ownerDeviceID: ownerDeviceID,
                sessionID: sessionID,
                requestID: requestID,
                mutation: mutation
            ))
            storedEvents.append(RuntimeChatStoredEvent(
                timestamp: timestamp,
                kind: mutation.eventKind,
                requestID: requestID,
                sessionID: sessionID,
                model: storedSessions.first { $0.sessionID == sessionID }?.model ?? "",
                ownerDeviceID: ownerDeviceID
            ))
        }
        return RuntimeChatSessionMutationResult(sessionID: sessionID, mutation: mutation, timestamp: timestamp)
    }

    func listSessions(ownerDeviceID: String?, limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        lock.withLock {
            recordedSessionListRequests.append(RuntimeChatSessionListRequest(
                ownerDeviceID: ownerDeviceID,
                limit: limit,
                includeArchived: includeArchived
            ))
            return Array(storedSessions.prefix(limit))
        }
    }

    func listAllSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        lock.withLock { Array(storedSessions.prefix(limit)) }
    }

    func listMessages(ownerDeviceID: String?, sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        lock.withLock { Array((storedMessages[sessionID] ?? []).suffix(limit)) }
    }

    func listAllMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        lock.withLock { Array((storedMessages[sessionID] ?? []).suffix(limit)) }
    }
}

private struct RuntimeChatMutationRequest: Equatable {
    var ownerDeviceID: String?
    var sessionID: String
    var requestID: String
    var mutation: RuntimeChatSessionMutation
}

private struct RuntimeChatSessionListRequest: Equatable {
    var ownerDeviceID: String?
    var limit: Int
    var includeArchived: Bool
}

private struct FailingRuntimeChatEventStore: RuntimeChatEventStore {
    func append(_ event: RuntimeChatStoredEvent) throws {
        throw NSError(
            domain: "AetherLinkTests",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "chat store write failed"]
        )
    }

    func listSessions(ownerDeviceID: String?, limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        throw NSError(
            domain: "AetherLinkTests",
            code: 2,
            userInfo: [NSLocalizedDescriptionKey: "chat store read failed"]
        )
    }

    func listAllSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        try listSessions(ownerDeviceID: nil, limit: limit, includeArchived: includeArchived)
    }

    func listMessages(ownerDeviceID: String?, sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        throw NSError(
            domain: "AetherLinkTests",
            code: 3,
            userInfo: [NSLocalizedDescriptionKey: "chat store messages failed"]
        )
    }

    func listAllMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        try listMessages(ownerDeviceID: nil, sessionID: sessionID, limit: limit)
    }

    func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult {
        throw NSError(
            domain: "AetherLinkTests",
            code: 4,
            userInfo: [NSLocalizedDescriptionKey: "chat store mutation failed"]
        )
    }
}

private final class SequencedRuntimeChatEventStore: RuntimeChatEventStore, @unchecked Sendable {
    private let lock = NSLock()
    private var results: [Result<[RuntimeChatStoredSession], Error>]

    init(results: [Result<[RuntimeChatStoredSession], Error>]) {
        self.results = results
    }

    func append(_ event: RuntimeChatStoredEvent) throws {}

    func listSessions(ownerDeviceID: String?, limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        try listAllSessions(limit: limit, includeArchived: includeArchived)
    }

    func listAllSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        let result = lock.withLock {
            results.isEmpty ? .success([]) : results.removeFirst()
        }
        return Array(try result.get().prefix(limit))
    }

    func listMessages(ownerDeviceID: String?, sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        []
    }

    func listAllMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        []
    }

    func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult {
        RuntimeChatSessionMutationResult(sessionID: sessionID, mutation: mutation, timestamp: timestamp)
    }
}

private struct RuntimeChatSearchListRequest: Equatable {
    var ownerDeviceID: String?
    var limit: Int
    var includeArchived: Bool
    var query: String?
    var embeddingModelID: String?
}

private struct RuntimeChatMessagesListRequest: Equatable {
    var ownerDeviceID: String?
    var sessionID: String
    var limit: Int
}

private final class SearchHintRecordingRuntimeChatEventStore: RuntimeChatEventStore, @unchecked Sendable {
    private let lock = NSLock()
    private let sessions: [RuntimeChatStoredSession]
    private var recordedSearchRequests: [RuntimeChatSearchListRequest] = []
    private var recordedMessageRequests: [RuntimeChatMessagesListRequest] = []

    init(sessions: [RuntimeChatStoredSession]) {
        self.sessions = sessions
    }

    var searchRequests: [RuntimeChatSearchListRequest] {
        lock.withLock { recordedSearchRequests }
    }

    var messageRequests: [RuntimeChatMessagesListRequest] {
        lock.withLock { recordedMessageRequests }
    }

    func append(_ event: RuntimeChatStoredEvent) throws {}

    func listSessions(ownerDeviceID: String?, limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        Array(sessions.prefix(limit))
    }

    func listSessions(
        ownerDeviceID: String?,
        limit: Int,
        includeArchived: Bool,
        query: String?,
        embeddingModelID: String?
    ) throws -> [RuntimeChatStoredSession] {
        lock.withLock {
            recordedSearchRequests.append(RuntimeChatSearchListRequest(
                ownerDeviceID: ownerDeviceID,
                limit: limit,
                includeArchived: includeArchived,
                query: query,
                embeddingModelID: embeddingModelID
            ))
        }
        return Array(sessions.prefix(limit))
    }

    func listAllSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        try listSessions(ownerDeviceID: nil, limit: limit, includeArchived: includeArchived)
    }

    func listMessages(ownerDeviceID: String?, sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        lock.withLock {
            recordedMessageRequests.append(RuntimeChatMessagesListRequest(
                ownerDeviceID: ownerDeviceID,
                sessionID: sessionID,
                limit: limit
            ))
        }
        return []
    }

    func listAllMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        []
    }

    func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult {
        RuntimeChatSessionMutationResult(sessionID: sessionID, mutation: mutation, timestamp: timestamp)
    }
}

private func testRuntimeInspectorError(_ message: String) -> NSError {
    NSError(
        domain: "AetherLinkTests",
        code: 100,
        userInfo: [NSLocalizedDescriptionKey: message]
    )
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
