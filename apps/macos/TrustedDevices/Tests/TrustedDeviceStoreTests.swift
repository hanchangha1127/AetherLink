import Foundation
import TrustedDevices
import XCTest

final class TrustedDeviceStoreTests: XCTestCase {
    func testTrustCreatesStoreWithOwnerOnlyPermissions() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let store = TrustedDeviceStore(fileURL: fileURL)
        let device = TrustedDevice(
            id: "device-1",
            name: "Phone",
            publicKeyBase64: "public-key-1",
            pairedAt: Date(timeIntervalSince1970: 1_000)
        )

        try await store.trust(device)
        let loaded = try await store.load()

        XCTAssertEqual(loaded, [device])
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
        XCTAssertEqual(try directoryPermissions(at: fileURL.deletingLastPathComponent()), 0o700)
    }

    func testLoadCorrectsBroadPermissionsWithoutDroppingTrustedDevices() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let directoryURL = fileURL.deletingLastPathComponent()
        let device = TrustedDevice(
            id: "device-1",
            name: "Phone",
            publicKeyBase64: "public-key-1",
            pairedAt: Date(timeIntervalSince1970: 2_000)
        )
        try await TrustedDeviceStore(fileURL: fileURL).trust(device)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: directoryURL.path)
        try FileManager.default.setAttributes([.posixPermissions: 0o644], ofItemAtPath: fileURL.path)

        let loaded = try await TrustedDeviceStore(fileURL: fileURL).load()

        XCTAssertEqual(loaded, [device])
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
        XCTAssertEqual(try directoryPermissions(at: directoryURL), 0o700)
    }

    func testRemoveMaintainsOwnerOnlyPermissions() async throws {
        let fileURL = temporaryTrustedDevicesFileURL()
        let directoryURL = fileURL.deletingLastPathComponent()
        let store = TrustedDeviceStore(fileURL: fileURL)
        try await store.trust(TrustedDevice(
            id: "device-1",
            name: "Phone",
            publicKeyBase64: "public-key-1",
            pairedAt: Date(timeIntervalSince1970: 3_000)
        ))

        try await store.remove(deviceID: "device-1")
        let loaded = try await store.load()

        XCTAssertEqual(loaded, [])
        XCTAssertEqual(try filePermissions(at: fileURL), 0o600)
        XCTAssertEqual(try directoryPermissions(at: directoryURL), 0o700)
    }

    private func temporaryTrustedDevicesFileURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-trusted-device-tests", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("trusted-devices.json")
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
