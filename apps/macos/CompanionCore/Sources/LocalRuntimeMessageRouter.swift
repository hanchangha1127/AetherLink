import BridgeProtocol
import CryptoKit
import DocumentIngestion
import Foundation
import LMStudioBackend
import OllamaBackend
import Pairing
import Security
import Transport
import TrustedDevices

public final class LocalRuntimeMessageRouter: @unchecked Sendable {
    private let backend: any LlmBackend
    private let requiresAuthentication: Bool
    private let pairingCoordinator: PairingCoordinator
    private let trustedDeviceStore: TrustedDeviceStore
    private let onPairingAccepted: (@Sendable (TrustedDevice) -> Void)?
    private let dateFormatter = ISO8601DateFormatter()
    private let authLock = NSLock()
    private var authSessions: [UUID: AuthSessionState] = [:]

    public init(
        backend: any LlmBackend,
        requiresAuthentication: Bool = true,
        pairingCoordinator: PairingCoordinator = PairingCoordinator(),
        trustedDeviceStore: TrustedDeviceStore = TrustedDeviceStore(),
        onPairingAccepted: (@Sendable (TrustedDevice) -> Void)? = nil
    ) {
        self.backend = backend
        self.requiresAuthentication = requiresAuthentication
        self.pairingCoordinator = pairingCoordinator
        self.trustedDeviceStore = trustedDeviceStore
        self.onPairingAccepted = onPairingAccepted
        dateFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    }

    public func handle(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        Task {
            await dispatch(envelope, sink: sink)
        }
    }

