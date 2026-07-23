import BridgeProtocol
import Foundation
import Network

enum LocalPeerFrameBodyMode: Equatable, Sendable {
    case protocolEnvelope
    case raw
}

final class LocalPeerFrameBodyModeGate: @unchecked Sendable {
    private let lock = NSLock()
    private let mode: LocalPeerFrameBodyMode
    private var terminal = false

    init(mode: LocalPeerFrameBodyMode) {
        self.mode = mode
    }

    func require(_ expected: LocalPeerFrameBodyMode) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard !terminal, mode == expected else {
            terminal = true
            return false
        }
        return true
    }
}

struct LocalPeerRawFrameBodyEncoder: Sendable {
    private let codec = ProtocolCodec()

    func encode(_ body: Data) throws -> Data {
        try codec.encodeLengthPrefixedBody(body)
    }
}

private enum LocalPeerReceiveMode: Sendable {
    case protocolEnvelope(LocalPeerMessageHandler)
    case raw(LocalPeerRawFrameBodyHandler)

    var connectionMode: LocalPeerFrameBodyMode {
        switch self {
        case .protocolEnvelope: .protocolEnvelope
        case .raw: .raw
        }
    }
}

/// Serializes frame submission through the transport completion boundary.
/// The next body is not handed to Network.framework until the preceding body
/// reports `contentProcessed`, so raw callers get an exact ordered completion
/// seam rather than enqueue-only acknowledgement.
final class LocalPeerOrderedFrameWriter: @unchecked Sendable {
    typealias Write = @Sendable (Data, @escaping @Sendable (Bool) -> Void) -> Void

    private struct Pending {
        let id = UUID()
        let frame: Data
        let completion: @Sendable (Bool) -> Void
    }

    private let queue: DispatchQueue
    private let write: Write
    private let closeTransport: @Sendable () -> Void
    private let maximumOutstandingFrames: Int
    private var pending: [Pending] = []
    private var inFlight: Pending?
    private var terminal = false

    init(
        label: String,
        maximumOutstandingFrames: Int = 32,
        write: @escaping Write,
        closeTransport: @escaping @Sendable () -> Void
    ) {
        precondition(maximumOutstandingFrames > 0)
        queue = DispatchQueue(label: label)
        self.maximumOutstandingFrames = maximumOutstandingFrames
        self.write = write
        self.closeTransport = closeTransport
    }

    func send(
        _ frame: Data,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        queue.async { [self] in
            guard !terminal else {
                completion(false)
                return
            }
            let outstanding = pending.count + (inFlight == nil ? 0 : 1)
            guard outstanding < maximumOutstandingFrames else {
                completion(false)
                terminalize(closeUnderlyingTransport: true)
                return
            }
            pending.append(Pending(frame: frame, completion: completion))
            startNextIfNeeded()
        }
    }

    func close() {
        queue.async { [self] in
            terminalize(closeUnderlyingTransport: true)
        }
    }

    private func startNextIfNeeded() {
        guard !terminal, inFlight == nil, !pending.isEmpty else { return }
        let next = pending.removeFirst()
        inFlight = next
        write(next.frame) { [weak self] succeeded in
            guard let self else {
                next.completion(false)
                return
            }
            self.queue.async {
                guard self.inFlight?.id == next.id else { return }
                self.inFlight = nil
                let accepted = succeeded && !self.terminal
                next.completion(accepted)
                if accepted {
                    self.startNextIfNeeded()
                } else if !self.terminal {
                    self.terminalize(closeUnderlyingTransport: true)
                }
            }
        }
    }

    private func terminalize(closeUnderlyingTransport: Bool) {
        guard !terminal else { return }
        terminal = true
        let rejected = (inFlight.map { [$0] } ?? []) + pending
        inFlight = nil
        pending.removeAll(keepingCapacity: false)
        rejected.forEach { $0.completion(false) }
        if closeUnderlyingTransport {
            closeTransport()
        }
    }
}

/// Small injected seam around an accepted connection. Production uses the
/// Network.framework adapter below; tests can prove receive/close behavior
/// without opening a socket.
protocol LocalPeerAcceptedRawConnectionIO: AnyObject, Sendable {
    func start(onTerminal: @escaping @Sendable () -> Void)
    func receiveExactly(
        _ byteCount: Int,
        completion: @escaping @Sendable (Data?) -> Void
    )
    func send(
        _ frame: Data,
        completion: @escaping @Sendable (Bool) -> Void
    )
    func cancel()
}

