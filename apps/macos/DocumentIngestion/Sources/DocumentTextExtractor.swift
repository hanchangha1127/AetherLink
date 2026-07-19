import Foundation
import PDFKit
import Darwin

public struct ExtractedDocument: Equatable, Sendable {
    public var fileName: String
    public var mimeType: String
    public var text: String

    public init(fileName: String, mimeType: String, text: String) {
        self.fileName = fileName
        self.mimeType = mimeType
        self.text = text
    }
}

public let documentIngestionResourcePolicyMaxInputBytesCeiling = 32 * 1024 * 1024
public let documentIngestionResourcePolicyMaxArchiveListingBytesCeiling = 1 * 1024 * 1024
public let documentIngestionArchiveEntryNameCharacterLimitCeiling = 512
public let documentIngestionResourcePolicyMaxArchiveEntriesCeiling = 512
public let documentIngestionResourcePolicyMaxArchiveEntryBytesCeiling = 8 * 1024 * 1024
public let documentIngestionResourcePolicyMaxConverterOutputBytesCeiling = 8 * 1024 * 1024
public let documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling = 200_000
public let documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling = 1 * 1024 * 1024
let documentIngestionProcessTimeout: TimeInterval = 30

public struct DocumentIngestionResourcePolicy: Equatable, Sendable {
    public static let standard = DocumentIngestionResourcePolicy()

    public var maxInputBytes: Int
    public var maxArchiveListingBytes: Int
    public var maxArchiveEntries: Int
    public var maxArchiveEntryBytes: Int
    public var maxConverterOutputBytes: Int
    public var maxExtractedTextCharacters: Int
    public var maxExtractedTextUTF8Bytes: Int

    public init(
        maxInputBytes: Int = documentIngestionResourcePolicyMaxInputBytesCeiling,
        maxArchiveListingBytes: Int = documentIngestionResourcePolicyMaxArchiveListingBytesCeiling,
        maxArchiveEntries: Int = documentIngestionResourcePolicyMaxArchiveEntriesCeiling,
        maxArchiveEntryBytes: Int = documentIngestionResourcePolicyMaxArchiveEntryBytesCeiling,
        maxConverterOutputBytes: Int = documentIngestionResourcePolicyMaxConverterOutputBytesCeiling,
        maxExtractedTextCharacters: Int = documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling,
        maxExtractedTextUTF8Bytes: Int = documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling
    ) {
        self.maxInputBytes = maxInputBytes
        self.maxArchiveListingBytes = maxArchiveListingBytes
        self.maxArchiveEntries = maxArchiveEntries
        self.maxArchiveEntryBytes = maxArchiveEntryBytes
        self.maxConverterOutputBytes = maxConverterOutputBytes
        self.maxExtractedTextCharacters = maxExtractedTextCharacters
        self.maxExtractedTextUTF8Bytes = maxExtractedTextUTF8Bytes
    }
}

public enum DocumentIngestionError: Error, Equatable, LocalizedError, Sendable {
    case unsupportedFileType(String)
    case unreadablePDF(String)
    case archiveListingFailed(String)
    case archiveEntryReadFailed(String)
    case converterFailed(String)
    case noExtractableText(String)
    case resourceLimitExceeded(resource: String, limit: Int, actual: Int)
    case invalidResourcePolicy(String)

    public var errorDescription: String? {
        switch self {
        case .unsupportedFileType(let path):
            return "Unsupported document type: \(path)"
        case .unreadablePDF(let path):
            return "Could not read PDF document: \(path)"
        case .archiveListingFailed(let path):
            return "Could not list document archive: \(path)"
        case .archiveEntryReadFailed(let entry):
            return "Could not read document archive entry: \(entry)"
        case .converterFailed(let path):
            return "Could not convert document to text: \(path)"
        case .noExtractableText(let path):
            return "No extractable document text found: \(path)"
        case .resourceLimitExceeded(let resource, let limit, let actual):
            return "Document ingestion resource limit exceeded for \(resource): \(actual) exceeded \(limit)"
        case .invalidResourcePolicy(let reason):
            return "Invalid document ingestion resource policy: \(reason)"
        }
    }
}

public enum DocumentInputValidationError: Error, Equatable, LocalizedError, Sendable {
    case unsafeInputFile(String)
    case inputReadFailed(String)

    public var errorDescription: String? {
        switch self {
        case .unsafeInputFile(let path):
            return "Document input must be a regular file without symbolic links: \(path)"
        case .inputReadFailed(let path):
            return "Could not read document input: \(path)"
        }
    }
}

struct DocumentInputSnapshotHooks: Sendable {
    var didOpenSourceDescriptor: (@Sendable (URL) throws -> Void)?

    init(didOpenSourceDescriptor: (@Sendable (URL) throws -> Void)? = nil) {
        self.didOpenSourceDescriptor = didOpenSourceDescriptor
    }
}

public final class DocumentTextExtractor: Sendable {
    private let resourcePolicy: DocumentIngestionResourcePolicy
    private let snapshotHooks: DocumentInputSnapshotHooks

    public init(resourcePolicy: DocumentIngestionResourcePolicy = .standard) {
        self.resourcePolicy = resourcePolicy
        snapshotHooks = DocumentInputSnapshotHooks()
    }

    init(
        resourcePolicy: DocumentIngestionResourcePolicy = .standard,
        snapshotHooks: DocumentInputSnapshotHooks
    ) {
        self.resourcePolicy = resourcePolicy
        self.snapshotHooks = snapshotHooks
    }

