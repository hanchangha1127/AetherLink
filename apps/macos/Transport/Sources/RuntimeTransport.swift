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

/// Opt-in transport surface for callers that own the frame-body protocol.
///
/// Bodies are still carried in the existing four-byte big-endian length frame,
/// but are delivered before `BridgeProtocol` JSON decoding. A connection is
/// created in either envelope mode or raw mode and must fail closed if callers
/// attempt to mix the two APIs.
public protocol RuntimeRawFrameBodyTransport {
    func startRaw(
        port: UInt16,
        onFrameBody: @escaping LocalPeerRawFrameBodyHandler
    )
}

/// Listener surface for production raw endpoints.
///
/// This path is deliberately separate from both legacy envelope decoding and
/// the eager `startRaw` callback. The caller must install a one-use
/// authorization before a connection is accepted. An accepted connection with
/// no authorization is closed without reading any peer bytes.
public protocol RuntimeAcceptedRawSessionTransport: AnyObject {
    var status: PeerServerStatus { get }

    func startAcceptedRaw(
        port: UInt16,
        onAcceptedSession: @escaping @Sendable (
            any RuntimeAcceptedRawSession
        ) -> Void
    )

    /// Transfers ownership of `authorization` to the transport regardless of
    /// the return value. Only one authorization may wait for the next accepted
    /// connection; duplicates and offers to a stopped listener fail closed.
    @discardableResult
    func supplyAcceptedRawSessionAuthorization(
        _ authorization: RuntimeAcceptedRawSessionAuthorization
    ) -> Bool

    /// An external stop waits for any in-flight accepted-session callback to
    /// return, and no new callback may begin after that stop returns. Calling
    /// stop synchronously from inside the callback is permitted and closes
    /// that acceptance fail-closed.
    func stop()
}

public protocol RuntimeRawFrameBodySink: Sendable {
    var connectionID: UUID { get }

    /// Completion means the full length-prefixed frame reached the transport's
    /// content-processed boundary. `close()` must reject all queued/in-flight
    /// completions and interrupt the underlying operation without waiting for
    /// a caller-held authority/publication permit.
    func sendRawFrameBody(_ body: Data)
    func sendRawFrameBody(
        _ body: Data,
        completion: @escaping @Sendable (Bool) -> Void
    )
    func sendRawFrameBodyAndWait(_ body: Data) async -> Bool
    func close()
}

public extension RuntimeRawFrameBodySink {
    func sendRawFrameBody(_ body: Data) {
        sendRawFrameBody(body) { _ in }
    }

    func sendRawFrameBodyAndWait(_ body: Data) async -> Bool {
        await withCheckedContinuation { continuation in
            sendRawFrameBody(body) { succeeded in
                continuation.resume(returning: succeeded)
            }
        }
    }
}

public typealias LocalPeerRawFrameBodyHandler = @Sendable (
    Data,
    any RuntimeRawFrameBodySink
) async -> Void

/// Immutable provenance claims attached to one accepted production raw
/// endpoint. There is deliberately no public initializer. G1a tests may mint
/// synthetic values through the DEBUG-only SPI factory; the G1b acceptor can
/// obtain a value only by consuming caller-supplied one-use authorization.
public struct RuntimeAcceptedRawRouteDescriptor: Equatable, Sendable {
    public let sessionID: String
    public let object7And26BindingDigest: String
    public let routeKind: String
    public let pairBindingDigest: String
    public let pairEpoch: UInt64
    public let generation: UInt64
    public let clientIdentityFingerprint: String
    public let runtimeIdentityFingerprint: String
    public let connectorInputCommitmentDigest: String
    public let effectiveNotBeforeMs: UInt64
    public let expiresAtMs: UInt64

    init(
        sessionID: String,
        object7And26BindingDigest: String,
        routeKind: String,
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        connectorInputCommitmentDigest: String,
        effectiveNotBeforeMs: UInt64,
        expiresAtMs: UInt64
    ) {
        self.sessionID = sessionID
        self.object7And26BindingDigest = object7And26BindingDigest
        self.routeKind = routeKind
        self.pairBindingDigest = pairBindingDigest
        self.pairEpoch = pairEpoch
        self.generation = generation
        self.clientIdentityFingerprint = clientIdentityFingerprint
        self.runtimeIdentityFingerprint = runtimeIdentityFingerprint
        self.connectorInputCommitmentDigest = connectorInputCommitmentDigest
        self.effectiveNotBeforeMs = effectiveNotBeforeMs
        self.expiresAtMs = expiresAtMs
    }

