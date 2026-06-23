package com.localagentbridge.android.runtime

import android.app.Application
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Base64
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.localagentbridge.android.core.protocol.AuthChallengePayload
import com.localagentbridge.android.core.protocol.AuthResponsePayload
import com.localagentbridge.android.core.protocol.ChatAttachmentPayload
import com.localagentbridge.android.core.protocol.ChatCancelPayload
import com.localagentbridge.android.core.protocol.ChatDeltaPayload
import com.localagentbridge.android.core.protocol.ChatDonePayload
import com.localagentbridge.android.core.protocol.ChatMessagePayload
import com.localagentbridge.android.core.protocol.ChatSendPayload
import com.localagentbridge.android.core.protocol.ChatSuggestionsRequestPayload
import com.localagentbridge.android.core.protocol.ChatSuggestionsResultPayload
import com.localagentbridge.android.core.protocol.ErrorPayload
import com.localagentbridge.android.core.protocol.HelloPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.ModelPullPayload
import com.localagentbridge.android.core.protocol.ModelPullResultPayload
import com.localagentbridge.android.core.protocol.ModelsResultPayload
import com.localagentbridge.android.core.protocol.PairingRequestPayload
import com.localagentbridge.android.core.protocol.PairingResultPayload
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.RuntimeHealthPayload
import com.localagentbridge.android.core.pairing.DeviceIdentityStore
import com.localagentbridge.android.core.pairing.MacPairingPayload
import com.localagentbridge.android.core.pairing.MacPairingPayloadParser
import com.localagentbridge.android.core.pairing.PairingStore
import com.localagentbridge.android.core.pairing.TrustedMac
import com.localagentbridge.android.core.transport.BonjourDiscovery
import com.localagentbridge.android.core.transport.MacRuntimeTransportClient
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.RuntimeConnectionFailure
import com.localagentbridge.android.core.transport.RuntimeConnectionFailureReason
import com.localagentbridge.android.core.transport.RuntimeConnectionManager
import com.localagentbridge.android.core.transport.RuntimeConnectionTarget
import com.localagentbridge.android.core.transport.RuntimeEndpointHint
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import com.localagentbridge.android.core.transport.RuntimeRouteCandidate
import com.localagentbridge.android.core.transport.RuntimeRouteResolver
import com.localagentbridge.android.core.transport.RuntimeRouteSource
import com.localagentbridge.android.core.transport.RuntimeTransportConnector
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import java.util.UUID

