import Foundation

public enum BackendStatus: Equatable, Sendable {
    case available
    case unavailable(BackendError)

    public var message: String {
        switch self {
        case .available:
            return "Available"
        case .unavailable(let error):
            return error.message
        }
    }
}

public enum ModelProvider: String, Equatable, Sendable {
    case ollama
    case lmStudio = "lm_studio"
    case aggregate

    public var displayName: String {
        switch self {
        case .ollama:
            return "Ollama"
        case .lmStudio:
            return "LM Studio"
        case .aggregate:
            return "AetherLink Runtime"
        }
    }

    public func qualifiedModelID(_ modelID: String) -> String {
        "\(rawValue):\(modelID)"
    }

    public static func splitQualifiedModelID(_ modelID: String) -> (provider: ModelProvider, modelID: String)? {
        for provider in [ModelProvider.ollama, .lmStudio] {
            let prefix = "\(provider.rawValue):"
            if modelID.hasPrefix(prefix) {
                return (provider, String(modelID.dropFirst(prefix.count)))
            }
        }
        return nil
    }
}

public struct BackendError: Error, Equatable, LocalizedError, Sendable {
    public var provider: ModelProvider
    public var code: String
    public var message: String
    public var retryable: Bool

    public init(provider: ModelProvider, code: String, message: String, retryable: Bool) {
        self.provider = provider
        self.code = code
        self.message = message
        self.retryable = retryable
    }

    public var errorDescription: String? {
        message
    }
}

public struct ModelInfo: Identifiable, Equatable, Sendable {
    public static let maximumCatalogModelCount = 256
    public static let maximumCatalogResponseBytes = 4_194_304
    public static let maximumModelIdentityCodePoints = 512
    public static let maximumQualifiedModelIDCodePoints = 522
    public static let maximumCapabilityCount = 32
    public static let maximumCapabilityCodePoints = 128
    public static let maximumContextWindowTokens = 16_777_216
    public static let maximumSizeBytes = Int64.max

    public var id: String
    public var name: String
    public var provider: ModelProvider
    public var kind: ModelKind
    public var capabilities: [String]
    public var providerModelID: String
    public var sizeBytes: Int64?
    public var modifiedAt: Date?
    public var installed: Bool
    public var running: Bool
    public var source: ModelSource
    public var remoteModel: String?
    public var remoteHost: String?
    public var contextWindowTokens: Int?
    public var persistentEmbeddingRevision: String?

    public init(
        id: String,
        name: String,
        provider: ModelProvider = .ollama,
        kind: ModelKind = .chat,
        capabilities: [String]? = nil,
        providerModelID: String? = nil,
        sizeBytes: Int64? = nil,
        modifiedAt: Date? = nil,
        installed: Bool = true,
        running: Bool = false,
        source: ModelSource = .local,
        remoteModel: String? = nil,
        remoteHost: String? = nil,
        contextWindowTokens: Int? = nil,
        persistentEmbeddingRevision: String? = nil
    ) {
        self.id = id
        self.name = name
        self.provider = provider
        self.kind = kind
        self.capabilities = capabilities ?? kind.defaultCapabilities
        self.providerModelID = providerModelID ?? id
        self.sizeBytes = sizeBytes
        self.modifiedAt = modifiedAt
        self.installed = installed
        self.running = running
        self.source = source
        self.remoteModel = remoteModel
        self.remoteHost = remoteHost
        self.contextWindowTokens = contextWindowTokens
        self.persistentEmbeddingRevision = persistentEmbeddingRevision
    }

    public static func validatedContextWindowTokens(_ value: Int?) -> Int? {
        guard let value, (1...maximumContextWindowTokens).contains(value) else {
            return nil
        }
        return value
    }

    public static func validatedContextWindowTokens(decimal value: Decimal) -> Int? {
        guard value >= Decimal(1), value <= Decimal(maximumContextWindowTokens) else {
            return nil
        }
        var candidate = value
        var integral = Decimal()
        NSDecimalRound(&integral, &candidate, 0, .down)
        guard integral == value else {
            return nil
        }
        return NSDecimalNumber(decimal: integral).intValue
    }

