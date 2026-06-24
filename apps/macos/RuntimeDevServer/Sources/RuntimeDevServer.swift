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
        let backend: any LlmBackend = useMockBackend
            ? DevMockBackend()
            : AggregatingLlmBackend(ollama: OllamaBackend(), lmStudio: LMStudioBackend())
        let pairingCoordinator = PairingCoordinator()
        let trustedDeviceStore = Self.trustedDeviceStore(environment: environment)
        let identity = Self.runtimeIdentity(environment: environment)
        let router = LocalRuntimeMessageRouter(
            backend: backend,
            pairingCoordinator: pairingCoordinator,
            trustedDeviceStore: trustedDeviceStore,
            onPairingAccepted: { device in
                print("[runtime] Development pairing accepted for device_id=\(device.id) name=\"\(device.name)\"")
            }
        )
        let server = LocalPeerServer()
        let advertiser = BonjourAdvertiser()
        let relayConfiguration = Self.relayConfiguration(environment: environment, identity: identity)
        let relayClient = relayConfiguration == nil ? nil : RelayPeerClient()
        RuntimeDevServerState.server = server
        RuntimeDevServerState.advertiser = advertiser
        RuntimeDevServerState.relayClient = relayClient

        server.start(port: port) { envelope, sink in
            print("[runtime] received type=\(envelope.type) request_id=\(envelope.requestID)")
            router.handle(envelope, sink: LoggingSink(wrapped: sink))
        }
        advertiser.start(port: Int32(port), metadata: identity.advertisementMetadata)
        if let relayConfiguration, let relayClient {
            relayClient.start(configuration: relayConfiguration) { envelope, sink in
                print("[runtime] relay received type=\(envelope.type) request_id=\(envelope.requestID)")
                router.handle(envelope, sink: LoggingSink(wrapped: sink))
            }
        }

        print("[runtime] AetherLink dev server listening on 127.0.0.1:\(port)")
        print("[runtime] Backend: \(useMockBackend ? "dev mock" : "Ollama + LM Studio")")
        print("[runtime] Advertising _aetherlink._tcp.local. on port \(port)")
        if let relayConfiguration {
            print("[runtime] Relay route enabled: \(relayConfiguration.host):\(relayConfiguration.port) id=\(relayConfiguration.relayID)")
        }
        print("[runtime] For a USB-connected client device, run:")
        print("[runtime]   adb reverse tcp:\(port) tcp:\(port)")
        print("[runtime] Then connect the client app to 127.0.0.1:\(port)")

        if environment["AETHERLINK_DEV_PAIRING"] == "1" {
            startDevelopmentPairing(
                coordinator: pairingCoordinator,
                port: port,
                identity: identity,
                environment: environment
            )
        }

        dispatchMain()
    }

    private static func trustedDeviceStore(environment: [String: String]) -> TrustedDeviceStore {
        guard let path = environment["AETHERLINK_DEV_TRUSTED_DEVICES_FILE"], !path.isEmpty else {
            return TrustedDeviceStore()
        }
        return TrustedDeviceStore(fileURL: URL(fileURLWithPath: path))
    }

    private static func relayConfiguration(
        environment: [String: String],
        identity: DevRuntimeIdentity
    ) -> RelayPeerConfiguration? {
        guard let host = environment["AETHERLINK_RELAY_HOST"]?.takeIfNotEmpty else {
            return nil
        }
        let port = UInt16(environment["AETHERLINK_RELAY_PORT"] ?? "") ?? 43171
        let relayID = environment["AETHERLINK_RELAY_ID"]?.takeIfNotEmpty ?? identity.routeToken
        let relaySecret = environment["AETHERLINK_RELAY_SECRET"]?.takeIfNotEmpty
        return RelayPeerConfiguration(host: host, port: port, relayID: relayID, relaySecret: relaySecret)
    }

    private static func startDevelopmentPairing(
        coordinator: PairingCoordinator,
        port: UInt16,
        identity: DevRuntimeIdentity,
        environment: [String: String]
    ) {
        let session = coordinator.beginPairing(
            validFor: TimeInterval(environment["AETHERLINK_DEV_PAIRING_TTL_SECONDS"] ?? "") ?? 300,
            macDeviceID: identity.deviceID,
            macName: identity.name,
            fingerprint: identity.fingerprint,
            runtimePublicKeyBase64: identity.publicKeyBase64.isEmpty ? nil : identity.publicKeyBase64,
            routeToken: identity.routeToken,
            host: environment["AETHERLINK_DEV_PAIRING_HOST"] ?? "127.0.0.1",
            port: Int(port),
            relayHost: environment["AETHERLINK_RELAY_HOST"]?.takeIfNotEmpty,
            relayPort: environment["AETHERLINK_RELAY_PORT"].flatMap { UInt16($0) }.map(Int.init),
            relayID: environment["AETHERLINK_RELAY_ID"]?.takeIfNotEmpty ?? identity.routeToken,
            relaySecret: environment["AETHERLINK_RELAY_SECRET"]?.takeIfNotEmpty
        )

        print("[runtime] WARNING: AETHERLINK_DEV_PAIRING=1 opened a development-only pairing window.")
        print("[runtime] Do not enable this mode for production or normal trusted-device use.")
        printDevelopmentPairingInfo(session)
    }

    private static func printDevelopmentPairingInfo(_ session: PairingSession) {
        var info: [String: Any] = [
            "pairing_code": session.code,
            "pairing_nonce": session.nonce,
            "mac_device_id": session.macDeviceID,
            "mac_name": session.macName,
            "fingerprint": session.fingerprint,
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

        guard let data = try? JSONSerialization.data(withJSONObject: info, options: [.sortedKeys]),
              let json = String(data: data, encoding: .utf8)
        else {
            print("[runtime] Failed to serialize development pairing info.")
            return
        }
        print("[runtime] AETHERLINK_DEV_PAIRING_INFO \(json)")
    }

    private static func runtimeIdentity(environment: [String: String]) -> DevRuntimeIdentity {
        let deviceID = environment["AETHERLINK_DEV_MAC_DEVICE_ID"] ?? "aetherlink-dev-mac"
        let identityKey = loadDevelopmentRuntimeIdentityKey(
            deviceID: deviceID,
            environment: environment
        )
        return DevRuntimeIdentity(
            deviceID: environment["AETHERLINK_DEV_MAC_DEVICE_ID"] ?? "aetherlink-dev-mac",
            name: environment["AETHERLINK_DEV_RUNTIME_NAME"] ?? environment["AETHERLINK_DEV_MAC_NAME"] ?? "AetherLink Dev Runtime",
            publicKeyBase64: identityKey.publicKeyBase64,
            fingerprint: environment["AETHERLINK_DEV_MAC_FINGERPRINT"] ?? identityKey.fingerprint,
            routeToken: environment["AETHERLINK_DEV_ROUTE_TOKEN"] ?? "dev-aetherlink-route"
        )
    }

    private static func loadDevelopmentRuntimeIdentityKey(
        deviceID: String,
        environment: [String: String]
    ) -> RuntimeIdentityKey {
        if let publicKey = environment["AETHERLINK_DEV_RUNTIME_PUBLIC_KEY"], !publicKey.isEmpty {
            return RuntimeIdentityKey(
                publicKeyBase64: publicKey,
                fingerprint: environment["AETHERLINK_DEV_RUNTIME_KEY_FINGERPRINT"] ?? "dev-\(deviceID)"
            )
        }
        do {
            return try RuntimeIdentityKeyStore(
                service: environment["AETHERLINK_DEV_RUNTIME_KEYCHAIN_SERVICE"] ?? "dev.aetherlink.runtime-dev-server",
                account: environment["AETHERLINK_DEV_RUNTIME_KEYCHAIN_ACCOUNT"] ?? deviceID
            ).loadOrCreate()
        } catch {
            return RuntimeIdentityKey(publicKeyBase64: "", fingerprint: "dev-\(deviceID)")
        }
    }
}

