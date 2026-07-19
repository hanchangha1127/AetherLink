import BridgeProtocol
@testable import CompanionCore
import CryptoKit
import Foundation
import Pairing
import Transport
import TrustedDevices
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
        let lifecycle = RelayLifecycleRecorder()
        let relayClient = RecordingRelayTransport(
            onStop: { lifecycle.record("bootstrap-retire") }
        )
        let pairedRelayClient = RecordingRelayTransport(
            onStart: { lifecycle.record("pair-start") }
        )
        let pairedPrivateOverlay = RecordingPrivateOverlayTransport(
            onStart: { lifecycle.record("overlay-start") }
        )
        let model = fixture.makeModel(
            allocator: allocator,
            relayClient: relayClient,
            pairedRelayClient: pairedRelayClient,
            pairedPrivateOverlayTransport: pairedPrivateOverlay
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

        let configurationRequest = model.requestConfigureDevelopmentRelayForUserInterface(
            host: fixture.host,
            port: fixture.port,
            relaySecret: fixture.endpointSecret,
            attemptAllocation: true
        )
        guard case .started(let configurationRequestID) = configurationRequest else {
            return XCTFail("Expected asynchronous relay configuration to start")
        }
        let didCompleteConfigurationRequest = await waitForRelayConfigurationCompletion(
            on: model,
            requestID: configurationRequestID
        )
        XCTAssertTrue(didCompleteConfigurationRequest)
        XCTAssertEqual(
            model.relayConfigurationRequestCompletion?.requestID,
            configurationRequestID
        )

        await model.activateRuntimeRouteRefresh(refreshed)
        XCTAssertEqual(relayClient.stopCount, 1)
        XCTAssertEqual(pairedRelayClient.startedConfigurations.count, 1)
        XCTAssertEqual(pairedRelayClient.startedConfigurations.first?.relayID, pairedRelayID)
        XCTAssertEqual(pairedPrivateOverlay.startedFingerprints, [
            authorizationContext.trustedClientKeyFingerprint,
        ])
        XCTAssertEqual(lifecycle.events, ["overlay-start", "pair-start", "bootstrap-retire"])
        XCTAssertNotEqual(
            fixture.defaults.string(forKey: "aetherlink.discovery_route_token"),
            fixture.routeToken
        )
        XCTAssertNil(fixture.savedTicketGeneration)
        XCTAssertNil(model.relayConfigurationRequestState)
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

    @MainActor
    func testRestoredPairScopedRouteStartsPrivateOverlayBeforeRelayAndStopsBoth() async throws {
        let fixture = try makeFixture(ticketGeneration: 11)
        let authorizationContext = try makeAuthorizationContext(requestID: "paired-refresh-restore")
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: fixture.routeToken,
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            clientKeyFingerprint: authorizationContext.trustedClientKeyFingerprint
        )
        let allocator = RecordingPairedRelayAllocator(renewalAllocation: RelayServiceRouteAllocation(
            host: fixture.host,
            port: fixture.port,
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: fixture.currentExpiry + 60_000,
            relayNonce: "nonce-generation-12",
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            ticketGeneration: 12
        ))
        let initialModel = fixture.makeModel(
            allocator: allocator,
            relayClient: RecordingRelayTransport()
        )

        _ = try await initialModel.refreshRuntimeRoute(authorizationContext: authorizationContext)

        let lifecycle = RelayLifecycleRecorder()
        let pairedRelay = RecordingRelayTransport(onStart: { lifecycle.record("pair-start") })
        let privateOverlay = RecordingPrivateOverlayTransport(
            onStart: { lifecycle.record("overlay-start") }
        )
        let restoredModel = fixture.makeModel(
            allocator: RecordingPairedRelayAllocator(),
            relayClient: RecordingRelayTransport(),
            pairedRelayClient: pairedRelay,
            pairedPrivateOverlayTransport: privateOverlay
        )

        restoredModel.start(port: 43213)

        XCTAssertEqual(privateOverlay.startedFingerprints, [
            authorizationContext.trustedClientKeyFingerprint,
        ])
        XCTAssertEqual(pairedRelay.startedConfigurations.map(\.relayID), [pairedRelayID])
        XCTAssertEqual(lifecycle.events, ["overlay-start", "pair-start"])

        restoredModel.stop()

        XCTAssertEqual(privateOverlay.stopCount, 1)
        XCTAssertEqual(pairedRelay.stopCount, 1)
    }

    @MainActor
    func testInFlightPairedRefreshCannotActivateAfterRuntimeStopAndPreservesAdvancedLease() async throws {
        let fixture = try makeFixture(ticketGeneration: 13)
        let authorizationContext = try makeAuthorizationContext(requestID: "paired-refresh-stop-race")
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: fixture.routeToken,
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            clientKeyFingerprint: authorizationContext.trustedClientKeyFingerprint
        )
        let allocator = SuspendedPairedRelayAllocator(allocation: RelayServiceRouteAllocation(
            host: fixture.host,
            port: fixture.port,
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: fixture.currentExpiry + 60_000,
            relayNonce: "nonce-generation-14",
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            ticketGeneration: 14
        ))
        let pairedRelay = RecordingRelayTransport()
        let privateOverlay = RecordingPrivateOverlayTransport()
        let model = fixture.makeModel(
            allocator: allocator,
            relayClient: RecordingRelayTransport(),
            pairedRelayClient: pairedRelay,
            pairedPrivateOverlayTransport: privateOverlay
        )
        model.start(port: 43214)

        let refreshTask = Task { @MainActor in
            try await model.refreshRuntimeRoute(authorizationContext: authorizationContext)
        }
        await Task.yield()
        XCTAssertEqual(allocator.waitForRenewal(), .success)

        model.stop()
        allocator.completeRenewal()

        do {
            _ = try await refreshTask.value
            XCTFail("Expected stopped runtime to cancel the in-flight paired refresh")
        } catch is CancellationError {
            // Expected lifecycle invalidation.
        }

        XCTAssertTrue(privateOverlay.startedFingerprints.isEmpty)
        XCTAssertTrue(pairedRelay.startedConfigurations.isEmpty)
        let storedRoutes = PairScopedRelayRouteStore(
            userDefaults: fixture.defaults,
            relaySecretStore: fixture.secretStore
        ).loadAll()
        XCTAssertEqual(storedRoutes.count, 1)
        XCTAssertEqual(storedRoutes.first?.relayID, pairedRelayID)
        XCTAssertEqual(storedRoutes.first?.ticketGeneration, 14)
    }

    @MainActor
    func testInFlightPairedRefreshCannotRecreateRemovedPairRoute() async throws {
        let fixture = try makeFixture(ticketGeneration: 17)
        let authorizationContext = try makeAuthorizationContext(requestID: "paired-refresh-remove-race")
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: fixture.routeToken,
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            clientKeyFingerprint: authorizationContext.trustedClientKeyFingerprint
        )
        let allocator = SuspendedPairedRelayAllocator(allocation: RelayServiceRouteAllocation(
            host: fixture.host,
            port: fixture.port,
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: fixture.currentExpiry + 60_000,
            relayNonce: "nonce-generation-18",
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            ticketGeneration: 18
        ))
        let trustedStoreURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-paired-route-trust", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("trusted-devices.json", isDirectory: false)
        let trustedStore = TrustedDeviceStore(fileURL: trustedStoreURL)
        let trustedDevice = TrustedDevice(
            id: "client-remove-race",
            name: "Client Remove Race",
            publicKeyBase64: authorizationContext.trustedClientPublicKeyBase64
        )
        try await trustedStore.trust(trustedDevice)
        let pairedRelay = RecordingRelayTransport()
        let privateOverlay = RecordingPrivateOverlayTransport()
        let model = fixture.makeModel(
            allocator: allocator,
            relayClient: RecordingRelayTransport(),
            pairedRelayClient: pairedRelay,
            pairedPrivateOverlayTransport: privateOverlay,
            trustedDeviceStore: trustedStore
        )
        model.start(port: 43215)

        let refreshTask = Task { @MainActor in
            try await model.refreshRuntimeRoute(authorizationContext: authorizationContext)
        }
        await Task.yield()
        XCTAssertEqual(allocator.waitForRenewal(), .success)

        await model.removeTrustedDevice(trustedDevice)
        allocator.completeRenewal()

        do {
            _ = try await refreshTask.value
            XCTFail("Expected removed pair to cancel the in-flight paired refresh")
        } catch is CancellationError {
            // Expected pair-generation invalidation.
        }

        XCTAssertTrue(privateOverlay.startedFingerprints.isEmpty)
        XCTAssertTrue(pairedRelay.startedConfigurations.isEmpty)
        let remainingTrustedDevices = try await trustedStore.load()
        XCTAssertTrue(remainingTrustedDevices.isEmpty)
        XCTAssertTrue(PairScopedRelayRouteStore(
            userDefaults: fixture.defaults,
            relaySecretStore: fixture.secretStore
        ).loadAll().isEmpty)
    }

    @MainActor
    func testOlderCommittedRefreshWaitsForNewerFailureThenActivatesExactlyOnce() async throws {
        let fixture = try makeFixture(ticketGeneration: 30)
        let firstContext = try makeAuthorizationContext(requestID: "same-pair-refresh-first")
        let secondContext = try makeAuthorizationContext(
            requestID: "same-pair-refresh-second",
            matching: firstContext
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: fixture.routeToken,
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            clientKeyFingerprint: firstContext.trustedClientKeyFingerprint
        )
        let allocator = SequencedSuspendedPairedRelayAllocator()
        let pairedRelay = RecordingRelayTransport()
        let privateOverlay = RecordingPrivateOverlayTransport()
        let model = fixture.makeModel(
            allocator: allocator,
            relayClient: RecordingRelayTransport(),
            pairedRelayClient: pairedRelay,
            pairedPrivateOverlayTransport: privateOverlay
        )

        let firstTask = Task { @MainActor in
            try await model.refreshRuntimeRoute(authorizationContext: firstContext)
        }
        await Task.yield()
        XCTAssertEqual(allocator.waitForRenewal(), .success)
        let secondTask = Task { @MainActor in
            try await model.refreshRuntimeRoute(authorizationContext: secondContext)
        }
        await Task.yield()
        XCTAssertEqual(allocator.waitForRenewal(), .success)

        allocator.completeRenewal(
            at: 0,
            allocation: RelayServiceRouteAllocation(
                host: fixture.host,
                port: fixture.port,
                relayID: pairedRelayID,
                relayExpiresAtEpochMillis: fixture.currentExpiry + 60_000,
                relayNonce: "same-pair-generation-31",
                runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
                ticketGeneration: 31
            )
        )
        let firstRefresh = try await firstTask.value
        let firstResult = try XCTUnwrap(firstRefresh)
        await model.activateRuntimeRouteRefresh(firstResult)

        XCTAssertTrue(privateOverlay.startedFingerprints.isEmpty)
        XCTAssertTrue(pairedRelay.startedConfigurations.isEmpty)

        allocator.failRenewal(at: 1, error: .clientAuthorizationRejected)
        do {
            _ = try await secondTask.value
            XCTFail("Expected the newer same-pair refresh to fail")
        } catch let error as RelayServiceRouteAllocationError {
            XCTAssertEqual(error, .clientAuthorizationRejected)
        }

        XCTAssertEqual(privateOverlay.startedFingerprints, [
            firstContext.trustedClientKeyFingerprint,
        ])
        XCTAssertEqual(pairedRelay.startedConfigurations.map(\.relayID), [pairedRelayID])
        let storedRoute = try XCTUnwrap(PairScopedRelayRouteStore(
            userDefaults: fixture.defaults,
            relaySecretStore: fixture.secretStore
        ).loadAll().first)
        XCTAssertEqual(storedRoute.ticketGeneration, 31)
        XCTAssertEqual(storedRoute.relayNonce, "same-pair-generation-31")
    }

    @MainActor
    func testOlderConflictingResponseCannotOverwriteNewerCommittedRefresh() async throws {
        let fixture = try makeFixture(ticketGeneration: 40)
        let firstContext = try makeAuthorizationContext(requestID: "same-pair-conflict-first")
        let secondContext = try makeAuthorizationContext(
            requestID: "same-pair-conflict-second",
            matching: firstContext
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: fixture.routeToken,
            runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
            clientKeyFingerprint: firstContext.trustedClientKeyFingerprint
        )
        let allocator = SequencedSuspendedPairedRelayAllocator()
        let pairedRelay = RecordingRelayTransport()
        let privateOverlay = RecordingPrivateOverlayTransport()
        let model = fixture.makeModel(
            allocator: allocator,
            relayClient: RecordingRelayTransport(),
            pairedRelayClient: pairedRelay,
            pairedPrivateOverlayTransport: privateOverlay
        )

        let firstTask = Task { @MainActor in
            try await model.refreshRuntimeRoute(authorizationContext: firstContext)
        }
        await Task.yield()
        XCTAssertEqual(allocator.waitForRenewal(), .success)
        let secondTask = Task { @MainActor in
            try await model.refreshRuntimeRoute(authorizationContext: secondContext)
        }
        await Task.yield()
        XCTAssertEqual(allocator.waitForRenewal(), .success)

        allocator.completeRenewal(
            at: 1,
            allocation: RelayServiceRouteAllocation(
                host: fixture.host,
                port: fixture.port,
                relayID: pairedRelayID,
                relayExpiresAtEpochMillis: fixture.currentExpiry + 120_000,
                relayNonce: "newer-committed-generation-41",
                runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
                ticketGeneration: 41
            )
        )
        let secondRefresh = try await secondTask.value
        let secondResult = try XCTUnwrap(secondRefresh)
        await model.activateRuntimeRouteRefresh(secondResult)

        allocator.completeRenewal(
            at: 0,
            allocation: RelayServiceRouteAllocation(
                host: fixture.host,
                port: fixture.port,
                relayID: pairedRelayID,
                relayExpiresAtEpochMillis: fixture.currentExpiry + 60_000,
                relayNonce: "older-conflicting-generation-41",
                runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
                ticketGeneration: 41
            )
        )
        do {
            _ = try await firstTask.value
            XCTFail("Expected the stale conflicting response to be cancelled")
        } catch is CancellationError {
            // Expected compare-and-swap rejection.
        }

        XCTAssertEqual(privateOverlay.startedFingerprints, [
            firstContext.trustedClientKeyFingerprint,
        ])
        XCTAssertEqual(pairedRelay.startedConfigurations.map(\.relayID), [pairedRelayID])
        let storedRoute = try XCTUnwrap(PairScopedRelayRouteStore(
            userDefaults: fixture.defaults,
            relaySecretStore: fixture.secretStore
        ).loadAll().first)
        XCTAssertEqual(storedRoute.ticketGeneration, 41)
        XCTAssertEqual(storedRoute.relayNonce, "newer-committed-generation-41")
    }

    @MainActor
    func testPendingPairActivationsAreKeyedByFingerprint() async throws {
        let fixture = try makeFixture(ticketGeneration: 15)
        let firstContext = try makeAuthorizationContext(requestID: "paired-refresh-first")
        let secondContext = try makeAuthorizationContext(requestID: "paired-refresh-second")
        let store = PairScopedRelayRouteStore(
            userDefaults: fixture.defaults,
            relaySecretStore: fixture.secretStore
        )
        for (index, context) in [firstContext, secondContext].enumerated() {
            let relayID = RelayAllocationIdentityChallenge.pairedRelayID(
                routeToken: fixture.routeToken,
                runtimeKeyFingerprint: fixture.runtimeIdentity.fingerprint,
                clientKeyFingerprint: context.trustedClientKeyFingerprint
            )
            _ = try store.upsert(
                PairScopedRelayRoute(
                    clientKeyFingerprint: context.trustedClientKeyFingerprint,
                    routeToken: fixture.routeToken,
                    host: fixture.host,
                    port: fixture.port,
                    relayID: relayID,
                    relayExpiresAtEpochMillis: fixture.currentExpiry,
                    relayNonce: "stored-nonce-\(index)",
                    ticketGeneration: Int64(20 + index)
                ),
                relaySecret: fixture.endpointSecret
            )
        }
        let pairedRelay = RecordingRelayTransport()
        let privateOverlay = RecordingPrivateOverlayTransport()
        let model = fixture.makeModel(
            allocator: PerPairAdvancingRelayAllocator(),
            relayClient: RecordingRelayTransport(),
            pairedRelayClient: pairedRelay,
            pairedPrivateOverlayTransport: privateOverlay
        )

        let firstRefresh = try await model.refreshRuntimeRoute(authorizationContext: firstContext)
        let firstResult = try XCTUnwrap(firstRefresh)
        let secondRefresh = try await model.refreshRuntimeRoute(authorizationContext: secondContext)
        let secondResult = try XCTUnwrap(secondRefresh)
        await model.activateRuntimeRouteRefresh(firstResult)
        await model.activateRuntimeRouteRefresh(secondResult)

        XCTAssertEqual(Set(privateOverlay.startedFingerprints), Set([
            firstContext.trustedClientKeyFingerprint,
            secondContext.trustedClientKeyFingerprint,
        ]))
        XCTAssertEqual(Set(pairedRelay.startedConfigurations.map(\.relayID)), Set([
            try XCTUnwrap(firstResult.relayID),
            try XCTUnwrap(secondResult.relayID),
        ]))
    }
}

