import XCTest
@testable import DocumentIngestion

final class DocumentTextExtractorTests: XCTestCase {
    func testExtractsTextFromDocxDocumentXML() throws {
        let fileURL = try makeArchive(
            extension: "docx",
            entries: [
                "word/document.xml": "<document><body><p><r><t>Hello DOCX</t></r></p></body></document>"
            ]
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.fileName, fileURL.lastPathComponent)
        XCTAssertEqual(document.mimeType, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        XCTAssertEqual(document.text, "Hello DOCX")
    }

    func testExtractsTextFromHWPXSectionXML() throws {
        let fileURL = try makeArchive(
            extension: "hwpx",
            entries: [
                "Contents/section0.xml": "<root><p><t>Hello HWPX</t></p></root>"
            ]
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/hwp+zip")
        XCTAssertEqual(document.text, "Hello HWPX")
    }

    func testExtractsTextFromHWPXHancomMimeAlias() throws {
        let fileURL = try makeArchive(
            extension: "bin",
            entries: [
                "Contents/section0.xml": "<root><p><t>Hello Hancom HWPX</t></p></root>"
            ]
        )

        let document = try DocumentTextExtractor().extractText(
            from: fileURL,
            mimeType: "application/vnd.hancom.hwpx"
        )

        XCTAssertEqual(document.mimeType, "application/hwp+zip")
        XCTAssertEqual(document.text, "Hello Hancom HWPX")
    }

    func testExtractsTextFromHWPMLXmlDocument() throws {
        let fileURL = try writeText("<body><p><t>Hello HWPML</t></p></body>", extension: "hwpml")

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/x-hwpml")
        XCTAssertEqual(document.text, "Hello HWPML")
    }

    func testExtractsTextFromHWPMLHancomMimeAlias() throws {
        let fileURL = try writeExtensionlessText("<body><p><t>Hello Hancom HWPML</t></p></body>")

        let document = try DocumentTextExtractor().extractText(
            from: fileURL,
            mimeType: "application/vnd.hancom.hwpml"
        )

        XCTAssertEqual(document.mimeType, "application/x-hwpml")
        XCTAssertEqual(document.text, "Hello Hancom HWPML")
    }

    func testExtractsTextFromOpenDocumentText() throws {
        let fileURL = try makeArchive(
            extension: "odt",
            entries: [
                "content.xml": "<office:text><text:p>Hello ODT</text:p></office:text>"
            ]
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/vnd.oasis.opendocument.text")
        XCTAssertEqual(document.text, "Hello ODT")
    }

    func testExtractsTextFromOpenDocumentSpreadsheet() throws {
        let fileURL = try makeArchive(
            extension: "ods",
            entries: [
                "content.xml": "<office:spreadsheet><table:table-cell>Hello ODS</table:table-cell></office:spreadsheet>"
            ]
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/vnd.oasis.opendocument.spreadsheet")
        XCTAssertEqual(document.text, "Hello ODS")
    }

    func testExtractsTextFromOpenXMLSpreadsheetSharedStrings() throws {
        let fileURL = try makeArchive(
            extension: "xlsx",
            entries: [
                "xl/sharedStrings.xml": "<sst><si><t>Hello XLSX</t></si></sst>",
                "xl/worksheets/sheet1.xml": "<worksheet><sheetData><row><c><v>0</v></c></row></sheetData></worksheet>"
            ]
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        XCTAssertTrue(document.text.contains("Hello XLSX"))
    }

    func testExtractsTextFromOpenXMLPresentationSlides() throws {
        let fileURL = try makeArchive(
            extension: "pptx",
            entries: [
                "ppt/slides/slide1.xml": "<slide><shape><text>Hello PPTX</text></shape></slide>"
            ]
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        XCTAssertEqual(document.text, "Hello PPTX")
    }

    func testExtractsTextFromEPUBXHTML() throws {
        let fileURL = try makeArchive(
            extension: "epub",
            entries: [
                "OEBPS/chapter1.xhtml": "<html><body><h1>Hello EPUB</h1><p>Chapter text</p></body></html>"
            ]
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/epub+zip")
        XCTAssertTrue(document.text.contains("Hello EPUB"))
        XCTAssertTrue(document.text.contains("Chapter text"))
    }

    func testExtractsTextFromLegacyIWorkXMLArchive() throws {
        let fileURL = try makeArchive(
            extension: "pages",
            entries: [
                "index.xml": "<document><text>Hello Pages</text></document>"
            ]
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/vnd.apple.pages")
        XCTAssertEqual(document.text, "Hello Pages")
    }

    func testBestEffortExtractsTextFromLegacyBinarySpreadsheet() throws {
        let fileURL = try writeData(
            Data([0x00, 0x01, 0x02]) + Data("Hello XLS legacy".utf8) + Data([0x00]),
            extension: "xls"
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/vnd.ms-excel")
        XCTAssertTrue(document.text.contains("Hello XLS legacy"))
    }

    func testBestEffortExtractsUTF16TextFromLegacyHWP() throws {
        let utf16Bytes = "한글 HWP".utf16.flatMap { value in
            [UInt8(value & 0x00FF), UInt8(value >> 8)]
        }
        let fileURL = try writeData(
            Data([0x00, 0x01]) + Data(utf16Bytes) + Data([0x00, 0x00]),
            extension: "hwp"
        )

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/x-hwp")
        XCTAssertTrue(document.text.contains("한글 HWP"))
    }

    func testExtractsTextFromHTML() throws {
        let fileURL = try writeText("<html><body><h1>Hello HTML</h1></body></html>", extension: "html")

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "text/html")
        XCTAssertTrue(document.text.contains("Hello HTML"))
    }

    func testExtractsTextFromXHTML() throws {
        let fileURL = try writeText("<html><body><h1>Hello XHTML</h1></body></html>", extension: "xhtml")

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "text/html")
        XCTAssertTrue(document.text.contains("Hello XHTML"))
    }

    func testExtractsPlainTextFamilyDocuments() throws {
        let fileURL = try writeText(#"{"title":"Hello JSON"}"#, extension: "json")

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "text/plain")
        XCTAssertEqual(document.text, #"{"title":"Hello JSON"}"#)
    }

    func testExtractsStructuredPlainTextDocumentFamily() throws {
        let cases: [(extension: String, mimeType: String?, fileText: String, expectedText: String)] = [
            ("jsonl", "application/x-ndjson", #"{"title":"Hello JSONL"}"#, #"{"title":"Hello JSONL"}"#),
            ("yaml", "application/yaml", "title: Hello YAML", "title: Hello YAML"),
            ("toml", "application/toml", #"title = "Hello TOML""#, #"title = "Hello TOML""#),
            ("csv", "text/csv", "title,body\nHello CSV,Attachment text", "title,body Hello CSV,Attachment text"),
            ("tsv", "text/tab-separated-values", "title\tbody\nHello TSV\tAttachment text", "title body Hello TSV Attachment text"),
            ("ini", "text/plain", "[section]\ntitle=Hello INI", "[section] title=Hello INI"),
            ("properties", "text/plain", "title=Hello properties", "title=Hello properties"),
        ]

        for testCase in cases {
            let fileURL = try writeText(testCase.fileText, extension: testCase.extension)

            let document = try DocumentTextExtractor().extractText(
                from: fileURL,
                mimeType: testCase.mimeType
            )

            XCTAssertEqual(document.mimeType, "text/plain", "Expected plain text MIME for .\(testCase.extension)")
            XCTAssertEqual(document.text, testCase.expectedText, "Unexpected text for .\(testCase.extension)")
        }
    }

    func testExtractsStructuredPlainTextDocumentsFromMimeOnlyAttachments() throws {
        let cases: [(mimeType: String, fileText: String, expectedText: String)] = [
            ("application/jsonl", #"{"title":"Hello JSONL"}"#, #"{"title":"Hello JSONL"}"#),
            ("application/x-yaml", "title: Hello YAML", "title: Hello YAML"),
            ("application/toml", #"title = "Hello TOML""#, #"title = "Hello TOML""#),
            ("application/x-toml", #"title = "Hello xTOML""#, #"title = "Hello xTOML""#),
        ]

        for testCase in cases {
            let fileURL = try writeExtensionlessText(testCase.fileText)

            let document = try DocumentTextExtractor().extractText(
                from: fileURL,
                mimeType: testCase.mimeType
            )

            XCTAssertEqual(document.mimeType, "text/plain", "Expected MIME-only \(testCase.mimeType) as text")
            XCTAssertEqual(document.text, testCase.expectedText, "Unexpected text for \(testCase.mimeType)")
        }
    }

    func testExtractsRTFText() throws {
        let fileURL = try writeText(#"{\rtf1\ansi Hello RTF}"#, extension: "rtf")

        let document = try DocumentTextExtractor().extractText(from: fileURL)

        XCTAssertEqual(document.mimeType, "application/rtf")
        XCTAssertTrue(document.text.contains("Hello RTF"))
    }

    func testRejectsUnsupportedFileType() throws {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("bin")
        try Data([0x00, 0x01]).write(to: fileURL)

        XCTAssertThrowsError(try DocumentTextExtractor().extractText(from: fileURL)) { error in
            XCTAssertEqual(error as? DocumentIngestionError, .unsupportedFileType(fileURL.path))
        }
    }

    private func writeText(_ text: String, extension pathExtension: String) throws -> URL {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension(pathExtension)
        try text.write(to: fileURL, atomically: true, encoding: .utf8)
        return fileURL
    }

    private func writeExtensionlessText(_ text: String) throws -> URL {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        try text.write(to: fileURL, atomically: true, encoding: .utf8)
        return fileURL
    }

    private func writeData(_ data: Data, extension pathExtension: String) throws -> URL {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension(pathExtension)
        try data.write(to: fileURL)
        return fileURL
    }

    private func makeArchive(
        extension pathExtension: String,
        entries: [String: String]
    ) throws -> URL {
        let rootURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: rootURL, withIntermediateDirectories: true)

        for (path, content) in entries {
            let entryURL = rootURL.appendingPathComponent(path)
            try FileManager.default.createDirectory(
                at: entryURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try content.data(using: .utf8)?.write(to: entryURL)
        }

        let archiveURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension(pathExtension)
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/zip")
        process.currentDirectoryURL = rootURL
        process.arguments = ["-qr", archiveURL.path, "."]
        try process.run()
        process.waitUntilExit()
        XCTAssertEqual(process.terminationStatus, 0)
        return archiveURL
    }
}
