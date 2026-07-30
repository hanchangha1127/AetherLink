import BridgeProtocol
@testable import CompanionCore
import Darwin
import Foundation
import Transport
import XCTest

final class MacRuntimeConnectionManagerTests: XCTestCase {
    @MainActor
    func testStartLocalDefersAdvertisementUntilListenerIsReady() async {
        let events = LocalOwnershipEventRecorder()
        let local = RecordingRuntimeTransport(
            statusesAfterStart: [.starting(port: 43171)],
            events: events
        )
        let advertiser = RecordingRuntimeAdvertiser(events: events)
        let manager = makeManager(local: local, advertiser: advertiser)
        let metadata = RuntimeAdvertisementMetadata(
            version: "4",
            routeToken: "route-token",
            deviceID: "device-id",
            fingerprint: "fingerprint",
            app: "Companion"
        )

        let status = manager.startLocal(
            port: 43171,
            metadata: metadata,
            onMessage: unusedMessageHandler
        )

        XCTAssertEqual(status, .starting(port: 43171))
        XCTAssertEqual(local.startedPorts, [43171])
        XCTAssertTrue(advertiser.starts.isEmpty)
        XCTAssertEqual(events.events, [
            .localStart(port: 43171),
        ])

        local.emitStatus(.listening(port: 43171), start: 0)
        await flushStatusCallbacks()

        XCTAssertEqual(advertiser.starts, [.init(port: 43171, metadata: metadata)])
        XCTAssertEqual(events.events, [
            .localStart(port: 43171),
            .advertiserStart(port: 43171, metadata: metadata),
        ])
    }

    @MainActor
    func testStartLocalDefersReadyUntilAdvertisementIsPublished() async {
        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser(
            statusesAfterStart: [.publishing]
        )
        let manager = makeManager(local: local, advertiser: advertiser)
        var observedStatuses: [PeerServerStatus] = []

        let status = manager.startLocal(
            port: 43_191,
            metadata: RuntimeAdvertisementMetadata(version: "publishing"),
            onStatusChange: { observedStatuses.append($0) },
            onMessage: unusedMessageHandler
        )

        XCTAssertEqual(status, .starting(port: 43_191))
        XCTAssertTrue(observedStatuses.isEmpty)

        advertiser.emitStatus(.published, start: 0)
        await flushStatusCallbacks()

        XCTAssertEqual(observedStatuses, [.listening(port: 43_191)])
        XCTAssertEqual(local.stopCount, 0)
        XCTAssertEqual(advertiser.stopCount, 0)
    }

    @MainActor
    func testAsyncListenerReadyForwardsImmediateAdvertisementFailure() async {
        let port: UInt16 = 43_195
        let failure = PeerServerStatus.failed(
            "Local discovery publication failed immediately."
        )
        let local = RecordingRuntimeTransport(
            statusesAfterStart: [.starting(port: port)]
        )
        let advertiser = RecordingRuntimeAdvertiser(
            statusesAfterStart: [
                .failed("Local discovery publication failed immediately."),
            ]
        )
        let manager = makeManager(local: local, advertiser: advertiser)
        var observedStatuses: [PeerServerStatus] = []

        XCTAssertEqual(
            manager.startLocal(
                port: port,
                metadata: RuntimeAdvertisementMetadata(version: "immediate-failure"),
                onStatusChange: { observedStatuses.append($0) },
                onMessage: unusedMessageHandler
            ),
            .starting(port: port)
        )

        local.emitStatus(.listening(port: port), start: 0)
        await flushStatusCallbacks()

        XCTAssertEqual(observedStatuses, [failure])
        XCTAssertEqual(local.stopCount, 1)
        XCTAssertEqual(advertiser.stopCount, 1)
    }

    @MainActor
    func testAdvertisementFailureAllowsSamePortRetryAndIgnoresStaleSuccess()
        async
    {
        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser(
            statusesAfterStart: [.publishing, .publishing]
        )
        let manager = makeManager(local: local, advertiser: advertiser)
        var observedStatuses: [PeerServerStatus] = []

        XCTAssertEqual(
            manager.startLocal(
                port: 43_192,
                metadata: RuntimeAdvertisementMetadata(version: "first"),
                onStatusChange: { observedStatuses.append($0) },
                onMessage: unusedMessageHandler
            ),
            .starting(port: 43_192)
        )
        advertiser.emitStatus(
            .failed("Local discovery publication failed."),
            start: 0
        )
        await flushStatusCallbacks()

        XCTAssertEqual(
            observedStatuses,
            [.failed("Local discovery publication failed.")]
        )
        XCTAssertEqual(local.stopCount, 1)
        XCTAssertEqual(advertiser.stopCount, 1)

        XCTAssertEqual(
            manager.startLocal(
                port: 43_192,
                metadata: RuntimeAdvertisementMetadata(version: "retry"),
                onStatusChange: { observedStatuses.append($0) },
                onMessage: unusedMessageHandler
            ),
            .starting(port: 43_192)
        )
        advertiser.emitStatus(.published, start: 0)
        await flushStatusCallbacks()
        XCTAssertEqual(
            observedStatuses,
            [.failed("Local discovery publication failed.")]
        )

        advertiser.emitStatus(.published, start: 1)
        await flushStatusCallbacks()

        XCTAssertEqual(
            observedStatuses,
            [
                .failed("Local discovery publication failed."),
                .listening(port: 43_192),
            ]
        )
        XCTAssertEqual(
            advertiser.starts.map(\.metadata.version),
            ["first", "retry"]
        )
    }

    @MainActor
    func testRefreshWhileAdvertisementPublishesUsesLatestMetadataOnly() async {
        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser(
            statusesAfterStart: [.publishing, .publishing]
        )
        let manager = makeManager(local: local, advertiser: advertiser)
        var observedStatuses: [PeerServerStatus] = []

        XCTAssertEqual(
            manager.startLocal(
                port: 43_193,
                metadata: RuntimeAdvertisementMetadata(version: "initial"),
                onStatusChange: { observedStatuses.append($0) },
                onMessage: unusedMessageHandler
            ),
            .starting(port: 43_193)
        )
        XCTAssertEqual(
            manager.refreshLocalAdvertisement(
                metadata: RuntimeAdvertisementMetadata(version: "latest")
            ),
            .starting(port: 43_193)
        )

        advertiser.emitStatus(.published, start: 0)
        await flushStatusCallbacks()
        XCTAssertTrue(observedStatuses.isEmpty)

        advertiser.emitStatus(.published, start: 1)
        await flushStatusCallbacks()

        XCTAssertEqual(observedStatuses, [.listening(port: 43_193)])
        XCTAssertEqual(
            advertiser.starts.map(\.metadata.version),
            ["initial", "latest"]
        )
        XCTAssertEqual(advertiser.stopCount, 1)
    }

