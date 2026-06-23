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
    val chatSessions: List<RuntimeChatSession> = emptyList(),
    val archivedChatSessions: List<RuntimeChatSession> = emptyList(),
    val activeChatSessionId: String? = null,
    val messages: List<RuntimeChatMessage> = emptyList(),
    val chatInput: String = "",
    val isStreaming: Boolean = false,
    val activeRequestId: String? = null,
    val memoryEntries: List<RuntimeMemoryEntry> = emptyList(),
    val error: RuntimeUiError? = null,
)

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
    val providerModelId: String? = null,
    val installed: Boolean = true,
    val running: Boolean = false,
    val source: String? = null,
    val description: String? = null,
    val sizeBytes: Long? = null,
)

data class RuntimeProviderStatus(
    val id: String,
    val name: String,
    val available: Boolean,
)

data class RuntimeChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: String,
    val content: String,
    val reasoning: String = "",
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
