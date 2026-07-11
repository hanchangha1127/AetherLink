import Darwin
import enum BridgeProtocol.PairedRelayAllocationAuthorization
import protocol BridgeProtocol.PairedRelayAllocationRuntimeSigning
import struct BridgeProtocol.RelayAllocationIdentityChallenge
import protocol BridgeProtocol.RelayIdentityAuthorizationSigning
import struct BridgeProtocol.RelayRuntimeIdentity
import Foundation
import CryptoKit
import LMStudioBackend
import OllamaBackend
import Pairing
import Security
import Transport
import TrustedDevices

private let pairingQRCodeLeaseRenewalMarginSeconds: TimeInterval = 360

private func generateRuntimeLocalRelaySecret() -> String {
    var bytes = [UInt8](repeating: 0, count: 32)
    let status = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
    precondition(status == errSecSuccess, "Unable to generate a runtime-local relay secret")
    return Data(bytes).base64EncodedString()
}

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

public struct CompanionRuntimeDataSummary: Equatable, Sendable {
    public var activeChatSessionCount: Int
    public var archivedChatSessionCount: Int
    public var enabledMemoryCount: Int
    public var pausedMemoryCount: Int
    public var lastRefreshedAt: Date?
    public var errorMessage: String?

    public init(
        activeChatSessionCount: Int = 0,
        archivedChatSessionCount: Int = 0,
        enabledMemoryCount: Int = 0,
        pausedMemoryCount: Int = 0,
        lastRefreshedAt: Date? = nil,
        errorMessage: String? = nil
    ) {
        self.activeChatSessionCount = activeChatSessionCount
        self.archivedChatSessionCount = archivedChatSessionCount
        self.enabledMemoryCount = enabledMemoryCount
        self.pausedMemoryCount = pausedMemoryCount
        self.lastRefreshedAt = lastRefreshedAt
        self.errorMessage = errorMessage
    }

    public var hasError: Bool {
        errorMessage?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false
    }
}

public enum CompanionRelayConfigurationResult: Equatable, Sendable {
    case disabled
    case savedStatic(endpoint: String)
    case allocated(endpoint: String)
    case allocationFailed(endpoint: String, message: String)
}

public struct CompanionDevelopmentRelaySettings: Equatable, Sendable {
    public enum HostReachabilityWarning: String, Equatable, Sendable {
        case invalidFormat
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
    public var allowsPrivateOverlay: Bool

    public init(
        isEnabled: Bool,
        host: String = "",
        port: UInt16 = 43171,
        relayID: String = "",
        relaySecret: String? = nil,
        isEnvironmentOverride: Bool = false,
        allowsPrivateOverlay: Bool = false
    ) {
        self.isEnabled = isEnabled
        self.host = host
        self.port = port
        self.relayID = relayID
        self.relaySecret = relaySecret
        self.isEnvironmentOverride = isEnvironmentOverride
        self.allowsPrivateOverlay = allowsPrivateOverlay
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

    public var isEligibleForRemoteQRCode: Bool {
        hostReachabilityWarning?.blocksRemoteQRCode(allowsPrivateOverlay: allowsPrivateOverlay) != true
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
        var normalizedHost = host
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
            .lowercased()
        while normalizedHost.hasSuffix(".") {
            normalizedHost.removeLast()
        }
        guard !normalizedHost.isEmpty else { return nil }
        if normalizedHost.contains("://") ||
            normalizedHost.contains("/") ||
            normalizedHost.contains("?") ||
            normalizedHost.contains("#") ||
            normalizedHost.contains("@") ||
            isHostPortInput(normalizedHost) {
            return .invalidFormat
        }
        if normalizedHost == "localhost" ||
            normalizedHost == "::1" ||
            normalizedHost == "0:0:0:0:0:0:0:1" ||
            normalizedHost.hasPrefix("127.") {
            return .loopback
        }
        if normalizedHost == "0.0.0.0" ||
            normalizedHost == "::" ||
            normalizedHost == "0:0:0:0:0:0:0:0" ||
            normalizedHost == "255.255.255.255" {
            return .privateNetwork
        }
        if normalizedHost.hasSuffix(".local") {
            return .localName
        }
        if normalizedHost.isPrivateOrLocalIPv4RelayLiteral() ||
            normalizedHost.isPrivateOrLocalIPv6RelayLiteral() {
            return .privateNetwork
        }
        return nil
    }

    private static func isHostPortInput(_ host: String) -> Bool {
        guard !host.hasPrefix("["),
              host.filter({ $0 == ":" }).count == 1,
              let colon = host.lastIndex(of: ":")
        else {
            return false
        }
        let suffix = host[host.index(after: colon)...]
        return !suffix.isEmpty && suffix.allSatisfy(\.isNumber)
    }
}

public struct CompanionBootstrapRelaySettings: Equatable, Sendable {
    public var isEnabled: Bool
    public var endpoints: String
    public var allocationToken: String?
    public var allowsPrivateOverlay: Bool

    public init(
        isEnabled: Bool,
        endpoints: String = "",
        allocationToken: String? = nil,
        allowsPrivateOverlay: Bool = false
    ) {
        self.isEnabled = isEnabled
        self.endpoints = endpoints
        self.allocationToken = allocationToken?.takeIfNotEmpty()
        self.allowsPrivateOverlay = allowsPrivateOverlay
    }

    public static let disabled = CompanionBootstrapRelaySettings(isEnabled: false)

    public var endpointLabel: String? {
        guard isEnabled, !endpoints.isEmpty else { return nil }
        return endpoints
    }
}

public protocol CompanionRelaySecretStoring: Sendable {
    func saveSecret(_ secret: String, for handle: String)
    func readSecret(for handle: String) -> String?
    func removeSecret(for handle: String)
}

public final class KeychainCompanionRelaySecretStore: CompanionRelaySecretStoring, @unchecked Sendable {
    private let service: String

    public init(service: String = "dev.aetherlink.relay-secret-store") {
        self.service = service
    }

    public func saveSecret(_ secret: String, for handle: String) {
        removeSecret(for: handle)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: handle,
            kSecValueData as String: Data(secret.utf8)
        ]
        SecItemAdd(query as CFDictionary, nil)
    }

    public func readSecret(for handle: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: handle,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data
        else {
            return nil
        }
        return String(data: data, encoding: .utf8)?.takeIfNotEmpty()
    }

    public func removeSecret(for handle: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: handle
        ]
        SecItemDelete(query as CFDictionary)
    }
}

private extension String {
    func isPrivateOrLocalIPv4RelayLiteral() -> Bool {
        let octets = split(separator: ".", omittingEmptySubsequences: false)
        guard octets.count == 4 else { return false }
        let values: [Int] = octets.compactMap { part in
            guard !part.isEmpty, part.allSatisfy(\.isNumber), let value = Int(part), (0...255).contains(value) else {
                return nil
            }
            return value
        }
        guard values.count == 4 else { return false }
        let first = values[0]
        let second = values[1]
        return first == 0 ||
            first == 10 ||
            first == 127 ||
            first >= 224 ||
            (first == 100 && (64...127).contains(second)) ||
            (first == 169 && second == 254) ||
            (first == 172 && (16...31).contains(second)) ||
            (first == 192 && second == 168)
    }

    func isPrivateOrLocalIPv6RelayLiteral() -> Bool {
        guard contains(":") else { return false }
        let normalized = lowercased()
        return normalized == "::" ||
            normalized == "::1" ||
            normalized == "0:0:0:0:0:0:0:0" ||
            normalized == "0:0:0:0:0:0:0:1" ||
            normalized.hasPrefix("fe80:") ||
            normalized.hasPrefix("fc") ||
            normalized.hasPrefix("fd")
    }
}

