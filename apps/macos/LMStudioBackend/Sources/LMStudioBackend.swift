import Foundation
import OllamaBackend

public final class LMStudioBackend: LlmBackend, @unchecked Sendable {
    public static let defaultBaseURL = URL(string: "http://127.0.0.1:1234")!
    public let provider = ModelProvider.lmStudio

    private static let defaultUnloadPollAttempts = 20
    private static let defaultUnloadPollIntervalNanoseconds: UInt64 = 100_000_000
    private static let defaultDataResponseByteLimit = 32 * 1_024 * 1_024
    private static let defaultDataResponseTimeout: TimeInterval = 60

    private let baseURL: URL
    private let session: URLSession
    private let unloadPollAttempts: Int
    private let unloadPollIntervalNanoseconds: UInt64
    private let unloadSleeper: @Sendable (UInt64) async throws -> Void
    private let catalogResponseByteLimit: Int
    private let dataResponseByteLimit: Int
    private let dataResponseTimeout: TimeInterval
    private let streamLimits: LMStudioStreamLimits
    private let registry = LMStudioGenerationRegistry()
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    public init(baseURL: URL = LMStudioBackend.defaultBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        self.unloadPollAttempts = Self.defaultUnloadPollAttempts
        self.unloadPollIntervalNanoseconds = Self.defaultUnloadPollIntervalNanoseconds
        self.unloadSleeper = { try await Task.sleep(nanoseconds: $0) }
        self.catalogResponseByteLimit = ModelInfo.maximumCatalogResponseBytes
        self.dataResponseByteLimit = Self.defaultDataResponseByteLimit
        self.dataResponseTimeout = Self.defaultDataResponseTimeout
        self.streamLimits = LMStudioStreamLimits()
    }

    init(
        baseURL: URL,
        session: URLSession,
        unloadPollAttempts: Int,
        catalogResponseByteLimit: Int = ModelInfo.maximumCatalogResponseBytes,
        dataResponseByteLimit: Int = defaultDataResponseByteLimit,
        dataResponseTimeout: TimeInterval = defaultDataResponseTimeout,
        streamLimits: LMStudioStreamLimits = LMStudioStreamLimits(),
        unloadPollIntervalNanoseconds: UInt64 = 0,
        unloadSleeper: @escaping @Sendable (UInt64) async throws -> Void = { _ in }
    ) {
        self.baseURL = baseURL
        self.session = session
        self.unloadPollAttempts = max(1, unloadPollAttempts)
        self.catalogResponseByteLimit = max(0, catalogResponseByteLimit)
        self.dataResponseByteLimit = max(0, dataResponseByteLimit)
        self.dataResponseTimeout = Self.normalizedDataResponseTimeout(dataResponseTimeout)
        self.streamLimits = streamLimits
        self.unloadPollIntervalNanoseconds = unloadPollIntervalNanoseconds
        self.unloadSleeper = unloadSleeper
    }

