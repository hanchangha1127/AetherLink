@testable import CompanionCore
import Foundation
import XCTest

final class RuntimeMemorySemanticDuplicateSuggestionsTests: XCTestCase {
    func testThresholdBoundariesTiesAndDeterministicPairOrder() throws {
        let candidates = makeCandidates([
            ("c", "content-c"),
            ("a", "content-a"),
            ("b", "content-b")
        ])
        let result = try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            candidates: candidates,
            embeddings: [[0.8, 0.6], [1, 0], [0.8, 0.6]],
            similarityThresholdBasisPoints: 8_000
        )

        XCTAssertEqual(result.pairs, [
            pair("b", "c", 10_000),
            pair("a", "b", 8_000),
            pair("a", "c", 8_000)
        ])
        XCTAssertFalse(result.truncated)

        let strict = try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            candidates: candidates,
            embeddings: [[0.8, 0.6], [1, 0], [0.8, 0.6]],
            similarityThresholdBasisPoints: 8_001
        )
        XCTAssertEqual(strict.pairs, [pair("b", "c", 10_000)])
    }

    func testPairsAreNonTransitiveAndIDsMayAppearInMultiplePairs() throws {
        let result = try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            candidates: makeCandidates([
                ("a", "a-content"),
                ("b", "b-content"),
                ("c", "c-content")
            ]),
            embeddings: [
                [1, 0],
                [cos(.pi / 6), sin(.pi / 6)],
                [cos(.pi / 3), sin(.pi / 3)]
            ],
            similarityThresholdBasisPoints: 8_500
        )

        XCTAssertEqual(result.pairs, [
            pair("a", "b", 8_660),
            pair("b", "c", 8_660)
        ])
        XCTAssertEqual(result.pairs.filter { $0.firstEntryID == "b" || $0.secondEntryID == "b" }.count, 2)
    }

    func testByteExactStoredContentIsExcludedWithoutTrimBasedExclusion() throws {
        let result = try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            candidates: makeCandidates([
                ("a", "same"),
                ("b", "same"),
                ("c", " same ")
            ]),
            embeddings: [[1, 0], [1, 0], [1, 0]],
            similarityThresholdBasisPoints: 10_000
        )

        XCTAssertEqual(result.pairs, [
            pair("a", "c", 10_000),
            pair("b", "c", 10_000)
        ])
    }

    func testSelectionOmitsWholeLongDocumentsAndMarksSourceCap() throws {
        var sources = (0...200).map { index in
            source(id: String(format: "id-%03d", index), content: " v ")
        }
        sources[1] = source(id: "id-001", content: "  123456  ")
        sources[2] = source(id: "id-002", content: " \n ")

        let selection = try RuntimeMemorySemanticDuplicateSuggester.selectCandidates(
            from: sources,
            modelDocumentUTF8ByteLimit: 5
        )

        XCTAssertEqual(selection.candidates.count, 198)
        XCTAssertEqual(selection.candidates[0].entry.id, "id-000")
        XCTAssertEqual(selection.candidates[0].document, "v")
        XCTAssertEqual(selection.omittedEntryCount, 2)
        XCTAssertTrue(selection.sourceTruncated)
        XCTAssertFalse(selection.candidates.contains { $0.entry.id == "id-001" })
        XCTAssertFalse(selection.candidates.contains { $0.entry.id == "id-200" })
    }

    func testSelectionCapsAggregateCandidateContentWithoutPrefixing() throws {
        XCTAssertEqual(
            RuntimeMemorySemanticDuplicateSuggester.maximumSourceEventLogByteCount,
            8 * 1_024 * 1_024
        )
        let halfPlusOne = String(
            repeating: "x",
            count: RuntimeMemorySemanticDuplicateSuggester
                .maximumCandidateContentUTF8ByteCount / 2 + 1
        )
        let selection = try RuntimeMemorySemanticDuplicateSuggester.selectCandidates(
            from: [
                source(id: "a", content: halfPlusOne),
                source(id: "b", content: halfPlusOne)
            ],
            modelDocumentUTF8ByteLimit: halfPlusOne.utf8.count
        )

        XCTAssertEqual(selection.candidates.map { $0.entry.id }, ["a"])
        XCTAssertEqual(selection.candidates[0].document, halfPlusOne)
        XCTAssertEqual(selection.omittedEntryCount, 1)
        XCTAssertTrue(selection.sourceTruncated)
    }

    func testSelectionUsesFullTrimmedContentAndDoesNotMutateEntries() throws {
        var original = entry(id: "entry", content: " \n full text \t")
        original.search = RuntimeMemoryEntrySearch(rank: 7, snippet: "keep", matchedFields: ["content"])
        let selection = try RuntimeMemorySemanticDuplicateSuggester.selectCandidates(
            from: [RuntimeMemorySemanticSearchSource(entry: original, sourceRevision: "revision")],
            modelDocumentUTF8ByteLimit: 9
        )

        XCTAssertEqual(selection.candidates.map(\.document), ["full text"])
        XCTAssertEqual(selection.candidates[0].entry, original)
        XCTAssertEqual(original.content, " \n full text \t")
        XCTAssertEqual(original.search?.rank, 7)
        XCTAssertEqual(selection.omittedEntryCount, 0)
        XCTAssertFalse(selection.sourceTruncated)

        let result = try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            from: selection,
            embeddings: [[1]],
            similarityThresholdBasisPoints: 8_000
        )
        XCTAssertEqual(result.pairs, [])
        XCTAssertEqual(selection.candidates[0].entry, original)
    }

    func testInvalidThresholdCountsVectorsDimensionsAndDuplicateIDsAreRejected() throws {
        let candidates = makeCandidates([("a", "a"), ("b", "b")])

        XCTAssertThrowsError(try suggestions(candidates, [[1], [1]], threshold: 7_999)) {
            XCTAssertEqual($0 as? RuntimeMemorySemanticDuplicateSuggestionsError, .invalidSimilarityThreshold)
        }
        XCTAssertThrowsError(try suggestions(candidates, [[1], [1]], threshold: 10_001)) {
            XCTAssertEqual($0 as? RuntimeMemorySemanticDuplicateSuggestionsError, .invalidSimilarityThreshold)
        }
        XCTAssertThrowsError(try suggestions(candidates, [[1]], threshold: 8_000)) {
            XCTAssertEqual($0 as? RuntimeMemorySemanticDuplicateSuggestionsError, .embeddingCountMismatch)
        }
        XCTAssertThrowsError(try suggestions(candidates, [[1], [1, 0]], threshold: 8_000)) {
            XCTAssertEqual($0 as? RuntimeMemorySemanticDuplicateSuggestionsError, .invalidEmbeddingDimension)
        }
        for invalid in [Double.nan, Double.infinity, -Double.infinity] {
            XCTAssertThrowsError(try suggestions(candidates, [[1], [invalid]], threshold: 8_000)) {
                XCTAssertEqual($0 as? RuntimeMemorySemanticDuplicateSuggestionsError, .invalidEmbedding)
            }
        }
        XCTAssertThrowsError(try suggestions(candidates, [[1], [0]], threshold: 8_000)) {
            XCTAssertEqual($0 as? RuntimeMemorySemanticDuplicateSuggestionsError, .invalidEmbedding)
        }
        XCTAssertThrowsError(try suggestions(makeCandidates([("a", "one"), ("a", "two")]), [[1], [1]], threshold: 8_000)) {
            XCTAssertEqual($0 as? RuntimeMemorySemanticDuplicateSuggestionsError, .duplicateCandidateID("a"))
        }
        let tooManyCandidates = makeCandidates((0...RuntimeMemorySemanticDuplicateSuggester.candidateLimit).map {
            ("id-\($0)", "content-\($0)")
        })
        XCTAssertThrowsError(try suggestions(
            tooManyCandidates,
            Array(repeating: [1], count: tooManyCandidates.count),
            threshold: 8_000
        )) {
            XCTAssertEqual($0 as? RuntimeMemorySemanticDuplicateSuggestionsError, .candidateLimitExceeded)
        }
        XCTAssertThrowsError(try RuntimeMemorySemanticDuplicateSuggester.selectCandidates(
            from: [],
            modelDocumentUTF8ByteLimit: 0
        )) {
            XCTAssertEqual($0 as? RuntimeMemorySemanticDuplicateSuggestionsError, .invalidDocumentByteLimit)
        }
    }

    func testEmbeddingDimensionAbovePersistentCacheLimitIsRejected() throws {
        let candidates = makeCandidates([("a", "a"), ("b", "b")])
        let maximum = Array(
            repeating: 1.0,
            count: RuntimeMemorySemanticDuplicateSuggester.maximumEmbeddingDimension
        )
        let oversized = Array(
            repeating: 1.0,
            count: RuntimeMemorySemanticDuplicateSuggester.maximumEmbeddingDimension + 1
        )

        let boundaryResult = try suggestions(
            candidates,
            [maximum, maximum],
            threshold: 10_000
        )
        XCTAssertEqual(boundaryResult.pairs.count, 1)
        XCTAssertEqual(boundaryResult.pairs.first?.similarityBasisPoints, 10_000)

        XCTAssertThrowsError(try suggestions(
            candidates,
            [oversized, oversized],
            threshold: 8_000
        )) {
            XCTAssertEqual(
                $0 as? RuntimeMemorySemanticDuplicateSuggestionsError,
                .embeddingDimensionLimitExceeded
            )
        }
    }

    func testCancelledScoringFailsWithCancellationError() throws {
        let candidates = makeCandidates([("a", "a"), ("b", "b")])
        let maximum = Array(
            repeating: 1.0,
            count: RuntimeMemorySemanticDuplicateSuggester.maximumEmbeddingDimension
        )
        var cancellationChecks = 0

        XCTAssertThrowsError(try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            candidates: candidates,
            embeddings: [maximum, maximum],
            similarityThresholdBasisPoints: 8_000,
            cancellationCheck: {
                cancellationChecks += 1
                if cancellationChecks == 8 {
                    throw CancellationError()
                }
            }
        )) { error in
            XCTAssertTrue(error is CancellationError, "Expected CancellationError, received \(error)")
        }
        XCTAssertEqual(cancellationChecks, 8)
    }

    func testPairLimitKeepsBestHundredAndSetsResultTruncation() throws {
        let candidates = makeCandidates((0..<15).map {
            (String(format: "id-%02d", $0), "content-\($0)")
        })
        let result = try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            candidates: candidates,
            embeddings: Array(repeating: [1, 0], count: candidates.count),
            similarityThresholdBasisPoints: 10_000
        )

        XCTAssertEqual(result.pairs.count, 100)
        XCTAssertTrue(result.truncated)
        XCTAssertEqual(result.pairs.first, pair("id-00", "id-01", 10_000))
        XCTAssertEqual(result.pairs.last, pair("id-11", "id-12", 10_000))
    }

    func testUnsignedUTF8OrderingAcrossUnicodePlanes() throws {
        let privateUseID = "entry-\u{E000}"
        let astralID = "entry-\u{1F600}"
        let result = try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            candidates: makeCandidates([
                (astralID, "astral"),
                (privateUseID, "private")
            ]),
            embeddings: [[1], [1]],
            similarityThresholdBasisPoints: 10_000
        )

        XCTAssertEqual(result.pairs, [pair(privateUseID, astralID, 10_000)])
    }

    func testResponseAggregateEntryIDByteCapFailsClosed() {
        let suffix = String(
            repeating: "x",
            count: RuntimeMemorySemanticDuplicateSuggester.maximumResponseEntryIDUTF8ByteCount / 2
        )
        XCTAssertThrowsError(try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            candidates: makeCandidates([("a\(suffix)", "a"), ("b\(suffix)", "b")]),
            embeddings: [[1], [1]],
            similarityThresholdBasisPoints: 10_000
        )) {
            XCTAssertEqual(
                $0 as? RuntimeMemorySemanticDuplicateSuggestionsError,
                .responseEntryIDUTF8ByteLimitExceeded
            )
        }
    }

    func testCompleteLinkClustersDoNotBridgeAChainAndUseCanonicalTieBreak() throws {
        let values = [
            ("c", "content-c"),
            ("b", "content-b"),
            ("a", "content-a")
        ]
        let vectorsByID: [String: [Double]] = [
            "a": [1, 0],
            "b": [cos(.pi / 6), sin(.pi / 6)],
            "c": [cos(.pi / 3), sin(.pi / 3)]
        ]
        let candidates = makeCandidates(values)
        let result = try RuntimeMemorySemanticDuplicateSuggester.clusters(
            candidates: candidates,
            embeddings: values.map { vectorsByID[$0.0]! },
            similarityThresholdBasisPoints: 8_500
        )

        XCTAssertEqual(result.clusters, [cluster(["a", "b"], 8_660)])
        XCTAssertEqual(result.scannedCount, 3)
        XCTAssertEqual(Set(result.clusters.flatMap(\.entryIDs)).count, 2)

        let reorderedValues = values.reversed()
        let reordered = try RuntimeMemorySemanticDuplicateSuggester.clusters(
            candidates: makeCandidates(Array(reorderedValues)),
            embeddings: reorderedValues.map { vectorsByID[$0.0]! },
            similarityThresholdBasisPoints: 8_500
        )
        XCTAssertEqual(reordered, result)
    }

    func testCompleteLinkClusterMinimumAndOutputOrderingAreDeterministic() throws {
        let result = try RuntimeMemorySemanticDuplicateSuggester.clusters(
            candidates: makeCandidates([
                ("z", "z"),
                ("y", "y"),
                ("c", "c"),
                ("b", "b"),
                ("a", "a")
            ]),
            embeddings: [
                [0, 1],
                [0, 1],
                [0.8, 0.6],
                [0.8, 0.6],
                [1, 0]
            ],
            similarityThresholdBasisPoints: 8_000
        )

        XCTAssertEqual(result.clusters, [
            cluster(["y", "z"], 10_000),
            cluster(["a", "b", "c"], 8_000)
        ])
    }

    func testCompleteLinkExactContentPairIsIneligibleAndSingletonsAreOmitted() throws {
        let result = try RuntimeMemorySemanticDuplicateSuggester.clusters(
            candidates: makeCandidates([
                ("b", "same"),
                ("c", "different"),
                ("a", "same")
            ]),
            embeddings: [[1], [1], [1]],
            similarityThresholdBasisPoints: 10_000,
            omittedEntryCount: 4,
            sourceTruncated: true
        )

        XCTAssertEqual(result.clusters, [cluster(["a", "c"], 10_000)])
        XCTAssertEqual(result.omittedEntryCount, 4)
        XCTAssertTrue(result.sourceTruncated)
    }

    func testCompleteLinkClusterCancellationAndResponseByteCapFailClosed() throws {
        var checks = 0
        XCTAssertThrowsError(try RuntimeMemorySemanticDuplicateSuggester.clusters(
            candidates: makeCandidates([("a", "a"), ("b", "b"), ("c", "c")]),
            embeddings: [[1], [1], [1]],
            similarityThresholdBasisPoints: 10_000,
            cancellationCheck: {
                checks += 1
                if checks == 7 { throw CancellationError() }
            }
        )) { XCTAssertTrue($0 is CancellationError) }
        XCTAssertEqual(checks, 7)

        let suffix = String(
            repeating: "x",
            count: RuntimeMemorySemanticDuplicateSuggester.maximumResponseEntryIDUTF8ByteCount / 2
        )
        XCTAssertThrowsError(try RuntimeMemorySemanticDuplicateSuggester.clusters(
            candidates: makeCandidates([("a\(suffix)", "a"), ("b\(suffix)", "b")]),
            embeddings: [[1], [1]],
            similarityThresholdBasisPoints: 10_000
        )) {
            XCTAssertEqual(
                $0 as? RuntimeMemorySemanticDuplicateSuggestionsError,
                .responseEntryIDUTF8ByteLimitExceeded
            )
        }
    }

    private func suggestions(
        _ candidates: [RuntimeSemanticMemoryCandidate],
        _ embeddings: [[Double]],
        threshold: Int
    ) throws -> RuntimeMemorySemanticDuplicateSuggestionsResult {
        try RuntimeMemorySemanticDuplicateSuggester.suggestions(
            candidates: candidates,
            embeddings: embeddings,
            similarityThresholdBasisPoints: threshold
        )
    }

    private func makeCandidates(_ values: [(String, String)]) -> [RuntimeSemanticMemoryCandidate] {
        values.map { id, content in
            RuntimeSemanticMemoryCandidate(
                entry: entry(id: id, content: content),
                sourceRevision: "revision-\(id)",
                document: content.trimmingCharacters(in: .whitespacesAndNewlines),
                documentFingerprint: "fingerprint-\(id)"
            )
        }
    }

    private func source(id: String, content: String) -> RuntimeMemorySemanticSearchSource {
        RuntimeMemorySemanticSearchSource(
            entry: entry(id: id, content: content),
            sourceRevision: "revision-\(id)"
        )
    }

    private func entry(id: String, content: String) -> RuntimeMemoryEntry {
        RuntimeMemoryEntry(
            id: id,
            content: content,
            createdAt: Date(timeIntervalSince1970: 1),
            updatedAt: Date(timeIntervalSince1970: 2)
        )
    }

    private func pair(
        _ firstEntryID: String,
        _ secondEntryID: String,
        _ score: Int
    ) -> RuntimeMemorySemanticDuplicatePair {
        RuntimeMemorySemanticDuplicatePair(
            firstEntryID: firstEntryID,
            secondEntryID: secondEntryID,
            similarityBasisPoints: score
        )
    }

    private func cluster(
        _ entryIDs: [String],
        _ minimumScore: Int
    ) -> RuntimeMemorySemanticDuplicateCluster {
        RuntimeMemorySemanticDuplicateCluster(
            entryIDs: entryIDs,
            minimumSimilarityBasisPoints: minimumScore
        )
    }
}
