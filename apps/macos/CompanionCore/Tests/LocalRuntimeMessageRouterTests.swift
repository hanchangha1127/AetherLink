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
            message: "Ollama is not reachable from the runtime host.",
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
                message: "LM Studio is not reachable from the runtime host.",
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
        let forwardedMessage = try XCTUnwrap(request.messages.first)
        XCTAssertTrue(forwardedMessage.content.contains("Summarize this."))
        XCTAssertTrue(forwardedMessage.content.contains("[Attached document: roadmap.md (text/plain)]"))
        XCTAssertTrue(forwardedMessage.content.contains(documentText))
        XCTAssertEqual(forwardedMessage.attachments, [
            ChatAttachment(
                type: "image",
                mimeType: "image/png",
                name: "diagram.png",
                dataBase64: imageDataBase64
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
        let forwardedMessage = try XCTUnwrap(forwardedRequest.messages.first)
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

    func testChatSuggestionsRequestReturnsStructuredSuggestions() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"suggestions":["What should we verify next?","Can you compare the tradeoffs?"]}"#),
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
            .string("Can you compare the tradeoffs?")
        ]))
        let request = try XCTUnwrap(capturedRequest.value)
        XCTAssertEqual(request.generationID, "suggestions-1")
        XCTAssertEqual(request.model, "llama3.1:8b")
        XCTAssertTrue(request.messages.first?.content.contains("strict JSON") == true)
    }

    func testChatSuggestionsRequestReturnsEmptySuggestionsForInvalidJSON() async throws {
        let sink = RecordingSink()
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta("1. Ask about follow-up work\n2. Compare alternatives"),
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

    func testChatTitleRequestReturnsStructuredTitle() async throws {
        let sink = RecordingSink()
        let capturedRequest = LockedBox<ChatRequest?>(nil)
        let router = makeRouter(backend: MockBackend(
            models: [ModelInfo(id: "llama3.1:8b", name: "llama3.1:8b", installed: true)],
            chatEvents: [
                .delta(#"{"title":"Runtime-Mediated Model Access"}"#),
                .done(inputTokens: 4, outputTokens: 8)
            ],
            onChatRequest: { request in
                capturedRequest.value = request
            }
        ))
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
                    ])
                ])
            ]
        )

        emptyRouter.handle(emptyEnvelope, sink: emptySink)

        let emptyMessage = try await emptySink.waitForMessages(count: 1).first
        XCTAssertEqual(emptyMessage?.type, MessageType.chatTitleResult)
        XCTAssertEqual(emptyMessage?.requestID, "title-empty")
        XCTAssertEqual(emptyMessage?.payload["title"], .string(""))
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

    func testPairingQRCodePayloadCanOmitEndpointHints() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "mac-1",
            macName: "AetherLink Runtime",
            fingerprint: "fp-1",
            runtimePublicKeyBase64: "runtime-public-key",
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
        XCTAssertEqual(queryItems["mac_device_id"], "mac-1")
        XCTAssertEqual(queryItems["mac_name"], "AetherLink Runtime")
        XCTAssertEqual(queryItems["fingerprint"], "fp-1")
        XCTAssertEqual(queryItems["runtime_public_key"], "runtime-public-key")
        XCTAssertEqual(queryItems["runtime_key_fingerprint"], "fp-1")
        XCTAssertEqual(queryItems["route_token"], "route-1")
        XCTAssertEqual(queryItems["service_type"], "_aetherlink._tcp.local.")
        XCTAssertNil(queryItems["host"])
        XCTAssertNil(queryItems["port"])
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
            relaySecret: "secret with symbols + / ="
        )

        let components = try XCTUnwrap(URLComponents(string: session.qrPayload))
        let queryItems = try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }

        XCTAssertEqual(queryItems["relay_host"], "relay.example.test")
        XCTAssertEqual(queryItems["relay_port"], "43171")
        XCTAssertEqual(queryItems["relay_id"], "relay-id-1")
        XCTAssertEqual(queryItems["relay_secret"], "secret with symbols + / =")
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
    func testCompanionAppModelGeneratesIdentityOnlyPairingQRCode() throws {
        let model = CompanionAppModel(
            backend: MockBackend(status: .available),
            peerServer: FakeRuntimeTransport(),
            advertiser: FakeRuntimeAdvertiser()
        )

        model.beginPairing()

        let session = try XCTUnwrap(model.pairingSession)
        let components = try XCTUnwrap(URLComponents(string: session.qrPayload))
        let queryItems = try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }

        XCTAssertEqual(components.scheme, "aetherlink")
        XCTAssertEqual(components.host, "pair")
        XCTAssertEqual(queryItems["pairing_nonce"], session.nonce)
        XCTAssertEqual(queryItems["pairing_code"], session.code)
        XCTAssertFalse(queryItems["mac_device_id"]?.isEmpty ?? true)
        XCTAssertFalse(queryItems["fingerprint"]?.isEmpty ?? true)
        XCTAssertFalse(queryItems["route_token"]?.isEmpty ?? true)
        XCTAssertNil(queryItems["host"])
        XCTAssertNil(queryItems["port"])
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
                message: "LM Studio is not reachable from the runtime host.",
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

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
