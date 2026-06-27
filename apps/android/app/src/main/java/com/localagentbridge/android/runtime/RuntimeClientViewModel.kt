package com.localagentbridge.android.runtime

import android.app.Application
import android.app.Activity
import android.content.Context
import android.content.res.Configuration
import android.net.Uri
import android.os.Bundle
import android.os.LocaleList
import android.provider.OpenableColumns
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.localagentbridge.android.BuildConfig
import com.localagentbridge.android.R
import com.localagentbridge.android.core.protocol.AuthChallengePayload
import com.localagentbridge.android.core.protocol.AuthResponsePayload
import com.localagentbridge.android.core.protocol.ChatAttachmentPayload
import com.localagentbridge.android.core.protocol.ChatCancelPayload
import com.localagentbridge.android.core.protocol.ChatDeltaPayload
import com.localagentbridge.android.core.protocol.ChatDonePayload
import com.localagentbridge.android.core.protocol.ChatMessagePayload
import com.localagentbridge.android.core.protocol.ChatMessagesListRequestPayload
import com.localagentbridge.android.core.protocol.ChatMessagesListResultPayload
import com.localagentbridge.android.core.protocol.ChatSessionLifecyclePayload
import com.localagentbridge.android.core.protocol.ChatSessionRenamePayload
import com.localagentbridge.android.core.protocol.ChatSendPayload
import com.localagentbridge.android.core.protocol.ChatSessionsListRequestPayload
import com.localagentbridge.android.core.protocol.ChatSessionsListResultPayload
import com.localagentbridge.android.core.protocol.ChatSuggestionsRequestPayload
import com.localagentbridge.android.core.protocol.ChatSuggestionsResultPayload
import com.localagentbridge.android.core.protocol.ChatTitleRequestPayload
import com.localagentbridge.android.core.protocol.ChatTitleResultPayload
import com.localagentbridge.android.core.protocol.ErrorPayload
import com.localagentbridge.android.core.protocol.HelloPayload
import com.localagentbridge.android.core.protocol.MemoryDeletePayload
import com.localagentbridge.android.core.protocol.MemoryDeleteResultPayload
import com.localagentbridge.android.core.protocol.MemoryListResultPayload
import com.localagentbridge.android.core.protocol.MemoryUpsertPayload
import com.localagentbridge.android.core.protocol.MemoryUpsertResultPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.ModelPullPayload
import com.localagentbridge.android.core.protocol.ModelPullResultPayload
import com.localagentbridge.android.core.protocol.ModelsResultPayload
import com.localagentbridge.android.core.protocol.PairingRequestPayload
import com.localagentbridge.android.core.protocol.PairingResultPayload
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.RouteRefreshPayload
import com.localagentbridge.android.core.protocol.RuntimeHealthPayload
import com.localagentbridge.android.core.pairing.DeviceIdentity
import com.localagentbridge.android.core.pairing.DeviceIdentityStore
import com.localagentbridge.android.core.pairing.RuntimePairingPayload
import com.localagentbridge.android.core.pairing.RuntimePairingPayloadParser
import com.localagentbridge.android.core.pairing.PairingStore
import com.localagentbridge.android.core.pairing.RuntimeIdentityProofVerifier
import com.localagentbridge.android.core.pairing.TrustedRuntime
import com.localagentbridge.android.core.transport.BonjourDiscovery
import com.localagentbridge.android.core.transport.DiscoveredRuntime
import com.localagentbridge.android.core.transport.RuntimeTransportClient
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.RuntimeConnectionFailure
import com.localagentbridge.android.core.transport.RuntimeConnectionFailureReason
import com.localagentbridge.android.core.transport.RuntimeConnectionManager
import com.localagentbridge.android.core.transport.RuntimeConnectionTarget
import com.localagentbridge.android.core.transport.RuntimeEndpointHint
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import com.localagentbridge.android.core.transport.RuntimeProtocolChannel
import com.localagentbridge.android.core.transport.RuntimeRelayConnector
import com.localagentbridge.android.core.transport.RuntimeRelayTcpClient
import com.localagentbridge.android.core.transport.RuntimeRouteCandidate
import com.localagentbridge.android.core.transport.RuntimeRouteCapability
import com.localagentbridge.android.core.transport.RuntimeRouteResolver
import com.localagentbridge.android.core.transport.RuntimeRouteRejectionReason
import com.localagentbridge.android.core.transport.RuntimeRouteSource
import com.localagentbridge.android.core.transport.RuntimeTransportConnector
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.Flow
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
import java.util.Base64
import java.util.Locale
import java.util.UUID

internal interface RuntimeTrustedRuntimeStore {
    val trustedRuntime: Flow<TrustedRuntime?>
    suspend fun trustRuntime(runtime: TrustedRuntime)
    suspend fun forgetRuntime()
}

internal interface RuntimeDeviceIdentityProvider {
    suspend fun loadOrCreate(): DeviceIdentity
}

internal interface RuntimeDiscoverySource {
    fun discover(): Flow<List<DiscoveredRuntime>>
}

internal interface RuntimeLocalDataStore {
    fun load(): PersistedRuntimeData
    fun save(data: PersistedRuntimeData)
}

internal interface RuntimeLifecycleCallbacksRegistrar {
    fun register(application: Application, callbacks: Application.ActivityLifecycleCallbacks)
    fun unregister(application: Application, callbacks: Application.ActivityLifecycleCallbacks)
}

internal data class RuntimeAttachmentMetadata(
    val name: String,
    val mimeType: String,
    val sizeBytes: Long,
)

internal interface RuntimeAttachmentReader {
    fun metadata(reference: String): RuntimeAttachmentMetadata
    fun readBytes(reference: String): ByteArray?
}

internal data class RuntimeClientViewModelDependencies(
    val json: Json,
    val transportClient: RuntimeTransportClient,
    val transportConnector: RuntimeTransportConnector,
    val relayConnector: RuntimeRelayConnector,
    val discovery: RuntimeDiscoverySource,
    val trustedRuntimeStore: RuntimeTrustedRuntimeStore,
    val deviceIdentityProvider: RuntimeDeviceIdentityProvider,
    val localDataStore: RuntimeLocalDataStore,
    val lifecycleCallbacksRegistrar: RuntimeLifecycleCallbacksRegistrar,
    val attachmentReader: RuntimeAttachmentReader? = null,
    val attachmentPromptHeaderProvider: ((String) -> String)? = null,
    val currentTimeMillis: () -> Long = { System.currentTimeMillis() },
) {
    companion object {
        fun create(application: Application): RuntimeClientViewModelDependencies {
            val json = runtimeClientJson()
            val transportClient = RuntimeTransportClient()
            return RuntimeClientViewModelDependencies(
                json = json,
                transportClient = transportClient,
                transportConnector = RuntimeTransportConnector { host, port, timeoutMillis ->
                    transportClient.connect(host = host, port = port, timeoutMillis = timeoutMillis)
                },
                relayConnector = RuntimeRelayTcpClient(),
                discovery = AndroidRuntimeDiscoverySource(BonjourDiscovery(application)),
                trustedRuntimeStore = AndroidTrustedRuntimeStore(PairingStore(application)),
                deviceIdentityProvider = AndroidDeviceIdentityProvider(DeviceIdentityStore(application)),
                localDataStore = AndroidRuntimeLocalDataStore(RuntimeLocalStore(application, json)),
                lifecycleCallbacksRegistrar = AndroidRuntimeLifecycleCallbacksRegistrar,
                attachmentReader = AndroidRuntimeAttachmentReader(application),
                attachmentPromptHeaderProvider = { languageTag ->
                    attachmentOnlyPromptHeader(application, languageTag)
                },
            )
        }
    }
}

private class AndroidTrustedRuntimeStore(
    private val store: PairingStore,
) : RuntimeTrustedRuntimeStore {
    override val trustedRuntime: Flow<TrustedRuntime?> = store.trustedRuntime

    override suspend fun trustRuntime(runtime: TrustedRuntime) {
        store.trustRuntime(runtime)
    }

    override suspend fun forgetRuntime() {
        store.forgetRuntime()
    }
}

private class AndroidDeviceIdentityProvider(
    private val store: DeviceIdentityStore,
) : RuntimeDeviceIdentityProvider {
    override suspend fun loadOrCreate(): DeviceIdentity = store.loadOrCreate()
}

private class AndroidRuntimeDiscoverySource(
    private val discovery: BonjourDiscovery,
) : RuntimeDiscoverySource {
    override fun discover(): Flow<List<DiscoveredRuntime>> = discovery.discover()
}

private class AndroidRuntimeLocalDataStore(
    private val store: RuntimeLocalStore,
) : RuntimeLocalDataStore {
    override fun load(): PersistedRuntimeData = store.load()

    override fun save(data: PersistedRuntimeData) {
        store.save(data)
    }
}

private object AndroidRuntimeLifecycleCallbacksRegistrar : RuntimeLifecycleCallbacksRegistrar {
    override fun register(application: Application, callbacks: Application.ActivityLifecycleCallbacks) {
        application.registerActivityLifecycleCallbacks(callbacks)
    }

    override fun unregister(application: Application, callbacks: Application.ActivityLifecycleCallbacks) {
        application.unregisterActivityLifecycleCallbacks(callbacks)
    }
}

private class AndroidRuntimeAttachmentReader(
    private val application: Application,
) : RuntimeAttachmentReader {
    override fun metadata(reference: String): RuntimeAttachmentMetadata {
        val uri = Uri.parse(reference)
        val resolver = application.contentResolver
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
        return RuntimeAttachmentMetadata(name = name, mimeType = mimeType, sizeBytes = sizeBytes)
    }

    override fun readBytes(reference: String): ByteArray? {
        val uri = Uri.parse(reference)
        val resolver = application.contentResolver
        return runCatching {
            resolver.openInputStream(uri)?.use { input -> input.readBytes() }
        }.getOrNull()
    }
}

private fun runtimeClientJson(): Json = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
    encodeDefaults = true
}

internal val RUNTIME_CLIENT_CAPABILITIES = listOf(
    MessageType.RuntimeHealth,
    MessageType.ModelsList,
    MessageType.ModelsPull,
    MessageType.RouteRefresh,
    MessageType.ChatSend,
    MessageType.ChatCancel,
    MessageType.ChatSessionsList,
    MessageType.ChatMessagesList,
    MessageType.ChatSuggestionsRequest,
    MessageType.ChatTitleRequest,
    MessageType.ChatSessionRename,
    MessageType.ChatSessionArchive,
    MessageType.ChatSessionRestore,
    MessageType.ChatSessionDelete,
    MessageType.MemoryList,
    MessageType.MemoryUpsert,
    MessageType.MemoryDelete,
    "chat.attachments",
)

internal const val ROUTE_REFRESH_LEASE_RENEWAL_LEAD_MS = 60_000L
internal const val ROUTE_REFRESH_LEASE_MIN_DELAY_MS = 1_000L
internal const val ROUTE_REFRESH_RETRY_DELAY_MS = 10_000L

internal fun runtimeRouteRefreshLeaseDelayMillis(
    nowEpochMillis: Long,
    relayExpiresAtEpochMillis: Long?,
    renewalLeadMillis: Long = ROUTE_REFRESH_LEASE_RENEWAL_LEAD_MS,
    minimumDelayMillis: Long = ROUTE_REFRESH_LEASE_MIN_DELAY_MS,
): Long? {
    val expiresAt = relayExpiresAtEpochMillis ?: return null
    if (expiresAt <= nowEpochMillis) return null
    return maxOf(minimumDelayMillis, expiresAt - nowEpochMillis - renewalLeadMillis)
}

internal fun runtimeRouteRefreshRetryDelayMillis(
    nowEpochMillis: Long,
    relayExpiresAtEpochMillis: Long?,
    retryDelayMillis: Long = ROUTE_REFRESH_RETRY_DELAY_MS,
    minimumDelayMillis: Long = ROUTE_REFRESH_LEASE_MIN_DELAY_MS,
): Long? {
    val expiresAt = relayExpiresAtEpochMillis ?: return null
    val remainingMillis = expiresAt - nowEpochMillis
    if (remainingMillis <= minimumDelayMillis) return null
    return minOf(retryDelayMillis, remainingMillis - minimumDelayMillis)
        .coerceAtLeast(minimumDelayMillis)
}

