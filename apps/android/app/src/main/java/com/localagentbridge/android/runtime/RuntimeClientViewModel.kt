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
import com.localagentbridge.android.core.protocol.CHAT_SOURCE_ATTRIBUTIONS_CAPABILITY
import com.localagentbridge.android.core.protocol.CHAT_SOURCE_ATTRIBUTION_RESOLVE_CAPABILITY
import com.localagentbridge.android.core.protocol.CHAT_SESSIONS_SYNC_CAPABILITY
import com.localagentbridge.android.core.protocol.ChatDeltaPayload
import com.localagentbridge.android.core.protocol.ChatDonePayload
import com.localagentbridge.android.core.protocol.ChatMessagePayload
import com.localagentbridge.android.core.protocol.ChatMessagesListRequestPayload
import com.localagentbridge.android.core.protocol.ChatMessagesListResultPayload
import com.localagentbridge.android.core.protocol.ChatSessionLifecyclePayload
import com.localagentbridge.android.core.protocol.ChatSessionRenamePayload
import com.localagentbridge.android.core.protocol.ChatSessionSummaryPayload
import com.localagentbridge.android.core.protocol.ChatSendPayload
import com.localagentbridge.android.core.protocol.ChatSourceAttributionPayload
import com.localagentbridge.android.core.protocol.ChatSourceAttributionResolveRequestPayload
import com.localagentbridge.android.core.protocol.ChatSourceAttributionResolveResultPayload
import com.localagentbridge.android.core.protocol.ChatSessionsListRequestPayload
import com.localagentbridge.android.core.protocol.ChatSessionsListResultPayload
import com.localagentbridge.android.core.protocol.ChatSessionsBulkLifecyclePayload
import com.localagentbridge.android.core.protocol.ChatSessionsBulkLifecycleResultPayload
import com.localagentbridge.android.core.protocol.ChatTitleRequestPayload
import com.localagentbridge.android.core.protocol.ChatTitleResultPayload
import com.localagentbridge.android.core.protocol.CitationResolveRequestPayload
import com.localagentbridge.android.core.protocol.CitationResolveResultPayload
import com.localagentbridge.android.core.protocol.ErrorPayload
import com.localagentbridge.android.core.protocol.HelloPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsListRequestPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsListResultPayload
import com.localagentbridge.android.core.protocol.IndexDocumentsSummaryPayload
import com.localagentbridge.android.core.protocol.MemoryDeletePayload
import com.localagentbridge.android.core.protocol.MemoryDeleteResultPayload
import com.localagentbridge.android.core.protocol.MEMORY_DUPLICATE_SUGGESTIONS_CAPABILITY
import com.localagentbridge.android.core.protocol.MemoryDuplicateSuggestionsListResultPayload
import com.localagentbridge.android.core.protocol.MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_CAPABILITY
import com.localagentbridge.android.core.protocol.MemorySemanticDuplicateSuggestionsListRequestPayload
import com.localagentbridge.android.core.protocol.MemorySemanticDuplicateSuggestionsListResultPayload
import com.localagentbridge.android.core.protocol.MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_CAPABILITY
import com.localagentbridge.android.core.protocol.MemorySemanticDuplicateClustersListRequestPayload
import com.localagentbridge.android.core.protocol.MemorySemanticDuplicateClustersListResultPayload
import com.localagentbridge.android.core.protocol.MemoryListRequestPayload
import com.localagentbridge.android.core.protocol.MemoryListResultPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftApprovePayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftApproveResultPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftDismissPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftDismissResultPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftGenerateRequestPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftGenerateResultPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftsListRequestPayload
import com.localagentbridge.android.core.protocol.MemorySummaryDraftsListResultPayload
import com.localagentbridge.android.core.protocol.MemoryUpsertPayload
import com.localagentbridge.android.core.protocol.MemoryUpsertResultPayload
import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.ModelPullPayload
import com.localagentbridge.android.core.protocol.ModelPullResultPayload
import com.localagentbridge.android.core.protocol.ModelsResultPayload
import com.localagentbridge.android.core.protocol.PairingRequestPayload
import com.localagentbridge.android.core.protocol.PairingResultPayload
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationChallenge
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationProof
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import com.localagentbridge.android.core.protocol.RetrievalQueryRequestPayload
import com.localagentbridge.android.core.protocol.RetrievalQueryResultPayload
import com.localagentbridge.android.core.protocol.RelayAllocationAuthorizationPayload
import com.localagentbridge.android.core.protocol.RelayAllocationChallengePayload
import com.localagentbridge.android.core.protocol.RouteRefreshPayload
import com.localagentbridge.android.core.protocol.RuntimeDocumentIndexDocumentPayload
import com.localagentbridge.android.core.protocol.RuntimeHealthPayload
import com.localagentbridge.android.core.protocol.RuntimeModelResidencyUnloadFailurePayload
import com.localagentbridge.android.core.protocol.TrustedSourceApproveRequestPayload
import com.localagentbridge.android.core.protocol.TrustedSourceApproveResultPayload
import com.localagentbridge.android.core.protocol.TrustedSourceDismissRequestPayload
import com.localagentbridge.android.core.protocol.TrustedSourceDismissResultPayload
import com.localagentbridge.android.core.protocol.TrustedSourceListRequestPayload
import com.localagentbridge.android.core.protocol.TrustedSourceListResultPayload
import com.localagentbridge.android.core.protocol.TrustedSourcePayload
import com.localagentbridge.android.core.protocol.TrustedSourceRevokeRequestPayload
import com.localagentbridge.android.core.protocol.TrustedSourceRevokeResultPayload
import com.localagentbridge.android.core.protocol.isCanonicalProviderQualifiedModelId
import com.localagentbridge.android.core.pairing.DeviceIdentity
import com.localagentbridge.android.core.pairing.DeviceIdentityStore
import com.localagentbridge.android.core.pairing.INITIAL_PAIRING_PROOF_SCHEME
import com.localagentbridge.android.core.pairing.InitialPairingAcceptedResult
import com.localagentbridge.android.core.pairing.InitialPairingClientRequest
import com.localagentbridge.android.core.pairing.InitialPairingProof
import com.localagentbridge.android.core.pairing.PairedRelayAllocationAuthorization
import com.localagentbridge.android.core.pairing.PairedRelayAllocationAuthorizationProof
import com.localagentbridge.android.core.pairing.RuntimePairingPayload
import com.localagentbridge.android.core.pairing.RuntimePairingPayloadParser
import com.localagentbridge.android.core.pairing.PairingStore
import com.localagentbridge.android.core.pairing.RuntimeIdentityProofVerifier
import com.localagentbridge.android.core.pairing.TrustedRuntime
import com.localagentbridge.android.core.pairing.isCanonicalOpaqueRouteValue
import com.localagentbridge.android.core.transport.BonjourDiscovery
import com.localagentbridge.android.core.transport.DiscoveredRuntime
import com.localagentbridge.android.core.transport.RuntimeTransportClient
import com.localagentbridge.android.core.transport.PairedRuntimeIdentity
import com.localagentbridge.android.core.transport.PreparedRemoteRuntimeRoute
import com.localagentbridge.android.core.transport.RuntimeConnectionFailure
import com.localagentbridge.android.core.transport.RuntimeConnectionFailureReason
import com.localagentbridge.android.core.transport.RuntimeConnectionManager
import com.localagentbridge.android.core.transport.RuntimeConnectionTarget
import com.localagentbridge.android.core.transport.RuntimeEndpointHint
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import com.localagentbridge.android.core.transport.RuntimeProtocolChannel
import com.localagentbridge.android.core.transport.RuntimePeerToPeerConnector
import com.localagentbridge.android.core.transport.RuntimeRelayConnector
import com.localagentbridge.android.core.transport.RelayClientRegistrationAuthorizer
import com.localagentbridge.android.core.transport.RuntimeRelayTcpClient
import com.localagentbridge.android.core.transport.RuntimeRouteCandidate
import com.localagentbridge.android.core.transport.RuntimeRouteCapability
import com.localagentbridge.android.core.transport.RuntimeRouteResolver
import com.localagentbridge.android.core.transport.RuntimeRouteRejectionReason
import com.localagentbridge.android.core.transport.RuntimeRouteSource
import com.localagentbridge.android.core.transport.RuntimeTransportConnector
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.security.MessageDigest
import java.time.Instant
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
    fun readBytes(reference: String, maxBytes: Int): ByteArray?
}

internal enum class RuntimeRelayProbeResult {
    Ready,
    Unavailable,
    Unsupported,
}

internal fun interface RuntimeRelayReachabilityChecker {
    suspend fun check(
        route: PreparedRemoteRuntimeRoute.Relay,
        timeoutMillis: Int,
    ): RuntimeRelayProbeResult
}

private sealed interface PendingChatSessionMutation {
    val sessionId: String
    val sequence: Long
}

private data class PendingChatSessionsListRun(
    var requestId: String,
    val query: String?,
    val channel: RuntimeProtocolChannel,
    val connectionGeneration: Long,
    val authorityGeneration: Long,
    val summaries: MutableList<ChatSessionSummaryPayload> = mutableListOf(),
    val sessionIds: MutableSet<String> = mutableSetOf(),
    val cursors: MutableSet<String> = mutableSetOf(),
    var snapshotCount: Int? = null,
    var pageCount: Int = 0,
)

private data class PendingChatSessionsBulkLifecycle(
    var requestId: String,
    val type: String,
    val scope: String,
    val channel: RuntimeProtocolChannel,
    val connectionGeneration: Long,
    val authorityGeneration: Long,
    var batchCount: Int = 0,
    var cumulativeAffectedCount: Int = 0,
)

private data class RuntimeChatHistoryRequestCorrelation(
    val requestId: String,
    val type: String,
    val channel: RuntimeProtocolChannel,
    val connectionGeneration: Long,
    val authorityGeneration: Long,
)

private val REQUEST_BOUND_SEND_FAILURE_TYPES = setOf(
    MessageType.PairingRequest,
    MessageType.Hello,
    MessageType.AuthResponse,
    MessageType.ChatSessionsList,
    MessageType.ChatMessagesList,
    MessageType.ChatTitleRequest,
    MessageType.ChatSessionRename,
    MessageType.ChatSessionArchive,
    MessageType.ChatSessionRestore,
    MessageType.ChatSessionDelete,
    MessageType.ModelsList,
    MessageType.MemoryList,
    MessageType.MemoryDuplicateSuggestionsList,
    MessageType.MemorySemanticDuplicateClustersList,
    MessageType.MemorySummaryDraftsList,
    MessageType.MemorySummaryDraftGenerate,
    MessageType.MemorySummaryDraftApprove,
    MessageType.MemorySummaryDraftDismiss,
    MessageType.IndexDocumentsList,
    MessageType.RetrievalQuery,
    MessageType.CitationResolve,
    MessageType.ChatSourceAttributionResolve,
    MessageType.TrustedSourceApprove,
    MessageType.TrustedSourceDismiss,
    MessageType.TrustedSourceList,
    MessageType.TrustedSourceRevoke,
    MessageType.RouteRefresh,
    MessageType.RelayAllocationAuthorization,
)

private data class PendingChatSessionLifecycleMutation(
    override val sessionId: String,
    override val sequence: Long,
    val type: String,
    val previousSession: PersistedChatSession,
    val restoreAsActive: Boolean,
) : PendingChatSessionMutation

private data class PendingChatSessionRenameMutation(
    override val sessionId: String,
    override val sequence: Long,
    val previousTitle: String,
    val previousTitleManuallyEdited: Boolean,
    val previousTitleGenerated: Boolean,
    val previousUpdatedAtMillis: Long,
) : PendingChatSessionMutation

private data class PendingMemorySummaryDraftGeneration(
    val draft: RuntimeMemorySummaryDraft,
    val modelId: String,
)

private data class PendingMemoryDuplicateSuggestionsRequest(
    val requestId: String,
    val channel: RuntimeProtocolChannel,
    val connectionGeneration: Long,
    val authorityGeneration: Long,
)

private data class PendingModelsListRequest(
    val requestId: String,
    val channel: RuntimeProtocolChannel,
    val connectionGeneration: Long,
    val authorityGeneration: Long,
)

private data class PendingMemorySemanticDuplicateSuggestionsRequest(
    val requestId: String,
    val channel: RuntimeProtocolChannel,
    val connectionGeneration: Long,
    val authorityGeneration: Long,
    val embeddingModelId: String,
    val minimumSimilarityBasisPoints: Int,
)

private data class PendingMemorySemanticDuplicateClustersRequest(
    val requestId: String,
    val channel: RuntimeProtocolChannel,
    val connectionGeneration: Long,
    val authorityGeneration: Long,
    val memoryCatalogGeneration: Long,
    val modelCatalogGeneration: Long,
    val embeddingModelId: String,
    val minimumSimilarityBasisPoints: Int,
)

private data class PendingSourceReview(
    val sourceAnchorId: String,
    val citationId: String,
    val reviewId: String,
    val confirmationToken: String,
    val disclosureVersion: String,
    val usageScope: String,
)

private data class PendingHistoricalSourceAttributionResolve(
    val requestId: String,
    val sessionId: String,
    val localMessageId: String,
    val assistantMessageId: String,
    val sourceAttribution: RuntimeChatSourceAttribution,
    val channel: RuntimeProtocolChannel,
    val connectionGeneration: Long,
)


private data class PendingInitialPairingRequest(
    val payload: RuntimePairingPayload,
    val requestId: String,
    val requestDigest: String,
    val clientDeviceId: String,
    val transportBinding: String?,
)

private enum class RuntimeAuthenticationPhase {
    PreparingHello,
    AwaitingChallenge,
    SendingResponse,
    AwaitingFinalResponse,
}

private data class PendingRuntimeAuthentication(
    val helloRequestId: String,
    val channel: RuntimeProtocolChannel,
    val connectionGeneration: Long,
    val forcePairedClaim: Boolean?,
    val attempt: Int,
    val phase: RuntimeAuthenticationPhase,
    val identity: DeviceIdentity? = null,
    val challengeRequestId: String? = null,
)

private data class PendingPairedRelayAllocationAuthorization(
    val requestId: String,
    val authorizationId: String,
    val challenge: String,
    val relayId: String,
    val relayExpiresAtEpochMillis: Long,
    val relayNonce: String,
    val ticketGeneration: Long,
    val transportBinding: String,
    val clientKeyFingerprint: String,
)

internal data class RuntimeClientViewModelDependencies(
    val json: Json,
    val transportClient: RuntimeTransportClient,
    val transportConnector: RuntimeTransportConnector,
    val relayConnector: RuntimeRelayConnector,
    val peerToPeerConnector: RuntimePeerToPeerConnector? = null,
    val discovery: RuntimeDiscoverySource,
    val trustedRuntimeStore: RuntimeTrustedRuntimeStore,
    val deviceIdentityProvider: RuntimeDeviceIdentityProvider,
    val localDataStore: RuntimeLocalDataStore,
    val lifecycleCallbacksRegistrar: RuntimeLifecycleCallbacksRegistrar,
    val attachmentReader: RuntimeAttachmentReader? = null,
    val attachmentPromptHeaderProvider: ((String) -> String)? = null,
    val relayReachabilityChecker: RuntimeRelayReachabilityChecker = RuntimeRelayReachabilityChecker { _, _ ->
        RuntimeRelayProbeResult.Ready
    },
    val authenticatedRouteRefreshEnabled: Boolean = false,
    val currentTimeMillis: () -> Long = { System.currentTimeMillis() },
) {
    companion object {
        fun create(application: Application): RuntimeClientViewModelDependencies {
            val json = runtimeClientJson()
            val transportClient = RuntimeTransportClient()
            val deviceIdentityProvider = AndroidDeviceIdentityProvider(DeviceIdentityStore(application))
            return RuntimeClientViewModelDependencies(
                json = json,
                transportClient = transportClient,
                transportConnector = RuntimeTransportConnector { host, port, timeoutMillis ->
                    transportClient.connect(host = host, port = port, timeoutMillis = timeoutMillis)
                },
                relayConnector = RuntimeRelayTcpClient(
                    clientRegistrationAuthorizer = AndroidRelayClientRegistrationAuthorizer(
                        deviceIdentityProvider,
                    ),
                ),
                discovery = AndroidRuntimeDiscoverySource(BonjourDiscovery(application)),
                trustedRuntimeStore = AndroidTrustedRuntimeStore(PairingStore(application)),
                deviceIdentityProvider = deviceIdentityProvider,
                localDataStore = AndroidRuntimeLocalDataStore(RuntimeLocalStore(application, json)),
                lifecycleCallbacksRegistrar = AndroidRuntimeLifecycleCallbacksRegistrar,
                attachmentReader = AndroidRuntimeAttachmentReader(application),
                attachmentPromptHeaderProvider = { languageTag ->
                    attachmentOnlyPromptHeader(application, languageTag)
                },
                relayReachabilityChecker = AndroidRuntimeRelayReachabilityChecker(),
                authenticatedRouteRefreshEnabled = false,
            )
        }
    }
}

private class AndroidRuntimeRelayReachabilityChecker : RuntimeRelayReachabilityChecker {
    override suspend fun check(
        route: PreparedRemoteRuntimeRoute.Relay,
        timeoutMillis: Int,
    ): RuntimeRelayProbeResult = withContext(Dispatchers.IO) {
        val socket = runCatching { Socket() }.getOrElse {
            return@withContext RuntimeRelayProbeResult.Unavailable
        }
        try {
            socket.tcpNoDelay = true
            socket.soTimeout = timeoutMillis
            try {
                socket.connect(InetSocketAddress(route.host, route.port), timeoutMillis)
            } catch (_: Exception) {
                return@withContext RuntimeRelayProbeResult.Unavailable
            }
            runCatching {
                val request = "AETHERLINK_RELAY probe ${route.relayId.sanitizeRelayProbeToken()}\n"
                socket.outputStream.write(request.toByteArray(Charsets.UTF_8))
                socket.outputStream.flush()
                socket.inputStream.readAsciiLine(maxBytes = 256).relayProbeResult()
            }.getOrDefault(RuntimeRelayProbeResult.Unsupported)
        } finally {
            runCatching { socket.close() }
        }
    }
}

private fun String.sanitizeRelayProbeToken(): String {
    require(isNotBlank()) { "Relay token must not be blank" }
    require(none { it <= ' ' }) { "Relay token must not contain whitespace" }
    return this
}

internal fun String.isRelayProbeReady(): Boolean {
    val response = relayProbeResponseOrNull() ?: return false
    return response.known && response.runtimeWaiting
}

internal fun String.isRelayProbeKnown(): Boolean {
    return relayProbeResponseOrNull()?.known == true
}

internal fun String.relayProbeResult(): RuntimeRelayProbeResult {
    val response = relayProbeResponseOrNull() ?: return RuntimeRelayProbeResult.Unsupported
    return if (response.known) {
        RuntimeRelayProbeResult.Ready
    } else {
        RuntimeRelayProbeResult.Unavailable
    }
}

private data class RelayProbeResponseFlags(
    val known: Boolean,
    val runtimeWaiting: Boolean,
)

private fun String.relayProbeResponseOrNull(): RelayProbeResponseFlags? {
    val tokens = trim().split(Regex("\\s+")).filter { it.isNotBlank() }
    if (tokens.size != 4 || tokens[0] != "AETHERLINK_RELAY" || tokens[1] != "probe") {
        return null
    }
    val values = mutableMapOf<String, Boolean>()
    for (token in tokens.drop(2)) {
        val separator = token.indexOf('=')
        if (separator <= 0 || separator == token.lastIndex || token.indexOf('=', separator + 1) >= 0) {
            return null
        }
        val key = token.substring(0, separator)
        if (key !in RELAY_PROBE_RESPONSE_KEYS || key in values) return null
        val value = token.substring(separator + 1).relayProbeBooleanOrNull() ?: return null
        values[key] = value
    }
    val routeStatusKeys = values.keys.intersect(RELAY_PROBE_ROUTE_STATUS_KEYS)
    if (routeStatusKeys.size != 1 || "runtime_waiting" !in values) return null
    return RelayProbeResponseFlags(
        known = values.getValue(routeStatusKeys.single()),
        runtimeWaiting = values.getValue("runtime_waiting"),
    )
}

private val RELAY_PROBE_ROUTE_STATUS_KEYS = setOf("known", "allocated")
private val RELAY_PROBE_RESPONSE_KEYS = RELAY_PROBE_ROUTE_STATUS_KEYS + "runtime_waiting"

private fun String.relayProbeBooleanOrNull(): Boolean? {
    return when {
        this == "1" || equals("true", ignoreCase = true) || equals("yes", ignoreCase = true) -> true
        this == "0" || equals("false", ignoreCase = true) || equals("no", ignoreCase = true) -> false
        else -> null
    }
}

private fun java.io.InputStream.readAsciiLine(maxBytes: Int): String {
    val buffer = StringBuilder()
    while (buffer.length < maxBytes) {
        val next = read()
        if (next == -1) break
        if (next == '\n'.code) return buffer.toString().trimEnd('\r')
        buffer.append(next.toChar())
    }
    error("Relay probe response was not a complete line")
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

private class AndroidRelayClientRegistrationAuthorizer(
    private val identityProvider: RuntimeDeviceIdentityProvider,
) : RelayClientRegistrationAuthorizer {
    override suspend fun authorize(
        challenge: PairedClientRelayRegistrationChallenge,
    ): PairedClientRelayRegistrationProof {
        val identity = identityProvider.loadOrCreate()
        return PairedClientRelayRegistrationProof(
            clientPublicKeyBase64 = identity.publicKeyBase64,
            clientSignatureBase64 = identity.signPairedClientRelayRegistrationAuthorization(
                challenge,
            ),
        )
    }
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

    override fun readBytes(reference: String, maxBytes: Int): ByteArray? {
        val uri = Uri.parse(reference)
        val resolver = application.contentResolver
        return runCatching {
            resolver.openInputStream(uri)?.use { input ->
                val boundedSize = maxBytes + 1
                val output = ByteArrayOutputStream(boundedSize.coerceAtMost(DEFAULT_BUFFER_SIZE))
                val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                var totalBytes = 0
                while (totalBytes < boundedSize) {
                    val bytesToRead = minOf(buffer.size, boundedSize - totalBytes)
                    val bytesRead = input.read(buffer, 0, bytesToRead)
                    if (bytesRead == -1) break
                    output.write(buffer, 0, bytesRead)
                    totalBytes += bytesRead
                }
                output.toByteArray()
            }
        }.getOrNull()
    }
}

private fun runtimeClientJson(): Json = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
    encodeDefaults = true
}

private val ERROR_PAYLOAD_KEYS = setOf(
    "code",
    "message",
    "retryable",
)

private fun JsonObject.errorPayloadUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in ERROR_PAYLOAD_KEYS }
}

private val AUTH_RESPONSE_RESULT_PAYLOAD_KEYS = setOf(
    "accepted",
    "device_id",
    "message",
    "transport_binding",
)

private fun JsonObject.authResponseResultUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in AUTH_RESPONSE_RESULT_PAYLOAD_KEYS }
}

private val PAIRING_RESULT_PAYLOAD_KEYS = setOf(
    "accepted",
    "mac_device_id",
    "runtime_device_id",
    "runtime_public_key",
    "runtime_key_fingerprint",
    "trusted_device_id",
    "message",
    "pairing_proof_scheme",
    "pairing_request_digest",
    "runtime_pairing_signature",
    "transport_binding",
    "code",
    "retryable",
    "failed_attempts",
    "max_failed_attempts",
    "remaining_attempts",
)

private val PAIRING_REJECTION_RESULT_PAYLOAD_KEYS = setOf(
    "code",
    "retryable",
    "failed_attempts",
    "max_failed_attempts",
    "remaining_attempts",
)

private fun JsonObject.pairingResultUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in PAIRING_RESULT_PAYLOAD_KEYS }
}

private val AUTH_CHALLENGE_PAYLOAD_KEYS = setOf(
    "device_id",
    "nonce",
    "runtime_key_fingerprint",
    "runtime_signature",
    "transport_binding",
)

private fun JsonObject.authChallengeUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in AUTH_CHALLENGE_PAYLOAD_KEYS }
}

private fun authenticationTransportBindingMatches(actual: String?, expected: String?): Boolean {
    if (expected == null) return actual == null
    return DeviceIdentity.isCanonicalTransportBinding(expected) && actual == expected
}

private val ROUTE_REFRESH_RESPONSE_PAYLOAD_KEYS = setOf(
    "runtime_device_id",
    "runtime_key_fingerprint",
    "relay_host",
    "relay_port",
    "relay_id",
    "relay_secret",
    "relay_expires_at",
    "relay_nonce",
    "relay_scope",
    "ticket_generation",
    "p2p_class",
    "p2p_record_id",
    "p2p_encrypted_body",
    "p2p_expires_at",
    "p2p_anti_replay_nonce",
    "p2p_protocol_version",
)

private fun JsonObject.hasOnlyRouteRefreshResponsePayloadKeys(): Boolean =
    keys.all { it in ROUTE_REFRESH_RESPONSE_PAYLOAD_KEYS }

private val MODELS_RESULT_PAYLOAD_KEYS = setOf("models")

private val MODEL_INFO_PAYLOAD_KEYS = setOf(
    "id",
    "name",
    "backend",
    "provider",
    "model_kind",
    "kind",
    "capabilities",
    "provider_model_id",
    "qualified_id",
    "installed",
    "running",
    "source",
    "description",
    "size_bytes",
    "context_window_tokens",
    "modified_at",
    "remote_model",
)

private fun JsonObject.modelsResultUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in MODELS_RESULT_PAYLOAD_KEYS }?.let { return it }
    val models = this["models"] as? JsonArray ?: return null
    models.forEachIndexed { index, element ->
        val model = element as? JsonObject ?: return@forEachIndexed
        model.keys.firstOrNull { it !in MODEL_INFO_PAYLOAD_KEYS }?.let {
            return "models[$index].$it"
        }
    }
    return null
}

private val MODEL_PULL_RESULT_PAYLOAD_KEYS = setOf(
    "model",
    "id",
    "backend",
    "provider",
    "accepted",
    "success",
    "status",
    "installed",
    "message",
)

private fun JsonObject.modelPullResultUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in MODEL_PULL_RESULT_PAYLOAD_KEYS }
}

private val RUNTIME_HEALTH_PAYLOAD_KEYS = setOf(
    "status",
    "ollama",
    "lm_studio",
    "model_residency",
)

private val RUNTIME_BACKEND_HEALTH_PAYLOAD_KEYS = setOf(
    "available",
    "message",
    "code",
    "retryable",
)

private val RUNTIME_MODEL_RESIDENCY_PAYLOAD_KEYS = setOf(
    "supported",
    "active_provider",
    "active_model_id",
    "in_flight_generations",
    "idle_unload_delay_seconds",
    "last_unload_failure",
)

private val RUNTIME_MODEL_RESIDENCY_UNLOAD_FAILURE_PAYLOAD_KEYS = setOf(
    "provider",
    "model_id",
    "reason",
)

private fun JsonObject.runtimeHealthUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in RUNTIME_HEALTH_PAYLOAD_KEYS }?.let { return it }
    val ollama = this["ollama"] as? JsonObject
    ollama?.keys?.firstOrNull { it !in RUNTIME_BACKEND_HEALTH_PAYLOAD_KEYS }?.let {
        return "ollama.$it"
    }
    val lmStudio = this["lm_studio"] as? JsonObject
    lmStudio?.keys?.firstOrNull { it !in RUNTIME_BACKEND_HEALTH_PAYLOAD_KEYS }?.let {
        return "lm_studio.$it"
    }
    val modelResidency = this["model_residency"] as? JsonObject
    modelResidency?.keys?.firstOrNull { it !in RUNTIME_MODEL_RESIDENCY_PAYLOAD_KEYS }?.let {
        return "model_residency.$it"
    }
    val lastUnloadFailure = modelResidency?.get("last_unload_failure") as? JsonObject
    lastUnloadFailure?.keys?.firstOrNull { it !in RUNTIME_MODEL_RESIDENCY_UNLOAD_FAILURE_PAYLOAD_KEYS }?.let {
        return "model_residency.last_unload_failure.$it"
    }
    return null
}

private val CHAT_SESSIONS_LIST_RESULT_PAYLOAD_KEYS = setOf(
    "sessions",
    "snapshot_count",
    "next_cursor",
)

private val CHAT_SESSIONS_BULK_LIFECYCLE_RESULT_PAYLOAD_KEYS = setOf(
    "scope",
    "status",
    "affected_count",
    "remaining_count",
    "completed_at",
)

private val CHAT_SESSION_SUMMARY_PAYLOAD_KEYS = setOf(
    "session_id",
    "title",
    "model",
    "last_activity_at",
    "message_count",
    "status",
    "archived_at",
    "last_event",
    "last_finish_reason",
    "last_error_code",
    "search",
)

private val CHAT_SESSION_SEARCH_PAYLOAD_KEYS = setOf(
    "rank",
    "snippet",
    "matched_fields",
)

private fun JsonObject.chatSessionsListUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in CHAT_SESSIONS_LIST_RESULT_PAYLOAD_KEYS }?.let { return it }
    val sessions = this["sessions"] as? JsonArray ?: return null
    sessions.forEachIndexed { index, element ->
        val session = element as? JsonObject ?: return@forEachIndexed
        session.keys.firstOrNull { it !in CHAT_SESSION_SUMMARY_PAYLOAD_KEYS }?.let {
            return "sessions[$index].$it"
        }
        val search = session["search"] as? JsonObject ?: return@forEachIndexed
        search.keys.firstOrNull { it !in CHAT_SESSION_SEARCH_PAYLOAD_KEYS }?.let {
            return "sessions[$index].search.$it"
        }
    }
    return null
}

private fun JsonObject.chatSessionsBulkLifecycleResultUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in CHAT_SESSIONS_BULK_LIFECYCLE_RESULT_PAYLOAD_KEYS }
}

private val CHAT_MESSAGES_LIST_RUNTIME_ONLY_PAYLOAD_KEYS = setOf(
    "compaction_metadata",
    "source_pointers",
)

private val CHAT_MESSAGES_LIST_RESULT_PAYLOAD_KEYS = setOf(
    "session_id",
    "messages",
) + CHAT_MESSAGES_LIST_RUNTIME_ONLY_PAYLOAD_KEYS

private val CHAT_STORED_MESSAGE_PAYLOAD_KEYS = setOf(
    "role",
    "content",
    "reasoning",
    "attachments",
    "source_attributions",
    "assistant_message_id",
    "created_at",
) + CHAT_MESSAGES_LIST_RUNTIME_ONLY_PAYLOAD_KEYS

private val CHAT_STORED_ATTACHMENT_PAYLOAD_KEYS = setOf(
    "type",
    "mime_type",
    "name",
    "text",
)

private val CHAT_SOURCE_ATTRIBUTION_PAYLOAD_KEYS = setOf(
    "source_index",
    "document_name",
    "mime_type",
    "chunk_index",
)

private fun JsonObject.chatMessagesListUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in CHAT_MESSAGES_LIST_RESULT_PAYLOAD_KEYS }?.let { return it }
    val messages = this["messages"] as? JsonArray ?: return null
    messages.forEachIndexed { messageIndex, element ->
        val message = element as? JsonObject ?: return@forEachIndexed
        message.keys.firstOrNull { it !in CHAT_STORED_MESSAGE_PAYLOAD_KEYS }?.let {
            return "messages[$messageIndex].$it"
        }
        val attachments = message["attachments"] as? JsonArray
        attachments?.forEachIndexed { attachmentIndex, attachmentElement ->
            val attachment = attachmentElement as? JsonObject ?: return@forEachIndexed
            attachment.keys.firstOrNull { it !in CHAT_STORED_ATTACHMENT_PAYLOAD_KEYS }?.let {
                return "messages[$messageIndex].attachments[$attachmentIndex].$it"
            }
        }
        val sourceAttributions = message["source_attributions"] as? JsonArray
        sourceAttributions?.forEachIndexed { attributionIndex, attributionElement ->
            val attribution = attributionElement as? JsonObject ?: return@forEachIndexed
            attribution.keys.firstOrNull { it !in CHAT_SOURCE_ATTRIBUTION_PAYLOAD_KEYS }?.let {
                return "messages[$messageIndex].source_attributions[$attributionIndex].$it"
            }
        }
    }
    return null
}

private val CHAT_DELTA_PAYLOAD_KEYS = setOf(
    "delta",
    "text",
    "reasoning_delta",
    "thinking_delta",
)

private fun JsonObject.chatDeltaUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in CHAT_DELTA_PAYLOAD_KEYS }
}

private val CHAT_DONE_PAYLOAD_KEYS = setOf(
    "finish_reason",
    "usage",
    "source_attributions",
    "assistant_message_id",
)

private val CHAT_DONE_USAGE_PAYLOAD_KEYS = setOf(
    "input_tokens",
    "output_tokens",
)

private fun JsonObject.chatDoneUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in CHAT_DONE_PAYLOAD_KEYS }?.let { return it }
    val usage = this["usage"] as? JsonObject
    usage?.keys?.firstOrNull { it !in CHAT_DONE_USAGE_PAYLOAD_KEYS }?.let {
        return "usage.$it"
    }
    val sourceAttributions = this["source_attributions"] as? JsonArray
    sourceAttributions?.forEachIndexed { index, element ->
        val attribution = element as? JsonObject ?: return@forEachIndexed
        attribution.keys.firstOrNull { it !in CHAT_SOURCE_ATTRIBUTION_PAYLOAD_KEYS }?.let {
            return "source_attributions[$index].$it"
        }
    }
    return null
}

private val CHAT_CANCEL_ACK_PAYLOAD_KEYS = setOf(
    "target_request_id",
    "cancelled",
)

private fun JsonObject.chatCancelAckUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in CHAT_CANCEL_ACK_PAYLOAD_KEYS }
}

private val CHAT_TITLE_RESULT_PAYLOAD_KEYS = setOf("title")

private fun JsonObject.chatTitleResultUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in CHAT_TITLE_RESULT_PAYLOAD_KEYS }
}

private val CHAT_SESSION_RENAME_RESULT_PAYLOAD_KEYS = setOf(
    "session_id",
    "title",
    "renamed_at",
)

private fun JsonObject.chatSessionRenameResultUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in CHAT_SESSION_RENAME_RESULT_PAYLOAD_KEYS }
}

private val CHAT_SESSION_LIFECYCLE_RESULT_PAYLOAD_KEYS = setOf(
    "session_id",
    "status",
    "archived_at",
    "restored_at",
    "deleted_at",
)

private fun JsonObject.chatSessionLifecycleResultUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in CHAT_SESSION_LIFECYCLE_RESULT_PAYLOAD_KEYS }
}

private val RUNTIME_DOCUMENT_INDEX_DOCUMENT_PAYLOAD_KEYS = setOf(
    "id",
    "display_name",
    "mime_type",
    "content_fingerprint",
    "extracted_character_count",
    "chunk_count",
    "quality",
)

private val INDEX_DOCUMENTS_LIST_RESULT_PAYLOAD_KEYS = setOf(
    "documents",
    "summary",
)

private val INDEX_DOCUMENTS_SUMMARY_PAYLOAD_KEYS = setOf(
    "document_count",
    "chunk_count",
    "extracted_character_count",
    "quality_counts",
)

private val INDEX_DOCUMENTS_QUALITY_COUNTS_PAYLOAD_KEYS = setOf(
    "no_usable_text",
    "single_chunk",
    "chunked",
)

private val RETRIEVAL_QUERY_RESULT_PAYLOAD_KEYS = setOf("results")

private val RETRIEVAL_QUERY_RESULT_ITEM_PAYLOAD_KEYS = setOf(
    "document",
    "source_anchor_id",
    "chunk_index",
    "start_character_offset",
    "end_character_offset",
    "rank",
    "match_kind",
    "matched_terms",
    "snippet",
)

private fun JsonObject.indexDocumentsListResultUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in INDEX_DOCUMENTS_LIST_RESULT_PAYLOAD_KEYS }?.let { return it }
    val documents = this["documents"] as? JsonArray
    documents?.forEachIndexed { index, element ->
        val document = element as? JsonObject ?: return@forEachIndexed
        document.keys.firstOrNull { it !in RUNTIME_DOCUMENT_INDEX_DOCUMENT_PAYLOAD_KEYS }?.let {
            return "documents[$index].$it"
        }
    }
    val summary = this["summary"] as? JsonObject
    summary?.keys?.firstOrNull { it !in INDEX_DOCUMENTS_SUMMARY_PAYLOAD_KEYS }?.let {
        return "summary.$it"
    }
    val qualityCounts = summary?.get("quality_counts") as? JsonObject
    qualityCounts?.keys?.firstOrNull { it !in INDEX_DOCUMENTS_QUALITY_COUNTS_PAYLOAD_KEYS }?.let {
        return "summary.quality_counts.$it"
    }
    return null
}

private fun JsonObject.retrievalQueryResultUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in RETRIEVAL_QUERY_RESULT_PAYLOAD_KEYS }?.let { return it }
    val results = this["results"] as? JsonArray ?: return null
    results.forEachIndexed { index, element ->
        val result = element as? JsonObject ?: return@forEachIndexed
        result.keys.firstOrNull { it !in RETRIEVAL_QUERY_RESULT_ITEM_PAYLOAD_KEYS }?.let {
            return "results[$index].$it"
        }
        val document = result["document"] as? JsonObject ?: return@forEachIndexed
        document.keys.firstOrNull { it !in RUNTIME_DOCUMENT_INDEX_DOCUMENT_PAYLOAD_KEYS }?.let {
            return "results[$index].document.$it"
        }
    }
    return null
}

private val MEMORY_LIST_RESULT_PAYLOAD_KEYS = setOf("entries")

private val MEMORY_DUPLICATE_SUGGESTIONS_LIST_RESULT_PAYLOAD_KEYS = setOf(
    "groups",
    "scanned_count",
    "truncated",
)

private val MEMORY_DUPLICATE_SUGGESTION_GROUP_PAYLOAD_KEYS = setOf("entry_ids")

private val MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_LIST_RESULT_PAYLOAD_KEYS = setOf(
    "pairs",
    "scanned_count",
    "omitted_count",
    "truncated",
)

private val MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_PAIR_PAYLOAD_KEYS = setOf(
    "entry_ids",
    "similarity_basis_points",
)

private val MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_LIST_RESULT_PAYLOAD_KEYS = setOf(
    "clusters",
    "scanned_count",
    "omitted_count",
    "truncated",
)

private val MEMORY_SEMANTIC_DUPLICATE_CLUSTER_PAYLOAD_KEYS = setOf(
    "entry_ids",
    "minimum_similarity_basis_points",
)

private val MEMORY_UPSERT_RESULT_PAYLOAD_KEYS = setOf("entry")

private val MEMORY_DELETE_RESULT_PAYLOAD_KEYS = setOf(
    "id",
    "deleted_at",
)

private val MEMORY_ENTRY_PAYLOAD_KEYS = setOf(
    "id",
    "content",
    "enabled",
    "created_at",
    "updated_at",
    "source",
    "search",
)

private val MEMORY_ENTRY_SOURCE_PAYLOAD_KEYS = setOf(
    "kind",
    "draft_id",
    "summary_method",
    "session",
    "source_message_count",
    "source_range",
    "source_pointers",
)

private val MEMORY_SUMMARY_DRAFT_SESSION_PAYLOAD_KEYS = setOf(
    "session_id",
    "title",
    "model",
    "last_activity_at",
    "message_count",
    "inactive_seconds",
)

private val MEMORY_SUMMARY_DRAFT_SOURCE_POINTER_PAYLOAD_KEYS = setOf(
    "session_id",
    "message_index",
    "role",
    "created_at",
    "excerpt",
)

private val MEMORY_SUMMARY_DRAFTS_LIST_RESULT_PAYLOAD_KEYS = setOf("drafts")

private val MEMORY_SUMMARY_DRAFT_APPROVE_RESULT_PAYLOAD_KEYS = setOf(
    "draft_id",
    "status",
    "entry",
)

private val MEMORY_SUMMARY_DRAFT_DISMISS_RESULT_PAYLOAD_KEYS = setOf(
    "draft_id",
    "status",
    "dismissed_at",
)

private val MEMORY_SUMMARY_DRAFT_GENERATE_RESULT_PAYLOAD_KEYS = setOf("draft")

private val MEMORY_SUMMARY_DRAFT_PAYLOAD_KEYS = setOf(
    "id",
    "session",
    "source_message_count",
    "source_range",
    "source_pointers",
    "summary_preview",
    "summary_method",
    "generated_at",
    "generated_model_id",
)

private fun JsonObject.memorySummaryDraftUnknownMetadataKey(pathPrefix: String): String? {
    keys.firstOrNull { it !in MEMORY_SUMMARY_DRAFT_PAYLOAD_KEYS }?.let {
        return "$pathPrefix.$it"
    }
    val session = this["session"] as? JsonObject
    session?.keys?.firstOrNull { it !in MEMORY_SUMMARY_DRAFT_SESSION_PAYLOAD_KEYS }?.let {
        return "$pathPrefix.session.$it"
    }
    val sourcePointers = this["source_pointers"] as? JsonArray ?: return null
    sourcePointers.forEachIndexed { pointerIndex, pointerElement ->
        val pointer = pointerElement as? JsonObject ?: return@forEachIndexed
        pointer.keys.firstOrNull { it !in MEMORY_SUMMARY_DRAFT_SOURCE_POINTER_PAYLOAD_KEYS }?.let {
            return "$pathPrefix.source_pointers[$pointerIndex].$it"
        }
    }
    return null
}

private fun JsonObject.memorySummaryDraftsListResultUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in MEMORY_SUMMARY_DRAFTS_LIST_RESULT_PAYLOAD_KEYS }?.let { return it }
    val drafts = this["drafts"] as? JsonArray ?: return null
    drafts.forEachIndexed { draftIndex, element ->
        val draft = element as? JsonObject ?: return@forEachIndexed
        draft.memorySummaryDraftUnknownMetadataKey("drafts[$draftIndex]")?.let { return it }
    }
    return null
}

private fun JsonObject.memorySummaryDraftGenerateResultUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in MEMORY_SUMMARY_DRAFT_GENERATE_RESULT_PAYLOAD_KEYS }?.let { return it }
    val draft = this["draft"] as? JsonObject ?: return null
    return draft.memorySummaryDraftUnknownMetadataKey("draft")
}

private fun JsonObject.memoryEntryUnknownMetadataKey(pathPrefix: String): String? {
    keys.firstOrNull { it !in MEMORY_ENTRY_PAYLOAD_KEYS }?.let {
        return "$pathPrefix.$it"
    }
    val search = this["search"] as? JsonObject
    search?.keys?.firstOrNull { it !in CHAT_SESSION_SEARCH_PAYLOAD_KEYS }?.let {
        return "$pathPrefix.search.$it"
    }
    val source = this["source"] as? JsonObject ?: return null
    source.keys.firstOrNull { it !in MEMORY_ENTRY_SOURCE_PAYLOAD_KEYS }?.let {
        return "$pathPrefix.source.$it"
    }
    val session = source["session"] as? JsonObject
    session?.keys?.firstOrNull { it !in MEMORY_SUMMARY_DRAFT_SESSION_PAYLOAD_KEYS }?.let {
        return "$pathPrefix.source.session.$it"
    }
    val sourcePointers = source["source_pointers"] as? JsonArray ?: return null
    sourcePointers.forEachIndexed { pointerIndex, pointerElement ->
        val pointer = pointerElement as? JsonObject ?: return@forEachIndexed
        pointer.keys.firstOrNull { it !in MEMORY_SUMMARY_DRAFT_SOURCE_POINTER_PAYLOAD_KEYS }?.let {
            return "$pathPrefix.source.source_pointers[$pointerIndex].$it"
        }
    }
    return null
}

private fun JsonObject.memoryListResultUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in MEMORY_LIST_RESULT_PAYLOAD_KEYS }?.let { return it }
    val entries = this["entries"] as? JsonArray ?: return null
    entries.forEachIndexed { entryIndex, element ->
        val entry = element as? JsonObject ?: return@forEachIndexed
        entry.memoryEntryUnknownMetadataKey("entries[$entryIndex]")?.let { return it }
    }
    return null
}

private fun JsonObject.memoryDuplicateSuggestionsListResultUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in MEMORY_DUPLICATE_SUGGESTIONS_LIST_RESULT_PAYLOAD_KEYS }?.let { return it }
    val groups = this["groups"] as? JsonArray ?: return null
    groups.forEachIndexed { groupIndex, element ->
        val group = element as? JsonObject ?: return@forEachIndexed
        group.keys.firstOrNull { it !in MEMORY_DUPLICATE_SUGGESTION_GROUP_PAYLOAD_KEYS }?.let {
            return "groups[$groupIndex].$it"
        }
    }
    return null
}

private fun JsonObject.memorySemanticDuplicateSuggestionsListResultUnknownMetadataKey(): String? {
    keys.firstOrNull {
        it !in MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_LIST_RESULT_PAYLOAD_KEYS
    }?.let { return it }
    val pairs = this["pairs"] as? JsonArray ?: return null
    pairs.forEachIndexed { pairIndex, element ->
        val pair = element as? JsonObject ?: return@forEachIndexed
        pair.keys.firstOrNull {
            it !in MEMORY_SEMANTIC_DUPLICATE_SUGGESTION_PAIR_PAYLOAD_KEYS
        }?.let { return "pairs[$pairIndex].$it" }
    }
    return null
}

private fun JsonObject.memorySemanticDuplicateClustersListResultUnknownMetadataKey(): String? {
    keys.firstOrNull {
        it !in MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_LIST_RESULT_PAYLOAD_KEYS
    }?.let { return it }
    val clusters = this["clusters"] as? JsonArray ?: return null
    clusters.forEachIndexed { clusterIndex, element ->
        val cluster = element as? JsonObject ?: return@forEachIndexed
        cluster.keys.firstOrNull {
            it !in MEMORY_SEMANTIC_DUPLICATE_CLUSTER_PAYLOAD_KEYS
        }?.let { return "clusters[$clusterIndex].$it" }
    }
    return null
}

private fun JsonObject.memoryUpsertResultUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in MEMORY_UPSERT_RESULT_PAYLOAD_KEYS }?.let { return it }
    val entry = this["entry"] as? JsonObject ?: return null
    return entry.memoryEntryUnknownMetadataKey("entry")
}

private fun JsonObject.memoryDeleteResultUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in MEMORY_DELETE_RESULT_PAYLOAD_KEYS }
}

private fun JsonObject.memorySummaryDraftApproveResultUnknownMetadataKey(): String? {
    keys.firstOrNull { it !in MEMORY_SUMMARY_DRAFT_APPROVE_RESULT_PAYLOAD_KEYS }?.let { return it }
    val entry = this["entry"] as? JsonObject ?: return null
    return entry.memoryEntryUnknownMetadataKey("entry")
}

private fun JsonObject.memorySummaryDraftDismissResultUnknownMetadataKey(): String? {
    return keys.firstOrNull { it !in MEMORY_SUMMARY_DRAFT_DISMISS_RESULT_PAYLOAD_KEYS }
}

internal val RUNTIME_CLIENT_CAPABILITIES = listOf(
    MessageType.RuntimeHealth,
    MessageType.ModelsList,
    MessageType.ModelsPull,
    MessageType.ChatSend,
    MessageType.ChatCancel,
    MessageType.ChatSessionsList,
    MessageType.ChatMessagesList,
    MessageType.ChatTitleRequest,
    MessageType.ChatSessionRename,
    MessageType.ChatSessionArchive,
    MessageType.ChatSessionRestore,
    MessageType.ChatSessionDelete,
    MessageType.IndexDocumentsList,
    MessageType.RetrievalQuery,
    MessageType.CitationResolve,
    MessageType.TrustedSourceApprove,
    MessageType.TrustedSourceDismiss,
    MessageType.TrustedSourceList,
    MessageType.TrustedSourceRevoke,
    MessageType.MemoryList,
    MessageType.MemoryDuplicateSuggestionsList,
    MessageType.MemorySemanticDuplicateSuggestionsList,
    MessageType.MemorySemanticDuplicateClustersList,
    MessageType.MemoryUpsert,
    MessageType.MemoryDelete,
    MessageType.MemorySummaryDraftsList,
    MessageType.MemorySummaryDraftGenerate,
    MessageType.MemorySummaryDraftApprove,
    MessageType.MemorySummaryDraftDismiss,
    "chat.attachments",
    CHAT_SOURCE_ATTRIBUTIONS_CAPABILITY,
    CHAT_SOURCE_ATTRIBUTION_RESOLVE_CAPABILITY,
    CHAT_SESSIONS_SYNC_CAPABILITY,
    MEMORY_DUPLICATE_SUGGESTIONS_CAPABILITY,
    MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_CAPABILITY,
    MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_CAPABILITY,
)

internal fun runtimeClientCapabilities(authenticatedRouteRefreshEnabled: Boolean): List<String> {
    return if (authenticatedRouteRefreshEnabled) {
        RUNTIME_CLIENT_CAPABILITIES + MessageType.RouteRefresh
    } else {
        RUNTIME_CLIENT_CAPABILITIES
    }
}

internal const val ROUTE_REFRESH_LEASE_RENEWAL_LEAD_MS = 60_000L
private const val CHAT_SESSIONS_BULK_SCOPE_ALL_ACTIVE = "all_active"
private const val CHAT_SESSIONS_BULK_SCOPE_ALL_ARCHIVED = "all_archived"
private const val MAX_RUNTIME_CHAT_SESSION_PAGE_SIZE = 200
private const val MAX_RUNTIME_CHAT_SESSIONS_BULK_BATCH_SIZE = 200
private const val MAX_RUNTIME_CHAT_SESSION_LIST_PAGES = 100
private const val MAX_RUNTIME_CHAT_SESSION_BULK_BATCHES = 50
private const val MAX_RUNTIME_CHAT_SESSION_BULK_AFFECTED = 10_000
private const val MAX_CLOSED_RUNTIME_CHAT_HISTORY_REQUESTS = 128
private const val MAX_CLOSED_MEMORY_DUPLICATE_SUGGESTIONS_REQUESTS = 32
private const val MAX_CLOSED_MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_REQUESTS = 32
private const val MAX_CLOSED_MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_REQUESTS = 32
private val MEMORY_DUPLICATE_SUGGESTIONS_UNSUPPORTED_ERROR_CODES = setOf(
    "unknown_message_type",
    "unsupported_operation",
)
private val MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_UNSUPPORTED_ERROR_CODES = setOf(
    "unknown_message_type",
    "unsupported_operation",
)
private val MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_UNSUPPORTED_ERROR_CODES = setOf(
    "unknown_message_type",
    "unsupported_operation",
)
internal const val ROUTE_REFRESH_LEASE_MIN_DELAY_MS = 1_000L
internal const val ROUTE_REFRESH_RETRY_DELAY_MS = 10_000L
internal const val ROUTE_REFRESH_REQUEST_TIMEOUT_MS = 15_000L
internal const val CITATION_RESOLVE_REQUEST_TIMEOUT_MS = 15_000L
private val CHAT_ASSISTANT_MESSAGE_ID_PATTERN = Regex("^assistant_message_[0-9a-f]{32}$")
internal const val RELAY_REACHABILITY_PREFLIGHT_TIMEOUT_MS = 1_500

internal fun runtimeRouteRefreshLeaseDelayMillis(
    nowEpochMillis: Long,
    remoteRouteExpiresAtEpochMillis: Long?,
    renewalLeadMillis: Long = ROUTE_REFRESH_LEASE_RENEWAL_LEAD_MS,
    minimumDelayMillis: Long = ROUTE_REFRESH_LEASE_MIN_DELAY_MS,
): Long? {
    val expiresAt = remoteRouteExpiresAtEpochMillis ?: return null
    val remainingMillis = expiresAt - nowEpochMillis
    if (remainingMillis <= 0L) return null
    val minimumDelay = minimumDelayMillis.coerceAtLeast(0L)
    if (remainingMillis <= minimumDelay) return 0L
    val scheduledDelay = maxOf(
        minimumDelay,
        remainingMillis - renewalLeadMillis.coerceAtLeast(0L),
    )
    return scheduledDelay.coerceAtMost(remainingMillis - 1L)
}

internal fun runtimeRouteRefreshRetryDelayMillis(
    nowEpochMillis: Long,
    remoteRouteExpiresAtEpochMillis: Long?,
    retryDelayMillis: Long = ROUTE_REFRESH_RETRY_DELAY_MS,
    minimumDelayMillis: Long = ROUTE_REFRESH_LEASE_MIN_DELAY_MS,
): Long? {
    val expiresAt = remoteRouteExpiresAtEpochMillis ?: return null
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
    private val clientCapabilities = runtimeClientCapabilities(
        authenticatedRouteRefreshEnabled = dependencies.authenticatedRouteRefreshEnabled,
    )
    private val client = dependencies.transportClient
    private val remoteRoutePlanner = RuntimeRemoteRoutePlanner(
        pendingPairingPayload = { pendingPairingPayload },
        trustedRuntime = { state.value.trustedRuntime },
        nowEpochMillis = dependencies.currentTimeMillis,
    )
    private val connectionManager = RuntimeConnectionManager(
        connector = dependencies.transportConnector,
        routeResolver = RuntimeRouteResolver { target ->
            runtimeRouteCandidates(
                state = state.value,
                target = target,
                includeUsbReverseFallback = shouldIncludeDebugUsbReverseFallback(target),
                suppressDirectRoutes = pendingPairingPayload
                    ?.takeIf { payload ->
                        target.identity?.let { identity -> payload.matchesIdentity(identity) } == true
                    }
                    ?.hasRemoteRoute() == true,
            )
        },
        remoteRoutePreparer = remoteRoutePlanner,
        peerToPeerConnector = dependencies.peerToPeerConnector,
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
    private var routeRefreshRequestTimeoutJob: Job? = null
    private var activeChannel: RuntimeProtocolChannel? = null
    private var activeConnectionGeneration = 0L
    private var pendingPairingPayload: RuntimePairingPayload? = null
    private var pendingPairingRequestPayload: RuntimePairingPayload? = null
    private var pendingInitialPairingRequest: PendingInitialPairingRequest? = null
    private var pendingRuntimeAuthentication: PendingRuntimeAuthentication? = null
    private val closedRuntimeAuthenticationRequestIds = mutableSetOf<String>()
    private var pendingPairingRetryJob: Job? = null
    private var pendingPairingDiscoveryTimeoutJob: Job? = null
    private var pendingPairingRetryAttempts = 0
    private var pendingModelPullRequestId: String? = null
    private var pendingModelsListRequest: PendingModelsListRequest? = null
    private var pendingChatSessionsRequestId: String? = null
    private var pendingChatSessionsQuery: String? = null
    private var pendingChatSessionsListRun: PendingChatSessionsListRun? = null
    private var pendingChatSessionsBulkLifecycle: PendingChatSessionsBulkLifecycle? = null
    private var runtimeChatSessionsAuthoritativeSyncSupported = false
    private var runtimeChatSessionsBulkAuthorityEnabled = false
    private var runtimeChatSearchSummariesById: Map<String, ChatSessionSummaryPayload> = emptyMap()
    private var pendingChatMessagesRequestId: String? = null
    private var pendingChatMessagesSessionId: String? = null
    private var pendingChatMessagesRequestCorrelation: RuntimeChatHistoryRequestCorrelation? = null
    private val closedRuntimeChatHistoryRequests = mutableListOf<RuntimeChatHistoryRequestCorrelation>()
    private var pendingTitleRequestId: String? = null
    private var pendingTitleSessionId: String? = null
    private var pendingMemoryListRequestId: String? = null
    private var pendingMemoryListQuery: String? = null
    private var pendingMemoryListEmbeddingModelId: String? = null
    private var pendingMemoryListChannel: RuntimeProtocolChannel? = null
    private var pendingMemoryListConnectionGeneration: Long? = null
    private var pendingMemoryListAuthorityGeneration: Long? = null
    private var pendingMemoryDuplicateSuggestionsRequest: PendingMemoryDuplicateSuggestionsRequest? = null
    private val closedMemoryDuplicateSuggestionsRequests =
        mutableListOf<PendingMemoryDuplicateSuggestionsRequest>()
    private var memoryDuplicateSuggestionsListAcceptedAuthorityGeneration: Long? = null
    private var memoryDuplicateSuggestionsUnsupportedAuthorityGeneration: Long? = null
    private var pendingMemorySemanticDuplicateSuggestionsRequest:
        PendingMemorySemanticDuplicateSuggestionsRequest? = null
    private val closedMemorySemanticDuplicateSuggestionsRequests =
        mutableListOf<PendingMemorySemanticDuplicateSuggestionsRequest>()
    private var memorySemanticDuplicateSuggestionsListAcceptedAuthorityGeneration: Long? = null
    private var memorySemanticDuplicateSuggestionsUnsupportedAuthorityGeneration: Long? = null
    private var pendingMemorySemanticDuplicateClustersRequest:
        PendingMemorySemanticDuplicateClustersRequest? = null
    private val closedMemorySemanticDuplicateClustersRequests =
        mutableListOf<PendingMemorySemanticDuplicateClustersRequest>()
    private var memorySemanticDuplicateClustersListAcceptedAuthorityGeneration: Long? = null
    private var memorySemanticDuplicateClustersUnsupportedAuthorityGeneration: Long? = null
    private var memoryCatalogGeneration = 0L
    private var modelCatalogGeneration = 0L
    private var modelCatalogAcceptedAuthorityGeneration: Long? = null
    private var pendingMemorySummaryDraftsRequestId: String? = null
    private var pendingDocumentCatalogRequestId: String? = null
    private var pendingDocumentSearchRequestId: String? = null
    private var pendingDocumentSearchPayload: RetrievalQueryRequestPayload? = null
    private var pendingDocumentSearchCanRetryWithoutEmbedding = false
    private var pendingCitationResolveRequestId: String? = null
    private var pendingCitationResolveSourceAnchorId: String? = null
    private var citationResolveRequestTimeoutJob: Job? = null
    private var pendingHistoricalSourceAttributionResolve: PendingHistoricalSourceAttributionResolve? = null
    private var historicalSourceAttributionResolveTimeoutJob: Job? = null
    private var pendingSourceReview: PendingSourceReview? = null
    private var pendingTrustedSourceApproveRequestId: String? = null
    private var pendingTrustedSourceDismissRequestId: String? = null
    private var pendingTrustedSourceListRequestId: String? = null
    private var pendingTrustedSourceListMutationGeneration: Long? = null
    private var trustedSourceMutationGeneration: Long = 0
    private val pendingTrustedSourceRevocationsByRequestId = mutableMapOf<String, String>()
    private val trustedSourceGrantsBySourceAnchorId = mutableMapOf<String, String>()
    private val pendingMemorySummaryDraftGenerationsByRequestId =
        mutableMapOf<String, PendingMemorySummaryDraftGeneration>()
    private val pendingMemorySummaryDraftApprovalDraftIdsByRequestId = mutableMapOf<String, String>()
    private val pendingMemorySummaryDraftDismissalDraftIdsByRequestId = mutableMapOf<String, String>()
    private var pendingRouteRefreshRequestId: String? = null
    private var pendingRouteRefreshRequiresPairedAuthorization = false
    private var pendingPairedRelayAllocationAuthorization: PendingPairedRelayAllocationAuthorization? = null
    private val pendingChatSessionLifecycleRequestIds = mutableSetOf<String>()
    private val pendingChatSessionRenameRequestIds = mutableSetOf<String>()
    private val pendingChatSessionLifecycleMutationsByRequestId = mutableMapOf<String, PendingChatSessionLifecycleMutation>()
    private val pendingChatSessionRenameMutationsByRequestId = mutableMapOf<String, PendingChatSessionRenameMutation>()
    private var pendingChatSessionMutationSequence = 0L
    private val pendingAttachmentsBySession = mutableMapOf<String?, List<RuntimePendingAttachment>>()
    private var modelIdToSelectAfterRefresh: String? = null
    private var isSessionAuthenticated = false
    private var runtimeSessionAuthorityGeneration = 0L
    private var persistedRuntimeData = PersistedRuntimeData()
    private var shouldRestoreTrustedRuntimeConnection = true
    private var didAttemptTrustedRuntimeRestore = false
    private val connectionMutex = Mutex()
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
        publishPersistedRuntimeData(loadedRuntimeData, save = false, syncComposerDraft = true)
        restorePersistedPendingPairingRouteIfNeeded(loadedRuntimeData)
        viewModelScope.launch {
            pairingStore.trustedRuntime.collect { trusted ->
                val currentTrust = state.value.trustedRuntime
                if (
                    currentTrust?.deviceId != trusted?.deviceId ||
                    currentTrust?.fingerprint != trusted?.fingerprint ||
                    currentTrust?.publicKeyBase64 != trusted?.publicKeyBase64
                ) {
                    clearTrustedSourceSessionState()
                }
                if (
                    pendingRouteRefreshRequestId != null &&
                    !state.value.trustedRuntime.hasSameRelayAllocationRoute(trusted)
                ) {
                    clearPendingRouteRefreshRequest()
                }
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
                            relayTicketGeneration = trusted.relayTicketGeneration,
                            p2pRouteClass = trusted.p2pRouteClass,
                            p2pRecordId = trusted.p2pRecordId,
                            p2pEncryptedBody = trusted.p2pEncryptedBody,
                            p2pExpiresAtEpochMillis = trusted.p2pExpiresAtEpochMillis,
                            p2pAntiReplayNonce = trusted.p2pAntiReplayNonce,
                            p2pProtocolVersion = trusted.p2pProtocolVersion,
                        )
                        it.withTrustedRuntimeRouteFields(runtime, endpoint)
                    }
                }
                if (
                    trusted != null &&
                    shouldRestoreTrustedRuntimeConnection &&
                    !didAttemptTrustedRuntimeRestore &&
                    shouldAttemptTrustedRuntimeRestore(shouldRestoreTrustedRuntimeConnection, state.value)
                ) {
                    didAttemptTrustedRuntimeRestore = true
                    restoreTrustedRuntimeConnection()
                }
            }
        }
    }

    fun updateHost(value: String) {
        if (rejectUserMutationWhileStreaming()) return
        mutableState.update {
            it.copy(
                runtimeHost = value.trim(),
                runtimeEndpointSource = RuntimeEndpointSource.Manual,
            )
        }
    }

    fun updatePort(value: String) {
        if (rejectUserMutationWhileStreaming()) return
        mutableState.update {
            it.copy(
                runtimePort = value.filter(Char::isDigit).take(5),
                runtimeEndpointSource = RuntimeEndpointSource.Manual,
            )
        }
    }

    fun useUsbReverseEndpoint() {
        if (rejectUserMutationWhileStreaming()) return
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
        if (rejectUserMutationWhileStreaming()) return
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
        if (rejectUserMutationWhileStreaming()) return
        mutableState.update { it.copy(pairingCode = value.filter(Char::isDigit).take(6)) }
    }

    fun updateChatInput(value: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (rejectUserMutationWhileActiveChatMessagesLoading()) return
        val cleanDraft = persistComposerDraft(value)
        mutableState.update { it.copy(chatInput = cleanDraft) }
    }

    fun clearChatDraft() {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (rejectUserMutationWhileActiveChatMessagesLoading()) return
        val cleanDraft = clearComposerDraft()
        clearPendingAttachmentsForSession()
        mutableState.update {
            it.copy(
                chatInput = cleanDraft,
                pendingAttachments = emptyList(),
            )
        }
    }

    fun toggleTrustedSourceSelection(sourceAnchorId: String) {
        val current = state.value
        if (current.isStreaming || current.isLoadingActiveChatMessages) return
        val selectable = current.trustedSources.any { it.sourceAnchorId == sourceAnchorId } &&
            trustedSourceGrantsBySourceAnchorId.containsKey(sourceAnchorId)
        if (!selectable) return
        mutableState.update {
            val selected = it.selectedTrustedSourceAnchorIds
            val updated = if (sourceAnchorId in selected) {
                selected - sourceAnchorId
            } else {
                if (selected.size >= MAX_SELECTED_TRUSTED_SOURCES) return@update it
                selected + sourceAnchorId
            }
            it.copy(selectedTrustedSourceAnchorIds = updated)
        }
    }

    fun removeTrustedSourceSelection(sourceAnchorId: String) {
        mutableState.update {
            it.copy(selectedTrustedSourceAnchorIds = it.selectedTrustedSourceAnchorIds - sourceAnchorId)
        }
    }

    fun addAttachments(uris: List<Uri>) {
        addAttachmentReferences(uris.map { it.toString() })
    }

    internal fun addAttachmentReferences(references: List<String>) {
        if (references.isEmpty()) return
        viewModelScope.launch {
            if (state.value.isStreaming) {
                showError("generation_in_progress")
                return@launch
            }
            if (rejectUserMutationWhileActiveChatMessagesLoading()) return@launch
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
                val bytes = attachmentReader.readBytes(reference, MAX_ATTACHMENT_BYTES)
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
            rememberPendingAttachmentsForCurrentSession()
        }
    }

    fun removePendingAttachment(attachmentId: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (rejectUserMutationWhileActiveChatMessagesLoading()) return
        mutableState.update { current ->
            current.copy(
                pendingAttachments = current.pendingAttachments.filterNot { it.id == attachmentId },
                error = null,
            )
        }
        rememberPendingAttachmentsForCurrentSession()
    }

    fun setAppLanguageTag(languageTag: String) {
        publishPersistedRuntimeData(
            persistedRuntimeData.withAppLanguageTag(languageTag),
            save = true,
        )
    }

    fun followSystemAppLanguageTag(languageTag: String?) {
        publishPersistedRuntimeData(
            persistedRuntimeData.withFollowSystemAppLanguageTag(languageTag),
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
        clearPendingHistoricalSourceAttributionResolve()
        rememberPendingAttachmentsForCurrentSession()
        clearPendingAttachmentsForSession(null)
        publishPersistedRuntimeData(
            persistedRuntimeData
                .withNoActiveSession()
                .withComposerDraft("", sessionId = null),
            save = true,
            syncComposerDraft = true,
        )
        mutableState.update {
            it.copy(
                loadingChatSessionId = null,
                selectedTrustedSourceAnchorIds = emptyList(),
            )
        }
    }

    fun openPreviousChat(sessionId: String): Boolean {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return false
        }
        val session = runtimeChatSessionForAction(sessionId)
        if (session == null || session.archivedAtMillis != null) {
            showError("chat_session_not_found")
            return false
        }
        clearPendingHistoricalSourceAttributionResolve()
        rememberPendingAttachmentsForCurrentSession()
        publishPersistedRuntimeData(
            persistedRuntimeData.withActiveSession(sessionId),
            save = true,
            syncComposerDraft = true,
        )
        mutableState.update {
            it.copy(
                loadingChatSessionId = null,
                selectedTrustedSourceAnchorIds = emptyList(),
            )
        }
        requestRuntimeChatMessages(sessionId)
        return true
    }

    fun selectChatSession(sessionId: String): Boolean = openPreviousChat(sessionId)

    fun renameChatSession(sessionId: String, title: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        val session = runtimeChatSessionForAction(sessionId)
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
        val session = runtimeChatSessionForAction(sessionId)
        if (session == null) {
            showError("chat_session_not_found")
            return
        }
        if (session.archivedAtMillis == null) {
            showError("chat_session_must_be_archived_before_delete")
            return
        }
        if (isRuntimeOwnedChatMutationBlocked(listOf(session))) return
        clearPendingAttachmentsForSession(sessionId)
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
            val cleanDraft = clearComposerDraft(sessionId = null)
            mutableState.update {
                it.copy(
                    chatInput = cleanDraft,
                    pendingAttachments = emptyList(),
                )
            }
        }
    }

    fun archiveChatSession(sessionId: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        val session = runtimeChatSessionForAction(sessionId)
        if (session == null) {
            showError("chat_session_not_found")
            return
        }
        if (isRuntimeOwnedChatMutationBlocked(listOf(session))) return
        val restoreAsActive = persistedRuntimeData.activeSessionId == session.id
        clearPendingAttachmentsForSession(sessionId)
        publishPersistedRuntimeData(
            persistedRuntimeData.withArchivedChatSession(sessionId, nowMillis()),
            save = true,
        )
        sendRuntimeChatSessionLifecycleIfNeeded(
            session = session,
            type = MessageType.ChatSessionArchive,
            restoreAsActive = restoreAsActive,
        )
        if (state.value.activeChatSessionId == null) {
            val cleanDraft = clearComposerDraft(sessionId = null)
            mutableState.update {
                it.copy(
                    chatInput = cleanDraft,
                    pendingAttachments = emptyList(),
                )
            }
        }
    }

    fun archiveChatSessions() {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        val sessionsToArchive = persistedRuntimeData.sessions.filter { it.archivedAtMillis == null }
        if (isRuntimeOwnedChatMutationBlocked(sessionsToArchive)) return
        val includesRuntimeOwnedSessions = sessionsToArchive.any { it.runtimeOwned }
        if (runtimeChatSessionsAuthoritativeSyncSupported && includesRuntimeOwnedSessions) {
            if (!runtimeChatSessionsBulkAuthorityEnabled) {
                showError("chat_history_loading")
                return
            }
            if (beginRuntimeChatSessionsBulkLifecycle(
                    type = MessageType.ChatSessionArchive,
                    scope = CHAT_SESSIONS_BULK_SCOPE_ALL_ACTIVE,
                )
            ) {
                return
            }
            showError("chat_history_loading")
            return
        }
        val activeSessionIdBeforeArchive = persistedRuntimeData.activeSessionId
        sessionsToArchive.forEach { clearPendingAttachmentsForSession(it.id) }
        clearPendingAttachmentsForSession(null)
        publishPersistedRuntimeData(
            persistedRuntimeData.withArchivedChatSessions(nowMillis()),
            save = true,
        )
        sessionsToArchive.forEach { session ->
            sendRuntimeChatSessionLifecycleIfNeeded(
                session = session,
                type = MessageType.ChatSessionArchive,
                restoreAsActive = activeSessionIdBeforeArchive == session.id,
            )
        }
        val cleanDraft = clearComposerDraft(sessionId = null)
        mutableState.update {
            it.copy(
                chatInput = cleanDraft,
                pendingAttachments = emptyList(),
            )
        }
    }

    fun unarchiveChatSession(sessionId: String) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        val session = runtimeChatSessionForAction(sessionId)
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
        val includesRuntimeOwnedSessions = archivedSessionsToDelete.any { it.runtimeOwned }
        if (runtimeChatSessionsAuthoritativeSyncSupported && includesRuntimeOwnedSessions) {
            if (!runtimeChatSessionsBulkAuthorityEnabled) {
                showError("chat_history_loading")
                return
            }
            if (beginRuntimeChatSessionsBulkLifecycle(
                    type = MessageType.ChatSessionDelete,
                    scope = CHAT_SESSIONS_BULK_SCOPE_ALL_ARCHIVED,
                )
            ) {
                return
            }
            showError("chat_history_loading")
            return
        }
        archivedSessionsToDelete.forEach { clearPendingAttachmentsForSession(it.id) }
        clearPendingAttachmentsForSession(null)
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
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        clearMemoryDuplicateSuggestions()
        clearMemorySemanticDuplicateSuggestions()
        clearMemorySemanticDuplicateClusters()
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
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        clearMemoryDuplicateSuggestions()
        clearMemorySemanticDuplicateSuggestions()
        clearMemorySemanticDuplicateClusters()
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
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        clearMemoryDuplicateSuggestions()
        clearMemorySemanticDuplicateSuggestions()
        clearMemorySemanticDuplicateClusters()
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

    fun refreshRuntimeMemory() {
        refreshRuntimeMemory(query = null)
    }

    fun refreshRuntimeMemory(query: String?) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        val normalizedQuery = query?.trim()?.ifBlank { null }
        requestRuntimeMemory(query = normalizedQuery)
        if (normalizedQuery == null) {
            requestRuntimeMemorySummaryDrafts()
        }
    }

    fun refreshRuntimeMemorySummaryDrafts() {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        requestRuntimeMemorySummaryDrafts()
    }

    fun scanRuntimeMemoryDuplicateSuggestions() {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeMemoryCommand() || !state.value.memoryDuplicateSuggestionsAvailable) {
            showError("memory_runtime_required")
            return
        }
        val channel = activeChannel ?: return
        val requestId = MEMORY_DUPLICATE_SUGGESTIONS_REQUEST_ID_PREFIX + UUID.randomUUID()
        closePendingMemoryDuplicateSuggestionsRequest()
        pendingMemoryDuplicateSuggestionsRequest = PendingMemoryDuplicateSuggestionsRequest(
            requestId = requestId,
            channel = channel,
            connectionGeneration = activeConnectionGeneration,
            authorityGeneration = runtimeSessionAuthorityGeneration,
        )
        mutableState.update {
            it.copy(
                memoryDuplicateSuggestionGroups = emptyList(),
                memoryDuplicateSuggestionsScannedCount = 0,
                memoryDuplicateSuggestionsTruncated = false,
                hasMemoryDuplicateSuggestionsResult = false,
                isScanningMemoryDuplicateSuggestions = true,
                error = null,
            )
        }
        sendEnvelope(
            ProtocolEnvelope(
                type = MessageType.MemoryDuplicateSuggestionsList,
                requestId = requestId,
            )
        )
    }

    fun scanRuntimeMemorySemanticDuplicateSuggestions(
        minimumSimilarityBasisPoints: Int = 9_000,
    ) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (minimumSimilarityBasisPoints !in 8_000..10_000) {
            showError("invalid_payload")
            return
        }
        val current = state.value
        val embeddingModelId = current.selectedEmbeddingModelId
        if (
            !canSendRuntimeMemoryCommand() ||
            !current.memorySemanticDuplicateSuggestionsAvailable ||
            embeddingModelId == null ||
            !hasEligibleMemorySemanticDuplicateSuggestionsModel(current, embeddingModelId)
        ) {
            showError("memory_runtime_required")
            return
        }
        val channel = activeChannel ?: return
        val requestId = MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_REQUEST_ID_PREFIX + UUID.randomUUID()
        clearMemorySemanticDuplicateSuggestions()
        pendingMemorySemanticDuplicateSuggestionsRequest =
            PendingMemorySemanticDuplicateSuggestionsRequest(
                requestId = requestId,
                channel = channel,
                connectionGeneration = activeConnectionGeneration,
                authorityGeneration = runtimeSessionAuthorityGeneration,
                embeddingModelId = embeddingModelId,
                minimumSimilarityBasisPoints = minimumSimilarityBasisPoints,
            )
        mutableState.update {
            it.copy(
                memorySemanticDuplicateSuggestionsThresholdBasisPoints =
                    minimumSimilarityBasisPoints,
                isScanningMemorySemanticDuplicateSuggestions = true,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.MemorySemanticDuplicateSuggestionsList,
                serializer = MemorySemanticDuplicateSuggestionsListRequestPayload.serializer(),
                payload = MemorySemanticDuplicateSuggestionsListRequestPayload(
                    embeddingModelId = embeddingModelId,
                    minimumSimilarityBasisPoints = minimumSimilarityBasisPoints,
                ),
                requestId = requestId,
            )
        )
    }

    fun scanRuntimeMemorySemanticDuplicateClusters(
        minimumSimilarityBasisPoints: Int = 9_000,
    ) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (minimumSimilarityBasisPoints !in 8_000..10_000) {
            showError("invalid_payload")
            return
        }
        val current = state.value
        val embeddingModelId = current.selectedEmbeddingModelId
        if (
            !canSendRuntimeMemoryCommand() ||
            !current.memorySemanticDuplicateClustersAvailable ||
            embeddingModelId == null ||
            !hasEligibleMemorySemanticDuplicateSuggestionsModel(current, embeddingModelId)
        ) {
            showError("memory_runtime_required")
            return
        }
        val channel = activeChannel ?: return
        val requestId = MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_REQUEST_ID_PREFIX + UUID.randomUUID()
        clearMemorySemanticDuplicateClusters()
        pendingMemorySemanticDuplicateClustersRequest = PendingMemorySemanticDuplicateClustersRequest(
            requestId = requestId,
            channel = channel,
            connectionGeneration = activeConnectionGeneration,
            authorityGeneration = runtimeSessionAuthorityGeneration,
            memoryCatalogGeneration = memoryCatalogGeneration,
            modelCatalogGeneration = modelCatalogGeneration,
            embeddingModelId = embeddingModelId,
            minimumSimilarityBasisPoints = minimumSimilarityBasisPoints,
        )
        mutableState.update {
            it.copy(
                memorySemanticDuplicateClustersThresholdBasisPoints =
                    minimumSimilarityBasisPoints,
                isScanningMemorySemanticDuplicateClusters = true,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.MemorySemanticDuplicateClustersList,
                serializer = MemorySemanticDuplicateClustersListRequestPayload.serializer(),
                payload = MemorySemanticDuplicateClustersListRequestPayload(
                    embeddingModelId = embeddingModelId,
                    minimumSimilarityBasisPoints = minimumSimilarityBasisPoints,
                ),
                requestId = requestId,
            )
        )
    }

    fun refreshRuntimeDocumentCatalog() {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeDocumentSearchCommand()) {
            showError("document_search_runtime_required")
            return
        }
        requestRuntimeDocumentCatalog()
    }

    fun searchRuntimeDocuments(query: String) {
        val normalizedQuery = query.trim()
        if (normalizedQuery.isBlank()) {
            clearPendingRuntimeDocumentSearch()
            mutableState.update {
                it.copy(
                    documentSearchQuery = "",
                    documentSearchResults = emptyList(),
                    isSearchingDocuments = false,
                    error = null,
                )
            }
            return
        }
        if (normalizedQuery.length > MAX_RUNTIME_DOCUMENT_QUERY_CHARACTERS) {
            clearPendingRuntimeDocumentSearch()
            mutableState.update {
                it.copy(
                    documentSearchQuery = "",
                    documentSearchResults = emptyList(),
                    isSearchingDocuments = false,
                    error = runtimeUiError("document_search_failed", "query_too_long"),
                )
            }
            return
        }
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeDocumentSearchCommand()) {
            showError("document_search_runtime_required")
            return
        }
        requestRuntimeDocumentSearch(normalizedQuery)
    }

    fun resolveCitation(sourceAnchorId: String) {
        val anchorId = sourceAnchorId.trim()
        if (pendingCitationResolveRequestId != null) return
        if (pendingTrustedSourceListRequestId != null) return
        if (state.value.documentSearchResults.none { it.sourceAnchorId == anchorId }) return
        if (!canSendRuntimeDocumentSearchCommand()) {
            showError("document_search_runtime_required")
            return
        }
        val payload = runCatching { CitationResolveRequestPayload(anchorId) }.getOrNull() ?: return
        val requestId = CITATION_RESOLVE_REQUEST_ID_PREFIX + UUID.randomUUID()
        pendingCitationResolveRequestId = requestId
        pendingCitationResolveSourceAnchorId = anchorId
        scheduleCitationResolveTimeout(requestId)
        mutableState.update { it.copy(isResolvingCitation = true, error = null) }
        sendEnvelope(
            envelope(
                type = MessageType.CitationResolve,
                requestId = requestId,
                serializer = CitationResolveRequestPayload.serializer(),
                payload = payload,
            )
        )
    }

    fun reviewHistoricalSourceAttribution(messageId: String, sourceIndex: Int) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (pendingHistoricalSourceAttributionResolve != null || pendingCitationResolveRequestId != null) return
        if (!state.value.isConnected) {
            showError("connect_first")
            return
        }
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }
        if (rejectUserMutationWhileActiveChatMessagesLoading()) return
        val current = state.value
        val sessionId = current.activeChatSessionId ?: return
        val message = current.messages.singleOrNull { it.id == messageId && it.role == "assistant" } ?: return
        val assistantMessageId = message.assistantMessageId
            ?.takeIf(CHAT_ASSISTANT_MESSAGE_ID_PATTERN::matches)
            ?: return
        val attribution = message.sourceAttributions.singleOrNull { it.sourceIndex == sourceIndex } ?: return
        val channel = activeChannel ?: return
        val requestId = HISTORICAL_SOURCE_ATTRIBUTION_RESOLVE_REQUEST_ID_PREFIX + UUID.randomUUID()
        val pending = PendingHistoricalSourceAttributionResolve(
            requestId = requestId,
            sessionId = sessionId,
            localMessageId = message.id,
            assistantMessageId = assistantMessageId,
            sourceAttribution = attribution,
            channel = channel,
            connectionGeneration = activeConnectionGeneration,
        )
        pendingHistoricalSourceAttributionResolve = pending
        scheduleHistoricalSourceAttributionResolveTimeout(requestId)
        mutableState.update {
            it.copy(
                resolvingSourceAttributionMessageId = message.id,
                resolvingSourceAttributionIndex = sourceIndex,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.ChatSourceAttributionResolve,
                requestId = requestId,
                serializer = ChatSourceAttributionResolveRequestPayload.serializer(),
                payload = ChatSourceAttributionResolveRequestPayload(
                    sessionId = sessionId,
                    assistantMessageId = assistantMessageId,
                    sourceIndex = sourceIndex,
                ),
            )
        )
    }

    fun approveTrustedSource() {
        state.value.sourceReview?.sourceAnchorId?.let(::approveTrustedSource)
    }

    fun approveTrustedSource(sourceAnchorId: String) {
        if (pendingTrustedSourceApproveRequestId != null) return
        val review = pendingSourceReview?.takeIf { it.sourceAnchorId == sourceAnchorId.trim() } ?: return
        if (!canSendRuntimeDocumentSearchCommand()) {
            showError("document_search_runtime_required")
            return
        }
        val requestId = TRUSTED_SOURCE_APPROVE_REQUEST_ID_PREFIX + UUID.randomUUID()
        pendingTrustedSourceApproveRequestId = requestId
        mutableState.update { it.copy(isApprovingTrustedSource = true, error = null) }
        sendEnvelope(
            envelope(
                type = MessageType.TrustedSourceApprove,
                requestId = requestId,
                serializer = TrustedSourceApproveRequestPayload.serializer(),
                payload = TrustedSourceApproveRequestPayload(
                    reviewId = review.reviewId,
                    confirmationToken = review.confirmationToken,
                    disclosureVersion = review.disclosureVersion,
                    usageScope = review.usageScope,
                ),
            )
        )
    }

    fun dismissTrustedSource() {
        val sourceReview = state.value.sourceReview
        if (
            sourceReview == null &&
            (pendingCitationResolveRequestId != null || pendingHistoricalSourceAttributionResolve != null)
        ) {
            clearPendingCitationResolve()
            clearPendingHistoricalSourceAttributionResolve()
            mutableState.update {
                it.copy(
                    isResolvingCitation = false,
                    resolvingSourceAttributionMessageId = null,
                    resolvingSourceAttributionIndex = null,
                    error = null,
                )
            }
            return
        }
        sourceReview ?: return
        if (pendingSourceReview == null) {
            mutableState.update { it.copy(sourceReview = null, error = null) }
            return
        }
        dismissTrustedSource(sourceReview.sourceAnchorId)
    }

    fun dismissTrustedSource(sourceAnchorId: String) {
        if (pendingTrustedSourceDismissRequestId != null) return
        val review = pendingSourceReview?.takeIf { it.sourceAnchorId == sourceAnchorId.trim() } ?: return
        if (!canSendRuntimeDocumentSearchCommand()) {
            showError("document_search_runtime_required")
            return
        }
        val requestId = TRUSTED_SOURCE_DISMISS_REQUEST_ID_PREFIX + UUID.randomUUID()
        pendingTrustedSourceDismissRequestId = requestId
        mutableState.update { it.copy(isDismissingTrustedSource = true, error = null) }
        sendEnvelope(
            envelope(
                type = MessageType.TrustedSourceDismiss,
                requestId = requestId,
                serializer = TrustedSourceDismissRequestPayload.serializer(),
                payload = TrustedSourceDismissRequestPayload(review.reviewId),
            )
        )
    }

    fun refreshTrustedSources() {
        if (pendingTrustedSourceListRequestId != null) return
        if (!canSendRuntimeDocumentSearchCommand()) {
            showError("document_search_runtime_required")
            return
        }
        val requestId = TRUSTED_SOURCE_LIST_REQUEST_ID_PREFIX + UUID.randomUUID()
        pendingTrustedSourceListRequestId = requestId
        pendingTrustedSourceListMutationGeneration = trustedSourceMutationGeneration
        mutableState.update { it.copy(isLoadingTrustedSources = true, error = null) }
        sendEnvelope(
            envelope(
                type = MessageType.TrustedSourceList,
                requestId = requestId,
                serializer = TrustedSourceListRequestPayload.serializer(),
                payload = TrustedSourceListRequestPayload(limit = MAX_RUNTIME_TRUSTED_SOURCES),
            )
        )
    }

    fun revokeTrustedSource(sourceAnchorId: String) {
        val anchorId = sourceAnchorId.trim()
        if (pendingTrustedSourceRevocationsByRequestId.containsValue(anchorId)) return
        val grantId = trustedSourceGrantsBySourceAnchorId[anchorId] ?: return
        removeTrustedSourceSelection(anchorId)
        if (!canSendRuntimeDocumentSearchCommand()) {
            showError("document_search_runtime_required")
            return
        }
        val requestId = TRUSTED_SOURCE_REVOKE_REQUEST_ID_PREFIX + UUID.randomUUID()
        pendingTrustedSourceRevocationsByRequestId[requestId] = anchorId
        mutableState.update {
            it.copy(
                revokingTrustedSourceAnchorIds = it.revokingTrustedSourceAnchorIds + anchorId,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.TrustedSourceRevoke,
                requestId = requestId,
                serializer = TrustedSourceRevokeRequestPayload.serializer(),
                payload = TrustedSourceRevokeRequestPayload(grantId),
            )
        )
    }

    fun generateMemorySummaryDraft(draftId: String) {
        val cleanDraftId = draftId.trim()
        if (cleanDraftId.isBlank()) return
        val current = state.value
        val draft = current.memorySummaryDrafts.firstOrNull { it.id == cleanDraftId } ?: return
        if (draft.summaryMethod != "deterministic_preview") return
        if (current.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        if (pendingMemorySummaryDraftGenerationsByRequestId.values.any { it.draft.id == cleanDraftId }) return
        if (cleanDraftId in pendingMemorySummaryDraftApprovalDraftIdsByRequestId.values) return
        if (cleanDraftId in pendingMemorySummaryDraftDismissalDraftIdsByRequestId.values) return
        when (current.selectedModelSendState()) {
            SelectedModelSendState.Missing -> {
                showError("select_chat_model")
                return
            }
            SelectedModelSendState.NotInstalled -> {
                showError("install_model_first")
                return
            }
            SelectedModelSendState.Ready -> Unit
        }
        val modelId = current.selectedModelId ?: return
        val requestId = UUID.randomUUID().toString()
        pendingMemorySummaryDraftGenerationsByRequestId[requestId] = PendingMemorySummaryDraftGeneration(
            draft = draft,
            modelId = modelId,
        )
        mutableState.update {
            it.copy(
                generatingMemorySummaryDraftIds = it.generatingMemorySummaryDraftIds + cleanDraftId,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.MemorySummaryDraftGenerate,
                requestId = requestId,
                serializer = MemorySummaryDraftGenerateRequestPayload.serializer(),
                payload = MemorySummaryDraftGenerateRequestPayload(
                    draftId = cleanDraftId,
                    model = modelId,
                    expectedSessionId = draft.session.sessionId,
                    expectedSourceMessageCount = draft.sourceMessageCount,
                ),
            )
        )
    }

    fun approveMemorySummaryDraft(draftId: String) {
        val cleanDraftId = draftId.trim()
        if (cleanDraftId.isBlank()) return
        val draft = state.value.memorySummaryDrafts.firstOrNull { it.id == cleanDraftId } ?: return
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        if (cleanDraftId in pendingMemorySummaryDraftApprovalDraftIdsByRequestId.values) return
        if (cleanDraftId in pendingMemorySummaryDraftDismissalDraftIdsByRequestId.values) return
        if (pendingMemorySummaryDraftGenerationsByRequestId.values.any { it.draft.id == cleanDraftId }) return
        val requestId = UUID.randomUUID().toString()
        pendingMemorySummaryDraftApprovalDraftIdsByRequestId[requestId] = cleanDraftId
        mutableState.update {
            it.copy(
                approvingMemorySummaryDraftIds = it.approvingMemorySummaryDraftIds + cleanDraftId,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.MemorySummaryDraftApprove,
                requestId = requestId,
                serializer = MemorySummaryDraftApprovePayload.serializer(),
                payload = MemorySummaryDraftApprovePayload(
                    draftId = cleanDraftId,
                    enabled = true,
                    expectedSessionId = draft.session.sessionId,
                    expectedSourceMessageCount = draft.sourceMessageCount,
                ),
            )
        )
    }

    fun dismissMemorySummaryDraft(draftId: String) {
        val cleanDraftId = draftId.trim()
        if (cleanDraftId.isBlank()) return
        val draft = state.value.memorySummaryDrafts.firstOrNull { it.id == cleanDraftId } ?: return
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeMemoryCommand()) {
            showError("memory_runtime_required")
            return
        }
        if (cleanDraftId in pendingMemorySummaryDraftDismissalDraftIdsByRequestId.values) return
        if (cleanDraftId in pendingMemorySummaryDraftApprovalDraftIdsByRequestId.values) return
        if (pendingMemorySummaryDraftGenerationsByRequestId.values.any { it.draft.id == cleanDraftId }) return
        val requestId = UUID.randomUUID().toString()
        pendingMemorySummaryDraftDismissalDraftIdsByRequestId[requestId] = cleanDraftId
        mutableState.update {
            it.copy(
                dismissingMemorySummaryDraftIds = it.dismissingMemorySummaryDraftIds + cleanDraftId,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.MemorySummaryDraftDismiss,
                requestId = requestId,
                serializer = MemorySummaryDraftDismissPayload.serializer(),
                payload = MemorySummaryDraftDismissPayload(
                    draftId = cleanDraftId,
                    expectedSessionId = draft.session.sessionId,
                    expectedSourceMessageCount = draft.sourceMessageCount,
                ),
            )
        )
    }

    fun refreshRuntimeChatHistory() {
        refreshRuntimeChatHistory(query = null)
    }

    fun refreshRuntimeChatHistory(query: String?) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!canSendRuntimeChatHistoryCommand()) {
            showError("chat_history_runtime_required")
            return
        }
        requestRuntimeChatSessions(query = query)
    }

    fun setTrustedRuntimeAutoReconnectEnabled(enabled: Boolean) {
        if (rejectUserMutationWhileStreaming()) return
        persistTrustedRuntimeAutoReconnectEnabled(enabled)
        if (!enabled) {
            reconnectJob?.cancel()
            reconnectJob = null
            return
        }
        restoreTrustedRuntimeConnection()
    }

    fun connectToTrustedRuntime() {
        if (rejectUserMutationWhileStreaming()) return
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
                revokeAuthenticatedRuntimeSessionState()
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

    fun trustRuntimeFromPairingQr(
        rawValue: String,
        requireRemoteRoute: Boolean = true,
    ) {
        if (rejectUserMutationWhileStreaming()) return
        viewModelScope.launch {
            cancelPendingPairingRetry()
            cancelPendingPairingDiscoveryTimeout()
            mutableState.update { it.copy(routeRefreshNoticeRuntimeName = null) }
            val payload = when (
                val parsed = parseRuntimePairingQrPayload(
                    rawValue = rawValue,
                    allowDebugLoopbackRelay = BuildConfig.DEBUG,
                    allowDiagnosticLocalDirectEndpoint = BuildConfig.DEBUG,
                    requireRemoteRoute = requireRemoteRoute,
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
                nowEpochMillis = nowMillis(),
            )
            if (refreshedTrustedRuntime != null) {
                clearPendingRouteRefreshRequest()
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

            if (
                pendingPairingPayload != payload &&
                shouldPreemptActiveConnectionForPairingQr(state.value, payload)
            ) {
                closeRuntimeConnection()
            }

            pendingPairingPayload = payload
            persistPendingPairingPayload(payload)
            val plan = pendingPairingConnectionPlan(
                state = state.value,
                payload = payload,
                allowUsbReverseFallback = BuildConfig.DEBUG,
            )
            mutableState.value = plan.pendingState

            if (plan.shouldStartDiscovery) {
                startDiscoveryInternal()
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
        if (pendingPairingRequestPayload == payload) {
            Log.d(TAG, "Skipping duplicate pairing.request for runtime=${payload.runtimeDeviceId}")
            return
        }
        pendingPairingRequestPayload = payload
        runCatching {
            val identity = deviceIdentityStore.loadOrCreate()
            val runtimePublicKey = requireNotNull(payload.runtimePublicKeyBase64) {
                "Pairing QR does not contain a runtime public key"
            }
            val requestId = UUID.randomUUID().toString()
            val transportBinding = activeChannel?.transportSecurityContext?.bindingId
            val clientRequest = InitialPairingClientRequest(
                scheme = INITIAL_PAIRING_PROOF_SCHEME,
                protocolVersion = 1,
                requestId = requestId,
                pairingNonce = payload.pairingNonce,
                pairingCode = payload.pairingCode,
                runtimeDeviceId = payload.runtimeDeviceId,
                runtimePublicKey = runtimePublicKey,
                runtimeKeyFingerprint = payload.fingerprint,
                clientDeviceId = identity.deviceId,
                clientDeviceName = identity.deviceName,
                clientPublicKey = identity.publicKeyBase64,
                clientKeyFingerprint = initialPairingPublicKeyFingerprint(identity.publicKeyBase64),
                transportBinding = transportBinding,
            )
            val pairingSignature = identity.signInitialPairingRequest(clientRequest)
            pendingInitialPairingRequest = PendingInitialPairingRequest(
                payload = payload,
                requestId = requestId,
                requestDigest = clientRequest.digest(),
                clientDeviceId = identity.deviceId,
                transportBinding = transportBinding,
            )

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
                        pairingProofScheme = INITIAL_PAIRING_PROOF_SCHEME,
                        pairingSignature = pairingSignature,
                        transportBinding = transportBinding,
                    ),
                    requestId = requestId,
                )
            )
        }
            .onSuccess {
                cancelPendingPairingRetry()
                cancelPendingPairingDiscoveryTimeout()
            }
            .onFailure { error ->
                cancelPendingPairingRetry()
                cancelPendingPairingDiscoveryTimeout()
                pendingPairingPayload = null
                clearPendingPairingRequest()
                clearPersistedPendingPairingRoute()
                mutableState.update { it.withClearedPendingPairing() }
                showError("device_identity_failed", error.message)
            }
    }

    private fun clearPendingPairingRequest() {
        pendingPairingRequestPayload = null
        pendingInitialPairingRequest = null
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
            startDiscoveryInternal()
            schedulePendingPairingDiscoveryTimeout(payload)
        }

        viewModelScope.launch {
            val target = pairingRuntimeConnectionTarget(
                state = state.value,
                payload = payload,
                allowUsbReverseFallback = BuildConfig.DEBUG,
            )
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
        if (rejectUserMutationWhileStreaming()) return
        startDiscoveryInternal()
    }

    private fun startDiscoveryInternal() {
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
                    it.copy(error = runtimeUiError("discovery_failed", error.message))
                }
            } finally {
                mutableState.update { it.copy(isDiscovering = false) }
            }
        }
    }

    private fun ensureTrustedRuntimeDiscovery() {
        if (discoveryJob?.isActive == true) return
        startDiscoveryInternal()
    }

    private suspend fun connectToPendingPairingRuntimeIfNeeded() {
        val payload = pendingPairingPayload ?: return
        val current = state.value
        if (current.isConnected || current.isConnecting) return
        val target = pairingRuntimeConnectionTarget(
            state = current,
            payload = payload,
            allowUsbReverseFallback = BuildConfig.DEBUG,
        ) ?: return
        mutableState.update { it.copy(isPairingAwaitingRoute = false) }
        if (connectToRuntime(target, requestHealthAfterConnect = false)) {
            sendPairingRequest(payload)
        } else {
            handlePendingPairingConnectionFailure(payload)
        }
    }

    private fun handlePendingPairingConnectionFailure(payload: RuntimePairingPayload) {
        val currentError = state.value.error
        if (
            payload.hasRelayRoute() &&
            currentError?.diagnosticCode == "route_diagnostic_relay_unreachable_from_device"
        ) {
            cancelPendingPairingRetry()
            cancelPendingPairingDiscoveryTimeout()
            pendingPairingPayload = null
            clearPendingPairingRequest()
            clearPersistedPendingPairingRoute()
            mutableState.update {
                it.withClearedPendingPairing().copy(error = currentError)
            }
            return
        }
        if (payload.hasExpiredRemoteRoute()) {
            cancelPendingPairingRetry()
            cancelPendingPairingDiscoveryTimeout()
            pendingPairingPayload = null
            clearPendingPairingRequest()
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
        if (payload.hasRemoteRoute()) {
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
        clearPendingPairingRequest()
        cancelPendingPairingDiscoveryTimeout()
        clearPersistedPendingPairingRoute()
        mutableState.update { it.withClearedPendingPairing() }
    }

    private fun schedulePendingPairingRetry(payload: RuntimePairingPayload) {
        if (pendingPairingPayload != payload || !payload.hasRemoteRoute()) return
        if (pendingPairingRetryAttempts >= MAX_PENDING_PAIRING_RETRY_ATTEMPTS) {
            cancelPendingPairingRetry()
            pendingPairingPayload = null
            clearPendingPairingRequest()
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
            clearPendingPairingRequest()
            val target = pairingRuntimeConnectionTarget(
                state = current,
                payload = payload,
                allowUsbReverseFallback = BuildConfig.DEBUG,
            )
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

    private fun shouldIncludeDebugUsbReverseFallback(target: RuntimeConnectionTarget): Boolean {
        if (!BuildConfig.DEBUG) return false
        if (state.value.runtimeEndpointSource == RuntimeEndpointSource.UsbReverse) return true
        val pending = pendingPairingPayload ?: return false
        if (pending.hasRemoteRoute()) return false
        val identity = target.identity ?: return false
        return pending.matchesIdentity(identity)
    }

    private fun schedulePendingPairingDiscoveryTimeout(payload: RuntimePairingPayload) {
        if (pendingPairingPayload != payload || !payload.shouldWaitForDiscoveryRoute()) return
        pendingPairingDiscoveryTimeoutJob?.cancel()
        pendingPairingDiscoveryTimeoutJob = viewModelScope.launch {
            delay(PENDING_PAIRING_DISCOVERY_TIMEOUT_MS)
            if (pendingPairingPayload != payload) return@launch
            val current = state.value
            if (current.isConnected || current.isConnecting) return@launch
            if (
                pairingRuntimeConnectionTarget(
                    state = current,
                    payload = payload,
                    allowUsbReverseFallback = BuildConfig.DEBUG,
                ) != null
            ) {
                return@launch
            }
            pendingPairingPayload = null
            clearPendingPairingRequest()
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
        if (rejectUserMutationWhileStreaming()) return
        stopDiscoveryInternal()
    }

    private fun stopDiscoveryInternal() {
        discoveryJob?.cancel()
        discoveryJob = null
        cancelPendingPairingRetry()
        cancelPendingPairingDiscoveryTimeout()
        pendingPairingPayload = null
        clearPendingPairingRequest()
        clearPersistedPendingPairingRoute()
        mutableState.update {
            it.withClearedPendingPairing().copy(
                isDiscovering = false,
            )
        }
    }

    fun useDiscoveredRuntime(peer: RuntimeDiscoveredRuntime) {
        if (rejectUserMutationWhileStreaming()) return
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
        if (rejectUserMutationWhileStreaming()) return
        persistTrustedRuntimeAutoReconnectEnabled(false)
        closeRuntimeConnection()
        viewModelScope.launch {
            pairingStore.forgetRuntime()
            mutableState.update { it.copy(routeRefreshNoticeRuntimeName = null, error = null) }
        }
    }

    fun disconnect() {
        if (rejectUserMutationWhileStreaming()) return
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
        resetMemoryDuplicateSuggestionsAuthority()
        resetMemorySemanticDuplicateSuggestionsAuthority()
        resetMemorySemanticDuplicateClustersAuthority()
        activeChannel?.close()
        activeChannel = null
        activeConnectionGeneration += 1L
        client.close()
        isSessionAuthenticated = false
        runtimeSessionAuthorityGeneration += 1L
        runtimeChatSessionsAuthoritativeSyncSupported = false
        runtimeChatSessionsBulkAuthorityEnabled = false
        clearPendingRuntimeAuthentication()
        closedRuntimeAuthenticationRequestIds.clear()
        cancelPendingPairingDiscoveryTimeout()
        pendingModelPullRequestId = null
        clearPendingModelsListRequest()
        modelCatalogAcceptedAuthorityGeneration = null
        clearPendingMemoryListRequest()
        pendingMemorySummaryDraftsRequestId = null
        clearPendingRuntimeDocumentRequests()
        pendingMemorySummaryDraftGenerationsByRequestId.clear()
        pendingMemorySummaryDraftApprovalDraftIdsByRequestId.clear()
        pendingMemorySummaryDraftDismissalDraftIdsByRequestId.clear()
        clearPendingRouteRefreshRequest()
        pendingPairingPayload = null
        clearPendingPairingRequest()
        clearPendingRuntimeHistoryRequests()
        clearPendingChatSessionsBulkLifecycle()
        clearRuntimeChatSearchAuthority()
        rollbackAndClearPendingRuntimeChatSessionMutations()
        modelIdToSelectAfterRefresh = null
        mutableState.update {
            it.withClearedPendingPairing().copy(
                isConnected = false,
                isConnecting = false,
                isStreaming = false,
                installingModelId = null,
                activeRequestId = null,
                memorySummaryDrafts = emptyList(),
                memoryDuplicateSuggestionGroups = emptyList(),
                memoryDuplicateSuggestionsScannedCount = 0,
                memoryDuplicateSuggestionsTruncated = false,
                hasMemoryDuplicateSuggestionsResult = false,
                isScanningMemoryDuplicateSuggestions = false,
                memoryDuplicateSuggestionsAvailable = false,
                generatingMemorySummaryDraftIds = emptySet(),
                approvingMemorySummaryDraftIds = emptySet(),
                dismissingMemorySummaryDraftIds = emptySet(),
                documentCatalog = RuntimeDocumentCatalog(),
                isLoadingDocumentCatalog = false,
                documentSearchQuery = "",
                documentSearchResults = emptyList(),
                isSearchingDocuments = false,
                chatSessionSearchQuery = null,
                chatSessionSearchResults = emptyList(),
                memorySearchQuery = null,
                memorySearchResults = emptyList(),
                runtimeStatus = "disconnected",
                activeRouteKind = null,
                routeRefreshNoticeRuntimeName = null,
            )
        }
    }

    fun requestRuntimeHealth() {
        if (rejectUserMutationWhileStreaming()) return
        requestRuntimeHealthInternal()
    }

    private fun requestRuntimeHealthInternal() {
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }
        sendEnvelope(ProtocolEnvelope(type = MessageType.RuntimeHealth))
    }

    fun requestModels() {
        if (rejectUserMutationWhileStreaming()) return
        requestModelsInternal()
    }

    private fun requestModelsInternal() {
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }
        val channel = activeChannel?.takeIf(RuntimeProtocolChannel::isConnected) ?: return
        val requestId = MODELS_LIST_REQUEST_ID_PREFIX + UUID.randomUUID()
        pendingModelsListRequest = PendingModelsListRequest(
            requestId = requestId,
            channel = channel,
            connectionGeneration = activeConnectionGeneration,
            authorityGeneration = runtimeSessionAuthorityGeneration,
        )
        mutableState.update {
            it.copy(
                isLoadingModels = true,
                error = null,
            )
        }
        sendEnvelope(ProtocolEnvelope(type = MessageType.ModelsList, requestId = requestId))
    }

    private fun requestRuntimeChatSessions(query: String? = null) {
        if (!isSessionAuthenticated) return
        val channel = activeChannel?.takeIf(RuntimeProtocolChannel::isConnected) ?: return
        if (pendingChatSessionsBulkLifecycle != null) {
            showError("chat_history_loading")
            return
        }
        clearPendingChatSessionsListRun()
        val requestId = CHAT_SESSIONS_LIST_REQUEST_ID_PREFIX + UUID.randomUUID()
        val normalizedQuery = query?.trim()?.ifBlank { null }
        pendingChatSessionsRequestId = requestId
        pendingChatSessionsQuery = normalizedQuery
        pendingChatSessionsListRun = PendingChatSessionsListRun(
            requestId = requestId,
            query = normalizedQuery,
            channel = channel,
            connectionGeneration = activeConnectionGeneration,
            authorityGeneration = runtimeSessionAuthorityGeneration,
        )
        mutableState.update {
            it.copy(
                isLoadingChatSessions = true,
            )
        }
        val embeddingModelId = normalizedQuery?.let { state.value.selectedEmbeddingModelId }
        sendEnvelope(
            envelope(
                type = MessageType.ChatSessionsList,
                requestId = requestId,
                serializer = ChatSessionsListRequestPayload.serializer(),
                payload = ChatSessionsListRequestPayload(
                    limit = MAX_RUNTIME_CHAT_SESSIONS,
                    includeArchived = true,
                    query = normalizedQuery,
                    embeddingModelId = embeddingModelId,
                ),
            )
        )
    }

    private fun requestRuntimeChatSessionsContinuation(
        run: PendingChatSessionsListRun,
        cursor: String,
    ) {
        if (!run.hasCurrentRuntimeAuthority()) {
            clearPendingChatSessionsListRun(run)
            return
        }
        closeRuntimeChatHistoryRequest(run.correlation())
        val requestId = CHAT_SESSIONS_LIST_REQUEST_ID_PREFIX + UUID.randomUUID()
        run.requestId = requestId
        pendingChatSessionsRequestId = requestId
        pendingChatSessionsQuery = run.query
        sendEnvelope(
            envelope(
                type = MessageType.ChatSessionsList,
                requestId = requestId,
                serializer = ChatSessionsListRequestPayload.serializer(),
                payload = ChatSessionsListRequestPayload(cursor = cursor),
            )
        )
    }

    private fun requestRuntimeChatMessages(sessionId: String) {
        if (!isSessionAuthenticated) return
        val channel = activeChannel?.takeIf(RuntimeProtocolChannel::isConnected) ?: return
        if (sessionId.isBlank()) return
        val session = persistedRuntimeData.sessions.firstOrNull { it.id == sessionId }
        if (session?.runtimeOwned != true || session.archivedAtMillis != null) return
        clearPendingChatMessagesRequest()
        val requestId = CHAT_MESSAGES_LIST_REQUEST_ID_PREFIX + UUID.randomUUID()
        pendingChatMessagesRequestId = requestId
        pendingChatMessagesSessionId = sessionId
        pendingChatMessagesRequestCorrelation = RuntimeChatHistoryRequestCorrelation(
            requestId = requestId,
            type = MessageType.ChatMessagesList,
            channel = channel,
            connectionGeneration = activeConnectionGeneration,
            authorityGeneration = runtimeSessionAuthorityGeneration,
        )
        mutableState.update { current ->
            if (current.activeChatSessionId == sessionId) {
                current.copy(
                    loadingChatSessionId = sessionId,
                    error = null,
                )
            } else {
                current
            }
        }
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

    private fun requestRuntimeMemory(query: String? = null, allowEmbeddingModel: Boolean = true) {
        val channel = activeChannel
        if (!isSessionAuthenticated || channel?.isConnected != true) return
        if (pendingMemoryListRequestId != null) return
        val normalizedQuery = query?.trim()?.ifBlank { null }
        if (normalizedQuery == null) {
            memoryDuplicateSuggestionsListAcceptedAuthorityGeneration = null
            memorySemanticDuplicateSuggestionsListAcceptedAuthorityGeneration = null
            memorySemanticDuplicateClustersListAcceptedAuthorityGeneration = null
            clearMemoryDuplicateSuggestions()
            clearMemorySemanticDuplicateSuggestions()
            clearMemorySemanticDuplicateClusters()
            mutableState.update {
                it.copy(
                    memoryDuplicateSuggestionsAvailable = false,
                    memorySemanticDuplicateSuggestionsAvailable = false,
                    memorySemanticDuplicateClustersAvailable = false,
                )
            }
        }
        val requestId = UUID.randomUUID().toString()
        pendingMemoryListRequestId = requestId
        pendingMemoryListChannel = channel
        pendingMemoryListConnectionGeneration = activeConnectionGeneration
        pendingMemoryListAuthorityGeneration = runtimeSessionAuthorityGeneration
        pendingMemoryListQuery = normalizedQuery
        val embeddingModelId = normalizedQuery
            ?.takeIf { allowEmbeddingModel }
            ?.let { state.value.selectedEmbeddingModelId }
        pendingMemoryListEmbeddingModelId = embeddingModelId
        if (normalizedQuery == null) {
            sendEnvelope(ProtocolEnvelope(type = MessageType.MemoryList, requestId = requestId))
        } else {
            sendEnvelope(
                envelope(
                    type = MessageType.MemoryList,
                    requestId = requestId,
                    serializer = MemoryListRequestPayload.serializer(),
                    payload = MemoryListRequestPayload(
                        query = normalizedQuery,
                        embeddingModelId = embeddingModelId,
                    ),
                )
            )
        }
    }

    private fun requestRuntimeMemorySummaryDrafts() {
        if (!isSessionAuthenticated || activeChannel?.isConnected != true) return
        if (pendingMemorySummaryDraftsRequestId != null) return
        val requestId = UUID.randomUUID().toString()
        pendingMemorySummaryDraftsRequestId = requestId
        sendEnvelope(
            envelope(
                type = MessageType.MemorySummaryDraftsList,
                requestId = requestId,
                serializer = MemorySummaryDraftsListRequestPayload.serializer(),
                payload = MemorySummaryDraftsListRequestPayload(
                    limit = MAX_RUNTIME_MEMORY_SUMMARY_DRAFTS,
                ),
            )
        )
    }

    private fun requestRuntimeDocumentCatalog() {
        if (!isSessionAuthenticated || activeChannel?.isConnected != true) return
        if (pendingDocumentCatalogRequestId != null) return
        val requestId = UUID.randomUUID().toString()
        pendingDocumentCatalogRequestId = requestId
        mutableState.update {
            it.copy(
                isLoadingDocumentCatalog = true,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.IndexDocumentsList,
                requestId = requestId,
                serializer = IndexDocumentsListRequestPayload.serializer(),
                payload = IndexDocumentsListRequestPayload(
                    limit = MAX_RUNTIME_DOCUMENT_CATALOG_ROWS,
                ),
            )
        )
    }

    private fun requestRuntimeDocumentSearch(query: String) {
        val embeddingModelId = state.value.selectedEmbeddingModelId
        requestRuntimeDocumentSearch(
            payload = RetrievalQueryRequestPayload(
                query = query,
                limit = MAX_RUNTIME_DOCUMENT_SEARCH_RESULTS,
                maxSnippetCharacters = MAX_RUNTIME_DOCUMENT_SNIPPET_CHARACTERS,
                embeddingModelId = embeddingModelId,
            ),
            canRetryWithoutEmbedding = embeddingModelId != null,
        )
    }

    private fun requestRuntimeDocumentSearch(
        payload: RetrievalQueryRequestPayload,
        canRetryWithoutEmbedding: Boolean,
    ) {
        if (!isSessionAuthenticated || activeChannel?.isConnected != true) return
        if (pendingDocumentSearchRequestId != null) return
        val requestId = DOCUMENT_SEARCH_REQUEST_ID_PREFIX + UUID.randomUUID()
        pendingDocumentSearchRequestId = requestId
        pendingDocumentSearchPayload = payload
        pendingDocumentSearchCanRetryWithoutEmbedding = canRetryWithoutEmbedding
        mutableState.update {
            it.copy(
                documentSearchQuery = payload.query,
                isSearchingDocuments = true,
                error = null,
            )
        }
        sendEnvelope(
            envelope(
                type = MessageType.RetrievalQuery,
                requestId = requestId,
                serializer = RetrievalQueryRequestPayload.serializer(),
                payload = payload,
            )
        )
    }

    private fun sendRuntimeChatSessionLifecycleIfNeeded(
        session: PersistedChatSession,
        type: String,
        restoreAsActive: Boolean = false,
    ) {
        if (!session.runtimeOwned) return
        if (!isSessionAuthenticated || activeChannel?.isConnected != true) return
        val requestId = UUID.randomUUID().toString()
        pendingChatSessionLifecycleRequestIds += requestId
        pendingChatSessionLifecycleMutationsByRequestId[requestId] = PendingChatSessionLifecycleMutation(
            sessionId = session.id,
            sequence = ++pendingChatSessionMutationSequence,
            type = type,
            previousSession = session,
            restoreAsActive = restoreAsActive,
        )
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
        pendingChatSessionRenameMutationsByRequestId[requestId] = PendingChatSessionRenameMutation(
            sessionId = session.id,
            sequence = ++pendingChatSessionMutationSequence,
            previousTitle = session.title,
            previousTitleManuallyEdited = session.titleManuallyEdited,
            previousTitleGenerated = session.titleGenerated,
            previousUpdatedAtMillis = session.updatedAtMillis,
        )
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
        if (state.value.isChatHistoryActionPending) {
            showError("chat_history_loading")
            return true
        }
        val loadingSessionId = state.value.loadingChatSessionId
        if (
            loadingSessionId != null &&
            sessions.any { session -> session.runtimeOwned && session.id == loadingSessionId }
        ) {
            showError("chat_history_loading")
            return true
        }
        val pendingMutationSessionIds =
            pendingChatSessionLifecycleMutationsByRequestId.values.mapTo(mutableSetOf()) { it.sessionId } +
                pendingChatSessionRenameMutationsByRequestId.values.map { it.sessionId }
        if (sessions.any { session -> session.runtimeOwned && session.id in pendingMutationSessionIds }) {
            showError("chat_history_loading")
            return true
        }
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
        val current = state.value
        if (current.isStreaming) {
            showError("generation_in_progress")
            return
        }
        val model = current.models.firstOrNull { it.id == modelId }
        if (model == null) {
            showError("select_chat_model")
            return
        }
        if (!model.isChatModel()) {
            showError("select_chat_model")
            return
        }
        if (!model.isRuntimeHostLocalModel()) {
            showError("select_chat_model")
            return
        }
        if (!model.installed) {
            requestModelInstall(modelId)
            return
        }
        persistSelectedModel(modelId)
    }

    fun selectEmbeddingModel(modelId: String?) {
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (modelId == null) {
            persistSelectedEmbeddingModel(null)
            return
        }
        val model = state.value.models.firstOrNull { it.id == modelId }
        if (
            model == null ||
            !isCanonicalProviderQualifiedModelId(model.id) ||
            !model.isEmbeddingModel()
        ) {
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
        if (state.value.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }

        val model = state.value.models.firstOrNull { it.id == modelId }
        if (model == null) {
            showError("select_chat_model")
            return
        }
        if (!model.isChatModel()) {
            showError("select_chat_model")
            return
        }
        if (!model.isRuntimeHostLocalModel()) {
            showError("select_chat_model")
            return
        }
        if (model.installed) {
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
        val startedWithoutActiveSession = current.activeChatSessionId == null
        if (current.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (rejectUserMutationWhileActiveChatMessagesLoading()) return
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
        val trustedSourceGrantIds = trustedSourceGrantIdsForSelection(current) ?: return
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
        clearPendingHistoricalSourceAttributionResolve()
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
        persistComposerDraft("", sessionId = sessionId)
        clearPendingAttachmentsForSession(sessionId)
        if (startedWithoutActiveSession) {
            persistComposerDraft("", sessionId = null)
            clearPendingAttachmentsForSession(null)
        }
        mutableState.update {
            it.copy(
                activeChatSessionId = sessionId,
                chatInput = "",
                pendingAttachments = emptyList(),
                selectedTrustedSourceAnchorIds = emptyList(),
                messages = updatedMessages,
                activeRequestId = requestId,
                isStreaming = true,
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
                        attachments = attachments,
                    ),
                    locale = current.runtimeRequestLocale(),
                    trustedSourceGrantIds = trustedSourceGrantIds,
                )
            )
        )
    }

    fun regenerateLatestResponse() {
        val current = state.value
        if (current.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (rejectUserMutationWhileActiveChatMessagesLoading()) return
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
        if (!current.isConnected) {
            showError("connect_first")
            return
        }
        if (!isSessionAuthenticated) {
            showError("authentication_required")
            return
        }

        val sessionId = current.activeChatSessionId ?: run {
            showError("regenerate_unavailable")
            return
        }
        val retry = retryLatestAssistantResponseCandidate(current) ?: run {
            showError("regenerate_unavailable")
            return
        }
        if (retry.precedingUserMessage.attachments.isNotEmpty()) {
            showError("regenerate_attachment_context_unavailable")
            return
        }

        val model = current.selectedModelId ?: return
        val trustedSourceGrantIds = trustedSourceGrantIdsForSelection(current) ?: return
        clearPendingHistoricalSourceAttributionResolve()
        val requestId = UUID.randomUUID().toString()
        val assistantMessage = RuntimeChatMessage(role = "assistant", content = "")
        val updatedMessages = retry.contextMessages + assistantMessage
        mutableState.update {
            it.copy(
                messages = updatedMessages,
                activeRequestId = requestId,
                isStreaming = true,
                selectedTrustedSourceAnchorIds = emptyList(),
                error = null,
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
                        messages = retry.contextMessages,
                    ),
                    locale = current.runtimeRequestLocale(),
                    trustedSourceGrantIds = trustedSourceGrantIds,
                )
            )
        )
    }

    fun retryLatestAssistantResponse() {
        regenerateLatestResponse()
    }

    fun reuseLatestUserMessageAsDraft() {
        val current = state.value
        if (current.isStreaming) {
            showError("generation_in_progress")
            return
        }
        if (rejectUserMutationWhileActiveChatMessagesLoading()) return
        val latestUserMessage = current.messages.lastOrNull {
            it.role == "user" && it.content.isNotBlank()
        } ?: run {
            showError("reuse_message_unavailable")
            return
        }
        if (latestUserMessage.attachments.isNotEmpty()) {
            showError("reuse_message_unavailable")
            return
        }
        clearPendingAttachmentsForSession()
        val cleanDraft = persistComposerDraft(latestUserMessage.content)
        mutableState.update {
            it.copy(
                chatInput = cleanDraft,
                pendingAttachments = emptyList(),
                error = null,
            )
        }
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
    ): Boolean = connectionMutex.withLock {
        if (hasActiveRuntimeConnectionForTarget(target)) {
            Log.d(TAG, "Skipping duplicate runtime connection ${target.connectionLogLabel()}")
            return@withLock true
        }

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
        clearPendingRouteRefreshRequest()
        activeChannel?.close()
        activeChannel = null
        activeConnectionGeneration += 1L
        client.close()
        clearPendingRuntimeAuthentication()
        closedRuntimeAuthenticationRequestIds.clear()
        revokeAuthenticatedRuntimeSessionState()

        val preflightError = relayReachabilityPreflightError(target)
        if (preflightError != null) {
            val current = state.value
            val trustedRuntimeWithoutFailedRelay = if (
                pendingPairingPayload == null &&
                preflightError.invalidatesStoredRemoteRoute()
            ) {
                current.trustedRuntime?.withoutInvalidatedRemoteRoute(preflightError)
            } else {
                null
            }
            Log.e(
                TAG,
                "Runtime connection preflight failed code=${preflightError.code}" +
                    " diagnostic=${preflightError.diagnosticCode ?: "none"}" +
                    " target=${target.connectionLogLabel()}",
            )
            val updatedState = current.copy(
                isConnected = false,
                isConnecting = false,
                runtimeStatus = "failed",
                activeRouteKind = null,
                error = preflightError,
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
            return@withLock false
        }

        val result = runCatching {
            Log.d(
                TAG,
                "Connecting to runtime ${target.connectionLogLabel()}"
            )
            connectionManager.connectWithRoute(target)
        }.onSuccess { connection ->
            activeChannel = connection.channel
            activeConnectionGeneration += 1L
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
                uiError.invalidatesStoredRemoteRoute()
            ) {
                current.trustedRuntime?.withoutInvalidatedRemoteRoute(uiError)
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
        return@withLock result.isSuccess
    }

    private fun hasActiveRuntimeConnectionForTarget(target: RuntimeConnectionTarget): Boolean {
        val identity = target.identity ?: return false
        val channel = activeChannel ?: return false
        if (!channel.isConnected) return false
        val current = state.value
        if (!current.isConnected || current.isConnecting) return false
        val trustedMatches = current.trustedRuntime?.matchesIdentity(identity) == true
        val pendingPairingMatches = pendingPairingPayload?.matchesIdentity(identity) == true
        return trustedMatches || pendingPairingMatches
    }

    private suspend fun relayReachabilityPreflightError(target: RuntimeConnectionTarget): RuntimeUiError? {
        when (target.endpointHint?.source) {
            RuntimeEndpointSource.BonjourDiscovery,
            RuntimeEndpointSource.UsbReverse,
            RuntimeEndpointSource.Emulator,
            RuntimeEndpointSource.Manual -> return null
            RuntimeEndpointSource.TrustedLastKnown,
            RuntimeEndpointSource.PairingQr,
            null -> Unit
        }
        val identity = target.identity ?: return null
        val relayRoute = remoteRoutePlanner.prepareRemoteRoutes(identity)
            .filterIsInstance<PreparedRemoteRuntimeRoute.Relay>()
            .firstOrNull()
            ?: return null
        val probeResult = runCatching {
            dependencies.relayReachabilityChecker.check(
                route = relayRoute,
                timeoutMillis = RELAY_REACHABILITY_PREFLIGHT_TIMEOUT_MS,
            )
        }.getOrDefault(RuntimeRelayProbeResult.Unsupported)
        if (probeResult != RuntimeRelayProbeResult.Unavailable) return null
        return RuntimeUiError(
            code = "remote_route_unreachable_from_device",
            diagnosticCode = "route_diagnostic_relay_unreachable_from_device",
            technicalDetail = "relay_host=${relayRoute.host} relay_port=${relayRoute.port}",
        )
    }

    private fun startReadLoop() {
        readJob?.cancel()
        val channel = activeChannel ?: client
        val connectionGeneration = activeConnectionGeneration
        readJob = viewModelScope.launch {
            while (isActive) {
                runCatching { channel.receive() }
                    .onSuccess { envelope ->
                        Log.d(TAG, "Received ${envelope.type} request_id=${envelope.requestId}")
                        handleEnvelope(envelope, channel, connectionGeneration)
                    }
                    .onFailure { error ->
                        if (
                            isActive &&
                            activeChannel === channel &&
                            activeConnectionGeneration == connectionGeneration
                        ) {
                            Log.e(TAG, "Runtime receive failed", error)
                            clearPendingRuntimeAuthentication()
                            closedRuntimeAuthenticationRequestIds.clear()
                            revokeAuthenticatedRuntimeSessionState()
                            clearPendingMemoryListRequest()
                            pendingMemorySummaryDraftsRequestId = null
                            pendingMemorySummaryDraftGenerationsByRequestId.clear()
                            clearPendingRuntimeDocumentRequests()
                            clearPendingPairingRequest()
                            clearPendingTitleRequest()
                            val current = state.value
                            val uiError = current.runtimeReceiveFailureUiError(error)
                            val trustedRuntimeWithoutFailedRelay = if (uiError.invalidatesStoredRemoteRoute()) {
                                current.trustedRuntime?.withoutInvalidatedRemoteRoute(uiError)
                            } else {
                                null
                            }
                            val updatedState = current.withRuntimeReceiveFailure(
                                uiError,
                            ).copy(
                                generatingMemorySummaryDraftIds = emptySet(),
                                memorySearchQuery = null,
                                memorySearchResults = emptyList(),
                                isLoadingDocumentCatalog = false,
                                isSearchingDocuments = false,
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

    private suspend fun handleEnvelope(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        when (envelope.type) {
            MessageType.AuthChallenge -> handleAuthChallenge(
                envelope,
                sourceChannel,
                sourceConnectionGeneration,
            )
            MessageType.AuthResponse -> handleAuthResponse(
                envelope,
                sourceChannel,
                sourceConnectionGeneration,
            )
            MessageType.PairingResult -> handlePairingResult(envelope)
            MessageType.RuntimeHealth -> handleRuntimeHealth(envelope)
            MessageType.ModelsList, MessageType.ModelsResult -> handleModels(
                envelope,
                sourceChannel,
                sourceConnectionGeneration,
            )
            MessageType.ModelsPull -> handleModelPull(envelope)
            MessageType.RelayAllocationChallenge -> handleRelayAllocationChallenge(envelope)
            MessageType.RouteRefresh -> handleRouteRefresh(envelope)
            MessageType.ChatSessionsList -> handleChatSessionsList(envelope)
            MessageType.ChatMessagesList -> handleChatMessagesList(envelope)
            MessageType.ChatDelta -> handleChatDelta(envelope)
            MessageType.ChatDone -> handleChatDone(envelope)
            MessageType.ChatCancel -> handleCancelAck(envelope)
            MessageType.ChatTitleResult -> handleChatTitleResult(envelope)
            MessageType.ChatSessionRename -> handleChatSessionRename(envelope)
            MessageType.ChatSessionArchive,
            MessageType.ChatSessionRestore,
            MessageType.ChatSessionDelete -> handleChatSessionLifecycle(envelope)
            MessageType.IndexDocumentsList -> handleIndexDocumentsList(envelope)
            MessageType.RetrievalQuery -> handleRetrievalQuery(envelope)
            MessageType.CitationResolve -> handleCitationResolve(envelope)
            MessageType.ChatSourceAttributionResolve ->
                handleHistoricalSourceAttributionResolve(
                    envelope,
                    sourceChannel,
                    sourceConnectionGeneration,
                )
            MessageType.TrustedSourceApprove -> handleTrustedSourceApprove(envelope)
            MessageType.TrustedSourceDismiss -> handleTrustedSourceDismiss(envelope)
            MessageType.TrustedSourceList -> handleTrustedSourceList(envelope)
            MessageType.TrustedSourceRevoke -> handleTrustedSourceRevoke(envelope)
            MessageType.MemoryList -> handleMemoryList(
                envelope,
                sourceChannel,
                sourceConnectionGeneration,
            )
            MessageType.MemoryDuplicateSuggestionsList -> handleMemoryDuplicateSuggestionsList(
                envelope,
                sourceChannel,
                sourceConnectionGeneration,
            )
            MessageType.MemorySemanticDuplicateSuggestionsList ->
                handleMemorySemanticDuplicateSuggestionsList(
                    envelope,
                    sourceChannel,
                    sourceConnectionGeneration,
                )
            MessageType.MemorySemanticDuplicateClustersList ->
                handleMemorySemanticDuplicateClustersList(
                    envelope,
                    sourceChannel,
                    sourceConnectionGeneration,
                )
            MessageType.MemorySummaryDraftsList -> handleMemorySummaryDraftsList(envelope)
            MessageType.MemorySummaryDraftGenerate -> handleMemorySummaryDraftGenerate(envelope)
            MessageType.MemorySummaryDraftApprove -> handleMemorySummaryDraftApprove(envelope)
            MessageType.MemorySummaryDraftDismiss -> handleMemorySummaryDraftDismiss(envelope)
            MessageType.MemoryUpsert -> handleMemoryUpsert(envelope)
            MessageType.MemoryDelete -> handleMemoryDelete(envelope)
            MessageType.Error -> handleError(
                envelope,
                sourceChannel,
                sourceConnectionGeneration,
            )
        }
    }

    private suspend fun handleAuthChallenge(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        val pending = pendingRuntimeAuthentication ?: return
        if (!pending.matchesActiveConnection(sourceChannel, sourceConnectionGeneration)) return
        if (pending.phase != RuntimeAuthenticationPhase.AwaitingChallenge) return
        if (pending.forcePairedClaim != null && envelope.requestId != pending.helloRequestId) return
        if (envelope.requestId in closedRuntimeAuthenticationRequestIds) return
        envelope.payload.authChallengeUnknownMetadataKey()?.let { unknownKey ->
            failRuntimeAuthentication(
                pending = pending,
                errorCode = "invalid_payload",
                detail = "auth.challenge response contains unsupported metadata: $unknownKey",
                retry = pending.forcePairedClaim != null,
            )
            return
        }
        val payload = decodePayload(AuthChallengePayload.serializer(), envelope.payload) ?: run {
            failRuntimeAuthentication(pending, retry = pending.forcePairedClaim != null)
            return
        }
        val identity = pending.identity ?: run {
            failRuntimeAuthentication(pending, errorCode = "authentication_failed")
            return
        }
        if (!verifyRuntimeAuthChallenge(payload, identity.deviceId, pending.channel)) {
            failRuntimeAuthentication(
                pending = pending,
                errorCode = "runtime_authentication_failed",
            )
            return
        }
        val sendingResponse = pending.copy(
            phase = RuntimeAuthenticationPhase.SendingResponse,
            challengeRequestId = envelope.requestId,
        )
        pendingRuntimeAuthentication = sendingResponse
        val sent = runCatching {
            sendEnvelopeInternal(
                envelope(
                    type = MessageType.AuthResponse,
                    serializer = AuthResponsePayload.serializer(),
                    payload = AuthResponsePayload(
                        deviceId = identity.deviceId,
                        nonce = payload.nonce,
                        signature = identity.signAuthenticationResponse(
                            nonce = payload.nonce,
                            transportBinding = payload.transportBinding,
                        ),
                        transportBinding = payload.transportBinding,
                    ),
                    requestId = envelope.requestId,
                ),
                pending.channel,
                pending.connectionGeneration,
            )
        }.getOrElse { error ->
            failRuntimeAuthentication(
                pending = sendingResponse,
                errorCode = "authentication_failed",
                detail = error.message,
            )
            false
        }
        if (!sent) return
        if (
            pendingRuntimeAuthentication == sendingResponse &&
            sendingResponse.matchesActiveConnection(sourceChannel, sourceConnectionGeneration)
        ) {
            pendingRuntimeAuthentication = sendingResponse.copy(
                phase = RuntimeAuthenticationPhase.AwaitingFinalResponse,
            )
        }
    }

    private fun verifyRuntimeAuthChallenge(
        payload: AuthChallengePayload,
        deviceId: String,
        channel: RuntimeProtocolChannel,
    ): Boolean {
        val transportBinding = channel.transportSecurityContext?.bindingId
        if (!authenticationTransportBindingMatches(payload.transportBinding, transportBinding)) return false
        val trustedRuntime = state.value.trustedRuntime ?: return transportBinding == null
        val runtimePublicKey = trustedRuntime.publicKeyBase64?.takeIf { it.isNotBlank() }
            ?: return transportBinding == null
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
            transportBinding = transportBinding,
        )
    }

    private fun handleAuthResponse(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        val pending = pendingRuntimeAuthentication ?: return
        if (!pending.matchesActiveConnection(sourceChannel, sourceConnectionGeneration)) return
        val expectedRequestId = pending.challengeRequestId
        val isPostPairingHelloResponse = pending.forcePairedClaim != null &&
            envelope.requestId == pending.helloRequestId
        if (envelope.requestId != expectedRequestId && !isPostPairingHelloResponse) return
        if (envelope.requestId in closedRuntimeAuthenticationRequestIds) return
        envelope.payload.authResponseResultUnknownMetadataKey()?.let { unknownKey ->
            failRuntimeAuthentication(
                pending = pending,
                errorCode = "invalid_payload",
                detail = "auth.response response contains unsupported metadata: $unknownKey",
                retry = pending.forcePairedClaim != null,
            )
            return
        }
        val payload = decodePayload(AuthResponsePayload.serializer(), envelope.payload) ?: run {
            failRuntimeAuthentication(pending, retry = pending.forcePairedClaim != null)
            return
        }
        if (
            pending.phase != RuntimeAuthenticationPhase.AwaitingFinalResponse ||
            envelope.requestId != expectedRequestId
        ) {
            return
        }
        val transportBinding = pending.channel.transportSecurityContext?.bindingId
        if (!authenticationTransportBindingMatches(payload.transportBinding, transportBinding)) {
            failRuntimeAuthentication(
                pending = pending,
                errorCode = "runtime_authentication_failed",
            )
            return
        }
        if (payload.accepted == true) {
            closeRuntimeAuthentication(pending)
            isSessionAuthenticated = true
            runtimeSessionAuthorityGeneration += 1L
            clearPendingModelsListRequest()
            modelCatalogAcceptedAuthorityGeneration = null
            resetMemoryDuplicateSuggestionsAuthority()
            resetMemorySemanticDuplicateSuggestionsAuthority()
            resetMemorySemanticDuplicateClustersAuthority()
            mutableState.update {
                it.copy(
                    runtimeStatus = "authenticated",
                    error = null,
                )
            }
            if (pending.forcePairedClaim == true) {
                requestRuntimeRouteRefresh(forcePairedClaim = true)
            } else {
                scheduleRuntimeRouteRefreshLease()
            }
            requestRuntimeHealthInternal()
            requestRuntimeChatSessions()
            requestRuntimeMemory()
            requestRuntimeMemorySummaryDrafts()
        } else {
            failRuntimeAuthentication(
                pending = pending,
                errorCode = "authentication_failed",
                detail = payload.message,
            )
        }
    }

    private fun PendingRuntimeAuthentication.matchesActiveConnection(
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        return channel === sourceChannel &&
            connectionGeneration == sourceConnectionGeneration &&
            activeChannel === sourceChannel &&
            activeConnectionGeneration == sourceConnectionGeneration
    }

    private fun closeRuntimeAuthentication(pending: PendingRuntimeAuthentication) {
        if (pendingRuntimeAuthentication?.helloRequestId == pending.helloRequestId) {
            pendingRuntimeAuthentication = null
        }
        closedRuntimeAuthenticationRequestIds += pending.helloRequestId
        pending.challengeRequestId?.let { closedRuntimeAuthenticationRequestIds += it }
    }

    private fun clearPendingRuntimeAuthentication() {
        pendingRuntimeAuthentication?.let(::closeRuntimeAuthentication)
    }

    private fun failRuntimeAuthentication(
        pending: PendingRuntimeAuthentication,
        errorCode: String? = null,
        detail: String? = null,
        retry: Boolean = false,
    ) {
        if (pendingRuntimeAuthentication?.helloRequestId != pending.helloRequestId) return
        closeRuntimeAuthentication(pending)
        revokeAuthenticatedRuntimeSessionState()
        if (errorCode != null) showError(errorCode, detail)
        if (
            retry &&
            pending.forcePairedClaim != null &&
            pending.attempt < MAX_POST_PAIRING_AUTHENTICATION_ATTEMPTS &&
            pending.matchesActiveConnection(pending.channel, pending.connectionGeneration) &&
            pending.channel.isConnected
        ) {
            sendHello(
                postPairingForcePairedClaim = requireNotNull(pending.forcePairedClaim),
                postPairingAuthenticationAttempt = pending.attempt + 1,
            )
        }
    }

    private fun handlePairingResult(envelope: ProtocolEnvelope) {
        envelope.payload.pairingResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "pairing.result response contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(PairingResultPayload.serializer(), envelope.payload) ?: return
        val pending = pendingPairingPayload
        val pendingRequest = pendingInitialPairingRequest
        if (!payload.accepted) {
            if (
                pending == null ||
                pendingRequest == null ||
                pendingRequest.payload != pending ||
                envelope.requestId != pendingRequest.requestId
            ) {
                showError("invalid_payload", "pairing.result does not match the active pairing request")
                return
            }
            cancelPendingPairingRetry()
            cancelPendingPairingDiscoveryTimeout()
            clearPendingPairingRequest()
            mutableState.update {
                it.copy(error = runtimeUiError("pairing_rejected", payload.message))
            }
            return
        }

        val hasRejectionMetadata = envelope.payload.keys.any { it in PAIRING_REJECTION_RESULT_PAYLOAD_KEYS }
        val currentTransportBinding = activeChannel?.transportSecurityContext?.bindingId
        if (pending == null || pendingRequest == null) {
            showError("invalid_payload", "pairing.result does not match the active pairing request")
            return
        }
        val acceptedProofIsValid = pendingRequest.payload == pending &&
            envelope.requestId == pendingRequest.requestId &&
            !hasRejectionMetadata &&
            currentTransportBinding == pendingRequest.transportBinding &&
            acceptedInitialPairingProofIsValid(
                pending = pending,
                pendingRequest = pendingRequest,
                payload = payload,
            )
        if (!acceptedProofIsValid) {
            cancelPendingPairingRetry()
            clearPendingPairingRequest()
            mutableState.update {
                it.copy(error = RuntimeUiError("runtime_identity_mismatch"))
            }
            return
        }

        viewModelScope.launch {
            if (activeChannel?.transportSecurityContext?.bindingId != pendingRequest.transportBinding) {
                clearPendingPairingRequest()
                mutableState.update {
                    it.copy(error = RuntimeUiError("runtime_identity_mismatch"))
                }
                return@launch
            }
            val trusted = trustedRuntimeFromAcceptedPairing(pending, payload)
            if (trusted == null) {
                cancelPendingPairingRetry()
                pendingPairingPayload = null
                clearPendingPairingRequest()
                clearPersistedPendingPairingRoute()
                mutableState.update {
                    it.withClearedPendingPairing().copy(
                        error = RuntimeUiError("runtime_identity_mismatch"),
                    )
                }
                return@launch
            }

            didAttemptTrustedRuntimeRestore = true
            pairingStore.trustRuntime(trusted)
            val sessionEndpoint = acceptedPairingCurrentEndpointHint(pending)
            val runtime = trusted.toRuntimeTrustedRuntime()
            cancelPendingPairingRetry()
            cancelPendingPairingDiscoveryTimeout()
            pendingPairingPayload = null
            clearPendingPairingRequest()
            clearPersistedPendingPairingRoute()
            revokeAuthenticatedRuntimeSessionState()
            publishPersistedRuntimeData(
                persistedRuntimeData.withPairingOnboardingCompleted(),
                save = true,
            )
            mutableState.update {
                it.withClearedPendingPairing()
                    .withTrustedRuntimeRouteFields(runtime, sessionEndpoint)
                    .copy(
                        runtimeStatus = "connected",
                        routeRefreshNoticeRuntimeName = null,
                        error = null,
                    )
            }
            val secureBinding = pendingRequest.transportBinding
                ?.takeIf(DeviceIdentity::isCanonicalTransportBinding)
            val forcePairedClaim =
                trusted.relayId != null &&
                secureBinding != null &&
                activeChannel?.transportSecurityContext?.bindingId == secureBinding
            sendHello(postPairingForcePairedClaim = forcePairedClaim)
        }
    }

    private fun sendHello(
        postPairingForcePairedClaim: Boolean? = null,
        postPairingAuthenticationAttempt: Int = 1,
    ) {
        val channelAtStart = activeChannel ?: return
        val connectionGenerationAtStart = activeConnectionGeneration
        val requestId = UUID.randomUUID().toString()
        clearPendingRuntimeAuthentication()
        pendingRuntimeAuthentication = PendingRuntimeAuthentication(
            helloRequestId = requestId,
            channel = channelAtStart,
            connectionGeneration = connectionGenerationAtStart,
            forcePairedClaim = postPairingForcePairedClaim,
            attempt = postPairingAuthenticationAttempt,
            phase = RuntimeAuthenticationPhase.PreparingHello,
        )
        viewModelScope.launch {
            runCatching { deviceIdentityStore.loadOrCreate() }
                .onSuccess { identity ->
                    val pending = pendingRuntimeAuthentication
                        ?.takeIf { it.helloRequestId == requestId }
                        ?: return@onSuccess
                    if (!pending.matchesActiveConnection(channelAtStart, connectionGenerationAtStart)) {
                        closeRuntimeAuthentication(pending)
                        return@onSuccess
                    }
                    val awaitingChallenge = pending.copy(
                        phase = RuntimeAuthenticationPhase.AwaitingChallenge,
                        identity = identity,
                    )
                    pendingRuntimeAuthentication = awaitingChallenge
                    val sent = sendEnvelopeInternal(
                        envelope(
                            type = MessageType.Hello,
                            serializer = HelloPayload.serializer(),
                            payload = HelloPayload(
                                deviceId = identity.deviceId,
                                deviceName = identity.deviceName,
                                capabilities = clientCapabilities,
                                transportBinding = channelAtStart.transportSecurityContext?.bindingId,
                            ),
                            requestId = requestId,
                        ),
                        channelAtStart,
                        connectionGenerationAtStart,
                    )
                    if (
                        !sent &&
                        pendingRuntimeAuthentication == awaitingChallenge &&
                        awaitingChallenge.matchesActiveConnection(channelAtStart, connectionGenerationAtStart)
                    ) {
                        failRuntimeAuthentication(
                            pending = awaitingChallenge,
                            errorCode = "authentication_failed",
                        )
                    }
                }
                .onFailure { error ->
                    pendingRuntimeAuthentication
                        ?.takeIf { it.helloRequestId == requestId }
                        ?.let { pending ->
                            failRuntimeAuthentication(
                                pending = pending,
                                errorCode = "device_identity_failed",
                                detail = error.message,
                            )
                        }
                }
        }
    }

    private fun requestRuntimeRouteRefresh(forcePairedClaim: Boolean = false) {
        if (!isSessionAuthenticated) return
        val channel = activeChannel ?: return
        if (!channel.isConnected) return
        val trustedRuntime = state.value.trustedRuntime ?: return
        val hasTicketGeneration = trustedRuntime.relayTicketGeneration != null
        val requiresPairedAuthorization = forcePairedClaim || hasTicketGeneration
        if (requiresPairedAuthorization) {
            val binding = channel.transportSecurityContext?.bindingId ?: return
            if (!DeviceIdentity.isCanonicalTransportBinding(binding)) return
            if (forcePairedClaim && hasTicketGeneration) return
        } else if (!dependencies.authenticatedRouteRefreshEnabled) {
            return
        }
        if (pendingRouteRefreshRequestId != null) return
        val requestId = UUID.randomUUID().toString()
        pendingRouteRefreshRequestId = requestId
        pendingRouteRefreshRequiresPairedAuthorization = requiresPairedAuthorization
        pendingPairedRelayAllocationAuthorization = null
        routeRefreshRequestTimeoutJob?.cancel()
        routeRefreshRequestTimeoutJob = if (requiresPairedAuthorization) {
            viewModelScope.launch {
                delay(ROUTE_REFRESH_REQUEST_TIMEOUT_MS)
                if (pendingRouteRefreshRequestId != requestId) return@launch
                clearPendingRouteRefreshRequest()
            }
        } else {
            null
        }
        sendEnvelope(ProtocolEnvelope(type = MessageType.RouteRefresh, requestId = requestId))
    }

    private suspend fun handleRelayAllocationChallenge(envelope: ProtocolEnvelope) {
        val requestId = pendingRouteRefreshRequestId ?: return
        if (envelope.requestId != requestId) return
        if (pendingPairedRelayAllocationAuthorization != null) return
        if (!isSessionAuthenticated) return
        val channel = activeChannel ?: return
        if (!channel.isConnected) return
        val binding = channel.transportSecurityContext?.bindingId ?: return
        if (!DeviceIdentity.isCanonicalTransportBinding(binding)) return
        val payload = decodePayload(RelayAllocationChallengePayload.serializer(), envelope.payload) ?: return
        val current = state.value.trustedRuntime ?: return
        val expectedOperation = if (current.relayTicketGeneration == null) "claim" else "renew"
        val storedTicketGeneration = current.relayTicketGeneration
        val routeToken = current.routeToken?.takeIf(::isCanonicalOpaqueRouteValue) ?: return
        val relayId = current.relayId ?: return
        val relayExpiresAt = current.relayExpiresAtEpochMillis ?: return
        val relayNonce = current.relayNonce ?: return
        val runtimeFingerprint = current.fingerprint ?: return
        if (
            payload.operation != expectedOperation ||
            payload.transportBinding != binding ||
            payload.currentRelayId != relayId ||
            payload.currentRelayExpiresAtEpochMillis != relayExpiresAt ||
            relayExpiresAt <= nowMillis() ||
            payload.currentRelayNonce != relayNonce ||
            payload.runtimeKeyFingerprint != runtimeFingerprint ||
            payload.routeTokenHash != pairedRelayRouteTokenHash(routeToken) ||
            (storedTicketGeneration != null && payload.currentTicketGeneration != storedTicketGeneration) ||
            payload.currentTicketGeneration == Long.MAX_VALUE ||
            payload.nextTicketGeneration != payload.currentTicketGeneration + 1L ||
            payload.challengeExpiresAtEpochMillis <= nowMillis()
        ) {
            return
        }

        val identity = runCatching { deviceIdentityStore.loadOrCreate() }.getOrNull() ?: return
        val clientFingerprint = runCatching {
            initialPairingPublicKeyFingerprint(identity.publicKeyBase64)
        }.getOrNull() ?: return
        val expectedPairedRelayId = runCatching {
            PairedRelayAllocationAuthorizationProof.pairedRelayId(
                routeToken = routeToken,
                runtimeKeyFingerprint = runtimeFingerprint,
                clientKeyFingerprint = clientFingerprint,
            )
        }.getOrNull() ?: return
        if (
            payload.clientKeyFingerprint != clientFingerprint ||
            payload.nextRelayId != expectedPairedRelayId
        ) {
            return
        }
        if (
            pendingRouteRefreshRequestId != requestId ||
            pendingPairedRelayAllocationAuthorization != null ||
            !isSessionAuthenticated ||
            activeChannel !== channel ||
            channel.transportSecurityContext?.bindingId != binding ||
            state.value.trustedRuntime != current ||
            payload.challengeExpiresAtEpochMillis <= nowMillis()
        ) {
            return
        }

        val authorization = runCatching {
            PairedRelayAllocationAuthorization(
                operation = payload.operation,
                requestId = requestId,
                authorizationId = payload.authorizationId,
                currentRelayId = payload.currentRelayId,
                nextRelayId = payload.nextRelayId,
                routeTokenHash = payload.routeTokenHash,
                runtimeKeyFingerprint = payload.runtimeKeyFingerprint,
                clientKeyFingerprint = payload.clientKeyFingerprint,
                currentTicketGeneration = payload.currentTicketGeneration,
                nextTicketGeneration = payload.nextTicketGeneration,
                currentRelayExpiresAtEpochMillis = payload.currentRelayExpiresAtEpochMillis,
                currentRelayNonce = payload.currentRelayNonce,
                nextRelayExpiresAtEpochMillis = payload.nextRelayExpiresAtEpochMillis,
                nextRelayNonce = payload.nextRelayNonce,
                challenge = payload.challenge,
                challengeExpiresAtEpochMillis = payload.challengeExpiresAtEpochMillis,
                transportBinding = payload.transportBinding,
            )
        }.getOrNull() ?: return
        val signature = runCatching {
            identity.signPairedRelayAllocationAuthorization(authorization)
        }.getOrNull() ?: return

        pendingPairedRelayAllocationAuthorization = PendingPairedRelayAllocationAuthorization(
            requestId = requestId,
            authorizationId = payload.authorizationId,
            challenge = payload.challenge,
            relayId = payload.nextRelayId,
            relayExpiresAtEpochMillis = payload.nextRelayExpiresAtEpochMillis,
            relayNonce = payload.nextRelayNonce,
            ticketGeneration = payload.nextTicketGeneration,
            transportBinding = binding,
            clientKeyFingerprint = clientFingerprint,
        )
        sendEnvelopeInternal(
            envelope(
                type = MessageType.RelayAllocationAuthorization,
                serializer = RelayAllocationAuthorizationPayload.serializer(),
                payload = RelayAllocationAuthorizationPayload(
                    proofScheme = payload.proofScheme,
                    authorizationId = payload.authorizationId,
                    challenge = payload.challenge,
                    clientKeyFingerprint = clientFingerprint,
                    transportBinding = binding,
                    clientSignature = signature,
                ),
                requestId = requestId,
            ),
            activeChannel,
        )
    }

    private fun handleRouteRefresh(envelope: ProtocolEnvelope) {
        if (pendingRouteRefreshRequestId != envelope.requestId) return
        val requiresPairedAuthorization = pendingRouteRefreshRequiresPairedAuthorization
        val pendingAuthorization = pendingPairedRelayAllocationAuthorization
        clearPendingRouteRefreshRequest()
        if (!envelope.payload.hasOnlyRouteRefreshResponsePayloadKeys()) {
            scheduleRuntimeRouteRefreshRetry()
            return
        }
        val payload = decodeRouteRefreshPayloadForRetry(envelope.payload) ?: run {
            scheduleRuntimeRouteRefreshRetry()
            return
        }
        val current = state.value.trustedRuntime ?: return
        if (!isSessionAuthenticated) return
        if (pendingAuthorization == null) {
            if (
                requiresPairedAuthorization ||
                current.relayTicketGeneration != null ||
                payload.ticketGeneration != null
            ) {
                scheduleRuntimeRouteRefreshRetry()
                return
            }
        } else {
            val binding = activeChannel?.transportSecurityContext?.bindingId
            if (
                binding != pendingAuthorization.transportBinding ||
                payload.relayId != pendingAuthorization.relayId ||
                payload.relayExpiresAtEpochMillis != pendingAuthorization.relayExpiresAtEpochMillis ||
                payload.relayNonce != pendingAuthorization.relayNonce ||
                payload.ticketGeneration != pendingAuthorization.ticketGeneration
            ) {
                scheduleRuntimeRouteRefreshRetry()
                return
            }
        }
        val trusted = trustedRuntimeFromRouteRefreshPayload(
            current = current,
            payload = payload,
            nowEpochMillis = nowMillis(),
        ) ?: run {
            scheduleRuntimeRouteRefreshRetry()
            return
        }
        viewModelScope.launch {
            if (state.value.trustedRuntime != current) return@launch
            if (
                pendingAuthorization != null &&
                activeChannel?.transportSecurityContext?.bindingId != pendingAuthorization.transportBinding
            ) {
                return@launch
            }
            didAttemptTrustedRuntimeRestore = true
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
        if (trustedRuntime.relayTicketGeneration != null) {
            val binding = channel.transportSecurityContext?.bindingId ?: return
            if (!DeviceIdentity.isCanonicalTransportBinding(binding)) return
        } else if (!dependencies.authenticatedRouteRefreshEnabled) {
            return
        }
        val now = nowMillis()
        val expiresAt = trustedRuntime.activeRemoteRouteLeaseExpiresAtEpochMillis(now) ?: return
        val delayMillis = runtimeRouteRefreshLeaseDelayMillis(
            nowEpochMillis = now,
            remoteRouteExpiresAtEpochMillis = expiresAt,
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
        val trustedRuntime = current.trustedRuntime
        if (trustedRuntime?.relayTicketGeneration != null) {
            val binding = channel.transportSecurityContext?.bindingId ?: return false
            if (!DeviceIdentity.isCanonicalTransportBinding(binding)) return false
        } else if (!dependencies.authenticatedRouteRefreshEnabled) {
            return false
        }
        val now = nowMillis()
        val delayMillis = runtimeRouteRefreshRetryDelayMillis(
            nowEpochMillis = now,
            remoteRouteExpiresAtEpochMillis = trustedRuntime
                .retryableRemoteRouteLeaseExpiresAtEpochMillis(now),
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
        if (!trustedRuntime.hasCompleteRemoteRouteMaterial()) return
        revokeAuthenticatedRuntimeSessionState()
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

    private fun clearPendingRouteRefreshRequest() {
        routeRefreshRequestTimeoutJob?.cancel()
        routeRefreshRequestTimeoutJob = null
        pendingRouteRefreshRequestId = null
        pendingRouteRefreshRequiresPairedAuthorization = false
        pendingPairedRelayAllocationAuthorization = null
    }

    private fun handleRuntimeHealth(envelope: ProtocolEnvelope) {
        envelope.payload.runtimeHealthUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "runtime.health response contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(RuntimeHealthPayload.serializer(), envelope.payload) ?: return
        if (payload.status.isPairingRequiredRuntimeCode()) {
            revokeAuthenticatedRuntimeSessionState()
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
                modelResidency = runtimeModelResidencyStatus(payload),
                error = null
            )
        }
        if (isSessionAuthenticated) {
            requestModelsInternal()
            requestRuntimeChatSessions()
            requestRuntimeMemory()
            requestRuntimeMemorySummaryDrafts()
        }
    }

    private fun handleModels(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        val pending = pendingModelsListRequest ?: return
        if (!pending.matchesCurrentModelsAuthority(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return
        envelope.payload.modelsResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "models.result response contains unsupported metadata: $unknownKey")
            clearPendingModelsListRequest()
            return
        }
        val payload = decodePayload(ModelsResultPayload.serializer(), envelope.payload) ?: run {
            clearPendingModelsListRequest()
            return
        }
        clearPendingModelsListRequest()
        modelCatalogGeneration += 1L
        modelCatalogAcceptedAuthorityGeneration = runtimeSessionAuthorityGeneration
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
                contextWindowTokens = it.contextWindowTokens?.takeIf { tokens -> tokens > 0 },
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
        if (pendingMemorySemanticDuplicateClustersRequest != null) {
            clearMemorySemanticDuplicateClusters()
        }
        val refreshedEmbeddingModelId = state.value.selectedEmbeddingModelId
        if (
            refreshedEmbeddingModelId != null &&
            !hasEligibleMemorySemanticDuplicateSuggestionsModel(
                state.value,
                refreshedEmbeddingModelId,
            )
        ) {
            clearMemorySemanticDuplicateSuggestions()
            clearMemorySemanticDuplicateClusters()
        }
        updateMemorySemanticDuplicateSuggestionsAvailability()
        updateMemorySemanticDuplicateClustersAvailability()
    }

    private fun handleModelPull(envelope: ProtocolEnvelope) {
        if (pendingModelPullRequestId != envelope.requestId) return
        envelope.payload.modelPullResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "models.pull response contains unsupported metadata: $unknownKey")
            return
        }
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
                        error = runtimeUiError("model_install_failed", payload.message),
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
                requestModelsInternal()
            }
        }
    }

    private fun handleChatSessionsList(envelope: ProtocolEnvelope) {
        val run = pendingChatSessionsListRun ?: return
        if (run.requestId != envelope.requestId || !run.hasCurrentRuntimeAuthority()) return
        run.pageCount += 1
        if (run.pageCount > MAX_RUNTIME_CHAT_SESSION_LIST_PAGES) {
            failPendingChatSessionsListRun(run, "chat.sessions.list response exceeded the 100-page budget")
            return
        }
        envelope.payload.chatSessionsListUnknownMetadataKey()?.let { unknownKey ->
            failPendingChatSessionsListRun(
                run,
                "chat.sessions.list response contains unsupported metadata: $unknownKey",
            )
            return
        }
        val payload = decodePayload(ChatSessionsListResultPayload.serializer(), envelope.payload) ?: run {
            clearPendingChatSessionsListRun(run)
            return
        }
        if (payload.sessions.size > MAX_RUNTIME_CHAT_SESSION_PAGE_SIZE) {
            failPendingChatSessionsListRun(run, "chat.sessions.list response page exceeds 200 sessions")
            return
        }
        val pageIds = payload.sessions.map(ChatSessionSummaryPayload::sessionId)
        if (pageIds.toSet().size != pageIds.size || pageIds.any(run.sessionIds::contains)) {
            failPendingChatSessionsListRun(run, "chat.sessions.list response contains duplicate session IDs")
            return
        }
        val snapshotCount = payload.snapshotCount
        if (snapshotCount == null) {
            if (runtimeChatSessionsAuthoritativeSyncSupported) {
                runtimeChatSessionsBulkAuthorityEnabled = false
                failPendingChatSessionsListRun(
                    run,
                    "chat.sessions.list response omitted snapshot_count after authoritative sync was established",
                )
                return
            }
            if (run.snapshotCount != null || run.summaries.isNotEmpty()) {
                failPendingChatSessionsListRun(run, "chat.sessions.list response snapshot_count changed between pages")
                return
            }
            run.summaries += payload.sessions
            run.sessionIds += pageIds
            completePendingChatSessionsListRun(run, capable = false)
            return
        }
        val expectedSnapshotCount = run.snapshotCount
        if (expectedSnapshotCount != null && expectedSnapshotCount != snapshotCount) {
            failPendingChatSessionsListRun(run, "chat.sessions.list response snapshot_count changed between pages")
            return
        }
        run.snapshotCount = snapshotCount
        val accumulatedCount = run.summaries.size + payload.sessions.size
        if (accumulatedCount > snapshotCount) {
            failPendingChatSessionsListRun(run, "chat.sessions.list response exceeded snapshot_count")
            return
        }
        val nextCursor = payload.nextCursor
        if (nextCursor != null) {
            if (payload.sessions.isEmpty()) {
                failPendingChatSessionsListRun(run, "chat.sessions.list response has an empty nonterminal page")
                return
            }
            if (accumulatedCount >= snapshotCount) {
                failPendingChatSessionsListRun(run, "chat.sessions.list response cursor exceeds snapshot_count")
                return
            }
            if (!run.cursors.add(nextCursor)) {
                failPendingChatSessionsListRun(run, "chat.sessions.list response repeated a cursor")
                return
            }
            run.summaries += payload.sessions
            run.sessionIds += pageIds
            requestRuntimeChatSessionsContinuation(run, nextCursor)
            return
        }
        if (accumulatedCount != snapshotCount) {
            failPendingChatSessionsListRun(run, "chat.sessions.list response final count does not match snapshot_count")
            return
        }
        run.summaries += payload.sessions
        run.sessionIds += pageIds
        completePendingChatSessionsListRun(run, capable = true)
    }

    private fun PendingChatSessionsListRun.hasCurrentRuntimeAuthority(): Boolean {
        return pendingChatSessionsListRun === this &&
            activeChannel === channel &&
            channel.isConnected &&
            activeConnectionGeneration == connectionGeneration &&
            isSessionAuthenticated &&
            runtimeSessionAuthorityGeneration == authorityGeneration
    }

    private fun clearPendingChatSessionsListRun(run: PendingChatSessionsListRun? = pendingChatSessionsListRun) {
        if (run == null) {
            if (pendingChatSessionsListRun != null) return
            pendingChatSessionsRequestId = null
            pendingChatSessionsQuery = null
            mutableState.update { it.copy(isLoadingChatSessions = false) }
            return
        }
        if (pendingChatSessionsListRun !== run) return
        closeRuntimeChatHistoryRequest(run.correlation())
        pendingChatSessionsListRun = null
        pendingChatSessionsRequestId = null
        pendingChatSessionsQuery = null
        mutableState.update { it.copy(isLoadingChatSessions = false) }
    }

    private fun failPendingChatSessionsListRun(
        run: PendingChatSessionsListRun,
        detail: String?,
    ) {
        clearPendingChatSessionsListRun(run)
        showError("invalid_payload", detail)
    }

    private fun completePendingChatSessionsListRun(
        run: PendingChatSessionsListRun,
        capable: Boolean,
    ) {
        if (!run.hasCurrentRuntimeAuthority()) return
        clearPendingChatSessionsListRun(run)
        if (capable && run.query == null) {
            runtimeChatSessionsAuthoritativeSyncSupported = true
            runtimeChatSessionsBulkAuthorityEnabled = true
        }
        publishRuntimeChatSessionsSnapshot(
            summaries = run.summaries,
            requestedQuery = run.query,
        )
    }

    private fun publishRuntimeChatSessionsSnapshot(
        summaries: List<ChatSessionSummaryPayload>,
        requestedQuery: String?,
    ) {
        if (requestedQuery != null) {
            val searchData = persistedRuntimeData.withRuntimeChatSessionSummaries(
                sessions = summaries,
                nowMillis = nowMillis(),
            )
            val resultsById = (
                runtimeChatSessions(searchData) + archivedRuntimeChatSessions(searchData)
                ).associateBy(RuntimeChatSession::id)
            val remoteResultIds = searchData.sessions
                .filter(PersistedChatSession::runtimeOwned)
                .mapTo(mutableSetOf(), PersistedChatSession::id)
            val orderedResults = summaries
                .filter { it.sessionId in remoteResultIds }
                .mapNotNull { resultsById[it.sessionId] }
                .distinctBy(RuntimeChatSession::id)
            val resultIDs = orderedResults.mapTo(mutableSetOf(), RuntimeChatSession::id)
            runtimeChatSearchSummariesById = summaries
                .filter { it.sessionId in resultIDs }
                .distinctBy(ChatSessionSummaryPayload::sessionId)
                .associateBy(ChatSessionSummaryPayload::sessionId)
            mutableState.update {
                it.copy(
                    chatSessionSearchQuery = requestedQuery,
                    chatSessionSearchResults = orderedResults,
                )
            }
            return
        }
        val syncedData = persistedRuntimeData.withRuntimeChatSessionSummaries(
            sessions = summaries,
            nowMillis = nowMillis(),
        )
        publishPersistedRuntimeData(
            syncedData,
            save = true,
            clearError = false,
        )
        clearRuntimeChatSearchAuthority()
        activeRuntimeSessionId(syncedData)?.let(::requestRuntimeChatMessages)
    }

    private fun handleChatMessagesList(envelope: ProtocolEnvelope) {
        if (pendingChatMessagesRequestId != envelope.requestId) return
        val expectedSessionId = pendingChatMessagesSessionId
        clearPendingChatMessagesRequest()
        envelope.payload.chatMessagesListUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "chat.messages.list response contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(ChatMessagesListResultPayload.serializer(), envelope.payload) ?: return
        if (expectedSessionId != null && expectedSessionId != payload.sessionId) return
        val replacementData = persistedRuntimeData.withRuntimeChatMessages(
            sessionId = payload.sessionId,
            messages = payload.messages,
            nowMillis = nowMillis(),
        )
        val pending = pendingHistoricalSourceAttributionResolve
        val replacementMessage = pending
            ?.takeIf { it.sessionId == payload.sessionId }
            ?.let { expected ->
                replacementData.sessions
                    .singleOrNull { it.id == payload.sessionId }
                    ?.messages
                    ?.singleOrNull { message ->
                        message.role == "assistant" &&
                            message.assistantMessageId == expected.assistantMessageId &&
                            message.sourceAttributions.any { attribution ->
                                attribution.sourceIndex == expected.sourceAttribution.sourceIndex &&
                                    attribution.documentName == expected.sourceAttribution.documentName &&
                                    attribution.mimeType == expected.sourceAttribution.mimeType &&
                                    attribution.chunkIndex == expected.sourceAttribution.chunkIndex
                            }
                    }
            }
        if (pending != null && replacementMessage == null) {
            clearPendingHistoricalSourceAttributionResolve()
        }
        publishPersistedRuntimeData(
            replacementData,
            save = true,
        )
        if (pending != null && replacementMessage != null) {
            pendingHistoricalSourceAttributionResolve = pending.copy(localMessageId = replacementMessage.id)
            mutableState.update {
                it.copy(
                    resolvingSourceAttributionMessageId = replacementMessage.id,
                    resolvingSourceAttributionIndex = pending.sourceAttribution.sourceIndex,
                )
            }
        }
    }

    private fun handleChatDelta(envelope: ProtocolEnvelope) {
        if (!isActiveChatEnvelope(envelope)) return
        envelope.payload.chatDeltaUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "chat.delta response contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(ChatDeltaPayload.serializer(), envelope.payload) ?: return
        val updatedState = state.value.withChatDelta(envelope, payload)
        mutableState.value = updatedState
        persistActiveMessages(updatedState.messages)
    }

    private fun handleChatDone(envelope: ProtocolEnvelope) {
        if (!isActiveChatEnvelope(envelope)) return
        envelope.payload.chatDoneUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "chat.done response contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(ChatDonePayload.serializer(), envelope.payload) ?: return
        val completedState = state.value.withChatDone(
            envelope,
            payload,
            payload.assistantMessageId,
        )
        val updatedState = if (payload.finishReason == "cancelled") {
            completedState
        } else {
            completedState.copy(error = null)
        }
        mutableState.value = updatedState
        persistActiveMessages(updatedState.messages, clearError = false)
        if (payload.finishReason != "cancelled") {
            val titleRequested = requestChatTitleIfNeeded(updatedState)
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

    private fun handleChatTitleResult(envelope: ProtocolEnvelope) {
        if (pendingTitleRequestId != envelope.requestId) return
        envelope.payload.chatTitleResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "chat.title.result response contains unsupported metadata: $unknownKey")
            return
        }
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
        )
        requestFreshRuntimeChatSessionsAfterMutationCompletion()
    }

    private fun handleChatSessionRename(envelope: ProtocolEnvelope) {
        if (envelope.requestId !in pendingChatSessionRenameRequestIds) return
        val mutation = pendingChatSessionRenameMutationsByRequestId[envelope.requestId] ?: run {
            pendingChatSessionRenameRequestIds -= envelope.requestId
            return
        }
        envelope.payload.chatSessionRenameResultUnknownMetadataKey()?.let { unknownKey ->
            pendingChatSessionRenameRequestIds -= envelope.requestId
            pendingChatSessionRenameMutationsByRequestId -= envelope.requestId
            handleRuntimeChatSessionMutationFailure(
                detail = "chat.session.rename response contains unsupported metadata: $unknownKey",
                renameMutation = mutation,
                errorCode = "invalid_payload",
            )
            return
        }
        val payload = decodePayload(ChatSessionRenamePayload.serializer(), envelope.payload) ?: run {
            val detail = state.value.error?.technicalDetail
            pendingChatSessionRenameRequestIds -= envelope.requestId
            pendingChatSessionRenameMutationsByRequestId -= envelope.requestId
            handleRuntimeChatSessionMutationFailure(
                detail = detail,
                renameMutation = mutation,
                errorCode = "invalid_payload",
            )
            return
        }
        if (payload.sessionId != mutation.sessionId) {
            pendingChatSessionRenameRequestIds -= envelope.requestId
            pendingChatSessionRenameMutationsByRequestId -= envelope.requestId
            handleRuntimeChatSessionMutationFailure(
                detail = "chat.session.rename response did not match the pending session",
                renameMutation = mutation,
                errorCode = "invalid_payload",
            )
            return
        }
        pendingChatSessionRenameRequestIds -= envelope.requestId
        pendingChatSessionRenameMutationsByRequestId -= envelope.requestId
        publishPersistedRuntimeData(
            persistedRuntimeData.withRenamedChatSession(
                sessionId = payload.sessionId,
                title = payload.title,
                nowMillis = nowMillis(),
            ),
            save = true,
        )
        requestFreshRuntimeChatSessionsAfterMutationCompletion()
    }

    private fun handleChatSessionLifecycle(envelope: ProtocolEnvelope) {
        if (pendingChatSessionsBulkLifecycle?.requestId == envelope.requestId) {
            handleChatSessionsBulkLifecycle(envelope)
            return
        }
        if (envelope.requestId !in pendingChatSessionLifecycleRequestIds) return
        val mutation = pendingChatSessionLifecycleMutationsByRequestId[envelope.requestId] ?: run {
            pendingChatSessionLifecycleRequestIds -= envelope.requestId
            return
        }
        envelope.payload.chatSessionLifecycleResultUnknownMetadataKey()?.let { unknownKey ->
            pendingChatSessionLifecycleRequestIds -= envelope.requestId
            pendingChatSessionLifecycleMutationsByRequestId -= envelope.requestId
            handleRuntimeChatSessionMutationFailure(
                detail = "${envelope.type} response contains unsupported metadata: $unknownKey",
                lifecycleMutation = mutation,
                errorCode = "invalid_payload",
            )
            return
        }
        val payload = decodePayload(ChatSessionLifecyclePayload.serializer(), envelope.payload) ?: run {
            val detail = state.value.error?.technicalDetail
            pendingChatSessionLifecycleRequestIds -= envelope.requestId
            pendingChatSessionLifecycleMutationsByRequestId -= envelope.requestId
            handleRuntimeChatSessionMutationFailure(
                detail = detail,
                lifecycleMutation = mutation,
                errorCode = "invalid_payload",
            )
            return
        }
        if (!payload.matchesPendingRuntimeChatSessionLifecycle(envelope.type, mutation)) {
            pendingChatSessionLifecycleRequestIds -= envelope.requestId
            pendingChatSessionLifecycleMutationsByRequestId -= envelope.requestId
            handleRuntimeChatSessionMutationFailure(
                detail = "${envelope.type} response did not match the pending session lifecycle operation",
                lifecycleMutation = mutation,
                errorCode = "invalid_payload",
            )
            return
        }
        pendingChatSessionLifecycleRequestIds -= envelope.requestId
        pendingChatSessionLifecycleMutationsByRequestId -= envelope.requestId
        publishPersistedRuntimeData(
            persistedRuntimeData.withRuntimeChatSessionLifecycleResult(
                result = payload,
                nowMillis = nowMillis(),
            ),
            save = true,
        )
        requestFreshRuntimeChatSessionsAfterMutationCompletion()
    }

    private fun beginRuntimeChatSessionsBulkLifecycle(
        type: String,
        scope: String,
    ): Boolean {
        if (!isSessionAuthenticated) return false
        val channel = activeChannel?.takeIf(RuntimeProtocolChannel::isConnected) ?: return false
        if (
            pendingChatSessionsListRun != null ||
            pendingChatSessionsBulkLifecycle != null ||
            pendingTitleRequestId != null ||
            pendingChatSessionLifecycleRequestIds.isNotEmpty() ||
            pendingChatSessionRenameRequestIds.isNotEmpty()
        ) {
            return false
        }
        val requestId = UUID.randomUUID().toString()
        val pending = PendingChatSessionsBulkLifecycle(
            requestId = requestId,
            type = type,
            scope = scope,
            channel = channel,
            connectionGeneration = activeConnectionGeneration,
            authorityGeneration = runtimeSessionAuthorityGeneration,
        )
        pendingChatSessionsBulkLifecycle = pending
        mutableState.update {
            it.copy(
                isBulkMutatingChatSessions = true,
                error = null,
            )
        }
        sendRuntimeChatSessionsBulkLifecycleBatch(pending)
        return true
    }

    private fun sendRuntimeChatSessionsBulkLifecycleBatch(
        pending: PendingChatSessionsBulkLifecycle,
    ) {
        if (!pending.hasCurrentRuntimeAuthority()) {
            clearPendingChatSessionsBulkLifecycle(pending)
            return
        }
        sendEnvelope(
            envelope(
                type = pending.type,
                requestId = pending.requestId,
                serializer = ChatSessionsBulkLifecyclePayload.serializer(),
                payload = ChatSessionsBulkLifecyclePayload(
                    scope = pending.scope,
                    limit = MAX_RUNTIME_CHAT_SESSIONS_BULK_BATCH_SIZE,
                ),
            )
        )
    }

    private fun handleChatSessionsBulkLifecycle(envelope: ProtocolEnvelope) {
        val pending = pendingChatSessionsBulkLifecycle ?: return
        if (
            pending.requestId != envelope.requestId ||
            envelope.type != pending.type ||
            !pending.hasCurrentRuntimeAuthority()
        ) {
            return
        }
        envelope.payload.chatSessionsBulkLifecycleResultUnknownMetadataKey()?.let { unknownKey ->
            failPendingChatSessionsBulkLifecycle(
                pending,
                "${envelope.type} bulk response contains unsupported metadata: $unknownKey",
                errorCode = "invalid_payload",
            )
            return
        }
        val payload = decodePayload(
            ChatSessionsBulkLifecycleResultPayload.serializer(),
            envelope.payload,
        ) ?: run {
            clearPendingChatSessionsBulkLifecycle(pending)
            reconcileRuntimeChatSessionsAfterBulkFailure()
            return
        }
        if (
            payload.scope != pending.scope ||
            payload.status != pending.expectedStatus() ||
            payload.affectedCount > MAX_RUNTIME_CHAT_SESSIONS_BULK_BATCH_SIZE ||
            (payload.remainingCount > 0 && payload.affectedCount == 0)
        ) {
            failPendingChatSessionsBulkLifecycle(
                pending,
                "${envelope.type} bulk response did not match the pending lifecycle operation",
                errorCode = "invalid_payload",
            )
            return
        }
        pending.batchCount += 1
        pending.cumulativeAffectedCount += payload.affectedCount
        if (pending.cumulativeAffectedCount > MAX_RUNTIME_CHAT_SESSION_BULK_AFFECTED) {
            failPendingChatSessionsBulkLifecycle(
                pending,
                "${envelope.type} bulk response exceeded the 10000-row budget",
                errorCode = "invalid_payload",
            )
            return
        }
        if (payload.remainingCount > 0) {
            if (pending.batchCount >= MAX_RUNTIME_CHAT_SESSION_BULK_BATCHES) {
                failPendingChatSessionsBulkLifecycle(
                    pending,
                    "${envelope.type} bulk response exceeded the 50-batch budget",
                    errorCode = "invalid_payload",
                )
                return
            }
            pending.requestId = UUID.randomUUID().toString()
            sendRuntimeChatSessionsBulkLifecycleBatch(pending)
            return
        }
        clearPendingChatSessionsBulkLifecycle(pending)
        applyCompletedRuntimeChatSessionsBulkLifecycle(pending)
        requestRuntimeChatSessions()
    }

    private fun PendingChatSessionsBulkLifecycle.expectedStatus(): String {
        return when (scope) {
            CHAT_SESSIONS_BULK_SCOPE_ALL_ACTIVE -> "archived"
            CHAT_SESSIONS_BULK_SCOPE_ALL_ARCHIVED -> "deleted"
            else -> ""
        }
    }

    private fun PendingChatSessionsBulkLifecycle.hasCurrentRuntimeAuthority(): Boolean {
        return pendingChatSessionsBulkLifecycle === this &&
            activeChannel === channel &&
            channel.isConnected &&
            activeConnectionGeneration == connectionGeneration &&
            isSessionAuthenticated &&
            runtimeSessionAuthorityGeneration == authorityGeneration
    }

    private fun clearPendingChatSessionsBulkLifecycle(
        pending: PendingChatSessionsBulkLifecycle? = pendingChatSessionsBulkLifecycle,
    ) {
        if (pending == null || pendingChatSessionsBulkLifecycle !== pending) return
        pendingChatSessionsBulkLifecycle = null
        mutableState.update { it.copy(isBulkMutatingChatSessions = false) }
    }

    private fun failPendingChatSessionsBulkLifecycle(
        pending: PendingChatSessionsBulkLifecycle,
        detail: String?,
        errorCode: String = "chat_session_sync_failed",
    ) {
        clearPendingChatSessionsBulkLifecycle(pending)
        showError(errorCode, detail)
        reconcileRuntimeChatSessionsAfterBulkFailure()
    }

    private fun reconcileRuntimeChatSessionsAfterBulkFailure() {
        if (isSessionAuthenticated && activeChannel?.isConnected == true) {
            requestRuntimeChatSessions()
        }
    }

    private fun applyCompletedRuntimeChatSessionsBulkLifecycle(
        pending: PendingChatSessionsBulkLifecycle,
    ) {
        when (pending.scope) {
            CHAT_SESSIONS_BULK_SCOPE_ALL_ACTIVE -> {
                persistedRuntimeData.sessions
                    .filter { it.archivedAtMillis == null }
                    .forEach { clearPendingAttachmentsForSession(it.id) }
                clearPendingAttachmentsForSession(null)
                publishPersistedRuntimeData(
                    persistedRuntimeData.withArchivedChatSessions(nowMillis()),
                    save = true,
                )
                val cleanDraft = clearComposerDraft(sessionId = null)
                mutableState.update {
                    it.copy(
                        chatInput = cleanDraft,
                        pendingAttachments = emptyList(),
                    )
                }
            }
            CHAT_SESSIONS_BULK_SCOPE_ALL_ARCHIVED -> {
                persistedRuntimeData.sessions
                    .filter { it.archivedAtMillis != null }
                    .forEach { clearPendingAttachmentsForSession(it.id) }
                clearPendingAttachmentsForSession(null)
                publishPersistedRuntimeData(
                    persistedRuntimeData.withoutArchivedChatSessions(nowMillis = nowMillis()),
                    save = true,
                )
            }
        }
        clearRuntimeChatSearchAuthority()
    }

    private fun ChatSessionLifecyclePayload.matchesPendingRuntimeChatSessionLifecycle(
        envelopeType: String,
        mutation: PendingChatSessionLifecycleMutation,
    ): Boolean {
        if (envelopeType != mutation.type || sessionId != mutation.sessionId) return false
        val cleanStatus = status?.trim()?.lowercase()
        if (cleanStatus != null && cleanStatus !in setOf("archived", "restored", "deleted")) return false
        val archiveSignal = cleanStatus == "archived" || archivedAt != null
        val restoreSignal = cleanStatus == "restored" || restoredAt != null
        val deleteSignal = cleanStatus == "deleted" || deletedAt != null
        if (listOf(archiveSignal, restoreSignal, deleteSignal).count { it } != 1) return false
        return when (mutation.type) {
            MessageType.ChatSessionArchive -> archiveSignal
            MessageType.ChatSessionRestore -> restoreSignal
            MessageType.ChatSessionDelete -> deleteSignal
            else -> false
        }
    }

    private fun handleIndexDocumentsList(envelope: ProtocolEnvelope) {
        if (pendingDocumentCatalogRequestId != envelope.requestId) return
        pendingDocumentCatalogRequestId = null
        envelope.payload.indexDocumentsListResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "index.documents.list response contains unsupported metadata: $unknownKey")
            mutableState.update { it.copy(isLoadingDocumentCatalog = false) }
            return
        }
        val payload = decodePayload(IndexDocumentsListResultPayload.serializer(), envelope.payload) ?: run {
            mutableState.update { it.copy(isLoadingDocumentCatalog = false) }
            return
        }
        mutableState.update {
            it.copy(
                documentCatalog = RuntimeDocumentCatalog(
                    documents = payload.documents.take(MAX_RUNTIME_DOCUMENT_CATALOG_ROWS).mapIndexed { index, document ->
                        document.toRuntimeDocumentIndexDocument(index)
                    },
                    summary = payload.summary.toRuntimeDocumentIndexSummary(),
                ),
                isLoadingDocumentCatalog = false,
                error = null,
            )
        }
    }

    private fun handleRetrievalQuery(envelope: ProtocolEnvelope) {
        if (pendingDocumentSearchRequestId != envelope.requestId) return
        clearPendingRuntimeDocumentSearch()
        envelope.payload.retrievalQueryResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "retrieval.query response contains unsupported metadata: $unknownKey")
            mutableState.update { it.copy(isSearchingDocuments = false) }
            return
        }
        val payload = decodePayload(RetrievalQueryResultPayload.serializer(), envelope.payload) ?: run {
            mutableState.update { it.copy(isSearchingDocuments = false) }
            return
        }
        mutableState.update {
            it.copy(
                documentSearchResults = payload.results.take(MAX_RUNTIME_DOCUMENT_SEARCH_RESULTS).mapIndexed { index, result ->
                    val startCharacterOffset = result.startCharacterOffset.coerceAtLeast(0)
                    RuntimeDocumentSearchResult(
                        document = result.document.toRuntimeDocumentIndexDocument(index),
                        chunkIndex = result.chunkIndex.coerceAtLeast(0),
                        startCharacterOffset = startCharacterOffset,
                        endCharacterOffset = result.endCharacterOffset.coerceAtLeast(startCharacterOffset),
                        rank = result.rank.coerceAtLeast(1),
                        matchKind = result.matchKind,
                        matchedTerms = result.matchedTerms.canonicalRuntimeDocumentMatchedTerms(),
                        snippet = result.snippet.boundedRuntimeDocumentSnippet(),
                        sourceAnchorId = result.sourceAnchorId.canonicalRuntimeSourceAnchorIdOrEmpty(),
                    )
                },
                isSearchingDocuments = false,
                error = null,
            )
        }
    }

    private fun handleCitationResolve(envelope: ProtocolEnvelope) {
        if (pendingCitationResolveRequestId != envelope.requestId) return
        val expectedAnchorId = pendingCitationResolveSourceAnchorId
        clearPendingCitationResolve()
        val payload = decodeTrustedSourceResponse(
            CitationResolveResultPayload.serializer(),
            envelope.payload,
        )
        if (
            payload == null ||
            expectedAnchorId == null ||
            payload.citation.sourceAnchorId != expectedAnchorId ||
            payload.trustedSource?.let {
                it.sourceAnchorId != expectedAnchorId || it.citationId != payload.citation.citationId
            } == true
        ) {
            mutableState.update { it.copy(isResolvingCitation = false) }
            showError("citation_resolve_failed")
            return
        }
        pendingSourceReview = PendingSourceReview(
            sourceAnchorId = expectedAnchorId,
            citationId = payload.citation.citationId,
            reviewId = payload.review.reviewId,
            confirmationToken = payload.review.confirmationToken,
            disclosureVersion = payload.review.disclosureVersion,
            usageScope = payload.review.usageScope,
        )
        payload.trustedSource?.let(::rememberTrustedSource)
        val chunk = payload.citation.chunkSummary
        mutableState.update {
            it.copy(
                sourceReview = RuntimeSourceReview(
                    sourceAnchorId = expectedAnchorId,
                    document = payload.citation.document.toRuntimeDocumentIndexDocument(0),
                    chunkIndex = chunk.chunkIndex,
                    startCharacterOffset = chunk.startCharacterOffset,
                    endCharacterOffset = chunk.endCharacterOffset,
                    characterCount = chunk.characterCount,
                    expiresAt = payload.review.expiresAt,
                    isTrusted = payload.trustedSource != null,
                ),
                trustedSources = payload.trustedSource?.let { trusted ->
                    it.trustedSources.upsertTrustedSource(trusted.toRuntimeTrustedSource())
                } ?: it.trustedSources,
                isResolvingCitation = false,
                error = null,
            )
        }
    }

    private fun handleHistoricalSourceAttributionResolve(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        val pending = pendingHistoricalSourceAttributionResolve ?: return
        if (envelope.requestId != pending.requestId) return
        if (
            pending.channel !== sourceChannel ||
            pending.connectionGeneration != sourceConnectionGeneration ||
            activeChannel !== sourceChannel ||
            activeConnectionGeneration != sourceConnectionGeneration
        ) {
            return
        }
        val currentMessage = state.value.messages.singleOrNull {
            it.id == pending.localMessageId &&
                it.role == "assistant" &&
                it.assistantMessageId == pending.assistantMessageId
        }
        val currentAttribution = currentMessage?.sourceAttributions?.singleOrNull {
            it.sourceIndex == pending.sourceAttribution.sourceIndex
        }
        val payload = decodeTrustedSourceResponse(
            ChatSourceAttributionResolveResultPayload.serializer(),
            envelope.payload,
        )
        if (payload == null) {
            clearPendingHistoricalSourceAttributionResolve()
            showError("source_attribution_resolve_failed")
            return
        }
        val citation = payload.citation
        val document = citation.document
        val chunk = citation.chunkSummary
        val responseMatchesSelection =
            state.value.activeChatSessionId == pending.sessionId &&
                currentAttribution == pending.sourceAttribution &&
                document.displayName == pending.sourceAttribution.documentName &&
                document.mimeType == pending.sourceAttribution.mimeType &&
                chunk.chunkIndex == pending.sourceAttribution.chunkIndex &&
                payload.trustedSource?.let {
                    it.sourceAnchorId != citation.sourceAnchorId || it.citationId != citation.citationId
                } != true
        clearPendingHistoricalSourceAttributionResolve()
        if (!responseMatchesSelection) {
            showError("source_attribution_resolve_failed")
            return
        }
        pendingSourceReview = PendingSourceReview(
            sourceAnchorId = citation.sourceAnchorId,
            citationId = citation.citationId,
            reviewId = payload.review.reviewId,
            confirmationToken = payload.review.confirmationToken,
            disclosureVersion = payload.review.disclosureVersion,
            usageScope = payload.review.usageScope,
        )
        payload.trustedSource?.let(::rememberTrustedSource)
        mutableState.update {
            it.copy(
                sourceReview = RuntimeSourceReview(
                    sourceAnchorId = citation.sourceAnchorId,
                    document = document.toRuntimeDocumentIndexDocument(0),
                    chunkIndex = chunk.chunkIndex,
                    startCharacterOffset = chunk.startCharacterOffset,
                    endCharacterOffset = chunk.endCharacterOffset,
                    characterCount = chunk.characterCount,
                    expiresAt = payload.review.expiresAt,
                    isTrusted = payload.trustedSource != null,
                ),
                trustedSources = payload.trustedSource?.let { trusted ->
                    it.trustedSources.upsertTrustedSource(trusted.toRuntimeTrustedSource())
                } ?: it.trustedSources,
                resolvingSourceAttributionMessageId = null,
                resolvingSourceAttributionIndex = null,
                error = null,
            )
        }
    }

    private fun handleTrustedSourceApprove(envelope: ProtocolEnvelope) {
        if (pendingTrustedSourceApproveRequestId != envelope.requestId) return
        pendingTrustedSourceApproveRequestId = null
        val review = pendingSourceReview
        val payload = decodeTrustedSourceResponse(TrustedSourceApproveResultPayload.serializer(), envelope.payload)
        val trustedSource = payload?.trustedSource
        if (
            review == null ||
            trustedSource == null ||
            trustedSource.sourceAnchorId != review.sourceAnchorId ||
            trustedSource.citationId != review.citationId ||
            state.value.sourceReview?.document != trustedSource.document.toRuntimeDocumentIndexDocument(0)
        ) {
            mutableState.update { it.copy(isApprovingTrustedSource = false) }
            showError("trusted_source_approve_failed")
            return
        }
        rememberTrustedSource(trustedSource)
        recordTrustedSourceMutation()
        pendingSourceReview = null
        mutableState.update {
            it.copy(
                sourceReview = it.sourceReview?.takeIf { source ->
                    source.sourceAnchorId == trustedSource.sourceAnchorId
                }?.copy(isTrusted = true),
                trustedSources = it.trustedSources.upsertTrustedSource(trustedSource.toRuntimeTrustedSource()),
                isApprovingTrustedSource = false,
                error = null,
            )
        }
    }

    private fun handleTrustedSourceDismiss(envelope: ProtocolEnvelope) {
        if (pendingTrustedSourceDismissRequestId != envelope.requestId) return
        pendingTrustedSourceDismissRequestId = null
        val review = pendingSourceReview
        val payload = decodeTrustedSourceResponse(TrustedSourceDismissResultPayload.serializer(), envelope.payload)
        if (review == null || payload == null || payload.reviewId != review.reviewId) {
            mutableState.update { it.copy(isDismissingTrustedSource = false) }
            showError("trusted_source_dismiss_failed")
            return
        }
        pendingSourceReview = null
        mutableState.update {
            it.copy(
                sourceReview = null,
                isDismissingTrustedSource = false,
                error = null,
            )
        }
    }

    private fun handleTrustedSourceList(envelope: ProtocolEnvelope) {
        if (pendingTrustedSourceListRequestId != envelope.requestId) return
        pendingTrustedSourceListRequestId = null
        val requestedMutationGeneration = pendingTrustedSourceListMutationGeneration
        pendingTrustedSourceListMutationGeneration = null
        val payload = decodeTrustedSourceResponse(TrustedSourceListResultPayload.serializer(), envelope.payload)
        if (payload == null) {
            mutableState.update { it.copy(isLoadingTrustedSources = false) }
            showError("trusted_source_list_failed")
            return
        }
        if (requestedMutationGeneration != trustedSourceMutationGeneration) {
            mutableState.update { it.copy(isLoadingTrustedSources = false) }
            return
        }
        trustedSourceGrantsBySourceAnchorId.clear()
        payload.trustedSources.forEach(::rememberTrustedSource)
        mutableState.update {
            it.copy(
                trustedSources = payload.trustedSources.map { source -> source.toRuntimeTrustedSource() },
                selectedTrustedSourceAnchorIds = it.selectedTrustedSourceAnchorIds.filter { anchorId ->
                    anchorId in trustedSourceGrantsBySourceAnchorId
                },
                sourceReview = it.sourceReview?.let { review ->
                    review.copy(isTrusted = review.sourceAnchorId in trustedSourceGrantsBySourceAnchorId)
                },
                hasLoadedTrustedSources = true,
                isLoadingTrustedSources = false,
                error = null,
            )
        }
    }

    private fun handleTrustedSourceRevoke(envelope: ProtocolEnvelope) {
        val anchorId = pendingTrustedSourceRevocationsByRequestId.remove(envelope.requestId) ?: return
        val expectedGrantId = trustedSourceGrantsBySourceAnchorId[anchorId]
        val payload = decodeTrustedSourceResponse(TrustedSourceRevokeResultPayload.serializer(), envelope.payload)
        if (payload == null || expectedGrantId == null || payload.grantId != expectedGrantId) {
            mutableState.update {
                it.copy(revokingTrustedSourceAnchorIds = it.revokingTrustedSourceAnchorIds - anchorId)
            }
            showError("trusted_source_revoke_failed")
            return
        }
        trustedSourceGrantsBySourceAnchorId.remove(anchorId)
        if (pendingSourceReview?.sourceAnchorId == anchorId) {
            pendingSourceReview = null
        }
        recordTrustedSourceMutation()
        mutableState.update {
            it.copy(
                trustedSources = it.trustedSources.filterNot { source -> source.sourceAnchorId == anchorId },
                selectedTrustedSourceAnchorIds = it.selectedTrustedSourceAnchorIds - anchorId,
                sourceReview = it.sourceReview?.takeUnless { review -> review.sourceAnchorId == anchorId },
                revokingTrustedSourceAnchorIds = it.revokingTrustedSourceAnchorIds - anchorId,
                error = null,
            )
        }
    }

    private fun handleMemoryList(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        if (
            pendingMemoryListRequestId != envelope.requestId ||
            pendingMemoryListChannel !== sourceChannel ||
            pendingMemoryListConnectionGeneration != sourceConnectionGeneration ||
            pendingMemoryListAuthorityGeneration != runtimeSessionAuthorityGeneration ||
            activeChannel !== sourceChannel ||
            activeConnectionGeneration != sourceConnectionGeneration ||
            !isSessionAuthenticated
        ) {
            return
        }
        val requestedQuery = pendingMemoryListQuery
        clearPendingMemoryListRequest()
        envelope.payload.memoryListResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "memory.list response contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(MemoryListResultPayload.serializer(), envelope.payload) ?: return
        if (requestedQuery != null) {
            val searchData = persistedRuntimeData.withRuntimeMemoryEntries(payload.entries, nowMillis())
            val resultsById = runtimeMemoryEntries(searchData).associateBy(RuntimeMemoryEntry::id)
            val orderedResults = payload.entries
                .mapNotNull { resultsById[it.id] }
                .distinctBy(RuntimeMemoryEntry::id)
            mutableState.update {
                it.copy(
                    memorySearchQuery = requestedQuery,
                    memorySearchResults = orderedResults,
                )
            }
            return
        }
        memoryCatalogGeneration += 1L
        clearMemoryDuplicateSuggestions()
        clearMemorySemanticDuplicateSuggestions()
        clearMemorySemanticDuplicateClusters()
        memoryDuplicateSuggestionsListAcceptedAuthorityGeneration = runtimeSessionAuthorityGeneration
        memorySemanticDuplicateSuggestionsListAcceptedAuthorityGeneration =
            runtimeSessionAuthorityGeneration
        memorySemanticDuplicateClustersListAcceptedAuthorityGeneration =
            runtimeSessionAuthorityGeneration
        publishPersistedRuntimeData(
            persistedRuntimeData.withRuntimeMemoryEntries(payload.entries, nowMillis()),
            save = true,
        )
        mutableState.update {
            it.copy(
                memorySearchQuery = null,
                memorySearchResults = emptyList(),
                memoryDuplicateSuggestionsAvailable =
                    memoryDuplicateSuggestionsListAcceptedAuthorityGeneration == runtimeSessionAuthorityGeneration &&
                    memoryDuplicateSuggestionsUnsupportedAuthorityGeneration != runtimeSessionAuthorityGeneration,
                memorySemanticDuplicateSuggestionsAvailable =
                    isMemorySemanticDuplicateSuggestionsAvailable(it),
                memorySemanticDuplicateClustersAvailable =
                    isMemorySemanticDuplicateClustersAvailable(it),
            )
        }
    }

    private fun handleMemoryDuplicateSuggestionsList(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        if (!isCurrentMemoryDuplicateSuggestionsRequest(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return
        closePendingMemoryDuplicateSuggestionsRequest()
        mutableState.update { it.copy(isScanningMemoryDuplicateSuggestions = false) }
        envelope.payload.memoryDuplicateSuggestionsListResultUnknownMetadataKey()?.let { unknownKey ->
            showError(
                "invalid_payload",
                "memory.duplicate_suggestions.list response contains unsupported metadata: $unknownKey",
            )
            return
        }
        val payload = decodePayload(
            MemoryDuplicateSuggestionsListResultPayload.serializer(),
            envelope.payload,
        ) ?: return
        val authoritativeEntryIds = state.value.memoryEntries.mapTo(mutableSetOf(), RuntimeMemoryEntry::id)
        val unknownEntryId = payload.groups
            .asSequence()
            .flatMap { it.entryIds.asSequence() }
            .firstOrNull { it !in authoritativeEntryIds }
        if (unknownEntryId != null) {
            showError(
                "invalid_payload",
                "memory.duplicate_suggestions.list response references unknown memory entry ID",
            )
            return
        }
        mutableState.update {
            it.copy(
                memoryDuplicateSuggestionGroups = payload.groups.map { group ->
                    RuntimeMemoryDuplicateSuggestionGroup(entryIds = group.entryIds)
                },
                memoryDuplicateSuggestionsScannedCount = payload.scannedCount,
                memoryDuplicateSuggestionsTruncated = payload.truncated,
                hasMemoryDuplicateSuggestionsResult = true,
                error = null,
            )
        }
    }

    private fun handleMemorySemanticDuplicateSuggestionsList(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        val pending = pendingMemorySemanticDuplicateSuggestionsRequest
        if (!isCurrentMemorySemanticDuplicateSuggestionsRequest(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return
        closePendingMemorySemanticDuplicateSuggestionsRequest()
        mutableState.update { it.copy(isScanningMemorySemanticDuplicateSuggestions = false) }
        envelope.payload.memorySemanticDuplicateSuggestionsListResultUnknownMetadataKey()?.let {
            unknownKey ->
            showError(
                "invalid_payload",
                "memory.semantic_duplicate_suggestions.list response contains unsupported metadata: $unknownKey",
            )
            return
        }
        val payload = decodePayload(
            MemorySemanticDuplicateSuggestionsListResultPayload.serializer(),
            envelope.payload,
        ) ?: return
        val minimumSimilarityBasisPoints = pending?.minimumSimilarityBasisPoints ?: return
        if (payload.pairs.any { it.similarityBasisPoints < minimumSimilarityBasisPoints }) {
            showError(
                "invalid_payload",
                "memory.semantic_duplicate_suggestions.list response score is below the requested threshold",
            )
            return
        }
        val authoritativeEntryIds = state.value.memoryEntries.mapTo(mutableSetOf(), RuntimeMemoryEntry::id)
        if (payload.pairs.any { pair -> pair.entryIds.any { it !in authoritativeEntryIds } }) {
            showError(
                "invalid_payload",
                "memory.semantic_duplicate_suggestions.list response references unknown memory entry ID",
            )
            return
        }
        mutableState.update {
            it.copy(
                memorySemanticDuplicateSuggestionPairs = payload.pairs.map { pair ->
                    RuntimeMemorySemanticDuplicateSuggestionPair(
                        entryIds = pair.entryIds,
                        similarityBasisPoints = pair.similarityBasisPoints,
                    )
                },
                memorySemanticDuplicateSuggestionsScannedCount = payload.scannedCount,
                memorySemanticDuplicateSuggestionsOmittedCount = payload.omittedCount,
                memorySemanticDuplicateSuggestionsTruncated = payload.truncated,
                memorySemanticDuplicateSuggestionsThresholdBasisPoints =
                    minimumSimilarityBasisPoints,
                hasMemorySemanticDuplicateSuggestionsResult = true,
                error = null,
            )
        }
    }

    private fun handleMemorySemanticDuplicateClustersList(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        val pending = pendingMemorySemanticDuplicateClustersRequest
        if (!isCurrentMemorySemanticDuplicateClustersRequest(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return
        closePendingMemorySemanticDuplicateClustersRequest()
        mutableState.update { it.copy(isScanningMemorySemanticDuplicateClusters = false) }
        envelope.payload.memorySemanticDuplicateClustersListResultUnknownMetadataKey()?.let { unknownKey ->
            showError(
                "invalid_payload",
                "memory.semantic_duplicate_clusters.list response contains unsupported metadata: $unknownKey",
            )
            return
        }
        val payload = decodePayload(
            MemorySemanticDuplicateClustersListResultPayload.serializer(),
            envelope.payload,
        ) ?: return
        val minimumSimilarityBasisPoints = pending?.minimumSimilarityBasisPoints ?: return
        if (payload.clusters.any { it.minimumSimilarityBasisPoints < minimumSimilarityBasisPoints }) {
            showError(
                "invalid_payload",
                "memory.semantic_duplicate_clusters.list response score is below the requested threshold",
            )
            return
        }
        val authoritativeEntriesById = state.value.memoryEntries.associateBy(RuntimeMemoryEntry::id)
        if (payload.clusters.any { cluster -> cluster.entryIds.any { it !in authoritativeEntriesById } }) {
            showError(
                "invalid_payload",
                "memory.semantic_duplicate_clusters.list response references unknown memory entry ID",
            )
            return
        }
        val hasByteIdenticalContents = payload.clusters.any { cluster ->
            val encodedContents = mutableListOf<ByteArray>()
            cluster.entryIds.any { entryId ->
                val content = authoritativeEntriesById.getValue(entryId).content.toByteArray(Charsets.UTF_8)
                val duplicate = encodedContents.any { existing -> existing.contentEquals(content) }
                encodedContents += content
                duplicate
            }
        }
        if (hasByteIdenticalContents) {
            showError(
                "invalid_payload",
                "memory.semantic_duplicate_clusters.list response contains byte-identical memory contents",
            )
            return
        }
        mutableState.update {
            it.copy(
                memorySemanticDuplicateClusters = payload.clusters.map { cluster ->
                    RuntimeMemorySemanticDuplicateCluster(
                        entryIds = cluster.entryIds,
                        minimumSimilarityBasisPoints = cluster.minimumSimilarityBasisPoints,
                    )
                },
                memorySemanticDuplicateClustersScannedCount = payload.scannedCount,
                memorySemanticDuplicateClustersOmittedCount = payload.omittedCount,
                memorySemanticDuplicateClustersTruncated = payload.truncated,
                memorySemanticDuplicateClustersThresholdBasisPoints = minimumSimilarityBasisPoints,
                hasMemorySemanticDuplicateClustersResult = true,
                error = null,
            )
        }
    }

    private fun handleMemorySummaryDraftsList(envelope: ProtocolEnvelope) {
        if (pendingMemorySummaryDraftsRequestId == envelope.requestId) {
            pendingMemorySummaryDraftsRequestId = null
        }
        envelope.payload.memorySummaryDraftsListResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "memory.summary.drafts.list response contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(MemorySummaryDraftsListResultPayload.serializer(), envelope.payload) ?: return
        mutableState.update {
            it.copy(
                memorySummaryDrafts = runtimeMemorySummaryDrafts(payload.drafts),
                error = null,
            )
        }
    }

    private fun handleMemorySummaryDraftGenerate(envelope: ProtocolEnvelope) {
        val pending = pendingMemorySummaryDraftGenerationsByRequestId.remove(envelope.requestId)
            ?: return
        val pendingDraftId = pending.draft.id
        mutableState.update { current ->
            current.copy(
                generatingMemorySummaryDraftIds = current.generatingMemorySummaryDraftIds - pendingDraftId,
            )
        }
        envelope.payload.memorySummaryDraftGenerateResultUnknownMetadataKey()?.let { unknownKey ->
            showError(
                "invalid_payload",
                "memory.summary.draft.generate response contains unsupported metadata: $unknownKey",
            )
            return
        }
        val payload = decodePayload(
            MemorySummaryDraftGenerateResultPayload.serializer(),
            envelope.payload,
        ) ?: return
        val generatedDraft = runtimeMemorySummaryDrafts(listOf(payload.draft)).singleOrNull()
        val currentDraft = state.value.memorySummaryDrafts.firstOrNull { it.id == pendingDraftId }
        val matchesPendingSource = generatedDraft != null &&
            generatedDraft.hasSameMemorySummarySourceAs(pending.draft) &&
            currentDraft?.hasSameMemorySummarySourceAs(pending.draft) == true
        val hasValidGenerationMetadata = generatedDraft?.summaryMethod == "llm_summary_v1" &&
            generatedDraft.generatedAtMillis != null &&
            generatedDraft.generatedModelId == pending.modelId
        if (!matchesPendingSource || !hasValidGenerationMetadata) {
            showError(
                "invalid_payload",
                "memory.summary.draft.generate response does not match the pending draft source and model",
            )
            requestRuntimeMemorySummaryDrafts()
            return
        }
        val acceptedGeneratedDraft = generatedDraft
        mutableState.update { current ->
            current.copy(
                memorySummaryDrafts = current.memorySummaryDrafts.map { draft ->
                    if (draft.id == pendingDraftId) acceptedGeneratedDraft else draft
                },
                error = null,
            )
        }
    }

    private fun handleMemorySummaryDraftApprove(envelope: ProtocolEnvelope) {
        val pendingDraftId = pendingMemorySummaryDraftApprovalDraftIdsByRequestId[envelope.requestId] ?: return
        envelope.payload.memorySummaryDraftApproveResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "memory.summary.draft.approve response contains unsupported metadata: $unknownKey")
            return
        }
        pendingMemorySummaryDraftApprovalDraftIdsByRequestId.remove(envelope.requestId)
        val payload = decodePayload(MemorySummaryDraftApproveResultPayload.serializer(), envelope.payload) ?: run {
            mutableState.update {
                it.copy(approvingMemorySummaryDraftIds = it.approvingMemorySummaryDraftIds - pendingDraftId)
            }
            return
        }
        val approvedDraftId = payload.draftId.trim().ifBlank { pendingDraftId }
        val draftIdsToClear = setOfNotNull(pendingDraftId, approvedDraftId)
        clearMemoryDuplicateSuggestions()
        clearMemorySemanticDuplicateSuggestions()
        clearMemorySemanticDuplicateClusters()
        publishPersistedRuntimeData(
            persistedRuntimeData.withRuntimeMemoryEntry(payload.entry, nowMillis()),
            save = true,
        )
        mutableState.update {
            it.copy(
                memorySummaryDrafts = it.memorySummaryDrafts.filterNot { draft -> draft.id in draftIdsToClear },
                approvingMemorySummaryDraftIds = it.approvingMemorySummaryDraftIds - draftIdsToClear,
                error = null,
            )
        }
    }

    private fun handleMemorySummaryDraftDismiss(envelope: ProtocolEnvelope) {
        val pendingDraftId = pendingMemorySummaryDraftDismissalDraftIdsByRequestId[envelope.requestId] ?: return
        envelope.payload.memorySummaryDraftDismissResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "memory.summary.draft.dismiss response contains unsupported metadata: $unknownKey")
            return
        }
        pendingMemorySummaryDraftDismissalDraftIdsByRequestId.remove(envelope.requestId)
        val payload = decodePayload(MemorySummaryDraftDismissResultPayload.serializer(), envelope.payload) ?: run {
            mutableState.update {
                it.copy(dismissingMemorySummaryDraftIds = it.dismissingMemorySummaryDraftIds - pendingDraftId)
            }
            return
        }
        val dismissedDraftId = payload.draftId.trim().ifBlank { pendingDraftId }
        val draftIdsToClear = setOfNotNull(pendingDraftId, dismissedDraftId)
        mutableState.update {
            it.copy(
                memorySummaryDrafts = it.memorySummaryDrafts.filterNot { draft -> draft.id in draftIdsToClear },
                dismissingMemorySummaryDraftIds = it.dismissingMemorySummaryDraftIds - draftIdsToClear,
                error = null,
            )
        }
    }

    private fun handleMemoryUpsert(envelope: ProtocolEnvelope) {
        clearMemoryDuplicateSuggestions()
        clearMemorySemanticDuplicateSuggestions()
        clearMemorySemanticDuplicateClusters()
        envelope.payload.memoryUpsertResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "memory.upsert response contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(MemoryUpsertResultPayload.serializer(), envelope.payload) ?: return
        publishPersistedRuntimeData(
            persistedRuntimeData.withRuntimeMemoryEntry(payload.entry, nowMillis()),
            save = true,
        )
    }

    private fun handleMemoryDelete(envelope: ProtocolEnvelope) {
        clearMemoryDuplicateSuggestions()
        clearMemorySemanticDuplicateSuggestions()
        clearMemorySemanticDuplicateClusters()
        envelope.payload.memoryDeleteResultUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "memory.delete response contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(MemoryDeleteResultPayload.serializer(), envelope.payload) ?: return
        publishPersistedRuntimeData(
            persistedRuntimeData.withoutRuntimeMemoryEntry(payload.id),
            save = true,
        )
    }

    private fun handleCancelAck(envelope: ProtocolEnvelope) {
        val activeRequestId = state.value.activeRequestId ?: return
        if (envelope.payload.isEmpty()) return
        envelope.payload.chatCancelAckUnknownMetadataKey()?.let { unknownKey ->
            showError("invalid_payload", "chat.cancel acknowledgement contains unsupported metadata: $unknownKey")
            return
        }
        val payload = decodePayload(ChatCancelPayload.serializer(), envelope.payload) ?: return
        val updatedState = state.value.withChatCancelAck(envelope, payload)
        mutableState.value = updatedState
        persistActiveMessages(updatedState.messages, clearError = false)
    }

    private fun handleError(
        envelope: ProtocolEnvelope,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ) {
        if (envelope.requestId in closedRuntimeAuthenticationRequestIds) return
        pendingRuntimeAuthentication
            ?.takeIf { pending ->
                pending.matchesActiveConnection(sourceChannel, sourceConnectionGeneration) &&
                    (pending.helloRequestId == envelope.requestId ||
                        pending.challengeRequestId == envelope.requestId)
            }
            ?.let { pending ->
                envelope.payload.errorPayloadUnknownMetadataKey()?.let { unknownKey ->
                    failRuntimeAuthentication(
                        pending = pending,
                        errorCode = "invalid_payload",
                        detail = "error response contains unsupported metadata: $unknownKey",
                        retry = pending.forcePairedClaim != null,
                    )
                    return
                }
                val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
                failRuntimeAuthentication(
                    pending = pending,
                    errorCode = if (payload == null) null else "authentication_failed",
                    detail = payload?.message,
                    retry = payload?.retryable == true,
                )
                return
            }
        pendingModelsListRequest
            ?.takeIf { pending ->
                pending.matchesCurrentModelsAuthority(
                    requestId = envelope.requestId,
                    sourceChannel = sourceChannel,
                    sourceConnectionGeneration = sourceConnectionGeneration,
                )
            }
            ?.let {
                envelope.payload.errorPayloadUnknownMetadataKey()?.let { unknownKey ->
                    clearPendingModelsListRequest()
                    showError(
                        "invalid_payload",
                        "error response contains unsupported metadata: $unknownKey",
                    )
                    return
                }
                val payload = decodePayload(ErrorPayload.serializer(), envelope.payload) ?: run {
                    clearPendingModelsListRequest()
                    return
                }
                clearPendingModelsListRequest()
                if (payload.code.isPairingRequiredRuntimeCode()) {
                    revokeAuthenticatedRuntimeSessionState()
                }
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
        if (envelope.requestId.startsWith(MODELS_LIST_REQUEST_ID_PREFIX)) return
        if (shouldIgnoreClosedMemoryDuplicateSuggestionsError(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return
        if (shouldIgnoreClosedMemorySemanticDuplicateSuggestionsError(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return
        if (shouldIgnoreClosedMemorySemanticDuplicateClustersError(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return
        if (
            shouldIgnoreStaleRuntimeChatHistoryError(
                envelope.requestId,
                sourceChannel,
                sourceConnectionGeneration,
            )
        ) {
            return
        }
        val pendingRevocationAnchorId = pendingTrustedSourceRevocationsByRequestId[envelope.requestId]
        val isPendingTrustedSourceRequest = envelope.requestId == pendingCitationResolveRequestId ||
            envelope.requestId == pendingHistoricalSourceAttributionResolve?.requestId ||
            envelope.requestId == pendingTrustedSourceApproveRequestId ||
            envelope.requestId == pendingTrustedSourceDismissRequestId ||
            envelope.requestId == pendingTrustedSourceListRequestId ||
            pendingRevocationAnchorId != null
        val trustedSourceErrorPayload = if (isPendingTrustedSourceRequest) {
            envelope.payload.errorPayloadUnknownMetadataKey()?.let { unknownKey ->
                clearTrustedSourceSessionState()
                showError("invalid_payload", "error response contains unsupported metadata: $unknownKey")
                return
            }
            decodePayload(ErrorPayload.serializer(), envelope.payload) ?: run {
                clearTrustedSourceSessionState()
                return
            }
        } else {
            null
        }
        if (trustedSourceErrorPayload?.code.isPairingRequiredRuntimeCode()) {
            revokeAuthenticatedRuntimeSessionState()
            mutableState.value = state.value.withRuntimeError(
                envelope,
                trustedSourceErrorPayload,
                pendingModelPullRequestId,
            )
            return
        }
        when (envelope.requestId) {
            pendingHistoricalSourceAttributionResolve?.requestId -> {
                clearPendingHistoricalSourceAttributionResolve()
                showError("source_attribution_resolve_failed", trustedSourceErrorPayload?.message)
                return
            }
            pendingCitationResolveRequestId -> {
                clearPendingCitationResolve()
                mutableState.update { it.copy(isResolvingCitation = false) }
                showError(
                    if (trustedSourceErrorPayload?.code == "citation_not_found") {
                        "citation_not_found"
                    } else {
                        "citation_resolve_failed"
                    }
                )
                return
            }
            pendingTrustedSourceApproveRequestId -> {
                pendingTrustedSourceApproveRequestId = null
                val terminalReview = trustedSourceErrorPayload?.code in TERMINAL_TRUSTED_SOURCE_REVIEW_ERROR_CODES
                if (terminalReview) pendingSourceReview = null
                mutableState.update {
                    it.copy(
                        sourceReview = if (terminalReview) null else it.sourceReview,
                        isApprovingTrustedSource = false,
                    )
                }
                showError(
                    if (terminalReview) requireNotNull(trustedSourceErrorPayload).code
                    else "trusted_source_approve_failed"
                )
                return
            }
            pendingTrustedSourceDismissRequestId -> {
                pendingTrustedSourceDismissRequestId = null
                val terminalReview = trustedSourceErrorPayload?.code in TERMINAL_TRUSTED_SOURCE_REVIEW_ERROR_CODES
                if (terminalReview) pendingSourceReview = null
                mutableState.update {
                    it.copy(
                        sourceReview = if (terminalReview) null else it.sourceReview,
                        isDismissingTrustedSource = false,
                    )
                }
                showError(
                    if (terminalReview) requireNotNull(trustedSourceErrorPayload).code
                    else "trusted_source_dismiss_failed"
                )
                return
            }
            pendingTrustedSourceListRequestId -> {
                pendingTrustedSourceListRequestId = null
                if (trustedSourceErrorPayload?.code == "trusted_source_not_found") {
                    trustedSourceGrantsBySourceAnchorId.clear()
                    recordTrustedSourceMutation()
                    mutableState.update {
                        it.copy(
                            trustedSources = emptyList(),
                            selectedTrustedSourceAnchorIds = emptyList(),
                            hasLoadedTrustedSources = false,
                            isLoadingTrustedSources = false,
                        )
                    }
                    showError("trusted_source_not_found")
                } else {
                    mutableState.update { it.copy(isLoadingTrustedSources = false) }
                    showError("trusted_source_list_failed")
                }
                return
            }
        }
        pendingTrustedSourceRevocationsByRequestId.remove(envelope.requestId)?.let { anchorId ->
            mutableState.update {
                it.copy(revokingTrustedSourceAnchorIds = it.revokingTrustedSourceAnchorIds - anchorId)
            }
            if (trustedSourceErrorPayload?.code == "trusted_source_not_found") {
                trustedSourceGrantsBySourceAnchorId.remove(anchorId)
                if (pendingSourceReview?.sourceAnchorId == anchorId) {
                    pendingSourceReview = null
                }
                recordTrustedSourceMutation()
                mutableState.update {
                    it.copy(
                        trustedSources = it.trustedSources.filterNot { source ->
                            source.sourceAnchorId == anchorId
                        },
                        selectedTrustedSourceAnchorIds = it.selectedTrustedSourceAnchorIds - anchorId,
                        sourceReview = it.sourceReview?.takeUnless { review ->
                            review.sourceAnchorId == anchorId
                        },
                    )
                }
                showError("trusted_source_not_found")
            } else {
                showError("trusted_source_revoke_failed")
            }
            return
        }
        if (envelope.requestId.isTrustedSourceRequestId()) return
        if (pendingDocumentSearchRequestId == envelope.requestId) {
            envelope.payload.errorPayloadUnknownMetadataKey()?.let { unknownKey ->
                clearPendingRuntimeDocumentSearch()
                mutableState.update { it.copy(isSearchingDocuments = false) }
                showError("invalid_payload", "error response contains unsupported metadata: $unknownKey")
                return
            }
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            val originalPayload = pendingDocumentSearchPayload
            val shouldRetryWithoutEmbedding = payload?.code == "invalid_payload" &&
                pendingDocumentSearchCanRetryWithoutEmbedding &&
                originalPayload?.embeddingModelId != null &&
                payload.message.trim() == LEGACY_RETRIEVAL_EMBEDDING_UNSUPPORTED_MESSAGE
            clearPendingRuntimeDocumentSearch()
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            if (shouldRetryWithoutEmbedding) {
                requestRuntimeDocumentSearch(
                    payload = requireNotNull(originalPayload).copy(embeddingModelId = null),
                    canRetryWithoutEmbedding = false,
                )
                return
            }
            mutableState.update { it.copy(isSearchingDocuments = false) }
            showError("document_search_failed", payload?.message)
            return
        }
        if (envelope.requestId.startsWith(DOCUMENT_SEARCH_REQUEST_ID_PREFIX)) return
        envelope.payload.errorPayloadUnknownMetadataKey()?.let { unknownKey ->
            val detail = "error response contains unsupported metadata: $unknownKey"
            if (isCurrentMemoryDuplicateSuggestionsRequest(
                    requestId = envelope.requestId,
                    sourceChannel = sourceChannel,
                    sourceConnectionGeneration = sourceConnectionGeneration,
                )
            ) {
                closePendingMemoryDuplicateSuggestionsRequest()
                mutableState.update { state ->
                    state.copy(isScanningMemoryDuplicateSuggestions = false)
                }
                showError("invalid_payload", detail)
                return
            }
            if (isCurrentMemorySemanticDuplicateClustersRequest(
                    requestId = envelope.requestId,
                    sourceChannel = sourceChannel,
                    sourceConnectionGeneration = sourceConnectionGeneration,
                )
            ) {
                closePendingMemorySemanticDuplicateClustersRequest()
                mutableState.update { state ->
                    state.copy(isScanningMemorySemanticDuplicateClusters = false)
                }
                showError("invalid_payload", detail)
                return
            }
            pendingChatSessionsBulkLifecycle
                ?.takeIf { it.requestId == envelope.requestId }
                ?.let { pending ->
                    failPendingChatSessionsBulkLifecycle(pending, detail, errorCode = "invalid_payload")
                    return
                }
            pendingChatSessionsListRun
                ?.takeIf { it.requestId == envelope.requestId }
                ?.let { run ->
                    failPendingChatSessionsListRun(run, detail)
                    return
                }
            if (pendingChatMessagesRequestId == envelope.requestId) {
                clearPendingChatMessagesRequest()
                showError("invalid_payload", detail)
                return
            }
            showError("invalid_payload", detail)
            return
        }
        pendingChatSessionsBulkLifecycle
            ?.takeIf { it.requestId == envelope.requestId }
            ?.let { pending ->
                val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
                if (payload?.code.isPairingRequiredRuntimeCode()) {
                    revokeAuthenticatedRuntimeSessionState()
                    mutableState.value = state.value.withRuntimeError(
                        envelope,
                        payload,
                        pendingModelPullRequestId,
                    )
                } else {
                    failPendingChatSessionsBulkLifecycle(pending, payload?.message)
                }
                return
            }
        if (pendingChatSessionLifecycleRequestIds.remove(envelope.requestId)) {
            val mutation = pendingChatSessionLifecycleMutationsByRequestId.remove(envelope.requestId)
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            val authenticationLost = payload?.code.isPairingRequiredRuntimeCode()
            if (authenticationLost) {
                revokeAuthenticatedRuntimeSessionState(listOfNotNull(mutation))
            }
            handleRuntimeChatSessionMutationFailure(
                detail = payload?.message,
                lifecycleMutation = mutation.takeUnless { authenticationLost },
            )
            if (authenticationLost) {
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
            }
            return
        }
        if (pendingChatSessionRenameRequestIds.remove(envelope.requestId)) {
            val mutation = pendingChatSessionRenameMutationsByRequestId.remove(envelope.requestId)
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            val authenticationLost = payload?.code.isPairingRequiredRuntimeCode()
            if (authenticationLost) {
                revokeAuthenticatedRuntimeSessionState(listOfNotNull(mutation))
            }
            handleRuntimeChatSessionMutationFailure(
                detail = payload?.message,
                renameMutation = mutation.takeUnless { authenticationLost },
            )
            if (authenticationLost) {
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
            }
            return
        }
        if (pendingTitleRequestId == envelope.requestId) {
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            clearPendingTitleRequest()
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
            }
            return
        }
        if (pendingChatSessionsRequestId == envelope.requestId) {
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            clearPendingChatSessionsListRun()
            showError("chat_history_load_failed", payload?.message)
            return
        }
        if (pendingChatMessagesRequestId == envelope.requestId) {
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            clearPendingChatMessagesRequest()
            showError("chat_history_load_failed", payload?.message)
            return
        }
        if (isCurrentMemoryListRequest(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) {
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            val retryQuery = pendingMemoryListQuery
            val unsupportedEmbeddingHint = payload?.code == "invalid_payload" &&
                pendingMemoryListEmbeddingModelId != null &&
                payload.message.orEmpty().contains("embedding_model_id")
            clearPendingMemoryListRequest()
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            if (unsupportedEmbeddingHint && retryQuery != null) {
                requestRuntimeMemory(retryQuery, allowEmbeddingModel = false)
                return
            }
            showError("memory_load_failed", payload?.message)
            return
        }
        if (isCurrentMemoryDuplicateSuggestionsRequest(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) {
            envelope.payload.errorPayloadUnknownMetadataKey()?.let { unknownKey ->
                closePendingMemoryDuplicateSuggestionsRequest()
                mutableState.update { state ->
                    state.copy(isScanningMemoryDuplicateSuggestions = false)
                }
                showError(
                    "invalid_payload",
                    "error response contains unsupported metadata: $unknownKey",
                )
                return
            }
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            closePendingMemoryDuplicateSuggestionsRequest()
            mutableState.update { state ->
                state.copy(isScanningMemoryDuplicateSuggestions = false)
            }
            if (payload?.code in MEMORY_DUPLICATE_SUGGESTIONS_UNSUPPORTED_ERROR_CODES) {
                memoryDuplicateSuggestionsUnsupportedAuthorityGeneration =
                    runtimeSessionAuthorityGeneration
                mutableState.update { state ->
                    state.copy(
                        memoryDuplicateSuggestionGroups = emptyList(),
                        memoryDuplicateSuggestionsScannedCount = 0,
                        memoryDuplicateSuggestionsTruncated = false,
                        hasMemoryDuplicateSuggestionsResult = false,
                        memoryDuplicateSuggestionsAvailable = false,
                    )
                }
                return
            }
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            showError("memory_load_failed", payload?.message)
            return
        }
        if (isCurrentMemorySemanticDuplicateSuggestionsRequest(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) {
            envelope.payload.errorPayloadUnknownMetadataKey()?.let { unknownKey ->
                closePendingMemorySemanticDuplicateSuggestionsRequest()
                mutableState.update { state ->
                    state.copy(isScanningMemorySemanticDuplicateSuggestions = false)
                }
                showError(
                    "invalid_payload",
                    "error response contains unsupported metadata: $unknownKey",
                )
                return
            }
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            closePendingMemorySemanticDuplicateSuggestionsRequest()
            mutableState.update { state ->
                state.copy(isScanningMemorySemanticDuplicateSuggestions = false)
            }
            if (payload?.code in MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_UNSUPPORTED_ERROR_CODES) {
                memorySemanticDuplicateSuggestionsUnsupportedAuthorityGeneration =
                    runtimeSessionAuthorityGeneration
                clearMemorySemanticDuplicateSuggestions()
                mutableState.update { state ->
                    state.copy(memorySemanticDuplicateSuggestionsAvailable = false)
                }
                return
            }
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            showError("memory_load_failed", payload?.message)
            return
        }
        if (isCurrentMemorySemanticDuplicateClustersRequest(
                requestId = envelope.requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) {
            envelope.payload.errorPayloadUnknownMetadataKey()?.let { unknownKey ->
                closePendingMemorySemanticDuplicateClustersRequest()
                mutableState.update { state ->
                    state.copy(isScanningMemorySemanticDuplicateClusters = false)
                }
                showError(
                    "invalid_payload",
                    "error response contains unsupported metadata: $unknownKey",
                )
                return
            }
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload) ?: run {
                closePendingMemorySemanticDuplicateClustersRequest()
                mutableState.update { state ->
                    state.copy(isScanningMemorySemanticDuplicateClusters = false)
                }
                return
            }
            closePendingMemorySemanticDuplicateClustersRequest()
            mutableState.update { state ->
                state.copy(isScanningMemorySemanticDuplicateClusters = false)
            }
            if (payload.code in MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_UNSUPPORTED_ERROR_CODES) {
                memorySemanticDuplicateClustersUnsupportedAuthorityGeneration =
                    runtimeSessionAuthorityGeneration
                clearMemorySemanticDuplicateClusters()
                mutableState.update { state ->
                    state.copy(memorySemanticDuplicateClustersAvailable = false)
                }
                return
            }
            if (payload.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            showError("memory_load_failed", payload.message)
            return
        }
        if (pendingMemorySummaryDraftsRequestId == envelope.requestId) {
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            pendingMemorySummaryDraftsRequestId = null
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            showError("memory_summary_drafts_load_failed", payload?.message)
            return
        }
        if (pendingDocumentCatalogRequestId == envelope.requestId) {
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            pendingDocumentCatalogRequestId = null
            mutableState.update { it.copy(isLoadingDocumentCatalog = false) }
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            showError("document_catalog_load_failed", payload?.message)
            return
        }
        pendingMemorySummaryDraftGenerationsByRequestId.remove(envelope.requestId)?.let { pending ->
            val draftId = pending.draft.id
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            mutableState.update {
                it.copy(
                    generatingMemorySummaryDraftIds = it.generatingMemorySummaryDraftIds - draftId,
                )
            }
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            showError("memory_summary_draft_generation_failed", payload?.message)
            if (payload?.code == "memory_summary_draft_stale") {
                requestRuntimeMemorySummaryDrafts()
            }
            return
        }
        pendingMemorySummaryDraftApprovalDraftIdsByRequestId.remove(envelope.requestId)?.let { draftId ->
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            mutableState.update {
                it.copy(approvingMemorySummaryDraftIds = it.approvingMemorySummaryDraftIds - draftId)
            }
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            showError("memory_summary_draft_approval_failed", payload?.message)
            return
        }
        pendingMemorySummaryDraftDismissalDraftIdsByRequestId.remove(envelope.requestId)?.let { draftId ->
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            mutableState.update {
                it.copy(dismissingMemorySummaryDraftIds = it.dismissingMemorySummaryDraftIds - draftId)
            }
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload,
                    pendingModelPullRequestId,
                )
                return
            }
            showError("memory_summary_draft_dismiss_failed", payload?.message)
            return
        }
        if (pendingRouteRefreshRequestId == envelope.requestId) {
            val payload = decodePayload(ErrorPayload.serializer(), envelope.payload)
            clearPendingRouteRefreshRequest()
            if (payload?.code.isPairingRequiredRuntimeCode()) {
                revokeAuthenticatedRuntimeSessionState()
                mutableState.value = state.value.withRuntimeError(
                    envelope,
                    payload?.withoutRouteRefreshSensitiveDetail(),
                    pendingModelPullRequestId,
                )
            } else if (payload?.retryable == false) {
                cancelRuntimeRouteRefreshLease()
                mutableState.update {
                    it.copy(error = RuntimeUiError("remote_routes_unavailable"))
                }
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
            revokeAuthenticatedRuntimeSessionState()
        }
        val updatedState = state.value.withRuntimeError(envelope, payload, pendingModelPullRequestId)
        mutableState.value = updatedState
        if (isActiveChatError) {
            if (payload?.code == "trusted_source_not_found") {
                trustedSourceGrantsBySourceAnchorId.clear()
                recordTrustedSourceMutation()
                mutableState.update {
                    it.copy(
                        trustedSources = emptyList(),
                        selectedTrustedSourceAnchorIds = emptyList(),
                        hasLoadedTrustedSources = false,
                    )
                }
            }
            persistActiveMessages(updatedState.messages, clearError = false)
        }
        if (isModelPullError) {
            pendingModelPullRequestId = null
        }
    }

    private fun sendEnvelope(envelope: ProtocolEnvelope) {
        val channelAtDispatch = activeChannel
        val connectionGenerationAtDispatch = activeConnectionGeneration
        val runtimeSessionAuthorityGenerationAtDispatch = runtimeSessionAuthorityGeneration
            .takeIf { isSessionAuthenticated }
        viewModelScope.launch {
            sendEnvelopeInternal(
                envelope = envelope,
                channelAtDispatch = channelAtDispatch,
                expectedConnectionGeneration = connectionGenerationAtDispatch,
                expectedRuntimeSessionAuthorityGeneration = runtimeSessionAuthorityGenerationAtDispatch,
            )
        }
    }

    private fun handleRuntimeChatSessionMutationFailure(
        detail: String?,
        lifecycleMutation: PendingChatSessionLifecycleMutation? = null,
        renameMutation: PendingChatSessionRenameMutation? = null,
        errorCode: String = "chat_session_sync_failed",
    ) {
        val repairedData = persistedRuntimeData.revertingRuntimeChatSessionMutations(
            listOfNotNull(lifecycleMutation, renameMutation),
        )
        if (repairedData != persistedRuntimeData) {
            publishPersistedRuntimeData(
                repairedData,
                save = true,
                clearError = false,
            )
        }
        showError(errorCode, detail)
        requestFreshRuntimeChatSessionsAfterMutationCompletion()
    }

    private fun requestFreshRuntimeChatSessionsAfterMutationCompletion() {
        clearPendingChatSessionsListRun()
        clearRuntimeChatSearchAuthority()
        requestRuntimeChatSessions()
    }

    private suspend fun sendEnvelopeInternal(
        envelope: ProtocolEnvelope,
        channelAtDispatch: RuntimeProtocolChannel?,
        expectedConnectionGeneration: Long? = null,
        expectedRuntimeSessionAuthorityGeneration: Long? = null,
    ): Boolean {
        val result = runCatching {
            Log.d(TAG, "Sending ${envelope.type} request_id=${envelope.requestId}")
            val channel = requireNotNull(channelAtDispatch) { "Runtime transport is not connected" }
            check(activeChannel === channel) { "Runtime transport changed before send" }
            if (expectedConnectionGeneration != null) {
                check(activeConnectionGeneration == expectedConnectionGeneration) {
                    "Runtime connection changed before send"
                }
            }
            if (expectedRuntimeSessionAuthorityGeneration != null) {
                check(runtimeSessionAuthorityGeneration == expectedRuntimeSessionAuthorityGeneration) {
                    "Runtime session authority changed before send"
                }
            }
            channel.send(envelope)
        }
            .onFailure { error ->
                Log.e(TAG, "Runtime send failed", error)
                if (
                    activeChannel !== channelAtDispatch ||
                    (expectedConnectionGeneration != null &&
                        activeConnectionGeneration != expectedConnectionGeneration) ||
                    (expectedRuntimeSessionAuthorityGeneration != null &&
                        runtimeSessionAuthorityGeneration != expectedRuntimeSessionAuthorityGeneration)
                ) {
                    return@onFailure
                }
                if (
                    !isSessionAuthenticated &&
                    envelope.type != MessageType.PairingRequest &&
                    envelope.type != MessageType.Hello &&
                    envelope.type != MessageType.AuthResponse
                ) {
                    return@onFailure
                }
                val current = state.value
                val isActiveChatSend = envelope.type == MessageType.ChatSend &&
                    current.activeRequestId == envelope.requestId
                val isTitleRequest = envelope.type == MessageType.ChatTitleRequest &&
                    pendingTitleRequestId == envelope.requestId
                val lifecycleMutation = pendingChatSessionLifecycleMutationsByRequestId.remove(envelope.requestId)
                val renameMutation = pendingChatSessionRenameMutationsByRequestId.remove(envelope.requestId)
                val isSessionLifecycleRequest = pendingChatSessionLifecycleRequestIds.remove(envelope.requestId)
                val isSessionRenameRequest = pendingChatSessionRenameRequestIds.remove(envelope.requestId)
                val isMemoryListRequest = envelope.type == MessageType.MemoryList &&
                    pendingMemoryListRequestId == envelope.requestId
                val isModelsListRequest = envelope.type == MessageType.ModelsList &&
                    pendingModelsListRequest?.requestId == envelope.requestId
                val isMemoryDuplicateSuggestionsRequest =
                    envelope.type == MessageType.MemoryDuplicateSuggestionsList &&
                        pendingMemoryDuplicateSuggestionsRequest?.requestId == envelope.requestId
                val isMemorySemanticDuplicateClustersRequest =
                    envelope.type == MessageType.MemorySemanticDuplicateClustersList &&
                        pendingMemorySemanticDuplicateClustersRequest?.requestId == envelope.requestId
                val isMemorySummaryDraftsRequest = envelope.type == MessageType.MemorySummaryDraftsList &&
                    pendingMemorySummaryDraftsRequestId == envelope.requestId
                val isDocumentCatalogRequest = envelope.type == MessageType.IndexDocumentsList &&
                    pendingDocumentCatalogRequestId == envelope.requestId
                val isDocumentSearchRequest = envelope.type == MessageType.RetrievalQuery &&
                    pendingDocumentSearchRequestId == envelope.requestId
                val isCitationResolveRequest = envelope.type == MessageType.CitationResolve &&
                    pendingCitationResolveRequestId == envelope.requestId
                val isHistoricalSourceAttributionResolveRequest =
                    envelope.type == MessageType.ChatSourceAttributionResolve &&
                        pendingHistoricalSourceAttributionResolve?.requestId == envelope.requestId
                val isTrustedSourceApproveRequest = envelope.type == MessageType.TrustedSourceApprove &&
                    pendingTrustedSourceApproveRequestId == envelope.requestId
                val isTrustedSourceDismissRequest = envelope.type == MessageType.TrustedSourceDismiss &&
                    pendingTrustedSourceDismissRequestId == envelope.requestId
                val isTrustedSourceListRequest = envelope.type == MessageType.TrustedSourceList &&
                    pendingTrustedSourceListRequestId == envelope.requestId
                val revokedSourceAnchorId = if (envelope.type == MessageType.TrustedSourceRevoke) {
                    pendingTrustedSourceRevocationsByRequestId.remove(envelope.requestId)
                } else {
                    null
                }
                val memorySummaryDraftGenerationId =
                    if (envelope.type == MessageType.MemorySummaryDraftGenerate) {
                        pendingMemorySummaryDraftGenerationsByRequestId.remove(envelope.requestId)?.draft?.id
                    } else {
                        null
                    }
                val memorySummaryDraftApprovalId =
                    if (envelope.type == MessageType.MemorySummaryDraftApprove) {
                        pendingMemorySummaryDraftApprovalDraftIdsByRequestId.remove(envelope.requestId)
                    } else {
                        null
                    }
                val memorySummaryDraftDismissalId =
                    if (envelope.type == MessageType.MemorySummaryDraftDismiss) {
                        pendingMemorySummaryDraftDismissalDraftIdsByRequestId.remove(envelope.requestId)
                    } else {
                        null
                    }
                val isRouteRefreshRequest = (
                    envelope.type == MessageType.RouteRefresh ||
                        envelope.type == MessageType.RelayAllocationAuthorization
                    ) &&
                    pendingRouteRefreshRequestId == envelope.requestId
                val runtimeAuthenticationRequest = pendingRuntimeAuthentication?.takeIf { pending ->
                    pending.channel === channelAtDispatch &&
                        ((envelope.type == MessageType.Hello && pending.helloRequestId == envelope.requestId) ||
                            (envelope.type == MessageType.AuthResponse &&
                                pending.challengeRequestId == envelope.requestId))
                }
                val isCurrentPairingRequest = envelope.type == MessageType.PairingRequest &&
                    pendingInitialPairingRequest?.requestId == envelope.requestId
                val chatSessionsListRun = pendingChatSessionsListRun?.takeIf { pending ->
                    envelope.type == MessageType.ChatSessionsList &&
                        pending.requestId == envelope.requestId
                }
                val isCurrentChatMessagesListRequest =
                    envelope.type == MessageType.ChatMessagesList &&
                        pendingChatMessagesRequestId == envelope.requestId
                val bulkLifecycleRequest = pendingChatSessionsBulkLifecycle?.takeIf { pending ->
                    pending.requestId == envelope.requestId && pending.type == envelope.type
                }
                if (isCurrentPairingRequest) {
                    clearPendingPairingRequest()
                    showError("send_failed", error.message)
                    return@onFailure
                }
                if (runtimeAuthenticationRequest != null) {
                    failRuntimeAuthentication(
                        pending = runtimeAuthenticationRequest,
                        errorCode = "authentication_failed",
                        detail = error.message,
                    )
                    return@onFailure
                }
                if (chatSessionsListRun != null) {
                    clearPendingChatSessionsListRun(chatSessionsListRun)
                    showError("chat_history_load_failed", error.message)
                    return@onFailure
                }
                if (isCurrentChatMessagesListRequest) {
                    clearPendingChatMessagesRequest()
                    showError("chat_history_load_failed", error.message)
                    return@onFailure
                }
                if (bulkLifecycleRequest != null) {
                    failPendingChatSessionsBulkLifecycle(bulkLifecycleRequest, error.message)
                    return@onFailure
                }
                if (isMemoryListRequest) {
                    clearPendingMemoryListRequest()
                    showError("memory_load_failed", error.message)
                    return@onFailure
                }
                if (isModelsListRequest) {
                    clearPendingModelsListRequest()
                    showError("send_failed", error.message)
                    return@onFailure
                }
                if (isMemoryDuplicateSuggestionsRequest) {
                    closePendingMemoryDuplicateSuggestionsRequest()
                    mutableState.update { it.copy(isScanningMemoryDuplicateSuggestions = false) }
                    showError("memory_load_failed", error.message)
                    return@onFailure
                }
                if (isMemorySemanticDuplicateClustersRequest) {
                    closePendingMemorySemanticDuplicateClustersRequest()
                    mutableState.update { it.copy(isScanningMemorySemanticDuplicateClusters = false) }
                    showError("memory_load_failed", error.message)
                    return@onFailure
                }
                if (isMemorySummaryDraftsRequest) {
                    pendingMemorySummaryDraftsRequestId = null
                    showError("memory_summary_drafts_load_failed", error.message)
                    return@onFailure
                }
                if (isDocumentCatalogRequest) {
                    pendingDocumentCatalogRequestId = null
                    mutableState.update { it.copy(isLoadingDocumentCatalog = false) }
                    showError("document_catalog_load_failed", error.message)
                    return@onFailure
                }
                if (isDocumentSearchRequest) {
                    clearPendingRuntimeDocumentSearch()
                    mutableState.update { it.copy(isSearchingDocuments = false) }
                    showError("document_search_failed", error.message)
                    return@onFailure
                }
                if (isCitationResolveRequest) {
                    clearPendingCitationResolve()
                    mutableState.update { it.copy(isResolvingCitation = false) }
                    showError("citation_resolve_failed")
                    return@onFailure
                }
                if (isHistoricalSourceAttributionResolveRequest) {
                    clearPendingHistoricalSourceAttributionResolve()
                    showError("source_attribution_resolve_failed", error.message)
                    return@onFailure
                }
                if (isTrustedSourceApproveRequest) {
                    pendingTrustedSourceApproveRequestId = null
                    mutableState.update { it.copy(isApprovingTrustedSource = false) }
                    showError("trusted_source_approve_failed")
                    return@onFailure
                }
                if (isTrustedSourceDismissRequest) {
                    pendingTrustedSourceDismissRequestId = null
                    mutableState.update { it.copy(isDismissingTrustedSource = false) }
                    showError("trusted_source_dismiss_failed")
                    return@onFailure
                }
                if (isTrustedSourceListRequest) {
                    pendingTrustedSourceListRequestId = null
                    mutableState.update { it.copy(isLoadingTrustedSources = false) }
                    showError("trusted_source_list_failed")
                    return@onFailure
                }
                if (revokedSourceAnchorId != null) {
                    mutableState.update {
                        it.copy(
                            revokingTrustedSourceAnchorIds =
                                it.revokingTrustedSourceAnchorIds - revokedSourceAnchorId,
                        )
                    }
                    showError("trusted_source_revoke_failed")
                    return@onFailure
                }
                if (memorySummaryDraftGenerationId != null) {
                    mutableState.update {
                        it.copy(
                            generatingMemorySummaryDraftIds =
                                it.generatingMemorySummaryDraftIds - memorySummaryDraftGenerationId,
                        )
                    }
                    showError("memory_summary_draft_generation_failed", error.message)
                    return@onFailure
                }
                if (memorySummaryDraftApprovalId != null) {
                    mutableState.update {
                        it.copy(
                            approvingMemorySummaryDraftIds =
                                it.approvingMemorySummaryDraftIds - memorySummaryDraftApprovalId,
                        )
                    }
                    showError("memory_summary_draft_approval_failed", error.message)
                    return@onFailure
                }
                if (memorySummaryDraftDismissalId != null) {
                    mutableState.update {
                        it.copy(
                            dismissingMemorySummaryDraftIds =
                                it.dismissingMemorySummaryDraftIds - memorySummaryDraftDismissalId,
                        )
                    }
                    showError("memory_summary_draft_dismiss_failed", error.message)
                    return@onFailure
                }
                if (isRouteRefreshRequest) {
                    clearPendingRouteRefreshRequest()
                    scheduleRuntimeRouteRefreshRetry()
                    return@onFailure
                }
                if (isTitleRequest) {
                    clearPendingTitleRequest()
                    return@onFailure
                }
                if (isSessionLifecycleRequest) {
                    handleRuntimeChatSessionMutationFailure(
                        detail = error.message,
                        lifecycleMutation = lifecycleMutation,
                    )
                    return@onFailure
                }
                if (isSessionRenameRequest) {
                    handleRuntimeChatSessionMutationFailure(
                        detail = error.message,
                        renameMutation = renameMutation,
                    )
                    return@onFailure
                }
                if (
                    envelope.type in REQUEST_BOUND_SEND_FAILURE_TYPES ||
                    (envelope.type == MessageType.ChatSend && !isActiveChatSend)
                ) {
                    return@onFailure
                }
                val cleanedMessages = if (isActiveChatSend) {
                    current.messages
                        .withoutTrailingAssistantSourceAttributions()
                        .withoutTrailingBlankAssistantPlaceholder()
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
                    error = runtimeUiError("send_failed", error.message)
                )
                if (isActiveChatSend) {
                    persistActiveMessages(cleanedMessages, clearError = false)
                }
            }
        return result.isSuccess
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

    private fun <T> decodeTrustedSourceResponse(serializer: KSerializer<T>, payload: JsonObject): T? {
        return try {
            json.decodeFromJsonElement(serializer, payload)
        } catch (_: SerializationException) {
            null
        } catch (_: IllegalArgumentException) {
            null
        }
    }

    private fun rememberTrustedSource(source: TrustedSourcePayload) {
        trustedSourceGrantsBySourceAnchorId[source.sourceAnchorId] = source.grantId
    }

    private fun trustedSourceGrantIdsForSelection(current: RuntimeUiState): List<String>? {
        if (current.selectedTrustedSourceAnchorIds.isEmpty()) return emptyList()
        val grantIds = current.selectedTrustedSourceAnchorIds.mapNotNull {
            trustedSourceGrantsBySourceAnchorId[it]
        }
        if (grantIds.size == current.selectedTrustedSourceAnchorIds.size) return grantIds
        mutableState.update { it.copy(selectedTrustedSourceAnchorIds = emptyList()) }
        showError("trusted_source_not_found")
        return null
    }

    private fun scheduleCitationResolveTimeout(requestId: String) {
        citationResolveRequestTimeoutJob?.cancel()
        citationResolveRequestTimeoutJob = viewModelScope.launch {
            delay(CITATION_RESOLVE_REQUEST_TIMEOUT_MS)
            if (pendingCitationResolveRequestId != requestId) return@launch
            pendingCitationResolveRequestId = null
            pendingCitationResolveSourceAnchorId = null
            citationResolveRequestTimeoutJob = null
            mutableState.update { it.copy(isResolvingCitation = false) }
            showError("citation_resolve_failed", "timeout")
        }
    }

    private fun clearPendingCitationResolve() {
        pendingCitationResolveRequestId = null
        pendingCitationResolveSourceAnchorId = null
        citationResolveRequestTimeoutJob?.cancel()
        citationResolveRequestTimeoutJob = null
    }

    private fun scheduleHistoricalSourceAttributionResolveTimeout(requestId: String) {
        historicalSourceAttributionResolveTimeoutJob?.cancel()
        historicalSourceAttributionResolveTimeoutJob = viewModelScope.launch {
            delay(CITATION_RESOLVE_REQUEST_TIMEOUT_MS)
            if (pendingHistoricalSourceAttributionResolve?.requestId != requestId) return@launch
            clearPendingHistoricalSourceAttributionResolve()
            showError("source_attribution_resolve_failed", "timeout")
        }
    }

    private fun clearPendingHistoricalSourceAttributionResolve() {
        pendingHistoricalSourceAttributionResolve = null
        historicalSourceAttributionResolveTimeoutJob?.cancel()
        historicalSourceAttributionResolveTimeoutJob = null
        mutableState.update {
            it.copy(
                resolvingSourceAttributionMessageId = null,
                resolvingSourceAttributionIndex = null,
            )
        }
    }

    private fun recordTrustedSourceMutation() {
        trustedSourceMutationGeneration += 1
    }

    private fun decodeRouteRefreshPayloadForRetry(payload: JsonObject): RouteRefreshPayload? {
        return try {
            json.decodeFromJsonElement(RouteRefreshPayload.serializer(), payload)
        } catch (_: SerializationException) {
            null
        } catch (_: IllegalArgumentException) {
            null
        }
    }

    private fun showError(code: String, detail: String? = null) {
        mutableState.update { it.copy(error = runtimeUiError(code, detail)) }
    }

    private fun rejectUserMutationWhileStreaming(): Boolean {
        if (!state.value.isStreaming) return false
        showError("generation_in_progress")
        return true
    }

    private fun rejectUserMutationWhileActiveChatMessagesLoading(): Boolean {
        if (!state.value.isLoadingActiveChatMessages) return false
        showError("chat_history_loading")
        return true
    }

    private fun publishTrustedRemoteRouteExpiredIfNeeded(
        current: RuntimeUiState = state.value,
    ): Boolean {
        if (autoReconnectTrustedRuntimeConnectionTarget(current) != null) {
            return false
        }
        if (!current.trustedRuntime.hasExpiredRemoteRoute(dependencies.currentTimeMillis())) {
            return false
        }
        val trustedRuntimeWithoutExpiredRelay = current.trustedRuntime?.withoutRemoteRoutes()
        revokeAuthenticatedRuntimeSessionState()
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

    private fun clearPendingRuntimeHistoryRequests() {
        clearPendingChatSessionsListRun()
        clearPendingChatMessagesRequest()
    }

    private fun PendingChatSessionsListRun.correlation(): RuntimeChatHistoryRequestCorrelation {
        return RuntimeChatHistoryRequestCorrelation(
            requestId = requestId,
            type = MessageType.ChatSessionsList,
            channel = channel,
            connectionGeneration = connectionGeneration,
            authorityGeneration = authorityGeneration,
        )
    }

    private fun clearPendingChatMessagesRequest() {
        val loadingSessionId = pendingChatMessagesSessionId
        pendingChatMessagesRequestCorrelation?.let(::closeRuntimeChatHistoryRequest)
        pendingChatMessagesRequestId = null
        pendingChatMessagesSessionId = null
        pendingChatMessagesRequestCorrelation = null
        clearChatMessagesLoading(loadingSessionId)
    }

    private fun closeRuntimeChatHistoryRequest(correlation: RuntimeChatHistoryRequestCorrelation) {
        closedRuntimeChatHistoryRequests.removeAll { closed ->
            closed.requestId == correlation.requestId &&
                closed.type == correlation.type &&
                closed.channel === correlation.channel &&
                closed.connectionGeneration == correlation.connectionGeneration &&
                closed.authorityGeneration == correlation.authorityGeneration
        }
        closedRuntimeChatHistoryRequests += correlation
        while (closedRuntimeChatHistoryRequests.size > MAX_CLOSED_RUNTIME_CHAT_HISTORY_REQUESTS) {
            closedRuntimeChatHistoryRequests.removeAt(0)
        }
    }

    private fun isClosedRuntimeChatHistoryRequest(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        return closedRuntimeChatHistoryRequests.any { closed ->
            closed.requestId == requestId &&
                closed.channel === sourceChannel &&
                closed.connectionGeneration == sourceConnectionGeneration
        }
    }

    private fun shouldIgnoreStaleRuntimeChatHistoryError(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        val currentSessionsRequest = pendingChatSessionsListRun?.let { run ->
            run.requestId == requestId &&
                run.channel === sourceChannel &&
                run.connectionGeneration == sourceConnectionGeneration
        } == true
        val currentMessagesRequest = pendingChatMessagesRequestCorrelation?.let { correlation ->
            correlation.requestId == requestId &&
                correlation.channel === sourceChannel &&
                correlation.connectionGeneration == sourceConnectionGeneration
        } == true
        if (currentSessionsRequest || currentMessagesRequest) return false

        return requestId.startsWith(CHAT_SESSIONS_LIST_REQUEST_ID_PREFIX) ||
            requestId.startsWith(CHAT_MESSAGES_LIST_REQUEST_ID_PREFIX) ||
            isClosedRuntimeChatHistoryRequest(
                requestId,
                sourceChannel,
                sourceConnectionGeneration,
            )
    }

    private fun clearRuntimeChatSearchAuthority() {
        runtimeChatSearchSummariesById = emptyMap()
        mutableState.update {
            it.copy(
                chatSessionSearchQuery = null,
                chatSessionSearchResults = emptyList(),
            )
        }
    }

    private fun consumeRuntimeChatSearchSummary(sessionId: String) {
        runtimeChatSearchSummariesById = runtimeChatSearchSummariesById - sessionId
        mutableState.update {
            it.copy(
                chatSessionSearchResults = it.chatSessionSearchResults.filterNot { result ->
                    result.id == sessionId
                },
            )
        }
    }

    private fun PersistedRuntimeData.revertingRuntimeChatSessionMutations(
        mutations: Collection<PendingChatSessionMutation>,
    ): PersistedRuntimeData {
        return mutations
            .sortedByDescending(PendingChatSessionMutation::sequence)
            .fold(this) { repairedData, mutation ->
                when (mutation) {
                    is PendingChatSessionLifecycleMutation -> repairedData.copy(
                        activeSessionId = if (
                            mutation.restoreAsActive && repairedData.activeSessionId == null
                        ) {
                            mutation.sessionId
                        } else {
                            repairedData.activeSessionId
                        },
                        sessions = listOf(mutation.previousSession) + repairedData.sessions.filterNot { session ->
                            session.id == mutation.sessionId
                        },
                        suppressedRuntimeSessions = repairedData.suppressedRuntimeSessions.filterNot { suppression ->
                            suppression.sessionId == mutation.sessionId
                        },
                    ).sanitized()

                    is PendingChatSessionRenameMutation -> repairedData.withRevertedRuntimeChatSessionRename(
                        sessionId = mutation.sessionId,
                        previousTitle = mutation.previousTitle,
                        previousTitleManuallyEdited = mutation.previousTitleManuallyEdited,
                        previousTitleGenerated = mutation.previousTitleGenerated,
                        previousUpdatedAtMillis = mutation.previousUpdatedAtMillis,
                    )
                }
            }
    }

    private fun rollbackAndClearPendingRuntimeChatSessionMutations(
        additionalMutations: Collection<PendingChatSessionMutation> = emptyList(),
    ) {
        val pendingMutations =
            pendingChatSessionLifecycleMutationsByRequestId.values +
                pendingChatSessionRenameMutationsByRequestId.values +
                additionalMutations
        pendingChatSessionLifecycleRequestIds.clear()
        pendingChatSessionRenameRequestIds.clear()
        pendingChatSessionLifecycleMutationsByRequestId.clear()
        pendingChatSessionRenameMutationsByRequestId.clear()
        clearPendingTitleRequest()
        val repairedData = persistedRuntimeData.revertingRuntimeChatSessionMutations(pendingMutations)
        if (repairedData != persistedRuntimeData) {
            publishPersistedRuntimeData(
                data = repairedData,
                save = true,
                clearError = false,
            )
        }
    }

    private fun revokeAuthenticatedRuntimeSessionState(
        additionalMutations: Collection<PendingChatSessionMutation> = emptyList(),
    ) {
        isSessionAuthenticated = false
        runtimeSessionAuthorityGeneration += 1L
        clearPendingModelsListRequest()
        modelCatalogAcceptedAuthorityGeneration = null
        resetMemoryDuplicateSuggestionsAuthority()
        resetMemorySemanticDuplicateSuggestionsAuthority()
        resetMemorySemanticDuplicateClustersAuthority()
        runtimeChatSessionsAuthoritativeSyncSupported = false
        runtimeChatSessionsBulkAuthorityEnabled = false
        clearTrustedSourceSessionState()
        clearPendingRuntimeHistoryRequests()
        clearPendingChatSessionsBulkLifecycle()
        clearRuntimeChatSearchAuthority()
        rollbackAndClearPendingRuntimeChatSessionMutations(additionalMutations)
        cancelRuntimeRouteRefreshLease()
        clearPendingRouteRefreshRequest()
    }

    private fun clearPendingRuntimeDocumentRequests() {
        pendingDocumentCatalogRequestId = null
        clearPendingRuntimeDocumentSearch()
        clearTrustedSourceSessionState()
    }

    private fun clearPendingRuntimeDocumentSearch() {
        pendingDocumentSearchRequestId = null
        pendingDocumentSearchPayload = null
        pendingDocumentSearchCanRetryWithoutEmbedding = false
    }

    private fun clearPendingMemoryListRequest() {
        pendingMemoryListRequestId = null
        pendingMemoryListQuery = null
        pendingMemoryListEmbeddingModelId = null
        pendingMemoryListChannel = null
        pendingMemoryListConnectionGeneration = null
        pendingMemoryListAuthorityGeneration = null
    }

    private fun clearPendingModelsListRequest() {
        pendingModelsListRequest = null
        mutableState.update { it.copy(isLoadingModels = false) }
    }

    private fun PendingModelsListRequest.matchesCurrentModelsAuthority(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        return this.requestId == requestId &&
            channel === sourceChannel &&
            connectionGeneration == sourceConnectionGeneration &&
            authorityGeneration == runtimeSessionAuthorityGeneration &&
            activeChannel === sourceChannel &&
            activeConnectionGeneration == sourceConnectionGeneration &&
            isSessionAuthenticated
    }

    private fun isCurrentMemoryListRequest(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        return pendingMemoryListRequestId == requestId &&
            pendingMemoryListChannel === sourceChannel &&
            pendingMemoryListConnectionGeneration == sourceConnectionGeneration &&
            pendingMemoryListAuthorityGeneration == runtimeSessionAuthorityGeneration &&
            activeChannel === sourceChannel &&
            activeConnectionGeneration == sourceConnectionGeneration &&
            isSessionAuthenticated
    }

    private fun isCurrentMemoryDuplicateSuggestionsRequest(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        val pending = pendingMemoryDuplicateSuggestionsRequest ?: return false
        return pending.requestId == requestId &&
            pending.channel === sourceChannel &&
            pending.connectionGeneration == sourceConnectionGeneration &&
            pending.authorityGeneration == runtimeSessionAuthorityGeneration &&
            activeChannel === sourceChannel &&
            activeConnectionGeneration == sourceConnectionGeneration &&
            isSessionAuthenticated
    }

    private fun isCurrentMemorySemanticDuplicateSuggestionsRequest(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        val pending = pendingMemorySemanticDuplicateSuggestionsRequest ?: return false
        val current = state.value
        return pending.requestId == requestId &&
            pending.channel === sourceChannel &&
            pending.connectionGeneration == sourceConnectionGeneration &&
            pending.authorityGeneration == runtimeSessionAuthorityGeneration &&
            activeChannel === sourceChannel &&
            activeConnectionGeneration == sourceConnectionGeneration &&
            isSessionAuthenticated &&
            current.selectedEmbeddingModelId == pending.embeddingModelId &&
            hasEligibleMemorySemanticDuplicateSuggestionsModel(
                current,
                pending.embeddingModelId,
            )
    }

    private fun isCurrentMemorySemanticDuplicateClustersRequest(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        val pending = pendingMemorySemanticDuplicateClustersRequest ?: return false
        val current = state.value
        return pending.requestId == requestId &&
            pending.channel === sourceChannel &&
            pending.connectionGeneration == sourceConnectionGeneration &&
            pending.authorityGeneration == runtimeSessionAuthorityGeneration &&
            pending.memoryCatalogGeneration == memoryCatalogGeneration &&
            pending.modelCatalogGeneration == modelCatalogGeneration &&
            activeChannel === sourceChannel &&
            activeConnectionGeneration == sourceConnectionGeneration &&
            isSessionAuthenticated &&
            current.selectedEmbeddingModelId == pending.embeddingModelId &&
            current.memorySemanticDuplicateClustersThresholdBasisPoints ==
                pending.minimumSimilarityBasisPoints &&
            hasEligibleMemorySemanticDuplicateSuggestionsModel(
                current,
                pending.embeddingModelId,
            )
    }

    private fun shouldIgnoreClosedMemoryDuplicateSuggestionsError(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        if (isCurrentMemoryDuplicateSuggestionsRequest(
                requestId = requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return false
        if (requestId.startsWith(MEMORY_DUPLICATE_SUGGESTIONS_REQUEST_ID_PREFIX)) return true
        return closedMemoryDuplicateSuggestionsRequests.any { closed ->
            closed.requestId == requestId &&
                closed.channel === sourceChannel &&
                closed.connectionGeneration == sourceConnectionGeneration
        }
    }

    private fun closePendingMemoryDuplicateSuggestionsRequest() {
        val pending = pendingMemoryDuplicateSuggestionsRequest ?: return
        pendingMemoryDuplicateSuggestionsRequest = null
        closedMemoryDuplicateSuggestionsRequests.removeAll { closed ->
            closed.requestId == pending.requestId &&
                closed.channel === pending.channel &&
                closed.connectionGeneration == pending.connectionGeneration &&
                closed.authorityGeneration == pending.authorityGeneration
        }
        closedMemoryDuplicateSuggestionsRequests += pending
        while (
            closedMemoryDuplicateSuggestionsRequests.size >
            MAX_CLOSED_MEMORY_DUPLICATE_SUGGESTIONS_REQUESTS
        ) {
            closedMemoryDuplicateSuggestionsRequests.removeAt(0)
        }
    }

    private fun shouldIgnoreClosedMemorySemanticDuplicateSuggestionsError(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        if (isCurrentMemorySemanticDuplicateSuggestionsRequest(
                requestId = requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return false
        if (requestId.startsWith(MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_REQUEST_ID_PREFIX)) {
            return true
        }
        return closedMemorySemanticDuplicateSuggestionsRequests.any { closed ->
            closed.requestId == requestId &&
                closed.channel === sourceChannel &&
                closed.connectionGeneration == sourceConnectionGeneration
        }
    }

    private fun closePendingMemorySemanticDuplicateSuggestionsRequest() {
        val pending = pendingMemorySemanticDuplicateSuggestionsRequest ?: return
        pendingMemorySemanticDuplicateSuggestionsRequest = null
        closedMemorySemanticDuplicateSuggestionsRequests.removeAll { closed ->
            closed.requestId == pending.requestId &&
                closed.channel === pending.channel &&
                closed.connectionGeneration == pending.connectionGeneration &&
                closed.authorityGeneration == pending.authorityGeneration
        }
        closedMemorySemanticDuplicateSuggestionsRequests += pending
        while (
            closedMemorySemanticDuplicateSuggestionsRequests.size >
            MAX_CLOSED_MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_REQUESTS
        ) {
            closedMemorySemanticDuplicateSuggestionsRequests.removeAt(0)
        }
    }

    private fun shouldIgnoreClosedMemorySemanticDuplicateClustersError(
        requestId: String,
        sourceChannel: RuntimeProtocolChannel,
        sourceConnectionGeneration: Long,
    ): Boolean {
        if (isCurrentMemorySemanticDuplicateClustersRequest(
                requestId = requestId,
                sourceChannel = sourceChannel,
                sourceConnectionGeneration = sourceConnectionGeneration,
            )
        ) return false
        if (requestId.startsWith(MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_REQUEST_ID_PREFIX)) {
            return true
        }
        return closedMemorySemanticDuplicateClustersRequests.any { closed ->
            closed.requestId == requestId &&
                closed.channel === sourceChannel &&
                closed.connectionGeneration == sourceConnectionGeneration
        }
    }

    private fun closePendingMemorySemanticDuplicateClustersRequest() {
        val pending = pendingMemorySemanticDuplicateClustersRequest ?: return
        pendingMemorySemanticDuplicateClustersRequest = null
        closedMemorySemanticDuplicateClustersRequests.removeAll { closed ->
            closed.requestId == pending.requestId &&
                closed.channel === pending.channel &&
                closed.connectionGeneration == pending.connectionGeneration &&
                closed.authorityGeneration == pending.authorityGeneration
        }
        closedMemorySemanticDuplicateClustersRequests += pending
        while (
            closedMemorySemanticDuplicateClustersRequests.size >
            MAX_CLOSED_MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_REQUESTS
        ) {
            closedMemorySemanticDuplicateClustersRequests.removeAt(0)
        }
    }

    private fun resetMemoryDuplicateSuggestionsAuthority() {
        memoryDuplicateSuggestionsListAcceptedAuthorityGeneration = null
        memoryDuplicateSuggestionsUnsupportedAuthorityGeneration = null
        clearMemoryDuplicateSuggestions()
        mutableState.update { it.copy(memoryDuplicateSuggestionsAvailable = false) }
    }

    private fun resetMemorySemanticDuplicateSuggestionsAuthority() {
        memorySemanticDuplicateSuggestionsListAcceptedAuthorityGeneration = null
        memorySemanticDuplicateSuggestionsUnsupportedAuthorityGeneration = null
        clearMemorySemanticDuplicateSuggestions()
        mutableState.update { it.copy(memorySemanticDuplicateSuggestionsAvailable = false) }
    }

    private fun resetMemorySemanticDuplicateClustersAuthority() {
        memorySemanticDuplicateClustersListAcceptedAuthorityGeneration = null
        memorySemanticDuplicateClustersUnsupportedAuthorityGeneration = null
        clearMemorySemanticDuplicateClusters()
        mutableState.update { it.copy(memorySemanticDuplicateClustersAvailable = false) }
    }

    private fun clearMemoryDuplicateSuggestions() {
        closePendingMemoryDuplicateSuggestionsRequest()
        mutableState.update {
            it.copy(
                memoryDuplicateSuggestionGroups = emptyList(),
                memoryDuplicateSuggestionsScannedCount = 0,
                memoryDuplicateSuggestionsTruncated = false,
                hasMemoryDuplicateSuggestionsResult = false,
                isScanningMemoryDuplicateSuggestions = false,
            )
        }
    }

    private fun clearMemorySemanticDuplicateSuggestions() {
        closePendingMemorySemanticDuplicateSuggestionsRequest()
        mutableState.update {
            it.copy(
                memorySemanticDuplicateSuggestionPairs = emptyList(),
                memorySemanticDuplicateSuggestionsScannedCount = 0,
                memorySemanticDuplicateSuggestionsOmittedCount = 0,
                memorySemanticDuplicateSuggestionsTruncated = false,
                hasMemorySemanticDuplicateSuggestionsResult = false,
                isScanningMemorySemanticDuplicateSuggestions = false,
            )
        }
    }

    private fun clearMemorySemanticDuplicateClusters() {
        closePendingMemorySemanticDuplicateClustersRequest()
        mutableState.update {
            it.copy(
                memorySemanticDuplicateClusters = emptyList(),
                memorySemanticDuplicateClustersScannedCount = 0,
                memorySemanticDuplicateClustersOmittedCount = 0,
                memorySemanticDuplicateClustersTruncated = false,
                memorySemanticDuplicateClustersThresholdBasisPoints = 9_000,
                hasMemorySemanticDuplicateClustersResult = false,
                isScanningMemorySemanticDuplicateClusters = false,
            )
        }
    }

    private fun hasEligibleMemorySemanticDuplicateSuggestionsModel(
        candidateState: RuntimeUiState,
        modelId: String,
    ): Boolean {
        return candidateState.models.any { model ->
            model.id == modelId &&
                isCanonicalProviderQualifiedModelId(model.id) &&
                model.installed &&
                model.isEmbeddingModel() &&
                model.isRuntimeHostLocalModel()
        }
    }

    private fun isMemorySemanticDuplicateSuggestionsAvailable(
        candidateState: RuntimeUiState,
    ): Boolean {
        val modelId = candidateState.selectedEmbeddingModelId ?: return false
        return memorySemanticDuplicateSuggestionsListAcceptedAuthorityGeneration ==
            runtimeSessionAuthorityGeneration &&
            memorySemanticDuplicateSuggestionsUnsupportedAuthorityGeneration !=
            runtimeSessionAuthorityGeneration &&
            modelCatalogAcceptedAuthorityGeneration == runtimeSessionAuthorityGeneration &&
            hasEligibleMemorySemanticDuplicateSuggestionsModel(candidateState, modelId)
    }

    private fun updateMemorySemanticDuplicateSuggestionsAvailability() {
        mutableState.update { candidateState ->
            candidateState.copy(
                memorySemanticDuplicateSuggestionsAvailable =
                    isMemorySemanticDuplicateSuggestionsAvailable(candidateState),
            )
        }
    }

    private fun isMemorySemanticDuplicateClustersAvailable(
        candidateState: RuntimeUiState,
    ): Boolean {
        val modelId = candidateState.selectedEmbeddingModelId ?: return false
        return memorySemanticDuplicateClustersListAcceptedAuthorityGeneration ==
            runtimeSessionAuthorityGeneration &&
            memorySemanticDuplicateClustersUnsupportedAuthorityGeneration !=
            runtimeSessionAuthorityGeneration &&
            modelCatalogAcceptedAuthorityGeneration == runtimeSessionAuthorityGeneration &&
            hasEligibleMemorySemanticDuplicateSuggestionsModel(candidateState, modelId)
    }

    private fun updateMemorySemanticDuplicateClustersAvailability() {
        mutableState.update { candidateState ->
            candidateState.copy(
                memorySemanticDuplicateClustersAvailable =
                    isMemorySemanticDuplicateClustersAvailable(candidateState),
            )
        }
    }

    private fun clearTrustedSourceSessionState() {
        clearPendingCitationResolve()
        clearPendingHistoricalSourceAttributionResolve()
        pendingSourceReview = null
        pendingTrustedSourceApproveRequestId = null
        pendingTrustedSourceDismissRequestId = null
        pendingTrustedSourceListRequestId = null
        pendingTrustedSourceListMutationGeneration = null
        trustedSourceMutationGeneration = 0
        pendingTrustedSourceRevocationsByRequestId.clear()
        trustedSourceGrantsBySourceAnchorId.clear()
        mutableState.update {
            it.copy(
                sourceReview = null,
                trustedSources = emptyList(),
                selectedTrustedSourceAnchorIds = emptyList(),
                hasLoadedTrustedSources = false,
                isResolvingCitation = false,
                resolvingSourceAttributionMessageId = null,
                resolvingSourceAttributionIndex = null,
                isApprovingTrustedSource = false,
                isDismissingTrustedSource = false,
                isLoadingTrustedSources = false,
                revokingTrustedSourceAnchorIds = emptySet(),
            )
        }
    }

    private fun clearChatMessagesLoading(sessionId: String?) {
        if (sessionId == null) return
        mutableState.update { current ->
            if (current.loadingChatSessionId == sessionId) {
                current.copy(loadingChatSessionId = null)
            } else {
                current
            }
        }
    }

    private fun canSendRuntimeMemoryCommand(): Boolean {
        return isSessionAuthenticated && activeChannel?.isConnected == true
    }

    private fun canSendRuntimeChatHistoryCommand(): Boolean {
        return isSessionAuthenticated && activeChannel?.isConnected == true
    }

    private fun canSendRuntimeDocumentSearchCommand(): Boolean {
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
        syncComposerDraft: Boolean = false,
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
                loadingChatSessionId = it.loadingChatSessionId?.takeIf { loadingId ->
                    loadingId == cleanData.activeSessionId
                },
                selectedModelId = cleanData.selectedModelId,
                selectedEmbeddingModelId = cleanData.selectedEmbeddingModelId,
                chatInput = if (syncComposerDraft) {
                    cleanData.composerDraftForSession(cleanData.activeSessionId)
                } else {
                    it.chatInput
                },
                pendingAttachments = if (syncComposerDraft) {
                    pendingAttachmentsBySession[cleanData.activeSessionId].orEmpty()
                } else {
                    it.pendingAttachments
                },
                messages = activeSessionMessages(cleanData),
                memoryEntries = runtimeMemoryEntries(cleanData),
                selectedLanguageTag = cleanData.appLanguageTag,
                selectedLanguageSource = cleanData.appLanguageSource ?: APP_LANGUAGE_SOURCE_DEFAULT,
                selectedTheme = RuntimeAppTheme.fromStorage(cleanData.appTheme),
                trustedRuntimeAutoReconnectEnabled = cleanData.trustedRuntimeAutoReconnectEnabled,
                pairingOnboardingCompleted = cleanData.pairingOnboardingCompleted,
                error = if (clearError) null else it.error,
            )
        }
    }

    private fun runtimeChatSessionForAction(sessionId: String): PersistedChatSession? {
        persistedRuntimeData.sessions
            .firstOrNull { it.id == sessionId && it.runtimeOwned }
            ?.let { current ->
                consumeRuntimeChatSearchSummary(sessionId)
                return current
            }
        val summary = runtimeChatSearchSummariesById[sessionId]
        if (summary != null) {
            val mergedData = persistedRuntimeData.withRuntimeChatSessionSummary(
                summary = summary,
                nowMillis = nowMillis(),
            )
            val mergedSession = mergedData.sessions
                .firstOrNull { it.id == sessionId }
                ?.takeIf { it.runtimeOwned }
                ?: return null
            publishPersistedRuntimeData(
                data = mergedData,
                save = false,
                clearError = false,
            )
            consumeRuntimeChatSearchSummary(sessionId)
            return mergedSession
        }
        return persistedRuntimeData.sessions.firstOrNull { it.id == sessionId }
    }

    private fun persistComposerDraft(
        value: String,
        sessionId: String? = state.value.activeChatSessionId,
    ): String {
        val cleanData = persistedRuntimeData.withComposerDraft(value, sessionId = sessionId)
        persistedRuntimeData = cleanData
        localStore.save(cleanData)
        return cleanData.composerDraftForSession(sessionId)
    }

    private fun clearComposerDraft(sessionId: String? = state.value.activeChatSessionId): String {
        return persistComposerDraft("", sessionId = sessionId)
    }

    private fun rememberPendingAttachmentsForCurrentSession() {
        rememberPendingAttachmentsForSession(
            sessionId = state.value.activeChatSessionId,
            attachments = state.value.pendingAttachments,
        )
    }

    private fun rememberPendingAttachmentsForSession(
        sessionId: String?,
        attachments: List<RuntimePendingAttachment>,
    ) {
        if (attachments.isEmpty()) {
            pendingAttachmentsBySession.remove(sessionId)
        } else {
            pendingAttachmentsBySession[sessionId] = attachments
        }
    }

    private fun clearPendingAttachmentsForSession(sessionId: String? = state.value.activeChatSessionId) {
        pendingAttachmentsBySession.remove(sessionId)
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
        val selectionChanged = cleanData.selectedEmbeddingModelId !=
            persistedRuntimeData.selectedEmbeddingModelId
        persistedRuntimeData = cleanData
        localStore.save(cleanData)
        if (selectionChanged) {
            clearMemorySemanticDuplicateSuggestions()
            clearMemorySemanticDuplicateClusters()
        }
        if (publish) {
            mutableState.update {
                val nextState = it.copy(
                    selectedEmbeddingModelId = cleanData.selectedEmbeddingModelId,
                    error = null,
                )
                nextState.copy(
                    memorySemanticDuplicateSuggestionsAvailable =
                        isMemorySemanticDuplicateSuggestionsAvailable(nextState),
                    memorySemanticDuplicateClustersAvailable =
                        isMemorySemanticDuplicateClustersAvailable(nextState),
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
        stopDiscoveryInternal()
        closeRuntimeConnection()
        viewModelScope.cancel()
        super.onCleared()
    }

    private companion object {
        const val TAG = "RuntimeClientVM"
        const val MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
        const val RECONNECT_DELAY_MS = 750L
        const val MAX_POST_PAIRING_AUTHENTICATION_ATTEMPTS = 2
        const val MAX_PENDING_PAIRING_RETRY_ATTEMPTS = 120
        const val PENDING_PAIRING_DISCOVERY_TIMEOUT_MS = 15_000L
        const val MAX_RUNTIME_CHAT_SESSIONS = 100
        const val MAX_RUNTIME_CHAT_MESSAGES = 200
        const val MAX_RUNTIME_MEMORY_SUMMARY_DRAFTS = 5
        const val MAX_RUNTIME_DOCUMENT_CATALOG_ROWS = 100
        const val MAX_RUNTIME_DOCUMENT_SEARCH_RESULTS = 10
        const val MAX_RUNTIME_TRUSTED_SOURCES = 100
        const val MAX_RUNTIME_DOCUMENT_QUERY_CHARACTERS = 1024
        private const val DOCUMENT_SEARCH_REQUEST_ID_PREFIX = "retrieval-query-"
        private const val MODELS_LIST_REQUEST_ID_PREFIX = "models-list-"
        private const val MEMORY_DUPLICATE_SUGGESTIONS_REQUEST_ID_PREFIX =
            "memory-duplicate-suggestions-list-"
        private const val MEMORY_SEMANTIC_DUPLICATE_SUGGESTIONS_REQUEST_ID_PREFIX =
            "memory-semantic-duplicate-suggestions-list-"
        private const val MEMORY_SEMANTIC_DUPLICATE_CLUSTERS_REQUEST_ID_PREFIX =
            "memory-semantic-duplicate-clusters-list-"
        private const val CHAT_SESSIONS_LIST_REQUEST_ID_PREFIX = "chat-sessions-list-"
        private const val CHAT_MESSAGES_LIST_REQUEST_ID_PREFIX = "chat-messages-list-"
        private const val CITATION_RESOLVE_REQUEST_ID_PREFIX = "citation-resolve-"
        private const val HISTORICAL_SOURCE_ATTRIBUTION_RESOLVE_REQUEST_ID_PREFIX =
            "chat-source-attribution-resolve-"
        private const val TRUSTED_SOURCE_APPROVE_REQUEST_ID_PREFIX = "trusted-source-approve-"
        private const val TRUSTED_SOURCE_DISMISS_REQUEST_ID_PREFIX = "trusted-source-dismiss-"
        private const val TRUSTED_SOURCE_LIST_REQUEST_ID_PREFIX = "trusted-source-list-"
        private const val TRUSTED_SOURCE_REVOKE_REQUEST_ID_PREFIX = "trusted-source-revoke-"
        private val TERMINAL_TRUSTED_SOURCE_REVIEW_ERROR_CODES = setOf(
            "trusted_source_review_not_found",
            "trusted_source_review_expired",
            "trusted_source_review_stale",
        )
        private const val LEGACY_RETRIEVAL_EMBEDDING_UNSUPPORTED_MESSAGE =
            "retrieval.query payload contains unsupported field(s): embedding_model_id"
        const val MAX_RUNTIME_DOCUMENT_SNIPPET_CHARACTERS = 480
        const val ATTACHMENT_TYPE_IMAGE = "image"
        const val ATTACHMENT_TYPE_DOCUMENT = "document"
        val CLIENT_CAPABILITIES = RUNTIME_CLIENT_CAPABILITIES
        val SUCCESS_PULL_STATUSES = setOf("success", "succeeded", "installed", "complete", "completed", "ready", "ok")
        val ACCEPTED_PULL_STATUSES = setOf("accepted", "queued", "pending", "started", "pulling", "downloading", "installing", "in_progress")
        val FAILED_PULL_STATUSES = setOf("failed", "failure", "error", "cancelled", "canceled")
    }
}

private fun RuntimeDocumentIndexDocumentPayload.toRuntimeDocumentIndexDocument(index: Int): RuntimeDocumentIndexDocument {
    val canonicalChunkCount = chunkCount.coerceAtLeast(0)
    return RuntimeDocumentIndexDocument(
        id = id.canonicalRuntimeDocumentIdOrFallback(index),
        displayName = displayName.canonicalRuntimeDocumentDisplayNameOrFallback(),
        mimeType = mimeType.canonicalRuntimeDocumentMimeTypeOrFallback(),
        contentFingerprint = contentFingerprint.canonicalRuntimeDocumentContentFingerprintOrEmpty(),
        extractedCharacterCount = extractedCharacterCount.coerceAtLeast(0),
        chunkCount = canonicalChunkCount,
        quality = canonicalRuntimeDocumentQualityForChunkCount(canonicalChunkCount),
    )
}

private fun TrustedSourcePayload.toRuntimeTrustedSource(): RuntimeTrustedSource {
    return RuntimeTrustedSource(
        sourceAnchorId = sourceAnchorId,
        document = document.toRuntimeDocumentIndexDocument(0),
    )
}

private fun List<RuntimeTrustedSource>.upsertTrustedSource(source: RuntimeTrustedSource): List<RuntimeTrustedSource> {
    return filterNot { it.sourceAnchorId == source.sourceAnchorId } + source
}

private fun String.isTrustedSourceRequestId(): Boolean {
    return startsWith("citation-resolve-") ||
        startsWith("trusted-source-approve-") ||
        startsWith("trusted-source-dismiss-") ||
        startsWith("trusted-source-list-") ||
        startsWith("trusted-source-revoke-")
}

private fun IndexDocumentsSummaryPayload.toRuntimeDocumentIndexSummary(): RuntimeDocumentIndexSummary {
    return RuntimeDocumentIndexSummary(
        documentCount = documentCount.coerceAtLeast(0),
        chunkCount = chunkCount.coerceAtLeast(0),
        extractedCharacterCount = extractedCharacterCount.coerceAtLeast(0),
        qualityCounts = RuntimeDocumentQualityCounts(
            noUsableText = qualityCounts.noUsableText.coerceAtLeast(0),
            singleChunk = qualityCounts.singleChunk.coerceAtLeast(0),
            chunked = qualityCounts.chunked.coerceAtLeast(0),
        ),
    )
}

private const val RUNTIME_DOCUMENT_QUALITY_NO_USABLE_TEXT = "no_usable_text"
private const val RUNTIME_DOCUMENT_QUALITY_SINGLE_CHUNK = "single_chunk"
private const val RUNTIME_DOCUMENT_QUALITY_CHUNKED = "chunked"
private const val MAX_RUNTIME_DOCUMENT_ID_LENGTH = 128
private const val MAX_RUNTIME_DOCUMENT_DISPLAY_NAME_LENGTH = 256
private const val MAX_RUNTIME_DOCUMENT_MIME_TYPE_LENGTH = 128
private const val MAX_RUNTIME_DOCUMENT_MATCHED_TERMS = 16
private const val MAX_RUNTIME_DOCUMENT_MATCHED_TERM_LENGTH = 64
private const val MAX_RUNTIME_DOCUMENT_TRANSIENT_SNIPPET_CHARACTERS = 480
private const val RUNTIME_DOCUMENT_FALLBACK_DISPLAY_NAME = "untitled-document"
private const val RUNTIME_DOCUMENT_UNKNOWN_MIME_TYPE = "application/octet-stream"
private val RUNTIME_DOCUMENT_MIME_TYPE_PATTERN = Regex("^[a-z0-9!#$%&'*+.^_`|~-]+/[a-z0-9!#$%&'*+.^_`|~-]+$")
private val RUNTIME_DOCUMENT_CONTENT_FINGERPRINT_PATTERN = Regex("^[0-9a-f]{16}$")
private val RUNTIME_SOURCE_ANCHOR_ID_PATTERN = Regex("^source_anchor_[0-9a-f]{16}$")

private fun canonicalRuntimeDocumentQualityForChunkCount(chunkCount: Int): String {
    return when {
        chunkCount <= 0 -> RUNTIME_DOCUMENT_QUALITY_NO_USABLE_TEXT
        chunkCount == 1 -> RUNTIME_DOCUMENT_QUALITY_SINGLE_CHUNK
        else -> RUNTIME_DOCUMENT_QUALITY_CHUNKED
    }
}

private fun String.canonicalRuntimeDocumentIdOrFallback(index: Int): String {
    val trimmed = trim()
    return trimmed.takeIf { value ->
        value.isNotBlank() &&
            value.length <= MAX_RUNTIME_DOCUMENT_ID_LENGTH &&
            value.none { character -> character.isISOControl() }
    } ?: "document_${index + 1}"
}

private fun String.canonicalRuntimeDocumentDisplayNameOrFallback(): String {
    val lastComponent = trim()
        .replace('\\', '/')
        .split('/')
        .lastOrNull { component -> component.isNotBlank() }
        ?.trim()
        .orEmpty()
    return lastComponent.takeIf { value ->
        value.isNotBlank() &&
            value != "." &&
            value != ".." &&
            value.length <= MAX_RUNTIME_DOCUMENT_DISPLAY_NAME_LENGTH &&
            value.none { character -> character.isISOControl() }
    } ?: RUNTIME_DOCUMENT_FALLBACK_DISPLAY_NAME
}

private fun String.canonicalRuntimeDocumentMimeTypeOrFallback(): String {
    return takeIf {
        it.length in 1..MAX_RUNTIME_DOCUMENT_MIME_TYPE_LENGTH &&
            RUNTIME_DOCUMENT_MIME_TYPE_PATTERN.matches(it)
    } ?: RUNTIME_DOCUMENT_UNKNOWN_MIME_TYPE
}

private fun List<String>.canonicalRuntimeDocumentMatchedTerms(): List<String> {
    return mapNotNull { term ->
        term.trim().takeIf { trimmed ->
            trimmed.isNotBlank() && trimmed.length <= MAX_RUNTIME_DOCUMENT_MATCHED_TERM_LENGTH
        }
    }.distinct().take(MAX_RUNTIME_DOCUMENT_MATCHED_TERMS)
}

private fun String.boundedRuntimeDocumentSnippet(): String {
    return take(MAX_RUNTIME_DOCUMENT_TRANSIENT_SNIPPET_CHARACTERS)
}

private fun String.canonicalRuntimeDocumentContentFingerprintOrEmpty(): String {
    return takeIf { RUNTIME_DOCUMENT_CONTENT_FINGERPRINT_PATTERN.matches(it) }.orEmpty()
}

private fun String.canonicalRuntimeSourceAnchorIdOrEmpty(): String {
    return takeIf { RUNTIME_SOURCE_ANCHOR_ID_PATTERN.matches(it) }.orEmpty()
}

private fun runtimeMemorySummaryDrafts(
    drafts: List<MemorySummaryDraftPayload>,
): List<RuntimeMemorySummaryDraft> {
    return drafts.mapNotNull { draft ->
        val id = draft.id.trim()
        val preview = draft.summaryPreview.trim()
        if (id.isBlank() || preview.isBlank()) return@mapNotNull null
        RuntimeMemorySummaryDraft(
            id = id,
            session = RuntimeMemorySummaryDraftSession(
                sessionId = draft.session.sessionId.trim(),
                title = draft.session.title.trim(),
                modelId = draft.session.model.trim(),
                lastActivityAtMillis = parseProtocolTimestampMillisOrNull(draft.session.lastActivityAt),
                messageCount = draft.session.messageCount.coerceAtLeast(0),
                inactiveSeconds = draft.session.inactiveSeconds.coerceAtLeast(0L),
            ),
            sourceMessageCount = draft.sourceMessageCount.coerceAtLeast(0),
            sourceRange = draft.sourceRange.trim(),
            sourcePointers = draft.sourcePointers.map { pointer ->
                RuntimeMemorySummaryDraftSourcePointer(
                    sessionId = pointer.sessionId.trim(),
                    messageIndex = pointer.messageIndex,
                    role = pointer.role.trim(),
                    createdAtMillis = pointer.createdAt?.let(::parseProtocolTimestampMillisOrNull),
                    excerpt = pointer.excerpt.trim(),
                )
            }.filter { it.excerpt.isNotBlank() },
            summaryPreview = preview,
            summaryMethod = draft.summaryMethod,
            generatedAtMillis = draft.generatedAt?.let(::parseProtocolTimestampMillisOrNull),
            generatedModelId = draft.generatedModelId?.trim()?.takeIf { it.isNotBlank() },
        )
    }
}

private fun RuntimeMemorySummaryDraft.hasSameMemorySummarySourceAs(
    expected: RuntimeMemorySummaryDraft,
): Boolean {
    return id == expected.id &&
        session == expected.session &&
        sourceMessageCount == expected.sourceMessageCount &&
        sourceRange == expected.sourceRange &&
        sourcePointers == expected.sourcePointers
}

private fun parseProtocolTimestampMillisOrNull(timestamp: String): Long? {
    return runCatching { Instant.parse(timestamp).toEpochMilli() }.getOrNull()
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

internal data class RetryLatestAssistantResponseCandidate(
    val contextMessages: List<RuntimeChatMessage>,
    val precedingUserMessage: RuntimeChatMessage,
)

internal fun retryLatestAssistantResponseCandidate(
    sourceState: RuntimeUiState,
): RetryLatestAssistantResponseCandidate? {
    if (sourceState.isStreaming) return null

    val latestAssistantIndex = sourceState.messages.indexOfLast {
        it.role == "assistant" && it.content.isNotBlank()
    }
    if (latestAssistantIndex < 0) return null
    val laterChatMessage = sourceState.messages
        .drop(latestAssistantIndex + 1)
        .any { (it.role == "user" || it.role == "assistant") && it.content.isNotBlank() }
    if (laterChatMessage) return null

    val precedingMessages = sourceState.messages.take(latestAssistantIndex)
    val precedingUserIndex = precedingMessages.indexOfLast {
        it.role == "user" && it.content.isNotBlank()
    }
    if (precedingUserIndex < 0) return null

    val contextMessages = precedingMessages.take(precedingUserIndex + 1)
    return RetryLatestAssistantResponseCandidate(
        contextMessages = contextMessages,
        precedingUserMessage = contextMessages[precedingUserIndex],
    )
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

internal fun runtimeModelResidencyStatus(payload: RuntimeHealthPayload): RuntimeModelResidencyStatus? {
    val residency = payload.modelResidency ?: return null
    return RuntimeModelResidencyStatus(
        supported = residency.supported,
        activeProvider = runtimeResidencySafeProvider(residency.activeProvider),
        activeModelId = runtimeResidencySafeModelId(residency.activeModelId),
        inFlightGenerations = residency.inFlightGenerations.coerceAtLeast(0),
        idleUnloadDelaySeconds = residency.idleUnloadDelaySeconds?.coerceAtLeast(0),
        lastUnloadFailure = runtimeResidencyUnloadFailureStatus(residency.lastUnloadFailure),
    )
}

internal fun runtimeProviderSafeMessage(message: String?): String {
    return message
        ?.trim()
        ?.takeUnless { it.containsBackendEndpointMaterial() }
        .orEmpty()
}

internal fun runtimeProviderSafeCode(code: String?): String? {
    return code
        ?.trim()
        ?.takeUnless { it.containsBackendEndpointMaterial() }
        ?.takeIf { it.matches(PROVIDER_DIAGNOSTIC_CODE_PATTERN) }
}

private fun runtimeResidencySafeProvider(provider: String?): String? {
    return provider
        ?.trim()
        ?.takeUnless { it.containsBackendEndpointMaterial() }
        ?.takeIf { it == "ollama" || it == "lm_studio" }
}

private fun runtimeResidencySafeModelId(modelID: String?): String? {
    return modelID
        ?.trim()
        ?.takeUnless { it.containsBackendEndpointMaterial() }
        ?.takeIf { it.isNotEmpty() && it.length <= 160 }
}

private fun runtimeResidencyUnloadFailureStatus(
    failure: RuntimeModelResidencyUnloadFailurePayload?,
): RuntimeModelResidencyUnloadFailureStatus? {
    failure ?: return null
    val provider = runtimeResidencySafeProvider(failure.provider) ?: return null
    val modelId = runtimeResidencySafeModelId(failure.modelId) ?: return null
    val reason = runtimeResidencySafeUnloadReason(failure.reason) ?: return null
    return RuntimeModelResidencyUnloadFailureStatus(
        provider = provider,
        modelId = modelId,
        reason = reason,
    )
}

private fun runtimeResidencySafeUnloadReason(reason: String?): String? {
    return reason
        ?.trim()
        ?.takeUnless { it.containsBackendEndpointMaterial() }
        ?.takeIf { it == "model_switch" || it == "idle_timeout" || it == "manual" }
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
            ?.takeUnless { trustedRuntime.hasRemoteRoute() }
            ?.takeUnless { it.source == RuntimeEndpointSource.TrustedLastKnown }
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
    if (state.trustedRuntime?.hasRemoteRoute() == true) return trustedTarget
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
        trustedRuntime.hasRemoteRoute() != true &&
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
    val hasSavedRemoteRoute = identity != null &&
        state.trustedRuntime
            ?.let { it.matchesIdentity(identity) && it.hasRemoteRoute() } == true
    if (identity != null) {
        if (!hasSavedRemoteRoute && !suppressDirectRoutes) state.selectedRouteEndpointHintOrNull()?.let { endpoint ->
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
        if (includeUsbReverseFallback && !hasSavedRemoteRoute && !suppressDirectRoutes) {
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
        if (!hasSavedRemoteRoute && !suppressDirectRoutes && endpoint.isAllowedDirectEndpoint() && seenEndpoints.add(key)) {
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
    if (advertisedRouteToken != null) {
        return targetRouteToken != null && advertisedRouteToken == targetRouteToken
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
            runtimeUiError("no_route", message)
        RuntimeConnectionFailureReason.NoConnectableRoute -> {
            if (hasExpiredRemoteRoute()) {
                runtimeUiError(
                    code = "remote_route_expired",
                    detail = message,
                    diagnosticCode = routeDiagnosticCode(),
                )
            } else if (hasMismatchedRemoteRoute() || hasUnavailableRemoteRoutePlaceholders()) {
                runtimeUiError(
                    code = "remote_routes_unavailable",
                    detail = message,
                    diagnosticCode = routeDiagnosticCode(),
                )
            } else {
                runtimeUiError(
                    code = "no_connectable_route",
                    detail = message,
                    diagnosticCode = routeDiagnosticCode(),
                )
            }
        }
        RuntimeConnectionFailureReason.RouteAttemptsFailed -> {
            val diagnosticCode = routeDiagnosticCode()
            runtimeUiError(
                code = if (diagnosticCode in REMOTE_ROUTE_UNREACHABLE_DIAGNOSTIC_CODES) {
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

private fun RuntimeConnectionFailure.hasMismatchedRemoteRoute(): Boolean {
    return routeRejections.any {
        it.reason == RuntimeRouteRejectionReason.RemoteRouteIdentityMismatch &&
            (it.capability == RuntimeRouteCapability.PeerToPeer || it.capability == RuntimeRouteCapability.Relay)
    }
}

private fun RuntimeConnectionFailure.routeDiagnosticCode(): String? {
    val hasMismatchedRemoteRoute = hasMismatchedRemoteRoute()
    val hasExpiredRemoteRoute = hasExpiredRemoteRoute()
    val hasUnpreparedLocalDirect = routeRejections.any {
        it.capability == RuntimeRouteCapability.DirectTcp &&
            it.reason == RuntimeRouteRejectionReason.DirectTcpEndpointNotPrepared
    }
    val hasFailedDirectEndpoint = attemptFailures.any {
        it.route is RuntimeRouteCandidate.DirectTcp
    }
    val hasFailedPeerToPeerRoute = attemptFailures.any {
        it.route is RuntimeRouteCandidate.PeerToPeer
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
        hasMismatchedRemoteRoute ->
            "route_diagnostic_remote_identity_mismatch"
        hasExpiredRemoteRoute ->
            "route_diagnostic_remote_route_expired"
        hasFailedRelayRoute ->
            "route_diagnostic_relay_failed"
        hasFailedPeerToPeerRoute && hasRelayPlaceholder ->
            "route_diagnostic_p2p_failed_relay_pending"
        hasFailedDirectEndpoint && hasPeerToPeerPlaceholder && hasRelayPlaceholder ->
            "route_diagnostic_direct_failed_remote_pending"
        hasUnpreparedLocalDirect && hasPeerToPeerPlaceholder && hasRelayPlaceholder ->
            "route_diagnostic_local_missing_remote_pending"
        hasPeerToPeerPlaceholder && hasRelayPlaceholder ->
            "route_diagnostic_remote_pending"
        else -> null
    }
}

private val REMOTE_ROUTE_UNREACHABLE_DIAGNOSTIC_CODES = setOf(
    "route_diagnostic_relay_failed",
    "route_diagnostic_p2p_failed_relay_pending",
)

private fun Throwable.connectionUiError(): RuntimeUiError {
    return when (this) {
        is RuntimeConnectionFailure -> toRuntimeUiError()
        else -> runtimeUiError("connection_failed", message)
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
    val hasRemoteRoute = payload.hasRemoteRoute()
    val endpoint = if (hasRemoteRoute) null else payload.endpointHintOrNull()
    return copy(
        pairingCode = payload.pairingCode,
        pendingPairingRuntimeName = payload.runtimeName,
        isPairingAwaitingRoute = endpoint == null && !hasRemoteRoute,
        runtimeHost = endpoint?.host ?: runtimeHost,
        runtimePort = endpoint?.port?.toString() ?: runtimePort,
        runtimeEndpointSource = endpoint?.source ?: runtimeEndpointSource,
        runtimeStatus = if (endpoint == null && !hasRemoteRoute) "pairing" else runtimeStatus,
        routeRefreshNoticeRuntimeName = null,
        error = null,
    )
}

internal fun RuntimeUiState.withClearedPendingPairing(): RuntimeUiState {
    return copy(
        pairingCode = "",
        pendingPairingRuntimeName = null,
        isPairingAwaitingRoute = false,
        runtimeStatus = if (runtimeStatus == "pairing") "disconnected" else runtimeStatus,
    )
}

internal fun RuntimeUiState.withTrustedRuntimeRouteFields(
    runtime: RuntimeTrustedRuntime,
    endpoint: RuntimeEndpointHint?,
): RuntimeUiState {
    val hasRemoteRoute = runtime.hasRemoteRoute()
    return copy(
        trustedRuntime = runtime,
        runtimeHost = if (hasRemoteRoute) "" else endpoint?.host ?: runtimeHost,
        runtimePort = if (hasRemoteRoute) "" else endpoint?.port?.toString() ?: runtimePort,
        runtimeEndpointSource = if (hasRemoteRoute) {
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
        relayTicketGeneration = null,
    )
}

private fun RuntimeTrustedRuntime.withoutRemoteRoutes(): RuntimeTrustedRuntime {
    return copy(
        relayHost = null,
        relayPort = null,
        relayId = null,
        relaySecret = null,
        relayExpiresAtEpochMillis = null,
        relayNonce = null,
        relayScope = null,
        relayTicketGeneration = null,
        p2pRouteClass = null,
        p2pRecordId = null,
        p2pEncryptedBody = null,
        p2pExpiresAtEpochMillis = null,
        p2pAntiReplayNonce = null,
        p2pProtocolVersion = null,
    )
}

private fun RuntimeTrustedRuntime.withoutInvalidatedRemoteRoute(error: RuntimeUiError): RuntimeTrustedRuntime {
    return if (error.isExpiredRemoteRouteError()) {
        withoutRemoteRoutes()
    } else {
        withoutRelayRoute()
    }
}

private fun RuntimeTrustedRuntime.toTrustedRuntimeOrNull(): TrustedRuntime? {
    val cleanFingerprint = fingerprint?.takeIf(String::isNotBlank) ?: return null
    return TrustedRuntime(
        deviceId = deviceId,
        name = name,
        fingerprint = cleanFingerprint,
        publicKeyBase64 = publicKeyBase64,
        routeToken = routeToken,
        host = null,
        port = null,
        relayHost = relayHost,
        relayPort = relayPort,
        relayId = relayId,
        relaySecret = relaySecret,
        relayExpiresAtEpochMillis = relayExpiresAtEpochMillis,
        relayNonce = relayNonce,
        relayScope = relayScope,
        relayTicketGeneration = relayTicketGeneration,
        p2pRouteClass = p2pRouteClass,
        p2pRecordId = p2pRecordId,
        p2pEncryptedBody = p2pEncryptedBody,
        p2pExpiresAtEpochMillis = p2pExpiresAtEpochMillis,
        p2pAntiReplayNonce = p2pAntiReplayNonce,
        p2pProtocolVersion = p2pProtocolVersion,
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

internal fun acceptedPairingCurrentEndpointHint(pending: RuntimePairingPayload): RuntimeEndpointHint? {
    return if (pending.hasRemoteRoute()) null else pending.endpointHintOrNull()
}

internal fun pairingRuntimeConnectionTarget(
    state: RuntimeUiState,
    payload: RuntimePairingPayload,
    allowUsbReverseFallback: Boolean = false,
): RuntimeConnectionTarget? {
    val endpoint = payload.endpointHintOrNull()
    if (payload.hasRemoteRoute()) return payload.toConnectionTarget(endpoint = null)
    if (endpoint != null) return payload.toConnectionTarget(endpoint)

    val identityOnlyTarget = payload.toConnectionTarget(endpoint = null)
    val identity = requireNotNull(identityOnlyTarget.identity)
    val discovered = state.discoveredRuntimes.firstOrNull { discovered ->
        discovered.matchesTrustedIdentity(identity, allowMissingMetadata = false)
    }
    if (discovered != null) {
        return identityOnlyTarget.copy(
            endpointHint = RuntimeEndpointHint(
                host = discovered.host,
                port = discovered.port,
                source = RuntimeEndpointSource.BonjourDiscovery,
            )
        )
    }
    if (allowUsbReverseFallback) {
        return identityOnlyTarget.copy(
            endpointHint = RuntimeEndpointHint(
                host = "127.0.0.1",
                port = 43170,
                source = RuntimeEndpointSource.UsbReverse,
            )
        )
    }
    return null
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

private fun initialPairingPublicKeyFingerprint(publicKeyBase64: String): String {
    val publicKeyBytes = Base64.getDecoder().decode(publicKeyBase64)
    require(Base64.getEncoder().encodeToString(publicKeyBytes) == publicKeyBase64) {
        "Device public key is not canonical Base64"
    }
    return MessageDigest.getInstance("SHA-256")
        .digest(publicKeyBytes)
        .joinToString("") { "%02x".format(it) }
}

private fun pairedRelayRouteTokenHash(routeToken: String): String {
    return MessageDigest.getInstance("SHA-256")
        .digest(routeToken.toByteArray(Charsets.UTF_8))
        .joinToString("") { "%02x".format(it) }
}

private fun RuntimeTrustedRuntime?.hasSameRelayAllocationRoute(other: TrustedRuntime?): Boolean {
    if (this == null || other == null) return this == null && other == null
    return deviceId == other.deviceId &&
        fingerprint == other.fingerprint &&
        routeToken == other.routeToken &&
        relayId == other.relayId &&
        relayExpiresAtEpochMillis == other.relayExpiresAtEpochMillis &&
        relayNonce == other.relayNonce &&
        relayTicketGeneration == other.relayTicketGeneration
}

private fun acceptedInitialPairingProofIsValid(
    pending: RuntimePairingPayload,
    pendingRequest: PendingInitialPairingRequest,
    payload: PairingResultPayload,
): Boolean {
    val runtimeDeviceId = payload.runtimeDeviceIdV2 ?: return false
    val runtimePublicKey = payload.runtimePublicKey ?: return false
    val runtimeKeyFingerprint = payload.runtimeKeyFingerprint ?: return false
    val trustedDeviceId = payload.trustedDeviceId ?: return false
    val pairingProofScheme = payload.pairingProofScheme ?: return false
    val pairingRequestDigest = payload.pairingRequestDigest ?: return false
    val runtimePairingSignature = payload.runtimePairingSignature ?: return false
    if (
        pairingProofScheme != INITIAL_PAIRING_PROOF_SCHEME ||
        pairingRequestDigest != pendingRequest.requestDigest ||
        runtimeDeviceId != pending.runtimeDeviceId ||
        runtimePublicKey != pending.runtimePublicKeyBase64 ||
        runtimeKeyFingerprint != pending.fingerprint ||
        trustedDeviceId != pendingRequest.clientDeviceId ||
        payload.transportBinding != pendingRequest.transportBinding
    ) {
        return false
    }

    val result = runCatching {
        InitialPairingAcceptedResult(
            scheme = pairingProofScheme,
            protocolVersion = 1,
            requestId = pendingRequest.requestId,
            pairingRequestDigest = pairingRequestDigest,
            accepted = true,
            runtimeDeviceId = runtimeDeviceId,
            runtimePublicKey = runtimePublicKey,
            runtimeKeyFingerprint = runtimeKeyFingerprint,
            trustedDeviceId = trustedDeviceId,
            message = payload.message,
            transportBinding = payload.transportBinding,
        )
    }.getOrNull() ?: return false

    return InitialPairingProof.verifyAcceptedResult(
        result = result,
        signatureBase64 = runtimePairingSignature,
        expectedRequestId = pendingRequest.requestId,
        expectedPairingRequestDigest = pendingRequest.requestDigest,
        expectedTrustedDeviceId = pendingRequest.clientDeviceId,
        expectedTransportBinding = pendingRequest.transportBinding,
    )
}

internal fun trustedRuntimeFromAcceptedPairing(
    pending: RuntimePairingPayload,
    payload: PairingResultPayload,
): TrustedRuntime? {
    if (pending.hasExpiredRemoteRoute()) return null
    val hasRelayRoute = pending.hasRelayRoute()
    val hasPeerToPeerRoute = pending.hasPeerToPeerRoute()
    if (!hasRelayRoute && pending.hasAnyRelayRouteMaterial()) return null
    if (!hasPeerToPeerRoute && pending.hasAnyPeerToPeerRouteMaterial()) return null
    val acceptedRuntimeDeviceId = payload.runtimeDeviceIdV2 ?: return null
    val acceptedFingerprint = payload.runtimeKeyFingerprint?.takeIf(String::isNotBlank) ?: return null
    val acceptedPublicKey = payload.runtimePublicKey?.takeIf(String::isNotBlank) ?: return null
    if (
        acceptedRuntimeDeviceId != pending.runtimeDeviceId ||
        acceptedFingerprint != pending.fingerprint ||
        pending.runtimePublicKeyBase64 == null ||
        acceptedPublicKey != pending.runtimePublicKeyBase64
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
        relayTicketGeneration = null,
        p2pRouteClass = if (hasPeerToPeerRoute) pending.p2pRouteClass else null,
        p2pRecordId = if (hasPeerToPeerRoute) pending.p2pRecordId else null,
        p2pEncryptedBody = if (hasPeerToPeerRoute) pending.p2pEncryptedBody else null,
        p2pExpiresAtEpochMillis = if (hasPeerToPeerRoute) pending.p2pExpiresAtEpochMillis else null,
        p2pAntiReplayNonce = if (hasPeerToPeerRoute) pending.p2pAntiReplayNonce else null,
        p2pProtocolVersion = if (hasPeerToPeerRoute) pending.p2pProtocolVersion else null,
    )
}

internal fun trustedRuntimeFromRouteRefreshQr(
    current: RuntimeTrustedRuntime?,
    payload: RuntimePairingPayload,
    nowEpochMillis: Long = System.currentTimeMillis(),
): TrustedRuntime? {
    current ?: return null
    if (payload.hasExpiredRemoteRoute(nowEpochMillis)) return null
    val hasRelayRoute = payload.hasRelayRoute(nowEpochMillis)
    val hasPeerToPeerRoute = payload.hasPeerToPeerRoute(nowEpochMillis)
    if (!payload.hasRemoteRoute(nowEpochMillis)) return null
    if (!hasRelayRoute && payload.relayScope != null) return null
    if (!hasRelayRoute && payload.hasAnyRelayRouteMaterial()) return null
    if (!hasPeerToPeerRoute && payload.hasAnyPeerToPeerRouteMaterial()) return null
    if (hasRelayRoute && !payload.isFreshRelayRouteRefreshQr(current, nowEpochMillis)) {
        return null
    }
    if (hasPeerToPeerRoute && !payload.isFreshPeerToPeerRouteRefreshQr(current, nowEpochMillis)) {
        return null
    }
    if (current.deviceId != payload.runtimeDeviceId) return null
    if (current.fingerprint != null && current.fingerprint != payload.fingerprint) return null
    if (!runtimePublicKeyMatches(current.publicKeyBase64, payload.runtimePublicKeyBase64)) {
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
        relayTicketGeneration = null,
        p2pRouteClass = if (hasPeerToPeerRoute) payload.p2pRouteClass else null,
        p2pRecordId = if (hasPeerToPeerRoute) payload.p2pRecordId else null,
        p2pEncryptedBody = if (hasPeerToPeerRoute) payload.p2pEncryptedBody else null,
        p2pExpiresAtEpochMillis = if (hasPeerToPeerRoute) payload.p2pExpiresAtEpochMillis else null,
        p2pAntiReplayNonce = if (hasPeerToPeerRoute) payload.p2pAntiReplayNonce else null,
        p2pProtocolVersion = if (hasPeerToPeerRoute) payload.p2pProtocolVersion else null,
    )
}

private fun RuntimePairingPayload.isFreshRelayRouteRefreshQr(
    current: RuntimeTrustedRuntime,
    nowEpochMillis: Long,
): Boolean {
    if (!current.hasRelayRoute(nowEpochMillis)) return true
    if (relayNonce != null && relayNonce == current.relayNonce) return false
    val currentExpiry = current.relayExpiresAtEpochMillis ?: return true
    val refreshedExpiry = relayExpiresAtEpochMillis ?: return true
    return refreshedExpiry > currentExpiry
}

private fun RuntimePairingPayload.isFreshPeerToPeerRouteRefreshQr(
    current: RuntimeTrustedRuntime,
    nowEpochMillis: Long,
): Boolean {
    if (!current.hasPeerToPeerRoute(nowEpochMillis)) return true
    if (p2pRecordId != null && p2pRecordId == current.p2pRecordId) return false
    if (p2pAntiReplayNonce != null && p2pAntiReplayNonce == current.p2pAntiReplayNonce) return false
    val currentExpiry = current.p2pExpiresAtEpochMillis ?: return true
    val refreshedExpiry = p2pExpiresAtEpochMillis ?: return true
    return refreshedExpiry > currentExpiry
}

internal fun trustedRuntimeFromRouteRefreshPayload(
    current: RuntimeTrustedRuntime?,
    payload: RouteRefreshPayload,
    nowEpochMillis: Long = System.currentTimeMillis(),
): TrustedRuntime? {
    current ?: return null
    val fingerprint = current.fingerprint ?: return null
    if (!isCanonicalOpaqueRouteValue(payload.runtimeDeviceId)) return null
    if (!isCanonicalOpaqueRouteValue(payload.runtimeKeyFingerprint)) return null
    if (payload.runtimeDeviceId != current.deviceId) return null
    if (payload.runtimeKeyFingerprint != fingerprint) return null
    val hasRelayMaterial = payload.hasAnyRouteRefreshRelayMaterial()
    val hasPeerToPeerMaterial = payload.hasAnyRouteRefreshPeerToPeerMaterial()
    if (!hasRelayMaterial && !hasPeerToPeerMaterial) return null
    if (hasRelayMaterial && !payload.isFreshRelayRouteRefresh(current, nowEpochMillis)) {
        return null
    }
    if (hasPeerToPeerMaterial && !payload.isFreshPeerToPeerRouteRefresh(current, nowEpochMillis)) {
        return null
    }
    val relayScope = payload.validatedRouteRefreshRelayScopeOrNull()
        ?: run {
            if (payload.relayScope == null) null else return null
        }
    val candidateRuntime = current.copy(
        endpointHint = null,
        relayHost = if (hasRelayMaterial) payload.relayHost else null,
        relayPort = if (hasRelayMaterial) payload.relayPort else null,
        relayId = if (hasRelayMaterial) payload.relayId else null,
        relaySecret = if (hasRelayMaterial) payload.relaySecret else null,
        relayExpiresAtEpochMillis = if (hasRelayMaterial) payload.relayExpiresAtEpochMillis else null,
        relayNonce = if (hasRelayMaterial) payload.relayNonce else null,
        relayScope = if (hasRelayMaterial) relayScope else null,
        relayTicketGeneration = if (hasRelayMaterial) payload.ticketGeneration else null,
        p2pRouteClass = if (hasPeerToPeerMaterial) payload.p2pRouteClass else null,
        p2pRecordId = if (hasPeerToPeerMaterial) payload.p2pRecordId else null,
        p2pEncryptedBody = if (hasPeerToPeerMaterial) payload.p2pEncryptedBody else null,
        p2pExpiresAtEpochMillis = if (hasPeerToPeerMaterial) payload.p2pExpiresAtEpochMillis else null,
        p2pAntiReplayNonce = if (hasPeerToPeerMaterial) payload.p2pAntiReplayNonce else null,
        p2pProtocolVersion = if (hasPeerToPeerMaterial) payload.p2pProtocolVersion else null,
    )
    if (hasRelayMaterial && !candidateRuntime.hasRelayRoute(nowEpochMillis)) return null
    if (hasPeerToPeerMaterial && !candidateRuntime.hasPeerToPeerRoute(nowEpochMillis)) return null
    if (!candidateRuntime.hasRemoteRoute(nowEpochMillis)) return null
    return TrustedRuntime(
        deviceId = current.deviceId,
        name = current.name,
        fingerprint = fingerprint,
        publicKeyBase64 = current.publicKeyBase64,
        routeToken = current.routeToken,
        host = null,
        port = null,
        relayHost = if (hasRelayMaterial) payload.relayHost else null,
        relayPort = if (hasRelayMaterial) payload.relayPort else null,
        relayId = if (hasRelayMaterial) payload.relayId else null,
        relaySecret = if (hasRelayMaterial) payload.relaySecret else null,
        relayExpiresAtEpochMillis = if (hasRelayMaterial) payload.relayExpiresAtEpochMillis else null,
        relayNonce = if (hasRelayMaterial) payload.relayNonce else null,
        relayScope = if (hasRelayMaterial) relayScope else null,
        relayTicketGeneration = if (hasRelayMaterial) payload.ticketGeneration else null,
        p2pRouteClass = if (hasPeerToPeerMaterial) payload.p2pRouteClass else null,
        p2pRecordId = if (hasPeerToPeerMaterial) payload.p2pRecordId else null,
        p2pEncryptedBody = if (hasPeerToPeerMaterial) payload.p2pEncryptedBody else null,
        p2pExpiresAtEpochMillis = if (hasPeerToPeerMaterial) payload.p2pExpiresAtEpochMillis else null,
        p2pAntiReplayNonce = if (hasPeerToPeerMaterial) payload.p2pAntiReplayNonce else null,
        p2pProtocolVersion = if (hasPeerToPeerMaterial) payload.p2pProtocolVersion else null,
    )
}

private fun RouteRefreshPayload.isFreshRelayRouteRefresh(
    current: RuntimeTrustedRuntime,
    nowEpochMillis: Long,
): Boolean {
    if (!current.hasRelayRoute(nowEpochMillis)) return true
    if (payloadRelayNonceReusesCurrent(current)) return false
    val currentExpiry = current.relayExpiresAtEpochMillis ?: return true
    val refreshedExpiry = relayExpiresAtEpochMillis ?: return true
    return refreshedExpiry > currentExpiry
}

private fun RouteRefreshPayload.payloadRelayNonceReusesCurrent(
    current: RuntimeTrustedRuntime,
): Boolean {
    return relayNonce != null && relayNonce == current.relayNonce
}

private fun RouteRefreshPayload.isFreshPeerToPeerRouteRefresh(
    current: RuntimeTrustedRuntime,
    nowEpochMillis: Long,
): Boolean {
    if (!current.hasPeerToPeerRoute(nowEpochMillis)) return true
    if (payloadP2pRecordIdReusesCurrent(current)) return false
    if (payloadP2pNonceReusesCurrent(current)) return false
    val currentExpiry = current.p2pExpiresAtEpochMillis ?: return true
    val refreshedExpiry = p2pExpiresAtEpochMillis ?: return true
    return refreshedExpiry > currentExpiry
}

private fun RouteRefreshPayload.payloadP2pRecordIdReusesCurrent(
    current: RuntimeTrustedRuntime,
): Boolean {
    return p2pRecordId != null && p2pRecordId == current.p2pRecordId
}

private fun RouteRefreshPayload.payloadP2pNonceReusesCurrent(
    current: RuntimeTrustedRuntime,
): Boolean {
    return p2pAntiReplayNonce != null && p2pAntiReplayNonce == current.p2pAntiReplayNonce
}

private val ROUTE_REFRESH_RELAY_SCOPES = setOf("remote", "private_overlay", "usb_reverse")

private fun RouteRefreshPayload.validatedRouteRefreshRelayScopeOrNull(): String? {
    val rawScope = relayScope ?: return null
    return rawScope.takeIf { it in ROUTE_REFRESH_RELAY_SCOPES }
}

private fun RouteRefreshPayload.hasAnyRouteRefreshRelayMaterial(): Boolean {
    return relayHost != null ||
        relayPort != null ||
        relayId != null ||
        relaySecret != null ||
        relayExpiresAtEpochMillis != null ||
        relayNonce != null ||
        relayScope != null ||
        ticketGeneration != null
}

private fun RouteRefreshPayload.hasAnyRouteRefreshPeerToPeerMaterial(): Boolean {
    return p2pRouteClass != null ||
        p2pRecordId != null ||
        p2pEncryptedBody != null ||
        p2pExpiresAtEpochMillis != null ||
        p2pAntiReplayNonce != null ||
        p2pProtocolVersion != null
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
    requireRemoteRoute: Boolean = false,
): RuntimePairingQrParseResult {
    val payload = runCatching {
        RuntimePairingPayloadParser.parse(
            rawValue = rawValue,
            allowDebugLoopbackRelay = allowDebugLoopbackRelay,
            allowDiagnosticLocalDirectEndpoint = allowDiagnosticLocalDirectEndpoint && !requireRemoteRoute,
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
    if (requireRemoteRoute && !payload.hasProductionQrBootstrap()) {
        return RuntimePairingQrParseResult.Rejected(
            error = RuntimeUiError(
                code = "pairing_endpoint_unavailable",
                diagnosticCode = "route_diagnostic_remote_pending",
            ),
        )
    }
    return RuntimePairingQrParseResult.Accepted(payload)
}

internal fun RuntimePairingPayload.hasProductionQrBootstrap(): Boolean {
    return !runtimePublicKeyBase64.isNullOrBlank() &&
        !routeToken.isNullOrBlank() &&
        hasRemoteRoute()
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
    allowUsbReverseFallback: Boolean = false,
): PendingPairingConnectionPlan {
    val pendingState = state.withPendingPairing(payload)
    return PendingPairingConnectionPlan(
        pendingState = pendingState,
        target = pairingRuntimeConnectionTarget(
            state = pendingState,
            payload = payload,
            allowUsbReverseFallback = allowUsbReverseFallback,
        ),
        shouldStartDiscovery = payload.shouldWaitForDiscoveryRoute(),
        shouldWaitForDiscoveryRoute = payload.shouldWaitForDiscoveryRoute(),
    )
}

internal fun RuntimePairingPayload.shouldWaitForDiscoveryRoute(): Boolean {
    return endpointHintOrNull() == null && !hasRemoteRoute()
}

internal fun pendingPairingExhaustedRouteError(payload: RuntimePairingPayload): RuntimeUiError {
    return if (payload.hasRemoteRoute()) {
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
            diagnosticCode = "route_diagnostic_direct_qr_rejected",
            technicalDetail = error.message,
        )
        RELAY_HOST_UNREACHABLE_QR_ERROR -> RuntimeUiError(
            code = "pairing_relay_route_rejected",
            diagnosticCode = "route_diagnostic_relay_qr_unreachable",
            technicalDetail = error.message,
        )
        PRIVATE_OVERLAY_RELAY_SCOPE_REQUIRED_QR_ERROR -> RuntimeUiError(
            code = "pairing_relay_route_rejected",
            diagnosticCode = "route_diagnostic_private_overlay_scope_required",
            technicalDetail = error.message,
        )
        else -> runtimeUiError("invalid_pairing_qr", error.message)
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
        relayTicketGeneration = relayTicketGeneration,
        p2pRouteClass = p2pRouteClass,
        p2pRecordId = p2pRecordId,
        p2pEncryptedBody = p2pEncryptedBody,
        p2pExpiresAtEpochMillis = p2pExpiresAtEpochMillis,
        p2pAntiReplayNonce = p2pAntiReplayNonce,
        p2pProtocolVersion = p2pProtocolVersion,
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
        !isCanonicalProviderQualifiedModelId(currentSelectedEmbeddingModelId) -> null
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
    )
}

internal fun RuntimeUiState.withChatDone(
    envelope: ProtocolEnvelope,
    payload: ChatDonePayload,
    assistantMessageId: String? = null,
): RuntimeUiState {
    if (activeRequestId != envelope.requestId) return this
    return copy(
        messages = messages
            .withClosedTrailingAssistantReasoning()
            .withTrailingAssistantSourceAttributions(payload.sourceAttributions, assistantMessageId)
            .withoutTrailingBlankAssistantPlaceholder(),
        isStreaming = false,
        activeRequestId = null,
        error = if (payload.finishReason == "cancelled") RuntimeUiError("generation_cancelled") else error,
    )
}

private fun List<RuntimeChatMessage>.withTrailingAssistantSourceAttributions(
    sourceAttributions: List<ChatSourceAttributionPayload>,
    assistantMessageId: String?,
): List<RuntimeChatMessage> {
    val trailingMessage = lastOrNull()?.takeIf { it.role == "assistant" } ?: return this
    return dropLast(1) + trailingMessage.copy(
        sourceAttributions = sourceAttributions.map { attribution ->
            RuntimeChatSourceAttribution(
                sourceIndex = attribution.sourceIndex,
                documentName = attribution.documentName,
                mimeType = attribution.mimeType,
                chunkIndex = attribution.chunkIndex,
            )
        },
        assistantMessageId = assistantMessageId?.takeIf { sourceAttributions.isNotEmpty() },
    )
}

private fun List<RuntimeChatMessage>.withoutTrailingAssistantSourceAttributions(): List<RuntimeChatMessage> {
    val trailingMessage = lastOrNull()
    if (trailingMessage?.role != "assistant" || trailingMessage.sourceAttributions.isEmpty()) return this
    return dropLast(1) + trailingMessage.copy(
        sourceAttributions = emptyList(),
        assistantMessageId = null,
    )
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
        messages = messages
            .withoutTrailingAssistantSourceAttributions()
            .withClosedTrailingAssistantReasoning()
            .withoutTrailingBlankAssistantPlaceholder(),
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
    val runtimeError = payload?.let { error -> runtimeUiError(error.code, error.message) }
        ?: RuntimeUiError("runtime_error")
    val updated = copy(
        messages = if (isActiveChatError) {
            messages
                .withoutTrailingAssistantSourceAttributions()
                .withClosedTrailingAssistantReasoning()
                .withoutTrailingBlankAssistantPlaceholder()
        } else {
            messages
        },
        isStreaming = if (isActiveChatError) false else isStreaming,
        activeRequestId = if (isActiveChatError) null else activeRequestId,
        isLoadingModels = false,
        installingModelId = if (isModelPullError) null else installingModelId,
        error = runtimeError,
    )
    return if (runtimeError.code.isPairingRequiredRuntimeCode()) {
        updated.withPairingRequiredRuntimeState(detail = runtimeError.technicalDetail ?: runtimeError.detail)
    } else {
        updated
    }
}

internal fun RuntimeUiState.runtimeReceiveFailureUiError(error: Throwable): RuntimeUiError {
    if (activeRouteKind == RuntimeActiveRouteKind.Relay && error.isRelayFrameAuthenticationFailure()) {
        return RuntimeUiError(
            code = "remote_route_auth_failed",
            diagnosticCode = "route_diagnostic_relay_auth_failed",
            technicalDetail = error.message,
        )
    }
    return runtimeUiError("receive_failed", error.message)
}

internal fun RuntimeUiState.withRuntimeReceiveFailure(detail: String?): RuntimeUiState =
    withRuntimeReceiveFailure(runtimeUiError("receive_failed", detail))

internal fun RuntimeUiState.withRuntimeReceiveFailure(error: RuntimeUiError): RuntimeUiState {
    return copy(
        isConnected = false,
        isStreaming = false,
        installingModelId = null,
        activeRequestId = null,
        documentCatalog = RuntimeDocumentCatalog(),
        isLoadingDocumentCatalog = false,
        documentSearchQuery = "",
        documentSearchResults = emptyList(),
        isSearchingDocuments = false,
        runtimeStatus = "disconnected",
        activeRouteKind = null,
        messages = if (activeRequestId != null) {
            messages
                .withoutTrailingAssistantSourceAttributions()
                .withClosedTrailingAssistantReasoning()
                .withoutTrailingBlankAssistantPlaceholder()
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
        this?.code == "remote_route_unreachable_from_device" ||
        this?.code == "remote_route_unreachable" ||
        this?.code == "remote_route_expired" ||
        this?.diagnosticCode == "route_diagnostic_relay_auth_failed" ||
        this?.diagnosticCode == "route_diagnostic_relay_unreachable_from_device" ||
        this?.diagnosticCode == "route_diagnostic_relay_failed" ||
        this?.diagnosticCode == "route_diagnostic_remote_route_expired"
}

private fun RuntimeUiError?.invalidatesStoredRemoteRoute(): Boolean {
    return this?.code == "remote_route_auth_failed" ||
        this?.code == "remote_route_expired" ||
        this?.diagnosticCode == "route_diagnostic_relay_auth_failed" ||
        this?.diagnosticCode == "route_diagnostic_remote_route_expired"
}

private fun RuntimeUiError.isExpiredRemoteRouteError(): Boolean {
    return code == "remote_route_expired" ||
        diagnosticCode == "route_diagnostic_remote_route_expired"
}

internal fun RuntimeUiState.withPairingRequiredRuntimeState(detail: String?): RuntimeUiState {
    return copy(
        isConnected = false,
        isConnecting = false,
        isStreaming = false,
        isLoadingModels = false,
        installingModelId = null,
        activeRequestId = null,
        runtimeStatus = "pairing_required",
        backendAvailable = null,
        backendCode = null,
        providerStatuses = emptyList(),
        modelResidency = null,
        error = runtimeUiError("pairing_required", detail),
    )
}

internal fun runtimeUiError(
    code: String,
    detail: String? = null,
    diagnosticCode: String? = null,
): RuntimeUiError {
    return RuntimeUiError(
        code = code,
        detail = detail.takeIf { code in USER_VISIBLE_RUNTIME_ERROR_DETAIL_CODES },
        diagnosticCode = diagnosticCode,
        technicalDetail = detail.takeUnless { code in USER_VISIBLE_RUNTIME_ERROR_DETAIL_CODES },
    )
}

private val USER_VISIBLE_RUNTIME_ERROR_DETAIL_CODES = setOf(
    "attachment_too_large",
    "attachment_read_failed",
)

private fun ErrorPayload.withoutRouteRefreshSensitiveDetail(): ErrorPayload {
    return copy(message = ROUTE_REFRESH_PAIRING_REQUIRED_DETAIL)
}

private const val ROUTE_REFRESH_PAIRING_REQUIRED_DETAIL = "Route refresh requires pairing again."

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

private fun List<RuntimeChatMessage>.withClosedTrailingAssistantReasoning(): List<RuntimeChatMessage> {
    val trailingMessage = lastOrNull()
    if (
        trailingMessage?.role != "assistant" ||
        (!trailingMessage.isReasoningOpen && trailingMessage.inlineReasoningPendingTag.isBlank())
    ) {
        return this
    }
    return dropLast(1) + trailingMessage.copy(
        isReasoningOpen = false,
        inlineReasoningPendingTag = "",
    )
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
private const val PRIVATE_OVERLAY_RELAY_SCOPE_REQUIRED_QR_ERROR =
    "Private relay hosts require relay_scope=private_overlay"
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
