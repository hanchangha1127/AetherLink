import Combine
import Foundation
import OllamaBackend
import Transport
import TrustedDevices
import XCTest
@testable import CompanionCore

@MainActor
final class CompanionModelPullApprovalTests: XCTestCase {
    func testInitialRefreshPublishesEmptyApprovalState() async throws {
        let fixture = try makeFixture()
        defer { fixture.remove() }

        await fixture.model.refreshModelPullApprovals()

        XCTAssertTrue(fixture.model.pendingModelPullReviews.isEmpty)
        XCTAssertTrue(fixture.model.modelPullAuditEvents.isEmpty)
        XCTAssertNil(fixture.model.modelPullApprovalErrorLocalizationKey)
        XCTAssertFalse(fixture.model.isModelPullDecisionInFlight)
    }

    func testRefreshPublishesDirectlySeededAuditWithoutInventingPendingReview() async throws {
        let fixture = try makeFixture()
        defer { fixture.remove() }
        await fixture.model.refreshModelPullApprovals()

        let operationID = "00000000-0000-4000-8000-000000000101"
        let requestedAt = Date(timeIntervalSince1970: 100)
        _ = try fixture.approvalStore.createRequest(
            operationID: operationID,
            requestBindingDigest: requestBindingDigest("a"),
            provider: .ollama,
            requestedAt: requestedAt,
            expiresAt: Date(timeIntervalSince1970: 300)
        )
        _ = try fixture.approvalStore.recordTerminal(
            operationID: operationID,
            event: .dismissal,
            at: Date(timeIntervalSince1970: 200)
        )

        await fixture.model.refreshModelPullApprovals()

        XCTAssertTrue(fixture.model.pendingModelPullReviews.isEmpty)
        XCTAssertEqual(fixture.model.modelPullAuditEvents.map(\.operationID), [operationID, operationID])
        XCTAssertEqual(fixture.model.modelPullAuditEvents.map(\.event), ["dismissal", "requested"])
        XCTAssertEqual(fixture.model.modelPullAuditEvents.map(\.provider), [.ollama, .ollama])
        XCTAssertNil(fixture.model.modelPullApprovalErrorLocalizationKey)
    }

    func testUnknownReviewDecisionsPublishErrorsAndResetInFlightState() async throws {
        let fixture = try makeFixture()
        defer { fixture.remove() }
        await fixture.model.refreshModelPullApprovals()
        let expectedError = RuntimeModelPullApprovalBrokerError.reviewNotFound.localizationKey
        var publishedErrors: [String] = []
        let errorObservation = fixture.model.$modelPullApprovalErrorLocalizationKey
            .compactMap { $0 }
            .sink { publishedErrors.append($0) }
        var decisionStates: [Bool] = []
        let decisionObservation = fixture.model.$isModelPullDecisionInFlight
            .dropFirst()
            .sink { decisionStates.append($0) }
        defer {
            errorObservation.cancel()
            decisionObservation.cancel()
        }

        await fixture.model.approveModelPull(operationID: "unknown-approval")

        XCTAssertTrue(publishedErrors.contains(expectedError))
        XCTAssertEqual(decisionStates, [true, false])
        XCTAssertFalse(fixture.model.isModelPullDecisionInFlight)
        XCTAssertTrue(fixture.model.pendingModelPullReviews.isEmpty)
        XCTAssertTrue(fixture.backend.calls.isEmpty)

        publishedErrors.removeAll()
        decisionStates.removeAll()
        await fixture.model.dismissModelPull(operationID: "unknown-dismissal")

        XCTAssertTrue(publishedErrors.contains(expectedError))
        XCTAssertEqual(decisionStates, [true, false])
        XCTAssertFalse(fixture.model.isModelPullDecisionInFlight)
        XCTAssertTrue(fixture.model.pendingModelPullReviews.isEmpty)
        XCTAssertTrue(fixture.backend.calls.isEmpty)
    }

