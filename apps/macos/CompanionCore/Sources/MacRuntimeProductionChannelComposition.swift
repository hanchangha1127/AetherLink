import BridgeProtocol
import Foundation
@_spi(ProductionRawEndpointOwnership) import Transport
@_spi(ProductionTransport) import TrustedDevices

enum MacRuntimeProductionChannelCompositionError: Error, Equatable, Sendable {
    case authorityCapabilityUnavailable
    case attachmentRightAlreadyIssued
    case duplicateAcceptedSession
    case rawHandlerInstallationRejected
    case rawEndpointUnavailable
    case acceptedRouteDescriptorMismatch
    case attachmentCancelled
}

/// The manager-facing surface of the production secure channel. Keeping this
/// protocol internal prevents an accepted raw transport from selecting a
/// legacy envelope handler after production composition has begun.
protocol MacRuntimeProductionComposedChannel:
    RuntimeMessageSink,
    AnyObject,
    Sendable
{
    func receiveRawFrameBody(_ body: Data) async throws
    func closeAndWait() async
    @discardableResult
    func installAttachmentTerminalObserver(
        _ observer: @escaping @Sendable () -> Void
    ) -> Bool
}

extension MacRuntimeProductionSecureChannel: MacRuntimeProductionComposedChannel {}

/// Opaque, one-use authority to start exactly one production channel.
///
/// A consumed claim remains owned here until channel construction transfers
/// it. That makes invalidation effective even while a non-cooperative composer
/// is suspended after consuming the claim.
final class MacRuntimeProductionChannelAuthorityCapability: @unchecked Sendable {
    typealias Router = @Sendable (
        ProtocolEnvelope,
        any RuntimeMessageSink
    ) -> Void
    typealias MakeChannel = @Sendable (
        any RuntimeRawFrameBodySink,
        @escaping Router
    ) throws -> any MacRuntimeProductionComposedChannel
    typealias Abandon = @Sendable () async -> Void

    struct Claim: Sendable {
        let makeChannel: MakeChannel
        let abandon: Abandon
    }

    private enum State {
        case available(Claim)
        case claimed(Claim)
        case transferred
        case invalidated
    }

    private let lock = NSLock()
    private var state: State

    private init(
        makeChannel: @escaping MakeChannel,
        abandon: @escaping Abandon
    ) {
        state = .available(Claim(makeChannel: makeChannel, abandon: abandon))
    }

    /// Issues a capability only when the exact-bound facade atomically grants
    /// its sole attachment right. A duplicate issue does not close the first
    /// channel or its session.
    static func issue(
        exactBoundSession: ProductionC1TransportSecureSession
    ) throws -> MacRuntimeProductionChannelAuthorityCapability {
        guard let attachmentRight = exactBoundSession.issueTransportAttachmentRight()
        else {
            throw MacRuntimeProductionChannelCompositionError
                .attachmentRightAlreadyIssued
        }
        return MacRuntimeProductionChannelAuthorityCapability(
            makeChannel: { rawSink, router in
                _ = attachmentRight
                return MacRuntimeProductionSecureChannel(
                    session: exactBoundSession,
                    rawSink: rawSink,
                    router: router
                )
            },
            abandon: {
                _ = attachmentRight
                await exactBoundSession.close()
            }
        )
    }

    #if DEBUG
    static func testing(
        makeChannel: @escaping MakeChannel,
        abandon: @escaping Abandon
    ) -> MacRuntimeProductionChannelAuthorityCapability {
        MacRuntimeProductionChannelAuthorityCapability(
            makeChannel: makeChannel,
            abandon: abandon
        )
    }
    #endif

    func consume() -> Claim? {
        lock.lock()
        defer { lock.unlock() }
        guard case .available(let claim) = state else { return nil }
        state = .claimed(claim)
        return claim
    }

