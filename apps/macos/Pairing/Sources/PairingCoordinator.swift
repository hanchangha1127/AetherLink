import CryptoKit
import Foundation
import TrustedDevices

public struct PairingSession: Identifiable, Equatable, Sendable {
    private typealias RelayQRCodeMaterial = (
        host: String,
        port: Int,
        id: String,
        secret: String,
        expiresAtEpochMillis: Int64,
        nonce: String
    )
    private typealias P2PQRCodeMaterial = (
        routeClass: String,
        recordID: String,
        encryptedBody: String,
        expiresAtEpochMillis: Int64,
        antiReplayNonce: String,
        protocolVersion: Int
    )

    public var id: String { nonce }
    public var code: String
    public var nonce: String
    public var expiresAt: Date
    public var macDeviceID: String
    public var macName: String
    public var fingerprint: String
    public var runtimePublicKeyBase64: String?
    public var routeToken: String?
    public var host: String?
    public var port: Int?
    public var relayHost: String?
    public var relayPort: Int?
    public var relayID: String?
    public var relaySecret: String?
    public var relayExpiresAtEpochMillis: Int64?
    public var relayNonce: String?
    public var relayScope: String?
    public var p2pRouteClass: String?
    public var p2pRecordID: String?
    public var p2pEncryptedBody: String?
    public var p2pExpiresAtEpochMillis: Int64?
    public var p2pAntiReplayNonce: String?
    public var p2pProtocolVersion: Int?
    public var serviceType: String

    public var qrPayload: String {
        pairingPayload(compact: false)
    }

    public var compactQRCodePayload: String {
        pairingPayload(compact: true)
    }

    /// Whether QR payload emission will include the complete canonical relay field set.
    public var hasCompleteCanonicalRelayQRCodeMaterial: Bool {
        relayQRCodeMaterial() != nil
    }

    public static func hasCompleteCanonicalRelayQRCodeMaterial(
        relayHost: String?,
        relayPort: Int?,
        relayID: String?,
        relaySecret: String?,
        relayExpiresAtEpochMillis: Int64?,
        relayNonce: String?,
        relayScope: String?
    ) -> Bool {
        relayQRCodeMaterial(
            relayHost: relayHost,
            relayPort: relayPort,
            relayID: relayID,
            relaySecret: relaySecret,
            relayExpiresAtEpochMillis: relayExpiresAtEpochMillis,
            relayNonce: relayNonce,
            relayScope: relayScope
        ) != nil
    }

    private func pairingPayload(compact: Bool) -> String {
        var components = URLComponents()
        components.scheme = "aetherlink"
        components.host = "pair"
        var queryItems = [
            URLQueryItem(name: compact ? "v" : "version", value: "1"),
            URLQueryItem(name: compact ? "n" : "pairing_nonce", value: nonce),
            URLQueryItem(name: compact ? "c" : "pairing_code", value: code),
            URLQueryItem(name: compact ? "rid" : "runtime_device_id", value: macDeviceID),
            URLQueryItem(name: compact ? "rn" : "runtime_name", value: macName),
            URLQueryItem(name: compact ? "rf" : "runtime_key_fingerprint", value: fingerprint)
        ]
        if let runtimePublicKeyBase64 = Self.canonicalOpaqueQRCodeValue(runtimePublicKeyBase64) {
            queryItems.append(URLQueryItem(name: compact ? "rk" : "runtime_public_key", value: runtimePublicKeyBase64))
        }
        if let routeToken = Self.canonicalOpaqueQRCodeValue(routeToken) {
            queryItems.append(URLQueryItem(name: compact ? "rt" : "route_token", value: routeToken))
        }
        if let p2pMaterial = p2pQRCodeMaterial() {
            queryItems.append(URLQueryItem(name: compact ? "pc" : "p2p_class", value: p2pMaterial.routeClass))
            queryItems.append(URLQueryItem(name: compact ? "prid" : "p2p_record_id", value: p2pMaterial.recordID))
            queryItems.append(URLQueryItem(name: compact ? "peb" : "p2p_encrypted_body", value: p2pMaterial.encryptedBody))
            queryItems.append(URLQueryItem(name: compact ? "px" : "p2p_expires_at", value: String(p2pMaterial.expiresAtEpochMillis)))
            queryItems.append(URLQueryItem(name: compact ? "pn" : "p2p_anti_replay_nonce", value: p2pMaterial.antiReplayNonce))
            queryItems.append(URLQueryItem(name: compact ? "pv" : "p2p_protocol_version", value: String(p2pMaterial.protocolVersion)))
        }
        if let host {
            queryItems.append(URLQueryItem(name: compact ? "h" : "host", value: host))
        }
        if let port {
            queryItems.append(URLQueryItem(name: compact ? "p" : "port", value: String(port)))
        }
        let relayMaterial = relayQRCodeMaterial()
        if let relayMaterial {
            queryItems.append(URLQueryItem(name: compact ? "rh" : "relay_host", value: relayMaterial.host))
            queryItems.append(URLQueryItem(name: compact ? "rp" : "relay_port", value: String(relayMaterial.port)))
            queryItems.append(URLQueryItem(name: compact ? "ri" : "relay_id", value: relayMaterial.id))
            queryItems.append(URLQueryItem(name: compact ? "rs" : "relay_secret", value: relayMaterial.secret))
            queryItems.append(URLQueryItem(name: compact ? "rx" : "relay_expires_at", value: String(relayMaterial.expiresAtEpochMillis)))
            queryItems.append(URLQueryItem(name: compact ? "rrn" : "relay_nonce", value: relayMaterial.nonce))
        }
        if let relayScope, !relayScope.isEmpty, relayMaterial != nil || relayHost == nil {
            let canonicalScopeName = relayMaterial == nil ? "route_scope" : "relay_scope"
            queryItems.append(URLQueryItem(name: compact ? "rsc" : canonicalScopeName, value: relayScope))
        }
        components.queryItems = queryItems
        if let percentEncodedQuery = components.percentEncodedQuery {
            components.percentEncodedQuery = percentEncodedQuery.replacingOccurrences(of: "+", with: "%2B")
        }
        return components.string ?? "aetherlink://pair"
    }

