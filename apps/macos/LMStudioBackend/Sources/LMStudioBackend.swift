import Foundation
import OllamaBackend

public final class LMStudioBackend: LlmBackend, @unchecked Sendable {
    public static let defaultBaseURL = URL(string: "http://127.0.0.1:1234")!
    public let provider = ModelProvider.lmStudio

    private let baseURL: URL
    private let session: URLSession
    private let registry = LMStudioGenerationRegistry()
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    public init(baseURL: URL = LMStudioBackend.defaultBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    public func healthCheck() async -> BackendStatus {
        do {
            _ = try await fetchReachabilityModelData()
            return .available
        } catch let error as LMStudioBackendError {
            return .unavailable(error.backendError)
        } catch {
            return .unavailable(LMStudioBackendError.transport(
                endpoint: "GET /api/v1/models",
                reason: error.localizedDescription
            ).backendError)
        }
    }

    public func listModels() async throws -> [ModelInfo] {
        let data: Data
        do {
            data = try await performDataRequest(endpoint: "GET /api/v1/models", url: baseURL.appending(path: "api/v1/models"))
        } catch let error as LMStudioBackendError where error.shouldFallbackToOpenAICompatible {
            return try await listOpenAICompatibleModels()
        }
        do {
            let response = try decoder.decode(LMStudioNativeModelsResponse.self, from: data)
            return response.models.compactMap { model in
                guard model.type == nil || model.type == "llm" else { return nil }
                return ModelInfo(
                    id: model.key,
                    name: model.displayName ?? model.key,
                    provider: .lmStudio,
                    providerModelID: model.key,
                    sizeBytes: model.sizeBytes,
                    installed: true,
                    running: !model.loadedInstances.isEmpty,
                    source: .local
                )
            }
        } catch {
            return try await listOpenAICompatibleModels()
        }
    }

    public func pullModel(name: String) async throws -> ModelPullResult {
        throw LMStudioBackendError.badResponse(
            endpoint: "POST /api/v1/models/download",
            reason: "LM Studio downloads are managed from LM Studio or lms; AetherLink does not expose Android-initiated LM Studio downloads."
        )
    }

    public func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task { [baseURL, session, encoder] in
                do {
                    let availableModels = try await self.listModels()
                    guard !availableModels.isEmpty else {
                        throw LMStudioBackendError.noModels
                    }

                    do {
                        try await Self.streamNativeChat(
                            request: request,
                            baseURL: baseURL,
                            session: session,
                            encoder: encoder,
                            continuation: continuation
                        )
                    } catch let error as LMStudioBackendError where error.shouldFallbackToOpenAICompatible {
                        try Task.checkCancellation()
                        try await Self.streamOpenAICompatibleChat(
                            request: request,
                            baseURL: baseURL,
                            session: session,
                            encoder: encoder,
                            continuation: continuation
                        )
                    }
                    registry.remove(id: request.generationID)
                } catch is CancellationError {
                    continuation.finish(throwing: LMStudioBackendError.generationCancelled(generationID: request.generationID))
                    registry.remove(id: request.generationID)
                } catch let error as URLError where error.code == .cancelled {
                    continuation.finish(throwing: LMStudioBackendError.generationCancelled(generationID: request.generationID))
                    registry.remove(id: request.generationID)
                } catch let error as LMStudioBackendError {
                    continuation.finish(throwing: error)
                    registry.remove(id: request.generationID)
                } catch let error as URLError {
                    continuation.finish(throwing: LMStudioBackendError.unavailable(
                        endpoint: "POST /api/v1/chat",
                        reason: error.localizedDescription
                    ))
                    registry.remove(id: request.generationID)
                } catch {
                    continuation.finish(throwing: LMStudioBackendError.transport(
                        endpoint: "POST /api/v1/chat",
                        reason: error.localizedDescription
                    ))
                    registry.remove(id: request.generationID)
                }
            }

            registry.register(id: request.generationID, task: task)

            continuation.onTermination = { [registry] termination in
                if case .cancelled = termination {
                    _ = registry.cancel(id: request.generationID)
                }
            }
        }
    }

    @discardableResult
    public func cancel(generationID: String) -> GenerationCancellationResult {
        registry.cancel(id: generationID)
    }

    private func fetchReachabilityModelData() async throws -> Data {
        do {
            return try await performDataRequest(endpoint: "GET /api/v1/models", url: baseURL.appending(path: "api/v1/models"))
        } catch let error as LMStudioBackendError where error.shouldFallbackToOpenAICompatible {
            return try await performDataRequest(endpoint: "GET /v1/models", url: baseURL.appending(path: "v1/models"))
        }
    }

    private func listOpenAICompatibleModels() async throws -> [ModelInfo] {
        let data = try await performDataRequest(endpoint: "GET /v1/models", url: baseURL.appending(path: "v1/models"))
        do {
            let response = try decoder.decode(OpenAIModelsResponse.self, from: data)
            return response.data.map { model in
                ModelInfo(
                    id: model.id,
                    name: model.id,
                    provider: .lmStudio,
                    providerModelID: model.id,
                    installed: true,
                    running: false,
                    source: .local
                )
            }
        } catch {
            throw LMStudioBackendError.badResponse(endpoint: "GET /v1/models", reason: error.localizedDescription)
        }
    }

    private func performDataRequest(endpoint: String, url: URL) async throws -> Data {
        try await performDataRequest(endpoint: endpoint, request: URLRequest(url: url))
    }

    private func performDataRequest(endpoint: String, request: URLRequest) async throws -> Data {
        do {
            let (data, response) = try await session.data(for: request)
            try Self.validate(response, endpoint: endpoint, body: data)
            return data
        } catch let error as LMStudioBackendError {
            throw error
        } catch let error as URLError {
            throw LMStudioBackendError.unavailable(endpoint: endpoint, reason: error.localizedDescription)
        } catch {
            throw LMStudioBackendError.transport(endpoint: endpoint, reason: error.localizedDescription)
        }
    }

    private static func streamNativeChat(
        request: ChatRequest,
        baseURL: URL,
        session: URLSession,
        encoder: JSONEncoder,
        continuation: AsyncThrowingStream<ChatStreamEvent, Error>.Continuation
    ) async throws {
        let endpoint = "POST /api/v1/chat"
        var urlRequest = URLRequest(url: baseURL.appending(path: "api/v1/chat"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try encode(
            LMStudioNativeChatRequest(model: request.model, messages: request.messages),
            encoder: encoder,
            endpoint: endpoint
        )

        let (bytes, response) = try await session.bytes(for: urlRequest)
        try validate(response, endpoint: endpoint, body: nil)

        var parser = ServerSentEventParser()
        for try await line in bytes.lines {
            try Task.checkCancellation()
            let events = try parser.append(line)
            for event in events {
                try handleNativeEvent(event, continuation: continuation, endpoint: endpoint)
                if event.name == "chat.end" {
                    continuation.finish()
                    return
                }
            }
        }

        for event in parser.finish() {
            try handleNativeEvent(event, continuation: continuation, endpoint: endpoint)
        }
        continuation.finish()
    }

    private static func streamOpenAICompatibleChat(
        request: ChatRequest,
        baseURL: URL,
        session: URLSession,
        encoder: JSONEncoder,
        continuation: AsyncThrowingStream<ChatStreamEvent, Error>.Continuation
    ) async throws {
        let endpoint = "POST /v1/chat/completions"
        var urlRequest = URLRequest(url: baseURL.appending(path: "v1/chat/completions"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try encode(
            OpenAIChatCompletionsRequest(model: request.model, messages: request.messages, stream: true),
            encoder: encoder,
            endpoint: endpoint
        )

        let (bytes, response) = try await session.bytes(for: urlRequest)
        try validate(response, endpoint: endpoint, body: nil)

        var inputTokens: Int?
        var outputTokens: Int?
        for try await line in bytes.lines {
            try Task.checkCancellation()
            guard let chunk = try decodeOpenAIStreamLine(line, endpoint: endpoint) else { continue }
            if let content = chunk.choices.first?.delta.content, !content.isEmpty {
                continuation.yield(.delta(content))
            }
            if let usage = chunk.usage {
                inputTokens = usage.promptTokens
                outputTokens = usage.completionTokens
            }
            if chunk.choices.contains(where: { $0.finishReason != nil }) {
                continuation.yield(.done(inputTokens: inputTokens, outputTokens: outputTokens))
                continuation.finish()
                return
            }
        }
        continuation.finish()
    }

    private static func handleNativeEvent(
        _ event: ServerSentEvent,
        continuation: AsyncThrowingStream<ChatStreamEvent, Error>.Continuation,
        endpoint: String
    ) throws {
        guard let data = event.data.data(using: .utf8) else {
            throw LMStudioBackendError.streamDecoding(line: event.data, reason: "Event data is not valid UTF-8")
        }
        switch event.name {
        case "message.delta":
            let delta = try decode(LMStudioMessageDelta.self, from: data, endpoint: endpoint, line: event.data)
            if !delta.content.isEmpty {
                continuation.yield(.delta(delta.content))
            }
        case "error":
            let payload = try decode(LMStudioStreamError.self, from: data, endpoint: endpoint, line: event.data)
            throw LMStudioBackendError.badResponse(endpoint: endpoint, reason: payload.error.message)
        case "chat.end":
            let end = try decode(LMStudioChatEnd.self, from: data, endpoint: endpoint, line: event.data)
            continuation.yield(.done(
                inputTokens: end.result.stats?.inputTokens,
                outputTokens: end.result.stats?.totalOutputTokens
            ))
        default:
            break
        }
    }

    private static func validate(_ response: URLResponse, endpoint: String, body: Data?) throws {
        guard let http = response as? HTTPURLResponse else {
            throw LMStudioBackendError.transport(endpoint: endpoint, reason: "Missing HTTP response")
        }
        guard (200..<300).contains(http.statusCode) else {
            let bodyString = body.flatMap { String(data: $0, encoding: .utf8) }
            throw LMStudioBackendError.httpStatus(endpoint: endpoint, statusCode: http.statusCode, body: bodyString)
        }
    }

    private static func encode<T: Encodable>(_ request: T, encoder: JSONEncoder, endpoint: String) throws -> Data {
        do {
            return try encoder.encode(request)
        } catch {
            throw LMStudioBackendError.requestEncoding(endpoint: endpoint, reason: error.localizedDescription)
        }
    }

    private static func decode<T: Decodable>(_ type: T.Type, from data: Data, endpoint: String, line: String) throws -> T {
        do {
            return try JSONDecoder().decode(type, from: data)
        } catch {
            throw LMStudioBackendError.streamDecoding(line: line, reason: error.localizedDescription)
        }
    }

    private static func decodeOpenAIStreamLine(_ line: String, endpoint: String) throws -> OpenAIChatChunk? {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        let jsonLine: String
        if trimmed.hasPrefix("data:") {
            jsonLine = String(trimmed.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces)
        } else {
            jsonLine = trimmed
        }

        guard !jsonLine.isEmpty, jsonLine != "[DONE]" else { return nil }
        guard let data = jsonLine.data(using: .utf8) else {
            throw LMStudioBackendError.streamDecoding(line: line, reason: "Line is not valid UTF-8")
        }

        do {
            return try JSONDecoder().decode(OpenAIChatChunk.self, from: data)
        } catch {
            throw LMStudioBackendError.streamDecoding(line: line, reason: error.localizedDescription)
        }
    }
}

private extension LMStudioBackendError {
    var shouldFallbackToOpenAICompatible: Bool {
        switch self {
        case .httpStatus(_, let statusCode, _):
            return statusCode == 400 || statusCode == 404 || statusCode == 405 || statusCode == 422
        case .badResponse, .streamDecoding:
            return true
        case .unavailable, .noModels, .requestEncoding, .generationCancelled, .generationNotFound, .transport:
            return false
        }
    }
}

private final class LMStudioGenerationRegistry: @unchecked Sendable {
    private let lock = NSLock()
    private var tasks: [String: Task<Void, Never>] = [:]

    func register(id: String, task: Task<Void, Never>) {
        lock.withLock {
            tasks[id] = task
        }
    }

    func cancel(id: String) -> GenerationCancellationResult {
        lock.withLock {
            guard let task = tasks.removeValue(forKey: id) else {
                return .notFound(generationID: id)
            }
            task.cancel()
            return .cancelled(generationID: id)
        }
    }

    func remove(id: String) {
        lock.withLock {
            tasks[id] = nil
        }
    }
}

private struct LMStudioNativeModelsResponse: Decodable {
    var models: [LMStudioNativeModel]
}

private struct LMStudioNativeModel: Decodable {
    var type: String?
    var key: String
    var displayName: String?
    var sizeBytes: Int64?
    var loadedInstances: [LMStudioLoadedInstance]

    enum CodingKeys: String, CodingKey {
        case type
        case key
        case id
        case displayName = "display_name"
        case sizeBytes = "size_bytes"
        case loadedInstances = "loaded_instances"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        type = try container.decodeIfPresent(String.self, forKey: .type)
        key = try container.decodeIfPresent(String.self, forKey: .key)
            ?? container.decode(String.self, forKey: .id)
        displayName = try container.decodeIfPresent(String.self, forKey: .displayName)
        sizeBytes = try container.decodeIfPresent(Int64.self, forKey: .sizeBytes)
        loadedInstances = try container.decodeIfPresent([LMStudioLoadedInstance].self, forKey: .loadedInstances) ?? []
    }
}

private struct LMStudioLoadedInstance: Decodable {
    var id: String
}

private struct OpenAIModelsResponse: Decodable {
    var data: [OpenAIModel]
}

private struct OpenAIModel: Decodable {
    var id: String
}

private struct LMStudioNativeChatRequest: Encodable {
    var model: String
    var input: [LMStudioInputMessage]
    var stream = true
    var store = false

    init(model: String, messages: [ChatMessage]) {
        self.model = model
        input = messages.map { LMStudioInputMessage(role: $0.role, content: $0.content) }
    }
}

private struct LMStudioInputMessage: Encodable {
    var type = "message"
    var role: String
    var content: String
}

private struct OpenAIChatCompletionsRequest: Encodable {
    var model: String
    var messages: [ChatMessage]
    var stream: Bool
}

private struct LMStudioMessageDelta: Decodable {
    var content: String
}

private struct LMStudioStreamError: Decodable {
    var error: LMStudioStreamErrorBody
}

private struct LMStudioStreamErrorBody: Decodable {
    var message: String
}

private struct LMStudioChatEnd: Decodable {
    var result: LMStudioChatResult
}

private struct LMStudioChatResult: Decodable {
    var stats: LMStudioChatStats?
}

private struct LMStudioChatStats: Decodable {
    var inputTokens: Int?
    var totalOutputTokens: Int?

    enum CodingKeys: String, CodingKey {
        case inputTokens = "input_tokens"
        case totalOutputTokens = "total_output_tokens"
    }
}

private struct OpenAIChatChunk: Decodable {
    var choices: [OpenAIChatChoice]
    var usage: OpenAIUsage?
}

private struct OpenAIChatChoice: Decodable {
    var delta: OpenAIChatDelta
    var finishReason: String?

    enum CodingKeys: String, CodingKey {
        case delta
        case finishReason = "finish_reason"
    }
}

private struct OpenAIChatDelta: Decodable {
    var content: String?
}

private struct OpenAIUsage: Decodable {
    var promptTokens: Int?
    var completionTokens: Int?

    enum CodingKeys: String, CodingKey {
        case promptTokens = "prompt_tokens"
        case completionTokens = "completion_tokens"
    }
}

private struct ServerSentEvent {
    var name: String
    var data: String
}

private struct ServerSentEventParser {
    private var eventName = "message"
    private var dataLines: [String] = []

    mutating func append(_ line: String) throws -> [ServerSentEvent] {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return flush()
        }
        if trimmed.hasPrefix("event:") {
            let pending = flush()
            eventName = String(trimmed.dropFirst("event:".count)).trimmingCharacters(in: .whitespaces)
            return pending
        }
        if trimmed.hasPrefix("data:") {
            dataLines.append(String(trimmed.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces))
            return []
        }
        if trimmed.hasPrefix(":") {
            return []
        }
        throw LMStudioBackendError.streamDecoding(line: line, reason: "Unsupported SSE field")
    }

    mutating func finish() -> [ServerSentEvent] {
        flush()
    }

    private mutating func flush() -> [ServerSentEvent] {
        guard !dataLines.isEmpty else {
            eventName = "message"
            return []
        }
        let event = ServerSentEvent(name: eventName, data: dataLines.joined(separator: "\n"))
        eventName = "message"
        dataLines = []
        return [event]
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
