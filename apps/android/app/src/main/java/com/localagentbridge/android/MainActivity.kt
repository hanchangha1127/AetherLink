package com.localagentbridge.android

import android.content.Context
import android.os.Bundle
import androidx.activity.SystemBarStyle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.annotation.StringRes
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Archive
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material.icons.filled.Unarchive
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.localagentbridge.android.runtime.RuntimeClientViewModel
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeUiState
import com.localagentbridge.android.ui.ChatScreen
import com.localagentbridge.android.ui.ConnectionStatusScreen
import com.localagentbridge.android.ui.ModelPickerScreen
import com.localagentbridge.android.ui.PairingScreen
import com.localagentbridge.android.ui.SettingsScreen
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            LocalAgentBridgeApp()
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun LocalAgentBridgeApp() {
    AetherLinkTheme {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background,
        ) {
            val viewModel: RuntimeClientViewModel = viewModel()
            val state by viewModel.state.collectAsStateWithLifecycle()
            val context = LocalContext.current
            val hapticFeedback = LocalHapticFeedback.current
            val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
            val scope = rememberCoroutineScope()
            var destination by rememberSaveable { mutableStateOf(AppDestination.Chat) }
            var renamingSessionId by rememberSaveable { mutableStateOf<String?>(null) }
            var renameDraft by rememberSaveable { mutableStateOf("") }
            var deletingSessionId by rememberSaveable { mutableStateOf<String?>(null) }
            var isArchiveHistoryDialogVisible by rememberSaveable { mutableStateOf(false) }
            var isDeleteHistoryDialogVisible by rememberSaveable { mutableStateOf(false) }
            val destinationTitle = stringResource(destination.labelRes)

            ModalNavigationDrawer(
                drawerState = drawerState,
                drawerContent = {
                    ModalDrawerSheet {
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(vertical = 12.dp),
                        ) {
                            Text(
                                text = stringResource(R.string.app_name),
                                style = MaterialTheme.typography.titleLarge,
                                modifier = Modifier.padding(horizontal = 28.dp, vertical = 12.dp),
                            )
                            Button(
                                onClick = {
                                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                    viewModel.startNewChat()
                                    destination = AppDestination.Chat
                                    scope.launch { drawerState.close() }
                                },
                                enabled = !state.isStreaming,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 12.dp, vertical = 8.dp),
                            ) {
                                Icon(Icons.Filled.Add, contentDescription = null)
                                Spacer(Modifier.size(8.dp))
                                Text(stringResource(R.string.new_chat))
                            }
                            Column(
                                modifier = Modifier
                                    .weight(1f)
                                    .verticalScroll(rememberScrollState()),
                            ) {
                                DrawerSectionLabel(text = stringResource(R.string.previous_chats))
                                if (state.chatSessions.isEmpty()) {
                                    Text(
                                        text = stringResource(R.string.no_previous_chats),
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(horizontal = 28.dp, vertical = 8.dp),
                                    )
                                } else {
                                    state.chatSessions.forEach { session ->
                                        ChatSessionDrawerItem(
                                            session = session,
                                            selected = destination == AppDestination.Chat &&
                                                session.id == state.activeChatSessionId,
                                            enabled = !state.isStreaming,
                                            onClick = {
                                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                                viewModel.selectChatSession(session.id)
                                                destination = AppDestination.Chat
                                                scope.launch { drawerState.close() }
                                            },
                                            onRename = {
                                                renamingSessionId = session.id
                                                renameDraft = session.title
                                            },
                                            onArchive = {
                                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                                viewModel.archiveChatSession(session.id)
                                            },
                                            onRestore = null,
                                            onDelete = {
                                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                                deletingSessionId = session.id
                                            },
                                        )
                                    }
                                    OutlinedButton(
                                        onClick = {
                                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                            isArchiveHistoryDialogVisible = true
                                        },
                                        enabled = !state.isStreaming,
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(horizontal = 12.dp, vertical = 8.dp),
                                    ) {
                                        Icon(Icons.Filled.Archive, contentDescription = null)
                                        Spacer(Modifier.size(8.dp))
                                        Text(stringResource(R.string.archive_all_chats))
                                    }
                                }
                                if (state.archivedChatSessions.isNotEmpty()) {
                                    DrawerSectionLabel(text = stringResource(R.string.archived_chats))
                                    state.archivedChatSessions.forEach { session ->
                                        ChatSessionDrawerItem(
                                            session = session,
                                            selected = false,
                                            enabled = !state.isStreaming,
                                            onClick = {
                                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                                viewModel.unarchiveChatSession(session.id)
                                                viewModel.selectChatSession(session.id)
                                                destination = AppDestination.Chat
                                                scope.launch { drawerState.close() }
                                            },
                                            onRename = null,
                                            onArchive = null,
                                            onRestore = {
                                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                                viewModel.unarchiveChatSession(session.id)
                                            },
                                            onDelete = {
                                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                                deletingSessionId = session.id
                                            },
                                        )
                                    }
                                }
                                if (state.chatSessions.isNotEmpty() || state.archivedChatSessions.isNotEmpty()) {
                                    OutlinedButton(
                                        onClick = {
                                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                            isDeleteHistoryDialogVisible = true
                                        },
                                        enabled = !state.isStreaming,
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(horizontal = 12.dp, vertical = 8.dp),
                                    ) {
                                        Icon(Icons.Filled.DeleteSweep, contentDescription = null)
                                        Spacer(Modifier.size(8.dp))
                                        Text(stringResource(R.string.delete_all_chats))
                                    }
                                }
                                HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                                DrawerDestinationItem(
                                    destination = AppDestination.Pairing,
                                    selected = destination == AppDestination.Pairing,
                                    onClick = {
                                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                        destination = AppDestination.Pairing
                                        scope.launch { drawerState.close() }
                                    },
                                )
                                DrawerDestinationItem(
                                    destination = AppDestination.Status,
                                    selected = destination == AppDestination.Status,
                                    onClick = {
                                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                        destination = AppDestination.Status
                                        scope.launch { drawerState.close() }
                                    },
                                )
                                DrawerDestinationItem(
                                    destination = AppDestination.Models,
                                    selected = destination == AppDestination.Models,
                                    onClick = {
                                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                        destination = AppDestination.Models
                                        scope.launch { drawerState.close() }
                                    },
                                )
                            }
                            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                            DrawerDestinationItem(
                                destination = AppDestination.Settings,
                                selected = destination == AppDestination.Settings,
                                onClick = {
                                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                    destination = AppDestination.Settings
                                    scope.launch { drawerState.close() }
                                },
                            )
                        }
                    }
                },
            ) {
                Scaffold(
                    topBar = {
                        TopAppBar(
                            title = {
                                if (destination == AppDestination.Chat) {
                                    ChatTopAppBarTitle(state)
                                } else {
                                    Text(destinationTitle)
                                }
                            },
                            navigationIcon = {
                                IconButton(
                                    onClick = {
                                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                        scope.launch { drawerState.open() }
                                    },
                                ) {
                                    Icon(
                                        imageVector = Icons.Filled.Menu,
                                        contentDescription = stringResource(R.string.content_desc_open_navigation),
                                    )
                                }
                            },
                        )
                    },
                ) { padding ->
                    when (destination) {
                        AppDestination.Chat -> ChatScreen(
                            state = state,
                            onInputChange = viewModel::updateChatInput,
                            onSend = viewModel::sendChatMessage,
                            onCancel = viewModel::cancelGeneration,
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(padding),
                        )
                        AppDestination.Pairing -> PairingScreen(
                            state = state,
                            onHostChange = viewModel::updateHost,
                            onPortChange = viewModel::updatePort,
                            onUseUsbReverse = viewModel::useUsbReverseEndpoint,
                            onUseEmulator = viewModel::useEmulatorEndpoint,
                            onStartDiscovery = viewModel::startDiscovery,
                            onStopDiscovery = viewModel::stopDiscovery,
                            onUseDiscoveredMac = viewModel::useDiscoveredMac,
                            onForgetTrustedMac = viewModel::forgetTrustedMac,
                            onScanPairingQr = {
                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                startPairingQrScanner(
                                    context = context,
                                    onResult = viewModel::trustMacFromPairingQr,
                                    onFailure = viewModel::showQrScanFailed,
                                )
                            },
                            onConnect = {
                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                viewModel.connectToTrustedRuntime()
                            },
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(padding),
                        )
                        AppDestination.Status -> ConnectionStatusScreen(
                            state = state,
                            onRefreshHealth = viewModel::requestRuntimeHealth,
                            onDisconnect = viewModel::disconnect,
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(padding),
                        )
                        AppDestination.Models -> ModelPickerScreen(
                            state = state,
                            onRequestModels = viewModel::requestModels,
                            onSelectModel = viewModel::selectModel,
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(padding),
                        )
                        AppDestination.Settings -> SettingsScreen(
                            state = state,
                            onHostChange = viewModel::updateHost,
                            onPortChange = viewModel::updatePort,
                            onUseUsbReverse = viewModel::useUsbReverseEndpoint,
                            onUseEmulator = viewModel::useEmulatorEndpoint,
                            onForgetTrustedMac = viewModel::forgetTrustedMac,
                            onAddMemoryEntry = viewModel::addMemoryEntry,
                            onRemoveMemoryEntry = viewModel::removeMemoryEntry,
                            onSetMemoryEntryEnabled = viewModel::setMemoryEntryEnabled,
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(padding),
                        )
                    }
                }
            }

            val sessionBeingRenamed = state.chatSessions.firstOrNull { it.id == renamingSessionId }
            if (sessionBeingRenamed != null) {
                RenameChatSessionDialog(
                    title = renameDraft,
                    onTitleChange = { renameDraft = it },
                    onDismiss = {
                        renamingSessionId = null
                        renameDraft = ""
                    },
                    onConfirm = {
                        viewModel.renameChatSession(sessionBeingRenamed.id, renameDraft)
                        renamingSessionId = null
                        renameDraft = ""
                    },
                )
            }

            val sessionBeingDeleted = (state.chatSessions + state.archivedChatSessions)
                .firstOrNull { it.id == deletingSessionId }
            if (sessionBeingDeleted != null) {
                DeleteChatSessionDialog(
                    sessionTitle = sessionBeingDeleted.title,
                    onDismiss = { deletingSessionId = null },
                    onConfirm = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        viewModel.deleteChatSession(sessionBeingDeleted.id)
                        deletingSessionId = null
                    },
                )
            }

            if (isArchiveHistoryDialogVisible) {
                ArchiveChatHistoryDialog(
                    onDismiss = { isArchiveHistoryDialogVisible = false },
                    onConfirm = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        viewModel.archiveChatSessions()
                        isArchiveHistoryDialogVisible = false
                    },
                )
            }

            if (isDeleteHistoryDialogVisible) {
                DeleteChatHistoryDialog(
                    onDismiss = { isDeleteHistoryDialogVisible = false },
                    onConfirm = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        viewModel.clearChatSessions()
                        isDeleteHistoryDialogVisible = false
                    },
                )
            }
        }
    }
}

