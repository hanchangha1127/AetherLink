import XCTest
@testable import DocumentIngestion

final class DocumentIngestionSanitizerCorpusTests: XCTestCase {
    func testMalformedUTF8PlainTextSeedsFailClosed() throws {
        let seeds: [(name: String, bytes: [UInt8])] = [
            ("isolated-continuation", [0x80]),
            ("overlong-slash", [0xC0, 0xAF]),
            ("truncated-three-byte", [0xE2, 0x82]),
            ("utf8-surrogate", [0xED, 0xA0, 0x80]),
            ("above-unicode-range", [0xF4, 0x90, 0x80, 0x80]),
        ]

        for seed in seeds {
            let fileURL = try writeSeed(
                Data(seed.bytes),
                name: seed.name,
                extension: "txt"
            )
            XCTAssertThrowsError(
                try DocumentTextExtractor().extractText(from: fileURL),
                seed.name
            ) { error in
                XCTAssertEqual(
                    error as? DocumentInputValidationError,
                    .inputReadFailed(fileURL.path),
                    seed.name
                )
            }
        }
    }

    func testMalformedXMLSeedsCannotPublishPartialPrefixText() throws {
        let directSeeds: [(name: String, data: Data)] = [
            ("truncated", Data("<root>prefix".utf8)),
            ("mismatched", Data("<root><child>prefix</root>".utf8)),
            (
                "invalid-utf8",
                Data([0x3C, 0x72, 0x3E, 0x80, 0x3C, 0x2F, 0x72, 0x3E])
            ),
        ]

        for seed in directSeeds {
            let fileURL = try writeSeed(
                seed.data,
                name: seed.name,
                extension: "xml"
            )
            XCTAssertThrowsError(
                try DocumentTextExtractor().extractText(from: fileURL),
                seed.name
            ) { error in
                XCTAssertEqual(
                    error as? DocumentIngestionError,
                    .noExtractableText(fileURL.path),
                    seed.name
                )
            }
        }

        let malformedDocumentXMLArchive = try XCTUnwrap(Data(base64Encoded:
            "UEsDBBQAAAAAAAAAIQAI6zDyJQAAACUAAAARAAAAd29yZC9kb2N1bWVudC54bWw8ZG9jdW1lbnQ+PGJvZHk+cHJlZml4PGJyb2tlbj48L2JvZHk+UEsBAhQDFAAAAAAAAAAhAAjrMPIlAAAAJQAAABEAAAAAAAAAAAAAAICBAAAAAHdvcmQvZG9jdW1lbnQueG1sUEsFBgAAAAABAAEAPwAAAFQAAAAAAA=="
        ))
        let archiveURL = try writeSeed(
            malformedDocumentXMLArchive,
            name: "malformed-document-xml",
            extension: "docx"
        )
        XCTAssertThrowsError(
            try DocumentTextExtractor().extractText(from: archiveURL)
        ) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .archiveEntryReadFailed("word/document.xml")
            )
        }
    }

    func testMalformedContainerAndNativeParserSeedsHaveExactOutcomes() throws {
        let truncatedArchives: [(name: String, data: Data)] = [
            ("empty", Data()),
            ("signature-only", Data([0x50, 0x4B, 0x03, 0x04])),
            ("not-a-zip", Data("not a zip archive".utf8)),
        ]
        for seed in truncatedArchives {
            let fileURL = try writeSeed(
                seed.data,
                name: seed.name,
                extension: "docx"
            )
            XCTAssertThrowsError(
                try DocumentTextExtractor().extractText(from: fileURL),
                seed.name
            ) { error in
                XCTAssertEqual(
                    error as? DocumentIngestionError,
                    .archiveListingFailed(fileURL.path),
                    seed.name
                )
            }
        }

        let pdfURL = try writeSeed(
            Data([0x00, 0x01, 0x02, 0x03]),
            name: "invalid-pdf",
            extension: "pdf"
        )
        XCTAssertThrowsError(
            try DocumentTextExtractor().extractText(from: pdfURL)
        ) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .unreadablePDF(pdfURL.path)
            )
        }

        let rtfURL = try writeSeed(
            Data([0x00]),
            name: "invalid-rtf",
            extension: "rtf"
        )
        XCTAssertThrowsError(
            try DocumentTextExtractor().extractText(from: rtfURL)
        )

        let htmlURL = try writeSeed(
            Data([0x80]),
            name: "invalid-html",
            extension: "html"
        )
        let htmlDocument = try DocumentTextExtractor().extractText(from: htmlURL)
        XCTAssertEqual(htmlDocument.text, "\u{FFFD}")
        XCTAssertEqual(htmlDocument.mimeType, "text/html")
    }

    func testExactAndLimitPlusOneSeedsRemainDistinct() throws {
        let inputExtractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(maxInputBytes: 8)
        )
        let exactInputURL = try writeSeed(
            Data("12345678".utf8),
            name: "input-exact",
            extension: "txt"
        )
        XCTAssertEqual(
            try inputExtractor.extractText(from: exactInputURL).text,
            "12345678"
        )

        let oversizedInputURL = try writeSeed(
            Data("123456789".utf8),
            name: "input-plus-one",
            extension: "txt"
        )
        XCTAssertThrowsError(
            try inputExtractor.extractText(from: oversizedInputURL)
        ) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(
                    resource: "input file",
                    limit: 8,
                    actual: 9
                )
            )
        }

        let utf8Extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(
                maxExtractedTextCharacters: 3,
                maxExtractedTextUTF8Bytes: 4
            )
        )
        let exactUTF8URL = try writeSeed(
            Data("éé".utf8),
            name: "utf8-exact",
            extension: "txt"
        )
        XCTAssertEqual(try utf8Extractor.extractText(from: exactUTF8URL).text, "éé")

        let oversizedUTF8URL = try writeSeed(
            Data("ééx".utf8),
            name: "utf8-plus-one",
            extension: "txt"
        )
        XCTAssertThrowsError(
            try utf8Extractor.extractText(from: oversizedUTF8URL)
        ) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(
                    resource: "extracted text UTF-8 bytes",
                    limit: 4,
                    actual: 5
                )
            )
        }

        let characterExtractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(
                maxExtractedTextCharacters: 2,
                maxExtractedTextUTF8Bytes: 3
            )
        )
        let exactCharacterURL = try writeSeed(
            Data("ab".utf8),
            name: "character-exact",
            extension: "txt"
        )
        XCTAssertEqual(
            try characterExtractor.extractText(from: exactCharacterURL).text,
            "ab"
        )

        let oversizedCharacterURL = try writeSeed(
            Data("abc".utf8),
            name: "character-plus-one",
            extension: "txt"
        )
        XCTAssertThrowsError(
            try characterExtractor.extractText(from: oversizedCharacterURL)
        ) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(
                    resource: "extracted text",
                    limit: 2,
                    actual: 3
                )
            )
        }
    }

    func testUnicodeChunkBoundarySeedsRoundTripByCharacterOffset() throws {
        let seeds = [
            "a\u{0301}b",
            "👨‍👩‍👧‍👦x",
            "🇰🇷y",
            "\u{0000}z",
            "。x",
        ]
        let chunker = DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 1,
            overlapCharacters: 0,
            minChunkCharacters: 1
        ))

        for (seedIndex, seed) in seeds.enumerated() {
            let chunks = try chunker.chunks(from: ExtractedDocument(
                fileName: "unicode-\(seedIndex).txt",
                mimeType: "text/plain",
                text: seed
            ))

            XCTAssertEqual(chunks.count, seed.count)
            XCTAssertEqual(chunks.map(\.index), Array(0..<seed.count))
            XCTAssertEqual(chunks.map(\.text).joined(), seed)
            for chunk in chunks {
                XCTAssertEqual(chunk.text.count, 1)
                XCTAssertEqual(
                    chunk.text,
                    substring(
                        seed,
                        start: chunk.startCharacterOffset,
                        end: chunk.endCharacterOffset
                    )
                )
            }
        }
    }

    private func writeSeed(
        _ data: Data,
        name: String,
        extension pathExtension: String
    ) throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        addTeardownBlock {
            try? FileManager.default.removeItem(at: directory)
        }
        let fileURL = directory
            .appendingPathComponent(name)
            .appendingPathExtension(pathExtension)
        try data.write(to: fileURL)
        return fileURL
    }

    private func substring(_ text: String, start: Int, end: Int) -> String {
        let startIndex = text.index(text.startIndex, offsetBy: start)
        let endIndex = text.index(text.startIndex, offsetBy: end)
        return String(text[startIndex..<endIndex])
    }
}
