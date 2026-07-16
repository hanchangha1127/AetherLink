import Foundation
import OllamaBackend

public enum RuntimeChatCompactionCalibrationStatus: String, Codable, Equatable, Sendable {
    case inputBudgetExceededObserved = "input_budget_exceeded_observed"
    case readyForReview = "ready_for_review"
    case collecting
}

public struct RuntimeChatCompactionCalibrationGroup: Codable, Equatable, Sendable {
    public var provider: String
    public var providerModelID: String
    public var wireMode: String
    public var estimatorIdentifier: String
    public var sampleCount: Int
    public var withinConservativeEstimateCount: Int
    public var exceededConservativeEstimateWithinBudgetCount: Int
    public var exceededInputBudgetCount: Int
    public var status: RuntimeChatCompactionCalibrationStatus

    private enum CodingKeys: String, CodingKey {
        case provider
        case providerModelID = "provider_model_id"
        case wireMode = "wire_mode"
        case estimatorIdentifier = "estimator_identifier"
        case sampleCount = "sample_count"
        case withinConservativeEstimateCount = "within_conservative_estimate_count"
        case exceededConservativeEstimateWithinBudgetCount = "exceeded_conservative_estimate_within_budget_count"
        case exceededInputBudgetCount = "exceeded_input_budget_count"
        case status
    }
}

public struct RuntimeChatCompactionCalibrationReport: Codable, Equatable, Sendable {
    public static let recentEligibleSampleCap = 1_000
    public static let groupCap = 32
    public static let minimumSampleFloor = 20

    public var sampledEligibleCount: Int
    public var reportedSampleCount: Int
    public var omittedSampleCount: Int
    public var groups: [RuntimeChatCompactionCalibrationGroup]

    public init() {
        sampledEligibleCount = 0
        reportedSampleCount = 0
        omittedSampleCount = 0
        groups = []
    }

    public static func build(from events: [RuntimeChatStoredEvent]) -> Self {
        var report = Self()
        var aggregates: [GroupKey: GroupAggregate] = [:]

        for event in events.reversed() {
            guard report.sampledEligibleCount < recentEligibleSampleCap else { break }
            guard let sample = eligibleSample(from: event) else { continue }

            saturatingIncrement(&report.sampledEligibleCount)
            if var aggregate = aggregates[sample.key] {
                aggregate.record(sample.relation)
                aggregates[sample.key] = aggregate
                saturatingIncrement(&report.reportedSampleCount)
            } else if aggregates.count < groupCap {
                var aggregate = GroupAggregate()
                aggregate.record(sample.relation)
                aggregates[sample.key] = aggregate
                saturatingIncrement(&report.reportedSampleCount)
            } else {
                saturatingIncrement(&report.omittedSampleCount)
            }
        }

        report.groups = aggregates.map { key, aggregate in
            RuntimeChatCompactionCalibrationGroup(
                provider: key.provider,
                providerModelID: key.providerModelID,
                wireMode: key.wireMode,
                estimatorIdentifier: key.estimatorIdentifier,
                sampleCount: aggregate.sampleCount,
                withinConservativeEstimateCount: aggregate.withinConservativeEstimateCount,
                exceededConservativeEstimateWithinBudgetCount:
                    aggregate.exceededConservativeEstimateWithinBudgetCount,
                exceededInputBudgetCount: aggregate.exceededInputBudgetCount,
                status: aggregate.status
            )
        }.sorted(by: groupPrecedes)
        return report
    }

    private static func eligibleSample(from event: RuntimeChatStoredEvent) -> EligibleSample? {
        guard event.kind == .done,
              let resolution = event.compactionResolution,
              resolution.primaryDispatched,
              resolution.summaryMethod == "deterministic_preview_v1"
                || resolution.summaryMethod == "llm_summary_v1",
              !resolution.estimatorIdentifier.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              resolution.inputBudgetTokens > 0,
              let estimatedInputTokensAfter = resolution.estimatedInputTokensAfter,
              estimatedInputTokensAfter >= 0,
              estimatedInputTokensAfter <= resolution.inputBudgetTokens,
              let calibration = resolution.providerUsageCalibration,
              calibration.countSource == RuntimeChatProviderUsageCalibration.countSourceIdentifier,
              calibration.inputTokens >= 0,
              event.usage?.inputTokens == calibration.inputTokens,
              validWireMode(calibration.wireMode, for: calibration.provider),
              canonicalProviderModelID(calibration.providerModelID) == calibration.providerModelID,
              !calibration.providerModelID.isEmpty,
              ModelProvider.splitQualifiedModelID(calibration.providerModelID) == nil,
              resolution.resolvedProviderQualifiedModelID
                == "\(calibration.provider):\(calibration.providerModelID)",
              expectedRelation(
                inputTokens: calibration.inputTokens,
                estimatedInputTokensAfter: estimatedInputTokensAfter,
                inputBudgetTokens: resolution.inputBudgetTokens
              ) == calibration.relation else {
            return nil
        }

        return EligibleSample(
            key: GroupKey(
                provider: calibration.provider,
                providerModelID: calibration.providerModelID,
                wireMode: calibration.wireMode,
                estimatorIdentifier: resolution.estimatorIdentifier
            ),
            relation: calibration.relation
        )
    }

