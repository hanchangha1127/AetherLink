import Darwin
import Foundation
import OllamaBackend

public enum RuntimeChatStoredEventKind: String, Codable, Equatable, Sendable {
    case request
    case assistantDelta = "assistant_delta"
    case reasoningDelta = "reasoning_delta"
    case title
    case archived
    case restored
    case deleted
    case done
    case cancelled
    case error
}

public enum RuntimeChatSessionMutation: String, Equatable, Sendable {
    case archive = "archived"
    case restore = "restored"
    case delete = "deleted"
}

public struct RuntimeChatSessionMutationResult: Equatable, Sendable {
    public var sessionID: String
    public var mutation: RuntimeChatSessionMutation
    public var timestamp: Date

    public init(sessionID: String, mutation: RuntimeChatSessionMutation, timestamp: Date) {
        self.sessionID = sessionID
        self.mutation = mutation
        self.timestamp = timestamp
    }
}

public enum RuntimeChatSessionBulkScope: String, Equatable, Sendable {
    case allActive = "all_active"
    case allArchived = "all_archived"

    public var mutation: RuntimeChatSessionMutation {
        switch self {
        case .allActive: .archive
        case .allArchived: .delete
        }
    }
}

public struct RuntimeChatSessionBulkMutationResult: Equatable, Sendable {
    public var scope: RuntimeChatSessionBulkScope
    public var affectedSessionIDs: [String]
    public var remainingCount: Int
    public var timestamp: Date

    public var mutation: RuntimeChatSessionMutation { scope.mutation }
    public var affectedCount: Int { affectedSessionIDs.count }

    public init(
        scope: RuntimeChatSessionBulkScope,
        affectedSessionIDs: [String],
        remainingCount: Int,
        timestamp: Date
    ) {
        self.scope = scope
        self.affectedSessionIDs = affectedSessionIDs
        self.remainingCount = remainingCount
        self.timestamp = timestamp
    }
}

public enum RuntimeChatEventStoreError: Error, LocalizedError, Equatable {
    case sessionNotFound(String)
    case sessionMustBeArchivedBeforeDelete(String)
    case bulkMutationUnsupported
    case invalidTargetedSessionSummarySessionID
    case duplicateTargetedSessionSummarySessionID
    case targetedSessionSummaryLimitExceeded(maximum: Int)
    case corruptEventLog(line: Int, reason: String)

    public var errorDescription: String? {
        switch self {
        case .sessionNotFound(let sessionID):
            return "Chat session not found: \(sessionID)"
        case .sessionMustBeArchivedBeforeDelete(let sessionID):
            return "Chat session must be archived before deletion: \(sessionID)"
        case .bulkMutationUnsupported:
            return "Atomic bulk chat session mutation is not supported by this store."
        case .invalidTargetedSessionSummarySessionID:
            return "Targeted chat session summary lookup contains an invalid session id."
        case .duplicateTargetedSessionSummarySessionID:
            return "Targeted chat session summary lookup contains a duplicate session id."
        case .targetedSessionSummaryLimitExceeded(let maximum):
            return "Targeted chat session summary lookup exceeds the maximum of \(maximum) session ids."
        case .corruptEventLog(let line, let reason):
            return "Runtime chat event log is corrupt at line \(line): \(reason)"
        }
    }
}

public enum RuntimeChatHostWideProjectionError: Error, LocalizedError, Equatable {
    case ambiguousSessionID(String)

    public var errorDescription: String? {
        switch self {
        case .ambiguousSessionID(let sessionID):
            return "Chat session id is shared by more than one owner: \(sessionID)"
        }
    }
}

public struct RuntimeChatStoredUsage: Codable, Equatable, Sendable {
    public var inputTokens: Int?
    public var outputTokens: Int?

    public init(inputTokens: Int?, outputTokens: Int?) {
        self.inputTokens = inputTokens
        self.outputTokens = outputTokens
    }

    enum CodingKeys: String, CodingKey {
        case inputTokens = "input_tokens"
        case outputTokens = "output_tokens"
    }
}

public enum RuntimeChatProviderTokenRelation: String, Codable, Equatable, Sendable {
    case withinConservativeEstimate = "within_conservative_estimate"
    case exceededConservativeEstimateWithinBudget = "exceeded_conservative_estimate_within_budget"
    case exceededInputBudget = "exceeded_input_budget"
}

public struct RuntimeChatProviderUsageCalibration: Codable, Equatable, Sendable {
    public static let countSourceIdentifier = "provider_usage_calibration_v1"

    public var countSource: String
    public var provider: String
    public var providerModelID: String
    public var wireMode: String
    public var inputTokens: Int
    public var relation: RuntimeChatProviderTokenRelation

    public init(
        countSource: String = Self.countSourceIdentifier,
        provider: String,
        providerModelID: String,
        wireMode: String,
        inputTokens: Int,
        relation: RuntimeChatProviderTokenRelation
    ) {
        self.countSource = countSource
        self.provider = provider
        self.providerModelID = providerModelID
        self.wireMode = wireMode
        self.inputTokens = inputTokens
        self.relation = relation
    }

    enum CodingKeys: String, CodingKey {
        case countSource = "count_source"
        case provider
        case providerModelID = "provider_model_id"
        case wireMode = "wire_mode"
        case inputTokens = "input_tokens"
        case relation
    }
}

public struct RuntimeChatStoredError: Codable, Equatable, Sendable {
    public var code: String
    public var message: String

    public init(code: String, message: String) {
        self.code = code
        self.message = message
    }
}

public struct RuntimeChatSourceAttribution: Codable, Equatable, Sendable {
    public var sourceIndex: Int
    public var documentName: String
    public var mimeType: String
    public var chunkIndex: Int

    public init(sourceIndex: Int, documentName: String, mimeType: String, chunkIndex: Int) {
        self.sourceIndex = sourceIndex
        self.documentName = documentName
        self.mimeType = mimeType
        self.chunkIndex = chunkIndex
    }

    enum CodingKeys: String, CodingKey, CaseIterable {
        case sourceIndex = "source_index"
        case documentName = "document_name"
        case mimeType = "mime_type"
        case chunkIndex = "chunk_index"
    }

    public init(from decoder: Decoder) throws {
        let allKeys = try decoder.container(keyedBy: RuntimeChatSourceAttributionAnyCodingKey.self).allKeys
        let allowedKeys = Set(CodingKeys.allCases.map(\.rawValue))
        guard allKeys.allSatisfy({ allowedKeys.contains($0.stringValue) }) else {
            throw DecodingError.dataCorrupted(
                .init(codingPath: decoder.codingPath, debugDescription: "Unsupported chat source attribution field")
            )
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        sourceIndex = try container.decode(Int.self, forKey: .sourceIndex)
        documentName = try container.decode(String.self, forKey: .documentName)
        mimeType = try container.decode(String.self, forKey: .mimeType)
        chunkIndex = try container.decode(Int.self, forKey: .chunkIndex)
    }
}

public struct RuntimeChatSourceAttributionBinding: Codable, Equatable, Sendable {
    public var sourceIndex: Int
    public var sourceAnchorID: String
    public var documentID: String
    public var sourceRevision: String

    public init(sourceIndex: Int, sourceAnchorID: String, documentID: String, sourceRevision: String) {
        self.sourceIndex = sourceIndex
        self.sourceAnchorID = sourceAnchorID
        self.documentID = documentID
        self.sourceRevision = sourceRevision
    }

    enum CodingKeys: String, CodingKey, CaseIterable {
        case sourceIndex = "source_index"
        case sourceAnchorID = "source_anchor_id"
        case documentID = "document_id"
        case sourceRevision = "source_revision"
    }

    public init(from decoder: Decoder) throws {
        let allKeys = try decoder.container(keyedBy: RuntimeChatSourceAttributionAnyCodingKey.self).allKeys
        let allowedKeys = Set(CodingKeys.allCases.map(\.rawValue))
        guard allKeys.allSatisfy({ allowedKeys.contains($0.stringValue) }) else {
            throw DecodingError.dataCorrupted(
                .init(
                    codingPath: decoder.codingPath,
                    debugDescription: "Unsupported chat source attribution binding field"
                )
            )
        }
        let container = try decoder.container(keyedBy: CodingKeys.self)
        sourceIndex = try container.decode(Int.self, forKey: .sourceIndex)
        sourceAnchorID = try container.decode(String.self, forKey: .sourceAnchorID)
        documentID = try container.decode(String.self, forKey: .documentID)
        sourceRevision = try container.decode(String.self, forKey: .sourceRevision)
    }
}

public struct RuntimeChatResolvedSourceAttribution: Equatable, Sendable {
    public var assistantMessageID: String
    public var binding: RuntimeChatSourceAttributionBinding
}

private struct RuntimeChatSourceAttributionAnyCodingKey: CodingKey {
    var stringValue: String
    var intValue: Int?

    init?(stringValue: String) {
        self.stringValue = stringValue
        self.intValue = nil
    }

    init?(intValue: Int) {
        self.stringValue = String(intValue)
        self.intValue = intValue
    }
}

public struct RuntimeChatCompactionSourcePointer: Codable, Equatable, Sendable {
    public var sourceKind: String
    public var sessionID: String
    public var requestID: String
    public var startTurn: Int
    public var endTurn: Int
    public var totalTurns: Int
    public var compactedTurnCount: Int
    public var retainedStartTurn: Int?
    public var retainedEndTurn: Int?
    public var retainedTurnCount: Int
    public var sourceFingerprintAlgorithm: String?
    public var sourceFingerprint: String?
    public var sourceCanonicalByteCount: Int?

    public init(
        sourceKind: String = "client_visible_conversation_turns",
        sessionID: String,
        requestID: String,
        startTurn: Int,
        endTurn: Int,
        totalTurns: Int,
        compactedTurnCount: Int,
        retainedStartTurn: Int? = nil,
        retainedEndTurn: Int? = nil,
        retainedTurnCount: Int,
        sourceFingerprintAlgorithm: String? = nil,
        sourceFingerprint: String? = nil,
        sourceCanonicalByteCount: Int? = nil
    ) {
        self.sourceKind = sourceKind
        self.sessionID = sessionID
        self.requestID = requestID
        self.startTurn = startTurn
        self.endTurn = endTurn
        self.totalTurns = totalTurns
        self.compactedTurnCount = compactedTurnCount
        self.retainedStartTurn = retainedStartTurn
        self.retainedEndTurn = retainedEndTurn
        self.retainedTurnCount = retainedTurnCount
        self.sourceFingerprintAlgorithm = sourceFingerprintAlgorithm
        self.sourceFingerprint = sourceFingerprint
        self.sourceCanonicalByteCount = sourceCanonicalByteCount
    }

    enum CodingKeys: String, CodingKey {
        case sourceKind = "source_kind"
        case sessionID = "session_id"
        case requestID = "request_id"
        case startTurn = "start_turn"
        case endTurn = "end_turn"
        case totalTurns = "total_turns"
        case compactedTurnCount = "compacted_turn_count"
        case retainedStartTurn = "retained_start_turn"
        case retainedEndTurn = "retained_end_turn"
        case retainedTurnCount = "retained_turn_count"
        case sourceFingerprintAlgorithm = "source_fingerprint_algorithm"
        case sourceFingerprint = "source_fingerprint"
        case sourceCanonicalByteCount = "source_canonical_byte_count"
    }
}

public struct RuntimeChatCompactionMetadata: Codable, Equatable, Sendable {
    public var strategy: String
    public var sourcePointers: [RuntimeChatCompactionSourcePointer]
    public var estimatorIdentifier: String?
    public var contextWindowTokens: Int?
    public var outputReserveTokens: Int?
    public var inputBudgetTokens: Int?
    public var estimatedInputTokensBefore: Int?
    public var estimatedInputTokensAfter: Int?
    public var estimateKind: String?
    public var summaryPolicy: String?

    public init(
        strategy: String = "backend_only_summary_v1",
        sourcePointers: [RuntimeChatCompactionSourcePointer],
        estimatorIdentifier: String? = nil,
        contextWindowTokens: Int? = nil,
        outputReserveTokens: Int? = nil,
        inputBudgetTokens: Int? = nil,
        estimatedInputTokensBefore: Int? = nil,
        estimatedInputTokensAfter: Int? = nil,
        estimateKind: String? = nil,
        summaryPolicy: String? = nil
    ) {
        self.strategy = strategy
        self.sourcePointers = sourcePointers
        self.estimatorIdentifier = estimatorIdentifier
        self.contextWindowTokens = contextWindowTokens
        self.outputReserveTokens = outputReserveTokens
        self.inputBudgetTokens = inputBudgetTokens
        self.estimatedInputTokensBefore = estimatedInputTokensBefore
        self.estimatedInputTokensAfter = estimatedInputTokensAfter
        self.estimateKind = estimateKind
        self.summaryPolicy = summaryPolicy
    }

