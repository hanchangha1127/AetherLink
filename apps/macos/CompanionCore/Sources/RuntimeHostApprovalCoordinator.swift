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
    private var committed = false
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
            committed = true
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
            while commitInFlight {
                consumeWaitingCheckpoint?()
                condition.wait()
            }
            guard case .issued = state, returnedReceipt == receipt else {
                state = .violated
                return false
            }
            state = .consumed
            return true
        }
    }

    func invalidateAndWait() {
        condition.withLock {
            while commitInFlight {
                condition.wait()
            }
            switch state {
            case .available, .issued:
                state = .violated
            case .persisting:
                state = .violated
            case .consumed, .failed, .violated:
                break
            }
        }
    }

    var didCommit: Bool {
        condition.withLock { committed }
    }

    var didTerminalize: Bool {
        condition.withLock { terminalized }
    }

    var committedAt: Date? {
        condition.withLock { storedCommittedAt }
    }
}

private final class RuntimeHostApprovalTerminalPublicationGate: @unchecked Sendable {
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

    var didPersist: Bool {
        lock.withLock { persisted }
    }

    var didTerminalize: Bool {
        lock.withLock { terminalized }
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
            reservationReceipt = try await pending.request.authorizeAndClaimExecution {
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
        } catch RuntimeHostApprovalAuthorityError.authenticationChanged {
            reservationReceiptIssuer.invalidateAndWait()
            if reservationReceiptIssuer.didTerminalize {
                finish(operationID: operationID)
                _ = await pending.request.publishApprovalRequired()
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            let terminalResult: RuntimeHostApprovalTerminalPersistenceResult
            do {
                terminalResult = try persistence.recordTerminal(
                    operationID: operationID,
                    event: reservationReceiptIssuer.didCommit
                        ? .resultSuppressed
                        : .authenticationChanged,
                    at: max(
                        now(),
                        reservationReceiptIssuer.committedAt ?? requestedAt
                    )
                )
            } catch {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if terminalResult == .expiredTerminalized {
                finish(operationID: operationID)
                _ = await pending.request.publishApprovalRequired()
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            finish(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.authenticationChanged
        } catch RuntimeHostApprovalAuthorityError.permissionChanged {
            reservationReceiptIssuer.invalidateAndWait()
            if reservationReceiptIssuer.didTerminalize {
                finish(operationID: operationID)
                _ = await pending.request.publishApprovalRequired()
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            let terminalResult: RuntimeHostApprovalTerminalPersistenceResult
            do {
                terminalResult = try persistence.recordTerminal(
                    operationID: operationID,
                    event: reservationReceiptIssuer.didCommit
                        ? .resultSuppressed
                        : .permissionChanged,
                    at: max(
                        now(),
                        reservationReceiptIssuer.committedAt ?? requestedAt
                    )
                )
            } catch {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            if terminalResult == .expiredTerminalized {
                finish(operationID: operationID)
                _ = await pending.request.publishApprovalRequired()
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            finish(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.permissionChanged
        } catch RuntimeHostApprovalPersistenceError.expired {
            reservationReceiptIssuer.invalidateAndWait()
            guard reservationReceiptIssuer.didTerminalize else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            finish(operationID: operationID)
            _ = await pending.request.publishApprovalRequired()
            throw RuntimeHostApprovalCoordinatorError.reviewNotFound
        } catch {
            reservationReceiptIssuer.invalidateAndWait()
            if reservationReceiptIssuer.didTerminalize {
                finish(operationID: operationID)
                _ = await pending.request.publishApprovalRequired()
                throw RuntimeHostApprovalCoordinatorError.reviewNotFound
            }
            if reservationReceiptIssuer.didCommit {
                do {
                    _ = try persistence.recordTerminal(
                        operationID: operationID,
                        event: .resultSuppressed,
                        at: max(
                            now(),
                            reservationReceiptIssuer.committedAt ?? requestedAt
                        )
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
        let outcome = await reserved.request.execute()
        guard now() < reserved.review.expiresAt,
              monotonicNow() < reserved.monotonicDeadline else {
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
            publication = try await reserved.request.prepareOutcomePublication(outcome)
        } catch RuntimeHostApprovalAuthorityError.authenticationChanged,
                RuntimeHostApprovalAuthorityError.permissionChanged {
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
            return
        } catch {
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
            try await publication {
                try terminalPublicationGate.commit()
            }
            guard terminalPublicationGate.completePublication() else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
        } catch RuntimeHostApprovalFlowSignal.expiredTerminalized {
            guard terminalPublicationGate.didTerminalize else {
                poisonAfterPersistenceFailure(operationID: operationID)
                throw RuntimeHostApprovalCoordinatorError.storageUnavailable
            }
            finish(operationID: operationID)
            return
        } catch RuntimeHostApprovalPersistenceError.expired {
            poisonAfterPersistenceFailure(operationID: operationID)
            throw RuntimeHostApprovalCoordinatorError.storageUnavailable
        } catch RuntimeHostApprovalAuthorityError.authenticationChanged,
                RuntimeHostApprovalAuthorityError.permissionChanged {
            guard !terminalPublicationGate.didPersist else {
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
            if terminalPublicationGate.didPersist {
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
        _ = await pending.request.publishApprovalRequired()
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
        _ = await pending.request.publishApprovalRequired()
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

    private func poisonAfterPersistenceFailure(operationID: String) {
        pendingByID[operationID] = nil
        if activeExecutionOperationID == operationID {
            activeExecutionOperationID = nil
        }
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
