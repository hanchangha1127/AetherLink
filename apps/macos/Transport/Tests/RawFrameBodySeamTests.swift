import BridgeProtocol
import Foundation
import Network
import XCTest
@_spi(ProductionRawEndpointAuthorization)
@_spi(ProductionRawEndpointOwnership)
@_spi(ProductionRawEndpointTesting)
@testable import Transport

final class RawFrameBodySeamTests: XCTestCase {
    func testOrderedWriterWaitsForContentProcessedBeforeSubmittingNextFrame() {
        let harness = ControlledFrameWriterHarness()
        let writer = LocalPeerOrderedFrameWriter(
            label: "raw-frame-order-test",
            write: harness.write,
            closeTransport: harness.close
        )
        let completions = LockedValues<Bool>()

        writer.send(Data([1])) { completions.append($0) }
        writer.send(Data([2])) { completions.append($0) }

        XCTAssertEqual(harness.waitForSubmissionCount(1), [Data([1])])
        XCTAssertFalse(harness.hasSubmissionCount(2))

        harness.completeSubmission(at: 0, succeeded: true)
        XCTAssertEqual(harness.waitForSubmissionCount(2), [Data([1]), Data([2])])
        harness.completeSubmission(at: 1, succeeded: true)

        XCTAssertEqual(completions.waitForCount(2), [true, true])
        XCTAssertEqual(harness.closeCount, 0)
    }

    func testOrderedWriterFailureClosesTransportAndRejectsQueuedFrames() {
        let harness = ControlledFrameWriterHarness()
        let writer = LocalPeerOrderedFrameWriter(
            label: "raw-frame-failure-test",
            write: harness.write,
            closeTransport: harness.close
        )
        let completions = LockedValues<Bool>()

        writer.send(Data([1])) { completions.append($0) }
        writer.send(Data([2])) { completions.append($0) }
        XCTAssertEqual(harness.waitForSubmissionCount(1), [Data([1])])

        harness.completeSubmission(at: 0, succeeded: false)

        XCTAssertEqual(completions.waitForCount(2), [false, false])
        XCTAssertEqual(harness.waitForCloseCount(1), 1)
        XCTAssertFalse(harness.hasSubmissionCount(2))
    }

    func testOrderedWriterOverflowFailsClosedAndCompletesEveryWaiter() {
        let harness = ControlledFrameWriterHarness()
        let writer = LocalPeerOrderedFrameWriter(
            label: "raw-frame-overflow-test",
            maximumOutstandingFrames: 2,
            write: harness.write,
            closeTransport: harness.close
        )
        let completions = LockedValues<Bool>()

        writer.send(Data([1])) { completions.append($0) }
        writer.send(Data([2])) { completions.append($0) }
        writer.send(Data([3])) { completions.append($0) }

        XCTAssertEqual(harness.waitForSubmissionCount(1), [Data([1])])
        XCTAssertEqual(harness.waitForCloseCount(1), 1)
        XCTAssertEqual(completions.waitForCount(3), [false, false, false])
        // Simulate an underlying completion racing after fail-closed cancel.
        harness.completeSubmission(at: 0, succeeded: true)

        XCTAssertEqual(completions.valuesSnapshot, [false, false, false])
        XCTAssertFalse(harness.hasSubmissionCount(2))
    }

    func testOrderedWriterCloseRejectsQueuedFramesAndClosesTransport() {
        let harness = ControlledFrameWriterHarness()
        let writer = LocalPeerOrderedFrameWriter(
            label: "raw-frame-close-test",
            write: harness.write,
            closeTransport: harness.close
        )
        let completions = LockedValues<Bool>()

        writer.send(Data([1])) { completions.append($0) }
        writer.send(Data([2])) { completions.append($0) }
        XCTAssertEqual(harness.waitForSubmissionCount(1), [Data([1])])

        writer.close()
        XCTAssertEqual(harness.waitForCloseCount(1), 1)
        XCTAssertEqual(completions.waitForCount(2), [false, false])
        harness.completeSubmission(at: 0, succeeded: false)

        XCTAssertEqual(completions.valuesSnapshot, [false, false])
        XCTAssertFalse(harness.hasSubmissionCount(2))
    }

