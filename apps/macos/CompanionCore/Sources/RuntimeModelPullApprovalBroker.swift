import Foundation
import OllamaBackend

public enum RuntimeModelPullPersistenceEventKind: String, CaseIterable, Sendable {
    case dismissed
    case expired
    case connectionClosed = "connection_closed"
    case authenticationChanged = "authentication_changed"
    case permissionChanged = "permission_changed"
    case dispatchSucceeded = "dispatch_succeeded"
    case dispatchFailed = "dispatch_failed"
    case resultSuppressed = "result_suppressed"
}

public enum RuntimeModelPullBrokerPersistenceError: Error, Equatable, Sendable {
    case expired
    case duplicateRequestBinding
}

public enum RuntimeModelPullReservationPersistenceResult: Equatable, Sendable {
    case reserved
    case expiredTerminalized
}

public enum RuntimeModelPullTerminalPersistenceResult: Equatable, Sendable {
    case recorded
    case expiredTerminalized
}

public struct RuntimeModelPullAuditSummary: Identifiable, Equatable, Sendable {
    public var id: String
    public var operationID: String
    public var event: String
    public var provider: ModelProvider
    public var actionID: String
    public var policyRevision: String
    public var occurredAt: Date

    public init(
        id: String,
        operationID: String,
        event: String,
        provider: ModelProvider,
        actionID: String = RuntimePermissionPolicyRegistry.modelPullActionID,
        policyRevision: String = RuntimePermissionPolicyRegistry.modelPullRevision,
        occurredAt: Date
    ) {
        self.id = id
        self.operationID = operationID
        self.event = event
        self.provider = provider
        self.actionID = actionID
        self.policyRevision = policyRevision
        self.occurredAt = occurredAt
    }
}

public protocol RuntimeModelPullBrokerPersistence: Sendable {
    func createPending(
        operationID: String,
        requestBindingDigest: String,
        provider: ModelProvider,
        actionID: String,
        policyRevision: String,
        requestedAt: Date,
        expiresAt: Date
    ) throws

    func reserveDispatchBeforeProvider(
        operationID: String,
        requestBindingDigest: String,
        at: Date
    ) throws -> RuntimeModelPullReservationPersistenceResult

    func recordTerminal(
        operationID: String,
        event: RuntimeModelPullPersistenceEventKind,
        at: Date
    ) throws -> RuntimeModelPullTerminalPersistenceResult

    func recoverUnfinishedApprovals(at: Date) throws
    func recentAuditEvents(limit: Int) throws -> [RuntimeModelPullAuditSummary]
}

extension SQLiteRuntimeModelPullApprovalStore: RuntimeModelPullBrokerPersistence {
    public func createPending(
        operationID: String,
        requestBindingDigest: String,
        provider: ModelProvider,
        actionID: String,
        policyRevision: String,
        requestedAt: Date,
        expiresAt: Date
    ) throws {
        guard provider == .ollama else {
            throw RuntimeModelPullApprovalStoreError.invalidProvider
        }
        do {
            _ = try createRequest(
                operationID: operationID,
                requestBindingDigest: requestBindingDigest,
                provider: .ollama,
                actionID: actionID,
                policyRevision: policyRevision,
                requestedAt: requestedAt,
                expiresAt: expiresAt
            )
        } catch RuntimeModelPullApprovalStoreError.duplicateRequestBinding {
            throw RuntimeModelPullBrokerPersistenceError.duplicateRequestBinding
        }
    }

    public func recordTerminal(
        operationID: String,
        event: RuntimeModelPullPersistenceEventKind,
        at: Date
    ) throws -> RuntimeModelPullTerminalPersistenceResult {
        let storedEvent: RuntimeModelPullApprovalEvent
        switch event {
        case .dismissed:
            storedEvent = .dismissal
        case .expired:
            storedEvent = .expiry
        case .connectionClosed:
            storedEvent = .connectionClosed
        case .authenticationChanged:
            storedEvent = .authenticationChanged
        case .permissionChanged:
            storedEvent = .permissionChanged
        case .dispatchSucceeded:
            storedEvent = .success
        case .dispatchFailed:
            storedEvent = .failure
        case .resultSuppressed:
            storedEvent = .resultSuppressed
        }
        do {
            _ = try recordTerminal(operationID: operationID, event: storedEvent, at: at)
            return .recorded
        } catch RuntimeModelPullApprovalStoreError.expiredReservation {
            return .expiredTerminalized
        }
    }

