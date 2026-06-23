package com.localagentbridge.android.ui

import androidx.annotation.StringRes
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.localagentbridge.android.R
import com.localagentbridge.android.runtime.RuntimeChatMessage
import com.localagentbridge.android.runtime.RuntimeDiscoveredMac
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimeUiError
import com.localagentbridge.android.runtime.RuntimeUiState

@Composable
fun PairingScreen(
    state: RuntimeUiState,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onUseUsbReverse: () -> Unit,
    onUseEmulator: () -> Unit,
    onStartDiscovery: () -> Unit,
    onStopDiscovery: () -> Unit,
    onUseDiscoveredMac: (RuntimeDiscoveredMac) -> Unit,
    onForgetTrustedMac: () -> Unit,
    onScanPairingQr: () -> Unit,
    onConnect: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ScreenList(modifier) {
        item {
            ScreenHeader(
                title = R.string.pairing_title,
                subtitle = R.string.pairing_subtitle,
            )
        }
        item {
            QrPairingPanel(
                isConnecting = state.isConnecting,
                onScanPairingQr = onScanPairingQr,
            )
        }
        item {
            TrustedMacPanel(
                state = state,
                onForgetTrustedMac = onForgetTrustedMac,
            )
        }
        item {
            Button(
                onClick = onConnect,
                enabled = state.trustedMac != null && !state.isConnecting,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(
                    Icons.Filled.Link,
                    contentDescription = null,
                )
                Spacer(Modifier.width(8.dp))
                Text(if (state.isConnecting) stringResource(R.string.connecting) else stringResource(R.string.connect_runtime))
            }
        }
        if (state.trustedMac == null) {
            item {
                EmptyState(text = stringResource(R.string.connect_requires_pairing))
            }
        }
        item {
            DiscoveryPanel(
                state = state,
                onStartDiscovery = onStartDiscovery,
                onStopDiscovery = onStopDiscovery,
                onUseDiscoveredMac = onUseDiscoveredMac,
            )
        }
        item {
            EndpointPanel(
                state = state,
                onHostChange = onHostChange,
                onPortChange = onPortChange,
                onUseUsbReverse = onUseUsbReverse,
                onUseEmulator = onUseEmulator,
            )
        }
        item { ErrorText(state.error) }
    }
}

@Composable
private fun QrPairingPanel(
    isConnecting: Boolean,
    onScanPairingQr: () -> Unit,
) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(R.string.qr_pairing_title),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = stringResource(R.string.qr_pairing_detail),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
            Button(
                onClick = onScanPairingQr,
                enabled = !isConnecting,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(
                    Icons.Filled.Link,
                    contentDescription = null,
                )
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.scan_qr))
            }
            Text(
                text = stringResource(R.string.qr_pairing_security_note),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
            )
        }
    }
}

@Composable
fun ConnectionStatusScreen(
    state: RuntimeUiState,
    onRefreshHealth: () -> Unit,
    onDisconnect: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ScreenList(modifier) {
        item {
            ScreenHeader(
                title = R.string.status_title,
                subtitle = R.string.status_subtitle,
            )
        }
        item {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text(
                        text = if (state.isConnected) {
                            stringResource(R.string.status_connected_summary)
                        } else {
                            stringResource(R.string.status_disconnected_summary)
                        },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    StatusLine(
                        label = stringResource(R.string.runtime),
                        value = runtimeStatusLabel(state.runtimeStatus),
                    )
                    StatusLine(
                        label = stringResource(R.string.backend),
                        value = backendStatusLabel(state.backendAvailable),
                    )
                    StatusLine(
                        label = stringResource(R.string.providers),
                        value = providerStatusSummary(state),
                    )
                    StatusLine(
                        label = stringResource(R.string.endpoint),
                        value = "${state.macHost}:${state.macPort}",
                    )
                    StatusLine(
                        label = stringResource(R.string.connected),
                        value = if (state.isConnected) stringResource(R.string.yes) else stringResource(R.string.no),
                    )
                }
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onRefreshHealth,
                    enabled = state.isConnected,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(
                        Icons.Filled.Refresh,
                        contentDescription = null,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.health))
                }
                OutlinedButton(
                    onClick = onDisconnect,
                    enabled = state.isConnected,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(
                        Icons.Filled.Close,
                        contentDescription = null,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.disconnect))
                }
            }
        }
        item { ErrorText(state.error) }
    }
}

