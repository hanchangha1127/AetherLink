import struct BridgeProtocol.ProtocolEnvelope
import CompanionCore
import Darwin
import Dispatch
import Foundation
import class LMStudioBackend.LMStudioBackend
import enum OllamaBackend.BackendStatus
import struct OllamaBackend.ChatRequest
import enum OllamaBackend.ChatStreamEvent
import enum OllamaBackend.GenerationCancellationResult
import protocol OllamaBackend.LlmBackend
import struct OllamaBackend.ModelInfo
import enum OllamaBackend.ModelProvider
import struct OllamaBackend.ModelPullResult
import struct OllamaBackend.ModelUnloadResult
import class OllamaBackend.OllamaBackend
import enum OllamaBackend.OllamaBackendError
import Pairing
import Transport
import TrustedDevices

@main
struct RuntimeDevServer {
    static func main() {
        setbuf(stdout, nil)
        setbuf(stderr, nil)

        let environment = ProcessInfo.processInfo.environment
        let port = UInt16(environment["LOCAL_AGENT_BRIDGE_PORT"] ?? "") ?? 43170
        let useMockBackend = environment["LOCAL_AGENT_BRIDGE_MOCK_BACKEND"] == "1"
        let useAggregateMockBackend = useMockBackend
            && environment["AETHERLINK_DEV_MOCK_AGGREGATE_RESIDENCY"] == "1"
        let backend: any LlmBackend = useMockBackend
            ? Self.developmentMockBackend(environment: environment, aggregateResidency: useAggregateMockBackend)
            : AggregatingLlmBackend(ollama: OllamaBackend(), lmStudio: LMStudioBackend())
        let pairingCoordinator = PairingCoordinator()
        let trustedDeviceStore = Self.trustedDeviceStore(environment: environment)
        let runtimeChatEventStore = Self.runtimeChatEventStore(environment: environment)
        let identity = Self.runtimeIdentity(environment: environment)
        let server = LocalPeerServer()
        let advertiser = BonjourAdvertiser()
        let shouldAdvertiseBonjour = environment["AETHERLINK_DEV_DISABLE_BONJOUR"] != "1"
        let relayRouteRequested = Self.relayRouteRequested(environment: environment)
        let relayRouteAllocation = Self.relayRouteAllocation(environment: environment, identity: identity)
        let relayConfiguration = relayRouteAllocation?.configuration
        let devPairingDirectHost = Self.developmentPairingDirectHost(
            environment: environment,
            relayConfigured: relayConfiguration != nil,
            relayRouteRequested: relayRouteRequested
        )
        let relayClient = (relayConfiguration == nil && !relayRouteRequested) ? nil : RelayPeerClient()
        let relayPairingReadiness = RelayPairingReadiness()
        let routerBox = RuntimeRouterBox()
        let relayMessageHandler: LocalPeerMessageHandler = { envelope, sink in
            print("[runtime] relay received type=\(envelope.type) request_id=\(envelope.requestID)")
            routerBox.handle(envelope, sink: LoggingSink(wrapped: sink))
        }
        let relayStatusHandler: @Sendable (RelayPeerStatus) -> Void = { status in
            relayPairingReadiness.update(status)
            print("[runtime] relay status=\(status.logLabel)")
        }
        let routeRefresher = DevelopmentRuntimeRouteRefresher(
            runtimeDeviceID: identity.deviceID,
            runtimeKeyFingerprint: identity.fingerprint,
            initialAllocation: relayRouteAllocation,
            allocationProvider: {
                Self.relayRouteAllocation(environment: environment, identity: identity)
            },
            p2pRouteProvider: {
                Self.developmentP2PRouteMaterial(environment: environment)
            },
            relayStatusHandler: relayStatusHandler,
            relayMessageHandler: relayMessageHandler,
            relayDisconnectHandler: { connectionID in
                routerBox.connectionDidClose(connectionID)
            },
            relayScopeProvider: { host in Self.relayScope(for: host) }
        )
        let router = LocalRuntimeMessageRouter(
            backend: backend,
            pairingCoordinator: pairingCoordinator,
            trustedDeviceStore: trustedDeviceStore,
            chatEventStore: runtimeChatEventStore,
            routeRefresher: routeRefresher,
            runtimeChallengeSigner: identity.signer,
            onPairingAccepted: { device in
                print("[runtime] Development pairing accepted for device_id=\(device.id) name=\"\(device.name)\"")
            }
        )
        routerBox.set(router)
        server.onDisconnect = { connectionID in
            routerBox.connectionDidClose(connectionID)
        }
        relayClient?.onDisconnect = { connectionID in
            routerBox.connectionDidClose(connectionID)
        }
        RuntimeDevServerState.server = server
        RuntimeDevServerState.advertiser = advertiser
        RuntimeDevServerState.relayClient = relayClient

        server.start(port: port) { envelope, sink in
            print("[runtime] received type=\(envelope.type) request_id=\(envelope.requestID)")
            routerBox.handle(envelope, sink: LoggingSink(wrapped: sink))
        }
        if shouldAdvertiseBonjour {
            advertiser.start(port: Int32(port), metadata: identity.advertisementMetadata)
        }
        if let relayConfiguration, let relayClient {
            relayClient.start(
                configuration: relayConfiguration,
                onStatusChange: relayStatusHandler,
                onMessage: relayMessageHandler
            )
        }

        print("[runtime] AetherLink dev server listening on 127.0.0.1:\(port)")
        print("[runtime] Backend: \(useMockBackend ? (useAggregateMockBackend ? "dev aggregate mock" : "dev mock") : "Ollama + LM Studio")")
        if shouldAdvertiseBonjour {
            print("[runtime] Advertising _aetherlink._tcp.local. on port \(port)")
        } else {
            print("[runtime] Bonjour advertising disabled for this development run.")
        }
        if let relayConfiguration {
            let relayScope = Self.relayScope(for: relayConfiguration.host) ?? "unknown"
            print("[runtime] Relay route enabled: \(relayConfiguration.host):\(relayConfiguration.port) scope=\(relayScope)")
        }
        printDevelopmentConnectionHint(
            port: port,
            relayConfiguration: relayConfiguration,
            directHost: devPairingDirectHost
        )

        if environment["AETHERLINK_DEV_PAIRING"] == "1" {
            if relayRouteRequested && relayConfiguration == nil && devPairingDirectHost == nil {
                print("[runtime] Development pairing QR not emitted: relay route allocation failed and no explicit direct pairing host was set.")
                print("[runtime] Fix the allocation relay or set AETHERLINK_DEV_PAIRING_HOST only for local diagnostics.")
            } else if waitForDevelopmentRelayPairingReadinessIfNeeded(
                relayConfiguration: relayConfiguration,
                relayPairingReadiness: relayPairingReadiness,
                environment: environment
            ) {
                startDevelopmentPairing(
                    coordinator: pairingCoordinator,
                    port: port,
                    identity: identity,
                    environment: environment,
                    relayConfiguration: relayConfiguration,
                    serviceRelayRouteLease: relayRouteAllocation?.lease,
                    directHost: devPairingDirectHost
                )
            }
        }

        dispatchMain()
    }

