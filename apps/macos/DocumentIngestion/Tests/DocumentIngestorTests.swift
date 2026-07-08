import XCTest
@testable import DocumentIngestion

final class DocumentIngestorTests: XCTestCase {
    func testIngestsExtractedDocumentIntoChunksAndSafeSummary() throws {
        let document = ExtractedDocument(
            fileName: "runtime-notes.md",
            mimeType: "text/markdown",
            text: [
                "AetherLink indexes user-approved documents inside the runtime boundary.",
                "Chunk metadata stays structural before embeddings or retrieval are introduced."
            ].joined(separator: " ")
        )

        let result = try DocumentIngestor(chunker: DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 72,
            overlapCharacters: 6,
            minChunkCharacters: 32
        ))).ingest(extractedDocument: document)

        XCTAssertEqual(result.document, document)
        XCTAssertGreaterThan(result.chunks.count, 1)
        XCTAssertEqual(result.summary.documentFileName, "runtime-notes.md")
        XCTAssertEqual(result.summary.documentMimeType, "text/markdown")
        XCTAssertEqual(result.summary.extractedCharacterCount, document.text.count)
        XCTAssertEqual(result.summary.chunkCount, result.chunks.count)
        XCTAssertEqual(result.summary.minChunkCharacters, result.chunks.map { $0.text.count }.min() ?? 0)
        XCTAssertEqual(result.summary.maxChunkCharacters, result.chunks.map { $0.text.count }.max() ?? 0)
        XCTAssertEqual(result.summary.quality, .chunked)
        XCTAssertEqual(result.chunks.map(\.documentFileName), Array(repeating: "runtime-notes.md", count: result.chunks.count))
        XCTAssertEqual(result.chunks.map(\.documentMimeType), Array(repeating: "text/markdown", count: result.chunks.count))
    }

    func testIngestsFileThroughExtractorWithoutLeakingSourcePathIntoSummary() throws {
        let fileURL = try writeText("AetherLink file ingestion keeps source paths out of portable summaries.", extension: "txt")

        let result = try DocumentIngestor(chunker: DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 120,
            overlapCharacters: 0,
            minChunkCharacters: 20
        ))).ingest(fileURL: fileURL)

        XCTAssertEqual(result.document.fileName, fileURL.lastPathComponent)
        XCTAssertEqual(result.document.mimeType, "text/plain")
        XCTAssertEqual(result.summary.documentFileName, fileURL.lastPathComponent)
        XCTAssertFalse(result.summary.documentFileName.contains(fileURL.deletingLastPathComponent().path))
        XCTAssertEqual(result.summary.documentMimeType, "text/plain")
        XCTAssertEqual(result.summary.chunkCount, 1)
        XCTAssertEqual(result.summary.quality, .singleChunk)
        XCTAssertEqual(result.chunks.single?.text, result.document.text)
    }

    func testWhitespaceExtractedDocumentProducesNoUsableTextSummary() throws {
        let result = try DocumentIngestor().ingest(extractedDocument: ExtractedDocument(
            fileName: "blank.txt",
            mimeType: "text/plain",
            text: " \n\t "
        ))

        XCTAssertEqual(result.chunks, [])
        XCTAssertEqual(result.summary.extractedCharacterCount, 0)
        XCTAssertEqual(result.summary.chunkCount, 0)
        XCTAssertEqual(result.summary.minChunkCharacters, 0)
        XCTAssertEqual(result.summary.maxChunkCharacters, 0)
        XCTAssertEqual(result.summary.quality, .noUsableText)
    }

    func testPropagatesChunkingPolicyErrorsBeforeReturningResult() {
        let document = ExtractedDocument(fileName: "bad-policy.txt", mimeType: "text/plain", text: "policy")
        let ingestor = DocumentIngestor(chunker: DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 32,
            overlapCharacters: 32,
            minChunkCharacters: 8
        )))

        XCTAssertThrowsError(try ingestor.ingest(extractedDocument: document)) { error in
            XCTAssertEqual(
                error as? DocumentChunkingError,
                .invalidPolicy("overlapCharacters must be less than maxCharacters")
            )
        }
    }

    private func writeText(_ text: String, extension pathExtension: String) throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let fileURL = directory.appendingPathComponent("sample.\(pathExtension)")
        try text.data(using: .utf8)?.write(to: fileURL)
        addTeardownBlock {
            try? FileManager.default.removeItem(at: directory)
        }
        return fileURL
    }
}

private extension Array {
    var single: Element? {
        count == 1 ? self[0] : nil
    }
}