    public static func validateForCatalogPublication(_ model: ModelInfo) throws {
        guard isValidRequiredModelIdentity(model.id) else {
            throw ModelCatalogPublicationValidationError.invalidModelID
        }
        guard isValidRequiredModelIdentity(model.name) else {
            throw ModelCatalogPublicationValidationError.invalidModelName
        }
        guard isValidRequiredModelIdentity(model.providerModelID) else {
            throw ModelCatalogPublicationValidationError.invalidProviderModelID
        }
        if let remoteModel = model.remoteModel,
           !isValidRequiredModelIdentity(remoteModel) {
            throw ModelCatalogPublicationValidationError.invalidRemoteModel
        }
        guard areValidCapabilities(model.capabilities) else {
            throw ModelCatalogPublicationValidationError.invalidCapabilities
        }
        if let contextWindowTokens = model.contextWindowTokens,
           validatedContextWindowTokens(contextWindowTokens) == nil {
            throw ModelCatalogPublicationValidationError.invalidContextWindow
        }
        if let sizeBytes = model.sizeBytes,
           !(0...maximumSizeBytes).contains(sizeBytes) {
            throw ModelCatalogPublicationValidationError.invalidSize
        }
    }

    public static func validateQualifiedModelID(_ modelID: String) throws {
        guard isNonblankBoundedString(modelID, maximumCodePoints: maximumQualifiedModelIDCodePoints) else {
            throw ModelCatalogPublicationValidationError.invalidQualifiedModelID
        }
    }

    public static func isValidRequiredModelIdentity(_ value: String) -> Bool {
        isNonblankBoundedString(value, maximumCodePoints: maximumModelIdentityCodePoints)
    }

    public static func areValidCapabilities(_ capabilities: [String]) -> Bool {
        guard capabilities.count <= maximumCapabilityCount else {
            return false
        }
        var uniqueCapabilities = Set<Data>()
        for capability in capabilities {
            guard isNonblankBoundedString(
                capability,
                maximumCodePoints: maximumCapabilityCodePoints
            ) else {
                return false
            }
            guard uniqueCapabilities.insert(Data(capability.utf8)).inserted else {
                return false
            }
        }
        return true
    }

    private static func isNonblankBoundedString(_ value: String, maximumCodePoints: Int) -> Bool {
        value.unicodeScalars.count <= maximumCodePoints
            && value.unicodeScalars.contains { !isCatalogBlankCodePoint($0.value) }
    }

    private static func isCatalogBlankCodePoint(_ value: UInt32) -> Bool {
        switch value {
        case 0x0009...0x000D,
             0x0020,
             0x0085,
             0x00A0,
             0x1680,
             0x2000...0x200B,
             0x2028,
             0x2029,
             0x202F,
             0x205F,
             0x3000,
             0xFEFF:
            return true
        default:
            return false
        }
    }
}

public enum ModelCatalogPublicationValidationError: Error, Equatable, LocalizedError, Sendable {
    case invalidModelID
    case invalidQualifiedModelID
    case invalidModelName
    case invalidProviderModelID
    case invalidRemoteModel
    case invalidCapabilities
    case invalidContextWindow
    case invalidSize

    public var errorDescription: String? {
        switch self {
        case .invalidModelID:
            return "The model catalog contains an invalid model identifier."
        case .invalidQualifiedModelID:
            return "The model catalog contains an invalid qualified model identifier."
        case .invalidModelName:
            return "The model catalog contains an invalid model name."
        case .invalidProviderModelID:
            return "The model catalog contains an invalid provider model identifier."
        case .invalidRemoteModel:
            return "The model catalog contains invalid remote-model metadata."
        case .invalidCapabilities:
            return "The model catalog contains invalid capability metadata."
        case .invalidContextWindow:
            return "The model catalog contains invalid context-window metadata."
        case .invalidSize:
            return "The model catalog contains invalid model-size metadata."
        }
    }
}

