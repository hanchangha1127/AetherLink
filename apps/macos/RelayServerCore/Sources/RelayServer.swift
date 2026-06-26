import Darwin
import Foundation

public struct RelayServerConfiguration: Equatable, Sendable {
    public var host: String
    public var port: UInt16
    public var allocationTTLSeconds: TimeInterval
    public var requiresAllocation: Bool
    public var allocationStoreURL: URL?
    public var allocationToken: String?

    public init(
        host: String = "0.0.0.0",
        port: UInt16 = 43171,
        allocationTTLSeconds: TimeInterval = 30 * 24 * 60 * 60,
        requiresAllocation: Bool = false,
        allocationStoreURL: URL? = nil,
        allocationToken: String? = nil
    ) {
        self.host = host
        self.port = port
        self.allocationTTLSeconds = allocationTTLSeconds
        self.requiresAllocation = requiresAllocation
        self.allocationStoreURL = allocationStoreURL
        self.allocationToken = allocationToken
    }
}

public final class RelayServer: @unchecked Sendable {
    private let configuration: RelayServerConfiguration
    private let matcher = RelayMatcher()
    private let allocationRegistry: RelayAllocationRegistry

    public init(configuration: RelayServerConfiguration) {
        self.configuration = configuration
        self.allocationRegistry = RelayAllocationRegistry(persistenceURL: configuration.allocationStoreURL)
    }

    public func run() throws -> Never {
        let listenSocket = try makeListenSocket(host: configuration.host, port: configuration.port)
        log("AetherLink Swift development relay listening on \(configuration.host):\(configuration.port)")

        while true {
            var storage = sockaddr_storage()
            var length = socklen_t(MemoryLayout<sockaddr_storage>.size)
            let clientSocket = withUnsafeMutablePointer(to: &storage) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                    Darwin.accept(listenSocket, sockaddrPointer, &length)
                }
            }

            if clientSocket >= 0 {
                DispatchQueue.global(qos: .userInitiated).async { [self] in
                    handleClient(socket: clientSocket)
                }
            }
        }
    }

    private func handleClient(socket: Int32) {
        do {
            let line = try readLine(socket: socket)
            if RelayAllocationRequest.isAllocationLine(line) {
                try handleAllocationRequest(line: line, socket: socket)
                close(socket)
                return
            }
            let handshake = try RelayHandshake.parse(line)
            guard isRelayIDAllowed(handshake.relayID) else {
                log("rejected unallocated relay_id=\(shortID(handshake.relayID))")
                close(socket)
                return
            }
            let peer = RelaySocketPeer(
                registration: RelayPeerRegistration(role: handshake.role, relayID: handshake.relayID),
                socket: socket
            )
            log("accepted role=\(handshake.role.rawValue) relay_id=\(shortID(handshake.relayID))")

            switch matcher.register(peer.registration) {
            case .waiting(let replaced):
                if let replaced {
                    RelaySocketRegistry.shared.close(peerID: replaced.id)
                }
                if handshake.role == .runtime,
                   !writeAll(socket: socket, data: RelayHandshake.registeredLine) {
                    close(socket)
                    return
                }
                RelaySocketRegistry.shared.store(peer)
                log("waiting relay_id=\(shortID(handshake.relayID)) role=\(handshake.role.rawValue)")
            case .matched(let runtime, let client):
                guard let runtimePeer = runtime.id == peer.registration.id ? peer : RelaySocketRegistry.shared.remove(peerID: runtime.id),
                      let clientPeer = client.id == peer.registration.id ? peer : RelaySocketRegistry.shared.remove(peerID: client.id)
                else {
                    close(socket)
                    return
                }
                bridge(runtime: runtimePeer, client: clientPeer)
            }
        } catch {
            close(socket)
        }
    }

    private func handleAllocationRequest(line: String, socket: Int32) throws {
        let request = try RelayAllocationRequest.parse(line)
        guard isAllocationAuthorized(request) else {
            log("rejected allocation route_token=\(shortID(request.routeToken))")
            throw RelayAllocationError.unauthorizedAllocation
        }
        let allocation = try RelayAllocation.make(
            routeToken: request.routeToken,
            requestedRelaySecret: request.requestedRelaySecret,
            validFor: configuration.allocationTTLSeconds
        )
        if request.shouldPersistAllocation {
            allocationRegistry.store(allocation)
        }
        guard writeAll(socket: socket, data: try allocation.responseLine()) else {
            throw RelayServerError.allocationWriteFailed
        }
        if request.isPreflight {
            log("preflight allocation route_token=\(shortID(request.routeToken))")
        } else {
            log("allocated relay_id=\(shortID(allocation.relayID)) route_token=\(shortID(request.routeToken))")
        }
    }

    private func isAllocationAuthorized(_ request: RelayAllocationRequest) -> Bool {
        guard let expectedToken = configuration.allocationToken, !expectedToken.isEmpty else {
            return true
        }
        return request.allocationToken == expectedToken
    }

    private func isRelayIDAllowed(_ relayID: String) -> Bool {
        guard configuration.requiresAllocation else { return true }
        return allocationRegistry.isValid(relayID: relayID)
    }

    private func bridge(runtime: RelaySocketPeer, client: RelaySocketPeer) {
        log("matched relay_id=\(shortID(runtime.registration.relayID)) runtime<->client")
        guard writeAll(socket: runtime.socket, data: RelayHandshake.readyLine),
              writeAll(socket: client.socket, data: RelayHandshake.readyLine)
        else {
            close(runtime.socket)
            close(client.socket)
            return
        }

        let group = DispatchGroup()
        group.enter()
        DispatchQueue.global(qos: .userInitiated).async {
            forwardBytes(from: runtime.socket, to: client.socket)
            group.leave()
        }
        group.enter()
        DispatchQueue.global(qos: .userInitiated).async {
            forwardBytes(from: client.socket, to: runtime.socket)
            group.leave()
        }
        group.wait()
        close(runtime.socket)
        close(client.socket)
    }
}