class RuntimeClientViewModel(application: Application) : AndroidViewModel(application) {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }
    private val client = MacRuntimeTransportClient()
    private val connectionManager = RuntimeConnectionManager(
        connector = RuntimeTransportConnector { host, port, timeoutMillis ->
            client.connect(host = host, port = port, timeoutMillis = timeoutMillis)
        },
        routeResolver = RuntimeRouteResolver { target ->
            runtimeRouteCandidates(state.value, target)
        },
    )
    private val discovery = BonjourDiscovery(application)
    private val pairingStore = PairingStore(application)
    private val deviceIdentityStore = DeviceIdentityStore(application)
    private val localStore = RuntimeLocalStore(application, json)
    private var readJob: Job? = null
    private var discoveryJob: Job? = null
    private var reconnectJob: Job? = null
    private var pendingPairingPayload: MacPairingPayload? = null
    private var pendingModelPullRequestId: String? = null
    private var pendingSuggestionRequestId: String? = null
    private var pendingSuggestionSessionId: String? = null
    private var modelIdToSelectAfterRefresh: String? = null
    private var isSessionAuthenticated = false
    private var persistedRuntimeData = PersistedRuntimeData()
    private var shouldRestoreTrustedRuntimeConnection = true
    private var didAttemptTrustedRuntimeRestore = false

    private val mutableState = MutableStateFlow(RuntimeUiState())
    val state: StateFlow<RuntimeUiState> = mutableState.asStateFlow()

    init {
        publishPersistedRuntimeData(localStore.load(), save = false)
        viewModelScope.launch {
            pairingStore.trustedMac.collect { trusted ->
                mutableState.update {
                    if (trusted == null) {
                        it.copy(trustedMac = null)
                    } else {
                        val endpoint = trusted.lastKnownEndpointHintOrNull()
                        it.copy(
                            trustedMac = RuntimeTrustedMac(
                                deviceId = trusted.deviceId,
                                name = trusted.name,
                                fingerprint = trusted.fingerprint,
                                routeToken = trusted.routeToken,
                                endpointHint = endpoint,
                            ),
                            macHost = endpoint?.host ?: it.macHost,
                            macPort = endpoint?.port?.toString() ?: it.macPort,
                            macEndpointSource = endpoint?.source ?: it.macEndpointSource,
                        )
                    }
                }
                if (
                    trusted != null &&
                    shouldRestoreTrustedRuntimeConnection &&
                    !didAttemptTrustedRuntimeRestore
                ) {
                    didAttemptTrustedRuntimeRestore = true
                    val current = state.value
                    val target = trusted.toConnectionTarget()
                    if (!current.isConnected && !current.isConnecting && target.endpointHint != null) {
                        connectToRuntime(target)
                    }
                }
            }
        }
    }

    fun updateHost(value: String) {
        mutableState.update {
            it.copy(
                macHost = value.trim(),
                macEndpointSource = RuntimeEndpointSource.Manual,
            )
        }
    }

    fun updatePort(value: String) {
        mutableState.update {
            it.copy(
                macPort = value.filter(Char::isDigit).take(5),
                macEndpointSource = RuntimeEndpointSource.Manual,
            )
        }
    }

    fun useUsbReverseEndpoint() {
        mutableState.update {
            it.copy(
                macHost = "127.0.0.1",
                macPort = "43170",
                macEndpointSource = RuntimeEndpointSource.UsbReverse,
                error = null,
            )
        }
    }

    fun useEmulatorEndpoint() {
        mutableState.update {
            it.copy(
                macHost = "10.0.2.2",
                macPort = "43170",
                macEndpointSource = RuntimeEndpointSource.Emulator,
                error = null,
            )
        }
    }

    fun updatePairingCode(value: String) {
        mutableState.update { it.copy(pairingCode = value.filter(Char::isDigit).take(6)) }
    }

    fun updateChatInput(value: String) {
        mutableState.update { it.copy(chatInput = value) }
    }

    fun useSuggestedQuestion(question: String) {
        val trimmed = question.trim()
        if (trimmed.isBlank()) return
        mutableState.update { it.copy(chatInput = trimmed, error = null) }
    }

    fun addAttachments(uris: List<Uri>) {
        if (uris.isEmpty()) return
        viewModelScope.launch {
            val resolver = getApplication<Application>().contentResolver
            val loadedAttachments = mutableListOf<RuntimePendingAttachment>()
            for (uri in uris.take(MAX_PENDING_ATTACHMENTS)) {
                val metadata = attachmentMetadata(uri)
                if (metadata.sizeBytes > MAX_ATTACHMENT_BYTES) {
                    showError("attachment_too_large", metadata.name)
                    return@launch
                }
                val bytes = runCatching {
                    resolver.openInputStream(uri)?.use { input -> input.readBytes() }
                }.getOrNull()
                if (bytes == null) {
                    showError("attachment_read_failed", metadata.name)
                    return@launch
                }
                if (bytes.size > MAX_ATTACHMENT_BYTES) {
                    showError("attachment_too_large", metadata.name)
                    return@launch
                }
                loadedAttachments += RuntimePendingAttachment(
                    type = attachmentType(metadata.mimeType, metadata.name),
                    name = metadata.name,
                    mimeType = metadata.mimeType,
                    sizeBytes = bytes.size.toLong(),
                    dataBase64 = Base64.encodeToString(bytes, Base64.NO_WRAP),
                )
            }
            mutableState.update { current ->
                val combined = (current.pendingAttachments + loadedAttachments)
                    .take(MAX_PENDING_ATTACHMENTS)
                current.copy(pendingAttachments = combined, error = null)
            }
        }
    }

    fun removePendingAttachment(attachmentId: String) {
        mutableState.update { current ->
            current.copy(
                pendingAttachments = current.pendingAttachments.filterNot { it.id == attachmentId },
                error = null,
            )
        }
    }

    fun setAppLanguageTag(languageTag: String) {
        publishPersistedRuntimeData(
            persistedRuntimeData.withAppLanguageTag(languageTag),
            save = true,
        )
    }

    fun startNewChat() {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        clearPendingSuggestions()
        publishPersistedRuntimeData(
            persistedRuntimeData.withNoActiveSession(),
            save = true,
        )
        mutableState.update { it.copy(chatInput = "", isLoadingSuggestions = false) }
    }

    fun openPreviousChat(sessionId: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (persistedRuntimeData.sessions.none { it.id == sessionId && it.archivedAtMillis == null }) {
            showError("chat_session_not_found")
            return
        }
        clearPendingSuggestions()
        publishPersistedRuntimeData(
            persistedRuntimeData.withActiveSession(sessionId),
            save = true,
        )
        mutableState.update { it.copy(isLoadingSuggestions = false) }
    }

    fun selectChatSession(sessionId: String) {
        openPreviousChat(sessionId)
    }

    fun renameChatSession(sessionId: String, title: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (persistedRuntimeData.sessions.none { it.id == sessionId }) {
            showError("chat_session_not_found")
            return
        }
        publishPersistedRuntimeData(
            persistedRuntimeData.withRenamedChatSession(sessionId, title, nowMillis()),
            save = true,
        )
    }

    fun deleteChatSession(sessionId: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (persistedRuntimeData.sessions.none { it.id == sessionId }) {
            showError("chat_session_not_found")
            return
        }
        publishPersistedRuntimeData(
            persistedRuntimeData.withoutChatSession(sessionId),
            save = true,
        )
        if (state.value.activeChatSessionId == null) {
            mutableState.update { it.copy(chatInput = "") }
        }
    }

    fun archiveChatSession(sessionId: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (persistedRuntimeData.sessions.none { it.id == sessionId }) {
            showError("chat_session_not_found")
            return
        }
        publishPersistedRuntimeData(
            persistedRuntimeData.withArchivedChatSession(sessionId, nowMillis()),
            save = true,
        )
        if (state.value.activeChatSessionId == null) {
            mutableState.update { it.copy(chatInput = "") }
        }
    }

    fun archiveChatSessions() {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        publishPersistedRuntimeData(
            persistedRuntimeData.withArchivedChatSessions(nowMillis()),
            save = true,
        )
        mutableState.update { it.copy(chatInput = "") }
    }

    fun unarchiveChatSession(sessionId: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (persistedRuntimeData.sessions.none { it.id == sessionId }) {
            showError("chat_session_not_found")
            return
        }
        publishPersistedRuntimeData(
            persistedRuntimeData.withUnarchivedChatSession(sessionId, nowMillis()),
            save = true,
        )
    }

    fun clearChatSessions() {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        publishPersistedRuntimeData(
            persistedRuntimeData.withoutChatSessions(),
            save = true,
        )
        mutableState.update { it.copy(chatInput = "") }
    }

    fun storeMemoryEntry(content: String) {
        publishPersistedRuntimeData(
            persistedRuntimeData.withMemoryEntry(content, nowMillis()),
            save = true,
        )
    }

    fun addMemoryEntry(content: String) {
        storeMemoryEntry(content)
    }

    fun removeMemoryEntry(entryId: String) {
        publishPersistedRuntimeData(
            persistedRuntimeData.withoutMemoryEntry(entryId),
            save = true,
        )
    }

    fun setMemoryEntryEnabled(entryId: String, enabled: Boolean) {
        publishPersistedRuntimeData(
            persistedRuntimeData.withMemoryEntryEnabled(entryId, enabled, nowMillis()),
            save = true,
        )
    }

    fun connectToTrustedRuntime() {
        shouldRestoreTrustedRuntimeConnection = true
        reconnectJob?.cancel()
        reconnectJob = null
        viewModelScope.launch {
            val target = trustedRuntimeConnectionTarget(state.value)
            if (target == null) {
                showError("pairing_required")
                return@launch
            }

            connectToRuntime(target)
        }
    }

    fun trustMacFromPairingQr(rawValue: String) {
        shouldRestoreTrustedRuntimeConnection = true
        viewModelScope.launch {
            val payload = runCatching { MacPairingPayloadParser.parse(rawValue) }
                .onFailure { error -> showError("invalid_pairing_qr", error.message) }
                .getOrNull()
                ?: return@launch

            pendingPairingPayload = payload
            mutableState.update {
                val endpoint = payload.endpointHintOrNull()
                it.copy(
                    pairingCode = payload.pairingCode,
                    macHost = endpoint?.host ?: it.macHost,
                    macPort = endpoint?.port?.toString() ?: it.macPort,
                    macEndpointSource = endpoint?.source ?: it.macEndpointSource,
                    error = null,
                )
            }
            val target = payload.toConnectionTarget()
            if (target == null) {
                pendingPairingPayload = null
                showError("pairing_endpoint_unavailable")
                return@launch
            }
            if (connectToRuntime(target, requestHealthAfterConnect = false)) {
                sendPairingRequest(payload)
            } else {
                pendingPairingPayload = null
            }
        }
    }

    fun showQrScanFailed(detail: String?) {
        showError("qr_scan_failed", detail)
    }

    private suspend fun sendPairingRequest(payload: MacPairingPayload) {
        runCatching { deviceIdentityStore.loadOrCreate() }
            .onSuccess { identity ->
                sendEnvelope(
                    envelope(
                        type = MessageType.PairingRequest,
                        serializer = PairingRequestPayload.serializer(),
                        payload = PairingRequestPayload(
                            pairingNonce = payload.pairingNonce,
                            pairingCode = payload.pairingCode,
                            deviceId = identity.deviceId,
                            deviceName = identity.deviceName,
                            publicKey = identity.publicKeyBase64,
                        ),
                    )
                )
            }
            .onFailure { error ->
                pendingPairingPayload = null
                showError("device_identity_failed", error.message)
            }
    }

    fun startDiscovery() {
        discoveryJob?.cancel()
        discoveryJob = viewModelScope.launch {
            mutableState.update {
                it.copy(
                    isDiscovering = true,
                    error = null,
                )
            }
            try {
                discovery.discover()
                    .collect { peers ->
                        mutableState.update {
                            it.copy(
                                discoveredMacs = peers.map { peer ->
                                    RuntimeDiscoveredMac(
                                        serviceName = peer.serviceName,
                                        host = peer.host,
                                        port = peer.port,
                                        routeToken = peer.routeToken,
                                        deviceId = peer.deviceId,
                                        fingerprint = peer.fingerprint,
                                        app = peer.app,
                                        version = peer.version,
                                    )
                                },
                                isDiscovering = true,
                                error = null,
                            )
                        }
                    }
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                mutableState.update {
                    it.copy(error = RuntimeUiError("discovery_failed", error.message))
                }
            } finally {
                mutableState.update { it.copy(isDiscovering = false) }
            }
        }
    }

    fun stopDiscovery() {
        discoveryJob?.cancel()
        discoveryJob = null
        mutableState.update { it.copy(isDiscovering = false) }
    }

    fun useDiscoveredMac(peer: RuntimeDiscoveredMac) {
        mutableState.update {
            it.copy(
                macHost = peer.host,
                macPort = peer.port.toString(),
                macEndpointSource = RuntimeEndpointSource.BonjourDiscovery,
                error = null,
            )
        }
    }

    fun forgetTrustedMac() {
        shouldRestoreTrustedRuntimeConnection = false
        viewModelScope.launch {
            pairingStore.forgetMac()
            mutableState.update { it.copy(error = null) }
        }
    }

    fun disconnect() {
        shouldRestoreTrustedRuntimeConnection = false
        reconnectJob?.cancel()
        reconnectJob = null
        readJob?.cancel()
        readJob = null
        client.close()
        isSessionAuthenticated = false
        pendingModelPullRequestId = null
        clearPendingSuggestions()
        modelIdToSelectAfterRefresh = null
        mutableState.update {
            it.copy(
                isConnected = false,
                isConnecting = false,
                isStreaming = false,
                isLoadingSuggestions = false,
                installingModelId = null,
                activeRequestId = null,
                runtimeStatus = "disconnected",
            )
        }
    }

    fun requestRuntimeHealth() {
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }
        sendEnvelope(ProtocolEnvelope(type = MessageType.RuntimeHealth))
    }

    fun requestModels() {
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }
        mutableState.update {
            it.copy(
                isLoadingModels = true,
                error = null,
            )
        }
        sendEnvelope(ProtocolEnvelope(type = MessageType.ModelsList))
    }

    fun selectModel(modelId: String) {
        val model = state.value.models.firstOrNull { it.id == modelId }
        if (model != null && !model.isChatModel()) {
            showError("select_chat_model")
            return
        }
        if (model != null && !model.installed) {
            requestModelInstall(modelId)
            return
        }
        persistSelectedModel(modelId)
    }

    fun selectEmbeddingModel(modelId: String) {
        val model = state.value.models.firstOrNull { it.id == modelId }
        if (model == null || !model.isEmbeddingModel()) {
            showError("select_embedding_model")
            return
        }
        persistSelectedEmbeddingModel(modelId)
    }

    fun requestModelInstall(modelId: String) {
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }

        val model = state.value.models.firstOrNull { it.id == modelId }
        if (model != null && !model.isChatModel()) {
            showError("select_chat_model")
            return
        }
        if (model?.installed == true) {
            persistSelectedModel(modelId)
            return
        }

        val requestId = UUID.randomUUID().toString()
        pendingModelPullRequestId = requestId
        modelIdToSelectAfterRefresh = modelId
        mutableState.update {
            it.copy(
                installingModelId = modelId,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.ModelsPull,
                requestId = requestId,
                serializer = ModelPullPayload.serializer(),
                payload = ModelPullPayload(model = modelId),
            )
        )
    }

    fun sendChatMessage() {
        val current = state.value
        val text = current.chatInput.trim()
        if (text.isEmpty() && current.pendingAttachments.isEmpty()) return
        when (current.selectedModelSendState()) {
            SelectedModelSendState.Ready -> Unit
            SelectedModelSendState.Missing -> {
                showError("select_model")
                return
            }
            SelectedModelSendState.NotInstalled -> {
                showError("install_model_first")
                return
            }
        }
        val model = current.selectedModelId ?: return
        val selectedModel = current.models.firstOrNull { it.id == model }
        if (current.pendingAttachments.any { it.type == ATTACHMENT_TYPE_IMAGE } && selectedModel?.supportsImageInput() != true) {
            showError("select_vision_model")
            return
        }
        if (!current.isConnected) {
            showError("connect_first")
            return
        }
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }

        val sessionId = ensureActiveChatSession()
        val requestId = UUID.randomUUID().toString()
        val displayText = text.ifBlank {
            current.pendingAttachments.joinToString(
                separator = "\n",
                prefix = "Analyze attached input:\n",
            ) { "- ${it.name}" }
        }
        val attachments = current.pendingAttachments
        val userMessage = RuntimeChatMessage(role = "user", content = displayText)
        val assistantMessage = RuntimeChatMessage(role = "assistant", content = "")
        val updatedMessages = current.messages + userMessage + assistantMessage
        clearPendingSuggestions()
        mutableState.update {
            it.copy(
                activeChatSessionId = sessionId,
                chatInput = "",
                pendingAttachments = emptyList(),
                messages = updatedMessages,
                activeRequestId = requestId,
                isStreaming = true,
                isLoadingSuggestions = false,
                error = null
            )
        }
        persistMessages(sessionId, updatedMessages)

        sendEnvelope(
            envelope(
                type = MessageType.ChatSend,
                requestId = requestId,
                serializer = ChatSendPayload.serializer(),
                payload = ChatSendPayload(
                    sessionId = sessionId,
                    model = model,
                    messages = chatSendMessages(
                        messages = current.messages + userMessage,
                        memoryEntries = current.memoryEntries,
                        attachments = attachments,
                    )
                )
            )
        )
    }

    fun cancelGeneration() {
        val activeRequestId = state.value.activeRequestId ?: return
        sendEnvelope(
            envelope(
                type = MessageType.ChatCancel,
                serializer = ChatCancelPayload.serializer(),
                payload = ChatCancelPayload(targetRequestId = activeRequestId)
            )
        )
    }

    private suspend fun connectToRuntime(
        host: String,
        port: Int,
        requestHealthAfterConnect: Boolean = true,
        endpointSource: RuntimeEndpointSource = RuntimeEndpointSource.Manual,
    ): Boolean = connectToRuntime(
        target = RuntimeConnectionTarget(
            identity = null,
            endpointHint = RuntimeEndpointHint(
                host = host,
                port = port,
                source = endpointSource,
            ),
        ),
        requestHealthAfterConnect = requestHealthAfterConnect,
    )

    private suspend fun connectToRuntime(
        target: RuntimeConnectionTarget,
        requestHealthAfterConnect: Boolean = true,
    ): Boolean {
        mutableState.update {
            it.copy(
                isConnecting = true,
                error = null,
                runtimeStatus = "connecting",
            )
        }

        readJob?.cancel()
        readJob = null
        client.close()
        isSessionAuthenticated = false

        val result = runCatching {
            Log.d(
                TAG,
                "Connecting to runtime ${target.connectionLogLabel()}"
            )
            connectionManager.connect(target)
        }.onSuccess {
            Log.d(TAG, "Connected to runtime ${target.connectionLogLabel()}")
            reconnectJob = null
            mutableState.update {
                it.copy(
                    isConnected = true,
                    isConnecting = false,
                    runtimeStatus = "connected",
                    error = null,
                )
            }
            startReadLoop()
            if (requestHealthAfterConnect) {
                sendHello()
            }
        }.onFailure { error ->
            Log.e(TAG, "Runtime connection failed", error)
            mutableState.update {
                it.copy(
                    isConnected = false,
                    isConnecting = false,
                    runtimeStatus = "failed",
                    error = error.connectionUiError(),
                )
            }
        }
        return result.isSuccess
    }

    private fun startReadLoop() {
        readJob?.cancel()
        readJob = viewModelScope.launch {
            while (isActive) {
                runCatching { client.receive() }
                    .onSuccess { envelope ->
                        Log.d(TAG, "Received ${envelope.type} request_id=${envelope.requestId}")
                        handleEnvelope(envelope)
                    }
                    .onFailure { error ->
                        if (isActive) {
                            Log.e(TAG, "Runtime receive failed", error)
                            isSessionAuthenticated = false
                            mutableState.update {
                                it.copy(
                                    isConnected = false,
                                    isStreaming = false,
                                    isLoadingSuggestions = false,
                                    installingModelId = null,
                                    activeRequestId = null,
                                    runtimeStatus = "disconnected",
                                    error = RuntimeUiError("receive_failed", error.message)
                                )
                            }
                            scheduleTrustedRuntimeReconnect()
                        }
                        return@launch
                    }
            }
        }
    }

    private fun scheduleTrustedRuntimeReconnect() {
        if (!shouldRestoreTrustedRuntimeConnection) return
        val target = trustedRuntimeConnectionTarget(state.value) ?: return
        reconnectJob?.cancel()
        reconnectJob = viewModelScope.launch {
            delay(RECONNECT_DELAY_MS)
            val current = state.value
            if (
                shouldRestoreTrustedRuntimeConnection &&
                !current.isConnected &&
                !current.isConnecting
            ) {
                connectToRuntime(target)
            }
        }
    }

    private fun handleEnvelope(envelope: ProtocolEnvelope) {
        when (envelope.type) {
            MessageType.AuthChallenge -> handleAuthChallenge(envelope)
            MessageType.AuthResponse -> handleAuthResponse(envelope)
            MessageType.PairingResult -> handlePairingResult(envelope)
            MessageType.RuntimeHealth -> handleRuntimeHealth(envelope)
            MessageType.ModelsList, MessageType.ModelsResult -> handleModels(envelope)
            MessageType.ModelsPull -> handleModelPull(envelope)
            MessageType.ChatDelta -> handleChatDelta(envelope)
            MessageType.ChatDone -> handleChatDone(envelope)
            MessageType.ChatCancel -> handleCancelAck(envelope)
            MessageType.ChatSuggestionsResult -> handleChatSuggestionsResult(envelope)
            MessageType.Error -> handleError(envelope)
        }
    }

    private fun handleAuthChallenge(envelope: ProtocolEnvelope) {
        val payload = decodePayload(AuthChallengePayload.serializer(), envelope.payload) ?: return
        viewModelScope.launch {
            runCatching {
                val identity = deviceIdentityStore.loadOrCreate()
                sendEnvelope(
                    envelope(
                        type = MessageType.AuthResponse,
                        serializer = AuthResponsePayload.serializer(),
                        payload = AuthResponsePayload(
                            deviceId = identity.deviceId,
                            nonce = payload.nonce,
                            signature = identity.sign(payload.nonce.encodeToByteArray()),
                        ),
                        requestId = envelope.requestId,
                    )
                )
            }.onFailure { error ->
                showError("authentication_failed", error.message)
            }
        }
    }

    private fun handleAuthResponse(envelope: ProtocolEnvelope) {
        val payload = decodePayload(AuthResponsePayload.serializer(), envelope.payload) ?: return
        if (payload.accepted == true) {
            isSessionAuthenticated = true
            mutableState.update {
                it.copy(
                    runtimeStatus = "authenticated",
                    error = null,
                )
            }
            requestRuntimeHealth()
        } else {
            isSessionAuthenticated = false
            showError("authentication_failed", payload.message)
        }
    }

    private fun handlePairingResult(envelope: ProtocolEnvelope) {
        val payload = decodePayload(PairingResultPayload.serializer(), envelope.payload) ?: return
        val pending = pendingPairingPayload
        if (!payload.accepted || pending == null) {
            pendingPairingPayload = null
            mutableState.update {
                it.copy(error = RuntimeUiError("pairing_rejected", payload.message))
            }
            return
        }

        viewModelScope.launch {
            val endpoint = pending.endpointHintOrNull()
            val trusted = TrustedMac(
                deviceId = payload.macDeviceId ?: pending.macDeviceId,
                name = pending.macName,
                fingerprint = pending.fingerprint,
                routeToken = pending.routeToken,
                host = endpoint?.host,
                port = endpoint?.port,
            )
            pairingStore.trustMac(trusted)
            val trustedEndpoint = trusted.lastKnownEndpointHintOrNull()
            pendingPairingPayload = null
            isSessionAuthenticated = true
            mutableState.update {
                it.copy(
                    trustedMac = RuntimeTrustedMac(
                        deviceId = trusted.deviceId,
                        name = trusted.name,
                        fingerprint = trusted.fingerprint,
                        routeToken = trusted.routeToken,
                        endpointHint = trustedEndpoint,
                    ),
                    macHost = trustedEndpoint?.host ?: it.macHost,
                    macPort = trustedEndpoint?.port?.toString() ?: it.macPort,
                    macEndpointSource = trustedEndpoint?.source ?: it.macEndpointSource,
                    error = null,
                )
            }
            requestRuntimeHealth()
        }
    }

    private fun sendHello() {
        viewModelScope.launch {
            runCatching { deviceIdentityStore.loadOrCreate() }
                .onSuccess { identity ->
                    sendEnvelope(
                        envelope(
                            type = MessageType.Hello,
                            serializer = HelloPayload.serializer(),
                            payload = HelloPayload(
                                deviceId = identity.deviceId,
                                deviceName = identity.deviceName,
                                capabilities = CLIENT_CAPABILITIES,
                            ),
                        )
                    )
                }
                .onFailure { error ->
                    showError("device_identity_failed", error.message)
                }
        }
    }

    private fun handleRuntimeHealth(envelope: ProtocolEnvelope) {
        val payload = decodePayload(RuntimeHealthPayload.serializer(), envelope.payload) ?: return
        val providerStatuses = runtimeProviderStatuses(payload)
        mutableState.update {
            it.copy(
                runtimeStatus = payload.status,
                backendAvailable = providerStatuses.takeIf { statuses -> statuses.isNotEmpty() }
                    ?.any { status -> status.available }
                    ?: payload.ollama?.available,
                backendCode = payload.ollama?.code ?: payload.lmStudio?.code,
                providerStatuses = providerStatuses,
                error = null
            )
        }
        if (isSessionAuthenticated) {
            requestModels()
        }
    }

    private fun handleModels(envelope: ProtocolEnvelope) {
        val payload = decodePayload(ModelsResultPayload.serializer(), envelope.payload) ?: return
        val models = payload.models.map {
            val provider = it.provider?.takeIf(String::isNotBlank)
                ?: it.backend?.takeIf(String::isNotBlank)
                ?: providerFromQualifiedId(it.qualifiedId)
                ?: "ollama"
            val providerModelId = it.providerModelId?.takeIf(String::isNotBlank)
                ?: providerModelIdFromQualifiedId(it.qualifiedId, provider)
            val modelId = it.qualifiedId?.takeIf(String::isNotBlank)
                ?: providerModelId?.let { id -> qualifyModelId(provider, id) }
                ?: it.id
            val capabilities = it.capabilities.mapNotNull { capability ->
                capability.trim().lowercase().takeIf(String::isNotBlank)
            }.distinct()
            val modelKind = normalizeModelKind(
                kind = it.modelKind ?: it.kind,
                capabilities = capabilities,
                id = modelId,
                name = it.name ?: it.id,
            )
            RuntimeModel(
                id = modelId,
                name = it.name?.takeIf(String::isNotBlank) ?: it.id,
                backend = it.backend ?: provider,
                provider = provider,
                modelKind = modelKind,
                capabilities = capabilities.ifEmpty { defaultCapabilitiesForModelKind(modelKind) },
                providerModelId = providerModelId,
                installed = it.installed ?: true,
                running = it.running ?: false,
                source = it.source,
                description = it.description,
                sizeBytes = it.sizeBytes,
            )
        }
        val current = state.value
        val chatModels = models.filter { it.isChatModel() }
        val embeddingModels = models.filter { it.isEmbeddingModel() }
        val installTarget = modelIdToSelectAfterRefresh
        val installedTarget = installTarget?.let { target ->
            chatModels.firstOrNull { it.id == target && it.installed }
        }
        val selectedModelId = when {
            installedTarget != null -> installedTarget.id
            current.selectedModelId != null && chatModels.any { it.id == current.selectedModelId && it.installed } -> current.selectedModelId
            else -> chatModels.firstOrNull { it.installed }?.id
        }
        val selectedEmbeddingModelId = when {
            current.selectedEmbeddingModelId != null &&
                embeddingModels.any { it.id == current.selectedEmbeddingModelId && it.installed } -> current.selectedEmbeddingModelId
            else -> embeddingModels.firstOrNull { it.installed }?.id
        }
        if (installedTarget != null) {
            modelIdToSelectAfterRefresh = null
        }
        val stillInstalling = current.installingModelId?.takeIf { installingId ->
            models.none { it.id == installingId && it.installed }
        }
        mutableState.update {
            current.copy(
                models = models,
                isLoadingModels = false,
                installingModelId = stillInstalling,
                selectedModelId = selectedModelId,
                selectedEmbeddingModelId = selectedEmbeddingModelId,
                error = null
            )
        }
        persistSelectedModel(selectedModelId, publish = false)
        persistSelectedEmbeddingModel(selectedEmbeddingModelId, publish = false)
    }

    private fun handleModelPull(envelope: ProtocolEnvelope) {
        val payload = decodePayload(ModelPullResultPayload.serializer(), envelope.payload) ?: return
        val modelId = payload.model ?: payload.id ?: state.value.installingModelId ?: modelIdToSelectAfterRefresh
        val status = payload.status?.lowercase()
        val accepted = payload.accepted == true || (status != null && status in ACCEPTED_PULL_STATUSES)
        val succeeded = payload.success == true || (status != null && status in SUCCESS_PULL_STATUSES)
        val failed = payload.success == false || (status != null && status in FAILED_PULL_STATUSES)

        when {
            failed -> {
                if (pendingModelPullRequestId == envelope.requestId) {
                    pendingModelPullRequestId = null
                }
                if (modelId != null && modelIdToSelectAfterRefresh == modelId) {
                    modelIdToSelectAfterRefresh = null
                }
                mutableState.update {
                    it.copy(
                        installingModelId = if (it.installingModelId == modelId) null else it.installingModelId,
                        error = RuntimeUiError("model_install_failed", payload.message),
                    )
                }
            }
            accepted || succeeded -> {
                if (modelId != null) {
                    modelIdToSelectAfterRefresh = modelId
                }
                if (succeeded && pendingModelPullRequestId == envelope.requestId) {
                    pendingModelPullRequestId = null
                }
                mutableState.update {
                    it.copy(
                        installingModelId = if (succeeded) null else modelId,
                        error = null,
                    )
                }
                requestModels()
            }
        }
    }

    private fun handleChatDelta(envelope: ProtocolEnvelope) {
        if (!isActiveChatEnvelope(envelope)) return
        val payload = decodePayload(ChatDeltaPayload.serializer(), envelope.payload) ?: return
        val updatedState = state.value.withChatDelta(envelope, payload)
        mutableState.value = updatedState
        persistActiveMessages(updatedState.messages)
    }

    private fun handleChatDone(envelope: ProtocolEnvelope) {
        if (!isActiveChatEnvelope(envelope)) return
        val payload = decodePayload(ChatDonePayload.serializer(), envelope.payload)
        val updatedState = state.value.withChatDone(envelope, payload)
        mutableState.value = updatedState
        persistActiveMessages(updatedState.messages, clearError = false)
        if (payload?.finishReason != "cancelled") {
            requestChatSuggestions(updatedState)
        }
    }

    private fun requestChatSuggestions(sourceState: RuntimeUiState) {
        if (!sourceState.isConnected || !isSessionAuthenticated) return
        if (sourceState.isStreaming || sourceState.isLoadingSuggestions) return
        if (sourceState.selectedModelSendState() != SelectedModelSendState.Ready) return

        val sessionId = sourceState.activeChatSessionId ?: return
        val model = sourceState.selectedModelId ?: return
        val recentMessages = sourceState.messages
            .filter { it.role == "user" || it.role == "assistant" }
            .filter { it.content.isNotBlank() }
            .takeLast(MAX_SUGGESTION_CONTEXT_MESSAGES)
            .map { message ->
                ChatMessagePayload(
                    role = message.role,
                    content = message.content,
                )
            }
        if (recentMessages.size < 2) return

        val requestId = UUID.randomUUID().toString()
        pendingSuggestionRequestId = requestId
        pendingSuggestionSessionId = sessionId
        mutableState.update {
            it.copy(
                isLoadingSuggestions = true,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.ChatSuggestionsRequest,
                requestId = requestId,
                serializer = ChatSuggestionsRequestPayload.serializer(),
                payload = ChatSuggestionsRequestPayload(
                    sessionId = sessionId,
                    model = model,
                    messages = recentMessages,
                    maxSuggestions = MAX_SUGGESTIONS,
                    locale = sourceState.selectedLanguageTag.takeIf { it.isNotBlank() },
                ),
            )
        )
    }

    private fun handleChatSuggestionsResult(envelope: ProtocolEnvelope) {
        if (pendingSuggestionRequestId != envelope.requestId) return
        if (pendingSuggestionSessionId != state.value.activeChatSessionId) {
            clearPendingSuggestions()
            mutableState.update { it.copy(isLoadingSuggestions = false) }
            return
        }
        val payload = decodePayload(ChatSuggestionsResultPayload.serializer(), envelope.payload)
        clearPendingSuggestions()
        val suggestions = payload?.suggestions.orEmpty().cleanedSuggestions()
        val updatedState = state.value.withChatSuggestions(suggestions)
        mutableState.value = updatedState.copy(isLoadingSuggestions = false)
        persistActiveMessages(updatedState.messages, clearError = false)
    }

    private fun handleCancelAck(envelope: ProtocolEnvelope) {
        val activeRequestId = state.value.activeRequestId ?: return
        val payload = if (envelope.requestId != activeRequestId) {
            if (envelope.payload.isEmpty()) return
            decodePayload(ChatCancelPayload.serializer(), envelope.payload) ?: return
        } else {
            null
        }
        val updatedState = state.value.withChatCancelAck(envelope, payload)
        mutableState.value = updatedState
        persistActiveMessages(updatedState.messages, clearError = false)
    }

    private fun handleError(envelope: ProtocolEnvelope) {
        if (pendingSuggestionRequestId == envelope.requestId) {
            clearPendingSuggestions()
            mutableState.update { it.copy(isLoadingSuggestions = false) }
            return
        }
        val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
        val isModelPullError = pendingModelPullRequestId == envelope.requestId
        val isActiveChatError = state.value.activeRequestId == envelope.requestId
        if (isModelPullError) {
            modelIdToSelectAfterRefresh = null
        }
        val updatedState = state.value.withRuntimeError(envelope, payload, pendingModelPullRequestId)
        mutableState.value = updatedState
        if (isActiveChatError) {
            persistActiveMessages(updatedState.messages, clearError = false)
        }
        if (isModelPullError) {
            pendingModelPullRequestId = null
        }
    }

    private fun sendEnvelope(envelope: ProtocolEnvelope) {
        viewModelScope.launch {
            runCatching {
                Log.d(TAG, "Sending ${envelope.type} request_id=${envelope.requestId}")
                client.send(envelope)
            }
                .onFailure { error ->
                    Log.e(TAG, "Runtime send failed", error)
                    val current = state.value
                    val isActiveChatSend = envelope.type == MessageType.ChatSend &&
                        current.activeRequestId == envelope.requestId
                    val isSuggestionRequest = envelope.type == MessageType.ChatSuggestionsRequest &&
                        pendingSuggestionRequestId == envelope.requestId
                    if (isSuggestionRequest) {
                        clearPendingSuggestions()
                        mutableState.update { it.copy(isLoadingSuggestions = false) }
                        return@onFailure
                    }
                    val cleanedMessages = if (isActiveChatSend) {
                        current.messages.withoutTrailingBlankAssistantPlaceholder()
                    } else {
                        current.messages
                    }
                    mutableState.value = current.copy(
                        isConnected = client.isConnected,
                        isStreaming = false,
                        isLoadingModels = false,
                        installingModelId = null,
                        activeRequestId = null,
                        messages = cleanedMessages,
                        error = RuntimeUiError("send_failed", error.message)
                    )
                    if (isActiveChatSend) {
                        persistActiveMessages(cleanedMessages, clearError = false)
                    }
                }
        }
    }

    private fun <T> envelope(
        type: String,
        serializer: KSerializer<T>,
        payload: T,
        requestId: String = UUID.randomUUID().toString(),
    ): ProtocolEnvelope {
        return ProtocolEnvelope(
            type = type,
            requestId = requestId,
            payload = json.encodeToJsonElement(serializer, payload).jsonObject
        )
    }

    private fun <T> decodePayload(serializer: KSerializer<T>, payload: JsonObject): T? {
        return try {
            json.decodeFromJsonElement(serializer, payload)
        } catch (error: SerializationException) {
            showError("invalid_payload", error.message)
            null
        } catch (error: IllegalArgumentException) {
            showError("invalid_payload", error.message)
            null
        }
    }

    private fun showError(code: String, detail: String? = null) {
        mutableState.update { it.copy(error = RuntimeUiError(code, detail)) }
    }

    private fun clearPendingSuggestions() {
        pendingSuggestionRequestId = null
        pendingSuggestionSessionId = null
    }

    private fun attachmentMetadata(uri: Uri): AttachmentMetadata {
        val resolver = getApplication<Application>().contentResolver
        var name = uri.lastPathSegment?.substringAfterLast('/')?.takeIf(String::isNotBlank)
            ?: "attachment"
        var sizeBytes = -1L
        resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)
            ?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)
                    if (nameIndex >= 0) {
                        name = cursor.getString(nameIndex)?.takeIf(String::isNotBlank) ?: name
                    }
                    if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) {
                        sizeBytes = cursor.getLong(sizeIndex)
                    }
                }
            }
        val mimeType = resolver.getType(uri) ?: mimeTypeFromName(name)
        return AttachmentMetadata(name = name, mimeType = mimeType, sizeBytes = sizeBytes)
    }

    private fun ensureActiveChatSession(): String {
        val currentSessionId = state.value.activeChatSessionId
        if (currentSessionId != null) return currentSessionId
        val data = persistedRuntimeData.withNewChatSession(nowMillis())
        publishPersistedRuntimeData(data, save = true)
        return data.activeSessionId ?: error("new chat session was not created")
    }

    private fun persistActiveMessages(
        messages: List<RuntimeChatMessage>,
        clearError: Boolean = true,
    ) {
        val sessionId = state.value.activeChatSessionId ?: return
        persistMessages(sessionId, messages, clearError = clearError)
    }

    private fun persistMessages(
        sessionId: String,
        messages: List<RuntimeChatMessage>,
        clearError: Boolean = true,
    ) {
        publishPersistedRuntimeData(
            persistedRuntimeData.withPersistedMessages(
                sessionId = sessionId,
                messages = messages,
                nowMillis = nowMillis(),
            ),
            save = true,
            clearError = clearError,
        )
    }

    private fun publishPersistedRuntimeData(
        data: PersistedRuntimeData,
        save: Boolean,
        clearError: Boolean = true,
    ) {
        val cleanData = data.sanitized()
        persistedRuntimeData = cleanData
        if (save) {
            localStore.save(cleanData)
        }
        mutableState.update {
            it.copy(
                chatSessions = runtimeChatSessions(cleanData),
                archivedChatSessions = archivedRuntimeChatSessions(cleanData),
                activeChatSessionId = cleanData.activeSessionId,
                selectedModelId = cleanData.selectedModelId,
                selectedEmbeddingModelId = cleanData.selectedEmbeddingModelId,
                messages = activeSessionMessages(cleanData),
                memoryEntries = runtimeMemoryEntries(cleanData),
                selectedLanguageTag = cleanData.appLanguageTag,
                error = if (clearError) null else it.error,
            )
        }
    }

    private fun persistSelectedModel(modelId: String?, publish: Boolean = true) {
        val cleanData = persistedRuntimeData.withSelectedModelId(modelId)
        persistedRuntimeData = cleanData
        localStore.save(cleanData)
        if (publish) {
            mutableState.update {
                it.copy(
                    selectedModelId = cleanData.selectedModelId,
                    error = null,
                )
            }
        }
    }

    private fun persistSelectedEmbeddingModel(modelId: String?, publish: Boolean = true) {
        val cleanData = persistedRuntimeData.withSelectedEmbeddingModelId(modelId)
        persistedRuntimeData = cleanData
        localStore.save(cleanData)
        if (publish) {
            mutableState.update {
                it.copy(
                    selectedEmbeddingModelId = cleanData.selectedEmbeddingModelId,
                    error = null,
                )
            }
        }
    }

    private fun nowMillis(): Long = System.currentTimeMillis()

    private fun isActiveChatEnvelope(envelope: ProtocolEnvelope): Boolean {
        return state.value.activeRequestId == envelope.requestId
    }

    override fun onCleared() {
        stopDiscovery()
        disconnect()
        super.onCleared()
    }

    private companion object {
        const val TAG = "RuntimeClientVM"
        const val MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
        const val MAX_PENDING_ATTACHMENTS = 4
        const val RECONNECT_DELAY_MS = 750L
        const val MAX_SUGGESTIONS = 3
        const val MAX_SUGGESTION_CONTEXT_MESSAGES = 8
        const val ATTACHMENT_TYPE_IMAGE = "image"
        const val ATTACHMENT_TYPE_DOCUMENT = "document"
        val CLIENT_CAPABILITIES = listOf(
            MessageType.RuntimeHealth,
            MessageType.ModelsList,
            MessageType.ModelsPull,
            MessageType.ChatSend,
            MessageType.ChatCancel,
            MessageType.ChatSuggestionsRequest,
            "chat.attachments",
        )
        val SUCCESS_PULL_STATUSES = setOf("success", "succeeded", "installed", "complete", "completed", "ready", "ok")
        val ACCEPTED_PULL_STATUSES = setOf("accepted", "queued", "pending", "started", "pulling", "downloading", "installing", "in_progress")
        val FAILED_PULL_STATUSES = setOf("failed", "failure", "error", "cancelled", "canceled")
    }
}