    func testRawAndEnvelopeSendAPIsCannotBeMixed() {
        let rawGate = LocalPeerFrameBodyModeGate(mode: .raw)
        XCTAssertTrue(rawGate.require(.raw))
        XCTAssertFalse(rawGate.require(.protocolEnvelope))
        XCTAssertFalse(rawGate.require(.raw), "a mode violation must leave the gate terminal")

        let envelopeGate = LocalPeerFrameBodyModeGate(mode: .protocolEnvelope)
        XCTAssertTrue(envelopeGate.require(.protocolEnvelope))
        XCTAssertFalse(envelopeGate.require(.raw))
        XCTAssertFalse(envelopeGate.require(.protocolEnvelope))
    }

    func testRawBodyRejectsEmptyAndOversizedPayloadBeforeSubmission() {
        let encoder = LocalPeerRawFrameBodyEncoder()
        for body in [Data(), Data(repeating: 0xA5, count: ProtocolCodec.maxFrameBytes + 1)] {
            XCTAssertThrowsError(try encoder.encode(body))
        }

        let maximum = Data(repeating: 0xA5, count: ProtocolCodec.maxFrameBytes)
        XCTAssertEqual(try? encoder.encode(maximum).count, maximum.count + 4)
    }

    func testAcceptedRawEndpointClaimTransfersOnceAndInstallsOneHandler() {
        let sink = ClaimTestRawSink()
        let installs = LockedValues<Bool>()
        let claim = RuntimeAcceptedRawEndpointClaim.testing(
            rawSink: sink,
            routeDescriptor: .testing(),
            installHandler: { _ in
                installs.append(true)
                return true
            }
        )
        let transfers = LockedValues<Bool>()

        DispatchQueue.concurrentPerform(iterations: 64) { _ in
            transfers.append(claim.transferRawSinkToChannel() != nil)
        }

        XCTAssertEqual(transfers.valuesSnapshot.filter { $0 }.count, 1)
        XCTAssertTrue(claim.installRawFrameBodyHandler { _ in })
        XCTAssertFalse(claim.installRawFrameBodyHandler { _ in })
        XCTAssertEqual(installs.valuesSnapshot, [true])

        claim.close()
        claim.close()
        XCTAssertEqual(sink.closeCount, 1)
    }

    func testAcceptedRawEndpointCloseBeforeTransferFailsClosed() {
        let sink = ClaimTestRawSink()
        let claim = RuntimeAcceptedRawEndpointClaim.testing(
            rawSink: sink,
            routeDescriptor: .testing(),
            installHandler: { _ in true }
        )

        claim.close()

        XCTAssertNil(claim.transferRawSinkToChannel())
        XCTAssertFalse(claim.installRawFrameBodyHandler { _ in })
        XCTAssertEqual(sink.closeCount, 1)
    }

    func testProductionAcceptedRawSessionDoesNotReceiveUntilInstallAndSerializesBodies()
        async
    {
        let accepted = AcceptedRawSessionRecorder()
        let disconnected = LockedValues<UUID>()
        let clock = AcceptedRawTestClock(nowMs: 150)
        let scheduler = ControlledAcceptedRawScheduler()
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: accepted.append,
            onDisconnect: { disconnected.append($0) },
            nowMs: { clock.nowMs },
            schedule: scheduler.schedule
        )
        let io = ControlledAcceptedRawConnectionIO()
        let authorization = makeAcceptedRawAuthorization(
            sessionID: "session-serial",
            effectiveNotBeforeMs: 100,
            expiresAtMs: 100_000
        )

        XCTAssertTrue(acceptor.supply(authorization))
        XCTAssertTrue(acceptor.accept(io))
        guard let session = accepted.first else {
            return XCTFail("Expected accepted raw session")
        }
        XCTAssertEqual(session.routeDescriptor.sessionID, "session-serial")
        XCTAssertEqual(io.startCount, 1)
        XCTAssertEqual(io.receiveLengths, [], "accept must not register a receive")

        guard let claim = session.takeRawEndpointClaim() else {
            return XCTFail("Expected one endpoint claim")
        }
        XCTAssertNotNil(claim.transferRawSinkToChannel())
        let handler = ControlledAcceptedRawHandler()
        XCTAssertTrue(claim.installRawFrameBodyHandler { body in
            await handler.handle(body)
        })
        XCTAssertEqual(io.waitForReceiveCount(1), [4])
        scheduler.runAll()
        XCTAssertEqual(io.cancelCount, 0, "installed handler owns the live session")

