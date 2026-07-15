@testable import CompanionCore
import Foundation
import XCTest

final class RuntimeMemorySemanticCalibrationTests: XCTestCase {
    func testSharedCorpusSweepsEveryBasisPointAndMatchesCompleteLinkReviewLabels() throws {
        let fixture = try loadFixture()
        XCTAssertEqual(fixture.schemaVersion, 1)
        XCTAssertEqual(fixture.corpusID, "memory-semantic-duplicate-calibration-v1")
        XCTAssertEqual(Set(fixture.entries.map(\.language)), ["en", "fr", "ja", "ko", "zh-Hans"])

        let result = try evaluate(fixture)

        XCTAssertEqual(result.thresholdMetrics.count, 2_001)
        XCTAssertEqual(result.thresholdMetrics.first?.thresholdBasisPoints, 8_000)
        XCTAssertEqual(result.thresholdMetrics.last?.thresholdBasisPoints, 10_000)
        XCTAssertEqual(result.bestF1ThresholdBasisPoints, 9_511)
        XCTAssertEqual(result.reviewThresholdMetrics, metrics(
            threshold: 9_000,
            truePositive: 7,
            falsePositive: 0,
            trueNegative: 7,
            falseNegative: 0,
            precision: 10_000,
            recall: 10_000,
            f1: 10_000
        ))
        XCTAssertEqual(result.thresholdMetrics[90], metrics(
            threshold: 8_090,
            truePositive: 7,
            falsePositive: 1,
            trueNegative: 6,
            falseNegative: 0,
            precision: 8_750,
            recall: 10_000,
            f1: 9_333
        ))
        XCTAssertEqual(result.thresholdMetrics[1_512], metrics(
            threshold: 9_512,
            truePositive: 5,
            falsePositive: 0,
            trueNegative: 7,
            falseNegative: 2,
            precision: 10_000,
            recall: 7_143,
            f1: 8_333
        ))
        XCTAssertTrue(result.reviewClustersExactMatch)
        XCTAssertEqual(result.expectedReviewClusters, fixture.expectedReviewClusters)
        XCTAssertEqual(result.predictedReviewClusters, [
            cluster(["theme-en", "theme-zh"], 9_900),
            cluster(["source-en", "source-ja"], 9_800),
            cluster(["concise-en", "concise-fr", "concise-ko"], 9_659),
            cluster(["chain-a", "chain-b"], 9_511)
        ])
        XCTAssertEqual(pairScore(result, "chain-a", "chain-b"), 9_511)
        XCTAssertEqual(pairScore(result, "chain-a", "chain-c"), 8_090)
        XCTAssertEqual(pairScore(result, "chain-b", "chain-c"), 9_511)
    }

    func testCalibrationIsDeterministicAcrossCandidateAndLabelOrder() throws {
        let fixture = try loadFixture()
        let baseline = try evaluate(fixture)
        let reversedFixture = CalibrationFixture(
            schemaVersion: fixture.schemaVersion,
            corpusID: fixture.corpusID,
            reviewThresholdBasisPoints: fixture.reviewThresholdBasisPoints,
            entries: fixture.entries.reversed(),
            pairLabels: fixture.pairLabels.reversed(),
            expectedReviewClusters: fixture.expectedReviewClusters
        )

        let reordered = try evaluate(reversedFixture)

        XCTAssertEqual(reordered.pairScores, baseline.pairScores)
        XCTAssertEqual(reordered.thresholdMetrics, baseline.thresholdMetrics)
        XCTAssertEqual(reordered.bestF1ThresholdBasisPoints, baseline.bestF1ThresholdBasisPoints)
        XCTAssertEqual(reordered.reviewThresholdMetrics, baseline.reviewThresholdMetrics)
        XCTAssertEqual(reordered.predictedReviewClusters, baseline.predictedReviewClusters)
        XCTAssertEqual(reordered.expectedReviewClusters, baseline.expectedReviewClusters)
        XCTAssertEqual(reordered.reviewClustersExactMatch, baseline.reviewClustersExactMatch)
    }