    func testProductionInitializationDoesNotDispatchProviderWork() async throws {
        let fixture = try makeFixture()
        defer { fixture.remove() }

        for _ in 0..<20 {
            await Task.yield()
        }

        XCTAssertEqual(fixture.model.providerStatuses.map(\.provider), [.ollama])
        XCTAssertTrue(fixture.model.pendingModelPullReviews.isEmpty)
        XCTAssertTrue(fixture.model.modelPullAuditEvents.isEmpty)
        XCTAssertTrue(fixture.backend.calls.isEmpty)
    }

    func testFailedStartupRecoveryPublishesLocalizedStorageErrorKey() async throws {
        let persistence = FailingRecoveryModelPullPersistence()
        let fixture = try makeFixture(persistence: persistence)
        defer { fixture.remove() }

        for _ in 0..<200
            where fixture.model.modelPullApprovalErrorLocalizationKey == nil
        {
            await Task.yield()
        }

        XCTAssertEqual(
            fixture.model.modelPullApprovalErrorLocalizationKey,
            RuntimeModelPullApprovalBrokerError.storageUnavailable.localizationKey
        )
        XCTAssertEqual(persistence.recoveryCallCount, 2)
        XCTAssertTrue(fixture.model.pendingModelPullReviews.isEmpty)
        XCTAssertTrue(fixture.backend.calls.isEmpty)
    }

    private func makeFixture(
        persistence: (any RuntimeModelPullBrokerPersistence)? = nil
    ) throws -> ModelPullFixture {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("CompanionModelPullApprovalTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        let defaultsSuiteName = "dev.aetherlink.model-pull-tests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: defaultsSuiteName))
        defaults.removePersistentDomain(forName: defaultsSuiteName)
        let backend = RecordingModelPullBackend()
        let approvalStore = SQLiteRuntimeModelPullApprovalStore(
            databaseURL: directoryURL.appendingPathComponent("model-pull-approvals.sqlite")
        )
        let model = CompanionAppModel(
            backend: backend,
            peerServer: NoOpRuntimeTransport(),
            advertiser: NoOpRuntimeAdvertiser(),
            relayClient: NoOpRelayPeerTransport(),
            pairedRelayClientFactory: { NoOpRelayPeerTransport() },
            environment: [
                "AETHERLINK_RUNTIME_IDENTITY_FILE": directoryURL
                    .appendingPathComponent("runtime-identity.json").path,
            ],
            userDefaults: defaults,
            relaySecretStore: InMemoryRelaySecretStore(),
            trustedDeviceStore: TrustedDeviceStore(
                fileURL: directoryURL.appendingPathComponent("trusted-devices.json")
            ),
            runtimeChatEventStore: JSONLRuntimeChatEventStore(
                fileURL: directoryURL.appendingPathComponent("chat-events.jsonl")
            ),
            runtimeChatCompactionSummaryCache: SQLiteRuntimeChatCompactionSummaryCache(
                databaseURL: directoryURL.appendingPathComponent("chat-compaction.sqlite")
            ),
            runtimeMemoryStore: JSONLRuntimeMemoryStore(
                fileURL: directoryURL.appendingPathComponent("memory-events.jsonl")
            ),
            runtimeDocumentIndexStore: SQLiteRuntimeDocumentIndexStore(
                databaseURL: directoryURL.appendingPathComponent("document-index.sqlite")
            ),
            runtimeModelPullApprovalPersistence: persistence ?? approvalStore,
            runtimeRouteHostProvider: { "127.0.0.1" }
        )
        return ModelPullFixture(
            directoryURL: directoryURL,
            defaultsSuiteName: defaultsSuiteName,
            model: model,
            backend: backend,
            approvalStore: approvalStore
        )
    }

    private func requestBindingDigest(_ marker: Character) -> String {
        SQLiteRuntimeModelPullApprovalStore.requestBindingDigestPrefix
            + String(repeating: marker, count: 64)
    }
}