        io.completeNextReceive(with: Data([0, 0, 0, 2]))
        XCTAssertEqual(io.waitForReceiveCount(2), [4, 2])
        let rawBody = Data([0xA5, 0x5A])
        io.completeNextReceive(with: rawBody)
        await handler.waitUntilEntered()

        XCTAssertEqual(io.receiveLengths, [4, 2], "next frame must await the handler")
        let receivedBodies = await handler.receivedBodies()
        XCTAssertEqual(receivedBodies, [rawBody])

        await handler.release()
        XCTAssertEqual(io.waitForReceiveCount(3), [4, 2, 4])

        claim.close()
        XCTAssertEqual(io.cancelCount, 1)
        XCTAssertEqual(disconnected.waitForCount(1), [session.connectionID])
    }

    func testProductionAcceptorRejectsDuplicatePendingAuthorizationAndUnauthorizedPeer() {
        let accepted = AcceptedRawSessionRecorder()
        let disconnected = LockedValues<UUID>()
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: accepted.append,
            onDisconnect: { disconnected.append($0) }
        )
        let firstAuthorization = makeAcceptedRawAuthorization(sessionID: "session-first")
        let duplicateAuthorization = makeAcceptedRawAuthorization(sessionID: "session-duplicate")

        XCTAssertTrue(acceptor.supply(firstAuthorization))
        XCTAssertFalse(acceptor.supply(duplicateAuthorization))
        XCTAssertNil(
            duplicateAuthorization.takeRouteDescriptorForAcceptedConnection(
                nowMs: 1
            ),
            "rejected authorization must be terminal"
        )

        let authorizedIO = ControlledAcceptedRawConnectionIO()
        XCTAssertTrue(acceptor.accept(authorizedIO))
        XCTAssertEqual(accepted.first?.routeDescriptor.sessionID, "session-first")

        let unauthorizedIO = ControlledAcceptedRawConnectionIO()
        XCTAssertFalse(acceptor.accept(unauthorizedIO))
        XCTAssertEqual(unauthorizedIO.startCount, 0)
        XCTAssertEqual(unauthorizedIO.receiveLengths, [])
        XCTAssertEqual(unauthorizedIO.cancelCount, 1)

        acceptor.stop()
        acceptor.stop()
        XCTAssertEqual(authorizedIO.cancelCount, 1)
        XCTAssertEqual(disconnected.valuesSnapshot.count, 1)

        let stoppedAuthorization = makeAcceptedRawAuthorization(sessionID: "session-stopped")
        XCTAssertFalse(acceptor.supply(stoppedAuthorization))
        XCTAssertNil(
            stoppedAuthorization.takeRouteDescriptorForAcceptedConnection(
                nowMs: 1
            )
        )
    }

    func testProductionAcceptedRawClaimInstallCloseAndDisconnectAreOneShot() {
        let accepted = AcceptedRawSessionRecorder()
        let disconnected = LockedValues<UUID>()
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: accepted.append,
            onDisconnect: { disconnected.append($0) }
        )
        XCTAssertTrue(acceptor.supply(makeAcceptedRawAuthorization(sessionID: "session-once")))
        let io = ControlledAcceptedRawConnectionIO()
        XCTAssertTrue(acceptor.accept(io))
        guard let session = accepted.first,
              let claim = session.takeRawEndpointClaim() else {
            return XCTFail("Expected accepted claim")
        }

        XCTAssertNil(session.takeRawEndpointClaim())
        XCTAssertFalse(claim.installRawFrameBodyHandler { _ in })
        XCTAssertNotNil(claim.transferRawSinkToChannel())
        XCTAssertNil(claim.transferRawSinkToChannel())
        XCTAssertTrue(claim.installRawFrameBodyHandler { _ in })
        XCTAssertFalse(claim.installRawFrameBodyHandler { _ in })
        XCTAssertEqual(io.waitForReceiveCount(1), [4])

        claim.close()
        claim.close()
        io.signalTerminal()

        XCTAssertEqual(io.cancelCount, 1)
        XCTAssertEqual(disconnected.waitForCount(1), [session.connectionID])
        XCTAssertEqual(disconnected.valuesSnapshot.count, 1)
        XCTAssertNil(session.takeRawEndpointClaim())
    }

    func testProductionAcceptedRawMalformedOrTruncatedFrameFailsClosed() {
        let malformedFrames: [(String, Data, Data?)] = [
            ("session-empty", Data([0, 0, 0, 0]), nil),
            ("session-oversized", Data([0x7F, 0xFF, 0xFF, 0xFF]), nil),
            ("session-truncated", Data([0, 0, 0, 3]), Data([1, 2])),
        ]
        for (sessionID, length, body) in malformedFrames {
            let accepted = AcceptedRawSessionRecorder()
            let disconnected = LockedValues<UUID>()
            let acceptor = LocalPeerAcceptedRawSessionAcceptor(
                onAccepted: accepted.append,
                onDisconnect: { disconnected.append($0) }
            )
            let io = ControlledAcceptedRawConnectionIO()
            XCTAssertTrue(acceptor.supply(makeAcceptedRawAuthorization(sessionID: sessionID)))
            XCTAssertTrue(acceptor.accept(io))
            guard let session = accepted.first,
                  let claim = session.takeRawEndpointClaim() else {
                return XCTFail("Expected accepted claim")
            }
            XCTAssertNotNil(claim.transferRawSinkToChannel())
            let handled = LockedValues<Data>()
            XCTAssertTrue(claim.installRawFrameBodyHandler { handled.append($0) })
            XCTAssertEqual(io.waitForReceiveCount(1), [4])

            io.completeNextReceive(with: length)
            if let body {
                XCTAssertEqual(io.waitForReceiveCount(2), [4, 3])
                io.completeNextReceive(with: body)
            }

            XCTAssertEqual(disconnected.waitForCount(1), [session.connectionID])
            XCTAssertEqual(io.cancelCount, 1)
            XCTAssertEqual(handled.valuesSnapshot, [])
        }
    }

    func testProductionAcceptedRawListenerPolicyRequiresIPv4Loopback() {
        let port: UInt16 = 43170
        let parameters = LocalPeerAcceptedRawListenerPolicy.parameters(port: port)
        let expected = NWEndpoint.hostPort(
            host: .ipv4(IPv4Address("127.0.0.1")!),
            port: NWEndpoint.Port(rawValue: port)!
        )

        XCTAssertEqual(parameters.requiredLocalEndpoint, expected)
    }

    func testProductionAuthorizationRejectsInvalidWindowAndAcceptTimeExpiry() {
        XCTAssertThrowsError(
            try issueAcceptedRawAuthorization(
                sessionID: "session-invalid-window",
                effectiveNotBeforeMs: 200,
                expiresAtMs: 200
            )
        ) { error in
            XCTAssertEqual(
                error as? RuntimeAcceptedRawSessionAuthorizationError,
                .invalidValidityWindow
            )
        }

        let clock = AcceptedRawTestClock(nowMs: 150)
        let scheduler = ControlledAcceptedRawScheduler()
        let accepted = AcceptedRawSessionRecorder()
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: accepted.append,
            onDisconnect: { _ in },
            nowMs: { clock.nowMs },
            schedule: scheduler.schedule
        )
        let authorization = makeAcceptedRawAuthorization(
            sessionID: "session-expired-at-accept",
            effectiveNotBeforeMs: 100,
            expiresAtMs: 200
        )
        XCTAssertTrue(acceptor.supply(authorization))

        clock.nowMs = 200
        let io = ControlledAcceptedRawConnectionIO()
        XCTAssertFalse(acceptor.accept(io))
        XCTAssertEqual(io.startCount, 0)
        XCTAssertEqual(io.receiveLengths, [])
        XCTAssertEqual(io.cancelCount, 1)
        XCTAssertEqual(accepted.count, 0)
    }

    func testProductionPendingAuthorizationExpiresAtEarlierBound() {
        let clock = AcceptedRawTestClock(nowMs: 150)
        let scheduler = ControlledAcceptedRawScheduler()
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: { _ in },
            onDisconnect: { _ in },
            nowMs: { clock.nowMs },
            schedule: scheduler.schedule
        )
        let authorization = makeAcceptedRawAuthorization(
            sessionID: "session-pending-expiry",
            effectiveNotBeforeMs: 100,
            expiresAtMs: 160
        )

        XCTAssertTrue(acceptor.supply(authorization))
        XCTAssertEqual(scheduler.delays, [10_000_000])
        XCTAssertTrue(scheduler.runNext())

        let io = ControlledAcceptedRawConnectionIO()
        XCTAssertFalse(acceptor.accept(io))
        XCTAssertEqual(io.startCount, 0)
        XCTAssertEqual(io.receiveLengths, [])
        XCTAssertEqual(io.cancelCount, 1)
        XCTAssertNil(
            authorization.takeRouteDescriptorForAcceptedConnection(nowMs: 155)
        )
    }

    func testProductionHandlerInstallationWaitHasFixedDeadlineAndClosesOnce() {
        let clock = AcceptedRawTestClock(nowMs: 150)
        let scheduler = ControlledAcceptedRawScheduler()
        let accepted = AcceptedRawSessionRecorder()
        let disconnected = LockedValues<UUID>()
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: accepted.append,
            onDisconnect: { disconnected.append($0) },
            nowMs: { clock.nowMs },
            schedule: scheduler.schedule
        )
        XCTAssertTrue(acceptor.supply(makeAcceptedRawAuthorization(
            sessionID: "session-handler-timeout",
            effectiveNotBeforeMs: 100,
            expiresAtMs: 100_000
        )))
        let io = ControlledAcceptedRawConnectionIO()
        XCTAssertTrue(acceptor.accept(io))
        guard let session = accepted.first else {
            return XCTFail("Expected accepted session")
        }

        XCTAssertEqual(
            scheduler.delays,
            [
                LocalPeerAcceptedRawSessionAcceptor
                    .maximumPendingAuthorizationNanoseconds,
                LocalPeerAcceptedRawSessionAcceptor
                    .maximumHandlerInstallationNanoseconds,
            ]
        )
        XCTAssertEqual(io.receiveLengths, [])
        scheduler.runAll()

        XCTAssertEqual(io.cancelCount, 1)
        XCTAssertEqual(disconnected.waitForCount(1), [session.connectionID])
        XCTAssertEqual(disconnected.valuesSnapshot.count, 1)
        XCTAssertNil(session.takeRawEndpointClaim())
    }

    func testProductionStopAndConnectionTerminalRaceDisconnectsExactlyOnce() {
        for iteration in 0..<64 {
            let accepted = AcceptedRawSessionRecorder()
            let disconnected = LockedValues<UUID>()
            let acceptor = LocalPeerAcceptedRawSessionAcceptor(
                onAccepted: accepted.append,
                onDisconnect: { disconnected.append($0) },
                nowMs: { 150 },
                schedule: { _, _ in }
            )
            XCTAssertTrue(acceptor.supply(makeAcceptedRawAuthorization(
                sessionID: "session-terminal-race-\(iteration)",
                effectiveNotBeforeMs: 100,
                expiresAtMs: 1_000
            )))
            let io = ControlledAcceptedRawConnectionIO()
            XCTAssertTrue(acceptor.accept(io))

            DispatchQueue.concurrentPerform(iterations: 2) { index in
                if index == 0 {
                    acceptor.stop()
                } else {
                    io.signalTerminal()
                }
            }

            XCTAssertEqual(disconnected.waitForCount(1).count, 1)
            XCTAssertEqual(disconnected.valuesSnapshot.count, 1)
            XCTAssertEqual(io.cancelCount, 1)
        }
    }

    func testProductionStopBeforeAcceptedDeliverySuppressesLateCallback() {
        let scheduler = PausingSecondAcceptedRawScheduler()
        let accepted = AcceptedRawSessionRecorder()
        let disconnected = LockedValues<UUID>()
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: accepted.append,
            onDisconnect: { disconnected.append($0) },
            nowMs: { 150 },
            schedule: scheduler.schedule
        )
        XCTAssertTrue(acceptor.supply(makeAcceptedRawAuthorization(
            sessionID: "session-stop-before-delivery",
            effectiveNotBeforeMs: 100,
            expiresAtMs: 1_000
        )))
        let io = ControlledAcceptedRawConnectionIO()
        let acceptResult = LockedValues<Bool>()

        DispatchQueue.global().async {
            acceptResult.append(acceptor.accept(io))
        }
        XCTAssertTrue(scheduler.waitUntilSecondScheduleEntered())

        acceptor.stop()
        XCTAssertEqual(accepted.count, 0)
        XCTAssertEqual(io.cancelCount, 1)
        scheduler.resumeSecondSchedule()

        XCTAssertEqual(acceptResult.waitForCount(1), [false])
        XCTAssertEqual(accepted.count, 0)
        XCTAssertEqual(disconnected.valuesSnapshot.count, 1)
    }

    func testProductionExternalStopWaitsForAcceptedCallbackToReturn() {
        let callbackPause = AcceptedRawCallbackPause()
        let accepted = AcceptedRawSessionRecorder()
        let disconnected = LockedValues<UUID>()
        let stopWaiting = DispatchSemaphore(value: 0)
        let stopReturned = DispatchSemaphore(value: 0)
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: { session in
                accepted.append(session)
                callbackPause.pause()
            },
            onDisconnect: { disconnected.append($0) },
            nowMs: { 150 },
            schedule: { _, _ in },
            onStopWaitingForDelivery: { stopWaiting.signal() }
        )
        XCTAssertTrue(acceptor.supply(makeAcceptedRawAuthorization(
            sessionID: "session-stop-waits-for-delivery",
            effectiveNotBeforeMs: 100,
            expiresAtMs: 1_000
        )))
        let io = ControlledAcceptedRawConnectionIO()
        let acceptResult = LockedValues<Bool>()
        DispatchQueue.global().async {
            acceptResult.append(acceptor.accept(io))
        }
        XCTAssertTrue(callbackPause.waitUntilPaused())

        DispatchQueue.global().async {
            acceptor.stop()
            stopReturned.signal()
        }
        XCTAssertEqual(stopWaiting.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(stopReturned.wait(timeout: .now()), .timedOut)
        XCTAssertEqual(io.cancelCount, 0)

        callbackPause.resume()
        XCTAssertEqual(stopReturned.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(acceptResult.waitForCount(1), [false])
        XCTAssertEqual(io.cancelCount, 1)
        XCTAssertEqual(disconnected.valuesSnapshot.count, 1)
    }

    func testProductionAcceptedCallbackMayStopReentrantlyAndFailsClosed() {
        let acceptorBox = WeakAcceptedRawAcceptorBox()
        let acceptedIDs = LockedValues<UUID>()
        let disconnected = LockedValues<UUID>()
        let stopWaits = LockedValues<Bool>()
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: { session in
                acceptedIDs.append(session.connectionID)
                acceptorBox.acceptor?.stop()
            },
            onDisconnect: { disconnected.append($0) },
            nowMs: { 150 },
            schedule: { _, _ in },
            onStopWaitingForDelivery: { stopWaits.append(true) }
        )
        acceptorBox.acceptor = acceptor
        XCTAssertTrue(acceptor.supply(makeAcceptedRawAuthorization(
            sessionID: "session-reentrant-stop",
            effectiveNotBeforeMs: 100,
            expiresAtMs: 1_000
        )))
        let io = ControlledAcceptedRawConnectionIO()

        XCTAssertFalse(acceptor.accept(io))
        XCTAssertEqual(acceptedIDs.valuesSnapshot.count, 1)
        XCTAssertEqual(io.cancelCount, 1)
        XCTAssertEqual(disconnected.valuesSnapshot, acceptedIDs.valuesSnapshot)
        XCTAssertEqual(stopWaits.valuesSnapshot, [])
    }

    private func makeAcceptedRawAuthorization(
        sessionID: String,
        effectiveNotBeforeMs: UInt64 = 1,
        expiresAtMs: UInt64 = .max
    ) -> RuntimeAcceptedRawSessionAuthorization {
        try! issueAcceptedRawAuthorization(
            sessionID: sessionID,
            effectiveNotBeforeMs: effectiveNotBeforeMs,
            expiresAtMs: expiresAtMs
        )
    }

    private func issueAcceptedRawAuthorization(
        sessionID: String,
        effectiveNotBeforeMs: UInt64,
        expiresAtMs: UInt64
    ) throws -> RuntimeAcceptedRawSessionAuthorization {
        try RuntimeAcceptedRawSessionAuthorization.issue(
            sessionID: sessionID,
            object7And26BindingDigest: String(repeating: "2", count: 64),
            routeKind: "p2p_direct",
            pairBindingDigest: String(repeating: "3", count: 64),
            pairEpoch: 1,
            generation: 1,
            clientIdentityFingerprint: String(repeating: "4", count: 64),
            runtimeIdentityFingerprint: String(repeating: "5", count: 64),
            connectorInputCommitmentDigest: String(repeating: "6", count: 64),
            effectiveNotBeforeMs: effectiveNotBeforeMs,
            expiresAtMs: expiresAtMs
        )
    }
}

