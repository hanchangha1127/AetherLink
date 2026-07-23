import BridgeProtocol
import Foundation
import P2PNATContracts
import Transport
import XCTest
@testable import CompanionCore

final class MacRuntimeProductionSecureChannelTests: XCTestCase {
    private let sessionID = String(repeating: "a", count: 32)
    private let digest = String(repeating: "b", count: 64)

    func testHappyHandshakeOutboundAndInboundApplication() async throws {
        let fixture = try makeFixture()
        XCTAssertNil(fixture.channel.transportSecurityContext)
        let handshakeBinding = fixture.channel
            .withTransportSecurityContextTransaction { $0?.bindingID }
        XCTAssertNil(handshakeBinding)
        try await activate(fixture)
        XCTAssertEqual(
            fixture.channel.transportSecurityContext,
            TransportSecurityContext(bindingID: digest)
        )
        let activeBinding = fixture.channel
            .withTransportSecurityContextTransaction { $0?.bindingID }
        XCTAssertEqual(activeBinding, digest)
        XCTAssertEqual(fixture.operations.events(), [
            "accept-confirmation", "send-confirmation", "confirmation-sent", "activate",
        ])
        let sent = fixture.raw.sentBodies()
        XCTAssertEqual(sent.count, 1)
        XCTAssertEqual(
            try ProductionSecureSessionKeyConfirmation(canonicalBytes: sent[0])
                .confirmingRole,
            .runtime
        )

        let outbound = envelope("outbound")
        let outboundSucceeded = await fixture.channel.sendAndWait(outbound)
        XCTAssertTrue(outboundSucceeded)
        let outboundRecord = try ProductionSecureSessionEncryptedRecord(
            canonicalBytes: try XCTUnwrap(fixture.raw.sentBodies().last)
        )
        XCTAssertEqual(outboundRecord.senderRole, .runtime)
        XCTAssertEqual(outboundRecord.contentType, .application)
        XCTAssertEqual(fixture.operations.sealedApplicationEnvelopes(), [outbound])

        let inbound = envelope("inbound")
        fixture.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(inbound)
        )
        try await fixture.channel.receiveRawFrameBody(try clientRecord(sequence: 0))
        let drained = await fixture.channel.waitUntilMailboxDrained()
        XCTAssertTrue(drained)
        XCTAssertEqual(fixture.routed.value(), [inbound])
        XCTAssertTrue(fixture.operations.publisherRanInsideOpen())

