import struct BridgeProtocol.ProtocolEnvelope
import enum BridgeProtocol.PairedRelayAllocationAuthorization
import protocol BridgeProtocol.PairedRelayAllocationRuntimeSigning
import struct BridgeProtocol.RelayAllocationIdentityChallenge
import protocol BridgeProtocol.RelayIdentityAuthorizationSigning
import struct BridgeProtocol.RelayRuntimeIdentity
import struct BridgeProtocol.TransportSecurityContext
import CompanionCore
import Darwin
import Dispatch
import DocumentIngestion
import Foundation
import struct OllamaBackend.BackendError
import class LMStudioBackend.LMStudioBackend
import enum OllamaBackend.BackendStatus
import struct OllamaBackend.ChatRequest
import enum OllamaBackend.ChatStreamEvent
import enum OllamaBackend.GenerationCancellationResult
import struct OllamaBackend.EmbeddingRequest
import struct OllamaBackend.EmbeddingResult
import protocol OllamaBackend.LlmBackend
import struct OllamaBackend.ModelInfo
import enum OllamaBackend.ModelKind
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
        let runtimeMemoryStore = Self.runtimeMemoryStore(environment: environment)
        let runtimeDocumentIndexStore = Self.runtimeDocumentIndexStore(environment: environment)
        let runtimeMemorySummaryPolicy = Self.runtimeMemorySummaryPolicy(environment: environment)
        let identity = Self.runtimeIdentity(environment: environment)
        let relayServiceRouteAllocator = TCPRelayServiceRouteAllocator()
        let pairedRelayAuthorization = try? relayAllocationAuthorization(identity)
        let server = LocalPeerServer()
        let advertiser = BonjourAdvertiser()
        let shouldAdvertiseBonjour = environment["AETHERLINK_DEV_DISABLE_BONJOUR"] != "1"
        let relayRouteRequested = Self.relayRouteRequested(environment: environment)
        let relayRouteAllocation = Self.relayRouteAllocation(
            environment: environment,
            identity: identity,
            relayServiceRouteAllocator: relayServiceRouteAllocator
        )
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
            logReceivedEnvelope(envelope, route: "relay")
            routerBox.handle(envelope, sink: LoggingSink(wrapped: sink))
        }
        let relayStatusHandler: @Sendable (RelayPeerStatus) -> Void = { status in
            relayPairingReadiness.update(status)
            print("[runtime] relay status=\(status.logLabel)")
        }
        let routeRefresher = DevelopmentRuntimeRouteRefresher(
            runtimeDeviceID: identity.deviceID,
            runtimeKeyFingerprint: identity.fingerprint,
            currentRouteToken: identity.routeToken,
            runtimeIdentity: pairedRelayAuthorization?.identity,
            authorizationSigner: pairedRelayAuthorization?.signer,
            relayServiceRouteAllocator: relayServiceRouteAllocator,
            allocationToken: environment["AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty
                ?? environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty,
            initialAllocation: relayRouteAllocation,
            activeRelayClientRetirer: relayClient.map { client in
                { client.retireAfterCurrentConnection() }
            },
            allocationProvider: {
                Self.relayRouteAllocation(
                    environment: environment,
                    identity: identity,
                    relayServiceRouteAllocator: relayServiceRouteAllocator
                )
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
            memoryStore: runtimeMemoryStore,
            documentIndexStore: runtimeDocumentIndexStore,
            memorySummaryPolicy: runtimeMemorySummaryPolicy,
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
            logReceivedEnvelope(envelope, route: nil)
            routerBox.handle(envelope, sink: LoggingSink(wrapped: sink))
        }
        if shouldAdvertiseBonjour {
            advertiser.start(port: Int32(port), metadata: identity.advertisementMetadata)
        }
        if let relayConfiguration, let relayClient {
            if relayConfiguration.runtimeIdentity != nil,
               relayConfiguration.identityAuthorizationSigner != nil {
                relayClient.start(
                    configuration: relayConfiguration,
                    onStatusChange: relayStatusHandler,
                    onMessage: relayMessageHandler
                )
            } else {
                print("[runtime] Relay route not started: runtime signing identity is unavailable.")
            }
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

    private static func runtimeMemoryStore(environment: [String: String]) -> any RuntimeMemoryStore {
        guard let path = environment["AETHERLINK_DEV_RUNTIME_MEMORY_JSONL_FILE"]?.takeIfNotEmpty else {
            return JSONLRuntimeMemoryStore()
        }
        return JSONLRuntimeMemoryStore(fileURL: URL(fileURLWithPath: path))
    }

    private static func runtimeDocumentIndexStore(environment: [String: String]) -> any RuntimeDocumentIndexReading {
        let store: SQLiteRuntimeDocumentIndexStore
        if let path = environment["AETHERLINK_DEV_RUNTIME_DOCUMENT_INDEX_SQLITE_FILE"]?.takeIfNotEmpty {
            store = SQLiteRuntimeDocumentIndexStore(databaseURL: URL(fileURLWithPath: path))
        } else {
            store = SQLiteRuntimeDocumentIndexStore()
        }
        if environment["AETHERLINK_DEV_RUNTIME_DOCUMENT_INDEX_SEED_SMOKE"] == "1" {
            do {
                try seedDevelopmentDocumentIndex(store)
            } catch {
                print("[runtime] document index seed failed: \(error.localizedDescription)")
            }
        }
        return store
    }

    private static func seedDevelopmentDocumentIndex(_ store: SQLiteRuntimeDocumentIndexStore) throws {
        let ingestor = DocumentIngestor(chunker: DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 120,
            overlapCharacters: 8,
            minChunkCharacters: 24
        )))
        try store.replaceDocument(
            result: ingestor.ingest(extractedDocument: ExtractedDocument(
                fileName: "runtime-retrieval-smoke.md",
                mimeType: "text/markdown",
                text: [
                    "Seeded runtime retrieval smoke proves document index results stay bounded for authenticated relay clients.",
                    "Lexical retrieval should return this snippet before semantic embeddings, citations, or trusted-source review exist.",
                    "AETHERLINK_SMOKE_RETRIEVAL_PRIVATE_BODY_SHOULD_NOT_APPEAR"
                ].joined(separator: " ")
            )),
            documentID: "smoke-retrieval-doc"
        )
        try store.replaceDocument(
            result: ingestor.ingest(extractedDocument: ExtractedDocument(
                fileName: "runtime-memory-smoke.md",
                mimeType: "text/markdown",
                text: [
                    "Runtime memory search is adjacent but this document is not the lexical document-index match.",
                    "AETHERLINK_SMOKE_RETRIEVAL_SECONDARY_BODY_SHOULD_NOT_APPEAR"
                ].joined(separator: " ")
            )),
            documentID: "smoke-memory-doc"
        )
    }

    private static func runtimeMemorySummaryPolicy(
        environment: [String: String]
    ) -> @Sendable (Int) -> RuntimeLongInactivityMemorySummarizationPolicy {
        let minimumInactiveInterval = TimeInterval(
            environment["AETHERLINK_DEV_MEMORY_SUMMARY_MIN_INACTIVE_SECONDS"] ?? ""
        )
        let minimumMessageCount = Int(environment["AETHERLINK_DEV_MEMORY_SUMMARY_MIN_MESSAGES"] ?? "")
        return { maxCandidateCount in
            RuntimeLongInactivityMemorySummarizationPolicy(
                minimumInactiveInterval: minimumInactiveInterval
                    ?? RuntimeLongInactivityMemorySummarizationPolicy.defaultMinimumInactiveInterval,
                minimumMessageCount: minimumMessageCount ?? 6,
                maxCandidateCount: maxCandidateCount
            )
        }
    }

    private static func developmentMockBackend(
        environment: [String: String],
        aggregateResidency: Bool
    ) -> any LlmBackend {
        guard aggregateResidency else {
            return AggregatingLlmBackend(
                [
                    DevMockBackend(
                        additionalModels: [
                            (
                                id: "nomic-embed-text",
                                name: "Dev Mock Embedding Model",
                                capabilities: ["embedding"]
                            )
                        ],
                        environment: environment
                    )
                ]
            )
        }
        let idleDelayMilliseconds = UInt64(environment["AETHERLINK_DEV_MOCK_RESIDENCY_IDLE_MS"] ?? "") ?? 600_000
        return AggregatingLlmBackend(
            [
                DevMockBackend(
                    provider: .ollama,
                    modelID: "dev-mock",
                    modelName: "Dev Mock Streaming Model",
                    additionalModels: [
                        (
                            id: "dev-mock-unload-failure",
                            name: "Dev Mock Unload Failure Model",
                            capabilities: ["chat"]
                        ),
                        (
                            id: "nomic-embed-text",
                            name: "Dev Mock Embedding Model",
                            capabilities: ["embedding"]
                        )
                    ],
                    environment: environment
                ),
                DevMockBackend(
                    provider: .lmStudio,
                    modelID: "dev-mock-alt",
                    modelName: "Dev Mock Alternate Model",
                    additionalModels: [
                        (
                            id: "dev-mock-vision",
                            name: "Dev Mock Vision Model",
                            capabilities: ["chat", "vision"]
                        )
                    ],
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

    private static func logReceivedEnvelope(_ envelope: ProtocolEnvelope, route: String?) {
        let routePrefix = route.map { "\($0) " } ?? ""
        print("[runtime] \(routePrefix)received type=\(envelope.type) request_id=\(envelope.requestID)")
        guard envelope.type == "chat.send",
              case .string(let model)? = envelope.payload["model"] else {
            return
        }
        print("[runtime] \(routePrefix)received chat.send model=\(safeLogIdentifier(model)) request_id=\(envelope.requestID)")
    }

    private static func safeLogIdentifier(_ value: String) -> String {
        let normalized = value.unicodeScalars.map { scalar -> String in
            if CharacterSet.whitespacesAndNewlines.contains(scalar)
                || CharacterSet.controlCharacters.contains(scalar) {
                return "_"
            }
            return String(scalar)
        }.joined()
        return String(normalized.prefix(256))
    }

    private static func relayRouteAllocation(
        environment: [String: String],
        identity: DevRuntimeIdentity,
        relayServiceRouteAllocator: any RelayServiceRouteAllocating
    ) -> CompanionRemoteRelayRouteAllocation? {
        let authorization: (
            identity: RelayRuntimeIdentity,
            signer: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning
        )
        do {
            authorization = try relayAllocationAuthorization(identity)
        } catch {
            if relayRouteRequested(environment: environment) {
                print("[runtime] relay allocation failed: \(error.localizedDescription)")
            }
            return nil
        }
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
                        relayNonce: lease.nonce,
                        runtimeIdentity: authorization.identity,
                        identityAuthorizationSigner: authorization.signer
                    ),
                    lease: CompanionRemoteRouteLease(
                        expiresAtEpochMillis: lease.expiresAtEpochMillis,
                        nonce: lease.nonce
                    )
                )
            }
            do {
                let endpointRelaySecret = Self.preferredDevelopmentRelaySecret(environment: environment)
                let serviceAllocation = try relayServiceRouteAllocator.allocateRelayRoute(
                    host: host,
                    port: port,
                    routeToken: identity.routeToken,
                    allocationToken: environment["AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty
                        ?? environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty,
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer,
                    timeout: 5
                )
                return try serviceAllocation.attachingEndpointSecret(
                    endpointRelaySecret,
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer
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
            return try EnvironmentRemoteRelayRouteAllocator(
                environment: environment,
                relayServiceAllocator: relayServiceRouteAllocator
            )
                .allocateRemoteRelayRoute(
                    runtimeDeviceID: identity.deviceID,
                    routeToken: identity.routeToken,
                    preferredRelaySecret: Self.preferredDevelopmentRelaySecret(environment: environment),
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer
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
    ) -> (
        key: RuntimeIdentityKey,
        signer: (
            any RuntimeChallengeSigning
                & RelayIdentityAuthorizationSigning
                & InitialPairingRuntimeResultSigning
                & PairedRelayAllocationRuntimeSigning
        )?
    ) {
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

private func relayAllocationAuthorization(
    _ identity: DevRuntimeIdentity
) throws -> (
    identity: RelayRuntimeIdentity,
    signer: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning
) {
    guard let signer = identity.signer else {
        throw RelayServiceRouteAllocationError.signingIdentityUnavailable
    }
    let relayIdentity = try signer.relayRuntimeIdentity()
    guard relayIdentity.publicKeyBase64 == identity.publicKeyBase64,
          relayIdentity.fingerprint == identity.fingerprint
    else {
        throw RelayServiceRouteAllocationError.signingIdentityMismatch
    }
    return (relayIdentity, signer)
}

private struct DevRuntimeIdentity {
    var deviceID: String
    var name: String
    var publicKeyBase64: String
    var fingerprint: String
    var routeToken: String
    var signer: (
        any RuntimeChallengeSigning
            & RelayIdentityAuthorizationSigning
            & InitialPairingRuntimeResultSigning
            & PairedRelayAllocationRuntimeSigning
    )?

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
    private struct PendingRelayActivation {
        let result: RuntimeRouteRefreshResult
        let allocation: CompanionRemoteRelayRouteAllocation
    }

    private let runtimeDeviceID: String
    private let runtimeKeyFingerprint: String
    private let currentRouteToken: String
    private let runtimeIdentity: RelayRuntimeIdentity?
    private let authorizationSigner: (
        any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning
    )?
    private let relayServiceRouteAllocator: any RelayServiceRouteAllocating
    private let allocationToken: String?
    private let allocationProvider: () -> CompanionRemoteRelayRouteAllocation?
    private let p2pRouteProvider: () -> DevelopmentP2PRouteMaterial?
    private let relayStatusHandler: @Sendable (RelayPeerStatus) -> Void
    private let relayMessageHandler: LocalPeerMessageHandler
    private let relayDisconnectHandler: @Sendable (UUID) -> Void
    private let relayScopeProvider: (String) -> String?
    private var activeAllocation: CompanionRemoteRelayRouteAllocation?
    private var activeRelayClientRetirer: (() -> Void)?
    private var refreshedRelayClients: [ObjectIdentifier: RelayPeerClient] = [:]
    private var pendingRelayActivation: PendingRelayActivation?

    init(
        runtimeDeviceID: String,
        runtimeKeyFingerprint: String,
        currentRouteToken: String,
        runtimeIdentity: RelayRuntimeIdentity?,
        authorizationSigner: (
            any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning
        )?,
        relayServiceRouteAllocator: any RelayServiceRouteAllocating,
        allocationToken: String?,
        initialAllocation: CompanionRemoteRelayRouteAllocation?,
        activeRelayClientRetirer: (() -> Void)?,
        allocationProvider: @escaping () -> CompanionRemoteRelayRouteAllocation?,
        p2pRouteProvider: @escaping () -> DevelopmentP2PRouteMaterial?,
        relayStatusHandler: @escaping @Sendable (RelayPeerStatus) -> Void,
        relayMessageHandler: @escaping LocalPeerMessageHandler,
        relayDisconnectHandler: @escaping @Sendable (UUID) -> Void,
        relayScopeProvider: @escaping (String) -> String?
    ) {
        self.runtimeDeviceID = runtimeDeviceID
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.currentRouteToken = currentRouteToken
        self.runtimeIdentity = runtimeIdentity
        self.authorizationSigner = authorizationSigner
        self.relayServiceRouteAllocator = relayServiceRouteAllocator
        self.allocationToken = allocationToken
        self.activeAllocation = initialAllocation
        self.activeRelayClientRetirer = activeRelayClientRetirer
        self.allocationProvider = allocationProvider
        self.p2pRouteProvider = p2pRouteProvider
        self.relayStatusHandler = relayStatusHandler
        self.relayMessageHandler = relayMessageHandler
        self.relayDisconnectHandler = relayDisconnectHandler
        self.relayScopeProvider = relayScopeProvider
    }

    func refreshRuntimeRoute() async throws -> RuntimeRouteRefreshResult? {
        guard let allocation = allocationProvider() else {
            return nil
        }
        guard let result = routeRefreshResult(for: allocation) else {
            return nil
        }
        pendingRelayActivation = PendingRelayActivation(
            result: result,
            allocation: allocation
        )
        return result
    }

    func refreshRuntimeRoute(
        authorizationContext: RuntimePairedRelayAuthorizationContext?
    ) async throws -> RuntimeRouteRefreshResult? {
        guard let authorizationContext else {
            throw RuntimeRouteRefreshAuthorizationError.pairedAuthorizationRequired
        }
        let bootstrapRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: currentRouteToken,
            runtimeKeyFingerprint: runtimeKeyFingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: currentRouteToken,
            runtimeKeyFingerprint: runtimeKeyFingerprint,
            clientKeyFingerprint: authorizationContext.trustedClientKeyFingerprint
        )
        guard let currentAllocation = activeAllocation,
              let currentLease = currentAllocation.lease,
              let currentTicketGeneration = currentLease.ticketGeneration,
              currentTicketGeneration > 0,
              currentTicketGeneration < Int64.max,
              let endpointRelaySecret = currentAllocation.configuration.relaySecret?.takeIfNotEmpty,
              currentAllocation.configuration.relayNonce == currentLease.nonce,
              !currentLease.isExpired(),
              let runtimeIdentity,
              let authorizationSigner,
              PairedRelayAllocationAuthorization.isCanonicalRelayID(
                  currentAllocation.configuration.relayID
              ),
              currentAllocation.configuration.relayID == bootstrapRelayID ||
                currentAllocation.configuration.relayID == pairedRelayID
        else {
            throw RelayServiceRouteAllocationError.invalidPairedRenewalRequest
        }

        let serviceAllocation = try await relayServiceRouteAllocator.renewPairedRelayRoute(
            currentRouteToken: currentRouteToken,
            currentConfiguration: currentAllocation.configuration,
            currentLease: currentLease,
            runtimeIdentity: runtimeIdentity,
            authorizationSigner: authorizationSigner,
            authorizationContext: authorizationContext,
            allocationToken: allocationToken,
            timeout: 5
        )
        guard serviceAllocation.host == currentAllocation.configuration.host,
              serviceAllocation.port == currentAllocation.configuration.port,
              serviceAllocation.relayID == pairedRelayID,
              serviceAllocation.runtimeKeyFingerprint == runtimeIdentity.fingerprint,
              serviceAllocation.ticketGeneration == currentTicketGeneration + 1,
              serviceAllocation.relayExpiresAtEpochMillis > currentLease.expiresAtEpochMillis,
              serviceAllocation.relayNonce != currentLease.nonce,
              !serviceAllocation.relayNonce.isEmpty
        else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }
        let renewedAllocation = try serviceAllocation.attachingEndpointSecret(
            endpointRelaySecret,
            runtimeIdentity: runtimeIdentity,
            identityAuthorizationSigner: authorizationSigner
        )
        guard let renewedLease = renewedAllocation.lease,
              renewedLease.isAdvancingReplacement(of: currentLease),
              renewedAllocation.configuration.host == currentAllocation.configuration.host,
              renewedAllocation.configuration.port == currentAllocation.configuration.port,
              renewedAllocation.configuration.relayID == pairedRelayID,
              renewedAllocation.configuration.relaySecret == endpointRelaySecret,
              let result = routeRefreshResult(for: renewedAllocation)
        else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }

        pendingRelayActivation = PendingRelayActivation(
            result: result,
            allocation: renewedAllocation
        )
        return result
    }

    func activateRuntimeRouteRefresh(_ result: RuntimeRouteRefreshResult) async {
        guard let pendingRelayActivation,
              pendingRelayActivation.result == result
        else {
            return
        }
        self.pendingRelayActivation = nil
        installRefreshedRelayClient(for: pendingRelayActivation.allocation)
    }

    private func installRefreshedRelayClient(for allocation: CompanionRemoteRelayRouteAllocation) {
        let configuration = allocation.configuration
        let refreshedRelayClient = RelayPeerClient()
        let clientID = ObjectIdentifier(refreshedRelayClient)
        refreshedRelayClients[clientID] = refreshedRelayClient
        refreshedRelayClient.onDisconnect = { [weak self] connectionID in
            self?.relayDisconnectHandler(connectionID)
        }
        refreshedRelayClient.start(
            configuration: configuration,
            onStatusChange: relayStatusHandler,
            onMessage: relayMessageHandler
        )
        let previousRelayClientRetirer = activeRelayClientRetirer
        activeAllocation = allocation
        activeRelayClientRetirer = { [weak refreshedRelayClient] in
            refreshedRelayClient?.retireAfterCurrentConnection()
        }
        previousRelayClientRetirer?()
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
            relayTicketGeneration: lease.ticketGeneration,
            relayScope: relayScopeProvider(configuration.host),
            p2pRouteClass: p2pRoute?.routeClass,
            p2pRecordID: p2pRoute?.recordID,
            p2pEncryptedBody: p2pRoute?.encryptedBody,
            p2pExpiresAtEpochMillis: p2pRoute?.expiresAtEpochMillis,
            p2pAntiReplayNonce: p2pRoute?.antiReplayNonce,
            p2pProtocolVersion: p2pRoute?.protocolVersion
        )
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
    private let capabilities: [String]
    private let additionalModels: [(id: String, name: String, capabilities: [String])]
    private let chunkDelayNanoseconds: UInt64
    private let unloadEventFile: String?
    private let chatRequestAuditFile: String?
    private let embeddingRequestAuditFile: String?
    private let unloadFailureTargets: Set<String>
    private let lock = NSLock()
    private var tasks: [String: Task<Void, Never>] = [:]
    private var pulledModels: [String] = []

    init(
        provider: ModelProvider = .ollama,
        modelID: String = "dev-mock",
        modelName: String = "Dev Mock Streaming Model",
        capabilities: [String] = ["chat"],
        additionalModels: [(id: String, name: String, capabilities: [String])] = [],
        environment: [String: String] = ProcessInfo.processInfo.environment
    ) {
        self.provider = provider
        self.modelID = modelID
        self.modelName = modelName
        self.capabilities = capabilities
        self.additionalModels = additionalModels
        let delayMilliseconds = UInt64(environment["AETHERLINK_DEV_MOCK_CHUNK_DELAY_MS"] ?? "") ?? 350
        chunkDelayNanoseconds = max(1, delayMilliseconds) * 1_000_000
        unloadEventFile = environment["AETHERLINK_DEV_MOCK_UNLOAD_EVENT_FILE"]?.takeIfNotEmpty
        chatRequestAuditFile = environment["AETHERLINK_DEV_MOCK_CHAT_REQUEST_AUDIT_FILE"]?.takeIfNotEmpty
        embeddingRequestAuditFile = environment["AETHERLINK_DEV_MOCK_EMBEDDING_REQUEST_AUDIT_FILE"]?.takeIfNotEmpty
        unloadFailureTargets = Set(
            (environment["AETHERLINK_DEV_MOCK_UNLOAD_FAILURES"] ?? "")
                .split(separator: ",")
                .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }
        )
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
                    kind: ModelKind.from(capabilities: capabilities, fallbackName: modelName),
                    capabilities: capabilities,
                    sizeBytes: 0,
                    modifiedAt: Self.stableModelModifiedAt,
                    installed: true,
                    running: false,
                    source: .local,
                    contextWindowTokens: 8_192,
                    persistentEmbeddingRevision: Self.persistentEmbeddingRevision(for: modelID)
                )
            ]
            models.append(contentsOf: additionalModels.map {
                ModelInfo(
                    id: $0.id,
                    name: $0.name,
                    provider: provider,
                    kind: ModelKind.from(capabilities: $0.capabilities, fallbackName: $0.name),
                    capabilities: $0.capabilities,
                    sizeBytes: 0,
                    modifiedAt: Self.stableModelModifiedAt,
                    installed: true,
                    running: false,
                    source: .local,
                    persistentEmbeddingRevision: Self.persistentEmbeddingRevision(for: $0.id)
                )
            })
            models.append(contentsOf: pulledModels.map {
                ModelInfo(
                    id: $0,
                    name: $0,
                    provider: provider,
                    capabilities: capabilities,
                    sizeBytes: 0,
                    modifiedAt: Self.stableModelModifiedAt,
                    installed: true,
                    running: false,
                    source: .local,
                    persistentEmbeddingRevision: Self.persistentEmbeddingRevision(for: $0)
                )
            })
            return models
        }
    }

    private static let stableModelModifiedAt = Date(timeIntervalSince1970: 0)

    private static func persistentEmbeddingRevision(for _: String) -> String {
        return "ollama-sha256:" + String(repeating: "d", count: 64)
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
        if unloadFailureTargets.contains("\(provider.rawValue)|\(providerModelID)") {
            throw BackendError(
                provider: provider,
                code: "mock_unload_failed",
                message: "Mock unload failure from http://127.0.0.1:11434/api/chat?relay_secret=mock-secret",
                retryable: true
            )
        }
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

    func embed(request: EmbeddingRequest) async throws -> EmbeddingResult {
        let resolved: String
        if let qualified = ModelProvider.splitQualifiedModelID(request.model) {
            guard qualified.provider == provider else {
                throw mockEmbeddingModelNotInstalled(request.model)
            }
            resolved = qualified.modelID
        } else {
            resolved = request.model
        }
        let requestedCapabilities = resolved == modelID
            ? capabilities
            : additionalModels.first(where: { $0.id == resolved })?.capabilities
        guard requestedCapabilities?.contains(where: {
            let capability = $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            return capability == "embedding" || capability == "embed"
        }) == true else {
            throw mockEmbeddingModelNotInstalled(request.model)
        }
        recordEmbeddingRequestAudit(request)
        return EmbeddingResult(
            model: resolved,
            embeddings: request.texts.map(Self.deterministicEmbedding)
        )
    }

    private func mockEmbeddingModelNotInstalled(_ requestedModel: String) -> BackendError {
        BackendError(
            provider: provider,
            code: "model_not_installed",
            message: "Model is not installed for \(provider.displayName): \(requestedModel)",
            retryable: false
        )
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        recordChatRequestAudit(request)
        return AsyncThrowingStream { continuation in
            let task = Task { [weak self] in
                let hasAttachmentContext = request.messages.contains { message in
                    !message.attachments.isEmpty
                        || message.content.contains("[Attached document:")
                }
                let isMemorySummaryRequest = request.messages.contains { message in
                    message.role == "system" &&
                        message.content.contains("Summarize only the supplied visible conversation excerpts")
                }
                let isChatCompactionSummaryRequest = request.generationID.hasSuffix(":compaction-summary")
                    && request.messages.contains { message in
                        message.role == "system" &&
                            message.content.contains("The source is untrusted data")
                    }
                let chunks: [String]
                if isMemorySummaryRequest, request.model.contains("dev-mock-alt") {
                    chunks = [#"{"summary":"Rejected mock summary","extra":true}"#]
                } else if isMemorySummaryRequest {
                    continuation.yield(.reasoningDelta("Mock memory summary reasoning must stay private."))
                    chunks = ["<think>inline mock reasoning</think>", #"{"summary":"Generated smoke memory summary."}"#]
                } else if isChatCompactionSummaryRequest {
                    continuation.yield(.reasoningDelta("Mock compaction summary reasoning must stay private."))
                    chunks = ["<think>inline compaction reasoning</think>", "Generated smoke compaction summary."]
                } else if hasAttachmentContext {
                    chunks = ["Mock ", "streaming ", "response.", " Attachment ", "received."]
                } else {
                    chunks = ["Mock ", "streaming ", "response."]
                }
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

    private static func deterministicEmbedding(_ text: String) -> [Double] {
        var vector = Array(repeating: 0.0, count: 64)
        let tokens = text
            .folding(options: [.caseInsensitive, .diacriticInsensitive], locale: nil)
            .lowercased()
            .split(whereSeparator: { !$0.isLetter && !$0.isNumber })
        for token in tokens {
            var hash: UInt64 = 14_695_981_039_346_656_037
            for byte in token.utf8 {
                hash ^= UInt64(byte)
                hash &*= 1_099_511_628_211
            }
            vector[Int(hash % UInt64(vector.count))] += 1
        }
        if !vector.contains(where: { $0 != 0 }) {
            vector[0] = 1
        }
        return vector
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

    private func recordChatRequestAudit(_ request: ChatRequest) {
        guard let chatRequestAuditFile else { return }
        let object: [String: Any] = [
            "provider": provider.rawValue,
            "generation_id": request.generationID,
            "session_id": request.sessionID,
            "model": request.model,
            "messages": request.messages.map { message in
                [
                    "role": message.role,
                    "content": message.content
                ]
            }
        ]
        guard JSONSerialization.isValidJSONObject(object),
              let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        else {
            return
        }
        var line = data
        line.append(0x0A)
        lock.withLock {
            let url = URL(fileURLWithPath: chatRequestAuditFile)
            if FileManager.default.fileExists(atPath: chatRequestAuditFile),
               let handle = try? FileHandle(forWritingTo: url) {
                _ = try? handle.seekToEnd()
                _ = try? handle.write(contentsOf: line)
                _ = try? handle.close()
            } else {
                try? line.write(to: url, options: .atomic)
            }
        }
    }

    private func recordEmbeddingRequestAudit(_ request: EmbeddingRequest) {
        guard let embeddingRequestAuditFile else { return }
        let object: [String: Any] = [
            "provider": provider.rawValue,
            "model": request.model,
            "input_count": request.texts.count,
        ]
        guard JSONSerialization.isValidJSONObject(object),
              let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) else {
            return
        }
        var line = data
        line.append(0x0A)
        lock.withLock {
            let url = URL(fileURLWithPath: embeddingRequestAuditFile)
            if FileManager.default.fileExists(atPath: embeddingRequestAuditFile),
               let handle = try? FileHandle(forWritingTo: url) {
                _ = try? handle.seekToEnd()
                _ = try? handle.write(contentsOf: line)
                _ = try? handle.close()
            } else {
                try? line.write(to: url, options: .atomic)
            }
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
    var transportSecurityContext: TransportSecurityContext? { wrapped.transportSecurityContext }

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
