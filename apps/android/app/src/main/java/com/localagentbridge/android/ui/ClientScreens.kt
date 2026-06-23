package com.localagentbridge.android.ui

import android.widget.Toast
import androidx.annotation.StringRes
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.localagentbridge.android.R
import com.localagentbridge.android.runtime.RuntimeAppLanguage
import com.localagentbridge.android.runtime.RuntimeChatMessage
import com.localagentbridge.android.runtime.RuntimeDiscoveredMac
import com.localagentbridge.android.runtime.RuntimeMemoryEntry
import com.localagentbridge.android.runtime.RuntimeUiError
import com.localagentbridge.android.runtime.RuntimeUiState

@Composable
fun PairingScreen(
    state: RuntimeUiState,
    onStartDiscovery: () -> Unit,
    onStopDiscovery: () -> Unit,
    onUseDiscoveredMac: (RuntimeDiscoveredMac) -> Unit,
    onForgetTrustedMac: () -> Unit,
    onScanPairingQr: () -> Unit,
    onConnect: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val hapticFeedback = LocalHapticFeedback.current

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
            PairingConnectButton(
                state = state,
                onConnect = onConnect,
            )
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
        item { ErrorText(state.error) }
    }
}

@Composable
private fun QrPairingPanel(
    isConnecting: Boolean,
    onScanPairingQr: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current

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
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onScanPairingQr()
                },
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
private fun PairingConnectButton(
    state: RuntimeUiState,
    onConnect: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current

    Button(
        onClick = {
            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
            onConnect()
        },
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

@Composable
fun ConnectionStatusScreen(
    state: RuntimeUiState,
    onRefreshHealth: () -> Unit,
    onDisconnect: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val hapticFeedback = LocalHapticFeedback.current

    ScreenList(modifier) {
        item {
            ScreenHeader(
                title = R.string.status_title,
                subtitle = R.string.status_subtitle,
            )
        }
        item {
            ConnectionStatusPanel(state = state)
        }
        item {
            ConnectionStatusActions(
                state = state,
                onRefreshHealth = onRefreshHealth,
                onDisconnect = onDisconnect,
            )
        }
        item { ErrorText(state.error) }
    }
}

@Composable
private fun ConnectionStatusPanel(state: RuntimeUiState) {
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
                value = state.trustedMac?.let { trusted -> "${trusted.host}:${trusted.port}" }
                    ?: "${state.macHost}:${state.macPort}",
            )
            StatusLine(
                label = stringResource(R.string.connected),
                value = if (state.isConnected) stringResource(R.string.yes) else stringResource(R.string.no),
            )
        }
    }
}

@Composable
private fun ConnectionStatusActions(
    state: RuntimeUiState,
    onRefreshHealth: () -> Unit,
    onDisconnect: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(
            onClick = {
                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                onRefreshHealth()
            },
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
            onClick = {
                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                onDisconnect()
            },
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

@Composable
fun ChatScreen(
    state: RuntimeUiState,
    onInputChange: (String) -> Unit,
    onSend: () -> Unit,
    onCancel: () -> Unit,
    onConnect: () -> Unit,
    onRequestModels: () -> Unit,
    modifier: Modifier = Modifier,
) {
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
        if (state.messages.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center,
            ) {
                ChatEmptyState(
                    state = state,
                    onInputChange = onInputChange,
                    onConnect = onConnect,
                    onRequestModels = onRequestModels,
                )
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
                items(
                    items = state.messages,
                    key = { message -> message.id },
                ) { message ->
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
    onStartDiscovery: () -> Unit,
    onStopDiscovery: () -> Unit,
    onUseDiscoveredMac: (RuntimeDiscoveredMac) -> Unit,
    onForgetTrustedMac: () -> Unit,
    onScanPairingQr: () -> Unit,
    onConnect: () -> Unit,
    onRefreshHealth: () -> Unit,
    onDisconnect: () -> Unit,
    onSetLanguageTag: (String) -> Unit,
    onAddMemoryEntry: (String) -> Unit,
    onRemoveMemoryEntry: (String) -> Unit,
    onSetMemoryEntryEnabled: (String, Boolean) -> Unit,
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
            PairingConnectButton(
                state = state,
                onConnect = onConnect,
            )
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
            ScreenHeader(
                title = R.string.status_title,
                subtitle = R.string.status_subtitle,
            )
        }
        item {
            ConnectionStatusPanel(state = state)
        }
        item {
            ConnectionStatusActions(
                state = state,
                onRefreshHealth = onRefreshHealth,
                onDisconnect = onDisconnect,
            )
        }
        item {
            EndpointPanel(
                state = state,
                onHostChange = onHostChange,
                onPortChange = onPortChange,
                onUseUsbReverse = onUseUsbReverse,
                onUseEmulator = onUseEmulator,
                title = R.string.runtime_endpoint,
            )
        }
        item {
            AppPreferencesPanel(
                selectedLanguageTag = state.selectedLanguageTag,
                onSetLanguageTag = onSetLanguageTag,
            )
        }
        item {
            MemoryPanel(
                entries = state.memoryEntries,
                onAddMemoryEntry = onAddMemoryEntry,
                onRemoveMemoryEntry = onRemoveMemoryEntry,
                onSetMemoryEntryEnabled = onSetMemoryEntryEnabled,
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
    val hapticFeedback = LocalHapticFeedback.current

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
                    onClick = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        onForgetTrustedMac()
                    },
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
    val hapticFeedback = LocalHapticFeedback.current
    val toggleExpanded = {
        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
        isExpanded.value = !isExpanded.value
    }

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
                    .clickable { toggleExpanded() },
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
                    onClick = { toggleExpanded() },
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
                        onClick = {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                            onUseUsbReverse()
                        },
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
                        onClick = {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                            onUseEmulator()
                        },
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
    val hapticFeedback = LocalHapticFeedback.current

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
                    onClick = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        onStartDiscovery()
                    },
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
                    onClick = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        onStopDiscovery()
                    },
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
    val hapticFeedback = LocalHapticFeedback.current

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
            TextButton(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onUse(peer)
                },
            ) {
                Text(stringResource(R.string.use))
            }
        }
    }
}

