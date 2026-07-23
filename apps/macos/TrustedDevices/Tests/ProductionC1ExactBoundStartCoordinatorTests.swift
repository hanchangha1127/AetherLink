import Foundation
@testable import P2PNATContracts
@_spi(TrustedDeviceTesting) @testable import TrustedDevices
import XCTest

final class ProductionC1ExactBoundStartCoordinatorTests: XCTestCase {
    func testPublicationGateRejectsOverflowWithoutDisturbingHeldWriter() async throws {
        let gate = ProductionC1AuthorityPublicationGate(maximumWaiters: 2)
        let heldWriter = try await gate.acquireWrite()
        let first = Task { try await gate.acquireRead() }
        let second = Task { try await gate.acquireRead() }
        let bothQueued = await waitUntil(timeoutIterations: 1_000) {
            await gate.waitingCountForTesting() == 2
        }
        XCTAssertTrue(bothQueued)

        do {
            _ = try await gate.acquireRead()
            XCTFail("expected bounded waiter overflow")
        } catch let error as ProductionC1AuthorityPublicationGateError {
            XCTAssertEqual(error, .capacityExceeded)
        }

        first.cancel()
        second.cancel()
        for task in [first, second] {
            do {
                _ = try await task.value
                XCTFail("cancelled waiter unexpectedly acquired a permit")
            } catch is CancellationError {
                // Expected.
            }
        }
        let remainingAfterCancellation = await gate.waitingCountForTesting()
        XCTAssertEqual(remainingAfterCancellation, 0)

        await gate.releaseWrite(heldWriter)
        let read = try await gate.acquireRead()
        await gate.releaseRead(read)
    }

    func testPublicationGateCancellationStormRemovesEveryContinuation() async throws {
        let gate = ProductionC1AuthorityPublicationGate(maximumWaiters: 4)
        let heldWriter = try await gate.acquireWrite()

        for _ in 0..<64 {
            let task = Task { try await gate.acquireRead() }
            let queued = await waitUntil(timeoutIterations: 1_000) {
                await gate.waitingCountForTesting() == 1
            }
            XCTAssertTrue(queued)
            task.cancel()
            do {
                _ = try await task.value
                XCTFail("cancelled waiter unexpectedly acquired a permit")
            } catch is CancellationError {
                // Expected.
            }
            let remaining = await gate.waitingCountForTesting()
            XCTAssertEqual(remaining, 0)
        }

        await gate.releaseWrite(heldWriter)
        let write = try await gate.acquireWrite()
        await gate.releaseWrite(write)
    }

    func testPublicationGateAdmitsWritersInStrictFIFOOrder() async throws {
        let gate = ProductionC1AuthorityPublicationGate(maximumWaiters: 8)
        let recorder = PublicationAdmissionRecorder()
        let heldRead = try await gate.acquireRead()

        let first = Task {
            let permit = try await gate.acquireWrite()
            await recorder.append(1)
            await gate.releaseWrite(permit)
        }
        let firstQueued = await waitUntil(timeoutIterations: 1_000) {
            await gate.waitingWriterCountForTesting() == 1
        }
        XCTAssertTrue(firstQueued)
        let second = Task {
            let permit = try await gate.acquireWrite()
            await recorder.append(2)
            await gate.releaseWrite(permit)
        }
        let secondQueued = await waitUntil(timeoutIterations: 1_000) {
            await gate.waitingWriterCountForTesting() == 2
        }
        XCTAssertTrue(secondQueued)
        let third = Task {
            let permit = try await gate.acquireWrite()
            await recorder.append(3)
            await gate.releaseWrite(permit)
        }
        let thirdQueued = await waitUntil(timeoutIterations: 1_000) {
            await gate.waitingWriterCountForTesting() == 3
        }
        XCTAssertTrue(thirdQueued)

        await gate.releaseRead(heldRead)
        try await first.value
        try await second.value
        try await third.value
        let admissionOrder = await recorder.snapshot()
        XCTAssertEqual(admissionOrder, [1, 2, 3])
    }

    func testPublicationGateCancelledWriterLetsQueuedReaderAdvanceExactlyOnce() async throws {
        let gate = ProductionC1AuthorityPublicationGate(maximumWaiters: 4)
        let heldRead = try await gate.acquireRead()
        let writer = Task { try await gate.acquireWrite() }
        let writerQueued = await waitUntil(timeoutIterations: 1_000) {
            await gate.waitingWriterCountForTesting() == 1
        }
        XCTAssertTrue(writerQueued)
        let reader = Task { try await gate.acquireRead() }
        let readerQueued = await waitUntil(timeoutIterations: 1_000) {
            await gate.waitingCountForTesting() == 2
        }
        XCTAssertTrue(readerQueued)

        writer.cancel()
        do {
            _ = try await writer.value
            XCTFail("cancelled writer unexpectedly acquired a permit")
        } catch is CancellationError {
            // Expected.
        }
        let remainingWriters = await gate.waitingWriterCountForTesting()
        XCTAssertEqual(remainingWriters, 0)

        await gate.releaseRead(heldRead)
        let queuedRead = try await reader.value
        await gate.releaseRead(queuedRead)
        let remaining = await gate.waitingCountForTesting()
        XCTAssertEqual(remaining, 0)
    }

    func testStoreCachesSingleExactBoundCoordinator() async {
        let store = TrustedDeviceStore(fileURL: temporaryFileURL())
        let first = await store.productionC1ExactBoundStartCoordinator()
        let second = await store.productionC1ExactBoundStartCoordinator()
        XCTAssertTrue(first === second)
    }

    func testPairReservationRejectsConcurrentAdmissionWhileValidationSuspends()
        async throws
    {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let first = validation(pair: "pair-a", marker: "marker-a")
        let competing = validation(pair: "pair-a", marker: "marker-b")
        let gate = ExactBoundValidationGate()
        let firstTask = Task {
            try await coordinator.admitForTesting(first) { validation in
                await gate.suspend(validation)
            }
        }
        await gate.waitUntilEntered()

        do {
            _ = try await coordinator.admitForTesting(competing) { $0 }
            XCTFail("Expected one live start per pair authority")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .pairAlreadyLive
            )
        }

