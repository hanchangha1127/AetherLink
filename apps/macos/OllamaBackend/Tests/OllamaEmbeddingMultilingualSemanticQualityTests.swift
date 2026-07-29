import CryptoKit
import Foundation
@testable import OllamaBackend
import XCTest

enum OllamaEmbeddingMultilingualSemanticQualityError: Error, Equatable {
    case invalidTaskSet
    case invalidEmbeddingShape
    case invalidEmbeddingValue
    case positiveMarginFailed(
        locale: String,
        scenarioOrdinalWithinLocale: Int
    )
    case repeatabilityFailed(
        locale: String,
        inputOrdinalWithinLocale: Int
    )
}

struct OllamaEmbeddingMultilingualSemanticTaskSet: Decodable {
    struct Input: Decodable {
        let id: String
        let locale: String
        let text: String
    }

    struct Scenario: Decodable {
        let hardNegativeId: String
        let id: String
        let locale: String
        let positiveId: String
        let queryId: String
        let unrelatedNegativeId: String
    }

    static let fixtureID = (
        "aetherlink-ollama-embedding-multilingual-semantic-task-set-v2"
    )
    static let recordedSHA256 = (
        "a4dde8d94f661fe9682103875ed53db703761722c19ec32b35ceba72ecae2e31"
    )
    static let supportedLocales = ["en", "ko", "ja", "zh-CN", "fr"]
    static let localeSlugs = [
        "en": "en",
        "ko": "ko",
        "ja": "ja",
        "zh-CN": "zh-cn",
        "fr": "fr",
    ]
    static let minimumPositiveMarginBasisPoints = 200
    static let minimumRepeatCosineBasisPoints = 9_990
    static let scenariosPerLocale = 4
    static let textsPerLocale = 16
    static let scenarioCount = 20
    static let textCount = 80
    static let secondCallOrderPolicy = "reverse-first-call"

    let firstCall: [Input]
    let fixtureId: String
    let locales: [String]
    let minimumPositiveMarginBasisPoints: Int
    let minimumRepeatCosineBasisPoints: Int
    let scenarios: [Scenario]
    let schemaVersion: Int
    let secondCallOrderPolicy: String

