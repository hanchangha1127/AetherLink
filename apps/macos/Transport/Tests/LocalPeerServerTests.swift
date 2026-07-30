import Darwin
import BridgeProtocol
import Foundation
import Network
import XCTest
@testable import Transport

final class LocalPeerServerTests: XCTestCase {
    func testLocalPeerConnectionCompletionReportsSuccessfulContentProcessing() throws {
        let server = try LocalPeerControlledListener()
        defer { server.stop() }

        let (connection, stateRecorder) = Self.startLoopbackConnection(port: server.port)
        defer { connection.cancel() }
        XCTAssertTrue(stateRecorder.waitUntilReady())

        let peer = LocalPeerConnection(connection: connection, codec: ProtocolCodec())
        let completion = LocalPeerSendCompletionRecorder()
        let envelope = ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "local-peer-callback-success",
            timestamp: Date(timeIntervalSince1970: 1_700_000_000),
            payload: ["status": .string("ready")]
        )

        peer.send(envelope) { succeeded in
            completion.append(succeeded)
        }

        XCTAssertEqual(completion.waitForValue(), true)
        XCTAssertEqual(server.waitForEnvelope(), envelope)
        XCTAssertFalse(completion.waitForAdditionalValue())
    }

    func testLocalPeerConnectionCompletionReportsEncodingFailure() {
        let connection = NWConnection(host: "127.0.0.1", port: 1, using: .tcp)
        let peer = LocalPeerConnection(connection: connection, codec: ProtocolCodec())
        let completion = LocalPeerSendCompletionRecorder()
        let unencodableEnvelope = ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "local-peer-callback-encoding-failure",
            payload: ["invalid_number": .number(.nan)]
        )

        peer.send(unencodableEnvelope) { succeeded in
            completion.append(succeeded)
        }

        XCTAssertEqual(completion.waitForValue(), false)
        XCTAssertFalse(completion.waitForAdditionalValue())
    }

    func testLocalPeerConnectionCompletionReportsContentProcessedErrorAfterCancellation() throws {
        let server = try LocalPeerControlledListener()
        defer { server.stop() }

        let (connection, stateRecorder) = Self.startLoopbackConnection(port: server.port)
        XCTAssertTrue(stateRecorder.waitUntilReady())
        let peer = LocalPeerConnection(connection: connection, codec: ProtocolCodec())

        connection.cancel()
        XCTAssertTrue(stateRecorder.waitUntilCancelled())

        let completion = LocalPeerSendCompletionRecorder()
        peer.send(ProtocolEnvelope(type: MessageType.runtimeHealth)) { succeeded in
            completion.append(succeeded)
        }

        XCTAssertEqual(completion.waitForValue(), false)
        XCTAssertFalse(completion.waitForAdditionalValue())
    }

    func testLocalPeerServerReportsDisconnectOnceWhenPeerClosesBeforeFrame() throws {
        let port = try Self.freeTCPPort()
        let disconnectRecorder = LocalPeerDisconnectRecorder()
        let statusRecorder = LocalPeerStatusRecorder()
        let server = LocalPeerServer()
        server.onDisconnect = { id in
            disconnectRecorder.append(id)
        }
        server.onStatusChange = { statusRecorder.append($0) }
        defer { server.stop() }

        server.start(port: port, onMessage: { _, _ in })
        XCTAssertEqual(
            statusRecorder.waitForCount(2),
            [.starting(port: port), .listening(port: port)]
        )

        let socket = try Self.connectWithRetry(port: port)
        Darwin.close(socket)

        XCTAssertEqual(disconnectRecorder.waitForCount(1), 1)
        Thread.sleep(forTimeInterval: 0.2)
        XCTAssertEqual(disconnectRecorder.count, 1)
    }

    func testLocalPeerServerReportsListenerStartAndExplicitStop() throws {
        let port = try Self.freeTCPPort()
        let statusRecorder = LocalPeerStatusRecorder()
        let server = LocalPeerServer()
        server.onStatusChange = { statusRecorder.append($0) }

        server.start(port: port, onMessage: { _, _ in })
        XCTAssertEqual(
            statusRecorder.waitForCount(2),
            [.starting(port: port), .listening(port: port)]
        )

        server.stop()
        XCTAssertEqual(
            statusRecorder.waitForCount(3),
            [.starting(port: port), .listening(port: port), .stopped]
        )
    }

    func testLocalPeerServerOccupiedPortFailsThenSameInstanceRetries() throws {
        let occupied = try Self.occupyTCPPort()
        var occupiedSocket: Int32? = occupied.socket
        let statusRecorder = LocalPeerStatusRecorder()
        let server = LocalPeerServer()
        server.onStatusChange = { statusRecorder.append($0) }
        defer {
            if let occupiedSocket {
                Darwin.close(occupiedSocket)
            }
            server.stop()
        }

        server.start(port: occupied.port, onMessage: { _, _ in })

        let failedStatuses = statusRecorder.waitForCount(2)
        XCTAssertEqual(failedStatuses.first, .starting(port: occupied.port))
        guard failedStatuses.count == 2,
              case .failed = failedStatuses[1] else {
            return XCTFail("An occupied port must transition from starting to failed: \(failedStatuses)")
        }
        guard case .failed = server.status else {
            return XCTFail("Expected failed status for occupied port, got \(server.status)")
        }

        Darwin.close(occupied.socket)
        occupiedSocket = nil
        server.start(port: occupied.port, onMessage: { _, _ in })

        XCTAssertEqual(
            statusRecorder.waitForCount(4).suffix(2),
            [.starting(port: occupied.port), .listening(port: occupied.port)]
        )
        XCTAssertEqual(
            server.status,
            .listening(port: occupied.port)
        )
        let socket = try Self.connectWithRetry(port: occupied.port)
        Darwin.close(socket)
    }

    func testPeerAdmissionCannotCrossListenerStopGenerationBoundary() throws {
        let port = try Self.freeTCPPort()
        let admissionReached = DispatchSemaphore(value: 0)
        let releaseAdmission = DispatchSemaphore(value: 0)
        let admissionRecorder = LocalPeerAdmissionRecorder()
        let disconnectRecorder = LocalPeerDisconnectRecorder()
        let server = LocalPeerServer(
            beforePeerAdmission: {
                admissionReached.signal()
                _ = releaseAdmission.wait(timeout: .now() + 2)
            },
            afterPeerAdmissionAttempt: { admitted in
                admissionRecorder.append(admitted)
            }
        )
        server.onDisconnect = { id in
            disconnectRecorder.append(id)
        }
        defer {
            releaseAdmission.signal()
            server.stop()
        }

        server.start(port: port, onMessage: { _, _ in })
        let socket = try Self.connectWithRetry(port: port)
        defer { Darwin.close(socket) }
        XCTAssertEqual(admissionReached.wait(timeout: .now() + 2), .success)

        server.stop()
        releaseAdmission.signal()

        XCTAssertEqual(admissionRecorder.waitForValue(), false)
        server.stop()
        XCTAssertEqual(disconnectRecorder.count, 0)
    }

    private static func freeTCPPort() throws -> UInt16 {
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else {
            throw LocalPeerServerTestError.socket(String(cString: strerror(errno)))
        }
        defer { Darwin.close(socket) }

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
            throw LocalPeerServerTestError.socket(String(cString: strerror(errno)))
        }

        var boundAddress = sockaddr_in()
        var boundAddressLength = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &boundAddress) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                Darwin.getsockname(socket, sockaddrPointer, &boundAddressLength)
            }
        }
        guard named == 0 else {
            throw LocalPeerServerTestError.socket(String(cString: strerror(errno)))
        }
        return UInt16(bigEndian: boundAddress.sin_port)
    }

    private static func occupyTCPPort() throws -> (socket: Int32, port: UInt16) {
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else {
            throw LocalPeerServerTestError.socket(String(cString: strerror(errno)))
        }

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
            throw LocalPeerServerTestError.socket(String(cString: strerror(errno)))
        }
        guard Darwin.listen(socket, 1) == 0 else {
            Darwin.close(socket)
            throw LocalPeerServerTestError.socket(String(cString: strerror(errno)))
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
            throw LocalPeerServerTestError.socket(String(cString: strerror(errno)))
        }
        return (socket, UInt16(bigEndian: boundAddress.sin_port))
    }

    private static func connectWithRetry(port: UInt16) throws -> Int32 {
        var lastError = "connection failed"
        for _ in 0..<20 {
            let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
            guard socket >= 0 else {
                throw LocalPeerServerTestError.socket(String(cString: strerror(errno)))
            }

            var address = sockaddr_in()
            address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            address.sin_family = sa_family_t(AF_INET)
            address.sin_port = port.bigEndian
            address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
            let connected = withUnsafePointer(to: &address) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                    Darwin.connect(socket, sockaddrPointer, socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }
            if connected == 0 {
                return socket
            }
            lastError = String(cString: strerror(errno))
            Darwin.close(socket)
            Thread.sleep(forTimeInterval: 0.05)
        }
        throw LocalPeerServerTestError.socket(lastError)
    }

    private static func startLoopbackConnection(
        port: UInt16
    ) -> (connection: NWConnection, stateRecorder: LocalPeerNWConnectionStateRecorder) {
        let connection = NWConnection(
            host: "127.0.0.1",
            port: NWEndpoint.Port(rawValue: port)!,
            using: .tcp
        )
        let stateRecorder = LocalPeerNWConnectionStateRecorder()
        connection.stateUpdateHandler = { state in
            stateRecorder.append(state)
        }
        connection.start(queue: DispatchQueue(label: "local-peer-connection-test"))
        return (connection, stateRecorder)
    }
}

private final class LocalPeerSendCompletionRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private let semaphore = DispatchSemaphore(value: 0)
    private var values = [Bool]()

    func append(_ value: Bool) {
        lock.lock()
        values.append(value)
        lock.unlock()
        semaphore.signal()
    }

    func waitForValue(timeout: DispatchTime = .now() + 2) -> Bool? {
        guard semaphore.wait(timeout: timeout) == .success else { return nil }
        lock.lock()
        defer { lock.unlock() }
        return values.first
    }

    func waitForAdditionalValue(timeout: DispatchTime = .now() + 0.05) -> Bool {
        semaphore.wait(timeout: timeout) == .success
    }
}

private final class LocalPeerControlledListener: @unchecked Sendable {
    private(set) var port: UInt16 = 0
    private let listener: NWListener
    private let queue = DispatchQueue(label: "local-peer-controlled-listener")
    private let lock = NSLock()
    private let ready = DispatchSemaphore(value: 0)
    private let received = DispatchSemaphore(value: 0)
    private var becameReady = false
    private var envelope: ProtocolEnvelope?

    init() throws {
        listener = try NWListener(using: .tcp, on: .any)
        listener.stateUpdateHandler = { [weak self] state in
            guard let self else { return }
            switch state {
            case .ready:
                lock.withLock { self.becameReady = true }
                ready.signal()
            case .failed:
                ready.signal()
            default:
                break
            }
        }
        listener.newConnectionHandler = { [weak self] connection in
            guard let self else {
                connection.cancel()
                return
            }
            connection.start(queue: queue)
            receiveFrame(on: connection)
        }
        listener.start(queue: queue)
        guard ready.wait(timeout: .now() + 2) == .success,
              lock.withLock({ becameReady }) else {
            listener.cancel()
            throw LocalPeerServerTestError.listenerNotReady
        }
        guard let listenerPort = listener.port else {
            listener.cancel()
            throw LocalPeerServerTestError.listenerPortUnavailable
        }
        port = listenerPort.rawValue
    }