        fixture.operations.queueInboundKeyUpdate(nextEpoch: 1)
        try await fixture.channel.receiveRawFrameBody(try clientRecord(
            sequence: 1,
            contentType: .keyUpdate
        ))
        let keyUpdateDrained = await fixture.channel.waitUntilMailboxDrained()
        XCTAssertTrue(keyUpdateDrained)
        XCTAssertEqual(fixture.routed.value(), [inbound])
    }

    func testOutboundFIFOAndKeyUpdatePrecedesNextApplication() async throws {
        let fixture = try makeFixture()
        try await activate(fixture)
        fixture.operations.queueApplicationSealResult(keyUpdateRequired: true)
        fixture.operations.queueApplicationSealResult(keyUpdateRequired: false)

        let completions = TestLocked<[Bool]>([])
        fixture.channel.send(envelope("one")) { succeeded in
            completions.mutate { $0.append(succeeded) }
        }
        fixture.channel.send(envelope("two")) { succeeded in
            completions.mutate { $0.append(succeeded) }
        }
        await waitUntil { completions.value().count == 2 }
        XCTAssertEqual(completions.value(), [true, true])
        XCTAssertEqual(
            fixture.operations.events().filter { $0.hasPrefix("seal-") },
            ["seal-app:one", "seal-key-update", "seal-app:two"]
        )
        let records = try fixture.raw.sentBodies().dropFirst().map {
            try ProductionSecureSessionEncryptedRecord(canonicalBytes: $0)
        }
        XCTAssertEqual(records.map(\.contentType), [
            .application, .keyUpdate, .application,
        ])
        XCTAssertEqual(records.map(\.sequence), [0, 1, 2])
    }

    func testTerminalAfterRecordCompletesSuccessThenCloses() async throws {
        let fixture = try makeFixture()
        try await activate(fixture)
        fixture.operations.queueApplicationSealResult(
            keyUpdateRequired: false,
            terminalAfterRecord: true
        )
        let succeeded = await fixture.channel.sendAndWait(envelope("last"))
        XCTAssertTrue(succeeded)
        await fixture.channel.closeAndWait()
        XCTAssertEqual(fixture.raw.closeCount(), 1)
        let reused = await awaitSend(fixture.channel, envelope("after-last"))
        XCTAssertFalse(reused)
    }

    func testReplayRejectionPropagatesAndTerminatesWithoutReuse() async throws {
        let fixture = try makeFixture()
        try await activate(fixture)
        fixture.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(envelope("first"))
        )
        try await fixture.channel.receiveRawFrameBody(try clientRecord(sequence: 0))
        fixture.operations.queueOpenError(.replay)
        do {
            try await fixture.channel.receiveRawFrameBody(try clientRecord(sequence: 0))
            XCTFail("Expected the secure-session replay rejection")
        } catch {
            XCTAssertEqual(error as? FakeSecureSessionError, .replay)
        }
        XCTAssertEqual(fixture.raw.closeCount(), 1)
        let laterSucceeded = await fixture.channel.sendAndWait(envelope("later"))
        XCTAssertFalse(laterSucceeded)
        XCTAssertEqual(fixture.operations.applicationSealCount(), 0)
    }

    func testRawSendFailureAndCancellationAfterSealAreTerminal() async throws {
        let failure = try makeFixture()
        try await activate(failure)
        failure.raw.failNextSend()
        let failedSucceeded = await failure.channel.sendAndWait(envelope("failed"))
        XCTAssertFalse(failedSucceeded)
        await waitUntil { failure.raw.closeCount() == 1 }
        XCTAssertEqual(failure.operations.applicationSealCount(), 1)
        let reused = await failure.channel.sendAndWait(envelope("no-reuse"))
        XCTAssertFalse(reused)
        XCTAssertEqual(failure.operations.applicationSealCount(), 1)

        let cancelled = try makeFixture()
        try await activate(cancelled)
        cancelled.raw.blockNextSend()
        let sendTask = Task {
            await cancelled.channel.sendAndWait(self.envelope("cancelled"))
        }
        await cancelled.raw.waitUntilSendBlocked()
        sendTask.cancel()
        let cancelledSucceeded = await sendTask.value
        XCTAssertFalse(cancelledSucceeded)
        await cancelled.channel.closeAndWait()
        XCTAssertEqual(cancelled.raw.closeCount(), 1)
        XCTAssertEqual(cancelled.operations.applicationSealCount(), 1)
        XCTAssertNil(cancelled.channel.transportSecurityContext)

        let explicit = try makeFixture()
        try await activate(explicit)
        explicit.raw.blockNextSend()
        let explicitSend = Task {
            await explicit.channel.sendAndWait(self.envelope("explicit-close"))
        }
        await explicit.raw.waitUntilSendBlocked()
        await explicit.channel.closeAndWait()
        let explicitSucceeded = await explicitSend.value
        XCTAssertFalse(explicitSucceeded)
        XCTAssertEqual(explicit.raw.closeCount(), 1)
        XCTAssertEqual(explicit.operations.closeCount(), 1)
    }

    func testCallerCancellationBeforeQueueClaimIsFailClosed() async throws {
        let fixture = try makeFixture()
        try await activate(fixture)
        let startGate = TestAsyncStartGate()
        let sendTask = Task {
            await startGate.wait()
            return await fixture.channel.sendAndWait(self.envelope("pre-cancelled"))
        }
        sendTask.cancel()
        await startGate.open()
        let succeeded = await sendTask.value
        XCTAssertFalse(succeeded)
        await fixture.channel.closeAndWait()
        XCTAssertEqual(fixture.raw.closeCount(), 1)
        XCTAssertEqual(fixture.operations.applicationSealCount(), 0)
    }

    func testOutboundDeadlineBreaksMissingRawCompletionAndCloseConverges()
        async throws
    {
        let watchdogGate = TestAsyncStartGate()
        let fixture = try makeFixture(
            outboundItemDeadlineNanoseconds: 1,
            watchdogSleep: { _ in await watchdogGate.wait() }
        )
        try await activate(fixture)
        let handshakeBodyCount = fixture.raw.sentBodies().count
        fixture.raw.dropNextCompletionEvenOnClose()
        let completions = TestLocked<[Bool]>([])
        fixture.channel.send(envelope("deadline")) { succeeded in
            completions.mutate { $0.append(succeeded) }
        }
        await waitUntil {
            fixture.raw.sentBodies().count == handshakeBodyCount + 1
        }
        await watchdogGate.open()
        await fixture.channel.closeAndWait()
        XCTAssertEqual(completions.value(), [false])
        XCTAssertEqual(fixture.raw.closeCount(), 1)
        XCTAssertEqual(fixture.operations.closeCount(), 1)
        XCTAssertEqual(fixture.operations.applicationSealCount(), 1)
    }

    func testStrictPhaseTypeMagicVersionEmptyAndSizeRejection() async throws {
        let invalidHandshakeBodies: [Data] = [
            Data(),
            Data(#"{"type":"fallback"}"#.utf8),
            Data(repeating: 0, count: 6),
            mutated(try clientConfirmation(), at: 5, to: 2),
            try clientRecord(sequence: 0),
            Data(repeating: 0, count:
                ProductionSecureSessionCryptoContract.maximumKeyConfirmationBytes + 1),
        ]
        for body in invalidHandshakeBodies {
            let fixture = try makeFixture()
            await assertInvalidFrame(body, fixture: fixture)
            XCTAssertEqual(fixture.raw.closeCount(), 1)
        }

        let active = try makeFixture()
        try await activate(active)
        await assertInvalidFrame(try clientConfirmation(), fixture: active)

        let oversized = try makeFixture()
        try await activate(oversized)
        await assertInvalidFrame(
            Data(repeating: 0,
                 count: ProductionSecureSessionCryptoContract.maximumRecordBytes + 1),
            fixture: oversized
        )
    }

    func testBoundedOutboundQueueOverflowClosesAndWakesAllCompletions()
        async throws
    {
        let fixture = try makeFixture(maximumOutboundQueueDepth: 2)
        try await activate(fixture)
        fixture.raw.blockNextSend()
        let completions = TestLocked<[Bool]>([])
        fixture.channel.send(envelope("one")) { succeeded in
            completions.mutate { $0.append(succeeded) }
        }
        await fixture.raw.waitUntilSendBlocked()
        fixture.channel.send(envelope("two")) { succeeded in
            completions.mutate { $0.append(succeeded) }
        }
        fixture.channel.send(envelope("overflow")) { succeeded in
            completions.mutate { $0.append(succeeded) }
        }
        await waitUntil { completions.value().count == 3 }
        XCTAssertEqual(completions.value(), [false, false, false])
        XCTAssertEqual(fixture.raw.closeCount(), 1)
    }

    func testEnvelopeEncodeFailureAndOversizeAreTerminal() async throws {
        let encodeFailure = try makeFixture()
        try await activate(encodeFailure)
        var invalid = envelope("nan")
        invalid.payload["not_json"] = .number(.nan)
        let encoded = await encodeFailure.channel.sendAndWait(invalid)
        XCTAssertFalse(encoded)
        await encodeFailure.channel.closeAndWait()
        XCTAssertEqual(encodeFailure.operations.applicationSealCount(), 0)

        let oversized = try makeFixture()
        try await activate(oversized)
        var large = envelope("large")
        large.payload["body"] = .string(String(
            repeating: "x",
            count: ProductionSecureSessionCryptoContract.maximumPlaintextBytes
        ))
        let sent = await oversized.channel.sendAndWait(large)
        XCTAssertFalse(sent)
        await oversized.channel.closeAndWait()
        XCTAssertEqual(oversized.operations.applicationSealCount(), 0)
    }

    func testInboundApplicationRemainsStagedUntilPostFenceSuccess() async throws {
        let gate = TestPostFenceGate()
        let routed = TestLocked<[ProtocolEnvelope]>([])
        let fixture = try makeFixture(
            mailboxWorkerScheduler: { $0() },
            router: { envelope, _ in routed.mutate { $0.append(envelope) } }
        )
        try await activate(fixture)
        let expected = envelope("post-fence-success")
        fixture.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(expected)
        )
        fixture.operations.setNextApplicationPostPublishHook {
            await gate.blockUntilReleased()
        }
        let receiveTask = Task {
            try await fixture.channel.receiveRawFrameBody(
                try self.clientRecord(sequence: 0)
            )
        }

        await gate.waitUntilEntered()
        XCTAssertTrue(routed.value().isEmpty)
        let drainFinished = TestLocked(false)
        let drainTask = Task {
            let result = await fixture.channel.waitUntilMailboxDrained()
            drainFinished.mutate { $0 = true }
            return result
        }
        await Task.yield()
        XCTAssertFalse(drainFinished.value())
        await gate.release()
        try await receiveTask.value
        let drained = await drainTask.value
        XCTAssertTrue(drained)
        XCTAssertEqual(routed.value(), [expected])
    }

    func testPostFenceFailureSuppressesTerminalApplicationReservation()
        async throws
    {
        let fixture = try makeFixture(mailboxWorkerScheduler: { $0() })
        try await activate(fixture)
        fixture.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(envelope("post-fence-failed")),
            terminalAfterRecord: true
        )
        fixture.operations.setNextApplicationPostPublishHook {
            throw FakeSecureSessionError.postFence
        }

        do {
            try await fixture.channel.receiveRawFrameBody(try clientRecord(sequence: 0))
            XCTFail("Expected post-fence failure")
        } catch {
            XCTAssertEqual(error as? FakeSecureSessionError, .postFence)
        }
        await fixture.channel.closeAndWait()
        XCTAssertTrue(fixture.routed.value().isEmpty)
        XCTAssertEqual(fixture.raw.closeCount(), 1)
    }

    func testObserverDuringPostFenceSuppressesStagedApplication() async throws {
        let gate = TestPostFenceGate()
        let fixture = try makeFixture(mailboxWorkerScheduler: { $0() })
        try await activate(fixture)
        fixture.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(envelope("observer-before-commit"))
        )
        fixture.operations.setNextApplicationPostPublishHook {
            await gate.blockUntilReleased()
        }
        let receiveTask = Task {
            try await fixture.channel.receiveRawFrameBody(
                try self.clientRecord(sequence: 0)
            )
        }

        await gate.waitUntilEntered()
        fixture.operations.fireTerminalObserver()
        await gate.release()
        do {
            try await receiveTask.value
            XCTFail("Expected terminal suppression before commit")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionSecureChannelError,
                .terminal
            )
        }
        await fixture.channel.closeAndWait()
        XCTAssertTrue(fixture.routed.value().isEmpty)
        XCTAssertEqual(fixture.raw.closeCount(), 1)
    }

    func testCancellationDuringPostFenceSuppressesStagedApplication()
        async throws
    {
        let gate = TestPostFenceGate()
        let fixture = try makeFixture(mailboxWorkerScheduler: { $0() })
        try await activate(fixture)
        fixture.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(envelope("cancel-before-commit"))
        )
        fixture.operations.setNextApplicationPostPublishHook {
            await gate.blockUntilReleased()
        }
        let receiveTask = Task {
            try await fixture.channel.receiveRawFrameBody(
                try self.clientRecord(sequence: 0)
            )
        }

        await gate.waitUntilEntered()
        receiveTask.cancel()
        await waitUntil { fixture.raw.closeCount() == 1 }
        XCTAssertTrue(fixture.routed.value().isEmpty)
        await gate.release()
        do {
            try await receiveTask.value
            XCTFail("Expected cancellation")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }
        await fixture.channel.closeAndWait()
        XCTAssertTrue(fixture.routed.value().isEmpty)
        XCTAssertEqual(fixture.raw.closeCount(), 1)
    }

    func testInboundMailboxOverflowIsTerminalAndWakesDrainWaiter() async throws {
        let mailboxExecutor = TestManualExecutor()
        let routeCount = TestLocked(0)
        let fixture = try makeFixture(
            maximumMailboxDepth: 1,
            mailboxWorkerScheduler: { mailboxExecutor.schedule($0) },
            router: { _, _ in
                routeCount.mutate { $0 += 1 }
            }
        )
        try await activate(fixture)
        for name in ["one", "two"] {
            fixture.operations.queueInboundApplication(
                try ProtocolCodec().encodeEnvelopeBody(envelope(name))
            )
        }
        try await fixture.channel.receiveRawFrameBody(try clientRecord(sequence: 0))
        let drainTask = Task { await fixture.channel.waitUntilMailboxDrained() }
        do {
            try await fixture.channel.receiveRawFrameBody(try clientRecord(sequence: 1))
            XCTFail("Expected bounded mailbox overflow")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionSecureChannelError,
                .inboundMailboxOverflow
            )
        }
        mailboxExecutor.runAll()
        let didDrain = await drainTask.value
        XCTAssertTrue(didDrain)
        await fixture.channel.closeAndWait()
        XCTAssertEqual(routeCount.value(), 1)
        XCTAssertEqual(fixture.raw.closeCount(), 1)
    }

    func testTerminalInboundApplicationDeliversExactlyOnceThenCloses()
        async throws
    {
        let mailboxExecutor = TestManualExecutor()
        let routed = TestLocked<[ProtocolEnvelope]>([])
        let fixture = try makeFixture(
            mailboxWorkerScheduler: { mailboxExecutor.schedule($0) },
            router: { envelope, _ in routed.mutate { $0.append(envelope) } }
        )
        try await activate(fixture)
        let terminalObserved = TestLocked(0)
        XCTAssertTrue(fixture.channel.installAttachmentTerminalObserver {
            terminalObserved.mutate { $0 += 1 }
        })
        let terminalEnvelope = envelope("terminal-app")
        fixture.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(terminalEnvelope),
            terminalAfterRecord: true
        )
        try await fixture.channel.receiveRawFrameBody(try clientRecord(sequence: 0))
        XCTAssertTrue(routed.value().isEmpty)
        XCTAssertEqual(fixture.raw.closeCount(), 0)
        XCTAssertEqual(terminalObserved.value(), 0)
        let closeFinished = TestLocked(false)
        let closeTask = Task {
            await fixture.channel.closeAndWait()
            closeFinished.mutate { $0 = true }
        }
        await Task.yield()
        XCTAssertFalse(closeFinished.value())
        mailboxExecutor.runAll()
        await closeTask.value
        XCTAssertEqual(routed.value(), [terminalEnvelope])
        XCTAssertEqual(fixture.raw.closeCount(), 1)
        XCTAssertEqual(terminalObserved.value(), 1)
    }

    func testTerminalInboundKeyUpdateClosesWithoutRouterDelivery() async throws {
        let fixture = try makeFixture()
        try await activate(fixture)
        fixture.operations.queueInboundKeyUpdate(
            nextEpoch: 1,
            terminalAfterRecord: true
        )
        try await fixture.channel.receiveRawFrameBody(try clientRecord(
            sequence: 0,
            contentType: .keyUpdate
        ))
        await fixture.channel.closeAndWait()
        XCTAssertTrue(fixture.routed.value().isEmpty)
        XCTAssertEqual(fixture.raw.closeCount(), 1)
    }

    func testObserverBeforeCommitSuppressesButAfterCommitDrains() async throws {
        let before = try makeFixture()
        try await activate(before)
        before.operations.fireTerminalObserver()
        before.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(envelope("suppressed"))
        )
        _ = try? await before.channel.receiveRawFrameBody(try clientRecord(sequence: 0))
        await before.channel.closeAndWait()
        XCTAssertTrue(before.routed.value().isEmpty)

        let mailboxExecutor = TestManualExecutor()
        let after = try makeFixture(
            mailboxWorkerScheduler: { mailboxExecutor.schedule($0) }
        )
        try await activate(after)
        let committed = envelope("committed")
        after.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(committed)
        )
        try await after.channel.receiveRawFrameBody(try clientRecord(sequence: 0))
        after.operations.fireTerminalObserver()
        mailboxExecutor.runAll()
        await after.channel.closeAndWait()
        XCTAssertEqual(after.routed.value(), [committed])
        XCTAssertEqual(after.raw.closeCount(), 1)
    }

    func testObserverAfterDequeueClaimCannotSuppressCommittedDelivery()
        async throws
    {
        let operationsReference = TestLocked<FakeSecureSessionOperations?>(nil)
        let fixture = try makeFixture(afterMailboxExecutionClaim: {
            operationsReference.value()?.fireTerminalObserver()
        })
        operationsReference.mutate { $0 = fixture.operations }
        try await activate(fixture)
        let committed = envelope("claimed")
        fixture.operations.queueInboundApplication(
            try ProtocolCodec().encodeEnvelopeBody(committed)
        )
        try await fixture.channel.receiveRawFrameBody(try clientRecord(sequence: 0))
        await fixture.channel.closeAndWait()
        XCTAssertEqual(fixture.routed.value(), [committed])
        XCTAssertEqual(fixture.raw.closeCount(), 1)
    }

    func testStaleGenerationIsIgnoredAndTerminalObserverClosesExactlyOnce()
        async throws
    {
        let fixture = try makeFixture()
        try await fixture.channel.receiveRawFrameBody(
            try clientConfirmation(),
            generationID: UUID()
        )
        XCTAssertTrue(fixture.operations.events().isEmpty)
        XCTAssertEqual(fixture.raw.closeCount(), 0)

        fixture.operations.fireTerminalObserver()
        fixture.operations.fireTerminalObserver()
        await fixture.channel.closeAndWait()
        XCTAssertEqual(fixture.operations.closeCount(), 1)
        XCTAssertEqual(fixture.raw.closeCount(), 1)
        let didDrain = await fixture.channel.waitUntilMailboxDrained()
        XCTAssertFalse(didDrain)
    }

    func testAttachmentTerminalObserverFiresForIdleAuthorityTerminationAndLateInstall()
        async throws
    {
        let fixture = try makeFixture()
        let observed = TestLocked(0)
        XCTAssertTrue(fixture.channel.installAttachmentTerminalObserver {
            observed.mutate { $0 += 1 }
        })
        XCTAssertFalse(fixture.channel.installAttachmentTerminalObserver {})
        fixture.operations.fireTerminalObserver()
        await fixture.channel.closeAndWait()
        XCTAssertEqual(observed.value(), 1)

        let alreadyExpired = try makeFixture(expiresAtMs: 1_000, nowMs: { 1_000 })
        await alreadyExpired.channel.closeAndWait()
        let lateObserved = TestLocked(0)
        XCTAssertTrue(alreadyExpired.channel.installAttachmentTerminalObserver {
            lateObserved.mutate { $0 += 1 }
        })
        XCTAssertEqual(lateObserved.value(), 1)
        XCTAssertFalse(alreadyExpired.channel.installAttachmentTerminalObserver {})
    }

    func testHandshakeTimeoutExpiryAndConcurrentRawCallbackFailClosed()
        async throws
    {
        let timeout = try makeFixture(
            handshakeTimeoutNanoseconds: 1,
            sleep: { _ in }
        )
        await timeout.channel.closeAndWait()
        XCTAssertEqual(timeout.raw.closeCount(), 1)

        let expiry = try makeFixture(expiresAtMs: 1_000, nowMs: { 1_000 })
        await expiry.channel.closeAndWait()
        XCTAssertEqual(expiry.raw.closeCount(), 1)

        let concurrent = try makeFixture()
        concurrent.raw.blockNextSend()
        let first = Task {
            try await concurrent.channel.receiveRawFrameBody(
                try self.clientConfirmation()
            )
        }
        await concurrent.raw.waitUntilSendBlocked()
        do {
            try await concurrent.channel.receiveRawFrameBody(try clientConfirmation())
            XCTFail("Expected concurrent raw callback fail-closed")
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionSecureChannelError,
                .invalidPhase
            )
        }
        _ = try? await first.value
        await concurrent.channel.closeAndWait()
        XCTAssertEqual(concurrent.raw.closeCount(), 1)
    }

    private struct Fixture {
        let operations: FakeSecureSessionOperations
        let raw: FakeRawSink
        let routed: TestLocked<[ProtocolEnvelope]>
        let channel: MacRuntimeProductionSecureChannel
    }

    private func makeFixture(
        maximumOutboundQueueDepth: Int = 32,
        maximumMailboxDepth: Int = 64,
        expiresAtMs: UInt64 = 10_000_000,
        handshakeTimeoutNanoseconds: UInt64 = 10_000_000_000,
        nowMs: @escaping @Sendable () -> UInt64 = { 1_000 },
        sleep: @escaping @Sendable (UInt64) async throws -> Void = {
            try await Task.sleep(nanoseconds: $0)
        },
        outboundItemDeadlineNanoseconds: UInt64 = 15_000_000_000,
        watchdogSleep: @escaping @Sendable (UInt64) async throws -> Void = {
            try await Task.sleep(nanoseconds: $0)
        },
        mailboxWorkerScheduler: (
            @Sendable (@escaping @Sendable () -> Void) -> Void
        )? = nil,
        beforeMailboxExecutionClaim: (@Sendable () -> Void)? = nil,
        afterMailboxExecutionClaim: (@Sendable () -> Void)? = nil,
        router overrideRouter: MacRuntimeProductionSecureChannel.EnvelopeRouter? = nil
    ) throws -> Fixture {
        let operations = try FakeSecureSessionOperations(
            sessionID: sessionID,
            digest: digest,
            expiresAtMs: expiresAtMs
        )
        let raw = FakeRawSink()
        let routed = TestLocked<[ProtocolEnvelope]>([])
        let router = overrideRouter ?? { envelope, _ in
            routed.mutate { $0.append(envelope) }
        }
        let channel = MacRuntimeProductionSecureChannel(
            operations: operations,
            rawSink: raw,
            maximumOutboundQueueDepth: maximumOutboundQueueDepth,
            maximumMailboxDepth: maximumMailboxDepth,
            handshakeTimeoutNanoseconds: handshakeTimeoutNanoseconds,
            outboundItemDeadlineNanoseconds: outboundItemDeadlineNanoseconds,
            nowMs: nowMs,
            sleep: sleep,
            watchdogSleep: watchdogSleep,
            mailboxWorkerScheduler: mailboxWorkerScheduler,
            beforeMailboxExecutionClaim: beforeMailboxExecutionClaim,
            afterMailboxExecutionClaim: afterMailboxExecutionClaim,
            router: router
        )
        return Fixture(
            operations: operations,
            raw: raw,
            routed: routed,
            channel: channel
        )
    }

    private func activate(_ fixture: Fixture) async throws {
        try await fixture.channel.receiveRawFrameBody(try clientConfirmation())
    }

    private func clientConfirmation() throws -> Data {
        try ProductionSecureSessionKeyConfirmation(
            sessionId: sessionID,
            transcriptDigestHex: digest,
            grantAuthorizationDigestHex: digest,
            confirmingRole: .client,
            proof: Data(repeating: 7, count: 32)
        ).canonicalBytes()
    }

    private func clientRecord(
        sequence: UInt64,
        contentType: ProductionSecureSessionContentType = .application
    ) throws -> Data {
        try ProductionSecureSessionEncryptedRecord(
            sessionId: sessionID,
            senderRole: .client,
            epoch: 0,
            sequence: sequence,
            contentType: contentType,
            ciphertext: Data([1]),
            tag: Data(repeating: 2, count: 16)
        ).canonicalBytes()
    }

    private func envelope(_ requestID: String) -> ProtocolEnvelope {
        ProtocolEnvelope(
            type: "runtime.health",
            requestID: requestID,
            timestamp: Date(timeIntervalSince1970: 1),
            payload: [:]
        )
    }

    private func mutated(_ data: Data, at offset: Int, to byte: UInt8) -> Data {
        var result = data
        result[result.startIndex + offset] = byte
        return result
    }

    private func assertInvalidFrame(
        _ body: Data,
        fixture: Fixture,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async {
        do {
            try await fixture.channel.receiveRawFrameBody(body)
            XCTFail("Expected strict raw-frame rejection", file: file, line: line)
        } catch {
            XCTAssertEqual(
                error as? MacRuntimeProductionSecureChannelError,
                .invalidFrame,
                file: file,
                line: line
            )
        }
    }

    private func waitUntil(
        _ predicate: @escaping @Sendable () -> Bool
    ) async {
        for _ in 0..<20_000 {
            if predicate() { return }
            await Task.yield()
        }
        XCTFail("Timed out waiting for asynchronous state")
    }

    private func awaitSend(
        _ channel: MacRuntimeProductionSecureChannel,
        _ envelope: ProtocolEnvelope
    ) async -> Bool {
        await channel.sendAndWait(envelope)
    }
}

