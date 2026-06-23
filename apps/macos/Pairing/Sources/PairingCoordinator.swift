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
    public var host: String
    public var port: Int
    public var serviceType: String

    public var qrPayload: String {
        var components = URLComponents()
        components.scheme = "aetherlink"
        components.host = "pair"
        components.queryItems = [
            URLQueryItem(name: "version", value: "1"),
            URLQueryItem(name: "pairing_nonce", value: nonce),
            URLQueryItem(name: "pairing_code", value: code),
            URLQueryItem(name: "mac_device_id", value: macDeviceID),
            URLQueryItem(name: "mac_name", value: macName),
            URLQueryItem(name: "fingerprint", value: fingerprint),
            URLQueryItem(name: "host", value: host),
            URLQueryItem(name: "port", value: String(port)),
            URLQueryItem(name: "service_type", value: serviceType)
        ]
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

public final class PairingCoordinator: @unchecked Sendable {
    private let lock = NSLock()
    private var activeSession: PairingSession?

    public init() {}

    public func beginPairing(
        validFor seconds: TimeInterval = 300,
        macDeviceID: String,
        macName: String = "AetherLink Mac",
        fingerprint: String,
        host: String,
        port: Int,
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
            host: host,
            port: port,
            serviceType: serviceType
        )
        lock.withLock { activeSession = session }
        return session
    }

    public func validate(_ request: PairingRequest) -> PairingValidationResult? {
        lock.withLock {
            guard let session = activeSession else { return nil }
            guard session.expiresAt > Date() else {
                activeSession = nil
                return nil
            }
            guard request.pairingNonce == session.nonce, request.pairingCode == session.code else {
                return nil
            }
            activeSession = nil
            return PairingValidationResult(
                trustedDevice: TrustedDevice(
                    id: request.deviceID,
                    name: request.deviceName,
                    publicKeyBase64: request.publicKeyBase64
                ),
                macDeviceID: session.macDeviceID,
                macName: session.macName
            )
        }
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
