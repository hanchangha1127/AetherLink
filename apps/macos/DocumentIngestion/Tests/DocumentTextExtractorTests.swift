import Darwin
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

    func testCanonicalizesMimeTypeBeforeDispatchingExtensionlessAttachments() throws {
        let jsonURL = try writeExtensionlessText(#"{"title":"Parameterized JSON"}"#)
        let jsonDocument = try DocumentTextExtractor().extractText(
            from: jsonURL,
            mimeType: " Application/JSON ; charset=UTF-8 "
        )
        XCTAssertEqual(jsonDocument.mimeType, "text/plain")
        XCTAssertEqual(jsonDocument.text, #"{"title":"Parameterized JSON"}"#)

        let htmlURL = try writeExtensionlessText("<html><body>Hello MIME HTML</body></html>")
        let htmlDocument = try DocumentTextExtractor().extractText(
            from: htmlURL,
            mimeType: " TEXT/HTML; charset=utf-8"
        )
        XCTAssertEqual(htmlDocument.mimeType, "text/html")
        XCTAssertTrue(htmlDocument.text.contains("Hello MIME HTML"))
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

    func testRejectsArchiveExtractionWhenResourcePolicyLimitIsExceeded() throws {
        let fileURL = try makeArchive(
            extension: "docx",
            entries: [
                "word/document.xml": "<document><body><p><r><t>Oversized archive entry text</t></r></p></body></document>"
            ]
        )
        let extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(maxArchiveEntryBytes: 16)
        )

        XCTAssertThrowsError(try extractor.extractText(from: fileURL)) { error in
            guard case let DocumentIngestionError.resourceLimitExceeded(resource, limit, actual) = error else {
                return XCTFail("Expected resourceLimitExceeded, got \(error)")
            }
            XCTAssertEqual(resource, "archive entry word/document.xml")
            XCTAssertEqual(limit, 16)
            XCTAssertGreaterThan(actual, limit)
        }
    }

    func testRejectsExtractedTextWhenResourcePolicyLimitIsExceeded() throws {
        let fileURL = try writeText("one two three four", extension: "txt")
        let extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(maxExtractedTextCharacters: 8)
        )

        XCTAssertThrowsError(try extractor.extractText(from: fileURL)) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(resource: "extracted text", limit: 8, actual: 18)
            )
        }
    }

    func testRejectsArchiveEntryFanoutWhenResourcePolicyLimitIsExceeded() throws {
        let fileURL = try makeArchive(
            extension: "epub",
            entries: [
                "OEBPS/chapter1.xhtml": "<html><body>Chapter one</body></html>",
                "OEBPS/chapter2.xhtml": "<html><body>Chapter two</body></html>",
                "OEBPS/chapter3.xhtml": "<html><body>Chapter three</body></html>",
            ]
        )
        let allowedExtractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(maxArchiveEntries: 3)
        )
        let boundedExtractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(
                maxArchiveEntries: 2,
                maxArchiveEntryBytes: 1
            )
        )

        let document = try allowedExtractor.extractText(from: fileURL)
        XCTAssertTrue(document.text.contains("Chapter one"))
        XCTAssertTrue(document.text.contains("Chapter three"))

        XCTAssertThrowsError(try boundedExtractor.extractText(from: fileURL)) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(resource: "archive entries", limit: 2, actual: 3)
            )
        }
    }

    func testStopsArchiveFanoutAtAggregateTextLimitBeforeReadingLaterEntries() throws {
        let fileURL = try makeArchive(
            extension: "epub",
            entries: [
                "OEBPS/1.txt": "12345678",
                "OEBPS/2.txt": "abcdefgh",
                "OEBPS/3.txt": String(repeating: "z", count: 100),
            ]
        )
        let extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(
                maxArchiveEntryBytes: 64,
                maxExtractedTextCharacters: 12
            )
        )

        XCTAssertThrowsError(try extractor.extractText(from: fileURL)) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(resource: "extracted text", limit: 12, actual: 17)
            )
        }
    }

    func testRejectsCombiningMarkPlainTextByAggregateUTF8ByteLimit() throws {
        let combiningText = "a" + String(repeating: "\u{0301}", count: 8)
        XCTAssertEqual(combiningText.count, 1)
        XCTAssertEqual(combiningText.utf8.count, 17)
        let fileURL = try writeText(combiningText, extension: "txt")
        let extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(
                maxExtractedTextCharacters: 1,
                maxExtractedTextUTF8Bytes: 8
            )
        )

        XCTAssertThrowsError(try extractor.extractText(from: fileURL)) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(
                    resource: "extracted text UTF-8 bytes",
                    limit: 8,
                    actual: 17
                )
            )
        }
    }

    func testRejectsCombiningMarkArchiveTextByAggregateUTF8ByteLimit() throws {
        let combiningText = "a" + String(repeating: "\u{0301}", count: 8)
        XCTAssertEqual(combiningText.count, 1)
        XCTAssertEqual(combiningText.utf8.count, 17)
        let fileURL = try makeArchive(
            extension: "epub",
            entries: ["OEBPS/combining.txt": combiningText]
        )
        let extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(
                maxExtractedTextCharacters: 1,
                maxExtractedTextUTF8Bytes: 8
            )
        )

        XCTAssertThrowsError(try extractor.extractText(from: fileURL)) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(
                    resource: "extracted text UTF-8 bytes",
                    limit: 8,
                    actual: 17
                )
            )
        }
    }

    func testBoundedProcessDrainsLargeStandardErrorWhileReadingOutput() throws {
        let script = """
        import sys
        sys.stderr.buffer.write(b"x" * (2 * 1024 * 1024))
        sys.stderr.flush()
        sys.stdout.buffer.write(b"done")
        """

        let result = try runBoundedDocumentProcess(
            executableURL: URL(fileURLWithPath: "/usr/bin/env"),
            arguments: ["python3", "-c", script],
            outputResource: "test process output",
            outputLimit: 16,
            timeout: 5
        )

        XCTAssertEqual(result.terminationStatus, 0)
        XCTAssertEqual(String(decoding: result.standardOutput, as: UTF8.self), "done")
    }

    func testBoundedProcessKillsAndReapsAChildThatIgnoresTermination() throws {
        let script = """
        import signal
        import time
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
        """
        let startedAt = Date()

        XCTAssertThrowsError(
            try runBoundedDocumentProcess(
                executableURL: URL(fileURLWithPath: "/usr/bin/env"),
                arguments: ["python3", "-c", script],
                outputResource: "test process timeout",
                outputLimit: 16,
                timeout: 0.05
            )
        ) { error in
            XCTAssertEqual(
                error as? DocumentProcessError,
                .timedOut("test process timeout")
            )
        }
        XCTAssertLessThan(Date().timeIntervalSince(startedAt), 3)
    }

    func testBoundedProcessesShareOneCumulativeMonotonicDeadline() throws {
        let clock = MonotonicTimeBox(1_000)
        let deadline = try DocumentProcessDeadline(
            timeout: 1,
            nowNanoseconds: { clock.get() }
        )
        let first = try runBoundedDocumentProcess(
            executableURL: URL(fileURLWithPath: "/usr/bin/true"),
            arguments: [],
            outputResource: "first process",
            outputLimit: 16,
            deadline: deadline
        )
        XCTAssertEqual(first.terminationStatus, 0)

        clock.set(1_000_001_000)
        XCTAssertThrowsError(
            try runBoundedDocumentProcess(
                executableURL: URL(fileURLWithPath: "/usr/bin/true"),
                arguments: [],
                outputResource: "second process",
                outputLimit: 16,
                deadline: deadline
            )
        ) { error in
            XCTAssertEqual(
                error as? DocumentProcessError,
                .timedOut("second process")
            )
        }
    }

    func testIgnoresPathShapedArchiveEntriesBeforeExtraction() throws {
        let oversizedName = "OEBPS/" +
            String(repeating: "a", count: documentIngestionArchiveEntryNameCharacterLimitCeiling) +
            ".xhtml"
        let fileURL = try makeArchiveWithRawEntries(
            extension: "epub",
            entries: [
                (
                    name: "OEBPS/chapter.xhtml",
                    content: "<html><body>Safe chapter text</body></html>"
                ),
                (
                    name: "../secret.xhtml",
                    content: "<html><body>PATH SENTINEL parent traversal</body></html>"
                ),
                (
                    name: "/absolute/secret.xhtml",
                    content: "<html><body>PATH SENTINEL absolute path</body></html>"
                ),
                (
                    name: "C:\\Users\\private\\secret.xhtml",
                    content: "<html><body>PATH SENTINEL windows path</body></html>"
                ),
                (
                    name: "OEBPS/./secret.xhtml",
                    content: "<html><body>PATH SENTINEL dot component</body></html>"
                ),
                (
                    name: oversizedName,
                    content: "<html><body>PATH SENTINEL oversized entry</body></html>"
                ),
            ]
        )
        let extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(maxArchiveEntries: 1)
        )

        let document = try extractor.extractText(from: fileURL)

        XCTAssertTrue(document.text.contains("Safe chapter text"))
        XCTAssertFalse(document.text.contains("PATH SENTINEL"))
    }

    func testAppliesStoreOwnedResourcePolicyCeilingsBeforeExtraction() throws {
        let fileURL = try writeText("bounded extraction policy", extension: "txt")
        let boundaryExtractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(
                maxInputBytes: documentIngestionResourcePolicyMaxInputBytesCeiling,
                maxArchiveListingBytes: documentIngestionResourcePolicyMaxArchiveListingBytesCeiling,
                maxArchiveEntries: documentIngestionResourcePolicyMaxArchiveEntriesCeiling,
                maxArchiveEntryBytes: documentIngestionResourcePolicyMaxArchiveEntryBytesCeiling,
                maxConverterOutputBytes: documentIngestionResourcePolicyMaxConverterOutputBytesCeiling,
                maxExtractedTextCharacters: documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling,
                maxExtractedTextUTF8Bytes: documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling
            )
        )

        let document = try boundaryExtractor.extractText(from: fileURL)
        XCTAssertEqual(document.text, "bounded extraction policy")

        let oversizedPolicies: [(DocumentIngestionResourcePolicy, DocumentIngestionError)] = [
            (
                DocumentIngestionResourcePolicy(
                    maxInputBytes: documentIngestionResourcePolicyMaxInputBytesCeiling + 1
                ),
                .invalidResourcePolicy(
                    "maxInputBytes must be less than or equal to \(documentIngestionResourcePolicyMaxInputBytesCeiling)"
                )
            ),
            (
                DocumentIngestionResourcePolicy(
                    maxArchiveListingBytes: documentIngestionResourcePolicyMaxArchiveListingBytesCeiling + 1
                ),
                .invalidResourcePolicy(
                    "maxArchiveListingBytes must be less than or equal to \(documentIngestionResourcePolicyMaxArchiveListingBytesCeiling)"
                )
            ),
            (
                DocumentIngestionResourcePolicy(
                    maxArchiveEntries: documentIngestionResourcePolicyMaxArchiveEntriesCeiling + 1
                ),
                .invalidResourcePolicy(
                    "maxArchiveEntries must be less than or equal to \(documentIngestionResourcePolicyMaxArchiveEntriesCeiling)"
                )
            ),
            (
                DocumentIngestionResourcePolicy(
                    maxArchiveEntryBytes: documentIngestionResourcePolicyMaxArchiveEntryBytesCeiling + 1
                ),
                .invalidResourcePolicy(
                    "maxArchiveEntryBytes must be less than or equal to \(documentIngestionResourcePolicyMaxArchiveEntryBytesCeiling)"
                )
            ),
            (
                DocumentIngestionResourcePolicy(
                    maxConverterOutputBytes: documentIngestionResourcePolicyMaxConverterOutputBytesCeiling + 1
                ),
                .invalidResourcePolicy(
                    "maxConverterOutputBytes must be less than or equal to \(documentIngestionResourcePolicyMaxConverterOutputBytesCeiling)"
                )
            ),
            (
                DocumentIngestionResourcePolicy(
                    maxExtractedTextCharacters: documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling + 1
                ),
                .invalidResourcePolicy(
                    "maxExtractedTextCharacters must be less than or equal to \(documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling)"
                )
            ),
            (
                DocumentIngestionResourcePolicy(
                    maxExtractedTextUTF8Bytes: documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling + 1
                ),
                .invalidResourcePolicy(
                    "maxExtractedTextUTF8Bytes must be less than or equal to \(documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling)"
                )
            ),
            (
                DocumentIngestionResourcePolicy(maxInputBytes: Int.max),
                .invalidResourcePolicy(
                    "maxInputBytes must be less than or equal to \(documentIngestionResourcePolicyMaxInputBytesCeiling)"
                )
            ),
            (
                DocumentIngestionResourcePolicy(maxArchiveEntries: Int.max),
                .invalidResourcePolicy(
                    "maxArchiveEntries must be less than or equal to \(documentIngestionResourcePolicyMaxArchiveEntriesCeiling)"
                )
            ),
            (
                DocumentIngestionResourcePolicy(maxExtractedTextCharacters: Int.max),
                .invalidResourcePolicy(
                    "maxExtractedTextCharacters must be less than or equal to \(documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling)"
                )
            )
        ]

        for (policy, expectedError) in oversizedPolicies {
            XCTAssertThrowsError(
                try DocumentTextExtractor(resourcePolicy: policy).extractText(from: fileURL)
            ) { error in
                XCTAssertEqual(error as? DocumentIngestionError, expectedError)
            }
        }
    }

    func testRejectsNonPositiveResourcePolicyBeforeExtraction() throws {
        let fileURL = try writeText("invalid policy", extension: "txt")
        let invalidPolicies: [(DocumentIngestionResourcePolicy, DocumentIngestionError)] = [
            (
                DocumentIngestionResourcePolicy(maxInputBytes: 0),
                .invalidResourcePolicy("maxInputBytes must be greater than zero")
            ),
            (
                DocumentIngestionResourcePolicy(maxArchiveListingBytes: -1),
                .invalidResourcePolicy("maxArchiveListingBytes must be greater than zero")
            ),
            (
                DocumentIngestionResourcePolicy(maxArchiveEntries: 0),
                .invalidResourcePolicy("maxArchiveEntries must be greater than zero")
            ),
            (
                DocumentIngestionResourcePolicy(maxArchiveEntryBytes: 0),
                .invalidResourcePolicy("maxArchiveEntryBytes must be greater than zero")
            ),
            (
                DocumentIngestionResourcePolicy(maxConverterOutputBytes: -1),
                .invalidResourcePolicy("maxConverterOutputBytes must be greater than zero")
            ),
            (
                DocumentIngestionResourcePolicy(maxExtractedTextCharacters: 0),
                .invalidResourcePolicy("maxExtractedTextCharacters must be greater than zero")
            ),
            (
                DocumentIngestionResourcePolicy(maxExtractedTextUTF8Bytes: 0),
                .invalidResourcePolicy("maxExtractedTextUTF8Bytes must be greater than zero")
            )
        ]

        for (policy, expectedError) in invalidPolicies {
            XCTAssertThrowsError(
                try DocumentTextExtractor(resourcePolicy: policy).extractText(from: fileURL)
            ) { error in
                XCTAssertEqual(error as? DocumentIngestionError, expectedError)
            }
        }
    }

    func testPrivateSnapshotAcceptsExactInputLimitAndRejectsLimitPlusOne() throws {
        let exactURL = try writeData(Data("12345678".utf8), extension: "txt")
        let oversizedURL = try writeData(Data("123456789".utf8), extension: "txt")
        let extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(maxInputBytes: 8)
        )

        XCTAssertEqual(try extractor.extractText(from: exactURL).text, "12345678")
        XCTAssertThrowsError(try extractor.extractText(from: oversizedURL)) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(resource: "input file", limit: 8, actual: 9)
            )
        }
    }

    func testPrivateSnapshotRejectsFileGrowthBeyondLimitAfterDescriptorValidation() throws {
        let fileURL = try writeData(Data("1234".utf8), extension: "txt")
        let extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(maxInputBytes: 4),
            snapshotHooks: DocumentInputSnapshotHooks(
                didOpenSourceDescriptor: { sourceURL in
                    let handle = try FileHandle(forWritingTo: sourceURL)
                    defer { try? handle.close() }
                    try handle.seekToEnd()
                    try handle.write(contentsOf: Data("5".utf8))
                }
            )
        )

        XCTAssertThrowsError(try extractor.extractText(from: fileURL)) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(resource: "input file", limit: 4, actual: 5)
            )
        }
    }

    func testPrivateSnapshotRejectsFIFOWithoutBlocking() throws {
        let fifoURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("txt")
        XCTAssertEqual(Darwin.mkfifo(fifoURL.path, 0o600), 0)
        defer { Darwin.unlink(fifoURL.path) }
        let startedAt = Date()

        XCTAssertThrowsError(try DocumentTextExtractor().extractText(from: fifoURL)) { error in
            XCTAssertEqual(error as? DocumentInputValidationError, .unsafeInputFile(fifoURL.path))
        }
        XCTAssertLessThan(Date().timeIntervalSince(startedAt), 1)
    }

    func testPrivateSnapshotRejectsSymbolicLinkInput() throws {
        let targetURL = try writeText("private target", extension: "txt")
        let linkURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("txt")
        try FileManager.default.createSymbolicLink(at: linkURL, withDestinationURL: targetURL)
        defer { try? FileManager.default.removeItem(at: linkURL) }

        XCTAssertThrowsError(try DocumentTextExtractor().extractText(from: linkURL)) { error in
            XCTAssertEqual(error as? DocumentInputValidationError, .unsafeInputFile(linkURL.path))
        }
    }

    func testArchiveHelpersReadValidatedSnapshotAfterSourcePathReplacement() throws {
        let originalArchive = try makeArchive(
            extension: "docx",
            entries: [
                "word/document.xml": "<document><body>ORIGINAL SNAPSHOT</body></document>"
            ]
        )
        let replacementArchive = try makeArchive(
            extension: "docx",
            entries: [
                "word/document.xml": "<document><body>REPLACEMENT PATH</body></document>"
            ]
        )
        let sourceURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("docx")
        try FileManager.default.copyItem(at: originalArchive, to: sourceURL)
        defer { try? FileManager.default.removeItem(at: sourceURL) }
        let displacedURL = sourceURL.deletingPathExtension()
            .appendingPathExtension("opened.docx")
        defer { try? FileManager.default.removeItem(at: displacedURL) }
        let replacementData = try Data(contentsOf: replacementArchive)
        let extractor = DocumentTextExtractor(
            snapshotHooks: DocumentInputSnapshotHooks(
                didOpenSourceDescriptor: { openedURL in
                    try FileManager.default.moveItem(at: openedURL, to: displacedURL)
                    try replacementData.write(to: openedURL)
                }
            )
        )

        let document = try extractor.extractText(from: sourceURL)

        XCTAssertTrue(document.text.contains("ORIGINAL SNAPSHOT"))
        XCTAssertFalse(document.text.contains("REPLACEMENT PATH"))
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

    private func makeArchiveWithRawEntries(
        extension pathExtension: String,
        entries: [(name: String, content: String)]
    ) throws -> URL {
        let archiveURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension(pathExtension)
        let payloadURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("json")
        let payload = entries.map { entry in
            ["name": entry.name, "content": entry.content]
        }
        try JSONSerialization.data(withJSONObject: payload).write(to: payloadURL)

        let script = """
        import json
        import sys
        import zipfile

        with open(sys.argv[2], "r", encoding="utf-8") as payload_file:
            entries = json.load(payload_file)

        with zipfile.ZipFile(sys.argv[1], "w") as archive:
            for entry in entries:
                archive.writestr(entry["name"], entry["content"])
        """
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["python3", "-c", script, archiveURL.path, payloadURL.path]
        try process.run()
        process.waitUntilExit()
        XCTAssertEqual(process.terminationStatus, 0)
        return archiveURL
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

private final class MonotonicTimeBox: @unchecked Sendable {
    private let lock = NSLock()
    private var value: UInt64

    init(_ value: UInt64) {
        self.value = value
    }

    func set(_ value: UInt64) {
        lock.lock()
        self.value = value
        lock.unlock()
    }

    func get() -> UInt64 {
        lock.lock()
        defer { lock.unlock() }
        return value
    }
}