    @MainActor
    func testUnexpectedAdvertisementStopClearsFalseReadyOwnership() async {
        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser()
        let manager = makeManager(local: local, advertiser: advertiser)
        var observedStatuses: [PeerServerStatus] = []

        XCTAssertEqual(
            manager.startLocal(
                port: 43_194,
                metadata: RuntimeAdvertisementMetadata(version: "published"),
                onStatusChange: { observedStatuses.append($0) },
                onMessage: unusedMessageHandler
            ),
            .listening(port: 43_194)
        )

        advertiser.emitStatus(.stopped, start: 0)
        await flushStatusCallbacks()

        XCTAssertEqual(
            observedStatuses,
            [.failed("Local discovery publication stopped unexpectedly.")]
        )
        XCTAssertEqual(local.stopCount, 1)
        XCTAssertEqual(advertiser.stopCount, 1)
    }

    @MainActor
    func testFailedLocalStartSuppressesAdvertisement() {
        let local = RecordingRuntimeTransport(statusesAfterStart: [.failed("unavailable")])
        let advertiser = RecordingRuntimeAdvertiser()
        let manager = makeManager(local: local, advertiser: advertiser)

        let status = manager.startLocal(
            port: 43172,
            metadata: RuntimeAdvertisementMetadata(version: "failed"),
            onMessage: unusedMessageHandler
        )

        XCTAssertEqual(status, .failed("unavailable"))
        XCTAssertTrue(advertiser.starts.isEmpty)
        XCTAssertEqual(advertiser.stopCount, 1)
        XCTAssertEqual(local.stopCount, 1)
    }

    @MainActor
    func testUnexpectedLocalPortCannotRemainStartingOrAdvertising() {
        let unexpectedPortFailure = PeerServerStatus.failed(
            "Local listener reported an unexpected port."
        )
        for status in [
            PeerServerStatus.starting(port: 43190),
            .listening(port: 43190),
        ] {
            let local = RecordingRuntimeTransport(statusesAfterStart: [status])
            let advertiser = RecordingRuntimeAdvertiser()
            let manager = makeManager(local: local, advertiser: advertiser)

            let result = manager.startLocal(
                port: 43189,
                metadata: RuntimeAdvertisementMetadata(version: "unexpected"),
                onMessage: unusedMessageHandler
            )

            XCTAssertEqual(result, unexpectedPortFailure)
            XCTAssertTrue(advertiser.starts.isEmpty)
            XCTAssertEqual(advertiser.stopCount, 1)
            XCTAssertEqual(local.stopCount, 1)
        }

        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser()
        let manager = makeManager(local: local, advertiser: advertiser)
        manager.startLocal(
            port: 43189,
            metadata: RuntimeAdvertisementMetadata(version: "initial"),
            onMessage: unusedMessageHandler
        )
        local.setStatus(.starting(port: 43190))

        let refreshResult = manager.refreshLocalAdvertisement(
            metadata: RuntimeAdvertisementMetadata(version: "refresh")
        )

        XCTAssertEqual(refreshResult, unexpectedPortFailure)
        XCTAssertEqual(advertiser.starts.count, 1)
        XCTAssertEqual(advertiser.stopCount, 1)
        XCTAssertEqual(local.stopCount, 1)
    }

    @MainActor
    func testRepeatedLocalStartStopsPriorOwnershipBeforeReplacement() {
        let events = LocalOwnershipEventRecorder()
        let local = RecordingRuntimeTransport(events: events)
        let advertiser = RecordingRuntimeAdvertiser(events: events)
        let manager = makeManager(local: local, advertiser: advertiser)
        let firstMetadata = RuntimeAdvertisementMetadata(version: "first")
        let secondMetadata = RuntimeAdvertisementMetadata(version: "second")

        manager.startLocal(port: 43173, metadata: firstMetadata, onMessage: unusedMessageHandler)
        manager.startLocal(port: 43174, metadata: secondMetadata, onMessage: unusedMessageHandler)

        XCTAssertEqual(local.startedPorts, [43173, 43174])
        XCTAssertEqual(local.stopCount, 1)
        XCTAssertEqual(advertiser.starts, [
            .init(port: 43173, metadata: firstMetadata),
            .init(port: 43174, metadata: secondMetadata),
        ])
        XCTAssertEqual(advertiser.stopCount, 1)
        XCTAssertEqual(events.events, [
            .localStart(port: 43173),
            .advertiserStart(port: 43173, metadata: firstMetadata),
            .advertiserStop,
            .localStop,
            .localStart(port: 43174),
            .advertiserStart(port: 43174, metadata: secondMetadata),
        ])
    }

    @MainActor
    func testRefreshLocalAdvertisementRestartsOnlyAdvertiserForActivePort() {
        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser()
        let manager = makeManager(local: local, advertiser: advertiser)
        let originalMetadata = RuntimeAdvertisementMetadata(version: "original")
        let refreshedMetadata = RuntimeAdvertisementMetadata(version: "refreshed")

        manager.startLocal(port: 43175, metadata: originalMetadata, onMessage: unusedMessageHandler)
        manager.refreshLocalAdvertisement(metadata: refreshedMetadata)

        XCTAssertEqual(local.startedPorts, [43175])
        XCTAssertEqual(local.stopCount, 0)
        XCTAssertEqual(advertiser.starts, [
            .init(port: 43175, metadata: originalMetadata),
            .init(port: 43175, metadata: refreshedMetadata),
        ])
        XCTAssertEqual(advertiser.stopCount, 1)
    }

    @MainActor
    func testRefreshWhileListenerStartsUsesLatestMetadataAfterReady() async {
        let local = RecordingRuntimeTransport(
            statusesAfterStart: [.starting(port: 43178)]
        )
        let advertiser = RecordingRuntimeAdvertiser()
        let manager = makeManager(local: local, advertiser: advertiser)
        let refreshedMetadata = RuntimeAdvertisementMetadata(version: "refreshed")

        manager.startLocal(
            port: 43178,
            metadata: RuntimeAdvertisementMetadata(version: "initial"),
            onMessage: unusedMessageHandler
        )
        let refreshStatus = manager.refreshLocalAdvertisement(
            metadata: refreshedMetadata
        )

        XCTAssertEqual(refreshStatus, .starting(port: 43178))
        XCTAssertTrue(advertiser.starts.isEmpty)
        XCTAssertEqual(advertiser.stopCount, 0)

        local.emitStatus(.listening(port: 43178), start: 0)
        await flushStatusCallbacks()

        XCTAssertEqual(
            advertiser.starts,
            [.init(port: 43178, metadata: refreshedMetadata)]
        )
    }

