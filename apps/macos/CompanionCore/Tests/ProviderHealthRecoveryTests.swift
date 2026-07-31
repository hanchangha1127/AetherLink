@testable import CompanionCore
import Foundation
import OllamaBackend
import Transport
import XCTest

@MainActor
final class ProviderHealthRecoveryTests: XCTestCase {
    private var defaultsSuiteNames: [String] = []

    override func tearDown() {
        for suiteName in defaultsSuiteNames {
            UserDefaults(suiteName: suiteName)?
                .removePersistentDomain(forName: suiteName)
        }
        defaultsSuiteNames.removeAll()
        super.tearDown()
    }

    func testRetryableProviderRecoversAutomaticallyWithCappedBackoff() async {
        let unavailable = retryableUnavailable(.ollama)
        let ollama = ScriptedProviderHealthBackend(
            provider: .ollama,
            statuses: [
                .unavailable(unavailable),
                .unavailable(unavailable),
                .unavailable(unavailable),
                .available,
            ]
        )
        let lmStudio = ScriptedProviderHealthBackend(
            provider: .lmStudio,
            statuses: [.available]
        )
        let sleeper = ControlledProviderRecoverySleeper()
        let model = makeModel(
            backend: AggregatingLlmBackend([ollama, lmStudio]),
            retryDelays: [10, 20],
            sleeper: sleeper
        )
        defer {
            sleeper.resumeAll()
            ollama.releaseHeldHealthChecks()
            lmStudio.releaseHeldHealthChecks()
            model.stop()
        }

        model.start(port: 43_230)
        await assertEventually {
            self.availability(of: .ollama, in: model) == .unavailable
                && self.availability(of: .lmStudio, in: model) == .available
                && sleeper.pendingCount == 1
        }
        XCTAssertEqual(ollama.healthCheckCallCount, 1)
        XCTAssertEqual(lmStudio.healthCheckCallCount, 1)
        XCTAssertEqual(sleeper.requestedDelays, [10])

        XCTAssertTrue(sleeper.resumeNext())
        await assertEventually {
            ollama.healthCheckCallCount == 2
                && sleeper.pendingCount == 1
        }
        XCTAssertEqual(sleeper.requestedDelays, [10, 20])

        XCTAssertTrue(sleeper.resumeNext())
        await assertEventually {
            ollama.healthCheckCallCount == 3
                && sleeper.pendingCount == 1
        }
        XCTAssertEqual(sleeper.requestedDelays, [10, 20, 20])

        XCTAssertTrue(sleeper.resumeNext())
        await assertEventually {
            self.availability(of: .ollama, in: model) == .available
                && sleeper.pendingCount == 0
        }
        XCTAssertEqual(ollama.healthCheckCallCount, 4)
        XCTAssertEqual(lmStudio.healthCheckCallCount, 1)
        XCTAssertEqual(
            model.logs.filter { $0 == unavailable.message }.count,
            1
        )
        XCTAssertEqual(
            model.logs.filter { $0 == "Ollama health check passed" }.count,
            1
        )
    }

    func testRecoveryChecksOnlyTheUnavailableLMStudioProvider() async {
        let unavailable = retryableUnavailable(.lmStudio)
        let ollama = ScriptedProviderHealthBackend(
            provider: .ollama,
            statuses: [.available]
        )
        let lmStudio = ScriptedProviderHealthBackend(
            provider: .lmStudio,
            statuses: [.unavailable(unavailable), .available]
        )
        let sleeper = ControlledProviderRecoverySleeper()
        let model = makeModel(
            backend: AggregatingLlmBackend([ollama, lmStudio]),
            retryDelays: [10],
            sleeper: sleeper
        )
        defer {
            sleeper.resumeAll()
            model.stop()
        }

        model.start(port: 43_231)
        await assertEventually {
            self.availability(of: .lmStudio, in: model) == .unavailable
                && sleeper.pendingCount == 1
        }
        XCTAssertTrue(sleeper.resumeNext())
        await assertEventually {
            self.availability(of: .lmStudio, in: model) == .available
        }

        XCTAssertEqual(ollama.healthCheckCallCount, 1)
        XCTAssertEqual(lmStudio.healthCheckCallCount, 2)
        XCTAssertEqual(ollama.modelListCallCount, 0)
        XCTAssertEqual(lmStudio.modelListCallCount, 0)
    }