    enum CodingKeys: String, CodingKey {
        case strategy
        case sourcePointers = "source_pointers"
        case estimatorIdentifier = "estimator_identifier"
        case contextWindowTokens = "context_window_tokens"
        case outputReserveTokens = "output_reserve_tokens"
        case inputBudgetTokens = "input_budget_tokens"
        case estimatedInputTokensBefore = "estimated_input_tokens_before"
        case estimatedInputTokensAfter = "estimated_input_tokens_after"
        case estimateKind = "estimate_kind"
        case summaryPolicy = "summary_policy"
    }
}

public struct RuntimeChatCompactionResolution: Codable, Equatable, Sendable {
    public var primaryDispatched: Bool
    public var summaryMethod: String?
    public var estimatorIdentifier: String
    public var inputBudgetTokens: Int
    public var estimatedInputTokensAfter: Int?
    public var resolvedProviderQualifiedModelID: String?
    public var providerUsageCalibration: RuntimeChatProviderUsageCalibration?

    public init(
        primaryDispatched: Bool,
        summaryMethod: String? = nil,
        estimatorIdentifier: String,
        inputBudgetTokens: Int,
        estimatedInputTokensAfter: Int? = nil,
        resolvedProviderQualifiedModelID: String? = nil,
        providerUsageCalibration: RuntimeChatProviderUsageCalibration? = nil
    ) {
        self.primaryDispatched = primaryDispatched
        self.summaryMethod = summaryMethod
        self.estimatorIdentifier = estimatorIdentifier
        self.inputBudgetTokens = inputBudgetTokens
        self.estimatedInputTokensAfter = estimatedInputTokensAfter
        self.resolvedProviderQualifiedModelID = resolvedProviderQualifiedModelID
        self.providerUsageCalibration = providerUsageCalibration
    }

    enum CodingKeys: String, CodingKey {
        case primaryDispatched = "primary_dispatched"
        case summaryMethod = "summary_method"
        case estimatorIdentifier = "estimator_identifier"
        case inputBudgetTokens = "input_budget_tokens"
        case estimatedInputTokensAfter = "estimated_input_tokens_after"
        case resolvedProviderQualifiedModelID = "resolved_provider_qualified_model_id"
        case providerUsageCalibration = "provider_usage_calibration"
    }
}

public struct RuntimeChatStoredEvent: Codable, Equatable, Sendable {
    public var id: String
    public var timestamp: Date
    public var kind: RuntimeChatStoredEventKind
    public var requestID: String
    public var sessionID: String
    public var model: String
    public var messages: [ChatMessage]?
    public var title: String?
    public var delta: String?
    public var reasoningDelta: String?
    public var finishReason: String?
    public var usage: RuntimeChatStoredUsage?
    public var error: RuntimeChatStoredError?
    public var ownerDeviceID: String?
    public var compactionMetadata: RuntimeChatCompactionMetadata?
    public var compactionResolution: RuntimeChatCompactionResolution?
    public var sourceAttributions: [RuntimeChatSourceAttribution]?
    public var assistantMessageID: String?
    public var sourceAttributionBindings: [RuntimeChatSourceAttributionBinding]?

    public init(
        id: String = UUID().uuidString,
        timestamp: Date = Date(),
        kind: RuntimeChatStoredEventKind,
        requestID: String,
        sessionID: String,
        model: String,
        messages: [ChatMessage]? = nil,
        title: String? = nil,
        delta: String? = nil,
        reasoningDelta: String? = nil,
        finishReason: String? = nil,
        usage: RuntimeChatStoredUsage? = nil,
        error: RuntimeChatStoredError? = nil,
        ownerDeviceID: String? = nil,
        compactionMetadata: RuntimeChatCompactionMetadata? = nil,
        compactionResolution: RuntimeChatCompactionResolution? = nil,
        sourceAttributions: [RuntimeChatSourceAttribution]? = nil,
        assistantMessageID: String? = nil,
        sourceAttributionBindings: [RuntimeChatSourceAttributionBinding]? = nil
    ) {
        self.id = id
        self.timestamp = timestamp
        self.kind = kind
        self.requestID = requestID
        self.sessionID = sessionID
        self.model = model
        self.messages = messages
        self.title = title
        self.delta = delta
        self.reasoningDelta = reasoningDelta
        self.finishReason = finishReason
        self.usage = usage
        self.error = error
        self.ownerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        self.compactionMetadata = compactionMetadata
        self.compactionResolution = compactionResolution
        self.sourceAttributions = sourceAttributions
        self.assistantMessageID = assistantMessageID
        self.sourceAttributionBindings = sourceAttributionBindings
    }

    enum CodingKeys: String, CodingKey {
        case id
        case timestamp
        case kind
        case requestID = "request_id"
        case sessionID = "session_id"
        case model
        case messages
        case title
        case delta
        case reasoningDelta = "reasoning_delta"
        case finishReason = "finish_reason"
        case usage
        case error
        case ownerDeviceID = "owner_device_id"
        case compactionMetadata = "compaction_metadata"
        case compactionResolution = "compaction_resolution"
        case sourceAttributions = "source_attributions"
        case assistantMessageID = "assistant_message_id"
        case sourceAttributionBindings = "source_attribution_bindings"
    }
}

public struct RuntimeChatStoredSession: Equatable, Sendable {
    public var sessionID: String
    public var title: String
    public var titleUpdatedAt: Date?
    public var titleRevision: Int
    public var model: String
    public var lastActivityAt: Date
    public var messageCount: Int
    public var status: String
    public var archivedAt: Date?
    public var lastEvent: String?
    public var lastFinishReason: String?
    public var lastErrorCode: String?
    public var search: RuntimeChatStoredSessionSearch?

    public init(
        sessionID: String,
        title: String,
        titleUpdatedAt: Date? = nil,
        titleRevision: Int = 0,
        model: String,
        lastActivityAt: Date,
        messageCount: Int,
        status: String = "active",
        archivedAt: Date? = nil,
        lastEvent: String? = nil,
        lastFinishReason: String? = nil,
        lastErrorCode: String? = nil,
        search: RuntimeChatStoredSessionSearch? = nil
    ) {
        self.sessionID = sessionID
        self.title = title
        self.titleUpdatedAt = titleUpdatedAt
        self.titleRevision = titleRevision
        self.model = model
        self.lastActivityAt = lastActivityAt
        self.messageCount = messageCount
        self.status = status
        self.archivedAt = archivedAt
        self.lastEvent = lastEvent
        self.lastFinishReason = lastFinishReason
        self.lastErrorCode = lastErrorCode
        self.search = search
    }
}

public struct RuntimeChatStoredSessionSearch: Equatable, Sendable {
    public var rank: Int
    public var snippet: String
    public var matchedFields: [String]

    public init(rank: Int, snippet: String, matchedFields: [String]) {
        self.rank = rank
        self.snippet = snippet
        self.matchedFields = matchedFields
    }
}

public struct RuntimeChatStoredMessage: Equatable, Sendable {
    public var role: String
    public var content: String
    public var reasoning: String?
    public var attachments: [ChatAttachment]
    public var createdAt: Date?
    public var sourceAttributions: [RuntimeChatSourceAttribution]
    public var assistantMessageID: String?

    public init(
        role: String,
        content: String,
        reasoning: String? = nil,
        attachments: [ChatAttachment] = [],
        createdAt: Date? = nil,
        sourceAttributions: [RuntimeChatSourceAttribution] = [],
        assistantMessageID: String? = nil
    ) {
        self.role = role
        self.content = content
        self.reasoning = reasoning
        self.attachments = attachments
        self.createdAt = createdAt
        self.sourceAttributions = sourceAttributions
        self.assistantMessageID = assistantMessageID
    }
}

public struct RuntimeChatSemanticSearchSource: Equatable, Sendable {
    public var session: RuntimeChatStoredSession
    public var messages: [RuntimeChatStoredMessage]
    public var sourceRevision: Int64?

    public init(
        session: RuntimeChatStoredSession,
        messages: [RuntimeChatStoredMessage],
        sourceRevision: Int64? = nil
    ) {
        self.session = session
        self.messages = messages
        self.sourceRevision = sourceRevision
    }
}

public struct RuntimeChatSemanticEmbeddingKey: Hashable, Sendable {
    public var ownerDeviceID: String?
    public var sessionID: String
    public var canonicalQualifiedEmbeddingModelID: String
    public var modelFingerprint: String
    public var documentFingerprint: String

    public init(
        ownerDeviceID: String?,
        sessionID: String,
        canonicalQualifiedEmbeddingModelID: String,
        modelFingerprint: String,
        documentFingerprint: String
    ) {
        self.ownerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        self.sessionID = sessionID
        self.canonicalQualifiedEmbeddingModelID = canonicalQualifiedEmbeddingModelID
        self.modelFingerprint = modelFingerprint
        self.documentFingerprint = documentFingerprint
    }
}

public struct RuntimeChatSemanticEmbeddingRecord: Equatable, Sendable {
    public var key: RuntimeChatSemanticEmbeddingKey
    public var embedding: [Double]
    public var sourceRevision: Int64?

    public init(
        key: RuntimeChatSemanticEmbeddingKey,
        embedding: [Double],
        sourceRevision: Int64? = nil
    ) {
        self.key = key
        self.embedding = embedding
        self.sourceRevision = sourceRevision
    }
}

public enum RuntimeChatEventStoreLimits {
    public static let maximumTargetedSessionSummaryCount = 10_000
}

struct RuntimeChatCompactionCalibrationStoreLimits: Equatable, Sendable {
    static let production = RuntimeChatCompactionCalibrationStoreLimits(
        jsonlByteCeiling: 64 * 1_024 * 1_024,
        jsonlLineCeiling: 50_000,
        jsonlLineByteCeiling: 4 * 1_024 * 1_024,
        sqliteTerminalScanCeiling: 50_000
    )

    var jsonlByteCeiling: Int
    var jsonlLineCeiling: Int
    var jsonlLineByteCeiling: Int
    var sqliteTerminalScanCeiling: Int

    init(
        jsonlByteCeiling: Int,
        jsonlLineCeiling: Int,
        jsonlLineByteCeiling: Int,
        sqliteTerminalScanCeiling: Int
    ) {
        self.jsonlByteCeiling = max(1, jsonlByteCeiling)
        self.jsonlLineCeiling = max(1, jsonlLineCeiling)
        self.jsonlLineByteCeiling = max(1, jsonlLineByteCeiling)
        self.sqliteTerminalScanCeiling = max(1, sqliteTerminalScanCeiling)
    }
}

func validatedTargetedSessionSummaryIDs(_ sessionIDs: [String]) throws -> [String] {
    guard sessionIDs.count <= RuntimeChatEventStoreLimits.maximumTargetedSessionSummaryCount else {
        throw RuntimeChatEventStoreError.targetedSessionSummaryLimitExceeded(
            maximum: RuntimeChatEventStoreLimits.maximumTargetedSessionSummaryCount
        )
    }
    var uniqueSessionIDs = Set<String>()
    uniqueSessionIDs.reserveCapacity(sessionIDs.count)
    for sessionID in sessionIDs {
        do {
            try runtimeResearchNotebookValidateBackingSessionID(sessionID)
        } catch {
            throw RuntimeChatEventStoreError.invalidTargetedSessionSummarySessionID
        }
        guard uniqueSessionIDs.insert(sessionID).inserted else {
            throw RuntimeChatEventStoreError.duplicateTargetedSessionSummarySessionID
        }
    }
    return sessionIDs
}

public protocol RuntimeChatEventStore: Sendable {
    func append(_ event: RuntimeChatStoredEvent) throws
    func chatCompactionCalibrationReport() throws -> RuntimeChatCompactionCalibrationReport
    func listSessions(ownerDeviceID: String?, limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession]
    func listSessionSummaries(
        ownerDeviceID: String?,
        sessionIDs: [String],
        includeArchived: Bool
    ) throws -> [RuntimeChatStoredSession]
    func listSessions(
        ownerDeviceID: String?,
        limit: Int,
        includeArchived: Bool,
        query: String?,
        embeddingModelID: String?
    ) throws -> [RuntimeChatStoredSession]
    func listAllSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession]
    func listMessages(ownerDeviceID: String?, sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage]
    func listSemanticSearchSources(
        ownerDeviceID: String?,
        sessionLimit: Int,
        messageLimit: Int,
        includeArchived: Bool
    ) throws -> [RuntimeChatSemanticSearchSource]
    func cachedSemanticEmbeddings(
        for keys: [RuntimeChatSemanticEmbeddingKey]
    ) throws -> [RuntimeChatSemanticEmbeddingRecord]
    func upsertSemanticEmbeddings(
        _ records: [RuntimeChatSemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws
    func listAllMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage]
    func resolveSourceAttribution(
        ownerDeviceID: String?,
        sessionID: String,
        assistantMessageID: String,
        sourceIndex: Int
    ) throws -> RuntimeChatResolvedSourceAttribution?
    func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult
    func mutateSessions(
        ownerDeviceID: String?,
        scope: RuntimeChatSessionBulkScope,
        limit: Int,
        requestID: String,
        timestamp: Date,
        beforeCommit: @Sendable ([String]) throws -> Void
    ) throws -> RuntimeChatSessionBulkMutationResult
    func performIfLongInactivityMemorySummarySourceCurrent(
        ownerDeviceID: String?,
        expectedDraft: RuntimeLongInactivityMemorySummarizationDraft,
        policy: RuntimeLongInactivityMemorySummarizationPolicy,
        operation: @Sendable () throws -> Void
    ) throws -> Bool
}

public struct RuntimeChatRetentionPolicy: Equatable, Sendable {
    public var deletedSessionRetentionInterval: TimeInterval
    public var deletedSessionPruneLimit: Int

