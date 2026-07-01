import CompanionCore
import OllamaBackend
import XCTest

final class AggregatingLlmBackendResidencyTests: XCTestCase {
    func testSwitchingModelsUnloadsPreviousInactiveModel() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let lmStudio = ResidencyTestBackend(
            provider: .lmStudio,
            models: [ModelInfo(id: "gemma-local", name: "gemma-local", provider: .lmStudio)]
        )
        let backend = AggregatingLlmBackend(
            [ollama, lmStudio],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        _ = try await collect(backend.chat(request: chatRequest(model: "lm_studio:gemma-local")))

        await eventually {
            ollama.unloadedModels == ["qwen-local"]
        }
        XCTAssertTrue(lmStudio.unloadedModels.isEmpty)
    }

    func testRepeatedSameModelDoesNotUnloadBetweenChats() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))

        XCTAssertTrue(ollama.unloadedModels.isEmpty)
    }

    func testIdlePolicyUnloadsActiveModelAfterDelay() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 0
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))

        await eventually {
            ollama.unloadedModels == ["qwen-local"]
        }
    }

    func testDoneEventClearsInFlightResidencyBeforeClientObservesCompletion() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        var iterator = backend.chat(request: chatRequest(model: "ollama:qwen-local")).makeAsyncIterator()
        let event = try await iterator.next()

        XCTAssertEqual(event, .done(inputTokens: 1, outputTokens: 1))
        XCTAssertEqual(
            backend.modelResidencySnapshot(),
            RuntimeModelResidencySnapshot(
                activeProvider: .ollama,
                activeModelID: "qwen-local",
                inFlightGenerations: 0,
                idleUnloadDelaySeconds: 60
            )
        )
    }

    func testManualUnloadClearsActiveResidentModelAndEmitsManualEvent() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let events = ResidencyEventRecorder()
        backend.setResidencyEventHandler { event in
            events.append(event)
        }

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        await eventually {
            let snapshot = backend.modelResidencySnapshot()
            return snapshot.activeModelID == "qwen-local" && snapshot.inFlightGenerations == 0
        }

        let result = await backend.unloadActiveResidencyModelNow()

        XCTAssertEqual(result, .requested(provider: .ollama, modelID: "qwen-local"))
        await eventually {
            ollama.unloadedModels == ["qwen-local"] &&
                events.containsUnloadSuccess(provider: .ollama, modelID: "qwen-local", reason: .manual)
        }
        XCTAssertEqual(
            backend.modelResidencySnapshot(),
            RuntimeModelResidencySnapshot(
                activeProvider: nil,
                activeModelID: nil,
                inFlightGenerations: 0,
                idleUnloadDelaySeconds: 60
            )
        )
    }

    func testManualUnloadFailureKeepsStructuredManualFailureReason() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            unloadErrors: [
                "qwen-local": NSError(
                    domain: "AetherLinkResidencyTest",
                    code: 43,
                    userInfo: [NSLocalizedDescriptionKey: "manual unload denied"]
                )
            ]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let events = ResidencyEventRecorder()
        backend.setResidencyEventHandler { event in
            events.append(event)
        }

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        await eventually {
            let snapshot = backend.modelResidencySnapshot()
            return snapshot.activeModelID == "qwen-local" && snapshot.inFlightGenerations == 0
        }
        let result = await backend.unloadActiveResidencyModelNow()

        XCTAssertEqual(result, .requested(provider: .ollama, modelID: "qwen-local"))
        await eventually {
            events.containsUnloadFailure(
                provider: .ollama,
                modelID: "qwen-local",
                reason: .manual,
                message: "manual unload denied"
            )
        }
        XCTAssertEqual(
            backend.modelResidencySnapshot().lastUnloadFailure,
            RuntimeModelResidencyUnloadFailure(provider: .ollama, modelID: "qwen-local", reason: .manual)
        )
    }

    func testManualUnloadSkipsWhileGenerationIsInFlight() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsChatsOpen: true
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        let chatTask = Task {
            try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        }
        await eventually {
            backend.modelResidencySnapshot().inFlightGenerations == 1
        }

        let result = await backend.unloadActiveResidencyModelNow()

        XCTAssertEqual(result, .inFlightGenerations(1))
        XCTAssertTrue(ollama.unloadedModels.isEmpty)
        XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "qwen-local")
        chatTask.cancel()
        _ = await chatTask.result
    }

    func testUnloadFailureEmitsProviderSpecificFailureEventWithoutBreakingNextChat() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            unloadErrors: [
                "qwen-local": NSError(
                    domain: "AetherLinkResidencyTest",
                    code: 42,
                    userInfo: [NSLocalizedDescriptionKey: "unload denied"]
                )
            ]
        )
        let lmStudio = ResidencyTestBackend(
            provider: .lmStudio,
            models: [ModelInfo(id: "gemma-local", name: "gemma-local", provider: .lmStudio)]
        )
        let backend = AggregatingLlmBackend(
            [ollama, lmStudio],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let events = ResidencyEventRecorder()
        backend.setResidencyEventHandler { event in
            events.append(event)
        }

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        _ = try await collect(backend.chat(request: chatRequest(model: "lm_studio:gemma-local")))

        await eventually {
            events.containsUnloadFailure(
                provider: .ollama,
                modelID: "qwen-local",
                reason: .modelSwitch,
                message: "unload denied"
            )
        }
        XCTAssertEqual(ollama.unloadedModels, ["qwen-local"])
        XCTAssertEqual(lmStudio.routedModels, ["gemma-local"])
        XCTAssertEqual(
            backend.modelResidencySnapshot(),
            RuntimeModelResidencySnapshot(
                activeProvider: .lmStudio,
                activeModelID: "gemma-local",
                inFlightGenerations: 0,
                idleUnloadDelaySeconds: 60,
                lastUnloadFailure: RuntimeModelResidencyUnloadFailure(
                    provider: .ollama,
                    modelID: "qwen-local",
                    reason: .modelSwitch
                )
            )
        )
    }

    func testUnknownUnqualifiedModelDoesNotFallbackToOllama() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await collect(backend.chat(request: chatRequest(model: "synthetic-default")))
            XCTFail("Expected unknown model to be rejected")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .aggregate)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertFalse(error.retryable)
            XCTAssertTrue(ollama.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testQualifiedModelMustBeReportedByThatProvider() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let lmStudio = ResidencyTestBackend(
            provider: .lmStudio,
            models: [ModelInfo(id: "gemma-local", name: "gemma-local", provider: .lmStudio)]
        )
        let backend = AggregatingLlmBackend([ollama, lmStudio])

        do {
            _ = try await collect(backend.chat(request: chatRequest(model: "lm_studio:qwen-local")))
            XCTFail("Expected provider-mismatched model to be rejected")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .lmStudio)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertFalse(error.retryable)
            XCTAssertTrue(lmStudio.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testInstalledEmbeddingModelIsNotRoutedAsChat() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [
                ModelInfo(
                    id: "nomic-embed-text",
                    name: "nomic-embed-text",
                    provider: .ollama,
                    kind: .embedding
                )
            ]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await collect(backend.chat(request: chatRequest(model: "ollama:nomic-embed-text")))
            XCTFail("Expected embedding model to be rejected for chat routing")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .ollama)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertFalse(error.retryable)
            XCTAssertTrue(ollama.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testInstalledCloudChatModelIsNotRoutedAsChat() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [
                ModelInfo(
                    id: "deepseek-v4-pro:cloud",
                    name: "deepseek-v4-pro:cloud",
                    provider: .ollama,
                    installed: true,
                    source: .cloud,
                    remoteModel: "deepseek-v4-pro",
                    remoteHost: "https://ollama.com:443"
                )
            ]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await collect(backend.chat(request: chatRequest(model: "ollama:deepseek-v4-pro:cloud")))
            XCTFail("Expected cloud model to be rejected for chat routing")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .ollama)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertFalse(error.retryable)
            XCTAssertTrue(ollama.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testDuplicateProviderBackendsKeepFirstProviderInsteadOfCrashing() async throws {
        let primaryOllama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let duplicateOllama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "shadow-local", name: "shadow-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend([primaryOllama, duplicateOllama])

        let models = try await backend.listModels()
        XCTAssertEqual(models.map(\.id), ["qwen-local"])

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))

        XCTAssertEqual(primaryOllama.routedModels, ["qwen-local"])
        XCTAssertTrue(duplicateOllama.routedModels.isEmpty)
    }

    private func chatRequest(model: String) -> ChatRequest {
        ChatRequest(
            generationID: UUID().uuidString,
            sessionID: "session-1",
            model: model,
            messages: [ChatMessage(role: "user", content: "Hi")]
        )
    }

    private func collect(_ stream: AsyncThrowingStream<ChatStreamEvent, Error>) async throws -> [ChatStreamEvent] {
        var events: [ChatStreamEvent] = []
        for try await event in stream {
            events.append(event)
        }
        return events
    }

    private func eventually(
        timeoutNanoseconds: UInt64 = 500_000_000,
        _ condition: @escaping () -> Bool
    ) async {
        let step: UInt64 = 10_000_000
        var waited: UInt64 = 0
        while waited <= timeoutNanoseconds {
            if condition() {
                return
            }
            try? await Task.sleep(nanoseconds: step)
            waited += step
        }
        XCTFail("Condition was not met before timeout.")
    }
}