private val EMBEDDING_MODEL_NAME_HINTS = setOf(
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
)

private data class AttachmentMetadata(
    val name: String,
    val mimeType: String,
    val sizeBytes: Long,
)

private fun attachmentType(mimeType: String, name: String): String {
    val normalizedMimeType = mimeType.lowercase()
    val extension = name.substringAfterLast('.', "").lowercase()
    return if (normalizedMimeType.startsWith("image/") || extension in IMAGE_EXTENSIONS) {
        "image"
    } else {
        "document"
    }
}

private fun mimeTypeFromName(name: String): String {
    return when (name.substringAfterLast('.', "").lowercase()) {
        "png" -> "image/png"
        "jpg", "jpeg" -> "image/jpeg"
        "webp" -> "image/webp"
        "gif" -> "image/gif"
        "pdf" -> "application/pdf"
        "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        "docm" -> "application/vnd.ms-word.document.macroenabled.12"
        "dotx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.template"
        "dotm" -> "application/vnd.ms-word.template.macroenabled.12"
        "doc" -> "application/msword"
        "hwpx" -> "application/hwp+zip"
        "odt" -> "application/vnd.oasis.opendocument.text"
        "ods" -> "application/vnd.oasis.opendocument.spreadsheet"
        "odp" -> "application/vnd.oasis.opendocument.presentation"
        "xlsx" -> "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        "xlsm" -> "application/vnd.ms-excel.sheet.macroenabled.12"
        "xltx" -> "application/vnd.openxmlformats-officedocument.spreadsheetml.template"
        "xltm" -> "application/vnd.ms-excel.template.macroenabled.12"
        "xls", "xlt" -> "application/vnd.ms-excel"
        "pptx" -> "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        "pptm" -> "application/vnd.ms-powerpoint.presentation.macroenabled.12"
        "ppsx" -> "application/vnd.openxmlformats-officedocument.presentationml.slideshow"
        "ppsm" -> "application/vnd.ms-powerpoint.slideshow.macroenabled.12"
        "potx" -> "application/vnd.openxmlformats-officedocument.presentationml.template"
        "potm" -> "application/vnd.ms-powerpoint.template.macroenabled.12"
        "ppt", "pps", "pot" -> "application/vnd.ms-powerpoint"
        "hwp" -> "application/x-hwp"
        "epub" -> "application/epub+zip"
        "pages" -> "application/vnd.apple.pages"
        "numbers" -> "application/vnd.apple.numbers"
        "key" -> "application/vnd.apple.keynote"
        "webarchive" -> "application/x-webarchive"
        "rtf" -> "application/rtf"
        "html", "htm" -> "text/html"
        "xml" -> "application/xml"
        "md", "markdown" -> "text/markdown"
        "rst" -> "text/x-rst"
        "adoc", "asciidoc" -> "text/asciidoc"
        "log" -> "text/x-log"
        "text", "conf", "ini", "toml", "properties", "env" -> "text/plain"
        "csv" -> "text/csv"
        "tsv" -> "text/tab-separated-values"
        "json" -> "application/json"
        "jsonl" -> "application/x-ndjson"
        "yaml", "yml" -> "application/yaml"
        "txt" -> "text/plain"
        else -> "application/octet-stream"
    }
}

