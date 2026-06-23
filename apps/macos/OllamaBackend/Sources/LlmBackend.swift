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
            return "Local runtime"
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
        remoteHost: String? = nil
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
        if normalizedCapabilities.contains(where: { $0 == "chat" || $0 == "completion" }) {
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

public struct ChatMessage: Codable, Equatable, Sendable {
    public var role: String
    public var content: String

    public init(role: String, content: String) {
        self.role = role
        self.content = content
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

public enum ChatStreamEvent: Equatable, Sendable {
    case delta(String)
    case reasoningDelta(String)
    case done(inputTokens: Int?, outputTokens: Int?)
}

public enum GenerationCancellationResult: Equatable, Sendable {
    case cancelled(generationID: String)
    case notFound(generationID: String)
}

public protocol LlmBackend: Sendable {
    var provider: ModelProvider { get }
    func healthCheck() async -> BackendStatus
    func listModels() async throws -> [ModelInfo]
    func pullModel(name: String) async throws -> ModelPullResult
    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error>
    @discardableResult func cancel(generationID: String) -> GenerationCancellationResult
}