    private static func validWireMode(_ wireMode: String, for provider: String) -> Bool {
        switch provider {
        case ModelProvider.ollama.rawValue:
            return wireMode == "ollama_chat"
        case ModelProvider.lmStudio.rawValue:
            return wireMode == "lmstudio_native" || wireMode == "lmstudio_openai_compat"
        default:
            return false
        }
    }

    private static func canonicalProviderModelID(_ modelID: String) -> String {
        let trimmed = modelID.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.hasSuffix(":latest") {
            return String(trimmed.dropLast(":latest".count))
        }
        return trimmed
    }

    private static func expectedRelation(
        inputTokens: Int,
        estimatedInputTokensAfter: Int,
        inputBudgetTokens: Int
    ) -> RuntimeChatProviderTokenRelation {
        if inputTokens <= estimatedInputTokensAfter {
            return .withinConservativeEstimate
        }
        if inputTokens <= inputBudgetTokens {
            return .exceededConservativeEstimateWithinBudget
        }
        return .exceededInputBudget
    }

    private static func groupPrecedes(
        _ lhs: RuntimeChatCompactionCalibrationGroup,
        _ rhs: RuntimeChatCompactionCalibrationGroup
    ) -> Bool {
        if lhs.sampleCount != rhs.sampleCount {
            return lhs.sampleCount > rhs.sampleCount
        }
        if lhs.provider != rhs.provider {
            return lhs.provider < rhs.provider
        }
        if lhs.providerModelID != rhs.providerModelID {
            return lhs.providerModelID < rhs.providerModelID
        }
        if lhs.wireMode != rhs.wireMode {
            return lhs.wireMode < rhs.wireMode
        }
        return lhs.estimatorIdentifier < rhs.estimatorIdentifier
    }

    private static func saturatingIncrement(_ value: inout Int) {
        let (incremented, overflow) = value.addingReportingOverflow(1)
        value = overflow ? Int.max : incremented
    }
}

private extension RuntimeChatCompactionCalibrationReport {
    struct GroupKey: Hashable, Sendable {
        var provider: String
        var providerModelID: String
        var wireMode: String
        var estimatorIdentifier: String
    }

    struct EligibleSample: Sendable {
        var key: GroupKey
        var relation: RuntimeChatProviderTokenRelation
    }

    struct GroupAggregate: Sendable {
        var sampleCount = 0
        var withinConservativeEstimateCount = 0
        var exceededConservativeEstimateWithinBudgetCount = 0
        var exceededInputBudgetCount = 0

        var status: RuntimeChatCompactionCalibrationStatus {
            if exceededInputBudgetCount > 0 {
                return .inputBudgetExceededObserved
            }
            if sampleCount >= RuntimeChatCompactionCalibrationReport.minimumSampleFloor {
                return .readyForReview
            }
            return .collecting
        }

        mutating func record(_ relation: RuntimeChatProviderTokenRelation) {
            RuntimeChatCompactionCalibrationReport.saturatingIncrement(&sampleCount)
            switch relation {
            case .withinConservativeEstimate:
                RuntimeChatCompactionCalibrationReport.saturatingIncrement(
                    &withinConservativeEstimateCount
                )
            case .exceededConservativeEstimateWithinBudget:
                RuntimeChatCompactionCalibrationReport.saturatingIncrement(
                    &exceededConservativeEstimateWithinBudgetCount
                )
            case .exceededInputBudget:
                RuntimeChatCompactionCalibrationReport.saturatingIncrement(&exceededInputBudgetCount)
            }
        }
    }
}
