package com.localagentbridge.android.feature.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp

@Composable
fun ChatScreen(
    state: ChatUiState,
    selectedModelId: String?,
    onInputChange: (String) -> Unit,
    onSend: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(stringResource(R.string.feature_chat_title), style = MaterialTheme.typography.titleLarge)
        Text(
            stringResource(R.string.feature_chat_model_value, selectedModelId ?: stringResource(R.string.feature_chat_model_none)),
            color = MaterialTheme.colorScheme.secondary,
        )
        LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.messages) { message ->
                Text("${message.role}: ${message.content}")
            }
        }
        state.errorCode?.let { Text(chatErrorText(it), color = MaterialTheme.colorScheme.error) }
        OutlinedTextField(
            value = state.input,
            onValueChange = onInputChange,
            label = { Text(stringResource(R.string.feature_chat_message)) },
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onSend, enabled = !state.isStreaming) {
                Text(stringResource(R.string.feature_chat_send))
            }
            Button(onClick = onCancel, enabled = state.isStreaming) {
                Text(stringResource(R.string.feature_chat_cancel))
            }
        }
    }
}

@Composable
private fun chatErrorText(code: String): String {
    return when (code) {
        "select_model" -> stringResource(R.string.feature_chat_error_select_model)
        "generation_cancelled" -> stringResource(R.string.feature_chat_error_generation_cancelled)
        else -> stringResource(R.string.feature_chat_error_unknown)
    }
}