private val IMAGE_EXTENSIONS = setOf("png", "jpg", "jpeg", "webp", "gif")

private fun providerFromQualifiedId(qualifiedId: String?): String? {
    val value = qualifiedId?.takeIf(String::isNotBlank) ?: return null
    return when {
        value.startsWith("lm_studio:") -> "lm_studio"
        value.startsWith("ollama:") -> "ollama"
        else -> null
    }
}

private fun providerModelIdFromQualifiedId(qualifiedId: String?, provider: String): String? {
    val value = qualifiedId?.takeIf(String::isNotBlank) ?: return null
    val prefix = "$provider:"
    return value.takeIf { it.startsWith(prefix) }?.removePrefix(prefix)
}

private fun qualifyModelId(provider: String, modelId: String): String {
    return if (modelId.startsWith("$provider:")) modelId else "$provider:$modelId"
}

internal enum class SelectedModelSendState {
    Ready,
    Missing,
    NotInstalled,
}

internal fun runtimeProviderStatuses(payload: RuntimeHealthPayload): List<RuntimeProviderStatus> {
    return listOfNotNull(
        payload.ollama?.let { status ->
            RuntimeProviderStatus(
                id = "ollama",
                name = "Ollama",
                available = status.available,
                message = status.message,
                code = status.code,
                retryable = status.retryable,
            )
        },
        payload.lmStudio?.let { status ->
            RuntimeProviderStatus(
                id = "lm_studio",
                name = "LM Studio",
                available = status.available,
                message = status.message,
                code = status.code,
                retryable = status.retryable,
            )
        },
    )
}

