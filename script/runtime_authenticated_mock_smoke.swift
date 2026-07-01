#!/usr/bin/env swift
import CryptoKit
import Darwin
import Foundation

let backendLeakMarkers = [
    "127.0.0.1:11434",
    "127.0.0.1:1234",
    "localhost:11434",
    "localhost:1234",
    "0.0.0.0:11434",
    "0.0.0.0:1234",
    ":11434",
    ":1234",
    "http://",
    "https://",
    "ws://",
    "wss://"
]

enum SmokeFailure: Error, CustomStringConvertible {
    case message(String)

    var description: String {
        switch self {
        case .message(let message):
            return message
        }
    }
}

enum BackendMode {
    case mock
    case realOllama

    var name: String {
        switch self {
        case .mock:
            return "mock"
        case .realOllama:
            return "real Ollama"
        }
    }
}

enum TransportMode: Equatable {
    case direct
    case relay

    var name: String {
        switch self {
        case .direct:
            return "direct TCP"
        case .relay:
            return "development relay"
        }
    }
}

struct SmokeOptions {
    var backendMode: BackendMode = .mock
    var allowUnavailable = false
    var transportMode: TransportMode = .direct
    var allowDirectFallback = false
    var expectP2PRouteRefresh = false

    static func parse(_ arguments: [String]) throws -> SmokeOptions {
        var options = SmokeOptions()
        for argument in arguments.dropFirst() {
            switch argument {
            case "--real-ollama":
                options.backendMode = .realOllama
            case "--allow-unavailable":
                options.allowUnavailable = true
            case "--relay":
                options.transportMode = .relay
            case "--allow-direct-fallback":
                options.allowDirectFallback = true
            case "--expect-p2p-route-refresh":
                options.expectP2PRouteRefresh = true
            case "--help", "-h":
                print("""
                Usage: ./script/runtime_authenticated_mock_smoke.swift [--relay] [--allow-direct-fallback] [--expect-p2p-route-refresh] [--real-ollama] [--allow-unavailable]

                  default              Run authenticated mock E2E smoke, including pull, attachment, and chat coverage.
                  --relay              Route the smoke through AetherLinkRelay allocation with encrypted relay frames.
                  --allow-direct-fallback
                                       Allow explicit mixed-route relay diagnostics where QR pairing info also carries direct host/port.
                  --expect-p2p-route-refresh
                                       Require authenticated route.refresh to include complete opaque P2P rendezvous route material.
                  --real-ollama        Run pairing/auth smoke against the real provider aggregate with Ollama behind the runtime host.
                  --allow-unavailable  In --real-ollama mode, skip successfully if Ollama is unavailable.
                """)
                exit(0)
            default:
                throw SmokeFailure.message("Unknown argument: \(argument)")
            }
        }
        if options.allowUnavailable, case .mock = options.backendMode {
            throw SmokeFailure.message("--allow-unavailable only applies with --real-ollama")
        }
        if options.allowUnavailable, options.transportMode == .relay {
            throw SmokeFailure.message("--allow-unavailable with --relay is not supported yet")
        }
        if options.allowDirectFallback, options.transportMode != .relay {
            throw SmokeFailure.message("--allow-direct-fallback only applies with --relay")
        }
        if options.expectP2PRouteRefresh, options.transportMode != .relay {
            throw SmokeFailure.message("--expect-p2p-route-refresh only applies with --relay")
        }
        return options
    }
}

struct ExpectedP2PRouteRefresh {
    var routeClass: String
    var recordID: String
    var encryptedBody: String
    var antiReplayNonce: String
    var protocolVersion: Int
}

let expectedP2PRouteRefresh = ExpectedP2PRouteRefresh(
    routeClass: "p2p_rendezvous",
    recordID: "smoke-p2p-record-1",
    encryptedBody: "smoke-p2p-encrypted-body-1",
    antiReplayNonce: "smoke-p2p-nonce-1",
    protocolVersion: 1
)

let smokeSessionID = "smoke-session-\(UUID().uuidString)"
let smokeTitleSessionID = "\(smokeSessionID)-title"
let smokeLifecycleSessionID = "\(smokeSessionID)-lifecycle"
let smokeResidencySessionID = "\(smokeSessionID)-residency"
let smokeOwnerIsolationSessionAID = "\(smokeSessionID)-owner-a"
let smokeOwnerIsolationSessionBID = "\(smokeSessionID)-owner-b"
let smokeDocumentAttachmentText = "Smoke attachment body proves authenticated relay attachment handling."
let smokeImageAttachmentPrompt = "Describe this smoke image."
let smokeImageAttachmentName = "smoke-vision-gate.png"
let smokeImageAttachmentBase64 = "iVBORw0KGgo="
let smokeVisionModelID = "dev-mock-vision"
let smokeUnloadFailureModelID = "dev-mock-unload-failure"
let smokePulledModelID = "dev-pulled"
let smokePulledModelPrompt = "Say hello from the pulled smoke model."

final class ServerOutput {
    private let lock = NSLock()
    private var buffer = ""
    private(set) var pairingInfo: [String: Any]?
    private(set) var pairingURI: String?
    let pairingInfoReady = DispatchSemaphore(value: 0)
    let pairingURIReady = DispatchSemaphore(value: 0)

    func append(_ data: Data) {
        guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
        lock.lock()
        buffer += text
        let lines = buffer.split(separator: "\n", omittingEmptySubsequences: false)
        let completeLineCount = buffer.hasSuffix("\n") ? lines.count : max(lines.count - 1, 0)
        let completeLines = lines.prefix(completeLineCount)
        buffer = buffer.hasSuffix("\n") ? "" : String(lines.last ?? "")
        lock.unlock()

        for line in completeLines {
            handleLine(String(line))
        }
    }

    private func handleLine(_ line: String) {
        print("[server] \(line)")
        let marker = "AETHERLINK_DEV_PAIRING_INFO "
        if let markerRange = line.range(of: marker) {
            let jsonText = String(line[markerRange.upperBound...])
            guard let data = jsonText.data(using: .utf8),
                  let object = try? JSONSerialization.jsonObject(with: data),
                  let info = object as? [String: Any]
            else {
                return
            }
            lock.lock()
            pairingInfo = info
            lock.unlock()
            pairingInfoReady.signal()
            return
        }

        let compactURIMarker = "AETHERLINK_DEV_PAIRING_COMPACT_URI "
        let canonicalURIMarker = "AETHERLINK_DEV_PAIRING_URI "
        let uriText: String?
        if let compactRange = line.range(of: compactURIMarker) {
            uriText = String(line[compactRange.upperBound...])
        } else if let canonicalRange = line.range(of: canonicalURIMarker) {
            uriText = String(line[canonicalRange.upperBound...])
        } else {
            uriText = nil
        }
        guard let uriText,
              !uriText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else {
            return
        }
        lock.lock()
        pairingURI = uriText.trimmingCharacters(in: .whitespacesAndNewlines)
        lock.unlock()
        pairingURIReady.signal()
    }
}

final class RelayProcessOutput {
    private let lock = NSLock()
    private var buffer = ""
    let listeningReady = DispatchSemaphore(value: 0)

    func append(_ data: Data) {
        guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
        lock.lock()
        buffer += text
        let lines = buffer.split(separator: "\n", omittingEmptySubsequences: false)
        let completeLineCount = buffer.hasSuffix("\n") ? lines.count : max(lines.count - 1, 0)
        let completeLines = lines.prefix(completeLineCount)
        buffer = buffer.hasSuffix("\n") ? "" : String(lines.last ?? "")
        lock.unlock()

        for line in completeLines {
            print("[relay] \(line)")
            if line.contains("development relay listening") {
                listeningReady.signal()
            }
        }
    }
}

struct RelayConfiguration {
    var relayID: String
    var relaySecret: String
    var relayNonce: String?
    var host: String
    var port: UInt16
}

struct RelayEndpoint {
    var host: String
    var port: UInt16
}

struct ParsedPairingURI {
    var pairingCode: String
    var pairingNonce: String
    var runtimeDeviceID: String
    var relayConfiguration: RelayConfiguration?
    var relayExpiresAt: Int64?
    var hasDirectHost: Bool
    var hasDirectPort: Bool
}

final class RelayCiphertextBoundaryRecorder {
    private let lock = NSLock()
    private var frameBodies: [(direction: String, body: Data)] = []

    func record(direction: String, body: Data) {
        lock.lock()
        frameBodies.append((direction, body))
        lock.unlock()
    }

    func requireNoPlaintextMarkers(_ markers: [String]) throws {
        lock.lock()
        let captured = frameBodies
        lock.unlock()

        guard !captured.isEmpty else {
            throw SmokeFailure.message("relay ciphertext boundary smoke did not capture encrypted relay frame bodies")
        }
        for marker in markers {
            let markerData = Data(marker.utf8)
            for (index, frame) in captured.enumerated() where frame.body.range(of: markerData) != nil {
                throw SmokeFailure.message(
                    "relay ciphertext boundary exposed plaintext marker \(marker) " +
                    "in \(frame.direction) frame \(index)"
                )
            }
        }
        print("Relay ciphertext boundary verified across \(captured.count) encrypted frame bodies.")
    }
}

enum RelayCiphertextBoundary {
    static var enabled = false
    static let recorder = RelayCiphertextBoundaryRecorder()

    static func recordClientFrameBody(_ body: Data) {
        guard enabled else { return }
        recorder.record(direction: "client-to-runtime", body: body)
    }

    static func recordRuntimeFrameBody(_ body: Data) {
        guard enabled else { return }
        recorder.record(direction: "runtime-to-client", body: body)
    }

    static func requireNoPlaintextMarkers(_ markers: [String]) throws {
        guard enabled else { return }
        try recorder.requireNoPlaintextMarkers(markers)
    }
}

final class TCPClient {
    let fd: Int32
    private var relayCipher: RelayFrameBodyCipher?

    init(host: String, port: UInt16, relayCipher: RelayFrameBodyCipher? = nil) throws {
        self.relayCipher = relayCipher
        fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else {
            throw SmokeFailure.message("socket() failed: \(String(cString: strerror(errno)))")
        }

        var timeout = timeval(tv_sec: 10, tv_usec: 0)
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = port.bigEndian
        guard inet_pton(AF_INET, host, &address.sin_addr) == 1 else {
            Darwin.close(fd)
            throw SmokeFailure.message("Invalid IPv4 host: \(host)")
        }

        let connected = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                Darwin.connect(fd, sockaddrPointer, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard connected == 0 else {
            let message = String(cString: strerror(errno))
            Darwin.close(fd)
            throw SmokeFailure.message("connect(\(host):\(port)) failed: \(message)")
        }
    }

    static func relay(
        host: String,
        port: UInt16,
        relayID: String,
        relaySecret: String,
        relayNonce: String
    ) throws -> TCPClient {
        let client = try TCPClient(
            host: host,
            port: port,
            relayCipher: RelayFrameBodyCipher(secret: relaySecret, routeNonce: relayNonce)
        )
        do {
            try client.writeAll(Data("AETHERLINK_RELAY client \(relayID)\n".utf8))
            let ready = try client.readExactly(Data("AETHERLINK_RELAY ready\n".utf8).count)
            guard ready == Data("AETHERLINK_RELAY ready\n".utf8) else {
                throw SmokeFailure.message("Relay did not return ready line")
            }
            return client
        } catch {
            client.close()
            throw error
        }
    }

    func close() {
        Darwin.close(fd)
    }

    func send(_ envelope: [String: Any]) throws {
        var body = try JSONSerialization.data(withJSONObject: envelope, options: [])
        if var cipher = relayCipher {
            body = try cipher.encryptClientFrameBody(body)
            RelayCiphertextBoundary.recordClientFrameBody(body)
            relayCipher = cipher
        }
        var length = UInt32(body.count).bigEndian
        let header = Data(bytes: &length, count: MemoryLayout<UInt32>.size)
        try writeAll(header)
        try writeAll(body)
    }

    func readEnvelope() throws -> [String: Any] {
        let header = try readExactly(4)
        let length = header.withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
        guard length > 0, length <= 1024 * 1024 else {
            throw SmokeFailure.message("Invalid frame length: \(length)")
        }
        var body = try readExactly(Int(length))
        if var cipher = relayCipher {
            RelayCiphertextBoundary.recordRuntimeFrameBody(body)
            body = try cipher.decryptRuntimeFrameBody(body)
            relayCipher = cipher
        }
        guard let object = try JSONSerialization.jsonObject(with: body) as? [String: Any] else {
            throw SmokeFailure.message("Response frame was not a JSON object")
        }
        return object
    }

    private func writeAll(_ data: Data) throws {
        try data.withUnsafeBytes { rawBuffer in
            guard let baseAddress = rawBuffer.baseAddress else { return }
            var written = 0
            while written < data.count {
                let result = Darwin.write(fd, baseAddress.advanced(by: written), data.count - written)
                guard result > 0 else {
                    throw SmokeFailure.message("write() failed: \(String(cString: strerror(errno)))")
                }
                written += result
            }
        }
    }

    private func readExactly(_ count: Int) throws -> Data {
        var data = Data(count: count)
        try data.withUnsafeMutableBytes { rawBuffer in
            guard let baseAddress = rawBuffer.baseAddress else { return }
            var readCount = 0
            while readCount < count {
                let result = Darwin.read(fd, baseAddress.advanced(by: readCount), count - readCount)
                guard result > 0 else {
                    if result == 0 {
                        throw SmokeFailure.message("socket closed while reading frame")
                    }
                    throw SmokeFailure.message("read() failed: \(String(cString: strerror(errno)))")
                }
                readCount += result
            }
        }
        return data
    }
}

struct RelayFrameBodyCipher {
    private static let aad = Data("AETHERLINK_RELAY_FRAME_V1".utf8)
    private static let keyPrefix = Data("AetherLink relay frame v1\n".utf8)
    private static let routeNonceContext = Data("\nroute_nonce\n".utf8)
    private static let tagBytes = 16

    private let key: SymmetricKey
    private var clientSendCounter: UInt64 = 0
    private var runtimeReceiveCounter: UInt64 = 0

    init(secret: String, routeNonce: String) {
        var material = Self.keyPrefix
        material.append(Data(secret.utf8))
        material.append(Self.routeNonceContext)
        material.append(Data(routeNonce.utf8))
        key = SymmetricKey(data: Data(SHA256.hash(data: material)))
    }

    mutating func encryptClientFrameBody(_ body: Data) throws -> Data {
        let encrypted = try encrypt(body, direction: "CLNT", counter: clientSendCounter)
        clientSendCounter += 1
        return encrypted
    }

    mutating func decryptRuntimeFrameBody(_ body: Data) throws -> Data {
        defer { runtimeReceiveCounter += 1 }
        return try decrypt(body, direction: "RUNT", counter: runtimeReceiveCounter)
    }

    private func encrypt(_ body: Data, direction: String, counter: UInt64) throws -> Data {
        let sealed = try AES.GCM.seal(
            body,
            using: key,
            nonce: nonce(direction: direction, counter: counter),
            authenticating: Self.aad
        )
        var encryptedBody = sealed.ciphertext
        encryptedBody.append(sealed.tag)
        return encryptedBody
    }

    private func decrypt(_ body: Data, direction: String, counter: UInt64) throws -> Data {
        guard body.count >= Self.tagBytes else {
            throw SmokeFailure.message("Relay ciphertext was too short: \(body.count)")
        }
        let sealed = try AES.GCM.SealedBox(
            nonce: nonce(direction: direction, counter: counter),
            ciphertext: body.prefix(body.count - Self.tagBytes),
            tag: body.suffix(Self.tagBytes)
        )
        return try AES.GCM.open(sealed, using: key, authenticating: Self.aad)
    }

