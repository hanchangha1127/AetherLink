import Darwin
import Foundation

@_silgen_name("flock")
private func systemFlock(_ descriptor: Int32, _ operation: Int32) -> Int32

private let trustedDeviceStoreLimitsUserInfoKey = CodingUserInfoKey(
    rawValue: "aetherlink.trusted-device-store-limits"
)!

public let trustedDeviceStoreMaxBytes = 1 * 1024 * 1024
public let trustedDeviceStoreMaxDevices = 256
public let trustedDeviceIdentifierMaxUTF8Bytes = 256
public let trustedDeviceNameMaxUTF8Bytes = 512
public let trustedDevicePublicKeyMaxUTF8Bytes = 4 * 1024

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

public enum TrustedDeviceStoreError: Error, Equatable, Sendable {
    case invalidStoreLocation
    case unsafeStoreFile
    case ambiguousDeviceIdentifier
    case lockUnavailable
    case lockAcquisitionTimedOut
    case ioFailure(operation: String, code: Int32)
    case durabilityUncertainAfterRename
}

public struct TrustedDeviceStoreResourceLimitError: Error, Equatable, LocalizedError, Sendable {
    public let resource: String
    public let limit: Int
    public let actual: Int

    public init(resource: String, limit: Int, actual: Int) {
        self.resource = resource
        self.limit = limit
        self.actual = actual
    }

    public var errorDescription: String? {
        "Trusted device resource limit exceeded for \(resource): \(actual) exceeded \(limit)"
    }
}

struct TrustedDeviceStoreLimits: Equatable, Sendable {
    static let standard = TrustedDeviceStoreLimits(
        maxStoreBytes: trustedDeviceStoreMaxBytes,
        maxDevices: trustedDeviceStoreMaxDevices,
        maxIdentifierUTF8Bytes: trustedDeviceIdentifierMaxUTF8Bytes,
        maxNameUTF8Bytes: trustedDeviceNameMaxUTF8Bytes,
        maxPublicKeyUTF8Bytes: trustedDevicePublicKeyMaxUTF8Bytes
    )

    var maxStoreBytes: Int
    var maxDevices: Int
    var maxIdentifierUTF8Bytes: Int
    var maxNameUTF8Bytes: Int
    var maxPublicKeyUTF8Bytes: Int
}

struct TrustedDeviceStoreSynchronizationHooks: Sendable {
    var didLoadMutationSnapshot: (@Sendable () -> Void)?
    var didObserveMutationLockContention: (@Sendable () -> Void)?
    var didCreateTemporaryFile: (@Sendable (URL) -> Void)?
    var didPrepareAtomicReplacement: (@Sendable (URL) -> Void)?

    init(
        didLoadMutationSnapshot: (@Sendable () -> Void)? = nil,
        didObserveMutationLockContention: (@Sendable () -> Void)? = nil,
        didCreateTemporaryFile: (@Sendable (URL) -> Void)? = nil,
        didPrepareAtomicReplacement: (@Sendable (URL) -> Void)? = nil
    ) {
        self.didLoadMutationSnapshot = didLoadMutationSnapshot
        self.didObserveMutationLockContention = didObserveMutationLockContention
        self.didCreateTemporaryFile = didCreateTemporaryFile
        self.didPrepareAtomicReplacement = didPrepareAtomicReplacement
    }
}

private struct TrustedDeviceStoreDirectory {
    let url: URL
    let descriptor: Int32
    let storeName: String

    var lockName: String { "\(storeName).lock" }
}

