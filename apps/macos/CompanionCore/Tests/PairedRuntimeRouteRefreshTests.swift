import BridgeProtocol
@testable import CompanionCore
import CryptoKit
import Foundation
import Pairing
import Transport
import XCTest

final class PairedRuntimeRouteRefreshTests: XCTestCase {
    @MainActor
    func testPairedRefreshRequiresContextAndNeverFallsBackToRuntimeOnlyAllocation() async throws {
        let fixture = try makeFixture(ticketGeneration: 1)
        let allocator = RecordingPairedRelayAllocator(
            renewalError: .clientAuthorizationRejected
        )
        let relayClient = RecordingRelayTransport()
        let model = fixture.makeModel(allocator: allocator, relayClient: relayClient)

        do {
            _ = try await model.refreshRuntimeRoute(authorizationContext: nil)
            XCTFail("Expected paired authorization to be required")
        } catch let error as RuntimeRouteRefreshAuthorizationError {
            XCTAssertEqual(error, .pairedAuthorizationRequired)
        }
        XCTAssertEqual(allocator.runtimeOnlyCallCount, 0)
        XCTAssertTrue(allocator.pairedCalls.isEmpty)

        do {
            _ = try await model.refreshRuntimeRoute(
                authorizationContext: try makeAuthorizationContext(requestID: "paired-refresh-1")
            )
            XCTFail("Expected paired allocation failure")
        } catch let error as RelayServiceRouteAllocationError {
            XCTAssertEqual(error, .clientAuthorizationRejected)
        }

        XCTAssertEqual(allocator.runtimeOnlyCallCount, 0)
        XCTAssertEqual(allocator.pairedCalls.count, 1)
        XCTAssertEqual(relayClient.stopCount, 0)
        XCTAssertEqual(fixture.savedTicketGeneration, 1)
        XCTAssertEqual(fixture.savedNonce, fixture.currentNonce)
    }

    @MainActor
    func testAcceptedPairedRefreshUsesCurrentAllocationAndPersistsNextGeneration() async throws {
        let fixture = try makeFixture(ticketGeneration: 7)
        let nextExpiry = fixture.currentExpiry + 60_000
        let authorizationContext = try makeAuthorizationContext(requestID: "paired-refresh-accepted")
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: fixture.routeToken,
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            clientKeyFingerprint: authorizationContext.trustedClientKeyFingerprint
        )
        let allocator = RecordingPairedRelayAllocator(renewalAllocation: RelayServiceRouteAllocation(
            host: fixture.host,
            port: fixture.port,
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: nextExpiry,
            relayNonce: "nonce-generation-8",
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            ticketGeneration: 8
        ))
        let relayClient = RecordingRelayTransport()
        let pairedRelayClient = RecordingRelayTransport()
        let model = fixture.makeModel(
            allocator: allocator,
            relayClient: relayClient,
            pairedRelayClient: pairedRelayClient
        )

        let refreshedResult = try await model.refreshRuntimeRoute(
            authorizationContext: authorizationContext
        )
        let refreshed = try XCTUnwrap(refreshedResult)

        let call = try XCTUnwrap(allocator.pairedCalls.first)
        XCTAssertEqual(allocator.runtimeOnlyCallCount, 0)
        XCTAssertEqual(call.currentRouteToken, fixture.routeToken)
        XCTAssertEqual(call.host, fixture.host)
        XCTAssertEqual(call.port, fixture.port)
        XCTAssertEqual(call.relayID, fixture.relayID)
        XCTAssertEqual(call.relaySecret, fixture.endpointSecret)
        XCTAssertEqual(call.relayNonce, fixture.currentNonce)
        XCTAssertEqual(call.currentLeaseGeneration, 7)
        XCTAssertEqual(call.currentLeaseExpiry, fixture.currentExpiry)
        XCTAssertEqual(call.runtimeIdentity, fixture.runtimeIdentity)
        XCTAssertEqual(call.authorizationRequestID, authorizationContext.requestID)
        XCTAssertEqual(call.authorizationConnectionID, authorizationContext.connectionID)
        XCTAssertEqual(call.allocationToken, fixture.allocationToken)
        XCTAssertEqual(call.timeout, 5)

