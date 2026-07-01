package com.localagentbridge.android.runtime

import com.localagentbridge.android.core.transport.RuntimeEndpointHint
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import java.util.UUID

internal const val MAX_PENDING_ATTACHMENTS = 4

data class RuntimeUiState(
    val runtimeHost: String = "",
    val runtimePort: String = "",
    val runtimeEndpointSource: RuntimeEndpointSource = RuntimeEndpointSource.Manual,
    val trustedRuntime: RuntimeTrustedRuntime? = null,
    val discoveredRuntimes: List<RuntimeDiscoveredRuntime> = emptyList(),
    val isDiscovering: Boolean = false,
    val pendingPairingRuntimeName: String? = null,
    val isPairingAwaitingRoute: Boolean = false,
    val routeRefreshNoticeRuntimeName: String? = null,
    val pairingCode: String = "",
    val isConnected: Boolean = false,
    val isConnecting: Boolean = false,
    val runtimeStatus: String = "disconnected",
    val backendAvailable: Boolean? = null,
    val backendCode: String? = null,
    val providerStatuses: List<RuntimeProviderStatus> = emptyList(),
    val models: List<RuntimeModel> = emptyList(),
    val isLoadingModels: Boolean = false,
    val installingModelId: String? = null,
    val selectedModelId: String? = null,
    val selectedEmbeddingModelId: String? = null,
    val chatSessions: List<RuntimeChatSession> = emptyList(),
    val archivedChatSessions: List<RuntimeChatSession> = emptyList(),
    val activeChatSessionId: String? = null,
    val loadingChatSessionId: String? = null,
    val messages: List<RuntimeChatMessage> = emptyList(),
    val chatInput: String = "",
    val pendingAttachments: List<RuntimePendingAttachment> = emptyList(),
    val isStreaming: Boolean = false,
    val activeRequestId: String? = null,
    val memoryEntries: List<RuntimeMemoryEntry> = emptyList(),
    val memorySummaryDrafts: List<RuntimeMemorySummaryDraft> = emptyList(),
    val approvingMemorySummaryDraftIds: Set<String> = emptySet(),
    val dismissingMemorySummaryDraftIds: Set<String> = emptySet(),
    val selectedLanguageTag: String = RuntimeAppLanguage.English.languageTag,
    val selectedLanguageSource: String = APP_LANGUAGE_SOURCE_DEFAULT,
    val selectedTheme: RuntimeAppTheme = RuntimeAppTheme.System,
    val trustedRuntimeAutoReconnectEnabled: Boolean = true,
    val pairingOnboardingCompleted: Boolean = false,
    val activeRouteKind: RuntimeActiveRouteKind? = null,
    val error: RuntimeUiError? = null,
) {
    val isLoadingActiveChatMessages: Boolean
        get() = activeChatSessionId != null && loadingChatSessionId == activeChatSessionId
}

enum class RuntimeActiveRouteKind {
    DirectTcp,
    PeerToPeer,
    Relay,
}

enum class RuntimeAppLanguage(val languageTag: String) {
    English("en"),
    Korean("ko"),
    Japanese("ja"),
    SimplifiedChinese("zh-CN"),
    French("fr");

    companion object {
        val supportedLanguageTags: Set<String> = entries
            .map { it.languageTag }
            .filter { it.isNotBlank() }
            .toSet()

        fun supportedLanguageTagOrNull(languageTag: String?): String? {
            val normalized = languageTag
                ?.trim()
                ?.replace('_', '-')
                ?: return null
            if (normalized.isBlank()) return null
            if (
                normalized.equals("zh-CN", ignoreCase = true) ||
                normalized.equals("zh-Hans", ignoreCase = true) ||
                normalized.equals("zh-rCN", ignoreCase = true) ||
                normalized.equals("zh-Hans-CN", ignoreCase = true)
            ) {
                return SimplifiedChinese.languageTag
            }
            val baseLanguage = normalized.substringBefore('-')
            return entries
                .firstOrNull { language ->
                    language.languageTag.equals(normalized, ignoreCase = true) ||
                        language.languageTag.equals(baseLanguage, ignoreCase = true)
                }
                ?.languageTag
        }

        fun normalizeLanguageTag(languageTag: String): String {
            return supportedLanguageTagOrNull(languageTag) ?: English.languageTag
        }
    }
}

enum class RuntimeAppTheme(val storageValue: String) {
    System("system"),
    Light("light"),
    Dark("dark");

    companion object {
        fun fromStorage(value: String): RuntimeAppTheme {
            val normalized = value.trim().lowercase()
            return entries.firstOrNull { it.storageValue == normalized } ?: System
        }
    }
}

