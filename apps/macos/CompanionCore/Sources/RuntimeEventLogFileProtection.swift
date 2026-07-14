import Darwin
import Foundation

enum RuntimeEventLogFileProtection {
    static let directoryPermissions = 0o700
    static let filePermissions = 0o600

    static func appendLine(_ line: Data, to fileURL: URL) throws {
        try withExclusiveFileAccess(to: fileURL) {
            try appendLineWithoutCoordination(line, to: fileURL)
        }
    }

    static func withExclusiveFileAccess<T>(
        to fileURL: URL,
        _ body: () throws -> T
    ) throws -> T {
        let coordinatedURL = canonicalFileURL(fileURL)
        let coordinationPath = coordinatedURL.path
        let pathLock = pathLock(for: coordinationPath)
        pathLock.lock()
        defer { pathLock.unlock() }

        let recursionKey = "RuntimeEventLogFileProtection.lock.\(coordinationPath)"
        let recursionDepth = (Thread.current.threadDictionary[recursionKey] as? NSNumber)?.intValue ?? 0
        Thread.current.threadDictionary[recursionKey] = recursionDepth + 1
        defer {
            if recursionDepth == 0 {
                Thread.current.threadDictionary.removeObject(forKey: recursionKey)
            } else {
                Thread.current.threadDictionary[recursionKey] = recursionDepth
            }
        }
        if recursionDepth > 0 {
            return try body()
        }

        try prepareDirectory(for: coordinatedURL)
        let lockURL = coordinationLockURL(for: coordinatedURL)
        let descriptor = lockURL.path.withCString { path in
            Darwin.open(
                path,
                O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW,
                mode_t(filePermissions)
            )
        }
        guard descriptor >= 0 else {
            throw posixError("open runtime event log coordination lock")
        }
        defer { Darwin.close(descriptor) }
        guard Darwin.fchmod(descriptor, mode_t(filePermissions)) == 0 else {
            throw posixError("secure runtime event log coordination lock")
        }
        var fileLock = Darwin.flock()
        fileLock.l_type = Int16(F_WRLCK)
        fileLock.l_whence = Int16(SEEK_SET)
        fileLock.l_start = 0
        fileLock.l_len = 0
        while Darwin.fcntl(descriptor, F_SETLKW, &fileLock) != 0 {
            guard errno == EINTR else {
                throw posixError("lock runtime event log")
            }
        }
        defer {
            fileLock.l_type = Int16(F_UNLCK)
            _ = Darwin.fcntl(descriptor, F_SETLK, &fileLock)
        }
        return try body()
    }

    private static func appendLineWithoutCoordination(_ line: Data, to fileURL: URL) throws {
        try prepareDirectory(for: fileURL)

        if FileManager.default.fileExists(atPath: fileURL.path) {
            try secureFile(at: fileURL)
            let handle = try FileHandle(forWritingTo: fileURL)
            defer { try? handle.close() }
            try handle.seekToEnd()
            try handle.write(contentsOf: line)
            try secureFile(at: fileURL)
        } else {
            let created = FileManager.default.createFile(
                atPath: fileURL.path,
                contents: line,
                attributes: [.posixPermissions: filePermissions]
            )
            if !created {
                try secureFile(at: fileURL)
                let handle = try FileHandle(forWritingTo: fileURL)
                defer { try? handle.close() }
                try handle.seekToEnd()
                try handle.write(contentsOf: line)
            }
            try secureFile(at: fileURL)
        }
    }

    static func prepareDirectory(for fileURL: URL) throws {
        let directory = fileURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: directoryPermissions]
        )
        try FileManager.default.setAttributes(
            [.posixPermissions: directoryPermissions],
            ofItemAtPath: directory.path
        )
    }

    static func secureFile(at fileURL: URL) throws {
        try FileManager.default.setAttributes(
            [.posixPermissions: filePermissions],
            ofItemAtPath: fileURL.path
        )
    }

    private static func canonicalFileURL(_ fileURL: URL) -> URL {
        let standardizedURL = fileURL.standardizedFileURL
        let directoryURL = standardizedURL
            .deletingLastPathComponent()
            .resolvingSymlinksInPath()
        return directoryURL.appendingPathComponent(standardizedURL.lastPathComponent)
    }

    private static func coordinationLockURL(for fileURL: URL) -> URL {
        fileURL.deletingLastPathComponent().appendingPathComponent(
            ".\(fileURL.lastPathComponent).coordination.lock",
            isDirectory: false
        )
    }

    private static func pathLock(for path: String) -> NSRecursiveLock {
        pathLocksGuard.lock()
        defer { pathLocksGuard.unlock() }
        if let existing = pathLocks[path] {
            return existing
        }
        let created = NSRecursiveLock()
        created.name = "RuntimeEventLogFileProtection:\(path)"
        pathLocks[path] = created
        return created
    }

    private static func posixError(_ operation: String) -> NSError {
        let code = errno
        return NSError(
            domain: NSPOSIXErrorDomain,
            code: Int(code),
            userInfo: [
                NSLocalizedDescriptionKey: "Could not \(operation): \(String(cString: strerror(code)))"
            ]
        )
    }

    private static let pathLocksGuard = NSLock()
    private static var pathLocks: [String: NSRecursiveLock] = [:]
}