internal fun trustedRuntimeConnectionTarget(state: RuntimeUiState): RuntimeConnectionTarget? {
    val trustedMac = state.trustedMac ?: return null
    return RuntimeConnectionTarget(
        identity = PairedRuntimeIdentity(
            deviceId = trustedMac.deviceId,
            name = trustedMac.name,
            fingerprint = trustedMac.fingerprint,
            routeToken = trustedMac.routeToken,
        ),
        endpointHint = trustedMac.endpointHint,
    )
}

internal fun runtimeRouteCandidates(
    state: RuntimeUiState,
    target: RuntimeConnectionTarget,
): List<RuntimeRouteCandidate> {
    val routes = mutableListOf<RuntimeRouteCandidate>()
    val seenEndpoints = mutableSetOf<Pair<String, Int>>()

    val identity = target.identity
    if (identity != null) {
        state.selectedRouteEndpointHintOrNull()?.let { endpoint ->
            val key = endpoint.host to endpoint.port
            if (state.isTrustedRouteEndpointAllowed(endpoint, identity) && seenEndpoints.add(key)) {
                routes += RuntimeRouteCandidate.DirectTcp(
                    hint = endpoint,
                    source = endpoint.routeSource(),
                )
            }
        }
        state.discoveredMacs.forEach { discovered ->
            val key = discovered.host to discovered.port
            if (discovered.matchesTrustedIdentity(identity, allowMissingMetadata = false) && seenEndpoints.add(key)) {
                routes += RuntimeRouteCandidate.DirectTcp(
                    hint = RuntimeEndpointHint(
                        host = discovered.host,
                        port = discovered.port,
                        source = RuntimeEndpointSource.BonjourDiscovery,
                    ),
                    source = RuntimeRouteSource.FreshDiscovery,
                )
            }
        }
    }

    target.endpointHint?.let { endpoint ->
        val key = endpoint.host to endpoint.port
        if (seenEndpoints.add(key)) {
            routes += RuntimeRouteCandidate.DirectTcp(
                hint = endpoint,
                source = endpoint.routeSource(),
            )
        }
    }

    target.identity?.let { identity ->
        routes += RuntimeRouteCandidate.LocalDirect(identity)
        routes += RuntimeRouteCandidate.PeerToPeer(identity)
        routes += RuntimeRouteCandidate.Relay(identity)
    }

    return routes
}