    static func load(
        from url: URL,
        expectedSHA256: String
    ) throws -> Self {
        guard expectedSHA256 == recordedSHA256 else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidTaskSet
        }
        let data = try Data(contentsOf: url, options: [.mappedIfSafe])
        let digest = SHA256.hash(data: data).map {
            String(format: "%02x", $0)
        }.joined()
        guard digest == expectedSHA256 else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidTaskSet
        }
        return try decodeValidated(data)
    }

    static func decodeValidated(_ data: Data) throws -> Self {
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
                "locales",
                "minimumPositiveMarginBasisPoints",
                "minimumRepeatCosineBasisPoints",
                "scenarios",
                "schemaVersion",
                "secondCallOrderPolicy",
            ],
            let firstCall = root["firstCall"] as? [[String: Any]],
            firstCall.allSatisfy({
                Set($0.keys) == ["id", "locale", "text"]
            }),
            let scenarios = root["scenarios"] as? [[String: Any]],
            scenarios.allSatisfy({
                Set($0.keys) == [
                    "hardNegativeId",
                    "id",
                    "locale",
                    "positiveId",
                    "queryId",
                    "unrelatedNegativeId",
                ]
            })
        else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidTaskSet
        }
    }

    private func validate() throws {
        guard
            fixtureId == Self.fixtureID,
            schemaVersion == 2,
            locales == Self.supportedLocales,
            minimumPositiveMarginBasisPoints
                == Self.minimumPositiveMarginBasisPoints,
            minimumRepeatCosineBasisPoints
                == Self.minimumRepeatCosineBasisPoints,
            scenarios.count == Self.scenarioCount,
            firstCall.count == Self.textCount,
            secondCallOrderPolicy == Self.secondCallOrderPolicy
        else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidTaskSet
        }

        let inputIDs = firstCall.map(\.id)
        let inputsByID = Dictionary(
            uniqueKeysWithValues: firstCall.map { ($0.id, $0) }
        )
        let scenarioIDs = scenarios.map(\.id)
        guard
            inputsByID.count == Self.textCount,
            Set(scenarioIDs).count == Self.scenarioCount,
            firstCall.allSatisfy({ input in
                Self.isBoundedIdentifier(input.id)
                    && Self.isValidLocaleBoundIdentifier(
                        input.id,
                        locale: input.locale
                    )
                    && Self.isValidText(input.text)
            }),
            scenarios.allSatisfy({ scenario in
                Self.isBoundedIdentifier(scenario.id)
                    && Self.isValidLocaleBoundIdentifier(
                        scenario.id,
                        locale: scenario.locale
                    )
            })
        else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidTaskSet
        }

        for locale in Self.supportedLocales {
            guard
                firstCall.filter({ $0.locale == locale }).count
                    == Self.textsPerLocale,
                scenarios.filter({ $0.locale == locale }).count
                    == Self.scenariosPerLocale
            else {
                throw OllamaEmbeddingMultilingualSemanticQualityError
                    .invalidTaskSet
            }
        }

        var referencedIDs: [String] = []
        for scenario in scenarios {
            let roles = [
                scenario.queryId,
                scenario.positiveId,
                scenario.hardNegativeId,
                scenario.unrelatedNegativeId,
            ]
            guard
                Set(roles).count == 4,
                roles.allSatisfy({
                    inputsByID[$0]?.locale == scenario.locale
                })
            else {
                throw OllamaEmbeddingMultilingualSemanticQualityError
                    .invalidTaskSet
            }
            referencedIDs.append(contentsOf: roles)
        }
        guard
            referencedIDs.count == Self.textCount,
            Set(referencedIDs).count == Self.textCount,
            Set(referencedIDs) == Set(inputIDs)
        else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidTaskSet
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

    private static func isValidLocaleBoundIdentifier(
        _ value: String,
        locale: String
    ) -> Bool {
        guard let slug = localeSlugs[locale] else { return false }
        return value.hasPrefix("\(slug)-")
    }

    private static func isValidText(_ value: String) -> Bool {
        guard
            !value.isEmpty,
            value.utf8.count <= 512,
            value.unicodeScalars.elementsEqual(
                value.precomposedStringWithCanonicalMapping.unicodeScalars
            ),
            value == value.trimmingCharacters(
                in: .whitespacesAndNewlines
            )
        else {
            return false
        }
        return value.unicodeScalars.allSatisfy { scalar in
            switch scalar.properties.generalCategory {
            case .control, .format, .surrogate, .privateUse, .unassigned,
                 .lineSeparator, .paragraphSeparator:
                return false
            default:
                return scalar.value == 0x20
                    || !CharacterSet.whitespaces.contains(scalar)
            }
        }
    }

    var firstCallTexts: [String] {
        firstCall.map(\.text)
    }

    var secondCallOrder: [String] {
        firstCall.map(\.id).reversed()
    }

    var secondCallTexts: [String] {
        let textsByID = Dictionary(
            uniqueKeysWithValues: firstCall.map { ($0.id, $0.text) }
        )
        return secondCallOrder.compactMap { textsByID[$0] }
    }
}

struct OllamaEmbeddingMultilingualLocaleAssessment: Equatable {
    let locale: String
    let scenarioCount: Int
    let textCount: Int
}

struct OllamaEmbeddingMultilingualSemanticAssessment: Equatable {
    let batchCalls: Int
    let embeddingCount: Int
    let localeAssessments: [
        OllamaEmbeddingMultilingualLocaleAssessment
    ]
    let scenarioCount: Int
    let textCountPerBatch: Int
}