enum LocalPeerAcceptedRawListenerPolicy {
    static func parameters(port: UInt16) -> NWParameters {
        let parameters = NWParameters.tcp
        parameters.allowLocalEndpointReuse = true
        let nwPort = NWEndpoint.Port(rawValue: port) ?? .any
        let loopback = IPv4Address("127.0.0.1")!
        parameters.requiredLocalEndpoint = .hostPort(
            host: .ipv4(loopback),
            port: nwPort
        )
        return parameters
    }
}

typealias LocalPeerAcceptedRawNow = @Sendable () -> UInt64
typealias LocalPeerAcceptedRawSchedule = @Sendable (
    UInt64,
    @escaping @Sendable () -> Void
) -> Void

private func localPeerAcceptedRawNowMs() -> UInt64 {
    let milliseconds = Date().timeIntervalSince1970 * 1_000
    guard milliseconds > 0 else { return 0 }
    return milliseconds >= Double(UInt64.max)
        ? UInt64.max
        : UInt64(milliseconds)
}

private func localPeerAcceptedRawSchedule(
    afterNanoseconds delay: UInt64,
    action: @escaping @Sendable () -> Void
) {
    let clampedDelay = min(delay, UInt64(Int.max))
    DispatchQueue.global(qos: .utility).asyncAfter(
        deadline: .now() + .nanoseconds(Int(clampedDelay)),
        execute: action
    )
}

private final class LocalPeerNWAcceptedRawConnectionIO:
    LocalPeerAcceptedRawConnectionIO,
    @unchecked Sendable
{
    private let connection: NWConnection
    private let queue = DispatchQueue(
        label: "dev.localagentbridge.production-accepted-raw",
        qos: .userInitiated
    )
    private let lock = NSLock()
    private var started = false
    private var cancelled = false

    init(connection: NWConnection) {
        self.connection = connection
    }

    func start(onTerminal: @escaping @Sendable () -> Void) {
        let shouldStart = lock.withLock {
            guard !started else { return false }
            started = true
            return true
        }
        guard shouldStart else { return }
        connection.stateUpdateHandler = { state in
            switch state {
            case .failed, .cancelled:
                onTerminal()
            default:
                break
            }
        }
        connection.start(queue: queue)
    }

    func receiveExactly(
        _ byteCount: Int,
        completion: @escaping @Sendable (Data?) -> Void
    ) {
        connection.receive(
            minimumIncompleteLength: byteCount,
            maximumLength: byteCount
        ) { data, _, _, error in
            guard error == nil, let data, data.count == byteCount else {
                completion(nil)
                return
            }
            completion(data)
        }
    }

    func send(
        _ frame: Data,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        connection.send(content: frame, completion: .contentProcessed { error in
            completion(error == nil)
        })
    }

    func cancel() {
        let shouldCancel = lock.withLock {
            guard !cancelled else { return false }
            cancelled = true
            return true
        }
        if shouldCancel { connection.cancel() }
    }
}

private final class LocalPeerAcceptedRawCloseGate: @unchecked Sendable {
    private let lock = NSLock()
    private let closeUnderlying: @Sendable () -> Void
    private var closed = false

    init(closeUnderlying: @escaping @Sendable () -> Void) {
        self.closeUnderlying = closeUnderlying
    }

    func close() {
        let shouldClose = lock.withLock {
            guard !closed else { return false }
            closed = true
            return true
        }
        if shouldClose { closeUnderlying() }
    }
}