private final class FailingRecoveryModelPullPersistence:
    RuntimeModelPullBrokerPersistence,
    @unchecked Sendable
{
    private let lock = NSLock()
    private var storedRecoveryCallCount = 0

    var recoveryCallCount: Int {
        lock.withLock { storedRecoveryCallCount }
    }

    func createPending(
        operationID: String,
        requestBindingDigest: String,
        provider: ModelProvider,
        actionID: String,
        policyRevision: String,
        requestedAt: Date,
        expiresAt: Date
    ) throws {
        throw RuntimeModelPullApprovalBrokerError.storageUnavailable
    }

    func reserveDispatchBeforeProvider(
        operationID: String,
        requestBindingDigest: String,
        at: Date
    ) throws -> RuntimeModelPullReservationPersistenceResult {
        throw RuntimeModelPullApprovalBrokerError.storageUnavailable
    }

    func recordTerminal(
        operationID: String,
        event: RuntimeModelPullPersistenceEventKind,
        at: Date
    ) throws -> RuntimeModelPullTerminalPersistenceResult {
        throw RuntimeModelPullApprovalBrokerError.storageUnavailable
    }

    func recoverUnfinishedApprovals(at: Date) throws {
        lock.withLock { storedRecoveryCallCount += 1 }
        throw RuntimeModelPullApprovalBrokerError.storageUnavailable
    }

    func recentAuditEvents(limit: Int) throws -> [RuntimeModelPullAuditSummary] {
        []
    }
}

private struct ModelPullFixture {
    let directoryURL: URL
    let defaultsSuiteName: String
    let model: CompanionAppModel
    let backend: RecordingModelPullBackend
    let approvalStore: SQLiteRuntimeModelPullApprovalStore

    func remove() {
        UserDefaults(suiteName: defaultsSuiteName)?.removePersistentDomain(forName: defaultsSuiteName)
        try? FileManager.default.removeItem(at: directoryURL)
    }
}

private final class RecordingModelPullBackend: LlmBackend, @unchecked Sendable {
    let provider = ModelProvider.ollama
    private let lock = NSLock()
    private var recordedCalls: [String] = []

    var calls: [String] {
        lock.withLock { recordedCalls }
    }

    func healthCheck() async -> BackendStatus {
        record("healthCheck")
        return .available
    }

    func listModels() async throws -> [ModelInfo] {
        record("listModels")
        return []
    }

    func pullModel(name: String) async throws -> ModelPullResult {
        record("pullModel")
        return ModelPullResult(model: name, status: "downloaded", installed: true)
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        record("chat")
        return AsyncThrowingStream { continuation in continuation.finish() }
    }

    func embed(request: EmbeddingRequest) async throws -> EmbeddingResult {
        record("embed")
        return EmbeddingResult(model: request.model, embeddings: [])
    }

    func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        record("unloadModel")
        return .unsupported(provider: provider, modelID: providerModelID)
    }

    func cancel(generationID: String) -> GenerationCancellationResult {
        record("cancel")
        return .notFound(generationID: generationID)
    }

    func takeProviderUsageSource(generationID: String) -> ChatProviderUsageSource? {
        record("takeProviderUsageSource")
        return nil
    }

    private func record(_ call: String) {
        lock.withLock { recordedCalls.append(call) }
    }
}

private final class NoOpRuntimeTransport: RuntimeTransport {
    var status = PeerServerStatus.stopped

    func start(port: UInt16, onMessage: @escaping LocalPeerMessageHandler) {
        status = .listening(port: port)
    }

    func stop() {
        status = .stopped
    }
}

private final class NoOpRuntimeAdvertiser: RuntimeAdvertiser {
    func start(port: Int32, metadata: RuntimeAdvertisementMetadata) {}
    func stop() {}
}

private final class NoOpRelayPeerTransport: RelayPeerTransport, @unchecked Sendable {
    func start(
        configuration: RelayPeerConfiguration,
        onStatusChange: (@Sendable (RelayPeerStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {}

    func stop() {}
}

private final class InMemoryRelaySecretStore: CompanionRelaySecretStoring, @unchecked Sendable {
    private let lock = NSLock()
    private var secrets: [String: String] = [:]

    func saveSecret(_ secret: String, for handle: String) {
        lock.withLock { secrets[handle] = secret }
    }

    func readSecret(for handle: String) -> String? {
        lock.withLock { secrets[handle] }
    }

    func removeSecret(for handle: String) {
        _ = lock.withLock { secrets.removeValue(forKey: handle) }
    }
}
