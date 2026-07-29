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

struct RuntimeSemanticChatSessionPrimaryRanking: Equatable {
    var orderedIndexes: [Int]
    var scoresByCandidateIndex: [Double]
}

enum RuntimeSemanticChatSessionSearch {
    static let maximumCandidateCount = 200
    static let maximumMessagesPerCandidate = 100
    static let maximumDocumentUTF8Bytes = 8_192
    static let fallbackDocumentUTF8Bytes = 1_024
    static let minimumSecondStageRerankCandidateCount = 8
    static let maximumSecondStageRerankCandidateCount = 32
    static let secondStageRerankLimitMultiplier = 4
    static let secondStagePrimaryAcceptanceWindow = 0.05
    static let secondStagePrimaryAcceptanceTolerance =
        32 * Double.ulpOfOne
    static let documentEncodingVersion = "chat-session-semantic-document-v1"
    static let modelFingerprintVersion = "embedding-model-fingerprint-v3"

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
              let revision = strongPersistentEmbeddingRevision(for: model),
              let embeddingInputProfile = model.embeddingInputProfile else {
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
            adapterContract =
                "ollama-api-embed-truncate-false-role-aware-profile-bound-v3"
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
            embeddingInputProfile.rawValue,
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
        let primaryRanking = try primaryRanking(
            candidates: candidates,
            queryEmbedding: queryEmbedding,
            candidateEmbeddings: candidateEmbeddings
        )
        return try rankedSessions(
            candidates: candidates,
            orderedIndexes: primaryRanking.orderedIndexes,
            limit: limit
        )
    }

    static func primaryOrderedCandidateIndexes(
        candidates: [RuntimeSemanticChatSessionCandidate],
        queryEmbedding: [Double],
        candidateEmbeddings: [[Double]]
    ) throws -> [Int] {
        try primaryRanking(
            candidates: candidates,
            queryEmbedding: queryEmbedding,
            candidateEmbeddings: candidateEmbeddings
        ).orderedIndexes
    }

    static func primaryRanking(
        candidates: [RuntimeSemanticChatSessionCandidate],
        queryEmbedding: [Double],
        candidateEmbeddings: [[Double]]
    ) throws -> RuntimeSemanticChatSessionPrimaryRanking {
        guard queryEmbedding.isValidSemanticEmbedding else {
            throw RuntimeSemanticChatSessionSearchError.invalidQueryEmbedding
        }
        guard candidateEmbeddings.count == candidates.count else {
            throw RuntimeSemanticChatSessionSearchError.embeddingCountMismatch
        }

        var scoresByCandidateIndex = Array(
            repeating: 0.0,
            count: candidateEmbeddings.count
        )
        let scored = try candidateEmbeddings.indices.map { index in
            let embedding = candidateEmbeddings[index]
            guard embedding.count == queryEmbedding.count,
                  embedding.isValidSemanticEmbedding else {
                throw RuntimeSemanticChatSessionSearchError.invalidCandidateEmbedding
            }
            let score = cosineSimilarity(queryEmbedding, embedding)
            guard score.isFinite else {
                throw RuntimeSemanticChatSessionSearchError
                    .invalidCandidateEmbedding
            }
            scoresByCandidateIndex[index] = score
            return (index: index, score: score)
        }

        let orderedIndexes = scored
            .sorted { lhs, rhs in
                if lhs.score != rhs.score {
                    return lhs.score > rhs.score
                }
                let lhsSession = candidates[lhs.index].session
                let rhsSession = candidates[rhs.index].session
                if lhsSession.lastActivityAt != rhsSession.lastActivityAt {
                    return lhsSession.lastActivityAt >
                        rhsSession.lastActivityAt
                }
                return lhsSession.sessionID < rhsSession.sessionID
            }
            .map(\.index)
        return RuntimeSemanticChatSessionPrimaryRanking(
            orderedIndexes: orderedIndexes,
            scoresByCandidateIndex: scoresByCandidateIndex
        )
    }

    static func secondStageRerankCandidateIndexes(
        primaryOrderedIndexes: [Int],
        limit: Int,
        excludedIndexes: Set<Int> = []
    ) -> [Int] {
        let eligibleIndexes = primaryOrderedIndexes.filter {
            !excludedIndexes.contains($0)
        }
        guard limit > 0, !eligibleIndexes.isEmpty else { return [] }
        let boundedLimit = min(
            limit,
            maximumSecondStageRerankCandidateCount
        )
        let scaledLimit = min(
            maximumSecondStageRerankCandidateCount,
            boundedLimit * secondStageRerankLimitMultiplier
        )
        let poolCount = min(
            eligibleIndexes.count,
            max(minimumSecondStageRerankCandidateCount, scaledLimit)
        )
        return Array(eligibleIndexes.prefix(poolCount))
    }

