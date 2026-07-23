import BridgeProtocol
import Foundation
import P2PNATContracts
import Transport
@_spi(ProductionTransport) import TrustedDevices

enum MacRuntimeProductionSecureChannelError: Error, Equatable, Sendable {
    case invalidPhase
    case invalidFrame
    case invalidPeerRole
    case sessionMismatch
    case rawSendFailed
    case outboundQueueOverflow
    case inboundMailboxOverflow
    case envelopeTooLarge
    case terminal
}

struct MacRuntimeProductionSecureChannelDescriptor: Equatable, Sendable {
    let bindingDigest: String
    let sessionID: String
    let expiresAtMs: UInt64
}

struct MacRuntimeProductionSecureChannelSealResult: Equatable, Sendable {
    let keyUpdateRequired: Bool
    let terminalAfterRecord: Bool
}

enum MacRuntimeProductionSecureChannelOpenResult: Equatable, Sendable {
    case application(keyUpdateRequired: Bool, terminalAfterRecord: Bool)
    case keyUpdate(nextEpoch: UInt32, terminalAfterRecord: Bool)

    var terminalAfterRecord: Bool {
        switch self {
        case let .application(_, terminalAfterRecord),
             let .keyUpdate(_, terminalAfterRecord):
            terminalAfterRecord
        }
    }
}

/// Internal seam keeps channel state-machine tests independent of real crypto
/// while the production adapter remains a narrow wrapper around the SPI facade.
protocol MacRuntimeProductionSecureSessionOperations: AnyObject, Sendable {
    var descriptor: MacRuntimeProductionSecureChannelDescriptor { get }

