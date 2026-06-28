import Foundation

enum RuntimeEventLogFileProtection {
    static let directoryPermissions = 0o700
    static let filePermissions = 0o600

    static func appendLine(_ line: Data, to fileURL: URL) throws {
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

    private static func prepareDirectory(for fileURL: URL) throws {
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

    private static func secureFile(at fileURL: URL) throws {
        try FileManager.default.setAttributes(
            [.posixPermissions: filePermissions],
            ofItemAtPath: fileURL.path
        )
    }
}
