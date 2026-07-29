import Foundation
import OllamaBackend
import XCTest
@testable import CompanionCore

final class RuntimeSemanticChatSessionSearchTests: XCTestCase {
    func testSemanticRankingUsesCosineSimilarityAndKeepsExistingResponseShape() throws {
        let older = RuntimeChatStoredSession(
            sessionID: "older",
            title: "Network setup",
            model: "ollama:llama3.1",
            lastActivityAt: Date(timeIntervalSince1970: 100),
            messageCount: 1
        )
        let newer = RuntimeChatStoredSession(
            sessionID: "newer",
            title: "Garden notes",
            model: "ollama:llama3.1",
            lastActivityAt: Date(timeIntervalSince1970: 200),
            messageCount: 1
        )
        let candidates = [
            RuntimeSemanticChatSessionSearch.candidate(
                session: older,
                messages: [.init(role: "assistant", content: "Reconnect through the private relay.")],
                query: "secure tunnel"
            ),
            RuntimeSemanticChatSessionSearch.candidate(
                session: newer,
                messages: [.init(role: "assistant", content: "Water the basil tomorrow.")],
                query: "secure tunnel"
            ),
        ].compactMap { $0 }

        let ranked = try RuntimeSemanticChatSessionSearch.rankedSessions(
            candidates: candidates,
            queryEmbedding: [1, 0],
            candidateEmbeddings: [[0.9, 0.1], [0.1, 0.9]],
            limit: 2
        )

        XCTAssertEqual(ranked.map(\.sessionID), ["older", "newer"])
        XCTAssertEqual(ranked.map(\.search?.rank), [1, 2])
        XCTAssertEqual(ranked.first?.search?.matchedFields, ["semantic"])
        XCTAssertEqual(ranked.first?.search?.snippet, "Reconnect through the private relay.")
    }

    func testSecondStageRerankReordersOnlyTheBoundedPrimaryPool()
        throws
    {
        let candidates = (0..<40).compactMap { index in
            RuntimeSemanticChatSessionSearch.candidate(
                session: RuntimeChatStoredSession(
                    sessionID: String(format: "session-%02d", index),
                    title: "Session \(index)",
                    model: "ollama:chat",
                    lastActivityAt: Date(
                        timeIntervalSince1970: Double(1_000 - index)
                    ),
                    messageCount: 1
                ),
                messages: [
                    .init(
                        role: "assistant",
                        content: "Candidate \(index)"
                    ),
                ],
                query: "semantic query"
            )
        }
        let primaryRanking = try RuntimeSemanticChatSessionSearch
            .primaryRanking(
                candidates: candidates,
                queryEmbedding: [1, 0],
                candidateEmbeddings: Array(
                    repeating: [1, 0],
                    count: candidates.count
                )
            )
        let primaryOrder = primaryRanking.orderedIndexes
        let rerankPool = RuntimeSemanticChatSessionSearch
            .secondStageRerankCandidateIndexes(
                primaryOrderedIndexes: primaryOrder,
                limit: 1
            )

        XCTAssertEqual(primaryOrder, Array(candidates.indices))
        XCTAssertEqual(rerankPool, Array(0..<8))

        let rerankedOrder = try RuntimeSemanticChatSessionSearch
            .applyingSecondStageRerank(
                primaryOrderedIndexes: primaryOrder,
                primaryScoresByCandidateIndex:
                    primaryRanking.scoresByCandidateIndex,
                rerankCandidateIndexes: rerankPool,
                queryEmbedding: [1, 0],
                candidateEmbeddings: rerankPool.map { index in
                    switch index {
                    case 0:
                        return [0, 1]
                    case 1:
                        return [1, 0]
                    default:
                        return [0.5, 0.5]
                    }
                }
            )
        let ranked = try RuntimeSemanticChatSessionSearch.rankedSessions(
            candidates: candidates,
            orderedIndexes: rerankedOrder,
            limit: 3
        )

        XCTAssertEqual(rerankedOrder.first, 1)
        XCTAssertEqual(rerankedOrder[8], 8)
        XCTAssertEqual(
            ranked.map(\.sessionID),
            ["session-01", "session-02", "session-03"]
        )
        XCTAssertEqual(ranked.map(\.search?.rank), [1, 2, 3])
    }

