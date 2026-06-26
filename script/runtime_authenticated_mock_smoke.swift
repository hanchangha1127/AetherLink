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
            case "--help", "-h":
                print("""
                Usage: ./script/runtime_authenticated_mock_smoke.swift [--relay] [--allow-direct-fallback] [--real-ollama] [--allow-unavailable]

                  default              Run authenticated mock E2E smoke, including pull and chat coverage.
                  --relay              Route the smoke through AetherLinkRelay allocation with encrypted relay frames.
                  --allow-direct-fallback
                                       Allow explicit mixed-route relay diagnostics where QR pairing info also carries direct host/port.
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
        return options
    }
}

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
        let challenge = try sendAndRead(
            client,
            type: "hello",
            requestID: "\(requestPrefix)-hello",
            payload: [
                "device_id": deviceID,
                "device_name": "Smoke Test Client",
                "client_capabilities": ["chat", "streaming", "attachments"]
            ]
        )
        try requireType(challenge, "auth.challenge", context: "\(requestPrefix) hello")
        let challengePayload = try payload(challenge, context: "\(requestPrefix) hello")
        let nonce = try requireString(challengePayload, "nonce", context: "\(requestPrefix) hello")

        let digest = SHA256.hash(data: Data(nonce.utf8))
        let signature = try privateKey.signature(for: digest).derRepresentation.base64EncodedString()
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
        try requireType(authResponse, "auth.response", context: "\(requestPrefix) auth.response")
        let authPayload = try payload(authResponse, context: "\(requestPrefix) auth.response")
        try requireBool(authPayload, "accepted", true, context: "\(requestPrefix) auth.response")
        return client
    } catch {
        client.close()
        throw error
    }
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
    bootstrapRelay: RelayEndpoint?
) throws -> Process {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    process.arguments = ["\(try runAndCapture(["swift", "build", "--show-bin-path"]))/RuntimeDevServer"]
    var environment = ProcessInfo.processInfo.environment
    environment["LOCAL_AGENT_BRIDGE_PORT"] = String(port)
    switch backendMode {
    case .mock:
        environment["LOCAL_AGENT_BRIDGE_MOCK_BACKEND"] = "1"
    case .realOllama:
        environment["LOCAL_AGENT_BRIDGE_MOCK_BACKEND"] = nil
    }
    environment["AETHERLINK_DEV_PAIRING"] = "1"
    environment["AETHERLINK_DEV_TRUSTED_DEVICES_FILE"] = trustedDevicesFile.path
    environment["AETHERLINK_DEV_RUNTIME_PUBLIC_KEY"] = "aetherlink-smoke-runtime-public-key"
    environment["AETHERLINK_DEV_RUNTIME_KEY_FINGERPRINT"] = "aetherlink-smoke-runtime-fingerprint"
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

func runMockBackendChecks(client: TCPClient, port: UInt16) throws {
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
    let mockCloudModels = try modelList.filter { model in
        model["source"] as? String == "cloud"
    }.map { model -> String in
        try requireString(model, "id", context: "mock cloud model")
    }
    guard mockCloudModels.isEmpty else {
        throw SmokeFailure.message("mock models.list should not include cloud suggestions: \(mockCloudModels)")
    }

    print("Checking models.pull...")
    let pulledModel = "dev-pulled"
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

    print("Checking chat.send streaming...")
    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat",
        payload: [
            "session_id": "smoke-session",
            "model": "dev-mock",
            "messages": [
                ["role": "user", "content": "Say hello from the smoke test."]
            ]
        ]
    ))
    var streamedText = ""
    var sawDone = false
    while !sawDone {
        let response = try client.readEnvelope()
        try assertNoBackendLeak(response, context: "smoke-chat")
        try requireRequestID(response, "smoke-chat", context: "chat.send")
        let responseType = response["type"] as? String
        if responseType == "chat.delta" {
            streamedText += (try payload(response, context: "chat.delta")["delta"] as? String) ?? ""
        } else if responseType == "chat.done" {
            let donePayload = try payload(response, context: "chat.done")
            guard donePayload["finish_reason"] as? String == "stop" else {
                throw SmokeFailure.message("chat.done did not finish with stop: \(response)")
            }
            sawDone = true
        } else {
            throw SmokeFailure.message("Unexpected chat response: \(response)")
        }
    }
    guard streamedText.contains("Mock streaming response.") else {
        throw SmokeFailure.message("chat.delta stream did not contain mock response: \(streamedText)")
    }

    print("Checking chat.cancel...")
    try client.send(envelope(
        "chat.send",
        requestID: "smoke-chat-cancel",
        payload: [
            "session_id": "smoke-session",
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
    let server = try startServer(
        port: port,
        trustedDevicesFile: temporaryDirectory.appendingPathComponent("trusted-devices.json"),
        backendMode: options.backendMode,
        relay: relayConfiguration,
        bootstrapRelay: bootstrapRelayEndpoint
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

    print("Pairing with dev session runtime_device_id=\(runtimeDeviceID) over \(options.transportMode.name)...")
    let pairingClient = try connectWithRetry(host: "127.0.0.1", port: port, relay: clientRelayConfiguration)
    do {
        let pairResponse = try sendAndRead(
            pairingClient,
            type: "pairing.request",
            requestID: "smoke-pair",
            payload: [
                "pairing_nonce": pairingNonce,
                "pairing_code": pairingCode,
                "device_id": deviceID,
                "device_name": "AetherLink Auth Smoke",
                "public_key": publicKeyBase64
            ]
        )
        try requireType(pairResponse, "pairing.result", context: "pairing.request")
        try requireRequestID(pairResponse, "smoke-pair", context: "pairing.request")
        let pairPayload = try payload(pairResponse, context: "pairing.request")
        try requireBool(pairPayload, "accepted", true, context: "pairing.request")
        pairingClient.close()
    } catch {
        pairingClient.close()
        throw error
    }

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

        switch options.backendMode {
        case .mock:
            try runMockBackendChecks(client: client, port: port)
        case .realOllama:
            try runRealOllamaChecks(client: client, port: port, allowUnavailable: options.allowUnavailable)
        }
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
}

do {
    try main()
} catch {
    fputs("FAILED: \(error)\n", stderr)
    exit(1)
}
