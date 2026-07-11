import BridgeProtocol
import Foundation

public protocol RuntimeDisconnectReporting: AnyObject {
    var onDisconnect: (@Sendable (UUID) -> Void)? { get set }
}

public protocol RuntimeTransport {
    var status: PeerServerStatus { get }

    func start(port: UInt16, onMessage: @escaping LocalPeerMessageHandler)
    func stop()
}

public protocol RuntimeAdvertiser {
    func start(port: Int32, metadata: RuntimeAdvertisementMetadata)
    func stop()
}

public extension RuntimeAdvertiser {
    func start(port: Int32) {
        start(port: port, metadata: RuntimeAdvertisementMetadata())
    }
}

public struct RuntimeAdvertisementMetadata: Equatable, Sendable {
    public var version: String
    public var routeToken: String?
    public var deviceID: String?
    public var fingerprint: String?
    public var app: String

    public init(
        version: String = "1",
        routeToken: String? = nil,
        deviceID: String? = nil,
        fingerprint: String? = nil,
        app: String = "AetherLink"
    ) {
        self.version = version
        self.routeToken = routeToken
        self.deviceID = deviceID
        self.fingerprint = fingerprint
        self.app = app
    }

    public var txtRecord: [String: String] {
        var record: [String: String] = [:]
        if let version = Self.safeDiscoveryTXTValue(version) {
            record["version"] = version
        }
        if let app = Self.safeDiscoveryTXTValue(app) {
            record["app"] = app
        }
        if let routeToken = Self.safeDiscoveryTXTValue(
            routeToken,
            normalizesDisplayWhitespace: false,
            rejectsWhitespace: true
        ) {
            record["route_token"] = routeToken
        }
        return record
    }

    public var txtRecordData: [String: Data] {
        txtRecord.mapValues { Data($0.utf8) }
    }

    private static func safeDiscoveryTXTValue(
        _ rawValue: String?,
        normalizesDisplayWhitespace: Bool = true,
        rejectsWhitespace: Bool = false
    ) -> String? {
        guard let rawValue else {
            return nil
        }
        let value = normalizesDisplayWhitespace
            ? rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
            : rawValue
        guard !value.isEmpty, value.count <= 160 else {
            return nil
        }
        if rejectsWhitespace,
           value.rangeOfCharacter(from: .whitespacesAndNewlines) != nil {
            return nil
        }
        guard value.rangeOfCharacter(from: .controlCharacters) == nil else {
            return nil
        }
        guard !containsForbiddenDiscoveryMaterial(value) else {
            return nil
        }
        return value
    }

    private static func containsForbiddenDiscoveryMaterial(_ value: String) -> Bool {
        let lowercased = value.lowercased()
        let forbiddenFragments = [
            "http://",
            "https://",
            "ws://",
            "wss://",
            ":11434",
            ":1234",
            "/api/",
            "/v1/",
            "ollama",
            "lm studio",
            "backend_url",
            "backend-url",
            "provider_url",
            "provider-url",
            "requested_route_token",
            "requested-route-token",
            "route_secret",
            "route-secret",
            "relay_secret",
            "relay-secret",
            "pairing_secret",
            "pairing-secret",
            "api_key",
            "api-key",
            "authorization",
            "bearer ",
            "models.list",
            "models.pull",
            "chat.send",
            "chat.cancel",
            "memory.",
            "prompt=",
            "response=",
            "file=",
        ]
        return forbiddenFragments.contains { lowercased.contains($0) }
    }
}