@Composable
fun ModelPickerScreen(
    state: RuntimeUiState,
    onRequestModels: () -> Unit,
    onSelectModel: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    ScreenList(modifier) {
        item {
            ScreenHeader(
                title = R.string.models_title,
                subtitle = R.string.models_subtitle,
            )
        }
        item {
            SelectedModelPanel(state = state)
        }
        item {
            Button(
                onClick = onRequestModels,
                enabled = state.isConnected && !state.isLoadingModels,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(
                    Icons.Filled.Refresh,
                    contentDescription = null,
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = if (state.isLoadingModels) {
                        stringResource(R.string.loading_models)
                    } else {
                        stringResource(R.string.load_models)
                    },
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (state.isLoadingModels) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    Text(
                        text = stringResource(R.string.loading_models),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
        }
        if (state.models.isEmpty() && !state.isLoadingModels) {
            item {
                EmptyStateCard(
                    title = if (state.isConnected) {
                        stringResource(R.string.no_models_connected_title)
                    } else {
                        stringResource(R.string.no_models_disconnected_title)
                    },
                    text = if (state.isConnected) {
                        stringResource(R.string.no_models_connected)
                    } else {
                        stringResource(R.string.no_models_disconnected)
                    },
                )
            }
        }
        items(state.models) { model ->
            ModelRow(
                model = model,
                selected = model.id == state.selectedModelId,
                isInstalling = model.id == state.installingModelId,
                onSelect = onSelectModel,
            )
        }
        item { ErrorText(state.error) }
    }
}

@Composable
fun ChatScreen(
    state: RuntimeUiState,
    onInputChange: (String) -> Unit,
    onSend: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val selectedModel = selectedModel(state)
    val listState = rememberLazyListState()
    val canSend = state.isConnected &&
        !state.isStreaming &&
        selectedModelIsUsable(state) &&
        state.chatInput.isNotBlank()

    LaunchedEffect(state.messages.size, state.messages.lastOrNull()?.content) {
        if (state.messages.isNotEmpty()) {
            listState.animateScrollToItem(state.messages.lastIndex)
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        ChatContextChips(
            state = state,
            selectedModel = selectedModel,
        )
        if (state.messages.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center,
            ) {
                ChatEmptyState(state)
            }
        } else {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                verticalArrangement = Arrangement.spacedBy(18.dp),
                contentPadding = PaddingValues(top = 10.dp, bottom = 12.dp),
            ) {
                items(state.messages) { message ->
                    ChatMessageRow(message)
                }
            }
        }
        ErrorText(state.error)
        ChatComposer(
            value = state.chatInput,
            enabled = !state.isStreaming,
            canSend = canSend,
            isStreaming = state.isStreaming,
            hint = chatInputHint(state),
            onInputChange = onInputChange,
            onSend = onSend,
            onCancel = onCancel,
        )
    }
}

@Composable
fun SettingsScreen(
    state: RuntimeUiState,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onUseUsbReverse: () -> Unit,
    onUseEmulator: () -> Unit,
    onForgetTrustedMac: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ScreenList(modifier) {
        item {
            ScreenHeader(
                title = R.string.settings_title,
                subtitle = R.string.settings_subtitle,
            )
        }
        item {
            CompanionOnlyPanel()
        }
        item {
            TrustedMacPanel(
                state = state,
                onForgetTrustedMac = onForgetTrustedMac,
            )
        }
        item {
            EndpointPanel(
                state = state,
                onHostChange = onHostChange,
                onPortChange = onPortChange,
                onUseUsbReverse = onUseUsbReverse,
                onUseEmulator = onUseEmulator,
            )
        }
        item { ErrorText(state.error) }
    }
}

@Composable
private fun ScreenList(
    modifier: Modifier,
    content: androidx.compose.foundation.lazy.LazyListScope.() -> Unit,
) {
    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
        contentPadding = PaddingValues(bottom = 24.dp),
        content = content,
    )
}

@Composable
private fun ScreenHeader(
    @StringRes title: Int,
    @StringRes subtitle: Int? = null,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            text = stringResource(title),
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
        )
        subtitle?.let {
            Text(
                text = stringResource(it),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
        }
    }
}