        await gate.release()
        _ = try await firstTask.value
        let liveCount = await coordinator.liveCountForTesting()
        XCTAssertEqual(liveCount, 1)
    }

    func testRevocationDuringSuspendedValidationFencesLateResultAndReplay()
        async throws
    {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let gate = ExactBoundValidationGate()
        let task = Task {
            try await coordinator.admitForTesting(candidate) { validation in
                await gate.suspend(validation)
            }
        }
        await gate.waitUntilEntered()
        await coordinator.fenceRevoked(pairAuthorityDigest: candidate.pairAuthorityDigest)
        await gate.release()

        do {
            _ = try await task.value
            XCTFail("Expected a late validator result to remain fenced")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .fenced
            )
        }
        let liveCount = await coordinator.liveCountForTesting()
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(liveCount, 0)
        XCTAssertEqual(reasons, [.revoked])
        do {
            _ = try await coordinator.admitForTesting(candidate) { $0 }
            XCTFail("Expected terminal marker replay to fail closed")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .markerReplay
            )
        }
    }

    func testAuthorityAdvanceDuringBeginRevalidationCannotReviveAdmission()
        async throws
    {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let gate = ExactBoundValidationGate()
        let beginTask = Task {
            try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { validation in await gate.suspend(validation) }
            )
        }
        await gate.waitUntilEntered()
        await coordinator.fenceAuthorityAdvance(
            previousPairAuthorityDigest: candidate.pairAuthorityDigest
        )
        await gate.release()

        do {
            _ = try await beginTask.value
            XCTFail("Expected authority advance to fence begin")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .fenced
            )
        }
        let liveCount = await coordinator.liveCountForTesting()
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(liveCount, 0)
        XCTAssertEqual(reasons, [.authorityAdvanced])
    }

    func testCancelDuringSuspendedStartCannotBecomeActive() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let gate = ExactBoundVoidGate()
        let resource = ExactBoundLateStartResource()
        let beginTask = Task {
            try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 },
                start: { _ in
                    await gate.suspend()
                    await resource.publish()
                },
                abort: { _ in await resource.abort() }
            )
        }
        await gate.waitUntilEntered()
        let cancelTask = Task { try await coordinator.cancel(handle) }
        let firstAbortStarted = await waitUntil(timeoutIterations: 1_000) {
            await resource.abortCount() == 1
        }
        XCTAssertTrue(firstAbortStarted)
        let inFlightAbortCount = await resource.abortCount()
        XCTAssertEqual(inFlightAbortCount, 1)
        let closesBeforeLatePublish = await resource.closeCount()
        XCTAssertEqual(closesBeforeLatePublish, 0)
        await gate.release()
        try await cancelTask.value

        do {
            _ = try await beginTask.value
            XCTFail("Expected cancelled start completion to remain fenced")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .fenced
            )
        }
        let liveCount = await coordinator.liveCountForTesting()
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(liveCount, 0)
        XCTAssertEqual(reasons, [.cancelled])
        let abortCount = await resource.abortCount()
        let closeCount = await resource.closeCount()
        let isPublished = await resource.isPublished()
        let abortObservedCancellation = await resource.observedCancellation()
        XCTAssertEqual(abortCount, 2)
        XCTAssertEqual(closeCount, 1)
        XCTAssertFalse(isPublished)
        XCTAssertEqual(abortObservedCancellation, [false, false])
    }

    func testDetachedStartSelfFenceDefersLateAbortAndRetainsPairReservation()
        async throws
    {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let resource = ExactBoundDeferredAbortResource()
        let beginTask = Task {
            try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 },
                start: { operationContext in
                    await Task.detached {
                        await coordinator.fenceRevoked(
                            pairAuthorityDigest: candidate.pairAuthorityDigest,
                            operationContext: operationContext
                        )
                    }.value
                    await resource.publish()
                },
                abort: { _ in await resource.abort() }
            )
        }

        let lateAbortStarted = await waitUntil(timeoutIterations: 1_000) {
            await resource.abortCount() == 2
        }
        XCTAssertTrue(
            lateAbortStarted,
            "A start-originated fence must return after the first abort"
        )
        guard lateAbortStarted else { return }
        let eventsDuringLateAbort = await resource.events()
        XCTAssertEqual(eventsDuringLateAbort, ["abort-1", "publish", "abort-2"])
        let closeCountDuringLateAbort = await resource.closeCount()
        let isPublishedDuringLateAbort = await resource.isPublished()
        XCTAssertEqual(closeCountDuringLateAbort, 1)
        XCTAssertFalse(isPublishedDuringLateAbort)

        let competing = validation(pair: "pair-a", marker: "marker-b")
        do {
            _ = try await coordinator.admitForTesting(competing) { $0 }
            XCTFail("Expected the deferred abort to retain the pair reservation")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .pairAlreadyLive
            )
        }

        await resource.releaseLateAbort()
        do {
            _ = try await beginTask.value
            XCTFail("Expected the self-fenced start to remain fenced")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .fenced
            )
        }
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.revoked])

        let replacement = try await coordinator.admitForTesting(competing) { $0 }
        XCTAssertEqual(replacement.markerDigest, competing.markerDigest)
        XCTAssertGreaterThan(replacement.generation, handle.generation)
    }

    func testCancellationDuringDelayedFirstSelfAbortCleansLatePublication()
        async throws
    {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let resource = ExactBoundDelayedFirstAbortResource()
        let beginTask = Task {
            try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 },
                start: { operationContext in
                    _ = Task.detached {
                        await coordinator.fenceRevoked(
                            pairAuthorityDigest: candidate.pairAuthorityDigest,
                            operationContext: operationContext
                        )
                    }
                    do {
                        try await Task.sleep(for: .seconds(60))
                    } catch {
                        await resource.publish()
                        throw error
                    }
                },
                abort: { _ in await resource.abort() }
            )
        }
        await resource.waitUntilFirstAbortEntered()

        beginTask.cancel()
        let latePublicationObserved = await waitUntil(timeoutIterations: 1_000) {
            await resource.isPublished()
        }
        XCTAssertTrue(latePublicationObserved)
        guard latePublicationObserved else { return }

        let competing = validation(pair: "pair-a", marker: "marker-b")
        do {
            _ = try await coordinator.admitForTesting(competing) { $0 }
            XCTFail("Expected the delayed first abort to retain the reservation")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .pairAlreadyLive
            )
        }

        await resource.releaseFirstAbort()
        do {
            _ = try await beginTask.value
            XCTFail("Expected producer cancellation to fail begin")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }

        let abortCount = await resource.abortCount()
        let closeCount = await resource.closeCount()
        let isPublished = await resource.isPublished()
        XCTAssertEqual(abortCount, 2)
        XCTAssertEqual(closeCount, 1)
        XCTAssertFalse(isPublished)

        let replacement = try await coordinator.admitForTesting(competing) { $0 }
        XCTAssertEqual(replacement.markerDigest, competing.markerDigest)
        XCTAssertGreaterThan(replacement.generation, handle.generation)
    }

    func testDetachedStartSelfCancelUsesContextAndReleasesReservation()
        async throws
    {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let resource = ExactBoundDeferredAbortResource()
        let beginTask = Task {
            try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 },
                start: { operationContext in
                    try await Task.detached {
                        try await coordinator.cancel(
                            handle,
                            operationContext: operationContext
                        )
                    }.value
                    await resource.publish()
                },
                abort: { _ in await resource.abort() }
            )
        }

        let lateAbortStarted = await waitUntil(timeoutIterations: 1_000) {
            await resource.abortCount() == 2
        }
        XCTAssertTrue(lateAbortStarted)
        guard lateAbortStarted else { return }

        let competing = validation(pair: "pair-a", marker: "marker-b")
        do {
            _ = try await coordinator.admitForTesting(competing) { $0 }
            XCTFail("Expected self-cancel cleanup to retain the reservation")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .pairAlreadyLive
            )
        }

        await resource.releaseLateAbort()
        do {
            _ = try await beginTask.value
            XCTFail("Expected the self-cancelled start to remain fenced")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .fenced
            )
        }
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.cancelled])

        let replacement = try await coordinator.admitForTesting(competing) { $0 }
        XCTAssertEqual(replacement.markerDigest, competing.markerDigest)
        XCTAssertGreaterThan(replacement.generation, handle.generation)
    }

    func testExternalFenceFirstAllowsDetachedStartReentryAndLateAbort()
        async throws
    {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let startGate = ExactBoundVoidGate()
        let resource = ExactBoundLateStartResource()
        let beginTask = Task {
            try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 },
                start: { operationContext in
                    await startGate.suspend()
                    await Task.detached {
                        await coordinator.fenceRevoked(
                            pairAuthorityDigest: candidate.pairAuthorityDigest,
                            operationContext: operationContext
                        )
                    }.value
                    await resource.publish()
                },
                abort: { _ in await resource.abort() }
            )
        }
        await startGate.waitUntilEntered()

        let fenceTask = Task {
            await coordinator.fenceRevoked(
                pairAuthorityDigest: candidate.pairAuthorityDigest
            )
        }
        let firstAbortStarted = await waitUntil(timeoutIterations: 1_000) {
            await resource.abortCount() == 1
        }
        XCTAssertTrue(firstAbortStarted)
        guard firstAbortStarted else { return }

        await startGate.release()
        await fenceTask.value
        do {
            _ = try await beginTask.value
            XCTFail("Expected the externally fenced start to remain fenced")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .fenced
            )
        }
        let abortCount = await resource.abortCount()
        let closeCount = await resource.closeCount()
        let isPublished = await resource.isPublished()
        XCTAssertEqual(abortCount, 2)
        XCTAssertEqual(closeCount, 1)
        XCTAssertFalse(isPublished)
    }

    func testDetachedAbortReentryDoesNotWaitForItsOwnCleanup() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let abortCompleted = ExactBoundAbortRecorder()
        _ = try await coordinator.beginForTesting(
            handle,
            claimed: candidate,
            validator: { $0 },
            start: { _ in },
            abort: { operationContext in
                await Task.detached {
                    await coordinator.fenceRevoked(
                        pairAuthorityDigest: candidate.pairAuthorityDigest,
                        operationContext: operationContext
                    )
                }.value
                await abortCompleted.record()
            }
        )

        let fenceTask = Task {
            await coordinator.fenceRevoked(
                pairAuthorityDigest: candidate.pairAuthorityDigest
            )
        }
        let reentryCompleted = await waitUntil(timeoutIterations: 1_000) {
            await abortCompleted.value() == 1
        }
        XCTAssertTrue(
            reentryCompleted,
            "A detached abort reentry must not wait for its own cleanup"
        )
        guard reentryCompleted else { return }
        await fenceTask.value

        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        let liveCount = await coordinator.liveCountForTesting()
        XCTAssertEqual(reasons, [.revoked])
        XCTAssertEqual(liveCount, 0)
    }

    func testDetachedAbortContextCancelRejectsTerminalHandleAndReleasesPair()
        async throws
    {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let abortCompleted = ExactBoundAbortRecorder()
        let cancelErrors = ExactBoundCoordinatorErrorRecorder()
        _ = try await coordinator.beginForTesting(
            handle,
            claimed: candidate,
            validator: { $0 },
            start: { _ in },
            abort: { operationContext in
                let cancelError = await Task.detached {
                    () -> ProductionC1ExactBoundStartCoordinatorError? in
                    do {
                        try await coordinator.cancel(
                            handle,
                            operationContext: operationContext
                        )
                        return nil
                    } catch {
                        return error as? ProductionC1ExactBoundStartCoordinatorError
                    }
                }.value
                if let cancelError {
                    await cancelErrors.record(cancelError)
                }
                await abortCompleted.record()
            }
        )

        let fenceTask = Task {
            await coordinator.fenceRevoked(
                pairAuthorityDigest: candidate.pairAuthorityDigest
            )
        }
        let reentryCompleted = await waitUntil(timeoutIterations: 1_000) {
            await abortCompleted.value() == 1
        }
        XCTAssertTrue(reentryCompleted)
        guard reentryCompleted else { return }
        await fenceTask.value

        let recordedErrors = await cancelErrors.values()
        XCTAssertEqual(recordedErrors, [.invalidHandle])
        let competing = validation(pair: "pair-a", marker: "marker-b")
        let replacement = try await coordinator.admitForTesting(competing) { $0 }
        XCTAssertEqual(replacement.markerDigest, competing.markerDigest)
        XCTAssertGreaterThan(replacement.generation, handle.generation)
    }

    func testAbortBeforeStartSkipsStartAction() async throws {
        let startRecorder = ExactBoundAbortRecorder()
        let abortRecorder = ExactBoundAbortRecorder()

        try await ProductionC1ExactBoundStartCoordinator
            .runPreStartAbortForTesting(
                start: { _ in await startRecorder.record() },
                abort: { _ in await abortRecorder.record() }
            )

        let startCount = await startRecorder.value()
        let abortCount = await abortRecorder.value()
        XCTAssertEqual(startCount, 0)
        XCTAssertEqual(abortCount, 1)
    }

    func testStartThrowAfterPartialSideEffectAbortsExactlyOnce() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let abortRecorder = ExactBoundAbortRecorder()

        do {
            _ = try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 },
                start: { _ in throw ExactBoundTestError.failed },
                abort: { _ in await abortRecorder.record() }
            )
            XCTFail("Expected partial start failure")
        } catch {
            XCTAssertEqual(error as? ExactBoundTestError, .failed)
        }
        let abortCount = await abortRecorder.value()
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(abortCount, 1)
        XCTAssertEqual(reasons, [.startFailed])
    }

    func testBeginValidatorFailureTerminalizesAdmittedRecord() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }

        do {
            _ = try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { _ in throw ExactBoundTestError.failed }
            )
            XCTFail("Expected begin revalidation failure")
        } catch {
            XCTAssertEqual(error as? ExactBoundTestError, .failed)
        }
        let liveCount = await coordinator.liveCountForTesting()
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(liveCount, 0)
        XCTAssertEqual(reasons, [.validationFailed])
    }

    func testPostStartExactRevalidationIsFencedWhenAuthorityChanges() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let validator = ExactBoundSecondCallGate()
        let beginTask = Task {
            try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { validation in await validator.validate(validation) }
            )
        }
        await validator.waitUntilSecondCallEntered()
        await coordinator.fenceAuthorityAdvance(
            previousPairAuthorityDigest: candidate.pairAuthorityDigest
        )
        await validator.release()

        do {
            _ = try await beginTask.value
            XCTFail("Expected post-start validation result to remain fenced")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .fenced
            )
        }
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.authorityAdvanced])
    }

    func testPostStartValidatorFailureAbortsExactlyOnce() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let validator = ExactBoundFailingSecondValidator()
        let abortRecorder = ExactBoundAbortRecorder()

        do {
            _ = try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { validation in try await validator.validate(validation) },
                start: { _ in },
                abort: { _ in await abortRecorder.record() }
            )
            XCTFail("Expected post-start exact validation failure")
        } catch {
            XCTAssertEqual(error as? ExactBoundTestError, .failed)
        }
        let abortCount = await abortRecorder.value()
        XCTAssertEqual(abortCount, 1)
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.validationFailed])
    }

    func testTaskCancellationAfterLateStartSuccessStillAbortsExactlyOnce()
        async throws
    {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let gate = ExactBoundVoidGate()
        let abortRecorder = ExactBoundAbortRecorder()
        let beginTask = Task {
            try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 },
                start: { _ in await gate.suspend() },
                abort: { _ in await abortRecorder.record() }
            )
        }
        await gate.waitUntilEntered()
        beginTask.cancel()
        await gate.release()

        do {
            _ = try await beginTask.value
            XCTFail("Expected cancellation after late start success")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }
        let abortCount = await abortRecorder.value()
        let abortObservedCancellation = await abortRecorder.observedCancellation()
        XCTAssertEqual(abortCount, 1)
        XCTAssertEqual(abortObservedCancellation, [false])
    }

    func testCancellationAfterFinalCheckPreservesSuccessfulTaskValue()
        async throws
    {
        let afterFinalCheck = ExactBoundVoidGate()
        let task = Task<String, Error> {
            try Task.checkCancellation()
            await afterFinalCheck.suspend()
            return "lease"
        }
        await afterFinalCheck.waitUntilEntered()

        task.cancel()
        await afterFinalCheck.release()

        let value = try await task.value
        XCTAssertEqual(value, "lease")
    }

    func testActiveRevokeAndExpiryEachAbortExactlyOnce() async throws {
        let revokeCoordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let revokeCandidate = validation(pair: "pair-revoke", marker: "marker-revoke")
        let revokeHandle = try await revokeCoordinator
            .admitForTesting(revokeCandidate) { $0 }
        let revokeAbort = ExactBoundAbortRecorder()
        _ = try await revokeCoordinator.beginForTesting(
            revokeHandle,
            claimed: revokeCandidate,
            validator: { $0 },
            start: { _ in },
            abort: { _ in
                await revokeCoordinator.fenceRevoked(
                    pairAuthorityDigest: revokeCandidate.pairAuthorityDigest
                )
                await revokeAbort.record()
            }
        )
        await revokeCoordinator.fenceRevoked(
            pairAuthorityDigest: revokeCandidate.pairAuthorityDigest
        )
        await revokeCoordinator.fenceRevoked(
            pairAuthorityDigest: revokeCandidate.pairAuthorityDigest
        )
        let revokeAbortCount = await revokeAbort.value()
        XCTAssertEqual(revokeAbortCount, 1)

        let clock = ExactBoundClock(100)
        let expiryCoordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            clock.get()
        }
        let expiryCandidate = validation(
            pair: "pair-expiry",
            marker: "marker-expiry",
            expiresAtMs: 200
        )
        let expiryHandle = try await expiryCoordinator
            .admitForTesting(expiryCandidate) { $0 }
        let expiryAbort = ExactBoundAbortRecorder()
        _ = try await expiryCoordinator.beginForTesting(
            expiryHandle,
            claimed: expiryCandidate,
            validator: { $0 },
            start: { _ in },
            abort: { _ in await expiryAbort.record() }
        )
        clock.set(200)
        await expiryCoordinator.fenceExpired()
        await expiryCoordinator.fenceExpired()
        let expiryAbortCount = await expiryAbort.value()
        XCTAssertEqual(expiryAbortCount, 1)
    }

    func testExpiryFenceStartsEveryPairAbortBeforeAwaitingSlowCleanup()
        async throws
    {
        let clock = ExactBoundClock(100)
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            clock.get()
        }
        let abortGate = ExactBoundParallelAbortGate()

        for index in 0..<2 {
            let candidate = validation(
                pair: "pair-\(index)",
                marker: "marker-\(index)",
                expiresAtMs: 200
            )
            let handle = try await coordinator.admitForTesting(candidate) { $0 }
            _ = try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 },
                start: { _ in },
                abort: { _ in await abortGate.suspend() }
            )
        }

        clock.set(200)
        let fenceTask = Task { await coordinator.fenceExpired() }
        let bothAbortsStarted = await waitUntil(timeoutIterations: 1_000) {
            await abortGate.enteredCount() == 2
        }
        XCTAssertTrue(
            bothAbortsStarted,
            "A slow abort must not prevent another pair's abort from starting"
        )

        await abortGate.releaseAll()
        await fenceTask.value
        let liveCount = await coordinator.liveCountForTesting()
        XCTAssertEqual(liveCount, 0)
    }

    func testActiveCancelAbortsExactlyOnce() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let abortRecorder = ExactBoundAbortRecorder()
        let lease = try await coordinator.beginForTesting(
            handle,
            claimed: candidate,
            validator: { $0 },
            start: { _ in },
            abort: { _ in await abortRecorder.record() }
        )
        try await coordinator.cancel(lease)
        let abortCount = await abortRecorder.value()
        XCTAssertEqual(abortCount, 1)
    }

    func testSlowAbortKeepsPairReservedUntilExactAbortClaimCompletes() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let abortGate = ExactBoundVoidGate()
        let lease = try await coordinator.beginForTesting(
            handle,
            claimed: candidate,
            validator: { $0 },
            start: { _ in },
            abort: { _ in await abortGate.suspend() }
        )

        let cancelTask = Task { try await coordinator.cancel(lease) }
        await abortGate.waitUntilEntered()

        let competing = validation(pair: "pair-a", marker: "marker-b")
        do {
            _ = try await coordinator.admitForTesting(competing) { $0 }
            XCTFail("Expected slow abort to retain the pair reservation")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .pairAlreadyLive
            )
        }

        await abortGate.release()
        try await cancelTask.value

        let replacement = try await coordinator.admitForTesting(competing) { $0 }
        XCTAssertEqual(replacement.markerDigest, competing.markerDigest)
        XCTAssertGreaterThan(replacement.generation, handle.generation)
    }

    func testCompleteIsNaturalTerminationAndDoesNotAbort() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let abortRecorder = ExactBoundAbortRecorder()
        let lease = try await coordinator.beginForTesting(
            handle,
            claimed: candidate,
            validator: { $0 },
            start: { _ in },
            abort: { _ in await abortRecorder.record() }
        )
        try await coordinator.complete(lease)
        let abortCount = await abortRecorder.value()
        XCTAssertEqual(abortCount, 0)
    }

    func testCompleteCancelRaceTransfersAbortOwnershipAtMostOnce() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let candidate = validation(pair: "pair-a", marker: "marker-a")
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let abortRecorder = ExactBoundAbortRecorder()
        let lease = try await coordinator.beginForTesting(
            handle,
            claimed: candidate,
            validator: { $0 },
            start: { _ in },
            abort: { _ in await abortRecorder.record() }
        )

        async let completed: Bool = {
            do {
                try await coordinator.complete(lease)
                return true
            } catch { return false }
        }()
        async let cancelled: Bool = {
            do {
                try await coordinator.cancel(lease)
                return true
            } catch { return false }
        }()
        let results = await (completed, cancelled)
        let winners = [results.0, results.1]
        XCTAssertEqual(winners.filter { $0 }.count, 1)
        let abortCount = await abortRecorder.value()
        XCTAssertEqual(abortCount, winners[1] ? 1 : 0)
    }

    func testExpiryFenceInvalidatesAdmittedHandle() async throws {
        let clock = ExactBoundClock(100)
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            clock.get()
        }
        let candidate = validation(
            pair: "pair-a",
            marker: "marker-a",
            expiresAtMs: 200
        )
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        clock.set(200)

        do {
            _ = try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 }
            )
            XCTFail("Expected expiry at the exact upper bound")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .expired
            )
        }
        let reasons = await coordinator.tombstonesForTesting().map(\.reason)
        XCTAssertEqual(reasons, [.expired])
    }

    func testTerminalTombstonesAreSecretFreeAndBoundedTo64() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        for index in 0..<70 {
            let candidate = validation(
                pair: "pair-a",
                marker: "marker-\(index)"
            )
            let handle = try await coordinator.admitForTesting(candidate) { $0 }
            let lease = try await coordinator.beginForTesting(
                handle,
                claimed: candidate,
                validator: { $0 }
            )
            try await coordinator.complete(lease)
        }

        let tombstones = await coordinator.tombstonesForTesting()
        XCTAssertEqual(tombstones.count, 64)
        XCTAssertEqual(tombstones.first?.generation, 7)
        XCTAssertEqual(tombstones.last?.generation, 70)
        XCTAssertEqual(
            Set(Mirror(reflecting: try XCTUnwrap(tombstones.last)).children.compactMap(\.label)),
            ["pairAuthorityDigest", "markerDigest", "generation", "reason"]
        )
    }

    func testOtherPairRetentionCannotEvictReplayFence() async throws {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting {
            100
        }
        let quietPair = validation(pair: "quiet-pair", marker: "quiet-marker")
        let quietHandle = try await coordinator.admitForTesting(quietPair) { $0 }
        let quietLease = try await coordinator.beginForTesting(
            quietHandle,
            claimed: quietPair,
            validator: { $0 }
        )
        try await coordinator.complete(quietLease)

        for index in 0..<70 {
            let noisy = validation(pair: "noisy-pair", marker: "noisy-\(index)")
            let handle = try await coordinator.admitForTesting(noisy) { $0 }
            let lease = try await coordinator.beginForTesting(
                handle,
                claimed: noisy,
                validator: { $0 }
            )
            try await coordinator.complete(lease)
        }

        do {
            _ = try await coordinator.admitForTesting(quietPair) { $0 }
            XCTFail("Expected another pair's churn not to evict the replay fence")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .markerReplay
            )
        }
    }

    func testCheckedGenerationRejectsUInt64Overflow() async {
        let coordinator = ProductionC1ExactBoundStartCoordinator.makeForTesting(
            nowMs: { 100 },
            initialGeneration: UInt64.max
        )
        do {
            _ = try await coordinator.admitForTesting(
                validation(pair: "pair-a", marker: "marker-a")
            ) { $0 }
            XCTFail("Expected checked generation overflow")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1ExactBoundStartCoordinatorError,
                .generationOverflow
            )
        }
    }

    func testDurablePairTransitionsAndRemoveAutomaticallyFenceCachedCoordinator()
        async throws
    {
        let revoke = try await activeStoreFixture(marker: "revoke-marker")
        let revokedAuthority = try nextAuthority(
            from: revoke.authority,
            status: .revoked,
            generation: revoke.authority.generation,
            revocationCounter: revoke.authority.revocationCounter + 1,
            transitionDigit: "7"
        )
        _ = try await revoke.store.applyVerifiedProductionPairTransition(
            deviceID: revoke.device.id,
            expectedPublicKeyBase64: revoke.device.publicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: try revoke.authority.digestHex(),
                nextAuthority: revokedAuthority
            )
        )
        let revokeAbortCount = await revoke.abortRecorder.value()
        let revokeReasons = await revoke.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(revokeAbortCount, 1)
        XCTAssertEqual(revokeReasons, [.revoked])

        let advance = try await activeStoreFixture(marker: "advance-marker")
        let advancedAuthority = try nextAuthority(
            from: advance.authority,
            status: .active,
            generation: advance.authority.generation + 1,
            revocationCounter: advance.authority.revocationCounter,
            transitionDigit: "8"
        )
        _ = try await advance.store.applyVerifiedProductionPairTransition(
            deviceID: advance.device.id,
            expectedPublicKeyBase64: advance.device.publicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: try advance.authority.digestHex(),
                nextAuthority: advancedAuthority
            )
        )
        let advanceAbortCount = await advance.abortRecorder.value()
        let advanceReasons = await advance.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(advanceAbortCount, 1)
        XCTAssertEqual(advanceReasons, [.authorityAdvanced])

        let removed = try await activeStoreFixture(marker: "remove-marker")
        try await removed.store.remove(deviceID: removed.device.id)
        let removeAbortCount = await removed.abortRecorder.value()
        let removeReasons = await removed.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(removeAbortCount, 1)
        XCTAssertEqual(removeReasons, [.revoked])
    }

    func testDurabilityUncertainPairTransitionAndRemoveFenceOldSessions()
        async throws
    {
        let transitionFailure = ExactBoundFailureSwitch()
        let transition = try await activeStoreFixture(
            marker: "uncertain-transition",
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                shouldFailDirectorySyncAfterRename: {
                    transitionFailure.isEnabled()
                }
            )
        )
        transitionFailure.enable()
        let advanced = try nextAuthority(
            from: transition.authority,
            status: .active,
            generation: transition.authority.generation + 1,
            revocationCounter: transition.authority.revocationCounter,
            transitionDigit: "9"
        )
        do {
            _ = try await transition.store.applyVerifiedProductionPairTransition(
                deviceID: transition.device.id,
                expectedPublicKeyBase64: transition.device.publicKeyBase64,
                transition: ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest:
                        try transition.authority.digestHex(),
                    nextAuthority: advanced
                )
            )
            XCTFail("Expected post-rename durability uncertainty")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .durabilityUncertainAfterRename
            )
        }
        let transitionAbortCount = await transition.abortRecorder.value()
        XCTAssertEqual(transitionAbortCount, 1)
        let transitionReasons = await transition.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(transitionReasons, [.authorityAdvanced])

        let removeFailure = ExactBoundFailureSwitch()
        let removed = try await activeStoreFixture(
            marker: "uncertain-remove",
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                shouldFailDirectorySyncAfterRename: {
                    removeFailure.isEnabled()
                }
            )
        )
        removeFailure.enable()
        do {
            try await removed.store.remove(deviceID: removed.device.id)
            XCTFail("Expected post-rename remove durability uncertainty")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .durabilityUncertainAfterRename
            )
        }
        let removeAbortCount = await removed.abortRecorder.value()
        XCTAssertEqual(removeAbortCount, 1)
        let removeReasons = await removed.coordinator
            .tombstonesForTesting().map(\.reason)
        XCTAssertEqual(removeReasons, [.revoked])
    }

    func testPreRenamePairTransitionFailureKeepsOldSessionPublished()
        async throws
    {
        let failure = ExactBoundFailureSwitch()
        let fixture = try await activeStoreFixture(
            marker: "pre-rename-failure",
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didPrepareAtomicReplacement: { temporaryURL in
                    if failure.isEnabled() {
                        try? FileManager.default.removeItem(at: temporaryURL)
                    }
                }
            )
        )
        failure.enable()
        let advanced = try nextAuthority(
            from: fixture.authority,
            status: .active,
            generation: fixture.authority.generation + 1,
            revocationCounter: fixture.authority.revocationCounter,
            transitionDigit: "a"
        )
        do {
            _ = try await fixture.store.applyVerifiedProductionPairTransition(
                deviceID: fixture.device.id,
                expectedPublicKeyBase64: fixture.device.publicKeyBase64,
                transition: ProductionPairStateTransition(
                    expectedPreviousAuthorityDigest:
                        try fixture.authority.digestHex(),
                    nextAuthority: advanced
                )
            )
            XCTFail("Expected pre-rename replacement failure")
        } catch {
            guard case .ioFailure = error as? TrustedDeviceStoreError else {
                XCTFail("Unexpected failure: \(error)")
                return
            }
        }
        let abortCount = await fixture.abortRecorder.value()
        let liveCount = await fixture.coordinator.liveCountForTesting()
        XCTAssertEqual(abortCount, 0)
        XCTAssertEqual(liveCount, 1)
    }

    private func validation(
        pair: String,
        marker: String,
        expiresAtMs: UInt64 = 1_000
    ) -> ProductionC1ExactBoundStartValidation {
        ProductionC1ExactBoundStartValidation(
            deviceID: "device",
            pairAuthorityDigest: pair,
            markerDigest: marker,
            admissionID: "admission-\(marker)",
            bindingDigest: "binding-\(marker)",
            sessionID: "session-\(marker)",
            effectiveNotBeforeMs: 0,
            expiresAtMs: expiresAtMs,
            pairLocalRevision: 2,
            ledgerRevision: 2
        )
    }

    private func temporaryFileURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("trusted-devices.json")
    }

    private func waitUntil(
        timeoutIterations: Int,
        condition: @escaping @Sendable () async -> Bool
    ) async -> Bool {
        for _ in 0..<timeoutIterations {
            if await condition() { return true }
            try? await Task.sleep(for: .milliseconds(1))
        }
        return false
    }

    private func activeStoreFixture(
        marker: String,
        synchronizationHooks: TrustedDeviceStoreSynchronizationHooks =
            TrustedDeviceStoreSynchronizationHooks()
    ) async throws -> (
        store: TrustedDeviceStore,
        coordinator: ProductionC1ExactBoundStartCoordinator,
        device: TrustedDevice,
        authority: ProductionPairAuthorityState,
        abortRecorder: ExactBoundAbortRecorder
    ) {
        let store = TrustedDeviceStore(
            fileURL: temporaryFileURL(),
            synchronizationHooks: synchronizationHooks
        )
        let device = TrustedDevice(
            id: "device-\(marker)",
            name: marker,
            publicKeyBase64: "key-\(marker)"
        )
        try await store.trust(device)
        let authority = try ProductionPairAuthorityState(
            pairBindingDigest: String(repeating: "1", count: 64),
            pairEpoch: 1,
            clientIdentityFingerprint: String(repeating: "2", count: 64),
            runtimeIdentityFingerprint: String(repeating: "3", count: 64),
            generation: 1,
            serviceConfigVersion: 1,
            keysetVersion: 1,
            revocationCounter: 0,
            protocolFloor: 1,
            status: .active,
            transitionId: String(repeating: "4", count: 64),
            transitionRequestDigest: String(repeating: "5", count: 64),
            acceptedReceiptDigest: String(repeating: "6", count: 64),
            authorityRevision: 1
        )
        _ = try await store.installProductionPairStateForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            authority: authority
        )
        let coordinator = await store.productionC1ExactBoundStartCoordinator()
        let candidate = validation(
            pair: try authority.digestHex(),
            marker: marker,
            expiresAtMs: UInt64.max
        )
        let handle = try await coordinator.admitForTesting(candidate) { $0 }
        let abortRecorder = ExactBoundAbortRecorder()
        _ = try await coordinator.beginForTesting(
            handle,
            claimed: candidate,
            validator: { $0 },
            start: { _ in },
            abort: { _ in await abortRecorder.record() }
        )
        return (store, coordinator, device, authority, abortRecorder)
    }

    private func nextAuthority(
        from previous: ProductionPairAuthorityState,
        status: ProductionPairAuthorityStatus,
        generation: UInt64,
        revocationCounter: UInt64,
        transitionDigit: Character
    ) throws -> ProductionPairAuthorityState {
        try ProductionPairAuthorityState(
            pairBindingDigest: previous.pairBindingDigest,
            pairEpoch: previous.pairEpoch,
            clientIdentityFingerprint: previous.clientIdentityFingerprint,
            runtimeIdentityFingerprint: previous.runtimeIdentityFingerprint,
            generation: generation,
            serviceConfigVersion: previous.serviceConfigVersion,
            keysetVersion: previous.keysetVersion,
            revocationCounter: revocationCounter,
            protocolFloor: previous.protocolFloor,
            status: status,
            transitionId: String(repeating: String(transitionDigit), count: 64),
            transitionRequestDigest: String(
                repeating: String(transitionDigit),
                count: 64
            ),
            acceptedReceiptDigest: previous.acceptedReceiptDigest,
            authorityRevision: previous.authorityRevision + 1
        )
    }
}