        XCTAssertEqual(refreshed.relayHost, fixture.host)
        XCTAssertEqual(refreshed.relayPort, Int(fixture.port))
        XCTAssertEqual(refreshed.relayID, pairedRelayID)
        XCTAssertEqual(refreshed.relaySecret, fixture.endpointSecret)
        XCTAssertEqual(refreshed.relayExpiresAtEpochMillis, nextExpiry)
        XCTAssertEqual(refreshed.relayNonce, "nonce-generation-8")
        XCTAssertEqual(refreshed.relayTicketGeneration, 8)
        XCTAssertEqual(relayClient.stopCount, 0)
        XCTAssertEqual(fixture.savedTicketGeneration, 7)
        XCTAssertEqual(fixture.savedExpiry, fixture.currentExpiry)
        XCTAssertEqual(fixture.savedNonce, fixture.currentNonce)
        XCTAssertEqual(fixture.savedHost, fixture.host)
        XCTAssertEqual(fixture.savedPort, Int(fixture.port))
        XCTAssertEqual(fixture.savedRelayID, fixture.relayID)
        XCTAssertEqual(fixture.savedEndpointSecret, fixture.endpointSecret)
        let storedPairRoute = try XCTUnwrap(
            PairScopedRelayRouteStore(
                userDefaults: fixture.defaults,
                relaySecretStore: fixture.secretStore
            ).loadAll().first
        )
        XCTAssertEqual(storedPairRoute.clientKeyFingerprint, authorizationContext.trustedClientKeyFingerprint)
        XCTAssertEqual(storedPairRoute.routeToken, fixture.routeToken)
        XCTAssertEqual(storedPairRoute.relayID, pairedRelayID)
        XCTAssertEqual(storedPairRoute.ticketGeneration, 8)
        XCTAssertEqual(storedPairRoute.relayNonce, "nonce-generation-8")
        XCTAssertEqual(storedPairRoute.relaySecret, fixture.endpointSecret)

        await model.activateRuntimeRouteRefresh(refreshed)
        XCTAssertEqual(relayClient.stopCount, 1)
        XCTAssertEqual(pairedRelayClient.startedConfigurations.count, 1)
        XCTAssertEqual(pairedRelayClient.startedConfigurations.first?.relayID, pairedRelayID)
        XCTAssertNotEqual(
            fixture.defaults.string(forKey: "aetherlink.discovery_route_token"),
            fixture.routeToken
        )
        XCTAssertNil(fixture.savedTicketGeneration)
    }

    @MainActor
    func testFinalAllocationMismatchRollsBackWithoutRestartOrFallback() async throws {
        let fixture = try makeFixture(ticketGeneration: 3)
        let allocator = RecordingPairedRelayAllocator(renewalAllocation: RelayServiceRouteAllocation(
            host: "different-relay.example.test",
            port: fixture.port,
            relayID: fixture.relayID,
            relayExpiresAtEpochMillis: fixture.currentExpiry + 60_000,
            relayNonce: "nonce-generation-4",
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            ticketGeneration: 4
        ))
        let relayClient = RecordingRelayTransport()
        let model = fixture.makeModel(allocator: allocator, relayClient: relayClient)

        do {
            _ = try await model.refreshRuntimeRoute(
                authorizationContext: try makeAuthorizationContext(requestID: "paired-refresh-mismatch")
            )
            XCTFail("Expected final allocation mismatch")
        } catch let error as RelayServiceRouteAllocationError {
            XCTAssertEqual(error, .invalidResponse)
        }

        XCTAssertEqual(allocator.runtimeOnlyCallCount, 0)
        XCTAssertEqual(allocator.pairedCalls.count, 1)
        XCTAssertEqual(relayClient.stopCount, 0)
        XCTAssertEqual(fixture.savedTicketGeneration, 3)
        XCTAssertEqual(fixture.savedExpiry, fixture.currentExpiry)
        XCTAssertEqual(fixture.savedNonce, fixture.currentNonce)
        XCTAssertEqual(fixture.savedHost, fixture.host)
        XCTAssertEqual(fixture.savedRelayID, fixture.relayID)
        XCTAssertEqual(fixture.savedEndpointSecret, fixture.endpointSecret)
    }

    @MainActor
    func testStaticDiagnosticRouteWithoutTicketGenerationCannotUsePairedRefresh() async throws {
        let fixture = try makeFixture(
            ticketGeneration: nil,
            relayIDOverride: "diagnostic-static-route"
        )
        let allocator = RecordingPairedRelayAllocator(renewalError: .pairedRenewalUnavailable)
        let relayClient = RecordingRelayTransport()
        let model = fixture.makeModel(allocator: allocator, relayClient: relayClient)

        do {
            _ = try await model.refreshRuntimeRoute(
                authorizationContext: try makeAuthorizationContext(requestID: "paired-refresh-static")
            )
            XCTFail("Expected static route rejection")
        } catch let error as RelayServiceRouteAllocationError {
            XCTAssertEqual(error, .invalidPairedRenewalRequest)
        }

        XCTAssertEqual(allocator.runtimeOnlyCallCount, 0)
        XCTAssertTrue(allocator.pairedCalls.isEmpty)
        XCTAssertEqual(relayClient.stopCount, 0)
        XCTAssertNil(fixture.savedTicketGeneration)
        XCTAssertEqual(fixture.savedNonce, fixture.currentNonce)
    }
}