    func testSecondStageRerankPreservesStrongPrimaryWinnerAndSkipsExcludedIndexes()
        throws
    {
        let primaryOrder = Array(0..<40)
        let rerankPool = RuntimeSemanticChatSessionSearch
            .secondStageRerankCandidateIndexes(
                primaryOrderedIndexes: primaryOrder,
                limit: 1,
                excludedIndexes: Set(0..<32)
            )
        XCTAssertEqual(rerankPool, Array(32..<40))

        let reranked = try RuntimeSemanticChatSessionSearch
            .applyingSecondStageRerank(
                primaryOrderedIndexes: [0, 1, 2],
                primaryScoresByCandidateIndex: [1, 0.9, 0.89],
                rerankCandidateIndexes: [0, 1, 2],
                queryEmbedding: [1, 0],
                candidateEmbeddings: [
                    [0, 1],
                    [1, 0],
                    [0.9, 0.1],
                ]
            )

        XCTAssertEqual(reranked, [0, 1, 2])
    }

    func testSecondStageRerankIncludesExactPrimaryAcceptanceBoundary()
        throws
    {
        let reranked = try RuntimeSemanticChatSessionSearch
            .applyingSecondStageRerank(
                primaryOrderedIndexes: [0, 1],
                primaryScoresByCandidateIndex: [1, 0.95],
                rerankCandidateIndexes: [0, 1],
                queryEmbedding: [1, 0],
                candidateEmbeddings: [
                    [0, 1],
                    [1, 0],
                ]
            )

        XCTAssertEqual(reranked, [1, 0])
    }

    func testRankingStaysFiniteForLargestFiniteVectorComponents()
        throws
    {
        let candidates = (0..<2).compactMap { index in
            RuntimeSemanticChatSessionSearch.candidate(
                session: RuntimeChatStoredSession(
                    sessionID: "extreme-\(index)",
                    title: "Extreme \(index)",
                    model: "ollama:chat",
                    lastActivityAt: Date(
                        timeIntervalSince1970: Double(2 - index)
                    ),
                    messageCount: 1
                ),
                messages: [],
                query: "extreme"
            )
        }
        let maximum = Double.greatestFiniteMagnitude
        let primaryRanking = try RuntimeSemanticChatSessionSearch
            .primaryRanking(
                candidates: candidates,
                queryEmbedding: [maximum, maximum],
                candidateEmbeddings: [
                    [maximum, maximum],
                    [maximum, -maximum],
                ]
            )

        XCTAssertEqual(primaryRanking.orderedIndexes, [0, 1])
        XCTAssertTrue(
            primaryRanking.scoresByCandidateIndex
                .allSatisfy(\.isFinite)
        )
        XCTAssertEqual(
            primaryRanking.scoresByCandidateIndex[0],
            1,
            accuracy: 0.000_000_001
        )

        let reranked = try RuntimeSemanticChatSessionSearch
            .applyingSecondStageRerank(
                primaryOrderedIndexes: [0, 1],
                primaryScoresByCandidateIndex: [1, 0.99],
                rerankCandidateIndexes: [0, 1],
                queryEmbedding: [maximum, maximum],
                candidateEmbeddings: [
                    [maximum, -maximum],
                    [maximum, maximum],
                ]
            )
        XCTAssertEqual(reranked, [1, 0])
    }

    func testSecondStageRerankRejectsMalformedShapeAndCandidateSets()
        throws
    {
        XCTAssertThrowsError(
            try RuntimeSemanticChatSessionSearch
                .applyingSecondStageRerank(
                    primaryOrderedIndexes: [0, 1],
                    primaryScoresByCandidateIndex: [1, 0.9],
                    rerankCandidateIndexes: [0, 0],
                    queryEmbedding: [1, 0],
                    candidateEmbeddings: [[1, 0], [1, 0]]
                )
        ) { error in
            XCTAssertEqual(
                error as? RuntimeSemanticChatSessionSearchError,
                .invalidRerankCandidateSet
            )
        }
        XCTAssertThrowsError(
            try RuntimeSemanticChatSessionSearch
                .applyingSecondStageRerank(
                    primaryOrderedIndexes: [0, 1],
                    primaryScoresByCandidateIndex: [1, 0.9],
                    rerankCandidateIndexes: [0],
                    queryEmbedding: [1, 0],
                    candidateEmbeddings: [[1]]
                )
        ) { error in
            XCTAssertEqual(
                error as? RuntimeSemanticChatSessionSearchError,
                .invalidRerankCandidateEmbedding
            )
        }
    }

