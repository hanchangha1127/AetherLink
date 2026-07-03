package com.localagentbridge.android.runtime

import android.content.Context
import com.localagentbridge.android.core.protocol.ChatAttachmentPayload
import com.localagentbridge.android.core.protocol.ChatMessagePayload
import com.localagentbridge.android.core.protocol.ChatSessionLifecyclePayload
import com.localagentbridge.android.core.protocol.ChatSessionSummaryPayload
import com.localagentbridge.android.core.protocol.ChatStoredMessagePayload
import com.localagentbridge.android.core.protocol.MemoryEntryPayload
import com.localagentbridge.android.core.protocol.MemoryEntrySourcePayload
import com.localagentbridge.android.core.pairing.AndroidKeystoreRelaySecretStore
import com.localagentbridge.android.core.pairing.OPAQUE_ROUTE_BODY_MAX_CHARS
import com.localagentbridge.android.core.pairing.RelaySecretStore
import com.localagentbridge.android.core.pairing.RuntimePairingPayload
import com.localagentbridge.android.core.pairing.isCanonicalOpaqueRouteValue
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerializationException
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID

private const val STORE_NAME = "runtime_local_store"
private const val STORE_KEY = "runtime_data"
private const val SUPPRESSED_REASON_DELETED = "deleted"
private const val MAX_PERSISTED_COMPOSER_DRAFT_CHARS = 20_000
internal const val APP_LANGUAGE_SOURCE_DEFAULT = "default"
internal const val APP_LANGUAGE_SOURCE_SYSTEM = "system"
internal const val APP_LANGUAGE_SOURCE_IN_APP = "in_app"

class RuntimeLocalStore(
    context: Context,
    private val json: Json,
    private val relaySecretStore: RelaySecretStore = AndroidKeystoreRelaySecretStore(context),
) {
    private val preferences = context.getSharedPreferences(STORE_NAME, Context.MODE_PRIVATE)

    fun load(): PersistedRuntimeData {
        val raw = preferences.getString(STORE_KEY, null) ?: return PersistedRuntimeData()
        return try {
            json.decodeFromString<PersistedRuntimeData>(raw)
                .sanitized()
                .withoutRuntimeOwnedLocalData()
                .withLoadedPendingPairingRelaySecret(relaySecretStore)
        } catch (_: SerializationException) {
            PersistedRuntimeData()
        } catch (_: IllegalArgumentException) {
            PersistedRuntimeData()
        }
    }

    fun save(data: PersistedRuntimeData) {
        val previousPendingSecretRef = preferences.getString(STORE_KEY, null)
            ?.let { raw ->
                runCatching { json.decodeFromString<PersistedRuntimeData>(raw) }.getOrNull()
            }
            ?.pendingPairingRoute
            ?.relaySecretRef
        val dataForDisk = data.withStoredPendingPairingRelaySecret(relaySecretStore)
        val currentPendingSecretRef = dataForDisk.pendingPairingRoute?.relaySecretRef
        if (previousPendingSecretRef != null && previousPendingSecretRef != currentPendingSecretRef) {
            relaySecretStore.removeSecret(previousPendingSecretRef)
        }
        preferences.edit()
            .putString(
                STORE_KEY,
                json.encodeToString(dataForDisk.sanitized().withoutRuntimeOwnedLocalData()),
            )
            .apply()
    }
}

@Serializable
data class PersistedRuntimeData(
    val version: Int = 1,
    val activeSessionId: String? = null,
    val selectedModelId: String? = null,
    val selectedEmbeddingModelId: String? = null,
    val composerDraft: String = "",
    val trustedRuntimeAutoReconnectEnabled: Boolean = true,
    val pairingOnboardingCompleted: Boolean = false,
    val sessions: List<PersistedChatSession> = emptyList(),
    val suppressedRuntimeSessions: List<PersistedSuppressedRuntimeSession> = emptyList(),
    val memoryEntries: List<PersistedMemoryEntry> = emptyList(),
    val appLanguageTag: String = RuntimeAppLanguage.English.languageTag,
    val appLanguageSource: String? = APP_LANGUAGE_SOURCE_DEFAULT,
    val appTheme: String = RuntimeAppTheme.System.storageValue,
    val pendingPairingRoute: PersistedPendingPairingRoute? = null,
)

@Serializable
data class PersistedChatSession(
    val id: String,
    val title: String,
    val modelId: String? = null,
    val composerDraft: String = "",
    val createdAtMillis: Long,
    val updatedAtMillis: Long,
    val archivedAtMillis: Long? = null,
    val titleManuallyEdited: Boolean = false,
    val titleGenerated: Boolean = false,
    val runtimeOwned: Boolean = false,
    val runtimeMessageCount: Int? = null,
    val lastEvent: String? = null,
    val lastFinishReason: String? = null,
    val lastErrorCode: String? = null,
    val runtimeSearchRank: Int? = null,
    val runtimeSearchSnippet: String? = null,
    val runtimeSearchMatchedFields: List<String> = emptyList(),
    val messages: List<PersistedChatMessage> = emptyList(),
)

@Serializable
data class PersistedChatMessage(
    val id: String,
    val role: String,
    val content: String,
    val reasoning: String = "",
    val attachments: List<PersistedMessageAttachment> = emptyList(),
    val createdAtMillis: Long,
)

@Serializable
data class PersistedMessageAttachment(
    val id: String,
    val type: String,
    val name: String,
    val mimeType: String,
    val text: String? = null,
)

@Serializable
data class PersistedSuppressedRuntimeSession(
    val sessionId: String,
    val reason: String,
    val updatedAtMillis: Long,
)

@Serializable
data class PersistedMemoryEntry(
    val id: String,
    val content: String,
    val enabled: Boolean = true,
    val createdAtMillis: Long,
    val updatedAtMillis: Long,
    val source: PersistedMemoryEntrySource? = null,
    val runtimeSearchRank: Int? = null,
    val runtimeSearchSnippet: String? = null,
    val runtimeSearchMatchedFields: List<String> = emptyList(),
)

@Serializable
data class PersistedMemoryEntrySource(
    val kind: String,
    val draftId: String,
    val summaryMethod: String,
    val session: PersistedMemoryEntrySourceSession,
    val sourceMessageCount: Int,
    val sourceRange: String,
    val sourcePointers: List<PersistedMemoryEntrySourcePointer>,
)

@Serializable
data class PersistedMemoryEntrySourceSession(
    val sessionId: String,
    val title: String,
    val modelId: String,
    val lastActivityAtMillis: Long?,
    val messageCount: Int,
    val inactiveSeconds: Long,
)

@Serializable
data class PersistedMemoryEntrySourcePointer(
    val sessionId: String,
    val messageIndex: Int,
    val role: String,
    val createdAtMillis: Long?,
    val excerpt: String,
)

@Serializable
data class PersistedPendingPairingRoute(
    val pairingNonce: String,
    val pairingCode: String,
    val runtimeDeviceId: String,
    val runtimeName: String,
    val fingerprint: String,
    val runtimePublicKeyBase64: String? = null,
    val routeToken: String? = null,
    val host: String? = null,
    val port: Int? = null,
    val relayHost: String? = null,
    val relayPort: Int? = null,
    val relayId: String? = null,
    val relaySecret: String? = null,
    val relaySecretRef: String? = null,
    val relayExpiresAtEpochMillis: Long? = null,
    val relayNonce: String? = null,
    val relayScope: String? = null,
    val p2pRouteClass: String? = null,
    val p2pRecordId: String? = null,
    val p2pEncryptedBody: String? = null,
    val p2pExpiresAtEpochMillis: Long? = null,
    val p2pAntiReplayNonce: String? = null,
    val p2pProtocolVersion: Int? = null,
    val serviceType: String? = null,
    val capturedAtEpochMillis: Long,
    val expiresAtEpochMillis: Long,
)

