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

public struct RuntimeDocumentIndexChunkSummary: Equatable, Sendable {
    public var documentID: String
    public var documentDisplayName: String
    public var documentMimeType: String
    public var chunkIndex: Int
    public var startCharacterOffset: Int
    public var endCharacterOffset: Int
    public var characterCount: Int
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

public protocol RuntimeDocumentIndexCatalogReading {
    func documents(limit: Int) throws -> [RuntimeDocumentIndexDocument]
    func summary() throws -> RuntimeDocumentIndexSummary
}

struct RuntimeDocumentIndexChunkEnvelope: Equatable, Sendable {
    var chunkIndex: Int
    var startCharacterOffset: Int
    var endCharacterOffset: Int
}

let runtimeDocumentIndexCatalogLimitCeiling = 100
let runtimeDocumentIndexChunkReadLimitCeiling = 200
let runtimeDocumentIndexChunkSummaryLimitCeiling = 100
let runtimeDocumentIndexQueryLimitCeiling = 100
let runtimeDocumentIndexSnippetCharacterLimitCeiling = 500
let runtimeDocumentIndexDocumentIDCharacterLimitCeiling = 128
let runtimeDocumentIndexContentFingerprintCharacterCount = 16
let runtimeDocumentIndexMimeTypeCharacterLimitCeiling = 128
let runtimeDocumentIndexUnknownMimeType = "application/octet-stream"
let runtimeDocumentIndexDisplayNameCharacterLimitCeiling = 256
let runtimeDocumentIndexUnknownDisplayName = "untitled-document"
let runtimeDocumentIndexQueryTextCharacterLimitCeiling = 1_024
let runtimeDocumentIndexQueryTermLimitCeiling = 16
let runtimeDocumentIndexQueryTermCharacterLimitCeiling = 64

public final class RuntimeDocumentIndexStore {
    private var documentsByID: [String: RuntimeDocumentIndexDocument] = [:]
    private var chunksByDocumentID: [String: [RuntimeDocumentIndexChunk]] = [:]
    private let lock = NSLock()

    public init() {}

    public static func stableDocumentID(for result: DocumentIngestionResult) -> String {
        let digest = stableHexDigest([
            runtimeDocumentIndexEffectiveDisplayName(for: result),
            runtimeDocumentIndexEffectiveMimeType(result.summary.documentMimeType),
            result.document.text
        ])
        return "doc_\(digest)"
    }

    public func replaceDocument(
        result: DocumentIngestionResult,
        documentID requestedDocumentID: String? = nil
    ) -> RuntimeDocumentIndexDocument {
        let documentID = runtimeDocumentIndexEffectiveDocumentID(
            requestedDocumentID,
            fallback: Self.stableDocumentID(for: result)
        )
        let document = runtimeDocumentIndexDocument(for: result, documentID: documentID)
        let chunks = runtimeDocumentIndexChunks(for: result, documentID: documentID)

        lock.withLock {
            documentsByID[documentID] = document
            chunksByDocumentID[documentID] = chunks
        }
        return document
    }

    public func deleteDocument(id documentID: String) {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return }
        lock.withLock {
            documentsByID.removeValue(forKey: documentID)
            chunksByDocumentID.removeValue(forKey: documentID)
        }
    }

    public func deleteAllDocuments() {
        lock.withLock {
            documentsByID.removeAll()
            chunksByDocumentID.removeAll()
        }
    }

    public func deleteDocuments(matchingQuality quality: DocumentIngestionQuality) {
        lock.withLock {
            let documentIDs = documentsByID
                .values
                .filter { $0.quality == quality }
                .map(\.id)
            for documentID in documentIDs {
                documentsByID.removeValue(forKey: documentID)
                chunksByDocumentID.removeValue(forKey: documentID)
            }
        }
    }

