import BridgeProtocol
import Foundation
@_spi(ProductionRawEndpointOwnership)
@_spi(ProductionRawEndpointTesting) import Transport
import XCTest
@testable import CompanionCore

final class MacRuntimeProductionChannelCompositionTests: XCTestCase {
    @MainActor
    func testAcceptedRawSessionRoutesOnlyThroughComposedChannelAndStopAllCloses()
        async throws
    {
        let fixture = makeManagerFixture()
        let accepted = CompositionAcceptedRawSession()
        let channelBox = CompositionLocked<CompositionFakeChannel?>(nil)
        let routed = CompositionLocked<[ProtocolEnvelope]>([])
        let capability = makeCapability(channelBox: channelBox)

        try await fixture.manager.attachAcceptedProductionRawSession(
            accepted,
            authorityCapability: capability,
            onMessage: { envelope, sink in
                XCTAssertEqual(sink.connectionID, accepted.connectionID)
                routed.mutate { $0.append(envelope) }
            }
        )
        XCTAssertEqual(accepted.installCount, 1)
        XCTAssertEqual(fixture.local.startCount, 0)
        XCTAssertEqual(fixture.bootstrap.startCount, 0)

        await accepted.emit(Data([0x01]))
        XCTAssertEqual(channelBox.value()?.receivedBodies, [Data([0x01])])
        XCTAssertEqual(routed.value().map(\.type), ["composition.test"])

        fixture.manager.stopAll()
        XCTAssertEqual(channelBox.value()?.closeTransitionCount, 1)
        XCTAssertEqual(accepted.sink.closeCount, 1)
    }