private final class WeakAcceptedRawAcceptorBox: @unchecked Sendable {
    weak var acceptor: LocalPeerAcceptedRawSessionAcceptor?
}

private final class AcceptedRawCallbackPause: @unchecked Sendable {
    private let paused = DispatchSemaphore(value: 0)
    private let resumeSignal = DispatchSemaphore(value: 0)

    func pause() {
        paused.signal()
        _ = resumeSignal.wait(timeout: .now() + 2)
    }

    func waitUntilPaused() -> Bool {
        paused.wait(timeout: .now() + 2) == .success
    }

    func resume() {
        resumeSignal.signal()
    }
}

private final class PausingSecondAcceptedRawScheduler: @unchecked Sendable {
    private let lock = NSLock()
    private let secondScheduleEntered = DispatchSemaphore(value: 0)
    private let resumeSecondScheduleSignal = DispatchSemaphore(value: 0)
    private var scheduleCount = 0

    lazy var schedule: LocalPeerAcceptedRawSchedule = {
        [weak self] _, _ in
        guard let self else { return }
        let shouldPause = self.lock.withRawTestLock {
            self.scheduleCount += 1
            return self.scheduleCount == 2
        }
        guard shouldPause else { return }
        self.secondScheduleEntered.signal()
        _ = self.resumeSecondScheduleSignal.wait(timeout: .now() + 2)
    }