    public func deleteDocuments(matchingContentFingerprint contentFingerprint: String) {
        guard let contentFingerprint = runtimeDocumentIndexCanonicalContentFingerprint(contentFingerprint) else { return }
        lock.withLock {
            let documentIDs = documentsByID
                .values
                .filter { $0.contentFingerprint == contentFingerprint }
                .map(\.id)
            for documentID in documentIDs {
                documentsByID.removeValue(forKey: documentID)
                chunksByDocumentID.removeValue(forKey: documentID)
            }
        }
    }

    public func deleteDocuments(matchingDisplayName displayName: String) {
        guard let displayName = runtimeDocumentIndexCanonicalDisplayName(displayName) else { return }
        lock.withLock {
            let documentIDs = documentsByID
                .values
                .filter { $0.displayName == displayName }
                .map(\.id)
            for documentID in documentIDs {
                documentsByID.removeValue(forKey: documentID)
                chunksByDocumentID.removeValue(forKey: documentID)
            }
        }
    }

    public func deleteDocuments(matchingMimeType mimeType: String) {
        guard let mimeType = runtimeDocumentIndexCanonicalMimeType(mimeType) else { return }
        lock.withLock {
            let documentIDs = documentsByID
                .values
                .filter { $0.mimeType == mimeType }
                .map(\.id)
            for documentID in documentIDs {
                documentsByID.removeValue(forKey: documentID)
                chunksByDocumentID.removeValue(forKey: documentID)
            }
        }
    }

    public func document(id documentID: String) -> RuntimeDocumentIndexDocument? {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return nil }
        return lock.withLock {
            documentsByID[documentID]
        }
    }

    public func chunks(
        for documentID: String,
        limit: Int = 200
    ) -> [RuntimeDocumentIndexChunk] {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexChunkReadLimitCeiling
              ) else { return [] }
        let chunks = lock.withLock {
            chunksByDocumentID[documentID] ?? []
        }
        return runtimeDocumentIndexChunksForRead(chunks, limit: effectiveLimit)
    }

    public func chunkSummaries(
        for documentID: String,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexChunkSummary] {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexChunkSummaryLimitCeiling
              ) else { return [] }
        let chunks = lock.withLock {
            chunksByDocumentID[documentID] ?? []
        }
        return runtimeDocumentIndexChunkSummaries(chunks, limit: effectiveLimit)
    }

    public func documents(limit: Int = 100) -> [RuntimeDocumentIndexDocument] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else { return [] }
        let documents = lock.withLock {
            Array(documentsByID.values)
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
    }

    public func documents(
        matchingDisplayName displayName: String,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard let displayName = runtimeDocumentIndexCanonicalDisplayName(displayName),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter { $0.displayName == displayName }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
    }

    public func documents(
        matchingContentFingerprint contentFingerprint: String,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard let contentFingerprint = runtimeDocumentIndexCanonicalContentFingerprint(contentFingerprint),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter { $0.contentFingerprint == contentFingerprint }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
    }

    public func documents(
        matchingMimeType mimeType: String,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard let mimeType = runtimeDocumentIndexCanonicalMimeType(mimeType),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter { $0.mimeType == mimeType }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
    }

    public func documents(
        matchingQuality quality: DocumentIngestionQuality,
        limit: Int = 100
    ) -> [RuntimeDocumentIndexDocument] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else { return [] }
        let documents = lock.withLock {
            documentsByID.values.filter { $0.quality == quality }
        }
        return runtimeDocumentIndexCatalogDocuments(documents, limit: effectiveLimit)
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
        guard !terms.isEmpty,
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexQueryLimitCeiling
              ),
              let effectiveSnippetLimit = runtimeDocumentIndexEffectiveLimit(
                maxSnippetCharacters,
                ceiling: runtimeDocumentIndexSnippetCharacterLimitCeiling
              ) else { return [] }

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
            limit: effectiveLimit,
            maxSnippetCharacters: effectiveSnippetLimit
        )
    }

    static func stableContentFingerprint(for result: DocumentIngestionResult) -> String {
        stableHexDigest([
            runtimeDocumentIndexEffectiveMimeType(result.summary.documentMimeType),
            result.document.text,
            String(runtimeDocumentIndexEffectiveExtractedCharacterCount(for: result)),
            String(runtimeDocumentIndexEffectiveChunkCount(for: result))
        ])
    }

    static func stableChunkID(
        documentID: String,
        chunkIndex: Int,
        startCharacterOffset: Int,
        endCharacterOffset: Int,
        text: String
    ) -> String {
        let digest = stableHexDigest([
            documentID,
            String(chunkIndex),
            String(startCharacterOffset),
            String(endCharacterOffset),
            text
        ])
        return "chunk_\(digest)"
    }
}

