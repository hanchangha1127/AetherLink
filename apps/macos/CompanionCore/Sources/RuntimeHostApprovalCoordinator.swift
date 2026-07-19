import Foundation

enum RuntimeHostApprovalPersistenceEventKind: String, CaseIterable, Sendable {
    case dismissed
    case expired
    case connectionClosed = "connection_closed"
    case authenticationChanged = "authentication_changed"
    case permissionChanged = "permission_changed"
    case dispatchSucceeded = "dispatch_succeeded"
    case dispatchFailed = "dispatch_failed"
    case resultSuppressed = "result_suppressed"
}

enum RuntimeHostApprovalPersistenceError: Error, Equatable, Sendable {
    case expired
    case duplicateRequestBinding
}

private enum RuntimeHostApprovalFlowSignal: Error {
    case expiredTerminalized
}

private enum RuntimeHostApprovalExternalStageError: Error {
    case timedOut
}

enum RuntimeHostApprovalReservationPersistenceResult: Equatable, Sendable {
    case reserved
    case expiredTerminalized
}

enum RuntimeHostApprovalTerminalPersistenceResult: Equatable, Sendable {
    case recorded
    case expiredTerminalized
}

struct RuntimeHostApprovalAuditSummary: Identifiable, Equatable, Sendable {
    public var id: String
    public var operationID: String
    public var event: String
    public var actionID: String
    public var policyRevision: String
    public var occurredAt: Date

    public init(
        id: String,
        operationID: String,
        event: String,
        actionID: String,
        policyRevision: String,
        occurredAt: Date
    ) {
        self.id = id
        self.operationID = operationID
        self.event = event
        self.actionID = actionID
        self.policyRevision = policyRevision
        self.occurredAt = occurredAt
    }
}

protocol RuntimeHostApprovalPersisting: Sendable {
    func createPending(
        operationID: String,
        requestBindingDigest: String,
        actionID: String,
        policyRevision: String,
        requestedAt: Date,
        expiresAt: Date
    ) throws

    func reserveDispatchBeforeExecution(
        operationID: String,
        requestBindingDigest: String,
        at: Date
    ) throws -> RuntimeHostApprovalReservationPersistenceResult

    func recordTerminal(
        operationID: String,
        event: RuntimeHostApprovalPersistenceEventKind,
        at: Date
    ) throws -> RuntimeHostApprovalTerminalPersistenceResult

    func recoverUnfinishedApprovals(at: Date) throws
    func recentAuditEvents(limit: Int) throws -> [RuntimeHostApprovalAuditSummary]
}

struct RuntimeHostApprovalActionRegistration: Hashable, Sendable {
    public let actionID: String
    public let policyRevision: String

    public init(actionID: String, policyRevision: String) {
        self.actionID = actionID
        self.policyRevision = policyRevision
    }
}

struct RuntimeHostApprovalReview: Identifiable, Equatable, Sendable {
    public var id: String { operationID }
    public var operationID: String
    public var actionID: String
    public var policyRevision: String
    public var resourceDisplayName: String
    public var requestingDeviceName: String
    public var requestingAuthorityKeyFingerprint: String
    public var requestedAt: Date
    public var expiresAt: Date
    public var isDispatching: Bool

    public init(
        operationID: String,
        actionID: String,
        policyRevision: String,
        resourceDisplayName: String,
        requestingDeviceName: String,
        requestingAuthorityKeyFingerprint: String,
        requestedAt: Date,
        expiresAt: Date,
        isDispatching: Bool = false
    ) {
        self.operationID = operationID
        self.actionID = actionID
        self.policyRevision = policyRevision
        self.resourceDisplayName = resourceDisplayName
        self.requestingDeviceName = requestingDeviceName
        self.requestingAuthorityKeyFingerprint = requestingAuthorityKeyFingerprint
        self.requestedAt = requestedAt
        self.expiresAt = expiresAt
        self.isDispatching = isDispatching
    }
}

enum RuntimeHostApprovalExecutionOutcome: Equatable, Sendable {
    case success
    case failure
}

enum RuntimeHostApprovalAuthorityError: Error, Sendable {
    case authenticationChanged
    case permissionChanged
}

enum RuntimeHostApprovalCoordinatorError: Error, Equatable, Sendable {
    case unavailable
    case queueFull
    case reviewNotFound
    case decisionInFlight
    case storageUnavailable
    case authenticationChanged
    case permissionChanged
}

private enum RuntimeHostApprovalReceiptError: Error, Sendable {
    case invalidOrReused
}

struct RuntimeHostApprovalReservationReceipt: Equatable, Sendable {
    fileprivate let operationID: String
    fileprivate let approvalToken: UUID
}

