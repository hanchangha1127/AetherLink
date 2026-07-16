import BridgeProtocol
import Foundation
import Network

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

public final class LocalPeerServer: RuntimeTransport, RuntimeDisconnectReporting, @unchecked Sendable {
    private var listener: NWListener?
    private let codec = ProtocolCodec()
    private let lock = NSLock()
    private var connections: [UUID: LocalPeerConnection] = [:]

    public private(set) var status: PeerServerStatus = .stopped
    public var onDisconnect: (@Sendable (UUID) -> Void)?

    public init() {}

    public func start(port: UInt16 = 43170, onMessage: @escaping LocalPeerMessageHandler) {
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

                let peer = LocalPeerConnection(connection: connection, codec: codec)
                Self.debugLog("accepted peer \(peer.id)")
                self.insert(peer)

                connection.stateUpdateHandler = { [weak self, weak peer] state in
                    switch state {
                    case .failed(let error):
                        Self.debugLog("peer failed \(peer?.id.uuidString ?? "unknown"): \(error)")
                        if let peer {
                            self?.remove(peer)
                        }
                    case .cancelled:
                        Self.debugLog("peer cancelled \(peer?.id.uuidString ?? "unknown")")
                        if let peer {
                            self?.remove(peer)
                        }
                    default:
                        break
                    }
                }

                connection.start(queue: .global(qos: .userInitiated))
                Self.receiveNextFrame(connection: connection, peer: peer, codec: codec, onMessage: onMessage)
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
        let activeConnections = lock.withLock {
            let values = Array(connections.values)
            connections.removeAll()
            return values
        }
        activeConnections.forEach { peer in
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

    private static func receiveNextFrame(
        connection: NWConnection,
        peer: LocalPeerConnection,
        codec: ProtocolCodec,
        onMessage: @escaping LocalPeerMessageHandler
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

                do {
                    let envelope = try codec.decodeEnvelope(body)
                    debugLog("peer \(peer.id) decoded type=\(envelope.type) request_id=\(envelope.requestID)")
                    onMessage(envelope, peer)
                    receiveNextFrame(connection: connection, peer: peer, codec: codec, onMessage: onMessage)
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
                    receiveNextFrame(connection: connection, peer: peer, codec: codec, onMessage: onMessage)
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

public final class LocalPeerConnection: RuntimeMessageSink, @unchecked Sendable {
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
    private let sendQueue: DispatchQueue

    init(connection: NWConnection, codec: ProtocolCodec) {
        self.connection = connection
        self.codec = codec
        self.sendQueue = DispatchQueue(label: "dev.localagentbridge.local-peer-send-\(id.uuidString)")
    }

    public func send(_ envelope: ProtocolEnvelope) {
        send(envelope) { _ in }
    }

    public func send(
        _ envelope: ProtocolEnvelope,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        sendQueue.async { [connection, codec] in
            do {
                let frame = try codec.encodeFrame(envelope)
                connection.send(content: frame, completion: .contentProcessed { error in
                    completion(error == nil)
                })
            } catch {
                connection.cancel()
                completion(false)
            }
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
        connection.cancel()
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