private enum FakeSecureSessionError: Error, Equatable {
    case replay
    case postFence
}

private final class FakeSecureSessionOperations:
    MacRuntimeProductionSecureSessionOperations,
    @unchecked Sendable
{
    private enum OpenAction {
        case application(Data, terminal: Bool)
        case keyUpdate(UInt32, terminal: Bool)
        case error(FakeSecureSessionError)
    }

    let descriptor: MacRuntimeProductionSecureChannelDescriptor
    private let digest: String
    private let lock = NSLock()
    private var terminalObserver: (@Sendable () -> Void)?
    private var eventValues: [String] = []
    private var nextOutboundSequence: UInt64 = 0
    private var applicationResults: [(keyUpdate: Bool, terminal: Bool)] = []
    private var openActions: [OpenAction] = []
    private var encodedApplicationEnvelopes: [ProtocolEnvelope] = []
    private var applicationSeals = 0
    private var closes = 0
    private var publisherInsideOpen = false
    private var applicationPostPublishHook: (
        @Sendable () async throws -> Void
    )?

    init(sessionID: String, digest: String, expiresAtMs: UInt64) throws {
        descriptor = MacRuntimeProductionSecureChannelDescriptor(
            bindingDigest: digest,
            sessionID: sessionID,
            expiresAtMs: expiresAtMs
        )
        self.digest = digest
    }

    func installTerminalObserver(
        _ observer: @escaping @Sendable () -> Void
    ) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard terminalObserver == nil else { return false }
        terminalObserver = observer
        return true
    }

    func sendLocalConfirmation(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws {
        appendEvent("send-confirmation")
        let body = try ProductionSecureSessionKeyConfirmation(
            sessionId: descriptor.sessionID,
            transcriptDigestHex: digest,
            grantAuthorizationDigestHex: digest,
            confirmingRole: .runtime,
            proof: Data(repeating: 8, count: 32)
        ).canonicalBytes()
        try await send(body)
        appendEvent("confirmation-sent")
    }

    func acceptPeerConfirmation(_ canonicalConfirmation: Data) async throws {
        _ = try ProductionSecureSessionKeyConfirmation(canonicalBytes: canonicalConfirmation)
        appendEvent("accept-confirmation")
    }

    func activate() async throws { appendEvent("activate") }

    func sealApplicationAndSend(
        _ plaintext: Data,
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> MacRuntimeProductionSecureChannelSealResult {
        let envelope = try ProtocolCodec().decodeEnvelope(plaintext)
        let (sequence, result) = withLock {
            () -> (UInt64, (keyUpdate: Bool, terminal: Bool)) in
            applicationSeals += 1
            encodedApplicationEnvelopes.append(envelope)
            eventValues.append("seal-app:\(envelope.requestID)")
            let sequence = nextOutboundSequence
            nextOutboundSequence += 1
            let result = applicationResults.isEmpty
                ? (keyUpdate: false, terminal: false)
                : applicationResults.removeFirst()
            return (sequence, result)
        }
        try await send(try record(
            sequence: sequence,
            contentType: .application
        ))
        return MacRuntimeProductionSecureChannelSealResult(
            keyUpdateRequired: result.keyUpdate,
            terminalAfterRecord: result.terminal
        )
    }

    func sealKeyUpdateAndSend(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> MacRuntimeProductionSecureChannelSealResult {
        let sequence = withLock { () -> UInt64 in
            eventValues.append("seal-key-update")
            let sequence = nextOutboundSequence
            nextOutboundSequence += 1
            return sequence
        }
        try await send(try record(sequence: sequence, contentType: .keyUpdate))
        return MacRuntimeProductionSecureChannelSealResult(
            keyUpdateRequired: false,
            terminalAfterRecord: false
        )
    }

    func openAndPublish(
        _ canonicalRecord: Data,
        publishApplication: @escaping @Sendable (Data) throws -> Void
    ) async throws -> MacRuntimeProductionSecureChannelOpenResult {
        _ = try ProductionSecureSessionEncryptedRecord(canonicalBytes: canonicalRecord)
        let action = withLock { openActions.removeFirst() }
        switch action {
        case let .application(plaintext, terminal):
            try publishApplication(plaintext)
            withLock { publisherInsideOpen = true }
            let postPublishHook = withLock {
                let hook = applicationPostPublishHook
                applicationPostPublishHook = nil
                return hook
            }
            try await postPublishHook?()
            return .application(
                keyUpdateRequired: false,
                terminalAfterRecord: terminal
            )
        case let .keyUpdate(nextEpoch, terminal):
            return .keyUpdate(nextEpoch: nextEpoch, terminalAfterRecord: terminal)
        case let .error(error):
            throw error
        }
    }

    func close() async {
        let observer = withLock { () -> (@Sendable () -> Void)? in
            closes += 1
            return terminalObserver
        }
        observer?()
    }

    func queueApplicationSealResult(
        keyUpdateRequired: Bool,
        terminalAfterRecord: Bool = false
    ) {
        lock.lock()
        applicationResults.append((keyUpdateRequired, terminalAfterRecord))
        lock.unlock()
    }

    func queueInboundApplication(
        _ plaintext: Data,
        terminalAfterRecord: Bool = false
    ) {
        lock.lock()
        openActions.append(.application(
            plaintext,
            terminal: terminalAfterRecord
        ))
        lock.unlock()
    }

    func queueInboundKeyUpdate(
        nextEpoch: UInt32,
        terminalAfterRecord: Bool = false
    ) {
        lock.lock()
        openActions.append(.keyUpdate(
            nextEpoch,
            terminal: terminalAfterRecord
        ))
        lock.unlock()
    }

    func queueOpenError(_ error: FakeSecureSessionError) {
        lock.lock()
        openActions.append(.error(error))
        lock.unlock()
    }

    func setNextApplicationPostPublishHook(
        _ hook: @escaping @Sendable () async throws -> Void
    ) {
        lock.lock()
        applicationPostPublishHook = hook
        lock.unlock()
    }

    func fireTerminalObserver() {
        lock.lock()
        let observer = terminalObserver
        lock.unlock()
        observer?()
    }

    func events() -> [String] {
        lock.lock()
        defer { lock.unlock() }
        return eventValues
    }

    func sealedApplicationEnvelopes() -> [ProtocolEnvelope] {
        lock.lock()
        defer { lock.unlock() }
        return encodedApplicationEnvelopes
    }

    func applicationSealCount() -> Int {
        lock.lock()
        defer { lock.unlock() }
        return applicationSeals
    }

    func closeCount() -> Int {
        lock.lock()
        defer { lock.unlock() }
        return closes
    }

    func publisherRanInsideOpen() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return publisherInsideOpen
    }

    private func appendEvent(_ value: String) {
        lock.lock()
        eventValues.append(value)
        lock.unlock()
    }

    private func withLock<Result>(_ operation: () -> Result) -> Result {
        lock.lock()
        defer { lock.unlock() }
        return operation()
    }

    private func record(
        sequence: UInt64,
        contentType: ProductionSecureSessionContentType
    ) throws -> Data {
        try ProductionSecureSessionEncryptedRecord(
            sessionId: descriptor.sessionID,
            senderRole: .runtime,
            epoch: 0,
            sequence: sequence,
            contentType: contentType,
            ciphertext: contentType == .application ? Data([3]) : Data([0, 0, 0, 1]),
            tag: Data(repeating: 4, count: 16)
        ).canonicalBytes()
    }
}

private final class FakeRawSink: RuntimeRawFrameBodySink, @unchecked Sendable {
    let connectionID = UUID()
    private let lock = NSLock()
    private var bodies: [Data] = []
    private var closeCalls = 0
    private var shouldFailNext = false
    private var shouldBlockNext = false
    private var shouldDropNextCompletion = false
    private var blockedCompletions: [@Sendable (Bool) -> Void] = []

    func sendRawFrameBody(
        _ body: Data,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        lock.lock()
        bodies.append(body)
        if shouldFailNext {
            shouldFailNext = false
            lock.unlock()
            completion(false)
            return
        }
        if shouldBlockNext {
            shouldBlockNext = false
            blockedCompletions.append(completion)
            lock.unlock()
            return
        }
        if shouldDropNextCompletion {
            shouldDropNextCompletion = false
            lock.unlock()
            return
        }
        lock.unlock()
        completion(true)
    }

    func close() {
        lock.lock()
        closeCalls += 1
        let completions = blockedCompletions
        blockedCompletions.removeAll()
        lock.unlock()
        completions.forEach { $0(false) }
    }

    func failNextSend() {
        lock.lock()
        shouldFailNext = true
        lock.unlock()
    }

    func blockNextSend() {
        lock.lock()
        shouldBlockNext = true
        lock.unlock()
    }

    func dropNextCompletionEvenOnClose() {
        lock.lock()
        shouldDropNextCompletion = true
        lock.unlock()
    }

    func waitUntilSendBlocked() async {
        for _ in 0..<20_000 {
            if hasBlockedCompletion() { return }
            await Task.yield()
        }
        XCTFail("Timed out waiting for blocked raw send")
    }

    func sentBodies() -> [Data] {
        lock.lock()
        defer { lock.unlock() }
        return bodies
    }

    func closeCount() -> Int {
        lock.lock()
        defer { lock.unlock() }
        return closeCalls
    }


    private func hasBlockedCompletion() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return !blockedCompletions.isEmpty
    }
}