    func testCalibrationRejectsMalformedLabelsAndExpectedClusters() throws {
        let fixture = try loadFixture()
        let candidates = makeCandidates(fixture.entries)
        let embeddings = fixture.entries.map(\.offlineEmbedding)
        let validLabels = fixture.pairLabels.map(\.runtimeLabel)

        XCTAssertThrowsError(try RuntimeMemorySemanticCalibrationEvaluator.evaluate(
            candidates: candidates,
            embeddings: embeddings,
            pairLabels: validLabels,
            expectedReviewClusters: fixture.expectedReviewClusters,
            reviewThresholdBasisPoints: 7_999
        )) {
            XCTAssertEqual($0 as? RuntimeMemorySemanticCalibrationError, .invalidReviewThreshold)
        }
        XCTAssertThrowsError(try RuntimeMemorySemanticCalibrationEvaluator.evaluate(
            candidates: candidates,
            embeddings: embeddings,
            pairLabels: [validLabels[0], validLabels[0]],
            expectedReviewClusters: fixture.expectedReviewClusters,
            reviewThresholdBasisPoints: 9_000
        )) {
            XCTAssertEqual(
                $0 as? RuntimeMemorySemanticCalibrationError,
                .duplicatePairLabel("chain-a", "chain-b")
            )
        }
        XCTAssertThrowsError(try RuntimeMemorySemanticCalibrationEvaluator.evaluate(
            candidates: candidates,
            embeddings: embeddings,
            pairLabels: [RuntimeMemorySemanticCalibrationPairLabel(
                firstEntryID: "chain-b",
                secondEntryID: "chain-a",
                isDuplicate: true
            ), validLabels[1]],
            expectedReviewClusters: fixture.expectedReviewClusters,
            reviewThresholdBasisPoints: 9_000
        )) {
            XCTAssertEqual(
                $0 as? RuntimeMemorySemanticCalibrationError,
                .noncanonicalPairLabel("chain-b", "chain-a")
            )
        }
        XCTAssertThrowsError(try RuntimeMemorySemanticCalibrationEvaluator.evaluate(
            candidates: candidates,
            embeddings: embeddings,
            pairLabels: validLabels,
            expectedReviewClusters: [["chain-a", "chain-b"], ["chain-b", "chain-c"]],
            reviewThresholdBasisPoints: 9_000
        )) {
            XCTAssertEqual(
                $0 as? RuntimeMemorySemanticCalibrationError,
                .repeatedExpectedClusterEntryID("chain-b")
            )
        }
        XCTAssertThrowsError(try RuntimeMemorySemanticCalibrationEvaluator.evaluate(
            candidates: candidates,
            embeddings: embeddings,
            pairLabels: validLabels,
            expectedReviewClusters: fixture.expectedReviewClusters.reversed(),
            reviewThresholdBasisPoints: 9_000
        )) {
            XCTAssertEqual(
                $0 as? RuntimeMemorySemanticCalibrationError,
                .noncanonicalExpectedClusterOrder
            )
        }
    }

    func testByteExactContentRemainsIneligibleAndNoPredictionPrecisionIsNull() throws {
        let candidates = makeCandidates([
            CalibrationEntry(id: "a", language: "en", content: "same", offlineEmbedding: [1, 0]),
            CalibrationEntry(id: "b", language: "ko", content: "same", offlineEmbedding: [1, 0]),
            CalibrationEntry(id: "c", language: "fr", content: "different", offlineEmbedding: [0, 1])
        ])
        let result = try RuntimeMemorySemanticCalibrationEvaluator.evaluate(
            candidates: candidates,
            embeddings: [[1, 0], [1, 0], [0, 1]],
            pairLabels: [
                RuntimeMemorySemanticCalibrationPairLabel(
                    firstEntryID: "a",
                    secondEntryID: "b",
                    isDuplicate: true
                ),
                RuntimeMemorySemanticCalibrationPairLabel(
                    firstEntryID: "a",
                    secondEntryID: "c",
                    isDuplicate: false
                )
            ],
            expectedReviewClusters: [],
            reviewThresholdBasisPoints: 9_000
        )

        XCTAssertEqual(result.pairScores.first?.similarityBasisPoints, 10_000)
        XCTAssertEqual(result.pairScores.first?.isSemanticCandidate, false)
        XCTAssertEqual(result.reviewThresholdMetrics.precisionBasisPoints, nil)
        XCTAssertEqual(result.reviewThresholdMetrics.recallBasisPoints, 0)
        XCTAssertEqual(result.reviewThresholdMetrics.f1BasisPoints, 0)
        XCTAssertTrue(result.predictedReviewClusters.isEmpty)
        XCTAssertTrue(result.reviewClustersExactMatch)
    }

    func testCalibrationSweepHonorsCancellation() throws {
        let fixture = try loadFixture()
        var checks = 0

        XCTAssertThrowsError(try RuntimeMemorySemanticCalibrationEvaluator.evaluate(
            candidates: makeCandidates(fixture.entries),
            embeddings: fixture.entries.map(\.offlineEmbedding),
            pairLabels: fixture.pairLabels.map(\.runtimeLabel),
            expectedReviewClusters: fixture.expectedReviewClusters,
            reviewThresholdBasisPoints: fixture.reviewThresholdBasisPoints,
            cancellationCheck: {
                checks += 1
                if checks == 80 { throw CancellationError() }
            }
        )) { error in
            XCTAssertTrue(error is CancellationError)
        }
        XCTAssertEqual(checks, 80)
    }