    private static func trustedDeviceStore(environment: [String: String]) -> TrustedDeviceStore {
        guard let path = environment["AETHERLINK_DEV_TRUSTED_DEVICES_FILE"], !path.isEmpty else {
            return TrustedDeviceStore()
        }
        return TrustedDeviceStore(fileURL: URL(fileURLWithPath: path))
    }

    private static func runtimeChatEventStore(environment: [String: String]) -> any RuntimeChatEventStore {
        guard let sqlitePath = environment["AETHERLINK_DEV_RUNTIME_CHAT_SQLITE_FILE"]?.takeIfNotEmpty else {
            return RuntimeChatEventStoreDefaults.productionStore()
        }
        let legacyJSONLFileURL = environment["AETHERLINK_DEV_RUNTIME_CHAT_JSONL_FILE"]?.takeIfNotEmpty
            .map { URL(fileURLWithPath: $0) }
        return SQLiteRuntimeChatEventStore(
            databaseURL: URL(fileURLWithPath: sqlitePath),
            legacyJSONLFileURL: legacyJSONLFileURL
        )
    }

    private static func developmentMockBackend(
        environment: [String: String],
        aggregateResidency: Bool
    ) -> any LlmBackend {
        guard aggregateResidency else {
            return DevMockBackend(environment: environment)
        }
        let idleDelayMilliseconds = UInt64(environment["AETHERLINK_DEV_MOCK_RESIDENCY_IDLE_MS"] ?? "") ?? 600_000
        return AggregatingLlmBackend(
            [
                DevMockBackend(
                    provider: .ollama,
                    modelID: "dev-mock",
                    modelName: "Dev Mock Streaming Model",
                    environment: environment
                ),
                DevMockBackend(
                    provider: .lmStudio,
                    modelID: "dev-mock-alt",
                    modelName: "Dev Mock Alternate Model",
                    environment: environment
                )
            ],
            modelIdleUnloadDelayNanoseconds: idleDelayMilliseconds * 1_000_000
        )
    }

    private static func printDevelopmentConnectionHint(
        port: UInt16,
        relayConfiguration: RelayPeerConfiguration?,
        directHost: String?
    ) {
        if relayConfiguration != nil && directHost == nil {
            print("[runtime] Relay QR route is active. Scan the emitted aetherlink://pair QR/URI in AetherLink.")
            print("[runtime] No USB port forwarding, fixed network address, or model-provider address is required for this route.")
            return
        }

        if relayConfiguration != nil {
            print("[runtime] Relay route is active with an explicit direct diagnostic fallback.")
        }
        print("[runtime] For local direct diagnostics with a USB-connected trusted device, run:")
        print("[runtime]   adb reverse tcp:\(port) tcp:\(port)")
        print("[runtime] Then use the local diagnostic route 127.0.0.1:\(port) in AetherLink.")
    }

