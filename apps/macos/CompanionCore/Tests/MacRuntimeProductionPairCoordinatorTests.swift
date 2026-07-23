import BridgeProtocol
@testable import CompanionCore
import CryptoKit
import Foundation
import P2PNATContracts
import Transport
@testable import TrustedDevices
import XCTest

final class MacRuntimeProductionPairCoordinatorTests: XCTestCase {
    @MainActor
    func testAdmissionOccursExactlyOnceBeforeFactoryAndStart() async throws {
        let fixture = try await makeCoordinatorFixture(sessionDigit: "d")
        let events = CoordinatorEventRecorder()
        let relay = CoordinatorRelayTransport(onStart: { events.record("start") })
        let authorizer = CoordinatorImmediateAuthorizer(
            permit: fixture.permit,
            events: events
        )
        let coordinator = makeCoordinator(
            authorizer: authorizer,
            relay: relay,
            events: events
        )

        try await coordinator.startRelay(plan: fixture.plan, onMessage: { _, _ in })

        let attemptCount = await authorizer.attemptCount
        XCTAssertEqual(attemptCount, 1)
        XCTAssertEqual(events.events, ["admit", "factory", "start"])
        XCTAssertEqual(relay.startCount, 1)
        guard case .active(_, let sessionID, let transcriptDigest) = coordinator.state(
            fingerprint: fixture.plan.clientKeyFingerprint
        ) else {
            return XCTFail("Expected an active exact-bound production generation")
        }
        XCTAssertEqual(sessionID, fixture.plan.sessionID)
        XCTAssertEqual(transcriptDigest, fixture.plan.transcriptDigest)
    }

    @MainActor
    func testAdmissionFailureBlocksWithoutFactoryOrStart() async throws {
        let fixture = try await makeCoordinatorFixture(sessionDigit: "d")
        let events = CoordinatorEventRecorder()
        let relay = CoordinatorRelayTransport(onStart: { events.record("start") })
        let authorizer = CoordinatorImmediateAuthorizer(
            permit: fixture.permit,
            failure: .denied,
            events: events
        )
        let coordinator = makeCoordinator(
            authorizer: authorizer,
            relay: relay,
            events: events
        )

        do {
            try await coordinator.startRelay(plan: fixture.plan, onMessage: { _, _ in })
            XCTFail("Expected admission denial")
        } catch {
            XCTAssertEqual(error as? CoordinatorAuthorizerError, .denied)
        }

        XCTAssertEqual(events.events, ["admit"])
        XCTAssertEqual(relay.startCount, 0)
        guard case .blocked = coordinator.state(fingerprint: fixture.plan.clientKeyFingerprint) else {
            return XCTFail("Expected denial to leave a blocked generation")
        }
    }

    @MainActor
    func testCancellationAfterDurableAdmissionBlocksBeforeFactory() async throws {
        let fixture = try await makeCoordinatorFixture(sessionDigit: "d")
        let events = CoordinatorEventRecorder()
        let relay = CoordinatorRelayTransport(onStart: { events.record("start") })
        let authorizer = CoordinatorImmediateAuthorizer(
            permit: fixture.permit,
            cancelsAfterAdmission: true,
            events: events
        )
        let coordinator = makeCoordinator(
            authorizer: authorizer,
            relay: relay,
            events: events
        )
        let task = Task { @MainActor in
            try await coordinator.startRelay(plan: fixture.plan, onMessage: { _, _ in })
        }

        do {
            try await task.value
            XCTFail("Expected post-admission cancellation")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }

        XCTAssertEqual(events.events, ["admit"])
        XCTAssertEqual(relay.startCount, 0)
        guard case .blocked = coordinator.state(fingerprint: fixture.plan.clientKeyFingerprint) else {
            return XCTFail("Expected cancellation to leave a blocked generation")
        }
    }