    private func dispatch(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        switch envelope.type {
        case MessageType.pairingRequest:
            await handlePairingRequest(envelope, sink: sink)
        case MessageType.hello:
            await handleHello(envelope, sink: sink)
        case MessageType.authResponse:
            await handleAuthResponse(envelope, sink: sink)
        case MessageType.runtimeHealth:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleRuntimeHealth(envelope, sink: sink)
        case MessageType.modelsList:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleModelsList(envelope, sink: sink)
        case MessageType.modelsPull:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleModelsPull(envelope, sink: sink)
        case MessageType.chatSend:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleChatSend(envelope, sink: sink)
        case MessageType.chatCancel:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatCancel(envelope, sink: sink)
        case MessageType.chatSuggestionsRequest:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleChatSuggestionsRequest(envelope, sink: sink)
        default:
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                code: "unknown_message_type",
                message: "Unsupported development transport message type: \(envelope.type)",
                retryable: false
            ))
        }
    }

    private func allowRuntimeCommand(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) -> Bool {
        guard requiresAuthentication else { return true }
        guard isAuthenticated(connectionID: sink.connectionID) else {
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                code: "authentication_required",
                message: "Pair and authenticate this client device before sending runtime commands.",
                retryable: false
            ))
            return false
        }
        return true
    }

    private func handlePairingRequest(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            let request = PairingRequest(
                pairingNonce: try requiredString("pairing_nonce", in: envelope.payload),
                pairingCode: try requiredString("pairing_code", in: envelope.payload),
                deviceID: try requiredString("device_id", in: envelope.payload),
                deviceName: try requiredString("device_name", in: envelope.payload),
                publicKeyBase64: try requiredString("public_key", in: envelope.payload)
            )
            switch pairingCoordinator.validate(request) {
            case .accepted(let validation):
                try await trustedDeviceStore.trust(validation.trustedDevice)
                markAuthenticated(connectionID: sink.connectionID, deviceID: validation.trustedDevice.id)
                onPairingAccepted?(validation.trustedDevice)

                var payload: [String: JSONValue] = [
                    "accepted": .bool(true),
                    "mac_device_id": .string(validation.macDeviceID),
                    "runtime_device_id": .string(validation.macDeviceID),
                    "runtime_key_fingerprint": .string(validation.runtimeKeyFingerprint),
                    "trusted_device_id": .string(validation.trustedDevice.id),
                    "message": .string("\(validation.trustedDevice.name) is now trusted by \(validation.macName).")
                ]
                if let runtimePublicKeyBase64 = validation.runtimePublicKeyBase64,
                   !runtimePublicKeyBase64.isEmpty {
                    payload["runtime_public_key"] = .string(runtimePublicKeyBase64)
                }

                sink.send(ProtocolEnvelope(
                    type: MessageType.pairingResult,
                    requestID: envelope.requestID,
                    payload: payload
                ))
            case .rejected(let rejection):
                sink.send(ProtocolEnvelope(
                    type: MessageType.pairingResult,
                    requestID: envelope.requestID,
                    payload: [
                        "accepted": .bool(false),
                        "code": .string(rejection.code),
                        "message": .string(rejection.message),
                        "retryable": .bool(rejection.retryable),
                        "failed_attempts": .number(Double(rejection.failedAttempts)),
                        "max_failed_attempts": .number(Double(rejection.maxFailedAttempts)),
                        "remaining_attempts": .number(Double(rejection.remainingAttempts))
                    ]
                ))
            }
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleChatSuggestionsRequest(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            let parsedRequest = try chatSuggestionsRequest(from: envelope)
            _ = try await resolvedInstalledModel(parsedRequest.request.model)

            var generatedText = ""
            for try await event in backend.chat(request: parsedRequest.request) {
                switch event {
                case .delta(let text):
                    generatedText += text
                case .reasoningDelta:
                    continue
                case .done:
                    break
                }
            }

            let suggestions = Self.suggestions(
                from: generatedText,
                maxSuggestions: parsedRequest.maxSuggestions
            )
            sink.send(ProtocolEnvelope(
                type: MessageType.chatSuggestionsResult,
                requestID: envelope.requestID,
                payload: [
                    "suggestions": .array(suggestions.map { .string($0) })
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleHello(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            let deviceID = try requiredString("device_id", in: envelope.payload)
            guard try await trustedDevice(deviceID: deviceID) != nil else {
                sink.send(errorEnvelope(
                    requestID: envelope.requestID,
                    code: "pairing_required",
                    message: "This client device is not trusted by the companion runtime.",
                    retryable: false
                ))
                return
            }

            let nonce = Self.makeNonce()
            setChallenge(connectionID: sink.connectionID, deviceID: deviceID, nonce: nonce)
            sink.send(ProtocolEnvelope(
                type: MessageType.authChallenge,
                requestID: envelope.requestID,
                payload: [
                    "device_id": .string(deviceID),
                    "nonce": .string(nonce)
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleAuthResponse(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            let deviceID = try requiredString("device_id", in: envelope.payload)
            let nonce = try requiredString("nonce", in: envelope.payload)
            let signature = try requiredString("signature", in: envelope.payload)

            guard challengeMatches(connectionID: sink.connectionID, deviceID: deviceID, nonce: nonce),
                  let device = try await trustedDevice(deviceID: deviceID),
                  Self.verifySignature(
                    publicKeyBase64: device.publicKeyBase64,
                    nonce: nonce,
                    signatureBase64: signature
                  )
            else {
                sink.send(errorEnvelope(
                    requestID: envelope.requestID,
                    code: "authentication_failed",
                    message: "Could not authenticate this client device.",
                    retryable: false
                ))
                return
            }

            markAuthenticated(connectionID: sink.connectionID, deviceID: deviceID)
            sink.send(ProtocolEnvelope(
                type: MessageType.authResponse,
                requestID: envelope.requestID,
                payload: [
                    "accepted": .bool(true),
                    "device_id": .string(deviceID)
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleRuntimeHealth(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        if let aggregate = backend as? AggregatingLlmBackend {
            let statuses = await aggregate.providerHealth()
            let providerPayloads = statuses.mapValues { status in
                healthPayload(for: status)
            }
            let anyAvailable = statuses.values.contains(.available)
            sink.send(ProtocolEnvelope(
                type: MessageType.runtimeHealth,
                requestID: envelope.requestID,
                payload: [
                    "status": .string(anyAvailable ? "ok" : "unavailable"),
                    "ollama": providerPayloads[.ollama] ?? .object([
                        "available": .bool(false),
                        "code": .string("backend_unavailable"),
                        "message": .string("Ollama is not enabled in the companion runtime."),
                        "retryable": .bool(false)
                    ]),
                    "lm_studio": providerPayloads[.lmStudio] ?? .object([
                        "available": .bool(false),
                        "code": .string("backend_unavailable"),
                        "message": .string("LM Studio is not enabled in the companion runtime."),
                        "retryable": .bool(false)
                    ])
                ]
            ))
            return
        }

        switch await backend.healthCheck() {
        case .available:
            sink.send(ProtocolEnvelope(
                type: MessageType.runtimeHealth,
                requestID: envelope.requestID,
                payload: [
                    "status": .string("ok"),
                    backend.provider.rawValue: .object([
                        "available": .bool(true),
                        "message": .string("\(backend.provider.displayName) is reachable from the companion runtime")
                    ])
                ]
            ))
        case .unavailable(let error):
            sink.send(ProtocolEnvelope(
                type: MessageType.runtimeHealth,
                requestID: envelope.requestID,
                payload: [
                    "status": .string("unavailable"),
                    error.provider.rawValue: healthPayload(for: .unavailable(error))
                ]
            ))
        }
    }

    private func handleModelsList(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            let models = try await backend.listModels()
            sink.send(ProtocolEnvelope(
                type: MessageType.modelsList,
                requestID: envelope.requestID,
                payload: [
                    "models": .array(models.map { model in
                        var payload: [String: JSONValue] = [
                            "id": .string(model.id),
                            "name": .string(model.name),
                            "backend": .string(model.provider.rawValue),
                            "provider": .string(model.provider.rawValue),
                            "model_kind": .string(model.kind.rawValue),
                            "capabilities": .array(model.capabilities.map { .string($0) }),
                            "provider_model_id": .string(model.providerModelID),
                            "qualified_id": .string(model.provider.qualifiedModelID(model.providerModelID)),
                            "installed": .bool(model.installed),
                            "running": .bool(model.running),
                            "source": .string(model.source.rawValue)
                        ]
                        if let sizeBytes = model.sizeBytes {
                            payload["size_bytes"] = .number(Double(sizeBytes))
                        }
                        if let modifiedAt = model.modifiedAt {
                            payload["modified_at"] = .string(dateFormatter.string(from: modifiedAt))
                        }
                        if let remoteModel = model.remoteModel, !remoteModel.isEmpty {
                            payload["remote_model"] = .string(remoteModel)
                        }
                        return .object(payload)
                    })
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleModelsPull(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            let model = try requiredString("model", in: envelope.payload)
            let result = try await backend.pullModel(name: model)
            let provider = ModelProvider.splitQualifiedModelID(model)?.provider ?? .ollama
            sink.send(ProtocolEnvelope(
                type: MessageType.modelsPull,
                requestID: envelope.requestID,
                payload: [
                    "model": .string(result.model),
                    "status": .string(result.status),
                    "installed": .bool(result.installed),
                    "backend": .string(provider.rawValue),
                    "provider": .string(provider.rawValue)
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleChatSend(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            let request = try chatRequest(from: envelope)
            let model = try await resolvedInstalledModel(request.model)
            try validateAttachments(in: request, for: model)
            for try await event in backend.chat(request: request) {
                switch event {
                case .delta(let text):
                    sink.send(ProtocolEnvelope(
                        type: MessageType.chatDelta,
                        requestID: envelope.requestID,
                        payload: ["delta": .string(text)]
                    ))
                case .reasoningDelta(let text):
                    sink.send(ProtocolEnvelope(
                        type: MessageType.chatDelta,
                        requestID: envelope.requestID,
                        payload: ["reasoning_delta": .string(text)]
                    ))
                case .done(let inputTokens, let outputTokens):
                    sink.send(ProtocolEnvelope(
                        type: MessageType.chatDone,
                        requestID: envelope.requestID,
                        payload: [
                            "finish_reason": .string("stop"),
                            "usage": .object([
                                "input_tokens": .number(Double(inputTokens ?? 0)),
                                "output_tokens": .number(Double(outputTokens ?? 0))
                            ])
                        ]
                    ))
                }
            }
        } catch OllamaBackendError.generationCancelled {
            sink.send(ProtocolEnvelope(
                type: MessageType.chatDone,
                requestID: envelope.requestID,
                payload: ["finish_reason": .string("cancelled")]
            ))
        } catch LMStudioBackendError.generationCancelled {
            sink.send(ProtocolEnvelope(
                type: MessageType.chatDone,
                requestID: envelope.requestID,
                payload: ["finish_reason": .string("cancelled")]
            ))
        } catch let error as BackendError where error.code == "generation_cancelled" {
            sink.send(ProtocolEnvelope(
                type: MessageType.chatDone,
                requestID: envelope.requestID,
                payload: ["finish_reason": .string("cancelled")]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func resolvedInstalledModel(_ requestedModel: String) async throws -> ResolvedRuntimeModel {
        let models = try await backend.listModels()
        if let resolved = ModelProvider.splitQualifiedModelID(requestedModel) {
            if let model = models.first(where: { model in
                model.installed
                    && model.provider == resolved.provider
                    && (
                        model.id == resolved.modelID
                            || model.name == resolved.modelID
                            || model.providerModelID == resolved.modelID
                            || Self.canonicalModelName(model.id) == Self.canonicalModelName(resolved.modelID)
                            || Self.canonicalModelName(model.providerModelID) == Self.canonicalModelName(resolved.modelID)
                    )
            }) {
                return ResolvedRuntimeModel(provider: model.provider, capabilities: model.capabilities)
            }
            throw LocalRuntimeRouterError.modelNotInstalled(requestedModel)
        }

        let requestedCanonicalName = Self.canonicalModelName(requestedModel)
        if let model = models.first(where: { model in
            model.installed && (
                model.id == requestedModel
                    || model.name == requestedModel
                    || model.providerModelID == requestedModel
                    || Self.canonicalModelName(model.id) == requestedCanonicalName
                    || Self.canonicalModelName(model.name) == requestedCanonicalName
                    || Self.canonicalModelName(model.providerModelID) == requestedCanonicalName
            )
        }) {
            return ResolvedRuntimeModel(provider: model.provider, capabilities: model.capabilities)
        }
        throw LocalRuntimeRouterError.modelNotInstalled(requestedModel)
    }

    private func validateAttachments(in request: ChatRequest, for model: ResolvedRuntimeModel) throws {
        guard request.messages.contains(where: { message in
            message.attachments.contains { $0.isImage }
        }) else { return }

        guard model.supportsImageAttachments else {
            throw LocalRuntimeRouterError.unsupportedAttachment(
                "Image attachments require a vision-capable model."
            )
        }
    }

    private func handleChatCancel(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let targetRequestID = try requiredString("target_request_id", in: envelope.payload)
            switch backend.cancel(generationID: targetRequestID) {
            case .cancelled:
                sink.send(ProtocolEnvelope(
                    type: MessageType.chatCancel,
                    requestID: envelope.requestID,
                    payload: [
                        "target_request_id": .string(targetRequestID),
                        "cancelled": .bool(true)
                    ]
                ))
            case .notFound:
                sink.send(errorEnvelope(
                    requestID: envelope.requestID,
                    code: "generation_not_found",
                    message: "No active generation found for request id: \(targetRequestID)",
                    retryable: false
                ))
            }
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func chatRequest(from envelope: ProtocolEnvelope) throws -> ChatRequest {
        let sessionID = try requiredString("session_id", in: envelope.payload)
        let model = try requiredString("model", in: envelope.payload)
        let messagesValue = try requiredValue("messages", in: envelope.payload)
        guard case .array(let messageValues) = messagesValue else {
            throw LocalRuntimeRouterError.invalidPayload("messages must be an array")
        }

        let messages = try messageValues.map { value -> ChatMessage in
            guard case .object(let object) = value else {
                throw LocalRuntimeRouterError.invalidPayload("Each message must be an object")
            }
            let parsedAttachments = try chatAttachments(from: object)
            let processed = try processChatAttachments(parsedAttachments)
            return ChatMessage(
                role: try requiredString("role", in: object),
                content: content(
                    try requiredString("content", in: object),
                    appending: processed.promptText
                ),
                attachments: processed.preservedAttachments
            )
        }

        return ChatRequest(
            generationID: envelope.requestID,
            sessionID: sessionID,
            model: model,
            messages: messages
        )
    }

    private func chatSuggestionsRequest(from envelope: ProtocolEnvelope) throws -> ChatSuggestionRuntimeRequest {
        let baseRequest = try chatRequest(from: envelope)
        let maxSuggestions = optionalInt("max_suggestions", in: envelope.payload)
            .map { min(max($0, 1), 5) }
            ?? 3
        let locale = optionalString("locale", in: envelope.payload)
        let recentMessages = Array(baseRequest.messages.suffix(8))
        guard recentMessages.contains(where: { $0.role == "user" }) else {
            throw LocalRuntimeRouterError.invalidPayload("messages must include at least one user message")
        }

        let suggestionRequest = ChatRequest(
            generationID: envelope.requestID,
            sessionID: baseRequest.sessionID,
            model: baseRequest.model,
            messages: Self.suggestionPromptMessages(
                recentMessages: recentMessages,
                maxSuggestions: maxSuggestions,
                locale: locale
            )
        )
        return ChatSuggestionRuntimeRequest(
            request: suggestionRequest,
            maxSuggestions: maxSuggestions
        )
    }

    private func errorEnvelope(requestID: String, error: Error) -> ProtocolEnvelope {
        if let error = error as? OllamaBackendError {
            let mappedError = error.backendError
            return errorEnvelope(
                requestID: requestID,
                code: mappedError.code,
                message: mappedError.message,
                retryable: mappedError.retryable
            )
        }
        if let error = error as? LMStudioBackendError {
            let mappedError = error.backendError
            return errorEnvelope(
                requestID: requestID,
                code: mappedError.code,
                message: mappedError.message,
                retryable: mappedError.retryable
            )
        }
        if let error = error as? BackendError {
            return errorEnvelope(
                requestID: requestID,
                code: error.code,
                message: error.message,
                retryable: error.retryable
            )
        }
        if let error = error as? LocalRuntimeRouterError {
            return errorEnvelope(
                requestID: requestID,
                code: error.code,
                message: error.localizedDescription,
                retryable: false
            )
        }
        return errorEnvelope(
            requestID: requestID,
            code: "internal_error",
            message: error.localizedDescription,
            retryable: false
        )
    }

    private func errorEnvelope(
        requestID: String,
        code: String,
        message: String,
        retryable: Bool
    ) -> ProtocolEnvelope {
        ProtocolEnvelope(
            type: MessageType.error,
            requestID: requestID,
            payload: [
                "code": .string(code),
                "message": .string(message),
                "retryable": .bool(retryable)
            ]
        )
    }

    private func healthPayload(for status: BackendStatus) -> JSONValue {
        switch status {
        case .available:
            return .object([
                "available": .bool(true),
                "message": .string("Backend is reachable from the companion runtime")
            ])
        case .unavailable(let error):
            return .object([
                "available": .bool(false),
                "code": .string(error.code),
                "message": .string(error.message),
                "retryable": .bool(error.retryable)
            ])
        }
    }

    private func trustedDevice(deviceID: String) async throws -> TrustedDevice? {
        try await trustedDeviceStore.load().first { $0.id == deviceID }
    }

    private func isAuthenticated(connectionID: UUID) -> Bool {
        authLock.withLock {
            if case .authenticated = authSessions[connectionID] {
                return true
            }
            return false
        }
    }

    private func setChallenge(connectionID: UUID, deviceID: String, nonce: String) {
        authLock.withLock {
            authSessions[connectionID] = .challenged(deviceID: deviceID, nonce: nonce)
        }
    }

    private func challengeMatches(connectionID: UUID, deviceID: String, nonce: String) -> Bool {
        authLock.withLock {
            authSessions[connectionID] == .challenged(deviceID: deviceID, nonce: nonce)
        }
    }

    private func markAuthenticated(connectionID: UUID, deviceID: String) {
        authLock.withLock {
            authSessions[connectionID] = .authenticated(deviceID: deviceID)
        }
    }

    private static func makeNonce() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).base64EncodedString()
    }

    private static func canonicalModelName(_ name: String) -> String {
        if name.hasSuffix(":latest") {
            return String(name.dropLast(":latest".count))
        }
        return name
    }

    private static func suggestionPromptMessages(
        recentMessages: [ChatMessage],
        maxSuggestions: Int,
        locale: String?
    ) -> [ChatMessage] {
        let localeInstruction = locale
            .map { "Use this BCP-47 locale when writing suggestions unless the conversation clearly uses another language: \($0)." }
            ?? "Use the same language as the conversation."
        return [
            ChatMessage(
                role: "system",
                content: """
                You generate short follow-up questions for a chat assistant UI.
                Return only strict JSON with this shape: {"suggestions":["question 1","question 2"]}.
                Generate \(maxSuggestions) useful next questions at most.
                Each question must be concise, natural, and directly related to the latest assistant answer.
                Do not answer the conversation. Do not include markdown, numbering, explanations, or extra keys.
                \(localeInstruction)
                """
            )
        ] + recentMessages + [
            ChatMessage(
                role: "user",
                content: "Generate the next questions now."
            )
        ]
    }

    private static func suggestions(from rawText: String, maxSuggestions: Int) -> [String] {
        let trimmedText = rawText.trimmingCharacters(in: .whitespacesAndNewlines)
        let decoder = JSONDecoder()
        if let data = trimmedText.data(using: .utf8) {
            if let result = try? decoder.decode(ChatSuggestionsResult.self, from: data) {
                return result.suggestions.cleanedSuggestions(maxCount: maxSuggestions)
            }
        }
        return []
    }

    private static func verifySignature(
        publicKeyBase64: String,
        nonce: String,
        signatureBase64: String
    ) -> Bool {
        guard let publicKeyData = Data(base64Encoded: publicKeyBase64),
              let signatureData = Data(base64Encoded: signatureBase64),
              let nonceData = nonce.data(using: .utf8),
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: publicKeyData),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: signatureData)
        else {
            return false
        }
        return publicKey.isValidSignature(signature, for: SHA256.hash(data: nonceData))
    }
}

private enum AuthSessionState: Equatable {
    case challenged(deviceID: String, nonce: String)
    case authenticated(deviceID: String)
}

private struct ChatSuggestionRuntimeRequest {
    var request: ChatRequest
    var maxSuggestions: Int
}

private struct ChatSuggestionsResult: Decodable {
    var suggestions: [String]
}

private enum LocalRuntimeRouterError: Error, LocalizedError {
    case invalidPayload(String)
    case modelNotInstalled(String)
    case unsupportedAttachment(String)
    case unreadableAttachment(String)

    var code: String {
        switch self {
        case .invalidPayload:
            return "invalid_payload"
        case .modelNotInstalled:
            return "model_not_installed"
        case .unsupportedAttachment:
            return "unsupported_attachment"
        case .unreadableAttachment:
            return "unreadable_attachment"
        }
    }

    var errorDescription: String? {
        switch self {
        case .invalidPayload(let message):
            return message
        case .modelNotInstalled(let model):
            return "Model '\(model)' is not installed on the companion runtime. Pull it through the companion runtime before sending chat."
        case .unsupportedAttachment(let message),
             .unreadableAttachment(let message):
            return message
        }
    }
}

private struct ProcessedChatAttachments {
    var promptText: String
    var preservedAttachments: [ChatAttachment]
}

private func chatAttachments(from object: [String: JSONValue]) throws -> [ChatAttachment] {
    guard let attachmentsValue = object["attachments"] else { return [] }
    guard case .array(let attachmentValues) = attachmentsValue else {
        throw LocalRuntimeRouterError.invalidPayload("attachments must be an array")
    }
    return try attachmentValues.map { value in
        guard case .object(let attachmentObject) = value else {
            throw LocalRuntimeRouterError.invalidPayload("Each attachment must be an object")
        }
        return ChatAttachment(
            type: try requiredString("type", in: attachmentObject),
            mimeType: try requiredString("mime_type", in: attachmentObject),
            name: optionalString("name", in: attachmentObject),
            dataBase64: optionalString("data_base64", in: attachmentObject),
            text: optionalString("text", in: attachmentObject)
        )
    }
}

private func processChatAttachments(_ attachments: [ChatAttachment]) throws -> ProcessedChatAttachments {
    var promptBlocks: [String] = []
    var preservedAttachments: [ChatAttachment] = []

    for attachment in attachments {
        if attachment.isImage {
            preservedAttachments.append(attachment)
            continue
        }

        let name = attachment.name ?? "attachment"
        if let text = attachment.text?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty {
            promptBlocks.append(documentPromptBlock(name: name, mimeType: attachment.mimeType, text: text))
            continue
        }

        guard let dataBase64 = attachment.dataBase64 else {
            throw LocalRuntimeRouterError.unreadableAttachment(
                "Attachment '\(name)' does not include readable text or base64 document data."
            )
        }
        guard let data = Data(base64Encoded: dataBase64) else {
            throw LocalRuntimeRouterError.unreadableAttachment(
                "Attachment '\(name)' contains invalid base64 document data."
            )
        }

        let extracted = try extractDocumentAttachment(
            data: data,
            name: name,
            mimeType: attachment.mimeType
        )
        promptBlocks.append(documentPromptBlock(
            name: extracted.fileName,
            mimeType: extracted.mimeType,
            text: extracted.text
        ))
    }

    return ProcessedChatAttachments(
        promptText: promptBlocks.joined(separator: "\n\n"),
        preservedAttachments: preservedAttachments
    )
}

private func extractDocumentAttachment(
    data: Data,
    name: String,
    mimeType: String
) throws -> ExtractedDocument {
    let temporaryDirectory = FileManager.default.temporaryDirectory
        .appendingPathComponent("aetherlink-attachments", isDirectory: true)
        .appendingPathComponent(UUID().uuidString, isDirectory: true)
    try FileManager.default.createDirectory(at: temporaryDirectory, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: temporaryDirectory) }

    let fileURL = temporaryDirectory.appendingPathComponent(safeAttachmentFileName(name))
    do {
        try data.write(to: fileURL, options: .atomic)
        return try DocumentTextExtractor().extractText(from: fileURL, mimeType: mimeType)
    } catch let error as DocumentIngestionError {
        switch error {
        case .unsupportedFileType:
            throw LocalRuntimeRouterError.unsupportedAttachment(
                "Attachment '\(name)' has unsupported document type '\(mimeType)'."
            )
        case .unreadablePDF, .archiveListingFailed, .archiveEntryReadFailed, .converterFailed, .noExtractableText:
            throw LocalRuntimeRouterError.unreadableAttachment(
                "Attachment '\(name)' could not be read: \(error.localizedDescription)"
            )
        }
    } catch {
        throw LocalRuntimeRouterError.unreadableAttachment(
            "Attachment '\(name)' could not be read: \(error.localizedDescription)"
        )
    }
}

private func content(_ baseContent: String, appending attachmentText: String) -> String {
    guard !attachmentText.isEmpty else { return baseContent }
    return "\(baseContent)\n\n\(attachmentText)"
}

private func documentPromptBlock(name: String, mimeType: String, text: String) -> String {
    """
    [Attached document: \(name) (\(mimeType))]
    \(text)
    """
}

private func safeAttachmentFileName(_ name: String) -> String {
    let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
    let fallback = trimmedName.isEmpty ? "attachment" : trimmedName
    let allowedCharacters = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    let scalars = fallback.unicodeScalars.map { scalar in
        allowedCharacters.contains(scalar) ? Character(scalar) : "_"
    }
    return String(scalars)
}

private extension ChatAttachment {
    var isImage: Bool {
        let normalizedType = type.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let normalizedMimeType = mimeType.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return normalizedType == "image" || normalizedMimeType.hasPrefix("image/")
    }
}

private struct ResolvedRuntimeModel {
    var provider: ModelProvider
    var capabilities: [String]
}

private extension ResolvedRuntimeModel {
    var supportsImageAttachments: Bool {
        capabilities.contains { capability in
            let normalized = capability.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            return normalized == "vision" || normalized == "image" || normalized == "multimodal"
        }
    }
}

private func requiredValue(_ key: String, in payload: [String: JSONValue]) throws -> JSONValue {
    guard let value = payload[key] else {
        throw LocalRuntimeRouterError.invalidPayload("Missing required payload field: \(key)")
    }
    return value
}

private func requiredString(_ key: String, in payload: [String: JSONValue]) throws -> String {
    let value = try requiredValue(key, in: payload)
    guard case .string(let string) = value, !string.isEmpty else {
        throw LocalRuntimeRouterError.invalidPayload("Payload field \(key) must be a non-empty string")
    }
    return string
}

private func optionalString(_ key: String, in payload: [String: JSONValue]) -> String? {
    guard let value = payload[key], case .string(let string) = value, !string.isEmpty else {
        return nil
    }
    return string
}

private func optionalInt(_ key: String, in payload: [String: JSONValue]) -> Int? {
    guard let value = payload[key] else { return nil }
    switch value {
    case .number(let number):
        return Int(number)
    case .string(let string):
        return Int(string.trimmingCharacters(in: .whitespacesAndNewlines))
    default:
        return nil
    }
}

private extension Array where Element == String {
    func cleanedSuggestions(maxCount: Int) -> [String] {
        var seen = Set<String>()
        var result: [String] = []
        for suggestion in self {
            let cleaned = suggestion
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .trimmingCharacters(in: CharacterSet(charactersIn: "\"'"))
            guard !cleaned.isEmpty else { continue }
            let key = cleaned.lowercased()
            guard !seen.contains(key) else { continue }
            seen.insert(key)
            result.append(cleaned)
            if result.count >= maxCount {
                break
            }
        }
        return result
    }
}