@Composable
private fun ChatEmptyState(
    state: RuntimeUiState,
    onInputChange: (String) -> Unit,
    onConnect: () -> Unit,
    onRequestModels: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val showStarterPrompts = state.isConnected &&
        !state.isConnecting &&
        !state.isLoadingModels &&
        !state.isStreaming &&
        selectedModelIsUsable(state)
    val starterPrompts = listOf(
        stringResource(R.string.chat_starter_prompt_explain_project),
        stringResource(R.string.chat_starter_prompt_summarize_plan),
        stringResource(R.string.chat_starter_prompt_debug_issue),
        stringResource(R.string.chat_starter_prompt_compare_options),
    )

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
        if (showStarterPrompts) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                starterPrompts.forEach { prompt ->
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                            onInputChange(prompt)
                        },
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                    ) {
                        Text(
                            text = prompt,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
        if (!state.isConnected && state.trustedMac != null) {
            Button(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onConnect()
                },
                enabled = !state.isConnecting,
            ) {
                Icon(Icons.Filled.Link, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(
                    text = if (state.isConnecting) {
                        stringResource(R.string.connecting)
                    } else {
                        stringResource(R.string.connect_runtime)
                    },
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (state.isConnected && state.models.isEmpty()) {
            Button(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onRequestModels()
                },
                enabled = !state.isLoadingModels,
            ) {
                Icon(Icons.Filled.Refresh, contentDescription = null)
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
            if (state.isLoadingModels) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
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
            Column(
                modifier = Modifier.widthIn(max = 320.dp),
                horizontalAlignment = Alignment.End,
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Surface(
                    shape = RoundedCornerShape(
                        topStart = 18.dp,
                        topEnd = 6.dp,
                        bottomStart = 18.dp,
                        bottomEnd = 18.dp,
                    ),
                    color = MaterialTheme.colorScheme.primaryContainer,
                ) {
                    MessageContent(
                        content = message.content,
                        textColor = MaterialTheme.colorScheme.onPrimaryContainer,
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 9.dp),
                    )
                }
                MessageCopyButton(textToCopy = message.content)
            }
        } else {
            AssistantMessage(message)
        }
    }
}

@Composable
private fun AssistantMessage(message: RuntimeChatMessage) {
    val hasReasoning = message.reasoning.isNotBlank()
    val isReasoningExpanded = rememberSaveable(message.id) { mutableStateOf(false) }
    val textToCopy = message.content.ifBlank { message.reasoning }

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
                if (hasReasoning) {
                    AssistantReasoning(
                        reasoning = message.reasoning,
                        expanded = isReasoningExpanded.value,
                        onExpandedChange = { isReasoningExpanded.value = it },
                    )
                }
                MessageContent(
                    content = message.content.ifBlank { stringResource(R.string.assistant_typing) },
                    textColor = MaterialTheme.colorScheme.onSurface,
                )
                if (message.content.isBlank()) {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
            }
            MessageCopyButton(textToCopy = textToCopy)
        }
    }
}