    private static func relayRouteAllocation(
        environment: [String: String],
        identity: DevRuntimeIdentity
    ) -> CompanionRemoteRelayRouteAllocation? {
        if let host = environment["AETHERLINK_RELAY_HOST"]?.takeIfNotEmpty {
            let port = UInt16(environment["AETHERLINK_RELAY_PORT"] ?? "") ?? 43171
            let explicitRelayID = environment["AETHERLINK_RELAY_ID"]?.takeIfNotEmpty
            let explicitRelaySecret = environment["AETHERLINK_RELAY_SECRET"]?.takeIfNotEmpty
            if explicitRelayID != nil || explicitRelaySecret != nil {
                guard let explicitRelayID, let explicitRelaySecret else {
                    print("[runtime] relay configuration failed: AETHERLINK_RELAY_ID and AETHERLINK_RELAY_SECRET must be set together.")
                    return nil
                }
                let lease = Self.newRelayRouteLease()
                return CompanionRemoteRelayRouteAllocation(
                    configuration: RelayPeerConfiguration(
                        host: host,
                        port: port,
                        relayID: explicitRelayID,
                        relaySecret: explicitRelaySecret,
                        relayNonce: lease.nonce
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: lease.expiresAtEpochMillis,
                        nonce: lease.nonce
                    )
                )
            }
            do {
                return try TCPRelayServiceRouteAllocator().allocateRelayRoute(
                    host: host,
                    port: port,
                    routeToken: identity.routeToken,
                    relaySecret: Self.preferredDevelopmentRelaySecret(environment: environment),
                    allocationToken: environment["AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty
                        ?? environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty,
                    timeout: 5
                )
            } catch {
                print("[runtime] relay allocation failed: \(error.localizedDescription)")
                return nil
            }
        }
        guard Self.bootstrapRelayRequested(environment: environment) else {
            return nil
        }
        do {
            return try EnvironmentRemoteRelayRouteAllocator(environment: environment)
                .allocateRemoteRelayRoute(
                    runtimeDeviceID: identity.deviceID,
                    routeToken: identity.routeToken,
                    preferredRelaySecret: Self.preferredDevelopmentRelaySecret(environment: environment)
                )
        } catch {
            print("[runtime] relay allocation failed: \(error.localizedDescription)")
            return nil
        }
    }

    private static func bootstrapRelayRequested(environment: [String: String]) -> Bool {
        environment["AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS"]?.takeIfNotEmpty != nil
            || environment["AETHERLINK_BOOTSTRAP_RELAY_HOST"]?.takeIfNotEmpty != nil
    }

    private static func relayRouteRequested(environment: [String: String]) -> Bool {
        environment["AETHERLINK_RELAY_HOST"]?.takeIfNotEmpty != nil
            || bootstrapRelayRequested(environment: environment)
    }

    private static func startDevelopmentPairing(
        coordinator: PairingCoordinator,
        port: UInt16,
        identity: DevRuntimeIdentity,
        environment: [String: String],
        relayConfiguration: RelayPeerConfiguration?,
        serviceRelayRouteLease: CompanionRemoteRouteLease?,
        directHost: String?
    ) {
        let relayRouteLease = relayConfiguration == nil
            ? nil
            : serviceRelayRouteLease.map {
                (expiresAtEpochMillis: $0.expiresAtEpochMillis, nonce: $0.nonce)
            } ?? relayConfiguration?.relayNonce.map { nonce in
                let lease = Self.newRelayRouteLease()
                return (expiresAtEpochMillis: lease.expiresAtEpochMillis, nonce: nonce)
            }
        let session = coordinator.beginPairing(
            validFor: TimeInterval(environment["AETHERLINK_DEV_PAIRING_TTL_SECONDS"] ?? "") ?? 300,
            macDeviceID: identity.deviceID,
            macName: identity.name,
            fingerprint: identity.fingerprint,
            runtimePublicKeyBase64: identity.publicKeyBase64.isEmpty ? nil : identity.publicKeyBase64,
            routeToken: identity.routeToken,
            host: directHost,
            port: directHost == nil ? nil : Int(port),
            relayHost: relayConfiguration?.host,
            relayPort: relayConfiguration.map { Int($0.port) },
            relayID: relayConfiguration?.relayID,
            relaySecret: relayConfiguration?.relaySecret,
            relayExpiresAtEpochMillis: relayRouteLease?.expiresAtEpochMillis,
            relayNonce: relayRouteLease?.nonce,
            relayScope: relayConfiguration.flatMap { relayScope(for: $0.host) },
            p2pRouteClass: nil,
            p2pRecordID: nil,
            p2pEncryptedBody: nil,
            p2pExpiresAtEpochMillis: nil,
            p2pAntiReplayNonce: nil,
            p2pProtocolVersion: nil
        )

        print("[runtime] WARNING: AETHERLINK_DEV_PAIRING=1 opened a development-only pairing window.")
        print("[runtime] Do not enable this mode for production or normal trusted-device use.")
        printDevelopmentPairingInfo(session)
    }

    private static func waitForDevelopmentRelayPairingReadinessIfNeeded(
        relayConfiguration: RelayPeerConfiguration?,
        relayPairingReadiness: RelayPairingReadiness,
        environment: [String: String]
    ) -> Bool {
        guard let relayConfiguration else {
            return true
        }

        let timeout = TimeInterval(environment["AETHERLINK_DEV_RELAY_PAIRING_READY_TIMEOUT_SECONDS"] ?? "") ?? 10
        print("[runtime] Waiting for relay route \(relayConfiguration.host):\(relayConfiguration.port) before emitting development pairing QR.")
        if relayPairingReadiness.waitUntilReadyForPairing(timeout: timeout) {
            return true
        }

        let status = relayPairingReadiness.currentStatus
        print("[runtime] Development pairing QR not emitted: relay route \(relayConfiguration.host):\(relayConfiguration.port) is not ready after \(timeout)s (status=\(status.logLabel)).")
        print("[runtime] Start the relay, fix public/VPN/tunnel reachability, or unset relay environment variables for direct local diagnostics.")
        return false
    }

    private static func developmentPairingDirectHost(
        environment: [String: String],
        relayConfigured: Bool,
        relayRouteRequested: Bool
    ) -> String? {
        if let explicitHost = environment["AETHERLINK_DEV_PAIRING_HOST"]?.takeIfNotEmpty {
            return explicitHost
        }
        return (relayConfigured || relayRouteRequested) ? nil : defaultRuntimeRouteHost()
    }

    private static func printDevelopmentPairingInfo(_ session: PairingSession) {
        var info: [String: Any] = [
            "pairing_code": session.code,
            "pairing_nonce": session.nonce,
            "runtime_device_id": session.macDeviceID,
            "runtime_name": session.macName,
            "runtime_key_fingerprint": session.fingerprint,
            "service_type": session.serviceType,
            "expires_at": ISO8601DateFormatter().string(from: session.expiresAt)
        ]
        if let runtimePublicKey = session.runtimePublicKeyBase64 {
            info["runtime_public_key"] = runtimePublicKey
            info["runtime_key_fingerprint"] = session.fingerprint
        }
        if let routeToken = session.routeToken {
            info["route_token"] = routeToken
        }
        if let host = session.host {
            info["host"] = host
        }
        if let port = session.port {
            info["port"] = port
        }
        if let relayHost = session.relayHost {
            info["relay_host"] = relayHost
        }
        if let relayPort = session.relayPort {
            info["relay_port"] = relayPort
        }
        if let relayID = session.relayID {
            info["relay_id"] = relayID
        }
        if let relaySecret = session.relaySecret {
            info["relay_secret"] = relaySecret
        }
        if let relayExpiresAtEpochMillis = session.relayExpiresAtEpochMillis {
            info["relay_expires_at"] = relayExpiresAtEpochMillis
        }
        if let relayNonce = session.relayNonce {
            info["relay_nonce"] = relayNonce
        }
        if let relayScope = session.relayScope {
            info["relay_scope"] = relayScope
        }

        guard let data = try? JSONSerialization.data(withJSONObject: info, options: [.sortedKeys]),
              let json = String(data: data, encoding: .utf8)
        else {
            print("[runtime] Failed to serialize development pairing info.")
            return
        }
        print("[runtime] AETHERLINK_DEV_PAIRING_INFO \(json)")
        print("[runtime] AETHERLINK_DEV_PAIRING_URI \(session.qrPayload)")
        print("[runtime] AETHERLINK_DEV_PAIRING_COMPACT_URI \(session.compactQRCodePayload)")
    }

    private static func runtimeIdentity(environment: [String: String]) -> DevRuntimeIdentity {
        let deviceID = environment["AETHERLINK_DEV_RUNTIME_DEVICE_ID"]
            ?? environment["AETHERLINK_DEV_MAC_DEVICE_ID"]
            ?? "aetherlink-dev-runtime"
        let identityKey = loadDevelopmentRuntimeIdentityKey(
            deviceID: deviceID,
            environment: environment
        )
        return DevRuntimeIdentity(
            deviceID: deviceID,
            name: environment["AETHERLINK_DEV_RUNTIME_NAME"] ?? environment["AETHERLINK_DEV_MAC_NAME"] ?? "AetherLink Dev Runtime",
            publicKeyBase64: identityKey.key.publicKeyBase64,
            fingerprint: environment["AETHERLINK_DEV_RUNTIME_FINGERPRINT"] ?? environment["AETHERLINK_DEV_MAC_FINGERPRINT"] ?? identityKey.key.fingerprint,
            routeToken: environment["AETHERLINK_DEV_ROUTE_TOKEN"] ?? "dev-aetherlink-route",
            signer: identityKey.signer
        )
    }

    private static func newRelayRouteLease(
        validFor seconds: TimeInterval = 15 * 60
    ) -> (expiresAtEpochMillis: Int64, nonce: String) {
        let expiresAt = Date().addingTimeInterval(seconds)
        return (
            expiresAtEpochMillis: Int64((expiresAt.timeIntervalSince1970 * 1000).rounded()),
            nonce: UUID().uuidString
        )
    }

    private static func developmentP2PRouteMaterial(environment: [String: String]) -> DevelopmentP2PRouteMaterial? {
        guard environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P"] == "1" else {
            return nil
        }
        let expiresAt = Date().addingTimeInterval(15 * 60)
        return DevelopmentP2PRouteMaterial(
            routeClass: environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_CLASS"]?.takeIfNotEmpty ?? "p2p_rendezvous",
            recordID: environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_RECORD_ID"]?.takeIfNotEmpty ?? "smoke-p2p-record-1",
            encryptedBody: environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_ENCRYPTED_BODY"]?.takeIfNotEmpty ?? "smoke-p2p-encrypted-body-1",
            expiresAtEpochMillis: Int64((expiresAt.timeIntervalSince1970 * 1000).rounded()),
            antiReplayNonce: environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_NONCE"]?.takeIfNotEmpty ?? "smoke-p2p-nonce-1",
            protocolVersion: Int(environment["AETHERLINK_DEV_ROUTE_REFRESH_P2P_PROTOCOL_VERSION"] ?? "") ?? 1
        )
    }

