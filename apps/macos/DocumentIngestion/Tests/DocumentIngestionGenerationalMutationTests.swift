import Foundation
import XCTest
@testable import DocumentIngestion

final class DocumentIngestionGenerationalMutationTests: XCTestCase {
    func testGeneratorMarkerContractMatchesGoldenVectors() throws {
        var zeroGenerator = SplitMix64V1(seed: 0)
        XCTAssertEqual(zeroGenerator.next(), 0xE220_A839_7B1D_CDAF)
        XCTAssertEqual(zeroGenerator.next(), 0x6E78_9E6A_A1B9_65F4)
        XCTAssertEqual(zeroGenerator.next(), 0x06C4_5D18_8009_454F)
        XCTAssertEqual(zeroGenerator.next(), 0xF88B_B8A8_724C_81EC)

        XCTAssertEqual(
            documentMutationSHA256(
                DocumentIngestionMutationCorpus.fixture(for: .pdf)
            ),
            DocumentIngestionMutationCorpus.pdfFixtureSHA256
        )
        XCTAssertEqual(
            documentMutationSHA256(
                DocumentIngestionMutationCorpus.fixture(for: .docx)
            ),
            DocumentIngestionMutationCorpus.docxFixtureSHA256
        )
        XCTAssertEqual(
            documentMutationSHA256(
                DocumentIngestionMutationCorpus.fixture(for: .epub)
            ),
            DocumentIngestionMutationCorpus.epubFixtureSHA256
        )
        XCTAssertEqual(
            documentMutationSHA256(
                DocumentIngestionMutationCorpus.fixture(for: .webarchive)
            ),
            DocumentIngestionMutationCorpus.webarchiveFixtureSHA256
        )

        let first = DocumentIngestionMutationCorpus.makeCases()
        let second = DocumentIngestionMutationCorpus.makeCases()
        XCTAssertEqual(first, second)
        XCTAssertEqual(first.count, DocumentIngestionMutationCorpus.caseCount)
        XCTAssertEqual(Set(first.map(\.caseSeed)).count, first.count)

        let expectedFormats = Dictionary(
            uniqueKeysWithValues: DocumentMutationFormat.allCases.map {
                ($0, DocumentMutationOperator.allCases.count)
            }
        )
        XCTAssertEqual(
            Dictionary(grouping: first, by: \.format).mapValues(\.count),
            expectedFormats
        )
        for mutation in DocumentMutationOperator.allCases {
            XCTAssertEqual(
                first.filter { $0.operators.last == mutation }.count,
                DocumentMutationFormat.allCases.count,
                mutation.rawValue
            )
        }
        XCTAssertTrue(first.allSatisfy { 1...4 ~= $0.operators.count })
        XCTAssertTrue(first.allSatisfy {
            $0.data.count <= DocumentIngestionMutationCorpus.maximumCaseBytes
        })
        XCTAssertEqual(
            first.filter { $0.operators.last == .padExact4096 }
                .map(\.data.count),
            Array(
                repeating: DocumentIngestionMutationCorpus.inputLimit,
                count: DocumentMutationFormat.allCases.count
            )
        )
        XCTAssertEqual(
            first.filter { $0.operators.last == .padPlusOne4097 }
                .map(\.data.count),
            Array(
                repeating: DocumentIngestionMutationCorpus.maximumCaseBytes,
                count: DocumentMutationFormat.allCases.count
            )
        )

        XCTAssertEqual(first.first?.caseSeed, 0xCAA4_CBEA_AFC5_B615)
        XCTAssertEqual(first.last?.caseSeed, 0xB6FC_6CC0_C7C5_DFD0)
        XCTAssertEqual(
            first.first?.markerLine,
            "AETHERLINK_DOCUMENT_MUTATION_V1 case=000 total=096 generator=splitmix64-v1 root=a37e2c915b04d8f6 seed=caa4cbeaafc5b615 format=txt operators=truncate,splice_seed,reverse_span,identity bytes=30 sha256=6000b29d84f965de0b7fb48481d9da6a812aa3197c08d160cea2255b151f3350"
        )
        XCTAssertEqual(
            first.last?.markerLine,
            "AETHERLINK_DOCUMENT_MUTATION_V1 case=095 total=096 generator=splitmix64-v1 root=a37e2c915b04d8f6 seed=b6fc6cc0c7c5dfd0 format=webarchive operators=pad_plus_one_4097 bytes=4097 sha256=3276585173b8bd36188455753d85a447ba462fc8a485f38758821b68b40786c3"
        )
        XCTAssertEqual(
            documentMutationSHA256(
                DocumentIngestionMutationCorpus.markerManifest(for: first)
            ),
            "bd6e38cbac664aca4e7d4d912fddd1f853b93dfc5b862751921848d885d1e379"
        )
    }

