import Darwin
import Foundation
@testable import TrustedDevices
import XCTest

final class TrustedDeviceStoreTests: XCTestCase {
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