    func waitUntilSecondScheduleEntered() -> Bool {
        secondScheduleEntered.wait(timeout: .now() + 2) == .success
    }

    func resumeSecondSchedule() {
        resumeSecondScheduleSignal.signal()
    }
}

private final class AcceptedRawSessionRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var sessions: [any RuntimeAcceptedRawSession] = []

    lazy var append: @Sendable (any RuntimeAcceptedRawSession) -> Void = {
        [weak self] session in
        guard let self else { return }
        lock.withRawTestLock { self.sessions.append(session) }
    }

    var first: (any RuntimeAcceptedRawSession)? {
        lock.withRawTestLock { sessions.first }
    }

    var count: Int { lock.withRawTestLock { sessions.count } }
}

private final class ControlledAcceptedRawConnectionIO:
    LocalPeerAcceptedRawConnectionIO,
    @unchecked Sendable
{
    private let lock = NSLock()
    private let receiveChanged = DispatchSemaphore(value: 0)
    private var storedStartCount = 0
    private var storedReceiveLengths: [Int] = []
    private var receiveCompletions: [(@Sendable (Data?) -> Void)] = []
    private var terminalHandler: (@Sendable () -> Void)?
    private var storedCancelCount = 0
    private var cancelled = false

    var startCount: Int { lock.withRawTestLock { storedStartCount } }
    var receiveLengths: [Int] { lock.withRawTestLock { storedReceiveLengths } }
    var cancelCount: Int { lock.withRawTestLock { storedCancelCount } }

    func start(onTerminal: @escaping @Sendable () -> Void) {
        lock.withRawTestLock {
            storedStartCount += 1
            terminalHandler = onTerminal
        }
    }

    func receiveExactly(
        _ byteCount: Int,
        completion: @escaping @Sendable (Data?) -> Void
    ) {
        lock.withRawTestLock {
            storedReceiveLengths.append(byteCount)
            receiveCompletions.append(completion)
        }
        receiveChanged.signal()
    }

    func send(
        _ frame: Data,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        completion(!lock.withRawTestLock { cancelled })
    }

    func cancel() {
        let callback: (@Sendable () -> Void)? = lock.withRawTestLock {
            guard !cancelled else { return nil }
            cancelled = true
            storedCancelCount += 1
            return terminalHandler
        }
        callback?()
    }

    func signalTerminal() {
        let callback = lock.withRawTestLock { terminalHandler }
        callback?()
    }

    func completeNextReceive(with data: Data?) {
        let callback: (@Sendable (Data?) -> Void)? = lock.withRawTestLock {
            guard !receiveCompletions.isEmpty else { return nil }
            return receiveCompletions.removeFirst()
        }
        callback?(data)
    }

    func waitForReceiveCount(_ count: Int) -> [Int] {
        let deadline = DispatchTime.now() + 2
        while true {
            let snapshot = receiveLengths
            if snapshot.count >= count { return snapshot }
            if receiveChanged.wait(timeout: deadline) != .success { return snapshot }
        }
    }
}