    func testNonRetryableProviderFailureDoesNotScheduleRecovery() async {
        let error = BackendError(
            provider: .ollama,
            code: "bad_backend_response",
            message: "The provider response is invalid.",
            retryable: false
        )
        let backend = ScriptedProviderHealthBackend(
            provider: .ollama,
            statuses: [.unavailable(error)]
        )
        let sleeper = ControlledProviderRecoverySleeper()
        let model = makeModel(
            backend: backend,
            retryDelays: [10],
            sleeper: sleeper
        )
        defer {
            sleeper.resumeAll()
            model.stop()
        }

        model.start(port: 43_232)
        await assertEventually {
            self.availability(of: .ollama, in: model) == .unavailable
        }
        await Task.yield()
        await Task.yield()

        XCTAssertEqual(backend.healthCheckCallCount, 1)
        XCTAssertTrue(sleeper.requestedDelays.isEmpty)
        XCTAssertEqual(sleeper.pendingCount, 0)
    }

    func testSleepCancelsRecoveryAndWakeStartsFreshImmediateProbe() async {
        let unavailable = retryableUnavailable(.ollama)
        let backend = ScriptedProviderHealthBackend(
            provider: .ollama,
            statuses: [.unavailable(unavailable), .available]
        )
        let sleeper = ControlledProviderRecoverySleeper()
        let model = makeModel(
            backend: backend,
            retryDelays: [10],
            sleeper: sleeper
        )
        defer {
            sleeper.resumeAll()
            model.stop()
        }

        model.start(port: 43_233)
        await assertEventually {
            self.availability(of: .ollama, in: model) == .unavailable
                && sleeper.pendingCount == 1
        }

        XCTAssertTrue(model.suspendForSystemSleep())
        await assertEventually { sleeper.pendingCount == 0 }
        XCTAssertEqual(backend.healthCheckCallCount, 1)

        XCTAssertTrue(model.resumeAfterSystemWake())
        await assertEventually {
            self.availability(of: .ollama, in: model) == .available
        }
        XCTAssertEqual(backend.healthCheckCallCount, 2)
        XCTAssertEqual(sleeper.pendingCount, 0)
    }

    func testStopRejectsCancellationResistantLateRecoveryResult() async {
        let unavailable = retryableUnavailable(.ollama)
        let backend = ScriptedProviderHealthBackend(
            provider: .ollama,
            statuses: [.unavailable(unavailable), .available],
            heldHealthCheckOrdinals: [2]
        )
        let sleeper = ControlledProviderRecoverySleeper()
        let model = makeModel(
            backend: backend,
            retryDelays: [10],
            sleeper: sleeper
        )
        defer {
            sleeper.resumeAll()
            backend.releaseHeldHealthChecks()
            model.stop()
        }

        model.start(port: 43_234)
        await assertEventually {
            self.availability(of: .ollama, in: model) == .unavailable
                && sleeper.pendingCount == 1
        }
        XCTAssertTrue(sleeper.resumeNext())
        await assertEventually {
            backend.healthCheckCallCount == 2
                && backend.heldHealthCheckCount == 1
        }

        model.stop()
        backend.releaseHeldHealthChecks()
        await assertEventually {
            backend.heldHealthCheckCount == 0
        }
        await Task.yield()
        await Task.yield()

        XCTAssertEqual(
            availability(of: .ollama, in: model),
            .unavailable
        )
        XCTAssertEqual(backend.healthCheckCallCount, 2)
    }

    func testDeinitCancelsRecoverySleeperWithoutRetainingModel() async {
        let unavailable = retryableUnavailable(.ollama)
        let backend = ScriptedProviderHealthBackend(
            provider: .ollama,
            statuses: [.unavailable(unavailable)]
        )
        let sleeper = ControlledProviderRecoverySleeper()
        weak var releasedModel: CompanionAppModel?
        var model: CompanionAppModel? = makeModel(
            backend: backend,
            retryDelays: [10],
            sleeper: sleeper
        )
        releasedModel = model

        model?.start(port: 43_236)
        await assertEventually {
            self.availability(of: .ollama, in: model!) == .unavailable
                && sleeper.pendingCount == 1
        }

        model = nil
        await assertEventually {
            releasedModel == nil && sleeper.pendingCount == 0
        }

        XCTAssertEqual(backend.healthCheckCallCount, 1)
    }

    func testConcurrentManualRefreshesJoinOneProviderProbe() async {
        let backend = ScriptedProviderHealthBackend(
            provider: .ollama,
            statuses: [.available],
            heldHealthCheckOrdinals: [1]
        )
        let model = makeModel(
            backend: backend,
            retryDelays: [],
            sleeper: ControlledProviderRecoverySleeper()
        )
        defer {
            backend.releaseHeldHealthChecks()
            model.stop()
        }

        let first = Task { await model.refreshBackendStatus() }
        await assertEventually {
            backend.healthCheckCallCount == 1
                && backend.heldHealthCheckCount == 1
        }
        let second = Task { await model.refreshBackendStatus() }
        await Task.yield()
        await Task.yield()

        XCTAssertEqual(backend.healthCheckCallCount, 1)
        XCTAssertEqual(backend.maximumConcurrentHealthChecks, 1)
        backend.releaseHeldHealthChecks()
        await first.value
        await second.value

        XCTAssertEqual(availability(of: .ollama, in: model), .available)
        XCTAssertEqual(backend.healthCheckCallCount, 1)
    }

