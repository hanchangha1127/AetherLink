import XCTest
@testable import CompanionCore

final class RuntimeSemanticMemorySearchTests: XCTestCase {
    func testCandidateEmbedsApprovedContentOnlyAndExcludesSourceAuditText() throws {
        let entry = RuntimeMemoryEntry(
            id: "memory-1",
            content: "Use the latest QR when relay recovery is required.",
            createdAt: Date(timeIntervalSince1970: 1_700_000_000),
            updatedAt: Date(timeIntervalSince1970: 1_700_000_100),
            source: source(title: "Private source title", excerpt: "Unapproved source excerpt")
        )
        let source = RuntimeMemorySemanticSearchSource(
            entry: entry,
            sourceRevision: RuntimeSemanticMemorySearch.sourceRevision(for: entry)
        )

        let candidate = try XCTUnwrap(RuntimeSemanticMemorySearch.candidate(source: source))

        XCTAssertEqual(candidate.document, entry.content)
        XCTAssertFalse(candidate.document.contains("Private source title"))
        XCTAssertFalse(candidate.document.contains("Unapproved source excerpt"))
    }

    func testSourceRevisionChangesForContentEnabledAndAuditSourceMutations() throws {
        let base = RuntimeMemoryEntry(
            id: "memory-1",
            content: "Prefers concise answers.",
            createdAt: Date(timeIntervalSince1970: 1_700_000_000),
            updatedAt: Date(timeIntervalSince1970: 1_700_000_100),
            source: source(title: "Session A", excerpt: "Source A")
        )
        var changedContent = base
        changedContent.content = "Prefers detailed answers."
        var changedEnabled = base
        changedEnabled.enabled = false
        var changedSource = base
        changedSource.source = source(title: "Session B", excerpt: "Source B")

        let revision = RuntimeSemanticMemorySearch.sourceRevision(for: base)
        XCTAssertNotEqual(revision, RuntimeSemanticMemorySearch.sourceRevision(for: changedContent))
        XCTAssertNotEqual(revision, RuntimeSemanticMemorySearch.sourceRevision(for: changedEnabled))
        XCTAssertNotEqual(revision, RuntimeSemanticMemorySearch.sourceRevision(for: changedSource))
    }

    func testRanksByCosineSimilarityWithoutChangingEntryMetadata() throws {
        let first = entry(id: "first", content: "relay recovery", updatedAt: 20)
        let second = entry(id: "second", content: "concise answers", updatedAt: 10)
        let candidates = [first, second].compactMap { entry in
            RuntimeSemanticMemorySearch.candidate(source: RuntimeMemorySemanticSearchSource(
                entry: entry,
                sourceRevision: RuntimeSemanticMemorySearch.sourceRevision(for: entry)
            ))
        }

        let ranked = try RuntimeSemanticMemorySearch.rankedEntries(
            candidates: candidates,
            queryEmbedding: [1, 0],
            candidateEmbeddings: [[0, 1], [1, 0]]
        )

        XCTAssertEqual(ranked.map(\.id), ["second", "first"])
        XCTAssertEqual(ranked.map(\.search?.rank), [1, 2])
        XCTAssertEqual(ranked.first?.search?.matchedFields, ["content"])
        XCTAssertEqual(ranked.first?.source, second.source)
    }

    func testDocumentFingerprintChangesWithByteBudget() throws {
        let entry = entry(id: "memory", content: String(repeating: "가", count: 200), updatedAt: 1)
        let source = RuntimeMemorySemanticSearchSource(
            entry: entry,
            sourceRevision: RuntimeSemanticMemorySearch.sourceRevision(for: entry)
        )
        let short = try XCTUnwrap(RuntimeSemanticMemorySearch.candidate(
            source: source,
            maximumDocumentUTF8Bytes: 30
        ))
        let long = try XCTUnwrap(RuntimeSemanticMemorySearch.candidate(
            source: source,
            maximumDocumentUTF8Bytes: 60
        ))

        XCTAssertLessThanOrEqual(short.document.utf8.count, 30)
        XCTAssertLessThanOrEqual(long.document.utf8.count, 60)
        XCTAssertNotEqual(short.documentFingerprint, long.documentFingerprint)
    }

    private func entry(id: String, content: String, updatedAt: TimeInterval) -> RuntimeMemoryEntry {
        RuntimeMemoryEntry(
            id: id,
            content: content,
            createdAt: Date(timeIntervalSince1970: 1),
            updatedAt: Date(timeIntervalSince1970: updatedAt)
        )
    }

    private func source(title: String, excerpt: String) -> RuntimeMemoryEntrySource {
        RuntimeMemoryEntrySource(
            kind: "long_inactivity_summary_draft",
            draftID: "draft-1",
            summaryMethod: "deterministic_preview",
            session: RuntimeMemoryEntrySourceSession(
                sessionID: "session-1",
                title: title,
                model: "ollama:test",
                lastActivityAt: Date(timeIntervalSince1970: 1_700_000_000),
                messageCount: 2,
                inactiveSeconds: 3_600
            ),
            sourceMessageCount: 2,
            sourceRange: "messages 1-2",
            sourcePointers: [RuntimeMemoryEntrySourcePointer(
                sessionID: "session-1",
                messageIndex: 0,
                role: "user",
                createdAt: Date(timeIntervalSince1970: 1_700_000_000),
                excerpt: excerpt
            )]
        )
    }
}
