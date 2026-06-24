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
    public static let chatSend = "chat.send"
    public static let chatDelta = "chat.delta"
    public static let chatDone = "chat.done"
    public static let chatCancel = "chat.cancel"
    public static let chatSuggestionsRequest = "chat.suggestions.request"
    public static let chatSuggestionsResult = "chat.suggestions.result"
    public static let error = "error"
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

    enum CodingKeys: String, CodingKey {
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
    public var sizeBytes: Int64?
    public var modifiedAt: Date?
    public var installed: Bool
    public var running: Bool
    public var source: String
    public var remoteModel: String?

    public init(
        id: String,
        name: String,
        sizeBytes: Int64? = nil,
        modifiedAt: Date? = nil,
        installed: Bool = true,
        running: Bool = false,
        source: String = "local",
        remoteModel: String? = nil
    ) {
        self.id = id
        self.name = name
        self.sizeBytes = sizeBytes
        self.modifiedAt = modifiedAt
        self.installed = installed
        self.running = running
        self.source = source
        self.remoteModel = remoteModel
    }

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case sizeBytes = "size_bytes"
        case modifiedAt = "modified_at"
        case installed
        case running
        case source
        case remoteModel = "remote_model"
    }
}