    #if DEBUG
    @_spi(ProductionRawEndpointTesting)
    public static func testing(
        sessionID: String = String(repeating: "1", count: 32),
        object7And26BindingDigest: String = String(repeating: "2", count: 64),
        routeKind: String = "p2p_direct",
        pairBindingDigest: String = String(repeating: "3", count: 64),
        pairEpoch: UInt64 = 1,
        generation: UInt64 = 1,
        clientIdentityFingerprint: String = String(repeating: "4", count: 64),
        runtimeIdentityFingerprint: String = String(repeating: "5", count: 64),
        connectorInputCommitmentDigest: String = String(repeating: "6", count: 64),
        effectiveNotBeforeMs: UInt64 = 1,
        expiresAtMs: UInt64 = 2
    ) -> Self {
        Self(
            sessionID: sessionID,
            object7And26BindingDigest: object7And26BindingDigest,
            routeKind: routeKind,
            pairBindingDigest: pairBindingDigest,
            pairEpoch: pairEpoch,
            generation: generation,
            clientIdentityFingerprint: clientIdentityFingerprint,
            runtimeIdentityFingerprint: runtimeIdentityFingerprint,
            connectorInputCommitmentDigest: connectorInputCommitmentDigest,
            effectiveNotBeforeMs: effectiveNotBeforeMs,
            expiresAtMs: expiresAtMs
        )
    }
    #endif
}

/// Opaque, one-use permission to attach caller-verified route provenance to
/// the next production raw connection.
///
/// The listener never derives this descriptor from peer-controlled bytes. The
/// G1b caller mints the authorization only after independently verifying the
/// route and transfers it to `RuntimeAcceptedRawSessionTransport`. Consuming,
/// cancelling, rejecting, or stopping the listener makes it permanently
/// unusable.
public enum RuntimeAcceptedRawSessionAuthorizationError: Error, Equatable, Sendable {
    case invalidValidityWindow
}

public final class RuntimeAcceptedRawSessionAuthorization: @unchecked Sendable {
    private let lock = NSLock()
    private var routeDescriptor: RuntimeAcceptedRawRouteDescriptor?

    private init(routeDescriptor: RuntimeAcceptedRawRouteDescriptor) {
        self.routeDescriptor = routeDescriptor
    }

    /// Production SPI for a verifier-owned caller. This is intentionally a
    /// field projection rather than a wire decoder: transport code must never
    /// obtain these claims by parsing the accepted connection.
    @_spi(ProductionRawEndpointAuthorization)
    public static func issue(
        sessionID: String,
        object7And26BindingDigest: String,
        routeKind: String,
        pairBindingDigest: String,
        pairEpoch: UInt64,
        generation: UInt64,
        clientIdentityFingerprint: String,
        runtimeIdentityFingerprint: String,
        connectorInputCommitmentDigest: String,
        effectiveNotBeforeMs: UInt64,
        expiresAtMs: UInt64
    ) throws -> RuntimeAcceptedRawSessionAuthorization {
        guard effectiveNotBeforeMs < expiresAtMs else {
            throw RuntimeAcceptedRawSessionAuthorizationError
                .invalidValidityWindow
        }
        return RuntimeAcceptedRawSessionAuthorization(
            routeDescriptor: RuntimeAcceptedRawRouteDescriptor(
                sessionID: sessionID,
                object7And26BindingDigest: object7And26BindingDigest,
                routeKind: routeKind,
                pairBindingDigest: pairBindingDigest,
                pairEpoch: pairEpoch,
                generation: generation,
                clientIdentityFingerprint: clientIdentityFingerprint,
                runtimeIdentityFingerprint: runtimeIdentityFingerprint,
                connectorInputCommitmentDigest: connectorInputCommitmentDigest,
                effectiveNotBeforeMs: effectiveNotBeforeMs,
                expiresAtMs: expiresAtMs
            )
        )
    }

    /// Cancels an authorization that has not yet been consumed. Repeated calls
    /// are harmless.
    public func close() {
        lock.lock()
        routeDescriptor = nil
        lock.unlock()
    }

    func takeRouteDescriptorForAcceptedConnection(nowMs: UInt64)
        -> RuntimeAcceptedRawRouteDescriptor?
    {
        lock.lock()
        defer { lock.unlock() }
        guard let routeDescriptor else { return nil }
        self.routeDescriptor = nil
        guard nowMs >= routeDescriptor.effectiveNotBeforeMs,
              nowMs < routeDescriptor.expiresAtMs else {
            return nil
        }
        return routeDescriptor
    }

