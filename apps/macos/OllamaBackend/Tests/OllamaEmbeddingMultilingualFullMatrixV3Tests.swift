import Foundation
@testable import OllamaBackend
import XCTest

enum OllamaEmbeddingMultilingualFullMatrixV3Error:
    Error,
    Equatable
{
    case invalidEmbeddingShape
    case invalidEmbeddingValue
    case invalidLiveState
}

struct OllamaEmbeddingMultilingualFullMatrixV3BatchFailure:
    Codable,
    Equatable
{
    let batchOrdinal: Int
    let comparisonFailureCount: Int
}

struct OllamaEmbeddingMultilingualFullMatrixV3RankingFailure:
    Codable,
    Equatable
{
    let failedBatches: [
        OllamaEmbeddingMultilingualFullMatrixV3BatchFailure
    ]
    let locale: String
    let scenarioOrdinalWithinLocale: Int
}

struct OllamaEmbeddingMultilingualFullMatrixV3RepeatabilityFailure:
    Codable,
    Equatable
{
    let inputOrdinalWithinLocale: Int
    let locale: String
}

struct OllamaEmbeddingMultilingualFullMatrixV3Observation:
    Codable,
    Equatable
{
    static let diagnosticPrefix = (
        "AETHERLINK_OLLAMA_MULTILINGUAL_FULL_MATRIX_V3="
    )

    let rankingFailures: [
        OllamaEmbeddingMultilingualFullMatrixV3RankingFailure
    ]
    let repeatabilityFailures: [
        OllamaEmbeddingMultilingualFullMatrixV3RepeatabilityFailure
    ]
    let schemaVersion: Int

    func canonicalDiagnostic() throws -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let data = try encoder.encode(self)
        guard let body = String(data: data, encoding: .utf8) else {
            throw OllamaEmbeddingMultilingualFullMatrixV3Error
                .invalidEmbeddingValue
        }
        return Self.diagnosticPrefix + body
    }
}