@Composable
private fun TrustedMacPanel(
    state: RuntimeUiState,
    onForgetTrustedMac: () -> Unit,
) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = if (state.trustedMac != null) Icons.Filled.CheckCircle else Icons.Filled.Link,
                    contentDescription = if (state.trustedMac != null) {
                        stringResource(R.string.trusted_mac)
                    } else {
                        stringResource(R.string.no_trusted_mac)
                    },
                    tint = if (state.trustedMac != null) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.secondary
                    },
                )
                Spacer(Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.trusted_mac),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                    Text(
                        text = state.trustedMac?.name ?: stringResource(R.string.no_trusted_mac),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            state.trustedMac?.let { trusted ->
                Text(
                    text = "${trusted.host}:${trusted.port}",
                    color = MaterialTheme.colorScheme.secondary,
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedButton(
                    onClick = onForgetTrustedMac,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.Close, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.forget))
                }
            } ?: Text(
                text = stringResource(R.string.trusted_mac_detail),
                color = MaterialTheme.colorScheme.secondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun EndpointPanel(
    state: RuntimeUiState,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onUseUsbReverse: () -> Unit,
    onUseEmulator: () -> Unit,
    @StringRes title: Int = R.string.advanced_connection,
) {
    val isExpanded = rememberSaveable { mutableStateOf(false) }

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { isExpanded.value = !isExpanded.value },
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = stringResource(title),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                    )
                    Text(
                        text = stringResource(R.string.advanced_connection_detail),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
                Spacer(Modifier.width(12.dp))
                FilledTonalIconButton(
                    onClick = { isExpanded.value = !isExpanded.value },
                ) {
                    Icon(
                        imageVector = if (isExpanded.value) {
                            Icons.Filled.KeyboardArrowUp
                        } else {
                            Icons.Filled.KeyboardArrowDown
                        },
                        contentDescription = stringResource(
                            if (isExpanded.value) {
                                R.string.hide_advanced_connection
                            } else {
                                R.string.show_advanced_connection
                            },
                        ),
                    )
                }
            }
            if (isExpanded.value) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = onUseUsbReverse,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(
                            Icons.Filled.PhoneAndroid,
                            contentDescription = null,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.usb_reverse))
                    }
                    OutlinedButton(
                        onClick = onUseEmulator,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(
                            Icons.Filled.Settings,
                            contentDescription = null,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.emulator))
                    }
                }
                OutlinedTextField(
                    value = state.macHost,
                    onValueChange = onHostChange,
                    label = { Text(stringResource(R.string.mac_runtime_host)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = state.macPort,
                    onValueChange = onPortChange,
                    label = { Text(stringResource(R.string.mac_runtime_port)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

@Composable
private fun DiscoveryPanel(
    state: RuntimeUiState,
    onStartDiscovery: () -> Unit,
    onStopDiscovery: () -> Unit,
    onUseDiscoveredMac: (RuntimeDiscoveredMac) -> Unit,
) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(R.string.discovered_macs),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Medium,
            )
            Text(
                text = stringResource(R.string.discovery_detail),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onStartDiscovery,
                    enabled = !state.isDiscovering,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.Refresh, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = if (state.isDiscovering) {
                            stringResource(R.string.discovering_macs)
                        } else {
                            stringResource(R.string.discover_macs)
                        },
                    )
                }
                OutlinedButton(
                    onClick = onStopDiscovery,
                    enabled = state.isDiscovering,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.Close, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.stop))
                }
            }
            if (state.isDiscovering) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            if (state.discoveredMacs.isEmpty()) {
                EmptyState(text = stringResource(R.string.no_discovered_macs))
            } else {
                LazyColumn(
                    modifier = Modifier.heightIn(max = 220.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.discoveredMacs) { peer ->
                        DiscoveredMacRow(peer = peer, onUse = onUseDiscoveredMac)
                    }
                }
            }
        }
    }
}

