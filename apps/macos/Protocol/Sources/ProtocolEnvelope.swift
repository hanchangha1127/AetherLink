import Foundation

public let protocolVersion = 1

public enum MessageType {
    public static let runtimeHealth = "runtime.health"
    public static let hello = "hello"
    public static let authChallenge = "auth.challenge"
    public static let authResponse = "auth.response"
    public static let pairingRequest = "pairing.request"
    public static let pairingResult = "pairing.result"
    public static let modelsList = "models.list"
    public static let modelsPull = "models.pull"
    public static let modelsResult = "models.result"
    public static let routeRefresh = "route.refresh"
    public static let chatSend = "chat.send"
    public static let chatDelta = "chat.delta"
    public static let chatDone = "chat.done"
    public static let chatCancel = "chat.cancel"
    public static let chatSessionsList = "chat.sessions.list"
    public static let chatMessagesList = "chat.messages.list"
    public static let chatTitleRequest = "chat.title.request"
    public static let chatTitleResult = "chat.title.result"
    public static let chatSessionRename = "chat.session.rename"
    public static let chatSessionArchive = "chat.session.archive"
    public static let chatSessionRestore = "chat.session.restore"
    public static let chatSessionDelete = "chat.session.delete"
    public static let memoryList = "memory.list"
    public static let memoryUpsert = "memory.upsert"
    public static let memoryDelete = "memory.delete"
    public static let memorySummaryDraftsList = "memory.summary.drafts.list"
    public static let memorySummaryDraftApprove = "memory.summary.draft.approve"
    public static let memorySummaryDraftDismiss = "memory.summary.draft.dismiss"
    public static let error = "error"
}

private struct DynamicCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int?

    init?(stringValue: String) {
        self.stringValue = stringValue
        intValue = nil
    }

    init?(intValue: Int) {
        stringValue = String(intValue)
        self.intValue = intValue
    }
}

public struct ProtocolEnvelope: Codable, Equatable, Sendable {
    public var version: Int
    public var type: String
    public var requestID: String
    public var timestamp: Date
    public var payload: [String: JSONValue]

    public init(
        version: Int = protocolVersion,
        type: String,
        requestID: String = UUID().uuidString,
        timestamp: Date = Date(),
        payload: [String: JSONValue] = [:]
    ) {
        self.version = version
        self.type = type
        self.requestID = requestID
        self.timestamp = timestamp
        self.payload = payload
    }

    public init(from decoder: Decoder) throws {
        let dynamicContainer = try decoder.container(keyedBy: DynamicCodingKey.self)
        let allowedKeys = Set(CodingKeys.allCases.map(\.stringValue))
        if let unknownKey = dynamicContainer.allKeys
            .map(\.stringValue)
            .filter({ !allowedKeys.contains($0) })
            .sorted()
            .first,
            let codingKey = DynamicCodingKey(stringValue: unknownKey)
        {
            throw DecodingError.dataCorruptedError(
                forKey: codingKey,
                in: dynamicContainer,
                debugDescription: "Unknown envelope field '\(unknownKey)'"
            )
        }

        let container = try decoder.container(keyedBy: CodingKeys.self)
        version = try container.decode(Int.self, forKey: .version)
        type = try container.decode(String.self, forKey: .type)
        requestID = try container.decode(String.self, forKey: .requestID)
        timestamp = try container.decode(Date.self, forKey: .timestamp)
        payload = try container.decode([String: JSONValue].self, forKey: .payload)
    }

    enum CodingKeys: String, CodingKey, CaseIterable {
        case version
        case type
        case requestID = "request_id"
        case timestamp
        case payload
    }
}

public struct ModelInfo: Codable, Identifiable, Equatable, Sendable {
    public var id: String
    public var name: String
    public var backend: String?
    public var provider: String?
    public var modelKind: String?
    public var capabilities: [String]
    public var providerModelID: String?
    public var qualifiedID: String?
    public var sizeBytes: Int64?
    public var modifiedAt: Date?
    public var installed: Bool
    public var running: Bool
    public var source: String
    public var remoteModel: String?
    public var contextWindowTokens: Int?

    public init(
        id: String,
        name: String,
        backend: String? = nil,
        provider: String? = nil,
        modelKind: String? = nil,
        capabilities: [String] = [],
        providerModelID: String? = nil,
        qualifiedID: String? = nil,
        sizeBytes: Int64? = nil,
        modifiedAt: Date? = nil,
        installed: Bool = true,
        running: Bool = false,
        source: String = "local",
        remoteModel: String? = nil,
        contextWindowTokens: Int? = nil
    ) {
        self.id = id
        self.name = name
        self.backend = backend
        self.provider = provider
        self.modelKind = modelKind
        self.capabilities = capabilities
        self.providerModelID = providerModelID
        self.qualifiedID = qualifiedID
        self.sizeBytes = sizeBytes
        self.modifiedAt = modifiedAt
        self.installed = installed
        self.running = running
        self.source = source
        self.remoteModel = remoteModel
        self.contextWindowTokens = contextWindowTokens
    }

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case backend
        case provider
        case modelKind = "model_kind"
        case capabilities
        case providerModelID = "provider_model_id"
        case qualifiedID = "qualified_id"
        case sizeBytes = "size_bytes"
        case modifiedAt = "modified_at"
        case installed
        case running
        case source
        case remoteModel = "remote_model"
        case contextWindowTokens = "context_window_tokens"
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        backend = try container.decodeIfPresent(String.self, forKey: .backend)
        provider = try container.decodeIfPresent(String.self, forKey: .provider)
        modelKind = try container.decodeIfPresent(String.self, forKey: .modelKind)
        capabilities = try container.decodeIfPresent([String].self, forKey: .capabilities) ?? []
        providerModelID = try container.decodeIfPresent(String.self, forKey: .providerModelID)
        qualifiedID = try container.decodeIfPresent(String.self, forKey: .qualifiedID)
        sizeBytes = try container.decodeIfPresent(Int64.self, forKey: .sizeBytes)
        modifiedAt = try container.decodeIfPresent(Date.self, forKey: .modifiedAt)
        installed = try container.decodeIfPresent(Bool.self, forKey: .installed) ?? true
        running = try container.decodeIfPresent(Bool.self, forKey: .running) ?? false
        source = try container.decodeIfPresent(String.self, forKey: .source) ?? "local"
        remoteModel = try container.decodeIfPresent(String.self, forKey: .remoteModel)
        contextWindowTokens = try container.decodeIfPresent(Int.self, forKey: .contextWindowTokens)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encodeIfPresent(backend, forKey: .backend)
        try container.encodeIfPresent(provider, forKey: .provider)
        try container.encodeIfPresent(modelKind, forKey: .modelKind)
        if !capabilities.isEmpty {
            try container.encode(capabilities, forKey: .capabilities)
        }
        try container.encodeIfPresent(providerModelID, forKey: .providerModelID)
        try container.encodeIfPresent(qualifiedID, forKey: .qualifiedID)
        try container.encodeIfPresent(sizeBytes, forKey: .sizeBytes)
        try container.encodeIfPresent(modifiedAt, forKey: .modifiedAt)
        try container.encode(installed, forKey: .installed)
        try container.encode(running, forKey: .running)
        try container.encode(source, forKey: .source)
        try container.encodeIfPresent(remoteModel, forKey: .remoteModel)
        try container.encodeIfPresent(contextWindowTokens, forKey: .contextWindowTokens)
    }
}
