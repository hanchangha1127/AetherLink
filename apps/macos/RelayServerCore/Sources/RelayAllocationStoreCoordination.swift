import Darwin
import Foundation

enum RelayAllocationStoreCoordinationError: Error, Equatable, Sendable {
    case invalidParentDirectory
    case lockUnavailable
    case storeAlreadyOwned
    case durabilityUncertainAfterRename
}

enum RelayAllocationStoreEntryState: Equatable, Sendable {
    case absent
    case regular
    case invalid
}

enum RelayAllocationStoreMarkerState: Character, Sendable {
    case uninitialized = "U"
    case adoptingExistingStore = "A"
    case established = "E"
}

struct RelayAllocationStoreMarker: Equatable, Sendable {
    let state: RelayAllocationStoreMarkerState
    let token: String

    private static let header = "AETHERLINK_RELAY_ALLOCATION_LOCK_V1"

    func encoded() -> Data {
        Data("\(Self.header)\nstate=\(state.rawValue)\ntoken=\(token)\n".utf8)
    }

    static func decode(_ data: Data) throws -> RelayAllocationStoreMarker {
        guard let text = String(data: data, encoding: .utf8) else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        let lines = text.split(separator: "\n", omittingEmptySubsequences: false)
        guard lines.count == 4,
              lines[0] == Substring(header),
              lines[1].hasPrefix("state="),
              lines[1].count == 7,
              lines[2].hasPrefix("token="),
              lines[3].isEmpty,
              let stateCharacter = lines[1].last,
              let state = RelayAllocationStoreMarkerState(rawValue: stateCharacter)
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        let token = String(lines[2].dropFirst("token=".count))
        guard token.count == 64,
              token.allSatisfy({ ("0"..."9").contains($0) || ("a"..."f").contains($0) })
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        return RelayAllocationStoreMarker(state: state, token: token)
    }
}

private struct RelayAllocationStoreSecureDirectory {
    let url: URL
    let descriptor: Int32
    let leafName: String
}

fileprivate struct RelayAllocationStoreFileIdentity: Hashable, Sendable {
    let device: UInt64
    let inode: UInt64

    init(_ metadata: stat) {
        device = UInt64(metadata.st_dev)
        inode = UInt64(metadata.st_ino)
    }
}

enum RelayAllocationStoreCoordination {
    private static let maximumStoreBytes = 16 * 1024 * 1024
    private static let recordLockTimeoutNanoseconds: UInt64 = 5_000_000_000
    private static let recordLockRetryNanoseconds = 10_000_000
    private static let testSyncLock = NSLock()
    private static var forcedAtomicDirectorySyncFailures = 0

    static func transactionLockURL(for storeURL: URL) -> URL {
        URL(fileURLWithPath: storeURL.path + ".transaction.lock")
    }

    static func secureCanonicalFileURL(for fileURL: URL) throws -> URL {
        let directory = try openSecureDirectory(for: fileURL)
        defer { Darwin.close(directory.descriptor) }
        return directory.url.appendingPathComponent(directory.leafName, isDirectory: false)
    }

    static func entryState(at fileURL: URL) throws -> RelayAllocationStoreEntryState {
        let directory = try openSecureDirectory(for: fileURL)
        defer { Darwin.close(directory.descriptor) }
        var metadata = stat()
        guard Darwin.fstatat(
            directory.descriptor,
            directory.leafName,
            &metadata,
            AT_SYMLINK_NOFOLLOW
        ) == 0 else {
            return errno == ENOENT ? .absent : .invalid
        }
        guard metadata.st_uid == geteuid(),
              metadata.st_mode & S_IFMT == S_IFREG,
              metadata.st_nlink == 1
        else {
            return .invalid
        }
        return .regular
    }

    static func readSecureFile(at fileURL: URL) throws -> Data {
        let directory = try openSecureDirectory(for: fileURL)
        defer { Darwin.close(directory.descriptor) }
        let descriptor = Darwin.openat(
            directory.descriptor,
            directory.leafName,
            O_RDONLY | O_CLOEXEC | O_NOFOLLOW
        )
        guard descriptor >= 0 else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        defer { Darwin.close(descriptor) }
        let metadata = try validateRegularDescriptor(descriptor)
        guard Darwin.fchmod(descriptor, mode_t(S_IRUSR | S_IWUSR)) == 0,
              metadata.st_size >= 0,
              metadata.st_size <= maximumStoreBytes
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        return try readAll(
            descriptor: descriptor,
            byteCount: Int(metadata.st_size)
        )
    }