public enum ModelKind: String, Equatable, Sendable {
    case chat
    case embedding

    public var defaultCapabilities: [String] {
        switch self {
        case .chat:
            return ["chat"]
        case .embedding:
            return ["embedding"]
        }
    }

    public static func from(capabilities: [String], fallbackName: String) -> ModelKind {
        let normalizedCapabilities = capabilities.map { $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }
        if normalizedCapabilities.contains(where: { $0 == "embedding" || $0 == "embed" }) {
            return .embedding
        }
        if normalizedCapabilities.contains(where: { $0 == "chat" || $0 == "completion" || $0 == "vision" || $0 == "image" }) {
            return .chat
        }
        return fallbackName.looksLikeEmbeddingModelName ? .embedding : .chat
    }
}

public enum ModelSource: String, Equatable, Sendable {
    case local
    case cloud
}

private extension String {
    var looksLikeEmbeddingModelName: Bool {
        let lowercasedValue = lowercased()
        return [
            "embed",
            "embedding",
            "nomic-embed",
            "mxbai",
            "all-minilm",
            "bge-",
            "bge:",
            "e5-",
            "e5:",
            "gte-",
            "gte:",
            "snowflake-arctic-embed",
            "qwen3-embedding",
            "embeddinggemma",
        ].contains { lowercasedValue.contains($0) }
    }
}

public struct ModelPullResult: Equatable, Sendable {
    public var model: String
    public var status: String
    public var installed: Bool

    public init(model: String, status: String, installed: Bool) {
        self.model = model
        self.status = status
        self.installed = installed
    }
}

public struct ModelUnloadResult: Equatable, Sendable {
    public enum Outcome: String, Equatable, Sendable {
        case confirmed
        case alreadyAbsent = "already_absent"
        case unsupported
    }

    public var provider: ModelProvider
    public var modelID: String
    public var outcome: Outcome
    public var message: String

    public var unloaded: Bool {
        outcome == .confirmed || outcome == .alreadyAbsent
    }

    public init(provider: ModelProvider, modelID: String, outcome: Outcome, message: String) {
        self.provider = provider
        self.modelID = modelID
        self.outcome = outcome
        self.message = message
    }

    public init(provider: ModelProvider, modelID: String, unloaded: Bool, message: String) {
        self.init(
            provider: provider,
            modelID: modelID,
            outcome: unloaded ? .confirmed : .unsupported,
            message: message
        )
    }

    public static func unloaded(provider: ModelProvider, modelID: String) -> ModelUnloadResult {
        ModelUnloadResult(
            provider: provider,
            modelID: modelID,
            outcome: .confirmed,
            message: "Model unloaded."
        )
    }

    public static func alreadyAbsent(provider: ModelProvider, modelID: String) -> ModelUnloadResult {
        ModelUnloadResult(
            provider: provider,
            modelID: modelID,
            outcome: .alreadyAbsent,
            message: "Model was already unloaded."
        )
    }

    public static func unsupported(provider: ModelProvider, modelID: String) -> ModelUnloadResult {
        ModelUnloadResult(
            provider: provider,
            modelID: modelID,
            outcome: .unsupported,
            message: "\(provider.displayName) does not support runtime-managed model unload."
        )
    }
}

public struct ChatMessage: Codable, Equatable, Sendable {
    public var role: String
    public var content: String
    public var attachments: [ChatAttachment]

    public init(role: String, content: String) {
        self.role = role
        self.content = content
        self.attachments = []
    }

    public init(role: String, content: String, attachments: [ChatAttachment]) {
        self.role = role
        self.content = content
        self.attachments = attachments
    }

    enum CodingKeys: String, CodingKey {
        case role
        case content
        case attachments
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        role = try container.decode(String.self, forKey: .role)
        content = try container.decode(String.self, forKey: .content)
        attachments = try container.decodeIfPresent([ChatAttachment].self, forKey: .attachments) ?? []
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(role, forKey: .role)
        try container.encode(content, forKey: .content)
        if !attachments.isEmpty {
            try container.encode(attachments, forKey: .attachments)
        }
    }
}