    public func extractText(from fileURL: URL, mimeType: String? = nil) throws -> ExtractedDocument {
        try validateResourcePolicy(resourcePolicy)
        let processDeadline = try DocumentProcessDeadline(timeout: documentIngestionProcessTimeout)
        let kind = DocumentKind(fileURL: fileURL, mimeType: mimeType)
        if case .unsupported = kind {
            throw DocumentIngestionError.unsupportedFileType(fileURL.path)
        }
        let snapshot = try makePrivateDocumentInputSnapshot(
            of: fileURL,
            byteLimit: resourcePolicy.maxInputBytes,
            deadline: processDeadline,
            hooks: snapshotHooks
        )
        let snapshotURL = snapshot.fileURL
        let text: String
        switch kind {
        case .pdf:
            text = try extractPDFText(
                from: snapshotURL,
                displayPath: fileURL.path,
                processDeadline: processDeadline
            )
        case .docx:
            text = try extractZippedText(
                from: snapshotURL,
                displayPath: fileURL.path,
                preferredEntries: ["word/document.xml"],
                fallbackEntryPrefixes: ["word/"],
                allowedPathExtensions: ["xml"],
                processDeadline: processDeadline
            )
        case .hwpx:
            text = try extractZippedText(
                from: snapshotURL,
                displayPath: fileURL.path,
                preferredEntries: ["Contents/section0.xml"],
                fallbackEntryPrefixes: ["Contents/"],
                allowedPathExtensions: ["xml"],
                processDeadline: processDeadline
            )
        case .odt:
            text = try extractZippedText(
                from: snapshotURL,
                displayPath: fileURL.path,
                preferredEntries: ["content.xml"],
                fallbackEntryPrefixes: [],
                allowedPathExtensions: ["xml"],
                processDeadline: processDeadline
            )
        case .ods, .odp:
            text = try extractZippedText(
                from: snapshotURL,
                displayPath: fileURL.path,
                preferredEntries: ["content.xml"],
                fallbackEntryPrefixes: [],
                allowedPathExtensions: ["xml"],
                processDeadline: processDeadline
            )
        case .xlsx:
            text = try extractZippedText(
                from: snapshotURL,
                displayPath: fileURL.path,
                preferredEntries: ["xl/sharedStrings.xml"],
                fallbackEntryPrefixes: ["xl/worksheets/"],
                allowedPathExtensions: ["xml"],
                processDeadline: processDeadline
            )
        case .pptx:
            text = try extractZippedText(
                from: snapshotURL,
                displayPath: fileURL.path,
                preferredEntries: [],
                fallbackEntryPrefixes: ["ppt/slides/", "ppt/notesSlides/"],
                allowedPathExtensions: ["xml"],
                processDeadline: processDeadline
            )
        case .epub:
            text = try extractZippedText(
                from: snapshotURL,
                displayPath: fileURL.path,
                preferredEntries: [],
                fallbackEntryPrefixes: [],
                allowedPathExtensions: ["xhtml", "html", "htm", "xml", "opf", "txt"],
                processDeadline: processDeadline
            )
        case .pages, .numbers, .keynote:
            text = try extractZippedText(
                from: snapshotURL,
                displayPath: fileURL.path,
                preferredEntries: ["index.xml"],
                fallbackEntryPrefixes: [],
                allowedPathExtensions: ["xml", "xhtml", "html", "htm", "txt"],
                processDeadline: processDeadline
            )
        case .rtf:
            text = try extractRTFText(from: snapshotURL, processDeadline: processDeadline)
        case .html:
            text = try extractHTMLText(from: snapshotURL, processDeadline: processDeadline)
        case .legacyWord, .webArchive:
            text = try extractTextutilText(
                from: snapshotURL,
                displayPath: fileURL.path,
                processDeadline: processDeadline
            )
        case .legacySpreadsheet, .legacyPresentation, .legacyHWP:
            text = try extractBinaryText(from: snapshotURL, processDeadline: processDeadline)
        case .hwpml, .xml:
            text = XMLTextCollector.collectText(from: try readSnapshotData(
                snapshotURL,
                limit: resourcePolicy.maxInputBytes,
                deadline: processDeadline
            ))
        case .plainText:
            let data = try readSnapshotData(
                snapshotURL,
                limit: resourcePolicy.maxInputBytes,
                deadline: processDeadline
            )
            guard let decoded = String(data: data, encoding: .utf8) else {
                throw DocumentInputValidationError.inputReadFailed(fileURL.path)
            }
            text = decoded
        case .unsupported:
            throw DocumentIngestionError.unsupportedFileType(fileURL.path)
        }
        _ = try processDeadline.remainingNanoseconds(outputResource: "document extraction")

        let normalizedText = normalizeWhitespace(text)
        try validateExtractedTextResourceLimits(
            normalizedText,
            characterLimit: resourcePolicy.maxExtractedTextCharacters,
            utf8ByteLimit: resourcePolicy.maxExtractedTextUTF8Bytes
        )
        guard !normalizedText.isEmpty else {
            throw DocumentIngestionError.noExtractableText(fileURL.path)
        }

        return ExtractedDocument(
            fileName: fileURL.lastPathComponent,
            mimeType: kind.mimeType,
            text: normalizedText
        )
    }

    private func extractPDFText(
        from fileURL: URL,
        displayPath: String,
        processDeadline: DocumentProcessDeadline
    ) throws -> String {
        guard let document = PDFDocument(url: fileURL) else {
            throw DocumentIngestionError.unreadablePDF(displayPath)
        }
        var accumulator = BoundedExtractedTextAccumulator(
            characterLimit: resourcePolicy.maxExtractedTextCharacters,
            utf8ByteLimit: resourcePolicy.maxExtractedTextUTF8Bytes
        )
        for pageIndex in 0..<document.pageCount {
            _ = try processDeadline.remainingNanoseconds(outputResource: "PDF extraction")
            if let pageText = document.page(at: pageIndex)?.string {
                try accumulator.append(pageText)
            }
        }
        return accumulator.text
    }

