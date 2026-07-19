import Foundation
@testable import CompanionCore
import XCTest

final class RuntimeHostApprovalCoordinatorTests: XCTestCase {
    func testUnregisteredExactClaimIsRejectedWithoutAuditOrExecution() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let executions = LockedRecorder<String>()
        let request = try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "unregistered-request",
            execute: {
                executions.append("execute")
                return .success
            }
        )
        let coordinator = RuntimeHostApprovalCoordinator(
            persistence: persistence,
            permissionPolicyRegistry: registry,
            registeredActions: []
        )

        do {
            _ = try await coordinator.enqueue(request)
            XCTFail("An exact claim for an unregistered action must be rejected")
        } catch {
            assertCoordinatorError(error, is: .unavailable)
        }

        XCTAssertTrue(persistence.auditEvents.isEmpty)
        XCTAssertEqual(persistence.createCallCount, 0)
        XCTAssertTrue(executions.values.isEmpty)
    }

    func testRegisteredSyntheticActionReservesThenExecutesOnceAndCommitsBeforePublication()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let order = LockedRecorder<String>()
        let persistence = InMemoryHostApprovalPersistence(order: order)
        let executions = LockedRecorder<String>()
        let publications = LockedRecorder<RuntimeHostApprovalExecutionOutcome>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let request = try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "successful-request",
            authorizeAndClaimExecution: { reservation in
                order.append("authorize")
                let receipt = try reservation()
                order.append("authorized")
                return receipt
            },
            execute: {
                executions.append("execute")
                order.append("execute")
                return .success
            },
            prepareOutcomePublication: { outcome in
                return { terminalCommit in
                    try terminalCommit()
                    order.append("publish")
                    publications.append(outcome)
                }
            }
        )

        let operationID = try await coordinator.enqueue(request)
        try await coordinator.approve(operationID: operationID)

        XCTAssertEqual(executions.values, ["execute"])
        XCTAssertEqual(publications.values, [.success])
        XCTAssertEqual(
            order.values,
            [
                "pending",
                "authorize",
                "reserved",
                "authorized",
                "execute",
                "terminal:dispatch_succeeded",
                "publish",
            ]
        )
        XCTAssertEqual(persistence.state(operationID: operationID), .terminal(.dispatchSucceeded))
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved", "dispatch_succeeded"]
        )
        let pendingReviews = await coordinator.pendingReviews()
        XCTAssertTrue(pendingReviews.isEmpty)
    }

    func testReservationReceiptFromAnotherOperationCannotReplaceDurableReservation()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let receipts = LockedRecorder<RuntimeHostApprovalReservationReceipt>()
        let rejectedExecutions = LockedRecorder<String>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let firstOperationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "receipt-source",
            authorizeAndClaimExecution: { reservation in
                let receipt = try reservation()
                receipts.append(receipt)
                return receipt
            }
        ))
        try await coordinator.approve(operationID: firstOperationID)

        let rejectedOperationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "receipt-reuse",
            authorizeAndClaimExecution: { _ in
                receipts.values[0]
            },
            execute: {
                rejectedExecutions.append("execute")
                return .success
            }
        ))

        do {
            try await coordinator.approve(operationID: rejectedOperationID)
            XCTFail("A reservation receipt from another operation must fail closed")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        XCTAssertTrue(rejectedExecutions.values.isEmpty)
        XCTAssertEqual(persistence.reservationCallCount, 1)
        XCTAssertEqual(persistence.state(operationID: rejectedOperationID), .pending)
        let rejectedReviews = await coordinator.pendingReviews()
        XCTAssertTrue(rejectedReviews.isEmpty)
    }

    func testWrongReceiptFailsClosedWithoutWaitingForConcurrentReservationCommit()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let authorizationMayReturn = DispatchSemaphore(value: 0)
        let reservationObserved = DispatchSemaphore(value: 0)
        let releaseReservation = DispatchSemaphore(value: 0)
        let wrongReceiptWaiting = DispatchSemaphore(value: 0)
        let persistence = InMemoryHostApprovalPersistence(
            reservationCheckpoint: { callCount in
                guard callCount == 2 else { return }
                authorizationMayReturn.signal()
                reservationObserved.signal()
                releaseReservation.wait()
            }
        )
        let receipts = LockedRecorder<RuntimeHostApprovalReservationReceipt>()
        let rejectedExecutions = LockedRecorder<String>()
        let approvalFinished = LockedRecorder<Bool>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            reservationReceiptConsumeWaitingCheckpoint: {
                wrongReceiptWaiting.signal()
            }
        )
        let firstOperationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "concurrent-receipt-source",
            authorizeAndClaimExecution: { reservation in
                let receipt = try reservation()
                receipts.append(receipt)
                return receipt
            }
        ))
        try await coordinator.approve(operationID: firstOperationID)

        let rejectedOperationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "concurrent-wrong-receipt",
            authorizeAndClaimExecution: { reservation in
                Task.detached {
                    _ = try? reservation()
                }
                await waitForSemaphore(authorizationMayReturn)
                return receipts.values[0]
            },
            execute: {
                rejectedExecutions.append("execute")
                return .success
            }
        ))
        let approvalTask = Task {
            defer { approvalFinished.append(true) }
            try await coordinator.approve(operationID: rejectedOperationID)
        }

        XCTAssertEqual(reservationObserved.wait(timeout: .now() + 1), .success)
        XCTAssertEqual(wrongReceiptWaiting.wait(timeout: .now() + 1), .success)
        try await waitForCount(1, recorder: approvalFinished)
        do {
            try await approvalTask.value
            XCTFail("A wrong receipt must fail closed while persistence remains blocked")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        XCTAssertTrue(rejectedExecutions.values.isEmpty)
        releaseReservation.signal()
        try await waitForCondition {
            persistence.state(operationID: rejectedOperationID) == .reserved
        }
        XCTAssertEqual(persistence.reservationCallCount, 2)
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            [
                "requested", "dispatch_reserved", "dispatch_succeeded",
                "requested", "dispatch_reserved",
            ]
        )
        try await coordinator.recoverUnfinished()
        XCTAssertEqual(
            persistence.state(operationID: rejectedOperationID),
            .recoveredReserved
        )
    }

    func testRepeatedReservationCallbackFailsClosedBeforeExecution() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let executions = LockedRecorder<String>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "repeated-reservation",
            authorizeAndClaimExecution: { reservation in
                let receipt = try reservation()
                do {
                    _ = try reservation()
                } catch {
                    // Swallowing the second failure must not make the first receipt valid again.
                }
                return receipt
            },
            execute: {
                executions.append("execute")
                return .success
            }
        ))

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("A repeated reservation callback must fail closed")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertEqual(persistence.reservationCallCount, 1)
        XCTAssertEqual(
            persistence.state(operationID: operationID),
            .terminal(.resultSuppressed)
        )
        let repeatedReviews = await coordinator.pendingReviews()
        XCTAssertTrue(repeatedReviews.isEmpty)
    }

    func testEscapedReservationInvocationAfterConsumptionCannotReserveAgain() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let escapedReservations = LockedRecorder<RuntimeHostApprovalReservation>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "escaped-reservation",
            authorizeAndClaimExecution: { reservation in
                escapedReservations.append(reservation)
                return try reservation()
            }
        ))
        try await coordinator.approve(operationID: operationID)

        XCTAssertThrowsError(try escapedReservations.values[0]())
        XCTAssertEqual(persistence.reservationCallCount, 1)
        XCTAssertEqual(persistence.state(operationID: operationID), .terminal(.dispatchSucceeded))
    }

    func testAuthorizationThrowAfterDurableReservationUsesResultSuppressed() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let executions = LockedRecorder<String>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "authorization-throw-after-reservation",
            authorizeAndClaimExecution: { reservation in
                _ = try reservation()
                throw RuntimeHostApprovalAuthorityError.authenticationChanged
            },
            execute: {
                executions.append("execute")
                return .success
            }
        ))

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("Authority loss after reservation must suppress without execution")
        } catch {
            assertCoordinatorError(error, is: .authenticationChanged)
        }

        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved", "result_suppressed"]
        )
        XCTAssertEqual(
            persistence.state(operationID: operationID),
            .terminal(.resultSuppressed)
        )
    }

    func testEscapedReservationAfterPreCommitAuthorizationFailureCannotReserve() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let executions = LockedRecorder<String>()
        let escapedReservations = LockedRecorder<RuntimeHostApprovalReservation>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "escaped-reservation-before-commit",
            authorizeAndClaimExecution: { reservation in
                escapedReservations.append(reservation)
                throw RuntimeHostApprovalAuthorityError.authenticationChanged
            },
            execute: {
                executions.append("execute")
                return .success
            }
        ))

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("Pre-commit authority failure must reject approval")
        } catch {
            assertCoordinatorError(error, is: .authenticationChanged)
        }

        XCTAssertThrowsError(try escapedReservations.values[0]())
        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertEqual(persistence.reservationCallCount, 0)
        XCTAssertEqual(
            persistence.state(operationID: operationID),
            .terminal(.authenticationChanged)
        )
    }

    func testOutcomePublicationPreparationFailureSuppressesWithoutPublication() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let publications = LockedRecorder<String>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "publication-preparation-failure",
            prepareOutcomePublication: { _ in
                throw HostApprovalTestError.injectedPersistenceFailure
            }
        ))

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("Publication preparation failure must fail closed")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        XCTAssertTrue(publications.values.isEmpty)
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved", "result_suppressed"]
        )
        XCTAssertEqual(
            persistence.state(operationID: operationID),
            .terminal(.resultSuppressed)
        )
    }

    func testPublicationDelayCrossingEitherDeadlineSuppressesResult() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let publications = LockedRecorder<String>()
        let wallClock = TestDateClock(date(100))
        let wallMonotonicClock = TestMonotonicClock(100)
        let wallPersistence = InMemoryHostApprovalPersistence()
        let wallCoordinator = makeCoordinator(
            persistence: wallPersistence,
            registry: registry,
            manifest: manifest,
            approvalTTL: 10,
            now: { wallClock.now() },
            monotonicNow: { wallMonotonicClock.now() }
        )
        let wallOperationID = try await wallCoordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "wall-publication-deadline",
            prepareOutcomePublication: { _ in
                wallClock.set(date(110))
                return { terminalCommit in
                    try terminalCommit()
                    publications.append("wall")
                }
            }
        ))
        try await wallCoordinator.approve(operationID: wallOperationID)

        let rollbackWallClock = TestDateClock(date(100))
        let monotonicClock = TestMonotonicClock(100)
        let monotonicPersistence = InMemoryHostApprovalPersistence()
        let monotonicCoordinator = makeCoordinator(
            persistence: monotonicPersistence,
            registry: registry,
            manifest: manifest,
            approvalTTL: 10,
            now: { rollbackWallClock.now() },
            monotonicNow: { monotonicClock.now() }
        )
        let monotonicOperationID = try await monotonicCoordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "monotonic-publication-deadline",
            prepareOutcomePublication: { _ in
                rollbackWallClock.set(date(50))
                monotonicClock.set(110)
                return { terminalCommit in
                    try terminalCommit()
                    publications.append("monotonic")
                }
            }
        ))
        try await monotonicCoordinator.approve(operationID: monotonicOperationID)

        XCTAssertTrue(publications.values.isEmpty)
        XCTAssertEqual(
            wallPersistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved", "result_suppressed"]
        )
        XCTAssertEqual(
            monotonicPersistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved", "result_suppressed"]
        )
    }

    func testReservationSuppressionUsesReservationTimestampAfterWallRollback() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let wallClock = TestDateClock(date(100))
        let persistence = InMemoryHostApprovalPersistence()
        let executions = LockedRecorder<String>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            now: { wallClock.now() }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "reservation-wall-rollback",
            authorizeAndClaimExecution: { reservation in
                _ = try reservation()
                wallClock.set(date(90))
                throw RuntimeHostApprovalAuthorityError.authenticationChanged
            },
            execute: {
                executions.append("execute")
                return .success
            }
        ))

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("Authority loss after reservation must suppress execution")
        } catch {
            assertCoordinatorError(error, is: .authenticationChanged)
        }

        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved", "result_suppressed"]
        )
        XCTAssertEqual(persistence.auditEvents.last?.occurredAt, date(100))
    }

    func testExpiredAdapterErrorWithoutTerminalizationEntersRecoveryMode() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence(
            throwsExpiredReservationWithoutTerminalization: true
        )
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "unterminated-expired-adapter"
        ))
        let waitingOperationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "waiting-during-unterminated-expired-adapter"
        ))

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("An unproven expired result must degrade storage")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }
        XCTAssertEqual(persistence.state(operationID: operationID), .pending)

        do {
            try await coordinator.approve(operationID: waitingOperationID)
            XCTFail("Recovery mode must block an already queued approval")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }
        do {
            try await coordinator.dismiss(operationID: waitingOperationID)
            XCTFail("Recovery mode must block dismissal of an already queued approval")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        do {
            _ = try await coordinator.enqueue(try syntheticRequest(
                registry: registry,
                manifest: manifest,
                requestID: "blocked-after-unterminated-expiry"
            ))
            XCTFail("Recovery mode must block new intake")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        try await coordinator.recoverUnfinished()
        XCTAssertEqual(persistence.state(operationID: operationID), .recoveredPending)
        XCTAssertEqual(persistence.state(operationID: waitingOperationID), .recoveredPending)
    }

    func testUnprovenTerminalExpiredErrorEntersRecoveryMode() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence(
            throwsExpiredTerminalWithoutTerminalization: true
        )
        let publications = LockedRecorder<String>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "unterminated-terminal-expiry",
            prepareOutcomePublication: { _ in
                { terminalCommit in
                    try terminalCommit()
                    publications.append("published")
                }
            }
        ))

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("An unproven terminal expiry must degrade storage")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        XCTAssertTrue(publications.values.isEmpty)
        XCTAssertEqual(persistence.state(operationID: operationID), .reserved)
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved"]
        )
        do {
            _ = try await coordinator.enqueue(try syntheticRequest(
                registry: registry,
                manifest: manifest,
                requestID: "blocked-after-unterminated-terminal-expiry"
            ))
            XCTFail("Recovery mode must block new intake")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }
    }

    func testAuthorizationTimeoutAndTerminalNotificationAreMonotonicAndBounded()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let monotonicClock = TestMonotonicClock(100)
        let deadline = ManualApprovalStageDeadline()
        let authorizationGate = CancellableAsyncGate()
        let notificationGate = CancellableAsyncGate()
        let authorizationStarted = LockedRecorder<Bool>()
        let authorizationCancelled = LockedRecorder<Bool>()
        let notificationStarted = LockedRecorder<Bool>()
        let notificationCancelled = LockedRecorder<Bool>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            approvalTTL: 10,
            monotonicNow: { monotonicClock.now() },
            externalStageDeadlineWait: { try await deadline.wait(delay: $0) }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "authorization-timeout",
            authorizeAndClaimExecution: { _ in
                authorizationStarted.append(true)
                do {
                    try await authorizationGate.wait()
                } catch is CancellationError {
                    authorizationCancelled.append(true)
                    throw CancellationError()
                }
                throw HostApprovalTestError.invalidPersistenceTransition
            },
            publishApprovalRequired: {
                notificationStarted.append(true)
                do {
                    try await notificationGate.wait()
                } catch is CancellationError {
                    notificationCancelled.append(true)
                } catch {
                    return false
                }
                return false
            }
        ))
        let approvalTask = Task {
            try await coordinator.approve(operationID: operationID)
        }

        try await waitForCount(1, recorder: authorizationStarted)
        try await waitForCondition { deadline.activeCount == 1 }
        monotonicClock.set(110)
        XCTAssertTrue(deadline.fireNext())

        try await waitForCount(1, recorder: notificationStarted)
        try await waitForCondition { deadline.activeCount == 1 }
        monotonicClock.set(120)
        XCTAssertTrue(deadline.fireNext())
        do {
            try await approvalTask.value
            XCTFail("An authorization stage that reaches its deadline must expire")
        } catch {
            assertCoordinatorError(error, is: .reviewNotFound)
        }

        try await waitForCount(1, recorder: authorizationCancelled)
        try await waitForCount(1, recorder: notificationCancelled)
        try await waitForCondition { deadline.activeCount == 0 }
        XCTAssertEqual(persistence.reservationCallCount, 0)
        XCTAssertEqual(persistence.state(operationID: operationID), .terminal(.expired))
        XCTAssertEqual(persistence.auditEvents.map(\.event), ["requested", "expired"])
        let pendingReviews = await coordinator.pendingReviews()
        XCTAssertTrue(pendingReviews.isEmpty)
    }

    func testAuthorizationTimeoutDoesNotWaitForBlockedReservationPersistence()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let blocker = CancellationIgnoringSynchronousGate()
        defer { blocker.release() }
        let terminalAttempts = LockedRecorder<RuntimeHostApprovalPersistenceEventKind>()
        let persistence = InMemoryHostApprovalPersistence(
            reservationOperationCheckpoint: { blocker.block() },
            terminalOperationCheckpoint: { terminalAttempts.append($0) }
        )
        let monotonicClock = TestMonotonicClock(100)
        let deadline = ManualApprovalStageDeadline()
        let authorizationReturned = LockedRecorder<Bool>()
        let approvalFinished = LockedRecorder<Bool>()
        let executions = LockedRecorder<Bool>()
        let publications = LockedRecorder<Bool>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            approvalTTL: 10,
            monotonicNow: { monotonicClock.now() },
            externalStageDeadlineWait: { try await deadline.wait(delay: $0) }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "blocked-reservation-timeout",
            authorizeAndClaimExecution: { reservation in
                defer { authorizationReturned.append(true) }
                return try reservation()
            },
            execute: {
                executions.append(true)
                return .success
            },
            prepareOutcomePublication: { _ in
                { terminalCommit in
                    try terminalCommit()
                    publications.append(true)
                }
            }
        ))
        let approvalTask = Task {
            defer { approvalFinished.append(true) }
            try await coordinator.approve(operationID: operationID)
        }

        XCTAssertTrue(blocker.waitUntilBlocked())
        try await waitForCondition { deadline.activeCount == 1 }
        monotonicClock.set(110)
        XCTAssertTrue(deadline.fireNext())
        try await waitForCount(1, recorder: approvalFinished)
        do {
            try await approvalTask.value
            XCTFail("Unknown reservation persistence must fail closed")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        XCTAssertEqual(persistence.state(operationID: operationID), .pending)
        XCTAssertEqual(persistence.auditEvents.map(\.event), ["requested"])
        XCTAssertTrue(terminalAttempts.values.isEmpty)
        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertTrue(publications.values.isEmpty)
        await assertCoordinatorRejectsNewIntake(
            coordinator,
            registry: registry,
            manifest: manifest,
            requestID: "blocked-reservation-timeout-poisoned"
        )

        blocker.release()
        try await waitForCount(1, recorder: authorizationReturned)
        try await waitForCondition {
            persistence.state(operationID: operationID) == .reserved
        }
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved"]
        )
        XCTAssertTrue(terminalAttempts.values.isEmpty)
        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertTrue(publications.values.isEmpty)

        try await coordinator.recoverUnfinished()
        XCTAssertEqual(persistence.state(operationID: operationID), .recoveredReserved)
        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertTrue(publications.values.isEmpty)
    }

    func testApprovalCancellationDoesNotWaitForBlockedReservationPersistence()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let blocker = CancellationIgnoringSynchronousGate()
        defer { blocker.release() }
        let terminalAttempts = LockedRecorder<RuntimeHostApprovalPersistenceEventKind>()
        let persistence = InMemoryHostApprovalPersistence(
            reservationOperationCheckpoint: { blocker.block() },
            terminalOperationCheckpoint: { terminalAttempts.append($0) }
        )
        let deadline = ManualApprovalStageDeadline()
        let authorizationReturned = LockedRecorder<Bool>()
        let approvalFinished = LockedRecorder<Bool>()
        let executions = LockedRecorder<Bool>()
        let publications = LockedRecorder<Bool>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            externalStageDeadlineWait: { try await deadline.wait(delay: $0) }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "blocked-reservation-cancellation",
            authorizeAndClaimExecution: { reservation in
                defer { authorizationReturned.append(true) }
                return try reservation()
            },
            execute: {
                executions.append(true)
                return .success
            },
            prepareOutcomePublication: { _ in
                { terminalCommit in
                    try terminalCommit()
                    publications.append(true)
                }
            }
        ))
        let approvalTask = Task {
            defer { approvalFinished.append(true) }
            try await coordinator.approve(operationID: operationID)
        }

        XCTAssertTrue(blocker.waitUntilBlocked())
        try await waitForCondition { deadline.activeCount == 1 }
        approvalTask.cancel()
        try await waitForCount(1, recorder: approvalFinished)
        do {
            try await approvalTask.value
            XCTFail("Cancellation must return while reservation persistence is blocked")
        } catch is CancellationError {
            // Expected.
        }

        XCTAssertEqual(persistence.state(operationID: operationID), .pending)
        XCTAssertEqual(persistence.auditEvents.map(\.event), ["requested"])
        XCTAssertTrue(terminalAttempts.values.isEmpty)
        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertTrue(publications.values.isEmpty)
        await assertCoordinatorRejectsNewIntake(
            coordinator,
            registry: registry,
            manifest: manifest,
            requestID: "blocked-reservation-cancellation-poisoned"
        )

        blocker.release()
        try await waitForCount(1, recorder: authorizationReturned)
        try await waitForCondition {
            persistence.state(operationID: operationID) == .reserved
        }
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved"]
        )
        XCTAssertTrue(terminalAttempts.values.isEmpty)
        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertTrue(publications.values.isEmpty)

        try await coordinator.recoverUnfinished()
        XCTAssertEqual(persistence.state(operationID: operationID), .recoveredReserved)
        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertTrue(publications.values.isEmpty)
    }

    func testPublicationTimeoutDoesNotWaitForBlockedTerminalPersistence()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let blocker = CancellationIgnoringSynchronousGate()
        defer { blocker.release() }
        let terminalAttempts = LockedRecorder<RuntimeHostApprovalPersistenceEventKind>()
        let persistence = InMemoryHostApprovalPersistence(
            terminalOperationCheckpoint: { event in
                terminalAttempts.append(event)
                if event == .dispatchSucceeded {
                    blocker.block()
                }
            }
        )
        let monotonicClock = TestMonotonicClock(100)
        let deadline = ManualApprovalStageDeadline()
        let publicationReturned = LockedRecorder<Bool>()
        let approvalFinished = LockedRecorder<Bool>()
        let executions = LockedRecorder<Bool>()
        let publications = LockedRecorder<Bool>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            approvalTTL: 10,
            monotonicNow: { monotonicClock.now() },
            externalStageDeadlineWait: { try await deadline.wait(delay: $0) }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "blocked-terminal-timeout",
            execute: {
                executions.append(true)
                return .success
            },
            prepareOutcomePublication: { _ in
                { terminalCommit in
                    defer { publicationReturned.append(true) }
                    try terminalCommit()
                    publications.append(true)
                }
            }
        ))
        let approvalTask = Task {
            defer { approvalFinished.append(true) }
            try await coordinator.approve(operationID: operationID)
        }

        XCTAssertTrue(blocker.waitUntilBlocked())
        try await waitForCondition { deadline.activeCount == 1 }
        monotonicClock.set(110)
        XCTAssertTrue(deadline.fireNext())
        try await waitForCount(1, recorder: approvalFinished)
        do {
            try await approvalTask.value
            XCTFail("Unknown terminal persistence must fail closed")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        XCTAssertEqual(persistence.state(operationID: operationID), .reserved)
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved"]
        )
        XCTAssertEqual(terminalAttempts.values, [.dispatchSucceeded])
        XCTAssertEqual(executions.values, [true])
        XCTAssertTrue(publications.values.isEmpty)
        await assertCoordinatorRejectsNewIntake(
            coordinator,
            registry: registry,
            manifest: manifest,
            requestID: "blocked-terminal-timeout-poisoned"
        )

        blocker.release()
        try await waitForCount(1, recorder: publicationReturned)
        try await waitForCondition {
            persistence.state(operationID: operationID) == .terminal(.dispatchSucceeded)
        }
        XCTAssertEqual(terminalAttempts.values, [.dispatchSucceeded])
        XCTAssertTrue(publications.values.isEmpty)

        try await coordinator.recoverUnfinished()
        XCTAssertEqual(
            persistence.state(operationID: operationID),
            .terminal(.dispatchSucceeded)
        )
        XCTAssertEqual(terminalAttempts.values, [.dispatchSucceeded])
        XCTAssertTrue(publications.values.isEmpty)
    }

    func testApprovalCancellationDoesNotWaitForBlockedTerminalPersistence()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let blocker = CancellationIgnoringSynchronousGate()
        defer { blocker.release() }
        let terminalAttempts = LockedRecorder<RuntimeHostApprovalPersistenceEventKind>()
        let persistence = InMemoryHostApprovalPersistence(
            terminalOperationCheckpoint: { event in
                terminalAttempts.append(event)
                if event == .dispatchSucceeded {
                    blocker.block()
                }
            }
        )
        let deadline = ManualApprovalStageDeadline()
        let publicationReturned = LockedRecorder<Bool>()
        let approvalFinished = LockedRecorder<Bool>()
        let executions = LockedRecorder<Bool>()
        let publications = LockedRecorder<Bool>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            externalStageDeadlineWait: { try await deadline.wait(delay: $0) }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "blocked-terminal-cancellation",
            execute: {
                executions.append(true)
                return .success
            },
            prepareOutcomePublication: { _ in
                { terminalCommit in
                    defer { publicationReturned.append(true) }
                    try terminalCommit()
                    publications.append(true)
                }
            }
        ))
        let approvalTask = Task {
            defer { approvalFinished.append(true) }
            try await coordinator.approve(operationID: operationID)
        }

        XCTAssertTrue(blocker.waitUntilBlocked())
        try await waitForCondition { deadline.activeCount == 1 }
        approvalTask.cancel()
        try await waitForCount(1, recorder: approvalFinished)
        do {
            try await approvalTask.value
            XCTFail("Cancellation must return while terminal persistence is blocked")
        } catch is CancellationError {
            // Expected.
        }

        XCTAssertEqual(persistence.state(operationID: operationID), .reserved)
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved"]
        )
        XCTAssertEqual(terminalAttempts.values, [.dispatchSucceeded])
        XCTAssertEqual(executions.values, [true])
        XCTAssertTrue(publications.values.isEmpty)
        await assertCoordinatorRejectsNewIntake(
            coordinator,
            registry: registry,
            manifest: manifest,
            requestID: "blocked-terminal-cancellation-poisoned"
        )

        blocker.release()
        try await waitForCount(1, recorder: publicationReturned)
        try await waitForCondition {
            persistence.state(operationID: operationID) == .terminal(.dispatchSucceeded)
        }
        XCTAssertEqual(terminalAttempts.values, [.dispatchSucceeded])
        XCTAssertTrue(publications.values.isEmpty)

        try await coordinator.recoverUnfinished()
        XCTAssertEqual(
            persistence.state(operationID: operationID),
            .terminal(.dispatchSucceeded)
        )
        XCTAssertEqual(terminalAttempts.values, [.dispatchSucceeded])
        XCTAssertTrue(publications.values.isEmpty)
    }

    func testApprovalTaskCancellationSuppressesAReservedExecutionAndReleasesWaiters()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let deadline = ManualApprovalStageDeadline()
        let executionGate = CancellableAsyncGate()
        let executions = LockedRecorder<Bool>()
        let cancellations = LockedRecorder<Bool>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            externalStageDeadlineWait: { try await deadline.wait(delay: $0) }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "cancel-reserved-execution",
            execute: {
                executions.append(true)
                do {
                    try await executionGate.wait()
                } catch is CancellationError {
                    cancellations.append(true)
                } catch {
                    return .failure
                }
                return .success
            }
        ))
        let approvalTask = Task {
            try await coordinator.approve(operationID: operationID)
        }

        try await waitForCount(1, recorder: executions)
        try await waitForCondition { deadline.activeCount == 1 }
        approvalTask.cancel()
        do {
            try await approvalTask.value
            XCTFail("Cancelling approval must cancel the active execution stage")
        } catch is CancellationError {
            // Expected.
        }

        try await waitForCount(1, recorder: cancellations)
        try await waitForCondition { deadline.activeCount == 0 }
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved", "result_suppressed"]
        )
        XCTAssertEqual(
            persistence.state(operationID: operationID),
            .terminal(.resultSuppressed)
        )
        let pendingReviews = await coordinator.pendingReviews()
        XCTAssertTrue(pendingReviews.isEmpty)
    }

    func testLateAuthorizationAfterTimeoutCannotReserveOrResurrectExpiredReview()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let monotonicClock = TestMonotonicClock(100)
        let deadline = ManualApprovalStageDeadline()
        let lateGate = AsyncGate()
        let authorizationStarted = LockedRecorder<Bool>()
        let lateRejections = LockedRecorder<Bool>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            approvalTTL: 10,
            monotonicNow: { monotonicClock.now() },
            externalStageDeadlineWait: { try await deadline.wait(delay: $0) }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "late-authorization",
            authorizeAndClaimExecution: { reservation in
                authorizationStarted.append(true)
                await lateGate.wait()
                do {
                    return try reservation()
                } catch {
                    lateRejections.append(true)
                    throw error
                }
            }
        ))
        let approvalTask = Task {
            try await coordinator.approve(operationID: operationID)
        }

        try await waitForCount(1, recorder: authorizationStarted)
        try await waitForCondition { deadline.activeCount == 1 }
        monotonicClock.set(110)
        XCTAssertTrue(deadline.fireNext())
        do {
            try await approvalTask.value
            XCTFail("The expired authorization must not remain in flight")
        } catch {
            assertCoordinatorError(error, is: .reviewNotFound)
        }

        await lateGate.open()
        try await waitForCount(1, recorder: lateRejections)
        try await waitForCondition { deadline.activeCount == 0 }
        XCTAssertEqual(persistence.reservationCallCount, 0)
        XCTAssertEqual(persistence.state(operationID: operationID), .terminal(.expired))
        XCTAssertEqual(persistence.auditEvents.map(\.event), ["requested", "expired"])
        let pendingReviews = await coordinator.pendingReviews()
        XCTAssertTrue(pendingReviews.isEmpty)
    }

    func testAllExternalApprovalStagesCompleteWithinInjectedDeadlineWithoutLeaks()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let deadline = ManualApprovalStageDeadline()
        let authorizationGate = AsyncGate()
        let executionGate = AsyncGate()
        let preparationGate = AsyncGate()
        let publicationGate = AsyncGate()
        let authorizationStarted = LockedRecorder<Bool>()
        let executionStarted = LockedRecorder<Bool>()
        let preparationStarted = LockedRecorder<Bool>()
        let publicationStarted = LockedRecorder<Bool>()
        let publications = LockedRecorder<RuntimeHostApprovalExecutionOutcome>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            externalStageDeadlineWait: { try await deadline.wait(delay: $0) }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "in-time-all-stages",
            authorizeAndClaimExecution: { reservation in
                authorizationStarted.append(true)
                await authorizationGate.wait()
                return try reservation()
            },
            execute: {
                executionStarted.append(true)
                await executionGate.wait()
                return .success
            },
            prepareOutcomePublication: { outcome in
                preparationStarted.append(true)
                await preparationGate.wait()
                return { terminalCommit in
                    publicationStarted.append(true)
                    await publicationGate.wait()
                    try terminalCommit()
                    publications.append(outcome)
                }
            }
        ))
        let approvalTask = Task {
            try await coordinator.approve(operationID: operationID)
        }

        try await waitForCount(1, recorder: authorizationStarted)
        try await waitForCondition { deadline.startedCount >= 1 }
        await authorizationGate.open()
        try await waitForCount(1, recorder: executionStarted)
        try await waitForCondition { deadline.startedCount >= 2 }
        await executionGate.open()
        try await waitForCount(1, recorder: preparationStarted)
        try await waitForCondition { deadline.startedCount >= 3 }
        await preparationGate.open()
        try await waitForCount(1, recorder: publicationStarted)
        try await waitForCondition { deadline.startedCount >= 4 }
        await publicationGate.open()
        try await approvalTask.value

        try await waitForCondition { deadline.activeCount == 0 }
        XCTAssertEqual(publications.values, [.success])
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved", "dispatch_succeeded"]
        )
        XCTAssertEqual(
            persistence.state(operationID: operationID),
            .terminal(.dispatchSucceeded)
        )
        let pendingReviews = await coordinator.pendingReviews()
        XCTAssertTrue(pendingReviews.isEmpty)
    }

    func testInMemoryPersistenceMirrorsSQLiteTerminalTransitionMatrix() throws {
        let persistence = InMemoryHostApprovalPersistence()
        try persistence.createPending(
            operationID: "pending-operation",
            requestBindingDigest: String(repeating: "a", count: 64),
            actionID: "test-action",
            policyRevision: String(repeating: "b", count: 64),
            requestedAt: date(100),
            expiresAt: date(160)
        )
        XCTAssertThrowsError(try persistence.recordTerminal(
            operationID: "pending-operation",
            event: .dispatchSucceeded,
            at: date(101)
        ))

        try persistence.createPending(
            operationID: "reserved-operation",
            requestBindingDigest: String(repeating: "c", count: 64),
            actionID: "test-action",
            policyRevision: String(repeating: "d", count: 64),
            requestedAt: date(100),
            expiresAt: date(160)
        )
        _ = try persistence.reserveDispatchBeforeExecution(
            operationID: "reserved-operation",
            requestBindingDigest: String(repeating: "c", count: 64),
            at: date(105)
        )
        XCTAssertThrowsError(try persistence.recordTerminal(
            operationID: "reserved-operation",
            event: .authenticationChanged,
            at: date(106)
        ))
        XCTAssertThrowsError(try persistence.recordTerminal(
            operationID: "reserved-operation",
            event: .resultSuppressed,
            at: date(104)
        ))
    }

    func testConcurrentApproveExecutesExactlyOnce() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let gate = AsyncGate()
        let executions = LockedRecorder<String>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let request = try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "concurrent-request",
            execute: {
                executions.append("execute")
                await gate.wait()
                return .success
            }
        )
        let operationID = try await coordinator.enqueue(request)

        let firstApproval = Task {
            try await coordinator.approve(operationID: operationID)
        }
        try await waitForCount(1, recorder: executions)

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("A concurrent approval must be rejected")
        } catch {
            assertCoordinatorError(error, is: .decisionInFlight)
        }

        await gate.open()
        try await firstApproval.value
        XCTAssertEqual(executions.values, ["execute"])
        XCTAssertEqual(persistence.reservationCallCount, 1)
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "dispatch_reserved", "dispatch_succeeded"]
        )
    }

    func testDuplicateRequestBindingDoesNotPoisonCoordinator() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let duplicate = try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "duplicate-request"
        )

        let firstOperationID = try await coordinator.enqueue(duplicate)
        do {
            _ = try await coordinator.enqueue(duplicate)
            XCTFail("A duplicate request binding must be rejected")
        } catch {
            assertCoordinatorError(error, is: .unavailable)
        }
        let laterOperationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "later-request"
        ))

        XCTAssertEqual(persistence.createCallCount, 3)
        XCTAssertEqual(persistence.auditEvents.map(\.event), ["requested", "requested"])
        let pendingOperationIDs = Set(await coordinator.pendingReviews().map(\.operationID))
        XCTAssertEqual(pendingOperationIDs, [firstOperationID, laterOperationID])
    }

    func testQueueAndEphemeralDisplayBoundsFailClosedBeforePersistence() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let queuePersistence = InMemoryHostApprovalPersistence()
        let queueCoordinator = RuntimeHostApprovalCoordinator(
            persistence: queuePersistence,
            permissionPolicyRegistry: registry,
            registeredActions: [RuntimeHostApprovalActionRegistration(
                actionID: manifest.actionID,
                policyRevision: manifest.revision
            )],
            pendingLimit: 1
        )
        _ = try await queueCoordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "queue-first"
        ))
        do {
            _ = try await queueCoordinator.enqueue(try syntheticRequest(
                registry: registry,
                manifest: manifest,
                requestID: "queue-second"
            ))
            XCTFail("The shared host approval queue must enforce its bound")
        } catch {
            assertCoordinatorError(error, is: .queueFull)
        }
        XCTAssertEqual(queuePersistence.createCallCount, 1)

        let invalidDisplayMutations: [(inout RuntimeHostApprovalRequest) -> Void] = [
            { (request: inout RuntimeHostApprovalRequest) in
                request.resourceDisplayName = " unsafe"
            },
            { (request: inout RuntimeHostApprovalRequest) in
                request.resourceDisplayName = "e\u{301}"
            },
            { (request: inout RuntimeHostApprovalRequest) in
                request.requestingDeviceName = "device\nname"
            },
            { (request: inout RuntimeHostApprovalRequest) in
                request.requestingDeviceName = String(repeating: "d", count: 513)
            },
            { (request: inout RuntimeHostApprovalRequest) in
                request.requestingDeviceName = "device\u{202E}name"
            },
            { (request: inout RuntimeHostApprovalRequest) in
                request.requestingDeviceName = "device\u{2066}name\u{2069}"
            },
            { (request: inout RuntimeHostApprovalRequest) in
                request.requestingDeviceName = "\u{200B}\u{2060}\u{FEFF}"
            },
            { (request: inout RuntimeHostApprovalRequest) in
                request.requestingDeviceName = "\u{2800}"
            },
            { (request: inout RuntimeHostApprovalRequest) in
                request.requestingAuthorityKeyFingerprint = "AA:BB"
            },
        ]
        for (index, mutate) in invalidDisplayMutations.enumerated() {
            let persistence = InMemoryHostApprovalPersistence()
            let coordinator = makeCoordinator(
                persistence: persistence,
                registry: registry,
                manifest: manifest
            )
            var request = try syntheticRequest(
                registry: registry,
                manifest: manifest,
                requestID: "invalid-display-\(index)"
            )
            mutate(&request)
            do {
                _ = try await coordinator.enqueue(request)
                XCTFail("Noncanonical ephemeral display metadata must be rejected")
            } catch {
                assertCoordinatorError(error, is: .unavailable)
            }
            XCTAssertEqual(persistence.createCallCount, 0)
        }
    }

    func testAuthorityDriftAndEitherClockExpiryExecuteZeroTimes() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let executions = LockedRecorder<String>()
        let driftPersistence = InMemoryHostApprovalPersistence()
        let driftCoordinator = makeCoordinator(
            persistence: driftPersistence,
            registry: registry,
            manifest: manifest
        )

        let authenticationID = try await driftCoordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "authentication-drift",
            authorizeAndClaimExecution: { _ in
                throw RuntimeHostApprovalAuthorityError.authenticationChanged
            },
            execute: {
                executions.append("authentication")
                return .success
            }
        ))
        do {
            try await driftCoordinator.approve(operationID: authenticationID)
            XCTFail("Authentication drift must reject approval")
        } catch {
            assertCoordinatorError(error, is: .authenticationChanged)
        }

        let permissionID = try await driftCoordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "permission-drift",
            authorizeAndClaimExecution: { _ in
                throw RuntimeHostApprovalAuthorityError.permissionChanged
            },
            execute: {
                executions.append("permission")
                return .success
            }
        ))
        do {
            try await driftCoordinator.approve(operationID: permissionID)
            XCTFail("Permission drift must reject approval")
        } catch {
            assertCoordinatorError(error, is: .permissionChanged)
        }

        let wallClock = TestDateClock(date(100))
        let wallMonotonicClock = TestMonotonicClock(100)
        let wallCoordinator = makeCoordinator(
            persistence: InMemoryHostApprovalPersistence(),
            registry: registry,
            manifest: manifest,
            approvalTTL: 10,
            now: { wallClock.now() },
            monotonicNow: { wallMonotonicClock.now() }
        )
        let wallExpiryID = try await wallCoordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "wall-expiry",
            execute: {
                executions.append("wall")
                return .success
            }
        ))
        wallClock.set(date(110))
        do {
            try await wallCoordinator.approve(operationID: wallExpiryID)
            XCTFail("Wall-clock expiry must prevent execution")
        } catch {
            assertCoordinatorError(error, is: .reviewNotFound)
        }

        let rollbackWallClock = TestDateClock(date(100))
        let monotonicClock = TestMonotonicClock(100)
        let monotonicCoordinator = makeCoordinator(
            persistence: InMemoryHostApprovalPersistence(),
            registry: registry,
            manifest: manifest,
            approvalTTL: 10,
            now: { rollbackWallClock.now() },
            monotonicNow: { monotonicClock.now() }
        )
        let monotonicExpiryID = try await monotonicCoordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "monotonic-expiry",
            execute: {
                executions.append("monotonic")
                return .success
            }
        ))
        rollbackWallClock.set(date(50))
        monotonicClock.set(110)
        do {
            try await monotonicCoordinator.approve(operationID: monotonicExpiryID)
            XCTFail("Monotonic expiry must win over wall-clock rollback")
        } catch {
            assertCoordinatorError(error, is: .reviewNotFound)
        }

        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertEqual(
            driftPersistence.auditEvents.map(\.event),
            ["requested", "authentication_changed", "requested", "permission_changed"]
        )
    }

    func testAuthorityFailureCrossingExpiryMapsExpiredTerminalizationToReviewNotFound()
        async throws
    {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let wallClock = TestDateClock(date(100))
        let monotonicClock = TestMonotonicClock(100)
        let persistence = InMemoryHostApprovalPersistence()
        let approvalRequiredPublications = LockedRecorder<Bool>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest,
            approvalTTL: 10,
            now: { wallClock.now() },
            monotonicNow: { monotonicClock.now() }
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "authority-expired-during-check",
            authorizeAndClaimExecution: { _ in
                wallClock.set(date(110))
                monotonicClock.set(110)
                throw RuntimeHostApprovalAuthorityError.authenticationChanged
            },
            publishApprovalRequired: {
                approvalRequiredPublications.append(true)
                return true
            }
        ))

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("Durably terminalized expiry must map to reviewNotFound")
        } catch {
            assertCoordinatorError(error, is: .reviewNotFound)
        }

        XCTAssertEqual(approvalRequiredPublications.values, [true])
        XCTAssertEqual(
            persistence.auditEvents.map(\.event),
            ["requested", "expired"]
        )
        XCTAssertEqual(persistence.state(operationID: operationID), .terminal(.expired))
    }

    func testTerminalPersistenceFailurePreventsPublicationAndDegradesStorage() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence(
            failingTerminalEvents: [.dispatchSucceeded, .resultSuppressed]
        )
        let executions = LockedRecorder<String>()
        let publications = LockedRecorder<RuntimeHostApprovalExecutionOutcome>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )
        let operationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "terminal-failure",
            execute: {
                executions.append("execute")
                return .success
            },
            prepareOutcomePublication: { outcome in
                return { terminalCommit in
                    try terminalCommit()
                    publications.append(outcome)
                }
            }
        ))

        do {
            try await coordinator.approve(operationID: operationID)
            XCTFail("An ambiguous terminal write failure must fail closed")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }

        XCTAssertEqual(executions.values, ["execute"])
        XCTAssertTrue(publications.values.isEmpty)
        XCTAssertEqual(persistence.state(operationID: operationID), .reserved)
        let pendingReviews = await coordinator.pendingReviews()
        XCTAssertTrue(pendingReviews.isEmpty)
        do {
            _ = try await coordinator.enqueue(try syntheticRequest(
                registry: registry,
                manifest: manifest,
                requestID: "blocked-after-terminal-failure"
            ))
            XCTFail("Storage-degraded mode must block new intake")
        } catch {
            assertCoordinatorError(error, is: .storageUnavailable)
        }
    }

    func testRecoveryQuarantinesUnfinishedWorkWithoutRetryingExecution() async throws {
        let manifest = syntheticManifest()
        let registry = try RuntimePermissionPolicyRegistry(manifests: [manifest])
        let persistence = InMemoryHostApprovalPersistence()
        let pendingClaim = try syntheticClaim(
            registry: registry,
            manifest: manifest,
            requestID: "recovery-pending"
        )
        let reservedClaim = try syntheticClaim(
            registry: registry,
            manifest: manifest,
            requestID: "recovery-reserved"
        )
        let pendingID = "00000000-0000-0000-0000-000000000001"
        let reservedID = "00000000-0000-0000-0000-000000000002"
        persistence.seedUnfinished(
            operationID: pendingID,
            claim: pendingClaim,
            state: .pending
        )
        persistence.seedUnfinished(
            operationID: reservedID,
            claim: reservedClaim,
            state: .reserved
        )
        let executions = LockedRecorder<String>()
        let publications = LockedRecorder<RuntimeHostApprovalExecutionOutcome>()
        let coordinator = makeCoordinator(
            persistence: persistence,
            registry: registry,
            manifest: manifest
        )

        try await coordinator.recoverUnfinished()
        let newOperationID = try await coordinator.enqueue(try syntheticRequest(
            registry: registry,
            manifest: manifest,
            requestID: "post-recovery-pending",
            execute: {
                executions.append("execute")
                return .success
            },
            prepareOutcomePublication: { outcome in
                return { terminalCommit in
                    try terminalCommit()
                    publications.append(outcome)
                }
            }
        ))
        try await coordinator.recoverUnfinished()

        XCTAssertEqual(persistence.recoveryCallCount, 1)
        XCTAssertEqual(persistence.state(operationID: pendingID), .recoveredPending)
        XCTAssertEqual(persistence.state(operationID: reservedID), .recoveredReserved)
        XCTAssertEqual(persistence.state(operationID: newOperationID), .pending)
        XCTAssertTrue(executions.values.isEmpty)
        XCTAssertTrue(publications.values.isEmpty)
    }

    private func makeCoordinator(
        persistence: InMemoryHostApprovalPersistence,
        registry: RuntimePermissionPolicyRegistry,
        manifest: RuntimePermissionPolicyManifest,
        approvalTTL: TimeInterval = 60,
        now: @escaping @Sendable () -> Date = { date(100) },
        monotonicNow: @escaping @Sendable () -> TimeInterval = { 100 },
        externalStageDeadlineWait: @escaping @Sendable (TimeInterval) async throws -> Void = {
            delay in
            try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
        },
        reservationReceiptConsumeWaitingCheckpoint: (@Sendable () -> Void)? = nil
    ) -> RuntimeHostApprovalCoordinator {
        RuntimeHostApprovalCoordinator(
            persistence: persistence,
            permissionPolicyRegistry: registry,
            registeredActions: [
                RuntimeHostApprovalActionRegistration(
                    actionID: manifest.actionID,
                    policyRevision: manifest.revision
                )
            ],
            approvalTTL: approvalTTL,
            now: now,
            monotonicNow: monotonicNow,
            externalStageDeadlineWait: externalStageDeadlineWait,
            reservationReceiptConsumeWaitingCheckpoint:
                reservationReceiptConsumeWaitingCheckpoint
        )
    }

    private func syntheticRequest(
        registry: RuntimePermissionPolicyRegistry,
        manifest: RuntimePermissionPolicyManifest,
        requestID: String,
        authorizeAndClaimExecution: @escaping @Sendable (
            @escaping RuntimeHostApprovalReservation
        ) async throws -> RuntimeHostApprovalReservationReceipt = { reservation in
            try reservation()
        },
        execute: @escaping @Sendable () async -> RuntimeHostApprovalExecutionOutcome = {
            .success
        },
        prepareOutcomePublication: @escaping @Sendable (
            RuntimeHostApprovalExecutionOutcome
        ) async throws -> RuntimeHostApprovalPublication = { _ in
            { terminalCommit in try terminalCommit() }
        },
        publishApprovalRequired: @escaping @Sendable () async -> Bool = { true }
    ) throws -> RuntimeHostApprovalRequest {
        let connectionID = UUID()
        let claim = try syntheticClaim(
            registry: registry,
            manifest: manifest,
            requestID: requestID,
            connectionID: connectionID
        )
        return RuntimeHostApprovalRequest(
            permissionClaim: claim,
            connectionID: connectionID,
            resourceDisplayName: "Synthetic resource",
            requestingDeviceName: "Synthetic device",
            requestingAuthorityKeyFingerprint: claim.authorityKeyFingerprint,
            authorizeAndClaimExecution: authorizeAndClaimExecution,
            execute: execute,
            prepareOutcomePublication: prepareOutcomePublication,
            publishApprovalRequired: publishApprovalRequired
        )
    }

    private func syntheticClaim(
        registry: RuntimePermissionPolicyRegistry,
        manifest: RuntimePermissionPolicyManifest,
        requestID: String,
        connectionID: UUID = UUID()
    ) throws -> RuntimePermissionPolicyClaim {
        try registry.claim(
            actionID: manifest.actionID,
            expectedRevision: manifest.revision,
            authority: RuntimePermissionAuthorityBinding(
                connectionID: connectionID,
                requestID: requestID,
                authenticationGeneration: 1,
                deviceID: "synthetic-device",
                publicKeyBase64: "c3ludGhldGljLXB1YmxpYy1rZXk=",
                transportBinding: String(repeating: "a", count: 64)
            ),
            resourceKind: "synthetic_resource",
            resourceValue: "synthetic-value"
        )
    }

    private func syntheticManifest() -> RuntimePermissionPolicyManifest {
        let actionID = "test_host_action_v1"
        return RuntimePermissionPolicyManifest(
            actionID: actionID,
            revision: RuntimePermissionPolicyRegistry.computedRevision(
                actionID: actionID,
                effect: .providerArtifactInstall,
                decision: .hostExplicitApproval,
                audit: .durableRedactedRequired
            ),
            effect: RuntimePermissionEffect.providerArtifactInstall.rawValue,
            decision: RuntimePermissionDecision.hostExplicitApproval.rawValue,
            audit: RuntimePermissionAuditRequirement.durableRedactedRequired.rawValue
        )
    }

    private func waitForCount<Value>(
        _ expected: Int,
        recorder: LockedRecorder<Value>
    ) async throws {
        for _ in 0..<10_000 {
            if recorder.values.count == expected {
                return
            }
            await Task.yield()
        }
        throw HostApprovalTestError.timedOut
    }

    private func waitForCondition(
        _ condition: @escaping @Sendable () -> Bool
    ) async throws {
        for _ in 0..<10_000 {
            if condition() {
                return
            }
            await Task.yield()
        }
        throw HostApprovalTestError.timedOut
    }

    private func assertCoordinatorError(
        _ error: Error,
        is expected: RuntimeHostApprovalCoordinatorError,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertEqual(
            error as? RuntimeHostApprovalCoordinatorError,
            expected,
            file: file,
            line: line
        )
    }

    private func assertCoordinatorRejectsNewIntake(
        _ coordinator: RuntimeHostApprovalCoordinator,
        registry: RuntimePermissionPolicyRegistry,
        manifest: RuntimePermissionPolicyManifest,
        requestID: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async {
        do {
            _ = try await coordinator.enqueue(try syntheticRequest(
                registry: registry,
                manifest: manifest,
                requestID: requestID
            ))
            XCTFail("Unknown persistence state must poison new intake", file: file, line: line)
        } catch {
            XCTAssertEqual(
                error as? RuntimeHostApprovalCoordinatorError,
                .storageUnavailable,
                file: file,
                line: line
            )
        }
    }
}