/// One accepted production connection. It deliberately implements only the
/// raw sink/session surfaces, so it cannot be routed to legacy envelope code.
/// No receive is registered until the manager-owned endpoint claim installs
/// its one raw handler.
final class LocalPeerAcceptedRawSession:
    RuntimeAcceptedRawSession,
    RuntimeRawFrameBodySink,
    @unchecked Sendable
{
    private enum State: Equatable {
        case waitingForHandler
        case receiving
        case terminal
    }

    public let connectionID: UUID
    public let routeDescriptor: RuntimeAcceptedRawRouteDescriptor

    private let io: any LocalPeerAcceptedRawConnectionIO
    private let writer: LocalPeerOrderedFrameWriter
    private let closeGate: LocalPeerAcceptedRawCloseGate
    private let schedule: LocalPeerAcceptedRawSchedule
    private let lock = NSLock()
    private var state = State.waitingForHandler
    private var connectionStarted = false
    private var claimTaken = false
    private var receiveOutstanding = false
    private var handler: (@Sendable (Data) async -> Void)?
    private var onTerminal: (@Sendable (UUID) -> Void)?

    init(
        connectionID: UUID = UUID(),
        routeDescriptor: RuntimeAcceptedRawRouteDescriptor,
        io: any LocalPeerAcceptedRawConnectionIO,
        schedule: @escaping LocalPeerAcceptedRawSchedule,
        onTerminal: @escaping @Sendable (UUID) -> Void
    ) {
        self.connectionID = connectionID
        self.routeDescriptor = routeDescriptor
        self.io = io
        self.schedule = schedule
        self.onTerminal = onTerminal
        let closeGate = LocalPeerAcceptedRawCloseGate { [io] in io.cancel() }
        self.closeGate = closeGate
        writer = LocalPeerOrderedFrameWriter(
            label: "dev.localagentbridge.production-accepted-send-\(connectionID.uuidString)",
            maximumOutstandingFrames: 32,
            write: { [io] frame, completion in
                io.send(frame, completion: completion)
            },
            closeTransport: { [closeGate] in closeGate.close() }
        )
    }

    var isOpen: Bool {
        lock.withLock { state != .terminal }
    }

    @discardableResult
    func startConnection() -> Bool {
        let shouldStart = lock.withLock {
            guard state != .terminal, !connectionStarted else { return false }
            connectionStarted = true
            return true
        }
        guard shouldStart else { return false }
        io.start { [weak self] in self?.close() }
        return isOpen
    }

    func startHandlerInstallationDeadline(afterNanoseconds delay: UInt64) {
        guard delay > 0 else {
            closeIfWaitingForHandler()
            return
        }
        schedule(delay) { [weak self] in
            self?.closeIfWaitingForHandler()
        }
    }

    @_spi(ProductionRawEndpointOwnership)
    @discardableResult
    public func takeRawEndpointClaim() -> RuntimeAcceptedRawEndpointClaim? {
        let canClaim = lock.withLock {
            guard state != .terminal, connectionStarted, !claimTaken else {
                return false
            }
            claimTaken = true
            return true
        }
        guard canClaim else { return nil }
        return RuntimeAcceptedRawEndpointClaim(
            rawSink: self,
            routeDescriptor: routeDescriptor,
            installHandler: { [weak self] handler in
                self?.installRawFrameBodyHandler(handler) ?? false
            }
        )
    }

    public func sendRawFrameBody(
        _ body: Data,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        guard isOpen else {
            completion(false)
            return
        }
        do {
            writer.send(
                try LocalPeerRawFrameBodyEncoder().encode(body),
                completion: completion
            )
        } catch {
            completion(false)
            close()
        }
    }

    public func close() {
        let terminalHandler: (@Sendable (UUID) -> Void)? = lock.withLock {
            guard state != .terminal else { return nil }
            state = .terminal
            receiveOutstanding = false
            handler = nil
            let terminalHandler = onTerminal
            onTerminal = nil
            return terminalHandler
        }
        guard let terminalHandler else { return }
        // Cancel synchronously so a blocked receive is interrupted before the
        // disconnect callback can start replacement work. The writer shares
        // the same idempotent close gate and drains send completions once.
        closeGate.close()
        writer.close()
        terminalHandler(connectionID)
    }

    private func installRawFrameBodyHandler(
        _ handler: @escaping @Sendable (Data) async -> Void
    ) -> Bool {
        let installed = lock.withLock {
            guard state == .waitingForHandler,
                  connectionStarted,
                  claimTaken,
                  self.handler == nil else {
                return false
            }
            self.handler = handler
            state = .receiving
            return true
        }
        guard installed else { return false }
        requestNextLength()
        return true
    }

    private func closeIfWaitingForHandler() {
        let isWaiting = lock.withLock { state == .waitingForHandler }
        if isWaiting { close() }
    }

    private func requestNextLength() {
        let shouldReceive = lock.withLock {
            guard state == .receiving,
                  handler != nil,
                  !receiveOutstanding else {
                return false
            }
            receiveOutstanding = true
            return true
        }
        guard shouldReceive else { return }
        io.receiveExactly(4) { [weak self] data in
            self?.didReceiveLength(data)
        }
    }

    private func didReceiveLength(_ data: Data?) {
        let mayProcess = lock.withLock {
            guard state == .receiving, receiveOutstanding else { return false }
            receiveOutstanding = false
            return true
        }
        guard mayProcess,
              let data,
              data.count == 4 else {
            if mayProcess { close() }
            return
        }
        let bodyLength = data.reduce(0) { partial, byte in
            (partial << 8) | Int(byte)
        }
        guard bodyLength > 0, bodyLength <= ProtocolCodec.maxFrameBytes else {
            close()
            return
        }
        requestBody(byteCount: bodyLength)
    }

    private func requestBody(byteCount: Int) {
        let shouldReceive = lock.withLock {
            guard state == .receiving,
                  handler != nil,
                  !receiveOutstanding else {
                return false
            }
            receiveOutstanding = true
            return true
        }
        guard shouldReceive else { return }
        io.receiveExactly(byteCount) { [weak self] data in
            self?.didReceiveBody(data, expectedByteCount: byteCount)
        }
    }

    private func didReceiveBody(_ data: Data?, expectedByteCount: Int) {
        let currentHandler: (@Sendable (Data) async -> Void)? = lock.withLock {
            guard state == .receiving, receiveOutstanding else { return nil }
            receiveOutstanding = false
            guard let data,
                  data.count == expectedByteCount,
                  let handler else {
                return nil
            }
            return handler
        }
        guard let data,
              data.count == expectedByteCount,
              let currentHandler else {
            close()
            return
        }
        Task { [weak self] in
            await currentHandler(data)
            self?.requestNextLength()
        }
    }
}