    @MainActor
    func testRefreshLocalAdvertisementIsInertForStoppedAndFailedStarts() {
        for status in [PeerServerStatus.stopped, .failed("unavailable")] {
            let local = RecordingRuntimeTransport(statusesAfterStart: [status])
            let advertiser = RecordingRuntimeAdvertiser()
            let manager = makeManager(local: local, advertiser: advertiser)

            manager.startLocal(
                port: 43176,
                metadata: RuntimeAdvertisementMetadata(version: "initial"),
                onMessage: unusedMessageHandler
            )
            manager.refreshLocalAdvertisement(
                metadata: RuntimeAdvertisementMetadata(version: "refreshed")
            )

            XCTAssertEqual(local.startedPorts, [43176])
            XCTAssertEqual(local.stopCount, 1)
            XCTAssertTrue(advertiser.starts.isEmpty)
            XCTAssertEqual(advertiser.stopCount, 1)
        }
    }

    @MainActor
    func testRefreshLocalAdvertisementCleansUpAsynchronouslyFailedListener() {
        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser()
        let manager = makeManager(local: local, advertiser: advertiser)

        manager.startLocal(
            port: 43179,
            metadata: RuntimeAdvertisementMetadata(version: "initial"),
            onMessage: unusedMessageHandler
        )
        local.setStatus(.failed("listener-failed"))

        let status = manager.refreshLocalAdvertisement(
            metadata: RuntimeAdvertisementMetadata(version: "stale-refresh")
        )

        XCTAssertEqual(status, .failed("listener-failed"))
        XCTAssertEqual(local.stopCount, 1)
        XCTAssertEqual(advertiser.starts.count, 1)
        XCTAssertEqual(advertiser.stopCount, 1)
    }

    @MainActor
    func testLateLocalFailureStopsOwnershipAndReportsStatus() async {
        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser()
        let manager = makeManager(local: local, advertiser: advertiser)
        var observedStatuses: [PeerServerStatus] = []

        manager.startLocal(
            port: 43180,
            metadata: RuntimeAdvertisementMetadata(version: "late-failure"),
            onStatusChange: { observedStatuses.append($0) },
            onMessage: unusedMessageHandler
        )
        local.emitStatus(.failed("listener-failed"), start: 0)
        await flushStatusCallbacks()

        XCTAssertEqual(observedStatuses, [.failed("listener-failed")])
        XCTAssertEqual(local.stopCount, 1)
        XCTAssertEqual(advertiser.starts.count, 1)
        XCTAssertEqual(advertiser.stopCount, 1)
    }

    @MainActor
    func testConcreteLocalListenerDefersAdvertisementAndRetriesAfterOccupiedPort() async throws {
        let occupied = try Self.occupyTCPPort()
        var occupiedSocket: Int32? = occupied.socket
        let local = LocalPeerServer()
        let advertiser = RecordingRuntimeAdvertiser()
        let manager = makeManager(local: local, advertiser: advertiser)
        var observedStatuses: [PeerServerStatus] = []
        defer {
            if let occupiedSocket {
                Darwin.close(occupiedSocket)
            }
            manager.stopAll()
        }

        let firstStatus = manager.startLocal(
            port: occupied.port,
            metadata: RuntimeAdvertisementMetadata(version: "occupied"),
            onStatusChange: { observedStatuses.append($0) },
            onMessage: unusedMessageHandler
        )

        XCTAssertNotEqual(firstStatus, .listening(port: occupied.port))
        XCTAssertTrue(advertiser.starts.isEmpty)
        let didFail = await waitForCondition {
            if case .failed = firstStatus {
                return true
            }
            return observedStatuses.contains { status in
                if case .failed = status { return true }
                return false
            }
        }
        XCTAssertTrue(didFail)
        XCTAssertFalse(
            observedStatuses.contains(.listening(port: occupied.port))
        )
        XCTAssertTrue(advertiser.starts.isEmpty)

        Darwin.close(occupied.socket)
        occupiedSocket = nil
        observedStatuses.removeAll()
        let retryMetadata = RuntimeAdvertisementMetadata(version: "retry")
        let retryStatus = manager.startLocal(
            port: occupied.port,
            metadata: retryMetadata,
            onStatusChange: { observedStatuses.append($0) },
            onMessage: unusedMessageHandler
        )

        if case .failed(let message) = retryStatus {
            XCTFail("Retry unexpectedly failed: \(message)")
        }
        let didAdvertise = await waitForCondition {
            advertiser.starts.count == 1
        }
        XCTAssertTrue(didAdvertise)
        XCTAssertEqual(
            advertiser.starts,
            [.init(port: Int32(occupied.port), metadata: retryMetadata)]
        )
        XCTAssertEqual(local.status, .listening(port: occupied.port))
    }

    @MainActor
    func testSupersededLocalStatusCallbackCannotStopReplacement() async {
        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser()
        let manager = makeManager(local: local, advertiser: advertiser)
        var observedStatuses: [PeerServerStatus] = []

        manager.startLocal(
            port: 43180,
            metadata: RuntimeAdvertisementMetadata(version: "first"),
            onStatusChange: { observedStatuses.append($0) },
            onMessage: unusedMessageHandler
        )
        manager.startLocal(
            port: 43181,
            metadata: RuntimeAdvertisementMetadata(version: "second"),
            onStatusChange: { observedStatuses.append($0) },
            onMessage: unusedMessageHandler
        )

        local.emitStatus(.failed("stale-listener"), start: 0)
        await flushStatusCallbacks()

        XCTAssertTrue(observedStatuses.isEmpty)
        XCTAssertEqual(local.stopCount, 1)
        XCTAssertEqual(advertiser.starts.count, 2)
        XCTAssertEqual(advertiser.stopCount, 1)

        local.emitStatus(.failed("current-listener"), start: 1)
        await flushStatusCallbacks()

        XCTAssertEqual(observedStatuses, [.failed("current-listener")])
        XCTAssertEqual(local.stopCount, 2)
        XCTAssertEqual(advertiser.stopCount, 2)
    }

    @MainActor
    func testStoppedLocalStatusCallbackIsIgnoredAfterExplicitStop() async {
        let local = RecordingRuntimeTransport()
        let manager = makeManager(local: local)
        var observedStatuses: [PeerServerStatus] = []

        manager.startLocal(
            port: 43180,
            metadata: RuntimeAdvertisementMetadata(version: "explicit-stop"),
            onStatusChange: { observedStatuses.append($0) },
            onMessage: unusedMessageHandler
        )
        manager.stopAll()
        local.emitStatus(.failed("after-stop"), start: 0)
        await flushStatusCallbacks()

        XCTAssertTrue(observedStatuses.isEmpty)
        XCTAssertEqual(local.stopCount, 1)
    }