@MainActor
private func waitForRelayConfigurationCompletion(
    on model: CompanionAppModel,
    requestID: UUID
) async -> Bool {
    for _ in 0..<1_000 {
        if model.relayConfigurationRequestCompletion?.requestID == requestID {
            return true
        }
        try? await Task.sleep(nanoseconds: 1_000_000)
    }
    return false
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
        pairedRelayClient: (any RelayPeerTransport)? = nil,
        pairedPrivateOverlayTransport: (any MacRuntimePrivateOverlayTransport)? = nil,
        trustedDeviceStore: TrustedDeviceStore = TrustedDeviceStore(
            fileURL: FileManager.default.temporaryDirectory
                .appendingPathComponent("aetherlink-paired-route-trust", isDirectory: true)
                .appendingPathComponent(UUID().uuidString, isDirectory: true)
                .appendingPathComponent("trusted-devices.json", isDirectory: false)
        )
    ) -> CompanionAppModel {
        let privateOverlayFactory: (@Sendable () -> any MacRuntimePrivateOverlayTransport)?
        if let pairedPrivateOverlayTransport {
            privateOverlayFactory = { @Sendable in pairedPrivateOverlayTransport }
        } else {
            privateOverlayFactory = nil
        }
        return CompanionAppModel(
            relayClient: relayClient,
            pairedRelayClientFactory: {
                pairedRelayClient ?? RecordingRelayTransport()
            },
            pairedPrivateOverlayTransportFactory: privateOverlayFactory,
            relayServiceRouteAllocator: allocator,
            environment: environment,
            userDefaults: defaults,
            relaySecretStore: secretStore,
            trustedDeviceStore: trustedDeviceStore
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

private func makeAuthorizationContext(
    requestID: String,
    matching context: RuntimePairedRelayAuthorizationContext
) throws -> RuntimePairedRelayAuthorizationContext {
    try RuntimePairedRelayAuthorizationContext(
        requestID: requestID,
        connectionID: UUID(),
        trustedClientPublicKeyBase64: context.trustedClientPublicKeyBase64,
        trustedClientKeyFingerprint: context.trustedClientKeyFingerprint,
        transportBinding: context.transportBinding,
        clientAuthorizationProvider: context.clientAuthorizationProvider
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

private final class SuspendedPairedRelayAllocator: RelayServiceRouteAllocating, @unchecked Sendable {
    private let lock = NSLock()
    private let allocation: RelayServiceRouteAllocation
    private let renewalStarted = DispatchSemaphore(value: 0)
    private var continuation: CheckedContinuation<RelayServiceRouteAllocation, any Error>?

    init(allocation: RelayServiceRouteAllocation) {
        self.allocation = allocation
    }

    func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        allocationToken: String?,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        timeout: TimeInterval,
        cancellation: RelayRouteAllocationCancellation
    ) throws -> RelayServiceRouteAllocation {
        try cancellation.throwIfCancelledOrExpired()
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
        try await withCheckedThrowingContinuation { continuation in
            lock.withLock {
                self.continuation = continuation
            }
            renewalStarted.signal()
        }
    }

    func waitForRenewal(timeout: DispatchTime = .now() + 2) -> DispatchTimeoutResult {
        renewalStarted.wait(timeout: timeout)
    }

    func completeRenewal() {
        let continuation = lock.withLock {
            defer { self.continuation = nil }
            return self.continuation
        }
        continuation?.resume(returning: allocation)
    }
}

private final class SequencedSuspendedPairedRelayAllocator: RelayServiceRouteAllocating, @unchecked Sendable {
    private let lock = NSLock()
    private let renewalStarted = DispatchSemaphore(value: 0)
    private var continuations: [CheckedContinuation<RelayServiceRouteAllocation, any Error>?] = []

    func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        allocationToken: String?,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        timeout: TimeInterval,
        cancellation: RelayRouteAllocationCancellation
    ) throws -> RelayServiceRouteAllocation {
        try cancellation.throwIfCancelledOrExpired()
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
        try await withCheckedThrowingContinuation { continuation in
            lock.withLock {
                continuations.append(continuation)
            }
            renewalStarted.signal()
        }
    }

    func waitForRenewal(timeout: DispatchTime = .now() + 2) -> DispatchTimeoutResult {
        renewalStarted.wait(timeout: timeout)
    }

    func completeRenewal(at index: Int, allocation: RelayServiceRouteAllocation) {
        takeContinuation(at: index)?.resume(returning: allocation)
    }

    func failRenewal(at index: Int, error: RelayServiceRouteAllocationError) {
        takeContinuation(at: index)?.resume(throwing: error)
    }

    private func takeContinuation(
        at index: Int
    ) -> CheckedContinuation<RelayServiceRouteAllocation, any Error>? {
        lock.withLock {
            guard continuations.indices.contains(index) else {
                return nil
            }
            defer { continuations[index] = nil }
            return continuations[index]
        }
    }
}

private final class PerPairAdvancingRelayAllocator: RelayServiceRouteAllocating, @unchecked Sendable {
    func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        allocationToken: String?,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        timeout: TimeInterval,
        cancellation: RelayRouteAllocationCancellation
    ) throws -> RelayServiceRouteAllocation {
        try cancellation.throwIfCancelledOrExpired()
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
        guard let ticketGeneration = currentLease.ticketGeneration else {
            throw RelayServiceRouteAllocationError.invalidPairedRenewalRequest
        }
        return RelayServiceRouteAllocation(
            host: currentConfiguration.host,
            port: currentConfiguration.port,
            relayID: RelayAllocationIdentityChallenge.pairedRelayID(
                routeToken: currentRouteToken,
                runtimeKeyFingerprint: runtimeIdentity.fingerprint,
                clientKeyFingerprint: authorizationContext.trustedClientKeyFingerprint
            ),
            relayExpiresAtEpochMillis: currentLease.expiresAtEpochMillis + 60_000,
            relayNonce: "renewed-\(authorizationContext.trustedClientKeyFingerprint.prefix(16))",
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            ticketGeneration: ticketGeneration + 1
        )
    }
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
        timeout: TimeInterval,
        cancellation: RelayRouteAllocationCancellation
    ) throws -> RelayServiceRouteAllocation {
        try cancellation.throwIfCancelledOrExpired()
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
    private let onStart: @Sendable () -> Void
    private let onStop: @Sendable () -> Void
    private var storedStopCount = 0
    private var storedStartedConfigurations: [RelayPeerConfiguration] = []

    init(
        onStart: @escaping @Sendable () -> Void = {},
        onStop: @escaping @Sendable () -> Void = {}
    ) {
        self.onStart = onStart
        self.onStop = onStop
    }

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
        onStart()
    }

    func stop() {
        lock.withLock {
            storedStopCount += 1
        }
        onStop()
    }
}