@Composable
private fun DiscoveredMacRow(peer: RuntimeDiscoveredMac, onUse: (RuntimeDiscoveredMac) -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(8.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = peer.serviceName,
                    style = MaterialTheme.typography.titleSmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = "${peer.host}:${peer.port}",
                    color = MaterialTheme.colorScheme.secondary,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            TextButton(onClick = { onUse(peer) }) {
                Text(stringResource(R.string.use))
            }
        }
    }
}

@Composable
private fun SelectedModelPanel(state: RuntimeUiState) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = stringResource(R.string.selected_model),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
            Text(
                text = selectedModelName(state),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = if (state.isConnected) {
                    stringResource(R.string.models_from_mac_runtime)
                } else {
                    stringResource(R.string.models_need_connection)
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
        }
    }
}

@Composable
private fun ModelRow(
    model: RuntimeModel,
    selected: Boolean,
    isInstalling: Boolean,
    onSelect: (String) -> Unit,
) {
    val cardModifier = if (model.installed) {
        Modifier
            .fillMaxWidth()
            .clickable { onSelect(model.id) }
    } else {
        Modifier.fillMaxWidth()
    }
    OutlinedCard(
        modifier = cardModifier,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = model.name,
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = modelStatusLine(model),
                        color = MaterialTheme.colorScheme.secondary,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (model.installed) {
                    RadioButton(selected = selected, onClick = { onSelect(model.id) })
                }
            }
            model.description?.takeIf { it.isNotBlank() }?.let { description ->
                Text(
                    text = description,
                    color = MaterialTheme.colorScheme.secondary,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (!model.installed) {
                Button(
                    onClick = { onSelect(model.id) },
                    enabled = !isInstalling,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.Refresh, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = if (isInstalling) {
                            stringResource(R.string.installing_model)
                        } else {
                            stringResource(R.string.install_model)
                        },
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (isInstalling) {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
            }
        }
    }
}

@Composable
private fun ChatContextChips(
    state: RuntimeUiState,
    selectedModel: RuntimeModel?,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        ChatModelChip(
            state = state,
            selectedModel = selectedModel,
            modifier = Modifier.weight(1f),
        )
        ChatStatusPill(state)
    }
}

@Composable
private fun ChatModelChip(
    state: RuntimeUiState,
    selectedModel: RuntimeModel?,
    modifier: Modifier = Modifier,
) {
    val supportingText = selectedModel?.let { model ->
        listOf(
            providerDisplayName(model.provider),
            modelSourceDisplayName(model.source),
        ).joinToString(" | ")
    } ?: if (state.isConnected) {
        stringResource(R.string.chat_select_model_from_mac)
    } else {
        stringResource(R.string.chat_needs_runtime)
    }

    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Filled.Link,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.size(18.dp),
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(1.dp),
            ) {
                Text(
                    text = selectedModel?.name ?: stringResource(R.string.model_none),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = supportingText,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun ChatEmptyState(state: RuntimeUiState) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Surface(
            modifier = Modifier.size(44.dp),
            shape = RoundedCornerShape(14.dp),
            color = if (state.isConnected) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.errorContainer
            },
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(
                    imageVector = if (state.isConnected) Icons.Filled.Link else Icons.Filled.Close,
                    contentDescription = null,
                    tint = if (state.isConnected) {
                        MaterialTheme.colorScheme.onPrimaryContainer
                    } else {
                        MaterialTheme.colorScheme.onErrorContainer
                    },
                )
            }
        }
        Column(
            verticalArrangement = Arrangement.spacedBy(6.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = chatEmptyTitle(state),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = chatEmptyText(state),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
        }
        if (state.isStreaming) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }
    }
}

