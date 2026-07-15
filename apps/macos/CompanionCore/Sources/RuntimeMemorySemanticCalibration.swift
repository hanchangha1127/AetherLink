import Foundation

struct RuntimeMemorySemanticCalibrationPairLabel: Equatable, Sendable {
    var firstEntryID: String
    var secondEntryID: String
    var isDuplicate: Bool
}

struct RuntimeMemorySemanticCalibrationPairScore: Equatable, Sendable {
    var firstEntryID: String
    var secondEntryID: String
    var isDuplicate: Bool
    var isSemanticCandidate: Bool
    var similarityBasisPoints: Int
}

struct RuntimeMemorySemanticCalibrationThresholdMetrics: Equatable, Sendable {
    var thresholdBasisPoints: Int
    var truePositiveCount: Int
    var falsePositiveCount: Int
    var trueNegativeCount: Int
    var falseNegativeCount: Int
    var precisionBasisPoints: Int?
    var recallBasisPoints: Int
    var f1BasisPoints: Int
}

struct RuntimeMemorySemanticCalibrationResult: Equatable, Sendable {
    var pairScores: [RuntimeMemorySemanticCalibrationPairScore]
    var thresholdMetrics: [RuntimeMemorySemanticCalibrationThresholdMetrics]
    var bestF1ThresholdBasisPoints: Int
    var reviewThresholdMetrics: RuntimeMemorySemanticCalibrationThresholdMetrics
    var predictedReviewClusters: [RuntimeMemorySemanticDuplicateCluster]
    var expectedReviewClusters: [[String]]
    var reviewClustersExactMatch: Bool
}

enum RuntimeMemorySemanticCalibrationError: Error, Equatable {
    case invalidCandidateCount
    case invalidReviewThreshold
    case invalidPairLabelCount
    case unknownPairEntryID(String)
    case noncanonicalPairLabel(String, String)
    case duplicatePairLabel(String, String)
    case missingPositiveOrNegativePairLabel
    case invalidExpectedCluster
    case unknownExpectedClusterEntryID(String)
    case repeatedExpectedClusterEntryID(String)
    case noncanonicalExpectedCluster
    case noncanonicalExpectedClusterOrder
}

enum RuntimeMemorySemanticCalibrationEvaluator {
    static func evaluate(
        candidates: [RuntimeSemanticMemoryCandidate],
        embeddings: [[Double]],
        pairLabels: [RuntimeMemorySemanticCalibrationPairLabel],
        expectedReviewClusters: [[String]],
        reviewThresholdBasisPoints: Int,
        cancellationCheck: () throws -> Void = { try Task.checkCancellation() }
    ) throws -> RuntimeMemorySemanticCalibrationResult {
        guard candidates.count >= 2,
              candidates.count <= RuntimeMemorySemanticDuplicateSuggester.candidateLimit else {
            throw RuntimeMemorySemanticCalibrationError.invalidCandidateCount
        }
        guard reviewThresholdBasisPoints >=
                RuntimeMemorySemanticDuplicateSuggester.minimumSimilarityThresholdBasisPoints,
              reviewThresholdBasisPoints <=
                RuntimeMemorySemanticDuplicateSuggester.maximumSimilarityThresholdBasisPoints else {
            throw RuntimeMemorySemanticCalibrationError.invalidReviewThreshold
        }
        let maximumPairCount = candidates.count * (candidates.count - 1) / 2
        guard !pairLabels.isEmpty, pairLabels.count <= maximumPairCount else {
            throw RuntimeMemorySemanticCalibrationError.invalidPairLabelCount
        }

        var candidateIndexes: [String: Int] = [:]
        for index in candidates.indices {
            try cancellationCheck()
            let entryID = candidates[index].entry.id
            guard candidateIndexes[entryID] == nil else {
                throw RuntimeMemorySemanticDuplicateSuggestionsError.duplicateCandidateID(entryID)
            }
            candidateIndexes[entryID] = index
        }
        guard embeddings.count == candidates.count else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.embeddingCountMismatch
        }
        let normalizedEmbeddings = try RuntimeMemorySemanticDuplicateSuggester.normalized(
            embeddings,
            cancellationCheck: cancellationCheck
        )