private actor PublicationAdmissionRecorder {
    private var values: [Int] = []

    func append(_ value: Int) {
        values.append(value)
    }

    func snapshot() -> [Int] {
        values
    }
}

private actor ExactBoundValidationGate {
    private var continuation: CheckedContinuation<Void, Never>?
    private var entered = false

    func suspend(
        _ validation: ProductionC1ExactBoundStartValidation
    ) async -> ProductionC1ExactBoundStartValidation {
        entered = true
        await withCheckedContinuation { continuation = $0 }
        return validation
    }

    func waitUntilEntered() async {
        while !entered { await Task.yield() }
    }

    func release() {
        continuation?.resume()
        continuation = nil
    }
}

private actor ExactBoundVoidGate {
    private var continuation: CheckedContinuation<Void, Never>?
    private var entered = false

    func suspend() async {
        entered = true
        await withCheckedContinuation { continuation = $0 }
    }

    func waitUntilEntered() async {
        while !entered { await Task.yield() }
    }

    func release() {
        continuation?.resume()
        continuation = nil
    }
}

private actor ExactBoundParallelAbortGate {
    private var continuations: [CheckedContinuation<Void, Never>] = []
    private var count = 0
    private var isReleased = false

    func suspend() async {
        count += 1
        guard !isReleased else { return }
        await withCheckedContinuation { continuations.append($0) }
    }

    func enteredCount() -> Int { count }

    func releaseAll() {
        isReleased = true
        let waiting = continuations
        continuations.removeAll()
        for continuation in waiting { continuation.resume() }
    }
}

