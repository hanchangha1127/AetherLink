@testable import CompanionCore
import OllamaBackend
import XCTest

final class RuntimeChatCompactionCalibrationReportTests: XCTestCase {
    func testEmptyInitializerAndGroupingStatusesRespectMinimumFloor() throws {
        XCTAssertEqual(RuntimeChatCompactionCalibrationReport(), RuntimeChatCompactionCalibrationReport())
        XCTAssertTrue(RuntimeChatCompactionCalibrationReport().groups.isEmpty)

        var events = (0..<19).map { _ in calibrationEvent(modelID: "ready-model") }
        events.append(calibrationEvent(
            modelID: "ready-model",
            relation: .exceededConservativeEstimateWithinBudget
        ))
        events.append(contentsOf: (0..<19).map { _ in
            calibrationEvent(modelID: "collecting-model")
        })
        events.append(calibrationEvent(modelID: "budget-model", relation: .exceededInputBudget))
        events.append(calibrationEvent(
            provider: "lm_studio",
            modelID: "ready-model",
            wireMode: "lmstudio_native",
            estimatorIdentifier: "estimator-v2"
        ))

        var wrongUsage = calibrationEvent(modelID: "structurally-ineligible")
        wrongUsage.usage = RuntimeChatStoredUsage(inputTokens: 99, outputTokens: 10)
        let noncanonicalModel = calibrationEvent(modelID: "noncanonical:latest")
        events.append(contentsOf: [wrongUsage, noncanonicalModel])

        let report = RuntimeChatCompactionCalibrationReport.build(from: events)

        XCTAssertEqual(report.sampledEligibleCount, 41)
        XCTAssertEqual(report.reportedSampleCount, 41)
        XCTAssertEqual(report.omittedSampleCount, 0)
        XCTAssertEqual(report.groups.count, 4)

        let ready = try XCTUnwrap(report.groups.first { $0.providerModelID == "ready-model" && $0.provider == "ollama" })
        XCTAssertEqual(ready.sampleCount, 20)
        XCTAssertEqual(ready.withinConservativeEstimateCount, 19)
        XCTAssertEqual(ready.exceededConservativeEstimateWithinBudgetCount, 1)
        XCTAssertEqual(ready.status, .readyForReview)

        let collecting = try XCTUnwrap(report.groups.first { $0.providerModelID == "collecting-model" })
        XCTAssertEqual(collecting.sampleCount, 19)
        XCTAssertEqual(collecting.status, .collecting)

        let budget = try XCTUnwrap(report.groups.first { $0.providerModelID == "budget-model" })
        XCTAssertEqual(budget.exceededInputBudgetCount, 1)
        XCTAssertEqual(budget.status, .inputBudgetExceededObserved)

        let exactKeyVariant = try XCTUnwrap(report.groups.first { $0.provider == "lm_studio" })
        XCTAssertEqual(exactKeyVariant.providerModelID, "ready-model")
        XCTAssertEqual(exactKeyVariant.wireMode, "lmstudio_native")
        XCTAssertEqual(exactKeyVariant.estimatorIdentifier, "estimator-v2")
    }

    func testNewestEligibleSamplesWinAtSampleCap() throws {
        var events = [calibrationEvent(relation: .exceededInputBudget)]
        events.append(contentsOf: (0..<RuntimeChatCompactionCalibrationReport.recentEligibleSampleCap).map { _ in
            calibrationEvent(relation: .withinConservativeEstimate)
        })

        let report = RuntimeChatCompactionCalibrationReport.build(from: events)
        let group = try XCTUnwrap(report.groups.first)

        XCTAssertEqual(report.sampledEligibleCount, 1_000)
        XCTAssertEqual(report.reportedSampleCount, 1_000)
        XCTAssertEqual(report.omittedSampleCount, 0)
        XCTAssertEqual(group.sampleCount, 1_000)
        XCTAssertEqual(group.withinConservativeEstimateCount, 1_000)
        XCTAssertEqual(group.exceededInputBudgetCount, 0)
        XCTAssertEqual(group.status, .readyForReview)
    }

    func testInputBudgetExceededWarningWinsAfterReviewFloor() throws {
        var events = (0..<RuntimeChatCompactionCalibrationReport.minimumSampleFloor).map { _ in
            calibrationEvent(relation: .withinConservativeEstimate)
        }
        events.append(calibrationEvent(relation: .exceededInputBudget))

        let group = try XCTUnwrap(
            RuntimeChatCompactionCalibrationReport.build(from: events).groups.first
        )

        XCTAssertEqual(group.sampleCount, RuntimeChatCompactionCalibrationReport.minimumSampleFloor + 1)
        XCTAssertEqual(group.exceededInputBudgetCount, 1)
        XCTAssertEqual(group.status, .inputBudgetExceededObserved)
    }

    func testGroupCapKeepsNewestGroupsAndReportsOmittedSamples() {
        let events = (0...RuntimeChatCompactionCalibrationReport.groupCap).map { index in
            calibrationEvent(modelID: String(format: "model-%02d", index))
        }

        let report = RuntimeChatCompactionCalibrationReport.build(from: events)

        XCTAssertEqual(report.sampledEligibleCount, 33)
        XCTAssertEqual(report.reportedSampleCount, 32)
        XCTAssertEqual(report.omittedSampleCount, 1)
        XCTAssertEqual(report.groups.count, 32)
        XCTAssertFalse(report.groups.contains { $0.providerModelID == "model-00" })
        XCTAssertTrue(report.groups.contains { $0.providerModelID == "model-32" })
    }

