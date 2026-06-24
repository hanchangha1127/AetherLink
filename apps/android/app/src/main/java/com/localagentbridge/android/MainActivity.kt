package com.localagentbridge.android

import android.content.Context
import android.content.res.Configuration
import android.os.Bundle
import android.os.LocaleList
import androidx.activity.SystemBarStyle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Archive
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Unarchive
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
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
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.localagentbridge.android.runtime.RuntimeClientViewModel
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimeUiState
import com.localagentbridge.android.runtime.isChatModel
import com.localagentbridge.android.ui.ChatScreen
import com.localagentbridge.android.ui.PairingScreen
import com.localagentbridge.android.ui.SettingsScreen
import com.localagentbridge.android.ui.runtimeProviderDisplayName
import kotlinx.coroutines.launch
import java.util.Locale

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
            LocalizedContent(languageTag = state.selectedLanguageTag) {
            val context = LocalContext.current
            val hapticFeedback = LocalHapticFeedback.current
            val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
            val scope = rememberCoroutineScope()
            var destination by rememberSaveable { mutableStateOf(AppDestination.Pairing) }
            var renamingSessionId by rememberSaveable { mutableStateOf<String?>(null) }
            var renameDraft by rememberSaveable { mutableStateOf("") }
            var chatSearchQuery by rememberSaveable { mutableStateOf("") }
            val destinationTitle = stringResource(destination.labelRes)
            val untitledChatTitle = stringResource(R.string.untitled_chat)
            val trimmedChatSearchQuery = chatSearchQuery.trim()
            val hasChatSearchQuery = trimmedChatSearchQuery.isNotEmpty()
            val hasAnyChatSessions = state.chatSessions.isNotEmpty()
            val filteredChatSessions = if (hasChatSearchQuery) {
                state.chatSessions.filter { session ->
                    session.title.ifBlank { untitledChatTitle }
                        .contains(trimmedChatSearchQuery, ignoreCase = true)
                }
            } else {
                state.chatSessions
            }
            val hasChatSearchResults = filteredChatSessions.isNotEmpty()
            val attachmentPickerLauncher = rememberLauncherForActivityResult(
                contract = ActivityResultContracts.GetMultipleContents(),
            ) { uris ->
                viewModel.addAttachments(uris)
            }

            LaunchedEffect(
                destination,
                state.trustedRuntime?.deviceId,
                state.pairingOnboardingCompleted,
            ) {
                val resolved = resolveAppDestination(
                    current = destination,
                    hasTrustedRuntime = state.trustedRuntime != null,
                    pairingOnboardingCompleted = state.pairingOnboardingCompleted,
                )
                if (resolved != destination) {
                    destination = resolved
                }
            }

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
                                if (hasAnyChatSessions) {
                                    ChatHistorySearchField(
                                        query = chatSearchQuery,
                                        onQueryChange = { chatSearchQuery = it },
                                        onClear = { chatSearchQuery = "" },
                                    )
                                }
                                if (hasChatSearchQuery && !hasChatSearchResults) {
                                    Text(
                                        text = stringResource(R.string.no_chat_search_results),
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(horizontal = 28.dp, vertical = 8.dp),
                                    )
                                } else if (!hasChatSearchQuery && state.chatSessions.isEmpty()) {
                                    Text(
                                        text = stringResource(R.string.no_previous_chats),
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(horizontal = 28.dp, vertical = 8.dp),
                                    )
                                } else {
                                    filteredChatSessions.forEach { session ->
                                        ChatSessionDrawerItem(
                                            session = session,
                                            selected = destination == AppDestination.Chat &&
                                                session.id == state.activeChatSessionId,
                                            enabled = !state.isStreaming,
                                            onClick = {
                                                viewModel.selectChatSession(session.id)
                                                destination = AppDestination.Chat
                                                scope.launch { drawerState.close() }
                                            },
                                            onRename = {
                                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                                renamingSessionId = session.id
                                                renameDraft = session.title
                                            },
                                            onArchive = {
                                                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                                viewModel.archiveChatSession(session.id)
                                            },
                                            onRestore = null,
                                            onDelete = null,
                                        )
                                    }
                                }
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
                            colors = TopAppBarDefaults.topAppBarColors(
                                containerColor = MaterialTheme.colorScheme.background,
                                scrolledContainerColor = MaterialTheme.colorScheme.background,
                            ),
                            title = {
                                if (destination == AppDestination.Chat) {
                                    ChatTopAppBarTitle(
                                        state = state,
                                        onRequestModels = viewModel::requestModels,
                                        onSelectModel = viewModel::selectModel,
                                    )
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
                            actions = {
                                if (destination == AppDestination.Chat) {
                                    IconButton(
                                        onClick = {
                                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                                            viewModel.startNewChat()
                                            destination = AppDestination.Chat
                                        },
                                        enabled = !state.isStreaming,
                                    ) {
                                        Icon(
                                            imageVector = Icons.Filled.Edit,
                                            contentDescription = stringResource(R.string.new_chat),
                                        )
                                    }
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
                            onConnect = viewModel::connectToTrustedRuntime,
                            onRefreshHealth = viewModel::requestRuntimeHealth,
                            onRequestModels = viewModel::requestModels,
                            onSelectModel = viewModel::selectModel,
                            onAttachFiles = { attachmentPickerLauncher.launch("*/*") },
                            onRemoveAttachment = viewModel::removePendingAttachment,
                            onSuggestionClick = viewModel::useSuggestedQuestion,
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(padding),
                        )
                        AppDestination.Pairing -> PairingScreen(
                            state = state,
                            onStartDiscovery = viewModel::startDiscovery,
                            onStopDiscovery = viewModel::stopDiscovery,
                            onUseDiscoveredRuntime = viewModel::useDiscoveredRuntime,
                            onForgetTrustedRuntime = viewModel::forgetTrustedRuntime,
                            onScanPairingQr = {
                                startPairingQrScanner(
                                    context = context,
                                    onResult = viewModel::trustRuntimeFromPairingQr,
                                    onFailure = viewModel::showQrScanFailed,
                                )
                            },
                            onConnect = viewModel::connectToTrustedRuntime,
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
                            onStartDiscovery = viewModel::startDiscovery,
                            onStopDiscovery = viewModel::stopDiscovery,
                            onUseDiscoveredRuntime = viewModel::useDiscoveredRuntime,
                            onForgetTrustedRuntime = viewModel::forgetTrustedRuntime,
                            onScanPairingQr = {
                                startPairingQrScanner(
                                    context = context,
                                    onResult = viewModel::trustRuntimeFromPairingQr,
                                    onFailure = viewModel::showQrScanFailed,
                                )
                            },
                            onConnect = viewModel::connectToTrustedRuntime,
                            onRefreshHealth = viewModel::requestRuntimeHealth,
                            onRequestModels = viewModel::requestModels,
                            onDisconnect = viewModel::disconnect,
                            onSetAutoReconnectEnabled = viewModel::setTrustedRuntimeAutoReconnectEnabled,
                            onSetLanguageTag = viewModel::setAppLanguageTag,
                            onSelectEmbeddingModel = viewModel::selectEmbeddingModel,
                            onAddMemoryEntry = viewModel::addMemoryEntry,
                            onRemoveMemoryEntry = viewModel::removeMemoryEntry,
                            onSetMemoryEntryEnabled = viewModel::setMemoryEntryEnabled,
                            onArchiveChatSession = viewModel::archiveChatSession,
                            onRestoreChatSession = viewModel::unarchiveChatSession,
                            onPermanentlyDeleteChatSession = viewModel::deleteChatSession,
                            onArchiveAllChatSessions = viewModel::archiveChatSessions,
                            onPermanentlyDeleteArchivedChatSessions = viewModel::clearArchivedChatSessions,
                            showDeveloperDiagnostics = BuildConfig.DEBUG,
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

            }
        }
    }
}

@Composable
private fun LocalizedContent(
    languageTag: String,
    content: @Composable () -> Unit,
) {
    val baseContext = LocalContext.current
    val configuration = LocalConfiguration.current
    val localizedContext = remember(baseContext, configuration, languageTag) {
        val cleanLanguageTag = languageTag.trim()
        if (cleanLanguageTag.isBlank()) {
            baseContext
        } else {
            val locale = Locale.forLanguageTag(cleanLanguageTag)
            val localizedConfiguration = Configuration(configuration)
            localizedConfiguration.setLocale(locale)
            localizedConfiguration.setLocales(LocaleList(locale))
            baseContext.createConfigurationContext(localizedConfiguration)
        }
    }

    CompositionLocalProvider(LocalContext provides localizedContext) {
        content()
    }
}

@Composable
private fun ChatTopAppBarTitle(
    state: RuntimeUiState,
    onRequestModels: () -> Unit,
    onSelectModel: (String) -> Unit,
) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
    ) {
        ChatModelTopBarMenu(
            state = state,
            onRequestModels = onRequestModels,
            onSelectModel = onSelectModel,
        )
    }
}