    @MainActor
    func testSupersededAndStoppedLocalMessageCallbacksAreIgnored() {
        let local = RecordingRuntimeTransport()
        let manager = makeManager(local: local)
        let recorder = MessageRecorder()
        let sink = RecordingMessageSink()

        manager.startLocal(
            port: 43180,
            metadata: RuntimeAdvertisementMetadata(version: "first"),
            onMessage: recorder.handler
        )
        manager.startLocal(
            port: 43181,
            metadata: RuntimeAdvertisementMetadata(version: "second"),
            onMessage: recorder.handler
        )

        local.emit(ProtocolEnvelope(type: "stale-local", requestID: "stale"), sink: sink, start: 0)
        local.emit(ProtocolEnvelope(type: "current-local", requestID: "current"), sink: sink, start: 1)
        manager.stopAll()
        local.emit(ProtocolEnvelope(type: "stopped-local", requestID: "stopped"), sink: sink, start: 1)

        XCTAssertEqual(recorder.envelopes.map(\.type), ["current-local"])
    }

    @MainActor
    func testStopAllWaitsForAdmittedLocalMessageCallbackBeforeReturning() {
        let local = RecordingRuntimeTransport()
        let manager = makeManager(local: local)
        let callbackEntered = DispatchSemaphore(value: 0)
        let releaseCallback = DispatchSemaphore(value: 0)
        let callbackCompleted = DispatchSemaphore(value: 0)
        let sink = RecordingMessageSink()

        manager.startLocal(
            port: 43182,
            metadata: RuntimeAdvertisementMetadata(version: "concurrent-stop"),
            onMessage: { _, _ in
                callbackEntered.signal()
                releaseCallback.wait()
                callbackCompleted.signal()
            }
        )

        DispatchQueue.global().async {
            local.emit(
                ProtocolEnvelope(type: "in-flight-local", requestID: "in-flight"),
                sink: sink,
                start: 0
            )
        }
        XCTAssertEqual(callbackEntered.wait(timeout: .now() + 1), .success)
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.05) {
            releaseCallback.signal()
        }

        manager.stopAll()