    @MainActor
    func testRevokeDuringAdmissionPreventsLateStart() async throws {
        let fixture = try await makeCoordinatorFixture(sessionDigit: "d")
        let events = CoordinatorEventRecorder()
        let relay = CoordinatorRelayTransport(onStart: { events.record("start") })
        let authorizer = CoordinatorSuspendedAuthorizer(events: events)
        let coordinator = makeCoordinator(
            authorizer: authorizer,
            relay: relay,
            events: events
        )
        let task = Task { @MainActor in
            try await coordinator.startRelay(plan: fixture.plan, onMessage: { _, _ in })
        }
        await authorizer.waitUntilStarted()

        coordinator.revokePair(fingerprint: fixture.plan.clientKeyFingerprint)
        await authorizer.succeed(with: fixture.permit)

        do {
            try await task.value
            XCTFail("Expected the revoked pending generation to stay inert")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }
        XCTAssertEqual(events.events, ["admit"])
        XCTAssertEqual(relay.startCount, 0)
        guard case .blocked = coordinator.state(fingerprint: fixture.plan.clientKeyFingerprint) else {
            return XCTFail("Expected revoke to retain a blocked generation")
        }
    }

    @MainActor
    func testAuthorityAdvanceStopsActiveTransportAndInvalidatesMessageCallback() async throws {
        let fixture = try await makeCoordinatorFixture(sessionDigit: "d")
        let relay = CoordinatorRelayTransport()
        let authorizer = CoordinatorImmediateAuthorizer(permit: fixture.permit)
        let coordinator = makeCoordinator(authorizer: authorizer, relay: relay)
        let messages = CoordinatorEventRecorder()
        let sink = CoordinatorMessageSink()

        try await coordinator.startRelay(
            plan: fixture.plan,
            onMessage: { envelope, _ in messages.record(envelope.type) }
        )
        relay.emitMessage(type: "current", sink: sink)
        coordinator.authorityDidAdvance(fingerprint: fixture.plan.clientKeyFingerprint)
        relay.emitMessage(type: "stale", sink: sink)

        XCTAssertEqual(messages.events, ["current"])
        XCTAssertEqual(relay.stopCount, 1)
        guard case .blocked = coordinator.state(fingerprint: fixture.plan.clientKeyFingerprint) else {
            return XCTFail("Expected authority advance to block the old generation")
        }
    }

    @MainActor
    func testStopAllDuringAdmissionPreventsLateStart() async throws {
        let fixture = try await makeCoordinatorFixture(sessionDigit: "d")
        let relay = CoordinatorRelayTransport()
        let authorizer = CoordinatorSuspendedAuthorizer()
        let coordinator = makeCoordinator(authorizer: authorizer, relay: relay)
        let task = Task { @MainActor in
            try await coordinator.startRelay(plan: fixture.plan, onMessage: { _, _ in })
        }
        await authorizer.waitUntilStarted()

        coordinator.stopAll()
        await authorizer.succeed(with: fixture.permit)

        do {
            try await task.value
            XCTFail("Expected stopped runtime generation to stay inert")
        } catch {
            XCTAssertTrue(error is CancellationError)
        }
        XCTAssertEqual(relay.startCount, 0)
    }

    @MainActor
    private func makeCoordinator(
        authorizer: any MacRuntimeProductionPairAuthorizing,
        relay: CoordinatorRelayTransport,
        events: CoordinatorEventRecorder? = nil
    ) -> MacRuntimeProductionPairCoordinator {
        let manager = MacRuntimeConnectionManager(
            localTransport: CoordinatorRuntimeTransport(),
            advertiser: CoordinatorAdvertiser(),
            bootstrapTransport: CoordinatorRelayTransport(),
            pairTransportFactory: {
                events?.record("factory")
                return relay
            },
            onDisconnect: { _ in }
        )
        return MacRuntimeProductionPairCoordinator(
            authorizer: authorizer,
            connectionManager: manager
        )
    }
}

private struct CoordinatorFixture {
    let plan: MacRuntimeVerifiedProductionRelayStartPlan
    let permit: ProductionPairAdmissionPermit
}