private final class RuntimeHostApprovalReservationReceiptIssuer:
    @unchecked Sendable
{
    enum InvalidationResult {
        case persistenceInFlight
        case settled(committedAt: Date?, terminalized: Bool)
    }

    private enum State {
        case available
        case persisting
        case issued
        case consumed
        case failed
        case violated
    }

    private let condition = NSCondition()
    private let receipt: RuntimeHostApprovalReservationReceipt
    private let consumeWaitingCheckpoint: (@Sendable () -> Void)?
    private var state = State.available
    private var commitInFlight = false
    private var terminalized = false
    private var storedCommittedAt: Date?

    init(
        receipt: RuntimeHostApprovalReservationReceipt,
        consumeWaitingCheckpoint: (@Sendable () -> Void)? = nil
    ) {
        self.receipt = receipt
        self.consumeWaitingCheckpoint = consumeWaitingCheckpoint
    }

    func issue(
        at reservationAt: Date,
        after commit: () throws -> RuntimeHostApprovalReservationPersistenceResult
    ) throws -> RuntimeHostApprovalReservationReceipt {
        let mayPersist = condition.withLock { () -> Bool in
            guard case .available = state else {
                state = .violated
                return false
            }
            state = .persisting
            commitInFlight = true
            return true
        }
        guard mayPersist else {
            throw RuntimeHostApprovalReceiptError.invalidOrReused
        }
        do {
            let result = try commit()
            guard result == .reserved else {
                condition.withLock {
                    terminalized = true
                }
                throw RuntimeHostApprovalPersistenceError.expired
            }
        } catch {
            condition.withLock {
                commitInFlight = false
                if case .persisting = state {
                    state = .failed
                }
                condition.broadcast()
            }
            throw error
        }
        let mayIssue = condition.withLock { () -> Bool in
            storedCommittedAt = reservationAt
            commitInFlight = false
            defer { condition.broadcast() }
            guard case .persisting = state else { return false }
            state = .issued
            return true
        }
        guard mayIssue else {
            throw RuntimeHostApprovalReceiptError.invalidOrReused
        }
        return receipt
    }

    func consume(_ returnedReceipt: RuntimeHostApprovalReservationReceipt) -> Bool {
        condition.withLock {
            if commitInFlight {
                consumeWaitingCheckpoint?()
                state = .violated
                return false
            }
            guard case .issued = state, returnedReceipt == receipt else {
                state = .violated
                return false
            }
            state = .consumed
            return true
        }
    }

    func invalidate() -> InvalidationResult {
        condition.withLock {
            if commitInFlight {
                state = .violated
                return .persistenceInFlight
            }
            switch state {
            case .available, .issued:
                state = .violated
            case .persisting:
                state = .violated
            case .consumed, .failed, .violated:
                break
            }
            return .settled(
                committedAt: storedCommittedAt,
                terminalized: terminalized
            )
        }
    }

    var committedAt: Date? {
        condition.withLock { storedCommittedAt }
    }
}

private final class RuntimeHostApprovalTerminalPublicationGate: @unchecked Sendable {
    enum InvalidationResult {
        case persistenceInFlight
        case settled(didPersist: Bool, terminalized: Bool)
    }

    private enum State {
        case available
        case persisting
        case committed
        case completed
        case consumed
        case failed
        case violated
    }

    private let lock = NSLock()
    private let commitOperation: @Sendable () throws -> RuntimeHostApprovalTerminalPersistenceResult
    private var state = State.available
    private var persisted = false
    private var terminalized = false

    init(
        commit: @escaping @Sendable () throws -> RuntimeHostApprovalTerminalPersistenceResult
    ) {
        self.commitOperation = commit
    }

    func commit() throws {
        let mayPersist = lock.withLock { () -> Bool in
            guard case .available = state else {
                state = .violated
                return false
            }
            state = .persisting
            return true
        }
        guard mayPersist else {
            throw RuntimeHostApprovalReceiptError.invalidOrReused
        }
        do {
            guard try commitOperation() == .recorded else {
                lock.withLock {
                    terminalized = true
                }
                throw RuntimeHostApprovalFlowSignal.expiredTerminalized
            }
        } catch {
            lock.withLock {
                guard case .persisting = state else { return }
                state = .failed
            }
            throw error
        }
        let didCommit = lock.withLock { () -> Bool in
            persisted = true
            guard case .persisting = state else { return false }
            state = .committed
            return true
        }
        guard didCommit else {
            throw RuntimeHostApprovalReceiptError.invalidOrReused
        }
    }

    func completePublication() -> Bool {
        lock.withLock {
            guard case .committed = state else {
                state = .violated
                return false
            }
            state = .completed
            return true
        }
    }

    func consumeCompletion() -> Bool {
        lock.withLock {
            guard case .completed = state else {
                state = .violated
                return false
            }
            state = .consumed
            return true
        }
    }

    func invalidate() -> InvalidationResult {
        lock.withLock {
            if case .persisting = state {
                state = .violated
                return .persistenceInFlight
            }
            switch state {
            case .available, .committed, .completed:
                state = .violated
            case .persisting:
                preconditionFailure("Persistence state changed while invalidating")
            case .consumed, .failed, .violated:
                break
            }
            return .settled(didPersist: persisted, terminalized: terminalized)
        }
    }

}