    public func healthCheck() async -> BackendStatus {
        do {
            _ = try await listModels()
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
            data = try await performCatalogDataRequest(endpoint: "GET /api/v1/models", url: baseURL.appending(path: "api/v1/models"))
        } catch let error as LMStudioBackendError where error.shouldFallbackModelCatalogToOpenAICompatible {
            return try await listOpenAICompatibleModels()
        }
        do {
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: data)
            let response = try decoder.decode(LMStudioNativeModelsResponse.self, from: data)
            guard response.models.count <= ModelInfo.maximumCatalogModelCount else {
                throw LMStudioCatalogValidationError.tooManyModels
            }
            try Self.validateUniqueModelIdentities(response.models.map(\.key))
            return try response.models.map { model in
                try Self.validateLoadedInstances(model.loadedInstances)
                guard model.hasValidCapabilitySource else {
                    throw ModelCatalogPublicationValidationError.invalidCapabilities
                }
                let kind = ModelKind.from(
                    capabilities: model.capabilities,
                    fallbackName: model.displayName ?? model.key
                )
                let modelInfo = ModelInfo(
                    id: model.key,
                    name: model.displayName ?? model.key,
                    provider: .lmStudio,
                    kind: kind,
                    capabilities: model.capabilities.isEmpty ? nil : model.capabilities,
                    providerModelID: model.key,
                    sizeBytes: model.sizeBytes,
                    installed: true,
                    running: !model.loadedInstances.isEmpty,
                    source: .local,
                    contextWindowTokens: model.contextWindowTokens
                )
                try ModelInfo.validateForCatalogPublication(modelInfo)
                return modelInfo
            }
        } catch let error as LMStudioBackendError {
            throw error
        } catch {
            throw LMStudioBackendError.badResponse(endpoint: "GET /api/v1/models", reason: error.localizedDescription)
        }
    }

    public func pullModel(name: String) async throws -> ModelPullResult {
        throw LMStudioBackendError.badResponse(
            endpoint: "POST /api/v1/models/download",
            reason: "LM Studio downloads are managed from LM Studio or lms; AetherLink does not expose client-initiated LM Studio downloads."
        )
    }

    public func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        let initialLookup = try await nativeModelLookup(for: providerModelID)
        let instanceIDs: [String]
        switch initialLookup {
        case .unsupported:
            return .unsupported(provider: provider, modelID: providerModelID)
        case .model(nil):
            return .alreadyAbsent(provider: provider, modelID: providerModelID)
        case .model(let model?):
            instanceIDs = model.loadedInstances.map(\.id)
        }
        guard !instanceIDs.isEmpty else {
            return .alreadyAbsent(provider: provider, modelID: providerModelID)
        }
        guard instanceIDs.allSatisfy({ !$0.isEmpty }) else {
            throw LMStudioBackendError.unloadNotConfirmed(reason: "The provider reported an invalid loaded instance identifier.")
        }

        for instanceID in instanceIDs {
            try Task.checkCancellation()
            try await unloadInstance(instanceID)
        }

        for attempt in 0..<unloadPollAttempts {
            try Task.checkCancellation()
            switch try await nativeModelLookup(for: providerModelID) {
            case .unsupported:
                throw LMStudioBackendError.unloadNotConfirmed(reason: "Native model state became unavailable before verification completed.")
            case .model(nil):
                return .unloaded(provider: provider, modelID: providerModelID)
            case .model(let model?) where model.loadedInstances.isEmpty:
                return .unloaded(provider: provider, modelID: providerModelID)
            case .model:
                break
            }
            if attempt + 1 < unloadPollAttempts {
                try await unloadSleeper(unloadPollIntervalNanoseconds)
            }
        }

        throw LMStudioBackendError.unloadNotConfirmed(reason: "The model remained resident after bounded verification.")
    }

    public func embed(request: EmbeddingRequest) async throws -> EmbeddingResult {
        let endpoint = "POST /v1/embeddings"
        var urlRequest = URLRequest(url: baseURL.appending(path: "v1/embeddings"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try Self.encode(
            OpenAIEmbeddingsRequest(model: request.model, input: request.texts),
            encoder: encoder,
            endpoint: endpoint
        )

        let data = try await performDataRequest(endpoint: endpoint, request: urlRequest)
        let response: OpenAIEmbeddingsResponse
        do {
            response = try decoder.decode(OpenAIEmbeddingsResponse.self, from: data)
        } catch {
            throw LMStudioBackendError.badResponse(endpoint: endpoint, reason: error.localizedDescription)
        }
        let embeddings = try Self.orderedEmbeddings(
            response.data,
            expectedCount: request.texts.count,
            endpoint: endpoint
        )
        return EmbeddingResult(model: response.model ?? request.model, embeddings: embeddings)
    }

    public func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream(bufferingPolicy: .bufferingOldest(streamLimits.bufferedEventLimit)) { continuation in
            registry.prepareForGeneration(id: request.generationID)
            let task = Task { [baseURL, session, encoder, streamLimits] in
                do {
                    let availableModels = try await self.listModels()
                    guard !availableModels.isEmpty else {
                        throw LMStudioBackendError.noModels
                    }

                    let completion: LMStudioStreamCompletion
                    do {
                        completion = try await Self.streamNativeChat(
                            request: request,
                            baseURL: baseURL,
                            session: session,
                            encoder: encoder,
                            limits: streamLimits
                        ) { event in
                            try Self.yield(event, to: continuation, endpoint: "POST /api/v1/chat")
                        }
                    } catch let error as LMStudioBackendError where error.shouldFallbackNativeEndpointToOpenAICompatible {
                        try Task.checkCancellation()
                        completion = try await Self.streamOpenAICompatibleChat(
                            request: request,
                            baseURL: baseURL,
                            session: session,
                            encoder: encoder,
                            limits: streamLimits
                        ) { event in
                            try Self.yield(event, to: continuation, endpoint: "POST /v1/chat/completions")
                        }
                    }
                    if completion.hasUsage {
                        registry.storeUsageSource(
                            ChatProviderUsageSource(
                                provider: .lmStudio,
                                providerModelID: request.model,
                                wireMode: completion.wireMode
                            ),
                            id: request.generationID
                        )
                    }
                    try Self.yield(
                        .done(inputTokens: completion.inputTokens, outputTokens: completion.outputTokens),
                        to: continuation,
                        endpoint: completion.endpoint
                    )
                    continuation.finish()
                    registry.remove(id: request.generationID)
                } catch is CancellationError {
                    continuation.finish(throwing: LMStudioBackendError.generationCancelled(generationID: request.generationID))
                    registry.remove(id: request.generationID, discardingUsageSource: true)
                } catch let error as URLError where error.code == .cancelled {
                    continuation.finish(throwing: LMStudioBackendError.generationCancelled(generationID: request.generationID))
                    registry.remove(id: request.generationID, discardingUsageSource: true)
                } catch let error as LMStudioBackendError {
                    continuation.finish(throwing: error)
                    registry.remove(id: request.generationID, discardingUsageSource: true)
                } catch let error as URLError {
                    continuation.finish(throwing: LMStudioBackendError.unavailable(
                        endpoint: "POST /api/v1/chat",
                        reason: error.localizedDescription
                    ))
                    registry.remove(id: request.generationID, discardingUsageSource: true)
                } catch {
                    continuation.finish(throwing: LMStudioBackendError.transport(
                        endpoint: "POST /api/v1/chat",
                        reason: error.localizedDescription
                    ))
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

    private func listOpenAICompatibleModels() async throws -> [ModelInfo] {
        let data = try await performCatalogDataRequest(endpoint: "GET /v1/models", url: baseURL.appending(path: "v1/models"))
        do {
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: data)
            let response = try decoder.decode(OpenAIModelsResponse.self, from: data)
            guard response.data.count <= ModelInfo.maximumCatalogModelCount else {
                throw LMStudioCatalogValidationError.tooManyModels
            }
            try Self.validateUniqueModelIdentities(response.data.map(\.id))
            return try response.data.map { model in
                let kind = ModelKind.from(capabilities: [], fallbackName: model.id)
                let modelInfo = ModelInfo(
                    id: model.id,
                    name: model.id,
                    provider: .lmStudio,
                    kind: kind,
                    capabilities: kind.defaultCapabilities,
                    providerModelID: model.id,
                    installed: true,
                    running: false,
                    source: .local,
                    contextWindowTokens: model.contextWindowTokens
                )
                try ModelInfo.validateForCatalogPublication(modelInfo)
                return modelInfo
            }
        } catch {
            throw LMStudioBackendError.badResponse(endpoint: "GET /v1/models", reason: error.localizedDescription)
        }
    }

    private static func validateUniqueModelIdentities(_ identities: [String]) throws {
        var exactIdentities = Set<Data>()
        var canonicalIdentities = Set<String>()
        for identity in identities {
            guard exactIdentities.insert(Data(identity.utf8)).inserted else {
                throw DecodingError.dataCorrupted(.init(
                    codingPath: [],
                    debugDescription: "The model catalog contains a duplicate model identity."
                ))
            }
            let canonicalIdentity = identity.precomposedStringWithCanonicalMapping
            guard canonicalIdentities.insert(canonicalIdentity).inserted else {
                throw DecodingError.dataCorrupted(.init(
                    codingPath: [],
                    debugDescription: "The model catalog contains canonically equivalent model identities."
                ))
            }
        }
    }

    private func nativeModelLookup(for modelID: String) async throws -> LMStudioNativeModelLookup {
        do {
            let data = try await performCatalogDataRequest(endpoint: "GET /api/v1/models", url: baseURL.appending(path: "api/v1/models"))
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: data)
            let response = try decoder.decode(LMStudioUnloadModelsResponse.self, from: data)
            guard response.models.count <= ModelInfo.maximumCatalogModelCount else {
                throw LMStudioCatalogValidationError.tooManyModels
            }
            try Self.validateUniqueModelIdentities(response.models.map(\.key))
            try response.models.forEach { model in
                let candidate = ModelInfo(
                    id: model.key,
                    name: model.key,
                    provider: .lmStudio,
                    providerModelID: model.key
                )
                try ModelInfo.validateForCatalogPublication(candidate)
                try Self.validateLoadedInstances(model.loadedInstances)
            }
            let requestedModelIdentity = Data(modelID.utf8)
            let matches = response.models.filter {
                Data($0.key.utf8) == requestedModelIdentity
            }
            guard matches.count <= 1 else {
                throw LMStudioBackendError.unloadNotConfirmed(
                    reason: "Native model state contained an ambiguous model key."
                )
            }
            return .model(matches.first)
        } catch let error as LMStudioBackendError where error.shouldFallbackNativeEndpointToOpenAICompatible {
            return .unsupported
        } catch is DecodingError {
            throw LMStudioBackendError.unloadNotConfirmed(
                reason: "Native model residency state was malformed."
            )
        } catch is StrictJSONValidationError {
            throw LMStudioBackendError.unloadNotConfirmed(
                reason: "Native model residency state was malformed."
            )
        } catch is LMStudioCatalogValidationError {
            throw LMStudioBackendError.unloadNotConfirmed(
                reason: "Native model residency state was malformed."
            )
        } catch let error as ModelCatalogPublicationValidationError {
            throw LMStudioBackendError.unloadNotConfirmed(
                reason: error.localizedDescription
            )
        } catch let error as LMStudioBackendError {
            if case .badResponse = error {
                throw LMStudioBackendError.unloadNotConfirmed(
                    reason: "Native model residency state was malformed."
                )
            }
            throw error
        }
    }

    private func unloadInstance(_ instanceID: String) async throws {
        let endpoint = "POST /api/v1/models/unload"
        var urlRequest = URLRequest(url: baseURL.appending(path: "api/v1/models/unload"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try Self.encode(
            LMStudioUnloadRequest(instanceID: instanceID),
            encoder: encoder,
            endpoint: endpoint
        )
        let data = try await performDataRequest(endpoint: endpoint, request: urlRequest)
        let acknowledgement: LMStudioUnloadResponse
        do {
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: data)
            acknowledgement = try decoder.decode(LMStudioUnloadResponse.self, from: data)
        } catch {
            throw LMStudioBackendError.unloadNotConfirmed(reason: "The provider acknowledgement was malformed.")
        }
        guard Data(acknowledgement.instanceID.utf8) == Data(instanceID.utf8) else {
            throw LMStudioBackendError.unloadNotConfirmed(reason: "The provider acknowledgement did not match the requested instance.")
        }
    }

    private static func validateLoadedInstances(_ instances: [LMStudioLoadedInstance]) throws {
        guard instances.count <= ModelInfo.maximumCatalogModelCount else {
            throw LMStudioCatalogValidationError.tooManyLoadedInstances
        }
        var exactIdentifiers = Set<Data>()
        var canonicalIdentifiers = Set<String>()
        for instance in instances {
            guard ModelInfo.isValidRequiredModelIdentity(instance.id),
                  exactIdentifiers.insert(Data(instance.id.utf8)).inserted,
                  canonicalIdentifiers.insert(
                      instance.id.precomposedStringWithCanonicalMapping
                  ).inserted else {
                throw LMStudioCatalogValidationError.invalidLoadedInstanceIdentity
            }
        }
    }

    private func performCatalogDataRequest(endpoint: String, url: URL) async throws -> Data {
        do {
            return try await performBoundedDataRequest(
                endpoint: endpoint,
                request: URLRequest(url: url),
                byteLimit: catalogResponseByteLimit
            )
        } catch LMStudioCatalogIngestionError.responseTooLarge {
            throw LMStudioBackendError.badResponse(
                endpoint: endpoint,
                reason: "The provider response exceeds the supported byte limit."
            )
        }
    }

    private func performBoundedDataRequest(
        endpoint: String,
        request: URLRequest,
        byteLimit: Int
    ) async throws -> Data {
        do {
            let timeoutNanoseconds = UInt64(dataResponseTimeout * 1_000_000_000)
            return try await withThrowingTaskGroup(of: Data.self) { group in
                group.addTask { [self] in
                    try await collectBoundedDataResponse(
                        endpoint: endpoint,
                        request: request,
                        byteLimit: byteLimit
                    )
                }
                group.addTask {
                    try await Task.sleep(nanoseconds: timeoutNanoseconds)
                    throw URLError(.timedOut)
                }
                defer { group.cancelAll() }
                guard let result = try await group.next() else {
                    throw CancellationError()
                }
                return result
            }
        } catch let error as LMStudioCatalogIngestionError {
            throw error
        } catch let error as LMStudioBackendError {
            throw error
        } catch is CancellationError {
            throw CancellationError()
        } catch let error as URLError where error.code == .cancelled {
            throw CancellationError()
        } catch let error as URLError {
            throw LMStudioBackendError.unavailable(endpoint: endpoint, reason: error.localizedDescription)
        } catch {
            throw LMStudioBackendError.transport(endpoint: endpoint, reason: error.localizedDescription)
        }
    }

    private func collectBoundedDataResponse(
        endpoint: String,
        request: URLRequest,
        byteLimit: Int
    ) async throws -> Data {
        var boundedRequest = request
        boundedRequest.timeoutInterval = dataResponseTimeout
        let (bytes, response) = try await session.bytes(for: boundedRequest)
        do {
            guard let http = response as? HTTPURLResponse else {
                throw LMStudioBackendError.transport(endpoint: endpoint, reason: "Missing HTTP response")
            }
            let isSuccess = (200..<300).contains(http.statusCode)
            if http.expectedContentLength > Int64(byteLimit) {
                if isSuccess {
                    throw LMStudioCatalogIngestionError.responseTooLarge
                }
                throw LMStudioBackendError.httpStatus(endpoint: endpoint, statusCode: http.statusCode, body: nil)
            }

            var data = Data()
            data.reserveCapacity(min(byteLimit, 64 * 1_024))
            for try await byte in bytes {
                try Task.checkCancellation()
                guard data.count < byteLimit else {
                    if isSuccess {
                        throw LMStudioCatalogIngestionError.responseTooLarge
                    }
                    throw LMStudioBackendError.httpStatus(endpoint: endpoint, statusCode: http.statusCode, body: nil)
                }
                data.append(byte)
            }
            try Self.validate(response, endpoint: endpoint, body: data)
            return data
        } catch {
            bytes.task.cancel()
            throw error
        }
    }

    private static func normalizedDataResponseTimeout(_ timeout: TimeInterval) -> TimeInterval {
        let maximum: TimeInterval = 24 * 60 * 60
        guard timeout.isFinite, timeout > 0 else { return defaultDataResponseTimeout }
        return min(timeout, maximum)
    }

    private func performDataRequest(endpoint: String, request: URLRequest) async throws -> Data {
        do {
            return try await performBoundedDataRequest(
                endpoint: endpoint,
                request: request,
                byteLimit: dataResponseByteLimit
            )
        } catch LMStudioCatalogIngestionError.responseTooLarge {
            throw LMStudioBackendError.badResponse(
                endpoint: endpoint,
                reason: "The provider response exceeds the supported byte limit."
            )
        } catch let error as LMStudioBackendError {
            throw error
        } catch is CancellationError {
            throw CancellationError()
        } catch let error as URLError where error.code == .cancelled {
            throw CancellationError()
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
        limits: LMStudioStreamLimits,
        emit: (ChatStreamEvent) throws -> Void
    ) async throws -> LMStudioStreamCompletion {
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
        do {
            try validate(response, endpoint: endpoint, body: nil)
            try validateContentLength(response, limit: limits.responseByteLimit)

            var lines = LMStudioBoundedLineReader(
                bytes: bytes,
                responseByteLimit: limits.responseByteLimit,
                lineByteLimit: limits.lineByteLimit
            )
            var parser = ServerSentEventParser(frameByteLimit: limits.frameByteLimit)
            var budget = LMStudioStreamBudget(limit: limits.aggregateAccountingByteLimit)
            while let line = try await lines.next() {
                try Task.checkCancellation()
                for event in try parser.append(line) {
                    if let completion = try handleNativeEvent(
                        event,
                        budget: &budget,
                        emit: emit,
                        endpoint: endpoint
                    ) {
                        bytes.task.cancel()
                        return completion
                    }
                }
            }

            for event in parser.finish() {
                if let completion = try handleNativeEvent(
                    event,
                    budget: &budget,
                    emit: emit,
                    endpoint: endpoint
                ) {
                    bytes.task.cancel()
                    return completion
                }
            }
            throw LMStudioStreamIngestionError.missingTerminal
        } catch is CancellationError {
            bytes.task.cancel()
            throw CancellationError()
        } catch let error as URLError where error.code == .cancelled {
            bytes.task.cancel()
            throw CancellationError()
        } catch is LMStudioStreamIngestionError {
            bytes.task.cancel()
            throw badStreamResponse(endpoint: endpoint)
        } catch {
            bytes.task.cancel()
            throw error
        }
    }

    private static func streamOpenAICompatibleChat(
        request: ChatRequest,
        baseURL: URL,
        session: URLSession,
        encoder: JSONEncoder,
        limits: LMStudioStreamLimits,
        emit: (ChatStreamEvent) throws -> Void
    ) async throws -> LMStudioStreamCompletion {
        let endpoint = "POST /v1/chat/completions"
        var urlRequest = URLRequest(url: baseURL.appending(path: "v1/chat/completions"))
        urlRequest.httpMethod = "POST"
        urlRequest.addValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try encode(
            OpenAIChatCompletionsRequest(
                model: request.model,
                messages: request.messages,
                stream: true,
                streamOptions: OpenAIStreamOptions(includeUsage: true)
            ),
            encoder: encoder,
            endpoint: endpoint
        )

        let (bytes, response) = try await session.bytes(for: urlRequest)
        do {
            try validate(response, endpoint: endpoint, body: nil)
            try validateContentLength(response, limit: limits.responseByteLimit)

            var lines = LMStudioBoundedLineReader(
                bytes: bytes,
                responseByteLimit: limits.responseByteLimit,
                lineByteLimit: limits.lineByteLimit
            )
            var budget = LMStudioStreamBudget(limit: limits.aggregateAccountingByteLimit)
            var inputTokens: Int?
            var outputTokens: Int?
            var hasUsage = false
            while let line = try await lines.next() {
                try Task.checkCancellation()
                guard let streamLine = try decodeOpenAIStreamLine(line, endpoint: endpoint) else { continue }
                if case .done = streamLine {
                    bytes.task.cancel()
                    return LMStudioStreamCompletion(
                        endpoint: endpoint,
                        wireMode: .lmStudioOpenAICompatible,
                        inputTokens: inputTokens,
                        outputTokens: outputTokens,
                        hasUsage: hasUsage
                    )
                }
                guard case .chunk(let chunk) = streamLine else { continue }
                let reasoning = chunk.choices.first?.delta.reasoningText ?? ""
                let content = chunk.choices.first?.delta.content ?? ""
                try budget.record(
                    reasoning: reasoning,
                    answer: content,
                    includesUsage: chunk.usage != nil
                )
                if !reasoning.isEmpty {
                    try emit(.reasoningDelta(reasoning))
                }
                if !content.isEmpty {
                    try emit(.delta(content))
                }
                if let usage = chunk.usage {
                    inputTokens = usage.promptTokens
                    outputTokens = usage.completionTokens
                    hasUsage = true
                }
            }
            throw LMStudioStreamIngestionError.missingTerminal
        } catch is CancellationError {
            bytes.task.cancel()
            throw CancellationError()
        } catch let error as URLError where error.code == .cancelled {
            bytes.task.cancel()
            throw CancellationError()
        } catch is LMStudioStreamIngestionError {
            bytes.task.cancel()
            throw badStreamResponse(endpoint: endpoint)
        } catch {
            bytes.task.cancel()
            throw error
        }
    }

    private static func handleNativeEvent(
        _ event: ServerSentEvent,
        budget: inout LMStudioStreamBudget,
        emit: (ChatStreamEvent) throws -> Void,
        endpoint: String
    ) throws -> LMStudioStreamCompletion? {
        guard let data = event.data.data(using: .utf8) else {
            throw LMStudioStreamIngestionError.invalidUTF8
        }
        switch event.name {
        case "message.delta":
            let delta = try decode(LMStudioMessageDelta.self, from: data, endpoint: endpoint, line: event.data)
            try budget.record(
                reasoning: delta.reasoningText,
                answer: delta.answerText,
                includesUsage: false
            )
            if !delta.reasoningText.isEmpty {
                try emit(.reasoningDelta(delta.reasoningText))
            }
            if !delta.answerText.isEmpty {
                try emit(.delta(delta.answerText))
            }
        case "error":
            let payload = try decode(LMStudioStreamError.self, from: data, endpoint: endpoint, line: event.data)
            throw LMStudioBackendError.badResponse(endpoint: endpoint, reason: payload.error.message)
        case "chat.end":
            let end = try decode(LMStudioChatEnd.self, from: data, endpoint: endpoint, line: event.data)
            let inputTokens = end.result.stats?.inputTokens
            let outputTokens = end.result.stats?.totalOutputTokens
            try budget.record(reasoning: "", answer: "", includesUsage: end.result.stats != nil)
            return LMStudioStreamCompletion(
                endpoint: endpoint,
                wireMode: .lmStudioNative,
                inputTokens: inputTokens,
                outputTokens: outputTokens,
                hasUsage: end.result.stats != nil
            )
        default:
            break
        }
        return nil
    }

    private static func validateContentLength(_ response: URLResponse, limit: Int) throws {
        guard response.expectedContentLength <= Int64(limit) else {
            throw LMStudioStreamIngestionError.responseTooLarge
        }
    }

    private static func yield(
        _ event: ChatStreamEvent,
        to continuation: AsyncThrowingStream<ChatStreamEvent, Error>.Continuation,
        endpoint: String
    ) throws {
        switch continuation.yield(event) {
        case .enqueued:
            return
        case .dropped:
            throw badStreamResponse(endpoint: endpoint)
        case .terminated:
            throw CancellationError()
        @unknown default:
            throw badStreamResponse(endpoint: endpoint)
        }
    }

    private static func badStreamResponse(endpoint: String) -> LMStudioBackendError {
        LMStudioBackendError.badResponse(
            endpoint: endpoint,
            reason: "The provider stream violated a bounded response contract."
        )
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

    private static func orderedEmbeddings(
        _ items: [OpenAIEmbeddingData],
        expectedCount: Int,
        endpoint: String
    ) throws -> [[Double]] {
        guard items.count == expectedCount else {
            throw LMStudioBackendError.badResponse(
                endpoint: endpoint,
                reason: "Expected \(expectedCount) embedding vectors, received \(items.count)."
            )
        }

        var ordered = Array<[Double]?>(repeating: nil, count: expectedCount)
        var dimension: Int?
        for item in items {
            guard ordered.indices.contains(item.index) else {
                throw LMStudioBackendError.badResponse(endpoint: endpoint, reason: "Embedding index \(item.index) is out of range.")
            }
            guard ordered[item.index] == nil else {
                throw LMStudioBackendError.badResponse(endpoint: endpoint, reason: "Embedding index \(item.index) is duplicated.")
            }
            guard !item.embedding.isEmpty else {
                throw LMStudioBackendError.badResponse(endpoint: endpoint, reason: "Embedding vectors must not be empty.")
            }
            guard item.embedding.allSatisfy(\.isFinite) else {
                throw LMStudioBackendError.badResponse(endpoint: endpoint, reason: "Embedding vectors must contain only finite values.")
            }
            if let dimension, item.embedding.count != dimension {
                throw LMStudioBackendError.badResponse(endpoint: endpoint, reason: "Embedding vector dimensions are inconsistent.")
            }
            dimension = item.embedding.count
            ordered[item.index] = item.embedding
        }

        guard ordered.allSatisfy({ $0 != nil }) else {
            throw LMStudioBackendError.badResponse(endpoint: endpoint, reason: "Embedding response is missing one or more indexes.")
        }
        return ordered.compactMap { $0 }
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
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: data)
            return try JSONDecoder().decode(type, from: data)
        } catch {
            throw LMStudioBackendError.streamDecoding(line: line, reason: error.localizedDescription)
        }
    }

    private static func decodeOpenAIStreamLine(_ line: String, endpoint: String) throws -> OpenAIStreamLine? {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        let jsonLine: String
        if trimmed.hasPrefix("data:") {
            jsonLine = String(trimmed.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces)
        } else {
            jsonLine = trimmed
        }

        guard !jsonLine.isEmpty else { return nil }
        if jsonLine == "[DONE]" { return .done }
        guard let data = jsonLine.data(using: .utf8) else {
            throw LMStudioBackendError.streamDecoding(line: line, reason: "Line is not valid UTF-8")
        }

        do {
            try StrictJSONValidator.validateNoDuplicateObjectKeys(in: data)
            return .chunk(try JSONDecoder().decode(OpenAIChatChunk.self, from: data))
        } catch {
            throw LMStudioBackendError.streamDecoding(line: line, reason: error.localizedDescription)
        }
    }
}

struct LMStudioStreamLimits: Sendable {
    static let defaultResponseByteLimit = 32 * 1_024 * 1_024
    static let defaultLineByteLimit = 1 * 1_024 * 1_024
    static let defaultFrameByteLimit = 1 * 1_024 * 1_024
    static let defaultAggregateAccountingByteLimit = 16 * 1_024 * 1_024
    static let defaultBufferedEventLimit = 64

    let responseByteLimit: Int
    let lineByteLimit: Int
    let frameByteLimit: Int
    let aggregateAccountingByteLimit: Int
    let bufferedEventLimit: Int

    init(
        responseByteLimit: Int = defaultResponseByteLimit,
        lineByteLimit: Int = defaultLineByteLimit,
        frameByteLimit: Int = defaultFrameByteLimit,
        aggregateAccountingByteLimit: Int = defaultAggregateAccountingByteLimit,
        bufferedEventLimit: Int = defaultBufferedEventLimit
    ) {
        self.responseByteLimit = max(1, responseByteLimit)
        self.lineByteLimit = max(1, min(lineByteLimit, self.responseByteLimit))
        self.frameByteLimit = max(1, min(frameByteLimit, self.responseByteLimit))
        self.aggregateAccountingByteLimit = max(1, aggregateAccountingByteLimit)
        self.bufferedEventLimit = max(1, bufferedEventLimit)
    }
}

struct LMStudioBoundedLineReader<Bytes: AsyncSequence> where Bytes.Element == UInt8 {
    private var iterator: Bytes.AsyncIterator
    private let responseByteLimit: Int
    private let lineByteLimit: Int
    private var responseByteCount = 0
    private var unfinishedLine = Data()

    init(bytes: Bytes, responseByteLimit: Int, lineByteLimit: Int) {
        self.iterator = bytes.makeAsyncIterator()
        self.responseByteLimit = max(1, responseByteLimit)
        self.lineByteLimit = max(1, lineByteLimit)
        unfinishedLine.reserveCapacity(min(self.lineByteLimit, 4 * 1_024))
    }

    mutating func next() async throws -> String? {
        while let byte = try await iterator.next() {
            guard responseByteCount < responseByteLimit else {
                throw LMStudioStreamIngestionError.responseTooLarge
            }
            responseByteCount += 1
            if byte == 0x0A {
                return try takeLine()
            }
            guard unfinishedLine.count < lineByteLimit else {
                throw LMStudioStreamIngestionError.lineTooLarge
            }
            unfinishedLine.append(byte)
        }
        guard !unfinishedLine.isEmpty else { return nil }
        return try takeLine()
    }

    private mutating func takeLine() throws -> String {
        if unfinishedLine.last == 0x0D {
            unfinishedLine.removeLast()
        }
        guard let line = String(data: unfinishedLine, encoding: .utf8) else {
            throw LMStudioStreamIngestionError.invalidUTF8
        }
        unfinishedLine.removeAll(keepingCapacity: true)
        return line
    }
}

private struct LMStudioStreamBudget {
    let limit: Int
    private(set) var consumed = 0

    mutating func record(reasoning: String, answer: String, includesUsage: Bool) throws {
        let (textBytes, textOverflow) = reasoning.utf8.count.addingReportingOverflow(answer.utf8.count)
        let usageBytes = includesUsage ? 2 * MemoryLayout<Int>.size : 0
        let (additionalBytes, accountingOverflow) = textBytes.addingReportingOverflow(usageBytes)
        guard !textOverflow,
              !accountingOverflow,
              additionalBytes <= limit - consumed else {
            throw LMStudioStreamIngestionError.aggregateAccountingTooLarge
        }
        consumed += additionalBytes
    }
}

private struct LMStudioStreamCompletion {
    let endpoint: String
    let wireMode: ChatProviderWireMode
    let inputTokens: Int?
    let outputTokens: Int?
    let hasUsage: Bool
}

private enum LMStudioStreamIngestionError: Error {
    case responseTooLarge
    case lineTooLarge
    case frameTooLarge
    case invalidUTF8
    case aggregateAccountingTooLarge
    case missingTerminal
}

private extension LMStudioBackendError {
    var shouldFallbackModelCatalogToOpenAICompatible: Bool {
        guard case .httpStatus(_, let statusCode, _) = self else {
            return false
        }
        return statusCode == 404 || statusCode == 405 || statusCode == 501
    }

    var shouldFallbackNativeEndpointToOpenAICompatible: Bool {
        guard case .httpStatus(_, let statusCode, _) = self else {
            return false
        }
        return statusCode == 400 || statusCode == 404 || statusCode == 405
            || statusCode == 422 || statusCode == 501
    }
}

private enum LMStudioCatalogIngestionError: Error {
    case responseTooLarge
}

private enum LMStudioCatalogValidationError: Error, LocalizedError {
    case tooManyModels
    case tooManyLoadedInstances
    case invalidLoadedInstanceIdentity

    var errorDescription: String? {
        switch self {
        case .tooManyModels:
            return "The provider returned too many model rows."
        case .tooManyLoadedInstances:
            return "The provider returned too many loaded model instances."
        case .invalidLoadedInstanceIdentity:
            return "The provider returned invalid loaded model instance metadata."
        }
    }
}

private final class LMStudioGenerationRegistry: @unchecked Sendable {
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

private struct LMStudioNativeModelsResponse: Decodable {
    var models: [LMStudioNativeModel]
}

private struct LMStudioNativeModel: Decodable {
    var type: String?
    var key: String
    var displayName: String?
    var sizeBytes: Int64?
    var contextWindowTokens: Int?
    var loadedInstances: [LMStudioLoadedInstance]
    var hasValidCapabilitySource: Bool {
        type.map { ModelInfo.areValidCapabilities([$0]) } ?? true
    }
    var capabilities: [String] {
        let normalizedType = type?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        switch normalizedType {
        case "embedding", "embeddings", "embed":
            return ["embedding"]
        case "vision", "vl", "image", "multimodal", "mm":
            return ["chat", "vision"]
        case "llm", "chat", "completion", nil:
            return ["chat"]
        default:
            return normalizedType.map { [$0] } ?? ["chat"]
        }
    }

    enum CodingKeys: String, CodingKey {
        case type
        case key
        case id
        case displayName = "display_name"
        case sizeBytes = "size_bytes"
        case contextWindowTokens = "context_window_tokens"
        case contextLength = "context_length"
        case maxContextLength = "max_context_length"
        case nContext = "n_ctx"
        case loadedInstances = "loaded_instances"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        type = try container.decodeIfPresent(String.self, forKey: .type)
        let keyAlias = try container.decodeIfPresent(String.self, forKey: .key)
        let idAlias = try container.decodeIfPresent(String.self, forKey: .id)
        if let keyAlias, let idAlias, Data(keyAlias.utf8) != Data(idAlias.utf8) {
            throw DecodingError.dataCorruptedError(
                forKey: .id,
                in: container,
                debugDescription: "The model identity aliases conflict."
            )
        }
        guard let resolvedKey = keyAlias ?? idAlias else {
            throw DecodingError.keyNotFound(
                CodingKeys.key,
                .init(codingPath: decoder.codingPath, debugDescription: "A model identity is required.")
            )
        }
        key = resolvedKey
        displayName = try container.decodeIfPresent(String.self, forKey: .displayName)
        sizeBytes = try container.decodeIfPresent(Int64.self, forKey: .sizeBytes)
        contextWindowTokens = try container.decodeContextWindowTokens(
            aliases: [.contextWindowTokens, .contextLength, .maxContextLength, .nContext]
        )
        loadedInstances = try container.decodeIfPresent([LMStudioLoadedInstance].self, forKey: .loadedInstances) ?? []
    }
}

private struct LMStudioLoadedInstance: Decodable {
    var id: String
}

private struct LMStudioUnloadModelsResponse: Decodable {
    var models: [LMStudioUnloadModel]
}

private struct LMStudioUnloadModel: Decodable {
    var key: String
    var loadedInstances: [LMStudioLoadedInstance]

    enum CodingKeys: String, CodingKey {
        case key
        case id
        case loadedInstances = "loaded_instances"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let keyAlias = try container.decodeIfPresent(String.self, forKey: .key)
        let idAlias = try container.decodeIfPresent(String.self, forKey: .id)
        if let keyAlias, let idAlias, Data(keyAlias.utf8) != Data(idAlias.utf8) {
            throw DecodingError.dataCorruptedError(
                forKey: .id,
                in: container,
                debugDescription: "The model identity aliases conflict."
            )
        }
        guard let resolvedKey = keyAlias ?? idAlias else {
            throw DecodingError.keyNotFound(
                CodingKeys.key,
                .init(codingPath: decoder.codingPath, debugDescription: "A model identity is required.")
            )
        }
        key = resolvedKey
        loadedInstances = try container.decode(
            [LMStudioLoadedInstance].self,
            forKey: .loadedInstances
        )
    }
}

private enum LMStudioNativeModelLookup {
    case unsupported
    case model(LMStudioUnloadModel?)
}

private struct OpenAIModelsResponse: Decodable {
    var data: [OpenAIModel]
}

private struct OpenAIEmbeddingsRequest: Encodable {
    var model: String
    var input: [String]
}

private struct OpenAIEmbeddingsResponse: Decodable {
    var model: String?
    var data: [OpenAIEmbeddingData]
}

private struct OpenAIEmbeddingData: Decodable {
    var index: Int
    var embedding: [Double]
}

private struct OpenAIModel: Decodable {
    var id: String
    var contextWindowTokens: Int?

    enum CodingKeys: String, CodingKey {
        case id
        case contextWindowTokens = "context_window_tokens"
        case contextLength = "context_length"
        case maxContextLength = "max_context_length"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        contextWindowTokens = try container.decodeContextWindowTokens(
            aliases: [.contextWindowTokens, .contextLength, .maxContextLength]
        )
    }
}

private extension KeyedDecodingContainer {
    func decodeContextWindowTokens(aliases: [Key]) throws -> Int? {
        var decodedValues: [Int] = []
        for alias in aliases where contains(alias) {
            let value = try decode(Decimal.self, forKey: alias)
            guard let validatedValue = ModelInfo.validatedContextWindowTokens(decimal: value) else {
                throw DecodingError.dataCorruptedError(
                    forKey: alias,
                    in: self,
                    debugDescription: "Context-window metadata must be a positive integer no greater than \(ModelInfo.maximumContextWindowTokens)."
                )
            }
            decodedValues.append(validatedValue)
        }
        guard let firstValue = decodedValues.first else {
            return nil
        }
        guard decodedValues.dropFirst().allSatisfy({ $0 == firstValue }) else {
            throw DecodingError.dataCorrupted(.init(
                codingPath: codingPath,
                debugDescription: "Context-window metadata aliases conflict."
            ))
        }
        return firstValue
    }
}

private struct LMStudioUnloadRequest: Encodable {
    var instanceID: String

    enum CodingKeys: String, CodingKey {
        case instanceID = "instance_id"
    }
}

private struct LMStudioUnloadResponse: Decodable {
    var instanceID: String

    enum CodingKeys: String, CodingKey {
        case instanceID = "instance_id"
    }
}

private struct LMStudioNativeChatRequest: Encodable {
    var model: String
    var input: [LMStudioInputItem]
    var stream = true
    var store = false

    init(model: String, messages: [ChatMessage]) {
        self.model = model
        input = messages.flatMap(LMStudioInputItem.items)
    }
}

private struct LMStudioInputItem: Encodable {
    var type: String
    var role: String?
    var content: String?
    var dataURL: String?

    enum CodingKeys: String, CodingKey {
        case type
        case role
        case content
        case dataURL = "data_url"
    }

    static func items(message: ChatMessage) -> [LMStudioInputItem] {
        let imageItems = message.attachments.compactMap(image)
        let trimmedContent = message.content.trimmingCharacters(in: .whitespacesAndNewlines)
        var items: [LMStudioInputItem] = []

        if !trimmedContent.isEmpty || imageItems.isEmpty {
            items.append(.message(role: message.role, content: message.content))
        }
        items.append(contentsOf: imageItems)
        return items
    }

    static func message(role: String, content: String) -> LMStudioInputItem {
        LMStudioInputItem(type: "message", role: role, content: content)
    }

    static func image(_ attachment: ChatAttachment) -> LMStudioInputItem? {
        guard let dataURL = attachment.imageDataURL else { return nil }
        return LMStudioInputItem(type: "image", dataURL: dataURL)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type, forKey: .type)
        try container.encodeIfPresent(role, forKey: .role)
        try container.encodeIfPresent(content, forKey: .content)
        try container.encodeIfPresent(dataURL, forKey: .dataURL)
    }
}

private struct OpenAIChatCompletionsRequest: Encodable {
    var model: String
    var messages: [OpenAIChatMessage]
    var stream: Bool
    var streamOptions: OpenAIStreamOptions

    enum CodingKeys: String, CodingKey {
        case model
        case messages
        case stream
        case streamOptions = "stream_options"
    }

    init(model: String, messages: [ChatMessage], stream: Bool, streamOptions: OpenAIStreamOptions) {
        self.model = model
        self.messages = messages.map(OpenAIChatMessage.init(message:))
        self.stream = stream
        self.streamOptions = streamOptions
    }
}

private struct OpenAIStreamOptions: Encodable {
    var includeUsage: Bool

    enum CodingKeys: String, CodingKey {
        case includeUsage = "include_usage"
    }
}

private struct OpenAIChatMessage: Encodable {
    var role: String
    var content: OpenAIMessageContent

    init(message: ChatMessage) {
        role = message.role
        let imageParts = message.attachments.compactMap(OpenAIContentPart.image)
        guard !imageParts.isEmpty else {
            content = .text(message.content)
            return
        }

        var parts: [OpenAIContentPart] = []
        let trimmedContent = message.content.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedContent.isEmpty {
            parts.append(.text(trimmedContent))
        }
        parts.append(contentsOf: imageParts)
        content = .parts(parts)
    }
}

private enum OpenAIMessageContent: Encodable {
    case text(String)
    case parts([OpenAIContentPart])

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .text(let text):
            try container.encode(text)
        case .parts(let parts):
            try container.encode(parts)
        }
    }
}

private struct OpenAIContentPart: Encodable {
    var type: String
    var text: String?
    var imageURL: OpenAIImageURL?

    enum CodingKeys: String, CodingKey {
        case type
        case text
        case imageURL = "image_url"
    }

    static func text(_ text: String) -> OpenAIContentPart {
        OpenAIContentPart(type: "text", text: text)
    }

    static func image(_ attachment: ChatAttachment) -> OpenAIContentPart? {
        guard let dataURL = attachment.imageDataURL else { return nil }
        return OpenAIContentPart(
            type: "image_url",
            imageURL: OpenAIImageURL(url: dataURL)
        )
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type, forKey: .type)
        try container.encodeIfPresent(text, forKey: .text)
        try container.encodeIfPresent(imageURL, forKey: .imageURL)
    }
}

