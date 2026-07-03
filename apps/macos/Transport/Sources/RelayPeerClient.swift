import BridgeProtocol
import Foundation
import Network

public struct RelayPeerConfiguration: Equatable, Sendable {
    public static let defaultControlLineTimeout: TimeInterval = 45

    public var host: String
    public var port: UInt16
    public var relayID: String
    public var relaySecret: String?
    public var relayNonce: String?
    public var reconnectDelay: TimeInterval
    public var controlLineTimeout: TimeInterval

    public init(
        host: String,
        port: UInt16,
        relayID: String,
        relaySecret: String? = nil,
        relayNonce: String? = nil,
        reconnectDelay: TimeInterval = 2
    ) {
        self.init(
            host: host,
            port: port,
            relayID: relayID,
            relaySecret: relaySecret,
            relayNonce: relayNonce,
            reconnectDelay: reconnectDelay,
            controlLineTimeout: Self.defaultControlLineTimeout
        )
    }

    public init(
        host: String,
        port: UInt16,
        relayID: String,
        relaySecret: String? = nil,
        relayNonce: String? = nil,
        reconnectDelay: TimeInterval = 2,
        controlLineTimeout: TimeInterval
    ) {
        precondition(!host.isEmpty, "Relay host must not be empty")
        precondition(!relayID.isEmpty, "Relay id must not be empty")
        precondition(relayNonce?.isEmpty != true, "Relay nonce must not be empty")
        precondition(controlLineTimeout > 0, "Relay control-line timeout must be positive")
        self.host = host
        self.port = port
        self.relayID = relayID
        self.relaySecret = relaySecret
        self.relayNonce = relayNonce
        self.reconnectDelay = reconnectDelay
        self.controlLineTimeout = controlLineTimeout
    }

    public func withRelayNonce(_ relayNonce: String?) -> RelayPeerConfiguration {
        RelayPeerConfiguration(
            host: host,
            port: port,
            relayID: relayID,
            relaySecret: relaySecret,
            relayNonce: relayNonce?.isEmpty == false ? relayNonce : nil,
            reconnectDelay: reconnectDelay,
            controlLineTimeout: controlLineTimeout
        )
    }
}

public enum RelayPeerStatus: Equatable, Sendable {
    case stopped
    case connecting
    case waitingForPeer
    case ready
    case reconnecting(String?)
    case failed(String)
}

