import BridgeProtocol
import Foundation
import Network

public struct RelayPeerConfiguration: Equatable, Sendable {
    public var host: String
    public var port: UInt16
    public var relayID: String
    public var relaySecret: String?
    public var reconnectDelay: TimeInterval

    public init(
        host: String,
        port: UInt16,
        relayID: String,
        relaySecret: String? = nil,
        reconnectDelay: TimeInterval = 2
    ) {
        precondition(!host.isEmpty, "Relay host must not be empty")
        precondition(!relayID.isEmpty, "Relay id must not be empty")
        self.host = host
        self.port = port
        self.relayID = relayID
        self.relaySecret = relaySecret
        self.reconnectDelay = reconnectDelay
    }
}

public final class RelayPeerClient: @unchecked Sendable {
    private let codec = ProtocolCodec()
    private let lock = NSLock()
    private var connection: NWConnection?
    private var isRunning = false
    private var reconnectWorkItem: DispatchWorkItem?

    public init() {}

    public func start(
        configuration: RelayPeerConfiguration,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        stop()
        lock.withLock {
            isRunning = true
        }
        connect(configuration: configuration, onMessage: onMessage)
    }

    public func stop() {
        let connectionToCancel = lock.withLock {
            isRunning = false
            reconnectWorkItem?.cancel()
            reconnectWorkItem = nil
            let current = connection
            connection = nil
            return current
        }
        connectionToCancel?.cancel()
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
            relaySecret: configuration.relaySecret
        )

        lock.withLock {
            self.connection = connection
        }

        connection.stateUpdateHandler = { [weak self, sink] state in
            switch state {
            case .ready:
                sink.sendRelayHandshake(relayID: configuration.relayID)
                Self.receiveReadyLine(connection: connection) { ready in
                    guard ready else {
                        connection.cancel()
                        return
                    }
                    Self.receiveNextFrame(
                        connection: connection,
                        peer: sink,
                        onMessage: onMessage
                    )
                }
            case .failed, .cancelled:
                self?.scheduleReconnect(configuration: configuration, onMessage: onMessage)
            default:
                break
            }
        }

        connection.start(queue: .global(qos: .userInitiated))
    }

    private func scheduleReconnect(
        configuration: RelayPeerConfiguration,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        let shouldReconnect = lock.withLock {
            guard isRunning else { return false }
            connection = nil
            return true
        }
        guard shouldReconnect else { return }

        let item = DispatchWorkItem { [weak self] in
            guard let self else { return }
            let stillRunning = self.lock.withLock { self.isRunning }
            guard stillRunning else { return }
            self.connect(configuration: configuration, onMessage: onMessage)
        }
        lock.withLock {
            reconnectWorkItem?.cancel()
            reconnectWorkItem = item
        }
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + configuration.reconnectDelay, execute: item)
    }

    private static func receiveReadyLine(connection: NWConnection, completion: @escaping @Sendable (Bool) -> Void) {
        let expected = Data("AETHERLINK_RELAY ready\n".utf8)
        connection.receive(minimumIncompleteLength: expected.count, maximumLength: expected.count) { data, _, _, error in
            guard error == nil,
                  let data
            else {
                completion(false)
                return
            }
            completion(data == expected)
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

    init(connection: NWConnection, codec: ProtocolCodec, relaySecret: String?) {
        self.connection = connection
        self.codec = codec
        self.sendQueue = DispatchQueue(label: "dev.aetherlink.relay-peer-send-\(id.uuidString)")
        if let relaySecret, !relaySecret.isEmpty {
            self.sendCipher = RelayFrameCipher(relaySecret: relaySecret)
            self.receiveCipher = RelayFrameCipher(relaySecret: relaySecret)
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
