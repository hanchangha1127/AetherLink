import CryptoKit
import Foundation
import TrustedDevices

public struct PairingSession: Identifiable, Equatable, Sendable {
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
        if let runtimePublicKeyBase64, !runtimePublicKeyBase64.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "rk" : "runtime_public_key", value: runtimePublicKeyBase64))
        }
        if let routeToken, !routeToken.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "rt" : "route_token", value: routeToken))
        }
        if let p2pRouteClass, !p2pRouteClass.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "pc" : "p2p_class", value: p2pRouteClass))
        }
        if let p2pRecordID, !p2pRecordID.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "prid" : "p2p_record_id", value: p2pRecordID))
        }
        if let p2pEncryptedBody, !p2pEncryptedBody.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "peb" : "p2p_encrypted_body", value: p2pEncryptedBody))
        }
        if let p2pExpiresAtEpochMillis {
            queryItems.append(URLQueryItem(name: compact ? "px" : "p2p_expires_at", value: String(p2pExpiresAtEpochMillis)))
        }
        if let p2pAntiReplayNonce, !p2pAntiReplayNonce.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "pn" : "p2p_anti_replay_nonce", value: p2pAntiReplayNonce))
        }
        if let p2pProtocolVersion {
            queryItems.append(URLQueryItem(name: compact ? "pv" : "p2p_protocol_version", value: String(p2pProtocolVersion)))
        }
        if let host {
            queryItems.append(URLQueryItem(name: compact ? "h" : "host", value: host))
        }
        if let port {
            queryItems.append(URLQueryItem(name: compact ? "p" : "port", value: String(port)))
        }
        if let relayHost, !relayHost.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "rh" : "relay_host", value: relayHost))
        }
        if let relayPort {
            queryItems.append(URLQueryItem(name: compact ? "rp" : "relay_port", value: String(relayPort)))
        }
        if let relayID, !relayID.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "ri" : "relay_id", value: relayID))
        }
        if let relaySecret, !relaySecret.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "rs" : "relay_secret", value: relaySecret))
        }
        if let relayExpiresAtEpochMillis {
            queryItems.append(URLQueryItem(name: compact ? "rx" : "relay_expires_at", value: String(relayExpiresAtEpochMillis)))
        }
        if let relayNonce, !relayNonce.isEmpty {
            queryItems.append(URLQueryItem(name: compact ? "rrn" : "relay_nonce", value: relayNonce))
        }
        if let relayScope, !relayScope.isEmpty {
            let canonicalScopeName = relayHost == nil ? "route_scope" : "relay_scope"
            queryItems.append(URLQueryItem(name: compact ? "rsc" : canonicalScopeName, value: relayScope))
        }
        components.queryItems = queryItems
        if let percentEncodedQuery = components.percentEncodedQuery {
            components.percentEncodedQuery = percentEncodedQuery.replacingOccurrences(of: "+", with: "%2B")
        }
        return components.string ?? "aetherlink://pair"
    }
}

public struct PairingRequest: Equatable, Sendable {
    public var pairingNonce: String
    public var pairingCode: String
    public var deviceID: String
    public var deviceName: String
    public var publicKeyBase64: String

    public init(
        pairingNonce: String,
        pairingCode: String,
        deviceID: String,
        deviceName: String,
        publicKeyBase64: String
    ) {
        self.pairingNonce = pairingNonce
        self.pairingCode = pairingCode
        self.deviceID = deviceID
        self.deviceName = deviceName
        self.publicKeyBase64 = publicKeyBase64
    }
}

public struct PairingValidationResult: Equatable, Sendable {
    public var trustedDevice: TrustedDevice
    public var macDeviceID: String
    public var macName: String
    public var runtimePublicKeyBase64: String?
    public var runtimeKeyFingerprint: String
}

public enum PairingRejectionReason: String, Equatable, Sendable {
    case noActiveSession = "pairing_not_active"
    case expired = "pairing_expired"
    case invalidCredentials = "pairing_invalid"
    case invalidDeviceIdentity = "pairing_invalid_device_identity"
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

    private let lock = NSLock()
    public let maxFailedAttempts: Int
    private var activeSession: PairingSession?
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
            relayScope: host == nil ? relayScope : relayScope ?? "local_diagnostic",
            p2pRouteClass: p2pRouteClass,
            p2pRecordID: p2pRecordID,
            p2pEncryptedBody: p2pEncryptedBody,
            p2pExpiresAtEpochMillis: p2pExpiresAtEpochMillis,
            p2pAntiReplayNonce: p2pAntiReplayNonce,
            p2pProtocolVersion: p2pProtocolVersion,
            serviceType: serviceType
        )
        lock.withLock {
            activeSession = session
            failedAttempts = 0
        }
        return session
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
                failedAttempts = 0
                return .rejected(rejection(
                    reason: .expired,
                    message: "Pairing session expired. Start pairing again in AetherLink Runtime.",
                    retryable: false,
                    failedAttempts: 0,
                    remainingAttempts: 0
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
            guard let trustedDevice = Self.trustedDevice(from: request) else {
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
            activeSession = nil
            failedAttempts = 0
            return .accepted(PairingValidationResult(
                trustedDevice: trustedDevice,
                macDeviceID: session.macDeviceID,
                macName: session.macName,
                runtimePublicKeyBase64: session.runtimePublicKeyBase64,
                runtimeKeyFingerprint: session.fingerprint
            ))
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

    private static func trustedDevice(from request: PairingRequest) -> TrustedDevice? {
        guard let deviceID = request.deviceID.opaquePairingValue(),
              deviceID.count <= 128,
              let publicKeyBase64 = request.publicKeyBase64.opaquePairingValue(),
              publicKeyBase64.count <= 4_096,
              let publicKeyData = Data(base64Encoded: publicKeyBase64),
              (try? P256.Signing.PublicKey(derRepresentation: publicKeyData)) != nil
        else {
            return nil
        }
        return TrustedDevice(
            id: deviceID,
            name: request.deviceName.normalizedDeviceName(),
            publicKeyBase64: publicKeyBase64
        )
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