extension RuntimeDocumentIndexStore: RuntimeDocumentIndexCatalogReading {}

func runtimeDocumentIndexDocument(
    for result: DocumentIngestionResult,
    documentID: String
) -> RuntimeDocumentIndexDocument {
    RuntimeDocumentIndexDocument(
        id: documentID,
        displayName: runtimeDocumentIndexEffectiveDisplayName(for: result),
        mimeType: runtimeDocumentIndexEffectiveMimeType(result.summary.documentMimeType),
        contentFingerprint: RuntimeDocumentIndexStore.stableContentFingerprint(for: result),
        extractedCharacterCount: runtimeDocumentIndexEffectiveExtractedCharacterCount(for: result),
        chunkCount: runtimeDocumentIndexEffectiveChunkCount(for: result),
        quality: runtimeDocumentIndexEffectiveQuality(for: result)
    )
}

func runtimeDocumentIndexEffectiveExtractedCharacterCount(for result: DocumentIngestionResult) -> Int {
    result.document.text.trimmingCharacters(in: .whitespacesAndNewlines).count
}

func runtimeDocumentIndexEffectiveChunkCount(for result: DocumentIngestionResult) -> Int {
    result.chunks.count
}

func runtimeDocumentIndexEffectiveQuality(for result: DocumentIngestionResult) -> DocumentIngestionQuality {
    switch runtimeDocumentIndexEffectiveChunkCount(for: result) {
    case 0:
        return .noUsableText
    case 1:
        return .singleChunk
    default:
        return .chunked
    }
}

func runtimeDocumentIndexEffectiveDisplayName(for result: DocumentIngestionResult) -> String {
    runtimeDocumentIndexCanonicalDisplayName(result.document.fileName)
        ?? runtimeDocumentIndexCanonicalDisplayName(result.summary.documentFileName)
        ?? runtimeDocumentIndexUnknownDisplayName
}

func runtimeDocumentIndexChunks(
    for result: DocumentIngestionResult,
    documentID: String
) -> [RuntimeDocumentIndexChunk] {
    let documentDisplayName = runtimeDocumentIndexEffectiveDisplayName(for: result)
    let documentCharacters = Array(result.document.text.trimmingCharacters(in: .whitespacesAndNewlines))
    var fallbackStartOffset = 0
    var minimumSearchStartOffset = 0

    return result.chunks.enumerated().map { canonicalIndex, chunk in
        let envelope = runtimeDocumentIndexEffectiveChunkEnvelope(
            for: chunk,
            canonicalIndex: canonicalIndex,
            documentCharacters: documentCharacters,
            minimumSearchStartOffset: minimumSearchStartOffset,
            fallbackStartOffset: fallbackStartOffset
        )
        fallbackStartOffset = max(fallbackStartOffset, envelope.endCharacterOffset)
        minimumSearchStartOffset = min(envelope.startCharacterOffset + 1, documentCharacters.count)

        return RuntimeDocumentIndexChunk(
            id: RuntimeDocumentIndexStore.stableChunkID(
                documentID: documentID,
                chunkIndex: envelope.chunkIndex,
                startCharacterOffset: envelope.startCharacterOffset,
                endCharacterOffset: envelope.endCharacterOffset,
                text: chunk.text
            ),
            documentID: documentID,
            documentDisplayName: documentDisplayName,
            documentMimeType: runtimeDocumentIndexEffectiveMimeType(chunk.documentMimeType),
            chunkIndex: envelope.chunkIndex,
            startCharacterOffset: envelope.startCharacterOffset,
            endCharacterOffset: envelope.endCharacterOffset,
            text: chunk.text
        )
    }
}