    static func applyingSecondStageRerank(
        primaryOrderedIndexes: [Int],
        primaryScoresByCandidateIndex: [Double],
        rerankCandidateIndexes: [Int],
        queryEmbedding: [Double],
        candidateEmbeddings: [[Double]]
    ) throws -> [Int] {
        guard queryEmbedding.isValidSemanticEmbedding else {
            throw RuntimeSemanticChatSessionSearchError
                .invalidRerankQueryEmbedding
        }
        let primaryIndexSet = Set(primaryOrderedIndexes)
        let rerankIndexSet = Set(rerankCandidateIndexes)
        guard
            candidateEmbeddings.count == rerankCandidateIndexes.count,
            primaryScoresByCandidateIndex.count ==
                primaryOrderedIndexes.count,
            primaryIndexSet.count == primaryOrderedIndexes.count,
            rerankIndexSet.count ==
                rerankCandidateIndexes.count,
            rerankIndexSet.isSubset(of: primaryIndexSet),
            primaryOrderedIndexes.allSatisfy({
                primaryScoresByCandidateIndex.indices.contains($0) &&
                    primaryScoresByCandidateIndex[$0].isFinite
            }),
            rerankCandidateIndexes ==
                primaryOrderedIndexes.filter({
                    rerankIndexSet.contains($0)
                })
        else {
            throw RuntimeSemanticChatSessionSearchError
                .invalidRerankCandidateSet
        }
        let primaryPositions = Dictionary(
            uniqueKeysWithValues: primaryOrderedIndexes.enumerated().map {
                ($0.element, $0.offset)
            }
        )
        let scored = try rerankCandidateIndexes.enumerated().map {
            offset,
            candidateIndex in
            let embedding = candidateEmbeddings[offset]
            guard
                embedding.count == queryEmbedding.count,
                embedding.isValidSemanticEmbedding,
                primaryPositions[candidateIndex] != nil
            else {
                throw RuntimeSemanticChatSessionSearchError
                    .invalidRerankCandidateEmbedding
            }
            let score = cosineSimilarity(queryEmbedding, embedding)
            guard score.isFinite else {
                throw RuntimeSemanticChatSessionSearchError
                    .invalidRerankCandidateEmbedding
            }
            return (
                index: candidateIndex,
                score: score
            )
        }

        var reranked: [Int] = []
        var groupStart = 0
        while groupStart < scored.count {
            let anchorIndex = scored[groupStart].index
            let anchorPrimaryScore =
                primaryScoresByCandidateIndex[anchorIndex]
            var groupEnd = groupStart + 1
            while groupEnd < scored.count {
                let candidatePrimaryScore =
                    primaryScoresByCandidateIndex[
                        scored[groupEnd].index
                    ]
                guard
                    anchorPrimaryScore - candidatePrimaryScore <=
                        secondStagePrimaryAcceptanceWindow +
                            secondStagePrimaryAcceptanceTolerance
                else {
                    break
                }
                groupEnd += 1
            }
            reranked.append(contentsOf: scored[groupStart..<groupEnd]
                .sorted { lhs, rhs in
                    if lhs.score != rhs.score {
                        return lhs.score > rhs.score
                    }
                    return primaryPositions[
                        lhs.index,
                        default: .max
                    ] < primaryPositions[
                        rhs.index,
                        default: .max
                    ]
                }
                .map(\.index))
            groupStart = groupEnd
        }
        let rerankedSet = Set(reranked)
        return reranked + primaryOrderedIndexes.filter {
            !rerankedSet.contains($0)
        }
    }

    static func rankedSessions(
        candidates: [RuntimeSemanticChatSessionCandidate],
        orderedIndexes: [Int],
        limit: Int
    ) throws -> [RuntimeChatStoredSession] {
        guard
            orderedIndexes.count == candidates.count,
            Set(orderedIndexes) == Set(candidates.indices)
        else {
            throw RuntimeSemanticChatSessionSearchError
                .invalidRankingOrder
        }
        return orderedIndexes
            .prefix(max(0, limit))
            .enumerated()
            .map { offset, candidateIndex in
                let candidate = candidates[candidateIndex]
                var session = candidate.session
                session.search = RuntimeChatStoredSessionSearch(
                    rank: offset + 1,
                    snippet: candidate.snippet,
                    matchedFields: candidate.matchedFields
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
        let lhsScale = lhs.reduce(0.0) {
            max($0, abs($1))
        }
        let rhsScale = rhs.reduce(0.0) {
            max($0, abs($1))
        }
        guard lhsScale.isFinite, lhsScale > 0,
              rhsScale.isFinite, rhsScale > 0 else {
            return .nan
        }
        var dotProduct = 0.0
        var lhsMagnitudeSquared = 0.0
        var rhsMagnitudeSquared = 0.0
        for index in lhs.indices {
            let scaledLHS = lhs[index] / lhsScale
            let scaledRHS = rhs[index] / rhsScale
            dotProduct += scaledLHS * scaledRHS
            lhsMagnitudeSquared += scaledLHS * scaledLHS
            rhsMagnitudeSquared += scaledRHS * scaledRHS
        }
        let denominator = sqrt(lhsMagnitudeSquared) * sqrt(rhsMagnitudeSquared)
        guard denominator.isFinite, denominator > 0 else {
            return .nan
        }
        let similarity = dotProduct / denominator
        guard similarity.isFinite else {
            return .nan
        }
        return min(1, max(-1, similarity))
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
    case invalidRerankQueryEmbedding
    case invalidRerankCandidateSet
    case invalidRerankCandidateEmbedding
    case invalidRankingOrder
}

extension Array where Element == Double {
    var isValidSemanticEmbedding: Bool {
        !isEmpty && allSatisfy(\.isFinite) && contains(where: { $0 != 0 })
    }
}
