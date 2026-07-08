import Foundation

public enum DocumentIngestionQuality: String, Equatable, Sendable {
    case noUsableText = "no_usable_text"
    case singleChunk = "single_chunk"
    case chunked = "chunked"
}

public struct DocumentIngestionSummary: Equatable, Sendable {
    public var documentFileName: String
    public var documentMimeType: String
    public var extractedCharacterCount: Int
    public var chunkCount: Int
    public var minChunkCharacters: Int
    public var maxChunkCharacters: Int
    public var quality: DocumentIngestionQuality

    public init(
        documentFileName: String,
        documentMimeType: String,
        extractedCharacterCount: Int,
        chunkCount: Int,
        minChunkCharacters: Int,
        maxChunkCharacters: Int,
        quality: DocumentIngestionQuality
    ) {
        self.documentFileName = documentFileName
        self.documentMimeType = documentMimeType
        self.extractedCharacterCount = extractedCharacterCount
        self.chunkCount = chunkCount
        self.minChunkCharacters = minChunkCharacters
        self.maxChunkCharacters = maxChunkCharacters
        self.quality = quality
    }
}

public struct DocumentIngestionResult: Equatable, Sendable {
    public var document: ExtractedDocument
    public var chunks: [DocumentChunk]
    public var summary: DocumentIngestionSummary

    public init(
        document: ExtractedDocument,
        chunks: [DocumentChunk],
        summary: DocumentIngestionSummary
    ) {
        self.document = document
        self.chunks = chunks
        self.summary = summary
    }
}

public final class DocumentIngestor: Sendable {
    private let textExtractor: DocumentTextExtractor
    private let chunker: DocumentChunker

    public init(
        textExtractor: DocumentTextExtractor = DocumentTextExtractor(),
        chunker: DocumentChunker = DocumentChunker()
    ) {
        self.textExtractor = textExtractor
        self.chunker = chunker
    }

    public func ingest(fileURL: URL, mimeType: String? = nil) throws -> DocumentIngestionResult {
        try ingest(extractedDocument: textExtractor.extractText(from: fileURL, mimeType: mimeType))
    }

    public func ingest(extractedDocument document: ExtractedDocument) throws -> DocumentIngestionResult {
        let chunks = try chunker.chunks(from: document)
        return DocumentIngestionResult(
            document: document,
            chunks: chunks,
            summary: summary(for: document, chunks: chunks)
        )
    }

    private func summary(for document: ExtractedDocument, chunks: [DocumentChunk]) -> DocumentIngestionSummary {
        let chunkLengths = chunks.map { $0.text.count }
        let quality: DocumentIngestionQuality
        switch chunks.count {
        case 0:
            quality = .noUsableText
        case 1:
            quality = .singleChunk
        default:
            quality = .chunked
        }

        return DocumentIngestionSummary(
            documentFileName: document.fileName,
            documentMimeType: document.mimeType,
            extractedCharacterCount: document.text.trimmingCharacters(in: .whitespacesAndNewlines).count,
            chunkCount: chunks.count,
            minChunkCharacters: chunkLengths.min() ?? 0,
            maxChunkCharacters: chunkLengths.max() ?? 0,
            quality: quality
        )
    }
}