private struct PairedRouteFixture {
    let defaults: UserDefaults
    let secretStore: InMemoryRelaySecretStore
    let environment: [String: String]
    let routeToken: String
    let runtimeIdentity: RelayRuntimeIdentity
    let host: String
    let port: UInt16
    let relayID: String
    let endpointSecret: String
    let currentExpiry: Int64
    let currentNonce: String
    let allocationToken: String

    @MainActor
    func makeModel(
        allocator: any RelayServiceRouteAllocating,
        relayClient: any RelayPeerTransport,
        pairedRelayClient: (any RelayPeerTransport)? = nil
    ) -> CompanionAppModel {
        CompanionAppModel(
            relayClient: relayClient,
            pairedRelayClientFactory: {
                pairedRelayClient ?? RecordingRelayTransport()
            },
            relayServiceRouteAllocator: allocator,
            environment: environment,
            userDefaults: defaults,
            relaySecretStore: secretStore
        )
    }

    var savedTicketGeneration: Int64? {
        let value = Int64(defaults.integer(forKey: "aetherlink.relay.lease_ticket_generation"))
        return value > 0 ? value : nil
    }

    var savedExpiry: Int64 {
        Int64(defaults.integer(forKey: "aetherlink.relay.lease_expires_at"))
    }

    var savedNonce: String? {
        defaults.string(forKey: "aetherlink.relay.lease_nonce")
    }

    var savedHost: String? {
        defaults.string(forKey: "aetherlink.relay.lease_host")
    }

    var savedPort: Int {
        defaults.integer(forKey: "aetherlink.relay.lease_port")
    }

    var savedRelayID: String? {
        defaults.string(forKey: "aetherlink.relay.lease_id")
    }

    var savedEndpointSecret: String? {
        guard let secretRef = defaults.string(forKey: "aetherlink.relay.secret_ref") else {
            return nil
        }
        return secretStore.readSecret(for: secretRef)
    }
}