    private func evaluate(
        _ fixture: CalibrationFixture
    ) throws -> RuntimeMemorySemanticCalibrationResult {
        try RuntimeMemorySemanticCalibrationEvaluator.evaluate(
            candidates: makeCandidates(fixture.entries),
            embeddings: fixture.entries.map(\.offlineEmbedding),
            pairLabels: fixture.pairLabels.map(\.runtimeLabel),
            expectedReviewClusters: fixture.expectedReviewClusters,
            reviewThresholdBasisPoints: fixture.reviewThresholdBasisPoints
        )
    }

    private func makeCandidates(
        _ entries: [CalibrationEntry]
    ) -> [RuntimeSemanticMemoryCandidate] {
        entries.map { value in
            let entry = RuntimeMemoryEntry(
                id: value.id,
                content: value.content,
                createdAt: Date(timeIntervalSince1970: 1),
                updatedAt: Date(timeIntervalSince1970: 2)
            )
            return RuntimeSemanticMemoryCandidate(
                entry: entry,
                sourceRevision: "calibration-v1-\(value.id)",
                document: value.content,
                documentFingerprint: "calibration-fingerprint-v1-\(value.id)"
            )
        }
    }

    private func metrics(
        threshold: Int,
        truePositive: Int,
        falsePositive: Int,
        trueNegative: Int,
        falseNegative: Int,
        precision: Int?,
        recall: Int,
        f1: Int
    ) -> RuntimeMemorySemanticCalibrationThresholdMetrics {
        RuntimeMemorySemanticCalibrationThresholdMetrics(
            thresholdBasisPoints: threshold,
            truePositiveCount: truePositive,
            falsePositiveCount: falsePositive,
            trueNegativeCount: trueNegative,
            falseNegativeCount: falseNegative,
            precisionBasisPoints: precision,
            recallBasisPoints: recall,
            f1BasisPoints: f1
        )
    }

    private func pairScore(
        _ result: RuntimeMemorySemanticCalibrationResult,
        _ firstEntryID: String,
        _ secondEntryID: String
    ) -> Int? {
        result.pairScores.first {
            $0.firstEntryID == firstEntryID && $0.secondEntryID == secondEntryID
        }?.similarityBasisPoints
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

    private func loadFixture() throws -> CalibrationFixture {
        let relative = "shared/evaluation/memory-semantic-duplicate-calibration-v1.json"
        let starts = [
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true),
            URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        ]
        for start in starts {
            var directory = start.standardizedFileURL
            while true {
                let candidate = directory.appendingPathComponent(relative)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    return try JSONDecoder().decode(
                        CalibrationFixture.self,
                        from: Data(contentsOf: candidate)
                    )
                }
                let parent = directory.deletingLastPathComponent()
                if parent.path == directory.path { break }
                directory = parent
            }
        }
        throw CalibrationFixtureError.notFound
    }
}

private enum CalibrationFixtureError: Error {
    case notFound
}

private struct CalibrationFixture: Decodable {
    var schemaVersion: Int
    var corpusID: String
    var reviewThresholdBasisPoints: Int
    var entries: [CalibrationEntry]
    var pairLabels: [CalibrationPairLabel]
    var expectedReviewClusters: [[String]]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case corpusID = "corpus_id"
        case reviewThresholdBasisPoints = "review_threshold_basis_points"
        case entries
        case pairLabels = "pair_labels"
        case expectedReviewClusters = "expected_review_clusters"
    }
}

private struct CalibrationEntry: Decodable {
    var id: String
    var language: String
    var content: String
    var offlineEmbedding: [Double]

    enum CodingKeys: String, CodingKey {
        case id
        case language
        case content
        case offlineEmbedding = "offline_embedding"
    }
}

private struct CalibrationPairLabel: Decodable {
    var firstEntryID: String
    var secondEntryID: String
    var isDuplicate: Bool

    var runtimeLabel: RuntimeMemorySemanticCalibrationPairLabel {
        RuntimeMemorySemanticCalibrationPairLabel(
            firstEntryID: firstEntryID,
            secondEntryID: secondEntryID,
            isDuplicate: isDuplicate
        )
    }

    enum CodingKeys: String, CodingKey {
        case firstEntryID = "first_entry_id"
        case secondEntryID = "second_entry_id"
        case isDuplicate = "is_duplicate"
    }
}