    private static func generateRelaySecret() -> String {
        let bytes = (0..<32).map { _ in UInt8.random(in: 0...255) }
        return Data(bytes).base64EncodedString()
    }

    private static func defaultRuntimeRouteHost() -> String? {
        var interfaces: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&interfaces) == 0, let firstInterface = interfaces else {
            return nil
        }
        defer { freeifaddrs(interfaces) }

        var candidates: [(name: String, address: String, score: Int)] = []
        var cursor: UnsafeMutablePointer<ifaddrs>? = firstInterface
        while let interface = cursor {
            defer { cursor = interface.pointee.ifa_next }
            let flags = Int32(interface.pointee.ifa_flags)
            guard (flags & IFF_UP) != 0, (flags & IFF_LOOPBACK) == 0 else { continue }
            guard let address = interface.pointee.ifa_addr, address.pointee.sa_family == UInt8(AF_INET) else { continue }

            let interfaceName = String(cString: interface.pointee.ifa_name)
            guard let score = pairingInterfaceScore(name: interfaceName) else { continue }

            var hostBuffer = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            let result = getnameinfo(
                address,
                socklen_t(address.pointee.sa_len),
                &hostBuffer,
                socklen_t(hostBuffer.count),
                nil,
                0,
                NI_NUMERICHOST
            )
            guard result == 0 else { continue }
            let addressString = String(cString: hostBuffer)
            guard isUsablePairingAddress(addressString) else { continue }
            candidates.append((interfaceName, addressString, score))
        }

