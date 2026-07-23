import BridgeProtocol
import Foundation
@_spi(ProductionRawEndpointOwnership)
@_spi(ProductionRawEndpointTesting) import Transport
import TrustedDevices
import XCTest
@testable import CompanionCore
@testable import P2PNATContracts

final class MacRuntimeProductionAcceptedSessionServiceTests: XCTestCase {
    @MainActor
    func testServiceAttachesAcceptedRawSessionAndRoutesThroughComposedChannel()
        async throws
    {
        let manager = makeManager()
        let service = makeService(connectionManager: manager)
        let accepted = ServiceAcceptedRawSession()
        let channelBox = ServiceLocked<ServiceComposedChannel?>(nil)
        let routed = ServiceLocked<[UUID]>([])
        let capability = makeCapability(channelBox: channelBox)
        let localEphemeralKey = P2PNATSessionEphemeralKey()

        try await service.acceptForTesting(
            accepted,
            localEphemeralKey: localEphemeralKey,
            beginAuthority: { capability },
            onMessage: { _, sink in
                routed.mutate { $0.append(sink.connectionID) }
            }
        )

        XCTAssertEqual(accepted.installCount, 1)
        await accepted.emit(Data([0x01]))
        XCTAssertEqual(channelBox.value()?.receivedBodies, [Data([0x01])])
        XCTAssertEqual(routed.value(), [accepted.connectionID])
        XCTAssertEqual(accepted.sink.closeCount, 0)
        XCTAssertFalse(localEphemeralKey.testOnlyRetainsPrivateKey)
        XCTAssertTrue(localEphemeralKey.testOnlyIsClosed)

        service.stop(connectionID: accepted.connectionID)
        XCTAssertEqual(channelBox.value()?.closeCount, 1)
        XCTAssertEqual(accepted.sink.closeCount, 1)
    }

    @MainActor
    func testAuthorityStartFailureClosesAcceptedEndpointWithoutInstallingHandler()
        async
    {
        let service = makeService(connectionManager: makeManager())
        let accepted = ServiceAcceptedRawSession()
        let localEphemeralKey = P2PNATSessionEphemeralKey()

        do {
            try await service.acceptForTesting(
                accepted,
                localEphemeralKey: localEphemeralKey,
                beginAuthority: { throw ServiceTestError.authorityUnavailable },
                onMessage: { _, _ in }
            )
            XCTFail("Expected authority failure")
        } catch {
            XCTAssertEqual(error as? ServiceTestError, .authorityUnavailable)
        }

        XCTAssertEqual(accepted.installCount, 0)
        XCTAssertEqual(accepted.sink.closeCount, 1)
        XCTAssertFalse(localEphemeralKey.testOnlyRetainsPrivateKey)
        XCTAssertTrue(localEphemeralKey.testOnlyIsClosed)
    }

    @MainActor
    func testRouteDescriptorMismatchClosesBeforeAuthorityStart() async {
        let service = makeService(connectionManager: makeManager())
        let accepted = ServiceAcceptedRawSession()
        let authorityStarts = ServiceLocked(0)
        let localEphemeralKey = P2PNATSessionEphemeralKey()
        let mismatched = RuntimeAcceptedRawRouteDescriptor.testing(
            generation: accepted.routeDescriptor.generation + 1
        )

        do {
            try await service.acceptForTesting(
                accepted,
                expectedRouteDescriptor: mismatched,
                localEphemeralKey: localEphemeralKey,
                beginAuthority: {
                    authorityStarts.mutate { $0 += 1 }
                    throw ServiceTestError.authorityUnavailable
                },
                onMessage: { _, _ in }
            )
            XCTFail("Expected route descriptor mismatch")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .acceptedRouteDescriptorMismatch
            )
        }

