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
                return self.response(statusCode: 200, body: #"{"object":"list","data":[{"id":"loaded-local-model","object":"model"}]}"#)
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(paths, ["/api/v1/models", "/v1/models"])
        XCTAssertEqual(models.map(\.id), ["loaded-local-model"])
        XCTAssertEqual(models.map(\.provider), [.lmStudio])
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
    var role: String
    var content: String
}

private struct PostedUnloadRequest: Decodable {
    var instanceID: String

    enum CodingKeys: String, CodingKey {
        case instanceID = "instance_id"
    }
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