private fun RuntimeUiState.selectedRouteEndpointHintOrNull(): RuntimeEndpointHint? {
    val source = macEndpointSource
    if (source == RuntimeEndpointSource.Manual || source == RuntimeEndpointSource.TrustedLastKnown) {
        return null
    }
    val port = macPort.toIntOrNull()?.takeIf { it in 1..65535 } ?: return null
    val host = macHost.takeIf { it.isNotBlank() } ?: return null
    return RuntimeEndpointHint(
        host = host,
        port = port,
        source = source,
    )
}

private fun RuntimeUiState.isTrustedRouteEndpointAllowed(
    endpoint: RuntimeEndpointHint,
    identity: PairedRuntimeIdentity,
): Boolean {
    if (endpoint.source != RuntimeEndpointSource.BonjourDiscovery) {
        return true
    }
    val discovered = discoveredMacs.firstOrNull { it.host == endpoint.host && it.port == endpoint.port }
        ?: return true
    return discovered.matchesTrustedIdentity(identity, allowMissingMetadata = true)
}

private fun RuntimeDiscoveredMac.matchesTrustedIdentity(
    identity: PairedRuntimeIdentity,
    allowMissingMetadata: Boolean,
): Boolean {
    val advertisedDeviceId = deviceId.normalizedIdentityOrNull()
    val advertisedFingerprint = fingerprint.normalizedIdentityOrNull()
    val advertisedRouteToken = routeToken.normalizedIdentityOrNull()
    if (advertisedRouteToken == null && advertisedDeviceId == null && advertisedFingerprint == null) {
        return allowMissingMetadata
    }
    val targetRouteToken = identity.routeToken.normalizedIdentityOrNull()
    if (advertisedRouteToken != null && targetRouteToken != null) {
        return advertisedRouteToken == targetRouteToken
    }
    val targetDeviceId = identity.deviceId.normalizedIdentityOrNull()
    val targetFingerprint = identity.fingerprint.normalizedIdentityOrNull()
    return advertisedDeviceId?.equals(targetDeviceId, ignoreCase = true) == true ||
        advertisedFingerprint?.equals(targetFingerprint, ignoreCase = true) == true
}