private struct RelaySocketPeer: Sendable {
    let registration: RelayPeerRegistration
    let socket: Int32
}

private final class RelaySocketRegistry: @unchecked Sendable {
    static let shared = RelaySocketRegistry()

    private let lock = NSLock()
    private var sockets: [UUID: RelaySocketPeer] = [:]

    func store(_ peer: RelaySocketPeer) {
        lock.withLock {
            sockets[peer.registration.id] = peer
        }
    }

    func remove(peerID: UUID) -> RelaySocketPeer? {
        lock.withLock {
            sockets.removeValue(forKey: peerID)
        }
    }

    func close(peerID: UUID) {
        if let peer = remove(peerID: peerID) {
            Darwin.close(peer.socket)
        }
    }
}

private func makeListenSocket(host: String, port: UInt16) throws -> Int32 {
    var hints = addrinfo(
        ai_flags: AI_PASSIVE,
        ai_family: AF_UNSPEC,
        ai_socktype: SOCK_STREAM,
        ai_protocol: IPPROTO_TCP,
        ai_addrlen: 0,
        ai_canonname: nil,
        ai_addr: nil,
        ai_next: nil
    )
    var result: UnsafeMutablePointer<addrinfo>?
    let status = getaddrinfo(host, String(port), &hints, &result)
    guard status == 0, let first = result else {
        throw RelayServerError.bindFailed(String(cString: gai_strerror(status)))
    }
    defer { freeaddrinfo(first) }

    var cursor: UnsafeMutablePointer<addrinfo>? = first
    while let info = cursor {
        let fd = Darwin.socket(info.pointee.ai_family, info.pointee.ai_socktype, info.pointee.ai_protocol)
        if fd >= 0 {
            var yes: Int32 = 1
            setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))
            if Darwin.bind(fd, info.pointee.ai_addr, info.pointee.ai_addrlen) == 0,
               Darwin.listen(fd, SOMAXCONN) == 0 {
                return fd
            }
            Darwin.close(fd)
        }
        cursor = info.pointee.ai_next
    }

    throw RelayServerError.bindFailed(String(cString: strerror(errno)))
}

private func readLine(socket: Int32, maxBytes: Int = 4096) throws -> String {
    var bytes: [UInt8] = []
    bytes.reserveCapacity(64)

    while bytes.count < maxBytes {
        var byte: UInt8 = 0
        let count = Darwin.recv(socket, &byte, 1, 0)
        guard count > 0 else {
            throw RelayServerError.handshakeReadFailed
        }
        bytes.append(byte)
        if byte == UInt8(ascii: "\n") {
            break
        }
    }

    guard bytes.last == UInt8(ascii: "\n") || bytes.count < maxBytes,
          let line = String(bytes: bytes, encoding: .utf8)
    else {
        throw RelayServerError.handshakeReadFailed
    }
    return line
}

private func writeAll(socket: Int32, data: Data) -> Bool {
    data.withUnsafeBytes { rawBuffer in
        guard let base = rawBuffer.baseAddress else { return true }
        var sent = 0
        while sent < rawBuffer.count {
            let count = Darwin.send(socket, base.advanced(by: sent), rawBuffer.count - sent, 0)
            guard count > 0 else { return false }
            sent += count
        }
        return true
    }
}

private func forwardBytes(from source: Int32, to destination: Int32) {
    var buffer = [UInt8](repeating: 0, count: 64 * 1024)
    while true {
        let count = Darwin.recv(source, &buffer, buffer.count, 0)
        guard count > 0 else { break }
        let data = Data(buffer.prefix(count))
        guard writeAll(socket: destination, data: data) else { break }
    }
    shutdown(destination, SHUT_WR)
}

private func shortID(_ value: String) -> String {
    guard value.count > 12 else { return value }
    return "\(value.prefix(6))...\(value.suffix(6))"
}

private func log(_ message: String) {
    print("[relay] \(message)")
    fflush(stdout)
}

public enum RelayServerError: Error, Equatable, Sendable {
    case bindFailed(String)
    case handshakeReadFailed
    case allocationWriteFailed
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