private enum InMemoryApprovalState: Equatable, Sendable {
    case pending
    case reserved
    case terminal(RuntimeHostApprovalPersistenceEventKind)
    case recoveredPending
    case recoveredReserved
}

private final class InMemoryHostApprovalPersistence:
    RuntimeHostApprovalPersisting,
    @unchecked Sendable
{
    private struct Row: Sendable {
        var requestBindingDigest: String
        var actionID: String
        var policyRevision: String
        var state: InMemoryApprovalState
        var updatedAt: Date
        var expiresAt: Date
    }

    private let lock = NSLock()
    private let order: LockedRecorder<String>?
    private let failingTerminalEvents: Set<RuntimeHostApprovalPersistenceEventKind>
    private let throwsExpiredReservationWithoutTerminalization: Bool
    private let throwsExpiredTerminalWithoutTerminalization: Bool
    private let reservationCheckpoint: (@Sendable (Int) -> Void)?
    private let reservationOperationCheckpoint: (@Sendable () -> Void)?
    private let terminalOperationCheckpoint: (@Sendable (
        RuntimeHostApprovalPersistenceEventKind
    ) -> Void)?
    private var rows: [String: Row] = [:]
    private var events: [RuntimeHostApprovalAuditSummary] = []
    private var storedCreateCallCount = 0
    private var storedReservationCallCount = 0
    private var storedRecoveryCallCount = 0

    init(
        order: LockedRecorder<String>? = nil,
        failingTerminalEvents: Set<RuntimeHostApprovalPersistenceEventKind> = [],
        throwsExpiredReservationWithoutTerminalization: Bool = false,
        throwsExpiredTerminalWithoutTerminalization: Bool = false,
        reservationCheckpoint: (@Sendable (Int) -> Void)? = nil,
        reservationOperationCheckpoint: (@Sendable () -> Void)? = nil,
        terminalOperationCheckpoint: (@Sendable (
            RuntimeHostApprovalPersistenceEventKind
        ) -> Void)? = nil
    ) {
        self.order = order
        self.failingTerminalEvents = failingTerminalEvents
        self.throwsExpiredReservationWithoutTerminalization =
            throwsExpiredReservationWithoutTerminalization
        self.throwsExpiredTerminalWithoutTerminalization =
            throwsExpiredTerminalWithoutTerminalization
        self.reservationCheckpoint = reservationCheckpoint
        self.reservationOperationCheckpoint = reservationOperationCheckpoint
        self.terminalOperationCheckpoint = terminalOperationCheckpoint
    }

    var auditEvents: [RuntimeHostApprovalAuditSummary] {
        lock.withLock { events }
    }

    var createCallCount: Int {
        lock.withLock { storedCreateCallCount }
    }

    var reservationCallCount: Int {
        lock.withLock { storedReservationCallCount }
    }

    var recoveryCallCount: Int {
        lock.withLock { storedRecoveryCallCount }
    }

    func state(operationID: String) -> InMemoryApprovalState? {
        lock.withLock { rows[operationID]?.state }
    }

    func seedUnfinished(
        operationID: String,
        claim: RuntimePermissionPolicyClaim,
        state: InMemoryApprovalState
    ) {
        lock.withLock {
            rows[operationID] = Row(
                requestBindingDigest: claim.requestBindingDigest,
                actionID: claim.definition.actionID,
                policyRevision: claim.definition.revision,
                state: state,
                updatedAt: date(100),
                expiresAt: date(160)
            )
        }
    }

    func createPending(
        operationID: String,
        requestBindingDigest: String,
        actionID: String,
        policyRevision: String,
        requestedAt: Date,
        expiresAt: Date
    ) throws {
        try lock.withLock {
            storedCreateCallCount += 1
            guard !rows.values.contains(where: {
                $0.requestBindingDigest == requestBindingDigest
            }) else {
                throw RuntimeHostApprovalPersistenceError.duplicateRequestBinding
            }
            rows[operationID] = Row(
                requestBindingDigest: requestBindingDigest,
                actionID: actionID,
                policyRevision: policyRevision,
                state: .pending,
                updatedAt: requestedAt,
                expiresAt: expiresAt
            )
            appendAudit(
                operationID: operationID,
                event: "requested",
                actionID: actionID,
                policyRevision: policyRevision,
                at: requestedAt
            )
        }
        order?.append("pending")
    }

    func reserveDispatchBeforeExecution(
        operationID: String,
        requestBindingDigest: String,
        at: Date
    ) throws -> RuntimeHostApprovalReservationPersistenceResult {
        reservationOperationCheckpoint?()
        let result = try lock.withLock { () -> RuntimeHostApprovalReservationPersistenceResult in
            storedReservationCallCount += 1
            reservationCheckpoint?(storedReservationCallCount)
            if throwsExpiredReservationWithoutTerminalization {
                throw RuntimeHostApprovalPersistenceError.expired
            }
            guard var row = rows[operationID],
                  row.requestBindingDigest == requestBindingDigest,
                  row.state == .pending else {
                throw HostApprovalTestError.invalidPersistenceTransition
            }
            guard at >= row.updatedAt else {
                throw HostApprovalTestError.invalidPersistenceTransition
            }
            if at >= row.expiresAt {
                row.state = .terminal(.expired)
                row.updatedAt = at
                rows[operationID] = row
                appendAudit(
                    operationID: operationID,
                    event: RuntimeHostApprovalPersistenceEventKind.expired.rawValue,
                    actionID: row.actionID,
                    policyRevision: row.policyRevision,
                    at: at
                )
                return .expiredTerminalized
            }
            row.state = .reserved
            row.updatedAt = at
            rows[operationID] = row
            appendAudit(
                operationID: operationID,
                event: "dispatch_reserved",
                actionID: row.actionID,
                policyRevision: row.policyRevision,
                at: at
            )
            return .reserved
        }
        order?.append(result == .reserved ? "reserved" : "terminal:expired")
        return result
    }

    func recordTerminal(
        operationID: String,
        event: RuntimeHostApprovalPersistenceEventKind,
        at: Date
    ) throws -> RuntimeHostApprovalTerminalPersistenceResult {
        terminalOperationCheckpoint?(event)
        let recordedEvent = try lock.withLock { () -> RuntimeHostApprovalPersistenceEventKind in
            if throwsExpiredTerminalWithoutTerminalization {
                throw RuntimeHostApprovalPersistenceError.expired
            }
            guard !failingTerminalEvents.contains(event) else {
                throw HostApprovalTestError.injectedPersistenceFailure
            }
            guard var row = rows[operationID], at >= row.updatedAt else {
                throw HostApprovalTestError.invalidPersistenceTransition
            }
            let effectiveEvent: RuntimeHostApprovalPersistenceEventKind
            switch row.state {
            case .pending:
                let allowed: Set<RuntimeHostApprovalPersistenceEventKind> = [
                    .dismissed,
                    .expired,
                    .connectionClosed,
                    .authenticationChanged,
                    .permissionChanged,
                ]
                guard allowed.contains(event) else {
                    throw HostApprovalTestError.invalidPersistenceTransition
                }
                if event == .expired {
                    guard at >= row.expiresAt else {
                        throw HostApprovalTestError.invalidPersistenceTransition
                    }
                    effectiveEvent = .expired
                } else if at >= row.expiresAt {
                    effectiveEvent = .expired
                } else {
                    effectiveEvent = event
                }
            case .reserved:
                let allowed: Set<RuntimeHostApprovalPersistenceEventKind> = [
                    .dispatchSucceeded,
                    .dispatchFailed,
                    .resultSuppressed,
                ]
                guard allowed.contains(event) else {
                    throw HostApprovalTestError.invalidPersistenceTransition
                }
                effectiveEvent = at >= row.expiresAt && event != .resultSuppressed
                    ? .resultSuppressed
                    : event
            case .terminal, .recoveredPending, .recoveredReserved:
                throw HostApprovalTestError.invalidPersistenceTransition
            }
            row.state = .terminal(effectiveEvent)
            row.updatedAt = at
            rows[operationID] = row
            appendAudit(
                operationID: operationID,
                event: effectiveEvent.rawValue,
                actionID: row.actionID,
                policyRevision: row.policyRevision,
                at: at
            )
            return effectiveEvent
        }
        order?.append("terminal:\(recordedEvent.rawValue)")
        return recordedEvent == event ? .recorded : .expiredTerminalized
    }

    func recoverUnfinishedApprovals(at: Date) throws {
        lock.withLock {
            storedRecoveryCallCount += 1
            for operationID in rows.keys {
                switch rows[operationID]?.state {
                case .pending:
                    rows[operationID]?.state = .recoveredPending
                case .reserved:
                    rows[operationID]?.state = .recoveredReserved
                default:
                    break
                }
            }
        }
    }

    func recentAuditEvents(limit: Int) throws -> [RuntimeHostApprovalAuditSummary] {
        lock.withLock { Array(events.suffix(limit).reversed()) }
    }

    private func appendAudit(
        operationID: String,
        event: String,
        actionID: String,
        policyRevision: String,
        at: Date
    ) {
        events.append(RuntimeHostApprovalAuditSummary(
            id: "audit-\(events.count + 1)",
            operationID: operationID,
            event: event,
            actionID: actionID,
            policyRevision: policyRevision,
            occurredAt: at
        ))
    }
}

