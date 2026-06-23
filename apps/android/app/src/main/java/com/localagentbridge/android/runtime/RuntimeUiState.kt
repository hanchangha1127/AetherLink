package com.localagentbridge.android.runtime

import java.util.UUID

data class RuntimeUiState(
    val macHost: String = "127.0.0.1",
    val macPort: String = "43170",
    val trustedMac: RuntimeTrustedMac? = null,
    val discoveredMacs: List<RuntimeDiscoveredMac> = emptyList(),
    val isDiscovering: Boolean = false,
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
    val messages: List<RuntimeChatMessage> = emptyList(),
    val chatInput: String = "",
    val pendingAttachments: List<RuntimePendingAttachment> = emptyList(),
    val isStreaming: Boolean = false,
    val isLoadingSuggestions: Boolean = false,
    val activeRequestId: String? = null,
    val memoryEntries: List<RuntimeMemoryEntry> = emptyList(),
    val selectedLanguageTag: String = RuntimeAppLanguage.English.languageTag,
    val error: RuntimeUiError? = null,
)

enum class RuntimeAppLanguage(val languageTag: String) {
    System(""),
    English("en"),
    Korean("ko"),
    Japanese("ja"),
    SimplifiedChinese("zh-CN"),
    French("fr");

    companion object {
        val supportedLanguageTags: Set<String> = entries.map { it.languageTag }.toSet()

        fun normalizeLanguageTag(languageTag: String): String {
            val trimmed = languageTag.trim()
            return supportedLanguageTags.firstOrNull { it.equals(trimmed, ignoreCase = true) }
                ?: System.languageTag
        }
    }
}

data class RuntimeTrustedMac(
    val deviceId: String,
    val name: String,
    val host: String,
    val port: Int,
)

data class RuntimeDiscoveredMac(
    val serviceName: String,
    val host: String,
    val port: Int,
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
    val source: String? = null,
    val description: String? = null,
    val sizeBytes: Long? = null,
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
    val suggestions: List<String> = emptyList(),
)

data class RuntimePendingAttachment(
    val id: String = UUID.randomUUID().toString(),
    val type: String,
    val name: String,
    val mimeType: String,
    val sizeBytes: Long,
    val dataBase64: String,
)

data class RuntimeChatSession(
    val id: String,
    val title: String,
    val updatedAtMillis: Long,
    val messageCount: Int,
    val archivedAtMillis: Long? = null,
)

data class RuntimeMemoryEntry(
    val id: String,
    val content: String,
    val enabled: Boolean,
    val createdAtMillis: Long,
    val updatedAtMillis: Long,
)

data class RuntimeUiError(
    val code: String,
    val detail: String? = null,
)