    private func nonce(direction: String, counter: UInt64) throws -> AES.GCM.Nonce {
        var data = Data(direction.utf8)
        var bigEndianCounter = counter.bigEndian
        data.append(Data(bytes: &bigEndianCounter, count: MemoryLayout<UInt64>.size))
        return try AES.GCM.Nonce(data: data)
    }
}

func envelope(_ type: String, requestID: String, payload: [String: Any] = [:]) -> [String: Any] {
    [
        "version": 1,
        "type": type,
        "request_id": requestID,
        "timestamp": ISO8601DateFormatter().string(from: Date()),
        "payload": payload
    ]
}

func runAndCapture(_ arguments: [String]) throws -> String {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    process.arguments = arguments
    let pipe = Pipe()
    process.standardOutput = pipe
    process.standardError = pipe
    try process.run()
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    process.waitUntilExit()
    let output = String(data: data, encoding: .utf8) ?? ""
    guard process.terminationStatus == 0 else {
        throw SmokeFailure.message("\(arguments.joined(separator: " ")) failed:\n\(output)")
    }
    return output.trimmingCharacters(in: .whitespacesAndNewlines)
}

func seedTrustedDevicesFile(
    fileURL: URL,
    devices: [(id: String, name: String, publicKeyBase64: String)]
) throws {
    try FileManager.default.createDirectory(
        at: fileURL.deletingLastPathComponent(),
        withIntermediateDirectories: true,
        attributes: [.posixPermissions: 0o700]
    )
    let records = devices.map { device in
        [
            "id": device.id,
            "name": device.name,
            "publicKeyBase64": device.publicKeyBase64,
            "pairedAt": "2026-06-30T00:00:00Z"
        ]
    }
    let data = try JSONSerialization.data(withJSONObject: records, options: [.prettyPrinted, .sortedKeys])
    try data.write(to: fileURL, options: [.atomic])
    try FileManager.default.setAttributes(
        [.posixPermissions: 0o600],
        ofItemAtPath: fileURL.standardizedFileURL.path
    )
}

func freePort() throws -> UInt16 {
    let fd = socket(AF_INET, SOCK_STREAM, 0)
    guard fd >= 0 else {
        throw SmokeFailure.message("socket() failed while choosing port")
    }
    defer { Darwin.close(fd) }

    var address = sockaddr_in()
    address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
    address.sin_family = sa_family_t(AF_INET)
    address.sin_addr.s_addr = in_addr_t(INADDR_LOOPBACK).bigEndian
    address.sin_port = 0
    let bound = withUnsafePointer(to: &address) { pointer in
        pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
            Darwin.bind(fd, sockaddrPointer, socklen_t(MemoryLayout<sockaddr_in>.size))
        }
    }
    guard bound == 0 else {
        throw SmokeFailure.message("bind(port: 0) failed: \(String(cString: strerror(errno)))")
    }

    var resolved = sockaddr_in()
    var length = socklen_t(MemoryLayout<sockaddr_in>.size)
    let named = withUnsafeMutablePointer(to: &resolved) { pointer in
        pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
            Darwin.getsockname(fd, sockaddrPointer, &length)
        }
    }
    guard named == 0 else {
        throw SmokeFailure.message("getsockname() failed: \(String(cString: strerror(errno)))")
    }
    return UInt16(bigEndian: resolved.sin_port)
}

func connectWithRetry(host: String, port: UInt16, relay: RelayConfiguration? = nil) throws -> TCPClient {
    let deadline = Date().addingTimeInterval(10)
    var lastError: Error?
    while Date() < deadline {
        do {
            if let relay {
                guard let relayNonce = relay.relayNonce, !relayNonce.isEmpty else {
                    throw SmokeFailure.message("Relay route is missing nonce-bound frame material")
                }
                return try TCPClient.relay(
                    host: relay.host,
                    port: relay.port,
                    relayID: relay.relayID,
                    relaySecret: relay.relaySecret,
                    relayNonce: relayNonce
                )
            }
            return try TCPClient(host: host, port: port)
        } catch {
            lastError = error
            usleep(100_000)
        }
    }
    throw SmokeFailure.message("Could not connect to RuntimeDevServer: \(lastError.map(String.init(describing:)) ?? "unknown error")")
}

func payload(_ response: [String: Any], context: String) throws -> [String: Any] {
    guard let payload = response["payload"] as? [String: Any] else {
        throw SmokeFailure.message("\(context) response had no object payload: \(response)")
    }
    return payload
}

func requireType(_ response: [String: Any], _ expected: String, context: String) throws {
    let actual = response["type"] as? String
    guard actual == expected else {
        throw SmokeFailure.message("\(context) expected type=\(expected), got \(actual ?? "nil"): \(response)")
    }
}

func requireRequestID(_ response: [String: Any], _ expected: String, context: String) throws {
    let actual = response["request_id"] as? String
    guard actual == expected else {
        throw SmokeFailure.message("\(context) expected request_id=\(expected), got \(actual ?? "nil")")
    }
}

func requireErrorCode(
    _ response: [String: Any],
    _ expectedCode: String,
    requestID: String,
    context: String,
    retryable: Bool = false
) throws {
    try requireType(response, "error", context: context)
    try requireRequestID(response, requestID, context: context)
    let errorPayload = try payload(response, context: context)
    guard errorPayload["code"] as? String == expectedCode else {
        throw SmokeFailure.message("\(context) expected error code \(expectedCode), got \(String(describing: errorPayload["code"])): \(response)")
    }
    try requireBool(errorPayload, "retryable", retryable, context: context)
}

func requireRejectedPairingResult(
    _ response: [String: Any],
    expectedCode: String,
    requestID: String,
    context: String,
    retryable: Bool
) throws {
    try requireType(response, "pairing.result", context: context)
    try requireRequestID(response, requestID, context: context)
    let rejectionPayload = try payload(response, context: context)
    try requireBool(rejectionPayload, "accepted", false, context: context)
    guard rejectionPayload["code"] as? String == expectedCode else {
        throw SmokeFailure.message("\(context) expected pairing rejection code \(expectedCode), got \(String(describing: rejectionPayload["code"])): \(response)")
    }
    try requireBool(rejectionPayload, "retryable", retryable, context: context)
}

func requireBool(_ object: [String: Any], _ key: String, _ expected: Bool, context: String) throws {
    guard let actual = object[key] as? Bool, actual == expected else {
        throw SmokeFailure.message("\(context) expected \(key)=\(expected), got \(String(describing: object[key]))")
    }
}

func requireString(_ object: [String: Any], _ key: String, context: String) throws -> String {
    guard let value = object[key] as? String, !value.isEmpty else {
        throw SmokeFailure.message("\(context) expected non-empty string for \(key)")
    }
    return value
}

func requireInt(_ object: [String: Any], _ key: String, context: String) throws -> Int {
    if let value = object[key] as? Int {
        return value
    }
    if let value = object[key] as? Int64 {
        return Int(value)
    }
    throw SmokeFailure.message("\(context) expected integer for \(key), got \(String(describing: object[key]))")
}

func requireInt64(_ object: [String: Any], _ key: String, context: String) throws -> Int64 {
    if let value = object[key] as? Int64 {
        return value
    }
    if let value = object[key] as? Int {
        return Int64(value)
    }
    if let value = object[key] as? Double, value.rounded() == value {
        return Int64(value)
    }
    throw SmokeFailure.message("\(context) expected int64 for \(key), got \(String(describing: object[key]))")
}

func parsePairingURI(_ value: String) throws -> ParsedPairingURI {
    try assertNoBackendLeak(value, context: "pairing URI")
    guard let components = URLComponents(string: value),
          components.scheme == "aetherlink",
          components.host == "pair",
          let items = components.queryItems,
          !items.isEmpty
    else {
        throw SmokeFailure.message("Development pairing URI must be an aetherlink://pair URI with query parameters: \(value)")
    }
    let query = Dictionary(
        items.map { ($0.name, $0.value ?? "") },
        uniquingKeysWith: { _, latest in latest }
    )

    let pairingCode = try requireQueryValue(
        query,
        names: ["pairing_code", "code", "c"],
        context: "pairing URI"
    )
    let pairingNonce = try requireQueryValue(
        query,
        names: ["pairing_nonce", "nonce", "n"],
        context: "pairing URI"
    )
    let runtimeDeviceID = try requireQueryValue(
        query,
        names: ["runtime_device_id", "mac_device_id", "device_id", "rid"],
        context: "pairing URI"
    )
    let hasDirectHost = queryValue(query, names: ["host", "runtime_host", "h"]) != nil
    let hasDirectPort = queryValue(query, names: ["port", "runtime_port", "p"]) != nil

    let relayHost = queryValue(query, names: ["relay_host", "remote_host", "route_host", "rendezvous_host", "rh"])
    let relayPortValue = queryValue(query, names: ["relay_port", "remote_port", "route_port", "rendezvous_port", "rp"])
    let relayID = queryValue(query, names: ["relay_id", "remote_id", "route_id", "network_id", "ri"])
    let relaySecret = queryValue(query, names: ["relay_secret", "remote_secret", "route_secret", "rs"])
    let relayNonce = queryValue(query, names: ["relay_nonce", "remote_nonce", "route_nonce", "rendezvous_nonce", "rrn"])
    let relayExpiresAtValue = queryValue(query, names: ["relay_expires_at", "remote_expires_at", "route_expires_at", "rendezvous_expires_at", "rx"])

    let relayConfiguration: RelayConfiguration?
    if relayHost != nil ||
        relayPortValue != nil ||
        relayID != nil ||
        relaySecret != nil ||
        relayNonce != nil ||
        relayExpiresAtValue != nil {
        guard let relayHost,
              let relayPortValue,
              let relayPort = UInt16(relayPortValue),
              let relayID,
              let relaySecret,
              let relayNonce,
              !relayNonce.isEmpty
        else {
            throw SmokeFailure.message("Pairing URI relay route was incomplete: \(query)")
        }
        relayConfiguration = RelayConfiguration(
            relayID: relayID,
            relaySecret: relaySecret,
            relayNonce: relayNonce,
            host: relayHost,
            port: relayPort
        )
    } else {
        relayConfiguration = nil
    }

    let relayExpiresAt: Int64?
    if let relayExpiresAtValue {
        guard let parsed = Int64(relayExpiresAtValue), parsed > 0 else {
            throw SmokeFailure.message("Pairing URI relay_expires_at was invalid: \(relayExpiresAtValue)")
        }
        relayExpiresAt = parsed
    } else {
        relayExpiresAt = nil
    }

    return ParsedPairingURI(
        pairingCode: pairingCode,
        pairingNonce: pairingNonce,
        runtimeDeviceID: runtimeDeviceID,
        relayConfiguration: relayConfiguration,
        relayExpiresAt: relayExpiresAt,
        hasDirectHost: hasDirectHost,
        hasDirectPort: hasDirectPort
    )
}

func queryValue(_ query: [String: String], names: [String]) -> String? {
    for name in names {
        if let value = query[name], !value.isEmpty {
            return value
        }
    }
    return nil
}

func requireQueryValue(_ query: [String: String], names: [String], context: String) throws -> String {
    guard let value = queryValue(query, names: names) else {
        throw SmokeFailure.message("\(context) missing \(names.first ?? "query field")")
    }
    return value
}

func nonEmptyEnvironmentValue(_ key: String) -> String? {
    guard let value = ProcessInfo.processInfo.environment[key]?.trimmingCharacters(in: .whitespacesAndNewlines),
          !value.isEmpty
    else {
        return nil
    }
    return value
}

func requireModelList(_ response: [String: Any], context: String) throws -> [[String: Any]] {
    let modelsPayload = try payload(response, context: context)
    guard let modelList = modelsPayload["models"] as? [[String: Any]] else {
        throw SmokeFailure.message("\(context) response had no models array: \(response)")
    }
    return modelList
}

func assertNoBackendLeak(_ value: Any, context: String, keyPath: [String] = []) throws {
    if let dictionary = value as? [String: Any] {
        for (key, child) in dictionary {
            try assertNoBackendLeak(child, context: context, keyPath: keyPath + [key])
        }
        return
    }
    if let array = value as? [Any] {
        for child in array {
            try assertNoBackendLeak(child, context: context, keyPath: keyPath)
        }
        return
    }
    if let string = value as? String {
        let lowered = string.lowercased()
        if let marker = backendLeakMarkers.first(where: { lowered.contains($0) }) {
            throw SmokeFailure.message("\(context) leaked backend marker \(marker): \(string)")
        }
    }
}

func sendAndRead(_ client: TCPClient, type: String, requestID: String, payload: [String: Any] = [:]) throws -> [String: Any] {
    try client.send(envelope(type, requestID: requestID, payload: payload))
    let response = try client.readEnvelope()
    try assertNoBackendLeak(response, context: requestID)
    return response
}

func refreshRelayRoute(
    client: TCPClient,
    runtimeDeviceID: String,
    runtimeKeyFingerprint: String,
    expectedEndpoint: RelayEndpoint,
    expectP2PRouteRefresh: Bool
) throws -> RelayConfiguration {
    print("Checking route.refresh relay renewal...")
    let response = try sendAndRead(client, type: "route.refresh", requestID: "smoke-route-refresh")
    try requireType(response, "route.refresh", context: "route.refresh")
    try requireRequestID(response, "smoke-route-refresh", context: "route.refresh")
    let routePayload = try payload(response, context: "route.refresh")
    guard try requireString(routePayload, "runtime_device_id", context: "route.refresh") == runtimeDeviceID,
          try requireString(routePayload, "runtime_key_fingerprint", context: "route.refresh") == runtimeKeyFingerprint
    else {
        throw SmokeFailure.message("route.refresh returned route material for a different runtime: \(response)")
    }
    let relayHost = try requireString(routePayload, "relay_host", context: "route.refresh")
    let relayPort = try requireInt(routePayload, "relay_port", context: "route.refresh")
    guard relayHost == expectedEndpoint.host,
          relayPort == Int(expectedEndpoint.port)
    else {
        throw SmokeFailure.message("route.refresh returned a different relay endpoint: \(response)")
    }
    let relayExpiresAt = try requireInt64(routePayload, "relay_expires_at", context: "route.refresh")
    guard relayExpiresAt > Int64(Date().timeIntervalSince1970 * 1000) else {
        throw SmokeFailure.message("route.refresh returned expired route material: \(response)")
    }
    guard let relayPortValue = UInt16(exactly: relayPort) else {
        throw SmokeFailure.message("route.refresh returned invalid relay port: \(response)")
    }
    let relayNonce = try requireString(routePayload, "relay_nonce", context: "route.refresh")
    if expectP2PRouteRefresh {
        try requireP2PRouteRefreshMaterial(routePayload, context: "route.refresh")
    }
    return RelayConfiguration(
        relayID: try requireString(routePayload, "relay_id", context: "route.refresh"),
        relaySecret: try requireString(routePayload, "relay_secret", context: "route.refresh"),
        relayNonce: relayNonce,
        host: relayHost,
        port: relayPortValue
    )
}

func requireP2PRouteRefreshMaterial(_ routePayload: [String: Any], context: String) throws {
    guard try requireString(routePayload, "p2p_class", context: context) == expectedP2PRouteRefresh.routeClass,
          try requireString(routePayload, "p2p_record_id", context: context) == expectedP2PRouteRefresh.recordID,
          try requireString(routePayload, "p2p_encrypted_body", context: context) == expectedP2PRouteRefresh.encryptedBody,
          try requireString(routePayload, "p2p_anti_replay_nonce", context: context) == expectedP2PRouteRefresh.antiReplayNonce,
          try requireInt(routePayload, "p2p_protocol_version", context: context) == expectedP2PRouteRefresh.protocolVersion
    else {
        throw SmokeFailure.message("\(context) returned unexpected P2P rendezvous route material: \(routePayload)")
    }
    let p2pExpiresAt = try requireInt64(routePayload, "p2p_expires_at", context: context)
    guard p2pExpiresAt > Int64(Date().timeIntervalSince1970 * 1000) else {
        throw SmokeFailure.message("\(context) returned expired P2P rendezvous material: \(routePayload)")
    }
}

func clientAuthSignature(
    privateKey: P256.Signing.PrivateKey,
    deviceID: String,
    nonce: String
) throws -> String {
    let authMessage = "AetherLink client auth response v1\n\(deviceID)\n\(nonce)"
    let digest = SHA256.hash(data: Data(authMessage.utf8))
    return try privateKey.signature(for: digest).derRepresentation.base64EncodedString()
}

func rawNonceSignature(privateKey: P256.Signing.PrivateKey, nonce: String) throws -> String {
    let digest = SHA256.hash(data: Data(nonce.utf8))
    return try privateKey.signature(for: digest).derRepresentation.base64EncodedString()
}

func trustedHelloNonce(client: TCPClient, deviceID: String, requestID: String) throws -> String {
    let challenge = try sendAndRead(
        client,
        type: "hello",
        requestID: requestID,
        payload: [
            "device_id": deviceID,
            "device_name": "Smoke Test Client",
            "client_capabilities": ["chat", "streaming", "attachments"]
        ]
    )
    try requireType(challenge, "auth.challenge", context: requestID)
    let challengePayload = try payload(challenge, context: requestID)
    return try requireString(challengePayload, "nonce", context: requestID)
}