    public func reserveDispatchBeforeProvider(
        operationID: String,
        requestBindingDigest: String,
        at: Date
    ) throws -> RuntimeModelPullReservationPersistenceResult {
        do {
            _ = try reserveDispatch(
                operationID: operationID,
                requestBindingDigest: requestBindingDigest,
                at: at
            )
            return .reserved
        } catch RuntimeModelPullApprovalStoreError.expiredReservation {
            return .expiredTerminalized
        }
    }

    public func recoverUnfinishedApprovals(at: Date) throws {
        _ = try recoverUnfinished(at: at)
    }

    public func recentAuditEvents(limit: Int) throws -> [RuntimeModelPullAuditSummary] {
        try recentEvents(limit: limit).map { event in
            RuntimeModelPullAuditSummary(
                id: "\(event.operationID):\(event.order)",
                operationID: event.operationID,
                event: event.event.rawValue,
                provider: .ollama,
                actionID: event.actionID,
                policyRevision: event.policyRevision,
                occurredAt: event.occurredAt
            )
        }
    }
}

public struct CompanionPendingModelPullReview: Identifiable, Equatable, Sendable {
    public var id: String { operationID }
    public var operationID: String
    public var model: String
    public var provider: ModelProvider
    public var requestingDeviceName: String
    public var requestingDeviceKeyFingerprint: String
    public var requestedAt: Date
    public var expiresAt: Date
    public var isDispatching: Bool

    public init(
        operationID: String,
        model: String,
        provider: ModelProvider,
        requestingDeviceName: String,
        requestingDeviceKeyFingerprint: String,
        requestedAt: Date,
        expiresAt: Date,
        isDispatching: Bool = false
    ) {
        self.operationID = operationID
        self.model = model
        self.provider = provider
        self.requestingDeviceName = requestingDeviceName
        self.requestingDeviceKeyFingerprint = requestingDeviceKeyFingerprint
        self.requestedAt = requestedAt
        self.expiresAt = expiresAt
        self.isDispatching = isDispatching
    }
}

public struct RuntimeModelPullWireFailure: Equatable, Sendable {
    public var code: String
    public var message: String
    public var retryable: Bool

    public init(code: String, message: String, retryable: Bool) {
        self.code = code
        self.message = message
        self.retryable = retryable
    }
}

public enum RuntimeModelPullDispatchOutcome: Equatable, Sendable {
    case success
    case failure(RuntimeModelPullWireFailure)
}

public enum RuntimeModelPullApprovalAuthorityError: Error, Sendable {
    case authenticationChanged
    case permissionChanged
}

public enum RuntimeModelPullApprovalBrokerError:
    Error,
    LocalizedError,
    Sendable,
    Equatable,
    CaseIterable
{
    case unavailable
    case queueFull
    case reviewNotFound
    case decisionInFlight
    case storageUnavailable
    case authenticationChanged
    case permissionChanged

    public var errorDescription: String? {
        switch self {
        case .unavailable:
            return "Model download approval is unavailable on this runtime host."
        case .queueFull:
            return "The runtime host model download review queue is full."
        case .reviewNotFound:
            return "This model download review is no longer available."
        case .decisionInFlight:
            return "Another model download decision is already in progress."
        case .storageUnavailable:
            return "The runtime host could not record the model download decision."
        case .authenticationChanged:
            return "The requesting device authentication changed before approval."
        case .permissionChanged:
            return "The runtime host permission policy changed before approval."
        }
    }

    public var localizationKey: String {
        errorDescription ?? "Model download approval is unavailable on this runtime host."
    }
}

public struct RuntimeModelPullReservationReceipt: Sendable {
    fileprivate let hostReceipt: RuntimeHostApprovalReservationReceipt

    fileprivate init(hostReceipt: RuntimeHostApprovalReservationReceipt) {
        self.hostReceipt = hostReceipt
    }
}