private actor ExactBoundLateStartResource {
    private var published = false
    private var aborts = 0
    private var closes = 0
    private var cancellationObservations: [Bool] = []

    func publish() { published = true }

    func abort() {
        aborts += 1
        cancellationObservations.append(Task.isCancelled)
        if published {
            published = false
            closes += 1
        }
    }

    func abortCount() -> Int { aborts }
    func closeCount() -> Int { closes }
    func isPublished() -> Bool { published }
    func observedCancellation() -> [Bool] { cancellationObservations }
}

private actor ExactBoundDeferredAbortResource {
    private var published = false
    private var aborts = 0
    private var closes = 0
    private var recordedEvents: [String] = []
    private var lateAbortContinuation: CheckedContinuation<Void, Never>?

    func publish() {
        published = true
        recordedEvents.append("publish")
    }

    func abort() async {
        aborts += 1
        recordedEvents.append("abort-\(aborts)")
        if published {
            published = false
            closes += 1
        }
        guard aborts == 2 else { return }
        await withCheckedContinuation { lateAbortContinuation = $0 }
    }

    func releaseLateAbort() {
        lateAbortContinuation?.resume()
        lateAbortContinuation = nil
    }

    func abortCount() -> Int { aborts }
    func closeCount() -> Int { closes }
    func isPublished() -> Bool { published }
    func events() -> [String] { recordedEvents }
}