    func transferClaimToChannel() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard case .claimed = state else { return false }
        state = .transferred
        return true
    }

    /// Invalidates either an unconsumed or an in-progress claim. Authority
    /// already transferred to a channel remains owned by that channel.
    func invalidate() async {
        await claimInvalidation()?()
    }

    /// Claims the state transition synchronously so registry teardown can make
    /// a capability unavailable before exposing a replacement generation.
    /// The returned asynchronous abandon work must run after caller locks are
    /// released.
    func claimInvalidation() -> Abandon? {
        lock.lock()
        defer { lock.unlock() }
        switch state {
        case .available(let claim), .claimed(let claim):
            state = .invalidated
            return claim.abandon
        case .transferred, .invalidated:
            return nil
        }
    }
}

protocol MacRuntimeProductionChannelComposing: Sendable {
    func compose(
        endpointClaim: RuntimeAcceptedRawEndpointClaim,
        authorityCapability: MacRuntimeProductionChannelAuthorityCapability,
        router: @escaping MacRuntimeProductionChannelAuthorityCapability.Router
    ) async throws -> any MacRuntimeProductionComposedChannel
}

/// Neutral composition only. It does not open a listener, select a route, or
/// manufacture authority. Raw-session lifetime remains registry-owned.
struct MacRuntimeProductionChannelComposer:
    MacRuntimeProductionChannelComposing,
    Sendable
{
    func compose(
        endpointClaim: RuntimeAcceptedRawEndpointClaim,
        authorityCapability: MacRuntimeProductionChannelAuthorityCapability,
        router: @escaping MacRuntimeProductionChannelAuthorityCapability.Router
    ) async throws -> any MacRuntimeProductionComposedChannel {
        guard let rawSink = endpointClaim.transferRawSinkToChannel() else {
            throw MacRuntimeProductionChannelCompositionError
                .rawEndpointUnavailable
        }
        guard let claim = authorityCapability.consume() else {
            throw MacRuntimeProductionChannelCompositionError
                .authorityCapabilityUnavailable
        }

        do {
            try Task.checkCancellation()
        } catch {
            await authorityCapability.invalidate()
            throw error
        }

        let channel: any MacRuntimeProductionComposedChannel
        do {
            channel = try claim.makeChannel(rawSink, router)
        } catch {
            await authorityCapability.invalidate()
            throw error
        }

        guard authorityCapability.transferClaimToChannel() else {
            channel.close()
            await channel.closeAndWait()
            throw MacRuntimeProductionChannelCompositionError.attachmentCancelled
        }

        do {
            try Task.checkCancellation()
            return channel
        } catch {
            channel.close()
            await channel.closeAndWait()
            throw error
        }
    }
}

private final class MacRuntimeProductionCompositionStartGate:
    @unchecked Sendable
{
    private let lock = NSLock()
    private var opened = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    func wait() async {
        await withCheckedContinuation { continuation in
            lock.lock()
            if opened {
                lock.unlock()
                continuation.resume()
            } else {
                waiters.append(continuation)
                lock.unlock()
            }
        }
    }

    func open() {
        lock.lock()
        guard !opened else {
            lock.unlock()
            return
        }
        opened = true
        let current = waiters
        waiters.removeAll(keepingCapacity: false)
        lock.unlock()
        current.forEach { $0.resume() }
    }
}