@Composable
private fun ChatTopAppBarTitle(state: RuntimeUiState) {
    val statusText = when {
        state.isStreaming -> stringResource(R.string.chat_status_streaming)
        state.isConnected -> stringResource(R.string.chat_status_connected)
        else -> stringResource(R.string.chat_status_disconnected)
    }
    val selectedModelName = state.models
        .firstOrNull { it.id == state.selectedModelId }
        ?.name
        ?: state.selectedModelId
    val subtitle = selectedModelName?.let { "$statusText - $it" } ?: statusText

    Column {
        Text(
            text = stringResource(R.string.app_name),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            text = subtitle,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun DrawerSectionLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = 28.dp, vertical = 8.dp),
    )
}

@Composable
private fun ChatSessionDrawerItem(
    session: RuntimeChatSession,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    onRename: (() -> Unit)?,
    onArchive: (() -> Unit)?,
    onRestore: (() -> Unit)?,
    onDelete: () -> Unit,
) {
    var isMenuExpanded by rememberSaveable(session.id) { mutableStateOf(false) }
    val title = session.title.ifBlank { stringResource(R.string.untitled_chat) }
    val subtitle = when {
        session.archivedAtMillis != null -> stringResource(R.string.archived_chat)
        session.messageCount > 0 -> stringResource(R.string.chat_message_count, session.messageCount)
        session.updatedAtMillis > 0L -> stringResource(R.string.new_chat)
        else -> ""
    }

    NavigationDrawerItem(
        selected = selected,
        onClick = onClick,
        enabled = enabled,
        icon = {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.Chat,
                contentDescription = null,
            )
        },
        label = {
            Row(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Text(
                        text = title,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (subtitle.isNotBlank()) {
                        Text(
                            text = subtitle,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
                IconButton(
                    onClick = { isMenuExpanded = true },
                    enabled = enabled,
                    modifier = Modifier.size(32.dp),
                ) {
                    Icon(
                        imageVector = Icons.Filled.MoreVert,
                        contentDescription = stringResource(R.string.chat_session_more),
                    )
                }
                DropdownMenu(
                    expanded = isMenuExpanded,
                    onDismissRequest = { isMenuExpanded = false },
                ) {
                    if (onRename != null) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.rename_chat)) },
                            leadingIcon = { Icon(Icons.Filled.Edit, contentDescription = null) },
                            onClick = {
                                isMenuExpanded = false
                                onRename()
                            },
                        )
                    }
                    if (onArchive != null) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.archive_chat)) },
                            leadingIcon = { Icon(Icons.Filled.Archive, contentDescription = null) },
                            onClick = {
                                isMenuExpanded = false
                                onArchive()
                            },
                        )
                    }
                    if (onRestore != null) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.restore_chat)) },
                            leadingIcon = { Icon(Icons.Filled.Unarchive, contentDescription = null) },
                            onClick = {
                                isMenuExpanded = false
                                onRestore()
                            },
                        )
                    }
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.delete_chat)) },
                        leadingIcon = { Icon(Icons.Filled.Delete, contentDescription = null) },
                        onClick = {
                            isMenuExpanded = false
                            onDelete()
                        },
                    )
                }
            }
        },
        modifier = Modifier.padding(horizontal = 12.dp),
    )
}