private func makeCoordinatorFixture(sessionDigit: Character) async throws -> CoordinatorFixture {
    let pairBindingDigest = String(repeating: "1", count: 64)
    let clientFingerprint = String(repeating: "2", count: 64)
    let runtimeFingerprint = String(repeating: "3", count: 64)
    let routeAuthorization = ProductionRouteAuthorization.turnRelay(
        pairBindingDigest: pairBindingDigest,
        pairEpoch: 2,
        generation: 7,
        leaseDigest: String(repeating: "a", count: 64),
        allocationDigest: String(repeating: "b", count: 64),
        pathValidationReceiptDigest: String(repeating: "c", count: 64)
    )
    let clientKey = P256.KeyAgreement.PrivateKey()
    let runtimeKey = P256.KeyAgreement.PrivateKey()
    let transcript = try ProductionSecureSessionTranscript(
        sessionId: String(repeating: sessionDigit, count: 32),
        pairBindingDigest: pairBindingDigest,
        pairEpoch: 2,
        clientIdentityFingerprint: clientFingerprint,
        runtimeIdentityFingerprint: runtimeFingerprint,
        clientEphemeralPublicKey: clientKey.publicKey.x963Representation,
        runtimeEphemeralPublicKey: runtimeKey.publicKey.x963Representation,
        clientNonce: String(repeating: "e", count: 32),
        runtimeNonce: String(repeating: "f", count: 32),
        generation: 7,
        serviceConfigVersion: 4,
        keysetVersion: 5,
        revocationCounter: 0,
        routeKind: routeAuthorization.kind,
        routeAuthDigest: try routeAuthorization.digestHex()
    )
    let attempt = MacRuntimeProductionPairConnectorAttempt(
        deviceID: "production-device",
        expectedPublicKeyBase64: "production-public-key",
        transcript: transcript,
        routeAuthorization: routeAuthorization
    )
    let authority = try ProductionPairAuthorityState(
        pairBindingDigest: pairBindingDigest,
        pairEpoch: 2,
        clientIdentityFingerprint: clientFingerprint,
        runtimeIdentityFingerprint: runtimeFingerprint,
        generation: 7,
        serviceConfigVersion: 4,
        keysetVersion: 5,
        revocationCounter: 0,
        protocolFloor: 1,
        status: .active,
        transitionId: String(repeating: "4", count: 64),
        transitionRequestDigest: String(repeating: "5", count: 64),
        acceptedReceiptDigest: String(repeating: "6", count: 64),
        authorityRevision: 1
    )
    let fileURL = FileManager.default.temporaryDirectory
        .appendingPathComponent("aetherlink-coordinator-permit-tests", isDirectory: true)
        .appendingPathComponent(UUID().uuidString, isDirectory: true)
        .appendingPathComponent("trusted-devices.json")
    let device = TrustedDevice(
        id: attempt.deviceID,
        name: "Coordinator fixture",
        publicKeyBase64: attempt.expectedPublicKeyBase64
    )
    let store = TrustedDeviceStore(fileURL: fileURL)
    try await store.trust(device)
    try await store.applyVerifiedProductionPairTransition(
        deviceID: device.id,
        expectedPublicKeyBase64: device.publicKeyBase64,
        transition: ProductionPairStateTransition(
            expectedPreviousAuthorityDigest: nil,
            nextAuthority: authority
        )
    )
    let permit = try await store.admitProductionSecureSession(
        deviceID: device.id,
        expectedPublicKeyBase64: device.publicKeyBase64,
        transcript: transcript,
        routeAuthorization: routeAuthorization
    )
    let plan = try MacRuntimeVerifiedProductionRelayStartPlan.testing(
        attempt: attempt,
        configuration: RelayPeerConfiguration(
            host: "relay.example.test",
            port: 443,
            relayID: "production-relay",
            relaySecret: "production-secret",
            relayNonce: "production-nonce"
        )
    )
    return CoordinatorFixture(plan: plan, permit: permit)
}

private enum CoordinatorAuthorizerError: Error, Equatable {
    case denied
}

