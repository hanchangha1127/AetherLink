import Foundation

public final class OllamaBackend: LlmBackend, @unchecked Sendable {
    public static let defaultBaseURL = URL(string: "http://127.0.0.1:11434")!
    public let provider = ModelProvider.ollama

    private let baseURL: URL
    private let session: URLSession
    private let registry = GenerationRegistry()
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    public init(baseURL: URL = OllamaBackend.defaultBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    public func healthCheck() async -> BackendStatus {
        do {
            _ = try await performDataRequest(endpoint: "GET /api/tags", url: baseURL.appending(path: "api/tags"))
            return .available
        } catch let error as OllamaBackendError {
            return .unavailable(error.backendError)
        } catch {
            return .unavailable(OllamaBackendError.transport(
                endpoint: "GET /api/tags",
                reason: error.localizedDescription
            ).backendError)
        }
    }

    public func listModels() async throws -> [ModelInfo] {
        let tagsEndpoint = "GET /api/tags"
        let tagsData = try await performDataRequest(endpoint: tagsEndpoint, url: baseURL.appending(path: "api/tags"))
        let psEndpoint = "GET /api/ps"
        let psData = try await performDataRequest(endpoint: psEndpoint, url: baseURL.appending(path: "api/ps"))
        do {
            let tags = try decoder.decode(OllamaTagsResponse.self, from: tagsData)
            let running = try decoder.decode(OllamaRunningModelsResponse.self, from: psData)
            let detailsByName = await modelDetailsByName(
                names: Self.uniqueModelNames(tags.models.map(\.name) + running.models.map(\.name))
            )
            return Self.mergeModels(
                installedModels: tags.models,
                runningModels: running.models,
                detailsByName: detailsByName
            )
        } catch let error as DecodingError {
            throw OllamaBackendError.responseDecoding(endpoint: "\(tagsEndpoint), \(psEndpoint)", reason: error.localizedDescription)
        } catch {
            throw OllamaBackendError.responseDecoding(endpoint: "\(tagsEndpoint), \(psEndpoint)", reason: error.localizedDescription)
        }
    }

    public func pullModel(name: String) async throws -> ModelPullResult {
        let endpoint = "POST /api/pull"
        var urlRequest = URLRequest(url: baseURL.appending(path: "api/pull"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            urlRequest.httpBody = try encoder.encode(OllamaPullRequest(model: name, stream: false))
        } catch {
            throw OllamaBackendError.requestEncoding(endpoint: endpoint, reason: error.localizedDescription)
        }

        let data = try await performDataRequest(endpoint: endpoint, request: urlRequest)
        do {
            let decoded = try decoder.decode(OllamaPullResponse.self, from: data)
            return ModelPullResult(model: name, status: decoded.status ?? "success", installed: true)
        } catch {
            throw OllamaBackendError.responseDecoding(endpoint: endpoint, reason: error.localizedDescription)
        }
    }

    public func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        let endpoint = "POST /api/chat"
        var urlRequest = URLRequest(url: baseURL.appending(path: "api/chat"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            urlRequest.httpBody = try encoder.encode(OllamaUnloadRequest(model: providerModelID))
        } catch {
            throw OllamaBackendError.requestEncoding(endpoint: endpoint, reason: error.localizedDescription)
        }

        _ = try await performDataRequest(endpoint: endpoint, request: urlRequest)
        return .unloaded(provider: provider, modelID: providerModelID)
    }

    private static func mergeModels(
        installedModels: [OllamaModel],
        runningModels: [OllamaRunningModel],
        detailsByName: [String: OllamaModelDetails] = [:]
    ) -> [ModelInfo] {
        var result: [ModelInfo] = []
        var indexesByID: [String: Int] = [:]
        var indexesByCanonicalName: [String: Int] = [:]

        func remember(_ model: ModelInfo) {
            indexesByID[model.id] = result.count
            indexesByCanonicalName[canonicalModelName(model.id)] = result.count
            result.append(model)
        }

        for model in installedModels {
            let details = modelDetails(for: model.name, in: detailsByName)
            let capabilities = inferredCapabilities(
                details.capabilities,
                for: model.name
            )
            let kind = ModelKind.from(capabilities: capabilities, fallbackName: model.name)
            remember(ModelInfo(
                id: model.name,
                name: model.name,
                provider: .ollama,
                kind: kind,
                capabilities: capabilities.isEmpty ? nil : capabilities,
                sizeBytes: model.size,
                modifiedAt: model.modifiedAt,
                installed: true,
                running: false,
                source: model.source,
                remoteModel: model.remoteModel,
                remoteHost: model.remoteHost,
                contextWindowTokens: details.contextWindowTokens
            ))
        }

        for model in runningModels {
            if let existingIndex = indexesByID[model.name] ?? indexesByCanonicalName[canonicalModelName(model.name)] {
                result[existingIndex].running = true
                if result[existingIndex].sizeBytes == nil {
                    result[existingIndex].sizeBytes = model.size
                }
                if result[existingIndex].contextWindowTokens == nil {
                    result[existingIndex].contextWindowTokens = modelDetails(for: model.name, in: detailsByName).contextWindowTokens
                }
            } else {
                if model.source == .cloud {
                    continue
                }
                let details = modelDetails(for: model.name, in: detailsByName)
                let capabilities = inferredCapabilities(
                    details.capabilities,
                    for: model.name
                )
                let kind = ModelKind.from(capabilities: capabilities, fallbackName: model.name)
                remember(ModelInfo(
                    id: model.name,
                    name: model.name,
                    provider: .ollama,
                    kind: kind,
                    capabilities: capabilities.isEmpty ? nil : capabilities,
                    sizeBytes: model.size,
                    installed: true,
                    running: true,
                    source: model.source,
                    contextWindowTokens: details.contextWindowTokens
                ))
            }
        }

        return result
    }

    private func modelDetailsByName(names: [String]) async -> [String: OllamaModelDetails] {
        var result: [String: OllamaModelDetails] = [:]
        for name in names where !name.isEmpty {
            do {
                let details = try await fetchModelDetails(name: name)
                if !details.isEmpty {
                    result[name] = details
                    result[Self.canonicalModelName(name)] = details
                }
            } catch {
                continue
            }
        }
        return result
    }

    private func fetchModelDetails(name: String) async throws -> OllamaModelDetails {
        let endpoint = "POST /api/show"
        var urlRequest = URLRequest(url: baseURL.appending(path: "api/show"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try encoder.encode(OllamaShowRequest(model: name))
        let data = try await performDataRequest(endpoint: endpoint, request: urlRequest)
        let response = try decoder.decode(OllamaShowResponse.self, from: data)
        let capabilities = response.capabilities.map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        }.filter { !$0.isEmpty }
        return OllamaModelDetails(
            capabilities: capabilities,
            contextWindowTokens: response.contextWindowTokens
        )
    }

    private static func modelDetails(for name: String, in detailsByName: [String: OllamaModelDetails]) -> OllamaModelDetails {
        detailsByName[name] ?? detailsByName[canonicalModelName(name)] ?? OllamaModelDetails()
    }

    private static func canonicalModelName(_ name: String) -> String {
        if name.hasSuffix(":latest") {
            return String(name.dropLast(":latest".count))
        }
        return name
    }

    private static func inferredCapabilities(_ capabilities: [String], for modelName: String) -> [String] {
        var result = capabilities
        let normalized = Set(result.map { $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() })
        if modelName.looksLikeVisionModelName && !normalized.contains("vision") {
            result.append("vision")
        }
        if result.contains(where: { $0 == "vision" }) && !normalized.contains("chat") && !normalized.contains("completion") {
            result.append("chat")
        }
        return result.map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        }.filter { !$0.isEmpty }.reduce(into: [String]()) { unique, capability in
            if !unique.contains(capability) {
                unique.append(capability)
            }
        }
    }

    private static func uniqueModelNames(_ names: [String]) -> [String] {
        var seen: Set<String> = []
        return names.filter { name in
            guard !seen.contains(name) else { return false }
            seen.insert(name)
            return true
        }
    }

    private func performDataRequest(endpoint: String, request: URLRequest) async throws -> Data {
        do {
            let (data, response) = try await session.data(for: request)
            try Self.validate(response, endpoint: endpoint, body: data)
            return data
        } catch let error as OllamaBackendError {
            throw error
        } catch let error as URLError {
            throw OllamaBackendError.unreachable(
                endpoint: endpoint,
                baseURL: baseURL.absoluteString,
                reason: error.localizedDescription
            )
        } catch {
            throw OllamaBackendError.transport(endpoint: endpoint, reason: error.localizedDescription)
        }
    }

    private func performDataRequest(endpoint: String, url: URL) async throws -> Data {
        try await performDataRequest(endpoint: endpoint, request: URLRequest(url: url))
    }

    public func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task { [baseURL, session, encoder] in
                let endpoint = "POST /api/chat"
                do {
                    var urlRequest = URLRequest(url: baseURL.appending(path: "api/chat"))
                    urlRequest.httpMethod = "POST"
                    urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
                    urlRequest.httpBody = try Self.encodeChatRequest(
                        OllamaChatRequest(model: request.model, messages: request.messages, stream: true, think: true),
                        encoder: encoder,
                        endpoint: endpoint
                    )

                    let (bytes, response) = try await session.bytes(for: urlRequest)
                    try Self.validate(response, endpoint: endpoint, body: nil)

                    for try await line in bytes.lines {
                        try Task.checkCancellation()
                        guard let chunk = try Self.decodeStreamLine(line, endpoint: endpoint) else { continue }
                        if let thinking = chunk.message?.thinking, !thinking.isEmpty {
                            continuation.yield(.reasoningDelta(thinking))
                        }
                        if let content = chunk.message?.content, !content.isEmpty {
                            continuation.yield(.delta(content))
                        }
                        if chunk.done == true {
                            continuation.yield(.done(inputTokens: chunk.promptEvalCount, outputTokens: chunk.evalCount))
                            continuation.finish()
                            registry.remove(id: request.generationID)
                            return
                        }
                    }

                    continuation.finish()
                    registry.remove(id: request.generationID)
                } catch is CancellationError {
                    continuation.finish(throwing: OllamaBackendError.generationCancelled(generationID: request.generationID))
                    registry.remove(id: request.generationID)
                } catch let error as URLError where error.code == .cancelled {
                    continuation.finish(throwing: OllamaBackendError.generationCancelled(generationID: request.generationID))
                    registry.remove(id: request.generationID)
                } catch let error as OllamaBackendError {
                    continuation.finish(throwing: error)
                    registry.remove(id: request.generationID)
                } catch let error as URLError {
                    continuation.finish(throwing: OllamaBackendError.unreachable(
                        endpoint: endpoint,
                        baseURL: baseURL.absoluteString,
                        reason: error.localizedDescription
                    ))
                    registry.remove(id: request.generationID)
                } catch {
                    continuation.finish(throwing: OllamaBackendError.transport(endpoint: endpoint, reason: error.localizedDescription))
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

    private static func encodeChatRequest(
        _ request: OllamaChatRequest,
        encoder: JSONEncoder,
        endpoint: String
    ) throws -> Data {
        do {
            return try encoder.encode(request)
        } catch {
            throw OllamaBackendError.requestEncoding(endpoint: endpoint, reason: error.localizedDescription)
        }
    }

    private static func validate(_ response: URLResponse, endpoint: String, body: Data?) throws {
        guard let http = response as? HTTPURLResponse else {
            throw OllamaBackendError.transport(endpoint: endpoint, reason: "Missing HTTP response")
        }
        guard (200..<300).contains(http.statusCode) else {
            let bodyString = body.flatMap { String(data: $0, encoding: .utf8) }
            throw OllamaBackendError.httpStatus(endpoint: endpoint, statusCode: http.statusCode, body: bodyString)
        }
    }

    private static func decodeStreamLine(_ line: String, endpoint: String) throws -> OllamaChatChunk? {
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
            throw OllamaBackendError.streamDecoding(line: line, reason: "Line is not valid UTF-8")
        }

        do {
            return try JSONDecoder().decode(OllamaChatChunk.self, from: data)
        } catch {
            throw OllamaBackendError.streamDecoding(line: line, reason: error.localizedDescription)
        }
    }
}

private extension String {
    var looksLikeVisionModelName: Bool {
        let value = lowercased()
        return [
            "vision",
            "visual",
            "vl",
            "llava",
            "bakllava",
            "moondream",
            "minicpm-v",
            "qwen2-vl",
            "qwen2.5-vl",
            "qwen3-vl",
            "llama3.2-vision",
            "gemma3",
        ].contains { value.contains($0) }
    }
}

private final class GenerationRegistry: @unchecked Sendable {
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

private struct OllamaTagsResponse: Decodable {
    var models: [OllamaModel]
}

private struct OllamaModel: Decodable {
    var name: String
    var size: Int64?
    var modifiedAt: Date?
    var remoteModel: String?
    var remoteHost: String?
    var source: ModelSource {
        Self.modelSource(name: name, remoteModel: remoteModel, remoteHost: remoteHost)
    }

    enum CodingKeys: String, CodingKey {
        case name
        case model
        case size
        case modifiedAt = "modified_at"
        case remoteModel = "remote_model"
        case remoteHost = "remote_host"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        name = try container.decodeIfPresent(String.self, forKey: .name)
            ?? container.decode(String.self, forKey: .model)
        size = try container.decodeIfPresent(Int64.self, forKey: .size)
        remoteModel = try container.decodeIfPresent(String.self, forKey: .remoteModel)
        remoteHost = try container.decodeIfPresent(String.self, forKey: .remoteHost)
        let modifiedAtString = try container.decodeIfPresent(String.self, forKey: .modifiedAt)
        modifiedAt = modifiedAtString.flatMap(Self.parseDate)
    }

    private static func parseDate(_ string: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: string) {
            return date
        }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: string)
    }

    fileprivate static func modelSource(name: String, remoteModel: String?, remoteHost: String?) -> ModelSource {
        if let remoteModel, !remoteModel.isEmpty {
            return .cloud
        }
        if let remoteHost, !remoteHost.isEmpty {
            return .cloud
        }
        let lowercasedName = name.lowercased()
        if lowercasedName.hasSuffix(":cloud") || lowercasedName.hasSuffix("-cloud") {
            return .cloud
        }
        return .local
    }
}

private struct OllamaRunningModelsResponse: Decodable {
    var models: [OllamaRunningModel]
}

private struct OllamaRunningModel: Decodable {
    var name: String
    var size: Int64?
    var source: ModelSource {
        OllamaModel.modelSource(name: name, remoteModel: nil, remoteHost: nil)
    }

    enum CodingKeys: String, CodingKey {
        case name
        case model
        case size
        case sizeVRAM = "size_vram"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        if let name = try container.decodeIfPresent(String.self, forKey: .name) {
            self.name = name
        } else {
            self.name = try container.decode(String.self, forKey: .model)
        }
        size = try container.decodeIfPresent(Int64.self, forKey: .size)
            ?? container.decodeIfPresent(Int64.self, forKey: .sizeVRAM)
    }
}

private struct OllamaPullRequest: Encodable {
    var model: String
    var stream: Bool
}

private struct OllamaPullResponse: Decodable {
    var status: String?
}

private struct OllamaUnloadRequest: Encodable {
    var model: String
    var messages: [OllamaChatMessage] = []
    var keepAlive = 0

    enum CodingKeys: String, CodingKey {
        case model
        case messages
        case keepAlive = "keep_alive"
    }
}

private struct OllamaShowRequest: Encodable {
    var model: String
}

private struct OllamaModelDetails {
    var capabilities: [String] = []
    var contextWindowTokens: Int?

    var isEmpty: Bool {
        capabilities.isEmpty && contextWindowTokens == nil
    }
}

private struct OllamaShowResponse: Decodable {
    var capabilities: [String]
    var contextWindowTokens: Int?

    enum CodingKeys: String, CodingKey {
        case capabilities
        case contextLength = "context_length"
        case contextWindow = "context_window"
        case contextWindowTokens = "context_window_tokens"
        case numCtx = "num_ctx"
        case modelInfo = "model_info"
        case parameters
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        capabilities = try container.decodeIfPresent([String].self, forKey: .capabilities) ?? []

        let directContextWindow = try Self.firstPositive(
            container.decodeIfPresent(Int.self, forKey: .contextWindowTokens),
            container.decodeIfPresent(Int.self, forKey: .contextLength),
            container.decodeIfPresent(Int.self, forKey: .contextWindow),
            container.decodeIfPresent(Int.self, forKey: .numCtx)
        )
        let modelInfo = try container.decodeIfPresent([String: FlexibleInt].self, forKey: .modelInfo)
        let modelInfoContextWindow = Self.firstPositive(
            modelInfo?["llama.context_length"]?.value,
            modelInfo?["general.context_length"]?.value,
            modelInfo?["context_length"]?.value,
            modelInfo?["num_ctx"]?.value
        )
        let parameters = try container.decodeIfPresent(String.self, forKey: .parameters)
        contextWindowTokens = directContextWindow
            ?? modelInfoContextWindow
            ?? Self.contextWindowTokens(fromParameters: parameters)
    }

    private static func firstPositive(_ values: Int?...) -> Int? {
        values.first { ($0 ?? 0) > 0 } ?? nil
    }

    private static func contextWindowTokens(fromParameters parameters: String?) -> Int? {
        guard let parameters else { return nil }
        for line in parameters.split(whereSeparator: \.isNewline) {
            let parts = line.split { character in
                character == " " || character == "\t" || character == "="
            }
            guard parts.count >= 2 else { continue }
            guard parts[0].trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "num_ctx" else {
                continue
            }
            if let value = Int(parts[1]), value > 0 {
                return value
            }
        }
        return nil
    }
}

private struct FlexibleInt: Decodable {
    var value: Int?

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = Int(double)
        } else if let string = try? container.decode(String.self) {
            value = Int(string.trimmingCharacters(in: .whitespacesAndNewlines))
        } else {
            value = nil
        }
    }
}