func requireAcceptedAuthResponse(
    _ response: [String: Any],
    requestID: String,
    context: String,
    deviceID: String? = nil
) throws {
    try requireType(response, "auth.response", context: context)
    try requireRequestID(response, requestID, context: context)
    let authPayload = try payload(response, context: context)
    try requireBool(authPayload, "accepted", true, context: context)
    if let deviceID, authPayload["device_id"] as? String != deviceID {
        throw SmokeFailure.message("\(context) returned a different device_id: \(response)")
    }
}

func authenticateFreshClient(
    host: String,
    port: UInt16,
    relay: RelayConfiguration?,
    deviceID: String,
    privateKey: P256.Signing.PrivateKey,
    requestPrefix: String
) throws -> TCPClient {
    let client = try connectWithRetry(host: host, port: port, relay: relay)
    do {
        let nonce = try trustedHelloNonce(
            client: client,
            deviceID: deviceID,
            requestID: "\(requestPrefix)-hello"
        )
        let signature = try clientAuthSignature(privateKey: privateKey, deviceID: deviceID, nonce: nonce)
        let authResponse = try sendAndRead(
            client,
            type: "auth.response",
            requestID: "\(requestPrefix)-auth",
            payload: [
                "device_id": deviceID,
                "nonce": nonce,
                "signature": signature
            ]
        )
        try requireAcceptedAuthResponse(
            authResponse,
            requestID: "\(requestPrefix)-auth",
            context: "\(requestPrefix) auth.response",
            deviceID: deviceID
        )
        return client
    } catch {
        client.close()
        throw error
    }
}

func runRejectedPairingChecks(
    host: String,
    port: UInt16,
    relay: RelayConfiguration?,
    pairingNonce: String,
    pairingCode: String,
    deviceID: String,
    publicKeyBase64: String
) throws {
    print("Checking rejected pairing request does not trust the device...")
    let invalidCode = pairingCode == "000000" ? "999999" : "000000"
    do {
        let client = try connectWithRetry(host: host, port: port, relay: relay)
        defer { client.close() }
        let response = try sendAndRead(
            client,
            type: "pairing.request",
            requestID: "smoke-pair-invalid-code",
            payload: [
                "pairing_nonce": pairingNonce,
                "pairing_code": invalidCode,
                "device_id": deviceID,
                "device_name": "AetherLink Invalid Pairing Smoke",
                "public_key": publicKeyBase64
            ]
        )
        try requireRejectedPairingResult(
            response,
            expectedCode: "pairing_invalid",
            requestID: "smoke-pair-invalid-code",
            context: "invalid pairing.request",
            retryable: true
        )
        let rejectionPayload = try payload(response, context: "invalid pairing.request")
        guard try requireInt(rejectionPayload, "failed_attempts", context: "invalid pairing.request") == 1,
              try requireInt(rejectionPayload, "remaining_attempts", context: "invalid pairing.request") >= 1
        else {
            throw SmokeFailure.message("invalid pairing.request did not report a bounded failed-attempt state: \(response)")
        }
        let healthAfterRejection = try sendAndRead(
            client,
            type: "runtime.health",
            requestID: "smoke-pair-invalid-code-health"
        )
        try requireErrorCode(
            healthAfterRejection,
            "authentication_required",
            requestID: "smoke-pair-invalid-code-health",
            context: "runtime.health after invalid pairing.request"
        )
    }

    do {
        let client = try connectWithRetry(host: host, port: port, relay: relay)
        defer { client.close() }
        let response = try sendAndRead(
            client,
            type: "hello",
            requestID: "smoke-invalid-pairing-hello",
            payload: [
                "device_id": deviceID,
                "device_name": "AetherLink Invalid Pairing Smoke",
                "client_capabilities": ["chat", "streaming"]
            ]
        )
        try requireErrorCode(
            response,
            "pairing_required",
            requestID: "smoke-invalid-pairing-hello",
            context: "hello after rejected pairing"
        )
    }
}

func runInvalidPairingIdentityCheck(
    host: String,
    port: UInt16,
    relay: RelayConfiguration?,
    pairingNonce: String,
    pairingCode: String,
    deviceID: String
) throws {
    print("Checking malformed pairing identity does not trust the device...")
    do {
        let client = try connectWithRetry(host: host, port: port, relay: relay)
        defer { client.close() }
        let response = try sendAndRead(
            client,
            type: "pairing.request",
            requestID: "smoke-pair-invalid-identity",
            payload: [
                "pairing_nonce": pairingNonce,
                "pairing_code": pairingCode,
                "device_id": deviceID,
                "device_name": "AetherLink Invalid Identity Smoke",
                "public_key": "not-a-p256-public-key"
            ]
        )
        try requireRejectedPairingResult(
            response,
            expectedCode: "pairing_invalid_device_identity",
            requestID: "smoke-pair-invalid-identity",
            context: "invalid pairing identity",
            retryable: true
        )
        let rejectionPayload = try payload(response, context: "invalid pairing identity")
        guard try requireInt(rejectionPayload, "failed_attempts", context: "invalid pairing identity") == 2,
              try requireInt(rejectionPayload, "remaining_attempts", context: "invalid pairing identity") >= 1
        else {
            throw SmokeFailure.message("invalid pairing identity did not preserve a retryable active session: \(response)")
        }
        let healthAfterRejection = try sendAndRead(
            client,
            type: "runtime.health",
            requestID: "smoke-pair-invalid-identity-health"
        )
        try requireErrorCode(
            healthAfterRejection,
            "authentication_required",
            requestID: "smoke-pair-invalid-identity-health",
            context: "runtime.health after invalid pairing identity"
        )
    }

    do {
        let client = try connectWithRetry(host: host, port: port, relay: relay)
        defer { client.close() }
        let response = try sendAndRead(
            client,
            type: "hello",
            requestID: "smoke-invalid-identity-hello",
            payload: [
                "device_id": deviceID,
                "device_name": "AetherLink Invalid Identity Smoke",
                "client_capabilities": ["chat", "streaming"]
            ]
        )
        try requireErrorCode(
            response,
            "pairing_required",
            requestID: "smoke-invalid-identity-hello",
            context: "hello after invalid pairing identity"
        )
    }
}

func pairTrustedDevice(
    host: String,
    port: UInt16,
    relay: RelayConfiguration?,
    pairingNonce: String,
    pairingCode: String,
    deviceID: String,
    deviceName: String,
    publicKeyBase64: String,
    requestID: String
) throws {
    let pairingClient = try connectWithRetry(host: host, port: port, relay: relay)
    do {
        let pairResponse = try sendAndRead(
            pairingClient,
            type: "pairing.request",
            requestID: requestID,
            payload: [
                "pairing_nonce": pairingNonce,
                "pairing_code": pairingCode,
                "device_id": deviceID,
                "device_name": deviceName,
                "public_key": publicKeyBase64
            ]
        )
        try requireType(pairResponse, "pairing.result", context: "pairing.request")
        try requireRequestID(pairResponse, requestID, context: "pairing.request")
        let pairPayload = try payload(pairResponse, context: "pairing.request")
        try requireBool(pairPayload, "accepted", true, context: "pairing.request")
        pairingClient.close()
    } catch {
        pairingClient.close()
        throw error
    }
}

func runConsumedPairingReuseCheck(
    host: String,
    port: UInt16,
    relay: RelayConfiguration?,
    pairingNonce: String,
    pairingCode: String,
    deviceID: String,
    publicKeyBase64: String
) throws {
    print("Checking consumed pairing QR cannot be reused...")
    do {
        let client = try connectWithRetry(host: host, port: port, relay: relay)
        defer { client.close() }
        let response = try sendAndRead(
            client,
            type: "pairing.request",
            requestID: "smoke-pair-consumed-reuse",
            payload: [
                "pairing_nonce": pairingNonce,
                "pairing_code": pairingCode,
                "device_id": deviceID,
                "device_name": "AetherLink Consumed Pairing Smoke",
                "public_key": publicKeyBase64
            ]
        )
        try requireRejectedPairingResult(
            response,
            expectedCode: "pairing_not_active",
            requestID: "smoke-pair-consumed-reuse",
            context: "consumed pairing.request",
            retryable: false
        )
        let healthAfterRejection = try sendAndRead(
            client,
            type: "runtime.health",
            requestID: "smoke-pair-consumed-health"
        )
        try requireErrorCode(
            healthAfterRejection,
            "authentication_required",
            requestID: "smoke-pair-consumed-health",
            context: "runtime.health after consumed pairing reuse"
        )
    }

    do {
        let client = try connectWithRetry(host: host, port: port, relay: relay)
        defer { client.close() }
        let response = try sendAndRead(
            client,
            type: "hello",
            requestID: "smoke-pair-consumed-hello",
            payload: [
                "device_id": deviceID,
                "device_name": "AetherLink Consumed Pairing Smoke",
                "client_capabilities": ["chat", "streaming"]
            ]
        )
        try requireErrorCode(
            response,
            "pairing_required",
            requestID: "smoke-pair-consumed-hello",
            context: "hello after consumed pairing reuse"
        )
    }
}

func runRawNonceAuthRejectionCheck(
    host: String,
    port: UInt16,
    relay: RelayConfiguration?,
    deviceID: String,
    privateKey: P256.Signing.PrivateKey
) throws {
    print("Checking raw nonce auth signature rejection...")
    let client = try connectWithRetry(host: host, port: port, relay: relay)
    defer { client.close() }
    let nonce = try trustedHelloNonce(
        client: client,
        deviceID: deviceID,
        requestID: "smoke-auth-raw-nonce-hello"
    )
    let signature = try rawNonceSignature(privateKey: privateKey, nonce: nonce)
    let response = try sendAndRead(
        client,
        type: "auth.response",
        requestID: "smoke-auth-raw-nonce-response",
        payload: [
            "device_id": deviceID,
            "nonce": nonce,
            "signature": signature
        ]
    )
    try requireErrorCode(
        response,
        "authentication_failed",
        requestID: "smoke-auth-raw-nonce-response",
        context: "raw nonce auth.response"
    )

    let modelsAfterRawNonce = try sendAndRead(
        client,
        type: "models.list",
        requestID: "smoke-auth-raw-nonce-models"
    )
    try requireErrorCode(
        modelsAfterRawNonce,
        "authentication_required",
        requestID: "smoke-auth-raw-nonce-models",
        context: "models.list after raw nonce auth.response"
    )
}

func runAuthReplayAndSupersededChallengeChecks(
    host: String,
    port: UInt16,
    relay: RelayConfiguration?,
    deviceID: String,
    privateKey: P256.Signing.PrivateKey
) throws {
    print("Checking auth replay and superseded challenge rejection...")
    do {
        let client = try connectWithRetry(host: host, port: port, relay: relay)
        defer { client.close() }
        let nonce = try trustedHelloNonce(
            client: client,
            deviceID: deviceID,
            requestID: "smoke-auth-replay-hello"
        )
        let signature = try clientAuthSignature(privateKey: privateKey, deviceID: deviceID, nonce: nonce)
        let authPayload: [String: Any] = [
            "device_id": deviceID,
            "nonce": nonce,
            "signature": signature
        ]
        let firstAuthResponse = try sendAndRead(
            client,
            type: "auth.response",
            requestID: "smoke-auth-replay-first",
            payload: authPayload
        )
        try requireAcceptedAuthResponse(
            firstAuthResponse,
            requestID: "smoke-auth-replay-first",
            context: "auth replay first auth.response",
            deviceID: deviceID
        )

        let replayResponse = try sendAndRead(
            client,
            type: "auth.response",
            requestID: "smoke-auth-replay-second",
            payload: authPayload
        )
        try requireErrorCode(
            replayResponse,
            "authentication_failed",
            requestID: "smoke-auth-replay-second",
            context: "replayed auth.response"
        )

        let modelsAfterReplay = try sendAndRead(
            client,
            type: "models.list",
            requestID: "smoke-auth-replay-models"
        )
        try requireType(modelsAfterReplay, "models.list", context: "models.list after replayed auth.response")
    }

    do {
        let client = try connectWithRetry(host: host, port: port, relay: relay)
        defer { client.close() }
        let staleNonce = try trustedHelloNonce(
            client: client,
            deviceID: deviceID,
            requestID: "smoke-auth-superseded-hello-1"
        )
        let freshNonce = try trustedHelloNonce(
            client: client,
            deviceID: deviceID,
            requestID: "smoke-auth-superseded-hello-2"
        )
        guard staleNonce != freshNonce else {
            throw SmokeFailure.message("superseded auth smoke expected distinct challenge nonces")
        }

        let staleSignature = try clientAuthSignature(privateKey: privateKey, deviceID: deviceID, nonce: staleNonce)
        let staleAuthResponse = try sendAndRead(
            client,
            type: "auth.response",
            requestID: "smoke-auth-superseded-stale",
            payload: [
                "device_id": deviceID,
                "nonce": staleNonce,
                "signature": staleSignature
            ]
        )
        try requireErrorCode(
            staleAuthResponse,
            "authentication_failed",
            requestID: "smoke-auth-superseded-stale",
            context: "superseded stale auth.response"
        )

        let freshSignature = try clientAuthSignature(privateKey: privateKey, deviceID: deviceID, nonce: freshNonce)
        let freshAuthResponse = try sendAndRead(
            client,
            type: "auth.response",
            requestID: "smoke-auth-superseded-fresh",
            payload: [
                "device_id": deviceID,
                "nonce": freshNonce,
                "signature": freshSignature
            ]
        )
        try requireAcceptedAuthResponse(
            freshAuthResponse,
            requestID: "smoke-auth-superseded-fresh",
            context: "superseded fresh auth.response",
            deviceID: deviceID
        )

        let healthAfterSuperseded = try sendAndRead(
            client,
            type: "runtime.health",
            requestID: "smoke-auth-superseded-health"
        )
        try requireType(healthAfterSuperseded, "runtime.health", context: "runtime.health after superseded auth")
    }
}

func runUnauthenticatedAndUntrustedRejectionChecks(
    host: String,
    port: UInt16,
    relay: RelayConfiguration?
) throws {
    print("Checking unauthenticated runtime command rejection...")
    let unauthenticatedCommands: [(type: String, requestID: String, payload: [String: Any])] = [
        ("models.list", "smoke-unauthenticated-models", [:]),
        ("models.pull", "smoke-unauthenticated-pull", [:]),
        (
            "chat.send",
            "smoke-unauthenticated-chat",
            [
                "session_id": smokeSessionID,
                "model": "dev-mock",
                "messages": [
                    ["role": "user", "content": "This must not reach the backend."]
                ]
            ]
        ),
        ("chat.cancel", "smoke-unauthenticated-cancel", ["target_request_id": "smoke-chat"]),
        ("route.refresh", "smoke-unauthenticated-route-refresh", [:]),
        ("chat.sessions.list", "smoke-unauthenticated-sessions", [:]),
        ("chat.messages.list", "smoke-unauthenticated-messages", [:]),
        ("chat.title.request", "smoke-unauthenticated-title", [:]),
        ("chat.session.rename", "smoke-unauthenticated-rename", [:]),
        ("chat.session.archive", "smoke-unauthenticated-archive", [:]),
        ("chat.session.restore", "smoke-unauthenticated-restore", [:]),
        ("chat.session.delete", "smoke-unauthenticated-delete", [:]),
        ("memory.list", "smoke-unauthenticated-memory", [:]),
        ("memory.upsert", "smoke-unauthenticated-memory-upsert", [:]),
        ("memory.delete", "smoke-unauthenticated-memory-delete", [:]),
        ("memory.summary.drafts.list", "smoke-unauthenticated-memory-summary-drafts", [:]),
        ("memory.summary.draft.approve", "smoke-unauthenticated-memory-summary-approve", [:]),
        ("memory.summary.draft.dismiss", "smoke-unauthenticated-memory-summary-dismiss", [:])
    ]
    for command in unauthenticatedCommands {
        let client = try connectWithRetry(host: host, port: port, relay: relay)
        defer { client.close() }
        let response = try sendAndRead(
            client,
            type: command.type,
            requestID: command.requestID,
            payload: command.payload
        )
        try requireErrorCode(
            response,
            "authentication_required",
            requestID: command.requestID,
            context: "unauthenticated \(command.type)"
        )
    }

    print("Checking untrusted client hello rejection...")
    let client = try connectWithRetry(host: host, port: port, relay: relay)
    defer { client.close() }
    let response = try sendAndRead(
        client,
        type: "hello",
        requestID: "smoke-untrusted-hello",
        payload: [
            "device_id": "aetherlink-auth-smoke-untrusted-device",
            "device_name": "Untrusted Smoke Client",
            "client_capabilities": ["chat", "streaming"]
        ]
    )
    try requireErrorCode(
        response,
        "pairing_required",
        requestID: "smoke-untrusted-hello",
        context: "untrusted hello"
    )
}

