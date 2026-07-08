import DocumentIngestion
import Foundation

public struct RuntimeDocumentIndexDocument: Equatable, Sendable {
    public var id: String
    public var displayName: String
    public var mimeType: String
    public var contentFingerprint: String
    public var extractedCharacterCount: Int
    public var chunkCount: Int
    public var quality: DocumentIngestionQuality
}

public struct RuntimeDocumentIndexChunk: Equatable, Sendable {
    public var id: String
    public var documentID: String
    public var documentDisplayName: String
    public var documentMimeType: String
    public var chunkIndex: Int
    public var startCharacterOffset: Int
    public var endCharacterOffset: Int
    public var text: String
}

public struct RuntimeDocumentSearchResult: Equatable, Sendable {
    public var document: RuntimeDocumentIndexDocument
    public var chunk: RuntimeDocumentIndexChunk
    public var rank: Int
    public var matchedTerms: [String]
    public var snippet: String
}

public struct RuntimeDocumentIndexSummary: Equatable, Sendable {
    public var documentCount: Int
    public var chunkCount: Int
    public var extractedCharacterCount: Int
    public var qualityCounts: [DocumentIngestionQuality: Int]
}

public final class RuntimeDocumentIndexStore {
    private var documentsByID: [String: RuntimeDocumentIndexDocument] = [:]
    private var chunksByDocumentID: [String: [RuntimeDocumentIndexChunk]] = [:]
    private let lock = NSLock()

    public init() {}

    public static func stableDocumentID(for result: DocumentIngestionResult) -> String {
        let digest = stableHexDigest([
            result.document.fileName,
            result.document.mimeType,
            result.document.text
        ])
        return "doc_\(digest)"
    }

    public func replaceDocument(
        result: DocumentIngestionResult,
        documentID requestedDocumentID: String? = nil
    ) -> RuntimeDocumentIndexDocument {
        let documentID = requestedDocumentID ?? Self.stableDocumentID(for: result)
        let document = runtimeDocumentIndexDocument(for: result, documentID: documentID)
        let chunks = runtimeDocumentIndexChunks(for: result, documentID: documentID)

        lock.withLock {
            documentsByID[documentID] = document
            chunksByDocumentID[documentID] = chunks
        }
        return document
    }

    public func deleteDocument(id documentID: String) {
        lock.withLock {
            documentsByID.removeValue(forKey: documentID)
            chunksByDocumentID.removeValue(forKey: documentID)
        }
    }

    public func document(id documentID: String) -> RuntimeDocumentIndexDocument? {
        lock.withLock {
            documentsByID[documentID]
        }
    }

    public func chunks(for documentID: String) -> [RuntimeDocumentIndexChunk] {
        lock.withLock {
            chunksByDocumentID[documentID] ?? []
        }
    }

    public func documents(limit: Int = 100) -> [RuntimeDocumentIndexDocument] {
        guard limit > 0 else { return [] }
        let documents = lock.withLock {
            Array(documentsByID.values)
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: limit)
    }

    public func documents(
        matchingContentFingerprint contentFingerprint: String,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard !contentFingerprint.isEmpty, limit > 0 else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter { $0.contentFingerprint == contentFingerprint }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: limit)
    }

    public func documents(
        matchingQuality quality: DocumentIngestionQuality,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard limit > 0 else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter { $0.quality == quality }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: limit)
    }

    public func summary() -> RuntimeDocumentIndexSummary {
        let documents = lock.withLock {
            Array(documentsByID.values)
        }
        return runtimeDocumentIndexSummary(documents)
    }

    public func query(
        _ query: String,
        limit: Int = 10,
        maxSnippetCharacters: Int = 160
    ) -> [RuntimeDocumentSearchResult] {
        let terms = runtimeDocumentSearchTerms(query)
        guard !terms.isEmpty, limit > 0 else { return [] }

        let snapshot = lock.withLock {
            chunksByDocumentID
                .values
                .flatMap { $0 }
                .compactMap { chunk -> (RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)? in
                    guard let document = documentsByID[chunk.documentID] else { return nil }
                    return (document, chunk)
                }
        }

        return runtimeDocumentSearchResults(
            from: snapshot,
            terms: terms,
            limit: limit,
            maxSnippetCharacters: maxSnippetCharacters
        )
    }

    static func stableContentFingerprint(for result: DocumentIngestionResult) -> String {
        stableHexDigest([
            result.document.mimeType,
            result.document.text,
            String(result.summary.extractedCharacterCount),
            String(result.summary.chunkCount)
        ])
    }

    static func stableChunkID(documentID: String, chunk: DocumentChunk) -> String {
        let digest = stableHexDigest([
            documentID,
            String(chunk.index),
            String(chunk.startCharacterOffset),
            String(chunk.endCharacterOffset),
            chunk.text
        ])
        return "chunk_\(digest)"
    }
}

