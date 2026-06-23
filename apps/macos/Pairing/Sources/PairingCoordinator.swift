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
    public var routeToken: String?
    public var host: String?
    public var port: Int?
    public var serviceType: String

    public var qrPayload: String {
        var components = URLComponents()
        components.scheme = "aetherlink"
        components.host = "pair"
        var queryItems = [
            URLQueryItem(name: "version", value: "1"),
            URLQueryItem(name: "pairing_nonce", value: nonce),
            URLQueryItem(name: "pairing_code", value: code),
            URLQueryItem(name: "mac_device_id", value: macDeviceID),
            URLQueryItem(name: "mac_name", value: macName),
            URLQueryItem(name: "fingerprint", value: fingerprint),
            URLQueryItem(name: "service_type", value: serviceType)
        ]
        if let routeToken, !routeToken.isEmpty {
            queryItems.append(URLQueryItem(name: "route_token", value: routeToken))
        }
        if let host {
            queryItems.append(URLQueryItem(name: "host", value: host))
        }
        if let port {
            queryItems.append(URLQueryItem(name: "port", value: String(port)))
        }
        components.queryItems = queryItems
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
}

public enum PairingRejectionReason: String, Equatable, Sendable {
    case noActiveSession = "pairing_not_active"
    case expired = "pairing_expired"
    case invalidCredentials = "pairing_invalid"
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
        macName: String = "AetherLink Mac",
        fingerprint: String,
        routeToken: String? = nil,
        host: String? = nil,
        port: Int? = nil,
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
            routeToken: routeToken,
            host: host,
            port: port,
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
                    message: "Pairing session expired. Start pairing again on the Mac.",
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
                        message: "Too many invalid pairing attempts. Start pairing again on the Mac.",
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
            activeSession = nil
            failedAttempts = 0
            return .accepted(PairingValidationResult(
                trustedDevice: TrustedDevice(
                    id: request.deviceID,
                    name: request.deviceName,
                    publicKeyBase64: request.publicKeyBase64
                ),
                macDeviceID: session.macDeviceID,
                macName: session.macName
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
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
