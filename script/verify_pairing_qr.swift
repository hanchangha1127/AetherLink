#!/usr/bin/env swift
import CoreImage
import Foundation

enum QRVerifyFailure: Error, CustomStringConvertible {
    case usage
    case missingImage(String)
    case emptyExpected
    case invalidPairingURI
    case missingQueryField(String)
    case invalidRelayHost(String)
    case relayHostMismatch(actual: String, expected: String)
    case invalidRelayPort(String)
    case relayPortMismatch(actual: String, expected: String)
    case invalidRelayExpiration(String)
    case invalidRelayToken(String)
    case invalidBootstrapToken(String)
    case directEndpointForbidden
    case invalidDirectEndpoint(String)
    case imageLoadFailed(String)
    case detectionFailed
    case multipleCodes(Int)
    case decodedValueMismatch

    var description: String {
        switch self {
        case .usage:
            return """
            Usage: script/verify_pairing_qr.swift --image <png-path> [--expected <text-or-file>] [--require-relay-route] [--require-production-bootstrap] [--expected-relay-host <host>] [--expected-relay-port <port>] [--forbid-direct-endpoint] [--allow-local-relay]
            """
        case .missingImage(let path):
            return "QR image does not exist at \(path)"
        case .emptyExpected:
            return "Expected QR value was empty."
        case .invalidPairingURI:
            return "Decoded QR value must be an aetherlink://pair URI with query parameters."
        case .missingQueryField(let field):
            return "Decoded pairing URI is missing required field \(field)."
        case .invalidRelayHost(let host):
            return "Decoded pairing URI relay_host is not a remote-reachable relay host: \(host)"
        case .relayHostMismatch(let actual, let expected):
            return "Decoded pairing URI relay_host=\(actual) did not match expected \(expected)."
        case .invalidRelayPort(let value):
            return "Decoded pairing URI contains invalid relay_port: \(value)"
        case .relayPortMismatch(let actual, let expected):
            return "Decoded pairing URI relay_port=\(actual) did not match expected \(expected)."
        case .invalidRelayExpiration(let value):
            return "Decoded pairing URI contains invalid relay_expires_at: \(value)"
        case .invalidRelayToken(let field):
            return "Decoded pairing URI contains invalid \(field)."
        case .invalidBootstrapToken(let field):
            return "Decoded pairing URI contains invalid production bootstrap field \(field)."
        case .directEndpointForbidden:
            return "Decoded pairing URI must not include direct host/port fields for remote relay pairing."
        case .invalidDirectEndpoint(let field):
            return "Decoded pairing URI contains invalid direct endpoint field \(field)."
        case .imageLoadFailed(let path):
            return "Could not load QR image from \(path)"
        case .detectionFailed:
            return "No QR code was detected in the image."
        case .multipleCodes(let count):
            return "Expected one QR code, detected \(count)."
        case .decodedValueMismatch:
            return "Decoded QR value did not match the expected value."
        }
    }
}

struct Options {
    var imagePath: String?
    var expected: String?
    var requireRelayRoute = false
    var requireProductionBootstrap = false
    var expectedRelayHost: String?
    var expectedRelayPort: String?
    var forbidDirectEndpoint = false
    var allowLocalRelay = false
}

func parseOptions(_ arguments: [String]) throws -> Options {
    var options = Options()
    var index = 1
    while index < arguments.count {
        let argument = arguments[index]
        switch argument {
        case "--image":
            guard index + 1 < arguments.count else { throw QRVerifyFailure.usage }
            options.imagePath = arguments[index + 1]
            index += 2
        case "--expected":
            guard index + 1 < arguments.count else { throw QRVerifyFailure.usage }
            options.expected = arguments[index + 1]
            index += 2
        case "--require-relay-route":
            options.requireRelayRoute = true
            index += 1
        case "--require-production-bootstrap":
            options.requireProductionBootstrap = true
            index += 1
        case "--expected-relay-host":
            guard index + 1 < arguments.count else { throw QRVerifyFailure.usage }
            options.expectedRelayHost = arguments[index + 1]
            options.requireRelayRoute = true
            index += 2
        case "--expected-relay-port":
            guard index + 1 < arguments.count else { throw QRVerifyFailure.usage }
            options.expectedRelayPort = arguments[index + 1]
            options.requireRelayRoute = true
            index += 2
        case "--forbid-direct-endpoint":
            options.forbidDirectEndpoint = true
            index += 1
        case "--allow-local-relay":
            options.allowLocalRelay = true
            index += 1
        case "-h", "--help":
            throw QRVerifyFailure.usage
        default:
            throw QRVerifyFailure.usage
        }
    }
    guard options.imagePath != nil else {
        throw QRVerifyFailure.usage
    }
    return options
}

