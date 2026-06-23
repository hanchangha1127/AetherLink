import BridgeProtocol
import CryptoKit
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
                message: "Pair and authenticate this Android device before sending runtime commands.",
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
            guard let validation = pairingCoordinator.validate(request) else {
                sink.send(ProtocolEnvelope(
                    type: MessageType.pairingResult,
                    requestID: envelope.requestID,
                    payload: [
                        "accepted": .bool(false),
                        "message": .string("Pairing code was rejected or expired.")
                    ]
                ))
                return
            }

            try await trustedDeviceStore.trust(validation.trustedDevice)
            markAuthenticated(connectionID: sink.connectionID, deviceID: validation.trustedDevice.id)
            onPairingAccepted?(validation.trustedDevice)

            sink.send(ProtocolEnvelope(
                type: MessageType.pairingResult,
                requestID: envelope.requestID,
                payload: [
                    "accepted": .bool(true),
                    "mac_device_id": .string(validation.macDeviceID),
                    "trusted_device_id": .string(validation.trustedDevice.id),
                    "message": .string("\(validation.trustedDevice.name) is now trusted by \(validation.macName).")
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
                    message: "This Android device is not trusted by the Mac runtime.",
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
                    message: "Could not authenticate this Android device.",
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
                        "message": .string("Ollama is not enabled in the Mac runtime."),
                        "retryable": .bool(false)
                    ]),
                    "lm_studio": providerPayloads[.lmStudio] ?? .object([
                        "available": .bool(false),
                        "code": .string("backend_unavailable"),
                        "message": .string("LM Studio is not enabled in the Mac runtime."),
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
                        "message": .string("\(backend.provider.displayName) is reachable from the Mac runtime")
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
                        if let remoteHost = model.remoteHost, !remoteHost.isEmpty {
                            payload["remote_host"] = .string(remoteHost)
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
            try await requireInstalledModel(request.model)
            for try await event in backend.chat(request: request) {
                switch event {
                case .delta(let text):
                    sink.send(ProtocolEnvelope(
                        type: MessageType.chatDelta,
                        requestID: envelope.requestID,
                        payload: ["delta": .string(text)]
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

    private func requireInstalledModel(_ requestedModel: String) async throws {
        let models = try await backend.listModels()
        if let resolved = ModelProvider.splitQualifiedModelID(requestedModel) {
            let isInstalled = models.contains { model in
                model.installed
                    && model.provider == resolved.provider
                    && (
                        model.id == resolved.modelID
                            || model.name == resolved.modelID
                            || model.providerModelID == resolved.modelID
                            || Self.canonicalModelName(model.id) == Self.canonicalModelName(resolved.modelID)
                            || Self.canonicalModelName(model.providerModelID) == Self.canonicalModelName(resolved.modelID)
                    )
            }
            guard isInstalled else {
                throw LocalRuntimeRouterError.modelNotInstalled(requestedModel)
            }
            return
        }

        let requestedCanonicalName = Self.canonicalModelName(requestedModel)
        let isInstalled = models.contains { model in
            model.installed && (
                model.id == requestedModel
                    || model.name == requestedModel
                    || model.providerModelID == requestedModel
                    || Self.canonicalModelName(model.id) == requestedCanonicalName
                    || Self.canonicalModelName(model.name) == requestedCanonicalName
                    || Self.canonicalModelName(model.providerModelID) == requestedCanonicalName
            )
        }
        guard isInstalled else {
            throw LocalRuntimeRouterError.modelNotInstalled(requestedModel)
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
            return ChatMessage(
                role: try requiredString("role", in: object),
                content: try requiredString("content", in: object)
            )
        }

        return ChatRequest(
            generationID: envelope.requestID,
            sessionID: sessionID,
            model: model,
            messages: messages
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
                "message": .string("Backend is reachable from the Mac runtime")
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

private enum LocalRuntimeRouterError: Error, LocalizedError {
    case invalidPayload(String)
    case modelNotInstalled(String)

    var code: String {
        switch self {
        case .invalidPayload:
            return "invalid_payload"
        case .modelNotInstalled:
            return "model_not_installed"
        }
    }

    var errorDescription: String? {
        switch self {
        case .invalidPayload(let message):
            return message
        case .modelNotInstalled(let model):
            return "Model '\(model)' is not installed on the Mac runtime. Pull it through the Mac runtime before sending chat."
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