    public init(
        deletedSessionRetentionInterval: TimeInterval,
        deletedSessionPruneLimit: Int
    ) {
        self.deletedSessionRetentionInterval = deletedSessionRetentionInterval
        self.deletedSessionPruneLimit = deletedSessionPruneLimit
    }

    public static let productionDefault = RuntimeChatRetentionPolicy(
        deletedSessionRetentionInterval: 90 * 24 * 60 * 60,
        deletedSessionPruneLimit: 100
    )
}

public struct RuntimeChatRetentionMaintenanceResult: Equatable, Sendable {
    public var deletedSessionPruneResult: RuntimeChatDeletedSessionPruneResult

    public var prunedDeletedSessionCount: Int {
        deletedSessionPruneResult.prunedSessionCount
    }

    public init(deletedSessionPruneResult: RuntimeChatDeletedSessionPruneResult) {
        self.deletedSessionPruneResult = deletedSessionPruneResult
    }
}

public enum RuntimeChatEventStoreDefaults {
    public static func productionStore(
        sqliteDatabaseURL: URL = SQLiteRuntimeChatEventStore.defaultDatabaseURL(),
        legacyJSONLFileURL: URL? = JSONLRuntimeChatEventStore.defaultFileURL()
    ) -> any RuntimeChatEventStore {
        SQLiteRuntimeChatEventStore(
            databaseURL: sqliteDatabaseURL,
            legacyJSONLFileURL: legacyJSONLFileURL
        )
    }

    public static func runProductionMaintenance(
        on store: any RuntimeChatEventStore,
        now: Date = Date(),
        policy: RuntimeChatRetentionPolicy = .productionDefault
    ) throws -> RuntimeChatRetentionMaintenanceResult {
        guard policy.deletedSessionRetentionInterval > 0,
              policy.deletedSessionPruneLimit > 0,
              let sqliteStore = store as? SQLiteRuntimeChatEventStore else {
            return RuntimeChatRetentionMaintenanceResult(
                deletedSessionPruneResult: RuntimeChatDeletedSessionPruneResult(
                    prunedSessionIDs: [],
                    prunedEventCount: 0
                )
            )
        }

        let cutoff = now.addingTimeInterval(-policy.deletedSessionRetentionInterval)
        return RuntimeChatRetentionMaintenanceResult(
            deletedSessionPruneResult: try sqliteStore.pruneDeletedSessionsBatch(
                deletedBefore: cutoff,
                limit: policy.deletedSessionPruneLimit
            )
        )
    }

    public static func runProductionMaintenance(
        on store: any RuntimeChatEventStore,
        ownerDeviceID: String?,
        now: Date = Date(),
        policy: RuntimeChatRetentionPolicy = .productionDefault
    ) throws -> RuntimeChatRetentionMaintenanceResult {
        guard policy.deletedSessionRetentionInterval > 0,
              policy.deletedSessionPruneLimit > 0,
              let sqliteStore = store as? SQLiteRuntimeChatEventStore else {
            return RuntimeChatRetentionMaintenanceResult(
                deletedSessionPruneResult: RuntimeChatDeletedSessionPruneResult(
                    prunedSessionIDs: [],
                    prunedEventCount: 0
                )
            )
        }

        let cutoff = now.addingTimeInterval(-policy.deletedSessionRetentionInterval)
        return RuntimeChatRetentionMaintenanceResult(
            deletedSessionPruneResult: try sqliteStore.pruneDeletedSessionsBatch(
                ownerDeviceID: ownerDeviceID,
                deletedBefore: cutoff,
                limit: policy.deletedSessionPruneLimit
            )
        )
    }
}

public extension RuntimeChatEventStore {
    func chatCompactionCalibrationReport() throws -> RuntimeChatCompactionCalibrationReport {
        RuntimeChatCompactionCalibrationReport()
    }

    func performIfLongInactivityMemorySummarySourceCurrent(
        ownerDeviceID: String?,
        expectedDraft: RuntimeLongInactivityMemorySummarizationDraft,
        policy: RuntimeLongInactivityMemorySummarizationPolicy,
        operation: @Sendable () throws -> Void
    ) throws -> Bool {
        let drafts = try listLongInactivityMemorySummarizationDrafts(
            ownerDeviceID: ownerDeviceID,
            policy: policy
        )
        guard let currentDraft = drafts.first(where: { $0.id == expectedDraft.id }),
              currentDraft.hasSameMemorySummarySource(as: expectedDraft) else {
            return false
        }
        try operation()
        return true
    }

    func resolveSourceAttribution(
        ownerDeviceID: String?,
        sessionID: String,
        assistantMessageID: String,
        sourceIndex: Int
    ) throws -> RuntimeChatResolvedSourceAttribution? {
        nil
    }
    func cachedSemanticEmbeddings(
        for keys: [RuntimeChatSemanticEmbeddingKey]
    ) throws -> [RuntimeChatSemanticEmbeddingRecord] {
        []
    }

    func upsertSemanticEmbeddings(
        _ records: [RuntimeChatSemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws {}

    func upsertSemanticEmbeddings(
        _ records: [RuntimeChatSemanticEmbeddingRecord]
    ) throws {
        try upsertSemanticEmbeddings(records, if: { true })
    }

    func listSemanticSearchSources(
        ownerDeviceID: String?,
        sessionLimit: Int,
        messageLimit: Int,
        includeArchived: Bool
    ) throws -> [RuntimeChatSemanticSearchSource] {
        guard sessionLimit > 0, messageLimit > 0 else { return [] }
        return try listSessions(
            ownerDeviceID: ownerDeviceID,
            limit: sessionLimit,
            includeArchived: includeArchived
        ).map { session in
            RuntimeChatSemanticSearchSource(
                session: session,
                messages: try listMessages(
                    ownerDeviceID: ownerDeviceID,
                    sessionID: session.sessionID,
                    limit: messageLimit
                )
            )
        }
    }

    func listSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        try listSessions(ownerDeviceID: nil, limit: limit, includeArchived: includeArchived)
    }

    func listSessions(
        ownerDeviceID: String?,
        limit: Int,
        includeArchived: Bool,
        query: String?
    ) throws -> [RuntimeChatStoredSession] {
        try listSessions(
            ownerDeviceID: ownerDeviceID,
            limit: limit,
            includeArchived: includeArchived,
            query: query,
            embeddingModelID: nil
        )
    }

    func listSessions(
        ownerDeviceID: String?,
        limit: Int,
        includeArchived: Bool,
        query: String?,
        embeddingModelID: String?
    ) throws -> [RuntimeChatStoredSession] {
        guard let searchQuery = RuntimeChatSessionSearchQuery(query) else {
            return try listSessions(ownerDeviceID: ownerDeviceID, limit: limit, includeArchived: includeArchived)
        }
        guard limit > 0 else { return [] }

        let candidates = try listSessions(
            ownerDeviceID: ownerDeviceID,
            limit: Int.max,
            includeArchived: includeArchived
        )
        var matches: [(session: RuntimeChatStoredSession, match: RuntimeChatSessionSearchMatch)] = []
        for session in candidates {
            let messages = try listMessages(ownerDeviceID: ownerDeviceID, sessionID: session.sessionID, limit: Int.max)
            if let match = session.runtimeSearchMatch(searchQuery, messages: messages) {
                matches.append((session, match))
            }
        }
        return matches
            .sorted { lhs, rhs in
                if lhs.match.score != rhs.match.score {
                    return lhs.match.score > rhs.match.score
                }
                if lhs.session.lastActivityAt != rhs.session.lastActivityAt {
                    return lhs.session.lastActivityAt > rhs.session.lastActivityAt
                }
                return lhs.session.sessionID < rhs.session.sessionID
            }
            .limited(to: limit)
            .enumerated()
            .map { offset, result in
                var session = result.session
                session.search = RuntimeChatStoredSessionSearch(
                    rank: offset + 1,
                    snippet: result.match.snippet,
                    matchedFields: result.match.matchedFields
                )
                return session
            }
    }

    func listSessions(limit: Int) throws -> [RuntimeChatStoredSession] {
        try listSessions(limit: limit, includeArchived: false)
    }

    func listAllSessions(limit: Int) throws -> [RuntimeChatStoredSession] {
        try listAllSessions(limit: limit, includeArchived: false)
    }

    func listMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        try listMessages(ownerDeviceID: nil, sessionID: sessionID, limit: limit)
    }

    func listAllMessages(sessionID: String) throws -> [RuntimeChatStoredMessage] {
        try listAllMessages(sessionID: sessionID, limit: 200)
    }

    func mutateSession(
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult {
        try mutateSession(
            ownerDeviceID: nil,
            sessionID: sessionID,
            requestID: requestID,
            mutation: mutation,
            timestamp: timestamp
        )
    }

    func mutateSessions(
        ownerDeviceID: String?,
        scope: RuntimeChatSessionBulkScope,
        limit: Int,
        requestID: String,
        timestamp: Date
    ) throws -> RuntimeChatSessionBulkMutationResult {
        try mutateSessions(
            ownerDeviceID: ownerDeviceID,
            scope: scope,
            limit: limit,
            requestID: requestID,
            timestamp: timestamp,
            beforeCommit: { _ in }
        )
    }

    func mutateSessions(
        ownerDeviceID: String?,
        scope: RuntimeChatSessionBulkScope,
        limit: Int,
        requestID: String,
        timestamp: Date,
        beforeCommit: @Sendable ([String]) throws -> Void
    ) throws -> RuntimeChatSessionBulkMutationResult {
        throw RuntimeChatEventStoreError.bulkMutationUnsupported
    }
}

public struct NullRuntimeChatEventStore: RuntimeChatEventStore {
    public init() {}

    public func append(_ event: RuntimeChatStoredEvent) throws {}

    public func listSessions(ownerDeviceID: String?, limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        []
    }

    public func listSessionSummaries(
        ownerDeviceID: String?,
        sessionIDs: [String],
        includeArchived: Bool
    ) throws -> [RuntimeChatStoredSession] {
        _ = try validatedTargetedSessionSummaryIDs(sessionIDs)
        return []
    }

    public func listAllSessions(limit: Int, includeArchived: Bool) throws -> [RuntimeChatStoredSession] {
        []
    }

    public func listMessages(ownerDeviceID: String?, sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        []
    }

    public func listAllMessages(sessionID: String, limit: Int) throws -> [RuntimeChatStoredMessage] {
        []
    }

    public func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date
    ) throws -> RuntimeChatSessionMutationResult {
        RuntimeChatSessionMutationResult(sessionID: sessionID, mutation: mutation, timestamp: timestamp)
    }

    public func mutateSessions(
        ownerDeviceID: String?,
        scope: RuntimeChatSessionBulkScope,
        limit: Int,
        requestID: String,
        timestamp: Date,
        beforeCommit: @Sendable ([String]) throws -> Void
    ) throws -> RuntimeChatSessionBulkMutationResult {
        try beforeCommit([])
        return RuntimeChatSessionBulkMutationResult(
            scope: scope,
            affectedSessionIDs: [],
            remainingCount: 0,
            timestamp: timestamp
        )
    }
}

struct RuntimeChatCompactionResolutionBindingKey: Hashable {
    var ownerDeviceID: String?
    var sessionID: String
    var requestID: String

