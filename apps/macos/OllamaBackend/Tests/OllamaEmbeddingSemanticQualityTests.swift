import CryptoKit
import Foundation
import XCTest

enum OllamaEmbeddingSemanticQualityError: Error, Equatable {
    case invalidTaskSet
    case invalidEmbeddingShape
    case invalidEmbeddingValue
    case positiveMarginFailed(scenarioID: String)
    case repeatabilityFailed(inputID: String)
}

struct OllamaEmbeddingSemanticTaskSet: Decodable {
    struct Input: Decodable {
        let id: String
        let text: String
    }

    struct Scenario: Decodable {
        let hardNegativeId: String
        let id: String
        let positiveId: String
        let queryId: String
        let unrelatedNegativeId: String
    }

    static let fixtureID = (
        "aetherlink-ollama-embedding-semantic-task-set-v1"
    )
    static let recordedSHA256 = (
        "e00f27d91a11f73f6f5f74eef9a4681b2dd2d70c45090456de17a5642b67023f"
    )
    static let minimumPositiveMarginBasisPoints = 200
    static let minimumRepeatCosineBasisPoints = 9_990
    static let scenarioCount = 4
    static let textCount = 16

    let firstCall: [Input]
    let fixtureId: String
    let minimumPositiveMarginBasisPoints: Int
    let minimumRepeatCosineBasisPoints: Int
    let scenarios: [Scenario]
    let schemaVersion: Int
    let secondCallOrder: [String]

    static func load(
        from url: URL,
        expectedSHA256: String
    ) throws -> Self {
        guard expectedSHA256 == recordedSHA256 else {
            throw OllamaEmbeddingSemanticQualityError.invalidTaskSet
        }
        let data = try Data(contentsOf: url, options: [.mappedIfSafe])
        let digest = SHA256.hash(data: data).map {
            String(format: "%02x", $0)
        }.joined()
        guard digest == expectedSHA256 else {
            throw OllamaEmbeddingSemanticQualityError.invalidTaskSet
        }
        try validateClosedJSONShape(data)
        let value = try JSONDecoder().decode(Self.self, from: data)
        try value.validate()
        return value
    }

    private static func validateClosedJSONShape(_ data: Data) throws {
        guard
            let root = try JSONSerialization.jsonObject(with: data)
                as? [String: Any],
            Set(root.keys) == [
                "firstCall",
                "fixtureId",
                "minimumPositiveMarginBasisPoints",
                "minimumRepeatCosineBasisPoints",
                "scenarios",
                "schemaVersion",
                "secondCallOrder",
            ],
            let firstCall = root["firstCall"] as? [[String: Any]],
            firstCall.allSatisfy({ Set($0.keys) == ["id", "text"] }),
            let scenarios = root["scenarios"] as? [[String: Any]],
            scenarios.allSatisfy({
                Set($0.keys) == [
                    "hardNegativeId",
                    "id",
                    "positiveId",
                    "queryId",
                    "unrelatedNegativeId",
                ]
            })
        else {
            throw OllamaEmbeddingSemanticQualityError.invalidTaskSet
        }
    }

