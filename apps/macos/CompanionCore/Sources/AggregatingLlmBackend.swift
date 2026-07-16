import Foundation
import OllamaBackend

private final class RuntimeAggregateGenerationReservation: @unchecked Sendable {
    var task: Task<Void, Never>?

    private let lock = NSLock()
    private var activated = false
    private var activationContinuation: CheckedContinuation<Void, Never>?

    func waitUntilActivated() async {
        await withCheckedContinuation { continuation in
            lock.withLock {
                if activated {
                    continuation.resume()
                } else {
                    activationContinuation = continuation
                }
            }
        }
    }

    func activate() {
        let continuation = lock.withLock {
            activated = true
            let continuation = activationContinuation
            activationContinuation = nil
            return continuation
        }
        continuation?.resume()
    }
}

private final class RuntimeResidencyUnloadGate: @unchecked Sendable {
    private let lock = NSLock()
    private var activated = false
    private var activationContinuation: CheckedContinuation<Void, Never>?

    func waitUntilActivated() async {
        await withCheckedContinuation { continuation in
            lock.withLock {
                if activated {
                    continuation.resume()
                } else {
                    activationContinuation = continuation
                }
            }
        }
    }

    func activate() {
        let continuation = lock.withLock {
            activated = true
            let continuation = activationContinuation
            activationContinuation = nil
            return continuation
        }
        continuation?.resume()
    }
}

private struct RuntimeResidencyUnloadOperation: @unchecked Sendable {
    let id: UUID
    let model: RuntimeModelResidencyKey
    let reason: RuntimeModelResidencyUnloadReason
    let gate: RuntimeResidencyUnloadGate
    let task: Task<Void, Never>
}

private enum RuntimeResidencyUnloadExecution {
    case succeeded
    case failed(message: String)
}

private enum RuntimeResidencyPreparation {
    case cancelled
    case wait(RuntimeResidencyUnloadOperation)
    case ready(activeChanged: Bool)
}

public final class AggregatingLlmBackend: LlmBackend, @unchecked Sendable {
    public let provider = ModelProvider.aggregate

    private let orderedBackends: [any LlmBackend]
    private let backendsByProvider: [ModelProvider: any LlmBackend]
    private let lock = NSLock()
    private var generationProviders: [String: ModelProvider] = [:]
    private var generationReservations: [String: RuntimeAggregateGenerationReservation] = [:]
    private var completedProviderUsageSources: [String: (source: ChatProviderUsageSource, sequence: UInt64)] = [:]
    private var completedProviderUsageSequence: UInt64 = 0
    private var activeResidencyModel: RuntimeModelResidencyKey?
    private var inFlightResidencyCounts: [RuntimeModelResidencyKey: Int] = [:]
    private var lastUnloadFailure: RuntimeModelResidencyUnloadFailure?
    private var idleUnloadTask: Task<Void, Never>?
    private var idleUnloadGeneration: UInt64 = 0
    private var idleResidencyStartedAtUptimeNanoseconds: UInt64?
    private var modelIdleUnloadDelayNanoseconds: UInt64
    private let idleUnloadSleeper: @Sendable (UInt64) async throws -> Void
    private let idleUnloadAttemptHandler: @Sendable () -> Void
    private var residencyUnloadOperations: [RuntimeModelResidencyKey: RuntimeResidencyUnloadOperation] = [:]
    private var residencyEventHandler: (@Sendable (RuntimeModelResidencyEvent) -> Void)?

    public convenience init(
        _ backends: [any LlmBackend],
        modelIdleUnloadDelayNanoseconds: UInt64 = 600_000_000_000
    ) {
        self.init(
            backends,
            modelIdleUnloadDelayNanoseconds: modelIdleUnloadDelayNanoseconds,
            idleUnloadSleeper: { delayNanoseconds in
                try await Task.sleep(nanoseconds: delayNanoseconds)
            },
            idleUnloadAttemptHandler: {}
        )
    }