        var seenLabels = Set<RuntimeMemorySemanticCalibrationPairKey>()
        var positiveCount = 0
        var negativeCount = 0
        var pairScores: [RuntimeMemorySemanticCalibrationPairScore] = []
        pairScores.reserveCapacity(pairLabels.count)
        for label in pairLabels {
            try cancellationCheck()
            guard let firstIndex = candidateIndexes[label.firstEntryID] else {
                throw RuntimeMemorySemanticCalibrationError
                    .unknownPairEntryID(label.firstEntryID)
            }
            guard let secondIndex = candidateIndexes[label.secondEntryID] else {
                throw RuntimeMemorySemanticCalibrationError
                    .unknownPairEntryID(label.secondEntryID)
            }
            guard RuntimeMemorySemanticDuplicateSuggester.utf8LexicographicallyPrecedes(
                label.firstEntryID,
                label.secondEntryID
            ) else {
                throw RuntimeMemorySemanticCalibrationError.noncanonicalPairLabel(
                    label.firstEntryID,
                    label.secondEntryID
                )
            }
            let labelKey = RuntimeMemorySemanticCalibrationPairKey(
                firstEntryID: label.firstEntryID,
                secondEntryID: label.secondEntryID
            )
            guard seenLabels.insert(labelKey).inserted else {
                throw RuntimeMemorySemanticCalibrationError.duplicatePairLabel(
                    label.firstEntryID,
                    label.secondEntryID
                )
            }
            if label.isDuplicate {
                positiveCount += 1
            } else {
                negativeCount += 1
            }
            let score = try RuntimeMemorySemanticDuplicateSuggester.similarityBasisPoints(
                normalizedEmbeddings[firstIndex],
                normalizedEmbeddings[secondIndex],
                cancellationCheck: cancellationCheck
            )
            pairScores.append(RuntimeMemorySemanticCalibrationPairScore(
                firstEntryID: label.firstEntryID,
                secondEntryID: label.secondEntryID,
                isDuplicate: label.isDuplicate,
                isSemanticCandidate: Data(candidates[firstIndex].entry.content.utf8) !=
                    Data(candidates[secondIndex].entry.content.utf8),
                similarityBasisPoints: score
            ))
        }
        guard positiveCount > 0, negativeCount > 0 else {
            throw RuntimeMemorySemanticCalibrationError.missingPositiveOrNegativePairLabel
        }

        pairScores.sort {
            if $0.firstEntryID != $1.firstEntryID {
                return RuntimeMemorySemanticDuplicateSuggester.utf8LexicographicallyPrecedes(
                    $0.firstEntryID,
                    $1.firstEntryID
                )
            }
            return RuntimeMemorySemanticDuplicateSuggester.utf8LexicographicallyPrecedes(
                $0.secondEntryID,
                $1.secondEntryID
            )
        }

        var thresholdMetrics: [RuntimeMemorySemanticCalibrationThresholdMetrics] = []
        thresholdMetrics.reserveCapacity(
            RuntimeMemorySemanticDuplicateSuggester.maximumSimilarityThresholdBasisPoints -
                RuntimeMemorySemanticDuplicateSuggester.minimumSimilarityThresholdBasisPoints + 1
        )
        let thresholdRange = ClosedRange(uncheckedBounds: (
            lower: RuntimeMemorySemanticDuplicateSuggester
                .minimumSimilarityThresholdBasisPoints,
            upper: RuntimeMemorySemanticDuplicateSuggester
                .maximumSimilarityThresholdBasisPoints
        ))
        for threshold in thresholdRange {
            try cancellationCheck()
            thresholdMetrics.append(try metrics(
                for: pairScores,
                thresholdBasisPoints: threshold,
                cancellationCheck: cancellationCheck
            ))
        }
        let bestMetrics = thresholdMetrics.max(by: metricsPrecede)!
        let reviewMetrics = thresholdMetrics[
            reviewThresholdBasisPoints -
                RuntimeMemorySemanticDuplicateSuggester.minimumSimilarityThresholdBasisPoints
        ]

        let canonicalExpectedClusters = try validateExpectedClusters(
            expectedReviewClusters,
            candidateIndexes: candidateIndexes
        )
        let clusterResult = try RuntimeMemorySemanticDuplicateSuggester.clusters(
            candidates: candidates,
            embeddings: embeddings,
            similarityThresholdBasisPoints: reviewThresholdBasisPoints,
            cancellationCheck: cancellationCheck
        )
        let canonicalPredictedClusters = clusterResult.clusters
            .map(\.entryIDs)
            .sorted(by: clusterIDsPrecede)

