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
    private let memorySummaryPolicy: @Sendable (Int) -> RuntimeLongInactivityMemorySummarizationPolicy
    private let routeRefresher: (any RuntimeRouteRefreshing)?
    private let runtimeChallengeSigner: (any RuntimeChallengeSigning)?
    private let onPairingAccepted: (@Sendable (TrustedDevice) -> Void)?
    private let dateFormatter = ISO8601DateFormatter()
    private let authLock = NSLock()
    private var authSessions: [UUID: AuthSessionState] = [:]
    private let chatStorageLock = NSLock()
    private var activeChatStorageContexts: [String: RuntimeChatStorageContext] = [:]
    private var activeChatRequestIDsByConnection: [UUID: Set<String>] = [:]
    private var recordedCancelledChatRequestIDs = Set<String>()

    public init(
        backend: any LlmBackend,
        requiresAuthentication: Bool = true,
        pairingCoordinator: PairingCoordinator = PairingCoordinator(),
        trustedDeviceStore: TrustedDeviceStore = TrustedDeviceStore(),
        chatEventStore: any RuntimeChatEventStore = RuntimeChatEventStoreDefaults.productionStore(),
        memoryStore: any RuntimeMemoryStore = JSONLRuntimeMemoryStore(),
        memorySummaryPolicy: @escaping @Sendable (Int) -> RuntimeLongInactivityMemorySummarizationPolicy = {
            RuntimeLongInactivityMemorySummarizationPolicy(maxCandidateCount: $0)
        },
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
        self.memorySummaryPolicy = memorySummaryPolicy
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

    public func connectionDidClose(_ connectionID: UUID) {
        authLock.withLock {
            authSessions[connectionID] = nil
        }
        cancelActiveChats(for: connectionID)
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
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleRuntimeHealth(envelope, sink: sink)
        case MessageType.modelsList:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleModelsList(envelope, sink: sink)
        case MessageType.modelsPull:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleModelsPull(envelope, sink: sink)
        case MessageType.routeRefresh:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleRouteRefresh(envelope, sink: sink)
        case MessageType.chatSend:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleChatSend(envelope, sink: sink)
        case MessageType.chatCancel:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatCancel(envelope, sink: sink)
        case MessageType.chatSessionsList:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionsList(envelope, sink: sink)
        case MessageType.chatMessagesList:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatMessagesList(envelope, sink: sink)
        case MessageType.chatTitleRequest:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            await handleChatTitleRequest(envelope, sink: sink)
        case MessageType.chatSessionRename:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionRename(envelope, sink: sink)
        case MessageType.chatSessionArchive:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionMutation(envelope, sink: sink, mutation: .archive)
        case MessageType.chatSessionRestore:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionMutation(envelope, sink: sink, mutation: .restore)
        case MessageType.chatSessionDelete:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleChatSessionMutation(envelope, sink: sink, mutation: .delete)
        case MessageType.memoryList:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleMemoryList(envelope, sink: sink)
        case MessageType.memoryUpsert:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleMemoryUpsert(envelope, sink: sink)
        case MessageType.memoryDelete:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleMemoryDelete(envelope, sink: sink)
        case MessageType.memorySummaryDraftsList:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleMemorySummaryDraftsList(envelope, sink: sink)
        case MessageType.memorySummaryDraftApprove:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleMemorySummaryDraftApprove(envelope, sink: sink)
        case MessageType.memorySummaryDraftDismiss:
            guard await allowRuntimeCommand(envelope, sink: sink) else { return }
            handleMemorySummaryDraftDismiss(envelope, sink: sink)
        case MessageType.authChallenge,
             MessageType.pairingResult,
             MessageType.modelsResult,
             MessageType.chatDelta,
             MessageType.chatDone,
             MessageType.chatTitleResult,
             MessageType.error:
            handleUnexpectedClientMessageDirection(envelope, sink: sink)
        default:
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                code: "unknown_message_type",
                message: "Unsupported AetherLink Runtime message type: \(envelope.type)",
                retryable: false
            ))
        }
    }

    private func handleUnexpectedClientMessageDirection(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        sink.send(errorEnvelope(
            requestID: envelope.requestID,
            code: "unexpected_message_direction",
            message: "Runtime-to-client message type cannot be sent to AetherLink Runtime: \(envelope.type)",
            retryable: false
        ))
    }

    private func allowRuntimeCommand(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async -> Bool {
        guard requiresAuthentication else { return true }
        guard let authenticatedDeviceID = authenticatedDeviceID(connectionID: sink.connectionID) else {
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                code: "authentication_required",
                message: "Pair and authenticate this device before sending runtime commands.",
                retryable: false
            ))
            return false
        }
        do {
            guard try await trustedDevice(deviceID: authenticatedDeviceID) != nil else {
                clearAuthentication(connectionID: sink.connectionID)
                sink.send(errorEnvelope(
                    requestID: envelope.requestID,
                    code: "pairing_required",
                    message: "This device is no longer trusted by AetherLink Runtime.",
                    retryable: false
                ))
                return false
            }
        } catch {
            clearAuthentication(connectionID: sink.connectionID)
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
            return false
        }
        return true
    }

    private func handlePairingRequest(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            try validateAllowedRequestPayload(envelope, allowedKeys: allowedPairingRequestPayloadKeys)
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

    private func handleChatTitleRequest(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        do {
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
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
                    title: title,
                    ownerDeviceID: ownerDeviceID
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
            try validateAllowedRequestPayload(envelope, allowedKeys: allowedHelloPayloadKeys)
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
            try validateAllowedRequestPayload(envelope, allowedKeys: allowedAuthResponsePayloadKeys)
            let deviceID = try requiredString("device_id", in: envelope.payload)
            let nonce = try requiredString("nonce", in: envelope.payload)
            let signature = try requiredString("signature", in: envelope.payload)

            guard challengeMatches(connectionID: sink.connectionID, deviceID: deviceID, nonce: nonce),
                  let device = try await trustedDevice(deviceID: deviceID),
                  Self.verifySignature(
                    publicKeyBase64: device.publicKeyBase64,
                    deviceID: deviceID,
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
        do {
            try validateEmptyRequestPayload(envelope)
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
            return
        }

        if let aggregate = backend as? AggregatingLlmBackend {
            let statuses = await aggregate.providerHealth()
            let providerPayloads = statuses.mapValues { status in
                healthPayload(for: status)
            }
            let anyAvailable = statuses.values.contains(.available)
            var payload: [String: JSONValue] = [
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
            payload["model_residency"] = modelResidencyPayload(for: aggregate.modelResidencySnapshot())
            sink.send(ProtocolEnvelope(
                type: MessageType.runtimeHealth,
                requestID: envelope.requestID,
                payload: payload
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
            try validateEmptyRequestPayload(envelope)
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
                        if let contextWindowTokens = model.contextWindowTokens, contextWindowTokens > 0 {
                            payload["context_window_tokens"] = .number(Double(contextWindowTokens))
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
            let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedModelsPullPayloadKeys)
            guard unsupportedPayloadKeys.isEmpty else {
                let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
                throw LocalRuntimeRouterError.invalidPayload("models.pull payload contains unsupported field(s): \(fields)")
            }
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
            try validateEmptyRequestPayload(envelope)
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
            return
        }

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
            guard let payload = route.routeRefreshPayload() else {
                sink.send(errorEnvelope(
                    requestID: envelope.requestID,
                    code: "route_refresh_unavailable",
                    message: "AetherLink Runtime could not refresh remote route material.",
                    retryable: true
                ))
                return
            }
            sink.send(ProtocolEnvelope(
                type: MessageType.routeRefresh,
                requestID: envelope.requestID,
                payload: payload
            ))
        } catch {
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                code: "route_refresh_unavailable",
                message: "AetherLink Runtime could not refresh remote route material.",
                retryable: true
            ))
        }
    }

    private func handleChatSend(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) async {
        var storageContext: RuntimeChatStorageContext?
        var activeStorageRequestID: String?
        defer {
            if let activeStorageRequestID {
                unregisterActiveChatStorageContext(requestID: activeStorageRequestID)
            }
        }
        do {
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
            let parsedClientRequest = try parsedChatRequest(from: envelope)
            let clientRequest = parsedClientRequest.request
            let locale = optionalString("locale", in: envelope.payload)
            try validateChatSessionCanReceiveSend(
                sessionID: clientRequest.sessionID,
                ownerDeviceID: ownerDeviceID
            )
            storageContext = RuntimeChatStorageContext(
                requestID: envelope.requestID,
                sessionID: clientRequest.sessionID,
                model: clientRequest.model,
                connectionID: sink.connectionID,
                ownerDeviceID: ownerDeviceID
            )
            let storedMessages = Self.chatStorageMessages(from: parsedClientRequest.storageMessages)
            let guardedRequest = Self.chatRequestWithRuntimeCapabilityGuard(clientRequest)
            let memoryEntries: [RuntimeMemoryEntry]
            do {
                memoryEntries = try memoryStore.list(ownerDeviceID: ownerDeviceID)
            } catch {
                throw LocalRuntimeRouterError.memoryStoreUnavailable(error.localizedDescription)
            }
            let request = Self.chatRequestWithRuntimeMemory(
                guardedRequest,
                memoryEntries: memoryEntries
            )
            try recordChatEvent(.init(
                kind: .request,
                requestID: envelope.requestID,
                sessionID: request.sessionID,
                model: request.model,
                messages: storedMessages,
                ownerDeviceID: ownerDeviceID
            ))
            registerActiveChatStorageContext(storageContext)
            activeStorageRequestID = envelope.requestID
            let model = try await resolvedInstalledChatModel(request.model)
            let backendRequest = Self.chatRequestWithRuntimeConversationCompaction(
                request,
                contextWindowTokens: model.contextWindowTokens
            )
            try validateAttachments(in: backendRequest, for: model)
            var inlineReasoningSplitter = RuntimeInlineReasoningSplitter()
            for try await event in backend.chat(request: backendRequest) {
                guard !isCancelledChatRequest(requestID: envelope.requestID) else { return }
                switch event {
                case .delta(let text):
                    try emitChatSegments(
                        inlineReasoningSplitter.split(text),
                        requestID: envelope.requestID,
                        sessionID: backendRequest.sessionID,
                        model: backendRequest.model,
                        ownerDeviceID: ownerDeviceID,
                        sink: sink
                    )
                case .reasoningDelta(let text):
                    try recordChatEvent(.init(
                        kind: .reasoningDelta,
                        requestID: envelope.requestID,
                        sessionID: backendRequest.sessionID,
                        model: backendRequest.model,
                        reasoningDelta: text,
                        ownerDeviceID: ownerDeviceID
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
                        ownerDeviceID: ownerDeviceID,
                        sink: sink
                    )
                    try recordChatEvent(.init(
                        kind: .done,
                        requestID: envelope.requestID,
                        sessionID: backendRequest.sessionID,
                        model: backendRequest.model,
                        finishReason: "stop",
                        usage: RuntimeChatStoredUsage(inputTokens: inputTokens, outputTokens: outputTokens),
                        ownerDeviceID: ownerDeviceID
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
                        ownerDeviceID: ownerDeviceID,
                        locale: locale
                    )
                }
            }
        } catch OllamaBackendError.generationCancelled {
            sendCancelledChatDoneIfNeeded(context: storageContext, sink: sink)
        } catch LMStudioBackendError.generationCancelled {
            sendCancelledChatDoneIfNeeded(context: storageContext, sink: sink)
        } catch let error as BackendError where error.code == "generation_cancelled" {
            sendCancelledChatDoneIfNeeded(context: storageContext, sink: sink)
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

    private func validateChatSessionCanReceiveSend(sessionID: String, ownerDeviceID: String?) throws {
        let sessions: [RuntimeChatStoredSession]
        do {
            sessions = try chatEventStore.listSessions(
                ownerDeviceID: ownerDeviceID,
                limit: Int.max,
                includeArchived: true
            )
        } catch {
            throw LocalRuntimeRouterError.chatStoreUnavailable(error.localizedDescription)
        }
        guard let session = sessions.first(where: { $0.sessionID == sessionID }) else {
            return
        }
        if session.status == "archived" {
            throw LocalRuntimeRouterError.chatSessionMustBeRestoredBeforeSend(sessionID)
        }
    }

    private func emitChatSegments(
        _ segments: [RuntimeInlineReasoningSegment],
        requestID: String,
        sessionID: String,
        model: String,
        ownerDeviceID: String?,
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
                    delta: text,
                    ownerDeviceID: ownerDeviceID
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
                    reasoningDelta: text,
                    ownerDeviceID: ownerDeviceID
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
        ownerDeviceID: String?,
        sessionID: String,
        requestID: String,
        mutation: RuntimeChatSessionMutation
    ) throws -> RuntimeChatSessionMutationResult {
        do {
            return try chatEventStore.mutateSession(
                ownerDeviceID: ownerDeviceID,
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

    @discardableResult
    private func recordCancelledChatEventIfPossible(context: RuntimeChatStorageContext?) -> Bool {
        guard let context else { return false }
        guard markCancelledChatRequestIfNeeded(requestID: context.requestID) else { return false }
        try? recordChatEvent(.init(
            kind: .cancelled,
            requestID: context.requestID,
            sessionID: context.sessionID,
            model: context.model,
            finishReason: "cancelled",
            ownerDeviceID: context.ownerDeviceID
        ))
        return true
    }

    private func sendCancelledChatDoneIfNeeded(
        context: RuntimeChatStorageContext?,
        sink: any RuntimeMessageSink
    ) {
        guard let context, recordCancelledChatEventIfPossible(context: context) else { return }
        sink.send(ProtocolEnvelope(
            type: MessageType.chatDone,
            requestID: context.requestID,
            payload: ["finish_reason": .string("cancelled")]
        ))
    }

    private func registerActiveChatStorageContext(_ context: RuntimeChatStorageContext?) {
        guard let context else { return }
        chatStorageLock.withLock {
            activeChatStorageContexts[context.requestID] = context
            activeChatRequestIDsByConnection[context.connectionID, default: []].insert(context.requestID)
            recordedCancelledChatRequestIDs.remove(context.requestID)
        }
    }

    private func unregisterActiveChatStorageContext(requestID: String) {
        chatStorageLock.withLock {
            if let connectionID = activeChatStorageContexts[requestID]?.connectionID {
                activeChatRequestIDsByConnection[connectionID]?.remove(requestID)
                if activeChatRequestIDsByConnection[connectionID]?.isEmpty == true {
                    activeChatRequestIDsByConnection[connectionID] = nil
                }
            } else {
                for connectionID in Array(activeChatRequestIDsByConnection.keys) {
                    activeChatRequestIDsByConnection[connectionID]?.remove(requestID)
                    if activeChatRequestIDsByConnection[connectionID]?.isEmpty == true {
                        activeChatRequestIDsByConnection[connectionID] = nil
                    }
                }
            }
            activeChatStorageContexts[requestID] = nil
            recordedCancelledChatRequestIDs.remove(requestID)
        }
    }

    private func activeChatStorageContext(for requestID: String) -> RuntimeChatStorageContext? {
        chatStorageLock.withLock {
            activeChatStorageContexts[requestID]
        }
    }

    private func markCancelledChatRequestIfNeeded(requestID: String) -> Bool {
        chatStorageLock.withLock {
            if recordedCancelledChatRequestIDs.contains(requestID) {
                return false
            }
            recordedCancelledChatRequestIDs.insert(requestID)
            return true
        }
    }

    private func isCancelledChatRequest(requestID: String) -> Bool {
        chatStorageLock.withLock {
            recordedCancelledChatRequestIDs.contains(requestID)
        }
    }

    private func cancelActiveChats(for connectionID: UUID) {
        let contexts = takeActiveChatStorageContexts(for: connectionID)
        for context in contexts {
            if case .cancelled = backend.cancel(generationID: context.requestID) {
                recordCancelledChatEventIfPossible(context: context)
            }
        }
    }

    private func takeActiveChatStorageContexts(for connectionID: UUID) -> [RuntimeChatStorageContext] {
        chatStorageLock.withLock {
            let requestIDs = activeChatRequestIDsByConnection[connectionID, default: []]
            activeChatRequestIDsByConnection[connectionID] = nil
            return requestIDs.compactMap { requestID in
                let context = activeChatStorageContexts[requestID]
                activeChatStorageContexts[requestID] = nil
                return context
            }
        }
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
            ),
            ownerDeviceID: context.ownerDeviceID
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
                        requestedModel: requestedModel,
                        contextWindowTokens: model.contextWindowTokens
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
                requestedModel: requestedModel,
                contextWindowTokens: model.contextWindowTokens
            )
        }
        throw LocalRuntimeRouterError.modelNotInstalled(requestedModel)
    }

    private static func resolvedChatModel(
        provider: ModelProvider,
        kind: ModelKind,
        capabilities: [String],
        requestedModel: String,
        contextWindowTokens: Int?
    ) throws -> ResolvedRuntimeModel {
        guard kind == ModelKind.chat else {
            throw LocalRuntimeRouterError.modelNotInstalled(requestedModel)
        }
        return ResolvedRuntimeModel(
            provider: provider,
            kind: kind,
            capabilities: capabilities,
            contextWindowTokens: contextWindowTokens
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
            let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedChatCancelPayloadKeys)
            guard unsupportedPayloadKeys.isEmpty else {
                let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
                throw LocalRuntimeRouterError.invalidPayload("chat.cancel payload contains unsupported field(s): \(fields)")
            }
            let targetRequestID = try requiredString("target_request_id", in: envelope.payload)
            switch backend.cancel(generationID: targetRequestID) {
            case .cancelled:
                let context = activeChatStorageContext(for: targetRequestID)
                let shouldSendChatDone = recordCancelledChatEventIfPossible(context: context)
                sink.send(ProtocolEnvelope(
                    type: MessageType.chatCancel,
                    requestID: envelope.requestID,
                    payload: [
                        "target_request_id": .string(targetRequestID),
                        "cancelled": .bool(true)
                    ]
                ))
                if shouldSendChatDone, let context {
                    sink.send(ProtocolEnvelope(
                        type: MessageType.chatDone,
                        requestID: context.requestID,
                        payload: ["finish_reason": .string("cancelled")]
                    ))
                }
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
        let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedChatSessionsListPayloadKeys)
        guard unsupportedPayloadKeys.isEmpty else {
            let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                error: LocalRuntimeRouterError.invalidPayload(
                    "chat.sessions.list payload contains unsupported field(s): \(fields)"
                )
            ))
            return
        }
        do {
            let limit = boundedWindowLimit(
                try optionalRequestInt("limit", in: envelope.payload),
                defaultLimit: 100,
                maxLimit: 200
            )
            let includeArchived = try optionalRequestBool("include_archived", in: envelope.payload) ?? false
            let query = try optionalRequestString("query", in: envelope.payload)
            let embeddingModelID = try normalizedChatSessionSearchEmbeddingModelID(
                query: query,
                payload: envelope.payload
            )
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
            let sessions = try chatEventStore.listSessions(
                ownerDeviceID: ownerDeviceID,
                limit: limit,
                includeArchived: includeArchived,
                query: query,
                embeddingModelID: embeddingModelID
            )
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
                        if let search = session.search {
                            payload["search"] = .object([
                                "rank": .number(Double(search.rank)),
                                "snippet": .string(search.snippet),
                                "matched_fields": .array(search.matchedFields.map { .string($0) })
                            ])
                        }
                        return .object(payload)
                    })
                ]
            ))
        } catch let error as LocalRuntimeRouterError {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: LocalRuntimeRouterError.chatStoreUnavailable(error.localizedDescription)))
        }
    }

    private func normalizedChatSessionSearchEmbeddingModelID(
        query: String?,
        payload: [String: JSONValue]
    ) throws -> String? {
        let rawEmbeddingModelID = try optionalRequestString("embedding_model_id", in: payload)
        guard RuntimeChatSessionSearchQuery(query) != nil else { return nil }
        let normalized = rawEmbeddingModelID?.trimmingCharacters(in: .whitespacesAndNewlines)
        return normalized?.isEmpty == false ? normalized : nil
    }

    private func handleChatMessagesList(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedChatMessagesListPayloadKeys)
        guard unsupportedPayloadKeys.isEmpty else {
            let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                error: LocalRuntimeRouterError.invalidPayload(
                    "chat.messages.list payload contains unsupported field(s): \(fields)"
                )
            ))
            return
        }
        do {
            let sessionID = try requiredString("session_id", in: envelope.payload)
            let limit = boundedWindowLimit(
                try optionalRequestInt("limit", in: envelope.payload),
                defaultLimit: 200,
                maxLimit: 500
            )
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
            let scopedMessages = try chatEventStore.listMessages(
                ownerDeviceID: ownerDeviceID,
                sessionID: sessionID,
                limit: limit
            )
            sink.send(ProtocolEnvelope(
                type: MessageType.chatMessagesList,
                requestID: envelope.requestID,
                payload: [
                    "session_id": .string(sessionID),
                    "messages": .array(scopedMessages.map { message in
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
            let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedChatSessionLifecyclePayloadKeys)
            guard unsupportedPayloadKeys.isEmpty else {
                let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
                throw LocalRuntimeRouterError.invalidPayload(
                    "chat.session lifecycle payload contains unsupported field(s): \(fields)"
                )
            }
            let sessionID = try requiredString("session_id", in: envelope.payload)
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
            let result = try mutateChatSession(
                ownerDeviceID: ownerDeviceID,
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
            let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedChatSessionRenamePayloadKeys)
            guard unsupportedPayloadKeys.isEmpty else {
                let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
                throw LocalRuntimeRouterError.invalidPayload(
                    "chat.session.rename payload contains unsupported field(s): \(fields)"
                )
            }
            let sessionID = try requiredString("session_id", in: envelope.payload)
            let title = try requiredString("title", in: envelope.payload)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard !title.isEmpty else {
                throw LocalRuntimeRouterError.invalidPayload("Payload field title must be a non-empty string")
            }
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
            guard let session = try chatEventStore
                .listSessions(ownerDeviceID: ownerDeviceID, limit: Int.max, includeArchived: true)
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
                title: title,
                ownerDeviceID: ownerDeviceID
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
        let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedMemoryListPayloadKeys)
        guard unsupportedPayloadKeys.isEmpty else {
            let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                error: LocalRuntimeRouterError.invalidPayload(
                    "memory.list payload contains unsupported field(s): \(fields)"
                )
            ))
            return
        }
        do {
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
            let entries = try memoryStore.list(
                ownerDeviceID: ownerDeviceID,
                query: try optionalRequestString("query", in: envelope.payload)
            )
            sink.send(ProtocolEnvelope(
                type: MessageType.memoryList,
                requestID: envelope.requestID,
                payload: [
                    "entries": .array(entries.map { .object(memoryEntryPayload($0)) })
                ]
            ))
        } catch let error as LocalRuntimeRouterError {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: LocalRuntimeRouterError.memoryStoreUnavailable(error.localizedDescription)))
        }
    }

    private func handleMemoryUpsert(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedMemoryUpsertPayloadKeys)
            guard unsupportedPayloadKeys.isEmpty else {
                let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
                throw LocalRuntimeRouterError.invalidPayload(
                    "memory.upsert payload contains unsupported field(s): \(fields)"
                )
            }
            let entry = try memoryStore.upsert(
                ownerDeviceID: commandOwnerDeviceID(connectionID: sink.connectionID),
                id: try optionalRequestString("id", in: envelope.payload),
                content: try requiredString("content", in: envelope.payload),
                enabled: try optionalRequestBool("enabled", in: envelope.payload),
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
            let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedMemoryDeletePayloadKeys)
            guard unsupportedPayloadKeys.isEmpty else {
                let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
                throw LocalRuntimeRouterError.invalidPayload(
                    "memory.delete payload contains unsupported field(s): \(fields)"
                )
            }
            let result = try memoryStore.delete(
                ownerDeviceID: commandOwnerDeviceID(connectionID: sink.connectionID),
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
        var payload: [String: JSONValue] = [
            "id": .string(entry.id),
            "content": .string(entry.content),
            "enabled": .bool(entry.enabled),
            "created_at": .string(dateFormatter.string(from: entry.createdAt)),
            "updated_at": .string(dateFormatter.string(from: entry.updatedAt))
        ]
        if let source = entry.source {
            payload["source"] = .object(memoryEntrySourcePayload(source))
        }
        if let search = entry.search {
            payload["search"] = .object([
                "rank": .number(Double(search.rank)),
                "snippet": .string(search.snippet),
                "matched_fields": .array(search.matchedFields.map { .string($0) })
            ])
        }
        return payload
    }

    private func handleMemorySummaryDraftsList(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedMemorySummaryDraftsListPayloadKeys)
        guard unsupportedPayloadKeys.isEmpty else {
            let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
            sink.send(errorEnvelope(
                requestID: envelope.requestID,
                error: LocalRuntimeRouterError.invalidPayload(
                    "memory.summary.drafts.list payload contains unsupported field(s): \(fields)"
                )
            ))
            return
        }
        do {
            let limit = boundedWindowLimit(
                try optionalRequestInt("limit", in: envelope.payload),
                defaultLimit: 25,
                maxLimit: 50
            )
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
            let drafts = try availableMemorySummaryDrafts(
                ownerDeviceID: ownerDeviceID,
                limit: limit
            )
            sink.send(ProtocolEnvelope(
                type: MessageType.memorySummaryDraftsList,
                requestID: envelope.requestID,
                payload: [
                    "drafts": .array(drafts.map { .object(memorySummaryDraftPayload($0)) })
                ]
            ))
        } catch let error as LocalRuntimeRouterError {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: LocalRuntimeRouterError.chatStoreUnavailable(error.localizedDescription)))
        }
    }

    private func availableMemorySummaryDrafts(
        ownerDeviceID: String?,
        limit: Int
    ) throws -> [RuntimeLongInactivityMemorySummarizationDraft] {
        let policy = memorySummaryPolicy(limit)
        let drafts = try chatEventStore.listLongInactivityMemorySummarizationDrafts(
            ownerDeviceID: ownerDeviceID,
            policy: policy
        )
        let approvedEntryIDs: Set<String>
        let dismissedDraftIDs: Set<String>
        do {
            approvedEntryIDs = Set(try memoryStore.list(ownerDeviceID: ownerDeviceID).map(\.id))
            dismissedDraftIDs = try memoryStore.dismissedMemorySummaryDraftIDs(ownerDeviceID: ownerDeviceID)
        } catch {
            throw LocalRuntimeRouterError.memoryStoreUnavailable(error.localizedDescription)
        }
        return drafts.filter { draft in
            !approvedEntryIDs.contains(memorySummaryDraftEntryID(draft.id)) &&
                !dismissedDraftIDs.contains(draft.id)
        }
    }

    private func handleMemorySummaryDraftApprove(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedMemorySummaryDraftApprovePayloadKeys)
            guard unsupportedPayloadKeys.isEmpty else {
                let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
                throw LocalRuntimeRouterError.invalidPayload(
                    "memory.summary.draft.approve payload contains unsupported field(s): \(fields)"
                )
            }
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
            let draftID = try requiredString("draft_id", in: envelope.payload)
            let rawExpectedSessionID = optionalString("expected_session_id", in: envelope.payload)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            let expectedSessionID = rawExpectedSessionID.flatMap { $0.isEmpty ? nil : $0 }
            let expectedSourceMessageCount = optionalInt("expected_source_message_count", in: envelope.payload)
            let policy = memorySummaryPolicy(50)
            let drafts = try chatEventStore.listLongInactivityMemorySummarizationDrafts(
                ownerDeviceID: ownerDeviceID,
                policy: policy
            )
            guard let draft = drafts.first(where: { $0.id == draftID }) else {
                throw LocalRuntimeRouterError.memorySummaryDraftUnavailable(draftID)
            }
            if let expectedSessionID, expectedSessionID != draft.candidate.sessionID {
                throw LocalRuntimeRouterError.memorySummaryDraftStale(draftID)
            }
            if let expectedSourceMessageCount, expectedSourceMessageCount != draft.sourceMessageCount {
                throw LocalRuntimeRouterError.memorySummaryDraftStale(draftID)
            }
            let rawContent = optionalString("content", in: envelope.payload)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            let content = rawContent.flatMap { $0.isEmpty ? nil : $0 } ?? draft.summaryPreview
            let entry = try memoryStore.upsert(
                ownerDeviceID: ownerDeviceID,
                id: memorySummaryDraftEntryID(draftID),
                content: content,
                enabled: optionalBool("enabled", in: envelope.payload) ?? true,
                source: memorySummaryDraftEntrySource(draft),
                timestamp: Date()
            )
            sink.send(ProtocolEnvelope(
                type: MessageType.memorySummaryDraftApprove,
                requestID: envelope.requestID,
                payload: [
                    "draft_id": .string(draft.id),
                    "status": .string("approved"),
                    "entry": .object(memoryEntryPayload(entry))
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func handleMemorySummaryDraftDismiss(_ envelope: ProtocolEnvelope, sink: any RuntimeMessageSink) {
        do {
            let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedMemorySummaryDraftDismissPayloadKeys)
            guard unsupportedPayloadKeys.isEmpty else {
                let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
                throw LocalRuntimeRouterError.invalidPayload(
                    "memory.summary.draft.dismiss payload contains unsupported field(s): \(fields)"
                )
            }
            let ownerDeviceID = commandOwnerDeviceID(connectionID: sink.connectionID)
            let draftID = try requiredString("draft_id", in: envelope.payload)
            let rawExpectedSessionID = optionalString("expected_session_id", in: envelope.payload)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            let expectedSessionID = rawExpectedSessionID.flatMap { $0.isEmpty ? nil : $0 }
            let expectedSourceMessageCount = optionalInt("expected_source_message_count", in: envelope.payload)
            let policy = memorySummaryPolicy(50)
            let drafts = try chatEventStore.listLongInactivityMemorySummarizationDrafts(
                ownerDeviceID: ownerDeviceID,
                policy: policy
            )
            guard let draft = drafts.first(where: { $0.id == draftID }) else {
                throw LocalRuntimeRouterError.memorySummaryDraftUnavailable(draftID)
            }
            if let expectedSessionID, expectedSessionID != draft.candidate.sessionID {
                throw LocalRuntimeRouterError.memorySummaryDraftStale(draftID)
            }
            if let expectedSourceMessageCount, expectedSourceMessageCount != draft.sourceMessageCount {
                throw LocalRuntimeRouterError.memorySummaryDraftStale(draftID)
            }
            let result = try memoryStore.dismissMemorySummaryDraft(
                ownerDeviceID: ownerDeviceID,
                draftID: draft.id,
                timestamp: Date()
            )
            sink.send(ProtocolEnvelope(
                type: MessageType.memorySummaryDraftDismiss,
                requestID: envelope.requestID,
                payload: [
                    "draft_id": .string(result.draftID),
                    "status": .string("dismissed"),
                    "dismissed_at": .string(dateFormatter.string(from: result.dismissedAt))
                ]
            ))
        } catch {
            sink.send(errorEnvelope(requestID: envelope.requestID, error: error))
        }
    }

    private func memorySummaryDraftEntryID(_ draftID: String) -> String {
        "memory-summary:\(draftID)"
    }

    private func memorySummaryDraftEntrySource(
        _ draft: RuntimeLongInactivityMemorySummarizationDraft
    ) -> RuntimeMemoryEntrySource {
        RuntimeMemoryEntrySource(
            kind: "long_inactivity_summary_draft",
            draftID: draft.id,
            summaryMethod: "deterministic_preview",
            session: RuntimeMemoryEntrySourceSession(
                sessionID: draft.candidate.sessionID,
                title: draft.candidate.title,
                model: draft.candidate.model,
                lastActivityAt: draft.candidate.lastActivityAt,
                messageCount: draft.candidate.messageCount,
                inactiveSeconds: max(0, Int(draft.candidate.inactiveInterval))
            ),
            sourceMessageCount: draft.sourceMessageCount,
            sourceRange: draft.sourceRangeDescription,
            sourcePointers: draft.sourcePointers.map { pointer in
                RuntimeMemoryEntrySourcePointer(
                    sessionID: pointer.sessionID,
                    messageIndex: pointer.messageIndex,
                    role: pointer.role,
                    createdAt: pointer.createdAt,
                    excerpt: pointer.excerpt
                )
            }
        )
    }

    private func memoryEntrySourcePayload(_ source: RuntimeMemoryEntrySource) -> [String: JSONValue] {
        [
            "kind": .string(source.kind),
            "draft_id": .string(source.draftID),
            "summary_method": .string(source.summaryMethod),
            "session": .object(memoryEntrySourceSessionPayload(source.session)),
            "source_message_count": .number(Double(source.sourceMessageCount)),
            "source_range": .string(source.sourceRange),
            "source_pointers": .array(source.sourcePointers.map { pointer in
                .object(memoryEntrySourcePointerPayload(pointer))
            })
        ]
    }

    private func memoryEntrySourceSessionPayload(
        _ session: RuntimeMemoryEntrySourceSession
    ) -> [String: JSONValue] {
        [
            "session_id": .string(session.sessionID),
            "title": .string(session.title),
            "model": .string(session.model),
            "last_activity_at": .string(dateFormatter.string(from: session.lastActivityAt)),
            "message_count": .number(Double(session.messageCount)),
            "inactive_seconds": .number(Double(session.inactiveSeconds))
        ]
    }

    private func memoryEntrySourcePointerPayload(
        _ pointer: RuntimeMemoryEntrySourcePointer
    ) -> [String: JSONValue] {
        var payload: [String: JSONValue] = [
            "session_id": .string(pointer.sessionID),
            "message_index": .number(Double(pointer.messageIndex)),
            "role": .string(pointer.role),
            "excerpt": .string(pointer.excerpt)
        ]
        if let createdAt = pointer.createdAt {
            payload["created_at"] = .string(dateFormatter.string(from: createdAt))
        }
        return payload
    }

    private func memorySummaryDraftPayload(
        _ draft: RuntimeLongInactivityMemorySummarizationDraft
    ) -> [String: JSONValue] {
        [
            "id": .string(draft.id),
            "session": .object(memorySummaryDraftSessionPayload(draft.candidate)),
            "source_message_count": .number(Double(draft.sourceMessageCount)),
            "source_range": .string(draft.sourceRangeDescription),
            "source_pointers": .array(draft.sourcePointers.map { pointer in
                .object(memorySummaryDraftSourcePointerPayload(pointer))
            }),
            "summary_preview": .string(draft.summaryPreview)
        ]
    }

    private func memorySummaryDraftSessionPayload(
        _ candidate: RuntimeLongInactivityMemorySummarizationCandidate
    ) -> [String: JSONValue] {
        [
            "session_id": .string(candidate.sessionID),
            "title": .string(candidate.title),
            "model": .string(candidate.model),
            "last_activity_at": .string(dateFormatter.string(from: candidate.lastActivityAt)),
            "message_count": .number(Double(candidate.messageCount)),
            "inactive_seconds": .number(Double(Int(candidate.inactiveInterval)))
        ]
    }

    private func memorySummaryDraftSourcePointerPayload(
        _ pointer: RuntimeLongInactivityMemorySummarizationSourcePointer
    ) -> [String: JSONValue] {
        var payload: [String: JSONValue] = [
            "session_id": .string(pointer.sessionID),
            "message_index": .number(Double(pointer.messageIndex)),
            "role": .string(pointer.role),
            "excerpt": .string(pointer.excerpt)
        ]
        if let createdAt = pointer.createdAt {
            payload["created_at"] = .string(dateFormatter.string(from: createdAt))
        }
        return payload
    }

    private func chatRequest(from envelope: ProtocolEnvelope) throws -> ChatRequest {
        try parsedChatRequest(from: envelope).request
    }

    private func parsedChatRequest(from envelope: ProtocolEnvelope) throws -> RuntimeParsedChatRequest {
        let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedChatRequestPayloadKeys)
        guard unsupportedPayloadKeys.isEmpty else {
            let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
            throw LocalRuntimeRouterError.invalidPayload("Chat request payload contains unsupported field(s): \(fields)")
        }
        let sessionID = try requiredString("session_id", in: envelope.payload)
        let model = try requiredString("model", in: envelope.payload)
        let messagesValue = try requiredValue("messages", in: envelope.payload)
        guard case .array(let messageValues) = messagesValue else {
            throw LocalRuntimeRouterError.invalidPayload("messages must be an array")
        }

        let parsedMessages = try messageValues.map { value -> RuntimeParsedChatMessage in
            guard case .object(let object) = value else {
                throw LocalRuntimeRouterError.invalidPayload("Each message must be an object")
            }
            let unsupportedKeys = Set(object.keys).subtracting(allowedChatMessageKeys)
            guard unsupportedKeys.isEmpty else {
                let fields = unsupportedKeys.sorted().joined(separator: ", ")
                throw LocalRuntimeRouterError.invalidPayload("Message contains unsupported field(s): \(fields)")
            }
            let role = try requiredString("role", in: object)
            let baseContent = try requiredString("content", in: object)
            let parsedAttachments = try chatAttachments(from: object)
            let processed = try processChatAttachments(parsedAttachments)
            return RuntimeParsedChatMessage(
                backendMessage: ChatMessage(
                    role: role,
                    content: content(baseContent, appending: processed.promptText),
                    attachments: processed.preservedAttachments
                ),
                storageMessage: ChatMessage(
                    role: role,
                    content: baseContent,
                    attachments: processed.preservedAttachments
                ),
            )
        }

        return RuntimeParsedChatRequest(
            request: ChatRequest(
                generationID: envelope.requestID,
                sessionID: sessionID,
                model: model,
                messages: parsedMessages.map(\.backendMessage)
            ),
            storageMessages: parsedMessages.map(\.storageMessage)
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

    private func modelResidencyPayload(for snapshot: RuntimeModelResidencySnapshot) -> JSONValue {
        var payload: [String: JSONValue] = [
            "supported": .bool(true),
            "in_flight_generations": .number(Double(snapshot.inFlightGenerations)),
            "idle_unload_delay_seconds": .number(Double(snapshot.idleUnloadDelaySeconds))
        ]
        if let activeProvider = snapshot.activeProvider {
            payload["active_provider"] = .string(activeProvider.rawValue)
        }
        if let activeModelID = snapshot.activeModelID, !activeModelID.isEmpty {
            payload["active_model_id"] = .string(activeModelID)
        }
        if let failure = snapshot.lastUnloadFailure {
            payload["last_unload_failure"] = .object([
                "provider": .string(failure.provider.rawValue),
                "model_id": .string(failure.modelID),
                "reason": .string(failure.reason.rawValue)
            ])
        }
        return .object(payload)
    }

    private func trustedDevice(deviceID: String) async throws -> TrustedDevice? {
        try await trustedDeviceStore.load().first { $0.id == deviceID }
    }

    private func authenticatedDeviceID(connectionID: UUID) -> String? {
        authLock.withLock {
            guard case .authenticated(let deviceID) = authSessions[connectionID] else {
                return nil
            }
            return deviceID
        }
    }

    private func commandOwnerDeviceID(connectionID: UUID) -> String? {
        requiresAuthentication ? authenticatedDeviceID(connectionID: connectionID) : nil
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

    private func clearAuthentication(connectionID: UUID) {
        authLock.withLock {
            authSessions[connectionID] = nil
        }
    }

    private func scheduleChatTitleGenerationIfNeeded(
        sessionID: String,
        model: String,
        sourceRequestID: String,
        ownerDeviceID: String?,
        locale: String?
    ) {
        Task {
            await generateAndStoreChatTitleIfNeeded(
                sessionID: sessionID,
                model: model,
                sourceRequestID: sourceRequestID,
                ownerDeviceID: ownerDeviceID,
                locale: locale
            )
        }
    }

    private func generateAndStoreChatTitleIfNeeded(
        sessionID: String,
        model: String,
        sourceRequestID: String,
        ownerDeviceID: String?,
        locale: String?
    ) async {
        do {
            let sessions = try chatEventStore.listSessions(
                ownerDeviceID: ownerDeviceID,
                limit: 200,
                includeArchived: true
            )
            guard let session = sessions.first(where: { $0.sessionID == sessionID }),
                  session.status == "active",
                  session.title.isPlaceholderChatTitle else {
                return
            }

            let storedMessages = try chatEventStore.listMessages(
                ownerDeviceID: ownerDeviceID,
                sessionID: sessionID,
                limit: 8
            )
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
                title: title,
                ownerDeviceID: ownerDeviceID
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
        messages
            .filter { message in
                !message.isAetherLinkCapabilityGuard && !message.isRuntimeUserMemoryContext
            }
            .map { message in
                ChatMessage(
                    role: message.role,
                    content: message.content,
                    attachments: message.attachments.map(\.withoutInlineDataForStorage)
                )
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

    private static func chatRequestWithRuntimeConversationCompaction(
        _ request: ChatRequest,
        contextWindowTokens: Int? = nil
    ) -> ChatRequest {
        let messages = request.messages.filter { !$0.isRuntimeConversationCompactionContext }
        let estimatedCharacters = estimatedRuntimeContextCharacters(in: messages)
        let maxContextCharacters = runtimeConversationCompactionMaxContextCharacters(
            contextWindowTokens: contextWindowTokens
        )
        guard estimatedCharacters > maxContextCharacters else {
            return ChatRequest(
                generationID: request.generationID,
                sessionID: request.sessionID,
                model: request.model,
                messages: messages
            )
        }

        var conversationTurns: [(messageIndex: Int, turnNumber: Int, message: ChatMessage)] = []
        for (index, message) in messages.enumerated() where message.isConversationTurn {
            conversationTurns.append((messageIndex: index, turnNumber: conversationTurns.count + 1, message: message))
        }
        guard conversationTurns.count > runtimeConversationCompactionRecentTurnCount else {
            return ChatRequest(
                generationID: request.generationID,
                sessionID: request.sessionID,
                model: request.model,
                messages: messages
            )
        }

        let compactedTurns = Array(conversationTurns.dropLast(runtimeConversationCompactionRecentTurnCount))
        guard let summaryMessage = runtimeConversationCompactionMessage(
            from: compactedTurns.map { $0.message },
            sourceSpan: (
                startTurn: compactedTurns.first?.turnNumber ?? 1,
                endTurn: compactedTurns.last?.turnNumber ?? compactedTurns.count,
                totalTurns: conversationTurns.count
            )
        ) else {
            return ChatRequest(
                generationID: request.generationID,
                sessionID: request.sessionID,
                model: request.model,
                messages: messages
            )
        }

        let compactedIndices = Set(compactedTurns.map(\.messageIndex))
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

    private static func runtimeConversationCompactionMessage(
        from messages: [ChatMessage],
        sourceSpan: (startTurn: Int, endTurn: Int, totalTurns: Int)
    ) -> ChatMessage? {
        var remainingCharacters = runtimeConversationCompactionMaxSummaryCharacters
        var lines: [String] = [
            runtimeConversationCompactionPrefix,
            "Backend-only summary of older turns from this active session. The user-visible transcript is preserved separately; archived or deleted chats are not included.",
            "\(runtimeConversationCompactionSourceSpanPrefix) client-visible conversation turns \(sourceSpan.startTurn)-\(sourceSpan.endTurn) of \(sourceSpan.totalTurns)."
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

        guard lines.count > 3 else { return nil }
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
        AetherLink currently provides runtime-mediated local model chat, model listing, file/image attachment handling when supported, and chat titles.
        The current build does not provide live web search, browsing, MCP tools, skills, scheduled automations, Python execution, or other external tools unless explicit tool output is included in this conversation.
        Do not claim that you can search the web, browse, run tools, access files, or use unavailable integrations. If asked for an unavailable capability, say it is not available in this build and offer the closest supported alternative.
        """
    )

    private static let runtimeUserMemoryPrefix = "Runtime user memory:"
    private static let runtimeUserMemoryMaxEntries = 8
    private static let runtimeUserMemoryMaxCharacters = 1_500
    private static let runtimeConversationCompactionPrefix = "Runtime conversation summary:"
    private static let runtimeConversationCompactionSourceSpanPrefix = "Source span:"
    private static let runtimeConversationCompactionDefaultMaxContextCharacters = 24_000
    private static let runtimeConversationCompactionCharactersPerTokenBudget = 3
    private static let runtimeConversationCompactionMinModelContextCharacters = 4_000
    private static let runtimeConversationCompactionRecentTurnCount = 12
    private static let runtimeConversationCompactionMaxSummaryCharacters = 4_000
    private static let runtimeConversationCompactionMaxSummaryLines = 24
    private static let runtimeConversationCompactionMaxLineCharacters = 320

    private static func runtimeConversationCompactionMaxContextCharacters(contextWindowTokens: Int?) -> Int {
        guard let contextWindowTokens, contextWindowTokens > 0 else {
            return runtimeConversationCompactionDefaultMaxContextCharacters
        }
        let boundedTokens = min(contextWindowTokens, Int.max / runtimeConversationCompactionCharactersPerTokenBudget)
        return max(
            runtimeConversationCompactionMinModelContextCharacters,
            boundedTokens * runtimeConversationCompactionCharactersPerTokenBudget
        )
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
        deviceID: String,
        nonce: String,
        signatureBase64: String
    ) -> Bool {
        guard let publicKeyData = Data(base64Encoded: publicKeyBase64),
              let signatureData = Data(base64Encoded: signatureBase64),
              let messageData = clientAuthenticationResponseMessage(deviceID: deviceID, nonce: nonce).data(using: .utf8),
              let publicKey = try? P256.Signing.PublicKey(derRepresentation: publicKeyData),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: signatureData)
        else {
            return false
        }
        return publicKey.isValidSignature(signature, for: SHA256.hash(data: messageData))
    }

    static func clientAuthenticationResponseMessage(deviceID: String, nonce: String) -> String {
        "\(clientAuthenticationResponseContext)\n\(deviceID)\n\(nonce)"
    }

    private static let clientAuthenticationResponseContext = "AetherLink client auth response v1"
}

private enum AuthSessionState: Equatable {
    case challenged(deviceID: String, nonce: String)
    case authenticated(deviceID: String)
}

private struct ChatTitleRuntimeRequest {
    var request: ChatRequest
}

private struct RuntimeChatStorageContext {
    var requestID: String
    var sessionID: String
    var model: String
    var connectionID: UUID
    var ownerDeviceID: String?
}

private struct RuntimeParsedChatRequest {
    var request: ChatRequest
    var storageMessages: [ChatMessage]
}

private struct RuntimeParsedChatMessage {
    var backendMessage: ChatMessage
    var storageMessage: ChatMessage
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

private let allowedRouteRefreshRelayScopes: Set<String> = [
    "remote",
    "private_overlay",
    "usb_reverse"
]

private extension RuntimeRouteRefreshResult {
    func routeRefreshPayload(nowEpochMillis: Int64 = currentRouteRefreshEpochMillis()) -> [String: JSONValue]? {
        guard runtimeDeviceID.isCanonicalRouteRefreshValue,
              runtimeKeyFingerprint.isCanonicalRouteRefreshValue
        else {
            return nil
        }

        var payload: [String: JSONValue] = [
            "runtime_device_id": .string(runtimeDeviceID),
            "runtime_key_fingerprint": .string(runtimeKeyFingerprint)
        ]

        let hasRelayMaterial = hasAnyRelayRouteMaterial
        let hasP2PMaterial = hasAnyP2PRouteMaterial
        guard hasRelayMaterial || hasP2PMaterial else {
            return nil
        }

        if hasRelayMaterial {
            guard let relayHost,
                  let relayPort,
                  let relayID,
                  let relaySecret,
                  let relayExpiresAtEpochMillis,
                  let relayNonce,
                  relayHost.isCanonicalRouteRefreshValue,
                  relayID.isCanonicalRouteRefreshValue,
                  relaySecret.isCanonicalRouteRefreshValue,
                  relayNonce.isCanonicalRouteRefreshValue,
                  (1...65_535).contains(relayPort),
                  relayExpiresAtEpochMillis > nowEpochMillis,
                  let validatedRelayScope,
                  relayHost.isEligibleRouteRefreshRelayHost(relayScope: validatedRelayScope)
            else {
                return nil
            }
            payload["relay_host"] = .string(relayHost)
            payload["relay_port"] = .number(Double(relayPort))
            payload["relay_id"] = .string(relayID)
            payload["relay_secret"] = .string(relaySecret)
            payload["relay_expires_at"] = .number(Double(relayExpiresAtEpochMillis))
            payload["relay_nonce"] = .string(relayNonce)
            if let validatedRelayScope {
                payload["relay_scope"] = .string(validatedRelayScope)
            }
        }

        if hasP2PMaterial {
            guard let p2pRouteClass,
                  let p2pRecordID,
                  let p2pEncryptedBody,
                  let p2pExpiresAtEpochMillis,
                  let p2pAntiReplayNonce,
                  let p2pProtocolVersion,
                  p2pRouteClass == "p2p_rendezvous",
                  p2pRecordID.isCanonicalRouteRefreshValue,
                  p2pEncryptedBody.isCanonicalRouteRefreshP2PEncryptedBody,
                  p2pAntiReplayNonce.isCanonicalRouteRefreshValue,
                  p2pExpiresAtEpochMillis > nowEpochMillis,
                  p2pProtocolVersion == 1
            else {
                return nil
            }
            payload["p2p_class"] = .string(p2pRouteClass)
            payload["p2p_record_id"] = .string(p2pRecordID)
            payload["p2p_encrypted_body"] = .string(p2pEncryptedBody)
            payload["p2p_expires_at"] = .number(Double(p2pExpiresAtEpochMillis))
            payload["p2p_anti_replay_nonce"] = .string(p2pAntiReplayNonce)
            payload["p2p_protocol_version"] = .number(Double(p2pProtocolVersion))
        }
        return payload
    }

    var hasAnyRelayRouteMaterial: Bool {
        relayHost != nil ||
            relayPort != nil ||
            relayID != nil ||
            relaySecret != nil ||
            relayExpiresAtEpochMillis != nil ||
            relayNonce != nil ||
            relayScope != nil
    }

    var hasAnyP2PRouteMaterial: Bool {
        p2pRouteClass != nil ||
            p2pRecordID != nil ||
            p2pEncryptedBody != nil ||
            p2pExpiresAtEpochMillis != nil ||
            p2pAntiReplayNonce != nil ||
            p2pProtocolVersion != nil
    }

    var validatedRelayScope: String?? {
        guard let relayScope else {
            return .some(nil)
        }
        return allowedRouteRefreshRelayScopes.contains(relayScope) ? .some(relayScope) : nil
    }
}

private let routeRefreshOpaqueValueMaxCharacters = 512
private let routeRefreshP2PEncryptedBodyMaxCharacters = 2_048

private extension String {
    var isCanonicalRouteRefreshValue: Bool {
        isCanonicalRouteRefreshValue(maxCharacters: routeRefreshOpaqueValueMaxCharacters)
    }

    var isCanonicalRouteRefreshP2PEncryptedBody: Bool {
        isCanonicalRouteRefreshValue(maxCharacters: routeRefreshP2PEncryptedBodyMaxCharacters)
    }

    func isCanonicalRouteRefreshValue(maxCharacters: Int) -> Bool {
        !isEmpty &&
            count <= maxCharacters &&
            rangeOfCharacter(from: .whitespacesAndNewlines) == nil
    }

    func isEligibleRouteRefreshRelayHost(relayScope: String?) -> Bool {
        switch CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: self) {
        case nil:
            return true
        case .loopback:
            return relayScope == "usb_reverse"
        case .privateNetwork:
            return relayScope == "private_overlay"
        case .invalidFormat, .localName:
            return false
        }
    }
}

private func currentRouteRefreshEpochMillis() -> Int64 {
    Int64((Date().timeIntervalSince1970 * 1000).rounded())
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
    case chatSessionMustBeRestoredBeforeSend(String)
    case chatStoreUnavailable(String)
    case memoryStoreUnavailable(String)
    case memorySummaryDraftUnavailable(String)
    case memorySummaryDraftStale(String)

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
        case .chatSessionMustBeRestoredBeforeSend:
            return "chat_session_must_be_restored_before_send"
        case .chatStoreUnavailable:
            return "chat_store_unavailable"
        case .memoryStoreUnavailable:
            return "memory_store_unavailable"
        case .memorySummaryDraftUnavailable:
            return "memory_summary_draft_unavailable"
        case .memorySummaryDraftStale:
            return "memory_summary_draft_stale"
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
        case .chatSessionMustBeRestoredBeforeSend(let sessionID):
            return "Restore this archived chat before sending another message: \(sessionID)"
        case .chatStoreUnavailable(let message):
            return "The runtime could not access chat history on this host: \(message)"
        case .memoryStoreUnavailable(let message):
            return "The runtime could not access memory on this host: \(message)"
        case .memorySummaryDraftUnavailable:
            return "Memory summary draft is no longer available."
        case .memorySummaryDraftStale:
            return "Memory summary draft changed before approval. Refresh suggested memories and review it again."
        }
    }
}

private struct ProcessedChatAttachments {
    var promptText: String
    var preservedAttachments: [ChatAttachment]
}

private func validateEmptyRequestPayload(_ envelope: ProtocolEnvelope) throws {
    try validateAllowedRequestPayload(envelope, allowedKeys: [])
}

private func validateAllowedRequestPayload(_ envelope: ProtocolEnvelope, allowedKeys: Set<String>) throws {
    let unsupportedPayloadKeys = Set(envelope.payload.keys).subtracting(allowedKeys)
    guard unsupportedPayloadKeys.isEmpty else {
        let fields = unsupportedPayloadKeys.sorted().joined(separator: ", ")
        throw LocalRuntimeRouterError.invalidPayload("\(envelope.type) payload contains unsupported field(s): \(fields)")
    }
}

private let allowedPairingRequestPayloadKeys: Set<String> = [
    "pairing_nonce",
    "pairing_code",
    "device_id",
    "device_name",
    "public_key",
]

private let allowedHelloPayloadKeys: Set<String> = [
    "device_id",
    "device_name",
    "client_capabilities",
]

private let allowedAuthResponsePayloadKeys: Set<String> = [
    "device_id",
    "nonce",
    "signature",
]

private let allowedModelsPullPayloadKeys: Set<String> = [
    "model",
    "backend",
]

private let allowedChatCancelPayloadKeys: Set<String> = [
    "target_request_id",
]

private let allowedChatSessionsListPayloadKeys: Set<String> = [
    "limit",
    "include_archived",
    "query",
    "embedding_model_id",
]

private let allowedChatMessagesListPayloadKeys: Set<String> = [
    "session_id",
    "limit",
]

private let allowedChatSessionLifecyclePayloadKeys: Set<String> = [
    "session_id",
]

private let allowedChatSessionRenamePayloadKeys: Set<String> = [
    "session_id",
    "title",
]

private let allowedMemoryListPayloadKeys: Set<String> = [
    "query",
]

private let allowedMemoryUpsertPayloadKeys: Set<String> = [
    "id",
    "content",
    "enabled",
]

private let allowedMemoryDeletePayloadKeys: Set<String> = [
    "id",
]

private let allowedMemorySummaryDraftsListPayloadKeys: Set<String> = [
    "limit",
]

private let allowedMemorySummaryDraftApprovePayloadKeys: Set<String> = [
    "draft_id",
    "content",
    "enabled",
    "expected_session_id",
    "expected_source_message_count",
]

private let allowedMemorySummaryDraftDismissPayloadKeys: Set<String> = [
    "draft_id",
    "expected_session_id",
    "expected_source_message_count",
]

private let allowedChatRequestPayloadKeys: Set<String> = [
    "session_id",
    "model",
    "locale",
    "messages",
]

private let allowedChatMessageKeys: Set<String> = [
    "role",
    "content",
    "attachments",
]

private let allowedChatAttachmentKeys: Set<String> = [
    "type",
    "mime_type",
    "name",
    "data_base64",
    "text",
]

private func chatAttachments(from object: [String: JSONValue]) throws -> [ChatAttachment] {
    guard let attachmentsValue = object["attachments"] else { return [] }
    guard case .array(let attachmentValues) = attachmentsValue else {
        throw LocalRuntimeRouterError.invalidPayload("attachments must be an array")
    }
    return try attachmentValues.map { value in
        guard case .object(let attachmentObject) = value else {
            throw LocalRuntimeRouterError.invalidPayload("Each attachment must be an object")
        }
        let unsupportedKeys = Set(attachmentObject.keys).subtracting(allowedChatAttachmentKeys)
        guard unsupportedKeys.isEmpty else {
            let fields = unsupportedKeys.sorted().joined(separator: ", ")
            throw LocalRuntimeRouterError.invalidPayload("Attachment contains unsupported field(s): \(fields)")
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
        case .unreadablePDF,
             .archiveListingFailed,
             .archiveEntryReadFailed,
             .converterFailed,
             .noExtractableText,
             .resourceLimitExceeded:
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

    var withoutInlineDataForStorage: ChatAttachment {
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
    var contextWindowTokens: Int?
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

private func optionalRequestString(_ key: String, in payload: [String: JSONValue]) throws -> String? {
    guard let value = payload[key] else { return nil }
    guard case .string(let string) = value else {
        throw LocalRuntimeRouterError.invalidPayload("Payload field \(key) must be a string")
    }
    return string.isEmpty ? nil : string
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

private func optionalRequestInt(_ key: String, in payload: [String: JSONValue]) throws -> Int? {
    guard let value = payload[key] else { return nil }
    guard case .number(let number) = value,
          number.isFinite,
          number.rounded(.towardZero) == number,
          number >= Double(Int.min),
          number <= Double(Int.max) else {
        throw LocalRuntimeRouterError.invalidPayload("Payload field \(key) must be an integer")
    }
    return Int(number)
}

private func boundedWindowLimit(_ value: Int?, defaultLimit: Int, maxLimit: Int) -> Int {
    guard let value else { return defaultLimit }
    return min(max(value, 0), maxLimit)
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

private func optionalRequestBool(_ key: String, in payload: [String: JSONValue]) throws -> Bool? {
    guard let value = payload[key] else { return nil }
    guard case .bool(let bool) = value else {
        throw LocalRuntimeRouterError.invalidPayload("Payload field \(key) must be a boolean")
    }
    return bool
}

private extension String {
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
