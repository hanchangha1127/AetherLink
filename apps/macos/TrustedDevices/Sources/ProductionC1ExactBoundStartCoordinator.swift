import Foundation

struct ProductionC1ExactBoundStartHandle: Equatable, Sendable {
    let generation: UInt64
    let markerDigest: String
    fileprivate let nonce: UUID

    fileprivate init(generation: UInt64, markerDigest: String, nonce: UUID) {
        self.generation = generation
        self.markerDigest = markerDigest
        self.nonce = nonce
    }
}

struct ProductionC1ExactBoundStartLease: Equatable, Sendable {
    let generation: UInt64
    let markerDigest: String
    fileprivate let nonce: UUID

    fileprivate init(generation: UInt64, markerDigest: String, nonce: UUID) {
        self.generation = generation
        self.markerDigest = markerDigest
        self.nonce = nonce
    }
}

/// Opaque reentrancy provenance for one exact-bound start operation.
///
/// This value grants no authority. Its only purpose is to preserve the
/// operation identity when a start or abort callback crosses an unstructured
/// task boundary that does not inherit task-local values.
struct ProductionC1ExactBoundStartOperationContext: Sendable {
    fileprivate let operationID: UUID

    fileprivate init() {
        operationID = UUID()
    }
}

enum ProductionC1ExactBoundStartTerminalReason: Equatable, Sendable {
    case completed
    case cancelled
    case revoked
    case authorityAdvanced
    case expired
    case validationFailed
    case startFailed
}

struct ProductionC1ExactBoundStartTombstone: Equatable, Sendable {
    let pairAuthorityDigest: String
    let markerDigest: String
    let generation: UInt64
    let reason: ProductionC1ExactBoundStartTerminalReason
}

enum ProductionC1ExactBoundStartCoordinatorError: Error, Equatable, Sendable {
    case pairAlreadyLive
    case markerReplay
    case invalidHandle
    case invalidLease
    case fenced
    case expired
    case generationOverflow
}