/// Bounded one-slot authorization and accepted-session owner. This object is
/// also the injected unit-test seam for G1b-A; it opens no socket itself.
final class LocalPeerAcceptedRawSessionAcceptor: @unchecked Sendable {
    typealias AcceptedHandler = @Sendable (any RuntimeAcceptedRawSession) -> Void
    typealias DisconnectHandler = @Sendable (UUID) -> Void
    typealias StopDeliveryWaitHandler = @Sendable () -> Void

    private struct PendingAuthorization {
        let generationID: UUID
        let authorization: RuntimeAcceptedRawSessionAuthorization
    }

    static let maximumPendingAuthorizationNanoseconds: UInt64 =
        15_000_000_000
    static let maximumHandlerInstallationNanoseconds: UInt64 =
        15_000_000_000

    private let lock = NSLock()
    // Delivery is a synchronous revocation boundary. An external stop waits
    // for an in-flight callback to return, while a callback may synchronously
    // stop the acceptor without deadlocking on itself.
    private let deliveryLock = NSRecursiveLock()
    private let onAccepted: AcceptedHandler
    private let onDisconnect: DisconnectHandler
    private let nowMs: LocalPeerAcceptedRawNow
    private let schedule: LocalPeerAcceptedRawSchedule
    private let onStopWaitingForDelivery: StopDeliveryWaitHandler
    private var active = true
    private var pendingAuthorization: PendingAuthorization?
    private var sessions: [UUID: LocalPeerAcceptedRawSession] = [:]

    init(
        onAccepted: @escaping AcceptedHandler,
        onDisconnect: @escaping DisconnectHandler,
        nowMs: @escaping LocalPeerAcceptedRawNow = {
            localPeerAcceptedRawNowMs()
        },
        schedule: @escaping LocalPeerAcceptedRawSchedule = { delay, action in
            localPeerAcceptedRawSchedule(
                afterNanoseconds: delay,
                action: action
            )
        },
        onStopWaitingForDelivery: @escaping StopDeliveryWaitHandler = {}
    ) {
        self.onAccepted = onAccepted
        self.onDisconnect = onDisconnect
        self.nowMs = nowMs
        self.schedule = schedule
        self.onStopWaitingForDelivery = onStopWaitingForDelivery
    }