    func stop() {
        listener.cancel()
    }

    func waitForEnvelope(timeout: DispatchTime = .now() + 2) -> ProtocolEnvelope? {
        guard received.wait(timeout: timeout) == .success else { return nil }
        return lock.withLock { envelope }
    }

    private func receiveFrame(on connection: NWConnection) {
        connection.receive(minimumIncompleteLength: 4, maximumLength: 4) {
            [weak self] lengthData, _, _, error in
            guard let self, error == nil,
                  let lengthData, lengthData.count == 4 else {
                connection.cancel()
                return
            }
            let bodyLength = lengthData.withUnsafeBytes {
                Int($0.load(as: UInt32.self).bigEndian)
            }
            guard bodyLength > 0, bodyLength <= ProtocolCodec.maxFrameBytes else {
                connection.cancel()
                return
            }
            connection.receive(
                minimumIncompleteLength: bodyLength,
                maximumLength: bodyLength
            ) { [weak self] body, _, _, bodyError in
                guard let self, bodyError == nil,
                      let body, body.count == bodyLength,
                      let decoded = try? ProtocolCodec().decodeEnvelope(body) else {
                    connection.cancel()
                    return
                }
                lock.withLock { self.envelope = decoded }
                received.signal()
            }
        }
    }
}

private final class LocalPeerNWConnectionStateRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private let readyOrFailed = DispatchSemaphore(value: 0)
    private let cancelled = DispatchSemaphore(value: 0)
    private var becameReady = false

    func append(_ state: NWConnection.State) {
        switch state {
        case .ready:
            lock.lock()
            becameReady = true
            lock.unlock()
            readyOrFailed.signal()
        case .failed:
            readyOrFailed.signal()
        case .cancelled:
            cancelled.signal()
        default:
            break
        }
    }

    func waitUntilReady(timeout: DispatchTime = .now() + 2) -> Bool {
        guard readyOrFailed.wait(timeout: timeout) == .success else { return false }
        lock.lock()
        defer { lock.unlock() }
        return becameReady
    }

    func waitUntilCancelled(timeout: DispatchTime = .now() + 2) -> Bool {
        cancelled.wait(timeout: timeout) == .success
    }
}

