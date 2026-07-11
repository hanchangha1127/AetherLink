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
