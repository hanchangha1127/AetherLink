import CryptoKit
import Foundation
import OllamaBackend

struct RuntimeSemanticChatSessionCandidate: Sendable {
    var session: RuntimeChatStoredSession
    var sourceRevision: Int64?
    var document: String
    var documentFingerprint: String
    var snippet: String
    var matchedFields: [String]
}

enum RuntimeSemanticChatSessionSearch {
    static let maximumCandidateCount = 200
    static let maximumMessagesPerCandidate = 100
    static let maximumDocumentUTF8Bytes = 8_192
    static let fallbackDocumentUTF8Bytes = 1_024
    static let documentEncodingVersion = "chat-session-semantic-document-v1"
    static let modelFingerprintVersion = "embedding-model-fingerprint-v1"

    static func candidate(
        session: RuntimeChatStoredSession,
        messages: [RuntimeChatStoredMessage],
        query: String,
        maximumDocumentUTF8Bytes: Int = maximumDocumentUTF8Bytes,
        sourceRevision: Int64? = nil
    ) -> RuntimeSemanticChatSessionCandidate? {
        let documentByteLimit = max(1, min(maximumDocumentUTF8Bytes, Self.maximumDocumentUTF8Bytes))
        var fields: [(name: String, text: String)] = []

        func append(_ name: String, _ rawText: String?) {
            guard let rawText else { return }
            let boundedText = utf8Prefix(rawText, maximumBytes: documentByteLimit)
            guard let text = normalizedText(boundedText), !text.isEmpty else { return }
            fields.append((name, text))
        }

        append("title", session.title)
        for message in messages.reversed() {
            append("transcript", message.content)
            append("reasoning", message.reasoning)
            for attachment in message.attachments {
                append("attachment", attachment.name)
                append("attachment", attachment.text)
            }
        }

        guard !fields.isEmpty else { return nil }
        let document = utf8Prefix(
            fields.map { "\($0.name): \($0.text)" }.joined(separator: "\n"),
            maximumBytes: documentByteLimit
        )
        guard !document.isEmpty else { return nil }

        let lexicalMatch = RuntimeChatSessionSearchQuery(query).flatMap {
            session.runtimeSearchMatch($0, messages: messages)
        }
        let fallbackSnippet = fields
            .first(where: { $0.name == "transcript" })?
            .text ?? fields[0].text

        return RuntimeSemanticChatSessionCandidate(
            session: session,
            sourceRevision: sourceRevision,
            document: document,
            documentFingerprint: fingerprint(fields: [
                documentEncodingVersion,
                String(documentByteLimit),
                document
            ]),
            snippet: lexicalMatch?.snippet ?? utf8Prefix(fallbackSnippet, maximumBytes: 512),
            matchedFields: lexicalMatch?.matchedFields ?? ["semantic"]
        )
    }

    static func persistentModelFingerprint(
        model: ModelInfo,
        requestedQualifiedModelID: String
    ) -> String? {
        guard model.installed,
              model.source == .local,
              model.kind == .embedding,
              let requested = ModelProvider.splitQualifiedModelID(requestedQualifiedModelID),
              requested.provider == model.provider,
              let revision = strongPersistentEmbeddingRevision(for: model) else {
            return nil
        }
        let canonicalProviderModelID = canonicalModelName(model.providerModelID)
        let canonicalRequestedModelID = canonicalModelName(requested.modelID)
        let capabilities = Array(Set(model.capabilities.map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        }.filter { !$0.isEmpty })).sorted()
        let adapterContract: String
        switch model.provider {
        case .ollama:
            adapterContract = "ollama-api-embed-truncate-false-v1"
        case .lmStudio:
            adapterContract = "lmstudio-openai-embeddings-v1"
        case .aggregate:
            return nil
        }
        return fingerprint(fields: [
            modelFingerprintVersion,
            model.provider.rawValue,
            canonicalProviderModelID,
            canonicalRequestedModelID,
            revision,
            model.sizeBytes.map(String.init) ?? "",
            model.modifiedAt.map { String(format: "%.6f", $0.timeIntervalSince1970) } ?? "",
            capabilities.joined(separator: ","),
            model.contextWindowTokens.map(String.init) ?? "",
            adapterContract
        ])
    }

    static func canonicalModelName(_ name: String) -> String {
        name.hasSuffix(":latest") ? String(name.dropLast(":latest".count)) : name
    }

    private static func strongPersistentEmbeddingRevision(for model: ModelInfo) -> String? {
        guard model.provider == .ollama,
              let revision = model.persistentEmbeddingRevision?
                .trimmingCharacters(in: .whitespacesAndNewlines),
              revision.hasPrefix("ollama-sha256:") else {
            return nil
        }
        let digest = revision.dropFirst("ollama-sha256:".count)
        guard digest.count == 64,
              digest.unicodeScalars.allSatisfy({
                  CharacterSet(charactersIn: "0123456789abcdef").contains($0)
              }) else {
            return nil
        }
        return revision
    }

    static func rankedSessions(
        candidates: [RuntimeSemanticChatSessionCandidate],
        queryEmbedding: [Double],
        candidateEmbeddings: [[Double]],
        limit: Int
    ) throws -> [RuntimeChatStoredSession] {
        guard queryEmbedding.isValidSemanticEmbedding else {
            throw RuntimeSemanticChatSessionSearchError.invalidQueryEmbedding
        }
        guard candidateEmbeddings.count == candidates.count else {
            throw RuntimeSemanticChatSessionSearchError.embeddingCountMismatch
        }

        let scored = try zip(candidates, candidateEmbeddings).map { candidate, embedding in
            guard embedding.count == queryEmbedding.count,
                  embedding.isValidSemanticEmbedding else {
                throw RuntimeSemanticChatSessionSearchError.invalidCandidateEmbedding
            }
            return (candidate: candidate, score: cosineSimilarity(queryEmbedding, embedding))
        }

        return scored
            .sorted { lhs, rhs in
                if lhs.score != rhs.score {
                    return lhs.score > rhs.score
                }
                if lhs.candidate.session.lastActivityAt != rhs.candidate.session.lastActivityAt {
                    return lhs.candidate.session.lastActivityAt > rhs.candidate.session.lastActivityAt
                }
                return lhs.candidate.session.sessionID < rhs.candidate.session.sessionID
            }
            .prefix(max(0, limit))
            .enumerated()
            .map { offset, result in
                var session = result.candidate.session
                session.search = RuntimeChatStoredSessionSearch(
                    rank: offset + 1,
                    snippet: result.candidate.snippet,
                    matchedFields: result.candidate.matchedFields
                )
                return session
            }
    }

    private static func normalizedText(_ rawText: String?) -> String? {
        rawText?
            .components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
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

enum RuntimeSemanticChatSessionSearchError: Error, Equatable {
    case invalidQueryEmbedding
    case embeddingCountMismatch
    case invalidCandidateEmbedding
}

extension Array where Element == Double {
    var isValidSemanticEmbedding: Bool {
        !isEmpty && allSatisfy(\.isFinite) && contains(where: { $0 != 0 })
    }
}