func runtimeDocumentIndexEffectiveChunkEnvelope(
    for chunk: DocumentChunk,
    canonicalIndex: Int,
    documentCharacters: [Character],
    minimumSearchStartOffset: Int,
    fallbackStartOffset: Int
) -> RuntimeDocumentIndexChunkEnvelope {
    let offsets = runtimeDocumentIndexValidatedChunkOffsets(
        for: chunk,
        documentCharacters: documentCharacters,
        minimumSearchStartOffset: minimumSearchStartOffset
    )
        ?? runtimeDocumentIndexLocatedChunkOffsets(
            for: chunk.text,
            documentCharacters: documentCharacters,
            minimumSearchStartOffset: minimumSearchStartOffset
        )
        ?? runtimeDocumentIndexFallbackChunkOffsets(
            for: chunk.text,
            documentCharacterCount: documentCharacters.count,
            fallbackStartOffset: fallbackStartOffset
        )
    return RuntimeDocumentIndexChunkEnvelope(
        chunkIndex: canonicalIndex,
        startCharacterOffset: offsets.start,
        endCharacterOffset: offsets.end
    )
}

func runtimeDocumentIndexValidatedChunkOffsets(
    for chunk: DocumentChunk,
    documentCharacters: [Character],
    minimumSearchStartOffset: Int
) -> (start: Int, end: Int)? {
    guard chunk.startCharacterOffset >= 0,
          chunk.startCharacterOffset >= minimumSearchStartOffset,
          chunk.endCharacterOffset >= chunk.startCharacterOffset,
          chunk.endCharacterOffset <= documentCharacters.count else { return nil }
    let text = String(documentCharacters[chunk.startCharacterOffset..<chunk.endCharacterOffset])
    guard text == chunk.text else { return nil }
    return (chunk.startCharacterOffset, chunk.endCharacterOffset)
}

func runtimeDocumentIndexLocatedChunkOffsets(
    for text: String,
    documentCharacters: [Character],
    minimumSearchStartOffset: Int
) -> (start: Int, end: Int)? {
    let chunkCharacters = Array(text)
    guard !chunkCharacters.isEmpty,
          chunkCharacters.count <= documentCharacters.count else { return nil }
    let lastStart = documentCharacters.count - chunkCharacters.count
    let firstStart = min(max(minimumSearchStartOffset, 0), documentCharacters.count)
    guard firstStart <= lastStart else { return nil }
    for start in firstStart...lastStart {
        let end = start + chunkCharacters.count
        if Array(documentCharacters[start..<end]) == chunkCharacters {
            return (start, end)
        }
    }
    return nil
}

func runtimeDocumentIndexFallbackChunkOffsets(
    for text: String,
    documentCharacterCount: Int,
    fallbackStartOffset: Int
) -> (start: Int, end: Int) {
    let start = min(max(fallbackStartOffset, 0), documentCharacterCount)
    let end = min(start + text.count, documentCharacterCount)
    return (start, end)
}

func runtimeDocumentIndexEffectiveDocumentID(_ requestedDocumentID: String?, fallback: String) -> String {
    runtimeDocumentIndexCanonicalDocumentID(requestedDocumentID) ?? fallback
}

func runtimeDocumentIndexCanonicalDocumentID(_ documentID: String?) -> String? {
    guard let documentID else { return nil }
    let trimmed = documentID.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty,
          !trimmed.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }),
          trimmed.count <= runtimeDocumentIndexDocumentIDCharacterLimitCeiling else { return nil }
    return trimmed
}

