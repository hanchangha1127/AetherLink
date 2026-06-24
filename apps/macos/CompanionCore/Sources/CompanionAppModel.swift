import Darwin
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

public struct CompanionDevelopmentRelaySettings: Equatable, Sendable {
    public enum HostReachabilityWarning: String, Equatable, Sendable {
        case loopback
        case privateNetwork
        case localName
    }

    public var isEnabled: Bool
    public var host: String
    public var port: UInt16
    public var relayID: String
    public var relaySecret: String?
    public var isEnvironmentOverride: Bool

    public init(
        isEnabled: Bool,
        host: String = "",
        port: UInt16 = 43171,
        relayID: String = "",
        relaySecret: String? = nil,
        isEnvironmentOverride: Bool = false
    ) {
        self.isEnabled = isEnabled
        self.host = host
        self.port = port
        self.relayID = relayID
        self.relaySecret = relaySecret
        self.isEnvironmentOverride = isEnvironmentOverride
    }

    public static let disabled = CompanionDevelopmentRelaySettings(isEnabled: false)

    public var endpointLabel: String? {
        guard isEnabled, !host.isEmpty else { return nil }
        return "\(host):\(port)"
    }

    public var hostReachabilityWarning: HostReachabilityWarning? {
        Self.hostReachabilityWarning(for: host)
    }

    public var frameEncryptionEnabled: Bool {
        relaySecret?.takeIfNotEmpty() != nil
    }

    public var relayConfiguration: RelayPeerConfiguration? {
        guard isEnabled, !host.isEmpty, !relayID.isEmpty else { return nil }
        return RelayPeerConfiguration(
            host: host,
            port: port,
            relayID: relayID,
            relaySecret: relaySecret?.takeIfNotEmpty()
        )
    }

    public static func hostReachabilityWarning(for host: String) -> HostReachabilityWarning? {
        let normalizedHost = host
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        guard !normalizedHost.isEmpty else { return nil }
        if normalizedHost == "localhost" ||
            normalizedHost == "::1" ||
            normalizedHost.hasPrefix("127.") {
            return .loopback
        }
        if normalizedHost.hasSuffix(".local") {
            return .localName
        }
        if normalizedHost.hasPrefix("10.") ||
            normalizedHost.hasPrefix("192.168.") {
            return .privateNetwork
        }
        let octets = normalizedHost.split(separator: ".")
        if octets.count == 4,
           octets[0] == "172",
           let secondOctet = Int(octets[1]),
           (16...31).contains(secondOctet) {
            return .privateNetwork
        }
        return nil
    }
}

public struct CompanionDevelopmentRelayStatus: Equatable, Sendable {
    public var status: RelayPeerStatus
    public var endpoint: String?

    public init(status: RelayPeerStatus, endpoint: String? = nil) {
        self.status = status
        self.endpoint = endpoint
    }

    public static let stopped = CompanionDevelopmentRelayStatus(status: .stopped)
}

@MainActor
public final class CompanionAppModel: ObservableObject {
    @Published public private(set) var backendStatus = "Not checked"
    @Published public private(set) var transportStatus = "Stopped"
    @Published public private(set) var transportState: CompanionTransportStatus = .stopped
    @Published public private(set) var providerStatuses: [CompanionProviderStatus]
    @Published public private(set) var developmentRelaySettings: CompanionDevelopmentRelaySettings = .disabled
    @Published public private(set) var developmentRelayConnectionStatus: CompanionDevelopmentRelayStatus = .stopped
    @Published public private(set) var pairingSession: PairingSession?
    @Published public private(set) var trustedDevices: [TrustedDevice] = []
    @Published public private(set) var models: [ModelInfo] = []
    @Published public private(set) var modelResidency: CompanionModelResidencyStatus = .inactive
    @Published public private(set) var logs: [String] = []

