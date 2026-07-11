import BridgeProtocol
import Foundation

public typealias RuntimePairedRelayAuthorizationProvider = @Sendable (
    PairedRelayAllocationAuthorizationChallenge
) async throws -> PairedRelayAllocationClientProof

public struct RuntimePairedRelayAuthorizationContext: Sendable {
    public let requestID: String
    public let connectionID: UUID
    public let trustedClientPublicKeyBase64: String
    public let trustedClientKeyFingerprint: String
    public let transportBinding: String
    public let clientAuthorizationProvider: RuntimePairedRelayAuthorizationProvider

    public init(
        requestID: String,
        connectionID: UUID,
        trustedClientPublicKeyBase64: String,
        trustedClientKeyFingerprint: String,
        transportBinding: String,
        clientAuthorizationProvider: @escaping RuntimePairedRelayAuthorizationProvider
    ) throws {
        guard PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(requestID),
              PairedRelayAllocationAuthorization.isCanonicalDigest(transportBinding)
        else {
            throw RuntimeRouteRefreshAuthorizationError.invalidContext
        }
        do {
            _ = try PairedRelayAllocationAuthorization.validatedClientPublicKey(
                base64: trustedClientPublicKeyBase64,
                fingerprint: trustedClientKeyFingerprint
            )
        } catch {
            throw RuntimeRouteRefreshAuthorizationError.invalidContext
        }
        self.requestID = requestID
        self.connectionID = connectionID
        self.trustedClientPublicKeyBase64 = trustedClientPublicKeyBase64
        self.trustedClientKeyFingerprint = trustedClientKeyFingerprint
        self.transportBinding = transportBinding
        self.clientAuthorizationProvider = clientAuthorizationProvider
    }
}

public enum RuntimeRouteRefreshAuthorizationError: Error, Equatable, LocalizedError, Sendable {
    case invalidContext
    case pairedAuthorizationRequired

    public var errorDescription: String? {
        switch self {
        case .invalidContext:
            return "The paired relay authorization context is invalid."
        case .pairedAuthorizationRequired:
            return "Authenticated route refresh requires paired client authorization."
        }
    }
}

public struct RuntimeRouteRefreshResult: Equatable, Sendable {
    public var runtimeDeviceID: String
    public var runtimeKeyFingerprint: String
    public var relayHost: String?
    public var relayPort: Int?
    public var relayID: String?
    public var relaySecret: String?
    public var relayExpiresAtEpochMillis: Int64?
    public var relayNonce: String?
    public var relayTicketGeneration: Int64?
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
        relayTicketGeneration: Int64? = nil,
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
        self.relayTicketGeneration = relayTicketGeneration
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
    func refreshRuntimeRoute(
        authorizationContext: RuntimePairedRelayAuthorizationContext?
    ) async throws -> RuntimeRouteRefreshResult?
    func activateRuntimeRouteRefresh(_ result: RuntimeRouteRefreshResult) async
}

public extension RuntimeRouteRefreshing {
    func refreshRuntimeRoute(
        authorizationContext: RuntimePairedRelayAuthorizationContext?
    ) async throws -> RuntimeRouteRefreshResult? {
        guard authorizationContext == nil else {
            throw RuntimeRouteRefreshAuthorizationError.pairedAuthorizationRequired
        }
        return try await refreshRuntimeRoute()
    }

    func activateRuntimeRouteRefresh(_ result: RuntimeRouteRefreshResult) async {}
}