@Composable
private fun RenameChatSessionDialog(
    title: String,
    onTitleChange: (String) -> Unit,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.rename_chat)) },
        text = {
            OutlinedTextField(
                value = title,
                onValueChange = onTitleChange,
                label = { Text(stringResource(R.string.chat_title_label)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
        },
        confirmButton = {
            TextButton(
                onClick = onConfirm,
                enabled = title.isNotBlank(),
            ) {
                Text(stringResource(R.string.save))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.cancel))
            }
        },
    )
}

@Composable
private fun DeleteChatSessionDialog(
    sessionTitle: String,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.delete_chat)) },
        text = {
            Text(
                text = stringResource(
                    R.string.delete_chat_confirm,
                    sessionTitle.ifBlank { stringResource(R.string.untitled_chat) },
                ),
            )
        },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(stringResource(R.string.delete))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.cancel))
            }
        },
    )
}

@Composable
private fun ArchiveChatHistoryDialog(
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.archive_all_chats)) },
        text = { Text(stringResource(R.string.archive_all_chats_confirm)) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(stringResource(R.string.archive))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.cancel))
            }
        },
    )
}

@Composable
private fun DeleteChatHistoryDialog(
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.delete_all_chats)) },
        text = { Text(stringResource(R.string.delete_all_chats_confirm)) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(stringResource(R.string.delete))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.cancel))
            }
        },
    )
}