    @discardableResult
    func supply(
        _ authorization: RuntimeAcceptedRawSessionAuthorization
    ) -> Bool {
        guard let remainingValidity = authorization
            .remainingValidityNanoseconds(nowMs: nowMs()) else {
            authorization.close()
            return false
        }
        let generationID = UUID()
        let accepted = lock.withLock {
            guard active, pendingAuthorization == nil else { return false }
            pendingAuthorization = PendingAuthorization(
                generationID: generationID,
                authorization: authorization
            )
            return true
        }
        guard accepted else {
            authorization.close()
            return false
        }
        schedule(
            min(
                remainingValidity,
                Self.maximumPendingAuthorizationNanoseconds
            )
        ) { [weak self] in
            self?.expirePendingAuthorization(generationID: generationID)
        }
        return accepted
    }

    @discardableResult
    func accept(_ io: any LocalPeerAcceptedRawConnectionIO) -> Bool {
        let pending: PendingAuthorization? = lock.withLock {
            guard active else { return nil }
            let pending = pendingAuthorization
            pendingAuthorization = nil
            return pending
        }
        let acceptedAtMs = nowMs()
        guard let pending,
              let descriptor = pending.authorization
                .takeRouteDescriptorForAcceptedConnection(nowMs: acceptedAtMs)
        else {
            io.cancel()
            return false
        }
        let remainingValidity = Self.remainingValidityNanoseconds(
            expiresAtMs: descriptor.expiresAtMs,
            nowMs: acceptedAtMs
        )
        guard remainingValidity > 0 else {
            io.cancel()
            return false
        }

        let session = LocalPeerAcceptedRawSession(
            routeDescriptor: descriptor,
            io: io,
            schedule: schedule,
            onTerminal: { [weak self] connectionID in
                self?.remove(connectionID: connectionID)
            }
        )
        let inserted = lock.withLock {
            guard active, sessions[session.connectionID] == nil else {
                return false
            }
            sessions[session.connectionID] = session
            return true
        }
        guard inserted else {
            session.close()
            return false
        }
        guard session.startConnection() else {
            session.close()
            return false
        }
        session.startHandlerInstallationDeadline(
            afterNanoseconds: min(
                remainingValidity,
                Self.maximumHandlerInstallationNanoseconds
            )
        )
        guard deliverIfActive(session) else {
            session.close()
            return false
        }
        return true
    }

    func stop() {
        // Publish the stop request before waiting for a callback lease. This
        // prevents later deliveries from overtaking a waiting stop. Cleanup is
        // claimed only after acquiring the recursive delivery lock so a stop
        // invoked by the callback itself can close synchronously.
        lock.withLock { active = false }
        if !deliveryLock.try() {
            onStopWaitingForDelivery()
            deliveryLock.lock()
        }
        let snapshot: (
            RuntimeAcceptedRawSessionAuthorization?,
            [LocalPeerAcceptedRawSession]
        ) = lock.withLock {
            let pendingAuthorization = self.pendingAuthorization?.authorization
            self.pendingAuthorization = nil
            let sessions = Array(self.sessions.values)
            self.sessions.removeAll(keepingCapacity: false)
            return (pendingAuthorization, sessions)
        }
        deliveryLock.unlock()
        snapshot.0?.close()
        snapshot.1.forEach { session in
            session.close()
            onDisconnect(session.connectionID)
        }
    }

    private func deliverIfActive(
        _ session: LocalPeerAcceptedRawSession
    ) -> Bool {
        deliveryLock.lock()
        defer { deliveryLock.unlock() }
        let mayDeliver = lock.withLock {
            active && sessions[session.connectionID] === session
        }
        guard mayDeliver else { return false }
        onAccepted(session)
        // A synchronous re-entrant stop is allowed through the recursive
        // delivery lock, but makes this acceptance terminal.
        return lock.withLock { active }
    }

    private func remove(connectionID: UUID) {
        let removed = lock.withLock {
            sessions.removeValue(forKey: connectionID) != nil
        }
        if removed { onDisconnect(connectionID) }
    }

    private func expirePendingAuthorization(generationID: UUID) {
        let authorization: RuntimeAcceptedRawSessionAuthorization? = lock
            .withLock {
                guard pendingAuthorization?.generationID == generationID else {
                    return nil
                }
                let authorization = pendingAuthorization?.authorization
                pendingAuthorization = nil
                return authorization
            }
        authorization?.close()
    }