    func testSlowProviderDoesNotBlockOtherProviderPublication() async {
        let ollama = ScriptedProviderHealthBackend(
            provider: .ollama,
            statuses: [.available],
            heldHealthCheckOrdinals: [1]
        )
        let lmStudio = ScriptedProviderHealthBackend(
            provider: .lmStudio,
            statuses: [.available]
        )
        let model = makeModel(
            backend: AggregatingLlmBackend([ollama, lmStudio]),
            retryDelays: [],
            sleeper: ControlledProviderRecoverySleeper()
        )
        defer {
            ollama.releaseHeldHealthChecks()
            model.stop()
        }

        model.start(port: 43_235)
        await assertEventually {
            ollama.heldHealthCheckCount == 1
                && self.availability(of: .lmStudio, in: model) == .available
        }
        XCTAssertEqual(
            availability(of: .ollama, in: model),
            .notChecked
        )

        ollama.releaseHeldHealthChecks()
        await assertEventually {
            self.availability(of: .ollama, in: model) == .available
        }
        XCTAssertEqual(ollama.healthCheckCallCount, 1)
        XCTAssertEqual(lmStudio.healthCheckCallCount, 1)
    }

    private func makeModel(
        backend: any LlmBackend,
        retryDelays: [UInt64],
        sleeper: ControlledProviderRecoverySleeper
    ) -> CompanionAppModel {
        let suiteName = "ProviderHealthRecoveryTests.\(UUID().uuidString)"
        defaultsSuiteNames.append(suiteName)
        let defaults = UserDefaults(suiteName: suiteName)!
        defaults.removePersistentDomain(forName: suiteName)
        return CompanionAppModel(
            backend: backend,
            peerServer: RecoveryRuntimeTransport(),
            advertiser: RecoveryRuntimeAdvertiser(),
            environment: [:],
            userDefaults: defaults,
            relaySecretStore: InMemoryRecoveryRelaySecretStore(),
            providerRecoveryRetryDelaysNanoseconds: retryDelays,
            providerRecoverySleeper: { delay in
                try await sleeper.sleep(delay)
            }
        )
    }

    private func availability(
        of provider: ModelProvider,
        in model: CompanionAppModel
    ) -> CompanionProviderStatus.Availability? {
        model.providerStatuses.first {
            $0.provider == provider
        }?.availability
    }

    private func retryableUnavailable(
        _ provider: ModelProvider
    ) -> BackendError {
        BackendError(
            provider: provider,
            code: "backend_unavailable",
            message: "\(provider.displayName) is temporarily unavailable.",
            retryable: true
        )
    }

    private func waitUntil(
        timeout: TimeInterval = 2,
        condition: @escaping @MainActor () -> Bool
    ) async -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if condition() {
                return true
            }
            try? await Task.sleep(nanoseconds: 1_000_000)
        }
        return condition()
    }

    private func assertEventually(
        timeout: TimeInterval = 2,
        file: StaticString = #filePath,
        line: UInt = #line,
        condition: @escaping @MainActor () -> Bool
    ) async {
        let matched = await waitUntil(
            timeout: timeout,
            condition: condition
        )
        XCTAssertTrue(matched, file: file, line: line)
    }
}