    static func writeAtomically(_ data: Data, to storeURL: URL) throws {
        guard data.count <= maximumStoreBytes else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        let directory = try openSecureDirectory(for: storeURL)
        defer { Darwin.close(directory.descriptor) }
        let currentState = try entryState(
            directoryDescriptor: directory.descriptor,
            leafName: directory.leafName
        )
        guard currentState != .invalid else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }

        let temporaryName = ".\(directory.leafName).tmp.\(getpid()).\(UUID().uuidString)"
        let descriptor = Darwin.openat(
            directory.descriptor,
            temporaryName,
            O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW,
            mode_t(S_IRUSR | S_IWUSR)
        )
        guard descriptor >= 0 else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        var shouldRemoveTemporaryFile = true
        defer {
            Darwin.close(descriptor)
            if shouldRemoveTemporaryFile {
                Darwin.unlinkat(directory.descriptor, temporaryName, 0)
            }
        }
        _ = try validateRegularDescriptor(descriptor)
        guard Darwin.fchmod(descriptor, mode_t(S_IRUSR | S_IWUSR)) == 0 else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        try writeAll(data, descriptor: descriptor)
        guard syncDescriptor(descriptor),
              Darwin.renameat(
                directory.descriptor,
                temporaryName,
                directory.descriptor,
                directory.leafName
              ) == 0
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        shouldRemoveTemporaryFile = false
        guard syncAtomicWriteDirectory(directory.descriptor) else {
            throw RelayAllocationStoreCoordinationError.durabilityUncertainAfterRename
        }
    }

    static func failNextAtomicDirectorySyncForTesting() {
        testSyncLock.lock()
        forcedAtomicDirectorySyncFailures += 1
        testSyncLock.unlock()
    }

    static func syncParentDirectory(of fileURL: URL) throws {
        let directory = try openSecureDirectory(for: fileURL)
        defer { Darwin.close(directory.descriptor) }
        guard syncDescriptor(directory.descriptor) else {
            throw RelayAllocationStoreCoordinationError.durabilityUncertainAfterRename
        }
    }

    static func setRecordLock(
        descriptor: Int32,
        type: Int16,
        blocking: Bool,
        start: off_t,
        length: off_t
    ) throws -> Bool {
        var record = Darwin.flock()
        record.l_type = type
        record.l_whence = Int16(SEEK_SET)
        record.l_start = start
        record.l_len = length
        let deadline = try monotonicNanoseconds().addingReportingOverflow(
            recordLockTimeoutNanoseconds
        )
        guard !deadline.overflow else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        while Darwin.fcntl(descriptor, F_SETLK, &record) != 0 {
            let lockError = errno
            if lockError == EINTR { continue }
            guard lockError == EACCES || lockError == EAGAIN else {
                throw RelayAllocationStoreCoordinationError.lockUnavailable
            }
            guard blocking else { return false }
            guard try monotonicNanoseconds() < deadline.partialValue else {
                throw RelayAllocationStoreCoordinationError.lockUnavailable
            }
            var delay = timespec(tv_sec: 0, tv_nsec: recordLockRetryNanoseconds)
            var remaining = timespec()
            while Darwin.nanosleep(&delay, &remaining) != 0 && errno == EINTR {
                delay = remaining
            }
        }
        return true
    }

    static func retainedLockDescriptorCountForTesting() -> Int {
        RelayAllocationStoreProcessCoordination.retainedDescriptorCount()
    }

    fileprivate static func openSecureLockFile(
        at lockURL: URL,
        initialState: RelayAllocationStoreMarkerState
    ) throws -> (
        descriptor: Int32,
        canonicalURL: URL,
        identity: RelayAllocationStoreFileIdentity
    ) {
        let directory = try openSecureDirectory(for: lockURL)
        defer { Darwin.close(directory.descriptor) }
        let canonicalURL = directory.url.appendingPathComponent(
            directory.leafName,
            isDirectory: false
        )
        var descriptor = Darwin.openat(
            directory.descriptor,
            directory.leafName,
            O_RDWR | O_CLOEXEC | O_NOFOLLOW
        )
        if descriptor < 0 && errno == ENOENT {
            descriptor = try createInitializedLockFile(
                directory: directory,
                initialState: initialState
            )
        }
        guard descriptor >= 0 else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        do {
            let metadata = try validateRegularDescriptor(descriptor)
            guard Darwin.fchmod(descriptor, mode_t(S_IRUSR | S_IWUSR)) == 0 else {
                throw RelayAllocationStoreCoordinationError.lockUnavailable
            }
            _ = try readMarker(descriptor: descriptor)
            return (
                descriptor,
                canonicalURL,
                RelayAllocationStoreFileIdentity(metadata)
            )
        } catch {
            RelayAllocationStoreProcessCoordination.retainOrCloseFailedDescriptor(descriptor)
            throw error
        }
    }

    fileprivate static func fileIdentity(
        at fileURL: URL
    ) throws -> RelayAllocationStoreFileIdentity {
        let directory = try openSecureDirectory(for: fileURL)
        defer { Darwin.close(directory.descriptor) }
        var metadata = stat()
        guard Darwin.fstatat(
            directory.descriptor,
            directory.leafName,
            &metadata,
            AT_SYMLINK_NOFOLLOW
        ) == 0,
              metadata.st_uid == geteuid(),
              metadata.st_mode & S_IFMT == S_IFREG,
              metadata.st_nlink == 1
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        return RelayAllocationStoreFileIdentity(metadata)
    }

    static func readMarker(descriptor: Int32) throws -> RelayAllocationStoreMarker {
        var metadata = stat()
        guard Darwin.fstat(descriptor, &metadata) == 0,
              metadata.st_size > 0,
              metadata.st_size <= 512
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        return try RelayAllocationStoreMarker.decode(
            readAll(descriptor: descriptor, byteCount: Int(metadata.st_size))
        )
    }

    static func writeMarker(
        _ marker: RelayAllocationStoreMarker,
        descriptor: Int32
    ) throws {
        let data = marker.encoded()
        try writeAll(data, descriptor: descriptor, positionedAtStart: true)
        guard Darwin.ftruncate(descriptor, off_t(data.count)) == 0,
              syncDescriptor(descriptor)
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
    }

    private static func openSecureDirectory(
        for fileURL: URL
    ) throws -> RelayAllocationStoreSecureDirectory {
        guard fileURL.isFileURL,
              !fileURL.lastPathComponent.isEmpty,
              fileURL.lastPathComponent != ".",
              fileURL.lastPathComponent != ".."
        else {
            throw RelayAllocationStoreCoordinationError.invalidParentDirectory
        }
        let requestedDirectory = fileURL.deletingLastPathComponent()
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(
            atPath: requestedDirectory.path,
            isDirectory: &isDirectory
        ), isDirectory.boolValue else {
            throw RelayAllocationStoreCoordinationError.invalidParentDirectory
        }
        let canonicalDirectory = requestedDirectory
            .resolvingSymlinksInPath()
            .standardizedFileURL
        let descriptor = Darwin.open(
            canonicalDirectory.path,
            O_RDONLY | O_CLOEXEC | O_NOFOLLOW
        )
        guard descriptor >= 0 else {
            throw RelayAllocationStoreCoordinationError.invalidParentDirectory
        }
        var metadata = stat()
        guard Darwin.fstat(descriptor, &metadata) == 0,
              metadata.st_uid == geteuid(),
              metadata.st_mode & S_IFMT == S_IFDIR,
              metadata.st_mode & (S_IWGRP | S_IWOTH) == 0
        else {
            Darwin.close(descriptor)
            throw RelayAllocationStoreCoordinationError.invalidParentDirectory
        }
        return RelayAllocationStoreSecureDirectory(
            url: canonicalDirectory,
            descriptor: descriptor,
            leafName: fileURL.lastPathComponent
        )
    }

    private static func entryState(
        directoryDescriptor: Int32,
        leafName: String
    ) throws -> RelayAllocationStoreEntryState {
        var metadata = stat()
        guard Darwin.fstatat(
            directoryDescriptor,
            leafName,
            &metadata,
            AT_SYMLINK_NOFOLLOW
        ) == 0 else {
            return errno == ENOENT ? .absent : .invalid
        }
        guard metadata.st_uid == geteuid(),
              metadata.st_mode & S_IFMT == S_IFREG,
              metadata.st_nlink == 1
        else {
            return .invalid
        }
        return .regular
    }

    private static func createInitializedLockFile(
        directory: RelayAllocationStoreSecureDirectory,
        initialState: RelayAllocationStoreMarkerState
    ) throws -> Int32 {
        let temporaryName = ".\(directory.leafName).init.\(getpid()).\(UUID().uuidString)"
        var descriptor = Darwin.openat(
            directory.descriptor,
            temporaryName,
            O_RDWR | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW,
            mode_t(S_IRUSR | S_IWUSR)
        )
        var linkedToFinalPath = false
        guard descriptor >= 0 else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        var shouldRemoveTemporaryFile = true
        defer {
            if descriptor >= 0 {
                if linkedToFinalPath {
                    RelayAllocationStoreProcessCoordination.retainLockDescriptor(descriptor)
                } else {
                    Darwin.close(descriptor)
                }
            }
            if shouldRemoveTemporaryFile {
                Darwin.unlinkat(directory.descriptor, temporaryName, 0)
            }
        }
        let marker = RelayAllocationStoreMarker(
            state: initialState,
            token: UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
                + UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
        )
        try writeMarker(marker, descriptor: descriptor)
        let installResult = Darwin.renameatx_np(
            directory.descriptor,
            temporaryName,
            directory.descriptor,
            directory.leafName,
            UInt32(RENAME_EXCL)
        )
        if installResult == 0 {
            linkedToFinalPath = true
            shouldRemoveTemporaryFile = false
            guard syncDescriptor(directory.descriptor) else {
                throw RelayAllocationStoreCoordinationError.lockUnavailable
            }
            let result = descriptor
            descriptor = -1
            return result
        }
        guard errno == EEXIST else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        Darwin.close(descriptor)
        descriptor = -1
        Darwin.unlinkat(directory.descriptor, temporaryName, 0)
        shouldRemoveTemporaryFile = false
        let existing = Darwin.openat(
            directory.descriptor,
            directory.leafName,
            O_RDWR | O_CLOEXEC | O_NOFOLLOW
        )
        guard existing >= 0 else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        return existing
    }

    private static func validateRegularDescriptor(_ descriptor: Int32) throws -> stat {
        var metadata = stat()
        guard Darwin.fstat(descriptor, &metadata) == 0,
              metadata.st_uid == geteuid(),
              metadata.st_mode & S_IFMT == S_IFREG,
              metadata.st_nlink == 1
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        return metadata
    }

    private static func readAll(descriptor: Int32, byteCount: Int) throws -> Data {
        var data = Data(count: byteCount)
        var offset = 0
        try data.withUnsafeMutableBytes { rawBuffer in
            while offset < byteCount {
                let count = Darwin.pread(
                    descriptor,
                    rawBuffer.baseAddress?.advanced(by: offset),
                    byteCount - offset,
                    off_t(offset)
                )
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else {
                    throw RelayAllocationStoreCoordinationError.lockUnavailable
                }
                offset += count
            }
        }
        return data
    }

    private static func writeAll(
        _ data: Data,
        descriptor: Int32,
        positionedAtStart: Bool = false
    ) throws {
        try data.withUnsafeBytes { rawBuffer in
            guard let baseAddress = rawBuffer.baseAddress else { return }
            var offset = 0
            while offset < rawBuffer.count {
                let count = positionedAtStart
                    ? Darwin.pwrite(
                        descriptor,
                        baseAddress.advanced(by: offset),
                        rawBuffer.count - offset,
                        off_t(offset)
                    )
                    : Darwin.write(
                        descriptor,
                        baseAddress.advanced(by: offset),
                        rawBuffer.count - offset
                    )
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else {
                    throw RelayAllocationStoreCoordinationError.lockUnavailable
                }
                offset += count
            }
        }
    }

    private static func syncDescriptor(_ descriptor: Int32) -> Bool {
        for _ in 0..<3 {
            if Darwin.fsync(descriptor) == 0 { return true }
            if errno == EINTR { continue }
        }
        return false
    }

    private static func monotonicNanoseconds() throws -> UInt64 {
        var value = timespec()
        guard Darwin.clock_gettime(CLOCK_MONOTONIC, &value) == 0,
              value.tv_sec >= 0,
              value.tv_nsec >= 0
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        return UInt64(value.tv_sec) * 1_000_000_000 + UInt64(value.tv_nsec)
    }

    private static func syncAtomicWriteDirectory(_ descriptor: Int32) -> Bool {
        testSyncLock.lock()
        if forcedAtomicDirectorySyncFailures > 0 {
            forcedAtomicDirectorySyncFailures -= 1
            testSyncLock.unlock()
            return false
        }
        testSyncLock.unlock()
        return syncDescriptor(descriptor)
    }
}