    private static func remainingValidityNanoseconds(
        expiresAtMs: UInt64,
        nowMs: UInt64
    ) -> UInt64 {
        guard nowMs < expiresAtMs else { return 0 }
        let remainingMs = expiresAtMs - nowMs
        let (nanoseconds, overflow) = remainingMs.multipliedReportingOverflow(
            by: 1_000_000
        )
        return overflow ? UInt64.max : nanoseconds
    }
}

public enum PeerServerStatus: Equatable, Sendable {
    case stopped
    case listening(port: UInt16)
    case failed(String)
}

public protocol RuntimeMessageSink: Sendable {
    var connectionID: UUID { get }
    var transportSecurityContext: TransportSecurityContext? { get }

    func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result

    func send(_ envelope: ProtocolEnvelope)
    func send(
        _ envelope: ProtocolEnvelope,
        completion: @escaping @Sendable (Bool) -> Void
    )
    func sendAndWait(_ envelope: ProtocolEnvelope) async -> Bool
    func close()
}

public extension RuntimeMessageSink {
    var transportSecurityContext: TransportSecurityContext? { nil }

    func send(
        _ envelope: ProtocolEnvelope,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        send(envelope)
        completion(true)
    }

    func sendAndWait(_ envelope: ProtocolEnvelope) async -> Bool {
        await withCheckedContinuation { continuation in
            send(envelope) { succeeded in
                continuation.resume(returning: succeeded)
            }
        }
    }
}

public typealias LocalPeerMessageHandler = @Sendable (ProtocolEnvelope, any RuntimeMessageSink) -> Void