    @discardableResult
    func installTerminalObserver(
        _ observer: @escaping @Sendable () -> Void
    ) -> Bool
    func sendLocalConfirmation(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws
    func acceptPeerConfirmation(_ canonicalConfirmation: Data) async throws
    func activate() async throws
    func sealApplicationAndSend(
        _ plaintext: Data,
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> MacRuntimeProductionSecureChannelSealResult
    func sealKeyUpdateAndSend(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> MacRuntimeProductionSecureChannelSealResult
    func openAndPublish(
        _ canonicalRecord: Data,
        publishApplication: @escaping @Sendable (Data) throws -> Void
    ) async throws -> MacRuntimeProductionSecureChannelOpenResult
    func close() async
}

final class MacRuntimeProductionSecureSessionFacadeAdapter:
    MacRuntimeProductionSecureSessionOperations,
    @unchecked Sendable
{
    private let session: ProductionC1TransportSecureSession

    init(_ session: ProductionC1TransportSecureSession) {
        self.session = session
    }

    var descriptor: MacRuntimeProductionSecureChannelDescriptor {
        MacRuntimeProductionSecureChannelDescriptor(
            bindingDigest: session.descriptor.bindingDigest,
            sessionID: session.descriptor.sessionID,
            expiresAtMs: session.descriptor.expiresAtMs
        )
    }

    @discardableResult
    func installTerminalObserver(
        _ observer: @escaping @Sendable () -> Void
    ) -> Bool {
        session.installTerminalObserver(observer)
    }

    func sendLocalConfirmation(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws {
        try await session.sendLocalConfirmation(using: send)
    }

    func acceptPeerConfirmation(_ canonicalConfirmation: Data) async throws {
        try await session.acceptPeerConfirmation(canonicalConfirmation)
    }

    func activate() async throws {
        try await session.activate()
    }

    func sealApplicationAndSend(
        _ plaintext: Data,
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> MacRuntimeProductionSecureChannelSealResult {
        let result = try await session.sealApplicationAndSend(plaintext, using: send)
        return MacRuntimeProductionSecureChannelSealResult(
            keyUpdateRequired: result.keyUpdateRequired,
            terminalAfterRecord: result.terminalAfterRecord
        )
    }

    func sealKeyUpdateAndSend(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> MacRuntimeProductionSecureChannelSealResult {
        let result = try await session.sealKeyUpdateAndSend(using: send)
        return MacRuntimeProductionSecureChannelSealResult(
            keyUpdateRequired: result.keyUpdateRequired,
            terminalAfterRecord: result.terminalAfterRecord
        )
    }

    func openAndPublish(
        _ canonicalRecord: Data,
        publishApplication: @escaping @Sendable (Data) throws -> Void
    ) async throws -> MacRuntimeProductionSecureChannelOpenResult {
        let result: ProductionC1TransportOpenPublication<Void> = try await session
            .openAndPublish(canonicalRecord) { plaintext in
                try publishApplication(plaintext)
            }
        switch result {
        case let .application(_, keyUpdateRequired, terminalAfterRecord):
            return .application(
                keyUpdateRequired: keyUpdateRequired,
                terminalAfterRecord: terminalAfterRecord
            )
        case let .keyUpdate(nextEpoch, terminalAfterRecord):
            return .keyUpdate(
                nextEpoch: nextEpoch,
                terminalAfterRecord: terminalAfterRecord
            )
        }
    }

    func close() async { await session.close() }
}

/// A generation-bound raw-body secure channel. It is intentionally not wired
/// into the production manager yet and opens no sockets on its own.
final class MacRuntimeProductionSecureChannel: RuntimeMessageSink, @unchecked Sendable {
    typealias EnvelopeRouter = @Sendable (
        ProtocolEnvelope,
        any RuntimeMessageSink
    ) -> Void

    private enum Phase { case handshake, active, drainingTerminal, terminal }

    private struct OutboundItem {
        let id: UUID
        let generationID: UUID
        let envelope: ProtocolEnvelope
        let completion: @Sendable (Bool) -> Void
    }

    private struct MailboxItem {
        let id: UUID
        let generationID: UUID
        let envelope: ProtocolEnvelope
        var terminalAfterDelivery: Bool
    }

    private struct State {
        var phase: Phase = .handshake
        var inboundProcessing = false
        var outbound: [OutboundItem] = []
        var outboundInFlight: OutboundItem?
        var outboundWorkerRunning = false
        var keyUpdateRequired = false
        var stagedMailbox: [UUID: MailboxItem] = [:]
        var mailbox: [MailboxItem] = []
        var mailboxInFlight: MailboxItem?
        var mailboxWorkerRunning = false
        var mailboxDrainWaiters: [CheckedContinuation<Bool, Never>] = []
        var terminalCloseStarted = false
        var operationsCloseFinished = false
        var terminalCloseFinished = false
        var terminalCloseWaiters: [CheckedContinuation<Void, Never>] = []
        var activeRawSendClaim: MacRuntimeProductionSecureChannelRawSendClaim?
        var attachmentTerminalObserver: (@Sendable () -> Void)?
        var attachmentTerminalObserverInstalled = false
        var attachmentTerminalObserverFired = false
    }

    let connectionID: UUID
    let generationID: UUID
    var transportSecurityContext: TransportSecurityContext? {
        lock.lock()
        defer { lock.unlock() }
        guard state.phase == .active else { return nil }
        return TransportSecurityContext(bindingID: operations.descriptor.bindingDigest)
    }

    private let operations: any MacRuntimeProductionSecureSessionOperations
    private let rawSink: any RuntimeRawFrameBodySink
    private let router: EnvelopeRouter
    private let codec: ProtocolCodec
    private let maximumOutboundQueueDepth: Int
    private let maximumMailboxDepth: Int
    private let nowMs: @Sendable () -> UInt64
    private let handshakeTimeoutNanoseconds: UInt64
    private let sleep: @Sendable (UInt64) async throws -> Void
    private let outboundItemDeadlineNanoseconds: UInt64
    private let watchdogSleep: @Sendable (UInt64) async throws -> Void
    private let mailboxWorkerScheduler: (
        @Sendable (@escaping @Sendable () -> Void) -> Void
    )?
    private let beforeMailboxExecutionClaim: (@Sendable () -> Void)?
    private let afterMailboxExecutionClaim: (@Sendable () -> Void)?
    private let lock = NSLock()
    private var state = State()
    private var outboundWorker: Task<Void, Never>?
    private var mailboxWorker: Task<Void, Never>?
    private var expiryWorker: Task<Void, Never>?
    private var handshakeTimeoutWorker: Task<Void, Never>?
    private var outboundWatchdogWorker: Task<Void, Never>?

    convenience init(
        session: ProductionC1TransportSecureSession,
        rawSink: any RuntimeRawFrameBodySink,
        maximumOutboundQueueDepth: Int = 32,
        maximumMailboxDepth: Int = 64,
        handshakeTimeoutNanoseconds: UInt64 = 10_000_000_000,
        outboundItemDeadlineNanoseconds: UInt64 = 15_000_000_000,
        nowMs: @escaping @Sendable () -> UInt64 = {
            UInt64(Date().timeIntervalSince1970 * 1_000)
        },
        sleep: @escaping @Sendable (UInt64) async throws -> Void = {
            try await Task.sleep(nanoseconds: $0)
        },
        watchdogSleep: @escaping @Sendable (UInt64) async throws -> Void = {
            try await Task.sleep(nanoseconds: $0)
        },
        mailboxWorkerScheduler: (
            @Sendable (@escaping @Sendable () -> Void) -> Void
        )? = nil,
        beforeMailboxExecutionClaim: (@Sendable () -> Void)? = nil,
        afterMailboxExecutionClaim: (@Sendable () -> Void)? = nil,
        router: @escaping EnvelopeRouter
    ) {
        self.init(
            operations: MacRuntimeProductionSecureSessionFacadeAdapter(session),
            rawSink: rawSink,
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
    }

    init(
        operations: any MacRuntimeProductionSecureSessionOperations,
        rawSink: any RuntimeRawFrameBodySink,
        generationID: UUID = UUID(),
        maximumOutboundQueueDepth: Int = 32,
        maximumMailboxDepth: Int = 64,
        handshakeTimeoutNanoseconds: UInt64 = 10_000_000_000,
        outboundItemDeadlineNanoseconds: UInt64 = 15_000_000_000,
        nowMs: @escaping @Sendable () -> UInt64 = {
            UInt64(Date().timeIntervalSince1970 * 1_000)
        },
        sleep: @escaping @Sendable (UInt64) async throws -> Void = {
            try await Task.sleep(nanoseconds: $0)
        },
        watchdogSleep: @escaping @Sendable (UInt64) async throws -> Void = {
            try await Task.sleep(nanoseconds: $0)
        },
        mailboxWorkerScheduler: (
            @Sendable (@escaping @Sendable () -> Void) -> Void
        )? = nil,
        beforeMailboxExecutionClaim: (@Sendable () -> Void)? = nil,
        afterMailboxExecutionClaim: (@Sendable () -> Void)? = nil,
        router: @escaping EnvelopeRouter
    ) {
        precondition(maximumOutboundQueueDepth > 0)
        precondition(maximumMailboxDepth > 0)
        precondition(outboundItemDeadlineNanoseconds > 0)
        self.operations = operations
        self.rawSink = rawSink
        self.generationID = generationID
        connectionID = rawSink.connectionID
        self.maximumOutboundQueueDepth = maximumOutboundQueueDepth
        self.maximumMailboxDepth = maximumMailboxDepth
        self.handshakeTimeoutNanoseconds = handshakeTimeoutNanoseconds
        self.outboundItemDeadlineNanoseconds = outboundItemDeadlineNanoseconds
        self.nowMs = nowMs
        self.sleep = sleep
        self.watchdogSleep = watchdogSleep
        self.mailboxWorkerScheduler = mailboxWorkerScheduler
        self.beforeMailboxExecutionClaim = beforeMailboxExecutionClaim
        self.afterMailboxExecutionClaim = afterMailboxExecutionClaim
        self.router = router
        codec = ProtocolCodec()

        let installed = operations.installTerminalObserver { [weak self] in
            self?.terminalize(expectedGenerationID: generationID)
        }
        if !installed || operations.descriptor.expiresAtMs <= nowMs() {
            terminalize(expectedGenerationID: generationID)
        } else {
            scheduleExpiry()
            scheduleHandshakeTimeout()
        }
    }

    func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result {
        lock.lock()
        defer { lock.unlock() }
        let context = state.phase == .active
            ? TransportSecurityContext(bindingID: operations.descriptor.bindingDigest)
            : nil
        return try operation(context)
    }

    /// Composition-level lifecycle notification. This is deliberately
    /// separate from the exact session observer already owned by the channel.
    /// It fires once for every terminal path, including idle expiry and
    /// authority fencing where no subsequent raw body arrives.
    @discardableResult
    func installAttachmentTerminalObserver(
        _ observer: @escaping @Sendable () -> Void
    ) -> Bool {
        let invokeInline: Bool
        lock.lock()
        guard !state.attachmentTerminalObserverInstalled else {
            lock.unlock()
            return false
        }
        state.attachmentTerminalObserverInstalled = true
        if state.phase == .terminal {
            state.attachmentTerminalObserverFired = true
            invokeInline = true
        } else {
            state.attachmentTerminalObserver = observer
            invokeInline = false
        }
        lock.unlock()
        if invokeInline { observer() }
        return true
    }

    func send(_ envelope: ProtocolEnvelope) {
        send(envelope) { _ in }
    }

    func send(
        _ envelope: ProtocolEnvelope,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        _ = enqueueOutbound(
            envelope,
            completion: completion
        )
    }

    @discardableResult
    private func enqueueOutbound(
        _ envelope: ProtocolEnvelope,
        completion: @escaping @Sendable (Bool) -> Void
    ) -> UUID? {
        let item = OutboundItem(
            id: UUID(),
            generationID: generationID,
            envelope: envelope,
            completion: completion
        )
        var shouldStartWorker = false
        var shouldTerminalize = false
        lock.lock()
        if state.phase != .active || item.generationID != generationID {
            let shouldFailClosed = state.phase == .handshake
            lock.unlock()
            completion(false)
            if shouldFailClosed {
                terminalize(expectedGenerationID: generationID)
            }
            return nil
        }
        let outstanding = state.outbound.count + (state.outboundInFlight == nil ? 0 : 1)
        if outstanding >= maximumOutboundQueueDepth {
            shouldTerminalize = true
        } else {
            state.outbound.append(item)
            if !state.outboundWorkerRunning {
                state.outboundWorkerRunning = true
                shouldStartWorker = true
            }
        }
        lock.unlock()
        if shouldTerminalize {
            completion(false)
            terminalize(expectedGenerationID: generationID)
            return nil
        } else if shouldStartWorker {
            startOutboundWorker()
        }
        return item.id
    }

    func sendAndWait(_ envelope: ProtocolEnvelope) async -> Bool {
        let claim = MacRuntimeProductionSecureChannelSendWaitClaim()
        return await withTaskCancellationHandler {
            await withCheckedContinuation { continuation in
                claim.install(continuation)
                guard !claim.isCancelled else {
                    claim.resolve(false)
                    return
                }
                let requestID = enqueueOutbound(envelope) {
                    claim.resolve($0)
                }
                claim.installRequestID(requestID) { [weak self] requestID in
                    self?.cancelOutboundRequest(requestID)
                }
            }
        } onCancel: {
            claim.cancel(
                cancelRequest: { [weak self] requestID in
                    self?.cancelOutboundRequest(requestID)
                },
                cancelBeforeRequestClaim: { [weak self] in
                    guard let self else { return }
                    terminalize(expectedGenerationID: generationID)
                }
            )
        }
    }

    func close() {
        terminalize(expectedGenerationID: generationID)
    }

    func timeout() {
        terminalize(expectedGenerationID: generationID)
    }

    func closeAndWait() async {
        terminalize(expectedGenerationID: generationID)
        await withCheckedContinuation { continuation in
            lock.lock()
            if state.terminalCloseFinished {
                lock.unlock()
                continuation.resume()
            } else {
                state.terminalCloseWaiters.append(continuation)
                lock.unlock()
            }
        }
    }

    func receiveRawFrameBody(_ body: Data) async throws {
        try await receiveRawFrameBody(body, generationID: generationID)
    }

    func receiveRawFrameBody(_ body: Data, generationID callbackGenerationID: UUID)
        async throws
    {
        guard callbackGenerationID == generationID else { return }
        // `LocalPeerServer` awaits each raw-body handler before requesting the
        // next body. We still fail closed on a concurrent external callback,
        // avoiding an unbounded continuation queue if that invariant regresses.
        guard claimInbound(generationID: callbackGenerationID) else {
            terminalize(expectedGenerationID: callbackGenerationID)
            throw MacRuntimeProductionSecureChannelError.invalidPhase
        }
        do {
            try await processRawFrameBody(
                body,
                generationID: callbackGenerationID
            )
            releaseInbound(generationID: callbackGenerationID)
        } catch {
            releaseInbound(generationID: callbackGenerationID)
            terminalize(expectedGenerationID: callbackGenerationID)
            throw error
        }
    }

    func waitUntilMailboxDrained() async -> Bool {
        await withCheckedContinuation { continuation in
            lock.lock()
            if state.phase == .terminal {
                lock.unlock()
                continuation.resume(returning: false)
            } else if state.stagedMailbox.isEmpty,
                      state.mailbox.isEmpty,
                      !state.mailboxWorkerRunning {
                lock.unlock()
                continuation.resume(returning: true)
            } else {
                state.mailboxDrainWaiters.append(continuation)
                lock.unlock()
            }
        }
    }

    private func processRawFrameBody(
        _ body: Data,
        generationID callbackGenerationID: UUID
    ) async throws {
        let phase = currentPhase(generationID: callbackGenerationID)
        switch phase {
        case .handshake:
            let confirmation = try parseConfirmation(body)
            guard confirmation.confirmingRole == .client else {
                throw MacRuntimeProductionSecureChannelError.invalidPeerRole
            }
            guard confirmation.sessionId == operations.descriptor.sessionID else {
                throw MacRuntimeProductionSecureChannelError.sessionMismatch
            }
            try await operations.acceptPeerConfirmation(body)
            try await operations.sendLocalConfirmation { [weak self] runtimeBody in
                guard let self else {
                    throw MacRuntimeProductionSecureChannelError.terminal
                }
                let runtimeConfirmation = try self.parseConfirmation(runtimeBody)
                guard runtimeConfirmation.confirmingRole == .runtime else {
                    throw MacRuntimeProductionSecureChannelError.invalidPeerRole
                }
                guard runtimeConfirmation.sessionId == self.operations.descriptor.sessionID else {
                    throw MacRuntimeProductionSecureChannelError.sessionMismatch
                }
                try await self.sendRawAndWait(
                    runtimeBody,
                    generationID: callbackGenerationID
                )
            }
            try await operations.activate()
            guard transitionToActive(generationID: callbackGenerationID) else {
                throw MacRuntimeProductionSecureChannelError.terminal
            }
        case .active:
            let record = try parseRecord(body)
            guard record.senderRole == .client else {
                throw MacRuntimeProductionSecureChannelError.invalidPeerRole
            }
            guard record.sessionId == operations.descriptor.sessionID else {
                throw MacRuntimeProductionSecureChannelError.sessionMismatch
            }
            let mailboxReservation =
                MacRuntimeProductionSecureChannelMailboxReservationCapture()
            do {
                let result = try await withTaskCancellationHandler {
                    try await operations.openAndPublish(body) { [weak self] plaintext in
                        guard let self else {
                            throw MacRuntimeProductionSecureChannelError.terminal
                        }
                        guard record.contentType == .application else {
                            throw MacRuntimeProductionSecureChannelError.invalidFrame
                        }
                        let envelope = try self.codec.decodeEnvelope(plaintext)
                        let reservationID = try self.stageMailbox(
                            envelope,
                            generationID: callbackGenerationID
                        )
                        guard mailboxReservation.storeIfEmpty(reservationID) else {
                            self.suppressStagedMailbox(
                                reservationID,
                                generationID: callbackGenerationID
                            )
                            throw MacRuntimeProductionSecureChannelError.invalidFrame
                        }
                    }
                } onCancel: { [weak self] in
                    self?.terminalize(expectedGenerationID: callbackGenerationID)
                }
                try Task.checkCancellation()
                switch (record.contentType, result) {
                case (.application, .application):
                    guard let reservationID = mailboxReservation.value() else {
                        throw MacRuntimeProductionSecureChannelError.invalidFrame
                    }
                    try commitStagedMailbox(
                        reservationID,
                        terminalAfterDelivery: result.terminalAfterRecord,
                        generationID: callbackGenerationID
                    )
                case (.keyUpdate, .keyUpdate):
                    guard mailboxReservation.value() == nil else {
                        throw MacRuntimeProductionSecureChannelError.invalidFrame
                    }
                default:
                    throw MacRuntimeProductionSecureChannelError.invalidFrame
                }
                if result.terminalAfterRecord {
                    terminalize(expectedGenerationID: callbackGenerationID)
                }
            } catch {
                if let reservationID = mailboxReservation.value() {
                    suppressStagedMailbox(
                        reservationID,
                        generationID: callbackGenerationID
                    )
                }
                throw error
            }
        case .drainingTerminal, .terminal:
            throw MacRuntimeProductionSecureChannelError.terminal
        }
    }

    private func startOutboundWorker() {
        let worker = Task { [weak self] in
            guard let self else { return }
            await runOutboundWorker()
        }
        lock.lock()
        outboundWorker = worker
        let shouldCancel = state.phase != .active
        lock.unlock()
        if shouldCancel { worker.cancel() }
    }

    private func runOutboundWorker() async {
        while let item = takeNextOutboundItem() {
            startOutboundWatchdog(for: item)
            do {
                try Task.checkCancellation()
                guard currentPhase(generationID: item.generationID) == .active else {
                    throw MacRuntimeProductionSecureChannelError.invalidPhase
                }
                var body = try codec.encodeEnvelopeBody(item.envelope)
                defer { Self.wipeTemporaryData(&body) }
                guard !body.isEmpty,
                      body.count <= ProductionSecureSessionCryptoContract.maximumPlaintextBytes else {
                    throw MacRuntimeProductionSecureChannelError.envelopeTooLarge
                }
                if currentKeyUpdateRequirement(generationID: item.generationID) {
                    let update = try await operations.sealKeyUpdateAndSend { [weak self] record in
                        guard let self else {
                            throw MacRuntimeProductionSecureChannelError.terminal
                        }
                        try await self.validateAndSendRuntimeRecord(
                            record,
                            generationID: item.generationID,
                            expectedContentType: .keyUpdate
                        )
                    }
                    setKeyUpdateRequirement(
                        update.keyUpdateRequired,
                        generationID: item.generationID
                    )
                    if update.terminalAfterRecord {
                        throw MacRuntimeProductionSecureChannelError.terminal
                    }
                }
                let result = try await operations.sealApplicationAndSend(body) { [weak self] record in
                    guard let self else {
                        throw MacRuntimeProductionSecureChannelError.terminal
                    }
                    try await self.validateAndSendRuntimeRecord(
                        record,
                        generationID: item.generationID,
                        expectedContentType: .application
                    )
                }
                setKeyUpdateRequirement(
                    result.keyUpdateRequired,
                    generationID: item.generationID
                )
                try Task.checkCancellation()
                guard finishOutboundItem(item, succeeded: true) else { return }
                if result.terminalAfterRecord {
                    // Android and macOS both define this as success-then-close:
                    // the authenticated record reached raw actual completion,
                    // so its caller succeeds before the session becomes terminal.
                    terminalize(expectedGenerationID: item.generationID)
                    return
                }
            } catch {
                terminalize(expectedGenerationID: item.generationID)
                return
            }
        }
    }

    private func takeNextOutboundItem() -> OutboundItem? {
        lock.lock()
        defer { lock.unlock() }
        guard state.phase == .active else {
            state.outboundWorkerRunning = false
            return nil
        }
        guard !state.outbound.isEmpty else {
            state.outboundWorkerRunning = false
            outboundWorker = nil
            return nil
        }
        let item = state.outbound.removeFirst()
        state.outboundInFlight = item
        return item
    }

    private func finishOutboundItem(_ item: OutboundItem, succeeded: Bool) -> Bool {
        lock.lock()
        guard state.phase == .active,
              item.generationID == generationID,
              state.outboundInFlight?.id == item.id else {
            lock.unlock()
            return false
        }
        state.outboundInFlight = nil
        let watchdog = outboundWatchdogWorker
        outboundWatchdogWorker = nil
        lock.unlock()
        watchdog?.cancel()
        item.completion(succeeded)
        return true
    }

    private func startOutboundWatchdog(for item: OutboundItem) {
        let worker = Task { [weak self] in
            guard let self else { return }
            do {
                try await watchdogSleep(outboundItemDeadlineNanoseconds)
                try Task.checkCancellation()
            } catch {
                return
            }
            guard outboundWatchdogStillOwns(item) else { return }
            terminalize(expectedGenerationID: item.generationID)
        }
        lock.lock()
        outboundWatchdogWorker?.cancel()
        outboundWatchdogWorker = worker
        let shouldCancel = state.phase != .active
            || state.outboundInFlight?.id != item.id
        lock.unlock()
        if shouldCancel { worker.cancel() }
    }

    private func outboundWatchdogStillOwns(_ item: OutboundItem) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return state.phase == .active
            && state.outboundInFlight?.id == item.id
            && item.generationID == generationID
    }

    private func cancelOutboundRequest(_ requestID: UUID) {
        lock.lock()
        let ownsRequest = state.outboundInFlight?.id == requestID
            || state.outbound.contains(where: { $0.id == requestID })
        lock.unlock()
        guard ownsRequest else { return }
        terminalize(expectedGenerationID: generationID)
    }

    /// Reserves bounded mailbox capacity inside the secure-session publication
    /// callback without making the envelope executable by the router.
    private func stageMailbox(
        _ envelope: ProtocolEnvelope,
        generationID callbackGenerationID: UUID
    ) throws -> UUID {
        let itemID = UUID()
        lock.lock()
        guard state.phase == .active, callbackGenerationID == generationID else {
            lock.unlock()
            throw MacRuntimeProductionSecureChannelError.terminal
        }
        let reservedDepth = state.stagedMailbox.count + state.mailbox.count
        guard reservedDepth < maximumMailboxDepth else {
            lock.unlock()
            throw MacRuntimeProductionSecureChannelError.inboundMailboxOverflow
        }
        state.stagedMailbox[itemID] = MailboxItem(
            id: itemID,
            generationID: callbackGenerationID,
            envelope: envelope,
            terminalAfterDelivery: false
        )
        lock.unlock()
        return itemID
    }

    /// Commits only after `openAndPublish` has completed its post-fence check.
    /// The append and worker-start claim are one lock-linearized transition.
    private func commitStagedMailbox(
        _ itemID: UUID,
        terminalAfterDelivery: Bool,
        generationID callbackGenerationID: UUID
    ) throws {
        var shouldStartWorker = false
        lock.lock()
        guard state.phase == .active,
              callbackGenerationID == generationID,
              var item = state.stagedMailbox.removeValue(forKey: itemID),
              item.generationID == callbackGenerationID else {
            lock.unlock()
            throw MacRuntimeProductionSecureChannelError.terminal
        }
        item.terminalAfterDelivery = terminalAfterDelivery
        state.mailbox.append(item)
        if !state.mailboxWorkerRunning {
            state.mailboxWorkerRunning = true
            shouldStartWorker = true
        }
        lock.unlock()
        if shouldStartWorker { startMailboxWorker() }
    }

    private func suppressStagedMailbox(
        _ itemID: UUID,
        generationID callbackGenerationID: UUID
    ) {
        lock.lock()
        if callbackGenerationID == generationID {
            state.stagedMailbox.removeValue(forKey: itemID)
        }
        lock.unlock()
    }

    private func startMailboxWorker() {
        if let mailboxWorkerScheduler {
            mailboxWorkerScheduler { [weak self] in
                self?.runMailboxWorker()
            }
            return
        }
        let worker = Task { [weak self] in
            guard let self else { return }
            runMailboxWorker()
        }
        lock.lock()
        mailboxWorker = worker
        let shouldCancel = state.phase == .terminal
        lock.unlock()
        if shouldCancel { worker.cancel() }
    }

    private func runMailboxWorker() {
        while true {
            let item: MailboxItem?
            let waiters: [CheckedContinuation<Bool, Never>]
            lock.lock()
            let hasQueuedItem = !state.mailbox.isEmpty
            lock.unlock()
            if hasQueuedItem { beforeMailboxExecutionClaim?() }
            lock.lock()
            if state.phase == .terminal {
                state.mailboxWorkerRunning = false
                mailboxWorker = nil
                lock.unlock()
                return
            }
            if state.mailbox.isEmpty {
                state.mailboxWorkerRunning = false
                mailboxWorker = nil
                if state.stagedMailbox.isEmpty {
                    waiters = state.mailboxDrainWaiters
                    state.mailboxDrainWaiters.removeAll()
                } else {
                    waiters = []
                }
                item = nil
            } else {
                // Dequeue and execution claim are one lock-linearized step.
                // Once claimed, a later terminal observer cannot suppress the
                // already committed publication.
                let claimed = state.mailbox.removeFirst()
                state.mailboxInFlight = claimed
                item = claimed
                waiters = []
            }
            lock.unlock()
            for waiter in waiters { waiter.resume(returning: true) }
            guard let item else {
                finishTerminalCloseIfReady(expectedGenerationID: generationID)
                return
            }
            afterMailboxExecutionClaim?()
            router(item.envelope, self)
            finishMailboxExecutionClaim(item)
        }
    }

    private func finishMailboxExecutionClaim(_ originalItem: MailboxItem) {
        var shouldRequestTerminal = false
        var drainWaiters: [CheckedContinuation<Bool, Never>] = []
        lock.lock()
        if state.mailboxInFlight?.id == originalItem.id {
            shouldRequestTerminal = state.mailboxInFlight?.terminalAfterDelivery == true
            state.mailboxInFlight = nil
            if state.stagedMailbox.isEmpty && state.mailbox.isEmpty {
                drainWaiters = state.mailboxDrainWaiters
                state.mailboxDrainWaiters.removeAll()
            }
        }
        lock.unlock()
        drainWaiters.forEach { $0.resume(returning: true) }
        if shouldRequestTerminal {
            terminalize(expectedGenerationID: originalItem.generationID)
        }
        finishTerminalCloseIfReady(expectedGenerationID: originalItem.generationID)
    }

    private func validateAndSendRuntimeRecord(
        _ body: Data,
        generationID callbackGenerationID: UUID,
        expectedContentType: ProductionSecureSessionContentType
    ) async throws {
        let record = try parseRecord(body)
        guard record.senderRole == .runtime else {
            throw MacRuntimeProductionSecureChannelError.invalidPeerRole
        }
        guard record.sessionId == operations.descriptor.sessionID else {
            throw MacRuntimeProductionSecureChannelError.sessionMismatch
        }
        guard record.contentType == expectedContentType else {
            throw MacRuntimeProductionSecureChannelError.invalidFrame
        }
        try await sendRawAndWait(body, generationID: callbackGenerationID)
    }

    private func sendRawAndWait(
        _ body: Data,
        generationID callbackGenerationID: UUID
    ) async throws {
        try Task.checkCancellation()
        let claim = MacRuntimeProductionSecureChannelRawSendClaim()
        guard installRawSendClaim(
            claim,
            generationID: callbackGenerationID
        ) else {
            throw MacRuntimeProductionSecureChannelError.terminal
        }
        let succeeded = await withTaskCancellationHandler {
            await claim.wait { [rawSink] completion in
                rawSink.sendRawFrameBody(body, completion: completion)
            }
        } onCancel: {
            claim.resolve(false)
        }
        clearRawSendClaim(claim)
        guard succeeded else {
            throw MacRuntimeProductionSecureChannelError.rawSendFailed
        }
        try Task.checkCancellation()
        let phase = currentPhase(generationID: callbackGenerationID)
        guard phase == .handshake || phase == .active else {
            throw MacRuntimeProductionSecureChannelError.terminal
        }
    }

    private func installRawSendClaim(
        _ claim: MacRuntimeProductionSecureChannelRawSendClaim,
        generationID callbackGenerationID: UUID
    ) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard callbackGenerationID == generationID,
              state.phase == .handshake || state.phase == .active,
              state.activeRawSendClaim == nil else {
            return false
        }
        state.activeRawSendClaim = claim
        return true
    }

    private func clearRawSendClaim(
        _ claim: MacRuntimeProductionSecureChannelRawSendClaim
    ) {
        lock.lock()
        if state.activeRawSendClaim === claim {
            state.activeRawSendClaim = nil
        }
        lock.unlock()
    }

    private func parseConfirmation(
        _ body: Data
    ) throws -> ProductionSecureSessionKeyConfirmation {
        try validateHeader(
            body,
            objectType: ProductionSecureSessionCryptoContract.keyConfirmationObjectType,
            maximumBytes: ProductionSecureSessionCryptoContract.maximumKeyConfirmationBytes
        )
        do {
            return try ProductionSecureSessionKeyConfirmation(canonicalBytes: body)
        } catch {
            throw MacRuntimeProductionSecureChannelError.invalidFrame
        }
    }

    private func parseRecord(
        _ body: Data
    ) throws -> ProductionSecureSessionEncryptedRecord {
        try validateHeader(
            body,
            objectType: ProductionSecureSessionCryptoContract.encryptedRecordObjectType,
            maximumBytes: ProductionSecureSessionCryptoContract.maximumRecordBytes
        )
        do {
            return try ProductionSecureSessionEncryptedRecord(canonicalBytes: body)
        } catch {
            throw MacRuntimeProductionSecureChannelError.invalidFrame
        }
    }

    private func validateHeader(
        _ body: Data,
        objectType: UInt8,
        maximumBytes: Int
    ) throws {
        guard !body.isEmpty,
              body.count <= maximumBytes,
              body.count >= 6,
              body.prefix(4) == ProductionSecureSessionContract.magic,
              body[body.startIndex + 4] == objectType,
              body[body.startIndex + 5] == ProductionSecureSessionContract.version else {
            throw MacRuntimeProductionSecureChannelError.invalidFrame
        }
    }

    private func currentPhase(generationID callbackGenerationID: UUID) -> Phase {
        lock.lock()
        defer { lock.unlock() }
        guard callbackGenerationID == generationID else { return .terminal }
        return state.phase
    }

    private func transitionToActive(generationID callbackGenerationID: UUID) -> Bool {
        lock.lock()
        guard callbackGenerationID == generationID, state.phase == .handshake else {
            lock.unlock()
            return false
        }
        state.phase = .active
        let timeoutWorker = handshakeTimeoutWorker
        handshakeTimeoutWorker = nil
        lock.unlock()
        timeoutWorker?.cancel()
        return true
    }

    private func currentKeyUpdateRequirement(
        generationID callbackGenerationID: UUID
    ) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard callbackGenerationID == generationID, state.phase == .active else {
            return false
        }
        return state.keyUpdateRequired
    }

    private func setKeyUpdateRequirement(
        _ required: Bool,
        generationID callbackGenerationID: UUID
    ) {
        lock.lock()
        if callbackGenerationID == generationID, state.phase == .active {
            state.keyUpdateRequired = required
        }
        lock.unlock()
    }

    private func scheduleExpiry() {
        let expiresAtMs = operations.descriptor.expiresAtMs
        let worker = Task { [weak self] in
            guard let self else { return }
            while true {
                do {
                    try Task.checkCancellation()
                } catch {
                    return
                }
                guard currentPhase(generationID: generationID) != .terminal else { return }
                let current = nowMs()
                guard expiresAtMs > current else {
                    terminalize(expectedGenerationID: generationID)
                    return
                }
                // Short monotonic chunks avoid multiplication overflow and
                // re-check wall-clock jumps in either direction.
                let remainingMs = min(expiresAtMs - current, 60_000)
                do {
                    try await sleep(remainingMs * 1_000_000)
                    await Task.yield()
                } catch {
                    return
                }
            }
        }
        lock.lock()
        expiryWorker = worker
        let shouldCancel = state.phase == .terminal
        lock.unlock()
        if shouldCancel { worker.cancel() }
    }

    private func scheduleHandshakeTimeout() {
        let worker = Task { [weak self] in
            guard let self else { return }
            do {
                try await sleep(handshakeTimeoutNanoseconds)
            } catch {
                return
            }
            guard currentPhase(generationID: generationID) == .handshake else { return }
            terminalize(expectedGenerationID: generationID)
        }
        lock.lock()
        handshakeTimeoutWorker = worker
        let shouldCancel = state.phase != .handshake
        lock.unlock()
        if shouldCancel { worker.cancel() }
    }

    private func terminalize(expectedGenerationID: UUID) {
        let rejected: [OutboundItem]
        let mailboxWaiters: [CheckedContinuation<Bool, Never>]
        let outboundWorker: Task<Void, Never>?
        let mailboxWorker: Task<Void, Never>?
        let expiryWorker: Task<Void, Never>?
        let handshakeTimeoutWorker: Task<Void, Never>?
        let outboundWatchdogWorker: Task<Void, Never>?
        let rawSendClaim: MacRuntimeProductionSecureChannelRawSendClaim?
        let shouldDrainMailbox: Bool
        lock.lock()
        guard expectedGenerationID == generationID,
              state.phase != .terminal,
              state.phase != .drainingTerminal else {
            lock.unlock()
            return
        }
        shouldDrainMailbox = !state.mailbox.isEmpty || state.mailboxInFlight != nil
        state.phase = shouldDrainMailbox ? .drainingTerminal : .terminal
        // STAGED reservations have not crossed the facade's post-fence commit
        // point and therefore never acquire terminal-drain delivery rights.
        state.stagedMailbox.removeAll(keepingCapacity: false)
        rejected = (state.outboundInFlight.map { [$0] } ?? []) + state.outbound
        state.outboundInFlight = nil
        state.outbound.removeAll(keepingCapacity: false)
        if shouldDrainMailbox {
            mailboxWaiters = []
        } else {
            mailboxWaiters = state.mailboxDrainWaiters
            state.mailboxDrainWaiters.removeAll()
        }
        outboundWorker = self.outboundWorker
        mailboxWorker = shouldDrainMailbox ? nil : self.mailboxWorker
        expiryWorker = self.expiryWorker
        handshakeTimeoutWorker = self.handshakeTimeoutWorker
        outboundWatchdogWorker = self.outboundWatchdogWorker
        rawSendClaim = state.activeRawSendClaim
        state.activeRawSendClaim = nil
        self.outboundWorker = nil
        if !shouldDrainMailbox { self.mailboxWorker = nil }
        self.expiryWorker = nil
        self.handshakeTimeoutWorker = nil
        self.outboundWatchdogWorker = nil
        lock.unlock()

        outboundWorker?.cancel()
        mailboxWorker?.cancel()
        expiryWorker?.cancel()
        handshakeTimeoutWorker?.cancel()
        outboundWatchdogWorker?.cancel()
        rawSendClaim?.resolve(false)
        rejected.forEach { $0.completion(false) }
        mailboxWaiters.forEach { $0.resume(returning: false) }
        finishTerminalCloseIfReady(expectedGenerationID: expectedGenerationID)
    }

    private func markOperationsCloseFinished(expectedGenerationID: UUID) {
        lock.lock()
        guard expectedGenerationID == generationID,
              state.terminalCloseStarted else {
            lock.unlock()
            return
        }
        state.operationsCloseFinished = true
        lock.unlock()
        finishTerminalCloseIfReady(expectedGenerationID: expectedGenerationID)
    }

    private func finishTerminalCloseIfReady(expectedGenerationID: UUID) {
        var shouldStartClose = false
        var waiters: [CheckedContinuation<Void, Never>] = []
        var attachmentTerminalObserver: (@Sendable () -> Void)?
        lock.lock()
        guard expectedGenerationID == generationID,
              state.phase == .drainingTerminal || state.phase == .terminal,
              state.stagedMailbox.isEmpty,
              state.mailbox.isEmpty,
              state.mailboxInFlight == nil else {
            lock.unlock()
            return
        }
        state.phase = .terminal
        if !state.terminalCloseStarted {
            state.terminalCloseStarted = true
            shouldStartClose = true
        }
        if state.operationsCloseFinished && !state.terminalCloseFinished {
            state.terminalCloseFinished = true
            waiters = state.terminalCloseWaiters
            state.terminalCloseWaiters.removeAll()
        }
        if state.attachmentTerminalObserverInstalled,
           !state.attachmentTerminalObserverFired {
            state.attachmentTerminalObserverFired = true
            attachmentTerminalObserver = state.attachmentTerminalObserver
            state.attachmentTerminalObserver = nil
        }
        lock.unlock()
        if shouldStartClose {
            // A committed inbound publication owns delivery before teardown.
            // Raw/session closure starts only after that mailbox claim drains.
            rawSink.close()
            Task { [weak self, operations] in
                await operations.close()
                self?.markOperationsCloseFinished(
                    expectedGenerationID: expectedGenerationID
                )
            }
        }
        attachmentTerminalObserver?()
        waiters.forEach { $0.resume() }
    }

    private func claimInbound(generationID callbackGenerationID: UUID) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard callbackGenerationID == generationID,
              state.phase == .handshake || state.phase == .active,
              !state.inboundProcessing else {
            return false
        }
        state.inboundProcessing = true
        return true
    }

    private func releaseInbound(generationID callbackGenerationID: UUID) {
        lock.lock()
        if callbackGenerationID == generationID {
            state.inboundProcessing = false
        }
        lock.unlock()
    }

    private static func wipeTemporaryData(_ data: inout Data) {
        guard !data.isEmpty else { return }
        data.resetBytes(in: data.startIndex..<data.endIndex)
        data.removeAll(keepingCapacity: false)
    }
}

private final class MacRuntimeProductionSecureChannelSendWaitClaim:
    @unchecked Sendable
{
    private let lock = NSLock()
    private var continuation: CheckedContinuation<Bool, Never>?
    private var requestID: UUID?
    private var cancelled = false
    private var resolved = false

    var isCancelled: Bool {
        lock.lock()
        defer { lock.unlock() }
        return cancelled
    }

    func install(_ continuation: CheckedContinuation<Bool, Never>) {
        lock.lock()
        self.continuation = continuation
        lock.unlock()
    }

    func installRequestID(
        _ requestID: UUID?,
        cancel: (UUID) -> Void
    ) {
        lock.lock()
        self.requestID = requestID
        let shouldCancel = cancelled && !resolved
        lock.unlock()
        if shouldCancel, let requestID { cancel(requestID) }
    }

    func cancel(
        cancelRequest: (UUID) -> Void,
        cancelBeforeRequestClaim: () -> Void
    ) {
        lock.lock()
        cancelled = true
        let shouldCancel = !resolved
        let requestID = shouldCancel ? requestID : nil
        lock.unlock()
        guard shouldCancel else { return }
        if let requestID {
            cancelRequest(requestID)
        } else {
            cancelBeforeRequestClaim()
        }
    }

    func resolve(_ value: Bool) {
        lock.lock()
        guard !resolved else {
            lock.unlock()
            return
        }
        resolved = true
        let continuation = continuation
        self.continuation = nil
        lock.unlock()
        continuation?.resume(returning: value)
    }
}

private final class MacRuntimeProductionSecureChannelRawSendClaim:
    @unchecked Sendable
{
    private let lock = NSLock()
    private var continuation: CheckedContinuation<Bool, Never>?
    private var resolvedValue: Bool?

    func wait(
        start: (@escaping @Sendable (Bool) -> Void) -> Void
    ) async -> Bool {
        await withCheckedContinuation { continuation in
            lock.lock()
            if let resolvedValue {
                lock.unlock()
                continuation.resume(returning: resolvedValue)
                return
            }
            self.continuation = continuation
            lock.unlock()
            start { [weak self] in self?.resolve($0) }
        }
    }

    func resolve(_ value: Bool) {
        lock.lock()
        guard resolvedValue == nil else {
            lock.unlock()
            return
        }
        resolvedValue = value
        let continuation = continuation
        self.continuation = nil
        lock.unlock()
        continuation?.resume(returning: value)
    }
}

private final class MacRuntimeProductionSecureChannelMailboxReservationCapture:
    @unchecked Sendable
{
    private let lock = NSLock()
    private var itemID: UUID?

    func storeIfEmpty(_ itemID: UUID) -> Bool {
        lock.lock()
        guard self.itemID == nil else {
            lock.unlock()
            return false
        }
        self.itemID = itemID
        lock.unlock()
        return true
    }

    func value() -> UUID? {
        lock.lock()
        defer { lock.unlock() }
        return itemID
    }
}
