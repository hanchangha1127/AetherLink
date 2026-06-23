import Foundation
import LMStudioBackend
import OllamaBackend
import Pairing
import Transport
import TrustedDevices

public struct CompanionTransportStatus: Equatable, Sendable {
    public enum State: Equatable, Sendable {
        case stopped
        case advertising
        case failed
    }

    public var state: State
    public var serviceName: String?
    public var port: UInt16?
    public var failureMessage: String?

    public init(
        state: State,
        serviceName: String? = nil,
        port: UInt16? = nil,
        failureMessage: String? = nil
    ) {
        self.state = state
        self.serviceName = serviceName
        self.port = port
        self.failureMessage = failureMessage
    }

    public static let stopped = CompanionTransportStatus(state: .stopped)

    public static func advertising(serviceName: String, port: UInt16) -> CompanionTransportStatus {
        CompanionTransportStatus(state: .advertising, serviceName: serviceName, port: port)
    }

    public static func failed(_ message: String) -> CompanionTransportStatus {
        CompanionTransportStatus(state: .failed, failureMessage: message)
    }
}

public struct CompanionProviderStatus: Identifiable, Equatable, Sendable {
    public enum Availability: Equatable, Sendable {
        case notChecked
        case available
        case unavailable
    }

    public var provider: ModelProvider
    public var availability: Availability
    public var message: String?
    public var code: String?
    public var retryable: Bool?

    public var id: String {
        provider.rawValue
    }

    public init(
        provider: ModelProvider,
        availability: Availability,
        message: String? = nil,
        code: String? = nil,
        retryable: Bool? = nil
    ) {
        self.provider = provider
        self.availability = availability
        self.message = message
        self.code = code
        self.retryable = retryable
    }

    public static func notChecked(provider: ModelProvider) -> CompanionProviderStatus {
        CompanionProviderStatus(provider: provider, availability: .notChecked)
    }

    public static func from(provider: ModelProvider, status: BackendStatus) -> CompanionProviderStatus {
        switch status {
        case .available:
            return CompanionProviderStatus(provider: provider, availability: .available, message: status.message)
        case .unavailable(let error):
            return CompanionProviderStatus(
                provider: provider,
                availability: .unavailable,
                message: error.message,
                code: error.code,
                retryable: error.retryable
            )
        }
    }
}