public actor TrustedDeviceStore {
    private static let directoryPermissions = mode_t(S_IRWXU)
    private static let filePermissions = mode_t(S_IRUSR | S_IWUSR)
    private static let defaultLockTimeoutNanoseconds: UInt64 = 5_000_000_000
    private static let lockRetryNanoseconds: UInt64 = 10_000_000

    private let fileURL: URL
    private let fileManager: FileManager
    private let lockTimeoutNanoseconds: UInt64
    private let synchronizationHooks: TrustedDeviceStoreSynchronizationHooks
    private let limits: TrustedDeviceStoreLimits
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    public init(fileURL: URL? = nil, fileManager: FileManager = .default) {
        let base = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let directory = base.appendingPathComponent("AetherLink", isDirectory: true)
        self.fileURL = fileURL ?? directory.appendingPathComponent("trusted-devices.json")
        self.fileManager = fileManager
        lockTimeoutNanoseconds = Self.defaultLockTimeoutNanoseconds
        synchronizationHooks = TrustedDeviceStoreSynchronizationHooks()
        limits = .standard
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
        decoder.userInfo[trustedDeviceStoreLimitsUserInfoKey] = limits
    }

    init(
        fileURL: URL,
        fileManager: FileManager = .default,
        lockTimeoutNanoseconds: UInt64 = TrustedDeviceStore.defaultLockTimeoutNanoseconds,
        synchronizationHooks: TrustedDeviceStoreSynchronizationHooks,
        limits: TrustedDeviceStoreLimits = .standard
    ) {
        self.fileURL = fileURL
        self.fileManager = fileManager
        self.lockTimeoutNanoseconds = lockTimeoutNanoseconds
        self.synchronizationHooks = synchronizationHooks
        self.limits = limits
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
        decoder.userInfo[trustedDeviceStoreLimitsUserInfoKey] = limits
    }

    public func load() throws -> [TrustedDevice] {
        return try withStoreLock(exclusive: false) { directory in
            try loadUnlocked(from: directory)
        }
    }

    public func trust(_ device: TrustedDevice) throws {
        try validateDevice(device)
        try withStoreLock(exclusive: true) { directory in
            var devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            if let existingIndex = devices.firstIndex(where: { $0.id == device.id }) {
                devices[existingIndex] = device
            } else {
                try enforceLimit(
                    devices.count + 1,
                    resource: "trusted device rows",
                    limit: limits.maxDevices
                )
                devices.append(device)
            }
            try saveUnlocked(devices.sorted { $0.name < $1.name }, in: directory)
        }
    }

    public func remove(deviceID: String) throws {
        try validateField(
            deviceID,
            resource: "device identifier UTF-8 bytes",
            limit: limits.maxIdentifierUTF8Bytes
        )
        try withStoreLock(exclusive: true) { directory in
            let devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            try saveUnlocked(devices.filter { $0.id != deviceID }, in: directory)
        }
    }

    public func withTrustedDeviceSnapshot<Result: Sendable>(
        deviceID: String,
        operation: @Sendable (TrustedDevice?) throws -> Result
    ) throws -> Result {
        try validateField(
            deviceID,
            resource: "device identifier UTF-8 bytes",
            limit: limits.maxIdentifierUTF8Bytes
        )
        return try withStoreLock(exclusive: false) { directory in
            let device = try loadUnlocked(from: directory).first { $0.id == deviceID }
            return try operation(device)
        }
    }

    private func withStoreLock<Result>(
        exclusive: Bool,
        operation: (TrustedDeviceStoreDirectory) throws -> Result
    ) throws -> Result {
        let directory = try openSecureDirectory()
        defer { Darwin.close(directory.descriptor) }

        let lockDescriptor = try openSecureLockFile(in: directory)
        defer { Darwin.close(lockDescriptor) }
        try acquireLock(
            descriptor: lockDescriptor,
            operation: exclusive ? LOCK_EX : LOCK_SH
        )
        defer { _ = systemFlock(lockDescriptor, LOCK_UN) }
        return try operation(directory)
    }

    private func openSecureDirectory() throws -> TrustedDeviceStoreDirectory {
        guard fileURL.isFileURL,
              !fileURL.lastPathComponent.isEmpty,
              fileURL.lastPathComponent != ".",
              fileURL.lastPathComponent != ".."
        else {
            throw TrustedDeviceStoreError.invalidStoreLocation
        }
        let requestedDirectory = fileURL.deletingLastPathComponent()
        do {
            try fileManager.createDirectory(
                at: requestedDirectory,
                withIntermediateDirectories: true,
                attributes: [.posixPermissions: Self.directoryPermissions]
            )
        } catch {
            throw TrustedDeviceStoreError.invalidStoreLocation
        }
        let canonicalDirectory = requestedDirectory
            .resolvingSymlinksInPath()
            .standardizedFileURL
        let descriptor = Darwin.open(
            canonicalDirectory.path,
            O_RDONLY | O_CLOEXEC | O_NOFOLLOW
        )
        guard descriptor >= 0 else {
            throw ioFailure("open directory")
        }
        var metadata = stat()
        guard Darwin.fstat(descriptor, &metadata) == 0,
              metadata.st_uid == geteuid(),
              metadata.st_mode & S_IFMT == S_IFDIR
        else {
            Darwin.close(descriptor)
            throw TrustedDeviceStoreError.invalidStoreLocation
        }
        do {
            try secureDescriptor(
                descriptor,
                permissions: Self.directoryPermissions,
                operation: "secure trusted device directory"
            )
        } catch {
            Darwin.close(descriptor)
            throw error
        }
        return TrustedDeviceStoreDirectory(
            url: canonicalDirectory,
            descriptor: descriptor,
            storeName: fileURL.lastPathComponent
        )
    }

    private func openSecureLockFile(in directory: TrustedDeviceStoreDirectory) throws -> Int32 {
        let descriptor = Darwin.openat(
            directory.descriptor,
            directory.lockName,
            O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW,
            Self.filePermissions
        )
        guard descriptor >= 0 else {
            throw TrustedDeviceStoreError.lockUnavailable
        }
        do {
            try validateRegularFileDescriptor(descriptor, failure: .lockUnavailable)
            try secureDescriptor(
                descriptor,
                permissions: Self.filePermissions,
                operation: "secure lock file"
            )
            return descriptor
        } catch {
            Darwin.close(descriptor)
            throw error
        }
    }

    private func acquireLock(descriptor: Int32, operation: Int32) throws {
        let started = try monotonicNanoseconds()
        let deadlineResult = started.addingReportingOverflow(lockTimeoutNanoseconds)
        guard !deadlineResult.overflow else {
            throw TrustedDeviceStoreError.lockUnavailable
        }
        let deadline = deadlineResult.partialValue
        var reportedContention = false

        while systemFlock(descriptor, operation | LOCK_NB) != 0 {
            let lockError = errno
            if lockError == EINTR { continue }
            guard lockError == EWOULDBLOCK || lockError == EAGAIN else {
                throw TrustedDeviceStoreError.lockUnavailable
            }
            if operation == LOCK_EX && !reportedContention {
                reportedContention = true
                synchronizationHooks.didObserveMutationLockContention?()
            }
            let now = try monotonicNanoseconds()
            guard now < deadline else {
                throw TrustedDeviceStoreError.lockAcquisitionTimedOut
            }
            let delayNanoseconds = min(Self.lockRetryNanoseconds, deadline - now)
            var delay = timespec(
                tv_sec: time_t(delayNanoseconds / 1_000_000_000),
                tv_nsec: Int(delayNanoseconds % 1_000_000_000)
            )
            var remaining = timespec()
            while Darwin.nanosleep(&delay, &remaining) != 0 {
                guard errno == EINTR else {
                    throw TrustedDeviceStoreError.lockUnavailable
                }
                delay = remaining
            }
        }
    }

    private func loadUnlocked(from directory: TrustedDeviceStoreDirectory) throws -> [TrustedDevice] {
        var pathMetadata = stat()
        guard Darwin.fstatat(
            directory.descriptor,
            directory.storeName,
            &pathMetadata,
            AT_SYMLINK_NOFOLLOW
        ) == 0 else {
            if errno == ENOENT { return [] }
            throw ioFailure("inspect trusted device store")
        }
        guard isSafeRegularFile(pathMetadata) else {
            throw TrustedDeviceStoreError.unsafeStoreFile
        }
        let descriptor = Darwin.openat(
            directory.descriptor,
            directory.storeName,
            O_RDONLY | O_CLOEXEC | O_NOFOLLOW
        )
        guard descriptor >= 0 else {
            throw ioFailure("open trusted device store")
        }
        defer { Darwin.close(descriptor) }
        try validateRegularFileDescriptor(descriptor, failure: .unsafeStoreFile)
        try secureDescriptor(
            descriptor,
            permissions: Self.filePermissions,
            operation: "secure trusted device store"
        )
        let data = try readAll(from: descriptor)
        let decoded = try decoder.decode(BoundedTrustedDeviceCollection.self, from: data)
        return decoded.devices
    }

    private func saveUnlocked(
        _ devices: [TrustedDevice],
        in directory: TrustedDeviceStoreDirectory
    ) throws {
        try validateDevices(devices)
        try validateDestination(in: directory)
        let data = try encoder.encode(devices)
        try enforceLimit(
            data.count,
            resource: "trusted device store bytes",
            limit: limits.maxStoreBytes
        )
        let temporaryName = ".\(directory.storeName).tmp.\(getpid()).\(UUID().uuidString)"
        let descriptor = Darwin.openat(
            directory.descriptor,
            temporaryName,
            O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW,
            Self.filePermissions
        )
        guard descriptor >= 0 else {
            throw ioFailure("create trusted device temporary file")
        }
        let temporaryURL = directory.url.appendingPathComponent(temporaryName)
        var shouldRemoveTemporaryFile = true
        defer {
            Darwin.close(descriptor)
            if shouldRemoveTemporaryFile {
                Darwin.unlinkat(directory.descriptor, temporaryName, 0)
            }
        }
        synchronizationHooks.didCreateTemporaryFile?(temporaryURL)
        try validateRegularFileDescriptor(descriptor, failure: .unsafeStoreFile)
        try secureDescriptor(
            descriptor,
            permissions: Self.filePermissions,
            operation: "secure trusted device temporary file"
        )
        try writeAll(data, to: descriptor)
        try syncFile(descriptor)

        synchronizationHooks.didPrepareAtomicReplacement?(temporaryURL)
        guard Darwin.renameat(
            directory.descriptor,
            temporaryName,
            directory.descriptor,
            directory.storeName
        ) == 0 else {
            throw ioFailure("replace trusted device store")
        }
        shouldRemoveTemporaryFile = false
        guard syncDescriptor(directory.descriptor) else {
            throw TrustedDeviceStoreError.durabilityUncertainAfterRename
        }
    }

    private func validateDestination(in directory: TrustedDeviceStoreDirectory) throws {
        var metadata = stat()
        guard Darwin.fstatat(
            directory.descriptor,
            directory.storeName,
            &metadata,
            AT_SYMLINK_NOFOLLOW
        ) == 0 else {
            if errno == ENOENT { return }
            throw ioFailure("inspect trusted device destination")
        }
        guard isSafeRegularFile(metadata) else {
            throw TrustedDeviceStoreError.unsafeStoreFile
        }
    }

    private func validateRegularFileDescriptor(
        _ descriptor: Int32,
        failure: TrustedDeviceStoreError
    ) throws {
        var metadata = stat()
        guard Darwin.fstat(descriptor, &metadata) == 0,
              isSafeRegularFile(metadata)
        else {
            throw failure
        }
    }

    private func isSafeRegularFile(_ metadata: stat) -> Bool {
        metadata.st_uid == geteuid()
            && metadata.st_mode & S_IFMT == S_IFREG
            && metadata.st_nlink == 1
    }

    private func readAll(from descriptor: Int32) throws -> Data {
        var metadata = stat()
        guard Darwin.fstat(descriptor, &metadata) == 0,
              metadata.st_size >= 0
        else {
            throw TrustedDeviceStoreError.unsafeStoreFile
        }
        if UInt64(metadata.st_size) > UInt64(limits.maxStoreBytes) {
            throw TrustedDeviceStoreResourceLimitError(
                resource: "trusted device store bytes",
                limit: limits.maxStoreBytes,
                actual: boundedStoreActualCount(metadata.st_size)
            )
        }

        var data = Data()
        data.reserveCapacity(Int(metadata.st_size))
        var buffer = [UInt8](repeating: 0, count: 64 * 1024)
        while true {
            let requestedCount = min(buffer.count, limits.maxStoreBytes - data.count + 1)
            let count = Darwin.read(descriptor, &buffer, requestedCount)
            if count < 0 && errno == EINTR { continue }
            guard count >= 0 else {
                throw ioFailure("read trusted device store")
            }
            guard count > 0 else { return data }

            let actualCount = data.count + count
            guard actualCount <= limits.maxStoreBytes else {
                throw TrustedDeviceStoreResourceLimitError(
                    resource: "trusted device store bytes",
                    limit: limits.maxStoreBytes,
                    actual: actualCount
                )
            }
            data.append(contentsOf: buffer[0..<count])
        }
    }

    private func secureDescriptor(
        _ descriptor: Int32,
        permissions: mode_t,
        operation: String
    ) throws {
        guard Darwin.fchmod(descriptor, permissions) == 0 else {
            throw ioFailure(operation)
        }
        guard let emptyACL = Darwin.acl_init(0) else {
            throw ioFailure(operation)
        }
        defer { _ = Darwin.acl_free(UnsafeMutableRawPointer(emptyACL)) }
        while Darwin.acl_set_fd_np(descriptor, emptyACL, ACL_TYPE_EXTENDED) != 0 {
            if errno == EINTR { continue }
            throw ioFailure(operation)
        }
    }

    private func validateDevice(_ device: TrustedDevice) throws {
        try validateTrustedDevice(device, limits: limits)
    }

    private func validateDevices(_ devices: [TrustedDevice]) throws {
        try enforceLimit(
            devices.count,
            resource: "trusted device rows",
            limit: limits.maxDevices
        )
        var deviceIdentifiers = Set<String>()
        for device in devices {
            try validateDevice(device)
            guard deviceIdentifiers.insert(device.id).inserted else {
                throw TrustedDeviceStoreError.ambiguousDeviceIdentifier
            }
        }
    }

    private func validateField(
        _ value: String,
        resource: String,
        limit: Int
    ) throws {
        try enforceLimit(value.utf8.count, resource: resource, limit: limit)
    }

    private func enforceLimit(
        _ actual: Int,
        resource: String,
        limit: Int
    ) throws {
        guard actual <= limit else {
            throw TrustedDeviceStoreResourceLimitError(
                resource: resource,
                limit: limit,
                actual: actual
            )
        }
    }

    private func writeAll(_ data: Data, to descriptor: Int32) throws {
        try data.withUnsafeBytes { buffer in
            guard let baseAddress = buffer.baseAddress else { return }
            var offset = 0
            while offset < buffer.count {
                let count = Darwin.write(
                    descriptor,
                    baseAddress.advanced(by: offset),
                    buffer.count - offset
                )
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else {
                    throw ioFailure("write trusted device store")
                }
                offset += count
            }
        }
    }

    private func syncFile(_ descriptor: Int32) throws {
        while Darwin.fcntl(descriptor, F_FULLFSYNC) != 0 {
            let syncError = errno
            if syncError == EINTR { continue }
            if syncError == EINVAL || syncError == ENOTSUP {
                guard syncDescriptor(descriptor) else {
                    throw ioFailure("sync trusted device store", code: errno)
                }
                return
            }
            throw ioFailure("sync trusted device store", code: syncError)
        }
    }

    private func syncDescriptor(_ descriptor: Int32) -> Bool {
        while Darwin.fsync(descriptor) != 0 {
            if errno != EINTR { return false }
        }
        return true
    }

    private func monotonicNanoseconds() throws -> UInt64 {
        var value = timespec()
        guard Darwin.clock_gettime(CLOCK_MONOTONIC, &value) == 0,
              value.tv_sec >= 0,
              value.tv_nsec >= 0
        else {
            throw TrustedDeviceStoreError.lockUnavailable
        }
        return UInt64(value.tv_sec) * 1_000_000_000 + UInt64(value.tv_nsec)
    }

    private func ioFailure(
        _ operation: String,
        code: Int32 = errno
    ) -> TrustedDeviceStoreError {
        .ioFailure(operation: operation, code: code)
    }
}

