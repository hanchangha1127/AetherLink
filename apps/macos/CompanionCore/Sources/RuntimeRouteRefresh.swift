import Foundation

public struct RuntimeRouteRefreshResult: Equatable, Sendable {
    public var runtimeDeviceID: String
    public var runtimeKeyFingerprint: String
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

    public init(
        runtimeDeviceID: String,
        runtimeKeyFingerprint: String,
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
        p2pProtocolVersion: Int? = nil
    ) {
        self.runtimeDeviceID = runtimeDeviceID
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.relayHost = relayHost
        self.relayPort = relayPort
        self.relayID = relayID
        self.relaySecret = relaySecret
        self.relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
        self.relayNonce = relayNonce
        self.relayScope = relayScope
        self.p2pRouteClass = p2pRouteClass
        self.p2pRecordID = p2pRecordID
        self.p2pEncryptedBody = p2pEncryptedBody
        self.p2pExpiresAtEpochMillis = p2pExpiresAtEpochMillis
        self.p2pAntiReplayNonce = p2pAntiReplayNonce
        self.p2pProtocolVersion = p2pProtocolVersion
    }
}

@MainActor
public protocol RuntimeRouteRefreshing: AnyObject {
    func refreshRuntimeRoute() async throws -> RuntimeRouteRefreshResult?
}