@Composable
private fun ChatModelTopBarMenu(
    state: RuntimeUiState,
    onRequestModels: () -> Unit,
    onSelectModel: (String) -> Unit,
) {
    var isExpanded by rememberSaveable { mutableStateOf(false) }
    var modelSearchQuery by rememberSaveable { mutableStateOf("") }
    val hapticFeedback = LocalHapticFeedback.current
    val chatModels = state.models.filter { it.isChatModel() }
    val selectedModel = chatModels.firstOrNull { it.id == state.selectedModelId }
    val selectedModelUnavailable = state.selectedModelId != null && selectedModel == null
    val selectedModelRecoveryMessage = when {
        state.isLoadingModels -> stringResource(R.string.selected_model_restoring)
        state.isConnected -> stringResource(R.string.selected_model_unavailable)
        else -> stringResource(R.string.selected_model_restoring)
    }
    val selectedLabel = when {
        selectedModel != null -> selectedModel.name
        state.isLoadingModels -> stringResource(R.string.loading_models)
        else -> stringResource(R.string.choose_model)
    }
    val modelPickerStateDescription = when {
        selectedModel != null -> selectedModel.name
        selectedModelUnavailable -> selectedModelRecoveryMessage
        state.isLoadingModels -> stringResource(R.string.loading_models)
        !state.isConnected -> stringResource(R.string.chat_status_disconnected)
        else -> stringResource(R.string.chat_hint_select_model)
    }
    val trimmedModelSearchQuery = modelSearchQuery.trim()
    val hasModelSearchQuery = trimmedModelSearchQuery.isNotEmpty()
    val visibleModels = if (hasModelSearchQuery) {
        chatModels.filter { model -> model.matchesModelQuery(trimmedModelSearchQuery) }
    } else {
        chatModels
    }

    Box {
        TextButton(
            onClick = {
                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                isExpanded = true
                if (state.isConnected && chatModels.isEmpty() && !state.isLoadingModels) {
                    onRequestModels()
                }
            },
            enabled = !state.isStreaming,
            shape = androidx.compose.foundation.shape.RoundedCornerShape(18.dp),
            colors = ButtonDefaults.textButtonColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f),
                contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.36f),
                disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.52f),
            ),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(
                horizontal = 12.dp,
                vertical = 6.dp,
            ),
            modifier = Modifier
                .widthIn(max = 236.dp)
                .semantics {
                    stateDescription = modelPickerStateDescription
                },
        ) {
            Text(
                text = selectedLabel,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Icon(
                imageVector = Icons.Filled.KeyboardArrowDown,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
        }
        DropdownMenu(
            expanded = isExpanded,
            onDismissRequest = { isExpanded = false },
            modifier = Modifier
                .widthIn(min = 260.dp, max = 360.dp)
                .heightIn(max = 420.dp),
        ) {
            DropdownMenuItem(
                text = {
                    Column {
                        Text(
                            text = if (state.isLoadingModels) {
                                stringResource(R.string.loading_models)
                            } else {
                                stringResource(R.string.load_models)
                            },
                        )
                        Text(
                            text = selectedModel?.let { model ->
                                stringResource(
                                    R.string.model_provider_value,
                                    runtimeProviderDisplayName(model.provider),
                                )
                            } ?: if (state.isConnected) {
                                stringResource(R.string.chat_status_connected)
                            } else {
                                stringResource(R.string.chat_status_disconnected)
                            },
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                },
                leadingIcon = { Icon(Icons.Filled.Refresh, contentDescription = null) },
                enabled = state.isConnected && !state.isLoadingModels,
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onRequestModels()
                },
            )
            HorizontalDivider()
            if (selectedModelUnavailable) {
                DropdownMenuItem(
                    text = {
                        Column {
                            Text(
                                text = stringResource(R.string.selected_model_unavailable),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                text = selectedModelRecoveryMessage,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 3,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    },
                    enabled = false,
                    onClick = {},
                )
                HorizontalDivider()
            }
            if (chatModels.isEmpty()) {
                DropdownMenuItem(
                    text = {
                        Text(
                            text = if (state.isConnected) {
                                stringResource(R.string.no_models_connected)
                            } else {
                                stringResource(R.string.no_models_disconnected)
                            },
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    },
                    enabled = false,
                    onClick = {},
                )
            } else {
                OutlinedTextField(
                    value = modelSearchQuery,
                    onValueChange = { modelSearchQuery = it },
                    singleLine = true,
                    textStyle = MaterialTheme.typography.bodyMedium,
                    label = {
                        Text(
                            text = stringResource(R.string.model_search_label),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    },
                    leadingIcon = {
                        Icon(
                            imageVector = Icons.Filled.Search,
                            contentDescription = null,
                        )
                    },
                    trailingIcon = {
                        if (modelSearchQuery.isNotEmpty()) {
                            IconButton(
                                onClick = {
                                    modelSearchQuery = ""
                                },
                            ) {
                                Icon(
                                    imageVector = Icons.Filled.Close,
                                    contentDescription = stringResource(R.string.clear_model_search),
                                )
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                )
                if (visibleModels.isEmpty()) {
                    DropdownMenuItem(
                        text = {
                            Text(
                                text = stringResource(R.string.no_model_search_results),
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                        },
                        enabled = false,
                        onClick = {},
                    )
                }
                visibleModels.forEach { model ->
                    ChatModelMenuItem(
                        model = model,
                        selected = model.id == state.selectedModelId,
                        installing = model.id == state.installingModelId,
                        onSelect = {
                            hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                            onSelectModel(model.id)
                            isExpanded = false
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun ChatModelMenuItem(
    model: RuntimeModel,
    selected: Boolean,
    installing: Boolean,
    onSelect: () -> Unit,
) {
    DropdownMenuItem(
        text = {
            Column {
                Text(
                    text = model.name,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = modelMenuStatusLine(model = model, installing = installing),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        },
        trailingIcon = {
            if (selected) {
                Icon(
                    imageVector = Icons.Filled.CheckCircle,
                    contentDescription = null,
                )
            }
        },
        enabled = !installing,
        onClick = onSelect,
    )
}

@Composable
private fun modelMenuStatusLine(model: RuntimeModel, installing: Boolean): String {
    val availability = when {
        installing -> stringResource(R.string.installing_model)
        !model.installed -> stringResource(R.string.install_model)
        model.running -> stringResource(R.string.model_running)
        else -> stringResource(R.string.model_installed)
    }
    return "${runtimeProviderDisplayName(model.provider)} - $availability"
}

private fun RuntimeModel.matchesModelQuery(query: String): Boolean {
    return listOfNotNull(
        id,
        name,
        backend,
        provider,
        providerModelId,
        source,
        description,
    ).any { value -> value.contains(query, ignoreCase = true) }
}

@Composable
private fun ChatHistorySearchField(
    query: String,
    onQueryChange: (String) -> Unit,
    onClear: () -> Unit,
) {
    OutlinedTextField(
        value = query,
        onValueChange = onQueryChange,
        singleLine = true,
        textStyle = MaterialTheme.typography.bodyMedium,
        label = {
            Text(
                text = stringResource(R.string.chat_search_label),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        },
        leadingIcon = {
            Icon(
                imageVector = Icons.Filled.Search,
                contentDescription = null,
            )
        },
        trailingIcon = {
            if (query.isNotEmpty()) {
                IconButton(
                    onClick = {
                        onClear()
                    },
                ) {
                    Icon(
                        imageVector = Icons.Filled.Close,
                        contentDescription = stringResource(R.string.clear_chat_search),
                    )
                }
            }
        },
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
    )
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
    onDelete: (() -> Unit)?,
) {
    var isMenuExpanded by rememberSaveable(session.id) { mutableStateOf(false) }
    val hapticFeedback = LocalHapticFeedback.current
    val title = session.title.ifBlank { stringResource(R.string.untitled_chat) }
    val subtitle = when {
        session.archivedAtMillis != null -> stringResource(R.string.archived_chat)
        session.messageCount > 0 -> stringResource(R.string.chat_message_count, session.messageCount)
        session.updatedAtMillis > 0L -> stringResource(R.string.new_chat)
        else -> ""
    }

    NavigationDrawerItem(
        selected = selected,
        onClick = {
            if (enabled) {
                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                onClick()
            }
        },
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
                    onClick = {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                        isMenuExpanded = true
                    },
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
                    if (onDelete != null) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.delete_chat)) },
                            leadingIcon = { Icon(Icons.Filled.Archive, contentDescription = null) },
                            onClick = {
                                isMenuExpanded = false
                                onDelete()
                            },
                        )
                    }
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
    val hapticFeedback = LocalHapticFeedback.current

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
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onConfirm()
                },
                enabled = title.isNotBlank(),
            ) {
                Text(stringResource(R.string.save))
            }
        },
        dismissButton = {
            TextButton(
                onClick = {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    onDismiss()
                },
            ) {
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
