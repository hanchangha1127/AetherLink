import CryptoKit
import Darwin
import Foundation
@testable import P2PNATContracts
@testable import TrustedDevices
import XCTest

final class TrustedDeviceStoreTests: XCTestCase {
    func testEndpointObject4Object26SharedDigestParityVectors() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(at: fileURL)
        XCTAssertEqual(
            try preparation.nextState.snapshotDigestHex(),
            "2f285232932e32da2ca1aea633f37df6bbfbf7b5ceb4978878b9278b94d224f7"
        )
        XCTAssertEqual(
            try preparation.nextCompoundRecord.digestHex(),
            "22a1b5f70632c2024fd565708d6227f2ad21037f450b5e1094892d9dd3c36a71"
        )
        _ = try await TrustedDeviceStore(fileURL: fileURL)
            .commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: preparation
            )
        let loaded = try await TrustedDeviceStore(fileURL: fileURL).load()
        let stored = try XCTUnwrap(
            loaded.first?.productionC1EndpointAdmissionState
        )
        let marker = try StoredProductionC1EndpointCommitMarker(
            canonicalBytes: try XCTUnwrap(stored.commitMarkerCanonicalBytes.first)
        )
        XCTAssertEqual(
            marker.endpointEntryDigest,
            "127958514e2894e27cc3ae3a362a7691ce2a4161c6e2024f70cff01d2cfd6a37"
        )
    }

    func testEndpointPersistenceRejectsPreObject26SchemaVersions() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(at: fileURL)
        _ = try await TrustedDeviceStore(fileURL: fileURL)
            .commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: preparation
            )
        let committedBytes = try Data(contentsOf: fileURL)

        var rows = try XCTUnwrap(
            JSONSerialization.jsonObject(with: committedBytes) as? [[String: Any]]
        )
        var state = try XCTUnwrap(
            rows[0]["productionC1EndpointAdmissionState"] as? [String: Any]
        )
        state["version"] = 1
        rows[0]["productionC1EndpointAdmissionState"] = state
        try JSONSerialization.data(withJSONObject: rows).write(to: fileURL)
        do {
            _ = try await TrustedDeviceStore(fileURL: fileURL).load()
            XCTFail("Expected the pre-object-26 endpoint state schema to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionC1EndpointStateCorrupt
            )
        }

        try committedBytes.write(to: fileURL)
        rows = try XCTUnwrap(
            JSONSerialization.jsonObject(with: committedBytes) as? [[String: Any]]
        )
        state = try XCTUnwrap(
            rows[0]["productionC1EndpointAdmissionState"] as? [String: Any]
        )
        var markers = try XCTUnwrap(
            state["commitMarkerCanonicalBytes"] as? [String]
        )
        var marker = try XCTUnwrap(
            JSONSerialization.jsonObject(
                with: try XCTUnwrap(Data(base64Encoded: markers[0]))
            ) as? [String: Any]
        )
        marker["version"] = 3
        markers[0] = try JSONSerialization.data(
            withJSONObject: marker,
            options: [.sortedKeys, .withoutEscapingSlashes]
        ).base64EncodedString()
        state["commitMarkerCanonicalBytes"] = markers
        rows[0]["productionC1EndpointAdmissionState"] = state
        try JSONSerialization.data(withJSONObject: rows).write(to: fileURL)
        do {
            _ = try await TrustedDeviceStore(fileURL: fileURL).load()
            XCTFail("Expected the pre-object-26 marker schema to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionC1EndpointStateCorrupt
            )
        }
    }

    func testPublicAuthorityTokenAPISurfaceHasNoExternalInitializersOrRawAdmissionMint()
        throws
    {
        let trustedSymbols = try publicSymbolGraph(module: "TrustedDevices")
        let contractSymbols = try publicSymbolGraph(module: "P2PNATContracts")
        let opaqueTypes: Set<String> = [
            "ProductionPairAdmissionPermit",
            "VerifiedProductionC1AdmissionPermit",
            "ProductionC1EndpointGrantCompoundCommitToken",
            "ProductionC1EndpointGrantCommitReadback",
        ]
        let externalInitializers = trustedSymbols.filter { symbol in
            guard symbolKind(symbol) == "swift.init",
                  let owner = symbolPath(symbol).first else { return false }
            return opaqueTypes.contains(owner)
        }
        XCTAssertTrue(
            externalInitializers.isEmpty,
            "Opaque durable authority values must expose no public initializers: \(externalInitializers.map(symbolPath))"
        )
        XCTAssertFalse(trustedSymbols.contains {
            symbolPath($0).last?.hasPrefix("admitProductionSecureSession(") == true
        })
        XCTAssertFalse(contractSymbols.contains {
            symbolPath($0).contains("ProductionPairStateAdmission")
                || symbolPath($0).contains("ProductionPairAdmissionPreparation")
                || symbolPath($0).contains("ProductionPairAdmissionPermit")
        })
        XCTAssertTrue(trustedSymbols.contains {
            symbolPath($0).last?.hasPrefix("admitVerifiedProductionC1SecureSession(") == true
        })
    }

    func testLegacyStoreWithoutProductionPairStateRemainsReadable() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let legacy = LegacyTrustedDevice(
            id: "legacy-device",
            name: "Legacy phone",
            publicKeyBase64: "legacy-public-key",
            pairedAt: Date(timeIntervalSince1970: 500)
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        try encoder.encode([legacy]).write(to: fileURL)

        let loaded = try await TrustedDeviceStore(fileURL: fileURL).load()

        XCTAssertEqual(
            loaded,
            [
                TrustedDevice(
                    id: legacy.id,
                    name: legacy.name,
                    publicKeyBase64: legacy.publicKeyBase64,
                    pairedAt: legacy.pairedAt
                ),
            ]
        )
        XCTAssertNil(loaded[0].productionPairState)
    }

    func testCorruptProductionPairStateFailsClosedWithoutRewritingStore() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let originalData = Data(
            """
            [{"id":"device-1","name":"Phone","publicKeyBase64":"public-key-device-1","pairedAt":"1970-01-01T00:08:20Z","productionPairState":"AA=="}]
            """.utf8
        )
        try originalData.write(to: fileURL)

        do {
            _ = try await TrustedDeviceStore(fileURL: fileURL).load()
            XCTFail("Expected corrupt production pair state to fail closed")
        } catch {
            XCTAssertEqual(error as? ProductionPairStateError, .malformedCanonical)
        }
        XCTAssertEqual(try Data(contentsOf: fileURL), originalData)
    }

    func testProductionPairStateRoundTripsThroughAtomicStore() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let authority = try makeProductionPairAuthority(generation: 7, authorityRevision: 1)
        let state = try ProductionPairStateSnapshot(authority: authority, localRevision: 1)
        let device = TrustedDevice(
            id: "stateful-device",
            name: "Stateful phone",
            publicKeyBase64: "stateful-public-key",
            pairedAt: Date(timeIntervalSince1970: 600)
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

        let loaded = try await store.load()
        XCTAssertEqual(loaded, [TrustedDevice(
            id: device.id,
            name: device.name,
            publicKeyBase64: device.publicKeyBase64,
            pairedAt: device.pairedAt,
            productionPairState: state
        )])
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
    }

    func testTrustPreservesExistingProductionPairStateWhenReplacementOmitsIt() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let authority = try makeProductionPairAuthority(generation: 8, authorityRevision: 1)
        let state = try ProductionPairStateSnapshot(authority: authority, localRevision: 1)
        let original = TrustedDevice(
            id: "preserved-device",
            name: "Original name",
            publicKeyBase64: "preserved-public-key",
            pairedAt: Date(timeIntervalSince1970: 700),
            productionPairState: state
        )
        let replacement = TrustedDevice(
            id: original.id,
            name: "Updated name",
            publicKeyBase64: original.publicKeyBase64,
            pairedAt: original.pairedAt
        )
        let store = TrustedDeviceStore(fileURL: fileURL)
        try await store.trust(TrustedDevice(
            id: original.id,
            name: original.name,
            publicKeyBase64: original.publicKeyBase64,
            pairedAt: original.pairedAt
        ))
        try await store.applyVerifiedProductionPairTransition(
            deviceID: original.id,
            expectedPublicKeyBase64: original.publicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: nil,
                nextAuthority: authority
            )
        )

        try await store.trust(replacement)

        let loadedDevices = try await store.load()
        let loaded = try XCTUnwrap(loadedDevices.first)
        XCTAssertEqual(loaded.name, replacement.name)
        XCTAssertEqual(loaded.productionPairState, state)
    }

    func testTrustRejectsProductionPairStateOverwriteAndIdentityReplacement() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let originalAuthority = try makeProductionPairAuthority(generation: 9, authorityRevision: 1)
        let originalState = try ProductionPairStateSnapshot(
            authority: originalAuthority,
            localRevision: 1
        )
        let original = TrustedDevice(
            id: "protected-device",
            name: "Protected phone",
            publicKeyBase64: "protected-public-key",
            pairedAt: Date(timeIntervalSince1970: 800),
            productionPairState: originalState
        )
        let store = TrustedDeviceStore(fileURL: fileURL)
        try await store.trust(TrustedDevice(
            id: original.id,
            name: original.name,
            publicKeyBase64: original.publicKeyBase64,
            pairedAt: original.pairedAt
        ))
        try await store.applyVerifiedProductionPairTransition(
            deviceID: original.id,
            expectedPublicKeyBase64: original.publicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: nil,
                nextAuthority: originalAuthority
            )
        )

        let downgraded = TrustedDevice(
            id: original.id,
            name: original.name,
            publicKeyBase64: original.publicKeyBase64,
            pairedAt: original.pairedAt,
            productionPairState: try makeProductionPairState(
                generation: 8,
                authorityRevision: 10
            )
        )
        do {
            try await store.trust(downgraded)
            XCTFail("Expected generic trust to reject a pair-state overwrite")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionPairStateOverwriteRejected
            )
        }

        let changedIdentity = TrustedDevice(
            id: original.id,
            name: original.name,
            publicKeyBase64: "replacement-public-key",
            pairedAt: original.pairedAt
        )
        do {
            try await store.trust(changedIdentity)
            XCTFail("Expected generic trust to reject identity replacement")
        } catch {
            XCTAssertEqual(error as? TrustedDeviceStoreError, .trustedDeviceIdentityMismatch)
        }
        let loaded = try await store.load()
        XCTAssertEqual(loaded, [original])
    }

    func testTrustRejectsProductionPairStateBootstrapWithoutVerifiedTransition() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let state = try makeProductionPairState(generation: 1, authorityRevision: 1)
        let stateful = TrustedDevice(
            id: "unverified-state",
            name: "Unverified state",
            publicKeyBase64: "unverified-public-key",
            pairedAt: Date(timeIntervalSince1970: 850),
            productionPairState: state
        )
        let store = TrustedDeviceStore(fileURL: fileURL)

        do {
            try await store.trust(stateful)
            XCTFail("Expected generic trust to reject a new production pair state")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionPairStateOverwriteRejected
            )
        }

        let stateless = TrustedDevice(
            id: stateful.id,
            name: stateful.name,
            publicKeyBase64: stateful.publicKeyBase64,
            pairedAt: stateful.pairedAt
        )
        try await store.trust(stateless)
        do {
            try await store.trust(stateful)
            XCTFail("Expected generic trust to reject state injection into an existing row")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionPairStateOverwriteRejected
            )
        }
        let loaded = try await store.load()
        XCTAssertEqual(loaded, [stateless])
    }

    func testVerifiedProductionPairTransitionPersistsAndReplaysIdempotently() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let device = makeDevice(id: "transition-device", name: "Transition", timestamp: 900)
        let store = TrustedDeviceStore(fileURL: fileURL)
        try await store.trust(device)
        let authority = try makeProductionPairAuthority(
            generation: 1,
            authorityRevision: 1
        )
        let transition = try ProductionPairStateTransition(
            expectedPreviousAuthorityDigest: nil,
            nextAuthority: authority
        )

        let applied = try await store.applyVerifiedProductionPairTransition(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            transition: transition
        )
        let replayed = try await store.applyVerifiedProductionPairTransition(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            transition: transition
        )

        XCTAssertEqual(applied, replayed)
        XCTAssertEqual(applied.localRevision, 1)
        let loaded = try await store.load()
        XCTAssertEqual(loaded.first?.productionPairState, applied)
    }

    func testCompetingVerifiedTransitionsSerializeAcrossStoreInstances() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let device = makeDevice(id: "serialized-device", name: "Serialized", timestamp: 950)
        let bootstrapStore = TrustedDeviceStore(fileURL: fileURL)
        try await bootstrapStore.trust(device)
        let initialAuthority = try makeProductionPairAuthority(
            generation: 1,
            authorityRevision: 1
        )
        let initial = try await bootstrapStore.applyVerifiedProductionPairTransition(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            transition: try ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: nil,
                nextAuthority: initialAuthority
            )
        )
        let expectedDigest = try initial.authority.digestHex()
        let firstTransition = try ProductionPairStateTransition(
            expectedPreviousAuthorityDigest: expectedDigest,
            nextAuthority: makeProductionPairAuthority(
                generation: 2,
                authorityRevision: 2,
                transitionDigit: "7"
            )
        )
        let competingTransition = try ProductionPairStateTransition(
            expectedPreviousAuthorityDigest: expectedDigest,
            nextAuthority: makeProductionPairAuthority(
                generation: 3,
                authorityRevision: 2,
                transitionDigit: "8"
            )
        )
        let firstSnapshotLoaded = DispatchSemaphore(value: 0)
        let releaseFirstMutation = DispatchSemaphore(value: 0)
        let secondMutationContended = DispatchSemaphore(value: 0)
        let firstStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didLoadMutationSnapshot: {
                    firstSnapshotLoaded.signal()
                    releaseFirstMutation.wait()
                }
            )
        )
        let secondStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didObserveMutationLockContention: { secondMutationContended.signal() }
            )
        )
        var firstMutationReleased = false
        defer {
            if !firstMutationReleased { releaseFirstMutation.signal() }
        }

        let firstTask = Task {
            try await firstStore.applyVerifiedProductionPairTransition(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                transition: firstTransition
            )
        }
        XCTAssertEqual(firstSnapshotLoaded.wait(timeout: .now() + 2), .success)
        let competingTask = Task {
            try await secondStore.applyVerifiedProductionPairTransition(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                transition: competingTransition
            )
        }
        XCTAssertEqual(secondMutationContended.wait(timeout: .now() + 2), .success)

        firstMutationReleased = true
        releaseFirstMutation.signal()
        let applied = try await firstTask.value
        do {
            _ = try await competingTask.value
            XCTFail("Expected the stale competing transition to fail closed")
        } catch {
            XCTAssertEqual(error as? ProductionPairStateError, .previousStateMismatch)
        }

        let finalState = try await TrustedDeviceStore(fileURL: fileURL)
            .load()
            .first?
            .productionPairState
        XCTAssertEqual(finalState, applied)
        XCTAssertEqual(finalState?.authority.generation, 2)
        XCTAssertEqual(finalState?.localRevision, 2)
    }

    func testEndpointCompoundCommitReturnsTokenOnlyAfterExactDurableByteReadback()
        async throws
    {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(at: fileURL)
        let bytesObservedBeforeReturn = LockedBox<Data>()
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didCommitBeforeReadback: { url in
                    if let bytes = try? Data(contentsOf: url) {
                        bytesObservedBeforeReturn.set(bytes)
                    }
                }
            )
        )

        let outcome = try await store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            preparation: preparation
        )

        guard case let .committed(token) = outcome else {
            return XCTFail("Expected an applied durable commit token")
        }
        XCTAssertEqual(token.admissionID, preparation.entry.admissionId)
        XCTAssertEqual(token.sessionID, preparation.sessionID)
        XCTAssertEqual(
            token.routeAuthorizationDigest,
            preparation.routeAuthorizationDigest
        )
        XCTAssertEqual(
            token.grantAuthorizationDigest,
            preparation.grantAuthorizationDigest
        )
        XCTAssertNotEqual(
            token.routeAuthorizationDigest,
            token.grantAuthorizationDigest
        )
        XCTAssertEqual(token.pairAuthorityDigest, preparation.pairAuthorityDigest)
        XCTAssertEqual(token.effectiveNotBeforeMs, preparation.effectiveNotBeforeMs)
        XCTAssertEqual(token.expiresAtMs, preparation.expiresAtMs)
        XCTAssertEqual(token.ledgerRevision, preparation.nextState.revision)
        XCTAssertEqual(try Data(contentsOf: fileURL), bytesObservedBeforeReturn.get())
        let restartReadback = try await TrustedDeviceStore(fileURL: fileURL)
            .readProductionC1EndpointGrantCommit(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                admissionID: preparation.entry.admissionId,
                bindingDigest: preparation.entry.bindingDigest
            )
        XCTAssertEqual(restartReadback?.markerDigest, token.markerDigest)
        XCTAssertEqual(restartReadback?.compoundCommitDigest, token.compoundCommitDigest)
        XCTAssertEqual(restartReadback?.sessionID, token.sessionID)
        XCTAssertEqual(
            restartReadback?.routeAuthorizationDigest,
            token.routeAuthorizationDigest
        )
        XCTAssertEqual(
            restartReadback?.grantAuthorizationDigest,
            token.grantAuthorizationDigest
        )
        XCTAssertEqual(restartReadback?.pairAuthorityDigest, token.pairAuthorityDigest)
        XCTAssertEqual(restartReadback?.effectiveNotBeforeMs, token.effectiveNotBeforeMs)
        XCTAssertEqual(restartReadback?.expiresAtMs, token.expiresAtMs)
    }

    func testEndpointCommitRejectsExpiredPreparationBeforeWriteAndPreservesBytes() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(
            at: fileURL,
            effectiveNotBeforeMs: 100,
            expiresAtMs: 200
        )
        let originalBytes = try Data(contentsOf: fileURL)
        let clock = LockedBox<UInt64>()
        clock.set(200)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            trustedNowEpochMillis: { clock.get() ?? 0 }
        )

        do {
            _ = try await store.commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: preparation
            )
            XCTFail("Expected the exclusive expiry boundary to reject before write")
        } catch {
            XCTAssertEqual(error as? ProductionC1Error, .expired)
        }

        XCTAssertEqual(try Data(contentsOf: fileURL), originalBytes)
    }

    func testEndpointCommitAcceptsExactNotBeforeAndTokenCarriesWindow() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(
            at: fileURL,
            effectiveNotBeforeMs: 100,
            expiresAtMs: 200
        )
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            trustedNowEpochMillis: { 100 }
        )

        let outcome = try await store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            preparation: preparation
        )

        guard case let .committed(token) = outcome else {
            return XCTFail("Expected exact not-before to remain valid")
        }
        XCTAssertEqual(token.effectiveNotBeforeMs, 100)
        XCTAssertEqual(token.expiresAtMs, 200)
    }

    func testEndpointCommitExpiryDuringReadbackLeavesOnlyNonAuthorizingCommit() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(
            at: fileURL,
            effectiveNotBeforeMs: 100,
            expiresAtMs: 200
        )
        let originalBytes = try Data(contentsOf: fileURL)
        let clock = LockedBox<UInt64>()
        clock.set(150)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didCommitBeforeReadback: { _ in clock.set(200) }
            ),
            trustedNowEpochMillis: { clock.get() ?? 0 }
        )

        do {
            _ = try await store.commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: preparation
            )
            XCTFail("Expected expiry after durable write to withhold the live token")
        } catch {
            XCTAssertEqual(error as? ProductionC1Error, .expired)
        }

        XCTAssertNotEqual(try Data(contentsOf: fileURL), originalBytes)
        let readback = try await TrustedDeviceStore(fileURL: fileURL)
            .readProductionC1EndpointGrantCommit(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                admissionID: preparation.entry.admissionId,
                bindingDigest: preparation.entry.bindingDigest
            )
        XCTAssertEqual(readback?.effectiveNotBeforeMs, 100)
        XCTAssertEqual(readback?.expiresAtMs, 200)
    }

    func testEndpointCommitRejectsTrustedClockRegressionAfterReadback() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(
            at: fileURL,
            effectiveNotBeforeMs: 100,
            expiresAtMs: 200
        )
        let clock = LockedBox<UInt64>()
        clock.set(150)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didCommitBeforeReadback: { _ in clock.set(149) }
            ),
            trustedNowEpochMillis: { clock.get() ?? 0 }
        )

        do {
            _ = try await store.commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: preparation
            )
            XCTFail("Expected a regressed trusted clock to withhold the token")
        } catch {
            XCTAssertEqual(error as? TrustedDeviceStoreError, .trustedClockRegression)
        }

        let readback = try await TrustedDeviceStore(fileURL: fileURL)
            .readProductionC1EndpointGrantCommit(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                admissionID: preparation.entry.admissionId,
                bindingDigest: preparation.entry.bindingDigest
            )
        XCTAssertNotNil(readback)
    }

    func testExpiredEndpointRetryRemainsReadbackOnly() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, applied) = try bootstrapEndpointCommitStore(
            at: fileURL,
            effectiveNotBeforeMs: 100,
            expiresAtMs: 200
        )
        let clock = LockedBox<UInt64>()
        clock.set(150)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            trustedNowEpochMillis: { clock.get() ?? 0 }
        )
        _ = try await store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            preparation: applied
        )
        let committedBytes = try Data(contentsOf: fileURL)
        clock.set(200)
        let retry = try endpointPreparation(
            currentLedger: applied.nextState,
            currentPair: applied.nextPairSnapshot,
            entry: applied.entry,
            disposition: .idempotent,
            effectiveNotBeforeMs: 100,
            expiresAtMs: 200
        )

        let outcome = try await store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            preparation: retry
        )

        guard case let .alreadyCommitted(readback) = outcome else {
            return XCTFail("Expired retry must never mint a live token")
        }
        XCTAssertEqual(readback.effectiveNotBeforeMs, 100)
        XCTAssertEqual(readback.expiresAtMs, 200)
        XCTAssertEqual(try Data(contentsOf: fileURL), committedBytes)
    }

    func testEndpointCommitWithholdsTokenWhenPostRenameBytesDoNotMatch() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(at: fileURL)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didCommitBeforeReadback: { url in
                    guard let handle = try? FileHandle(forWritingTo: url) else { return }
                    defer { try? handle.close() }
                    _ = try? handle.seekToEnd()
                    try? handle.write(contentsOf: Data([0x20]))
                }
            )
        )

        do {
            _ = try await store.commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: preparation
            )
            XCTFail("Expected exact-byte readback mismatch to withhold the token")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionC1EndpointCommitReadbackMismatch
            )
        }
    }

    func testIdempotentEndpointRetryReturnsOnlyReadbackAndDoesNotGrowMarkers()
        async throws
    {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, applied) = try bootstrapEndpointCommitStore(at: fileURL)
        let store = TrustedDeviceStore(fileURL: fileURL)
        _ = try await store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            preparation: applied
        )
        let committedBytes = try Data(contentsOf: fileURL)
        let retry = try endpointPreparation(
            currentLedger: applied.nextState,
            currentPair: applied.nextPairSnapshot,
            entry: applied.entry,
            disposition: .idempotent
        )

        let outcome = try await store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            preparation: retry
        )

        guard case let .alreadyCommitted(readback) = outcome else {
            return XCTFail("An idempotent retry must never mint a live commit token")
        }
        XCTAssertEqual(readback.admissionID, applied.entry.admissionId)
        XCTAssertEqual(try Data(contentsOf: fileURL), committedBytes)
        let loaded = try await store.load()
        XCTAssertEqual(
            loaded.first?.productionC1EndpointAdmissionState?
                .commitMarkerCanonicalBytes.count,
            1
        )
    }

    func testSequentialEndpointCommitsAppendCanonicalChainedMarkers() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, firstPreparation) = try bootstrapEndpointCommitStore(at: fileURL)
        let store = TrustedDeviceStore(fileURL: fileURL)
        _ = try await store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            preparation: firstPreparation
        )
        let secondPreparation = try makeAppliedEndpointPreparation(
            currentLedger: firstPreparation.nextState,
            currentPair: firstPreparation.nextPairSnapshot,
            digit: "8"
        )
        _ = try await store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            preparation: secondPreparation
        )

        let loadedDevices = try await store.load()
        let stored = try XCTUnwrap(
            loadedDevices.first?.productionC1EndpointAdmissionState
        )
        XCTAssertEqual(stored.commitMarkerCanonicalBytes.count, 2)
        let firstMarker = try StoredProductionC1EndpointCommitMarker(
            canonicalBytes: stored.commitMarkerCanonicalBytes[0]
        )
        let secondMarker = try StoredProductionC1EndpointCommitMarker(
            canonicalBytes: stored.commitMarkerCanonicalBytes[1]
        )
        XCTAssertEqual(firstMarker.sequence, 1)
        XCTAssertNil(firstMarker.previousMarkerDigest)
        XCTAssertEqual(secondMarker.sequence, 2)
        XCTAssertEqual(secondMarker.previousMarkerDigest, try firstMarker.digestHex())
        XCTAssertEqual(
            secondMarker.expectedCompoundDigest,
            firstMarker.committedCompoundDigest
        )
    }

    func testEndpointCompoundCommitSaveFailureIsAtomicAndReturnsNoToken() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(at: fileURL)
        let originalBytes = try Data(contentsOf: fileURL)
        let constrained = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            limits: testLimits(maxStoreBytes: originalBytes.count)
        )

        do {
            _ = try await constrained.commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: preparation
            )
            XCTFail("Expected compound persistence to fail atomically")
        } catch {
            XCTAssertNotNil(error as? TrustedDeviceStoreResourceLimitError)
        }
        XCTAssertEqual(try Data(contentsOf: fileURL), originalBytes)
        let absentReadback = try await TrustedDeviceStore(fileURL: fileURL)
            .readProductionC1EndpointGrantCommit(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                admissionID: preparation.entry.admissionId,
                bindingDigest: preparation.entry.bindingDigest
            )
        XCTAssertNil(absentReadback)
    }

    func testCompetingEndpointCompoundCommitsSerializeAndRejectStalePreparation()
        async throws
    {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, firstPreparation) = try bootstrapEndpointCommitStore(at: fileURL)
        let bootstrapDevices = try await TrustedDeviceStore(fileURL: fileURL).load()
        let currentPair = try XCTUnwrap(bootstrapDevices.first?.productionPairState)
        let baseline = try ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest: currentPair.authority.digestHex(),
            pairLocalRevision: currentPair.localRevision,
            remainingGrants: UInt64(
                ProductionC1EndpointLedgerPersistenceContract.maximumEntries
            ),
            retentionLimit: UInt32(
                ProductionC1EndpointLedgerPersistenceContract.maximumEntries
            )
        )
        let secondPreparation = try makeAppliedEndpointPreparation(
            currentLedger: baseline,
            currentPair: currentPair,
            digit: "8"
        )
        let firstLoaded = DispatchSemaphore(value: 0)
        let releaseFirst = DispatchSemaphore(value: 0)
        let secondContended = DispatchSemaphore(value: 0)
        let firstStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didLoadMutationSnapshot: {
                    firstLoaded.signal()
                    releaseFirst.wait()
                }
            )
        )
        let secondStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didObserveMutationLockContention: { secondContended.signal() }
            )
        )
        var didRelease = false
        defer { if !didRelease { releaseFirst.signal() } }

        let firstTask = Task {
            try await firstStore.commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: firstPreparation
            )
        }
        XCTAssertEqual(firstLoaded.wait(timeout: .now() + 2), .success)
        let secondTask = Task {
            try await secondStore.commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: secondPreparation
            )
        }
        XCTAssertEqual(secondContended.wait(timeout: .now() + 2), .success)
        didRelease = true
        releaseFirst.signal()
        guard case .committed = try await firstTask.value else {
            return XCTFail("Expected the first serialized commit to win")
        }
        do {
            _ = try await secondTask.value
            XCTFail("Expected the stale concurrent preparation to fail")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1CandidateCapabilityError,
                .revisionMismatch
            )
        }
    }

    func testEndpointMarkerTransplantAndCorruptionFailClosed() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(at: fileURL)
        _ = try await TrustedDeviceStore(fileURL: fileURL)
            .commitPreparedProductionC1EndpointGrantForTesting(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                preparation: preparation
            )
        let committedBytes = try Data(contentsOf: fileURL)
        var rows = try XCTUnwrap(
            JSONSerialization.jsonObject(with: committedBytes) as? [[String: Any]]
        )
        rows[0]["id"] = "transplanted-device"
        let transplantedBytes = try JSONSerialization.data(withJSONObject: rows)
        try transplantedBytes.write(to: fileURL)

        do {
            _ = try await TrustedDeviceStore(fileURL: fileURL).load()
            XCTFail("Expected the device-bound marker transplant to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionC1EndpointCommitChainMismatch
            )
        }

        try committedBytes.write(to: fileURL)
        rows = try XCTUnwrap(
            JSONSerialization.jsonObject(with: committedBytes) as? [[String: Any]]
        )
        var state = try XCTUnwrap(
            rows[0]["productionC1EndpointAdmissionState"] as? [String: Any]
        )
        var markers = try XCTUnwrap(
            state["commitMarkerCanonicalBytes"] as? [String]
        )
        let grantMarkerBytes = try XCTUnwrap(Data(base64Encoded: markers[0]))
        var grantMarker = try XCTUnwrap(
            JSONSerialization.jsonObject(with: grantMarkerBytes) as? [String: Any]
        )
        grantMarker["grantAuthorizationDigest"] = String(repeating: "e", count: 64)
        markers[0] = try JSONSerialization.data(
            withJSONObject: grantMarker,
            options: [.sortedKeys, .withoutEscapingSlashes]
        ).base64EncodedString()
        state["commitMarkerCanonicalBytes"] = markers
        rows[0]["productionC1EndpointAdmissionState"] = state
        try JSONSerialization.data(withJSONObject: rows).write(to: fileURL)
        do {
            _ = try await TrustedDeviceStore(fileURL: fileURL).load()
            XCTFail("Expected marker grant-authorization substitution to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionC1EndpointCommitChainMismatch
            )
        }

        try committedBytes.write(to: fileURL)
        rows = try XCTUnwrap(
            JSONSerialization.jsonObject(with: committedBytes) as? [[String: Any]]
        )
        state = try XCTUnwrap(
            rows[0]["productionC1EndpointAdmissionState"] as? [String: Any]
        )
        markers = try XCTUnwrap(state["commitMarkerCanonicalBytes"] as? [String])
        let firstMarkerBytes = try XCTUnwrap(Data(base64Encoded: markers[0]))
        var firstMarker = try XCTUnwrap(
            JSONSerialization.jsonObject(with: firstMarkerBytes) as? [String: Any]
        )
        firstMarker["expectedCompoundDigest"] = String(repeating: "f", count: 64)
        markers[0] = try JSONSerialization.data(
            withJSONObject: firstMarker,
            options: [.sortedKeys, .withoutEscapingSlashes]
        ).base64EncodedString()
        state["commitMarkerCanonicalBytes"] = markers
        rows[0]["productionC1EndpointAdmissionState"] = state
        try JSONSerialization.data(withJSONObject: rows).write(to: fileURL)
        do {
            _ = try await TrustedDeviceStore(fileURL: fileURL).load()
            XCTFail("Expected an unreachable first compound predecessor to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionC1EndpointCommitChainMismatch
            )
        }

        try committedBytes.write(to: fileURL)
        rows = try XCTUnwrap(
            JSONSerialization.jsonObject(with: committedBytes) as? [[String: Any]]
        )
        state = try XCTUnwrap(
            rows[0]["productionC1EndpointAdmissionState"] as? [String: Any]
        )
        markers = try XCTUnwrap(state["commitMarkerCanonicalBytes"] as? [String])
        let bindingMarkerBytes = try XCTUnwrap(Data(base64Encoded: markers[0]))
        var bindingMarker = try XCTUnwrap(
            JSONSerialization.jsonObject(with: bindingMarkerBytes) as? [String: Any]
        )
        bindingMarker["routeAuthorizationDigest"] = String(repeating: "f", count: 64)
        markers[0] = try JSONSerialization.data(
            withJSONObject: bindingMarker,
            options: [.sortedKeys, .withoutEscapingSlashes]
        ).base64EncodedString()
        state["commitMarkerCanonicalBytes"] = markers
        rows[0]["productionC1EndpointAdmissionState"] = state
        try JSONSerialization.data(withJSONObject: rows).write(to: fileURL)
        do {
            _ = try await TrustedDeviceStore(fileURL: fileURL).load()
            XCTFail("Expected marker route-authorization substitution to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionC1EndpointCommitChainMismatch
            )
        }

        try committedBytes.write(to: fileURL)
        rows = try XCTUnwrap(
            JSONSerialization.jsonObject(with: committedBytes) as? [[String: Any]]
        )
        state = try XCTUnwrap(
            rows[0]["productionC1EndpointAdmissionState"] as? [String: Any]
        )
        markers = try XCTUnwrap(state["commitMarkerCanonicalBytes"] as? [String])
        markers[0] = Data("corrupt".utf8).base64EncodedString()
        state["commitMarkerCanonicalBytes"] = markers
        rows[0]["productionC1EndpointAdmissionState"] = state
        try JSONSerialization.data(withJSONObject: rows).write(to: fileURL)
        do {
            _ = try await TrustedDeviceStore(fileURL: fileURL).load()
            XCTFail("Expected corrupt marker bytes to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionC1EndpointStateCorrupt
            )
        }
    }

    func testGenericTrustPreservesCommittedEndpointStateAndRejectsInjection() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let (device, preparation) = try bootstrapEndpointCommitStore(at: fileURL)
        let store = TrustedDeviceStore(fileURL: fileURL)
        _ = try await store.commitPreparedProductionC1EndpointGrantForTesting(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            preparation: preparation
        )
        let committedDevices = try await store.load()
        let committed = try XCTUnwrap(committedDevices.first)
        let replacement = TrustedDevice(
            id: committed.id,
            name: "Renamed",
            publicKeyBase64: committed.publicKeyBase64,
            pairedAt: committed.pairedAt
        )
        try await store.trust(replacement)
        let preservedDevices = try await store.load()
        let preserved = try XCTUnwrap(preservedDevices.first)
        XCTAssertEqual(
            preserved.productionC1EndpointAdmissionState,
            committed.productionC1EndpointAdmissionState
        )
        let injected = TrustedDevice(
            id: preserved.id,
            name: preserved.name,
            publicKeyBase64: preserved.publicKeyBase64,
            pairedAt: preserved.pairedAt,
            productionPairState: preserved.productionPairState,
            productionC1EndpointAdmissionState: preserved.productionC1EndpointAdmissionState
        )
        do {
            try await store.trust(injected)
            XCTFail("Expected generic trust to reject endpoint-state injection")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionC1EndpointStateInjectionRejected
            )
        }
    }

    func testEndpointLedgerPersistenceCodecIsStrictAndContainsNoSecretCanary() throws {
        let pair = try makeProductionPairState(generation: 30, authorityRevision: 1)
        let ledger = try ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest: pair.authority.digestHex(),
            pairLocalRevision: pair.localRevision,
            remainingGrants: 64,
            retentionLimit: 64
        )
        let canonical = try ledger.persistenceCanonicalBytes()
        XCTAssertEqual(
            try ProductionC1EndpointGrantLedgerState(persistenceCanonicalBytes: canonical),
            ledger
        )
        let framed = Data([0xff]) + canonical + Data([0xee])
        let nonZeroBasedSlice = framed[1..<(1 + canonical.count)]
        XCTAssertEqual(nonZeroBasedSlice.startIndex, 1)
        XCTAssertEqual(
            try ProductionC1EndpointGrantLedgerState(
                persistenceCanonicalBytes: nonZeroBasedSlice
            ),
            ledger
        )
        var badMagic = canonical
        badMagic[0] ^= 0xff
        do {
            _ = try ProductionC1EndpointGrantLedgerState(
                persistenceCanonicalBytes: badMagic
            )
            XCTFail("Expected a non-ALC1EGL1 ledger magic to fail closed")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1CandidateCapabilityError,
                .malformedCanonical
            )
        }
        var revisionGap = canonical
        var impossibleRevision = UInt64(10).bigEndian
        let impossibleRevisionBytes = withUnsafeBytes(of: &impossibleRevision) { Data($0) }
        revisionGap.replaceSubrange(12..<20, with: impossibleRevisionBytes)
        do {
            _ = try ProductionC1EndpointGrantLedgerState(
                persistenceCanonicalBytes: revisionGap
            )
            XCTFail("Expected a non-contiguous ledger revision to be rejected")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1CandidateCapabilityError,
                .invalidValue
            )
        }
        XCTAssertNil(String(data: canonical, encoding: .utf8)?.range(
            of: "private-secret-canary"
        ))
        var legacyVersion = canonical
        var versionOne = UInt32(1).bigEndian
        let versionOneBytes = withUnsafeBytes(of: &versionOne) { Data($0) }
        legacyVersion.replaceSubrange(8..<12, with: versionOneBytes)
        do {
            _ = try ProductionC1EndpointGrantLedgerState(
                persistenceCanonicalBytes: legacyVersion
            )
            XCTFail("Expected the pre-object-26 ledger version to fail closed")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1CandidateCapabilityError,
                .malformedCanonical
            )
        }
        do {
            _ = try ProductionC1EndpointGrantLedgerState(
                persistenceCanonicalBytes: canonical + Data([0])
            )
            XCTFail("Expected trailing bytes to be rejected")
        } catch {
            XCTAssertEqual(
                error as? ProductionC1CandidateCapabilityError,
                .malformedCanonical
            )
        }
    }

    func testProductionSessionAdmissionPersistsConsumptionBeforeReturningPermitAndRejectsReplay()
        async throws
    {
        let fileURL = temporaryTrustedDevicesFileURL()
        let authority = try makeProductionPairAuthority(generation: 12, authorityRevision: 1)
        let state = try ProductionPairStateSnapshot(authority: authority, localRevision: 1)
        let device = TrustedDevice(
            id: "admission-device",
            name: "Admission",
            publicKeyBase64: "admission-public-key",
            pairedAt: Date(timeIntervalSince1970: 1_000)
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
        let admission = try makeProductionAdmission(for: state)

        let permit = try await store.admitProductionSecureSession(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            transcript: admission.transcript,
            routeAuthorization: admission.routeAuthorization
        )

        XCTAssertEqual(permit.pairAuthorityDigest, try authority.digestHex())
        XCTAssertEqual(permit.sessionId, admission.transcript.sessionId)
        XCTAssertEqual(permit.transcriptDigest, admission.transcript.digestHex)
        XCTAssertEqual(
            permit.routeAuthorizationDigest,
            try admission.routeAuthorization.digestHex()
        )
        XCTAssertEqual(permit.previousPairSnapshotDigest, try state.digestHex())
        let persistedAfterAdmission = try await store.load().first?.productionPairState
        XCTAssertEqual(persistedAfterAdmission?.localRevision, state.localRevision + 1)
        XCTAssertEqual(persistedAfterAdmission?.consumedEntries.count, 1)
        XCTAssertEqual(permit.pairSnapshotDigest, try persistedAfterAdmission?.digestHex())

        do {
            _ = try await store.admitProductionSecureSession(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                transcript: admission.transcript,
                routeAuthorization: admission.routeAuthorization
            )
            XCTFail("Expected a consumed session to fail closed as replay")
        } catch {
            XCTAssertEqual(error as? ProductionPairStateError, .replay)
        }
        let persistedAfterReplay = try await store.load().first?.productionPairState
        XCTAssertEqual(persistedAfterReplay, persistedAfterAdmission)
    }

    func testProductionSessionAdmissionDoesNotReturnPermitWhenDurableSaveFails() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let authority = try makeProductionPairAuthority(generation: 13, authorityRevision: 1)
        let state = try ProductionPairStateSnapshot(authority: authority, localRevision: 1)
        let device = TrustedDevice(
            id: "save-failure-device",
            name: "Save failure",
            publicKeyBase64: "save-failure-public-key",
            pairedAt: Date(timeIntervalSince1970: 1_050)
        )
        let bootstrapStore = TrustedDeviceStore(fileURL: fileURL)
        try await bootstrapStore.trust(device)
        try await bootstrapStore.applyVerifiedProductionPairTransition(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: nil,
                nextAuthority: authority
            )
        )
        let originalData = try Data(contentsOf: fileURL)
        let constrainedStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            limits: testLimits(maxStoreBytes: originalData.count)
        )
        let admission = try makeProductionAdmission(for: state)

        do {
            _ = try await constrainedStore.admitProductionSecureSession(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                transcript: admission.transcript,
                routeAuthorization: admission.routeAuthorization
            )
            XCTFail("Expected durable save failure before permit return")
        } catch {
            XCTAssertNotNil(error as? TrustedDeviceStoreResourceLimitError)
        }

        XCTAssertEqual(try Data(contentsOf: fileURL), originalData)
        let persisted = try await TrustedDeviceStore(fileURL: fileURL).load()
        XCTAssertEqual(persisted.first?.productionPairState, state)
    }

    func testProductionSessionAdmissionWithholdsPermitOnExactReadbackTamper() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let authority = try makeProductionPairAuthority(generation: 14, authorityRevision: 1)
        let state = try ProductionPairStateSnapshot(authority: authority, localRevision: 1)
        let device = TrustedDevice(
            id: "readback-tamper-device",
            name: "Readback tamper",
            publicKeyBase64: "readback-tamper-public-key",
            pairedAt: Date(timeIntervalSince1970: 1_075)
        )
        let bootstrapStore = TrustedDeviceStore(fileURL: fileURL)
        try await bootstrapStore.trust(device)
        try await bootstrapStore.applyVerifiedProductionPairTransition(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: nil,
                nextAuthority: authority
            )
        )
        let originalData = try Data(contentsOf: fileURL)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didCommitBeforeReadback: { url in try? originalData.write(to: url) }
            )
        )
        let admission = try makeProductionAdmission(for: state)

        do {
            _ = try await store.admitProductionSecureSession(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                transcript: admission.transcript,
                routeAuthorization: admission.routeAuthorization
            )
            XCTFail("Expected exact-byte rollback tamper to withhold the permit")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreError,
                .productionPairAdmissionReadbackMismatch
            )
        }
        XCTAssertEqual(try Data(contentsOf: fileURL), originalData)
    }

    func testVerifiedC1AdmissionReturnsBoundPermitOnlyAfterExactReadback() async throws {
        let now: UInt64 = 1_000_000
        let expiresAtMs = now + 200
        let fixture = try makeVerifiedC1AdmissionFixture(nowMs: now, expiresAtMs: expiresAtMs)
        let fileURL = temporaryTrustedDevicesFileURL()
        let device = TrustedDevice(
            id: "verified-c1-admission",
            name: "Verified C1 admission",
            publicKeyBase64: "verified-c1-public-key",
            pairedAt: Date(timeIntervalSince1970: 1_100)
        )
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            trustedNowEpochMillis: { now }
        )
        try await store.trust(device)
        try await store.applyVerifiedProductionPairTransition(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: nil,
                nextAuthority: fixture.state.authority
            )
        )

        let permit = try await store.admitVerifiedProductionC1SecureSession(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            binding: fixture.binding
        )

        XCTAssertEqual(permit.pairAuthorityDigest, try fixture.state.authority.digestHex())
        XCTAssertEqual(permit.sessionId, fixture.binding.transcript.sessionId)
        XCTAssertEqual(permit.transcriptDigest, fixture.binding.transcript.digestHex)
        XCTAssertEqual(permit.routeAuthorizationDigest, fixture.binding.authorization.digestHex)
        XCTAssertEqual(permit.routeCapabilityDigest, fixture.binding.plan.capabilityDigest)
        XCTAssertEqual(permit.routePlanClaimsDigest, fixture.binding.plan.claimsDigest)
        XCTAssertEqual(
            permit.connectorInputCommitmentDigest,
            fixture.binding.connectorInput.commitmentDigest
        )
        XCTAssertEqual(permit.previousPairSnapshotDigest, try fixture.state.digestHex())
        XCTAssertEqual(permit.effectiveNotBeforeMs, now - 10)
        XCTAssertEqual(permit.expiresAtMs, expiresAtMs)
        let persisted = try await store.load()
        let persistedSnapshot = try XCTUnwrap(persisted.first?.productionPairState)
        XCTAssertEqual(persistedSnapshot.localRevision, 2)
        XCTAssertEqual(permit.pairSnapshotDigest, try persistedSnapshot.digestHex())
    }

    func testVerifiedC1AdmissionExpiryAfterPersistenceReturnsNoPermitAndReplayStaysConsumed()
        async throws
    {
        let now: UInt64 = 1_000_000
        let expiresAtMs = now + 200
        let fixture = try makeVerifiedC1AdmissionFixture(nowMs: now, expiresAtMs: expiresAtMs)
        let fileURL = temporaryTrustedDevicesFileURL()
        let device = TrustedDevice(
            id: "verified-c1-expiry",
            name: "Verified C1 expiry",
            publicKeyBase64: "verified-c1-expiry-public-key",
            pairedAt: Date(timeIntervalSince1970: 1_200)
        )
        let clock = LockedBox<UInt64>()
        clock.set(now)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didCommitBeforeReadback: { _ in clock.set(expiresAtMs) }
            ),
            trustedNowEpochMillis: { clock.get() ?? 0 }
        )
        try await store.trust(device)
        try await store.applyVerifiedProductionPairTransition(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: nil,
                nextAuthority: fixture.state.authority
            )
        )
        let originalBytes = try Data(contentsOf: fileURL)

        do {
            _ = try await store.admitVerifiedProductionC1SecureSession(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                binding: fixture.binding
            )
            XCTFail("Expected post-persistence expiry to withhold the live permit")
        } catch {
            XCTAssertEqual(error as? ProductionC1Error, .expired)
        }

        XCTAssertNotEqual(try Data(contentsOf: fileURL), originalBytes)
        let persisted = try await store.load()
        XCTAssertEqual(persisted.first?.productionPairState?.localRevision, 2)
        clock.set(now)
        do {
            _ = try await store.admitVerifiedProductionC1SecureSession(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                binding: fixture.binding
            )
            XCTFail("Expected the persisted consumption to remain non-authorizing on retry")
        } catch {
            XCTAssertEqual(error as? ProductionPairStateError, .replay)
        }
    }

    func testVerifiedC1AdmissionPostReadbackClockRegressionWithholdsPermitAndReplayStaysConsumed()
        async throws
    {
        let now: UInt64 = 1_000_000
        let fixture = try makeVerifiedC1AdmissionFixture(
            nowMs: now,
            expiresAtMs: now + 200
        )
        let fileURL = temporaryTrustedDevicesFileURL()
        let device = TrustedDevice(
            id: "verified-c1-clock-regression",
            name: "Verified C1 clock regression",
            publicKeyBase64: "verified-c1-clock-regression-public-key",
            pairedAt: Date(timeIntervalSince1970: 1_250)
        )
        let clock = LockedBox<UInt64>()
        clock.set(now)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didCommitBeforeReadback: { _ in clock.set(now - 1) }
            ),
            trustedNowEpochMillis: { clock.get() ?? 0 }
        )
        try await store.trust(device)
        try await store.applyVerifiedProductionPairTransition(
            deviceID: device.id,
            expectedPublicKeyBase64: device.publicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: nil,
                nextAuthority: fixture.state.authority
            )
        )

        do {
            _ = try await store.admitVerifiedProductionC1SecureSession(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                binding: fixture.binding
            )
            XCTFail("Expected post-readback trusted-clock regression to withhold the permit")
        } catch {
            XCTAssertEqual(error as? TrustedDeviceStoreError, .trustedClockRegression)
        }

        let persisted = try await store.load()
        XCTAssertEqual(persisted.first?.productionPairState?.localRevision, 2)
        clock.set(now)
        do {
            _ = try await store.admitVerifiedProductionC1SecureSession(
                deviceID: device.id,
                expectedPublicKeyBase64: device.publicKeyBase64,
                binding: fixture.binding
            )
            XCTFail("Expected the durable tombstone to remain a replay after clock regression")
        } catch {
            XCTAssertEqual(error as? ProductionPairStateError, .replay)
        }
    }

    func testTrustCreatesStoreWithOwnerOnlyPermissions() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let store = TrustedDeviceStore(fileURL: fileURL)
        let device = makeDevice(id: "device-1", name: "Phone", timestamp: 1_000)

        try await store.trust(device)
        let loaded = try await store.load()

        XCTAssertEqual(loaded, [device])
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
        XCTAssertEqual(try filePermissions(at: lockURL(for: fileURL)), 0o600)
        XCTAssertEqual(try directoryPermissions(at: fileURL.deletingLastPathComponent()), 0o700)
    }

    func testLoadCorrectsBroadPermissionsWithoutDroppingTrustedDevices() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let directoryURL = fileURL.deletingLastPathComponent()
        let lockURL = lockURL(for: fileURL)
        let device = makeDevice(id: "device-1", name: "Phone", timestamp: 2_000)
        try await TrustedDeviceStore(fileURL: fileURL).trust(device)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: directoryURL.path)
        try FileManager.default.setAttributes([.posixPermissions: 0o644], ofItemAtPath: fileURL.path)
        try FileManager.default.setAttributes([.posixPermissions: 0o666], ofItemAtPath: lockURL.path)

        let loaded = try await TrustedDeviceStore(fileURL: fileURL).load()

        XCTAssertEqual(loaded, [device])
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
        XCTAssertEqual(try filePermissions(at: lockURL), 0o600)
        XCTAssertEqual(try directoryPermissions(at: directoryURL), 0o700)
    }

    func testRemoveMaintainsOwnerOnlyPermissions() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let directoryURL = fileURL.deletingLastPathComponent()
        let store = TrustedDeviceStore(fileURL: fileURL)
        try await store.trust(makeDevice(id: "device-1", name: "Phone", timestamp: 3_000))

        try await store.remove(deviceID: "device-1")
        let loaded = try await store.load()

        XCTAssertEqual(loaded, [])
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
        XCTAssertEqual(try filePermissions(at: lockURL(for: fileURL)), 0o600)
        XCTAssertEqual(try directoryPermissions(at: directoryURL), 0o700)
    }

    func testConcurrentLaterRevokeWinsOverEarlierStaleUpsertAcrossStoreInstances() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let original = makeDevice(id: "device-1", name: "Phone", timestamp: 4_000)
        let staleUpsert = TrustedDevice(
            id: original.id,
            name: "Stale phone name",
            publicKeyBase64: original.publicKeyBase64,
            pairedAt: original.pairedAt
        )
        try await TrustedDeviceStore(fileURL: fileURL).trust(original)

        let firstSnapshotLoaded = DispatchSemaphore(value: 0)
        let releaseFirstMutation = DispatchSemaphore(value: 0)
        let secondMutationContended = DispatchSemaphore(value: 0)
        let staleStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didLoadMutationSnapshot: {
                    firstSnapshotLoaded.signal()
                    releaseFirstMutation.wait()
                }
            )
        )
        let revokingStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didObserveMutationLockContention: { secondMutationContended.signal() }
            )
        )
        var firstMutationReleased = false
        defer {
            if !firstMutationReleased { releaseFirstMutation.signal() }
        }

        let staleTask = Task { try await staleStore.trust(staleUpsert) }
        XCTAssertEqual(firstSnapshotLoaded.wait(timeout: .now() + 2), .success)
        let revokeTask = Task { try await revokingStore.remove(deviceID: original.id) }
        XCTAssertEqual(secondMutationContended.wait(timeout: .now() + 2), .success)

        firstMutationReleased = true
        releaseFirstMutation.signal()
        try await staleTask.value
        try await revokeTask.value

        let finalDevices = try await TrustedDeviceStore(fileURL: fileURL).load()
        XCTAssertEqual(finalDevices, [])
    }

    func testConcurrentUpsertsAcrossStoreInstancesPreserveBothDevices() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let first = makeDevice(id: "device-a", name: "Alpha", timestamp: 5_000)
        let second = makeDevice(id: "device-b", name: "Beta", timestamp: 6_000)
        let firstSnapshotLoaded = DispatchSemaphore(value: 0)
        let releaseFirstMutation = DispatchSemaphore(value: 0)
        let secondMutationContended = DispatchSemaphore(value: 0)
        let firstStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didLoadMutationSnapshot: {
                    firstSnapshotLoaded.signal()
                    releaseFirstMutation.wait()
                }
            )
        )
        let secondStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didObserveMutationLockContention: { secondMutationContended.signal() }
            )
        )
        var firstMutationReleased = false
        defer {
            if !firstMutationReleased { releaseFirstMutation.signal() }
        }

        let firstTask = Task { try await firstStore.trust(first) }
        XCTAssertEqual(firstSnapshotLoaded.wait(timeout: .now() + 2), .success)
        let secondTask = Task { try await secondStore.trust(second) }
        XCTAssertEqual(secondMutationContended.wait(timeout: .now() + 2), .success)

        firstMutationReleased = true
        releaseFirstMutation.signal()
        try await firstTask.value
        try await secondTask.value

        let finalDevices = try await TrustedDeviceStore(fileURL: fileURL).load()
        XCTAssertEqual(finalDevices, [first, second])
    }

    func testSnapshotHoldsSharedLockUntilOperationCompletesThenRevokeTakesEffect() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let device = makeDevice(id: "device-snapshot", name: "Snapshot", timestamp: 6_500)
        try await TrustedDeviceStore(fileURL: fileURL).trust(device)

        let snapshotEntered = DispatchSemaphore(value: 0)
        let releaseSnapshot = DispatchSemaphore(value: 0)
        let revokeContended = DispatchSemaphore(value: 0)
        let revokeCompleted = DispatchSemaphore(value: 0)
        let snapshotStore = TrustedDeviceStore(fileURL: fileURL)
        let revokingStore = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didObserveMutationLockContention: { revokeContended.signal() }
            )
        )
        var snapshotReleased = false
        defer {
            if !snapshotReleased { releaseSnapshot.signal() }
        }

        let snapshotTask = Task {
            try await snapshotStore.withTrustedDeviceSnapshot(deviceID: device.id) { trustedDevice in
                snapshotEntered.signal()
                releaseSnapshot.wait()
                return trustedDevice
            }
        }
        XCTAssertEqual(snapshotEntered.wait(timeout: .now() + 2), .success)

        let revokeTask = Task {
            defer { revokeCompleted.signal() }
            try await revokingStore.remove(deviceID: device.id)
        }
        XCTAssertEqual(revokeContended.wait(timeout: .now() + 2), .success)
        XCTAssertEqual(revokeCompleted.wait(timeout: .now() + 0.05), .timedOut)

        snapshotReleased = true
        releaseSnapshot.signal()
        let snapshotDevice = try await snapshotTask.value
        XCTAssertEqual(snapshotDevice, device)
        try await revokeTask.value
        let finalStore = TrustedDeviceStore(fileURL: fileURL)
        let finalDevices = try await finalStore.load()
        XCTAssertEqual(finalDevices, [])
    }

    func testAtomicReplacementKeepsOldCompleteStoreVisibleUntilDurableTempIsReady() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let original = makeDevice(id: "device-a", name: "Alpha", timestamp: 7_000)
        let added = makeDevice(id: "device-b", name: "Beta", timestamp: 8_000)
        try await TrustedDeviceStore(fileURL: fileURL).trust(original)

        let replacementPrepared = DispatchSemaphore(value: 0)
        let releaseReplacement = DispatchSemaphore(value: 0)
        let temporaryURL = LockedBox<URL>()
        let writer = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didPrepareAtomicReplacement: { url in
                    temporaryURL.set(url)
                    replacementPrepared.signal()
                    releaseReplacement.wait()
                }
            )
        )
        var replacementReleased = false
        defer {
            if !replacementReleased { releaseReplacement.signal() }
        }

        let writeTask = Task { try await writer.trust(added) }
        XCTAssertEqual(replacementPrepared.wait(timeout: .now() + 2), .success)
        let preparedURL = try XCTUnwrap(temporaryURL.get())

        XCTAssertEqual(try decodeDevices(at: fileURL), [original])
        XCTAssertEqual(try decodeDevices(at: preparedURL), [original, added])
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
        XCTAssertEqual(try filePermissions(at: preparedURL), 0o600)

        replacementReleased = true
        releaseReplacement.signal()
        try await writeTask.value

        XCTAssertEqual(try decodeDevices(at: fileURL), [original, added])
        XCTAssertFalse(FileManager.default.fileExists(atPath: preparedURL.path))
    }

    func testMutationFailsClosedWhenLockCannotBeAcquiredBeforeDeadline() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let holderLoadedSnapshot = DispatchSemaphore(value: 0)
        let releaseHolder = DispatchSemaphore(value: 0)
        let holder = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didLoadMutationSnapshot: {
                    holderLoadedSnapshot.signal()
                    releaseHolder.wait()
                }
            )
        )
        let contender = TrustedDeviceStore(
            fileURL: fileURL,
            lockTimeoutNanoseconds: 25_000_000,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks()
        )
        var holderReleased = false
        defer {
            if !holderReleased { releaseHolder.signal() }
        }

        let holderTask = Task {
            try await holder.trust(makeDevice(id: "device-a", name: "Alpha", timestamp: 9_000))
        }
        XCTAssertEqual(holderLoadedSnapshot.wait(timeout: .now() + 2), .success)

        do {
            try await contender.trust(makeDevice(id: "device-b", name: "Beta", timestamp: 10_000))
            XCTFail("Expected bounded lock acquisition to fail closed")
        } catch {
            XCTAssertEqual(error as? TrustedDeviceStoreError, .lockAcquisitionTimedOut)
        }

        holderReleased = true
        releaseHolder.signal()
        try await holderTask.value
        let finalDeviceIDs = try await TrustedDeviceStore(fileURL: fileURL).load().map(\.id)
        XCTAssertEqual(finalDeviceIDs, ["device-a"])
    }

    func testMutationRejectsSymlinkStoreWithoutChangingTarget() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let directoryURL = fileURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        let targetURL = directoryURL.appendingPathComponent("outside.json")
        let originalData = Data("external".utf8)
        try originalData.write(to: targetURL)
        try FileManager.default.createSymbolicLink(at: fileURL, withDestinationURL: targetURL)

        do {
            try await TrustedDeviceStore(fileURL: fileURL).trust(
                makeDevice(id: "device-a", name: "Alpha", timestamp: 11_000)
            )
            XCTFail("Expected a symlink store path to fail closed")
        } catch {
            XCTAssertEqual(error as? TrustedDeviceStoreError, .unsafeStoreFile)
        }

        XCTAssertEqual(try Data(contentsOf: targetURL), originalData)
    }

    func testStoreByteLimitAcceptsExactBytesAndRejectsLimitPlusOneBeforeAllocation() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let limits = testLimits(maxStoreBytes: 64)
        let exactData = Data("[]".utf8) + Data(repeating: 0x20, count: 62)
        XCTAssertEqual(exactData.count, limits.maxStoreBytes)
        try exactData.write(to: fileURL)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            limits: limits
        )

        let exactLoaded = try await store.load()
        XCTAssertEqual(exactLoaded, [])

        let oversizedData = exactData + Data([0x20])
        try oversizedData.write(to: fileURL)
        do {
            _ = try await store.load()
            XCTFail("Expected the store byte ceiling to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreResourceLimitError,
                TrustedDeviceStoreResourceLimitError(
                    resource: "trusted device store bytes",
                    limit: 64,
                    actual: 65
                )
            )
        }
    }

    func testFieldLimitsAcceptExactUTF8BytesAndRejectLimitPlusOneOnMutationAndRead() async throws {
        let limits = testLimits(
            maxIdentifierUTF8Bytes: 4,
            maxNameUTF8Bytes: 4,
            maxPublicKeyUTF8Bytes: 4
        )
        let fileURL = temporaryTrustedDevicesFileURL()
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            limits: limits
        )
        let exactDevice = TrustedDevice(
            id: "id12",
            name: "éé",
            publicKeyBase64: "key1",
            pairedAt: Date(timeIntervalSince1970: 12_000)
        )

        try await store.trust(exactDevice)
        let exactLoaded = try await store.load()
        XCTAssertEqual(exactLoaded, [exactDevice])

        let oversizedFields: [(TrustedDevice, TrustedDeviceStoreResourceLimitError)] = [
            (
                TrustedDevice(
                    id: "id123",
                    name: exactDevice.name,
                    publicKeyBase64: exactDevice.publicKeyBase64,
                    pairedAt: exactDevice.pairedAt
                ),
                TrustedDeviceStoreResourceLimitError(
                    resource: "device identifier UTF-8 bytes",
                    limit: 4,
                    actual: 5
                )
            ),
            (
                TrustedDevice(
                    id: exactDevice.id,
                    name: "ééx",
                    publicKeyBase64: exactDevice.publicKeyBase64,
                    pairedAt: exactDevice.pairedAt
                ),
                TrustedDeviceStoreResourceLimitError(
                    resource: "device name UTF-8 bytes",
                    limit: 4,
                    actual: 5
                )
            ),
            (
                TrustedDevice(
                    id: exactDevice.id,
                    name: exactDevice.name,
                    publicKeyBase64: "key12",
                    pairedAt: exactDevice.pairedAt
                ),
                TrustedDeviceStoreResourceLimitError(
                    resource: "device public key UTF-8 bytes",
                    limit: 4,
                    actual: 5
                )
            ),
        ]
        for (device, expectedError) in oversizedFields {
            do {
                try await store.trust(device)
                XCTFail("Expected oversized trusted-device field to fail closed")
            } catch {
                XCTAssertEqual(error as? TrustedDeviceStoreResourceLimitError, expectedError)
            }
        }
        let loadedAfterRejectedMutations = try await store.load()
        XCTAssertEqual(loadedAfterRejectedMutations, [exactDevice])

        let invalidReadDevice = TrustedDevice(
            id: exactDevice.id,
            name: "ééx",
            publicKeyBase64: exactDevice.publicKeyBase64,
            pairedAt: exactDevice.pairedAt
        )
        try encodeDevices([invalidReadDevice]).write(to: fileURL)
        do {
            _ = try await store.load()
            XCTFail("Expected oversized decoded field to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreResourceLimitError,
                TrustedDeviceStoreResourceLimitError(
                    resource: "device name UTF-8 bytes",
                    limit: 4,
                    actual: 5
                )
            )
        }
    }

    func testRepeatedTrustHonorsRowLimitAndReplacementAtCapacity() async throws {
        let limits = testLimits(maxDevices: 2)
        let fileURL = temporaryTrustedDevicesFileURL()
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            limits: limits
        )
        let first = makeDevice(id: "one", name: "One", timestamp: 13_000)
        let second = makeDevice(id: "two", name: "Two", timestamp: 14_000)
        let replacement = makeDevice(id: "one", name: "One replacement", timestamp: 15_000)

        try await store.trust(first)
        try await store.trust(second)
        try await store.trust(replacement)
        let loadedAtCapacity = try await store.load()
        XCTAssertEqual(loadedAtCapacity, [replacement, second])

        do {
            try await store.trust(makeDevice(id: "three", name: "Three", timestamp: 16_000))
            XCTFail("Expected repeated trust beyond the row ceiling to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreResourceLimitError,
                TrustedDeviceStoreResourceLimitError(
                    resource: "trusted device rows",
                    limit: 2,
                    actual: 3
                )
            )
        }
        let loadedAfterOverflow = try await store.load()
        XCTAssertEqual(loadedAfterOverflow, [replacement, second])
    }

    func testLoadRejectsRowLimitPlusOneBeforeBuildingUnboundedArray() async throws {
        let limits = testLimits(maxDevices: 2)
        let fileURL = temporaryTrustedDevicesFileURL()
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let devices = [
            makeDevice(id: "one", name: "One", timestamp: 17_000),
            makeDevice(id: "two", name: "Two", timestamp: 18_000),
            makeDevice(id: "three", name: "Three", timestamp: 19_000),
        ]
        try encodeDevices(devices).write(to: fileURL)
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(),
            limits: limits
        )

        do {
            _ = try await store.load()
            XCTFail("Expected decoded rows above the ceiling to fail closed")
        } catch {
            XCTAssertEqual(
                error as? TrustedDeviceStoreResourceLimitError,
                TrustedDeviceStoreResourceLimitError(
                    resource: "trusted device rows",
                    limit: 2,
                    actual: 3
                )
            )
        }
    }

    func testLoadAndSnapshotLookupRejectDuplicateDeviceIdentifiersWithDifferentKeys() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let originalData = try writeAmbiguousStore(to: fileURL)
        let store = TrustedDeviceStore(fileURL: fileURL)

        do {
            _ = try await store.load()
            XCTFail("Expected duplicate trusted-device identifiers to fail closed")
        } catch {
            XCTAssertEqual(error as? TrustedDeviceStoreError, .ambiguousDeviceIdentifier)
        }
        XCTAssertEqual(try Data(contentsOf: fileURL), originalData)

        let lookupWasInvoked = LockedBox<Bool>()
        do {
            _ = try await store.withTrustedDeviceSnapshot(deviceID: "duplicate-device") { device in
                lookupWasInvoked.set(true)
                return device?.publicKeyBase64
            }
            XCTFail("Expected ambiguous snapshot lookup to fail closed")
        } catch {
            XCTAssertEqual(error as? TrustedDeviceStoreError, .ambiguousDeviceIdentifier)
        }
        XCTAssertNil(lookupWasInvoked.get())
        XCTAssertEqual(try Data(contentsOf: fileURL), originalData)
    }

    func testTrustAndRemoveRejectDuplicateDeviceIdentifiersWithoutRewritingAuthority() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let originalData = try writeAmbiguousStore(to: fileURL)
        let store = TrustedDeviceStore(fileURL: fileURL)
        let replacement = TrustedDevice(
            id: "duplicate-device",
            name: "Replacement",
            publicKeyBase64: "replacement-public-key",
            pairedAt: Date(timeIntervalSince1970: 22_000)
        )

        do {
            try await store.trust(replacement)
            XCTFail("Expected trust to reject ambiguous authority")
        } catch {
            XCTAssertEqual(error as? TrustedDeviceStoreError, .ambiguousDeviceIdentifier)
        }
        XCTAssertEqual(try Data(contentsOf: fileURL), originalData)

        do {
            try await store.remove(deviceID: "duplicate-device")
            XCTFail("Expected remove to reject ambiguous authority")
        } catch {
            XCTAssertEqual(error as? TrustedDeviceStoreError, .ambiguousDeviceIdentifier)
        }
        XCTAssertEqual(try Data(contentsOf: fileURL), originalData)
    }

    func testLoadAndMutationRemoveExtendedACLsFromDirectoryLockStoreAndTemporaryFile() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let directoryURL = fileURL.deletingLastPathComponent()
        let lockFileURL = lockURL(for: fileURL)
        let first = makeDevice(id: "device-1", name: "Phone", timestamp: 20_000)
        try await TrustedDeviceStore(fileURL: fileURL).trust(first)
        try addBroadReadACL(at: directoryURL)
        try addBroadReadACL(at: lockFileURL)
        try addBroadReadACL(at: fileURL)
        XCTAssertGreaterThan(try extendedACLCount(at: directoryURL), 0)
        XCTAssertGreaterThan(try extendedACLCount(at: lockFileURL), 0)
        XCTAssertGreaterThan(try extendedACLCount(at: fileURL), 0)

        let loadedAfterACLRepair = try await TrustedDeviceStore(fileURL: fileURL).load()
        XCTAssertEqual(loadedAfterACLRepair, [first])
        XCTAssertEqual(try extendedACLCount(at: directoryURL), 0)
        XCTAssertEqual(try extendedACLCount(at: lockFileURL), 0)
        XCTAssertEqual(try extendedACLCount(at: fileURL), 0)

        let injectedTemporaryACLCount = LockedBox<Int>()
        let injectionError = LockedBox<String>()
        let store = TrustedDeviceStore(
            fileURL: fileURL,
            synchronizationHooks: TrustedDeviceStoreSynchronizationHooks(
                didCreateTemporaryFile: { temporaryURL in
                    do {
                        try addBroadReadACL(at: temporaryURL)
                        injectedTemporaryACLCount.set(try extendedACLCount(at: temporaryURL))
                    } catch {
                        injectionError.set(String(describing: error))
                    }
                }
            )
        )
        try await store.trust(makeDevice(id: "device-2", name: "Tablet", timestamp: 21_000))

        XCTAssertNil(injectionError.get())
        XCTAssertGreaterThan(injectedTemporaryACLCount.get() ?? 0, 0)
        XCTAssertEqual(try extendedACLCount(at: fileURL), 0)
        XCTAssertEqual(try extendedACLCount(at: lockFileURL), 0)
        XCTAssertEqual(try extendedACLCount(at: directoryURL), 0)
    }

    private func bootstrapEndpointCommitStore(
        at fileURL: URL,
        effectiveNotBeforeMs: UInt64 = 0,
        expiresAtMs: UInt64 = 4_102_444_800_000
    ) throws -> (
        device: TrustedDevice,
        preparation: ProductionC1EndpointGrantAdmissionPreparation
    ) {
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let pair = try makeProductionPairState(generation: 30, authorityRevision: 1)
        let device = TrustedDevice(
            id: "endpoint-device",
            name: "Endpoint",
            publicKeyBase64: "endpoint-public-key",
            pairedAt: Date(timeIntervalSince1970: 30_000),
            productionPairState: pair
        )
        try encodeDevices([device]).write(to: fileURL)
        let ledger = try ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest: pair.authority.digestHex(),
            pairLocalRevision: pair.localRevision,
            remainingGrants: UInt64(
                ProductionC1EndpointLedgerPersistenceContract.maximumEntries
            ),
            retentionLimit: UInt32(
                ProductionC1EndpointLedgerPersistenceContract.maximumEntries
            )
        )
        return (
            device,
            try makeAppliedEndpointPreparation(
                currentLedger: ledger,
                currentPair: pair,
                digit: "7",
                effectiveNotBeforeMs: effectiveNotBeforeMs,
                expiresAtMs: expiresAtMs
            )
        )
    }

    private func makeAppliedEndpointPreparation(
        currentLedger: ProductionC1EndpointGrantLedgerState,
        currentPair: ProductionPairStateSnapshot,
        digit: Character,
        effectiveNotBeforeMs: UInt64 = 0,
        expiresAtMs: UInt64 = 4_102_444_800_000
    ) throws -> ProductionC1EndpointGrantAdmissionPreparation {
        let sessionID = String(repeating: String(digit), count: 32)
        let transcriptDigest = String(repeating: String(digit), count: 64)
        let nextPair = try ProductionPairStateSnapshot(
            authority: currentPair.authority,
            localRevision: currentPair.localRevision + 1,
            consumedEntries: currentPair.consumedEntries + [
                try ProductionPairConsumedSession(
                    sessionId: sessionID,
                    transcriptDigest: transcriptDigest
                ),
            ],
            transitionHistory: currentPair.transitionHistory
        )
        let entry = ProductionC1EndpointGrantEntry(
            admissionId: String(repeating: String(digit), count: 64),
            bindingDigest: String(repeating: String(digit), count: 64),
            routeGrantDigest: String(repeating: String(digit), count: 64),
            sessionId: sessionID,
            transcriptDigest: transcriptDigest,
            routeAuthorizationDigest: String(repeating: String(digit), count: 64),
            grantAuthorizationDigest: String(repeating: "a", count: 64),
            connectorInputCommitmentDigest: String(repeating: String(digit), count: 64),
            pairSnapshotDigest: try nextPair.digestHex(),
            committedRevision: currentLedger.revision + 1
        )
        let nextLedger = try ProductionC1EndpointGrantLedgerState(
            revision: currentLedger.revision + 1,
            pairAuthorityDigest: currentLedger.pairAuthorityDigest,
            pairLocalRevision: nextPair.localRevision,
            remainingGrants: currentLedger.remainingGrants - 1,
            retentionLimit: currentLedger.retentionLimit,
            entries: currentLedger.entries + [entry]
        )
        let currentCompound = try ProductionC1EndpointCompoundRecord(
            grantLedger: currentLedger,
            pairSnapshot: currentPair
        )
        let nextCompound = try ProductionC1EndpointCompoundRecord(
            grantLedger: nextLedger,
            pairSnapshot: nextPair
        )
        return try ProductionC1EndpointGrantAdmissionPreparation(
            disposition: .applied,
            sessionID: entry.sessionId,
            routeAuthorizationDigest: entry.routeAuthorizationDigest,
            grantAuthorizationDigest: entry.grantAuthorizationDigest,
            pairAuthorityDigest: nextLedger.pairAuthorityDigest,
            effectiveNotBeforeMs: effectiveNotBeforeMs,
            expiresAtMs: expiresAtMs,
            expectedRevision: currentLedger.revision,
            expectedSnapshotDigest: try currentLedger.snapshotDigestHex(),
            expectedPairSnapshotDigest: try currentPair.digestHex(),
            nextState: nextLedger,
            nextPairSnapshot: nextPair,
            expectedCompoundDigest: try currentCompound.digestHex(),
            nextCompoundRecord: nextCompound,
            entry: entry
        )
    }

    private func endpointPreparation(
        currentLedger: ProductionC1EndpointGrantLedgerState,
        currentPair: ProductionPairStateSnapshot,
        entry: ProductionC1EndpointGrantEntry,
        disposition: ProductionC1CandidateCASDisposition,
        effectiveNotBeforeMs: UInt64 = 0,
        expiresAtMs: UInt64 = 4_102_444_800_000
    ) throws -> ProductionC1EndpointGrantAdmissionPreparation {
        let compound = try ProductionC1EndpointCompoundRecord(
            grantLedger: currentLedger,
            pairSnapshot: currentPair
        )
        return try ProductionC1EndpointGrantAdmissionPreparation(
            disposition: disposition,
            sessionID: entry.sessionId,
            routeAuthorizationDigest: entry.routeAuthorizationDigest,
            grantAuthorizationDigest: entry.grantAuthorizationDigest,
            pairAuthorityDigest: currentLedger.pairAuthorityDigest,
            effectiveNotBeforeMs: effectiveNotBeforeMs,
            expiresAtMs: expiresAtMs,
            expectedRevision: currentLedger.revision,
            expectedSnapshotDigest: try currentLedger.snapshotDigestHex(),
            expectedPairSnapshotDigest: try currentPair.digestHex(),
            nextState: currentLedger,
            nextPairSnapshot: currentPair,
            expectedCompoundDigest: try compound.digestHex(),
            nextCompoundRecord: compound,
            entry: entry
        )
    }

    private func makeDevice(
        id: String,
        name: String,
        timestamp: TimeInterval
    ) -> TrustedDevice {
        TrustedDevice(
            id: id,
            name: name,
            publicKeyBase64: "public-key-\(id)",
            pairedAt: Date(timeIntervalSince1970: timestamp)
        )
    }

    private func makeProductionPairState(
        generation: UInt64,
        authorityRevision: UInt64
    ) throws -> ProductionPairStateSnapshot {
        let authority = try makeProductionPairAuthority(
            generation: generation,
            authorityRevision: authorityRevision
        )
        return try ProductionPairStateSnapshot(
            authority: authority,
            localRevision: authorityRevision
        )
    }

    private func makeProductionPairAuthority(
        generation: UInt64,
        authorityRevision: UInt64,
        transitionDigit: Character = "4"
    ) throws -> ProductionPairAuthorityState {
        try ProductionPairAuthorityState(
            pairBindingDigest: String(repeating: "1", count: 64),
            pairEpoch: 2,
            clientIdentityFingerprint: String(repeating: "2", count: 64),
            runtimeIdentityFingerprint: String(repeating: "3", count: 64),
            generation: generation,
            serviceConfigVersion: 4,
            keysetVersion: 5,
            revocationCounter: 0,
            protocolFloor: 1,
            status: .active,
            transitionId: String(repeating: transitionDigit, count: 64),
            transitionRequestDigest: String(repeating: "5", count: 64),
            acceptedReceiptDigest: String(repeating: "6", count: 64),
            authorityRevision: authorityRevision
        )
    }

    private func makeProductionAdmission(
        for state: ProductionPairStateSnapshot
    ) throws -> (
        transcript: ProductionSecureSessionTranscript,
        routeAuthorization: ProductionRouteAuthorization
    ) {
        let authority = state.authority
        let routeAuthorization = ProductionRouteAuthorization.turnRelay(
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            generation: authority.generation,
            leaseDigest: String(repeating: "a", count: 64),
            allocationDigest: String(repeating: "b", count: 64),
            pathValidationReceiptDigest: String(repeating: "c", count: 64)
        )
        let clientKey = P256.KeyAgreement.PrivateKey()
        let runtimeKey = P256.KeyAgreement.PrivateKey()
        let transcript = try ProductionSecureSessionTranscript(
            sessionId: String(repeating: "d", count: 32),
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: clientKey.publicKey.x963Representation,
            runtimeEphemeralPublicKey: runtimeKey.publicKey.x963Representation,
            clientNonce: String(repeating: "e", count: 32),
            runtimeNonce: String(repeating: "f", count: 32),
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            keysetVersion: authority.keysetVersion,
            revocationCounter: authority.revocationCounter,
            routeKind: routeAuthorization.kind,
            routeAuthDigest: try routeAuthorization.digestHex()
        )
        return (transcript, routeAuthorization)
    }

    private struct VerifiedC1AdmissionFixture {
        let state: ProductionPairStateSnapshot
        let binding: VerifiedProductionC1TranscriptBinding
    }

    private func makeVerifiedC1AdmissionFixture(
        nowMs: UInt64,
        expiresAtMs: UInt64
    ) throws -> VerifiedC1AdmissionFixture {
        let serviceIdDigest = String(repeating: "a", count: 64)
        let rootKey = try deterministicSigningKey(41)
        let routeKey = try deterministicSigningKey(42)
        let routeKeyId = signingKeyId(routeKey.publicKey)
        let delegatedRouteKey = try ProductionC1DelegatedKey(
            keysetVersion: 1,
            keyId: routeKeyId,
            purposes: [.routeCapability],
            notBeforeMs: nowMs - 100,
            expiresAtMs: expiresAtMs + 1_000,
            publicKeyX963: routeKey.publicKey.x963Representation
        )
        let keyset = try ProductionC1ServiceKeyset.signed(
            serviceIdDigest: serviceIdDigest,
            keysetVersion: 1,
            previousKeysetDigest: nil,
            issuedAtMs: nowMs - 100,
            expiresAtMs: expiresAtMs + 1_000,
            delegatedKeys: [delegatedRouteKey],
            using: rootKey
        )
        let verifiedKeyset = try ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            expectedServiceIdDigest: serviceIdDigest,
            pinnedRootPublicKey: rootKey.publicKey,
            minimumAcceptedKeysetVersion: 1,
            nowMs: nowMs
        )
        let authority = try ProductionPairAuthorityState(
            pairBindingDigest: String(repeating: "b", count: 64),
            pairEpoch: 1,
            clientIdentityFingerprint: String(repeating: "c", count: 64),
            runtimeIdentityFingerprint: String(repeating: "d", count: 64),
            generation: 1,
            serviceConfigVersion: 1,
            keysetVersion: 1,
            revocationCounter: 0,
            protocolFloor: 1,
            status: .active,
            transitionId: String(repeating: "e", count: 64),
            transitionRequestDigest: String(repeating: "f", count: 64),
            acceptedReceiptDigest: String(repeating: "1", count: 64),
            authorityRevision: 1
        )
        let state = try ProductionPairStateSnapshot(authority: authority, localRevision: 1)
        let clientEphemeral = try deterministicSigningKey(43).publicKey.x963Representation
        let runtimeEphemeral = try deterministicSigningKey(44).publicKey.x963Representation
        let securityContext = try ProductionC1PreauthorizationSessionContext(
            sessionId: String(repeating: "2", count: 32),
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: clientEphemeral,
            runtimeEphemeralPublicKey: runtimeEphemeral,
            clientNonce: String(repeating: "3", count: 32),
            runtimeNonce: String(repeating: "4", count: 32),
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            keysetVersion: authority.keysetVersion,
            revocationCounter: authority.revocationCounter,
            routeKind: .turnRelay
        )
        let routeHandle = "verified-c1-relay"
        let nonce = "verified-c1-nonce"
        let secret = Data(repeating: 0x5a, count: 32)
        let pathReceiptDigest = String(repeating: "5", count: 64)
        let connector = try ProductionC1RouteConnectorMaterial(
            kind: .turnRelay,
            addressBytes: Data([127, 0, 0, 1]),
            port: 443,
            serverName: "relay.example",
            transport: .tlsTcp,
            routeHandleDigest: ProductionC1RouteCommitments.routeHandleDigest(
                kind: .turnRelay,
                routeHandle: routeHandle
            ),
            credentialCommitmentDigest: ProductionC1RouteCommitments.credentialCommitmentDigest(
                kind: .turnRelay,
                routeHandle: routeHandle,
                nonce: nonce,
                secret: secret
            ),
            pathReceiptDigest: pathReceiptDigest,
            leaseDigest: String(repeating: "6", count: 64),
            allocationDigest: String(repeating: "7", count: 64)
        )
        let claims = try ProductionC1RoutePlanClaims(
            planId: String(repeating: "8", count: 64),
            kind: .turnRelay,
            pairAuthorityDigest: authority.digestHex(),
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            generation: authority.generation,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            connector: connector,
            securityContextDigest: securityContext.digestHex(),
            selectedPathReceiptDigest: pathReceiptDigest,
            notBeforeMs: nowMs - 10,
            expiresAtMs: expiresAtMs
        )
        let capability = try ProductionC1RouteCapability.signed(
            serviceIdDigest: serviceIdDigest,
            keysetVersion: 1,
            capabilityId: String(repeating: "9", count: 64),
            issuedAtMs: nowMs - 100,
            notBeforeMs: nowMs - 20,
            expiresAtMs: expiresAtMs + 100,
            authority: authority,
            kind: .turnRelay,
            routePlanClaimsDigest: claims.digestHex(),
            using: routeKey
        )
        let plan = try ProductionC1Verifier.verifyRoutePlan(
            claims: claims,
            capability: capability,
            securityContext: securityContext,
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            nowMs: nowMs
        )
        let connectorInput = try ProductionC1Verifier.verifyConnectorInput(
            for: plan,
            routeHandle: routeHandle,
            nonce: nonce,
            secret: secret,
            nowMs: nowMs
        )
        let authorization = try ProductionC1Verifier.makeRouteAuthorization(
            for: plan,
            nowMs: nowMs
        )
        let transcript = try ProductionSecureSessionTranscript(
            sessionId: securityContext.sessionId,
            pairBindingDigest: authority.pairBindingDigest,
            pairEpoch: authority.pairEpoch,
            clientIdentityFingerprint: authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: authority.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: clientEphemeral,
            runtimeEphemeralPublicKey: runtimeEphemeral,
            clientNonce: securityContext.clientNonce,
            runtimeNonce: securityContext.runtimeNonce,
            generation: authority.generation,
            serviceConfigVersion: authority.serviceConfigVersion,
            keysetVersion: authority.keysetVersion,
            revocationCounter: authority.revocationCounter,
            routeKind: .turnRelay,
            routeAuthDigest: authorization.digestHex
        )
        return VerifiedC1AdmissionFixture(
            state: state,
            binding: try ProductionC1Verifier.verifyTranscriptBinding(
                transcript: transcript,
                authorization: authorization,
                verifiedPlan: plan,
                connectorInput: connectorInput,
                authority: authority,
                nowMs: nowMs
            )
        )
    }

    private func deterministicSigningKey(_ scalar: UInt8) throws -> P256.Signing.PrivateKey {
        var raw = Data(repeating: 0, count: 32)
        raw[31] = scalar
        return try P256.Signing.PrivateKey(rawRepresentation: raw)
    }

    private func signingKeyId(_ key: P256.Signing.PublicKey) -> String {
        SHA256.hash(data: key.derRepresentation)
            .map { String(format: "%02x", $0) }
            .joined()
    }

    private func temporaryTrustedDevicesFileURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-trusted-device-tests", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("trusted-devices.json")
    }

    private func lockURL(for fileURL: URL) -> URL {
        URL(fileURLWithPath: fileURL.path + ".lock")
    }

    private func decodeDevices(at fileURL: URL) throws -> [TrustedDevice] {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode([TrustedDevice].self, from: Data(contentsOf: fileURL))
    }

    private func encodeDevices(_ devices: [TrustedDevice]) throws -> Data {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(devices)
    }

    private func writeAmbiguousStore(to fileURL: URL) throws -> Data {
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let devices = [
            TrustedDevice(
                id: "duplicate-device",
                name: "First",
                publicKeyBase64: "first-public-key",
                pairedAt: Date(timeIntervalSince1970: 20_000)
            ),
            TrustedDevice(
                id: "duplicate-device",
                name: "Second",
                publicKeyBase64: "second-public-key",
                pairedAt: Date(timeIntervalSince1970: 21_000)
            ),
        ]
        let data = try encodeDevices(devices)
        try data.write(to: fileURL)
        return data
    }

    private func testLimits(
        maxStoreBytes: Int = 4 * 1024,
        maxDevices: Int = 8,
        maxIdentifierUTF8Bytes: Int = 128,
        maxNameUTF8Bytes: Int = 128,
        maxPublicKeyUTF8Bytes: Int = 512
    ) -> TrustedDeviceStoreLimits {
        TrustedDeviceStoreLimits(
            maxStoreBytes: maxStoreBytes,
            maxDevices: maxDevices,
            maxIdentifierUTF8Bytes: maxIdentifierUTF8Bytes,
            maxNameUTF8Bytes: maxNameUTF8Bytes,
            maxPublicKeyUTF8Bytes: maxPublicKeyUTF8Bytes
        )
    }

    private func filePermissions(at fileURL: URL) throws -> Int {
        let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
        return try XCTUnwrap(attributes[.posixPermissions] as? Int) & 0o777
    }

    private func directoryPermissions(at directoryURL: URL) throws -> Int {
        let attributes = try FileManager.default.attributesOfItem(atPath: directoryURL.path)
        return try XCTUnwrap(attributes[.posixPermissions] as? Int) & 0o777
    }

    private func publicSymbolGraph(module: String) throws -> [[String: Any]] {
        #if arch(arm64)
        let architecture = "arm64"
        #elseif arch(x86_64)
        let architecture = "x86_64"
        #else
        throw XCTSkip("Unsupported architecture for Swift symbol-graph extraction")
        #endif
        var projectRoot = URL(fileURLWithPath: #filePath)
        for _ in 0..<5 { projectRoot.deleteLastPathComponent() }
        let modulesURL = projectRoot
            .appendingPathComponent(".build", isDirectory: true)
            .appendingPathComponent("\(architecture)-apple-macosx", isDirectory: true)
            .appendingPathComponent("debug", isDirectory: true)
            .appendingPathComponent("Modules", isDirectory: true)
        let outputURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-public-api-symbols", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(
            at: outputURL,
            withIntermediateDirectories: true
        )
        defer { try? FileManager.default.removeItem(at: outputURL) }

        let sdkPath = try runProcess(
            executable: "/usr/bin/xcrun",
            arguments: ["--sdk", "macosx", "--show-sdk-path"]
        ).trimmingCharacters(in: .whitespacesAndNewlines)
        _ = try runProcess(
            executable: "/usr/bin/xcrun",
            arguments: [
                "swift-symbolgraph-extract",
                "-module-name", module,
                "-I", modulesURL.path,
                "-target", "\(architecture)-apple-macosx14.0",
                "-sdk", sdkPath,
                "-minimum-access-level", "public",
                "-output-dir", outputURL.path,
            ]
        )
        let graphURL = outputURL.appendingPathComponent("\(module).symbols.json")
        let graph = try XCTUnwrap(
            JSONSerialization.jsonObject(with: Data(contentsOf: graphURL))
                as? [String: Any]
        )
        return try XCTUnwrap(graph["symbols"] as? [[String: Any]])
    }

    private func runProcess(executable: String, arguments: [String]) throws -> String {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        let output = Pipe()
        process.standardOutput = output
        process.standardError = output
        try process.run()
        process.waitUntilExit()
        let bytes = output.fileHandleForReading.readDataToEndOfFile()
        let text = String(decoding: bytes, as: UTF8.self)
        guard process.terminationStatus == 0 else {
            throw NSError(
                domain: "TrustedDeviceStoreTests.Process",
                code: Int(process.terminationStatus),
                userInfo: [NSLocalizedDescriptionKey: text]
            )
        }
        return text
    }

    private func symbolKind(_ symbol: [String: Any]) -> String? {
        (symbol["kind"] as? [String: Any])?["identifier"] as? String
    }

    private func symbolPath(_ symbol: [String: Any]) -> [String] {
        symbol["pathComponents"] as? [String] ?? []
    }
}