    private func extractZippedText(
        from fileURL: URL,
        displayPath: String,
        preferredEntries: [String],
        fallbackEntryPrefixes: [String],
        allowedPathExtensions: Set<String>,
        processDeadline: DocumentProcessDeadline
    ) throws -> String {
        let entries = try archiveEntries(
            fileURL,
            displayPath: displayPath,
            processDeadline: processDeadline
        ).filter(isCanonicalArchiveEntryPath)
        let selectedEntries = preferredEntries.filter(entries.contains)
        let fallbackEntries = entries
            .filter { entry in
                let lowercasedEntry = entry.lowercased()
                let pathExtension = URL(fileURLWithPath: lowercasedEntry).pathExtension
                let prefixAllowed = fallbackEntryPrefixes.isEmpty ||
                    fallbackEntryPrefixes.contains(where: entry.hasPrefix)
                return prefixAllowed &&
                    allowedPathExtensions.contains(pathExtension) &&
                    !lowercasedEntry.contains("/_rels/") &&
                    !lowercasedEntry.hasPrefix("__macosx/") &&
                    lowercasedEntry != "[content_types].xml"
            }
            .sorted()
        let xmlEntries = (selectedEntries + fallbackEntries).reduce(into: [String]()) { result, entry in
            if !result.contains(entry) {
                result.append(entry)
            }
        }
        try enforceCountLimit(
            xmlEntries.count,
            resource: "archive entries",
            limit: resourcePolicy.maxArchiveEntries
        )

        var accumulator = BoundedExtractedTextAccumulator(
            characterLimit: resourcePolicy.maxExtractedTextCharacters,
            utf8ByteLimit: resourcePolicy.maxExtractedTextUTF8Bytes
        )
        for entry in xmlEntries {
            let data = try archiveEntryData(
                fileURL,
                entry: entry,
                processDeadline: processDeadline
            )
            try accumulator.append(extractText(fromArchiveEntry: entry, data: data))
        }
        return accumulator.text
    }

    private func extractText(fromArchiveEntry entry: String, data: Data) -> String {
        let pathExtension = URL(fileURLWithPath: entry.lowercased()).pathExtension
        switch pathExtension {
        case "html", "htm", "xhtml":
            return String(data: data, encoding: .utf8).map(stripHTMLTags) ?? ""
        case "txt":
            return String(data: data, encoding: .utf8) ?? ""
        default:
            return XMLTextCollector.collectText(from: data)
        }
    }

    private func extractRTFText(
        from fileURL: URL,
        processDeadline: DocumentProcessDeadline
    ) throws -> String {
        let data = try readSnapshotData(
            fileURL,
            limit: resourcePolicy.maxInputBytes,
            deadline: processDeadline
        )
        let attributed = try NSAttributedString(
            data: data,
            options: [.documentType: NSAttributedString.DocumentType.rtf],
            documentAttributes: nil
        )
        return attributed.string
    }

    private func extractHTMLText(
        from fileURL: URL,
        processDeadline: DocumentProcessDeadline
    ) throws -> String {
        let data = try readSnapshotData(
            fileURL,
            limit: resourcePolicy.maxInputBytes,
            deadline: processDeadline
        )
        if let attributed = try? NSAttributedString(
            data: data,
            options: [.documentType: NSAttributedString.DocumentType.html],
            documentAttributes: nil
        ) {
            return attributed.string
        }
        if let html = String(data: data, encoding: .utf8) {
            return stripHTMLTags(html)
        }
        return ""
    }

    private func extractTextutilText(
        from fileURL: URL,
        displayPath: String,
        processDeadline: DocumentProcessDeadline
    ) throws -> String {
        let data = try runTextutil(
            arguments: ["-convert", "txt", "-stdout", fileURL.path],
            outputResource: "textutil output",
            displayPath: displayPath,
            processDeadline: processDeadline
        )
        return String(data: data, encoding: .utf8) ?? String(decoding: data, as: UTF8.self)
    }

    private func extractBinaryText(
        from fileURL: URL,
        processDeadline: DocumentProcessDeadline
    ) throws -> String {
        let data = try readSnapshotData(
            fileURL,
            limit: resourcePolicy.maxInputBytes,
            deadline: processDeadline
        )
        let byteStrings = extractPrintableByteStrings(from: data)
        let utf16Strings = extractPrintableUTF16LEStrings(from: data)
        return uniqueTextParts(byteStrings + utf16Strings).joined(separator: "\n")
    }

    private func archiveEntries(
        _ fileURL: URL,
        displayPath: String,
        processDeadline: DocumentProcessDeadline
    ) throws -> [String] {
        let data = try runUnzip(
            arguments: ["-Z1", fileURL.path],
            error: .archiveListingFailed(displayPath),
            outputResource: "archive listing",
            processDeadline: processDeadline
        )
        guard let output = String(data: data, encoding: .utf8) else {
            throw DocumentIngestionError.archiveListingFailed(displayPath)
        }
        return output
            .split(separator: "\n")
            .map(String.init)
            .filter { !$0.isEmpty }
    }

    private func archiveEntryData(
        _ fileURL: URL,
        entry: String,
        processDeadline: DocumentProcessDeadline
    ) throws -> Data {
        try runUnzip(
            arguments: ["-p", fileURL.path, entry],
            error: .archiveEntryReadFailed(entry),
            outputResource: "archive entry \(entry)",
            processDeadline: processDeadline
        )
    }

    private func runUnzip(
        arguments: [String],
        error: DocumentIngestionError,
        outputResource: String,
        processDeadline: DocumentProcessDeadline
    ) throws -> Data {
        let result: DocumentProcessResult
        do {
            result = try runBoundedDocumentProcess(
                executableURL: URL(fileURLWithPath: "/usr/bin/unzip"),
                arguments: arguments,
                outputResource: outputResource,
                outputLimit: outputResource == "archive listing"
                    ? resourcePolicy.maxArchiveListingBytes
                    : resourcePolicy.maxArchiveEntryBytes,
                deadline: processDeadline
            )
        } catch is DocumentProcessError {
            throw error
        }
        guard result.terminationStatus == 0 else {
            throw error
        }
        return result.standardOutput
    }

    private func runTextutil(
        arguments: [String],
        outputResource: String,
        displayPath: String,
        processDeadline: DocumentProcessDeadline
    ) throws -> Data {
        let result: DocumentProcessResult
        do {
            result = try runBoundedDocumentProcess(
                executableURL: URL(fileURLWithPath: "/usr/bin/textutil"),
                arguments: arguments,
                outputResource: outputResource,
                outputLimit: resourcePolicy.maxConverterOutputBytes,
                deadline: processDeadline
            )
        } catch is DocumentProcessError {
            throw DocumentIngestionError.converterFailed(displayPath)
        }
        guard result.terminationStatus == 0 else {
            throw DocumentIngestionError.converterFailed(displayPath)
        }
        return result.standardOutput
    }
}

