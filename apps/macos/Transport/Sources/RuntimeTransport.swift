import BridgeProtocol
import Foundation

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
        var record = [
            "version": version,
            "app": app
        ]
        if let routeToken, !routeToken.isEmpty {
            record["route_token"] = routeToken
        }
        if let deviceID, !deviceID.isEmpty {
            record["device_id"] = deviceID
        }
        if let fingerprint, !fingerprint.isEmpty {
            record["fingerprint"] = fingerprint
        }
        return record
    }

    public var txtRecordData: [String: Data] {
        txtRecord.mapValues { Data($0.utf8) }
    }
}