    init(event: RuntimeChatStoredEvent) {
        self.init(
            ownerDeviceID: event.ownerDeviceID,
            sessionID: event.sessionID,
            requestID: event.requestID
        )
    }

    init(ownerDeviceID: String?, sessionID: String, requestID: String) {
        self.ownerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        self.sessionID = sessionID
        self.requestID = requestID
    }
}

struct RuntimeChatSessionProjectionKey: Hashable {
    var ownerDeviceID: String?
    var sessionID: String

    init(event: RuntimeChatStoredEvent) {
        self.init(ownerDeviceID: event.ownerDeviceID, sessionID: event.sessionID)
    }

    init(ownerDeviceID: String?, sessionID: String) {
        self.ownerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        self.sessionID = sessionID
    }
}

private struct RuntimeChatCompactionCalibrationScanEnvelope: Decodable {
    enum CalibrationPayloadShape: Equatable {
        case absent
        case object
        case malformed
    }

    var kind: RuntimeChatStoredEventKind
    var requestID: String
    var sessionID: String
    var ownerDeviceID: String?
    var hasCompactionResolution: Bool
    var calibrationPayloadShape: CalibrationPayloadShape

    enum CodingKeys: String, CodingKey {
        case kind
        case requestID = "request_id"
        case sessionID = "session_id"
        case ownerDeviceID = "owner_device_id"
        case compactionResolution = "compaction_resolution"
    }

    private enum ResolutionCodingKeys: String, CodingKey {
        case providerUsageCalibration = "provider_usage_calibration"
    }

    private enum CalibrationCodingKeys: CodingKey {}

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        kind = try container.decode(RuntimeChatStoredEventKind.self, forKey: .kind)
        requestID = try container.decode(String.self, forKey: .requestID)
        sessionID = try container.decode(String.self, forKey: .sessionID)
        ownerDeviceID = try container.decodeIfPresent(String.self, forKey: .ownerDeviceID)
        guard container.contains(.compactionResolution),
              (try? container.decodeNil(forKey: .compactionResolution)) == false else {
            hasCompactionResolution = false
            calibrationPayloadShape = .absent
            return
        }
        hasCompactionResolution = true
        guard let resolution = try? container.nestedContainer(
            keyedBy: ResolutionCodingKeys.self,
            forKey: .compactionResolution
        ) else {
            calibrationPayloadShape = .malformed
            return
        }
        guard resolution.contains(.providerUsageCalibration) else {
            calibrationPayloadShape = .absent
            return
        }
        calibrationPayloadShape = (try? resolution.nestedContainer(
            keyedBy: CalibrationCodingKeys.self,
            forKey: .providerUsageCalibration
        )) == nil ? .malformed : .object
    }
}

func isFullyEligibleRuntimeChatCompactionCalibrationEvent(
    _ event: RuntimeChatStoredEvent
) -> Bool {
    RuntimeChatCompactionCalibrationReport.build(from: [event]).sampledEligibleCount == 1
}

public final class JSONLRuntimeChatEventStore: RuntimeChatEventStore, @unchecked Sendable {
    private let fileURL: URL
    private let encoder: JSONEncoder
    private let calibrationReportStoreLimits: RuntimeChatCompactionCalibrationStoreLimits
    private let lock = NSLock()

    public init(fileURL: URL = JSONLRuntimeChatEventStore.defaultFileURL()) {
        self.fileURL = fileURL
        self.calibrationReportStoreLimits = .production
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
        self.encoder.outputFormatting = [.sortedKeys]
    }

    init(
        fileURL: URL,
        calibrationReportStoreLimits: RuntimeChatCompactionCalibrationStoreLimits
    ) {
        self.fileURL = fileURL
        self.calibrationReportStoreLimits = calibrationReportStoreLimits
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
        self.encoder.outputFormatting = [.sortedKeys]
    }