    private func relayQRCodeMaterial() -> RelayQRCodeMaterial? {
        Self.relayQRCodeMaterial(
            relayHost: relayHost,
            relayPort: relayPort,
            relayID: relayID,
            relaySecret: relaySecret,
            relayExpiresAtEpochMillis: relayExpiresAtEpochMillis,
            relayNonce: relayNonce,
            relayScope: relayScope
        )
    }

    private static func relayQRCodeMaterial(
        relayHost rawRelayHost: String?,
        relayPort: Int?,
        relayID: String?,
        relaySecret: String?,
        relayExpiresAtEpochMillis: Int64?,
        relayNonce: String?,
        relayScope: String?
    ) -> RelayQRCodeMaterial? {
        guard let rawRelayHost,
              let relayHost = Self.canonicalRelayHostValue(rawRelayHost),
              Self.relayHostMatchesRelayScope(relayHost, relayScope: relayScope),
              let relayPort,
              (1...65_535).contains(relayPort),
              let relayID = Self.canonicalOpaqueQRCodeValue(relayID),
              let relaySecret = Self.canonicalOpaqueQRCodeValue(relaySecret),
              let relayExpiresAtEpochMillis,
              relayExpiresAtEpochMillis > 0,
              let relayNonce = Self.canonicalOpaqueQRCodeValue(relayNonce)
        else {
            return nil
        }
        return (
            host: relayHost,
            port: relayPort,
            id: relayID,
            secret: relaySecret,
            expiresAtEpochMillis: relayExpiresAtEpochMillis,
            nonce: relayNonce
        )
    }

    private static func relayHostMatchesRelayScope(_ relayHost: String, relayScope: String?) -> Bool {
        guard let normalizedHost = canonicalRelayHostValue(relayHost) else { return false }
        if isLoopbackRelayHost(normalizedHost) {
            return relayScope == "usb_reverse"
        }
        if isLocalOnlyRelayHost(normalizedHost) {
            return false
        }
        if normalizedHost.isPrivateOrLocalIPv4RelayLiteral() ||
            normalizedHost.isPrivateOrLocalIPv6RelayLiteral() {
            return relayScope == "private_overlay" &&
                normalizedHost.isPrivateOverlayRelayLiteral()
        }
        return relayScope == nil || relayScope == "remote"
    }