    private func validate() throws {
        guard
            fixtureId == Self.fixtureID,
            schemaVersion == 1,
            minimumPositiveMarginBasisPoints
                == Self.minimumPositiveMarginBasisPoints,
            minimumRepeatCosineBasisPoints
                == Self.minimumRepeatCosineBasisPoints,
            scenarios.count == Self.scenarioCount,
            firstCall.count == Self.textCount,
            secondCallOrder.count == Self.textCount
        else {
            throw OllamaEmbeddingSemanticQualityError.invalidTaskSet
        }

        let inputIDs = firstCall.map(\.id)
        let uniqueInputIDs = Set(inputIDs)
        let scenarioIDs = scenarios.map(\.id)
        guard
            uniqueInputIDs.count == Self.textCount,
            Set(secondCallOrder) == uniqueInputIDs,
            Set(secondCallOrder).count == Self.textCount,
            secondCallOrder != inputIDs,
            Set(scenarioIDs).count == Self.scenarioCount,
            firstCall.allSatisfy({
                Self.isBoundedIdentifier($0.id)
                    && !$0.text.trimmingCharacters(
                        in: .whitespacesAndNewlines
                    ).isEmpty
                    && $0.text.utf8.count <= 512
                    && $0.text.unicodeScalars.allSatisfy({
                        (0x20...0x7e).contains($0.value)
                    })
            }),
            scenarioIDs.allSatisfy(Self.isBoundedIdentifier)
        else {
            throw OllamaEmbeddingSemanticQualityError.invalidTaskSet
        }

        var referencedIDs: [String] = []
        for scenario in scenarios {
            let roles = [
                scenario.queryId,
                scenario.positiveId,
                scenario.hardNegativeId,
                scenario.unrelatedNegativeId,
            ]
            guard Set(roles).count == 4 else {
                throw OllamaEmbeddingSemanticQualityError.invalidTaskSet
            }
            referencedIDs.append(contentsOf: roles)
        }
        guard
            referencedIDs.count == Self.textCount,
            Set(referencedIDs) == uniqueInputIDs
        else {
            throw OllamaEmbeddingSemanticQualityError.invalidTaskSet
        }
    }

    private static func isBoundedIdentifier(_ value: String) -> Bool {
        guard (1...64).contains(value.utf8.count) else { return false }
        return value.unicodeScalars.allSatisfy {
            (0x61...0x7a).contains($0.value)
                || (0x30...0x39).contains($0.value)
                || $0.value == 0x2d
        }
    }

    var firstCallTexts: [String] {
        firstCall.map(\.text)
    }

    var secondCallTexts: [String] {
        let textsByID = Dictionary(
            uniqueKeysWithValues: firstCall.map { ($0.id, $0.text) }
        )
        return secondCallOrder.compactMap { textsByID[$0] }
    }
}

struct OllamaEmbeddingSemanticAssessment: Equatable {
    let batchCalls: Int
    let embeddingCount: Int
    let scenarioCount: Int
    let textCountPerBatch: Int
}

enum OllamaEmbeddingSemanticScorer {
    static func assess(
        taskSet: OllamaEmbeddingSemanticTaskSet,
        firstEmbeddings: [[Double]],
        secondEmbeddings: [[Double]]
    ) throws -> OllamaEmbeddingSemanticAssessment {
        let first = try validatedEmbeddingMap(
            ids: taskSet.firstCall.map(\.id),
            embeddings: firstEmbeddings,
            expectedDimension: nil
        )
        let dimension = try requiredDimension(first)
        let second = try validatedEmbeddingMap(
            ids: taskSet.secondCallOrder,
            embeddings: secondEmbeddings,
            expectedDimension: dimension
        )

        for scenario in taskSet.scenarios {
            try validateRanking(
                scenario: scenario,
                embeddings: first,
                minimumBasisPoints: (
                    taskSet.minimumPositiveMarginBasisPoints
                )
            )
            try validateRanking(
                scenario: scenario,
                embeddings: second,
                minimumBasisPoints: (
                    taskSet.minimumPositiveMarginBasisPoints
                )
            )
        }
        for input in taskSet.firstCall {
            guard
                let firstVector = first[input.id],
                let secondVector = second[input.id],
                passesBasisPointMinimum(
                    try cosine(firstVector, secondVector),
                    minimum: taskSet.minimumRepeatCosineBasisPoints
                )
            else {
                throw OllamaEmbeddingSemanticQualityError
                    .repeatabilityFailed(inputID: input.id)
            }
        }
        return OllamaEmbeddingSemanticAssessment(
            batchCalls: 2,
            embeddingCount: (
                firstEmbeddings.count + secondEmbeddings.count
            ),
            scenarioCount: taskSet.scenarios.count,
            textCountPerBatch: taskSet.firstCall.count
        )
    }

    static func passesBasisPointMinimum(
        _ value: Double,
        minimum: Int
    ) -> Bool {
        value.isFinite
            && minimum >= 0
            && value >= Double(minimum) / 10_000
    }