    private let backend: any LlmBackend
    private var runtimeRouter: LocalRuntimeMessageRouter!
    private let pairingCoordinator = PairingCoordinator()
    private let trustedDeviceStore = TrustedDeviceStore()
    private let userDefaults: UserDefaults
    private let peerServer: any RuntimeTransport
    private let advertiser: any RuntimeAdvertiser
    private let relayClient: any RelayPeerTransport
    private let runtimeRouteHostProvider: () -> String?
    private var relayConfiguration: RelayPeerConfiguration?
    private let macDeviceID: String
    private let runtimeIdentityKey: RuntimeIdentityKey
    private let runtimeIdentityWarning: String?
    private var runtimePort: UInt16 = 43170
    private var isRuntimeStarted = false

    public var hasDevelopmentRelayRoute: Bool {
        relayConfiguration != nil
    }

    public var isDevelopmentRelayQRCodeReady: Bool {
        guard developmentRelaySettings.isEnabled, relayConfiguration != nil else { return false }
        if let warning = developmentRelaySettings.hostReachabilityWarning,
           !developmentRelaySettings.isEnvironmentOverride,
           warning != .privateNetwork {
            return false
        }
        return true
    }

    public var shouldIncludeDevelopmentRelayInPairingQRCode: Bool {
        relayConfiguration != nil && isDevelopmentRelayQRCodeReady
    }

    public var developmentRelayEndpoint: String? {
        developmentRelaySettings.endpointLabel
    }

    public var relayFrameEncryptionEnabled: Bool {
        developmentRelaySettings.frameEncryptionEnabled
    }