@Composable
private fun MessageContent(
    content: String,
    textColor: androidx.compose.ui.graphics.Color,
    modifier: Modifier = Modifier,
) {
    val parts = parseMessageContent(content)

    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        parts.forEach { part ->
            when (part) {
                is MessageContentPart.Text -> {
                    Text(
                        text = part.text,
                        style = MaterialTheme.typography.bodyLarge,
                        color = textColor,
                    )
                }
                is MessageContentPart.Code -> {
                    CodeBlock(
                        code = part.code,
                        language = part.language,
                    )
                }
            }
        }
    }
}

@Composable
private fun CodeBlock(
    code: String,
    language: String?,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f),
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (language != null) {
                    Text(
                        text = language,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                } else {
                    Spacer(modifier = Modifier.weight(1f))
                }
                MessageCopyButton(textToCopy = code)
            }
            Text(
                text = code,
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                softWrap = false,
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
            )
        }
    }
}

@Composable
private fun MessageCopyButton(textToCopy: String) {
    val clipboardManager = LocalClipboardManager.current
    val context = LocalContext.current
    val hapticFeedback = LocalHapticFeedback.current
    val copiedMessage = stringResource(R.string.message_copied)

    TextButton(
        onClick = {
            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
            clipboardManager.setText(AnnotatedString(textToCopy))
            Toast.makeText(context, copiedMessage, Toast.LENGTH_SHORT).show()
        },
        enabled = textToCopy.isNotBlank(),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
    ) {
        Icon(
            imageVector = Icons.Filled.ContentCopy,
            contentDescription = stringResource(R.string.copy_message),
            modifier = Modifier.size(16.dp),
        )
    }
}

private sealed interface MessageContentPart {
    data class Text(val text: String) : MessageContentPart
    data class Code(val language: String?, val code: String) : MessageContentPart
}

private fun parseMessageContent(content: String): List<MessageContentPart> {
    val parts = mutableListOf<MessageContentPart>()
    var cursor = 0

    while (cursor < content.length) {
        val fenceStart = content.indexOf("```", startIndex = cursor)
        if (fenceStart == -1) {
            addTextPart(parts, content.substring(cursor))
            break
        }

        addTextPart(parts, content.substring(cursor, fenceStart))

        val languageStart = fenceStart + 3
        val languageEnd = content.indexOf('\n', startIndex = languageStart)
        if (languageEnd == -1) {
            addTextPart(parts, content.substring(fenceStart))
            break
        }

        val language = content
            .substring(languageStart, languageEnd)
            .trim()
            .takeIf { it.isNotEmpty() }
        val codeStart = languageEnd + 1
        val fenceEnd = content.indexOf("```", startIndex = codeStart)

        if (fenceEnd == -1) {
            parts += MessageContentPart.Code(
                language = language,
                code = content.substring(codeStart).trimEnd('\n'),
            )
            break
        }

        parts += MessageContentPart.Code(
            language = language,
            code = content.substring(codeStart, fenceEnd).trimEnd('\n'),
        )
        cursor = fenceEnd + 3
        if (cursor < content.length && content[cursor] == '\n') {
            cursor += 1
        }
    }

    return parts.ifEmpty { listOf(MessageContentPart.Text(content)) }
}

private fun addTextPart(
    parts: MutableList<MessageContentPart>,
    text: String,
) {
    val trimmed = text.trim('\n')
    if (trimmed.isNotBlank()) {
        parts += MessageContentPart.Text(trimmed)
    }
}

