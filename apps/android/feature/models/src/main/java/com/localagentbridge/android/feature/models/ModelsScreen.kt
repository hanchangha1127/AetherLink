package com.localagentbridge.android.feature.models

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp

@Composable
fun ModelsScreen(
    state: ModelsUiState,
    onRefresh: () -> Unit,
    onSelectModel: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(stringResource(R.string.feature_models_title), style = MaterialTheme.typography.titleLarge)
        Button(onClick = onRefresh) {
            Text(stringResource(R.string.feature_models_load_models))
        }
        state.models.forEach { model ->
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSelectModel(model.id) },
            ) {
                Row(modifier = Modifier.padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column {
                        Text(model.name, style = MaterialTheme.typography.titleMedium)
                        Text(model.id, style = MaterialTheme.typography.bodySmall)
                    }
                    RadioButton(
                        selected = model.id == state.selectedModelId,
                        onClick = { onSelectModel(model.id) },
                    )
                }
            }
        }
        state.error?.let { Text(stringResource(R.string.feature_models_error, it), color = MaterialTheme.colorScheme.error) }
    }
}