data class RuntimeTrustedRuntime(
    val deviceId: String,
    val name: String,
    val fingerprint: String? = null,
    val publicKeyBase64: String? = null,
    val routeToken: String? = null,
    val endpointHint: RuntimeEndpointHint? = null,
    val relayHost: String? = null,
    val relayPort: Int? = null,
    val relayId: String? = null,
    val relaySecret: String? = null,
    val relayExpiresAtEpochMillis: Long? = null,
    val relayNonce: String? = null,
    val relayScope: String? = null,
    val p2pRouteClass: String? = null,
    val p2pRecordId: String? = null,
    val p2pEncryptedBody: String? = null,
    val p2pExpiresAtEpochMillis: Long? = null,
    val p2pAntiReplayNonce: String? = null,
    val p2pProtocolVersion: Int? = null,
) {
    val lastKnownEndpoint: RuntimeEndpointHint
        get() = requireNotNull(endpointHint) { "Trusted runtime endpoint hint is not available" }
}

data class RuntimeDiscoveredRuntime(
    val serviceName: String,
    val host: String,
    val port: Int,
    val routeToken: String? = null,
    val deviceId: String? = null,
    val fingerprint: String? = null,
    val app: String? = null,
    val version: String? = null,
)

data class RuntimeModel(
    val id: String,
    val name: String,
    val backend: String = "ollama",
    val provider: String = "ollama",
    val modelKind: String = MODEL_KIND_CHAT,
    val capabilities: List<String> = emptyList(),
    val providerModelId: String? = null,
    val installed: Boolean = true,
    val running: Boolean = false,
    val source: String? = "local",
    val description: String? = null,
    val sizeBytes: Long? = null,
    val contextWindowTokens: Int? = null,
)

const val MODEL_KIND_CHAT = "chat"
const val MODEL_KIND_EMBEDDING = "embedding"

data class RuntimeProviderStatus(
    val id: String,
    val name: String,
    val available: Boolean,
    val message: String = "",
    val code: String? = null,
    val retryable: Boolean? = null,
)

data class RuntimeChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: String,
    val content: String,
    val reasoning: String = "",
    val isReasoningOpen: Boolean = false,
    val inlineReasoningPendingTag: String = "",
    val attachments: List<RuntimeMessageAttachment> = emptyList(),
)

data class RuntimePendingAttachment(
    val id: String = UUID.randomUUID().toString(),
    val type: String,
    val name: String,
    val mimeType: String,
    val sizeBytes: Long,
    val dataBase64: String,
)

data class RuntimeMessageAttachment(
    val id: String = UUID.randomUUID().toString(),
    val type: String,
    val name: String,
    val mimeType: String,
    val text: String? = null,
)

data class RuntimeChatSession(
    val id: String,
    val title: String,
    val modelId: String? = null,
    val updatedAtMillis: Long,
    val messageCount: Int,
    val archivedAtMillis: Long? = null,
    val titleManuallyEdited: Boolean = false,
    val titleGenerated: Boolean = false,
    val lastEvent: String? = null,
    val lastFinishReason: String? = null,
    val lastErrorCode: String? = null,
    val searchRank: Int? = null,
    val searchSnippet: String? = null,
    val searchMatchedFields: List<String> = emptyList(),
)

data class RuntimeMemoryEntry(
    val id: String,
    val content: String,
    val enabled: Boolean,
    val createdAtMillis: Long,
    val updatedAtMillis: Long,
    val source: RuntimeMemoryEntrySource? = null,
)

data class RuntimeMemoryEntrySource(
    val kind: String,
    val draftId: String,
    val summaryMethod: String,
    val session: RuntimeMemorySummaryDraftSession,
    val sourceMessageCount: Int,
    val sourceRange: String,
    val sourcePointers: List<RuntimeMemorySummaryDraftSourcePointer>,
)

data class RuntimeMemorySummaryDraft(
    val id: String,
    val session: RuntimeMemorySummaryDraftSession,
    val sourceMessageCount: Int,
    val sourceRange: String,
    val sourcePointers: List<RuntimeMemorySummaryDraftSourcePointer>,
    val summaryPreview: String,
)

data class RuntimeMemorySummaryDraftSession(
    val sessionId: String,
    val title: String,
    val modelId: String,
    val lastActivityAtMillis: Long?,
    val messageCount: Int,
    val inactiveSeconds: Long,
)

data class RuntimeMemorySummaryDraftSourcePointer(
    val sessionId: String,
    val messageIndex: Int,
    val role: String,
    val createdAtMillis: Long?,
    val excerpt: String,
)

data class RuntimeUiError(
    val code: String,
    val detail: String? = null,
    val diagnosticCode: String? = null,
    val technicalDetail: String? = null,
)
