import Foundation

public enum DocumentIngestionQuality: String, Equatable, Sendable {
    case noUsableText = "no_usable_text"
    case singleChunk = "single_chunk"
    case chunked = "chunked"
}

public let documentIngestionDocumentFileNameCharacterLimitCeiling = 256
public let documentIngestionUnknownDocumentFileName = "untitled-document"

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
        let document = canonicalizedDocumentEnvelope(document)
        try validateExtractedDocumentEnvelope(document)
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

private func canonicalizedDocumentEnvelope(_ document: ExtractedDocument) -> ExtractedDocument {
    ExtractedDocument(
        fileName: canonicalDocumentFileName(document.fileName) ?? documentIngestionUnknownDocumentFileName,
        mimeType: document.mimeType,
        text: document.text
    )
}

private func validateExtractedDocumentEnvelope(_ document: ExtractedDocument) throws {
    guard document.text.count <= documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling else {
        throw DocumentIngestionError.resourceLimitExceeded(
            resource: "extracted text",
            limit: documentIngestionResourcePolicyMaxExtractedTextCharactersCeiling,
            actual: document.text.count
        )
    }
}

private func canonicalDocumentFileName(_ fileName: String?) -> String? {
    guard let fileName else { return nil }
    let trimmed = fileName.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { return nil }

    let normalizedSeparators = trimmed.replacingOccurrences(of: "\\", with: "/")
    guard let lastComponent = normalizedSeparators
        .split(separator: "/", omittingEmptySubsequences: true)
        .last
        .map(String.init)?
        .trimmingCharacters(in: .whitespacesAndNewlines),
        !lastComponent.isEmpty,
        lastComponent != ".",
        lastComponent != "..",
        lastComponent.count <= documentIngestionDocumentFileNameCharacterLimitCeiling,
        !lastComponent.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) })
    else { return nil }

    return lastComponent
}