        return candidates
            .sorted { lhs, rhs in
                if lhs.score != rhs.score {
                    return lhs.score < rhs.score
                }
                return lhs.name.localizedStandardCompare(rhs.name) == .orderedAscending
            }
            .first?
            .address
    }

    private static func pairingInterfaceScore(name: String) -> Int? {
        let virtualPrefixes = [
            "bridge",
            "utun",
            "awdl",
            "llw",
            "lo",
            "gif",
            "stf",
            "p2p",
            "ap"
        ]
        if virtualPrefixes.contains(where: { name.hasPrefix($0) }) {
            return nil
        }
        if name.hasPrefix("en") {
            return 0
        }
        return 10
    }

    private static func isUsablePairingAddress(_ address: String) -> Bool {
        guard !address.isEmpty else { return false }
        if address == "0.0.0.0" || address == "255.255.255.255" { return false }
        if address.hasPrefix("127.") || address.hasPrefix("169.254.") { return false }
        return true
    }

    private static func preferredDevelopmentRelaySecret(environment: [String: String]) -> String {
        environment["AETHERLINK_DEV_RELAY_SECRET"]?.takeIfNotEmpty
            ?? environment["AETHERLINK_BOOTSTRAP_RELAY_FRAME_SECRET"]?.takeIfNotEmpty
            ?? loadOrCreateSavedDevelopmentRelaySecret()
    }

    private static func relayScope(for host: String) -> String? {
        let normalized = host
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
            .lowercased()
        if normalized == "localhost" ||
            normalized == "::1" ||
            normalized == "0:0:0:0:0:0:0:1" ||
            normalized.hasPrefix("127.") {
            return "usb_reverse"
        }
        if normalized.isPrivateOverlayRelayLiteral() {
            return "private_overlay"
        }
        return nil
    }

    private static func loadOrCreateSavedDevelopmentRelaySecret(
        defaults: UserDefaults = .standard
    ) -> String {
        let key = "aetherlink.dev_relay.secret"
        if let existing = defaults.string(forKey: key)?.takeIfNotEmpty {
            return existing
        }
        let secret = generateRelaySecret()
        defaults.set(secret, forKey: key)
        return secret
    }

    private static func loadDevelopmentRuntimeIdentityKey(
        deviceID: String,
        environment: [String: String]
    ) -> (key: RuntimeIdentityKey, signer: (any RuntimeChallengeSigning)?) {
        if let filePath = environment["AETHERLINK_DEV_RUNTIME_IDENTITY_FILE"], !filePath.isEmpty {
            let store = FileRuntimeIdentityKeyStore(fileURL: URL(fileURLWithPath: filePath))
            do {
                return (try store.loadOrCreate(), store)
            } catch {
                print("[runtime] runtime identity file failed: \(error.localizedDescription)")
                return (
                    RuntimeIdentityKey(publicKeyBase64: "", fingerprint: "dev-\(deviceID)"),
                    nil
                )
            }
        }
        if let publicKey = environment["AETHERLINK_DEV_RUNTIME_PUBLIC_KEY"], !publicKey.isEmpty {
            return (
                RuntimeIdentityKey(
                    publicKeyBase64: publicKey,
                    fingerprint: environment["AETHERLINK_DEV_RUNTIME_KEY_FINGERPRINT"] ?? "dev-\(deviceID)"
                ),
                nil
            )
        }
        let store = RuntimeIdentityKeyStore(
            service: environment["AETHERLINK_DEV_RUNTIME_KEYCHAIN_SERVICE"] ?? "dev.aetherlink.runtime-dev-server",
            account: environment["AETHERLINK_DEV_RUNTIME_KEYCHAIN_ACCOUNT"] ?? deviceID
        )
        do {
            return (try store.loadOrCreate(), store)
        } catch {
            let fileStore = FileRuntimeIdentityKeyStore()
            do {
                print("[runtime] runtime identity Keychain unavailable; using persisted file identity fallback.")
                return (try fileStore.loadOrCreate(), fileStore)
            } catch {
                print("[runtime] runtime identity stores unavailable; using temporary fingerprint fallback.")
                return (RuntimeIdentityKey(publicKeyBase64: "", fingerprint: "dev-\(deviceID)"), nil)
            }
        }
    }
}