internal fun PersistedRuntimeData.sanitized(): PersistedRuntimeData {
    val cleanAppLanguageTag = RuntimeAppLanguage.normalizeLanguageTag(appLanguageTag)
    val cleanAppLanguageSource = when (appLanguageSource?.trim()) {
        APP_LANGUAGE_SOURCE_DEFAULT,
        APP_LANGUAGE_SOURCE_SYSTEM,
        APP_LANGUAGE_SOURCE_IN_APP -> appLanguageSource.trim()
        else -> {
            if (cleanAppLanguageTag == RuntimeAppLanguage.English.languageTag) {
                APP_LANGUAGE_SOURCE_DEFAULT
            } else {
                APP_LANGUAGE_SOURCE_IN_APP
            }
        }
    }
    val cleanSessions = sessions
        .filter { it.id.isNotBlank() }
        .distinctBy { it.id }
        .map { session ->
            val fallbackTitle = titleForMessages(session.messages.map { it.toRuntimeChatMessage() })
            val cleanTitle = session.title.trim().takeIf(String::isNotBlank) ?: DEFAULT_CHAT_TITLE
            val migratedTitle = when {
                cleanTitle == LEGACY_DEFAULT_CHAT_TITLE &&
                    !session.titleManuallyEdited &&
                    !session.titleGenerated -> DEFAULT_CHAT_TITLE
                session.hasLegacyPromptTitle(cleanTitle, fallbackTitle) -> DEFAULT_CHAT_TITLE
                else -> cleanTitle
            }
                session.copy(
                    title = migratedTitle,
                    modelId = session.modelId?.trim()?.takeIf(String::isNotBlank),
                    composerDraft = if (session.archivedAtMillis == null) {
                        session.composerDraft.take(MAX_PERSISTED_COMPOSER_DRAFT_CHARS)
                    } else {
                        ""
                    },
                    titleManuallyEdited = session.titleManuallyEdited ||
                    (
                        !session.runtimeOwned &&
                            !session.titleGenerated &&
                            migratedTitle != DEFAULT_CHAT_TITLE &&
                            migratedTitle != fallbackTitle
                    ),
                    runtimeSearchRank = session.runtimeSearchRank?.takeIf { it > 0 },
                    runtimeSearchSnippet = session.runtimeSearchSnippet?.trim()?.takeIf(String::isNotBlank),
                    runtimeSearchMatchedFields = session.runtimeSearchMatchedFields
                        .mapNotNull { it.trim().takeIf(String::isNotBlank) }
                        .distinct(),
                messages = session.messages
                    .filter { it.role in CHAT_STORAGE_ROLES }
                    .map { it.withCleanAttachments() },
            )
        }
    val cleanMemory = memoryEntries
        .map {
            it.copy(
                id = it.id.trim(),
                content = it.content.trim(),
                source = it.source?.sanitizedOrNull(),
                runtimeSearchRank = it.runtimeSearchRank?.takeIf { rank -> rank > 0 },
                runtimeSearchSnippet = it.runtimeSearchSnippet?.trim()?.takeIf(String::isNotBlank),
                runtimeSearchMatchedFields = it.runtimeSearchMatchedFields
                    .mapNotNull { field -> field.trim().takeIf(String::isNotBlank) }
                    .distinct(),
            )
        }
        .filter { it.id.isNotBlank() && it.content.isNotBlank() }
        .distinctBy { it.id }
    val cleanSuppressedRuntimeSessions = suppressedRuntimeSessions
        .mapNotNull { suppression ->
            val sessionId = suppression.sessionId.trim()
            val reason = suppression.reason.trim().takeIf(String::isNotBlank) ?: SUPPRESSED_REASON_DELETED
            if (sessionId.isBlank()) {
                null
            } else {
                suppression.copy(sessionId = sessionId, reason = reason)
            }
        }
        .distinctBy { it.sessionId }
    return copy(
        activeSessionId = activeSessionId?.takeIf { id ->
            cleanSessions.any { it.id == id && it.archivedAtMillis == null }
        },
        selectedModelId = selectedModelId?.trim()?.takeIf(String::isNotBlank),
        selectedEmbeddingModelId = selectedEmbeddingModelId?.trim()?.takeIf(String::isNotBlank),
        composerDraft = composerDraft.take(MAX_PERSISTED_COMPOSER_DRAFT_CHARS),
        trustedRuntimeAutoReconnectEnabled = trustedRuntimeAutoReconnectEnabled,
        pairingOnboardingCompleted = pairingOnboardingCompleted,
        sessions = cleanSessions.sortedByDescending { it.updatedAtMillis },
        suppressedRuntimeSessions = cleanSuppressedRuntimeSessions.sortedByDescending { it.updatedAtMillis },
        memoryEntries = cleanMemory.sortedByDescending { it.updatedAtMillis },
        appLanguageTag = cleanAppLanguageTag,
        appLanguageSource = cleanAppLanguageSource,
        appTheme = RuntimeAppTheme.fromStorage(appTheme).storageValue,
        pendingPairingRoute = pendingPairingRoute?.sanitizedOrNull(),
    )
}

internal fun PersistedRuntimeData.withoutRuntimeOwnedLocalData(): PersistedRuntimeData {
    return copy(
        sessions = sessions.map { session ->
            if (session.runtimeOwned && session.messages.isNotEmpty()) {
                session.copy(
                    runtimeSearchRank = null,
                    runtimeSearchSnippet = null,
                    runtimeSearchMatchedFields = emptyList(),
                    messages = emptyList(),
                )
            } else if (session.runtimeOwned) {
                session.copy(
                    runtimeSearchRank = null,
                    runtimeSearchSnippet = null,
                    runtimeSearchMatchedFields = emptyList(),
                )
            } else {
                session
            }
        },
        memoryEntries = emptyList(),
    ).sanitized()
}

private fun PersistedChatSession.hasLegacyPromptTitle(
    cleanTitle: String,
    fallbackTitle: String,
): Boolean {
    return !runtimeOwned &&
        !titleManuallyEdited &&
        !titleGenerated &&
        cleanTitle != DEFAULT_CHAT_TITLE &&
        cleanTitle == fallbackTitle
}

