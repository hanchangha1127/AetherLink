import Foundation
import OllamaBackend
import XCTest

final class OllamaBackendTests: XCTestCase {
    override func tearDown() {
        MockURLProtocol.handler = nil
        SuspendingURLProtocol.onStart = nil
        SuspendingURLProtocol.onStop = nil
        super.tearDown()
    }

    func testHealthCheckUsesLocalTagsEndpoint() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/tags")
            return self.response(statusCode: 200, body: #"{"models":[]}"#)
        }

        let status = await backend.healthCheck()

        XCTAssertEqual(status, .available)
    }

    func testListModelsMergesTagsRunningAndCloudModelsWithoutRecommendedDefaults() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(
                    statusCode: 200,
                    body: """
                    {
                      "models": [
                        {
                          "name": "custom-local:7b",
                          "size": 1234
                        },
                        {
                          "name": "deepseek-v4-pro:cloud",
                          "model": "deepseek-v4-pro:cloud",
                          "remote_model": "deepseek-v4-pro",
                          "remote_host": "https://ollama.com:443",
                          "size": 344,
                          "modified_at": "2026-06-23T09:00:00Z"
                        },
                        {
                          "name": "provider-cloud",
                          "size": 222
                        }
                      ]
                    }
                    """
                )
            case "/api/ps":
                return self.response(
                    statusCode: 200,
                    body: """
                    {
                      "models": [
                        {
                          "name": "deepseek-v4-pro:cloud",
                          "size": 999
                        },
                        {
                          "model": "local-running:latest",
                          "size_vram": 2048
                        },
                        {
                          "name": "ps-only-cloud:cloud",
                          "size": 512
                        }
                      ]
                    }
                    """
                )
            case "/api/show":
                return self.response(statusCode: 200, body: #"{"capabilities":["completion"]}"#)
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(models.map(\.id), [
            "custom-local:7b",
            "deepseek-v4-pro:cloud",
            "provider-cloud",
            "local-running:latest"
        ])
        XCTAssertEqual(models[0].source, .local)
        XCTAssertTrue(models[0].installed)
        XCTAssertFalse(models[0].running)
        XCTAssertEqual(models[1].source, .cloud)
        XCTAssertTrue(models[1].installed)
        XCTAssertTrue(models[1].running)
        XCTAssertEqual(models[1].remoteModel, "deepseek-v4-pro")
        XCTAssertEqual(models[1].remoteHost, "https://ollama.com:443")
        XCTAssertEqual(models[1].sizeBytes, 344)
        XCTAssertNotNil(models[1].modifiedAt)
        XCTAssertEqual(models[2].source, .cloud)
        XCTAssertTrue(models[2].installed)
        XCTAssertFalse(models[2].running)
        XCTAssertEqual(models[3].source, .local)
        XCTAssertTrue(models[3].installed)
        XCTAssertTrue(models[3].running)
        XCTAssertEqual(models[3].sizeBytes, 2048)
        XCTAssertEqual(models.map(\.kind), [.chat, .chat, .chat, .chat])
        XCTAssertEqual(models[0].capabilities, ["completion"])
    }

    func testListModelsUsesShowCapabilitiesToSeparateEmbeddingModels() async throws {
        var showRequestCount = 0
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"nomic-embed-text","size":10},{"name":"qwen3:8b","size":20}]}"#)
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                showRequestCount += 1
                if showRequestCount == 1 {
                    return self.response(statusCode: 200, body: #"{"capabilities":["embedding"]}"#)
                }
                return self.response(statusCode: 200, body: #"{"capabilities":["completion"]}"#)
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(models.first { $0.id == "nomic-embed-text" }?.kind, .embedding)
        XCTAssertEqual(models.first { $0.id == "nomic-embed-text" }?.capabilities, ["embedding"])
        XCTAssertEqual(models.first { $0.id == "qwen3:8b" }?.kind, .chat)
    }

    func testListModelsDoesNotInventRecommendedDefaultsWhenTagsAreEmpty() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags", "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertTrue(models.isEmpty)
    }

    func testPullModelPostsNonStreamingPullRequest() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/pull")
            XCTAssertEqual(request.httpMethod, "POST")
            let body = try self.requestBodyData(from: request)
            let postedRequest = try JSONDecoder().decode(PostedPullRequest.self, from: body)
            XCTAssertEqual(postedRequest.model, "deepseek-v4-pro:cloud")
            XCTAssertFalse(postedRequest.stream)
            return self.response(statusCode: 200, body: #"{"status":"success"}"#)
        }

        let result = try await backend.pullModel(name: "deepseek-v4-pro:cloud")

        XCTAssertEqual(result, ModelPullResult(model: "deepseek-v4-pro:cloud", status: "success", installed: true))
    }

    func testPullModelHTTPStatusReturnsStructuredError() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/pull")
            return self.response(statusCode: 500, body: "pull failed")
        }

        do {
            _ = try await backend.pullModel(name: "gemma3")
            XCTFail("Expected structured error")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(error, .httpStatus(endpoint: "POST /api/pull", statusCode: 500, body: "pull failed"))
            XCTAssertEqual(error.code, "ollama_http_status")
            XCTAssertTrue(error.retryable)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadModelPostsEmptyChatWithKeepAliveZero() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/chat")
            XCTAssertEqual(request.httpMethod, "POST")
            let body = try self.requestBodyData(from: request)
            let postedRequest = try JSONDecoder().decode(PostedUnloadRequest.self, from: body)
            XCTAssertEqual(postedRequest.model, "llama3.1:8b")
            XCTAssertTrue(postedRequest.messages.isEmpty)
            XCTAssertEqual(postedRequest.keepAlive, 0)
            return self.response(statusCode: 200, body: #"{"done":true}"#)
        }

        let result = try await backend.unloadModel(providerModelID: "llama3.1:8b")

        XCTAssertEqual(result, .unloaded(provider: .ollama, modelID: "llama3.1:8b"))
    }

    func testChatStreamsOllamaLineDelimitedJSON() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/chat")
            XCTAssertEqual(request.httpMethod, "POST")
            let body = try self.requestBodyData(from: request)
            let postedRequest = try JSONDecoder().decode(PostedChatRequest.self, from: body)
            XCTAssertEqual(postedRequest.model, "llama3.1:8b")
            XCTAssertEqual(postedRequest.messages, [ChatMessage(role: "user", content: "Hi")])
            XCTAssertTrue(postedRequest.stream)
            XCTAssertTrue(postedRequest.think)
            return self.response(
                statusCode: 200,
                body: """
                {"message":{"role":"assistant","content":"Hello "},"done":false}
                {"message":{"role":"assistant","content":"there"},"done":false}
                {"done":true,"prompt_eval_count":3,"eval_count":4}

                """
            )
        }
        let request = ChatRequest(
            generationID: "generation-1",
            sessionID: "session-1",
            model: "llama3.1:8b",
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

    func testChatStreamsThinkingSeparatelyFromContent() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/chat")
            let body = try self.requestBodyData(from: request)
            let postedRequest = try JSONDecoder().decode(PostedChatRequest.self, from: body)
            XCTAssertTrue(postedRequest.think)
            return self.response(
                statusCode: 200,
                body: """
                {"message":{"role":"assistant","thinking":"I should reason first. "},"done":false}
                {"message":{"role":"assistant","thinking":"Now answer. ","content":"Hello"},"done":false}
                {"message":{"role":"assistant","content":" there"},"done":false}
                {"done":true,"prompt_eval_count":5,"eval_count":6}

                """
            )
        }
        let request = ChatRequest(
            generationID: "generation-thinking",
            sessionID: "session-1",
            model: "qwen3:8b",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .reasoningDelta("I should reason first. "),
            .reasoningDelta("Now answer. "),
            .delta("Hello"),
            .delta(" there"),
            .done(inputTokens: 5, outputTokens: 6)
        ])
    }

    func testChatStreamsServerSentEventLines() async throws {
        let backend = makeBackend { _ in
            self.response(
                statusCode: 200,
                body: """
                data: {"message":{"role":"assistant","content":"Hello"},"done":false}
                data: {"done":true,"prompt_eval_count":1,"eval_count":2}
                data: [DONE]

                """
            )
        }
        let request = ChatRequest(
            generationID: "generation-sse",
            sessionID: "session-1",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .delta("Hello"),
            .done(inputTokens: 1, outputTokens: 2)
        ])
    }

    func testHTTPStatusReturnsStructuredError() async {
        let backend = makeBackend { _ in
            self.response(statusCode: 503, body: "offline")
        }

        do {
            _ = try await backend.listModels()
            XCTFail("Expected structured error")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(error, .httpStatus(endpoint: "GET /api/tags", statusCode: 503, body: "offline"))
            XCTAssertEqual(error.code, "ollama_http_status")
            XCTAssertTrue(error.retryable)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testHTTPForbiddenMapsToOllamaAccessRequiredBackendError() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/tags")
            return self.response(statusCode: 403, body: "forbidden")
        }

        do {
            _ = try await backend.listModels()
            XCTFail("Expected structured error")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(error, .httpStatus(endpoint: "GET /api/tags", statusCode: 403, body: "forbidden"))
            XCTAssertEqual(error.code, "ollama_auth_required")
            XCTAssertEqual(error.backendError.code, "ollama_auth_required")
            XCTAssertFalse(error.backendError.message.contains("Mac runtime"))
            XCTAssertTrue(error.retryable)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testCancelUnknownGenerationReturnsNotFound() {
        let backend = makeBackend { _ in
            self.response(statusCode: 200, body: "{}")
        }

        XCTAssertEqual(
            backend.cancel(generationID: "missing"),
            .notFound(generationID: "missing")
        )
    }

    func testCancelActiveGenerationCancelsStream() async {
        let requestStarted = expectation(description: "request started")
        let loadingStopped = expectation(description: "loading stopped")
        SuspendingURLProtocol.onStart = { request in
            XCTAssertEqual(request.url?.path, "/api/chat")
            requestStarted.fulfill()
        }
        SuspendingURLProtocol.onStop = {
            loadingStopped.fulfill()
        }

        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [SuspendingURLProtocol.self]
        let session = URLSession(configuration: configuration)
        let backend = OllamaBackend(baseURL: URL(string: "http://127.0.0.1:11434")!, session: session)
        let request = ChatRequest(
            generationID: "generation-cancel",
            sessionID: "session-1",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Keep going")]
        )

        let streamTask = Task<Error?, Never> {
            do {
                for try await _ in backend.chat(request: request) {}
                return nil
            } catch {
                return error
            }
        }

        await fulfillment(of: [requestStarted], timeout: 1)

        XCTAssertEqual(
            backend.cancel(generationID: "generation-cancel"),
            .cancelled(generationID: "generation-cancel")
        )

        let error = await streamTask.value
        XCTAssertEqual(error as? OllamaBackendError, .generationCancelled(generationID: "generation-cancel"))
        await fulfillment(of: [loadingStopped], timeout: 1)
    }

    private func makeBackend(
        handler: @escaping (URLRequest) throws -> (HTTPURLResponse, Data)
    ) -> OllamaBackend {
        MockURLProtocol.handler = handler
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: configuration)
        return OllamaBackend(baseURL: URL(string: "http://127.0.0.1:11434")!, session: session)
    }

    private func response(statusCode: Int, body: String) -> (HTTPURLResponse, Data) {
        let url = URL(string: "http://127.0.0.1:11434")!
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

private struct PostedChatRequest: Decodable {
    var model: String
    var messages: [ChatMessage]
    var stream: Bool
    var think: Bool
}

private struct PostedPullRequest: Decodable {
    var model: String
    var stream: Bool
}

private struct PostedUnloadRequest: Decodable {
    var model: String
    var messages: [ChatMessage]
    var keepAlive: Int

    enum CodingKeys: String, CodingKey {
        case model
        case messages
        case keepAlive = "keep_alive"
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

private final class SuspendingURLProtocol: URLProtocol {
    static var onStart: ((URLRequest) -> Void)?
    static var onStop: (() -> Void)?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "http://127.0.0.1:11434")!,
            statusCode: 200,
            httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/x-ndjson"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        Self.onStart?(request)
    }

    override func stopLoading() {
        Self.onStop?()
    }
}