    public func append(_ event: RuntimeChatStoredEvent) throws {
        try lock.withLock {
            try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: fileURL) {
                try appendUnlocked(event)
            }
        }
    }

    public func chatCompactionCalibrationReport() throws -> RuntimeChatCompactionCalibrationReport {
        try lock.withLock {
            try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: fileURL) {
                RuntimeChatCompactionCalibrationReport.build(
                    from: try Self.calibrationReportEvents(
                        from: fileURL,
                        limits: calibrationReportStoreLimits
                    )
                )
            }
        }
    }

    public func listSessions(
        ownerDeviceID: String?,
        limit: Int = 100,
        includeArchived: Bool = false
    ) throws -> [RuntimeChatStoredSession] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try Self.sessions(
                from: readEvents(ownerDeviceID: ownerDeviceID),
                limit: limit,
                includeArchived: includeArchived
            )
        }
    }

    public func listSessionSummaries(
        ownerDeviceID: String?,
        sessionIDs: [String],
        includeArchived: Bool
    ) throws -> [RuntimeChatStoredSession] {
        let validatedSessionIDs = try validatedTargetedSessionSummaryIDs(sessionIDs)
        guard !validatedSessionIDs.isEmpty else { return [] }
        let requestedSessionIDs = Set(validatedSessionIDs)
        return try lock.withLock {
            let targetedEvents = try readEvents(
                ownerDeviceID: ownerDeviceID,
                sessionIDs: requestedSessionIDs
            )
            return try Self.sessions(
                from: targetedEvents,
                limit: validatedSessionIDs.count,
                includeArchived: includeArchived
            )
        }
    }

    public func listAllSessions(
        limit: Int = 100,
        includeArchived: Bool = false
    ) throws -> [RuntimeChatStoredSession] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try Self.sessions(
                from: readEvents(),
                limit: limit,
                includeArchived: includeArchived
            )
        }
    }

    public func listMessages(
        ownerDeviceID: String?,
        sessionID: String,
        limit: Int = 200
    ) throws -> [RuntimeChatStoredMessage] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            try Self.messages(from: readEvents(ownerDeviceID: ownerDeviceID), sessionID: sessionID, limit: limit)
        }
    }

    public func listSemanticSearchSources(
        ownerDeviceID: String?,
        sessionLimit: Int,
        messageLimit: Int,
        includeArchived: Bool
    ) throws -> [RuntimeChatSemanticSearchSource] {
        guard sessionLimit > 0, messageLimit > 0 else { return [] }
        return try lock.withLock {
            let events = try readEvents(ownerDeviceID: ownerDeviceID)
            return try Self.sessions(
                from: events,
                limit: sessionLimit,
                includeArchived: includeArchived
            ).map { session in
                RuntimeChatSemanticSearchSource(
                    session: session,
                    messages: Self.messages(
                        from: events,
                        sessionID: session.sessionID,
                        limit: messageLimit
                    )
                )
            }
        }
    }

    public func listAllMessages(
        sessionID: String,
        limit: Int = 200
    ) throws -> [RuntimeChatStoredMessage] {
        guard limit > 0 else { return [] }
        return try lock.withLock {
            let events = try readEvents()
            let keys = Self.sessionProjectionKeys(from: events, sessionID: sessionID)
            guard keys.count <= 1 else {
                throw RuntimeChatHostWideProjectionError.ambiguousSessionID(sessionID)
            }
            guard let key = keys.first else { return [] }
            return Self.messages(from: events, key: key, limit: limit)
        }
    }

    public func performIfLongInactivityMemorySummarySourceCurrent(
        ownerDeviceID: String?,
        expectedDraft: RuntimeLongInactivityMemorySummarizationDraft,
        policy: RuntimeLongInactivityMemorySummarizationPolicy,
        operation: @Sendable () throws -> Void
    ) throws -> Bool {
        try lock.withLock {
            try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: fileURL) {
                let indexedEvents = try Self.decodedEventsInAppendOrder(from: fileURL)
                try Self.validateCompactionResolutionBindings(indexedEvents)
                let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
                let events = indexedEvents.map(\.event).filter {
                    $0.ownerDeviceID == scopedOwnerDeviceID
                }
                let sessions = try Self.sessions(
                    from: events,
                    limit: Int.max,
                    includeArchived: false
                )
                guard let candidate = policy.candidates(from: sessions, now: Date())
                        .first(where: {
                            $0.sessionID == expectedDraft.candidate.sessionID
                        }),
                      let currentDraft = policy.draft(
                        for: candidate,
                        messages: Self.messages(
                            from: events,
                            sessionID: candidate.sessionID,
                            limit: Int.max
                        )
                      ),
                      currentDraft.hasSameMemorySummarySource(as: expectedDraft) else {
                    return false
                }
                try operation()
                return true
            }
        }
    }

    public func resolveSourceAttribution(
        ownerDeviceID: String?,
        sessionID: String,
        assistantMessageID: String,
        sourceIndex: Int
    ) throws -> RuntimeChatResolvedSourceAttribution? {
        try lock.withLock {
            Self.resolvedSourceAttribution(
                from: try readEvents(ownerDeviceID: ownerDeviceID),
                sessionID: sessionID,
                assistantMessageID: assistantMessageID,
                sourceIndex: sourceIndex
            )
        }
    }

    public func mutateSession(
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation,
        timestamp: Date = Date()
    ) throws -> RuntimeChatSessionMutationResult {
        try lock.withLock {
            try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: fileURL) {
                let cleanSessionID = sessionID.trimmingCharacters(in: .whitespacesAndNewlines)
                let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
                let events = try readEvents(ownerDeviceID: scopedOwnerDeviceID)
                let sessionEvents = events.filter { $0.sessionID == cleanSessionID }
                let lifecycleState = Self.lifecycleState(from: sessionEvents)
                guard !cleanSessionID.isEmpty,
                      !sessionEvents.isEmpty,
                      lifecycleState != .deleted else {
                    throw RuntimeChatEventStoreError.sessionNotFound(sessionID)
                }
                if mutation == .delete, lifecycleState != .archived {
                    throw RuntimeChatEventStoreError.sessionMustBeArchivedBeforeDelete(cleanSessionID)
                }
                try appendUnlocked(RuntimeChatStoredEvent(
                    timestamp: timestamp,
                    kind: mutation.eventKind,
                    requestID: requestID,
                    sessionID: cleanSessionID,
                    model: Self.latestModel(from: sessionEvents),
                    ownerDeviceID: scopedOwnerDeviceID
                ))
                return RuntimeChatSessionMutationResult(
                    sessionID: cleanSessionID,
                    mutation: mutation,
                    timestamp: timestamp
                )
            }
        }
    }

    public func mutateSessions(
        ownerDeviceID: String?,
        scope: RuntimeChatSessionBulkScope,
        limit: Int,
        requestID: String,
        timestamp: Date = Date(),
        beforeCommit: @Sendable ([String]) throws -> Void = { _ in }
    ) throws -> RuntimeChatSessionBulkMutationResult {
        let boundedLimit = max(1, min(limit, 200))
        return try lock.withLock {
            try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: fileURL) {
                let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
                let ownerEvents = try readEvents(ownerDeviceID: scopedOwnerDeviceID)
                let targets = try Self.sessions(
                    from: ownerEvents,
                    limit: Int.max,
                    includeArchived: true
                ).filter { session in
                    switch scope {
                    case .allActive: session.status == RuntimeChatSessionLifecycleState.active.rawValue
                    case .allArchived: session.status == RuntimeChatSessionLifecycleState.archived.rawValue
                    }
                }
                let selected = Array(targets.prefix(boundedLimit))
                let eventsBySessionID = Dictionary(grouping: ownerEvents, by: \.sessionID)
                let selectedIDs = selected.map(\.sessionID)
                try beforeCommit(selectedIDs)
                let mutationEvents = selected.map { session in
                    RuntimeChatStoredEvent(
                        timestamp: timestamp,
                        kind: scope.mutation.eventKind,
                        requestID: requestID,
                        sessionID: session.sessionID,
                        model: Self.latestModel(from: eventsBySessionID[session.sessionID] ?? []),
                        ownerDeviceID: scopedOwnerDeviceID
                    )
                }
                try appendBatchAtomicallyUnlocked(mutationEvents)
                return RuntimeChatSessionBulkMutationResult(
                    scope: scope,
                    affectedSessionIDs: selectedIDs,
                    remainingCount: targets.count - selected.count,
                    timestamp: timestamp
                )
            }
        }
    }

    public static func defaultFileURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-chat-events.jsonl", isDirectory: false)
    }

    private func readEvents(ownerDeviceID: String?) throws -> [RuntimeChatStoredEvent] {
        let scopedOwnerDeviceID = ownerDeviceID.normalizedOwnerDeviceID
        return try readEvents().filter {
            $0.ownerDeviceID.normalizedOwnerDeviceID == scopedOwnerDeviceID
        }
    }

    private func readEvents(
        ownerDeviceID: String?,
        sessionIDs: Set<String>
    ) throws -> [RuntimeChatStoredEvent] {
        try Self.events(
            from: fileURL,
            ownerDeviceID: ownerDeviceID.normalizedOwnerDeviceID,
            sessionIDs: sessionIDs
        )
    }

    private func readEvents() throws -> [RuntimeChatStoredEvent] {
        try Self.events(from: fileURL)
    }

    static func events(from fileURL: URL) throws -> [RuntimeChatStoredEvent] {
        try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: fileURL) {
            let indexedEvents = try decodedEventsInAppendOrder(from: fileURL)
            try validateCompactionResolutionBindings(indexedEvents)
            return indexedEvents.map(\.event)
        }
    }

    private static func events(
        from fileURL: URL,
        ownerDeviceID: String?,
        sessionIDs: Set<String>
    ) throws -> [RuntimeChatStoredEvent] {
        try RuntimeEventLogFileProtection.withExclusiveFileAccess(to: fileURL) {
            let indexedEvents = try decodedEventsInAppendOrder(from: fileURL)
            try validateCompactionResolutionBindings(indexedEvents)
            return indexedEvents
                .filter { indexedEvent in
                    indexedEvent.event.ownerDeviceID.normalizedOwnerDeviceID == ownerDeviceID
                        && sessionIDs.contains(indexedEvent.event.sessionID)
                }
                .map(\.event)
        }
    }

    private static func decodedEventsInAppendOrder(
        from fileURL: URL
    ) throws -> [(line: Int, event: RuntimeChatStoredEvent)] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let data = try Data(contentsOf: fileURL)
        guard !data.isEmpty else { return [] }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let lines = String(decoding: data, as: UTF8.self)
            .components(separatedBy: .newlines)
        var events: [(line: Int, event: RuntimeChatStoredEvent)] = []
        for (index, line) in lines.enumerated() {
            guard !line.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                continue
            }
            let lineData = Data(line.utf8)
            do {
                let decoded = try decoder.decode(RuntimeChatStoredEvent.self, from: lineData)
                let event = Self.projectingLegacyTitleForReplay(decoded)
                try Self.validateStoredEvent(event, line: index + 1)
                events.append((line: index + 1, event: event))
            } catch {
                if let storeError = error as? RuntimeChatEventStoreError {
                    throw storeError
                }
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: index + 1,
                    reason: Self.decodeFailureReason(error)
                )
            }
        }
        return events
    }

    static func validateCompactionResolutionBindings(
        _ indexedEvents: [(line: Int, event: RuntimeChatStoredEvent)]
    ) throws {
        var latestRequests: [RuntimeChatCompactionResolutionBindingKey: RuntimeChatStoredEvent] = [:]
        var terminalBindings: Set<RuntimeChatCompactionResolutionBindingKey> = []
        for indexedEvent in indexedEvents {
            let event = indexedEvent.event
            let key = RuntimeChatCompactionResolutionBindingKey(event: event)
            if event.kind == .request {
                latestRequests[key] = event
                continue
            }
            guard let resolution = event.compactionResolution else { continue }
            guard terminalBindings.insert(key).inserted else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: indexedEvent.line,
                    reason: "chat compaction binding has duplicate terminal resolution"
                )
            }
            guard let request = latestRequests[key],
                  let metadata = request.compactionMetadata,
                  metadata.strategy == "adaptive_backend_only_summary_v3" else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: indexedEvent.line,
                    reason: "chat compaction resolution is not bound to an adaptive v3 request"
                )
            }
            guard metadata.estimatorIdentifier == resolution.estimatorIdentifier,
                  metadata.inputBudgetTokens == resolution.inputBudgetTokens else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: indexedEvent.line,
                    reason: "chat compaction resolution does not match request accounting"
                )
            }
            if resolution.summaryMethod == "deterministic_preview_v1",
               metadata.estimatedInputTokensAfter != resolution.estimatedInputTokensAfter {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: indexedEvent.line,
                    reason: "deterministic chat compaction resolution does not match request estimate"
                )
            }
        }
    }

    private static let calibrationReportJSONLReadChunkSize = 64 * 1_024

    private static func calibrationReportEvents(
        from fileURL: URL,
        limits: RuntimeChatCompactionCalibrationStoreLimits
    ) throws -> [RuntimeChatStoredEvent] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let handle = try FileHandle(forReadingFrom: fileURL)
        defer { try? handle.close() }

        var position = try handle.seekToEnd()
        guard position > 0 else { return [] }

        typealias ScannedEvent = (reverseOrdinal: Int, event: RuntimeChatStoredEvent)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        var carriedPrefix = Data()
        var scannedBytes = 0
        var scannedLines = 0
        var reverseOrdinal = 0
        var selectedTerminals: [ScannedEvent] = []
        var selectedRequests: [RuntimeChatCompactionResolutionBindingKey: ScannedEvent] = [:]
        var unresolvedRequestKeys: Set<RuntimeChatCompactionResolutionBindingKey> = []
        var terminalBindings: Set<RuntimeChatCompactionResolutionBindingKey> = []

        func decodeStoredEvent(_ data: Data, validating: Bool) throws -> RuntimeChatStoredEvent {
            do {
                let decoded = try decoder.decode(RuntimeChatStoredEvent.self, from: data)
                let event = projectingLegacyTitleForReplay(decoded)
                if validating {
                    try validateStoredEvent(event, line: 0)
                }
                return event
            } catch {
                if let storeError = error as? RuntimeChatEventStoreError {
                    throw storeError
                }
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: 0,
                    reason: decodeFailureReason(error)
                )
            }
        }

        func processLine(_ data: Data) throws {
            guard !String(decoding: data, as: UTF8.self)
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .isEmpty else {
                return
            }
            guard scannedLines < limits.jsonlLineCeiling else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: 0,
                    reason: "chat compaction calibration JSONL tail exceeds the line ceiling"
                )
            }
            guard data.count <= limits.jsonlLineByteCeiling else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: 0,
                    reason: "chat compaction calibration JSONL record exceeds the byte ceiling"
                )
            }
            scannedLines += 1
            reverseOrdinal += 1

            let envelope: RuntimeChatCompactionCalibrationScanEnvelope
            do {
                envelope = try decoder.decode(
                    RuntimeChatCompactionCalibrationScanEnvelope.self,
                    from: data
                )
            } catch {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: 0,
                    reason: decodeFailureReason(error)
                )
            }
            let key = RuntimeChatCompactionResolutionBindingKey(
                ownerDeviceID: envelope.ownerDeviceID,
                sessionID: envelope.sessionID,
                requestID: envelope.requestID
            )

            if envelope.calibrationPayloadShape == .malformed {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: 0,
                    reason: "chat provider usage calibration payload is not an object"
                )
            }

            if envelope.hasCompactionResolution {
                switch envelope.kind {
                case .done, .cancelled, .error:
                    guard terminalBindings.insert(key).inserted else {
                        throw RuntimeChatEventStoreError.corruptEventLog(
                            line: 0,
                            reason: "chat compaction binding has duplicate terminal resolution"
                        )
                    }
                default:
                    throw RuntimeChatEventStoreError.corruptEventLog(
                        line: 0,
                        reason: "chat compaction resolution is only valid on terminal events"
                    )
                }
            }

            if envelope.kind == .request, unresolvedRequestKeys.contains(key) {
                let request = try decodeStoredEvent(data, validating: true)
                selectedRequests[key] = (reverseOrdinal, request)
                unresolvedRequestKeys.remove(key)
            }

            guard envelope.kind == .done,
                  envelope.calibrationPayloadShape == .object,
                  selectedTerminals.count
                    < RuntimeChatCompactionCalibrationReport.recentEligibleSampleCap else {
                return
            }
            let candidate = try decodeStoredEvent(data, validating: false)
            guard isFullyEligibleRuntimeChatCompactionCalibrationEvent(candidate) else { return }
            try validateStoredEvent(candidate, line: 0)
            selectedTerminals.append((reverseOrdinal, candidate))
            unresolvedRequestKeys.insert(key)
        }

        func hasCompleteTail() -> Bool {
            selectedTerminals.count
                == RuntimeChatCompactionCalibrationReport.recentEligibleSampleCap
                && unresolvedRequestKeys.isEmpty
        }

        var stoppedAtResourceCeiling = false
        scanLoop: while position > 0 {
            if hasCompleteTail() { break }
            let remainingByteBudget = limits.jsonlByteCeiling - scannedBytes
            guard remainingByteBudget > 0 else {
                stoppedAtResourceCeiling = true
                break
            }
            let chunkSize = min(
                calibrationReportJSONLReadChunkSize,
                remainingByteBudget,
                Int(position)
            )
            position -= UInt64(chunkSize)
            try handle.seek(toOffset: position)
            guard let chunk = try handle.read(upToCount: chunkSize), chunk.count == chunkSize else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: 0,
                    reason: "chat compaction calibration JSONL tail changed while reading"
                )
            }
            scannedBytes += chunk.count
            var buffer = chunk
            buffer.append(carriedPrefix)
            var lineEnd = buffer.endIndex
            while let newline = buffer[..<lineEnd].lastIndex(of: 0x0A) {
                let lineStart = buffer.index(after: newline)
                try processLine(Data(buffer[lineStart..<lineEnd]))
                if hasCompleteTail() { break scanLoop }
                lineEnd = newline
            }
            carriedPrefix = Data(buffer[..<lineEnd])
            if carriedPrefix.count > limits.jsonlLineByteCeiling {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: 0,
                    reason: "chat compaction calibration JSONL record exceeds the byte ceiling"
                )
            }
        }

        if position == 0, !hasCompleteTail(), !carriedPrefix.isEmpty {
            try processLine(carriedPrefix)
        }
        if stoppedAtResourceCeiling || (position > 0 && !hasCompleteTail()) {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: 0,
                reason: "chat compaction calibration JSONL tail exceeds the scan ceiling"
            )
        }
        guard unresolvedRequestKeys.isEmpty else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: 0,
                reason: "chat compaction calibration request binding is outside the bounded JSONL tail"
            )
        }

        let validationEvents = (Array(selectedRequests.values) + selectedTerminals)
            .sorted { $0.reverseOrdinal > $1.reverseOrdinal }
            .map { (line: 0, event: $0.event) }
        try validateCompactionResolutionBindings(validationEvents)
        return selectedTerminals
            .sorted { $0.reverseOrdinal > $1.reverseOrdinal }
            .map(\.event)
    }

    private static func decodeFailureReason(_ error: Error) -> String {
        if let decodingError = error as? DecodingError {
            switch decodingError {
            case .dataCorrupted:
                return "data corrupted"
            case .keyNotFound(let key, _):
                return "missing key '\(key.stringValue)'"
            case .typeMismatch(let type, _):
                return "type mismatch for \(type)"
            case .valueNotFound(let type, _):
                return "missing value for \(type)"
            @unknown default:
                return "decode failed"
            }
        }
        return "decode failed"
    }

    static func validateStoredEvent(_ event: RuntimeChatStoredEvent, line: Int) throws {
        try requireNonBlank(event.id, line: line, reason: "chat event id is empty")
        try requireNonBlank(event.requestID, line: line, reason: "chat request id is empty")
        try requireNonBlank(event.sessionID, line: line, reason: "chat session id is empty")
        if let compactionMetadata = event.compactionMetadata {
            guard event.kind == .request else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction metadata is only valid on request events"
                )
            }
            try validateCompactionMetadata(compactionMetadata, event: event, line: line)
        }
        if let compactionResolution = event.compactionResolution {
            guard event.kind == .done || event.kind == .cancelled || event.kind == .error else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction resolution is only valid on terminal events"
                )
            }
            try validateCompactionResolution(compactionResolution, event: event, line: line)
        }
        if let sourceAttributions = event.sourceAttributions {
            guard event.kind == .done, event.finishReason == "stop" else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat source attributions are only valid on stop completion events"
                )
            }
            guard !sourceAttributions.isEmpty,
                  sourceAttributions.count <= runtimeTrustedSourceChatContextGrantLimitCeiling else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat source attribution count is invalid"
                )
            }
            for (offset, attribution) in sourceAttributions.enumerated() {
                guard attribution.sourceIndex == offset + 1,
                      runtimeDocumentIndexCanonicalDisplayName(attribution.documentName) == attribution.documentName,
                      runtimeDocumentIndexCanonicalMimeType(attribution.mimeType) == attribution.mimeType,
                      attribution.chunkIndex >= 0 else {
                    throw RuntimeChatEventStoreError.corruptEventLog(
                        line: line,
                        reason: "chat source attribution is not canonical"
                    )
                }
            }
        }
        let hasResolutionMetadata = event.assistantMessageID != nil
            || event.sourceAttributionBindings != nil
        if hasResolutionMetadata {
            guard let sourceAttributions = event.sourceAttributions,
                  let assistantMessageID = event.assistantMessageID,
                  runtimeChatCanonicalAssistantMessageID(assistantMessageID) == assistantMessageID,
                  let bindings = event.sourceAttributionBindings,
                  bindings.count == sourceAttributions.count else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat source attribution bindings are incomplete"
                )
            }
            for (offset, binding) in bindings.enumerated() {
                guard binding.sourceIndex == offset + 1,
                      binding.sourceIndex == sourceAttributions[offset].sourceIndex,
                      runtimeDocumentIndexCanonicalSourceAnchorID(binding.sourceAnchorID) == binding.sourceAnchorID,
                      runtimeDocumentIndexCanonicalDocumentID(binding.documentID) == binding.documentID,
                      runtimeDocumentCanonicalSourceRevision(binding.sourceRevision) == binding.sourceRevision else {
                    throw RuntimeChatEventStoreError.corruptEventLog(
                        line: line,
                        reason: "chat source attribution binding is not canonical"
                    )
                }
            }
        }

        switch event.kind {
        case .request:
            guard let messages = event.messages, !messages.isEmpty else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat request messages are empty"
                )
            }
            for message in messages {
                try requireNonBlank(message.role, line: line, reason: "chat request message role is empty")
            }
        case .title:
            try requireCanonicalChatTitle(event.title, line: line)
        case .assistantDelta:
            try requireNonEmpty(event.delta, line: line, reason: "chat assistant delta is empty")
        case .reasoningDelta:
            try requireNonEmpty(event.reasoningDelta, line: line, reason: "chat reasoning delta is empty")
        case .error:
            guard let error = event.error else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat error payload is missing"
                )
            }
            try requireNonBlank(error.code, line: line, reason: "chat error code is empty")
            try requireNonBlank(error.message, line: line, reason: "chat error message is empty")
        case .done, .cancelled, .archived, .restored, .deleted:
            break
        }
    }

    private static func requireCanonicalChatTitle(_ value: String?, line: Int) throws {
        guard let value else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "chat title is empty"
            )
        }
        let normalized = value.precomposedStringWithCanonicalMapping
        guard !normalized.isEmpty,
              value.unicodeScalars.elementsEqual(normalized.unicodeScalars),
              value == value.trimmingCharacters(in: .whitespacesAndNewlines),
              value.unicodeScalars.count <= RuntimeResearchNotebook.maximumTitleCharacters,
              value.unicodeScalars.allSatisfy({
                  !CharacterSet.controlCharacters.contains($0)
              }) else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "chat title is not canonical or exceeds the title limit"
            )
        }
    }

    static func projectingLegacyTitleForReplay(
        _ event: RuntimeChatStoredEvent
    ) -> RuntimeChatStoredEvent {
        guard event.kind == .title, let title = event.title, !title.isEmpty else {
            return event
        }
        var projectedEvent = event
        projectedEvent.title = legacyCanonicalChatTitleProjection(title)
        return projectedEvent
    }

    private static func legacyCanonicalChatTitleProjection(_ value: String) -> String {
        let controlFree = String(String.UnicodeScalarView(
            value.unicodeScalars.filter { !CharacterSet.controlCharacters.contains($0) }
        ))
        let normalized = controlFree
            .precomposedStringWithCanonicalMapping
            .trimmingCharacters(in: .whitespacesAndNewlines)
        var scalarCount = 0
        var bounded = ""
        for character in normalized {
            let characterScalarCount = String(character).unicodeScalars.count
            guard scalarCount + characterScalarCount <= RuntimeResearchNotebook.maximumTitleCharacters else {
                break
            }
            bounded.append(character)
            scalarCount += characterScalarCount
        }
        let projected = bounded.trimmingCharacters(in: .whitespacesAndNewlines)
        return projected.isEmpty ? defaultSessionTitle : projected
    }

    private static func validateCompactionMetadata(
        _ metadata: RuntimeChatCompactionMetadata,
        event: RuntimeChatStoredEvent,
        line: Int
    ) throws {
        try requireNonBlank(metadata.strategy, line: line, reason: "chat compaction strategy is empty")
        let accountingPresence = [
            metadata.estimatorIdentifier != nil,
            metadata.contextWindowTokens != nil,
            metadata.outputReserveTokens != nil,
            metadata.inputBudgetTokens != nil,
            metadata.estimatedInputTokensBefore != nil,
            metadata.estimatedInputTokensAfter != nil,
        ]
        let hasAccounting = accountingPresence.allSatisfy { $0 }
        guard hasAccounting || accountingPresence.allSatisfy({ !$0 }) else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "chat compaction accounting fields must be all present or all absent"
            )
        }
        let adaptiveStrategies = [
            "adaptive_backend_only_summary_v2",
            "adaptive_backend_only_summary_v3",
        ]
        if adaptiveStrategies.contains(metadata.strategy) && !hasAccounting {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "adaptive chat compaction accounting is missing"
            )
        }
        let policyPresence = [metadata.estimateKind != nil, metadata.summaryPolicy != nil]
        let hasPolicy = policyPresence.allSatisfy { $0 }
        guard hasPolicy || policyPresence.allSatisfy({ !$0 }) else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "chat compaction estimate policy fields must be all present or all absent"
            )
        }
        if metadata.strategy == "adaptive_backend_only_summary_v3" {
            let supportedSummaryPolicies = [
                "llm_prepass_with_deterministic_fallback_v1",
                "llm_prepass_with_incremental_lineage_v2",
            ]
            guard metadata.estimateKind == "planned_upper_bound",
                  metadata.summaryPolicy.map(supportedSummaryPolicies.contains) == true else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "adaptive v3 chat compaction estimate policy is invalid"
                )
            }
        }
        if hasAccounting {
            try requireNonBlank(
                metadata.estimatorIdentifier,
                line: line,
                reason: "chat compaction estimator identifier is empty"
            )
            guard let contextWindowTokens = metadata.contextWindowTokens,
                  let outputReserveTokens = metadata.outputReserveTokens,
                  let inputBudgetTokens = metadata.inputBudgetTokens,
                  let estimatedInputTokensBefore = metadata.estimatedInputTokensBefore,
                  let estimatedInputTokensAfter = metadata.estimatedInputTokensAfter,
                  contextWindowTokens > 0,
                  outputReserveTokens >= 0,
                  inputBudgetTokens > 0,
                  estimatedInputTokensBefore >= 0,
                  estimatedInputTokensAfter >= 0 else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction accounting token counts are invalid"
                )
            }
            guard contextWindowTokens > outputReserveTokens else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction context window must exceed output reserve"
                )
            }
            guard inputBudgetTokens == contextWindowTokens - outputReserveTokens else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction input budget is inconsistent"
                )
            }
            guard estimatedInputTokensBefore > inputBudgetTokens else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction input estimate did not exceed budget"
                )
            }
            guard estimatedInputTokensAfter <= inputBudgetTokens else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction output estimate exceeds input budget"
                )
            }
        }
        guard !metadata.sourcePointers.isEmpty else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "chat compaction source pointers are empty"
            )
        }
        for pointer in metadata.sourcePointers {
            try requireNonBlank(pointer.sourceKind, line: line, reason: "chat compaction source kind is empty")
            try requireNonBlank(pointer.sessionID, line: line, reason: "chat compaction session id is empty")
            try requireNonBlank(pointer.requestID, line: line, reason: "chat compaction request id is empty")
            guard pointer.startTurn > 0,
                  pointer.endTurn >= pointer.startTurn,
                  pointer.totalTurns >= pointer.endTurn,
                  pointer.compactedTurnCount == pointer.endTurn - pointer.startTurn + 1,
                  pointer.retainedTurnCount >= 0 else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction source pointer range is invalid"
                )
            }
            if let retainedStartTurn = pointer.retainedStartTurn {
                guard retainedStartTurn > pointer.endTurn else {
                    throw RuntimeChatEventStoreError.corruptEventLog(
                        line: line,
                        reason: "chat compaction retained range starts before compacted range"
                    )
                }
            }
            if let retainedEndTurn = pointer.retainedEndTurn {
                guard retainedEndTurn > 0,
                      retainedEndTurn <= pointer.totalTurns else {
                    throw RuntimeChatEventStoreError.corruptEventLog(
                        line: line,
                        reason: "chat compaction retained range exceeds total turns"
                    )
                }
            }
            let fingerprintPresence = [
                pointer.sourceFingerprintAlgorithm != nil,
                pointer.sourceFingerprint != nil,
                pointer.sourceCanonicalByteCount != nil,
            ]
            let hasFingerprint = fingerprintPresence.allSatisfy { $0 }
            guard hasFingerprint || fingerprintPresence.allSatisfy({ !$0 }) else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction source fingerprint fields must be all present or all absent"
                )
            }
            if hasFingerprint {
                guard pointer.sourceFingerprintAlgorithm == RuntimeChatCompactionSourceFingerprinter.algorithm,
                      let sourceFingerprint = pointer.sourceFingerprint,
                      sourceFingerprint.range(
                        of: "^[0-9a-f]{64}$",
                        options: .regularExpression
                      ) != nil,
                      let sourceCanonicalByteCount = pointer.sourceCanonicalByteCount,
                      sourceCanonicalByteCount > 0 else {
                    throw RuntimeChatEventStoreError.corruptEventLog(
                        line: line,
                        reason: "chat compaction source fingerprint is invalid"
                    )
                }
            }
        }
        if adaptiveStrategies.contains(metadata.strategy) {
            guard metadata.sourcePointers.count == 1,
                  let pointer = metadata.sourcePointers.first,
                  pointer.sourceKind == "client_visible_conversation_turns",
                  pointer.sessionID == event.sessionID,
                  pointer.requestID == event.requestID,
                  pointer.startTurn == 1,
                  pointer.endTurn < pointer.totalTurns,
                  pointer.retainedStartTurn == pointer.endTurn + 1,
                  pointer.retainedEndTurn == pointer.totalTurns,
                  pointer.retainedTurnCount == pointer.totalTurns - pointer.compactedTurnCount else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "adaptive chat compaction source pointer is inconsistent with request event"
                )
            }
        }
        if metadata.strategy == "adaptive_backend_only_summary_v3" {
            guard let pointer = metadata.sourcePointers.first,
                  pointer.retainedStartTurn != nil,
                  pointer.retainedEndTurn != nil,
                  pointer.sourceFingerprint != nil,
                  pointer.sourceCanonicalByteCount != nil else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "adaptive v3 chat compaction source binding is missing"
                )
            }
        }
        for pointer in metadata.sourcePointers where pointer.sourceFingerprint != nil {
            guard let sourceFingerprint = pointer.sourceFingerprint,
                  let sourceCanonicalByteCount = pointer.sourceCanonicalByteCount,
                  let messages = event.messages else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction source binding is missing request messages"
                )
            }
            let conversationMessages = messages.filter { message in
                let role = message.role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
                return role == "user" || role == "assistant"
            }
            guard conversationMessages.count == pointer.totalTurns,
                  pointer.startTurn > 0,
                  pointer.endTurn <= conversationMessages.count else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction source turns do not match the request event"
                )
            }
            let selectedMessages = Array(
                conversationMessages[(pointer.startTurn - 1)..<pointer.endTurn]
            )
            let recomputed = RuntimeChatCompactionSourceFingerprinter.fingerprint(
                pointer: pointer,
                messages: selectedMessages
            )
            guard recomputed.canonicalByteCount == sourceCanonicalByteCount,
                  constantTimeEqual(recomputed.digest, sourceFingerprint) else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction source fingerprint does not match the request event"
                )
            }
        }
    }

    private static func constantTimeEqual(_ lhs: String, _ rhs: String) -> Bool {
        let left = Array(lhs.utf8)
        let right = Array(rhs.utf8)
        guard left.count == right.count else { return false }
        var difference: UInt8 = 0
        for index in left.indices {
            difference |= left[index] ^ right[index]
        }
        return difference == 0
    }

    private static func validateCompactionResolution(
        _ resolution: RuntimeChatCompactionResolution,
        event: RuntimeChatStoredEvent,
        line: Int
    ) throws {
        try requireNonBlank(
            resolution.estimatorIdentifier,
            line: line,
            reason: "chat compaction resolution estimator identifier is empty"
        )
        guard resolution.inputBudgetTokens > 0 else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "chat compaction resolution input budget is invalid"
            )
        }
        if resolution.primaryDispatched {
            guard resolution.summaryMethod == "deterministic_preview_v1"
                    || resolution.summaryMethod == "llm_summary_v1",
                  let estimatedInputTokensAfter = resolution.estimatedInputTokensAfter,
                  estimatedInputTokensAfter >= 0,
                  estimatedInputTokensAfter <= resolution.inputBudgetTokens else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "dispatched chat compaction resolution is invalid"
                )
            }
        } else {
            guard resolution.summaryMethod == nil,
                  resolution.estimatedInputTokensAfter == nil,
                  resolution.resolvedProviderQualifiedModelID == nil,
                  resolution.providerUsageCalibration == nil,
                  event.kind != .done else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "undispatched chat compaction resolution is invalid"
                )
            }
        }
        if let resolvedProviderQualifiedModelID = resolution.resolvedProviderQualifiedModelID {
            guard let resolved = ModelProvider.splitQualifiedModelID(resolvedProviderQualifiedModelID),
                  !resolved.modelID.isEmpty,
                  canonicalProviderModelID(resolved.modelID) == resolved.modelID,
                  resolved.provider.qualifiedModelID(resolved.modelID) == resolvedProviderQualifiedModelID else {
                throw RuntimeChatEventStoreError.corruptEventLog(
                    line: line,
                    reason: "chat compaction resolved provider model binding is invalid"
                )
            }
        }
        if let calibration = resolution.providerUsageCalibration {
            try validateProviderUsageCalibration(
                calibration,
                resolution: resolution,
                event: event,
                line: line
            )
        }
    }

    private static func validateProviderUsageCalibration(
        _ calibration: RuntimeChatProviderUsageCalibration,
        resolution: RuntimeChatCompactionResolution,
        event: RuntimeChatStoredEvent,
        line: Int
    ) throws {
        let validWireMode: Bool
        switch calibration.provider {
        case ModelProvider.ollama.rawValue:
            validWireMode = calibration.wireMode == "ollama_chat"
        case ModelProvider.lmStudio.rawValue:
            validWireMode = calibration.wireMode == "lmstudio_native"
                || calibration.wireMode == "lmstudio_openai_compat"
        default:
            validWireMode = false
        }
        let calibrationQualifiedModelID = "\(calibration.provider):\(calibration.providerModelID)"
        guard event.kind == .done,
              resolution.primaryDispatched,
              calibration.countSource == RuntimeChatProviderUsageCalibration.countSourceIdentifier,
              calibration.inputTokens >= 0,
              event.usage?.inputTokens == calibration.inputTokens,
              validWireMode,
              calibration.providerModelID == canonicalProviderModelID(calibration.providerModelID),
              !calibration.providerModelID.isEmpty,
              ModelProvider.splitQualifiedModelID(calibration.providerModelID) == nil,
              resolution.resolvedProviderQualifiedModelID == calibrationQualifiedModelID,
              let estimatedInputTokensAfter = resolution.estimatedInputTokensAfter else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "chat provider usage calibration is invalid"
            )
        }
        let expectedRelation: RuntimeChatProviderTokenRelation
        if calibration.inputTokens <= estimatedInputTokensAfter {
            expectedRelation = .withinConservativeEstimate
        } else if calibration.inputTokens <= resolution.inputBudgetTokens {
            expectedRelation = .exceededConservativeEstimateWithinBudget
        } else {
            expectedRelation = .exceededInputBudget
        }
        guard calibration.relation == expectedRelation else {
            throw RuntimeChatEventStoreError.corruptEventLog(
                line: line,
                reason: "chat provider usage calibration relation does not match request accounting"
            )
        }
    }

    private static func canonicalProviderModelID(_ modelID: String) -> String {
        let trimmed = modelID.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.hasSuffix(":latest") {
            return String(trimmed.dropLast(":latest".count))
        }
        return trimmed
    }

    private static func requireNonBlank(_ value: String?, line: Int, reason: String) throws {
        guard let value, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw RuntimeChatEventStoreError.corruptEventLog(line: line, reason: reason)
        }
    }

    private static func requireNonEmpty(_ value: String?, line: Int, reason: String) throws {
        guard let value, !value.isEmpty else {
            throw RuntimeChatEventStoreError.corruptEventLog(line: line, reason: reason)
        }
    }

    private func appendUnlocked(_ event: RuntimeChatStoredEvent) throws {
        let sanitized = event.sanitizedForStorage()
        try Self.validateStoredEvent(sanitized, line: 0)
        if sanitized.compactionResolution != nil {
            let existingEvents = try Self.decodedEventsInAppendOrder(from: fileURL)
            try Self.validateCompactionResolutionBindings(
                existingEvents + [(line: 0, event: sanitized)]
            )
        }
        let data = try encoder.encode(sanitized)
        let line = data + Data([0x0A])
        try RuntimeEventLogFileProtection.appendLine(line, to: fileURL)
    }

    private func appendBatchAtomicallyUnlocked(_ events: [RuntimeChatStoredEvent]) throws {
        guard !events.isEmpty else { return }
        var appendedData = Data()
        for event in events {
            let sanitized = event.sanitizedForStorage()
            try Self.validateStoredEvent(sanitized, line: 0)
            appendedData.append(try encoder.encode(sanitized))
            appendedData.append(0x0A)
        }
        var completeData = FileManager.default.fileExists(atPath: fileURL.path)
            ? try Data(contentsOf: fileURL)
            : Data()
        completeData.append(appendedData)

        try RuntimeEventLogFileProtection.prepareDirectory(for: fileURL)
        let temporaryURL = fileURL.deletingLastPathComponent().appendingPathComponent(
            ".\(fileURL.lastPathComponent).bulk-\(UUID().uuidString).tmp"
        )
        defer { try? FileManager.default.removeItem(at: temporaryURL) }
        try completeData.write(to: temporaryURL, options: .atomic)
        try RuntimeEventLogFileProtection.secureFile(at: temporaryURL)
        guard Darwin.rename(temporaryURL.path, fileURL.path) == 0 else {
            let code = errno
            throw NSError(
                domain: NSPOSIXErrorDomain,
                code: Int(code),
                userInfo: [
                    NSLocalizedDescriptionKey: "Could not atomically replace runtime chat event log: \(String(cString: strerror(code)))"
                ]
            )
        }
        try RuntimeEventLogFileProtection.secureFile(at: fileURL)
    }

    static func sessions(
        from events: [RuntimeChatStoredEvent],
        limit: Int,
        includeArchived: Bool
    ) throws -> [RuntimeChatStoredSession] {
        let grouped = Dictionary(grouping: events) { event in
            RuntimeChatSessionProjectionKey(event: event)
        }
        return grouped.compactMap { key, events -> (
            key: RuntimeChatSessionProjectionKey,
            session: RuntimeChatStoredSession
        )? in
            let state = lifecycleState(from: events)
            guard state == .active || (includeArchived && state == .archived) else { return nil }
            let chatEvents = events.filter { !$0.kind.isSessionMetadata }
            guard let last = latestEvent(from: chatEvents)
                    ?? latestEvent(from: events) else { return nil }
            let storedTitle = latestStoredTitle(from: events)
            let messages = messages(from: events, key: key, limit: Int.max)
            let archivedAt = state == .archived ? latestLifecycleEvent(from: events)?.timestamp : nil
            return (
                key: key,
                session: RuntimeChatStoredSession(
                    sessionID: key.sessionID,
                    title: storedTitle?.title ?? defaultSessionTitle,
                    titleUpdatedAt: storedTitle?.timestamp,
                    titleRevision: storedTitle?.revision ?? 0,
                    model: last.model,
                    lastActivityAt: last.timestamp,
                    messageCount: messages.count,
                    status: state.rawValue,
                    archivedAt: archivedAt,
                    lastEvent: last.kind.rawValue,
                    lastFinishReason: last.finishReason?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfBlank,
                    lastErrorCode: last.error?.code.trimmingCharacters(in: .whitespacesAndNewlines).nilIfBlank
                )
            )
        }
        .sorted { lhs, rhs in
            if lhs.session.lastActivityAt != rhs.session.lastActivityAt {
                return lhs.session.lastActivityAt > rhs.session.lastActivityAt
            }
            if lhs.session.sessionID != rhs.session.sessionID {
                return lhs.session.sessionID < rhs.session.sessionID
            }
            return (lhs.key.ownerDeviceID ?? "") < (rhs.key.ownerDeviceID ?? "")
        }
        .limited(to: limit)
        .map(\.session)
    }

    static func messages(
        from events: [RuntimeChatStoredEvent],
        sessionID: String,
        limit: Int
    ) -> [RuntimeChatStoredMessage] {
        let keys = sessionProjectionKeys(from: events, sessionID: sessionID)
        guard keys.count == 1, let key = keys.first else { return [] }
        return messages(from: events, key: key, limit: limit)
    }

    static func sessionProjectionKeys(
        from events: [RuntimeChatStoredEvent],
        sessionID: String
    ) -> Set<RuntimeChatSessionProjectionKey> {
        Set(events.compactMap { event in
            event.sessionID == sessionID
                ? RuntimeChatSessionProjectionKey(event: event)
                : nil
        })
    }

    static func messages(
        from events: [RuntimeChatStoredEvent],
        key: RuntimeChatSessionProjectionKey,
        limit: Int
    ) -> [RuntimeChatStoredMessage] {
        let appendOrderedSessionEvents = events.filter {
            RuntimeChatSessionProjectionKey(event: $0) == key
        }
        guard !appendOrderedSessionEvents.isEmpty else { return [] }
        guard lifecycleState(from: appendOrderedSessionEvents) != .deleted else { return [] }

        let sessionEvents = appendOrderedSessionEvents
            .enumerated()
            .sorted { lhs, rhs in
                if lhs.element.timestamp == rhs.element.timestamp {
                    return lhs.offset < rhs.offset
                }
                return lhs.element.timestamp < rhs.element.timestamp
            }
            .map(\.element)

        let requestEvents = sessionEvents.filter { $0.kind == .request }
        var messages: [RuntimeChatStoredMessage] = []

        for request in requestEvents {
            let requestMessages = request.messages?
                .filter { !$0.isRuntimeOnlySystemMessage }
                .map {
                    RuntimeChatStoredMessage(
                        role: $0.role,
                        content: $0.content,
                        attachments: $0.attachments.map(\.withoutInlineData),
                        createdAt: request.timestamp
                    )
                }
                ?? []
            messages = mergeTranscript(messages, withRequestMessages: requestMessages)

            let responseEvents = sessionEvents
                .filter { $0.requestID == request.requestID && $0.timestamp >= request.timestamp }
            let answer = responseEvents
                .compactMap(\.delta)
                .joined()
                .trimmingCharacters(in: .whitespacesAndNewlines)
            let reasoning = responseEvents
                .compactMap(\.reasoningDelta)
                .joined()
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if !answer.isEmpty || !reasoning.isEmpty {
                let completion = responseEvents.last { $0.kind == .done && $0.finishReason == "stop" }
                messages.append(RuntimeChatStoredMessage(
                    role: "assistant",
                    content: answer,
                    reasoning: reasoning.isEmpty ? nil : reasoning,
                    createdAt: responseEvents.last?.timestamp,
                    sourceAttributions: completion?.sourceAttributions ?? [],
                    assistantMessageID: completion?.assistantMessageID
                ))
            }
        }

        return messages.limited(toLast: limit)
    }

    private static func mergeTranscript(
        _ existing: [RuntimeChatStoredMessage],
        withRequestMessages requestMessages: [RuntimeChatStoredMessage]
    ) -> [RuntimeChatStoredMessage] {
        guard !requestMessages.isEmpty else { return existing }
        guard !existing.isEmpty else { return requestMessages }

        if requestMessages.count <= existing.count,
           zip(existing.prefix(requestMessages.count), requestMessages).allSatisfy({
               sameMessageContent($0, $1)
           }) {
            return requestMessages
        }

        let maxOverlap = min(existing.count, requestMessages.count)
        let overlap = stride(from: maxOverlap, through: 1, by: -1).first { count in
            let existingSuffix = existing.suffix(count)
            let requestPrefix = requestMessages.prefix(count)
            return zip(existingSuffix, requestPrefix).allSatisfy { existingMessage, requestMessage in
                sameMessageContent(existingMessage, requestMessage)
            }
        } ?? 0

        return existing + requestMessages.dropFirst(overlap)
    }

    private static func sameMessageContent(
        _ lhs: RuntimeChatStoredMessage,
        _ rhs: RuntimeChatStoredMessage
    ) -> Bool {
        lhs.role == rhs.role && lhs.content == rhs.content
    }

    private static func latestStoredTitle(
        from events: [RuntimeChatStoredEvent]
    ) -> (title: String, timestamp: Date, revision: Int)? {
        var latest: (event: RuntimeChatStoredEvent, title: String)?
        var revision = 0
        for event in events where event.kind == .title {
            let title = event.title?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            guard !title.isEmpty else { continue }
            revision += 1
            latest = (event, title)
        }
        guard let latest else { return nil }
        return (
            title: latest.title,
            timestamp: latest.event.timestamp,
            revision: revision
        )
    }

    static func latestModel(from events: [RuntimeChatStoredEvent]) -> String {
        events
            .reversed()
            .first { !$0.model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }?
            .model ?? ""
    }

    private static func lifecycleState(from events: [RuntimeChatStoredEvent]) -> RuntimeChatSessionLifecycleState {
        guard let latestLifecycle = latestLifecycleEvent(from: events) else {
            return .active
        }
        switch latestLifecycle.kind {
        case .archived:
            return .archived
        case .deleted:
            return .deleted
        case .restored:
            return .active
        default:
            return .active
        }
    }

    private static func latestLifecycleEvent(from events: [RuntimeChatStoredEvent]) -> RuntimeChatStoredEvent? {
        events.last { $0.kind.isSessionLifecycle }
    }

    private static func latestEvent(from events: [RuntimeChatStoredEvent]) -> RuntimeChatStoredEvent? {
        events
            .enumerated()
            .max { lhs, rhs in
                if lhs.element.timestamp == rhs.element.timestamp {
                    return lhs.offset < rhs.offset
                }
                return lhs.element.timestamp < rhs.element.timestamp
            }?
            .element
    }

    private static let defaultSessionTitle = "New chat"
}