class RuntimeClientViewModel internal constructor(
    application: Application,
    private val dependencies: RuntimeClientViewModelDependencies,
) : AndroidViewModel(application) {
    constructor(application: Application) : this(
        application = application,
        dependencies = RuntimeClientViewModelDependencies.create(application),
    )

    private val json = dependencies.json
    private val client = dependencies.transportClient
    private val connectionManager = RuntimeConnectionManager(
        connector = dependencies.transportConnector,
        routeResolver = RuntimeRouteResolver { target ->
            runtimeRouteCandidates(
                state = state.value,
                target = target,
                includeUsbReverseFallback = BuildConfig.DEBUG &&
                    state.value.runtimeEndpointSource == RuntimeEndpointSource.UsbReverse,
                suppressDirectRoutes = pendingPairingPayload
                    ?.takeIf { payload ->
                        target.identity?.let { identity -> payload.matchesIdentity(identity) } == true
                    }
                    ?.hasRelayRoute() == true,
            )
        },
        remoteRoutePreparer = RuntimeRemoteRoutePlanner(
            pendingPairingPayload = { pendingPairingPayload },
            trustedRuntime = { state.value.trustedRuntime },
            nowEpochMillis = dependencies.currentTimeMillis,
        ),
        relayConnector = dependencies.relayConnector,
        currentTimeMillis = dependencies.currentTimeMillis,
    )
    private val discovery = dependencies.discovery
    private val pairingStore = dependencies.trustedRuntimeStore
    private val deviceIdentityStore = dependencies.deviceIdentityProvider
    private val localStore = dependencies.localDataStore
    private val attachmentReader = dependencies.attachmentReader ?: AndroidRuntimeAttachmentReader(application)
    private var readJob: Job? = null
    private var discoveryJob: Job? = null
    private var reconnectJob: Job? = null
    private var routeRefreshLeaseJob: Job? = null
    private var activeChannel: RuntimeProtocolChannel? = null
    private var pendingPairingPayload: RuntimePairingPayload? = null
    private var pendingPairingRetryJob: Job? = null
    private var pendingPairingDiscoveryTimeoutJob: Job? = null
    private var pendingPairingRetryAttempts = 0
    private var pendingModelPullRequestId: String? = null
    private var pendingChatSessionsRequestId: String? = null
    private var pendingChatMessagesRequestId: String? = null
    private var pendingChatMessagesSessionId: String? = null
    private var pendingSuggestionRequestId: String? = null
    private var pendingSuggestionSessionId: String? = null
    private var pendingTitleRequestId: String? = null
    private var pendingTitleSessionId: String? = null
    private var pendingMemoryListRequestId: String? = null
    private var pendingRouteRefreshRequestId: String? = null
    private val pendingChatSessionLifecycleRequestIds = mutableSetOf<String>()
    private val pendingChatSessionRenameRequestIds = mutableSetOf<String>()
    private var modelIdToSelectAfterRefresh: String? = null
    private var isSessionAuthenticated = false
    private var persistedRuntimeData = PersistedRuntimeData()
    private var shouldRestoreTrustedRuntimeConnection = true
    private var didAttemptTrustedRuntimeRestore = false
    private val lifecycleCallbacks = object : Application.ActivityLifecycleCallbacks {
        override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) = Unit
        override fun onActivityStarted(activity: Activity) = Unit
        override fun onActivityResumed(activity: Activity) {
            restoreTrustedRuntimeConnection()
        }
        override fun onActivityPaused(activity: Activity) = Unit
        override fun onActivityStopped(activity: Activity) = Unit
        override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) = Unit
        override fun onActivityDestroyed(activity: Activity) = Unit
    }

    private val mutableState = MutableStateFlow(RuntimeUiState())
    val state: StateFlow<RuntimeUiState> = mutableState.asStateFlow()

    init {
        dependencies.lifecycleCallbacksRegistrar.register(application, lifecycleCallbacks)
        val loadedRuntimeData = localStore.load()
        shouldRestoreTrustedRuntimeConnection = loadedRuntimeData.trustedRuntimeAutoReconnectEnabled
        publishPersistedRuntimeData(loadedRuntimeData, save = false)
        restorePersistedPendingPairingRouteIfNeeded(loadedRuntimeData)
        viewModelScope.launch {
            pairingStore.trustedRuntime.collect { trusted ->
                mutableState.update {
                    if (trusted == null) {
                        it.copy(trustedRuntime = null)
                    } else {
                        val endpoint = trusted.lastKnownEndpointHintOrNull()
                        val runtime = RuntimeTrustedRuntime(
                            deviceId = trusted.deviceId,
                            name = trusted.name,
                            fingerprint = trusted.fingerprint,
                            publicKeyBase64 = trusted.publicKeyBase64,
                            routeToken = trusted.routeToken,
                            endpointHint = endpoint,
                            relayHost = trusted.relayHost,
                            relayPort = trusted.relayPort,
                            relayId = trusted.relayId,
                            relaySecret = trusted.relaySecret,
                            relayExpiresAtEpochMillis = trusted.relayExpiresAtEpochMillis,
                            relayNonce = trusted.relayNonce,
                            relayScope = trusted.relayScope,
                        )
                        it.withTrustedRuntimeRouteFields(runtime, endpoint)
                    }
                }
                if (
                    trusted != null &&
                    shouldRestoreTrustedRuntimeConnection &&
                    !didAttemptTrustedRuntimeRestore
                ) {
                    didAttemptTrustedRuntimeRestore = true
                    restoreTrustedRuntimeConnection()
                }
            }
        }
    }

    fun updateHost(value: String) {
        mutableState.update {
            it.copy(
                runtimeHost = value.trim(),
                runtimeEndpointSource = RuntimeEndpointSource.Manual,
            )
        }
    }

    fun updatePort(value: String) {
        mutableState.update {
            it.copy(
                runtimePort = value.filter(Char::isDigit).take(5),
                runtimeEndpointSource = RuntimeEndpointSource.Manual,
            )
        }
    }

    fun useUsbReverseEndpoint() {
        mutableState.update {
            it.copy(
                runtimeHost = "127.0.0.1",
                runtimePort = "43170",
                runtimeEndpointSource = RuntimeEndpointSource.UsbReverse,
                error = null,
            )
        }
    }

    fun useEmulatorEndpoint() {
        mutableState.update {
            it.copy(
                runtimeHost = "10.0.2.2",
                runtimePort = "43170",
                runtimeEndpointSource = RuntimeEndpointSource.Emulator,
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
        addAttachmentReferences(uris.map { it.toString() })
    }

    internal fun addAttachmentReferences(references: List<String>) {
        if (references.isEmpty()) return
        viewModelScope.launch {
            val availableSlots = (MAX_PENDING_ATTACHMENTS - state.value.pendingAttachments.size)
                .coerceAtLeast(0)
            if (availableSlots == 0) {
                showError("attachment_limit_reached")
                return@launch
            }
            val referencesToLoad = references.take(availableSlots)
            val selectionWasLimited = references.size > referencesToLoad.size
            val loadedAttachments = mutableListOf<RuntimePendingAttachment>()
            for (reference in referencesToLoad) {
                val metadata = attachmentReader.metadata(reference)
                if (metadata.sizeBytes > MAX_ATTACHMENT_BYTES) {
                    showError("attachment_too_large", metadata.name)
                    return@launch
                }
                val bytes = attachmentReader.readBytes(reference)
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
                    dataBase64 = Base64.getEncoder().encodeToString(bytes),
                )
            }
            mutableState.update { current ->
                val combined = (current.pendingAttachments + loadedAttachments)
                    .take(MAX_PENDING_ATTACHMENTS)
                current.copy(
                    pendingAttachments = combined,
                    error = if (selectionWasLimited) {
                        RuntimeUiError(code = "attachment_limit_reached")
                    } else {
                        null
                    },
                )
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

    fun reconcileSystemAppLanguageTag(languageTag: String?) {
        val cleanData = persistedRuntimeData.withSystemAppLanguageTag(languageTag)
        if (cleanData != persistedRuntimeData) {
            publishPersistedRuntimeData(cleanData, save = true)
        }
    }

    fun setAppTheme(theme: RuntimeAppTheme) {
        publishPersistedRuntimeData(
            persistedRuntimeData.withAppTheme(theme),
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
        requestRuntimeChatMessages(sessionId)
    }

    fun selectChatSession(sessionId: String) {
        openPreviousChat(sessionId)
    }

    fun renameChatSession(sessionId: String, title: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        val session = persistedRuntimeData.sessions.firstOrNull { it.id == sessionId }
        if (session == null) {
            showError("chat_session_not_found")
            return
        }
        if (isRuntimeOwnedChatMutationBlocked(listOf(session))) return
        val cleanTitle = title.trim()
        if (cleanTitle.isBlank()) return
        publishPersistedRuntimeData(
            persistedRuntimeData.withRenamedChatSession(sessionId, cleanTitle, nowMillis()),
            save = true,
        )
        sendRuntimeChatSessionRenameIfNeeded(
            session = session,
            title = cleanTitle,
        )
    }

    fun deleteChatSession(sessionId: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        val session = persistedRuntimeData.sessions.firstOrNull { it.id == sessionId }
        if (session == null) {
            showError("chat_session_not_found")
            return
        }
        if (session.archivedAtMillis == null) {
            showError("chat_session_must_be_archived_before_delete")
            return
        }
        if (isRuntimeOwnedChatMutationBlocked(listOf(session))) return
        val now = nowMillis()
        publishPersistedRuntimeData(
            persistedRuntimeData.withoutArchivedChatSession(sessionId, nowMillis = now),
            save = true,
        )
        sendRuntimeChatSessionLifecycleIfNeeded(
            session = session,
            type = MessageType.ChatSessionDelete,
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
        val session = persistedRuntimeData.sessions.firstOrNull { it.id == sessionId }
        if (session == null) {
            showError("chat_session_not_found")
            return
        }
        if (isRuntimeOwnedChatMutationBlocked(listOf(session))) return
        publishPersistedRuntimeData(
            persistedRuntimeData.withArchivedChatSession(sessionId, nowMillis()),
            save = true,
        )
        sendRuntimeChatSessionLifecycleIfNeeded(
            session = session,
            type = MessageType.ChatSessionArchive,
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
        val sessionsToArchive = persistedRuntimeData.sessions.filter { it.archivedAtMillis == null }
        if (isRuntimeOwnedChatMutationBlocked(sessionsToArchive)) return
        publishPersistedRuntimeData(
            persistedRuntimeData.withArchivedChatSessions(nowMillis()),
            save = true,
        )
        sessionsToArchive.forEach { session ->
            sendRuntimeChatSessionLifecycleIfNeeded(
                session = session,
                type = MessageType.ChatSessionArchive,
            )
        }
        mutableState.update { it.copy(chatInput = "") }
    }

    fun unarchiveChatSession(sessionId: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        val session = persistedRuntimeData.sessions.firstOrNull { it.id == sessionId }
        if (session == null) {
            showError("chat_session_not_found")
            return
        }
        if (isRuntimeOwnedChatMutationBlocked(listOf(session))) return
        publishPersistedRuntimeData(
            persistedRuntimeData.withUnarchivedChatSession(sessionId, nowMillis()),
            save = true,
        )
        sendRuntimeChatSessionLifecycleIfNeeded(
            session = session,
            type = MessageType.ChatSessionRestore,
        )
    }

    fun clearArchivedChatSessions() {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        val archivedSessionsToDelete = persistedRuntimeData.sessions.filter { it.archivedAtMillis != null }
        if (isRuntimeOwnedChatMutationBlocked(archivedSessionsToDelete)) return
        val now = nowMillis()
        publishPersistedRuntimeData(
            persistedRuntimeData.withoutArchivedChatSessions(nowMillis = now),
            save = true,
        )
        archivedSessionsToDelete.forEach { session ->
            sendRuntimeChatSessionLifecycleIfNeeded(
                session = session,
                type = MessageType.ChatSessionDelete,
            )
        }
    }

    fun addMemoryEntry(content: String) {
        val cleanContent = content.trim()
        if (cleanContent.isBlank()) return
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        sendEnvelope(
            envelope(
                type = MessageType.MemoryUpsert,
                serializer = MemoryUpsertPayload.serializer(),
                payload = MemoryUpsertPayload(
                    content = cleanContent,
                    enabled = true,
                ),
            )
        )
    }

    fun removeMemoryEntry(entryId: String) {
        val cleanId = entryId.trim()
        if (cleanId.isBlank()) return
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        sendEnvelope(
            envelope(
                type = MessageType.MemoryDelete,
                serializer = MemoryDeletePayload.serializer(),
                payload = MemoryDeletePayload(id = cleanId),
            )
        )
    }

    fun setMemoryEntryEnabled(entryId: String, enabled: Boolean) {
        val entry = state.value.memoryEntries.firstOrNull { it.id == entryId } ?: return
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        sendEnvelope(
            envelope(
                type = MessageType.MemoryUpsert,
                serializer = MemoryUpsertPayload.serializer(),
                payload = MemoryUpsertPayload(
                    id = entry.id,
                    content = entry.content,
                    enabled = enabled,
                ),
            )
        )
    }

    fun setTrustedRuntimeAutoReconnectEnabled(enabled: Boolean) {
        persistTrustedRuntimeAutoReconnectEnabled(enabled)
        if (!enabled) {
            reconnectJob?.cancel()
            reconnectJob = null
            return
        }
        restoreTrustedRuntimeConnection()
    }

    fun connectToTrustedRuntime() {
        persistTrustedRuntimeAutoReconnectEnabled(true)
        reconnectJob?.cancel()
        reconnectJob = null
        viewModelScope.launch {
            val current = state.value
            if (publishTrustedRemoteRouteExpiredIfNeeded(current)) return@launch
            if (current.shouldDiscoverTrustedRuntimeRoute()) {
                ensureTrustedRuntimeDiscovery()
            }
            val target = autoReconnectTrustedRuntimeConnectionTarget(current)
                ?: trustedRuntimeConnectionTarget(current)
            if (target == null) {
                if (publishTrustedRemoteRouteExpiredIfNeeded(current)) return@launch
                showError("pairing_required")
                return@launch
            }

            connectToRuntime(target)
        }
    }

    fun restoreTrustedRuntimeConnection() {
        if (pendingPairingPayload != null) return
        val current = state.value
        if (!shouldAttemptTrustedRuntimeRestore(shouldRestoreTrustedRuntimeConnection, current)) return
        if (publishTrustedRemoteRouteExpiredIfNeeded(current)) return
        if (current.shouldDiscoverTrustedRuntimeRoute()) {
            ensureTrustedRuntimeDiscovery()
        }
        val target = autoReconnectTrustedRuntimeConnectionTarget(current) ?: run {
            publishTrustedRemoteRouteExpiredIfNeeded(current)
            return
        }
        reconnectJob?.cancel()
        reconnectJob = viewModelScope.launch(start = CoroutineStart.UNDISPATCHED) {
            val refreshed = state.value
            if (
                shouldRestoreTrustedRuntimeConnection &&
                !refreshed.isConnected &&
                !refreshed.isConnecting
            ) {
                connectToRuntime(autoReconnectTrustedRuntimeConnectionTarget(refreshed) ?: target)
            }
        }
    }

    fun trustRuntimeFromPairingQr(rawValue: String) {
        viewModelScope.launch {
            cancelPendingPairingRetry()
            cancelPendingPairingDiscoveryTimeout()
            mutableState.update { it.copy(routeRefreshNoticeRuntimeName = null) }
            val payload = when (
                val parsed = parseRuntimePairingQrPayload(
                    rawValue = rawValue,
                    allowDebugLoopbackRelay = BuildConfig.DEBUG,
                    allowDiagnosticLocalDirectEndpoint = BuildConfig.DEBUG,
                )
            ) {
                is RuntimePairingQrParseResult.Accepted -> parsed.payload
                is RuntimePairingQrParseResult.Rejected -> {
                    if (parsed.clearPendingPairing) {
                        pendingPairingPayload = null
                        clearPersistedPendingPairingRoute()
                        mutableState.update {
                            it.withClearedPendingPairing().copy(error = parsed.error)
                        }
                    } else {
                        mutableState.update { it.copy(error = parsed.error) }
                    }
                    return@launch
                }
            }

            persistTrustedRuntimeAutoReconnectEnabled(true)
            val refreshedTrustedRuntime = trustedRuntimeFromRouteRefreshQr(
                current = state.value.trustedRuntime,
                payload = payload,
            )
            if (refreshedTrustedRuntime != null) {
                cancelPendingPairingDiscoveryTimeout()
                clearPersistedPendingPairingRoute()
                val trustedEndpoint = refreshedTrustedRuntime.lastKnownEndpointHintOrNull()
                val runtime = refreshedTrustedRuntime.toRuntimeTrustedRuntime()
                pairingStore.trustRuntime(refreshedTrustedRuntime)
                mutableState.update {
                    it.withClearedPendingPairing()
                        .withTrustedRuntimeRouteFields(runtime, trustedEndpoint)
                        .copy(
                            routeRefreshNoticeRuntimeName = runtime.name,
                            error = null,
                        )
                }
                connectToRuntime(refreshedTrustedRuntime.toConnectionTarget())
                return@launch
            }

            if (shouldPreemptActiveConnectionForPairingQr(state.value, payload)) {
                closeRuntimeConnection()
            }

            pendingPairingPayload = payload
            persistPendingPairingPayload(payload)
            val plan = pendingPairingConnectionPlan(state.value, payload)
            mutableState.value = plan.pendingState

            if (plan.shouldStartDiscovery) {
                startDiscovery()
            }

            val target = plan.target
            if (target == null) {
                if (plan.shouldWaitForDiscoveryRoute) {
                    schedulePendingPairingDiscoveryTimeout(payload)
                    return@launch
                }
                pendingPairingPayload = null
                clearPersistedPendingPairingRoute()
                mutableState.update {
                    it.withClearedPendingPairing().copy(
                        error = RuntimeUiError("pairing_endpoint_unavailable"),
                    )
                }
                return@launch
            }
            mutableState.update { it.copy(isPairingAwaitingRoute = false) }
            if (connectToRuntime(target, requestHealthAfterConnect = false)) {
                sendPairingRequest(payload)
            } else {
                handlePendingPairingConnectionFailure(payload)
            }
        }
    }

    fun showQrScanFailed(detail: String?) {
        showError("qr_scan_failed", detail)
    }

    private suspend fun sendPairingRequest(payload: RuntimePairingPayload) {
        runCatching { deviceIdentityStore.loadOrCreate() }
            .onSuccess { identity ->
                cancelPendingPairingRetry()
                cancelPendingPairingDiscoveryTimeout()
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
                cancelPendingPairingRetry()
                cancelPendingPairingDiscoveryTimeout()
                pendingPairingPayload = null
                clearPersistedPendingPairingRoute()
                mutableState.update { it.withClearedPendingPairing() }
                showError("device_identity_failed", error.message)
            }
    }

    private fun persistPendingPairingPayload(payload: RuntimePairingPayload) {
        val cleanData = persistedRuntimeData.withPendingPairingRoute(
            payload = payload,
            nowMillis = nowMillis(),
        )
        persistedRuntimeData = cleanData
        localStore.save(cleanData)
    }

    private fun clearPersistedPendingPairingRoute() {
        val cleanData = persistedRuntimeData.withoutPendingPairingRoute()
        if (cleanData == persistedRuntimeData) return
        persistedRuntimeData = cleanData
        localStore.save(cleanData)
    }

    private fun restorePersistedPendingPairingRouteIfNeeded(data: PersistedRuntimeData) {
        val pendingRoute = data.pendingPairingRoute ?: return
        val payload = pendingRoute.toRuntimePairingPayloadOrNull()
        if (
            payload == null ||
            pendingRoute.isExpired(nowMillis()) ||
            payload.hasExpiredRemoteRoute()
        ) {
            clearPersistedPendingPairingRoute()
            return
        }

        pendingPairingPayload = payload
        mutableState.update {
            it.withPendingPairing(payload)
        }

        if (payload.shouldWaitForDiscoveryRoute()) {
            startDiscovery()
            schedulePendingPairingDiscoveryTimeout(payload)
        }

        viewModelScope.launch {
            val target = pairingRuntimeConnectionTarget(state.value, payload)
            if (target == null) {
                if (payload.shouldWaitForDiscoveryRoute()) {
                    mutableState.update {
                        it.withPendingPairing(payload)
                    }
                    return@launch
                }
                pendingPairingPayload = null
                clearPersistedPendingPairingRoute()
                mutableState.update {
                    it.withClearedPendingPairing().copy(
                        error = RuntimeUiError("pairing_endpoint_unavailable"),
                    )
                }
                return@launch
            }
            mutableState.update { it.copy(isPairingAwaitingRoute = false) }
            if (connectToRuntime(target, requestHealthAfterConnect = false)) {
                sendPairingRequest(payload)
            } else {
                handlePendingPairingConnectionFailure(payload)
            }
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
                                discoveredRuntimes = peers.map { peer ->
                                    RuntimeDiscoveredRuntime(
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
                        connectToPendingPairingRuntimeIfNeeded()
                        connectToDiscoveredTrustedRuntimeIfNeeded()
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

    private fun ensureTrustedRuntimeDiscovery() {
        if (discoveryJob?.isActive == true) return
        startDiscovery()
    }

    private suspend fun connectToPendingPairingRuntimeIfNeeded() {
        val payload = pendingPairingPayload ?: return
        val current = state.value
        if (current.isConnected || current.isConnecting) return
        val target = pairingRuntimeConnectionTarget(current, payload) ?: return
        mutableState.update { it.copy(isPairingAwaitingRoute = false) }
        if (connectToRuntime(target, requestHealthAfterConnect = false)) {
            sendPairingRequest(payload)
        } else {
            handlePendingPairingConnectionFailure(payload)
        }
    }

    private fun handlePendingPairingConnectionFailure(payload: RuntimePairingPayload) {
        if (payload.hasExpiredRemoteRoute()) {
            cancelPendingPairingRetry()
            cancelPendingPairingDiscoveryTimeout()
            pendingPairingPayload = null
            clearPersistedPendingPairingRoute()
            mutableState.update {
                it.withClearedPendingPairing().copy(
                    error = RuntimeUiError(
                        code = "remote_route_expired",
                        diagnosticCode = "route_diagnostic_remote_route_expired",
                    ),
                )
            }
            return
        }
        if (payload.hasRelayRoute()) {
            mutableState.update {
                it.copy(
                    isPairingAwaitingRoute = false,
                    runtimeStatus = "pairing",
                    error = RuntimeUiError("pairing_route_retrying"),
                )
            }
            schedulePendingPairingRetry(payload)
            return
        }
        pendingPairingPayload = null
        cancelPendingPairingDiscoveryTimeout()
        clearPersistedPendingPairingRoute()
        mutableState.update { it.withClearedPendingPairing() }
    }

    private fun schedulePendingPairingRetry(payload: RuntimePairingPayload) {
        if (pendingPairingPayload != payload || !payload.hasRelayRoute()) return
        if (pendingPairingRetryAttempts >= MAX_PENDING_PAIRING_RETRY_ATTEMPTS) {
            cancelPendingPairingRetry()
            pendingPairingPayload = null
            clearPersistedPendingPairingRoute()
            mutableState.update {
                it.withClearedPendingPairing().copy(
                    error = pendingPairingExhaustedRouteError(payload),
                )
            }
            return
        }

        pendingPairingRetryAttempts += 1
        val retryDelay = RECONNECT_DELAY_MS * pendingPairingRetryAttempts.coerceAtMost(4)
        pendingPairingRetryJob?.cancel()
        pendingPairingRetryJob = viewModelScope.launch {
            delay(retryDelay)
            if (pendingPairingPayload != payload) return@launch
            val current = state.value
            if (current.isConnected || current.isConnecting) return@launch
            val target = pairingRuntimeConnectionTarget(current, payload)
            if (target == null) {
                handlePendingPairingConnectionFailure(payload)
                return@launch
            }
            if (connectToRuntime(target, requestHealthAfterConnect = false)) {
                sendPairingRequest(payload)
            } else {
                handlePendingPairingConnectionFailure(payload)
            }
        }
    }

    private fun cancelPendingPairingRetry() {
        pendingPairingRetryJob?.cancel()
        pendingPairingRetryJob = null
        pendingPairingRetryAttempts = 0
    }

    private fun schedulePendingPairingDiscoveryTimeout(payload: RuntimePairingPayload) {
        if (pendingPairingPayload != payload || !payload.shouldWaitForDiscoveryRoute()) return
        pendingPairingDiscoveryTimeoutJob?.cancel()
        pendingPairingDiscoveryTimeoutJob = viewModelScope.launch {
            delay(PENDING_PAIRING_DISCOVERY_TIMEOUT_MS)
            if (pendingPairingPayload != payload) return@launch
            val current = state.value
            if (current.isConnected || current.isConnecting) return@launch
            if (pairingRuntimeConnectionTarget(current, payload) != null) return@launch
            pendingPairingPayload = null
            clearPersistedPendingPairingRoute()
            mutableState.update {
                it.withClearedPendingPairing().copy(
                    error = RuntimeUiError(
                        code = "pairing_endpoint_unavailable",
                        diagnosticCode = "route_diagnostic_remote_pending",
                    ),
                )
            }
        }
    }

    private fun cancelPendingPairingDiscoveryTimeout() {
        pendingPairingDiscoveryTimeoutJob?.cancel()
        pendingPairingDiscoveryTimeoutJob = null
    }

    private suspend fun connectToDiscoveredTrustedRuntimeIfNeeded() {
        if (pendingPairingPayload != null) return
        if (!shouldRestoreTrustedRuntimeConnection) return
        val current = state.value
        if (current.isConnected || current.isConnecting) return
        val target = autoReconnectTrustedRuntimeConnectionTarget(current) ?: return
        connectToRuntime(target)
    }

    fun stopDiscovery() {
        discoveryJob?.cancel()
        discoveryJob = null
        cancelPendingPairingRetry()
        cancelPendingPairingDiscoveryTimeout()
        pendingPairingPayload = null
        clearPersistedPendingPairingRoute()
        mutableState.update {
            it.withClearedPendingPairing().copy(
                isDiscovering = false,
            )
        }
    }

    fun useDiscoveredRuntime(peer: RuntimeDiscoveredRuntime) {
        val current = state.value
        if (!discoveredRuntimeSelectableForTrustState(current, pendingPairingPayload, peer)) {
            mutableState.update {
                it.copy(
                    error = RuntimeUiError(
                        if (current.trustedRuntime == null && pendingPairingPayload == null) {
                            "pairing_required"
                        } else {
                            "runtime_identity_mismatch"
                        },
                    ),
                )
            }
            return
        }
        mutableState.update {
            it.copy(
                runtimeHost = peer.host,
                runtimePort = peer.port.toString(),
                runtimeEndpointSource = RuntimeEndpointSource.BonjourDiscovery,
                error = null,
            )
        }
    }

    fun forgetTrustedRuntime() {
        persistTrustedRuntimeAutoReconnectEnabled(false)
        closeRuntimeConnection()
        viewModelScope.launch {
            pairingStore.forgetRuntime()
            mutableState.update { it.copy(routeRefreshNoticeRuntimeName = null, error = null) }
        }
    }

    fun disconnect() {
        persistTrustedRuntimeAutoReconnectEnabled(false)
        closeRuntimeConnection()
    }

    private fun closeRuntimeConnection() {
        reconnectJob?.cancel()
        reconnectJob = null
        cancelRuntimeRouteRefreshLease()
        cancelPendingPairingRetry()
        readJob?.cancel()
        readJob = null
        activeChannel?.close()
        activeChannel = null
        client.close()
        isSessionAuthenticated = false
        cancelPendingPairingDiscoveryTimeout()
        pendingModelPullRequestId = null
        pendingMemoryListRequestId = null
        pendingRouteRefreshRequestId = null
        pendingPairingPayload = null
        clearPendingRuntimeHistoryRequests()
        pendingChatSessionLifecycleRequestIds.clear()
        pendingChatSessionRenameRequestIds.clear()
        clearPendingSuggestions()
        clearPendingTitleRequest()
        modelIdToSelectAfterRefresh = null
        mutableState.update {
            it.withClearedPendingPairing().copy(
                isConnected = false,
                isConnecting = false,
                isStreaming = false,
                isLoadingSuggestions = false,
                installingModelId = null,
                activeRequestId = null,
                runtimeStatus = "disconnected",
                activeRouteKind = null,
                routeRefreshNoticeRuntimeName = null,
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

    private fun requestRuntimeChatSessions() {
        if (!isSessionAuthenticated || activeChannel?.isConnected != true) return
        if (pendingChatSessionsRequestId != null) return
        val requestId = UUID.randomUUID().toString()
        pendingChatSessionsRequestId = requestId
        sendEnvelope(
            envelope(
                type = MessageType.ChatSessionsList,
                requestId = requestId,
                serializer = ChatSessionsListRequestPayload.serializer(),
                payload = ChatSessionsListRequestPayload(
                    limit = MAX_RUNTIME_CHAT_SESSIONS,
                    includeArchived = true,
                ),
            )
        )
    }

    private fun requestRuntimeChatMessages(sessionId: String) {
        if (!isSessionAuthenticated || activeChannel?.isConnected != true) return
        if (sessionId.isBlank()) return
        val requestId = UUID.randomUUID().toString()
        pendingChatMessagesRequestId = requestId
        pendingChatMessagesSessionId = sessionId
        sendEnvelope(
            envelope(
                type = MessageType.ChatMessagesList,
                requestId = requestId,
                serializer = ChatMessagesListRequestPayload.serializer(),
                payload = ChatMessagesListRequestPayload(
                    sessionId = sessionId,
                    limit = MAX_RUNTIME_CHAT_MESSAGES,
                ),
            )
        )
    }

    private fun requestRuntimeMemory() {
        if (!isSessionAuthenticated || activeChannel?.isConnected != true) return
        if (pendingMemoryListRequestId != null) return
        val requestId = UUID.randomUUID().toString()
        pendingMemoryListRequestId = requestId
        sendEnvelope(ProtocolEnvelope(type = MessageType.MemoryList, requestId = requestId))
    }

    private fun sendRuntimeChatSessionLifecycleIfNeeded(
        session: PersistedChatSession,
        type: String,
    ) {
        if (!session.runtimeOwned) return
        if (!isSessionAuthenticated || activeChannel?.isConnected != true) return
        val requestId = UUID.randomUUID().toString()
        pendingChatSessionLifecycleRequestIds += requestId
        sendEnvelope(
            envelope(
                type = type,
                requestId = requestId,
                serializer = ChatSessionLifecyclePayload.serializer(),
                payload = ChatSessionLifecyclePayload(sessionId = session.id),
            )
        )
    }

    private fun sendRuntimeChatSessionRenameIfNeeded(
        session: PersistedChatSession,
        title: String,
    ) {
        if (!session.runtimeOwned) return
        if (!isSessionAuthenticated || activeChannel?.isConnected != true) return
        val requestId = UUID.randomUUID().toString()
        pendingChatSessionRenameRequestIds += requestId
        sendEnvelope(
            envelope(
                type = MessageType.ChatSessionRename,
                requestId = requestId,
                serializer = ChatSessionRenamePayload.serializer(),
                payload = ChatSessionRenamePayload(
                    sessionId = session.id,
                    title = title,
                ),
            )
        )
    }

    private fun isRuntimeOwnedChatMutationBlocked(sessions: List<PersistedChatSession>): Boolean {
        if (
            !runtimeOwnedChatMutationRequiresConnectedRuntime(
                sessions = sessions,
                isSessionAuthenticated = isSessionAuthenticated,
                isTransportConnected = activeChannel?.isConnected == true,
            )
        ) {
            return false
        }
        showError("chat_history_runtime_required")
        return true
    }

    fun selectModel(modelId: String) {
        val model = state.value.models.firstOrNull { it.id == modelId }
        if (model != null && !model.isChatModel()) {
            showError("select_chat_model")
            return
        }
        if (model != null && !model.isRuntimeHostLocalModel()) {
            showError("select_chat_model")
            return
        }
        if (model != null && !model.installed) {
            requestModelInstall(modelId)
            return
        }
        persistSelectedModel(modelId)
    }

    fun selectEmbeddingModel(modelId: String?) {
        if (modelId == null) {
            persistSelectedEmbeddingModel(null)
            return
        }
        val model = state.value.models.firstOrNull { it.id == modelId }
        if (model == null || !model.isEmbeddingModel()) {
            showError("select_embedding_model")
            return
        }
        if (!model.installed || !model.isRuntimeHostLocalModel()) {
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
        if (model != null && !model.isRuntimeHostLocalModel()) {
            showError("select_chat_model")
            return
        }
        if (model?.installed == true) {
            persistSelectedModel(modelId)
            return
        }

        persistSelectedModel(modelId)
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
            attachmentOnlyPrompt(
                attachments = current.pendingAttachments,
                promptHeader = dependencies.attachmentPromptHeaderProvider?.invoke(current.selectedLanguageTag)
                    ?: attachmentOnlyPromptHeader(
                        context = getApplication(),
                        languageTag = current.selectedLanguageTag,
                    ),
            )
        }
        val attachments = current.pendingAttachments
        val userMessage = RuntimeChatMessage(
            role = "user",
            content = displayText,
            attachments = attachments.map { attachment ->
                RuntimeMessageAttachment(
                    type = attachment.type,
                    name = attachment.name,
                    mimeType = attachment.mimeType,
                )
            },
        )
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
        persistMessages(sessionId, updatedMessages, runtimeBacked = true)

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
                    ),
                    locale = current.runtimeRequestLocale(),
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
                activeRouteKind = null,
            )
        }

        readJob?.cancel()
        readJob = null
        cancelRuntimeRouteRefreshLease()
        activeChannel?.close()
        activeChannel = null
        client.close()
        isSessionAuthenticated = false

        val result = runCatching {
            Log.d(
                TAG,
                "Connecting to runtime ${target.connectionLogLabel()}"
            )
            connectionManager.connectWithRoute(target)
        }.onSuccess { connection ->
            activeChannel = connection.channel
            val connectedEndpoint = connection.route.connectedEndpointHintOrNull()
            val activeRouteKind = connection.route.activeRouteKind()
            Log.d(
                TAG,
                "Connected to runtime ${target.connectionLogLabel()} route=${connection.route.connectionRouteLogLabel()}"
            )
            reconnectJob = null
            mutableState.update {
                it.copy(
                    isConnected = true,
                    isConnecting = false,
                    runtimeStatus = "connected",
                    runtimeHost = connectedEndpoint?.host ?: it.runtimeHost,
                    runtimePort = connectedEndpoint?.port?.toString() ?: it.runtimePort,
                    runtimeEndpointSource = connectedEndpoint?.source ?: it.runtimeEndpointSource,
                    activeRouteKind = activeRouteKind,
                    error = null,
                )
            }
            startReadLoop()
            if (requestHealthAfterConnect) {
                sendHello()
            }
        }.onFailure { error ->
            val uiError = error.connectionUiError()
            val current = state.value
            val trustedRuntimeWithoutFailedRelay = if (
                pendingPairingPayload == null &&
                uiError.requiresFreshRemoteRouteBeforeReconnect()
            ) {
                current.trustedRuntime?.withoutRelayRoute()
            } else {
                null
            }
            Log.e(
                TAG,
                "Runtime connection failed code=${uiError.code}" +
                    " diagnostic=${uiError.diagnosticCode ?: "none"}" +
                    " target=${target.connectionLogLabel()}",
                error,
            )
            val updatedState = current.copy(
                isConnected = false,
                isConnecting = false,
                runtimeStatus = "failed",
                activeRouteKind = null,
                error = uiError,
            ).let { failedState ->
                trustedRuntimeWithoutFailedRelay?.let { runtime ->
                    failedState.withTrustedRuntimeRouteFields(runtime, runtime.endpointHint)
                } ?: failedState
            }
            mutableState.value = updatedState
            trustedRuntimeWithoutFailedRelay?.toTrustedRuntimeOrNull()?.let { trusted ->
                didAttemptTrustedRuntimeRestore = true
                viewModelScope.launch {
                    pairingStore.trustRuntime(trusted)
                }
            }
            if (shouldRetryTrustedRuntimeConnectFailure(state.value, target, shouldRestoreTrustedRuntimeConnection)) {
                scheduleTrustedRuntimeReconnect()
            }
        }
        return result.isSuccess
    }

    private fun startReadLoop() {
        readJob?.cancel()
        readJob = viewModelScope.launch {
            val channel = activeChannel ?: client
            while (isActive) {
                runCatching { channel.receive() }
                    .onSuccess { envelope ->
                        Log.d(TAG, "Received ${envelope.type} request_id=${envelope.requestId}")
                        handleEnvelope(envelope)
                    }
                    .onFailure { error ->
                        if (isActive) {
                            Log.e(TAG, "Runtime receive failed", error)
                            isSessionAuthenticated = false
                            clearPendingRuntimeHistoryRequests()
                            pendingMemoryListRequestId = null
                            pendingRouteRefreshRequestId = null
                            cancelRuntimeRouteRefreshLease()
                            clearPendingSuggestions()
                            clearPendingTitleRequest()
                            val current = state.value
                            val uiError = current.runtimeReceiveFailureUiError(error)
                            val trustedRuntimeWithoutFailedRelay = if (uiError.requiresFreshRemoteRouteBeforeReconnect()) {
                                current.trustedRuntime?.withoutRelayRoute()
                            } else {
                                null
                            }
                            val updatedState = current.withRuntimeReceiveFailure(
                                uiError,
                            ).let { failedState ->
                                trustedRuntimeWithoutFailedRelay?.let { runtime ->
                                    failedState.withTrustedRuntimeRouteFields(runtime, runtime.endpointHint)
                                } ?: failedState
                            }
                            mutableState.value = updatedState
                            trustedRuntimeWithoutFailedRelay?.toTrustedRuntimeOrNull()?.let { trusted ->
                                didAttemptTrustedRuntimeRestore = true
                                viewModelScope.launch {
                                    pairingStore.trustRuntime(trusted)
                                }
                            }
                            if (current.activeRequestId != null) {
                                persistActiveMessages(updatedState.messages, clearError = false)
                            }
                            if (!uiError.requiresFreshRemoteRouteBeforeReconnect()) {
                                scheduleTrustedRuntimeReconnect()
                            }
                        }
                        return@launch
                    }
            }
        }
    }

    private fun scheduleTrustedRuntimeReconnect() {
        if (!shouldRestoreTrustedRuntimeConnection) return
        val current = state.value
        if (current.error.requiresFreshRemoteRouteBeforeReconnect()) return
        if (publishTrustedRemoteRouteExpiredIfNeeded(current)) return
        if (current.shouldDiscoverTrustedRuntimeRoute()) {
            ensureTrustedRuntimeDiscovery()
        }
        val target = autoReconnectTrustedRuntimeConnectionTarget(current) ?: run {
            publishTrustedRemoteRouteExpiredIfNeeded(current)
            return
        }
        reconnectJob?.cancel()
        reconnectJob = viewModelScope.launch {
            delay(RECONNECT_DELAY_MS)
            val current = state.value
            if (
                shouldRestoreTrustedRuntimeConnection &&
                !current.isConnected &&
                !current.isConnecting
            ) {
                connectToRuntime(autoReconnectTrustedRuntimeConnectionTarget(current) ?: target)
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
            MessageType.RouteRefresh -> handleRouteRefresh(envelope)
            MessageType.ChatSessionsList -> handleChatSessionsList(envelope)
            MessageType.ChatMessagesList -> handleChatMessagesList(envelope)
            MessageType.ChatDelta -> handleChatDelta(envelope)
            MessageType.ChatDone -> handleChatDone(envelope)
            MessageType.ChatCancel -> handleCancelAck(envelope)
            MessageType.ChatSuggestionsResult -> handleChatSuggestionsResult(envelope)
            MessageType.ChatTitleResult -> handleChatTitleResult(envelope)
            MessageType.ChatSessionRename -> handleChatSessionRename(envelope)
            MessageType.ChatSessionArchive,
            MessageType.ChatSessionRestore,
            MessageType.ChatSessionDelete -> handleChatSessionLifecycle(envelope)
            MessageType.MemoryList -> handleMemoryList(envelope)
            MessageType.MemoryUpsert -> handleMemoryUpsert(envelope)
            MessageType.MemoryDelete -> handleMemoryDelete(envelope)
            MessageType.Error -> handleError(envelope)
        }
    }

    private fun handleAuthChallenge(envelope: ProtocolEnvelope) {
        val payload = decodePayload(AuthChallengePayload.serializer(), envelope.payload) ?: return
        viewModelScope.launch {
            runCatching {
                val identity = deviceIdentityStore.loadOrCreate()
                if (!verifyRuntimeAuthChallenge(payload, identity.deviceId)) {
                    isSessionAuthenticated = false
                    showError("runtime_authentication_failed")
                    return@launch
                }
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

    private fun verifyRuntimeAuthChallenge(
        payload: AuthChallengePayload,
        deviceId: String,
    ): Boolean {
        val trustedRuntime = state.value.trustedRuntime ?: return true
        val runtimePublicKey = trustedRuntime.publicKeyBase64?.takeIf { it.isNotBlank() }
            ?: return true
        val challengedDeviceId = payload.deviceId?.takeIf { it.isNotBlank() } ?: return false
        if (challengedDeviceId != deviceId) return false
        val signature = payload.runtimeSignature?.takeIf { it.isNotBlank() } ?: return false
        val challengeFingerprint = payload.runtimeKeyFingerprint?.takeIf { it.isNotBlank() }
        if (challengeFingerprint != null && trustedRuntime.fingerprint != null && challengeFingerprint != trustedRuntime.fingerprint) {
            return false
        }
        return RuntimeIdentityProofVerifier.verifyChallenge(
            runtimePublicKeyBase64 = runtimePublicKey,
            expectedFingerprint = trustedRuntime.fingerprint,
            deviceId = challengedDeviceId,
            nonce = payload.nonce,
            signatureBase64 = signature,
        )
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
            requestRuntimeRouteRefresh()
            scheduleRuntimeRouteRefreshLease()
            requestRuntimeHealth()
            requestRuntimeChatSessions()
            requestRuntimeMemory()
        } else {
            isSessionAuthenticated = false
            cancelRuntimeRouteRefreshLease()
            showError("authentication_failed", payload.message)
        }
    }

    private fun handlePairingResult(envelope: ProtocolEnvelope) {
        val payload = decodePayload(PairingResultPayload.serializer(), envelope.payload) ?: return
        val pending = pendingPairingPayload
        if (!payload.accepted || pending == null) {
            cancelPendingPairingRetry()
            cancelPendingPairingDiscoveryTimeout()
            pendingPairingPayload = null
            clearPersistedPendingPairingRoute()
            mutableState.update {
                it.withClearedPendingPairing().copy(
                    error = RuntimeUiError("pairing_rejected", payload.message),
                )
            }
            return
        }

        viewModelScope.launch {
            val trusted = trustedRuntimeFromAcceptedPairing(pending, payload)
            if (trusted == null) {
                cancelPendingPairingRetry()
                pendingPairingPayload = null
                clearPersistedPendingPairingRoute()
                mutableState.update {
                    it.withClearedPendingPairing().copy(
                        error = RuntimeUiError("runtime_identity_mismatch"),
                    )
                }
                return@launch
            }

            pairingStore.trustRuntime(trusted)
            val trustedEndpoint = trusted.lastKnownEndpointHintOrNull()
            val runtime = trusted.toRuntimeTrustedRuntime()
            cancelPendingPairingRetry()
            cancelPendingPairingDiscoveryTimeout()
            pendingPairingPayload = null
            clearPersistedPendingPairingRoute()
            isSessionAuthenticated = true
            publishPersistedRuntimeData(
                persistedRuntimeData.withPairingOnboardingCompleted(),
                save = true,
            )
            mutableState.update {
                it.withClearedPendingPairing()
                    .withTrustedRuntimeRouteFields(runtime, trustedEndpoint)
                    .copy(routeRefreshNoticeRuntimeName = null, error = null)
            }
            requestRuntimeRouteRefresh()
            scheduleRuntimeRouteRefreshLease()
            requestRuntimeHealth()
            requestRuntimeChatSessions()
            requestRuntimeMemory()
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

    private fun requestRuntimeRouteRefresh() {
        if (!isSessionAuthenticated) return
        if (activeChannel?.isConnected != true) return
        if (state.value.trustedRuntime == null) return
        if (pendingRouteRefreshRequestId != null) return
        val requestId = UUID.randomUUID().toString()
        pendingRouteRefreshRequestId = requestId
        sendEnvelope(ProtocolEnvelope(type = MessageType.RouteRefresh, requestId = requestId))
    }

    private fun handleRouteRefresh(envelope: ProtocolEnvelope) {
        if (pendingRouteRefreshRequestId != envelope.requestId) return
        pendingRouteRefreshRequestId = null
        val payload = decodePayload(RouteRefreshPayload.serializer(), envelope.payload) ?: return
        val current = state.value.trustedRuntime ?: return
        val trusted = trustedRuntimeFromRouteRefreshPayload(
            current = current,
            payload = payload,
            nowEpochMillis = nowMillis(),
        ) ?: run {
            scheduleRuntimeRouteRefreshRetry()
            return
        }
        viewModelScope.launch {
            pairingStore.trustRuntime(trusted)
            val runtime = trusted.toRuntimeTrustedRuntime()
            mutableState.update {
                it.withTrustedRuntimeRouteFields(runtime, trusted.lastKnownEndpointHintOrNull())
                    .copy(routeRefreshNoticeRuntimeName = null)
            }
            scheduleRuntimeRouteRefreshLease()
        }
    }

    private fun scheduleRuntimeRouteRefreshLease() {
        routeRefreshLeaseJob?.cancel()
        routeRefreshLeaseJob = null
        if (!isSessionAuthenticated) return
        val channel = activeChannel ?: return
        if (!channel.isConnected) return
        val current = state.value
        if (!current.isConnected) return
        val trustedRuntime = current.trustedRuntime ?: return
        val now = nowMillis()
        if (!trustedRuntime.hasRelayRoute(now)) return
        val delayMillis = runtimeRouteRefreshLeaseDelayMillis(
            nowEpochMillis = now,
            relayExpiresAtEpochMillis = trustedRuntime.relayExpiresAtEpochMillis,
        ) ?: return
        routeRefreshLeaseJob = viewModelScope.launch {
            delay(delayMillis)
            routeRefreshLeaseJob = null
            requestRuntimeRouteRefresh()
        }
    }

    private fun scheduleRuntimeRouteRefreshRetry(): Boolean {
        routeRefreshLeaseJob?.cancel()
        routeRefreshLeaseJob = null
        if (!isSessionAuthenticated) return false
        val channel = activeChannel ?: return false
        if (!channel.isConnected) return false
        val current = state.value
        if (!current.isConnected) return false
        val delayMillis = runtimeRouteRefreshRetryDelayMillis(
            nowEpochMillis = nowMillis(),
            relayExpiresAtEpochMillis = current.trustedRuntime?.relayExpiresAtEpochMillis,
        ) ?: run {
            publishRouteRefreshLeaseExpired(current)
            return false
        }
        routeRefreshLeaseJob = viewModelScope.launch {
            delay(delayMillis)
            routeRefreshLeaseJob = null
            requestRuntimeRouteRefresh()
        }
        return true
    }

    private fun publishRouteRefreshLeaseExpired(current: RuntimeUiState) {
        val trustedRuntime = current.trustedRuntime ?: return
        if (trustedRuntime.relayExpiresAtEpochMillis == null) return
        mutableState.update {
            it.copy(
                isConnected = false,
                isConnecting = false,
                runtimeStatus = "failed",
                activeRouteKind = null,
                routeRefreshNoticeRuntimeName = null,
                error = RuntimeUiError(
                    code = "remote_route_expired",
                    diagnosticCode = "route_diagnostic_remote_route_expired",
                ),
            )
        }
    }

    private fun cancelRuntimeRouteRefreshLease() {
        routeRefreshLeaseJob?.cancel()
        routeRefreshLeaseJob = null
    }

    private fun handleRuntimeHealth(envelope: ProtocolEnvelope) {
        val payload = decodePayload(RuntimeHealthPayload.serializer(), envelope.payload) ?: return
        if (payload.status.isPairingRequiredRuntimeCode()) {
            isSessionAuthenticated = false
            mutableState.update {
                it.withPairingRequiredRuntimeState(detail = null)
            }
            return
        }
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
            requestRuntimeChatSessions()
            requestRuntimeMemory()
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
                installed = it.installed == true,
                running = it.running ?: false,
                source = it.source,
                description = it.description,
                sizeBytes = it.sizeBytes,
            )
        }
        val current = state.value
        val installTarget = modelIdToSelectAfterRefresh
        val reconciledSelections = reconcileModelSelections(
            currentSelectedModelId = current.selectedModelId,
            currentSelectedEmbeddingModelId = current.selectedEmbeddingModelId,
            models = models,
            installTargetModelId = installTarget,
        )
        if (reconciledSelections.installedTargetModelId != null) {
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
                selectedModelId = reconciledSelections.selectedModelId,
                selectedEmbeddingModelId = reconciledSelections.selectedEmbeddingModelId,
                error = null
            )
        }
        persistSelectedModel(reconciledSelections.selectedModelId, publish = false)
        persistSelectedEmbeddingModel(reconciledSelections.selectedEmbeddingModelId, publish = false)
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

    private fun handleChatSessionsList(envelope: ProtocolEnvelope) {
        if (pendingChatSessionsRequestId != null && pendingChatSessionsRequestId != envelope.requestId) return
        pendingChatSessionsRequestId = null
        val payload = decodePayload(ChatSessionsListResultPayload.serializer(), envelope.payload) ?: return
        val syncedData = persistedRuntimeData.withRuntimeChatSessionSummaries(
            sessions = payload.sessions,
            nowMillis = nowMillis(),
        )
        publishPersistedRuntimeData(
            syncedData,
            save = true,
            clearError = false,
        )
        activeRuntimeSessionId(syncedData)?.let(::requestRuntimeChatMessages)
    }

    private fun handleChatMessagesList(envelope: ProtocolEnvelope) {
        if (pendingChatMessagesRequestId != null && pendingChatMessagesRequestId != envelope.requestId) return
        val expectedSessionId = pendingChatMessagesSessionId
        pendingChatMessagesRequestId = null
        pendingChatMessagesSessionId = null
        val payload = decodePayload(ChatMessagesListResultPayload.serializer(), envelope.payload) ?: return
        if (expectedSessionId != null && expectedSessionId != payload.sessionId) return
        publishPersistedRuntimeData(
            persistedRuntimeData.withRuntimeChatMessages(
                sessionId = payload.sessionId,
                messages = payload.messages,
                nowMillis = nowMillis(),
            ),
            save = true,
            clearError = false,
        )
        requestChatSuggestions(
            sourceState = state.value,
            requireMissingSuggestions = true,
        )
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
            val titleRequested = requestChatTitleIfNeeded(updatedState)
            requestChatSuggestions(updatedState)
            if (!titleRequested) {
                requestRuntimeChatSessions()
            }
        }
    }

    private fun requestChatTitleIfNeeded(sourceState: RuntimeUiState): Boolean {
        val candidate = chatTitleRequestCandidate(
            sourceState = sourceState,
            persistedRuntimeData = persistedRuntimeData,
            isSessionAuthenticated = isSessionAuthenticated,
        ) ?: return false
        val requestId = UUID.randomUUID().toString()
        pendingTitleRequestId = requestId
        pendingTitleSessionId = candidate.sessionId
        sendEnvelope(
            envelope(
                type = MessageType.ChatTitleRequest,
                requestId = requestId,
                serializer = ChatTitleRequestPayload.serializer(),
                payload = ChatTitleRequestPayload(
                    sessionId = candidate.sessionId,
                    model = candidate.model,
                    messages = candidate.messages,
                    locale = candidate.locale,
                ),
            )
        )
        return true
    }

    private fun requestChatSuggestions(
        sourceState: RuntimeUiState,
        requireMissingSuggestions: Boolean = false,
    ) {
        val candidate = chatSuggestionsRequestCandidate(
            sourceState = sourceState,
            isSessionAuthenticated = isSessionAuthenticated,
            requireMissingSuggestions = requireMissingSuggestions,
            maxContextMessages = MAX_SUGGESTION_CONTEXT_MESSAGES,
            maxSuggestions = MAX_SUGGESTIONS,
        ) ?: return
        val requestId = UUID.randomUUID().toString()
        pendingSuggestionRequestId = requestId
        pendingSuggestionSessionId = candidate.sessionId
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
                    sessionId = candidate.sessionId,
                    model = candidate.model,
                    messages = candidate.messages,
                    maxSuggestions = candidate.maxSuggestions,
                    locale = candidate.locale,
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

    private fun handleChatTitleResult(envelope: ProtocolEnvelope) {
        if (pendingTitleRequestId != envelope.requestId) return
        val sessionId = pendingTitleSessionId
        clearPendingTitleRequest()
        if (sessionId == null) return
        val payload = decodePayload(ChatTitleResultPayload.serializer(), envelope.payload) ?: return
        publishPersistedRuntimeData(
            persistedRuntimeData.withGeneratedChatSessionTitle(
                sessionId = sessionId,
                title = payload.title,
                nowMillis = nowMillis(),
            ),
            save = true,
            clearError = false,
        )
        requestRuntimeChatSessions()
    }

    private fun handleChatSessionRename(envelope: ProtocolEnvelope) {
        pendingChatSessionRenameRequestIds -= envelope.requestId
        val payload = decodePayload(ChatSessionRenamePayload.serializer(), envelope.payload) ?: return
        publishPersistedRuntimeData(
            persistedRuntimeData.withRenamedChatSession(
                sessionId = payload.sessionId,
                title = payload.title,
                nowMillis = nowMillis(),
            ),
            save = true,
            clearError = false,
        )
        requestRuntimeChatSessions()
    }

    private fun handleChatSessionLifecycle(envelope: ProtocolEnvelope) {
        pendingChatSessionLifecycleRequestIds -= envelope.requestId
        val payload = decodePayload(ChatSessionLifecyclePayload.serializer(), envelope.payload) ?: return
        publishPersistedRuntimeData(
            persistedRuntimeData.withRuntimeChatSessionLifecycleResult(
                result = payload,
                nowMillis = nowMillis(),
            ),
            save = true,
            clearError = false,
        )
        requestRuntimeChatSessions()
    }

    private fun handleMemoryList(envelope: ProtocolEnvelope) {
        if (pendingMemoryListRequestId == envelope.requestId) {
            pendingMemoryListRequestId = null
        }
        val payload = decodePayload(MemoryListResultPayload.serializer(), envelope.payload) ?: return
        publishPersistedRuntimeData(
            persistedRuntimeData.withRuntimeMemoryEntries(payload.entries, nowMillis()),
            save = true,
        )
    }

    private fun handleMemoryUpsert(envelope: ProtocolEnvelope) {
        val payload = decodePayload(MemoryUpsertResultPayload.serializer(), envelope.payload) ?: return
        publishPersistedRuntimeData(
            persistedRuntimeData.withRuntimeMemoryEntry(payload.entry, nowMillis()),
            save = true,
        )
    }

    private fun handleMemoryDelete(envelope: ProtocolEnvelope) {
        val payload = decodePayload(MemoryDeleteResultPayload.serializer(), envelope.payload) ?: return
        publishPersistedRuntimeData(
            persistedRuntimeData.withoutRuntimeMemoryEntry(payload.id),
            save = true,
        )
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
        if (pendingChatSessionLifecycleRequestIds.remove(envelope.requestId)) {
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            showError("chat_session_sync_failed", payload?.message)
            return
        }
        if (pendingSuggestionRequestId == envelope.requestId) {
            clearPendingSuggestions()
            mutableState.update { it.copy(isLoadingSuggestions = false) }
            return
        }
        if (pendingTitleRequestId == envelope.requestId) {
            clearPendingTitleRequest()
            return
        }
        if (pendingChatSessionsRequestId == envelope.requestId) {
            pendingChatSessionsRequestId = null
            return
        }
        if (pendingChatMessagesRequestId == envelope.requestId) {
            pendingChatMessagesRequestId = null
            pendingChatMessagesSessionId = null
            return
        }
        if (pendingMemoryListRequestId == envelope.requestId) {
            pendingMemoryListRequestId = null
            return
        }
        if (pendingRouteRefreshRequestId == envelope.requestId) {
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            pendingRouteRefreshRequestId = null
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                isSessionAuthenticated = false
                cancelRuntimeRouteRefreshLease()
                mutableState.value = state.value.withRuntimeError(envelope, payload, pendingModelPullRequestId)
            } else {
                scheduleRuntimeRouteRefreshRetry()
            }
            return
        }
        val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
        val isModelPullError = pendingModelPullRequestId == envelope.requestId
        val isActiveChatError = state.value.activeRequestId == envelope.requestId
        if (isModelPullError) {
            modelIdToSelectAfterRefresh = null
        }
        if (payload?.code.isPairingRequiredRuntimeCode()) {
            isSessionAuthenticated = false
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
                val channel = requireNotNull(activeChannel) { "Runtime transport is not connected" }
                channel.send(envelope)
            }
                .onFailure { error ->
                    Log.e(TAG, "Runtime send failed", error)
                    val current = state.value
                    val isActiveChatSend = envelope.type == MessageType.ChatSend &&
                        current.activeRequestId == envelope.requestId
                    val isSuggestionRequest = envelope.type == MessageType.ChatSuggestionsRequest &&
                        pendingSuggestionRequestId == envelope.requestId
                    val isTitleRequest = envelope.type == MessageType.ChatTitleRequest &&
                        pendingTitleRequestId == envelope.requestId
                    val isSessionLifecycleRequest = pendingChatSessionLifecycleRequestIds.remove(envelope.requestId)
                    val isSessionRenameRequest = pendingChatSessionRenameRequestIds.remove(envelope.requestId)
                    val isMemoryListRequest = envelope.type == MessageType.MemoryList &&
                        pendingMemoryListRequestId == envelope.requestId
                    val isRouteRefreshRequest = envelope.type == MessageType.RouteRefresh &&
                        pendingRouteRefreshRequestId == envelope.requestId
                    val isRuntimeHistoryRequest = (
                        envelope.type == MessageType.ChatSessionsList &&
                            pendingChatSessionsRequestId == envelope.requestId
                        ) || (
                        envelope.type == MessageType.ChatMessagesList &&
                            pendingChatMessagesRequestId == envelope.requestId
                        )
                    if (isSuggestionRequest) {
                        clearPendingSuggestions()
                        mutableState.update { it.copy(isLoadingSuggestions = false) }
                        return@onFailure
                    }
                    if (isRuntimeHistoryRequest) {
                        clearPendingRuntimeHistoryRequests()
                        return@onFailure
                    }
                    if (isMemoryListRequest) {
                        pendingMemoryListRequestId = null
                        return@onFailure
                    }
                    if (isRouteRefreshRequest) {
                        pendingRouteRefreshRequestId = null
                        scheduleRuntimeRouteRefreshRetry()
                        return@onFailure
                    }
                    if (isTitleRequest) {
                        clearPendingTitleRequest()
                        return@onFailure
                    }
                    if (isSessionLifecycleRequest) {
                        showError("chat_session_sync_failed", error.message)
                        return@onFailure
                    }
                    if (isSessionRenameRequest) {
                        showError("chat_session_sync_failed", error.message)
                        return@onFailure
                    }
                    val cleanedMessages = if (isActiveChatSend) {
                        current.messages.withoutTrailingBlankAssistantPlaceholder()
                    } else {
                        current.messages
                    }
                    mutableState.value = current.copy(
                        isConnected = activeChannel?.isConnected == true,
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

    private fun publishTrustedRemoteRouteExpiredIfNeeded(
        current: RuntimeUiState = state.value,
    ): Boolean {
        if (autoReconnectTrustedRuntimeConnectionTarget(current) != null) {
            return false
        }
        if (!current.trustedRuntime.hasExpiredRelayRoute(dependencies.currentTimeMillis())) {
            return false
        }
        val trustedRuntimeWithoutExpiredRelay = current.trustedRuntime?.withoutRelayRoute()
        mutableState.update {
            val expiredState = it.copy(
                isConnected = false,
                isConnecting = false,
                runtimeStatus = "failed",
                activeRouteKind = null,
                error = RuntimeUiError(
                    code = "remote_route_expired",
                    diagnosticCode = "route_diagnostic_remote_route_expired",
                ),
            )
            trustedRuntimeWithoutExpiredRelay?.let { runtime ->
                expiredState.withTrustedRuntimeRouteFields(runtime, runtime.endpointHint)
            } ?: expiredState
        }
        trustedRuntimeWithoutExpiredRelay?.toTrustedRuntimeOrNull()?.let { trusted ->
            viewModelScope.launch {
                pairingStore.trustRuntime(trusted)
            }
        }
        return true
    }

    private fun clearPendingSuggestions() {
        pendingSuggestionRequestId = null
        pendingSuggestionSessionId = null
    }

    private fun clearPendingRuntimeHistoryRequests() {
        pendingChatSessionsRequestId = null
        pendingChatMessagesRequestId = null
        pendingChatMessagesSessionId = null
    }

    private fun canSendRuntimeMemoryCommand(): Boolean {
        return isSessionAuthenticated && activeChannel?.isConnected == true
    }

    private fun clearPendingTitleRequest() {
        pendingTitleRequestId = null
        pendingTitleSessionId = null
    }

    private fun ensureActiveChatSession(): String {
        val currentSessionId = state.value.activeChatSessionId
        if (currentSessionId != null) return currentSessionId
        val data = persistedRuntimeData.withNewChatSession(
            nowMillis = nowMillis(),
            modelId = state.value.selectedModelId,
        )
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
        runtimeBacked: Boolean = false,
    ) {
        publishPersistedRuntimeData(
            persistedRuntimeData.withPersistedMessages(
                sessionId = sessionId,
                messages = messages,
                nowMillis = nowMillis(),
                runtimeBacked = runtimeBacked,
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
                selectedTheme = RuntimeAppTheme.fromStorage(cleanData.appTheme),
                trustedRuntimeAutoReconnectEnabled = cleanData.trustedRuntimeAutoReconnectEnabled,
                pairingOnboardingCompleted = cleanData.pairingOnboardingCompleted,
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

    private fun persistTrustedRuntimeAutoReconnectEnabled(enabled: Boolean) {
        shouldRestoreTrustedRuntimeConnection = enabled
        val cleanData = persistedRuntimeData.withTrustedRuntimeAutoReconnectEnabled(enabled)
        persistedRuntimeData = cleanData
        localStore.save(cleanData)
        mutableState.update {
            it.copy(
                trustedRuntimeAutoReconnectEnabled = cleanData.trustedRuntimeAutoReconnectEnabled,
                error = null,
            )
        }
    }

    private fun nowMillis(): Long = dependencies.currentTimeMillis()

    private fun isActiveChatEnvelope(envelope: ProtocolEnvelope): Boolean {
        return state.value.activeRequestId == envelope.requestId
    }

    override fun onCleared() {
        dependencies.lifecycleCallbacksRegistrar.unregister(getApplication(), lifecycleCallbacks)
        stopDiscovery()
        closeRuntimeConnection()
        super.onCleared()
    }

    private companion object {
        const val TAG = "RuntimeClientVM"
        const val MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
        const val MAX_PENDING_ATTACHMENTS = 4
        const val RECONNECT_DELAY_MS = 750L
        const val MAX_PENDING_PAIRING_RETRY_ATTEMPTS = 120
        const val PENDING_PAIRING_DISCOVERY_TIMEOUT_MS = 15_000L
        const val MAX_SUGGESTIONS = 3
        const val MAX_SUGGESTION_CONTEXT_MESSAGES = 8
        const val MAX_RUNTIME_CHAT_SESSIONS = 100
        const val MAX_RUNTIME_CHAT_MESSAGES = 200
        const val ATTACHMENT_TYPE_IMAGE = "image"
        const val ATTACHMENT_TYPE_DOCUMENT = "document"
        val CLIENT_CAPABILITIES = RUNTIME_CLIENT_CAPABILITIES
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
        "hwpml" -> "application/x-hwpml"
        "epub" -> "application/epub+zip"
        "pages" -> "application/vnd.apple.pages"
        "numbers" -> "application/vnd.apple.numbers"
        "key" -> "application/vnd.apple.keynote"
        "webarchive" -> "application/x-webarchive"
        "rtf" -> "application/rtf"
        "html", "htm" -> "text/html"
        "xhtml" -> "application/xhtml+xml"
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
                message = runtimeProviderSafeMessage(status.message),
                code = runtimeProviderSafeCode(status.code),
                retryable = status.retryable,
            )
        },
        payload.lmStudio?.let { status ->
            RuntimeProviderStatus(
                id = "lm_studio",
                name = "LM Studio",
                available = status.available,
                message = runtimeProviderSafeMessage(status.message),
                code = runtimeProviderSafeCode(status.code),
                retryable = status.retryable,
            )
        },
    )
}

internal fun runtimeProviderSafeMessage(message: String): String {
    return message
        .trim()
        .takeUnless { it.containsBackendEndpointMaterial() }
        .orEmpty()
}

internal fun runtimeProviderSafeCode(code: String?): String? {
    return code
        ?.trim()
        ?.takeUnless { it.containsBackendEndpointMaterial() }
        ?.takeIf { it.matches(PROVIDER_DIAGNOSTIC_CODE_PATTERN) }
}

private fun String.containsBackendEndpointMaterial(): Boolean {
    return BACKEND_ENDPOINT_DETAIL_PATTERNS.any { pattern -> pattern.containsMatchIn(this) }
}

private val BACKEND_ENDPOINT_DETAIL_PATTERNS = listOf(
    Regex("https?://[^\\s,;)]+", RegexOption.IGNORE_CASE),
    Regex("\\b(?:[A-Za-z0-9.-]+|\\[[0-9A-Fa-f:]+])(?::)(?:11434|1234)\\b", RegexOption.IGNORE_CASE),
    Regex("\\b(?:Ollama|LM Studio)\\s+URL\\b", RegexOption.IGNORE_CASE),
    Regex("/(?:api/(?:tags|ps|pull|chat|show|v1)|v1/(?:models|chat|chat/completions))\\b", RegexOption.IGNORE_CASE),
    Regex(
        "(^|[\\s{,;?&])['\"]?(?:route[_-]?token|routeToken|route[_-]?secret|relay[_-]?secret|relaySecret|pairing[_-]?secret|pairingSecret|rt|rs)['\"]?\\s*[:=]\\s*['\"]?[^\\s'\",;})]+",
        RegexOption.IGNORE_CASE,
    ),
)

private val PROVIDER_DIAGNOSTIC_CODE_PATTERN = Regex("[A-Za-z][A-Za-z0-9_.-]{0,79}")

internal fun trustedRuntimeConnectionTarget(state: RuntimeUiState): RuntimeConnectionTarget? {
    val trustedRuntime = state.trustedRuntime ?: return null
    return RuntimeConnectionTarget(
        identity = PairedRuntimeIdentity(
            deviceId = trustedRuntime.deviceId,
            name = trustedRuntime.name,
            fingerprint = trustedRuntime.fingerprint,
            publicKeyBase64 = trustedRuntime.publicKeyBase64,
            routeToken = trustedRuntime.routeToken,
        ),
        endpointHint = trustedRuntime.endpointHint
            ?.takeUnless { trustedRuntime.hasRelayRoute() }
            ?.takeUnless { it.source == RuntimeEndpointSource.TrustedLastKnown },
    )
}

internal fun trustedDiscoveredRuntimeConnectionTarget(state: RuntimeUiState): RuntimeConnectionTarget? {
    val target = trustedRuntimeConnectionTarget(state) ?: return null
    val identity = target.identity ?: return null
    val discovered = state.discoveredRuntimes.firstOrNull { discovered ->
        discovered.matchesTrustedIdentity(identity, allowMissingMetadata = false)
    } ?: return null
    return target.copy(
        endpointHint = RuntimeEndpointHint(
            host = discovered.host,
            port = discovered.port,
            source = RuntimeEndpointSource.BonjourDiscovery,
        )
    )
}

internal fun autoReconnectTrustedRuntimeConnectionTarget(state: RuntimeUiState): RuntimeConnectionTarget? {
    if (state.isConnected || state.isConnecting) return null
    val discoveredTarget = trustedDiscoveredRuntimeConnectionTarget(state)
    if (discoveredTarget != null) return discoveredTarget
    val trustedTarget = trustedRuntimeConnectionTarget(state) ?: return null
    if (state.trustedRuntime?.hasRelayRoute() == true) return trustedTarget
    return trustedTarget.takeIf { it.endpointHint != null }
}

internal fun shouldAttemptTrustedRuntimeRestore(
    restoreEnabled: Boolean,
    state: RuntimeUiState,
): Boolean {
    return restoreEnabled && state.trustedRuntime != null && !state.isConnected && !state.isConnecting
}

internal fun shouldRetryTrustedRuntimeConnectFailure(
    state: RuntimeUiState,
    target: RuntimeConnectionTarget,
    restoreEnabled: Boolean,
): Boolean {
    if (!restoreEnabled || state.isConnected || state.isConnecting) return false
    if (state.error.requiresFreshRemoteRouteBeforeReconnect()) return false
    val identity = target.identity ?: return false
    val trustedRuntime = state.trustedRuntime ?: return false
    return trustedRuntime.matchesIdentity(identity)
}

internal fun RuntimeUiState.shouldDiscoverTrustedRuntimeRoute(): Boolean {
    return trustedRuntime != null &&
        trustedRuntime.hasRelayRoute() != true &&
        !isConnected &&
        !isConnecting
}

internal fun discoveredRuntimeSelectableForTrustState(
    state: RuntimeUiState,
    pendingPairingPayload: RuntimePairingPayload?,
    peer: RuntimeDiscoveredRuntime,
): Boolean {
    val trustedIdentity = trustedRuntimeConnectionTarget(state)?.identity
    val pendingIdentity = pendingPairingPayload?.toConnectionTarget(endpoint = null)?.identity
    return listOfNotNull(trustedIdentity, pendingIdentity)
        .any { identity -> peer.matchesTrustedIdentity(identity, allowMissingMetadata = false) }
}

internal fun runtimeRouteCandidates(
    state: RuntimeUiState,
    target: RuntimeConnectionTarget,
    includeUsbReverseFallback: Boolean = false,
    suppressDirectRoutes: Boolean = false,
): List<RuntimeRouteCandidate> {
    val routes = mutableListOf<RuntimeRouteCandidate>()
    val seenEndpoints = mutableSetOf<Pair<String, Int>>()

    val identity = target.identity
    val hasSavedRelayRoute = identity != null &&
        state.trustedRuntime
            ?.let { it.matchesIdentity(identity) && it.hasRelayRoute() } == true
    if (identity != null) {
        if (!hasSavedRelayRoute && !suppressDirectRoutes) state.selectedRouteEndpointHintOrNull()?.let { endpoint ->
            val key = endpoint.host to endpoint.port
            if (
                endpoint.isAllowedDirectEndpoint() &&
                state.isTrustedRouteEndpointAllowed(endpoint, identity) &&
                seenEndpoints.add(key)
            ) {
                routes += RuntimeRouteCandidate.DirectTcp(
                    hint = endpoint,
                    source = endpoint.routeSource(),
                )
            }
        }
        if (!suppressDirectRoutes) state.discoveredRuntimes.forEach { discovered ->
            val key = discovered.host to discovered.port
            val endpoint = RuntimeEndpointHint(
                host = discovered.host,
                port = discovered.port,
                source = RuntimeEndpointSource.BonjourDiscovery,
            )
            if (
                endpoint.isAllowedDirectEndpoint() &&
                discovered.matchesTrustedIdentity(identity, allowMissingMetadata = false) &&
                seenEndpoints.add(key)
            ) {
                routes += RuntimeRouteCandidate.DirectTcp(
                    hint = endpoint,
                    source = RuntimeRouteSource.FreshDiscovery,
                )
            }
        }
        if (includeUsbReverseFallback && !hasSavedRelayRoute && !suppressDirectRoutes) {
            val endpoint = RuntimeEndpointHint(
                host = "127.0.0.1",
                port = 43170,
                source = RuntimeEndpointSource.UsbReverse,
            )
            val key = endpoint.host to endpoint.port
            if (seenEndpoints.add(key)) {
                routes += RuntimeRouteCandidate.DirectTcp(
                    hint = endpoint,
                    source = RuntimeRouteSource.FreshDiscovery,
                )
            }
        }
    }

    target.endpointHint?.let { endpoint ->
        val key = endpoint.host to endpoint.port
        if (!hasSavedRelayRoute && !suppressDirectRoutes && endpoint.isAllowedDirectEndpoint() && seenEndpoints.add(key)) {
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
    val source = runtimeEndpointSource
    if (source == RuntimeEndpointSource.Manual || source == RuntimeEndpointSource.TrustedLastKnown) {
        return null
    }
    val port = runtimePort.toIntOrNull()?.takeIf { it in 1..65535 } ?: return null
    val host = runtimeHost.takeIf { it.isNotBlank() } ?: return null
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
    val discovered = discoveredRuntimes.firstOrNull { it.host == endpoint.host && it.port == endpoint.port }
        ?: return false
    return discovered.matchesTrustedIdentity(identity, allowMissingMetadata = false)
}

private fun RuntimeDiscoveredRuntime.matchesTrustedIdentity(
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

internal fun runtimePublicKeyMatches(expected: String?, actual: String?): Boolean {
    val normalizedExpected = expected.normalizedIdentityOrNull()
    val normalizedActual = actual.normalizedIdentityOrNull()
    return normalizedExpected == null || normalizedActual == null || normalizedExpected == normalizedActual
}

internal fun RuntimeConnectionFailure.toRuntimeUiError(): RuntimeUiError {
    return when (reason) {
        RuntimeConnectionFailureReason.NoRoutesResolved ->
            RuntimeUiError("no_route", message)
        RuntimeConnectionFailureReason.NoConnectableRoute -> {
            if (hasExpiredRemoteRoute()) {
                RuntimeUiError(
                    code = "remote_route_expired",
                    detail = message,
                    diagnosticCode = routeDiagnosticCode(),
                )
            } else if (hasUnavailableRemoteRoutePlaceholders()) {
                RuntimeUiError(
                    code = "remote_routes_unavailable",
                    detail = message,
                    diagnosticCode = routeDiagnosticCode(),
                )
            } else {
                RuntimeUiError(
                    code = "no_connectable_route",
                    detail = message,
                    diagnosticCode = routeDiagnosticCode(),
                )
            }
        }
        RuntimeConnectionFailureReason.RouteAttemptsFailed -> {
            val diagnosticCode = routeDiagnosticCode()
            RuntimeUiError(
                code = if (diagnosticCode == "route_diagnostic_relay_failed") {
                    "remote_route_unreachable"
                } else {
                    "connection_failed"
                },
                detail = message,
                diagnosticCode = diagnosticCode,
            )
        }
    }
}

private fun RuntimeConnectionFailure.hasUnavailableRemoteRoutePlaceholders(): Boolean {
    if (reason != RuntimeConnectionFailureReason.NoConnectableRoute) return false
    val hasPeerToPeerPlaceholder = routeRejections.any {
        it.capability == RuntimeRouteCapability.PeerToPeer &&
            it.reason == RuntimeRouteRejectionReason.PeerToPeerConnectorNotAvailable
    }
    val hasRelayPlaceholder = routeRejections.any {
        it.capability == RuntimeRouteCapability.Relay &&
            it.reason == RuntimeRouteRejectionReason.RelayConnectorNotAvailable
    }
    return hasPeerToPeerPlaceholder && hasRelayPlaceholder
}

private fun RuntimeConnectionFailure.hasExpiredRemoteRoute(): Boolean {
    return routeRejections.any {
        it.reason == RuntimeRouteRejectionReason.RemoteRouteExpired &&
            (it.capability == RuntimeRouteCapability.PeerToPeer || it.capability == RuntimeRouteCapability.Relay)
    }
}

private fun RuntimeConnectionFailure.routeDiagnosticCode(): String? {
    val hasExpiredRemoteRoute = hasExpiredRemoteRoute()
    val hasUnpreparedLocalDirect = routeRejections.any {
        it.capability == RuntimeRouteCapability.DirectTcp &&
            it.reason == RuntimeRouteRejectionReason.DirectTcpEndpointNotPrepared
    }
    val hasFailedDirectEndpoint = attemptFailures.any {
        it.route is RuntimeRouteCandidate.DirectTcp
    }
    val hasFailedRelayRoute = attemptFailures.any {
        it.route is RuntimeRouteCandidate.Relay
    }
    val hasPeerToPeerPlaceholder = routeRejections.any {
        it.capability == RuntimeRouteCapability.PeerToPeer &&
            it.reason == RuntimeRouteRejectionReason.PeerToPeerConnectorNotAvailable
    }
    val hasRelayPlaceholder = routeRejections.any {
        it.capability == RuntimeRouteCapability.Relay &&
            it.reason == RuntimeRouteRejectionReason.RelayConnectorNotAvailable
    }
    return when {
        hasExpiredRemoteRoute ->
            "route_diagnostic_remote_route_expired"
        hasFailedRelayRoute ->
            "route_diagnostic_relay_failed"
        hasFailedDirectEndpoint && hasPeerToPeerPlaceholder && hasRelayPlaceholder ->
            "route_diagnostic_direct_failed_remote_pending"
        hasUnpreparedLocalDirect && hasPeerToPeerPlaceholder && hasRelayPlaceholder ->
            "route_diagnostic_local_missing_remote_pending"
        hasPeerToPeerPlaceholder && hasRelayPlaceholder ->
            "route_diagnostic_remote_pending"
        else -> null
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

private fun RuntimeRouteCandidate.connectedEndpointHintOrNull(): RuntimeEndpointHint? {
    return when (this) {
        is RuntimeRouteCandidate.DirectTcp -> hint
        else -> null
    }
}

internal fun RuntimeRouteCandidate.activeRouteKind(): RuntimeActiveRouteKind {
    return when (this) {
        is RuntimeRouteCandidate.DirectTcp -> RuntimeActiveRouteKind.DirectTcp
        is RuntimeRouteCandidate.PeerToPeer -> RuntimeActiveRouteKind.PeerToPeer
        is RuntimeRouteCandidate.Relay -> RuntimeActiveRouteKind.Relay
        is RuntimeRouteCandidate.LocalDirect -> RuntimeActiveRouteKind.DirectTcp
    }
}

private fun RuntimeRouteCandidate.connectionRouteLogLabel(): String {
    return when (this) {
        is RuntimeRouteCandidate.DirectTcp -> "direct=${hint.host}:${hint.port} source=${hint.source}"
        is RuntimeRouteCandidate.LocalDirect -> "local_direct identity=${identity.deviceId}"
        is RuntimeRouteCandidate.PeerToPeer -> "p2p identity=${identity.deviceId}"
        is RuntimeRouteCandidate.Relay -> "relay identity=${identity.deviceId}"
    }
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

private fun RuntimeEndpointHint.isAllowedDirectEndpoint(): Boolean {
    if (port in LOCAL_MODEL_BACKEND_PORTS) return false
    if (source != RuntimeEndpointSource.Manual) return true
    return true
}

private fun TrustedRuntime.lastKnownEndpointHintOrNull(): RuntimeEndpointHint? {
    val endpointHost = host ?: return null
    val endpointPort = port ?: return null
    return RuntimeEndpointHint(
        host = endpointHost,
        port = endpointPort,
        source = RuntimeEndpointSource.TrustedLastKnown,
    )
}

private fun TrustedRuntime.toConnectionTarget(): RuntimeConnectionTarget {
    return RuntimeConnectionTarget(
        identity = PairedRuntimeIdentity(
            deviceId = deviceId,
            name = name,
            fingerprint = fingerprint,
            publicKeyBase64 = publicKeyBase64,
            routeToken = routeToken,
        ),
        endpointHint = lastKnownEndpointHintOrNull(),
    )
}

private fun RuntimePairingPayload.endpointHintOrNull(): RuntimeEndpointHint? {
    val endpointHost = host ?: return null
    val endpointPort = port ?: return null
    return RuntimeEndpointHint(
        host = endpointHost,
        port = endpointPort,
        source = RuntimeEndpointSource.PairingQr,
    )
}

internal fun RuntimeUiState.withPendingPairing(payload: RuntimePairingPayload): RuntimeUiState {
    val endpoint = if (payload.hasRelayRoute()) null else payload.endpointHintOrNull()
    return copy(
        pairingCode = payload.pairingCode,
        pendingPairingRuntimeName = payload.runtimeName,
        isPairingAwaitingRoute = endpoint == null && !payload.hasRelayRoute(),
        runtimeHost = endpoint?.host ?: runtimeHost,
        runtimePort = endpoint?.port?.toString() ?: runtimePort,
        runtimeEndpointSource = endpoint?.source ?: runtimeEndpointSource,
        runtimeStatus = if (endpoint == null && !payload.hasRelayRoute()) "pairing" else runtimeStatus,
        routeRefreshNoticeRuntimeName = null,
        error = null,
    )
}

internal fun RuntimeUiState.withClearedPendingPairing(): RuntimeUiState {
    return copy(
        pendingPairingRuntimeName = null,
        isPairingAwaitingRoute = false,
        runtimeStatus = if (runtimeStatus == "pairing") "disconnected" else runtimeStatus,
    )
}

internal fun RuntimeUiState.withTrustedRuntimeRouteFields(
    runtime: RuntimeTrustedRuntime,
    endpoint: RuntimeEndpointHint?,
): RuntimeUiState {
    return copy(
        trustedRuntime = runtime,
        runtimeHost = if (runtime.hasRelayRoute()) "" else endpoint?.host ?: runtimeHost,
        runtimePort = if (runtime.hasRelayRoute()) "" else endpoint?.port?.toString() ?: runtimePort,
        runtimeEndpointSource = if (runtime.hasRelayRoute()) {
            RuntimeEndpointSource.Manual
        } else {
            endpoint?.source ?: runtimeEndpointSource
        },
    )
}

private fun RuntimeTrustedRuntime.withoutRelayRoute(): RuntimeTrustedRuntime {
    return copy(
        relayHost = null,
        relayPort = null,
        relayId = null,
        relaySecret = null,
        relayExpiresAtEpochMillis = null,
        relayNonce = null,
        relayScope = null,
    )
}

private fun RuntimeTrustedRuntime.toTrustedRuntimeOrNull(): TrustedRuntime? {
    val cleanFingerprint = fingerprint?.takeIf(String::isNotBlank) ?: return null
    return TrustedRuntime(
        deviceId = deviceId,
        name = name,
        fingerprint = cleanFingerprint,
        publicKeyBase64 = publicKeyBase64,
        routeToken = routeToken,
        host = endpointHint?.host,
        port = endpointHint?.port,
        relayHost = relayHost,
        relayPort = relayPort,
        relayId = relayId,
        relaySecret = relaySecret,
        relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
        relayNonce = relayNonce,
        relayScope = relayScope,
    )
}

internal fun RuntimePairingPayload.toConnectionTarget(
    endpoint: RuntimeEndpointHint? = endpointHintOrNull(),
): RuntimeConnectionTarget {
    return RuntimeConnectionTarget(
        identity = PairedRuntimeIdentity(
            deviceId = runtimeDeviceId,
            name = runtimeName,
            fingerprint = fingerprint,
            publicKeyBase64 = runtimePublicKeyBase64,
            routeToken = routeToken,
        ),
        endpointHint = endpoint,
    )
}

internal fun pairingRuntimeConnectionTarget(
    state: RuntimeUiState,
    payload: RuntimePairingPayload,
): RuntimeConnectionTarget? {
    val endpoint = payload.endpointHintOrNull()
    if (payload.hasRelayRoute()) return payload.toConnectionTarget(endpoint = null)
    if (endpoint != null) return payload.toConnectionTarget(endpoint)

    val identityOnlyTarget = payload.toConnectionTarget(endpoint = null)
    val identity = requireNotNull(identityOnlyTarget.identity)
    val discovered = state.discoveredRuntimes.firstOrNull { discovered ->
        discovered.matchesTrustedIdentity(identity, allowMissingMetadata = false)
    } ?: return null

    return identityOnlyTarget.copy(
        endpointHint = RuntimeEndpointHint(
            host = discovered.host,
            port = discovered.port,
            source = RuntimeEndpointSource.BonjourDiscovery,
        )
    )
}

internal fun shouldPreemptActiveConnectionForPairingQr(
    state: RuntimeUiState,
    payload: RuntimePairingPayload,
): Boolean {
    if (!state.isConnected && !state.isConnecting) return false
    val trusted = state.trustedRuntime ?: return true
    if (trusted.deviceId != payload.runtimeDeviceId) return true
    if (!runtimePublicKeyMatches(payload.fingerprint, trusted.fingerprint)) return true
    if (!runtimePublicKeyMatches(payload.runtimePublicKeyBase64, trusted.publicKeyBase64)) return true
    return false
}

internal fun trustedRuntimeFromAcceptedPairing(
    pending: RuntimePairingPayload,
    payload: PairingResultPayload,
): TrustedRuntime? {
    if (pending.hasExpiredRemoteRoute()) return null
    val hasRelayRoute = pending.hasRelayRoute()
    val acceptedRuntimeDeviceId = payload.runtimeDeviceIdV2
        ?: payload.runtimeDeviceId
        ?: pending.runtimeDeviceId
    val acceptedFingerprint = payload.runtimeKeyFingerprint
        ?.takeIf(String::isNotBlank)
        ?: pending.fingerprint
    val acceptedPublicKey = payload.runtimePublicKey?.takeIf(String::isNotBlank)
        ?: pending.runtimePublicKeyBase64
    if (
        acceptedRuntimeDeviceId != pending.runtimeDeviceId ||
        acceptedFingerprint != pending.fingerprint ||
        !runtimePublicKeyMatches(pending.runtimePublicKeyBase64, acceptedPublicKey)
    ) {
        return null
    }
    return TrustedRuntime(
        deviceId = acceptedRuntimeDeviceId,
        name = pending.runtimeName,
        fingerprint = acceptedFingerprint,
        publicKeyBase64 = acceptedPublicKey,
        routeToken = pending.routeToken,
        host = null,
        port = null,
        relayHost = if (hasRelayRoute) pending.relayHost else null,
        relayPort = if (hasRelayRoute) pending.relayPort else null,
        relayId = if (hasRelayRoute) pending.relayId else null,
        relaySecret = if (hasRelayRoute) pending.relaySecret else null,
        relayExpiresAtEpochMillis = if (hasRelayRoute) pending.relayExpiresAtEpochMillis else null,
        relayNonce = if (hasRelayRoute) pending.relayNonce else null,
        relayScope = if (hasRelayRoute) pending.relayScope else null,
    )
}

internal fun trustedRuntimeFromRouteRefreshQr(
    current: RuntimeTrustedRuntime?,
    payload: RuntimePairingPayload,
): TrustedRuntime? {
    current ?: return null
    if (payload.hasExpiredRemoteRoute()) return null
    val hasRelayRoute = payload.hasRelayRoute()
    if (!hasRelayRoute) return null
    if (current.deviceId != payload.runtimeDeviceId) return null
    if (current.fingerprint != null && current.fingerprint != payload.fingerprint) return null
    if (
        current.publicKeyBase64 != null &&
        payload.runtimePublicKeyBase64 != current.publicKeyBase64
    ) {
        return null
    }
    return TrustedRuntime(
        deviceId = current.deviceId,
        name = payload.runtimeName.takeIf { it.isNotBlank() } ?: current.name,
        fingerprint = current.fingerprint ?: payload.fingerprint,
        publicKeyBase64 = current.publicKeyBase64 ?: payload.runtimePublicKeyBase64,
        routeToken = payload.routeToken ?: current.routeToken,
        host = null,
        port = null,
        relayHost = if (hasRelayRoute) payload.relayHost else null,
        relayPort = if (hasRelayRoute) payload.relayPort else null,
        relayId = if (hasRelayRoute) payload.relayId else null,
        relaySecret = if (hasRelayRoute) payload.relaySecret else null,
        relayExpiresAtEpochMillis = if (hasRelayRoute) payload.relayExpiresAtEpochMillis else null,
        relayNonce = if (hasRelayRoute) payload.relayNonce else null,
        relayScope = if (hasRelayRoute) payload.relayScope else null,
    )
}

internal fun trustedRuntimeFromRouteRefreshPayload(
    current: RuntimeTrustedRuntime?,
    payload: RouteRefreshPayload,
    nowEpochMillis: Long = System.currentTimeMillis(),
): TrustedRuntime? {
    current ?: return null
    val fingerprint = current.fingerprint ?: return null
    if (payload.runtimeDeviceId != current.deviceId) return null
    if (payload.runtimeKeyFingerprint != fingerprint) return null
    val candidateRuntime = current.copy(
        endpointHint = null,
        relayHost = payload.relayHost,
        relayPort = payload.relayPort,
        relayId = payload.relayId,
        relaySecret = payload.relaySecret,
        relayExpiresAtEpochMillis = payload.relayExpiresAtEpochMillis,
        relayNonce = payload.relayNonce,
        relayScope = payload.relayScope,
    )
    if (!candidateRuntime.hasRelayRoute(nowEpochMillis)) return null
    return TrustedRuntime(
        deviceId = current.deviceId,
        name = current.name,
        fingerprint = fingerprint,
        publicKeyBase64 = current.publicKeyBase64,
        routeToken = current.routeToken,
        host = null,
        port = null,
        relayHost = payload.relayHost,
        relayPort = payload.relayPort,
        relayId = payload.relayId,
        relaySecret = payload.relaySecret,
        relayExpiresAtEpochMillis = payload.relayExpiresAtEpochMillis,
        relayNonce = payload.relayNonce,
        relayScope = payload.relayScope,
    )
}

internal sealed class RuntimePairingQrParseResult {
    data class Accepted(val payload: RuntimePairingPayload) : RuntimePairingQrParseResult()
    data class Rejected(
        val error: RuntimeUiError,
        val clearPendingPairing: Boolean = false,
    ) : RuntimePairingQrParseResult()
}

internal fun parseRuntimePairingQrPayload(
    rawValue: String,
    allowDebugLoopbackRelay: Boolean,
    allowDiagnosticLocalDirectEndpoint: Boolean,
): RuntimePairingQrParseResult {
    val payload = runCatching {
        RuntimePairingPayloadParser.parse(
            rawValue = rawValue,
            allowDebugLoopbackRelay = allowDebugLoopbackRelay,
            allowDiagnosticLocalDirectEndpoint = allowDiagnosticLocalDirectEndpoint,
        )
    }.getOrElse { error ->
        return RuntimePairingQrParseResult.Rejected(pairingQrParseUiError(error))
    }
    if (payload.hasExpiredRemoteRoute()) {
        return RuntimePairingQrParseResult.Rejected(
            error = RuntimeUiError(
                code = "remote_route_expired",
                diagnosticCode = "route_diagnostic_remote_route_expired",
            ),
            clearPendingPairing = true,
        )
    }
    return RuntimePairingQrParseResult.Accepted(payload)
}

internal data class PendingPairingConnectionPlan(
    val pendingState: RuntimeUiState,
    val target: RuntimeConnectionTarget?,
    val shouldStartDiscovery: Boolean,
    val shouldWaitForDiscoveryRoute: Boolean,
)

internal fun pendingPairingConnectionPlan(
    state: RuntimeUiState,
    payload: RuntimePairingPayload,
): PendingPairingConnectionPlan {
    val pendingState = state.withPendingPairing(payload)
    return PendingPairingConnectionPlan(
        pendingState = pendingState,
        target = pairingRuntimeConnectionTarget(pendingState, payload),
        shouldStartDiscovery = payload.shouldWaitForDiscoveryRoute(),
        shouldWaitForDiscoveryRoute = payload.shouldWaitForDiscoveryRoute(),
    )
}

internal fun RuntimePairingPayload.shouldWaitForDiscoveryRoute(): Boolean {
    return endpointHintOrNull() == null && !hasRelayRoute()
}

internal fun pendingPairingExhaustedRouteError(payload: RuntimePairingPayload): RuntimeUiError {
    return if (payload.hasRelayRoute()) {
        RuntimeUiError(
            code = "remote_route_unreachable",
            diagnosticCode = "route_diagnostic_relay_failed",
        )
    } else {
        RuntimeUiError("pairing_endpoint_unavailable")
    }
}

internal fun pairingQrParseUiError(error: Throwable): RuntimeUiError {
    return when (error.message) {
        LOCAL_DIRECT_ENDPOINT_QR_ERROR -> RuntimeUiError(
            code = "pairing_direct_route_rejected",
            detail = error.message,
            diagnosticCode = "route_diagnostic_direct_qr_rejected",
        )
        RELAY_HOST_UNREACHABLE_QR_ERROR -> RuntimeUiError(
            code = "pairing_relay_route_rejected",
            detail = error.message,
            diagnosticCode = "route_diagnostic_relay_qr_unreachable",
        )
        else -> RuntimeUiError("invalid_pairing_qr", error.message)
    }
}

private fun TrustedRuntime.toRuntimeTrustedRuntime(): RuntimeTrustedRuntime {
    return RuntimeTrustedRuntime(
        deviceId = deviceId,
        name = name,
        fingerprint = fingerprint,
        publicKeyBase64 = publicKeyBase64,
        routeToken = routeToken,
        endpointHint = lastKnownEndpointHintOrNull(),
        relayHost = relayHost,
        relayPort = relayPort,
        relayId = relayId,
        relaySecret = relaySecret,
        relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
        relayNonce = relayNonce,
        relayScope = relayScope,
    )
}

internal fun RuntimeUiState.selectedModelSendState(): SelectedModelSendState {
    val selectedId = selectedModelId ?: return SelectedModelSendState.Missing
    val selectedModel = models.firstOrNull { it.id == selectedId }
        ?: return SelectedModelSendState.Missing
    return if (!selectedModel.isChatModel()) {
        SelectedModelSendState.Missing
    } else if (!selectedModel.isRuntimeHostLocalModel()) {
        SelectedModelSendState.Missing
    } else if (selectedModel.installed) {
        SelectedModelSendState.Ready
    } else {
        SelectedModelSendState.NotInstalled
    }
}

internal data class ChatTitleRequestCandidate(
    val sessionId: String,
    val model: String,
    val messages: List<ChatMessagePayload>,
    val locale: String?,
)

internal data class ChatSuggestionsRequestCandidate(
    val sessionId: String,
    val model: String,
    val messages: List<ChatMessagePayload>,
    val maxSuggestions: Int,
    val locale: String?,
)

internal fun chatSuggestionsRequestCandidate(
    sourceState: RuntimeUiState,
    isSessionAuthenticated: Boolean,
    requireMissingSuggestions: Boolean,
    maxContextMessages: Int,
    maxSuggestions: Int,
): ChatSuggestionsRequestCandidate? {
    if (!sourceState.isConnected || !isSessionAuthenticated) return null
    if (sourceState.isStreaming || sourceState.isLoadingSuggestions) return null
    if (sourceState.selectedModelSendState() != SelectedModelSendState.Ready) return null

    val sessionId = sourceState.activeChatSessionId ?: return null
    val model = sourceState.selectedModelId ?: return null
    val latestAssistant = sourceState.messages.lastOrNull { it.role == "assistant" && it.content.isNotBlank() }
        ?: return null
    if (requireMissingSuggestions && latestAssistant.suggestions.isNotEmpty()) return null

    val recentMessages = sourceState.messages
        .filter { it.role == "user" || it.role == "assistant" }
        .filter { it.content.isNotBlank() }
        .takeLast(maxContextMessages)
        .map { message ->
            ChatMessagePayload(
                role = message.role,
                content = message.content,
            )
        }
    if (recentMessages.size < 2) return null

    return ChatSuggestionsRequestCandidate(
        sessionId = sessionId,
        model = model,
        messages = recentMessages,
        maxSuggestions = maxSuggestions,
        locale = sourceState.runtimeRequestLocale(),
    )
}

internal fun chatTitleRequestCandidate(
    sourceState: RuntimeUiState,
    persistedRuntimeData: PersistedRuntimeData,
    isSessionAuthenticated: Boolean,
): ChatTitleRequestCandidate? {
    if (!sourceState.isConnected || !isSessionAuthenticated) return null
    if (sourceState.isStreaming) return null
    if (sourceState.selectedModelSendState() != SelectedModelSendState.Ready) return null

    val sessionId = sourceState.activeChatSessionId ?: return null
    val session = persistedRuntimeData.sessions.firstOrNull { it.id == sessionId } ?: return null
    if (session.archivedAtMillis != null || session.titleManuallyEdited || session.titleGenerated) return null

    val chatMessages = sourceState.messages
        .filter { it.role == "user" || it.role == "assistant" }
        .filter { it.content.isNotBlank() }
    if (chatMessages.count { it.role == "user" } != 1) return null
    if (chatMessages.count { it.role == "assistant" } != 1) return null

    val model = sourceState.selectedModelId ?: return null
    return ChatTitleRequestCandidate(
        sessionId = sessionId,
        model = model,
        messages = chatMessages.map { message ->
            ChatMessagePayload(
                role = message.role,
                content = message.content,
            )
        },
        locale = sourceState.runtimeRequestLocale(),
    )
}

internal fun RuntimeUiState.runtimeRequestLocale(): String {
    return RuntimeAppLanguage.normalizeLanguageTag(selectedLanguageTag)
}

internal fun attachmentOnlyPromptHeader(
    context: Context,
    languageTag: String,
): String {
    val normalizedLanguageTag = RuntimeAppLanguage.normalizeLanguageTag(languageTag)
    val locale = Locale.forLanguageTag(normalizedLanguageTag)
    val configuration = Configuration(context.resources.configuration)
    configuration.setLocale(locale)
    configuration.setLocales(LocaleList(locale))
    return context.createConfigurationContext(configuration)
        .getString(R.string.attachment_only_prompt_header)
}

internal fun attachmentOnlyPrompt(
    attachments: List<RuntimePendingAttachment>,
    promptHeader: String,
): String {
    return attachments.joinToString(
        separator = "\n",
        prefix = "${promptHeader.trimEnd()}\n",
    ) { "- ${it.name}" }
}

internal fun runtimeOwnedChatMutationRequiresConnectedRuntime(
    sessions: List<PersistedChatSession>,
    isSessionAuthenticated: Boolean,
    isTransportConnected: Boolean,
): Boolean {
    return sessions.any { it.runtimeOwned } && !(isSessionAuthenticated && isTransportConnected)
}

internal data class ReconciledModelSelections(
    val selectedModelId: String?,
    val selectedEmbeddingModelId: String?,
    val installedTargetModelId: String? = null,
)

internal fun reconcileModelSelections(
    currentSelectedModelId: String?,
    currentSelectedEmbeddingModelId: String?,
    models: List<RuntimeModel>,
    installTargetModelId: String? = null,
): ReconciledModelSelections {
    val chatModels = models.filter { it.isChatModel() && it.isRuntimeHostLocalModel() }
    val embeddingModels = models.filter { it.isEmbeddingModel() }
    val installedTarget = installTargetModelId?.let { target ->
        chatModels.firstOrNull { it.id == target && it.installed }
    }
    val selectedModelId = when {
        installedTarget != null -> installedTarget.id
        currentSelectedModelId == null -> chatModels.firstOrNull { it.installed }?.id
        models.any { it.id == currentSelectedModelId && !it.isChatModel() } -> null
        models.any { it.id == currentSelectedModelId && !it.isRuntimeHostLocalModel() } -> null
        else -> currentSelectedModelId
    }
    val selectedEmbeddingModelId = when {
        currentSelectedEmbeddingModelId == null -> null
        models.any { it.id == currentSelectedEmbeddingModelId && !it.isEmbeddingModel() } -> null
        models.any { it.id == currentSelectedEmbeddingModelId && it.isEmbeddingModel() && !it.installed } -> null
        models.any { it.id == currentSelectedEmbeddingModelId && it.isEmbeddingModel() && !it.isRuntimeHostLocalModel() } -> null
        else -> currentSelectedEmbeddingModelId
    }
    return ReconciledModelSelections(
        selectedModelId = selectedModelId,
        selectedEmbeddingModelId = selectedEmbeddingModelId,
        installedTargetModelId = installedTarget?.id,
    )
}

internal fun RuntimeModel.isChatModel(): Boolean {
    return !isEmbeddingModel() &&
        (modelKind == MODEL_KIND_CHAT || capabilities.any { it == "chat" || it == "completion" || it == "vision" || it == "image" })
}

internal fun RuntimeModel.isEmbeddingModel(): Boolean {
    return modelKind == MODEL_KIND_EMBEDDING || capabilities.any { it == "embedding" || it == "embed" }
}

internal fun RuntimeModel.supportsImageInput(): Boolean {
    return isChatModel() && capabilities.any { it == "vision" || it == "image" || it == "multimodal" }
}

internal fun RuntimeModel.isRuntimeHostLocalModel(): Boolean {
    val normalizedSource = source?.trim()?.lowercase()
    return normalizedSource == "local"
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
        updated[index] = item.withAssistantDelta(payload)
    }
    return copy(messages = updated)
}

private fun RuntimeChatMessage.withAssistantDelta(payload: ChatDeltaPayload): RuntimeChatMessage {
    val parsedContent = payload.content.extractInlineReasoning(
        startsInReasoning = isReasoningOpen,
        pendingTag = inlineReasoningPendingTag,
    )
    val answerDelta = if (content.isBlank()) {
        parsedContent.answer.trimStart()
    } else {
        parsedContent.answer
    }
    return copy(
        content = content + answerDelta,
        reasoning = reasoning + payload.reasoning + parsedContent.reasoning,
        isReasoningOpen = parsedContent.isReasoningOpen,
        inlineReasoningPendingTag = parsedContent.pendingTag,
        suggestions = emptyList(),
    )
}

internal fun RuntimeUiState.withChatDone(
    envelope: ProtocolEnvelope,
    payload: ChatDonePayload?,
): RuntimeUiState {
    if (activeRequestId != envelope.requestId) return this
    return copy(
        messages = messages
            .map { message ->
                if (message.role == "assistant") {
                    message.copy(
                        isReasoningOpen = false,
                        inlineReasoningPendingTag = "",
                    )
                } else {
                    message
                }
            }
            .withoutTrailingBlankAssistantPlaceholder(),
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
    val runtimeError = payload?.let { error -> RuntimeUiError(error.code, error.message) }
        ?: RuntimeUiError("runtime_error")
    val updated = copy(
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
        error = runtimeError,
    )
    return if (runtimeError.code.isPairingRequiredRuntimeCode()) {
        updated.withPairingRequiredRuntimeState(detail = runtimeError.detail)
    } else {
        updated
    }
}

internal fun RuntimeUiState.runtimeReceiveFailureUiError(error: Throwable): RuntimeUiError {
    if (activeRouteKind == RuntimeActiveRouteKind.Relay && error.isRelayFrameAuthenticationFailure()) {
        return RuntimeUiError(
            code = "remote_route_auth_failed",
            detail = error.message,
            diagnosticCode = "route_diagnostic_relay_auth_failed",
        )
    }
    return RuntimeUiError("receive_failed", error.message)
}

internal fun RuntimeUiState.withRuntimeReceiveFailure(detail: String?): RuntimeUiState =
    withRuntimeReceiveFailure(RuntimeUiError("receive_failed", detail))

internal fun RuntimeUiState.withRuntimeReceiveFailure(error: RuntimeUiError): RuntimeUiState {
    return copy(
        isConnected = false,
        isStreaming = false,
        isLoadingSuggestions = false,
        installingModelId = null,
        activeRequestId = null,
        runtimeStatus = "disconnected",
        activeRouteKind = null,
        messages = if (activeRequestId != null) {
            messages.withoutTrailingBlankAssistantPlaceholder()
        } else {
            messages
        },
        error = error,
    )
}

private fun Throwable.isRelayFrameAuthenticationFailure(): Boolean {
    var current: Throwable? = this
    while (current != null) {
        if (current is javax.crypto.AEADBadTagException) return true
        val message = current.message?.lowercase().orEmpty()
        if (
            "tag mismatch" in message ||
            "mac check failed" in message ||
            "authentication tag" in message
        ) {
            return true
        }
        current = current.cause
    }
    return false
}

private fun RuntimeUiError?.requiresFreshRemoteRouteBeforeReconnect(): Boolean {
    return this?.code == "remote_route_auth_failed" ||
        this?.code == "remote_route_unreachable" ||
        this?.code == "remote_route_expired" ||
        this?.diagnosticCode == "route_diagnostic_relay_auth_failed" ||
        this?.diagnosticCode == "route_diagnostic_relay_failed" ||
        this?.diagnosticCode == "route_diagnostic_remote_route_expired"
}

internal fun RuntimeUiState.withPairingRequiredRuntimeState(detail: String?): RuntimeUiState {
    return copy(
        isConnected = false,
        isConnecting = false,
        isStreaming = false,
        isLoadingModels = false,
        isLoadingSuggestions = false,
        installingModelId = null,
        activeRequestId = null,
        runtimeStatus = "pairing_required",
        backendAvailable = null,
        backendCode = null,
        providerStatuses = emptyList(),
        error = RuntimeUiError("pairing_required", detail),
    )
}

internal fun String?.isPairingRequiredRuntimeCode(): Boolean {
    return equals("pairing_required", ignoreCase = true) ||
        equals("authentication_required", ignoreCase = true)
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

internal fun String.extractInlineReasoning(startsInReasoning: Boolean = false): InlineReasoningDelta {
    return extractInlineReasoning(
        startsInReasoning = startsInReasoning,
        pendingTag = "",
    )
}

internal fun String.extractInlineReasoning(
    startsInReasoning: Boolean = false,
    pendingTag: String,
): InlineReasoningDelta {
    if (isEmpty()) {
        return InlineReasoningDelta(
            answer = "",
            reasoning = "",
            isReasoningOpen = startsInReasoning,
            pendingTag = pendingTag,
        )
    }

    val combined = pendingTag + this
    val pendingTagRange = combined.trailingPartialThinkTagRange()
    val text = if (pendingTagRange == null) {
        combined
    } else {
        combined.removeRange(pendingTagRange)
    }
    val nextPendingTag = pendingTagRange?.let { combined.substring(it) }.orEmpty()
    if (text.isEmpty()) {
        return InlineReasoningDelta(
            answer = "",
            reasoning = "",
            isReasoningOpen = startsInReasoning,
            pendingTag = nextPendingTag,
        )
    }

    val answer = StringBuilder()
    val reasoning = StringBuilder()
    var cursor = 0
    var isReasoningOpen = startsInReasoning

    while (cursor < text.length) {
        if (isReasoningOpen) {
            val closeTag = THINK_CLOSE_TAG_REGEX.find(text, cursor)
            if (closeTag == null) {
                reasoning.append(text.substring(cursor))
                cursor = text.length
            } else {
                reasoning.append(text.substring(cursor, closeTag.range.first))
                cursor = closeTag.range.last + 1
                isReasoningOpen = false
            }
        } else {
            val openTag = THINK_OPEN_TAG_REGEX.find(text, cursor)
            val strayCloseTag = THINK_CLOSE_TAG_REGEX.find(text, cursor)
            if (strayCloseTag != null && (openTag == null || strayCloseTag.range.first < openTag.range.first)) {
                answer.append(text.substring(cursor, strayCloseTag.range.first))
                cursor = strayCloseTag.range.last + 1
            } else if (openTag == null) {
                answer.append(text.substring(cursor))
                cursor = text.length
            } else {
                answer.append(text.substring(cursor, openTag.range.first))
                cursor = openTag.range.last + 1
                isReasoningOpen = true
            }
        }
    }

    return InlineReasoningDelta(
        answer = answer.toString(),
        reasoning = reasoning.toString(),
        isReasoningOpen = isReasoningOpen,
        pendingTag = nextPendingTag,
    )
}

internal data class InlineReasoningDelta(
    val answer: String,
    val reasoning: String,
    val isReasoningOpen: Boolean,
    val pendingTag: String = "",
)

private const val LOCAL_DIRECT_ENDPOINT_QR_ERROR = "Local direct endpoint QR routes are diagnostic-only"
private const val RELAY_HOST_UNREACHABLE_QR_ERROR = "Relay host is not reachable for remote pairing"
private val LOCAL_MODEL_BACKEND_PORTS = setOf(11434, 1234)
private val THINK_OPEN_TAG_REGEX = Regex("<\\s*(think|thinking)\\s*>", RegexOption.IGNORE_CASE)
private val THINK_CLOSE_TAG_REGEX = Regex("<\\s*/\\s*(think|thinking)\\s*>", RegexOption.IGNORE_CASE)
private val THINK_TAG_TOKENS = listOf(
    "<think>",
    "<thinking>",
    "</think>",
    "</thinking>",
)

private fun String.trailingPartialThinkTagRange(): IntRange? {
    val tagStart = lastIndexOf('<')
    if (tagStart < 0) return null
    val suffix = substring(tagStart).lowercase()
    if (suffix in THINK_TAG_TOKENS) return null
    return if (THINK_TAG_TOKENS.any { it.startsWith(suffix) }) {
        tagStart until length
    } else {
        null
    }
}