private actor ExactBoundDelayedFirstAbortResource {
    private var published = false
    private var aborts = 0
    private var closes = 0
    private var firstAbortEntered = false
    private var firstAbortContinuation: CheckedContinuation<Void, Never>?

    func publish() { published = true }

    func abort() async {
        aborts += 1
        if aborts == 1 {
            firstAbortEntered = true
            await withCheckedContinuation { firstAbortContinuation = $0 }
        }
        if published {
            published = false
            closes += 1
        }
    }

    func waitUntilFirstAbortEntered() async {
        while !firstAbortEntered { await Task.yield() }
    }

    func releaseFirstAbort() {
        firstAbortContinuation?.resume()
        firstAbortContinuation = nil
    }

    func abortCount() -> Int { aborts }
    func closeCount() -> Int { closes }
    func isPublished() -> Bool { published }
}

private actor ExactBoundSecondCallGate {
    private var callCount = 0
    private var continuation: CheckedContinuation<Void, Never>?

    func validate(
        _ validation: ProductionC1ExactBoundStartValidation
    ) async -> ProductionC1ExactBoundStartValidation {
        callCount += 1
        if callCount == 2 {
            await withCheckedContinuation { continuation = $0 }
        }
        return validation
    }

    func waitUntilSecondCallEntered() async {
        while callCount < 2 { await Task.yield() }
    }

    func release() {
        continuation?.resume()
        continuation = nil
    }
}

