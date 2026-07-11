import Foundation

public let protocolVersion = 1
public let relayAllocationProofScheme = "runtime-client-p256-v2"
public let relayAllocationProtocolVersion = 2

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
    public static let relayAllocationChallenge = "relay.allocation.challenge"
    public static let relayAllocationAuthorization = "relay.allocation.authorization"
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
    public static let indexDocumentsList = "index.documents.list"
    public static let retrievalQuery = "retrieval.query"
    public static let sourceAnchorResolve = "source_anchor.resolve"
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

public enum RelayAllocationPayloadValidationError: Error, Equatable, Sendable {
    case invalidField(String)
}

public struct RelayAllocationChallengePayload: Codable, Equatable, Sendable {
    public let proofScheme: String
    public let protocolVersion: Int
    public let operation: String
    public let authorizationID: String
    public let currentRelayID: String
    public let nextRelayID: String
    public let routeTokenHash: String
    public let runtimeKeyFingerprint: String
    public let clientKeyFingerprint: String
    public let currentTicketGeneration: Int64
    public let nextTicketGeneration: Int64
    public let currentRelayExpiresAtEpochMillis: Int64
    public let currentRelayNonce: String
    public let nextRelayExpiresAtEpochMillis: Int64
    public let nextRelayNonce: String
    public let challenge: String
    public let challengeExpiresAtEpochMillis: Int64
    public let transportBinding: String

    public init(
        proofScheme: String,
        protocolVersion: Int,
        operation: String,
        authorizationID: String,
        currentRelayID: String,
        nextRelayID: String,
        routeTokenHash: String,
        runtimeKeyFingerprint: String,
        clientKeyFingerprint: String,
        currentTicketGeneration: Int64,
        nextTicketGeneration: Int64,
        currentRelayExpiresAtEpochMillis: Int64,
        currentRelayNonce: String,
        nextRelayExpiresAtEpochMillis: Int64,
        nextRelayNonce: String,
        challenge: String,
        challengeExpiresAtEpochMillis: Int64,
        transportBinding: String
    ) throws {
        guard proofScheme == relayAllocationProofScheme else {
            throw RelayAllocationPayloadValidationError.invalidField("proof_scheme")
        }
        guard protocolVersion == relayAllocationProtocolVersion else {
            throw RelayAllocationPayloadValidationError.invalidField("protocol_version")
        }
        guard operation == "claim" || operation == "renew" else {
            throw RelayAllocationPayloadValidationError.invalidField("operation")
        }
        guard isBoundedNonBlank(authorizationID) else {
            throw RelayAllocationPayloadValidationError.invalidField("authorization_id")
        }
        guard isRuntimeKeyBoundRelayID(currentRelayID) else {
            throw RelayAllocationPayloadValidationError.invalidField("current_relay_id")
        }
        guard isRuntimeKeyBoundRelayID(nextRelayID) else {
            throw RelayAllocationPayloadValidationError.invalidField("next_relay_id")
        }
        guard operation != "claim" || currentRelayID != nextRelayID else {
            throw RelayAllocationPayloadValidationError.invalidField("next_relay_id")
        }
        guard isLowercaseHex64(routeTokenHash) else {
            throw RelayAllocationPayloadValidationError.invalidField("route_token_hash")
        }
        guard isLowercaseHex64(runtimeKeyFingerprint) else {
            throw RelayAllocationPayloadValidationError.invalidField("runtime_key_fingerprint")
        }
        guard isLowercaseHex64(clientKeyFingerprint) else {
            throw RelayAllocationPayloadValidationError.invalidField("client_key_fingerprint")
        }
        guard currentTicketGeneration > 0 else {
            throw RelayAllocationPayloadValidationError.invalidField("current_ticket_generation")
        }
        guard nextTicketGeneration > 0 else {
            throw RelayAllocationPayloadValidationError.invalidField("next_ticket_generation")
        }
        guard currentRelayExpiresAtEpochMillis > 0 else {
            throw RelayAllocationPayloadValidationError.invalidField("current_relay_expires_at")
        }
        guard isBoundedWhitespaceFree(currentRelayNonce) else {
            throw RelayAllocationPayloadValidationError.invalidField("current_relay_nonce")
        }
        guard nextRelayExpiresAtEpochMillis > 0 else {
            throw RelayAllocationPayloadValidationError.invalidField("next_relay_expires_at")
        }
        guard isBoundedWhitespaceFree(nextRelayNonce) else {
            throw RelayAllocationPayloadValidationError.invalidField("next_relay_nonce")
        }
        guard isLowercaseHex64(challenge) else {
            throw RelayAllocationPayloadValidationError.invalidField("challenge")
        }
        guard challengeExpiresAtEpochMillis > 0 else {
            throw RelayAllocationPayloadValidationError.invalidField("challenge_expires_at")
        }
        guard isLowercaseHex64(transportBinding) else {
            throw RelayAllocationPayloadValidationError.invalidField("transport_binding")
        }

        self.proofScheme = proofScheme
        self.protocolVersion = protocolVersion
        self.operation = operation
        self.authorizationID = authorizationID
        self.currentRelayID = currentRelayID
        self.nextRelayID = nextRelayID
        self.routeTokenHash = routeTokenHash
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.clientKeyFingerprint = clientKeyFingerprint
        self.currentTicketGeneration = currentTicketGeneration
        self.nextTicketGeneration = nextTicketGeneration
        self.currentRelayExpiresAtEpochMillis = currentRelayExpiresAtEpochMillis
        self.currentRelayNonce = currentRelayNonce
        self.nextRelayExpiresAtEpochMillis = nextRelayExpiresAtEpochMillis
        self.nextRelayNonce = nextRelayNonce
        self.challenge = challenge
        self.challengeExpiresAtEpochMillis = challengeExpiresAtEpochMillis
        self.transportBinding = transportBinding
    }