private actor ControlledAcceptedRawHandler {
    private var bodies: [Data] = []
    private var entered = false
    private var enteredWaiters: [CheckedContinuation<Void, Never>] = []
    private var releaseWaiter: CheckedContinuation<Void, Never>?

    func handle(_ body: Data) async {
        bodies.append(body)
        entered = true
        let waiters = enteredWaiters
        enteredWaiters.removeAll(keepingCapacity: false)
        waiters.forEach { $0.resume() }
        await withCheckedContinuation { continuation in
            releaseWaiter = continuation
        }
    }

    func waitUntilEntered() async {
        if entered { return }
        await withCheckedContinuation { continuation in
            enteredWaiters.append(continuation)
        }
    }

    func receivedBodies() -> [Data] { bodies }

    func release() {
        let waiter = releaseWaiter
        releaseWaiter = nil
        waiter?.resume()
    }
}

private final class AcceptedRawTestClock: @unchecked Sendable {
    private let lock = NSLock()
    private var storedNowMs: UInt64

    init(nowMs: UInt64) {
        storedNowMs = nowMs
    }

    var nowMs: UInt64 {
        get { lock.withRawTestLock { storedNowMs } }
        set { lock.withRawTestLock { storedNowMs = newValue } }
    }
}

private final class ControlledAcceptedRawScheduler: @unchecked Sendable {
    private struct Entry {
        let delay: UInt64
        let action: @Sendable () -> Void
    }

