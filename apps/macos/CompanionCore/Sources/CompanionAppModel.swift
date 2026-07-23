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
import SystemConfiguration
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

public enum CompanionRuntimeChatRetentionState: Equatable, Sendable {
    case notRun
    case running
    case completed
    case failed
}

public struct CompanionRuntimeChatRetentionStatus: Equatable, Sendable {
    public var state: CompanionRuntimeChatRetentionState
    public var prunedDeletedSessionCount: Int
    public var lastRunAt: Date?

    public init(
        state: CompanionRuntimeChatRetentionState = .notRun,
        prunedDeletedSessionCount: Int = 0,
        lastRunAt: Date? = nil
    ) {
        self.state = state
        self.prunedDeletedSessionCount = max(0, prunedDeletedSessionCount)
        self.lastRunAt = lastRunAt
    }
}

public enum CompanionRelayConfigurationResult: Equatable, Sendable {
    case disabled
    case savedStatic(endpoint: String)
    case allocated(endpoint: String)
    case allocationFailed(endpoint: String, message: String)
}

public enum CompanionRelayConfigurationRequestResult: Equatable, Sendable {
    case started(requestID: UUID)
    case completed(CompanionRelayConfigurationResult)
}

public enum CompanionRelayConfigurationOperation: Equatable, Sendable {
    case developmentRelay
    case bootstrapRelay
}

public struct CompanionRelayConfigurationRequestContext: Equatable, Sendable {
    public let requestID: UUID
    public let operation: CompanionRelayConfigurationOperation

    public init(requestID: UUID, operation: CompanionRelayConfigurationOperation) {
        self.requestID = requestID
        self.operation = operation
    }
}

public struct CompanionRelayConfigurationRequestCompletion: Equatable, Sendable {
    public let requestID: UUID
    public let operation: CompanionRelayConfigurationOperation
    public let result: CompanionRelayConfigurationResult

    public init(
        requestID: UUID,
        operation: CompanionRelayConfigurationOperation,
        result: CompanionRelayConfigurationResult
    ) {
        self.requestID = requestID
        self.operation = operation
        self.result = result
    }
}

public enum CompanionRelayConfigurationRequestState: Equatable, Sendable {
    case active(CompanionRelayConfigurationRequestContext)
    case completed(CompanionRelayConfigurationRequestCompletion)
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
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        cancellation: RelayRouteAllocationCancellation
    ) throws -> CompanionRemoteRelayRouteAllocation?
}

public extension CompanionRemoteRelayRouteAllocating {
    var canAllocateRemoteRelayRoute: Bool { false }

    func allocateRemoteRelayRoute(
        runtimeDeviceID: String,
        routeToken: String,
        preferredRelaySecret: String?,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning
    ) throws -> CompanionRemoteRelayRouteAllocation? {
        try allocateRemoteRelayRoute(
            runtimeDeviceID: runtimeDeviceID,
            routeToken: routeToken,
            preferredRelaySecret: preferredRelaySecret,
            runtimeIdentity: runtimeIdentity,
            identityAuthorizationSigner: identityAuthorizationSigner,
            cancellation: RelayRouteAllocationCancellation(timeout: 15)
        )
    }
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
        try allocateRemoteRelayRoute(
            runtimeDeviceID: runtimeDeviceID,
            routeToken: routeToken,
            preferredRelaySecret: preferredRelaySecret,
            runtimeIdentity: runtimeIdentity,
            identityAuthorizationSigner: identityAuthorizationSigner,
            cancellation: RelayRouteAllocationCancellation(timeout: 15)
        )
    }

    public func allocateRemoteRelayRoute(
        runtimeDeviceID: String,
        routeToken: String,
        preferredRelaySecret: String? = nil,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        cancellation: RelayRouteAllocationCancellation
    ) throws -> CompanionRemoteRelayRouteAllocation? {
        try cancellation.throwIfCancelledOrExpired()
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
            try cancellation.throwIfCancelledOrExpired()
            do {
                let serviceAllocation = try relayServiceAllocator.allocateRelayRoute(
                    host: endpoint.host,
                    port: endpoint.port,
                    routeToken: routeToken,
                    allocationToken: allocationToken,
                    runtimeIdentity: runtimeIdentity,
                    identityAuthorizationSigner: identityAuthorizationSigner,
                    timeout: 5,
                    cancellation: cancellation
                )
                return try serviceAllocation.attachingEndpointSecret(
                    endpointRelaySecret,
                    runtimeIdentity: runtimeIdentity,
                    identityAuthorizationSigner: identityAuthorizationSigner
                )
            } catch {
                try cancellation.throwIfCancelledOrExpired()
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
        validatedBootstrapRelayEndpoints(from: endpointList, defaultPort: defaultPort) ?? []
    }

    static func hasValidBootstrapRelayEndpoints(_ endpointList: String) -> Bool {
        validatedBootstrapRelayEndpoints(
            from: endpointList,
            defaultPort: defaultBootstrapRelayPort
        ) != nil
    }

    private static func validatedBootstrapRelayEndpoints(
        from endpointList: String,
        defaultPort: UInt16
    ) -> [BootstrapRelayEndpoint]? {
        let values = endpointList.split(separator: ",", omittingEmptySubsequences: false)
        guard !values.isEmpty else { return nil }
        var endpoints: [BootstrapRelayEndpoint] = []
        endpoints.reserveCapacity(values.count)
        for value in values {
            guard let endpoint = parseBootstrapRelayEndpoint(
                String(value),
                defaultPort: defaultPort
            ) else {
                return nil
            }
            endpoints.append(endpoint)
        }
        return endpoints.isEmpty ? nil : endpoints
    }

    private static func parseBootstrapRelayEndpoint(
        _ value: String,
        defaultPort: UInt16
    ) -> BootstrapRelayEndpoint? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        if trimmed.hasPrefix("[") {
            guard let closeBracket = trimmed.firstIndex(of: "]") else { return nil }
            let host = String(trimmed[trimmed.index(after: trimmed.startIndex)..<closeBracket])
            guard isCanonicalBootstrapRelayHost(host) else { return nil }
            let remainder = trimmed[trimmed.index(after: closeBracket)...]
            if remainder.isEmpty {
                return BootstrapRelayEndpoint(host: host, port: defaultPort)
            }
            guard remainder.hasPrefix(":"),
                  let port = UInt16(String(remainder.dropFirst())),
                  port > 0
            else {
                return nil
            }
            return BootstrapRelayEndpoint(host: host, port: port)
        }

        guard !trimmed.contains("["), !trimmed.contains("]") else { return nil }
        let colonCount = trimmed.filter { $0 == ":" }.count
        if colonCount == 1 {
            guard let colon = trimmed.lastIndex(of: ":"),
                  let port = UInt16(String(trimmed[trimmed.index(after: colon)...])),
                  port > 0
            else {
                return nil
            }
            let host = String(trimmed[..<colon])
            guard isCanonicalBootstrapRelayHost(host) else { return nil }
            return BootstrapRelayEndpoint(host: host, port: port)
        }

        guard isCanonicalBootstrapRelayHost(trimmed) else {
            return nil
        }
        return BootstrapRelayEndpoint(host: trimmed, port: defaultPort)
    }

    private static func isCanonicalBootstrapRelayHost(_ host: String) -> Bool {
        !host.isEmpty &&
            host.rangeOfCharacter(from: .whitespacesAndNewlines) == nil &&
            !host.contains("[") &&
            !host.contains("]") &&
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: host) != .invalidFormat
    }
}

private struct BootstrapRelayEndpoint: Equatable, Sendable {
    var host: String
    var port: UInt16
}

private let companionRelayAllocationIOQueue = DispatchQueue(
    label: "dev.aetherlink.companion.relay-allocation",
    qos: .userInitiated,
    attributes: .concurrent
)

private struct CompanionRouteAllocationRequest: Equatable, Sendable {
    var routeStateRevision: UInt64
    var generation: UInt64
    var routeToken: String
    var cancellation: RelayRouteAllocationCancellation
    var timeoutIssueKind: CompanionRemoteRoutePreparationIssue.Kind
    var timeoutEndpoint: String?
    var timeoutBehavior: CompanionRouteAllocationTimeoutBehavior
    var userInterfaceRequestContext: CompanionRelayConfigurationRequestContext?
    var userInterfaceFallbackEndpoint: String?

    static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.routeStateRevision == rhs.routeStateRevision &&
            lhs.generation == rhs.generation &&
            lhs.routeToken == rhs.routeToken &&
            lhs.cancellation === rhs.cancellation &&
            lhs.timeoutIssueKind == rhs.timeoutIssueKind &&
            lhs.timeoutEndpoint == rhs.timeoutEndpoint &&
            lhs.timeoutBehavior == rhs.timeoutBehavior &&
            lhs.userInterfaceRequestContext == rhs.userInterfaceRequestContext &&
            lhs.userInterfaceFallbackEndpoint == rhs.userInterfaceFallbackEndpoint
    }
}

private enum CompanionRouteAllocationTimeoutBehavior: Equatable, Sendable {
    case none
    case saveStaticDevelopmentRelay(
        host: String,
        port: UInt16,
        secret: String,
        allowsPrivateOverlay: Bool
    )
    case startConfiguredRelay
}

private enum CompanionRouteAllocationOutcome: Sendable {
    case allocation(CompanionRemoteRelayRouteAllocation?)
    case failure(String)
}

private enum CompanionRuntimeStartRoutePreparation {
    case asynchronous
    case none
}

private enum CompanionRelaySecretSource {
    case none
    case protectedStore
    case environmentEphemeral
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
    private static let relaySecretPersistenceFailureMessage =
        "Connection secret could not be saved securely."

    @Published public private(set) var backendStatus = "Not checked"
    @Published public private(set) var transportStatus = "Stopped"
    @Published public private(set) var transportState: CompanionTransportStatus = .stopped
    @Published public private(set) var providerStatuses: [CompanionProviderStatus]
    @Published public private(set) var bootstrapRelaySettings: CompanionBootstrapRelaySettings = .disabled
    @Published public private(set) var developmentRelaySettings: CompanionDevelopmentRelaySettings = .disabled
    @Published public private(set) var developmentRelayConnectionStatus: CompanionDevelopmentRelayStatus = .stopped
    @Published public private(set) var remoteRoutePreparationIssue: CompanionRemoteRoutePreparationIssue?
    @Published public private(set) var isRemoteRoutePreparationInFlight = false
    @Published public private(set) var relayConfigurationRequestState: CompanionRelayConfigurationRequestState?
    @Published public private(set) var pairingSession: PairingSession?
    @Published public private(set) var trustedDevices: [TrustedDevice] = []
    @Published public private(set) var models: [ModelInfo] = []
    @Published public private(set) var pendingModelPullReviews: [CompanionPendingModelPullReview] = []
    @Published public private(set) var modelPullAuditEvents: [RuntimeModelPullAuditSummary] = []
    @Published public private(set) var modelPullApprovalErrorLocalizationKey: String?
    @Published public private(set) var isModelPullDecisionInFlight = false
    @Published public private(set) var modelResidency: CompanionModelResidencyStatus = .inactive
    @Published public private(set) var modelIdleUnloadPolicy: RuntimeModelIdleUnloadPolicy
    @Published public private(set) var isModelIdleUnloadPolicyUpdateInFlight = false
    @Published public private(set) var runtimeDataSummary = CompanionRuntimeDataSummary()
    @Published public private(set) var runtimeChatRetentionStatus = CompanionRuntimeChatRetentionStatus()
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
    private var runtimeModelPullApprovalBroker: RuntimeModelPullApprovalBroker!
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
    private var developmentRelaySecretSource: CompanionRelaySecretSource = .none
    private var remoteRelayRouteAllocator: any CompanionRemoteRelayRouteAllocating
    private let relayServiceRouteAllocator: any RelayServiceRouteAllocating
    private let environment: [String: String]
    private let runtimeRouteHostProvider: () -> String?
    private let allowsLocalDiagnosticPairingFromUserInterface: Bool
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
    private var hasScheduledRuntimeChatRetentionMaintenance = false
    private var runtimeChatRetentionMaintenanceTask: Task<Void, Never>?
    private let modelIdleUnloadPolicyUpdateQueue = RuntimeModelIdleUnloadPolicyUpdateQueue()
    private var shouldGenerateRemotePairingQRCodeWhenRelayReady = false
    private var pendingRemotePairingPreparationID: UUID?
    private var pendingRemotePairingEndpoint: String?
    private var remotePairingPreparationTimeoutTask: Task<Void, Never>?
    private let pairingRoutePreparationTimeoutNanoseconds: UInt64
    private var routeAllocationTimeoutTask: Task<Void, Never>?
    private let routeAllocationTimeoutNanoseconds: UInt64
    private var routeStateRevision: UInt64 = 0
    private var routeAllocationRequestGeneration: UInt64 = 0
    private var activeRouteAllocationRequest: CompanionRouteAllocationRequest?
    private var drainingRouteAllocationRequest: CompanionRouteAllocationRequest?