    func testCandidateBoundsUTF8AndNeverIncludesInlineAttachmentBytes() throws {
        let privateBytes = "private-inline-base64-canary"
        let session = RuntimeChatStoredSession(
            sessionID: "bounded",
            title: "Unicode",
            model: "ollama:llama3.1",
            lastActivityAt: Date(),
            messageCount: 1
        )
        let attachment = ChatAttachment(
            type: "image",
            mimeType: "image/png",
            name: "diagram.png",
            dataBase64: privateBytes,
            text: String(repeating: "가", count: 10_000)
        )

        let candidate = try XCTUnwrap(RuntimeSemanticChatSessionSearch.candidate(
            session: session,
            messages: [.init(role: "user", content: "검토", attachments: [attachment])],
            query: "diagram"
        ))

        XCTAssertLessThanOrEqual(
            candidate.document.utf8.count,
            RuntimeSemanticChatSessionSearch.maximumDocumentUTF8Bytes
        )
        XCTAssertFalse(candidate.document.contains(privateBytes))
        XCTAssertNotNil(candidate.document.data(using: .utf8))
    }

    func testCandidateDocumentPrioritizesNewestMessagesInsideByteBudget() throws {
        let session = RuntimeChatStoredSession(
            sessionID: "recent-first",
            title: "Session",
            model: "ollama:llama3.1",
            lastActivityAt: Date(),
            messageCount: 3
        )
        let messages = [
            RuntimeChatStoredMessage(role: "user", content: "oldest " + String(repeating: "a", count: 200)),
            RuntimeChatStoredMessage(role: "assistant", content: "middle " + String(repeating: "b", count: 200)),
            RuntimeChatStoredMessage(role: "user", content: "newest semantic target")
        ]

        let candidate = try XCTUnwrap(RuntimeSemanticChatSessionSearch.candidate(
            session: session,
            messages: messages,
            query: "related idea",
            maximumDocumentUTF8Bytes: 96
        ))

        XCTAssertTrue(candidate.document.contains("newest semantic target"))
        XCTAssertFalse(candidate.document.contains("oldest"))
        XCTAssertEqual(candidate.snippet, "newest semantic target")
    }

    func testRankingRejectsMalformedEmbeddingShapes() throws {
        let session = RuntimeChatStoredSession(
            sessionID: "session",
            title: "Title",
            model: "ollama:llama3.1",
            lastActivityAt: Date(),
            messageCount: 1
        )
        let candidate = try XCTUnwrap(RuntimeSemanticChatSessionSearch.candidate(
            session: session,
            messages: [],
            query: "query"
        ))

        XCTAssertThrowsError(try RuntimeSemanticChatSessionSearch.rankedSessions(
            candidates: [candidate],
            queryEmbedding: [1, 0],
            candidateEmbeddings: [],
            limit: 1
        )) { error in
            XCTAssertEqual(error as? RuntimeSemanticChatSessionSearchError, .embeddingCountMismatch)
        }
        XCTAssertThrowsError(try RuntimeSemanticChatSessionSearch.rankedSessions(
            candidates: [candidate],
            queryEmbedding: [1, 0],
            candidateEmbeddings: [[1]],
            limit: 1
        )) { error in
            XCTAssertEqual(error as? RuntimeSemanticChatSessionSearchError, .invalidCandidateEmbedding)
        }
    }