internal fun PersistedRuntimeData.withPendingPairingRoute(
    payload: RuntimePairingPayload,
    nowMillis: Long,
): PersistedRuntimeData {
    return copy(
        pendingPairingRoute = payload.toPersistedPendingPairingRoute(nowMillis),
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutPendingPairingRoute(): PersistedRuntimeData {
    return copy(pendingPairingRoute = null).sanitized()
}

internal fun PersistedPendingPairingRoute.isExpired(nowMillis: Long): Boolean {
    return expiresAtEpochMillis <= nowMillis
}

internal fun PersistedPendingPairingRoute.toRuntimePairingPayloadOrNull(): RuntimePairingPayload? {
    val clean = sanitizedOrNull() ?: return null
    if (clean.hasPersistedRelayRoute() && clean.relaySecret.isNullOrBlank()) return null
    return RuntimePairingPayload(
        pairingNonce = clean.pairingNonce,
        pairingCode = clean.pairingCode,
        runtimeDeviceId = clean.runtimeDeviceId,
        runtimeName = clean.runtimeName,
        fingerprint = clean.fingerprint,
        runtimePublicKeyBase64 = clean.runtimePublicKeyBase64,
        routeToken = clean.routeToken,
        host = clean.host,
        port = clean.port,
        relayHost = clean.relayHost,
        relayPort = clean.relayPort,
        relayId = clean.relayId,
        relaySecret = clean.relaySecret,
        relayExpiresAtEpochMillis = clean.relayExpiresAtEpochMillis,
        relayNonce = clean.relayNonce,
        relayScope = clean.relayScope,
        p2pRouteClass = clean.p2pRouteClass,
        p2pRecordId = clean.p2pRecordId,
        p2pEncryptedBody = clean.p2pEncryptedBody,
        p2pExpiresAtEpochMillis = clean.p2pExpiresAtEpochMillis,
        p2pAntiReplayNonce = clean.p2pAntiReplayNonce,
        p2pProtocolVersion = clean.p2pProtocolVersion,
        serviceType = clean.serviceType,
    )
}

private fun RuntimePairingPayload.toPersistedPendingPairingRoute(nowMillis: Long): PersistedPendingPairingRoute {
    val pairingWindowExpiresAt = nowMillis + PENDING_PAIRING_ROUTE_TTL_MILLIS
    val relayRouteExpiresAt = relayExpiresAtEpochMillis?.takeIf { it > 0L }
    val p2pRouteExpiresAt = p2pExpiresAtEpochMillis?.takeIf { it > 0L }
    val expiresAt = listOfNotNull(pairingWindowExpiresAt, relayRouteExpiresAt, p2pRouteExpiresAt).min()
    return PersistedPendingPairingRoute(
        pairingNonce = pairingNonce,
        pairingCode = pairingCode,
        runtimeDeviceId = runtimeDeviceId,
        runtimeName = runtimeName,
        fingerprint = fingerprint,
        runtimePublicKeyBase64 = runtimePublicKeyBase64?.takeIf(String::isNotBlank),
        routeToken = routeToken?.takeIf(String::isNotBlank),
        host = null,
        port = null,
        relayHost = relayHost?.takeIf(String::isNotBlank),
        relayPort = relayPort,
        relayId = relayId?.takeIf(String::isNotBlank),
        relaySecret = relaySecret?.takeIf(String::isNotBlank),
        relaySecretRef = relaySecret
            ?.takeIf(String::isNotBlank)
            ?.let {
                pendingPairingRelaySecretHandle(
                    runtimeDeviceId = runtimeDeviceId,
                    relayId = relayId,
                    pairingNonce = pairingNonce,
                )
            },
        relayExpiresAtEpochMillis = relayRouteExpiresAt,
        relayNonce = relayNonce?.takeIf(String::isNotBlank),
        relayScope = relayScope?.takeIf(String::isNotBlank),
        p2pRouteClass = p2pRouteClass?.takeIf(String::isNotBlank),
        p2pRecordId = p2pRecordId?.takeIf(String::isNotBlank),
        p2pEncryptedBody = p2pEncryptedBody?.takeIf(String::isNotBlank),
        p2pExpiresAtEpochMillis = p2pRouteExpiresAt,
        p2pAntiReplayNonce = p2pAntiReplayNonce?.takeIf(String::isNotBlank),
        p2pProtocolVersion = p2pProtocolVersion,
        serviceType = serviceType?.takeIf(String::isNotBlank),
        capturedAtEpochMillis = nowMillis,
        expiresAtEpochMillis = expiresAt,
    )
}

private fun PersistedPendingPairingRoute.sanitizedOrNull(): PersistedPendingPairingRoute? {
    val cleanNonce = pairingNonce.trim()
    val cleanCode = pairingCode.trim()
    val cleanRuntimeDeviceId = runtimeDeviceId.trim()
    val cleanRuntimeName = runtimeName.trim().ifBlank { "AetherLink Runtime" }
    val cleanFingerprint = fingerprint.trim()
    if (
        cleanNonce.isBlank() ||
        !cleanCode.matches(Regex("\\d{6}")) ||
        cleanRuntimeDeviceId.isBlank() ||
        cleanFingerprint.isBlank() ||
        capturedAtEpochMillis <= 0L ||
        expiresAtEpochMillis <= capturedAtEpochMillis
    ) {
        return null
    }
    val cleanPort = port?.takeIf { it in 1..65535 }
    val cleanRelayPort = relayPort?.takeIf { it in 1..65535 }
    val cleanHost = host?.trim()?.takeIf(String::isNotBlank)
    if ((cleanHost == null) != (cleanPort == null)) return null
    val cleanRelayHost = relayHost?.trim()?.takeIf(String::isNotBlank)
    val cleanRelayId = relayId?.trim()?.takeIf(String::isNotBlank)
    val cleanRelaySecret = relaySecret?.trim()?.takeIf(String::isNotBlank)
    val cleanRelaySecretRef = relaySecretRef?.trim()?.takeIf(String::isNotBlank)
    val cleanRelayExpiresAt = relayExpiresAtEpochMillis?.takeIf { it > 0L }
    val cleanRelayNonce = relayNonce?.trim()?.takeIf(String::isNotBlank)
    val cleanP2pRouteClass = p2pRouteClass?.takeIf(::isCanonicalOpaqueRouteValue)
    val cleanP2pRecordId = p2pRecordId?.takeIf(::isCanonicalOpaqueRouteValue)
    val cleanP2pEncryptedBody = p2pEncryptedBody
        ?.takeIf { isCanonicalOpaqueRouteValue(it, maxChars = OPAQUE_ROUTE_BODY_MAX_CHARS) }
    val cleanP2pExpiresAt = p2pExpiresAtEpochMillis?.takeIf { it > 0L }
    val cleanP2pAntiReplayNonce = p2pAntiReplayNonce?.takeIf(::isCanonicalOpaqueRouteValue)
    val hasRelayField = listOf(
        cleanRelayHost,
        cleanRelayPort,
        cleanRelayId,
        cleanRelaySecret,
        cleanRelaySecretRef,
        cleanRelayExpiresAt,
        cleanRelayNonce,
    ).any { it != null }
    if (
        hasRelayField &&
        (
            cleanRelayHost == null ||
                cleanRelayPort == null ||
                cleanRelayId == null ||
                (cleanRelaySecret == null && cleanRelaySecretRef == null) ||
                cleanRelayExpiresAt == null ||
                cleanRelayNonce == null
        )
    ) {
        return null
    }
    val hasP2pField = listOf(
        cleanP2pRouteClass,
        cleanP2pRecordId,
        cleanP2pEncryptedBody,
        cleanP2pExpiresAt,
        cleanP2pAntiReplayNonce,
        p2pProtocolVersion,
    ).any { it != null }
    if (
        hasP2pField &&
        (
            cleanP2pRouteClass != "p2p_rendezvous" ||
                cleanP2pRecordId == null ||
                cleanP2pEncryptedBody == null ||
                cleanP2pExpiresAt == null ||
                cleanP2pAntiReplayNonce == null ||
                p2pProtocolVersion != 1
        )
    ) {
        return null
    }
    return copy(
        pairingNonce = cleanNonce,
        pairingCode = cleanCode,
        runtimeDeviceId = cleanRuntimeDeviceId,
        runtimeName = cleanRuntimeName,
        fingerprint = cleanFingerprint,
        runtimePublicKeyBase64 = runtimePublicKeyBase64?.trim()?.takeIf(String::isNotBlank),
        routeToken = routeToken?.trim()?.takeIf(String::isNotBlank),
        host = null,
        port = null,
        relayHost = cleanRelayHost,
        relayPort = cleanRelayPort,
        relayId = cleanRelayId,
        relaySecret = cleanRelaySecret,
        relaySecretRef = cleanRelaySecretRef,
        relayExpiresAtEpochMillis = cleanRelayExpiresAt,
        relayNonce = cleanRelayNonce,
        relayScope = relayScope?.trim()?.takeIf(String::isNotBlank),
        p2pRouteClass = cleanP2pRouteClass,
        p2pRecordId = cleanP2pRecordId,
        p2pEncryptedBody = cleanP2pEncryptedBody,
        p2pExpiresAtEpochMillis = cleanP2pExpiresAt,
        p2pAntiReplayNonce = cleanP2pAntiReplayNonce,
        p2pProtocolVersion = p2pProtocolVersion,
        serviceType = serviceType?.trim()?.takeIf(String::isNotBlank),
    )
}

internal fun PersistedRuntimeData.withStoredPendingPairingRelaySecret(
    relaySecretStore: RelaySecretStore,
): PersistedRuntimeData {
    val pending = pendingPairingRoute?.sanitizedOrNull() ?: return withoutPendingPairingRoute()
    val relaySecret = pending.relaySecret?.trim()?.takeIf(String::isNotBlank)
    val relaySecretRef = when {
        relaySecret != null -> pending.relaySecretRef
            ?: pendingPairingRelaySecretHandle(
                runtimeDeviceId = pending.runtimeDeviceId,
                relayId = pending.relayId,
                pairingNonce = pending.pairingNonce,
            )
        else -> pending.relaySecretRef
    }
    if (relaySecret != null && relaySecretRef != null) {
        relaySecretStore.saveSecret(relaySecretRef, relaySecret)
    }
    return copy(
        pendingPairingRoute = pending.copy(
            relaySecret = null,
            relaySecretRef = relaySecretRef,
        ),
    ).sanitized()
}

internal fun PersistedRuntimeData.withLoadedPendingPairingRelaySecret(
    relaySecretStore: RelaySecretStore,
): PersistedRuntimeData {
    val pending = pendingPairingRoute?.sanitizedOrNull() ?: return withoutPendingPairingRoute()
    if (!pending.hasPersistedRelayRoute()) return copy(pendingPairingRoute = pending).sanitized()
    if (!pending.relaySecret.isNullOrBlank()) return copy(pendingPairingRoute = pending).sanitized()
    val relaySecret = pending.relaySecretRef
        ?.let(relaySecretStore::readSecret)
        ?.trim()
        ?.takeIf(String::isNotBlank)
        ?: return withoutPendingPairingRoute()
    return copy(
        pendingPairingRoute = pending.copy(relaySecret = relaySecret),
    ).sanitized()
}

private fun PersistedPendingPairingRoute.hasPersistedRelayRoute(): Boolean {
    return relayHost != null ||
        relayPort != null ||
        relayId != null ||
        relaySecret != null ||
        relaySecretRef != null ||
        relayExpiresAtEpochMillis != null ||
        relayNonce != null
}

private fun pendingPairingRelaySecretHandle(
    runtimeDeviceId: String,
    relayId: String?,
    pairingNonce: String,
): String {
    val digest = MessageDigest.getInstance("SHA-256")
        .digest("$runtimeDeviceId\n$relayId\n$pairingNonce".toByteArray(Charsets.UTF_8))
    return "pending-relay-v1-" + digest.joinToString("") { "%02x".format(it) }
}

private const val PENDING_PAIRING_ROUTE_TTL_MILLIS = 5 * 60 * 1000L

internal fun PersistedRuntimeData.withSelectedModelId(modelId: String?): PersistedRuntimeData {
    return copy(selectedModelId = modelId?.trim()?.takeIf(String::isNotBlank)).sanitized()
}

internal fun PersistedRuntimeData.withSelectedEmbeddingModelId(modelId: String?): PersistedRuntimeData {
    return copy(selectedEmbeddingModelId = modelId?.trim()?.takeIf(String::isNotBlank)).sanitized()
}

internal fun PersistedRuntimeData.composerDraftForSession(sessionId: String? = activeSessionId): String {
    val cleanSessionId = sessionId?.trim()?.takeIf(String::isNotBlank)
    return if (cleanSessionId == null) {
        composerDraft
    } else {
        sessions.firstOrNull { it.id == cleanSessionId }?.composerDraft ?: composerDraft
    }
}

internal fun PersistedRuntimeData.withComposerDraft(
    value: String,
    sessionId: String? = activeSessionId,
): PersistedRuntimeData {
    val cleanDraft = value.take(MAX_PERSISTED_COMPOSER_DRAFT_CHARS)
    val cleanSessionId = sessionId?.trim()?.takeIf { id -> sessions.any { it.id == id } }
        ?: return copy(composerDraft = cleanDraft).sanitized()
    return copy(
        sessions = sessions.map { session ->
            if (session.id == cleanSessionId) {
                session.copy(composerDraft = cleanDraft)
            } else {
                session
            }
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withTrustedRuntimeAutoReconnectEnabled(enabled: Boolean): PersistedRuntimeData {
    return copy(trustedRuntimeAutoReconnectEnabled = enabled).sanitized()
}

internal fun PersistedRuntimeData.withPairingOnboardingCompleted(): PersistedRuntimeData {
    return copy(pairingOnboardingCompleted = true).sanitized()
}

internal fun PersistedRuntimeData.withAppLanguageTag(languageTag: String): PersistedRuntimeData {
    return copy(
        appLanguageTag = RuntimeAppLanguage.normalizeLanguageTag(languageTag),
        appLanguageSource = APP_LANGUAGE_SOURCE_IN_APP,
    ).sanitized()
}

internal fun PersistedRuntimeData.withFollowSystemAppLanguageTag(languageTag: String?): PersistedRuntimeData {
    val normalizedLanguageTag = RuntimeAppLanguage.supportedLanguageTagOrNull(languageTag)
    return copy(
        appLanguageTag = normalizedLanguageTag ?: RuntimeAppLanguage.English.languageTag,
        appLanguageSource = if (normalizedLanguageTag == null) {
            APP_LANGUAGE_SOURCE_DEFAULT
        } else {
            APP_LANGUAGE_SOURCE_SYSTEM
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withSystemAppLanguageTag(languageTag: String?): PersistedRuntimeData {
    val cleanData = sanitized()
    if (cleanData.appLanguageSource == APP_LANGUAGE_SOURCE_IN_APP) return cleanData
    val normalizedLanguageTag = RuntimeAppLanguage.supportedLanguageTagOrNull(languageTag) ?: return cleanData
    return cleanData.copy(
        appLanguageTag = normalizedLanguageTag,
        appLanguageSource = APP_LANGUAGE_SOURCE_SYSTEM,
    ).sanitized()
}

internal fun PersistedRuntimeData.withAppTheme(theme: RuntimeAppTheme): PersistedRuntimeData {
    return copy(appTheme = theme.storageValue).sanitized()
}

internal fun PersistedRuntimeData.withActiveSession(sessionId: String): PersistedRuntimeData {
    val session = sessions.firstOrNull { it.id == sessionId && it.archivedAtMillis == null } ?: return this
    return copy(
        activeSessionId = session.id,
        selectedModelId = session.modelId?.trim()?.takeIf(String::isNotBlank) ?: selectedModelId,
    ).sanitized()
}

internal fun PersistedRuntimeData.withNoActiveSession(): PersistedRuntimeData {
    return copy(activeSessionId = null).sanitized()
}

internal fun PersistedRuntimeData.withRenamedChatSession(
    sessionId: String,
    title: String,
    nowMillis: Long,
): PersistedRuntimeData {
    val cleanTitle = title.trim()
    if (cleanTitle.isBlank()) return this
    return copy(
        sessions = sessions.map { session ->
            if (session.id == sessionId) {
                session.copy(
                    title = cleanTitle,
                    titleManuallyEdited = true,
                    titleGenerated = false,
                    updatedAtMillis = nowMillis,
                )
            } else {
                session
            }
        }
    ).sanitized()
}

internal fun PersistedRuntimeData.withRevertedRuntimeChatSessionRename(
    sessionId: String,
    previousTitle: String,
    previousTitleManuallyEdited: Boolean,
    previousTitleGenerated: Boolean,
    nowMillis: Long,
): PersistedRuntimeData {
    return copy(
        sessions = sessions.map { session ->
            if (session.id == sessionId && session.runtimeOwned) {
                session.copy(
                    title = previousTitle,
                    titleManuallyEdited = previousTitleManuallyEdited,
                    titleGenerated = previousTitleGenerated,
                    updatedAtMillis = nowMillis,
                )
            } else {
                session
            }
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withArchivedChatSession(
    sessionId: String,
    nowMillis: Long,
): PersistedRuntimeData {
    return copy(
        activeSessionId = activeSessionId?.takeIf { it != sessionId },
        sessions = sessions.map { session ->
            if (session.id == sessionId) {
                session.copy(archivedAtMillis = nowMillis, updatedAtMillis = nowMillis)
            } else {
                session
            }
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withArchivedChatSessions(nowMillis: Long): PersistedRuntimeData {
    return copy(
        activeSessionId = null,
        sessions = sessions.map { session ->
            if (session.archivedAtMillis == null) {
                session.copy(archivedAtMillis = nowMillis, updatedAtMillis = nowMillis)
            } else {
                session
            }
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withUnarchivedChatSession(
    sessionId: String,
    nowMillis: Long,
): PersistedRuntimeData {
    return copy(
        suppressedRuntimeSessions = suppressedRuntimeSessions.filterNot { it.sessionId == sessionId },
        sessions = sessions.map { session ->
            if (session.id == sessionId) {
                session.copy(archivedAtMillis = null, updatedAtMillis = nowMillis)
            } else {
                session
            }
        },
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutRuntimeChatSessionSuppression(
    sessionId: String,
): PersistedRuntimeData {
    return copy(
        suppressedRuntimeSessions = suppressedRuntimeSessions.filterNot { it.sessionId == sessionId },
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutChatSession(
    sessionId: String,
    nowMillis: Long? = null,
): PersistedRuntimeData {
    val deletedSession = sessions.firstOrNull { it.id == sessionId }
    return copy(
        activeSessionId = activeSessionId?.takeIf { it != sessionId },
        sessions = sessions.filterNot { it.id == sessionId },
        suppressedRuntimeSessions = suppressedRuntimeSessions.withRuntimeDeletion(
            session = deletedSession,
            nowMillis = nowMillis ?: deletedSession?.updatedAtMillis ?: 0L,
        ),
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutArchivedChatSession(
    sessionId: String,
    nowMillis: Long? = null,
): PersistedRuntimeData {
    val deletedSession = sessions.firstOrNull { it.id == sessionId && it.archivedAtMillis != null }
        ?: return this
    return copy(
        activeSessionId = activeSessionId?.takeIf { it != sessionId },
        sessions = sessions.filterNot { it.id == sessionId },
        suppressedRuntimeSessions = suppressedRuntimeSessions.withRuntimeDeletion(
            session = deletedSession,
            nowMillis = nowMillis ?: deletedSession.updatedAtMillis,
        ),
    ).sanitized()
}

internal fun PersistedRuntimeData.withGeneratedChatSessionTitle(
    sessionId: String,
    title: String,
    nowMillis: Long,
): PersistedRuntimeData {
    val cleanTitle = title.cleanedChatTitle()
    if (cleanTitle.isBlank()) return this
    return copy(
        sessions = sessions.map { session ->
            if (session.id == sessionId && !session.titleManuallyEdited) {
                session.copy(
                    title = cleanTitle,
                    titleGenerated = true,
                    updatedAtMillis = nowMillis,
                )
            } else {
                session
            }
        }
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutChatSessions(
    nowMillis: Long? = null,
): PersistedRuntimeData {
    return copy(
        activeSessionId = null,
        sessions = emptyList(),
        suppressedRuntimeSessions = suppressedRuntimeSessions.withRuntimeDeletions(
            sessions = sessions,
            nowMillis = nowMillis ?: sessions.maxOfOrNull { it.updatedAtMillis } ?: 0L,
        ),
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutArchivedChatSessions(
    nowMillis: Long? = null,
): PersistedRuntimeData {
    val archivedSessions = sessions.filter { it.archivedAtMillis != null }
    return copy(
        sessions = sessions.filter { it.archivedAtMillis == null },
        suppressedRuntimeSessions = suppressedRuntimeSessions.withRuntimeDeletions(
            sessions = archivedSessions,
            nowMillis = nowMillis ?: archivedSessions.maxOfOrNull { it.updatedAtMillis } ?: 0L,
        ),
    ).sanitized()
}

internal fun PersistedRuntimeData.withNewChatSession(
    nowMillis: Long,
    sessionId: String = UUID.randomUUID().toString(),
    modelId: String? = null,
): PersistedRuntimeData {
    val session = PersistedChatSession(
        id = sessionId,
        title = DEFAULT_CHAT_TITLE,
        modelId = modelId?.trim()?.takeIf(String::isNotBlank),
        createdAtMillis = nowMillis,
        updatedAtMillis = nowMillis,
    )
    return copy(
        activeSessionId = sessionId,
        sessions = listOf(session) + sessions,
    ).sanitized()
}

internal fun PersistedRuntimeData.withPersistedMessages(
    sessionId: String,
    messages: List<RuntimeChatMessage>,
    nowMillis: Long,
    runtimeBacked: Boolean = false,
): PersistedRuntimeData {
    val existing = sessions.firstOrNull { it.id == sessionId }
    val createdAt = existing?.createdAtMillis ?: nowMillis
    val existingMessageTimes = existing?.messages.orEmpty().associate { it.id to it.createdAtMillis }
    val title = existing?.title?.trim()?.takeIf(String::isNotBlank) ?: DEFAULT_CHAT_TITLE
    val persistedMessages = messages
        .filter { it.role in CHAT_STORAGE_ROLES }
        .map { it.toPersistedChatMessage(existingMessageTimes[it.id] ?: nowMillis) }
    val updatedSession = PersistedChatSession(
        id = sessionId,
        title = title,
        modelId = existing?.modelId,
        createdAtMillis = createdAt,
        updatedAtMillis = nowMillis,
        archivedAtMillis = existing?.archivedAtMillis,
        titleManuallyEdited = existing?.titleManuallyEdited ?: false,
        titleGenerated = existing?.titleGenerated ?: false,
        runtimeOwned = existing?.runtimeOwned == true || runtimeBacked,
        runtimeMessageCount = existing?.runtimeMessageCount ?: messages.size.takeIf { runtimeBacked },
        lastEvent = existing?.lastEvent,
        lastFinishReason = existing?.lastFinishReason,
        lastErrorCode = existing?.lastErrorCode,
        composerDraft = existing?.composerDraft.orEmpty(),
        messages = persistedMessages,
    )
    return copy(
        activeSessionId = sessionId,
        sessions = listOf(updatedSession) + sessions.filterNot { it.id == sessionId },
    ).sanitized()
}

internal fun PersistedRuntimeData.withRuntimeChatSessionSummaries(
    sessions: List<ChatSessionSummaryPayload>,
    nowMillis: Long,
): PersistedRuntimeData {
    val runtimeSummaries = sessions
        .filter { it.sessionId.isNotBlank() }
        .filterNot { it.sessionId in deletedRuntimeSessionIds() }
        .distinctBy { it.sessionId }
    val localOnlySessions = this.sessions.filterNot { it.runtimeOwned }
    val mergedRuntimeSessions = runtimeSummaries.map { summary ->
        val existing = this.sessions.firstOrNull { it.id == summary.sessionId }
        val updatedAt = parseTimestampMillis(summary.lastActivityAt) ?: existing?.updatedAtMillis ?: nowMillis
        val modelId = summary.model.trim().takeIf(String::isNotBlank) ?: existing?.modelId
        val cleanMessageCount = summary.messageCount.coerceAtLeast(0)
        val isArchived = summary.status.equals("archived", ignoreCase = true) || summary.archivedAt != null
        val archivedAt = if (isArchived) {
            summary.archivedAt?.let(::parseTimestampMillis)
                ?: existing?.archivedAtMillis
                ?: updatedAt
        } else {
            null
        }
        val title = summary.title.trim().takeIf(String::isNotBlank) ?: existing?.title ?: DEFAULT_CHAT_TITLE
        val searchRank = summary.search?.rank?.takeIf { it > 0 }
        val searchSnippet = summary.search?.snippet?.trim()?.takeIf(String::isNotBlank)
        val searchMatchedFields = summary.search?.matchedFields
            ?.mapNotNull { it.trim().takeIf(String::isNotBlank) }
            ?.distinct()
            .orEmpty()
        existing?.copy(
            title = if (existing.titleManuallyEdited) existing.title else title,
            modelId = modelId,
            updatedAtMillis = updatedAt,
            archivedAtMillis = archivedAt,
            titleGenerated = existing.titleGenerated || !existing.titleManuallyEdited,
            runtimeOwned = true,
            runtimeMessageCount = cleanMessageCount,
            lastEvent = summary.lastEvent?.trim()?.takeIf(String::isNotBlank),
            lastFinishReason = summary.lastFinishReason?.trim()?.takeIf(String::isNotBlank),
            lastErrorCode = summary.lastErrorCode?.trim()?.takeIf(String::isNotBlank),
            runtimeSearchRank = searchRank,
            runtimeSearchSnippet = searchSnippet,
            runtimeSearchMatchedFields = searchMatchedFields,
        ) ?: PersistedChatSession(
            id = summary.sessionId,
            title = title,
            modelId = modelId,
            createdAtMillis = updatedAt,
            updatedAtMillis = updatedAt,
            archivedAtMillis = archivedAt,
            titleGenerated = true,
            runtimeOwned = true,
            runtimeMessageCount = cleanMessageCount,
            lastEvent = summary.lastEvent?.trim()?.takeIf(String::isNotBlank),
            lastFinishReason = summary.lastFinishReason?.trim()?.takeIf(String::isNotBlank),
            lastErrorCode = summary.lastErrorCode?.trim()?.takeIf(String::isNotBlank),
            runtimeSearchRank = searchRank,
            runtimeSearchSnippet = searchSnippet,
            runtimeSearchMatchedFields = searchMatchedFields,
        )
    }
    return copy(
        sessions = mergedRuntimeSessions + localOnlySessions,
    ).sanitized()
}

internal fun PersistedRuntimeData.withRuntimeChatMessages(
    sessionId: String,
    messages: List<ChatStoredMessagePayload>,
    nowMillis: Long,
): PersistedRuntimeData {
    val cleanSessionId = sessionId.trim()
    if (cleanSessionId.isBlank()) return this
    if (cleanSessionId in deletedRuntimeSessionIds()) return this
    val existing = sessions.firstOrNull { it.id == cleanSessionId }?.takeIf { it.runtimeOwned }
        ?: return this
    val persistedMessages = messages
        .filter { it.role in CHAT_STORAGE_ROLES }
        .mapIndexed { index, message ->
            val createdAt = message.createdAt?.let(::parseTimestampMillis) ?: nowMillis
            PersistedChatMessage(
                id = stableRuntimeMessageId(cleanSessionId, index, message),
                role = message.role,
                content = message.content,
                reasoning = message.reasoning.orEmpty(),
                attachments = message.attachments
                    .mapIndexedNotNull { attachmentIndex, attachment ->
                        attachment.toPersistedMessageAttachment(
                            messageId = stableRuntimeMessageId(cleanSessionId, index, message),
                            index = attachmentIndex,
                        )
                    },
                createdAtMillis = createdAt,
            )
        }
    val updatedAt = persistedMessages.maxOfOrNull { it.createdAtMillis }
        ?: existing.updatedAtMillis
    val title = existing.title.takeIf(String::isNotBlank) ?: DEFAULT_CHAT_TITLE
    val updatedSession = PersistedChatSession(
        id = cleanSessionId,
        title = title,
        modelId = existing.modelId,
        createdAtMillis = existing.createdAtMillis,
        updatedAtMillis = updatedAt,
        archivedAtMillis = existing.archivedAtMillis,
        titleManuallyEdited = existing.titleManuallyEdited,
        titleGenerated = existing.titleGenerated,
        runtimeOwned = true,
        runtimeMessageCount = messages.size,
        lastEvent = existing.lastEvent,
        lastFinishReason = existing.lastFinishReason,
        lastErrorCode = existing.lastErrorCode,
        composerDraft = existing.composerDraft,
        messages = persistedMessages,
    )
    return copy(
        sessions = listOf(updatedSession) + sessions.filterNot { it.id == cleanSessionId },
    ).sanitized()
}

internal fun PersistedRuntimeData.withRuntimeChatSessionLifecycleResult(
    result: ChatSessionLifecyclePayload,
    nowMillis: Long,
): PersistedRuntimeData {
    val sessionId = result.sessionId.trim()
    if (sessionId.isBlank()) return this
    val existingSession = sessions.firstOrNull { it.id == sessionId }
    if (existingSession != null && !existingSession.runtimeOwned) return this
    val status = result.status?.trim()?.lowercase()
    val archivedAt = result.archivedAt?.let(::parseTimestampMillis)
    val restoredAt = result.restoredAt?.let(::parseTimestampMillis)
    val deletedAt = result.deletedAt?.let(::parseTimestampMillis)
    return when {
        status == "archived" || archivedAt != null -> withArchivedChatSession(
            sessionId = sessionId,
            nowMillis = archivedAt ?: nowMillis,
        )
        status == "restored" || restoredAt != null -> withUnarchivedChatSession(
            sessionId = sessionId,
            nowMillis = restoredAt ?: nowMillis,
        )
        status == "deleted" || deletedAt != null -> copy(
            activeSessionId = activeSessionId?.takeIf { it != sessionId },
            sessions = sessions.filterNot { it.id == sessionId },
            suppressedRuntimeSessions = suppressedRuntimeSessions.withRuntimeDeletion(
                sessionId = sessionId,
                nowMillis = deletedAt ?: nowMillis,
            ),
        ).sanitized()
        else -> this
    }
}

private fun List<PersistedSuppressedRuntimeSession>.withRuntimeDeletion(
    session: PersistedChatSession?,
    nowMillis: Long,
): List<PersistedSuppressedRuntimeSession> {
    if (session?.runtimeOwned != true) return this
    val timestamp = maxOf(nowMillis, session.updatedAtMillis)
    return filterNot { it.sessionId == session.id } + PersistedSuppressedRuntimeSession(
        sessionId = session.id,
        reason = SUPPRESSED_REASON_DELETED,
        updatedAtMillis = timestamp,
    )
}

private fun List<PersistedSuppressedRuntimeSession>.withRuntimeDeletion(
    sessionId: String,
    nowMillis: Long,
): List<PersistedSuppressedRuntimeSession> {
    val cleanSessionId = sessionId.trim()
    if (cleanSessionId.isBlank()) return this
    return filterNot { it.sessionId == cleanSessionId } + PersistedSuppressedRuntimeSession(
        sessionId = cleanSessionId,
        reason = SUPPRESSED_REASON_DELETED,
        updatedAtMillis = nowMillis,
    )
}

private fun List<PersistedSuppressedRuntimeSession>.withRuntimeDeletions(
    sessions: List<PersistedChatSession>,
    nowMillis: Long,
): List<PersistedSuppressedRuntimeSession> {
    return sessions.fold(this) { suppressions, session ->
        suppressions.withRuntimeDeletion(session, nowMillis)
    }
}

private fun PersistedRuntimeData.deletedRuntimeSessionIds(): Set<String> {
    return suppressedRuntimeSessions
        .filter { it.reason == SUPPRESSED_REASON_DELETED }
        .mapTo(mutableSetOf()) { it.sessionId }
}

internal fun PersistedRuntimeData.withRuntimeMemoryEntries(
    entries: List<MemoryEntryPayload>,
    nowMillis: Long,
): PersistedRuntimeData {
    val cleanEntries = entries
        .filter { it.id.isNotBlank() && it.content.isNotBlank() }
        .distinctBy { it.id }
        .map { entry ->
            val existing = memoryEntries.firstOrNull { it.id == entry.id }
            entry.toPersistedMemoryEntry(existing = existing, nowMillis = nowMillis)
        }
    return copy(memoryEntries = cleanEntries).sanitized()
}

internal fun PersistedRuntimeData.withRuntimeMemoryEntry(
    entry: MemoryEntryPayload,
    nowMillis: Long,
): PersistedRuntimeData {
    if (entry.id.isBlank() || entry.content.isBlank()) return this
    val existing = memoryEntries.firstOrNull { it.id == entry.id }
    val persisted = entry.toPersistedMemoryEntry(existing = existing, nowMillis = nowMillis)
    return copy(
        memoryEntries = listOf(persisted) + memoryEntries.filterNot { it.id == entry.id },
    ).sanitized()
}

internal fun PersistedRuntimeData.withoutRuntimeMemoryEntry(entryId: String): PersistedRuntimeData {
    val cleanId = entryId.trim()
    if (cleanId.isBlank()) return this
    return copy(memoryEntries = memoryEntries.filterNot { it.id == cleanId }).sanitized()
}

internal fun activeSessionMessages(data: PersistedRuntimeData): List<RuntimeChatMessage> {
    val activeSessionId = data.activeSessionId ?: return emptyList()
    return data.sessions.firstOrNull { it.id == activeSessionId && it.archivedAtMillis == null }
        ?.messages
        ?.map { it.toRuntimeChatMessage() }
        ?: emptyList()
}

internal fun activeRuntimeSessionId(data: PersistedRuntimeData): String? {
    val activeSessionId = data.activeSessionId ?: return null
    return data.sessions
        .firstOrNull { session ->
            session.id == activeSessionId &&
                session.archivedAtMillis == null &&
                session.runtimeOwned
        }
        ?.id
}

internal fun runtimeChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return data.sessions
        .filter { it.archivedAtMillis == null }
        .map { session ->
            session.toRuntimeChatSession()
        }
}

internal fun archivedRuntimeChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return data.sessions
        .filter { it.archivedAtMillis != null }
        .map { session ->
            session.toRuntimeChatSession()
        }
}

private fun PersistedChatSession.toRuntimeChatSession(): RuntimeChatSession {
    return RuntimeChatSession(
        id = id,
        title = title,
        modelId = modelId,
        updatedAtMillis = updatedAtMillis,
        messageCount = (runtimeMessageCount ?: messages.size).coerceAtLeast(0),
        archivedAtMillis = archivedAtMillis,
        titleManuallyEdited = titleManuallyEdited,
        titleGenerated = titleGenerated,
        lastEvent = lastEvent,
        lastFinishReason = lastFinishReason,
        lastErrorCode = lastErrorCode,
        searchRank = runtimeSearchRank,
        searchSnippet = runtimeSearchSnippet,
        searchMatchedFields = runtimeSearchMatchedFields,
    )
}

internal fun memoryCandidateChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return runtimeChatSessions(data)
}

internal fun researchCandidateChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return runtimeChatSessions(data)
}

internal fun reflectionCandidateChatSessions(data: PersistedRuntimeData): List<RuntimeChatSession> {
    return runtimeChatSessions(data)
}

internal fun runtimeMemoryEntries(data: PersistedRuntimeData): List<RuntimeMemoryEntry> {
    return data.memoryEntries.map { entry ->
        RuntimeMemoryEntry(
            id = entry.id,
            content = entry.content,
            enabled = entry.enabled,
            createdAtMillis = entry.createdAtMillis,
            updatedAtMillis = entry.updatedAtMillis,
            source = entry.source?.toRuntimeMemoryEntrySource(),
            searchRank = entry.runtimeSearchRank,
            searchSnippet = entry.runtimeSearchSnippet,
            searchMatchedFields = entry.runtimeSearchMatchedFields,
        )
    }
}

internal fun chatSendMessages(
    messages: List<RuntimeChatMessage>,
    attachments: List<RuntimePendingAttachment> = emptyList(),
): List<ChatMessagePayload> {
    val conversationMessages = messages
        .filter { it.role == "user" || it.role == "assistant" }
        .filter { it.content.isNotBlank() }
    return conversationMessages
        .mapIndexed { index, message ->
            val messageAttachments = if (index == conversationMessages.lastIndex) {
                attachments.map { attachment ->
                    ChatAttachmentPayload(
                        type = attachment.type,
                        mimeType = attachment.mimeType,
                        name = attachment.name,
                        dataBase64 = attachment.dataBase64,
                    )
                }
            } else {
                emptyList()
            }
            ChatMessagePayload(
                role = message.role,
                content = message.content,
                attachments = messageAttachments,
            )
        }
}

private fun PersistedChatMessage.toRuntimeChatMessage(): RuntimeChatMessage {
    return RuntimeChatMessage(
        id = id,
        role = role,
        content = content,
        reasoning = reasoning,
        attachments = attachments.map { it.toRuntimeMessageAttachment() },
    )
}

private fun RuntimeChatMessage.toPersistedChatMessage(nowMillis: Long): PersistedChatMessage {
    return PersistedChatMessage(
        id = id,
        role = role,
        content = content,
        reasoning = reasoning,
        attachments = attachments.map { it.toPersistedMessageAttachment() },
        createdAtMillis = nowMillis,
    )
}

private fun PersistedChatMessage.withCleanAttachments(): PersistedChatMessage {
    return copy(
        attachments = attachments
            .mapNotNull { it.sanitizedOrNull() }
            .distinctBy { it.id },
    )
}

private fun ChatAttachmentPayload.toPersistedMessageAttachment(
    messageId: String,
    index: Int,
): PersistedMessageAttachment? {
    val type = type.trim().takeIf(String::isNotBlank) ?: return null
    val mimeType = mimeType.trim().takeIf(String::isNotBlank) ?: return null
    val name = name?.trim()?.takeIf(String::isNotBlank) ?: mimeType
    val text = text?.trim()?.takeIf(String::isNotBlank)
    val idSeed = listOf("runtime-attachment", messageId, index.toString(), type, mimeType, name, text.orEmpty())
        .joinToString(separator = "\u001F")
    return PersistedMessageAttachment(
        id = UUID.nameUUIDFromBytes(idSeed.encodeToByteArray()).toString(),
        type = type,
        name = name,
        mimeType = mimeType,
        text = text,
    )
}

private fun RuntimeMessageAttachment.toPersistedMessageAttachment(): PersistedMessageAttachment {
    return PersistedMessageAttachment(
        id = id,
        type = type,
        name = name,
        mimeType = mimeType,
        text = text?.trim()?.takeIf(String::isNotBlank),
    )
}

private fun PersistedMessageAttachment.toRuntimeMessageAttachment(): RuntimeMessageAttachment {
    return RuntimeMessageAttachment(
        id = id,
        type = type,
        name = name,
        mimeType = mimeType,
        text = text,
    )
}

private fun PersistedMessageAttachment.sanitizedOrNull(): PersistedMessageAttachment? {
    val cleanType = type.trim().takeIf(String::isNotBlank) ?: return null
    val cleanMimeType = mimeType.trim().takeIf(String::isNotBlank) ?: return null
    val cleanName = name.trim().takeIf(String::isNotBlank) ?: cleanMimeType
    return copy(
        id = id.trim().takeIf(String::isNotBlank)
            ?: UUID.nameUUIDFromBytes(
                listOf(cleanType, cleanMimeType, cleanName, text.orEmpty()).joinToString("\u001F").encodeToByteArray()
            ).toString(),
        type = cleanType,
        mimeType = cleanMimeType,
        name = cleanName,
        text = text?.trim()?.takeIf(String::isNotBlank),
    )
}

private fun MemoryEntryPayload.toPersistedMemoryEntry(
    existing: PersistedMemoryEntry?,
    nowMillis: Long,
): PersistedMemoryEntry {
    val createdAt = createdAt?.let(::parseTimestampMillis)
        ?: existing?.createdAtMillis
        ?: nowMillis
    val updatedAt = updatedAt?.let(::parseTimestampMillis)
        ?: existing?.updatedAtMillis
        ?: createdAt
    val searchRank = search?.rank?.takeIf { it > 0 }
    val searchSnippet = search?.snippet?.trim()?.takeIf(String::isNotBlank)
    val searchMatchedFields = search?.matchedFields
        ?.mapNotNull { it.trim().takeIf(String::isNotBlank) }
        ?.distinct()
        .orEmpty()
    return PersistedMemoryEntry(
        id = id,
        content = content.trim(),
        enabled = enabled,
        createdAtMillis = createdAt,
        updatedAtMillis = updatedAt,
        source = source?.toPersistedMemoryEntrySource() ?: existing?.source,
        runtimeSearchRank = searchRank,
        runtimeSearchSnippet = searchSnippet,
        runtimeSearchMatchedFields = searchMatchedFields,
    )
}

private fun MemoryEntrySourcePayload.toPersistedMemoryEntrySource(): PersistedMemoryEntrySource? {
    val cleanKind = kind.trim().takeIf(String::isNotBlank) ?: return null
    val cleanDraftId = draftId.trim().takeIf(String::isNotBlank) ?: return null
    val cleanSummaryMethod = summaryMethod.trim().takeIf(String::isNotBlank) ?: return null
    val cleanSessionId = session.sessionId.trim().takeIf(String::isNotBlank) ?: return null
    val pointers = sourcePointers.mapNotNull { pointer ->
        PersistedMemoryEntrySourcePointer(
            sessionId = pointer.sessionId.trim(),
            messageIndex = pointer.messageIndex,
            role = pointer.role.trim(),
            createdAtMillis = pointer.createdAt?.let(::parseTimestampMillis),
            excerpt = pointer.excerpt.trim(),
        ).sanitizedOrNull()
    }
    if (pointers.isEmpty()) return null
    return PersistedMemoryEntrySource(
        kind = cleanKind,
        draftId = cleanDraftId,
        summaryMethod = cleanSummaryMethod,
        session = PersistedMemoryEntrySourceSession(
            sessionId = cleanSessionId,
            title = session.title.trim(),
            modelId = session.model.trim(),
            lastActivityAtMillis = parseTimestampMillis(session.lastActivityAt),
            messageCount = session.messageCount.coerceAtLeast(0),
            inactiveSeconds = session.inactiveSeconds.coerceAtLeast(0L),
        ),
        sourceMessageCount = sourceMessageCount.coerceAtLeast(pointers.size),
        sourceRange = sourceRange.trim().takeIf(String::isNotBlank) ?: return null,
        sourcePointers = pointers,
    )
}

private fun PersistedMemoryEntrySource.sanitizedOrNull(): PersistedMemoryEntrySource? {
    val cleanKind = kind.trim().takeIf(String::isNotBlank) ?: return null
    val cleanDraftId = draftId.trim().takeIf(String::isNotBlank) ?: return null
    val cleanSummaryMethod = summaryMethod.trim().takeIf(String::isNotBlank) ?: return null
    val cleanSourceRange = sourceRange.trim().takeIf(String::isNotBlank) ?: return null
    val cleanSessionId = session.sessionId.trim().takeIf(String::isNotBlank) ?: return null
    val cleanPointers = sourcePointers.mapNotNull { it.sanitizedOrNull() }
    if (cleanPointers.isEmpty()) return null
    return copy(
        kind = cleanKind,
        draftId = cleanDraftId,
        summaryMethod = cleanSummaryMethod,
        session = session.copy(
            sessionId = cleanSessionId,
            title = session.title.trim(),
            modelId = session.modelId.trim(),
            messageCount = session.messageCount.coerceAtLeast(0),
            inactiveSeconds = session.inactiveSeconds.coerceAtLeast(0L),
        ),
        sourceMessageCount = sourceMessageCount.coerceAtLeast(cleanPointers.size),
        sourceRange = cleanSourceRange,
        sourcePointers = cleanPointers,
    )
}

private fun PersistedMemoryEntrySourcePointer.sanitizedOrNull(): PersistedMemoryEntrySourcePointer? {
    val cleanSessionId = sessionId.trim().takeIf(String::isNotBlank) ?: return null
    val cleanRole = role.trim().takeIf(String::isNotBlank) ?: return null
    val cleanExcerpt = excerpt.trim().takeIf(String::isNotBlank) ?: return null
    return copy(
        sessionId = cleanSessionId,
        messageIndex = messageIndex.coerceAtLeast(1),
        role = cleanRole,
        excerpt = cleanExcerpt,
    )
}

private fun PersistedMemoryEntrySource.toRuntimeMemoryEntrySource(): RuntimeMemoryEntrySource {
    return RuntimeMemoryEntrySource(
        kind = kind,
        draftId = draftId,
        summaryMethod = summaryMethod,
        session = RuntimeMemorySummaryDraftSession(
            sessionId = session.sessionId,
            title = session.title,
            modelId = session.modelId,
            lastActivityAtMillis = session.lastActivityAtMillis,
            messageCount = session.messageCount,
            inactiveSeconds = session.inactiveSeconds,
        ),
        sourceMessageCount = sourceMessageCount,
        sourceRange = sourceRange,
        sourcePointers = sourcePointers.map { pointer ->
            RuntimeMemorySummaryDraftSourcePointer(
                sessionId = pointer.sessionId,
                messageIndex = pointer.messageIndex,
                role = pointer.role,
                createdAtMillis = pointer.createdAtMillis,
                excerpt = pointer.excerpt,
            )
        },
    )
}

private fun stableRuntimeMessageId(
    sessionId: String,
    index: Int,
    message: ChatStoredMessagePayload,
): String {
    val seed = listOf(
        "runtime",
        sessionId,
        index.toString(),
        message.createdAt.orEmpty(),
        message.role,
        message.content,
        message.reasoning.orEmpty(),
        message.attachments.joinToString(separator = "\u001E") { attachment ->
            listOf(
                attachment.type,
                attachment.mimeType,
                attachment.name.orEmpty(),
                attachment.text.orEmpty(),
            ).joinToString(separator = "\u001D")
        },
    ).joinToString(separator = "\u001F")
    return UUID.nameUUIDFromBytes(seed.encodeToByteArray()).toString()
}

private fun parseTimestampMillis(timestamp: String): Long? {
    return runCatching { Instant.parse(timestamp).toEpochMilli() }.getOrNull()
}

private fun titleForMessages(messages: List<RuntimeChatMessage>): String {
    return messages.firstOrNull { it.role == "user" && it.content.isNotBlank() }
        ?.content
        ?.lineSequence()
        ?.firstOrNull()
        ?.trim()
        ?.take(MAX_TITLE_LENGTH)
        ?: DEFAULT_CHAT_TITLE
}

private val CHAT_STORAGE_ROLES = setOf("user", "assistant")
private const val DEFAULT_CHAT_TITLE = ""
private const val LEGACY_DEFAULT_CHAT_TITLE = "New chat"
private const val MAX_TITLE_LENGTH = 48

internal fun String.cleanedChatTitle(): String {
    return trim()
        .lineSequence()
        .firstOrNull()
        ?.trim()
        ?.trim('"', '\'', '`')
        ?.take(MAX_TITLE_LENGTH)
        .orEmpty()
}