public protocol RelayPeerTransport: AnyObject, Sendable {
    func start(
        configuration: RelayPeerConfiguration,
        onStatusChange: (@Sendable (RelayPeerStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    )

    func stop()
}

public final class RelayPeerClient: RelayPeerTransport, @unchecked Sendable {
    private let codec = ProtocolCodec()
    private let lock = NSLock()
    private var connection: NWConnection?
    private var connectionID: UUID?
    private var isRunning = false
    private var reconnectWorkItem: DispatchWorkItem?
    private var status: RelayPeerStatus = .stopped
    private var statusHandler: (@Sendable (RelayPeerStatus) -> Void)?
    public var onDisconnect: (@Sendable (UUID) -> Void)?

    public init() {}

    public func start(
        configuration: RelayPeerConfiguration,
        onStatusChange: (@Sendable (RelayPeerStatus) -> Void)? = nil,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        stop()
        lock.withLock {
            isRunning = true
            statusHandler = onStatusChange
        }
        updateStatus(.connecting)
        connect(configuration: configuration, onMessage: onMessage)
    }

    public func stop() {
        let result = lock.withLock {
            isRunning = false
            reconnectWorkItem?.cancel()
            reconnectWorkItem = nil
            let current = connection
            let consumedConnectionID = connectionID
            connection = nil
            connectionID = nil
            return (connection: current, connectionID: consumedConnectionID, handler: statusHandler)
        }
        if let connectionID = result.connectionID {
            onDisconnect?(connectionID)
        }
        result.connection?.cancel()
        updateStatus(.stopped, handler: result.handler)
    }

    public func retireAfterCurrentConnection() {
        let shouldReportStopped = lock.withLock {
            isRunning = false
            reconnectWorkItem?.cancel()
            reconnectWorkItem = nil
            return connection == nil
        }
        if shouldReportStopped {
            updateStatus(.stopped)
        }
    }

    private func connect(
        configuration: RelayPeerConfiguration,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        let endpointHost = NWEndpoint.Host(configuration.host)
        let endpointPort = NWEndpoint.Port(rawValue: configuration.port) ?? .any
        let connection = NWConnection(host: endpointHost, port: endpointPort, using: .tcp)
        let sink = RelayPeerConnection(
            connection: connection,
            codec: codec,
            relaySecret: configuration.relaySecret,
            relayNonce: configuration.relayNonce
        )

        lock.withLock {
            self.connection = connection
            self.connectionID = sink.id
        }

        connection.stateUpdateHandler = { [weak self, sink] state in
            switch state {
            case .ready:
                guard let self else { return }
                sink.sendRelayHandshake(relayID: configuration.relayID)
                Self.receiveRegistrationStatus(
                    connection: connection,
                    timeout: configuration.controlLineTimeout
                ) { result in
                    switch result {
                    case .status(.registered):
                        self.updateStatus(.waitingForPeer)
                        Self.receiveRegistrationStatus(
                            connection: connection,
                            timeout: configuration.controlLineTimeout
                        ) { result in
                            guard result == .status(.ready) else {
                                switch result {
                                case .timedOut:
                                    self.updateStatus(.failed("Relay ready line timed out after registration."))
                                default:
                                    self.updateStatus(.failed("Relay did not return ready after registration."))
                                }
                                connection.cancel()
                                return
                            }
                            self.updateStatus(.ready)
                            Self.receiveNextFrame(
                                connection: connection,
                                peer: sink,
                                onMessage: onMessage
                            )
                        }
                    case .status(.ready):
                        self.updateStatus(.ready)
                        Self.receiveNextFrame(
                            connection: connection,
                            peer: sink,
                            onMessage: onMessage
                        )
                    case .invalid:
                        self.updateStatus(.failed("Relay did not accept runtime registration."))
                        connection.cancel()
                    case .timedOut:
                        self.updateStatus(.failed("Relay registration timed out before ready."))
                        connection.cancel()
                    }
                }
            case .waiting(let error):
                self?.updateStatus(.failed(error.localizedDescription))
            case .failed(let error):
                self?.updateStatus(.failed(error.localizedDescription))
                self?.notifyDisconnectIfCurrentConnection(sink.id)
                self?.scheduleReconnect(
                    configuration: configuration,
                    onMessage: onMessage,
                    message: error.localizedDescription
                )
            case .cancelled:
                self?.notifyDisconnectIfCurrentConnection(sink.id)
                self?.scheduleReconnect(
                    configuration: configuration,
                    onMessage: onMessage,
                    message: nil
                )
            default:
                break
            }
        }

        connection.start(queue: .global(qos: .userInitiated))
    }

    private func scheduleReconnect(
        configuration: RelayPeerConfiguration,
        onMessage: @escaping LocalPeerMessageHandler,
        message: String?
    ) {
        let shouldReconnect = lock.withLock {
            guard isRunning else { return false }
            connection = nil
            connectionID = nil
            return true
        }
        guard shouldReconnect else { return }
        updateStatus(.reconnecting(message))

        let item = DispatchWorkItem { [weak self] in
            guard let self else { return }
            let stillRunning = self.lock.withLock { self.isRunning }
            guard stillRunning else { return }
            self.updateStatus(.connecting)
            self.connect(configuration: configuration, onMessage: onMessage)
        }
        lock.withLock {
            reconnectWorkItem?.cancel()
            reconnectWorkItem = item
        }
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + configuration.reconnectDelay, execute: item)
    }

    private func notifyDisconnectIfCurrentConnection(_ id: UUID) {
        let shouldNotify = lock.withLock {
            guard connectionID == id else { return false }
            connectionID = nil
            return true
        }
        if shouldNotify {
            onDisconnect?(id)
        }
    }

    private func updateStatus(_ newStatus: RelayPeerStatus) {
        let handler = lock.withLock {
            status = newStatus
            return statusHandler
        }
        handler?(newStatus)
    }

    private func updateStatus(
        _ newStatus: RelayPeerStatus,
        handler explicitHandler: (@Sendable (RelayPeerStatus) -> Void)?
    ) {
        lock.withLock {
            status = newStatus
        }
        explicitHandler?(newStatus)
    }

    private enum RelayRegistrationStatus: Equatable, Sendable {
        case registered
        case ready
    }

    private enum RelayRegistrationReadResult: Equatable, Sendable {
        case status(RelayRegistrationStatus)
        case invalid
        case timedOut
    }

    private static func receiveRegistrationStatus(
        connection: NWConnection,
        timeout: TimeInterval,
        completion: @escaping @Sendable (RelayRegistrationReadResult) -> Void
    ) {
        let gate = RelayRegistrationReadGate()
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + timeout) {
            gate.resolve(.timedOut, completion: completion)
        }
        receiveLine(connection: connection) { line in
            switch line {
            case "AETHERLINK_RELAY registered":
                gate.resolve(.status(.registered), completion: completion)
            case "AETHERLINK_RELAY ready":
                gate.resolve(.status(.ready), completion: completion)
            default:
                gate.resolve(.invalid, completion: completion)
            }
        }
    }