private final class RelayAllocationStoreProcessLockFile: @unchecked Sendable {
    let canonicalURL: URL
    let descriptor: Int32
    let identity: RelayAllocationStoreFileIdentity
    let processLock = NSLock()

    init(
        canonicalURL: URL,
        descriptor: Int32,
        identity: RelayAllocationStoreFileIdentity
    ) {
        self.canonicalURL = canonicalURL
        self.descriptor = descriptor
        self.identity = identity
    }

    func validatePathIdentity(at lockURL: URL) throws {
        guard try RelayAllocationStoreCoordination.fileIdentity(at: lockURL) == identity else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
    }

    func marker() throws -> RelayAllocationStoreMarker {
        try RelayAllocationStoreCoordination.readMarker(descriptor: descriptor)
    }
}

fileprivate enum RelayAllocationStoreProcessCoordination {
    private static let lock = NSLock()
    private static var lockFiles: [RelayAllocationStoreFileIdentity: RelayAllocationStoreProcessLockFile] = [:]
    // Never close another descriptor for this inode while POSIX record locks may exist.
    private static var retainedDuplicateDescriptors: [Int32] = []
    private static var ownedLockFiles = Set<RelayAllocationStoreFileIdentity>()

    static func lockFile(
        at lockURL: URL,
        initialState: RelayAllocationStoreMarkerState
    ) throws -> RelayAllocationStoreProcessLockFile {
        if let identity = try? RelayAllocationStoreCoordination.fileIdentity(at: lockURL) {
            lock.lock()
            let existing = lockFiles[identity]
            lock.unlock()
            if let existing { return existing }
        }
        let opened = try RelayAllocationStoreCoordination.openSecureLockFile(
            at: lockURL,
            initialState: initialState
        )
        lock.lock()
        defer { lock.unlock() }
        if let existing = lockFiles[opened.identity] {
            retainedDuplicateDescriptors.append(opened.descriptor)
            return existing
        }
        let file = RelayAllocationStoreProcessLockFile(
            canonicalURL: opened.canonicalURL,
            descriptor: opened.descriptor,
            identity: opened.identity
        )
        lockFiles[opened.identity] = file
        return file
    }

    static func retainLockDescriptor(_ descriptor: Int32) {
        lock.lock()
        retainedDuplicateDescriptors.append(descriptor)
        lock.unlock()
    }

    static func retainOrCloseFailedDescriptor(_ descriptor: Int32) {
        var metadata = stat()
        let identity = Darwin.fstat(descriptor, &metadata) == 0
            ? RelayAllocationStoreFileIdentity(metadata)
            : nil
        lock.lock()
        if let identity, lockFiles[identity] != nil {
            retainedDuplicateDescriptors.append(descriptor)
            lock.unlock()
        } else {
            lock.unlock()
            Darwin.close(descriptor)
        }
    }

    static func retainedDescriptorCount() -> Int {
        lock.lock()
        defer { lock.unlock() }
        return retainedDuplicateDescriptors.count
    }

    static func reserveOwner(identity: RelayAllocationStoreFileIdentity) -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return ownedLockFiles.insert(identity).inserted
    }

    static func releaseOwner(identity: RelayAllocationStoreFileIdentity) {
        lock.lock()
        ownedLockFiles.remove(identity)
        lock.unlock()
    }
}

