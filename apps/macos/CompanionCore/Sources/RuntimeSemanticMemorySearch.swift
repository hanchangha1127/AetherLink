import CryptoKit
import Foundation

struct RuntimeSemanticMemoryCandidate: Sendable {
    var entry: RuntimeMemoryEntry
    var sourceRevision: String
    var document: String
    var documentFingerprint: String
}

enum RuntimeSemanticMemorySearch {
    static let maximumCandidateCount = 200
    static let maximumDocumentUTF8Bytes = 4_096
    static let fallbackDocumentUTF8Bytes = 1_024
    static let documentEncodingVersion = "approved-memory-semantic-document-v1"
    static let sourceRevisionVersion = "approved-memory-source-revision-v1"

    static func candidate(
        source: RuntimeMemorySemanticSearchSource,
        maximumDocumentUTF8Bytes: Int = maximumDocumentUTF8Bytes
    ) -> RuntimeSemanticMemoryCandidate? {
        let limit = max(1, min(maximumDocumentUTF8Bytes, Self.maximumDocumentUTF8Bytes))
        let content = source.entry.content
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !content.isEmpty else { return nil }
        let document = utf8Prefix(content, maximumBytes: limit)
        guard !document.isEmpty else { return nil }
        return RuntimeSemanticMemoryCandidate(
            entry: source.entry,
            sourceRevision: source.sourceRevision,
            document: document,
            documentFingerprint: fingerprint(fields: [
                documentEncodingVersion,
                String(limit),
                document
            ])
        )
    }

    static func sourceRevision(for entry: RuntimeMemoryEntry) -> String {
        fingerprint(fields: [
            sourceRevisionVersion,
            entry.id,
            entry.content,
            entry.enabled ? "enabled" : "disabled",
            timestamp(entry.createdAt),
            timestamp(entry.updatedAt),
            canonicalSource(entry.source)
        ])
    }

    static func rankedEntries(
        candidates: [RuntimeSemanticMemoryCandidate],
        queryEmbedding: [Double],
        candidateEmbeddings: [[Double]]
    ) throws -> [RuntimeMemoryEntry] {
        guard queryEmbedding.isValidSemanticEmbedding else {
            throw RuntimeSemanticMemorySearchError.invalidQueryEmbedding
        }
        guard candidateEmbeddings.count == candidates.count else {
            throw RuntimeSemanticMemorySearchError.embeddingCountMismatch
        }
        let scored = try zip(candidates, candidateEmbeddings).map { candidate, embedding in
            guard embedding.count == queryEmbedding.count,
                  embedding.isValidSemanticEmbedding else {
                throw RuntimeSemanticMemorySearchError.invalidCandidateEmbedding
            }
            return (candidate: candidate, score: cosineSimilarity(queryEmbedding, embedding))
        }
        return scored
            .sorted { lhs, rhs in
                if lhs.score != rhs.score { return lhs.score > rhs.score }
                if lhs.candidate.entry.updatedAt != rhs.candidate.entry.updatedAt {
                    return lhs.candidate.entry.updatedAt > rhs.candidate.entry.updatedAt
                }
                return lhs.candidate.entry.id < rhs.candidate.entry.id
            }
            .enumerated()
            .map { offset, result in
                var entry = result.candidate.entry
                entry.search = RuntimeMemoryEntrySearch(
                    rank: offset + 1,
                    snippet: utf8Prefix(entry.content, maximumBytes: 512),
                    matchedFields: ["content"]
                )
                return entry
            }
    }

    private static func canonicalSource(_ source: RuntimeMemoryEntrySource?) -> String {
        guard let source else { return "" }
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        guard let data = try? encoder.encode(source) else { return "invalid-source" }
        return String(decoding: data, as: UTF8.self)
    }

    private static func timestamp(_ date: Date) -> String {
        String(format: "%.6f", date.timeIntervalSince1970)
    }

    private static func utf8Prefix(_ text: String, maximumBytes: Int) -> String {
        guard text.utf8.count > maximumBytes else { return text }
        var byteCount = 0
        var end = text.startIndex
        while end < text.endIndex {
            let next = text.index(after: end)
            let characterBytes = text[end..<next].utf8.count
            guard byteCount + characterBytes <= maximumBytes else { break }
            byteCount += characterBytes
            end = next
        }
        return String(text[..<end])
    }

    private static func cosineSimilarity(_ lhs: [Double], _ rhs: [Double]) -> Double {
        var dotProduct = 0.0
        var lhsMagnitudeSquared = 0.0
        var rhsMagnitudeSquared = 0.0
        for index in lhs.indices {
            dotProduct += lhs[index] * rhs[index]
            lhsMagnitudeSquared += lhs[index] * lhs[index]
            rhsMagnitudeSquared += rhs[index] * rhs[index]
        }
        let denominator = sqrt(lhsMagnitudeSquared) * sqrt(rhsMagnitudeSquared)
        return denominator > 0 ? dotProduct / denominator : -Double.infinity
    }

    private static func fingerprint(fields: [String]) -> String {
        var hasher = SHA256()
        for field in fields {
            let data = Data(field.utf8)
            var length = UInt64(data.count).bigEndian
            withUnsafeBytes(of: &length) { hasher.update(data: Data($0)) }
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}

enum RuntimeSemanticMemorySearchError: Error, Equatable {
    case invalidQueryEmbedding
    case embeddingCountMismatch
    case invalidCandidateEmbedding
}