private final class RecordingPrivateOverlayTransport: MacRuntimePrivateOverlayTransport, @unchecked Sendable {
    private let lock = NSLock()
    private let onStart: @Sendable () -> Void
    private var storedOnDisconnect: (@Sendable (UUID) -> Void)?
    private var storedStartedFingerprints: [String] = []
    private var storedStopCount = 0

    init(onStart: @escaping @Sendable () -> Void = {}) {
        self.onStart = onStart
    }

    var onDisconnect: (@Sendable (UUID) -> Void)? {
        get { lock.withLock { storedOnDisconnect } }
        set { lock.withLock { storedOnDisconnect = newValue } }
    }

    var startedFingerprints: [String] {
        lock.withLock { storedStartedFingerprints }
    }

    var stopCount: Int {
        lock.withLock { storedStopCount }
    }

    func start(
        clientKeyFingerprint: String,
        onStatusChange: (@Sendable (MacRuntimePrivateOverlayStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        lock.withLock {
            storedStartedFingerprints.append(clientKeyFingerprint)
        }
        onStart()
    }

    func stop() {
        lock.withLock {
            storedStopCount += 1
        }
    }
}

private final class RelayLifecycleRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var storedEvents: [String] = []

    var events: [String] {
        lock.withLock { storedEvents }
    }

    func record(_ event: String) {
        lock.withLock {
            storedEvents.append(event)
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
