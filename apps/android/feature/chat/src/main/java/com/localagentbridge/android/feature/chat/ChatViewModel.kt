package com.localagentbridge.android.feature.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

class ChatViewModel : ViewModel() {
    private val mutableState = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = mutableState.asStateFlow()
    private var streamJob: Job? = null

    fun updateInput(input: String) {
        mutableState.update { it.copy(input = input) }
    }

    fun send(selectedModelId: String?) {
	        val text = state.value.input.trim()
	        if (text.isEmpty()) return
	        if (selectedModelId == null) {
	            mutableState.update { it.copy(errorCode = "select_model") }
	            return
	        }

        val requestId = UUID.randomUUID().toString()
        mutableState.update {
            it.copy(
                input = "",
                isStreaming = true,
                activeRequestId = requestId,
	                errorCode = null,
	                messages = it.messages + ChatMessage("user", text) + ChatMessage("assistant", ""),
            )
        }

        streamJob?.cancel()
        streamJob = viewModelScope.launch {
            val chunks = listOf("Streaming ", "from Mac ", "companion ", "will appear here.")
            chunks.forEach { chunk ->
                delay(250)
                mutableState.update { current ->
                    val updated = current.messages.dropLast(1) +
                        current.messages.last().copy(content = current.messages.last().content + chunk)
                    current.copy(messages = updated)
                }
            }
            mutableState.update { it.copy(isStreaming = false, activeRequestId = null) }
        }
    }

    fun cancel() {
        streamJob?.cancel()
        mutableState.update {
            it.copy(
	                isStreaming = false,
	                activeRequestId = null,
	                errorCode = "generation_cancelled",
	            )
	        }
    }
}