        XCTAssertEqual(callbackCompleted.wait(timeout: .now()), .success)
    }

    @MainActor
    func testLocalMessageHandlerPassesThroughUnchanged() {
        let local = RecordingRuntimeTransport()
        let manager = makeManager(local: local)
        let recorder = MessageRecorder()
        let sink = RecordingMessageSink()
        let envelope = ProtocolEnvelope(type: "local", requestID: "local-request")

        manager.startLocal(
            port: 43177,
            metadata: RuntimeAdvertisementMetadata(),
            onMessage: recorder.handler
        )
        local.emit(envelope, sink: sink, start: 0)

        XCTAssertEqual(recorder.envelopes, [envelope])
        XCTAssertEqual(recorder.sinkConnectionIDs, [sink.connectionID])
    }

    @MainActor
    func testConcreteLocalPeerServerForwardsDisconnect() {
        let local = LocalPeerServer()
        let recorder = DisconnectRecorder()
        _ = MacRuntimeConnectionManager(
            localTransport: local,
            advertiser: RecordingRuntimeAdvertiser(),
            bootstrapTransport: RecordingRelayTransport(),
            pairTransportFactory: { RecordingRelayTransport() },
            onDisconnect: { connectionID in recorder.record(connectionID) }
        )
        let connectionID = UUID()

        local.onDisconnect?(connectionID)

        XCTAssertEqual(recorder.connectionIDs, [connectionID])
    }

    @MainActor
    func testStopAllStopsLocalAdvertiserBootstrapAndPairsExactlyOnce() {
        let local = RecordingRuntimeTransport()
        let advertiser = RecordingRuntimeAdvertiser()
        let bootstrap = RecordingRelayTransport()
        let first = RecordingRelayTransport()
        let second = RecordingRelayTransport()
        let manager = makeManager(
            local: local,
            advertiser: advertiser,
            bootstrap: bootstrap,
            factory: RelayTransportFactory([first, second])
        )

        manager.startLocal(
            port: 43178,
            metadata: RuntimeAdvertisementMetadata(),
            onMessage: unusedMessageHandler
        )
        manager.startBootstrap(
            configuration: configuration("bootstrap"),
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("a"),
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-b",
            configuration: configuration("b"),
            onMessage: unusedMessageHandler
        )

        manager.stopAll()
        manager.stopAll()

        XCTAssertEqual(local.stopCount, 1)
        XCTAssertEqual(advertiser.stopCount, 1)
        XCTAssertEqual(bootstrap.stopCount, 1)
        XCTAssertEqual(first.stopCount, 1)
        XCTAssertEqual(second.stopCount, 1)
    }

    @MainActor
    func testLatePairStatusFromSupersededGenerationIsIgnoredAndReplacementStopsOnce() async {
        let first = RecordingRelayTransport()
        let second = RecordingRelayTransport()
        let factory = RelayTransportFactory([first, second])
        let manager = makeManager(factory: factory)
        var statuses: [RelayPeerStatus] = []

        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("first"),
            onStatusChange: { statuses.append($0) },
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("second"),
            onStatusChange: { statuses.append($0) },
            onMessage: unusedMessageHandler
        )

        XCTAssertEqual(first.stopCount, 1)
        first.emit(.failed("late"), start: 0)
        second.emit(.ready, start: 0)
        await flushStatusCallbacks()

        XCTAssertEqual(statuses, [.ready])
        XCTAssertEqual(first.stopCount, 1)
        XCTAssertEqual(second.stopCount, 0)
    }

    @MainActor
    func testPairPrivateOverlayForwardsCurrentStatusMessageAndDisconnect() async {
        let overlay = RecordingPrivateOverlayTransport()
        let recorder = MessageRecorder()
        let disconnects = DisconnectRecorder()
        let sink = RecordingMessageSink()
        var statuses: [MacRuntimePrivateOverlayStatus] = []
        let manager = makeManager(
            overlayFactory: PrivateOverlayTransportFactory([overlay]),
            onDisconnect: { disconnects.record($0) }
        )

        XCTAssertTrue(manager.startPairPrivateOverlay(
            fingerprint: "pair-a",
            onStatusChange: { statuses.append($0) },
            onMessage: recorder.handler
        ))
        overlay.emit(.ready, start: 0)
        overlay.emit(
            ProtocolEnvelope(type: "overlay-current", requestID: "overlay-current"),
            sink: sink,
            start: 0
        )
        let connectionID = UUID()
        overlay.emitDisconnect(connectionID)
        await flushStatusCallbacks()

        XCTAssertEqual(overlay.startedFingerprints, ["pair-a"])
        XCTAssertEqual(statuses, [.ready])
        XCTAssertEqual(recorder.envelopes.map(\.type), ["overlay-current"])
        XCTAssertEqual(disconnects.connectionIDs, [connectionID])
    }

    @MainActor
    func testPairPrivateOverlayReplacementInvalidatesStaleStatusAndMessagesBeforeStop() async {
        let first = RecordingPrivateOverlayTransport(statusEmittedOnStop: .failed("during-stop"))
        let second = RecordingPrivateOverlayTransport()
        let recorder = MessageRecorder()
        let sink = RecordingMessageSink()
        var statuses: [MacRuntimePrivateOverlayStatus] = []
        let manager = makeManager(
            overlayFactory: PrivateOverlayTransportFactory([first, second])
        )

        manager.startPairPrivateOverlay(
            fingerprint: "pair-a",
            onStatusChange: { statuses.append($0) },
            onMessage: recorder.handler
        )
        manager.startPairPrivateOverlay(
            fingerprint: "pair-a",
            onStatusChange: { statuses.append($0) },
            onMessage: recorder.handler
        )
        first.emit(.failed("late"), start: 0)
        first.emit(
            ProtocolEnvelope(type: "overlay-stale", requestID: "overlay-stale"),
            sink: sink,
            start: 0
        )
        second.emit(.ready, start: 0)
        second.emit(
            ProtocolEnvelope(type: "overlay-current", requestID: "overlay-current"),
            sink: sink,
            start: 0
        )
        await flushStatusCallbacks()

        XCTAssertEqual(first.stopCount, 1)
        XCTAssertEqual(second.stopCount, 0)
        XCTAssertEqual(statuses, [.ready])
        XCTAssertEqual(recorder.envelopes.map(\.type), ["overlay-current"])
    }

    @MainActor
    func testPairPrivateOverlayAndRelayStoppedStatusesRemoveOnlyTheirOwnCandidate() {
        let overlayA = RecordingPrivateOverlayTransport()
        let overlayB = RecordingPrivateOverlayTransport()
        let relayA = RecordingRelayTransport()
        let relayB = RecordingRelayTransport()
        let manager = makeManager(
            factory: RelayTransportFactory([relayA, relayB]),
            overlayFactory: PrivateOverlayTransportFactory([overlayA, overlayB])
        )

        manager.startPairPrivateOverlay(
            fingerprint: "pair-a",
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("relay-a"),
            onMessage: unusedMessageHandler
        )
        overlayA.emit(.stopped, start: 0)
        manager.stopPair(fingerprint: "pair-a")

        XCTAssertEqual(overlayA.stopCount, 0)
        XCTAssertEqual(relayA.stopCount, 1)

        manager.startPairPrivateOverlay(
            fingerprint: "pair-b",
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-b",
            configuration: configuration("relay-b"),
            onMessage: unusedMessageHandler
        )
        relayB.emit(.stopped, start: 0)
        manager.stopPair(fingerprint: "pair-b")

        XCTAssertEqual(overlayB.stopCount, 1)
        XCTAssertEqual(relayB.stopCount, 0)
    }

    @MainActor
    func testPairPrivateOverlayAndRelayFailuresPreserveTheOtherCandidateUntilPairStop() async {
        let overlayA = RecordingPrivateOverlayTransport()
        let overlayB = RecordingPrivateOverlayTransport()
        let relayA = RecordingRelayTransport()
        let relayB = RecordingRelayTransport()
        let manager = makeManager(
            factory: RelayTransportFactory([relayA, relayB]),
            overlayFactory: PrivateOverlayTransportFactory([overlayA, overlayB])
        )
        var overlayStatuses: [MacRuntimePrivateOverlayStatus] = []
        var relayStatuses: [RelayPeerStatus] = []

        manager.startPairPrivateOverlay(
            fingerprint: "pair-a",
            onStatusChange: { overlayStatuses.append($0) },
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("relay-a"),
            onStatusChange: { relayStatuses.append($0) },
            onMessage: unusedMessageHandler
        )
        overlayA.emit(.failed("overlay-failed"), start: 0)
        relayA.emit(.ready, start: 0)

        manager.startPairPrivateOverlay(
            fingerprint: "pair-b",
            onStatusChange: { overlayStatuses.append($0) },
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-b",
            configuration: configuration("relay-b"),
            onStatusChange: { relayStatuses.append($0) },
            onMessage: unusedMessageHandler
        )
        relayB.emit(.failed("relay-failed"), start: 0)
        overlayB.emit(.ready, start: 0)
        await flushStatusCallbacks()

        XCTAssertEqual(overlayStatuses, [.failed("overlay-failed"), .ready])
        XCTAssertEqual(relayStatuses, [.ready, .failed("relay-failed")])

        manager.stopPair(fingerprint: "pair-a")
        manager.stopPair(fingerprint: "pair-b")

        XCTAssertEqual(overlayA.stopCount, 1)
        XCTAssertEqual(relayA.stopCount, 1)
        XCTAssertEqual(overlayB.stopCount, 1)
        XCTAssertEqual(relayB.stopCount, 1)
    }

    @MainActor
    func testStopPairAndStopAllReleasePairOverlayAndRelayOwnershipExactlyOnce() {
        let overlayA = RecordingPrivateOverlayTransport()
        let overlayB = RecordingPrivateOverlayTransport()
        let relayA = RecordingRelayTransport()
        let relayB = RecordingRelayTransport()
        let manager = makeManager(
            factory: RelayTransportFactory([relayA, relayB]),
            overlayFactory: PrivateOverlayTransportFactory([overlayA, overlayB])
        )

        for (fingerprint, relayID) in [("pair-a", "relay-a"), ("pair-b", "relay-b")] {
            XCTAssertTrue(manager.startPairPrivateOverlay(
                fingerprint: fingerprint,
                onMessage: unusedMessageHandler
            ))
            manager.startPair(
                fingerprint: fingerprint,
                configuration: configuration(relayID),
                onMessage: unusedMessageHandler
            )
        }

        manager.stopPair(fingerprint: "pair-a")
        manager.stopPair(fingerprint: "pair-a")
        manager.stopAll()
        manager.stopAll()

        XCTAssertEqual(overlayA.stopCount, 1)
        XCTAssertEqual(relayA.stopCount, 1)
        XCTAssertEqual(overlayB.stopCount, 1)
        XCTAssertEqual(relayB.stopCount, 1)
    }

    @MainActor
    func testPairPrivateOverlayStartReturnsFalseWithoutInjectedFactory() {
        let manager = makeManager()

        XCTAssertFalse(manager.startPairPrivateOverlay(
            fingerprint: "pair-a",
            onMessage: unusedMessageHandler
        ))
    }

    @MainActor
    func testReplacedRetiredAndStoppedRelayMessageCallbacksAreIgnored() {
        let bootstrap = RecordingRelayTransport()
        let firstPair = RecordingRelayTransport()
        let secondPair = RecordingRelayTransport()
        let manager = makeManager(
            bootstrap: bootstrap,
            factory: RelayTransportFactory([firstPair, secondPair])
        )
        let recorder = MessageRecorder()
        let sink = RecordingMessageSink()

        manager.startBootstrap(
            configuration: configuration("bootstrap-first"),
            onMessage: recorder.handler
        )
        manager.startBootstrap(
            configuration: configuration("bootstrap-second"),
            onMessage: recorder.handler
        )
        bootstrap.emit(ProtocolEnvelope(type: "stale-bootstrap", requestID: "b1"), sink: sink, start: 0)
        bootstrap.emit(ProtocolEnvelope(type: "current-bootstrap", requestID: "b2"), sink: sink, start: 1)
        manager.retireBootstrapAfterCurrentConnection()
        bootstrap.emit(ProtocolEnvelope(type: "retired-bootstrap", requestID: "b3"), sink: sink, start: 1)

        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("pair-first"),
            onMessage: recorder.handler
        )
        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("pair-second"),
            onMessage: recorder.handler
        )
        firstPair.emit(ProtocolEnvelope(type: "stale-pair", requestID: "p1"), sink: sink, start: 0)
        secondPair.emit(ProtocolEnvelope(type: "current-pair", requestID: "p2"), sink: sink, start: 0)
        manager.stopPair(fingerprint: "pair-a")
        secondPair.emit(ProtocolEnvelope(type: "stopped-pair", requestID: "p3"), sink: sink, start: 0)

        XCTAssertEqual(recorder.envelopes.map(\.type), ["current-bootstrap", "current-pair"])
    }

    @MainActor
    func testPairReplacementInvalidatesGenerationBeforeStoppingOldTransport() async {
        let first = RecordingRelayTransport(statusEmittedOnStop: .failed("during-stop"))
        let second = RecordingRelayTransport()
        let manager = makeManager(factory: RelayTransportFactory([first, second]))
        var statuses: [RelayPeerStatus] = []

        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("first"),
            onStatusChange: { statuses.append($0) },
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("second"),
            onStatusChange: { statuses.append($0) },
            onMessage: unusedMessageHandler
        )
        await flushStatusCallbacks()

        XCTAssertTrue(statuses.isEmpty)
        XCTAssertEqual(first.stopCount, 1)
    }

    @MainActor
    func testLateBootstrapStatusFromSupersededGenerationIsIgnored() async {
        let bootstrap = RecordingRelayTransport()
        let manager = makeManager(bootstrap: bootstrap)
        var statuses: [RelayPeerStatus] = []

        manager.startBootstrap(
            configuration: configuration("first"),
            onStatusChange: { statuses.append($0) },
            onMessage: unusedMessageHandler
        )
        manager.startBootstrap(
            configuration: configuration("second"),
            onStatusChange: { statuses.append($0) },
            onMessage: unusedMessageHandler
        )

        bootstrap.emit(.failed("late"), start: 0)
        bootstrap.emit(.waitingForPeer, start: 1)
        await flushStatusCallbacks()

        XCTAssertEqual(statuses, [.waitingForPeer])
        XCTAssertEqual(bootstrap.stopCount, 1)
    }

    @MainActor
    func testStopPairRemovesOnlyRequestedFingerprint() {
        let first = RecordingRelayTransport()
        let second = RecordingRelayTransport()
        let manager = makeManager(factory: RelayTransportFactory([first, second]))

        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("a"),
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-b",
            configuration: configuration("b"),
            onMessage: unusedMessageHandler
        )
        manager.stopPair(fingerprint: "pair-a")
        manager.stopPair(fingerprint: "pair-a")

        XCTAssertEqual(first.stopCount, 1)
        XCTAssertEqual(second.stopCount, 0)

        manager.stopAll()
        XCTAssertEqual(first.stopCount, 1)
        XCTAssertEqual(second.stopCount, 1)
    }

    @MainActor
    func testStopAllStopsEachCurrentlyOwnedTransportExactlyOnce() {
        let bootstrap = RecordingRelayTransport()
        let first = RecordingRelayTransport()
        let second = RecordingRelayTransport()
        let manager = makeManager(
            bootstrap: bootstrap,
            factory: RelayTransportFactory([first, second])
        )

        manager.startBootstrap(
            configuration: configuration("bootstrap"),
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("a"),
            onMessage: unusedMessageHandler
        )
        manager.startPair(
            fingerprint: "pair-b",
            configuration: configuration("b"),
            onMessage: unusedMessageHandler
        )

        manager.stopAll()
        manager.stopAll()

        XCTAssertEqual(bootstrap.stopCount, 1)
        XCTAssertEqual(first.stopCount, 1)
        XCTAssertEqual(second.stopCount, 1)
    }

    @MainActor
    func testRetireBootstrapWithoutActiveGenerationStillSignalsInjectedTransport() {
        let bootstrap = RecordingRelayTransport()
        let manager = makeManager(bootstrap: bootstrap)

        manager.retireBootstrapAfterCurrentConnection()

        XCTAssertEqual(bootstrap.retireCount, 1)
        XCTAssertEqual(bootstrap.stopCount, 0)
    }

    @MainActor
    func testRetiredBootstrapIgnoresLateStatusButRemainsOwnedUntilStopAll() async {
        let bootstrap = RecordingRelayTransport()
        let manager = makeManager(bootstrap: bootstrap)
        var statuses: [RelayPeerStatus] = []

        manager.startBootstrap(
            configuration: configuration("bootstrap"),
            onStatusChange: { statuses.append($0) },
            onMessage: unusedMessageHandler
        )
        manager.retireBootstrapAfterCurrentConnection()
        bootstrap.emit(.failed("retired-connection-failed"), start: 0)
        await flushStatusCallbacks()

        XCTAssertTrue(statuses.isEmpty)
        XCTAssertEqual(bootstrap.retireCount, 1)
        XCTAssertEqual(bootstrap.stopCount, 0)

        manager.stopAll()
        manager.stopAll()
        XCTAssertEqual(bootstrap.stopCount, 1)
    }

    @MainActor
    func testMessageHandlersPassThroughUnchanged() {
        let bootstrap = RecordingRelayTransport()
        let pair = RecordingRelayTransport()
        let manager = makeManager(
            bootstrap: bootstrap,
            factory: RelayTransportFactory([pair])
        )
        let bootstrapRecorder = MessageRecorder()
        let pairRecorder = MessageRecorder()
        let sink = RecordingMessageSink()
        let bootstrapEnvelope = ProtocolEnvelope(type: "bootstrap", requestID: "bootstrap-request")
        let pairEnvelope = ProtocolEnvelope(type: "pair", requestID: "pair-request")

        manager.startBootstrap(
            configuration: configuration("bootstrap"),
            onMessage: bootstrapRecorder.handler
        )
        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("pair"),
            onMessage: pairRecorder.handler
        )

        bootstrap.emit(bootstrapEnvelope, sink: sink, start: 0)
        pair.emit(pairEnvelope, sink: sink, start: 0)

        XCTAssertEqual(bootstrapRecorder.envelopes, [bootstrapEnvelope])
        XCTAssertEqual(pairRecorder.envelopes, [pairEnvelope])
        XCTAssertEqual(bootstrapRecorder.sinkConnectionIDs, [sink.connectionID])
        XCTAssertEqual(pairRecorder.sinkConnectionIDs, [sink.connectionID])
    }

    @MainActor
    func testConcreteRelayPeerClientForwardsDisconnect() {
        let bootstrap = RelayPeerClient()
        let recorder = DisconnectRecorder()
        _ = MacRuntimeConnectionManager(
            bootstrapTransport: bootstrap,
            pairTransportFactory: { RecordingRelayTransport() },
            onDisconnect: { connectionID in recorder.record(connectionID) }
        )
        let connectionID = UUID()

        bootstrap.onDisconnect?(connectionID)

        XCTAssertEqual(recorder.connectionIDs, [connectionID])
    }

    @MainActor
    func testInjectedLocalAndRelayDisconnectCapabilitiesForwardExactConnectionIDs() {
        let local = RecordingRuntimeTransport()
        let bootstrap = RecordingRelayTransport()
        let pair = RecordingRelayTransport()
        let recorder = DisconnectRecorder()
        let manager = makeManager(
            local: local,
            bootstrap: bootstrap,
            factory: RelayTransportFactory([pair]),
            onDisconnect: { recorder.record($0) }
        )
        manager.startPair(
            fingerprint: "pair-a",
            configuration: configuration("pair-a"),
            onMessage: unusedMessageHandler
        )
        let localID = UUID()
        let bootstrapID = UUID()
        let pairID = UUID()

        local.onDisconnect?(localID)
        bootstrap.onDisconnect?(bootstrapID)
        pair.onDisconnect?(pairID)

        XCTAssertEqual(recorder.connectionIDs, [localID, bootstrapID, pairID])
    }

    private let unusedMessageHandler: LocalPeerMessageHandler = { _, _ in }

    @MainActor
    private func makeManager(
        local: any RuntimeTransport = RecordingRuntimeTransport(),
        advertiser: any RuntimeAdvertiser = RecordingRuntimeAdvertiser(),
        bootstrap: RecordingRelayTransport = RecordingRelayTransport(),
        factory: RelayTransportFactory = RelayTransportFactory([]),
        overlayFactory: PrivateOverlayTransportFactory? = nil,
        onDisconnect: @escaping @Sendable (UUID) -> Void = { _ in }
    ) -> MacRuntimeConnectionManager {
        let privateOverlayFactory: (@Sendable () -> any MacRuntimePrivateOverlayTransport)?
        if let overlayFactory {
            privateOverlayFactory = { @Sendable in overlayFactory.make() }
        } else {
            privateOverlayFactory = nil
        }
        return MacRuntimeConnectionManager(
            localTransport: local,
            advertiser: advertiser,
            bootstrapTransport: bootstrap,
            pairTransportFactory: { factory.make() },
            pairPrivateOverlayTransportFactory: privateOverlayFactory,
            onDisconnect: onDisconnect
        )
    }

    private func configuration(_ relayID: String) -> RelayPeerConfiguration {
        RelayPeerConfiguration(host: "relay.example", port: 443, relayID: relayID)
    }

    private static func occupyTCPPort() throws -> (socket: Int32, port: UInt16) {
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else {
            throw socketError()
        }

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = UInt16(0).bigEndian
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let bound = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                Darwin.bind(socket, sockaddrPointer, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard bound == 0, Darwin.listen(socket, 1) == 0 else {
            Darwin.close(socket)
            throw socketError()
        }

        var boundAddress = sockaddr_in()
        var boundAddressLength = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &boundAddress) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                Darwin.getsockname(socket, sockaddrPointer, &boundAddressLength)
            }
        }
        guard named == 0 else {
            Darwin.close(socket)
            throw socketError()
        }
        return (socket, UInt16(bigEndian: boundAddress.sin_port))
    }

    private static func socketError() -> NSError {
        NSError(
            domain: NSPOSIXErrorDomain,
            code: Int(errno),
            userInfo: [NSLocalizedDescriptionKey: String(cString: strerror(errno))]
        )
    }

    @MainActor
    private func waitForCondition(
        timeout: TimeInterval = 2,
        _ condition: @escaping () -> Bool
    ) async -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if condition() { return true }
            try? await Task.sleep(nanoseconds: 10_000_000)
        }
        return condition()
    }

    @MainActor
    private func flushStatusCallbacks() async {
        await Task.yield()
        await Task.yield()
    }
}

