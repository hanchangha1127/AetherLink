import Darwin
import BridgeProtocol
import Foundation
import XCTest
@testable import Transport

final class RelayPeerClientTests: XCTestCase {
    func testRelayPeerConfigurationDefaultControlLineTimeoutAllowsPhysicalQrStartup() {
        let configuration = RelayPeerConfiguration(
            host: "127.0.0.1",
            port: 43171,
            relayID: "relay-default-timeout"
        )

        XCTAssertEqual(configuration.controlLineTimeout, 45)
    }

    func testRelayPeerClientWaitsForAcceptedRuntimeRegistrationBeforeWaitingForPeer() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let statusRecorder = RelayStatusRecorder()
        let registeredStatus = DispatchSemaphore(value: 0)
        let readyStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-test",
                reconnectDelay: 60
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .waitingForPeer {
                    registeredStatus.signal()
                }
                if status == .ready {
                    readyStatus.signal()
                }
            },
            onMessage: { _, _ in }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-test\n")
        XCTAssertFalse(statusRecorder.contains(.waitingForPeer))

        server.write("AETHERLINK_RELAY registered\n")
        XCTAssertEqual(registeredStatus.wait(timeout: .now() + 2), .success)
        XCTAssertTrue(statusRecorder.contains(.waitingForPeer))
        XCTAssertFalse(statusRecorder.contains(.ready))

        server.write("AETHERLINK_RELAY ready\n")
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 2), .success)
        XCTAssertTrue(statusRecorder.contains(.ready))
    }

    func testRelayPeerClientTimesOutWhenRegistrationLineNeverArrives() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let statusRecorder = RelayStatusRecorder()
        let failedStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-registration-timeout",
                reconnectDelay: 60,
                controlLineTimeout: 0.1
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .failed("Relay registration timed out before ready.") {
                    failedStatus.signal()
                }
            },
            onMessage: { _, _ in }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-registration-timeout\n")
        XCTAssertEqual(failedStatus.wait(timeout: .now() + 2), .success)
        XCTAssertFalse(statusRecorder.contains(.waitingForPeer))
        XCTAssertFalse(statusRecorder.contains(.ready))
    }

    func testRelayPeerClientTimesOutWhenReadyLineNeverArrivesAfterRegistration() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let statusRecorder = RelayStatusRecorder()
        let registeredStatus = DispatchSemaphore(value: 0)
        let failedStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-ready-timeout",
                reconnectDelay: 60,
                controlLineTimeout: 0.1
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .waitingForPeer {
                    registeredStatus.signal()
                }
                if status == .failed("Relay ready line timed out after registration.") {
                    failedStatus.signal()
                }
            },
            onMessage: { _, _ in }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-ready-timeout\n")
        server.write("AETHERLINK_RELAY registered\n")
        XCTAssertEqual(registeredStatus.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(failedStatus.wait(timeout: .now() + 2), .success)
        XCTAssertFalse(statusRecorder.contains(.ready))
    }

    func testRelayPeerClientReportsDisconnectOnceWhenStoppedConnectionCancels() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let disconnectRecorder = RelayDisconnectRecorder()
        let client = RelayPeerClient()
        defer { client.stop() }
        client.onDisconnect = { id in
            disconnectRecorder.append(id)
        }

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-disconnect-test",
                reconnectDelay: 60
            ),
            onMessage: { _, _ in }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-disconnect-test\n")

        client.stop()
        XCTAssertEqual(disconnectRecorder.waitForCount(1), 1)
        Thread.sleep(forTimeInterval: 0.2)
        XCTAssertEqual(disconnectRecorder.count, 1)
    }

    func testRelayPeerClientRetireKeepsCurrentConnectionAndSuppressesReconnect() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let codec = ProtocolCodec()
        let statusRecorder = RelayStatusRecorder()
        let readyStatus = DispatchSemaphore(value: 0)
        let requestHandled = DispatchSemaphore(value: 0)
        let disconnectRecorder = RelayDisconnectRecorder()
        let client = RelayPeerClient()
        defer { client.stop() }
        client.onDisconnect = { id in
            disconnectRecorder.append(id)
        }

        let responseEnvelope = ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "retired-response",
            payload: ["status": .string("retired-current-connection")]
        )
        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-retire-test",
                reconnectDelay: 0.1
            ),
            onStatusChange: { status in
                statusRecorder.append(status)
                if status == .ready {
                    readyStatus.signal()
                }
            },
            onMessage: { envelope, sink in
                XCTAssertEqual(envelope.type, MessageType.modelsList)
                XCTAssertEqual(envelope.requestID, "retired-current-request")
                sink.send(responseEnvelope)
                requestHandled.signal()
            }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-retire-test\n")
        server.write("AETHERLINK_RELAY ready\n")
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 2), .success)

        client.retireAfterCurrentConnection()
        XCTAssertFalse(statusRecorder.contains(.stopped))

        let requestEnvelope = ProtocolEnvelope(
            type: MessageType.modelsList,
            requestID: "retired-current-request"
        )
        server.writeFrameBody(try codec.encodeEnvelopeBody(requestEnvelope))
        XCTAssertEqual(requestHandled.wait(timeout: .now() + 2), .success)

        let responseBody = try XCTUnwrap(server.waitForFrameBody())
        let decodedResponse = try codec.decodeEnvelope(responseBody)
        XCTAssertEqual(decodedResponse.type, responseEnvelope.type)
        XCTAssertEqual(decodedResponse.requestID, responseEnvelope.requestID)
        XCTAssertEqual(decodedResponse.payload, responseEnvelope.payload)

        server.closeAcceptedSocket()
        XCTAssertEqual(disconnectRecorder.waitForCount(1), 1)
        XCTAssertNil(server.waitForHandshake(index: 1, timeout: .now() + 0.5))
        XCTAssertFalse(statusRecorder.contains { status in
            if case .reconnecting = status {
                return true
            }
            return false
        })
    }

    func testRelayPeerClientEncryptsRuntimeFramesWithRouteNonceBoundCipher() throws {
        let server = try ControlledRelayServer()
        defer { server.stop() }

        let codec = ProtocolCodec()
        let relaySecret = "nonce-bound-relay-secret"
        let relayNonce = "nonce-bound-route"
        let requestHandled = DispatchSemaphore(value: 0)
        let readyStatus = DispatchSemaphore(value: 0)
        let client = RelayPeerClient()
        defer { client.stop() }

        let responseEnvelope = ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "nonce-bound-response",
            payload: ["status": .string("runtime-ciphertext")]
        )
        let plaintextResponseBody = try codec.encodeEnvelopeBody(responseEnvelope)

        client.start(
            configuration: RelayPeerConfiguration(
                host: "127.0.0.1",
                port: server.port,
                relayID: "relay-nonce-bound",
                relaySecret: relaySecret,
                relayNonce: relayNonce,
                reconnectDelay: 60
            ),
            onStatusChange: { status in
                if status == .ready {
                    readyStatus.signal()
                }
            },
            onMessage: { envelope, sink in
                XCTAssertEqual(envelope.type, MessageType.modelsList)
                XCTAssertEqual(envelope.requestID, "nonce-bound-request")
                sink.send(responseEnvelope)
                requestHandled.signal()
            }
        )

        XCTAssertEqual(server.waitForHandshake(), "AETHERLINK_RELAY runtime relay-nonce-bound\n")
        server.write("AETHERLINK_RELAY ready\n")
        XCTAssertEqual(readyStatus.wait(timeout: .now() + 2), .success)

        let requestEnvelope = ProtocolEnvelope(
            type: MessageType.modelsList,
            requestID: "nonce-bound-request",
            payload: ["probe": .string("client-ciphertext")]
        )
        var clientCipher = RelayFrameCipher(relaySecret: relaySecret, routeNonce: relayNonce)
        let encryptedRequestBody = try clientCipher.encryptClientBody(try codec.encodeEnvelopeBody(requestEnvelope))
        server.writeFrameBody(encryptedRequestBody)

        XCTAssertEqual(requestHandled.wait(timeout: .now() + 2), .success)
        let encryptedResponseBody = try XCTUnwrap(server.waitForFrameBody())

        XCTAssertNotEqual(encryptedResponseBody, plaintextResponseBody)
        XCTAssertNil(encryptedResponseBody.range(of: Data(MessageType.runtimeHealth.utf8)))
        XCTAssertNil(encryptedResponseBody.range(of: Data("runtime-ciphertext".utf8)))

        var runtimeCipher = RelayFrameCipher(relaySecret: relaySecret, routeNonce: relayNonce)
        let decryptedResponseBody = try runtimeCipher.decryptRuntimeBody(encryptedResponseBody)
        let decodedResponse = try codec.decodeEnvelope(decryptedResponseBody)
        XCTAssertEqual(decodedResponse.version, responseEnvelope.version)
        XCTAssertEqual(decodedResponse.type, responseEnvelope.type)
        XCTAssertEqual(decodedResponse.requestID, responseEnvelope.requestID)
        XCTAssertEqual(decodedResponse.payload, responseEnvelope.payload)

        var wrongNonceCipher = RelayFrameCipher(relaySecret: relaySecret, routeNonce: "wrong-route")
        XCTAssertThrowsError(try wrongNonceCipher.decryptRuntimeBody(encryptedResponseBody))
    }
}