    public init(from decoder: Decoder) throws {
        try rejectUnknownFields(decoder, allowedFields: Set(CodingKeys.allCases.map(\.stringValue)))
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            proofScheme: container.decode(String.self, forKey: .proofScheme),
            protocolVersion: container.decode(Int.self, forKey: .protocolVersion),
            operation: container.decode(String.self, forKey: .operation),
            authorizationID: container.decode(String.self, forKey: .authorizationID),
            currentRelayID: container.decode(String.self, forKey: .currentRelayID),
            nextRelayID: container.decode(String.self, forKey: .nextRelayID),
            routeTokenHash: container.decode(String.self, forKey: .routeTokenHash),
            runtimeKeyFingerprint: container.decode(String.self, forKey: .runtimeKeyFingerprint),
            clientKeyFingerprint: container.decode(String.self, forKey: .clientKeyFingerprint),
            currentTicketGeneration: container.decode(Int64.self, forKey: .currentTicketGeneration),
            nextTicketGeneration: container.decode(Int64.self, forKey: .nextTicketGeneration),
            currentRelayExpiresAtEpochMillis: container.decode(Int64.self, forKey: .currentRelayExpiresAtEpochMillis),
            currentRelayNonce: container.decode(String.self, forKey: .currentRelayNonce),
            nextRelayExpiresAtEpochMillis: container.decode(Int64.self, forKey: .nextRelayExpiresAtEpochMillis),
            nextRelayNonce: container.decode(String.self, forKey: .nextRelayNonce),
            challenge: container.decode(String.self, forKey: .challenge),
            challengeExpiresAtEpochMillis: container.decode(Int64.self, forKey: .challengeExpiresAtEpochMillis),
            transportBinding: container.decode(String.self, forKey: .transportBinding)
        )
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case proofScheme = "proof_scheme"
        case protocolVersion = "protocol_version"
        case operation
        case authorizationID = "authorization_id"
        case currentRelayID = "current_relay_id"
        case nextRelayID = "next_relay_id"
        case routeTokenHash = "route_token_hash"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case clientKeyFingerprint = "client_key_fingerprint"
        case currentTicketGeneration = "current_ticket_generation"
        case nextTicketGeneration = "next_ticket_generation"
        case currentRelayExpiresAtEpochMillis = "current_relay_expires_at"
        case currentRelayNonce = "current_relay_nonce"
        case nextRelayExpiresAtEpochMillis = "next_relay_expires_at"
        case nextRelayNonce = "next_relay_nonce"
        case challenge
        case challengeExpiresAtEpochMillis = "challenge_expires_at"
        case transportBinding = "transport_binding"
    }
}