private final class RuntimeHostApprovalExternalStageStartLatch: @unchecked Sendable {
    private let condition = NSCondition()
    private var isOpen = false

    func wait() {
        condition.withLock {
            while !isOpen {
                condition.wait()
            }
        }
    }

    func open() {
        condition.withLock {
            isOpen = true
            condition.broadcast()
        }
    }
}

private final class RuntimeHostApprovalExternalStageGate<Value: Sendable>:
    @unchecked Sendable
{
    private let lock = NSLock()
    private var continuation: CheckedContinuation<Value, any Error>?
    private var pendingResult: Result<Value, any Error>?
    private var operationTask: Task<Void, Never>?
    private var deadlineTask: Task<Void, Never>?
    private var isResolved = false

    func install(_ continuation: CheckedContinuation<Value, any Error>) {
        let result = lock.withLock { () -> Result<Value, any Error>? in
            if let pendingResult {
                self.pendingResult = nil
                return pendingResult
            }
            self.continuation = continuation
            return nil
        }
        if let result {
            continuation.resume(with: result)
        }
    }

    func register(
        operationTask: Task<Void, Never>,
        deadlineTask: Task<Void, Never>
    ) {
        let shouldCancel = lock.withLock { () -> Bool in
            guard !isResolved else { return true }
            self.operationTask = operationTask
            self.deadlineTask = deadlineTask
            return false
        }
        if shouldCancel {
            operationTask.cancel()
            deadlineTask.cancel()
        }
    }

    func resolve(_ result: Result<Value, any Error>) {
        let resolution = lock.withLock { () -> (
            CheckedContinuation<Value, any Error>?,
            Task<Void, Never>?,
            Task<Void, Never>?
        ) in
            guard !isResolved else { return (nil, nil, nil) }
            isResolved = true
            guard let continuation else {
                pendingResult = result
                return (nil, nil, nil)
            }
            self.continuation = nil
            let operationTask = self.operationTask
            let deadlineTask = self.deadlineTask
            self.operationTask = nil
            self.deadlineTask = nil
            return (continuation, operationTask, deadlineTask)
        }
        guard let continuation = resolution.0 else { return }
        resolution.1?.cancel()
        resolution.2?.cancel()
        continuation.resume(with: result)
    }
}

typealias RuntimeHostApprovalReservation = @Sendable () throws
    -> RuntimeHostApprovalReservationReceipt
typealias RuntimeHostApprovalTerminalCommit = @Sendable () throws -> Void
typealias RuntimeHostApprovalPublication = @Sendable (
    @escaping RuntimeHostApprovalTerminalCommit
) async throws -> Void

struct RuntimeHostApprovalRequest: Sendable {
    public var permissionClaim: RuntimePermissionPolicyClaim
    public var connectionID: UUID
    public var resourceDisplayName: String
    public var requestingDeviceName: String
    public var requestingAuthorityKeyFingerprint: String
    public var authorizeAndClaimExecution: @Sendable (
        @escaping RuntimeHostApprovalReservation
    ) async throws -> RuntimeHostApprovalReservationReceipt
    public var execute: @Sendable () async -> RuntimeHostApprovalExecutionOutcome
    public var prepareOutcomePublication: @Sendable (
        RuntimeHostApprovalExecutionOutcome
    ) async throws -> RuntimeHostApprovalPublication
    public var publishApprovalRequired: @Sendable () async -> Bool

    public init(
        permissionClaim: RuntimePermissionPolicyClaim,
        connectionID: UUID,
        resourceDisplayName: String,
        requestingDeviceName: String,
        requestingAuthorityKeyFingerprint: String,
        authorizeAndClaimExecution: @escaping @Sendable (
            @escaping RuntimeHostApprovalReservation
        ) async throws -> RuntimeHostApprovalReservationReceipt,
        execute: @escaping @Sendable () async -> RuntimeHostApprovalExecutionOutcome,
        prepareOutcomePublication: @escaping @Sendable (
            RuntimeHostApprovalExecutionOutcome
        ) async throws -> RuntimeHostApprovalPublication,
        publishApprovalRequired: @escaping @Sendable () async -> Bool
    ) {
        self.permissionClaim = permissionClaim
        self.connectionID = connectionID
        self.resourceDisplayName = resourceDisplayName
        self.requestingDeviceName = requestingDeviceName
        self.requestingAuthorityKeyFingerprint = requestingAuthorityKeyFingerprint
        self.authorizeAndClaimExecution = authorizeAndClaimExecution
        self.execute = execute
        self.prepareOutcomePublication = prepareOutcomePublication
        self.publishApprovalRequired = publishApprovalRequired
    }
}