    private let lock = NSLock()
    private var entries: [Entry] = []

    lazy var schedule: LocalPeerAcceptedRawSchedule = {
        [weak self] delay, action in
        self?.lock.withRawTestLock {
            self?.entries.append(Entry(delay: delay, action: action))
        }
    }

    var delays: [UInt64] {
        lock.withRawTestLock { entries.map(\.delay) }
    }

    @discardableResult
    func runNext() -> Bool {
        let action: (@Sendable () -> Void)? = lock.withRawTestLock {
            guard !entries.isEmpty else { return nil }
            return entries.removeFirst().action
        }
        action?()
        return action != nil
    }

    func runAll() {
        while runNext() {}
    }
}

private extension NSLock {
    func withRawTestLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}

private final class ClaimTestRawSink: RuntimeRawFrameBodySink, @unchecked Sendable {
    let connectionID = UUID()
    private let lock = NSLock()
    private var closes = 0

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
        closes += 1
        lock.unlock()
    }
}

private final class ControlledFrameWriterHarness: @unchecked Sendable {
    private let lock = NSLock()
    private let changed = DispatchSemaphore(value: 0)
    private var submissions: [Data] = []
    private var callbacks: [(@Sendable (Bool) -> Void)] = []
    private var storedCloseCount = 0

    lazy var write: LocalPeerOrderedFrameWriter.Write = { [weak self] frame, completion in
        guard let self else {
            completion(false)
            return
        }
        lock.lock()
        submissions.append(frame)
        callbacks.append(completion)
        lock.unlock()
        changed.signal()
    }