        XCTAssertEqual(authorityStarts.value(), 0)
        XCTAssertEqual(accepted.installCount, 0)
        XCTAssertEqual(accepted.sink.closeCount, 1)
        XCTAssertFalse(localEphemeralKey.testOnlyRetainsPrivateKey)
        XCTAssertTrue(localEphemeralKey.testOnlyIsClosed)
    }

    @MainActor
    func testCancellationClosesPreparedEndpointAndUntransferredKeyPromptly()
        async
    {
        let service = makeService(connectionManager: makeManager())
        let accepted = ServiceAcceptedRawSession()
        let localEphemeralKey = P2PNATSessionEphemeralKey()
        let gate = ServiceAuthorityGate()
        let capability = makeCapability()

        let task = Task {
            try await service.acceptForTesting(
                accepted,
                localEphemeralKey: localEphemeralKey,
                beginAuthority: {
                    await gate.suspend()
                    try Task.checkCancellation()
                    return capability
                },
                onMessage: { _, _ in }
            )
        }
        await gate.waitUntilEntered()

        task.cancel()
        let closedPromptly = await waitUntil {
            localEphemeralKey.testOnlyIsClosed
                && accepted.sink.closeCount == 1
        }
        XCTAssertTrue(closedPromptly)
        XCTAssertFalse(localEphemeralKey.testOnlyRetainsPrivateKey)
        XCTAssertEqual(accepted.installCount, 0)

        await gate.release()
        do {
            try await task.value
            XCTFail("Expected cancellation")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }
    }

    @MainActor
    func testTargetedStopInvalidatesSuspendedAuthorityBeforeAttachment()
        async throws
    {
        let manager = makeManager()
        let service = makeService(connectionManager: manager)
        let connectionID = UUID()
        let accepted = ServiceAcceptedRawSession(connectionID: connectionID)
        let fresh = ServiceAcceptedRawSession(connectionID: connectionID)
        let localEphemeralKey = P2PNATSessionEphemeralKey()
        let gate = ServiceAuthorityGate()
        let abandonCount = ServiceLocked(0)
        let channelBox = ServiceLocked<ServiceComposedChannel?>(nil)
        let freshChannel = ServiceLocked<ServiceComposedChannel?>(nil)
        let capability = makeCapability(
            channelBox: channelBox,
            abandonCount: abandonCount
        )
        let freshCapability = makeCapability(channelBox: freshChannel)

        let task = Task {
            try await service.acceptForTesting(
                accepted,
                localEphemeralKey: localEphemeralKey,
                beginAuthority: {
                    await gate.suspend()
                    return capability
                },
                onMessage: { _, _ in }
            )
        }
        await gate.waitUntilEntered()

        service.stop(connectionID: accepted.connectionID)
        XCTAssertEqual(accepted.sink.closeCount, 1)
        XCTAssertEqual(accepted.installCount, 0)
        XCTAssertFalse(localEphemeralKey.testOnlyRetainsPrivateKey)
        XCTAssertTrue(localEphemeralKey.testOnlyIsClosed)
        XCTAssertEqual(abandonCount.value(), 0)

        try await service.acceptForTesting(
            fresh,
            beginAuthority: { freshCapability },
            onMessage: { _, _ in }
        )
        XCTAssertEqual(fresh.installCount, 1)
        XCTAssertEqual(fresh.sink.closeCount, 0)

        await gate.release()
        do {
            try await task.value
            XCTFail("Expected stopped pre-attachment attempt to fail")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .attachmentCancelled
            )
        }

        XCTAssertNil(channelBox.value())
        XCTAssertEqual(abandonCount.value(), 1)
        XCTAssertEqual(accepted.installCount, 0)
        XCTAssertEqual(accepted.sink.closeCount, 1)
        XCTAssertEqual(freshChannel.value()?.closeCount, 0)
        await fresh.emit(Data([0x30]))
        XCTAssertEqual(freshChannel.value()?.receivedBodies, [Data([0x30])])

        service.stop(connectionID: connectionID)
    }

    @MainActor
    func testStopAllRejectsLateAuthorityWithoutDisturbingFreshGeneration()
        async throws
    {
        let manager = makeManager()
        let service = makeService(connectionManager: manager)
        let connectionID = UUID()
        let stale = ServiceAcceptedRawSession(connectionID: connectionID)
        let fresh = ServiceAcceptedRawSession(connectionID: connectionID)
        let staleKey = P2PNATSessionEphemeralKey()
        let staleGate = ServiceAuthorityGate()
        let staleAbandonCount = ServiceLocked(0)
        let staleChannel = ServiceLocked<ServiceComposedChannel?>(nil)
        let freshChannel = ServiceLocked<ServiceComposedChannel?>(nil)
        let staleCapability = makeCapability(
            channelBox: staleChannel,
            abandonCount: staleAbandonCount
        )
        let freshCapability = makeCapability(channelBox: freshChannel)

        let staleTask = Task {
            try await service.acceptForTesting(
                stale,
                localEphemeralKey: staleKey,
                beginAuthority: {
                    await staleGate.suspend()
                    return staleCapability
                },
                onMessage: { _, _ in }
            )
        }
        await staleGate.waitUntilEntered()

        service.stopAll()
        XCTAssertEqual(stale.sink.closeCount, 1)
        XCTAssertEqual(stale.installCount, 0)
        XCTAssertFalse(staleKey.testOnlyRetainsPrivateKey)
        XCTAssertTrue(staleKey.testOnlyIsClosed)

        try await service.acceptForTesting(
            fresh,
            beginAuthority: { freshCapability },
            onMessage: { _, _ in }
        )
        XCTAssertEqual(fresh.installCount, 1)
        XCTAssertEqual(fresh.sink.closeCount, 0)

        await staleGate.release()
        do {
            try await staleTask.value
            XCTFail("Expected stale stop-all generation to fail")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .attachmentCancelled
            )
        }

        XCTAssertNil(staleChannel.value())
        XCTAssertEqual(staleAbandonCount.value(), 1)
        XCTAssertEqual(stale.installCount, 0)
        XCTAssertEqual(stale.sink.closeCount, 1)
        XCTAssertEqual(freshChannel.value()?.closeCount, 0)
        await fresh.emit(Data([0x31]))
        XCTAssertEqual(freshChannel.value()?.receivedBodies, [Data([0x31])])

        service.stop(connectionID: connectionID)
    }

    func testExpectedRouteDescriptorRejectsEveryFieldMismatch() {
        let base = RuntimeAcceptedRawRouteDescriptor.testing()
        let expected = MacRuntimeProductionExpectedRouteDescriptor(testing: base)
        XCTAssertTrue(expected.matches(base))

        let mismatches: [RuntimeAcceptedRawRouteDescriptor] = [
            .testing(sessionID: String(repeating: "a", count: 32)),
            .testing(object7And26BindingDigest: String(repeating: "b", count: 64)),
            .testing(routeKind: "turn_relay"),
            .testing(pairBindingDigest: String(repeating: "c", count: 64)),
            .testing(pairEpoch: 2),
            .testing(generation: 2),
            .testing(clientIdentityFingerprint: String(repeating: "d", count: 64)),
            .testing(runtimeIdentityFingerprint: String(repeating: "e", count: 64)),
            .testing(connectorInputCommitmentDigest: String(repeating: "f", count: 64)),
            .testing(effectiveNotBeforeMs: 0),
            .testing(expiresAtMs: 3),
        ]

        for descriptor in mismatches {
            XCTAssertFalse(expected.matches(descriptor))
        }
    }

    @MainActor
    func testDuplicateConnectionFailsClosedWithoutDisplacingActiveGeneration()
        async throws
    {
        let manager = makeManager()
        let service = makeService(connectionManager: manager)
        let connectionID = UUID()
        let active = ServiceAcceptedRawSession(connectionID: connectionID)
        let duplicate = ServiceAcceptedRawSession(connectionID: connectionID)
        let activeChannel = ServiceLocked<ServiceComposedChannel?>(nil)
        let duplicateAbandonCount = ServiceLocked(0)
        let activeCapability = makeCapability(channelBox: activeChannel)
        let duplicateCapability = makeCapability(
            abandonCount: duplicateAbandonCount
        )

        try await service.acceptForTesting(
            active,
            beginAuthority: { activeCapability },
            onMessage: { _, _ in }
        )

        do {
            try await service.acceptForTesting(
                duplicate,
                beginAuthority: { duplicateCapability },
                onMessage: { _, _ in }
            )
            XCTFail("Expected duplicate rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .duplicateAcceptedSession
            )
        }

        XCTAssertEqual(duplicate.installCount, 0)
        XCTAssertEqual(duplicate.sink.closeCount, 1)
        XCTAssertEqual(duplicateAbandonCount.value(), 1)
        XCTAssertEqual(activeChannel.value()?.closeCount, 0)
        await active.emit(Data([0x11]))
        XCTAssertEqual(activeChannel.value()?.receivedBodies, [Data([0x11])])
        service.stop(connectionID: connectionID)
    }

    @MainActor
    func testStopClaimsOldGenerationBeforeSameConnectionReplacement()
        async throws
    {
        let manager = makeManager()
        let service = makeService(connectionManager: manager)
        let connectionID = UUID()
        let first = ServiceAcceptedRawSession(connectionID: connectionID)
        let second = ServiceAcceptedRawSession(connectionID: connectionID)
        let firstChannel = ServiceLocked<ServiceComposedChannel?>(nil)
        let secondChannel = ServiceLocked<ServiceComposedChannel?>(nil)
        let firstCapability = makeCapability(channelBox: firstChannel)
        let secondCapability = makeCapability(channelBox: secondChannel)

        try await service.acceptForTesting(
            first,
            beginAuthority: { firstCapability },
            onMessage: { _, _ in }
        )

        service.stop(connectionID: connectionID)
        XCTAssertEqual(firstChannel.value()?.closeCount, 1)
        XCTAssertEqual(first.sink.closeCount, 1)

        try await service.acceptForTesting(
            second,
            beginAuthority: { secondCapability },
            onMessage: { _, _ in }
        )
        XCTAssertEqual(second.installCount, 1)
        XCTAssertEqual(second.sink.closeCount, 0)

        await first.emit(Data([0x21]))
        await second.emit(Data([0x22]))
        XCTAssertEqual(firstChannel.value()?.receivedBodies, [])
        XCTAssertEqual(secondChannel.value()?.receivedBodies, [Data([0x22])])
        service.stop(connectionID: connectionID)
    }

    @MainActor
    private func makeManager() -> MacRuntimeConnectionManager {
        MacRuntimeConnectionManager(
            localTransport: ServiceRuntimeTransport(),
            advertiser: ServiceAdvertiser(),
            bootstrapTransport: ServiceRelayTransport(),
            pairTransportFactory: { ServiceRelayTransport() },
            onDisconnect: { _ in }
        )
    }

    @MainActor
    private func makeService(
        connectionManager: MacRuntimeConnectionManager
    ) -> MacRuntimeProductionAcceptedSessionService {
        let storeURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(
                "aetherlink-production-service-test-\(UUID().uuidString).json"
            )
        return MacRuntimeProductionAcceptedSessionService(
            connectionManager: connectionManager,
            trustedDeviceStore: TrustedDeviceStore(fileURL: storeURL)
        )
    }

    private func makeCapability(
        channelBox: ServiceLocked<ServiceComposedChannel?>? = nil,
        abandonCount: ServiceLocked<Int> = ServiceLocked(0)
    ) -> MacRuntimeProductionChannelAuthorityCapability {
        MacRuntimeProductionChannelAuthorityCapability.testing(
            makeChannel: { rawSink, router in
                let channel = ServiceComposedChannel(
                    rawSink: rawSink,
                    router: router
                )
                channelBox?.mutate { $0 = channel }
                return channel
            },
            abandon: { abandonCount.mutate { $0 += 1 } }
        )
    }

    private func waitUntil(
        _ predicate: @escaping @Sendable () -> Bool
    ) async -> Bool {
        for _ in 0..<250 {
            if predicate() { return true }
            try? await Task.sleep(nanoseconds: 1_000_000)
        }
        return predicate()
    }
}

