package com.localagentbridge.android

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.os.Bundle
import android.os.LocaleList
import androidx.activity.SystemBarStyle
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivityResultRegistryOwner
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Archive
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.FlashlightOff
import androidx.compose.material.icons.filled.FlashlightOn
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
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
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.localagentbridge.android.runtime.RuntimeClientViewModel
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimeAppTheme
import com.localagentbridge.android.runtime.RuntimeUiState
import com.localagentbridge.android.runtime.isChatModel
import com.localagentbridge.android.runtime.isEmbeddingModel
import com.localagentbridge.android.runtime.isRuntimeHostLocalModel
import com.localagentbridge.android.runtime.supportsImageInput
import com.localagentbridge.android.core.pairing.RuntimePairingPayloadParser
import com.localagentbridge.android.ui.AetherLinkInteractionFeedback
import com.localagentbridge.android.ui.ChatScreen
import com.localagentbridge.android.ui.SettingsScreen
import com.localagentbridge.android.ui.aetherLinkHapticFeedbackType
import com.localagentbridge.android.ui.chatHistorySessionStatusRes
import com.localagentbridge.android.ui.runtimeProviderDisplayName
import kotlinx.coroutines.launch
import java.net.URI
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

private fun HapticFeedback.performAetherLinkFeedback(feedback: AetherLinkInteractionFeedback) {
    performHapticFeedback(aetherLinkHapticFeedbackType(feedback))
}

class MainActivity : ComponentActivity() {
    private val pairingUriState = mutableStateOf<String?>(null)
    private val developerDiagnosticsState = mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pairingUriState.value = intent.pairingUriOrNull()
        developerDiagnosticsState.value = shouldEnableDeveloperDiagnostics(
            isDebugBuild = BuildConfig.DEBUG,
            requestedByLaunch = intent.developerDiagnosticsRequested(),
        )
        setContent {
            LocalAgentBridgeApp(
                pairingUri = pairingUriState.value,
                showDeveloperDiagnostics = developerDiagnosticsState.value,
                onPairingUriConsumed = { pairingUriState.value = null },
            )
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        pairingUriState.value = intent.pairingUriOrNull()
        developerDiagnosticsState.value = shouldEnableDeveloperDiagnostics(
            isDebugBuild = BuildConfig.DEBUG,
            requestedByLaunch = intent.developerDiagnosticsRequested(),
        )
    }
}

internal const val DEVELOPER_DIAGNOSTICS_EXTRA = "aetherlink.dev_diagnostics"

internal fun shouldEnableDeveloperDiagnostics(
    isDebugBuild: Boolean,
    requestedByLaunch: Boolean,
): Boolean {
    return isDebugBuild && requestedByLaunch
}