enum OllamaEmbeddingMultilingualSemanticScorer {
    static func assess(
        taskSet: OllamaEmbeddingMultilingualSemanticTaskSet,
        firstEmbeddings: [[Double]],
        secondEmbeddings: [[Double]]
    ) throws -> OllamaEmbeddingMultilingualSemanticAssessment {
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

        var scenarioOrdinalsByLocale: [String: Int] = [:]
        for scenario in taskSet.scenarios {
            let scenarioOrdinal = (
                scenarioOrdinalsByLocale[scenario.locale, default: 0] + 1
            )
            scenarioOrdinalsByLocale[scenario.locale] = scenarioOrdinal
            try validateRanking(
                scenario: scenario,
                embeddings: first,
                minimumBasisPoints: taskSet
                    .minimumPositiveMarginBasisPoints,
                failureLocale: scenario.locale,
                failureOrdinalWithinLocale: scenarioOrdinal
            )
            try validateRanking(
                scenario: scenario,
                embeddings: second,
                minimumBasisPoints: taskSet
                    .minimumPositiveMarginBasisPoints,
                failureLocale: scenario.locale,
                failureOrdinalWithinLocale: scenarioOrdinal
            )
        }
        var inputOrdinalsByLocale: [String: Int] = [:]
        for input in taskSet.firstCall {
            let inputOrdinal = (
                inputOrdinalsByLocale[input.locale, default: 0] + 1
            )
            inputOrdinalsByLocale[input.locale] = inputOrdinal
            guard
                let firstVector = first[input.id],
                let secondVector = second[input.id],
                passesBasisPointMinimum(
                    try cosine(firstVector, secondVector),
                    minimum: taskSet.minimumRepeatCosineBasisPoints
                )
            else {
                throw OllamaEmbeddingMultilingualSemanticQualityError
                    .repeatabilityFailed(
                        locale: input.locale,
                        inputOrdinalWithinLocale: inputOrdinal
                    )
            }
        }

        return OllamaEmbeddingMultilingualSemanticAssessment(
            batchCalls: 2,
            embeddingCount: (
                firstEmbeddings.count + secondEmbeddings.count
            ),
            localeAssessments: taskSet.locales.map { locale in
                OllamaEmbeddingMultilingualLocaleAssessment(
                    locale: locale,
                    scenarioCount: taskSet.scenarios.filter({
                        $0.locale == locale
                    }).count,
                    textCount: taskSet.firstCall.filter({
                        $0.locale == locale
                    }).count
                )
            },
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
        expectedCount: Int,
        expectedDimension: Int?
    ) throws -> [String: [Double]] {
        guard
            ids.count == expectedCount,
            embeddings.count == expectedCount,
            Set(ids).count == expectedCount,
            let observedDimension = embeddings.first?.count,
            observedDimension > 0,
            expectedDimension == nil || expectedDimension == observedDimension
        else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidEmbeddingShape
        }
        for vector in embeddings {
            guard vector.count == observedDimension else {
                throw OllamaEmbeddingMultilingualSemanticQualityError
                    .invalidEmbeddingShape
            }
            guard
                vector.allSatisfy(\.isFinite),
                let normSquared = finiteDot(vector, vector),
                normSquared > 0
            else {
                throw OllamaEmbeddingMultilingualSemanticQualityError
                    .invalidEmbeddingValue
            }
        }
        return Dictionary(uniqueKeysWithValues: zip(ids, embeddings))
    }

