import CryptoKit
import Foundation

struct RuntimeMemorySemanticDuplicateCandidateSelection: Sendable {
    var candidates: [RuntimeSemanticMemoryCandidate]
    var omittedEntryCount: Int
    var sourceTruncated: Bool

    init(
        candidates: [RuntimeSemanticMemoryCandidate],
        omittedEntryCount: Int,
        sourceTruncated: Bool
    ) {
        self.candidates = candidates
        self.omittedEntryCount = omittedEntryCount
        self.sourceTruncated = sourceTruncated
    }
}

struct RuntimeMemorySemanticDuplicatePair: Equatable, Sendable {
    var firstEntryID: String
    var secondEntryID: String
    var similarityBasisPoints: Int

    init(firstEntryID: String, secondEntryID: String, similarityBasisPoints: Int) {
        self.firstEntryID = firstEntryID
        self.secondEntryID = secondEntryID
        self.similarityBasisPoints = similarityBasisPoints
    }
}

struct RuntimeMemorySemanticDuplicateSuggestionsResult: Equatable, Sendable {
    var pairs: [RuntimeMemorySemanticDuplicatePair]
    var scannedCount: Int
    var omittedEntryCount: Int
    var sourceTruncated: Bool
    var truncated: Bool

    init(
        pairs: [RuntimeMemorySemanticDuplicatePair],
        scannedCount: Int,
        omittedEntryCount: Int,
        sourceTruncated: Bool,
        truncated: Bool
    ) {
        self.pairs = pairs
        self.scannedCount = scannedCount
        self.omittedEntryCount = omittedEntryCount
        self.sourceTruncated = sourceTruncated
        self.truncated = truncated
    }
}

struct RuntimeMemorySemanticDuplicateCluster: Equatable, Sendable {
    var entryIDs: [String]
    var minimumSimilarityBasisPoints: Int

    init(entryIDs: [String], minimumSimilarityBasisPoints: Int) {
        self.entryIDs = entryIDs
        self.minimumSimilarityBasisPoints = minimumSimilarityBasisPoints
    }
}

struct RuntimeMemorySemanticDuplicateClustersResult: Equatable, Sendable {
    var clusters: [RuntimeMemorySemanticDuplicateCluster]
    var scannedCount: Int
    var omittedEntryCount: Int
    var sourceTruncated: Bool

    init(
        clusters: [RuntimeMemorySemanticDuplicateCluster],
        scannedCount: Int,
        omittedEntryCount: Int,
        sourceTruncated: Bool
    ) {
        self.clusters = clusters
        self.scannedCount = scannedCount
        self.omittedEntryCount = omittedEntryCount
        self.sourceTruncated = sourceTruncated
    }
}

enum RuntimeMemorySemanticDuplicateSuggestionsError: Error, Equatable {
    case invalidDocumentByteLimit
    case candidateLimitExceeded
    case duplicateCandidateID(String)
    case invalidSimilarityThreshold
    case embeddingCountMismatch
    case invalidEmbeddingDimension
    case embeddingDimensionLimitExceeded
    case invalidEmbedding
    case responseEntryIDUTF8ByteLimitExceeded
}

enum RuntimeMemorySemanticDuplicateSuggester {
    static let candidateLimit = 200
    static let pairLimit = 100
    static let clusterLimit = 100
    static let maximumSourceEventLogByteCount = 8 * 1_024 * 1_024
    static let maximumCandidateContentUTF8ByteCount = 1 * 1_024 * 1_024
    static let maximumEmbeddingBatchCount = 64
    static let maximumEmbeddingBatchUTF8ByteCount = 262_144
    static let maximumEmbeddingDimension = 65_536
    static let minimumSimilarityThresholdBasisPoints = 8_000
    static let maximumSimilarityThresholdBasisPoints = 10_000
    static let maximumResponseEntryIDUTF8ByteCount = 128 * 1_024

    private static let cancellationCheckStride = 1_024

    private static let documentEncodingVersion =
        "approved-memory-semantic-duplicate-document-v1"

    static func selectCandidates(
        from sources: [RuntimeMemorySemanticSearchSource],
        modelDocumentUTF8ByteLimit: Int
    ) throws -> RuntimeMemorySemanticDuplicateCandidateSelection {
        guard modelDocumentUTF8ByteLimit > 0 else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.invalidDocumentByteLimit
        }

