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
    private let chatEventStore: any RuntimeChatEventStore
    private let memoryStore: any RuntimeMemoryStore
    private let routeRefresher: (any RuntimeRouteRefreshing)?
    private let runtimeChallengeSigner: (any RuntimeChallengeSigning)?
    private let onPairingAccepted: (@Sendable (TrustedDevice) -> Void)?
    private let dateFormatter = ISO8601DateFormatter()
    private let authLock = NSLock()
    private var authSessions: [UUID: AuthSessionState] = [:]

    public init(
        backend: any LlmBackend,
        requiresAuthentication: Bool = true,
        pairingCoordinator: PairingCoordinator = PairingCoordinator(),
        trustedDeviceStore: TrustedDeviceStore = TrustedDeviceStore(),
        chatEventStore: any RuntimeChatEventStore = JSONLRuntimeChatEventStore(),
        memoryStore: any RuntimeMemoryStore = JSONLRuntimeMemoryStore(),
        routeRefresher: (any RuntimeRouteRefreshing)? = nil,
        runtimeChallengeSigner: (any RuntimeChallengeSigning)? = nil,
        onPairingAccepted: (@Sendable (TrustedDevice) -> Void)? = nil
    ) {
        self.backend = backend
        self.requiresAuthentication = requiresAuthentication
        self.pairingCoordinator = pairingCoordinator
        self.trustedDeviceStore = trustedDeviceStore
        self.chatEventStore = chatEventStore
        self.memoryStore = memoryStore
        self.routeRefresher = routeRefresher
        self.runtimeChallengeSigner = runtimeChallengeSigner
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
        case MessageType.routeRefresh:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleRouteRefresh(envelope, sink: sink)
        case MessageType.chatSend:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleChatSend(envelope, sink: sink)
        case MessageType.chatCancel:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatCancel(envelope, sink: sink)
        case MessageType.chatSessionsList:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionsList(envelope, sink: sink)
        case MessageType.chatMessagesList:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatMessagesList(envelope, sink: sink)
        case MessageType.chatSuggestionsRequest:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleChatSuggestionsRequest(envelope, sink: sink)
        case MessageType.chatTitleRequest:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleChatTitleRequest(envelope, sink: sink)
        case MessageType.chatSessionRename:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionRename(envelope, sink: sink)
        case MessageType.chatSessionArchive:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionMutation(envelope, sink: sink, mutation: .archive)
        case MessageType.chatSessionRestore:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionMutation(envelope, sink: sink, mutation: .restore)
        case MessageType.chatSessionDelete:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionMutation(envelope, sink: sink, mutation: .delete)
        case MessageType.memoryList:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleMemoryList(envelope, sink: sink)
        case MessageType.memoryUpsert:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleMemoryUpsert(envelope, sink: sink)
        case MessageType.memoryDelete:
            guard allowRuntimeCommand(envelope, sink: sink) else { return }
            handleMemoryDelete(envelope, sink: sink)
        default:
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                code: "unknown_message_type",
                message: "Unsupported AetherLink Runtime message type: \(envelope.type)",
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
                message: "Pair and authenticate this device before sending runtime commands.",
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
            _ = try await resolvedInstalledChatModel(parsedRequest.request.model)

            var generatedText = ""
            var inlineReasoningSplitter = RuntimeInlineReasoningSplitter()
            for try await event in backend.chat(request: parsedRequest.request) {
                switch event {
                case .delta(let text):
                    generatedText += inlineReasoningSplitter.split(text).answerText
                case .reasoningDelta:
                    continue
                case .done:
                    generatedText += inlineReasoningSplitter.flush().answerText
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

    private func handleChatTitleRequest(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            let parsedRequest = try chatTitleRequest(from: envelope)
            _ = try await resolvedInstalledChatModel(parsedRequest.request.model)

            var generatedText = ""
            var inlineReasoningSplitter = RuntimeInlineReasoningSplitter()
            for try await event in backend.chat(request: parsedRequest.request) {
                switch event {
                case .delta(let text):
                    generatedText += inlineReasoningSplitter.split(text).answerText
                case .reasoningDelta:
                    continue
                case .done:
                    generatedText += inlineReasoningSplitter.flush().answerText
                    break
                }
            }

            let title = Self.title(from: generatedText)
            if !title.isEmpty {
                try recordChatEvent(.init(
                    kind: .title,
                    requestID: envelope.requestID,
                    sessionID: parsedRequest.request.sessionID,
                    model: parsedRequest.request.model,
                    title: title
                ))
            }

            sink.send(ProtocolEnvelope(
                type: MessageType.chatTitleResult,
                requestID: envelope.requestID,
                payload: [
                    "title": .string(title)
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
                    message: "This device is not trusted by AetherLink Runtime.",
                    retryable: false
                ))
                return
            }

            let nonce = Self.makeNonce()
            setChallenge(connectionID: sink.connectionID, deviceID: deviceID, nonce: nonce)
            var payload: [String: JSONValue] = [
                "device_id": .string(deviceID),
                "nonce": .string(nonce)
            ]
            if let runtimeChallengeSigner {
                let proof = try runtimeChallengeSigner.signAuthChallenge(deviceID: deviceID, nonce: nonce)
                payload["runtime_key_fingerprint"] = .string(proof.runtimeKeyFingerprint)
                payload["runtime_signature"] = .string(proof.signatureBase64)
            }
            sink.send(ProtocolEnvelope(
                type: MessageType.authChallenge,
                requestID: envelope.requestID,
                payload: payload
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
                    message: "Could not authenticate this device.",
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
                        "message": .string("Ollama is not enabled in AetherLink Runtime."),
                        "retryable": .bool(false)
                    ]),
                    "lm_studio": providerPayloads[.lmStudio] ?? .object([
                        "available": .bool(false),
                        "code": .string("backend_unavailable"),
                        "message": .string("LM Studio is not enabled in AetherLink Runtime."),
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
                        "message": .string("\(backend.provider.displayName) is reachable from AetherLink Runtime")
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

    private func handleRouteRefresh(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            guard let routeRefresher else {
                sink.send(errorEnvelope(
                    requestID: envelope.requestID,
                    code: "route_refresh_unavailable",
                    message: "AetherLink Runtime does not have a refreshable remote route configured.",
                    retryable: true
                ))
                return
            }
            guard let route = try await routeRefresher.refreshRuntimeRoute() else {
                sink.send(errorEnvelope(
                    requestID: envelope.requestID,
                    code: "route_refresh_unavailable",
                    message: "AetherLink Runtime could not refresh remote route material.",
                    retryable: true
                ))
                return
            }
            var payload: [String: JSONValue] = [
                "runtime_device_id": .string(route.runtimeDeviceID),
                "runtime_key_fingerprint": .string(route.runtimeKeyFingerprint),
                "relay_host": .string(route.relayHost),
                "relay_port": .number(Double(route.relayPort)),
                "relay_id": .string(route.relayID),
                "relay_secret": .string(route.relaySecret),
                "relay_expires_at": .number(Double(route.relayExpiresAtEpochMillis)),
                "relay_nonce": .string(route.relayNonce)
            ]
            if let relayScope = route.relayScope?.trimmingCharacters(in: .whitespacesAndNewlines),
               !relayScope.isEmpty {
                payload["relay_scope"] = .string(relayScope)
            }
            sink.send(ProtocolEnvelope(
                type: MessageType.routeRefresh,
                requestID: envelope.requestID,
                payload: payload
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleChatSend(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        var storageContext: RuntimeChatStorageContext?
        do {
            let clientRequest = try chatRequest(from: envelope)
            let locale = optionalString("locale", in: envelope.payload)
            storageContext = RuntimeChatStorageContext(
                requestID: envelope.requestID,
                sessionID: clientRequest.sessionID,
                model: clientRequest.model
            )
            let storedMessages = Self.chatStorageMessages(from: clientRequest.messages)
            let guardedRequest = Self.chatRequestWithRuntimeCapabilityGuard(clientRequest)
            let memoryEntries: [RuntimeMemoryEntry]
            do {
                memoryEntries = try memoryStore.list()
            } catch {
                throw LocalRuntimeRouterError.memoryStoreUnavailable(error.localizedDescription)
            }
            let request = Self.chatRequestWithRuntimeMemory(
                guardedRequest,
                memoryEntries: memoryEntries
            )
            let backendRequest = Self.chatRequestWithRuntimeConversationCompaction(request)
            try recordChatEvent(.init(
                kind: .request,
                requestID: envelope.requestID,
                sessionID: backendRequest.sessionID,
                model: backendRequest.model,
                messages: storedMessages
            ))
            let model = try await resolvedInstalledChatModel(backendRequest.model)
            try validateAttachments(in: backendRequest, for: model)
            var inlineReasoningSplitter = RuntimeInlineReasoningSplitter()
            for try await event in backend.chat(request: backendRequest) {
                switch event {
                case .delta(let text):
                    try emitChatSegments(
                        inlineReasoningSplitter.split(text),
                        requestID: envelope.requestID,
                        sessionID: backendRequest.sessionID,
                        model: backendRequest.model,
                        sink: sink
                    )
                case .reasoningDelta(let text):
                    try recordChatEvent(.init(
                        kind: .reasoningDelta,
                        requestID: envelope.requestID,
                        sessionID: backendRequest.sessionID,
                        model: backendRequest.model,
                        reasoningDelta: text
                    ))
                    sink.send(ProtocolEnvelope(
                        type: MessageType.chatDelta,
                        requestID: envelope.requestID,
                        payload: ["reasoning_delta": .string(text)]
                    ))
                case .done(let inputTokens, let outputTokens):
                    try emitChatSegments(
                        inlineReasoningSplitter.flush(),
                        requestID: envelope.requestID,
                        sessionID: backendRequest.sessionID,
                        model: backendRequest.model,
                        sink: sink
                    )
                    try recordChatEvent(.init(
                        kind: .done,
                        requestID: envelope.requestID,
                        sessionID: backendRequest.sessionID,
                        model: backendRequest.model,
                        finishReason: "stop",
                        usage: RuntimeChatStoredUsage(inputTokens: inputTokens, outputTokens: outputTokens)
                    ))
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
                    scheduleChatTitleGenerationIfNeeded(
                        sessionID: backendRequest.sessionID,
                        model: backendRequest.model,
                        sourceRequestID: envelope.requestID,
                        locale: locale
                    )
                }
            }
        } catch OllamaBackendError.generationCancelled {
            recordCancelledChatEventIfPossible(context: storageContext)
            sink.send(ProtocolEnvelope(
                type: MessageType.chatDone,
                requestID: envelope.requestID,
                payload: ["finish_reason": .string("cancelled")]
            ))
        } catch LMStudioBackendError.generationCancelled {
            recordCancelledChatEventIfPossible(context: storageContext)
            sink.send(ProtocolEnvelope(
                type: MessageType.chatDone,
                requestID: envelope.requestID,
                payload: ["finish_reason": .string("cancelled")]
            ))
        } catch let error as BackendError where error.code == "generation_cancelled" {
            recordCancelledChatEventIfPossible(context: storageContext)
            sink.send(ProtocolEnvelope(
                type: MessageType.chatDone,
                requestID: envelope.requestID,
                payload: ["finish_reason": .string("cancelled")]
            ))
        } catch {
            recordChatErrorIfPossible(context: storageContext, error: error)
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func recordChatEvent(_ event: RuntimeChatStoredEvent) throws {
        do {
            try chatEventStore.append(event)
        } catch {
            throw LocalRuntimeRouterError.chatStoreUnavailable(error.localizedDescription)
        }
    }

    private func emitChatSegments(
        _ segments: [RuntimeInlineReasoningSegment],
        requestID: String,
        sessionID: String,
        model: String,
        sink: any RuntimeMessageSink
    ) throws {
        for segment in segments {
            switch segment {
            case .answer(let text):
                guard !text.isEmpty else { continue }
                try recordChatEvent(.init(
                    kind: .assistantDelta,
                    requestID: requestID,
                    sessionID: sessionID,
                    model: model,
                    delta: text
                ))
                sink.send(ProtocolEnvelope(
                    type: MessageType.chatDelta,
                    requestID: requestID,
                    payload: ["delta": .string(text)]
                ))
            case .reasoning(let text):
                guard !text.isEmpty else { continue }
                try recordChatEvent(.init(
                    kind: .reasoningDelta,
                    requestID: requestID,
                    sessionID: sessionID,
                    model: model,
                    reasoningDelta: text
                ))
                sink.send(ProtocolEnvelope(
                    type: MessageType.chatDelta,
                    requestID: requestID,
                    payload: ["reasoning_delta": .string(text)]
                ))
            }
        }
    }

    private func mutateChatSession(
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation
    ) throws -> RuntimeChatSessionMutationResult {
        do {
            return try chatEventStore.mutateSession(
                sessionID: sessionID,
                requestID: requestID,
                mutation: mutation,
                timestamp: Date()
            )
        } catch RuntimeChatEventStoreError.sessionNotFound {
            throw LocalRuntimeRouterError.chatSessionNotFound(sessionID)
        } catch RuntimeChatEventStoreError.sessionMustBeArchivedBeforeDelete {
            throw LocalRuntimeRouterError.chatSessionMustBeArchivedBeforeDelete(sessionID)
        } catch {
            throw LocalRuntimeRouterError.chatStoreUnavailable(error.localizedDescription)
        }
    }

    private func recordCancelledChatEventIfPossible(context: RuntimeChatStorageContext?) {
        guard let context else { return }
        try? recordChatEvent(.init(
            kind: .cancelled,
            requestID: context.requestID,
            sessionID: context.sessionID,
            model: context.model,
            finishReason: "cancelled"
        ))
    }

    private func recordChatErrorIfPossible(context: RuntimeChatStorageContext?, error: Error) {
        guard let context else { return }
        try? recordChatEvent(.init(
            kind: .error,
            requestID: context.requestID,
            sessionID: context.sessionID,
            model: context.model,
            error: RuntimeChatStoredError(
                code: errorCode(for: error),
                message: error.localizedDescription
            )
        ))
    }

    private func resolvedInstalledChatModel(_ requestedModel: String) async throws -> ResolvedRuntimeModel {
        let models = try await backend.listModels()
        if let resolved = ModelProvider.splitQualifiedModelID(requestedModel) {
            if let model = models.first(where: { model in
                model.installed
                    && model.source == .local
                    && model.provider == resolved.provider
                    && (
                        model.id == resolved.modelID
                            || model.name == resolved.modelID
                            || model.providerModelID == resolved.modelID
                            || Self.canonicalModelName(model.id) == Self.canonicalModelName(resolved.modelID)
                            || Self.canonicalModelName(model.providerModelID) == Self.canonicalModelName(resolved.modelID)
                    )
            }) {
                return try Self.resolvedChatModel(
                    provider: model.provider,
                    kind: model.kind,
                    capabilities: model.capabilities,
                    requestedModel: requestedModel
                )
            }
            throw LocalRuntimeRouterError.modelNotInstalled(requestedModel)
        }

        let requestedCanonicalName = Self.canonicalModelName(requestedModel)
        if let model = models.first(where: { model in
            model.installed && model.source == .local && (
                model.id == requestedModel
                    || model.name == requestedModel
                    || model.providerModelID == requestedModel
                    || Self.canonicalModelName(model.id) == requestedCanonicalName
                    || Self.canonicalModelName(model.name) == requestedCanonicalName
                    || Self.canonicalModelName(model.providerModelID) == requestedCanonicalName
            )
        }) {
            return try Self.resolvedChatModel(
                provider: model.provider,
                kind: model.kind,
                capabilities: model.capabilities,
                requestedModel: requestedModel
            )
        }
        throw LocalRuntimeRouterError.modelNotInstalled(requestedModel)
    }

    private static func resolvedChatModel(
        provider: ModelProvider,
        kind: ModelKind,
        capabilities: [String],
        requestedModel: String
    ) throws -> ResolvedRuntimeModel {
        guard kind == ModelKind.chat else {
            throw LocalRuntimeRouterError.modelNotInstalled(requestedModel)
        }
        return ResolvedRuntimeModel(
            provider: provider,
            kind: kind,
            capabilities: capabilities
        )
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

    private func handleChatSessionsList(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let limit = optionalInt("limit", in: envelope.payload).map { min(max($0, 1), 200) } ?? 100
            let includeArchived = optionalBool("include_archived", in: envelope.payload) ?? false
            let sessions = try chatEventStore.listSessions(limit: limit, includeArchived: includeArchived)
            sink.send(ProtocolEnvelope(
                type: MessageType.chatSessionsList,
                requestID: envelope.requestID,
                payload: [
                    "sessions": .array(sessions.map { session in
                        var payload: [String: JSONValue] = [
                            "session_id": .string(session.sessionID),
                            "title": .string(session.title),
                            "model": .string(session.model),
                            "last_activity_at": .string(dateFormatter.string(from: session.lastActivityAt)),
                            "message_count": .number(Double(session.messageCount)),
                            "status": .string(session.status)
                        ]
                        if let archivedAt = session.archivedAt {
                            payload["archived_at"] = .string(dateFormatter.string(from: archivedAt))
                        }
                        if let lastEvent = session.lastEvent {
                            payload["last_event"] = .string(lastEvent)
                        }
                        if let lastFinishReason = session.lastFinishReason {
                            payload["last_finish_reason"] = .string(lastFinishReason)
                        }
                        if let lastErrorCode = session.lastErrorCode {
                            payload["last_error_code"] = .string(lastErrorCode)
                        }
                        return .object(payload)
                    })
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: LocalRuntimeRouterError.chatStoreUnavailable(error.localizedDescription)))
        }
    }

    private func handleChatMessagesList(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let sessionID = try requiredString("session_id", in: envelope.payload)
            let limit = optionalInt("limit", in: envelope.payload).map { min(max($0, 1), 500) } ?? 200
            let messages = try chatEventStore.listMessages(sessionID: sessionID, limit: limit)
            sink.send(ProtocolEnvelope(
                type: MessageType.chatMessagesList,
                requestID: envelope.requestID,
                payload: [
                    "session_id": .string(sessionID),
                    "messages": .array(messages.map { message in
                        var payload: [String: JSONValue] = [
                            "role": .string(message.role),
                            "content": .string(message.content)
                        ]
                        if let reasoning = message.reasoning, !reasoning.isEmpty {
                            payload["reasoning"] = .string(reasoning)
                        }
                        if let createdAt = message.createdAt {
                            payload["created_at"] = .string(dateFormatter.string(from: createdAt))
                        }
                        if !message.attachments.isEmpty {
                            payload["attachments"] = .array(message.attachments.map { attachment in
                                var attachmentPayload: [String: JSONValue] = [
                                    "type": .string(attachment.type),
                                    "mime_type": .string(attachment.mimeType)
                                ]
                                if let name = attachment.name, !name.isEmpty {
                                    attachmentPayload["name"] = .string(name)
                                }
                                if let text = attachment.text, !text.isEmpty {
                                    attachmentPayload["text"] = .string(text)
                                }
                                return .object(attachmentPayload)
                            })
                        }
                        return .object(payload)
                    })
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleChatSessionMutation(
        _ envelope: ProtocolEnvelope,
        sink: any RuntimeMessageSink,
        mutation: RuntimeChatSessionMutation
    ) {
        do {
            let sessionID = try requiredString("session_id", in: envelope.payload)
            let result = try mutateChatSession(
                sessionID: sessionID,
                requestID: envelope.requestID,
                mutation: mutation
            )
            sink.send(ProtocolEnvelope(
                type: mutation.messageType,
                requestID: envelope.requestID,
                payload: [
                    "session_id": .string(result.sessionID),
                    "status": .string(result.mutation.rawValue),
                    mutation.timestampPayloadKey: .string(dateFormatter.string(from: result.timestamp))
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleChatSessionRename(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let sessionID = try requiredString("session_id", in: envelope.payload)
            let title = try requiredString("title", in: envelope.payload)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard !title.isEmpty else {
                throw LocalRuntimeRouterError.invalidPayload("Payload field title must be a non-empty string")
            }
            guard let session = try chatEventStore
                .listSessions(limit: Int.max, includeArchived: true)
                .first(where: { $0.sessionID == sessionID }) else {
                throw RuntimeChatEventStoreError.sessionNotFound(sessionID)
            }
            let renamedAt = Date()
            try recordChatEvent(.init(
                timestamp: renamedAt,
                kind: .title,
                requestID: envelope.requestID,
                sessionID: sessionID,
                model: session.model,
                title: title
            ))
            sink.send(ProtocolEnvelope(
                type: MessageType.chatSessionRename,
                requestID: envelope.requestID,
                payload: [
                    "session_id": .string(sessionID),
                    "title": .string(title),
                    "renamed_at": .string(dateFormatter.string(from: renamedAt))
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleMemoryList(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let entries = try memoryStore.list()
            sink.send(ProtocolEnvelope(
                type: MessageType.memoryList,
                requestID: envelope.requestID,
                payload: [
                    "entries": .array(entries.map { .object(memoryEntryPayload($0)) })
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: LocalRuntimeRouterError.memoryStoreUnavailable(error.localizedDescription)))
        }
    }

    private func handleMemoryUpsert(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let entry = try memoryStore.upsert(
                id: optionalString("id", in: envelope.payload),
                content: try requiredString("content", in: envelope.payload),
                enabled: optionalBool("enabled", in: envelope.payload),
                timestamp: Date()
            )
            sink.send(ProtocolEnvelope(
                type: MessageType.memoryUpsert,
                requestID: envelope.requestID,
                payload: [
                    "entry": .object(memoryEntryPayload(entry))
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleMemoryDelete(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let result = try memoryStore.delete(
                id: try requiredString("id", in: envelope.payload),
                timestamp: Date()
            )
            sink.send(ProtocolEnvelope(
                type: MessageType.memoryDelete,
                requestID: envelope.requestID,
                payload: [
                    "id": .string(result.id),
                    "deleted_at": .string(dateFormatter.string(from: result.deletedAt))
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func memoryEntryPayload(_ entry: RuntimeMemoryEntry) -> [String: JSONValue] {
        [
            "id": .string(entry.id),
            "content": .string(entry.content),
            "enabled": .bool(entry.enabled),
            "created_at": .string(dateFormatter.string(from: entry.createdAt)),
            "updated_at": .string(dateFormatter.string(from: entry.updatedAt))
        ]
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
            .map { min(max($0, 1), Self.maxChatSuggestionCount) }
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

    private func chatTitleRequest(from envelope: ProtocolEnvelope) throws -> ChatTitleRuntimeRequest {
        let baseRequest = try chatRequest(from: envelope)
        let locale = optionalString("locale", in: envelope.payload)
        let recentMessages = Array(baseRequest.messages.suffix(8))
        guard recentMessages.contains(where: { $0.role == "user" }) else {
            throw LocalRuntimeRouterError.invalidPayload("messages must include at least one user message")
        }
        guard recentMessages.contains(where: { $0.role == "assistant" }) else {
            throw LocalRuntimeRouterError.invalidPayload("messages must include at least one assistant message")
        }

        let titleRequest = ChatRequest(
            generationID: envelope.requestID,
            sessionID: baseRequest.sessionID,
            model: baseRequest.model,
            messages: Self.titlePromptMessages(
                recentMessages: recentMessages,
                locale: locale
            )
        )
        return ChatTitleRuntimeRequest(request: titleRequest)
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
        if let error = error as? RuntimeChatEventStoreError {
            let mappedError: LocalRuntimeRouterError
            switch error {
            case .sessionNotFound(let sessionID):
                mappedError = .chatSessionNotFound(sessionID)
            case .sessionMustBeArchivedBeforeDelete(let sessionID):
                mappedError = .chatSessionMustBeArchivedBeforeDelete(sessionID)
            case .corruptEventLog:
                mappedError = .chatStoreUnavailable(error.localizedDescription)
            }
            return errorEnvelope(requestID: requestID, error: mappedError)
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

    private func errorCode(for error: Error) -> String {
        if let error = error as? OllamaBackendError {
            return error.backendError.code
        }
        if let error = error as? LMStudioBackendError {
            return error.backendError.code
        }
        if let error = error as? BackendError {
            return error.code
        }
        if let error = error as? LocalRuntimeRouterError {
            return error.code
        }
        return "internal_error"
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
                "message": .string("Model provider is reachable from AetherLink Runtime")
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

    private func scheduleChatTitleGenerationIfNeeded(
        sessionID: String,
        model: String,
        sourceRequestID: String,
        locale: String?
    ) {
        Task {
            await generateAndStoreChatTitleIfNeeded(
                sessionID: sessionID,
                model: model,
                sourceRequestID: sourceRequestID,
                locale: locale
            )
        }
    }

    private func generateAndStoreChatTitleIfNeeded(
        sessionID: String,
        model: String,
        sourceRequestID: String,
        locale: String?
    ) async {
        do {
            let sessions = try chatEventStore.listSessions(limit: 200, includeArchived: true)
            guard let session = sessions.first(where: { $0.sessionID == sessionID }),
                  session.status == "active",
                  session.title.isPlaceholderChatTitle else {
                return
            }

            let storedMessages = try chatEventStore.listMessages(sessionID: sessionID, limit: 8)
            guard Self.isFirstAnsweredTurn(storedMessages) else { return }

            let promptMessages = storedMessages.map {
                ChatMessage(role: $0.role, content: $0.content)
            }
            let generatedTitle = await generatedChatTitle(
                sessionID: sessionID,
                model: model,
                messages: promptMessages,
                locale: locale
            )
            let title = generatedTitle.isEmpty
                ? Self.deterministicTitle(from: storedMessages)
                : generatedTitle
            guard !title.isEmpty else { return }

            try recordChatEvent(.init(
                kind: .title,
                requestID: "\(sourceRequestID)-title",
                sessionID: sessionID,
                model: model,
                title: title
            ))
        } catch {
            return
        }
    }

    private func generatedChatTitle(
        sessionID: String,
        model: String,
        messages: [ChatMessage],
        locale: String?
    ) async -> String {
        do {
            let request = ChatRequest(
                generationID: "\(sessionID)-title-\(UUID().uuidString)",
                sessionID: sessionID,
                model: model,
                messages: Self.titlePromptMessages(
                    recentMessages: messages,
                    locale: locale
                )
            )
            var generatedText = ""
            var inlineReasoningSplitter = RuntimeInlineReasoningSplitter()
            for try await event in backend.chat(request: request) {
                switch event {
                case .delta(let text):
                    generatedText += inlineReasoningSplitter.split(text).answerText
                case .reasoningDelta:
                    continue
                case .done:
                    generatedText += inlineReasoningSplitter.flush().answerText
                    break
                }
            }
            return Self.title(from: generatedText)
        } catch {
            return ""
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

    private static func titlePromptMessages(
        recentMessages: [ChatMessage],
        locale: String?
    ) -> [ChatMessage] {
        let localeInstruction = locale
            .map { "Use this BCP-47 locale when writing the title unless the conversation clearly uses another language: \($0)." }
            ?? "Use the same language as the conversation."
        return [
            ChatMessage(
                role: "system",
                content: """
                You generate a short title for a chat conversation.
                Return only strict JSON with this shape: {"title":"concise title"}.
                The title must be natural, specific to the recent conversation, and at most 8 words.
                Do not include markdown, quotes around the whole response, numbering, explanations, or extra keys.
                \(localeInstruction)
                """
            )
        ] + recentMessages + [
            ChatMessage(
                role: "user",
                content: "Generate the chat title now."
            )
        ]
    }

    private static func chatRequestWithRuntimeCapabilityGuard(_ request: ChatRequest) -> ChatRequest {
        guard !request.messages.contains(where: { $0.isAetherLinkCapabilityGuard }) else {
            return request
        }
        return ChatRequest(
            generationID: request.generationID,
            sessionID: request.sessionID,
            model: request.model,
            messages: [runtimeCapabilityGuardMessage] + request.messages
        )
    }

    private static func chatStorageMessages(from messages: [ChatMessage]) -> [ChatMessage] {
        messages.filter { message in
            !message.isAetherLinkCapabilityGuard && !message.isRuntimeUserMemoryContext
        }
    }

    private static func chatRequestWithRuntimeMemory(
        _ request: ChatRequest,
        memoryEntries: [RuntimeMemoryEntry]
    ) -> ChatRequest {
        var messages = request.messages.filter { !$0.isRuntimeUserMemoryContext }
        guard let memoryMessage = runtimeUserMemoryMessage(from: memoryEntries) else {
            return ChatRequest(
                generationID: request.generationID,
                sessionID: request.sessionID,
                model: request.model,
                messages: messages
            )
        }

        let insertIndex = messages.first?.isAetherLinkCapabilityGuard == true ? 1 : 0
        messages.insert(memoryMessage, at: insertIndex)
        return ChatRequest(
            generationID: request.generationID,
            sessionID: request.sessionID,
            model: request.model,
            messages: messages
        )
    }

    private static func chatRequestWithRuntimeConversationCompaction(_ request: ChatRequest) -> ChatRequest {
        let messages = request.messages.filter { !$0.isRuntimeConversationCompactionContext }
        let estimatedCharacters = estimatedRuntimeContextCharacters(in: messages)
        guard estimatedCharacters > runtimeConversationCompactionMaxContextCharacters else {
            return ChatRequest(
                generationID: request.generationID,
                sessionID: request.sessionID,
                model: request.model,
                messages: messages
            )
        }

        let conversationMessages = messages.enumerated().filter { $0.element.isConversationTurn }
        guard conversationMessages.count > runtimeConversationCompactionRecentTurnCount else {
            return ChatRequest(
                generationID: request.generationID,
                sessionID: request.sessionID,
                model: request.model,
                messages: messages
            )
        }

        let compactedMessages = Array(conversationMessages.dropLast(runtimeConversationCompactionRecentTurnCount))
        guard let summaryMessage = runtimeConversationCompactionMessage(
            from: compactedMessages.map(\.element)
        ) else {
            return ChatRequest(
                generationID: request.generationID,
                sessionID: request.sessionID,
                model: request.model,
                messages: messages
            )
        }

        let compactedIndices = Set(compactedMessages.map(\.offset))
        var compactedRequestMessages: [ChatMessage] = []
        var insertedSummary = false
        for (index, message) in messages.enumerated() {
            guard compactedIndices.contains(index) else {
                compactedRequestMessages.append(message)
                continue
            }
            if !insertedSummary {
                compactedRequestMessages.append(summaryMessage)
                insertedSummary = true
            }
        }

        return ChatRequest(
            generationID: request.generationID,
            sessionID: request.sessionID,
            model: request.model,
            messages: compactedRequestMessages
        )
    }

    private static func estimatedRuntimeContextCharacters(in messages: [ChatMessage]) -> Int {
        messages.reduce(0) { partialResult, message in
            partialResult + estimatedRuntimeContextCharacters(in: message)
        }
    }

    private static func estimatedRuntimeContextCharacters(in message: ChatMessage) -> Int {
        let attachmentCharacters = message.attachments.reduce(0) { partialResult, attachment in
            partialResult +
                (attachment.name?.count ?? 0) +
                (attachment.text?.count ?? 0) +
                (attachment.dataBase64?.count ?? 0)
        }
        return message.role.count + message.content.count + attachmentCharacters
    }

    private static func runtimeConversationCompactionMessage(from messages: [ChatMessage]) -> ChatMessage? {
        var remainingCharacters = runtimeConversationCompactionMaxSummaryCharacters
        var lines: [String] = [
            runtimeConversationCompactionPrefix,
            "Backend-only summary of older turns from this active session. The user-visible transcript is preserved separately; archived or deleted chats are not included."
        ]

        for message in messages {
            guard remainingCharacters > 0 else { break }
            let line = runtimeConversationCompactionLine(from: message, remainingCharacters: remainingCharacters)
            guard !line.isEmpty else { continue }
            lines.append(line)
            remainingCharacters -= line.count
            if lines.count >= runtimeConversationCompactionMaxSummaryLines {
                break
            }
        }

        guard lines.count > 2 else { return nil }
        return ChatMessage(
            role: "system",
            content: lines.joined(separator: "\n")
        )
    }

    private static func runtimeConversationCompactionLine(
        from message: ChatMessage,
        remainingCharacters: Int
    ) -> String {
        let role = message.normalizedRuntimeRole == "assistant" ? "Assistant" : "User"
        var content = normalizedRuntimeSummaryContent(message.content)
        if content.isEmpty {
            content = runtimeAttachmentSummary(from: message.attachments)
        }
        guard !content.isEmpty else { return "" }
        let prefix = "- \(role): "
        let availableCharacters = min(
            runtimeConversationCompactionMaxLineCharacters,
            max(0, remainingCharacters - prefix.count)
        )
        guard availableCharacters > 0 else { return "" }
        if content.count > availableCharacters {
            content = String(content.prefix(availableCharacters))
                .trimmingCharacters(in: .whitespacesAndNewlines) + "..."
        }
        return prefix + content
    }

    private static func normalizedRuntimeSummaryContent(_ content: String) -> String {
        content
            .components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func runtimeAttachmentSummary(from attachments: [ChatAttachment]) -> String {
        let summaries = attachments.compactMap { attachment -> String? in
            let name = attachment.name?.trimmingCharacters(in: .whitespacesAndNewlines)
            let mimeType = attachment.mimeType.trimmingCharacters(in: .whitespacesAndNewlines)
            let label = [name, mimeType.isEmpty ? nil : mimeType].compactMap { $0 }.joined(separator: ", ")
            guard !label.isEmpty else { return nil }
            return "[attachment: \(label)]"
        }
        return summaries.joined(separator: " ")
    }

    private static func runtimeUserMemoryMessage(from memoryEntries: [RuntimeMemoryEntry]) -> ChatMessage? {
        var remainingCharacters = runtimeUserMemoryMaxCharacters
        var lines: [String] = []
        for entry in memoryEntries where entry.enabled {
            let content = normalizedRuntimeMemoryContent(entry.content)
            guard !content.isEmpty else { continue }
            let prefix = "- "
            let availableCharacters = remainingCharacters - prefix.count
            guard availableCharacters > 0 else { break }
            let boundedContent: String
            if content.count > availableCharacters {
                boundedContent = String(content.prefix(availableCharacters))
                    .trimmingCharacters(in: .whitespacesAndNewlines)
            } else {
                boundedContent = content
            }
            guard !boundedContent.isEmpty else { continue }
            lines.append(prefix + boundedContent)
            remainingCharacters -= prefix.count + boundedContent.count
            if lines.count >= runtimeUserMemoryMaxEntries || remainingCharacters <= 0 {
                break
            }
        }
        guard !lines.isEmpty else { return nil }
        return ChatMessage(
            role: "system",
            content: runtimeUserMemoryPrefix + "\n" + lines.joined(separator: "\n")
        )
    }

    private static func normalizedRuntimeMemoryContent(_ content: String) -> String {
        content
            .components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static let runtimeCapabilityGuardMessage = ChatMessage(
        role: "system",
        content: """
        AetherLink currently provides runtime-mediated local model chat, model listing, file/image attachment handling when supported, chat titles, and suggested next questions.
        The current build does not provide live web search, browsing, MCP tools, skills, scheduled automations, Python execution, or other external tools unless explicit tool output is included in this conversation.
        Do not claim that you can search the web, browse, run tools, access files, or use unavailable integrations. If asked for an unavailable capability, say it is not available in this build and offer the closest supported alternative.
        """
    )

    private static let runtimeUserMemoryPrefix = "Runtime user memory:"
    private static let runtimeUserMemoryMaxEntries = 8
    private static let runtimeUserMemoryMaxCharacters = 1_500
    private static let runtimeConversationCompactionPrefix = "Runtime conversation summary:"
    private static let runtimeConversationCompactionMaxContextCharacters = 24_000
    private static let runtimeConversationCompactionRecentTurnCount = 12
    private static let runtimeConversationCompactionMaxSummaryCharacters = 4_000
    private static let runtimeConversationCompactionMaxSummaryLines = 24
    private static let runtimeConversationCompactionMaxLineCharacters = 320

    private static let maxChatSuggestionCount = 4

    private static func suggestions(from rawText: String, maxSuggestions: Int) -> [String] {
        let trimmedText = rawText.trimmingCharacters(in: .whitespacesAndNewlines)
        let decoder = JSONDecoder()
        if let data = jsonPayloadText(from: trimmedText).data(using: .utf8) {
            if let result = try? decoder.decode(ChatSuggestionsResult.self, from: data) {
                return result.suggestions.cleanedSuggestions(maxCount: maxSuggestions)
            }
        }
        return fallbackSuggestionList(from: trimmedText, maxSuggestions: maxSuggestions)
    }

    private static func title(from rawText: String) -> String {
        let trimmedText = rawText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedText.isEmpty else { return "" }

        let decoder = JSONDecoder()
        let fencedPayload = fencedCodePayload(from: trimmedText)
        let jsonCandidate = fencedPayload ?? trimmedText
        if let data = jsonCandidate.data(using: .utf8),
           let result = try? decoder.decode(ChatTitleResult.self, from: data) {
            return result.title.cleanedTitle()
        }

        if fencedPayload != nil {
            return ""
        }

        if trimmedText.hasPrefix("{") || trimmedText.hasPrefix("[") {
            return ""
        }

        return trimmedText.cleanedTitle()
    }

    private static func jsonPayloadText(from text: String) -> String {
        let trimmedText = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let fencedPayload = fencedCodePayload(from: trimmedText) else {
            return trimmedText
        }
        return fencedPayload
    }

    private static func fencedCodePayload(from text: String) -> String? {
        guard let openingFence = text.range(of: "```") else { return nil }
        let afterOpeningFence = text[openingFence.upperBound...]
        guard let firstLineBreak = afterOpeningFence.firstIndex(of: "\n") else { return nil }
        let bodyStart = afterOpeningFence.index(after: firstLineBreak)
        let bodySlice: Substring
        if let closingFence = afterOpeningFence[bodyStart...].range(of: "```") {
            bodySlice = afterOpeningFence[bodyStart..<closingFence.lowerBound]
        } else {
            bodySlice = afterOpeningFence[bodyStart...]
        }
        let body = String(bodySlice).trimmingCharacters(in: .whitespacesAndNewlines)
        return body.isEmpty ? nil : body
    }

    private static func fallbackSuggestionList(from text: String, maxSuggestions: Int) -> [String] {
        let candidates = text
            .components(separatedBy: .newlines)
            .filter { $0.hasSuggestionListPrefix }
        return candidates.cleanedSuggestions(maxCount: maxSuggestions)
    }

    private static func isFirstAnsweredTurn(_ messages: [RuntimeChatStoredMessage]) -> Bool {
        let visibleMessages = messages.filter { message in
            let role = message.role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            return role == "user" || role == "assistant"
        }
        guard visibleMessages.count == 2 else { return false }
        return visibleMessages.first?.role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "user"
            && visibleMessages.last?.role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "assistant"
            && !visibleMessages.last!.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private static func deterministicTitle(from messages: [RuntimeChatStoredMessage]) -> String {
        let assistantText = messages
            .first { $0.role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "assistant" }?
            .content ?? ""
        let userText = messages
            .first { $0.role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "user" }?
            .content ?? ""

        let source = assistantText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? userText
            : assistantText
        let sentence = source
            .components(separatedBy: CharacterSet(charactersIn: ".!?\n"))
            .first ?? source
        return sentence.cleanedTitle(maxWordCount: 6, maxCharacterCount: 60)
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

private struct ChatTitleRuntimeRequest {
    var request: ChatRequest
}

private struct RuntimeChatStorageContext {
    var requestID: String
    var sessionID: String
    var model: String
}

private extension RuntimeChatSessionMutation {
    var messageType: String {
        switch self {
        case .archive:
            return MessageType.chatSessionArchive
        case .restore:
            return MessageType.chatSessionRestore
        case .delete:
            return MessageType.chatSessionDelete
        }
    }

    var timestampPayloadKey: String {
        switch self {
        case .archive:
            return "archived_at"
        case .restore:
            return "restored_at"
        case .delete:
            return "deleted_at"
        }
    }
}

private struct ChatSuggestionsResult: Decodable {
    var suggestions: [String]
}

private struct ChatTitleResult: Decodable {
    var title: String
}

private enum LocalRuntimeRouterError: Error, LocalizedError {
    case invalidPayload(String)
    case modelNotInstalled(String)
    case unsupportedAttachment(String)
    case unreadableAttachment(String)
    case chatSessionNotFound(String)
    case chatSessionMustBeArchivedBeforeDelete(String)
    case chatStoreUnavailable(String)
    case memoryStoreUnavailable(String)

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
        case .chatSessionNotFound:
            return "chat_session_not_found"
        case .chatSessionMustBeArchivedBeforeDelete:
            return "chat_session_must_be_archived_before_delete"
        case .chatStoreUnavailable:
            return "chat_store_unavailable"
        case .memoryStoreUnavailable:
            return "memory_store_unavailable"
        }
    }

    var errorDescription: String? {
        switch self {
        case .invalidPayload(let message):
            return message
        case .modelNotInstalled(let model):
            return "Model '\(model)' is not installed in AetherLink Runtime. Pull it through AetherLink Runtime before sending chat."
        case .unsupportedAttachment(let message),
             .unreadableAttachment(let message):
            return message
        case .chatSessionNotFound(let sessionID):
            return "Chat session not found in AetherLink Runtime: \(sessionID)"
        case .chatSessionMustBeArchivedBeforeDelete(let sessionID):
            return "Archive this chat before permanently deleting it: \(sessionID)"
        case .chatStoreUnavailable(let message):
            return "The runtime could not access chat history on this host: \(message)"
        case .memoryStoreUnavailable(let message):
            return "The runtime could not save memory information on this host: \(message)"
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
            preservedAttachments.append(ChatAttachment(
                type: attachment.type,
                mimeType: attachment.mimeType,
                name: attachment.name,
                dataBase64: nil,
                text: text
            ))
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
        preservedAttachments.append(ChatAttachment(
            type: attachment.type,
            mimeType: extracted.mimeType,
            name: extracted.fileName,
            dataBase64: nil,
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

private extension ChatMessage {
    var normalizedRuntimeRole: String {
        role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    var isConversationTurn: Bool {
        normalizedRuntimeRole == "user" || normalizedRuntimeRole == "assistant"
    }

    var isAetherLinkCapabilityGuard: Bool {
        guard normalizedRuntimeRole == "system" else {
            return false
        }
        let lowercasedContent = content.lowercased()
        return lowercasedContent.contains("aetherlink currently provides runtime-mediated local model chat") &&
            lowercasedContent.contains("does not provide live web search") &&
            lowercasedContent.contains("do not claim that you can search the web")
    }

    var isRuntimeUserMemoryContext: Bool {
        guard normalizedRuntimeRole == "system" else {
            return false
        }
        return content
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            .hasPrefix("runtime user memory:")
    }

    var isRuntimeConversationCompactionContext: Bool {
        guard normalizedRuntimeRole == "system" else {
            return false
        }
        return content
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            .hasPrefix("runtime conversation summary:")
    }
}

private struct ResolvedRuntimeModel {
    var provider: ModelProvider
    var kind: ModelKind
    var capabilities: [String]
}

private enum RuntimeInlineReasoningSegment: Equatable {
    case answer(String)
    case reasoning(String)
}

private struct RuntimeInlineReasoningSplitter {
    private var isReasoningOpen = false
    private var pendingTagFragment = ""

    mutating func split(_ text: String) -> [RuntimeInlineReasoningSegment] {
        guard !text.isEmpty else { return [] }

        var input = pendingTagFragment + text
        pendingTagFragment = ""
        if let partialTagRange = input.trailingPartialInlineReasoningTagRange {
            pendingTagFragment = String(input[partialTagRange])
            input.removeSubrange(partialTagRange)
        }

        guard !input.isEmpty else { return [] }
        return splitCompleteText(input)
    }

    mutating func flush() -> [RuntimeInlineReasoningSegment] {
        guard !pendingTagFragment.isEmpty else { return [] }
        defer { pendingTagFragment = "" }
        return [
            isReasoningOpen ? .reasoning(pendingTagFragment) : .answer(pendingTagFragment)
        ]
    }

    private mutating func splitCompleteText(_ text: String) -> [RuntimeInlineReasoningSegment] {
        var segments: [RuntimeInlineReasoningSegment] = []
        var cursor = text.startIndex

        while cursor < text.endIndex {
            if isReasoningOpen {
                guard let closeTag = text.nextInlineReasoningTag(from: cursor, matching: .close) else {
                    segments.appendMerging(.reasoning(String(text[cursor...])))
                    cursor = text.endIndex
                    continue
                }

                segments.appendMerging(.reasoning(String(text[cursor..<closeTag.range.lowerBound])))
                cursor = closeTag.range.upperBound
                isReasoningOpen = false
            } else {
                guard let tag = text.nextInlineReasoningTag(from: cursor) else {
                    segments.appendMerging(.answer(String(text[cursor...])))
                    cursor = text.endIndex
                    continue
                }

                switch tag.kind {
                case .open:
                    segments.appendMerging(.answer(String(text[cursor..<tag.range.lowerBound])))
                    cursor = tag.range.upperBound
                    isReasoningOpen = true
                case .close:
                    segments.appendMerging(.answer(String(text[cursor..<tag.range.lowerBound])))
                    cursor = tag.range.upperBound
                }
            }
        }

        return segments
    }
}

private enum RuntimeInlineReasoningTagKind {
    case open
    case close

    static let tokens: [(kind: RuntimeInlineReasoningTagKind, value: String)] = [
        (.open, "<think>"),
        (.open, "<thinking>"),
        (.close, "</think>"),
        (.close, "</thinking>")
    ]
}

private extension Array where Element == RuntimeInlineReasoningSegment {
    var answerText: String {
        map { segment in
            if case .answer(let text) = segment {
                return text
            }
            return ""
        }.joined()
    }

    mutating func appendMerging(_ segment: RuntimeInlineReasoningSegment) {
        switch segment {
        case .answer(let text), .reasoning(let text):
            guard !text.isEmpty else { return }
        }

        guard let last = popLast() else {
            append(segment)
            return
        }

        switch (last, segment) {
        case (.answer(let lhs), .answer(let rhs)):
            append(.answer(lhs + rhs))
        case (.reasoning(let lhs), .reasoning(let rhs)):
            append(.reasoning(lhs + rhs))
        default:
            append(last)
            append(segment)
        }
    }
}

private extension String {
    typealias RuntimeInlineReasoningTag = (kind: RuntimeInlineReasoningTagKind, range: Range<String.Index>)

    func nextInlineReasoningTag(
        from cursor: String.Index,
        matching expectedKind: RuntimeInlineReasoningTagKind? = nil
    ) -> RuntimeInlineReasoningTag? {
        var best: RuntimeInlineReasoningTag?
        for token in RuntimeInlineReasoningTagKind.tokens where expectedKind == nil || token.kind == expectedKind {
            guard let range = range(
                of: token.value,
                options: [.caseInsensitive],
                range: cursor..<endIndex
            ) else {
                continue
            }
            if best == nil || range.lowerBound < best!.range.lowerBound {
                best = (token.kind, range)
            }
        }
        return best
    }

    var trailingPartialInlineReasoningTagRange: Range<String.Index>? {
        guard let tagStart = lastIndex(of: "<") else { return nil }
        let suffix = String(self[tagStart...]).lowercased()
        guard !RuntimeInlineReasoningTagKind.tokens.contains(where: { $0.value == suffix }) else {
            return nil
        }
        return RuntimeInlineReasoningTagKind.tokens.contains(where: { $0.value.hasPrefix(suffix) })
            ? tagStart..<endIndex
            : nil
    }
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

private func optionalBool(_ key: String, in payload: [String: JSONValue]) -> Bool? {
    guard let value = payload[key] else { return nil }
    switch value {
    case .bool(let bool):
        return bool
    case .string(let string):
        return Bool(string.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())
    default:
        return nil
    }
}

private extension Array where Element == String {
    func cleanedSuggestions(maxCount: Int) -> [String] {
        var seen = Set<String>()
        var result: [String] = []
        for suggestion in self {
            let cleaned = suggestion.cleanedSuggestion()
            guard !cleaned.isEmpty else { continue }
            let key = cleaned.suggestionDedupeKey
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

private extension String {
    var hasSuggestionListPrefix: Bool {
        range(
            of: #"^\s*(?:[-*•]\s+|\d{1,2}[\.)]\s+)"#,
            options: .regularExpression
        ) != nil
    }

    func cleanedSuggestion() -> String {
        var cleaned = trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "\"'`"))
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if let prefixRange = cleaned.range(of: #"^\s*(?:[-*•]\s+|\d{1,2}[\.)]\s+)"#, options: .regularExpression) {
            cleaned.removeSubrange(prefixRange)
        }
        return cleaned
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "\"'`"))
            .collapsedSuggestionWhitespace()
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var suggestionDedupeKey: String {
        collapsedSuggestionWhitespace()
            .folding(options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive], locale: .current)
            .lowercased()
    }

    func collapsedSuggestionWhitespace() -> String {
        components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
    }

    var isPlaceholderChatTitle: Bool {
        let normalized = trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return normalized.isEmpty || normalized == "new chat"
    }

    func cleanedTitle(maxWordCount: Int = 8, maxCharacterCount: Int = 80) -> String {
        var cleaned = trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "\"'`"))

        if cleaned.hasPrefix("```") {
            cleaned = cleaned
                .replacingOccurrences(of: "```json", with: "")
                .replacingOccurrences(of: "```", with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .trimmingCharacters(in: CharacterSet(charactersIn: "\"'`"))
        }

        let disallowedPrefixes = ["title:", "Title:", "- ", "* ", "1. "]
        for prefix in disallowedPrefixes where cleaned.hasPrefix(prefix) {
            cleaned = String(cleaned.dropFirst(prefix.count))
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }

        cleaned = cleaned
            .components(separatedBy: .newlines)
            .first?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !cleaned.isEmpty else { return "" }

        let words = cleaned.split(whereSeparator: { $0.isWhitespace })
        if words.count > maxWordCount {
            cleaned = words.prefix(maxWordCount).joined(separator: " ")
        }
        if cleaned.count > maxCharacterCount {
            let index = cleaned.index(cleaned.startIndex, offsetBy: maxCharacterCount)
            cleaned = String(cleaned[..<index]).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return cleaned
    }
}