private fun String?.normalizedIdentityOrNull(): String? {
    return this?.trim()?.takeIf { it.isNotEmpty() }
}

internal fun RuntimeConnectionFailure.toRuntimeUiError(): RuntimeUiError {
    return when (reason) {
        RuntimeConnectionFailureReason.NoRoutesResolved ->
            RuntimeUiError("no_route", message)
        RuntimeConnectionFailureReason.NoConnectableRoute ->
            RuntimeUiError("no_connectable_route", message)
        RuntimeConnectionFailureReason.RouteAttemptsFailed ->
            RuntimeUiError("connection_failed", message)
    }
}

private fun Throwable.connectionUiError(): RuntimeUiError {
    return when (this) {
        is RuntimeConnectionFailure -> toRuntimeUiError()
        else -> RuntimeUiError("connection_failed", message)
    }
}

private fun RuntimeConnectionTarget.connectionLogLabel(): String {
    val endpoint = endpointHint
    val endpointLabel = if (endpoint == null) {
        "endpoint=unresolved"
    } else {
        "endpoint=${endpoint.host}:${endpoint.port} source=${endpoint.source}"
    }
    return "$endpointLabel identity=${identity?.deviceId}"
}

private fun RuntimeEndpointHint.routeSource(): RuntimeRouteSource {
    return when (source) {
        RuntimeEndpointSource.TrustedLastKnown -> RuntimeRouteSource.TrustedLastKnownEndpoint
        RuntimeEndpointSource.PairingQr -> RuntimeRouteSource.EndpointHint
        RuntimeEndpointSource.BonjourDiscovery -> RuntimeRouteSource.FreshDiscovery
        RuntimeEndpointSource.UsbReverse -> RuntimeRouteSource.FreshDiscovery
        RuntimeEndpointSource.Emulator -> RuntimeRouteSource.EndpointHint
        RuntimeEndpointSource.Manual -> RuntimeRouteSource.Manual
    }
}