func runtimeDocumentIndexDocument(
    for result: DocumentIngestionResult,
    documentID: String
) -> RuntimeDocumentIndexDocument {
    RuntimeDocumentIndexDocument(
        id: documentID,
        displayName: result.summary.documentFileName,
        mimeType: result.summary.documentMimeType,
        contentFingerprint: RuntimeDocumentIndexStore.stableContentFingerprint(for: result),
        extractedCharacterCount: result.summary.extractedCharacterCount,
        chunkCount: result.summary.chunkCount,
        quality: result.summary.quality
    )
}

func runtimeDocumentIndexChunks(
    for result: DocumentIngestionResult,
    documentID: String
) -> [RuntimeDocumentIndexChunk] {
    result.chunks.map { chunk in
        RuntimeDocumentIndexChunk(
            id: RuntimeDocumentIndexStore.stableChunkID(documentID: documentID, chunk: chunk),
            documentID: documentID,
            documentDisplayName: chunk.documentFileName,
            documentMimeType: chunk.documentMimeType,
            chunkIndex: chunk.index,
            startCharacterOffset: chunk.startCharacterOffset,
            endCharacterOffset: chunk.endCharacterOffset,
            text: chunk.text
        )
    }
}

func runtimeDocumentIndexCatalogDocuments(
    _ documents: [RuntimeDocumentIndexDocument],
    limit: Int
) -> [RuntimeDocumentIndexDocument] {
    guard limit > 0 else { return [] }
    return documents
        .sorted { lhs, rhs in
            if lhs.displayName != rhs.displayName {
                return lhs.displayName < rhs.displayName
            }
            return lhs.id < rhs.id
        }
        .prefix(limit)
        .map { $0 }
}

func runtimeDocumentIndexSummary(
    _ documents: [RuntimeDocumentIndexDocument]
) -> RuntimeDocumentIndexSummary {
    documents.reduce(into: RuntimeDocumentIndexSummary(
        documentCount: 0,
        chunkCount: 0,
        extractedCharacterCount: 0,
        qualityCounts: [:]
    )) { summary, document in
        summary.documentCount += 1
        summary.chunkCount += document.chunkCount
        summary.extractedCharacterCount += document.extractedCharacterCount
        summary.qualityCounts[document.quality, default: 0] += 1
    }
}

func runtimeDocumentSearchTerms(_ query: String) -> [String] {
    var seen = Set<String>()
    return query
        .lowercased()
        .split { character in
            !character.unicodeScalars.allSatisfy { CharacterSet.alphanumerics.contains($0) }
        }
        .compactMap { rawTerm -> String? in
            let term = String(rawTerm)
            guard !term.isEmpty, !seen.contains(term) else { return nil }
            seen.insert(term)
            return term
        }
}

func runtimeDocumentSearchResults(
    from snapshot: [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)],
    query: String,
    limit: Int = 10,
    maxSnippetCharacters: Int = 160
) -> [RuntimeDocumentSearchResult] {
    let terms = runtimeDocumentSearchTerms(query)
    guard !terms.isEmpty, limit > 0 else { return [] }
    return runtimeDocumentSearchResults(
        from: snapshot,
        terms: terms,
        limit: limit,
        maxSnippetCharacters: maxSnippetCharacters
    )
}