    func testGroupsHaveDeterministicCountThenLexicalOrder() {
        let events = [
            calibrationEvent(provider: "ollama", modelID: "zeta", wireMode: "ollama_chat", estimatorIdentifier: "b"),
            calibrationEvent(provider: "lm_studio", modelID: "beta", wireMode: "lmstudio_native", estimatorIdentifier: "a"),
            calibrationEvent(provider: "lm_studio", modelID: "alpha", wireMode: "lmstudio_openai_compat", estimatorIdentifier: "a"),
            calibrationEvent(provider: "lm_studio", modelID: "alpha", wireMode: "lmstudio_native", estimatorIdentifier: "z"),
            calibrationEvent(provider: "lm_studio", modelID: "alpha", wireMode: "lmstudio_native", estimatorIdentifier: "a"),
            calibrationEvent(provider: "ollama", modelID: "popular", wireMode: "ollama_chat", estimatorIdentifier: "a"),
            calibrationEvent(provider: "ollama", modelID: "popular", wireMode: "ollama_chat", estimatorIdentifier: "a"),
        ]

        let orderedKeys = RuntimeChatCompactionCalibrationReport.build(from: events).groups.map {
            "\($0.sampleCount)|\($0.provider)|\($0.providerModelID)|\($0.wireMode)|\($0.estimatorIdentifier)"
        }

        XCTAssertEqual(orderedKeys, [
            "2|ollama|popular|ollama_chat|a",
            "1|lm_studio|alpha|lmstudio_native|a",
            "1|lm_studio|alpha|lmstudio_native|z",
            "1|lm_studio|alpha|lmstudio_openai_compat|a",
            "1|lm_studio|beta|lmstudio_native|a",
            "1|ollama|zeta|ollama_chat|b",
        ])
    }

    func testJSONReportContainsOnlyAggregateDataNotEventPrivacyCanaries() throws {
        let canaries = [
            "prompt-private-canary",
            "messages-private-canary",
            "session-private-canary",
            "request-private-canary",
            "owner-private-canary",
        ]
        var event = calibrationEvent()
        event.id = "messages-private-canary"
        event.requestID = "request-private-canary"
        event.sessionID = "session-private-canary"
        event.ownerDeviceID = "owner-private-canary"
        event.messages = [ChatMessage(role: "user", content: "prompt-private-canary")]

        let report = RuntimeChatCompactionCalibrationReport.build(from: [event])
        let json = String(decoding: try JSONEncoder().encode(report), as: UTF8.self)
        let root = try XCTUnwrap(
            JSONSerialization.jsonObject(with: Data(json.utf8)) as? [String: Any]
        )
        let groups = try XCTUnwrap(root["groups"] as? [[String: Any]])
        let group = try XCTUnwrap(groups.first)

        XCTAssertEqual(report.sampledEligibleCount, 1)
        XCTAssertEqual(
            Set(root.keys),
            ["groups", "omittedSampleCount", "reportedSampleCount", "sampledEligibleCount"]
        )
        XCTAssertEqual(
            Set(group.keys),
            [
                "estimator_identifier",
                "exceeded_conservative_estimate_within_budget_count",
                "exceeded_input_budget_count",
                "provider",
                "provider_model_id",
                "sample_count",
                "status",
                "wire_mode",
                "within_conservative_estimate_count",
            ]
        )
        XCTAssertFalse(json.contains("timestamp"))
        for canary in canaries {
            XCTAssertFalse(json.contains(canary), "Report leaked \(canary)")
        }
    }

    private func calibrationEvent(
        provider: String = "ollama",
        modelID: String = "llama3.1:8b",
        wireMode: String = "ollama_chat",
        estimatorIdentifier: String = "estimator-v1",
        relation: RuntimeChatProviderTokenRelation = .withinConservativeEstimate
    ) -> RuntimeChatStoredEvent {
        let inputTokens: Int
        switch relation {
        case .withinConservativeEstimate:
            inputTokens = 100
        case .exceededConservativeEstimateWithinBudget:
            inputTokens = 150
        case .exceededInputBudget:
            inputTokens = 201
        }
        return RuntimeChatStoredEvent(
            kind: .done,
            requestID: "request",
            sessionID: "session",
            model: "\(provider):\(modelID)",
            finishReason: "stop",
            usage: RuntimeChatStoredUsage(inputTokens: inputTokens, outputTokens: 10),
            ownerDeviceID: "owner",
            compactionResolution: RuntimeChatCompactionResolution(
                primaryDispatched: true,
                summaryMethod: "llm_summary_v1",
                estimatorIdentifier: estimatorIdentifier,
                inputBudgetTokens: 200,
                estimatedInputTokensAfter: 100,
                resolvedProviderQualifiedModelID: "\(provider):\(modelID)",
                providerUsageCalibration: RuntimeChatProviderUsageCalibration(
                    provider: provider,
                    providerModelID: modelID,
                    wireMode: wireMode,
                    inputTokens: inputTokens,
                    relation: relation
                )
            )
        )
    }
}
