import Foundation
import OllamaBackend

public final class AggregatingLlmBackend: LlmBackend, @unchecked Sendable {
    public let provider = ModelProvider.aggregate

    private let orderedBackends: [any LlmBackend]
    private let backendsByProvider: [ModelProvider: any LlmBackend]
    private let lock = NSLock()
    private var generationProviders: [String: ModelProvider] = [:]
    private var activeResidencyModel: RuntimeModelResidencyKey?
    private var inFlightResidencyCounts: [RuntimeModelResidencyKey: Int] = [:]
    private var idleUnloadTask: Task<Void, Never>?
    private let modelIdleUnloadDelayNanoseconds: UInt64
    private var residencyEventHandler: (@Sendable (RuntimeModelResidencyEvent) -> Void)?

    public init(
        _ backends: [any LlmBackend],
        modelIdleUnloadDelayNanoseconds: UInt64 = 600_000_000_000
    ) {
        orderedBackends = backends
        backendsByProvider = Dictionary(uniqueKeysWithValues: backends.map { ($0.provider, $0) })
        self.modelIdleUnloadDelayNanoseconds = modelIdleUnloadDelayNanoseconds
    }

    public convenience init(ollama: any LlmBackend, lmStudio: any LlmBackend) {
        self.init([ollama, lmStudio])
    }

    public func setResidencyEventHandler(_ handler: (@Sendable (RuntimeModelResidencyEvent) -> Void)?) {
        lock.withLock {
            residencyEventHandler = handler
        }
    }