private enum LocalOwnershipEvent: Equatable {
    case localStart(port: UInt16)
    case localStop
    case advertiserStart(port: Int32, metadata: RuntimeAdvertisementMetadata)
    case advertiserStop
}

private final class LocalOwnershipEventRecorder {
    private(set) var events: [LocalOwnershipEvent] = []

    func record(_ event: LocalOwnershipEvent) {
        events.append(event)
    }
}

private final class RecordingRuntimeTransport: RuntimeTransport, RuntimeDisconnectReporting,
    RuntimeStatusReporting, @unchecked Sendable
{
    private var statusesAfterStart: [PeerServerStatus]
    private let events: LocalOwnershipEventRecorder?
    private var messageHandlers: [LocalPeerMessageHandler] = []
    private var statusHandlers: [(@Sendable (PeerServerStatus) -> Void)?] = []
    var onDisconnect: (@Sendable (UUID) -> Void)?
    var onStatusChange: (@Sendable (PeerServerStatus) -> Void)?

    private(set) var status = PeerServerStatus.stopped
    private(set) var startedPorts: [UInt16] = []
    private(set) var stopCount = 0

    init(
        statusesAfterStart: [PeerServerStatus] = [],
        events: LocalOwnershipEventRecorder? = nil
    ) {
        self.statusesAfterStart = statusesAfterStart
        self.events = events
    }

    func start(port: UInt16, onMessage: @escaping LocalPeerMessageHandler) {
        startedPorts.append(port)
        messageHandlers.append(onMessage)
        statusHandlers.append(onStatusChange)
        status = statusesAfterStart.isEmpty
            ? .listening(port: port)
            : statusesAfterStart.removeFirst()
        events?.record(.localStart(port: port))
    }

    func stop() {
        stopCount += 1
        status = .stopped
        events?.record(.localStop)
    }

    func emit(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink, start index: Int) {
        messageHandlers[index](envelope, sink)
    }

    func setStatus(_ status: PeerServerStatus) {
        self.status = status
    }

    func emitStatus(_ status: PeerServerStatus, start index: Int) {
        self.status = status
        statusHandlers[index]?(status)
    }
}

