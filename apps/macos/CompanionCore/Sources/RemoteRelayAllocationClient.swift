import Darwin
import Foundation
import Transport

public protocol RelayServiceRouteAllocating: Sendable {
    func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        relaySecret: String?,
        allocationToken: String?,
        timeout: TimeInterval
    ) throws -> CompanionRemoteRelayRouteAllocation
}

public struct TCPRelayServiceRouteAllocator: RelayServiceRouteAllocating {
    public init() {}

    public func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        relaySecret: String? = nil,
        allocationToken: String? = nil,
        timeout: TimeInterval = 5
    ) throws -> CompanionRemoteRelayRouteAllocation {
        try validateRelayToken(routeToken)
        if let relaySecret {
            try validateRelaySecret(relaySecret)
        }
        if let allocationToken {
            try validateAllocationToken(allocationToken)
        }
        let socket = try Self.connectSocket(host: host, port: port, timeout: timeout)
        defer { Darwin.close(socket) }

        var requestParts = ["AETHERLINK_RELAY", "allocate", routeToken]
        if let relaySecret {
            requestParts.append(relaySecret)
        }
        if let allocationToken {
            requestParts.append("allocation_token=\(allocationToken)")
        }
        let requestLine = requestParts.joined(separator: " ") + "\n"
        guard writeAll(socket: socket, data: Data(requestLine.utf8)) else {
            throw RelayServiceRouteAllocationError.writeFailed
        }
        let responseLine = try readLine(socket: socket)
        let response = try RelayServiceAllocationResponse.parse(responseLine)
        try response.validate()
        return CompanionRemoteRelayRouteAllocation(
            configuration: RelayPeerConfiguration(
                host: host,
                port: port,
                relayID: response.relayID,
                relaySecret: response.relaySecret,
                relayNonce: response.relayNonce
            ),
            lease: CompanionRemoteRouteLease(
                expiresAtEpochMillis: response.relayExpiresAtEpochMillis,
                nonce: response.relayNonce
            )
        )
    }

    private static func connectSocket(host: String, port: UInt16, timeout: TimeInterval) throws -> Int32 {
        var hints = addrinfo(
            ai_flags: 0,
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
            throw RelayServiceRouteAllocationError.resolveFailed(String(cString: gai_strerror(status)))
        }
        defer { freeaddrinfo(first) }

        var cursor: UnsafeMutablePointer<addrinfo>? = first
        while let info = cursor {
            let fd = Darwin.socket(info.pointee.ai_family, info.pointee.ai_socktype, info.pointee.ai_protocol)
            if fd >= 0 {
                setTimeout(timeout, on: fd)
                if Darwin.connect(fd, info.pointee.ai_addr, info.pointee.ai_addrlen) == 0 {
                    return fd
                }
                Darwin.close(fd)
            }
            cursor = info.pointee.ai_next
        }

        throw RelayServiceRouteAllocationError.connectFailed(String(cString: strerror(errno)))
    }
}

public enum RelayServiceRouteAllocationError: Error, Equatable, LocalizedError, Sendable {
    case invalidRouteToken
    case resolveFailed(String)
    case connectFailed(String)
    case writeFailed
    case readFailed
    case invalidResponse
    case incompleteStaticBootstrapRoute
    case invalidRelaySecret
    case invalidAllocationToken

    public var errorDescription: String? {
        switch self {
        case .invalidRouteToken:
            return "Remote route token is invalid."
        case .resolveFailed(let message):
            return "AetherLink Runtime connection address could not be resolved: \(message)"
        case .connectFailed(let message):
            return "Remote route allocation connection failed: \(message)"
        case .writeFailed:
            return "Remote route allocation request could not be sent."
        case .readFailed:
            return "Remote route allocation response could not be read."
        case .invalidResponse:
            return "Remote route allocation response was invalid."
        case .incompleteStaticBootstrapRoute:
            return "Bootstrap route override must include both route id and route secret."
        case .invalidRelaySecret:
            return "Route secret is invalid for allocation."
        case .invalidAllocationToken:
            return "Route allocation token is invalid."
        }
    }
}

private struct RelayServiceAllocationResponse: Decodable {
    let relayID: String
    let relaySecret: String
    let relayExpiresAtEpochMillis: Int64
    let relayNonce: String

    static func parse(_ line: String) throws -> RelayServiceAllocationResponse {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        let prefix = "AETHERLINK_RELAY allocation "
        guard trimmed.hasPrefix(prefix),
              let data = String(trimmed.dropFirst(prefix.count)).data(using: .utf8)
        else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }
        return try JSONDecoder().decode(RelayServiceAllocationResponse.self, from: data)
    }

    private enum CodingKeys: String, CodingKey {
        case relayID = "relay_id"
        case relaySecret = "relay_secret"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
    }

    func validate() throws {
        try validateRelayToken(relayID)
        try validateRelaySecret(relaySecret)
        guard relayExpiresAtEpochMillis > 0,
              !relayNonce.isEmpty,
              relayNonce.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
        else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }
    }
}

private func validateRelayToken(_ value: String) throws {
    guard !value.isEmpty,
          value.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
    else {
        throw RelayServiceRouteAllocationError.invalidRouteToken
    }
}

private func validateRelaySecret(_ value: String) throws {
    guard !value.isEmpty,
          value.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
    else {
        throw RelayServiceRouteAllocationError.invalidRelaySecret
    }
}

private func validateAllocationToken(_ value: String) throws {
    guard !value.isEmpty,
          value.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
    else {
        throw RelayServiceRouteAllocationError.invalidAllocationToken
    }
}

private func setTimeout(_ timeout: TimeInterval, on socket: Int32) {
    let seconds = Int(timeout)
    let microseconds = Int((timeout - TimeInterval(seconds)) * 1_000_000)
    var value = timeval(tv_sec: seconds, tv_usec: Int32(microseconds))
    setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, &value, socklen_t(MemoryLayout<timeval>.size))
    setsockopt(socket, SOL_SOCKET, SO_SNDTIMEO, &value, socklen_t(MemoryLayout<timeval>.size))
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

private func readLine(socket: Int32, maxBytes: Int = 4096) throws -> String {
    var bytes: [UInt8] = []
    bytes.reserveCapacity(128)

    while bytes.count < maxBytes {
        var byte: UInt8 = 0
        let count = Darwin.recv(socket, &byte, 1, 0)
        guard count > 0 else {
            throw RelayServiceRouteAllocationError.readFailed
        }
        bytes.append(byte)
        if byte == UInt8(ascii: "\n") {
            break
        }
    }

    guard bytes.last == UInt8(ascii: "\n"),
          let line = String(bytes: bytes, encoding: .utf8)
    else {
        throw RelayServiceRouteAllocationError.readFailed
    }
    return line
}