private struct OllamaChatRequest: Encodable {
    var model: String
    var messages: [OllamaChatMessage]
    var stream: Bool
    var think: Bool

    init(model: String, messages: [ChatMessage], stream: Bool, think: Bool) {
        self.model = model
        self.messages = messages.map(OllamaChatMessage.init(message:))
        self.stream = stream
        self.think = think
    }
}

private struct OllamaChatMessage: Encodable {
    var role: String
    var content: String
    var images: [String]

    init(message: ChatMessage) {
        role = message.role
        content = message.content
        images = message.attachments.compactMap { attachment in
            let normalizedType = attachment.type.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            let normalizedMimeType = attachment.mimeType.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard normalizedType == "image" || normalizedMimeType.hasPrefix("image/") else {
                return nil
            }
            return attachment.dataBase64
        }
    }

    enum CodingKeys: String, CodingKey {
        case role
        case content
        case images
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(role, forKey: .role)
        try container.encode(content, forKey: .content)
        if !images.isEmpty {
            try container.encode(images, forKey: .images)
        }
    }
}

private struct OllamaChatChunk: Decodable {
    var message: OllamaChatChunkMessage?
    var done: Bool?
    var promptEvalCount: Int?
    var evalCount: Int?

    enum CodingKeys: String, CodingKey {
        case message
        case done
        case promptEvalCount = "prompt_eval_count"
        case evalCount = "eval_count"
    }
}

private struct OllamaChatChunkMessage: Decodable {
    var content: String?
    var thinking: String?
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
