import Foundation

public struct RuntimeRouteRefreshResult: Equatable, Sendable {
    public var relayHost: String
    public var relayPort: Int
    public var relayID: String
    public var relaySecret: String
    public var relayExpiresAtEpochMillis: Int64
    public var relayNonce: String
    public var relayScope: String?

    public init(
        relayHost: String,
        relayPort: Int,
        relayID: String,
        relaySecret: String,
        relayExpiresAtEpochMillis: Int64,
        relayNonce: String,
        relayScope: String? = nil
    ) {
        self.relayHost = relayHost
        self.relayPort = relayPort
        self.relayID = relayID
        self.relaySecret = relaySecret
        self.relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
        self.relayNonce = relayNonce
        self.relayScope = relayScope
    }
}

@MainActor
public protocol RuntimeRouteRefreshing: AnyObject {
    func refreshRuntimeRoute() async throws -> RuntimeRouteRefreshResult?
}
