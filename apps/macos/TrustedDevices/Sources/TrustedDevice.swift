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
    private let fileURL: URL
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    public init(fileURL: URL? = nil) {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let directory = base.appendingPathComponent("AetherLink", isDirectory: true)
        self.fileURL = fileURL ?? directory.appendingPathComponent("trusted-devices.json")
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
    }

    public func load() throws -> [TrustedDevice] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
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

    private func save(_ devices: [TrustedDevice]) throws {
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try encoder.encode(devices).write(to: fileURL, options: [.atomic])
    }
}
