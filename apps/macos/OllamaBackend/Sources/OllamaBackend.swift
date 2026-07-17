import Foundation

public final class OllamaBackend: LlmBackend, @unchecked Sendable {
    public static let defaultBaseURL = URL(string: "http://127.0.0.1:11434")!
    public let provider = ModelProvider.ollama

    private static let defaultUnloadPollAttempts = 20
    private static let defaultUnloadPollIntervalNanoseconds: UInt64 = 100_000_000

    private let baseURL: URL
    private let session: URLSession
    private let unloadPollAttempts: Int
    private let unloadPollIntervalNanoseconds: UInt64
    private let unloadSleeper: @Sendable (UInt64) async throws -> Void
    private let catalogResponseByteLimit: Int
    private let registry = GenerationRegistry()
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    public init(baseURL: URL = OllamaBackend.defaultBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        self.unloadPollAttempts = Self.defaultUnloadPollAttempts
        self.unloadPollIntervalNanoseconds = Self.defaultUnloadPollIntervalNanoseconds
        self.unloadSleeper = { try await Task.sleep(nanoseconds: $0) }
        self.catalogResponseByteLimit = ModelInfo.maximumCatalogResponseBytes
    }

    init(
        baseURL: URL,
        session: URLSession,
        unloadPollAttempts: Int,
        catalogResponseByteLimit: Int = ModelInfo.maximumCatalogResponseBytes,
        unloadPollIntervalNanoseconds: UInt64 = 0,
        unloadSleeper: @escaping @Sendable (UInt64) async throws -> Void = { _ in }
    ) {
        self.baseURL = baseURL
        self.session = session
        self.unloadPollAttempts = max(1, unloadPollAttempts)
        self.catalogResponseByteLimit = max(0, catalogResponseByteLimit)
        self.unloadPollIntervalNanoseconds = unloadPollIntervalNanoseconds
        self.unloadSleeper = unloadSleeper
    }