private func validateResourcePolicy(_ policy: DocumentIngestionResourcePolicy) throws {
    try validatePositiveCeiling(
        policy.maxInputBytes,
        name: "maxInputBytes",
        ceiling: documentIngestionResourcePolicyMaxInputBytesCeiling
    )
    try validatePositiveCeiling(
        policy.maxArchiveListingBytes,
        name: "maxArchiveListingBytes",
        ceiling: documentIngestionResourcePolicyMaxArchiveListingBytesCeiling
    )
    try validatePositiveCeiling(
        policy.maxArchiveEntries,
        name: "maxArchiveEntries",
        ceiling: documentIngestionResourcePolicyMaxArchiveEntriesCeiling
    )
    try validatePositiveCeiling(
        policy.maxArchiveEntryBytes,
        name: "maxArchiveEntryBytes",
        ceiling: documentIngestionResourcePolicyMaxArchiveEntryBytesCeiling
    )
    try validatePositiveCeiling(
        policy.maxConverterOutputBytes,
        name: "maxConverterOutputBytes",
        ceiling: documentIngestionResourcePolicyMaxConverterOutputBytesCeiling
    )
    try validatePositiveCeiling(
        policy.maxExtractedTextCharacters,
        name: "maxExtractedTextCharacters",
        ceiling: documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling
    )
    try validatePositiveCeiling(
        policy.maxExtractedTextUTF8Bytes,
        name: "maxExtractedTextUTF8Bytes",
        ceiling: documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling
    )
}

private func validatePositiveCeiling(_ value: Int, name: String, ceiling: Int) throws {
    guard value > 0 else {
        throw DocumentIngestionError.invalidResourcePolicy("\(name) must be greater than zero")
    }
    guard value <= ceiling else {
        throw DocumentIngestionError.invalidResourcePolicy("\(name) must be less than or equal to \(ceiling)")
    }
}

private final class PrivateDocumentInputSnapshot {
    let fileURL: URL
    private let directoryURL: URL

    init(fileURL: URL, directoryURL: URL) {
        self.fileURL = fileURL
        self.directoryURL = directoryURL
    }

    deinit {
        try? FileManager.default.removeItem(at: directoryURL)
    }
}

private func makePrivateDocumentInputSnapshot(
    of sourceURL: URL,
    byteLimit: Int,
    deadline: DocumentProcessDeadline,
    hooks: DocumentInputSnapshotHooks
) throws -> PrivateDocumentInputSnapshot {
    guard sourceURL.isFileURL else {
        throw DocumentInputValidationError.unsafeInputFile(sourceURL.path)
    }
    var pathMetadata = stat()
    guard Darwin.lstat(sourceURL.path, &pathMetadata) == 0 else {
        throw DocumentInputValidationError.inputReadFailed(sourceURL.path)
    }
    guard pathMetadata.st_mode & S_IFMT == S_IFREG else {
        throw DocumentInputValidationError.unsafeInputFile(sourceURL.path)
    }
    let sourceDescriptor = Darwin.open(
        sourceURL.path,
        O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK
    )
    guard sourceDescriptor >= 0 else {
        if errno == ELOOP {
            throw DocumentInputValidationError.unsafeInputFile(sourceURL.path)
        }
        throw DocumentInputValidationError.inputReadFailed(sourceURL.path)
    }
    defer { Darwin.close(sourceDescriptor) }

    var sourceMetadata = stat()
    guard Darwin.fstat(sourceDescriptor, &sourceMetadata) == 0 else {
        throw DocumentInputValidationError.inputReadFailed(sourceURL.path)
    }
    guard sourceMetadata.st_mode & S_IFMT == S_IFREG else {
        throw DocumentInputValidationError.unsafeInputFile(sourceURL.path)
    }
    guard sourceMetadata.st_size >= 0 else {
        throw DocumentInputValidationError.unsafeInputFile(sourceURL.path)
    }
    if UInt64(sourceMetadata.st_size) > UInt64(byteLimit) {
        throw DocumentIngestionError.resourceLimitExceeded(
            resource: "input file",
            limit: byteLimit,
            actual: boundedDocumentActualCount(sourceMetadata.st_size)
        )
    }
    try hooks.didOpenSourceDescriptor?(sourceURL)
    _ = try deadline.remainingNanoseconds(outputResource: "input file snapshot")

    let directoryURL = FileManager.default.temporaryDirectory
        .appendingPathComponent(
            "aetherlink-document-snapshot-\(UUID().uuidString)",
            isDirectory: true
        )
    do {
        try FileManager.default.createDirectory(
            at: directoryURL,
            withIntermediateDirectories: false,
            attributes: [.posixPermissions: 0o700]
        )
    } catch {
        throw DocumentInputValidationError.inputReadFailed(sourceURL.path)
    }
    var shouldRemoveDirectory = true
    defer {
        if shouldRemoveDirectory {
            try? FileManager.default.removeItem(at: directoryURL)
        }
    }

    let directoryDescriptor = Darwin.open(
        directoryURL.path,
        O_RDONLY | O_CLOEXEC | O_NOFOLLOW
    )
    guard directoryDescriptor >= 0 else {
        throw DocumentInputValidationError.inputReadFailed(sourceURL.path)
    }
    defer { Darwin.close(directoryDescriptor) }
    try secureDocumentSnapshotDescriptor(
        directoryDescriptor,
        expectedType: S_IFDIR,
        permissions: 0o700,
        displayPath: sourceURL.path
    )

    let snapshotName = privateSnapshotFileName(for: sourceURL)
    let snapshotDescriptor = Darwin.openat(
        directoryDescriptor,
        snapshotName,
        O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW,
        0o600
    )
    guard snapshotDescriptor >= 0 else {
        throw DocumentInputValidationError.inputReadFailed(sourceURL.path)
    }
    defer { Darwin.close(snapshotDescriptor) }
    try secureDocumentSnapshotDescriptor(
        snapshotDescriptor,
        expectedType: S_IFREG,
        permissions: 0o600,
        displayPath: sourceURL.path
    )

    var buffer = [UInt8](repeating: 0, count: 64 * 1024)
    var totalBytes = 0
    while true {
        _ = try deadline.remainingNanoseconds(outputResource: "input file snapshot")
        let remainingWithSentinel = byteLimit - totalBytes + 1
        let requestedCount = min(buffer.count, remainingWithSentinel)
        let count = Darwin.read(sourceDescriptor, &buffer, requestedCount)
        if count < 0 && errno == EINTR { continue }
        guard count >= 0 else {
            throw DocumentInputValidationError.inputReadFailed(sourceURL.path)
        }
        guard count > 0 else { break }

        let actualBytes = totalBytes + count
        guard actualBytes <= byteLimit else {
            throw DocumentIngestionError.resourceLimitExceeded(
                resource: "input file",
                limit: byteLimit,
                actual: actualBytes
            )
        }
        try writeDocumentSnapshotBytes(
            buffer,
            count: count,
            to: snapshotDescriptor,
            displayPath: sourceURL.path
        )
        totalBytes = actualBytes
    }
    shouldRemoveDirectory = false
    return PrivateDocumentInputSnapshot(
        fileURL: directoryURL.appendingPathComponent(snapshotName),
        directoryURL: directoryURL
    )
}

