package com.localagentbridge.android.ui

import android.widget.Toast
import androidx.annotation.StringRes
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
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
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
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
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimePendingAttachment
import com.localagentbridge.android.runtime.RuntimeProviderStatus
import com.localagentbridge.android.runtime.RuntimeTrustedMac
import com.localagentbridge.android.runtime.RuntimeUiError
import com.localagentbridge.android.runtime.RuntimeUiState
import com.localagentbridge.android.runtime.isChatModel
import com.localagentbridge.android.runtime.isEmbeddingModel
import com.localagentbridge.android.runtime.supportsImageInput

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
            ProviderStatusRows(providers = state.providerStatuses)
            StatusLine(
                label = stringResource(R.string.endpoint),
                value = state.trustedMac?.endpointHint?.let { endpoint -> "${endpoint.host}:${endpoint.port}" }
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
private fun ProviderStatusRows(providers: List<RuntimeProviderStatus>) {
    if (providers.isEmpty()) return

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        providers.forEachIndexed { index, provider ->
            ProviderStatusRow(provider = provider)
            if (index != providers.lastIndex) {
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun ProviderStatusRow(provider: RuntimeProviderStatus) {
    val statusText = if (provider.available) {
        stringResource(R.string.provider_status_ready)
    } else {
        stringResource(R.string.provider_status_unavailable)
    }
    val icon = if (provider.available) Icons.Filled.CheckCircle else Icons.Filled.Error
    val tint = if (provider.available) {
        MaterialTheme.colorScheme.primary
    } else {
        MaterialTheme.colorScheme.error
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = statusText,
            tint = tint,
            modifier = Modifier.size(20.dp),
        )
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = provider.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(12.dp))
                Text(
                    text = statusText,
                    style = MaterialTheme.typography.labelMedium,
                    color = tint,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(
                text = providerStatusDetail(provider),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
            )
            provider.message.takeIf { it.isNotBlank() }?.let { message ->
                Text(
                    text = stringResource(R.string.provider_mac_detail, message),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            provider.code?.takeIf { it.isNotBlank() }?.let { code ->
                Text(
                    text = stringResource(R.string.provider_error_code, code),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            if (provider.retryable == true) {
                Text(
                    text = stringResource(R.string.provider_retryable_hint),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
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
    onRefreshHealth: () -> Unit,
    onRequestModels: () -> Unit,
    onSelectModel: (String) -> Unit,
    onAttachFiles: () -> Unit,
    onRemoveAttachment: (String) -> Unit,
    onSuggestionClick: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val listState = rememberLazyListState()
    val hasSendableContent = state.chatInput.isNotBlank() || state.pendingAttachments.isNotEmpty()
    val hasUnsupportedImageAttachment = hasUnsupportedImageAttachment(state)
    val canSend = state.isConnected &&
        !state.isStreaming &&
        selectedModelIsUsable(state) &&
        hasSendableContent &&
        !hasUnsupportedImageAttachment
    val density = LocalDensity.current
    val keyboardDockPadding = if (WindowInsets.ime.getBottom(density) > 0) 64.dp else 0.dp

    LaunchedEffect(state.messages.size, state.messages.lastOrNull()?.content) {
        if (state.messages.isNotEmpty()) {
            listState.animateScrollToItem(state.messages.lastIndex)
        }
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 14.dp, vertical = 8.dp),
    ) {
        if (state.messages.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(bottom = 168.dp),
                contentAlignment = Alignment.Center,
            ) {
                ChatEmptyState(
                    state = state,
                    onConnect = onConnect,
                    onRequestModels = onRequestModels,
                    onSelectModel = onSelectModel,
                )
            }
        } else {
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(18.dp),
                contentPadding = PaddingValues(top = 10.dp, bottom = 176.dp),
            ) {
                items(
                    items = state.messages,
                    key = { message -> message.id },
                ) { message ->
                    val isLatestAssistant = message.role == "assistant" &&
                        message.id == state.messages.lastAssistantMessageId()
                    ChatMessageRow(
                        message = message,
                        isStreaming = state.isStreaming &&
                            message.role == "assistant" &&
                            message.id == state.messages.lastOrNull()?.id,
                        showSuggestions = isLatestAssistant && !state.isStreaming,
                        isLoadingSuggestions = isLatestAssistant && state.isLoadingSuggestions,
                        onSuggestionClick = onSuggestionClick,
                    )
                }
            }
        }
        Column(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(bottom = keyboardDockPadding),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            BackendReadinessBanner(
                state = state,
                onRefreshHealth = onRefreshHealth,
            )
            ErrorText(state.error)
            ChatComposer(
                value = state.chatInput,
                attachments = state.pendingAttachments,
                enabled = !state.isStreaming,
                canSend = canSend,
                isStreaming = state.isStreaming,
                hint = chatInputHint(state),
                onInputChange = onInputChange,
                onAttachFiles = onAttachFiles,
                onRemoveAttachment = onRemoveAttachment,
                onSend = onSend,
                onCancel = onCancel,
            )
        }
    }
}

@Composable
private fun BackendReadinessBanner(
    state: RuntimeUiState,
    onRefreshHealth: () -> Unit,
) {
    if (!state.isConnected || state.backendAvailable != false) return

    val hapticFeedback = LocalHapticFeedback.current
    val unavailableProviders = state.providerStatuses.filter { provider -> !provider.available }
    val detail = unavailableProviders
        .firstOrNull()
        ?.let { provider -> providerStatusDetail(provider) }
        ?: stringResource(R.string.chat_backend_unavailable_detail)

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.errorContainer,
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.Top,
            ) {
                Icon(
                    imageVector = Icons.Filled.Error,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onErrorContainer,
                )
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = stringResource(R.string.chat_backend_unavailable_title),
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                    Text(
                        text = detail,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                }
            }
            TextButton(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onRefreshHealth()
                },
            ) {
                Icon(
                    imageVector = Icons.Filled.Refresh,
                    contentDescription = null,
                )
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.refresh_health))
            }
        }
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
    onRequestModels: () -> Unit,
    onDisconnect: () -> Unit,
    onSetLanguageTag: (String) -> Unit,
    onSelectEmbeddingModel: (String) -> Unit,
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
            AppPreferencesPanel(
                selectedLanguageTag = state.selectedLanguageTag,
                onSetLanguageTag = onSetLanguageTag,
            )
        }
        item {
            EmbeddingModelPanel(
                state = state,
                onRequestModels = onRequestModels,
                onSelectEmbeddingModel = onSelectEmbeddingModel,
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
        item {
            SettingsExpandableSection(
                title = R.string.status_title,
                subtitle = R.string.status_subtitle,
            ) {
                CompanionOnlyPanel()
                QrPairingPanel(
                    isConnecting = state.isConnecting,
                    onScanPairingQr = onScanPairingQr,
                )
                TrustedMacPanel(
                    state = state,
                    onForgetTrustedMac = onForgetTrustedMac,
                )
                PairingConnectButton(
                    state = state,
                    onConnect = onConnect,
                )
                if (state.trustedMac == null) {
                    EmptyState(text = stringResource(R.string.connect_requires_pairing))
                }
                ConnectionStatusPanel(state = state)
                ConnectionStatusActions(
                    state = state,
                    onRefreshHealth = onRefreshHealth,
                    onDisconnect = onDisconnect,
                )
            }
        }
        item {
            SettingsExpandableSection(
                title = R.string.advanced_connection,
                subtitle = R.string.advanced_connection_detail,
            ) {
                DiscoveryPanel(
                    state = state,
                    onStartDiscovery = onStartDiscovery,
                    onStopDiscovery = onStopDiscovery,
                    onUseDiscoveredMac = onUseDiscoveredMac,
                )
                EndpointPanel(
                    state = state,
                    onHostChange = onHostChange,
                    onPortChange = onPortChange,
                    onUseUsbReverse = onUseUsbReverse,
                    onUseEmulator = onUseEmulator,
                    title = R.string.runtime_endpoint,
                )
            }
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
private fun SettingsExpandableSection(
    @StringRes title: Int,
    @StringRes subtitle: Int,
    initiallyExpanded: Boolean = false,
    content: @Composable ColumnScope.() -> Unit,
) {
    val isExpanded = rememberSaveable { mutableStateOf(initiallyExpanded) }
    val toggleExpanded = { isExpanded.value = !isExpanded.value }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        HorizontalDivider()
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { toggleExpanded() }
                .padding(vertical = 4.dp),
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
                    text = stringResource(subtitle),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            Spacer(Modifier.width(12.dp))
            FilledTonalIconButton(onClick = { toggleExpanded() }) {
                Icon(
                    imageVector = if (isExpanded.value) {
                        Icons.Filled.KeyboardArrowUp
                    } else {
                        Icons.Filled.KeyboardArrowDown
                    },
                    contentDescription = null,
                )
            }
        }
        if (isExpanded.value) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    content = content,
                )
            }
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
                    text = trusted.endpointHint?.let { endpoint -> "${endpoint.host}:${endpoint.port}" }
                        ?: stringResource(R.string.status_unknown),
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
                            Icons.Filled.Link,
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
                        DiscoveredMacRow(
                            peer = peer,
                            trustedMac = state.trustedMac,
                            onUse = onUseDiscoveredMac,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DiscoveredMacRow(
    peer: RuntimeDiscoveredMac,
    trustedMac: RuntimeTrustedMac?,
    onUse: (RuntimeDiscoveredMac) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val identityStatus = peer.identityStatus(trustedMac)
    val hasAdvertisedIdentity = peer.hasAdvertisedIdentity()
    val isKnownMismatch = identityStatus == DiscoveredMacIdentityStatus.DifferentTrustedRuntime

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
                Text(
                    text = stringResource(identityStatus.labelRes(hasAdvertisedIdentity)),
                    color = when (identityStatus) {
                        DiscoveredMacIdentityStatus.TrustedMatch -> MaterialTheme.colorScheme.primary
                        DiscoveredMacIdentityStatus.DifferentTrustedRuntime -> MaterialTheme.colorScheme.error
                        DiscoveredMacIdentityStatus.Unknown -> MaterialTheme.colorScheme.secondary
                    },
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            TextButton(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onUse(peer)
                },
                enabled = !isKnownMismatch,
            ) {
                Text(stringResource(R.string.use))
            }
        }
    }
}

private enum class DiscoveredMacIdentityStatus {
    TrustedMatch,
    Unknown,
    DifferentTrustedRuntime;

    @StringRes
    fun labelRes(hasAdvertisedIdentity: Boolean): Int = when (this) {
        TrustedMatch -> R.string.discovery_identity_trusted_match
        Unknown -> if (hasAdvertisedIdentity) {
            R.string.discovery_identity_unknown
        } else {
            R.string.discovery_identity_not_advertised
        }
        DifferentTrustedRuntime -> R.string.discovery_identity_different_trusted_runtime
    }
}

private fun RuntimeDiscoveredMac.identityStatus(trustedMac: RuntimeTrustedMac?): DiscoveredMacIdentityStatus {
    val discoveredRouteToken = routeToken.normalizedIdentityValue()
    val discoveredDeviceId = deviceId.normalizedIdentityValue()
    val discoveredFingerprint = fingerprint.normalizedIdentityValue()

    if (discoveredRouteToken == null && discoveredDeviceId == null && discoveredFingerprint == null) {
        return DiscoveredMacIdentityStatus.Unknown
    }
    if (trustedMac == null) {
        return DiscoveredMacIdentityStatus.Unknown
    }

    val trustedRouteToken = trustedMac.routeToken.normalizedIdentityValue()
    val trustedDeviceId = trustedMac.deviceId.normalizedIdentityValue()
    val trustedFingerprint = trustedMac.fingerprint.normalizedIdentityValue()
    val routeTokenMatches = discoveredRouteToken != null && discoveredRouteToken == trustedRouteToken
    val deviceIdMatches = discoveredDeviceId != null && discoveredDeviceId == trustedDeviceId
    val fingerprintMatches = discoveredFingerprint != null && discoveredFingerprint == trustedFingerprint
    val routeTokenDiffers = discoveredRouteToken != null &&
        trustedRouteToken != null &&
        discoveredRouteToken != trustedRouteToken
    val deviceIdDiffers = discoveredDeviceId != null && trustedDeviceId != null && discoveredDeviceId != trustedDeviceId
    val fingerprintDiffers = discoveredFingerprint != null &&
        trustedFingerprint != null &&
        discoveredFingerprint != trustedFingerprint

    return when {
        routeTokenMatches -> DiscoveredMacIdentityStatus.TrustedMatch
        routeTokenDiffers -> DiscoveredMacIdentityStatus.DifferentTrustedRuntime
        (deviceIdMatches || fingerprintMatches) && !routeTokenDiffers && !fingerprintDiffers && !deviceIdDiffers -> {
            DiscoveredMacIdentityStatus.TrustedMatch
        }
        deviceIdDiffers || fingerprintDiffers -> DiscoveredMacIdentityStatus.DifferentTrustedRuntime
        else -> DiscoveredMacIdentityStatus.Unknown
    }
}

private fun RuntimeDiscoveredMac.hasAdvertisedIdentity(): Boolean =
    routeToken.normalizedIdentityValue() != null ||
        deviceId.normalizedIdentityValue() != null ||
        fingerprint.normalizedIdentityValue() != null

private fun String?.normalizedIdentityValue(): String? = this?.trim()?.takeUnless { it.isEmpty() }

@Composable
private fun ChatEmptyState(
    state: RuntimeUiState,
    onConnect: () -> Unit,
    onRequestModels: () -> Unit,
    onSelectModel: (String) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current

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
                MaterialTheme.colorScheme.surfaceVariant
            },
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(
                    imageVector = Icons.Filled.Link,
                    contentDescription = null,
                    tint = if (state.isConnected) {
                        MaterialTheme.colorScheme.onPrimaryContainer
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
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
        val chatModels = state.models.filter { it.isChatModel() }
        if (state.isConnected && !selectedModelIsUsable(state) && chatModels.isNotEmpty()) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                horizontalAlignment = Alignment.Start,
            ) {
                Text(
                    text = stringResource(R.string.chat_select_model_from_mac),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                QuickModelPicker(
                    models = chatModels,
                    installingModelId = state.installingModelId,
                    onSelectModel = onSelectModel,
                )
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
        if (state.isConnected && !selectedModelIsUsable(state)) {
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
private fun QuickModelPicker(
    models: List<RuntimeModel>,
    installingModelId: String?,
    onSelectModel: (String) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val visibleModels = models.sortedWith(
        compareBy<RuntimeModel> { !it.installed }
            .thenBy { it.name.lowercase() }
    ).take(8)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        visibleModels.forEach { model ->
            val isInstalling = model.id == installingModelId
            val status = quickModelStatus(model = model, installing = isInstalling)
            OutlinedButton(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onSelectModel(model.id)
                },
                enabled = !isInstalling,
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                modifier = Modifier
                    .widthIn(max = 220.dp)
                    .semantics {
                        stateDescription = status
                    },
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        text = model.name,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = status,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
private fun quickModelStatus(model: RuntimeModel, installing: Boolean): String {
    return when {
        installing -> stringResource(R.string.installing_model)
        !model.installed -> stringResource(R.string.install_model)
        model.running -> stringResource(R.string.model_running)
        else -> stringResource(R.string.model_installed)
    }
}

@Composable
private fun ChatMessageRow(
    message: RuntimeChatMessage,
    isStreaming: Boolean,
    showSuggestions: Boolean,
    isLoadingSuggestions: Boolean,
    onSuggestionClick: (String) -> Unit,
) {
    val isUser = message.role == "user"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        if (isUser) {
            Column(
                modifier = Modifier.widthIn(max = 560.dp),
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
                if (message.content.isNotBlank()) {
                    MessageCopyButton(textToCopy = message.content)
                }
            }
        } else {
            AssistantMessage(
                message = message,
                isStreaming = isStreaming,
                showSuggestions = showSuggestions,
                isLoadingSuggestions = isLoadingSuggestions,
                onSuggestionClick = onSuggestionClick,
            )
        }
    }
}

@Composable
private fun AssistantMessage(
    message: RuntimeChatMessage,
    isStreaming: Boolean,
    showSuggestions: Boolean,
    isLoadingSuggestions: Boolean,
    onSuggestionClick: (String) -> Unit,
) {
    val hasReasoning = message.reasoning.isNotBlank()
    val isReasoningExpanded = rememberSaveable(message.id) { mutableStateOf(false) }
    val textToCopy = message.content.ifBlank { message.reasoning }
    val showTyping = isStreaming && message.content.isBlank()

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
                if (message.content.isNotBlank() || showTyping) {
                    MessageContent(
                        content = message.content.ifBlank { stringResource(R.string.assistant_typing) },
                        textColor = MaterialTheme.colorScheme.onSurface,
                    )
                }
                if (showTyping) {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
            }
            if (textToCopy.isNotBlank()) {
                MessageCopyButton(textToCopy = textToCopy)
            }
            if (showSuggestions) {
                SuggestedQuestions(
                    suggestions = message.suggestions,
                    isLoading = isLoadingSuggestions,
                    onSuggestionClick = onSuggestionClick,
                )
            }
        }
    }
}

@Composable
private fun SuggestedQuestions(
    suggestions: List<String>,
    isLoading: Boolean,
    onSuggestionClick: (String) -> Unit,
) {
    if (suggestions.isEmpty() && !isLoading) return

    val hapticFeedback = LocalHapticFeedback.current
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = stringResource(
                if (isLoading && suggestions.isEmpty()) {
                    R.string.generating_suggestions
                } else {
                    R.string.suggested_next_questions
                }
            ),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        if (suggestions.isNotEmpty()) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                suggestions.forEach { suggestion ->
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                            onSuggestionClick(suggestion)
                        },
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 7.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            text = suggestion,
                            maxLines = 3,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        } else {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
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
                if (code.isNotBlank()) {
                    MessageCopyButton(textToCopy = code)
                }
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

private fun List<RuntimeChatMessage>.lastAssistantMessageId(): String? {
    return lastOrNull { it.role == "assistant" }?.id
}

@Composable
private fun AssistantReasoning(
    reasoning: String,
    expanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
) {
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
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.72f),
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
    attachments: List<RuntimePendingAttachment>,
    enabled: Boolean,
    canSend: Boolean,
    isStreaming: Boolean,
    hint: String,
    onInputChange: (String) -> Unit,
    onAttachFiles: () -> Unit,
    onRemoveAttachment: (String) -> Unit,
    onSend: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val showComposerStatus = !isStreaming && !canSend && hint.isNotBlank()
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        tonalElevation = 2.dp,
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            if (isStreaming) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            AttachmentChips(
                attachments = attachments,
                enabled = enabled,
                onRemoveAttachment = onRemoveAttachment,
            )
            BasicTextField(
                value = value,
                onValueChange = onInputChange,
                enabled = enabled,
                singleLine = false,
                minLines = 1,
                maxLines = 5,
                textStyle = MaterialTheme.typography.bodyLarge.copy(
                    color = MaterialTheme.colorScheme.onSurface,
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 38.dp, max = 150.dp),
                decorationBox = { innerTextField ->
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 2.dp, vertical = 8.dp),
                        contentAlignment = Alignment.TopStart,
                    ) {
                        if (value.isBlank()) {
                            Text(
                                text = stringResource(R.string.chat_composer_placeholder),
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.secondary,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        innerTextField()
                    }
                },
            )
            if (showComposerStatus) {
                Text(
                    text = hint,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(horizontal = 2.dp),
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                FilledTonalIconButton(
                    onClick = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        onAttachFiles()
                    },
                    enabled = enabled,
                    modifier = Modifier.size(40.dp),
                ) {
                    Icon(
                        Icons.Filled.Add,
                        contentDescription = stringResource(R.string.content_desc_attach_files),
                    )
                }
                Spacer(modifier = Modifier.weight(1f))
                if (isStreaming) {
                    FilledIconButton(
                        onClick = {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                            onCancel()
                        },
                        enabled = true,
                        modifier = Modifier.size(40.dp),
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
                        modifier = Modifier
                            .size(40.dp)
                            .semantics {
                                stateDescription = hint
                            },
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.Send,
                            contentDescription = stringResource(R.string.content_desc_send),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun AttachmentChips(
    attachments: List<RuntimePendingAttachment>,
    enabled: Boolean,
    onRemoveAttachment: (String) -> Unit,
) {
    if (attachments.isEmpty()) return

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        attachments.forEach { attachment ->
            AttachmentChip(
                attachment = attachment,
                enabled = enabled,
                onRemoveAttachment = onRemoveAttachment,
            )
        }
    }
}

@Composable
private fun AttachmentChip(
    attachment: RuntimePendingAttachment,
    enabled: Boolean,
    onRemoveAttachment: (String) -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = MaterialTheme.colorScheme.secondaryContainer,
        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
    ) {
        Row(
            modifier = Modifier.padding(start = 12.dp, end = 4.dp, top = 4.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = attachment.name,
                style = MaterialTheme.typography.labelMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.widthIn(max = 180.dp),
            )
            IconButton(
                onClick = { onRemoveAttachment(attachment.id) },
                enabled = enabled,
                modifier = Modifier.size(28.dp),
            ) {
                Icon(
                    Icons.Filled.Close,
                    contentDescription = stringResource(R.string.content_desc_remove_attachment, attachment.name),
                    modifier = Modifier.size(18.dp),
                )
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
private fun EmbeddingModelPanel(
    state: RuntimeUiState,
    onRequestModels: () -> Unit,
    onSelectEmbeddingModel: (String) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val embeddingModels = state.models
        .filter { it.isEmbeddingModel() }
        .sortedWith(compareBy<RuntimeModel> { !it.installed }.thenBy { it.name.lowercase() })
    val selectedEmbeddingModel = embeddingModels.firstOrNull { it.id == state.selectedEmbeddingModelId }
    val selectedEmbeddingModelLabel = selectedEmbeddingModel?.name
        ?: state.selectedEmbeddingModelId
            ?.substringAfter(':')
            ?.takeIf(String::isNotBlank)
        ?: stringResource(R.string.model_none)

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    text = stringResource(R.string.embedding_model_title),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = stringResource(R.string.embedding_model_subtitle),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            StatusLine(
                label = stringResource(R.string.selected_embedding_model),
                value = selectedEmbeddingModelLabel,
            )
            Button(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onRequestModels()
                },
                enabled = state.isConnected && !state.isLoadingModels,
                modifier = Modifier.fillMaxWidth(),
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
            when {
                !state.isConnected -> EmptyState(text = stringResource(R.string.embedding_model_connect_first))
                embeddingModels.isEmpty() -> EmptyState(text = stringResource(R.string.embedding_model_empty))
                else -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    embeddingModels.forEach { model ->
                        EmbeddingModelRow(
                            model = model,
                            selected = model.id == state.selectedEmbeddingModelId,
                            onSelectEmbeddingModel = onSelectEmbeddingModel,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun EmbeddingModelRow(
    model: RuntimeModel,
    selected: Boolean,
    onSelectEmbeddingModel: (String) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    OutlinedButton(
        onClick = {
            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
            onSelectEmbeddingModel(model.id)
        },
        enabled = model.installed,
        modifier = Modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = if (selected) Icons.Filled.CheckCircle else Icons.Filled.Search,
                contentDescription = null,
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = model.name,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = "${model.provider} - ${quickModelStatus(model = model, installing = false)}",
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

    Column(
        modifier = Modifier.selectableGroup(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
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
                    .selectable(
                        selected = selected,
                        role = Role.RadioButton,
                    ) {
                        if (!selected) {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        }
                        onSetLanguageTag(language.languageTag)
                    }
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                RadioButton(
                    selected = selected,
                    onClick = null,
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
    val selectedModel = state.models.firstOrNull { it.id == selectedId && it.isChatModel() }
    return selectedModel?.installed == true
}

private fun selectedModelIsMissingFromRuntime(state: RuntimeUiState): Boolean {
    val selectedId = state.selectedModelId ?: return false
    return state.models.none { it.id == selectedId && it.isChatModel() }
}

private fun hasUnsupportedImageAttachment(state: RuntimeUiState): Boolean {
    if (state.pendingAttachments.none { it.type == "image" }) return false
    val selectedId = state.selectedModelId ?: return false
    val selectedModel = state.models.firstOrNull { it.id == selectedId && it.isChatModel() }
    return selectedModel?.supportsImageInput() != true
}

@Composable
private fun chatInputHint(state: RuntimeUiState): String {
    return when {
        !state.isConnected -> stringResource(R.string.chat_hint_connect)
        state.selectedModelId == null -> stringResource(R.string.chat_hint_select_model)
        selectedModelIsMissingFromRuntime(state) -> stringResource(R.string.chat_hint_model_unavailable)
        !selectedModelIsUsable(state) -> stringResource(R.string.chat_hint_install_model)
        hasUnsupportedImageAttachment(state) -> stringResource(R.string.chat_hint_select_vision_model)
        state.isStreaming -> stringResource(R.string.chat_hint_wait_for_stream)
        state.chatInput.isBlank() && state.pendingAttachments.isEmpty() -> stringResource(R.string.chat_hint_enter_message)
        else -> stringResource(R.string.chat_hint_ready)
    }
}

@Composable
private fun chatEmptyTitle(state: RuntimeUiState): String {
    return when {
        !state.isConnected -> stringResource(R.string.empty_chat_disconnected_title)
        state.isStreaming -> stringResource(R.string.empty_chat_streaming_title)
        !selectedModelIsUsable(state) -> stringResource(R.string.empty_chat_no_model_title)
        else -> stringResource(R.string.empty_chat_ready_title)
    }
}

@Composable
private fun chatEmptyText(state: RuntimeUiState): String {
    return when {
        !state.isConnected -> stringResource(R.string.empty_chat_disconnected)
        state.isStreaming -> stringResource(R.string.empty_chat_streaming)
        selectedModelIsMissingFromRuntime(state) -> stringResource(R.string.selected_model_unavailable)
        !selectedModelIsUsable(state) -> stringResource(R.string.empty_chat_no_model)
        else -> stringResource(R.string.empty_chat_ready)
    }
}

@Composable
private fun runtimeErrorLabel(error: RuntimeUiError): String {
    return when (error.code) {
        "invalid_endpoint" -> stringResource(R.string.error_invalid_endpoint)
        "connection_failed" -> stringResource(R.string.error_connection_failed)
        "no_route" -> stringResource(R.string.error_no_runtime_route)
        "no_connectable_route" -> stringResource(R.string.error_no_connectable_runtime_route)
        "discovery_failed" -> stringResource(R.string.error_discovery_failed)
        "invalid_pairing_qr" -> stringResource(R.string.error_invalid_pairing_qr)
        "pairing_endpoint_unavailable" -> stringResource(R.string.error_pairing_endpoint_unavailable)
        "qr_scan_failed" -> stringResource(R.string.error_qr_scan_failed)
        "pair_first" -> stringResource(R.string.error_pair_first)
        "pairing_required" -> stringResource(R.string.error_pairing_required)
        "pairing_rejected" -> stringResource(R.string.error_pairing_rejected)
        "authentication_required" -> stringResource(R.string.error_authentication_required)
        "authentication_failed" -> stringResource(R.string.error_authentication_failed)
        "device_identity_failed" -> stringResource(R.string.error_device_identity_failed)
        "select_model" -> stringResource(R.string.error_select_model)
        "select_chat_model" -> stringResource(R.string.error_select_chat_model)
        "select_embedding_model" -> stringResource(R.string.error_select_embedding_model)
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
        "attachment_too_large" -> stringResource(R.string.error_attachment_too_large)
        "attachment_read_failed" -> stringResource(R.string.error_attachment_read_failed)
        "select_vision_model" -> stringResource(R.string.error_select_vision_model)
        "unsupported_attachment" -> stringResource(R.string.error_unsupported_attachment)
        "unreadable_attachment" -> stringResource(R.string.error_unreadable_attachment)
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
private fun providerStatusDetail(provider: RuntimeProviderStatus): String {
    if (provider.available) {
        return stringResource(R.string.provider_status_ready_detail, provider.name)
    }
    return when (provider.id) {
        "ollama" -> stringResource(R.string.provider_ollama_unavailable_hint)
        "lm_studio" -> stringResource(R.string.provider_lm_studio_unavailable_hint)
        else -> stringResource(R.string.provider_unavailable_hint, provider.name)
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