    public func healthCheck() async -> BackendStatus {
        do {
            let endpoint = "GET /api/tags"
            let data = try await performCatalogDataRequest(endpoint: endpoint, url: baseURL.appending(path: "api/tags"))
            _ = try decodeTagsResponse(data, endpoint: endpoint)
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
        let tagsData = try await performCatalogDataRequest(endpoint: tagsEndpoint, url: baseURL.appending(path: "api/tags"))
        let tags = try decodeTagsResponse(tagsData, endpoint: tagsEndpoint)
        let psEndpoint = "GET /api/ps"
        let psData = try await performCatalogDataRequest(endpoint: psEndpoint, url: baseURL.appending(path: "api/ps"))
        let running = try decodeRunningModelsResponse(psData, endpoint: psEndpoint)
        let detailNames = Self.uniqueModelNames(tags.models.map(\.name) + running.models.map(\.name))
        guard detailNames.count <= ModelInfo.maximumCatalogModelCount else {
            throw OllamaBackendError.responseDecoding(
                endpoint: tagsEndpoint,
                reason: "The model catalog exceeds the supported row limit."
            )
        }
        let detailsByName = try await modelDetailsByName(
            names: detailNames
        )
        do {
            return try Self.mergeModels(
                installedModels: tags.models,
                runningModels: running.models,
                detailsByName: detailsByName
            )
        } catch {
            throw OllamaBackendError.responseDecoding(
                endpoint: tagsEndpoint,
                reason: error.localizedDescription
            )
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
        guard let runningModelID = try await findRunningModelID(matching: providerModelID) else {
            return .alreadyAbsent(provider: provider, modelID: providerModelID)
        }

        let endpoint = "POST /api/chat"
        var urlRequest = URLRequest(url: baseURL.appending(path: "api/chat"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            urlRequest.httpBody = try encoder.encode(OllamaUnloadRequest(model: runningModelID))
        } catch {
            throw OllamaBackendError.requestEncoding(endpoint: endpoint, reason: error.localizedDescription)
        }

        let acknowledgementData = try await performDataRequest(endpoint: endpoint, request: urlRequest)
        let acknowledgement: OllamaUnloadResponse
        do {
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: acknowledgementData)
            acknowledgement = try decoder.decode(OllamaUnloadResponse.self, from: acknowledgementData)
        } catch {
            throw OllamaBackendError.unloadNotConfirmed(reason: "The provider acknowledgement was malformed.")
        }
        guard acknowledgement.done == true, acknowledgement.doneReason == "unload" else {
            throw OllamaBackendError.unloadNotConfirmed(reason: "The provider acknowledgement was not terminal.")
        }

        for attempt in 0..<unloadPollAttempts {
            try Task.checkCancellation()
            if try await findRunningModelID(matching: providerModelID) == nil {
                return .unloaded(provider: provider, modelID: providerModelID)
            }
            if attempt + 1 < unloadPollAttempts {
                try await unloadSleeper(unloadPollIntervalNanoseconds)
            }
        }

        throw OllamaBackendError.unloadNotConfirmed(reason: "The model remained resident after bounded verification.")
    }

    private func findRunningModelID(matching modelID: String) async throws -> String? {
        let endpoint = "GET /api/ps"
        let data = try await performCatalogDataRequest(endpoint: endpoint, url: baseURL.appending(path: "api/ps"))
        let response = try decodeRunningModelsResponse(data, endpoint: endpoint)
        let exactTarget = Data(modelID.utf8)
        if let exact = response.models.first(where: { Data($0.name.utf8) == exactTarget }) {
            return exact.name
        }
        let canonicalTarget = Data(Self.canonicalModelName(modelID).utf8)
        return response.models.first(where: {
            Data(Self.canonicalModelName($0.name).utf8) == canonicalTarget
        })?.name
    }

    public func embed(request: EmbeddingRequest) async throws -> EmbeddingResult {
        let endpoint = "POST /api/embed"
        var urlRequest = URLRequest(url: baseURL.appending(path: "api/embed"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            urlRequest.httpBody = try encoder.encode(OllamaEmbedRequest(
                model: request.model,
                input: request.texts
            ))
        } catch {
            throw OllamaBackendError.requestEncoding(endpoint: endpoint, reason: error.localizedDescription)
        }

        let data = try await performDataRequest(endpoint: endpoint, request: urlRequest)
        let response: OllamaEmbedResponse
        do {
            response = try decoder.decode(OllamaEmbedResponse.self, from: data)
        } catch {
            throw OllamaBackendError.responseDecoding(endpoint: endpoint, reason: error.localizedDescription)
        }
        try Self.validateEmbeddings(response.embeddings, expectedCount: request.texts.count, endpoint: endpoint)
        return EmbeddingResult(model: response.model ?? request.model, embeddings: response.embeddings)
    }

    private static func mergeModels(
        installedModels: [OllamaModel],
        runningModels: [OllamaRunningModel],
        detailsByName: [Data: OllamaModelDetails] = [:]
    ) throws -> [ModelInfo] {
        var result: [ModelInfo] = []
        var indexesByID: [Data: Int] = [:]
        var indexesByCanonicalName: [Data: Int] = [:]

        func remember(_ model: ModelInfo) throws {
            try ModelInfo.validateForCatalogPublication(model)
            indexesByID[Data(model.id.utf8)] = result.count
            indexesByCanonicalName[Data(canonicalModelName(model.id).utf8)] = result.count
            result.append(model)
        }

        for model in installedModels {
            let details = modelDetails(for: model.name, in: detailsByName)
            guard details.isTrusted else { continue }
            let capabilities = inferredCapabilities(
                details.capabilities,
                for: model.name
            )
            guard ModelInfo.areValidCapabilities(capabilities) else { continue }
            let kind = ModelKind.from(capabilities: capabilities, fallbackName: model.name)
            try remember(ModelInfo(
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
                contextWindowTokens: details.contextWindowTokens,
                persistentEmbeddingRevision: model.persistentEmbeddingRevision
            ))
        }

        for model in runningModels {
            if let existingIndex = indexesByID[Data(model.name.utf8)]
                ?? indexesByCanonicalName[Data(canonicalModelName(model.name).utf8)] {
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
                guard details.isTrusted else { continue }
                let capabilities = inferredCapabilities(
                    details.capabilities,
                    for: model.name
                )
                guard ModelInfo.areValidCapabilities(capabilities) else { continue }
                let kind = ModelKind.from(capabilities: capabilities, fallbackName: model.name)
                try remember(ModelInfo(
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

    private func modelDetailsByName(names: [String]) async throws -> [Data: OllamaModelDetails] {
        var result: [Data: OllamaModelDetails] = [:]
        for name in names where !name.isEmpty {
            try Task.checkCancellation()
            do {
                let details = try await fetchModelDetails(name: name)
                if !details.isEmpty {
                    result[Data(name.utf8)] = details
                    result[Data(Self.canonicalModelName(name).utf8)] = details
                }
            } catch OllamaModelDetailsError.malformedResponse {
                result[Data(name.utf8)] = .untrusted
                result[Data(Self.canonicalModelName(name).utf8)] = .untrusted
            } catch is CancellationError {
                throw CancellationError()
            } catch let error as URLError where error.code == .cancelled {
                throw CancellationError()
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
        let data: Data
        do {
            data = try await performBoundedDataRequest(endpoint: endpoint, request: urlRequest)
        } catch OllamaCatalogIngestionError.responseTooLarge {
            throw OllamaModelDetailsError.malformedResponse
        }
        let response: OllamaShowResponse
        do {
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: data)
            response = try decoder.decode(OllamaShowResponse.self, from: data)
            guard ModelInfo.areValidCapabilities(response.capabilities) else {
                throw OllamaCatalogValidationError.invalidCapabilities
            }
        } catch {
            throw OllamaModelDetailsError.malformedResponse
        }
        let capabilities = response.capabilities.map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        }
        guard ModelInfo.areValidCapabilities(capabilities) else {
            throw OllamaModelDetailsError.malformedResponse
        }
        return OllamaModelDetails(
            capabilities: capabilities,
            contextWindowTokens: response.contextWindowTokens
        )
    }

    private static func modelDetails(for name: String, in detailsByName: [Data: OllamaModelDetails]) -> OllamaModelDetails {
        detailsByName[Data(name.utf8)]
            ?? detailsByName[Data(canonicalModelName(name).utf8)]
            ?? OllamaModelDetails()
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
        var uniqueCapabilityIdentities = Set<Data>()
        return result.map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        }.filter { capability in
            !capability.isEmpty
                && uniqueCapabilityIdentities.insert(Data(capability.utf8)).inserted
        }
    }

    private static func uniqueModelNames(_ names: [String]) -> [String] {
        var seen: Set<Data> = []
        return names.filter { name in
            let identity = Data(canonicalModelName(name).utf8)
            guard !seen.contains(identity) else { return false }
            seen.insert(identity)
            return true
        }
    }

    private func decodeTagsResponse(_ data: Data, endpoint: String) throws -> OllamaTagsResponse {
        do {
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: data)
            let response = try decoder.decode(OllamaTagsResponse.self, from: data)
            guard response.models.count <= ModelInfo.maximumCatalogModelCount else {
                throw OllamaCatalogValidationError.tooManyModels
            }
            try Self.validateUniqueModelIdentities(response.models.map(\.name))
            try response.models.forEach(Self.validateInstalledModel)
            return response
        } catch {
            throw OllamaBackendError.responseDecoding(endpoint: endpoint, reason: error.localizedDescription)
        }
    }

    private func decodeRunningModelsResponse(
        _ data: Data,
        endpoint: String
    ) throws -> OllamaRunningModelsResponse {
        do {
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: data)
            let response = try decoder.decode(OllamaRunningModelsResponse.self, from: data)
            guard response.models.count <= ModelInfo.maximumCatalogModelCount else {
                throw OllamaCatalogValidationError.tooManyModels
            }
            try Self.validateUniqueModelIdentities(response.models.map(\.name))
            try response.models.forEach(Self.validateRunningModel)
            return response
        } catch {
            throw OllamaBackendError.responseDecoding(endpoint: endpoint, reason: error.localizedDescription)
        }
    }

    private static func validateUniqueModelIdentities(_ names: [String]) throws {
        var exactNames: Set<Data> = []
        var canonicalNames: Set<Data> = []
        for name in names {
            guard exactNames.insert(Data(name.utf8)).inserted,
                  canonicalNames.insert(Data(canonicalModelName(name).utf8)).inserted else {
                throw OllamaCatalogValidationError.ambiguousModelIdentity
            }
        }
    }

    private static func validateInstalledModel(_ model: OllamaModel) throws {
        let candidate = ModelInfo(
            id: model.name,
            name: model.name,
            provider: .ollama,
            providerModelID: model.name,
            sizeBytes: model.size,
            source: model.source,
            remoteModel: model.remoteModel
        )
        try ModelInfo.validateForCatalogPublication(candidate)
    }

    private static func validateRunningModel(_ model: OllamaRunningModel) throws {
        let candidate = ModelInfo(
            id: model.name,
            name: model.name,
            provider: .ollama,
            providerModelID: model.name,
            sizeBytes: model.size,
            source: model.source
        )
        try ModelInfo.validateForCatalogPublication(candidate)
    }

    private func performCatalogDataRequest(endpoint: String, url: URL) async throws -> Data {
        do {
            return try await performBoundedDataRequest(endpoint: endpoint, request: URLRequest(url: url))
        } catch OllamaCatalogIngestionError.responseTooLarge {
            throw OllamaBackendError.responseDecoding(
                endpoint: endpoint,
                reason: "The provider response exceeds the supported byte limit."
            )
        }
    }

    private func performBoundedDataRequest(endpoint: String, request: URLRequest) async throws -> Data {
        do {
            let (bytes, response) = try await session.bytes(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw OllamaBackendError.transport(endpoint: endpoint, reason: "Missing HTTP response")
            }
            let isSuccess = (200..<300).contains(http.statusCode)
            if http.expectedContentLength > Int64(catalogResponseByteLimit) {
                if isSuccess {
                    throw OllamaCatalogIngestionError.responseTooLarge
                }
                throw OllamaBackendError.httpStatus(endpoint: endpoint, statusCode: http.statusCode, body: nil)
            }

            var data = Data()
            data.reserveCapacity(min(catalogResponseByteLimit, 64 * 1_024))
            for try await byte in bytes {
                data.append(byte)
                if data.count > catalogResponseByteLimit {
                    if isSuccess {
                        throw OllamaCatalogIngestionError.responseTooLarge
                    }
                    throw OllamaBackendError.httpStatus(endpoint: endpoint, statusCode: http.statusCode, body: nil)
                }
            }
            try Self.validate(response, endpoint: endpoint, body: data)
            return data
        } catch let error as OllamaCatalogIngestionError {
            throw error
        } catch let error as OllamaBackendError {
            throw error
        } catch is CancellationError {
            throw CancellationError()
        } catch let error as URLError where error.code == .cancelled {
            throw CancellationError()
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

    private func performDataRequest(endpoint: String, request: URLRequest) async throws -> Data {
        do {
            let (data, response) = try await session.data(for: request)
            try Self.validate(response, endpoint: endpoint, body: data)
            return data
        } catch let error as OllamaBackendError {
            throw error
        } catch is CancellationError {
            throw CancellationError()
        } catch let error as URLError where error.code == .cancelled {
            throw CancellationError()
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

    public func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            registry.prepareForGeneration(id: request.generationID)
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
                            if chunk.promptEvalCount != nil || chunk.evalCount != nil {
                                registry.storeUsageSource(
                                    ChatProviderUsageSource(
                                        provider: .ollama,
                                        providerModelID: request.model,
                                        wireMode: .ollamaChat
                                    ),
                                    id: request.generationID
                                )
                            }
                            continuation.yield(.done(inputTokens: chunk.promptEvalCount, outputTokens: chunk.evalCount))
                            continuation.finish()
                            registry.remove(id: request.generationID)
                            return
                        }
                    }

                    continuation.finish()
                    registry.remove(id: request.generationID, discardingUsageSource: true)
                } catch is CancellationError {
                    continuation.finish(throwing: OllamaBackendError.generationCancelled(generationID: request.generationID))
                    registry.remove(id: request.generationID, discardingUsageSource: true)
                } catch let error as URLError where error.code == .cancelled {
                    continuation.finish(throwing: OllamaBackendError.generationCancelled(generationID: request.generationID))
                    registry.remove(id: request.generationID, discardingUsageSource: true)
                } catch let error as OllamaBackendError {
                    continuation.finish(throwing: error)
                    registry.remove(id: request.generationID, discardingUsageSource: true)
                } catch let error as URLError {
                    continuation.finish(throwing: OllamaBackendError.unreachable(
                        endpoint: endpoint,
                        baseURL: baseURL.absoluteString,
                        reason: error.localizedDescription
                    ))
                    registry.remove(id: request.generationID, discardingUsageSource: true)
                } catch {
                    continuation.finish(throwing: OllamaBackendError.transport(endpoint: endpoint, reason: error.localizedDescription))
                    registry.remove(id: request.generationID, discardingUsageSource: true)
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

    public func takeProviderUsageSource(generationID: String) -> ChatProviderUsageSource? {
        registry.takeUsageSource(id: generationID)
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

    private static func validateEmbeddings(
        _ embeddings: [[Double]],
        expectedCount: Int,
        endpoint: String
    ) throws {
        guard embeddings.count == expectedCount else {
            throw OllamaBackendError.responseDecoding(
                endpoint: endpoint,
                reason: "Expected \(expectedCount) embedding vectors, received \(embeddings.count)."
            )
        }
        guard let dimension = embeddings.first?.count, dimension > 0 else {
            throw OllamaBackendError.responseDecoding(endpoint: endpoint, reason: "Embedding vectors must not be empty.")
        }
        guard embeddings.allSatisfy({ $0.count == dimension }) else {
            throw OllamaBackendError.responseDecoding(endpoint: endpoint, reason: "Embedding vector dimensions are inconsistent.")
        }
        guard embeddings.allSatisfy({ $0.allSatisfy(\.isFinite) }) else {
            throw OllamaBackendError.responseDecoding(endpoint: endpoint, reason: "Embedding vectors must contain only finite values.")
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
    private static let maximumCompletedUsageSources = 128

    private let lock = NSLock()
    private var tasks: [String: Task<Void, Never>] = [:]
    private var usageSources: [String: ChatProviderUsageSource] = [:]
    private var usageSourceOrder: [String] = []

    func prepareForGeneration(id: String) {
        lock.withLock {
            removeUsageSourceLocked(id: id)
        }
    }

    func register(id: String, task: Task<Void, Never>) {
        lock.withLock {
            tasks[id] = task
        }
    }

    func cancel(id: String) -> GenerationCancellationResult {
        lock.withLock {
            removeUsageSourceLocked(id: id)
            guard let task = tasks.removeValue(forKey: id) else {
                return .notFound(generationID: id)
            }
            task.cancel()
            return .cancelled(generationID: id)
        }
    }

    func remove(id: String, discardingUsageSource: Bool = false) {
        lock.withLock {
            tasks[id] = nil
            if discardingUsageSource {
                removeUsageSourceLocked(id: id)
            }
        }
    }

    func storeUsageSource(_ source: ChatProviderUsageSource, id: String) {
        lock.withLock {
            removeUsageSourceLocked(id: id)
            usageSources[id] = source
            usageSourceOrder.append(id)
            while usageSourceOrder.count > Self.maximumCompletedUsageSources {
                let oldestID = usageSourceOrder.removeFirst()
                usageSources[oldestID] = nil
            }
        }
    }

    func takeUsageSource(id: String) -> ChatProviderUsageSource? {
        lock.withLock {
            let source = usageSources[id]
            removeUsageSourceLocked(id: id)
            return source
        }
    }

    private func removeUsageSourceLocked(id: String) {
        usageSources[id] = nil
        usageSourceOrder.removeAll { $0 == id }
    }
}

private struct OllamaTagsResponse: Decodable {
    var models: [OllamaModel]
}

private struct OllamaModel: Decodable {
    var name: String
    var digest: String?
    var size: Int64?
    var modifiedAt: Date?
    var remoteModel: String?
    var remoteHost: String?
    var source: ModelSource {
        Self.modelSource(name: name, remoteModel: remoteModel, remoteHost: remoteHost)
    }
    var persistentEmbeddingRevision: String? {
        guard let digest,
              digest.count == 64,
              digest.unicodeScalars.allSatisfy({
                  CharacterSet(charactersIn: "0123456789abcdefABCDEF").contains($0)
              }) else {
            return nil
        }
        return "ollama-sha256:\(digest.lowercased())"
    }

    enum CodingKeys: String, CodingKey {
        case name
        case model
        case digest
        case size
        case modifiedAt = "modified_at"
        case remoteModel = "remote_model"
        case remoteHost = "remote_host"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        name = try Self.decodeModelIdentity(from: container)
        digest = try container.decodeIfPresent(String.self, forKey: .digest)
        size = try container.decodeIfPresent(Int64.self, forKey: .size)
        remoteModel = try container.decodeIfPresent(String.self, forKey: .remoteModel)
        remoteHost = try container.decodeIfPresent(String.self, forKey: .remoteHost)
        let modifiedAtString = try container.decodeIfPresent(String.self, forKey: .modifiedAt)
        modifiedAt = modifiedAtString.flatMap(Self.parseDate)
    }

    fileprivate static func decodeModelIdentity<Key: CodingKey>(
        from container: KeyedDecodingContainer<Key>,
        nameKey: Key,
        modelKey: Key
    ) throws -> String {
        let name = try container.decodeIfPresent(String.self, forKey: nameKey)
        let model = try container.decodeIfPresent(String.self, forKey: modelKey)
        if let name, let model, Data(name.utf8) != Data(model.utf8) {
            throw OllamaCatalogValidationError.ambiguousModelIdentity
        }
        guard let identity = name ?? model else {
            throw DecodingError.keyNotFound(
                nameKey,
                DecodingError.Context(
                    codingPath: container.codingPath,
                    debugDescription: "Expected a model identity."
                )
            )
        }
        return identity
    }

    private static func decodeModelIdentity(
        from container: KeyedDecodingContainer<CodingKeys>
    ) throws -> String {
        try decodeModelIdentity(from: container, nameKey: .name, modelKey: .model)
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
        name = try OllamaModel.decodeModelIdentity(from: container, nameKey: .name, modelKey: .model)
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

private struct OllamaEmbedRequest: Encodable {
    var model: String
    var input: [String]
    var truncate = false
}

private struct OllamaEmbedResponse: Decodable {
    var model: String?
    var embeddings: [[Double]]
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

private struct OllamaUnloadResponse: Decodable {
    var done: Bool?
    var doneReason: String?

    enum CodingKeys: String, CodingKey {
        case done
        case doneReason = "done_reason"
    }
}

private struct OllamaShowRequest: Encodable {
    var model: String
}

private struct OllamaModelDetails {
    var capabilities: [String] = []
    var contextWindowTokens: Int?
    var isTrusted = true

    static let untrusted = OllamaModelDetails(isTrusted: false)

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

        do {
            var candidates = try Self.contextWindowValues(
                in: container,
                keys: [.contextWindowTokens, .contextLength, .contextWindow, .numCtx]
            )
            if container.contains(.modelInfo) {
                let modelInfo = try container.nestedContainer(
                    keyedBy: ModelInfoCodingKey.self,
                    forKey: .modelInfo
                )
                candidates += try Self.contextWindowValues(
                    in: modelInfo,
                    keys: ModelInfoCodingKey.contextWindowKeys
                )
            }
            if container.contains(.parameters) {
                let parameters = try container.decode(String.self, forKey: .parameters)
                candidates += try Self.contextWindowValues(fromParameters: parameters)
            }
            guard Set(candidates).count <= 1 else {
                throw OllamaCatalogValidationError.conflictingContextWindowAliases
            }
            contextWindowTokens = candidates.first
        } catch {
            contextWindowTokens = nil
        }
    }

    private static func contextWindowValues<Key: CodingKey>(
        in container: KeyedDecodingContainer<Key>,
        keys: [Key]
    ) throws -> [Int] {
        try keys.compactMap { key in
            guard container.contains(key) else { return nil }
            let value = try container.decode(Decimal.self, forKey: key)
            guard let validated = ModelInfo.validatedContextWindowTokens(decimal: value) else {
                throw OllamaCatalogValidationError.invalidContextWindow
            }
            return validated
        }
    }

    private static func contextWindowValues(fromParameters parameters: String) throws -> [Int] {
        var values: [Int] = []
        for line in parameters.split(whereSeparator: \.isNewline) {
            let parts = line.split { character in
                character == " " || character == "\t" || character == "="
            }
            guard parts.first?.lowercased() == "num_ctx" else {
                continue
            }
            guard parts.count == 2,
                  parts[1].allSatisfy({ $0.isASCII && $0.isNumber }),
                  let value = Int(parts[1]),
                  let validated = ModelInfo.validatedContextWindowTokens(value) else {
                throw OllamaCatalogValidationError.invalidContextWindow
            }
            values.append(validated)
        }
        return values
    }
}

private struct ModelInfoCodingKey: CodingKey, Hashable {
    static let contextWindowKeys = [
        Self(stringValue: "llama.context_length")!,
        Self(stringValue: "general.context_length")!,
        Self(stringValue: "context_length")!,
        Self(stringValue: "num_ctx")!,
    ]

    var stringValue: String
    var intValue: Int?

    init?(stringValue: String) {
        self.stringValue = stringValue
    }

    init?(intValue: Int) {
        self.stringValue = String(intValue)
        self.intValue = intValue
    }
}

private enum OllamaCatalogValidationError: Error, LocalizedError {
    case ambiguousModelIdentity
    case conflictingContextWindowAliases
    case invalidCapabilities
    case invalidContextWindow
    case tooManyModels

    var errorDescription: String? {
        switch self {
        case .ambiguousModelIdentity:
            return "The provider returned an ambiguous model identity."
        case .conflictingContextWindowAliases:
            return "The provider returned conflicting context-window aliases."
        case .invalidCapabilities:
            return "The provider returned invalid model capabilities."
        case .invalidContextWindow:
            return "The provider returned an invalid context window."
        case .tooManyModels:
            return "The provider returned too many model rows."
        }
    }
}

private enum OllamaCatalogIngestionError: Error {
    case responseTooLarge
}

private enum OllamaModelDetailsError: Error {
    case malformedResponse
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