    func remainingValidityNanoseconds(nowMs: UInt64) -> UInt64? {
        lock.lock()
        defer { lock.unlock() }
        guard let routeDescriptor,
              nowMs < routeDescriptor.expiresAtMs else {
            return nil
        }
        let remainingMs = routeDescriptor.expiresAtMs - nowMs
        let (nanoseconds, overflow) = remainingMs.multipliedReportingOverflow(
            by: 1_000_000
        )
        return overflow ? UInt64.max : nanoseconds
    }
}

/// One-shot ownership transfer from a transport acceptor to the production
/// manager/composer graph. The raw sink is never exposed through the accepted
/// session itself.
public final class RuntimeAcceptedRawEndpointClaim: @unchecked Sendable {
    public let connectionID: UUID
    public let routeDescriptor: RuntimeAcceptedRawRouteDescriptor

    private let rawSink: any RuntimeRawFrameBodySink
    private let installHandler: @Sendable (
        @escaping @Sendable (Data) async -> Void
    ) -> Bool
    private let lock = NSLock()
    private var rawSinkTransferred = false
    private var handlerInstalled = false
    private var closed = false

    init(
        rawSink: any RuntimeRawFrameBodySink,
        routeDescriptor: RuntimeAcceptedRawRouteDescriptor,
        installHandler: @escaping @Sendable (
            @escaping @Sendable (Data) async -> Void
        ) -> Bool
    ) {
        self.rawSink = rawSink
        connectionID = rawSink.connectionID
        self.routeDescriptor = routeDescriptor
        self.installHandler = installHandler
    }

    #if DEBUG
    @_spi(ProductionRawEndpointTesting)
    public static func testing(
        rawSink: any RuntimeRawFrameBodySink,
        routeDescriptor: RuntimeAcceptedRawRouteDescriptor,
        installHandler: @escaping @Sendable (
            @escaping @Sendable (Data) async -> Void
        ) -> Bool
    ) -> RuntimeAcceptedRawEndpointClaim {
        RuntimeAcceptedRawEndpointClaim(
            rawSink: rawSink,
            routeDescriptor: routeDescriptor,
            installHandler: installHandler
        )
    }
    #endif

    @_spi(ProductionRawEndpointOwnership)
    public func transferRawSinkToChannel()
        -> (any RuntimeRawFrameBodySink)?
    {
        lock.lock()
        defer { lock.unlock() }
        guard !closed, !rawSinkTransferred else { return nil }
        rawSinkTransferred = true
        return rawSink
    }

    @_spi(ProductionRawEndpointOwnership)
    @discardableResult
    public func installRawFrameBodyHandler(
        _ handler: @escaping @Sendable (Data) async -> Void
    ) -> Bool {
        lock.lock()
        guard !closed, rawSinkTransferred, !handlerInstalled else {
            lock.unlock()
            return false
        }
        handlerInstalled = true
        lock.unlock()

        guard installHandler(handler) else {
            close()
            return false
        }
        return true
    }

    @_spi(ProductionRawEndpointOwnership)
    public func close() {
        lock.lock()
        guard !closed else {
            lock.unlock()
            return
        }
        closed = true
        lock.unlock()
        rawSink.close()
    }
}

/// Per-connection raw receive ownership handed off by a transport acceptor.
///
/// This contract is deliberately transport-neutral: it grants no production
/// authority and performs no protocol decoding. The manager may take its
/// endpoint claim once; only the claimed endpoint can transfer the sink to the
/// composer and install one handler. Rejection is terminal and must never fall
/// back to an envelope/plaintext receive path. A conforming transport invokes
/// the handler serially and waits for each invocation before delivering the
/// next body.
public protocol RuntimeAcceptedRawSession: AnyObject, Sendable {
    var connectionID: UUID { get }
    var routeDescriptor: RuntimeAcceptedRawRouteDescriptor { get }

    @_spi(ProductionRawEndpointOwnership)
    @discardableResult
    func takeRawEndpointClaim() -> RuntimeAcceptedRawEndpointClaim?
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
        if let version = Self.safeDiscoveryTXTValue(version, key: "version") {
            record["version"] = version
        }
        if let app = Self.safeDiscoveryTXTValue(app, key: "app") {
            record["app"] = app
        }
        if let routeToken = Self.safeDiscoveryTXTValue(
            routeToken,
            key: "route_token",
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
        key: String,
        normalizesDisplayWhitespace: Bool = true,
        rejectsWhitespace: Bool = false
    ) -> String? {
        guard let rawValue else {
            return nil
        }
        let value = normalizesDisplayWhitespace
            ? rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
            : rawValue
        guard !value.isEmpty,
              key.utf8.count + 1 + value.utf8.count <= 255
        else {
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
