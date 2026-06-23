import Foundation
import LMStudioBackend
import OllamaBackend
import Pairing
import Transport
import TrustedDevices

@MainActor
public final class CompanionAppModel: ObservableObject {
    @Published public private(set) var backendStatus = "Not checked"
    @Published public private(set) var transportStatus = "Stopped"
    @Published public private(set) var pairingSession: PairingSession?
    @Published public private(set) var trustedDevices: [TrustedDevice] = []
    @Published public private(set) var models: [ModelInfo] = []
    @Published public private(set) var logs: [String] = []

    private let backend: any LlmBackend
    private var runtimeRouter: LocalRuntimeMessageRouter!
    private let pairingCoordinator = PairingCoordinator()
    private let trustedDeviceStore = TrustedDeviceStore()
    private let peerServer: any RuntimeTransport
    private let advertiser: any RuntimeAdvertiser
    private let macDeviceID: String
    private var runtimePort: UInt16 = 43170

    public init(
        backend: any LlmBackend = AggregatingLlmBackend(ollama: OllamaBackend(), lmStudio: LMStudioBackend()),
        peerServer: any RuntimeTransport = LocalPeerServer(),
        advertiser: any RuntimeAdvertiser = BonjourAdvertiser()
    ) {
        self.backend = backend
        self.peerServer = peerServer
        self.advertiser = advertiser
        self.macDeviceID = Self.loadOrCreateMacDeviceID()
        self.runtimeRouter = LocalRuntimeMessageRouter(
            backend: backend,
            pairingCoordinator: pairingCoordinator,
            trustedDeviceStore: trustedDeviceStore,
            onPairingAccepted: { [weak self] device in
                Task { @MainActor in
                    self?.pairingSession = nil
                    await self?.refreshTrustedDevices()
                    self?.log("Trusted \(device.name)")
                }
            }
        )
    }

    public func start(port: UInt16 = 43170) {
        runtimePort = port
        let router = runtimeRouter!
        peerServer.start(port: port) { [router, weak self] envelope, sink in
            Task { @MainActor in
                self?.log("Received \(envelope.type)")
            }
            router.handle(envelope, sink: sink)
        }
        advertiser.start(port: Int32(port))
        transportStatus = "Advertising _aetherlink._tcp.local. on port \(port)"
        log("Companion started")
        Task {
            await refreshTrustedDevices()
            await refreshOllamaStatus()
        }
    }

    public func stop() {
        peerServer.stop()
        advertiser.stop()
        transportStatus = "Stopped"
        log("Companion stopped")
    }

    public func refreshOllamaStatus() async {
        if let aggregate = backend as? AggregatingLlmBackend {
            let statuses = await aggregate.providerHealth()
            backendStatus = statuses
                .sorted { $0.key.rawValue < $1.key.rawValue }
                .map { provider, status in
                    switch status {
                    case .available:
                        return "\(provider.displayName) available"
                    case .unavailable(let error):
                        return "\(provider.displayName) unavailable: \(error.message)"
                    }
                }
                .joined(separator: " | ")
            log(backendStatus)
            return
        }

        switch await backend.healthCheck() {
        case .available:
            backendStatus = "\(backend.provider.displayName) available"
            log("\(backend.provider.displayName) health check passed")
        case .unavailable(let error):
            backendStatus = error.message
            log(error.message)
        }
    }

    public func loadModels() async {
        do {
            models = try await backend.listModels()
            log("Loaded \(models.count) local model(s)")
        } catch {
            log("Model list failed: \(error.localizedDescription)")
        }
    }

    public func beginPairing() {
        pairingSession = pairingCoordinator.beginPairing(
            macDeviceID: macDeviceID,
            fingerprint: "dev-\(macDeviceID)",
            host: Self.primaryLocalIPv4Address(),
            port: Int(runtimePort)
        )
        log("Pairing code generated")
    }

    public func removeTrustedDevice(_ device: TrustedDevice) async {
        do {
            try await trustedDeviceStore.remove(deviceID: device.id)
            await refreshTrustedDevices()
            log("Removed \(device.name)")
        } catch {
            log("Remove trusted device failed: \(error.localizedDescription)")
        }
    }

    public func refreshTrustedDevices() async {
        do {
            trustedDevices = try await trustedDeviceStore.load()
        } catch {
            log("Trusted device load failed: \(error.localizedDescription)")
        }
    }

    private func log(_ message: String) {
        logs.insert(message, at: 0)
        logs = Array(logs.prefix(50))
    }

    private static func loadOrCreateMacDeviceID() -> String {
        let key = "aetherlink.mac_device_id"
        if let existing = UserDefaults.standard.string(forKey: key), !existing.isEmpty {
            return existing
        }
        let deviceID = UUID().uuidString
        UserDefaults.standard.set(deviceID, forKey: key)
        return deviceID
    }

    private static func primaryLocalIPv4Address() -> String {
        Host.current().addresses.first { address in
            address.contains(".")
                && !address.hasPrefix("127.")
                && !address.hasPrefix("169.254.")
        } ?? "127.0.0.1"
    }
}