public struct RelayAllocationAuthorizationPayload: Codable, Equatable, Sendable {
    public let proofScheme: String
    public let authorizationID: String
    public let challenge: String
    public let clientKeyFingerprint: String
    public let transportBinding: String
    public let clientSignature: String

    public init(
        proofScheme: String,
        authorizationID: String,
        challenge: String,
        clientKeyFingerprint: String,
        transportBinding: String,
        clientSignature: String
    ) throws {
        guard proofScheme == relayAllocationProofScheme else {
            throw RelayAllocationPayloadValidationError.invalidField("proof_scheme")
        }
        guard isBoundedNonBlank(authorizationID) else {
            throw RelayAllocationPayloadValidationError.invalidField("authorization_id")
        }
        guard isLowercaseHex64(challenge) else {
            throw RelayAllocationPayloadValidationError.invalidField("challenge")
        }
        guard isLowercaseHex64(clientKeyFingerprint) else {
            throw RelayAllocationPayloadValidationError.invalidField("client_key_fingerprint")
        }
        guard isLowercaseHex64(transportBinding) else {
            throw RelayAllocationPayloadValidationError.invalidField("transport_binding")
        }
        guard isCanonicalBoundedBase64(clientSignature) else {
            throw RelayAllocationPayloadValidationError.invalidField("client_signature")
        }

        self.proofScheme = proofScheme
        self.authorizationID = authorizationID
        self.challenge = challenge
        self.clientKeyFingerprint = clientKeyFingerprint
        self.transportBinding = transportBinding
        self.clientSignature = clientSignature
    }

    public init(from decoder: Decoder) throws {
        try rejectUnknownFields(decoder, allowedFields: Set(CodingKeys.allCases.map(\.stringValue)))
        let container = try decoder.container(keyedBy: CodingKeys.self)
        try self.init(
            proofScheme: container.decode(String.self, forKey: .proofScheme),
            authorizationID: container.decode(String.self, forKey: .authorizationID),
            challenge: container.decode(String.self, forKey: .challenge),
            clientKeyFingerprint: container.decode(String.self, forKey: .clientKeyFingerprint),
            transportBinding: container.decode(String.self, forKey: .transportBinding),
            clientSignature: container.decode(String.self, forKey: .clientSignature)
        )
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case proofScheme = "proof_scheme"
        case authorizationID = "authorization_id"
        case challenge
        case clientKeyFingerprint = "client_key_fingerprint"
        case transportBinding = "transport_binding"
        case clientSignature = "client_signature"
    }
}

private func rejectUnknownFields(_ decoder: Decoder, allowedFields: Set<String>) throws {
    let container = try decoder.container(keyedBy: DynamicCodingKey.self)
    if let unknownField = container.allKeys
        .map(\.stringValue)
        .filter({ !allowedFields.contains($0) })
        .sorted()
        .first,
        let codingKey = DynamicCodingKey(stringValue: unknownField)
    {
        throw DecodingError.dataCorruptedError(
            forKey: codingKey,
            in: container,
            debugDescription: "Unknown payload field '\(unknownField)'"
        )
    }
}

private func isLowercaseHex64(_ value: String) -> Bool {
    value.utf8.count == 64 && value.utf8.allSatisfy { byte in
        (UInt8(ascii: "0")...UInt8(ascii: "9")).contains(byte) ||
            (UInt8(ascii: "a")...UInt8(ascii: "f")).contains(byte)
    }
}

private func isRuntimeKeyBoundRelayID(_ value: String) -> Bool {
    value.hasPrefix("rt2-") && isLowercaseHex64(String(value.dropFirst(4)))
}

private func isBoundedNonBlank(_ value: String) -> Bool {
    value.count <= 512 && value.contains { !$0.isWhitespace }
}

private func isBoundedWhitespaceFree(_ value: String) -> Bool {
    !value.isEmpty && value.count <= 512 && value.allSatisfy { !$0.isWhitespace }
}

private func isCanonicalBoundedBase64(_ value: String) -> Bool {
    guard !value.isEmpty,
          value.count <= 512,
          let decoded = Data(base64Encoded: value)
    else {
        return false
    }
    return decoded.base64EncodedString() == value
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
