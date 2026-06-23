package com.localagentbridge.android.feature.chat

data class ChatMessage(
    val role: String,
    val content: String,
)

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val input: String = "",
    val isStreaming: Boolean = false,
    val activeRequestId: String? = null,
    val errorCode: String? = null,
)