public typealias RuntimeModelPullReservation = @Sendable () throws
    -> RuntimeModelPullReservationReceipt
typealias RuntimeModelPullTerminalCommit = @Sendable () throws -> Void
typealias RuntimeModelPullOutcomePublication = @Sendable (
    @escaping RuntimeModelPullTerminalCommit
) async throws -> Void

struct RuntimeModelPullApprovalIntake: Sendable {
    public var permissionClaim: RuntimePermissionPolicyClaim
    public var connectionID: UUID
    public var model: String
    public var provider: ModelProvider
    public var requestingDeviceName: String
    // A successful durable reservation is the irreversible provider-dispatch claim.
    public var authorizeAndClaimDispatch: @Sendable (
        @escaping RuntimeModelPullReservation
    ) async throws -> RuntimeModelPullReservationReceipt
    var prepareOutcomePublication: @Sendable (
        RuntimeModelPullDispatchOutcome
    ) async throws -> RuntimeModelPullOutcomePublication
    public var publishApprovalRequired: @Sendable () async -> Bool

    init(
        permissionClaim: RuntimePermissionPolicyClaim,
        connectionID: UUID,
        model: String,
        provider: ModelProvider,
        requestingDeviceName: String,
        authorizeAndClaimDispatch: @escaping @Sendable (
            @escaping RuntimeModelPullReservation
        ) async throws -> RuntimeModelPullReservationReceipt,
        prepareOutcomePublication: @escaping @Sendable (
            RuntimeModelPullDispatchOutcome
        ) async throws -> RuntimeModelPullOutcomePublication,
        publishApprovalRequired: @escaping @Sendable () async -> Bool
    ) {
        self.permissionClaim = permissionClaim
        self.connectionID = connectionID
        self.model = model
        self.provider = provider
        self.requestingDeviceName = requestingDeviceName
        self.authorizeAndClaimDispatch = authorizeAndClaimDispatch
        self.prepareOutcomePublication = prepareOutcomePublication
        self.publishApprovalRequired = publishApprovalRequired
    }
}

private struct RuntimeModelPullHostApprovalPersistenceAdapter:
    RuntimeHostApprovalPersisting,
    Sendable
{
    let persistence: any RuntimeModelPullBrokerPersistence

    func createPending(
        operationID: String,
        requestBindingDigest: String,
        actionID: String,
        policyRevision: String,
        requestedAt: Date,
        expiresAt: Date
    ) throws {
        do {
            try persistence.createPending(
                operationID: operationID,
                requestBindingDigest: requestBindingDigest,
                provider: .ollama,
                actionID: actionID,
                policyRevision: policyRevision,
                requestedAt: requestedAt,
                expiresAt: expiresAt
            )
        } catch RuntimeModelPullBrokerPersistenceError.duplicateRequestBinding {
            throw RuntimeHostApprovalPersistenceError.duplicateRequestBinding
        }
    }

    func reserveDispatchBeforeExecution(
        operationID: String,
        requestBindingDigest: String,
        at: Date
    ) throws -> RuntimeHostApprovalReservationPersistenceResult {
        switch try persistence.reserveDispatchBeforeProvider(
                operationID: operationID,
                requestBindingDigest: requestBindingDigest,
                at: at
            ) {
        case .reserved:
            return .reserved
        case .expiredTerminalized:
            return .expiredTerminalized
        }
    }

    func recordTerminal(
        operationID: String,
        event: RuntimeHostApprovalPersistenceEventKind,
        at: Date
    ) throws -> RuntimeHostApprovalTerminalPersistenceResult {
        let modelPullEvent: RuntimeModelPullPersistenceEventKind = switch event {
        case .dismissed:
            .dismissed
        case .expired:
            .expired
        case .connectionClosed:
            .connectionClosed
        case .authenticationChanged:
            .authenticationChanged
        case .permissionChanged:
            .permissionChanged
        case .dispatchSucceeded:
            .dispatchSucceeded
        case .dispatchFailed:
            .dispatchFailed
        case .resultSuppressed:
            .resultSuppressed
        }
        switch try persistence.recordTerminal(
                operationID: operationID,
                event: modelPullEvent,
                at: at
            ) {
        case .recorded:
            return .recorded
        case .expiredTerminalized:
            return .expiredTerminalized
        }
    }

    func recoverUnfinishedApprovals(at: Date) throws {
        try persistence.recoverUnfinishedApprovals(at: at)
    }

    func recentAuditEvents(limit: Int) throws -> [RuntimeHostApprovalAuditSummary] {
        try persistence.recentAuditEvents(limit: limit).map { event in
            RuntimeHostApprovalAuditSummary(
                id: event.id,
                operationID: event.operationID,
                event: event.event,
                actionID: event.actionID,
                policyRevision: event.policyRevision,
                occurredAt: event.occurredAt
            )
        }
    }
}