private func readSnapshotData(
    _ fileURL: URL,
    limit: Int,
    deadline: DocumentProcessDeadline
) throws -> Data {
    let descriptor = Darwin.open(
        fileURL.path,
        O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK
    )
    guard descriptor >= 0 else {
        throw DocumentInputValidationError.inputReadFailed(fileURL.path)
    }
    defer { Darwin.close(descriptor) }

    var metadata = stat()
    guard Darwin.fstat(descriptor, &metadata) == 0,
          metadata.st_mode & S_IFMT == S_IFREG,
          metadata.st_size >= 0
    else {
        throw DocumentInputValidationError.unsafeInputFile(fileURL.path)
    }
    if UInt64(metadata.st_size) > UInt64(limit) {
        throw DocumentIngestionError.resourceLimitExceeded(
            resource: "input file",
            limit: limit,
            actual: boundedDocumentActualCount(metadata.st_size)
        )
    }

    var data = Data()
    data.reserveCapacity(Int(metadata.st_size))
    var buffer = [UInt8](repeating: 0, count: 64 * 1024)
    while true {
        _ = try deadline.remainingNanoseconds(outputResource: "input file snapshot")
        let requestedCount = min(buffer.count, limit - data.count + 1)
        let count = Darwin.read(descriptor, &buffer, requestedCount)
        if count < 0 && errno == EINTR { continue }
        guard count >= 0 else {
            throw DocumentInputValidationError.inputReadFailed(fileURL.path)
        }
        guard count > 0 else { return data }
        let actualBytes = data.count + count
        guard actualBytes <= limit else {
            throw DocumentIngestionError.resourceLimitExceeded(
                resource: "input file",
                limit: limit,
                actual: actualBytes
            )
        }
        data.append(contentsOf: buffer[0..<count])
    }
}

private func secureDocumentSnapshotDescriptor(
    _ descriptor: Int32,
    expectedType: mode_t,
    permissions: mode_t,
    displayPath: String
) throws {
    var metadata = stat()
    guard Darwin.fstat(descriptor, &metadata) == 0,
          metadata.st_uid == geteuid(),
          metadata.st_mode & S_IFMT == expectedType,
          Darwin.fchmod(descriptor, permissions) == 0,
          removeDocumentSnapshotExtendedACL(descriptor)
    else {
        throw DocumentInputValidationError.inputReadFailed(displayPath)
    }
}

private func removeDocumentSnapshotExtendedACL(_ descriptor: Int32) -> Bool {
    guard let emptyACL = Darwin.acl_init(0) else { return false }
    defer { Darwin.acl_free(UnsafeMutableRawPointer(emptyACL)) }
    while Darwin.acl_set_fd_np(descriptor, emptyACL, ACL_TYPE_EXTENDED) != 0 {
        if errno != EINTR { return false }
    }
    return true
}

private func writeDocumentSnapshotBytes(
    _ bytes: [UInt8],
    count: Int,
    to descriptor: Int32,
    displayPath: String
) throws {
    var offset = 0
    while offset < count {
        let written = bytes.withUnsafeBytes { buffer in
            Darwin.write(
                descriptor,
                buffer.baseAddress?.advanced(by: offset),
                count - offset
            )
        }
        if written < 0 && errno == EINTR { continue }
        guard written > 0 else {
            throw DocumentInputValidationError.inputReadFailed(displayPath)
        }
        offset += written
    }
}

private func privateSnapshotFileName(for sourceURL: URL) -> String {
    let pathExtension = sourceURL.pathExtension.lowercased()
    let isSafeExtension = !pathExtension.isEmpty
        && pathExtension.utf8.count <= 16
        && pathExtension.unicodeScalars.allSatisfy {
            CharacterSet.alphanumerics.contains($0)
        }
    return isSafeExtension ? "input.\(pathExtension)" : "input.document"
}

private func boundedDocumentActualCount(_ value: off_t) -> Int {
    value > off_t(Int.max) ? Int.max : Int(value)
}

struct DocumentProcessResult: Sendable {
    var standardOutput: Data
    var terminationStatus: Int32
}

enum DocumentProcessError: Error, Equatable, Sendable {
    case timedOut(String)
}

struct DocumentProcessDeadline: Sendable {
    private let deadlineNanoseconds: UInt64
    private let nowNanoseconds: @Sendable () -> UInt64

    init(
        timeout: TimeInterval,
        nowNanoseconds: @escaping @Sendable () -> UInt64 = {
            DispatchTime.now().uptimeNanoseconds
        }
    ) throws {
        guard timeout > 0, timeout.isFinite else {
            throw DocumentProcessError.timedOut("document extraction")
        }
        let durationDouble = (timeout * 1_000_000_000).rounded(.up)
        guard durationDouble.isFinite,
              durationDouble > 0,
              durationDouble < Double(UInt64.max)
        else {
            throw DocumentProcessError.timedOut("document extraction")
        }
        let durationNanoseconds = UInt64(durationDouble)
        let started = nowNanoseconds()
        let deadline = started.addingReportingOverflow(durationNanoseconds)
        guard !deadline.overflow else {
            throw DocumentProcessError.timedOut("document extraction")
        }
        deadlineNanoseconds = deadline.partialValue
        self.nowNanoseconds = nowNanoseconds
    }