private enum ServiceTestError: Error, Equatable { case authorityUnavailable }

private final class ServiceAcceptedRawSession:
    RuntimeAcceptedRawSession,
    @unchecked Sendable
{
    let sink: ServiceRawSink
    let routeDescriptor: RuntimeAcceptedRawRouteDescriptor
    var connectionID: UUID { sink.connectionID }
    private let lock = NSLock()
    private var handler: (@Sendable (Data) async -> Void)?
    private var installs = 0
    private var claimTaken = false

    init(
        connectionID: UUID = UUID(),
        routeDescriptor: RuntimeAcceptedRawRouteDescriptor = .testing()
    ) {
        sink = ServiceRawSink(connectionID: connectionID)
        self.routeDescriptor = routeDescriptor
    }

    var installCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return installs
    }

    func takeRawEndpointClaim() -> RuntimeAcceptedRawEndpointClaim? {
        lock.lock()
        guard !claimTaken else {
            lock.unlock()
            return nil
        }
        claimTaken = true
        lock.unlock()
        return RuntimeAcceptedRawEndpointClaim.testing(
            rawSink: sink,
            routeDescriptor: routeDescriptor,
            installHandler: { [weak self] handler in
                self?.installRawFrameBodyHandler(handler) ?? false
            }
        )
    }

    func installRawFrameBodyHandler(
        _ handler: @escaping @Sendable (Data) async -> Void
    ) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        installs += 1
        guard self.handler == nil else { return false }
        self.handler = handler
        return true
    }

    func emit(_ body: Data) async {
        let current = currentHandler()
        await current?(body)
    }

    private func currentHandler() -> (@Sendable (Data) async -> Void)? {
        lock.lock()
        defer { lock.unlock() }
        let current = handler
        return current
    }
}

