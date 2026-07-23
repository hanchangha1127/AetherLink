import CryptoKit
import Foundation
@_spi(AuthorityLifecycle) import P2PNATContracts

enum ProductionC1ExactBoundSecureSessionError: Error, Equatable, Sendable {
    case exactBindingMismatch
    case fenced
    case handshakeUnavailable
    case cipherUnavailable
    case alreadyActivated
}

@_spi(ProductionTransport)
public struct ProductionC1TransportSealPublication: Equatable, Sendable {
    public let keyUpdateRequired: Bool
    public let terminalAfterRecord: Bool

    fileprivate init(
        keyUpdateRequired: Bool,
        terminalAfterRecord: Bool
    ) {
        self.keyUpdateRequired = keyUpdateRequired
        self.terminalAfterRecord = terminalAfterRecord
    }
}

@_spi(ProductionTransport)
public struct ProductionC1TransportSecureSessionDescriptor: Equatable, Sendable {
    /// Domain-separated object-7/object-26 digest used by the secure-session
    /// KDF. This is deliberately distinct from the endpoint commit token's
    /// `bindingDigest`.
    public let bindingDigest: String
    public let sessionID: String
    public let expiresAtMs: UInt64

    fileprivate init(
        bindingDigest: String,
        sessionID: String,
        expiresAtMs: UInt64
    ) throws {
        guard Self.isLowercaseHex(bindingDigest, count: 64),
              Self.isLowercaseHex(sessionID, count: 32),
              expiresAtMs > 0 else {
            throw ProductionC1ExactBoundSecureSessionError.exactBindingMismatch
        }
        self.bindingDigest = bindingDigest
        self.sessionID = sessionID
        self.expiresAtMs = expiresAtMs
    }

    private static func isLowercaseHex(_ value: String, count: Int) -> Bool {
        value.utf8.count == count && value.utf8.allSatisfy {
            (48...57).contains($0) || (97...102).contains($0)
        }
    }
}

@_spi(ProductionTransport)
public enum ProductionC1TransportOpenPublication<Published: Sendable>: Sendable {
    case application(
        Published,
        keyUpdateRequired: Bool,
        terminalAfterRecord: Bool
    )
    case keyUpdate(nextEpoch: UInt32, terminalAfterRecord: Bool)
}

/// Opaque proof that the exact-bound session has granted its sole production
/// transport attachment. The value intentionally exposes no authority or
/// cryptographic material outside TrustedDevices.
@_spi(ProductionTransport)
public struct ProductionC1TransportSecureSessionAttachmentRight: Sendable {
    fileprivate let nonce: UUID

    fileprivate init(nonce: UUID) {
        self.nonce = nonce
    }
}

/// Narrow cross-module facade for the future production transport adapter.
/// It exposes neither the authority permit/coordinator nor raw crypto objects.
@_spi(ProductionTransport)
public final class ProductionC1TransportSecureSession: @unchecked Sendable {
    private let session: ProductionC1ExactBoundSecureSession
    private let attachmentRightLock = NSLock()
    private var didIssueAttachmentRight = false
    public let descriptor: ProductionC1TransportSecureSessionDescriptor

    fileprivate init(
        session: ProductionC1ExactBoundSecureSession,
        descriptor: ProductionC1TransportSecureSessionDescriptor
    ) {
        self.session = session
        self.descriptor = descriptor
    }

    static func start(
        coordinator: ProductionC1ExactBoundStartCoordinator,
        request: ProductionC1ExactBoundStartRequest,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        nowMs: @escaping @Sendable () -> UInt64
    ) async throws -> ProductionC1TransportSecureSession {
        let exactSession = try await ProductionC1ExactBoundSecureSession.start(
            coordinator: coordinator,
            request: request,
            localEphemeralKey: localEphemeralKey,
            nowMs: nowMs
        )
        do {
            let descriptor = try ProductionC1TransportSecureSessionDescriptor(
                bindingDigest: try ProductionSecureSessionCrypto.exactBindingDigestHex(
                    request.verifiedBinding.runtimeKeyScheduleBinding
                ),
                sessionID: request.token.sessionID,
                expiresAtMs: request.token.expiresAtMs
            )
            return ProductionC1TransportSecureSession(
                session: exactSession,
                descriptor: descriptor
            )
        } catch {
            await exactSession.close()
            throw error
        }
    }