private struct DevRuntimeIdentity {
    var deviceID: String
    var name: String
    var publicKeyBase64: String
    var fingerprint: String
    var routeToken: String
    var signer: (any RuntimeChallengeSigning)?

    var advertisementMetadata: RuntimeAdvertisementMetadata {
        RuntimeAdvertisementMetadata(
            routeToken: routeToken,
            deviceID: deviceID,
            fingerprint: fingerprint
        )
    }
}

private struct DevelopmentP2PRouteMaterial {
    var routeClass: String
    var recordID: String
    var encryptedBody: String
    var expiresAtEpochMillis: Int64
    var antiReplayNonce: String
    var protocolVersion: Int
}

private enum RuntimeDevServerState {
    static var server: LocalPeerServer?
    static var advertiser: BonjourAdvertiser?
    static var relayClient: RelayPeerClient?
}

private final class RuntimeRouterBox: @unchecked Sendable {
    private let lock = NSLock()
    private var router: LocalRuntimeMessageRouter?

    func set(_ router: LocalRuntimeMessageRouter) {
        lock.withLock {
            self.router = router
        }
    }

    func handle(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        let current = lock.withLock { router }
        current?.handle(envelope, sink: sink)
    }

    func connectionDidClose(_ connectionID: UUID) {
        let current = lock.withLock { router }
        current?.connectionDidClose(connectionID)
    }
}

@MainActor
private final class DevelopmentRuntimeRouteRefresher: RuntimeRouteRefreshing {
    private let runtimeDeviceID: String
    private let runtimeKeyFingerprint: String
    private let allocationProvider: () -> CompanionRemoteRelayRouteAllocation?
    private let p2pRouteProvider: () -> DevelopmentP2PRouteMaterial?
    private let relayStatusHandler: @Sendable (RelayPeerStatus) -> Void
    private let relayMessageHandler: LocalPeerMessageHandler
    private let relayDisconnectHandler: @Sendable (UUID) -> Void
    private let relayScopeProvider: (String) -> String?
    private var activeAllocation: CompanionRemoteRelayRouteAllocation?
    private var refreshedRelayClients: [ObjectIdentifier: RelayPeerClient] = [:]

    init(
        runtimeDeviceID: String,
        runtimeKeyFingerprint: String,
        initialAllocation: CompanionRemoteRelayRouteAllocation?,
        allocationProvider: @escaping () -> CompanionRemoteRelayRouteAllocation?,
        p2pRouteProvider: @escaping () -> DevelopmentP2PRouteMaterial?,
        relayStatusHandler: @escaping @Sendable (RelayPeerStatus) -> Void,
        relayMessageHandler: @escaping LocalPeerMessageHandler,
        relayDisconnectHandler: @escaping @Sendable (UUID) -> Void,
        relayScopeProvider: @escaping (String) -> String?
    ) {
        self.runtimeDeviceID = runtimeDeviceID
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.activeAllocation = initialAllocation
        self.allocationProvider = allocationProvider
        self.p2pRouteProvider = p2pRouteProvider
        self.relayStatusHandler = relayStatusHandler
        self.relayMessageHandler = relayMessageHandler
        self.relayDisconnectHandler = relayDisconnectHandler
        self.relayScopeProvider = relayScopeProvider
    }