private final class ResidencyTestBackend: LlmBackend, @unchecked Sendable {
    let provider: ModelProvider

    private let lock = NSLock()
    private let models: [ModelInfo]
    private let unloadErrors: [String: Error]
    private let holdsChatsOpen: Bool
    private var unloaded: [String] = []
    private var routed: [String] = []

    var unloadedModels: [String] {
        lock.withLock { unloaded }
    }

    var routedModels: [String] {
        lock.withLock { routed }
    }

    init(
        provider: ModelProvider,
        models: [ModelInfo] = [],
        unloadErrors: [String: Error] = [:],
        holdsChatsOpen: Bool = false
    ) {
        self.provider = provider
        self.models = models
        self.unloadErrors = unloadErrors
        self.holdsChatsOpen = holdsChatsOpen
    }

    func healthCheck() async -> BackendStatus {
        .available
    }

    func listModels() async throws -> [ModelInfo] {
        models
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            lock.withLock {
                routed.append(request.model)
            }
            guard !holdsChatsOpen else {
                return
            }
            continuation.yield(.done(inputTokens: 1, outputTokens: 1))
            continuation.finish()
        }
    }

    func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        lock.withLock {
            unloaded.append(providerModelID)
        }
        if let error = unloadErrors[providerModelID] {
            throw error
        }
        return .unloaded(provider: provider, modelID: providerModelID)
    }

    @discardableResult
    func cancel(generationID: String) -> GenerationCancellationResult {
        .notFound(generationID: generationID)
    }
}

private final class ResidencyEventRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var events: [RuntimeModelResidencyEvent] = []

    func append(_ event: RuntimeModelResidencyEvent) {
        lock.withLock {
            events.append(event)
        }
    }

    func containsUnloadSuccess(
        provider: ModelProvider,
        modelID: String,
        reason: RuntimeModelResidencyUnloadReason
    ) -> Bool {
        lock.withLock {
            events.contains { event in
                if case let .unloadSucceeded(eventProvider, eventModelID, eventReason) = event {
                    return eventProvider == provider &&
                        eventModelID == modelID &&
                        eventReason == reason
                }
                return false
            }
        }
    }

    func containsUnloadFailure(
        provider: ModelProvider,
        modelID: String,
        reason: RuntimeModelResidencyUnloadReason,
        message: String
    ) -> Bool {
        lock.withLock {
            events.contains { event in
                if case let .unloadFailed(eventProvider, eventModelID, eventReason, eventMessage) = event {
                    return eventProvider == provider &&
                        eventModelID == modelID &&
                        eventReason == reason &&
                        eventMessage == message
                }
                return false
            }
        }
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