private struct LegacyTrustedDevice: Codable {
    let id: String
    let name: String
    let publicKeyBase64: String
    let pairedAt: Date
}

private final class LockedBox<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var value: Value?

    func set(_ value: Value) {
        lock.lock()
        self.value = value
        lock.unlock()
    }

    func get() -> Value? {
        lock.lock()
        defer { lock.unlock() }
        return value
    }
}

private func addBroadReadACL(at fileURL: URL) throws {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/bin/chmod")
    process.arguments = ["+a", "everyone allow read", fileURL.path]
    process.standardOutput = FileHandle.nullDevice
    process.standardError = FileHandle.nullDevice
    try process.run()
    process.waitUntilExit()
    guard process.terminationStatus == 0 else {
        throw NSError(
            domain: "TrustedDeviceStoreTests.ACL",
            code: Int(process.terminationStatus)
        )
    }
}

private func extendedACLCount(at fileURL: URL) throws -> Int {
    guard let acl = Darwin.acl_get_file(fileURL.path, ACL_TYPE_EXTENDED) else {
        if errno == ENOENT { return 0 }
        throw NSError(
            domain: NSPOSIXErrorDomain,
            code: Int(errno)
        )
    }
    defer { _ = Darwin.acl_free(UnsafeMutableRawPointer(acl)) }

    var entry: acl_entry_t?
    var status = Darwin.acl_get_entry(acl, ACL_FIRST_ENTRY.rawValue, &entry)
    var count = 0
    while status == 0 {
        count += 1
        status = Darwin.acl_get_entry(acl, ACL_NEXT_ENTRY.rawValue, &entry)
    }
    guard status == -1, errno == EINVAL else {
        throw NSError(
            domain: NSPOSIXErrorDomain,
            code: Int(errno)
        )
    }
    return count
}
