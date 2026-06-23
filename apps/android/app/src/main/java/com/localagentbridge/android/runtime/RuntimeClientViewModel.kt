package com.localagentbridge.android.runtime

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.localagentbridge.android.core.protocol.AuthChallengePayload
import com.localagentbridge.android.core.protocol.AuthResponsePayload
import com.localagentbridge.android.core.protocol.ChatCancelPayload
import com.localagentbridge.android.core.protocol.ChatDeltaPayload
import com.localagentbridge.android.core.protocol.ChatDonePayload
import com.localagentbridge.android.core.protocol.ChatMessagePayload
import com.localagentbridge.android.core.protocol.ChatSendPayload
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
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException
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
    private val discovery = BonjourDiscovery(application)
    private val pairingStore = PairingStore(application)
    private val deviceIdentityStore = DeviceIdentityStore(application)
    private var readJob: Job? = null
    private var discoveryJob: Job? = null
    private var pendingPairingPayload: MacPairingPayload? = null
    private var pendingModelPullRequestId: String? = null
    private var modelIdToSelectAfterRefresh: String? = null
    private var isSessionAuthenticated = false
    private val chatSessionId = UUID.randomUUID().toString()

    private val mutableState = MutableStateFlow(RuntimeUiState())
    val state: StateFlow<RuntimeUiState> = mutableState.asStateFlow()

    init {
        viewModelScope.launch {
            pairingStore.trustedMac.collect { trusted ->
                mutableState.update {
                    if (trusted == null) {
                        it.copy(trustedMac = null)
                    } else {
                        it.copy(
                            trustedMac = RuntimeTrustedMac(
                                deviceId = trusted.deviceId,
                                name = trusted.name,
                                host = trusted.host,
                                port = trusted.port,
                            ),
                            macHost = trusted.host,
                            macPort = trusted.port.toString(),
                        )
                    }
                }
            }
        }
    }

    fun updateHost(value: String) {
        mutableState.update { it.copy(macHost = value.trim()) }
    }

    fun updatePort(value: String) {
        mutableState.update { it.copy(macPort = value.filter(Char::isDigit).take(5)) }
    }

    fun useUsbReverseEndpoint() {
        mutableState.update {
            it.copy(
                macHost = "127.0.0.1",
                macPort = "43170",
                error = null,
            )
        }
    }

    fun useEmulatorEndpoint() {
        mutableState.update {
            it.copy(
                macHost = "10.0.2.2",
                macPort = "43170",
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

    fun connectToTrustedRuntime() {
        viewModelScope.launch {
            val trustedMac = state.value.trustedMac
            if (trustedMac == null) {
                showError("pairing_required")
                return@launch
            }

            connectToRuntime(trustedMac.host, trustedMac.port)
        }
    }

    fun trustMacFromPairingQr(rawValue: String) {
        viewModelScope.launch {
            val payload = runCatching { MacPairingPayloadParser.parse(rawValue) }
                .onFailure { error -> showError("invalid_pairing_qr", error.message) }
                .getOrNull()
                ?: return@launch

            pendingPairingPayload = payload
            mutableState.update {
                it.copy(
                    pairingCode = payload.pairingCode,
                    macHost = payload.host,
                    macPort = payload.port.toString(),
                    error = null,
                )
            }
            if (connectToRuntime(payload.host, payload.port, requestHealthAfterConnect = false)) {
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
                error = null,
            )
        }
    }

    fun forgetTrustedMac() {
        viewModelScope.launch {
            pairingStore.forgetMac()
            mutableState.update { it.copy(error = null) }
        }
    }

    fun disconnect() {
        readJob?.cancel()
        readJob = null
        client.close()
        isSessionAuthenticated = false
        pendingModelPullRequestId = null
        modelIdToSelectAfterRefresh = null
        mutableState.update {
            it.copy(
                isConnected = false,
                isConnecting = false,
                isStreaming = false,
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
        if (model != null && !model.installed) {
            requestModelInstall(modelId)
            return
        }
        mutableState.update { it.copy(selectedModelId = modelId) }
    }

    fun requestModelInstall(modelId: String) {
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }

        val model = state.value.models.firstOrNull { it.id == modelId }
        if (model?.installed == true) {
            mutableState.update { it.copy(selectedModelId = modelId) }
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
        val model = current.selectedModelId
        if (text.isEmpty()) return
        if (model == null) {
            showError("select_model")
            return
        }
        if (current.models.any { it.id == model && !it.installed }) {
            showError("install_model_first")
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

        val requestId = UUID.randomUUID().toString()
        val userMessage = RuntimeChatMessage(role = "user", content = text)
        val assistantMessage = RuntimeChatMessage(role = "assistant", content = "")
        mutableState.update {
            it.copy(
                chatInput = "",
                messages = it.messages + userMessage + assistantMessage,
                activeRequestId = requestId,
                isStreaming = true,
                error = null
            )
        }

        sendEnvelope(
            envelope(
                type = MessageType.ChatSend,
                requestId = requestId,
                serializer = ChatSendPayload.serializer(),
                payload = ChatSendPayload(
                    sessionId = chatSessionId,
                    model = model,
                    messages = (current.messages + userMessage)
                        .filter { it.role == "user" || it.role == "assistant" }
                        .filter { it.content.isNotBlank() }
                        .map { ChatMessagePayload(role = it.role, content = it.content) }
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
            Log.d(TAG, "Connecting to Mac runtime $host:$port")
            client.connect(host, port)
        }.onSuccess {
            Log.d(TAG, "Connected to Mac runtime $host:$port")
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
            Log.e(TAG, "Mac runtime connection failed", error)
            mutableState.update {
                it.copy(
                    isConnected = false,
                    isConnecting = false,
                    runtimeStatus = "failed",
                    error = RuntimeUiError("connection_failed", error.message),
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
                            Log.e(TAG, "Mac runtime receive failed", error)
                            isSessionAuthenticated = false
                            mutableState.update {
                                it.copy(
                                    isConnected = false,
                                    isStreaming = false,
                                    installingModelId = null,
                                    activeRequestId = null,
                                    runtimeStatus = "disconnected",
                                    error = RuntimeUiError("receive_failed", error.message)
                                )
                            }
                        }
                        return@launch
                    }
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
            val trusted = TrustedMac(
                deviceId = payload.macDeviceId ?: pending.macDeviceId,
                name = pending.macName,
                fingerprint = pending.fingerprint,
                host = pending.host,
                port = pending.port,
            )
            pairingStore.trustMac(trusted)
            pendingPairingPayload = null
            isSessionAuthenticated = true
            mutableState.update {
                it.copy(
                    trustedMac = RuntimeTrustedMac(
                        deviceId = trusted.deviceId,
                        name = trusted.name,
                        host = trusted.host,
                        port = trusted.port,
                    ),
                    macHost = trusted.host,
                    macPort = trusted.port.toString(),
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
        val providerStatuses = listOfNotNull(
            payload.ollama?.let { RuntimeProviderStatus("ollama", "Ollama", it.available) },
            payload.lmStudio?.let { RuntimeProviderStatus("lm_studio", "LM Studio", it.available) },
        )
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
            RuntimeModel(
                id = modelId,
                name = it.name?.takeIf(String::isNotBlank) ?: it.id,
                backend = it.backend ?: provider,
                provider = provider,
                providerModelId = providerModelId,
                installed = it.installed ?: true,
                running = it.running ?: false,
                source = it.source,
                description = it.description,
                sizeBytes = it.sizeBytes,
            )
        }
        mutableState.update { current ->
            val installTarget = modelIdToSelectAfterRefresh
            val installedTarget = installTarget?.let { target ->
                models.firstOrNull { it.id == target && it.installed }
            }
            val selectedModelId = when {
                installedTarget != null -> installedTarget.id
                current.selectedModelId != null && models.any { it.id == current.selectedModelId && it.installed } -> current.selectedModelId
                else -> models.firstOrNull { it.installed }?.id
            }
            if (installedTarget != null) {
                modelIdToSelectAfterRefresh = null
            }
            val stillInstalling = current.installingModelId?.takeIf { installingId ->
                models.none { it.id == installingId && it.installed }
            }
            current.copy(
                models = models,
                isLoadingModels = false,
                installingModelId = stillInstalling,
                selectedModelId = selectedModelId,
                error = null
            )
        }
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
        if (payload.content.isEmpty()) return
        mutableState.update { current ->
            val updated = current.messages.toMutableList()
            val index = updated.indexOfLast { it.role == "assistant" }
            if (index >= 0) {
                val item = updated[index]
                updated[index] = item.copy(content = item.content + payload.content)
            }
            current.copy(messages = updated)
        }
    }

    private fun handleChatDone(envelope: ProtocolEnvelope) {
        if (!isActiveChatEnvelope(envelope)) return
        val payload = decodePayload(ChatDonePayload.serializer(), envelope.payload)
        mutableState.update {
            it.copy(
                isStreaming = false,
                activeRequestId = null,
                error = if (payload?.finishReason == "cancelled") RuntimeUiError("generation_cancelled") else it.error
            )
        }
    }

    private fun handleCancelAck(envelope: ProtocolEnvelope) {
        val activeRequestId = state.value.activeRequestId ?: return
        if (envelope.requestId != activeRequestId) {
            if (envelope.payload.isEmpty()) return
            val payload = decodePayload(ChatCancelPayload.serializer(), envelope.payload) ?: return
            if (payload.targetRequestId != activeRequestId) return
        }
        mutableState.update {
            it.copy(
                isStreaming = false,
                activeRequestId = null,
                error = null
            )
        }
    }

    private fun handleError(envelope: ProtocolEnvelope) {
        val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
        val isModelPullError = pendingModelPullRequestId == envelope.requestId
        val isActiveChatError = state.value.activeRequestId == envelope.requestId
        if (isModelPullError) {
            modelIdToSelectAfterRefresh = null
        }
        mutableState.update {
            it.copy(
                isStreaming = if (isActiveChatError) false else it.isStreaming,
                activeRequestId = if (isActiveChatError) null else it.activeRequestId,
                isLoadingModels = false,
                installingModelId = if (isModelPullError) null else it.installingModelId,
                error = payload?.let { error -> RuntimeUiError(error.code, error.message) }
                    ?: RuntimeUiError("runtime_error")
            )
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
                    Log.e(TAG, "Mac runtime send failed", error)
                    mutableState.update {
                        it.copy(
                            isConnected = client.isConnected,
                            isStreaming = false,
                            isLoadingModels = false,
                            installingModelId = null,
                            activeRequestId = null,
                            error = RuntimeUiError("send_failed", error.message)
                        )
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
        val CLIENT_CAPABILITIES = listOf(
            MessageType.RuntimeHealth,
            MessageType.ModelsList,
            MessageType.ModelsPull,
            MessageType.ChatSend,
            MessageType.ChatCancel,
        )
        val SUCCESS_PULL_STATUSES = setOf("success", "succeeded", "installed", "complete", "completed", "ready", "ok")
        val ACCEPTED_PULL_STATUSES = setOf("accepted", "queued", "pending", "started", "pulling", "downloading", "installing", "in_progress")
        val FAILED_PULL_STATUSES = setOf("failed", "failure", "error", "cancelled", "canceled")
    }
}

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