    @MainActor
    func testAuthorityCapabilityIsOneUseAndNeverFallsBackToLegacy() async throws {
        let fixture = makeManagerFixture()
        let first = CompositionAcceptedRawSession()
        let second = CompositionAcceptedRawSession()
        let capability = makeCapability()

        try await fixture.manager.attachAcceptedProductionRawSession(
            first,
            authorityCapability: capability,
            onMessage: { _, _ in }
        )
        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                second,
                authorityCapability: capability,
                onMessage: { _, _ in }
            )
            XCTFail("Expected one-use authority rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .authorityCapabilityUnavailable
            )
        }

        XCTAssertEqual(second.sink.closeCount, 1)
        XCTAssertEqual(second.installCount, 0)
        XCTAssertEqual(fixture.local.startCount, 0)
        XCTAssertEqual(fixture.bootstrap.startCount, 0)
        fixture.manager.stopAll()
        XCTAssertEqual(first.sink.closeCount, 1)
    }

    @MainActor
    func testCompositionFailureClosesRawAbandonsAuthorityAndForbidsReuse()
        async throws
    {
        let fixture = makeManagerFixture()
        let first = CompositionAcceptedRawSession()
        let second = CompositionAcceptedRawSession()
        let abandonCount = CompositionLocked(0)
        let capability = MacRuntimeProductionChannelAuthorityCapability.testing(
            makeChannel: { _, _ in throw CompositionTestError.makeFailed },
            abandon: { abandonCount.mutate { $0 += 1 } }
        )

        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                first,
                authorityCapability: capability,
                onMessage: { _, _ in }
            )
            XCTFail("Expected composition failure")
        } catch {
            XCTAssertEqual(error as? CompositionTestError, .makeFailed)
        }
        XCTAssertEqual(abandonCount.value(), 1)
        XCTAssertEqual(first.sink.closeCount, 1)

        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                second,
                authorityCapability: capability,
                onMessage: { _, _ in }
            )
            XCTFail("Expected consumed capability rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .authorityCapabilityUnavailable
            )
        }
        XCTAssertEqual(second.sink.closeCount, 1)
        XCTAssertEqual(fixture.local.startCount, 0)
    }

    @MainActor
    func testPreCancelledAttemptConsumesCapabilityAndClosesRaw() async throws {
        let fixture = makeManagerFixture()
        let accepted = CompositionAcceptedRawSession()
        let abandonCount = CompositionLocked(0)
        let gate = CompositionAsyncGate()
        let capability = makeCapability(abandonCount: abandonCount)
        let task = Task { @MainActor in
            await gate.wait()
            try await fixture.manager.attachAcceptedProductionRawSession(
                accepted,
                authorityCapability: capability,
                onMessage: { _, _ in }
            )
        }
        task.cancel()
        await gate.open()
        do {
            try await task.value
            XCTFail("Expected cancellation")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }

        XCTAssertEqual(abandonCount.value(), 1)
        XCTAssertEqual(accepted.sink.closeCount, 1)
        XCTAssertEqual(accepted.installCount, 0)
        let reuse = CompositionAcceptedRawSession()
        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                reuse,
                authorityCapability: capability,
                onMessage: { _, _ in }
            )
            XCTFail("Expected consumed capability rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .authorityCapabilityUnavailable
            )
        }
        XCTAssertEqual(reuse.sink.closeCount, 1)
    }

    @MainActor
    func testRejectedHandlerAndReceiveFailureCloseWithoutFallback() async throws {
        let fixture = makeManagerFixture()
        let rejected = CompositionAcceptedRawSession(acceptsHandler: false)
        let rejectedChannel = CompositionLocked<CompositionFakeChannel?>(nil)
        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                rejected,
                authorityCapability: makeCapability(channelBox: rejectedChannel),
                onMessage: { _, _ in }
            )
            XCTFail("Expected raw handler rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .rawHandlerInstallationRejected
            )
        }
        XCTAssertEqual(rejectedChannel.value()?.closeTransitionCount, 1)
        XCTAssertEqual(rejected.sink.closeCount, 1)

        let failing = CompositionAcceptedRawSession()
        let failingChannel = CompositionLocked<CompositionFakeChannel?>(nil)
        try await fixture.manager.attachAcceptedProductionRawSession(
            failing,
            authorityCapability: makeCapability(
                channelBox: failingChannel,
                receiveFails: true
            ),
            onMessage: { _, _ in XCTFail("A failed raw record must not route") }
        )
        await failing.emit(Data([0x01]))
        await failing.emit(Data([0x02]))
        XCTAssertEqual(failingChannel.value()?.receivedBodies, [Data([0x01])])
        XCTAssertEqual(failingChannel.value()?.closeTransitionCount, 1)
        XCTAssertEqual(failing.sink.closeCount, 1)
        XCTAssertEqual(fixture.local.startCount, 0)
        XCTAssertEqual(fixture.bootstrap.startCount, 0)
    }

    @MainActor
    func testDuplicateAcceptedConnectionInvalidatesSecondAuthority() async throws {
        let fixture = makeManagerFixture()
        let connectionID = UUID()
        let first = CompositionAcceptedRawSession(connectionID: connectionID)
        let second = CompositionAcceptedRawSession(connectionID: connectionID)
        let abandoned = CompositionLocked(0)
        try await fixture.manager.attachAcceptedProductionRawSession(
            first,
            authorityCapability: makeCapability(),
            onMessage: { _, _ in }
        )

        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                second,
                authorityCapability: makeCapability(abandonCount: abandoned),
                onMessage: { _, _ in }
            )
            XCTFail("Expected duplicate accepted-session rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .duplicateAcceptedSession
            )
        }
        XCTAssertEqual(abandoned.value(), 1)
        XCTAssertEqual(second.sink.closeCount, 1)
        XCTAssertEqual(second.installCount, 0)
        fixture.manager.stopAll()
        XCTAssertEqual(first.sink.closeCount, 1)
    }

    @MainActor
    func testStopAllDuringCompositionPreventsAttachmentAndClosesChannel()
        async throws
    {
        let fixture = makeManagerFixture()
        let accepted = CompositionAcceptedRawSession()
        let channelBox = CompositionLocked<CompositionFakeChannel?>(nil)
        let composer = CompositionControlledComposer()
        let task = Task { @MainActor in
            try await fixture.manager.attachAcceptedProductionRawSession(
                accepted,
                authorityCapability: makeCapability(channelBox: channelBox),
                composer: composer,
                onMessage: { _, _ in XCTFail("Cancelled attachment routed a message") }
            )
        }

        await composer.waitUntilEntered()
        fixture.manager.stopAll()
        await composer.release()
        do {
            try await task.value
            XCTFail("Expected the cleared reservation to reject attachment")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .attachmentCancelled
            )
        }
        XCTAssertNil(channelBox.value())
        XCTAssertEqual(accepted.sink.closeCount, 1)
        XCTAssertEqual(fixture.local.startCount, 0)
        XCTAssertEqual(fixture.bootstrap.startCount, 0)
    }

    @MainActor
    func testStopAllImmediatelyCleansForeverSuspendedClaimedComposer()
        async throws
    {
        let fixture = makeManagerFixture()
        let accepted = CompositionAcceptedRawSession()
        let abandoned = CompositionLocked(0)
        let composer = CompositionNoncooperativeComposer(returnsChannel: false)
        let completion = expectation(description: "attach returns without composer")
        let result = CompositionLocked<Error?>(nil)

        let attachTask = Task { @MainActor in
            do {
                try await fixture.manager.attachAcceptedProductionRawSession(
                    accepted,
                    authorityCapability: makeCapability(abandonCount: abandoned),
                    composer: composer,
                    onMessage: { _, _ in XCTFail("Stopped reservation routed") }
                )
            } catch {
                result.mutate { $0 = error }
            }
            completion.fulfill()
        }

        await composer.waitUntilEntered()
        fixture.manager.stopAll()
        await fulfillment(of: [completion], timeout: 1)
        XCTAssertEqual(
            result.value() as? MacRuntimeProductionChannelCompositionError,
            .attachmentCancelled
        )
        XCTAssertEqual(accepted.sink.closeCount, 1)
        XCTAssertEqual(accepted.installCount, 0)
        let abandonedInTime = await waitUntil { abandoned.value() == 1 }
        XCTAssertTrue(abandonedInTime)

        await composer.release()
        _ = await attachTask.result
    }

    @MainActor
    func testTerminalClaimInvalidatesCapabilityBeforeDelayedAbandonRuns()
        async throws
    {
        let fixture = makeManagerFixture()
        let connectionID = UUID()
        let first = CompositionAcceptedRawSession(connectionID: connectionID)
        let composer = CompositionControlledComposer()
        let abandonGate = CompositionReceiveGate()
        let makeCount = CompositionLocked(0)
        let abandonCount = CompositionLocked(0)
        let capability = MacRuntimeProductionChannelAuthorityCapability.testing(
            makeChannel: { rawSink, router in
                makeCount.mutate { $0 += 1 }
                return CompositionFakeChannel(
                    rawSink: rawSink,
                    router: router,
                    receiveFails: false
                )
            },
            abandon: {
                abandonCount.mutate { $0 += 1 }
                await abandonGate.suspendUntilReleased()
            }
        )
        let firstTask = Task { @MainActor in
            try await fixture.manager.attachAcceptedProductionRawSession(
                first,
                authorityCapability: capability,
                composer: composer,
                onMessage: { _, _ in XCTFail("Stopped generation routed") }
            )
        }

        await composer.waitUntilEntered()
        fixture.manager.productionRawSessionAttachments.closeAllForTesting {
            // All terminal claims have completed, while Cleanup.perform has not
            // started and therefore cannot have scheduled asynchronous abandon.
            // A deferred invalidation implementation deterministically leaves
            // the capability available at this exact boundary.
            XCTAssertNil(capability.consume())
        }

        do {
            try await firstTask.value
            XCTFail("Expected first generation cancellation")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .attachmentCancelled
            )
        }

        // The asynchronous abandon is now definitely running but deliberately
        // blocked. Replacement attachment must remain impossible as well.
        await abandonGate.waitUntilEntered()
        let replacement = CompositionAcceptedRawSession(connectionID: connectionID)
        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                replacement,
                authorityCapability: capability,
                onMessage: { _, _ in XCTFail("Invalidated capability routed") }
            )
            XCTFail("Expected synchronous capability invalidation")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .authorityCapabilityUnavailable
            )
        }
        XCTAssertEqual(makeCount.value(), 0)
        XCTAssertEqual(abandonCount.value(), 1)
        XCTAssertEqual(replacement.installCount, 0)
        XCTAssertEqual(replacement.sink.closeCount, 1)

        await abandonGate.release()
        await composer.release()
        await Task.yield()
    }

    @MainActor
    func testLateChannelFromNoncooperativeComposerIsClosedWithoutInstallation()
        async throws
    {
        let fixture = makeManagerFixture()
        let accepted = CompositionAcceptedRawSession()
        let channelBox = CompositionLocked<CompositionFakeChannel?>(nil)
        let composer = CompositionNoncooperativeComposer(returnsChannel: true)
        let completion = expectation(description: "attachment cancellation returns")
        let attachTask = Task { @MainActor in
            defer { completion.fulfill() }
            try await fixture.manager.attachAcceptedProductionRawSession(
                accepted,
                authorityCapability: makeCapability(channelBox: channelBox),
                composer: composer,
                onMessage: { _, _ in XCTFail("Late channel routed") }
            )
        }

        await composer.waitUntilEntered()
        fixture.manager.stopAll()
        await fulfillment(of: [completion], timeout: 1)
        do {
            try await attachTask.value
            XCTFail("Expected stopped reservation rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .attachmentCancelled
            )
        }

        await composer.release()
        let lateChannelClosed = await waitUntil {
            channelBox.value()?.closeTransitionCount == 1
        }
        XCTAssertTrue(lateChannelClosed)
        XCTAssertEqual(accepted.installCount, 0)
        XCTAssertEqual(accepted.sink.closeCount, 1)
    }

    @MainActor
    func testStopAllBeforeComposerReturnNeverAdmitsBufferedImmediateFrame()
        async throws
    {
        let fixture = makeManagerFixture()
        let accepted = CompositionAcceptedRawSession()
        let routed = CompositionLocked(0)
        let channelBox = CompositionLocked<CompositionFakeChannel?>(nil)
        let composer = CompositionNoncooperativeComposer(returnsChannel: true)
        let task = Task { @MainActor in
            try await fixture.manager.attachAcceptedProductionRawSession(
                accepted,
                authorityCapability: makeCapability(channelBox: channelBox),
                composer: composer,
                onMessage: { _, _ in routed.mutate { $0 += 1 } }
            )
        }

        await composer.waitUntilEntered()
        fixture.manager.stopAll()
        do {
            try await task.value
            XCTFail("Expected stopped reservation rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .attachmentCancelled
            )
        }
        await composer.release()
        let bufferedChannelClosed = await waitUntil {
            channelBox.value()?.closeTransitionCount == 1
        }
        XCTAssertTrue(bufferedChannelClosed)
        await accepted.emit(Data([0x55]))
        XCTAssertEqual(accepted.installCount, 0)
        XCTAssertEqual(routed.value(), 0)
    }

    @MainActor
    func testStopWinningDuringHandlerInstallLeavesInstalledHandlerClosed()
        async throws
    {
        let fixture = makeManagerFixture()
        let attachments = fixture.manager.productionRawSessionAttachments
        let accepted = CompositionAcceptedRawSession(
            onInstall: { attachments.closeAll() }
        )
        let routed = CompositionLocked(0)
        let channelBox = CompositionLocked<CompositionFakeChannel?>(nil)

        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                accepted,
                authorityCapability: makeCapability(channelBox: channelBox),
                onMessage: { _, _ in routed.mutate { $0 += 1 } }
            )
            XCTFail("Expected lifecycle confirmation rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .attachmentCancelled
            )
        }

        XCTAssertEqual(accepted.installCount, 1)
        await accepted.emit(Data([0x01]))
        XCTAssertEqual(channelBox.value()?.receivedBodies, [])
        XCTAssertEqual(routed.value(), 0)
        XCTAssertEqual(channelBox.value()?.closeTransitionCount, 1)
        XCTAssertEqual(accepted.sink.closeCount, 1)
    }

    @MainActor
    func testHandlerRejectionRollsBackGenerationForReplacement() async throws {
        let fixture = makeManagerFixture()
        let connectionID = UUID()
        let rejected = CompositionAcceptedRawSession(
            connectionID: connectionID,
            acceptsHandler: false
        )
        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                rejected,
                authorityCapability: makeCapability(),
                onMessage: { _, _ in }
            )
            XCTFail("Expected handler rejection")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .rawHandlerInstallationRejected
            )
        }

        let replacement = CompositionAcceptedRawSession(connectionID: connectionID)
        try await fixture.manager.attachAcceptedProductionRawSession(
            replacement,
            authorityCapability: makeCapability(),
            onMessage: { _, _ in }
        )
        XCTAssertEqual(replacement.installCount, 1)
        fixture.manager.stopAll()
    }

    @MainActor
    func testOldGenerationDelayedReceiveFailureCannotRemoveReplacement()
        async throws
    {
        let fixture = makeManagerFixture()
        let connectionID = UUID()
        let receiveGate = CompositionReceiveGate()
        let first = CompositionAcceptedRawSession(connectionID: connectionID)
        try await fixture.manager.attachAcceptedProductionRawSession(
            first,
            authorityCapability: makeCapability(
                receiveFails: true,
                receiveGate: receiveGate
            ),
            onMessage: { _, _ in XCTFail("Failed old receive routed") }
        )

        let oldReceive = Task { await first.emit(Data([0x01])) }
        await receiveGate.waitUntilEntered()
        fixture.manager.stopAcceptedProductionRawSession(connectionID: connectionID)

        let second = CompositionAcceptedRawSession(connectionID: connectionID)
        let secondRouted = CompositionLocked(0)
        try await fixture.manager.attachAcceptedProductionRawSession(
            second,
            authorityCapability: makeCapability(),
            onMessage: { _, _ in secondRouted.mutate { $0 += 1 } }
        )

        await receiveGate.release()
        await oldReceive.value
        await second.emit(Data([0x02]))
        XCTAssertEqual(secondRouted.value(), 1)

        let third = CompositionAcceptedRawSession(connectionID: connectionID)
        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                third,
                authorityCapability: makeCapability(),
                onMessage: { _, _ in }
            )
            XCTFail("Replacement generation should still be active")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .duplicateAcceptedSession
            )
        }
        fixture.manager.stopAll()
    }

    @MainActor
    func testSuccessfulTerminalRecordSelfRemovesExactGeneration() async throws {
        let fixture = makeManagerFixture()
        let connectionID = UUID()
        let terminal = CompositionAcceptedRawSession(connectionID: connectionID)
        try await fixture.manager.attachAcceptedProductionRawSession(
            terminal,
            authorityCapability: makeCapability(
                startsActive: true,
                terminalAfterReceive: true
            ),
            onMessage: { _, _ in }
        )
        await terminal.emit(Data([0x01]))

        let replacement = CompositionAcceptedRawSession(connectionID: connectionID)
        try await fixture.manager.attachAcceptedProductionRawSession(
            replacement,
            authorityCapability: makeCapability(),
            onMessage: { _, _ in }
        )
        XCTAssertEqual(replacement.installCount, 1)
        fixture.manager.stopAll()
    }

    @MainActor
    func testTerminalDeliveryBlocksReplacementUntilFinalRouteReturns()
        async throws
    {
        let fixture = makeManagerFixture()
        let connectionID = UUID()
        let receiveGate = CompositionReceiveGate()
        let terminal = CompositionAcceptedRawSession(connectionID: connectionID)
        let routed = CompositionLocked(0)
        try await fixture.manager.attachAcceptedProductionRawSession(
            terminal,
            authorityCapability: makeCapability(
                receiveGate: receiveGate,
                startsActive: true,
                terminalAfterReceive: true
            ),
            onMessage: { _, _ in routed.mutate { $0 += 1 } }
        )

        let receiveTask = Task { await terminal.emit(Data([0x01])) }
        await receiveGate.waitUntilEntered()
        let tooEarly = CompositionAcceptedRawSession(connectionID: connectionID)
        do {
            try await fixture.manager.attachAcceptedProductionRawSession(
                tooEarly,
                authorityCapability: makeCapability(),
                onMessage: { _, _ in }
            )
            XCTFail("Replacement must wait for final delivery")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionChannelCompositionError,
                .duplicateAcceptedSession
            )
        }

        await receiveGate.release()
        await receiveTask.value
        XCTAssertEqual(routed.value(), 1)
        let replacement = CompositionAcceptedRawSession(connectionID: connectionID)
        try await fixture.manager.attachAcceptedProductionRawSession(
            replacement,
            authorityCapability: makeCapability(),
            onMessage: { _, _ in }
        )
        XCTAssertEqual(replacement.installCount, 1)
        fixture.manager.stopAll()
    }

    @MainActor
    func testIdleChannelTerminalObserverSelfRemovesWithoutAnotherRawBody()
        async throws
    {
        let fixture = makeManagerFixture()
        let connectionID = UUID()
        let accepted = CompositionAcceptedRawSession(connectionID: connectionID)
        let channelBox = CompositionLocked<CompositionFakeChannel?>(nil)
        try await fixture.manager.attachAcceptedProductionRawSession(
            accepted,
            authorityCapability: makeCapability(channelBox: channelBox),
            onMessage: { _, _ in }
        )

        channelBox.value()?.close()
        let replacement = CompositionAcceptedRawSession(connectionID: connectionID)
        try await fixture.manager.attachAcceptedProductionRawSession(
            replacement,
            authorityCapability: makeCapability(),
            onMessage: { _, _ in }
        )
        XCTAssertEqual(replacement.installCount, 1)
        fixture.manager.stopAll()
    }

    private func makeCapability(
        channelBox: CompositionLocked<CompositionFakeChannel?>? = nil,
        abandonCount: CompositionLocked<Int> = CompositionLocked(0),
        receiveFails: Bool = false,
        receiveGate: CompositionReceiveGate? = nil,
        startsActive: Bool = false,
        terminalAfterReceive: Bool = false
    ) -> MacRuntimeProductionChannelAuthorityCapability {
        MacRuntimeProductionChannelAuthorityCapability.testing(
            makeChannel: { rawSink, router in
                let channel = CompositionFakeChannel(
                    rawSink: rawSink,
                    router: router,
                    receiveFails: receiveFails,
                    receiveGate: receiveGate,
                    startsActive: startsActive,
                    terminalAfterReceive: terminalAfterReceive
                )
                channelBox?.mutate { $0 = channel }
                return channel
            },
            abandon: { abandonCount.mutate { $0 += 1 } }
        )
    }

    @MainActor
    private func makeManagerFixture() -> CompositionManagerFixture {
        let local = CompositionRuntimeTransport()
        let bootstrap = CompositionRelayTransport()
        let manager = MacRuntimeConnectionManager(
            localTransport: local,
            advertiser: CompositionAdvertiser(),
            bootstrapTransport: bootstrap,
            pairTransportFactory: { CompositionRelayTransport() },
            onDisconnect: { _ in }
        )
        return CompositionManagerFixture(
            manager: manager,
            local: local,
            bootstrap: bootstrap
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

private struct CompositionManagerFixture {
    let manager: MacRuntimeConnectionManager
    let local: CompositionRuntimeTransport
    let bootstrap: CompositionRelayTransport
}

private enum CompositionTestError: Error, Equatable { case makeFailed, receiveFailed }

private final class CompositionFakeChannel:
    MacRuntimeProductionComposedChannel,
    @unchecked Sendable
{
    let connectionID: UUID
    var transportSecurityContext: TransportSecurityContext? {
        lock.lock()
        defer { lock.unlock() }
        return activeContext
            ? TransportSecurityContext(bindingID: String(repeating: "a", count: 64))
            : nil
    }
    private let rawSink: any RuntimeRawFrameBodySink
    private let router: MacRuntimeProductionChannelAuthorityCapability.Router
    private let receiveFails: Bool
    private let receiveGate: CompositionReceiveGate?
    private let terminalAfterReceive: Bool
    private let lock = NSLock()
    private var bodies: [Data] = []
    private var closeTransitions = 0
    private var activeContext: Bool
    private var terminalObserver: (@Sendable () -> Void)?
    private var terminalObserverInstalled = false
    private var terminalObserverFired = false

    init(
        rawSink: any RuntimeRawFrameBodySink,
        router: @escaping MacRuntimeProductionChannelAuthorityCapability.Router,
        receiveFails: Bool,
        receiveGate: CompositionReceiveGate? = nil,
        startsActive: Bool = false,
        terminalAfterReceive: Bool = false
    ) {
        self.rawSink = rawSink
        self.router = router
        self.receiveFails = receiveFails
        self.receiveGate = receiveGate
        self.activeContext = startsActive
        self.terminalAfterReceive = terminalAfterReceive
        connectionID = rawSink.connectionID
    }

    var receivedBodies: [Data] {
        lock.lock()
        defer { lock.unlock() }
        return bodies
    }

    var closeTransitionCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return closeTransitions
    }

    func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result {
        try operation(nil)
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
        if let receiveGate { await receiveGate.suspendUntilReleased() }
        if receiveFails { throw CompositionTestError.receiveFailed }
        router(ProtocolEnvelope(type: "composition.test"), self)
        if terminalAfterReceive {
            transitionToTerminalAfterReceive()?()
        }
    }

    private func record(_ body: Data) {
        lock.lock()
        bodies.append(body)
        lock.unlock()
    }

    func close() {
        let observer: (@Sendable () -> Void)?
        lock.lock()
        guard closeTransitions == 0 else {
            lock.unlock()
            return
        }
        closeTransitions = 1
        activeContext = false
        observer = claimTerminalObserverLocked()
        lock.unlock()
        rawSink.close()
        observer?()
    }

    func closeAndWait() async { close() }

    @discardableResult
    func installAttachmentTerminalObserver(
        _ observer: @escaping @Sendable () -> Void
    ) -> Bool {
        let invokeInline: Bool
        lock.lock()
        guard !terminalObserverInstalled else {
            lock.unlock()
            return false
        }
        terminalObserverInstalled = true
        if closeTransitions > 0 {
            terminalObserverFired = true
            invokeInline = true
        } else {
            terminalObserver = observer
            invokeInline = false
        }
        lock.unlock()
        if invokeInline { observer() }
        return true
    }

    private func claimTerminalObserverLocked() -> (@Sendable () -> Void)? {
        guard terminalObserverInstalled, !terminalObserverFired else { return nil }
        terminalObserverFired = true
        let observer = terminalObserver
        terminalObserver = nil
        return observer
    }

    private func transitionToTerminalAfterReceive()
        -> (@Sendable () -> Void)?
    {
        lock.lock()
        defer { lock.unlock() }
        activeContext = false
        return claimTerminalObserverLocked()
    }
}

private final class CompositionAcceptedRawSession:
    RuntimeAcceptedRawSession,
    @unchecked Sendable
{
    let sink: CompositionRawSink
    let routeDescriptor: RuntimeAcceptedRawRouteDescriptor
    var connectionID: UUID { sink.connectionID }
    private let acceptsHandler: Bool
    private let onInstall: (@Sendable () -> Void)?
    private let lock = NSLock()
    private var handler: (@Sendable (Data) async -> Void)?
    private var installs = 0
    private var claimTaken = false

    init(
        connectionID: UUID = UUID(),
        routeDescriptor: RuntimeAcceptedRawRouteDescriptor = .testing(),
        acceptsHandler: Bool = true,
        onInstall: (@Sendable () -> Void)? = nil
    ) {
        sink = CompositionRawSink(connectionID: connectionID)
        self.routeDescriptor = routeDescriptor
        self.acceptsHandler = acceptsHandler
        self.onInstall = onInstall
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
        installs += 1
        guard acceptsHandler, self.handler == nil else {
            lock.unlock()
            return false
        }
        lock.unlock()
        onInstall?()
        lock.lock()
        defer { lock.unlock() }
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
        return handler
    }
}

private final class CompositionRawSink: RuntimeRawFrameBodySink, @unchecked Sendable {
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

private final class CompositionRuntimeTransport:
    RuntimeTransport,
    @unchecked Sendable
{
    private(set) var status: PeerServerStatus = .stopped
    private(set) var startCount = 0

    func start(port: UInt16, onMessage: @escaping LocalPeerMessageHandler) {
        startCount += 1
        status = .listening(port: port)
    }

    func stop() { status = .stopped }
}

private final class CompositionRelayTransport:
    RelayPeerTransport,
    @unchecked Sendable
{
    private(set) var startCount = 0

    func start(
        configuration: RelayPeerConfiguration,
        onStatusChange: (@Sendable (RelayPeerStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        startCount += 1
    }

    func stop() {}
}

private struct CompositionAdvertiser: RuntimeAdvertiser {
    func start(port: Int32, metadata: RuntimeAdvertisementMetadata) {}
    func stop() {}
}

private final class CompositionLocked<Value>: @unchecked Sendable {
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

private actor CompositionAsyncGate {
    private var opened = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    func wait() async {
        guard !opened else { return }
        await withCheckedContinuation { waiters.append($0) }
    }

    func open() {
        opened = true
        let current = waiters
        waiters.removeAll()
        current.forEach { $0.resume() }
    }
}

private actor CompositionControlledComposer:
    MacRuntimeProductionChannelComposing
{
    private var entered = false
    private var released = false
    private var entryWaiters: [CheckedContinuation<Void, Never>] = []
    private var releaseWaiters: [CheckedContinuation<Void, Never>] = []

    func compose(
        endpointClaim: RuntimeAcceptedRawEndpointClaim,
        authorityCapability: MacRuntimeProductionChannelAuthorityCapability,
        router: @escaping MacRuntimeProductionChannelAuthorityCapability.Router
    ) async throws -> any MacRuntimeProductionComposedChannel {
        entered = true
        let waitingForEntry = entryWaiters
        entryWaiters.removeAll()
        waitingForEntry.forEach { $0.resume() }
        if !released {
            await withCheckedContinuation { releaseWaiters.append($0) }
        }
        return try await MacRuntimeProductionChannelComposer().compose(
            endpointClaim: endpointClaim,
            authorityCapability: authorityCapability,
            router: router
        )
    }

    func waitUntilEntered() async {
        guard !entered else { return }
        await withCheckedContinuation { entryWaiters.append($0) }
    }

    func release() {
        released = true
        let waiting = releaseWaiters
        releaseWaiters.removeAll()
        waiting.forEach { $0.resume() }
    }
}

private actor CompositionNoncooperativeComposer:
    MacRuntimeProductionChannelComposing
{
    private let returnsChannel: Bool
    private var entered = false
    private var released = false
    private var entryWaiters: [CheckedContinuation<Void, Never>] = []
    private var releaseWaiters: [CheckedContinuation<Void, Never>] = []

    init(returnsChannel: Bool) {
        self.returnsChannel = returnsChannel
    }

    func compose(
        endpointClaim: RuntimeAcceptedRawEndpointClaim,
        authorityCapability: MacRuntimeProductionChannelAuthorityCapability,
        router: @escaping MacRuntimeProductionChannelAuthorityCapability.Router
    ) async throws -> any MacRuntimeProductionComposedChannel {
        guard let rawSink = endpointClaim.transferRawSinkToChannel() else {
            throw MacRuntimeProductionChannelCompositionError.rawEndpointUnavailable
        }
        guard let claim = authorityCapability.consume() else {
            throw MacRuntimeProductionChannelCompositionError
                .authorityCapabilityUnavailable
        }
        entered = true
        let currentEntryWaiters = entryWaiters
        entryWaiters.removeAll(keepingCapacity: false)
        currentEntryWaiters.forEach { $0.resume() }
        if !released {
            // Intentionally ignores task cancellation to exercise registry-owned
            // cleanup and late-result disposal.
            await withCheckedContinuation { releaseWaiters.append($0) }
        }
        guard returnsChannel else { throw CompositionTestError.makeFailed }
        return try claim.makeChannel(rawSink, router)
    }

    func waitUntilEntered() async {
        guard !entered else { return }
        await withCheckedContinuation { entryWaiters.append($0) }
    }

    func release() {
        released = true
        let current = releaseWaiters
        releaseWaiters.removeAll(keepingCapacity: false)
        current.forEach { $0.resume() }
    }
}

private actor CompositionReceiveGate {
    private var entered = false
    private var released = false
    private var entryWaiters: [CheckedContinuation<Void, Never>] = []
    private var releaseWaiters: [CheckedContinuation<Void, Never>] = []

    func suspendUntilReleased() async {
        entered = true
        let currentEntryWaiters = entryWaiters
        entryWaiters.removeAll(keepingCapacity: false)
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
        let current = releaseWaiters
        releaseWaiters.removeAll(keepingCapacity: false)
        current.forEach { $0.resume() }
    }
}