    func testBoundedGenerationalMutationsHaveSafeOutcomes() throws {
        let cases = DocumentIngestionMutationCorpus.makeCases()
        let temporaryDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(
            at: temporaryDirectory,
            withIntermediateDirectories: false,
            attributes: [.posixPermissions: 0o700]
        )
        defer { try? FileManager.default.removeItem(at: temporaryDirectory) }

        let extractor = DocumentTextExtractor(
            resourcePolicy: DocumentIngestionResourcePolicy(
                maxInputBytes: DocumentIngestionMutationCorpus.inputLimit,
                maxArchiveListingBytes: 64 * 1024,
                maxArchiveEntries: 32,
                maxArchiveEntryBytes: 16 * 1024,
                maxConverterOutputBytes: 16 * 1024,
                maxExtractedTextCharacters: 8_192,
                maxExtractedTextUTF8Bytes: 16 * 1024
            )
        )

        for mutationCase in cases {
            let fileURL = temporaryDirectory.appendingPathComponent(
                mutationCase.fileName,
                isDirectory: false
            )
            try mutationCase.data.write(to: fileURL, options: .atomic)
            emitToStandardError(mutationCase.markerLine)

            do {
                let document = try extractor.extractText(from: fileURL)
                XCTAssertEqual(document.fileName, mutationCase.fileName)
                XCTAssertEqual(document.mimeType, mutationCase.format.mimeType)
                XCTAssertFalse(document.text.isEmpty)
                XCTAssertLessThanOrEqual(document.text.count, 8_192)
                XCTAssertLessThanOrEqual(document.text.utf8.count, 16 * 1024)
            } catch {
                try assertAllowed(error, for: mutationCase)
            }
        }

        emitToStandardError(
            DocumentIngestionMutationCorpus.summaryLine(for: cases)
        )
    }

    private func assertAllowed(
        _ error: Error,
        for mutationCase: DocumentMutationCase
    ) throws {
        if mutationCase.operators.last == .padPlusOne4097 {
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(
                    resource: "input file",
                    limit: DocumentIngestionMutationCorpus.inputLimit,
                    actual: DocumentIngestionMutationCorpus.maximumCaseBytes
                ),
                mutationCase.markerLine
            )
            return
        }

        if let validationError = error as? DocumentInputValidationError {
            if mutationCase.format == .txt,
               case .inputReadFailed = validationError {
                return
            }
            XCTFail(
                "unexpected input validation outcome: \(validationError); " +
                    mutationCase.markerLine
            )
            return
        }
        if let processError = error as? DocumentProcessError {
            if mutationCase.format == .rtf || mutationCase.format == .pdf,
               case .timedOut = processError {
                return
            }
            XCTFail(
                "unexpected process outcome: \(processError); " +
                    mutationCase.markerLine
            )
            return
        }
        if let ingestionError = error as? DocumentIngestionError {
            if isAllowed(ingestionError, for: mutationCase.format) {
                return
            }
            XCTFail(
                "unexpected ingestion outcome: \(ingestionError); " +
                    mutationCase.markerLine
            )
            return
        }

        let cocoaError = error as NSError
        if mutationCase.format == .rtf && cocoaError.domain == NSCocoaErrorDomain {
            return
        }
        XCTFail(
            "unexpected error domain \(cocoaError.domain); " +
                mutationCase.markerLine
        )
    }

    private func isAllowed(
        _ error: DocumentIngestionError,
        for format: DocumentMutationFormat
    ) -> Bool {
        switch error {
        case .resourceLimitExceeded, .noExtractableText:
            return true
        case .unreadablePDF:
            return format == .pdf
        case .archiveListingFailed, .archiveEntryReadFailed:
            return format == .docx || format == .epub
        case .converterFailed:
            return format == .webarchive
        case .unsupportedFileType, .invalidResourcePolicy:
            return false
        }
    }

    private func emitToStandardError(_ line: String) {
        FileHandle.standardError.write(Data((line + "\n").utf8))
    }
}