    public init(
        backend: any LlmBackend = AggregatingLlmBackend(ollama: OllamaBackend(), lmStudio: LMStudioBackend()),
        peerServer: any RuntimeTransport = LocalPeerServer(),
        advertiser: any RuntimeAdvertiser = BonjourAdvertiser(),
        relayClient: any RelayPeerTransport = RelayPeerClient(),
        userDefaults: UserDefaults = .standard,
        runtimeRouteHostProvider: (() -> String?)? = nil
    ) {
        self.backend = backend
        self.providerStatuses = Self.initialProviderStatuses(for: backend)
        self.peerServer = peerServer
        self.advertiser = advertiser
        self.relayClient = relayClient
        self.userDefaults = userDefaults
        self.runtimeRouteHostProvider = runtimeRouteHostProvider ?? Self.defaultRuntimeRouteHost
        let macDeviceID = Self.loadOrCreateMacDeviceID(defaults: userDefaults)
        let runtimeIdentity = Self.loadOrCreateRuntimeIdentityKey(deviceID: macDeviceID)
        self.macDeviceID = macDeviceID
        self.runtimeIdentityKey = runtimeIdentity.key
        self.runtimeIdentityWarning = runtimeIdentity.warning
        self.discoveryRouteToken = Self.loadOrCreateDiscoveryRouteToken(defaults: userDefaults)
        let relaySettings = Self.loadDevelopmentRelaySettings(
            routeToken: discoveryRouteToken,
            defaults: userDefaults
        )
        self.developmentRelaySettings = relaySettings
        self.relayConfiguration = relaySettings.relayConfiguration
        self.developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
            status: .stopped,
            endpoint: relaySettings.endpointLabel
        )
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
        if let runtimeIdentityWarning {
            log(runtimeIdentityWarning)
        }
    }

    public func start(port: UInt16 = 43170) {
        runtimePort = port
        isRuntimeStarted = true
        let router = runtimeRouter!
        peerServer.start(port: port) { [router, weak self] envelope, sink in
            Task { @MainActor in
                self?.log("Received \(envelope.type)")
            }
            router.handle(envelope, sink: sink)
        }
        startRelayClientIfConfigured()
        transportState = Self.transportStatus(from: peerServer.status)
        refreshTransportStatusText()
        switch transportState.state {
        case .advertising:
            advertiser.start(port: Int32(port), metadata: runtimeAdvertisementMetadata)
            log("AetherLink runtime started")
            if let relayConfiguration {
                log("Relay route enabled: \(relayConfiguration.host):\(relayConfiguration.port)")
            }
        case .failed:
            advertiser.stop()
            let message = transportState.failureMessage ?? "Runtime listener failed"
            transportStatus = "Runtime listener failed: \(message)"
            log(transportStatus)
        case .stopped:
            advertiser.stop()
            transportStatus = "Stopped"
            log("AetherLink runtime stopped")
        }
        Task {
            await refreshTrustedDevices()
            await refreshBackendStatus()
        }
    }

    public func stop() {
        isRuntimeStarted = false
        peerServer.stop()
        advertiser.stop()
        relayClient.stop()
        transportState = .stopped
        transportStatus = "Stopped"
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
            status: .stopped,
            endpoint: developmentRelaySettings.endpointLabel
        )
        log("AetherLink runtime stopped")
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
        if !isRuntimeStarted {
            start(port: runtimePort)
        }
        let pairingRelayConfiguration = shouldIncludeDevelopmentRelayInPairingQRCode ? relayConfiguration : nil
        let localRouteHost = pairingRelayConfiguration == nil ? localPairingRouteHost : nil
        let relayRouteLease = pairingRelayConfiguration.map { _ in Self.newRelayRouteLease() }
        pairingSession = pairingCoordinator.beginPairing(
            macDeviceID: macDeviceID,
            fingerprint: macFingerprint,
            runtimePublicKeyBase64: macPublicKeyBase64,
            routeToken: discoveryRouteToken,
            host: localRouteHost,
            port: localRouteHost == nil ? nil : Int(runtimePort),
            relayHost: pairingRelayConfiguration?.host,
            relayPort: pairingRelayConfiguration.map { Int($0.port) },
            relayID: pairingRelayConfiguration?.relayID,
            relaySecret: pairingRelayConfiguration?.relaySecret,
            relayExpiresAtEpochMillis: relayRouteLease?.expiresAtEpochMillis,
            relayNonce: relayRouteLease?.nonce
        )
        log("Pairing code generated")
    }

    public func configureDevelopmentRelay(
        host: String,
        port: UInt16,
        relaySecret: String? = nil
    ) {
        let trimmedHost = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedHost.isEmpty else {
            clearDevelopmentRelay()
            return
        }

        let secret = relaySecret?.takeIfNotEmpty() ?? Self.generateRelaySecret()
        let settings = CompanionDevelopmentRelaySettings(
            isEnabled: true,
            host: trimmedHost,
            port: port,
            relayID: discoveryRouteToken,
            relaySecret: secret,
            isEnvironmentOverride: false
        )
        Self.saveDevelopmentRelaySettings(settings, defaults: userDefaults)
        developmentRelaySettings = settings
        relayConfiguration = settings.relayConfiguration
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
            status: .stopped,
            endpoint: settings.endpointLabel
        )
        restartRelayClientIfRunning()
        refreshTransportStatusText()
        log("Relay route configured: \(trimmedHost):\(port)")
    }

    public func clearDevelopmentRelay() {
        Self.clearSavedDevelopmentRelaySettings(defaults: userDefaults)
        developmentRelaySettings = .disabled
        relayConfiguration = nil
        relayClient.stop()
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(status: .stopped)
        refreshTransportStatusText()
        log("Relay route disabled")
    }

    public func regenerateDevelopmentRelaySecret() {
        guard developmentRelaySettings.isEnabled else { return }
        let settings = CompanionDevelopmentRelaySettings(
            isEnabled: true,
            host: developmentRelaySettings.host,
            port: developmentRelaySettings.port,
            relayID: discoveryRouteToken,
            relaySecret: Self.generateRelaySecret(),
            isEnvironmentOverride: false
        )
        Self.saveDevelopmentRelaySettings(settings, defaults: userDefaults)
        developmentRelaySettings = settings
        relayConfiguration = settings.relayConfiguration
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
            status: .stopped,
            endpoint: settings.endpointLabel
        )
        restartRelayClientIfRunning()
        refreshTransportStatusText()
        log("Relay frame secret regenerated")
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

    private func startRelayClientIfConfigured() {
        guard let relayConfiguration else { return }
        let router = runtimeRouter!
        let endpoint = "\(relayConfiguration.host):\(relayConfiguration.port)"
        relayClient.start(
            configuration: relayConfiguration,
            onStatusChange: { [weak self] status in
                Task { @MainActor in
                    self?.handleRelayStatus(status, endpoint: endpoint)
                }
            }
        ) { [router, weak self] envelope, sink in
            Task { @MainActor in
                self?.log("Relay received \(envelope.type)")
            }
            router.handle(envelope, sink: sink)
        }
    }

    private func restartRelayClientIfRunning() {
        relayClient.stop()
        guard isRuntimeStarted else { return }
        startRelayClientIfConfigured()
    }

    private func handleRelayStatus(_ status: RelayPeerStatus, endpoint: String) {
        guard relayConfiguration != nil, developmentRelaySettings.endpointLabel == endpoint else {
            if case .stopped = status {
                developmentRelayConnectionStatus = .stopped
            }
            return
        }
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(status: status, endpoint: endpoint)
        refreshTransportStatusText()
        switch status {
        case .ready:
            log("Relay route ready: \(endpoint)")
        case .failed(let message):
            log("Relay route failed: \(endpoint): \(message)")
        case .reconnecting(let message):
            if let message {
                log("Relay route reconnecting: \(endpoint): \(message)")
            } else {
                log("Relay route reconnecting: \(endpoint)")
            }
        default:
            break
        }
    }

    private func refreshTransportStatusText() {
        switch transportState.state {
        case .advertising:
            if let relayConfiguration {
                let endpoint = "\(relayConfiguration.host):\(relayConfiguration.port)"
                switch developmentRelayConnectionStatus.status {
                case .ready:
                    transportStatus = "Advertising locally and relay ready \(endpoint)"
                case .failed(let message):
                    transportStatus = "Advertising locally; relay failed \(endpoint): \(message)"
                case .connecting, .waitingForPeer:
                    transportStatus = "Advertising locally; relay connecting \(endpoint)"
                case .reconnecting:
                    transportStatus = "Advertising locally; relay reconnecting \(endpoint)"
                case .stopped:
                    transportStatus = "Advertising locally and relay configured \(endpoint)"
                }
            } else {
                transportStatus = "Advertising _aetherlink._tcp.local. on port \(runtimePort)"
            }
        case .failed:
            transportStatus = "Runtime listener failed: \(transportState.failureMessage ?? "unknown error")"
        case .stopped:
            transportStatus = "Stopped"
        }
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
        runtimeIdentityKey.fingerprint
    }

    private var macPublicKeyBase64: String? {
        runtimeIdentityKey.publicKeyBase64.takeIfNotEmpty()
    }

    private var localPairingRouteHost: String? {
        guard transportState.state == .advertising else { return nil }
        return runtimeRouteHostProvider()
    }

    private let discoveryRouteToken: String

    private var runtimeAdvertisementMetadata: RuntimeAdvertisementMetadata {
        RuntimeAdvertisementMetadata(
            routeToken: discoveryRouteToken,
            deviceID: macDeviceID,
            fingerprint: macFingerprint
        )
    }

    private static func loadDevelopmentRelaySettings(
        routeToken: String,
        defaults: UserDefaults
    ) -> CompanionDevelopmentRelaySettings {
        let environment = ProcessInfo.processInfo.environment
        if let host = environment["AETHERLINK_RELAY_HOST"]?.takeIfNotEmpty() {
            let port = UInt16(environment["AETHERLINK_RELAY_PORT"] ?? "") ?? 43171
            let relayID = environment["AETHERLINK_RELAY_ID"]?.takeIfNotEmpty() ?? routeToken
            let relaySecret = environment["AETHERLINK_RELAY_SECRET"]?.takeIfNotEmpty()
            return CompanionDevelopmentRelaySettings(
                isEnabled: true,
                host: host,
                port: port,
                relayID: relayID,
                relaySecret: relaySecret,
                isEnvironmentOverride: true
            )
        }

        guard let host = defaults.string(forKey: RelayDefaults.host)?.takeIfNotEmpty() else {
            return .disabled
        }
        let storedPort = defaults.integer(forKey: RelayDefaults.port)
        let port = UInt16(exactly: storedPort).flatMap { $0 == 0 ? nil : $0 } ?? 43171
        let relaySecret = defaults.string(forKey: RelayDefaults.secret)?.takeIfNotEmpty()
        return CompanionDevelopmentRelaySettings(
            isEnabled: true,
            host: host,
            port: port,
            relayID: routeToken,
            relaySecret: relaySecret,
            isEnvironmentOverride: false
        )
    }

    private static func saveDevelopmentRelaySettings(
        _ settings: CompanionDevelopmentRelaySettings,
        defaults: UserDefaults
    ) {
        defaults.set(settings.host, forKey: RelayDefaults.host)
        defaults.set(Int(settings.port), forKey: RelayDefaults.port)
        if let relaySecret = settings.relaySecret?.takeIfNotEmpty() {
            defaults.set(relaySecret, forKey: RelayDefaults.secret)
        } else {
            defaults.removeObject(forKey: RelayDefaults.secret)
        }
    }

    private static func clearSavedDevelopmentRelaySettings(defaults: UserDefaults) {
        defaults.removeObject(forKey: RelayDefaults.host)
        defaults.removeObject(forKey: RelayDefaults.port)
        defaults.removeObject(forKey: RelayDefaults.secret)
    }

    private static func generateRelaySecret() -> String {
        let bytes = (0..<32).map { _ in UInt8.random(in: 0...255) }
        return Data(bytes).base64EncodedString()
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

    private enum RelayDefaults {
        static let host = "aetherlink.relay.host"
        static let port = "aetherlink.relay.port"
        static let secret = "aetherlink.relay.secret"
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

    private static func loadOrCreateMacDeviceID(defaults: UserDefaults) -> String {
        let key = "aetherlink.mac_device_id"
        if let existing = defaults.string(forKey: key), !existing.isEmpty {
            return existing
        }
        let deviceID = UUID().uuidString
        defaults.set(deviceID, forKey: key)
        return deviceID
    }

    private static func loadOrCreateDiscoveryRouteToken(defaults: UserDefaults) -> String {
        let key = "aetherlink.discovery_route_token"
        if let existing = defaults.string(forKey: key), !existing.isEmpty {
            return existing
        }
        let token = UUID().uuidString
        defaults.set(token, forKey: key)
        return token
    }

    private static func loadOrCreateRuntimeIdentityKey(deviceID: String) -> (key: RuntimeIdentityKey, warning: String?) {
        do {
            return (try RuntimeIdentityKeyStore().loadOrCreate(), nil)
        } catch {
            return (
                RuntimeIdentityKey(publicKeyBase64: "", fingerprint: "dev-\(deviceID)"),
                "Runtime identity Keychain unavailable; using development fingerprint fallback."
            )
        }
    }

    nonisolated private static func defaultRuntimeRouteHost() -> String? {
        var interfaces: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&interfaces) == 0, let firstInterface = interfaces else {
            return nil
        }
        defer { freeifaddrs(interfaces) }

        var candidates: [(name: String, address: String)] = []
        var cursor: UnsafeMutablePointer<ifaddrs>? = firstInterface
        while let interface = cursor {
            defer { cursor = interface.pointee.ifa_next }
            let flags = Int32(interface.pointee.ifa_flags)
            guard (flags & IFF_UP) != 0, (flags & IFF_LOOPBACK) == 0 else { continue }
            guard let address = interface.pointee.ifa_addr, address.pointee.sa_family == UInt8(AF_INET) else { continue }

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
            candidates.append((String(cString: interface.pointee.ifa_name), addressString))
        }

        let preferredPrefixes = ["en", "bridge", "utun"]
        return candidates.first { candidate in
            preferredPrefixes.contains { candidate.name.hasPrefix($0) }
        }?.address ?? candidates.first?.address
    }

    nonisolated private static func isUsablePairingAddress(_ address: String) -> Bool {
        guard !address.isEmpty else { return false }
        if address == "0.0.0.0" || address == "255.255.255.255" { return false }
        if address.hasPrefix("127.") || address.hasPrefix("169.254.") { return false }
        return true
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

private extension String {
    func takeIfNotEmpty() -> String? {
        isEmpty ? nil : self
    }
}