        let inspectedCount = min(sources.count, candidateLimit)
        var seenEntryIDs = Set<String>()
        var candidates: [RuntimeSemanticMemoryCandidate] = []
        var omittedEntryCount = 0
        var candidateContentUTF8ByteCount = 0

        for source in sources.prefix(inspectedCount) {
            guard seenEntryIDs.insert(source.entry.id).inserted else {
                throw RuntimeMemorySemanticDuplicateSuggestionsError
                    .duplicateCandidateID(source.entry.id)
            }
            let document = source.entry.content
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard !document.isEmpty,
                  document.utf8.count <= modelDocumentUTF8ByteLimit else {
                omittedEntryCount += 1
                continue
            }
            let (nextCandidateContentUTF8ByteCount, overflow) = candidateContentUTF8ByteCount
                .addingReportingOverflow(document.utf8.count)
            guard !overflow,
                  nextCandidateContentUTF8ByteCount <=
                    maximumCandidateContentUTF8ByteCount else {
                omittedEntryCount += 1
                continue
            }
            candidateContentUTF8ByteCount = nextCandidateContentUTF8ByteCount
            candidates.append(RuntimeSemanticMemoryCandidate(
                entry: source.entry,
                sourceRevision: source.sourceRevision,
                document: document,
                documentFingerprint: fingerprint(fields: [
                    documentEncodingVersion,
                    String(modelDocumentUTF8ByteLimit),
                    document
                ])
            ))
        }