    private static func validatedEmbeddingMap(
        ids: [String],
        embeddings: [[Double]],
        expectedDimension: Int?
    ) throws -> [String: [Double]] {
        guard
            ids.count == OllamaEmbeddingSemanticTaskSet.textCount,
            embeddings.count == ids.count,
            Set(ids).count == ids.count,
            let observedDimension = embeddings.first?.count,
            observedDimension > 0,
            expectedDimension == nil || expectedDimension == observedDimension
        else {
            throw OllamaEmbeddingSemanticQualityError.invalidEmbeddingShape
        }
        for vector in embeddings {
            guard vector.count == observedDimension else {
                throw OllamaEmbeddingSemanticQualityError.invalidEmbeddingShape
            }
            guard
                vector.allSatisfy(\.isFinite),
                let normSquared = finiteDot(vector, vector),
                normSquared > 0
            else {
                throw OllamaEmbeddingSemanticQualityError.invalidEmbeddingValue
            }
        }
        return Dictionary(
            uniqueKeysWithValues: zip(ids, embeddings)
        )
    }

    private static func requiredDimension(
        _ embeddings: [String: [Double]]
    ) throws -> Int {
        guard let dimension = embeddings.values.first?.count else {
            throw OllamaEmbeddingSemanticQualityError.invalidEmbeddingShape
        }
        return dimension
    }

    private static func validateRanking(
        scenario: OllamaEmbeddingSemanticTaskSet.Scenario,
        embeddings: [String: [Double]],
        minimumBasisPoints: Int
    ) throws {
        guard
            let query = embeddings[scenario.queryId],
            let positive = embeddings[scenario.positiveId],
            let hardNegative = embeddings[scenario.hardNegativeId],
            let unrelatedNegative = embeddings[
                scenario.unrelatedNegativeId
            ]
        else {
            throw OllamaEmbeddingSemanticQualityError.invalidEmbeddingShape
        }
        let positiveCosine = try cosine(query, positive)
        for negative in [hardNegative, unrelatedNegative] {
            let margin = positiveCosine - (try cosine(query, negative))
            guard passesBasisPointMinimum(
                margin,
                minimum: minimumBasisPoints
            ) else {
                throw OllamaEmbeddingSemanticQualityError
                    .positiveMarginFailed(scenarioID: scenario.id)
            }
        }
    }

    private static func cosine(
        _ lhs: [Double],
        _ rhs: [Double]
    ) throws -> Double {
        guard lhs.count == rhs.count, !lhs.isEmpty else {
            throw OllamaEmbeddingSemanticQualityError.invalidEmbeddingShape
        }
        guard
            let dot = finiteDot(lhs, rhs),
            let lhsNormSquared = finiteDot(lhs, lhs),
            let rhsNormSquared = finiteDot(rhs, rhs),
            lhsNormSquared > 0,
            rhsNormSquared > 0
        else {
            throw OllamaEmbeddingSemanticQualityError.invalidEmbeddingValue
        }
        let denominator = sqrt(lhsNormSquared) * sqrt(rhsNormSquared)
        let value = dot / denominator
        guard denominator.isFinite, denominator > 0, value.isFinite else {
            throw OllamaEmbeddingSemanticQualityError.invalidEmbeddingValue
        }
        return max(-1, min(1, value))
    }

    private static func finiteDot(
        _ lhs: [Double],
        _ rhs: [Double]
    ) -> Double? {
        guard lhs.count == rhs.count else { return nil }
        var result = 0.0
        for (left, right) in zip(lhs, rhs) {
            let product = left * right
            guard product.isFinite else { return nil }
            result += product
            guard result.isFinite else { return nil }
        }
        return result
    }
}