    func refreshRuntimeRoute() async throws -> RuntimeRouteRefreshResult? {
        if let activeAllocation,
           !Self.shouldRenew(lease: activeAllocation.lease),
           let result = routeRefreshResult(for: activeAllocation) {
            return result
        }
        guard let allocation = allocationProvider() else {
            return nil
        }
        guard let result = routeRefreshResult(for: allocation) else {
            return nil
        }
        activeAllocation = allocation
        let configuration = allocation.configuration
        let refreshedRelayClient = RelayPeerClient()
        let clientID = ObjectIdentifier(refreshedRelayClient)
        refreshedRelayClients[clientID] = refreshedRelayClient
        refreshedRelayClient.onDisconnect = { [weak self] connectionID in
            self?.relayDisconnectHandler(connectionID)
            Task { @MainActor [weak self] in
                self?.refreshedRelayClients.removeValue(forKey: clientID)
            }
        }
        refreshedRelayClient.start(
            configuration: configuration,
            onStatusChange: relayStatusHandler,
            onMessage: relayMessageHandler
        )
        return result
    }

    private func routeRefreshResult(for allocation: CompanionRemoteRelayRouteAllocation) -> RuntimeRouteRefreshResult? {
        let configuration = allocation.configuration
        guard let relaySecret = configuration.relaySecret?.takeIfNotEmpty,
              let lease = allocation.lease
        else {
            return nil
        }
        let p2pRoute = p2pRouteProvider()
        return RuntimeRouteRefreshResult(
            runtimeDeviceID: runtimeDeviceID,
            runtimeKeyFingerprint: runtimeKeyFingerprint,
            relayHost: configuration.host,
            relayPort: Int(configuration.port),
            relayID: configuration.relayID,
            relaySecret: relaySecret,
            relayExpiresAtEpochMillis: lease.expiresAtEpochMillis,
            relayNonce: lease.nonce,
            relayScope: relayScopeProvider(configuration.host),
            p2pRouteClass: p2pRoute?.routeClass,
            p2pRecordID: p2pRoute?.recordID,
            p2pEncryptedBody: p2pRoute?.encryptedBody,
            p2pExpiresAtEpochMillis: p2pRoute?.expiresAtEpochMillis,
            p2pAntiReplayNonce: p2pRoute?.antiReplayNonce,
            p2pProtocolVersion: p2pRoute?.protocolVersion
        )
    }

    private static func shouldRenew(lease: CompanionRemoteRouteLease?) -> Bool {
        guard let lease else {
            return true
        }
        return lease.isExpired(renewalMarginSeconds: 60)
    }
}

private final class RelayPairingReadiness: @unchecked Sendable {
    private let condition = NSCondition()
    private var status: RelayPeerStatus = .stopped

    var currentStatus: RelayPeerStatus {
        condition.lock()
        defer { condition.unlock() }
        return status
    }

    func update(_ newStatus: RelayPeerStatus) {
        condition.lock()
        status = newStatus
        condition.broadcast()
        condition.unlock()
    }

    func waitUntilReadyForPairing(timeout: TimeInterval) -> Bool {
        let deadline = Date().addingTimeInterval(max(0, timeout))
        condition.lock()
        defer { condition.unlock() }

        while !status.isReadyForPairing {
            if !condition.wait(until: deadline) {
                break
            }
        }
        return status.isReadyForPairing
    }
}

private extension String {
    var takeIfNotEmpty: String? {
        isEmpty ? nil : self
    }

    func isPrivateOverlayRelayLiteral() -> Bool {
        isPrivateOverlayIPv4Literal() || isPrivateOverlayIPv6Literal()
    }

    private func isPrivateOverlayIPv4Literal() -> Bool {
        let octets = split(separator: ".", omittingEmptySubsequences: false)
        guard octets.count == 4 else { return false }
        let values: [Int] = octets.compactMap { part in
            guard !part.isEmpty,
                  part.allSatisfy(\.isNumber),
                  let value = Int(part),
                  (0...255).contains(value)
            else {
                return nil
            }
            return value
        }
        guard values.count == 4 else { return false }
        let first = values[0]
        let second = values[1]
        return first == 10 ||
            (first == 100 && (64...127).contains(second)) ||
            (first == 172 && (16...31).contains(second)) ||
            (first == 192 && second == 168)
    }

    private func isPrivateOverlayIPv6Literal() -> Bool {
        guard contains(":") else { return false }
        return hasPrefix("fc") || hasPrefix("fd")
    }
}

private extension RelayPeerStatus {
    var isReadyForPairing: Bool {
        switch self {
        case .waitingForPeer, .ready:
            return true
        case .stopped, .connecting, .reconnecting, .failed:
            return false
        }
    }