    func testCandidateFingerprintChangesWithDocumentOrByteBudget() throws {
        let session = RuntimeChatStoredSession(
            sessionID: "fingerprint",
            title: "Title",
            model: "ollama:chat",
            lastActivityAt: Date(),
            messageCount: 1
        )
        let first = try XCTUnwrap(RuntimeSemanticChatSessionSearch.candidate(
            session: session,
            messages: [.init(role: "user", content: "first document")],
            query: "document",
            maximumDocumentUTF8Bytes: 128
        ))
        let same = try XCTUnwrap(RuntimeSemanticChatSessionSearch.candidate(
            session: session,
            messages: [.init(role: "user", content: "first document")],
            query: "different query does not affect the indexed document",
            maximumDocumentUTF8Bytes: 128
        ))
        let changedText = try XCTUnwrap(RuntimeSemanticChatSessionSearch.candidate(
            session: session,
            messages: [.init(role: "user", content: "second document")],
            query: "document",
            maximumDocumentUTF8Bytes: 128
        ))
        let changedBudget = try XCTUnwrap(RuntimeSemanticChatSessionSearch.candidate(
            session: session,
            messages: [.init(role: "user", content: "first document")],
            query: "document",
            maximumDocumentUTF8Bytes: 64
        ))

        XCTAssertEqual(first.documentFingerprint, same.documentFingerprint)
        XCTAssertNotEqual(first.documentFingerprint, changedText.documentFingerprint)
        XCTAssertNotEqual(first.documentFingerprint, changedBudget.documentFingerprint)
        XCTAssertEqual(first.documentFingerprint.count, 64)
    }

    func testPersistentModelFingerprintRequiresStrongRevisionAndCanonicalizesLatestAlias() throws {
        let base = ModelInfo(
            id: "nomic-embed-text:latest",
            name: "Nomic Embed",
            provider: .ollama,
            kind: .embedding,
            capabilities: ["embedding", "local"],
            providerModelID: "nomic-embed-text:latest",
            sizeBytes: 123,
            modifiedAt: Date(timeIntervalSince1970: 100),
            contextWindowTokens: 2_048,
            persistentEmbeddingRevision: "ollama-sha256:" + String(repeating: "a", count: 64)
        )
        var reordered = base
        reordered.capabilities = ["local", "embedding", "embedding"]
        var changedRevision = base
        changedRevision.persistentEmbeddingRevision = "ollama-sha256:" + String(repeating: "b", count: 64)
        var missingRevision = base
        missingRevision.persistentEmbeddingRevision = nil
        var mutableAliasRevision = base
        mutableAliasRevision.persistentEmbeddingRevision = "latest"
        var nonCanonicalDigestRevision = base
        nonCanonicalDigestRevision.persistentEmbeddingRevision =
            "ollama-sha256:" + String(repeating: "A", count: 64)
        var roleAwareProfile = base
        roleAwareProfile.embeddingInputProfile = .embeddingGemma
        var unknownProfile = base
        unknownProfile.embeddingInputProfile = nil

        let untagged = try XCTUnwrap(RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: base,
            requestedQualifiedModelID: "ollama:nomic-embed-text"
        ))
        let latest = try XCTUnwrap(RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: reordered,
            requestedQualifiedModelID: "ollama:nomic-embed-text:latest"
        ))

        XCTAssertEqual(untagged, latest)
        XCTAssertNotEqual(untagged, RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: changedRevision,
            requestedQualifiedModelID: "ollama:nomic-embed-text"
        ))
        XCTAssertNotEqual(untagged, RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: roleAwareProfile,
            requestedQualifiedModelID: "ollama:nomic-embed-text"
        ))
        XCTAssertNil(RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: unknownProfile,
            requestedQualifiedModelID: "ollama:nomic-embed-text"
        ))
        XCTAssertNil(RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: missingRevision,
            requestedQualifiedModelID: "ollama:nomic-embed-text"
        ))
        XCTAssertNil(RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: mutableAliasRevision,
            requestedQualifiedModelID: "ollama:nomic-embed-text"
        ))
        XCTAssertNil(RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: nonCanonicalDigestRevision,
            requestedQualifiedModelID: "ollama:nomic-embed-text"
        ))
        XCTAssertNil(RuntimeSemanticChatSessionSearch.persistentModelFingerprint(
            model: base,
            requestedQualifiedModelID: "lm_studio:nomic-embed-text"
        ))
    }
}