private final class ScriptedProviderHealthBackend:
    LlmBackend,
    @unchecked Sendable
{
    let provider: ModelProvider

    private let lock = NSLock()
    private var statuses: [BackendStatus]
    private let fallbackStatus: BackendStatus
    private let heldHealthCheckOrdinals: Set<Int>
    private var heldHealthCheckContinuations: [
        CheckedContinuation<Void, Never>
    ] = []
    private var healthCheckCalls = 0
    private var activeHealthChecks = 0
    private var maximumActiveHealthChecks = 0
    private var modelListCalls = 0

    init(
        provider: ModelProvider,
        statuses: [BackendStatus],
        heldHealthCheckOrdinals: Set<Int> = []
    ) {
        self.provider = provider
        self.statuses = statuses
        self.fallbackStatus = statuses.last ?? .available
        self.heldHealthCheckOrdinals = heldHealthCheckOrdinals
    }

    var healthCheckCallCount: Int {
        withLock { healthCheckCalls }
    }

    var maximumConcurrentHealthChecks: Int {
        withLock { maximumActiveHealthChecks }
    }

    var heldHealthCheckCount: Int {
        withLock { heldHealthCheckContinuations.count }
    }

    var modelListCallCount: Int {
        withLock { modelListCalls }
    }

    func healthCheck() async -> BackendStatus {
        let (ordinal, status) = withLock {
            healthCheckCalls += 1
            activeHealthChecks += 1
            maximumActiveHealthChecks = max(
                maximumActiveHealthChecks,
                activeHealthChecks
            )
            let status = statuses.isEmpty
                ? fallbackStatus
                : statuses.removeFirst()
            return (healthCheckCalls, status)
        }
        defer {
            withLock {
                activeHealthChecks -= 1
            }
        }
        if heldHealthCheckOrdinals.contains(ordinal) {
            await withCheckedContinuation { continuation in
                withLock {
                    heldHealthCheckContinuations.append(continuation)
                }
            }
        }
        return status
    }

    func releaseHeldHealthChecks() {
        let continuations = withLock {
            let continuations = heldHealthCheckContinuations
            heldHealthCheckContinuations.removeAll()
            return continuations
        }
        continuations.forEach { $0.resume() }
    }

    func listModels() async throws -> [ModelInfo] {
        withLock {
            modelListCalls += 1
        }
        return []
    }

    func chat(
        request: ChatRequest
    ) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            continuation.yield(.done(inputTokens: 0, outputTokens: 0))
            continuation.finish()
        }
    }

    func embed(request: EmbeddingRequest) async throws -> EmbeddingResult {
        EmbeddingResult(
            model: request.model,
            embeddings: request.texts.map { _ in [0] }
        )
    }

    func unloadModel(
        providerModelID: String
    ) async throws -> ModelUnloadResult {
        .unsupported(provider: provider, modelID: providerModelID)
    }

    @discardableResult
    func cancel(generationID: String) -> GenerationCancellationResult {
        .notFound(generationID: generationID)
    }

    private func withLock<Result>(
        _ body: () -> Result
    ) -> Result {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }
}

private final class ControlledProviderRecoverySleeper:
    @unchecked Sendable
{
    private struct PendingSleep {
        let id: UUID
        let continuation: CheckedContinuation<Void, Error>
    }

    private let lock = NSLock()
    private var pendingSleeps: [PendingSleep] = []
    private var cancelledBeforeRegistration = Set<UUID>()
    private var delays: [UInt64] = []

    var pendingCount: Int {
        withLock { pendingSleeps.count }
    }

    var requestedDelays: [UInt64] {
        withLock { delays }
    }

    func sleep(_ delay: UInt64) async throws {
        try Task.checkCancellation()
        let sleepID = UUID()
        try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                let resumeCancelled = withLock {
                    delays.append(delay)
                    if cancelledBeforeRegistration.remove(sleepID) != nil {
                        return true
                    }
                    pendingSleeps.append(PendingSleep(
                        id: sleepID,
                        continuation: continuation
                    ))
                    return false
                }
                if resumeCancelled {
                    continuation.resume(throwing: CancellationError())
                }
            }
        } onCancel: {
            let continuation: CheckedContinuation<Void, Error>? = self.withLock {
                if let index = self.pendingSleeps.firstIndex(where: {
                    $0.id == sleepID
                }) {
                    return self.pendingSleeps.remove(at: index).continuation
                }
                self.cancelledBeforeRegistration.insert(sleepID)
                return nil
            }
            continuation?.resume(throwing: CancellationError())
        }
    }

    @discardableResult
    func resumeNext() -> Bool {
        let pending = withLock {
            pendingSleeps.isEmpty ? nil : pendingSleeps.removeFirst()
        }
        pending?.continuation.resume()
        return pending != nil
    }

    func resumeAll() {
        let pending = withLock {
            let pending = pendingSleeps
            pendingSleeps.removeAll()
            return pending
        }
        pending.forEach { $0.continuation.resume() }
    }

    private func withLock<Result>(
        _ body: () -> Result
    ) -> Result {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }
}

private final class RecoveryRuntimeTransport:
    RuntimeTransport,
    RuntimeStatusReporting
{
    private(set) var status: PeerServerStatus = .stopped
    var onStatusChange: (@Sendable (PeerServerStatus) -> Void)?

    func start(
        port: UInt16,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        status = .listening(port: port)
    }

    func stop() {
        status = .stopped
    }
}

private final class RecoveryRuntimeAdvertiser: RuntimeAdvertiser {
    func start(
        port: Int32,
        metadata: RuntimeAdvertisementMetadata
    ) {}

    func stop() {}
}

private final class InMemoryRecoveryRelaySecretStore:
    CompanionRelaySecretStoring,
    @unchecked Sendable
{
    private let lock = NSLock()
    private var secrets: [String: String] = [:]

    func saveSecret(_ secret: String, for handle: String) {
        withLock {
            secrets[handle] = secret
        }
    }

    func readSecret(for handle: String) -> String? {
        withLock { secrets[handle] }
    }

    func removeSecret(for handle: String) {
        withLock {
            secrets[handle] = nil
        }
    }

    private func withLock<Result>(
        _ body: () -> Result
    ) -> Result {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }
}