private actor CoordinatorImmediateAuthorizer: MacRuntimeProductionPairAuthorizing {
    private let permit: ProductionPairAdmissionPermit
    private let failure: CoordinatorAuthorizerError?
    private let cancelsAfterAdmission: Bool
    private let events: CoordinatorEventRecorder?
    private(set) var attemptCount = 0

    init(
        permit: ProductionPairAdmissionPermit,
        failure: CoordinatorAuthorizerError? = nil,
        cancelsAfterAdmission: Bool = false,
        events: CoordinatorEventRecorder? = nil
    ) {
        self.permit = permit
        self.failure = failure
        self.cancelsAfterAdmission = cancelsAfterAdmission
        self.events = events
    }

    func authorizeProductionPairConnector(
        _ attempt: MacRuntimeProductionPairConnectorAttempt
    ) async throws -> ProductionPairAdmissionPermit {
        attemptCount += 1
        events?.record("admit")
        if let failure { throw failure }
        if cancelsAfterAdmission {
            withUnsafeCurrentTask { $0?.cancel() }
        }
        return permit
    }
}

private actor CoordinatorSuspendedAuthorizer: MacRuntimeProductionPairAuthorizing {
    private let events: CoordinatorEventRecorder?
    private var didStart = false
    private var startWaiters: [CheckedContinuation<Void, Never>] = []
    private var admissionContinuation: CheckedContinuation<ProductionPairAdmissionPermit, Error>?

    init(events: CoordinatorEventRecorder? = nil) {
        self.events = events
    }

    func authorizeProductionPairConnector(
        _ attempt: MacRuntimeProductionPairConnectorAttempt
    ) async throws -> ProductionPairAdmissionPermit {
        didStart = true
        events?.record("admit")
        startWaiters.forEach { $0.resume() }
        startWaiters.removeAll()
        return try await withCheckedThrowingContinuation { continuation in
            admissionContinuation = continuation
        }
    }

    func waitUntilStarted() async {
        if didStart { return }
        await withCheckedContinuation { startWaiters.append($0) }
    }

    func succeed(with permit: ProductionPairAdmissionPermit) {
        admissionContinuation?.resume(returning: permit)
        admissionContinuation = nil
    }
}

private final class CoordinatorEventRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var storedEvents: [String] = []

    var events: [String] { lock.withLock { storedEvents } }

    func record(_ event: String) {
        lock.withLock { storedEvents.append(event) }
    }
}

private final class CoordinatorRuntimeTransport: RuntimeTransport, @unchecked Sendable {
    var status: PeerServerStatus = .stopped
    func start(port: UInt16, onMessage: @escaping LocalPeerMessageHandler) {}
    func stop() {}
}

private final class CoordinatorAdvertiser: RuntimeAdvertiser, @unchecked Sendable {
    func start(port: Int32, metadata: RuntimeAdvertisementMetadata) {}
    func stop() {}
}

private final class CoordinatorRelayTransport:
    RelayPeerTransport,
    RuntimeDisconnectReporting,
    @unchecked Sendable
{
    private let lock = NSLock()
    private let onStart: (@Sendable () -> Void)?
    private var storedStartCount = 0
    private var storedStopCount = 0
    private var messageHandler: LocalPeerMessageHandler?
    var onDisconnect: (@Sendable (UUID) -> Void)?

    init(onStart: (@Sendable () -> Void)? = nil) {
        self.onStart = onStart
    }

    var startCount: Int { lock.withLock { storedStartCount } }
    var stopCount: Int { lock.withLock { storedStopCount } }

    func start(
        configuration: RelayPeerConfiguration,
        onStatusChange: (@Sendable (RelayPeerStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        lock.withLock {
            storedStartCount += 1
            messageHandler = onMessage
        }
        onStart?()
    }

    func stop() {
        lock.withLock { storedStopCount += 1 }
    }

    func emitMessage(type: String, sink: any RuntimeMessageSink) {
        let handler = lock.withLock { messageHandler }
        handler?(ProtocolEnvelope(type: type, requestID: type), sink)
    }
}

private final class CoordinatorMessageSink: RuntimeMessageSink, @unchecked Sendable {
    let connectionID = UUID()
    func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result {
        try operation(nil)
    }
    func send(_ envelope: ProtocolEnvelope) {}
    func close() {}
}
