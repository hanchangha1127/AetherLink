import Foundation
import PDFKit

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

public enum DocumentIngestionError: Error, Equatable, LocalizedError, Sendable {
    case unsupportedFileType(String)
    case unreadablePDF(String)
    case archiveListingFailed(String)
    case archiveEntryReadFailed(String)
    case converterFailed(String)
    case noExtractableText(String)

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
        }
    }
}

public final class DocumentTextExtractor: Sendable {
    public init() {}

    public func extractText(from fileURL: URL, mimeType: String? = nil) throws -> ExtractedDocument {
        let kind = DocumentKind(fileURL: fileURL, mimeType: mimeType)
        let text: String
        switch kind {
        case .pdf:
            text = try extractPDFText(from: fileURL)
        case .docx:
            text = try extractZippedText(
                from: fileURL,
                preferredEntries: ["word/document.xml"],
                fallbackEntryPrefixes: ["word/"],
                allowedPathExtensions: ["xml"]
            )
        case .hwpx:
            text = try extractZippedText(
                from: fileURL,
                preferredEntries: ["Contents/section0.xml"],
                fallbackEntryPrefixes: ["Contents/"],
                allowedPathExtensions: ["xml"]
            )
        case .odt:
            text = try extractZippedText(
                from: fileURL,
                preferredEntries: ["content.xml"],
                fallbackEntryPrefixes: [],
                allowedPathExtensions: ["xml"]
            )
        case .ods, .odp:
            text = try extractZippedText(
                from: fileURL,
                preferredEntries: ["content.xml"],
                fallbackEntryPrefixes: [],
                allowedPathExtensions: ["xml"]
            )
        case .xlsx:
            text = try extractZippedText(
                from: fileURL,
                preferredEntries: ["xl/sharedStrings.xml"],
                fallbackEntryPrefixes: ["xl/worksheets/"],
                allowedPathExtensions: ["xml"]
            )
        case .pptx:
            text = try extractZippedText(
                from: fileURL,
                preferredEntries: [],
                fallbackEntryPrefixes: ["ppt/slides/", "ppt/notesSlides/"],
                allowedPathExtensions: ["xml"]
            )
        case .epub:
            text = try extractZippedText(
                from: fileURL,
                preferredEntries: [],
                fallbackEntryPrefixes: [],
                allowedPathExtensions: ["xhtml", "html", "htm", "xml", "opf", "txt"]
            )
        case .pages, .numbers, .keynote:
            text = try extractZippedText(
                from: fileURL,
                preferredEntries: ["index.xml"],
                fallbackEntryPrefixes: [],
                allowedPathExtensions: ["xml", "xhtml", "html", "htm", "txt"]
            )
        case .rtf:
            text = try extractRTFText(from: fileURL)
        case .html:
            text = try extractHTMLText(from: fileURL)
        case .legacyWord, .webArchive:
            text = try extractTextutilText(from: fileURL)
        case .legacySpreadsheet, .legacyPresentation, .legacyHWP:
            text = try extractBinaryText(from: fileURL)
        case .xml:
            text = XMLTextCollector.collectText(from: try Data(contentsOf: fileURL))
        case .plainText:
            text = try String(contentsOf: fileURL, encoding: .utf8)
        case .unsupported:
            throw DocumentIngestionError.unsupportedFileType(fileURL.path)
        }

        let normalizedText = normalizeWhitespace(text)
        guard !normalizedText.isEmpty else {
            throw DocumentIngestionError.noExtractableText(fileURL.path)
        }

        return ExtractedDocument(
            fileName: fileURL.lastPathComponent,
            mimeType: kind.mimeType,
            text: normalizedText
        )
    }

    private func extractPDFText(from fileURL: URL) throws -> String {
        guard let document = PDFDocument(url: fileURL) else {
            throw DocumentIngestionError.unreadablePDF(fileURL.path)
        }
        return (0..<document.pageCount)
            .compactMap { document.page(at: $0)?.string }
            .joined(separator: "\n\n")
    }

    private func extractZippedText(
        from fileURL: URL,
        preferredEntries: [String],
        fallbackEntryPrefixes: [String],
        allowedPathExtensions: Set<String>
    ) throws -> String {
        let entries = try archiveEntries(fileURL)
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

        let textParts = try xmlEntries.map { entry -> String in
            let data = try archiveEntryData(fileURL, entry: entry)
            return extractText(fromArchiveEntry: entry, data: data)
        }

        return textParts.joined(separator: "\n\n")
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

    private func extractRTFText(from fileURL: URL) throws -> String {
        let data = try Data(contentsOf: fileURL)
        let attributed = try NSAttributedString(
            data: data,
            options: [.documentType: NSAttributedString.DocumentType.rtf],
            documentAttributes: nil
        )
        return attributed.string
    }

    private func extractHTMLText(from fileURL: URL) throws -> String {
        let data = try Data(contentsOf: fileURL)
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

    private func extractTextutilText(from fileURL: URL) throws -> String {
        let data = try runTextutil(arguments: ["-convert", "txt", "-stdout", fileURL.path])
        return String(data: data, encoding: .utf8) ?? String(decoding: data, as: UTF8.self)
    }

    private func extractBinaryText(from fileURL: URL) throws -> String {
        let data = try Data(contentsOf: fileURL)
        let byteStrings = extractPrintableByteStrings(from: data)
        let utf16Strings = extractPrintableUTF16LEStrings(from: data)
        return uniqueTextParts(byteStrings + utf16Strings).joined(separator: "\n")
    }

    private func archiveEntries(_ fileURL: URL) throws -> [String] {
        let data = try runUnzip(arguments: ["-Z1", fileURL.path], error: .archiveListingFailed(fileURL.path))
        guard let output = String(data: data, encoding: .utf8) else {
            throw DocumentIngestionError.archiveListingFailed(fileURL.path)
        }
        return output
            .split(separator: "\n")
            .map(String.init)
            .filter { !$0.isEmpty }
    }

    private func archiveEntryData(_ fileURL: URL, entry: String) throws -> Data {
        try runUnzip(arguments: ["-p", fileURL.path, entry], error: .archiveEntryReadFailed(entry))
    }

    private func runUnzip(arguments: [String], error: DocumentIngestionError) throws -> Data {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/unzip")
        process.arguments = arguments
        let output = Pipe()
        let errors = Pipe()
        process.standardOutput = output
        process.standardError = errors
        try process.run()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            throw error
        }
        return output.fileHandleForReading.readDataToEndOfFile()
    }

    private func runTextutil(arguments: [String]) throws -> Data {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/textutil")
        process.arguments = arguments
        let output = Pipe()
        process.standardOutput = output
        process.standardError = Pipe()
        try process.run()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            throw DocumentIngestionError.converterFailed(arguments.last ?? "")
        }
        return output.fileHandleForReading.readDataToEndOfFile()
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
        let normalizedMimeType = mimeType?.lowercased()
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
        case ("hwpx", _), (_, "application/hwp+zip"), (_, "application/x-hwpx"):
            self = .hwpx
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
        case ("html", _), ("htm", _), (_, "text/html"), (_, "application/xhtml+xml"):
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
            (_, "application/x-ndjson"),
            (_, "application/yaml"),
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