private final class ControlledRelayServer {
    let port: UInt16

    private let listenSocket: Int32
    private let handshakeSemaphore = DispatchSemaphore(value: 0)
    private let lock = NSLock()
    private var acceptedSocket: Int32 = -1
    private var handshakes = [[UInt8]]()
    private var stopped = false

    init() throws {
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else {
            throw TestRelayServerError.socket(String(cString: strerror(errno)))
        }
        var yes: Int32 = 1
        setsockopt(socket, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = UInt16(0).bigEndian
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let bound = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                Darwin.bind(socket, sockaddrPointer, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard bound == 0 else {
            Darwin.close(socket)
            throw TestRelayServerError.socket(String(cString: strerror(errno)))
        }
        guard Darwin.listen(socket, 1) == 0 else {
            Darwin.close(socket)
            throw TestRelayServerError.socket(String(cString: strerror(errno)))
        }

        var boundAddress = sockaddr_in()
        var boundAddressLength = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &boundAddress) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                Darwin.getsockname(socket, sockaddrPointer, &boundAddressLength)
            }
        }
        guard named == 0 else {
            Darwin.close(socket)
            throw TestRelayServerError.socket(String(cString: strerror(errno)))
        }

        self.listenSocket = socket
        self.port = UInt16(bigEndian: boundAddress.sin_port)

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.acceptConnections(socket: socket)
        }
    }

    func waitForHandshake(index: Int = 0, timeout: DispatchTime = .now() + 2) -> String? {
        while lock.withLock({ handshakes.count <= index }) {
            guard handshakeSemaphore.wait(timeout: timeout) == .success else {
                return nil
            }
        }
        return lock.withLock {
            String(bytes: handshakes[index], encoding: .utf8)
        }
    }

    func waitForFrameBody() -> Data? {
        let fd = lock.withLock { acceptedSocket }
        guard fd >= 0,
              let lengthData = readExactly(byteCount: 4, socket: fd)
        else {
            return nil
        }
        let bodyLength = lengthData.reduce(UInt32(0)) { partial, byte in
            (partial << 8) | UInt32(byte)
        }
        guard bodyLength > 0,
              bodyLength <= UInt32(ProtocolCodec.maxFrameBytes)
        else {
            return nil
        }
        return readExactly(byteCount: Int(bodyLength), socket: fd)
    }

    func write(_ line: String) {
        let fd = lock.withLock { acceptedSocket }
        guard fd >= 0 else { return }
        let bytes = Array(line.utf8)
        _ = bytes.withUnsafeBytes { rawBuffer in
            Darwin.send(fd, rawBuffer.baseAddress, rawBuffer.count, 0)
        }
    }

    func writeFrameBody(_ body: Data) {
        let fd = lock.withLock { acceptedSocket }
        guard fd >= 0 else { return }
        var length = UInt32(body.count).bigEndian
        var frame = Data(bytes: &length, count: MemoryLayout<UInt32>.size)
        frame.append(body)
        frame.withUnsafeBytes { rawBuffer in
            _ = Darwin.send(fd, rawBuffer.baseAddress, rawBuffer.count, 0)
        }
    }

    func stop() {
        let sockets = lock.withLock {
            stopped = true
            let accepted = acceptedSocket
            acceptedSocket = -1
            return (listen: listenSocket, accepted: accepted)
        }
        if sockets.accepted >= 0 {
            Darwin.close(sockets.accepted)
        }
        Darwin.close(sockets.listen)
    }

    func closeAcceptedSocket() {
        let accepted = lock.withLock {
            let accepted = acceptedSocket
            acceptedSocket = -1
            return accepted
        }
        if accepted >= 0 {
            Darwin.close(accepted)
        }
    }

    private func acceptConnections(socket: Int32) {
        while true {
            let fd = Darwin.accept(socket, nil, nil)
            guard fd >= 0 else { return }
            let shouldClose = lock.withLock {
                if stopped {
                    return true
                }
                acceptedSocket = fd
                return false
            }
            if shouldClose {
                Darwin.close(fd)
                return
            }
            var timeout = timeval(tv_sec: 2, tv_usec: 0)
            setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))
            receiveHandshake(socket: fd)
        }
    }

    private func receiveHandshake(socket: Int32) {
        var handshake = [UInt8]()
        while true {
            var byte: UInt8 = 0
            let count = Darwin.recv(socket, &byte, 1, 0)
            guard count == 1 else { return }
            handshake.append(byte)
            if byte == UInt8(ascii: "\n") {
                lock.withLock {
                    handshakes.append(handshake)
                }
                handshakeSemaphore.signal()
                return
            }
        }
    }

    private func readExactly(byteCount: Int, socket: Int32) -> Data? {
        var buffer = [UInt8](repeating: 0, count: byteCount)
        var offset = 0
        while offset < byteCount {
            let received = buffer.withUnsafeMutableBytes { rawBuffer -> Int in
                guard let baseAddress = rawBuffer.baseAddress else { return -1 }
                return Darwin.recv(socket, baseAddress.advanced(by: offset), byteCount - offset, 0)
            }
            guard received > 0 else {
                return nil
            }
            offset += received
        }
        return Data(buffer)
    }
}

private final class RelayStatusRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var statuses: [RelayPeerStatus] = []

    func append(_ status: RelayPeerStatus) {
        lock.withLock {
            statuses.append(status)
        }
    }

    func contains(_ status: RelayPeerStatus) -> Bool {
        lock.withLock {
            statuses.contains(status)
        }
    }

    func contains(_ predicate: (RelayPeerStatus) -> Bool) -> Bool {
        lock.withLock {
            statuses.contains(where: predicate)
        }
    }
}

private final class RelayDisconnectRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private let semaphore = DispatchSemaphore(value: 0)
    private var ids: [UUID] = []

    var count: Int {
        lock.withLock { ids.count }
    }

    func append(_ id: UUID) {
        lock.withLock {
            ids.append(id)
        }
        semaphore.signal()
    }

    func waitForCount(_ expectedCount: Int, timeout: DispatchTime = .now() + 2) -> Int {
        while count < expectedCount {
            if semaphore.wait(timeout: timeout) != .success {
                break
            }
        }
        return count
    }
}

private enum TestRelayServerError: Error {
    case socket(String)
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