private func waitForSemaphore(_ semaphore: DispatchSemaphore) async {
    await withCheckedContinuation { continuation in
        DispatchQueue.global().async {
            semaphore.wait()
            continuation.resume()
        }
    }
}

private actor AsyncGate {
    private var isOpen = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    func wait() async {
        guard !isOpen else { return }
        await withCheckedContinuation { continuation in
            waiters.append(continuation)
        }
    }

    func open() {
        isOpen = true
        let continuations = waiters
        waiters.removeAll()
        continuations.forEach { $0.resume() }
    }
}

private final class CancellationIgnoringSynchronousGate: @unchecked Sendable {
    private let lock = NSLock()
    private let started = DispatchSemaphore(value: 0)
    private let releaseSemaphore = DispatchSemaphore(value: 0)
    private var didRelease = false

    func block() {
        started.signal()
        releaseSemaphore.wait()
    }

    func waitUntilBlocked() -> Bool {
        started.wait(timeout: .now() + 1) == .success
    }

    func release() {
        let shouldSignal = lock.withLock { () -> Bool in
            guard !didRelease else { return false }
            didRelease = true
            return true
        }
        if shouldSignal {
            releaseSemaphore.signal()
        }
    }
}

private final class CancellableAsyncGate: @unchecked Sendable {
    private let lock = NSLock()
    private var isOpen = false
    private var nextWaiterID = 0
    private var cancelledBeforeInstall: Set<Int> = []
    private var waiters: [Int: CheckedContinuation<Void, any Error>] = [:]