private final class ServiceRawSink: RuntimeRawFrameBodySink, @unchecked Sendable {
    let connectionID: UUID
    private let lock = NSLock()
    private var closes = 0

    init(connectionID: UUID) { self.connectionID = connectionID }

    var closeCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return closes
    }

    func sendRawFrameBody(
        _ body: Data,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        completion(false)
    }

    func close() {
        lock.lock()
        if closes == 0 { closes = 1 }
        lock.unlock()
    }
}

private final class ServiceComposedChannel:
    MacRuntimeProductionComposedChannel,
    @unchecked Sendable
{
    let connectionID: UUID
    var transportSecurityContext: TransportSecurityContext? {
        TransportSecurityContext(bindingID: String(repeating: "a", count: 64))
    }
    private let rawSink: any RuntimeRawFrameBodySink
    private let router: MacRuntimeProductionChannelAuthorityCapability.Router
    private let lock = NSLock()
    private var bodies: [Data] = []
    private var closes = 0
    private var terminalObserver: (@Sendable () -> Void)?

    init(
        rawSink: any RuntimeRawFrameBodySink,
        router: @escaping MacRuntimeProductionChannelAuthorityCapability.Router
    ) {
        self.rawSink = rawSink
        self.router = router
        connectionID = rawSink.connectionID
    }

    var receivedBodies: [Data] {
        lock.lock()
        defer { lock.unlock() }
        return bodies
    }

    var closeCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return closes
    }

    func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result {
        try operation(transportSecurityContext)
    }

    func send(_ envelope: ProtocolEnvelope) {}

    func send(
        _ envelope: ProtocolEnvelope,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        completion(false)
    }

    func sendAndWait(_ envelope: ProtocolEnvelope) async -> Bool { false }

    func receiveRawFrameBody(_ body: Data) async throws {
        record(body)
        router(ProtocolEnvelope(type: "service.test"), self)
    }

    private func record(_ body: Data) {
        lock.lock()
        bodies.append(body)
        lock.unlock()
    }

    func close() {
        let observer: (@Sendable () -> Void)?
        lock.lock()
        guard closes == 0 else {
            lock.unlock()
            return
        }
        closes = 1
        observer = terminalObserver
        terminalObserver = nil
        lock.unlock()
        rawSink.close()
        observer?()
    }

    func closeAndWait() async { close() }

    func installAttachmentTerminalObserver(
        _ observer: @escaping @Sendable () -> Void
    ) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard terminalObserver == nil, closes == 0 else { return false }
        terminalObserver = observer
        return true
    }
}