private struct OpenAIImageURL: Encodable {
    var url: String
}

private struct LMStudioMessageDelta: Decodable {
    var content: String?
    var reasoningContent: String?
    var reasoningDelta: String?
    var thinkingDelta: String?
    var reasoning: String?
    var thinking: String?
    var thoughts: String?

    var answerText: String {
        content ?? ""
    }

    var reasoningText: String {
        reasoningContent ??
            reasoningDelta ??
            thinkingDelta ??
            reasoning ??
            thinking ??
            thoughts ??
            ""
    }

    enum CodingKeys: String, CodingKey {
        case content
        case reasoningContent = "reasoning_content"
        case reasoningDelta = "reasoning_delta"
        case thinkingDelta = "thinking_delta"
        case reasoning
        case thinking
        case thoughts
    }
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

private enum OpenAIStreamLine {
    case chunk(OpenAIChatChunk)
    case done
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
    var reasoningContent: String?
    var reasoningDelta: String?
    var thinkingDelta: String?
    var reasoning: String?
    var thinking: String?
    var thoughts: String?

    var reasoningText: String {
        reasoningContent ??
            reasoningDelta ??
            thinkingDelta ??
            reasoning ??
            thinking ??
            thoughts ??
            ""
    }

    enum CodingKeys: String, CodingKey {
        case content
        case reasoningContent = "reasoning_content"
        case reasoningDelta = "reasoning_delta"
        case thinkingDelta = "thinking_delta"
        case reasoning
        case thinking
        case thoughts
    }
}

private struct OpenAIUsage: Decodable {
    var promptTokens: Int?
    var completionTokens: Int?