    private static let runtimeChatRetentionMaintenanceIntervalNanoseconds: UInt64 = 24 * 60 * 60 * 1_000_000_000

    public var relayConfigurationRequestCompletion: CompanionRelayConfigurationRequestCompletion? {
        guard case .completed(let completion) = relayConfigurationRequestState else { return nil }
        return completion
    }

    public func acknowledgeRelayConfigurationRequestCompletion(requestID: UUID) {
        guard case .completed(let completion) = relayConfigurationRequestState,
              completion.requestID == requestID
        else {
            return
        }
        relayConfigurationRequestState = nil
    }

    private func clearCompletedRelayConfigurationRequestState() {
        guard case .completed = relayConfigurationRequestState else { return }
        relayConfigurationRequestState = nil
    }

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
        guard hasSecureFreshRemoteRouteMaterialForQRCode else { return false }
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

    public var canRequestRemotePairingForUserInterface: Bool {
        guard !isRemoteRoutePreparationInFlight else { return false }
        if shouldIncludeDevelopmentRelayInPairingQRCode || hasCanonicalFreshRemoteRouteMaterialForQRCode {
            return true
        }
        if canAttemptAutomaticRemoteRouteAllocation {
            return true
        }
        return relayConfiguration != nil &&
            isDevelopmentRelayRouteEligibleForQRCode &&
            shouldRefreshConfiguredRelayRouteLeaseForPairing
    }

    private var hasReadyRemotePairingRouteForUserInterface: Bool {
        shouldIncludeDevelopmentRelayInPairingQRCode || hasCanonicalFreshRemoteRouteMaterialForQRCode
    }

    public var canRequestLocalDiagnosticPairingForUserInterface: Bool {
        guard allowsLocalDiagnosticPairingFromUserInterface,
              !isRemoteRoutePreparationInFlight
        else {
            return false
        }
        if isRuntimeStarted, transportState.state != .advertising {
            return false
        }
        return localDiagnosticPairingRouteHostCandidate != nil
    }

    public var shouldUseLocalDiagnosticPairingForUserInterface: Bool {
        canRequestLocalDiagnosticPairingForUserInterface && !hasReadyRemotePairingRouteForUserInterface
    }

    public var canRequestPairingForUserInterface: Bool {
        canRequestRemotePairingForUserInterface || canRequestLocalDiagnosticPairingForUserInterface
    }

    private var hasCurrentRelayRouteLeaseForQRCode: Bool {
        if let allocatedRemoteRouteLease {
            return isRelayRouteLeaseFreshForPairingQRCode(allocatedRemoteRouteLease)
        }
        return false
    }