private final class RecordingRuntimeAdvertiser: RuntimeAdvertiser,
    RuntimeAdvertisementStatusReporting
{
    struct Start: Equatable {
        let port: Int32
        let metadata: RuntimeAdvertisementMetadata
    }

    private let events: LocalOwnershipEventRecorder?
    private var statusesAfterStart: [RuntimeAdvertisementStatus]
    private var statusHandlers: [
        (@Sendable (RuntimeAdvertisementStatus) -> Void)?
    ] = []
    private(set) var starts: [Start] = []
    private(set) var stopCount = 0
    private(set) var advertisementStatus = RuntimeAdvertisementStatus.stopped
    var onAdvertisementStatusChange: (
        @Sendable (RuntimeAdvertisementStatus) -> Void
    )?

    init(
        events: LocalOwnershipEventRecorder? = nil,
        statusesAfterStart: [RuntimeAdvertisementStatus] = []
    ) {
        self.events = events
        self.statusesAfterStart = statusesAfterStart
    }

    func start(port: Int32, metadata: RuntimeAdvertisementMetadata) {
        starts.append(.init(port: port, metadata: metadata))
        statusHandlers.append(onAdvertisementStatusChange)
        advertisementStatus = statusesAfterStart.isEmpty
            ? .published
            : statusesAfterStart.removeFirst()
        events?.record(.advertiserStart(port: port, metadata: metadata))
    }

    func stop() {
        stopCount += 1
        advertisementStatus = .stopped
        events?.record(.advertiserStop)
    }

    func emitStatus(
        _ status: RuntimeAdvertisementStatus,
        start index: Int
    ) {
        advertisementStatus = status
        statusHandlers[index]?(status)
    }
}