    func remainingNanoseconds(outputResource: String) throws -> UInt64 {
        let now = nowNanoseconds()
        guard now < deadlineNanoseconds else {
            throw DocumentProcessError.timedOut(outputResource)
        }
        return deadlineNanoseconds - now
    }
}

func runBoundedDocumentProcess(
    executableURL: URL,
    arguments: [String],
    outputResource: String,
    outputLimit: Int,
    timeout: TimeInterval
) throws -> DocumentProcessResult {
    try runBoundedDocumentProcess(
        executableURL: executableURL,
        arguments: arguments,
        outputResource: outputResource,
        outputLimit: outputLimit,
        deadline: DocumentProcessDeadline(timeout: timeout)
    )
}

func runBoundedDocumentProcess(
    executableURL: URL,
    arguments: [String],
    outputResource: String,
    outputLimit: Int,
    deadline: DocumentProcessDeadline
) throws -> DocumentProcessResult {
    precondition(outputLimit > 0)
    _ = try deadline.remainingNanoseconds(outputResource: outputResource)

    let process = Process()
    process.executableURL = executableURL
    process.arguments = arguments
    process.standardInput = FileHandle.nullDevice

    let outputPipe = Pipe()
    let errorPipe = Pipe()
    process.standardOutput = outputPipe
    process.standardError = errorPipe

    let termination = DispatchSemaphore(value: 0)
    process.terminationHandler = { _ in termination.signal() }
    try process.run()
    try? outputPipe.fileHandleForWriting.close()
    try? errorPipe.fileHandleForWriting.close()

    let capture = BoundedDocumentProcessOutput(limit: outputLimit)
    let drains = DispatchGroup()
    drains.enter()
    DispatchQueue.global(qos: .utility).async {
        capture.read(from: outputPipe.fileHandleForReading)
        drains.leave()
    }
    drains.enter()
    DispatchQueue.global(qos: .utility).async {
        drainDocumentProcessDiagnostics(from: errorPipe.fileHandleForReading)
        drains.leave()
    }

    var didExit = false
    var exceededOutputLimit: Int?
    while !didExit {
        if let actual = capture.limitExceededActualCount {
            exceededOutputLimit = actual
            break
        }

        guard let remainingNanoseconds = try? deadline.remainingNanoseconds(
            outputResource: outputResource
        ) else {
            break
        }
        let waitNanoseconds = min(remainingNanoseconds, 10_000_000)
        didExit = termination.wait(
            timeout: .now() + .nanoseconds(Int(waitNanoseconds))
        ) == .success
    }

    if !didExit {
        _ = terminateAndReapDocumentProcess(process, termination: termination)
    }

    if drains.wait(timeout: .now() + .seconds(2)) == .timedOut {
        try? outputPipe.fileHandleForReading.close()
        try? errorPipe.fileHandleForReading.close()
        throw DocumentProcessError.timedOut(outputResource)
    }

    if let actual = exceededOutputLimit ?? capture.limitExceededActualCount {
        throw DocumentIngestionError.resourceLimitExceeded(
            resource: outputResource,
            limit: outputLimit,
            actual: actual
        )
    }
    guard didExit else {
        throw DocumentProcessError.timedOut(outputResource)
    }

    return DocumentProcessResult(
        standardOutput: capture.data,
        terminationStatus: process.terminationStatus
    )
}

private final class BoundedDocumentProcessOutput: @unchecked Sendable {
    private let limit: Int
    private let lock = NSLock()
    private var storage = Data()
    private var exceededActualCount: Int?

    init(limit: Int) {
        self.limit = limit
        storage.reserveCapacity(min(limit, 64 * 1024))
    }

    var data: Data {
        lock.withLock { storage }
    }

    var limitExceededActualCount: Int? {
        lock.withLock { exceededActualCount }
    }

    func read(from handle: FileHandle) {
        defer { try? handle.close() }
        while true {
            let chunk = handle.readData(ofLength: 64 * 1024)
            guard !chunk.isEmpty else { return }
            let shouldContinue = lock.withLock { () -> Bool in
                let actualCount = storage.count + chunk.count
                guard actualCount <= limit else {
                    exceededActualCount = actualCount
                    return false
                }
                storage.append(chunk)
                return true
            }
            guard shouldContinue else { return }
        }
    }
}

private func drainDocumentProcessDiagnostics(from handle: FileHandle) {
    defer { try? handle.close() }
    while !handle.readData(ofLength: 64 * 1024).isEmpty {}
}

private func terminateAndReapDocumentProcess(
    _ process: Process,
    termination: DispatchSemaphore
) -> Bool {
    if process.isRunning {
        process.terminate()
    }
    if termination.wait(timeout: .now() + .milliseconds(200)) == .success {
        return true
    }
    if process.isRunning {
        _ = Darwin.kill(process.processIdentifier, SIGKILL)
    }
    return termination.wait(timeout: .now() + .seconds(2)) == .success
}

private func enforceDataLimit(_ data: Data, resource: String, limit: Int) throws {
    guard data.count <= limit else {
        throw DocumentIngestionError.resourceLimitExceeded(
            resource: resource,
            limit: limit,
            actual: data.count
        )
    }
}

private func enforceCountLimit(_ count: Int, resource: String, limit: Int) throws {
    guard count <= limit else {
        throw DocumentIngestionError.resourceLimitExceeded(
            resource: resource,
            limit: limit,
            actual: count
        )
    }
}

private func enforceStringLimit(_ text: String, resource: String, limit: Int) throws {
    guard text.count <= limit else {
        throw DocumentIngestionError.resourceLimitExceeded(
            resource: resource,
            limit: limit,
            actual: text.count
        )
    }
}

private func enforceStringUTF8ByteLimit(
    _ text: String,
    resource: String,
    limit: Int
) throws {
    let byteCount = text.utf8.count
    guard byteCount <= limit else {
        throw DocumentIngestionError.resourceLimitExceeded(
            resource: resource,
            limit: limit,
            actual: byteCount
        )
    }
}