    private static func receiveLine(
        connection: NWConnection,
        buffer: Data = Data(),
        completion: @escaping @Sendable (String?) -> Void
    ) {
        guard buffer.count < 256 else {
            completion(nil)
            return
        }
        connection.receive(minimumIncompleteLength: 1, maximumLength: 1) { data, _, _, error in
            guard error == nil,
                  let data,
                  let byte = data.first
            else {
                completion(nil)
                return
            }
            var nextBuffer = buffer
            if byte == UInt8(ascii: "\n") {
                completion(String(data: nextBuffer, encoding: .utf8)?.trimmingCharacters(in: .newlines))
                return
            }
            nextBuffer.append(byte)
            receiveLine(connection: connection, buffer: nextBuffer, completion: completion)
        }
    }

    private final class RelayRegistrationReadGate: @unchecked Sendable {
        private let lock = NSLock()
        private var isResolved = false

        func resolve(
            _ result: RelayRegistrationReadResult,
            completion: @escaping @Sendable (RelayRegistrationReadResult) -> Void
        ) {
            let shouldComplete = lock.withLock {
                guard !isResolved else { return false }
                isResolved = true
                return true
            }
            if shouldComplete {
                completion(result)
            }
        }
    }

    private static func receiveNextFrame(
        connection: NWConnection,
        peer: RelayPeerConnection?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        guard let peer else {
            connection.cancel()
            return
        }
        connection.receive(minimumIncompleteLength: 4, maximumLength: 4) { lengthData, _, _, error in
            guard error == nil, let lengthData, lengthData.count == 4 else {
                peer.close()
                return
            }

            let length = lengthData.withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
            let bodyLength = Int(length)
            guard bodyLength > 0 && bodyLength <= ProtocolCodec.maxFrameBytes else {
                peer.close()
                return
            }

            connection.receive(minimumIncompleteLength: bodyLength, maximumLength: bodyLength) { body, _, _, error in
                guard error == nil, let body, body.count == bodyLength else {
                    peer.close()
                    return
                }

                do {
                    let envelope = try peer.decodeReceivedBody(body)
                    onMessage(envelope, peer)
                    receiveNextFrame(connection: connection, peer: peer, onMessage: onMessage)
                } catch {
                    peer.send(ProtocolEnvelope(
                        type: MessageType.error,
                        payload: [
                            "code": .string("invalid_payload"),
                            "message": .string(error.localizedDescription),
                            "retryable": .bool(false)
                        ]
                    ))
                    receiveNextFrame(connection: connection, peer: peer, onMessage: onMessage)
                }
            }
        }
    }
}

public final class RelayPeerConnection: RuntimeMessageSink, @unchecked Sendable {
    public let id = UUID()
    public var connectionID: UUID { id }

    private let connection: NWConnection
    private let codec: ProtocolCodec
    private let sendQueue: DispatchQueue
    private var sendCipher: RelayFrameCipher?
    private var receiveCipher: RelayFrameCipher?

    init(connection: NWConnection, codec: ProtocolCodec, relaySecret: String?, relayNonce: String?) {
        self.connection = connection
        self.codec = codec
        self.sendQueue = DispatchQueue(label: "dev.aetherlink.relay-peer-send-\(id.uuidString)")
        if let relaySecret, !relaySecret.isEmpty {
            self.sendCipher = RelayFrameCipher(relaySecret: relaySecret, routeNonce: relayNonce)
            self.receiveCipher = RelayFrameCipher(relaySecret: relaySecret, routeNonce: relayNonce)
        }
    }

    func sendRelayHandshake(relayID: String) {
        let line = "AETHERLINK_RELAY runtime \(relayID)\n"
        connection.send(content: Data(line.utf8), completion: .contentProcessed { _ in })
    }

    public func send(_ envelope: ProtocolEnvelope) {
        sendQueue.async { [self] in
            do {
                var body = try codec.encodeEnvelopeBody(envelope)
                if var cipher = sendCipher {
                    body = try cipher.encryptRuntimeBody(body)
                    sendCipher = cipher
                }
                let frame = try codec.encodeLengthPrefixedBody(body)
                connection.send(content: frame, completion: .contentProcessed { _ in })
            } catch {
                connection.cancel()
            }
        }
    }

    public func close() {
        connection.cancel()
    }

    func decodeReceivedBody(_ body: Data) throws -> ProtocolEnvelope {
        var decodedBody = body
        if var cipher = receiveCipher {
            decodedBody = try cipher.decryptClientBody(body)
            receiveCipher = cipher
        }
        return try codec.decodeEnvelope(decodedBody)
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
