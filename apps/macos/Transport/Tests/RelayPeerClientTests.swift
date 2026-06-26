import Darwin
import Foundation
import XCTest
@testable import Transport

final class RelayPeerClientTests: XCTestCase {
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
}

private final class ControlledRelayServer {
    let port: UInt16

    private let listenSocket: Int32
    private let handshakeSemaphore = DispatchSemaphore(value: 0)
    private let lock = NSLock()
    private var acceptedSocket: Int32 = -1
    private var handshake = [UInt8]()
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
            guard let self else { return }
            let fd = Darwin.accept(socket, nil, nil)
            guard fd >= 0 else { return }
            let shouldClose = self.lock.withLock {
                if self.stopped {
                    return true
                }
                self.acceptedSocket = fd
                return false
            }
            if shouldClose {
                Darwin.close(fd)
                return
            }
            self.receiveHandshake(socket: fd)
        }
    }

    func waitForHandshake() -> String? {
        guard handshakeSemaphore.wait(timeout: .now() + 2) == .success else {
            return nil
        }
        return lock.withLock {
            String(bytes: handshake, encoding: .utf8)
        }
    }

    func write(_ line: String) {
        let fd = lock.withLock { acceptedSocket }
        guard fd >= 0 else { return }
        let bytes = Array(line.utf8)
        _ = bytes.withUnsafeBytes { rawBuffer in
            Darwin.send(fd, rawBuffer.baseAddress, rawBuffer.count, 0)
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

    private func receiveHandshake(socket: Int32) {
        while true {
            var byte: UInt8 = 0
            let count = Darwin.recv(socket, &byte, 1, 0)
            guard count == 1 else { return }
            let isComplete = lock.withLock {
                handshake.append(byte)
                return byte == UInt8(ascii: "\n")
            }
            if isComplete {
                handshakeSemaphore.signal()
                return
            }
        }
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