@Composable
private fun DrawerDestinationItem(
    destination: AppDestination,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val label = stringResource(destination.labelRes)
    NavigationDrawerItem(
        selected = selected,
        onClick = onClick,
        icon = {
            Icon(
                imageVector = destination.icon,
                contentDescription = null,
            )
        },
        label = { Text(label) },
        modifier = Modifier.padding(horizontal = 12.dp),
    )
}

@Composable
private fun AetherLinkTheme(content: @Composable () -> Unit) {
    val darkTheme = isSystemInDarkTheme()
    val colorScheme = if (darkTheme) {
        AetherLinkDarkColors
    } else {
        AetherLinkLightColors
    }
    ApplySystemBars(colorScheme = colorScheme, darkTheme = darkTheme)
    MaterialTheme(
        colorScheme = colorScheme,
        content = content,
    )
}

@Composable
private fun ApplySystemBars(colorScheme: ColorScheme, darkTheme: Boolean) {
    val activity = LocalContext.current as? ComponentActivity ?: return
    val statusBarColor = colorScheme.background.toArgb()
    val navigationBarColor = colorScheme.surface.toArgb()

    SideEffect {
        val statusBarStyle = if (darkTheme) {
            SystemBarStyle.dark(statusBarColor)
        } else {
            SystemBarStyle.light(statusBarColor, statusBarColor)
        }
        val navigationBarStyle = if (darkTheme) {
            SystemBarStyle.dark(navigationBarColor)
        } else {
            SystemBarStyle.light(navigationBarColor, navigationBarColor)
        }

        activity.enableEdgeToEdge(
            statusBarStyle = statusBarStyle,
            navigationBarStyle = navigationBarStyle,
        )
    }
}