private func runtimeDocumentSearchResults(
    from snapshot: [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)],
    terms: [String],
    limit: Int,
    maxSnippetCharacters: Int
) -> [RuntimeDocumentSearchResult] {
    snapshot.compactMap { document, chunk in
        let counts = matchCounts(in: chunk.text, terms: terms)
        let matchedTerms = terms.filter { (counts[$0] ?? 0) > 0 }
        guard !matchedTerms.isEmpty else { return nil }
        let rank = matchedTerms.count * 100 + counts.values.reduce(0, +)
        return RuntimeDocumentSearchResult(
            document: document,
            chunk: chunk,
            rank: rank,
            matchedTerms: matchedTerms,
            snippet: boundedSnippet(from: chunk.text, terms: matchedTerms, maxCharacters: maxSnippetCharacters)
        )
    }
    .sorted { lhs, rhs in
        if lhs.rank != rhs.rank { return lhs.rank > rhs.rank }
        if lhs.document.displayName != rhs.document.displayName {
            return lhs.document.displayName < rhs.document.displayName
        }
        return lhs.chunk.chunkIndex < rhs.chunk.chunkIndex
    }
    .prefix(limit)
    .map { $0 }
}

private func matchCounts(in text: String, terms: [String]) -> [String: Int] {
    let searchableText = text.lowercased()
    return terms.reduce(into: [String: Int]()) { counts, term in
        var searchStart = searchableText.startIndex
        while let range = searchableText.range(of: term, range: searchStart..<searchableText.endIndex) {
            counts[term, default: 0] += 1
            searchStart = range.upperBound
        }
    }
}

private func boundedSnippet(from text: String, terms: [String], maxCharacters: Int) -> String {
    guard maxCharacters > 0 else { return "" }
    guard let firstRange = firstMatchRange(in: text, terms: terms) else {
        return String(text.prefix(maxCharacters))
    }

    let usesPrefix = firstRange.lowerBound > text.startIndex
    let usesSuffix = firstRange.upperBound < text.endIndex
    let prefix = usesPrefix ? "..." : ""
    let suffix = usesSuffix ? "..." : ""
    let contentBudget = max(0, maxCharacters - prefix.count - suffix.count)
    guard contentBudget > 0 else {
        return String((prefix + suffix).prefix(maxCharacters))
    }

    let matchedOffset = text.distance(from: text.startIndex, to: firstRange.lowerBound)
    let halfBudget = max(0, contentBudget / 2)
    let startOffset = max(0, matchedOffset - halfBudget)
    let startIndex = text.index(text.startIndex, offsetBy: startOffset)
    let endIndex = text.index(startIndex, offsetBy: min(contentBudget, text.distance(from: startIndex, to: text.endIndex)))
    return prefix + text[startIndex..<endIndex].trimmingCharacters(in: .whitespacesAndNewlines) + suffix
}

private func firstMatchRange(in text: String, terms: [String]) -> Range<String.Index>? {
    terms
        .compactMap { term in
            text.range(of: term, options: [.caseInsensitive, .diacriticInsensitive])
        }
        .min { lhs, rhs in lhs.lowerBound < rhs.lowerBound }
}

private func stableHexDigest(_ values: [String]) -> String {
    var hash: UInt64 = 0xcbf29ce484222325
    for value in values {
        for byte in value.utf8 {
            hash ^= UInt64(byte)
            hash = hash &* 0x100000001b3
        }
        hash ^= 0xff
        hash = hash &* 0x100000001b3
    }
    let hex = String(hash, radix: 16)
    return String(repeating: "0", count: max(0, 16 - hex.count)) + hex
}

private extension NSLock {
    func withLock<T>(_ operation: () -> T) -> T {
        lock()
        defer { unlock() }
        return operation()
    }
}