func validateExtractedTextResourceLimits(
    _ text: String,
    characterLimit: Int = documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling,
    utf8ByteLimit: Int = documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling
) throws {
    try enforceStringUTF8ByteLimit(
        text,
        resource: "extracted text UTF-8 bytes",
        limit: utf8ByteLimit
    )
    try enforceStringLimit(
        text,
        resource: "extracted text",
        limit: characterLimit
    )
}

private struct BoundedExtractedTextAccumulator {
    let characterLimit: Int
    let utf8ByteLimit: Int
    private(set) var text = ""
    private var characterCount = 0
    private var utf8ByteCount = 0

    init(characterLimit: Int, utf8ByteLimit: Int) {
        self.characterLimit = characterLimit
        self.utf8ByteLimit = utf8ByteLimit
        text.reserveCapacity(min(utf8ByteLimit, 64 * 1024))
    }

    mutating func append(_ rawText: String) throws {
        let part = normalizeWhitespace(rawText)
        guard !part.isEmpty else { return }

        let separatorCount = text.isEmpty ? 0 : 1
        let actualCharacterCount = saturatedResourceTotal(
            characterCount,
            separatorCount,
            part.count
        )
        guard actualCharacterCount <= characterLimit else {
            throw DocumentIngestionError.resourceLimitExceeded(
                resource: "extracted text",
                limit: characterLimit,
                actual: actualCharacterCount
            )
        }
        let actualUTF8ByteCount = saturatedResourceTotal(
            utf8ByteCount,
            separatorCount,
            part.utf8.count
        )
        guard actualUTF8ByteCount <= utf8ByteLimit else {
            throw DocumentIngestionError.resourceLimitExceeded(
                resource: "extracted text UTF-8 bytes",
                limit: utf8ByteLimit,
                actual: actualUTF8ByteCount
            )
        }
        if separatorCount == 1 {
            text.append(" ")
        }
        text.append(part)
        characterCount = actualCharacterCount
        utf8ByteCount = actualUTF8ByteCount
    }
}

private func saturatedResourceTotal(_ values: Int...) -> Int {
    values.reduce(0) { total, value in
        let result = total.addingReportingOverflow(value)
        return result.overflow ? Int.max : result.partialValue
    }
}

private enum DocumentKind {
    case pdf
    case docx
    case legacyWord
    case legacySpreadsheet
    case legacyPresentation
    case legacyHWP
    case hwpx
    case hwpml
    case odt
    case ods
    case odp
    case xlsx
    case pptx
    case epub
    case pages
    case numbers
    case keynote
    case rtf
    case html
    case webArchive
    case xml
    case plainText
    case unsupported

    init(fileURL: URL, mimeType: String?) {
        let ext = fileURL.pathExtension.lowercased()
        let normalizedMimeType = normalizedDocumentMimeType(mimeType)
        switch (ext, normalizedMimeType) {
        case ("pdf", _), (_, "application/pdf"):
            self = .pdf
        case ("docx", _),
            ("docm", _),
            ("dotx", _),
            ("dotm", _),
            (_, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            (_, "application/vnd.ms-word.document.macroenabled.12"),
            (_, "application/vnd.openxmlformats-officedocument.wordprocessingml.template"),
            (_, "application/vnd.ms-word.template.macroenabled.12"):
            self = .docx
        case ("doc", _), (_, "application/msword"):
            self = .legacyWord
        case ("xls", _),
            ("xlt", _),
            (_, "application/vnd.ms-excel"):
            self = .legacySpreadsheet
        case ("ppt", _),
            ("pps", _),
            ("pot", _),
            (_, "application/vnd.ms-powerpoint"):
            self = .legacyPresentation
        case ("hwp", _), (_, "application/x-hwp"), (_, "application/haansofthwp"):
            self = .legacyHWP
        case ("hwpx", _), (_, "application/hwp+zip"), (_, "application/x-hwpx"), (_, "application/vnd.hancom.hwpx"):
            self = .hwpx
        case ("hwpml", _), (_, "application/x-hwpml"), (_, "application/vnd.hancom.hwpml"):
            self = .hwpml
        case ("odt", _), (_, "application/vnd.oasis.opendocument.text"):
            self = .odt
        case ("ods", _), (_, "application/vnd.oasis.opendocument.spreadsheet"):
            self = .ods
        case ("odp", _), (_, "application/vnd.oasis.opendocument.presentation"):
            self = .odp
        case ("xlsx", _),
            ("xlsm", _),
            ("xltx", _),
            ("xltm", _),
            (_, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            (_, "application/vnd.ms-excel.sheet.macroenabled.12"),
            (_, "application/vnd.openxmlformats-officedocument.spreadsheetml.template"),
            (_, "application/vnd.ms-excel.template.macroenabled.12"):
            self = .xlsx
        case ("pptx", _),
            ("pptm", _),
            ("ppsx", _),
            ("ppsm", _),
            ("potx", _),
            ("potm", _),
            (_, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            (_, "application/vnd.ms-powerpoint.presentation.macroenabled.12"),
            (_, "application/vnd.openxmlformats-officedocument.presentationml.slideshow"),
            (_, "application/vnd.ms-powerpoint.slideshow.macroenabled.12"),
            (_, "application/vnd.openxmlformats-officedocument.presentationml.template"),
            (_, "application/vnd.ms-powerpoint.template.macroenabled.12"):
            self = .pptx
        case ("epub", _), (_, "application/epub+zip"):
            self = .epub
        case ("pages", _), (_, "application/vnd.apple.pages"):
            self = .pages
        case ("numbers", _), (_, "application/vnd.apple.numbers"):
            self = .numbers
        case ("key", _), (_, "application/vnd.apple.keynote"):
            self = .keynote
        case ("rtf", _), (_, "application/rtf"), (_, "text/rtf"):
            self = .rtf
        case ("html", _), ("htm", _), ("xhtml", _), (_, "text/html"), (_, "application/xhtml+xml"):
            self = .html
        case ("webarchive", _), (_, "application/x-webarchive"):
            self = .webArchive
        case ("xml", _), (_, "application/xml"), (_, "text/xml"):
            self = .xml
        case ("txt", _),
            ("md", _),
            ("markdown", _),
            ("rst", _),
            ("adoc", _),
            ("asciidoc", _),
            ("log", _),
            ("text", _),
            ("conf", _),
            ("ini", _),
            ("toml", _),
            ("properties", _),
            ("env", _),
            ("csv", _),
            ("tsv", _),
            ("json", _),
            ("jsonl", _),
            ("yaml", _),
            ("yml", _),
            (_, "text/plain"),
            (_, "text/markdown"),
            (_, "text/x-rst"),
            (_, "text/asciidoc"),
            (_, "text/x-log"),
            (_, "text/csv"),
            (_, "text/tab-separated-values"),
            (_, "application/json"),
            (_, "application/jsonl"),
            (_, "application/x-ndjson"),
            (_, "application/yaml"),
            (_, "application/x-yaml"),
            (_, "application/toml"),
            (_, "application/x-toml"),
            (_, "text/yaml"):
            self = .plainText
        default:
            self = .unsupported
        }
    }

    var mimeType: String {
        switch self {
        case .pdf:
            return "application/pdf"
        case .docx:
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        case .legacyWord:
            return "application/msword"
        case .legacySpreadsheet:
            return "application/vnd.ms-excel"
        case .legacyPresentation:
            return "application/vnd.ms-powerpoint"
        case .legacyHWP:
            return "application/x-hwp"
        case .hwpx:
            return "application/hwp+zip"
        case .hwpml:
            return "application/x-hwpml"
        case .odt:
            return "application/vnd.oasis.opendocument.text"
        case .ods:
            return "application/vnd.oasis.opendocument.spreadsheet"
        case .odp:
            return "application/vnd.oasis.opendocument.presentation"
        case .xlsx:
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        case .pptx:
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        case .epub:
            return "application/epub+zip"
        case .pages:
            return "application/vnd.apple.pages"
        case .numbers:
            return "application/vnd.apple.numbers"
        case .keynote:
            return "application/vnd.apple.keynote"
        case .rtf:
            return "application/rtf"
        case .html:
            return "text/html"
        case .webArchive:
            return "application/x-webarchive"
        case .xml:
            return "application/xml"
        case .plainText:
            return "text/plain"
        case .unsupported:
            return "application/octet-stream"
        }
    }
}

private func normalizedDocumentMimeType(_ mimeType: String?) -> String? {
    guard let mimeType else { return nil }
    let value = mimeType.split(
        separator: ";",
        maxSplits: 1,
        omittingEmptySubsequences: false
    ).first.map(String.init) ?? mimeType
    let normalized = value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    return normalized.isEmpty ? nil : normalized
}

private func isCanonicalArchiveEntryPath(_ entry: String) -> Bool {
    guard !entry.isEmpty else { return false }
    guard entry.count <= documentIngestionArchiveEntryNameCharacterLimitCeiling else { return false }
    guard entry.trimmingCharacters(in: .whitespacesAndNewlines) == entry else { return false }
    guard !entry.hasPrefix("/") && !entry.hasPrefix("~") else { return false }
    guard !entry.contains("\\") && !hasWindowsDrivePrefix(entry) else { return false }
    guard !entry.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else {
        return false
    }

    let components = entry.split(separator: "/", omittingEmptySubsequences: false)
    guard components.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }) else {
        return false
    }

    return true
}

private func hasWindowsDrivePrefix(_ entry: String) -> Bool {
    let scalars = Array(entry.unicodeScalars.prefix(2))
    guard scalars.count == 2 else { return false }
    let first = scalars[0].value
    return ((65...90).contains(first) || (97...122).contains(first)) && scalars[1].value == 58
}

private final class XMLTextCollector: NSObject, XMLParserDelegate {
    private var parts: [String] = []