@MainActor
private func makeFixture(
    ticketGeneration: Int64?,
    relayIDOverride: String? = nil
) throws -> PairedRouteFixture {
    let defaults = try isolatedRouteRefreshDefaults()
    let identityURL = FileManager.default.temporaryDirectory
        .appendingPathComponent("aetherlink-paired-route-tests", isDirectory: true)
        .appendingPathComponent(UUID().uuidString, isDirectory: true)
        .appendingPathComponent("runtime-identity.json", isDirectory: false)
    let identityStore = FileRuntimeIdentityKeyStore(fileURL: identityURL)
    _ = try identityStore.loadOrCreate()
    let runtimeIdentity = try identityStore.relayRuntimeIdentity()
    let routeToken = "paired-runtime-route-token"
    let relayID = relayIDOverride ?? RelayAllocationIdentityChallenge.relayID(
        routeToken: routeToken,
        runtimeKeyFingerprint: runtimeIdentity.fingerprint
    )
    let host = "relay.example.test"
    let port: UInt16 = 443
    let endpointSecret = "endpoint-owned-secret"
    let currentExpiry: Int64 = 4_102_444_800_000
    let currentNonce = "nonce-current-generation"
    let allocationToken = "paired-allocation-token"
    let deviceID = "paired-runtime-device"
    let secretRef = "test-secret-ref"
    let secretStore = InMemoryRelaySecretStore()
    secretStore.saveSecret(endpointSecret, for: secretRef)

    defaults.set(deviceID, forKey: "aetherlink.mac_device_id")
    defaults.set(routeToken, forKey: "aetherlink.discovery_route_token")
    defaults.set(host, forKey: "aetherlink.relay.host")
    defaults.set(Int(port), forKey: "aetherlink.relay.port")
    defaults.set(relayID, forKey: "aetherlink.relay.id")
    defaults.set(secretRef, forKey: "aetherlink.relay.secret_ref")
    defaults.set(Int(currentExpiry), forKey: "aetherlink.relay.lease_expires_at")
    defaults.set(currentNonce, forKey: "aetherlink.relay.lease_nonce")
    defaults.set(host, forKey: "aetherlink.relay.lease_host")
    defaults.set(Int(port), forKey: "aetherlink.relay.lease_port")
    defaults.set(relayID, forKey: "aetherlink.relay.lease_id")
    if let ticketGeneration {
        defaults.set(Int(ticketGeneration), forKey: "aetherlink.relay.lease_ticket_generation")
    }

    return PairedRouteFixture(
        defaults: defaults,
        secretStore: secretStore,
        environment: [
            "AETHERLINK_RUNTIME_IDENTITY_FILE": identityURL.path,
            "AETHERLINK_RELAY_ALLOCATION_TOKEN": allocationToken,
        ],
        routeToken: routeToken,
        runtimeIdentity: runtimeIdentity,
        host: host,
        port: port,
        relayID: relayID,
        endpointSecret: endpointSecret,
        currentExpiry: currentExpiry,
        currentNonce: currentNonce,
        allocationToken: allocationToken
    )
}

private func makeAuthorizationContext(
    requestID: String
) throws -> RuntimePairedRelayAuthorizationContext {
    let privateKey = P256.Signing.PrivateKey()
    let publicKeyData = privateKey.publicKey.derRepresentation
    let publicKeyBase64 = publicKeyData.base64EncodedString()
    let fingerprint = SHA256.hash(data: publicKeyData)
        .map { String(format: "%02x", $0) }
        .joined()
    return try RuntimePairedRelayAuthorizationContext(
        requestID: requestID,
        connectionID: UUID(),
        trustedClientPublicKeyBase64: publicKeyBase64,
        trustedClientKeyFingerprint: fingerprint,
        transportBinding: String(repeating: "a", count: 64),
        clientAuthorizationProvider: { _ in
            throw PairedRouteTestError.unexpectedClientAuthorization
        }
    )
}

private func isolatedRouteRefreshDefaults() throws -> UserDefaults {
    let suiteName = "PairedRuntimeRouteRefreshTests.\(UUID().uuidString)"
    guard let defaults = UserDefaults(suiteName: suiteName) else {
        throw PairedRouteTestError.defaultsUnavailable
    }
    defaults.removePersistentDomain(forName: suiteName)
    return defaults
}

private enum PairedRouteTestError: Error {
    case defaultsUnavailable
    case unexpectedClientAuthorization
}