    func wait() async throws {
        let waiterID = lock.withLock { () -> Int in
            defer { nextWaiterID += 1 }
            return nextWaiterID
        }
        try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                let disposition = lock.withLock { () -> Int in
                    if isOpen {
                        return 1
                    }
                    if cancelledBeforeInstall.remove(waiterID) != nil {
                        return 2
                    }
                    waiters[waiterID] = continuation
                    return 0
                }
                switch disposition {
                case 1:
                    continuation.resume()
                case 2:
                    continuation.resume(throwing: CancellationError())
                default:
                    break
                }
            }
        } onCancel: {
            let continuation: CheckedContinuation<Void, any Error>? = self.lock.withLock {
                if let continuation = self.waiters.removeValue(forKey: waiterID) {
                    return continuation
                }
                self.cancelledBeforeInstall.insert(waiterID)
                return nil
            }
            continuation?.resume(throwing: CancellationError())
        }
    }

    func open() {
        let continuations = lock.withLock { () -> [CheckedContinuation<Void, any Error>] in
            isOpen = true
            let continuations = Array(waiters.values)
            waiters.removeAll()
            return continuations
        }
        continuations.forEach { $0.resume() }
    }
}

private final class ManualApprovalStageDeadline: @unchecked Sendable {
    private let lock = NSLock()
    private var nextWaiterID = 0
    private var cancelledBeforeInstall: Set<Int> = []
    private var waiters: [Int: CheckedContinuation<Void, any Error>] = [:]
    private var delays: [TimeInterval] = []