    private static func canonicalRelayHostValue(_ relayHost: String) -> String? {
        let normalizedHost = relayHost
            .trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
            .trimmingCharacters(in: CharacterSet(charactersIn: "."))
            .lowercased()
        guard !relayHost.isEmpty,
              relayHost.trimmingCharacters(in: .whitespacesAndNewlines) == relayHost,
              relayHost.rangeOfCharacter(from: .whitespacesAndNewlines) == nil,
              !relayHost.contains("://"),
              relayHost.allSatisfy({ !["/", "?", "#", "@"].contains($0) }),
              !normalizedHost.contains(":") || normalizedHost.isIPv6RelayLiteralShape
        else {
            return nil
        }
        return normalizedHost
    }

    private static func isLoopbackRelayHost(_ host: String) -> Bool {
        host == "localhost" ||
            host == "::1" ||
            host == "0:0:0:0:0:0:0:1" ||
            host.hasPrefix("127.")
    }

    private static func isLocalOnlyRelayHost(_ host: String) -> Bool {
        host == "local" ||
            host.hasSuffix(".local") ||
            host == "0.0.0.0" ||
            host == "::" ||
            host == "0:0:0:0:0:0:0:0" ||
            host.hasPrefix("169.254.") ||
            host.hasPrefix("fe80:") ||
            host.isIPv4MulticastRelayLiteral() ||
            host.isIPv6MulticastRelayLiteral()
    }

    private func p2pQRCodeMaterial() -> P2PQRCodeMaterial? {
        guard p2pRouteClass == "p2p_rendezvous",
              let p2pRecordID = Self.canonicalOpaqueQRCodeValue(p2pRecordID),
              let p2pEncryptedBody = Self.canonicalOpaqueQRCodeValue(
                  p2pEncryptedBody,
                  maxLength: Self.opaqueQRBodyMaxLength
              ),
              let p2pExpiresAtEpochMillis,
              p2pExpiresAtEpochMillis > 0,
              let p2pAntiReplayNonce = Self.canonicalOpaqueQRCodeValue(p2pAntiReplayNonce),
              p2pProtocolVersion == 1
        else {
            return nil
        }
        return (
            routeClass: "p2p_rendezvous",
            recordID: p2pRecordID,
            encryptedBody: p2pEncryptedBody,
            expiresAtEpochMillis: p2pExpiresAtEpochMillis,
            antiReplayNonce: p2pAntiReplayNonce,
            protocolVersion: 1
        )
    }

    private static func canonicalOpaqueQRCodeValue(_ value: String?) -> String? {
        canonicalOpaqueQRCodeValue(value, maxLength: opaqueQRValueMaxLength)
    }

    private static func canonicalOpaqueQRCodeValue(_ value: String?, maxLength: Int) -> String? {
        guard let value,
              !value.isEmpty,
              value.count <= maxLength,
              value.trimmingCharacters(in: .whitespacesAndNewlines) == value,
              value.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
        else {
            return nil
        }
        return value
    }

    private static let opaqueQRValueMaxLength = 512
    private static let opaqueQRBodyMaxLength = 2_048
}

private extension String {
    func isPrivateOverlayRelayLiteral() -> Bool {
        isPrivateOverlayIPv4RelayLiteral() || isPrivateOverlayIPv6RelayLiteral()
    }

    func isPrivateOrLocalIPv4RelayLiteral() -> Bool {
        guard let octets = ipv4Octets else { return false }
        let first = octets[0]
        let second = octets[1]
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
            hasPrefix("fd") ||
            hasPrefix("ff")
    }

    func isIPv4MulticastRelayLiteral() -> Bool {
        guard let octets = ipv4Octets else { return false }
        return octets[0] >= 224
    }

    func isIPv6MulticastRelayLiteral() -> Bool {
        contains(":") && hasPrefix("ff")
    }

    private func isPrivateOverlayIPv4RelayLiteral() -> Bool {
        guard let octets = ipv4Octets else { return false }
        let first = octets[0]
        let second = octets[1]
        return first == 10 ||
            (first == 100 && (64...127).contains(second)) ||
            (first == 172 && (16...31).contains(second)) ||
            (first == 192 && second == 168)
    }

    private func isPrivateOverlayIPv6RelayLiteral() -> Bool {
        guard contains(":") else { return false }
        return hasPrefix("fc") || hasPrefix("fd")
    }

    private var ipv4Octets: [Int]? {
        let octets = split(separator: ".", omittingEmptySubsequences: false)
        guard octets.count == 4 else { return nil }
        let values = octets.compactMap { part -> Int? in
            guard !part.isEmpty,
                  part.allSatisfy(\.isNumber),
                  let value = Int(part),
                  (0...255).contains(value)
            else {
                return nil
            }
            return value
        }
        return values.count == 4 ? values : nil
    }

