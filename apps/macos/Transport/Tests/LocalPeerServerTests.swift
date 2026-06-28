import Darwin
import Foundation
import XCTest
@testable import Transport

final class LocalPeerServerTests: XCTestCase {
    func testLocalPeerServerReportsDisconnectOnceWhenPeerClosesBeforeFrame() throws {
        let port = try Self.freeTCPPort()
        let disconnectRecorder = LocalPeerDisconnectRecorder()
        let server = LocalPeerServer()
        server.onDisconnect = { id in
            disconnectRecorder.append(id)
        }
        defer { server.stop() }

        server.start(port: port, onMessage: { _, _ in })
        XCTAssertEqual(server.status, .listening(port: port))

        let socket = try Self.connectWithRetry(port: port)
        Darwin.close(socket)

        XCTAssertEqual(disconnectRecorder.waitForCount(1), 1)
        Thread.sleep(forTimeInterval: 0.2)
        XCTAssertEqual(disconnectRecorder.count, 1)
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

private enum LocalPeerServerTestError: Error {
    case socket(String)
}