private final class ServiceRuntimeTransport: RuntimeTransport, @unchecked Sendable {
    private(set) var status: PeerServerStatus = .stopped
    func start(port: UInt16, onMessage: @escaping LocalPeerMessageHandler) {
        status = .listening(port: port)
    }
    func stop() { status = .stopped }
}

private final class ServiceRelayTransport: RelayPeerTransport, @unchecked Sendable {
    func start(
        configuration: RelayPeerConfiguration,
        onStatusChange: (@Sendable (RelayPeerStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {}
    func stop() {}
}

private struct ServiceAdvertiser: RuntimeAdvertiser {
    func start(port: Int32, metadata: RuntimeAdvertisementMetadata) {}
    func stop() {}
}

private final class ServiceLocked<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var stored: Value

    init(_ value: Value) { stored = value }

    func value() -> Value {
        lock.lock()
        defer { lock.unlock() }
        return stored
    }

    func mutate(_ operation: (inout Value) -> Void) {
        lock.lock()
        operation(&stored)
        lock.unlock()
    }
}

private actor ServiceAuthorityGate {
    private var entered = false
    private var released = false
    private var entryWaiters: [CheckedContinuation<Void, Never>] = []
    private var releaseWaiters: [CheckedContinuation<Void, Never>] = []

    func suspend() async {
        entered = true
        let currentEntryWaiters = entryWaiters
        entryWaiters.removeAll()
        currentEntryWaiters.forEach { $0.resume() }
        guard !released else { return }
        await withCheckedContinuation { releaseWaiters.append($0) }
    }

    func waitUntilEntered() async {
        guard !entered else { return }
        await withCheckedContinuation { entryWaiters.append($0) }
    }

    func release() {
        released = true
        let currentReleaseWaiters = releaseWaiters
        releaseWaiters.removeAll()
        currentReleaseWaiters.forEach { $0.resume() }
    }
}