@Composable
private fun ChatMessageRow(message: RuntimeChatMessage) {
    val isUser = message.role == "user"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        if (isUser) {
            Surface(
                modifier = Modifier.widthIn(max = 320.dp),
                shape = RoundedCornerShape(
                    topStart = 18.dp,
                    topEnd = 6.dp,
                    bottomStart = 18.dp,
                    bottomEnd = 18.dp,
                ),
                color = MaterialTheme.colorScheme.primaryContainer,
            ) {
                Text(
                    text = message.content,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 9.dp),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                )
            }
        } else {
            AssistantMessage(message)
        }
    }
}

@Composable
private fun AssistantMessage(message: RuntimeChatMessage) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.Top,
    ) {
        AssistantAvatar()
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = stringResource(R.string.role_assistant),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.secondary,
                fontWeight = FontWeight.Medium,
            )
            Column(
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = message.content.ifBlank { stringResource(R.string.assistant_typing) },
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                if (message.content.isBlank()) {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
            }
        }
    }
}

@Composable
private fun AssistantAvatar() {
    Surface(
        modifier = Modifier.size(30.dp),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                text = stringResource(R.string.role_assistant_initial),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

@Composable
private fun ChatStatusPill(state: RuntimeUiState) {
    val text = when {
        state.isStreaming -> stringResource(R.string.chat_status_streaming)
        state.isConnected -> stringResource(R.string.chat_status_connected)
        else -> stringResource(R.string.chat_status_disconnected)
    }
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = if (state.isConnected) {
            MaterialTheme.colorScheme.primaryContainer
        } else {
            MaterialTheme.colorScheme.errorContainer
        },
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            style = MaterialTheme.typography.labelSmall,
            color = if (state.isConnected) {
                MaterialTheme.colorScheme.onPrimaryContainer
            } else {
                MaterialTheme.colorScheme.onErrorContainer
            },
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun ChatComposer(
    value: String,
    enabled: Boolean,
    canSend: Boolean,
    isStreaming: Boolean,
    hint: String,
    onInputChange: (String) -> Unit,
    onSend: () -> Unit,
    onCancel: () -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        tonalElevation = 2.dp,
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier.padding(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (isStreaming) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.Bottom,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = value,
                    onValueChange = onInputChange,
                    placeholder = { Text(stringResource(R.string.chat_composer_placeholder)) },
                    singleLine = false,
                    minLines = 1,
                    maxLines = 6,
                    modifier = Modifier.weight(1f),
                    enabled = enabled,
                    shape = RoundedCornerShape(22.dp),
                )
                if (isStreaming) {
                    FilledIconButton(
                        onClick = onCancel,
                        enabled = true,
                        modifier = Modifier.size(48.dp),
                    ) {
                        Icon(
                            Icons.Filled.Close,
                            contentDescription = stringResource(R.string.content_desc_cancel_generation),
                        )
                    }
                } else {
                    FilledIconButton(
                        onClick = onSend,
                        enabled = canSend,
                        modifier = Modifier.size(48.dp),
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.Send,
                            contentDescription = stringResource(R.string.content_desc_send),
                        )
                    }
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = hint,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                if (isStreaming) {
                    TextButton(onClick = onCancel) {
                        Text(stringResource(R.string.cancel))
                    }
                }
            }
        }
    }
}

@Composable
private fun CompanionOnlyPanel() {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = stringResource(R.string.companion_only_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
            Text(
                text = stringResource(R.string.companion_only_detail),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
    }
}

@Composable
private fun StatusLine(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.Medium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        HorizontalDivider()
    }
}

@Composable
private fun EmptyState(text: String) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(16.dp),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.secondary,
        )
    }
}