private struct DevRuntimeIdentity {
    var deviceID: String
    var name: String
    var publicKeyBase64: String
    var fingerprint: String
    var routeToken: String

    var advertisementMetadata: RuntimeAdvertisementMetadata {
        RuntimeAdvertisementMetadata(
            routeToken: routeToken,
            deviceID: deviceID,
            fingerprint: fingerprint
        )
    }
}

private enum RuntimeDevServerState {
    static var server: LocalPeerServer?
    static var advertiser: BonjourAdvertiser?
    static var relayClient: RelayPeerClient?
}

private extension String {
    var takeIfNotEmpty: String? {
        isEmpty ? nil : self
    }
}

private final class DevMockBackend: LlmBackend, @unchecked Sendable {
    let provider = ModelProvider.ollama
    private let lock = NSLock()
    private var tasks: [String: Task<Void, Never>] = [:]
    private var pulledModels: [String] = []

    func healthCheck() async -> BackendStatus {
        .available
    }

    func listModels() async throws -> [ModelInfo] {
        lock.withLock {
            var models = [
                ModelInfo(
                    id: "dev-mock",
                    name: "Dev Mock Streaming Model",
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

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task { [weak self] in
                let chunks = ["Mock ", "streaming ", "response."]
                for chunk in chunks {
                    if Task.isCancelled {
                        continuation.finish(throwing: OllamaBackendError.generationCancelled(generationID: request.generationID))
                        self?.remove(request.generationID)
                        return
                    }
                    continuation.yield(.delta(chunk))
                    try? await Task.sleep(nanoseconds: 350_000_000)
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