private final class LocalPeerDisconnectRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private let semaphore = DispatchSemaphore(value: 0)
    private var ids: [UUID] = []

    var count: Int {
        lock.lock()
        defer { lock.unlock() }
        return ids.count
    }

    func append(_ id: UUID) {
        lock.lock()
        ids.append(id)
        lock.unlock()
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

private final class LocalPeerStatusRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private let semaphore = DispatchSemaphore(value: 0)
    private var statuses: [PeerServerStatus] = []

    func append(_ status: PeerServerStatus) {
        lock.withLock { statuses.append(status) }
        semaphore.signal()
    }

    func waitForCount(
        _ expectedCount: Int,
        timeout: DispatchTime = .now() + 2
    ) -> [PeerServerStatus] {
        while lock.withLock({ statuses.count }) < expectedCount {
            if semaphore.wait(timeout: timeout) != .success {
                break
            }
        }
        return lock.withLock { statuses }
    }
}

private final class LocalPeerAdmissionRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private let semaphore = DispatchSemaphore(value: 0)
    private var values: [Bool] = []

    func append(_ value: Bool) {
        lock.withLock { values.append(value) }
        semaphore.signal()
    }

    func waitForValue(timeout: DispatchTime = .now() + 2) -> Bool? {
        guard semaphore.wait(timeout: timeout) == .success else { return nil }
        return lock.withLock { values.first }
    }
}

private enum LocalPeerServerTestError: Error {
    case listenerNotReady
    case listenerPortUnavailable
    case socket(String)
}
