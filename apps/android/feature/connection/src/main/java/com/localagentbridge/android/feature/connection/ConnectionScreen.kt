package com.localagentbridge.android.feature.connection

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.localagentbridge.android.core.transport.DiscoveredMac

@Composable
fun ConnectionScreen(
    state: ConnectionUiState,
    onDiscover: () -> Unit,
    onSelect: (DiscoveredMac) -> Unit,
    onPairingCodeChange: (String) -> Unit,
    onPair: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(stringResource(R.string.feature_connection_title), style = MaterialTheme.typography.titleLarge)
        Text(connectionStatusText(state), color = MaterialTheme.colorScheme.secondary)
        Button(onClick = onDiscover) {
            Text(stringResource(R.string.feature_connection_discover_mac))
        }

        state.discoveredMacs.forEach { mac ->
            MacRow(mac = mac, selected = mac == state.selectedMac, onClick = { onSelect(mac) })
        }

        OutlinedTextField(
            value = state.pairingCode,
            onValueChange = onPairingCodeChange,
            label = { Text(stringResource(R.string.feature_connection_pairing_code_label)) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        Button(onClick = onPair, enabled = state.selectedMac != null) {
            Text(stringResource(R.string.feature_connection_pair))
        }

        state.errorCode?.let {
            Text(connectionErrorText(it), color = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun MacRow(mac: DiscoveredMac, selected: Boolean, onClick: () -> Unit) {
    Surface(
        tonalElevation = if (selected) 3.dp else 0.dp,
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(modifier = Modifier.padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text(mac.serviceName, style = MaterialTheme.typography.titleMedium)
                Text("${mac.host}:${mac.port}", style = MaterialTheme.typography.bodySmall)
            }
            if (selected) Text(stringResource(R.string.feature_connection_selected))
        }
    }
}

@Composable
private fun connectionStatusText(state: ConnectionUiState): String {
    return when (state.statusCode) {
        "discovery_ready" -> stringResource(R.string.feature_connection_status_discovery_ready)
        "selected" -> stringResource(R.string.feature_connection_status_selected, state.statusDetail.orEmpty())
        "paired" -> stringResource(R.string.feature_connection_status_paired, state.statusDetail.orEmpty())
        else -> stringResource(R.string.feature_connection_status_not_connected)
    }
}

@Composable
private fun connectionErrorText(code: String): String {
    return when (code) {
        "select_mac_first" -> stringResource(R.string.feature_connection_error_select_mac_first)
        "invalid_pairing_code" -> stringResource(R.string.feature_connection_error_invalid_pairing_code)
        else -> stringResource(R.string.feature_connection_error_unknown)
    }
}