    static func collectText(from data: Data) -> String {
        let collector = XMLTextCollector()
        let parser = XMLParser(data: data)
        parser.delegate = collector
        _ = parser.parse()
        return collector.parts.joined(separator: " ")
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) {
        let text = string.trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty {
            parts.append(text)
        }
    }
}

private func extractPrintableByteStrings(from data: Data) -> [String] {
    var parts: [String] = []
    var current: [UInt8] = []

    func flush() {
        guard current.count >= 4 else {
            current.removeAll(keepingCapacity: true)
            return
        }
        parts.append(String(decoding: current, as: UTF8.self))
        current.removeAll(keepingCapacity: true)
    }

    for byte in data {
        if byte == 0x09 || (byte >= 0x20 && byte <= 0x7E) {
            current.append(byte)
        } else {
            flush()
        }
    }
    flush()
    return parts
}

private func extractPrintableUTF16LEStrings(from data: Data) -> [String] {
    var parts: [String] = []
    var scalars: [Unicode.Scalar] = []
    var index = 0

    func flush() {
        guard scalars.count >= 4 else {
            scalars.removeAll(keepingCapacity: true)
            return
        }
        parts.append(String(String.UnicodeScalarView(scalars)))
        scalars.removeAll(keepingCapacity: true)
    }

    while index + 1 < data.count {
        let low = UInt16(data[index])
        let high = UInt16(data[index + 1]) << 8
        let value = low | high
        if isPrintableUTF16Scalar(value), let scalar = Unicode.Scalar(UInt32(value)) {
            scalars.append(scalar)
        } else {
            flush()
        }
        index += 2
    }
    flush()
    return parts
}

private func isPrintableUTF16Scalar(_ value: UInt16) -> Bool {
    guard value >= 0x20, value != 0x7F else { return false }
    guard value < 0xD800 || value > 0xDFFF else { return false }
    return value != 0xFFFE && value != 0xFFFF
}

private func uniqueTextParts(_ parts: [String]) -> [String] {
    var seen = Set<String>()
    var result: [String] = []
    for part in parts {
        let normalized = normalizeWhitespace(part)
        guard normalized.count >= 4, !seen.contains(normalized) else { continue }
        seen.insert(normalized)
        result.append(normalized)
    }
    return result
}

private func normalizeWhitespace(_ text: String) -> String {
    text
        .components(separatedBy: .whitespacesAndNewlines)
        .filter { !$0.isEmpty }
        .joined(separator: " ")
}

private func stripHTMLTags(_ html: String) -> String {
    html.replacingOccurrences(
        of: "<[^>]+>",
        with: " ",
        options: .regularExpression
    )
}