    private static func requiredDimension(
        _ embeddings: [String: [Double]]
    ) throws -> Int {
        guard let dimension = embeddings.values.first?.count else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidEmbeddingShape
        }
        return dimension
    }

    private static func validateRanking(
        scenario: OllamaEmbeddingMultilingualSemanticTaskSet.Scenario,
        embeddings: [String: [Double]],
        minimumBasisPoints: Int,
        failureLocale: String,
        failureOrdinalWithinLocale: Int
    ) throws {
        guard
            let query = embeddings[scenario.queryId],
            let positive = embeddings[scenario.positiveId],
            let hardNegative = embeddings[scenario.hardNegativeId],
            let unrelatedNegative = embeddings[
                scenario.unrelatedNegativeId
            ]
        else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidEmbeddingShape
        }
        let positiveCosine = try cosine(query, positive)
        for negative in [hardNegative, unrelatedNegative] {
            let margin = positiveCosine - (try cosine(query, negative))
            guard passesBasisPointMinimum(
                margin,
                minimum: minimumBasisPoints
            ) else {
                throw OllamaEmbeddingMultilingualSemanticQualityError
                    .positiveMarginFailed(
                        locale: failureLocale,
                        scenarioOrdinalWithinLocale: (
                            failureOrdinalWithinLocale
                        )
                    )
            }
        }
    }

    private static func cosine(
        _ lhs: [Double],
        _ rhs: [Double]
    ) throws -> Double {
        guard lhs.count == rhs.count, !lhs.isEmpty else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidEmbeddingShape
        }
        guard
            let dot = finiteDot(lhs, rhs),
            let lhsNormSquared = finiteDot(lhs, lhs),
            let rhsNormSquared = finiteDot(rhs, rhs),
            lhsNormSquared > 0,
            rhsNormSquared > 0
        else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidEmbeddingValue
        }
        let denominator = sqrt(lhsNormSquared) * sqrt(rhsNormSquared)
        let value = dot / denominator
        guard denominator.isFinite, denominator > 0, value.isFinite else {
            throw OllamaEmbeddingMultilingualSemanticQualityError
                .invalidEmbeddingValue
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

final class OllamaEmbeddingMultilingualSemanticQualityTests:
    XCTestCase
{
    func testCanonicalTaskSetHasRecordedHashAndClosedContract() throws {
        let taskSet = try loadCanonicalTaskSet()

        XCTAssertEqual(
            taskSet.fixtureId,
            OllamaEmbeddingMultilingualSemanticTaskSet.fixtureID
        )
        XCTAssertEqual(
            taskSet.locales,
            OllamaEmbeddingMultilingualSemanticTaskSet.supportedLocales
        )
        XCTAssertEqual(taskSet.scenarios.count, 20)
        XCTAssertEqual(taskSet.firstCall.count, 80)
        XCTAssertEqual(taskSet.secondCallTexts.count, 80)
    }

    func testScorerAcceptsEveryLocaleAcrossBothPermutations() throws {
        let taskSet = try loadCanonicalTaskSet()
        let vectors = syntheticVectors(taskSet: taskSet)

        let assessment = try OllamaEmbeddingMultilingualSemanticScorer
            .assess(
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

        XCTAssertEqual(assessment, expectedAssessment())
    }

    func testScorerRejectsFailedMarginWithoutRetainingRawValues()
        throws
    {
        let taskSet = try loadCanonicalTaskSet()
        var vectors = syntheticVectors(taskSet: taskSet)
        let scenario = try XCTUnwrap(taskSet.scenarios.first)
        vectors[scenario.positiveId] = vectors[scenario.hardNegativeId]

        XCTAssertThrowsError(
            try OllamaEmbeddingMultilingualSemanticScorer.assess(
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
            let scenarioOrdinal = try! XCTUnwrap(
                taskSet.scenarios
                    .filter({ $0.locale == scenario.locale })
                    .firstIndex(where: { $0.id == scenario.id })
            ) + 1
            XCTAssertEqual(
                error as?
                    OllamaEmbeddingMultilingualSemanticQualityError,
                .positiveMarginFailed(
                    locale: scenario.locale,
                    scenarioOrdinalWithinLocale: scenarioOrdinal
                )
            )
            let diagnostic = String(describing: error)
            XCTAssertFalse(diagnostic.contains(scenario.id))
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
            taskSet.scenarios.last?.unrelatedNegativeId
        )
        let input = try XCTUnwrap(
            taskSet.firstCall.first(where: { $0.id == inputID })
        )
        let inputOrdinal = try XCTUnwrap(
            taskSet.firstCall
                .filter({ $0.locale == input.locale })
                .firstIndex(where: { $0.id == inputID })
        ) + 1
        secondVectors[inputID] = Array(
            repeating: 1,
            count: try XCTUnwrap(vectors[inputID]).count
        )

        XCTAssertThrowsError(
            try OllamaEmbeddingMultilingualSemanticScorer.assess(
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
                error as?
                    OllamaEmbeddingMultilingualSemanticQualityError,
                .repeatabilityFailed(
                    locale: input.locale,
                    inputOrdinalWithinLocale: inputOrdinal
                )
            )
            XCTAssertFalse(String(describing: error).contains(inputID))
        }
    }

    func testTaskSetRejectsUnicodeAndLocaleBoundaryMutations()
        throws
    {
        let canonicalData = try Data(contentsOf: canonicalTaskSetURL())
        let canonical = try XCTUnwrap(
            JSONSerialization.jsonObject(with: canonicalData)
                as? [String: Any]
        )
        let mutations: [(String, (inout [String: Any]) -> Void)] = [
            ("unsupported-locale", { value in
                value["locales"] = ["en", "ko", "ja", "zh-CN", "de"]
            }),
            ("non-nfc", { value in
                var rows = value["firstCall"] as! [[String: Any]]
                rows[64]["text"] = "Cafe\u{301}"
                value["firstCall"] = rows
            }),
            ("format-character", { value in
                var rows = value["firstCall"] as! [[String: Any]]
                rows[16]["text"] = "강아지\u{200b}가 달린다."
                value["firstCall"] = rows
            }),
            ("cross-locale-input", { value in
                var rows = value["firstCall"] as! [[String: Any]]
                rows[16]["locale"] = "ja"
                value["firstCall"] = rows
            }),
            ("extra-root-key", { value in
                value["unexpected"] = true
            }),
        ]

        for (label, mutate) in mutations {
            try XCTContext.runActivity(named: label) { _ in
                var value = canonical
                mutate(&value)
                let data = try JSONSerialization.data(
                    withJSONObject: value,
                    options: [.sortedKeys]
                )
                XCTAssertThrowsError(
                    try OllamaEmbeddingMultilingualSemanticTaskSet
                        .decodeValidated(data),
                    "mutation \(label) was accepted"
                )
            }
        }
    }

    func testScorerRejectsInvalidCountDimensionAndValues() throws {
        let taskSet = try loadCanonicalTaskSet()
        let vectors = syntheticVectors(taskSet: taskSet)
        let validFirst = orderedVectors(
            ids: taskSet.firstCall.map(\.id),
            vectors: vectors
        )
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
            OllamaEmbeddingMultilingualSemanticQualityError
        )] = [
            (short, .invalidEmbeddingShape),
            (mismatchedDimension, .invalidEmbeddingShape),
            (zeroNorm, .invalidEmbeddingValue),
        ]
        for (input, expectedError) in cases {
            XCTAssertThrowsError(
                try OllamaEmbeddingMultilingualSemanticScorer.assess(
                    taskSet: taskSet,
                    firstEmbeddings: input,
                    secondEmbeddings: validSecond
                )
            ) { error in
                XCTAssertEqual(
                    error as?
                        OllamaEmbeddingMultilingualSemanticQualityError,
                    expectedError
                )
            }
        }
    }

    func testBasisPointThresholdsDoNotRoundIntoFalsePasses() {
        XCTAssertFalse(
            OllamaEmbeddingMultilingualSemanticScorer
                .passesBasisPointMinimum(0.0199, minimum: 200)
        )
        XCTAssertTrue(
            OllamaEmbeddingMultilingualSemanticScorer
                .passesBasisPointMinimum(0.02, minimum: 200)
        )
        XCTAssertFalse(
            OllamaEmbeddingMultilingualSemanticScorer
                .passesBasisPointMinimum(0.9989, minimum: 9_990)
        )
        XCTAssertTrue(
            OllamaEmbeddingMultilingualSemanticScorer
                .passesBasisPointMinimum(0.999, minimum: 9_990)
        )
    }

    func testLiveOllamaExactVersionInstalledEmbeddingMultilingualSemanticQuality()
        async throws
    {
        let environment = ProcessInfo.processInfo.environment
        let enableKey = (
            "AETHERLINK_RUN_OLLAMA_LIVE_EMBEDDING_MULTILINGUAL_"
            + "SEMANTIC_QUALITY_TEST"
        )
        guard environment[enableKey] == "1" else {
            throw XCTSkip(
                "Set \(enableKey)=1 to enable the isolated multilingual semantic-quality test."
            )
        }
        let fixture = try await liveFixture(environment: environment)
        let taskSet = try liveTaskSet(environment: environment)
        let backend = fixture.backend
        let modelID = fixture.modelID

        let healthBefore = await backend.healthCheck()
        XCTAssertEqual(healthBefore, .available)
        let catalogBefore = try await backend.listModels()
        XCTAssertEqual(catalogBefore.count, fixture.expectedCatalogCount)
        let selectedBefore = try XCTUnwrap(catalogBefore.first(where: {
            Self.sameOllamaModel($0.id, modelID)
        }))
        XCTAssertTrue(selectedBefore.installed)
        XCTAssertFalse(selectedBefore.running)
        XCTAssertEqual(selectedBefore.kind, .embedding)
        let catalogIdentityBefore = catalogBefore.map(\.id).sorted()

        let firstResult = try await backend.embed(
            request: EmbeddingRequest(
                model: modelID,
                texts: taskSet.firstCallTexts
            )
        )
        let secondResult = try await backend.embed(
            request: EmbeddingRequest(
                model: modelID,
                texts: taskSet.secondCallTexts
            )
        )
        XCTAssertTrue(Self.sameOllamaModel(firstResult.model, modelID))
        XCTAssertTrue(Self.sameOllamaModel(secondResult.model, modelID))
        let assessment = try OllamaEmbeddingMultilingualSemanticScorer
            .assess(
                taskSet: taskSet,
                firstEmbeddings: firstResult.embeddings,
                secondEmbeddings: secondResult.embeddings
            )
        XCTAssertEqual(assessment, expectedAssessment())

        let catalogAfterEmbedding = try await backend.listModels()
        let selectedAfterEmbedding = try XCTUnwrap(
            catalogAfterEmbedding.first(where: {
                Self.sameOllamaModel($0.id, modelID)
            })
        )
        XCTAssertTrue(selectedAfterEmbedding.running)
        let unloadResult = try await backend.unloadModel(
            providerModelID: modelID
        )
        XCTAssertEqual(unloadResult.outcome, .confirmed)
        let catalogAfterUnload = try await backend.listModels()
        XCTAssertEqual(
            catalogAfterUnload.map(\.id).sorted(),
            catalogIdentityBefore
        )
        let selectedAfterUnload = try XCTUnwrap(
            catalogAfterUnload.first(where: {
                Self.sameOllamaModel($0.id, modelID)
            })
        )
        XCTAssertTrue(selectedAfterUnload.installed)
        XCTAssertFalse(selectedAfterUnload.running)
        let healthAfter = await backend.healthCheck()
        XCTAssertEqual(healthAfter, .available)
    }

    private struct LiveFixture {
        let backend: OllamaBackend
        let modelID: String
        let expectedCatalogCount: Int
    }

    private enum LiveFixtureError: Error {
        case invalidEnvironment
        case invalidBoundary
        case invalidSnapshot
    }

    private func liveFixture(
        environment: [String: String]
    ) async throws -> LiveFixture {
        guard
            let baseURLValue = environment[
                "AETHERLINK_OLLAMA_LIVE_BASE_URL"
            ],
            let baseURL = URL(string: baseURLValue),
            let expectedVersion = environment[
                "AETHERLINK_OLLAMA_LIVE_EXPECTED_VERSION"
            ],
            let archiveSHA256 = environment[
                "AETHERLINK_OLLAMA_LIVE_ARCHIVE_SHA256"
            ],
            let modelsDirectory = environment[
                "AETHERLINK_OLLAMA_LIVE_MODELS_DIRECTORY"
            ],
            let modelID = environment[
                "AETHERLINK_OLLAMA_LIVE_EMBEDDING_MODEL_ID"
            ],
            let expectedCatalogCountValue = environment[
                "AETHERLINK_OLLAMA_LIVE_EXPECTED_CATALOG_COUNT"
            ],
            let expectedCatalogCount = Int(expectedCatalogCountValue),
            String(expectedCatalogCount) == expectedCatalogCountValue
        else {
            XCTFail("Missing runner-owned multilingual fixture inputs.")
            throw LiveFixtureError.invalidEnvironment
        }
        let exactCandidateHashes = [
            "0.32.5": (
                "5789dd037a86adb328c72c11fc45e6c558452d07e5b50814a8"
                + "bdb7b0fbdbcd81"
            ),
            "0.32.4": (
                "15383493225d5e7e7fda052dc103ab4d2835a22eabb41655f1"
                + "d6302c6d1577bc"
            ),
        ]
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
            exactCandidateHashes[expectedVersion] == archiveSHA256,
            (1...ModelInfo.maximumCatalogModelCount).contains(
                expectedCatalogCount
            ),
            !modelID.isEmpty,
            modelID.utf8.count <= 1_024,
            modelID.unicodeScalars.allSatisfy({
                $0.value >= 0x20 && $0.value != 0x7f
            })
        else {
            XCTFail("The multilingual fixture boundary was invalid.")
            throw LiveFixtureError.invalidBoundary
        }

        var isDirectory: ObjCBool = false
        let modelsDirectoryURL = URL(
            fileURLWithPath: modelsDirectory,
            isDirectory: true
        ).standardizedFileURL
        guard
            modelsDirectory.hasPrefix("/"),
            modelsDirectoryURL.lastPathComponent == "model-snapshot",
            modelsDirectoryURL.pathComponents.contains(where: {
                $0.hasPrefix(
                    "aetherlink-ollama-embedding-semantic-quality-v2-"
                )
            }),
            FileManager.default.fileExists(
                atPath: modelsDirectoryURL.path,
                isDirectory: &isDirectory
            ),
            isDirectory.boolValue
        else {
            XCTFail("The multilingual model snapshot escaped its boundary.")
            throw LiveFixtureError.invalidSnapshot
        }

        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 120
        configuration.timeoutIntervalForResource = 180
        let session = URLSession(configuration: configuration)
        let versionURL = baseURL.appending(path: "api/version")
        let (versionData, versionResponse) = try await session.data(
            from: versionURL
        )
        XCTAssertEqual(
            (versionResponse as? HTTPURLResponse)?.statusCode,
            200
        )
        let versionPayload = try XCTUnwrap(
            JSONSerialization.jsonObject(with: versionData)
                as? [String: Any]
        )
        XCTAssertEqual(
            versionPayload["version"] as? String,
            expectedVersion
        )
        return LiveFixture(
            backend: OllamaBackend(baseURL: baseURL, session: session),
            modelID: modelID,
            expectedCatalogCount: expectedCatalogCount
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
            XCTFail("Missing runner-owned multilingual task set.")
            throw LiveFixtureError.invalidEnvironment
        }
        let url = URL(
            fileURLWithPath: path,
            isDirectory: false
        ).standardizedFileURL
        guard
            url.lastPathComponent
                == "ollama-embedding-multilingual-semantic-quality-v2.json",
            url.pathComponents.contains(where: {
                $0.hasPrefix(
                    "aetherlink-ollama-embedding-semantic-quality-v2-"
                )
            })
        else {
            XCTFail("The multilingual task set escaped its boundary.")
            throw LiveFixtureError.invalidBoundary
        }
        return try OllamaEmbeddingMultilingualSemanticTaskSet.load(
            from: url,
            expectedSHA256: sha256
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

    private func expectedAssessment()
        -> OllamaEmbeddingMultilingualSemanticAssessment
    {
        OllamaEmbeddingMultilingualSemanticAssessment(
            batchCalls: 2,
            embeddingCount: 160,
            localeAssessments: (
                OllamaEmbeddingMultilingualSemanticTaskSet
                    .supportedLocales.map { locale in
                        OllamaEmbeddingMultilingualLocaleAssessment(
                            locale: locale,
                            scenarioCount: 4,
                            textCount: 16
                        )
                    }
            ),
            scenarioCount: 20,
            textCountPerBatch: 80
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