private fun TrustedMac.lastKnownEndpointHintOrNull(): RuntimeEndpointHint? {
    val endpointHost = host ?: return null
    val endpointPort = port ?: return null
    return RuntimeEndpointHint(
        host = endpointHost,
        port = endpointPort,
        source = RuntimeEndpointSource.TrustedLastKnown,
    )
}

private fun TrustedMac.toConnectionTarget(): RuntimeConnectionTarget {
    return RuntimeConnectionTarget(
        identity = PairedRuntimeIdentity(
            deviceId = deviceId,
            name = name,
            fingerprint = fingerprint,
            routeToken = routeToken,
        ),
        endpointHint = lastKnownEndpointHintOrNull(),
    )
}

private fun MacPairingPayload.endpointHintOrNull(): RuntimeEndpointHint? {
    val endpointHost = host ?: return null
    val endpointPort = port ?: return null
    return RuntimeEndpointHint(
        host = endpointHost,
        port = endpointPort,
        source = RuntimeEndpointSource.PairingQr,
    )
}

private fun MacPairingPayload.toConnectionTarget(): RuntimeConnectionTarget? {
    val endpoint = endpointHintOrNull() ?: return null
    return RuntimeConnectionTarget(
        identity = PairedRuntimeIdentity(
            deviceId = macDeviceId,
            name = macName,
            fingerprint = fingerprint,
            routeToken = routeToken,
        ),
        endpointHint = endpoint,
    )
}

internal fun RuntimeUiState.selectedModelSendState(): SelectedModelSendState {
    val selectedId = selectedModelId ?: return SelectedModelSendState.Missing
    val selectedModel = models.firstOrNull { it.id == selectedId }
        ?: return SelectedModelSendState.Missing
    return if (!selectedModel.isChatModel()) {
        SelectedModelSendState.Missing
    } else if (selectedModel.installed) {
        SelectedModelSendState.Ready
    } else {
        SelectedModelSendState.NotInstalled
    }
}

internal fun RuntimeModel.isChatModel(): Boolean {
    return modelKind == MODEL_KIND_CHAT || capabilities.any { it == "chat" || it == "completion" || it == "vision" || it == "image" }
}

internal fun RuntimeModel.isEmbeddingModel(): Boolean {
    return modelKind == MODEL_KIND_EMBEDDING || capabilities.any { it == "embedding" || it == "embed" }
}

internal fun RuntimeModel.supportsImageInput(): Boolean {
    return isChatModel() && capabilities.any { it == "vision" || it == "image" || it == "multimodal" }
}

internal fun normalizeModelKind(
    kind: String?,
    capabilities: List<String>,
    id: String,
    name: String,
): String {
    val normalizedKind = kind?.trim()?.lowercase()
    if (normalizedKind == MODEL_KIND_EMBEDDING || normalizedKind == "embed" || normalizedKind == "embeddings") {
        return MODEL_KIND_EMBEDDING
    }
    if (
        normalizedKind == MODEL_KIND_CHAT ||
        normalizedKind == "llm" ||
        normalizedKind == "completion" ||
        normalizedKind == "text" ||
        normalizedKind == "vision" ||
        normalizedKind == "vl" ||
        normalizedKind == "multimodal"
    ) {
        return MODEL_KIND_CHAT
    }
    if (capabilities.any { it == "embedding" || it == "embed" }) {
        return MODEL_KIND_EMBEDDING
    }
    if (capabilities.any { it == "chat" || it == "completion" || it == "vision" || it == "image" || it == "multimodal" }) {
        return MODEL_KIND_CHAT
    }
    return if (looksLikeEmbeddingModel(id) || looksLikeEmbeddingModel(name)) {
        MODEL_KIND_EMBEDDING
    } else {
        MODEL_KIND_CHAT
    }
}

internal fun defaultCapabilitiesForModelKind(modelKind: String): List<String> {
    return if (modelKind == MODEL_KIND_EMBEDDING) listOf("embedding") else listOf("chat")
}

private fun looksLikeEmbeddingModel(value: String): Boolean {
    val lower = value.lowercase()
    return EMBEDDING_MODEL_NAME_HINTS.any { hint -> lower.contains(hint) }
}

internal fun RuntimeUiState.withChatDelta(
    envelope: ProtocolEnvelope,
    payload: ChatDeltaPayload,
): RuntimeUiState {
    if (activeRequestId != envelope.requestId) return this
    if (payload.content.isEmpty() && payload.reasoning.isEmpty()) return this

        val updated = messages.toMutableList()
        val index = updated.indexOfLast { it.role == "assistant" }
        if (index >= 0) {
            val item = updated[index]
            updated[index] = item.copy(
                content = item.content + payload.content,
                reasoning = item.reasoning + payload.reasoning,
                suggestions = emptyList(),
            )
        }
        return copy(messages = updated)
    }

internal fun RuntimeUiState.withChatDone(
    envelope: ProtocolEnvelope,
    payload: ChatDonePayload?,
): RuntimeUiState {
    if (activeRequestId != envelope.requestId) return this
    return copy(
        messages = messages.withoutTrailingBlankAssistantPlaceholder(),
        isStreaming = false,
        activeRequestId = null,
        error = if (payload?.finishReason == "cancelled") RuntimeUiError("generation_cancelled") else error,
        )
    }

internal fun RuntimeUiState.withChatSuggestions(suggestions: List<String>): RuntimeUiState {
    val updated = messages.toMutableList()
    val index = updated.indexOfLast { it.role == "assistant" && it.content.isNotBlank() }
    if (index < 0) return this
    val cleanedSuggestions = suggestions.cleanedSuggestions()
    updated[index] = updated[index].copy(suggestions = cleanedSuggestions)
    return copy(messages = updated)
}

internal fun RuntimeUiState.withChatCancelAck(
    envelope: ProtocolEnvelope,
    payload: ChatCancelPayload?,
): RuntimeUiState {
    val activeRequestId = activeRequestId ?: return this
    if (envelope.requestId != activeRequestId && payload?.targetRequestId != activeRequestId) {
        return this
    }
    return copy(
        messages = messages.withoutTrailingBlankAssistantPlaceholder(),
        isStreaming = false,
        activeRequestId = null,
        error = null,
    )
}

internal fun RuntimeUiState.withRuntimeError(
    envelope: ProtocolEnvelope,
    payload: ErrorPayload?,
    pendingModelPullRequestId: String?,
): RuntimeUiState {
    val isActiveChatError = activeRequestId == envelope.requestId
    val isModelPullError = pendingModelPullRequestId == envelope.requestId
    return copy(
        messages = if (isActiveChatError) {
            messages.withoutTrailingBlankAssistantPlaceholder()
        } else {
            messages
        },
        isStreaming = if (isActiveChatError) false else isStreaming,
        isLoadingSuggestions = if (isActiveChatError) false else isLoadingSuggestions,
        activeRequestId = if (isActiveChatError) null else activeRequestId,
        isLoadingModels = false,
        installingModelId = if (isModelPullError) null else installingModelId,
        error = payload?.let { error -> RuntimeUiError(error.code, error.message) }
            ?: RuntimeUiError("runtime_error"),
    )
}

private fun List<RuntimeChatMessage>.withoutTrailingBlankAssistantPlaceholder(): List<RuntimeChatMessage> {
    val trailingMessage = lastOrNull()
    return if (
        trailingMessage?.role == "assistant" &&
        trailingMessage.content.isBlank() &&
        trailingMessage.reasoning.isBlank()
    ) {
        dropLast(1)
    } else {
        this
    }
}