actor ProductionC1ExactBoundStartCoordinator {
    static let maximumTerminalTombstonesPerPairScope = 64

    typealias StartOperation = @Sendable (
        ProductionC1ExactBoundStartOperationContext
    ) async throws -> Void

    /// Generation-scoped, idempotent cleanup instruction. The coordinator-owned
    /// operation latch invokes it again after an in-flight start returns.
    typealias AbortOperation = @Sendable (
        ProductionC1ExactBoundStartOperationContext
    ) async -> Void

    private enum OperationInvocationContext {
        @TaskLocal static var current:
            ProductionC1ExactBoundStartOperationContext?
    }

    private actor DeferredAbortCompletion {
        private var isFinishRequested = false
        private var isCompleted = false
        private var finishAction: (@Sendable () async -> Void)?
        private var completionWaiters: [CheckedContinuation<Void, Never>] = []

        func installFinishAction(
            _ action: @escaping @Sendable () async -> Void
        ) async {
            guard !isCompleted else { return }
            if isFinishRequested {
                await action()
                complete()
            } else {
                finishAction = action
            }
        }

        func finish() async {
            guard !isCompleted else { return }
            if !isFinishRequested {
                isFinishRequested = true
                if let action = finishAction {
                    finishAction = nil
                    await action()
                    complete()
                    return
                }
            }
            await withCheckedContinuation { continuation in
                completionWaiters.append(continuation)
            }
        }

        private func complete() {
            guard !isCompleted else { return }
            isCompleted = true
            let waiting = completionWaiters
            completionWaiters.removeAll()
            for continuation in waiting { continuation.resume() }
        }
    }

    private actor FirstAbortAttemptCompletion {
        private var isFinished = false
        private var waiters: [CheckedContinuation<Void, Never>] = []

        func wait() async {
            guard !isFinished else { return }
            await withCheckedContinuation { continuation in
                waiters.append(continuation)
            }
        }

        func finish() {
            guard !isFinished else { return }
            isFinished = true
            let waiting = waiters
            waiters.removeAll()
            for continuation in waiting { continuation.resume() }
        }
    }

    private typealias CoordinatedAbortOperation = @Sendable (
        _ invokingOperationID: UUID?
    ) async -> DeferredAbortCompletion?

    typealias Validator = @Sendable (
        ProductionC1ExactBoundStartRequest
    ) async throws -> ProductionC1ExactBoundStartValidation

    private enum Phase: Equatable {
        case validating
        case admitted
        case starting
        case active
    }

    private actor OperationLatch {
        private enum Phase {
            case notStarted
            case starting
            case finished
        }

        private struct DeferredAbortState {
            let completion: DeferredAbortCompletion
            let firstAttemptCompletion: FirstAbortAttemptCompletion
        }

        private let startAction: StartOperation
        private let abortAction: AbortOperation
        private let operationContext =
            ProductionC1ExactBoundStartOperationContext()
        private var phase: Phase = .notStarted
        private var abortRequested = false
        private var deferredAbortState: DeferredAbortState?
        private var startFinishedWaiters: [CheckedContinuation<Void, Never>] = []

        init(
            start: @escaping StartOperation,
            abort: @escaping AbortOperation
        ) {
            startAction = start
            abortAction = abort
        }

        func start() async throws {
            precondition(
                phase == .notStarted,
                "Production C1 start operation was reused"
            )
            guard !abortRequested else {
                await finishStart()
                return
            }
            phase = .starting
            do {
                try await OperationInvocationContext.$current.withValue(
                    operationContext
                ) {
                    try await startAction(operationContext)
                }
                await finishStart()
            } catch {
                await finishStart()
                throw error
            }
        }

        func abort(
            invokedBy invokingOperationID: UUID?
        ) async -> DeferredAbortCompletion? {
            abortRequested = true
            let phaseAtAbort = phase
            let selfOriginatedState: DeferredAbortState?
            if phaseAtAbort == .starting,
               invokingOperationID == operationContext.operationID {
                if let deferredAbortState {
                    selfOriginatedState = deferredAbortState
                } else {
                    let state = DeferredAbortState(
                        completion: DeferredAbortCompletion(),
                        firstAttemptCompletion: FirstAbortAttemptCompletion()
                    )
                    deferredAbortState = state
                    selfOriginatedState = state
                }
            } else {
                selfOriginatedState = nil
            }
            await invokeAbortAction()
            if let selfOriginatedState {
                await selfOriginatedState.firstAttemptCompletion.finish()
                return selfOriginatedState.completion
            }
            guard phaseAtAbort == .starting else { return nil }
            await waitUntilStartFinished()
            await invokeAbortAction()
            return nil
        }

        private func invokeAbortAction() async {
            await OperationInvocationContext.$current.withValue(
                operationContext
            ) {
                await abortAction(operationContext)
            }
        }

        private func waitUntilStartFinished() async {
            guard phase != .finished else { return }
            await withCheckedContinuation { continuation in
                startFinishedWaiters.append(continuation)
            }
        }

        private func finishStart() async {
            phase = .finished
            let waiters = startFinishedWaiters
            startFinishedWaiters.removeAll()
            for waiter in waiters { waiter.resume() }
            guard let deferredAbortState else { return }
            self.deferredAbortState = nil
            await deferredAbortState.firstAttemptCompletion.wait()
            let abortAction = abortAction
            let operationContext = operationContext
            await Task.detached(priority: nil) {
                await OperationInvocationContext.$current.withValue(
                    operationContext
                ) {
                    await abortAction(operationContext)
                }
            }.value
            await deferredAbortState.completion.finish()
        }
    }

    private struct LiveRecord {
        let handle: ProductionC1ExactBoundStartHandle
        let pairAuthorityDigest: String
        let expiresAtMs: UInt64
        var validation: ProductionC1ExactBoundStartValidation?
        var lease: ProductionC1ExactBoundStartLease?
        var abort: CoordinatedAbortOperation?
        var phase: Phase
    }

    private struct TerminatingReservation: Equatable, Sendable {
        let markerDigest: String
        let generation: UInt64
    }

    private struct AbortClaim: Sendable {
        let pairAuthorityDigest: String
        let reservation: TerminatingReservation
        let invokingOperationID: UUID?
        let abort: CoordinatedAbortOperation
    }

    private let validator: Validator?
    private let nowMs: @Sendable () -> UInt64
    private let publicationGate: ProductionC1AuthorityPublicationGate
    private var generation: UInt64
    private var recordsByMarker: [String: LiveRecord] = [:]
    private var liveMarkerByPairAuthority: [String: String] = [:]
    private var terminatingReservationByPairAuthority:
        [String: TerminatingReservation] = [:]
    private var tombstonesByPairAuthority:
        [String: [ProductionC1ExactBoundStartTombstone]] = [:]
    private var tombstonedMarkers: Set<String> = []

    private init(
        validator: Validator?,
        nowMs: @escaping @Sendable () -> UInt64,
        publicationGate: ProductionC1AuthorityPublicationGate,
        initialGeneration: UInt64 = 0
    ) {
        self.validator = validator
        self.nowMs = nowMs
        self.publicationGate = publicationGate
        generation = initialGeneration
    }

    static func storeOwned(
        validator: @escaping Validator,
        nowMs: @escaping @Sendable () -> UInt64,
        publicationGate: ProductionC1AuthorityPublicationGate
    ) -> ProductionC1ExactBoundStartCoordinator {
        ProductionC1ExactBoundStartCoordinator(
            validator: validator,
            nowMs: nowMs,
            publicationGate: publicationGate
        )
    }

    func acquirePublicationRead()
        async throws -> ProductionC1AuthorityPublicationReadPermit
    {
        do {
            return try await publicationGate.acquireRead()
        } catch let error as CancellationError {
            throw error
        } catch ProductionC1AuthorityPublicationGateError.capacityExceeded {
            throw ProductionC1ExactBoundStartCoordinatorError.fenced
        }
    }

    func releasePublicationRead(
        _ permit: ProductionC1AuthorityPublicationReadPermit
    ) async {
        await publicationGate.releaseRead(permit)
    }

    #if DEBUG
    func waitingPublicationWriterCountForTesting() async -> Int {
        await publicationGate.waitingWriterCountForTesting()
    }
    #endif

    func admit(
        _ request: ProductionC1ExactBoundStartRequest
    ) async throws -> ProductionC1ExactBoundStartHandle {
        guard let validator else {
            throw ProductionC1ExactBoundStartCoordinatorError.fenced
        }
        let claimed = validationClaim(from: request)
        return try await admit(
            claimed: claimed,
            validate: { try await validator(request) }
        )
    }

    func begin(
        _ handle: ProductionC1ExactBoundStartHandle,
        request: ProductionC1ExactBoundStartRequest,
        start: @escaping StartOperation,
        abort: @escaping AbortOperation
    ) async throws -> ProductionC1ExactBoundStartLease {
        guard let validator else {
            throw ProductionC1ExactBoundStartCoordinatorError.fenced
        }
        return try await begin(
            handle,
            validate: { try await validator(request) },
            start: start,
            abort: abort
        )
    }

    func cancel(
        _ handle: ProductionC1ExactBoundStartHandle,
        operationContext: ProductionC1ExactBoundStartOperationContext? = nil
    ) async throws {
        guard let record = exactRecord(for: handle) else {
            throw ProductionC1ExactBoundStartCoordinatorError.invalidHandle
        }
        await invokeAbort(terminalize(
            record,
            reason: .cancelled,
            operationContext: operationContext
        ))
    }

    func cancel(_ lease: ProductionC1ExactBoundStartLease) async throws {
        guard let record = exactRecord(for: lease) else {
            throw ProductionC1ExactBoundStartCoordinatorError.invalidLease
        }
        await invokeAbort(terminalize(record, reason: .cancelled))
    }

    func complete(_ lease: ProductionC1ExactBoundStartLease) throws {
        guard let record = exactRecord(for: lease), record.phase == .active else {
            throw ProductionC1ExactBoundStartCoordinatorError.invalidLease
        }
        terminalize(record, reason: .completed)
    }

    func complete(_ handle: ProductionC1ExactBoundStartHandle) throws {
        guard let record = exactRecord(for: handle), record.phase == .active else {
            throw ProductionC1ExactBoundStartCoordinatorError.invalidHandle
        }
        terminalize(record, reason: .completed)
    }

    func assertActive(_ lease: ProductionC1ExactBoundStartLease) async throws {
        guard let record = exactRecord(for: lease), record.phase == .active else {
            throw ProductionC1ExactBoundStartCoordinatorError.invalidLease
        }
        if nowMs() >= record.expiresAtMs {
            await invokeAbort(terminalize(record, reason: .expired))
            throw ProductionC1ExactBoundStartCoordinatorError.expired
        }
    }

    func fenceRevoked(
        pairAuthorityDigest: String,
        operationContext: ProductionC1ExactBoundStartOperationContext? = nil
    ) async {
        await invokeAbort(terminalize(
            pairAuthorityDigest: pairAuthorityDigest,
            reason: .revoked,
            operationContext: operationContext
        ))
    }

    func fenceAuthorityAdvance(
        previousPairAuthorityDigest: String,
        operationContext: ProductionC1ExactBoundStartOperationContext? = nil
    ) async {
        await invokeAbort(terminalize(
            pairAuthorityDigest: previousPairAuthorityDigest,
            reason: .authorityAdvanced,
            operationContext: operationContext
        ))
    }

    func fenceExpired(
        operationContext: ProductionC1ExactBoundStartOperationContext? = nil
    ) async {
        let instant = nowMs()
        let expired = recordsByMarker.values.filter { instant >= $0.expiresAtMs }
        let aborts = expired.compactMap {
            terminalize(
                $0,
                reason: .expired,
                operationContext: operationContext
            )
        }
        await invokeAborts(aborts)
    }

    private func admit(
        claimed: ProductionC1ExactBoundStartValidation,
        validate: @escaping @Sendable () async throws
            -> ProductionC1ExactBoundStartValidation
    ) async throws -> ProductionC1ExactBoundStartHandle {
        guard !tombstonedMarkers.contains(claimed.markerDigest) else {
            throw ProductionC1ExactBoundStartCoordinatorError.markerReplay
        }
        guard recordsByMarker[claimed.markerDigest] == nil else {
            throw ProductionC1ExactBoundStartCoordinatorError.markerReplay
        }
        guard liveMarkerByPairAuthority[claimed.pairAuthorityDigest] == nil else {
            throw ProductionC1ExactBoundStartCoordinatorError.pairAlreadyLive
        }
        guard terminatingReservationByPairAuthority[claimed.pairAuthorityDigest] == nil else {
            throw ProductionC1ExactBoundStartCoordinatorError.pairAlreadyLive
        }
        let next = generation.addingReportingOverflow(1)
        guard !next.overflow else {
            throw ProductionC1ExactBoundStartCoordinatorError.generationOverflow
        }
        generation = next.partialValue
        let handle = ProductionC1ExactBoundStartHandle(
            generation: generation,
            markerDigest: claimed.markerDigest,
            nonce: UUID()
        )
        let record = LiveRecord(
            handle: handle,
            pairAuthorityDigest: claimed.pairAuthorityDigest,
            expiresAtMs: claimed.expiresAtMs,
            validation: nil,
            lease: nil,
            abort: nil,
            phase: .validating
        )
        recordsByMarker[claimed.markerDigest] = record
        liveMarkerByPairAuthority[claimed.pairAuthorityDigest] = claimed.markerDigest

        do {
            let validated = try await validate()
            try Task.checkCancellation()
            guard validated == claimed,
                  var current = exactRecord(for: handle),
                  current.phase == .validating else {
                throw ProductionC1ExactBoundStartCoordinatorError.fenced
            }
            guard nowMs() < validated.expiresAtMs else {
                terminalize(current, reason: .expired)
                throw ProductionC1ExactBoundStartCoordinatorError.expired
            }
            current.validation = validated
            current.phase = .admitted
            recordsByMarker[claimed.markerDigest] = current
            return handle
        } catch {
            if let current = exactRecord(for: handle), current.phase == .validating {
                if Task.isCancelled {
                    terminalize(current, reason: .cancelled)
                } else {
                    releaseWithoutTombstone(current)
                }
            }
            throw error
        }
    }

    private func begin(
        _ handle: ProductionC1ExactBoundStartHandle,
        validate: @escaping @Sendable () async throws
            -> ProductionC1ExactBoundStartValidation,
        start: @escaping StartOperation,
        abort: @escaping AbortOperation
    ) async throws -> ProductionC1ExactBoundStartLease {
        guard let admitted = exactRecord(for: handle),
              admitted.phase == .admitted,
              let admittedValidation = admitted.validation else {
            throw ProductionC1ExactBoundStartCoordinatorError.invalidHandle
        }
        guard nowMs() < admitted.expiresAtMs else {
            terminalize(admitted, reason: .expired)
            throw ProductionC1ExactBoundStartCoordinatorError.expired
        }

        let validated: ProductionC1ExactBoundStartValidation
        do {
            validated = try await validate()
            try Task.checkCancellation()
        } catch {
            var abort: AbortClaim?
            if let current = exactRecord(for: handle), current.phase == .admitted {
                abort = terminalize(
                    current,
                    reason: terminalReason(forValidationError: error)
                )
            }
            await invokeAbort(abort)
            throw error
        }
        guard var starting = exactRecord(for: handle),
              starting.phase == .admitted else {
            throw ProductionC1ExactBoundStartCoordinatorError.fenced
        }
        guard validated == admittedValidation else {
            await invokeAbort(terminalize(starting, reason: .validationFailed))
            throw ProductionC1ExactBoundStartCoordinatorError.fenced
        }
        guard nowMs() < starting.expiresAtMs else {
            await invokeAbort(terminalize(starting, reason: .expired))
            throw ProductionC1ExactBoundStartCoordinatorError.expired
        }
        let lease = ProductionC1ExactBoundStartLease(
            generation: handle.generation,
            markerDigest: handle.markerDigest,
            nonce: UUID()
        )
        let operation = OperationLatch(start: start, abort: abort)
        starting.lease = lease
        starting.abort = { invokingOperationID in
            await operation.abort(invokedBy: invokingOperationID)
        }
        starting.phase = .starting
        recordsByMarker[handle.markerDigest] = starting

        do {
            try await operation.start()
            try Task.checkCancellation()
        } catch {
            var ownedAbort: AbortClaim?
            if let current = exactRecord(for: handle), current.phase == .starting {
                ownedAbort = terminalize(
                    current,
                    reason: Task.isCancelled ? .cancelled : .startFailed
                )
            }
            await invokeAbort(ownedAbort)
            throw error
        }
        guard let stillStarting = exactRecord(for: handle),
              stillStarting.phase == .starting,
              stillStarting.lease == lease else {
            throw ProductionC1ExactBoundStartCoordinatorError.fenced
        }

        let postStartValidation: ProductionC1ExactBoundStartValidation
        do {
            postStartValidation = try await validate()
            try Task.checkCancellation()
        } catch {
            var abort: AbortClaim?
            if let current = exactRecord(for: handle), current.phase == .starting {
                abort = terminalize(
                    current,
                    reason: terminalReason(forValidationError: error)
                )
            }
            await invokeAbort(abort)
            throw error
        }
        guard var current = exactRecord(for: handle),
              current.phase == .starting,
              current.lease == lease else {
            throw ProductionC1ExactBoundStartCoordinatorError.fenced
        }
        guard postStartValidation == admittedValidation else {
            await invokeAbort(terminalize(current, reason: .validationFailed))
            throw ProductionC1ExactBoundStartCoordinatorError.fenced
        }
        guard nowMs() < current.expiresAtMs else {
            await invokeAbort(terminalize(current, reason: .expired))
            throw ProductionC1ExactBoundStartCoordinatorError.expired
        }
        current.phase = .active
        recordsByMarker[handle.markerDigest] = current
        return lease
    }

    private func validationClaim(
        from request: ProductionC1ExactBoundStartRequest
    ) -> ProductionC1ExactBoundStartValidation {
        let token = request.token
        return ProductionC1ExactBoundStartValidation(
            deviceID: request.deviceID,
            pairAuthorityDigest: token.pairAuthorityDigest,
            markerDigest: token.markerDigest,
            admissionID: token.admissionID,
            bindingDigest: token.bindingDigest,
            sessionID: token.sessionID,
            effectiveNotBeforeMs: token.effectiveNotBeforeMs,
            expiresAtMs: token.expiresAtMs,
            pairLocalRevision: token.pairLocalRevision,
            ledgerRevision: token.ledgerRevision
        )
    }

    private func exactRecord(
        for handle: ProductionC1ExactBoundStartHandle
    ) -> LiveRecord? {
        guard let record = recordsByMarker[handle.markerDigest],
              record.handle == handle else { return nil }
        return record
    }

    private func exactRecord(
        for lease: ProductionC1ExactBoundStartLease
    ) -> LiveRecord? {
        guard let record = recordsByMarker[lease.markerDigest],
              record.handle.generation == lease.generation,
              record.lease == lease else { return nil }
        return record
    }

    @discardableResult
    private func terminalize(
        pairAuthorityDigest: String,
        reason: ProductionC1ExactBoundStartTerminalReason,
        operationContext: ProductionC1ExactBoundStartOperationContext? = nil
    ) -> AbortClaim? {
        guard let marker = liveMarkerByPairAuthority[pairAuthorityDigest],
              let record = recordsByMarker[marker] else { return nil }
        return terminalize(
            record,
            reason: reason,
            operationContext: operationContext
        )
    }

    private func terminalReason(
        forValidationError error: Error
    ) -> ProductionC1ExactBoundStartTerminalReason {
        if Task.isCancelled { return .cancelled }
        if error as? ProductionC1ExactBoundStartValidationError == .expired {
            return .expired
        }
        return .validationFailed
    }

    private func releaseWithoutTombstone(_ record: LiveRecord) {
        recordsByMarker.removeValue(forKey: record.handle.markerDigest)
        if liveMarkerByPairAuthority[record.pairAuthorityDigest]
            == record.handle.markerDigest {
            liveMarkerByPairAuthority.removeValue(forKey: record.pairAuthorityDigest)
        }
    }

    @discardableResult
    private func terminalize(
        _ record: LiveRecord,
        reason: ProductionC1ExactBoundStartTerminalReason,
        operationContext: ProductionC1ExactBoundStartOperationContext? = nil
    ) -> AbortClaim? {
        releaseWithoutTombstone(record)
        let tombstone = ProductionC1ExactBoundStartTombstone(
            pairAuthorityDigest: record.pairAuthorityDigest,
            markerDigest: record.handle.markerDigest,
            generation: record.handle.generation,
            reason: reason
        )
        var pairTombstones = tombstonesByPairAuthority[record.pairAuthorityDigest] ?? []
        pairTombstones.append(tombstone)
        tombstonedMarkers.insert(tombstone.markerDigest)
        var removedMarker: String?
        if pairTombstones.count > Self.maximumTerminalTombstonesPerPairScope {
            removedMarker = pairTombstones.removeFirst().markerDigest
        }
        tombstonesByPairAuthority[record.pairAuthorityDigest] = pairTombstones
        if let removedMarker,
           !tombstonesByPairAuthority.values.contains(where: { tombstones in
               tombstones.contains(where: { $0.markerDigest == removedMarker })
           }) {
            tombstonedMarkers.remove(removedMarker)
        }
        guard reason != .completed, let abort = record.abort else { return nil }
        let reservation = TerminatingReservation(
            markerDigest: record.handle.markerDigest,
            generation: record.handle.generation
        )
        terminatingReservationByPairAuthority[record.pairAuthorityDigest] = reservation
        return AbortClaim(
            pairAuthorityDigest: record.pairAuthorityDigest,
            reservation: reservation,
            invokingOperationID: (
                operationContext ?? OperationInvocationContext.current
            )?.operationID,
            abort: abort
        )
    }

    private func invokeAbort(_ claim: AbortClaim?) async {
        guard let claim else { return }
        await invokeAborts([claim])
    }

    private func invokeAborts(_ claims: [AbortClaim]) async {
        await withTaskGroup(of: Void.self) { group in
            for claim in claims {
                group.addTask {
                    let deferredCompletion = await Task.detached(priority: nil) {
                        await claim.abort(claim.invokingOperationID)
                    }.value
                    if let deferredCompletion {
                        await deferredCompletion.installFinishAction {
                            await self.finishAbort(claim)
                        }
                    } else {
                        await self.finishAbort(claim)
                    }
                }
            }
            await group.waitForAll()
        }
    }

    private func finishAbort(_ claim: AbortClaim) {
        if terminatingReservationByPairAuthority[claim.pairAuthorityDigest]
            == claim.reservation {
            terminatingReservationByPairAuthority.removeValue(
                forKey: claim.pairAuthorityDigest
            )
        }
    }

    #if DEBUG
    typealias TestingValidator = @Sendable (
        ProductionC1ExactBoundStartValidation
    ) async throws -> ProductionC1ExactBoundStartValidation

    static func makeForTesting(
        nowMs: @escaping @Sendable () -> UInt64,
        initialGeneration: UInt64 = 0
    ) -> ProductionC1ExactBoundStartCoordinator {
        ProductionC1ExactBoundStartCoordinator(
            validator: nil,
            nowMs: nowMs,
            publicationGate: ProductionC1AuthorityPublicationGate(),
            initialGeneration: initialGeneration
        )
    }

    func admitForTesting(
        _ claimed: ProductionC1ExactBoundStartValidation,
        validator: @escaping TestingValidator
    ) async throws -> ProductionC1ExactBoundStartHandle {
        try await admit(claimed: claimed) { try await validator(claimed) }
    }

    func beginForTesting(
        _ handle: ProductionC1ExactBoundStartHandle,
        claimed: ProductionC1ExactBoundStartValidation,
        validator: @escaping TestingValidator,
        start: @escaping StartOperation = { _ in },
        abort: @escaping AbortOperation = { _ in }
    ) async throws -> ProductionC1ExactBoundStartLease {
        try await begin(
            handle,
            validate: { try await validator(claimed) },
            start: start,
            abort: abort
        )
    }

    func tombstonesForTesting() -> [ProductionC1ExactBoundStartTombstone] {
        tombstonesByPairAuthority.values
            .flatMap { $0 }
            .sorted { $0.generation < $1.generation }
    }

    func liveCountForTesting() -> Int { recordsByMarker.count }

    static func runPreStartAbortForTesting(
        start: @escaping StartOperation,
        abort: @escaping AbortOperation
    ) async throws {
        let operation = OperationLatch(start: start, abort: abort)
        _ = await operation.abort(invokedBy: nil)
        try await operation.start()
    }
    #endif
}