func runtimeDocumentIndexCanonicalDisplayName(_ displayName: String?) -> String? {
    guard let displayName else { return nil }
    let trimmed = displayName.trimmingCharacters(in: .whitespacesAndNewlines)
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
        !lastComponent.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }),
        lastComponent.count <= runtimeDocumentIndexDisplayNameCharacterLimitCeiling
    else { return nil }

    return lastComponent
}

func runtimeDocumentIndexCanonicalContentFingerprint(_ contentFingerprint: String?) -> String? {
    guard let contentFingerprint else { return nil }
    let trimmed = contentFingerprint.trimmingCharacters(in: .whitespacesAndNewlines)
    guard trimmed.count == runtimeDocumentIndexContentFingerprintCharacterCount,
          trimmed.utf8.allSatisfy({ byte in
            (byte >= 48 && byte <= 57) || (byte >= 97 && byte <= 102)
          }) else { return nil }
    return trimmed
}

func runtimeDocumentIndexEffectiveMimeType(_ mimeType: String?) -> String {
    runtimeDocumentIndexCanonicalMimeType(mimeType) ?? runtimeDocumentIndexUnknownMimeType
}

func runtimeDocumentIndexCanonicalMimeType(_ mimeType: String?) -> String? {
    guard let mimeType else { return nil }
    let trimmed = mimeType.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty,
          trimmed.count <= runtimeDocumentIndexMimeTypeCharacterLimitCeiling else { return nil }
    let parts = trimmed.split(separator: "/", omittingEmptySubsequences: false)
    guard parts.count == 2,
          parts.allSatisfy({ !$0.isEmpty }),
          parts.allSatisfy({ component in
            component.utf8.allSatisfy(runtimeDocumentIndexMimeTypeTokenByteIsAllowed)
          }) else { return nil }
    return trimmed
}

private func runtimeDocumentIndexMimeTypeTokenByteIsAllowed(_ byte: UInt8) -> Bool {
    (byte >= 48 && byte <= 57)
        || (byte >= 97 && byte <= 122)
        || byte == 33
        || byte == 35
        || byte == 36
        || byte == 37
        || byte == 38
        || byte == 39
        || byte == 42
        || byte == 43
        || byte == 45
        || byte == 46
        || byte == 94
        || byte == 95
        || byte == 96
        || byte == 124
        || byte == 126
}

func runtimeDocumentIndexChunkSummaries(
    _ chunks: [RuntimeDocumentIndexChunk],
    limit: Int
) -> [RuntimeDocumentIndexChunkSummary] {
    guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
        limit,
        ceiling: runtimeDocumentIndexChunkSummaryLimitCeiling
    ) else { return [] }
    return chunks
        .sorted { lhs, rhs in lhs.chunkIndex < rhs.chunkIndex }
        .prefix(effectiveLimit)
        .map { chunk in
            RuntimeDocumentIndexChunkSummary(
                documentID: chunk.documentID,
                documentDisplayName: chunk.documentDisplayName,
                documentMimeType: chunk.documentMimeType,
                chunkIndex: chunk.chunkIndex,
                startCharacterOffset: chunk.startCharacterOffset,
                endCharacterOffset: chunk.endCharacterOffset,
                characterCount: chunk.text.count
            )
        }
}

func runtimeDocumentIndexChunksForRead(
    _ chunks: [RuntimeDocumentIndexChunk],
    limit: Int
) -> [RuntimeDocumentIndexChunk] {
    guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
        limit,
        ceiling: runtimeDocumentIndexChunkReadLimitCeiling
    ) else { return [] }
    return chunks
        .sorted { lhs, rhs in lhs.chunkIndex < rhs.chunkIndex }
        .prefix(effectiveLimit)
        .map { $0 }
}