final class OllamaEmbeddingSemanticQualityTests: XCTestCase {
    func testCanonicalTaskSetHasRecordedHashAndClosedContract() throws {
        let taskSet = try loadCanonicalTaskSet()

        XCTAssertEqual(
            taskSet.fixtureId,
            OllamaEmbeddingSemanticTaskSet.fixtureID
        )
        XCTAssertEqual(
            taskSet.scenarios.count,
            OllamaEmbeddingSemanticTaskSet.scenarioCount
        )
        XCTAssertEqual(
            taskSet.firstCall.count,
            OllamaEmbeddingSemanticTaskSet.textCount
        )
        XCTAssertEqual(
            taskSet.secondCallTexts.count,
            OllamaEmbeddingSemanticTaskSet.textCount
        )
    }

    func testScorerAcceptsEveryScenarioAcrossBothPermutations() throws {
        let taskSet = try loadCanonicalTaskSet()
        let vectors = syntheticVectors(taskSet: taskSet)

        let assessment = try OllamaEmbeddingSemanticScorer.assess(
            taskSet: taskSet,
            firstEmbeddings: orderedVectors(
                ids: taskSet.firstCall.map(\.id),
                vectors: vectors
            ),
            secondEmbeddings: orderedVectors(
                ids: taskSet.secondCallOrder,
                vectors: vectors
            )
        )

        XCTAssertEqual(
            assessment,
            OllamaEmbeddingSemanticAssessment(
                batchCalls: 2,
                embeddingCount: 32,
                scenarioCount: 4,
                textCountPerBatch: 16
            )
        )
    }

    func testScorerRejectsFailedMarginWithoutRetainingRawValues() throws {
        let taskSet = try loadCanonicalTaskSet()
        var vectors = syntheticVectors(taskSet: taskSet)
        let scenario = try XCTUnwrap(taskSet.scenarios.first)
        vectors[scenario.positiveId] = vectors[scenario.hardNegativeId]

        XCTAssertThrowsError(
            try OllamaEmbeddingSemanticScorer.assess(
                taskSet: taskSet,
                firstEmbeddings: orderedVectors(
                    ids: taskSet.firstCall.map(\.id),
                    vectors: vectors
                ),
                secondEmbeddings: orderedVectors(
                    ids: taskSet.secondCallOrder,
                    vectors: vectors
                )
            )
        ) { error in
            XCTAssertEqual(
                error as? OllamaEmbeddingSemanticQualityError,
                .positiveMarginFailed(scenarioID: scenario.id)
            )
            let diagnostic = String(describing: error)
            XCTAssertFalse(diagnostic.contains(scenario.queryId))
            XCTAssertFalse(
                diagnostic.contains(
                    taskSet.firstCall.first(where: {
                        $0.id == scenario.queryId
                    })?.text ?? "query-canary"
                )
            )
        }
    }

    func testScorerRejectsRepeatabilityDriftAfterPermutation() throws {
        let taskSet = try loadCanonicalTaskSet()
        let vectors = syntheticVectors(taskSet: taskSet)
        var secondVectors = vectors
        let inputID = try XCTUnwrap(
            taskSet.scenarios.first?.unrelatedNegativeId
        )
        secondVectors[inputID] = Array(
            repeating: 1,
            count: try XCTUnwrap(vectors[inputID]).count
        )

        XCTAssertThrowsError(
            try OllamaEmbeddingSemanticScorer.assess(
                taskSet: taskSet,
                firstEmbeddings: orderedVectors(
                    ids: taskSet.firstCall.map(\.id),
                    vectors: vectors
                ),
                secondEmbeddings: orderedVectors(
                    ids: taskSet.secondCallOrder,
                    vectors: secondVectors
                )
            )
        ) { error in
            XCTAssertEqual(
                error as? OllamaEmbeddingSemanticQualityError,
                .repeatabilityFailed(inputID: inputID)
            )
        }
    }

