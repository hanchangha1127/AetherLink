import CompanionCore
import OllamaBackend
import XCTest

final class AggregatingLlmBackendResidencyTests: XCTestCase {
    func testSwitchingModelsUnloadsPreviousInactiveModel() async throws {
        let ollama = ResidencyTestBackend(provider: .ollama)
        let lmStudio = ResidencyTestBackend(provider: .lmStudio)
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
        let ollama = ResidencyTestBackend(provider: .ollama)
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))

        XCTAssertTrue(ollama.unloadedModels.isEmpty)
    }

    func testIdlePolicyUnloadsActiveModelAfterDelay() async throws {
        let ollama = ResidencyTestBackend(provider: .ollama)
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 0
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))

        await eventually {
            ollama.unloadedModels == ["qwen-local"]
        }
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
    private var unloaded: [String] = []

    var unloadedModels: [String] {
        lock.withLock { unloaded }
    }

    init(provider: ModelProvider) {
        self.provider = provider
    }

    func healthCheck() async -> BackendStatus {
        .available
    }

    func listModels() async throws -> [ModelInfo] {
        []
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            continuation.yield(.done(inputTokens: 1, outputTokens: 1))
            continuation.finish()
        }
    }

    func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        lock.withLock {
            unloaded.append(providerModelID)
        }
        return .unloaded(provider: provider, modelID: providerModelID)
    }

    @discardableResult
    func cancel(generationID: String) -> GenerationCancellationResult {
        .notFound(generationID: generationID)
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