    var isIPv6RelayLiteralShape: Bool {
        allSatisfy { character in
            character.isHexDigit || character == ":"
        }
    }
}

public struct PairingRequest: Equatable, Sendable {
    public var requestID: String
    public var pairingNonce: String
    public var pairingCode: String
    public var deviceID: String
    public var deviceName: String
    public var publicKeyBase64: String
    public var proofScheme: String
    public var signatureBase64: String
    public var transportBinding: String?

    public init(
        requestID: String,
        pairingNonce: String,
        pairingCode: String,
        deviceID: String,
        deviceName: String,
        publicKeyBase64: String,
        proofScheme: String,
        signatureBase64: String,
        transportBinding: String?
    ) {
        self.requestID = requestID
        self.pairingNonce = pairingNonce
        self.pairingCode = pairingCode
        self.deviceID = deviceID
        self.deviceName = deviceName
        self.publicKeyBase64 = publicKeyBase64
        self.proofScheme = proofScheme
        self.signatureBase64 = signatureBase64
        self.transportBinding = transportBinding
    }
}

public struct PairingValidationResult: Equatable, Sendable {
    public var trustedDevice: TrustedDevice
    public var macDeviceID: String
    public var macName: String
    public var runtimePublicKeyBase64: String?
    public var runtimeKeyFingerprint: String
    public var pairingRequestDigest: String
}

public enum PairingRejectionReason: String, Equatable, Sendable {
    case noActiveSession = "pairing_not_active"
    case expired = "pairing_expired"
    case invalidCredentials = "pairing_invalid"
    case invalidDeviceIdentity = "pairing_invalid_device_identity"
    case inProgress = "pairing_in_progress"
    case attemptsExceeded = "pairing_attempts_exceeded"
}

public struct PairingRejection: Equatable, Sendable {
    public var reason: PairingRejectionReason
    public var message: String
    public var retryable: Bool
    public var failedAttempts: Int
    public var maxFailedAttempts: Int
    public var remainingAttempts: Int

    public var code: String { reason.rawValue }
}

public enum PairingValidationOutcome: Equatable, Sendable {
    case accepted(PairingValidationResult)
    case rejected(PairingRejection)
}

public final class PairingCoordinator: @unchecked Sendable {
    public static let defaultMaxFailedAttempts = 3
    private static let allowedRelayRouteScopes: Set<String> = [
        "remote",
        "private_overlay",
        "usb_reverse"
    ]
    private static let localDiagnosticRouteScope = "local_diagnostic"

    private let lock = NSLock()
    public let maxFailedAttempts: Int
    private var activeSession: PairingSession?
    private var reservedRequestDigest: String?
    private var failedAttempts = 0

    public init(maxFailedAttempts: Int = PairingCoordinator.defaultMaxFailedAttempts) {
        precondition(maxFailedAttempts > 0, "maxFailedAttempts must be greater than zero")
        self.maxFailedAttempts = maxFailedAttempts
    }

    public func beginPairing(
        validFor seconds: TimeInterval = 300,
        macDeviceID: String,
        macName: String = "AetherLink Runtime",
        fingerprint: String,
        runtimePublicKeyBase64: String? = nil,
        routeToken: String? = nil,
        host: String? = nil,
        port: Int? = nil,
        relayHost: String? = nil,
        relayPort: Int? = nil,
        relayID: String? = nil,
        relaySecret: String? = nil,
        relayExpiresAtEpochMillis: Int64? = nil,
        relayNonce: String? = nil,
        relayScope: String? = nil,
        p2pRouteClass: String? = nil,
        p2pRecordID: String? = nil,
        p2pEncryptedBody: String? = nil,
        p2pExpiresAtEpochMillis: Int64? = nil,
        p2pAntiReplayNonce: String? = nil,
        p2pProtocolVersion: Int? = nil,
        serviceType: String = "_aetherlink._tcp.local."
    ) -> PairingSession {
        let code = String(format: "%06d", Int.random(in: 0...999_999))
        let nonce = UUID().uuidString
        let session = PairingSession(
            code: code,
            nonce: nonce,
            expiresAt: Date().addingTimeInterval(seconds),
            macDeviceID: macDeviceID,
            macName: macName,
            fingerprint: fingerprint,
            runtimePublicKeyBase64: runtimePublicKeyBase64,
            routeToken: routeToken,
            host: host,
            port: port,
            relayHost: relayHost,
            relayPort: relayPort,
            relayID: relayID,
            relaySecret: relaySecret,
            relayExpiresAtEpochMillis: relayExpiresAtEpochMillis,
            relayNonce: relayNonce,
            relayScope: Self.validatedRelayScope(
                relayScope,
                hasDirectEndpoint: host != nil,
                hasRelayRoute: relayHost != nil
            ),
            p2pRouteClass: p2pRouteClass,
            p2pRecordID: p2pRecordID,
            p2pEncryptedBody: p2pEncryptedBody,
            p2pExpiresAtEpochMillis: p2pExpiresAtEpochMillis,
            p2pAntiReplayNonce: p2pAntiReplayNonce,
            p2pProtocolVersion: p2pProtocolVersion,
            serviceType: serviceType
        )
        return lock.withLock {
            if reservedRequestDigest != nil, let activeSession {
                return activeSession
            }
            activeSession = session
            reservedRequestDigest = nil
            failedAttempts = 0
            return session
        }
    }