actor RuntimeHostApprovalCoordinator {
    private enum PendingState {
        case pending
        case authorizing(UUID)
        case executing(UUID)
    }

    private struct PendingApproval {
        var review: RuntimeHostApprovalReview
        var request: RuntimeHostApprovalRequest
        var state: PendingState
        var monotonicDeadline: TimeInterval
    }

    private let persistence: any RuntimeHostApprovalPersisting
    private let permissionPolicyRegistry: RuntimePermissionPolicyRegistry
    private let registeredActions: Set<RuntimeHostApprovalActionRegistration>
    private let now: @Sendable () -> Date
    private let monotonicNow: @Sendable () -> TimeInterval
    private let externalStageDeadlineWait: @Sendable (TimeInterval) async throws -> Void
    private let approvalTTL: TimeInterval
    private let pendingLimit: Int
    private let onStateChange: (@Sendable () -> Void)?
    private let reservationReceiptConsumeWaitingCheckpoint: (@Sendable () -> Void)?
    private var pendingByID: [String: PendingApproval] = [:]
    private var activeExecutionOperationID: String?
    private var recoveryFailed: Bool

    public init(
        persistence: any RuntimeHostApprovalPersisting,
        permissionPolicyRegistry: RuntimePermissionPolicyRegistry,
        registeredActions: [RuntimeHostApprovalActionRegistration],
        approvalTTL: TimeInterval = 300,
        pendingLimit: Int = 32,
        now: @escaping @Sendable () -> Date = { Date() },
        monotonicNow: @escaping @Sendable () -> TimeInterval = {
            ProcessInfo.processInfo.systemUptime
        },
        externalStageDeadlineWait: @escaping @Sendable (TimeInterval) async throws -> Void = {
            delay in
            let nanoseconds = UInt64(
                min(max(0, delay) * 1_000_000_000, Double(UInt64.max))
            )
            try await Task.sleep(nanoseconds: nanoseconds)
        },
        onStateChange: (@Sendable () -> Void)? = nil,
        reservationReceiptConsumeWaitingCheckpoint: (@Sendable () -> Void)? = nil
    ) {
        self.persistence = persistence
        self.permissionPolicyRegistry = permissionPolicyRegistry
        self.registeredActions = Set(registeredActions)
        self.approvalTTL = max(1, min(approvalTTL, 600))
        self.pendingLimit = max(1, min(pendingLimit, 32))
        self.now = now
        self.monotonicNow = monotonicNow
        self.externalStageDeadlineWait = externalStageDeadlineWait
        self.onStateChange = onStateChange
        self.reservationReceiptConsumeWaitingCheckpoint =
            reservationReceiptConsumeWaitingCheckpoint
        do {
            try persistence.recoverUnfinishedApprovals(at: now())
            self.recoveryFailed = false
        } catch {
            self.recoveryFailed = true
        }
    }

    public func recoverUnfinished() throws {
        guard recoveryFailed else {
            return
        }
        guard pendingByID.isEmpty, activeExecutionOperationID == nil else {
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        do {
            try persistence.recoverUnfinishedApprovals(at: now())
            recoveryFailed = false
        } catch {
            recoveryFailed = true
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        onStateChange?()
    }

    @discardableResult
    public func enqueue(_ request: RuntimeHostApprovalRequest) throws -> String {
        guard !recoveryFailed else {
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        let registration = RuntimeHostApprovalActionRegistration(
            actionID: request.permissionClaim.definition.actionID,
            policyRevision: request.permissionClaim.definition.revision
        )
        guard registeredActions.contains(registration),
              permissionPolicyRegistry.validates(request.permissionClaim),
              RuntimeApprovalReviewText.isCanonicalDisplayString(request.resourceDisplayName),
              RuntimeApprovalReviewText.isCanonicalDisplayString(request.requestingDeviceName),
              RuntimeApprovalReviewText.isCanonicalKeyFingerprint(
                request.requestingAuthorityKeyFingerprint
              ),
              request.requestingAuthorityKeyFingerprint
                == request.permissionClaim.authorityKeyFingerprint else {
            throw RuntimeHostApprovalCoordinatorError.unavailable
        }
        guard pendingByID.count < pendingLimit else {
            throw RuntimeHostApprovalCoordinatorError.queueFull
        }
        let requestedAt = now()
        let expiresAt = requestedAt.addingTimeInterval(approvalTTL)
        let monotonicDeadline = monotonicNow() + approvalTTL
        let operationID = UUID().uuidString.lowercased()
        do {
            try persistence.createPending(
                operationID: operationID,
                requestBindingDigest: request.permissionClaim.requestBindingDigest,
                actionID: registration.actionID,
                policyRevision: registration.policyRevision,
                requestedAt: requestedAt,
                expiresAt: expiresAt
            )
        } catch RuntimeHostApprovalPersistenceError.duplicateRequestBinding {
            throw RuntimeHostApprovalCoordinatorError.unavailable
        } catch {
            recoveryFailed = true
            onStateChange?()
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        pendingByID[operationID] = PendingApproval(
            review: RuntimeHostApprovalReview(
                operationID: operationID,
                actionID: registration.actionID,
                policyRevision: registration.policyRevision,
                resourceDisplayName: request.resourceDisplayName,
                requestingDeviceName: request.requestingDeviceName,
                requestingAuthorityKeyFingerprint: request.requestingAuthorityKeyFingerprint,
                requestedAt: requestedAt,
                expiresAt: expiresAt
            ),
            request: request,
            state: .pending,
            monotonicDeadline: monotonicDeadline
        )
        onStateChange?()
        scheduleExpiry(operationID: operationID, monotonicDeadline: monotonicDeadline)
        return operationID
    }

    public func pendingReviews() -> [RuntimeHostApprovalReview] {
        pendingByID.values
            .map(\.review)
            .sorted { lhs, rhs in
                if lhs.requestedAt != rhs.requestedAt {
                    return lhs.requestedAt < rhs.requestedAt
                }
                return lhs.operationID < rhs.operationID
            }
    }

    public func recentAuditEvents(
        limit: Int = 100
    ) throws -> [RuntimeHostApprovalAuditSummary] {
        do {
            return try persistence.recentAuditEvents(limit: max(1, min(limit, 100)))
        } catch {
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
    }

    public func approve(operationID: String) async throws {
        guard !recoveryFailed else {
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        guard activeExecutionOperationID == nil else {
            throw RuntimeHostApprovalCoordinatorError.decisionInFlight
        }
        guard var pending = pendingByID[operationID], case .pending = pending.state else {
            throw RuntimeHostApprovalCoordinatorError.reviewNotFound
        }
        guard pending.review.expiresAt > now(),
              pending.monotonicDeadline > monotonicNow() else {
            try await expire(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.reviewNotFound
        }
        let registration = RuntimeHostApprovalActionRegistration(
            actionID: pending.request.permissionClaim.definition.actionID,
            policyRevision: pending.request.permissionClaim.definition.revision
        )
        guard registeredActions.contains(registration),
              permissionPolicyRegistry.validates(pending.request.permissionClaim) else {
            try terminalizePermissionChange(operationID: operationID, pending: pending)
            throw RuntimeHostApprovalCoordinatorError.permissionChanged
        }
        let token = UUID()
        pending.state = .authorizing(token)
        pending.review.isDispatching = true
        pendingByID[operationID] = pending
        activeExecutionOperationID = operationID
        onStateChange?()
        let requestBindingDigest = pending.request.permissionClaim.requestBindingDigest
        let approvalRequest = pending.request
        let persistence = self.persistence
        let now = self.now
        let monotonicNow = self.monotonicNow
        let requestedAt = pending.review.requestedAt
        let expiresAt = pending.review.expiresAt
        let monotonicDeadline = pending.monotonicDeadline
        let reservationReceiptIssuer = RuntimeHostApprovalReservationReceiptIssuer(
            receipt: RuntimeHostApprovalReservationReceipt(
                operationID: operationID,
                approvalToken: token
            ),
            consumeWaitingCheckpoint: reservationReceiptConsumeWaitingCheckpoint
        )

        let reservationReceipt: RuntimeHostApprovalReservationReceipt
        do {
            reservationReceipt = try await awaitExternalStage(
                until: monotonicDeadline
            ) {
                try await approvalRequest.authorizeAndClaimExecution {
                    [persistence, now, monotonicNow] in
                    let reservationAt = max(now(), requestedAt)
                    return try reservationReceiptIssuer.issue(at: reservationAt) {
                        guard now() < expiresAt,
                              monotonicNow() < monotonicDeadline else {
                            _ = try persistence.recordTerminal(
                                operationID: operationID,
                                event: .expired,
                                at: max(now(), expiresAt)
                            )
                            return .expiredTerminalized
                        }
                        return try persistence.reserveDispatchBeforeExecution(
                            operationID: operationID,
                            requestBindingDigest: requestBindingDigest,
                            at: reservationAt
                        )
                    }
                }
            }
        } catch RuntimeHostApprovalExternalStageError.timedOut {
            let invalidation = reservationReceiptIssuer.invalidate()
            guard case let .settled(committedAt, terminalized) = invalidation else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if terminalized {
                finish(operationID: operationID)
                await publishApprovalRequiredBounded(pending.request)
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            if let reservationAt = committedAt {
                try suppressReservedOperation(
                    operationID: operationID,
                    reservationAt: reservationAt
                )
            } else {
                do {
                    _ = try persistence.recordTerminal(
                        operationID: operationID,
                        event: .expired,
                        at: max(now(), expiresAt)
                    )
                } catch {
                    poisonAfterPersistenceFailure(operationID: operationID)
                    throw RuntimeHostApprovalCoordinatorError.storageUnavailable
                }
                finish(operationID: operationID)
                await publishApprovalRequiredBounded(pending.request)
            }
            throw RuntimeHostApprovalCoordinatorError.reviewNotFound
        } catch is CancellationError {
            let invalidation = reservationReceiptIssuer.invalidate()
            guard case let .settled(committedAt, terminalized) = invalidation else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw CancellationError()
            }
            if terminalized {
                finish(operationID: operationID)
                await publishApprovalRequiredBounded(pending.request)
            } else if let reservationAt = committedAt {
                try suppressReservedOperation(
                    operationID: operationID,
                    reservationAt: reservationAt
                )
            } else {
                restorePendingAfterCancelledAuthorization(
                    operationID: operationID,
                    token: token
                )
            }
            throw CancellationError()
        } catch RuntimeHostApprovalAuthorityError.authenticationChanged {
            let invalidation = reservationReceiptIssuer.invalidate()
            guard case let .settled(committedAt, terminalized) = invalidation else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if terminalized {
                finish(operationID: operationID)
                await publishApprovalRequiredBounded(pending.request)
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            let terminalResult: RuntimeHostApprovalTerminalPersistenceResult
            do {
                terminalResult = try persistence.recordTerminal(
                    operationID: operationID,
                    event: committedAt != nil
                        ? .resultSuppressed
                        : .authenticationChanged,
                    at: max(
                        now(),
                        committedAt ?? requestedAt
                    )
                )
            } catch {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if terminalResult == .expiredTerminalized {
                finish(operationID: operationID)
                await publishApprovalRequiredBounded(pending.request)
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            finish(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.authenticationChanged
        } catch RuntimeHostApprovalAuthorityError.permissionChanged {
            let invalidation = reservationReceiptIssuer.invalidate()
            guard case let .settled(committedAt, terminalized) = invalidation else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if terminalized {
                finish(operationID: operationID)
                await publishApprovalRequiredBounded(pending.request)
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            let terminalResult: RuntimeHostApprovalTerminalPersistenceResult
            do {
                terminalResult = try persistence.recordTerminal(
                    operationID: operationID,
                    event: committedAt != nil
                        ? .resultSuppressed
                        : .permissionChanged,
                    at: max(
                        now(),
                        committedAt ?? requestedAt
                    )
                )
            } catch {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if terminalResult == .expiredTerminalized {
                finish(operationID: operationID)
                await publishApprovalRequiredBounded(pending.request)
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            finish(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.permissionChanged
        } catch RuntimeHostApprovalPersistenceError.expired {
            let invalidation = reservationReceiptIssuer.invalidate()
            guard case let .settled(_, terminalized) = invalidation,
                  terminalized else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            finish(operationID: operationID)
            await publishApprovalRequiredBounded(pending.request)
            throw RuntimeHostApprovalCoordinatorError.reviewNotFound
        } catch {
            let invalidation = reservationReceiptIssuer.invalidate()
            guard case let .settled(committedAt, terminalized) = invalidation else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if terminalized {
                finish(operationID: operationID)
                await publishApprovalRequiredBounded(pending.request)
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            if let committedAt {
                do {
                    _ = try persistence.recordTerminal(
                        operationID: operationID,
                        event: .resultSuppressed,
                        at: max(now(), committedAt)
                    )
                    finish(operationID: operationID)
                } catch {
                    poisonAfterPersistenceFailure(operationID: operationID)
                }
            } else {
                poisonAfterPersistenceFailure(operationID: operationID)
            }
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        guard reservationReceiptIssuer.consume(reservationReceipt) else {
            try failClosedAfterReservationProofViolation(
                operationID: operationID,
                pending: pending,
                reservationCommittedAt: reservationReceiptIssuer.committedAt
            )
        }
        guard let reservationAt = reservationReceiptIssuer.committedAt else {
            try failClosedAfterReservationProofViolation(
                operationID: operationID,
                pending: pending,
                reservationCommittedAt: nil
            )
        }

        guard var reserved = pendingByID[operationID],
              case .authorizing(let currentToken) = reserved.state,
              currentToken == token else {
            finish(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.reviewNotFound
        }
        reserved.state = .executing(token)
        pendingByID[operationID] = reserved
        let reservedRequest = reserved.request
        let outcome: RuntimeHostApprovalExecutionOutcome
        do {
            outcome = try await awaitExternalStage(until: monotonicDeadline) {
                await reservedRequest.execute()
            }
        } catch RuntimeHostApprovalExternalStageError.timedOut {
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            return
        } catch is CancellationError {
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            throw CancellationError()
        } catch {
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        guard now() < reserved.review.expiresAt,
              monotonicNow() < reserved.monotonicDeadline else {
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            return
        }

        let terminalEvent: RuntimeHostApprovalPersistenceEventKind = switch outcome {
        case .success:
            .dispatchSucceeded
        case .failure:
            .dispatchFailed
        }
        let publication: RuntimeHostApprovalPublication
        do {
            publication = try await awaitExternalStage(until: monotonicDeadline) {
                try await reservedRequest.prepareOutcomePublication(outcome)
            }
        } catch RuntimeHostApprovalExternalStageError.timedOut {
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            return
        } catch is CancellationError {
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            throw CancellationError()
        } catch RuntimeHostApprovalAuthorityError.authenticationChanged,
                RuntimeHostApprovalAuthorityError.permissionChanged {
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            return
        } catch {
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }

        let terminalPublicationGate = RuntimeHostApprovalTerminalPublicationGate {
            [persistence, now, monotonicNow] in
            let terminalAt = max(now(), reservationAt)
            guard now() < expiresAt,
                  monotonicNow() < monotonicDeadline else {
                _ = try persistence.recordTerminal(
                    operationID: operationID,
                    event: .resultSuppressed,
                    at: terminalAt
                )
                return .expiredTerminalized
            }
            return try persistence.recordTerminal(
                operationID: operationID,
                event: terminalEvent,
                at: terminalAt
            )
        }
        do {
            try await awaitExternalStage(until: monotonicDeadline) {
                try await publication {
                    try terminalPublicationGate.commit()
                }
            }
            guard terminalPublicationGate.completePublication() else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
        } catch RuntimeHostApprovalExternalStageError.timedOut {
            let invalidation = terminalPublicationGate.invalidate()
            guard case let .settled(didPersist, terminalized) = invalidation else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if terminalized {
                finish(operationID: operationID)
                return
            }
            guard !didPersist else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            return
        } catch is CancellationError {
            let invalidation = terminalPublicationGate.invalidate()
            guard case let .settled(didPersist, terminalized) = invalidation else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw CancellationError()
            }
            if terminalized {
                finish(operationID: operationID)
                throw CancellationError()
            }
            guard !didPersist else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            try suppressReservedOperation(
                operationID: operationID,
                reservationAt: reservationAt
            )
            throw CancellationError()
        } catch RuntimeHostApprovalFlowSignal.expiredTerminalized {
            let invalidation = terminalPublicationGate.invalidate()
            guard case let .settled(_, terminalized) = invalidation,
                  terminalized else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            finish(operationID: operationID)
            return
        } catch RuntimeHostApprovalPersistenceError.expired {
            _ = terminalPublicationGate.invalidate()
            poisonAfterPersistenceFailure(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        } catch RuntimeHostApprovalAuthorityError.authenticationChanged,
                RuntimeHostApprovalAuthorityError.permissionChanged {
            let invalidation = terminalPublicationGate.invalidate()
            guard case let .settled(didPersist, _) = invalidation,
                  !didPersist else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            do {
                _ = try persistence.recordTerminal(
                    operationID: operationID,
                    event: .resultSuppressed,
                    at: max(now(), reservationAt)
                )
                finish(operationID: operationID)
                return
            } catch {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
        } catch {
            let invalidation = terminalPublicationGate.invalidate()
            guard case let .settled(didPersist, _) = invalidation else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if didPersist {
                poisonAfterPersistenceFailure(operationID: operationID)
            } else {
                do {
                    _ = try persistence.recordTerminal(
                        operationID: operationID,
                        event: .resultSuppressed,
                        at: max(now(), reservationAt)
                    )
                    finish(operationID: operationID)
                } catch {
                    poisonAfterPersistenceFailure(operationID: operationID)
                }
            }
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        guard terminalPublicationGate.consumeCompletion() else {
            poisonAfterPersistenceFailure(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        finish(operationID: operationID)
    }

    public func dismiss(operationID: String) async throws {
        guard !recoveryFailed else {
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        guard let pending = pendingByID[operationID], case .pending = pending.state else {
            throw RuntimeHostApprovalCoordinatorError.reviewNotFound
        }
        do {
            _ = try persistence.recordTerminal(
                operationID: operationID,
                event: .dismissed,
                at: auditDate(for: pending)
            )
        } catch {
            poisonAfterPersistenceFailure(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        pendingByID[operationID] = nil
        await publishApprovalRequiredBounded(pending.request)
        onStateChange?()
    }

    public func cancel(connectionID: UUID) async {
        let operationIDs = pendingByID.values.compactMap { pending -> String? in
            guard pending.request.connectionID == connectionID,
                  case .pending = pending.state else {
                return nil
            }
            return pending.review.operationID
        }
        var persistenceFailed = false
        for operationID in operationIDs {
            if let pending = pendingByID[operationID] {
                do {
                    _ = try persistence.recordTerminal(
                        operationID: operationID,
                        event: .connectionClosed,
                        at: auditDate(for: pending)
                    )
                } catch {
                    persistenceFailed = true
                }
            }
            pendingByID[operationID] = nil
        }
        if persistenceFailed {
            recoveryFailed = true
        }
        if !operationIDs.isEmpty {
            onStateChange?()
        }
    }

    private func expire(operationID: String) async throws {
        guard let pending = pendingByID[operationID], case .pending = pending.state else {
            return
        }
        guard now() >= pending.review.expiresAt ||
                monotonicNow() >= pending.monotonicDeadline else {
            return
        }
        do {
            _ = try persistence.recordTerminal(
                operationID: operationID,
                event: .expired,
                at: max(now(), pending.review.expiresAt)
            )
        } catch {
            poisonAfterPersistenceFailure(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        pendingByID[operationID] = nil
        await publishApprovalRequiredBounded(pending.request)
        onStateChange?()
    }

    private func awaitExternalStage<Value: Sendable>(
        until monotonicDeadline: TimeInterval,
        operation: @escaping @Sendable () async throws -> Value
    ) async throws -> Value {
        let gate = RuntimeHostApprovalExternalStageGate<Value>()
        let startLatch = RuntimeHostApprovalExternalStageStartLatch()
        let monotonicNow = self.monotonicNow
        let deadlineWait = externalStageDeadlineWait

        return try await withTaskCancellationHandler {
            try Task.checkCancellation()
            return try await withCheckedThrowingContinuation { continuation in
                gate.install(continuation)
                let operationTask = Task.detached {
                    startLatch.wait()
                    do {
                        try Task.checkCancellation()
                        let value = try await operation()
                        try Task.checkCancellation()
                        gate.resolve(.success(value))
                    } catch {
                        gate.resolve(.failure(error))
                    }
                }
                let deadlineTask = Task.detached {
                    startLatch.wait()
                    do {
                        while true {
                            try Task.checkCancellation()
                            let remaining = monotonicDeadline - monotonicNow()
                            guard remaining > 0 else { break }
                            try await deadlineWait(remaining)
                        }
                        try Task.checkCancellation()
                        gate.resolve(.failure(RuntimeHostApprovalExternalStageError.timedOut))
                    } catch is CancellationError {
                        return
                    } catch {
                        gate.resolve(.failure(error))
                    }
                }
                gate.register(operationTask: operationTask, deadlineTask: deadlineTask)
                startLatch.open()
            }
        } onCancel: {
            gate.resolve(.failure(CancellationError()))
        }
    }

    private func publishApprovalRequiredBounded(
        _ request: RuntimeHostApprovalRequest
    ) async {
        let deadline = monotonicNow() + approvalTTL
        _ = try? await awaitExternalStage(until: deadline) {
            await request.publishApprovalRequired()
        }
    }

    private func suppressReservedOperation(
        operationID: String,
        reservationAt: Date
    ) throws {
        do {
            _ = try persistence.recordTerminal(
                operationID: operationID,
                event: .resultSuppressed,
                at: max(now(), reservationAt)
            )
        } catch {
            poisonAfterPersistenceFailure(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        finish(operationID: operationID)
    }

    private func restorePendingAfterCancelledAuthorization(
        operationID: String,
        token: UUID
    ) {
        guard var pending = pendingByID[operationID],
              case .authorizing(let currentToken) = pending.state,
              currentToken == token else {
            finish(operationID: operationID)
            return
        }
        pending.state = .pending
        pending.review.isDispatching = false
        pendingByID[operationID] = pending
        if activeExecutionOperationID == operationID {
            activeExecutionOperationID = nil
        }
        onStateChange?()
    }

    private func scheduleExpiry(operationID: String, monotonicDeadline: TimeInterval) {
        let delay = max(0, monotonicDeadline - monotonicNow())
        Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            try? await self?.expire(operationID: operationID)
        }
    }

    private func terminalizePermissionChange(
        operationID: String,
        pending: PendingApproval
    ) throws {
        do {
            _ = try persistence.recordTerminal(
                operationID: operationID,
                event: .permissionChanged,
                at: auditDate(for: pending)
            )
        } catch {
            poisonAfterPersistenceFailure(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        }
        finish(operationID: operationID)
    }

    private func failClosedAfterReservationProofViolation(
        operationID: String,
        pending: PendingApproval,
        reservationCommittedAt: Date?
    ) throws -> Never {
        if let reservationCommittedAt {
            do {
                _ = try persistence.recordTerminal(
                    operationID: operationID,
                    event: .resultSuppressed,
                    at: max(now(), reservationCommittedAt)
                )
                finish(operationID: operationID)
            } catch {
                poisonAfterPersistenceFailure(operationID: operationID)
            }
        } else {
            poisonAfterPersistenceFailure(operationID: operationID)
        }
        throw RuntimeHostApprovalCoordinatorError.storageUnavailable
    }

    private func auditDate(for pending: PendingApproval) -> Date {
        max(now(), pending.review.requestedAt)
    }

    private func poisonAfterPersistenceFailure(operationID _: String) {
        pendingByID.removeAll(keepingCapacity: true)
        activeExecutionOperationID = nil
        recoveryFailed = true
        onStateChange?()
    }

    private func finish(operationID: String) {
        pendingByID[operationID] = nil
        if activeExecutionOperationID == operationID {
            activeExecutionOperationID = nil
        }
        onStateChange?()
    }

}