enum OllamaEmbeddingMultilingualFullMatrixV3Scorer {
    static func assess(
        taskSet: OllamaEmbeddingMultilingualSemanticTaskSet,
        firstEmbeddings: [[Double]],
        secondEmbeddings: [[Double]]
    ) throws -> OllamaEmbeddingMultilingualFullMatrixV3Observation {
        let first = try validatedEmbeddingMap(
            ids: taskSet.firstCall.map(\.id),
            embeddings: firstEmbeddings,
            expectedCount: taskSet.firstCall.count,
            expectedDimension: nil
        )
        let dimension = try requiredDimension(first)
        let second = try validatedEmbeddingMap(
            ids: taskSet.secondCallOrder,
            embeddings: secondEmbeddings,
            expectedCount: taskSet.firstCall.count,
            expectedDimension: dimension
        )

        var rankingFailures: [
            OllamaEmbeddingMultilingualFullMatrixV3RankingFailure
        ] = []
        var scenarioOrdinalsByLocale: [String: Int] = [:]
        for scenario in taskSet.scenarios {
            let ordinal = (
                scenarioOrdinalsByLocale[scenario.locale, default: 0] + 1
            )
            scenarioOrdinalsByLocale[scenario.locale] = ordinal
            var failedBatches: [
                OllamaEmbeddingMultilingualFullMatrixV3BatchFailure
            ] = []
            for (batchOrdinal, embeddings) in [
                (1, first),
                (2, second),
            ] {
                var failureCount = 0
                for margin in try rankingMargins(
                    scenario: scenario,
                    embeddings: embeddings
                ) {
                    if !passesBasisPointMinimum(
                        margin,
                        minimum: taskSet
                            .minimumPositiveMarginBasisPoints
                    ) {
                        failureCount += 1
                    }
                }
                if failureCount > 0 {
                    failedBatches.append(
                        OllamaEmbeddingMultilingualFullMatrixV3BatchFailure(
                            batchOrdinal: batchOrdinal,
                            comparisonFailureCount: failureCount
                        )
                    )
                }
            }
            if !failedBatches.isEmpty {
                rankingFailures.append(
                    OllamaEmbeddingMultilingualFullMatrixV3RankingFailure(
                        failedBatches: failedBatches,
                        locale: scenario.locale,
                        scenarioOrdinalWithinLocale: ordinal
                    )
                )
            }
        }

        var repeatabilityFailures: [
            OllamaEmbeddingMultilingualFullMatrixV3RepeatabilityFailure
        ] = []
        var inputOrdinalsByLocale: [String: Int] = [:]
        for input in taskSet.firstCall {
            let ordinal = (
                inputOrdinalsByLocale[input.locale, default: 0] + 1
            )
            inputOrdinalsByLocale[input.locale] = ordinal
            guard
                let firstVector = first[input.id],
                let secondVector = second[input.id]
            else {
                throw OllamaEmbeddingMultilingualFullMatrixV3Error
                    .invalidEmbeddingShape
            }
            if !passesBasisPointMinimum(
                try cosine(firstVector, secondVector),
                minimum: taskSet.minimumRepeatCosineBasisPoints
            ) {
                repeatabilityFailures.append(
                    OllamaEmbeddingMultilingualFullMatrixV3RepeatabilityFailure(
                        inputOrdinalWithinLocale: ordinal,
                        locale: input.locale
                    )
                )
            }
        }

        return OllamaEmbeddingMultilingualFullMatrixV3Observation(
            rankingFailures: rankingFailures,
            repeatabilityFailures: repeatabilityFailures,
            schemaVersion: 1
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
        expectedCount: Int,
        expectedDimension: Int?
    ) throws -> [String: [Double]] {
        guard
            ids.count == expectedCount,
            embeddings.count == expectedCount,
            Set(ids).count == expectedCount,
            let observedDimension = embeddings.first?.count,
            observedDimension > 0,
            expectedDimension == nil
                || expectedDimension == observedDimension
        else {
            throw OllamaEmbeddingMultilingualFullMatrixV3Error
                .invalidEmbeddingShape
        }
        for vector in embeddings {
            guard vector.count == observedDimension else {
                throw OllamaEmbeddingMultilingualFullMatrixV3Error
                    .invalidEmbeddingShape
            }
            guard
                vector.allSatisfy(\.isFinite),
                vector.contains(where: { $0 != 0 })
            else {
                throw OllamaEmbeddingMultilingualFullMatrixV3Error
                    .invalidEmbeddingValue
            }
        }
        return Dictionary(uniqueKeysWithValues: zip(ids, embeddings))
    }

    private static func requiredDimension(
        _ embeddings: [String: [Double]]
    ) throws -> Int {
        guard let dimension = embeddings.values.first?.count else {
            throw OllamaEmbeddingMultilingualFullMatrixV3Error
                .invalidEmbeddingShape
        }
        return dimension
    }

    private static func rankingMargins(
        scenario: OllamaEmbeddingMultilingualSemanticTaskSet.Scenario,
        embeddings: [String: [Double]]
    ) throws -> [Double] {
        guard
            let query = embeddings[scenario.queryId],
            let positive = embeddings[scenario.positiveId],
            let hardNegative = embeddings[scenario.hardNegativeId],
            let unrelatedNegative = embeddings[
                scenario.unrelatedNegativeId
            ]
        else {
            throw OllamaEmbeddingMultilingualFullMatrixV3Error
                .invalidEmbeddingShape
        }
        let positiveCosine = try cosine(query, positive)
        return [
            positiveCosine - (try cosine(query, hardNegative)),
            positiveCosine - (try cosine(query, unrelatedNegative)),
        ]
    }

    private static func cosine(
        _ lhs: [Double],
        _ rhs: [Double]
    ) throws -> Double {
        guard lhs.count == rhs.count, !lhs.isEmpty else {
            throw OllamaEmbeddingMultilingualFullMatrixV3Error
                .invalidEmbeddingShape
        }
        guard
            let lhsScale = lhs.lazy.map({ abs($0) }).max(),
            let rhsScale = rhs.lazy.map({ abs($0) }).max(),
            lhsScale.isFinite,
            rhsScale.isFinite,
            lhsScale > 0,
            rhsScale > 0
        else {
            throw OllamaEmbeddingMultilingualFullMatrixV3Error
                .invalidEmbeddingValue
        }
        var dot = 0.0
        var lhsNormSquared = 0.0
        var rhsNormSquared = 0.0
        for (left, right) in zip(lhs, rhs) {
            let scaledLeft = left / lhsScale
            let scaledRight = right / rhsScale
            dot += scaledLeft * scaledRight
            lhsNormSquared += scaledLeft * scaledLeft
            rhsNormSquared += scaledRight * scaledRight
        }
        let denominator = sqrt(lhsNormSquared) * sqrt(rhsNormSquared)
        let value = dot / denominator
        guard
            dot.isFinite,
            lhsNormSquared.isFinite,
            rhsNormSquared.isFinite,
            denominator.isFinite,
            denominator > 0,
            value.isFinite
        else {
            throw OllamaEmbeddingMultilingualFullMatrixV3Error
                .invalidEmbeddingValue
        }
        return max(-1, min(1, value))
    }
}

final class OllamaEmbeddingMultilingualFullMatrixV3Tests:
    XCTestCase
{
    func testAllPassObservationEvaluatesTheCompleteMatrix() throws {
        let taskSet = try loadCanonicalTaskSet()
        let vectors = syntheticVectors(taskSet: taskSet)

        let observation = try score(
            taskSet: taskSet,
            firstVectors: vectors,
            secondVectors: vectors
        )

        XCTAssertTrue(observation.rankingFailures.isEmpty)
        XCTAssertTrue(observation.repeatabilityFailures.isEmpty)
    }

    func testFailuresDoNotShortCircuitLaterLocalesOrRepeatability()
        throws
    {
        let taskSet = try loadCanonicalTaskSet()
        var firstVectors = syntheticVectors(taskSet: taskSet)
        var secondVectors = firstVectors
        let koreanScenario = try XCTUnwrap(
            taskSet.scenarios.filter({ $0.locale == "ko" }).dropFirst()
                .first
        )
        let japaneseScenario = try XCTUnwrap(
            taskSet.scenarios.filter({ $0.locale == "ja" }).last
        )
        firstVectors[koreanScenario.positiveId] = firstVectors[
            koreanScenario.hardNegativeId
        ]
        for scenario in [koreanScenario, japaneseScenario] {
            secondVectors[scenario.positiveId] = secondVectors[
                scenario.hardNegativeId
            ]
        }
        let frenchRepeatInputID = try XCTUnwrap(
            taskSet.scenarios.filter({ $0.locale == "fr" }).last?
                .unrelatedNegativeId
        )
        secondVectors[frenchRepeatInputID] = try XCTUnwrap(
            secondVectors[frenchRepeatInputID]
        ).map { -$0 }

        let observation = try score(
            taskSet: taskSet,
            firstVectors: firstVectors,
            secondVectors: secondVectors
        )

        XCTAssertEqual(observation.rankingFailures, [
            OllamaEmbeddingMultilingualFullMatrixV3RankingFailure(
                failedBatches: [
                    .init(
                        batchOrdinal: 1,
                        comparisonFailureCount: 2
                    ),
                    .init(
                        batchOrdinal: 2,
                        comparisonFailureCount: 2
                    ),
                ],
                locale: "ko",
                scenarioOrdinalWithinLocale: 2
            ),
            OllamaEmbeddingMultilingualFullMatrixV3RankingFailure(
                failedBatches: [
                    .init(
                        batchOrdinal: 2,
                        comparisonFailureCount: 2
                    ),
                ],
                locale: "ja",
                scenarioOrdinalWithinLocale: 4
            ),
        ])
        XCTAssertEqual(observation.repeatabilityFailures, [
            OllamaEmbeddingMultilingualFullMatrixV3RepeatabilityFailure(
                inputOrdinalWithinLocale: 14,
                locale: "ja"
            ),
            OllamaEmbeddingMultilingualFullMatrixV3RepeatabilityFailure(
                inputOrdinalWithinLocale: 16,
                locale: "fr"
            ),
        ])
    }

    func testDiagnosticIsClosedBoundedAndNonretaining() throws {
        let taskSet = try loadCanonicalTaskSet()
        var vectors = syntheticVectors(taskSet: taskSet)
        for scenario in taskSet.scenarios {
            vectors[scenario.positiveId] = vectors[
                scenario.hardNegativeId
            ]
        }

        let observation = try score(
            taskSet: taskSet,
            firstVectors: vectors,
            secondVectors: vectors
        )
        let diagnostic = try observation.canonicalDiagnostic()

        XCTAssertEqual(observation.rankingFailures.count, 20)
        XCTAssertEqual(
            observation.rankingFailures.flatMap(\.failedBatches)
                .reduce(0) { $0 + $1.comparisonFailureCount },
            80
        )
        XCTAssertLessThanOrEqual(
            observation.rankingFailures.count,
            OllamaEmbeddingMultilingualSemanticTaskSet.scenarioCount
        )
        XCTAssertLessThanOrEqual(
            observation.repeatabilityFailures.count,
            OllamaEmbeddingMultilingualSemanticTaskSet.textCount
        )
        XCTAssertTrue(diagnostic.hasPrefix(
            OllamaEmbeddingMultilingualFullMatrixV3Observation
                .diagnosticPrefix
        ))
        XCTAssertFalse(diagnostic.contains("\"text\""))
        XCTAssertFalse(diagnostic.contains("\"score\""))
        XCTAssertFalse(diagnostic.contains("\"model\""))
        XCTAssertFalse(diagnostic.contains("\"path\""))
        for input in taskSet.firstCall {
            XCTAssertFalse(diagnostic.contains(input.id))
            XCTAssertFalse(diagnostic.contains(input.text))
        }
        for scenario in taskSet.scenarios {
            XCTAssertFalse(diagnostic.contains(scenario.id))
        }
    }

    func testInvalidShapeAndValuesRemainFatal() throws {
        let taskSet = try loadCanonicalTaskSet()
        let vectors = syntheticVectors(taskSet: taskSet)
        let first = orderedVectors(
            ids: taskSet.firstCall.map(\.id),
            vectors: vectors
        )
        let second = orderedVectors(
            ids: taskSet.secondCallOrder,
            vectors: vectors
        )
        var firstShort = first
        firstShort.removeLast()
        var firstRagged = first
        firstRagged[0].append(0)
        var firstNonfinite = first
        firstNonfinite[0][0] = .infinity
        var firstZero = first
        firstZero[0] = Array(
            repeating: 0,
            count: firstZero[0].count
        )
        var secondShort = second
        secondShort.removeLast()
        var secondRagged = second
        secondRagged[0].append(0)
        let secondDimensionMismatch = second.map { $0 + [0] }
        let cases: [(
            [[Double]],
            [[Double]],
            OllamaEmbeddingMultilingualFullMatrixV3Error
        )] = [
            (firstShort, second, .invalidEmbeddingShape),
            (firstRagged, second, .invalidEmbeddingShape),
            (firstNonfinite, second, .invalidEmbeddingValue),
            (firstZero, second, .invalidEmbeddingValue),
            (first, secondShort, .invalidEmbeddingShape),
            (first, secondRagged, .invalidEmbeddingShape),
            (first, secondDimensionMismatch, .invalidEmbeddingShape),
        ]

        for (firstInput, secondInput, expectedError) in cases {
            XCTAssertThrowsError(
                try OllamaEmbeddingMultilingualFullMatrixV3Scorer
                    .assess(
                        taskSet: taskSet,
                        firstEmbeddings: firstInput,
                        secondEmbeddings: secondInput
                    )
            ) { error in
                XCTAssertEqual(
                    error as?
                        OllamaEmbeddingMultilingualFullMatrixV3Error,
                    expectedError
                )
            }
        }
    }

    func testBasisPointThresholdsAreInclusiveAndExact() {
        XCTAssertFalse(
            OllamaEmbeddingMultilingualFullMatrixV3Scorer
                .passesBasisPointMinimum(0.0199, minimum: 200)
        )
        XCTAssertTrue(
            OllamaEmbeddingMultilingualFullMatrixV3Scorer
                .passesBasisPointMinimum(0.02, minimum: 200)
        )
        XCTAssertFalse(
            OllamaEmbeddingMultilingualFullMatrixV3Scorer
                .passesBasisPointMinimum(0.9989, minimum: 9_990)
        )
        XCTAssertTrue(
            OllamaEmbeddingMultilingualFullMatrixV3Scorer
                .passesBasisPointMinimum(0.999, minimum: 9_990)
        )
        XCTAssertFalse(
            OllamaEmbeddingMultilingualFullMatrixV3Scorer
                .passesBasisPointMinimum(.infinity, minimum: 200)
        )
        XCTAssertFalse(
            OllamaEmbeddingMultilingualFullMatrixV3Scorer
                .passesBasisPointMinimum(1, minimum: -1)
        )
    }

    func testLargestFiniteComponentsDoNotOverflowCosine() throws {
        let taskSet = try loadCanonicalTaskSet()
        var vectors = syntheticVectors(taskSet: taskSet)
        for key in vectors.keys {
            vectors[key] = try XCTUnwrap(vectors[key]).map {
                $0 * Double.greatestFiniteMagnitude
            }
        }

        let observation = try score(
            taskSet: taskSet,
            firstVectors: vectors,
            secondVectors: vectors
        )

        XCTAssertTrue(observation.rankingFailures.isEmpty)
        XCTAssertTrue(observation.repeatabilityFailures.isEmpty)
    }

    func testCleanupErrorPrecedesPrimaryError() {
        enum MarkerError: Error {
            case cleanup
            case primary
        }

        XCTAssertThrowsError(
            try Self.primaryValueAfterCleanup(
                primary: Result<Int, Error>.failure(
                    MarkerError.primary
                ),
                cleanup: Result<Void, Error>.failure(
                    MarkerError.cleanup
                )
            )
        ) { error in
            guard case MarkerError.cleanup = error else {
                return XCTFail("Cleanup error did not take precedence.")
            }
        }
    }

    func testLiveOllamaExactVersionInstalledEmbeddingMultilingualFullMatrixObservationV3()
        async throws
    {
        let environment = ProcessInfo.processInfo.environment
        let enableKey = (
            "AETHERLINK_RUN_OLLAMA_LIVE_EMBEDDING_MULTILINGUAL_"
                + "FULL_MATRIX_V3_TEST"
        )
        guard environment[enableKey] == "1" else {
            throw XCTSkip(
                "Set \(enableKey)=1 to enable the isolated multilingual full-matrix V3 observation."
            )
        }
        let fixture = try liveFixture(environment: environment)
        let backend = fixture.backend
        let modelID = fixture.modelID

        var catalogIdentityBefore: [String]?
        let primary: Result<
            OllamaEmbeddingMultilingualFullMatrixV3Observation,
            Error
        >
        do {
            let taskSet = try liveTaskSet(environment: environment)
            guard await backend.healthCheck() == .available else {
                throw OllamaEmbeddingMultilingualFullMatrixV3Error
                    .invalidLiveState
            }
            let catalog = try await backend.listModels()
            guard
                catalog.count == fixture.expectedCatalogCount,
                let selected = catalog.first(where: {
                    Self.sameOllamaModel($0.id, modelID)
                }),
                selected.installed,
                !selected.running,
                selected.kind == .embedding,
                selected.embeddingInputProfile == .embeddingGemma
            else {
                throw OllamaEmbeddingMultilingualFullMatrixV3Error
                    .invalidLiveState
            }
            catalogIdentityBefore = catalog.map(\.id).sorted()
            let first = try await backend.embed(
                request: EmbeddingRequest(
                    model: modelID,
                    inputs: taskSet.firstCallInputs
                )
            )
            let second = try await backend.embed(
                request: EmbeddingRequest(
                    model: modelID,
                    inputs: taskSet.secondCallInputs
                )
            )
            guard
                Self.sameOllamaModel(first.model, modelID),
                Self.sameOllamaModel(second.model, modelID),
                first.embeddingInputProfile == .embeddingGemma,
                second.embeddingInputProfile == .embeddingGemma
            else {
                throw OllamaEmbeddingMultilingualFullMatrixV3Error
                    .invalidLiveState
            }
            primary = .success(
                try OllamaEmbeddingMultilingualFullMatrixV3Scorer
                    .assess(
                        taskSet: taskSet,
                        firstEmbeddings: first.embeddings,
                        secondEmbeddings: second.embeddings
                    )
            )
        } catch {
            primary = .failure(error)
        }

        let primarySucceeded: Bool
        switch primary {
        case .success:
            primarySucceeded = true
        case .failure:
            primarySucceeded = false
        }
        var cleanupError: Error?
        do {
            let unload = try await backend.unloadModel(
                providerModelID: modelID
            )
            guard
                unload.unloaded,
                !primarySucceeded || unload.outcome == .confirmed
            else {
                throw OllamaEmbeddingMultilingualFullMatrixV3Error
                    .invalidLiveState
            }
        } catch {
            cleanupError = error
        }
        do {
            let catalog = try await backend.listModels()
            guard
                catalog.count == fixture.expectedCatalogCount,
                catalogIdentityBefore == nil
                    || catalog.map(\.id).sorted()
                        == catalogIdentityBefore,
                let selected = catalog.first(where: {
                    Self.sameOllamaModel($0.id, modelID)
                }),
                selected.installed,
                !selected.running
            else {
                throw OllamaEmbeddingMultilingualFullMatrixV3Error
                    .invalidLiveState
            }
        } catch {
            if cleanupError == nil {
                cleanupError = error
            }
        }
        if await backend.healthCheck() != .available,
            cleanupError == nil
        {
            cleanupError = (
                OllamaEmbeddingMultilingualFullMatrixV3Error
                    .invalidLiveState
            )
        }
        let cleanup: Result<Void, Error> = cleanupError.map {
            .failure($0)
        } ?? .success(())
        let observation = try Self.primaryValueAfterCleanup(
            primary: primary,
            cleanup: cleanup
        )
        print(try observation.canonicalDiagnostic())
    }

    private struct LiveFixture {
        let backend: OllamaBackend
        let expectedCatalogCount: Int
        let modelID: String
    }

    private enum LiveFixtureError: Error {
        case invalidBoundary
        case invalidEnvironment
    }

    private func liveFixture(
        environment: [String: String]
    ) throws -> LiveFixture {
        guard
            let baseURLValue = environment[
                "AETHERLINK_OLLAMA_LIVE_BASE_URL"
            ],
            let baseURL = URL(string: baseURLValue),
            let modelID = environment[
                "AETHERLINK_OLLAMA_LIVE_EMBEDDING_MODEL_ID"
            ],
            let expectedCatalogCountValue = environment[
                "AETHERLINK_OLLAMA_LIVE_EXPECTED_CATALOG_COUNT"
            ],
            let expectedCatalogCount = Int(expectedCatalogCountValue),
            String(expectedCatalogCount) == expectedCatalogCountValue
        else {
            XCTFail("Missing runner-owned V3 full-matrix fixture inputs.")
            throw LiveFixtureError.invalidEnvironment
        }
        guard
            baseURL.scheme == "http",
            baseURL.host == "127.0.0.1",
            let port = baseURL.port,
            port != 11_434,
            baseURL.user == nil,
            baseURL.password == nil,
            baseURL.query == nil,
            baseURL.fragment == nil,
            baseURL.path.isEmpty || baseURL.path == "/",
            (1...ModelInfo.maximumCatalogModelCount).contains(
                expectedCatalogCount
            ),
            !modelID.isEmpty,
            modelID.utf8.count <= 1_024,
            modelID.unicodeScalars.allSatisfy({
                $0.value >= 0x20 && $0.value != 0x7f
            })
        else {
            XCTFail("The V3 full-matrix fixture boundary was invalid.")
            throw LiveFixtureError.invalidBoundary
        }

        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 120
        configuration.timeoutIntervalForResource = 180
        let session = URLSession(configuration: configuration)
        return LiveFixture(
            backend: OllamaBackend(baseURL: baseURL, session: session),
            expectedCatalogCount: expectedCatalogCount,
            modelID: modelID
        )
    }

    private func liveTaskSet(
        environment: [String: String]
    ) throws -> OllamaEmbeddingMultilingualSemanticTaskSet {
        guard
            let path = environment[
                "AETHERLINK_OLLAMA_EMBEDDING_MULTILINGUAL_"
                    + "SEMANTIC_TASK_SET_PATH"
            ],
            path.hasPrefix("/"),
            let sha256 = environment[
                "AETHERLINK_OLLAMA_EMBEDDING_MULTILINGUAL_"
                    + "SEMANTIC_TASK_SET_SHA256"
            ]
        else {
            XCTFail("Missing runner-owned V3 full-matrix task set.")
            throw LiveFixtureError.invalidEnvironment
        }
        let url = URL(
            fileURLWithPath: path,
            isDirectory: false
        ).standardizedFileURL
        guard
            url.lastPathComponent
                == "ollama-embedding-multilingual-semantic-quality-v2.json"
        else {
            XCTFail("The V3 full-matrix task set escaped its boundary.")
            throw LiveFixtureError.invalidBoundary
        }
        return try OllamaEmbeddingMultilingualSemanticTaskSet.load(
            from: url,
            expectedSHA256: sha256
        )
    }

    private func score(
        taskSet: OllamaEmbeddingMultilingualSemanticTaskSet,
        firstVectors: [String: [Double]],
        secondVectors: [String: [Double]]
    ) throws -> OllamaEmbeddingMultilingualFullMatrixV3Observation {
        try OllamaEmbeddingMultilingualFullMatrixV3Scorer.assess(
            taskSet: taskSet,
            firstEmbeddings: orderedVectors(
                ids: taskSet.firstCall.map(\.id),
                vectors: firstVectors
            ),
            secondEmbeddings: orderedVectors(
                ids: taskSet.secondCallOrder,
                vectors: secondVectors
            )
        )
    }

    private func loadCanonicalTaskSet() throws
        -> OllamaEmbeddingMultilingualSemanticTaskSet
    {
        try OllamaEmbeddingMultilingualSemanticTaskSet.load(
            from: canonicalTaskSetURL(),
            expectedSHA256: (
                OllamaEmbeddingMultilingualSemanticTaskSet.recordedSHA256
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
                path: (
                    "ollama-embedding-multilingual-semantic-quality-v2.json"
                )
            )
    }

    private func syntheticVectors(
        taskSet: OllamaEmbeddingMultilingualSemanticTaskSet
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

    private static func primaryValueAfterCleanup<Value>(
        primary: Result<Value, Error>,
        cleanup: Result<Void, Error>
    ) throws -> Value {
        try cleanup.get()
        return try primary.get()
    }

    private static func sameOllamaModel(
        _ lhs: String,
        _ rhs: String
    ) -> Bool {
        func canonical(_ value: String) -> String {
            value.hasSuffix(":latest")
                ? String(value.dropLast(":latest".count))
                : value
        }
        return lhs == rhs || canonical(lhs) == canonical(rhs)
    }
}