func runTrustedDeviceRevocationCheck(client: TCPClient, trustedDevicesFile: URL) throws {
    print("Checking trusted-device revocation clears an authenticated session...")
    guard FileManager.default.fileExists(atPath: trustedDevicesFile.path) else {
        throw SmokeFailure.message("Trusted-device store was missing before revocation check: \(trustedDevicesFile.path)")
    }
    try Data("[]".utf8).write(to: trustedDevicesFile, options: [.atomic])
    try FileManager.default.setAttributes(
        [.posixPermissions: 0o600],
        ofItemAtPath: trustedDevicesFile.standardizedFileURL.path
    )

    let revokedHealth = try sendAndRead(
        client,
        type: "runtime.health",
        requestID: "smoke-revoked-health"
    )
    try requireErrorCode(
        revokedHealth,
        "pairing_required",
        requestID: "smoke-revoked-health",
        context: "runtime.health after trusted-device revocation"
    )

    let clearedSessionModels = try sendAndRead(
        client,
        type: "models.list",
        requestID: "smoke-revoked-models"
    )
    try requireErrorCode(
        clearedSessionModels,
        "authentication_required",
        requestID: "smoke-revoked-models",
        context: "models.list after trusted-device revocation cleared session"
    )
}

func fetchLocalOllamaJSON(path: String) throws -> [String: Any] {
    guard let url = URL(string: "http://127.0.0.1:11434\(path)") else {
        throw SmokeFailure.message("Invalid local Ollama path: \(path)")
    }

    let semaphore = DispatchSemaphore(value: 0)
    final class RequestBox {
        var data: Data?
        var response: URLResponse?
        var error: Error?
    }
    let box = RequestBox()
    let task = URLSession.shared.dataTask(with: url) { data, response, error in
        box.data = data
        box.response = response
        box.error = error
        semaphore.signal()
    }
    task.resume()
    guard semaphore.wait(timeout: .now() + 5) == .success else {
        task.cancel()
        throw SmokeFailure.message("Timed out querying local Ollama \(path)")
    }
    if let error = box.error {
        throw SmokeFailure.message("Could not query local Ollama \(path): \(error.localizedDescription)")
    }
    guard let httpResponse = box.response as? HTTPURLResponse else {
        throw SmokeFailure.message("Local Ollama \(path) did not return HTTP")
    }
    guard (200..<300).contains(httpResponse.statusCode) else {
        throw SmokeFailure.message("Local Ollama \(path) returned HTTP \(httpResponse.statusCode)")
    }
    guard let data = box.data,
          let object = try JSONSerialization.jsonObject(with: data) as? [String: Any]
    else {
        throw SmokeFailure.message("Local Ollama \(path) did not return a JSON object")
    }
    return object
}

func ollamaModelNames(from object: [String: Any], context: String) throws -> Set<String> {
    let models = try ollamaModelRecords(from: object, context: context)
    let names = models.compactMap { model in
        (model["name"] as? String) ?? (model["model"] as? String)
    }
    return Set(names)
}

func ollamaModelRecords(from object: [String: Any], context: String) throws -> [[String: Any]] {
    guard let models = object["models"] as? [[String: Any]] else {
        throw SmokeFailure.message("\(context) did not include a models array: \(object)")
    }
    return models
}

func ollamaModelName(_ model: [String: Any], context: String) throws -> String {
    if let name = model["name"] as? String, !name.isEmpty {
        return name
    }
    if let modelName = model["model"] as? String, !modelName.isEmpty {
        return modelName
    }
    throw SmokeFailure.message("\(context) model had no name/model field: \(model)")
}

func isCloudOllamaModel(_ model: [String: Any], name: String) -> Bool {
    if let remoteModel = model["remote_model"] as? String, !remoteModel.isEmpty {
        return true
    }
    if let remoteHost = model["remote_host"] as? String, !remoteHost.isEmpty {
        return true
    }
    let lowered = name.lowercased()
    return lowered.hasSuffix(":cloud") || lowered.hasSuffix("-cloud")
}

func canonicalModelName(_ name: String) -> String {
    if name.hasSuffix(":latest") {
        return String(name.dropLast(":latest".count))
    }
    return name
}

func startServer(
    port: UInt16,
    trustedDevicesFile: URL,
    backendMode: BackendMode,
    relay: RelayConfiguration?,
    bootstrapRelay: RelayEndpoint?,
    expectP2PRouteRefresh: Bool,
    mockUnloadEventFile: URL?
) throws -> Process {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    process.arguments = ["\(try runAndCapture(["swift", "build", "--show-bin-path"]))/RuntimeDevServer"]
    var environment = ProcessInfo.processInfo.environment
    environment["LOCAL_AGENT_BRIDGE_PORT"] = String(port)
    switch backendMode {
    case .mock:
        environment["LOCAL_AGENT_BRIDGE_MOCK_BACKEND"] = "1"
        environment["AETHERLINK_DEV_MOCK_AGGREGATE_RESIDENCY"] = "1"
        environment["AETHERLINK_DEV_MOCK_RESIDENCY_IDLE_MS"] = "3000"
        environment["AETHERLINK_DEV_MOCK_UNLOAD_EVENT_FILE"] = mockUnloadEventFile?.path
        environment["AETHERLINK_DEV_MOCK_UNLOAD_FAILURES"] = "ollama|\(smokeUnloadFailureModelID)"
    case .realOllama:
        environment["LOCAL_AGENT_BRIDGE_MOCK_BACKEND"] = nil
        environment["AETHERLINK_DEV_MOCK_AGGREGATE_RESIDENCY"] = nil
        environment["AETHERLINK_DEV_MOCK_RESIDENCY_IDLE_MS"] = nil
        environment["AETHERLINK_DEV_MOCK_UNLOAD_EVENT_FILE"] = nil
        environment["AETHERLINK_DEV_MOCK_UNLOAD_FAILURES"] = nil
    }
    environment["AETHERLINK_DEV_PAIRING"] = "1"
    environment["AETHERLINK_DEV_TRUSTED_DEVICES_FILE"] = trustedDevicesFile.path
    environment["AETHERLINK_DEV_RUNTIME_CHAT_SQLITE_FILE"] = trustedDevicesFile
        .deletingLastPathComponent()
        .appendingPathComponent("runtime-chat-events.sqlite")
        .path
    environment["AETHERLINK_DEV_RUNTIME_CHAT_JSONL_FILE"] = trustedDevicesFile
        .deletingLastPathComponent()
        .appendingPathComponent("runtime-chat-events.jsonl")
        .path
    environment["AETHERLINK_DEV_RUNTIME_PUBLIC_KEY"] = "aetherlink-smoke-runtime-public-key"
    environment["AETHERLINK_DEV_RUNTIME_KEY_FINGERPRINT"] = "aetherlink-smoke-runtime-fingerprint"
    if expectP2PRouteRefresh {
        environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P"] = "1"
        environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_CLASS"] = expectedP2PRouteRefresh.routeClass
        environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_RECORD_ID"] = expectedP2PRouteRefresh.recordID
        environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_ENCRYPTED_BODY"] = expectedP2PRouteRefresh.encryptedBody
        environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_NONCE"] = expectedP2PRouteRefresh.antiReplayNonce
        environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_PROTOCOL_VERSION"] = String(expectedP2PRouteRefresh.protocolVersion)
    }
    if let relay {
        environment["AETHERLINK_RELAY_HOST"] = relay.host
        environment["AETHERLINK_RELAY_PORT"] = String(relay.port)
        environment["AETHERLINK_RELAY_ID"] = relay.relayID
        environment["AETHERLINK_RELAY_SECRET"] = relay.relaySecret
    }
    if let bootstrapRelay {
        environment["AETHERLINK_BOOTSTRAP_RELAY_HOST"] = bootstrapRelay.host
        environment["AETHERLINK_BOOTSTRAP_RELAY_PORT"] = String(bootstrapRelay.port)
        environment["AETHERLINK_RELAY_HOST"] = nil
        environment["AETHERLINK_RELAY_PORT"] = nil
        environment["AETHERLINK_RELAY_ID"] = nil
        environment["AETHERLINK_RELAY_SECRET"] = nil
    }
    process.environment = environment
    return process
}

func readStoppedChatStream(client: TCPClient, requestID: String, context: String) throws -> String {
    var streamedText = ""
    while true {
        let response = try client.readEnvelope()
        try assertNoBackendLeak(response, context: context)
        try requireRequestID(response, requestID, context: context)
        let responseType = response["type"] as? String
        if responseType == "chat.delta" {
            streamedText += (try payload(response, context: "\(context) delta")["delta"] as? String) ?? ""
        } else if responseType == "chat.done" {
            let donePayload = try payload(response, context: "\(context) done")
            guard donePayload["finish_reason"] as? String == "stop" else {
                throw SmokeFailure.message("\(context) chat.done did not finish with stop: \(response)")
            }
            return streamedText
        } else {
            throw SmokeFailure.message("Unexpected \(context) response: \(response)")
        }
    }
}

func relayPlaintextBoundaryMarkers() -> [String] {
    return [
        "pairing.request",
        "smoke-pair-invalid-code-health",
        "pairing_invalid",
        "smoke-pair-invalid-identity",
        "smoke-invalid-identity-hello",
        "pairing_invalid_device_identity",
        "AetherLink Invalid Identity Smoke",
        "smoke-pair-consumed",
        "smoke-pair-consumed-health",
        "pairing_not_active",
        "No active pairing session is available.",
        "AetherLink Consumed Pairing Smoke",
        "auth.challenge",
        "auth.response",
        "authentication_failed",
        "authentication_required",
        "Could not authenticate this device.",
        "runtime.health",
        "models.list",
        "models.pull",
        "chat.send",
        "chat.cancel",
        "chat.sessions.list",
        "chat.messages.list",
        "chat.title.request",
        "chat.session.rename",
        "chat.session.archive",
        "chat.session.restore",
        "chat.session.delete",
        "memory.upsert",
        "memory.list",
        "memory.delete",
        "memory.summary.drafts.list",
        "memory.summary.draft.approve",
        "memory.summary.draft.dismiss",
        "smoke-memory-summary-drafts",
        "smoke-memory-summary-approve-unavailable",
        "smoke-memory-summary-dismiss-unavailable",
        "memory_summary_draft_unavailable",
        "smoke-missing-memory-summary-draft",
        "smoke-auth-raw-nonce",
        "smoke-auth-replay",
        "smoke-auth-superseded",
        "smoke-owner",
        "Device A private smoke memory.",
        "Device B private smoke memory.",
        "Use device A memory.",
        "Use device B memory.",
        "B cannot rename A",
        "smoke-sessions-search-metadata",
        "hello smoke test",
        "matched_fields",
        "Say hello from the smoke test.",
        smokePulledModelPrompt,
        "smoke-chat-pulled-model",
        "Summarize the attached smoke note.",
        smokeImageAttachmentPrompt,
        smokeImageAttachmentName,
        smokeImageAttachmentBase64,
        "smoke-chat-image-non-vision",
        "smoke-chat-image-vision",
        "unsupported_attachment",
        "Image attachments require a vision-capable model.",
        "smoke-chat-missing-model-residency",
        "model_not_installed",
        "dev-missing-residency",
        "smoke-health-residency-repeat",
        "smoke-health-residency-missing-model",
        "smoke-health-residency-idle",
        "smoke-health-residency-failure-source",
        "smoke-chat-unload-failure-source",
        "Activate a model that will fail unload.",
        "smoke-chat-unload-failure-switch",
        "Switch after a mock unload failure.",
        "smoke-health-residency-unload-failure",
        "last_unload_failure",
        "model_switch",
        "Create a session for lifecycle smoke.",
        "Runtime smoke lifecycle",
        smokeDocumentAttachmentText,
        Data(smokeDocumentAttachmentText.utf8).base64EncodedString(),
        "Prefers smoke-tested concise answers.",
        "Mock streaming response.",
        "Attachment received.",
        "dev-mock",
        smokeVisionModelID,
        smokeUnloadFailureModelID,
        smokePulledModelID
    ]
}

func verifyRelayCiphertextBoundaryIfNeeded() throws {
    guard RelayCiphertextBoundary.enabled else { return }
    print("Checking relay ciphertext boundary...")
    try RelayCiphertextBoundary.requireNoPlaintextMarkers(relayPlaintextBoundaryMarkers())
}

func mockUnloadEvents(from fileURL: URL) throws -> [String] {
    guard FileManager.default.fileExists(atPath: fileURL.path) else {
        return []
    }
    let text = try String(contentsOf: fileURL, encoding: .utf8)
    return text
        .split(separator: "\n")
        .map(String.init)
        .filter { !$0.isEmpty }
}

func waitForMockUnloadEvent(_ expected: String, fileURL: URL, context: String) throws {
    let deadline = Date().addingTimeInterval(8)
    var latestEvents: [String] = []
    while Date() < deadline {
        latestEvents = try mockUnloadEvents(from: fileURL)
        if latestEvents.contains(expected) {
            return
        }
        usleep(100_000)
    }
    throw SmokeFailure.message("\(context) did not observe expected unload event \(expected). Events: \(latestEvents)")
}

func requireNoMockUnloadEvents(_ fileURL: URL, context: String) throws {
    let events = try mockUnloadEvents(from: fileURL)
    guard events.isEmpty else {
        throw SmokeFailure.message("\(context) observed unexpected model unload event(s): \(events)")
    }
}

func resetMockUnloadEvents(_ fileURL: URL, context: String) throws {
    let fileManager = FileManager.default
    guard fileManager.fileExists(atPath: fileURL.path) else { return }
    do {
        try fileManager.removeItem(at: fileURL)
    } catch {
        throw SmokeFailure.message("\(context) could not reset model unload event file: \(error.localizedDescription)")
    }
}

func requireRuntimeHealthModelResidency(
    client: TCPClient,
    requestID: String,
    expectedActiveProvider: String?,
    expectedActiveModelID: String?,
    context: String
) throws -> [String: Any] {
    let deadline = Date().addingTimeInterval(6)
    var attempt = 0
    while true {
        let healthRequestID = attempt == 0 ? requestID : "\(requestID)-retry-\(attempt)"
        do {
            let health = try sendAndRead(client, type: "runtime.health", requestID: healthRequestID)
            try requireType(health, "runtime.health", context: context)
            try requireRequestID(health, healthRequestID, context: context)
            let healthPayload = try payload(health, context: context)
            guard let residency = healthPayload["model_residency"] as? [String: Any] else {
                throw SmokeFailure.message("\(context) did not include model_residency: \(health)")
            }
            try requireBool(residency, "supported", true, context: context)
            let inFlightGenerations = try requireInt64(residency, "in_flight_generations", context: context)
            guard inFlightGenerations == 0 else {
                throw SmokeFailure.message("\(context) expected no in-flight generations, got \(inFlightGenerations): \(health)")
            }
            let idleUnloadDelaySeconds = try requireInt64(residency, "idle_unload_delay_seconds", context: context)
            guard idleUnloadDelaySeconds > 0 else {
                throw SmokeFailure.message("\(context) expected positive idle_unload_delay_seconds, got \(idleUnloadDelaySeconds): \(health)")
            }
            if let expectedActiveProvider {
                guard residency["active_provider"] as? String == expectedActiveProvider else {
                    throw SmokeFailure.message("\(context) expected active_provider \(expectedActiveProvider): \(health)")
                }
            } else if residency["active_provider"] != nil {
                throw SmokeFailure.message("\(context) expected no active_provider: \(health)")
            }
            if let expectedActiveModelID {
                guard residency["active_model_id"] as? String == expectedActiveModelID else {
                    throw SmokeFailure.message("\(context) expected active_model_id \(expectedActiveModelID): \(health)")
                }
            } else if residency["active_model_id"] != nil {
                throw SmokeFailure.message("\(context) expected no active_model_id: \(health)")
            }
            return residency
        } catch let failure as SmokeFailure {
            guard Date() < deadline else {
                throw failure
            }
            attempt += 1
            usleep(100_000)
        }
    }
}