/// Owns every resource associated with a reserved generation, including the
/// composition task and the result waiters. A terminal claim resolves waiters
/// immediately; it never waits for a non-cooperative composer to return.
fileprivate final class MacRuntimeProductionRawSessionCleanupOwner:
    @unchecked Sendable
{
    typealias Channel = any MacRuntimeProductionComposedChannel

    private enum State {
        case pending
        case completed(Result<Channel, Error>)
        case terminal
    }

    struct Cleanup: @unchecked Sendable {
        let endpointClaim: RuntimeAcceptedRawEndpointClaim
        let compositionTask: Task<Void, Never>?
        let channel: Channel?
        let waiters: [CheckedContinuation<Channel, Error>]
        let terminalError: Error
        let abandon: MacRuntimeProductionChannelAuthorityCapability.Abandon?

        func perform() {
            endpointClaim.close()
            compositionTask?.cancel()
            channel?.close()
            waiters.forEach {
                $0.resume(throwing: terminalError)
            }
            Task {
                await abandon?()
                await channel?.closeAndWait()
            }
        }
    }

    let endpointClaim: RuntimeAcceptedRawEndpointClaim
    let authorityCapability: MacRuntimeProductionChannelAuthorityCapability
    private let lock = NSLock()
    private var state: State = .pending
    private var compositionTask: Task<Void, Never>?
    private var channel: Channel?
    private var waiters: [CheckedContinuation<Channel, Error>] = []
    private var terminalError: Error =
        MacRuntimeProductionChannelCompositionError.attachmentCancelled

    init(
        endpointClaim: RuntimeAcceptedRawEndpointClaim,
        authorityCapability: MacRuntimeProductionChannelAuthorityCapability
    ) {
        self.endpointClaim = endpointClaim
        self.authorityCapability = authorityCapability
    }

    func installCompositionTask(_ task: Task<Void, Never>) {
        lock.lock()
        if case .terminal = state {
            lock.unlock()
            task.cancel()
            return
        }
        compositionTask = task
        lock.unlock()
    }

    func waitForComposition() async throws -> Channel {
        try await withCheckedThrowingContinuation { continuation in
            lock.lock()
            switch state {
            case .pending:
                waiters.append(continuation)
                lock.unlock()
            case .completed(let result):
                lock.unlock()
                continuation.resume(with: result)
            case .terminal:
                let error = terminalError
                lock.unlock()
                continuation.resume(throwing: error)
            }
        }
    }

    func compositionSucceeded(_ composedChannel: Channel) {
        let currentWaiters: [CheckedContinuation<Channel, Error>]
        lock.lock()
        guard case .pending = state else {
            lock.unlock()
            composedChannel.close()
            Task { await composedChannel.closeAndWait() }
            return
        }
        channel = composedChannel
        state = .completed(.success(composedChannel))
        currentWaiters = waiters
        waiters.removeAll(keepingCapacity: false)
        lock.unlock()
        currentWaiters.forEach { $0.resume(returning: composedChannel) }
    }

    func compositionFailed(_ error: Error) {
        let currentWaiters: [CheckedContinuation<Channel, Error>]
        lock.lock()
        guard case .pending = state else {
            lock.unlock()
            return
        }
        state = .completed(.failure(error))
        currentWaiters = waiters
        waiters.removeAll(keepingCapacity: false)
        lock.unlock()
        currentWaiters.forEach { $0.resume(throwing: error) }
    }

    /// Must be called while the registry owns the generation transition.
    func claimTerminal(
        error: Error = MacRuntimeProductionChannelCompositionError
            .attachmentCancelled
    ) -> Cleanup? {
        lock.lock()
        defer { lock.unlock() }
        guard case .terminal = state else {
            state = .terminal
            terminalError = error
            // This lock order is registry -> owner -> capability. Composition
            // never holds the capability lock while taking the owner/registry
            // lock, so the synchronous claim cannot form a lock cycle.
            let abandon = authorityCapability.claimInvalidation()
            let cleanup = Cleanup(
                endpointClaim: endpointClaim,
                compositionTask: compositionTask,
                channel: channel,
                waiters: waiters,
                terminalError: error,
                abandon: abandon
            )
            compositionTask = nil
            channel = nil
            waiters.removeAll(keepingCapacity: false)
            return cleanup
        }
        return nil
    }
}