final class RelayAllocationStoreTransactionLock: @unchecked Sendable {
    let storeURL: URL
    fileprivate let lockURL: URL
    fileprivate let lockFile: RelayAllocationStoreProcessLockFile

    init(storeURL requestedStoreURL: URL) throws {
        storeURL = try RelayAllocationStoreCoordination.secureCanonicalFileURL(
            for: requestedStoreURL
        )
        lockURL = RelayAllocationStoreCoordination.transactionLockURL(for: storeURL)
        let storeState = try RelayAllocationStoreCoordination.entryState(at: storeURL)
        let initialState: RelayAllocationStoreMarkerState = storeState == .absent
            ? .uninitialized
            : .adoptingExistingStore
        lockFile = try RelayAllocationStoreProcessCoordination.lockFile(
            at: lockURL,
            initialState: initialState
        )
    }

    func withExclusiveLock<T>(
        _ body: (RelayAllocationStoreMarker) throws -> T
    ) throws -> T {
        lockFile.processLock.lock()
        defer { lockFile.processLock.unlock() }
        try lockFile.validatePathIdentity(at: lockURL)
        _ = try RelayAllocationStoreCoordination.setRecordLock(
            descriptor: lockFile.descriptor,
            type: Int16(F_WRLCK),
            blocking: true,
            start: 0,
            length: 1
        )
        defer {
            _ = try? RelayAllocationStoreCoordination.setRecordLock(
                descriptor: lockFile.descriptor,
                type: Int16(F_UNLCK),
                blocking: false,
                start: 0,
                length: 1
            )
        }
        try lockFile.validatePathIdentity(at: lockURL)
        return try body(lockFile.marker())
    }