private actor ExactBoundFailingSecondValidator {
    private var callCount = 0

    func validate(
        _ validation: ProductionC1ExactBoundStartValidation
    ) throws -> ProductionC1ExactBoundStartValidation {
        callCount += 1
        if callCount == 2 { throw ExactBoundTestError.failed }
        return validation
    }
}

private actor ExactBoundAbortRecorder {
    private var count = 0
    private var cancellationObservations: [Bool] = []

    func record() {
        count += 1
        cancellationObservations.append(Task.isCancelled)
    }
    func value() -> Int { count }
    func observedCancellation() -> [Bool] { cancellationObservations }
}

private final class ExactBoundFailureSwitch: @unchecked Sendable {
    private let lock = NSLock()
    private var enabled = false

    func enable() {
        lock.lock()
        enabled = true
        lock.unlock()
    }

    func isEnabled() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return enabled
    }
}

private actor ExactBoundCoordinatorErrorRecorder {
    private var recordedErrors: [ProductionC1ExactBoundStartCoordinatorError] = []

    func record(_ error: ProductionC1ExactBoundStartCoordinatorError) {
        recordedErrors.append(error)
    }

    func values() -> [ProductionC1ExactBoundStartCoordinatorError] {
        recordedErrors
    }
}

private enum ExactBoundTestError: Error, Equatable {
    case failed
}

private final class ExactBoundClock: @unchecked Sendable {
    private let lock = NSLock()
    private var value: UInt64

    init(_ value: UInt64) { self.value = value }

    func get() -> UInt64 {
        lock.lock()
        defer { lock.unlock() }
        return value
    }

    func set(_ value: UInt64) {
        lock.lock()
        self.value = value
        lock.unlock()
    }
}