        return RuntimeMemorySemanticCalibrationResult(
            pairScores: pairScores,
            thresholdMetrics: thresholdMetrics,
            bestF1ThresholdBasisPoints: bestMetrics.thresholdBasisPoints,
            reviewThresholdMetrics: reviewMetrics,
            predictedReviewClusters: clusterResult.clusters,
            expectedReviewClusters: canonicalExpectedClusters,
            reviewClustersExactMatch: canonicalPredictedClusters == canonicalExpectedClusters
        )
    }

    private static func metrics(
        for pairScores: [RuntimeMemorySemanticCalibrationPairScore],
        thresholdBasisPoints: Int,
        cancellationCheck: () throws -> Void
    ) throws -> RuntimeMemorySemanticCalibrationThresholdMetrics {
        var truePositiveCount = 0
        var falsePositiveCount = 0
        var trueNegativeCount = 0
        var falseNegativeCount = 0
        for (index, pairScore) in pairScores.enumerated() {
            if index.isMultiple(of: 1_024) {
                try cancellationCheck()
            }
            let predictedDuplicate = pairScore.isSemanticCandidate &&
                pairScore.similarityBasisPoints >= thresholdBasisPoints
            switch (pairScore.isDuplicate, predictedDuplicate) {
            case (true, true): truePositiveCount += 1
            case (false, true): falsePositiveCount += 1
            case (false, false): trueNegativeCount += 1
            case (true, false): falseNegativeCount += 1
            }
        }
        let predictedPositiveCount = truePositiveCount + falsePositiveCount
        let actualPositiveCount = truePositiveCount + falseNegativeCount
        return RuntimeMemorySemanticCalibrationThresholdMetrics(
            thresholdBasisPoints: thresholdBasisPoints,
            truePositiveCount: truePositiveCount,
            falsePositiveCount: falsePositiveCount,
            trueNegativeCount: trueNegativeCount,
            falseNegativeCount: falseNegativeCount,
            precisionBasisPoints: predictedPositiveCount == 0 ? nil : ratioBasisPoints(
                numerator: truePositiveCount,
                denominator: predictedPositiveCount
            ),
            recallBasisPoints: ratioBasisPoints(
                numerator: truePositiveCount,
                denominator: actualPositiveCount
            ),
            f1BasisPoints: ratioBasisPoints(
                numerator: 2 * truePositiveCount,
                denominator: 2 * truePositiveCount + falsePositiveCount + falseNegativeCount
            )
        )
    }

    private static func ratioBasisPoints(numerator: Int, denominator: Int) -> Int {
        guard denominator > 0 else { return 0 }
        return (numerator * 10_000 + denominator / 2) / denominator
    }

    private static func metricsPrecede(
        _ lhs: RuntimeMemorySemanticCalibrationThresholdMetrics,
        _ rhs: RuntimeMemorySemanticCalibrationThresholdMetrics
    ) -> Bool {
        if lhs.f1BasisPoints != rhs.f1BasisPoints {
            return lhs.f1BasisPoints < rhs.f1BasisPoints
        }
        if lhs.precisionBasisPoints != rhs.precisionBasisPoints {
            return (lhs.precisionBasisPoints ?? -1) < (rhs.precisionBasisPoints ?? -1)
        }
        return lhs.thresholdBasisPoints < rhs.thresholdBasisPoints
    }

    private static func validateExpectedClusters(
        _ clusters: [[String]],
        candidateIndexes: [String: Int]
    ) throws -> [[String]] {
        guard clusters.count <= RuntimeMemorySemanticDuplicateSuggester.clusterLimit else {
            throw RuntimeMemorySemanticCalibrationError.invalidExpectedCluster
        }
        var seenEntryIDs = Set<String>()
        for cluster in clusters {
            guard cluster.count >= 2,
                  cluster.count <= RuntimeMemorySemanticDuplicateSuggester.candidateLimit else {
                throw RuntimeMemorySemanticCalibrationError.invalidExpectedCluster
            }
            for entryID in cluster {
                guard candidateIndexes[entryID] != nil else {
                    throw RuntimeMemorySemanticCalibrationError
                        .unknownExpectedClusterEntryID(entryID)
                }
                guard seenEntryIDs.insert(entryID).inserted else {
                    throw RuntimeMemorySemanticCalibrationError
                        .repeatedExpectedClusterEntryID(entryID)
                }
            }
            guard cluster.elementsEqual(
                cluster.sorted(by: RuntimeMemorySemanticDuplicateSuggester
                    .utf8LexicographicallyPrecedes)
            ) else {
                throw RuntimeMemorySemanticCalibrationError.noncanonicalExpectedCluster
            }
        }
        guard clusters.elementsEqual(clusters.sorted(by: clusterIDsPrecede)) else {
            throw RuntimeMemorySemanticCalibrationError.noncanonicalExpectedClusterOrder
        }
        return clusters
    }

    private static func clusterIDsPrecede(_ lhs: [String], _ rhs: [String]) -> Bool {
        lhs.lexicographicallyPrecedes(
            rhs,
            by: RuntimeMemorySemanticDuplicateSuggester.utf8LexicographicallyPrecedes
        )
    }
}

private struct RuntimeMemorySemanticCalibrationPairKey: Hashable {
    var firstEntryID: String
    var secondEntryID: String
}