private final class RecordingPairedRelayAllocator: RelayServiceRouteAllocating, @unchecked Sendable {
    struct PairedCall: Equatable {
        let currentRouteToken: String
        let host: String
        let port: UInt16
        let relayID: String
        let relaySecret: String?
        let relayNonce: String?
        let currentLeaseGeneration: Int64?
        let currentLeaseExpiry: Int64
        let runtimeIdentity: RelayRuntimeIdentity
        let authorizationRequestID: String
        let authorizationConnectionID: UUID
        let allocationToken: String?
        let timeout: TimeInterval
    }

    private let lock = NSLock()
    private let renewalAllocation: RelayServiceRouteAllocation?
    private let renewalError: RelayServiceRouteAllocationError?
    private var storedRuntimeOnlyCallCount = 0
    private var storedPairedCalls: [PairedCall] = []

    init(
        renewalAllocation: RelayServiceRouteAllocation? = nil,
        renewalError: RelayServiceRouteAllocationError? = nil
    ) {
        self.renewalAllocation = renewalAllocation
        self.renewalError = renewalError
    }

    var runtimeOnlyCallCount: Int {
        lock.withLock { storedRuntimeOnlyCallCount }
    }

    var pairedCalls: [PairedCall] {
        lock.withLock { storedPairedCalls }
    }

    func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        allocationToken: String?,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        timeout: TimeInterval
    ) throws -> RelayServiceRouteAllocation {
        lock.withLock {
            storedRuntimeOnlyCallCount += 1
        }
        throw RelayServiceRouteAllocationError.pairedRenewalUnavailable
    }

    func renewPairedRelayRoute(
        currentRouteToken: String,
        currentConfiguration: RelayPeerConfiguration,
        currentLease: CompanionRemoteRouteLease,
        runtimeIdentity: RelayRuntimeIdentity,
        authorizationSigner: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning,
        authorizationContext: RuntimePairedRelayAuthorizationContext,
        allocationToken: String?,
        timeout: TimeInterval
    ) async throws -> RelayServiceRouteAllocation {
        lock.withLock {
            storedPairedCalls.append(PairedCall(
                currentRouteToken: currentRouteToken,
                host: currentConfiguration.host,
                port: currentConfiguration.port,
                relayID: currentConfiguration.relayID,
                relaySecret: currentConfiguration.relaySecret,
                relayNonce: currentConfiguration.relayNonce,
                currentLeaseGeneration: currentLease.ticketGeneration,
                currentLeaseExpiry: currentLease.expiresAtEpochMillis,
                runtimeIdentity: runtimeIdentity,
                authorizationRequestID: authorizationContext.requestID,
                authorizationConnectionID: authorizationContext.connectionID,
                allocationToken: allocationToken,
                timeout: timeout
            ))
        }
        if let renewalError {
            throw renewalError
        }
        guard let renewalAllocation else {
            throw RelayServiceRouteAllocationError.pairedRenewalUnavailable
        }
        return renewalAllocation
    }
}

private final class RecordingRelayTransport: RelayPeerTransport, @unchecked Sendable {
    private let lock = NSLock()
    private var storedStopCount = 0
    private var storedStartedConfigurations: [RelayPeerConfiguration] = []

    var stopCount: Int {
        lock.withLock { storedStopCount }
    }

    var startedConfigurations: [RelayPeerConfiguration] {
        lock.withLock { storedStartedConfigurations }
    }

    func start(
        configuration: RelayPeerConfiguration,
        onStatusChange: (@Sendable (RelayPeerStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        lock.withLock {
            storedStartedConfigurations.append(configuration)
        }
    }

    func stop() {
        lock.withLock {
            storedStopCount += 1
        }
    }
}

private final class InMemoryRelaySecretStore: CompanionRelaySecretStoring, @unchecked Sendable {
    private let lock = NSLock()
    private var secrets: [String: String] = [:]

    func saveSecret(_ secret: String, for handle: String) {
        lock.withLock {
            secrets[handle] = secret
        }
    }

    func readSecret(for handle: String) -> String? {
        lock.withLock { secrets[handle] }
    }

    func removeSecret(for handle: String) {
        _ = lock.withLock {
            secrets.removeValue(forKey: handle)
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