public final class LocalPeerServer: RuntimeTransport, RuntimeRawFrameBodyTransport,
    RuntimeAcceptedRawSessionTransport, RuntimeDisconnectReporting,
    @unchecked Sendable
{
    private var listener: NWListener?
    private let codec = ProtocolCodec()
    private let lock = NSLock()
    private var connections: [UUID: LocalPeerConnection] = [:]
    private var acceptedRawAcceptor: LocalPeerAcceptedRawSessionAcceptor?

    public private(set) var status: PeerServerStatus = .stopped
    public var onDisconnect: (@Sendable (UUID) -> Void)?

    public init() {}

    public func start(port: UInt16 = 43170, onMessage: @escaping LocalPeerMessageHandler) {
        startListener(port: port, receiveMode: .protocolEnvelope(onMessage))
    }

    public func startRaw(
        port: UInt16 = 43170,
        onFrameBody: @escaping LocalPeerRawFrameBodyHandler
    ) {
        startListener(port: port, receiveMode: .raw(onFrameBody))
    }

    public func startAcceptedRaw(
        port: UInt16 = 43170,
        onAcceptedSession: @escaping @Sendable (
            any RuntimeAcceptedRawSession
        ) -> Void
    ) {
        stop()
        let acceptor = LocalPeerAcceptedRawSessionAcceptor(
            onAccepted: onAcceptedSession,
            onDisconnect: { [weak self] connectionID in
                self?.onDisconnect?(connectionID)
            }
        )
        do {
            let parameters = LocalPeerAcceptedRawListenerPolicy.parameters(
                port: port
            )
            let listener = try NWListener(using: parameters)

            listener.newConnectionHandler = { connection in
                let io = LocalPeerNWAcceptedRawConnectionIO(connection: connection)
                _ = acceptor.accept(io)
            }
            listener.stateUpdateHandler = { [weak self, weak acceptor] state in
                guard case .failed(let error) = state,
                      let acceptor else {
                    return
                }
                self?.failAcceptedRawListener(
                    acceptor,
                    message: error.localizedDescription
                )
            }

            self.listener = listener
            lock.withLock { acceptedRawAcceptor = acceptor }
            listener.start(queue: .global(qos: .userInitiated))
            status = .listening(port: port)
        } catch {
            acceptor.stop()
            status = .failed(error.localizedDescription)
        }
    }

    @discardableResult
    public func supplyAcceptedRawSessionAuthorization(
        _ authorization: RuntimeAcceptedRawSessionAuthorization
    ) -> Bool {
        guard let acceptor = lock.withLock({ acceptedRawAcceptor }) else {
            authorization.close()
            return false
        }
        return acceptor.supply(authorization)
    }

    private func startListener(port: UInt16, receiveMode: LocalPeerReceiveMode) {
        do {
            stop()

            let parameters = NWParameters.tcp
            parameters.allowLocalEndpointReuse = true
            let nwPort = NWEndpoint.Port(rawValue: port) ?? .any
            let listener = try NWListener(using: parameters, on: nwPort)

            listener.newConnectionHandler = { [weak self, codec] connection in
                guard let self else {
                    connection.cancel()
                    return
                }

                let peer = LocalPeerConnection(
                    connection: connection,
                    codec: codec,
                    mode: receiveMode.connectionMode
                )
                Self.debugLog("accepted peer \(peer.id)")
                self.insert(peer)

                connection.stateUpdateHandler = { [weak self, weak peer] state in
                    switch state {
                    case .failed(let error):
                        Self.debugLog("peer failed \(peer?.id.uuidString ?? "unknown"): \(error)")
                        if let peer {
                            // A state transition can arrive independently of a
                            // contentProcessed callback. Close the ordered
                            // writer before dropping the server's last strong
                            // reference so every in-flight and queued sender is
                            // completed exactly once with failure.
                            peer.close()
                            self?.remove(peer)
                        }
                    case .cancelled:
                        Self.debugLog("peer cancelled \(peer?.id.uuidString ?? "unknown")")
                        if let peer {
                            peer.close()
                            self?.remove(peer)
                        }
                    default:
                        break
                    }
                }

                connection.start(queue: .global(qos: .userInitiated))
                Self.receiveNextFrame(
                    connection: connection,
                    peer: peer,
                    codec: codec,
                    receiveMode: receiveMode
                )
            }

            listener.stateUpdateHandler = { [weak self] state in
                if case .failed(let error) = state {
                    self?.status = .failed(error.localizedDescription)
                }
            }

            listener.start(queue: .global(qos: .userInitiated))
            self.listener = listener
            self.status = .listening(port: port)
        } catch {
            status = .failed(error.localizedDescription)
        }
    }

    public func stop() {
        listener?.cancel()
        listener = nil
        let snapshot: (
            [LocalPeerConnection],
            LocalPeerAcceptedRawSessionAcceptor?
        ) = lock.withLock {
            let values = Array(connections.values)
            connections.removeAll()
            let acceptedRawAcceptor = self.acceptedRawAcceptor
            self.acceptedRawAcceptor = nil
            return (values, acceptedRawAcceptor)
        }
        snapshot.1?.stop()
        snapshot.0.forEach { peer in
            onDisconnect?(peer.id)
            peer.close()
        }
        status = .stopped
    }

    private func insert(_ peer: LocalPeerConnection) {
        lock.withLock {
            connections[peer.id] = peer
        }
    }

    private func remove(_ peer: LocalPeerConnection) {
        let removed = lock.withLock {
            connections.removeValue(forKey: peer.id)
        }
        if removed != nil {
            onDisconnect?(peer.id)
        }
    }

    private func failAcceptedRawListener(
        _ expectedAcceptor: LocalPeerAcceptedRawSessionAcceptor,
        message: String
    ) {
        let shouldStop = lock.withLock {
            guard acceptedRawAcceptor === expectedAcceptor else { return false }
            acceptedRawAcceptor = nil
            listener = nil
            return true
        }
        guard shouldStop else { return }
        expectedAcceptor.stop()
        status = .failed(message)
    }

    private static func receiveNextFrame(
        connection: NWConnection,
        peer: LocalPeerConnection,
        codec: ProtocolCodec,
        receiveMode: LocalPeerReceiveMode
    ) {
        connection.receive(minimumIncompleteLength: 4, maximumLength: 4) { lengthData, _, _, error in
            guard error == nil, let lengthData, lengthData.count == 4 else {
                debugLog("closing \(peer.id): failed to read frame length error=\(String(describing: error)) bytes=\(lengthData?.count ?? 0)")
                peer.close()
                return
            }

            let length = lengthData.withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
            let bodyLength = Int(length)
            guard bodyLength > 0 && bodyLength <= ProtocolCodec.maxFrameBytes else {
                debugLog("closing \(peer.id): invalid frame length \(bodyLength)")
                peer.close()
                return
            }
            debugLog("peer \(peer.id) frame length \(bodyLength)")

            connection.receive(minimumIncompleteLength: bodyLength, maximumLength: bodyLength) { body, _, _, error in
                guard error == nil, let body, body.count == bodyLength else {
                    debugLog("closing \(peer.id): failed to read frame body error=\(String(describing: error)) bytes=\(body?.count ?? 0)")
                    peer.close()
                    return
                }

                switch receiveMode {
                case .raw(let onFrameBody):
                    // The next read starts only after the raw owner finishes
                    // consuming this body. This supplies backpressure and one
                    // strictly ordered inbound body at a time.
                    Task {
                        await onFrameBody(body, peer)
                        receiveNextFrame(
                            connection: connection,
                            peer: peer,
                            codec: codec,
                            receiveMode: receiveMode
                        )
                    }
                case .protocolEnvelope(let onMessage):
                    do {
                        let envelope = try codec.decodeEnvelope(body)
                        debugLog("peer \(peer.id) decoded type=\(envelope.type) request_id=\(envelope.requestID)")
                        onMessage(envelope, peer)
                        receiveNextFrame(
                            connection: connection,
                            peer: peer,
                            codec: codec,
                            receiveMode: receiveMode
                        )
                    } catch {
                        debugLog("peer \(peer.id) decode error: \(error.localizedDescription)")
                        peer.send(ProtocolEnvelope(
                            type: MessageType.error,
                            payload: [
                                "code": .string("invalid_payload"),
                                "message": .string(error.localizedDescription),
                                "retryable": .bool(false)
                            ]
                        ))
                        receiveNextFrame(
                            connection: connection,
                            peer: peer,
                            codec: codec,
                            receiveMode: receiveMode
                        )
                    }
                }
            }
        }
    }

    private static func debugLog(_ message: String) {
        guard ProcessInfo.processInfo.environment["LOCAL_AGENT_BRIDGE_DEBUG_TRANSPORT"] == "1" else {
            return
        }
        print("[transport] \(message)")
    }
}