    var startedCount: Int {
        lock.withLock { delays.count }
    }

    var activeCount: Int {
        lock.withLock { waiters.count }
    }

    func wait(delay: TimeInterval) async throws {
        let waiterID = lock.withLock { () -> Int in
            delays.append(delay)
            defer { nextWaiterID += 1 }
            return nextWaiterID
        }
        try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                let wasCancelled = lock.withLock { () -> Bool in
                    if cancelledBeforeInstall.remove(waiterID) != nil {
                        return true
                    }
                    waiters[waiterID] = continuation
                    return false
                }
                if wasCancelled {
                    continuation.resume(throwing: CancellationError())
                }
            }
        } onCancel: {
            let continuation: CheckedContinuation<Void, any Error>? = self.lock.withLock {
                if let continuation = self.waiters.removeValue(forKey: waiterID) {
                    return continuation
                }
                self.cancelledBeforeInstall.insert(waiterID)
                return nil
            }
            continuation?.resume(throwing: CancellationError())
        }
    }

    @discardableResult
    func fireNext() -> Bool {
        let continuation = lock.withLock { () -> CheckedContinuation<Void, any Error>? in
            guard let waiterID = waiters.keys.min() else { return nil }
            return waiters.removeValue(forKey: waiterID)
        }
        continuation?.resume()
        return continuation != nil
    }
}

private final class LockedRecorder<Value: Sendable>: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValues: [Value] = []

    var values: [Value] {
        lock.withLock { storedValues }
    }

    func append(_ value: Value) {
        lock.withLock { storedValues.append(value) }
    }
}

private final class TestDateClock: @unchecked Sendable {
    private let lock = NSLock()
    private var value: Date

    init(_ value: Date) {
        self.value = value
    }

    func now() -> Date {
        lock.withLock { value }
    }

    func set(_ value: Date) {
        lock.withLock { self.value = value }
    }
}

private final class TestMonotonicClock: @unchecked Sendable {
    private let lock = NSLock()
    private var value: TimeInterval

    init(_ value: TimeInterval) {
        self.value = value
    }

    func now() -> TimeInterval {
        lock.withLock { value }
    }

    func set(_ value: TimeInterval) {
        lock.withLock { self.value = value }
    }
}

private enum HostApprovalTestError: Error {
    case injectedPersistenceFailure
    case invalidPersistenceTransition
    case timedOut
}

private func date(_ seconds: TimeInterval) -> Date {
    Date(timeIntervalSince1970: seconds)
}