    public init(
        backend: (any LlmBackend)? = nil,
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
        runtimeChatCompactionSummaryCache: any RuntimeChatCompactionSummaryCaching = SQLiteRuntimeChatCompactionSummaryCache(),
        runtimeMemoryStore: any RuntimeMemoryStore = JSONLRuntimeMemoryStore(),
        runtimeDocumentIndexStore: SQLiteRuntimeDocumentIndexStore = SQLiteRuntimeDocumentIndexStore(),
        runtimePromptSkillRegistry: RuntimePromptSkillRegistry = .bundled,
        runtimePermissionPolicyRegistry: RuntimePermissionPolicyRegistry = .bundled,
        runtimeModelPullApprovalPersistence: any RuntimeModelPullBrokerPersistence = SQLiteRuntimeModelPullApprovalStore(),
        runtimeRouteHostProvider: (() -> String?)? = nil,
        allowsAuthenticatedRouteRefresh: Bool = false,
        allowsLocalDiagnosticPairingFromUserInterface: Bool? = nil,
        pairingRoutePreparationTimeoutNanoseconds: UInt64 = 15_000_000_000,
        routeAllocationTimeoutNanoseconds: UInt64 = 15_000_000_000
    ) {
        precondition(
            pairingRoutePreparationTimeoutNanoseconds > 0,
            "Pairing route preparation timeout must be positive"
        )
        precondition(
            routeAllocationTimeoutNanoseconds > 0,
            "Route allocation timeout must be positive"
        )
        let modelIdleUnloadPolicyStore = RuntimeModelIdleUnloadPolicyStore(defaults: userDefaults)
        let loadedModelIdleUnloadPolicy = modelIdleUnloadPolicyStore.load()
        let resolvedBackend = backend ?? AggregatingLlmBackend(
            [OllamaBackend(), LMStudioBackend()],
            modelIdleUnloadDelayNanoseconds: loadedModelIdleUnloadPolicy.idleUnloadDelayNanoseconds
        )
        if let aggregate = resolvedBackend as? AggregatingLlmBackend {
            aggregate.configureModelIdleUnloadDelayNanoseconds(
                loadedModelIdleUnloadPolicy.idleUnloadDelayNanoseconds
            )
        }
        let loadedBootstrapRelaySettings = Self.loadBootstrapRelaySettings(
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        self.backend = resolvedBackend
        self.providerStatuses = Self.initialProviderStatuses(for: resolvedBackend)
        self.modelIdleUnloadPolicy = loadedModelIdleUnloadPolicy
        self.relayServiceRouteAllocator = relayServiceRouteAllocator
        self.environment = environment
        self.pairingRoutePreparationTimeoutNanoseconds = pairingRoutePreparationTimeoutNanoseconds
        self.routeAllocationTimeoutNanoseconds = routeAllocationTimeoutNanoseconds
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
        self.allowsLocalDiagnosticPairingFromUserInterface = Self.resolveLocalDiagnosticPairingUIAllowance(
            requestedOverride: allowsLocalDiagnosticPairingFromUserInterface,
            isDebugAssertConfiguration: _isDebugAssertConfiguration()
        )
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
        self.developmentRelaySecretSource = Self.loadedRelaySecretSource(
            environment: environment,
            settings: relaySettings
        )
        self.relayConfiguration = Self.relayConfiguration(for: relaySettings, lease: savedRelayLease)
        self.allocatedRemoteRouteLease = savedRelayLease
        self.developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
            status: .stopped,
            endpoint: relaySettings.endpointLabel
        )
        self.runtimeModelPullApprovalBroker = RuntimeModelPullApprovalBroker(
            dispatcher: resolvedBackend,
            persistence: runtimeModelPullApprovalPersistence,
            permissionPolicyRegistry: runtimePermissionPolicyRegistry,
            onStateChange: { [weak self] in
                Task { @MainActor in
                    await self?.refreshModelPullApprovals()
                }
            }
        )
        let runtimeModelPullApprovalBroker = self.runtimeModelPullApprovalBroker!
        self.runtimeRouter = LocalRuntimeMessageRouter(
            backend: resolvedBackend,
            pairingCoordinator: pairingCoordinator,
            trustedDeviceStore: trustedDeviceStore,
            chatEventStore: runtimeChatEventStore,
            chatCompactionSummaryCache: runtimeChatCompactionSummaryCache,
            memoryStore: runtimeMemoryStore,
            documentIndexStore: runtimeDocumentIndexStore,
            promptSkillRegistry: runtimePromptSkillRegistry,
            permissionPolicyRegistry: runtimePermissionPolicyRegistry,
            modelPullApprovalBroker: runtimeModelPullApprovalBroker,
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
        Task { [weak self] in
            var recoveryErrorLocalizationKey: String?
            do {
                try await runtimeModelPullApprovalBroker.recoverUnfinished()
            } catch {
                recoveryErrorLocalizationKey = RuntimeModelPullApprovalBrokerError
                    .storageUnavailable
                    .localizationKey
            }
            await self?.refreshModelPullApprovals()
            if let recoveryErrorLocalizationKey {
                await MainActor.run {
                    self?.modelPullApprovalErrorLocalizationKey = recoveryErrorLocalizationKey
                }
            }
        }
    }

    deinit {
        runtimeChatRetentionMaintenanceTask?.cancel()
        remotePairingPreparationTimeoutTask?.cancel()
        routeAllocationTimeoutTask?.cancel()
        activeRouteAllocationRequest?.cancellation.cancel()
        drainingRouteAllocationRequest?.cancellation.cancel()
    }

    public func start(port: UInt16 = 43170) {
        startRuntime(port: port, routePreparation: .asynchronous)
    }

    @discardableResult
    public func requestStartForUserInterface(port: UInt16 = 43170) -> Bool {
        guard !isRuntimeStarted || runtimePort != port else {
            return false
        }
        startRuntime(port: port, routePreparation: .asynchronous)
        return true
    }

    private func startRuntime(
        port: UInt16,
        routePreparation: CompanionRuntimeStartRoutePreparation
    ) {
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
        switch routePreparation {
        case .asynchronous:
            if shouldRenewSavedBootstrapRelayRoute && !hasRouteAllocationWorkerInFlight {
                if !requestAutomaticRemoteRelayRouteAllocation(
                    restartRelayClientIfRunning: false,
                    startRelayAfterCompletion: true,
                    pairingRequest: false
                ) {
                    startRelayClientIfConfigured()
                }
            } else {
                startRelayClientIfConfigured()
            }
        case .none:
            startRelayClientIfConfigured()
        }
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
        let startedRuntimeLifecycleGeneration = runtimeLifecycleGeneration
        Task {
            await startRestoredPairScopedTransports(
                expectedRuntimeLifecycleGeneration: startedRuntimeLifecycleGeneration
            )
            await refreshBackendStatus()
        }
        if !hasScheduledRuntimeChatRetentionMaintenance {
            hasScheduledRuntimeChatRetentionMaintenance = true
            let interval = Self.runtimeChatRetentionMaintenanceIntervalNanoseconds
            let store = runtimeChatEventStore
            runtimeChatRetentionMaintenanceTask = Task { [weak self, store] in
                while !Task.isCancelled {
                    guard self != nil else { return }
                    if self?.beginRuntimeChatRetentionMaintenance() == true {
                        do {
                            let prunedSessionCount = try await Self.pruneExpiredDeletedRuntimeChats(
                                from: store
                            )
                            self?.completeRuntimeChatRetentionMaintenance(
                                prunedSessionCount: prunedSessionCount
                            )
                        } catch is CancellationError {
                            return
                        } catch {
                            self?.failRuntimeChatRetentionMaintenance(error)
                        }
                    }
                    do {
                        try await Task.sleep(nanoseconds: interval)
                    } catch {
                        return
                    }
                }
            }
        }
    }

    public func stop() {
        invalidateRouteAllocationRequests(routeStateChanged: true)
        isRuntimeStarted = false
        cancelPendingRemotePairingPreparation()
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

    public func runRuntimeChatRetentionMaintenance() async {
        guard beginRuntimeChatRetentionMaintenance() else { return }
        let store = runtimeChatEventStore
        do {
            let prunedSessionCount = try await Self.pruneExpiredDeletedRuntimeChats(from: store)
            completeRuntimeChatRetentionMaintenance(prunedSessionCount: prunedSessionCount)
        } catch is CancellationError {
            runtimeChatRetentionStatus = CompanionRuntimeChatRetentionStatus(state: .notRun)
        } catch {
            failRuntimeChatRetentionMaintenance(error)
        }
    }

    private func beginRuntimeChatRetentionMaintenance() -> Bool {
        guard runtimeChatRetentionStatus.state != .running else { return false }
        runtimeChatRetentionStatus = CompanionRuntimeChatRetentionStatus(state: .running)
        return true
    }

    private func completeRuntimeChatRetentionMaintenance(prunedSessionCount: Int) {
        runtimeChatRetentionStatus = CompanionRuntimeChatRetentionStatus(
            state: .completed,
            prunedDeletedSessionCount: prunedSessionCount,
            lastRunAt: Date()
        )
        log(
            "Runtime chat retention completed: "
                + "\(prunedSessionCount) expired deleted sessions pruned"
        )
    }

    private func failRuntimeChatRetentionMaintenance(_ error: any Error) {
        runtimeChatRetentionStatus = CompanionRuntimeChatRetentionStatus(
            state: .failed,
            lastRunAt: Date()
        )
        log("Runtime chat retention failed: \(error.localizedDescription)")
    }

    nonisolated private static func pruneExpiredDeletedRuntimeChats(
        from store: any RuntimeChatEventStore
    ) async throws -> Int {
        let policy = RuntimeChatRetentionPolicy.productionDefault
        return try await withThrowingTaskGroup(of: Int.self) { group in
            group.addTask(priority: .utility) {
                var total = 0
                while true {
                    try Task.checkCancellation()
                    let result = try RuntimeChatEventStoreDefaults.runProductionMaintenance(
                        on: store,
                        policy: policy
                    )
                    total += result.prunedDeletedSessionCount
                    guard result.prunedDeletedSessionCount == policy.deletedSessionPruneLimit else {
                        return total
                    }
                    await Task.yield()
                }
            }
            guard let total = try await group.next() else { return 0 }
            group.cancelAll()
            return total
        }
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

    public func refreshModelPullApprovals() async {
        pendingModelPullReviews = await runtimeModelPullApprovalBroker.pendingReviews()
        do {
            modelPullAuditEvents = try await runtimeModelPullApprovalBroker.recentAuditEvents()
            modelPullApprovalErrorLocalizationKey = nil
        } catch {
            modelPullApprovalErrorLocalizationKey = modelPullApprovalLocalizationKey(for: error)
        }
    }

    public func approveModelPull(operationID: String) async {
        guard !isModelPullDecisionInFlight else { return }
        isModelPullDecisionInFlight = true
        modelPullApprovalErrorLocalizationKey = nil
        defer { isModelPullDecisionInFlight = false }
        var decisionErrorLocalizationKey: String?
        do {
            try await runtimeModelPullApprovalBroker.approve(operationID: operationID)
            await loadModels()
        } catch {
            decisionErrorLocalizationKey = modelPullApprovalLocalizationKey(for: error)
        }
        await refreshModelPullApprovals()
        if let decisionErrorLocalizationKey {
            modelPullApprovalErrorLocalizationKey = decisionErrorLocalizationKey
        }
    }

    public func dismissModelPull(operationID: String) async {
        guard !isModelPullDecisionInFlight else { return }
        isModelPullDecisionInFlight = true
        modelPullApprovalErrorLocalizationKey = nil
        defer { isModelPullDecisionInFlight = false }
        var decisionErrorLocalizationKey: String?
        do {
            try await runtimeModelPullApprovalBroker.dismiss(operationID: operationID)
        } catch {
            decisionErrorLocalizationKey = modelPullApprovalLocalizationKey(for: error)
        }
        await refreshModelPullApprovals()
        if let decisionErrorLocalizationKey {
            modelPullApprovalErrorLocalizationKey = decisionErrorLocalizationKey
        }
    }

    private func modelPullApprovalLocalizationKey(for error: Error) -> String {
        (error as? RuntimeModelPullApprovalBrokerError)?.localizationKey
            ?? RuntimeModelPullApprovalBrokerError.storageUnavailable.localizationKey
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

    public func setModelIdleUnloadPolicy(_ policy: RuntimeModelIdleUnloadPolicy) async {
        RuntimeModelIdleUnloadPolicyStore(defaults: userDefaults).save(policy)
        modelIdleUnloadPolicy = policy
        await applyModelIdleUnloadPolicy(policy)
    }

    @discardableResult
    public func requestModelIdleUnloadPolicy(_ policy: RuntimeModelIdleUnloadPolicy) -> Bool {
        guard !isModelIdleUnloadPolicyUpdateInFlight,
              policy != modelIdleUnloadPolicy
        else {
            return false
        }
        RuntimeModelIdleUnloadPolicyStore(defaults: userDefaults).save(policy)
        modelIdleUnloadPolicy = policy
        isModelIdleUnloadPolicyUpdateInFlight = true
        Task { [weak self] in
            guard let self else { return }
            await self.applyModelIdleUnloadPolicy(policy)
            self.isModelIdleUnloadPolicyUpdateInFlight = false
        }
        return true
    }

    private func applyModelIdleUnloadPolicy(_ policy: RuntimeModelIdleUnloadPolicy) async {
        guard let aggregate = backend as? AggregatingLlmBackend else {
            modelResidency = .unsupported
            return
        }
        let delayNanoseconds = policy.idleUnloadDelayNanoseconds
        let isLatestUpdate = await modelIdleUnloadPolicyUpdateQueue.enqueue {
            await aggregate.updateModelIdleUnloadDelayNanoseconds(delayNanoseconds)
        }
        guard isLatestUpdate else {
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

    @discardableResult
    public func requestPairingForUserInterface() -> Bool {
        if !shouldUseLocalDiagnosticPairingForUserInterface,
           canRequestRemotePairingForUserInterface {
            return requestRemotePairingForUserInterface()
        }
        guard canRequestLocalDiagnosticPairingForUserInterface,
              let localRouteHost = localDiagnosticPairingRouteHostCandidate
        else {
            publishRemotePairingUnavailability()
            return false
        }
        if !isRuntimeStarted {
            startRuntime(port: runtimePort, routePreparation: .none)
        }
        guard transportState.state == .advertising else {
            return false
        }
        remoteRoutePreparationIssue = nil
        generatePairingSession(
            routePolicy: .allowLocalDiagnostic,
            localRouteHostOverride: localRouteHost
        )
        return pairingSession?.host == localRouteHost
    }

    @discardableResult
    public func requestRemotePairingForUserInterface() -> Bool {
        guard !isRemoteRoutePreparationInFlight else {
            return false
        }
        guard canRequestRemotePairingForUserInterface else {
            publishRemotePairingUnavailability()
            return false
        }
        if !isRuntimeStarted {
            startRuntime(port: runtimePort, routePreparation: .none)
        }
        if shouldIncludeDevelopmentRelayInPairingQRCode {
            generatePairingSession(routePolicy: .remoteRequired)
            return true
        }

        if hasCanonicalFreshRemoteRouteMaterialForQRCode {
            let endpoint = developmentRelaySettings.endpointLabel ?? "connection service"
            schedulePendingRemotePairingPreparation(endpoint: endpoint)
            switch developmentRelayConnectionStatus.status {
            case .stopped, .failed:
                restartRelayClientIfRunning()
            case .connecting, .reconnecting, .waitingForPeer, .ready:
                break
            }
            return true
        }

        let preparationEndpoint = developmentRelaySettings.endpointLabel
            ?? bootstrapRelaySettings.endpointLabel
            ?? "connection service"
        if canAttemptAutomaticRemoteRouteAllocation {
            schedulePendingRemotePairingPreparation(endpoint: preparationEndpoint)
            guard requestAutomaticRemoteRelayRouteAllocation(
                restartRelayClientIfRunning: true,
                startRelayAfterCompletion: false,
                pairingRequest: true
            ) else {
                cancelPendingRemotePairingPreparation()
                return false
            }
            return true
        }

        if relayConfiguration != nil,
           isDevelopmentRelayRouteEligibleForQRCode,
           shouldRefreshConfiguredRelayRouteLeaseForPairing {
            schedulePendingRemotePairingPreparation(endpoint: preparationEndpoint)
            guard requestConfiguredRelayRouteLeaseRefreshForUserInterface() else {
                cancelPendingRemotePairingPreparation()
                return false
            }
            return true
        }

        publishRemotePairingUnavailability()
        return false
    }

    public func beginPairing(routePolicy: CompanionPairingRoutePolicy = .remoteRequired) {
        if routePolicy == .remoteRequired {
            _ = requestRemotePairingForUserInterface()
            return
        }
        if !isRuntimeStarted {
            startRuntime(port: runtimePort, routePreparation: .none)
        }
        generatePairingSession(routePolicy: routePolicy)
    }

    private func publishRemotePairingUnavailability() {
        if let issue = remoteRoutePreparationIssue {
            cancelPendingRemotePairingPreparation()
            log("Remote pairing QR not generated: \(issue.message)")
            return
        }
        if let endpoint = developmentRelaySettings.endpointLabel {
            cancelPendingRemotePairingPreparation()
            if !isDevelopmentRelayRouteEligibleForQRCode {
                log("Remote pairing QR not generated: remote route \(endpoint) cannot be included in QR")
                return
            }
            let message: String
            let kind: CompanionRemoteRoutePreparationIssue.Kind
            if !hasFreshCurrentRemoteRouteLease {
                kind = .routeLeaseRefreshRejected
                message = developmentRelaySettings.allowsPrivateOverlay && allocatedRemoteRouteLease == nil
                    ? "Private-overlay connection details require an allocated route lease before QR generation."
                    : "Connection details require a fresh allocated route lease before QR generation."
            } else {
                kind = .automaticPreparationRejected
                message = "Connection details could not be encoded safely in the pairing QR."
            }
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: kind,
                endpoint: endpoint,
                message: message
            )
            log("Remote pairing QR not generated: \(message)")
            return
        }
        cancelPendingRemotePairingPreparation()
        remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
            kind: .automaticPreparationUnavailable,
            message: "Configure a reachable remote route before generating a remote pairing QR."
        )
        log("Remote pairing QR not generated: configure a reachable remote route first")
    }

    private func generatePairingSession(
        routePolicy: CompanionPairingRoutePolicy,
        localRouteHostOverride: String? = nil
    ) {
        let pairingRelayConfiguration = shouldIncludeDevelopmentRelayInPairingQRCode ? relayConfiguration : nil
        if routePolicy == .remoteRequired && pairingRelayConfiguration == nil {
            publishRemotePairingUnavailability()
            return
        }
        cancelPendingRemotePairingPreparation()
        let localRouteHost = pairingRelayConfiguration == nil
            ? (localRouteHostOverride ?? localPairingRouteHost)
            : nil
        let relayRouteLease = relayRouteLeaseForPairing(relayConfiguration: pairingRelayConfiguration)
        let pairingRelayScope = pairingRelayConfiguration.flatMap {
            Self.relayScope(
                forRelayHost: $0.host,
                allowsPrivateOverlay: developmentRelaySettings.allowsPrivateOverlay
            )
        }
        if let pairingRelayConfiguration,
           !PairingSession.hasCompleteCanonicalRelayQRCodeMaterial(
               relayHost: pairingRelayConfiguration.host,
               relayPort: Int(pairingRelayConfiguration.port),
               relayID: pairingRelayConfiguration.relayID,
               relaySecret: pairingRelayConfiguration.relaySecret,
               relayExpiresAtEpochMillis: relayRouteLease?.expiresAtEpochMillis,
               relayNonce: relayRouteLease?.nonce,
               relayScope: pairingRelayScope
           ) {
            let endpoint = "\(pairingRelayConfiguration.host):\(pairingRelayConfiguration.port)"
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationRejected,
                endpoint: endpoint,
                message: "Connection details could not be encoded safely in the pairing QR."
            )
            log("Remote pairing QR not generated: connection details for \(endpoint) are not canonical")
            return
        }
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
            relayScope: pairingRelayScope
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
        guard !isRemoteRoutePreparationInFlight else {
            return .allocationFailed(
                endpoint: trimmedHost.isEmpty ? "connection service" : "\(trimmedHost):\(port)",
                message: "Connection preparation is already in progress."
            )
        }
        clearCompletedRelayConfigurationRequestState()
        invalidateRouteAllocationRequests(routeStateChanged: true)
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
                    timeout: 5,
                    cancellation: makeRouteAllocationCancellation()
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
                let endpoint = settings.endpointLabel ?? "\(configuration.host):\(configuration.port)"
                guard applyDevelopmentRelaySettings(settings, lease: allocation.lease) else {
                    return .allocationFailed(
                        endpoint: endpoint,
                        message: Self.relaySecretPersistenceFailureMessage
                    )
                }
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
                let endpoint = settings.endpointLabel ?? "\(trimmedHost):\(port)"
                guard applyDevelopmentRelaySettings(settings, lease: nil) else {
                    return .allocationFailed(
                        endpoint: endpoint,
                        message: Self.relaySecretPersistenceFailureMessage
                    )
                }
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
        guard applyDevelopmentRelaySettings(settings, lease: nil) else {
            return .allocationFailed(
                endpoint: settings.endpointLabel ?? "\(trimmedHost):\(port)",
                message: Self.relaySecretPersistenceFailureMessage
            )
        }
        log("Remote route configured: \(trimmedHost):\(port)")
        return .savedStatic(endpoint: settings.endpointLabel ?? "\(trimmedHost):\(port)")
    }

    @discardableResult
    public func requestConfigureDevelopmentRelayForUserInterface(
        host: String,
        port: UInt16,
        relaySecret: String? = nil,
        attemptAllocation: Bool = false,
        allowsPrivateOverlay: Bool = false
    ) -> CompanionRelayConfigurationRequestResult {
        guard !isRemoteRoutePreparationInFlight else {
            let endpoint = host.trimmingCharacters(in: .whitespacesAndNewlines)
            return .completed(.allocationFailed(
                endpoint: endpoint.isEmpty ? "connection service" : "\(endpoint):\(port)",
                message: "Connection preparation is already in progress."
            ))
        }
        clearCompletedRelayConfigurationRequestState()
        guard attemptAllocation else {
            return .completed(configureDevelopmentRelay(
                host: host,
                port: port,
                relaySecret: relaySecret,
                attemptAllocation: false,
                allowsPrivateOverlay: allowsPrivateOverlay
            ))
        }
        let trimmedHost = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedHost.isEmpty else {
            clearDevelopmentRelay()
            return .completed(.disabled)
        }
        guard CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: trimmedHost) != .invalidFormat else {
            return .completed(configureDevelopmentRelay(
                host: trimmedHost,
                port: port,
                relaySecret: relaySecret,
                attemptAllocation: false,
                allowsPrivateOverlay: allowsPrivateOverlay
            ))
        }

        let secret = relaySecret?.takeIfNotEmpty() ?? Self.generateRelaySecret()
        let authorization: (
            identity: RelayRuntimeIdentity,
            signer: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning
        )
        do {
            authorization = try relayAllocationAuthorization()
        } catch {
            applyFailedDevelopmentRelayAllocation(
                host: trimmedHost,
                port: port,
                secret: secret,
                allowsPrivateOverlay: allowsPrivateOverlay,
                message: error.localizedDescription
            )
            let endpoint = "\(trimmedHost):\(port)"
            return .completed(.allocationFailed(
                endpoint: endpoint,
                message: error.localizedDescription
            ))
        }

        let requestContext = CompanionRelayConfigurationRequestContext(
            requestID: UUID(),
            operation: .developmentRelay
        )
        let request = beginRouteAllocationRequest(
            timeoutIssueKind: .automaticPreparationFailed,
            timeoutEndpoint: "\(trimmedHost):\(port)",
            timeoutBehavior: .saveStaticDevelopmentRelay(
                host: trimmedHost,
                port: port,
                secret: secret,
                allowsPrivateOverlay: allowsPrivateOverlay
            ),
            userInterfaceRequestContext: requestContext,
            userInterfaceFallbackEndpoint: "\(trimmedHost):\(port)"
        )
        let allocator = relayServiceRouteAllocator
        let allocationToken = environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty()
        companionRelayAllocationIOQueue.async { [weak self] in
            let outcome: CompanionRouteAllocationOutcome
            do {
                let serviceAllocation = try allocator.allocateRelayRoute(
                    host: trimmedHost,
                    port: port,
                    routeToken: request.routeToken,
                    allocationToken: allocationToken,
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer,
                    timeout: 5,
                    cancellation: request.cancellation
                )
                outcome = .allocation(try serviceAllocation.attachingEndpointSecret(
                    secret,
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer
                ))
            } catch {
                outcome = .failure(error.localizedDescription)
            }
            Task { @MainActor [weak self] in
                self?.applyDevelopmentRelayAllocationForUserInterface(
                    outcome,
                    request: request,
                    requestedHost: trimmedHost,
                    requestedPort: port,
                    secret: secret,
                    allowsPrivateOverlay: allowsPrivateOverlay
                )
            }
        }
        return .started(requestID: requestContext.requestID)
    }

    public func clearDevelopmentRelay() {
        clearCompletedRelayConfigurationRequestState()
        invalidateRouteAllocationRequests(routeStateChanged: true)
        Self.clearSavedDevelopmentRelaySettings(
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        )
        Self.clearSavedRemoteRouteLease(defaults: userDefaults)
        developmentRelaySettings = .disabled
        developmentRelaySecretSource = .none
        relayConfiguration = nil
        allocatedRemoteRouteLease = nil
        runtimeConnectionManager.stopBootstrap()
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(status: .stopped)
        remoteRoutePreparationIssue = nil
        cancelPendingRemotePairingPreparation()
        refreshTransportStatusText()
        log("Remote route disabled")
    }

    @discardableResult
    public func requestClearDevelopmentRelayForUserInterface() -> Bool {
        guard !isRemoteRoutePreparationInFlight else { return false }
        clearDevelopmentRelay()
        return true
    }

    @discardableResult
    public func configureBootstrapRelay(
        endpoints: String,
        allocationToken: String? = nil,
        allowsPrivateOverlay: Bool = false
    ) -> CompanionRelayConfigurationResult {
        let trimmedEndpoints = endpoints.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !isRemoteRoutePreparationInFlight else {
            return .allocationFailed(
                endpoint: trimmedEndpoints.isEmpty ? "connection service" : trimmedEndpoints,
                message: "Connection preparation is already in progress."
            )
        }
        clearCompletedRelayConfigurationRequestState()
        guard !trimmedEndpoints.isEmpty else {
            clearBootstrapRelay()
            return .disabled
        }
        guard EnvironmentRemoteRelayRouteAllocator.hasValidBootstrapRelayEndpoints(trimmedEndpoints) else {
            let message = "Enter at least one valid connection service address."
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationRejected,
                endpoint: trimmedEndpoints,
                message: message
            )
            log("Bootstrap route configuration rejected: \(message)")
            return .allocationFailed(endpoint: trimmedEndpoints, message: message)
        }

        invalidateRouteAllocationRequests(routeStateChanged: true)

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

    @discardableResult
    public func requestConfigureBootstrapRelayForUserInterface(
        endpoints: String,
        allocationToken: String? = nil,
        allowsPrivateOverlay: Bool = false
    ) -> CompanionRelayConfigurationRequestResult {
        guard !isRemoteRoutePreparationInFlight else {
            let endpoint = endpoints.trimmingCharacters(in: .whitespacesAndNewlines)
            return .completed(.allocationFailed(
                endpoint: endpoint.isEmpty ? "connection service" : endpoint,
                message: "Connection preparation is already in progress."
            ))
        }
        clearCompletedRelayConfigurationRequestState()
        let trimmedEndpoints = endpoints.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedEndpoints.isEmpty else {
            clearBootstrapRelay()
            return .completed(.disabled)
        }
        guard EnvironmentRemoteRelayRouteAllocator.hasValidBootstrapRelayEndpoints(trimmedEndpoints) else {
            let message = "Enter at least one valid connection service address."
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationRejected,
                endpoint: trimmedEndpoints,
                message: message
            )
            log("Bootstrap route configuration rejected: \(message)")
            return .completed(.allocationFailed(endpoint: trimmedEndpoints, message: message))
        }

        invalidateRouteAllocationRequests(routeStateChanged: true)
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
        let requestContext = CompanionRelayConfigurationRequestContext(
            requestID: UUID(),
            operation: .bootstrapRelay
        )
        guard requestAutomaticRemoteRelayRouteAllocation(
            restartRelayClientIfRunning: true,
            startRelayAfterCompletion: false,
            pairingRequest: false,
            userInterfaceRequestContext: requestContext,
            userInterfaceFallbackEndpoint: settings.endpointLabel ?? trimmedEndpoints
        ) else {
            let message = remoteRoutePreparationIssue?.message
                ?? "Connection preparation did not return route details."
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationUnavailable,
                endpoint: settings.endpointLabel,
                message: message
            )
            return .completed(.allocationFailed(
                endpoint: settings.endpointLabel ?? trimmedEndpoints,
                message: message
            ))
        }
        return .started(requestID: requestContext.requestID)
    }