public actor RuntimeModelPullApprovalBroker {
    private let dispatcher: any ModelPullDispatching
    private let permissionPolicyRegistry: RuntimePermissionPolicyRegistry
    private let coordinator: RuntimeHostApprovalCoordinator

    public init(
        dispatcher: any ModelPullDispatching,
        persistence: any RuntimeModelPullBrokerPersistence,
        permissionPolicyRegistry: RuntimePermissionPolicyRegistry = .bundled,
        approvalTTL: TimeInterval = 300,
        pendingLimit: Int = 32,
        now: @escaping @Sendable () -> Date = { Date() },
        monotonicNow: @escaping @Sendable () -> TimeInterval = {
            ProcessInfo.processInfo.systemUptime
        },
        onStateChange: (@Sendable () -> Void)? = nil
    ) {
        self.dispatcher = dispatcher
        self.permissionPolicyRegistry = permissionPolicyRegistry
        self.coordinator = RuntimeHostApprovalCoordinator(
            persistence: RuntimeModelPullHostApprovalPersistenceAdapter(
                persistence: persistence
            ),
            permissionPolicyRegistry: permissionPolicyRegistry,
            registeredActions: [
                RuntimeHostApprovalActionRegistration(
                    actionID: RuntimePermissionPolicyRegistry.modelPullActionID,
                    policyRevision: RuntimePermissionPolicyRegistry.modelPullRevision
                )
            ],
            approvalTTL: approvalTTL,
            pendingLimit: pendingLimit,
            now: now,
            monotonicNow: monotonicNow,
            onStateChange: onStateChange
        )
    }

    public func recoverUnfinished() async throws {
        do {
            try await coordinator.recoverUnfinished()
        } catch let error as RuntimeHostApprovalCoordinatorError {
            throw Self.modelPullError(for: error)
        }
    }

    @discardableResult
    func enqueue(_ intake: RuntimeModelPullApprovalIntake) async throws -> String {
        guard intake.provider == .ollama,
              permissionPolicyRegistry.validatesModelPullClaim(
                intake.permissionClaim,
                connectionID: intake.connectionID,
                model: intake.model
              ) else {
            throw RuntimeModelPullApprovalBrokerError.unavailable
        }
        let dispatcher = dispatcher
        let request = RuntimeHostApprovalRequest(
            permissionClaim: intake.permissionClaim,
            connectionID: intake.connectionID,
            resourceDisplayName: intake.model,
            requestingDeviceName: RuntimeApprovalReviewText.canonicalDeviceName(
                intake.requestingDeviceName
            ),
            requestingAuthorityKeyFingerprint: intake.permissionClaim.authorityKeyFingerprint,
            authorizeAndClaimExecution: { reservation in
                do {
                    let receipt = try await intake.authorizeAndClaimDispatch {
                        do {
                            return RuntimeModelPullReservationReceipt(
                                hostReceipt: try reservation()
                            )
                        } catch RuntimeHostApprovalPersistenceError.expired {
                            throw RuntimeModelPullBrokerPersistenceError.expired
                        }
                    }
                    return receipt.hostReceipt
                } catch RuntimeModelPullApprovalAuthorityError.authenticationChanged {
                    throw RuntimeHostApprovalAuthorityError.authenticationChanged
                } catch RuntimeModelPullApprovalAuthorityError.permissionChanged {
                    throw RuntimeHostApprovalAuthorityError.permissionChanged
                } catch RuntimeModelPullBrokerPersistenceError.expired {
                    throw RuntimeHostApprovalPersistenceError.expired
                }
            },
            execute: {
                do {
                    _ = try await dispatcher.pullModel(name: intake.model)
                    return .success
                } catch {
                    return .failure
                }
            },
            prepareOutcomePublication: { outcome in
                let modelPullOutcome: RuntimeModelPullDispatchOutcome = switch outcome {
                case .success:
                    .success
                case .failure:
                    .failure(RuntimeModelPullWireFailure(
                        code: "backend_unavailable",
                        message: "The runtime host could not download the requested model.",
                        retryable: true
                    ))
                }
                do {
                    let publication = try await intake.prepareOutcomePublication(
                        modelPullOutcome
                    )
                    return { terminalCommit in
                        do {
                            try await publication {
                                try terminalCommit()
                            }
                        } catch RuntimeModelPullApprovalAuthorityError.authenticationChanged {
                            throw RuntimeHostApprovalAuthorityError.authenticationChanged
                        } catch RuntimeModelPullApprovalAuthorityError.permissionChanged {
                            throw RuntimeHostApprovalAuthorityError.permissionChanged
                        }
                    }
                } catch RuntimeModelPullApprovalAuthorityError.authenticationChanged {
                    throw RuntimeHostApprovalAuthorityError.authenticationChanged
                } catch RuntimeModelPullApprovalAuthorityError.permissionChanged {
                    throw RuntimeHostApprovalAuthorityError.permissionChanged
                }
            },
            publishApprovalRequired: intake.publishApprovalRequired
        )
        do {
            return try await coordinator.enqueue(request)
        } catch let error as RuntimeHostApprovalCoordinatorError {
            throw Self.modelPullError(for: error)
        }
    }

    public func pendingReviews() async -> [CompanionPendingModelPullReview] {
        await coordinator.pendingReviews().map { review in
            CompanionPendingModelPullReview(
                operationID: review.operationID,
                model: review.resourceDisplayName,
                provider: .ollama,
                requestingDeviceName: review.requestingDeviceName,
                requestingDeviceKeyFingerprint: review.requestingAuthorityKeyFingerprint,
                requestedAt: review.requestedAt,
                expiresAt: review.expiresAt,
                isDispatching: review.isDispatching
            )
        }
    }

    public func recentAuditEvents(
        limit: Int = 100
    ) async throws -> [RuntimeModelPullAuditSummary] {
        do {
            return try await coordinator.recentAuditEvents(limit: limit).map { event in
                RuntimeModelPullAuditSummary(
                    id: event.id,
                    operationID: event.operationID,
                    event: event.event,
                    provider: .ollama,
                    actionID: event.actionID,
                    policyRevision: event.policyRevision,
                    occurredAt: event.occurredAt
                )
            }
        } catch let error as RuntimeHostApprovalCoordinatorError {
            throw Self.modelPullError(for: error)
        }
    }

    public func approve(operationID: String) async throws {
        do {
            try await coordinator.approve(operationID: operationID)
        } catch let error as RuntimeHostApprovalCoordinatorError {
            throw Self.modelPullError(for: error)
        }
    }

    public func dismiss(operationID: String) async throws {
        do {
            try await coordinator.dismiss(operationID: operationID)
        } catch let error as RuntimeHostApprovalCoordinatorError {
            throw Self.modelPullError(for: error)
        }
    }

    public func cancel(connectionID: UUID) async {
        await coordinator.cancel(connectionID: connectionID)
    }

    private static func modelPullError(
        for error: RuntimeHostApprovalCoordinatorError
    ) -> RuntimeModelPullApprovalBrokerError {
        switch error {
        case .unavailable:
            .unavailable
        case .queueFull:
            .queueFull
        case .reviewNotFound:
            .reviewNotFound
        case .decisionInFlight:
            .decisionInFlight
        case .storageUnavailable:
            .storageUnavailable
        case .authenticationChanged:
            .authenticationChanged
        case .permissionChanged:
            .permissionChanged
        }
    }
}