        return RuntimeMemorySemanticDuplicateCandidateSelection(
            candidates: candidates,
            omittedEntryCount: omittedEntryCount,
            sourceTruncated: sources.count > candidateLimit || omittedEntryCount > 0
        )
    }

    static func suggestions(
        from selection: RuntimeMemorySemanticDuplicateCandidateSelection,
        embeddings: [[Double]],
        similarityThresholdBasisPoints: Int
    ) throws -> RuntimeMemorySemanticDuplicateSuggestionsResult {
        try suggestions(
            candidates: selection.candidates,
            embeddings: embeddings,
            similarityThresholdBasisPoints: similarityThresholdBasisPoints,
            omittedEntryCount: selection.omittedEntryCount,
            sourceTruncated: selection.sourceTruncated
        )
    }

    static func clusters(
        from selection: RuntimeMemorySemanticDuplicateCandidateSelection,
        embeddings: [[Double]],
        similarityThresholdBasisPoints: Int
    ) throws -> RuntimeMemorySemanticDuplicateClustersResult {
        try clusters(
            candidates: selection.candidates,
            embeddings: embeddings,
            similarityThresholdBasisPoints: similarityThresholdBasisPoints,
            omittedEntryCount: selection.omittedEntryCount,
            sourceTruncated: selection.sourceTruncated
        )
    }

    static func clusters(
        candidates: [RuntimeSemanticMemoryCandidate],
        embeddings: [[Double]],
        similarityThresholdBasisPoints: Int,
        omittedEntryCount: Int = 0,
        sourceTruncated: Bool = false,
        cancellationCheck: () throws -> Void = { try Task.checkCancellation() }
    ) throws -> RuntimeMemorySemanticDuplicateClustersResult {
        guard similarityThresholdBasisPoints >= minimumSimilarityThresholdBasisPoints,
              similarityThresholdBasisPoints <= maximumSimilarityThresholdBasisPoints else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.invalidSimilarityThreshold
        }
        guard candidates.count <= candidateLimit else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.candidateLimitExceeded
        }

        var seenEntryIDs = Set<String>()
        for candidate in candidates {
            guard seenEntryIDs.insert(candidate.entry.id).inserted else {
                throw RuntimeMemorySemanticDuplicateSuggestionsError
                    .duplicateCandidateID(candidate.entry.id)
            }
        }
        guard embeddings.count == candidates.count else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.embeddingCountMismatch
        }

        let canonicalIndexes = candidates.indices.sorted {
            utf8LexicographicallyPrecedes(candidates[$0].entry.id, candidates[$1].entry.id)
        }
        let normalizedEmbeddings = try normalized(
            embeddings,
            cancellationCheck: cancellationCheck
        )
        var scores = Array(
            repeating: Array<Int?>(repeating: nil, count: candidates.count),
            count: candidates.count
        )
        if canonicalIndexes.count >= 2 {
            for firstOffset in 0..<(canonicalIndexes.count - 1) {
                try cancellationCheck()
                let firstIndex = canonicalIndexes[firstOffset]
                for secondOffset in (firstOffset + 1)..<canonicalIndexes.count {
                    try cancellationCheck()
                    let secondIndex = canonicalIndexes[secondOffset]
                    guard Data(candidates[firstIndex].entry.content.utf8) !=
                            Data(candidates[secondIndex].entry.content.utf8) else {
                        continue
                    }
                    let score = try similarityBasisPoints(
                        normalizedEmbeddings[firstIndex],
                        normalizedEmbeddings[secondIndex],
                        cancellationCheck: cancellationCheck
                    )
                    guard score >= similarityThresholdBasisPoints else { continue }
                    scores[firstIndex][secondIndex] = score
                    scores[secondIndex][firstIndex] = score
                }
            }
        }

        var workingClusters = canonicalIndexes.map {
            RuntimeMemorySemanticWorkingCluster(indexes: [$0], minimumScore: 10_000)
        }
        while workingClusters.count >= 2 {
            try cancellationCheck()
            var bestMerge: RuntimeMemorySemanticClusterMerge?
            for firstIndex in 0..<(workingClusters.count - 1) {
                for secondIndex in (firstIndex + 1)..<workingClusters.count {
                    try cancellationCheck()
                    let lhs = workingClusters[firstIndex]
                    let rhs = workingClusters[secondIndex]
                    var minimumScore = min(lhs.minimumScore, rhs.minimumScore)
                    var eligible = true
                    for lhsIndex in lhs.indexes {
                        for rhsIndex in rhs.indexes {
                            try cancellationCheck()
                            guard let score = scores[lhsIndex][rhsIndex] else {
                                eligible = false
                                break
                            }
                            minimumScore = min(minimumScore, score)
                        }
                        if !eligible { break }
                    }
                    guard eligible else { continue }
                    let mergedIndexes = (lhs.indexes + rhs.indexes).sorted {
                        utf8LexicographicallyPrecedes(
                            candidates[$0].entry.id,
                            candidates[$1].entry.id
                        )
                    }
                    let merge = RuntimeMemorySemanticClusterMerge(
                        firstWorkingIndex: firstIndex,
                        secondWorkingIndex: secondIndex,
                        mergedIndexes: mergedIndexes,
                        minimumScore: minimumScore
                    )
                    if bestMerge == nil || clusterMerge(
                        merge,
                        precedes: bestMerge!,
                        candidates: candidates
                    ) {
                        bestMerge = merge
                    }
                }
            }
            guard let bestMerge else { break }
            workingClusters.remove(at: bestMerge.secondWorkingIndex)
            workingClusters.remove(at: bestMerge.firstWorkingIndex)
            workingClusters.append(RuntimeMemorySemanticWorkingCluster(
                indexes: bestMerge.mergedIndexes,
                minimumScore: bestMerge.minimumScore
            ))
            workingClusters.sort {
                canonicalIDArray(
                    for: $0.indexes,
                    candidates: candidates
                ).lexicographicallyPrecedes(
                    canonicalIDArray(for: $1.indexes, candidates: candidates),
                    by: utf8LexicographicallyPrecedes
                )
            }
        }

        var resultClusters = workingClusters.compactMap { cluster -> RuntimeMemorySemanticDuplicateCluster? in
            guard cluster.indexes.count >= 2 else { return nil }
            return RuntimeMemorySemanticDuplicateCluster(
                entryIDs: canonicalIDArray(for: cluster.indexes, candidates: candidates),
                minimumSimilarityBasisPoints: cluster.minimumScore
            )
        }
        resultClusters.sort { lhs, rhs in
            if lhs.minimumSimilarityBasisPoints != rhs.minimumSimilarityBasisPoints {
                return lhs.minimumSimilarityBasisPoints > rhs.minimumSimilarityBasisPoints
            }
            return lhs.entryIDs.lexicographicallyPrecedes(
                rhs.entryIDs,
                by: utf8LexicographicallyPrecedes
            )
        }
        guard resultClusters.count <= clusterLimit else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.responseEntryIDUTF8ByteLimitExceeded
        }

        var responseEntryIDUTF8ByteCount = 0
        var returnedEntryCount = 0
        for cluster in resultClusters {
            guard cluster.entryIDs.count >= 2,
                  cluster.entryIDs.count <= candidateLimit else {
                throw RuntimeMemorySemanticDuplicateSuggestionsError.candidateLimitExceeded
            }
            returnedEntryCount += cluster.entryIDs.count
            for entryID in cluster.entryIDs {
                let (nextByteCount, overflow) = responseEntryIDUTF8ByteCount
                    .addingReportingOverflow(entryID.utf8.count)
                guard !overflow,
                      nextByteCount <= maximumResponseEntryIDUTF8ByteCount else {
                    throw RuntimeMemorySemanticDuplicateSuggestionsError
                        .responseEntryIDUTF8ByteLimitExceeded
                }
                responseEntryIDUTF8ByteCount = nextByteCount
            }
        }
        guard returnedEntryCount <= candidates.count else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.candidateLimitExceeded
        }

        return RuntimeMemorySemanticDuplicateClustersResult(
            clusters: resultClusters,
            scannedCount: candidates.count,
            omittedEntryCount: omittedEntryCount,
            sourceTruncated: sourceTruncated
        )
    }

    static func suggestions(
        candidates: [RuntimeSemanticMemoryCandidate],
        embeddings: [[Double]],
        similarityThresholdBasisPoints: Int,
        omittedEntryCount: Int = 0,
        sourceTruncated: Bool = false,
        cancellationCheck: () throws -> Void = { try Task.checkCancellation() }
    ) throws -> RuntimeMemorySemanticDuplicateSuggestionsResult {
        guard similarityThresholdBasisPoints >= minimumSimilarityThresholdBasisPoints,
              similarityThresholdBasisPoints <= maximumSimilarityThresholdBasisPoints else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.invalidSimilarityThreshold
        }
        guard candidates.count <= candidateLimit else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.candidateLimitExceeded
        }

        var seenEntryIDs = Set<String>()
        for candidate in candidates {
            guard seenEntryIDs.insert(candidate.entry.id).inserted else {
                throw RuntimeMemorySemanticDuplicateSuggestionsError
                    .duplicateCandidateID(candidate.entry.id)
            }
        }
        guard embeddings.count == candidates.count else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.embeddingCountMismatch
        }

        let normalizedEmbeddings = try normalized(
            embeddings,
            cancellationCheck: cancellationCheck
        )
        var pairs: [RuntimeMemorySemanticDuplicatePair] = []
        if candidates.count >= 2 {
            for firstIndex in 0..<(candidates.count - 1) {
                try cancellationCheck()
                for secondIndex in (firstIndex + 1)..<candidates.count {
                    try cancellationCheck()
                    let first = candidates[firstIndex]
                    let second = candidates[secondIndex]
                    guard Data(first.entry.content.utf8) != Data(second.entry.content.utf8) else {
                        continue
                    }
                    let score = try similarityBasisPoints(
                        normalizedEmbeddings[firstIndex],
                        normalizedEmbeddings[secondIndex],
                        cancellationCheck: cancellationCheck
                    )
                    guard score >= similarityThresholdBasisPoints else { continue }

                    let firstPrecedesSecond = utf8LexicographicallyPrecedes(
                        first.entry.id,
                        second.entry.id
                    )
                    pairs.append(RuntimeMemorySemanticDuplicatePair(
                        firstEntryID: firstPrecedesSecond ? first.entry.id : second.entry.id,
                        secondEntryID: firstPrecedesSecond ? second.entry.id : first.entry.id,
                        similarityBasisPoints: score
                    ))
                }
            }
        }

        pairs.sort { lhs, rhs in
            if lhs.similarityBasisPoints != rhs.similarityBasisPoints {
                return lhs.similarityBasisPoints > rhs.similarityBasisPoints
            }
            if lhs.firstEntryID != rhs.firstEntryID {
                return utf8LexicographicallyPrecedes(lhs.firstEntryID, rhs.firstEntryID)
            }
            return utf8LexicographicallyPrecedes(lhs.secondEntryID, rhs.secondEntryID)
        }

        let pairResultTruncated = pairs.count > pairLimit
        let boundedPairs = Array(pairs.prefix(pairLimit))
        var responseEntryIDUTF8ByteCount = 0
        for pair in boundedPairs {
            for entryID in [pair.firstEntryID, pair.secondEntryID] {
                let (nextByteCount, overflow) = responseEntryIDUTF8ByteCount
                    .addingReportingOverflow(entryID.utf8.count)
                guard !overflow,
                      nextByteCount <= maximumResponseEntryIDUTF8ByteCount else {
                    throw RuntimeMemorySemanticDuplicateSuggestionsError
                        .responseEntryIDUTF8ByteLimitExceeded
                }
                responseEntryIDUTF8ByteCount = nextByteCount
            }
        }

        return RuntimeMemorySemanticDuplicateSuggestionsResult(
            pairs: boundedPairs,
            scannedCount: candidates.count,
            omittedEntryCount: omittedEntryCount,
            sourceTruncated: sourceTruncated,
            truncated: pairResultTruncated
        )
    }

    private static func normalized(
        _ embeddings: [[Double]],
        cancellationCheck: () throws -> Void
    ) throws -> [[Double]] {
        guard let dimension = embeddings.first?.count else { return [] }
        guard dimension > 0 else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.invalidEmbeddingDimension
        }
        guard dimension <= maximumEmbeddingDimension else {
            throw RuntimeMemorySemanticDuplicateSuggestionsError.embeddingDimensionLimitExceeded
        }

        var normalizedEmbeddings: [[Double]] = []
        normalizedEmbeddings.reserveCapacity(embeddings.count)
        for embedding in embeddings {
            try cancellationCheck()
            guard embedding.count == dimension else {
                throw RuntimeMemorySemanticDuplicateSuggestionsError.invalidEmbeddingDimension
            }

            var scale = 0.0
            for (index, value) in embedding.enumerated() {
                if index.isMultiple(of: cancellationCheckStride) {
                    try cancellationCheck()
                }
                guard value.isFinite else {
                    throw RuntimeMemorySemanticDuplicateSuggestionsError.invalidEmbedding
                }
                scale = max(scale, abs(value))
            }
            guard scale > 0 else {
                throw RuntimeMemorySemanticDuplicateSuggestionsError.invalidEmbedding
            }

            var scaled: [Double] = []
            scaled.reserveCapacity(dimension)
            var magnitudeSquared = 0.0
            for (index, value) in embedding.enumerated() {
                if index.isMultiple(of: cancellationCheckStride) {
                    try cancellationCheck()
                }
                let scaledValue = value / scale
                scaled.append(scaledValue)
                magnitudeSquared += scaledValue * scaledValue
            }
            let magnitude = sqrt(magnitudeSquared)
            guard magnitude.isFinite, magnitude > 0 else {
                throw RuntimeMemorySemanticDuplicateSuggestionsError.invalidEmbedding
            }

            var normalized: [Double] = []
            normalized.reserveCapacity(dimension)
            for (index, value) in scaled.enumerated() {
                if index.isMultiple(of: cancellationCheckStride) {
                    try cancellationCheck()
                }
                normalized.append(value / magnitude)
            }
            normalizedEmbeddings.append(normalized)
        }
        return normalizedEmbeddings
    }

    private static func similarityBasisPoints(
        _ lhs: [Double],
        _ rhs: [Double],
        cancellationCheck: () throws -> Void
    ) throws -> Int {
        var cosine = 0.0
        for index in lhs.indices {
            if index.isMultiple(of: cancellationCheckStride) {
                try cancellationCheck()
            }
            cosine += lhs[index] * rhs[index]
        }
        let boundedCosine = min(1, max(-1, cosine))
        return Int(
            (boundedCosine * Double(maximumSimilarityThresholdBasisPoints))
                .rounded(.toNearestOrAwayFromZero)
        )
    }

    private static func utf8LexicographicallyPrecedes(_ lhs: String, _ rhs: String) -> Bool {
        RuntimeMemoryExactDuplicateSuggester.utf8LexicographicallyPrecedes(lhs, rhs)
    }

    private static func canonicalIDArray(
        for indexes: [Int],
        candidates: [RuntimeSemanticMemoryCandidate]
    ) -> [String] {
        indexes.map { candidates[$0].entry.id }
    }

    private static func clusterMerge(
        _ lhs: RuntimeMemorySemanticClusterMerge,
        precedes rhs: RuntimeMemorySemanticClusterMerge,
        candidates: [RuntimeSemanticMemoryCandidate]
    ) -> Bool {
        if lhs.minimumScore != rhs.minimumScore {
            return lhs.minimumScore > rhs.minimumScore
        }
        return canonicalIDArray(
            for: lhs.mergedIndexes,
            candidates: candidates
        ).lexicographicallyPrecedes(
            canonicalIDArray(for: rhs.mergedIndexes, candidates: candidates),
            by: utf8LexicographicallyPrecedes
        )
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

private struct RuntimeMemorySemanticWorkingCluster {
    var indexes: [Int]
    var minimumScore: Int
}

private struct RuntimeMemorySemanticClusterMerge {
    var firstWorkingIndex: Int
    var secondWorkingIndex: Int
    var mergedIndexes: [Int]
    var minimumScore: Int
}