    func markEstablished(expectedToken: String) throws {
        let current = try lockFile.marker()
        guard current.token == expectedToken,
              current.state == .uninitialized || current.state == .adoptingExistingStore
        else {
            throw RelayAllocationStoreCoordinationError.lockUnavailable
        }
        try RelayAllocationStoreCoordination.writeMarker(
            RelayAllocationStoreMarker(state: .established, token: expectedToken),
            descriptor: lockFile.descriptor
        )
    }
}

final class RelayAllocationStoreOwnership: @unchecked Sendable {
    private let lockFile: RelayAllocationStoreProcessLockFile

    private init(lockFile: RelayAllocationStoreProcessLockFile) {
        self.lockFile = lockFile
    }

    static func acquire(storeURL: URL) throws -> RelayAllocationStoreOwnership {
        let transactionLock = try RelayAllocationStoreTransactionLock(storeURL: storeURL)
        let lockFile = transactionLock.lockFile
        lockFile.processLock.lock()
        defer { lockFile.processLock.unlock() }
        guard RelayAllocationStoreProcessCoordination.reserveOwner(identity: lockFile.identity) else {
            throw RelayAllocationStoreCoordinationError.storeAlreadyOwned
        }
        do {
            try lockFile.validatePathIdentity(at: transactionLock.lockURL)
            _ = try RelayAllocationStoreCoordination.setRecordLock(
                descriptor: lockFile.descriptor,
                type: Int16(F_WRLCK),
                blocking: true,
                start: 0,
                length: 1
            )
            defer {
                _ = try? RelayAllocationStoreCoordination.setRecordLock(
                    descriptor: lockFile.descriptor,
                    type: Int16(F_UNLCK),
                    blocking: false,
                    start: 0,
                    length: 1
                )
            }
            try lockFile.validatePathIdentity(at: transactionLock.lockURL)
            let marker = try lockFile.marker()
            guard marker.state == RelayAllocationStoreMarkerState.established else {
                throw RelayAllocationStoreCoordinationError.lockUnavailable
            }
            guard try RelayAllocationStoreCoordination.setRecordLock(
                    descriptor: lockFile.descriptor,
                    type: Int16(F_WRLCK),
                    blocking: false,
                    start: 1,
                    length: 1
                  ) else {
                throw RelayAllocationStoreCoordinationError.storeAlreadyOwned
            }
            return RelayAllocationStoreOwnership(lockFile: lockFile)
        } catch {
            RelayAllocationStoreProcessCoordination.releaseOwner(identity: lockFile.identity)
            throw error
        }
    }

    deinit {
        _ = try? RelayAllocationStoreCoordination.setRecordLock(
            descriptor: lockFile.descriptor,
            type: Int16(F_UNLCK),
            blocking: false,
            start: 1,
            length: 1
        )
        RelayAllocationStoreProcessCoordination.releaseOwner(identity: lockFile.identity)
    }
}