    func testScorerRejectsInvalidCountDimensionAndValues() throws {
        let taskSet = try loadCanonicalTaskSet()
        let vectors = syntheticVectors(taskSet: taskSet)
        let firstOrder = taskSet.firstCall.map(\.id)
        let validFirst = orderedVectors(ids: firstOrder, vectors: vectors)
        let validSecond = orderedVectors(
            ids: taskSet.secondCallOrder,
            vectors: vectors
        )

        var short = validFirst
        short.removeLast()
        var mismatchedDimension = validFirst
        mismatchedDimension[0].append(0)
        var zeroNorm = validFirst
        zeroNorm[0] = Array(repeating: 0, count: zeroNorm[0].count)

        let cases: [(
            [[Double]],
            OllamaEmbeddingSemanticQualityError
        )] = [
            (short, .invalidEmbeddingShape),
            (mismatchedDimension, .invalidEmbeddingShape),
            (zeroNorm, .invalidEmbeddingValue),
        ]
        for (input, expectedError) in cases {
            XCTAssertThrowsError(
                try OllamaEmbeddingSemanticScorer.assess(
                    taskSet: taskSet,
                    firstEmbeddings: input,
                    secondEmbeddings: validSecond
                )
            ) { error in
                XCTAssertEqual(
                    error as? OllamaEmbeddingSemanticQualityError,
                    expectedError
                )
            }
        }
        for value in [Double.nan, .infinity, -.infinity] {
            var nonFinite = validFirst
            nonFinite[0][0] = value
            XCTAssertThrowsError(
                try OllamaEmbeddingSemanticScorer.assess(
                    taskSet: taskSet,
                    firstEmbeddings: nonFinite,
                    secondEmbeddings: validSecond
                )
            ) { error in
                XCTAssertEqual(
                    error as? OllamaEmbeddingSemanticQualityError,
                    .invalidEmbeddingValue
                )
            }
        }
    }

    func testBasisPointThresholdsDoNotRoundIntoFalsePasses() {
        XCTAssertFalse(
            OllamaEmbeddingSemanticScorer.passesBasisPointMinimum(
                0.0199,
                minimum: 200
            )
        )
        XCTAssertTrue(
            OllamaEmbeddingSemanticScorer.passesBasisPointMinimum(
                0.02,
                minimum: 200
            )
        )
        XCTAssertFalse(
            OllamaEmbeddingSemanticScorer.passesBasisPointMinimum(
                0.9989,
                minimum: 9_990
            )
        )
        XCTAssertTrue(
            OllamaEmbeddingSemanticScorer.passesBasisPointMinimum(
                0.999,
                minimum: 9_990
            )
        )
    }

    private func loadCanonicalTaskSet() throws
        -> OllamaEmbeddingSemanticTaskSet {
        try OllamaEmbeddingSemanticTaskSet.load(
            from: canonicalTaskSetURL(),
            expectedSHA256: (
                OllamaEmbeddingSemanticTaskSet.recordedSHA256
            )
        )
    }

    private func canonicalTaskSetURL() -> URL {
        var root = URL(fileURLWithPath: #filePath)
        for _ in 0..<5 {
            root.deleteLastPathComponent()
        }
        return root
            .appending(path: "shared")
            .appending(path: "evaluation")
            .appending(
                path: "ollama-embedding-semantic-quality-v1.json"
            )
    }

    private func syntheticVectors(
        taskSet: OllamaEmbeddingSemanticTaskSet
    ) -> [String: [Double]] {
        let dimension = taskSet.scenarios.count * 3
        var vectors: [String: [Double]] = [:]
        for (index, scenario) in taskSet.scenarios.enumerated() {
            var positiveAxis = Array(repeating: 0.0, count: dimension)
            positiveAxis[index * 3] = 1
            var hardNegativeAxis = Array(
                repeating: 0.0,
                count: dimension
            )
            hardNegativeAxis[index * 3 + 1] = 1
            var unrelatedAxis = Array(
                repeating: 0.0,
                count: dimension
            )
            unrelatedAxis[index * 3 + 2] = 1
            vectors[scenario.queryId] = positiveAxis
            vectors[scenario.positiveId] = positiveAxis
            vectors[scenario.hardNegativeId] = hardNegativeAxis
            vectors[scenario.unrelatedNegativeId] = unrelatedAxis
        }
        return vectors
    }

    private func orderedVectors(
        ids: [String],
        vectors: [String: [Double]]
    ) -> [[Double]] {
        ids.compactMap { vectors[$0] }
    }
}