private struct BoundedTrustedDeviceCollection: Decodable {
    let devices: [TrustedDevice]

    init(from decoder: Decoder) throws {
        guard let limits = decoder.userInfo[trustedDeviceStoreLimitsUserInfoKey]
            as? TrustedDeviceStoreLimits
        else {
            throw TrustedDeviceStoreError.unsafeStoreFile
        }
        var container = try decoder.unkeyedContainer()
        if let declaredCount = container.count {
            try enforceTrustedDeviceLimit(
                declaredCount,
                resource: "trusted device rows",
                limit: limits.maxDevices
            )
        }

        var devices: [TrustedDevice] = []
        var deviceIdentifiers = Set<String>()
        devices.reserveCapacity(min(container.count ?? 0, limits.maxDevices))
        while !container.isAtEnd {
            guard devices.count < limits.maxDevices else {
                throw TrustedDeviceStoreResourceLimitError(
                    resource: "trusted device rows",
                    limit: limits.maxDevices,
                    actual: limits.maxDevices + 1
                )
            }
            let device = try container.decode(TrustedDevice.self)
            try validateTrustedDevice(device, limits: limits)
            guard deviceIdentifiers.insert(device.id).inserted else {
                throw TrustedDeviceStoreError.ambiguousDeviceIdentifier
            }
            devices.append(device)
        }
        self.devices = devices
    }
}

private func validateTrustedDevice(
    _ device: TrustedDevice,
    limits: TrustedDeviceStoreLimits
) throws {
    try enforceTrustedDeviceLimit(
        device.id.utf8.count,
        resource: "device identifier UTF-8 bytes",
        limit: limits.maxIdentifierUTF8Bytes
    )
    try enforceTrustedDeviceLimit(
        device.name.utf8.count,
        resource: "device name UTF-8 bytes",
        limit: limits.maxNameUTF8Bytes
    )
    try enforceTrustedDeviceLimit(
        device.publicKeyBase64.utf8.count,
        resource: "device public key UTF-8 bytes",
        limit: limits.maxPublicKeyUTF8Bytes
    )
}

private func enforceTrustedDeviceLimit(
    _ actual: Int,
    resource: String,
    limit: Int
) throws {
    guard actual <= limit else {
        throw TrustedDeviceStoreResourceLimitError(
            resource: resource,
            limit: limit,
            actual: actual
        )
    }
}

private func boundedStoreActualCount(_ value: off_t) -> Int {
    value > off_t(Int.max) ? Int.max : Int(value)
}