    public func modelResidencySnapshot() -> RuntimeModelResidencySnapshot {
        lock.withLock {
            RuntimeModelResidencySnapshot(
                activeProvider: activeResidencyModel?.provider,
                activeModelID: activeResidencyModel?.modelID,
                inFlightGenerations: inFlightResidencyCounts.values.reduce(0, +),
                idleUnloadDelaySeconds: Int(modelIdleUnloadDelayNanoseconds / 1_000_000_000)
            )
        }
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
            message: "No model provider is reachable from AetherLink Runtime.",
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
                message: "LM Studio model downloads are managed through LM Studio or lms for AetherLink Runtime.",
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
                    let residencyModel = RuntimeModelResidencyKey(
                        provider: resolved.provider,
                        modelID: resolved.modelID
                    )
                    await prepareResidency(for: residencyModel)
                    defer {
                        Task { [weak self] in
                            await self?.finishResidency(for: residencyModel)
                        }
                    }
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
        let models = try await listModels()
        if let resolved = ModelProvider.splitQualifiedModelID(model) {
            if let match = Self.matchingInstalledModel(
                requestedModel: resolved.modelID,
                requestedProvider: resolved.provider,
                models: models
            ) {
                return (match.provider, match.providerModelID)
            }
            throw Self.modelNotInstalledError(model, provider: resolved.provider)
        }

        if let match = Self.matchingInstalledModel(requestedModel: model, models: models) {
            return (match.provider, match.providerModelID)
        }

        throw Self.modelNotInstalledError(model, provider: .aggregate)
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
                message: "\(provider.displayName) is not enabled in AetherLink Runtime.",
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

    private func prepareResidency(for model: RuntimeModelResidencyKey) async {
        let result: (modelToUnload: RuntimeModelResidencyKey?, activeChanged: Bool) = lock.withLock {
            idleUnloadTask?.cancel()
            idleUnloadTask = nil

            let previous = activeResidencyModel
            let previousCanUnload = previous.flatMap { inFlightResidencyCounts[$0, default: 0] == 0 ? $0 : nil }
            activeResidencyModel = model
            inFlightResidencyCounts[model, default: 0] += 1
            guard previousCanUnload != model else {
                return (nil, previous != model)
            }
            return (previousCanUnload, previous != model)
        }

        if result.activeChanged {
            emit(.activeModelChanged(provider: model.provider, modelID: model.modelID))
        }

        if let modelToUnload = result.modelToUnload {
            await unloadResidencyModel(modelToUnload, reason: .modelSwitch)
        }
    }

    private func finishResidency(for model: RuntimeModelResidencyKey) async {
        let result: (modelToUnload: RuntimeModelResidencyKey?, reason: RuntimeModelResidencyUnloadReason?) = lock.withLock {
            let remaining = max(0, inFlightResidencyCounts[model, default: 0] - 1)
            if remaining == 0 {
                inFlightResidencyCounts[model] = nil
            } else {
                inFlightResidencyCounts[model] = remaining
                return (nil, nil)
            }

            if activeResidencyModel == model {
                idleUnloadTask?.cancel()
                if modelIdleUnloadDelayNanoseconds == 0 {
                    activeResidencyModel = nil
                    idleUnloadTask = nil
                    return (model, .idleTimeout)
                }
                idleUnloadTask = Task { [weak self, modelIdleUnloadDelayNanoseconds] in
                    do {
                        try await Task.sleep(nanoseconds: modelIdleUnloadDelayNanoseconds)
                    } catch {
                        return
                    }
                    await self?.unloadIdleResidencyModel(model)
                }
                return (nil, nil)
            }

            return (model, .modelSwitch)
        }

        if let modelToUnload = result.modelToUnload, let reason = result.reason {
            await unloadResidencyModel(modelToUnload, reason: reason)
        }
    }

    private func unloadIdleResidencyModel(_ model: RuntimeModelResidencyKey) async {
        let shouldUnload = lock.withLock {
            guard activeResidencyModel == model, inFlightResidencyCounts[model, default: 0] == 0 else {
                return false
            }
            activeResidencyModel = nil
            idleUnloadTask = nil
            return true
        }

        if shouldUnload {
            await unloadResidencyModel(model, reason: .idleTimeout)
        }
    }

    private func unloadResidencyModel(
        _ model: RuntimeModelResidencyKey,
        reason: RuntimeModelResidencyUnloadReason
    ) async {
        guard let backend = backendsByProvider[model.provider] else {
            return
        }
        emit(.unloadRequested(provider: model.provider, modelID: model.modelID, reason: reason))
        do {
            _ = try await backend.unloadModel(providerModelID: model.modelID)
            emit(.unloadSucceeded(provider: model.provider, modelID: model.modelID, reason: reason))
        } catch {
            emit(.unloadFailed(
                provider: model.provider,
                modelID: model.modelID,
                reason: reason,
                message: error.localizedDescription
            ))
            return
        }
    }

    private func emit(_ event: RuntimeModelResidencyEvent) {
        let handler = lock.withLock { residencyEventHandler }
        handler?(event)
    }

    private static func canonicalModelName(_ name: String) -> String {
        if name.hasSuffix(":latest") {
            return String(name.dropLast(":latest".count))
        }
        return name
    }

    private static func matchingInstalledModel(
        requestedModel: String,
        requestedProvider: ModelProvider? = nil,
        models: [ModelInfo]
    ) -> ModelInfo? {
        let requestedCanonical = canonicalModelName(requestedModel)
        return models.first { candidate in
            guard candidate.installed else { return false }
            guard candidate.source == .local else { return false }
            guard candidate.kind == .chat else { return false }
            if let requestedProvider, candidate.provider != requestedProvider {
                return false
            }
            let providerModelID = candidate.providerModelID
            return candidate.id == requestedModel
                || candidate.name == requestedModel
                || providerModelID == requestedModel
                || canonicalModelName(candidate.id) == requestedCanonical
                || canonicalModelName(candidate.name) == requestedCanonical
                || canonicalModelName(providerModelID) == requestedCanonical
        }
    }

    private static func modelNotInstalledError(_ model: String, provider: ModelProvider) -> BackendError {
        BackendError(
            provider: provider,
            code: "model_not_installed",
            message: "Model is not reported as installed by AetherLink Runtime: \(model)",
            retryable: false
        )
    }
}

private struct RuntimeModelResidencyKey: Hashable, Sendable {
    var provider: ModelProvider
    var modelID: String
}

public struct RuntimeModelResidencySnapshot: Equatable, Sendable {
    public var activeProvider: ModelProvider?
    public var activeModelID: String?
    public var inFlightGenerations: Int
    public var idleUnloadDelaySeconds: Int

    public init(
        activeProvider: ModelProvider?,
        activeModelID: String?,
        inFlightGenerations: Int,
        idleUnloadDelaySeconds: Int
    ) {
        self.activeProvider = activeProvider
        self.activeModelID = activeModelID
        self.inFlightGenerations = inFlightGenerations
        self.idleUnloadDelaySeconds = idleUnloadDelaySeconds
    }
}

public enum RuntimeModelResidencyUnloadReason: String, Equatable, Sendable {
    case modelSwitch = "model_switch"
    case idleTimeout = "idle_timeout"
}

public enum RuntimeModelResidencyEvent: Equatable, Sendable {
    case activeModelChanged(provider: ModelProvider, modelID: String)
    case unloadRequested(provider: ModelProvider, modelID: String, reason: RuntimeModelResidencyUnloadReason)
    case unloadSucceeded(provider: ModelProvider, modelID: String, reason: RuntimeModelResidencyUnloadReason)
    case unloadFailed(provider: ModelProvider, modelID: String, reason: RuntimeModelResidencyUnloadReason, message: String)
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