func requireModelResidencyUnloadFailure(
    _ residency: [String: Any],
    expectedProvider: String,
    expectedModelID: String,
    expectedReason: String,
    context: String
) throws {
    guard let failure = residency["last_unload_failure"] as? [String: Any] else {
        throw SmokeFailure.message("\(context) did not include last_unload_failure: \(residency)")
    }
    let keys = Set(failure.keys)
    let expectedKeys: Set<String> = ["provider", "model_id", "reason"]
    guard keys == expectedKeys else {
        throw SmokeFailure.message("\(context) expected only provider/model_id/reason keys, got \(keys): \(failure)")
    }
    guard failure["provider"] as? String == expectedProvider,
          failure["model_id"] as? String == expectedModelID,
          failure["reason"] as? String == expectedReason else {
        throw SmokeFailure.message(
            "\(context) expected \(expectedProvider)/\(expectedModelID)/\(expectedReason), got \(failure)"
        )
    }
}

func runAuthenticatedModelResidencyChecks(client: TCPClient, unloadEventFile: URL) throws {
    print("Checking authenticated model residency unload policy...")
    try resetMockUnloadEvents(unloadEventFile, context: "model residency setup")
    try requireNoMockUnloadEvents(unloadEventFile, context: "model residency before same-model repeat")

    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-repeat",
        payload: [
            "session_id": smokeResidencySessionID,
            "model": "dev-mock",
            "messages": [
                ["role": "user", "content": "Repeat the same model before switching."]
            ]
        ]
    ))
    let repeatText = try readStoppedChatStream(
        client: client,
        requestID: "smoke-chat-repeat",
        context: "smoke-chat-repeat"
    )
    guard repeatText.contains("Mock streaming response.") else {
        throw SmokeFailure.message("same-model repeat did not stream mock text: \(repeatText)")
    }
    try requireNoMockUnloadEvents(unloadEventFile, context: "model residency same-model repeat")
    _ = try requireRuntimeHealthModelResidency(
        client: client,
        requestID: "smoke-health-residency-repeat",
        expectedActiveProvider: "ollama",
        expectedActiveModelID: "dev-mock",
        context: "model residency repeat runtime.health"
    )

    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-missing-model-residency",
        payload: [
            "session_id": smokeResidencySessionID,
            "model": "dev-missing-residency",
            "messages": [
                ["role": "user", "content": "Rejected model selection must not disturb residency."]
            ]
        ]
    ))
    let missingModelError = try client.readEnvelope()
    try assertNoBackendLeak(missingModelError, context: "smoke-chat-missing-model-residency")
    try requireErrorCode(
        missingModelError,
        "model_not_installed",
        requestID: "smoke-chat-missing-model-residency",
        context: "smoke-chat-missing-model-residency"
    )
    try requireNoMockUnloadEvents(unloadEventFile, context: "model residency missing-model rejection")
    _ = try requireRuntimeHealthModelResidency(
        client: client,
        requestID: "smoke-health-residency-missing-model",
        expectedActiveProvider: "ollama",
        expectedActiveModelID: "dev-mock",
        context: "model residency missing-model runtime.health"
    )

    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-model-switch",
        payload: [
            "session_id": smokeResidencySessionID,
            "model": "lm_studio:dev-mock-alt",
            "messages": [
                ["role": "user", "content": "Switch providers to verify model unload."]
            ]
        ]
    ))
    let switchText = try readStoppedChatStream(
        client: client,
        requestID: "smoke-chat-model-switch",
        context: "smoke-chat-model-switch"
    )
    guard switchText.contains("Mock streaming response.") else {
        throw SmokeFailure.message("model-switch chat did not stream mock text: \(switchText)")
    }
    try waitForMockUnloadEvent(
        "ollama|dev-mock",
        fileURL: unloadEventFile,
        context: "model residency model-switch unload"
    )
    try waitForMockUnloadEvent(
        "lm_studio|dev-mock-alt",
        fileURL: unloadEventFile,
        context: "model residency idle unload"
    )
    _ = try requireRuntimeHealthModelResidency(
        client: client,
        requestID: "smoke-health-residency-idle",
        expectedActiveProvider: nil,
        expectedActiveModelID: nil,
        context: "model residency idle runtime.health"
    )

    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-unload-failure-source",
        payload: [
            "session_id": smokeResidencySessionID,
            "model": smokeUnloadFailureModelID,
            "messages": [
                ["role": "user", "content": "Activate a model that will fail unload."]
            ]
        ]
    ))
    let unloadFailureSourceText = try readStoppedChatStream(
        client: client,
        requestID: "smoke-chat-unload-failure-source",
        context: "smoke-chat-unload-failure-source"
    )
    guard unloadFailureSourceText.contains("Mock streaming response.") else {
        throw SmokeFailure.message("unload-failure source chat did not stream mock text: \(unloadFailureSourceText)")
    }
    _ = try requireRuntimeHealthModelResidency(
        client: client,
        requestID: "smoke-health-residency-failure-source",
        expectedActiveProvider: "ollama",
        expectedActiveModelID: smokeUnloadFailureModelID,
        context: "model residency unload-failure source runtime.health"
    )

    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-unload-failure-switch",
        payload: [
            "session_id": smokeResidencySessionID,
            "model": "lm_studio:dev-mock-alt",
            "messages": [
                ["role": "user", "content": "Switch after a mock unload failure."]
            ]
        ]
    ))
    let unloadFailureSwitchText = try readStoppedChatStream(
        client: client,
        requestID: "smoke-chat-unload-failure-switch",
        context: "smoke-chat-unload-failure-switch"
    )
    guard unloadFailureSwitchText.contains("Mock streaming response.") else {
        throw SmokeFailure.message("unload-failure switch chat did not stream mock text: \(unloadFailureSwitchText)")
    }
    let unloadFailureResidency = try requireRuntimeHealthModelResidency(
        client: client,
        requestID: "smoke-health-residency-unload-failure",
        expectedActiveProvider: "lm_studio",
        expectedActiveModelID: "dev-mock-alt",
        context: "model residency unload-failure runtime.health"
    )
    try requireModelResidencyUnloadFailure(
        unloadFailureResidency,
        expectedProvider: "ollama",
        expectedModelID: smokeUnloadFailureModelID,
        expectedReason: "model_switch",
        context: "model residency unload-failure runtime.health"
    )
}

func requireDictionaryArray(_ object: [String: Any], key: String, context: String) throws -> [[String: Any]] {
    guard let array = object[key] as? [[String: Any]] else {
        throw SmokeFailure.message("\(context) expected \(key) array of objects: \(object)")
    }
    return array
}

func requireStringArray(_ object: [String: Any], key: String, context: String) throws -> [String] {
    guard let array = object[key] as? [String] else {
        throw SmokeFailure.message("\(context) expected \(key) array of strings: \(object)")
    }
    return array
}

func requireSessionSummary(_ sessions: [[String: Any]], sessionID: String, context: String) throws -> [String: Any] {
    guard let session = sessions.first(where: { $0["session_id"] as? String == sessionID }) else {
        throw SmokeFailure.message("\(context) did not include \(sessionID): \(sessions)")
    }
    return session
}

func requireNoSession(_ sessions: [[String: Any]], sessionID: String, context: String) throws {
    guard !sessions.contains(where: { $0["session_id"] as? String == sessionID }) else {
        throw SmokeFailure.message("\(context) unexpectedly included \(sessionID): \(sessions)")
    }
}

func requireSearchMetadata(
    _ session: [String: Any],
    expectedRank: Int,
    snippetContains expectedSnippet: String,
    matchedField expectedMatchedField: String,
    context: String
) throws {
    guard let search = session["search"] as? [String: Any] else {
        throw SmokeFailure.message("\(context) expected search metadata: \(session)")
    }
    let rank = try requireInt(search, "rank", context: context)
    guard rank == expectedRank else {
        throw SmokeFailure.message("\(context) expected search rank \(expectedRank), got \(rank): \(session)")
    }
    let snippet = try requireString(search, "snippet", context: context)
    guard snippet.contains(expectedSnippet) else {
        throw SmokeFailure.message("\(context) expected snippet containing \(expectedSnippet), got \(snippet)")
    }
    let matchedFields = try requireStringArray(search, key: "matched_fields", context: context)
    guard matchedFields.contains(expectedMatchedField) else {
        throw SmokeFailure.message("\(context) expected matched field \(expectedMatchedField), got \(matchedFields)")
    }
}

func listChatSessions(
    client: TCPClient,
    requestID: String,
    includeArchived: Bool = false,
    query: String? = nil
) throws -> [[String: Any]] {
    var requestPayload: [String: Any] = [
        "include_archived": includeArchived,
        "limit": 20
    ]
    if let query, !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
        requestPayload["query"] = query
    }
    let response = try sendAndRead(
        client,
        type: "chat.sessions.list",
        requestID: requestID,
        payload: requestPayload
    )
    try requireType(response, "chat.sessions.list", context: requestID)
    try requireRequestID(response, requestID, context: requestID)
    let listPayload = try payload(response, context: requestID)
    return try requireDictionaryArray(listPayload, key: "sessions", context: requestID)
}

func listChatMessages(client: TCPClient, requestID: String, sessionID: String) throws -> [[String: Any]] {
    let response = try sendAndRead(
        client,
        type: "chat.messages.list",
        requestID: requestID,
        payload: [
            "session_id": sessionID,
            "limit": 20
        ]
    )
    try requireType(response, "chat.messages.list", context: requestID)
    try requireRequestID(response, requestID, context: requestID)
    let messagesPayload = try payload(response, context: requestID)
    guard messagesPayload["session_id"] as? String == sessionID else {
        throw SmokeFailure.message("\(requestID) returned a different session id: \(response)")
    }
    return try requireDictionaryArray(messagesPayload, key: "messages", context: requestID)
}

func listMemoryEntries(client: TCPClient, requestID: String) throws -> [[String: Any]] {
    let response = try sendAndRead(client, type: "memory.list", requestID: requestID)
    try requireType(response, "memory.list", context: requestID)
    try requireRequestID(response, requestID, context: requestID)
    let memoryPayload = try payload(response, context: requestID)
    return try requireDictionaryArray(memoryPayload, key: "entries", context: requestID)
}

func requireOnlyMemoryEntry(
    _ entries: [[String: Any]],
    id: String,
    content: String,
    context: String
) throws {
    guard entries.count == 1,
          entries.first?["id"] as? String == id,
          entries.first?["content"] as? String == content,
          entries.first?["enabled"] as? Bool == true
    else {
        throw SmokeFailure.message("\(context) expected one enabled memory entry \(id): \(entries)")
    }
}

func requireEmptyMessages(_ messages: [[String: Any]], context: String) throws {
    guard messages.isEmpty else {
        throw SmokeFailure.message("\(context) expected no visible messages: \(messages)")
    }
}

func runAuthenticatedTitleAndSessionLifecycleChecks(client: TCPClient) throws {
    print("Checking authenticated chat title and session lifecycle...")
    try client.send(envelope(
        "chat.send",
        requestID: "smoke-session-lifecycle-seed",
        payload: [
            "session_id": smokeLifecycleSessionID,
            "model": "dev-mock",
            "messages": [
                ["role": "user", "content": "Create a session for lifecycle smoke."]
            ]
        ]
    ))
    let seedText = try readStoppedChatStream(
        client: client,
        requestID: "smoke-session-lifecycle-seed",
        context: "smoke-session-lifecycle-seed"
    )
    guard seedText.contains("Mock streaming response.") else {
        throw SmokeFailure.message("lifecycle seed chat did not stream mock text: \(seedText)")
    }

    let titleResponse = try sendAndRead(
        client,
        type: "chat.title.request",
        requestID: "smoke-title",
        payload: [
            "session_id": smokeTitleSessionID,
            "model": "dev-mock",
            "locale": "en",
            "messages": [
                ["role": "user", "content": "Create a session for lifecycle smoke."],
                ["role": "assistant", "content": "Mock streaming response."]
            ]
        ]
    )
    try requireType(titleResponse, "chat.title.result", context: "chat.title.request")
    try requireRequestID(titleResponse, "smoke-title", context: "chat.title.request")
    let titlePayload = try payload(titleResponse, context: "chat.title.request")
    guard titlePayload["title"] as? String == "Mock streaming response." else {
        throw SmokeFailure.message("chat.title.request returned an unexpected title: \(titleResponse)")
    }

    let renamedTitle = "Runtime smoke lifecycle"
    let renameResponse = try sendAndRead(
        client,
        type: "chat.session.rename",
        requestID: "smoke-session-rename",
        payload: [
            "session_id": smokeLifecycleSessionID,
            "title": " \(renamedTitle) "
        ]
    )
    try requireType(renameResponse, "chat.session.rename", context: "chat.session.rename")
    try requireRequestID(renameResponse, "smoke-session-rename", context: "chat.session.rename")
    let renamePayload = try payload(renameResponse, context: "chat.session.rename")
    guard renamePayload["session_id"] as? String == smokeLifecycleSessionID,
          renamePayload["title"] as? String == renamedTitle,
          renamePayload["renamed_at"] is String
    else {
        throw SmokeFailure.message("chat.session.rename returned an unexpected payload: \(renameResponse)")
    }

    let renamedSessions = try listChatSessions(client: client, requestID: "smoke-sessions-after-rename")
    let renamedSession = try requireSessionSummary(
        renamedSessions,
        sessionID: smokeLifecycleSessionID,
        context: "chat.sessions.list after rename"
    )
    guard renamedSession["title"] as? String == renamedTitle,
          renamedSession["status"] as? String == "active"
    else {
        throw SmokeFailure.message("chat.session.rename did not update active session summary: \(renamedSession)")
    }

    let archiveResponse = try sendAndRead(
        client,
        type: "chat.session.archive",
        requestID: "smoke-session-archive",
        payload: ["session_id": smokeLifecycleSessionID]
    )
    try requireType(archiveResponse, "chat.session.archive", context: "chat.session.archive")
    try requireRequestID(archiveResponse, "smoke-session-archive", context: "chat.session.archive")
    let archivePayload = try payload(archiveResponse, context: "chat.session.archive")
    guard archivePayload["session_id"] as? String == smokeLifecycleSessionID,
          archivePayload["status"] as? String == "archived",
          archivePayload["archived_at"] is String
    else {
        throw SmokeFailure.message("chat.session.archive returned an unexpected payload: \(archiveResponse)")
    }

    let defaultSessionsAfterArchive = try listChatSessions(
        client: client,
        requestID: "smoke-sessions-default-after-archive"
    )
    guard !defaultSessionsAfterArchive.contains(where: { $0["session_id"] as? String == smokeLifecycleSessionID }) else {
        throw SmokeFailure.message("archived lifecycle session remained in default session list: \(defaultSessionsAfterArchive)")
    }
    let archivedSessions = try listChatSessions(
        client: client,
        requestID: "smoke-sessions-include-archived",
        includeArchived: true
    )
    let archivedSession = try requireSessionSummary(
        archivedSessions,
        sessionID: smokeLifecycleSessionID,
        context: "chat.sessions.list include archived"
    )
    guard archivedSession["status"] as? String == "archived",
          archivedSession["archived_at"] is String
    else {
        throw SmokeFailure.message("chat.sessions.list did not report archived lifecycle state: \(archivedSession)")
    }

    let archivedSendPrompt = "Attempt to send into archived lifecycle smoke."
    let archivedSendResponse = try sendAndRead(
        client,
        type: "chat.send",
        requestID: "smoke-session-archived-send",
        payload: [
            "session_id": smokeLifecycleSessionID,
            "model": "dev-mock",
            "messages": [
                ["role": "user", "content": archivedSendPrompt]
            ]
        ]
    )
    try requireErrorCode(
        archivedSendResponse,
        "chat_session_must_be_restored_before_send",
        requestID: "smoke-session-archived-send",
        context: "chat.send archived session"
    )
    let messagesAfterArchivedSend = try listChatMessages(
        client: client,
        requestID: "smoke-messages-after-archived-send",
        sessionID: smokeLifecycleSessionID
    )
    guard !messagesAfterArchivedSend.contains(where: { $0["content"] as? String == archivedSendPrompt }) else {
        throw SmokeFailure.message("archived chat.send mutated visible history: \(messagesAfterArchivedSend)")
    }

    let restoreResponse = try sendAndRead(
        client,
        type: "chat.session.restore",
        requestID: "smoke-session-restore",
        payload: ["session_id": smokeLifecycleSessionID]
    )
    try requireType(restoreResponse, "chat.session.restore", context: "chat.session.restore")
    try requireRequestID(restoreResponse, "smoke-session-restore", context: "chat.session.restore")
    let restorePayload = try payload(restoreResponse, context: "chat.session.restore")
    guard restorePayload["session_id"] as? String == smokeLifecycleSessionID,
          restorePayload["status"] as? String == "restored",
          restorePayload["restored_at"] is String
    else {
        throw SmokeFailure.message("chat.session.restore returned an unexpected payload: \(restoreResponse)")
    }
    let restoredSessions = try listChatSessions(client: client, requestID: "smoke-sessions-after-restore")
    let restoredSession = try requireSessionSummary(
        restoredSessions,
        sessionID: smokeLifecycleSessionID,
        context: "chat.sessions.list after restore"
    )
    guard restoredSession["status"] as? String == "active" else {
        throw SmokeFailure.message("chat.session.restore did not restore active session state: \(restoredSession)")
    }

    let activeDeleteResponse = try sendAndRead(
        client,
        type: "chat.session.delete",
        requestID: "smoke-session-delete-active",
        payload: ["session_id": smokeLifecycleSessionID]
    )
    try requireErrorCode(
        activeDeleteResponse,
        "chat_session_must_be_archived_before_delete",
        requestID: "smoke-session-delete-active",
        context: "chat.session.delete active session"
    )

    let archiveBeforeDeleteResponse = try sendAndRead(
        client,
        type: "chat.session.archive",
        requestID: "smoke-session-archive-before-delete",
        payload: ["session_id": smokeLifecycleSessionID]
    )
    try requireType(
        archiveBeforeDeleteResponse,
        "chat.session.archive",
        context: "chat.session.archive before delete"
    )
    try requireRequestID(
        archiveBeforeDeleteResponse,
        "smoke-session-archive-before-delete",
        context: "chat.session.archive before delete"
    )

    let deleteResponse = try sendAndRead(
        client,
        type: "chat.session.delete",
        requestID: "smoke-session-delete",
        payload: ["session_id": smokeLifecycleSessionID]
    )
    try requireType(deleteResponse, "chat.session.delete", context: "chat.session.delete")
    try requireRequestID(deleteResponse, "smoke-session-delete", context: "chat.session.delete")
    let deletePayload = try payload(deleteResponse, context: "chat.session.delete")
    guard deletePayload["session_id"] as? String == smokeLifecycleSessionID,
          deletePayload["status"] as? String == "deleted",
          deletePayload["deleted_at"] is String
    else {
        throw SmokeFailure.message("chat.session.delete returned an unexpected payload: \(deleteResponse)")
    }

    let sessionsAfterDelete = try listChatSessions(
        client: client,
        requestID: "smoke-sessions-after-delete",
        includeArchived: true
    )
    guard !sessionsAfterDelete.contains(where: { $0["session_id"] as? String == smokeLifecycleSessionID }) else {
        throw SmokeFailure.message("chat.session.delete left the lifecycle session listed: \(sessionsAfterDelete)")
    }

    let deletedMessagesResponse = try sendAndRead(
        client,
        type: "chat.messages.list",
        requestID: "smoke-messages-after-delete",
        payload: [
            "session_id": smokeLifecycleSessionID,
            "limit": 20
        ]
    )
    try requireType(deletedMessagesResponse, "chat.messages.list", context: "chat.messages.list after delete")
    let deletedMessagesPayload = try payload(deletedMessagesResponse, context: "chat.messages.list after delete")
    let deletedMessages = try requireDictionaryArray(
        deletedMessagesPayload,
        key: "messages",
        context: "chat.messages.list after delete"
    )
    guard deletedMessages.isEmpty else {
        throw SmokeFailure.message("chat.session.delete left lifecycle messages visible: \(deletedMessagesResponse)")
    }
}

