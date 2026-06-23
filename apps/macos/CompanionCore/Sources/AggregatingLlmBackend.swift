import Foundation
import OllamaBackend

public final class AggregatingLlmBackend: LlmBackend, @unchecked Sendable {
    public let provider = ModelProvider.aggregate

    private let orderedBackends: [any LlmBackend]
    private let backendsByProvider: [ModelProvider: any LlmBackend]
    private let lock = NSLock()
    private var generationProviders: [String: ModelProvider] = [:]

    public init(_ backends: [any LlmBackend]) {
        orderedBackends = backends
        backendsByProvider = Dictionary(uniqueKeysWithValues: backends.map { ($0.provider, $0) })
    }

    public convenience init(ollama: any LlmBackend, lmStudio: any LlmBackend) {
        self.init([ollama, lmStudio])
    }

    public func providerHealth() async -> [ModelProvider: BackendStatus] {
        var statuses: [ModelProvider: BackendStatus] = [:]
        for backend in orderedBackends {
            statuses[backend.provider] = await backend.healthCheck()
        }
        return statuses
    }

    public func healthCheck() async -> BackendStatus {
        let statuses = await providerHealth()
        if statuses.values.contains(.available) {
            return .available
        }
        return .unavailable(BackendError(
            provider: .aggregate,
            code: "backend_unavailable",
            message: "No local model backend is reachable from the companion runtime.",
            retryable: true
        ))
    }

    public func listModels() async throws -> [ModelInfo] {
        var models: [ModelInfo] = []
        var firstError: Error?
        for backend in orderedBackends {
            do {
                models.append(contentsOf: try await backend.listModels())
            } catch {
                if firstError == nil {
                    firstError = error
                }
            }
        }
        if models.isEmpty, let firstError {
            throw firstError
        }
        return models
    }

    public func pullModel(name: String) async throws -> ModelPullResult {
        let resolved = resolveModelReference(name)
        guard resolved.provider != .lmStudio else {
            throw BackendError(
                provider: .lmStudio,
                code: "unsupported_operation",
                message: "LM Studio model downloads are managed on the Mac through LM Studio or lms.",
                retryable: false
            )
        }
        let backend = try backend(for: resolved.provider)
        return try await backend.pullModel(name: resolved.modelID)
    }

    public func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let resolved = try await resolveChatRoute(for: request.model)
                    let backend = try backend(for: resolved.provider)
                    let routedRequest = ChatRequest(
                        generationID: request.generationID,
                        sessionID: request.sessionID,
                        model: resolved.modelID,
                        messages: request.messages
                    )
                    remember(generationID: request.generationID, provider: resolved.provider)
                    for try await event in backend.chat(request: routedRequest) {
                        continuation.yield(event)
                    }
                    forget(generationID: request.generationID)
                    continuation.finish()
                } catch {
                    forget(generationID: request.generationID)
                    continuation.finish(throwing: error)
                }
            }

            continuation.onTermination = { [weak self] termination in
                if case .cancelled = termination {
                    _ = self?.cancel(generationID: request.generationID)
                }
                task.cancel()
            }
        }
    }

    @discardableResult
    public func cancel(generationID: String) -> GenerationCancellationResult {
        if let provider = lock.withLock({ generationProviders[generationID] }),
           let backend = backendsByProvider[provider] {
            let result = backend.cancel(generationID: generationID)
            if case .cancelled = result {
                forget(generationID: generationID)
            }
            return result
        }

        for backend in orderedBackends {
            let result = backend.cancel(generationID: generationID)
            if case .cancelled = result {
                return result
            }
        }
        return .notFound(generationID: generationID)
    }

    private func resolveChatRoute(for model: String) async throws -> (provider: ModelProvider, modelID: String) {
        if let resolved = ModelProvider.splitQualifiedModelID(model) {
            return resolved
        }

        let requestedCanonical = Self.canonicalModelName(model)
        let models = try await listModels()
        if let match = models.first(where: { candidate in
            let providerModelID = candidate.providerModelID
            return candidate.installed && (
                candidate.id == model
                    || candidate.name == model
                    || providerModelID == model
                    || Self.canonicalModelName(candidate.id) == requestedCanonical
                    || Self.canonicalModelName(candidate.name) == requestedCanonical
                    || Self.canonicalModelName(providerModelID) == requestedCanonical
            )
        }) {
            return (match.provider, match.providerModelID)
        }

        return (.ollama, model)
    }

    private func resolveModelReference(_ model: String) -> (provider: ModelProvider, modelID: String) {
        if let resolved = ModelProvider.splitQualifiedModelID(model) {
            return resolved
        }
        return (.ollama, model)
    }

    private func backend(for provider: ModelProvider) throws -> any LlmBackend {
        guard let backend = backendsByProvider[provider] else {
            throw BackendError(
                provider: provider,
                code: "backend_unavailable",
                message: "\(provider.displayName) is not enabled in the companion runtime.",
                retryable: false
            )
        }
        return backend
    }

    private func remember(generationID: String, provider: ModelProvider) {
        lock.withLock {
            generationProviders[generationID] = provider
        }
    }

    private func forget(generationID: String) {
        lock.withLock {
            generationProviders[generationID] = nil
        }
    }

    private static func canonicalModelName(_ name: String) -> String {
        if name.hasSuffix(":latest") {
            return String(name.dropLast(":latest".count))
        }
        return name
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