    lazy var close: @Sendable () -> Void = { [weak self] in
        guard let self else { return }
        lock.lock()
        storedCloseCount += 1
        lock.unlock()
        changed.signal()
    }

    var closeCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return storedCloseCount
    }

    func waitForSubmissionCount(_ count: Int) -> [Data] {
        waitUntil { submissions.count >= count }
        lock.lock()
        defer { lock.unlock() }
        return submissions
    }

    func hasSubmissionCount(_ count: Int) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return submissions.count >= count
    }

    func completeSubmission(at index: Int, succeeded: Bool) {
        lock.lock()
        let callback = callbacks[index]
        lock.unlock()
        callback(succeeded)
    }

    func waitForCloseCount(_ count: Int) -> Int {
        waitUntil { storedCloseCount >= count }
        return closeCount
    }

    private func waitUntil(_ predicate: () -> Bool) {
        let deadline = DispatchTime.now() + 2
        while true {
            lock.lock()
            let complete = predicate()
            lock.unlock()
            if complete { return }
            if changed.wait(timeout: deadline) != .success { return }
        }
    }
}

private final class LockedValues<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private let changed = DispatchSemaphore(value: 0)
    private var values: [Value] = []

    var valuesSnapshot: [Value] {
        lock.lock()
        defer { lock.unlock() }
        return values
    }

    func append(_ value: Value) {
        lock.lock()
        values.append(value)
        lock.unlock()
        changed.signal()
    }

    func waitForCount(_ count: Int) -> [Value] {
        let deadline = DispatchTime.now() + 2
        while true {
            lock.lock()
            let complete = values.count >= count
            let snapshot = values
            lock.unlock()
            if complete { return snapshot }
            if changed.wait(timeout: deadline) != .success { return snapshot }
        }
    }
}