public final class LocalPeerConnection: RuntimeMessageSink, RuntimeRawFrameBodySink,
    @unchecked Sendable
{
    public let id = UUID()
    public var connectionID: UUID { id }
    public var transportSecurityContext: TransportSecurityContext? { nil }

    public func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result {
        try operation(nil)
    }

    private let connection: NWConnection
    private let codec: ProtocolCodec
    private let modeGate: LocalPeerFrameBodyModeGate
    private let writer: LocalPeerOrderedFrameWriter

    init(
        connection: NWConnection,
        codec: ProtocolCodec,
        mode: LocalPeerFrameBodyMode = .protocolEnvelope
    ) {
        self.connection = connection
        self.codec = codec
        modeGate = LocalPeerFrameBodyModeGate(mode: mode)
        let writerID = UUID().uuidString
        writer = LocalPeerOrderedFrameWriter(
            label: "dev.localagentbridge.local-peer-send-\(writerID)",
            maximumOutstandingFrames: mode == .raw ? 32 : 256,
            write: { [connection] frame, completion in
                connection.send(content: frame, completion: .contentProcessed { error in
                    completion(error == nil)
                })
            },
            closeTransport: { [connection] in connection.cancel() }
        )
    }

    public func send(_ envelope: ProtocolEnvelope) {
        send(envelope) { _ in }
    }

    public func send(
        _ envelope: ProtocolEnvelope,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        guard requireMode(.protocolEnvelope, completion: completion) else { return }
        do {
            writer.send(try codec.encodeFrame(envelope), completion: completion)
        } catch {
            failClosed(completion: completion)
        }
    }

    public func sendRawFrameBody(
        _ body: Data,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        guard requireMode(.raw, completion: completion) else { return }
        do {
            writer.send(try LocalPeerRawFrameBodyEncoder().encode(body), completion: completion)
        } catch {
            failClosed(completion: completion)
        }
    }

    public func sendAndWait(_ envelope: ProtocolEnvelope) async -> Bool {
        await withCheckedContinuation { continuation in
            send(envelope) { succeeded in
                continuation.resume(returning: succeeded)
            }
        }
    }

    public func close() {
        writer.close()
        connection.cancel()
    }

    private func requireMode(
        _ expected: LocalPeerFrameBodyMode,
        completion: @escaping @Sendable (Bool) -> Void
    ) -> Bool {
        guard modeGate.require(expected) else {
            failClosed(completion: completion)
            return false
        }
        return true
    }

    private func failClosed(completion: @escaping @Sendable (Bool) -> Void) {
        writer.close()
        connection.cancel()
        completion(false)
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