    enum CodingKeys: String, CodingKey {
        case promptTokens = "prompt_tokens"
        case completionTokens = "completion_tokens"
    }
}

private extension ChatAttachment {
    var isImage: Bool {
        let normalizedType = type.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let normalizedMimeType = mimeType.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return normalizedType == "image" || normalizedMimeType.hasPrefix("image/")
    }

    var imageDataURL: String? {
        guard isImage,
              let dataBase64 = dataBase64?.trimmingCharacters(in: .whitespacesAndNewlines),
              !dataBase64.isEmpty
        else {
            return nil
        }
        let normalizedMimeType = mimeType.trimmingCharacters(in: .whitespacesAndNewlines)
        let resolvedMimeType = normalizedMimeType.isEmpty ? "image/png" : normalizedMimeType
        return "data:\(resolvedMimeType);base64,\(dataBase64)"
    }
}

private struct ServerSentEvent {
    var name: String
    var data: String
}

private struct ServerSentEventParser {
    private let frameByteLimit: Int
    private var eventName = "message"
    private var dataLines: [String] = []
    private var dataByteCount = 0

    init(frameByteLimit: Int) {
        self.frameByteLimit = max(1, frameByteLimit)
    }

    mutating func append(_ line: String) throws -> [ServerSentEvent] {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return flush()
        }
        if trimmed.hasPrefix("event:") {
            eventName = String(trimmed.dropFirst("event:".count)).trimmingCharacters(in: .whitespaces)
            return []
        }
        if trimmed.hasPrefix("data:") {
            let dataLine = String(trimmed.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces)
            let separatorBytes = dataLines.isEmpty ? 0 : 1
            let (lineAndSeparatorBytes, overflow) = dataLine.utf8.count.addingReportingOverflow(separatorBytes)
            guard !overflow,
                  lineAndSeparatorBytes <= frameByteLimit - dataByteCount else {
                throw LMStudioStreamIngestionError.frameTooLarge
            }
            dataLines.append(dataLine)
            dataByteCount += lineAndSeparatorBytes
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
        dataByteCount = 0
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