private extension CompanionDevelopmentRelaySettings.HostReachabilityWarning {
    func blocksRemoteQRCode(allowsPrivateOverlay: Bool) -> Bool {
        switch self {
        case .invalidFormat, .loopback, .localName:
            return true
        case .privateNetwork:
            return !allowsPrivateOverlay
        }
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

public struct CompanionRemoteRoutePreparationIssue: Equatable, Sendable {
    public enum Kind: String, Equatable, Sendable {
        case automaticPreparationUnavailable
        case automaticPreparationRejected
        case automaticPreparationFailed
        case routeLeaseRefreshRejected
        case routeLeaseRefreshFailed
        case routeLeaseSecretMissing
        case relayConnectionFailed
    }

    public var kind: Kind
    public var endpoint: String?
    public var message: String

    public init(kind: Kind, endpoint: String? = nil, message: String) {
        self.kind = kind
        self.endpoint = endpoint
        self.message = message
    }
}

public enum CompanionPairingRoutePolicy: Equatable, Sendable {
    case remoteRequired
    case allowLocalDiagnostic
}

public struct CompanionRemoteRelayRouteAllocation: Equatable, Sendable {
    public var configuration: RelayPeerConfiguration
    public var lease: CompanionRemoteRouteLease?

    public init(
        configuration: RelayPeerConfiguration,
        lease: CompanionRemoteRouteLease? = nil
    ) {
        self.configuration = configuration.withRelayNonce(configuration.relayNonce ?? lease?.nonce)
        self.lease = lease
    }
}

public struct CompanionRemoteRouteLease: Equatable, Sendable {
    public var expiresAtEpochMillis: Int64
    public var nonce: String
    public var ticketGeneration: Int64?

    public init(
        expiresAtEpochMillis: Int64,
        nonce: String,
        ticketGeneration: Int64? = nil
    ) {
        precondition(expiresAtEpochMillis > 0, "Remote route lease expiration must be positive")
        precondition(!nonce.isEmpty, "Remote route lease nonce must not be empty")
        precondition(
            ticketGeneration == nil || ticketGeneration! > 0,
            "Remote route lease ticket generation must be positive"
        )
        self.expiresAtEpochMillis = expiresAtEpochMillis
        self.nonce = nonce
        self.ticketGeneration = ticketGeneration
    }

    public func isExpired(at date: Date = Date(), renewalMarginSeconds: TimeInterval = 0) -> Bool {
        let thresholdMillis = Int64((date.addingTimeInterval(renewalMarginSeconds).timeIntervalSince1970 * 1000).rounded())
        return expiresAtEpochMillis <= thresholdMillis
    }

    public func isAdvancingReplacement(of existing: CompanionRemoteRouteLease) -> Bool {
        let generationAdvances: Bool
        switch (existing.ticketGeneration, ticketGeneration) {
        case (nil, nil), (nil, .some):
            generationAdvances = true
        case (.some, nil):
            generationAdvances = false
        case let (.some(current), .some(next)):
            generationAdvances = current < Int64.max && next == current + 1
        }
        return expiresAtEpochMillis > existing.expiresAtEpochMillis &&
            nonce != existing.nonce &&
            generationAdvances
    }
}

public protocol CompanionRemoteRelayRouteAllocating: Sendable {
    var canAllocateRemoteRelayRoute: Bool { get }

    func allocateRemoteRelayRoute(
        runtimeDeviceID: String,
        routeToken: String,
        preferredRelaySecret: String?,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning
    ) throws -> CompanionRemoteRelayRouteAllocation?
}

public extension CompanionRemoteRelayRouteAllocating {
    var canAllocateRemoteRelayRoute: Bool { false }
}

public struct EnvironmentRemoteRelayRouteAllocator: CompanionRemoteRelayRouteAllocating {
    public var environment: [String: String]
    public var storedBootstrapRelaySettings: CompanionBootstrapRelaySettings
    private let relayServiceAllocator: any RelayServiceRouteAllocating
    private static let defaultBootstrapRelayPort: UInt16 = 43171

    public init(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        storedBootstrapRelaySettings: CompanionBootstrapRelaySettings = .disabled,
        relayServiceAllocator: any RelayServiceRouteAllocating = TCPRelayServiceRouteAllocator()
    ) {
        self.environment = environment
        self.storedBootstrapRelaySettings = storedBootstrapRelaySettings
        self.relayServiceAllocator = relayServiceAllocator
    }

    public var canAllocateRemoteRelayRoute: Bool {
        let defaultPort = Self.bootstrapRelayDefaultPort(from: environment)
        guard !bootstrapRelayEndpoints(defaultPort: defaultPort).isEmpty else {
            return false
        }
        let explicitRelayID = environment["AETHERLINK_BOOTSTRAP_RELAY_ID"]?.takeIfNotEmpty()
        let explicitRelaySecret = environment["AETHERLINK_BOOTSTRAP_RELAY_SECRET"]?.takeIfNotEmpty()
        if explicitRelayID != nil || explicitRelaySecret != nil {
            return explicitRelayID != nil && explicitRelaySecret != nil
        }
        return true
    }

    public func allocateRemoteRelayRoute(
        runtimeDeviceID: String,
        routeToken: String,
        preferredRelaySecret: String? = nil,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning
    ) throws -> CompanionRemoteRelayRouteAllocation? {
        let defaultPort = Self.bootstrapRelayDefaultPort(from: environment)
        let endpoints = bootstrapRelayEndpoints(defaultPort: defaultPort)
        guard let firstEndpoint = endpoints.first else {
            return nil
        }
        let explicitRelayID = environment["AETHERLINK_BOOTSTRAP_RELAY_ID"]?.takeIfNotEmpty()
        let explicitRelaySecret = environment["AETHERLINK_BOOTSTRAP_RELAY_SECRET"]?.takeIfNotEmpty()
        if explicitRelayID != nil || explicitRelaySecret != nil {
            guard let explicitRelayID, let explicitRelaySecret else {
                throw RelayServiceRouteAllocationError.incompleteStaticBootstrapRoute
            }
            return CompanionRemoteRelayRouteAllocation(
                configuration: RelayPeerConfiguration(
                    host: firstEndpoint.host,
                    port: firstEndpoint.port,
                    relayID: explicitRelayID,
                    relaySecret: explicitRelaySecret
                )
            )
        }
        var lastError: Error?
        let allocationToken = environment["AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty()
            ?? environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty()
            ?? storedBootstrapRelaySettings.allocationToken?.takeIfNotEmpty()
        let endpointRelaySecret = preferredRelaySecret?.takeIfNotEmpty()
            ?? generateRuntimeLocalRelaySecret()
        for endpoint in endpoints {
            do {
                let serviceAllocation = try relayServiceAllocator.allocateRelayRoute(
                    host: endpoint.host,
                    port: endpoint.port,
                    routeToken: routeToken,
                    allocationToken: allocationToken,
                    runtimeIdentity: runtimeIdentity,
                    identityAuthorizationSigner: identityAuthorizationSigner,
                    timeout: 5
                )
                return try serviceAllocation.attachingEndpointSecret(
                    endpointRelaySecret,
                    runtimeIdentity: runtimeIdentity,
                    identityAuthorizationSigner: identityAuthorizationSigner
                )
            } catch {
                lastError = error
            }
        }
        if let lastError {
            throw lastError
        }
        return nil
    }

    private func bootstrapRelayEndpoints(defaultPort: UInt16) -> [BootstrapRelayEndpoint] {
        let environmentEndpoints = Self.bootstrapRelayEndpoints(from: environment, defaultPort: defaultPort)
        if !environmentEndpoints.isEmpty {
            return environmentEndpoints
        }
        guard storedBootstrapRelaySettings.isEnabled else { return [] }
        return Self.bootstrapRelayEndpoints(from: storedBootstrapRelaySettings.endpoints, defaultPort: defaultPort)
    }

    private static func bootstrapRelayDefaultPort(from environment: [String: String]) -> UInt16 {
        UInt16(environment["AETHERLINK_BOOTSTRAP_RELAY_PORT"] ?? "") ?? defaultBootstrapRelayPort
    }

    private static func bootstrapRelayEndpoints(
        from environment: [String: String],
        defaultPort: UInt16
    ) -> [BootstrapRelayEndpoint] {
        if let endpointList = environment["AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS"]?.takeIfNotEmpty() {
            return bootstrapRelayEndpoints(from: endpointList, defaultPort: defaultPort)
        }
        guard let host = environment["AETHERLINK_BOOTSTRAP_RELAY_HOST"]?.takeIfNotEmpty() else {
            return []
        }
        return [BootstrapRelayEndpoint(host: host, port: defaultPort)]
    }

    private static func bootstrapRelayEndpoints(
        from endpointList: String,
        defaultPort: UInt16
    ) -> [BootstrapRelayEndpoint] {
        endpointList
            .split(separator: ",", omittingEmptySubsequences: true)
            .compactMap { parseBootstrapRelayEndpoint(String($0), defaultPort: defaultPort) }
    }

    private static func parseBootstrapRelayEndpoint(
        _ value: String,
        defaultPort: UInt16
    ) -> BootstrapRelayEndpoint? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        if trimmed.hasPrefix("["),
           let closeBracket = trimmed.firstIndex(of: "]") {
            let host = String(trimmed[trimmed.index(after: trimmed.startIndex)..<closeBracket])
            guard !host.isEmpty else { return nil }
            let remainder = trimmed[trimmed.index(after: closeBracket)...]
            if remainder.isEmpty {
                return BootstrapRelayEndpoint(host: host, port: defaultPort)
            }
            guard remainder.hasPrefix(":"),
                  let port = UInt16(String(remainder.dropFirst()))
            else {
                return nil
            }
            return BootstrapRelayEndpoint(host: host, port: port)
        }

        let colonCount = trimmed.filter { $0 == ":" }.count
        if colonCount == 1,
           let colon = trimmed.lastIndex(of: ":"),
           let port = UInt16(String(trimmed[trimmed.index(after: colon)...])) {
            let host = String(trimmed[..<colon])
            guard !host.isEmpty else { return nil }
            return BootstrapRelayEndpoint(host: host, port: port)
        }

        return BootstrapRelayEndpoint(host: trimmed, port: defaultPort)
    }
}

private struct BootstrapRelayEndpoint: Equatable, Sendable {
    var host: String
    var port: UInt16
}

@MainActor
private struct PendingPairScopedRelayActivation: Equatable {
    let clientKeyFingerprint: String
    let result: RuntimeRouteRefreshResult
    let rotatesBootstrapRoute: Bool
    let runtimeLifecycleGeneration: UUID
    let pairLifecycleGeneration: UUID
    let refreshSequence: UInt64
    var activationRequested: Bool
}

@MainActor
public final class CompanionAppModel: ObservableObject {
    @Published public private(set) var backendStatus = "Not checked"
    @Published public private(set) var transportStatus = "Stopped"
    @Published public private(set) var transportState: CompanionTransportStatus = .stopped
    @Published public private(set) var providerStatuses: [CompanionProviderStatus]
    @Published public private(set) var bootstrapRelaySettings: CompanionBootstrapRelaySettings = .disabled
    @Published public private(set) var developmentRelaySettings: CompanionDevelopmentRelaySettings = .disabled
    @Published public private(set) var developmentRelayConnectionStatus: CompanionDevelopmentRelayStatus = .stopped
    @Published public private(set) var remoteRoutePreparationIssue: CompanionRemoteRoutePreparationIssue?
    @Published public private(set) var pairingSession: PairingSession?
    @Published public private(set) var trustedDevices: [TrustedDevice] = []
    @Published public private(set) var models: [ModelInfo] = []
    @Published public private(set) var modelResidency: CompanionModelResidencyStatus = .inactive
    @Published public private(set) var runtimeDataSummary = CompanionRuntimeDataSummary()
    @Published public private(set) var runtimeChatSessions: [RuntimeChatStoredSession] = []
    @Published public private(set) var runtimeChatSessionsError: String?
    @Published public private(set) var runtimeChatTranscriptMessages: [String: [RuntimeChatStoredMessage]] = [:]
    @Published public private(set) var runtimeChatTranscriptErrors: [String: String] = [:]
    @Published public private(set) var runtimeMemoryEntries: [RuntimeMemoryEntry] = []
    @Published public private(set) var runtimeMemoryEntriesError: String?
    @Published public private(set) var runtimeDocumentSources: [CompanionRuntimeDocumentSource] = []
    @Published public private(set) var runtimeDocumentAuditEvents: [RuntimeDocumentSourceAuditEvent] = []
    @Published public private(set) var pendingRuntimeDocumentReview: CompanionRuntimeDocumentImportReview?
    @Published public private(set) var runtimeDocumentSourcesError: String?
    @Published public private(set) var runtimeDocumentSourcesIssue: RuntimeDocumentSourceManagementError?
    @Published public private(set) var isRuntimeDocumentSourceOperationInFlight = false
    @Published public private(set) var logs: [String] = []

    private let backend: any LlmBackend
    private var runtimeRouter: LocalRuntimeMessageRouter!
    private let runtimeChatEventStore: any RuntimeChatEventStore
    private let runtimeMemoryStore: any RuntimeMemoryStore
    private let runtimeDocumentSourceManager: RuntimeDocumentSourceManager
    private let pairingCoordinator = PairingCoordinator()
    private let trustedDeviceStore: TrustedDeviceStore
    private let userDefaults: UserDefaults
    private var runtimeConnectionManager: MacRuntimeConnectionManager!
    private let pairScopedRelayRouteStore: PairScopedRelayRouteStore
    private var pairScopedRelayRoutes: [String: ResolvedPairScopedRelayRoute]
    private let relaySecretStore: any CompanionRelaySecretStoring
    private var remoteRelayRouteAllocator: any CompanionRemoteRelayRouteAllocating
    private let relayServiceRouteAllocator: any RelayServiceRouteAllocating
    private let environment: [String: String]
    private let runtimeRouteHostProvider: () -> String?
    private var relayConfiguration: RelayPeerConfiguration?
    private var allocatedRemoteRouteLease: CompanionRemoteRouteLease?
    private var pendingPairedRelayActivations: [String: PendingPairScopedRelayActivation] = [:]
    private var runtimeLifecycleGeneration = UUID()
    private var pairLifecycleGenerations: [String: UUID] = [:]
    private var pairRefreshSequences: [String: UInt64] = [:]
    private var inFlightPairRefreshSequences: [String: Set<UInt64>] = [:]
    private let macDeviceID: String
    private let runtimeIdentityKey: RuntimeIdentityKey
    private let runtimeIdentityAuthorizationSigner: (
        any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning
    )?
    private let runtimeIdentityWarning: String?
    private var runtimePort: UInt16 = 43170
    private var isRuntimeStarted = false
    private var shouldGenerateRemotePairingQRCodeWhenRelayReady = false

    public var hasDevelopmentRelayRoute: Bool {
        relayConfiguration != nil
    }

    public var isDevelopmentRelayRouteEligibleForQRCode: Bool {
        guard developmentRelaySettings.isEnabled, relayConfiguration != nil else { return false }
        if !developmentRelaySettings.isEligibleForRemoteQRCode {
            return false
        }
        guard relayFrameEncryptionEnabled else { return false }
        return true
    }

    public var isDevelopmentRelayQRCodeReady: Bool {
        guard isDevelopmentRelayRouteEligibleForQRCode else { return false }
        guard isDevelopmentRelayRoutePreparedForQRCode else { return false }
        switch developmentRelayConnectionStatus.status {
        case .waitingForPeer, .ready:
            return true
        case .stopped, .connecting, .reconnecting, .failed:
            return false
        }
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

    public var isDevelopmentRelayRoutePreparedForQRCode: Bool {
        hasCurrentRelayRouteLeaseForQRCode
    }

    public var canPrepareRemoteRelayRouteAutomatically: Bool {
        canAttemptAutomaticRemoteRouteAllocation
    }

    private var hasCurrentRelayRouteLeaseForQRCode: Bool {
        if let allocatedRemoteRouteLease {
            return isRelayRouteLeaseFreshForPairingQRCode(allocatedRemoteRouteLease)
        }
        return false
    }

    public init(
        backend: any LlmBackend = AggregatingLlmBackend(ollama: OllamaBackend(), lmStudio: LMStudioBackend()),
        peerServer: any RuntimeTransport = LocalPeerServer(),
        advertiser: any RuntimeAdvertiser = BonjourAdvertiser(),
        relayClient: any RelayPeerTransport = RelayPeerClient(),
        pairedRelayClientFactory: @escaping @Sendable () -> any RelayPeerTransport = {
            RelayPeerClient()
        },
        pairedPrivateOverlayTransportFactory: (
            @Sendable () -> any MacRuntimePrivateOverlayTransport
        )? = nil,
        remoteRelayRouteAllocator: (any CompanionRemoteRelayRouteAllocating)? = nil,
        relayServiceRouteAllocator: any RelayServiceRouteAllocating = TCPRelayServiceRouteAllocator(),
        environment: [String: String] = ProcessInfo.processInfo.environment,
        userDefaults: UserDefaults = .standard,
        relaySecretStore: any CompanionRelaySecretStoring = KeychainCompanionRelaySecretStore(),
        trustedDeviceStore: TrustedDeviceStore = TrustedDeviceStore(),
        runtimeChatEventStore: any RuntimeChatEventStore = RuntimeChatEventStoreDefaults.productionStore(),
        runtimeMemoryStore: any RuntimeMemoryStore = JSONLRuntimeMemoryStore(),
        runtimeDocumentIndexStore: SQLiteRuntimeDocumentIndexStore = SQLiteRuntimeDocumentIndexStore(),
        runtimeRouteHostProvider: (() -> String?)? = nil,
        allowsAuthenticatedRouteRefresh: Bool = false
    ) {
        let loadedBootstrapRelaySettings = Self.loadBootstrapRelaySettings(
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        self.backend = backend
        self.providerStatuses = Self.initialProviderStatuses(for: backend)
        self.relayServiceRouteAllocator = relayServiceRouteAllocator
        self.environment = environment
        self.userDefaults = userDefaults
        self.bootstrapRelaySettings = loadedBootstrapRelaySettings
        self.relaySecretStore = relaySecretStore
        let pairScopedRelayRouteStore = PairScopedRelayRouteStore(
            userDefaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        self.pairScopedRelayRouteStore = pairScopedRelayRouteStore
        self.pairScopedRelayRoutes = Dictionary(
            uniqueKeysWithValues: pairScopedRelayRouteStore.loadAll().map {
                ($0.clientKeyFingerprint, $0)
            }
        )
        self.trustedDeviceStore = trustedDeviceStore
        self.runtimeChatEventStore = runtimeChatEventStore
        self.runtimeMemoryStore = runtimeMemoryStore
        self.runtimeDocumentSourceManager = RuntimeDocumentSourceManager(store: runtimeDocumentIndexStore)
        self.remoteRelayRouteAllocator = remoteRelayRouteAllocator ?? Self.makeRemoteRelayRouteAllocator(
            environment: environment,
            bootstrapRelaySettings: loadedBootstrapRelaySettings,
            relayServiceRouteAllocator: relayServiceRouteAllocator
        )
        self.runtimeRouteHostProvider = runtimeRouteHostProvider ?? Self.defaultRuntimeRouteHost
        let macDeviceID = Self.loadOrCreateMacDeviceID(defaults: userDefaults)
        let runtimeIdentity = Self.loadOrCreateRuntimeIdentityKey(
            deviceID: macDeviceID,
            environment: environment
        )
        self.macDeviceID = macDeviceID
        self.runtimeIdentityKey = runtimeIdentity.key
        self.runtimeIdentityAuthorizationSigner = runtimeIdentity.signer
        self.runtimeIdentityWarning = runtimeIdentity.warning
        self.discoveryRouteToken = Self.loadOrCreateDiscoveryRouteToken(defaults: userDefaults)
        let relaySettings = Self.loadDevelopmentRelaySettings(
            deviceID: macDeviceID,
            routeToken: discoveryRouteToken,
            environment: environment,
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        let savedRelayLease = Self.loadSavedRemoteRouteLease(
            defaults: userDefaults,
            relaySettings: relaySettings
        )
        self.developmentRelaySettings = relaySettings
        self.relayConfiguration = Self.relayConfiguration(for: relaySettings, lease: savedRelayLease)
        self.allocatedRemoteRouteLease = savedRelayLease
        self.developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
            status: .stopped,
            endpoint: relaySettings.endpointLabel
        )
        self.runtimeRouter = LocalRuntimeMessageRouter(
            backend: backend,
            pairingCoordinator: pairingCoordinator,
            trustedDeviceStore: trustedDeviceStore,
            chatEventStore: runtimeChatEventStore,
            memoryStore: runtimeMemoryStore,
            documentIndexStore: runtimeDocumentIndexStore,
            routeRefresher: allowsAuthenticatedRouteRefresh ? self : nil,
            runtimeChallengeSigner: runtimeIdentity.signer,
            onPairingAccepted: { [weak self] device in
                Task { @MainActor in
                    self?.pairingSession = nil
                    await self?.refreshTrustedDevices()
                    self?.log("Trusted \(device.name)")
                }
            }
        )
        let runtimeRouter = self.runtimeRouter!
        self.runtimeConnectionManager = MacRuntimeConnectionManager(
            localTransport: peerServer,
            advertiser: advertiser,
            bootstrapTransport: relayClient,
            pairTransportFactory: pairedRelayClientFactory,
            pairPrivateOverlayTransportFactory: pairedPrivateOverlayTransportFactory,
            onDisconnect: { connectionID in
                runtimeRouter.connectionDidClose(connectionID)
            }
        )
        configureResidencyEventsIfAvailable()
        if let runtimeIdentityWarning {
            log(runtimeIdentityWarning)
        }
        refreshRuntimeDataSummary()
    }

    public func start(port: UInt16 = 43170) {
        runtimePort = port
        isRuntimeStarted = true
        let router = runtimeRouter!
        let localStatus = runtimeConnectionManager.startLocal(
            port: port,
            metadata: runtimeAdvertisementMetadata
        ) { [router, weak self] envelope, sink in
            Task { @MainActor in
                self?.log("Received \(envelope.type)")
            }
            router.handle(envelope, sink: sink)
        }
        renewSavedBootstrapRelayRouteIfNeeded()
        startRelayClientIfConfigured()
        startRestoredPairScopedTransports()
        transportState = Self.transportStatus(from: localStatus)
        refreshTransportStatusText()
        switch transportState.state {
        case .advertising:
            log("AetherLink runtime started")
            if let relayConfiguration {
                log("Remote route enabled: \(relayConfiguration.host):\(relayConfiguration.port)")
            }
        case .failed:
            let message = transportState.failureMessage ?? "Runtime listener failed"
            transportStatus = "Runtime listener failed: \(message)"
            log(transportStatus)
        case .stopped:
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
        runtimeLifecycleGeneration = UUID()
        pendingPairedRelayActivations.removeAll()
        runtimeConnectionManager.stopAll()
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

    public func refreshRuntimeDataSummary() {
        let refreshedAt = Date()
        var activeChatSessionCount = runtimeDataSummary.activeChatSessionCount
        var archivedChatSessionCount = runtimeDataSummary.archivedChatSessionCount
        var enabledMemoryCount = runtimeDataSummary.enabledMemoryCount
        var pausedMemoryCount = runtimeDataSummary.pausedMemoryCount
        var errorMessages: [String] = []

        do {
            let sessions = try runtimeChatEventStore.listAllSessions(
                limit: Int.max,
                includeArchived: true
            )
            publishRuntimeChatSessions(sessions)
            activeChatSessionCount = sessions.filter { $0.status == "active" }.count
            archivedChatSessionCount = sessions.filter { $0.status == "archived" }.count
            runtimeChatSessionsError = nil
        } catch {
            let message = error.localizedDescription
            runtimeChatSessionsError = message
            errorMessages.append(message)
            log("Runtime chat history summary failed: \(message)")
        }

        do {
            let memoryEntries = try runtimeMemoryStore.listAll()
            publishRuntimeMemoryEntries(memoryEntries)
            enabledMemoryCount = memoryEntries.filter(\.enabled).count
            pausedMemoryCount = memoryEntries.filter { !$0.enabled }.count
            runtimeMemoryEntriesError = nil
        } catch {
            let message = error.localizedDescription
            runtimeMemoryEntriesError = message
            errorMessages.append(message)
            log("Runtime memory summary failed: \(message)")
        }

        runtimeDataSummary = CompanionRuntimeDataSummary(
            activeChatSessionCount: activeChatSessionCount,
            archivedChatSessionCount: archivedChatSessionCount,
            enabledMemoryCount: enabledMemoryCount,
            pausedMemoryCount: pausedMemoryCount,
            lastRefreshedAt: refreshedAt,
            errorMessage: errorMessages.first
        )
    }

    public func refreshRuntimeMemoryEntries() {
        do {
            let memoryEntries = try runtimeMemoryStore.listAll()
            publishRuntimeMemoryEntries(memoryEntries)
            runtimeMemoryEntriesError = nil
            runtimeDataSummary = CompanionRuntimeDataSummary(
                activeChatSessionCount: runtimeDataSummary.activeChatSessionCount,
                archivedChatSessionCount: runtimeDataSummary.archivedChatSessionCount,
                enabledMemoryCount: memoryEntries.filter(\.enabled).count,
                pausedMemoryCount: memoryEntries.filter { !$0.enabled }.count,
                lastRefreshedAt: Date(),
                errorMessage: runtimeDataSummaryErrorMessage()
            )
        } catch {
            let message = error.localizedDescription
            runtimeMemoryEntriesError = message
            runtimeDataSummary = CompanionRuntimeDataSummary(
                activeChatSessionCount: runtimeDataSummary.activeChatSessionCount,
                archivedChatSessionCount: runtimeDataSummary.archivedChatSessionCount,
                enabledMemoryCount: runtimeDataSummary.enabledMemoryCount,
                pausedMemoryCount: runtimeDataSummary.pausedMemoryCount,
                lastRefreshedAt: Date(),
                errorMessage: runtimeDataSummaryErrorMessage()
            )
            log("Runtime memory inspector failed: \(message)")
        }
    }

    public func refreshRuntimeDocumentSources() async {
        do {
            let sources = try await runtimeDocumentSourceManager.sources()
            let auditEvents = try await runtimeDocumentSourceManager.auditEvents()
            runtimeDocumentSources = sources.sorted { lhs, rhs in
                if lhs.approvedAt != rhs.approvedAt {
                    return lhs.approvedAt > rhs.approvedAt
                }
                return lhs.id < rhs.id
            }
            runtimeDocumentAuditEvents = auditEvents
            runtimeDocumentSourcesError = nil
            runtimeDocumentSourcesIssue = nil
        } catch {
            publishRuntimeDocumentSourceFailure(error)
        }
    }

    public func prepareRuntimeDocumentSource(
        fileURL: URL,
        replacingSourceID: String? = nil
    ) async {
        guard !isRuntimeDocumentSourceOperationInFlight else { return }
        isRuntimeDocumentSourceOperationInFlight = true
        defer { isRuntimeDocumentSourceOperationInFlight = false }
        do {
            pendingRuntimeDocumentReview = try await runtimeDocumentSourceManager.prepareImport(
                from: fileURL,
                replacingSourceID: replacingSourceID
            )
            runtimeDocumentSourcesError = nil
            runtimeDocumentSourcesIssue = nil
        } catch {
            pendingRuntimeDocumentReview = nil
            publishRuntimeDocumentSourceFailure(error)
        }
    }

    public func approveRuntimeDocumentSourceReview() async {
        guard !isRuntimeDocumentSourceOperationInFlight,
              let review = pendingRuntimeDocumentReview else { return }
        isRuntimeDocumentSourceOperationInFlight = true
        defer { isRuntimeDocumentSourceOperationInFlight = false }
        do {
            _ = try await runtimeDocumentSourceManager.approve(
                reviewID: review.id,
                confirmationToken: review.confirmationToken,
                disclosureVersion: review.disclosureVersion
            )
            pendingRuntimeDocumentReview = nil
            runtimeDocumentSourcesError = nil
            runtimeDocumentSourcesIssue = nil
            log("Document source approved for trusted devices")
            await refreshRuntimeDocumentSources()
        } catch {
            publishRuntimeDocumentSourceFailure(error)
        }
    }

    public func discardRuntimeDocumentSourceReview() async {
        guard let review = pendingRuntimeDocumentReview else { return }
        pendingRuntimeDocumentReview = nil
        await runtimeDocumentSourceManager.cancel(reviewID: review.id)
    }

    public func removeRuntimeDocumentSource(id sourceID: String, expectedRevision: String) async {
        guard !isRuntimeDocumentSourceOperationInFlight else { return }
        isRuntimeDocumentSourceOperationInFlight = true
        defer { isRuntimeDocumentSourceOperationInFlight = false }
        do {
            try await runtimeDocumentSourceManager.removeSource(
                id: sourceID,
                expectedRevision: expectedRevision
            )
            runtimeDocumentSourcesError = nil
            runtimeDocumentSourcesIssue = nil
            log("Document source removed from trusted-device access")
            await refreshRuntimeDocumentSources()
        } catch {
            publishRuntimeDocumentSourceFailure(error)
        }
    }

    public func makeRuntimeDocumentAuditExport() async -> Data? {
        do {
            let data = try await runtimeDocumentSourceManager.auditExportData()
            runtimeDocumentSourcesError = nil
            runtimeDocumentSourcesIssue = nil
            return data
        } catch {
            publishRuntimeDocumentSourceFailure(error)
            return nil
        }
    }

    private func publishRuntimeDocumentSourceFailure(_ error: Error) {
        let message: String
        let issue: RuntimeDocumentSourceManagementError
        if let managementError = error as? RuntimeDocumentSourceManagementError {
            issue = managementError
            message = managementError.localizedDescription
        } else {
            issue = .storageUnavailable
            message = RuntimeDocumentSourceManagementError.storageUnavailable.localizedDescription
        }
        runtimeDocumentSourcesIssue = issue
        runtimeDocumentSourcesError = message
        log("Document source operation failed")
    }

    public func refreshRuntimeChatSessions() {
        do {
            let sessions = try runtimeChatEventStore.listAllSessions(
                limit: Int.max,
                includeArchived: true
            )
            publishRuntimeChatSessions(sessions)
            runtimeChatSessionsError = nil
            runtimeDataSummary = CompanionRuntimeDataSummary(
                activeChatSessionCount: sessions.filter { $0.status == "active" }.count,
                archivedChatSessionCount: sessions.filter { $0.status == "archived" }.count,
                enabledMemoryCount: runtimeDataSummary.enabledMemoryCount,
                pausedMemoryCount: runtimeDataSummary.pausedMemoryCount,
                lastRefreshedAt: Date(),
                errorMessage: runtimeDataSummaryErrorMessage()
            )
        } catch {
            let message = error.localizedDescription
            runtimeChatSessionsError = message
            runtimeDataSummary = CompanionRuntimeDataSummary(
                activeChatSessionCount: runtimeDataSummary.activeChatSessionCount,
                archivedChatSessionCount: runtimeDataSummary.archivedChatSessionCount,
                enabledMemoryCount: runtimeDataSummary.enabledMemoryCount,
                pausedMemoryCount: runtimeDataSummary.pausedMemoryCount,
                lastRefreshedAt: Date(),
                errorMessage: runtimeDataSummaryErrorMessage()
            )
            log("Runtime chat history inspector failed: \(message)")
        }
    }

    public func refreshRuntimeChatTranscriptPreview(sessionID: String, limit: Int = 20) {
        let cleanSessionID = sessionID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanSessionID.isEmpty else { return }
        do {
            let messages = try runtimeChatEventStore.listAllMessages(
                sessionID: cleanSessionID,
                limit: limit
            )
            var messageMap = runtimeChatTranscriptMessages
            messageMap[cleanSessionID] = messages
            runtimeChatTranscriptMessages = messageMap

            var errorMap = runtimeChatTranscriptErrors
            errorMap.removeValue(forKey: cleanSessionID)
            runtimeChatTranscriptErrors = errorMap
        } catch {
            var messageMap = runtimeChatTranscriptMessages
            messageMap[cleanSessionID] = []
            runtimeChatTranscriptMessages = messageMap

            var errorMap = runtimeChatTranscriptErrors
            errorMap[cleanSessionID] = error.localizedDescription
            runtimeChatTranscriptErrors = errorMap
            log("Runtime chat transcript preview failed: \(error.localizedDescription)")
        }
    }

    private func publishRuntimeChatSessions(_ sessions: [RuntimeChatStoredSession]) {
        runtimeChatSessions = sessions.sorted { lhs, rhs in
            if lhs.lastActivityAt != rhs.lastActivityAt {
                return lhs.lastActivityAt > rhs.lastActivityAt
            }
            return lhs.sessionID < rhs.sessionID
        }
    }

    private func publishRuntimeMemoryEntries(_ entries: [RuntimeMemoryEntry]) {
        runtimeMemoryEntries = entries.sorted { lhs, rhs in
            if lhs.updatedAt != rhs.updatedAt {
                return lhs.updatedAt > rhs.updatedAt
            }
            return lhs.id < rhs.id
        }
    }

    private func runtimeDataSummaryErrorMessage() -> String? {
        runtimeChatSessionsError ?? runtimeMemoryEntriesError
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

    public func unloadResidentModelNow() async {
        guard let aggregate = backend as? AggregatingLlmBackend else {
            modelResidency = .unsupported
            return
        }
        _ = await aggregate.unloadActiveResidencyModelNow()
        modelResidency = CompanionModelResidencyStatus(
            snapshot: aggregate.modelResidencySnapshot(),
            lastEvent: modelResidency.lastEvent
        )
    }

    public func beginPairing(routePolicy: CompanionPairingRoutePolicy = .remoteRequired) {
        if !isRuntimeStarted {
            start(port: runtimePort)
        }
        if routePolicy == .remoteRequired {
            prepareRemoteRelayRouteForPairing()
        }
        let pairingRelayConfiguration = shouldIncludeDevelopmentRelayInPairingQRCode ? relayConfiguration : nil
        if routePolicy == .remoteRequired && pairingRelayConfiguration == nil {
            pairingSession = nil
            if let issue = remoteRoutePreparationIssue {
                shouldGenerateRemotePairingQRCodeWhenRelayReady = false
                log("Remote pairing QR not generated: \(issue.message)")
            } else if let endpoint = developmentRelaySettings.endpointLabel {
                if isDevelopmentRelayRouteEligibleForQRCode {
                    shouldGenerateRemotePairingQRCodeWhenRelayReady = true
                    log("Remote pairing QR not generated: remote route \(endpoint) is not ready")
                } else {
                    shouldGenerateRemotePairingQRCodeWhenRelayReady = false
                    log("Remote pairing QR not generated: remote route \(endpoint) cannot be included in QR")
                }
            } else {
                shouldGenerateRemotePairingQRCodeWhenRelayReady = false
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .automaticPreparationUnavailable,
                    message: "Configure a reachable remote route before generating a remote pairing QR."
                )
                log("Remote pairing QR not generated: configure a reachable remote route first")
            }
            return
        }
        shouldGenerateRemotePairingQRCodeWhenRelayReady = false
        let localRouteHost = pairingRelayConfiguration == nil ? localPairingRouteHost : nil
        let relayRouteLease = relayRouteLeaseForPairing(relayConfiguration: pairingRelayConfiguration)
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
            relayNonce: relayRouteLease?.nonce,
            relayScope: pairingRelayConfiguration.flatMap {
                Self.relayScope(
                    forRelayHost: $0.host,
                    allowsPrivateOverlay: developmentRelaySettings.allowsPrivateOverlay
                )
            }
        )
        log("Pairing code generated")
    }

    @discardableResult
    public func configureDevelopmentRelay(
        host: String,
        port: UInt16,
        relaySecret: String? = nil,
        attemptAllocation: Bool = false,
        allowsPrivateOverlay: Bool = false
    ) -> CompanionRelayConfigurationResult {
        let trimmedHost = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedHost.isEmpty else {
            clearDevelopmentRelay()
            return .disabled
        }
        if CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: trimmedHost) == .invalidFormat {
            let message = "Connection address must not include a scheme, path, user info, query, fragment, or port."
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationRejected,
                endpoint: trimmedHost,
                message: message
            )
            log("Remote route configuration rejected: \(message)")
            return .allocationFailed(endpoint: trimmedHost, message: message)
        }

        let secret = relaySecret?.takeIfNotEmpty() ?? Self.generateRelaySecret()
        if attemptAllocation {
            do {
                let authorization = try relayAllocationAuthorization()
                let serviceAllocation = try relayServiceRouteAllocator.allocateRelayRoute(
                    host: trimmedHost,
                    port: port,
                    routeToken: discoveryRouteToken,
                    allocationToken: environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty(),
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer,
                    timeout: 5
                )
                let allocation = try serviceAllocation.attachingEndpointSecret(
                    secret,
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer
                )
                let configuration = allocation.configuration
                guard acceptsRemoteRouteAllocation(allocation) else {
                    let endpoint = "\(configuration.host):\(configuration.port)"
                    let message = "Remote route lease did not advance."
                    remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                        kind: .automaticPreparationRejected,
                        endpoint: endpoint,
                        message: message
                    )
                    log("Remote route allocation rejected: non-advancing lease for \(endpoint)")
                    return .allocationFailed(endpoint: endpoint, message: message)
                }
                let settings = CompanionDevelopmentRelaySettings(
                    isEnabled: true,
                    host: configuration.host,
                    port: configuration.port,
                    relayID: configuration.relayID,
                    relaySecret: configuration.relaySecret?.takeIfNotEmpty() ?? secret,
                    isEnvironmentOverride: false,
                    allowsPrivateOverlay: allowsPrivateOverlay || Self.allowsPrivateOverlayRelayEnvironment(environment)
                )
                applyDevelopmentRelaySettings(settings, lease: allocation.lease)
                let endpoint = settings.endpointLabel ?? "\(configuration.host):\(configuration.port)"
                log("Remote route allocated: \(endpoint)")
                return .allocated(endpoint: endpoint)
            } catch {
                let settings = CompanionDevelopmentRelaySettings(
                    isEnabled: true,
                    host: trimmedHost,
                    port: port,
                    relayID: discoveryRouteToken,
                    relaySecret: secret,
                    isEnvironmentOverride: false,
                    allowsPrivateOverlay: allowsPrivateOverlay || Self.allowsPrivateOverlayRelayEnvironment(environment)
                )
                applyDevelopmentRelaySettings(settings, lease: nil)
                let endpoint = settings.endpointLabel ?? "\(trimmedHost):\(port)"
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .automaticPreparationFailed,
                    endpoint: endpoint,
                    message: error.localizedDescription
                )
                log("Remote route allocation failed: \(error.localizedDescription)")
                return .allocationFailed(endpoint: endpoint, message: error.localizedDescription)
            }
        }

        let settings = CompanionDevelopmentRelaySettings(
            isEnabled: true,
            host: trimmedHost,
            port: port,
            relayID: discoveryRouteToken,
            relaySecret: secret,
            isEnvironmentOverride: false,
            allowsPrivateOverlay: allowsPrivateOverlay || Self.allowsPrivateOverlayRelayEnvironment(environment)
        )
        applyDevelopmentRelaySettings(settings, lease: nil)
        log("Remote route configured: \(trimmedHost):\(port)")
        return .savedStatic(endpoint: settings.endpointLabel ?? "\(trimmedHost):\(port)")
    }

    public func clearDevelopmentRelay() {
        Self.clearSavedDevelopmentRelaySettings(
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        Self.clearSavedRemoteRouteLease(defaults: userDefaults)
        developmentRelaySettings = .disabled
        relayConfiguration = nil
        allocatedRemoteRouteLease = nil
        runtimeConnectionManager.stopBootstrap()
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(status: .stopped)
        remoteRoutePreparationIssue = nil
        shouldGenerateRemotePairingQRCodeWhenRelayReady = false
        refreshTransportStatusText()
        log("Remote route disabled")
    }

    @discardableResult
    public func configureBootstrapRelay(
        endpoints: String,
        allocationToken: String? = nil,
        allowsPrivateOverlay: Bool = false
    ) -> CompanionRelayConfigurationResult {
        let trimmedEndpoints = endpoints.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedEndpoints.isEmpty else {
            clearBootstrapRelay()
            return .disabled
        }

        let settings = CompanionBootstrapRelaySettings(
            isEnabled: true,
            endpoints: trimmedEndpoints,
            allocationToken: allocationToken?.trimmingCharacters(in: .whitespacesAndNewlines),
            allowsPrivateOverlay: allowsPrivateOverlay
        )
        Self.saveBootstrapRelaySettings(
            settings,
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        bootstrapRelaySettings = settings
        remoteRelayRouteAllocator = Self.makeRemoteRelayRouteAllocator(
            environment: environment,
            bootstrapRelaySettings: settings,
            relayServiceRouteAllocator: relayServiceRouteAllocator
        )
        remoteRoutePreparationIssue = nil
        allocateRemoteRelayRouteIfAvailable()

        if let issue = remoteRoutePreparationIssue {
            return .allocationFailed(endpoint: settings.endpointLabel ?? trimmedEndpoints, message: issue.message)
        }
        if let endpoint = developmentRelayEndpoint {
            return .allocated(endpoint: endpoint)
        }
        let message = "Connection preparation did not return route details."
        remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
            kind: .automaticPreparationUnavailable,
            endpoint: settings.endpointLabel,
            message: message
        )
        return .allocationFailed(endpoint: settings.endpointLabel ?? trimmedEndpoints, message: message)
    }

    public func clearBootstrapRelay() {
        Self.clearSavedBootstrapRelaySettings(
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        bootstrapRelaySettings = .disabled
        remoteRelayRouteAllocator = Self.makeRemoteRelayRouteAllocator(
            environment: environment,
            bootstrapRelaySettings: .disabled,
            relayServiceRouteAllocator: relayServiceRouteAllocator
        )
        remoteRoutePreparationIssue = nil
        log("Bootstrap route disabled")
    }

    public func regenerateDevelopmentRelaySecret() {
        guard developmentRelaySettings.isEnabled else { return }
        let settings = CompanionDevelopmentRelaySettings(
            isEnabled: true,
            host: developmentRelaySettings.host,
            port: developmentRelaySettings.port,
            relayID: discoveryRouteToken,
            relaySecret: Self.generateRelaySecret(),
            isEnvironmentOverride: false,
            allowsPrivateOverlay: developmentRelaySettings.allowsPrivateOverlay
        )
        Self.saveDevelopmentRelaySettings(
            settings,
            deviceID: macDeviceID,
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        Self.clearSavedRemoteRouteLease(defaults: userDefaults)
        developmentRelaySettings = settings
        relayConfiguration = Self.relayConfiguration(for: settings, lease: nil)
        allocatedRemoteRouteLease = nil
        remoteRoutePreparationIssue = nil
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
            status: .stopped,
            endpoint: settings.endpointLabel
        )
        restartRelayClientIfRunning()
        refreshTransportStatusText()
        log("Route secret regenerated")
    }

    private func allocateRemoteRelayRouteIfAvailable(restartRelayClientIfRunning shouldRestartRelayClient: Bool = true) {
        do {
            let authorization = try relayAllocationAuthorization()
            let preferredRelaySecret = developmentRelaySettings.relaySecret?.takeIfNotEmpty()
                ?? Self.loadSavedRelaySecret(
                    deviceID: macDeviceID,
                    relayID: developmentRelaySettings.relayID,
                    defaults: userDefaults,
                    relaySecretStore: relaySecretStore
                )
            guard let allocation = try remoteRelayRouteAllocator.allocateRemoteRelayRoute(
                runtimeDeviceID: macDeviceID,
                routeToken: discoveryRouteToken,
                preferredRelaySecret: preferredRelaySecret,
                runtimeIdentity: authorization.identity,
                identityAuthorizationSigner: authorization.signer
            ) else {
                if remoteRelayRouteAllocator.canAllocateRemoteRelayRoute {
                    remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                        kind: .automaticPreparationUnavailable,
                        message: "Connection preparation did not return route details."
                    )
                    log("Remote route bootstrap unavailable: connection preparation did not return route details")
                }
                return
            }
            guard isEligibleAutomaticRelayHost(allocation.configuration.host) else {
                let endpoint = "\(allocation.configuration.host):\(allocation.configuration.port)"
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .automaticPreparationRejected,
                    endpoint: endpoint,
                    message: "This AetherLink Runtime connection address is not reachable from another network."
                )
                log("Remote route bootstrap rejected unreachable connection address \(allocation.configuration.host)")
                return
            }
            guard acceptsRemoteRouteAllocation(allocation) else {
                let endpoint = "\(allocation.configuration.host):\(allocation.configuration.port)"
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .automaticPreparationRejected,
                    endpoint: endpoint,
                    message: "Remote route lease did not advance."
                )
                log("Remote route bootstrap rejected non-advancing lease for \(endpoint)")
                return
            }

            let configuration = allocation.configuration
            let settings = CompanionDevelopmentRelaySettings(
                isEnabled: true,
                host: configuration.host,
                port: configuration.port,
                relayID: configuration.relayID,
                relaySecret: configuration.relaySecret?.takeIfNotEmpty()
                    ?? preferredRelaySecret
                    ?? Self.generateRelaySecret(),
                isEnvironmentOverride: false,
                allowsPrivateOverlay: allowsPrivateOverlayRelay
            )
            Self.saveDevelopmentRelaySettings(
                settings,
                deviceID: macDeviceID,
                defaults: userDefaults,
                relaySecretStore: relaySecretStore
            )
            if let lease = allocation.lease {
                Self.saveRemoteRouteLease(lease, relaySettings: settings, defaults: userDefaults)
            } else if Self.hasDynamicRelayAllocationEnvironment(environment) {
                Self.clearSavedRemoteRouteLease(defaults: userDefaults)
            }
            developmentRelaySettings = settings
            relayConfiguration = Self.relayConfiguration(for: settings, lease: allocation.lease)
            allocatedRemoteRouteLease = allocation.lease
            developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
                status: .stopped,
                endpoint: settings.endpointLabel
            )
            if shouldRestartRelayClient {
                restartRelayClientIfRunning()
            }
            remoteRoutePreparationIssue = nil
            refreshTransportStatusText()
            log("Remote route bootstrap allocated route \(settings.endpointLabel ?? "configured route")")
        } catch {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationFailed,
                message: error.localizedDescription
            )
            log("Remote route bootstrap failed: \(error.localizedDescription)")
        }
    }

    private func prepareRemoteRelayRouteForPairing() {
        if canAttemptAutomaticRemoteRouteAllocation {
            if !hasFreshCurrentRemoteRouteLease {
                allocateRemoteRelayRouteIfAvailable()
            }
            return
        }
        guard relayConfiguration != nil else {
            allocateRemoteRelayRouteIfAvailable()
            return
        }
        guard isDevelopmentRelayRouteEligibleForQRCode else {
            return
        }
        guard shouldRefreshConfiguredRelayRouteLeaseForPairing else {
            return
        }
        if allocatedRemoteRouteLease?.isExpired(renewalMarginSeconds: pairingQRCodeLeaseRenewalMarginSeconds) == true {
            refreshConfiguredRelayRouteLeaseIfAvailable()
            return
        }
        if allocatedRemoteRouteLease == nil {
            refreshConfiguredRelayRouteLeaseIfAvailable()
            return
        }
        allocateRemoteRelayRouteIfAvailable()
    }

    private func refreshConfiguredRelayRouteLeaseIfAvailable() {
        guard developmentRelaySettings.isEnabled,
              let currentConfiguration = relayConfiguration
        else {
            return
        }
        guard isEligibleAutomaticRelayHost(currentConfiguration.host) else {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .routeLeaseRefreshRejected,
                endpoint: developmentRelaySettings.endpointLabel,
                message: "This AetherLink Runtime connection address is not reachable from another network."
            )
            log("Remote route lease refresh rejected unreachable connection address \(currentConfiguration.host)")
            return
        }
        guard let relaySecret = currentConfiguration.relaySecret?.takeIfNotEmpty()
            ?? developmentRelaySettings.relaySecret?.takeIfNotEmpty()
        else {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .routeLeaseSecretMissing,
                endpoint: developmentRelaySettings.endpointLabel,
                message: "Route secret is missing."
            )
            log("Remote route lease refresh skipped: route secret is missing")
            return
        }

        do {
            let authorization = try relayAllocationAuthorization()
            let serviceAllocation = try relayServiceRouteAllocator.allocateRelayRoute(
                host: currentConfiguration.host,
                port: currentConfiguration.port,
                routeToken: discoveryRouteToken,
                allocationToken: environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty(),
                runtimeIdentity: authorization.identity,
                identityAuthorizationSigner: authorization.signer,
                timeout: 5
            )
            let allocation = try serviceAllocation.attachingEndpointSecret(
                relaySecret,
                runtimeIdentity: authorization.identity,
                identityAuthorizationSigner: authorization.signer
            )
            guard isEligibleAutomaticRelayHost(allocation.configuration.host) else {
                let endpoint = "\(allocation.configuration.host):\(allocation.configuration.port)"
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .routeLeaseRefreshRejected,
                    endpoint: endpoint,
                    message: "This AetherLink Runtime connection address is not reachable from another network."
                )
                log("Remote route lease refresh rejected unreachable connection address \(allocation.configuration.host)")
                return
            }
            guard acceptsRemoteRouteAllocation(allocation) else {
                let endpoint = "\(allocation.configuration.host):\(allocation.configuration.port)"
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .routeLeaseRefreshRejected,
                    endpoint: endpoint,
                    message: "Remote route lease did not advance."
                )
                log("Remote route lease refresh rejected non-advancing lease for \(endpoint)")
                return
            }
            let configuration = allocation.configuration
            let settings = CompanionDevelopmentRelaySettings(
                isEnabled: true,
                host: configuration.host,
                port: configuration.port,
                relayID: configuration.relayID,
                relaySecret: configuration.relaySecret?.takeIfNotEmpty() ?? relaySecret,
                isEnvironmentOverride: developmentRelaySettings.isEnvironmentOverride,
                allowsPrivateOverlay: allowsPrivateOverlayRelay
            )
            applyDevelopmentRelaySettings(settings, lease: allocation.lease)
            log("Remote route lease refreshed: \(settings.endpointLabel ?? "configured route")")
        } catch {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .routeLeaseRefreshFailed,
                endpoint: developmentRelaySettings.endpointLabel,
                message: error.localizedDescription
            )
            log("Remote route lease refresh failed: \(error.localizedDescription)")
        }
    }

    private func renewSavedBootstrapRelayRouteIfNeeded() {
        guard developmentRelaySettings.isEnabled else { return }
        guard relayConfiguration != nil else { return }
        guard canAttemptAutomaticRemoteRouteAllocation else { return }
        guard !hasFreshCurrentRemoteRouteLease else { return }
        allocateRemoteRelayRouteIfAvailable(restartRelayClientIfRunning: false)
    }

    private var hasFreshCurrentRemoteRouteLease: Bool {
        guard relayConfiguration != nil,
              let allocatedRemoteRouteLease
        else {
            return false
        }
        return isRelayRouteLeaseFreshForPairingQRCode(allocatedRemoteRouteLease)
    }

    private func acceptsRemoteRouteAllocation(_ allocation: CompanionRemoteRelayRouteAllocation) -> Bool {
        guard let incomingLease = allocation.lease,
              let currentLease = allocatedRemoteRouteLease,
              allocation.configuration.relayID == developmentRelaySettings.relayID
        else {
            return true
        }
        return incomingLease.isAdvancingReplacement(of: currentLease)
    }

    private func isEligibleAutomaticRelayHost(_ host: String) -> Bool {
        CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: host)?
            .blocksRemoteQRCode(allowsPrivateOverlay: allowsPrivateOverlayRelay) != true
    }

    private var allowsPrivateOverlayRelay: Bool {
        developmentRelaySettings.allowsPrivateOverlay ||
            bootstrapRelaySettings.allowsPrivateOverlay ||
            Self.allowsPrivateOverlayRelayEnvironment(environment)
    }

    private var canAttemptAutomaticRemoteRouteAllocation: Bool {
        remoteRelayRouteAllocator.canAllocateRemoteRelayRoute ||
            Self.hasDynamicRelayAllocationEnvironment(environment) ||
            bootstrapRelaySettings.isEnabled
    }

    private var shouldRefreshConfiguredRelayRouteLeaseForPairing: Bool {
        guard let relayConfiguration else { return false }
        return CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: relayConfiguration.host) == nil
    }

    private static func relayScope(
        forRelayHost host: String,
        allowsPrivateOverlay: Bool
    ) -> String? {
        switch CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: host) {
        case .loopback:
            return "usb_reverse"
        case .privateNetwork:
            return allowsPrivateOverlay ? "private_overlay" : nil
        case nil:
            return "remote"
        case .invalidFormat, .localName:
            return nil
        }
    }

    private func applyDevelopmentRelaySettings(
        _ settings: CompanionDevelopmentRelaySettings,
        lease: CompanionRemoteRouteLease?,
        restartRelayClient: Bool = true
    ) {
        Self.saveDevelopmentRelaySettings(
            settings,
            deviceID: macDeviceID,
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        if let lease {
            Self.saveRemoteRouteLease(lease, relaySettings: settings, defaults: userDefaults)
        } else {
            Self.clearSavedRemoteRouteLease(defaults: userDefaults)
        }
        developmentRelaySettings = settings
        relayConfiguration = Self.relayConfiguration(for: settings, lease: lease)
        allocatedRemoteRouteLease = lease
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
            status: .stopped,
            endpoint: settings.endpointLabel
        )
        remoteRoutePreparationIssue = nil
        if restartRelayClient {
            restartRelayClientIfRunning()
        }
        refreshTransportStatusText()
    }

    public func removeTrustedDevice(_ device: TrustedDevice) async {
        let clientKeyFingerprint = try? PairedRelayAllocationAuthorization.publicKeyFingerprint(
            publicKeyBase64: device.publicKeyBase64
        )
        if let clientKeyFingerprint {
            invalidatePairLifecycle(fingerprint: clientKeyFingerprint)
            runtimeConnectionManager.stopPair(fingerprint: clientKeyFingerprint)
        }
        do {
            try await trustedDeviceStore.remove(deviceID: device.id)
            if let clientKeyFingerprint {
                pairScopedRelayRoutes.removeValue(forKey: clientKeyFingerprint)
                do {
                    try pairScopedRelayRouteStore.remove(
                        clientKeyFingerprint: clientKeyFingerprint
                    )
                } catch {
                    log("Pair-scoped route removal failed")
                }
            }
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
        logs.insert(sanitizedCompanionLogMessage(message), at: 0)
        logs = Array(logs.prefix(50))
    }

    private func startRelayClientIfConfigured() {
        guard let relayConfiguration else { return }
        let authorizedConfiguration: RelayPeerConfiguration
        do {
            let authorization = try relayAllocationAuthorization()
            authorizedConfiguration = RelayPeerConfiguration(
                host: relayConfiguration.host,
                port: relayConfiguration.port,
                relayID: relayConfiguration.relayID,
                relaySecret: relayConfiguration.relaySecret,
                relayNonce: relayConfiguration.relayNonce,
                reconnectDelay: relayConfiguration.reconnectDelay,
                controlLineTimeout: relayConfiguration.controlLineTimeout,
                runtimeIdentity: authorization.identity,
                identityAuthorizationSigner: authorization.signer
            )
            self.relayConfiguration = authorizedConfiguration
        } catch {
            handleRelayStatus(.failed(error.localizedDescription), endpoint: "\(relayConfiguration.host):\(relayConfiguration.port)")
            return
        }
        let router = runtimeRouter!
        let endpoint = "\(authorizedConfiguration.host):\(authorizedConfiguration.port)"
        runtimeConnectionManager.startBootstrap(
            configuration: authorizedConfiguration,
            onStatusChange: { [weak self] status in
                self?.handleRelayStatus(status, endpoint: endpoint)
            }
        ) { [router, weak self] envelope, sink in
            Task { @MainActor in
                self?.log("Relay received \(envelope.type)")
            }
            router.handle(envelope, sink: sink)
        }
    }

    private func startPairScopedTransports(
        clientKeyFingerprint: String,
        configuration: RelayPeerConfiguration
    ) {
        let router = runtimeRouter!
        runtimeConnectionManager.startPairPrivateOverlay(
            fingerprint: clientKeyFingerprint,
            onStatusChange: { [weak self] status in
                switch status {
                case .ready:
                    self?.log("Pair-scoped private overlay ready")
                case .failed:
                    self?.log("Pair-scoped private overlay failed")
                case .stopped, .connecting:
                    break
                }
            }
        ) { [router, weak self] envelope, sink in
            Task { @MainActor in
                self?.log("Pair-scoped private overlay received \(envelope.type)")
            }
            router.handle(envelope, sink: sink)
        }

        let authorizedConfiguration: RelayPeerConfiguration
        do {
            let authorization = try relayAllocationAuthorization()
            authorizedConfiguration = RelayPeerConfiguration(
                host: configuration.host,
                port: configuration.port,
                relayID: configuration.relayID,
                relaySecret: configuration.relaySecret,
                relayNonce: configuration.relayNonce,
                reconnectDelay: configuration.reconnectDelay,
                controlLineTimeout: configuration.controlLineTimeout,
                runtimeIdentity: authorization.identity,
                identityAuthorizationSigner: authorization.signer
            )
        } catch {
            log("Pair-scoped remote route could not start")
            return
        }

        runtimeConnectionManager.startPair(
            fingerprint: clientKeyFingerprint,
            configuration: authorizedConfiguration,
            onStatusChange: { [weak self] status in
                switch status {
                case .ready, .waitingForPeer:
                    self?.log("Pair-scoped remote route ready")
                case .failed:
                    self?.log("Pair-scoped remote route failed")
                case .stopped, .connecting, .reconnecting:
                    break
                }
            }
        ) { [router, weak self] envelope, sink in
            Task { @MainActor in
                self?.log("Pair-scoped relay received \(envelope.type)")
            }
            router.handle(envelope, sink: sink)
        }
    }

    private func beginPairLifecycleRefresh(
        fingerprint: String
    ) -> (runtime: UUID, pair: UUID, sequence: UInt64) {
        let pairGeneration = pairLifecycleGenerations[fingerprint] ?? UUID()
        pairLifecycleGenerations[fingerprint] = pairGeneration
        let sequence = (pairRefreshSequences[fingerprint] ?? 0) + 1
        pairRefreshSequences[fingerprint] = sequence
        inFlightPairRefreshSequences[fingerprint, default: []].insert(sequence)
        return (runtimeLifecycleGeneration, pairGeneration, sequence)
    }

    private func finishPairLifecycleRefresh(fingerprint: String, sequence: UInt64) {
        inFlightPairRefreshSequences[fingerprint]?.remove(sequence)
        if inFlightPairRefreshSequences[fingerprint]?.isEmpty == true {
            inFlightPairRefreshSequences.removeValue(forKey: fingerprint)
        }
        reconcilePendingPairActivation(fingerprint: fingerprint)
    }

    private func invalidatePairLifecycle(fingerprint: String) {
        pairLifecycleGenerations[fingerprint] = UUID()
        inFlightPairRefreshSequences.removeValue(forKey: fingerprint)
        pendingPairedRelayActivations.removeValue(forKey: fingerprint)
    }

    private func reconcilePendingPairActivation(fingerprint: String) {
        guard let pendingActivation = pendingPairedRelayActivations[fingerprint],
              pendingActivation.activationRequested,
              !(inFlightPairRefreshSequences[fingerprint] ?? []).contains(where: {
                  $0 > pendingActivation.refreshSequence
              }),
              pendingActivation.result.runtimeDeviceID == macDeviceID,
              pendingActivation.result.runtimeKeyFingerprint == macFingerprint,
              runtimeLifecycleGeneration == pendingActivation.runtimeLifecycleGeneration,
              pairLifecycleGenerations[fingerprint] == pendingActivation.pairLifecycleGeneration,
              let storedRoute = pairScopedRelayRoutes[fingerprint],
              let relayHost = pendingActivation.result.relayHost,
              relayHost == storedRoute.host,
              let relayPort = pendingActivation.result.relayPort,
              relayPort == Int(storedRoute.port),
              let relayID = pendingActivation.result.relayID,
              relayID == storedRoute.relayID,
              let relaySecret = pendingActivation.result.relaySecret,
              relaySecret == storedRoute.relaySecret,
              let expiresAtEpochMillis = pendingActivation.result.relayExpiresAtEpochMillis,
              expiresAtEpochMillis == storedRoute.relayExpiresAtEpochMillis,
              let relayNonce = pendingActivation.result.relayNonce,
              relayNonce == storedRoute.relayNonce,
              let ticketGeneration = pendingActivation.result.relayTicketGeneration,
              ticketGeneration == storedRoute.ticketGeneration
        else {
            return
        }
        pendingPairedRelayActivations.removeValue(forKey: fingerprint)
        startPairScopedTransports(
            clientKeyFingerprint: fingerprint,
            configuration: pairScopedRelayConfiguration(storedRoute)
        )
        if pendingActivation.rotatesBootstrapRoute {
            rotateBootstrapRouteAfterPairClaim()
        }
    }

    private func startRestoredPairScopedTransports(now: Date = Date()) {
        let nowEpochMillis = Int64((now.timeIntervalSince1970 * 1_000).rounded())
        for route in pairScopedRelayRoutes.values.sorted(by: {
            $0.clientKeyFingerprint < $1.clientKeyFingerprint
        }) where route.relayExpiresAtEpochMillis > nowEpochMillis {
            startPairScopedTransports(
                clientKeyFingerprint: route.clientKeyFingerprint,
                configuration: pairScopedRelayConfiguration(route)
            )
        }
    }

    private func pairScopedRelayConfiguration(
        _ route: ResolvedPairScopedRelayRoute
    ) -> RelayPeerConfiguration {
        RelayPeerConfiguration(
            host: route.host,
            port: route.port,
            relayID: route.relayID,
            relaySecret: route.relaySecret,
            relayNonce: route.relayNonce
        )
    }

    private func rotateBootstrapRouteAfterPairClaim() {
        let previousSettings = developmentRelaySettings
        discoveryRouteToken = UUID().uuidString
        userDefaults.set(discoveryRouteToken, forKey: "aetherlink.discovery_route_token")
        if previousSettings.isEnabled,
           !previousSettings.host.isEmpty,
           let relaySecret = previousSettings.relaySecret {
            applyDevelopmentRelaySettings(
                CompanionDevelopmentRelaySettings(
                    isEnabled: true,
                    host: previousSettings.host,
                    port: previousSettings.port,
                    relayID: discoveryRouteToken,
                    relaySecret: relaySecret,
                    isEnvironmentOverride: previousSettings.isEnvironmentOverride,
                    allowsPrivateOverlay: previousSettings.allowsPrivateOverlay
                ),
                lease: nil,
                restartRelayClient: false
            )
        } else {
            Self.clearSavedRemoteRouteLease(defaults: userDefaults)
            allocatedRemoteRouteLease = nil
        }
        runtimeConnectionManager.retireBootstrapAfterCurrentConnection()
        allocateRemoteRelayRouteIfAvailable()
        if transportState.state == .advertising {
            let localStatus = runtimeConnectionManager.refreshLocalAdvertisement(
                metadata: runtimeAdvertisementMetadata
            )
            transportState = Self.transportStatus(from: localStatus)
            refreshTransportStatusText()
        }
    }

    private static func relayConfiguration(
        for settings: CompanionDevelopmentRelaySettings,
        lease: CompanionRemoteRouteLease?
    ) -> RelayPeerConfiguration? {
        settings.relayConfiguration?.withRelayNonce(lease?.nonce)
    }

    private func restartRelayClientIfRunning() {
        runtimeConnectionManager.stopBootstrap()
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
            clearRelayConnectionIssueIfRouteIsUsable()
            log("Remote route ready: \(endpoint)")
            generatePendingRemotePairingQRCodeIfReady()
        case .waitingForPeer:
            clearRelayConnectionIssueIfRouteIsUsable()
            generatePendingRemotePairingQRCodeIfReady()
        case .failed(let message):
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .relayConnectionFailed,
                endpoint: endpoint,
                message: message
            )
            log("Remote route failed: \(endpoint): \(message)")
            renewRelayRouteAfterFailureIfNeeded(endpoint: endpoint)
        case .reconnecting(let message):
            if let message {
                log("Remote route reconnecting: \(endpoint): \(message)")
            } else {
                log("Remote route reconnecting: \(endpoint)")
            }
        default:
            break
        }
    }

    private func clearRelayConnectionIssueIfRouteIsUsable() {
        if isDevelopmentRelayRoutePreparedForQRCode {
            remoteRoutePreparationIssue = nil
            return
        }
        if remoteRoutePreparationIssue?.kind == .relayConnectionFailed {
            remoteRoutePreparationIssue = nil
        }
    }

    private func renewRelayRouteAfterFailureIfNeeded(endpoint: String) {
        guard isRuntimeStarted else { return }
        guard relayConfiguration != nil, developmentRelaySettings.endpointLabel == endpoint else { return }
        guard canAttemptAutomaticRemoteRouteAllocation else { return }
        allocateRemoteRelayRouteIfAvailable(restartRelayClientIfRunning: true)
    }

    private func relayRouteLeaseForPairing(
        relayConfiguration: RelayPeerConfiguration?
    ) -> (expiresAtEpochMillis: Int64, nonce: String, ticketGeneration: Int64?)? {
        guard relayConfiguration != nil else { return nil }
        if let allocatedRemoteRouteLease {
            guard isRelayRouteLeaseFreshForPairingQRCode(allocatedRemoteRouteLease) else { return nil }
            return (
                expiresAtEpochMillis: allocatedRemoteRouteLease.expiresAtEpochMillis,
                nonce: allocatedRemoteRouteLease.nonce,
                ticketGeneration: allocatedRemoteRouteLease.ticketGeneration
            )
        }
        return nil
    }

    private func generatePendingRemotePairingQRCodeIfReady() {
        guard shouldGenerateRemotePairingQRCodeWhenRelayReady else { return }
        guard shouldIncludeDevelopmentRelayInPairingQRCode else { return }
        shouldGenerateRemotePairingQRCodeWhenRelayReady = false
        beginPairing(routePolicy: .allowLocalDiagnostic)
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

    private func relayAllocationAuthorization() throws -> (
        identity: RelayRuntimeIdentity,
        signer: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning
    ) {
        guard let signer = runtimeIdentityAuthorizationSigner else {
            throw RelayServiceRouteAllocationError.signingIdentityUnavailable
        }
        let identity = try signer.relayRuntimeIdentity()
        guard identity.publicKeyBase64 == runtimeIdentityKey.publicKeyBase64,
              identity.fingerprint == runtimeIdentityKey.fingerprint
        else {
            throw RelayServiceRouteAllocationError.signingIdentityMismatch
        }
        return (identity, signer)
    }

    private var localPairingRouteHost: String? {
        guard transportState.state == .advertising else { return nil }
        return runtimeRouteHostProvider()
    }

    private var discoveryRouteToken: String

    private var runtimeAdvertisementMetadata: RuntimeAdvertisementMetadata {
        RuntimeAdvertisementMetadata(
            routeToken: discoveryRouteToken
        )
    }

    private static func loadDevelopmentRelaySettings(
        deviceID: String,
        routeToken: String,
        environment: [String: String],
        defaults: UserDefaults,
        relaySecretStore: any CompanionRelaySecretStoring
    ) -> CompanionDevelopmentRelaySettings {
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
                isEnvironmentOverride: true,
                allowsPrivateOverlay: Self.allowsPrivateOverlayRelayEnvironment(environment)
            )
        }
        if let host = environment["AETHERLINK_BOOTSTRAP_RELAY_HOST"]?.takeIfNotEmpty() {
            let port = UInt16(environment["AETHERLINK_BOOTSTRAP_RELAY_PORT"] ?? "") ?? 43171
            let savedLeaseRelayID: String?
            if defaults.string(forKey: RelayDefaults.leaseHost) == host,
               UInt16(exactly: defaults.integer(forKey: RelayDefaults.leasePort)) == port {
                savedLeaseRelayID = defaults.string(forKey: RelayDefaults.leaseRelayID)?.takeIfNotEmpty()
            } else {
                savedLeaseRelayID = nil
            }
            let relayID = environment["AETHERLINK_BOOTSTRAP_RELAY_ID"]?.takeIfNotEmpty()
                ?? savedLeaseRelayID
                ?? routeToken
            let relaySecret = environment["AETHERLINK_BOOTSTRAP_RELAY_SECRET"]?.takeIfNotEmpty()
                ?? environment["AETHERLINK_BOOTSTRAP_RELAY_FRAME_SECRET"]?.takeIfNotEmpty()
                ?? loadSavedRelaySecret(
                    deviceID: deviceID,
                    relayID: relayID,
                    defaults: defaults,
                    relaySecretStore: relaySecretStore
                )
            return CompanionDevelopmentRelaySettings(
                isEnabled: true,
                host: host,
                port: port,
                relayID: relayID,
                relaySecret: relaySecret,
                isEnvironmentOverride: true,
                allowsPrivateOverlay: Self.allowsPrivateOverlayRelayEnvironment(environment)
            )
        }

        guard let host = defaults.string(forKey: RelayDefaults.host)?.takeIfNotEmpty() else {
            return .disabled
        }
        let storedPort = defaults.integer(forKey: RelayDefaults.port)
        let port = UInt16(exactly: storedPort).flatMap { $0 == 0 ? nil : $0 } ?? 43171
        let relayID = defaults.string(forKey: RelayDefaults.relayID)?.takeIfNotEmpty() ?? routeToken
        let relaySecret = loadSavedRelaySecret(
            deviceID: deviceID,
            relayID: relayID,
            defaults: defaults,
            relaySecretStore: relaySecretStore
        )
        return CompanionDevelopmentRelaySettings(
            isEnabled: true,
            host: host,
            port: port,
            relayID: relayID,
            relaySecret: relaySecret,
            isEnvironmentOverride: false,
            allowsPrivateOverlay: defaults.bool(forKey: RelayDefaults.allowsPrivateOverlay)
        )
    }

    private static func allowsPrivateOverlayRelayEnvironment(_ environment: [String: String]) -> Bool {
        environment["AETHERLINK_RELAY_ALLOW_PRIVATE_OVERLAY"]?.isTruthyEnvironmentValue == true ||
            environment["AETHERLINK_BOOTSTRAP_RELAY_ALLOW_PRIVATE_OVERLAY"]?.isTruthyEnvironmentValue == true ||
            environment["AETHERLINK_ALLOW_PRIVATE_OVERLAY_RELAY"]?.isTruthyEnvironmentValue == true
    }

    private static func makeRemoteRelayRouteAllocator(
        environment: [String: String],
        bootstrapRelaySettings: CompanionBootstrapRelaySettings,
        relayServiceRouteAllocator: any RelayServiceRouteAllocating
    ) -> EnvironmentRemoteRelayRouteAllocator {
        EnvironmentRemoteRelayRouteAllocator(
            environment: environment,
            storedBootstrapRelaySettings: bootstrapRelaySettings,
            relayServiceAllocator: relayServiceRouteAllocator
        )
    }

    private static func hasBootstrapRelayEnvironment(_ environment: [String: String]) -> Bool {
        environment["AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS"]?.takeIfNotEmpty() != nil ||
            environment["AETHERLINK_BOOTSTRAP_RELAY_HOST"]?.takeIfNotEmpty() != nil
    }

    private static func hasDynamicRelayAllocationEnvironment(_ environment: [String: String]) -> Bool {
        if environment["AETHERLINK_RELAY_HOST"]?.takeIfNotEmpty() != nil {
            return environment["AETHERLINK_RELAY_ID"]?.takeIfNotEmpty() == nil ||
                environment["AETHERLINK_RELAY_SECRET"]?.takeIfNotEmpty() == nil
        }
        guard hasBootstrapRelayEnvironment(environment) else { return false }
        return environment["AETHERLINK_BOOTSTRAP_RELAY_ID"]?.takeIfNotEmpty() == nil ||
            environment["AETHERLINK_BOOTSTRAP_RELAY_SECRET"]?.takeIfNotEmpty() == nil
    }

    private static func saveDevelopmentRelaySettings(
        _ settings: CompanionDevelopmentRelaySettings,
        deviceID: String,
        defaults: UserDefaults,
        relaySecretStore: any CompanionRelaySecretStoring
    ) {
        defaults.set(settings.host, forKey: RelayDefaults.host)
        defaults.set(Int(settings.port), forKey: RelayDefaults.port)
        defaults.set(settings.relayID, forKey: RelayDefaults.relayID)
        defaults.set(settings.allowsPrivateOverlay, forKey: RelayDefaults.allowsPrivateOverlay)
        let previousSecretRef = defaults.string(forKey: RelayDefaults.secretRef)?.takeIfNotEmpty()
        if let relaySecret = settings.relaySecret?.takeIfNotEmpty() {
            let secretRef = relaySecretRef(deviceID: deviceID, relayID: settings.relayID)
            relaySecretStore.saveSecret(relaySecret, for: secretRef)
            defaults.set(secretRef, forKey: RelayDefaults.secretRef)
            if let previousSecretRef, previousSecretRef != secretRef {
                relaySecretStore.removeSecret(for: previousSecretRef)
            }
        } else {
            if let previousSecretRef {
                relaySecretStore.removeSecret(for: previousSecretRef)
            }
            defaults.removeObject(forKey: RelayDefaults.secretRef)
        }
        defaults.removeObject(forKey: RelayDefaults.secret)
    }

    private static func clearSavedDevelopmentRelaySettings(
        defaults: UserDefaults,
        relaySecretStore: any CompanionRelaySecretStoring
    ) {
        if let secretRef = defaults.string(forKey: RelayDefaults.secretRef)?.takeIfNotEmpty() {
            relaySecretStore.removeSecret(for: secretRef)
        }
        defaults.removeObject(forKey: RelayDefaults.host)
        defaults.removeObject(forKey: RelayDefaults.port)
        defaults.removeObject(forKey: RelayDefaults.relayID)
        defaults.removeObject(forKey: RelayDefaults.secret)
        defaults.removeObject(forKey: RelayDefaults.secretRef)
        defaults.removeObject(forKey: RelayDefaults.allowsPrivateOverlay)
    }

    private static func loadSavedRemoteRouteLease(
        defaults: UserDefaults,
        relaySettings: CompanionDevelopmentRelaySettings
    ) -> CompanionRemoteRouteLease? {
        let expiresAtEpochMillis = Int64(defaults.integer(forKey: RelayDefaults.leaseExpiresAt))
        guard expiresAtEpochMillis > 0,
              let nonce = defaults.string(forKey: RelayDefaults.leaseNonce)?.takeIfNotEmpty()
        else {
            return nil
        }
        guard defaults.string(forKey: RelayDefaults.leaseHost) == relaySettings.host,
              UInt16(exactly: defaults.integer(forKey: RelayDefaults.leasePort)) == relaySettings.port,
              defaults.string(forKey: RelayDefaults.leaseRelayID) == relaySettings.relayID
        else {
            return nil
        }
        let storedGeneration = Int64(defaults.integer(forKey: RelayDefaults.leaseTicketGeneration))
        return CompanionRemoteRouteLease(
            expiresAtEpochMillis: expiresAtEpochMillis,
            nonce: nonce,
            ticketGeneration: storedGeneration > 0 ? storedGeneration : nil
        )
    }

    private static func saveRemoteRouteLease(
        _ lease: CompanionRemoteRouteLease,
        relaySettings: CompanionDevelopmentRelaySettings,
        defaults: UserDefaults
    ) {
        defaults.set(Int(lease.expiresAtEpochMillis), forKey: RelayDefaults.leaseExpiresAt)
        defaults.set(lease.nonce, forKey: RelayDefaults.leaseNonce)
        if let ticketGeneration = lease.ticketGeneration {
            defaults.set(Int(ticketGeneration), forKey: RelayDefaults.leaseTicketGeneration)
        } else {
            defaults.removeObject(forKey: RelayDefaults.leaseTicketGeneration)
        }
        defaults.set(relaySettings.host, forKey: RelayDefaults.leaseHost)
        defaults.set(Int(relaySettings.port), forKey: RelayDefaults.leasePort)
        defaults.set(relaySettings.relayID, forKey: RelayDefaults.leaseRelayID)
    }

    private static func clearSavedRemoteRouteLease(defaults: UserDefaults) {
        defaults.removeObject(forKey: RelayDefaults.leaseExpiresAt)
        defaults.removeObject(forKey: RelayDefaults.leaseNonce)
        defaults.removeObject(forKey: RelayDefaults.leaseTicketGeneration)
        defaults.removeObject(forKey: RelayDefaults.leaseHost)
        defaults.removeObject(forKey: RelayDefaults.leasePort)
        defaults.removeObject(forKey: RelayDefaults.leaseRelayID)
    }

    private static func loadBootstrapRelaySettings(
        defaults: UserDefaults,
        relaySecretStore: any CompanionRelaySecretStoring
    ) -> CompanionBootstrapRelaySettings {
        guard let endpoints = defaults.string(forKey: BootstrapRelayDefaults.endpoints)?.takeIfNotEmpty() else {
            return .disabled
        }
        return CompanionBootstrapRelaySettings(
            isEnabled: true,
            endpoints: endpoints,
            allocationToken: loadSavedBootstrapAllocationToken(
                endpoints: endpoints,
                defaults: defaults,
                relaySecretStore: relaySecretStore
            ),
            allowsPrivateOverlay: defaults.bool(forKey: BootstrapRelayDefaults.allowsPrivateOverlay)
        )
    }

    private static func saveBootstrapRelaySettings(
        _ settings: CompanionBootstrapRelaySettings,
        defaults: UserDefaults,
        relaySecretStore: any CompanionRelaySecretStoring
    ) {
        defaults.set(settings.endpoints, forKey: BootstrapRelayDefaults.endpoints)
        defaults.set(settings.allowsPrivateOverlay, forKey: BootstrapRelayDefaults.allowsPrivateOverlay)
        let previousTokenRef = defaults.string(forKey: BootstrapRelayDefaults.allocationTokenRef)?.takeIfNotEmpty()
        if let allocationToken = settings.allocationToken?.takeIfNotEmpty() {
            let tokenRef = bootstrapAllocationTokenRef(endpoints: settings.endpoints)
            relaySecretStore.saveSecret(allocationToken, for: tokenRef)
            defaults.set(tokenRef, forKey: BootstrapRelayDefaults.allocationTokenRef)
            if let previousTokenRef, previousTokenRef != tokenRef {
                relaySecretStore.removeSecret(for: previousTokenRef)
            }
        } else {
            if let previousTokenRef {
                relaySecretStore.removeSecret(for: previousTokenRef)
            }
            defaults.removeObject(forKey: BootstrapRelayDefaults.allocationTokenRef)
        }
        defaults.removeObject(forKey: BootstrapRelayDefaults.allocationToken)
    }

    private static func clearSavedBootstrapRelaySettings(
        defaults: UserDefaults,
        relaySecretStore: any CompanionRelaySecretStoring
    ) {
        if let tokenRef = defaults.string(forKey: BootstrapRelayDefaults.allocationTokenRef)?.takeIfNotEmpty() {
            relaySecretStore.removeSecret(for: tokenRef)
        }
        defaults.removeObject(forKey: BootstrapRelayDefaults.endpoints)
        defaults.removeObject(forKey: BootstrapRelayDefaults.allocationToken)
        defaults.removeObject(forKey: BootstrapRelayDefaults.allocationTokenRef)
        defaults.removeObject(forKey: BootstrapRelayDefaults.allowsPrivateOverlay)
    }

    private static func loadSavedRelaySecret(
        deviceID: String,
        relayID: String,
        defaults: UserDefaults,
        relaySecretStore: any CompanionRelaySecretStoring
    ) -> String? {
        let legacySecret = defaults.string(forKey: RelayDefaults.secret)?.takeIfNotEmpty()
        let storedSecretRef = defaults.string(forKey: RelayDefaults.secretRef)?.takeIfNotEmpty()
        if let legacySecret {
            let secretRef = relaySecretRef(deviceID: deviceID, relayID: relayID)
            relaySecretStore.saveSecret(legacySecret, for: secretRef)
            defaults.set(secretRef, forKey: RelayDefaults.secretRef)
            defaults.removeObject(forKey: RelayDefaults.secret)
            if let storedSecretRef, storedSecretRef != secretRef {
                relaySecretStore.removeSecret(for: storedSecretRef)
            }
            return legacySecret
        }
        guard let storedSecretRef else { return nil }
        guard let secret = relaySecretStore.readSecret(for: storedSecretRef)?.takeIfNotEmpty() else {
            defaults.removeObject(forKey: RelayDefaults.secretRef)
            return nil
        }
        return secret
    }

    private static func loadSavedBootstrapAllocationToken(
        endpoints: String,
        defaults: UserDefaults,
        relaySecretStore: any CompanionRelaySecretStoring
    ) -> String? {
        let legacyToken = defaults.string(forKey: BootstrapRelayDefaults.allocationToken)?.takeIfNotEmpty()
        let storedTokenRef = defaults.string(forKey: BootstrapRelayDefaults.allocationTokenRef)?.takeIfNotEmpty()
        if let legacyToken {
            let tokenRef = bootstrapAllocationTokenRef(endpoints: endpoints)
            relaySecretStore.saveSecret(legacyToken, for: tokenRef)
            defaults.set(tokenRef, forKey: BootstrapRelayDefaults.allocationTokenRef)
            defaults.removeObject(forKey: BootstrapRelayDefaults.allocationToken)
            if let storedTokenRef, storedTokenRef != tokenRef {
                relaySecretStore.removeSecret(for: storedTokenRef)
            }
            return legacyToken
        }
        guard let storedTokenRef else { return nil }
        guard let token = relaySecretStore.readSecret(for: storedTokenRef)?.takeIfNotEmpty() else {
            defaults.removeObject(forKey: BootstrapRelayDefaults.allocationTokenRef)
            return nil
        }
        return token
    }

    private static func relaySecretRef(deviceID: String, relayID: String) -> String {
        secretStoreRef(prefix: "relay-v1", parts: [deviceID, relayID])
    }

    private static func bootstrapAllocationTokenRef(endpoints: String) -> String {
        secretStoreRef(prefix: "bootstrap-token-v1", parts: [endpoints])
    }

    private static func secretStoreRef(prefix: String, parts: [String]) -> String {
        let joined = parts.joined(separator: "\n")
        let digest = SHA256.hash(data: Data(joined.utf8))
        let hex = digest.map { String(format: "%02x", $0) }.joined()
        return "\(prefix)-\(hex)"
    }

    private static func generateRelaySecret() -> String {
        generateRuntimeLocalRelaySecret()
    }

    private enum RelayDefaults {
        static let host = "aetherlink.relay.host"
        static let port = "aetherlink.relay.port"
        static let relayID = "aetherlink.relay.id"
        static let secret = "aetherlink.relay.secret"
        static let secretRef = "aetherlink.relay.secret_ref"
        static let allowsPrivateOverlay = "aetherlink.relay.allows_private_overlay"
        static let leaseExpiresAt = "aetherlink.relay.lease_expires_at"
        static let leaseNonce = "aetherlink.relay.lease_nonce"
        static let leaseTicketGeneration = "aetherlink.relay.lease_ticket_generation"
        static let leaseHost = "aetherlink.relay.lease_host"
        static let leasePort = "aetherlink.relay.lease_port"
        static let leaseRelayID = "aetherlink.relay.lease_id"
    }

    private enum BootstrapRelayDefaults {
        static let endpoints = "aetherlink.bootstrap_relay.endpoints"
        static let allocationToken = "aetherlink.bootstrap_relay.allocation_token"
        static let allocationTokenRef = "aetherlink.bootstrap_relay.allocation_token_ref"
        static let allowsPrivateOverlay = "aetherlink.bootstrap_relay.allows_private_overlay"
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

    private static func loadOrCreateRuntimeIdentityKey(
        deviceID: String,
        environment: [String: String]
    ) -> (
        key: RuntimeIdentityKey,
        signer: (
            any RuntimeChallengeSigning
                & RelayIdentityAuthorizationSigning
                & InitialPairingRuntimeResultSigning
                & PairedRelayAllocationRuntimeSigning
        )?,
        warning: String?
    ) {
        if let filePath = runtimeIdentityFilePathOverride(environment: environment) {
            let fileStore = FileRuntimeIdentityKeyStore(fileURL: URL(fileURLWithPath: filePath))
            do {
                return (try fileStore.loadOrCreate(), fileStore, nil)
            } catch {
                return (
                    RuntimeIdentityKey(publicKeyBase64: "", fingerprint: "dev-\(deviceID)"),
                    nil,
                    "Runtime identity file unavailable; using temporary fingerprint fallback."
                )
            }
        }

        let store = RuntimeIdentityKeyStore()
        do {
            return (try store.loadOrCreate(), store, nil)
        } catch {
            let fileStore = FileRuntimeIdentityKeyStore()
            do {
                return (
                    try fileStore.loadOrCreate(),
                    fileStore,
                    "Runtime identity Keychain unavailable; using persisted file identity fallback."
                )
            } catch {
                return (
                    RuntimeIdentityKey(publicKeyBase64: "", fingerprint: "dev-\(deviceID)"),
                    nil,
                    "Runtime identity stores unavailable; using temporary fingerprint fallback."
                )
            }
        }
    }

    private static func runtimeIdentityFilePathOverride(environment: [String: String]) -> String? {
        if let filePath = environment["AETHERLINK_RUNTIME_IDENTITY_FILE"]?.trimmingCharacters(in: .whitespacesAndNewlines),
           !filePath.isEmpty {
            return filePath
        }
        if ProcessInfo.processInfo.processName == "xctest" ||
            ProcessInfo.processInfo.processName.hasSuffix(".xctest") ||
            ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil {
            return FileManager.default.temporaryDirectory
                .appendingPathComponent(
                    "aetherlink-xctest-runtime-identity-\(ProcessInfo.processInfo.processIdentifier)",
                    isDirectory: true
                )
                .appendingPathComponent("runtime-identity.json", isDirectory: false)
                .path
        }
        return nil
    }

    nonisolated private static func defaultRuntimeRouteHost() -> String? {
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
            let interfaceName = String(cString: interface.pointee.ifa_name)
            guard let score = pairingInterfaceScore(name: interfaceName) else { continue }
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

    nonisolated private static func pairingInterfaceScore(name: String) -> Int? {
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

    nonisolated private static func isUsablePairingAddress(_ address: String) -> Bool {
        guard !address.isEmpty else { return false }
        if address == "0.0.0.0" || address == "255.255.255.255" { return false }
        if address.hasPrefix("127.") || address.hasPrefix("169.254.") { return false }
        return true
    }

}

private func isRelayRouteLeaseFreshForPairingQRCode(_ lease: CompanionRemoteRouteLease) -> Bool {
    !lease.isExpired(renewalMarginSeconds: pairingQRCodeLeaseRenewalMarginSeconds)
}

extension CompanionAppModel: RuntimeRouteRefreshing {
    public func refreshRuntimeRoute() async throws -> RuntimeRouteRefreshResult? {
        prepareRemoteRelayRouteForPairing()
        guard isDevelopmentRelayRouteEligibleForQRCode,
              let relayConfiguration,
              let relaySecret = relayConfiguration.relaySecret?.takeIfNotEmpty(),
              let lease = relayRouteLeaseForPairing(relayConfiguration: relayConfiguration)
        else {
            return nil
        }
        let result = RuntimeRouteRefreshResult(
            runtimeDeviceID: macDeviceID,
            runtimeKeyFingerprint: macFingerprint,
            relayHost: relayConfiguration.host,
            relayPort: Int(relayConfiguration.port),
            relayID: relayConfiguration.relayID,
            relaySecret: relaySecret,
            relayExpiresAtEpochMillis: lease.expiresAtEpochMillis,
            relayNonce: lease.nonce,
            relayTicketGeneration: lease.ticketGeneration,
            relayScope: Self.relayScope(
                forRelayHost: relayConfiguration.host,
                allowsPrivateOverlay: developmentRelaySettings.allowsPrivateOverlay
            )
        )
        return result
    }

    public func refreshRuntimeRoute(
        authorizationContext: RuntimePairedRelayAuthorizationContext?
    ) async throws -> RuntimeRouteRefreshResult? {
        guard let authorizationContext else {
            throw RuntimeRouteRefreshAuthorizationError.pairedAuthorizationRequired
        }
        let clientKeyFingerprint = authorizationContext.trustedClientKeyFingerprint
        let authorization = try relayAllocationAuthorization()
        let storedPairRoute = pairScopedRelayRoutes[
            clientKeyFingerprint
        ]
        let currentRouteToken = storedPairRoute?.routeToken ?? discoveryRouteToken
        let bootstrapRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: currentRouteToken,
            runtimeKeyFingerprint: authorization.identity.fingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: currentRouteToken,
            runtimeKeyFingerprint: authorization.identity.fingerprint,
            clientKeyFingerprint: clientKeyFingerprint
        )
        let storedConfiguration = storedPairRoute.map(pairScopedRelayConfiguration)
        let storedLease = storedPairRoute.map {
            CompanionRemoteRouteLease(
                expiresAtEpochMillis: $0.relayExpiresAtEpochMillis,
                nonce: $0.relayNonce,
                ticketGeneration: $0.ticketGeneration
            )
        }
        guard let currentConfiguration = storedConfiguration ?? relayConfiguration,
              let endpointRelaySecret = currentConfiguration.relaySecret?.takeIfNotEmpty(),
              let currentLease = storedLease ?? allocatedRemoteRouteLease,
              let currentTicketGeneration = currentLease.ticketGeneration,
              currentTicketGeneration > 0,
              currentTicketGeneration < Int64.max,
              currentConfiguration.relayNonce == currentLease.nonce,
              !currentLease.isExpired(),
              PairedRelayAllocationAuthorization.isCanonicalRelayID(currentConfiguration.relayID),
              currentConfiguration.relayID == bootstrapRelayID ||
                currentConfiguration.relayID == pairedRelayID
        else {
            throw RelayServiceRouteAllocationError.invalidPairedRenewalRequest
        }
        let lifecycleGeneration = beginPairLifecycleRefresh(
            fingerprint: clientKeyFingerprint
        )
        defer {
            finishPairLifecycleRefresh(
                fingerprint: clientKeyFingerprint,
                sequence: lifecycleGeneration.sequence
            )
        }

        let serviceAllocation = try await relayServiceRouteAllocator.renewPairedRelayRoute(
            currentRouteToken: currentRouteToken,
            currentConfiguration: currentConfiguration,
            currentLease: currentLease,
            runtimeIdentity: authorization.identity,
            authorizationSigner: authorization.signer,
            authorizationContext: authorizationContext,
            allocationToken: environment["AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty()
                ?? environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty(),
            timeout: 5
        )
        guard pairLifecycleGenerations[clientKeyFingerprint] == lifecycleGeneration.pair else {
            throw CancellationError()
        }
        guard serviceAllocation.host == currentConfiguration.host,
              serviceAllocation.port == currentConfiguration.port,
              serviceAllocation.relayID == pairedRelayID,
              serviceAllocation.runtimeKeyFingerprint == authorization.identity.fingerprint,
              serviceAllocation.ticketGeneration == currentTicketGeneration + 1,
              serviceAllocation.relayExpiresAtEpochMillis > currentLease.expiresAtEpochMillis,
              serviceAllocation.relayNonce != currentLease.nonce,
              !serviceAllocation.relayNonce.isEmpty
        else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }

        let allocation = try serviceAllocation.attachingEndpointSecret(
            endpointRelaySecret,
            runtimeIdentity: authorization.identity,
            identityAuthorizationSigner: authorization.signer
        )
        guard let renewedLease = allocation.lease,
              renewedLease.isAdvancingReplacement(of: currentLease),
              allocation.configuration.host == currentConfiguration.host,
              allocation.configuration.port == currentConfiguration.port,
              allocation.configuration.relayID == pairedRelayID,
              allocation.configuration.relaySecret == endpointRelaySecret
        else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }

        let storedRoute = try PairScopedRelayRoute(
            clientKeyFingerprint: clientKeyFingerprint,
            routeToken: currentRouteToken,
            host: currentConfiguration.host,
            port: currentConfiguration.port,
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: renewedLease.expiresAtEpochMillis,
            relayNonce: renewedLease.nonce,
            ticketGeneration: renewedLease.ticketGeneration ?? serviceAllocation.ticketGeneration
        )
        guard pairLifecycleGenerations[clientKeyFingerprint] == lifecycleGeneration.pair else {
            throw CancellationError()
        }
        let resolvedRoute: ResolvedPairScopedRelayRoute
        if pairScopedRelayRoutes[clientKeyFingerprint] == storedPairRoute {
            resolvedRoute = try pairScopedRelayRouteStore.upsert(
                storedRoute,
                relaySecret: endpointRelaySecret
            )
        } else if let currentRoute = pairScopedRelayRoutes[clientKeyFingerprint],
                  currentRoute.route == storedRoute,
                  currentRoute.relaySecret == endpointRelaySecret {
            resolvedRoute = currentRoute
        } else {
            throw CancellationError()
        }
        pairScopedRelayRoutes[resolvedRoute.clientKeyFingerprint] = resolvedRoute
        guard runtimeLifecycleGeneration == lifecycleGeneration.runtime,
              pairLifecycleGenerations[clientKeyFingerprint] == lifecycleGeneration.pair
        else {
            throw CancellationError()
        }

        let result = RuntimeRouteRefreshResult(
            runtimeDeviceID: macDeviceID,
            runtimeKeyFingerprint: macFingerprint,
            relayHost: currentConfiguration.host,
            relayPort: Int(currentConfiguration.port),
            relayID: pairedRelayID,
            relaySecret: endpointRelaySecret,
            relayExpiresAtEpochMillis: renewedLease.expiresAtEpochMillis,
            relayNonce: renewedLease.nonce,
            relayTicketGeneration: renewedLease.ticketGeneration,
            relayScope: Self.relayScope(
                forRelayHost: currentConfiguration.host,
                allowsPrivateOverlay: developmentRelaySettings.allowsPrivateOverlay
            )
        )
        if pendingPairedRelayActivations[clientKeyFingerprint]?.refreshSequence ?? 0
            <= lifecycleGeneration.sequence {
            pendingPairedRelayActivations[clientKeyFingerprint] = PendingPairScopedRelayActivation(
                clientKeyFingerprint: clientKeyFingerprint,
                result: result,
                rotatesBootstrapRoute: storedPairRoute == nil &&
                    currentConfiguration.relayID == bootstrapRelayID,
                runtimeLifecycleGeneration: lifecycleGeneration.runtime,
                pairLifecycleGeneration: lifecycleGeneration.pair,
                refreshSequence: lifecycleGeneration.sequence,
                activationRequested: false
            )
        }
        return result
    }

    public func activateRuntimeRouteRefresh(_ result: RuntimeRouteRefreshResult) async {
        let matchingActivations = pendingPairedRelayActivations.values.filter {
            $0.result == result
        }
        guard matchingActivations.count == 1,
              let pendingActivation = matchingActivations.first
        else {
            return
        }
        pendingPairedRelayActivations[pendingActivation.clientKeyFingerprint]?
            .activationRequested = true
        reconcilePendingPairActivation(fingerprint: pendingActivation.clientKeyFingerprint)
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
        case .manual:
            return "manual"
        }
    }
}