@Composable
private fun AssistantReasoning(
    reasoning: String,
    expanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(R.string.assistant_reasoning_label),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.secondary,
                )
                TextButton(
                    onClick = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        onExpandedChange(!expanded)
                    },
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                ) {
                    Icon(
                        imageVector = if (expanded) {
                            Icons.Filled.KeyboardArrowUp
                        } else {
                            Icons.Filled.KeyboardArrowDown
                        },
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Spacer(modifier = Modifier.width(2.dp))
                    Text(
                        text = stringResource(
                            if (expanded) {
                                R.string.assistant_reasoning_hide
                            } else {
                                R.string.assistant_reasoning_show
                            }
                        ),
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }
            Text(
                text = reasoning,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = if (expanded) Int.MAX_VALUE else 2,
                overflow = TextOverflow.Ellipsis,
            )
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
    val hapticFeedback = LocalHapticFeedback.current
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
                        onClick = {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                            onCancel()
                        },
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
                        onClick = {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                            onSend()
                        },
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
                    TextButton(
                        onClick = {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                            onCancel()
                        },
                    ) {
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
private fun AppPreferencesPanel(
    selectedLanguageTag: String,
    onSetLanguageTag: (String) -> Unit,
) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(R.string.preferences_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                StatusLine(
                    label = stringResource(R.string.appearance_title),
                    value = stringResource(R.string.appearance_system),
                )
                Text(
                    text = stringResource(R.string.appearance_system_detail),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            LanguagePreferenceSelector(
                selectedLanguageTag = selectedLanguageTag,
                onSetLanguageTag = onSetLanguageTag,
            )
        }
    }
}

@Composable
private fun LanguagePreferenceSelector(
    selectedLanguageTag: String,
    onSetLanguageTag: (String) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val options = listOf(
        RuntimeAppLanguage.System to R.string.language_system,
        RuntimeAppLanguage.English to R.string.language_english,
        RuntimeAppLanguage.Korean to R.string.language_korean,
        RuntimeAppLanguage.Japanese to R.string.language_japanese,
        RuntimeAppLanguage.SimplifiedChinese to R.string.language_simplified_chinese,
        RuntimeAppLanguage.French to R.string.language_french,
    )

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = stringResource(R.string.language_title),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
        )
        options.forEach { (language, labelRes) ->
            val selected = language.languageTag == selectedLanguageTag
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        onSetLanguageTag(language.languageTag)
                    }
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                RadioButton(
                    selected = selected,
                    onClick = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        onSetLanguageTag(language.languageTag)
                    },
                )
                Text(
                    text = stringResource(labelRes),
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun MemoryPanel(
    entries: List<RuntimeMemoryEntry>,
    onAddMemoryEntry: (String) -> Unit,
    onRemoveMemoryEntry: (String) -> Unit,
    onSetMemoryEntryEnabled: (String, Boolean) -> Unit,
) {
    val draft = rememberSaveable { mutableStateOf("") }
    val canAdd = draft.value.isNotBlank()
    val hapticFeedback = LocalHapticFeedback.current

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    text = stringResource(R.string.memory_title),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = stringResource(R.string.memory_subtitle),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            OutlinedTextField(
                value = draft.value,
                onValueChange = { draft.value = it },
                label = { Text(stringResource(R.string.memory_add_label)) },
                placeholder = { Text(stringResource(R.string.memory_add_placeholder)) },
                minLines = 2,
                maxLines = 4,
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onAddMemoryEntry(draft.value)
                    draft.value = ""
                },
                enabled = canAdd,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Filled.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.memory_add))
            }
            if (entries.isEmpty()) {
                EmptyState(text = stringResource(R.string.memory_empty))
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    entries.forEach { entry ->
                        MemoryEntryRow(
                            entry = entry,
                            onRemoveMemoryEntry = onRemoveMemoryEntry,
                            onSetMemoryEntryEnabled = onSetMemoryEntryEnabled,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun MemoryEntryRow(
    entry: RuntimeMemoryEntry,
    onRemoveMemoryEntry: (String) -> Unit,
    onSetMemoryEntryEnabled: (String, Boolean) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val showDeleteConfirmation = rememberSaveable(entry.id) { mutableStateOf(false) }

    if (showDeleteConfirmation.value) {
        AlertDialog(
            onDismissRequest = {
                showDeleteConfirmation.value = false
            },
            title = {
                Text(stringResource(R.string.memory_remove_confirm_title))
            },
            text = {
                Text(stringResource(R.string.memory_remove_confirm_message))
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        showDeleteConfirmation.value = false
                        onRemoveMemoryEntry(entry.id)
                    },
                ) {
                    Text(stringResource(R.string.delete))
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        showDeleteConfirmation.value = false
                    },
                ) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = entry.content,
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.bodyMedium,
                color = if (entry.enabled) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.58f)
                },
            )
            Text(
                text = stringResource(
                    if (entry.enabled) {
                        R.string.memory_enabled
                    } else {
                        R.string.memory_paused
                    },
                ),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.secondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Switch(
                checked = entry.enabled,
                onCheckedChange = { enabled ->
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onSetMemoryEntryEnabled(entry.id, enabled)
                },
            )
            FilledTonalIconButton(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    showDeleteConfirmation.value = true
                },
                modifier = Modifier.size(40.dp),
            ) {
                Icon(
                    imageVector = Icons.Filled.Delete,
                    contentDescription = stringResource(R.string.memory_remove),
                )
            }
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

private fun selectedModelIsUsable(state: RuntimeUiState): Boolean {
    val selectedId = state.selectedModelId ?: return false
    return state.models.firstOrNull { it.id == selectedId }?.installed == true
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
        "generation_in_progress" -> stringResource(R.string.error_generation_in_progress)
        "chat_session_not_found" -> stringResource(R.string.error_chat_session_not_found)
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