final class MacRuntimeProductionRawSessionAttachment:
    @unchecked Sendable
{
    typealias TerminalHandler = @Sendable (UUID, UUID) -> Void

    let connectionID: UUID
    let generationID: UUID
    private let lock = NSLock()
    private var channel: (any MacRuntimeProductionComposedChannel)?
    private var acceptingInput = false
    private var terminalReported = false
    private let onTerminal: TerminalHandler

    init(
        connectionID: UUID,
        generationID: UUID,
        channel: any MacRuntimeProductionComposedChannel,
        onTerminal: @escaping TerminalHandler
    ) {
        self.connectionID = connectionID
        self.generationID = generationID
        self.channel = channel
        self.onTerminal = onTerminal
    }

    fileprivate func activate() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard channel != nil, !terminalReported else { return false }
        acceptingInput = true
        return true
    }

    fileprivate func armTerminalObservation() -> Bool {
        guard let currentChannel = currentChannel() else { return false }
        let installed = currentChannel.installAttachmentTerminalObserver {
            [weak self] in
            self?.reportTerminalOnce()
        }
        if !installed { reportTerminalOnce() }
        return installed
    }

    fileprivate func deactivate() {
        lock.lock()
        acceptingInput = false
        channel = nil
        lock.unlock()
    }

    func receive(_ body: Data) async {
        guard let currentChannel = admittedChannel() else { return }
        do {
            try await currentChannel.receiveRawFrameBody(body)
        } catch {
            // The channel owns terminal-drain ordering. Closing it drives the
            // installed one-shot observer only after any committed mailbox
            // delivery has returned.
            currentChannel.close()
        }
    }

    private func admittedChannel()
        -> (any MacRuntimeProductionComposedChannel)?
    {
        lock.lock()
        defer { lock.unlock() }
        guard acceptingInput else { return nil }
        return channel
    }

    private func currentChannel()
        -> (any MacRuntimeProductionComposedChannel)?
    {
        lock.lock()
        defer { lock.unlock() }
        return channel
    }

    private func reportTerminalOnce() {
        lock.lock()
        guard !terminalReported else {
            lock.unlock()
            return
        }
        terminalReported = true
        acceptingInput = false
        lock.unlock()
        onTerminal(connectionID, generationID)
    }
}

final class MacRuntimeProductionRawSessionAttachments: @unchecked Sendable {
    private enum Entry {
        case reserved(
            generationID: UUID,
            owner: MacRuntimeProductionRawSessionCleanupOwner
        )
        case active(
            generationID: UUID,
            owner: MacRuntimeProductionRawSessionCleanupOwner,
            attachment: MacRuntimeProductionRawSessionAttachment
        )

        var generationID: UUID {
            switch self {
            case .reserved(let generationID, _),
                 .active(let generationID, _, _):
                return generationID
            }
        }

        var owner: MacRuntimeProductionRawSessionCleanupOwner {
            switch self {
            case .reserved(_, let owner), .active(_, let owner, _):
                return owner
            }
        }

        var attachment: MacRuntimeProductionRawSessionAttachment? {
            guard case .active(_, _, let attachment) = self else { return nil }
            return attachment
        }
    }

    fileprivate struct Reservation: @unchecked Sendable {
        fileprivate let generationID: UUID
        fileprivate let owner: MacRuntimeProductionRawSessionCleanupOwner
    }

    private let lock = NSLock()
    private var entries: [UUID: Entry] = [:]

    fileprivate func reserve(
        connectionID: UUID,
        endpointClaim: RuntimeAcceptedRawEndpointClaim,
        authorityCapability: MacRuntimeProductionChannelAuthorityCapability
    ) -> Reservation? {
        lock.lock()
        defer { lock.unlock() }
        guard entries[connectionID] == nil else { return nil }
        let generationID = UUID()
        let owner = MacRuntimeProductionRawSessionCleanupOwner(
            endpointClaim: endpointClaim,
            authorityCapability: authorityCapability
        )
        entries[connectionID] = .reserved(
            generationID: generationID,
            owner: owner
        )
        return Reservation(generationID: generationID, owner: owner)
    }