extension JSONLRuntimeChatEventStore {
    static func resolvedSourceAttribution(
        from events: [RuntimeChatStoredEvent],
        sessionID: String,
        assistantMessageID: String,
        sourceIndex: Int
    ) -> RuntimeChatResolvedSourceAttribution? {
        guard runtimeChatCanonicalAssistantMessageID(assistantMessageID) == assistantMessageID,
              (1...runtimeTrustedSourceChatContextGrantLimitCeiling).contains(sourceIndex) else { return nil }
        let keys = sessionProjectionKeys(from: events, sessionID: sessionID)
        guard keys.count == 1, let key = keys.first else { return nil }
        let appendOrderedSessionEvents = events.filter {
            RuntimeChatSessionProjectionKey(event: $0) == key
        }
        guard lifecycleState(from: appendOrderedSessionEvents) != .deleted else { return nil }
        let sessionEvents = appendOrderedSessionEvents
            .enumerated()
            .sorted { lhs, rhs in
                if lhs.element.timestamp == rhs.element.timestamp {
                    return lhs.offset < rhs.offset
                }
                return lhs.element.timestamp < rhs.element.timestamp
            }
            .map(\.element)
        let completionOffsets = sessionEvents.indices.filter { offset in
            let event = sessionEvents[offset]
            return event.kind == .done
                && event.finishReason == "stop"
                && event.assistantMessageID == assistantMessageID
        }
        guard messages(from: events, key: key, limit: Int.max).contains(where: {
                  $0.assistantMessageID == assistantMessageID
              }),
              completionOffsets.count == 1,
              let completionOffset = completionOffsets.first else { return nil }
        let completion = sessionEvents[completionOffset]
        let matchingRequestOffsets = sessionEvents.indices.filter { offset in
            let event = sessionEvents[offset]
            return event.kind == .request && event.requestID == completion.requestID
        }
        guard matchingRequestOffsets.count == 1,
              let requestOffset = matchingRequestOffsets.first,
              requestOffset < completionOffset,
              sessionEvents[..<completionOffset].lastIndex(where: { $0.kind == .request }) == requestOffset else {
            return nil
        }
        let request = sessionEvents[requestOffset]
        let responseEvents = sessionEvents[(requestOffset + 1)...completionOffset]
        guard request.requestID == completion.requestID,
              responseEvents.contains(where: {
                  $0.requestID == completion.requestID
                      && (($0.delta?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false)
                          || ($0.reasoningDelta?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false))
              }),
              completion.sourceAttributions?.contains(where: { $0.sourceIndex == sourceIndex }) == true,
              let binding = completion.sourceAttributionBindings?.first(where: {
                  $0.sourceIndex == sourceIndex
              }) else { return nil }
        return RuntimeChatResolvedSourceAttribution(
            assistantMessageID: assistantMessageID,
            binding: binding
        )
    }
}