    private static func validatedRelayScope(
        _ relayScope: String?,
        hasDirectEndpoint: Bool,
        hasRelayRoute: Bool
    ) -> String? {
        let requestedScope = relayScope.flatMap { $0.isEmpty ? nil : $0 }
        if hasRelayRoute {
            guard let requestedScope else { return nil }
            return allowedRelayRouteScopes.contains(requestedScope) ? requestedScope : nil
        }
        if hasDirectEndpoint {
            let requestedScope = requestedScope ?? localDiagnosticRouteScope
            return requestedScope == localDiagnosticRouteScope ? requestedScope : nil
        }
        return nil
    }

    public func validate(_ request: PairingRequest) -> PairingValidationOutcome {
        lock.withLock {
            guard let session = activeSession else {
                return .rejected(rejection(
                    reason: .noActiveSession,
                    message: "No active pairing session is available.",
                    retryable: false,
                    failedAttempts: 0,
                    remainingAttempts: 0
                ))
            }
            guard session.expiresAt > Date() else {
                activeSession = nil
                reservedRequestDigest = nil
                failedAttempts = 0
                return .rejected(rejection(
                    reason: .expired,
                    message: "Pairing session expired. Start pairing again in AetherLink Runtime.",
                    retryable: false,
                    failedAttempts: 0,
                    remainingAttempts: 0
                ))
            }
            guard reservedRequestDigest == nil else {
                return .rejected(rejection(
                    reason: .inProgress,
                    message: "Another pairing request is being committed.",
                    retryable: true,
                    failedAttempts: failedAttempts,
                    remainingAttempts: max(0, maxFailedAttempts - failedAttempts)
                ))
            }
            guard request.pairingNonce == session.nonce, request.pairingCode == session.code else {
                failedAttempts += 1
                let remainingAttempts = max(0, maxFailedAttempts - failedAttempts)
                guard failedAttempts < maxFailedAttempts else {
                    let rejection = rejection(
                        reason: .attemptsExceeded,
                        message: "Too many invalid pairing attempts. Start pairing again in AetherLink Runtime.",
                        retryable: false,
                        failedAttempts: failedAttempts,
                        remainingAttempts: remainingAttempts
                    )
                    activeSession = nil
                    reservedRequestDigest = nil
                    failedAttempts = 0
                    return .rejected(rejection)
                }
                return .rejected(rejection(
                    reason: .invalidCredentials,
                    message: "Pairing code or nonce was rejected.",
                    retryable: true,
                    failedAttempts: failedAttempts,
                    remainingAttempts: remainingAttempts
                ))
            }
            guard let validated = Self.validatedDeviceAndProof(from: request, session: session) else {
                failedAttempts += 1
                let remainingAttempts = max(0, maxFailedAttempts - failedAttempts)
                guard failedAttempts < maxFailedAttempts else {
                    let rejection = rejection(
                        reason: .attemptsExceeded,
                        message: "Too many invalid pairing attempts. Start pairing again in AetherLink Runtime.",
                        retryable: false,
                        failedAttempts: failedAttempts,
                        remainingAttempts: remainingAttempts
                    )
                    activeSession = nil
                    reservedRequestDigest = nil
                    failedAttempts = 0
                    return .rejected(rejection)
                }
                return .rejected(rejection(
                    reason: .invalidDeviceIdentity,
                    message: "Pairing device identity was rejected.",
                    retryable: true,
                    failedAttempts: failedAttempts,
                    remainingAttempts: remainingAttempts
                ))
            }
            reservedRequestDigest = validated.requestDigest
            return .accepted(PairingValidationResult(
                trustedDevice: validated.trustedDevice,
                macDeviceID: session.macDeviceID,
                macName: session.macName,
                runtimePublicKeyBase64: session.runtimePublicKeyBase64,
                runtimeKeyFingerprint: session.fingerprint,
                pairingRequestDigest: validated.requestDigest
            ))
        }
    }