private fun Intent.developerDiagnosticsRequested(): Boolean {
    return getBooleanExtra(DEVELOPER_DIAGNOSTICS_EXTRA, false)
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun LocalAgentBridgeApp(
    pairingUri: String? = null,
    showDeveloperDiagnostics: Boolean = false,
    onPairingUriConsumed: () -> Unit = {},
) {
    val viewModel: RuntimeClientViewModel = viewModel()
    val state by viewModel.state.collectAsStateWithLifecycle()
    AetherLinkTheme(theme = state.selectedTheme) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background,
        ) {
            LocalizedContent(languageTag = state.selectedLanguageTag) {
            val context = LocalContext.current
            val configuration = LocalConfiguration.current
            val hapticFeedback = LocalHapticFeedback.current
            val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
            val scope = rememberCoroutineScope()
            val snackbarHostState = remember { SnackbarHostState() }
            val usePermanentNavigation = shouldUsePermanentNavigationRail(configuration.screenWidthDp)
            var destination by rememberSaveable { mutableStateOf(AppDestination.Chat) }
            var renamingSessionId by rememberSaveable { mutableStateOf<String?>(null) }
            var renameDraft by rememberSaveable { mutableStateOf("") }
            var chatSearchQuery by rememberSaveable { mutableStateOf("") }
            var showPairingQrScanner by rememberSaveable { mutableStateOf(false) }
            var settingsOpenedForPairingOnboarding by rememberSaveable { mutableStateOf(false) }
            var returnToChatAfterPairing by rememberSaveable { mutableStateOf(false) }
            val effectiveDestination = resolveAppDestination(
                current = destination,
                hasTrustedRuntime = state.trustedRuntime != null,
            )
            val destinationTitle = stringResource(
                appDestinationTitleRes(
                    destination = effectiveDestination,
                    hasTrustedRuntime = state.trustedRuntime != null,
                    isPairingAwaitingRoute = state.isPairingAwaitingRoute,
                )
            )
            val untitledChatTitle = stringResource(R.string.untitled_chat)
            val chatArchivedSnackbar = stringResource(R.string.chat_archived_snackbar)
            val qrScanCanceledSnackbar = stringResource(R.string.qr_scan_canceled_snackbar)
            val undoAction = stringResource(R.string.undo)
            val trimmedChatSearchQuery = chatSearchQuery.trim()
            val hasChatSearchQuery = trimmedChatSearchQuery.isNotEmpty()
            val hasAnyChatSessions = state.chatSessions.isNotEmpty()
            val filteredChatSessions = if (hasChatSearchQuery) {
                state.chatSessions.filter { session ->
                    session.localizedTitle(untitledChatTitle)
                        .contains(trimmedChatSearchQuery, ignoreCase = true)
                }
            } else {
                state.chatSessions
            }
            val hasChatSearchResults = filteredChatSessions.isNotEmpty()
            val attachmentPickerLauncher = rememberLauncherForActivityResult(
                contract = ActivityResultContracts.OpenMultipleDocuments(),
            ) { uris ->
                viewModel.addAttachments(uris)
            }
            val handlePairingQr: (String) -> Unit = { rawValue ->
                returnToChatAfterPairing = state.trustedRuntime == null ||
                    destination == AppDestination.Chat ||
                    state.isPairingAwaitingRoute
                settingsOpenedForPairingOnboarding = true
                destination = AppDestination.Settings
                viewModel.trustRuntimeFromPairingQr(rawValue)
            }
            val scanPairingQr = {
                showPairingQrScanner = true
            }

            LaunchedEffect(pairingUri) {
                val uri = pairingUri?.takeIf { it.isNotBlank() } ?: return@LaunchedEffect
                returnToChatAfterPairing = true
                settingsOpenedForPairingOnboarding = true
                destination = AppDestination.Settings
                viewModel.trustRuntimeFromPairingQr(uri)
                onPairingUriConsumed()
            }

            LaunchedEffect(
                destination,
                state.trustedRuntime?.deviceId,
                state.isConnected,
                state.isConnecting,
                state.isPairingAwaitingRoute,
                returnToChatAfterPairing,
                settingsOpenedForPairingOnboarding,
            ) {
                val hasTrustedRuntime = state.trustedRuntime != null
                if (
                    shouldReturnToChatAfterPairing(
                        returnToChatAfterPairing = returnToChatAfterPairing,
                        hasTrustedRuntime = hasTrustedRuntime,
                        isConnected = state.isConnected,
                        isConnecting = state.isConnecting,
                        isPairingAwaitingRoute = state.isPairingAwaitingRoute,
                    )
                ) {
                    destination = AppDestination.Chat
                    returnToChatAfterPairing = false
                    settingsOpenedForPairingOnboarding = false
                    return@LaunchedEffect
                }
                val resolved = resolveAppDestination(
                    current = destination,
                    hasTrustedRuntime = hasTrustedRuntime,
                )
                if (resolved != destination) {
                    if (resolved == AppDestination.Settings && !hasTrustedRuntime) {
                        settingsOpenedForPairingOnboarding = true
                    }
                    destination = resolved
                } else if (
                    shouldLeavePairingSettingsAfterTrustedRuntimeReady(
                        destination = destination,
                        hasTrustedRuntime = hasTrustedRuntime,
                        settingsOpenedForPairingOnboarding = settingsOpenedForPairingOnboarding,
                        isPairingAwaitingRoute = state.isPairingAwaitingRoute,
                    )
                ) {
                    destination = AppDestination.Chat
                    settingsOpenedForPairingOnboarding = false
                }
            }

            if (showPairingQrScanner) {
                PairingQrScannerScreen(
                    onResult = { rawValue ->
                        showPairingQrScanner = false
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        handlePairingQr(rawValue)
                    },
                    onCancel = {
                        showPairingQrScanner = false
                        scope.launch {
                            snackbarHostState.showSnackbar(qrScanCanceledSnackbar)
                        }
                    },
                    onFailure = { detail ->
                        showPairingQrScanner = false
                        viewModel.showQrScanFailed(detail)
                    },
                    modifier = Modifier.fillMaxSize(),
                )
            } else {
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
                            DrawerRuntimeSummary(state = state)
                            Button(
                                onClick = {
                                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
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
                                        onClear = {
                                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                            chatSearchQuery = ""
                                        },
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
                                            selected = effectiveDestination == AppDestination.Chat &&
                                                session.id == state.activeChatSessionId,
                                            enabled = !state.isStreaming,
                                            onClick = {
                                                viewModel.selectChatSession(session.id)
                                                destination = AppDestination.Chat
                                                scope.launch { drawerState.close() }
                                            },
                                            onRename = {
                                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                                renamingSessionId = session.id
                                                renameDraft = session.editableTitle()
                                            },
                                            onArchive = {
                                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                                                val archivedSessionId = session.id
                                                viewModel.archiveChatSession(archivedSessionId)
                                                scope.launch {
                                                    drawerState.close()
                                                    val result = snackbarHostState.showSnackbar(
                                                        message = chatArchivedSnackbar,
                                                        actionLabel = undoAction,
                                                        withDismissAction = true,
                                                    )
                                                    if (result == SnackbarResult.ActionPerformed) {
                                                        viewModel.unarchiveChatSession(archivedSessionId)
                                                    }
                                                }
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
                                selected = effectiveDestination == AppDestination.Settings,
                                onClick = {
                                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                                    returnToChatAfterPairing = false
                                    settingsOpenedForPairingOnboarding = false
                                    destination = AppDestination.Settings
                                    scope.launch { drawerState.close() }
                                },
                            )
                        }
                    }
                },
            ) {
                Row(modifier = Modifier.fillMaxSize()) {
                    if (usePermanentNavigation) {
                        AetherLinkPermanentNavigationRail(
                            selectedDestination = effectiveDestination,
                            newChatEnabled = !state.isStreaming,
                            onNewChat = {
                                viewModel.startNewChat()
                                destination = AppDestination.Chat
                            },
                            onSelectDestination = { selectedDestination ->
                                if (selectedDestination == AppDestination.Settings) {
                                    returnToChatAfterPairing = false
                                    settingsOpenedForPairingOnboarding = false
                                }
                                destination = selectedDestination
                            },
                        )
                    }
                    Scaffold(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight(),
                        snackbarHost = { SnackbarHost(snackbarHostState) },
                        topBar = {
                            Column {
                                TopAppBar(
                                    colors = TopAppBarDefaults.topAppBarColors(
                                        containerColor = MaterialTheme.colorScheme.background,
                                        scrolledContainerColor = MaterialTheme.colorScheme.surface,
                                    ),
                                    title = {
                                        if (effectiveDestination == AppDestination.Chat) {
                                            ChatTopAppBarTitle(
                                                state = state,
                                                onRequestModels = viewModel::requestModels,
                                                onSelectModel = viewModel::selectModel,
                                                onSelectEmbeddingModel = viewModel::selectEmbeddingModel,
                                            )
                                        } else {
                                            Text(destinationTitle)
                                        }
                                    },
                                    navigationIcon = {
                                        IconButton(
                                            onClick = {
                                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
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
                                        if (effectiveDestination == AppDestination.Chat) {
                                            IconButton(
                                                onClick = {
                                                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
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
                                HorizontalDivider(
                                    color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.36f),
                                )
                            }
                        },
                    ) { padding ->
                        when (effectiveDestination) {
                            AppDestination.Chat -> ChatScreen(
                                state = state,
                                onInputChange = viewModel::updateChatInput,
                                onSend = viewModel::sendChatMessage,
                                onCancel = viewModel::cancelGeneration,
                                onConnect = viewModel::connectToTrustedRuntime,
                                onScanPairingQr = scanPairingQr,
                                onRefreshHealth = viewModel::requestRuntimeHealth,
                                onAttachFiles = { attachmentPickerLauncher.launch(attachmentPickerMimeTypes(state)) },
                                onRemoveAttachment = viewModel::removePendingAttachment,
                                onSuggestionClick = viewModel::useSuggestedQuestion,
                                onScanLatestQr = scanPairingQr,
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
                                onScanPairingQr = scanPairingQr,
                                onSubmitPairingPayload = handlePairingQr,
                                onConnect = viewModel::connectToTrustedRuntime,
                                onRefreshHealth = viewModel::requestRuntimeHealth,
                                onRequestModels = viewModel::requestModels,
                                onDisconnect = viewModel::disconnect,
                                onSetAutoReconnectEnabled = viewModel::setTrustedRuntimeAutoReconnectEnabled,
                                onSetLanguageTag = viewModel::setAppLanguageTag,
                                onSetTheme = viewModel::setAppTheme,
                                onSelectEmbeddingModel = viewModel::selectEmbeddingModel,
                                onAddMemoryEntry = viewModel::addMemoryEntry,
                                onRemoveMemoryEntry = viewModel::removeMemoryEntry,
                                onSetMemoryEntryEnabled = viewModel::setMemoryEntryEnabled,
                                onArchiveChatSession = viewModel::archiveChatSession,
                                onRestoreChatSession = viewModel::unarchiveChatSession,
                                onPermanentlyDeleteChatSession = viewModel::deleteChatSession,
                                onArchiveAllChatSessions = viewModel::archiveChatSessions,
                                onPermanentlyDeleteArchivedChatSessions = viewModel::clearArchivedChatSessions,
                                showDeveloperDiagnostics = showDeveloperDiagnostics,
                                modifier = Modifier
                                    .fillMaxSize()
                                    .padding(padding),
                            )
                        }
                    }
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
    val activityResultRegistryOwner = checkNotNull(LocalActivityResultRegistryOwner.current) {
        "ActivityResultRegistryOwner is required for AetherLink."
    }
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

    CompositionLocalProvider(
        LocalContext provides localizedContext,
        LocalActivityResultRegistryOwner provides activityResultRegistryOwner,
    ) {
        content()
    }
}

@Composable
private fun AetherLinkPermanentNavigationRail(
    selectedDestination: AppDestination,
    newChatEnabled: Boolean,
    onNewChat: () -> Unit,
    onSelectDestination: (AppDestination) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current

    NavigationRail(
        modifier = Modifier
            .fillMaxHeight()
            .width(84.dp),
        containerColor = MaterialTheme.colorScheme.surface,
        header = {
            IconButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    onNewChat()
                },
                enabled = newChatEnabled,
            ) {
                Icon(
                    imageVector = Icons.Filled.Edit,
                    contentDescription = stringResource(R.string.new_chat),
                )
            }
        },
    ) {
        NavigationRailItem(
            selected = selectedDestination == AppDestination.Chat,
            onClick = {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                onSelectDestination(AppDestination.Chat)
            },
            icon = {
                Icon(
                    imageVector = AppDestination.Chat.icon,
                    contentDescription = null,
                )
            },
            label = {
                Text(
                    text = stringResource(AppDestination.Chat.labelRes),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            },
        )
        Spacer(Modifier.weight(1f))
        NavigationRailItem(
            selected = selectedDestination == AppDestination.Settings,
            onClick = {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                onSelectDestination(AppDestination.Settings)
            },
            icon = {
                Icon(
                    imageVector = Icons.Filled.Settings,
                    contentDescription = null,
                )
            },
            label = {
                Text(
                    text = stringResource(AppDestination.Settings.labelRes),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            },
        )
    }
}

@Composable
internal fun ChatTopAppBarTitle(
    state: RuntimeUiState,
    onRequestModels: () -> Unit,
    onSelectModel: (String) -> Unit,
    onSelectEmbeddingModel: (String?) -> Unit,
) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
    ) {
        ChatModelTopBarMenu(
            state = state,
            onRequestModels = onRequestModels,
            onSelectModel = onSelectModel,
            onSelectEmbeddingModel = onSelectEmbeddingModel,
        )
    }
}

@Composable
private fun ChatModelTopBarMenu(
    state: RuntimeUiState,
    onRequestModels: () -> Unit,
    onSelectModel: (String) -> Unit,
    onSelectEmbeddingModel: (String?) -> Unit,
) {
    var isExpanded by rememberSaveable { mutableStateOf(false) }
    var modelSearchQuery by rememberSaveable { mutableStateOf("") }
    val hapticFeedback = LocalHapticFeedback.current
    val chatModels = chatModelMenuModels(
        models = state.models,
        selectedModelId = state.selectedModelId,
    )
    val selectedModel = chatModels.firstOrNull { it.id == state.selectedModelId }
    val selectedModelUnavailable = state.selectedModelId != null && selectedModel == null
    val selectedModelRecoveryMessage = when {
        state.isLoadingModels -> stringResource(R.string.selected_model_restoring)
        state.isConnected -> stringResource(R.string.selected_model_unavailable)
        else -> stringResource(R.string.selected_model_restoring)
    }
    val selectedLabel = chatModelPickerClosedLabel(
        state = state,
        loadingModelsLabel = stringResource(R.string.loading_models),
        chooseModelLabel = stringResource(R.string.choose_model),
    )
    val modelPickerStateDescription = when {
        selectedModel != null -> selectedModel.name
        selectedModelUnavailable -> selectedModelRecoveryMessage
        state.isLoadingModels -> stringResource(R.string.loading_models)
        !state.isConnected -> stringResource(R.string.chat_status_disconnected)
        else -> stringResource(R.string.chat_hint_select_model)
    }
    val trimmedModelSearchQuery = modelSearchQuery.trim()
    val visibleModels = chatModelMenuModels(
        models = state.models,
        query = trimmedModelSearchQuery,
        selectedModelId = state.selectedModelId,
    )
    val allEmbeddingModels = embeddingModelMenuModels(
        models = state.models,
        selectedEmbeddingModelId = state.selectedEmbeddingModelId,
    )
    val visibleEmbeddingModels = embeddingModelMenuModels(
        models = state.models,
        query = trimmedModelSearchQuery,
        selectedEmbeddingModelId = state.selectedEmbeddingModelId,
    )
    val selectedEmbeddingModel = allEmbeddingModels.firstOrNull { it.id == state.selectedEmbeddingModelId }
    val selectedEmbeddingModelUnavailable =
        state.selectedEmbeddingModelId != null && selectedEmbeddingModel == null
    val hasSearchableModels = modelMenuSearchAvailable(state.models)

    Box {
        TextButton(
            onClick = {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
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
                .widthIn(max = 220.dp)
                .semantics {
                    stateDescription = modelPickerStateDescription
                },
        ) {
            Icon(
                imageVector = if (selectedModel != null) Icons.Filled.CheckCircle else Icons.Filled.Search,
                contentDescription = null,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.size(6.dp))
            Text(
                text = selectedLabel,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.labelLarge,
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
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    onRequestModels()
                },
            )
            HorizontalDivider()
            if (selectedModelUnavailable) {
                DropdownInfoItem {
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
                }
                HorizontalDivider()
            }
            if (hasSearchableModels) {
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
                                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
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
            }
            if (chatModels.isEmpty()) {
                DropdownInfoItem {
                    Text(
                        text = if (state.isConnected) {
                            stringResource(R.string.no_models_connected)
                        } else {
                            stringResource(R.string.no_models_disconnected)
                        },
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            } else {
                if (visibleModels.isEmpty()) {
                    DropdownInfoItem {
                        Text(
                            text = stringResource(R.string.no_model_search_results),
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
                visibleModels.forEach { model ->
                    ChatModelMenuItem(
                        model = model,
                        selected = model.id == state.selectedModelId,
                        installing = model.id == state.installingModelId,
                        onSelect = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                            onSelectModel(model.id)
                            isExpanded = false
                        },
                    )
                }
            }
            HorizontalDivider()
            DropdownInfoItem(
                modifier = Modifier.padding(top = 2.dp, bottom = 2.dp),
            ) {
                Column {
                    Text(
                        text = stringResource(R.string.embedding_model_title),
                        style = MaterialTheme.typography.labelLarge,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = selectedEmbeddingModel?.name
                            ?: state.selectedEmbeddingModelId?.let(::savedModelDisplayName)
                            ?: stringResource(R.string.embedding_model_none_detail),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            EmbeddingModelMenuItem(
                model = null,
                selected = state.selectedEmbeddingModelId == null,
                onSelect = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                    onSelectEmbeddingModel(null)
                    isExpanded = false
                },
            )
            if (selectedEmbeddingModelUnavailable) {
                DropdownInfoItem {
                    Column {
                        Text(
                            text = stringResource(R.string.selected_embedding_model_unavailable),
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            text = stringResource(R.string.selected_embedding_model_restoring),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
            if (visibleEmbeddingModels.isEmpty()) {
                DropdownInfoItem {
                    Text(
                        text = stringResource(
                            embeddingModelMenuEmptyTextRes(
                                isConnected = state.isConnected,
                                hasEmbeddingModels = allEmbeddingModels.isNotEmpty(),
                                hasSearchQuery = trimmedModelSearchQuery.isNotEmpty(),
                            ),
                        ),
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            } else {
                visibleEmbeddingModels.forEach { model ->
                    EmbeddingModelMenuItem(
                        model = model,
                        selected = model.id == state.selectedEmbeddingModelId,
                        onSelect = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                            onSelectEmbeddingModel(model.id)
                            isExpanded = false
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun DropdownInfoItem(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        content()
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
        enabled = chatModelMenuItemEnabled(model, installing),
        onClick = onSelect,
    )
}

@Composable
private fun EmbeddingModelMenuItem(
    model: RuntimeModel?,
    selected: Boolean,
    onSelect: () -> Unit,
) {
    DropdownMenuItem(
        text = {
            Column {
                Text(
                    text = model?.name ?: stringResource(R.string.model_none),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = model?.let { modelMenuStatusLine(model = it, installing = false) }
                        ?: stringResource(R.string.embedding_model_none_detail),
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
        enabled = model == null || embeddingModelMenuItemEnabled(model),
        onClick = onSelect,
    )
}

internal fun chatModelMenuItemEnabled(model: RuntimeModel, installing: Boolean): Boolean {
    return model.isChatModel() && model.isRuntimeHostLocalModel() && !installing
}

internal fun embeddingModelMenuItemEnabled(model: RuntimeModel): Boolean {
    return model.isEmbeddingModel() && model.installed && model.isRuntimeHostLocalModel()
}

internal fun modelMenuSearchAvailable(models: List<RuntimeModel>): Boolean {
    return chatModelMenuModels(models).isNotEmpty() || embeddingModelMenuModels(models).isNotEmpty()
}

internal fun embeddingModelMenuEmptyTextRes(
    isConnected: Boolean,
    hasEmbeddingModels: Boolean,
    hasSearchQuery: Boolean,
): Int {
    return when {
        hasSearchQuery && hasEmbeddingModels -> R.string.no_model_search_results
        isConnected -> R.string.embedding_model_empty
        else -> R.string.embedding_model_connect_first
    }
}

@Composable
private fun modelMenuStatusLine(model: RuntimeModel, installing: Boolean): String {
    val availability = when {
        installing -> stringResource(R.string.installing_model)
        !model.installed -> stringResource(R.string.model_not_installed)
        model.running -> stringResource(R.string.model_running)
        else -> stringResource(R.string.model_installed)
    }
    return "${runtimeProviderDisplayName(model.provider)} - $availability"
}

internal fun chatModelMenuModels(
    models: List<RuntimeModel>,
    query: String = "",
    selectedModelId: String? = null,
): List<RuntimeModel> {
    val trimmedQuery = query.trim()
    return models
        .asSequence()
        .filter { it.isChatModel() && it.isRuntimeHostLocalModel() }
        .filter { model ->
            trimmedQuery.isEmpty() ||
                model.id == selectedModelId ||
                model.matchesModelQuery(trimmedQuery)
        }
        .sortedWith(
            compareByDescending<RuntimeModel> { it.id == selectedModelId }
                .thenByDescending { it.running }
                .thenBy { it.name.lowercase(Locale.US) },
        )
        .toList()
}

internal fun embeddingModelMenuModels(
    models: List<RuntimeModel>,
    query: String = "",
    selectedEmbeddingModelId: String? = null,
): List<RuntimeModel> {
    val trimmedQuery = query.trim()
    return models
        .asSequence()
        .filter { it.isEmbeddingModel() && it.installed && it.isRuntimeHostLocalModel() }
        .filter { model ->
            trimmedQuery.isEmpty() ||
                model.id == selectedEmbeddingModelId ||
                model.matchesModelQuery(trimmedQuery)
        }
        .sortedWith(
            compareByDescending<RuntimeModel> { it.id == selectedEmbeddingModelId }
                .thenByDescending { it.running }
                .thenBy { it.name.lowercase(Locale.US) },
        )
        .toList()
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

internal fun attachmentPickerMimeTypes(state: RuntimeUiState): Array<String> {
    val selectedModel = state.models.firstOrNull { it.id == state.selectedModelId }
    return if (selectedModel?.supportsImageInput() == true) {
        runtimeDocumentAttachmentMimeTypes + "image/*"
    } else {
        runtimeDocumentAttachmentMimeTypes
    }
}

private val runtimeDocumentAttachmentMimeTypes = arrayOf(
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-word.document.macroenabled.12",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    "application/vnd.ms-word.template.macroenabled.12",
    "application/haansofthwp",
    "application/hwp+zip",
    "application/x-hwp",
    "application/x-hwpml",
    "application/vnd.hancom.hwpml",
    "application/vnd.hancom.hwpx",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel.sheet.macroenabled.12",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.template",
    "application/vnd.ms-excel.template.macroenabled.12",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint.presentation.macroenabled.12",
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
    "application/vnd.ms-powerpoint.slideshow.macroenabled.12",
    "application/vnd.openxmlformats-officedocument.presentationml.template",
    "application/vnd.ms-powerpoint.template.macroenabled.12",
    "application/vnd.apple.pages",
    "application/vnd.apple.numbers",
    "application/vnd.apple.keynote",
    "application/epub+zip",
    "application/rtf",
    "application/x-webarchive",
    "application/json",
    "application/jsonl",
    "application/x-ndjson",
    "application/yaml",
    "application/x-yaml",
    "application/toml",
    "application/x-toml",
    "application/xml",
    "text/html",
    "text/rtf",
    "application/xhtml+xml",
    "text/csv",
    "text/tab-separated-values",
    "text/markdown",
    "text/x-rst",
    "text/asciidoc",
    "text/x-log",
    "text/yaml",
    "text/*",
)

internal fun savedModelDisplayName(modelId: String): String {
    val trimmed = modelId.trim()
    if (trimmed.isEmpty()) return trimmed
    val providerPrefix = trimmed.substringBefore(':', missingDelimiterValue = "")
        .lowercase(Locale.US)
    return if (providerPrefix in modelDisplayProviderPrefixes && ':' in trimmed) {
        trimmed.substringAfter(':').takeIf { it.isNotBlank() } ?: trimmed
    } else {
        trimmed
    }
}

internal fun chatModelPickerClosedLabel(
    state: RuntimeUiState,
    loadingModelsLabel: String,
    chooseModelLabel: String,
): String {
    val selectedModel = chatModelMenuModels(state.models)
        .firstOrNull { it.id == state.selectedModelId }
    return when {
        selectedModel != null -> selectedModel.name
        state.selectedModelId != null -> savedModelDisplayName(state.selectedModelId)
        state.isLoadingModels -> loadingModelsLabel
        else -> chooseModelLabel
    }
}

private val modelDisplayProviderPrefixes = setOf(
    "ollama",
    "lmstudio",
    "lm_studio",
    "companion",
    "runtime",
)

@Composable
private fun DrawerRuntimeSummary(state: RuntimeUiState) {
    val chatModels = chatModelMenuModels(state.models)
    val selectedModel = chatModels.firstOrNull { it.id == state.selectedModelId }
    val runtimeName = state.trustedRuntime?.name ?: stringResource(R.string.no_trusted_runtime)
    val modelName = selectedModel?.name
        ?: state.selectedModelId?.let(::savedModelDisplayName)
        ?: stringResource(R.string.model_none)
    val connectionLabel = when {
        state.isConnected -> stringResource(R.string.status_connected)
        state.isConnecting -> stringResource(R.string.status_connecting)
        state.trustedRuntime != null -> stringResource(R.string.status_disconnected)
        else -> stringResource(R.string.status_pairing_required)
    }
    val connectionTone = when {
        state.isConnected -> MaterialTheme.colorScheme.primary
        state.isConnecting -> MaterialTheme.colorScheme.secondary
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 2.dp),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.52f),
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 11.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(R.string.runtime),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = connectionLabel,
                    style = MaterialTheme.typography.labelSmall,
                    color = connectionTone,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(
                text = runtimeName,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.22f))
            Text(
                text = stringResource(R.string.selected_model),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.secondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = modelName,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
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
internal fun ChatSessionDrawerItem(
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
    val title = session.localizedTitle(stringResource(R.string.untitled_chat))
    val baseSubtitle = when {
        session.archivedAtMillis != null -> stringResource(R.string.archived_chat)
        session.messageCount > 0 -> stringResource(R.string.chat_message_count, session.messageCount)
        session.updatedAtMillis > 0L -> stringResource(R.string.new_chat)
        else -> ""
    }
    val statusRes = chatHistorySessionStatusRes(session)
    val subtitle = statusRes?.let { status ->
        val statusText = stringResource(status)
        if (baseSubtitle.isBlank()) {
            statusText
        } else {
            stringResource(R.string.chat_session_status_value, baseSubtitle, statusText)
        }
    } ?: baseSubtitle
    val subtitleColor = when (statusRes) {
        R.string.chat_session_status_failed -> MaterialTheme.colorScheme.error
        R.string.chat_session_status_in_progress -> MaterialTheme.colorScheme.primary
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    NavigationDrawerItem(
        selected = selected,
        onClick = {
            if (enabled) {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
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
	                            color = subtitleColor,
	                            maxLines = 1,
	                            overflow = TextOverflow.Ellipsis,
	                        )
	                    }
	                }
                IconButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
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
                            leadingIcon = { Icon(Icons.Filled.Delete, contentDescription = null) },
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

private fun RuntimeChatSession.localizedTitle(untitledTitle: String): String {
    val cleanTitle = title.trim()
    return if (cleanTitle.isBlank() || cleanTitle == LEGACY_DEFAULT_CHAT_TITLE) {
        untitledTitle
    } else {
        cleanTitle
    }
}

private fun RuntimeChatSession.editableTitle(): String {
    val cleanTitle = title.trim()
    return if (cleanTitle == LEGACY_DEFAULT_CHAT_TITLE) "" else cleanTitle
}

private const val LEGACY_DEFAULT_CHAT_TITLE = "New chat"

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
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
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
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
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
private fun AetherLinkTheme(theme: RuntimeAppTheme, content: @Composable () -> Unit) {
    val systemDarkTheme = isSystemInDarkTheme()
    val darkTheme = when (theme) {
        RuntimeAppTheme.System -> systemDarkTheme
        RuntimeAppTheme.Light -> false
        RuntimeAppTheme.Dark -> true
    }
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
    primary = Color(0xFF0F7B5F),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFD8F1E6),
    onPrimaryContainer = Color(0xFF062B20),
    secondary = Color(0xFF5B625F),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFE0E5E1),
    onSecondaryContainer = Color(0xFF1C211F),
    tertiary = Color(0xFF62605B),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFE7E3D8),
    onTertiaryContainer = Color(0xFF22201B),
    background = Color(0xFFFCFCFA),
    onBackground = Color(0xFF1B1C1A),
    surface = Color(0xFFFCFCFA),
    onSurface = Color(0xFF1B1C1A),
    surfaceVariant = Color(0xFFE6E8E3),
    onSurfaceVariant = Color(0xFF454843),
    outline = Color(0xFF747872),
)

private val AetherLinkDarkColors: ColorScheme = darkColorScheme(
    primary = Color(0xFF8BDDBF),
    onPrimary = Color(0xFF073625),
    primaryContainer = Color(0xFF14543D),
    onPrimaryContainer = Color(0xFFD8F1E6),
    secondary = Color(0xFFC4CBC6),
    onSecondary = Color(0xFF2D322F),
    secondaryContainer = Color(0xFF434A46),
    onSecondaryContainer = Color(0xFFE0E5E1),
    tertiary = Color(0xFFCBC6BB),
    onTertiary = Color(0xFF333029),
    tertiaryContainer = Color(0xFF4A473F),
    onTertiaryContainer = Color(0xFFE7E3D8),
    background = Color(0xFF111312),
    onBackground = Color(0xFFE2E4E0),
    surface = Color(0xFF111312),
    onSurface = Color(0xFFE2E4E0),
    surfaceVariant = Color(0xFF444843),
    onSurfaceVariant = Color(0xFFC5C9C2),
    outline = Color(0xFF8E938C),
)

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun PairingQrScannerScreen(
    onResult: (String) -> Unit,
    onCancel: () -> Unit,
    onFailure: (String?) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val hapticFeedback = LocalHapticFeedback.current
    var torchEnabled by rememberSaveable { mutableStateOf(false) }
    var torchAvailable by rememberSaveable { mutableStateOf(false) }
    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        hasCameraPermission = granted
    }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.qr_scanner_title)) },
                navigationIcon = {
                    IconButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                            onCancel()
                        },
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Close,
                            contentDescription = stringResource(R.string.cancel),
                        )
                    }
                },
                actions = {
                    if (torchAvailable) {
                        IconButton(
                            onClick = {
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                                torchEnabled = !torchEnabled
                            },
                        ) {
                            Icon(
                                imageVector = if (torchEnabled) {
                                    Icons.Filled.FlashlightOff
                                } else {
                                    Icons.Filled.FlashlightOn
                                },
                                contentDescription = stringResource(
                                    if (torchEnabled) {
                                        R.string.qr_scanner_flashlight_off
                                    } else {
                                        R.string.qr_scanner_flashlight_on
                                    }
                                ),
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    scrolledContainerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
    ) { padding ->
        if (hasCameraPermission) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
            ) {
                PairingQrCameraPreview(
                    onResult = onResult,
                    onFailure = onFailure,
                    torchEnabled = torchEnabled,
                    onTorchAvailabilityChanged = { available ->
                        torchAvailable = available
                        if (!available) {
                            torchEnabled = false
                        }
                    },
                    modifier = Modifier.fillMaxSize(),
                )
                Box(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .size(260.dp)
                        .border(
                            border = BorderStroke(
                                width = 3.dp,
                                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.92f),
                            ),
                            shape = RoundedCornerShape(28.dp),
                        ),
                )
                Surface(
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(16.dp)
                        .widthIn(max = 520.dp),
                    shape = RoundedCornerShape(8.dp),
                    color = MaterialTheme.colorScheme.surface.copy(alpha = 0.94f),
                    tonalElevation = 2.dp,
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Text(
                            text = stringResource(R.string.qr_scanner_detail),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        TextButton(
                            onClick = {
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                                onCancel()
                            },
                        ) {
                            Text(stringResource(R.string.cancel))
                        }
                    }
                }
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    text = stringResource(R.string.qr_scanner_permission_title),
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.size(12.dp))
                Text(
                    text = stringResource(R.string.qr_scanner_permission_detail),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                )
                Spacer(Modifier.size(18.dp))
                Button(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        permissionLauncher.launch(Manifest.permission.CAMERA)
                    },
                ) {
                    Text(stringResource(R.string.qr_scanner_permission_action))
                }
            }
        }
    }
}

@Composable
private fun PairingQrCameraPreview(
    onResult: (String) -> Unit,
    onFailure: (String?) -> Unit,
    torchEnabled: Boolean,
    onTorchAvailabilityChanged: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val resultConsumed = remember { AtomicBoolean(false) }
    val analyzerExecutor = remember { Executors.newSingleThreadExecutor() }
    val barcodeScanner = remember { BarcodeScanning.getClient() }
    var camera by remember { mutableStateOf<Camera?>(null) }

    LaunchedEffect(torchEnabled, camera) {
        camera?.cameraControl?.enableTorch(torchEnabled)
    }

    DisposableEffect(Unit) {
        onDispose {
            camera?.cameraControl?.enableTorch(false)
            analyzerExecutor.shutdown()
            barcodeScanner.close()
            onTorchAvailabilityChanged(false)
            runCatching {
                ProcessCameraProvider.getInstance(context).get().unbindAll()
            }
        }
    }

    AndroidView(
        modifier = modifier,
        factory = { viewContext ->
            PreviewView(viewContext).also { previewView ->
                val cameraProviderFuture = ProcessCameraProvider.getInstance(viewContext)
                cameraProviderFuture.addListener(
                    {
                        val cameraProvider = cameraProviderFuture.get()
                        val preview = Preview.Builder().build().also { preview ->
                            preview.setSurfaceProvider(previewView.surfaceProvider)
                        }
                        val analysis = ImageAnalysis.Builder()
                            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                            .build()
                            .also { imageAnalysis ->
                                imageAnalysis.setAnalyzer(analyzerExecutor) { imageProxy ->
                                    if (resultConsumed.get()) {
                                        imageProxy.close()
                                        return@setAnalyzer
                                    }
                                    val mediaImage = imageProxy.image
                                    if (mediaImage == null) {
                                        imageProxy.close()
                                        return@setAnalyzer
                                    }
                                    val inputImage = InputImage.fromMediaImage(
                                        mediaImage,
                                        imageProxy.imageInfo.rotationDegrees,
                                    )
                                    barcodeScanner.process(inputImage)
                                        .addOnSuccessListener { barcodes ->
                                            val rawValue = barcodes.firstAetherLinkPairingRawValueOrNull()
                                            if (rawValue != null && resultConsumed.compareAndSet(false, true)) {
                                                onResult(rawValue)
                                            }
                                        }
                                        .addOnFailureListener {
                                            // Individual frames can fail ML Kit processing while the camera stream is healthy.
                                            // Keep the scanner open for the next frame; setup/bind failures remain fatal below.
                                        }
                                        .addOnCompleteListener {
                                            imageProxy.close()
                                        }
                                }
                            }

                        runCatching {
                            cameraProvider.unbindAll()
                            val boundCamera = cameraProvider.bindToLifecycle(
                                lifecycleOwner,
                                CameraSelector.DEFAULT_BACK_CAMERA,
                                preview,
                                analysis,
                            )
                            camera = boundCamera
                            onTorchAvailabilityChanged(boundCamera.cameraInfo.hasFlashUnit())
                        }.onFailure { error ->
                            camera = null
                            onTorchAvailabilityChanged(false)
                            if (resultConsumed.compareAndSet(false, true)) {
                                onFailure(error.message)
                            }
                        }
                    },
                    ContextCompat.getMainExecutor(viewContext),
                )
            }
        },
    )
}

internal fun String.isAetherLinkPairingQrValue(): Boolean {
    return runCatching {
        RuntimePairingPayloadParser.parse(
            rawValue = trim(),
            allowDebugLoopbackRelay = BuildConfig.DEBUG,
            allowDiagnosticLocalDirectEndpoint = BuildConfig.DEBUG,
        )
    }.isSuccess
}

internal fun String.isAetherLinkPairingQrCandidateValue(): Boolean {
    val uri = runCatching { URI(trim()) }.getOrNull() ?: return false
    val scheme = uri.scheme?.lowercase(Locale.US)
    if (scheme != "aetherlink" && scheme != "lab") return false
    val action = uri.host?.lowercase(Locale.US)
    return action == "pair"
}

private fun List<Barcode>.firstAetherLinkPairingRawValueOrNull(): String? {
    return firstNotNullOfOrNull { barcode ->
        barcode.rawValue
            ?.takeIf { it.isNotBlank() }
            ?.takeIf { it.isAetherLinkPairingQrCandidateValue() }
    }
}

private fun Intent?.pairingUriOrNull(): String? {
    val uri = this?.data ?: return null
    return pairingUriStringOrNull(
        scheme = uri.scheme,
        host = uri.host,
        path = uri.path,
        rawUri = uri.toString(),
    )
}

internal fun pairingUriStringOrNull(
    scheme: String?,
    host: String?,
    path: String?,
    rawUri: String,
): String? {
    val normalizedScheme = scheme?.lowercase(Locale.US)
    if (normalizedScheme != "aetherlink" && normalizedScheme != "lab") return null
    val action = host?.lowercase(Locale.US)
    if (action != "pair") return null
    return rawUri
}