func runtimeDocumentIndexCatalogDocuments(
    _ documents: [RuntimeDocumentIndexDocument],
    limit: Int
) -> [RuntimeDocumentIndexDocument] {
    guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
        limit,
        ceiling: runtimeDocumentIndexCatalogLimitCeiling
    ) else { return [] }
    return documents
        .sorted { lhs, rhs in
            if lhs.displayName != rhs.displayName {
                return lhs.displayName < rhs.displayName
            }
            return lhs.id < rhs.id
        }
        .prefix(effectiveLimit)
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
    runtimeDocumentIndexEffectiveSearchTerms(query)
}

func runtimeDocumentIndexEffectiveSearchTerms(_ query: String) -> [String] {
    guard query.count <= runtimeDocumentIndexQueryTextCharacterLimitCeiling else { return [] }

    var seen = Set<String>()
    var terms: [String] = []
    for rawTerm in query.lowercased().split(whereSeparator: { character in
        !character.unicodeScalars.allSatisfy { CharacterSet.alphanumerics.contains($0) }
    }) {
        let term = String(rawTerm)
        guard term.count <= runtimeDocumentIndexQueryTermCharacterLimitCeiling else { return [] }
        guard !term.isEmpty, !seen.contains(term) else { continue }
        seen.insert(term)
        terms.append(term)
        guard terms.count <= runtimeDocumentIndexQueryTermLimitCeiling else { return [] }
    }
    return terms
}

func runtimeDocumentSearchResults(
    from snapshot: [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)],
    query: String,
    limit: Int = 10,
    maxSnippetCharacters: Int = 160
) -> [RuntimeDocumentSearchResult] {
    let terms = runtimeDocumentSearchTerms(query)
    guard !terms.isEmpty,
          let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexQueryLimitCeiling
          ),
          let effectiveSnippetLimit = runtimeDocumentIndexEffectiveLimit(
            maxSnippetCharacters,
            ceiling: runtimeDocumentIndexSnippetCharacterLimitCeiling
          ) else { return [] }
    return runtimeDocumentSearchResults(
        from: snapshot,
        terms: terms,
        limit: effectiveLimit,
        maxSnippetCharacters: effectiveSnippetLimit
    )
}

private func runtimeDocumentSearchResults(
    from snapshot: [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)],
    terms: [String],
    limit: Int,
    maxSnippetCharacters: Int
) -> [RuntimeDocumentSearchResult] {
    guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
        limit,
        ceiling: runtimeDocumentIndexQueryLimitCeiling
    ),
          let effectiveSnippetLimit = runtimeDocumentIndexEffectiveLimit(
            maxSnippetCharacters,
            ceiling: runtimeDocumentIndexSnippetCharacterLimitCeiling
          ) else { return [] }
    return snapshot.compactMap { document, chunk in
        let counts = matchCounts(in: chunk.text, terms: terms)
        let matchedTerms = terms.filter { (counts[$0] ?? 0) > 0 }
        guard !matchedTerms.isEmpty else { return nil }
        let rank = matchedTerms.count * 100 + counts.values.reduce(0, +)
        return RuntimeDocumentSearchResult(
            document: document,
            chunk: chunk,
            rank: rank,
            matchedTerms: matchedTerms,
            snippet: boundedSnippet(from: chunk.text, terms: matchedTerms, maxCharacters: effectiveSnippetLimit)
        )
    }
    .sorted { lhs, rhs in
        if lhs.rank != rhs.rank { return lhs.rank > rhs.rank }
        if lhs.document.displayName != rhs.document.displayName {
            return lhs.document.displayName < rhs.document.displayName
        }
        return lhs.chunk.chunkIndex < rhs.chunk.chunkIndex
    }
    .prefix(effectiveLimit)
    .map { $0 }
}

func runtimeDocumentIndexEffectiveLimit(_ requestedLimit: Int, ceiling: Int) -> Int? {
    guard requestedLimit > 0, ceiling > 0 else { return nil }
    return min(requestedLimit, ceiling)
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