    public func sendLocalConfirmation(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws {
        try await session.sendLocalConfirmation(using: send)
    }

    public func acceptPeerConfirmation(_ canonicalConfirmation: Data) async throws {
        try await session.acceptPeerConfirmation(canonicalConfirmation)
    }

    public func activate() async throws {
        try await session.activate()
    }

    public func sealApplicationAndSend(
        _ plaintext: Data,
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> ProductionC1TransportSealPublication {
        try await session.sealApplicationAndSend(plaintext, using: send)
    }

    public func sealKeyUpdateAndSend(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> ProductionC1TransportSealPublication {
        try await session.sealKeyUpdateAndSend(using: send)
    }

    public func openAndPublish<Published: Sendable>(
        _ canonicalRecord: Data,
        publishApplication: @escaping @Sendable (Data) async throws -> Published
    ) async throws -> ProductionC1TransportOpenPublication<Published> {
        try await session.openAndPublish(
            canonicalRecord,
            publishApplication: publishApplication
        )
    }

    public func close() async {
        await session.close()
    }

    /// Atomically grants this exact-bound session's only transport attachment.
    /// A duplicate request fails without closing or otherwise mutating the
    /// already attached channel/session.
    public func issueTransportAttachmentRight()
        -> ProductionC1TransportSecureSessionAttachmentRight?
    {
        attachmentRightLock.lock()
        defer { attachmentRightLock.unlock() }
        guard !didIssueAttachmentRight else { return nil }
        didIssueAttachmentRight = true
        return ProductionC1TransportSecureSessionAttachmentRight(nonce: UUID())
    }

    /// Installs the transport's one-shot synchronous terminal callback. The
    /// callback is invoked for local close, publication failure, and external
    /// authority fencing. If termination already happened, it runs inline.
    /// Returns false when an observer was already installed.
    @discardableResult
    public func installTerminalObserver(
        _ observer: @escaping @Sendable () -> Void
    ) -> Bool {
        session.installTerminalObserver(observer)
    }
}

/// Per-session drain gate used only by atomic transport publications. Existing
/// value-returning crypto APIs retain their historical close-race semantics,
/// while a transport send/publication that has begun is allowed to linearize
/// before local close wipes and completes the lease.
private actor ProductionC1TransportPublicationLifecycle {
    private var acceptingPublications = true
    private var closeFinished = false
    private var terminalFinishRequested = false
    private var activePublicationCount = 0
    private var drainWaiters: [CheckedContinuation<Void, Never>] = []
    private var closeWaiters: [CheckedContinuation<Void, Never>] = []

    func beginPublication() throws {
        guard acceptingPublications, !closeFinished else {
            throw ProductionC1ExactBoundSecureSessionError.fenced
        }
        activePublicationCount += 1
    }

    func endPublication() {
        precondition(activePublicationCount > 0)
        activePublicationCount -= 1
        if activePublicationCount == 0 {
            let waiters = drainWaiters
            drainWaiters.removeAll()
            for waiter in waiters { waiter.resume() }
            if terminalFinishRequested {
                completeClose()
            }
        }
    }

    /// Returns true only to the caller that owns final close work. Followers
    /// wait for that caller (or a terminal publication failure) to finish.
    func beginClose() async -> Bool {
        guard !closeFinished else { return false }
        if acceptingPublications {
            acceptingPublications = false
            if activePublicationCount > 0 {
                await withCheckedContinuation { drainWaiters.append($0) }
            }
            return !closeFinished
        }
        await withCheckedContinuation { closeWaiters.append($0) }
        return false
    }

    func finishClose() {
        precondition(activePublicationCount == 0)
        completeClose()
    }

    /// A terminal publication failure rejects new work immediately but does
    /// not wake close/drain waiters until every already-active publication has
    /// exited its authority read permit.
    func requestTerminalFinish() {
        acceptingPublications = false
        terminalFinishRequested = true
        guard activePublicationCount == 0 else { return }
        completeClose()
    }

    private func completeClose() {
        guard !closeFinished else { return }
        closeFinished = true
        let drains = drainWaiters
        let followers = closeWaiters
        drainWaiters.removeAll()
        closeWaiters.removeAll()
        for waiter in drains { waiter.resume() }
        for waiter in followers { waiter.resume() }
    }
}

/// Owns the exact would-be return allocation for a confirmation result. The
/// handshake keeps its own canonical confirmation cache, so suppressing this
/// result cannot corrupt the still-live handshake on a non-terminal fence.
private final class ProductionC1SensitiveResultData: @unchecked Sendable {
    private let lock = NSLock()
    private let pointer: UnsafeMutableRawPointer
    private let count: Int
    private var discarded = false

    init(copying source: Data) {
        count = source.count
        pointer = UnsafeMutableRawPointer.allocate(
            byteCount: max(source.count, 1),
            alignment: MemoryLayout<UInt8>.alignment
        )
        pointer.initializeMemory(
            as: UInt8.self,
            repeating: 0,
            count: max(source.count, 1)
        )
        if !source.isEmpty {
            source.copyBytes(
                to: pointer.assumingMemoryBound(to: UInt8.self),
                count: source.count
            )
        }
    }

    deinit {
        productionC1WipeSensitiveResult(pointer, count: count)
        pointer.deallocate()
    }

    func snapshot() -> Data {
        lock.lock()
        defer { lock.unlock() }
        return Data(bytes: pointer, count: count)
    }

    func discard() {
        lock.lock()
        defer { lock.unlock() }
        guard !discarded else { return }
        productionC1WipeSensitiveResult(pointer, count: count)
        discarded = true
    }
}

/// Internal-only retained view used to prove that a suppressed confirmation's
/// owner was wiped. It deliberately creates a fresh snapshot on every read.
final class ProductionC1SensitiveResultTestingProbe: @unchecked Sendable {
    private let snapshotter: @Sendable () -> Data

    fileprivate init(snapshotter: @escaping @Sendable () -> Data) {
        self.snapshotter = snapshotter
    }

    func snapshot() -> Data { snapshotter() }
}

@inline(never)
private func productionC1WipeSensitiveResult(
    _ pointer: UnsafeMutableRawPointer,
    count: Int
) {
    guard count > 0 else { return }
    for offset in 0..<count {
        pointer.storeBytes(of: UInt8.zero, toByteOffset: offset, as: UInt8.self)
    }
}

/// Couples one production secure-session crypto state to the exact durable
/// authority lease that admitted it. Raw handshake and cipher objects never
/// escape this wrapper, so every observable result is fenced before and after
/// the underlying crypto operation.
final class ProductionC1ExactBoundSecureSession: @unchecked Sendable {
    private final class ResourceBox: @unchecked Sendable {
        private let lock = NSLock()
        private var handshake: ProductionSecureSessionHandshake?
        private var cipher: ProductionSecureSessionCipher?
        private var terminal = false
        private var terminalObserverInstalled = false
        private var terminalObserver: (@Sendable () -> Void)?

        func install(_ value: ProductionSecureSessionHandshake) throws {
            lock.lock()
            defer { lock.unlock() }
            guard !terminal else {
                value.invalidate()
                throw ProductionC1ExactBoundSecureSessionError.fenced
            }
            guard handshake == nil, cipher == nil else {
                value.invalidate()
                throw ProductionC1ExactBoundSecureSessionError.fenced
            }
            handshake = value
        }

        func withHandshake<T>(
            _ operation: (ProductionSecureSessionHandshake) throws -> T
        ) throws -> T {
            lock.lock()
            defer { lock.unlock() }
            guard !terminal else {
                throw ProductionC1ExactBoundSecureSessionError.fenced
            }
            guard cipher == nil else {
                throw ProductionC1ExactBoundSecureSessionError.alreadyActivated
            }
            guard let handshake else {
                throw ProductionC1ExactBoundSecureSessionError.handshakeUnavailable
            }
            return try operation(handshake)
        }

        func activate(nowMs: UInt64) throws {
            lock.lock()
            defer { lock.unlock() }
            guard !terminal else {
                throw ProductionC1ExactBoundSecureSessionError.fenced
            }
            guard cipher == nil else {
                throw ProductionC1ExactBoundSecureSessionError.alreadyActivated
            }
            guard let handshake else {
                throw ProductionC1ExactBoundSecureSessionError.handshakeUnavailable
            }
            cipher = try handshake.makeCipher(nowMs: nowMs)
        }

        func withCipher<T>(
            _ operation: (ProductionSecureSessionCipher) throws -> T
        ) throws -> T {
            lock.lock()
            defer { lock.unlock() }
            guard !terminal else {
                throw ProductionC1ExactBoundSecureSessionError.fenced
            }
            guard let cipher else {
                throw ProductionC1ExactBoundSecureSessionError.cipherUnavailable
            }
            return try operation(cipher)
        }

        func assertLive() throws {
            lock.lock()
            defer { lock.unlock() }
            guard !terminal else {
                throw ProductionC1ExactBoundSecureSessionError.fenced
            }
        }

        func installTerminalObserver(
            _ observer: @escaping @Sendable () -> Void
        ) -> Bool {
            lock.lock()
            guard !terminalObserverInstalled else {
                lock.unlock()
                return false
            }
            terminalObserverInstalled = true
            if terminal {
                lock.unlock()
                observer()
            } else {
                terminalObserver = observer
                lock.unlock()
            }
            return true
        }

        /// Idempotent and terminal. If publication races with this call, a
        /// subsequent install observes `terminal` and wipes the late resource.
        func invalidate() {
            lock.lock()
            guard !terminal else {
                lock.unlock()
                return
            }
            terminal = true
            handshake?.invalidate()
            cipher?.close()
            handshake = nil
            cipher = nil
            let observer = terminalObserver
            terminalObserver = nil
            lock.unlock()
            observer?()
        }
    }

    private let coordinator: ProductionC1ExactBoundStartCoordinator
    private let lease: ProductionC1ExactBoundStartLease
    private let resources: ResourceBox
    private let nowMs: @Sendable () -> UInt64
    private let beforePostFence: (@Sendable () async -> Void)?
    private let afterCloseInvalidateBeforeComplete: (@Sendable () async -> Void)?
    private let observeLocalConfirmationResult:
        (@Sendable (ProductionC1SensitiveResultTestingProbe) -> Void)?
    private let observeSealResult:
        (@Sendable (ProductionSecureSessionSealResult) -> Void)?
    private let observeOpenResult:
        (@Sendable (ProductionSecureSessionOpenResult) -> Void)?
    private let publicationLifecycle = ProductionC1TransportPublicationLifecycle()
    private let closeLock = NSLock()
    private var closeRequested = false

    private init(
        coordinator: ProductionC1ExactBoundStartCoordinator,
        lease: ProductionC1ExactBoundStartLease,
        resources: ResourceBox,
        nowMs: @escaping @Sendable () -> UInt64,
        beforePostFence: (@Sendable () async -> Void)? = nil,
        afterCloseInvalidateBeforeComplete: (@Sendable () async -> Void)? = nil,
        observeLocalConfirmationResult:
            (@Sendable (ProductionC1SensitiveResultTestingProbe) -> Void)? = nil,
        observeSealResult:
            (@Sendable (ProductionSecureSessionSealResult) -> Void)? = nil,
        observeOpenResult:
            (@Sendable (ProductionSecureSessionOpenResult) -> Void)? = nil
    ) {
        self.coordinator = coordinator
        self.lease = lease
        self.resources = resources
        self.nowMs = nowMs
        self.beforePostFence = beforePostFence
        self.afterCloseInvalidateBeforeComplete = afterCloseInvalidateBeforeComplete
        self.observeLocalConfirmationResult = observeLocalConfirmationResult
        self.observeSealResult = observeSealResult
        self.observeOpenResult = observeOpenResult
    }

    static func start(
        coordinator: ProductionC1ExactBoundStartCoordinator,
        request: ProductionC1ExactBoundStartRequest,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        nowMs: @escaping @Sendable () -> UInt64
    ) async throws -> ProductionC1ExactBoundSecureSession {
        try await startCore(
            coordinator: coordinator,
            request: request,
            keyScheduleBindingOverride: nil,
            localEphemeralKey: localEphemeralKey,
            nowMs: nowMs,
            afterDeriveBeforeInstall: nil,
            afterAbort: nil,
            beforePostFence: nil,
            afterCloseInvalidateBeforeComplete: nil,
            observeLocalConfirmationResult: nil,
            observeSealResult: nil,
            observeOpenResult: nil
        )
    }

    #if DEBUG
    static func startForTesting(
        coordinator: ProductionC1ExactBoundStartCoordinator,
        request: ProductionC1ExactBoundStartRequest,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        nowMs: @escaping @Sendable () -> UInt64,
        keyScheduleBindingOverride:
            VerifiedProductionC1CandidateP2PKeyScheduleBinding? = nil,
        afterDeriveBeforeInstall: (@Sendable () async -> Void)? = nil,
        afterAbort: (@Sendable () async -> Void)? = nil,
        beforePostFence: (@Sendable () async -> Void)? = nil,
        afterCloseInvalidateBeforeComplete: (@Sendable () async -> Void)? = nil,
        observeLocalConfirmationResult:
            (@Sendable (ProductionC1SensitiveResultTestingProbe) -> Void)? = nil,
        observeSealResult:
            (@Sendable (ProductionSecureSessionSealResult) -> Void)? = nil,
        observeOpenResult:
            (@Sendable (ProductionSecureSessionOpenResult) -> Void)? = nil
    ) async throws -> ProductionC1ExactBoundSecureSession {
        try await startCore(
            coordinator: coordinator,
            request: request,
            keyScheduleBindingOverride: keyScheduleBindingOverride,
            localEphemeralKey: localEphemeralKey,
            nowMs: nowMs,
            afterDeriveBeforeInstall: afterDeriveBeforeInstall,
            afterAbort: afterAbort,
            beforePostFence: beforePostFence,
            afterCloseInvalidateBeforeComplete: afterCloseInvalidateBeforeComplete,
            observeLocalConfirmationResult: observeLocalConfirmationResult,
            observeSealResult: observeSealResult,
            observeOpenResult: observeOpenResult
        )
    }
    #endif

    private static func startCore(
        coordinator: ProductionC1ExactBoundStartCoordinator,
        request: ProductionC1ExactBoundStartRequest,
        keyScheduleBindingOverride:
            VerifiedProductionC1CandidateP2PKeyScheduleBinding?,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        nowMs: @escaping @Sendable () -> UInt64,
        afterDeriveBeforeInstall: (@Sendable () async -> Void)?,
        afterAbort: (@Sendable () async -> Void)?,
        beforePostFence: (@Sendable () async -> Void)?,
        afterCloseInvalidateBeforeComplete: (@Sendable () async -> Void)?,
        observeLocalConfirmationResult:
            (@Sendable (ProductionC1SensitiveResultTestingProbe) -> Void)?,
        observeSealResult:
            (@Sendable (ProductionSecureSessionSealResult) -> Void)?,
        observeOpenResult:
            (@Sendable (ProductionSecureSessionOpenResult) -> Void)?
    ) async throws -> ProductionC1ExactBoundSecureSession {
        let permit = try await coordinator.acquirePublicationRead()
        do {
            let result = try await startHoldingPublicationRead(
                coordinator: coordinator,
                request: request,
                keyScheduleBindingOverride: keyScheduleBindingOverride,
                localEphemeralKey: localEphemeralKey,
                nowMs: nowMs,
                afterDeriveBeforeInstall: afterDeriveBeforeInstall,
                afterAbort: afterAbort,
                beforePostFence: beforePostFence,
                afterCloseInvalidateBeforeComplete:
                    afterCloseInvalidateBeforeComplete,
                observeLocalConfirmationResult: observeLocalConfirmationResult,
                observeSealResult: observeSealResult,
                observeOpenResult: observeOpenResult
            )
            await coordinator.releasePublicationRead(permit)
            return result
        } catch {
            await coordinator.releasePublicationRead(permit)
            throw error
        }
    }

    private static func startHoldingPublicationRead(
        coordinator: ProductionC1ExactBoundStartCoordinator,
        request: ProductionC1ExactBoundStartRequest,
        keyScheduleBindingOverride:
            VerifiedProductionC1CandidateP2PKeyScheduleBinding?,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        nowMs: @escaping @Sendable () -> UInt64,
        afterDeriveBeforeInstall: (@Sendable () async -> Void)?,
        afterAbort: (@Sendable () async -> Void)?,
        beforePostFence: (@Sendable () async -> Void)?,
        afterCloseInvalidateBeforeComplete: (@Sendable () async -> Void)?,
        observeLocalConfirmationResult:
            (@Sendable (ProductionC1SensitiveResultTestingProbe) -> Void)?,
        observeSealResult:
            (@Sendable (ProductionSecureSessionSealResult) -> Void)?,
        observeOpenResult:
            (@Sendable (ProductionSecureSessionOpenResult) -> Void)?
    ) async throws -> ProductionC1ExactBoundSecureSession {
        let keyScheduleBinding = keyScheduleBindingOverride
            ?? request.verifiedBinding.runtimeKeyScheduleBinding
        try validateExactBinding(keyScheduleBinding, request: request)
        let resources = ResourceBox()
        let handle = try await coordinator.admit(request)
        do {
            let lease = try await coordinator.begin(
                handle,
                request: request,
                start: { _ in
                    let handshake = try ProductionSecureSessionCrypto.deriveHandshake(
                        binding: keyScheduleBinding,
                        localEphemeralKey: localEphemeralKey,
                        nowMs: nowMs()
                    )
                    await afterDeriveBeforeInstall?()
                    try resources.install(handshake)
                },
                abort: { _ in
                    resources.invalidate()
                    await afterAbort?()
                }
            )
            let result = ProductionC1ExactBoundSecureSession(
                coordinator: coordinator,
                lease: lease,
                resources: resources,
                nowMs: nowMs,
                beforePostFence: beforePostFence,
                afterCloseInvalidateBeforeComplete: afterCloseInvalidateBeforeComplete,
                observeLocalConfirmationResult: observeLocalConfirmationResult,
                observeSealResult: observeSealResult,
                observeOpenResult: observeOpenResult
            )
            do {
                try Task.checkCancellation()
                try await coordinator.assertActive(lease)
                try Task.checkCancellation()
                return result
            } catch {
                resources.invalidate()
                try? await coordinator.cancel(lease)
                throw error
            }
        } catch {
            resources.invalidate()
            throw error
        }
    }

    func localConfirmation() async throws -> Data {
        let result = try await fenced(
            {
                let bytes = try resources.withHandshake {
                    try $0.localConfirmation(nowMs: nowMs())
                }
                return ProductionC1SensitiveResultData(copying: bytes)
            },
            observeProducedResult: { [observeLocalConfirmationResult] result in
                observeLocalConfirmationResult?(
                    ProductionC1SensitiveResultTestingProbe(
                        snapshotter: { result.snapshot() }
                    )
                )
            },
            discardSuppressedResult: { $0.discard() }
        )
        return result.snapshot()
    }

    func markLocalConfirmationSent(_ canonicalConfirmation: Data) async throws {
        try await fenced {
            try resources.withHandshake {
                try $0.markLocalConfirmationSent(
                    canonicalConfirmation,
                    nowMs: nowMs()
                )
            }
        }
    }

    func acceptPeerConfirmation(_ canonicalConfirmation: Data) async throws {
        try await fenced {
            try resources.withHandshake {
                try $0.acceptPeerConfirmation(
                    canonicalConfirmation,
                    nowMs: nowMs()
                )
            }
        }
    }

    func activate() async throws {
        try await fenced { try resources.activate(nowMs: nowMs()) }
    }

    func sealApplication(_ plaintext: Data) async throws
        -> ProductionSecureSessionSealResult
    {
        try await fenced(
            {
                try resources.withCipher {
                    try $0.sealApplication(plaintext, nowMs: nowMs())
                }
            },
            observeProducedResult: observeSealResult,
            discardSuppressedResult: {
                $0.discardSuppressedResultBytes()
            }
        )
    }

    func sealKeyUpdate() async throws -> ProductionSecureSessionSealResult {
        try await fenced(
            {
                try resources.withCipher { try $0.sealKeyUpdate(nowMs: nowMs()) }
            },
            observeProducedResult: observeSealResult,
            discardSuppressedResult: {
                $0.discardSuppressedResultBytes()
            }
        )
    }

    func open(_ record: ProductionSecureSessionEncryptedRecord) async throws
        -> ProductionSecureSessionOpenResult
    {
        try await fenced(
            {
                try resources.withCipher { try $0.open(record, nowMs: nowMs()) }
            },
            observeProducedResult: observeOpenResult,
            discardSuppressedResult: {
                $0.discardSuppressedResultBytes()
            }
        )
    }

    func open(canonicalRecord: Data) async throws
        -> ProductionSecureSessionOpenResult
    {
        try await fenced(
            {
                try resources.withCipher {
                    try $0.open(canonicalRecord: canonicalRecord, nowMs: nowMs())
                }
            },
            observeProducedResult: observeOpenResult,
            discardSuppressedResult: {
                $0.discardSuppressedResultBytes()
            }
        )
    }

    func installTerminalObserver(
        _ observer: @escaping @Sendable () -> Void
    ) -> Bool {
        resources.installTerminalObserver(observer)
    }

    func sendLocalConfirmation(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws {
        try await atomicPublication(
            produce: {
                let bytes = try resources.withHandshake {
                    try $0.localConfirmation(nowMs: nowMs())
                }
                return ProductionC1SensitiveResultData(copying: bytes)
            },
            observeProducedResult: { [observeLocalConfirmationResult] result in
                observeLocalConfirmationResult?(
                    ProductionC1SensitiveResultTestingProbe(
                        snapshotter: { result.snapshot() }
                    )
                )
            },
            publish: { result in
                var canonicalConfirmation = result.snapshot()
                defer { Self.wipeTemporaryData(&canonicalConfirmation) }
                try await send(canonicalConfirmation)
                try resources.withHandshake {
                    try $0.markLocalConfirmationSent(
                        canonicalConfirmation,
                        nowMs: nowMs()
                    )
                }
            },
            discardProducedResult: { $0.discard() }
        )
    }

    func sealApplicationAndSend(
        _ plaintext: Data,
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> ProductionC1TransportSealPublication {
        try await sealAndSend(
            produce: {
                try resources.withCipher {
                    try $0.sealApplication(plaintext, nowMs: nowMs())
                }
            },
            using: send
        )
    }

    func sealKeyUpdateAndSend(
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> ProductionC1TransportSealPublication {
        try await sealAndSend(
            produce: {
                try resources.withCipher { try $0.sealKeyUpdate(nowMs: nowMs()) }
            },
            using: send
        )
    }

    func openAndPublish<Published: Sendable>(
        _ canonicalRecord: Data,
        publishApplication: @escaping @Sendable (Data) async throws -> Published
    ) async throws -> ProductionC1TransportOpenPublication<Published> {
        try await atomicPublication(
            produce: {
                try resources.withCipher {
                    try $0.open(canonicalRecord: canonicalRecord, nowMs: nowMs())
                }
            },
            observeProducedResult: observeOpenResult,
            publish: { result in
                switch result.openedContent {
                case let .application(plaintext):
                    var publicationBytes = plaintext
                    defer { Self.wipeTemporaryData(&publicationBytes) }
                    let published = try await publishApplication(publicationBytes)
                    return .application(
                        published,
                        keyUpdateRequired: result.keyUpdateRequired,
                        terminalAfterRecord: result.terminalAfterRecord
                    )
                case let .keyUpdate(nextEpoch):
                    return .keyUpdate(
                        nextEpoch: nextEpoch,
                        terminalAfterRecord: result.terminalAfterRecord
                    )
                }
            },
            discardProducedResult: { $0.discardSuppressedResultBytes() }
        )
    }

    /// Local close is idempotent and completes the authority lease after first
    /// wiping the crypto state. A concurrent external fence may win; in that
    /// case the coordinator already ran the same terminal invalidation.
    func close() async {
        guard await publicationLifecycle.beginClose() else { return }
        guard beginClose() else {
            await publicationLifecycle.finishClose()
            return
        }
        resources.invalidate()
        await afterCloseInvalidateBeforeComplete?()
        try? await coordinator.complete(lease)
        await publicationLifecycle.finishClose()
    }

    private func beginClose() -> Bool {
        closeLock.lock()
        defer { closeLock.unlock() }
        guard !closeRequested else { return false }
        closeRequested = true
        return true
    }

    private func fenced<T>(
        _ operation: () throws -> T,
        observeProducedResult: ((T) -> Void)? = nil,
        discardSuppressedResult: (inout T) -> Void = { _ in }
    ) async throws -> T {
        let permit = try await coordinator.acquirePublicationRead()
        do {
            try Task.checkCancellation()
            try await coordinator.assertActive(lease)
            try resources.assertLive()
            try Task.checkCancellation()
            let result = try operation()
            observeProducedResult?(result)
            do {
                try Task.checkCancellation()
                await beforePostFence?()
                try Task.checkCancellation()
                try await coordinator.assertActive(lease)
                try resources.assertLive()
                try Task.checkCancellation()
                await coordinator.releasePublicationRead(permit)
                return result
            } catch {
                // The publication read permit remains held while the exact
                // would-be return storage is destroyed.
                var suppressedResult = result
                discardSuppressedResult(&suppressedResult)
                throw error
            }
        } catch {
            if Task.isCancelled || Self.isTerminalCryptoError(error) {
                resources.invalidate()
                try? await coordinator.cancel(lease)
            }
            await coordinator.releasePublicationRead(permit)
            throw error
        }
    }

    private func sealAndSend(
        produce: () throws -> ProductionSecureSessionSealResult,
        using send: @escaping @Sendable (Data) async throws -> Void
    ) async throws -> ProductionC1TransportSealPublication {
        try await atomicPublication(
            produce: produce,
            observeProducedResult: observeSealResult,
            publish: { result in
                var canonicalRecord = result.record.canonicalBytes()
                defer { Self.wipeTemporaryData(&canonicalRecord) }
                try await send(canonicalRecord)
                return ProductionC1TransportSealPublication(
                    keyUpdateRequired: result.keyUpdateRequired,
                    terminalAfterRecord: result.terminalAfterRecord
                )
            },
            discardProducedResult: { $0.discardSuppressedResultBytes() }
        )
    }

    /// Keeps the authority publication read permit across both crypto state
    /// consumption and the transport side effect. Once a result is produced,
    /// any send/publication failure or cancellation is terminal because the
    /// corresponding sequence/handshake transition cannot be safely replayed.
    private func atomicPublication<Produced, Published>(
        produce: () throws -> Produced,
        observeProducedResult: ((Produced) -> Void)? = nil,
        publish: (Produced) async throws -> Published,
        discardProducedResult: (inout Produced) -> Void
    ) async throws -> Published {
        try await publicationLifecycle.beginPublication()
        var publicationPermit: ProductionC1AuthorityPublicationReadPermit?
        var producedResult: Produced?
        var didProduceResult = false
        do {
            let permit = try await coordinator.acquirePublicationRead()
            publicationPermit = permit
            try Task.checkCancellation()
            try await coordinator.assertActive(lease)
            try resources.assertLive()
            try Task.checkCancellation()

            let produced = try produce()
            producedResult = produced
            didProduceResult = true
            observeProducedResult?(produced)
            let published = try await publish(produced)

            if var consumed = producedResult {
                discardProducedResult(&consumed)
                producedResult = nil
            }
            try Task.checkCancellation()
            await beforePostFence?()
            try Task.checkCancellation()
            try await coordinator.assertActive(lease)
            try resources.assertLive()
            try Task.checkCancellation()

            await coordinator.releasePublicationRead(permit)
            await publicationLifecycle.endPublication()
            return published
        } catch {
            let mustTerminalize = didProduceResult
                || Task.isCancelled
                || Self.isTerminalCryptoError(error)
            if var suppressed = producedResult {
                discardProducedResult(&suppressed)
                producedResult = nil
            }
            if mustTerminalize {
                await publicationLifecycle.requestTerminalFinish()
                resources.invalidate()
                try? await coordinator.cancel(lease)
            }
            if let publicationPermit {
                await coordinator.releasePublicationRead(publicationPermit)
            }
            await publicationLifecycle.endPublication()
            throw error
        }
    }

    private static func wipeTemporaryData(_ data: inout Data) {
        guard !data.isEmpty else { return }
        data.resetBytes(in: data.startIndex..<data.endIndex)
        data.removeAll(keepingCapacity: false)
    }

    private static func isTerminalCryptoError(_ error: Error) -> Bool {
        guard let error = error as? ProductionSecureSessionCryptoError else {
            return false
        }
        switch error {
        case .notYetValid, .expired, .timeRegression,
             .invalidConfirmation, .confirmationConflict,
             .sessionLimitExceeded, .sealFailed, .closed:
            return true
        default:
            return false
        }
    }

    private static func validateExactBinding(
        _ binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        request: ProductionC1ExactBoundStartRequest
    ) throws {
        let transcript = request.verifiedBinding.transcript
        let grant = request.verifiedBinding.grant.grantAuthorization
        let authorization = binding.grantAuthorization.authorization
        let token = request.token
        let transcriptDigest = SHA256.hash(data: transcript.canonicalBytes())
            .map { String(format: "%02x", $0) }
            .joined()
        let grantDigest: String
        do {
            grantDigest = try authorization.digestHex()
        } catch {
            throw ProductionC1ExactBoundSecureSessionError.exactBindingMismatch
        }
        guard binding.transcript == transcript,
              binding.grantAuthorization == grant,
              binding.securityContext == request.verifiedBinding.securityContext,
              // This resource is owned by the macOS runtime. The request's
              // endpoint binding is client-minted for outbound connection,
              // while the separately verifier-minted key-schedule view must
              // be the authorized runtime half of that same object-7/26 pair.
              binding.localRole == .runtime,
              authorization.initiatorRole == .client,
              authorization.connectorTargetRole == .runtime,
              binding.securityContext.digestHex() == authorization.securityContextDigest,
              transcriptDigest == token.transcriptDigest,
              grantDigest == token.grantAuthorizationDigest,
              binding.grantAuthorization.digestHex == token.grantAuthorizationDigest,
              transcript.sessionId == token.sessionID,
              authorization.sessionId == token.sessionID,
              authorization.pairAuthorityDigest == token.pairAuthorityDigest,
              authorization.effectiveNotBeforeMs == token.effectiveNotBeforeMs,
              authorization.expiresAtMs == token.expiresAtMs else {
            throw ProductionC1ExactBoundSecureSessionError.exactBindingMismatch
        }
    }
}