    var logLabel: String {
        switch self {
        case .stopped:
            return "stopped"
        case .connecting:
            return "connecting"
        case .waitingForPeer:
            return "waiting_for_peer"
        case .ready:
            return "ready"
        case .reconnecting(let message):
            return message.map { "reconnecting: \($0)" } ?? "reconnecting"
        case .failed(let message):
            return "failed: \(message)"
        }
    }
}

private final class DevMockBackend: LlmBackend, @unchecked Sendable {
    let provider: ModelProvider
    private let modelID: String
    private let modelName: String
    private let chunkDelayNanoseconds: UInt64
    private let unloadEventFile: String?
    private let lock = NSLock()
    private var tasks: [String: Task<Void, Never>] = [:]
    private var pulledModels: [String] = []

    init(
        provider: ModelProvider = .ollama,
        modelID: String = "dev-mock",
        modelName: String = "Dev Mock Streaming Model",
        environment: [String: String] = ProcessInfo.processInfo.environment
    ) {
        self.provider = provider
        self.modelID = modelID
        self.modelName = modelName
        let delayMilliseconds = UInt64(environment["AETHERLINK_DEV_MOCK_CHUNK_DELAY_MS"] ?? "") ?? 350
        chunkDelayNanoseconds = max(1, delayMilliseconds) * 1_000_000
        unloadEventFile = environment["AETHERLINK_DEV_MOCK_UNLOAD_EVENT_FILE"]?.takeIfNotEmpty
    }

    func healthCheck() async -> BackendStatus {
        .available
    }

    func listModels() async throws -> [ModelInfo] {
        lock.withLock {
            var models = [
                ModelInfo(
                    id: modelID,
                    name: modelName,
                    provider: provider,
                    sizeBytes: 0,
                    modifiedAt: Date(),
                    installed: true,
                    running: false,
                    source: .local
                )
            ]
            models.append(contentsOf: pulledModels.map {
                ModelInfo(
                    id: $0,
                    name: $0,
                    provider: provider,
                    sizeBytes: 0,
                    modifiedAt: Date(),
                    installed: true,
                    running: false,
                    source: .local
                )
            })
            return models
        }
    }

    func pullModel(name: String) async throws -> ModelPullResult {
        lock.withLock {
            if !pulledModels.contains(name) {
                pulledModels.append(name)
            }
        }
        return ModelPullResult(model: name, status: "success", installed: true)
    }

    func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        if let unloadEventFile {
            let line = "\(provider.rawValue)|\(providerModelID)\n"
            if let data = line.data(using: .utf8) {
                let url = URL(fileURLWithPath: unloadEventFile)
                if FileManager.default.fileExists(atPath: unloadEventFile),
                   let handle = try? FileHandle(forWritingTo: url) {
                    try handle.seekToEnd()
                    try handle.write(contentsOf: data)
                    try handle.close()
                } else {
                    try data.write(to: url, options: .atomic)
                }
            }
        }
        return .unloaded(provider: provider, modelID: providerModelID)
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task { [weak self] in
                let hasAttachmentContext = request.messages.contains { message in
                    !message.attachments.isEmpty
                        || message.content.contains("[Attached document:")
                }
                let chunks = hasAttachmentContext
                    ? ["Mock ", "streaming ", "response.", " Attachment ", "received."]
                    : ["Mock ", "streaming ", "response."]
                for chunk in chunks {
                    if Task.isCancelled {
                        continuation.finish(throwing: OllamaBackendError.generationCancelled(generationID: request.generationID))
                        self?.remove(request.generationID)
                        return
                    }
                    continuation.yield(.delta(chunk))
                    try? await Task.sleep(nanoseconds: self?.chunkDelayNanoseconds ?? 350_000_000)
                }
                continuation.yield(.done(inputTokens: 1, outputTokens: chunks.count))
                continuation.finish()
                self?.remove(request.generationID)
            }
            register(request.generationID, task: task)
            continuation.onTermination = { [weak self] termination in
                if case .cancelled = termination {
                    _ = self?.cancel(generationID: request.generationID)
                }
            }
        }
    }

    func cancel(generationID: String) -> GenerationCancellationResult {
        lock.withLock {
            guard let task = tasks.removeValue(forKey: generationID) else {
                return .notFound(generationID: generationID)
            }
            task.cancel()
            return .cancelled(generationID: generationID)
        }
    }

    private func register(_ generationID: String, task: Task<Void, Never>) {
        lock.withLock {
            tasks[generationID] = task
        }
    }

    private func remove(_ generationID: String) {
        lock.withLock {
            tasks[generationID] = nil
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

private final class LoggingSink: RuntimeMessageSink, @unchecked Sendable {
    private let wrapped: any RuntimeMessageSink
    var connectionID: UUID { wrapped.connectionID }

    init(wrapped: any RuntimeMessageSink) {
        self.wrapped = wrapped
    }

    func send(_ envelope: ProtocolEnvelope) {
        print("[runtime] sending type=\(envelope.type) request_id=\(envelope.requestID)")
        wrapped.send(envelope)
    }

    func close() {
        wrapped.close()
    }
}