let runtimeChatAssistantMessageIDPrefix = "assistant_message_"

func runtimeChatAssistantMessageID() -> String {
    runtimeChatAssistantMessageIDPrefix + UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
}

func runtimeChatCanonicalAssistantMessageID(_ value: String?) -> String? {
    guard let value, value.hasPrefix(runtimeChatAssistantMessageIDPrefix) else { return nil }
    let suffix = value.dropFirst(runtimeChatAssistantMessageIDPrefix.count)
    guard suffix.count == 32,
          suffix.utf8.allSatisfy({ ($0 >= 48 && $0 <= 57) || ($0 >= 97 && $0 <= 102) }) else { return nil }
    return value
}

private enum RuntimeChatSessionLifecycleState: String {
    case active
    case archived
    case deleted
}

extension RuntimeChatSessionMutation {
    var eventKind: RuntimeChatStoredEventKind {
        switch self {
        case .archive:
            return .archived
        case .restore:
            return .restored
        case .delete:
            return .deleted
        }
    }
}

private extension RuntimeChatStoredEventKind {
    var isSessionLifecycle: Bool {
        switch self {
        case .archived, .restored, .deleted:
            return true
        default:
            return false
        }
    }

    var isSessionMetadata: Bool {
        self == .title || isSessionLifecycle
    }
}

