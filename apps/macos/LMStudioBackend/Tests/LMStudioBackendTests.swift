import Foundation
import LMStudioBackend
import OllamaBackend
import XCTest

final class LMStudioBackendTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func testHealthCheckUsesNativeLocalModelsEndpoint() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.host, "127.0.0.1")
            XCTAssertEqual(request.url?.port, 1234)
            XCTAssertEqual(request.url?.path, "/api/v1/models")
            return self.response(statusCode: 200, body: #"{"models":[]}"#)
        }

        let status = await backend.healthCheck()

        XCTAssertEqual(status, .available)
    }

    func testListModelsParsesNativeLocalLLMAndEmbeddingModelsSeparately() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/v1/models")
            return self.response(
                statusCode: 200,
                body: """
                {
                  "models": [
                    {
                      "type": "llm",
                      "publisher": "google",
                      "key": "google/gemma-4-26b-a4b",
                      "display_name": "Gemma 4 26B A4B",
                      "size_bytes": 17990911801,
                      "context_length": 131072,
                      "loaded_instances": [{"id": "google/gemma-4-26b-a4b"}]
                    },
                    {
                      "type": "embedding",
                      "key": "text-embedding-nomic",
                      "display_name": "Nomic Embed",
                      "loaded_instances": []
                    }
                  ]
                }
                """
            )
        }

        let models = try await backend.listModels()

        XCTAssertEqual(models.count, 2)
        XCTAssertEqual(models.first?.id, "google/gemma-4-26b-a4b")
        XCTAssertEqual(models.first?.name, "Gemma 4 26B A4B")
        XCTAssertEqual(models.first?.provider, .lmStudio)
        XCTAssertEqual(models.first?.kind, .chat)
        XCTAssertEqual(models.first?.capabilities, ["chat"])
        XCTAssertEqual(models.first?.providerModelID, "google/gemma-4-26b-a4b")
        XCTAssertEqual(models.first?.sizeBytes, 17990911801)
        XCTAssertEqual(models.first?.contextWindowTokens, 131072)
        XCTAssertEqual(models.first?.source, .local)
        XCTAssertTrue(models.first?.installed == true)
        XCTAssertTrue(models.first?.running == true)
        XCTAssertEqual(models.last?.id, "text-embedding-nomic")
        XCTAssertEqual(models.last?.name, "Nomic Embed")
        XCTAssertEqual(models.last?.kind, .embedding)
        XCTAssertEqual(models.last?.capabilities, ["embedding"])
    }

    func testListModelsFallsBackToOpenAICompatibleModels() async throws {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 404, body: "missing")
            case "/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"object":"list","data":[{"id":"loaded-local-model","object":"model","context_window_tokens":32768},{"id":"text-embedding-nomic","object":"model"}]}"#
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(paths, ["/api/v1/models", "/v1/models"])
        XCTAssertEqual(models.map(\.id), ["loaded-local-model", "text-embedding-nomic"])
        XCTAssertEqual(models.map(\.provider), [.lmStudio, .lmStudio])
        XCTAssertEqual(models.map(\.kind), [.chat, .embedding])
        XCTAssertEqual(models.map(\.capabilities), [["chat"], ["embedding"]])
        XCTAssertEqual(models.first?.contextWindowTokens, 32768)
    }

    func testEmbedPostsBatchAndRestoresIndexOrder() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/v1/embeddings")
            XCTAssertEqual(request.httpMethod, "POST")
            let posted = try JSONDecoder().decode(PostedEmbeddingRequest.self, from: self.requestBodyData(from: request))
            XCTAssertEqual(posted.model, "text-embedding-nomic")
            XCTAssertEqual(posted.input, ["first", "second"])
            return self.response(
                statusCode: 200,
                body: #"{"model":"text-embedding-nomic","data":[{"index":1,"embedding":[0.3,0.4]},{"index":0,"embedding":[0.1,0.2]}]}"#
            )
        }

        let result = try await backend.embed(request: EmbeddingRequest(
            model: "text-embedding-nomic",
            texts: ["first", "second"]
        ))

        XCTAssertEqual(result.model, "text-embedding-nomic")
        XCTAssertEqual(result.embeddings, [[0.1, 0.2], [0.3, 0.4]])
    }

    func testEmbedRejectsDuplicateMissingOrOutOfRangeIndexes() async {
        let bodies = [
            #"{"data":[{"index":0,"embedding":[0.1]},{"index":0,"embedding":[0.2]}]}"#,
            #"{"data":[{"index":0,"embedding":[0.1]}]}"#,
            #"{"data":[{"index":0,"embedding":[0.1]},{"index":2,"embedding":[0.2]}]}"#,
        ]
        for body in bodies {
            let backend = makeBackend { _ in self.response(statusCode: 200, body: body) }
            do {
                _ = try await backend.embed(request: EmbeddingRequest(model: "embed", texts: ["a", "b"]))
                XCTFail("Expected invalid embedding indexes")
            } catch is LMStudioBackendError {
                continue
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testEmbedRejectsEmptyOrInconsistentVectors() async {
        let cases: [(body: String, texts: [String])] = [
            (#"{"data":[{"index":0,"embedding":[]}]}"#, ["a"]),
            (#"{"data":[{"index":0,"embedding":[0.1]},{"index":1,"embedding":[0.2,0.3]}]}"#, ["a", "b"]),
        ]
        for testCase in cases {
            let backend = makeBackend { _ in self.response(statusCode: 200, body: testCase.body) }
            do {
                _ = try await backend.embed(request: EmbeddingRequest(model: "embed", texts: testCase.texts))
                XCTFail("Expected invalid embedding vectors")
            } catch is LMStudioBackendError {
                continue
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelPostsLoadedInstanceID() async throws {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: """
                    {
                      "models": [
                        {
                          "type": "llm",
                          "key": "google/gemma-4-26b-a4b",
                          "display_name": "Gemma 4 26B A4B",
                          "loaded_instances": [{"id": "instance-gemma"}]
                        }
                      ]
                    }
                    """
                )
            case "/api/v1/models/unload":
                XCTAssertEqual(request.httpMethod, "POST")
                let body = try self.requestBodyData(from: request)
                let posted = try JSONDecoder().decode(PostedUnloadRequest.self, from: body)
                XCTAssertEqual(posted.instanceID, "instance-gemma")
                return self.response(statusCode: 200, body: #"{"instance_id":"instance-gemma"}"#)
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let result = try await backend.unloadModel(providerModelID: "google/gemma-4-26b-a4b")

        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/models/unload"])
        XCTAssertEqual(result, .unloaded(provider: .lmStudio, modelID: "google/gemma-4-26b-a4b"))
    }

    func testUnloadModelHTTPStatusReturnsStructuredError() async {
        var paths: [String] = []
        let unsafeBody = "unload denied http://127.0.0.1:1234/api/v1/models/unload route_token=secret"
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: """
                    {
                      "models": [
                        {
                          "type": "llm",
                          "key": "google/gemma-4-26b-a4b",
                          "display_name": "Gemma 4 26B A4B",
                          "loaded_instances": [{"id": "instance-gemma"}]
                        }
                      ]
                    }
                    """
                )
            case "/api/v1/models/unload":
                XCTAssertEqual(request.httpMethod, "POST")
                let body = try self.requestBodyData(from: request)
                let posted = try JSONDecoder().decode(PostedUnloadRequest.self, from: body)
                XCTAssertEqual(posted.instanceID, "instance-gemma")
                return self.response(statusCode: 503, body: unsafeBody)
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "google/gemma-4-26b-a4b")
            XCTFail("Expected structured unload error")
        } catch let error as LMStudioBackendError {
            XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/models/unload"])
            XCTAssertEqual(error, .httpStatus(endpoint: "POST /api/v1/models/unload", statusCode: 503, body: unsafeBody))
            XCTAssertEqual(error.code, "lm_studio_http_status")
            XCTAssertTrue(error.retryable)
            XCTAssertEqual(error.backendError.provider, .lmStudio)
            XCTAssertFalse(error.backendError.message.contains("127.0.0.1"))
            XCTAssertFalse(error.backendError.message.contains("route_token"))
            XCTAssertFalse(error.backendError.message.contains("/api/v1/models/unload"))
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testChatStreamsNativeServerSentEvents() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"qwen-local","display_name":"Qwen Local","loaded_instances":[{"id":"qwen-local"}]}]}"#)
            case "/api/v1/chat":
                XCTAssertEqual(request.httpMethod, "POST")
                let body = try self.requestBodyData(from: request)
                let posted = try JSONDecoder().decode(PostedNativeChatRequest.self, from: body)
                XCTAssertEqual(posted.model, "qwen-local")
                XCTAssertTrue(posted.stream)
                XCTAssertFalse(posted.store)
                XCTAssertEqual(posted.input.map(\.type), ["message"])
                XCTAssertEqual(posted.input.map(\.role), ["user"])
                XCTAssertEqual(posted.input.map(\.content), ["Hi"])
                return self.response(
                    statusCode: 200,
                    body: """
                    event: chat.start
                    data: {"type":"chat.start","model_instance_id":"qwen-local"}

                    event: message.delta
                    data: {"type":"message.delta","content":"Hello "}

                    event: message.delta
                    data: {"type":"message.delta","content":"there"}

                    event: chat.end
                    data: {"type":"chat.end","result":{"model_instance_id":"qwen-local","output":[{"type":"message","content":"Hello there"}],"stats":{"input_tokens":3,"total_output_tokens":4}}}

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-1",
            sessionID: "session-1",
            model: "qwen-local",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .delta("Hello "),
            .delta("there"),
            .done(inputTokens: 3, outputTokens: 4)
        ])
    }

    func testChatStreamsNativeReasoningSeparatelyFromAnswerContent() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"reasoning-local","loaded_instances":[{"id":"reasoning-local"}]}]}"#)
            case "/api/v1/chat":
                return self.response(
                    statusCode: 200,
                    body: """
                    event: chat.start
                    data: {"type":"chat.start","model_instance_id":"reasoning-local"}

                    event: message.delta
                    data: {"type":"message.delta","reasoning_content":"Plan first. "}

                    event: message.delta
                    data: {"type":"message.delta","thinking":"Then answer. ","content":"Hello"}

                    event: chat.end
                    data: {"type":"chat.end","result":{"model_instance_id":"reasoning-local","output":[{"type":"message","content":"Hello"}],"stats":{"input_tokens":4,"total_output_tokens":1}}}

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-reasoning-native",
            sessionID: "session-1",
            model: "reasoning-local",
            messages: [ChatMessage(role: "user", content: "Think")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .reasoningDelta("Plan first. "),
            .reasoningDelta("Then answer. "),
            .delta("Hello"),
            .done(inputTokens: 4, outputTokens: 1)
        ])
    }

    func testChatFallsBackToOpenAICompatibleStreamingWhenNativeChatShapeFails() async throws {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"qwen-local","loaded_instances":[]}]}"#)
            case "/api/v1/chat":
                return self.response(statusCode: 422, body: "native rejected")
            case "/v1/chat/completions":
                return self.response(
                    statusCode: 200,
                    body: """
                    data: {"choices":[{"delta":{"content":"Fallback"},"finish_reason":null}]}
                    data: {"choices":[{"delta":{"content":" stream"},"finish_reason":null}],"usage":{"prompt_tokens":2,"completion_tokens":3}}
                    data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":2,"completion_tokens":3}}
                    data: [DONE]

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-fallback",
            sessionID: "session-1",
            model: "qwen-local",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/chat", "/v1/chat/completions"])
        XCTAssertEqual(events, [
            .delta("Fallback"),
            .delta(" stream"),
            .done(inputTokens: 2, outputTokens: 3)
        ])
    }

    func testChatStreamsOpenAICompatibleReasoningSeparatelyFromAnswerContent() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"reasoning-openai","loaded_instances":[]}]}"#)
            case "/api/v1/chat":
                return self.response(statusCode: 422, body: "native rejected")
            case "/v1/chat/completions":
                return self.response(
                    statusCode: 200,
                    body: """
                    data: {"choices":[{"delta":{"reasoning_content":"Plan. "},"finish_reason":null}]}
                    data: {"choices":[{"delta":{"thinking":"Check. ","content":"Answer"},"finish_reason":null}],"usage":{"prompt_tokens":3,"completion_tokens":2}}
                    data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":3,"completion_tokens":2}}
                    data: [DONE]

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-reasoning-openai",
            sessionID: "session-1",
            model: "reasoning-openai",
            messages: [ChatMessage(role: "user", content: "Think")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .reasoningDelta("Plan. "),
            .reasoningDelta("Check. "),
            .delta("Answer"),
            .done(inputTokens: 3, outputTokens: 2)
        ])
    }

    func testChatWithImageAttachmentUsesNativeImageInput() async throws {
        var paths: [String] = []
        var postedRequest: PostedNativeChatRequest?
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"type":"vision","key":"vision-local","loaded_instances":[]}]}"#
                )
            case "/api/v1/chat":
                let body = try self.requestBodyData(from: request)
                postedRequest = try JSONDecoder().decode(PostedNativeChatRequest.self, from: body)
                return self.response(
                    statusCode: 200,
                    body: """
                    event: chat.start
                    data: {"type":"chat.start","model_instance_id":"vision-local"}

                    event: message.delta
                    data: {"type":"message.delta","content":"Vision"}

                    event: chat.end
                    data: {"type":"chat.end","result":{"model_instance_id":"vision-local","output":[{"type":"message","content":"Vision"}],"stats":{"input_tokens":5,"total_output_tokens":1}}}

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-vision",
            sessionID: "session-1",
            model: "vision-local",
            messages: [
                ChatMessage(
                    role: "user",
                    content: "Describe this image.",
                    attachments: [
                        ChatAttachment(
                            type: "image",
                            mimeType: "image/png",
                            name: "diagram.png",
                            dataBase64: "iVBORw0KGgo="
                        )
                    ]
                )
            ]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/chat"])
        XCTAssertEqual(events, [
            .delta("Vision"),
            .done(inputTokens: 5, outputTokens: 1)
        ])

        let payload = try XCTUnwrap(postedRequest)
        XCTAssertEqual(payload.model, "vision-local")
        XCTAssertTrue(payload.stream)
        XCTAssertFalse(payload.store)
        XCTAssertEqual(payload.input.count, 2)
        XCTAssertEqual(payload.input[0].type, "message")
        XCTAssertEqual(payload.input[0].role, "user")
        XCTAssertEqual(payload.input[0].content, "Describe this image.")
        XCTAssertNil(payload.input[0].dataURL)
        XCTAssertEqual(payload.input[1].type, "image")
        XCTAssertNil(payload.input[1].role)
        XCTAssertNil(payload.input[1].content)
        XCTAssertEqual(payload.input[1].dataURL, "data:image/png;base64,iVBORw0KGgo=")
    }

    func testChatWithImageAttachmentFallsBackToOpenAICompatibleVisionContentWhenNativeRejects() async throws {
        var paths: [String] = []
        var postedPayload: [String: Any]?
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"type":"vision","key":"vision-local","loaded_instances":[]}]}"#
                )
            case "/api/v1/chat":
                return self.response(statusCode: 422, body: "native rejected")
            case "/v1/chat/completions":
                let body = try self.requestBodyData(from: request)
                postedPayload = try JSONSerialization.jsonObject(with: body) as? [String: Any]
                return self.response(
                    statusCode: 200,
                    body: """
                    data: {"choices":[{"delta":{"content":"Vision"},"finish_reason":null}]}
                    data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":5,"completion_tokens":1}}
                    data: [DONE]

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-vision-fallback",
            sessionID: "session-1",
            model: "vision-local",
            messages: [
                ChatMessage(
                    role: "user",
                    content: "Describe this image.",
                    attachments: [
                        ChatAttachment(
                            type: "image",
                            mimeType: "image/png",
                            name: "diagram.png",
                            dataBase64: "iVBORw0KGgo="
                        )
                    ]
                )
            ]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/chat", "/v1/chat/completions"])
        XCTAssertEqual(events, [
            .delta("Vision"),
            .done(inputTokens: 5, outputTokens: 1)
        ])

        let payload = try XCTUnwrap(postedPayload)
        XCTAssertEqual(payload["model"] as? String, "vision-local")
        XCTAssertEqual(payload["stream"] as? Bool, true)
        let messages = try XCTUnwrap(payload["messages"] as? [[String: Any]])
        let message = try XCTUnwrap(messages.first)
        XCTAssertNil(message["attachments"])
        XCTAssertEqual(message["role"] as? String, "user")

        let content = try XCTUnwrap(message["content"] as? [[String: Any]])
        XCTAssertEqual(content.count, 2)
        XCTAssertEqual(content[0]["type"] as? String, "text")
        XCTAssertEqual(content[0]["text"] as? String, "Describe this image.")
        XCTAssertEqual(content[1]["type"] as? String, "image_url")
        let imageURL = try XCTUnwrap(content[1]["image_url"] as? [String: Any])
        XCTAssertEqual(imageURL["url"] as? String, "data:image/png;base64,iVBORw0KGgo=")
    }

    func testChatWithoutModelsReturnsStructuredNoModelsError() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/v1/models")
            return self.response(statusCode: 200, body: #"{"models":[]}"#)
        }

        let request = ChatRequest(
            generationID: "lm-no-models",
            sessionID: "session-1",
            model: "missing",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        do {
            for try await _ in backend.chat(request: request) {}
            XCTFail("Expected no models error")
        } catch let error as LMStudioBackendError {
            XCTAssertEqual(error, .noModels)
            XCTAssertEqual(error.code, "lm_studio_no_models")
            XCTAssertFalse(error.retryable)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    private func makeBackend(
        handler: @escaping (URLRequest) throws -> (HTTPURLResponse, Data)
    ) -> LMStudioBackend {
        MockURLProtocol.handler = handler
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: configuration)
        return LMStudioBackend(baseURL: URL(string: "http://127.0.0.1:1234")!, session: session)
    }

    private func response(statusCode: Int, body: String) -> (HTTPURLResponse, Data) {
        let url = URL(string: "http://127.0.0.1:1234")!
        let response = HTTPURLResponse(
            url: url,
            statusCode: statusCode,
            httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"]
        )!
        return (response, Data(body.utf8))
    }

    private func requestBodyData(from request: URLRequest) throws -> Data {
        if let body = request.httpBody {
            return body
        }

        guard let bodyStream = request.httpBodyStream else {
            return try XCTUnwrap(nil as Data?)
        }

        bodyStream.open()
        defer { bodyStream.close() }

        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 4096)
        while bodyStream.hasBytesAvailable {
            let readCount = bodyStream.read(&buffer, maxLength: buffer.count)
            if readCount < 0 {
                throw bodyStream.streamError ?? URLError(.cannotDecodeContentData)
            }
            if readCount == 0 {
                break
            }
            data.append(buffer, count: readCount)
        }
        return data
    }
}

private struct PostedNativeChatRequest: Decodable {
    var model: String
    var input: [PostedNativeInput]
    var stream: Bool
    var store: Bool
}

private struct PostedNativeInput: Decodable {
    var type: String?
    var role: String?
    var content: String?
    var dataURL: String?

    enum CodingKeys: String, CodingKey {
        case type
        case role
        case content
        case dataURL = "data_url"
    }
}

private struct PostedUnloadRequest: Decodable {
    var instanceID: String

    enum CodingKeys: String, CodingKey {
        case instanceID = "instance_id"
    }
}

private struct PostedEmbeddingRequest: Decodable {
    var model: String
    var input: [String]
}

private final class MockURLProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let handler = Self.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