    init(
        _ backends: [any LlmBackend],
        modelIdleUnloadDelayNanoseconds: UInt64,
        idleUnloadSleeper: @escaping @Sendable (UInt64) async throws -> Void,
        idleUnloadAttemptHandler: @escaping @Sendable () -> Void = {}
    ) {
        let uniqueBackends = Self.firstBackendsByProvider(backends)
        orderedBackends = uniqueBackends.ordered
        backendsByProvider = uniqueBackends.byProvider
        self.modelIdleUnloadDelayNanoseconds = modelIdleUnloadDelayNanoseconds
        self.idleUnloadSleeper = idleUnloadSleeper
        self.idleUnloadAttemptHandler = idleUnloadAttemptHandler
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
            let unloading = residencyUnloadOperations.values.min { lhs, rhs in
                let lhsKey = "\(lhs.model.provider.rawValue):\(lhs.model.modelID)"
                let rhsKey = "\(rhs.model.provider.rawValue):\(rhs.model.modelID)"
                return lhsKey < rhsKey
            }
            return RuntimeModelResidencySnapshot(
                activeProvider: activeResidencyModel?.provider,
                activeModelID: activeResidencyModel?.modelID,
                inFlightGenerations: inFlightResidencyCounts.values.reduce(0, +),
                idleUnloadDelaySeconds: Int(modelIdleUnloadDelayNanoseconds / 1_000_000_000),
                unloadingProvider: unloading?.model.provider,
                unloadingModelID: unloading?.model.modelID,
                unloadingReason: unloading?.reason,
                lastUnloadFailure: lastUnloadFailure
            )
        }
    }

    public func updateModelIdleUnloadDelayNanoseconds(_ delayNanoseconds: UInt64) async {
        let unloadOperation = beginModelIdleUnloadDelayUpdate(delayNanoseconds)
        if let unloadOperation {
            await runResidencyUnloadOperation(unloadOperation)
        }
    }

    public func configureModelIdleUnloadDelayNanoseconds(_ delayNanoseconds: UInt64) {
        let unloadOperation = beginModelIdleUnloadDelayUpdate(delayNanoseconds)
        if let unloadOperation {
            unloadOperation.gate.activate()
        }
    }

    private func beginModelIdleUnloadDelayUpdate(
        _ delayNanoseconds: UInt64
    ) -> RuntimeResidencyUnloadOperation? {
        lock.withLock {
            guard modelIdleUnloadDelayNanoseconds != delayNanoseconds else {
                return nil
            }
            modelIdleUnloadDelayNanoseconds = delayNanoseconds
            cancelIdleUnloadTaskLocked()

            guard let activeResidencyModel,
                  inFlightResidencyCounts[activeResidencyModel, default: 0] == 0
            else {
                idleResidencyStartedAtUptimeNanoseconds = nil
                return nil
            }

            let now = DispatchTime.now().uptimeNanoseconds
            let idleStartedAt = idleResidencyStartedAtUptimeNanoseconds ?? now
            idleResidencyStartedAtUptimeNanoseconds = idleStartedAt
            let elapsed = now >= idleStartedAt ? now - idleStartedAt : 0
            guard delayNanoseconds > elapsed else {
                idleResidencyStartedAtUptimeNanoseconds = nil
                return makeResidencyUnloadOperationLocked(
                    for: activeResidencyModel,
                    reason: .idleTimeout
                )
            }

            scheduleIdleUnloadTaskLocked(
                for: activeResidencyModel,
                delayNanoseconds: delayNanoseconds - elapsed
            )
            return nil
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
            let reservation = RuntimeAggregateGenerationReservation()
            let task = Task {
                await reservation.waitUntilActivated()
                var residencyModel: RuntimeModelResidencyKey?
                var residencyFinished = false
                do {
                    try Task.checkCancellation()
                    let resolved = try await resolveChatRoute(for: request.model)
                    let backend = try backend(for: resolved.provider)
                    let currentResidencyModel = RuntimeModelResidencyKey(
                        provider: resolved.provider,
                        modelID: resolved.modelID
                    )
                    try await prepareResidency(for: currentResidencyModel)
                    residencyModel = currentResidencyModel
                    try Task.checkCancellation()
                    let routedRequest = ChatRequest(
                        generationID: request.generationID,
                        sessionID: request.sessionID,
                        model: resolved.modelID,
                        messages: request.messages
                    )
                    let providerEvents = try providerChatStreamIfActive(
                        request: routedRequest,
                        provider: resolved.provider,
                        backend: backend
                    )
                    for try await event in providerEvents {
                        if case .done = event {
                            if let source = backend.takeProviderUsageSource(
                                generationID: routedRequest.generationID
                            ) {
                                storeCompletedProviderUsageSource(
                                    source,
                                    generationID: request.generationID
                                )
                            }
                            if !residencyFinished {
                                residencyFinished = true
                                await finishResidency(for: currentResidencyModel)
                            }
                        }
                        continuation.yield(event)
                    }
                    if !residencyFinished {
                        residencyFinished = true
                        await finishResidency(for: currentResidencyModel)
                    }
                    forget(generationID: request.generationID, reservation: reservation)
                    continuation.finish()
                } catch {
                    if let residencyModel, !residencyFinished {
                        residencyFinished = true
                        await finishResidency(for: residencyModel)
                    }
                    forget(generationID: request.generationID, reservation: reservation)
                    continuation.finish(throwing: error)
                }
            }
            reservation.task = task
            let registered = lock.withLock {
                guard generationReservations[request.generationID] == nil else { return false }
                completedProviderUsageSources[request.generationID] = nil
                generationReservations[request.generationID] = reservation
                return true
            }
            guard registered else {
                task.cancel()
                reservation.activate()
                continuation.finish(throwing: BackendError(
                    provider: .aggregate,
                    code: "generation_already_active",
                    message: "A generation with this request id is already active.",
                    retryable: false
                ))
                return
            }
            reservation.activate()

            continuation.onTermination = { [weak self] termination in
                if case .cancelled = termination {
                    _ = self?.cancel(generationID: request.generationID)
                }
                task.cancel()
            }
        }
    }

    public func takeProviderUsageSource(generationID: String) -> ChatProviderUsageSource? {
        lock.withLock {
            completedProviderUsageSources.removeValue(forKey: generationID)?.source
        }
    }

    public func embed(request: EmbeddingRequest) async throws -> EmbeddingResult {
        let resolved = try await resolveEmbeddingRoute(for: request.model)
        let backend = try backend(for: resolved.provider)
        let residencyModel = RuntimeModelResidencyKey(
            provider: resolved.provider,
            modelID: resolved.modelID
        )
        try await prepareResidency(for: residencyModel)
        do {
            try Task.checkCancellation()
            let result = try await backend.embed(request: EmbeddingRequest(
                model: resolved.modelID,
                texts: request.texts
            ))
            await finishResidency(for: residencyModel)
            return result
        } catch {
            await finishResidency(for: residencyModel)
            try Task.checkCancellation()
            throw error
        }
    }

    @discardableResult
    public func cancel(generationID: String) -> GenerationCancellationResult {
        let active: (reserved: Bool, provider: ModelProvider?) = lock.withLock {
            guard let reservation = generationReservations[generationID],
                  let task = reservation.task else {
                return (false, nil)
            }
            task.cancel()
            return (true, generationProviders[generationID])
        }
        if active.reserved {
            if let provider = active.provider,
               let backend = backendsByProvider[provider] {
                _ = backend.cancel(generationID: generationID)
            }
            return .cancelled(generationID: generationID)
        }

        for backend in orderedBackends {
            let result = backend.cancel(generationID: generationID)
            if case .cancelled = result {
                return result
            }
        }
        return .notFound(generationID: generationID)
    }

    @discardableResult
    public func unloadActiveResidencyModelNow() async -> RuntimeModelResidencyManualUnloadResult {
        let outcome: (
            result: RuntimeModelResidencyManualUnloadResult,
            unloadOperation: RuntimeResidencyUnloadOperation?
        ) = lock.withLock {
            guard let model = activeResidencyModel else {
                return (.noActiveModel, nil)
            }
            let inFlightGenerations = inFlightResidencyCounts[model, default: 0]
            guard inFlightGenerations == 0 else {
                return (.inFlightGenerations(inFlightGenerations), nil)
            }
            idleResidencyStartedAtUptimeNanoseconds = nil
            cancelIdleUnloadTaskLocked()
            return (
                .requested(provider: model.provider, modelID: model.modelID),
                makeResidencyUnloadOperationLocked(for: model, reason: .manual)
            )
        }

        if let unloadOperation = outcome.unloadOperation {
            await runResidencyUnloadOperation(unloadOperation)
        }
        return outcome.result
    }

    private func resolveChatRoute(for model: String) async throws -> (provider: ModelProvider, modelID: String) {
        let models = try await listModels()
        if let resolved = ModelProvider.splitQualifiedModelID(model) {
            if let match = Self.matchingInstalledProviderModelID(
                resolved.modelID,
                provider: resolved.provider,
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

    private func resolveEmbeddingRoute(for model: String) async throws -> (provider: ModelProvider, modelID: String) {
        let models = try await listModels()
        if let resolved = ModelProvider.splitQualifiedModelID(model),
           let match = Self.matchingInstalledProviderModelID(
               resolved.modelID,
               provider: resolved.provider,
               requiredKind: .embedding,
               models: models
           ) {
            return (match.provider, match.providerModelID)
        }

        let provider = ModelProvider.splitQualifiedModelID(model)?.provider ?? .aggregate
        throw Self.modelNotInstalledError(model, provider: provider)
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

    private static func firstBackendsByProvider(
        _ backends: [any LlmBackend]
    ) -> (ordered: [any LlmBackend], byProvider: [ModelProvider: any LlmBackend]) {
        var ordered: [any LlmBackend] = []
        var byProvider: [ModelProvider: any LlmBackend] = [:]
        for backend in backends {
            if byProvider[backend.provider] == nil {
                ordered.append(backend)
                byProvider[backend.provider] = backend
            }
        }
        return (ordered, byProvider)
    }

    private func forget(
        generationID: String,
        reservation: RuntimeAggregateGenerationReservation
    ) {
        lock.withLock {
            guard generationReservations[generationID] === reservation else { return }
            generationProviders[generationID] = nil
            generationReservations[generationID] = nil
        }
    }

    private func providerChatStreamIfActive(
        request: ChatRequest,
        provider: ModelProvider,
        backend: any LlmBackend
    ) throws -> AsyncThrowingStream<ChatStreamEvent, Error> {
        try lock.withLock {
            guard generationReservations[request.generationID] != nil else {
                throw CancellationError()
            }
            try Task.checkCancellation()
            generationProviders[request.generationID] = provider
            return backend.chat(request: request)
        }
    }

    private func storeCompletedProviderUsageSource(
        _ source: ChatProviderUsageSource,
        generationID: String
    ) {
        lock.withLock {
            completedProviderUsageSequence &+= 1
            completedProviderUsageSources[generationID] = (
                source: source,
                sequence: completedProviderUsageSequence
            )
            while completedProviderUsageSources.count > 256,
                  let oldest = completedProviderUsageSources.min(by: {
                      $0.value.sequence < $1.value.sequence
                  })?.key {
                completedProviderUsageSources[oldest] = nil
            }
        }
    }

    private func prepareResidency(for model: RuntimeModelResidencyKey) async throws {
        while true {
            try Task.checkCancellation()
            let preparation: RuntimeResidencyPreparation = lock.withLock {
                guard !Task.isCancelled else {
                    return .cancelled
                }
                if let unloadOperation = residencyUnloadOperations[model] {
                    return .wait(unloadOperation)
                }

                cancelIdleUnloadTaskLocked()
                idleResidencyStartedAtUptimeNanoseconds = nil

                let previous = activeResidencyModel
                let previousCanUnload = previous.flatMap {
                    inFlightResidencyCounts[$0, default: 0] == 0 ? $0 : nil
                }
                if let previousCanUnload, previousCanUnload != model {
                    return .wait(
                        makeResidencyUnloadOperationLocked(
                            for: previousCanUnload,
                            reason: .modelSwitch
                        )
                    )
                }
                activeResidencyModel = model
                inFlightResidencyCounts[model, default: 0] += 1
                return .ready(activeChanged: previous != model)
            }

            switch preparation {
            case .cancelled:
                throw CancellationError()
            case .wait(let unloadOperation):
                await runResidencyUnloadOperation(unloadOperation)
                try Task.checkCancellation()
                continue
            case .ready(let activeChanged):
                if activeChanged {
                    emit(.activeModelChanged(provider: model.provider, modelID: model.modelID))
                } else {
                    emit(.stateChanged)
                }
                return
            }
        }
    }

    private func finishResidency(for model: RuntimeModelResidencyKey) async {
        let unloadOperation: RuntimeResidencyUnloadOperation? = lock.withLock {
            let remaining = max(0, inFlightResidencyCounts[model, default: 0] - 1)
            if remaining == 0 {
                inFlightResidencyCounts[model] = nil
            } else {
                inFlightResidencyCounts[model] = remaining
                return nil
            }

            if activeResidencyModel == model {
                idleResidencyStartedAtUptimeNanoseconds = DispatchTime.now().uptimeNanoseconds
                if modelIdleUnloadDelayNanoseconds == 0 {
                    idleResidencyStartedAtUptimeNanoseconds = nil
                    cancelIdleUnloadTaskLocked()
                    return makeResidencyUnloadOperationLocked(for: model, reason: .idleTimeout)
                }
                scheduleIdleUnloadTaskLocked(
                    for: model,
                    delayNanoseconds: modelIdleUnloadDelayNanoseconds
                )
                return nil
            }

            return makeResidencyUnloadOperationLocked(for: model, reason: .modelSwitch)
        }
        emit(.stateChanged)

        if let unloadOperation {
            await runResidencyUnloadOperation(unloadOperation)
        }
    }

    private func cancelIdleUnloadTaskLocked() {
        idleUnloadGeneration &+= 1
        idleUnloadTask?.cancel()
        idleUnloadTask = nil
    }

    private func scheduleIdleUnloadTaskLocked(
        for model: RuntimeModelResidencyKey,
        delayNanoseconds: UInt64
    ) {
        idleUnloadGeneration &+= 1
        let generation = idleUnloadGeneration
        let sleeper = idleUnloadSleeper
        idleUnloadTask?.cancel()
        idleUnloadTask = Task { [weak self] in
            do {
                try await sleeper(delayNanoseconds)
            } catch {
                return
            }
            await self?.unloadIdleResidencyModel(model, generation: generation)
        }
    }

    private func unloadIdleResidencyModel(
        _ model: RuntimeModelResidencyKey,
        generation: UInt64
    ) async {
        let unloadOperation: RuntimeResidencyUnloadOperation? = lock.withLock {
            guard idleUnloadGeneration == generation,
                  activeResidencyModel == model,
                  inFlightResidencyCounts[model, default: 0] == 0
            else {
                return nil
            }
            idleUnloadTask = nil
            idleResidencyStartedAtUptimeNanoseconds = nil
            idleUnloadGeneration &+= 1
            return makeResidencyUnloadOperationLocked(for: model, reason: .idleTimeout)
        }
        idleUnloadAttemptHandler()

        if let unloadOperation {
            await runResidencyUnloadOperation(unloadOperation)
        }
    }

    private func makeResidencyUnloadOperationLocked(
        for model: RuntimeModelResidencyKey,
        reason: RuntimeModelResidencyUnloadReason
    ) -> RuntimeResidencyUnloadOperation {
        if let existing = residencyUnloadOperations[model] {
            return existing
        }

        let id = UUID()
        let gate = RuntimeResidencyUnloadGate()
        let task = Task { [weak self] in
            await gate.waitUntilActivated()
            guard let self else { return }
            let execution = await self.performResidencyUnload(model, reason: reason)
            self.completeResidencyUnloadOperation(
                model: model,
                reason: reason,
                id: id,
                execution: execution
            )
            switch execution {
            case .succeeded:
                self.emit(.unloadSucceeded(provider: model.provider, modelID: model.modelID, reason: reason))
            case .failed(let message):
                self.emit(.unloadFailed(
                    provider: model.provider,
                    modelID: model.modelID,
                    reason: reason,
                    message: message
                ))
            }
        }
        let operation = RuntimeResidencyUnloadOperation(
            id: id,
            model: model,
            reason: reason,
            gate: gate,
            task: task
        )
        residencyUnloadOperations[model] = operation
        return operation
    }

    private func runResidencyUnloadOperation(
        _ operation: RuntimeResidencyUnloadOperation
    ) async {
        operation.gate.activate()
        await operation.task.value
    }

    private func completeResidencyUnloadOperation(
        model: RuntimeModelResidencyKey,
        reason: RuntimeModelResidencyUnloadReason,
        id: UUID,
        execution: RuntimeResidencyUnloadExecution
    ) {
        lock.withLock {
            guard residencyUnloadOperations[model]?.id == id else { return }
            residencyUnloadOperations[model] = nil

            switch execution {
            case .succeeded:
                if lastUnloadFailure?.provider == model.provider,
                   lastUnloadFailure?.modelID == model.modelID {
                    lastUnloadFailure = nil
                }
                if activeResidencyModel == model,
                   inFlightResidencyCounts[model, default: 0] == 0 {
                    activeResidencyModel = nil
                    idleResidencyStartedAtUptimeNanoseconds = nil
                    cancelIdleUnloadTaskLocked()
                }
            case .failed:
                lastUnloadFailure = RuntimeModelResidencyUnloadFailure(
                    provider: model.provider,
                    modelID: model.modelID,
                    reason: reason
                )
                if reason == .modelSwitch {
                    if activeResidencyModel == model,
                       inFlightResidencyCounts[model, default: 0] == 0 {
                        activeResidencyModel = nil
                        idleResidencyStartedAtUptimeNanoseconds = nil
                        cancelIdleUnloadTaskLocked()
                    }
                } else if activeResidencyModel == model,
                          inFlightResidencyCounts[model, default: 0] == 0 {
                    let now = DispatchTime.now().uptimeNanoseconds
                    idleResidencyStartedAtUptimeNanoseconds = now
                    if modelIdleUnloadDelayNanoseconds > 0 {
                        scheduleIdleUnloadTaskLocked(
                            for: model,
                            delayNanoseconds: modelIdleUnloadDelayNanoseconds
                        )
                    }
                }
            }
        }
    }

    private func performResidencyUnload(
        _ model: RuntimeModelResidencyKey,
        reason: RuntimeModelResidencyUnloadReason
    ) async -> RuntimeResidencyUnloadExecution {
        guard let backend = backendsByProvider[model.provider] else {
            return .failed(message: "The model provider is not enabled in AetherLink Runtime.")
        }
        emit(.unloadRequested(provider: model.provider, modelID: model.modelID, reason: reason))
        do {
            let result = try await backend.unloadModel(providerModelID: model.modelID)
            guard result.provider == model.provider,
                  result.modelID == model.modelID
            else {
                return .failed(message: "The model provider returned a mismatched unload confirmation.")
            }
            guard result.unloaded else {
                return .failed(message: result.message)
            }
            return .succeeded
        } catch {
            return .failed(message: error.localizedDescription)
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
        requiredKind: ModelKind = .chat,
        models: [ModelInfo]
    ) -> ModelInfo? {
        let requestedCanonical = canonicalModelName(requestedModel)
        let eligibleModels = models.filter { candidate in
            guard candidate.installed else { return false }
            guard candidate.source == .local else { return false }
            guard candidate.kind == requiredKind else { return false }
            guard isValidProviderModelID(candidate.providerModelID) else { return false }
            if let requestedProvider, candidate.provider != requestedProvider {
                return false
            }
            return true
        }
        if let exactMatch = eligibleModels.first(where: { candidate in
            let providerModelID = candidate.providerModelID
            return candidate.id == requestedModel
                || candidate.name == requestedModel
                || providerModelID == requestedModel
        }) {
            return exactMatch
        }
        return eligibleModels.first { candidate in
            let providerModelID = candidate.providerModelID
            return canonicalModelName(candidate.id) == requestedCanonical
                || canonicalModelName(candidate.name) == requestedCanonical
                || canonicalModelName(providerModelID) == requestedCanonical
        }
    }

    private static func matchingInstalledProviderModelID(
        _ providerModelID: String,
        provider: ModelProvider,
        requiredKind: ModelKind = .chat,
        models: [ModelInfo]
    ) -> ModelInfo? {
        models.first { candidate in
            candidate.installed &&
                candidate.source == .local &&
                candidate.kind == requiredKind &&
                candidate.provider == provider &&
                isValidProviderModelID(candidate.providerModelID) &&
                candidate.providerModelID == providerModelID
        }
    }

    private static func isValidProviderModelID(_ providerModelID: String) -> Bool {
        !providerModelID.isEmpty &&
            providerModelID == providerModelID.trimmingCharacters(in: .whitespacesAndNewlines) &&
            ModelProvider.splitQualifiedModelID(providerModelID) == nil
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
    public var unloadingProvider: ModelProvider?
    public var unloadingModelID: String?
    public var unloadingReason: RuntimeModelResidencyUnloadReason?
    public var lastUnloadFailure: RuntimeModelResidencyUnloadFailure?

    public init(
        activeProvider: ModelProvider?,
        activeModelID: String?,
        inFlightGenerations: Int,
        idleUnloadDelaySeconds: Int,
        unloadingProvider: ModelProvider? = nil,
        unloadingModelID: String? = nil,
        unloadingReason: RuntimeModelResidencyUnloadReason? = nil,
        lastUnloadFailure: RuntimeModelResidencyUnloadFailure? = nil
    ) {
        self.activeProvider = activeProvider
        self.activeModelID = activeModelID
        self.inFlightGenerations = inFlightGenerations
        self.idleUnloadDelaySeconds = idleUnloadDelaySeconds
        self.unloadingProvider = unloadingProvider
        self.unloadingModelID = unloadingModelID
        self.unloadingReason = unloadingReason
        self.lastUnloadFailure = lastUnloadFailure
    }
}

public enum RuntimeModelResidencyUnloadReason: String, Equatable, Sendable {
    case modelSwitch = "model_switch"
    case idleTimeout = "idle_timeout"
    case manual = "manual"
}

public enum RuntimeModelResidencyManualUnloadResult: Equatable, Sendable {
    case noActiveModel
    case inFlightGenerations(Int)
    case requested(provider: ModelProvider, modelID: String)
}

public struct RuntimeModelResidencyUnloadFailure: Equatable, Sendable {
    public var provider: ModelProvider
    public var modelID: String
    public var reason: RuntimeModelResidencyUnloadReason

    public init(
        provider: ModelProvider,
        modelID: String,
        reason: RuntimeModelResidencyUnloadReason
    ) {
        self.provider = provider
        self.modelID = modelID
        self.reason = reason
    }
}

public enum RuntimeModelResidencyEvent: Equatable, Sendable {
    case stateChanged
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