extension RuntimeChatStoredEvent {
    func sanitizedForStorage() -> RuntimeChatStoredEvent {
        var copy = self
        copy.messages = messages?.map { message in
            ChatMessage(
                role: message.role,
                content: message.content,
                attachments: message.attachments.map(\.withoutInlineData)
            )
        }
        return copy
    }
}

extension ChatAttachment {
    var withoutInlineData: ChatAttachment {
        ChatAttachment(
            type: type,
            mimeType: mimeType,
            name: name,
            dataBase64: nil,
            text: text
        )
    }
}

private extension ChatMessage {
    var isRuntimeOnlySystemMessage: Bool {
        guard role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "system" else {
            return false
        }
        let lowercasedContent = content.lowercased()
        let normalizedContent = lowercasedContent.trimmingCharacters(in: .whitespacesAndNewlines)
        return (
            lowercasedContent.contains("aetherlink currently provides runtime-mediated local model chat") &&
                lowercasedContent.contains("does not provide live web search")
        ) || normalizedContent.hasPrefix("runtime user memory:")
    }
}

extension Array {
    func limited(to limit: Int) -> [Element] {
        guard limit > 0 else { return [] }
        guard count > limit else { return self }
        return Array(prefix(limit))
    }

    func limited(toLast limit: Int) -> [Element] {
        guard limit > 0 else { return [] }
        guard count > limit else { return self }
        return Array(suffix(limit))
    }
}

extension String {
    var nilIfBlank: String? {
        isEmpty ? nil : self
    }

    var runtimeSearchSnippetText: String {
        components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var normalizedRuntimeSearchText: String {
        folding(options: [.caseInsensitive, .diacriticInsensitive], locale: nil)
            .lowercased()
    }
}

private extension Optional where Wrapped == String {
    var normalizedOwnerDeviceID: String? {
        guard let value = self?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else {
            return nil
        }
        return value
    }
}

struct RuntimeChatSessionSearchQuery {
    let terms: [String]

    init?(_ rawQuery: String?) {
        let terms = rawQuery?
            .normalizedRuntimeSearchText
            .split(whereSeparator: { $0.isWhitespace })
            .map(String.init)
            ?? []
        guard !terms.isEmpty else { return nil }
        self.terms = terms
    }
}

struct RuntimeChatSessionSearchField {
    var name: String
    var text: String
    var weight: Int
    var order: Int
}

struct RuntimeChatSessionSearchMatch {
    var score: Int
    var snippet: String
    var matchedFields: [String]
}

extension RuntimeChatStoredSession {
    func runtimeSearchMatch(
        _ query: RuntimeChatSessionSearchQuery,
        messages: [RuntimeChatStoredMessage]
    ) -> RuntimeChatSessionSearchMatch? {
        let fields = searchFields(messages: messages)
        var matchedTerms = Set<String>()
        var matchedFields: [String] = []
        var score = 0
        var snippetCandidates: [(field: RuntimeChatSessionSearchField, termCount: Int)] = []

        for field in fields {
            let normalizedText = field.text.normalizedRuntimeSearchText
            guard !normalizedText.isEmpty else { continue }
            let fieldTerms = query.terms.filter { normalizedText.contains($0) }
            guard !fieldTerms.isEmpty else { continue }

            matchedTerms.formUnion(fieldTerms)
            if !matchedFields.contains(field.name) {
                matchedFields.append(field.name)
            }
            score += field.weight * fieldTerms.count
            if fieldTerms.count == query.terms.count {
                score += 25
            }
            snippetCandidates.append((field, fieldTerms.count))
        }

        guard query.terms.allSatisfy({ matchedTerms.contains($0) }) else { return nil }

        let bestSnippetField = snippetCandidates
            .sorted { lhs, rhs in
                if lhs.termCount != rhs.termCount {
                    return lhs.termCount > rhs.termCount
                }
                if lhs.field.weight != rhs.field.weight {
                    return lhs.field.weight > rhs.field.weight
                }
                return lhs.field.order < rhs.field.order
            }
            .first?
            .field
        let snippet = bestSnippetField
            .map { Self.searchSnippet(from: $0.text, terms: query.terms) }
            ?? title

        return RuntimeChatSessionSearchMatch(
            score: score,
            snippet: snippet,
            matchedFields: matchedFields
        )
    }

    private func searchFields(messages: [RuntimeChatStoredMessage]) -> [RuntimeChatSessionSearchField] {
        var fields: [RuntimeChatSessionSearchField] = []
        func append(_ name: String, _ text: String?, weight: Int) {
            guard let text = text?.runtimeSearchSnippetText, !text.isEmpty else { return }
            fields.append(RuntimeChatSessionSearchField(name: name, text: text, weight: weight, order: fields.count))
        }

        append("title", title, weight: 100)
        append("session_id", sessionID, weight: 40)
        append("model", model, weight: 60)
        append("status", status, weight: 25)
        append("last_event", lastEvent, weight: 25)
        append("last_finish_reason", lastFinishReason, weight: 20)
        append("last_error_code", lastErrorCode, weight: 20)
        for message in messages {
            append("transcript", message.content, weight: 80)
            append("reasoning", message.reasoning, weight: 50)
            for attachment in message.attachments {
                append("attachment", attachment.name, weight: 45)
                append("attachment", attachment.mimeType, weight: 25)
                append("attachment", attachment.text, weight: 70)
            }
        }
        return fields
    }

    private static func searchSnippet(
        from text: String,
        terms: [String],
        maxCharacters: Int = 160
    ) -> String {
        let cleanText = text.runtimeSearchSnippetText
        guard !cleanText.isEmpty else { return "" }
        guard cleanText.count > maxCharacters else { return cleanText }

        let firstRange = terms
            .compactMap { term in
                cleanText.range(of: term, options: [.caseInsensitive, .diacriticInsensitive])
            }
            .min { lhs, rhs in lhs.lowerBound < rhs.lowerBound }
        let center = firstRange?.lowerBound ?? cleanText.startIndex
        let prefixCharacters = maxCharacters / 3
        let start = cleanText.index(center, offsetBy: -prefixCharacters, limitedBy: cleanText.startIndex)
            ?? cleanText.startIndex
        let end = cleanText.index(start, offsetBy: maxCharacters, limitedBy: cleanText.endIndex)
            ?? cleanText.endIndex
        let snippet = cleanText[start..<end].trimmingCharacters(in: .whitespacesAndNewlines)
        let leading = start == cleanText.startIndex ? "" : "..."
        let trailing = end == cleanText.endIndex ? "" : "..."
        return leading + snippet + trailing
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