private val AetherLinkLightColors: ColorScheme = lightColorScheme(
    primary = Color(0xFF0B6B74),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFC7F0F4),
    onPrimaryContainer = Color(0xFF06363B),
    secondary = Color(0xFF586268),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFDCE6EA),
    onSecondaryContainer = Color(0xFF202A2F),
    tertiary = Color(0xFF6A5E15),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFF4E58A),
    onTertiaryContainer = Color(0xFF211C00),
    background = Color(0xFFFAFCFC),
    onBackground = Color(0xFF171D1F),
    surface = Color(0xFFFAFCFC),
    onSurface = Color(0xFF171D1F),
    surfaceVariant = Color(0xFFE0E4E7),
    onSurfaceVariant = Color(0xFF42484B),
    outline = Color(0xFF70787C),
)

private val AetherLinkDarkColors: ColorScheme = darkColorScheme(
    primary = Color(0xFF7BD2DD),
    onPrimary = Color(0xFF00363D),
    primaryContainer = Color(0xFF00515A),
    onPrimaryContainer = Color(0xFFC7F0F4),
    secondary = Color(0xFFC0CAD0),
    onSecondary = Color(0xFF2B3337),
    secondaryContainer = Color(0xFF424B50),
    onSecondaryContainer = Color(0xFFDCE6EA),
    tertiary = Color(0xFFD7C96F),
    onTertiary = Color(0xFF393000),
    tertiaryContainer = Color(0xFF514700),
    onTertiaryContainer = Color(0xFFF4E58A),
    background = Color(0xFF101416),
    onBackground = Color(0xFFE0E3E5),
    surface = Color(0xFF101416),
    onSurface = Color(0xFFE0E3E5),
    surfaceVariant = Color(0xFF42484B),
    onSurfaceVariant = Color(0xFFC0C8CC),
    outline = Color(0xFF8A9296),
)

private fun startPairingQrScanner(
    context: Context,
    onResult: (String) -> Unit,
    onFailure: (String?) -> Unit,
) {
    val options = GmsBarcodeScannerOptions.Builder()
        .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
        .build()
    val scanner = GmsBarcodeScanning.getClient(context, options)

    scanner.startScan()
        .addOnSuccessListener { barcode ->
            val rawValue = barcode.rawValue
            if (rawValue.isNullOrBlank()) {
                onFailure(context.getString(R.string.error_qr_empty_detail))
            } else {
                onResult(rawValue)
            }
        }
        .addOnCanceledListener {
            // User intentionally dismissed the scanner. Keep the current pairing state.
        }
        .addOnFailureListener { error ->
            onFailure(error.message)
        }
}

private enum class AppDestination(
    @param:StringRes val labelRes: Int,
    val icon: ImageVector,
) {
    Chat(R.string.tab_chat, Icons.AutoMirrored.Filled.Chat),
    Pairing(R.string.tab_pairing, Icons.Filled.Link),
    Status(R.string.tab_status, Icons.Filled.Sync),
    Models(R.string.tab_models, Icons.Filled.Storage),
    Settings(R.string.tab_settings, Icons.Filled.Settings),
}