func expectedText(from value: String?) throws -> String? {
    guard let value else { return nil }
    if value == "-" {
        let data = FileHandle.standardInput.readDataToEndOfFile()
        guard let text = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
              !text.isEmpty
        else {
            throw QRVerifyFailure.emptyExpected
        }
        return text
    }

    if FileManager.default.fileExists(atPath: value) {
        let text = try String(contentsOfFile: value, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { throw QRVerifyFailure.emptyExpected }
        return text
    }

    let text = value.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !text.isEmpty else { throw QRVerifyFailure.emptyExpected }
    return text
}

func decodedQRCodeValue(from imagePath: String) throws -> String {
    guard FileManager.default.fileExists(atPath: imagePath) else {
        throw QRVerifyFailure.missingImage(imagePath)
    }
    let url = URL(fileURLWithPath: imagePath)
    guard let image = CIImage(contentsOf: url) else {
        throw QRVerifyFailure.imageLoadFailed(imagePath)
    }
    let detector = CIDetector(
        ofType: CIDetectorTypeQRCode,
        context: nil,
        options: [CIDetectorAccuracy: CIDetectorAccuracyHigh]
    )
    let features = detector?.features(in: image) ?? []
    guard !features.isEmpty else {
        throw QRVerifyFailure.detectionFailed
    }
    guard features.count == 1 else {
        throw QRVerifyFailure.multipleCodes(features.count)
    }
    guard let qrFeature = features.first as? CIQRCodeFeature,
          let message = qrFeature.messageString,
          !message.isEmpty
    else {
        throw QRVerifyFailure.detectionFailed
    }
    return message
}

func validatePairingURI(_ value: String, options: Options) throws {
    guard let components = URLComponents(string: value),
          components.scheme == "aetherlink",
          components.host == "pair",
          let queryItems = components.queryItems,
          !queryItems.isEmpty
    else {
        throw QRVerifyFailure.invalidPairingURI
    }

    let query = Dictionary(
        queryItems.map { ($0.name, $0.value ?? "") },
        uniquingKeysWith: { _, latest in latest }
    )

    for field in [
        QRField(canonical: "version", aliases: ["v"]),
        QRField(canonical: "pairing_nonce", aliases: ["nonce", "n"]),
        QRField(canonical: "pairing_code", aliases: ["code", "c"]),
        QRField(canonical: "runtime_device_id", aliases: ["mac_device_id", "device_id", "rid"]),
        QRField(canonical: "runtime_key_fingerprint", aliases: ["fingerprint", "cert_fingerprint", "rf"])
    ] where query.value(for: field) == nil {
        throw QRVerifyFailure.missingQueryField(field.canonical)
    }

    if options.requireProductionBootstrap {
        try validateProductionBootstrap(query: query)
    }

    if options.forbidDirectEndpoint,
       query.value(for: QRField(canonical: "host", aliases: ["runtime_host", "h"])) != nil ||
        query.value(for: QRField(canonical: "port", aliases: ["runtime_port", "p"])) != nil {
        throw QRVerifyFailure.directEndpointForbidden
    }

    if let directPort = query.value(for: QRField(canonical: "port", aliases: ["runtime_port", "p"])) {
        guard let port = Int(directPort), (1...65_535).contains(port) else {
            throw QRVerifyFailure.invalidDirectEndpoint("port")
        }
        guard query.value(for: QRField(canonical: "host", aliases: ["runtime_host", "h"])) != nil else {
            throw QRVerifyFailure.invalidDirectEndpoint("host")
        }
    }

    if options.requireRelayRoute {
        try validateRelayRoute(query: query, options: options)
    }
}

func validateProductionBootstrap(query: [String: String]) throws {
    let requiredBootstrapFields = [
        QRField(canonical: "runtime_public_key", aliases: ["mac_public_key", "public_key", "rk"]),
        QRField(canonical: "route_token", aliases: ["discovery_token", "rt"])
    ]
    for field in requiredBootstrapFields {
        guard let value = query.value(for: field) else {
            throw QRVerifyFailure.missingQueryField(field.canonical)
        }
        guard value.rangeOfCharacter(from: .whitespacesAndNewlines) == nil else {
            throw QRVerifyFailure.invalidBootstrapToken(field.canonical)
        }
    }
}

func validateRelayRoute(query: [String: String], options: Options) throws {
    let requiredRelayFields = [
        QRField(canonical: "relay_host", aliases: ["remote_host", "route_host", "rendezvous_host", "rh"]),
        QRField(canonical: "relay_port", aliases: ["remote_port", "route_port", "rendezvous_port", "rp"]),
        QRField(canonical: "relay_id", aliases: ["remote_id", "route_id", "network_id", "ri"]),
        QRField(canonical: "relay_secret", aliases: ["remote_secret", "route_secret", "rs"]),
        QRField(canonical: "relay_expires_at", aliases: ["remote_expires_at", "route_expires_at", "rendezvous_expires_at", "rx"]),
        QRField(canonical: "relay_nonce", aliases: ["remote_nonce", "route_nonce", "rendezvous_nonce", "rrn"])
    ]
    for field in requiredRelayFields where query.value(for: field) == nil {
        throw QRVerifyFailure.missingQueryField(field.canonical)
    }

    let relayHost = query.value(for: QRField(canonical: "relay_host", aliases: ["remote_host", "route_host", "rendezvous_host", "rh"]))!
    let relayScope = query.value(for: QRField(canonical: "relay_scope", aliases: ["remote_scope", "route_scope", "rsc"]))
    if !options.allowLocalRelay, !isEligibleRemoteRelayHost(relayHost, relayScope: relayScope) {
        throw QRVerifyFailure.invalidRelayHost(relayHost)
    }
    if let expectedRelayHost = options.expectedRelayHost,
       relayHost != expectedRelayHost {
        throw QRVerifyFailure.relayHostMismatch(actual: relayHost, expected: expectedRelayHost)
    }

    let relayPort = query.value(for: QRField(canonical: "relay_port", aliases: ["remote_port", "route_port", "rendezvous_port", "rp"]))!
    guard let relayPortNumber = Int(relayPort),
          (1...65_535).contains(relayPortNumber)
    else {
        throw QRVerifyFailure.invalidRelayPort(relayPort)
    }
    if let expectedRelayPort = options.expectedRelayPort,
       relayPort != expectedRelayPort {
        throw QRVerifyFailure.relayPortMismatch(actual: relayPort, expected: expectedRelayPort)
    }

    let relayExpiration = query.value(for: QRField(canonical: "relay_expires_at", aliases: ["remote_expires_at", "route_expires_at", "rendezvous_expires_at", "rx"]))!
    guard let expiresAt = Int64(relayExpiration), expiresAt > 0 else {
        throw QRVerifyFailure.invalidRelayExpiration(relayExpiration)
    }

    for field in [
        QRField(canonical: "relay_id", aliases: ["remote_id", "route_id", "network_id", "ri"]),
        QRField(canonical: "relay_nonce", aliases: ["remote_nonce", "route_nonce", "rendezvous_nonce", "rrn"])
    ] {
        guard query.value(for: field)?.rangeOfCharacter(from: .whitespacesAndNewlines) == nil else {
            throw QRVerifyFailure.invalidRelayToken(field.canonical)
        }
    }
}

struct QRField: CustomStringConvertible {
    let canonical: String
    var aliases: [String] = []

    var description: String {
        canonical
    }
}

extension Dictionary where Key == String, Value == String {
    func value(for field: QRField) -> String? {
        for key in [field.canonical] + field.aliases {
            if let value = self[key], !value.isEmpty {
                return value
            }
        }
        return nil
    }
}

func isEligibleRemoteRelayHost(_ host: String, relayScope: String? = nil) -> Bool {
    let normalized = host
        .trimmingCharacters(in: .whitespacesAndNewlines)
        .trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        .trimmingCharacters(in: CharacterSet(charactersIn: "."))
        .lowercased()
    guard !normalized.isEmpty else { return false }
    if normalized == "localhost" ||
        normalized == "::1" ||
        normalized == "0:0:0:0:0:0:0:1" ||
        normalized == "0.0.0.0" ||
        normalized == "::" ||
        normalized.hasPrefix("127.") {
        return false
    }
    if normalized == "local" || normalized.hasSuffix(".local") {
        return false
    }
    if normalized.isPrivateOrLocalIPv4RelayLiteral() ||
        normalized.isPrivateOrLocalIPv6RelayLiteral() {
        return relayScope?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "private_overlay" &&
            normalized.isPrivateOverlayRelayLiteral()
    }
    return true
}

extension String {
    func isPrivateOverlayRelayLiteral() -> Bool {
        isPrivateOverlayIPv4Literal() || isPrivateOverlayIPv6Literal()
    }

    private func isPrivateOverlayIPv4Literal() -> Bool {
        let octets = split(separator: ".", omittingEmptySubsequences: false)
        guard octets.count == 4 else { return false }
        let values: [Int] = octets.compactMap { part in
            guard !part.isEmpty,
                  part.allSatisfy(\.isNumber),
                  let value = Int(part),
                  (0...255).contains(value)
            else {
                return nil
            }
            return value
        }
        guard values.count == 4 else { return false }
        let first = values[0]
        let second = values[1]
        return first == 10 ||
            (first == 100 && (64...127).contains(second)) ||
            (first == 172 && (16...31).contains(second)) ||
            (first == 192 && second == 168)
    }

    private func isPrivateOverlayIPv6Literal() -> Bool {
        guard contains(":") else { return false }
        return hasPrefix("fc") || hasPrefix("fd")
    }

    func isPrivateOrLocalIPv4RelayLiteral() -> Bool {
        let octets = split(separator: ".", omittingEmptySubsequences: false)
        guard octets.count == 4 else { return false }
        let values: [Int] = octets.compactMap { part in
            guard !part.isEmpty,
                  part.allSatisfy(\.isNumber),
                  let value = Int(part),
                  (0...255).contains(value)
            else {
                return nil
            }
            return value
        }
        guard values.count == 4 else { return false }
        let first = values[0]
        let second = values[1]
        return first == 0 ||
            first == 10 ||
            first == 127 ||
            first >= 224 ||
            (first == 100 && (64...127).contains(second)) ||
            (first == 169 && second == 254) ||
            (first == 172 && (16...31).contains(second)) ||
            (first == 192 && second == 168)
    }

    func isPrivateOrLocalIPv6RelayLiteral() -> Bool {
        guard contains(":") else { return false }
        return self == "::" ||
            self == "::1" ||
            self == "0:0:0:0:0:0:0:0" ||
            self == "0:0:0:0:0:0:0:1" ||
            hasPrefix("fe80:") ||
            hasPrefix("fc") ||
            hasPrefix("fd")
    }
}

do {
    let options = try parseOptions(CommandLine.arguments)
    let imagePath = options.imagePath!
    let decoded = try decodedQRCodeValue(from: imagePath)
    try validatePairingURI(decoded, options: options)
    if let expected = try expectedText(from: options.expected), decoded != expected {
        throw QRVerifyFailure.decodedValueMismatch
    }
    print(decoded)
} catch {
    fputs("FAILED: \(error)\n", stderr)
    switch error {
    case QRVerifyFailure.usage,
        QRVerifyFailure.missingImage,
        QRVerifyFailure.emptyExpected,
        QRVerifyFailure.invalidPairingURI,
        QRVerifyFailure.missingQueryField,
        QRVerifyFailure.invalidRelayHost,
        QRVerifyFailure.relayHostMismatch,
        QRVerifyFailure.invalidRelayPort,
        QRVerifyFailure.relayPortMismatch,
        QRVerifyFailure.invalidRelayExpiration,
        QRVerifyFailure.invalidRelayToken,
        QRVerifyFailure.invalidBootstrapToken,
        QRVerifyFailure.directEndpointForbidden,
        QRVerifyFailure.invalidDirectEndpoint:
        exit(2)
    case QRVerifyFailure.imageLoadFailed,
        QRVerifyFailure.detectionFailed,
        QRVerifyFailure.multipleCodes,
        QRVerifyFailure.decodedValueMismatch:
        exit(3)
    default:
        exit(1)
    }
}