func runAuthenticatedHistoryAndMemoryChecks(client: TCPClient) throws {
    print("Checking authenticated chat history and runtime memory...")
    let sessionsResponse = try sendAndRead(
        client,
        type: "chat.sessions.list",
        requestID: "smoke-sessions",
        payload: [
            "include_archived": true,
            "limit": 10
        ]
    )
    try requireType(sessionsResponse, "chat.sessions.list", context: "chat.sessions.list")
    try requireRequestID(sessionsResponse, "smoke-sessions", context: "chat.sessions.list")
    let sessionsPayload = try payload(sessionsResponse, context: "chat.sessions.list")
    let sessions = try requireDictionaryArray(sessionsPayload, key: "sessions", context: "chat.sessions.list")
    guard let smokeSession = sessions.first(where: { $0["session_id"] as? String == smokeSessionID }) else {
        throw SmokeFailure.message("chat.sessions.list did not include \(smokeSessionID) after chat.send: \(sessionsResponse)")
    }
    guard smokeSession["model"] as? String == "dev-mock",
          let messageCount = smokeSession["message_count"] as? Int,
          messageCount >= 2
    else {
        throw SmokeFailure.message("chat.sessions.list returned incomplete smoke-session summary: \(smokeSession)")
    }

    let searchedSessions = try listChatSessions(
        client: client,
        requestID: "smoke-sessions-search-metadata",
        includeArchived: true,
        query: "hello smoke test"
    )
    guard searchedSessions.first?["session_id"] as? String == smokeSessionID else {
        throw SmokeFailure.message("chat.sessions.list query did not rank \(smokeSessionID) first: \(searchedSessions)")
    }
    let searchedSmokeSession = try requireSessionSummary(
        searchedSessions,
        sessionID: smokeSessionID,
        context: "chat.sessions.list query search metadata"
    )
    try requireSearchMetadata(
        searchedSmokeSession,
        expectedRank: 1,
        snippetContains: "Say hello from the smoke test.",
        matchedField: "transcript",
        context: "chat.sessions.list query search metadata"
    )

    let messagesResponse = try sendAndRead(
        client,
        type: "chat.messages.list",
        requestID: "smoke-messages",
        payload: [
            "session_id": smokeSessionID,
            "limit": 20
        ]
    )
    try requireType(messagesResponse, "chat.messages.list", context: "chat.messages.list")
    try requireRequestID(messagesResponse, "smoke-messages", context: "chat.messages.list")
    let messagesPayload = try payload(messagesResponse, context: "chat.messages.list")
    guard messagesPayload["session_id"] as? String == smokeSessionID else {
        throw SmokeFailure.message("chat.messages.list returned a different session id: \(messagesResponse)")
    }
    let messages = try requireDictionaryArray(messagesPayload, key: "messages", context: "chat.messages.list")
    guard messages.contains(where: {
        $0["role"] as? String == "user"
            && ($0["content"] as? String)?.contains("Say hello from the smoke test.") == true
    }) else {
        throw SmokeFailure.message("chat.messages.list did not include the smoke user turn: \(messagesResponse)")
    }
    guard messages.contains(where: {
        $0["role"] as? String == "assistant"
            && ($0["content"] as? String)?.contains("Mock streaming response.") == true
    }) else {
        throw SmokeFailure.message("chat.messages.list did not include the smoke assistant response: \(messagesResponse)")
    }

    let memoryID = "smoke-memory-route"
    let memoryUpsertResponse = try sendAndRead(
        client,
        type: "memory.upsert",
        requestID: "smoke-memory-upsert",
        payload: [
            "id": memoryID,
            "content": " Prefers smoke-tested concise answers. ",
            "enabled": true
        ]
    )
    try requireType(memoryUpsertResponse, "memory.upsert", context: "memory.upsert")
    try requireRequestID(memoryUpsertResponse, "smoke-memory-upsert", context: "memory.upsert")
    let memoryUpsertPayload = try payload(memoryUpsertResponse, context: "memory.upsert")
    guard let upsertedEntry = memoryUpsertPayload["entry"] as? [String: Any],
          upsertedEntry["id"] as? String == memoryID,
          upsertedEntry["content"] as? String == "Prefers smoke-tested concise answers.",
          upsertedEntry["enabled"] as? Bool == true
    else {
        throw SmokeFailure.message("memory.upsert returned an unexpected entry: \(memoryUpsertResponse)")
    }

    let memoryListResponse = try sendAndRead(client, type: "memory.list", requestID: "smoke-memory-list")
    try requireType(memoryListResponse, "memory.list", context: "memory.list")
    try requireRequestID(memoryListResponse, "smoke-memory-list", context: "memory.list")
    let memoryListPayload = try payload(memoryListResponse, context: "memory.list")
    let memoryEntries = try requireDictionaryArray(memoryListPayload, key: "entries", context: "memory.list")
    guard memoryEntries.contains(where: {
        $0["id"] as? String == memoryID
            && $0["content"] as? String == "Prefers smoke-tested concise answers."
            && $0["enabled"] as? Bool == true
    }) else {
        throw SmokeFailure.message("memory.list did not include the smoke memory entry: \(memoryListResponse)")
    }

    let memoryDeleteResponse = try sendAndRead(
        client,
        type: "memory.delete",
        requestID: "smoke-memory-delete",
        payload: ["id": memoryID]
    )
    try requireType(memoryDeleteResponse, "memory.delete", context: "memory.delete")
    try requireRequestID(memoryDeleteResponse, "smoke-memory-delete", context: "memory.delete")
    let memoryDeletePayload = try payload(memoryDeleteResponse, context: "memory.delete")
    guard memoryDeletePayload["id"] as? String == memoryID,
          memoryDeletePayload["deleted_at"] is String
    else {
        throw SmokeFailure.message("memory.delete returned an unexpected deletion payload: \(memoryDeleteResponse)")
    }

    let memoryAfterDeleteResponse = try sendAndRead(
        client,
        type: "memory.list",
        requestID: "smoke-memory-list-after-delete"
    )
    try requireType(memoryAfterDeleteResponse, "memory.list", context: "memory.list after delete")
    try requireRequestID(memoryAfterDeleteResponse, "smoke-memory-list-after-delete", context: "memory.list after delete")
    let memoryAfterDeletePayload = try payload(memoryAfterDeleteResponse, context: "memory.list after delete")
    let memoryEntriesAfterDelete = try requireDictionaryArray(
        memoryAfterDeletePayload,
        key: "entries",
        context: "memory.list after delete"
    )
    guard !memoryEntriesAfterDelete.contains(where: { $0["id"] as? String == memoryID }) else {
        throw SmokeFailure.message("memory.delete did not remove the smoke memory entry: \(memoryAfterDeleteResponse)")
    }

    let summaryDraftsResponse = try sendAndRead(
        client,
        type: "memory.summary.drafts.list",
        requestID: "smoke-memory-summary-drafts",
        payload: ["limit": 5]
    )
    try requireType(summaryDraftsResponse, "memory.summary.drafts.list", context: "memory.summary.drafts.list")
    try requireRequestID(
        summaryDraftsResponse,
        "smoke-memory-summary-drafts",
        context: "memory.summary.drafts.list"
    )
    let summaryDraftsPayload = try payload(summaryDraftsResponse, context: "memory.summary.drafts.list")
    let summaryDrafts = try requireDictionaryArray(
        summaryDraftsPayload,
        key: "drafts",
        context: "memory.summary.drafts.list"
    )
    guard summaryDrafts.isEmpty else {
        throw SmokeFailure.message("memory.summary.drafts.list should be empty in the fresh smoke store: \(summaryDraftsResponse)")
    }

    let missingDraftID = "smoke-missing-memory-summary-draft"
    let summaryApproveUnavailableResponse = try sendAndRead(
        client,
        type: "memory.summary.draft.approve",
        requestID: "smoke-memory-summary-approve-unavailable",
        payload: [
            "draft_id": missingDraftID,
            "expected_session_id": "smoke-missing-session",
            "expected_source_message_count": 2
        ]
    )
    try requireErrorCode(
        summaryApproveUnavailableResponse,
        "memory_summary_draft_unavailable",
        requestID: "smoke-memory-summary-approve-unavailable",
        context: "memory.summary.draft.approve unavailable draft"
    )

    let summaryDismissUnavailableResponse = try sendAndRead(
        client,
        type: "memory.summary.draft.dismiss",
        requestID: "smoke-memory-summary-dismiss-unavailable",
        payload: [
            "draft_id": missingDraftID,
            "expected_session_id": "smoke-missing-session",
            "expected_source_message_count": 2
        ]
    )
    try requireErrorCode(
        summaryDismissUnavailableResponse,
        "memory_summary_draft_unavailable",
        requestID: "smoke-memory-summary-dismiss-unavailable",
        context: "memory.summary.draft.dismiss unavailable draft"
    )
}

func runMultiDeviceOwnerIsolationChecks(
    host: String,
    port: UInt16,
    relay: RelayConfiguration?,
    deviceAID: String,
    privateKeyA: P256.Signing.PrivateKey,
    deviceBID: String,
    privateKeyB: P256.Signing.PrivateKey
) throws {
    print("Checking multi-device owner isolation...")
    let memoryID = "smoke-owner-shared-memory"
    let memoryAContent = "Device A private smoke memory."
    let memoryBContent = "Device B private smoke memory."

    do {
        let clientA = try authenticateFreshClient(
            host: host,
            port: port,
            relay: relay,
            deviceID: deviceAID,
            privateKey: privateKeyA,
            requestPrefix: "smoke-owner-a"
        )
        defer { clientA.close() }
        let memoryAUpsert = try sendAndRead(
            clientA,
            type: "memory.upsert",
            requestID: "smoke-owner-a-memory-upsert",
            payload: [
                "id": memoryID,
                "content": memoryAContent,
                "enabled": true
            ]
        )
        try requireType(memoryAUpsert, "memory.upsert", context: "owner A memory.upsert")
        try requireRequestID(memoryAUpsert, "smoke-owner-a-memory-upsert", context: "owner A memory.upsert")

        let memoryAList = try listMemoryEntries(client: clientA, requestID: "smoke-owner-a-memory-list")
        try requireOnlyMemoryEntry(memoryAList, id: memoryID, content: memoryAContent, context: "owner A memory.list")

        try clientA.send(envelope(
            "chat.send",
            requestID: "smoke-owner-a-chat",
            payload: [
                "session_id": smokeOwnerIsolationSessionAID,
                "model": "dev-mock",
                "messages": [
                    ["role": "user", "content": "Use device A memory."]
                ]
            ]
        ))
        let chatAText = try readStoppedChatStream(
            client: clientA,
            requestID: "smoke-owner-a-chat",
            context: "owner A chat.send"
        )
        guard chatAText.contains("Mock streaming response.") else {
            throw SmokeFailure.message("owner A chat did not stream mock text: \(chatAText)")
        }
    }

    do {
        let clientB = try authenticateFreshClient(
            host: host,
            port: port,
            relay: relay,
            deviceID: deviceBID,
            privateKey: privateKeyB,
            requestPrefix: "smoke-owner-b"
        )
        defer { clientB.close() }
        let memoryBEmpty = try listMemoryEntries(client: clientB, requestID: "smoke-owner-b-memory-empty")
        guard memoryBEmpty.isEmpty else {
            throw SmokeFailure.message("owner B memory.list saw owner A memory before B upsert: \(memoryBEmpty)")
        }

        let memoryBUpsert = try sendAndRead(
            clientB,
            type: "memory.upsert",
            requestID: "smoke-owner-b-memory-upsert",
            payload: [
                "id": memoryID,
                "content": memoryBContent,
                "enabled": true
            ]
        )
        try requireType(memoryBUpsert, "memory.upsert", context: "owner B memory.upsert")
        try requireRequestID(memoryBUpsert, "smoke-owner-b-memory-upsert", context: "owner B memory.upsert")

        let memoryBList = try listMemoryEntries(client: clientB, requestID: "smoke-owner-b-memory-list")
        try requireOnlyMemoryEntry(memoryBList, id: memoryID, content: memoryBContent, context: "owner B memory.list")

        let sessionsBEmpty = try listChatSessions(
            client: clientB,
            requestID: "smoke-owner-b-sessions-empty",
            includeArchived: true
        )
        try requireNoSession(
            sessionsBEmpty,
            sessionID: smokeOwnerIsolationSessionAID,
            context: "owner B chat.sessions.list before B chat"
        )
        let messagesBA = try listChatMessages(
            client: clientB,
            requestID: "smoke-owner-b-messages-a",
            sessionID: smokeOwnerIsolationSessionAID
        )
        try requireEmptyMessages(messagesBA, context: "owner B chat.messages.list for owner A session")

        let renameBA = try sendAndRead(
            clientB,
            type: "chat.session.rename",
            requestID: "smoke-owner-b-rename-a",
            payload: [
                "session_id": smokeOwnerIsolationSessionAID,
                "title": "B cannot rename A"
            ]
        )
        try requireErrorCode(
            renameBA,
            "chat_session_not_found",
            requestID: "smoke-owner-b-rename-a",
            context: "owner B rename owner A session"
        )
        let archiveBA = try sendAndRead(
            clientB,
            type: "chat.session.archive",
            requestID: "smoke-owner-b-archive-a",
            payload: ["session_id": smokeOwnerIsolationSessionAID]
        )
        try requireErrorCode(
            archiveBA,
            "chat_session_not_found",
            requestID: "smoke-owner-b-archive-a",
            context: "owner B archive owner A session"
        )
        let deleteBA = try sendAndRead(
            clientB,
            type: "chat.session.delete",
            requestID: "smoke-owner-b-delete-a",
            payload: ["session_id": smokeOwnerIsolationSessionAID]
        )
        try requireErrorCode(
            deleteBA,
            "chat_session_not_found",
            requestID: "smoke-owner-b-delete-a",
            context: "owner B delete owner A session"
        )

        try clientB.send(envelope(
            "chat.send",
            requestID: "smoke-owner-b-chat",
            payload: [
                "session_id": smokeOwnerIsolationSessionBID,
                "model": "dev-mock",
                "messages": [
                    ["role": "user", "content": "Use device B memory."]
                ]
            ]
        ))
        let chatBText = try readStoppedChatStream(
            client: clientB,
            requestID: "smoke-owner-b-chat",
            context: "owner B chat.send"
        )
        guard chatBText.contains("Mock streaming response.") else {
            throw SmokeFailure.message("owner B chat did not stream mock text: \(chatBText)")
        }

        let sessionsB = try listChatSessions(
            client: clientB,
            requestID: "smoke-owner-b-sessions",
            includeArchived: true
        )
        _ = try requireSessionSummary(
            sessionsB,
            sessionID: smokeOwnerIsolationSessionBID,
            context: "owner B chat.sessions.list"
        )
        try requireNoSession(
            sessionsB,
            sessionID: smokeOwnerIsolationSessionAID,
            context: "owner B chat.sessions.list"
        )

        let memoryBDelete = try sendAndRead(
            clientB,
            type: "memory.delete",
            requestID: "smoke-owner-b-memory-delete",
            payload: ["id": memoryID]
        )
        try requireType(memoryBDelete, "memory.delete", context: "owner B memory.delete")
        try requireRequestID(memoryBDelete, "smoke-owner-b-memory-delete", context: "owner B memory.delete")
        let memoryBAfterDelete = try listMemoryEntries(client: clientB, requestID: "smoke-owner-b-memory-after-delete")
        guard memoryBAfterDelete.isEmpty else {
            throw SmokeFailure.message("owner B memory.delete left B memory visible: \(memoryBAfterDelete)")
        }
    }

    do {
        let clientA = try authenticateFreshClient(
            host: host,
            port: port,
            relay: relay,
            deviceID: deviceAID,
            privateKey: privateKeyA,
            requestPrefix: "smoke-owner-a-recheck"
        )
        defer { clientA.close() }
        let memoryAAfterBDelete = try listMemoryEntries(client: clientA, requestID: "smoke-owner-a-memory-after-b-delete")
        try requireOnlyMemoryEntry(
            memoryAAfterBDelete,
            id: memoryID,
            content: memoryAContent,
            context: "owner A memory.list after owner B delete"
        )
        let sessionsA = try listChatSessions(
            client: clientA,
            requestID: "smoke-owner-a-sessions",
            includeArchived: true
        )
        _ = try requireSessionSummary(
            sessionsA,
            sessionID: smokeOwnerIsolationSessionAID,
            context: "owner A chat.sessions.list"
        )
        try requireNoSession(
            sessionsA,
            sessionID: smokeOwnerIsolationSessionBID,
            context: "owner A chat.sessions.list"
        )
        let messagesAB = try listChatMessages(
            client: clientA,
            requestID: "smoke-owner-a-messages-b",
            sessionID: smokeOwnerIsolationSessionBID
        )
        try requireEmptyMessages(messagesAB, context: "owner A chat.messages.list for owner B session")
    }
}