    @discardableResult
    public func commitPairing(requestDigest: String) -> Bool {
        lock.withLock {
            guard reservedRequestDigest == requestDigest else { return false }
            activeSession = nil
            reservedRequestDigest = nil
            failedAttempts = 0
            return true
        }
    }

    @discardableResult
    public func releasePairing(requestDigest: String) -> Bool {
        lock.withLock {
            guard reservedRequestDigest == requestDigest else { return false }
            reservedRequestDigest = nil
            return true
        }
    }

    private func rejection(
        reason: PairingRejectionReason,
        message: String,
        retryable: Bool,
        failedAttempts: Int,
        remainingAttempts: Int
    ) -> PairingRejection {
        PairingRejection(
            reason: reason,
            message: message,
            retryable: retryable,
            failedAttempts: failedAttempts,
            maxFailedAttempts: maxFailedAttempts,
            remainingAttempts: remainingAttempts
        )
    }

    private static func validatedDeviceAndProof(
        from request: PairingRequest,
        session: PairingSession
    ) -> (trustedDevice: TrustedDevice, requestDigest: String)? {
        guard let deviceID = request.deviceID.opaquePairingValue(),
              deviceID.count <= 128,
              let publicKeyBase64 = request.publicKeyBase64.opaquePairingValue(),
              publicKeyBase64.count <= 4_096,
              let publicKeyData = Data(base64Encoded: publicKeyBase64),
              publicKeyData.base64EncodedString() == publicKeyBase64,
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: publicKeyData),
              publicKey.derRepresentation == publicKeyData,
              let runtimePublicKeyBase64 = session.runtimePublicKeyBase64,
              let runtimePublicKeyData = Data(base64Encoded: runtimePublicKeyBase64),
              runtimePublicKeyData.base64EncodedString() == runtimePublicKeyBase64
        else {
            return nil
        }
        let clientKeyFingerprint = SHA256.hash(data: publicKeyData)
            .map { String(format: "%02x", $0) }
            .joined()
        guard let proof = try? InitialPairingClientProof(
            scheme: request.proofScheme,
            requestID: request.requestID,
            pairingNonce: request.pairingNonce,
            pairingCode: request.pairingCode,
            runtimeDeviceID: session.macDeviceID,
            runtimePublicKey: runtimePublicKeyBase64,
            runtimeKeyFingerprint: session.fingerprint,
            clientDeviceID: request.deviceID,
            clientDeviceName: request.deviceName,
            clientPublicKey: publicKeyBase64,
            clientKeyFingerprint: clientKeyFingerprint,
            transportBinding: request.transportBinding ?? "none",
            signatureBase64: request.signatureBase64
        ), proof.verify() else {
            return nil
        }
        return (TrustedDevice(
            id: deviceID,
            name: request.deviceName.normalizedDeviceName(),
            publicKeyBase64: publicKeyBase64
        ), proof.requestDigest())
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}

private extension String {
    func opaquePairingValue() -> String? {
        guard !isEmpty,
              self == trimmingCharacters(in: .whitespacesAndNewlines),
              rangeOfCharacter(from: .pairingOpaqueInvalidCharacters) == nil
        else {
            return nil
        }
        return self
    }

    func normalizedDeviceName() -> String {
        let collapsed = trimmingCharacters(in: .pairingDisplaySeparators)
            .components(separatedBy: .pairingDisplaySeparators)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
        return String((collapsed.isEmpty ? "AetherLink Client" : collapsed).prefix(80))
    }
}

private extension CharacterSet {
    static var pairingOpaqueInvalidCharacters: CharacterSet {
        var set = CharacterSet.whitespacesAndNewlines
        set.formUnion(.controlCharacters)
        return set
    }

    static var pairingDisplaySeparators: CharacterSet {
        pairingOpaqueInvalidCharacters
    }
}