private final class RelayTransportFactory: @unchecked Sendable {
    private let lock = NSLock()
    private var transports: [RecordingRelayTransport]

    init(_ transports: [RecordingRelayTransport]) {
        self.transports = transports
    }

    func make() -> any RelayPeerTransport {
        lock.withLock {
            precondition(!transports.isEmpty, "No relay transport queued")
            return transports.removeFirst()
        }
    }
}

private final class RecordingRelayTransport: MacRuntimeBootstrapRetiringTransport, RuntimeDisconnectReporting, @unchecked Sendable {
    private let lock = NSLock()
    private let statusEmittedOnStop: RelayPeerStatus?
    private var storedStopCount = 0
    private var storedRetireCount = 0
    private var statusHandlers: [(@Sendable (RelayPeerStatus) -> Void)?] = []
    private var messageHandlers: [LocalPeerMessageHandler] = []
    var onDisconnect: (@Sendable (UUID) -> Void)?

    init(statusEmittedOnStop: RelayPeerStatus? = nil) {
        self.statusEmittedOnStop = statusEmittedOnStop
    }

    var stopCount: Int {
        lock.withLock { storedStopCount }
    }

    var retireCount: Int {
        lock.withLock { storedRetireCount }
    }

    func start(
        configuration: RelayPeerConfiguration,
        onStatusChange: (@Sendable (RelayPeerStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        lock.withLock {
            statusHandlers.append(onStatusChange)
            messageHandlers.append(onMessage)
        }
    }

    func stop() {
        let handler = lock.withLock {
            storedStopCount += 1
            return statusHandlers.last ?? nil
        }
        if let statusEmittedOnStop {
            handler?(statusEmittedOnStop)
        }
    }

    func retireAfterCurrentConnection() {
        lock.withLock {
            storedRetireCount += 1
        }
    }

    func emit(_ status: RelayPeerStatus, start index: Int) {
        let handler = lock.withLock { statusHandlers[index] }
        handler?(status)
    }

    func emit(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink, start index: Int) {
        let handler = lock.withLock { messageHandlers[index] }
        handler(envelope, sink)
    }
}

private final class PrivateOverlayTransportFactory: @unchecked Sendable {
    private let lock = NSLock()
    private var transports: [RecordingPrivateOverlayTransport]

    init(_ transports: [RecordingPrivateOverlayTransport]) {
        self.transports = transports
    }

    func make() -> any MacRuntimePrivateOverlayTransport {
        lock.withLock {
            precondition(!transports.isEmpty, "No private-overlay transport queued")
            return transports.removeFirst()
        }
    }
}

private final class RecordingPrivateOverlayTransport: MacRuntimePrivateOverlayTransport, @unchecked Sendable {
    private let lock = NSLock()
    private let statusEmittedOnStop: MacRuntimePrivateOverlayStatus?
    private var storedOnDisconnect: (@Sendable (UUID) -> Void)?
    private var storedStartedFingerprints: [String] = []
    private var storedStopCount = 0
    private var statusHandlers: [(@Sendable (MacRuntimePrivateOverlayStatus) -> Void)?] = []
    private var messageHandlers: [LocalPeerMessageHandler] = []

    init(statusEmittedOnStop: MacRuntimePrivateOverlayStatus? = nil) {
        self.statusEmittedOnStop = statusEmittedOnStop
    }

    var onDisconnect: (@Sendable (UUID) -> Void)? {
        get { lock.withLock { storedOnDisconnect } }
        set { lock.withLock { storedOnDisconnect = newValue } }
    }

    var startedFingerprints: [String] {
        lock.withLock { storedStartedFingerprints }
    }

    var stopCount: Int {
        lock.withLock { storedStopCount }
    }

    func start(
        clientKeyFingerprint: String,
        onStatusChange: (@Sendable (MacRuntimePrivateOverlayStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        lock.withLock {
            storedStartedFingerprints.append(clientKeyFingerprint)
            statusHandlers.append(onStatusChange)
            messageHandlers.append(onMessage)
        }
    }

    func stop() {
        let handler = lock.withLock {
            storedStopCount += 1
            return statusHandlers.last ?? nil
        }
        if let statusEmittedOnStop {
            handler?(statusEmittedOnStop)
        }
    }

    func emit(_ status: MacRuntimePrivateOverlayStatus, start index: Int) {
        let handler = lock.withLock { statusHandlers[index] }
        handler?(status)
    }

    func emit(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink, start index: Int) {
        let handler = lock.withLock { messageHandlers[index] }
        handler(envelope, sink)
    }

    func emitDisconnect(_ connectionID: UUID) {
        let handler = lock.withLock { storedOnDisconnect }
        handler?(connectionID)
    }
}

private final class MessageRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var storedEnvelopes: [ProtocolEnvelope] = []
    private var storedSinkConnectionIDs: [UUID] = []

    var handler: LocalPeerMessageHandler {
        { [weak self] envelope, sink in
            self?.lock.withLock {
                self?.storedEnvelopes.append(envelope)
                self?.storedSinkConnectionIDs.append(sink.connectionID)
            }
        }
    }

    var envelopes: [ProtocolEnvelope] {
        lock.withLock { storedEnvelopes }
    }

    var sinkConnectionIDs: [UUID] {
        lock.withLock { storedSinkConnectionIDs }
    }
}

private final class DisconnectRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var storedConnectionIDs: [UUID] = []

    var connectionIDs: [UUID] {
        lock.withLock { storedConnectionIDs }
    }

    func record(_ connectionID: UUID) {
        lock.withLock {
            storedConnectionIDs.append(connectionID)
        }
    }
}

private final class RecordingMessageSink: RuntimeMessageSink, @unchecked Sendable {
    let connectionID = UUID()

    func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result {
        try operation(nil)
    }

    func send(_ envelope: ProtocolEnvelope) {}
    func close() {}
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