@MainActor
public final class CompanionAppModel: ObservableObject {
    @Published public private(set) var backendStatus = "Not checked"
    @Published public private(set) var transportStatus = "Stopped"
    @Published public private(set) var transportState: CompanionTransportStatus = .stopped
    @Published public private(set) var providerStatuses: [CompanionProviderStatus]
    @Published public private(set) var pairingSession: PairingSession?
    @Published public private(set) var trustedDevices: [TrustedDevice] = []
    @Published public private(set) var models: [ModelInfo] = []
    @Published public private(set) var modelResidency: CompanionModelResidencyStatus = .inactive
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
        self.providerStatuses = Self.initialProviderStatuses(for: backend)
        self.peerServer = peerServer
        self.advertiser = advertiser
        self.macDeviceID = Self.loadOrCreateMacDeviceID()
        self.discoveryRouteToken = Self.loadOrCreateDiscoveryRouteToken()
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
        configureResidencyEventsIfAvailable()
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
        transportState = Self.transportStatus(from: peerServer.status)
        switch transportState.state {
        case .advertising:
            advertiser.start(port: Int32(port), metadata: runtimeAdvertisementMetadata)
            transportStatus = "Advertising _aetherlink._tcp.local. on port \(port)"
            log("Companion started")
        case .failed:
            advertiser.stop()
            let message = transportState.failureMessage ?? "Runtime listener failed"
            transportStatus = "Runtime listener failed: \(message)"
            log(transportStatus)
        case .stopped:
            advertiser.stop()
            transportStatus = "Stopped"
            log("Companion stopped")
        }
        Task {
            await refreshTrustedDevices()
            await refreshBackendStatus()
        }
    }

    public func stop() {
        peerServer.stop()
        advertiser.stop()
        transportState = .stopped
        transportStatus = "Stopped"
        log("Companion stopped")
    }

    public func refreshBackendStatus() async {
        if let aggregate = backend as? AggregatingLlmBackend {
            let statuses = await aggregate.providerHealth()
            let sortedStatuses = statuses.sorted { $0.key.rawValue < $1.key.rawValue }
            providerStatuses = sortedStatuses.map { provider, status in
                CompanionProviderStatus.from(provider: provider, status: status)
            }
            backendStatus = Self.backendStatusString(for: sortedStatuses)
            log(backendStatus)
            return
        }

        let status = await backend.healthCheck()
        providerStatuses = [CompanionProviderStatus.from(provider: backend.provider, status: status)]
        switch status {
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

    public func refreshModelResidencyStatus() {
        guard let aggregate = backend as? AggregatingLlmBackend else {
            modelResidency = .unsupported
            return
        }
        modelResidency = CompanionModelResidencyStatus(
            snapshot: aggregate.modelResidencySnapshot(),
            lastEvent: modelResidency.lastEvent
        )
    }

    public func beginPairing() {
        pairingSession = pairingCoordinator.beginPairing(
            macDeviceID: macDeviceID,
            fingerprint: macFingerprint,
            routeToken: discoveryRouteToken,
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

    private func configureResidencyEventsIfAvailable() {
        guard let aggregate = backend as? AggregatingLlmBackend else {
            modelResidency = .unsupported
            return
        }
        modelResidency = CompanionModelResidencyStatus(
            snapshot: aggregate.modelResidencySnapshot(),
            lastEvent: nil
        )
        aggregate.setResidencyEventHandler { [weak self] event in
            Task { @MainActor in
                self?.handleResidencyEvent(event)
            }
        }
    }

    private func handleResidencyEvent(_ event: RuntimeModelResidencyEvent) {
        if let aggregate = backend as? AggregatingLlmBackend {
            modelResidency = CompanionModelResidencyStatus(
                snapshot: aggregate.modelResidencySnapshot(),
                lastEvent: event.logMessage
            )
        }
        log(event.logMessage)
    }

    private var macFingerprint: String {
        "dev-\(macDeviceID)"
    }

    private let discoveryRouteToken: String

    private var runtimeAdvertisementMetadata: RuntimeAdvertisementMetadata {
        RuntimeAdvertisementMetadata(
            routeToken: discoveryRouteToken
        )
    }

    private static func initialProviderStatuses(for backend: any LlmBackend) -> [CompanionProviderStatus] {
        if backend is AggregatingLlmBackend {
            return [
                .notChecked(provider: .ollama),
                .notChecked(provider: .lmStudio)
            ]
        }
        return [.notChecked(provider: backend.provider)]
    }

    private static func backendStatusString(for statuses: [(key: ModelProvider, value: BackendStatus)]) -> String {
        statuses
            .map { provider, status in
                switch status {
                case .available:
                    return "\(provider.displayName) available"
                case .unavailable(let error):
                    return "\(provider.displayName) unavailable: \(error.message)"
                }
            }
            .joined(separator: " | ")
    }

    private static func transportStatus(from status: PeerServerStatus) -> CompanionTransportStatus {
        switch status {
        case .stopped:
            return .stopped
        case .listening(let port):
            return .advertising(serviceName: "_aetherlink._tcp.local.", port: port)
        case .failed(let message):
            return .failed(message)
        }
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

    private static func loadOrCreateDiscoveryRouteToken() -> String {
        let key = "aetherlink.discovery_route_token"
        if let existing = UserDefaults.standard.string(forKey: key), !existing.isEmpty {
            return existing
        }
        let token = UUID().uuidString
        UserDefaults.standard.set(token, forKey: key)
        return token
    }

    private static func primaryLocalIPv4Address() -> String {
        Host.current().addresses.first { address in
            address.contains(".")
                && !address.hasPrefix("127.")
                && !address.hasPrefix("169.254.")
        } ?? "127.0.0.1"
    }
}

public struct CompanionModelResidencyStatus: Equatable, Sendable {
    public var activeProvider: ModelProvider?
    public var activeModelID: String?
    public var inFlightGenerations: Int
    public var idleUnloadDelaySeconds: Int
    public var lastEvent: String?
    public var supported: Bool

    public static let inactive = CompanionModelResidencyStatus(
        activeProvider: nil,
        activeModelID: nil,
        inFlightGenerations: 0,
        idleUnloadDelaySeconds: 600,
        lastEvent: nil,
        supported: true
    )

    public static let unsupported = CompanionModelResidencyStatus(
        activeProvider: nil,
        activeModelID: nil,
        inFlightGenerations: 0,
        idleUnloadDelaySeconds: 0,
        lastEvent: nil,
        supported: false
    )

    public init(
        activeProvider: ModelProvider?,
        activeModelID: String?,
        inFlightGenerations: Int,
        idleUnloadDelaySeconds: Int,
        lastEvent: String?,
        supported: Bool
    ) {
        self.activeProvider = activeProvider
        self.activeModelID = activeModelID
        self.inFlightGenerations = inFlightGenerations
        self.idleUnloadDelaySeconds = idleUnloadDelaySeconds
        self.lastEvent = lastEvent
        self.supported = supported
    }

    public init(snapshot: RuntimeModelResidencySnapshot, lastEvent: String?) {
        self.init(
            activeProvider: snapshot.activeProvider,
            activeModelID: snapshot.activeModelID,
            inFlightGenerations: snapshot.inFlightGenerations,
            idleUnloadDelaySeconds: snapshot.idleUnloadDelaySeconds,
            lastEvent: lastEvent,
            supported: true
        )
    }
}

private extension RuntimeModelResidencyEvent {
    var logMessage: String {
        switch self {
        case .activeModelChanged(let provider, let modelID):
            return "Model residency active: \(provider.displayName) \(modelID)"
        case .unloadRequested(let provider, let modelID, let reason):
            return "Model unload requested: \(provider.displayName) \(modelID) (\(reason.logLabel))"
        case .unloadSucceeded(let provider, let modelID, let reason):
            return "Model unloaded: \(provider.displayName) \(modelID) (\(reason.logLabel))"
        case .unloadFailed(let provider, let modelID, let reason, let message):
            return "Model unload failed: \(provider.displayName) \(modelID) (\(reason.logLabel)): \(message)"
        }
    }
}

private extension RuntimeModelResidencyUnloadReason {
    var logLabel: String {
        switch self {
        case .modelSwitch:
            return "model switch"
        case .idleTimeout:
            return "idle timeout"
        }
    }
}