private final class TestLocked<Value>: @unchecked Sendable {
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

private final class TestManualExecutor: @unchecked Sendable {
    private let lock = NSLock()
    private var jobs: [@Sendable () -> Void] = []

    func schedule(_ job: @escaping @Sendable () -> Void) {
        lock.lock()
        jobs.append(job)
        lock.unlock()
    }

    func runAll() {
        while true {
            lock.lock()
            guard !jobs.isEmpty else {
                lock.unlock()
                return
            }
            let job = jobs.removeFirst()
            lock.unlock()
            job()
        }
    }
}

private actor TestAsyncStartGate {
    private var opened = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    func wait() async {
        guard !opened else { return }
        await withCheckedContinuation { waiters.append($0) }
    }

    func open() {
        opened = true
        let continuations = waiters
        waiters.removeAll()
        continuations.forEach { $0.resume() }
    }
}

private actor TestPostFenceGate {
    private var entered = false
    private var released = false
    private var entryWaiters: [CheckedContinuation<Void, Never>] = []
    private var releaseWaiters: [CheckedContinuation<Void, Never>] = []

    func blockUntilReleased() async {
        entered = true
        let waitingForEntry = entryWaiters
        entryWaiters.removeAll()
        waitingForEntry.forEach { $0.resume() }
        guard !released else { return }
        await withCheckedContinuation { releaseWaiters.append($0) }
    }

    func waitUntilEntered() async {
        guard !entered else { return }
        await withCheckedContinuation { entryWaiters.append($0) }
    }

    func release() {
        released = true
        let waitingForRelease = releaseWaiters
        releaseWaiters.removeAll()
        waitingForRelease.forEach { $0.resume() }
    }
}
