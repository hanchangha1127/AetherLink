import Foundation

public struct TrustedDevice: Codable, Identifiable, Equatable, Sendable {
    public var id: String
    public var name: String
    public var publicKeyBase64: String
    public var pairedAt: Date

    public init(id: String, name: String, publicKeyBase64: String, pairedAt: Date = Date()) {
        self.id = id
        self.name = name
        self.publicKeyBase64 = publicKeyBase64
        self.pairedAt = pairedAt
    }
}

public actor TrustedDeviceStore {
    private static let directoryPermissions = 0o700
    private static let filePermissions = 0o600

    private let fileURL: URL
    private let fileManager: FileManager
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    public init(fileURL: URL? = nil, fileManager: FileManager = .default) {
        let base = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let directory = base.appendingPathComponent("AetherLink", isDirectory: true)
        self.fileURL = fileURL ?? directory.appendingPathComponent("trusted-devices.json")
        self.fileManager = fileManager
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
    }

    public func load() throws -> [TrustedDevice] {
        guard fileManager.fileExists(atPath: fileURL.path) else { return [] }
        try secureDirectory()
        try secureFile()
        let data = try Data(contentsOf: fileURL)
        return try decoder.decode([TrustedDevice].self, from: data)
    }

    public func trust(_ device: TrustedDevice) throws {
        var devices = try load()
        devices.removeAll { $0.id == device.id }
        devices.append(device)
        try save(devices.sorted { $0.name < $1.name })
    }

    public func remove(deviceID: String) throws {
        try save(try load().filter { $0.id != deviceID })
    }

    public func withTrustedDeviceSnapshot<Result: Sendable>(
        deviceID: String,
        operation: @Sendable (TrustedDevice?) throws -> Result
    ) throws -> Result {
        let device = try load().first { $0.id == deviceID }
        return try operation(device)
    }

    private func save(_ devices: [TrustedDevice]) throws {
        try secureDirectory()
        try encoder.encode(devices).write(to: fileURL, options: [.atomic])
        try secureFile()
    }

    private func secureDirectory() throws {
        let directoryURL = fileURL.deletingLastPathComponent()
        try fileManager.createDirectory(
            at: directoryURL,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: Self.directoryPermissions]
        )
        try fileManager.setAttributes(
            [.posixPermissions: Self.directoryPermissions],
            ofItemAtPath: directoryURL.standardizedFileURL.path
        )
    }

    private func secureFile() throws {
        try fileManager.setAttributes(
            [.posixPermissions: Self.filePermissions],
            ofItemAtPath: fileURL.standardizedFileURL.path
        )
    }
}