@Composable
private fun EmptyStateCard(title: String, text: String) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Medium,
            )
            Text(
                text = text,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
        }
    }
}

@Composable
private fun ErrorText(error: RuntimeUiError?) {
    if (error != null) {
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(8.dp),
            color = MaterialTheme.colorScheme.errorContainer,
        ) {
            Row(
                modifier = Modifier.padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.Filled.Error,
                    contentDescription = stringResource(R.string.content_desc_error),
                    tint = MaterialTheme.colorScheme.onErrorContainer,
                )
                Spacer(Modifier.width(8.dp))
                Column {
                    Text(
                        text = stringResource(R.string.error_title),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                    Text(
                        text = runtimeErrorLabel(error),
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                    error.detail?.takeIf { it.isNotBlank() }?.let { detail ->
                        Text(
                            text = stringResource(R.string.error_detail, detail),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun selectedModelName(state: RuntimeUiState): String {
    return selectedModel(state)?.name
        ?: state.selectedModelId
        ?: stringResource(R.string.model_none)
}

private fun selectedModel(state: RuntimeUiState): RuntimeModel? {
    val selectedId = state.selectedModelId ?: return null
    return state.models.firstOrNull { it.id == selectedId }
}

private fun selectedModelIsUsable(state: RuntimeUiState): Boolean {
    val selectedId = state.selectedModelId ?: return false
    return state.models.firstOrNull { it.id == selectedId }?.installed != false
}

@Composable
private fun chatInputHint(state: RuntimeUiState): String {
    return when {
        !state.isConnected -> stringResource(R.string.chat_hint_connect)
        state.selectedModelId == null -> stringResource(R.string.chat_hint_select_model)
        !selectedModelIsUsable(state) -> stringResource(R.string.chat_hint_install_model)
        state.isStreaming -> stringResource(R.string.chat_hint_wait_for_stream)
        state.chatInput.isBlank() -> stringResource(R.string.chat_hint_enter_message)
        else -> stringResource(R.string.chat_hint_ready)
    }
}

@Composable
private fun chatEmptyTitle(state: RuntimeUiState): String {
    return when {
        !state.isConnected -> stringResource(R.string.empty_chat_disconnected_title)
        state.selectedModelId == null -> stringResource(R.string.empty_chat_no_model_title)
        state.isStreaming -> stringResource(R.string.empty_chat_streaming_title)
        else -> stringResource(R.string.empty_chat_ready_title)
    }
}

@Composable
private fun chatEmptyText(state: RuntimeUiState): String {
    return when {
        !state.isConnected -> stringResource(R.string.empty_chat_disconnected)
        state.selectedModelId == null -> stringResource(R.string.empty_chat_no_model)
        state.isStreaming -> stringResource(R.string.empty_chat_streaming)
        else -> stringResource(R.string.empty_chat_ready)
    }
}

@Composable
private fun runtimeErrorLabel(error: RuntimeUiError): String {
    return when (error.code) {
        "invalid_endpoint" -> stringResource(R.string.error_invalid_endpoint)
        "connection_failed" -> stringResource(R.string.error_connection_failed)
        "discovery_failed" -> stringResource(R.string.error_discovery_failed)
        "invalid_pairing_qr" -> stringResource(R.string.error_invalid_pairing_qr)
        "qr_scan_failed" -> stringResource(R.string.error_qr_scan_failed)
        "pair_first" -> stringResource(R.string.error_pair_first)
        "pairing_required" -> stringResource(R.string.error_pairing_required)
        "pairing_rejected" -> stringResource(R.string.error_pairing_rejected)
        "authentication_required" -> stringResource(R.string.error_authentication_required)
        "authentication_failed" -> stringResource(R.string.error_authentication_failed)
        "device_identity_failed" -> stringResource(R.string.error_device_identity_failed)
        "select_model" -> stringResource(R.string.error_select_model)
        "connect_first" -> stringResource(R.string.error_connect_first)
        "receive_failed" -> stringResource(R.string.error_receive_failed)
        "generation_cancelled" -> stringResource(R.string.error_generation_cancelled)
        "runtime_error" -> stringResource(R.string.error_runtime_error)
        "send_failed" -> stringResource(R.string.error_send_failed)
        "invalid_payload" -> stringResource(R.string.error_invalid_payload)
        "install_model_first" -> stringResource(R.string.error_install_model_first)
        "model_install_failed" -> stringResource(R.string.error_model_install_failed)
        "backend_unavailable" -> stringResource(R.string.error_backend_unavailable)
        "generation_not_found" -> stringResource(R.string.error_generation_not_found)
        "transport_error" -> stringResource(R.string.error_transport_error)
        "internal_error" -> stringResource(R.string.error_internal_error)
        else -> stringResource(R.string.error_unknown)
    }
}

@Composable
private fun modelStatusLine(model: RuntimeModel): String {
    val installState = when {
        model.running -> stringResource(R.string.model_running)
        model.installed -> stringResource(R.string.model_installed)
        else -> stringResource(R.string.model_available_to_install)
    }
    val providerText = stringResource(R.string.model_provider_value, providerDisplayName(model.provider))
    val sourceText = stringResource(R.string.model_source_value, modelSourceDisplayName(model.source))
    val sizeText = model.sizeBytes?.let { stringResource(R.string.model_size_value, formatSizeBytes(it)) }
    return listOfNotNull(installState, providerText, sourceText, sizeText).joinToString(" | ")
}

@Composable
private fun providerStatusSummary(state: RuntimeUiState): String {
    if (state.providerStatuses.isEmpty()) {
        return backendStatusLabel(state.backendAvailable)
    }
    val available = stringResource(R.string.backend_available)
    val unavailable = stringResource(R.string.backend_unavailable)
    return state.providerStatuses.joinToString(" | ") { provider ->
        val status = if (provider.available) available else unavailable
        "${provider.name}: $status"
    }
}

@Composable
private fun providerDisplayName(provider: String?): String {
    return when (provider?.lowercase()) {
        "lm_studio" -> "LM Studio"
        "ollama" -> "Ollama"
        "aggregate" -> stringResource(R.string.provider_local_runtime)
        null, "" -> stringResource(R.string.status_unknown)
        else -> provider.orEmpty()
    }
}

@Composable
private fun modelSourceDisplayName(source: String?): String {
    return when (source?.lowercase()) {
        "local" -> stringResource(R.string.model_source_local)
        "cloud" -> stringResource(R.string.model_source_cloud)
        null, "" -> stringResource(R.string.status_unknown)
        else -> source.orEmpty()
    }
}

private fun formatSizeBytes(sizeBytes: Long): String {
    val units = listOf("B", "KB", "MB", "GB", "TB")
    var value = sizeBytes.toDouble()
    var unitIndex = 0
    while (value >= 1024 && unitIndex < units.lastIndex) {
        value /= 1024
        unitIndex += 1
    }
    return if (unitIndex == 0) {
        "${sizeBytes} ${units[unitIndex]}"
    } else {
        "%.1f %s".format(value, units[unitIndex])
    }
}

@Composable
private fun runtimeStatusLabel(status: String): String {
    return when (status.lowercase()) {
        "disconnected" -> stringResource(R.string.status_disconnected)
        "connecting" -> stringResource(R.string.status_connecting)
        "connected" -> stringResource(R.string.status_connected)
        "authenticated" -> stringResource(R.string.status_authenticated)
        "failed" -> stringResource(R.string.status_failed)
        "ok" -> stringResource(R.string.status_ok)
        else -> stringResource(R.string.status_unknown)
    }
}

@Composable
private fun backendStatusLabel(available: Boolean?): String {
    return when (available) {
        true -> stringResource(R.string.backend_available)
        false -> stringResource(R.string.backend_unavailable)
        null -> stringResource(R.string.status_unknown)
    }
}