    /// Commits the exact reservation and opens its admission gate before any
    /// raw handler can be installed.
    func commitActive(
        connectionID: UUID,
        generationID: UUID,
        attachment: MacRuntimeProductionRawSessionAttachment
    ) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard case .reserved(let currentGenerationID, let owner) =
                entries[connectionID],
              currentGenerationID == generationID,
              attachment.activate() else {
            return false
        }
        entries[connectionID] = .active(
            generationID: generationID,
            owner: owner,
            attachment: attachment
        )
        return true
    }

    func isActive(connectionID: UUID, generationID: UUID) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard case .active(let currentGenerationID, _, _) =
                entries[connectionID] else {
            return false
        }
        return currentGenerationID == generationID
    }

    func terminalClaim(
        connectionID: UUID,
        generationID: UUID? = nil,
        error: Error = MacRuntimeProductionChannelCompositionError
            .attachmentCancelled
    ) {
        let cleanup: MacRuntimeProductionRawSessionCleanupOwner.Cleanup?
        lock.lock()
        guard let entry = entries[connectionID],
              generationID == nil || entry.generationID == generationID else {
            lock.unlock()
            return
        }
        entries.removeValue(forKey: connectionID)
        entry.attachment?.deactivate()
        cleanup = entry.owner.claimTerminal(error: error)
        lock.unlock()
        cleanup?.perform()
    }

    func closeAll() {
        closeAll(afterTerminalClaimsBeforeCleanup: nil)
    }

    #if DEBUG
    /// Deterministic race-test seam. The callback runs with no registry/owner
    /// lock held, after every terminal claim, and before any cleanup can close,
    /// resume, schedule abandon work, or otherwise advance asynchronous state.
    func closeAllForTesting(
        afterTerminalClaimsBeforeCleanup callback: @escaping () -> Void
    ) {
        closeAll(afterTerminalClaimsBeforeCleanup: callback)
    }
    #endif

    private func closeAll(
        afterTerminalClaimsBeforeCleanup callback: (() -> Void)?
    ) {
        let cleanups: [MacRuntimeProductionRawSessionCleanupOwner.Cleanup]
        lock.lock()
        let currentEntries = Array(entries.values)
        entries.removeAll(keepingCapacity: false)
        cleanups = currentEntries.compactMap { entry in
            entry.attachment?.deactivate()
            return entry.owner.claimTerminal()
        }
        lock.unlock()
        callback?()
        cleanups.forEach { $0.perform() }
    }
}

/// Opaque manager-prepared endpoint. The service can retain this token while
/// starting exact-bound authority, but it cannot access or transfer the raw
/// sink. Attachment consumes it once.
final class MacRuntimePreparedProductionRawSession: @unchecked Sendable {
    private let lock = NSLock()
    private var endpointClaim: RuntimeAcceptedRawEndpointClaim?

    init(endpointClaim: RuntimeAcceptedRawEndpointClaim) {
        self.endpointClaim = endpointClaim
    }

    func takeForAttachment() -> RuntimeAcceptedRawEndpointClaim? {
        lock.lock()
        defer { lock.unlock() }
        guard let endpointClaim else { return nil }
        self.endpointClaim = nil
        return endpointClaim
    }

    func close() {
        let claim: RuntimeAcceptedRawEndpointClaim?
        lock.lock()
        claim = endpointClaim
        endpointClaim = nil
        lock.unlock()
        claim?.close()
    }
}

extension MacRuntimeConnectionManager {
    /// Claims and validates the endpoint before any exact-bound authority
    /// capability is created or consumed. A mismatch is terminal.
    func prepareAcceptedProductionRawSession(
        _ acceptedSession: any RuntimeAcceptedRawSession,
        matchesExpectedDescriptor: (RuntimeAcceptedRawRouteDescriptor) -> Bool
    ) throws -> MacRuntimePreparedProductionRawSession {
        guard let endpointClaim = acceptedSession.takeRawEndpointClaim() else {
            throw MacRuntimeProductionChannelCompositionError
                .rawEndpointUnavailable
        }
        guard endpointClaim.connectionID == acceptedSession.connectionID,
              endpointClaim.routeDescriptor == acceptedSession.routeDescriptor,
              matchesExpectedDescriptor(endpointClaim.routeDescriptor) else {
            endpointClaim.close()
            throw MacRuntimeProductionChannelCompositionError
                .acceptedRouteDescriptorMismatch
        }
        return MacRuntimePreparedProductionRawSession(
            endpointClaim: endpointClaim
        )
    }

    /// Fail-closed disposal used when expected-descriptor derivation itself
    /// fails before a prepared endpoint can be returned.
    func rejectAcceptedProductionRawSession(
        _ acceptedSession: any RuntimeAcceptedRawSession
    ) {
        acceptedSession.takeRawEndpointClaim()?.close()
    }

