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
    public var runtimeIdentity: RelayRuntimeIdentity?
    public var identityAuthorizationSigner: (any RelayIdentityAuthorizationSigning)?

    public init(
        host: String,
        port: UInt16,
        relayID: String,
        relaySecret: String? = nil,
        relayNonce: String? = nil,
        reconnectDelay: TimeInterval = 2,
        runtimeIdentity: RelayRuntimeIdentity? = nil,
        identityAuthorizationSigner: (any RelayIdentityAuthorizationSigning)? = nil
    ) {
        self.init(
            host: host,
            port: port,
            relayID: relayID,
            relaySecret: relaySecret,
            relayNonce: relayNonce,
            reconnectDelay: reconnectDelay,
            controlLineTimeout: Self.defaultControlLineTimeout,
            runtimeIdentity: runtimeIdentity,
            identityAuthorizationSigner: identityAuthorizationSigner
        )
    }

    public init(
        host: String,
        port: UInt16,
        relayID: String,
        relaySecret: String? = nil,
        relayNonce: String? = nil,
        reconnectDelay: TimeInterval = 2,
        controlLineTimeout: TimeInterval,
        runtimeIdentity: RelayRuntimeIdentity? = nil,
        identityAuthorizationSigner: (any RelayIdentityAuthorizationSigning)? = nil
    ) {
        precondition(!host.isEmpty, "Relay host must not be empty")
        precondition(!relayID.isEmpty, "Relay id must not be empty")
        precondition(relayNonce?.isEmpty != true, "Relay nonce must not be empty")
        precondition(controlLineTimeout > 0, "Relay control-line timeout must be positive")
        precondition(
            (runtimeIdentity == nil) == (identityAuthorizationSigner == nil),
            "Relay runtime identity and authorization signer must be configured together"
        )
        self.host = host
        self.port = port
        self.relayID = relayID
        self.relaySecret = relaySecret
        self.relayNonce = relayNonce
        self.reconnectDelay = reconnectDelay
        self.controlLineTimeout = controlLineTimeout
        self.runtimeIdentity = runtimeIdentity
        self.identityAuthorizationSigner = identityAuthorizationSigner
    }

    public static func == (lhs: RelayPeerConfiguration, rhs: RelayPeerConfiguration) -> Bool {
        lhs.host == rhs.host &&
            lhs.port == rhs.port &&
            lhs.relayID == rhs.relayID &&
            lhs.relaySecret == rhs.relaySecret &&
            lhs.relayNonce == rhs.relayNonce &&
            lhs.reconnectDelay == rhs.reconnectDelay &&
            lhs.controlLineTimeout == rhs.controlLineTimeout &&
            lhs.runtimeIdentity == rhs.runtimeIdentity &&
            (lhs.identityAuthorizationSigner == nil) == (rhs.identityAuthorizationSigner == nil)
    }

    public func withRelayNonce(_ relayNonce: String?) -> RelayPeerConfiguration {
        RelayPeerConfiguration(
            host: host,
            port: port,
            relayID: relayID,
            relaySecret: relaySecret,
            relayNonce: relayNonce?.isEmpty == false ? relayNonce : nil,
            reconnectDelay: reconnectDelay,
            controlLineTimeout: controlLineTimeout,
            runtimeIdentity: runtimeIdentity,
            identityAuthorizationSigner: identityAuthorizationSigner
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

public final class RelayPeerClient: RelayPeerTransport, RuntimeDisconnectReporting, @unchecked Sendable {
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
                let failConfirmation: @Sendable () -> Void = {
                    self.updateStatus(.failed("Relay key confirmation failed."))
                    connection.cancel()
                }
                let finishReady: @Sendable (RelaySessionKeys?) -> Void = { sessionKeys in
                    do {
                        try sink.activateFrameCipher(sessionKeys: sessionKeys)
                    } catch {
                        failConfirmation()
                        return
                    }
                    self.updateStatus(.ready)
                    Self.receiveNextFrame(
                        connection: connection,
                        peer: sink,
                        onMessage: onMessage
                    )
                }
                let acceptReady: @Sendable (RelayRegistrationStatus) -> Void = { readyStatus in
                    do {
                        guard case .ready(let peer) = readyStatus else {
                            failConfirmation()
                            return
                        }
                        guard let peer else {
                            guard !sink.requiresStrictCrypto else {
                                failConfirmation()
                                return
                            }
                            finishReady(nil)
                            return
                        }
                        guard sink.requiresStrictCrypto else {
                            failConfirmation()
                            return
                        }
                        let sessionKeys = try sink.prepareRelaySession(
                            relayID: configuration.relayID,
                            clientSessionNonce: peer.sessionNonce,
                            clientEphemeralKey: peer.ephemeralKey
                        )
                        Self.receiveConfirmationLine(
                            connection: connection,
                            timeout: configuration.controlLineTimeout
                        ) { result in
                            guard case .line(let line) = result,
                                  sink.validateClientConfirmation(line, sessionKeys: sessionKeys)
                            else {
                                failConfirmation()
                                return
                            }
                            sink.sendRuntimeConfirmation(sessionKeys: sessionKeys) { sent in
                                guard sent else {
                                    failConfirmation()
                                    return
                                }
                                finishReady(sessionKeys)
                            }
                        }
                    } catch {
                        failConfirmation()
                    }
                }
                let receiveRegistrationStatus: @Sendable () -> Void = {
                    Self.receiveRegistrationStatus(
                        connection: connection,
                        timeout: configuration.controlLineTimeout
                    ) { result in
                        switch result {
                        case .status(.registered(let strict)) where strict == sink.requiresStrictCrypto:
                            self.updateStatus(.waitingForPeer)
                            Self.receiveRegistrationStatus(
                                connection: connection,
                                timeout: configuration.controlLineTimeout
                            ) { result in
                                switch result {
                                case .status(let status):
                                    acceptReady(status)
                                case .timedOut:
                                    self.updateStatus(.failed("Relay ready line timed out after registration."))
                                    connection.cancel()
                                default:
                                    self.updateStatus(.failed("Relay did not return ready after registration."))
                                    connection.cancel()
                                }
                            }
                        case .status(let status):
                            acceptReady(status)
                        case .invalid:
                            self.updateStatus(.failed("Relay did not accept runtime registration."))
                            connection.cancel()
                        case .timedOut:
                            self.updateStatus(.failed("Relay registration timed out before ready."))
                            connection.cancel()
                        }
                    }
                }
                let failAuthorization: @Sendable () -> Void = {
                    self.updateStatus(.failed("Relay runtime registration authorization failed."))
                    connection.cancel()
                }

                sink.sendRelayHandshake(
                    relayID: configuration.relayID,
                    runtimeIdentity: configuration.runtimeIdentity
                )
                if sink.requiresStrictCrypto, let runtimeIdentity = configuration.runtimeIdentity {
                    guard let signer = configuration.identityAuthorizationSigner else {
                        failAuthorization()
                        return
                    }
                    Self.receiveRegistrationChallenge(
                        connection: connection,
                        timeout: configuration.controlLineTimeout
                    ) { result in
                        guard case .challenge(let challenge) = result,
                              sink.validateRegistrationChallenge(
                                challenge,
                                relayID: configuration.relayID,
                                relayNonce: configuration.relayNonce,
                                runtimeIdentity: runtimeIdentity
                              ),
                              let signerIdentity = try? signer.relayRuntimeIdentity(),
                              signerIdentity == runtimeIdentity,
                              let proof = try? signer.signRelayRuntimeRegistrationChallenge(challenge),
                              proof.runtimeIdentity == runtimeIdentity,
                              RelayIdentityAuthorization.verify(
                                signatureBase64: proof.signatureBase64,
                                messageData: challenge.signedMessageData(),
                                runtimeIdentity: runtimeIdentity
                              )
                        else {
                            failAuthorization()
                            return
                        }
                        sink.sendRuntimeRegistrationProof(
                            challenge: challenge.challenge,
                            signatureBase64: proof.signatureBase64
                        ) { sent in
                            guard sent else {
                                failAuthorization()
                                return
                            }
                            receiveRegistrationStatus()
                        }
                    }
                } else {
                    receiveRegistrationStatus()
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
        case registered(strict: Bool)
        case ready(peer: RelayStrictPeer?)
    }

    private struct RelayStrictPeer: Equatable, Sendable {
        let sessionNonce: String
        let ephemeralKey: String
    }

    private enum RelayRegistrationReadResult: Equatable, Sendable {
        case status(RelayRegistrationStatus)
        case invalid
        case timedOut
    }

    private enum RelayRegistrationChallengeReadResult: Equatable, Sendable {
        case challenge(RelayRuntimeRegistrationIdentityChallenge)
        case invalid
        case timedOut
    }

    private enum RelayConfirmationReadResult: Equatable, Sendable {
        case line(String)
        case unavailable
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
                gate.resolve(.status(.registered(strict: false)), completion: completion)
            case "AETHERLINK_RELAY registered crypto=2":
                gate.resolve(.status(.registered(strict: true)), completion: completion)
            case "AETHERLINK_RELAY ready":
                gate.resolve(.status(.ready(peer: nil)), completion: completion)
            default:
                if let peer = relayReadyStrictPeer(line) {
                    gate.resolve(.status(.ready(peer: peer)), completion: completion)
                } else {
                    gate.resolve(.invalid, completion: completion)
                }
            }
        }
    }

    private static func receiveRegistrationChallenge(
        connection: NWConnection,
        timeout: TimeInterval,
        completion: @escaping @Sendable (RelayRegistrationChallengeReadResult) -> Void
    ) {
        let gate = RelayRegistrationChallengeReadGate()
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + timeout) {
            gate.resolve(.timedOut, completion: completion)
        }
        receiveLine(connection: connection, maximumByteCount: 4_096) { line in
            guard let challenge = parseRegistrationChallenge(line) else {
                gate.resolve(.invalid, completion: completion)
                return
            }
            gate.resolve(.challenge(challenge), completion: completion)
        }
    }

    private static func parseRegistrationChallenge(
        _ line: String?
    ) -> RelayRuntimeRegistrationIdentityChallenge? {
        guard let line,
              !line.contains("\r"),
              line.hasPrefix(RelayRuntimeRegistrationIdentityChallenge.responsePrefix)
        else { return nil }
        let json = String(line.dropFirst(RelayRuntimeRegistrationIdentityChallenge.responsePrefix.count))
        guard json.first == "{", json.last == "}", let data = json.data(using: .utf8) else {
            return nil
        }
        let expectedKeys: Set<String> = [
            "relay_id",
            "relay_expires_at",
            "relay_nonce",
            "runtime_key_fingerprint",
            "ticket_generation",
            "session_nonce",
            "ephemeral_key",
            "challenge",
            "challenge_expires_at",
            "crypto_version",
            "allocation_auth"
        ]
        guard let object = try? JSONSerialization.jsonObject(with: data),
              let payload = object as? [String: Any],
              Set(payload.keys) == expectedKeys,
              let decoded = try? JSONDecoder().decode(
                RelayRuntimeRegistrationIdentityChallenge.self,
                from: data
              )
        else { return nil }
        return try? RelayRuntimeRegistrationIdentityChallenge(
            relayID: decoded.relayID,
            relayExpiresAtEpochMillis: decoded.relayExpiresAtEpochMillis,
            relayNonce: decoded.relayNonce,
            runtimeKeyFingerprint: decoded.runtimeKeyFingerprint,
            ticketGeneration: decoded.ticketGeneration,
            sessionNonce: decoded.sessionNonce,
            ephemeralKey: decoded.ephemeralKey,
            challenge: decoded.challenge,
            challengeExpiresAtEpochMillis: decoded.challengeExpiresAtEpochMillis,
            cryptoVersion: decoded.cryptoVersion,
            allocationAuth: decoded.allocationAuth
        )
    }

    private static func relayReadyStrictPeer(_ line: String?) -> RelayStrictPeer? {
        guard let line else { return nil }
        let parts = line.split(separator: " ", omittingEmptySubsequences: false)
        guard parts.count == 5,
              parts[0] == "AETHERLINK_RELAY",
              parts[1] == "ready",
              parts[2] == "crypto=2"
        else { return nil }
        let nonceField = String(parts[3])
        let keyField = String(parts[4])
        let noncePrefix = "peer_session_nonce="
        let keyPrefix = "peer_ephemeral_key="
        guard nonceField.hasPrefix(noncePrefix), keyField.hasPrefix(keyPrefix) else { return nil }
        let nonce = String(nonceField.dropFirst(noncePrefix.count))
        let ephemeralKey = String(keyField.dropFirst(keyPrefix.count))
        guard RelaySessionNonce.isCanonical(nonce),
              RelaySessionCrypto.isCanonicalEphemeralKey(ephemeralKey)
        else { return nil }
        return RelayStrictPeer(sessionNonce: nonce, ephemeralKey: ephemeralKey)
    }

    private static func receiveConfirmationLine(
        connection: NWConnection,
        timeout: TimeInterval,
        completion: @escaping @Sendable (RelayConfirmationReadResult) -> Void
    ) {
        let gate = RelayConfirmationReadGate()
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + timeout) {
            gate.resolve(.timedOut, completion: completion)
        }
        receiveLine(connection: connection) { line in
            if let line {
                gate.resolve(.line(line), completion: completion)
            } else {
                gate.resolve(.unavailable, completion: completion)
            }
        }
    }

    private static func receiveLine(
        connection: NWConnection,
        buffer: Data = Data(),
        maximumByteCount: Int = 256,
        completion: @escaping @Sendable (String?) -> Void
    ) {
        guard buffer.count < maximumByteCount else {
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
                completion(String(data: nextBuffer, encoding: .utf8))
                return
            }
            nextBuffer.append(byte)
            receiveLine(
                connection: connection,
                buffer: nextBuffer,
                maximumByteCount: maximumByteCount,
                completion: completion
            )
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

    private final class RelayRegistrationChallengeReadGate: @unchecked Sendable {
        private let lock = NSLock()
        private var isResolved = false

        func resolve(
            _ result: RelayRegistrationChallengeReadResult,
            completion: @escaping @Sendable (RelayRegistrationChallengeReadResult) -> Void
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

    private final class RelayConfirmationReadGate: @unchecked Sendable {
        private let lock = NSLock()
        private var isResolved = false

        func resolve(
            _ result: RelayConfirmationReadResult,
            completion: @escaping @Sendable (RelayConfirmationReadResult) -> Void
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
                } catch RelayPeerSessionError.encryptedFrameRejected {
                    peer.close()
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
    public var transportSecurityContext: TransportSecurityContext? {
        transportSecurityContextLock.withLock { storedTransportSecurityContext }
    }
    var requiresStrictCrypto: Bool { relaySecret != nil }

    private let connection: NWConnection
    private let codec: ProtocolCodec
    private let sendQueue: DispatchQueue
    private let transportSecurityContextLock = NSLock()
    private var storedTransportSecurityContext: TransportSecurityContext?
    private let relaySecret: String?
    private let relayNonce: String?
    private let runtimeSessionNonce: String?
    private let runtimeEphemeralKey: RelaySessionEphemeralKey?
    private var sendCipher: RelayFrameCipher?
    private var receiveCipher: RelayFrameCipher?

    init(connection: NWConnection, codec: ProtocolCodec, relaySecret: String?, relayNonce: String?) {
        self.connection = connection
        self.codec = codec
        self.sendQueue = DispatchQueue(label: "dev.aetherlink.relay-peer-send-\(id.uuidString)")
        self.storedTransportSecurityContext = nil
        self.relaySecret = relaySecret?.isEmpty == false ? relaySecret : nil
        self.relayNonce = relayNonce
        self.runtimeSessionNonce = relaySecret?.isEmpty == false ? RelaySessionNonce.generate() : nil
        self.runtimeEphemeralKey = relaySecret?.isEmpty == false ? RelaySessionEphemeralKey() : nil
    }

    func sendRelayHandshake(relayID: String, runtimeIdentity: RelayRuntimeIdentity?) {
        var line = "AETHERLINK_RELAY runtime \(relayID)"
        if let runtimeSessionNonce, let runtimeEphemeralKey {
            line += " crypto=2 session_nonce=\(runtimeSessionNonce)" +
                " ephemeral_key=\(runtimeEphemeralKey.publicKeyHex)"
            if let runtimeIdentity {
                line += " runtime_key_fingerprint=\(runtimeIdentity.fingerprint)"
            }
        }
        line += "\n"
        connection.send(content: Data(line.utf8), completion: .contentProcessed { _ in })
    }

    func validateRegistrationChallenge(
        _ challenge: RelayRuntimeRegistrationIdentityChallenge,
        relayID: String,
        relayNonce: String?,
        runtimeIdentity: RelayRuntimeIdentity
    ) -> Bool {
        guard let relayNonce,
              let runtimeSessionNonce,
              let runtimeEphemeralKey
        else { return false }
        let nowEpochMillis = Int64(Date().timeIntervalSince1970 * 1_000)
        return challenge.relayID == relayID &&
            challenge.relayNonce == relayNonce &&
            challenge.runtimeKeyFingerprint == runtimeIdentity.fingerprint &&
            challenge.sessionNonce == runtimeSessionNonce &&
            challenge.ephemeralKey == runtimeEphemeralKey.publicKeyHex &&
            challenge.relayExpiresAtEpochMillis > nowEpochMillis &&
            challenge.challengeExpiresAtEpochMillis > nowEpochMillis
    }

    func sendRuntimeRegistrationProof(
        challenge: String,
        signatureBase64: String,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        let line = "AETHERLINK_RELAY registration_proof crypto=2 challenge=\(challenge) " +
            "signature=\(signatureBase64)\n"
        connection.send(content: Data(line.utf8), completion: .contentProcessed { error in
            completion(error == nil)
        })
    }

    func prepareRelaySession(
        relayID: String,
        clientSessionNonce: String,
        clientEphemeralKey: String
    ) throws -> RelaySessionKeys {
        guard let relaySecret,
              let runtimeSessionNonce,
              let runtimeEphemeralKey
        else {
            throw RelayPeerSessionError.missingStrictSession
        }
        return try RelaySessionCrypto.deriveKeys(
            localRole: .runtime,
            localEphemeralKey: runtimeEphemeralKey,
            relayID: relayID,
            routeNonce: relayNonce,
            relaySecret: relaySecret,
            clientSessionNonce: clientSessionNonce,
            runtimeSessionNonce: runtimeSessionNonce,
            clientEphemeralKey: clientEphemeralKey,
            runtimeEphemeralKey: runtimeEphemeralKey.publicKeyHex
        )
    }

    func validateClientConfirmation(
        _ line: String,
        sessionKeys: RelaySessionKeys
    ) -> Bool {
        return RelayKeyConfirmation.validateControlLine(
            line + "\n",
            expectedRole: .client,
            sessionKeys: sessionKeys
        )
    }

    func sendRuntimeConfirmation(
        sessionKeys: RelaySessionKeys,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        let line = RelayKeyConfirmation.controlLine(
            role: .runtime,
            sessionKeys: sessionKeys
        )
        connection.send(content: Data(line.utf8), completion: .contentProcessed { error in
            completion(error == nil)
        })
    }

    func activateFrameCipher(
        sessionKeys: RelaySessionKeys?,
        initialFrameIndex: Int64 = 0
    ) throws {
        guard let relaySecret else {
            guard sessionKeys == nil else {
                throw RelayPeerSessionError.unexpectedSecurityContext
            }
            return
        }
        guard !relaySecret.isEmpty, let sessionKeys else {
            throw RelayPeerSessionError.missingSecurityContext
        }
        sendCipher = RelayFrameCipher(
            sessionKeys: sessionKeys,
            frameIndex: initialFrameIndex
        )
        receiveCipher = RelayFrameCipher(
            sessionKeys: sessionKeys,
            frameIndex: initialFrameIndex
        )
        transportSecurityContextLock.withLock {
            storedTransportSecurityContext = TransportSecurityContext(
                bindingID: sessionKeys.bindingID
            )
        }
    }

    public func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result {
        try transportSecurityContextLock.withLock {
            try operation(storedTransportSecurityContext)
        }
    }

    public func send(_ envelope: ProtocolEnvelope) {
        send(envelope) { _ in }
    }

    public func send(
        _ envelope: ProtocolEnvelope,
        completion: @escaping @Sendable (Bool) -> Void
    ) {
        sendQueue.async { [self] in
            do {
                var body = try codec.encodeEnvelopeBody(envelope)
                if var cipher = sendCipher {
                    body = try cipher.encryptRuntimeBody(body)
                    sendCipher = cipher
                }
                let frame = try codec.encodeLengthPrefixedBody(body)
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

    func decodeReceivedBody(_ body: Data) throws -> ProtocolEnvelope {
        var decodedBody = body
        if var cipher = receiveCipher {
            do {
                decodedBody = try cipher.decryptClientBody(body)
            } catch {
                throw RelayPeerSessionError.encryptedFrameRejected
            }
            receiveCipher = cipher
        }
        return try codec.decodeEnvelope(decodedBody)
    }
}

private enum RelayPeerSessionError: Error, Equatable {
    case missingStrictSession
    case missingSecurityContext
    case unexpectedSecurityContext
    case encryptedFrameRejected
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