func runMockBackendChecks(client: TCPClient, port: UInt16, unloadEventFile: URL) throws {
    print("Checking runtime.health...")
    let health = try sendAndRead(client, type: "runtime.health", requestID: "smoke-health")
    try requireType(health, "runtime.health", context: "runtime.health")
    let healthPayload = try payload(health, context: "runtime.health")
    guard healthPayload["status"] as? String == "ok",
          let ollama = healthPayload["ollama"] as? [String: Any],
          ollama["available"] as? Bool == true
    else {
        throw SmokeFailure.message("runtime.health did not report ok/available: \(health)")
    }

    print("Checking models.list...")
    let models = try sendAndRead(client, type: "models.list", requestID: "smoke-models")
    try requireType(models, "models.list", context: "models.list")
    let modelList = try requireModelList(models, context: "models.list")
    guard modelList.contains(where: { $0["id"] as? String == "dev-mock" }) else {
        throw SmokeFailure.message("models.list did not include dev-mock: \(models)")
    }
    guard modelList.contains(where: {
        $0["id"] as? String == "dev-mock-alt"
            && $0["provider"] as? String == "lm_studio"
            && $0["qualified_id"] as? String == "lm_studio:dev-mock-alt"
    }) else {
        throw SmokeFailure.message("models.list did not include the LM Studio aggregate mock model: \(models)")
    }
    guard modelList.contains(where: {
        $0["id"] as? String == smokeVisionModelID
            && $0["provider"] as? String == "lm_studio"
            && $0["qualified_id"] as? String == "lm_studio:\(smokeVisionModelID)"
            && ($0["capabilities"] as? [String])?.contains("vision") == true
    }) else {
        throw SmokeFailure.message("models.list did not include the vision-capable mock model: \(models)")
    }
    let mockCloudModels = try modelList.filter { model in
        model["source"] as? String == "cloud"
    }.map { model -> String in
        try requireString(model, "id", context: "mock cloud model")
    }
    guard mockCloudModels.isEmpty else {
        throw SmokeFailure.message("mock models.list should not include cloud suggestions: \(mockCloudModels)")
    }

    print("Checking models.pull...")
    let pulledModel = smokePulledModelID
    let pull = try sendAndRead(
        client,
        type: "models.pull",
        requestID: "smoke-pull",
        payload: ["model": pulledModel]
    )
    try assertNoBackendLeak(pull, context: "models.pull")
    try requireType(pull, "models.pull", context: "models.pull")
    let pullPayload = try payload(pull, context: "models.pull")
    guard pullPayload["model"] as? String == pulledModel,
          pullPayload["installed"] as? Bool == true
    else {
        throw SmokeFailure.message("models.pull did not report installed model: \(pull)")
    }

    let modelsAfterPull = try sendAndRead(client, type: "models.list", requestID: "smoke-models-after-pull")
    try requireType(modelsAfterPull, "models.list", context: "models.list after pull")
    let modelListAfterPull = try requireModelList(modelsAfterPull, context: "models.list after pull")
    guard modelListAfterPull.contains(where: {
        $0["id"] as? String == pulledModel
            && $0["installed"] as? Bool == true
            && $0["source"] as? String == "local"
    }) else {
        throw SmokeFailure.message("models.list did not include pulled model: \(modelsAfterPull)")
    }

    print("Checking chat.send with pulled model...")
    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-pulled-model",
        payload: [
            "session_id": smokeSessionID,
            "model": smokePulledModelID,
            "messages": [
                ["role": "user", "content": smokePulledModelPrompt]
            ]
        ]
    ))
    let pulledModelStreamedText = try readStoppedChatStream(
        client: client,
        requestID: "smoke-chat-pulled-model",
        context: "smoke-chat-pulled-model"
    )
    guard pulledModelStreamedText.contains("Mock streaming response.") else {
        throw SmokeFailure.message(
            "pulled model chat stream did not contain mock response: \(pulledModelStreamedText)"
        )
    }

    print("Checking chat.send streaming...")
    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat",
        payload: [
            "session_id": smokeSessionID,
            "model": "dev-mock",
            "messages": [
                ["role": "user", "content": "Say hello from the smoke test."]
            ]
        ]
    ))
    let streamedText = try readStoppedChatStream(client: client, requestID: "smoke-chat", context: "smoke-chat")
    guard streamedText.contains("Mock streaming response.") else {
        throw SmokeFailure.message("chat.delta stream did not contain mock response: \(streamedText)")
    }

    print("Checking chat.send with document attachment...")
    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-attachment",
        payload: [
            "session_id": smokeSessionID,
            "model": "dev-mock",
            "messages": [
                [
                    "role": "user",
                    "content": "Summarize the attached smoke note.",
                    "attachments": [
                        [
                            "type": "document",
                            "mime_type": "text/plain",
                            "name": "smoke-note.md",
                            "data_base64": Data(smokeDocumentAttachmentText.utf8).base64EncodedString()
                        ]
                    ]
                ]
            ]
        ]
    ))
    let attachmentStreamedText = try readStoppedChatStream(
        client: client,
        requestID: "smoke-chat-attachment",
        context: "smoke-chat-attachment"
    )
    guard attachmentStreamedText.contains("Mock streaming response."),
          attachmentStreamedText.contains("Attachment received.")
    else {
        throw SmokeFailure.message("attachment chat stream did not confirm attachment handling: \(attachmentStreamedText)")
    }

    print("Checking chat.send image attachment rejection for non-vision model...")
    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-image-non-vision",
        payload: [
            "session_id": smokeSessionID,
            "model": "dev-mock",
            "messages": [
                [
                    "role": "user",
                    "content": smokeImageAttachmentPrompt,
                    "attachments": [
                        [
                            "type": "image",
                            "mime_type": "image/png",
                            "name": smokeImageAttachmentName,
                            "data_base64": smokeImageAttachmentBase64
                        ]
                    ]
                ]
            ]
        ]
    ))
    let imageAttachmentError = try client.readEnvelope()
    try assertNoBackendLeak(imageAttachmentError, context: "smoke-chat-image-non-vision")
    try requireErrorCode(
        imageAttachmentError,
        "unsupported_attachment",
        requestID: "smoke-chat-image-non-vision",
        context: "smoke-chat-image-non-vision"
    )
    let imageAttachmentErrorPayload = try payload(
        imageAttachmentError,
        context: "smoke-chat-image-non-vision"
    )
    let imageAttachmentErrorMessage = try requireString(
        imageAttachmentErrorPayload,
        "message",
        context: "smoke-chat-image-non-vision"
    )
    guard imageAttachmentErrorMessage.contains("vision-capable model") else {
        throw SmokeFailure.message(
            "image attachment rejection did not explain the vision-capable model requirement: \(imageAttachmentError)"
        )
    }

    print("Checking chat.send image attachment success for vision-capable model...")
    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-image-vision",
        payload: [
            "session_id": smokeSessionID,
            "model": smokeVisionModelID,
            "messages": [
                [
                    "role": "user",
                    "content": smokeImageAttachmentPrompt,
                    "attachments": [
                        [
                            "type": "image",
                            "mime_type": "image/png",
                            "name": smokeImageAttachmentName,
                            "data_base64": smokeImageAttachmentBase64
                        ]
                    ]
                ]
            ]
        ]
    ))
    let visionAttachmentStreamedText = try readStoppedChatStream(
        client: client,
        requestID: "smoke-chat-image-vision",
        context: "smoke-chat-image-vision"
    )
    guard visionAttachmentStreamedText.contains("Mock streaming response."),
          visionAttachmentStreamedText.contains("Attachment received.")
    else {
        throw SmokeFailure.message(
            "vision image attachment chat stream did not confirm attachment handling: \(visionAttachmentStreamedText)"
        )
    }

    print("Checking chat.cancel...")
    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-cancel",
        payload: [
            "session_id": smokeSessionID,
            "model": "dev-mock",
            "messages": [
                ["role": "user", "content": "Start a cancellable response."]
            ]
        ]
    ))

    var sentCancel = false
    var sawCancelAck = false
    var sawCancelledDone = false
    while !(sawCancelAck && sawCancelledDone) {
        let response = try client.readEnvelope()
        try assertNoBackendLeak(response, context: "chat.cancel")
        let responseType = response["type"] as? String
        if responseType == "chat.delta", response["request_id"] as? String == "smoke-chat-cancel" {
            if !sentCancel {
                try client.send(envelope(
                    "chat.cancel",
                    requestID: "smoke-cancel",
                    payload: ["target_request_id": "smoke-chat-cancel"]
                ))
                sentCancel = true
            }
        } else if responseType == "chat.cancel" {
            try requireRequestID(response, "smoke-cancel", context: "chat.cancel")
            let cancelPayload = try payload(response, context: "chat.cancel")
            try requireBool(cancelPayload, "cancelled", true, context: "chat.cancel")
            sawCancelAck = true
        } else if responseType == "chat.done", response["request_id"] as? String == "smoke-chat-cancel" {
            let donePayload = try payload(response, context: "cancelled chat.done")
            guard donePayload["finish_reason"] as? String == "cancelled" else {
                throw SmokeFailure.message("cancelled chat.done used unexpected finish_reason: \(response)")
            }
            sawCancelledDone = true
        } else {
            throw SmokeFailure.message("Unexpected cancel flow response: \(response)")
        }
    }

    try runAuthenticatedModelResidencyChecks(client: client, unloadEventFile: unloadEventFile)
    try runAuthenticatedHistoryAndMemoryChecks(client: client)
    try runAuthenticatedTitleAndSessionLifecycleChecks(client: client)

    print("OK: authenticated mock E2E smoke passed on local diagnostic port \(port).")
}

func runRealOllamaChecks(client: TCPClient, port: UInt16, allowUnavailable: Bool) throws {
    print("Checking runtime.health against real model provider aggregate...")
    let health = try sendAndRead(client, type: "runtime.health", requestID: "smoke-health")
    try requireType(health, "runtime.health", context: "runtime.health")
    let healthPayload = try payload(health, context: "runtime.health")
    guard let ollama = healthPayload["ollama"] as? [String: Any] else {
        throw SmokeFailure.message("runtime.health did not include ollama object: \(health)")
    }

    if ollama["available"] as? Bool == false {
        guard ollama["code"] as? String == "backend_unavailable" else {
            throw SmokeFailure.message("runtime.health Ollama unavailable response was not useful backend_unavailable: \(health)")
        }
        let message = "Real Ollama smoke skipped: runtime.health reported the Ollama provider unavailable. Start Ollama on the runtime host and rerun --real-ollama."
        if allowUnavailable {
            print("SKIPPED: \(message)")
            return
        }
        throw SmokeFailure.message(message)
    }

    guard ollama["available"] as? Bool == true
    else {
        throw SmokeFailure.message("runtime.health did not report ok/available for real Ollama: \(health)")
    }

    let directTags = try fetchLocalOllamaJSON(path: "/api/tags")
    let directPs = try fetchLocalOllamaJSON(path: "/api/ps")
    let installedModelRecords = try ollamaModelRecords(from: directTags, context: "Ollama /api/tags")
    let installedModelNames = try ollamaModelNames(from: directTags, context: "Ollama /api/tags")
    let runningModelNames = try ollamaModelNames(from: directPs, context: "Ollama /api/ps")
    print("Local Ollama reports \(installedModelNames.count) installed model(s); \(runningModelNames.count) running model(s).")

    print("Checking models.list against real Ollama model state...")
    let models = try sendAndRead(client, type: "models.list", requestID: "smoke-models")
    try requireType(models, "models.list", context: "models.list")
    let modelList = try requireModelList(models, context: "models.list")

    func runtimeModel(named name: String) -> [String: Any]? {
        modelList.first { model in
            model["backend"] as? String == "ollama"
                && (model["id"] as? String == name || model["name"] as? String == name)
        }
    }

    let missingInstalled = try installedModelRecords.compactMap { record -> String? in
        let name = try ollamaModelName(record, context: "Ollama /api/tags")
        guard let model = runtimeModel(named: name) else { return name }
        let expectedSource = isCloudOllamaModel(record, name: name) ? "cloud" : "local"
        guard model["installed"] as? Bool == true,
              model["source"] as? String == expectedSource,
              model["backend"] as? String == "ollama"
        else {
            return name
        }
        if let remoteModel = record["remote_model"] as? String, !remoteModel.isEmpty,
           model["remote_model"] as? String != remoteModel {
            return name
        }
        return nil
    }
    guard missingInstalled.isEmpty else {
        throw SmokeFailure.message("models.list missed or misclassified installed model(s) from /api/tags: \(missingInstalled)")
    }

    let missingRunning = runningModelNames.sorted().filter { name in
        guard let model = runtimeModel(named: name) else { return true }
        return model["running"] as? Bool != true
            || model["installed"] as? Bool != true
    }
    guard missingRunning.isEmpty else {
        throw SmokeFailure.message("models.list did not mark running model(s) from /api/ps as running=true: \(missingRunning)")
    }

    let unexpectedRecommendedModels = try modelList.filter { model in
        model["source"] as? String == "recommended"
    }.map { model -> String in
        try requireString(model, "id", context: "unexpected recommended model")
    }
    guard unexpectedRecommendedModels.isEmpty else {
        throw SmokeFailure.message("models.list returned hardcoded recommended/default model(s): \(unexpectedRecommendedModels)")
    }

    let cloudModels = try installedModelRecords.compactMap { record -> String? in
        let name = try ollamaModelName(record, context: "Ollama /api/tags")
        return isCloudOllamaModel(record, name: name) ? name : nil
    }
    if cloudModels.isEmpty {
        print("No cloud model in local /api/tags; installed/running model checks still passed.")
    } else {
        print("Verified cloud model classification for: \(cloudModels.sorted().joined(separator: ", "))")
    }

    print("OK: authenticated real Ollama smoke passed on 127.0.0.1:\(port).")
}