public struct ChatAttachment: Codable, Equatable, Sendable {
    public var type: String
    public var mimeType: String
    public var name: String?
    public var dataBase64: String?
    public var text: String?

    public init(
        type: String,
        mimeType: String,
        name: String? = nil,
        dataBase64: String? = nil,
        text: String? = nil
    ) {
        self.type = type
        self.mimeType = mimeType
        self.name = name
        self.dataBase64 = dataBase64
        self.text = text
    }

    enum CodingKeys: String, CodingKey {
        case type
        case mimeType = "mime_type"
        case name
        case dataBase64 = "data_base64"
        case text
    }
}

public struct ChatRequest: Equatable, Sendable {
    public var generationID: String
    public var sessionID: String
    public var model: String
    public var messages: [ChatMessage]

    public init(
        generationID: String = UUID().uuidString,
        sessionID: String,
        model: String,
        messages: [ChatMessage]
    ) {
        self.generationID = generationID
        self.sessionID = sessionID
        self.model = model
        self.messages = messages
    }
}

public enum ChatProviderWireMode: String, Equatable, Sendable {
    case ollamaChat = "ollama_chat"
    case lmStudioNative = "lmstudio_native"
    case lmStudioOpenAICompatible = "lmstudio_openai_compat"
}

public struct ChatProviderUsageSource: Equatable, Sendable {
    public var provider: ModelProvider
    public var providerModelID: String
    public var wireMode: ChatProviderWireMode

    public init(provider: ModelProvider, providerModelID: String, wireMode: ChatProviderWireMode) {
        self.provider = provider
        self.providerModelID = providerModelID
        self.wireMode = wireMode
    }
}

public enum ChatStreamEvent: Equatable, Sendable {
    case delta(String)
    case reasoningDelta(String)
    case done(inputTokens: Int?, outputTokens: Int?)
}

public enum GenerationCancellationResult: Equatable, Sendable {
    case cancelled(generationID: String)
    case notFound(generationID: String)
}

public struct EmbeddingRequest: Equatable, Sendable {
    public var model: String
    public var texts: [String]

    public init(model: String, texts: [String]) {
        self.model = model
        self.texts = texts
    }
}

public struct EmbeddingResult: Equatable, Sendable {
    public var model: String
    public var embeddings: [[Double]]

    public init(model: String, embeddings: [[Double]]) {
        self.model = model
        self.embeddings = embeddings
    }
}

public protocol RuntimeModelServingBackend: Sendable {
    var provider: ModelProvider { get }
    func healthCheck() async -> BackendStatus
    func listModels() async throws -> [ModelInfo]
    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error>
    func embed(request: EmbeddingRequest) async throws -> EmbeddingResult
    func unloadModel(providerModelID: String) async throws -> ModelUnloadResult
    @discardableResult func cancel(generationID: String) -> GenerationCancellationResult
    func takeProviderUsageSource(generationID: String) -> ChatProviderUsageSource?
}

public protocol ModelPullDispatching: Sendable {
    func pullModel(name: String) async throws -> ModelPullResult
}

public protocol LlmBackend: RuntimeModelServingBackend, ModelPullDispatching {}

public extension RuntimeModelServingBackend {
    func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        .unsupported(provider: provider, modelID: providerModelID)
    }

    func embed(request: EmbeddingRequest) async throws -> EmbeddingResult {
        throw BackendError(
            provider: provider,
            code: "unsupported_operation",
            message: "\(provider.displayName) does not support text embeddings.",
            retryable: false
        )
    }

    func takeProviderUsageSource(generationID: String) -> ChatProviderUsageSource? {
        nil
    }
}

public extension LlmBackend {
    func pullModel(name: String) async throws -> ModelPullResult {
        throw BackendError(
            provider: provider,
            code: "unsupported_operation",
            message: "\(provider.displayName) does not support runtime-managed model downloads.",
            retryable: false
        )
    }

}