func sanitizedCompanionLogMessage(_ message: String) -> String {
    var sanitized = message
    for pattern in companionLogRedactionPatterns {
        sanitized = sanitized.replacingOccurrences(
            of: pattern,
            with: "[redacted]",
            options: [.regularExpression, .caseInsensitive]
        )
    }
    return sanitized
}

private let companionLogRedactionPatterns = [
    #"https?://[^\s,;)]+"#,
    #"\b(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+])(?::)(?:11434|1234)(?:/[^\s,;)]*)?"#,
    #"/(?:api/(?:tags|ps|pull|chat|show|v1)|v1/(?:models|chat|chat/completions))\b"#,
    #"(?:^|[\s?&{,;])["']?(?:relay_secret|relaySecret|route_secret|routeSecret|route_token|routeToken|pairing_secret|pairingSecret|relay_id|relayId|relay_nonce|relayNonce|allocation_token|allocationToken|p2p_class|p2pClass|p2pRouteClass|p2p_record_id|p2pRecordID|p2pRecordId|p2p_encrypted_body|p2pEncryptedBody|p2p_expires_at|p2pExpiresAt|p2pExpiresAtEpochMillis|p2p_anti_replay_nonce|p2pAntiReplayNonce|p2p_protocol_version|p2pProtocolVersion|rs|rt|ri|rrn|pc|prid|peb|px|pn|pv)["']?\s*(?:=|:|\s)\s*["']?[^"',\s;})]+"#,
    #"\b(?:relay_secret|relaySecret|route_secret|routeSecret|route_token|routeToken|pairing_secret|pairingSecret|relay_id|relayId|relay_nonce|relayNonce|allocation_token|allocationToken|p2p_class|p2pClass|p2pRouteClass|p2p_record_id|p2pRecordID|p2pRecordId|p2p_encrypted_body|p2pEncryptedBody|p2p_expires_at|p2pExpiresAt|p2pExpiresAtEpochMillis|p2p_anti_replay_nonce|p2pAntiReplayNonce|p2p_protocol_version|p2pProtocolVersion)\b"#,
]

private extension String {
    func takeIfNotEmpty() -> String? {
        isEmpty ? nil : self
    }

    var isTruthyEnvironmentValue: Bool {
        switch trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
        case "1", "true", "yes", "on":
            return true
        default:
            return false
        }
    }
}