func main() throws {
    let options = try SmokeOptions.parse(CommandLine.arguments)
    RelayCiphertextBoundary.enabled = options.transportMode == .relay

    guard FileManager.default.fileExists(atPath: "Package.swift") else {
        throw SmokeFailure.message("Run this script from the repository root.")
    }

    print("Building RuntimeDevServer for \(options.backendMode.name) smoke over \(options.transportMode.name)...")
    _ = try runAndCapture(["swift", "build", "--product", "RuntimeDevServer"])

    let port = try freePort()
    var relayConfiguration: RelayConfiguration?
    var bootstrapRelayEndpoint: RelayEndpoint?
    var relayProcess: Process?
    var relayPipe: Pipe?
    if options.transportMode == .relay {
        _ = try runAndCapture(["swift", "build", "--product", "AetherLinkRelay"])
        let relayPort = try freePort()
        let relayEndpoint = RelayEndpoint(host: "127.0.0.1", port: relayPort)
        let manualRelayID = nonEmptyEnvironmentValue("AETHERLINK_RELAY_ID")
        let manualRelaySecret = nonEmptyEnvironmentValue("AETHERLINK_RELAY_SECRET")
        if manualRelayID != nil || manualRelaySecret != nil {
            guard let manualRelayID, let manualRelaySecret else {
                throw SmokeFailure.message("Manual relay smoke requires both AETHERLINK_RELAY_ID and AETHERLINK_RELAY_SECRET")
            }
            relayConfiguration = RelayConfiguration(
                relayID: manualRelayID,
                relaySecret: manualRelaySecret,
                host: relayEndpoint.host,
                port: relayEndpoint.port
            )
        } else {
            bootstrapRelayEndpoint = relayEndpoint
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        let relayBinary = "\(try runAndCapture(["swift", "build", "--show-bin-path"]))/AetherLinkRelay"
        process.arguments = [
            relayBinary,
            "--host",
            relayEndpoint.host,
            "--port",
            String(relayEndpoint.port)
        ]
        if bootstrapRelayEndpoint != nil {
            process.arguments?.append("--require-allocation")
        }
        let output = RelayProcessOutput()
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { handle in
            output.append(handle.availableData)
        }
        try process.run()
        guard output.listeningReady.wait(timeout: .now() + 10) == .success else {
            process.terminate()
            throw SmokeFailure.message("Development relay did not start")
        }
        relayProcess = process
        relayPipe = pipe
        if let relayConfiguration {
            print("Preconfigured relay smoke route ready on \(relayConfiguration.host):\(relayConfiguration.port) relay_id=\(relayConfiguration.relayID)")
        } else {
            print("Allocated relay smoke endpoint ready on \(relayEndpoint.host):\(relayEndpoint.port)")
        }
    }
    defer {
        relayPipe?.fileHandleForReading.readabilityHandler = nil
        if let relayProcess, relayProcess.isRunning {
            relayProcess.terminate()
            relayProcess.waitUntilExit()
        }
    }

    let temporaryDirectory = FileManager.default.temporaryDirectory
        .appendingPathComponent("aetherlink-auth-smoke-\(UUID().uuidString)", isDirectory: true)
    try FileManager.default.createDirectory(at: temporaryDirectory, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: temporaryDirectory) }

    let output = ServerOutput()
    let trustedDevicesFile = temporaryDirectory.appendingPathComponent("trusted-devices.json")
    let mockUnloadEventFile = temporaryDirectory.appendingPathComponent("mock-unload-events.log")
    let ownerDeviceBID = "aetherlink-auth-smoke-device-b"
    let ownerDeviceBPrivateKey = P256.Signing.PrivateKey()
    let ownerDeviceBPublicKeyBase64 = ownerDeviceBPrivateKey.publicKey.derRepresentation.base64EncodedString()
    try seedTrustedDevicesFile(
        fileURL: trustedDevicesFile,
        devices: [
            (
                id: ownerDeviceBID,
                name: "AetherLink Auth Smoke B",
                publicKeyBase64: ownerDeviceBPublicKeyBase64
            )
        ]
    )
    let server = try startServer(
        port: port,
        trustedDevicesFile: trustedDevicesFile,
        backendMode: options.backendMode,
        relay: relayConfiguration,
        bootstrapRelay: bootstrapRelayEndpoint,
        expectP2PRouteRefresh: options.expectP2PRouteRefresh,
        mockUnloadEventFile: options.backendMode == .mock ? mockUnloadEventFile : nil
    )
    let outputPipe = Pipe()
    server.standardOutput = outputPipe
    server.standardError = outputPipe
    outputPipe.fileHandleForReading.readabilityHandler = { handle in
        output.append(handle.availableData)
    }

    try server.run()
    defer {
        outputPipe.fileHandleForReading.readabilityHandler = nil
        if server.isRunning {
            server.terminate()
            server.waitUntilExit()
        }
    }

    guard output.pairingInfoReady.wait(timeout: .now() + 20) == .success,
          let pairingInfo = output.pairingInfo
    else {
        throw SmokeFailure.message("RuntimeDevServer did not print AETHERLINK_DEV_PAIRING_INFO")
    }
    guard output.pairingURIReady.wait(timeout: .now() + 5) == .success,
          let pairingURI = output.pairingURI
    else {
        throw SmokeFailure.message("RuntimeDevServer did not print AETHERLINK_DEV_PAIRING_URI")
    }

    let parsedPairingURI = try parsePairingURI(pairingURI)
    let pairingCode = parsedPairingURI.pairingCode
    let pairingNonce = parsedPairingURI.pairingNonce
    let runtimeDeviceID = parsedPairingURI.runtimeDeviceID
    let pairingInfoCode = try requireString(pairingInfo, "pairing_code", context: "dev pairing info")
    let pairingInfoNonce = try requireString(pairingInfo, "pairing_nonce", context: "dev pairing info")
    let pairingInfoRuntimeDeviceID = try requireString(pairingInfo, "runtime_device_id", context: "dev pairing info")
    let pairingInfoRuntimeKeyFingerprint = try requireString(pairingInfo, "runtime_key_fingerprint", context: "dev pairing info")
    guard pairingInfoCode == pairingCode,
          pairingInfoNonce == pairingNonce,
          pairingInfoRuntimeDeviceID == runtimeDeviceID
    else {
        throw SmokeFailure.message("Development pairing URI did not match pairing info: uri=\(pairingURI) info=\(pairingInfo)")
    }
    if let legacyRuntimeDeviceID = pairingInfo["mac_device_id"] as? String,
       legacyRuntimeDeviceID != runtimeDeviceID {
        throw SmokeFailure.message("Development pairing legacy runtime id did not match canonical runtime_device_id: \(pairingInfo)")
    }
    var clientRelayConfiguration = relayConfiguration
    if options.transportMode == .relay {
        guard let parsedRelayConfiguration = parsedPairingURI.relayConfiguration else {
            throw SmokeFailure.message("Relay-mode development pairing URI did not include relay route material: \(pairingURI)")
        }
        let relayHost = try requireString(pairingInfo, "relay_host", context: "dev pairing info")
        let relayID = try requireString(pairingInfo, "relay_id", context: "dev pairing info")
        let relaySecret = try requireString(pairingInfo, "relay_secret", context: "dev pairing info")
        let relayNonce = try requireString(pairingInfo, "relay_nonce", context: "dev pairing info")
        let relayPort = try requireInt(pairingInfo, "relay_port", context: "dev pairing info")
        let expectedEndpoint = bootstrapRelayEndpoint
            ?? relayConfiguration.map { RelayEndpoint(host: $0.host, port: $0.port) }
            ?? RelayEndpoint(host: relayHost, port: UInt16(relayPort))
        guard relayHost == expectedEndpoint.host,
              relayPort == Int(expectedEndpoint.port)
        else {
            throw SmokeFailure.message("Development pairing info did not include the configured relay endpoint: \(pairingInfo)")
        }
        guard parsedRelayConfiguration.host == relayHost,
              parsedRelayConfiguration.port == UInt16(relayPort),
              parsedRelayConfiguration.relayID == relayID,
              parsedRelayConfiguration.relaySecret == relaySecret,
              parsedRelayConfiguration.relayNonce == relayNonce
        else {
            throw SmokeFailure.message("Development pairing URI relay route did not match pairing info: uri=\(pairingURI) info=\(pairingInfo)")
        }
        if let relayConfiguration {
            guard relayID == relayConfiguration.relayID,
                  relaySecret == relayConfiguration.relaySecret
            else {
                throw SmokeFailure.message("Manual relay pairing info did not include the configured relay credentials: \(pairingInfo)")
            }
        }
        guard let relayExpiresAt = pairingInfo["relay_expires_at"] as? Int64 ?? (pairingInfo["relay_expires_at"] as? Int).map(Int64.init),
              relayExpiresAt > Int64(Date().timeIntervalSince1970 * 1000),
              parsedPairingURI.relayExpiresAt == relayExpiresAt,
              !relayNonce.isEmpty
        else {
            throw SmokeFailure.message("Development pairing URI/info did not include matching fresh relay lease material: uri=\(pairingURI) info=\(pairingInfo)")
        }
        let hasDirectHost = pairingInfo["host"] != nil
        let hasDirectPort = pairingInfo["port"] != nil
        if hasDirectHost != parsedPairingURI.hasDirectHost || hasDirectPort != parsedPairingURI.hasDirectPort {
            throw SmokeFailure.message("Development pairing URI direct-route flags did not match pairing info: uri=\(pairingURI) info=\(pairingInfo)")
        }
        if (parsedPairingURI.hasDirectHost || parsedPairingURI.hasDirectPort), !options.allowDirectFallback {
            throw SmokeFailure.message("Relay-mode development pairing URI must not include a local direct host/port by default: \(pairingURI)")
        }
        if options.allowDirectFallback, parsedPairingURI.hasDirectHost != parsedPairingURI.hasDirectPort {
            throw SmokeFailure.message("Mixed-route relay pairing URI must include both local direct host and port: \(pairingURI)")
        }
        if options.allowDirectFallback, hasDirectPort {
            let directPort = try requireInt(pairingInfo, "port", context: "mixed-route dev pairing info")
            guard (1...65535).contains(directPort) else {
                throw SmokeFailure.message("Mixed-route relay pairing info direct port must be in 1...65535: \(pairingInfo)")
            }
        }
        clientRelayConfiguration = parsedRelayConfiguration
    }

    let privateKey = P256.Signing.PrivateKey()
    let publicKeyBase64 = privateKey.publicKey.derRepresentation.base64EncodedString()
    let deviceID = "aetherlink-auth-smoke-device"
    let consumedPairingDeviceID = "aetherlink-auth-smoke-consumed-pair-device"
    let consumedPairingDevicePrivateKey = P256.Signing.PrivateKey()
    let consumedPairingDevicePublicKeyBase64 = consumedPairingDevicePrivateKey.publicKey.derRepresentation.base64EncodedString()

    try runRejectedPairingChecks(
        host: "127.0.0.1",
        port: port,
        relay: clientRelayConfiguration,
        pairingNonce: pairingNonce,
        pairingCode: pairingCode,
        deviceID: deviceID,
        publicKeyBase64: publicKeyBase64
    )

    try runInvalidPairingIdentityCheck(
        host: "127.0.0.1",
        port: port,
        relay: clientRelayConfiguration,
        pairingNonce: pairingNonce,
        pairingCode: pairingCode,
        deviceID: deviceID
    )

    print("Pairing with dev session runtime_device_id=\(runtimeDeviceID) over \(options.transportMode.name)...")
    try pairTrustedDevice(
        host: "127.0.0.1",
        port: port,
        relay: clientRelayConfiguration,
        pairingNonce: pairingNonce,
        pairingCode: pairingCode,
        deviceID: deviceID,
        deviceName: "AetherLink Auth Smoke",
        publicKeyBase64: publicKeyBase64,
        requestID: "smoke-pair"
    )

    try runConsumedPairingReuseCheck(
        host: "127.0.0.1",
        port: port,
        relay: clientRelayConfiguration,
        pairingNonce: pairingNonce,
        pairingCode: pairingCode,
        deviceID: consumedPairingDeviceID,
        publicKeyBase64: consumedPairingDevicePublicKeyBase64
    )

    try runRawNonceAuthRejectionCheck(
        host: "127.0.0.1",
        port: port,
        relay: clientRelayConfiguration,
        deviceID: deviceID,
        privateKey: privateKey
    )

    try runAuthReplayAndSupersededChallengeChecks(
        host: "127.0.0.1",
        port: port,
        relay: clientRelayConfiguration,
        deviceID: deviceID,
        privateKey: privateKey
    )

    try runUnauthenticatedAndUntrustedRejectionChecks(
        host: "127.0.0.1",
        port: port,
        relay: clientRelayConfiguration
    )

    print("Authenticating a fresh \(options.transportMode.name) connection with P-256 challenge-response...")
    do {
        let client = try authenticateFreshClient(
            host: "127.0.0.1",
            port: port,
            relay: clientRelayConfiguration,
            deviceID: deviceID,
            privateKey: privateKey,
            requestPrefix: "smoke"
        )
        defer { client.close() }

        if options.transportMode == .relay {
            let expectedEndpoint = bootstrapRelayEndpoint
                ?? relayConfiguration.map { RelayEndpoint(host: $0.host, port: $0.port) }
                ?? clientRelayConfiguration.map { RelayEndpoint(host: $0.host, port: $0.port) }
                ?? RelayEndpoint(host: "127.0.0.1", port: 0)
            guard expectedEndpoint.port != 0 else {
                throw SmokeFailure.message("route.refresh smoke could not resolve expected relay endpoint")
            }
            clientRelayConfiguration = try refreshRelayRoute(
                client: client,
                runtimeDeviceID: runtimeDeviceID,
                runtimeKeyFingerprint: pairingInfoRuntimeKeyFingerprint,
                expectedEndpoint: expectedEndpoint,
                expectP2PRouteRefresh: options.expectP2PRouteRefresh
            )
        }

        switch options.backendMode {
        case .mock:
            try runMockBackendChecks(client: client, port: port, unloadEventFile: mockUnloadEventFile)
        case .realOllama:
            try runRealOllamaChecks(client: client, port: port, allowUnavailable: options.allowUnavailable)
        }
    }

    if case .mock = options.backendMode {
        try runMultiDeviceOwnerIsolationChecks(
            host: "127.0.0.1",
            port: port,
            relay: clientRelayConfiguration,
            deviceAID: deviceID,
            privateKeyA: privateKey,
            deviceBID: ownerDeviceBID,
            privateKeyB: ownerDeviceBPrivateKey
        )
    }

    print("Reconnecting with the saved trusted \(options.transportMode.name) route...")
    let reconnectClient = try authenticateFreshClient(
        host: "127.0.0.1",
        port: port,
        relay: clientRelayConfiguration,
        deviceID: deviceID,
        privateKey: privateKey,
        requestPrefix: "smoke-reconnect"
    )
    defer { reconnectClient.close() }
    let reconnectHealth = try sendAndRead(
        reconnectClient,
        type: "runtime.health",
        requestID: "smoke-reconnect-health"
    )
    try requireType(reconnectHealth, "runtime.health", context: "saved trusted route reconnect runtime.health")
    let reconnectPayload = try payload(reconnectHealth, context: "saved trusted route reconnect runtime.health")
    guard reconnectPayload["status"] as? String == "ok" else {
        throw SmokeFailure.message("saved trusted route reconnect runtime.health did not report ok: \(reconnectHealth)")
    }
    try runTrustedDeviceRevocationCheck(
        client: reconnectClient,
        trustedDevicesFile: trustedDevicesFile
    )
    try verifyRelayCiphertextBoundaryIfNeeded()
}

do {
    try main()
} catch {
    fputs("FAILED: \(error)\n", stderr)
    exit(1)
}