    public func clearBootstrapRelay() {
        clearCompletedRelayConfigurationRequestState()
        invalidateRouteAllocationRequests(routeStateChanged: true)
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

    @discardableResult
    public func requestClearBootstrapRelayForUserInterface() -> Bool {
        guard !isRemoteRoutePreparationInFlight else { return false }
        clearBootstrapRelay()
        return true
    }

    public func regenerateDevelopmentRelaySecret() {
        guard developmentRelaySettings.isEnabled,
              !isRemoteRoutePreparationInFlight
        else {
            return
        }
        clearCompletedRelayConfigurationRequestState()
        invalidateRouteAllocationRequests(routeStateChanged: true)
        let settings = CompanionDevelopmentRelaySettings(
            isEnabled: true,
            host: developmentRelaySettings.host,
            port: developmentRelaySettings.port,
            relayID: discoveryRouteToken,
            relaySecret: Self.generateRelaySecret(),
            isEnvironmentOverride: false,
            allowsPrivateOverlay: developmentRelaySettings.allowsPrivateOverlay
        )
        guard applyDevelopmentRelaySettings(settings, lease: nil) else { return }
        log("Route secret regenerated")
    }

    private func beginRouteAllocationRequest(
        timeoutIssueKind: CompanionRemoteRoutePreparationIssue.Kind,
        timeoutEndpoint: String?,
        timeoutBehavior: CompanionRouteAllocationTimeoutBehavior = .none,
        userInterfaceRequestContext: CompanionRelayConfigurationRequestContext? = nil,
        userInterfaceFallbackEndpoint: String? = nil
    ) -> CompanionRouteAllocationRequest {
        precondition(!hasRouteAllocationWorkerInFlight, "Route allocation worker overlap is forbidden")
        routeAllocationRequestGeneration += 1
        let request = CompanionRouteAllocationRequest(
            routeStateRevision: routeStateRevision,
            generation: routeAllocationRequestGeneration,
            routeToken: discoveryRouteToken,
            cancellation: makeRouteAllocationCancellation(),
            timeoutIssueKind: timeoutIssueKind,
            timeoutEndpoint: timeoutEndpoint,
            timeoutBehavior: timeoutBehavior,
            userInterfaceRequestContext: userInterfaceRequestContext,
            userInterfaceFallbackEndpoint: userInterfaceFallbackEndpoint
        )
        activeRouteAllocationRequest = request
        relayConfigurationRequestState = userInterfaceRequestContext.map {
            CompanionRelayConfigurationRequestState.active($0)
        }
        refreshRemoteRoutePreparationInFlightState()
        scheduleRouteAllocationTimeout(for: request)
        return request
    }

    private func makeRouteAllocationCancellation() -> RelayRouteAllocationCancellation {
        RelayRouteAllocationCancellation(
            timeout: TimeInterval(routeAllocationTimeoutNanoseconds) / 1_000_000_000
        )
    }

    private func finishRouteAllocationRequestIfCurrent(
        _ request: CompanionRouteAllocationRequest
    ) -> Bool {
        if drainingRouteAllocationRequest == request {
            drainingRouteAllocationRequest = nil
            refreshRemoteRoutePreparationInFlightState()
            return false
        }
        guard activeRouteAllocationRequest == request,
              request.routeStateRevision == routeStateRevision,
              request.generation == routeAllocationRequestGeneration,
              request.routeToken == discoveryRouteToken
        else {
            return false
        }
        routeAllocationTimeoutTask?.cancel()
        routeAllocationTimeoutTask = nil
        request.cancellation.cancel()
        activeRouteAllocationRequest = nil
        refreshRemoteRoutePreparationInFlightState()
        return true
    }

    private func invalidateRouteAllocationRequests(routeStateChanged: Bool) {
        clearCompletedRelayConfigurationRequestState()
        if routeStateChanged {
            routeStateRevision += 1
        }
        routeAllocationRequestGeneration += 1
        routeAllocationTimeoutTask?.cancel()
        routeAllocationTimeoutTask = nil
        if let request = activeRouteAllocationRequest {
            publishRelayConfigurationRequestCompletion(
                for: request,
                result: .allocationFailed(
                    endpoint: request.userInterfaceFallbackEndpoint
                        ?? request.timeoutEndpoint
                        ?? "connection service",
                    message: "Connection preparation was cancelled before completion."
                )
            )
            request.cancellation.cancel()
            drainingRouteAllocationRequest = request
            activeRouteAllocationRequest = nil
        }
        refreshRemoteRoutePreparationInFlightState()
    }

    private var hasRouteAllocationWorkerInFlight: Bool {
        activeRouteAllocationRequest != nil || drainingRouteAllocationRequest != nil
    }

    private func refreshRemoteRoutePreparationInFlightState() {
        isRemoteRoutePreparationInFlight = hasRouteAllocationWorkerInFlight ||
            pendingRemotePairingPreparationID != nil
    }

    private func scheduleRouteAllocationTimeout(for request: CompanionRouteAllocationRequest) {
        routeAllocationTimeoutTask?.cancel()
        let timeoutNanoseconds = routeAllocationTimeoutNanoseconds
        routeAllocationTimeoutTask = Task { [weak self] in
            do {
                try await Task.sleep(nanoseconds: timeoutNanoseconds)
            } catch {
                return
            }
            guard !Task.isCancelled else { return }
            self?.failRouteAllocationIfCurrent(request)
        }
    }

    private func failRouteAllocationIfCurrent(_ request: CompanionRouteAllocationRequest) {
        guard activeRouteAllocationRequest == request,
              request.routeStateRevision == routeStateRevision,
              request.generation == routeAllocationRequestGeneration,
              request.routeToken == discoveryRouteToken
        else {
            return
        }

        request.cancellation.cancel()
        routeAllocationTimeoutTask = nil
        drainingRouteAllocationRequest = request
        activeRouteAllocationRequest = nil
        routeAllocationRequestGeneration += 1
        if pendingRemotePairingPreparationID != nil {
            cancelPendingRemotePairingPreparation()
        } else {
            refreshRemoteRoutePreparationInFlightState()
        }

        let message = "Connection preparation timed out."
        switch request.timeoutBehavior {
        case .none:
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: request.timeoutIssueKind,
                endpoint: request.timeoutEndpoint,
                message: message
            )
        case .saveStaticDevelopmentRelay(let host, let port, let secret, let allowsPrivateOverlay):
            applyFailedDevelopmentRelayAllocation(
                host: host,
                port: port,
                secret: secret,
                allowsPrivateOverlay: allowsPrivateOverlay,
                message: message
            )
        case .startConfiguredRelay:
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: request.timeoutIssueKind,
                endpoint: request.timeoutEndpoint,
                message: message
            )
            if isRuntimeStarted {
                startRelayClientIfConfigured()
            }
        }
        log("Remote route allocation timed out for \(request.timeoutEndpoint ?? "connection service")")
        publishRelayConfigurationRequestCompletion(
            for: request,
            result: .allocationFailed(
                endpoint: request.userInterfaceFallbackEndpoint
                    ?? request.timeoutEndpoint
                    ?? "connection service",
                message: message
            )
        )
    }

    private func publishRelayConfigurationRequestCompletion(
        for request: CompanionRouteAllocationRequest,
        result: CompanionRelayConfigurationResult
    ) {
        guard let context = request.userInterfaceRequestContext else { return }
        relayConfigurationRequestState = .completed(CompanionRelayConfigurationRequestCompletion(
            requestID: context.requestID,
            operation: context.operation,
            result: result
        ))
    }

    private func hasUserInterfaceRequestContext(
        _ request: CompanionRouteAllocationRequest
    ) -> Bool {
        request.userInterfaceRequestContext != nil
    }

    private func publishCurrentRelayConfigurationRequestCompletion(
        for request: CompanionRouteAllocationRequest
    ) {
        guard hasUserInterfaceRequestContext(request) else { return }
        if let issue = remoteRoutePreparationIssue {
            publishRelayConfigurationRequestCompletion(
                for: request,
                result: .allocationFailed(
                    endpoint: issue.endpoint
                        ?? request.userInterfaceFallbackEndpoint
                        ?? request.timeoutEndpoint
                        ?? "connection service",
                    message: issue.message
                )
            )
        } else if let endpoint = developmentRelayEndpoint {
            publishRelayConfigurationRequestCompletion(
                for: request,
                result: .allocated(endpoint: endpoint)
            )
        } else {
            publishRelayConfigurationRequestCompletion(
                for: request,
                result: .allocationFailed(
                    endpoint: request.userInterfaceFallbackEndpoint
                        ?? request.timeoutEndpoint
                        ?? "connection service",
                    message: "Connection preparation did not return route details."
                )
            )
        }
    }

    @discardableResult
    private func requestAutomaticRemoteRelayRouteAllocation(
        restartRelayClientIfRunning shouldRestartRelayClient: Bool,
        startRelayAfterCompletion: Bool,
        pairingRequest: Bool,
        userInterfaceRequestContext: CompanionRelayConfigurationRequestContext? = nil,
        userInterfaceFallbackEndpoint: String? = nil
    ) -> Bool {
        guard !hasRouteAllocationWorkerInFlight else { return false }
        let authorization: (
            identity: RelayRuntimeIdentity,
            signer: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning
        )
        do {
            authorization = try relayAllocationAuthorization()
        } catch {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationFailed,
                message: error.localizedDescription
            )
            log("Remote route bootstrap failed: \(error.localizedDescription)")
            if pairingRequest {
                cancelPendingRemotePairingPreparation()
                log("Remote pairing QR not generated: \(error.localizedDescription)")
            }
            return false
        }

        let preferredRelaySecret = developmentRelaySettings.relaySecret?.takeIfNotEmpty()
            ?? Self.loadSavedRelaySecret(
                deviceID: macDeviceID,
                relayID: developmentRelaySettings.relayID,
                defaults: userDefaults,
                relaySecretStore: relaySecretStore
        )
        let allocator = remoteRelayRouteAllocator
        let timeoutEndpoint = bootstrapRelaySettings.endpointLabel
            ?? developmentRelaySettings.endpointLabel
            ?? "connection service"
        let request = beginRouteAllocationRequest(
            timeoutIssueKind: pairingRequest ? .relayConnectionFailed : .automaticPreparationFailed,
            timeoutEndpoint: timeoutEndpoint,
            timeoutBehavior: startRelayAfterCompletion ? .startConfiguredRelay : .none,
            userInterfaceRequestContext: userInterfaceRequestContext,
            userInterfaceFallbackEndpoint: userInterfaceFallbackEndpoint
        )
        let runtimeDeviceID = macDeviceID
        companionRelayAllocationIOQueue.async { [weak self] in
            let outcome: CompanionRouteAllocationOutcome
            do {
                outcome = .allocation(try allocator.allocateRemoteRelayRoute(
                    runtimeDeviceID: runtimeDeviceID,
                    routeToken: request.routeToken,
                    preferredRelaySecret: preferredRelaySecret,
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer,
                    cancellation: request.cancellation
                ))
            } catch {
                outcome = .failure(error.localizedDescription)
            }
            Task { @MainActor [weak self] in
                self?.applyAutomaticRemoteRelayRouteAllocation(
                    outcome,
                    request: request,
                    preferredRelaySecret: preferredRelaySecret,
                    restartRelayClientIfRunning: shouldRestartRelayClient,
                    startRelayAfterCompletion: startRelayAfterCompletion,
                    pairingRequest: pairingRequest
                )
            }
        }
        return true
    }

    private func applyAutomaticRemoteRelayRouteAllocation(
        _ outcome: CompanionRouteAllocationOutcome,
        request: CompanionRouteAllocationRequest,
        preferredRelaySecret: String?,
        restartRelayClientIfRunning shouldRestartRelayClient: Bool,
        startRelayAfterCompletion: Bool,
        pairingRequest: Bool
    ) {
        guard finishRouteAllocationRequestIfCurrent(request) else { return }

        switch outcome {
        case .failure(let message):
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationFailed,
                endpoint: bootstrapRelaySettings.endpointLabel,
                message: message
            )
            log("Remote route bootstrap failed: \(message)")
        case .allocation(nil):
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationUnavailable,
                endpoint: bootstrapRelaySettings.endpointLabel,
                message: "Connection preparation did not return route details."
            )
            log("Remote route bootstrap unavailable: connection preparation did not return route details")
        case .allocation(.some(let allocation)):
            if !isEligibleAutomaticRelayHost(allocation.configuration.host) {
                let endpoint = "\(allocation.configuration.host):\(allocation.configuration.port)"
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .automaticPreparationRejected,
                    endpoint: endpoint,
                    message: "This AetherLink Runtime connection address is not reachable from another network."
                )
                log("Remote route bootstrap rejected unreachable connection address \(allocation.configuration.host)")
            } else if !acceptsRemoteRouteAllocation(allocation) {
                let endpoint = "\(allocation.configuration.host):\(allocation.configuration.port)"
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .automaticPreparationRejected,
                    endpoint: endpoint,
                    message: "Remote route lease did not advance."
                )
                log("Remote route bootstrap rejected non-advancing lease for \(endpoint)")
            } else {
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
                if applyDevelopmentRelaySettings(
                    settings,
                    lease: allocation.lease,
                    restartRelayClient: shouldRestartRelayClient
                ) {
                    log("Remote route bootstrap allocated route \(settings.endpointLabel ?? "configured route")")
                }
            }
        }

        if startRelayAfterCompletion, isRuntimeStarted {
            startRelayClientIfConfigured()
        }
        publishCurrentRelayConfigurationRequestCompletion(for: request)
        completePairingRoutePreparationAfterAllocationIfNeeded(pairingRequest: pairingRequest)
    }

    @discardableResult
    private func requestConfiguredRelayRouteLeaseRefreshForUserInterface(
        pairingRequest: Bool = true
    ) -> Bool {
        guard !hasRouteAllocationWorkerInFlight else { return false }
        guard developmentRelaySettings.isEnabled,
              let currentConfiguration = relayConfiguration
        else {
            return false
        }
        guard isEligibleAutomaticRelayHost(currentConfiguration.host) else {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .routeLeaseRefreshRejected,
                endpoint: developmentRelaySettings.endpointLabel,
                message: "This AetherLink Runtime connection address is not reachable from another network."
            )
            return false
        }
        guard let relaySecret = currentConfiguration.relaySecret?.takeIfNotEmpty()
            ?? developmentRelaySettings.relaySecret?.takeIfNotEmpty()
        else {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .routeLeaseSecretMissing,
                endpoint: developmentRelaySettings.endpointLabel,
                message: "Route secret is missing."
            )
            return false
        }
        let authorization: (
            identity: RelayRuntimeIdentity,
            signer: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning
        )
        do {
            authorization = try relayAllocationAuthorization()
        } catch {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .routeLeaseRefreshFailed,
                endpoint: developmentRelaySettings.endpointLabel,
                message: error.localizedDescription
            )
            return false
        }

        let request = beginRouteAllocationRequest(
            timeoutIssueKind: .routeLeaseRefreshFailed,
            timeoutEndpoint: developmentRelaySettings.endpointLabel
        )
        let allocator = relayServiceRouteAllocator
        let allocationToken = environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]?.takeIfNotEmpty()
        companionRelayAllocationIOQueue.async { [weak self] in
            let outcome: CompanionRouteAllocationOutcome
            do {
                let serviceAllocation = try allocator.allocateRelayRoute(
                    host: currentConfiguration.host,
                    port: currentConfiguration.port,
                    routeToken: request.routeToken,
                    allocationToken: allocationToken,
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer,
                    timeout: 5,
                    cancellation: request.cancellation
                )
                outcome = .allocation(try serviceAllocation.attachingEndpointSecret(
                    relaySecret,
                    runtimeIdentity: authorization.identity,
                    identityAuthorizationSigner: authorization.signer
                ))
            } catch {
                outcome = .failure(error.localizedDescription)
            }
            Task { @MainActor [weak self] in
                self?.applyConfiguredRelayRouteLeaseRefreshForUserInterface(
                    outcome,
                    request: request,
                    relaySecret: relaySecret,
                    pairingRequest: pairingRequest
                )
            }
        }
        return true
    }

    private func applyConfiguredRelayRouteLeaseRefreshForUserInterface(
        _ outcome: CompanionRouteAllocationOutcome,
        request: CompanionRouteAllocationRequest,
        relaySecret: String,
        pairingRequest: Bool
    ) {
        guard finishRouteAllocationRequestIfCurrent(request) else { return }
        switch outcome {
        case .failure(let resolvedMessage):
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .routeLeaseRefreshFailed,
                endpoint: developmentRelaySettings.endpointLabel,
                message: resolvedMessage
            )
            log("Remote route lease refresh failed: \(resolvedMessage)")
        case .allocation(nil):
            let resolvedMessage = "Remote route allocation response was invalid."
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .routeLeaseRefreshFailed,
                endpoint: developmentRelaySettings.endpointLabel,
                message: resolvedMessage
            )
            log("Remote route lease refresh failed: \(resolvedMessage)")
        case .allocation(.some(let allocation)):
            let endpoint = "\(allocation.configuration.host):\(allocation.configuration.port)"
            if !isEligibleAutomaticRelayHost(allocation.configuration.host) {
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .routeLeaseRefreshRejected,
                    endpoint: endpoint,
                    message: "This AetherLink Runtime connection address is not reachable from another network."
                )
            } else if !acceptsRemoteRouteAllocation(allocation) {
                remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                    kind: .routeLeaseRefreshRejected,
                    endpoint: endpoint,
                    message: "Remote route lease did not advance."
                )
            } else {
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
                if applyDevelopmentRelaySettings(settings, lease: allocation.lease) {
                    log("Remote route lease refreshed: \(settings.endpointLabel ?? "configured route")")
                }
            }
        }
        completePairingRoutePreparationAfterAllocationIfNeeded(pairingRequest: pairingRequest)
    }

    private func completePairingRoutePreparationAfterAllocationIfNeeded(pairingRequest: Bool) {
        guard pairingRequest else { return }
        if let issue = remoteRoutePreparationIssue {
            cancelPendingRemotePairingPreparation()
            log("Remote pairing QR not generated: \(issue.message)")
            return
        }
        generatePendingRemotePairingQRCodeIfReady()
    }

    private func applyDevelopmentRelayAllocationForUserInterface(
        _ outcome: CompanionRouteAllocationOutcome,
        request: CompanionRouteAllocationRequest,
        requestedHost: String,
        requestedPort: UInt16,
        secret: String,
        allowsPrivateOverlay: Bool
    ) {
        guard finishRouteAllocationRequestIfCurrent(request) else { return }
        switch outcome {
        case .failure(let resolvedMessage):
            applyFailedDevelopmentRelayAllocation(
                host: requestedHost,
                port: requestedPort,
                secret: secret,
                allowsPrivateOverlay: allowsPrivateOverlay,
                message: resolvedMessage
            )
        case .allocation(nil):
            applyFailedDevelopmentRelayAllocation(
                host: requestedHost,
                port: requestedPort,
                secret: secret,
                allowsPrivateOverlay: allowsPrivateOverlay,
                message: "Remote route allocation response was invalid."
            )
        case .allocation(.some(let allocation)):
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
                publishCurrentRelayConfigurationRequestCompletion(for: request)
                return
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
            if applyDevelopmentRelaySettings(settings, lease: allocation.lease) {
                log("Remote route allocated: \(settings.endpointLabel ?? "\(configuration.host):\(configuration.port)")")
            }
        }
        publishCurrentRelayConfigurationRequestCompletion(for: request)
    }

    private func applyFailedDevelopmentRelayAllocation(
        host: String,
        port: UInt16,
        secret: String,
        allowsPrivateOverlay: Bool,
        message: String
    ) {
        let settings = CompanionDevelopmentRelaySettings(
            isEnabled: true,
            host: host,
            port: port,
            relayID: discoveryRouteToken,
            relaySecret: secret,
            isEnvironmentOverride: false,
            allowsPrivateOverlay: allowsPrivateOverlay || Self.allowsPrivateOverlayRelayEnvironment(environment)
        )
        guard applyDevelopmentRelaySettings(settings, lease: nil) else { return }
        let endpoint = settings.endpointLabel ?? "\(host):\(port)"
        remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
            kind: .automaticPreparationFailed,
            endpoint: endpoint,
            message: message
        )
        log("Remote route allocation failed: \(message)")
    }

    private func allocateRemoteRelayRouteIfAvailable(restartRelayClientIfRunning shouldRestartRelayClient: Bool = true) {
        guard !hasRouteAllocationWorkerInFlight else { return }
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
                identityAuthorizationSigner: authorization.signer,
                cancellation: makeRouteAllocationCancellation()
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
            guard applyDevelopmentRelaySettings(
                settings,
                lease: allocation.lease,
                restartRelayClient: shouldRestartRelayClient
            ) else {
                return
            }
            log("Remote route bootstrap allocated route \(settings.endpointLabel ?? "configured route")")
        } catch {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationFailed,
                message: error.localizedDescription
            )
            log("Remote route bootstrap failed: \(error.localizedDescription)")
        }
    }

    private var shouldRenewSavedBootstrapRelayRoute: Bool {
        developmentRelaySettings.isEnabled &&
            relayConfiguration != nil &&
            canAttemptAutomaticRemoteRouteAllocation &&
            !hasFreshCurrentRemoteRouteLease
    }

    private var hasFreshCurrentRemoteRouteLease: Bool {
        guard relayConfiguration != nil,
              let allocatedRemoteRouteLease
        else {
            return false
        }
        return isRelayRouteLeaseFreshForPairingQRCode(allocatedRemoteRouteLease)
    }

    private var hasCanonicalFreshRemoteRouteMaterialForQRCode: Bool {
        guard hasSecureFreshRemoteRouteMaterialForQRCode,
              let relayConfiguration,
              let relaySecret = relayConfiguration.relaySecret?.takeIfNotEmpty(),
              let lease = relayRouteLeaseForPairing(relayConfiguration: relayConfiguration)
        else {
            return false
        }
        return PairingSession.hasCompleteCanonicalRelayQRCodeMaterial(
            relayHost: relayConfiguration.host,
            relayPort: Int(relayConfiguration.port),
            relayID: relayConfiguration.relayID,
            relaySecret: relaySecret,
            relayExpiresAtEpochMillis: lease.expiresAtEpochMillis,
            relayNonce: lease.nonce,
            relayScope: Self.relayScope(
                forRelayHost: relayConfiguration.host,
                allowsPrivateOverlay: developmentRelaySettings.allowsPrivateOverlay
            )
        )
    }

    private var hasSecureFreshRemoteRouteMaterialForQRCode: Bool {
        guard isDevelopmentRelayRouteEligibleForQRCode,
              hasFreshCurrentRemoteRouteLease,
              let relayConfiguration,
              let relaySecret = relayConfiguration.relaySecret?.takeIfNotEmpty()
        else {
            return false
        }
        return hasSecureRelaySecretForQRCode(
            relaySecret,
            relayID: relayConfiguration.relayID
        )
    }

    private func hasSecureRelaySecretForQRCode(_ relaySecret: String, relayID: String) -> Bool {
        switch developmentRelaySecretSource {
        case .none:
            return false
        case .environmentEphemeral:
            return Self.explicitEnvironmentRelaySecret(
                environment: environment,
                settings: developmentRelaySettings
            ) == relaySecret
        case .protectedStore:
            break
        }
        let expectedSecretRef = Self.relaySecretRef(deviceID: macDeviceID, relayID: relayID)
        guard userDefaults.string(forKey: RelayDefaults.secretRef)?.takeIfNotEmpty() == expectedSecretRef else {
            return false
        }
        return relaySecretStore.readSecret(for: expectedSecretRef)?.takeIfNotEmpty() == relaySecret
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

    @discardableResult
    private func applyDevelopmentRelaySettings(
        _ settings: CompanionDevelopmentRelaySettings,
        lease: CompanionRemoteRouteLease?,
        restartRelayClient: Bool = true
    ) -> Bool {
        guard Self.saveDevelopmentRelaySettings(
            settings,
            deviceID: macDeviceID,
            defaults: userDefaults,
            relaySecretStore: relaySecretStore
        ) else {
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .routeLeaseSecretMissing,
                endpoint: settings.endpointLabel,
                message: Self.relaySecretPersistenceFailureMessage
            )
            log("Remote route rejected: connection secret persistence failed")
            return false
        }
        if let lease {
            Self.saveRemoteRouteLease(lease, relaySettings: settings, defaults: userDefaults)
        } else {
            Self.clearSavedRemoteRouteLease(defaults: userDefaults)
        }
        developmentRelaySettings = settings
        developmentRelaySecretSource = settings.relaySecret?.takeIfNotEmpty() == nil
            ? .none
            : .protectedStore
        relayConfiguration = Self.relayConfiguration(for: settings, lease: lease)
        allocatedRemoteRouteLease = lease
        developmentRelayConnectionStatus = CompanionDevelopmentRelayStatus(
            status: .stopped,
            endpoint: settings.endpointLabel
        )
        if pendingRemotePairingPreparationID != nil {
            pendingRemotePairingEndpoint = settings.endpointLabel
        }
        remoteRoutePreparationIssue = nil
        if restartRelayClient {
            restartRelayClientIfRunning()
        }
        refreshTransportStatusText()
        return true
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
        _ = await reloadTrustedDevicesForPairScopedTransportStart()
    }

    private func reloadTrustedDevicesForPairScopedTransportStart() async -> [TrustedDevice]? {
        do {
            let loadedTrustedDevices = try await trustedDeviceStore.load()
            trustedDevices = loadedTrustedDevices
            return loadedTrustedDevices
        } catch {
            log("Trusted device load failed: \(error.localizedDescription)")
            return nil
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
        configuration: RelayPeerConfiguration,
        trustedDevices: [TrustedDevice]
    ) -> Bool {
        let matchingTrustedDevices = trustedDevices.filter { device in
            guard let fingerprint = try? PairedRelayAllocationAuthorization.publicKeyFingerprint(
                publicKeyBase64: device.publicKeyBase64
            ) else {
                return false
            }
            return fingerprint == clientKeyFingerprint
        }
        guard matchingTrustedDevices.count == 1,
              matchingTrustedDevices[0].productionPairState == nil
        else {
            log("Legacy pair-scoped transport start rejected")
            return false
        }

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
            return false
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
        return true
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
        Task { [weak self] in
            await self?.reconcilePendingPairActivation(fingerprint: fingerprint)
        }
    }

    private func invalidatePairLifecycle(fingerprint: String) {
        pairLifecycleGenerations[fingerprint] = UUID()
        inFlightPairRefreshSequences.removeValue(forKey: fingerprint)
        pendingPairedRelayActivations.removeValue(forKey: fingerprint)
    }

    private func reconcilePendingPairActivation(fingerprint: String) async {
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

        guard let loadedTrustedDevices = await reloadTrustedDevicesForPairScopedTransportStart(),
              runtimeLifecycleGeneration == pendingActivation.runtimeLifecycleGeneration,
              pairLifecycleGenerations[fingerprint] == pendingActivation.pairLifecycleGeneration,
              pairScopedRelayRoutes[fingerprint] == storedRoute
        else {
            return
        }
        guard startPairScopedTransports(
            clientKeyFingerprint: fingerprint,
            configuration: pairScopedRelayConfiguration(storedRoute),
            trustedDevices: loadedTrustedDevices
        ) else {
            return
        }
        if pendingActivation.rotatesBootstrapRoute {
            rotateBootstrapRouteAfterPairClaim()
        }
    }

    private func startRestoredPairScopedTransports(
        now: Date = Date(),
        expectedRuntimeLifecycleGeneration: UUID
    ) async {
        guard let loadedTrustedDevices = await reloadTrustedDevicesForPairScopedTransportStart(),
              isRuntimeStarted,
              runtimeLifecycleGeneration == expectedRuntimeLifecycleGeneration
        else {
            return
        }
        let nowEpochMillis = Int64((now.timeIntervalSince1970 * 1_000).rounded())
        for route in pairScopedRelayRoutes.values.sorted(by: {
            $0.clientKeyFingerprint < $1.clientKeyFingerprint
        }) where route.relayExpiresAtEpochMillis > nowEpochMillis {
            guard pairScopedRelayRoutes[route.clientKeyFingerprint] == route,
                  runtimeLifecycleGeneration == expectedRuntimeLifecycleGeneration
            else {
                continue
            }
            _ = startPairScopedTransports(
                clientKeyFingerprint: route.clientKeyFingerprint,
                configuration: pairScopedRelayConfiguration(route),
                trustedDevices: loadedTrustedDevices
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
        invalidateRouteAllocationRequests(routeStateChanged: true)
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
        if canAttemptAutomaticRemoteRouteAllocation {
            _ = requestAutomaticRemoteRelayRouteAllocation(
                restartRelayClientIfRunning: true,
                startRelayAfterCompletion: false,
                pairingRequest: false
            )
        }
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
            refreshPendingRemotePairingRouteIfNeeded()
            clearRelayConnectionIssueIfRouteIsUsable()
            log("Remote route ready: \(endpoint)")
            generatePendingRemotePairingQRCodeIfReady()
        case .waitingForPeer:
            refreshPendingRemotePairingRouteIfNeeded()
            clearRelayConnectionIssueIfRouteIsUsable()
            generatePendingRemotePairingQRCodeIfReady()
        case .failed(let message):
            remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
                kind: .relayConnectionFailed,
                endpoint: endpoint,
                message: message
            )
            log("Remote route failed: \(endpoint): \(message)")
            let renewalStarted = renewRelayRouteAfterFailureIfNeeded(endpoint: endpoint)
            if !renewalStarted, remoteRoutePreparationIssue != nil {
                cancelPendingRemotePairingPreparation()
            }
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

    @discardableResult
    private func renewRelayRouteAfterFailureIfNeeded(endpoint: String) -> Bool {
        guard isRuntimeStarted else { return false }
        guard relayConfiguration != nil, developmentRelaySettings.endpointLabel == endpoint else { return false }
        guard canAttemptAutomaticRemoteRouteAllocation else { return false }
        guard !hasRouteAllocationWorkerInFlight else { return true }
        return requestAutomaticRemoteRelayRouteAllocation(
            restartRelayClientIfRunning: true,
            startRelayAfterCompletion: false,
            pairingRequest: shouldGenerateRemotePairingQRCodeWhenRelayReady
        )
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

    private func schedulePendingRemotePairingPreparation(endpoint: String) {
        shouldGenerateRemotePairingQRCodeWhenRelayReady = true
        let preparationID = UUID()
        pendingRemotePairingPreparationID = preparationID
        pendingRemotePairingEndpoint = endpoint
        refreshRemoteRoutePreparationInFlightState()
        remotePairingPreparationTimeoutTask?.cancel()
        let timeoutNanoseconds = pairingRoutePreparationTimeoutNanoseconds
        remotePairingPreparationTimeoutTask = Task { [weak self] in
            do {
                try await Task.sleep(nanoseconds: timeoutNanoseconds)
            } catch {
                return
            }
            guard !Task.isCancelled else { return }
            self?.failPendingRemotePairingPreparationIfCurrent(
                preparationID: preparationID
            )
        }
    }

    private func cancelPendingRemotePairingPreparation() {
        shouldGenerateRemotePairingQRCodeWhenRelayReady = false
        pendingRemotePairingPreparationID = nil
        pendingRemotePairingEndpoint = nil
        remotePairingPreparationTimeoutTask?.cancel()
        remotePairingPreparationTimeoutTask = nil
        refreshRemoteRoutePreparationInFlightState()
    }

    private func failPendingRemotePairingPreparationIfCurrent(
        preparationID: UUID
    ) {
        guard pendingRemotePairingPreparationID == preparationID,
              shouldGenerateRemotePairingQRCodeWhenRelayReady
        else {
            return
        }
        let endpoint = pendingRemotePairingEndpoint ?? "connection service"
        cancelPendingRemotePairingPreparation()
        invalidateRouteAllocationRequests(routeStateChanged: false)
        remoteRoutePreparationIssue = CompanionRemoteRoutePreparationIssue(
            kind: .relayConnectionFailed,
            endpoint: endpoint,
            message: "Connection preparation timed out."
        )
        log("Remote pairing QR not generated: connection preparation timed out for \(endpoint)")
    }

    private func refreshPendingRemotePairingRouteIfNeeded() {
        guard shouldGenerateRemotePairingQRCodeWhenRelayReady else { return }
        guard !isDevelopmentRelayRoutePreparedForQRCode else { return }
        guard !hasRouteAllocationWorkerInFlight else { return }
        let requested: Bool
        if canAttemptAutomaticRemoteRouteAllocation {
            requested = requestAutomaticRemoteRelayRouteAllocation(
                restartRelayClientIfRunning: true,
                startRelayAfterCompletion: false,
                pairingRequest: true
            )
        } else if relayConfiguration != nil,
                  isDevelopmentRelayRouteEligibleForQRCode,
                  shouldRefreshConfiguredRelayRouteLeaseForPairing {
            requested = requestConfiguredRelayRouteLeaseRefreshForUserInterface(pairingRequest: true)
        } else {
            requested = false
            publishRemotePairingUnavailability()
        }
        if !requested || remoteRoutePreparationIssue != nil {
            cancelPendingRemotePairingPreparation()
        }
    }

    private func generatePendingRemotePairingQRCodeIfReady() {
        guard shouldGenerateRemotePairingQRCodeWhenRelayReady else { return }
        guard shouldIncludeDevelopmentRelayInPairingQRCode else { return }
        cancelPendingRemotePairingPreparation()
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
        let logMessage = event.logMessage
        if let aggregate = backend as? AggregatingLlmBackend {
            modelResidency = CompanionModelResidencyStatus(
                snapshot: aggregate.modelResidencySnapshot(),
                lastEvent: logMessage ?? modelResidency.lastEvent
            )
        }
        if let logMessage {
            log(logMessage)
        }
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

    private var localDiagnosticPairingRouteHostCandidate: String? {
        guard allowsLocalDiagnosticPairingFromUserInterface,
              let host = runtimeRouteHostProvider()?.trimmingCharacters(in: .whitespacesAndNewlines),
              !host.isEmpty,
              Self.isUsablePairingAddress(host)
        else {
            return nil
        }
        return host
    }

    private var discoveryRouteToken: String

    private var runtimeAdvertisementMetadata: RuntimeAdvertisementMetadata {
        RuntimeAdvertisementMetadata(
            routeToken: discoveryRouteToken
        )
    }

    private static func loadedRelaySecretSource(
        environment: [String: String],
        settings: CompanionDevelopmentRelaySettings
    ) -> CompanionRelaySecretSource {
        guard let relaySecret = settings.relaySecret?.takeIfNotEmpty() else {
            return .none
        }
        if explicitEnvironmentRelaySecret(environment: environment, settings: settings) == relaySecret {
            return .environmentEphemeral
        }
        return .protectedStore
    }

    private static func explicitEnvironmentRelaySecret(
        environment: [String: String],
        settings: CompanionDevelopmentRelaySettings
    ) -> String? {
        guard settings.isEnvironmentOverride else { return nil }
        if environment["AETHERLINK_RELAY_HOST"]?.takeIfNotEmpty() != nil {
            return environment["AETHERLINK_RELAY_SECRET"]?.takeIfNotEmpty()
        }
        guard environment["AETHERLINK_BOOTSTRAP_RELAY_HOST"]?.takeIfNotEmpty() != nil else {
            return nil
        }
        return environment["AETHERLINK_BOOTSTRAP_RELAY_SECRET"]?.takeIfNotEmpty()
            ?? environment["AETHERLINK_BOOTSTRAP_RELAY_FRAME_SECRET"]?.takeIfNotEmpty()
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
    ) -> Bool {
        let previousSecretRef = defaults.string(forKey: RelayDefaults.secretRef)?.takeIfNotEmpty()
        let previousSecret = previousSecretRef.flatMap { relaySecretStore.readSecret(for: $0) }
        let committedSecretRef: String?
        if let relaySecret = settings.relaySecret?.takeIfNotEmpty() {
            let secretRef = relaySecretRef(deviceID: deviceID, relayID: settings.relayID)
            relaySecretStore.saveSecret(relaySecret, for: secretRef)
            guard relaySecretStore.readSecret(for: secretRef)?.takeIfNotEmpty() == relaySecret else {
                if secretRef == previousSecretRef, let previousSecret {
                    relaySecretStore.saveSecret(previousSecret, for: secretRef)
                } else {
                    relaySecretStore.removeSecret(for: secretRef)
                }
                return false
            }
            committedSecretRef = secretRef
        } else {
            committedSecretRef = nil
        }

        defaults.set(settings.host, forKey: RelayDefaults.host)
        defaults.set(Int(settings.port), forKey: RelayDefaults.port)
        defaults.set(settings.relayID, forKey: RelayDefaults.relayID)
        defaults.set(settings.allowsPrivateOverlay, forKey: RelayDefaults.allowsPrivateOverlay)
        if let committedSecretRef {
            defaults.set(committedSecretRef, forKey: RelayDefaults.secretRef)
            if let previousSecretRef, previousSecretRef != committedSecretRef {
                relaySecretStore.removeSecret(for: previousSecretRef)
            }
        } else {
            if let previousSecretRef {
                relaySecretStore.removeSecret(for: previousSecretRef)
            }
            defaults.removeObject(forKey: RelayDefaults.secretRef)
        }
        defaults.removeObject(forKey: RelayDefaults.secret)
        return true
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

    nonisolated static func resolveLocalDiagnosticPairingUIAllowance(
        requestedOverride: Bool?,
        isDebugAssertConfiguration: Bool
    ) -> Bool {
        guard isDebugAssertConfiguration else { return false }
        return requestedOverride ?? true
    }

    nonisolated private static func defaultRuntimeRouteHost() -> String? {
        var interfaces: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&interfaces) == 0, let firstInterface = interfaces else {
            return nil
        }
        defer { freeifaddrs(interfaces) }

        let primaryInterfaceName = primaryIPv4InterfaceName()
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
            guard let score = pairingInterfaceScore(
                name: interfaceName,
                primaryInterfaceName: primaryInterfaceName
            ) else {
                continue
            }
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

    nonisolated private static func primaryIPv4InterfaceName() -> String? {
        guard let state = SCDynamicStoreCopyValue(
            nil,
            "State:/Network/Global/IPv4" as CFString
        ) as? [String: Any] else {
            return nil
        }
        return state["PrimaryInterface"] as? String
    }

    nonisolated static func pairingInterfaceScore(
        name: String,
        primaryInterfaceName: String?
    ) -> Int? {
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
        if name == primaryInterfaceName {
            return 0
        }
        if name.hasPrefix("en") {
            return 10
        }
        return 20
    }

    nonisolated private static func isUsablePairingAddress(_ address: String) -> Bool {
        guard !address.isEmpty else { return false }
        if address == "0.0.0.0" || address == "255.255.255.255" { return false }
        if address.hasPrefix("127.") || address.hasPrefix("169.254.") { return false }
        return true
    }

    @Published public private(set) var runtimeChatCompactionCalibrationReport =
        RuntimeChatCompactionCalibrationReport()
    @Published public private(set) var runtimeChatCompactionCalibrationReportError: String?
    @Published public private(set) var isRuntimeChatCompactionCalibrationReportRefreshing = false

}

private func isRelayRouteLeaseFreshForPairingQRCode(_ lease: CompanionRemoteRouteLease) -> Bool {
    !lease.isExpired(renewalMarginSeconds: pairingQRCodeLeaseRenewalMarginSeconds)
}

extension CompanionAppModel: RuntimeRouteRefreshing {
    public func refreshRuntimeRoute() async throws -> RuntimeRouteRefreshResult? {
        if !hasCanonicalFreshRemoteRouteMaterialForQRCode {
            if !hasRouteAllocationWorkerInFlight {
                let requested: Bool
                if canAttemptAutomaticRemoteRouteAllocation {
                    requested = requestAutomaticRemoteRelayRouteAllocation(
                        restartRelayClientIfRunning: true,
                        startRelayAfterCompletion: false,
                        pairingRequest: false
                    )
                } else if relayConfiguration != nil,
                          isDevelopmentRelayRouteEligibleForQRCode,
                          shouldRefreshConfiguredRelayRouteLeaseForPairing {
                    requested = requestConfiguredRelayRouteLeaseRefreshForUserInterface(
                        pairingRequest: false
                    )
                } else {
                    requested = false
                }
                guard requested else { return nil }
            }
            while hasRouteAllocationWorkerInFlight {
                try Task.checkCancellation()
                try await Task.sleep(nanoseconds: 10_000_000)
            }
        }
        guard isDevelopmentRelayRouteEligibleForQRCode,
              hasCanonicalFreshRemoteRouteMaterialForQRCode,
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
        await reconcilePendingPairActivation(
            fingerprint: pendingActivation.clientKeyFingerprint
        )
    }

    public func refreshRuntimeChatCompactionCalibrationReport() async {
        guard !isRuntimeChatCompactionCalibrationReportRefreshing else { return }
        isRuntimeChatCompactionCalibrationReportRefreshing = true
        runtimeChatCompactionCalibrationReport = RuntimeChatCompactionCalibrationReport()
        runtimeChatCompactionCalibrationReportError = nil
        defer { isRuntimeChatCompactionCalibrationReportRefreshing = false }

        let store = runtimeChatEventStore
        do {
            runtimeChatCompactionCalibrationReport = try await Self.loadRuntimeChatCompactionCalibrationReport(
                from: store
            )
        } catch is CancellationError {
            runtimeChatCompactionCalibrationReport = RuntimeChatCompactionCalibrationReport()
        } catch {
            let message = error.localizedDescription
            runtimeChatCompactionCalibrationReport = RuntimeChatCompactionCalibrationReport()
            runtimeChatCompactionCalibrationReportError = message
            log("Runtime chat compaction calibration report failed: \(message)")
        }
    }

    nonisolated private static func loadRuntimeChatCompactionCalibrationReport(
        from store: any RuntimeChatEventStore
    ) async throws -> RuntimeChatCompactionCalibrationReport {
        try await withThrowingTaskGroup(of: RuntimeChatCompactionCalibrationReport.self) { group in
            group.addTask(priority: .utility) {
                try Task.checkCancellation()
                return try store.chatCompactionCalibrationReport()
            }
            guard let report = try await group.next() else {
                throw CancellationError()
            }
            group.cancelAll()
            return report
        }
    }
}

public struct CompanionModelResidencyStatus: Equatable, Sendable {
    public var activeProvider: ModelProvider?
    public var activeModelID: String?
    public var inFlightGenerations: Int
    public var idleUnloadDelaySeconds: Int
    public var unloadingProvider: ModelProvider?
    public var unloadingModelID: String?
    public var unloadingReason: RuntimeModelResidencyUnloadReason?
    public var lastUnloadFailure: RuntimeModelResidencyUnloadFailure?
    public var lastEvent: String?
    public var supported: Bool

    public static let inactive = CompanionModelResidencyStatus(
        activeProvider: nil,
        activeModelID: nil,
        inFlightGenerations: 0,
        idleUnloadDelaySeconds: 600,
        unloadingProvider: nil,
        unloadingModelID: nil,
        unloadingReason: nil,
        lastUnloadFailure: nil,
        lastEvent: nil,
        supported: true
    )

    public static let unsupported = CompanionModelResidencyStatus(
        activeProvider: nil,
        activeModelID: nil,
        inFlightGenerations: 0,
        idleUnloadDelaySeconds: 0,
        unloadingProvider: nil,
        unloadingModelID: nil,
        unloadingReason: nil,
        lastUnloadFailure: nil,
        lastEvent: nil,
        supported: false
    )

    public init(
        activeProvider: ModelProvider?,
        activeModelID: String?,
        inFlightGenerations: Int,
        idleUnloadDelaySeconds: Int,
        unloadingProvider: ModelProvider? = nil,
        unloadingModelID: String? = nil,
        unloadingReason: RuntimeModelResidencyUnloadReason? = nil,
        lastUnloadFailure: RuntimeModelResidencyUnloadFailure? = nil,
        lastEvent: String?,
        supported: Bool
    ) {
        self.activeProvider = activeProvider
        self.activeModelID = activeModelID
        self.inFlightGenerations = inFlightGenerations
        self.idleUnloadDelaySeconds = idleUnloadDelaySeconds
        self.unloadingProvider = unloadingProvider
        self.unloadingModelID = unloadingModelID
        self.unloadingReason = unloadingReason
        self.lastUnloadFailure = lastUnloadFailure
        self.lastEvent = lastEvent
        self.supported = supported
    }

    public init(snapshot: RuntimeModelResidencySnapshot, lastEvent: String?) {
        self.init(
            activeProvider: snapshot.activeProvider,
            activeModelID: snapshot.activeModelID,
            inFlightGenerations: snapshot.inFlightGenerations,
            idleUnloadDelaySeconds: snapshot.idleUnloadDelaySeconds,
            unloadingProvider: snapshot.unloadingProvider,
            unloadingModelID: snapshot.unloadingModelID,
            unloadingReason: snapshot.unloadingReason,
            lastUnloadFailure: snapshot.lastUnloadFailure,
            lastEvent: lastEvent,
            supported: true
        )
    }
}

private extension RuntimeModelResidencyEvent {
    var logMessage: String? {
        switch self {
        case .stateChanged:
            return nil
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