    #if DEBUG
    /// Legacy-shaped test helper. Production service code must provide an
    /// independently derived expected descriptor before authority starts.
    func attachAcceptedProductionRawSession(
        _ acceptedSession: any RuntimeAcceptedRawSession,
        authorityCapability: MacRuntimeProductionChannelAuthorityCapability,
        composer: any MacRuntimeProductionChannelComposing =
            MacRuntimeProductionChannelComposer(),
        onMessage: @escaping LocalPeerMessageHandler
    ) async throws {
        let expectedDescriptor = acceptedSession.routeDescriptor
        let preparedSession = try prepareAcceptedProductionRawSession(
            acceptedSession,
            matchesExpectedDescriptor: { $0 == expectedDescriptor }
        )
        try await attachPreparedProductionRawSession(
            preparedSession,
            authorityCapability: authorityCapability,
            composer: composer,
            onMessage: onMessage
        )
    }
    #endif

    /// Manager-owned attachment seam used by
    /// `MacRuntimeProductionAcceptedSessionService`. The service supplies the
    /// exact-bound capability and an already accepted raw session; a concrete
    /// production transport acceptor/listener remains intentionally unwired.
    func attachPreparedProductionRawSession(
        _ preparedSession: MacRuntimePreparedProductionRawSession,
        authorityCapability: MacRuntimeProductionChannelAuthorityCapability,
        composer: any MacRuntimeProductionChannelComposing =
            MacRuntimeProductionChannelComposer(),
        onMessage: @escaping LocalPeerMessageHandler
    ) async throws {
        guard let endpointClaim = preparedSession.takeForAttachment() else {
            await authorityCapability.invalidate()
            throw MacRuntimeProductionChannelCompositionError
                .rawEndpointUnavailable
        }
        let connectionID = endpointClaim.connectionID
        guard let reservation = productionRawSessionAttachments.reserve(
            connectionID: connectionID,
            endpointClaim: endpointClaim,
            authorityCapability: authorityCapability
        ) else {
            endpointClaim.close()
            await authorityCapability.invalidate()
            throw MacRuntimeProductionChannelCompositionError
                .duplicateAcceptedSession
        }

        let generationID = reservation.generationID
        let startGate = MacRuntimeProductionCompositionStartGate()
        let owner = reservation.owner
        let compositionTask = Task {
            await startGate.wait()
            do {
                let channel = try await composer.compose(
                    endpointClaim: endpointClaim,
                    authorityCapability: authorityCapability,
                    router: onMessage
                )
                owner.compositionSucceeded(channel)
            } catch {
                owner.compositionFailed(error)
            }
        }
        owner.installCompositionTask(compositionTask)

        try await withTaskCancellationHandler {
            startGate.open()
            do {
                let channel = try await owner.waitForComposition()
                try Task.checkCancellation()
                let attachments = productionRawSessionAttachments
                let attachment = MacRuntimeProductionRawSessionAttachment(
                    connectionID: connectionID,
                    generationID: generationID,
                    channel: channel,
                    onTerminal: { connectionID, generationID in
                        attachments.terminalClaim(
                            connectionID: connectionID,
                            generationID: generationID
                        )
                    }
                )

                guard attachment.armTerminalObservation() else {
                    throw MacRuntimeProductionChannelCompositionError
                        .attachmentCancelled
                }

                guard productionRawSessionAttachments.commitActive(
                    connectionID: connectionID,
                    generationID: generationID,
                    attachment: attachment
                ) else {
                    throw MacRuntimeProductionChannelCompositionError
                        .attachmentCancelled
                }

                guard endpointClaim.installRawFrameBodyHandler({ body in
                    await attachment.receive(body)
                }) else {
                    throw MacRuntimeProductionChannelCompositionError
                        .rawHandlerInstallationRejected
                }

                guard productionRawSessionAttachments.isActive(
                    connectionID: connectionID,
                    generationID: generationID
                ) else {
                    throw MacRuntimeProductionChannelCompositionError
                        .attachmentCancelled
                }
            } catch {
                productionRawSessionAttachments.terminalClaim(
                    connectionID: connectionID,
                    generationID: generationID
                )
                throw error
            }
        } onCancel: {
            productionRawSessionAttachments.terminalClaim(
                connectionID: connectionID,
                generationID: generationID,
                error: CancellationError()
            )
        }
    }

    func stopAcceptedProductionRawSession(connectionID: UUID) {
        productionRawSessionAttachments.terminalClaim(connectionID: connectionID)
    }
}
